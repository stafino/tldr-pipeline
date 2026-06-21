# TLDR Pipeline UI - Redesign Proposal

Audience: a curator who has to ship 13 newsletters before 10am. The UI must let them clear a queue, not "explore a dashboard."

## 1. Inspiration

Three references, each contributing one specific pattern:

- **Linear's Triage inbox.** Borrow the *three-pane shell*: left rail (newsletters / sections, with unread-style counts), middle list (dense one-line-per-story rows with rank, score, title, flags), right pane (full story + editable blurb). Selection is sticky; keyboard moves through the list. This is the dominant pattern for "review N items, decide on each."
- **Superhuman / Hey.com triage.** Borrow *single-key verbs on the focused item* - `a` approve, `r` reject, `x` cross-assign, `e` edit blurb, `j/k` next/prev. The curator's job is fundamentally email-triage-shaped: a queue with a verdict per item.
- **GitHub Projects board (when needed) and PR-in-N-projects chip.** Borrow the *"also in" chip cluster*: a story landing in 3 newsletters shows three small mono-style pills (`ai`, `dev`, `data`) inline on its row, color-coded by whether each assignment is approved, pending, or rejected. Same pattern Spotify uses for "on 3 playlists."

What we are *not* borrowing: Notion's airy cards (wrong density), Substack's analytics-first dash (wrong job), Beehiiv's WYSIWYG editor (the final format is a fixed text template, not freeform).

## 2. Information architecture

The data has three intersecting axes - day, newsletter, section - and a cross-cutting dimension (cross-assignments). The current UI nests them as date → newsletter → section-tabs, which hides 4/5 of any newsletter behind a click and makes cross-newsletter context invisible. Reorganize:

**Top (always visible): the Day.** One date in scope. Status pills show pipeline health (raw → deduped → scored → blurbed → decided). One global progress bar: "47 of 142 decisions made." This is the curator's anchor.

**Left rail (persistent): the Newsletter list.** All 13 newsletters with `decided/total` counts and a small approved/pending/rejected donut. A "Cross-assignments" pseudo-newsletter at the top surfaces stories landing in 2+ newsletters - the highest-leverage items to review first, and the most demo-able artifact of the system's intelligence.

**Middle pane: the Section-grouped story list.** All five sections of the selected newsletter as one scrollable list with sticky section headers (not tabs). The curator's mental model is "the issue," not "this one tab" - they need Headlines and Quick Links visible together to feel the shape of the day. Each row is one (story, newsletter) pair.

**Right pane: the selected story.** Title, source, URL, draft blurb (inline editable), word/min-read against the section's min/max, the "also in" chip cluster (click a chip to jump), and the model's reasoning. Always rendered, never modal - keyboard nav stays continuous.

**Bottom drawer (collapsible): the Issue preview.** The TLDR-format text for the current newsletter, re-rendering live as decisions land. A second column shows the backtest diff against the published issue for that date when available. The day-level export bar is the floor of the screen.

