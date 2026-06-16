"""Track URLs we've blurbed in past pipeline runs, so we can skip
regenerating blurbs for stories TLDR (or we) have already covered.

The set is built by scanning data/blurbs/*.jsonl files for the last N days
and returning a (newsletter, url) → blurb-date dict.

This is a complement to common/already_covered (which tracks what TLDR
actually published). past_blurbs tracks what WE blurbed regardless of
whether TLDR picked it.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)

BLURBS_DIR = Path("data/blurbs")


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


def build_past_blurbed_set(
    target_date: date, lookback_days: int = 14
) -> dict[tuple[str, str], str]:
    """Return {(newsletter, canonical_url): blurb_date} for blurbs we've
    produced in the lookback window ending at target_date (inclusive)."""
    out: dict[tuple[str, str], str] = {}
    if not BLURBS_DIR.exists():
        return out
    cutoff = target_date - timedelta(days=lookback_days)
    for f in BLURBS_DIR.glob("*.jsonl"):
        try:
            file_date = date.fromisoformat(f.stem)
        except Exception:
            continue
        if not (cutoff <= file_date <= target_date):
            continue
        try:
            with f.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    url = d.get("story_url", "")
                    nl = d.get("newsletter", "")
                    if not url or not nl:
                        continue
                    cu = _canonical_url(url)
                    key = (nl, cu)
                    # Keep the EARLIEST blurb date for the URL (first written)
                    if key not in out or file_date.isoformat() < out[key]:
                        out[key] = file_date.isoformat()
        except Exception as e:
            log.warning("Failed reading past blurb file %s: %r", f, e)
    return out
