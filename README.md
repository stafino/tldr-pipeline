# tldr-pipeline

AI-assisted curation infrastructure for the **entire TLDR newsletter family**.

The pipeline ingests RSS, arXiv, Hacker News across 100+ sources, deduplicates stories, then for each story decides:

1. Which of the **13 TLDR newsletters** it belongs in (a story can land in multiple).
2. Which **section** of each newsletter is the right slot.
3. A per-newsletter fit score.

Then it generates voice-matched blurbs (Opus 4.7) for each (story, newsletter) pair, and renders each newsletter's issue in the **exact TLDR layout** — ready for a curator to review, edit, and ship.

Goal: cut curator time per issue by 50-70% while preserving voice and editorial judgment, **across every TLDR newsletter at once**.

## Newsletters supported

| Newsletter | Slug | Audience |
|---|---|---|
| TLDR (Tech) | `tldr_tech` | General technical readers — the flagship daily digest |
| TLDR AI | `tldr_ai` | ML engineers and AI researchers |
| TLDR Founders | `tldr_founders` | Startup founders and operators |
| TLDR Dev | `tldr_dev` | Software engineers across stacks |
| TLDR Data | `tldr_data` | Analytics engineers, data engineers, data PMs |
| TLDR Design | `tldr_design` | Product designers and design leaders |
| TLDR InfoSec | `tldr_infosec` | Security practitioners |
| TLDR IT | `tldr_it` | Enterprise IT leaders, CIOs |
| TLDR DevOps | `tldr_devops` | SREs, platform engineers |
| TLDR Marketing | `tldr_marketing` | Growth and demand-gen marketers |
| TLDR Product | `tldr_product` | Product managers |
| TLDR Crypto | `tldr_crypto` | Crypto-native engineers and operators |
| TLDR Fintech | `tldr_fintech` | Payments / banking-infra builders |

Each newsletter has its own section schema (e.g., Founders has "📈 Headlines & Trends, 🧠 Strategies & Tactics, ⚒️ Tools & Resources, 🎁 Miscellaneous, ⚡ Quick Links") with per-section blurb word-count constraints. Target 5-10 stories per section, 20-50 stories per newsletter per day, 100-250+ stories total across the family.

## Two LLM backends

| Backend | How it's billed | Speed per call | When to use |
|---|---|---|---|
| `cli` (default) | Your Claude Code subscription | 5-10s (subprocess spawn) | Personal prototyping, no API key |
| `api` | `ANTHROPIC_API_KEY`, billed per token | 1-2s | Automation, demos with quota concerns |

Switch with `LLM_BACKEND=cli|api` in `.env`.

## Architecture

```
100+ RSS feeds + 7 arXiv categories + Hacker News
     │
     ▼  ingestion/           topic-tagged stories       → data/raw/<date>.jsonl
     │
     ▼  dedup/               sentence-transformer        → data/deduped/<date>.jsonl
     │                       clustering + canonical
     │
     ▼  ranking/             multi-newsletter scoring:   → data/scored/<date>.jsonl
     │                       ONE call per story →
     │                       up to 3 (newsletter,
     │                       section, score) tuples
     │
     ▼  blurbs/              per-(story, newsletter)     → data/blurbs/<date>.jsonl
     │                       voice-matched blurb gen,
     │                       per-section word constraints
     │
     ▼  formatters/tldr/     one issue per newsletter    → data/issues/<nl>-<date>.txt
     │                       in the exact TLDR layout
     │
     ▼  ui/app.py            Streamlit review: newsletter picker, per-section
                              tabs, formatted preview, download per-newsletter
                              or family bundle
```

Editorial knowledge in `.claude/skills/`:

- `tldr_voice_core.md` — universal voice rules across all newsletters
- `tldr_<nl>_voice.md` — 13 per-newsletter addenda (length, audience, jargon, anti-patterns specific to that newsletter)
- `curation_rubric.md` — 5-dimension 0-100 scoring rubric with disqualifiers and tie-breakers
- `data_sources.md` — source list with quality notes

The blurb generator loads `tldr_voice_core.md` + the relevant per-newsletter addendum every call.

## Quickstart

```bash
# install uv if missing
curl -LsSf https://astral.sh/uv/install.sh | sh

# configure (LLM_BACKEND=cli is the default — no API key needed)
cp .env.example .env

# run everything for today + open the review UI
./tldr
```

The full pipeline for a day with 100+ ingested stories takes ~40-90 minutes in CLI mode (the subprocess-spawn overhead is the main cost). Subsequent runs hit the disk cache and finish in seconds. The cache is keyed by `(set-of-newsletters, url, title)` for ranking and `(newsletter, section, url)` for blurbs — both invalidate automatically if the newsletter set or section schema changes.

