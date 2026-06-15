from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import yaml

from common.story import write_jsonl
from ingestion.arxiv_puller import pull_arxiv
from ingestion.hn import pull_hn
from ingestion.rss import pull_all_rss

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--sources", default="config/sources.yaml")
    ap.add_argument("--out-dir", default="data/raw")
    ap.add_argument("--rss-lookback-hours", type=int, default=48)
    args = ap.parse_args()

    config = yaml.safe_load(Path(args.sources).read_text())

    stories = []
    stories.extend(pull_all_rss(config.get("rss", []), lookback_hours=args.rss_lookback_hours))

    ax = config.get("arxiv", {})
    stories.extend(
        pull_arxiv(
            ax.get("categories", ["cs.AI"]),
            max_results_per_category=ax.get("max_results_per_category", 30),
            lookback_hours=ax.get("lookback_hours", 48),
        )
    )

    hn = config.get("hackernews", {})
    stories.extend(
        pull_hn(
            min_score=hn.get("min_score", 75),
            lookback_hours=hn.get("lookback_hours", 24),
        )
    )

    out_path = Path(args.out_dir) / f"{args.date}.jsonl"
    write_jsonl(out_path, stories)
    log.info("Wrote %d stories to %s", len(stories), out_path)


if __name__ == "__main__":
    main()
