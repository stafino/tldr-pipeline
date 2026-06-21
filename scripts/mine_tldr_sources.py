"""Scrape the last N days of every TLDR newsletter, extract every cited
source URL, and aggregate by domain → per-newsletter source-frequency
tables. Output: docs/tldr_source_audit.md with the top sources per newsletter
and our coverage gap.

Usage:
  uv run python scripts/mine_tldr_sources.py --days 30
  uv run python scripts/mine_tldr_sources.py --days 30 --newsletter tldr_marketing
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import requests
import yaml
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

SLUG_MAP = {
    "tldr_tech": "tech",
    "tldr_ai": "ai",
    "tldr_founders": "founders",
    "tldr_dev": "dev",
    "tldr_data": "data",
    "tldr_design": "design",
    "tldr_infosec": "infosec",
    "tldr_it": "it",
    "tldr_devops": "devops",
    "tldr_marketing": "marketing",
    "tldr_product": "product",
    "tldr_crypto": "crypto",
    "tldr_fintech": "fintech",
}

USER_AGENT = "tldr-source-audit/0.1 (research)"
ARCHIVE = "https://tldr.tech/{slug}/{d}"
MINUTE_READ_RE = re.compile(r"\(\d+\s*minute\s*read\)\s*$", re.I)
SPONSOR_RE = re.compile(r"\(sponsor\)\s*$", re.I)
OUTPUT_PATH = Path("docs/tldr_source_audit.md")


@dataclass
class StoryCitation:
    newsletter: str
    date: str
    title: str
    url: str
    domain: str


def _canonical_domain(url: str) -> str:
    """openai.com/index/x → openai.com  ;  www.thedefiant.io → thedefiant.io"""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _fetch_one(slug: str, date_str: str) -> list[StoryCitation] | None:
    """Returns list of citations for one (slug, date), or None if 404/landing-page."""
    url = ARCHIVE.format(slug=slug, d=date_str)
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
        return None

    soup = BeautifulSoup(r.text, "lxml")
    out: list[StoryCitation] = []

    # TLDR's archive renders each story as a heading WITH a link to the source.
    # Strategy: find each heading whose text ends with "(N minute read)" or "(Sponsor)";
    # take the next anchor link in the DOM as the source URL.
    for h in soup.find_all(["h3", "h2"]):
        text = h.get_text(" ", strip=True)
        if not text or SPONSOR_RE.search(text):
            continue
        if not MINUTE_READ_RE.search(text):
            continue
        cleaned_title = MINUTE_READ_RE.sub("", text).strip()
        if len(cleaned_title) < 6:
            continue

        # Find the link associated with this heading. Two patterns occur on
        # tldr.tech: (a) the heading itself wraps an <a>, or (b) the next <a>
        # in document order points to the source.
        link_tag = h.find("a", href=True)
        if not link_tag:
            # walk forward in document order
            sib = h.find_next("a", href=True)
            link_tag = sib if sib else None
        if not link_tag:
            continue
        href = link_tag.get("href", "")
        if not href.startswith("http"):
            continue
        # Strip TLDR's tracking params
        href_clean = href.split("?")[0]
        domain = _canonical_domain(href_clean)
        if not domain or "tldr.tech" in domain:
            continue
        out.append(StoryCitation(
            newsletter="",  # set by caller
            date=date_str,
            title=cleaned_title,
            url=href_clean,
            domain=domain,
        ))

    # If we got fewer than 2 real entries, treat as landing-page (not published yet).
    if len(out) < 2:
        return None
    return out


def _date_range(days: int) -> list[str]:
    """Last N days excluding today (today might not be published yet)."""
    today = _date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(1, days + 1)]


def _load_current_sources() -> set[str]:
    """Set of domains we already scrape from in config/sources.yaml."""
    cfg = yaml.safe_load(Path("config/sources.yaml").read_text())
    domains: set[str] = set()
    for entry in cfg.get("rss", []):
        url = entry.get("url", "")
        d = _canonical_domain(url)
        if d:
            domains.add(d)
    return domains


def mine(newsletter_ids: list[str], days: int = 30, concurrency: int = 8) -> dict[str, list[StoryCitation]]:
    """Returns {newsletter_id: [citations]} mined from the last N days."""
    dates = _date_range(days)
    log.info("Mining %d newsletters × %d days = %d page fetches", len(newsletter_ids), len(dates), len(newsletter_ids) * len(dates))

    citations_by_nl: dict[str, list[StoryCitation]] = {nid: [] for nid in newsletter_ids}
    tasks: list[tuple[str, str, str]] = []  # (nl_id, slug, date)
    for nid in newsletter_ids:
        slug = SLUG_MAP.get(nid)
        if not slug:
            continue
        for d in dates:
            tasks.append((nid, slug, d))

    completed = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_fetch_one, slug, d): (nid, d) for nid, slug, d in tasks}
        for fut in as_completed(futures):
            nid, d = futures[fut]
            try:
                result = fut.result()
            except Exception as e:
                log.warning("worker failed for %s/%s: %r", nid, d, e)
                result = None
            completed += 1
            if completed % 25 == 0:
                log.info("  progress: %d/%d pages fetched", completed, len(tasks))
            if result:
                for c in result:
                    c.newsletter = nid
                    citations_by_nl[nid].append(c)
    return citations_by_nl


def write_audit(citations_by_nl: dict[str, list[StoryCitation]], days: int, current_domains: set[str]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# TLDR Source Audit\n")
    lines.append(f"Mined the last **{days} days** of each TLDR newsletter and counted every cited domain.")
    lines.append(f"Total citations scraped: **{sum(len(c) for c in citations_by_nl.values())}**\n")
    lines.append(f"Our pipeline currently covers **{len(current_domains)}** RSS source domains.\n")

    # Global top sources across all newsletters
    global_counts: Counter[str] = Counter()
    for cits in citations_by_nl.values():
        for c in cits:
            global_counts[c.domain] += 1
    lines.append("## Top 30 cited domains across the whole TLDR family\n")
    lines.append("| Rank | Domain | Citations | Covered? |")
    lines.append("|------|--------|-----------|----------|")
    for i, (dom, n) in enumerate(global_counts.most_common(30), 1):
        covered = "✅ yes" if dom in current_domains else "❌ MISSING"
        lines.append(f"| {i} | `{dom}` | {n} | {covered} |")
    lines.append("")

    # Per-newsletter breakdown
    for nid, cits in sorted(citations_by_nl.items()):
        if not cits:
            lines.append(f"## {nid}\n\nNo citations scraped (TLDR archive likely empty for this newsletter window).\n")
            continue
        per_domain: Counter[str] = Counter(c.domain for c in cits)
        n_stories = len(cits)
        n_unique_domains = len(per_domain)
        lines.append(f"## {nid}\n")
        lines.append(f"{n_stories} citations across {n_unique_domains} unique domains.\n")
        lines.append("| Rank | Domain | Citations | Covered? |")
        lines.append("|------|--------|-----------|----------|")
        for i, (dom, n) in enumerate(per_domain.most_common(20), 1):
            covered = "✅" if dom in current_domains else "❌"
            lines.append(f"| {i} | `{dom}` | {n} | {covered} |")
        # Show 3 example titles+URLs from missing sources for sanity-check
        missing = [(dom, n) for dom, n in per_domain.most_common(20) if dom not in current_domains]
        if missing:
            lines.append("\n**Sample stories from missing sources** (to sanity-check they're worth adding):")
            shown = set()
            for c in cits:
                if c.domain in {d for d, _ in missing[:5]} and c.domain not in shown:
                    lines.append(f"- `{c.domain}` - {c.title[:80]}")
                    shown.add(c.domain)
                if len(shown) >= 5:
                    break
        lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines))
    log.info("Wrote audit to %s", OUTPUT_PATH)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--newsletter", default="all")
    args = ap.parse_args()

    nl_ids = list(SLUG_MAP.keys()) if args.newsletter == "all" else [args.newsletter]
    current_domains = _load_current_sources()
    log.info("Currently covered domains: %d", len(current_domains))

    citations = mine(nl_ids, days=args.days)
    write_audit(citations, args.days, current_domains)


if __name__ == "__main__":
    main()
