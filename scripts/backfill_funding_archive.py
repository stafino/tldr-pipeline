"""Backfill funding rounds by walking source archive pages.

Why: the cron pipeline only stores articles it actually scored, so the
Funding tab is blank for any date before the pipeline started running.
This one-off walks paginated archive pages of funding-heavy sources
(TC Venture for now), extracts (url, title, date), runs the existing
LLM funding-extractor over the candidates, and merges results into
data/funding/<date>.jsonl keyed by article publish date.

Usage:
  uv run python scripts/backfill_funding_archive.py --days 14
  uv run python scripts/backfill_funding_archive.py --days 14 --dry-run

Only TC Venture is implemented today. The article cache + dedup in
funding.extract make re-runs cheap.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

from common.article_fetch import fetch_body
from common.story import ScoredStory, Story
from funding.extract import TITLE_KEYWORDS, _cache_path, _extract_one

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"}

OUT_DIR = Path("data/funding")


# ─── source: TechCrunch daily archives ──────────────────────────────────────

TC_URL_RE = re.compile(
    r"https?://techcrunch\.com/(20\d{2})/(\d{1,2})/(\d{1,2})/[a-z0-9-]+/?"
)


def tc_walk_dates(start: date, end: date) -> list[tuple[str, str, date]]:
    """Walk TC's daily-archive URLs (one HTTP request per date).

    TC exposes /YYYY/MM/DD/ pages that list every article published that day.
    Way higher yield than /category/venture/ because TC files funding news
    under many categories, not just "venture".
    """
    out: list[tuple[str, str, date]] = []
    seen: set[str] = set()
    d = start
    while d <= end:
        url = f"https://techcrunch.com/{d.year:04d}/{d.month:02d}/{d.day:02d}/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            log.warning("tc %s fetch error: %r", d, e)
            d += timedelta(days=1)
            continue
        if r.status_code != 200:
            log.warning("tc %s HTTP %d", d, r.status_code)
            d += timedelta(days=1)
            continue
        soup = BeautifulSoup(r.text, "lxml")
        day_added = 0
        for a in soup.select(f'a[href*="techcrunch.com/{d.year:04d}/{d.month:02d}/"]'):
            href = a.get("href", "")
            m = TC_URL_RE.match(href)
            if not m:
                continue
            # Only keep articles whose URL-encoded date matches the page date —
            # filters out TC's "related stories" sidebar from other days.
            art_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if art_date != d:
                continue
            canon = m.group(0).rstrip("/")
            if not canon.startswith("http"):
                canon = "https://" + canon
            if canon in seen:
                continue
            seen.add(canon)
            title = a.get_text(strip=True)
            if not title or len(title) < 12:
                continue
            out.append((canon, title, art_date))
            day_added += 1
        log.info("tc %s: %d articles", d, day_added)
        d += timedelta(days=1)
    return out


# ─── source: EU funding RSS feeds (last ~N days of items) ──────────────────

EU_FEEDS = [
    # EU regional press
    ("tech_eu", "https://tech.eu/feed"),
    ("silicon_canals", "https://siliconcanals.com/feed/"),
    ("maddyness", "https://www.maddyness.com/feed/"),
    ("maddyness_uk", "https://www.maddyness.com/uk/feed/"),
    ("uktech_news", "https://www.uktech.news/feed/"),
    ("sifted_titles", "https://sifted.eu/feed"),
    ("eu_startups", "https://www.eu-startups.com/feed/"),
    # Added 2026-06-17 — broader EU databases + dedicated funding feeds
    ("crunchbase_news", "https://news.crunchbase.com/feed/"),
    ("techfundingnews", "https://techfundingnews.com/feed/"),
    ("uktech_funding", "https://www.uktech.news/funding/feed/"),
    ("startups_co_uk", "https://startups.co.uk/news/feed/"),
    ("businesscloud_uk", "https://businesscloud.co.uk/feed/"),
    ("vc_cafe", "https://www.vccafe.com/feed/"),
    ("the_recursive", "https://therecursive.com/feed/"),
    ("startupbusiness_it", "https://www.startupbusiness.it/feed"),
    ("deutsche_startups", "https://www.deutsche-startups.de/feed/"),
    ("gruenderszene", "https://www.gruenderszene.de/feed"),
    ("frenchweb", "https://www.frenchweb.fr/feed"),
    ("startupdaily_au", "https://startupdaily.net/feed/"),
]


def eu_walk_rss(oldest_allowed: date) -> list[tuple[str, str, date, str]]:
    """Return (url, title, published_date, source_name) from EU funding feeds.

    RSS only carries the publisher's most recent items (typically 10–50),
    so we can't go back arbitrarily far — but the current window catches
    every fresh EU round that hit the wire in the last few days.
    """
    out: list[tuple[str, str, date, str]] = []
    seen: set[str] = set()
    for source_name, feed_url in EU_FEEDS:
        try:
            f = feedparser.parse(feed_url, request_headers=HEADERS)
        except Exception as e:
            log.warning("eu %s parse error: %r", source_name, e)
            continue
        added = 0
        for e in f.entries:
            link = (e.get("link") or "").split("?")[0].rstrip("/")
            if not link or link in seen:
                continue
            seen.add(link)
            title = (e.get("title") or "").strip()
            if not title:
                continue
            pub = e.get("published_parsed") or e.get("updated_parsed")
            if not pub:
                continue
            d = date(pub.tm_year, pub.tm_mon, pub.tm_mday)
            if d < oldest_allowed:
                continue
            out.append((link, title, d, source_name))
            added += 1
        log.info("eu %s: %d items in window", source_name, added)
    return out


# ─── glue ───────────────────────────────────────────────────────────────────


def build_synthetic(
    url: str, title: str, published_date: date, source: str, body: str = ""
) -> ScoredStory:
    """Construct the minimal ScoredStory shape _extract_one() reads."""
    story = Story(
        title=title,
        url=url,
        source=source,
        source_type="rss",
        published_at=f"{published_date.isoformat()}T12:00:00+00:00",
        raw_text=body,
        source_topics=["founders", "vc"],
    )
    # ScoredStory dataclass requires score + assignments; give it placeholders.
    return ScoredStory(
        story=story,
        score=0.0,
        reasoning="",
        is_technical=False,
        is_novel=False,
        is_mainstream_relevant=True,
        assignments=[],
        components={},
        boosts={},
        hn_points=0,
        hn_comments=0,
    )


def merge_into_existing(rounds_by_date: dict[str, list[dict]], dry_run: bool) -> int:
    """Write or merge each date's rounds into data/funding/<date>.jsonl.

    Dedupe by story_url — if the same URL is already in the file (from a
    previous cron or backfill), the existing entry wins. This script is
    additive only.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for date_str, new_rows in rounds_by_date.items():
        path = OUT_DIR / f"{date_str}.jsonl"
        existing: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                existing[r["story_url"]] = r
        added = 0
        for r in new_rows:
            if r["story_url"] in existing:
                continue
            existing[r["story_url"]] = r
            added += 1
        if added == 0:
            continue
        if dry_run:
            log.info("would add %d rows to %s (total would be %d)", added, path, len(existing))
        else:
            with path.open("w") as f:
                for r in existing.values():
                    f.write(json.dumps(r))
                    f.write("\n")
            log.info("wrote %s — added %d, total now %d", path, added, len(existing))
        written += added
    return written


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="lookback window in days")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = date.today()
    oldest = today - timedelta(days=args.days)
    log.info("backfill window: %s → %s", oldest, today)

    # 1. Walk daily archives (TC) + EU RSS feeds
    tc_articles = tc_walk_dates(oldest, today)
    log.info("collected %d articles from TC daily archives", len(tc_articles))
    eu_articles = eu_walk_rss(oldest)
    log.info("collected %d articles from EU funding feeds", len(eu_articles))

    # Normalize to (url, title, date, source) tuples
    raw_articles: list[tuple[str, str, date, str]] = [
        (u, t, d, "techcrunch") for u, t, d in tc_articles
    ] + eu_articles
    log.info("combined %d articles from all sources", len(raw_articles))

    # 2. Title pre-filter — drop anything that doesn't look like a round
    candidates = [a for a in raw_articles if TITLE_KEYWORDS.search(a[1])]
    log.info("%d candidates after title filter (of %d)", len(candidates), len(raw_articles))

    # 3. Fetch article body + LLM-classify. We need the body because
    #    headlines alone rarely state "HQ'd in $COUNTRY" — without it the
    #    LLM defaults to region=OTHER and we drop everything. Sifted body
    #    is paywalled so fetch will return empty for those; the LLM can
    #    still classify many of them from headline + RSS-style title.
    rounds: list = []
    for url, title, d, source in candidates:
        body = fetch_body(url)
        story = build_synthetic(url, title, d, source=source, body=body)
        # Drop any stale cache entry — earlier runs might have classified this
        # URL as OTHER from headline-only context. Force the LLM to re-extract
        # now that we're feeding it the body.
        cp = _cache_path(url)
        if cp.exists():
            cp.unlink()
        try:
            r = _extract_one(story)
        except Exception as e:
            log.warning("extract failed for %s: %r", url, e)
            continue
        if r is None:
            continue
        if r.region == "OTHER":
            continue
        rounds.append(r)
    log.info("classified %d EU/NA rounds", len(rounds))

    # 4. Group by *raised* date (the LLM-extracted announcement date,
    #    falling back to article publish date when not stated) and merge.
    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in rounds:
        d_str = r.raised_date or r.published_at[:10]
        by_date[d_str].append(r.to_dict())
    for d_str, rows in by_date.items():
        log.info("  raised %s: %d rounds", d_str, len(rows))

    added = merge_into_existing(by_date, dry_run=args.dry_run)
    log.info("done — added %d new rows across %d dates", added, len(by_date))


if __name__ == "__main__":
    main()
