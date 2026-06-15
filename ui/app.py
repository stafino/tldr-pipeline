from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from common.newsletters import default_newsletter_id, load_newsletters
from common.story import ScoredStory, read_jsonl
from formatters.tldr import render as render_tldr

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
    code, .stTextArea textarea { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("tldr pipeline")
st.caption("Daily candidate ranking by section. Pick a date, review, export issue draft.")


def _available_dates() -> list[str]:
    dates: set[str] = set()
    for d in (SCORED_DIR, BLURBS_DIR):
        if d.exists():
            for p in d.glob("*.jsonl"):
                dates.add(p.stem)
    return sorted(dates, reverse=True)


def _load_blurbs(d: str) -> dict[str, dict]:
    p = BLURBS_DIR / f"{d}.jsonl"
    if not p.exists():
        return {}
    out: dict[str, dict] = {}
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            b = json.loads(line)
            out[b["story_url"]] = b
    return out


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

newsletters = load_newsletters()
default_nl = default_newsletter_id()
nl_ids = list(newsletters.keys())

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    selected_date = st.selectbox("date", dates, index=0)
with col2:
    selected_nl = st.selectbox(
        "newsletter", nl_ids, index=nl_ids.index(default_nl) if default_nl in nl_ids else 0
    )
with col3:
    counts = _counts_for_day(selected_date)
    st.markdown(
        f"**raw**: {counts['raw']} &nbsp;&nbsp; **deduped**: {counts['deduped']} &nbsp;&nbsp; "
        f"**scored**: {counts['scored']} &nbsp;&nbsp; **blurbed**: {counts['blurbed']}"
    )

nl = newsletters[selected_nl]
scored_raw = read_jsonl(SCORED_DIR / f"{selected_date}.jsonl")
scored = [ScoredStory.from_dict(d) for d in scored_raw if d.get("newsletter", selected_nl) == selected_nl]

if not scored:
    st.info(
        f"No stories scored under newsletter '{selected_nl}' for {selected_date}. "
        f"Run `make rank DATE={selected_date} --newsletter {selected_nl}` first."
    )
    st.stop()

blurbs_by_url = _load_blurbs(selected_date)

# Group and slice top-N per section.
by_section: dict[str, list[ScoredStory]] = {s.id: [] for s in nl.sections}
for s in scored:
    if s.section_id in by_section:
        by_section[s.section_id].append(s)
for sec in nl.sections:
    by_section[sec.id] = by_section[sec.id][: sec.target_count]

# Render each section as its own table.
tabs = st.tabs([f"{sec.emoji} {sec.name} ({len(by_section[sec.id])})" for sec in nl.sections])
for tab, sec in zip(tabs, nl.sections):
    with tab:
        rows = []
        for rank, s in enumerate(by_section[sec.id], start=1):
            b = blurbs_by_url.get(s.story.url, {})
            rows.append(
                {
                    "#": rank,
                    "score": int(round(s.score)),
                    "title": s.story.title,
                    "url": s.story.url,
                    "min": int(b.get("minute_read", 0)),
                    "wc": int(b.get("word_count", 0)),
                    "flag": bool(b.get("needs_review", False)),
                    "blurb": b.get("blurb", ""),
                    "source": s.story.source,
                    "why": s.reasoning,
                }
            )
        if not rows:
            st.info(f"No stories classified into {sec.name}.")
            continue
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(70 + 110 * len(rows), 700),
            column_config={
                "#": st.column_config.NumberColumn(width="small"),
                "score": st.column_config.NumberColumn(width="small"),
                "title": st.column_config.TextColumn(width="large"),
                "url": st.column_config.LinkColumn(width="medium"),
                "min": st.column_config.NumberColumn("min read", width="small"),
                "wc": st.column_config.NumberColumn("words", width="small"),
                "flag": st.column_config.CheckboxColumn("flag", width="small"),
                "blurb": st.column_config.TextColumn(width="large"),
                "source": st.column_config.TextColumn(width="small"),
                "why": st.column_config.TextColumn("why", width="medium"),
            },
        )

st.divider()
st.subheader("Issue draft (TLDR format)")

issue_text = render_tldr(scored, blurbs_by_url, selected_nl, selected_date)
st.text_area("preview", value=issue_text, height=480, label_visibility="collapsed")

cdl1, cdl2 = st.columns([1, 5])
with cdl1:
    st.download_button(
        "download .txt",
        data=issue_text,
        file_name=f"{selected_nl}-{selected_date}.txt",
        mime="text/plain",
    )
