"""Update per-newsletter source weights from the backtest cache.

Reads every cached BacktestResult under data/backtest/, looks at which
domains TLDR has picked stories from vs which our pipeline surfaced,
and writes data/source_weights.json. The ranker reads it on every run
and biases scoring toward sources that historically match TLDR's taste.

Run after each cron backtest stage so weights compound over time.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.backtest import BACKTEST_DIR  # noqa: E402
from common.source_weights import save_weights, update_all  # noqa: E402

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dates",
        nargs="*",
        default=None,
        help="optional date list (YYYY-MM-DD). Defaults to all dates we have scored data for.",
    )
    args = ap.parse_args()

    if args.dates:
        dates = args.dates
    else:
        # All dates we have a scored.jsonl for. The source-weight learner only
        # counts our predictions for the same dates we have backtest data on.
        scored_dir = Path("data/scored")
        dates = sorted(p.stem for p in scored_dir.glob("*.jsonl"))

    log.info("Updating source weights using %d date(s) of scored data", len(dates))
    log.info("Backtest cache directory: %s (%d files)", BACKTEST_DIR, len(list(BACKTEST_DIR.glob("*.json"))))

    weights = update_all(dates)
    save_weights(weights)
    log.info("Wrote data/source_weights.json")


if __name__ == "__main__":
    main()