## `tldr` subcommands

| Command | Behaviour |
|---|---|
| `tldr` | Full pipeline + launch UI |
| `tldr refresh` | Full pipeline only |
| `tldr ingest` / `dedup` / `rank` | Single step (newsletter-agnostic) |
| `tldr blurbs` | Blurbs for ALL newsletters (default) |
| `tldr blurbs tldr_ai` | Blurbs for one newsletter only — useful for iteration |
| `tldr format` | Render ALL newsletter issues |
| `tldr format tldr_ai` | Render one |
| `tldr ui` | Launch the Streamlit review UI |
| `tldr open tldr_founders` | Open today's Founders issue in `$EDITOR` |
| `tldr status` | Counts per stage + list of rendered issues |
| `tldr list` | List all newsletters and their sections |
| `tldr backtest 2026-06-01 2026-06-12` | Recall@K for all newsletters vs the real archive |
| `tldr backtest 2026-06-01 2026-06-12 tldr_ai` | Just one newsletter |

Env overrides: `DATE=YYYY-MM-DD`, `LLM_BACKEND=cli|api`, `MIN_ASSIGNMENT_SCORE=55` (raise to be pickier).

## Sources

100+ sources tagged by topic in `config/sources.yaml`. Mix of:
- **First-party** lab/company blogs (OpenAI, Anthropic, DeepMind, AWS, Stripe, etc.)
- **Substacks** (Stratechery, Tom Tunguz, Benn Stancil, Latent Space, Lenny's, Import AI, Every, …)
- **VC / research blogs** (a16z, Sequoia, Paradigm, NFX, …)
- **Trade pubs** (Krebs, Schneier, Dark Reading, CIO Dive, The Block, Sifted, …)
- **arXiv** (cs.AI, cs.LG, cs.CL, cs.CR, cs.SE, cs.DB, cs.HC)
- **Hacker News** top-stories filter

Each source carries `topics:` tags. The ranking model sees these and uses them as a hint when picking newsletters.

**Not yet wired up:** X / LinkedIn ingestion. X's API requires a paid tier; LinkedIn has no public RSS. TLDR cites both via threadreader unrolls and "from a LinkedIn post" framing — until we add these, you'll undercount stories sourced there. Worth knowing when looking at backtest recall numbers.

## Cost model

Per refresh in `api` mode (Sonnet ranking + Opus blurbs):

- ~150 stories × ranking call = ~$0.40-0.70
- ~200-300 blurbs (across all newsletters) = ~$8-15

Total: roughly **$10-20 per daily refresh in API mode** for the entire family. With `cli` backend you just spend subscription credits, which are flat.

To reduce blurb cost dramatically: switch `BLURB_MODEL=claude-sonnet-4-6` in `.env` and accept slight voice drift.

## Tuning knobs

- **Voice off for one newsletter?** Edit its `.claude/skills/tldr_<nl>_voice.md` addendum. Each is ~50 lines.
- **Stories assigned to wrong newsletter?** Edit the `description:` and `topics:` fields in `config/newsletters.yaml`. Those drive the classifier.
- **Want fewer / more stories per section?** Adjust `target_count:` in `config/newsletters.yaml`.
- **Too many borderline stories?** Raise `MIN_ASSIGNMENT_SCORE` in `.env` (default 55).
- **Missing source?** Add to `config/sources.yaml` with topic tags; the ingestion picks it up next run.
- **Dedup over/under-merging?** Adjust threshold in `dedup/cluster.py` (default 0.82).

## Layout

```
tldr-pipeline/
├── common/                 # Shared dataclasses, newsletter schemas, LLM backend
├── ingestion/              # RSS + arXiv + HN pullers (topic-tagged)
├── dedup/                  # Sentence-transformer clustering
├── ranking/                # Multi-newsletter scoring with section assignment
├── blurbs/                 # Per-(story, newsletter) voice-matched generation
├── formatters/             # Exact TLDR-format renderer per newsletter
├── ui/                     # Streamlit review: newsletter picker, per-section tabs
├── scripts/                # Backtest across all newsletters
├── config/                 # sources.yaml, newsletters.yaml
├── .claude/skills/         # Voice core + 13 per-newsletter addenda + rubric
├── data/                   # Generated artifacts (gitignored)
├── tldr                    # Subcommand driver — `tldr` to run everything
├── pyproject.toml
└── .env.example
```

## Status

Working prototype, end-to-end across all 13 newsletters. Not production-hardened: no auth on the Streamlit UI, no per-curator click-data signal in ranking (that's the obvious next step — pull historical TLDR open/click data per newsletter and learn a re-ranker on top of the LLM scores), no X / LinkedIn ingestion. Backtest recall is a useful metric but undercounts because we miss the X-sourced stories TLDR cites.
