from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import yaml

from common.story import write_jsonl
from ingestion.arxiv_puller import pull_arxiv
from ingestion.hn import pull_hn
from ingestion.rss import pull_all_rss
from ingestion.tldr_picks import pull_tldr_picks

log = logging.getLogger(__name__)


def _window(target_date: date, lookback_days: int) -> tuple[datetime, datetime]:
    """Inclusive 'last N days' window ending at the target date.

    For target=2026-06-15, lookback=2 → [2026-06-13 00:00 UTC, 2026-06-16 00:00 UTC).
    That covers the 13th, 14th, and the 15th, in line with the editorial intent
    of 'the last couple of days'.
    """
    end = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start = datetime.combine(target_date - timedelta(days=lookback_days), time.min, tzinfo=timezone.utc)
    return start, end


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--sources", default="config/sources.yaml")
    ap.add_argument("--out-dir", default="data/raw")
    ap.add_argument("--lookback-days", type=int, default=2, help="how many days back from the target")
    args = ap.parse_args()

    target = datetime.fromisoformat(args.date).date()
    after, before = _window(target, args.lookback_days)
    log.info("Ingestion window: [%s, %s)", after.isoformat(), before.isoformat())

    config = yaml.safe_load(Path(args.sources).read_text())

    stories = []
    stories.extend(pull_all_rss(config.get("rss", []), published_after=after, published_before=before))

    ax = config.get("arxiv", {})
    stories.extend(
        pull_arxiv(
            ax.get("categories", ["cs.AI"]),
            published_after=after,
            published_before=before,
            max_results_per_category=ax.get("max_results_per_category", 30),
        )
    )

    hn = config.get("hackernews", {})
    stories.extend(
        pull_hn(
            published_after=after,
            published_before=before,
            min_score=hn.get("min_score", 75),
        )
    )

    # TLDR's own previously-published picks - high-trust input that
    # closes the recall loop. Excludes today (the date the backtest
    # compares against) so we don't trivially self-match.
    stories.extend(pull_tldr_picks(target, lookback_days=7))

    out_path = Path(args.out_dir) / f"{args.date}.jsonl"
    write_jsonl(out_path, stories)
    log.info("Wrote %d stories to %s (window %s → %s)", len(stories), out_path, after.date(), before.date())


if __name__ == "__main__":
    main()
