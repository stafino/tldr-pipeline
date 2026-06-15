from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
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


@dataclass
class Newsletter:
    id: str
    brand_name: str
    voice_skill: str
    sections: list[Section]

    @property
    def section_ids(self) -> list[str]:
        return [s.id for s in self.sections]

    def section(self, sid: str) -> Section | None:
        for s in self.sections:
            if s.id == sid:
                return s
        return None


@lru_cache(maxsize=4)
def load_newsletters(path: str = "config/newsletters.yaml") -> dict[str, Newsletter]:
    data = yaml.safe_load(Path(path).read_text())
    out: dict[str, Newsletter] = {}
    for nid, nl in data.items():
        if nid == "default":
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
        )
    return out


def default_newsletter_id(path: str = "config/newsletters.yaml") -> str:
    data = yaml.safe_load(Path(path).read_text())
    return data.get("default", "tldr_founders")


def get_newsletter(nid: str, path: str = "config/newsletters.yaml") -> Newsletter:
    nls = load_newsletters(path)
    if nid not in nls:
        raise KeyError(f"Unknown newsletter '{nid}'. Available: {list(nls)}")
    return nls[nid]
