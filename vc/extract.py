"""VC industry classifier — surfaces non-deal venture content.

The Funding tab covers startup raises. This module covers everything
*else* a VC reader cares about: fund news, partner moves, exits, market
signals, regulatory shifts, opinion essays. Designed to power a TLDR-VC
niche newsletter.

Re-uses the existing scored.jsonl input. Pre-filters by keyword to keep
LLM cost bounded, then classifies each candidate into one of six types.
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

VC_MODEL = os.environ.get("VC_MODEL", "claude-haiku-4-5-20251001")
VC_CONCURRENCY = int(os.environ.get("VC_CONCURRENCY", "8"))

CACHE_DIR = Path("data/vc_cache")

# Pre-filter regex: title contains any keyword commonly found in VC
# industry coverage. Erring permissive — LLM has final say.
TITLE_KEYWORDS = re.compile(
    r"\b("
    # Fund-side
    r"fund|funds|LP|GP|limited partner|general partner|"
    r"venture capital|VC|family office|sovereign wealth|"
    r"close[sd]?|launched|raised|raising|"
    # People moves
    r"joins?|hires?|partner|principal|managing director|board|appoints?|"
    r"departs?|leaves?|founded|founding|"
    # Exits
    r"IPO|acquisition|acquired|secondary|exit|M&A|merger|"
    # Market signals
    r"valuation|portfolio|investment|deploy(?:ed|ment)?|capital|"
    r"vintage|cohort|"
    # Famous firms
    r"a16z|Andreessen|Sequoia|Bessemer|Accel|Lightspeed|Khosla|"
    r"Founders Fund|Greylock|Kleiner|Benchmark|Index Ventures|"
    r"General Catalyst|Tiger Global|Insight|Coatue|"
    # Regulatory + market structure
    r"SEC|disclosure|carry|management fee|secondaries|continuation fund"
    r")\b",
    re.IGNORECASE,
)


VC_TYPES = {
    "fund_news": "Fund launches, fund closes, LP commitments, fund-of-funds news",
    "partner_move": "Partner / principal / MD hires, departures, founding moves",
    "exit": "IPOs, acquisitions, secondary sales, exits",
    "market_signal": "Sector trends, performance data, market analysis, LP behavior, vintage performance",
    "opinion": "Partner essays, market commentary, strategy pieces, predictions",
    "regulatory": "SEC, fund regulation, carry/fee policy, compliance news",
}


@dataclass
class VcArticle:
    story_url: str
    title: str
    source: str
    published_at: str
    is_vc: bool
    vc_type: str  # one of VC_TYPES keys, or "" if is_vc=false
    headline_summary: str  # one-line LLM-generated summary, 8-15 words
    firms: list[str]  # named VC firms mentioned
    people: list[str]  # named people mentioned
    region: str  # "NA" | "EU" | "ASIA" | "GLOBAL" | "OTHER"

    def to_dict(self) -> dict:
        return asdict(self)


EXTRACT_SYSTEM = """You classify articles for a venture capital industry newsletter.

The reader is a VC partner, an LP, or a founder paying attention to who's
funding what. Inclusive bar: if it would interest someone in venture
capital, mark is_vc=true.

Return ONLY a JSON object. No markdown.

Schema:
{
  "is_vc": true | false,
  "vc_type": "fund_news | partner_move | exit | market_signal | opinion | regulatory" | "",
  "headline_summary": "one-line punchy summary, 8-15 words" | "",
  "firms": ["named VC firms or notable startups, e.g. Sequoia, a16z, OpenAI"],
  "people": ["named people, e.g. Marc Andreessen, Sam Altman"],
  "region": "NA | EU | ASIA | GLOBAL | OTHER"
}

vc_type classification (pick the best fit):
- fund_news: new fund launched/closed, LP commits, fund-of-funds, asset
  manager moves into venture, large pool of capital being raised by an
  investment firm (NOT a startup operating-business raise)
- partner_move: a notable person joins/leaves/founds anything — a VC firm,
  a portfolio company at exec/board level, AI lab leadership. Anything
  that signals capital allocation power moving around.
