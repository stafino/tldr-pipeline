export interface Story {
  title: string;
  url: string;
  source: string;
  source_type: string;
  published_at: string;
  raw_text?: string;
  source_topics?: string[];
}

export interface Assignment {
  newsletter: string;
  section_id: string;
  score: number;
}

export interface ScoredStory {
  story: Story;
  score: number;
  reasoning: string;
  is_technical: boolean;
  is_novel: boolean;
  is_mainstream_relevant: boolean;
  assignments: Assignment[];
  components?: Record<string, number>;
  boosts?: Record<string, number>;
  hn_points?: number;
  hn_comments?: number;
}

export interface Blurb {
  story_url: string;
  title: string;
  newsletter: string;
  section_id: string;
  blurb: string;
  word_count: number;
  minute_read: number;
  needs_review?: boolean;
}

export interface Section {
  id: string;
  name: string;
  emoji: string;
  min_words: number;
  max_words: number;
  target_count: number;
  description: string;
}

export interface Newsletter {
  id: string;
  brand_name: string;
  voice_skill: string;
  sections: Section[];
  topics: string[];
  edition_size: number;
}

export interface PredictionMatch {
  rank: number;
  score: number;
  title: string;
  url: string;
  matched_tldr_idx: number | null;
  similarity: number | null;
}

export interface BacktestResult {
  date: string;
  newsletter: string;
  fetched_at: string;
  tldr_titles: string[];
  tldr_matched: boolean[];
  predictions: PredictionMatch[];
  recall_at: Record<string, number>;
  hits_at: Record<string, number>;
  available: boolean;
  tldr_urls?: string[];
  tldr_domains?: string[];
}

export type DecisionStatus = 'pending' | 'approved' | 'rejected';

export interface Decision {
  story_url: string;
  newsletter: string;
  status: DecisionStatus;
  edited_blurb?: string;
}

export type FundingRegion = 'EU' | 'NA' | 'OTHER';

export type VcType =
  | 'fund_news'
  | 'partner_move'
  | 'exit'
  | 'market_signal'
  | 'opinion'
  | 'regulatory';

export type VcRegion = 'NA' | 'EU' | 'ASIA' | 'GLOBAL' | 'OTHER';

export type VcSector =
  | 'ai'
  | 'fintech'
  | 'crypto'
  | 'climate'
  | 'biotech'
  | 'enterprise'
  | 'consumer'
  | 'deeptech'
  | 'other';

export interface VcArticle {
  story_url: string;
  title: string;
  source: string;
  published_at: string;
  is_vc: boolean;
  vc_type: VcType;
  headline_summary: string;
  firms: string[];
  people: string[];
  region: VcRegion;
  sector?: VcSector; // optional for backwards-compat with rows written
                     // before the schema added it; UI treats missing as 'other'
  blurb?: string;    // 60-80 word LLM summary; optional for back-compat
}

export interface FundingRound {
  story_url: string;
  title: string;
  source: string;
  published_at: string;
  // YYYY-MM-DD - when the round was actually announced/closed. Set by the
  // LLM extractor from the article body, falling back to the article's
  // publish date when no explicit signal is found. This is the date the
  // /funding UI filters on.
  raised_date: string;
  company: string;
  amount_usd: number | null;
  amount_raw: string;
  round_label: string;
  country: string;
  region: FundingRegion;
  investors: string[];
  valuation_usd: number | null;
}
