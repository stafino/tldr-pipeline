"""TLDR pipeline curator UI — dark theme, link-based navigation.

Three-pane layout (Linear Triage style):
- left rail: clickable newsletters + Cross-assignments queue
- middle: section-grouped story list, each row is a clickable link
- right: selected story detail with inline blurb editor + approve/reject
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from common import decisions as dec
from common.newsletters import default_newsletter_id, load_newsletters
from common.story import Assignment, ScoredStory, read_jsonl
from formatters.tldr import render as render_tldr
from ranking.score import top_per_section

SCORED_DIR = Path("data/scored")
BLURBS_DIR = Path("data/blurbs")
RAW_DIR = Path("data/raw")
DEDUP_DIR = Path("data/deduped")

CROSS_KEY = "__cross__"

st.set_page_config(page_title="tldr pipeline", layout="wide", initial_sidebar_state="collapsed")

# ─────────────────────────────────────────────────────────────────────────────
# Color tokens (CSS variables) — change here once, every component picks it up.
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    :root {
        --bg: #0a0a0a;
        --surface: #171717;
        --surface-hi: #1f1f1f;
        --border: #2a2a2a;
        --border-strong: #404040;
        --text: #fafafa;
        --text-dim: #a3a3a3;
        --text-mute: #737373;
        --accent: #3b82f6;
        --accent-soft: #1e3a8a;
        --ok: #10b981;
        --ok-soft: #064e3b;
        --warn: #f59e0b;
        --warn-soft: #78350f;
        --no: #ef4444;
        --no-soft: #7f1d1d;
    }

    .block-container { padding: 1.0rem 1.25rem 5rem; max-width: 1600px; }
    [data-testid="stHeader"] { display: none; }
    [data-testid="stToolbar"] { display: none; }

    /* default sans for prose */
    html, body, .stApp, .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span,
    button, [data-testid="stButton"] button {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif;
    }
    /* mono where it adds clarity */
    .num, .chip, code, pre, .preview, .src, .why { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

    /* ─── Top bar ─── */
    .brand { font-size: 14px; font-weight: 600; letter-spacing: -0.01em; color: var(--text); margin: 0; }
    .pill { font-size: 11px; color: var(--text-dim); }
    .pill b { color: var(--text); font-weight: 600; }
    .topbar-sep { height: 1px; background: var(--border); margin: 8px 0 4px; }

    /* override the date selectbox to dark */
    [data-baseweb="select"] > div { background: var(--surface) !important; border-color: var(--border) !important; color: var(--text) !important; font-size: 12px !important; }
    .stTextInput input { background: var(--surface) !important; border-color: var(--border) !important; color: var(--text) !important; font-size: 12px !important; }

    /* ─── Rail ─── */
    .rail { padding: 4px 0; font-size: 13px; }
    .rail .head { font-size: 10px; letter-spacing: 0.1em; color: var(--text-mute); text-transform: uppercase; margin: 12px 0 6px; }
    .rail a {
        display: flex; justify-content: space-between; align-items: baseline;
        padding: 6px 10px; border-radius: 5px; text-decoration: none;
        color: var(--text-dim); line-height: 1.3; margin-bottom: 1px;
        border: 1px solid transparent;
    }
    .rail a:hover { background: var(--surface); color: var(--text); }
    .rail a.active { background: var(--accent-soft); color: var(--text); border-color: var(--accent); }
    .rail a .lbl { font-weight: 500; }
    .rail a.active .lbl { font-weight: 600; }
    .rail a .ct { color: var(--text-mute); font-size: 11px; }
    .rail a.active .ct { color: #c7d2fe; }
    .rail .star { color: #fbbf24; margin-right: 4px; }

    /* ─── Story list container (rendered as one big HTML blob) ─── */
    .stories-pane { display: flex; flex-direction: column; }

    /* ─── Section headers (sticky) ─── */
    .sec {
        display: flex !important; align-items: center; gap: 10px;
        padding: 16px 4px 8px;
        border-bottom: 1px solid var(--border);
        background: var(--bg);
    }
    .sec .em { font-size: 16px; }
    .sec h3 { font-size: 12px !important; font-weight: 600; margin: 0 !important; color: var(--text) !important; letter-spacing: 0.06em; text-transform: uppercase; }
    .sec .meta { font-size: 11px; color: var(--text-mute); margin-left: auto; }
    .sec-head-top { display: flex; align-items: center; gap: 10px; padding: 4px 4px 14px; border-bottom: 1px solid var(--border-strong); margin-bottom: 0; }
    .sec-head-top h2 { font-size: 13px !important; font-weight: 700; margin: 0 !important; color: var(--text) !important; letter-spacing: 0.02em; }
    .sec-head-top .meta { font-size: 11px; color: var(--text-mute); margin-left: auto; }

    /* ─── Story rows (flexbox; min-width:0 on title is critical to allow wrap) ─── */
    a.row {
        display: flex !important;
        align-items: flex-start;
        gap: 12px;
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
        text-decoration: none !important;
        color: inherit !important;
        cursor: pointer;
        line-height: 1.4;
    }
    a.row:hover { background: var(--surface); }
    a.row.sel { background: var(--accent-soft); border-left: 2px solid var(--accent); padding-left: 6px; }
    a.row .rank { flex: 0 0 22px; text-align: right; color: var(--text-mute); font-size: 11px; padding-top: 1px; }
    a.row .score { flex: 0 0 32px; color: var(--text); font-size: 12px; font-weight: 700; padding-top: 1px; }
    a.row .main { flex: 1 1 auto; min-width: 0; }
    a.row .title { font-size: 13.5px; color: var(--text); margin: 0; word-wrap: break-word; overflow-wrap: break-word; }
    a.row .ftr { font-size: 10.5px; color: var(--text-mute); margin-top: 4px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
    a.row .stat { flex: 0 0 24px; text-align: center; font-size: 14px; line-height: 1; padding-top: 2px; }
    a.row .stat.ok { color: var(--ok); }
    a.row .stat.no { color: var(--no); }
    a.row .stat.warn { color: var(--warn); }
    a.row .stat.pending { color: var(--text-mute); }
    .empty { padding: 20px 4px; color: var(--text-mute); font-size: 12px; }

    /* ─── Chips ─── */
    .chip {
        display: inline-block; padding: 1px 7px; margin-right: 5px;
        border-radius: 3px; font-size: 10.5px;
        background: var(--surface-hi); color: var(--text-dim);
        border: 1px solid var(--border);
    }
    .chip.ok { background: var(--ok-soft); color: #6ee7b7; border-color: #047857; }
    .chip.no { background: var(--no-soft); color: #fca5a5; border-color: #b91c1c; }
    .chip.warn { background: var(--warn-soft); color: #fcd34d; border-color: #d97706; }
    .chip.accent { background: var(--accent-soft); color: #c7d2fe; border-color: var(--accent); }

    /* ─── Detail pane ─── */
    .detail-empty {
        color: var(--text-mute); font-size: 12px; padding: 24px 0;
        border: 1px dashed var(--border); border-radius: 6px;
        text-align: center;
    }
    .detail { padding: 0 4px; }
    .detail h2 { font-size: 15px; font-weight: 600; margin: 0 0 6px; color: var(--text); line-height: 1.35; }
    .detail .src { font-size: 11px; color: var(--text-dim); margin-bottom: 12px; }
    .detail .src a { color: var(--accent); text-decoration: none; }
    .detail .src a:hover { text-decoration: underline; }
    .detail .label {
        font-size: 10px; letter-spacing: 0.1em; color: var(--text-mute);
        text-transform: uppercase; margin: 14px 0 6px;
    }
    .detail .why { font-size: 12px; color: var(--text-dim); line-height: 1.5; margin: 0; }
    .detail .wc { font-size: 11px; color: var(--text-mute); margin-top: 4px; }
    .detail .wc.ok { color: var(--ok); }
    .detail .wc.bad { color: var(--warn); }

    /* override textarea */
    .stTextArea textarea {
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        font-size: 13px !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif !important;
    }
    .stTextArea textarea:focus { border-color: var(--accent) !important; outline: none !important; }

    /* ─── Buttons ─── */
    .stButton button {
        border-radius: 4px; padding: 6px 12px; font-size: 12px; font-weight: 500;
        background: var(--surface); color: var(--text); border: 1px solid var(--border);
        transition: all 0.1s ease;
    }
    .stButton button:hover { background: var(--surface-hi); border-color: var(--border-strong); color: var(--text); }
    .approve .stButton button { color: #6ee7b7; border-color: #065f46; background: var(--ok-soft); }
    .approve .stButton button:hover { background: #065f46; color: #fafafa; border-color: #047857; }
    .reject .stButton button { color: #fca5a5; border-color: #991b1b; background: var(--no-soft); }
    .reject .stButton button:hover { background: #991b1b; color: #fafafa; border-color: #b91c1c; }
    .download .stButton button, .stDownloadButton button { color: var(--text); border-color: var(--border); background: var(--surface); }

    /* ─── Issue preview ─── */
    .preview {
        white-space: pre-wrap; font-size: 11.5px; line-height: 1.5;
        background: var(--surface); padding: 14px; border: 1px solid var(--border); border-radius: 4px;
        max-height: 480px; overflow-y: auto;
        color: var(--text-dim);
    }
    .preview-empty {
        padding: 24px; color: var(--text-mute); font-size: 12px;
        background: var(--surface); border: 1px dashed var(--border); border-radius: 4px;
        text-align: center;
    }

    .stExpander { background: transparent !important; border: 1px solid var(--border) !important; border-radius: 4px !important; }
    .stExpander summary { color: var(--text-dim) !important; font-size: 12px !important; }

    /* Hide Streamlit footer */
    footer { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _available_dates() -> list[str]:
    dates: set[str] = set()
    for d in (SCORED_DIR, BLURBS_DIR):
        if d.exists():
            for p in d.glob("*.jsonl"):
                dates.add(p.stem)
    return sorted(dates, reverse=True)


def _load_blurbs(date: str) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    p = BLURBS_DIR / f"{date}.jsonl"
    if not p.exists():
        return out
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            b = json.loads(line)
            out[(b["story_url"], b["newsletter"])] = b
    return out


def _counts_pipeline(date: str) -> dict[str, int]:
    return {
        "raw": len(read_jsonl(RAW_DIR / f"{date}.jsonl")),
        "deduped": len(read_jsonl(DEDUP_DIR / f"{date}.jsonl")),
        "scored": len(read_jsonl(SCORED_DIR / f"{date}.jsonl")),
        "blurbed": len(read_jsonl(BLURBS_DIR / f"{date}.jsonl")) if (BLURBS_DIR / f"{date}.jsonl").exists() else 0,
    }


def _row_status(decision: dec.Decision | None, blurb: dict, section_min: int, section_max: int) -> tuple[str, str]:
    """Return (css_class, glyph)."""
    if decision and decision.status == dec.APPROVED:
        return "ok", "✓"
    if decision and decision.status == dec.REJECTED:
        return "no", "✗"
    if blurb.get("needs_review"):
        return "warn", "⚠"
    wc = int(blurb.get("word_count", 0))
    if wc and not (section_min <= wc <= section_max):
        return "warn", "⚠"
    return "pending", "●"


def _link(href_params: dict[str, str], inner_html: str, css_class: str = "row-link") -> str:
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in href_params.items())
    return f'<a href="?{qs}" target="_self" class="{css_class}">{inner_html}</a>'


# ─────────────────────────────────────────────────────────────────────────────
# Session bootstrap & query-param parsing
# ─────────────────────────────────────────────────────────────────────────────
ss = st.session_state
qp = st.query_params

# Restore selected newsletter & story from query params if present (allows
# clickable links instead of fat Streamlit buttons).
if "nl" in qp:
    ss.selected_nl = qp["nl"]
if "story" in qp:
    ss.selected_url = qp["story"]
    ss.selected_nl_for_detail = qp.get("nl_detail", ss.get("selected_nl"))

if "selected_url" not in ss:
    ss.selected_url = None
if "selected_nl" not in ss:
    ss.selected_nl = None
if "selected_nl_for_detail" not in ss:
    ss.selected_nl_for_detail = None
if "decisions" not in ss:
    ss.decisions = {}
if "loaded_date" not in ss:
    ss.loaded_date = None


# ─────────────────────────────────────────────────────────────────────────────
# Top bar
# ─────────────────────────────────────────────────────────────────────────────
dates = _available_dates()
if not dates:
    st.markdown('<h1 class="brand">tldr pipeline</h1>', unsafe_allow_html=True)
    st.write("")
    st.markdown(
        '<p style="color:#a3a3a3;font-size:13px;">No scored runs yet. Run <code>tldr refresh</code> to populate today.</p>',
        unsafe_allow_html=True,
    )
    st.stop()

nls = load_newsletters()
nl_ids = list(nls.keys())

tb1, tb2, tb3, tb4 = st.columns([2, 3, 4, 3])
with tb1:
    st.markdown('<h1 class="brand">tldr pipeline</h1>', unsafe_allow_html=True)
with tb2:
    selected_date = st.selectbox("date", dates, index=0, label_visibility="collapsed")

# Reload decisions when date changes
if ss.loaded_date != selected_date:
    ss.decisions = dec.load(selected_date)
    ss.loaded_date = selected_date

counts = _counts_pipeline(selected_date)

with tb3:
    st.markdown(
        f'<div class="pill" style="padding-top:6px;">'
        f'raw <b>{counts["raw"]}</b> · '
        f'dedup <b>{counts["deduped"]}</b> · '
        f'scored <b>{counts["scored"]}</b> · '
        f'blurbed <b>{counts["blurbed"]}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )

with tb4:
    st.text_input("search", placeholder="search…", label_visibility="collapsed", key="search")

st.markdown('<div class="topbar-sep"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Load scored + blurbs
# ─────────────────────────────────────────────────────────────────────────────
scored_all = [ScoredStory.from_dict(d) for d in read_jsonl(SCORED_DIR / f"{selected_date}.jsonl")]
blurbs = _load_blurbs(selected_date)

# Apply search filter
search_q = (ss.get("search") or "").strip().lower()
if search_q:
    scored_all = [s for s in scored_all if search_q in s.story.title.lower()]

nl_totals: dict[str, int] = {nid: 0 for nid in nl_ids}
nl_decided: dict[str, int] = {nid: 0 for nid in nl_ids}
cross_set: set[str] = set()
for s in scored_all:
    if len(s.assignments) > 1:
        cross_set.add(s.story.url)
    for a in s.assignments:
        if a.newsletter in nl_totals:
            nl_totals[a.newsletter] += 1
            d = ss.decisions.get((s.story.url, a.newsletter))
            if d and d.is_decided():
                nl_decided[a.newsletter] += 1

# Auto-select first newsletter on first load (prefer one with assignments)
if ss.selected_nl is None or ss.selected_nl not in nl_ids + [CROSS_KEY]:
    for nid in nl_ids:
        if nl_totals[nid] > 0:
            ss.selected_nl = nid
            break
    else:
        ss.selected_nl = default_newsletter_id()


# ─────────────────────────────────────────────────────────────────────────────
# Three-pane layout
# ─────────────────────────────────────────────────────────────────────────────
rail_col, mid_col, det_col = st.columns([1.0, 3.0, 2.0], gap="medium")


# ─── LEFT RAIL ───
with rail_col:
    rail_html = ['<div class="rail">', '<div class="head">queue</div>']

    cross_decided = sum(
        1 for url in cross_set
        if all(
            ss.decisions.get((url, a.newsletter), dec.Decision(url, a.newsletter)).is_decided()
            for s in scored_all if s.story.url == url for a in s.assignments
        )
    )
    cross_active = " active" if ss.selected_nl == CROSS_KEY else ""
    rail_html.append(
        _link(
            {"nl": CROSS_KEY},
            f'<span class="lbl"><span class="star">★</span>Cross-assigned</span>'
            f'<span class="ct">{cross_decided}/{len(cross_set)}</span>',
            css_class=f"rail-link",
        ).replace('class="rail-link"', f'class="rail-link{cross_active}"')
    )

    rail_html.append('<div class="head">newsletters</div>')
    for nid in nl_ids:
        nl = nls[nid]
        total = nl_totals[nid]
        decided = nl_decided[nid]
        label = nl.brand_name.replace("TLDR ", "").replace("TLDR", "Main")
        active = " active" if ss.selected_nl == nid else ""
        count_color = "ct"
        rail_html.append(
            _link(
                {"nl": nid},
                f'<span class="lbl">{label}</span><span class="{count_color}">{decided}/{total}</span>',
                css_class=f"rail-link{active}",
            )
        )

    rail_html.append("</div>")
    st.markdown("".join(rail_html), unsafe_allow_html=True)


# ─── MIDDLE PANE ───
def _build_row_html(
    rank: int,
    score: float,
    title: str,
    story_url: str,
    target_nl: str,           # which newsletter the row's primary assignment is to
    rail_nl: str,             # what's selected in the rail (for the back-link)
    chips_html: str,
    wc_text: str,
    status_cls: str,
    glyph: str,
    is_sel: bool,
) -> str:
    qs_params = {"nl": rail_nl, "story": story_url, "nl_detail": target_nl}
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in qs_params.items())
    sel_cls = " sel" if is_sel else ""
    title_safe = title.replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<a class="row{sel_cls}" href="?{qs}" target="_self">'
        f'<span class="num rank">{rank}</span>'
        f'<span class="num score">{int(round(score))}</span>'
        f'<span class="main">'
        f'<span class="title">{title_safe}</span>'
        f'<span class="ftr">{chips_html}<span class="num">{wc_text}</span></span>'
        f'</span>'
        f'<span class="stat {status_cls}">{glyph}</span>'
        f'</a>'
    )


def _chips_for(scored_story: ScoredStory, decisions, exclude_nl: str | None = None, primary_nl: str | None = None) -> str:
    chips: list[str] = []
    for a in scored_story.assignments:
        if a.newsletter == exclude_nl:
            continue
        nick = a.newsletter.replace("tldr_", "")
        d = decisions.get((scored_story.story.url, a.newsletter))
        if d and d.status == dec.APPROVED:
            cls = "ok"
        elif d and d.status == dec.REJECTED:
            cls = "no"
        elif a.newsletter == primary_nl:
            cls = "accent"
        else:
            cls = ""
        chips.append(f'<span class="chip {cls}">{nick}</span>')
    return "".join(chips)


with mid_col:
    parts: list[str] = ['<div class="stories-pane">']

    if ss.selected_nl == CROSS_KEY:
        cross_stories = sorted(
            [s for s in scored_all if s.story.url in cross_set],
            key=lambda s: s.score, reverse=True
        )
        parts.append(
            f'<div class="sec-head-top"><h2>★ Cross-assignments</h2>'
            f'<span class="meta">{len(cross_stories)} stories in 2+ newsletters</span></div>'
        )
        if not cross_stories:
            parts.append('<div class="empty">No cross-assignments today.</div>')
        else:
            for rank, s in enumerate(cross_stories, start=1):
                primary = s.primary
                if primary is None:
                    continue
                sec_obj = nls[primary.newsletter].section(primary.section_id)
                section_min = sec_obj.min_words if sec_obj else 40
                section_max = sec_obj.max_words if sec_obj else 80
                blurb = blurbs.get((s.story.url, primary.newsletter), {})
                decision = ss.decisions.get((s.story.url, primary.newsletter))
                status_cls, glyph = _row_status(decision, blurb, section_min, section_max)
                is_sel = (ss.selected_url == s.story.url and ss.selected_nl_for_detail == primary.newsletter)
                chips_html = _chips_for(s, ss.decisions, primary_nl=primary.newsletter)
                wc = int(blurb.get("word_count", 0))
                wc_text = f"{wc}w" if wc else "—"
                parts.append(_build_row_html(
                    rank=rank, score=primary.score, title=s.story.title,
                    story_url=s.story.url, target_nl=primary.newsletter, rail_nl=CROSS_KEY,
                    chips_html=chips_html, wc_text=wc_text,
                    status_cls=status_cls, glyph=glyph, is_sel=is_sel,
                ))

    else:
        nl = nls[ss.selected_nl]
        by_section = top_per_section(scored_all, nl.id)
        total_for_nl = sum(len(stories) for stories in by_section.values())
        parts.append(
            f'<div class="sec-head-top"><h2>{nl.brand_name}</h2>'
            f'<span class="meta">{nl_decided[nl.id]}/{total_for_nl} decided · '
            f'{selected_date}</span></div>'
        )

        if total_for_nl == 0:
            parts.append(f'<div class="empty">No stories assigned to {nl.brand_name} for {selected_date}.</div>')
        else:
            for sec_obj in nl.sections:
                stories = by_section[sec_obj.id]
                if not stories:
                    continue
                decided_in_sec = sum(
                    1 for s in stories
                    if (d := ss.decisions.get((s.story.url, nl.id))) and d.is_decided()
                )
                parts.append(
                    f'<div class="sec"><span class="em">{sec_obj.emoji}</span>'
                    f'<h3>{sec_obj.name}</h3>'
                    f'<span class="meta">{decided_in_sec}/{len(stories)}</span></div>'
                )
                for rank, s in enumerate(stories, start=1):
                    a = s.for_newsletter(nl.id)
                    if a is None:
                        continue
                    blurb = blurbs.get((s.story.url, nl.id), {})
                    decision = ss.decisions.get((s.story.url, nl.id))
                    status_cls, glyph = _row_status(decision, blurb, sec_obj.min_words, sec_obj.max_words)
                    chips_html = _chips_for(s, ss.decisions, exclude_nl=nl.id)
                    wc = int(blurb.get("word_count", 0))
                    wc_text = f"{wc}w" if wc else "—"
                    is_sel = (ss.selected_url == s.story.url and ss.selected_nl_for_detail == nl.id)
                    parts.append(_build_row_html(
                        rank=rank, score=a.score, title=s.story.title,
                        story_url=s.story.url, target_nl=nl.id, rail_nl=nl.id,
                        chips_html=chips_html, wc_text=wc_text,
                        status_cls=status_cls, glyph=glyph, is_sel=is_sel,
                    ))

    parts.append("</div>")  # close stories-pane
    st.markdown("".join(parts), unsafe_allow_html=True)


# ─── RIGHT PANE — Detail / Editor ───
with det_col:
    selected_url = ss.selected_url
    selected_nl_for_detail = ss.selected_nl_for_detail

    selected_scored: ScoredStory | None = None
    selected_assignment: Assignment | None = None
    if selected_url and selected_nl_for_detail and selected_nl_for_detail in nl_ids:
        for s in scored_all:
            if s.story.url == selected_url:
                selected_scored = s
                selected_assignment = s.for_newsletter(selected_nl_for_detail)
                break

    if selected_scored is None or selected_assignment is None:
        st.markdown(
            '<div class="detail-empty">click a story row to load it here</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="detail">', unsafe_allow_html=True)
        nl = nls[selected_nl_for_detail]
        sec_obj = nl.section(selected_assignment.section_id)
        blurb = blurbs.get((selected_scored.story.url, selected_nl_for_detail), {})
        decision = ss.decisions.get((selected_scored.story.url, selected_nl_for_detail))

        st.markdown(f'<h2>{selected_scored.story.title}</h2>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="src">{selected_scored.story.source} · '
            f'<a href="{selected_scored.story.url}" target="_blank">open ↗</a> · '
            f'{nl.brand_name} → {sec_obj.name if sec_obj else selected_assignment.section_id} · '
            f'score {int(round(selected_assignment.score))}</div>',
            unsafe_allow_html=True,
        )

        # Blurb editor
        st.markdown(f'<div class="label">blurb · {nl.voice_skill}</div>', unsafe_allow_html=True)
        initial_blurb = (decision.edited_blurb if decision and decision.edited_blurb else blurb.get("blurb", ""))
        editor_key = f"edit_{selected_scored.story.url}_{selected_nl_for_detail}"
        edited = st.text_area(
            "blurb",
            value=initial_blurb,
            height=200,
            key=editor_key,
            label_visibility="collapsed",
        )

        # Word count vs target
        wc = len(edited.split())
        in_range = sec_obj and (sec_obj.min_words <= wc <= sec_obj.max_words)
        wc_class = "wc ok" if in_range else ("wc bad" if sec_obj else "wc")
        target = f"{sec_obj.min_words}–{sec_obj.max_words}" if sec_obj else "—"
        check = "✓" if in_range else "⚠"
        st.markdown(
            f'<div class="{wc_class}">{wc} words {check} · target {target} · '
            f'{int(blurb.get("minute_read", 5))} min read</div>',
            unsafe_allow_html=True,
        )

        # Action buttons
        ab1, ab2, ab3 = st.columns([1, 1, 1])
        with ab1:
            st.markdown('<div class="approve">', unsafe_allow_html=True)
            if st.button("✓ approve", key="act_approve", use_container_width=True):
                dec.upsert(
                    ss.decisions, selected_scored.story.url, selected_nl_for_detail,
                    status=dec.APPROVED,
                    edited_blurb=edited if edited != blurb.get("blurb", "") else "",
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with ab2:
            st.markdown('<div class="reject">', unsafe_allow_html=True)
            if st.button("✗ reject", key="act_reject", use_container_width=True):
                dec.upsert(
                    ss.decisions, selected_scored.story.url, selected_nl_for_detail,
                    status=dec.REJECTED,
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with ab3:
            if st.button("↺ reset", key="act_reset", use_container_width=True):
                dec.upsert(
                    ss.decisions, selected_scored.story.url, selected_nl_for_detail,
                    status=dec.PENDING, edited_blurb="",
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()

        # Auto-save edits
        if edited and edited != initial_blurb and edited != blurb.get("blurb", ""):
            dec.upsert(
                ss.decisions, selected_scored.story.url, selected_nl_for_detail,
                edited_blurb=edited,
            )
            dec.save(selected_date, ss.decisions)

        # Cross-assignments
        if len(selected_scored.assignments) > 1:
            st.markdown('<div class="label">also in</div>', unsafe_allow_html=True)
            cross_html = []
            for a in selected_scored.assignments:
                if a.newsletter == selected_nl_for_detail:
                    continue
                d2 = ss.decisions.get((selected_scored.story.url, a.newsletter))
                if d2 and d2.status == dec.APPROVED:
                    cls, gly = "ok", "✓"
                elif d2 and d2.status == dec.REJECTED:
                    cls, gly = "no", "✗"
                else:
                    cls, gly = "", "●"
                cross_html.append(
                    f'<a href="?nl={a.newsletter}&story={urllib.parse.quote(selected_scored.story.url)}&nl_detail={a.newsletter}" '
                    f'target="_self" style="text-decoration:none;">'
                    f'<span class="chip {cls}">{a.newsletter.replace("tldr_", "")} {gly} ({int(round(a.score))})</span>'
                    f'</a>'
                )
            st.markdown("".join(cross_html), unsafe_allow_html=True)

        # Reasoning
        if selected_scored.reasoning:
            st.markdown('<div class="label">why (model)</div>', unsafe_allow_html=True)
            st.markdown(f'<p class="why">{selected_scored.reasoning}</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Bottom: issue preview + exports
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("issue preview · tldr exact format", expanded=False):
    preview_nl = ss.selected_nl if ss.selected_nl and ss.selected_nl != CROSS_KEY else default_newsletter_id()
    nl_obj = nls.get(preview_nl)
    if nl_obj is None:
        st.markdown('<div class="preview-empty">select a newsletter</div>', unsafe_allow_html=True)
    else:
        merged: dict[str, dict] = {}
        for s in scored_all:
            a = s.for_newsletter(preview_nl)
            if not a:
                continue
            d = ss.decisions.get((s.story.url, preview_nl))
            if d and d.status == dec.REJECTED:
                continue
            base = blurbs.get((s.story.url, preview_nl), {}).copy()
            if d and d.edited_blurb:
                base["blurb"] = d.edited_blurb
            if base:
                merged[s.story.url] = base

        issue_text = render_tldr(scored_all, merged, preview_nl, selected_date)
        if merged:
            st.markdown(f'<div class="preview">{issue_text}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="preview-empty">no blurbs generated for {nl_obj.brand_name} yet</div>', unsafe_allow_html=True)

        ex1, ex2, _ = st.columns([1, 1, 4])
        with ex1:
            st.markdown('<div class="download">', unsafe_allow_html=True)
            st.download_button(
                "↓ this issue",
                data=issue_text,
                file_name=f"{preview_nl}-{selected_date}.txt",
                mime="text/plain",
                use_container_width=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)
        with ex2:
            bundle_parts: list[str] = [f"TLDR family bundle — {selected_date}\n"]
            for nid in nl_ids:
                m: dict[str, dict] = {}
                for s in scored_all:
                    a = s.for_newsletter(nid)
                    if not a:
                        continue
                    d2 = ss.decisions.get((s.story.url, nid))
                    if d2 and d2.status == dec.REJECTED:
                        continue
                    base = blurbs.get((s.story.url, nid), {}).copy()
                    if d2 and d2.edited_blurb:
                        base["blurb"] = d2.edited_blurb
                    if base:
                        m[s.story.url] = base
                if not m:
                    continue
                bundle_parts.append(f"\n{'='*60}\n{nls[nid].brand_name}\n{'='*60}\n")
                bundle_parts.append(render_tldr(scored_all, m, nid, selected_date))
            bundle_text = "\n".join(bundle_parts)
            st.markdown('<div class="download">', unsafe_allow_html=True)
            st.download_button(
                "↓ family bundle",
                data=bundle_text,
                file_name=f"tldr-family-{selected_date}.txt",
                mime="text/plain",
                use_container_width=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)
