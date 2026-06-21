"""HackerNews + Reddit engagement signal for a story URL.

Adds real-world reader signal to ranking - currently we score by LLM
judgment alone. HN points + comment counts are noisy but real proxies
for whether a story is actually getting attention.

Cached per URL with a 6-hour TTL because HN counts change rapidly in
the first day.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/engagement_cache")
TTL_SECONDS = 6 * 3600  # 6 hours
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
USER_AGENT = "tldr-pipeline-engagement/0.1"


@dataclass
class EngagementSignal:
    hn_points: int = 0
    hn_comments: int = 0
    hn_age_hours: int = 0
    found: bool = False

    def to_dict(self) -> dict:
        return {
            "hn_points": self.hn_points,
            "hn_comments": self.hn_comments,
            "hn_age_hours": self.hn_age_hours,
            "found": self.found,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EngagementSignal":
        return cls(
            hn_points=int(d.get("hn_points", 0)),
            hn_comments=int(d.get("hn_comments", 0)),
            hn_age_hours=int(d.get("hn_age_hours", 0)),
            found=bool(d.get("found", False)),
        )

    def summary(self) -> str:
        if not self.found:
            return "no HN signal"
        return f"HN: {self.hn_points} pts, {self.hn_comments} cmts, {self.hn_age_hours}h ago"


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < TTL_SECONDS


def fetch_signal(url: str) -> EngagementSignal:
    """Look up a URL on HN via Algolia. Cached for 6 hours."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(url)
    if _is_fresh(cache_path):
        try:
            return EngagementSignal.from_dict(json.loads(cache_path.read_text()))
        except Exception:
            pass

    try:
        r = requests.get(
            HN_SEARCH_URL,
            params={"query": url, "restrictSearchableAttributes": "url", "hitsPerPage": 3},
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        if r.status_code != 200:
            sig = EngagementSignal()
            cache_path.write_text(json.dumps(sig.to_dict()))
            return sig
        data = r.json()
        hits = data.get("hits", [])
        if not hits:
            sig = EngagementSignal()
            cache_path.write_text(json.dumps(sig.to_dict()))
            return sig
        # Take the highest-points hit
        best = max(hits, key=lambda h: h.get("points", 0))
        points = int(best.get("points", 0))
        comments = int(best.get("num_comments", 0))
        created_at_i = int(best.get("created_at_i", 0))
        age_hours = max(0, int((time.time() - created_at_i) / 3600)) if created_at_i else 0
        sig = EngagementSignal(
            hn_points=points, hn_comments=comments, hn_age_hours=age_hours, found=True
        )
        cache_path.write_text(json.dumps(sig.to_dict()))
        return sig
    except Exception as e:
        log.warning("Engagement fetch failed for %s: %r", url, e)
        sig = EngagementSignal()
        cache_path.write_text(json.dumps(sig.to_dict()))
        return sig


def batch_fetch(urls: list[str], concurrency: int = 8) -> dict[str, EngagementSignal]:
    """Fetch engagement signals in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    out: dict[str, EngagementSignal] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for url, sig in zip(urls, pool.map(fetch_signal, urls)):
            out[url] = sig
    return out
