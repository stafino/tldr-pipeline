/**
 * Shared formatters for /funding and /vc views.
 *
 * Previously duplicated across 3 files (funding/page.tsx,
 * FundingDetailPane.tsx, vc/page.tsx). Identical logic - pulled here.
 */

/**
 * "$5B" / "$60M" / "$300K" / "-". Matches Crunchbase News convention.
 */
export function formatUsd(usd: number | null, raw: string = ''): string {
  if (!usd) return raw || '-';
  if (usd >= 1_000_000_000)
    return `$${(usd / 1_000_000_000).toFixed(usd >= 10_000_000_000 ? 0 : 1)}B`;
  if (usd >= 1_000_000) return `$${Math.round(usd / 1_000_000)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `$${usd}`;
}

/**
 * Dealroom-style relative timestamp: "today" / "yesterday" / "Nd ago"
 * / "Nw ago" / short date for anything older than 30 days.
 * Computed UTC for both arguments to avoid TZ drift.
 */
export function relativeDate(iso: string, todayISO: string): string {
  if (!iso) return '';
  const r = new Date((iso.slice(0, 10) || todayISO) + 'T00:00:00Z').getTime();
  const t = new Date(todayISO + 'T00:00:00Z').getTime();
  const days = Math.round((t - r) / (24 * 60 * 60 * 1000));
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return new Date((iso.slice(0, 10) || todayISO) + 'T00:00:00Z').toLocaleDateString(
    'en-GB',
    { day: '2-digit', month: 'short', timeZone: 'UTC' },
  );
}

/**
 * Funding-round stage tier - used to colour-code chips.
 *   - Pre-seed / Seed → "early" (green)
 *   - Series A / B → "growth" (blue)
 *   - Series C+ / pre-IPO / growth → "late" (purple)
 *   - Extension / bridge → "ext" (amber)
 *   - Anything else → "other" (neutral)
 */
export type StageTier = 'early' | 'growth' | 'late' | 'ext' | 'other';

export function classifyFundingStage(
  label: string,
): { short: string; tier: StageTier } {
  const t = (label || '').trim().toLowerCase();
  if (!t) return { short: '', tier: 'other' };
  if (t.includes('pre-seed') || t.includes('preseed'))
    return { short: 'Pre-seed', tier: 'early' };
  if (t === 'seed' || t.startsWith('seed ') || t.includes('seed round'))
    return { short: 'Seed', tier: 'early' };
  const m = t.match(/series\s+([a-h])/);
  if (m) {
    const letter = m[1].toUpperCase();
    const tier: 'growth' | 'late' = ['A', 'B'].includes(letter) ? 'growth' : 'late';
    return { short: `Series ${letter}`, tier };
  }
  if (t.includes('extension')) return { short: 'Extension', tier: 'ext' };
  if (t.includes('bridge')) return { short: 'Bridge', tier: 'ext' };
  if (t.includes('growth')) return { short: 'Growth', tier: 'late' };
  if (t.includes('pre-ipo') || t.includes('pre ipo'))
    return { short: 'Pre-IPO', tier: 'late' };
  if (t.includes('strategic')) return { short: 'Strategic', tier: 'other' };
  return { short: label.length > 12 ? label.slice(0, 12) + '…' : label, tier: 'other' };
}

export function stageChipClass(tier: StageTier): string {
  switch (tier) {
    case 'early':
      return 'bg-ok-soft text-ok border-ok';
    case 'growth':
      return 'bg-accent-soft text-accent border-accent';
    case 'late':
      return 'bg-purple-900/40 text-purple-300 border-purple-700';
    case 'ext':
      return 'bg-warn-soft text-warn border-warn';
    default:
      return 'bg-surface text-text-dim border-border';
  }
}

/** "today" in UTC, YYYY-MM-DD. */
export function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}
