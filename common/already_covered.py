"""Build a 'recently covered by TLDR' URL set from the backtest cache, so the
ranker can avoid recommending stories TLDR already published in the last 14 days.

Reads data/backtest/*.json files in a sliding window. For each cached
BacktestResult that has tldr_urls populated, accumulate canonical
URL → newsletter mapping.

The ranker uses this to flag predictions as 'already covered' and apply a
sharp negative score adjustment.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)

BACKTEST_DIR = Path("data/backtest")


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return f"{host}{p.path}".rstrip("/")
    except Exception:
        return url.lower().rstrip("/")


def build_covered_set(target_date: date, lookback_days: int = 14) -> dict[str, list[str]]:
    """Return {canonical_url: [newsletter_id, ...]} for stories TLDR has
    published in the lookback window ending at target_date (inclusive)."""
    out: dict[str, list[str]] = {}
    if not BACKTEST_DIR.exists():
        return out

    cutoff = target_date - timedelta(days=lookback_days)
    for f in BACKTEST_DIR.glob("*.json"):
        # filename: YYYY-MM-DD-tldr_<id>.json
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if not d.get("available"):
            continue
        try:
            file_date = date.fromisoformat(d.get("date", ""))
        except Exception:
            continue
        if not (cutoff <= file_date <= target_date):
            continue
        nl = d.get("newsletter", "")
        urls = d.get("tldr_urls", [])
        for u in urls:
            cu = _canonical_url(u)
            if cu:
                out.setdefault(cu, []).append(nl)
    return out
