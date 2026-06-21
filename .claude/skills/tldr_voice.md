---
name: tldr_voice
description: Voice canon for TLDR AI blurbs. Annotated examples extracted from real recent issues, used as few-shot context for blurb generation.
type: reference
---

# TLDR AI Voice

This is the canonical voice for blurbs in the AI newsletter. Match it exactly.

## What is distinctive

**Substance-forward.** The first sentence states what happened or what's true, not why it matters. "OpenAI announced X" or "This post presents Y", not "In a stunning move, OpenAI..." or "What if you could...?"

**Declarative, past or simple present.** No questions, no rhetorical flourish, no curiosity gaps. The reader is competent and time-constrained; respect that.

**Concrete over abstract.** Specific numbers (revenue figures, parameter counts, benchmark scores, percentages) when they exist. Named products, named labs, named techniques. Avoid "powerful", "revolutionary", "groundbreaking", "game-changing", "next-generation". These words don't appear.

**Two sentences, 40-65 words.** Sentence 1: the lede (what was shipped/announced/found). Sentence 2: the technical or commercial detail that makes it worth reading. Some Quick Links blurbs are 1 sentence and shorter; that's reserved for the lightest items.

**No em dashes.** Sentence breaks are full stops. Commas, colons, and semicolons fine.

**Tense.** Past for completed actions ("released", "announced", "introduced"). Present for descriptions of capabilities or what a post argues. Don't mix breathlessly.

**Source-aware framing.** A paper's blurb describes the method ("This post presents an algorithm that..."). A company announcement describes the deal or shipping fact ("OpenAI announced it would acquire X"). A think-piece describes the argument ("Both labs have started aggressively pricing their APIs.").

**Plain English nouns over jargon stacks.** "Compute capacity" beats "high-density inference substrate". Jargon is fine when it's the actual technical term (QAT, microVM, MCP).

## Examples

### Headlines & Launches (corporate news, product ships)

**Example 1 - Acquisition**
> OpenAI announced it would acquire Ona to bring secure cloud execution and orchestration capabilities into the Codex platform. The technology is intended to support persistent, customer-controlled environments where agents can continue working across extended periods and sessions.

_Why this works: Sentence 1 states the deal and its purpose. Sentence 2 explains the strategic use case in plain terms. No hype._

**Example 2 - Infrastructure deal**
> Google signed a cloud service agreement with SpaceX for access to AI compute capacity tied to roughly 110,000 NVIDIA GPUs. The deal was framed as bridge capacity for rising Gemini Enterprise demand while Google expanded its own infrastructure.

_Why this works: Concrete number (110k GPUs). Sentence 2 gives the "why" without editorializing - uses the company's own framing._

**Example 3 - Policy / government**
> OpenAI and the Trump administration discussed a possible government stake in the company through donated equity. The proposal was tied to a broader "Public Wealth Fund" concept that could let citizens benefit from AI-driven economic gains.

_Why this works: Neutral on a politically charged story. States the fact, then the proposed mechanism. No moralizing._

**Example 4 - Product launch**
> Microsoft Scout is an always-on agent for Frontier program users that enhances automation in the Microsoft 365 stack. Scout offers multi-step routines, integrates with local files, and supports OpenAI and Anthropic models.

_Why this works: Defines the product (sentence 1) then lists three concrete capabilities (sentence 2)._

**Example 5 - Funding round**
> Cognition raised over $1B at a $26B valuation, with significant backing from major investors to expand Devin, an AI software engineer. Devin has significantly cut project times and improved automation for clients like Mercedes-Benz and Itaú.

_Why this works: Numbers in sentence 1. Named customers in sentence 2 make it credible without becoming a press release._

**Example 6 - Open release**
> Biohub has made its open discovery engine for protein structure prediction, design, and biological discovery available to researchers everywhere. The release includes ESMC, a state-of-the-art language model that has internalized the fundamental properties that govern protein biology, and ESMFold2, a design engine that transforms ESMC's sequence representations into atomically-resolved 3D structures.

_Why this works: Comma-separated triplet ("prediction, design, and biological discovery") used precisely. Names the specific models being released._

### Deep Dives & Analysis (think-pieces, technical posts)

**Example 7 - Editorial / market view**
> Both Anthropic and OpenAI have started aggressively pricing their APIs. This is likely because they have found product-market fit with coding/general-purpose agent products, and companies spending over $200 per month per user helps these businesses cover their costs much better than charging $10 to $20 per month per user.

_Why this works: States the observed fact, then gives the most likely cause. Specific price points._

**Example 8 - Cost analysis**
> LLM-assisted coding isn't likely to be affordable anytime soon. While it can enable developers to create things they never would have otherwise been able to before, it isn't economically viable for most use cases, and developers need to prepare for costs to continue rising and build more resilient systems.

_Why this works: Counterintuitive claim up front. Sentence 2 gives the practical implication. No "must read" framing._

**Example 9 - Research paper / arXiv-style**
> Frontier AI models are typically trained on sequences of integers known as tokens. Each token refers to some sequence of bytes, and these byte sequences often correspond to common words; this post presents an algorithm that can compute an optimal tokenizer in some settings.

_Why this works: Gives a one-line technical primer so non-experts follow, then states what the paper contributes._

