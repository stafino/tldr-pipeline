"""Rewrite predicted story titles in TLDR's headline style for honest backtest
matching.

The Fox/Roku case shows the problem: TLDR writes "Fox acquires Roku for $22B
to accelerate streaming advertising business"; we surface the original
"Fox wants to take over your TV". Title cosine misses these as a match
even though they're the same story.

Fix: use Haiku (cheap, fast) to rewrite each of our predicted titles in
TLDR-newsletter style, then match BOTH the original and the rewritten
title against TLDR's archive titles. Take the higher similarity.

Caching: titles cached forever by (url, newsletter) hash because the
rewrite is deterministic per story+newsletter context.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from common.llm import complete

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/title_rewrite_cache")
MODEL = os.environ.get("TITLE_REWRITE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM = """You rewrite story headlines in the style of TLDR newsletters.

TLDR's headline conventions:
- Lead with the actor or the most concrete claim.
- Include a number when one exists (dollar amounts, percentages, counts).
- Strip clickbait phrasing ("you won't believe", curiosity-gaps).
- Strip publication attribution from the headline body.
- 5-12 words typical; the headline is informational, not promotional.

Output ONLY the rewritten headline. No quotes, no preamble, no explanation."""


def _cache_path(url: str, newsletter: str) -> Path:
    h = hashlib.sha1(f"{url}|{newsletter}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.txt"


def rewrite_title(title: str, url: str, newsletter: str) -> str:
    """Return TLDR-style headline for a given story+newsletter context."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(url, newsletter)
    if cache.exists():
        return cache.read_text().strip()

    user = (
        f"Newsletter context: {newsletter}\n"
        f"Original title: {title}\n"
        f"Source URL: {url}\n\n"
        f"Rewrite as a TLDR-style headline."
    )
    try:
        rewritten = complete(SYSTEM, user, model=MODEL, max_tokens=80)
        rewritten = rewritten.strip().strip('"').strip("'").strip()
        # Strip any "Rewritten:" preamble the model might add
        for prefix in ("Rewritten:", "Headline:", "Title:"):
            if rewritten.lower().startswith(prefix.lower()):
                rewritten = rewritten[len(prefix):].strip()
        if not rewritten or len(rewritten) > 250:
            rewritten = title  # fall back to original on weird outputs
    except Exception as e:
        log.debug("Title rewrite failed for %s: %r", url, e)
        rewritten = title

    cache.write_text(rewritten)
    return rewritten


def batch_rewrite(items: list[tuple[str, str, str]], concurrency: int = 5) -> dict[str, str]:
    """Batch-rewrite. Items: list of (title, url, newsletter) tuples.
    Returns {url: rewritten_title}."""
    from concurrent.futures import ThreadPoolExecutor

    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(rewrite_title, t, u, n): u for t, u, n in items}
        for fut, url in futures.items():
            try:
                out[url] = fut.result()
            except Exception:
                # Find original title to fall back to
                for t, u, _ in items:
                    if u == url:
                        out[url] = t
                        break
    return out
