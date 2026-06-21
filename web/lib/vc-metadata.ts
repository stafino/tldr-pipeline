/**
 * VC type / sector / region label registries.
 *
 * Previously copy-pasted across vc/page.tsx, vc/issue/page.tsx,
 * vc/preview/page.tsx, vc/recap/page.tsx. Centralized here so a
 * relabel (e.g. adding a new section emoji) edits one place.
 */

import type { VcRegion, VcSector, VcType } from '@/lib/types';

export const TYPE_LABELS: Record<
  VcType,
  { label: string; emoji: string; color: string }
> = {
  fund_news: {
    label: 'Fund news',
    emoji: '💰',
    color: 'bg-ok-soft text-ok border-ok',
  },
  partner_move: {
    label: 'Partner moves',
    emoji: '🪑',
    color: 'bg-accent-soft text-accent border-accent',
  },
  exit: {
    label: 'Exits',
    emoji: '🚪',
    color: 'bg-purple-900/40 text-purple-300 border-purple-700',
  },
  market_signal: {
    label: 'Market signals',
    emoji: '📈',
    color: 'bg-warn-soft text-warn border-warn',
  },
  opinion: {
    label: 'Opinion',
    emoji: '💭',
    color: 'bg-surface text-text-dim border-border',
  },
  regulatory: {
    label: 'Regulatory',
    emoji: '⚖️',
    color: 'bg-no-soft text-no border-no',
  },
};

export const TYPES_ORDER: VcType[] = [
  'fund_news',
  'partner_move',
  'exit',
  'market_signal',
  'opinion',
  'regulatory',
];

export const SECTOR_LABELS: Record<VcSector, { label: string; emoji: string }> = {
  ai: { label: 'AI', emoji: '🤖' },
  fintech: { label: 'Fintech', emoji: '💳' },
  crypto: { label: 'Crypto', emoji: '⛓️' },
  climate: { label: 'Climate', emoji: '🌱' },
  biotech: { label: 'Biotech', emoji: '🧬' },
  enterprise: { label: 'Enterprise', emoji: '🏢' },
  consumer: { label: 'Consumer', emoji: '🛍️' },
  deeptech: { label: 'Deep tech', emoji: '🔬' },
  other: { label: 'Other', emoji: '·' },
};

export const SECTORS_ORDER: VcSector[] = [
  'ai',
  'fintech',
  'crypto',
  'enterprise',
  'deeptech',
  'climate',
  'biotech',
  'consumer',
  'other',
];

export const REGION_LABELS: Record<VcRegion, { label: string; flag: string }> = {
  NA: { label: 'North America', flag: '🇺🇸' },
  EU: { label: 'Europe', flag: '🇪🇺' },
  ASIA: { label: 'Asia', flag: '🌏' },
  GLOBAL: { label: 'Global', flag: '🌐' },
  OTHER: { label: 'Other', flag: '·' },
};

export const REGIONS_ORDER: VcRegion[] = ['NA', 'EU', 'ASIA', 'GLOBAL', 'OTHER'];

/**
 * The "TLDR-VC issue" section layout - same shape used by /vc/issue and
 * /vc/recap. `cap` is the per-section story limit; recap uses higher
 * caps than the daily issue.
 */
export interface IssueSection {
  key: VcType;
  emoji: string;
  name: string;
  tagline: string;
  cap: number;
}

export const ISSUE_SECTIONS: IssueSection[] = [
  { key: 'fund_news',     emoji: '💰', name: 'Funds & LPs',    tagline: 'Launches, closes, LP commits', cap: 4 },
  { key: 'exit',          emoji: '🚪', name: 'Exits & IPOs',   tagline: 'IPOs, M&A, secondaries',       cap: 4 },
  { key: 'partner_move',  emoji: '🪑', name: 'People & Moves', tagline: 'Hires, exits, board changes',  cap: 3 },
  { key: 'market_signal', emoji: '📈', name: 'Market Signals', tagline: 'Trends, performance, vintage', cap: 3 },
  { key: 'opinion',       emoji: '💭', name: 'Opinion',        tagline: 'Essays, predictions',          cap: 2 },
  { key: 'regulatory',    emoji: '⚖️', name: 'Regulatory',     tagline: 'SEC, antitrust, fund rules',   cap: 2 },
];
