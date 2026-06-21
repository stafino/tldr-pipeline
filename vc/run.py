"""Run VC classification over a scored JSONL.

Usage:
  uv run python -m vc.run --date 2026-06-21
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from common.story import ScoredStory, read_jsonl
from vc.extract import extract_vc


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--in-dir", default="data/scored")
    ap.add_argument("--out-dir", default="data/vc")
    args = ap.parse_args()

    in_path = Path(args.in_dir) / f"{args.date}.jsonl"
    if not in_path.exists():
        logging.warning("no scored file for %s; skipping", args.date)
        return

    raw = read_jsonl(in_path)
    scored = [ScoredStory.from_dict(d) for d in raw]
    articles = extract_vc(scored)

    out_path = Path(args.out_dir) / f"{args.date}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for a in articles:
            f.write(json.dumps(a.to_dict()))
            f.write("\n")
    logging.info("wrote %d VC articles to %s", len(articles), out_path)


if __name__ == "__main__":
    main()
