"""Shared sentence-transformer embedding with a per-title disk cache.

Titles recur across days (the same story is re-scraped, re-backtested), so the
MiniLM encode is pure wasted CPU on repeats. We cache each title's vector by
content hash under data/embeddings_cache/ (gitignored) and only encode misses.
The model itself is loaded once per process.
"""

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/embeddings_cache")


def _model_name() -> str:
    return os.environ.get("SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=2)
def _get_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _key(text: str, model_name: str) -> str:
    return hashlib.sha1(f"{model_name}\x00{text}".encode()).hexdigest()


def embed(texts: list[str]) -> np.ndarray:
    """Return normalized embeddings for `texts`, using the disk cache for hits
    and encoding only the misses. Output row order matches `texts`."""
    model_name = _model_name()
    n = len(texts)
    out: list[np.ndarray | None] = [None] * n
    miss_idx: list[int] = []
    miss_txt: list[str] = []

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(texts):
        p = CACHE_DIR / f"{_key(t, model_name)}.npy"
        if p.exists():
            try:
                out[i] = np.load(p)
                continue
            except Exception:
                pass  # corrupt cache entry; re-encode
        miss_idx.append(i)
        miss_txt.append(t)

    if miss_txt:
        vecs = np.asarray(_get_model(model_name).encode(miss_txt, normalize_embeddings=True))
        for j, i in enumerate(miss_idx):
            v = np.asarray(vecs[j])
            out[i] = v
            try:
                np.save(CACHE_DIR / f"{_key(texts[i], model_name)}.npy", v)
            except Exception as e:
                log.debug("embedding cache write failed: %r", e)

    return np.vstack(out) if n else np.zeros((0, 0))
