"""Shared JSON parsing helpers for LLM-extractor modules.

LLMs return JSON wrapped in unpredictable scaffolding — markdown fences,
preamble text, sometimes extra commentary after the closing brace. The
funding and vc extractors both need to deal with this, so the parsing
logic lives here once.
"""

from __future__ import annotations

import json
import re

_FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"\s*```$")
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_llm_json(text: str) -> dict | None:
    """Best-effort parse of an LLM response that is supposed to be one JSON object.

    Strategy:
    1. Strip surrounding whitespace and any ```json/``` fences.
    2. Try a straight json.loads — succeeds for well-behaved replies.
    3. Fall back to extracting the first { … } block via regex and
       parsing that, in case the model added preamble or commentary.
    4. Return None on total failure (caller should log a warning).
    """
    t = (text or "").strip()
    if t.startswith("```"):
        t = _FENCE_OPEN_RE.sub("", t)
        t = _FENCE_CLOSE_RE.sub("", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(t)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
