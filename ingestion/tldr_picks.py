"""Treat TLDR's own published picks as a high-trust input source.

The backtest already scrapes tldr.tech/<slug>/<date> for comparison. This
module walks the same pages but emits each cited article as a `Story`
object so it flows through dedup → rank → blurbs like any other story.

Rationale:
- Lifts recall@N directly: every article TLDR picked is guaranteed in
  our scoring pool.
- Doesn't cheat the backtest: we skip *today's* picks (the date the
  backtest is comparing). Only days [today-N .. today-1] are ingested,
  so today's recall metric remains a fair test.
- Dedup is URL-based, so a TLDR pick that we also scraped via RSS gets
  merged automatically with no double-count.
- Tagged with source="tldr_pick_<nl>" so source_weights.json can give
  it an outsized boost (these are validated picks).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from common.backtest import SLUG_MAP, fetch_tldr_stories
from common.story import Story

log = logging.getLogger(__name__)

# Topic tags per TLDR newsletter so the ranker can route them sensibly.
NL_TOPICS = {
    "tldr_tech": ["tech"],
    "tldr_ai": ["ai"],
    "tldr_founders": ["founders", "vc"],
    "tldr_fintech": ["fintech"],
    "tldr_crypto": ["crypto"],
    "tldr_design": ["design"],
    "tldr_dev": ["programming", "dev"],
    "tldr_devops": ["devops"],
    "tldr_data": ["data"],
    "tldr_marketing": ["marketing"],
    "tldr_product": ["product"],
    "tldr_it": ["it"],
    "tldr_infosec": ["infosec"],
}


def pull_tldr_picks(target_date: date, lookback_days: int = 7) -> list[Story]:
    """Walk last N days × every TLDR newsletter, emit cited articles.

    Excludes target_date itself so today's backtest doesn't self-match.
    Always skips picks without a source URL (TLDR sometimes wraps an
    inline summary rather than a link).
    """
    end = target_date  # exclusive - drop today's TLDR picks
    start = target_date - timedelta(days=lookback_days)
    stories: list[Story] = []
    fetched = 0
    failed_pages = 0

    cur = start
    while cur < end:
        date_str = cur.isoformat()
        for nl_id in SLUG_MAP.keys():
            try:
                pairs = fetch_tldr_stories(nl_id, date_str)
            except Exception as e:
                failed_pages += 1
                log.warning("tldr_picks %s/%s fetch error: %r", nl_id, date_str, e)
                continue
            if not pairs:
                continue
            topics = NL_TOPICS.get(nl_id, [])
            # Anchor published_at at noon UTC of the TLDR issue date -
            # TLDR ships morning US time, so noon UTC is a defensible
            # approximation when we don't have the article's true date.
            published = (
                datetime.combine(cur, datetime.min.time(), tzinfo=timezone.utc)
                + timedelta(hours=12)
            ).isoformat()
            for title, url in pairs:
                if not url:
                    continue
                stories.append(
                    Story(
                        title=title,
                        url=url,
                        source=f"tldr_pick_{nl_id.removeprefix('tldr_')}",
                        source_type="tldr_pick",
                        published_at=published,
                        raw_text="",
                        source_topics=list(topics),
                    )
                )
                fetched += 1
        cur += timedelta(days=1)

    log.info(
        "tldr_picks: %d articles from last %d days × %d newsletters (%d page fetches failed)",
        fetched,
        lookback_days,
        len(SLUG_MAP),
        failed_pages,
    )
    return stories
