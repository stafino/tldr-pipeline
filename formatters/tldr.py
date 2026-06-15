"""Render a day's scored + blurbed stories in the exact TLDR newsletter format,
one issue per newsletter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from common.newsletters import Newsletter, get_newsletter, load_newsletters
from common.story import ScoredStory, read_jsonl
from ranking.score import top_per_section


@dataclass
class _Item:
    title: str
    url: str
    blurb: str
    minute_read: int
    needs_review: bool


def _load_blurbs(path: Path, newsletter_id: str) -> dict[str, dict]:
    """Map story_url → blurb dict, filtered to one newsletter."""
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("newsletter") != newsletter_id:
                continue
            out[d["story_url"]] = d
    return out


def render(
    scored: list[ScoredStory],
    blurbs_by_url: dict[str, dict],
    newsletter_id: str,
    day: str,
) -> str:
    nl = get_newsletter(newsletter_id)
    by_section = top_per_section(scored, newsletter_id)

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
    blurbs = _load_blurbs(Path("data/blurbs") / f"{day}.jsonl", newsletter_id)
    return render(scored, blurbs, newsletter_id, day)


def render_all(day: str, out_dir: Path) -> dict[str, Path]:
    """Render every newsletter to data/issues/<nl>-<date>.txt; return paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    nls = load_newsletters()
    paths: dict[str, Path] = {}
    for nid in nls.keys():
        text = render_from_disk(day, nid)
        path = out_dir / f"{nid}-{day}.txt"
        path.write_text(text)
        paths[nid] = path
    return paths


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument(
        "--newsletter", default="all",
        help="A specific newsletter id, or 'all' for every newsletter (default).",
    )
    ap.add_argument("--out-dir", default="data/issues")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if args.newsletter == "all":
        paths = render_all(args.date, out_dir)
        for nid, p in paths.items():
            print(f"{nid}: {p}")
    else:
        text = render_from_disk(args.date, args.newsletter)
        p = out_dir / f"{args.newsletter}-{args.date}.txt"
        out_dir.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        print(text)
        print(f"\n(saved to {p})")


if __name__ == "__main__":
    main()