## 3. Concrete layout spec

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│  tldr pipeline   [2026-06-15 ▾]   raw 184 · dedup 151 · scored 151 · blurbed 142  │
│                  decided 47/142   ████████░░░░░░░░░░░░░░░  33%        [⌘K search] │
├──────────────┬────────────────────────────────────────────┬───────────────────────┤
│ NEWSLETTERS  │  TLDR AI  ·  2026-06-15  ·  22 stories     │  SELECTED STORY       │
│              │                                            │                       │
│ ★ Cross (12) │  ── Headlines & Launches  5/5 ─────────  ✓ │  Anthropic ships      │
│ tech    8/24 │  1  92  Anthropic ships memory in Claude…  │  long-term memory…    │
│ ai     7/22◀ │      [ai] [dev]  148w  ✓ approved         │                       │
│ founders 3/18│  2  88  OpenAI deprecates GPT-4 endpoints  │  techcrunch.com       │
│ dev     4/19 │      [tech] [dev]  62w  ● pending          │  open in tab ↗        │
│ data    2/16 │  3  84  Mistral raises $600M Series C      │  ─────────────────    │
│ design  0/12 │      [founders]  71w  ⚠ 31w under min      │  BLURB (ai voice)     │
│ infosec 5/15 │  4  79  …                                  │  ┌─────────────────┐  │
│ it      0/13 │  5  74  …                                  │  │ Anthropic gave  │  │
│ devops  1/14 │  ── Deep Dives & Analysis  3/5 ───────── ● │  │ Claude a memory │  │
│ marketing 6/17│  6  81  Why frontier labs are pivoting…   │  │ layer that …    │  │
│ product 4/16 │      [founders]  88w  ✓ approved           │  │                 │  │
│ crypto  0/10 │  7  …                                      │  └─────────────────┘  │
│ fintech 7/15 │  ── Engineering & Research  4/5 ─────── ●  │  72 words · 0:24 read │
│              │  ── Miscellaneous  2/3 ──────────────── ●  │  target 40-75 ✓       │
│ ─────────    │  ── Quick Links  3/5 ────────────────── ●  │  regen blurb ↻        │
│ done: 4/13   │                                            │  ─────────────────    │
│              │                                            │  ALSO IN              │
│              │                                            │  tldr_dev ✓ approved  │
│              │                                            │  tldr_tech ● pending  │
│              │                                            │  ─────────────────    │
│              │                                            │  WHY (model)          │
│              │                                            │  Frontier-lab memory  │
│              │                                            │  feature, high reader │
│              │                                            │  relevance for AI…    │
├──────────────┴────────────────────────────────────────────┴───────────────────────┤
│  ▾ issue preview (tldr_ai · 2026-06-15)    [backtest vs actual]    [copy] [.txt]  │
├───────────────────────────────────────────────────────────────────────────────────┤
│  approve-all visible  ·  regen all flagged (3)  ·  export issue  ·  export bundle │
└───────────────────────────────────────────────────────────────────────────────────┘
```

Status glyphs: `✓` approved, `●` pending, `✗` rejected, `⚠` flagged (word count off). Section header right-edge shows aggregate state of its rows. Score is a plain integer left-aligned next to rank - no progress bars, no color gradients.

Keyboard: `j/k` move row, `a/r` approve/reject, `e` focus blurb textarea, `g` then newsletter-letter to jump newsletters, `?` shows the cheat sheet.

## 4. Component breakdown

| Region | Streamlit component |
|---|---|
| Top bar | `st.columns([2,4,2])` + a custom HTML progress div (`st.markdown(unsafe_allow_html=True)`). Avoid `st.progress` - too tall and pastel. |
| Left rail | Single `st.markdown` block rendering an HTML `<ul>` of newsletters with counts; selection via `st.query_params` anchor links (`?nl=tldr_ai`). Tighter than 13 stacked `st.button`s. |
| Middle pane (story list) | **`streamlit-aggrid`** - justified. We need row selection that drives the right pane, sticky section grouping (AgGrid's `groupRowsSticky`), per-cell coloring for flags, and keyboard row nav. `st.dataframe` cannot drive a detail pane reliably and has no sticky groups. Per-row `st.container` becomes unusable past ~30 rows. AgGrid is the one place the dep is worth it. |
| Right pane | Outer `st.columns([3,2])` (list:detail = 3:2). Inside: `st.markdown` header, `st.text_area` blurb (height ~220), `st.columns(3)` for `approve / reject / regen`, `st.markdown` chips for "also in", `st.caption` for reasoning. State in `st.session_state["decisions"][(date, story_url, newsletter)]`. |
| Bottom drawer | `st.expander("issue preview")` with `st.code(issue_text, language=None)` - gives a copy button for free, monospace box matches export format. Backtest is a second `st.code` via `st.columns(2)`. |
| Bottom action bar | `st.columns([2,2,2,2])` with four `st.button`s; `st.download_button` for the two exports. |
| Keyboard | `streamlit-shortcuts` for `j/k/a/r/e`. To avoid the dep, a `components.html` block posting to `st.query_params` works. |
| Cross-assign chips | `st.markdown` rendering `<span class="chip chip-approved">ai</span>`, styled in the existing `<style>` block. |

CSS: monochrome - black text, one accent (`#2b6cb0`), greyscale elsewhere. Drop the global monospace; keep mono for the issue preview, ranks, scores, word counts, chips. Titles and blurbs are prose - set them in the default sans.

