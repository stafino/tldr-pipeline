/**
 * Filter-chip metadata for /funding. Lives in a plain module (no
 * 'use client') so both the server page and the client filter component
 * can import the same source of truth without crossing the RSC barrier.
 *
 * Next.js silently strips non-component exports from "use client" files,
 * so importing minUsdFromKey from FundingFilterChips.tsx into the
 * server page raises "is not a function" at request time.
 */

export interface StagePreset {
  key: string;
  label: string;
}

export interface MinPreset {
  key: string;
  label: string;
  usd: number;
}

export const STAGE_PRESETS: StagePreset[] = [
  { key: 'early', label: 'Early' },
  { key: 'growth', label: 'Growth' },
  { key: 'late', label: 'Late' },
  { key: 'ext', label: 'Extension' },
];

export const MIN_PRESETS: MinPreset[] = [
  { key: '10m', label: '$10M+', usd: 10_000_000 },
  { key: '50m', label: '$50M+', usd: 50_000_000 },
  { key: '100m', label: '$100M+', usd: 100_000_000 },
  { key: '500m', label: '$500M+', usd: 500_000_000 },
];

export function minUsdFromKey(key: string): number {
  const m = MIN_PRESETS.find((x) => x.key === key);
  return m ? m.usd : 0;
}
