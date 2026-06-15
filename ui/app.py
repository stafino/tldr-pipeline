from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from common.story import ScoredStory, read_jsonl

SCORED_DIR = Path("data/scored")
BLURBS_DIR = Path("data/blurbs")
RAW_DIR = Path("data/raw")
DEDUP_DIR = Path("data/deduped")

st.set_page_config(page_title="TLDR Pipeline", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1400px; }
    .stDataFrame, .stTable { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
    h1, h2, h3 { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    code { font-size: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("tldr pipeline")
st.caption("Daily candidate ranking. Pick a date, pick stories, export.")


def _available_dates() -> list[str]:
    dates: set[str] = set()
    for d in (SCORED_DIR, BLURBS_DIR):
        if d.exists():
            for p in d.glob("*.jsonl"):
                dates.add(p.stem)
    return sorted(dates, reverse=True)


def _load_day(d: str) -> tuple[list[ScoredStory], dict[str, dict]]:
    scored_raw = read_jsonl(SCORED_DIR / f"{d}.jsonl")
    scored = [ScoredStory.from_dict(s) for s in scored_raw]
    blurbs_map: dict[str, dict] = {}
    blurbs_path = BLURBS_DIR / f"{d}.jsonl"
    if blurbs_path.exists():
        with blurbs_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                b = json.loads(line)
                blurbs_map[b["story_url"]] = b
    return scored, blurbs_map


def _counts_for_day(d: str) -> dict[str, int]:
    return {
        "raw": len(read_jsonl(RAW_DIR / f"{d}.jsonl")),
        "deduped": len(read_jsonl(DEDUP_DIR / f"{d}.jsonl")),
        "scored": len(read_jsonl(SCORED_DIR / f"{d}.jsonl")),
        "blurbed": len(read_jsonl(BLURBS_DIR / f"{d}.jsonl")) if (BLURBS_DIR / f"{d}.jsonl").exists() else 0,
    }


dates = _available_dates()
if not dates:
    st.warning(
        "No scored runs found yet. Run `make refresh` (or `make ingest && make dedup && make rank && make blurbs`) first."
    )
    st.stop()

col1, col2 = st.columns([1, 4])
with col1:
    selected = st.selectbox("date", dates, index=0)
with col2:
    counts = _counts_for_day(selected)
    st.markdown(
        f"**raw**: {counts['raw']} &nbsp;&nbsp; **deduped**: {counts['deduped']} &nbsp;&nbsp; **scored**: {counts['scored']} &nbsp;&nbsp; **blurbed**: {counts['blurbed']}"
    )

scored, blurbs_map = _load_day(selected)

if not scored:
    st.info("No scored stories for this date.")
    st.stop()

rows = []
for rank, s in enumerate(scored, start=1):
    blurb = blurbs_map.get(s.story.url, {})
    rows.append(
        {
            "select": False,
            "rank": rank,
            "score": int(round(s.score)),
            "title": s.story.title,
            "url": s.story.url,
            "source": s.story.source,
            "type": s.story.source_type,
            "blurb": blurb.get("blurb", ""),
            "needs_review": blurb.get("needs_review", False),
            "reasoning": s.reasoning,
            "technical": s.is_technical,
            "novel": s.is_novel,
            "mainstream": s.is_mainstream_relevant,
            "related_n": len(s.story.related_sources),
            "related": "\n".join(s.story.related_sources),
        }
    )

df = pd.DataFrame(rows)

edited = st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    height=620,
    column_config={
        "select": st.column_config.CheckboxColumn("✓", width="small"),
        "rank": st.column_config.NumberColumn("#", width="small"),
        "score": st.column_config.NumberColumn("score", width="small"),
        "title": st.column_config.TextColumn("title", width="large"),
        "url": st.column_config.LinkColumn("url", width="medium"),
        "source": st.column_config.TextColumn("source", width="small"),
        "type": st.column_config.TextColumn("type", width="small"),
        "blurb": st.column_config.TextColumn("blurb", width="large"),
        "needs_review": st.column_config.CheckboxColumn("flag", width="small"),
        "reasoning": st.column_config.TextColumn("why", width="medium"),
        "technical": st.column_config.CheckboxColumn("tech", width="small"),
        "novel": st.column_config.CheckboxColumn("nov", width="small"),
        "mainstream": st.column_config.CheckboxColumn("ms", width="small"),
        "related_n": st.column_config.NumberColumn("rel", width="small"),
        "related": st.column_config.TextColumn("related urls", width="medium"),
    },
    disabled=[
        "rank", "score", "title", "url", "source", "type", "reasoning",
        "technical", "novel", "mainstream", "related_n", "related", "needs_review",
    ],
    key="story_table",
)

st.divider()

selected_rows = edited[edited["select"]]
st.markdown(f"**{len(selected_rows)} selected**")

if len(selected_rows) > 0:
    sections = ["Headlines & Launches", "Deep Dives & Analysis", "Engineering & Research", "Miscellaneous", "Quick Links"]
    chosen_section = st.selectbox("export under section", sections, index=0)

    issue_md = [f"## {chosen_section}\n"]
    for _, row in selected_rows.iterrows():
        title = row["title"]
        url = row["url"]
        blurb = row["blurb"] or "(blurb not generated)"
        issue_md.append(f"### {title}\n\n{blurb}\n\n[Read more]({url})\n")
    issue_text = "\n".join(issue_md)

    st.text_area("issue draft (copy to clipboard)", value=issue_text, height=300)
    st.download_button(
        "download .md",
        data=issue_text,
        file_name=f"tldr-{selected}.md",
        mime="text/markdown",
    )
