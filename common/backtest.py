"""Compare our daily predictions against what TLDR actually published.

The cache file format is one JSON per (newsletter, date) pair so the UI can
load it without re-scraping or re-embedding. The cron updates the cache after
each refresh.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from common.story import ScoredStory, read_jsonl
from ranking.score import top_per_section

log = logging.getLogger(__name__)

BACKTEST_DIR = Path("data/backtest")
ARCHIVE_URL = "https://tldr.tech/{slug}/{d}"
USER_AGENT = "tldr-pipeline-backtest/0.3 (+contact@example.com)"

# Title-cosine threshold. Lowered from 0.72 → 0.62 now that URL-overlap acts as
# a strong cross-check - fewer false positives, more true matches caught.
SIM_THRESHOLD = 0.62

SLUG_MAP = {
    "tldr_tech": "tech",
    "tldr_ai": "ai",
    "tldr_founders": "founders",
    "tldr_dev": "dev",
    "tldr_data": "data",
    "tldr_design": "design",
    "tldr_infosec": "infosec",
    "tldr_it": "it",
    "tldr_devops": "devops",
    "tldr_marketing": "marketing",
    "tldr_product": "product",
    "tldr_crypto": "crypto",
    "tldr_fintech": "fintech",
}


@dataclass
class PredictionMatch:
    rank: int
    score: float
    title: str
    url: str
    matched_tldr_idx: int | None  # which TLDR title this matched (if any)
    similarity: float | None


@dataclass
class BacktestResult:
    date: str
    newsletter: str
    fetched_at: str
    tldr_titles: list[str]
    tldr_matched: list[bool]               # per TLDR title: did we surface it in our top-30?
    predictions: list[PredictionMatch]      # ranked list of our predictions
    recall_at: dict[int, float] = field(default_factory=dict)   # K → recall
    hits_at: dict[int, int] = field(default_factory=dict)
    available: bool = True                  # False if TLDR's archive page didn't exist
    tldr_urls: list[str] = field(default_factory=list)     # source URLs aligned with tldr_titles
    tldr_domains: list[str] = field(default_factory=list)  # canonical domains, used by source-weight learner

    def to_dict(self) -> dict:
        d = asdict(self)
        d["recall_at"] = {str(k): v for k, v in self.recall_at.items()}
        d["hits_at"] = {str(k): v for k, v in self.hits_at.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestResult":
        return cls(
            date=d["date"],
            newsletter=d["newsletter"],
            fetched_at=d["fetched_at"],
            tldr_titles=d["tldr_titles"],
            tldr_matched=d.get("tldr_matched", []),
            predictions=[PredictionMatch(**p) for p in d["predictions"]],
            recall_at={int(k): float(v) for k, v in d.get("recall_at", {}).items()},
            hits_at={int(k): int(v) for k, v in d.get("hits_at", {}).items()},
            available=d.get("available", True),
            tldr_urls=d.get("tldr_urls", []),
            tldr_domains=d.get("tldr_domains", []),
        )


# ────────────────────────────────────────────────────────────────────────────
# Scraping
# ────────────────────────────────────────────────────────────────────────────
# Real TLDR story headlines end with "(N minute read)". Sponsor entries end
# with "(Sponsor)". Anything else is chrome (subject line, sponsor ads,
# section headers, footer). This pattern is the single strongest signal we
# can use to filter junk.
MINUTE_READ_RE = re.compile(r"\s*\(\d+\s*minute\s*read\)\s*$", re.I)
SPONSOR_RE = re.compile(r"\s*\(sponsor\)\s*$", re.I)


def _clean_title(text: str) -> str:
    """Strip the trailing (N minute read) suffix so the title matches our
    predicted story title (which doesn't have the read-time annotation)."""
    return MINUTE_READ_RE.sub("", text).strip()


def _canonical_url(url: str) -> str:
    """Strip tracking params + normalize for cross-source comparison.
    Example:
      https://www.example.com/post?utm_source=tldr&utm_campaign=x → example.com/post
    """
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        # Strip query string entirely (utm_*, ref=, etc.) - TLDR appends ?utm_source=tldrai
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        # Re-build without scheme/query/fragment
        return f"{host}{p.path}".rstrip("/")
    except Exception:
        return url.lower().rstrip("/")


def fetch_tldr_titles(newsletter_id: str, date: str) -> list[str]:
    """Backward-compat wrapper returning just titles. New code should use
    fetch_tldr_stories() which returns (title, url) pairs."""
    return [t for t, _ in fetch_tldr_stories(newsletter_id, date)]


SANE_MAX_TITLES = 30  # TLDR issues never carry more than ~20-25 articles


def fetch_tldr_stories(newsletter_id: str, date: str) -> list[tuple[str, str]]:
    """Scrape the published headlines AND source URLs from tldr.tech/<slug>/<date>.

    Returns list of (title, source_url) tuples. URL may be "" if not found.
    Returns an empty list if the page doesn't exist, OR if it returned an
    archive/landing fallback (when the day's issue isn't published yet -
    tldr.tech responds 200 with a multi-issue aggregate in that case,
    yielding 100+ titles, which always means "no issue today" not "huge
    issue today"). The SANE_MAX_TITLES threshold catches the fallback.
    """
    slug = SLUG_MAP.get(newsletter_id)
    if not slug:
        return []
    url = ARCHIVE_URL.format(slug=slug, d=date)
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if r.status_code == 404:
            return []
        r.raise_for_status()
    except Exception as e:
        log.warning("Failed fetch %s: %s", url, e)
        return []

    soup = BeautifulSoup(r.text, "lxml")
    out: list[tuple[str, str]] = []
    for tag in soup.find_all(["h3", "h2"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if SPONSOR_RE.search(text):
            continue
        if not MINUTE_READ_RE.search(text):
            continue
        cleaned = _clean_title(text)
        if len(cleaned) < 6:
            continue
        # TLDR wraps each <h3> heading in a parent <a> that links to the
        # source URL. Find the closest parent <a> with an href.
        link = tag.find_parent("a", href=True)
        if not link:
            # Fallbacks for the rare cases where the heading isn't wrapped:
            # check inside, then next/previous sibling anchors.
            link = tag.find("a", href=True)
        src_url = ""
        if link:
            href = link.get("href", "")
            if href.startswith("http") and "tldr.tech" not in href:
                src_url = href.split("?")[0]  # strip TLDR's utm trailer
        out.append((cleaned, src_url))

    # De-dupe by title preserving order
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for t, u in out:
        if t not in seen:
            seen.add(t)
            deduped.append((t, u))

    if len(deduped) > SANE_MAX_TITLES:
        log.warning(
            "tldr.tech/%s/%s returned %d titles - treating as not-yet-published "
            "archive fallback (real issues never exceed ~25 articles)",
            slug,
            date,
            len(deduped),
        )
        return []

    return deduped


# ────────────────────────────────────────────────────────────────────────────
# Matching via title embeddings
# ────────────────────────────────────────────────────────────────────────────
def _embed(texts: list[str]) -> np.ndarray:
    import os

    from sentence_transformers import SentenceTransformer

    model_name = os.environ.get(
        "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    model = SentenceTransformer(model_name)
    return np.asarray(model.encode(texts, normalize_embeddings=True))


def compute_matches(
    tldr_titles: list[str],
    predicted_titles: list[str],
    tldr_urls: list[str] | None = None,
    predicted_urls: list[str] | None = None,
    predicted_titles_rewritten: list[str] | None = None,
) -> tuple[list[int | None], list[float | None], list[bool]]:
    """For each prediction, find the best-matching TLDR story.

    A match is recorded when ANY of these is true:
      - URL match: canonical(pred_url) == canonical(tldr_url) (similarity = 1.0)
      - Cosine similarity of ORIGINAL or TLDR-style REWRITTEN title >= SIM_THRESHOLD

    Returns (matched_tldr_idx_per_pred, similarity_per_pred, tldr_matched).
    """
    n_pred = len(predicted_titles)
    if not tldr_titles or not predicted_titles:
        return [None] * n_pred, [None] * n_pred, [False] * len(tldr_titles)

    n_tldr = len(tldr_titles)
    tldr_urls = tldr_urls or [""] * n_tldr
    predicted_urls = predicted_urls or [""] * n_pred

    # Canonicalize URLs once
    tldr_url_canon = [_canonical_url(u) for u in tldr_urls]
    pred_url_canon = [_canonical_url(u) for u in predicted_urls]
    url_to_tldr_idx: dict[str, int] = {}
    for i, u in enumerate(tldr_url_canon):
        if u and u not in url_to_tldr_idx:
            url_to_tldr_idx[u] = i

    # Title embeddings - embed both original and rewritten variants so we
    # can take the best similarity score per prediction.
    has_rewrites = bool(predicted_titles_rewritten) and len(predicted_titles_rewritten) == n_pred
    if has_rewrites:
        all_titles = tldr_titles + predicted_titles + predicted_titles_rewritten
    else:
        all_titles = tldr_titles + predicted_titles
    embs = _embed(all_titles)
    tldr_e = embs[:n_tldr]
    pred_e = embs[n_tldr:n_tldr + n_pred]
    sims_orig = pred_e @ tldr_e.T  # (n_pred, n_tldr)
    if has_rewrites:
        pred_rw_e = embs[n_tldr + n_pred:]
        sims_rw = pred_rw_e @ tldr_e.T
        # Per-(pred, tldr) take max of original vs rewritten similarity
        sims = np.maximum(sims_orig, sims_rw)
    else:
        sims = sims_orig

    matched_idx: list[int | None] = []
    matched_sim: list[float | None] = []
    tldr_hit = [False] * n_tldr

    for i in range(n_pred):
        # 1) URL match (highest confidence)
        url_match = url_to_tldr_idx.get(pred_url_canon[i])
        if url_match is not None:
            matched_idx.append(url_match)
            matched_sim.append(1.0)
            tldr_hit[url_match] = True
            continue
        # 2) Title cosine match (best of original + rewritten)
        j = int(np.argmax(sims[i]))
        s = float(sims[i][j])
        if s >= SIM_THRESHOLD:
            matched_idx.append(j)
            matched_sim.append(s)
            tldr_hit[j] = True
        else:
            matched_idx.append(None)
            matched_sim.append(None)
    return matched_idx, matched_sim, tldr_hit


def _predicted_titles_and_urls(
    newsletter_id: str, date: str
) -> tuple[list[tuple[float, str, str]], int]:
    """Return [(score, title, url), ...] for ALL the predictions we'd display
    for this (newsletter, date). The set comes from top_per_section, which
    respects each section's target_count - so the size scales with the
    newsletters.yaml config (currently 25 × 5 sections = up to 125 per newsletter).

    Returns also the total count of stories scored that day (for context)."""
    p = Path("data/scored") / f"{date}.jsonl"
    if not p.exists():
        return [], 0
    scored = [ScoredStory.from_dict(d) for d in read_jsonl(p)]
    total = len(scored)
    by_section = top_per_section(scored, newsletter_id)
    out: list[tuple[float, str, str]] = []
    for stories in by_section.values():
        for s in stories:
            a = s.for_newsletter(newsletter_id)
            if a:
                out.append((a.score, s.story.title, s.story.url))
    out.sort(key=lambda x: x[0], reverse=True)
    return out, total


def compute_backtest(newsletter_id: str, date: str) -> BacktestResult:
    tldr_pairs = fetch_tldr_stories(newsletter_id, date)
    tldr_titles = [t for t, _ in tldr_pairs]
    tldr_urls = [u for _, u in tldr_pairs]
    preds, _ = _predicted_titles_and_urls(newsletter_id, date)

    if not tldr_titles:
        return BacktestResult(
            date=date,
            newsletter=newsletter_id,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            tldr_titles=[],
            tldr_matched=[],
            predictions=[
                PredictionMatch(rank=i + 1, score=sc, title=t, url=u,
                                matched_tldr_idx=None, similarity=None)
                for i, (sc, t, u) in enumerate(preds)
            ],
            recall_at={},
            hits_at={},
            available=False,
            tldr_urls=[],
            tldr_domains=[],
        )

    predicted_titles = [p[1] for p in preds]
    predicted_urls = [p[2] for p in preds]

    # Title rewriting for honest backtest measurement: rewrite each prediction
    # in TLDR-style and match both the original and the rewritten against
    # TLDR's published titles. Catches the Fox/Roku case where the same story
    # has very different rewritten headlines.
    predicted_titles_rewritten: list[str] = []
    try:
        from common.title_rewrite import batch_rewrite
        rewrites = batch_rewrite(
            [(t, u, newsletter_id) for t, u in zip(predicted_titles, predicted_urls)],
            concurrency=5,
        )
        predicted_titles_rewritten = [rewrites.get(u, t) for t, u in zip(predicted_titles, predicted_urls)]
    except Exception as e:
        log.warning("Title rewriting failed for %s/%s, falling back to originals: %r",
                    newsletter_id, date, e)
        predicted_titles_rewritten = list(predicted_titles)

    matched_idx, matched_sim, tldr_hit = compute_matches(
        tldr_titles, predicted_titles, tldr_urls=tldr_urls, predicted_urls=predicted_urls,
        predicted_titles_rewritten=predicted_titles_rewritten,
    )

    predictions = [
        PredictionMatch(
            rank=i + 1, score=preds[i][0], title=preds[i][1], url=preds[i][2],
            matched_tldr_idx=matched_idx[i],
            similarity=matched_sim[i],
        )
        for i in range(len(preds))
    ]

    # Recall@K: of TLDR's published titles, how many are matched by anything
    # in our top-K predictions? Wider K set so the dashboard shows both
    # display-tier (10, 25, 50) and full-ranker-signal (100, all) tiers.
    recall_at: dict[int, float] = {}
    hits_at: dict[int, int] = {}
    n_tldr = len(tldr_titles)
    n_pred = len(predicted_titles)
    k_targets = (10, 25, 50, 100, n_pred)
    for k in k_targets:
        kk = min(k, n_pred)
        top_k_idx = [matched_idx[i] for i in range(kk) if matched_idx[i] is not None]
        hits = len(set(top_k_idx))
        hits_at[k] = hits
        recall_at[k] = hits / n_tldr if n_tldr else 0.0

    tldr_domains = [
        (urlparse(u).netloc.lower().lstrip("www.") if u else "")
        for u in tldr_urls
    ]
    # Strip the www. prefix consistently
    tldr_domains = [d[4:] if d.startswith("www.") else d for d in tldr_domains]

    return BacktestResult(
        date=date,
        newsletter=newsletter_id,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        tldr_titles=tldr_titles,
        tldr_matched=tldr_hit,
        predictions=predictions,
        recall_at=recall_at,
        hits_at=hits_at,
        available=True,
        tldr_urls=tldr_urls,
        tldr_domains=tldr_domains,
    )


# ────────────────────────────────────────────────────────────────────────────
# Cache I/O
# ────────────────────────────────────────────────────────────────────────────
def cache_path(newsletter_id: str, date: str) -> Path:
    return BACKTEST_DIR / f"{date}-{newsletter_id}.json"


def save(result: BacktestResult) -> None:
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    p = cache_path(result.newsletter, result.date)
    p.write_text(json.dumps(result.to_dict(), indent=2))


def load_cached(newsletter_id: str, date: str) -> BacktestResult | None:
    p = cache_path(newsletter_id, date)
    if not p.exists():
        return None
    try:
        return BacktestResult.from_dict(json.loads(p.read_text()))
    except Exception as e:
        log.warning("Backtest cache read failed for %s: %s", p, e)
        return None


def all_cached_dates() -> list[str]:
    """All dates that have at least one backtest cache file."""
    if not BACKTEST_DIR.exists():
        return []
    dates: set[str] = set()
    for f in BACKTEST_DIR.glob("*.json"):
        stem = f.stem  # e.g. 2026-06-16-tldr_ai
        # date is first 10 chars
        if len(stem) >= 10:
            dates.add(stem[:10])
    return sorted(dates, reverse=True)


def load_all_for(newsletter_id: str, last_n_days: int = 7) -> list[BacktestResult]:
    """Load the last N days of cached results for a newsletter, oldest-first."""
    results = []
    dates = all_cached_dates()[:last_n_days]
    for d in sorted(dates):
        r = load_cached(newsletter_id, d)
        if r is not None:
            results.append(r)
    return results