- exit: IPO (filed, priced, talks), acquisition where one party is a
  VC-backed startup or hot private company, secondary sale, going-public
  via SPAC
- market_signal: sector trend data, performance numbers, deal volume,
  valuation reports, IPO market commentary, secondary market analysis
- opinion: partner essay, market commentary, predictions, strategy piece,
  even a controversial founder/VC op-ed
- regulatory: SEC, CFTC, antitrust, fund regulation, accredited-investor
  rules, carry/fee policy, anything that changes the venture rules

Mark is_vc=TRUE for these patterns (examples):
- "Andre Cronje quits Sonic Labs board" → partner_move
- "Noam Shazeer to join IPO-bound OpenAI" → partner_move
- "Kalshi holds early IPO talks" → exit
- "SpaceX to acquire Cursor for $60B" → exit
- "Fidelity launches money market fund" → fund_news (asset manager)
- "CFTC and SEC request comment on 'swaps' definition" → regulatory
- "Y Combinator backs new climate startup studio" → fund_news
- "Why valuations are 30% off vs 2024" → market_signal

Mark is_vc=FALSE only for clearly unrelated content:
- Plain product launches (iPhone, new AI model release) with no
  capital/personnel/exit angle
- Security/CVE bulletins
- Pure research papers (arxiv)
- Engineering deep dives

If headline_summary would exceed 15 words, trim it harder.
"""

EXTRACT_USER_TEMPLATE = """Title: {title}
Source: {source}
Published: {published_at}
{snippet_block}

Return the JSON object."""


def _parse_json(text: str) -> dict | None:
    t = text.strip()
    if t.startswith("```"):
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


def _extract_one(story: ScoredStory) -> VcArticle | None:
    url = story.story.url
    cached = _load_cached(url)
    if cached is not None:
        if not cached.get("is_vc"):
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
        raw = complete(EXTRACT_SYSTEM, user, model=VC_MODEL, max_tokens=400)
    except Exception as e:
        log.warning("vc extract LLM error for %s: %r", url, e)
        return None

    payload = _parse_json(raw)
    if payload is None:
        log.warning("vc extract: could not parse JSON for %s", url)
        return None

    _save_cached(url, payload)

    if not payload.get("is_vc"):
        return None
    return _build_from_payload(story, payload)


def _build_from_payload(story: ScoredStory, payload: dict) -> VcArticle:
    vc_type = (payload.get("vc_type") or "").strip()
    if vc_type not in VC_TYPES:
        vc_type = "market_signal"  # safe default
    region = (payload.get("region") or "OTHER").upper().strip()
    if region not in {"NA", "EU", "ASIA", "GLOBAL", "OTHER"}:
        region = "OTHER"
    return VcArticle(
        story_url=story.story.url,
        title=story.story.title,
        source=story.story.source,
        published_at=story.story.published_at,
        is_vc=True,
        vc_type=vc_type,
        headline_summary=(payload.get("headline_summary") or "").strip(),
        firms=[s for s in (payload.get("firms") or []) if isinstance(s, str)],
        people=[s for s in (payload.get("people") or []) if isinstance(s, str)],
        region=region,
    )


def extract_vc(scored: list[ScoredStory]) -> list[VcArticle]:
    """Pre-filter scored stories by VC keywords, LLM-classify the survivors."""
    candidates = [s for s in scored if TITLE_KEYWORDS.search(s.story.title or "")]
    log.info(
        "vc: %d candidates (of %d scored) after title filter",
        len(candidates),
        len(scored),
    )

    out: list[VcArticle] = []
    with ThreadPoolExecutor(max_workers=VC_CONCURRENCY) as pool:
        futures = {pool.submit(_extract_one, s): s for s in candidates}
        for fut in as_completed(futures):
            try:
                r = fut.result()
            except Exception as e:
                log.warning("vc worker error: %r", e)
                continue
            if r is None:
                continue
            out.append(r)

    out.sort(key=lambda r: (r.vc_type, r.published_at), reverse=True)
    log.info("vc: kept %d articles", len(out))
    return out
