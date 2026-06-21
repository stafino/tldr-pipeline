"""Disk-backed key→JSON cache.

A few modules (funding, vc, the backfill script) all want the same
SHA1-hashed URL → JSON file pattern. This module owns it so the
implementation lives in exactly one place.

Use:
    cache = UrlJsonCache(Path("data/funding_cache"))
    if (hit := cache.load(url)):
        ...
    cache.save(url, payload)
    cache.delete(url)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional


class UrlJsonCache:
    """Sha1-keyed URL → JSON-file cache."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # ── key plumbing ────────────────────────────────────────────────────
    def path_for(self, url: str) -> Path:
        """Where a given URL's payload lives on disk (may not exist)."""
        h = hashlib.sha1(url.encode()).hexdigest()
        return self.root / f"{h}.json"

    # ── load / save / delete ────────────────────────────────────────────
    def load(self, url: str) -> Optional[dict]:
        """Return the cached payload for url, or None if absent / corrupt."""
        p = self.path_for(url)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def save(self, url: str, payload: dict) -> None:
        """Write payload as JSON. Creates the cache dir on first write."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.path_for(url).write_text(json.dumps(payload))

    def delete(self, url: str) -> bool:
        """Remove the cached entry. Returns True if a file was removed."""
        p = self.path_for(url)
        if p.exists():
            p.unlink()
            return True
        return False
