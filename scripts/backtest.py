"""Backtest each TLDR newsletter against its real archive.

For each (date, newsletter) pair we:
  1. Scrape https://tldr.tech/<slug>/<date> for the actual headlines.
  2. Load our pipeline's top-N predicted stories assigned to that newsletter.
  3. Count how many of TLDR's published titles are matched (cosine sim >= threshold)
     by something in our top-10 / top-20 / top-30 for that newsletter.

Prints per-newsletter and aggregate recall.
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import requests
from bs4 import BeautifulSoup

from common.newsletters import load_newsletters
from common.story import ScoredStory, read_jsonl
from ranking.score import top_per_section

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://tldr.tech/{slug}/{d}"
USER_AGENT = "tldr-pipeline-backtest/0.2 (+contact@example.com)"
SIM_THRESHOLD = 0.78
TOP_K_BUCKETS = (10, 20, 30)


@dataclass
class DayResult:
    day: str
    newsletter: str
    tldr_titles: list[str]
    predicted_titles: list[str]
    hits_at: dict[int, int] = field(default_factory=dict)


# Map newsletter id → URL slug under tldr.tech.
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


def fetch_titles(newsletter_id: str, d: str) -> list[str]:
    slug = SLUG_MAP.get(newsletter_id)
    if not slug:
        return []
    url = ARCHIVE_URL.format(slug=slug, d=d)
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning("Failed fetch %s: %s", url, e)
        return []

    soup = BeautifulSoup(r.text, "lxml")
    titles: list[str] = []
    for tag in soup.find_all(["h3", "h2"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) < 8:
            continue
        if re.match(
            r"^(headlines|deep dives|engineering|research|miscellaneous|quick links|"
            r"news|trends|strategies|tactics|tools|resources|innovations|markets|"
            r"opinions|tutorials|attacks|vulnerabilities|guides|launches)",
            text,
            re.I,
        ):
            continue
        if text.lower().startswith("tldr"):
            continue
        titles.append(text)

    seen = set()
    out: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _embed(texts: list[str]) -> np.ndarray:
    import os

    from sentence_transformers import SentenceTransformer

    model_name = os.environ.get(
        "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    model = SentenceTransformer(model_name)
    return np.asarray(model.encode(texts, normalize_embeddings=True))


def compare_titles(tldr_titles: list[str], predicted_titles: list[str]) -> dict[int, int]:
    if not tldr_titles or not predicted_titles:
        return {k: 0 for k in TOP_K_BUCKETS}
    embs = _embed(tldr_titles + predicted_titles)
    n_tldr = len(tldr_titles)
    tldr_e = embs[:n_tldr]
    pred_e = embs[n_tldr:]
    sims = tldr_e @ pred_e.T
    out: dict[int, int] = {}
    for k in TOP_K_BUCKETS:
        kk = min(k, len(predicted_titles))
        sub = sims[:, :kk]
        hits = int((sub.max(axis=1) >= SIM_THRESHOLD).sum())
        out[k] = hits
    return out


def predicted_titles_for(newsletter_id: str, d: str) -> list[str]:
    p = Path("data/scored") / f"{d}.jsonl"
    scored = [ScoredStory.from_dict(x) for x in read_jsonl(p)]
    if not scored:
        return []
    by_section = top_per_section(scored, newsletter_id)
    flat = []
    for stories in by_section.values():
        for s in stories:
            flat.append(s.story.title)
    return flat


def backtest(start: str, end: str, newsletter_ids: list[str]) -> list[DayResult]:
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    cur = s
    results: list[DayResult] = []
    while cur <= e:
        d = cur.isoformat()
        for nid in newsletter_ids:
            tldr_titles = fetch_titles(nid, d)
            predicted = predicted_titles_for(nid, d)
            if not predicted:
                log.info("%s %s: no predictions on disk; skipping", d, nid)
                cur_result = DayResult(day=d, newsletter=nid, tldr_titles=tldr_titles, predicted_titles=[], hits_at={k: 0 for k in TOP_K_BUCKETS})
                results.append(cur_result)
                continue
            hits = compare_titles(tldr_titles, predicted)
            results.append(DayResult(day=d, newsletter=nid, tldr_titles=tldr_titles, predicted_titles=predicted, hits_at=hits))
            log.info("%s %s: tldr=%d predicted=%d hits=%s", d, nid, len(tldr_titles), len(predicted), hits)
        cur += timedelta(days=1)
    return results


def print_summary(results: list[DayResult]) -> None:
    if not results:
        print("No backtest results.")
        return

    print()
    print(f"{'date':<12} {'newsletter':<18} {'tldr':>5} {'pred':>5}  " + "  ".join(f"hit@{k}" for k in TOP_K_BUCKETS))
    print("-" * 80)
    by_nl: dict[str, list[DayResult]] = {}
    for r in results:
        by_nl.setdefault(r.newsletter, []).append(r)
        print(
            f"{r.day:<12} {r.newsletter:<18} {len(r.tldr_titles):>5} {len(r.predicted_titles):>5}  "
            + "  ".join(f"{r.hits_at.get(k, 0):>5}" for k in TOP_K_BUCKETS)
        )
    print("-" * 80)
    print("aggregate recall by newsletter:")
    print()
    for nid, lst in by_nl.items():
        total_tldr = sum(len(r.tldr_titles) for r in lst)
        if not total_tldr:
            print(f"  {nid:<18}  no tldr titles fetched")
            continue
        for k in TOP_K_BUCKETS:
            total_hits = sum(r.hits_at.get(k, 0) for r in lst)
            rate = total_hits / total_tldr * 100
            print(f"  {nid:<18} @{k:<3} hits={total_hits:>3}/{total_tldr:<3}  recall={rate:5.1f}%")
        print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--newsletter", default="all", help="A specific id, or 'all'.")
    args = ap.parse_args()

    nls = load_newsletters()
    if args.newsletter == "all":
        nl_ids = list(nls.keys())
    else:
        nl_ids = [args.newsletter]

    results = backtest(args.start, args.end, nl_ids)
    print_summary(results)


if __name__ == "__main__":
    main()
