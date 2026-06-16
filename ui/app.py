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
from datetime import date as _date
from datetime import datetime
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

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .block-container { padding: 1.0rem 1.25rem 5rem; max-width: 1600px; }
    [data-testid="stHeader"] { display: none; }
    [data-testid="stToolbar"] { display: none; }

    /* Inter — applied via inheritance so icon fonts (Material Icons used by
       Streamlit's expander chevron, selectbox arrows, etc.) keep working. */
    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    /* explicit elements that don't inherit form-family by default */
    button, input, textarea, select,
    .stMarkdown, .stMarkdown p, .stMarkdown div, .stMarkdown span,
    .stMarkdown li, .stMarkdown a, .stMarkdown h1, .stMarkdown h2,
    .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
    [data-testid="stMarkdownContainer"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    /* mono where it adds clarity */
    .num, .chip, code, pre, .preview, .formula, .score-tag {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
    }

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

    /* ─── Story rows (anchor links; flexbox with min-width:0 on title) ─── */
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
    a.row .ftr { font-size: 10.5px; color: var(--text-mute); margin-top: 4px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
    a.row .date-tag { color: var(--text-mute); font-size: 10.5px; }
    a.row .date-tag::after { content: " · "; color: var(--border-strong); margin-left: 2px; }
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

    /* ─── Detail pane — clear hierarchy ─── */
    .detail-empty {
        color: var(--text-mute); font-size: 12px; padding: 24px 0;
        border: 1px dashed var(--border); border-radius: 6px;
        text-align: center;
    }

    /* H1 — story title */
    .d-title {
        font-size: 26px;
        font-weight: 700;
        line-height: 1.2;
        margin: 0 0 14px;
        color: var(--text);
        letter-spacing: -0.018em;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    /* H2 — subtitle (source · score · newsletter), flex with real gaps */
    .d-meta {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin: 0 0 32px;
        font-size: 13px;
        color: var(--text-dim);
        font-family: 'Inter', sans-serif;
    }
    .d-meta a.src-link {
        color: var(--accent);
        text-decoration: none;
        font-weight: 500;
        font-size: 13px;
    }
    .d-meta a.src-link:hover { text-decoration: underline; }
    .d-meta .badge {
        font-size: 11.5px;
        padding: 3px 8px;
        border-radius: 4px;
        background: var(--surface);
        border: 1px solid var(--border);
        color: var(--text-dim);
        font-family: 'Inter', sans-serif;
    }
    .d-meta .badge.score-badge {
        color: var(--text);
        font-weight: 600;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    /* H3 — section labels (proper subsubtitle, NOT tiny caption) */
    .d-label {
        font-size: 11.5px;
        font-weight: 700;
        letter-spacing: 0.1em;
        color: var(--text-mute);
        text-transform: uppercase;
        margin: 28px 0 10px;
        font-family: 'Inter', sans-serif;
    }
    /* Body — section content (regular Inter, smaller than nothing else but the label) */
    .d-body {
        font-size: 14px;
        color: var(--text-dim);
        line-height: 1.6;
        margin: 0;
        font-family: 'Inter', sans-serif;
    }
    .d-body b { color: var(--text); font-weight: 600; }

    /* Word count line */
    .d-wc { font-size: 12px; color: var(--text-mute); margin: 8px 0 18px; font-family: 'Inter', sans-serif; }
    .d-wc.ok { color: var(--ok); }
    .d-wc.bad { color: var(--warn); }

    /* Cross-assignment chips in detail */
    .d-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
    .d-chips a { text-decoration: none; }

    /* ─── Blurb editor — fully transparent, reads like newsletter prose ─── */
    [data-testid="stTextArea"], [data-testid="stTextArea"] > div,
    [data-testid="stTextArea"] [data-baseweb], [data-testid="stTextArea"] [data-baseweb] > div {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stTextArea"] textarea {
        background: transparent !important;
        color: var(--text) !important;
        border: none !important;
        border-left: 2px solid var(--border) !important;
        border-radius: 0 !important;
        padding: 2px 0 2px 16px !important;
        font-size: 15.5px !important;
        line-height: 1.6 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-weight: 400 !important;
        resize: vertical !important;
        min-height: 140px;
        box-shadow: none !important;
        outline: none !important;
    }
    [data-testid="stTextArea"] textarea:hover { border-left-color: var(--text-mute) !important; }
    [data-testid="stTextArea"] textarea:focus {
        border-left-color: var(--accent) !important;
        background: transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* ─── Buttons (default) ─── */
    .stButton button {
        border-radius: 4px; padding: 8px 12px; font-size: 12px; font-weight: 500;
        background: var(--surface); color: var(--text); border: 1px solid var(--border);
        transition: all 0.1s ease;
        height: 38px;
    }
    .stButton button:hover { background: var(--surface-hi); border-color: var(--border-strong); color: var(--text); }
    .stDownloadButton button { color: var(--text); border-color: var(--border); background: var(--surface); height: 38px; padding: 8px 12px; font-size: 12px; font-weight: 500; border-radius: 4px; }
    .stDownloadButton button:hover { background: var(--surface-hi); border-color: var(--border-strong); }

    /* ─── Action row (approve / reject / reset) ─── */
    /* The sentinel .action-row-anchor div sits immediately before the row of
       three columns. We colour the buttons via column position inside the
       horizontal block that follows the sentinel. */
    .action-row-anchor + div [data-testid="column"]:nth-of-type(1) .stButton button {
        background: var(--ok-soft); color: #6ee7b7; border-color: #065f46;
    }
    .action-row-anchor + div [data-testid="column"]:nth-of-type(1) .stButton button:hover {
        background: #065f46; color: #fafafa; border-color: #047857;
    }
    .action-row-anchor + div [data-testid="column"]:nth-of-type(2) .stButton button {
        background: var(--no-soft); color: #fca5a5; border-color: #991b1b;
    }
    .action-row-anchor + div [data-testid="column"]:nth-of-type(2) .stButton button:hover {
        background: #991b1b; color: #fafafa; border-color: #b91c1c;
    }
    /* Streamlit also nests stHorizontalBlock; cover that selector variant too */
    .action-row-anchor + [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(1) .stButton button {
        background: var(--ok-soft); color: #6ee7b7; border-color: #065f46;
    }
    .action-row-anchor + [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(1) .stButton button:hover {
        background: #065f46; color: #fafafa; border-color: #047857;
    }
    .action-row-anchor + [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(2) .stButton button {
        background: var(--no-soft); color: #fca5a5; border-color: #991b1b;
    }
    .action-row-anchor + [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(2) .stButton button:hover {
        background: #991b1b; color: #fafafa; border-color: #b91c1c;
    }
    /* Ensure every column's button area has zero top-margin so they baseline-align. */
    .action-row-anchor + div [data-testid="column"] .stButton,
    .action-row-anchor + [data-testid="stHorizontalBlock"] [data-testid="column"] .stButton {
        margin-top: 0 !important;
    }

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

    /* ─── Top-bar tab nav (Curate / Backtest) ─── */
    .view-tabs { display: flex; gap: 4px; align-items: center; margin: 0; padding: 0; }
    .view-tabs a {
        display: inline-block; padding: 6px 14px; border-radius: 5px;
        font-size: 13px; font-weight: 500; color: var(--text-dim);
        text-decoration: none; border: 1px solid transparent;
    }
    .view-tabs a:hover { background: var(--surface); color: var(--text); }
    .view-tabs a.active {
        background: var(--accent-soft); color: var(--text);
        border-color: var(--accent); font-weight: 600;
    }

    /* ─── Backtest dashboard ─── */
    .bt-hero {
        background: linear-gradient(135deg, var(--surface) 0%, #1a2030 100%);
        border: 1px solid var(--border-strong);
        border-radius: 8px;
        padding: 22px 26px;
        margin: 6px 0 22px;
    }
    .bt-hero h2 { font-size: 14px; font-weight: 600; color: var(--text-dim);
        text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 6px; }
    .bt-hero .lede { font-size: 22px; font-weight: 600; color: var(--text); margin: 0 0 12px; letter-spacing: -0.01em; }
    .bt-hero .stat-row { display: flex; gap: 32px; flex-wrap: wrap; }
    .bt-hero .stat .num { font-size: 28px; font-weight: 700; color: var(--accent); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .bt-hero .stat .label { font-size: 11px; color: var(--text-mute); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }

    table.bt-table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0 24px; }
    table.bt-table th {
        text-align: left; padding: 10px 12px; color: var(--text-mute);
        font-weight: 600; text-transform: uppercase; font-size: 10px;
        letter-spacing: 0.08em; border-bottom: 1px solid var(--border-strong);
    }
    table.bt-table td {
        padding: 10px 12px; border-bottom: 1px solid var(--border);
        vertical-align: middle;
    }
    table.bt-table td.name { color: var(--text); font-weight: 500; }
    table.bt-table td.recall {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-weight: 600; text-align: right;
    }
    table.bt-table td.recall.hi { color: var(--ok); }
    table.bt-table td.recall.mid { color: var(--warn); }
    table.bt-table td.recall.lo { color: var(--text-mute); }
    table.bt-table td.spark {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        color: var(--accent); letter-spacing: 1px;
    }
    table.bt-table td.na { color: var(--text-mute); font-style: italic; }
    table.bt-table tr:hover { background: var(--surface); }

    .bt-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin-top: 8px; }
    .bt-compare .col-head {
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em;
        color: var(--text-mute); font-weight: 600; margin-bottom: 10px;
        padding-bottom: 8px; border-bottom: 1px solid var(--border-strong);
    }
    .bt-item {
        padding: 9px 0; border-bottom: 1px solid var(--border);
        font-size: 13px; line-height: 1.4; display: flex; gap: 10px; align-items: baseline;
    }
    .bt-item .idx {
        flex: 0 0 22px; text-align: right; color: var(--text-mute);
        font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .bt-item .marker {
        flex: 0 0 18px; font-size: 14px; line-height: 1;
    }
    .bt-item .marker.hit { color: var(--ok); }
    .bt-item .marker.miss { color: var(--no); }
    .bt-item .title { flex: 1 1 auto; color: var(--text); min-width: 0; word-wrap: break-word; }
    .bt-item.matched { background: rgba(16, 185, 129, 0.06); margin: 0 -8px; padding: 9px 8px; border-radius: 4px; }
    .bt-item.matched + .bt-item:not(.matched) { margin-top: 0; }
    .bt-item .score {
        flex: 0 0 28px; text-align: right;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 11px; color: var(--text);
    }
    .bt-empty {
        padding: 40px 20px; text-align: center; color: var(--text-mute);
        font-size: 13px; border: 1px dashed var(--border); border-radius: 6px;
    }
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


def _mtime(p: Path) -> float:
    """File mtime as a cache-key. Returns 0 if the file doesn't exist."""
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0


@st.cache_data(show_spinner=False)
def _load_scored_cached(date: str, _mtime_key: float) -> list[dict]:
    """JSONL → list of dicts. Cached by file mtime so updates invalidate
    automatically and clicks don't re-parse 300+ entries from disk."""
    return read_jsonl(SCORED_DIR / f"{date}.jsonl")


@st.cache_data(show_spinner=False)
def _load_blurbs_cached(date: str, _mtime_key: float) -> dict[str, dict]:
    """Cached blurbs loader. Returns a dict keyed by 'url||newsletter' string
    because tuple keys aren't hashable through st.cache_data's pickle layer."""
    p = BLURBS_DIR / f"{date}.jsonl"
    if not p.exists():
        return {}
    out: dict[str, dict] = {}
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            b = json.loads(line)
            out[f"{b['story_url']}||{b['newsletter']}"] = b
    return out


def _load_blurbs(date: str) -> dict[tuple[str, str], dict]:
    """Public API: returns the tuple-keyed dict the rest of the app expects."""
    raw = _load_blurbs_cached(date, _mtime(BLURBS_DIR / f"{date}.jsonl"))
    out: dict[tuple[str, str], dict] = {}
    for k, v in raw.items():
        url, nl = k.split("||", 1)
        out[(url, nl)] = v
    return out


def _counts_pipeline(date: str) -> dict[str, int]:
    return {
        "raw": len(read_jsonl(RAW_DIR / f"{date}.jsonl")),
        "deduped": len(read_jsonl(DEDUP_DIR / f"{date}.jsonl")),
        "scored": len(read_jsonl(SCORED_DIR / f"{date}.jsonl")),
        "blurbed": len(read_jsonl(BLURBS_DIR / f"{date}.jsonl")) if (BLURBS_DIR / f"{date}.jsonl").exists() else 0,
    }


def _short_date(iso: str, target_date: str) -> str:
    """Absolute publication date, formatted as 'Jun 14' (current year) or
    'Jun 14, 2025' if older than the current year. Year inferred from the
    parsed timestamp."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    try:
        target = datetime.fromisoformat(target_date).date()
        target_year = target.year
    except Exception:
        target_year = _date.today().year
    if dt.year == target_year:
        return dt.strftime("%b %-d")
    return dt.strftime("%b %-d, %Y")


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

# Top-level view: curate (default) or backtest. Persists in URL for direct linking.
current_view = qp.get("view", "curate")
if current_view not in ("curate", "backtest"):
    current_view = "curate"

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

# Brand + tab nav row
brand_col, tabs_col, _ = st.columns([2, 4, 6])
with brand_col:
    st.markdown('<h1 class="brand">tldr pipeline</h1>', unsafe_allow_html=True)
with tabs_col:
    curate_active = " active" if current_view == "curate" else ""
    backtest_active = " active" if current_view == "backtest" else ""
    st.markdown(
        f'<div class="view-tabs">'
        f'<a href="?view=curate" target="_self" class="{curate_active.strip()}">Curate</a>'
        f'<a href="?view=backtest" target="_self" class="{backtest_active.strip()}">Backtest</a>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST view — early return
# ─────────────────────────────────────────────────────────────────────────────
if current_view == "backtest":
    from common import backtest as bt

    backtest_dates = bt.all_cached_dates()
    if not backtest_dates:
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown(
            '<div class="bt-empty">No backtest data yet. The next cron run will populate it. '
            'You can force one now with: <code>tldr backtest_cache</code></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # Hero: aggregate recall@10 across all newsletters, latest day with predictions.
    # We skip days where we have a TLDR archive but zero predictions on our side
    # (pre-cron-launch dates), because they're 0/N by definition and just drag the
    # number down for free.
    latest_date = backtest_dates[0]
    latest_results = [bt.load_cached(nid, latest_date) for nid in nl_ids]
    latest_results = [r for r in latest_results if r is not None and r.available and r.predictions]

    total_tldr = sum(len(r.tldr_titles) for r in latest_results)
    total_hits_10 = sum(r.hits_at.get(10, 0) for r in latest_results)
    total_hits_25 = sum(r.hits_at.get(25, 0) for r in latest_results)
    total_hits_50 = sum(r.hits_at.get(50, 0) for r in latest_results)
    # "Any" tier: largest K we have, which is whatever the cache stored as the
    # all-predictions bucket. The compute_backtest function stores n_pred as the
    # last key — find the biggest K available across these results.
    max_k = max((max(r.hits_at.keys()) for r in latest_results if r.hits_at), default=0)
    total_hits_all = sum(r.hits_at.get(max_k, 0) for r in latest_results) if max_k else 0
    recall_10 = (total_hits_10 / total_tldr * 100) if total_tldr else 0
    recall_25 = (total_hits_25 / total_tldr * 100) if total_tldr else 0
    recall_50 = (total_hits_50 / total_tldr * 100) if total_tldr else 0
    recall_all = (total_hits_all / total_tldr * 100) if total_tldr else 0

    hero = (
        f'<div class="bt-hero">'
        f'<h2>How well we match TLDR</h2>'
        f'<p class="lede">{latest_date} · {len(latest_results)} newsletters compared · {total_tldr} stories TLDR actually published</p>'
        f'<div class="stat-row">'
        f'<div class="stat"><div class="num">{recall_10:.0f}%</div><div class="label">recall @ top 10</div></div>'
        f'<div class="stat"><div class="num">{recall_25:.0f}%</div><div class="label">recall @ top 25</div></div>'
        f'<div class="stat"><div class="num">{recall_50:.0f}%</div><div class="label">recall @ top 50</div></div>'
        f'<div class="stat"><div class="num" style="color:var(--text);">{recall_all:.0f}%</div><div class="label">recall @ any (full pool)</div></div>'
        f'</div></div>'
        f'<p style="color:var(--text-mute);font-size:12px;margin:-12px 0 22px;line-height:1.5;">'
        f'<b style="color:var(--text-dim);">Recall</b> = "of the stories TLDR actually published, how many did we surface in our top N?" '
        f'Matches via title-embedding similarity ≥ 0.72 (so "OpenAI Acquires Ona" matches "OpenAI buys long-agent startup Ona"). '
        f'Low numbers point to source coverage gaps — TLDR sources heavily from X, LinkedIn, and inside-baseball Substacks we haven\'t wired up yet.'
        f'</p>'
    )
    st.markdown(hero, unsafe_allow_html=True)

    # Per-newsletter table with 7-day sparkline
    SPARK_CHARS = "▁▂▃▄▅▆▇█"
    def _spark(values: list[float]) -> str:
        if not values:
            return ""
        out = []
        for v in values:
            idx = max(0, min(len(SPARK_CHARS) - 1, int(v * len(SPARK_CHARS))))
            out.append(SPARK_CHARS[idx])
        return "".join(out)

    rows_html = []
    for nid in nl_ids:
        history = bt.load_all_for(nid, last_n_days=7)
        # Filter to days we actually have predictions for — otherwise the
        # "TLDR title denominator" gets counted but our hits are 0 by definition.
        history = [r for r in history if r.predictions]
        if not history:
            rows_html.append(
                f'<tr><td class="name">{nls[nid].brand_name}</td>'
                f'<td colspan="4" class="na">no comparable issue yet (TLDR not published, or pipeline didn\'t run that day)</td></tr>'
            )
            continue
        # Aggregate recall over the loaded history
        agg_hits = {k: sum(r.hits_at.get(k, 0) for r in history) for k in (10, 25, 50)}
        # "all" tier uses each history entry's own largest K (varies by day)
        agg_hits_all = sum(
            r.hits_at.get(max(r.hits_at.keys()), 0) if r.hits_at else 0
            for r in history
        )
        agg_tldr = sum(len(r.tldr_titles) for r in history)
        if agg_tldr == 0:
            continue
        r10 = agg_hits[10] / agg_tldr
        r25 = agg_hits[25] / agg_tldr
        r50 = agg_hits[50] / agg_tldr
        r_all = agg_hits_all / agg_tldr
        spark = _spark([r.recall_at.get(10, 0) for r in history])

        def _cls(v: float) -> str:
            if v >= 0.5: return "recall hi"
            if v >= 0.25: return "recall mid"
            return "recall lo"

        rows_html.append(
            f'<tr>'
            f'<td class="name">{nls[nid].brand_name}</td>'
            f'<td class="{_cls(r10)}">{r10*100:.0f}%</td>'
            f'<td class="{_cls(r25)}">{r25*100:.0f}%</td>'
            f'<td class="{_cls(r50)}">{r50*100:.0f}%</td>'
            f'<td class="{_cls(r_all)}">{r_all*100:.0f}%</td>'
            f'<td class="spark">{spark}</td>'
            f'</tr>'
        )

    st.markdown(
        '<table class="bt-table">'
        '<thead><tr><th>Newsletter</th><th style="text-align:right;">R@10</th>'
        '<th style="text-align:right;">R@25</th><th style="text-align:right;">R@50</th>'
        '<th style="text-align:right;">R@all</th>'
        '<th>Last 7 days (R@10)</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table>',
        unsafe_allow_html=True,
    )

    # Detailed compare: pick a (date, newsletter) to inspect
    st.markdown('<h3 style="font-size:14px;font-weight:600;color:var(--text);margin:24px 0 12px;">'
                'Today vs published — side by side</h3>', unsafe_allow_html=True)

    bt_cols = st.columns([1, 1, 4])
    with bt_cols[0]:
        bt_date = st.selectbox("date", backtest_dates, index=0, key="bt_date", label_visibility="collapsed")
    with bt_cols[1]:
        bt_nl = st.selectbox(
            "newsletter", nl_ids,
            format_func=lambda x: nls[x].brand_name,
            key="bt_nl", label_visibility="collapsed",
        )

    detail = bt.load_cached(bt_nl, bt_date)
    if detail is None or not detail.available:
        st.markdown(
            f'<div class="bt-empty">No published TLDR {nls[bt_nl].brand_name} issue for {bt_date} '
            '(or the archive page returned 404).</div>',
            unsafe_allow_html=True,
        )
    elif not detail.predictions:
        st.markdown(
            '<div class="bt-empty">We have no predictions for this date — '
            'the pipeline didn\'t run, or no stories scored above the threshold.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Build left column: TLDR's published stories with hit/miss marker
        left_items = []
        for i, t in enumerate(detail.tldr_titles):
            hit = detail.tldr_matched[i] if i < len(detail.tldr_matched) else False
            marker = '<span class="marker hit">✓</span>' if hit else '<span class="marker miss">✗</span>'
            left_items.append(
                f'<div class="bt-item{" matched" if hit else ""}">'
                f'<span class="idx">{i+1}</span>{marker}'
                f'<span class="title">{t}</span>'
                f'</div>'
            )

        # Right column: our top predictions with score and match indicator
        right_items = []
        for p in detail.predictions:
            matched = p.matched_tldr_idx is not None
            marker = '<span class="marker hit">✓</span>' if matched else '<span class="marker miss">·</span>'
            right_items.append(
                f'<div class="bt-item{" matched" if matched else ""}">'
                f'<span class="idx">{p.rank}</span>{marker}'
                f'<span class="title">{p.title}</span>'
                f'<span class="score">{int(round(p.score))}</span>'
                f'</div>'
            )

        st.markdown(
            f'<div class="bt-compare">'
            f'<div><div class="col-head">TLDR {nls[bt_nl].brand_name.replace("TLDR ", "").replace("TLDR", "")} actually published ({len(detail.tldr_titles)})</div>'
            f'{"".join(left_items)}</div>'
            f'<div><div class="col-head">Our top {len(detail.predictions)} predictions</div>'
            f'{"".join(right_items)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        max_k_d = max(detail.hits_at.keys()) if detail.hits_at else 0
        all_hits = detail.hits_at.get(max_k_d, 0)
        st.markdown(
            f'<p style="color:var(--text-mute);font-size:11px;margin-top:14px;">'
            f'Hits at @10 / @25 / @50 / @any: '
            f'<b style="color:var(--text);font-family:ui-monospace,monospace;">'
            f'{detail.hits_at.get(10,0)} · {detail.hits_at.get(25,0)} · '
            f'{detail.hits_at.get(50,0)} · {all_hits}</b> '
            f'of {len(detail.tldr_titles)} TLDR titles · '
            f'pool size {len(detail.predictions)} predictions · '
            f'similarity threshold 0.72 · cached {detail.fetched_at[:19]}'
            f'</p>',
            unsafe_allow_html=True,
        )

    st.stop()  # do NOT render the curate view


# ─────────────────────────────────────────────────────────────────────────────
# CURATE view (default) — original three-pane layout below
# ─────────────────────────────────────────────────────────────────────────────
tb1, tb2, tb3, tb4 = st.columns([2, 3, 4, 3])
with tb1:
    st.markdown('<div style="height:1px;"></div>', unsafe_allow_html=True)
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
scored_all = [
    ScoredStory.from_dict(d)
    for d in _load_scored_cached(selected_date, _mtime(SCORED_DIR / f"{selected_date}.jsonl"))
]
blurbs = _load_blurbs(selected_date)

# Apply search filter
search_q = (ss.get("search") or "").strip().lower()
if search_q:
    scored_all = [s for s in scored_all if search_q in s.story.title.lower()]

# nl_shown = the count of stories actually displayed for each newsletter
# (capped by per-section target_count). nl_candidates = total stories that
# scored above MIN_ASSIGNMENT_SCORE for that newsletter (informational).
nl_shown: dict[str, int] = {nid: 0 for nid in nl_ids}
nl_candidates: dict[str, int] = {nid: 0 for nid in nl_ids}
nl_decided: dict[str, int] = {nid: 0 for nid in nl_ids}
cross_set: set[str] = set()

for s in scored_all:
    if len(s.assignments) > 1:
        cross_set.add(s.story.url)
    for a in s.assignments:
        if a.newsletter in nl_candidates:
            nl_candidates[a.newsletter] += 1

# Compute "shown" counts per newsletter by replaying top_per_section.
for nid in nl_ids:
    by_sec = top_per_section(scored_all, nid)
    for sec_id, stories in by_sec.items():
        nl_shown[nid] += len(stories)
        for s in stories:
            d = ss.decisions.get((s.story.url, nid))
            if d and d.is_decided():
                nl_decided[nid] += 1

# Auto-select first newsletter on first load (prefer one with assignments)
if ss.selected_nl is None or ss.selected_nl not in nl_ids + [CROSS_KEY]:
    for nid in nl_ids:
        if nl_shown[nid] > 0:
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
        total = nl_shown[nid]
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
    target_nl: str,
    rail_nl: str,
    chips_html: str,
    date_text: str,
    status_cls: str,
    glyph: str,
    is_sel: bool,
) -> str:
    """Row is an anchor link with query params. Click → Streamlit reads
    query_params on rerun and updates the detail pane. Cached data loaders
    make the rerun feel ~5x faster than before but it's still a rerun."""
    qs_params = {"nl": rail_nl, "story": story_url, "nl_detail": target_nl}
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in qs_params.items())
    sel_cls = " sel" if is_sel else ""
    title_safe = title.replace("<", "&lt;").replace(">", "&gt;")
    date_html = f'<span class="num date-tag">{date_text}</span>' if date_text else ""
    return (
        f'<a class="row{sel_cls}" href="?{qs}" target="_self">'
        f'<span class="num rank">{rank}</span>'
        f'<span class="num score">{int(round(score))}</span>'
        f'<span class="main">'
        f'<span class="title">{title_safe}</span>'
        f'<span class="ftr">{date_html}{chips_html}</span>'
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
                date_text = _short_date(s.story.published_at, selected_date)
                parts.append(_build_row_html(
                    rank=rank, score=primary.score, title=s.story.title,
                    story_url=s.story.url, target_nl=primary.newsletter, rail_nl=CROSS_KEY,
                    chips_html=chips_html, date_text=date_text,
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
                    date_text = _short_date(s.story.published_at, selected_date)
                    is_sel = (ss.selected_url == s.story.url and ss.selected_nl_for_detail == nl.id)
                    parts.append(_build_row_html(
                        rank=rank, score=a.score, title=s.story.title,
                        story_url=s.story.url, target_nl=nl.id, rail_nl=nl.id,
                        chips_html=chips_html, date_text=date_text,
                        status_cls=status_cls, glyph=glyph, is_sel=is_sel,
                    ))

    parts.append("</div>")
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
        nl = nls[selected_nl_for_detail]
        sec_obj = nl.section(selected_assignment.section_id)
        blurb = blurbs.get((selected_scored.story.url, selected_nl_for_detail), {})
        decision = ss.decisions.get((selected_scored.story.url, selected_nl_for_detail))

        from urllib.parse import urlparse
        domain = urlparse(selected_scored.story.url).netloc.lstrip("www.") or selected_scored.story.source

        title_safe = selected_scored.story.title.replace("<", "&lt;").replace(">", "&gt;")
        section_label = sec_obj.name if sec_obj else selected_assignment.section_id

        # Title + meta line as one HTML blob so the flex meta layout actually applies.
        st.markdown(
            f'<h1 class="d-title">{title_safe}</h1>'
            f'<div class="d-meta">'
            f'<a class="src-link" href="{selected_scored.story.url}" target="_blank" rel="noopener">{domain} ↗</a>'
            f'<span class="badge score-badge">score {int(round(selected_assignment.score))}</span>'
            f'<span class="badge">{nl.brand_name} · {section_label}</span>'
            f'</div>'
            f'<div class="d-label">newsletter summary</div>',
            unsafe_allow_html=True,
        )

        # Editable blurb (transparent textarea)
        initial_blurb = (decision.edited_blurb if decision and decision.edited_blurb else blurb.get("blurb", ""))
        editor_key = f"edit_{selected_scored.story.url}_{selected_nl_for_detail}"
        edited = st.text_area(
            "blurb",
            value=initial_blurb,
            height=180,
            key=editor_key,
            label_visibility="collapsed",
        )

        # Word count line
        wc = len(edited.split())
        in_range = sec_obj and (sec_obj.min_words <= wc <= sec_obj.max_words)
        wc_class = "d-wc ok" if in_range else ("d-wc bad" if sec_obj else "d-wc")
        target = f"{sec_obj.min_words}–{sec_obj.max_words}" if sec_obj else "—"
        check = "✓" if in_range else "⚠"
        st.markdown(
            f'<div class="{wc_class}">{wc} words {check} · target {target} · '
            f'{int(blurb.get("minute_read", 5))} min read</div>',
            unsafe_allow_html=True,
        )

        # Action buttons — wrapped in a sentinel div so column-position CSS works.
        st.markdown('<div class="action-row-anchor"></div>', unsafe_allow_html=True)
        ab1, ab2, ab3 = st.columns([1, 1, 1], gap="small")
        with ab1:
            if st.button("✓ approve", key="act_approve", use_container_width=True):
                dec.upsert(
                    ss.decisions, selected_scored.story.url, selected_nl_for_detail,
                    status=dec.APPROVED,
                    edited_blurb=edited if edited != blurb.get("blurb", "") else "",
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()
        with ab2:
            if st.button("✗ reject", key="act_reject", use_container_width=True):
                dec.upsert(
                    ss.decisions, selected_scored.story.url, selected_nl_for_detail,
                    status=dec.REJECTED,
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()
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

        # Cross-assignments + why-it-matters in one HTML blob so styles apply consistently.
        bottom_parts: list[str] = []

        if len(selected_scored.assignments) > 1:
            bottom_parts.append('<div class="d-label">also in</div>')
            bottom_parts.append('<div class="d-chips">')
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
                href = (
                    f"?nl={urllib.parse.quote(a.newsletter)}"
                    f"&story={urllib.parse.quote(selected_scored.story.url)}"
                    f"&nl_detail={urllib.parse.quote(a.newsletter)}"
                )
                bottom_parts.append(
                    f'<a href="{href}" target="_self">'
                    f'<span class="chip {cls}">{a.newsletter.replace("tldr_", "")} {gly} {int(round(a.score))}</span>'
                    f'</a>'
                )
            bottom_parts.append('</div>')

        if selected_scored.reasoning:
            reasoning_safe = selected_scored.reasoning.replace("<", "&lt;").replace(">", "&gt;")
            bottom_parts.append('<div class="d-label">why it matters</div>')
            bottom_parts.append(f'<p class="d-body">{reasoning_safe}</p>')

        if bottom_parts:
            st.markdown("".join(bottom_parts), unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Bottom: download buttons + scoring-methodology expander
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

# Compute exports (kept available even though the preview expander is gone)
preview_nl_id = ss.selected_nl if ss.selected_nl and ss.selected_nl != CROSS_KEY else default_newsletter_id()
preview_nl_obj = nls.get(preview_nl_id)


def _merged_blurbs_for(nid: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in scored_all:
        a = s.for_newsletter(nid)
        if not a:
            continue
        d = ss.decisions.get((s.story.url, nid))
        if d and d.status == dec.REJECTED:
            continue
        base = blurbs.get((s.story.url, nid), {}).copy()
        if d and d.edited_blurb:
            base["blurb"] = d.edited_blurb
        if base:
            out[s.story.url] = base
    return out


# Issue text for the currently selected newsletter
if preview_nl_obj is not None:
    issue_text = render_tldr(scored_all, _merged_blurbs_for(preview_nl_id), preview_nl_id, selected_date)
else:
    issue_text = ""

# Family bundle
bundle_parts: list[str] = [f"TLDR family bundle — {selected_date}\n"]
for nid in nl_ids:
    merged = _merged_blurbs_for(nid)
    if not merged:
        continue
    bundle_parts.append(f"\n{'='*60}\n{nls[nid].brand_name}\n{'='*60}\n")
    bundle_parts.append(render_tldr(scored_all, merged, nid, selected_date))
bundle_text = "\n".join(bundle_parts)

ex1, ex2, _ = st.columns([1, 1, 4])
with ex1:
    st.markdown('<div class="download">', unsafe_allow_html=True)
    st.download_button(
        f"↓ {preview_nl_id.replace('tldr_','')} issue",
        data=issue_text,
        file_name=f"{preview_nl_id}-{selected_date}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not issue_text,
    )
    st.markdown('</div>', unsafe_allow_html=True)
with ex2:
    st.markdown('<div class="download">', unsafe_allow_html=True)
    st.download_button(
        "↓ family bundle (all newsletters)",
        data=bundle_text,
        file_name=f"tldr-family-{selected_date}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

with st.expander("how is the score calculated?", expanded=False):
    st.markdown(
        """
        <div class="score-doc">
        <p>Every candidate story is scored <b>0–100</b> against five editorial
        dimensions. The model assigns sub-scores per dimension and combines them
        with the weights below:</p>

        <div class="formula">
          score = 0.30·<b>technical</b> + 0.25·<b>novelty</b> + 0.20·<b>implications</b> + 0.15·<b>credibility</b> + 0.10·<b>mainstream</b>
        </div>

        <table class="rubric">
          <tr><th>Dimension</th><th>Weight</th><th>What it measures</th></tr>
          <tr><td>Technical substance</td><td>30%</td><td>Reproducible detail, real numbers, named approach. A paper with code beats a capability claim.</td></tr>
          <tr><td>Novelty</td><td>25%</td><td>How different from what TLDR readers have already seen this week.</td></tr>
          <tr><td>Broader implications</td><td>20%</td><td>If true / if shipped, how much it changes what a serious reader should do or believe.</td></tr>
          <tr><td>Source credibility</td><td>15%</td><td>First-party blog &gt; trusted secondary (Simon Willison, Import AI) &gt; general tech press &gt; aggregator.</td></tr>
          <tr><td>Mainstream relevance</td><td>10%</td><td>Will this matter to a non-specialist? Lowest weight because TLDR readers are mostly already deep.</td></tr>
        </table>

        <p class="cap"><b>Disqualifiers</b> cap the score at 25: AI-generated thinkpieces, pure hype, content-marketing with no critical distance, sponsored posts, stories already covered in the last 14 days.</p>

        <p class="cap"><b>Newsletter fit</b> is scored separately per newsletter. A story only appears in a newsletter's queue if its per-newsletter score is ≥55 (configurable via <code>MIN_ASSIGNMENT_SCORE</code>).</p>

        <p class="cap">Tie-breakers prefer the original source over aggregators, technical depth over breadth, named authors with track records, fresher stories, and reproducible artifacts.</p>
        </div>

        <style>
        .score-doc { font-size: 13px; color: var(--text-dim); line-height: 1.55; }
        .score-doc p { margin: 0 0 12px; }
        .score-doc b { color: var(--text); font-weight: 600; }
        .score-doc .formula { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; padding: 14px 16px; background: var(--surface); border-left: 2px solid var(--accent); margin: 14px 0 18px; color: var(--text); }
        .score-doc .formula b { color: var(--accent); font-weight: 600; }
        .score-doc table.rubric { width: 100%; border-collapse: collapse; margin: 8px 0 18px; font-size: 12.5px; }
        .score-doc table.rubric th { text-align: left; padding: 8px 10px; color: var(--text-mute); font-weight: 600; text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em; border-bottom: 1px solid var(--border-strong); }
        .score-doc table.rubric td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
        .score-doc table.rubric td:nth-child(2) { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--text); font-weight: 600; white-space: nowrap; width: 60px; }
        .score-doc table.rubric td:first-child { color: var(--text); font-weight: 500; white-space: nowrap; }
        .score-doc .cap { font-size: 12px; color: var(--text-mute); }
        .score-doc code { background: var(--surface); padding: 1px 5px; border-radius: 3px; font-size: 11.5px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
