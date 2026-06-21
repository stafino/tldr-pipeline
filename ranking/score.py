from __future__ import annotations

import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from common.config import RANKING
from common.llm import complete
from common.newsletters import Newsletter, load_newsletters
from common.story import Assignment, ScoredStory, Story

log = logging.getLogger(__name__)

RUBRIC_PATH = Path(".claude/skills/curation_rubric.md")
RUBRIC_OVERRIDES_DIR = Path(".claude/skills/rubric_overrides")
CACHE_DIR = Path("data/scored/.cache")

# Back-compat aliases for any external importer.
RANKING_MODEL = RANKING.model

# Minimum per-newsletter score to keep an assignment. Stories with no
# assignment above this threshold are dropped.
MIN_ASSIGNMENT_SCORE = int(os.environ.get("MIN_ASSIGNMENT_SCORE", "55"))

# Parallel LLM calls. The CLI backend is subprocess-bound and slow per call;
# parallelism cuts wall time roughly linearly until rate limits or CPU saturate.
RANKING_CONCURRENCY = RANKING.concurrency

SYSTEM_TEMPLATE = """You are an editorial scorer for the TLDR family of daily newsletters. For each candidate story you decide (a) which TLDR newsletters it belongs in, (b) which section of each newsletter, (c) how strong a fit it is (0-100 per assignment), and (d) overall metadata. Always return JSON matching the exact schema requested. No prose outside JSON.

GLOBAL RUBRIC (apply to every newsletter):

{rubric}

LEARNED SOURCE PREFERENCES (per newsletter):

The pipeline tracks which source domains TLDR has historically picked
from. Use these as a soft prior when scoring — stories from a favored
source for a given newsletter deserve a modest score boost (+3 to +8).
Stories from unknown / low-preference domains aren't penalized; this is
purely a positive signal.

{source_preferences}

FRESHNESS PRIOR:

TLDR is a daily newsletter — fresh news wins. Apply this freshness
adjustment to the score:
  - < 12 hours old: +5 (breaking)
  - 12-24 hours old: +3 (very fresh)
  - 24-48 hours old: 0 (neutral — typical)
  - 48-72 hours old: -3 (stale for daily)
  - > 72 hours old: -8 (likely already covered)
The hours_old field is provided per story.

ALREADY-COVERED FLAG:

If a story has already_covered_by listing newsletter IDs, TLDR already
published this exact URL in the last 14 days. Don't recommend it again
unless it's a major update — apply a -25 score adjustment to the
already-covered newsletter(s) so it falls out of the top pool.

ENGAGEMENT SIGNAL:

The engagement_signal field shows the story's Hacker News traction:
points, comment count, age. This is a noisy but real reader-attention
signal. Apply this adjustment:
  - HN >= 200 points: +5 (strong reader signal)
  - HN >= 100 points: +3
  - HN >= 50 points: +1
  - HN < 50 or no signal: 0
Don't penalize — many high-quality stories never trend on HN.

TLDR FAMILY (assign the story to all newsletters where its score would be {min_score} or above; you can also return [] if it fits none):

{family}

IMPORTANT:
- Always pick a section_id from the listed sections for that newsletter — never invent one.
- A story can land in 0, 1, 2, or 3 newsletters. Be selective; don't force-fit.
- Quick Links is the catch-all when a story is interesting but not strong enough for a primary section.
- If a story is pure hype, content marketing, off-topic, or duplicate-y, return assignments: []."""

USER_TEMPLATE = """Score this candidate story:

Title: {title}
Source: {source} ({source_type})
Source topics: {source_topics}
URL: {url}
Published: {published_at} (hours_old: {hours_old})
already_covered_by: {already_covered_by}
engagement_signal: {engagement_signal}
Snippet: {snippet}

Return a JSON object with exactly these keys:
{{
  "reasoning": "<one sentence, under 200 chars>",
  "is_technical": <bool>,
  "is_novel": <bool>,
  "is_mainstream_relevant": <bool>,
  "components": {{
    "technical": <integer 0-100>,
    "novelty": <integer 0-100>,
    "implications": <integer 0-100>,
    "credibility": <integer 0-100>,
    "mainstream": <integer 0-100>
  }},
  "boosts": {{
    "freshness": <int>,
    "source_weight": <int>,
    "engagement": <int>,
    "already_covered": <int>
  }},
  "assignments": [
    {{"newsletter": "<one of: {newsletter_ids}>", "section_id": "<a section_id for that newsletter>", "score": <integer 0-100>}}
    // up to 3 assignments; empty list if the story fits nothing
  ]
}}"""


def _load_rubric() -> str:
    if not RUBRIC_PATH.exists():
        log.warning("Rubric file missing at %s; using inline fallback", RUBRIC_PATH)
        return "Score 0-100 by technical substance, novelty, broader implications, and source credibility."
    return RUBRIC_PATH.read_text()


