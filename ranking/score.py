from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from common.llm import complete
from common.newsletters import Newsletter, get_newsletter
from common.story import ScoredStory, Story

log = logging.getLogger(__name__)

RUBRIC_PATH = Path(".claude/skills/curation_rubric.md")
CACHE_DIR = Path("data/scored/.cache")

RANKING_MODEL = os.environ.get("RANKING_MODEL", "claude-sonnet-4-6")

SYSTEM_TEMPLATE = """You are an editorial scorer for {brand_name}. For each candidate story you apply the rubric below to (a) score 0-100 and (b) classify the story into one of the newsletter's sections. Always return JSON matching the exact schema requested. No prose outside JSON. If you wrap the JSON in fences, use ```json fences only.

RUBRIC:
{rubric}

SECTIONS for {brand_name} (pick one section_id per story):
{sections}"""

USER_TEMPLATE = """Score this candidate story for {brand_name}:

Title: {title}
Source: {source} ({source_type})
URL: {url}
Snippet: {snippet}

Return a JSON object with exactly these keys:
{{
  "score": <integer 0-100>,
  "section_id": "<one of: {section_ids}>",
  "reasoning": "<one sentence, under 200 chars>",
  "is_technical": <bool>,
  "is_novel": <bool>,
  "is_mainstream_relevant": <bool>
}}"""


def _load_rubric() -> str:
    if not RUBRIC_PATH.exists():
        log.warning("Rubric file missing at %s; using inline fallback", RUBRIC_PATH)
        return "Score 0-100 by technical substance, novelty, broader implications, and source credibility."
    return RUBRIC_PATH.read_text()


def _format_sections(nl: Newsletter) -> str:
    lines = []
    for s in nl.sections:
        lines.append(f"  - {s.id}: {s.name}. {s.description}")
    return "\n".join(lines)


def _cache_key(story: Story, newsletter: str) -> Path:
    h = hashlib.sha1(f"{newsletter}|{story.url}|{story.title}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    # Be lenient: find the first { and last } if there's other text.
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def rank_stories(
    stories: list[Story], newsletter: str = "tldr_founders", use_cache: bool = True
) -> list[ScoredStory]:
    if not stories:
        return []

    nl = get_newsletter(newsletter)
    rubric = _load_rubric()
    system = SYSTEM_TEMPLATE.format(
        brand_name=nl.brand_name, rubric=rubric, sections=_format_sections(nl)
    )
    valid_section_ids = set(nl.section_ids)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    scored: list[ScoredStory] = []
    for story in stories:
        cache_path = _cache_key(story, newsletter)
        if use_cache and cache_path.exists():
            data = json.loads(cache_path.read_text())
        else:
            user = USER_TEMPLATE.format(
                brand_name=nl.brand_name,
                title=story.title,
                source=story.source,
                source_type=story.source_type,
                url=story.url,
                snippet=(story.raw_text or "")[:500],
                section_ids=", ".join(nl.section_ids),
            )
            try:
                raw = complete(system, user, model=RANKING_MODEL, max_tokens=400)
                data = _parse_json_response(raw)
            except Exception as e:
                log.warning("Ranking failed for %s: %s", story.url, e)
                continue
            cache_path.write_text(json.dumps(data))

        section_id = data.get("section_id", "")
        if section_id not in valid_section_ids:
            # Bucket unknown classification into the last section ("quick" by convention).
            section_id = nl.sections[-1].id

        try:
            scored.append(
                ScoredStory(
                    story=story,
                    score=float(data.get("score", 0)),
                    reasoning=str(data.get("reasoning", "")),
                    is_technical=bool(data.get("is_technical", False)),
                    is_novel=bool(data.get("is_novel", False)),
                    is_mainstream_relevant=bool(data.get("is_mainstream_relevant", False)),
                    section_id=section_id,
                    newsletter=newsletter,
                )
            )
        except Exception as e:
            log.warning("Parse failed for %s: %s", story.url, e)

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def top_per_section(
    scored: list[ScoredStory], newsletter: str = "tldr_founders"
) -> dict[str, list[ScoredStory]]:
    """Return {section_id: [top N stories]} respecting each section's target_count."""
    nl = get_newsletter(newsletter)
    by_section: dict[str, list[ScoredStory]] = {s.id: [] for s in nl.sections}
    for s in scored:
        if s.section_id in by_section:
            by_section[s.section_id].append(s)
    for sec in nl.sections:
        by_section[sec.id] = by_section[sec.id][: sec.target_count]
    return by_section