**Example 10 - Personal project writeup**
> This post shares how a developer created their own LLM from scratch. It covers how they built their own pre-training and fine-tuning scripts, data processing pipelines, and custom dataset, with a total project cost of around $80.

_Why this works: Lead is the topic, not the author's emotions. Lists what's covered. Concrete cost number._

**Example 11 - Technical-economic argument**
> CoreWeave's co-founder Brannin McBee recently claimed that compute isn't fungible the way a commodity has to be. He has a real argument, but the non-commodity framing is the keystone of his company's value, so while he appears to be saying that there is no market, he's actually pricing the market and revealing where the spread still hides.

_Why this works: Takes a strong analytical stance without breathlessness. Long second sentence, but every clause does work._

**Example 12 - Model technique**
> Google released Gemma 4 checkpoints optimized with Quantization-Aware Training (QAT) to enhance efficiency on mobile and laptops. QAT minimizes performance loss during model compression, enabling models to run on everyday edge devices.

_Why this works: Names the technique (QAT), expands the acronym, then explains why it matters in 8 words._

**Example 13 - Capability demonstration**
> Anthropic's AI model Claude performs well in predicting NMR spectra, matching and sometimes surpassing traditional tools like ChemDraw and MestReNova. Opus 4.7 accurately predicted hydrogen and carbon shifts on average and demonstrated consistency in replicating results.

_Why this works: Specific benchmark (NMR spectra), specific comparisons (ChemDraw, MestReNova), specific model version (Opus 4.7)._

### Engineering & Research (developer tools, technical releases)

**Example 14 - Tool launch**
> LangSmith introduces Sandboxes, hardware-virtualized microVMs that provide AI agents with their own secure computing environment, directly addressing the risks of running untrusted code. These sandboxes allow agents to execute dynamic tasks, manage persistent state, and run complex workflows without compromising production infrastructure.

_Why this works: Names the technology (microVMs) and the problem it solves. Sentence 2 enumerates capabilities without padding._

**Example 15 - Console / platform update**
> Amazon Bedrock has introduced a new console optimized for Anthropic and OpenAI-compatible APIs, facilitating easier model selection and deployment. It features a comprehensive model catalog, project-based workflows, and live documentation with automatic code snippets.

_Why this works: Standard product-update template. Notice the lack of "easy-to-use", "intuitive", "seamless"._

**Example 16 - Safety / security feature**
> OpenAI introduced Lockdown Mode to reduce exposure to prompt injection attacks from webpages and external content. The feature disables live browsing, web image retrieval, deep research, and agent mode while keeping some cached content and image-generation functionality available.

_Why this works: Names the threat model. Lists exactly what's disabled. No marketing softness._

**Example 17 - Specialized model**
> Apex is a React Native coding model trained to build apps by analyzing architecture decisions, fixing framework-specific issues, and reasoning about constraints. While it doesn't match frontier models on coding benchmarks, the optimized model significantly alters the performance-to-cost ratio within its specific domain.

_Why this works: Sets the right expectation explicitly ("doesn't match frontier models") rather than overclaiming. That honesty is on-voice._

**Example 18 - Research framework**
> NVIDIA's LocateAnything is a vision-language grounding framework that decodes bounding boxes in parallel rather than token-by-token.

_Why this works: One sentence. Names what's novel about it (parallel decoding vs token-by-token). Quick Links length._

### Miscellaneous (industry / policy)

**Example 19 - Geopolitics**
> Nvidia will invest $150 billion a year to make sure that Taiwan remains at the epicenter of the AI revolution. The investment is aimed at cementing Taiwan as the world's tech manufacturing hub long term and includes a new Nvidia headquarters in Taiwan to expand its partnership with TSMC.

_Why this works: Big number. Concrete actions (new HQ, TSMC partnership). No commentary on whether this is good or bad._

**Example 20 - Capability rumor / future claim**
> Google DeepMind CEO Demis Hassabis now predicts AGI could be achieved by 2029-30, accelerating from his earlier estimate of 2030-2035.

_Why this works: One sentence. Names the person, the claim, and the delta from his prior statement. That comparison is the news._

### Quick Links (one sentence, often)

**Example 21 - Tool/repo pointer**
> SkillSpector, developed by NVIDIA, scans AI agent skills for security vulnerabilities before installation.

_Why this works: Subject, source, function. Done in one line._

**Example 22 - Editorial micro-take**
> The gross margins on subscriptions are way worse than API overall, so labs will likely start withholding new features or models from subscription plans.

_Why this works: A single claim with its consequence. No "interesting thread on X" framing - surfaces the actual idea._

## Anti-patterns (do not produce these)

- "This is huge for the AI industry." - Don't tell the reader what to feel.
- "Get ready to see..." / "Coming soon..." - Promotional copy register.
- "Researchers have unveiled..." - "Unveiled" is press-release vocabulary; prefer "released", "introduced", "shared".
- "In a groundbreaking move..." - Stop.
- Em dashes as drama markers - use a period and start a new sentence instead.
- "But what if..." or rhetorical questions - never lead with these.
- Excessive hedging: "could potentially possibly..." - pick one degree of certainty.
- Listing 5+ comma-separated features in a quick aside - pick the 2-3 strongest and cut the rest.
