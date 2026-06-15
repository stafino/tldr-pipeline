from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from common.story import Story

log = logging.getLogger(__name__)

# Priority order for picking the canonical story in a cluster.
SOURCE_PRIORITY = {
    "openai_blog": 100,
    "anthropic_news": 100,
    "deepmind_blog": 100,
    "google_research": 95,
    "meta_ai": 95,
    "huggingface_blog": 80,
    "langchain_blog": 70,
    "simonwillison": 75,
    "import_ai": 75,
    "latent_space": 65,
    "aqnichol": 70,
}
ARXIV_PRIORITY = 90
HN_PRIORITY = 40
DEFAULT_RSS_PRIORITY = 60


def _source_priority(story: Story) -> int:
    if story.source_type == "arxiv":
        return ARXIV_PRIORITY
    if story.source_type == "hn":
        return HN_PRIORITY
    return SOURCE_PRIORITY.get(story.source, DEFAULT_RSS_PRIORITY)


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def embed_titles(titles: list[str]) -> np.ndarray:
    """Embed titles with sentence-transformers. Lazy import to keep cold-start fast."""
    from sentence_transformers import SentenceTransformer

    model_name = os.environ.get(
        "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    model = SentenceTransformer(model_name)
    return np.asarray(model.encode(titles, normalize_embeddings=True))


def cluster_stories(stories: list[Story], threshold: float = 0.82) -> list[Story]:
    """Cluster stories by title similarity. Returns one canonical Story per cluster."""
    if not stories:
        return []

    # Cheap pre-pass: collapse exact-domain + exact-title matches first.
    seen_keys: dict[tuple[str, str], int] = {}
    deduped_pre: list[Story] = []
    for s in stories:
        key = (s.title.strip().lower(), _domain(s.url))
        if key in seen_keys:
            idx = seen_keys[key]
            if s.url not in deduped_pre[idx].related_sources:
                deduped_pre[idx].related_sources.append(s.url)
        else:
            seen_keys[key] = len(deduped_pre)
            deduped_pre.append(s)

    titles = [s.title for s in deduped_pre]
    embs = embed_titles(titles)
    sims = cosine_similarity(embs)

    n = len(deduped_pre)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if sims[i, j] >= threshold:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    canonical: list[Story] = []
    for members in clusters.values():
        members_stories = [deduped_pre[i] for i in members]
        chosen = max(members_stories, key=_source_priority)
        related = set(chosen.related_sources)
        for m in members_stories:
            if m.url != chosen.url:
                related.add(m.url)
            related.update(m.related_sources)
        chosen.related_sources = sorted(related)
        canonical.append(chosen)

    log.info("Dedup: %d -> %d stories (threshold=%.2f)", len(stories), len(canonical), threshold)
    return canonical
