from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from common.newsletters import default_newsletter_id, load_newsletters
from common.story import ScoredStory, read_jsonl
from formatters.tldr import render as render_tldr
from ranking.score import top_per_section

SCORED_DIR = Path("data/scored")
BLURBS_DIR = Path("data/blurbs")
RAW_DIR = Path("data/raw")
DEDUP_DIR = Path("data/deduped")

st.set_page_config(page_title="TLDR Pipeline", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1500px; }
    .stDataFrame, .stTable { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    h1, h2, h3 { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    code, .stTextArea textarea { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    [data-testid="stMetricValue"] { font-size: 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("tldr pipeline")
st.caption("Daily TLDR-family curation — every newsletter, every section.")


def _available_dates() -> list[str]:
    dates: set[str] = set()
    for d in (SCORED_DIR, BLURBS_DIR):
        if d.exists():
            for p in d.glob("*.jsonl"):
                dates.add(p.stem)
    return sorted(dates, reverse=True)


def _load_blurbs_for_date(d: str) -> list[dict]:
    p = BLURBS_DIR / f"{d}.jsonl"
    if not p.exists():
        return []
    out = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _counts_for_day(d: str) -> dict[str, int]:
    return {
        "raw": len(read_jsonl(RAW_DIR / f"{d}.jsonl")),
        "deduped": len(read_jsonl(DEDUP_DIR / f"{d}.jsonl")),
        "scored": len(read_jsonl(SCORED_DIR / f"{d}.jsonl")),
        "blurbed": len(_load_blurbs_for_date(d)),
    }


dates = _available_dates()
if not dates:
    st.warning(
        "No scored runs found yet. Run `tldr refresh` (or `make refresh`) first."
    )
    st.stop()

newsletters = load_newsletters()
nl_ids = list(newsletters.keys())
default_nl = default_newsletter_id()
nl_default_idx = nl_ids.index(default_nl) if default_nl in nl_ids else 0

cols_top = st.columns([1, 1, 3])
with cols_top[0]:
    selected_date = st.selectbox("date", dates, index=0)
counts = _counts_for_day(selected_date)
with cols_top[1]:
    st.markdown(
        f"raw **{counts['raw']}** • deduped **{counts['deduped']}** • scored **{counts['scored']}** • blurbed **{counts['blurbed']}**"
    )

# Count assignments per newsletter for the date.
scored_raw = read_jsonl(SCORED_DIR / f"{selected_date}.jsonl")
scored = [ScoredStory.from_dict(d) for d in scored_raw]
per_nl_counts = {nid: 0 for nid in nl_ids}
for s in scored:
    for a in s.assignments:
        if a.newsletter in per_nl_counts:
            per_nl_counts[a.newsletter] += 1

with cols_top[2]:
    summary = " · ".join(f"{nid.replace('tldr_','')} {n}" for nid, n in per_nl_counts.items() if n)
    st.caption(f"per-newsletter assignments → {summary if summary else '(none yet)'}")

cols_nl = st.columns([1, 4])
with cols_nl[0]:
    selected_nl = st.selectbox("newsletter", nl_ids, index=nl_default_idx, format_func=lambda x: newsletters[x].brand_name)
with cols_nl[1]:
    nl = newsletters[selected_nl]
    section_summary = "  ".join(f"{s.emoji} {s.name}" for s in nl.sections)
    st.markdown(f"**{nl.brand_name}** — sections: {section_summary}")

# Filter scored stories that have an assignment to this newsletter.
nl_scored = [s for s in scored if s.for_newsletter(selected_nl) is not None]

if not nl_scored:
    st.info(
        f"No stories assigned to {nl.brand_name} for {selected_date}. "
        "Either none ranked above threshold, or this newsletter wasn't included in the run."
    )
    st.stop()

by_section = top_per_section(scored, selected_nl)
blurbs_all = _load_blurbs_for_date(selected_date)
blurbs_for_nl: dict[str, dict] = {
    b["story_url"]: b for b in blurbs_all if b.get("newsletter") == selected_nl
}

tabs = st.tabs([f"{sec.emoji} {sec.name} ({len(by_section[sec.id])})" for sec in nl.sections])
for tab, sec in zip(tabs, nl.sections):
    with tab:
        rows = []
        for rank, s in enumerate(by_section[sec.id], start=1):
            b = blurbs_for_nl.get(s.story.url, {})
            assignment = s.for_newsletter(selected_nl)
            cross = ", ".join(
                a.newsletter.replace("tldr_", "") for a in s.assignments if a.newsletter != selected_nl
            )
            rows.append(
                {
                    "#": rank,
                    "score": int(round(assignment.score if assignment else s.score)),
                    "title": s.story.title,
                    "url": s.story.url,
                    "min": int(b.get("minute_read", 0)),
                    "wc": int(b.get("word_count", 0)),
                    "flag": bool(b.get("needs_review", False)),
                    "blurb": b.get("blurb", ""),
                    "source": s.story.source,
                    "also_in": cross,
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
            height=min(70 + 100 * len(rows), 700),
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
                "also_in": st.column_config.TextColumn("also in", width="small"),
                "why": st.column_config.TextColumn("why", width="medium"),
            },
        )

st.divider()
st.subheader(f"Issue draft — {nl.brand_name} ({selected_date})")

issue_text = render_tldr(scored, blurbs_for_nl, selected_nl, selected_date)
st.text_area("preview", value=issue_text, height=480, label_visibility="collapsed")

cdl1, cdl2, _ = st.columns([1, 1, 4])
with cdl1:
    st.download_button(
        "download this issue",
        data=issue_text,
        file_name=f"{selected_nl}-{selected_date}.txt",
        mime="text/plain",
    )
with cdl2:
    # Bundle all newsletters for the day.
    bundle_parts: list[str] = []
    for nid in nl_ids:
        try:
            txt = render_tldr(scored, {b["story_url"]: b for b in blurbs_all if b.get("newsletter") == nid}, nid, selected_date)
            if "📈" in txt or "🚀" in txt or "📱" in txt or "🧠" in txt or "⚒" in txt or "📊" in txt or "🔓" in txt or "⚙" in txt or "🤳" in txt or "💻" in txt or "🧑" in txt:
                bundle_parts.append(f"\n\n{'='*60}\n{newsletters[nid].brand_name}\n{'='*60}\n\n" + txt)
        except Exception:
            continue
    bundle_text = ("TLDR family bundle — " + selected_date + "\n").join([""] + bundle_parts) if bundle_parts else "(empty)"
    st.download_button(
        "download all newsletters",
        data=bundle_text,
        file_name=f"tldr-family-{selected_date}.txt",
        mime="text/plain",
    )
