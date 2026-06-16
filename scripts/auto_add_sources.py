"""Auto-discover RSS feeds for missing high-citation domains from the TLDR
source audit and append them to config/sources.yaml.

For each candidate domain:
  1. Try common RSS paths: /feed, /feed/, /rss, /rss.xml, /atom.xml, /index.xml
  2. Fetch the homepage and look for <link rel="alternate" type="application/rss+xml">
  3. Validate the discovered URL returns parseable RSS (>=1 entry)
  4. Determine topic tags from which TLDR newsletter(s) cited it
  5. Append to sources.yaml with a deterministic 'name'

Won't add: x.com, linkedin.com, threadreaderapp.com (no public RSS / paid only).
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

from scripts.mine_tldr_sources import SLUG_MAP, mine, _canonical_domain  # noqa: E402

log = logging.getLogger(__name__)

USER_AGENT = "tldr-source-discovery/0.1 (+research)"
SKIP_DOMAINS = {
    "x.com", "twitter.com",
    "linkedin.com",
    "threadreaderapp.com",
    "jobs.ashbyhq.com",   # job board, not editorial
    "youtube.com",
    "github.com",          # too generic (would index every repo)
    "medium.com",          # per-author RSS, can't bulk-add
    "instagram.com",
    "facebook.com",
    "reddit.com",
    "wikipedia.org",
    "apple.com",           # too broad
    "google.com",
    "amazon.com",
}

NL_TOPIC_MAP = {
    "tldr_tech":       "tech",
    "tldr_ai":         "ai",
    "tldr_founders":   "founders",
    "tldr_dev":        "programming",
    "tldr_data":       "data",
    "tldr_design":     "design",
    "tldr_infosec":    "infosec",
    "tldr_it":         "it",
    "tldr_devops":     "devops",
    "tldr_marketing":  "marketing",
    "tldr_product":    "product",
    "tldr_crypto":     "crypto",
    "tldr_fintech":    "fintech",
}

# Probe these paths in order
CANDIDATE_PATHS = [
    "/feed/",
    "/feed",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/index.xml",
    "/feed.xml",
    "/blog/feed",
    "/blog/feed/",
    "/blog/rss",
]


def _try_url(url: str) -> bool:
    """Returns True if url returns a parseable RSS/Atom with ≥1 entry."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8, allow_redirects=True)
        if r.status_code != 200:
            return False
        text = r.text
        if "<rss" not in text.lower() and "<feed" not in text.lower():
            return False
        parsed = feedparser.parse(text)
        return bool(parsed.entries) and len(parsed.entries) >= 1
    except Exception:
        return False


