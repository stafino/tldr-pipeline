from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path

from blurbs.generate import generate_for_sections
from common.newsletters import default_newsletter_id
from common.story import ScoredStory, read_jsonl
from ranking.score import top_per_section

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--in-dir", default="data/scored")
    ap.add_argument("--out-dir", default="data/blurbs")
    ap.add_argument("--newsletter", default=default_newsletter_id())
    args = ap.parse_args()

    raw = read_jsonl(Path(args.in_dir) / f"{args.date}.jsonl")
    scored = [ScoredStory.from_dict(d) for d in raw]
    by_section = top_per_section(scored, newsletter=args.newsletter)
    for sec_id, group in by_section.items():
        log.info("section %s: %d stories", sec_id, len(group))

    blurbs = generate_for_sections(by_section, newsletter=args.newsletter)

    out_path = Path(args.out_dir) / f"{args.date}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for b in blurbs:
            f.write(json.dumps(asdict(b)))
            f.write("\n")

    flagged = sum(1 for b in blurbs if b.needs_review)
    log.info("Wrote %d blurbs (%d flagged for review)", len(blurbs), flagged)


if __name__ == "__main__":
    main()
