from __future__ import annotations

import hashlib
import json
import logging
import socket
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

from common.story import Story

# Hard timeout for every RSS fetch. feedparser.parse(url) uses urllib's
# default which can hang for hours on a dead host (we saw a 50-min hang
# on thehackernews mid-cron). 15s gives flaky-but-alive feeds enough
# room while killing zombies fast.
FEED_TIMEOUT = 15
socket.setdefaulttimeout(FEED_TIMEOUT)

log = logging.getLogger(__name__)

RSS_CACHE_DIR = Path("data/rss_cache")


def _cache_paths(url: str) -> tuple[Path, Path]:
    h = hashlib.sha1(url.encode()).hexdigest()
    return RSS_CACHE_DIR / f"{h}.meta.json", RSS_CACHE_DIR / f"{h}.body"


def _fetch_feed_bytes(name: str, url: str) -> bytes | None:
    """GET the feed with conditional headers. On a 304 (unchanged since last
    run) re-serve the cached body instead of re-downloading. Output stories are
    identical either way - the raw file is overwritten each run, so we must
    still return every in-window entry, we just skip the wire transfer."""
    meta_path, body_path = _cache_paths(url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; lede/1.0)"}
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            meta = {}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]

    resp = requests.get(url, timeout=FEED_TIMEOUT, headers=headers)
    if resp.status_code == 304 and body_path.exists():
        log.info("RSS %s: 304 not-modified, serving cached body", name)
        return body_path.read_bytes()
    resp.raise_for_status()
    content = resp.content

    try:
        RSS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(content)
        new_meta: dict = {}
        if resp.headers.get("ETag"):
            new_meta["etag"] = resp.headers["ETag"]
        if resp.headers.get("Last-Modified"):
            new_meta["last_modified"] = resp.headers["Last-Modified"]
        meta_path.write_text(json.dumps(new_meta))
    except Exception as e:
        log.debug("RSS cache write failed for %s: %r", name, e)
    return content


def pull_rss(
    name: str,
    url: str,
    published_after: datetime,
    published_before: datetime,
    topics: list[str] | None = None,
) -> list[Story]:
    """Pull entries from a single RSS feed published within [after, before).

    Entries without a parseable publication date are dropped (rather than
    silently defaulted to 'now') - this matters for feeds like Paul Graham's
    that emit the full archive without dates.
    """
    # Pre-fetch with requests so we get a deterministic timeout, then hand
    # the raw bytes to feedparser. Avoids feedparser's hang-forever default.
    try:
        content = _fetch_feed_bytes(name, url)
        if not content:
            return []
        parsed = feedparser.parse(content)
    except Exception as e:
        log.warning("RSS pull failed for %s: %s", name, e)
        return []

    stories: list[Story] = []
    skipped_undated = 0

    for entry in parsed.entries:
        published = _entry_datetime(entry)
        if published is None:
            skipped_undated += 1
            continue
        if not (published_after <= published < published_before):
            continue

        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        if not title or not link:
            continue

        stories.append(
            Story(
                title=title,
                url=link,
                source=name,
                source_type="rss",
                published_at=published.isoformat(),
                raw_text=_entry_text(entry)[:4000],
                source_topics=list(topics or []),
            )
        )

    extra = f" ({skipped_undated} undated dropped)" if skipped_undated else ""
    log.info("RSS %s: %d stories%s", name, len(stories), extra)
    return stories


def _entry_datetime(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _entry_text(entry) -> str:
    for field in ("summary", "description"):
        v = entry.get(field)
        if v:
            return _strip_html(v)
    content = entry.get("content")
    if content and isinstance(content, list):
        return _strip_html(content[0].get("value", ""))
    return ""


def _strip_html(s: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(s, "lxml").get_text(" ", strip=True)


def pull_all_rss(
    sources: list[dict], published_after: datetime, published_before: datetime
) -> list[Story]:
    out: list[Story] = []
    for s in sources:
        out.extend(
            pull_rss(
                s["name"],
                s["url"],
                published_after=published_after,
                published_before=published_before,
                topics=s.get("topics"),
            )
        )
    return out