def _load_rubric_overrides() -> str:
    """Concatenate every per-newsletter rubric override file into a single
    block the ranker can read. These tune scoring nuance per newsletter
    (e.g., TLDR AI weights frontier-lab releases higher; TLDR Marketing
    weights named-channel-benchmark stories higher)."""
    if not RUBRIC_OVERRIDES_DIR.exists():
        return ""
    blocks: list[str] = ["## PER-NEWSLETTER SCORING OVERRIDES\n"]
    for f in sorted(RUBRIC_OVERRIDES_DIR.glob("*.md")):
        blocks.append(f.read_text().strip())
        blocks.append("")
    return "\n".join(blocks)


def _format_family(nls: dict[str, Newsletter]) -> str:
    blocks = []
    for nid, nl in nls.items():
        section_lines = "\n".join(
            f"      - {s.id}: {s.name} — {s.description}" for s in nl.sections
        )
        topics = ", ".join(nl.topics) if nl.topics else "(general)"
        blocks.append(
            f"  • {nid} ({nl.brand_name})\n"
            f"    topics: {topics}\n"
            f"    sections:\n{section_lines}"
        )
    return "\n\n".join(blocks)


def _cache_key(story: Story, family_version: str) -> Path:
    h = hashlib.sha1(f"{family_version}|{story.url}|{story.title}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def rank_stories(stories: list[Story], use_cache: bool = True) -> list[ScoredStory]:
    if not stories:
        return []

    nls = load_newsletters()
    rubric = _load_rubric()
    rubric_overrides = _load_rubric_overrides()
    if rubric_overrides:
        rubric = rubric + "\n\n" + rubric_overrides

    # Versioning the cache key by the set of newsletter IDs ensures that adding
    # or removing a newsletter invalidates the cache automatically.
    # v3 = added explainability fields (components, boosts) + HN engagement signal
    # + freshness + already-covered + per-newsletter rubric overrides.
    family_version = "v3:" + ",".join(sorted(nls.keys()))

    valid_sections: dict[str, set[str]] = {
        nid: set(nl.section_ids) for nid, nl in nls.items()
    }

    # Inject learned source-weight preferences per newsletter (if any exist).
    # The first run has empty weights — the file is populated after the first
    # backtest cycle and compounds from there.
    from common.source_weights import format_for_prompt

    source_pref_lines: list[str] = []
    for nid in nls.keys():
        block = format_for_prompt(nid, k=10)
        if block:
            source_pref_lines.append(block)
    source_preferences = "\n\n".join(source_pref_lines) if source_pref_lines else (
        "(No learned preferences yet — they populate after the first backtest cycle.)"
    )

    # Build a "TLDR already published this URL in the last 14 days" set.
    from common.already_covered import _canonical_url, build_covered_set
    from datetime import date as _date
    covered = build_covered_set(_date.today(), lookback_days=14)

    # Fetch HN engagement signal for every story (cached for 6h).
    from common.engagement import batch_fetch as fetch_engagement
    log.info("Fetching engagement signal for %d stories (HN/Algolia)...", len(stories))
    eng_signals = fetch_engagement([s.url for s in stories], concurrency=8)
    log.info("Engagement signals: %d found, %d empty",
             sum(1 for s in eng_signals.values() if s.found),
             sum(1 for s in eng_signals.values() if not s.found))

    system = SYSTEM_TEMPLATE.format(
        rubric=rubric, family=_format_family(nls),
        min_score=MIN_ASSIGNMENT_SCORE,
        source_preferences=source_preferences,
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _score_one(story: Story) -> dict | None:
        # Whole body is wrapped: a malformed cache file, a snippet containing
        # curly braces (which would break str.format), a hashlib edge case, or
        # any I/O failure must NEVER take down the whole pool. Return None and
        # log; the outer loop drops the story.
        try:
            cache_path = _cache_key(story, family_version)
            if use_cache and cache_path.exists():
                try:
                    return json.loads(cache_path.read_text())
                except Exception:
                    pass  # corrupt cache; refetch
            # Compute hours_old from published_at for the freshness prior
            hours_old = 999
            try:
                from datetime import datetime, timezone
                pub = datetime.fromisoformat(story.published_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                hours_old = int((now - pub).total_seconds() / 3600)
            except Exception:
                pass

            # Already-covered check
            cu = _canonical_url(story.url)
            covered_nls = covered.get(cu, [])
            already_covered_by = ", ".join(covered_nls) if covered_nls else "(none)"
            engagement_signal = eng_signals.get(story.url, type("X", (), {"summary": lambda: "no HN signal"})())
            eng_text = engagement_signal.summary() if hasattr(engagement_signal, "summary") else "no HN signal"

            user = (
                USER_TEMPLATE
                .replace("{title}", str(story.title))
                .replace("{source}", str(story.source))
                .replace("{source_type}", str(story.source_type))
                .replace("{source_topics}", ", ".join(story.source_topics) or "(none)")
                .replace("{url}", str(story.url))
                .replace("{published_at}", str(story.published_at))
                .replace("{hours_old}", str(hours_old))
                .replace("{already_covered_by}", already_covered_by)
                .replace("{engagement_signal}", eng_text)
                .replace("{snippet}", (story.raw_text or "")[:500])
                .replace("{newsletter_ids}", ", ".join(nls.keys()))
            )
            try:
                raw = complete(system, user, model=RANKING_MODEL, max_tokens=600)
                data = _parse_json_response(raw)
            except Exception as e:
                log.warning("Ranking failed for %s: %r", story.url, e)
                return None
            try:
                cache_path.write_text(json.dumps(data))
            except Exception as e:
                log.warning("Cache write failed for %s: %r", story.url, e)
            return data
        except Exception as e:
            log.warning("Unhandled in _score_one for %s: %r", getattr(story, "url", "?"), e)
            return None

    raw_results: dict[str, dict] = {}
    completed = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=RANKING_CONCURRENCY) as pool:
        futures = {pool.submit(_score_one, s): s for s in stories}
        for fut in as_completed(futures):
            story = futures[fut]
            try:
                data = fut.result()
            except Exception as e:
                # Belt-and-braces: _score_one already wraps everything, but if
                # something gets through (e.g. cancellation), don't crash the loop.
                log.warning("Future raised for %s: %r", getattr(story, "url", "?"), e)
                data = None
            completed += 1
            if data is None:
                failed += 1
            if completed % 10 == 0 or completed == len(stories):
                log.info("ranking progress: %d/%d (%d failed)", completed, len(stories), failed)
            if data is not None:
                raw_results[story.url] = data

    scored: list[ScoredStory] = []
    for story in stories:
        data = raw_results.get(story.url)
        if data is None:
            continue
        raw_assignments = data.get("assignments", []) or []
        clean: list[Assignment] = []
        for a in raw_assignments:
            nid = a.get("newsletter")
            sec = a.get("section_id")
            try:
                sc = float(a.get("score", 0))
            except (TypeError, ValueError):
                continue
            if nid not in valid_sections:
                continue
            if sec not in valid_sections[nid]:
                quick = next(
                    (s.id for s in nls[nid].sections if s.id.endswith("quick_links") or s.id == "quick"),
                    None,
                )
                if quick is None:
                    continue
                sec = quick
            if sc < MIN_ASSIGNMENT_SCORE:
                continue
            clean.append(Assignment(newsletter=nid, section_id=sec, score=sc))

        if not clean:
            continue

        max_score = max(a.score for a in clean)
        # Pull the explainability fields from the model's response
        comp = data.get("components", {}) or {}
        boosts = data.get("boosts", {}) or {}
        eng = eng_signals.get(story.url)
        hn_pts = eng.hn_points if eng else 0
        hn_cmts = eng.hn_comments if eng else 0
        scored.append(
            ScoredStory(
                story=story,
                score=max_score,
                reasoning=str(data.get("reasoning", "")),
                is_technical=bool(data.get("is_technical", False)),
                is_novel=bool(data.get("is_novel", False)),
                is_mainstream_relevant=bool(data.get("is_mainstream_relevant", False)),
                assignments=clean,
                components={k: int(v) for k, v in comp.items() if isinstance(v, (int, float))},
                boosts={k: int(v) for k, v in boosts.items() if isinstance(v, (int, float))},
                hn_points=hn_pts,
                hn_comments=hn_cmts,
            )
        )

    scored.sort(key=lambda s: s.score, reverse=True)
    log.info("Ranking kept %d/%d stories (>= %d on at least one newsletter)", len(scored), len(stories), MIN_ASSIGNMENT_SCORE)
    return scored


def by_newsletter(scored: list[ScoredStory]) -> dict[str, list[ScoredStory]]:
    """Group scored stories by newsletter (a story can appear under multiple)."""
    out: dict[str, list[ScoredStory]] = {}
    for s in scored:
        for a in s.assignments:
            out.setdefault(a.newsletter, []).append(s)
    # Sort each newsletter by its own score for that story.
    for nid, lst in out.items():
        lst.sort(key=lambda s: s.for_newsletter(nid).score, reverse=True)
    return out


def top_per_section(scored: list[ScoredStory], newsletter_id: str) -> dict[str, list[ScoredStory]]:
    """Group + cap stories per section for a single newsletter."""
    nls = load_newsletters()
    nl = nls[newsletter_id]
    groups: dict[str, list[ScoredStory]] = {s.id: [] for s in nl.sections}
    for s in scored:
        a = s.for_newsletter(newsletter_id)
        if not a:
            continue
        if a.section_id in groups:
            groups[a.section_id].append(s)
    # Sort within each section by per-newsletter score.
    for sec in nl.sections:
        groups[sec.id].sort(
            key=lambda s: s.for_newsletter(newsletter_id).score, reverse=True
        )
        groups[sec.id] = groups[sec.id][: sec.target_count]
    return groups
