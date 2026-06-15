# tldr-pipeline

An AI-assisted curation prototype for tech newsletters, modeled on TLDR AI.

The pipeline ingests RSS, arXiv, and Hacker News, deduplicates stories across sources, ranks them against an editorial rubric, drafts 2-sentence blurbs in the newsletter's voice, and presents everything in a Streamlit table where a curator can review, select, and export an issue draft.

Built to demonstrate that 50-70% of curator time per issue is automatable without sacrificing voice or editorial judgment.

## Architecture

```
RSS / arXiv / HN
     │
     ▼  ingestion/        raw stories         → data/raw/<date>.jsonl
     │
     ▼  dedup/            title embeddings,   → data/deduped/<date>.jsonl
     │                    canonical source
     │
     ▼  ranking/          Sonnet 4.6 +        → data/scored/<date>.jsonl
     │                    curation_rubric.md
     │
     ▼  blurbs/           Opus 4.7 +          → data/blurbs/<date>.jsonl
     │                    tldr_voice.md
     │
     ▼  ui/app.py         Streamlit review + export
```

Three project skill files in `.claude/skills/` carry the editorial knowledge:

- `tldr_voice.md` — annotated voice canon (22 real examples from recent issues)
- `curation_rubric.md` — 5-dimension 0-100 scoring rubric with disqualifiers and tie-breakers
- `data_sources.md` — source list with quality notes

These are loaded as system context by the ranking and blurb generators, and are the highest-leverage knobs to tune.

## Quickstart

```bash
# install uv if missing
curl -LsSf https://astral.sh/uv/install.sh | sh

# install deps
uv sync

# set your key
cp .env.example .env
# edit .env, set ANTHROPIC_API_KEY

# run the full pipeline for today
make refresh

# launch the review UI
make run
```

The first run downloads the sentence-transformer model (~80MB) for dedup embeddings. Subsequent runs use the cached copy.

## Per-step commands

```bash
make ingest DATE=2026-06-14    # pull from RSS, arXiv, HN
make dedup  DATE=2026-06-14    # cluster duplicates
make rank   DATE=2026-06-14    # score with Sonnet 4.6
make blurbs DATE=2026-06-14    # generate with Opus 4.7
```

## Cost model

For a 30-story workload with the defaults:

- Ranking (Sonnet 4.6): ~$0.15 per refresh
- Blurbs (Opus 4.7): ~$2-4 per refresh

Total: roughly **$3-5 per daily refresh**. Override `RANKING_MODEL` or `BLURB_MODEL` in `.env` to swap models. Sonnet for blurbs cuts cost ~3x with modest voice drift.

Ranking outputs are cached by URL+title hash in `data/scored/.cache/` so dev iterations don't re-pay. Delete that folder to force a re-score.

## Backtest

```bash
uv run python scripts/backtest.py --start 2026-06-01 --end 2026-06-12
```

For each day, this scrapes the actual TLDR AI issue, extracts the published headlines, and computes how many of TLDR's picks appear in our top-10 / top-20 / top-30 (via embedding similarity ≥ 0.78).

This is the metric to show in a demo: if we surface 60%+ of TLDR's actual picks in our top-10, the curator's job changes from "read everything" to "pick from a strong shortlist".

## Tuning

- **Voice off?** Edit `.claude/skills/tldr_voice.md`. Add 2-3 more examples in whichever section is weakest. Voice files are the cheapest, highest-leverage thing in the system.
- **Wrong stories in top-10?** Edit `.claude/skills/curation_rubric.md`. Adjust the dimension weights or add a calibration anchor.
- **Missing source types?** Add to `config/sources.yaml`. Document the addition in `.claude/skills/data_sources.md`.
- **Dedup over-merging?** Raise the threshold in `dedup/cluster.py` (default 0.82).
- **Dedup under-merging?** Lower it. Also check whether the issue is title-only — full-text embeddings would catch more.

## Layout

```
tldr-pipeline/
├── common/                 # Shared dataclasses, JSONL helpers
│   └── story.py
├── ingestion/              # RSS + arXiv + HN pullers
│   ├── rss.py
│   ├── arxiv_puller.py
│   ├── hn.py
│   └── run.py
├── dedup/                  # Embedding + clustering + canonical source pick
│   ├── cluster.py
│   └── run.py
├── ranking/                # Sonnet 4.6 scoring against rubric
│   ├── score.py
│   └── run.py
├── blurbs/                 # Opus 4.7 voice-matched blurbs
│   ├── generate.py
│   └── run.py
├── ui/                     # Streamlit review + export
│   └── app.py
├── scripts/                # Backtest + ad-hoc tooling
│   └── backtest.py
├── config/                 # sources.yaml
├── .claude/skills/         # Voice, rubric, sources (editorial knowledge)
├── data/                   # Generated artifacts (gitignored)
├── Makefile
├── pyproject.toml
└── .env.example
```

## Status

Prototype. End-to-end works on a real day's traffic. Not production-hardened: no retry queue for the model APIs beyond basic exponential backoff, no auth on the Streamlit UI, no per-newsletter routing, no click-data signal in ranking (that's the obvious next step — pull historical TLDR open/click data per story and learn a ranker on top of the LLM scores).
