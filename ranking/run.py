from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from common.story import Story, read_jsonl, write_jsonl
from ranking.score import rank_stories

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--in-dir", default="data/deduped")
    ap.add_argument("--out-dir", default="data/scored")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    raw = read_jsonl(Path(args.in_dir) / f"{args.date}.jsonl")
    stories = [Story.from_dict(d) for d in raw]
    scored = rank_stories(stories, use_cache=not args.no_cache)
    write_jsonl(Path(args.out_dir) / f"{args.date}.jsonl", scored)
    log.info("Wrote %d scored stories", len(scored))


if __name__ == "__main__":
    main()
