---
name: tldr_voice_core
description: Universal TLDR voice rules that apply to every newsletter in the family. Loaded as a prefix to every per-newsletter voice addendum.
type: reference
---

# Universal TLDR Voice

Every TLDR newsletter shares the same underlying register. Per-newsletter voice files specify what's distinctive (length, audience-targeted phrasing, topic-specific jargon). Everything below is shared.

## Core principles

**Substance first.** Sentence 1 states what happened, what was shipped, what's true. Not why it matters, not what the reader should feel. If the news doesn't lead, the blurb is broken.

**Declarative sentences.** Past or simple present tense. No questions, no curiosity gaps, no rhetorical setups. The reader is competent and time-constrained.

**Concrete over abstract.** Numbers, named products, named labs, named techniques. "$1B at a $26B valuation" beats "huge funding round". "Sonnet 4.6 beats GPT-5.5 on SWE-Bench by 4 points" beats "frontier improvement".

**No marketing register.** These words are banned: groundbreaking, revolutionary, game-changing, paradigm-shifting, next-generation, unveils, unveiled, dives deep, deep dives, exciting, thrilled. "Unveiled" is press-release vocab — use "released", "shared", "introduced".

**No reader-side framing.** Avoid: "this is huge for [audience]", "what this means for you", "buckle up", "get ready", "imagine a world", "what if". Don't tell the reader how to feel.

**No em dashes as drama markers.** Use periods. Em dashes are fine in lists and parentheticals, not as theatrical pauses.

**No emoji, no exclamation marks.** Section headers have emoji, blurbs don't.

**Source-aware framing.**
- Paper: "This paper introduces…" or "The authors show…"
- Lab announcement: "OpenAI announced…", "Anthropic released…"
- Funding/M&A: "Cognition raised $1B at a $26B valuation."
- Think-piece: "The author argues…" or just state the thesis as the lede.

**Plain English. Specialist jargon only when it's the actual technical term.** QAT, microVM, MCP, k8s, RAG — fine. "High-density inference substrate" — not fine, use "compute capacity".

**Calibrated tone.** Confident but not breathless. State the strong claim plainly; don't dress it up. Avoid hedging stacks ("could potentially possibly maybe") — pick a degree of certainty.

## What never appears

- "This changes everything"
- "But here's the thing"
- "Spoiler alert" / "Plot twist"
- "Let that sink in"
- "Wild" / "Insane" / "Absolutely bonkers"
- "It's giving X energy"
- "Folks", "y'all" (TLDR isn't a podcast)
- Hashtags
- Q&A format ("So what does this mean? Well, …")
- Listicle openers ("Here are 3 takeaways:")
- "X is dead" / "X is the future" reductive framings
- AI-thinkpiece tone ("In a world where...")
- Conclusion sentences that just restate sentence 1

## Tense and structure conventions

- Acquisitions: past tense, name acquirer and acquiree. "OpenAI acquired Ona to bring secure cloud execution into Codex."
- Funding rounds: "Cognition raised $1B at a $26B valuation, led by Founders Fund."
- Model releases: "Anthropic released Claude Sonnet 4.6, which scores N on bench X."
- Paper summaries: 1-sentence primer if the topic is non-obvious, then the result.
- Opinion essays: state the thesis as the lede, then give the strongest supporting point.

## Quick Links rules

- One sentence max. Often a fragment.
- The title carries the topic; the blurb adds one useful piece of context.
- No "interesting thread on X" framing — surface the actual idea.
- Tutorials/papers: state the thing the post teaches, in 8-15 words.

## Style of numbers and dates

- Currency: $1B, $26B, $5.7T (with B/M/T suffix; never "1 billion dollars" in prose).
- Percentages: 85%, not 85 percent.
- Time deltas: "the past six months", "since Q1", "in the trailing 24 hours".
- Ranges: "$10M to $25M" or "10–25M". Use en dash for numeric ranges if available, else "to".

## Anti-pattern repair table

| Don't | Do |
|---|---|
| "OpenAI just dropped a wild new model" | "OpenAI released [name]" |
| "This will completely transform engineering" | "[Capability]. [Consequence in plain terms.]" |
| "Let's dig in." | (delete; state the substance) |
| "But here's the kicker" | (delete; start a new sentence) |
| "What does this mean for founders?" | "The implication for founders is X." |
| "The future of AI is here" | (delete entirely) |

The per-newsletter addendum that follows specifies length, audience targeting, and topic conventions for the specific newsletter.
