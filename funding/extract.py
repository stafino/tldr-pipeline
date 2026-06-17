"""LLM-driven funding-round extraction from scored stories.

Pipeline-stage philosophy:
- Re-use the stories the ranker already scored. No new HTTP fetching.
- Pre-filter by a cheap keyword pass so we only LLM-call promising titles.
- Cache by canonical URL — re-runs are no-ops once a story has been
  extracted, regardless of whether it ended up classified as funding.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from common.llm import complete
from common.story import ScoredStory

log = logging.getLogger(__name__)

# Cheap and fast — extraction is tiny structured output, no need for Opus.
FUNDING_MODEL = os.environ.get("FUNDING_MODEL", "claude-haiku-4-5-20251001")
FUNDING_CONCURRENCY = int(os.environ.get("FUNDING_CONCURRENCY", "8"))

CACHE_DIR = Path("data/funding_cache")

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
    published_at: str
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
  "valuation_usd": number (USD-equivalent valuation) | null
}

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


def _parse_json(text: str) -> dict | None:
    t = text.strip()
    if t.startswith("```"):
        # strip ```json … ``` fences
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


# --- cache -------------------------------------------------------------------


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _load_cached(url: str) -> dict | None:
    p = _cache_path(url)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _save_cached(url: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(url).write_text(json.dumps(payload))


# --- extraction --------------------------------------------------------------


def _extract_one(story: ScoredStory) -> FundingRound | None:
    """Return a FundingRound for a story that's a funding announcement, else None.

    Results — including negatives — are cached so re-runs of the day are cheap.
    """
    url = story.story.url
    cached = _load_cached(url)
    if cached is not None:
        if not cached.get("is_funding"):
            return None
        return _build_from_payload(story, cached)

    snippet = (story.story.raw_text or "")[:600]
    snippet_block = f"Snippet: {snippet}" if snippet else ""
    user = EXTRACT_USER_TEMPLATE.format(
        title=story.story.title,
        source=story.story.source,
        published_at=story.story.published_at,
        snippet_block=snippet_block,
    )
    try:
        raw = complete(EXTRACT_SYSTEM, user, model=FUNDING_MODEL, max_tokens=400)
    except Exception as e:
        log.warning("funding extract LLM error for %s: %r", url, e)
        return None

    payload = _parse_json(raw)
    if payload is None:
        log.warning("funding extract: could not parse JSON for %s", url)
        return None

    _save_cached(url, payload)

    if not payload.get("is_funding"):
        return None
    return _build_from_payload(story, payload)


def _build_from_payload(story: ScoredStory, payload: dict) -> FundingRound:
    country = (payload.get("country") or "").strip()
    region = _resolve_region(country, payload.get("region"))
    return FundingRound(
        story_url=story.story.url,
        title=story.story.title,
        source=story.story.source,
        published_at=story.story.published_at,
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


def extract_funding(scored: list[ScoredStory]) -> list[FundingRound]:
    """Pre-filter to plausible titles, then LLM-extract in parallel.

    Drops:
    - Titles that have no funding-shaped keyword.
    - Stories the LLM says are not funding rounds.
    - Funding rounds outside EU/NA (the user only cares about those two).
    """
    candidates = [s for s in scored if TITLE_KEYWORDS.search(s.story.title or "")]
    log.info(
        "funding: %d candidates (of %d scored) after title filter",
        len(candidates),
        len(scored),
    )

    out: list[FundingRound] = []
    with ThreadPoolExecutor(max_workers=FUNDING_CONCURRENCY) as pool:
        futures = {pool.submit(_extract_one, s): s for s in candidates}
        for fut in as_completed(futures):
            try:
                r = fut.result()
            except Exception as e:
                log.warning("funding worker error: %r", e)
                continue
            if r is None:
                continue
            if r.region == "OTHER":
                continue
            out.append(r)

    # Sort by region, then amount (desc), then company name.
    out.sort(
        key=lambda r: (
            r.region,
            -(r.amount_usd or 0),
            (r.company or "").lower(),
        ),
    )
    log.info("funding: kept %d EU/NA rounds", len(out))
    return out
