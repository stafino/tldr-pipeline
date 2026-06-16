"""Per-(newsletter, source-domain) preference weights, learned from
historical backtest data.

The data model:
  data/source_weights.json
  {
    "tldr_ai": {
      "openai.com":    {"picks": 12, "predictions": 30, "ratio": 0.40, "weight": 1.4},
      "anthropic.com": {"picks": 8,  "predictions": 22, "ratio": 0.36, "weight": 1.3},
      ...
    },
    ...
  }

Definitions:
  picks       — count of times TLDR <newsletter> published a story from this
                domain (mined from the archive over the last N days).
  predictions — count of times we (the pipeline) surfaced a story from this
                domain in our top-pool for the same newsletter.
  ratio       — picks / (picks + predictions_without_pick). High ratio = TLDR
                actually picks from this source when we surface it.
  weight      — derived score multiplier suggested for the ranker. Bayesian-smoothed
                against a global prior so domains with very few samples
                don't get extreme weights.

The ranker is told the top weighted sources per newsletter via the system prompt.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from common.backtest import BACKTEST_DIR, BacktestResult, load_cached
from common.newsletters import load_newsletters
from common.story import ScoredStory, read_jsonl

log = logging.getLogger(__name__)

WEIGHTS_PATH = Path("data/source_weights.json")

# Bayesian smoothing prior: pretend every source has +M virtual "predictions
# without a pick" so domains with very few samples regress to ratio ≈ 0.
SMOOTHING_M = 3
# Weight curve: ratio of 0.0 → 0.5; ratio of 0.5 → 1.5; ratio of 1.0 → 2.5
WEIGHT_INTERCEPT = 0.5
WEIGHT_SLOPE = 2.0


def _canonical_domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _picks_per_domain(newsletter_id: str) -> Counter:
    """Count how many times TLDR published a story from each source domain,
    across all cached backtest files for this newsletter."""
    counter: Counter = Counter()
    if not BACKTEST_DIR.exists():
        return counter
    for f in BACKTEST_DIR.glob(f"*-{newsletter_id}.json"):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if not d.get("available"):
            continue
        # tldr_urls field is new; older cache files don't have it. We can
        # reconstruct from predictions matched to TLDR titles when needed,
        # but cleanest is to re-mine. For now: look at the saved cache schema.
        # The current schema stores tldr_titles list. Domain isn't stored, so
        # we re-scrape via the mine_tldr_sources function. For speed, we cache
        # the result alongside the backtest file as `_tldr_domains` if present.
        domains = d.get("tldr_domains")
        if domains:
            for dom in domains:
                if dom:
                    counter[dom] += 1
    return counter


def _predictions_per_domain(newsletter_id: str, dates: list[str]) -> Counter:
    """Count how many times OUR pipeline surfaced a story from each source
    domain in the prediction pool for this newsletter, across the given dates."""
    from ranking.score import top_per_section

    counter: Counter = Counter()
    for d in dates:
        scored_path = Path("data/scored") / f"{d}.jsonl"
        if not scored_path.exists():
            continue
        try:
            scored = [ScoredStory.from_dict(x) for x in read_jsonl(scored_path)]
        except Exception:
            continue
        by_sec = top_per_section(scored, newsletter_id)
        for stories in by_sec.values():
            for s in stories:
                dom = _canonical_domain(s.story.url)
                if dom:
                    counter[dom] += 1
    return counter


@dataclass
class DomainStats:
    picks: int
    predictions: int
    ratio: float
    weight: float


def compute_weights(newsletter_id: str, dates: list[str]) -> dict[str, DomainStats]:
    picks = _picks_per_domain(newsletter_id)
    preds = _predictions_per_domain(newsletter_id, dates)
    all_domains = set(picks) | set(preds)
    out: dict[str, DomainStats] = {}
    for dom in all_domains:
        p = picks.get(dom, 0)
        n = preds.get(dom, 0)
        # Bayesian ratio with smoothing
        ratio = p / (p + n + SMOOTHING_M)
        weight = round(WEIGHT_INTERCEPT + WEIGHT_SLOPE * ratio, 3)
        out[dom] = DomainStats(picks=p, predictions=n, ratio=round(ratio, 3), weight=weight)
    return out


def update_all(dates_to_consider: list[str]) -> dict[str, dict[str, DomainStats]]:
    nls = load_newsletters()
    out: dict[str, dict[str, DomainStats]] = {}
    for nid in nls.keys():
        weights = compute_weights(nid, dates_to_consider)
        out[nid] = weights
        log.info("  %s: %d domains weighted (max picks=%d)", nid, len(weights),
                 max((s.picks for s in weights.values()), default=0))
    return out


def save_weights(weights: dict[str, dict[str, DomainStats]]) -> None:
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = {
        nid: {
            dom: {
                "picks": s.picks,
                "predictions": s.predictions,
                "ratio": s.ratio,
                "weight": s.weight,
            }
            for dom, s in domains.items()
        }
        for nid, domains in weights.items()
    }
    WEIGHTS_PATH.write_text(json.dumps(serialized, indent=2, sort_keys=True))


def load_weights() -> dict[str, dict[str, dict]]:
    if not WEIGHTS_PATH.exists():
        return {}
    try:
        return json.loads(WEIGHTS_PATH.read_text())
    except Exception:
        return {}


def top_favored_sources(newsletter_id: str, k: int = 10) -> list[tuple[str, float, int]]:
    """Return top-K sources by weight for a newsletter, as (domain, weight, picks)."""
    weights = load_weights().get(newsletter_id, {})
    rows = [
        (dom, float(s.get("weight", 1.0)), int(s.get("picks", 0)))
        for dom, s in weights.items()
        if s.get("picks", 0) > 0
    ]
    rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return rows[:k]


def format_for_prompt(newsletter_id: str, k: int = 12) -> str:
    """Build the system-prompt fragment listing learned source preferences.
    Empty string if no weights have been learned yet for this newsletter."""
    top = top_favored_sources(newsletter_id, k=k)
    if not top:
        return ""
    lines = [
        f"LEARNED SOURCE PREFERENCES for {newsletter_id} (from {sum(p for _, _, p in top)} historical picks):",
        "Stories from these domains have been frequently selected by TLDR. Give modest score boosts when applicable:",
    ]
    for dom, w, picks in top:
        lines.append(f"  - {dom}  (weight {w:.2f}, picked {picks}×)")
    return "\n".join(lines)
