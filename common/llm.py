"""LLM backend abstraction.

Two backends are supported:
  - "api": uses the Anthropic SDK and ANTHROPIC_API_KEY (fast, billed per token)
  - "cli": shells out to `claude -p --bare ...` and bills against your Claude Code
           subscription (slower, but no API key needed)

Switch with LLM_BACKEND=api|cli (default: api).

Model aliases are normalized per backend:
  - API backend uses the full IDs from RANKING_MODEL / BLURB_MODEL envs.
  - CLI backend accepts short names ("sonnet", "opus", "haiku") which the CLI
    resolves to whatever the subscription tier exposes. If RANKING_MODEL/BLURB_MODEL
    are full IDs, we map them to the closest short name for the CLI.
"""

from __future__ import annotations

import logging
import os
import subprocess
from abc import ABC, abstractmethod

from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


def _resolve_backend() -> str:
    return os.environ.get("LLM_BACKEND", "api").lower()


def _cli_model_alias(full_id: str) -> str:
    """Map a full model ID to the short alias the claude CLI accepts."""
    fid = full_id.lower()
    if "opus" in fid:
        return "opus"
    if "haiku" in fid:
        return "haiku"
    return "sonnet"


class LLMBackend(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, model: str, max_tokens: int = 1024) -> str:
        """Return the assistant's text response."""


class APIBackend(LLMBackend):
    def __init__(self):
        from anthropic import Anthropic

        self.client = Anthropic()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def complete(self, system: str, user: str, model: str, max_tokens: int = 1024) -> str:
        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


class CLIBackend(LLMBackend):
    """Shells out to `claude -p --bare`. Slower but uses your subscription, not an API key."""

    def __init__(self):
        # Locate the CLI once.
        result = subprocess.run(["which", "claude"], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "LLM_BACKEND=cli but the `claude` CLI is not on PATH. "
                "Install Claude Code or switch to LLM_BACKEND=api."
            )
        self.claude_bin = result.stdout.strip()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=15))
    def complete(self, system: str, user: str, model: str, max_tokens: int = 1024) -> str:
        # max_tokens is not directly settable via CLI; we encode the constraint in the prompt instead.
        # --bare skips hooks/CLAUDE.md/plugin sync so the call is isolated.
        cmd = [
            self.claude_bin,
            "-p",
            "--bare",
            "--model",
            _cli_model_alias(model),
            "--system-prompt",
            system,
            "--output-format",
            "text",
            user,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180, check=True
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"claude CLI timed out after 180s: {e}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"claude CLI failed (exit {e.returncode}): {e.stderr[:500]}"
            ) from e
        return proc.stdout.strip()


_BACKEND: LLMBackend | None = None


def get_backend() -> LLMBackend:
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    backend = _resolve_backend()
    if backend == "cli":
        log.info("LLM backend: cli (using Claude Code subscription)")
        _BACKEND = CLIBackend()
    else:
        log.info("LLM backend: api (using ANTHROPIC_API_KEY)")
        _BACKEND = APIBackend()
    return _BACKEND


def complete(system: str, user: str, model: str, max_tokens: int = 1024) -> str:
    """Convenience wrapper. Picks the backend from LLM_BACKEND env."""
    return get_backend().complete(system, user, model, max_tokens=max_tokens)
