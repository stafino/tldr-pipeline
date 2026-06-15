from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from common.story import ScoredStory, Story

log = logging.getLogger(__name__)

RUBRIC_PATH = Path(".claude/skills/curation_rubric.md")
CACHE_DIR = Path("data/scored/.cache")

RANKING_MODEL = os.environ.get("RANKING_MODEL", "claude-sonnet-4-6")

SYSTEM_TEMPLATE = """You are an editorial scorer for a technical AI newsletter. Apply the rubric below to score one story at a time. Always return JSON matching the exact schema requested. No prose outside JSON.

RUBRIC:
{rubric}"""

USER_TEMPLATE = """Score this candidate story for {newsletter}:

Title: {title}
Source: {source} ({source_type})
URL: {url}
Snippet: {snippet}

Return a JSON object with exactly these keys:
{{
  "score": <integer 0-100>,
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


def _cache_key(story: Story, newsletter: str) -> Path:
    h = hashlib.sha1(f"{newsletter}|{story.url}|{story.title}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _call_model(client: Anthropic, system: str, user: str) -> dict:
    resp = client.messages.create(
        model=RANKING_MODEL,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    # Strip ```json fences if the model wraps the response.
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def rank_stories(
    stories: list[Story], newsletter: str = "tldr_ai", use_cache: bool = True
) -> list[ScoredStory]:
    if not stories:
        return []

    rubric = _load_rubric()
    system = SYSTEM_TEMPLATE.format(rubric=rubric)
    client = Anthropic()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    scored: list[ScoredStory] = []
    for story in stories:
        cache_path = _cache_key(story, newsletter)
        if use_cache and cache_path.exists():
            data = json.loads(cache_path.read_text())
        else:
            user = USER_TEMPLATE.format(
                newsletter=newsletter,
                title=story.title,
                source=story.source,
                source_type=story.source_type,
                url=story.url,
                snippet=(story.raw_text or "")[:500],
            )
            try:
                data = _call_model(client, system, user)
            except Exception as e:
                log.warning("Ranking failed for %s: %s", story.url, e)
                continue
            cache_path.write_text(json.dumps(data))

        try:
            scored.append(
                ScoredStory(
                    story=story,
                    score=float(data.get("score", 0)),
                    reasoning=str(data.get("reasoning", "")),
                    is_technical=bool(data.get("is_technical", False)),
                    is_novel=bool(data.get("is_novel", False)),
                    is_mainstream_relevant=bool(data.get("is_mainstream_relevant", False)),
                )
            )
        except Exception as e:
            log.warning("Parse failed for %s: %s", story.url, e)

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
