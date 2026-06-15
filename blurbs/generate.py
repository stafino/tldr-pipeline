from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from common.story import ScoredStory

log = logging.getLogger(__name__)

VOICE_PATH = Path(".claude/skills/tldr_voice.md")
BLURB_MODEL = os.environ.get("BLURB_MODEL", "claude-opus-4-7")

MIN_WORDS = 40
MAX_WORDS = 65

SYSTEM_TEMPLATE = """You write blurbs for {newsletter}, an AI/tech newsletter for engineers and researchers.

VOICE CANON (treat as ground truth, match exactly):

{voice}

HARD RULES:
- Output exactly 2 sentences, {min_words}-{max_words} words total.
- Lead with the substance, not the framing. No "this changes everything", no curiosity-gaps, no breathless adjectives.
- No em dashes. No emoji. No exclamation marks.
- Plain past or present tense, declarative.
- If the story is a paper or technical post, describe what was actually done; if it's a launch, describe the capability and who shipped it.
- Output ONLY the blurb text. No headlines, no source attribution, no preamble."""

USER_TEMPLATE = """Write a 2-sentence blurb in {newsletter} voice for this story.

Title: {title}
Source: {source}
URL: {url}
Context: {snippet}"""


@dataclass
class GeneratedBlurb:
    story_url: str
    title: str
    blurb: str
    word_count: int
    needs_review: bool


def _load_voice() -> str:
    if not VOICE_PATH.exists():
        log.warning("Voice file missing at %s; using inline fallback", VOICE_PATH)
        return "Lead with the substance. Two declarative sentences. 40-65 words."
    return VOICE_PATH.read_text()


def _word_count(s: str) -> int:
    return len(re.findall(r"\b[\w']+\b", s))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _call_model(client: Anthropic, system: str, user: str, max_tokens: int = 250) -> str:
    resp = client.messages.create(
        model=BLURB_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def generate_blurb(scored: ScoredStory, newsletter: str = "tldr_ai") -> GeneratedBlurb:
    voice = _load_voice()
    system = SYSTEM_TEMPLATE.format(
        newsletter=newsletter, voice=voice, min_words=MIN_WORDS, max_words=MAX_WORDS
    )
    user = USER_TEMPLATE.format(
        newsletter=newsletter,
        title=scored.story.title,
        source=scored.story.source,
        url=scored.story.url,
        snippet=(scored.story.raw_text or "")[:800],
    )

    client = Anthropic()
    attempts: list[tuple[str, int]] = []

    for attempt in range(2):
        try:
            text = _call_model(client, system, user)
        except Exception as e:
            log.warning("Blurb generation failed for %s: %s", scored.story.url, e)
            continue
        text = text.strip().strip('"').strip("'")
        wc = _word_count(text)
        attempts.append((text, wc))
        if MIN_WORDS <= wc <= MAX_WORDS:
            return GeneratedBlurb(
                story_url=scored.story.url,
                title=scored.story.title,
                blurb=text,
                word_count=wc,
                needs_review=False,
            )
        user = (
            f"That was {wc} words; the constraint is {MIN_WORDS}-{MAX_WORDS}. Try again.\n\n" + user
        )

    if not attempts:
        return GeneratedBlurb(
            story_url=scored.story.url,
            title=scored.story.title,
            blurb="",
            word_count=0,
            needs_review=True,
        )

    best = min(attempts, key=lambda a: abs(a[1] - (MIN_WORDS + MAX_WORDS) // 2))
    return GeneratedBlurb(
        story_url=scored.story.url,
        title=scored.story.title,
        blurb=best[0],
        word_count=best[1],
        needs_review=True,
    )


def generate_all(
    scored_stories: list[ScoredStory], newsletter: str = "tldr_ai"
) -> list[GeneratedBlurb]:
    out: list[GeneratedBlurb] = []
    for s in scored_stories:
        out.append(generate_blurb(s, newsletter=newsletter))
    return out
