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

from common.newsletters import load_newsletters
from common.story import ScoredStory, read_jsonl
from ranking.score import top_per_section

log = logging.getLogger(__name__)

BACKTEST_DIR = Path("data/backtest")
ARCHIVE_URL = "https://tldr.tech/{slug}/{d}"
USER_AGENT = "tldr-pipeline-backtest/0.2 (+contact@example.com)"
SIM_THRESHOLD = 0.72  # cosine sim — title-level, deliberately permissive

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

    def to_dict(self) -> dict:
        d = asdict(self)
        # asdict converts int keys to str; keep them as str for JSON anyway
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


def fetch_tldr_titles(newsletter_id: str, date: str) -> list[str]:
    """Scrape the published headlines from tldr.tech/<slug>/<date>.

    Returns an empty list if the page doesn't exist OR if it returned the
    newsletter's landing page (when the day's issue isn't published yet).
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
    titles: list[str] = []
    for tag in soup.find_all(["h3", "h2"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        # Only accept entries that look like real TLDR story headlines
        # (those carry the "(N minute read)" annotation in the rendered HTML).
        # Sponsor entries match the format too — skip them.
        if SPONSOR_RE.search(text):
            continue
        if not MINUTE_READ_RE.search(text):
            continue
        cleaned = _clean_title(text)
        if len(cleaned) < 6:
            continue
        titles.append(cleaned)

    # De-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


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
    tldr_titles: list[str], predicted_titles: list[str]
) -> tuple[list[int | None], list[float | None], list[bool]]:
    """For each prediction, find the best-matching TLDR title (if sim >= threshold).
    Returns (matched_tldr_idx_per_pred, similarity_per_pred, tldr_matched).
    """
    n_pred = len(predicted_titles)
    if not tldr_titles or not predicted_titles:
        return [None] * n_pred, [None] * n_pred, [False] * len(tldr_titles)

    embs = _embed(tldr_titles + predicted_titles)
    n_tldr = len(tldr_titles)
    tldr_e = embs[:n_tldr]
    pred_e = embs[n_tldr:]
    sims = pred_e @ tldr_e.T  # shape: (n_pred, n_tldr)

    matched_idx: list[int | None] = []
    matched_sim: list[float | None] = []
    tldr_hit = [False] * n_tldr
    for i in range(n_pred):
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
    """Return [(score, title, url), ...] for our top-30 predictions for this
    (newsletter, date), plus the total count of stories scored for that day."""
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
    return out[:30], total


def compute_backtest(newsletter_id: str, date: str) -> BacktestResult:
    tldr_titles = fetch_tldr_titles(newsletter_id, date)
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
        )

    predicted_titles = [p[1] for p in preds]
    matched_idx, matched_sim, tldr_hit = compute_matches(tldr_titles, predicted_titles)

    predictions = [
        PredictionMatch(
            rank=i + 1, score=preds[i][0], title=preds[i][1], url=preds[i][2],
            matched_tldr_idx=matched_idx[i],
            similarity=matched_sim[i],
        )
        for i in range(len(preds))
    ]

    # Recall@K: of TLDR's published titles, how many are matched by anything in our top-K?
    recall_at: dict[int, float] = {}
    hits_at: dict[int, int] = {}
    n_tldr = len(tldr_titles)
    for k in (10, 20, 30):
        kk = min(k, len(predicted_titles))
        # Recompute hits considering only the top-k predictions
        top_k_idx = [matched_idx[i] for i in range(kk) if matched_idx[i] is not None]
        hits = len(set(top_k_idx))
        hits_at[k] = hits
        recall_at[k] = hits / n_tldr if n_tldr else 0.0

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
