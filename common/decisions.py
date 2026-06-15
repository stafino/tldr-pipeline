"""Per-(date, story, newsletter) curator decisions.

The pipeline produces drafts; the UI lets a curator approve, reject, or edit
each story's draft blurb for each newsletter it landed in. Decisions persist
to data/decisions/<date>.jsonl, one record per (story_url, newsletter) pair.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DECISIONS_DIR = Path("data/decisions")

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


@dataclass
class Decision:
    story_url: str
    newsletter: str
    status: str = PENDING       # pending | approved | rejected
    edited_blurb: str = ""      # empty means use the generated blurb as-is
    updated_at: str = ""

    def is_decided(self) -> bool:
        return self.status in (APPROVED, REJECTED)


def _path(date: str) -> Path:
    return DECISIONS_DIR / f"{date}.jsonl"


def load(date: str) -> dict[tuple[str, str], Decision]:
    """Return {(story_url, newsletter) → Decision}. Empty dict if no file yet."""
    p = _path(date)
    out: dict[tuple[str, str], Decision] = {}
    if not p.exists():
        return out
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            decision = Decision(
                story_url=d["story_url"],
                newsletter=d["newsletter"],
                status=d.get("status", PENDING),
                edited_blurb=d.get("edited_blurb", ""),
                updated_at=d.get("updated_at", ""),
            )
            out[(decision.story_url, decision.newsletter)] = decision
    return out


def save(date: str, decisions: dict[tuple[str, str], Decision]) -> None:
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(date)
    with p.open("w") as f:
        for decision in decisions.values():
            f.write(json.dumps(asdict(decision)))
            f.write("\n")


def upsert(
    decisions: dict[tuple[str, str], Decision],
    story_url: str,
    newsletter: str,
    status: str | None = None,
    edited_blurb: str | None = None,
) -> Decision:
    key = (story_url, newsletter)
    d = decisions.get(key) or Decision(story_url=story_url, newsletter=newsletter)
    if status is not None:
        d.status = status
    if edited_blurb is not None:
        d.edited_blurb = edited_blurb
    d.updated_at = datetime.now(timezone.utc).isoformat()
    decisions[key] = d
    return d


def counts(decisions: dict[tuple[str, str], Decision], newsletter: str) -> dict[str, int]:
    out = {APPROVED: 0, REJECTED: 0, PENDING: 0}
    for (_, nid), d in decisions.items():
        if nid != newsletter:
            continue
        out[d.status] = out.get(d.status, 0) + 1
    return out
