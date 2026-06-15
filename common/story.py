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
        )


@dataclass
class ScoredStory:
    story: Story
    score: float
    reasoning: str
    is_technical: bool
    is_novel: bool
    is_mainstream_relevant: bool
    section_id: str = ""  # which newsletter section this belongs in
    newsletter: str = ""

    def to_dict(self) -> dict:
        return {
            "story": self.story.to_dict(),
            "score": self.score,
            "reasoning": self.reasoning,
            "is_technical": self.is_technical,
            "is_novel": self.is_novel,
            "is_mainstream_relevant": self.is_mainstream_relevant,
            "section_id": self.section_id,
            "newsletter": self.newsletter,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScoredStory":
        return cls(
            story=Story.from_dict(d["story"]),
            score=float(d["score"]),
            reasoning=d.get("reasoning", ""),
            is_technical=bool(d.get("is_technical", False)),
            is_novel=bool(d.get("is_novel", False)),
            is_mainstream_relevant=bool(d.get("is_mainstream_relevant", False)),
            section_id=d.get("section_id", ""),
            newsletter=d.get("newsletter", ""),
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
