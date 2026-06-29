/**
 * Internal ranking for funding rounds.
 *
 * Absolute dollars are deliberately NOT the primary signal. A round is scored
 * by how large it is *for its stage*, so a strong early round can out-rank a
 * routine late one: $30M Series A > $10M Series A, while $30M Series A is not
 * automatically below $300M Series D (both are ~2x their stage norm).
 *
 * Score = stage-relative amount (main) + investor breadth + valuation richness.
 * Fully deterministic, no LLM. Used to sort the Funding tab and to pick the
 * top 5 per region for the Monday Raises edition.
 */
import { classifyFundingStage } from '@/lib/formatters';
import type { FundingRound } from '@/lib/types';

/** Typical round size by stage (USD). The yardstick each round is measured against. */
const STAGE_BASELINE_USD: Record<string, number> = {
  'pre-seed': 2_000_000,
  seed: 5_000_000,
  'series a': 15_000_000,
  'series b': 40_000_000,
  'series c': 80_000_000,
  'series d': 150_000_000,
  'series e': 200_000_000,
  'series f': 250_000_000,
  'series g': 300_000_000,
  'series h': 350_000_000,
  growth: 300_000_000,
  'pre-ipo': 400_000_000,
  extension: 20_000_000,
  bridge: 10_000_000,
  strategic: 50_000_000,
};
const DEFAULT_BASELINE_USD = 30_000_000; // unknown/blank stage: neutral mid-size

function clamp(x: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, x));
}

export function fundingScore(r: FundingRound): number {
  const stage = classifyFundingStage(r.round_label).short.toLowerCase();
  const baseline = STAGE_BASELINE_USD[stage] ?? DEFAULT_BASELINE_USD;

  // Main signal: round size relative to its stage norm. log2 so 2x = +1, half
  // = -1. A round with no stated amount sinks toward the bottom.
  const amount = r.amount_usd ?? 0;
  const stageRel = amount > 0 ? clamp(Math.log2(amount / baseline), -3, 4) : -2;

  // Investor breadth - named backers, saturating at 6.
  const investorSig = Math.min(r.investors.length, 6) / 6;

  // Valuation richness for the stage (valuations run ~10x round size). Modest weight.
  const valRel =
    r.valuation_usd && r.valuation_usd > 0
      ? clamp(Math.log2(r.valuation_usd / (baseline * 10)), -3, 4)
      : 0;

  return 1.0 * stageRel + 0.8 * investorSig + 0.5 * valRel;
}

/** Sort a list of rounds by score, descending (highest-ranked first). */
export function byFundingScore(a: FundingRound, b: FundingRound): number {
  return fundingScore(b) - fundingScore(a);
}
