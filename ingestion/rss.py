from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import feedparser

from common.story import Story

log = logging.getLogger(__name__)


def pull_rss(name: str, url: str, lookback_hours: int = 36, topics: list[str] | None = None) -> list[Story]:
    """Pull recent entries from a single RSS feed. Returns empty list on failure."""
    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        log.warning("RSS pull failed for %s: %s", name, e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    stories: list[Story] = []

    for entry in parsed.entries:
        published = _entry_datetime(entry)
        if published and published < cutoff:
            continue

        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        if not title or not link:
            continue

        raw_text = _entry_text(entry)
        stories.append(
            Story(
                title=title,
                url=link,
                source=name,
                source_type="rss",
                published_at=(published or datetime.now(timezone.utc)).isoformat(),
                raw_text=raw_text[:4000],
                source_topics=list(topics or []),
            )
        )

    log.info("RSS %s: %d stories", name, len(stories))
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


def pull_all_rss(sources: list[dict], lookback_hours: int = 36) -> list[Story]:
    out: list[Story] = []
    for s in sources:
        out.extend(
            pull_rss(
                s["name"],
                s["url"],
                lookback_hours=lookback_hours,
                topics=s.get("topics"),
            )
        )
    return out
