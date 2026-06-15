"""Render a day's scored + blurbed stories in the exact TLDR newsletter format.

Layout:

    Sign Up | Advertise | View Online
    TLDR

    <Brand Name> <YYYY-MM-DD>

    <emoji>
    <Section Name>

    <Title> (<N> minute read)

    <Blurb>

    <Title> (<N> minute read)

    <Blurb>

    [...]

The format matches the body shape of real TLDR issues. Sponsor blocks and
referral footers are omitted; the curator-facing output is the editorial body.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from common.newsletters import Newsletter, get_newsletter
from common.story import ScoredStory, read_jsonl


@dataclass
class _Item:
    title: str
    url: str
    blurb: str
    minute_read: int
    needs_review: bool


def _load_blurbs(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out[d["story_url"]] = d
    return out


def _group_by_section(scored: list[ScoredStory], nl: Newsletter) -> dict[str, list[ScoredStory]]:
    groups: dict[str, list[ScoredStory]] = {s.id: [] for s in nl.sections}
    for s in scored:
        if s.section_id in groups:
            groups[s.section_id].append(s)
    for sec in nl.sections:
        groups[sec.id] = groups[sec.id][: sec.target_count]
    return groups


def render(
    scored: list[ScoredStory],
    blurbs_by_url: dict[str, dict],
    newsletter_id: str,
    day: str,
) -> str:
    nl = get_newsletter(newsletter_id)
    by_section = _group_by_section(scored, nl)

    lines: list[str] = []
    lines.append("Sign Up | Advertise | View Online")
    lines.append("TLDR")
    lines.append("")
    lines.append(f"{nl.brand_name} {day}")
    lines.append("")

    for sec in nl.sections:
        items: list[_Item] = []
        for s in by_section.get(sec.id, []):
            b = blurbs_by_url.get(s.story.url, {})
            blurb_text = b.get("blurb", "").strip()
            if not blurb_text:
                blurb_text = "(blurb not generated)"
            items.append(
                _Item(
                    title=s.story.title.strip(),
                    url=s.story.url,
                    blurb=blurb_text,
                    minute_read=int(b.get("minute_read", 5)),
                    needs_review=bool(b.get("needs_review", False)),
                )
            )

        if not items:
            continue

        lines.append(sec.emoji)
        lines.append(sec.name)
        lines.append("")

        for item in items:
            review_flag = " [flag]" if item.needs_review else ""
            lines.append(f"{item.title} ({item.minute_read} minute read){review_flag}")
            lines.append("")
            lines.append(item.blurb)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_from_disk(day: str, newsletter_id: str) -> str:
    scored = [ScoredStory.from_dict(d) for d in read_jsonl(Path("data/scored") / f"{day}.jsonl")]
    blurbs = _load_blurbs(Path("data/blurbs") / f"{day}.jsonl")
    return render(scored, blurbs, newsletter_id, day)


def main() -> None:
    import argparse

    from common.newsletters import default_newsletter_id

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--newsletter", default=default_newsletter_id())
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    text = render_from_disk(args.date, args.newsletter)

    out_path = Path(args.out) if args.out else Path("data/issues") / f"{args.newsletter}-{args.date}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(text)
    print(f"\n(saved to {out_path})")


if __name__ == "__main__":
    main()
