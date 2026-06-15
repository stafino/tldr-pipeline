from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import arxiv

from common.story import Story

log = logging.getLogger(__name__)

# Map arxiv categories → topic tags the ranking model uses.
ARXIV_TOPICS = {
    "cs.AI": ["ai"],
    "cs.LG": ["ai", "ml"],
    "cs.CL": ["ai", "ml"],
    "cs.CR": ["infosec"],
    "cs.SE": ["programming"],
    "cs.DB": ["data"],
    "cs.HC": ["design", "product"],
}


def pull_arxiv(
    categories: list[str],
    max_results_per_category: int = 30,
    lookback_hours: int = 48,
) -> list[Story]:
    """Pull recent arXiv submissions from a list of categories."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    client = arxiv.Client(page_size=max_results_per_category, delay_seconds=3.0, num_retries=2)
    stories: list[Story] = []

    for category in categories:
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results_per_category,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        try:
            results = list(client.results(search))
        except Exception as e:
            log.warning("arXiv pull failed for %s: %s", category, e)
            continue

        topics = ARXIV_TOPICS.get(category, [])

        for r in results:
            published = r.published
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published < cutoff:
                continue

            stories.append(
                Story(
                    title=r.title.strip().replace("\n", " "),
                    url=r.entry_id,
                    source=f"arxiv:{category}",
                    source_type="arxiv",
                    published_at=published.isoformat(),
                    raw_text=(r.summary or "").strip()[:4000],
                    source_topics=list(topics),
                )
            )

    log.info("arXiv: %d stories across %s", len(stories), categories)
    return stories
