"""Fetch the full article body for a URL.

Used by blurb generation to escape the "RSS snippet is too short" problem
that makes blurbs vague. Uses trafilatura (fast, well-maintained article
extractor). Falls back to readability-lxml or beautiful soup heuristics.

Cached on disk by URL hash with no TTL — article bodies don't change.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/article_cache")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (tldr-pipeline/0.1)"
)


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.txt"


def _extract_with_trafilatura(html: str) -> str:
    try:
        import trafilatura
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        return text or ""
    except ImportError:
        return ""
    except Exception:
        return ""


def _extract_with_soup(html: str) -> str:
    """Heuristic fallback: pull the longest <article> / main content block."""
    soup = BeautifulSoup(html, "lxml")
    candidates = soup.find_all(["article", "main"])
    if candidates:
        return max((c.get_text(" ", strip=True) for c in candidates), key=len)
    # Last resort: all <p>
    ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return " ".join(ps)


def fetch_body(url: str, max_chars: int = 3000) -> str:
    """Fetch and extract article body. Returns "" on failure. Cached forever."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(url)
    if cache_path.exists():
        return cache_path.read_text()[:max_chars]

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12, allow_redirects=True)
        if r.status_code != 200:
            cache_path.write_text("")
            return ""
        html = r.text
    except Exception as e:
        log.warning("Article fetch failed %s: %r", url, e)
        cache_path.write_text("")
        return ""

    text = _extract_with_trafilatura(html) or _extract_with_soup(html)
    text = (text or "").strip()
    cache_path.write_text(text)
    return text[:max_chars]


def batch_fetch(urls: list[str], concurrency: int = 6) -> dict[str, str]:
    from concurrent.futures import ThreadPoolExecutor

    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for url, body in zip(urls, pool.map(fetch_body, urls)):
            out[url] = body
    return out
