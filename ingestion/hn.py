from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from common.story import Story

log = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

AI_KEYWORDS = {
    "ai", "llm", "gpt", "openai", "anthropic", "claude", "gemini", "deepmind",
    "transformer", "diffusion", "agent", "rag", "embedding", "neural", "model",
    "training", "inference", "fine-tune", "prompt", "mistral", "qwen", "llama",
    "deepseek", "huggingface", "ml", "machine learning",
}


def pull_hn(min_score: int = 100, lookback_hours: int = 24, limit: int = 200) -> list[Story]:
    """Pull AI-relevant HN top stories above a score floor in the trailing window."""
    try:
        top_ids = requests.get(HN_TOP, timeout=10).json()[:limit]
    except Exception as e:
        log.warning("HN top fetch failed: %s", e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    stories: list[Story] = []

    for sid in top_ids:
        try:
            item = requests.get(HN_ITEM.format(id=sid), timeout=10).json()
        except Exception:
            continue
        if not item or item.get("type") != "story":
            continue
        if (item.get("score") or 0) < min_score:
            continue

        ts = item.get("time")
        if not ts:
            continue
        published = datetime.fromtimestamp(ts, tz=timezone.utc)
        if published < cutoff:
            continue

        title = (item.get("title") or "").strip()
        url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        if not title:
            continue

        if not _looks_ai_relevant(title):
            continue

        stories.append(
            Story(
                title=title,
                url=url,
                source="hackernews",
                source_type="hn",
                published_at=published.isoformat(),
                raw_text=f"HN score: {item.get('score')}, comments: {item.get('descendants', 0)}",
            )
        )

    log.info("HN: %d AI-relevant stories", len(stories))
    return stories


def _looks_ai_relevant(title: str) -> bool:
    lower = title.lower()
    return any(k in lower for k in AI_KEYWORDS)
