# tldr-pipeline

An AI-assisted curation prototype for tech newsletters, modeled on TLDR.

The pipeline ingests RSS, arXiv, and Hacker News, deduplicates stories across sources, ranks them against an editorial rubric, classifies each into the right newsletter section, drafts blurbs in the newsletter's voice, and renders the final output **in the exact TLDR format** — ready for a curator to skim, edit, and ship.

Built to demonstrate that 50-70% of curator time per issue is automatable without sacrificing voice or editorial judgment.

## Two LLM backends

| Backend | How it's billed | Speed per call | When to use |
|---|---|---|---|
| `api` (default) | `ANTHROPIC_API_KEY`, billed per token | 1-2s | Production, automation, demos with quota concerns |
| `cli` | Your Claude Code subscription | 5-10s (subprocess spawn) | Personal prototyping when you don't have an API key |

Switch with `LLM_BACKEND=api|cli` in `.env`. With `cli`, the pipeline shells out to `claude -p --bare --model <m> --system-prompt "..." "<user prompt>"`. A 50-story refresh takes ~3 minutes with `api`, ~10-15 minutes with `cli`. The CLI backend is fine for a demo; using subscription quota for automation isn't its intended purpose.

## Architecture

```
RSS / arXiv / HN
     │
     ▼  ingestion/        raw stories               → data/raw/<date>.jsonl
     │
     ▼  dedup/            title embeddings,         → data/deduped/<date>.jsonl
     │                    canonical source
     │
     ▼  ranking/          rubric scoring +          → data/scored/<date>.jsonl
     │                    section classification
     │
     ▼  blurbs/           voice-matched blurbs      → data/blurbs/<date>.jsonl
     │                    (top-10 per section)
     │
     ▼  formatters/tldr   exact TLDR issue layout   → data/issues/<nl>-<date>.txt
     │
     ▼  ui/app.py         Streamlit review + preview + download
```

Editorial knowledge lives in `.claude/skills/`:

- `tldr_founders_voice.md` — 20 annotated examples of the Founders voice (longer, more opinionated, operator-targeted)
- `tldr_voice.md` — 22 annotated examples of the AI voice (shorter, denser, technical)
- `curation_rubric.md` — 5-dimension 0-100 scoring rubric with disqualifiers and tie-breakers
- `data_sources.md` — source list with quality notes

Per-newsletter section schemas (target counts per section, word-count constraints, descriptions) live in `config/newsletters.yaml`.

## Quickstart

```bash
# install uv if missing
curl -LsSf https://astral.sh/uv/install.sh | sh

# install deps
uv sync

# configure
cp .env.example .env
# edit .env: set LLM_BACKEND and either ANTHROPIC_API_KEY or none (for cli)

# run the full pipeline for today, defaulting to Founders
make refresh

# or target the AI newsletter
make refresh NEWSLETTER=tldr_ai

# launch the review UI (preview + download issue draft)
make run
```

The first run downloads the sentence-transformer model (~80MB) for dedup embeddings.

## Per-step commands

```bash
make ingest  DATE=2026-06-14                       # pull from RSS, arXiv, HN
make dedup   DATE=2026-06-14                       # cluster duplicates
make rank    DATE=2026-06-14 NEWSLETTER=tldr_ai    # score + classify into sections
make blurbs  DATE=2026-06-14 NEWSLETTER=tldr_ai    # generate blurbs for top-10 per section
make format  DATE=2026-06-14 NEWSLETTER=tldr_ai    # render exact-TLDR-format issue draft
```

## Output format

The formatted issue matches the actual TLDR layout exactly: section header (emoji + name), each story rendered as

```
<Title> (<N> minute read)

<Blurb>
```

Default schema is `tldr_founders` (Headlines & Trends 📈, Strategies & Tactics 🧠, Tools & Resources ⚒️, Miscellaneous 🎁, Quick Links ⚡). Up to 10 stories per section. Adjust the per-section `target_count`, `min_words`, and `max_words` in `config/newsletters.yaml`.

## Cost model

For a 50-story workload (10 per section × 5 sections) with the API backend:

- Ranking (Sonnet 4.6): ~$0.20-0.30 per refresh
- Blurbs (Opus 4.7): ~$4-7 per refresh (longer blurbs for Founders push this up)

Total: roughly **$5-8 per daily refresh** in API mode. The CLI backend amortizes against your existing Claude Code subscription.

Ranking outputs are cached by `(newsletter, url, title)` hash under `data/scored/.cache/`. Delete that folder to force a re-score.

## Backtest

```bash
uv run python scripts/backtest.py --start 2026-06-01 --end 2026-06-12
```

Scrapes the actual TLDR archive for each day and computes recall@10/20/30 via title-embedding similarity. Useful for the "see, we surface 60%+ of TLDR's actual picks in our top-10" moment in a demo.

## Tuning

- **Voice off?** Edit `.claude/skills/tldr_founders_voice.md` (or `tldr_voice.md`). Add 2-3 more examples in whichever section is weakest.
- **Wrong stories in top-10?** Edit `.claude/skills/curation_rubric.md`. Adjust the dimension weights or add a calibration anchor.
- **Stories in the wrong section?** Edit the section `description` field in `config/newsletters.yaml`. Those descriptions are what the classifier reads.
- **Missing source types?** Add to `config/sources.yaml`; document in `.claude/skills/data_sources.md`.
- **Dedup over-merging?** Raise the threshold in `dedup/cluster.py` (default 0.82). Under-merging? Lower it.

## Layout

```
tldr-pipeline/
├── common/                 # Shared dataclasses, newsletter schemas, LLM backend
│   ├── story.py
│   ├── newsletters.py
│   └── llm.py
├── ingestion/              # RSS + arXiv + HN pullers
├── dedup/                  # Embedding + clustering + canonical source pick
├── ranking/                # Rubric scoring + section classification (Sonnet 4.6)
├── blurbs/                 # Section-aware voice-matched blurbs (Opus 4.7)
├── formatters/             # Exact TLDR format renderer
├── ui/                     # Streamlit review + preview + download
├── scripts/                # Backtest
├── config/                 # sources.yaml, newsletters.yaml
├── .claude/skills/         # Voice canons, rubric, data sources
├── data/                   # Generated artifacts (gitignored)
├── Makefile
├── pyproject.toml
└── .env.example
```

## Status

Prototype. End-to-end runs on a real day's traffic in both backend modes. Not production-hardened: no auth on the Streamlit UI, no per-curator click-data signal in ranking (the obvious next step — pull historical TLDR click data per story per curator and learn a re-ranker on top of the LLM scores), no X/Twitter ingestion (TLDR cites threadreader unrolls heavily, so backtest recall will undercount stories sourced from X).
