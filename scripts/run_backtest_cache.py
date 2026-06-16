"""Update the backtest cache for a date range across all newsletters.

Usage:
  uv run python scripts/run_backtest_cache.py                      # today
  uv run python scripts/run_backtest_cache.py --date 2026-06-12
  uv run python scripts/run_backtest_cache.py --start 2026-06-10 --end 2026-06-16
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path

# Ensure the repo root is on sys.path so 'common.*' imports resolve when this
# script is invoked directly (uv run python scripts/...).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.backtest import compute_backtest, save  # noqa: E402
from common.newsletters import load_newsletters  # noqa: E402

log = logging.getLogger(__name__)


def _date_range(start: str, end: str) -> list[str]:
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    out = []
    while s <= e:
        out.append(s.isoformat())
        s += timedelta(days=1)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="single date (default: today)")
    ap.add_argument("--start", default=None, help="range start (inclusive)")
    ap.add_argument("--end", default=None, help="range end (inclusive)")
    ap.add_argument("--newsletter", default="all", help="specific newsletter id or 'all'")
    args = ap.parse_args()

    if args.start and args.end:
        dates = _date_range(args.start, args.end)
    elif args.date:
        dates = [args.date]
    else:
        dates = [_date.today().isoformat()]

    nls = load_newsletters()
    nl_ids = list(nls.keys()) if args.newsletter == "all" else [args.newsletter]

    total = len(dates) * len(nl_ids)
    log.info("Backtest cache update: %d date(s) × %d newsletter(s) = %d entries", len(dates), len(nl_ids), total)

    n_done = 0
    n_available = 0
    for d in dates:
        for nid in nl_ids:
            try:
                result = compute_backtest(nid, d)
                save(result)
                n_done += 1
                if result.available:
                    n_available += 1
                    r10 = result.recall_at.get(10, 0) * 100
                    log.info(
                        "  %s/%s: %d TLDR titles · %d predictions · recall@10=%.0f%%",
                        d, nid, len(result.tldr_titles), len(result.predictions), r10,
                    )
                else:
                    log.info("  %s/%s: TLDR archive not available", d, nid)
            except Exception as e:
                log.warning("  %s/%s: %r", d, nid, e)
                n_done += 1

    log.info("done: %d/%d entries written (%d had a published TLDR issue to compare)",
             n_done, total, n_available)


if __name__ == "__main__":
    main()
