from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class Story:
    title: str
    url: str
    source: str
    source_type: str  # rss | arxiv | hn
    published_at: str  # ISO 8601
    raw_text: str = ""
    related_sources: list[str] = field(default_factory=list)
    source_topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Story":
        return cls(
            title=d["title"],
            url=d["url"],
            source=d["source"],
            source_type=d["source_type"],
            published_at=d["published_at"],
            raw_text=d.get("raw_text", ""),
            related_sources=d.get("related_sources", []),
            source_topics=d.get("source_topics", []),
        )


@dataclass
class Assignment:
    """A story's fit for one newsletter."""

    newsletter: str
    section_id: str
    score: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Assignment":
        return cls(
            newsletter=d["newsletter"],
            section_id=d["section_id"],
            score=float(d["score"]),
        )


@dataclass
class ScoredStory:
    story: Story
    score: float  # primary (max) score across all assignments
    reasoning: str
    is_technical: bool
    is_novel: bool
    is_mainstream_relevant: bool
    assignments: list[Assignment] = field(default_factory=list)

    @property
    def primary(self) -> Assignment | None:
        if not self.assignments:
            return None
        return max(self.assignments, key=lambda a: a.score)

    @property
    def newsletters(self) -> list[str]:
        return [a.newsletter for a in self.assignments]

    def for_newsletter(self, nid: str) -> Assignment | None:
        for a in self.assignments:
            if a.newsletter == nid:
                return a
        return None

    def to_dict(self) -> dict:
        return {
            "story": self.story.to_dict(),
            "score": self.score,
            "reasoning": self.reasoning,
            "is_technical": self.is_technical,
            "is_novel": self.is_novel,
            "is_mainstream_relevant": self.is_mainstream_relevant,
            "assignments": [a.to_dict() for a in self.assignments],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScoredStory":
        # Backwards-compat: older entries used single-newsletter fields.
        assignments = [Assignment.from_dict(a) for a in d.get("assignments", [])]
        if not assignments and d.get("newsletter") and d.get("section_id"):
            assignments = [
                Assignment(
                    newsletter=d["newsletter"],
                    section_id=d["section_id"],
                    score=float(d.get("score", 0)),
                )
            ]
        return cls(
            story=Story.from_dict(d["story"]),
            score=float(d.get("score", 0)),
            reasoning=d.get("reasoning", ""),
            is_technical=bool(d.get("is_technical", False)),
            is_novel=bool(d.get("is_novel", False)),
            is_mainstream_relevant=bool(d.get("is_mainstream_relevant", False)),
            assignments=assignments,
        )


def write_jsonl(path: Path, items: Iterable) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for item in items:
            f.write(json.dumps(item.to_dict() if hasattr(item, "to_dict") else item))
            f.write("\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
