from __future__ import annotations

import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from common.llm import complete
from common.newsletters import Newsletter, load_newsletters
from common.story import Assignment, ScoredStory, Story

log = logging.getLogger(__name__)

RUBRIC_PATH = Path(".claude/skills/curation_rubric.md")
CACHE_DIR = Path("data/scored/.cache")

RANKING_MODEL = os.environ.get("RANKING_MODEL", "claude-sonnet-4-6")

# Minimum per-newsletter score to keep an assignment. Stories with no
# assignment above this threshold are dropped.
MIN_ASSIGNMENT_SCORE = int(os.environ.get("MIN_ASSIGNMENT_SCORE", "55"))

# Parallel LLM calls. The CLI backend is subprocess-bound and slow per call;
# parallelism cuts wall time roughly linearly until rate limits or CPU saturate.
RANKING_CONCURRENCY = int(os.environ.get("RANKING_CONCURRENCY", "6"))

SYSTEM_TEMPLATE = """You are an editorial scorer for the TLDR family of daily newsletters. For each candidate story you decide (a) which TLDR newsletters it belongs in, (b) which section of each newsletter, (c) how strong a fit it is (0-100 per assignment), and (d) overall metadata. Always return JSON matching the exact schema requested. No prose outside JSON.

GLOBAL RUBRIC (apply to every newsletter):

{rubric}

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
Snippet: {snippet}

Return a JSON object with exactly these keys:
{{
  "reasoning": "<one sentence, under 200 chars>",
  "is_technical": <bool>,
  "is_novel": <bool>,
  "is_mainstream_relevant": <bool>,
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

    # Versioning the cache key by the set of newsletter IDs ensures that adding
    # or removing a newsletter invalidates the cache automatically.
    family_version = "v2:" + ",".join(sorted(nls.keys()))

    valid_sections: dict[str, set[str]] = {
        nid: set(nl.section_ids) for nid, nl in nls.items()
    }

    system = SYSTEM_TEMPLATE.format(
        rubric=rubric, family=_format_family(nls), min_score=MIN_ASSIGNMENT_SCORE
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
            user = (
                USER_TEMPLATE
                .replace("{title}", str(story.title))
                .replace("{source}", str(story.source))
                .replace("{source_type}", str(story.source_type))
                .replace("{source_topics}", ", ".join(story.source_topics) or "(none)")
                .replace("{url}", str(story.url))
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
        scored.append(
            ScoredStory(
                story=story,
                score=max_score,
                reasoning=str(data.get("reasoning", "")),
                is_technical=bool(data.get("is_technical", False)),
                is_novel=bool(data.get("is_novel", False)),
                is_mainstream_relevant=bool(data.get("is_mainstream_relevant", False)),
                assignments=clean,
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
