"""LLM-driven funding-round extraction from scored stories.

Pipeline-stage philosophy:
- Re-use the stories the ranker already scored. No new HTTP fetching.
- Pre-filter by a cheap keyword pass so we only LLM-call promising titles.
- Cache by canonical URL — re-runs are no-ops once a story has been
  extracted, regardless of whether it ended up classified as funding.

The cache → snippet → LLM → parse → save → typed-result skeleton (and
the parallel-worker fan-out) lives in `common.llm_extractor.LLMExtractor`;
this module supplies the funding-specific prompts, schema, region
validator, and post-filter (drop OTHER region).
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from common.cache import UrlJsonCache
from common.config import FUNDING
from common.llm_extractor import LLMExtractor
from common.story import ScoredStory

log = logging.getLogger(__name__)

# Cheap and fast — extraction is tiny structured output, no need for Opus.
# Back-compat aliases for any external importer.
FUNDING_MODEL = FUNDING.model
FUNDING_CONCURRENCY = FUNDING.concurrency

_CACHE = UrlJsonCache(Path("data/funding_cache"))

# Title keywords that pre-qualify a story for LLM extraction. Cheap regex
# pass to avoid running an LLM on every Hacker News post. Erring on
# permissive — the LLM can still say "not a funding story".
TITLE_KEYWORDS = re.compile(
    r"\b("
    r"raises?|raised|raising|"
    r"funding|funded|"
    r"seed|series\s+[a-eA-E]\b|pre-seed|"
    r"valuation|valued at|"
    r"announces?\s+(?:a\s+)?\$\d|"
    r"investment|invested|"
    r"closes?\s+\$\d|"
    r"M\b|B\b"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class FundingRound:
    story_url: str
    title: str
    source: str
    published_at: str  # when the *article* was published (RSS/scrape time)
    raised_date: str   # when the *round* was announced/closed (YYYY-MM-DD)
    company: str
    amount_usd: float | None
    amount_raw: str
    round_label: str
    country: str
    region: str  # "EU" | "NA" | "OTHER"
    investors: list[str]
    valuation_usd: float | None

    def to_dict(self) -> dict:
        return asdict(self)


# --- region resolution -------------------------------------------------------

_EU_COUNTRIES = {
    # Broad "Europe in venture parlance" — includes UK, Switzerland, Norway,
    # Iceland, the rest of EFTA. Matches how Sifted / Dealroom treat the region.
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia", "czech republic",
    "denmark", "estonia", "finland", "france", "germany", "greece", "hungary",
    "iceland", "ireland", "italy", "latvia", "liechtenstein", "lithuania",
    "luxembourg", "malta", "monaco", "netherlands", "norway", "poland", "portugal",
    "romania", "slovakia", "slovenia", "spain", "sweden", "switzerland",
    "united kingdom", "uk", "england", "scotland", "wales", "northern ireland",
}
_NA_COUNTRIES = {
    "united states", "usa", "us", "u.s.", "u.s.a.", "america",
    "canada",
}


def _resolve_region(country: str, hint: str | None) -> str:
    """Map a free-form country/HQ string to EU / NA / OTHER."""
    if hint and hint.upper() in {"EU", "NA", "OTHER"}:
        return hint.upper()
    if not country:
        return "OTHER"
    c = country.strip().lower().rstrip(".").strip()
    if c in _EU_COUNTRIES:
        return "EU"
    if c in _NA_COUNTRIES:
        return "NA"
    # Substring catches "based in the United Kingdom", "headquartered in Germany"
    for token in _EU_COUNTRIES:
        if token in c:
            return "EU"
    for token in _NA_COUNTRIES:
        if token in c:
            return "NA"
    return "OTHER"


# --- LLM prompt --------------------------------------------------------------

EXTRACT_SYSTEM = """You extract startup funding rounds from news headlines.

Given a title and optional snippet, decide whether it is announcing a
startup raising a round of funding (Seed, Series A/B/C/D/E+, growth,
pre-IPO, strategic). If it is, extract structured fields.

Return ONLY a JSON object. No markdown, no commentary. Schema:

{
  "is_funding": true | false,
  "company": "string (the startup that raised) | empty if is_funding=false",
  "amount_raw": "exact string from headline like '$5B' or '€60M' | empty",
  "amount_usd": number (USD-equivalent value as a plain number, NOT a string) | null,
  "round_label": "Seed | Pre-Seed | Series A | Series B | ... | Growth | Strategic | empty",
  "country": "country where the startup is headquartered, full name | empty if unknown",
  "region": "EU | NA | OTHER",
  "investors": ["list of named investors, empty list if none stated"],
  "valuation_usd": number (USD-equivalent valuation) | null,
  "raised_date": "YYYY-MM-DD when the round was announced or closed | empty if not stated"
}

