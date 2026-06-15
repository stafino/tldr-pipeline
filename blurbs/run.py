from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from blurbs.generate import generate_for_newsletter
from common.newsletters import load_newsletters
from common.story import ScoredStory, read_jsonl

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--in-dir", default="data/scored")
    ap.add_argument("--out-dir", default="data/blurbs")
    ap.add_argument(
        "--newsletter",
        default="all",
        help="A specific newsletter id, or 'all' to generate for every newsletter.",
    )
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    raw = read_jsonl(Path(args.in_dir) / f"{args.date}.jsonl")
    scored = [ScoredStory.from_dict(d) for d in raw]

    nls = load_newsletters()
    if args.newsletter == "all":
        nl_ids = list(nls.keys())
    else:
        nl_ids = [args.newsletter]

    out_path = Path(args.out_dir) / f"{args.date}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Preserve blurbs for newsletters we're NOT regenerating.
    existing: list[dict] = []
    if out_path.exists():
        with out_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get("newsletter") not in nl_ids:
                    existing.append(d)

    fresh: list[dict] = []
    for nl_id in nl_ids:
        blurbs = generate_for_newsletter(scored, nl_id, use_cache=not args.no_cache)
        log.info("%s: %d blurbs", nl_id, len(blurbs))
        for b in blurbs:
            fresh.append(b.to_dict())

    with out_path.open("w") as f:
        for d in existing + fresh:
            f.write(json.dumps(d))
            f.write("\n")

    flagged = sum(1 for d in fresh if d.get("needs_review"))
    log.info("Wrote %d new blurbs across %d newsletters (%d flagged)", len(fresh), len(nl_ids), flagged)


if __name__ == "__main__":
    main()
