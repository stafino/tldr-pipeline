---
name: data_sources
description: Source list for TLDR AI ingestion. RSS feeds, arXiv categories, HN config, with quality notes for each.
type: reference
---

# Data Sources

This file documents which sources the ingestion layer pulls from and why. The actual machine-readable list lives in `config/sources.yaml`; this file is the human-readable companion with quality notes and rationale.

## RSS feeds

| Source | URL | Quality | Frequency | What it's good for |
|---|---|---|---|---|
| `openai_blog` | https://openai.com/news/rss.xml | High (first-party) | 1-3/week | Model releases, official policy posts, deal announcements. Almost always worth surfacing. |
| `anthropic_news` | https://www.anthropic.com/news/rss.xml | High (first-party) | 1-3/week | Same as OpenAI - first-party. Research posts (e.g., interpretability) and product news. |
| `deepmind_blog` | https://deepmind.google/blog/rss.xml | High (first-party) | 1-2/week | Capability demos and research papers from DeepMind. |
| `google_research` | https://research.google/blog/rss/ | High | 2-4/week | Research breadth across DeepMind and other Google research orgs. |
| `meta_ai` | https://ai.meta.com/blog/rss/ | High | 1-3/week | Llama series, FAIR papers, infra posts. |
| `huggingface_blog` | https://huggingface.co/blog/feed.xml | Medium-High | 5-15/week | Practitioner posts, open model launches, training/inference techniques. Variable quality, but the good ones land in TLDR's Engineering section. |
| `simonwillison` | https://simonwillison.net/atom.xml | High (commentary) | 5-10/week | Simon's weekly notes and curated link posts often surface in TLDR Deep Dives. |
| `import_ai` | https://importai.substack.com/feed | High | 1/week | Jack Clark's roundup. Strong policy and capability synthesis. |
| `latent_space` | https://www.latent.space/feed | Medium | 2-3/week | Engineer-oriented essays and interviews. Good for tooling stories. |
| `aqnichol` | https://blog.aqnichol.com/feed.xml | High (technical) | Sporadic | Long-form technical posts; cited in TLDR Deep Dives when active. |
| `langchain_blog` | https://blog.langchain.com/rss/ | Medium | 3-6/week | Agent tooling launches and patterns. Some of it is product-marketing; pick selectively. |

### Notes on biases

- **Frontier-lab feeds skew positive.** OpenAI/Anthropic/DeepMind blogs are also marketing channels. The ranking model should still favor these (source credibility), but blurbs should describe what was actually shipped, not the lab's framing.
- **Hugging Face is high-volume.** Expect 5-15 entries per day. Most are not newsletter-worthy. The ranking model handles the filter; ingestion just pulls.
- **Substack noise.** Import AI and Latent Space are signal; many AI substacks aren't. Add new substacks with care.

## arXiv

Default categories scanned:
- `cs.AI` - general AI
- `cs.LG` - machine learning
- `cs.CL` - computational linguistics / NLP (most LLM papers land here)

Optionally add:
- `cs.CV` - for vision/multimodal heavy issues
- `cs.RO` - for robotics stories
- `stat.ML` - overlapping with cs.LG, lower volume

Each category pulls up to 50 most recent submissions in the trailing 36 hours. Most won't be newsletter-worthy; the ranking model will down-weight pure theory papers without empirical results.

### arXiv-specific scoring notes

- arXiv abstracts are dense; the model should score by abstract content, not just title.
- Papers without code or weights typically don't make it into TLDR unless the result is exceptional.
- Survey papers rarely score above ~50 unless the survey itself is the news.

## Hacker News

- `min_score`: 100 (default). Stories below this rarely have enough traction to matter.
- `lookback_hours`: 24. We want today's top stories, not yesterday's.
- Filter: title must contain one of the AI keyword tokens (`ingestion/hn.py`).

HN is the lowest-priority source in the dedup canonical-picking. It's useful for surfacing stories that broke on personal blogs or smaller outlets and then bubbled up - those are often Deep Dive candidates.

## Not yet implemented

These are sources TLDR clearly uses but we haven't wired up:

- **X / Twitter.** TLDR regularly cites threadreaderapp.com unrolls of viral tweets. Implementing this requires either X API (paid, rate-limited) or scraping nitter/threadreader.
- **arXiv-sanity / Papers With Code top.** Could add as a "quality filter" layer on top of raw arXiv.
- **GitHub trending.** Could surface fast-rising AI repos. Noisy without good filtering.
- **YouTube transcripts (e.g., Dwarkesh, Latent Space pods).** TLDR cites these. Would need a transcript pipeline.

If a story type keeps appearing in TLDR's actual issues but not in our top-30, the missing source is the most likely cause.

## Source priority for dedup

When the same story appears via multiple sources, the dedup module picks the canonical source using this priority (highest wins). See `dedup/cluster.py` for the actual map.

1. Frontier-lab first-party blog (OpenAI, Anthropic, DeepMind, Google Research, Meta AI) - 95-100
2. arXiv - 90
3. Trusted secondary (Simon Willison, Import AI, aqnichol) - 70-80
4. Other RSS - 60
5. HN - 40