raised_date rules:
- Look in the article body for phrases like "announced today", "today, X
  closed", "earlier this week", "X said Monday", "on June 12", or explicit
  ISO dates. Extract that as the raise date.
- "today" / "this morning" / "Monday" → resolve relative to the
  Published timestamp passed in the user message. E.g. if Published is
  2026-06-14 and the article says "announced today", raised_date is
  2026-06-14.
- If you can't find any explicit signal, leave it empty (we will fall
  back to the article publish date).

Region rules:
- EU: any European country (incl. UK, Switzerland, Norway).
- NA: United States or Canada.
- OTHER: anywhere else (Asia, MENA, LATAM, Africa, Oceania).

Hard rules:
- M&A, public company news, government funding to research labs, university
  grants, or grants to non-profits are NOT funding rounds. is_funding=false.
- Crypto token sales, ICOs, treasury raises are NOT VC funding rounds.
  is_funding=false.
- If amount_raw uses €, convert to USD at ~$1.08/€. If £, ~$1.27/£.
- If you don't know the country with high confidence, leave it empty and
  set region=OTHER (we will skip OTHER rows).
"""

EXTRACT_USER_TEMPLATE = """Title: {title}
Source: {source}
Published: {published_at}
{snippet_block}

Return the JSON object."""


# --- extraction --------------------------------------------------------------


# Back-compat shim — scripts/backfill_funding_archive.py imports _cache_path
# to bust stale entries before re-classifying. Keep the symbol working so
# the script doesn't need its own refactor in this commit.
def _cache_path(url: str) -> Path:
    return _CACHE.path_for(url)


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _build_from_payload(story: ScoredStory, payload: dict) -> FundingRound:
    country = (payload.get("country") or "").strip()
    region = _resolve_region(country, payload.get("region"))
    # raised_date: trust the LLM if it returned a well-formed YYYY-MM-DD,
    # otherwise fall back to the article's publish date (close enough for
    # fresh news; only drifts on retrospective coverage).
    raw_raised = (payload.get("raised_date") or "").strip()
    raised_date = raw_raised if _DATE_RE.match(raw_raised) else story.story.published_at[:10]
    return FundingRound(
        story_url=story.story.url,
        title=story.story.title,
        source=story.story.source,
        published_at=story.story.published_at,
        raised_date=raised_date,
        company=(payload.get("company") or "").strip(),
        amount_usd=_to_float(payload.get("amount_usd")),
        amount_raw=(payload.get("amount_raw") or "").strip(),
        round_label=(payload.get("round_label") or "").strip(),
        country=country,
        region=region,
        investors=[i for i in (payload.get("investors") or []) if isinstance(i, str)],
        valuation_usd=_to_float(payload.get("valuation_usd")),
    )


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class _FundingExtractor(LLMExtractor[FundingRound]):
    cache = _CACHE
    model = FUNDING_MODEL
    concurrency = FUNDING_CONCURRENCY
    title_filter_re = TITLE_KEYWORDS
    system_prompt = EXTRACT_SYSTEM
    log_label = "funding"

    def build_user_prompt(self, story: ScoredStory) -> str:
        snippet = (story.story.raw_text or "")[:600]
        snippet_block = f"Snippet: {snippet}" if snippet else ""
        return EXTRACT_USER_TEMPLATE.format(
            title=story.story.title,
            source=story.story.source,
            published_at=story.story.published_at,
            snippet_block=snippet_block,
        )

    def parse_payload(self, story: ScoredStory, payload: dict) -> FundingRound | None:
        if not payload.get("is_funding"):
            return None
        return _build_from_payload(story, payload)

    def post_filter(self, result: FundingRound) -> bool:
        # Drop funding rounds outside EU/NA (the user only cares about those two).
        return result.region != "OTHER"

    def sort_results(self, results: list[FundingRound]) -> list[FundingRound]:
        # Sort by region, then amount (desc), then company name.
        return sorted(
            results,
            key=lambda r: (
                r.region,
                -(r.amount_usd or 0),
                (r.company or "").lower(),
            ),
        )


# Back-compat: `scripts/backfill_funding_archive.py` imports `_extract_one`
# as a free function. Keep the symbol pointing at an instance method bound
# to a module-level extractor.
_EXTRACTOR = _FundingExtractor()


def _extract_one(story: ScoredStory) -> FundingRound | None:
    """Return a FundingRound for a story that's a funding announcement, else None.

    Results — including negatives — are cached so re-runs of the day are cheap.
    """
    return _EXTRACTOR.extract_one(story)


def extract_funding(scored: list[ScoredStory]) -> list[FundingRound]:
    """Pre-filter to plausible titles, then LLM-extract in parallel.

    Drops:
    - Titles that have no funding-shaped keyword.
    - Stories the LLM says are not funding rounds.
    - Funding rounds outside EU/NA (the user only cares about those two).
    """
    return _EXTRACTOR.extract(scored)