## 5. Five most-leveraged changes

1. **Replace `st.tabs` over sections with a single scrollable list grouped by sticky section headers.** This is the biggest one. Tabs hide 4/5 of the issue at any time and prevent the curator from forming a mental picture of the whole newsletter. One vertical list with sticky headers is how Linear, Superhuman, and every real triage tool works.
2. **Add a persistent right-pane detail view with an inline blurb editor and approve/reject state.** Today there is no edit, no approve, no reject - only a dataframe and a read-only preview. The whole point of a curation tool is per-item decisions; the data model already supports it (blurbs have `needs_review`), the UI just doesn't expose it. Persist decisions to `data/decisions/{date}.jsonl`.
3. **Add the left rail with the "Cross-assignments" pseudo-newsletter at the top.** Cross-assigned stories are where mistakes are most expensive (same blurb in two voices, double-counted in the bundle). Surfacing them as a dedicated queue is high-signal and visually demonstrates the system's intelligence to TLDR leadership during the demo.
4. **Live issue preview that re-renders as the curator approves/edits, with a backtest diff against the published issue.** The current preview is computed once and is decoupled from any decisions. A live preview *plus* a side-by-side diff with the real published TLDR for that date is the demo's "wow" moment - it proves the pipeline can reproduce the human output.
5. **Real keyboard nav (`j/k/a/r/e`) and a `?` cheat sheet.** Curators reviewing 150 items will not click. Without keyboard, the tool is a toy. With it, the tool is faster than the curator's current process - which is the only thing that will land the customer.

## 6. Anti-patterns to avoid

- **Do not use `st.dataframe` as the primary list.** It cannot drive a detail pane, cannot host inline editors that look acceptable, and screams "I am a generic Streamlit app." Either AgGrid or a hand-rolled list of `st.container` rows - not the default dataframe.
- **Do not use `st.tabs` for sections.** See #1 above. Tabs are fine for *modes* (Curate / Preview / Backtest), not for *parts of the same artifact*.
- **Kill the global monospace.** The current `app.py` forces `ui-monospace` on titles, headers, dataframes, textareas. It reads as "developer cosplay," not "professional product." Mono belongs on numbers, the issue preview, and chips. Titles and blurbs are prose - set them in the default sans.
- **No emoji in titles, headers, or buttons.** The current title is `"tldr pipeline"` (fine) but the bundle-export code literally sniffs for emoji characters in rendered text to decide if a newsletter is "real" - `if "📈" in txt or "🚀" in txt …`. That is both a UX smell and a logic bug; replace with an explicit `has_content` check on `blurbs_for_nl`. Section emojis from `newsletters.yaml` are part of TLDR's brand and belong only in the rendered issue preview, not the UI chrome.
- **No pastel cards, no "Get started!" empty states, no hero metrics.** A newsletter with no assignments shows one grey line: `tldr_design - no assignments for 2026-06-15`. Not a card with an illustration.
- **No `st.balloons`, no `st.success` toasts on approve.** The glyph flipping `●` → `✓` is its own feedback.
- **No "Dashboard" / "Pipeline" hero titles, no emoji in chrome.** The current `st.title("tldr pipeline")` voice - lowercase, no emoji, no period - is correct. Hold that voice everywhere.
- **Do not split the day into per-newsletter pages or routes.** One page, one day, left rail switches scope. Page-per-newsletter destroys the cross-assignment overview, which is the system's main differentiator.
