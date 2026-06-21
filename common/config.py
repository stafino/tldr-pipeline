"""Centralized env-var defaults for pipeline-stage tuning.

Per-stage `ModelConfig` bundles the LLM model id and its parallel-worker
count. Env var names are unchanged so the cron + Vercel env config keep
working — only the read site moved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """LLM model + concurrency for a pipeline stage."""

    model: str
    concurrency: int


def _model_config(prefix: str, default_model: str, default_concurrency: int) -> ModelConfig:
    return ModelConfig(
        model=os.environ.get(f"{prefix}_MODEL", default_model),
        concurrency=int(os.environ.get(f"{prefix}_CONCURRENCY", str(default_concurrency))),
    )


# Per-stage configs — defaults match what each module previously hardcoded.
FUNDING = _model_config("FUNDING", "claude-haiku-4-5-20251001", 8)
VC = _model_config("VC", "claude-haiku-4-5-20251001", 8)
RANKING = _model_config("RANKING", "claude-sonnet-4-6", 6)
BLURB = _model_config("BLURB", "claude-opus-4-7", 5)

# Backend selector for common.llm. Lowercased to match prior _resolve_backend()
# semantics so callers comparing against "api"/"cli" keep working.
LLM_BACKEND = os.environ.get("LLM_BACKEND", "api").lower()
