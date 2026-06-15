"""Backtest the pipeline against actual TLDR AI issues.

For each day in the range:
  1. Scrape the TLDR AI archive page for that date.
  2. Extract the story titles TLDR actually published.
  3. Load our pipeline's top-N predicted stories for that same date.
  4. Count how many of TLDR's published titles are matched (cosine sim >= threshold)
     by something in our top-10 / top-20 / top-30.

Prints per-day and aggregate hit rates. This is the metric you'd put in a Loom.
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import requests
from bs4 import BeautifulSoup

from common.story import ScoredStory, read_jsonl

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://tldr.tech/ai/{d}"
USER_AGENT = "tldr-pipeline-backtest/0.1 (+contact@example.com)"
SIM_THRESHOLD = 0.78
TOP_K_BUCKETS = (10, 20, 30)


@dataclass
class DayResult:
    day: str
    tldr_titles: list[str]
    predicted_titles: list[str]
    hits_at: dict[int, int]  # K -> matched count


def fetch_tldr_titles(d: str) -> list[str]:
    url = ARCHIVE_URL.format(d=d)
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning("Failed fetch %s: %s", url, e)
        return []

    soup = BeautifulSoup(r.text, "lxml")
    titles: list[str] = []
    # TLDR's issue pages render each story headline as a heading-ish element.
    for tag in soup.find_all(["h3", "h2"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) < 8:
            continue
        if re.match(r"^(headlines|deep dives|engineering|research|miscellaneous|quick links)", text, re.I):
            continue
        if text.lower().startswith("tldr"):
            continue
        titles.append(text)

    # De-dupe preserving order.
    seen = set()
    out = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _embed(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    import os

    model_name = os.environ.get(
        "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    model = SentenceTransformer(model_name)
    return np.asarray(model.encode(texts, normalize_embeddings=True))


def compare_titles(tldr_titles: list[str], predicted_titles: list[str]) -> dict[int, int]:
    """Return K -> count of TLDR titles matched by anything in top-K of predicted."""
    if not tldr_titles or not predicted_titles:
        return {k: 0 for k in TOP_K_BUCKETS}

    embs = _embed(tldr_titles + predicted_titles)
    n_tldr = len(tldr_titles)
    tldr_e = embs[:n_tldr]
    pred_e = embs[n_tldr:]

    sims = tldr_e @ pred_e.T  # normalized -> cosine

    out: dict[int, int] = {}
    for k in TOP_K_BUCKETS:
        kk = min(k, len(predicted_titles))
        sub = sims[:, :kk]
        hits = int((sub.max(axis=1) >= SIM_THRESHOLD).sum())
        out[k] = hits
    return out


def backtest(start: str, end: str, scored_dir: Path) -> list[DayResult]:
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    cur = s
    results: list[DayResult] = []
    while cur <= e:
        d = cur.isoformat()
        tldr_titles = fetch_tldr_titles(d)
        scored_path = scored_dir / f"{d}.jsonl"
        if not scored_path.exists():
            log.warning("No scored output for %s; skipping", d)
            cur += timedelta(days=1)
            continue
        scored = [ScoredStory.from_dict(x) for x in read_jsonl(scored_path)]
        predicted_titles = [s.story.title for s in scored]
        hits = compare_titles(tldr_titles, predicted_titles)
        results.append(DayResult(day=d, tldr_titles=tldr_titles, predicted_titles=predicted_titles, hits_at=hits))
        log.info("%s: tldr=%d predicted=%d hits=%s", d, len(tldr_titles), len(predicted_titles), hits)
        cur += timedelta(days=1)
    return results


def print_summary(results: list[DayResult]) -> None:
    if not results:
        print("No days backtested.")
        return

    print(f"\n{'date':<12} {'tldr':>5} {'pred':>5}  " + "  ".join(f"hits@{k}" for k in TOP_K_BUCKETS))
    print("-" * 60)
    totals = {k: 0 for k in TOP_K_BUCKETS}
    tldr_total = 0
    for r in results:
        tldr_total += len(r.tldr_titles)
        for k in TOP_K_BUCKETS:
            totals[k] += r.hits_at[k]
        row = f"{r.day:<12} {len(r.tldr_titles):>5} {len(r.predicted_titles):>5}  " + "  ".join(
            f"{r.hits_at[k]:>6}" for k in TOP_K_BUCKETS
        )
        print(row)

    print("-" * 60)
    print(f"{'AGGREGATE':<12} {tldr_total:>5}      " + "  ".join(
        f"{totals[k]:>6}" for k in TOP_K_BUCKETS
    ))
    if tldr_total:
        rates = "  ".join(f"{totals[k] / tldr_total * 100:>5.1f}%" for k in TOP_K_BUCKETS)
        print(f"{'recall':<12}              {rates}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--scored-dir", default="data/scored")
    args = ap.parse_args()

    results = backtest(args.start, args.end, Path(args.scored_dir))
    print_summary(results)


if __name__ == "__main__":
    main()
