from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from common.llm import complete
from common.newsletters import Newsletter, Section, get_newsletter
from common.story import ScoredStory

log = logging.getLogger(__name__)

BLURB_MODEL = os.environ.get("BLURB_MODEL", "claude-opus-4-7")

SYSTEM_TEMPLATE = """You write blurbs for {brand_name}, a daily newsletter. You match the voice canon exactly.

VOICE CANON (treat as ground truth):

{voice}

CURRENT SECTION: {section_name}
SECTION DESCRIPTION: {section_description}

HARD RULES FOR THIS SECTION:
- Word count: {min_words}-{max_words} words. Hard limit, no exceptions.
- {sentence_guidance}
- Lead with the substance. No "this changes everything", no curiosity-gaps, no breathless adjectives.
- No emoji. No exclamation marks. No rhetorical questions.
- No em dashes as drama markers (use periods).
- Output ONLY the blurb text. No headline, no source attribution, no preamble, no markdown."""

USER_TEMPLATE = """Write a blurb in {brand_name} voice for the "{section_name}" section.

Title: {title}
Source: {source}
URL: {url}
Context: {snippet}"""


@dataclass
class GeneratedBlurb:
    story_url: str
    title: str
    section_id: str
    blurb: str
    word_count: int
    minute_read: int
    needs_review: bool


def _load_voice(skill_id: str) -> str:
    p = Path(f".claude/skills/{skill_id}.md")
    if not p.exists():
        log.warning("Voice skill %s missing at %s; falling back to short stub", skill_id, p)
        return "Lead with the substance. Match the newsletter's existing voice. Two or three declarative sentences."
    return p.read_text()


def _word_count(s: str) -> int:
    return len(re.findall(r"\b[\w']+\b", s))


def _sentence_guidance(section: Section) -> str:
    if section.id == "quick":
        return "Output exactly ONE sentence."
    if section.max_words >= 90:
        return "Output 2-3 declarative sentences."
    return "Output exactly 2 declarative sentences."


def _estimate_minute_read(raw_text: str, fallback: int = 5) -> int:
    """Rough TLDR-style minute-read estimate. 250 wpm reading speed."""
    if not raw_text:
        return fallback
    wc = _word_count(raw_text)
    minutes = max(1, round(wc / 250))
    return min(minutes, 20)


def generate_blurb(
    scored: ScoredStory, newsletter: str = "tldr_founders"
) -> GeneratedBlurb:
    nl = get_newsletter(newsletter)
    section = nl.section(scored.section_id) or nl.sections[-1]
    voice = _load_voice(nl.voice_skill)

    system = SYSTEM_TEMPLATE.format(
        brand_name=nl.brand_name,
        voice=voice,
        section_name=section.name,
        section_description=section.description,
        min_words=section.min_words,
        max_words=section.max_words,
        sentence_guidance=_sentence_guidance(section),
    )
    user = USER_TEMPLATE.format(
        brand_name=nl.brand_name,
        section_name=section.name,
        title=scored.story.title,
        source=scored.story.source,
        url=scored.story.url,
        snippet=(scored.story.raw_text or "")[:1000],
    )

    attempts: list[tuple[str, int]] = []
    for attempt in range(2):
        try:
            text = complete(system, user, model=BLURB_MODEL, max_tokens=400)
        except Exception as e:
            log.warning("Blurb generation failed for %s: %s", scored.story.url, e)
            continue
        text = text.strip().strip('"').strip("'")
        # Strip a "Blurb:" or section-name prefix if the model added one.
        text = re.sub(r"^(blurb|summary|here(?:'s| is) the blurb)\s*:?\s*", "", text, flags=re.I)
        wc = _word_count(text)
        attempts.append((text, wc))
        if section.min_words <= wc <= section.max_words:
            return GeneratedBlurb(
                story_url=scored.story.url,
                title=scored.story.title,
                section_id=section.id,
                blurb=text,
                word_count=wc,
                minute_read=_estimate_minute_read(scored.story.raw_text),
                needs_review=False,
            )
        user = (
            f"That was {wc} words; the constraint is {section.min_words}-{section.max_words}. "
            "Rewrite within the constraint.\n\n"
        ) + user

    if not attempts:
        return GeneratedBlurb(
            story_url=scored.story.url,
            title=scored.story.title,
            section_id=section.id,
            blurb="",
            word_count=0,
            minute_read=_estimate_minute_read(scored.story.raw_text),
            needs_review=True,
        )

    target_mid = (section.min_words + section.max_words) // 2
    best = min(attempts, key=lambda a: abs(a[1] - target_mid))
    return GeneratedBlurb(
        story_url=scored.story.url,
        title=scored.story.title,
        section_id=section.id,
        blurb=best[0],
        word_count=best[1],
        minute_read=_estimate_minute_read(scored.story.raw_text),
        needs_review=True,
    )


def generate_for_sections(
    by_section: dict[str, list[ScoredStory]], newsletter: str = "tldr_founders"
) -> list[GeneratedBlurb]:
    out: list[GeneratedBlurb] = []
    for _section_id, scored_list in by_section.items():
        for s in scored_list:
            out.append(generate_blurb(s, newsletter=newsletter))
    return out
