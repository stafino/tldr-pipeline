"""Shared scaffolding for LLM-driven story extractors.

The funding and vc modules both implement the same skeleton:

1. Pre-filter scored stories by a cheap title regex.
2. For each candidate: check the on-disk JSON cache, otherwise call the
   LLM with a (system, user) prompt pair, parse the JSON, persist it,
   and turn it into a typed result.
3. Fan the candidates out across a thread pool, collect the survivors.

`LLMExtractor` owns that skeleton. Subclasses just declare:

  - what the cache lives under, which model + concurrency to use, which
    title regex pre-qualifies stories, and the system prompt;
  - how to build the user prompt from a story (`build_user_prompt`);
  - how to turn a parsed payload into a typed result, returning `None`
    when the LLM classified the story out of scope (`parse_payload`).

Everything else — caching, threading, logging, JSON parsing — is
handled here so the two extractors stay logic-identical.
"""

from __future__ import annotations

import logging
import re
from typing import Generic, Optional, TypeVar

from common.cache import UrlJsonCache
from common.json_utils import parse_llm_json
from common.llm import complete
from common.parallel import parallel_map
from common.story import ScoredStory

log = logging.getLogger(__name__)

T = TypeVar("T")


class LLMExtractor(Generic[T]):
    """Base class for cache-backed, threaded LLM extractors.

    Subclasses set the class-level configuration (cache, model,
    concurrency, title regex, system prompt) and override
    `build_user_prompt` + `parse_payload`. Everything else is shared.
    """

    # Subclass configuration ------------------------------------------------
    cache: UrlJsonCache
    model: str
    concurrency: int
    title_filter_re: re.Pattern
    system_prompt: str
    # Label used in log lines ("funding", "vc"). Defaults to the class name.
    log_label: str = ""
    # max_tokens passed to the LLM call. Both current callers use 400.
    max_tokens: int = 400

    # Subclass hooks --------------------------------------------------------
    def build_user_prompt(self, story: ScoredStory) -> str:
        """Render the user-message prompt for a single story."""
        raise NotImplementedError

    def parse_payload(self, story: ScoredStory, payload: dict) -> Optional[T]:
        """Turn a parsed JSON payload into a typed result.

        Return `None` when the LLM said the story is out of scope
        (e.g. `is_funding=false`, `is_vc=false`).
        """
        raise NotImplementedError

    def post_filter(self, result: T) -> bool:
        """Optional final gate per result. Return False to drop it."""
        return True

    def sort_results(self, results: list[T]) -> list[T]:
        """Optional ordering for the returned list. Default: no sort."""
        return results

    # Shared machinery ------------------------------------------------------
    def _label(self) -> str:
        return self.log_label or self.__class__.__name__

    def extract_one(self, story: ScoredStory) -> Optional[T]:
        """Cache-check → LLM → parse → cache-store. Mirrors the original
        per-module `_extract_one` exactly: cached negatives stay negative
        without a second LLM call, cached positives are re-built into a
        typed result from the cached payload.
        """
        label = self._label()
        url = story.story.url
        cached = self.cache.load(url)
        if cached is not None:
            return self.parse_payload(story, cached)

        user = self.build_user_prompt(story)
        try:
            raw = complete(
                self.system_prompt,
                user,
                model=self.model,
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            log.warning("%s extract LLM error for %s: %r", label, url, e)
            return None

        payload = parse_llm_json(raw)
        if payload is None:
            log.warning("%s extract: could not parse JSON for %s", label, url)
            return None

        self.cache.save(url, payload)
        return self.parse_payload(story, payload)

    def extract(self, scored: list[ScoredStory]) -> list[T]:
        """Pre-filter by title regex, then LLM-extract in parallel."""
        label = self._label()
        candidates = [
            s for s in scored if self.title_filter_re.search(s.story.title or "")
        ]
        log.info(
            "%s: %d candidates (of %d scored) after title filter",
            label,
            len(candidates),
            len(scored),
        )

        def _run(story: ScoredStory) -> Optional[T]:
            r = self.extract_one(story)
            if r is None or not self.post_filter(r):
                return None
            return r

        out: list[T] = parallel_map(
            _run,
            candidates,
            concurrency=self.concurrency,
            log=log,
            error_msg_fn=lambda _s, e: f"{label} worker error: {e!r}",
        )

        out = self.sort_results(out)
        log.info("%s: kept %d results", label, len(out))
        return out
