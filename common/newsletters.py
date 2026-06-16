from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Section:
    id: str
    name: str
    emoji: str
    min_words: int
    max_words: int
    target_count: int
    description: str

    @property
    def header(self) -> str:
        return f"{self.emoji}\n{self.name}"

    @property
    def is_quick_links(self) -> bool:
        return self.id.endswith("quick_links") or self.id == "quick"


@dataclass
class Newsletter:
    id: str
    brand_name: str
    voice_skill: str
    sections: list[Section]
    topics: list[str] = field(default_factory=list)

    @property
    def section_ids(self) -> list[str]:
        return [s.id for s in self.sections]

    def section(self, sid: str) -> Section | None:
        for s in self.sections:
            if s.id == sid:
                return s
        return None

    @property
    def quick_links_section(self) -> Section | None:
        return next((s for s in self.sections if s.is_quick_links), None)


def load_newsletters(path: str = "config/newsletters.yaml") -> dict[str, Newsletter]:
    data = yaml.safe_load(Path(path).read_text())
    out: dict[str, Newsletter] = {}
    for nid, nl in data.items():
        if nid == "default":
            continue
        if not isinstance(nl, dict):
            continue
        sections = [
            Section(
                id=s["id"],
                name=s["name"],
                emoji=s["emoji"],
                min_words=int(s["min_words"]),
                max_words=int(s["max_words"]),
                target_count=int(s["target_count"]),
                description=s.get("description", "").strip(),
            )
            for s in nl["sections"]
        ]
        out[nid] = Newsletter(
            id=nid,
            brand_name=nl["brand_name"],
            voice_skill=nl["voice_skill"],
            sections=sections,
            topics=list(nl.get("topics", [])),
        )
    return out


def default_newsletter_id(path: str = "config/newsletters.yaml") -> str:
    data = yaml.safe_load(Path(path).read_text())
    return data.get("default", "tldr_tech")


def get_newsletter(nid: str, path: str = "config/newsletters.yaml") -> Newsletter:
    nls = load_newsletters(path)
    if nid not in nls:
        raise KeyError(f"Unknown newsletter '{nid}'. Available: {list(nls)}")
    return nls[nid]