def _discover_rss(domain: str) -> str | None:
    """Try to find an RSS feed URL for the given domain."""
    # 1) Try common paths
    for path in CANDIDATE_PATHS:
        url = f"https://{domain}{path}"
        if _try_url(url):
            return url

    # 2) Parse the homepage for <link rel="alternate" ...>
    try:
        r = requests.get(f"https://{domain}/", headers={"User-Agent": USER_AGENT}, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.find_all("link", rel="alternate"):
                t = link.get("type", "")
                if "rss" in t.lower() or "atom" in t.lower() or "xml" in t.lower():
                    href = link.get("href", "")
                    if href.startswith("/"):
                        href = f"https://{domain}{href}"
                    elif not href.startswith("http"):
                        continue
                    if _try_url(href):
                        return href
    except Exception:
        pass
    return None


def _safe_name(domain: str) -> str:
    """Convert example.com → example_com (deterministic feed name)."""
    n = re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_")
    return n[:32]


def _topics_for(domain: str, citations_per_nl: dict[str, int]) -> list[str]:
    """Pick topic tags based on which newsletters cite this domain."""
    topics: list[str] = []
    sorted_nls = sorted(citations_per_nl.items(), key=lambda x: -x[1])
    # Include topics for the top-3 newsletters that cite this domain
    for nl_id, _ in sorted_nls[:3]:
        topic = NL_TOPIC_MAP.get(nl_id)
        if topic and topic not in topics:
            topics.append(topic)
    return topics or ["tech"]


def discover_missing_sources(
    citations_by_nl: dict[str, list],
    current_domains: set[str],
    min_citations: int = 3,
    max_to_add: int = 60,
    concurrency: int = 8,
) -> list[dict]:
    """Identify missing high-citation domains and discover their RSS feeds."""
    # Per-domain citation totals + which newsletters cite it
    domain_total: Counter = Counter()
    per_nl: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for nl_id, cits in citations_by_nl.items():
        for c in cits:
            domain_total[c.domain] += 1
            per_nl[c.domain][nl_id] += 1

    # Candidates: missing, above min citations, not in skip list
    candidates = [
        (dom, n) for dom, n in domain_total.most_common()
        if dom not in current_domains and dom not in SKIP_DOMAINS and n >= min_citations
    ][:max_to_add]
    log.info("Candidate missing domains (≥%d citations): %d", min_citations, len(candidates))

    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_discover_rss, dom): (dom, n) for dom, n in candidates}
        for fut in as_completed(futures):
            dom, n = futures[fut]
            try:
                url = fut.result()
            except Exception as e:
                log.warning("discovery failed for %s: %r", dom, e)
                url = None
            if url:
                topics = _topics_for(dom, per_nl[dom])
                found.append({
                    "name": _safe_name(dom),
                    "url": url,
                    "topics": topics,
                    "citations": n,
                    "domain": dom,
                })
                log.info("  ✓ %-30s → %s  (cited %d×, topics %s)", dom, url[:60], n, topics)
            else:
                log.info("  ✗ %-30s no RSS found (cited %d×)", dom, n)
    return found


def append_to_sources_yaml(found: list[dict]) -> int:
    """Append discovered feeds to config/sources.yaml. Returns count added."""
    if not found:
        return 0
    path = Path("config/sources.yaml")
    text = path.read_text()
    # Insert before the 'arxiv:' line at the bottom of the rss section
    insertion = ["", "  # ─── Auto-discovered from TLDR archive (60-day audit) ─────────────"]
    for entry in sorted(found, key=lambda x: -x["citations"]):
        topics_str = "[" + ", ".join(entry["topics"]) + "]"
        # YAML inline-flow safe: quote URL because it may contain ? or =
        url_quoted = f'"{entry["url"]}"' if any(c in entry["url"] for c in "?&") else entry["url"]
        line = (
            f"  - {{ name: {entry['name']:<20}, url: {url_quoted}, "
            f"topics: {topics_str} }}  # {entry['citations']}× cited"
        )
        insertion.append(line)

    insertion_str = "\n".join(insertion) + "\n"
    # Insert just before 'arxiv:'
    if "\narxiv:" not in text:
        log.error("Could not find 'arxiv:' marker in sources.yaml")
        return 0
    new_text = text.replace("\narxiv:", "\n" + insertion_str + "\narxiv:")
    path.write_text(new_text)
    return len(found)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--min-citations", type=int, default=3)
    ap.add_argument("--max-to-add", type=int, default=60)
    args = ap.parse_args()

    # Load current source domains
    cfg = yaml.safe_load(Path("config/sources.yaml").read_text())
    current = {_canonical_domain(e["url"]) for e in cfg.get("rss", [])}
    log.info("Currently scraping %d source domains", len(current))

    # Mine
    nl_ids = list(SLUG_MAP.keys())
    citations = mine(nl_ids, days=args.days)

    # Discover RSS for missing high-cited domains
    found = discover_missing_sources(
        citations, current,
        min_citations=args.min_citations,
        max_to_add=args.max_to_add,
    )

    # Append to sources.yaml
    n_added = append_to_sources_yaml(found)
    log.info("Appended %d new sources to config/sources.yaml", n_added)


if __name__ == "__main__":
    main()
