from __future__ import annotations

import hashlib
import json
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
CACHE_DIR = Path("data/blurbs/.cache")

SYSTEM_TEMPLATE = """You write blurbs for {brand_name}, a daily TLDR newsletter. You match the voice canon exactly.

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

CORE_VOICE_PATH = Path(".claude/skills/tldr_voice_core.md")


@dataclass
class GeneratedBlurb:
    story_url: str
    title: str
    newsletter: str
    section_id: str
    blurb: str
    word_count: int
    minute_read: int
    needs_review: bool

    def to_dict(self) -> dict:
        return {
            "story_url": self.story_url,
            "title": self.title,
            "newsletter": self.newsletter,
            "section_id": self.section_id,
            "blurb": self.blurb,
            "word_count": self.word_count,
            "minute_read": self.minute_read,
            "needs_review": self.needs_review,
        }


def _load_voice(skill_id: str) -> str:
    parts: list[str] = []
    if CORE_VOICE_PATH.exists():
        parts.append("# CORE TLDR VOICE (applies to every newsletter)\n\n" + CORE_VOICE_PATH.read_text())
    p = Path(f".claude/skills/{skill_id}.md")
    if p.exists():
        parts.append(f"\n\n# {skill_id} ADDENDUM (specific to this newsletter)\n\n" + p.read_text())
    elif not parts:
        log.warning("No voice file for %s; falling back to generic stub", skill_id)
        return "Lead with the substance. Match the newsletter's existing voice. Two or three declarative sentences."
    return "\n\n".join(parts)


def _word_count(s: str) -> int:
    return len(re.findall(r"\b[\w']+\b", s))


def _sentence_guidance(section: Section) -> str:
    if section.is_quick_links:
        return "Output exactly ONE sentence."
    if section.max_words >= 90:
        return "Output 2-3 declarative sentences."
    return "Output exactly 2 declarative sentences."


def _estimate_minute_read(raw_text: str, fallback: int = 5) -> int:
    if not raw_text:
        return fallback
    wc = _word_count(raw_text)
    minutes = max(1, round(wc / 250))
    return min(minutes, 20)


def _cache_key(story_url: str, newsletter: str, section_id: str) -> Path:
    h = hashlib.sha1(f"{newsletter}|{section_id}|{story_url}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def generate_blurb(
    scored: ScoredStory, newsletter_id: str, use_cache: bool = True
) -> GeneratedBlurb | None:
    nl = get_newsletter(newsletter_id)
    assignment = scored.for_newsletter(newsletter_id)
    if not assignment:
        return None
    section = nl.section(assignment.section_id) or nl.quick_links_section or nl.sections[-1]

    cache_path = _cache_key(scored.story.url, newsletter_id, section.id)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if use_cache and cache_path.exists():
        d = json.loads(cache_path.read_text())
        return GeneratedBlurb(
            story_url=d["story_url"],
            title=d["title"],
            newsletter=d["newsletter"],
            section_id=d["section_id"],
            blurb=d["blurb"],
            word_count=int(d["word_count"]),
            minute_read=int(d.get("minute_read", 5)),
            needs_review=bool(d.get("needs_review", False)),
        )

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
    for _ in range(2):
        try:
            text = complete(system, user, model=BLURB_MODEL, max_tokens=400)
        except Exception as e:
            log.warning("Blurb gen failed for %s [%s]: %r", scored.story.url, newsletter_id, e)
            continue
        text = text.strip().strip('"').strip("'")
        text = re.sub(r"^(blurb|summary|here(?:'s| is) the blurb)\s*:?\s*", "", text, flags=re.I)
        wc = _word_count(text)
        attempts.append((text, wc))
        if section.min_words <= wc <= section.max_words:
            result = GeneratedBlurb(
                story_url=scored.story.url,
                title=scored.story.title,
                newsletter=newsletter_id,
                section_id=section.id,
                blurb=text,
                word_count=wc,
                minute_read=_estimate_minute_read(scored.story.raw_text),
                needs_review=False,
            )
            cache_path.write_text(json.dumps(result.to_dict()))
            return result
        user = (
            f"That was {wc} words; the constraint is {section.min_words}-{section.max_words}. "
            "Rewrite within the constraint.\n\n"
        ) + user

    if not attempts:
        return None

    target_mid = (section.min_words + section.max_words) // 2
    best = min(attempts, key=lambda a: abs(a[1] - target_mid))
    result = GeneratedBlurb(
        story_url=scored.story.url,
        title=scored.story.title,
        newsletter=newsletter_id,
        section_id=section.id,
        blurb=best[0],
        word_count=best[1],
        minute_read=_estimate_minute_read(scored.story.raw_text),
        needs_review=True,
    )
    cache_path.write_text(json.dumps(result.to_dict()))
    return result


def generate_for_newsletter(
    scored: list[ScoredStory], newsletter_id: str, use_cache: bool = True
) -> list[GeneratedBlurb]:
    """Generate blurbs for the top-N-per-section assigned to one newsletter."""
    from ranking.score import top_per_section

    by_sec = top_per_section(scored, newsletter_id)
    out: list[GeneratedBlurb] = []
    for section_id, stories in by_sec.items():
        for s in stories:
            b = generate_blurb(s, newsletter_id, use_cache=use_cache)
            if b is not None:
                out.append(b)
    return out
