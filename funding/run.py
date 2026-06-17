"""Run funding extraction over a scored JSONL.

Usage:
  uv run python -m funding.run --date 2026-06-17
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from common.story import ScoredStory, read_jsonl
from funding.extract import extract_funding


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--in-dir", default="data/scored")
    ap.add_argument("--out-dir", default="data/funding")
    args = ap.parse_args()

    in_path = Path(args.in_dir) / f"{args.date}.jsonl"
    if not in_path.exists():
        logging.warning("no scored file for %s; skipping", args.date)
        return

    raw = read_jsonl(in_path)
    scored = [ScoredStory.from_dict(d) for d in raw]

    rounds = extract_funding(scored)

    out_path = Path(args.out_dir) / f"{args.date}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for r in rounds:
            f.write(json.dumps(r.to_dict()))
            f.write("\n")
    logging.info("wrote %d funding rounds to %s", len(rounds), out_path)


if __name__ == "__main__":
    main()
