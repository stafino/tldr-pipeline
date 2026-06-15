from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from common.story import Story, read_jsonl, write_jsonl
from dedup.cluster import cluster_stories

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--in-dir", default="data/raw")
    ap.add_argument("--out-dir", default="data/deduped")
    ap.add_argument("--threshold", type=float, default=0.82)
    args = ap.parse_args()

    raw = read_jsonl(Path(args.in_dir) / f"{args.date}.jsonl")
    stories = [Story.from_dict(d) for d in raw]
    deduped = cluster_stories(stories, threshold=args.threshold)
    write_jsonl(Path(args.out_dir) / f"{args.date}.jsonl", deduped)
    log.info("Wrote %d deduped stories", len(deduped))


if __name__ == "__main__":
    main()
