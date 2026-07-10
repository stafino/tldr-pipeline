from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from common.story import Story

log = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

TOPIC_KEYWORDS = {
    "ai": ("ai ", "llm", "gpt", "openai", "anthropic", "claude", "gemini", "deepmind",
           "transformer", "diffusion", "agent", "rag", "embedding", "neural",
           "fine-tune", "prompt", "mistral", "qwen", "llama", "deepseek",
           "huggingface", "machine learning"),
    "programming": ("typescript", "rust", "python", "go ", "kotlin", "framework",
                    "compile", "runtime", "library", "language", "code", "ide"),
    "infosec": ("vulnerab", "exploit", "cve", "breach", "ransom", "phishing",
                "malware", "zero-day", "supply chain attack", "security"),
    "devops": ("kubernetes", "k8s", "docker", "terraform", "sre", "observ", "ci/cd",
               "deploy"),
    "data": ("dbt", "snowflake", "databricks", "duckdb", "data engineer", "warehouse",
             "etl", "analytics", "spark"),
    "design": ("figma", "ux ", "ui design", "typography", "design system"),
    "crypto": ("bitcoin", "ethereum", "solana", "defi", "stablecoin", "blockchain",
               "web3", "nft"),
    "fintech": ("fintech", "neobank", "payment", "card issuer", "stablecoin"),
    "founders": ("startup", "founder", "seed round", "series a", "fundrais",
                 "raised $", "valuation", "go-to-market", "gtm"),
    "product": ("product manager", "roadmap", "user research", "discovery"),
    "marketing": ("seo", "ad spend", "growth hack", "demand gen", "brand campaign"),
}


def _topics_for(title: str) -> list[str]:
    lower = title.lower()
    return [topic for topic, kws in TOPIC_KEYWORDS.items() if any(k in lower for k in kws)]


def pull_hn(
    published_after: datetime,
    published_before: datetime,
    min_score: int = 75,
    limit: int = 300,
) -> list[Story]:
    try:
        top_ids = requests.get(HN_TOP, timeout=10).json()[:limit]
    except Exception as e:
        log.warning("HN top fetch failed: %s", e)
        return []

    # The firebase item API is one request per id; fetch them concurrently
    # instead of serially (was ~300 blocking round-trips).
    def _fetch_item(sid: int) -> dict | None:
        try:
            return requests.get(HN_ITEM.format(id=sid), timeout=10).json()
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        items = list(pool.map(_fetch_item, top_ids))

    stories: list[Story] = []

    for sid, item in zip(top_ids, items):
        if not item or item.get("type") != "story":
            continue
        if (item.get("score") or 0) < min_score:
            continue

        ts = item.get("time")
        if not ts:
            continue
        published = datetime.fromtimestamp(ts, tz=timezone.utc)
        if not (published_after <= published < published_before):
            continue

        title = (item.get("title") or "").strip()
        url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        if not title:
            continue

        topics = _topics_for(title)
        if not topics:
            topics = ["tech"]

        stories.append(
            Story(
                title=title,
                url=url,
                source="hackernews",
                source_type="hn",
                published_at=published.isoformat(),
                raw_text=f"HN score: {item.get('score')}, comments: {item.get('descendants', 0)}",
                source_topics=topics,
            )
        )

    log.info("HN: %d stories above score=%d in window", len(stories), min_score)
    return stories
