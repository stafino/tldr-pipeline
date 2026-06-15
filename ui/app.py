"""TLDR pipeline curator UI.

Three-pane layout inspired by Linear's Triage:
- left rail: newsletters with decided/total counts and a Cross-assignments queue
- middle: section-grouped story list for the selected newsletter, sticky headers
- right: selected story detail with inline blurb editor + approve/reject

State persists to data/decisions/<date>.jsonl.
"""

from __future__ import annotations

import json
import sys
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

CROSS_KEY = "__cross__"  # pseudo-newsletter id in the left rail

st.set_page_config(page_title="tldr pipeline", layout="wide", initial_sidebar_state="collapsed")

# ── Styling. Monochrome with a single accent. Mono only where it adds clarity.
st.markdown(
    """
    <style>
    /* Layout */
    .block-container { padding: 1.25rem 1.5rem 4rem; max-width: 1500px; }
    [data-testid="stHeader"] { display: none; }
    /* Reset default monospace globally — let titles render in sans */
    body, .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span,
    button, [data-testid="stButton"] button { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif; }
    /* Mono only for ranks, scores, words, chips, code */
    .num, .chip, code, pre, .preview { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

    /* Custom shell */
    h1.brand { font-size: 16px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
    .topbar { display: flex; align-items: center; gap: 18px; padding: 4px 0 12px; border-bottom: 1px solid #e5e7eb; }
    .pill { font-size: 11px; color: #6b7280; }
    .pill b { color: #111827; font-weight: 600; }

    /* Rail */
    .rail { padding: 8px 0; font-size: 13px; }
    .rail .head { font-size: 10px; letter-spacing: 0.08em; color: #9ca3af; text-transform: uppercase; margin: 8px 0 4px; }
    .rail a { display: flex; justify-content: space-between; padding: 4px 8px; border-radius: 4px; text-decoration: none; color: #111827; line-height: 1.4; }
    .rail a:hover { background: #f3f4f6; }
    .rail a.active { background: #eaf1fb; color: #1f4f8b; font-weight: 600; }
    .rail .count { color: #6b7280; font-size: 11px; }
    .rail a.active .count { color: #1f4f8b; }
    .rail .star { color: #b45309; }

    /* Section header in middle pane */
    .sec { display: flex; align-items: baseline; gap: 8px; padding: 14px 4px 6px; border-bottom: 1px solid #e5e7eb; position: sticky; top: 0; background: white; z-index: 1; }
    .sec h3 { font-size: 13px; font-weight: 600; margin: 0; }
    .sec .meta { font-size: 11px; color: #6b7280; margin-left: auto; }

    /* Story row */
    .row { display: grid; grid-template-columns: 28px 36px 1fr auto; gap: 8px; align-items: baseline; padding: 6px 4px; border-bottom: 1px solid #f3f4f6; cursor: pointer; }
    .row:hover { background: #f9fafb; }
    .row.sel { background: #f0f6ff; }
    .row .rank { color: #9ca3af; font-size: 11px; text-align: right; }
    .row .score { font-size: 11px; color: #111827; font-weight: 600; }
    .row .title { font-size: 13px; line-height: 1.35; color: #111827; }
    .row .ftr { font-size: 10.5px; color: #6b7280; margin-top: 2px; }
    .row .stat { font-size: 14px; color: #9ca3af; }
    .row .stat.ok { color: #047857; }
    .row .stat.no { color: #b91c1c; }
    .row .stat.warn { color: #b45309; }

    /* Chips */
    .chip { display: inline-block; padding: 1px 6px; margin-right: 4px; border-radius: 3px; background: #f1f5f9; color: #475569; font-size: 10.5px; }
    .chip.ok { background: #ecfdf5; color: #065f46; }
    .chip.no { background: #fef2f2; color: #991b1b; }
    .chip.warn { background: #fffbeb; color: #92400e; }

    /* Detail pane */
    .detail h2 { font-size: 14px; font-weight: 600; margin: 0 0 4px; }
    .detail .src { font-size: 11px; color: #6b7280; margin-bottom: 8px; }
    .detail .label { font-size: 10px; letter-spacing: 0.08em; color: #9ca3af; text-transform: uppercase; margin: 10px 0 4px; }
    .detail .why { font-size: 12px; color: #4b5563; line-height: 1.4; }
    .detail .wc { font-size: 11px; color: #6b7280; margin-top: 4px; }
    .detail .wc.bad { color: #b45309; }

    /* Preview */
    .preview { white-space: pre-wrap; font-size: 11.5px; line-height: 1.45; background: #fafafa; padding: 12px; border: 1px solid #eee; border-radius: 4px; max-height: 420px; overflow-y: auto; }

    /* Buttons */
    [data-testid="stButton"] button { border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 500; border: 1px solid #d1d5db; background: white; color: #111827; }
    [data-testid="stButton"] button:hover { background: #f9fafb; border-color: #9ca3af; }
    [data-testid="baseButton-secondary"] { background: white; }
    .approve button { color: #047857; border-color: #a7f3d0; }
    .approve button:hover { background: #ecfdf5; }
    .reject button { color: #b91c1c; border-color: #fecaca; }
    .reject button:hover { background: #fef2f2; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers
def _available_dates() -> list[str]:
    dates: set[str] = set()
    for d in (SCORED_DIR, BLURBS_DIR):
        if d.exists():
            for p in d.glob("*.jsonl"):
                dates.add(p.stem)
    return sorted(dates, reverse=True)


def _load_blurbs(date: str) -> dict[tuple[str, str], dict]:
    """Map (story_url, newsletter) → blurb dict."""
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
        "blurbed": sum(1 for _ in BLURBS_DIR.glob(f"{date}.jsonl")) and len(read_jsonl(BLURBS_DIR / f"{date}.jsonl")) or 0,
    }


def _row_status(decision: dec.Decision | None, blurb: dict, section_min: int, section_max: int) -> str:
    """Status glyph class for the row: ok | no | warn | pending."""
    if decision is None or decision.status == dec.PENDING:
        if blurb.get("needs_review"):
            return "warn"
        wc = int(blurb.get("word_count", 0))
        if wc and not (section_min <= wc <= section_max):
            return "warn"
        return ""
    if decision.status == dec.APPROVED:
        return "ok"
    if decision.status == dec.REJECTED:
        return "no"
    return ""


def _status_glyph(status_class: str) -> str:
    return {"ok": "✓", "no": "✗", "warn": "⚠", "": "●"}.get(status_class, "●")


# ── Session bootstrap
ss = st.session_state
if "selected_url" not in ss:
    ss.selected_url = None
if "selected_nl" not in ss:
    ss.selected_nl = None
if "decisions" not in ss:
    ss.decisions = {}
if "loaded_date" not in ss:
    ss.loaded_date = None


# ── Load data for selected date
dates = _available_dates()
if not dates:
    st.markdown('<h1 class="brand">tldr pipeline</h1>', unsafe_allow_html=True)
    st.write("")
    st.markdown(
        "No scored runs yet. Run `tldr refresh` to populate today, or `DATE=2026-06-12 tldr refresh` for a specific date."
    )
    st.stop()

# Top bar
nls = load_newsletters()
nl_ids = list(nls.keys())

c1, c2, c3, c4 = st.columns([2, 4, 3, 2])
with c1:
    st.markdown('<h1 class="brand">tldr pipeline</h1>', unsafe_allow_html=True)
with c2:
    selected_date = st.selectbox("date", dates, index=0, label_visibility="collapsed")
with c4:
    st.text_input("⌘K search", key="search", placeholder="search…", label_visibility="collapsed")

# Reload decisions when date changes
if ss.loaded_date != selected_date:
    ss.decisions = dec.load(selected_date)
    ss.loaded_date = selected_date

counts = _counts_pipeline(selected_date)

# Pipeline pills
with c3:
    st.markdown(
        f'<div class="pill">raw <b>{counts["raw"]}</b> · dedup <b>{counts["deduped"]}</b> · '
        f'scored <b>{counts["scored"]}</b> · blurbed <b>{counts["blurbed"]}</b></div>',
        unsafe_allow_html=True,
    )

# Load scored + blurbs
scored_all = [ScoredStory.from_dict(d) for d in read_jsonl(SCORED_DIR / f"{selected_date}.jsonl")]
blurbs = _load_blurbs(selected_date)

# Compute per-newsletter assignment counts and decision counts
nl_totals: dict[str, int] = {nid: 0 for nid in nl_ids}
nl_decisions: dict[str, dict[str, int]] = {nid: {dec.APPROVED: 0, dec.REJECTED: 0, dec.PENDING: 0} for nid in nl_ids}
cross_set: set[str] = set()  # story urls landing in 2+ newsletters
for s in scored_all:
    if len(s.assignments) > 1:
        cross_set.add(s.story.url)
    for a in s.assignments:
        if a.newsletter in nl_totals:
            nl_totals[a.newsletter] += 1
            d = ss.decisions.get((s.story.url, a.newsletter))
            status = d.status if d else dec.PENDING
            nl_decisions[a.newsletter][status] = nl_decisions[a.newsletter].get(status, 0) + 1

# Auto-select first newsletter on first load
if ss.selected_nl is None:
    # Prefer a newsletter with any assignments
    for nid in nl_ids:
        if nl_totals[nid] > 0:
            ss.selected_nl = nid
            break
    else:
        ss.selected_nl = default_newsletter_id()

# Allow newsletter selection via query param too (?nl=tldr_ai)
qp = st.query_params
if "nl" in qp and qp["nl"] in nl_ids + [CROSS_KEY]:
    ss.selected_nl = qp["nl"]


# ── Three-pane layout
rail_col, mid_col, det_col = st.columns([1.2, 3, 2])


# ── LEFT RAIL
with rail_col:
    def _rail_button(nid: str, label: str, total: int, decided: int, star: bool = False) -> None:
        cls = "active" if ss.selected_nl == nid else ""
        star_html = '<span class="star">★ </span>' if star else ""
        count_html = (
            f'<span class="count">{decided}/{total}</span>' if total else '<span class="count">0</span>'
        )
        # Use a real button so the click integrates with Streamlit state.
        key = f"rail_{nid}"
        if st.button(label, key=key, use_container_width=True):
            ss.selected_nl = nid
            ss.selected_url = None
            st.query_params["nl"] = nid
            st.rerun()
        # The button is rendered above; the markup adds the count line beneath it.
        st.markdown(
            f'<div style="font-size:10px;color:#9ca3af;margin:-6px 0 6px 8px;">{star_html}{count_html}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="rail">', unsafe_allow_html=True)
    st.markdown('<div class="head">queue</div>', unsafe_allow_html=True)

    cross_total = len(cross_set)
    cross_decided = sum(
        1
        for url in cross_set
        if all(
            ss.decisions.get((url, a.newsletter), dec.Decision(url, a.newsletter)).is_decided()
            for s in scored_all if s.story.url == url for a in s.assignments
        )
    )
    _rail_button(CROSS_KEY, "Cross-assignments", cross_total, cross_decided, star=True)

    st.markdown('<div class="head">newsletters</div>', unsafe_allow_html=True)
    for nid in nl_ids:
        nl = nls[nid]
        total = nl_totals[nid]
        decided = nl_decisions[nid][dec.APPROVED] + nl_decisions[nid][dec.REJECTED]
        label = nl.brand_name.replace("TLDR ", "").replace("TLDR", "main")
        _rail_button(nid, label, total, decided)

    st.markdown("</div>", unsafe_allow_html=True)


# ── MIDDLE PANE — story list for selected newsletter (or cross-assignments view)
def _render_row(scored: ScoredStory, assignment: Assignment, rank: int, section_min: int, section_max: int) -> None:
    """Render a single story row + handle click → set selected."""
    blurb = blurbs.get((scored.story.url, assignment.newsletter), {})
    decision = ss.decisions.get((scored.story.url, assignment.newsletter))
    status_cls = _row_status(decision, blurb, section_min, section_max)
    glyph = _status_glyph(status_cls)

    # Chips for cross-assignments
    chips = []
    for a in scored.assignments:
        if a.newsletter == assignment.newsletter:
            continue
        nick = a.newsletter.replace("tldr_", "")
        d = ss.decisions.get((scored.story.url, a.newsletter))
        cls = "ok" if d and d.status == dec.APPROVED else ("no" if d and d.status == dec.REJECTED else "")
        chips.append(f'<span class="chip {cls}">{nick}</span>')
    chips_html = "".join(chips)

    wc = int(blurb.get("word_count", 0))
    wc_text = f"{wc}w" if wc else "—"
    flag = "⚠" if blurb.get("needs_review") else ""

    is_selected = (ss.selected_url == scored.story.url and ss.selected_nl == assignment.newsletter)
    sel_cls = " sel" if is_selected else ""

    container = st.container()
    with container:
        # Use a button to capture click — render HTML for layout, button is the click target.
        st.markdown(
            f'<div class="row{sel_cls}">'
            f'<span class="num rank">{rank}</span>'
            f'<span class="num score">{int(round(assignment.score))}</span>'
            f'<div><div class="title">{scored.story.title}</div>'
            f'<div class="ftr">{chips_html}<span class="num">{wc_text}</span> {flag}</div></div>'
            f'<span class="num stat {status_cls}">{glyph}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Invisible-ish select button. Streamlit doesn't natively let us put a click-handler
        # on an HTML div, so we render a small "select" button below the row.
        if st.button("select", key=f"sel_{assignment.newsletter}_{scored.story.url}_{rank}", help="open this story in the detail pane"):
            ss.selected_url = scored.story.url
            ss.selected_nl_for_detail = assignment.newsletter
            st.rerun()


with mid_col:
    if ss.selected_nl == CROSS_KEY:
        st.markdown('<div class="sec"><h3>Cross-assignments</h3><span class="meta">stories landing in 2+ newsletters</span></div>', unsafe_allow_html=True)
        cross_stories = [s for s in scored_all if s.story.url in cross_set]
        cross_stories.sort(key=lambda s: s.score, reverse=True)
        if not cross_stories:
            st.markdown('<p style="color:#6b7280;font-size:12px;margin-top:12px;">No cross-assignments today.</p>', unsafe_allow_html=True)
        else:
            for rank, s in enumerate(cross_stories, start=1):
                # Show the highest-scoring assignment for the row
                primary = s.primary
                if primary is None:
                    continue
                sec = nls[primary.newsletter].section(primary.section_id)
                section_min = sec.min_words if sec else 40
                section_max = sec.max_words if sec else 80
                _render_row(s, primary, rank, section_min, section_max)
    else:
        nl = nls[ss.selected_nl]
        st.markdown(
            f'<div class="sec"><h3>{nl.brand_name}</h3><span class="meta">{nl_decisions[nl.id][dec.APPROVED] + nl_decisions[nl.id][dec.REJECTED]}/{nl_totals[nl.id]} decided</span></div>',
            unsafe_allow_html=True,
        )

        by_section = top_per_section(scored_all, nl.id)

        for sec in nl.sections:
            stories = by_section[sec.id]
            if not stories:
                continue
            decided_in_sec = 0
            for s in stories:
                d = ss.decisions.get((s.story.url, nl.id))
                if d and d.is_decided():
                    decided_in_sec += 1
            st.markdown(
                f'<div class="sec"><h3>{sec.emoji} {sec.name}</h3>'
                f'<span class="meta">{decided_in_sec}/{len(stories)}</span></div>',
                unsafe_allow_html=True,
            )
            for rank, s in enumerate(stories, start=1):
                a = s.for_newsletter(nl.id)
                if a is None:
                    continue
                _render_row(s, a, rank, sec.min_words, sec.max_words)


# ── RIGHT PANE — selected story detail + blurb editor
with det_col:
    st.markdown('<div class="detail">', unsafe_allow_html=True)
    selected_url = ss.selected_url
    selected_nl_for_detail = ss.get("selected_nl_for_detail") or ss.selected_nl

    selected_scored: ScoredStory | None = None
    selected_assignment: Assignment | None = None
    if selected_url and selected_nl_for_detail and selected_nl_for_detail != CROSS_KEY:
        for s in scored_all:
            if s.story.url == selected_url:
                selected_scored = s
                selected_assignment = s.for_newsletter(selected_nl_for_detail)
                break

    if selected_scored is None or selected_assignment is None:
        st.markdown('<p style="color:#6b7280;font-size:12px;">Click "select" on a row to load story details.</p>', unsafe_allow_html=True)
    else:
        nl = nls[selected_nl_for_detail]
        sec = nl.section(selected_assignment.section_id)
        blurb = blurbs.get((selected_scored.story.url, selected_nl_for_detail), {})
        decision = ss.decisions.get((selected_scored.story.url, selected_nl_for_detail))

        st.markdown(f'<h2>{selected_scored.story.title}</h2>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="src">{selected_scored.story.source} · '
            f'<a href="{selected_scored.story.url}" target="_blank">open ↗</a> · '
            f'{nl.brand_name} → {sec.name if sec else selected_assignment.section_id} · '
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
            height=180,
            key=editor_key,
            label_visibility="collapsed",
        )

        wc = len(edited.split())
        wc_bad = sec and not (sec.min_words <= wc <= sec.max_words)
        wc_class = "wc bad" if wc_bad else "wc"
        target = f"{sec.min_words}-{sec.max_words}" if sec else "—"
        st.markdown(
            f'<div class="{wc_class}">{wc} words · target {target} · '
            f'{int(blurb.get("minute_read", 5))} min read</div>',
            unsafe_allow_html=True,
        )

        # Action row
        b1, b2, b3, b4 = st.columns([1, 1, 1, 2])
        with b1:
            st.markdown('<div class="approve">', unsafe_allow_html=True)
            if st.button("✓ approve", key="act_approve"):
                dec.upsert(
                    ss.decisions,
                    selected_scored.story.url,
                    selected_nl_for_detail,
                    status=dec.APPROVED,
                    edited_blurb=edited if edited != blurb.get("blurb", "") else "",
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with b2:
            st.markdown('<div class="reject">', unsafe_allow_html=True)
            if st.button("✗ reject", key="act_reject"):
                dec.upsert(
                    ss.decisions,
                    selected_scored.story.url,
                    selected_nl_for_detail,
                    status=dec.REJECTED,
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with b3:
            if st.button("↺ reset", key="act_reset"):
                dec.upsert(
                    ss.decisions,
                    selected_scored.story.url,
                    selected_nl_for_detail,
                    status=dec.PENDING,
                    edited_blurb="",
                )
                dec.save(selected_date, ss.decisions)
                st.rerun()

        # Auto-save edits when the textarea changes and the user hasn't clicked approve.
        if edited and edited != initial_blurb and edited != blurb.get("blurb", ""):
            dec.upsert(
                ss.decisions,
                selected_scored.story.url,
                selected_nl_for_detail,
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
                    cls = "ok"
                    glyph = "✓"
                elif d2 and d2.status == dec.REJECTED:
                    cls = "no"
                    glyph = "✗"
                else:
                    cls = ""
                    glyph = "●"
                cross_html.append(
                    f'<span class="chip {cls}">{a.newsletter.replace("tldr_", "")} {glyph}</span>'
                )
            st.markdown("".join(cross_html), unsafe_allow_html=True)

        # Reasoning
        if selected_scored.reasoning:
            st.markdown('<div class="label">why (model)</div>', unsafe_allow_html=True)
            st.markdown(f'<p class="why">{selected_scored.reasoning}</p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ── BOTTOM — issue preview & exports
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("issue preview", expanded=True):
    # Render with edited blurbs and only approved-or-pending stories included.
    preview_nl = ss.selected_nl if ss.selected_nl and ss.selected_nl != CROSS_KEY else default_newsletter_id()
    nl = nls.get(preview_nl)
    if nl is None:
        st.markdown("(select a newsletter)")
    else:
        # Build a merged blurb map honoring decisions
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
        st.markdown(f'<div class="preview">{issue_text}</div>', unsafe_allow_html=True)

        exp1, exp2 = st.columns([1, 1])
        with exp1:
            st.download_button(
                "download this issue",
                data=issue_text,
                file_name=f"{preview_nl}-{selected_date}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with exp2:
            # Build a family bundle — only newsletters that have at least one merged blurb.
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
            st.download_button(
                "download family bundle",
                data=bundle_text,
                file_name=f"tldr-family-{selected_date}.txt",
                mime="text/plain",
                use_container_width=True,
            )
