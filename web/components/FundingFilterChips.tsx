'use client';

import { useRouter, useSearchParams } from 'next/navigation';

/**
 * Two rows of toggle chips: stage tier + minimum amount. Each chip is a
 * pure URL shortcut — clicking sets/clears the relevant query param.
 * Dealroom uses similar $100M+ quick-filters; Crunchbase News round-ups
 * cluster by stage. Mirror both.
 */
const STAGES: { key: string; label: string }[] = [
  { key: 'early', label: 'Early' },
  { key: 'growth', label: 'Growth' },
  { key: 'late', label: 'Late' },
  { key: 'ext', label: 'Extension' },
];

const MINS: { key: string; label: string; usd: number }[] = [
  { key: '10m', label: '$10M+', usd: 10_000_000 },
  { key: '50m', label: '$50M+', usd: 50_000_000 },
  { key: '100m', label: '$100M+', usd: 100_000_000 },
  { key: '500m', label: '$500M+', usd: 500_000_000 },
];

export default function FundingFilterChips({
  stage,
  min,
}: {
  stage: string;
  min: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();

  function toggle(param: string, value: string, currentValue: string) {
    const next = new URLSearchParams(sp.toString());
    if (currentValue === value) next.delete(param);
    else next.set(param, value);
    router.push('?' + next.toString(), { scroll: false });
  }

  const chipClass = (active: boolean) =>
    'px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors ' +
    (active
      ? 'bg-accent-soft text-text border-accent'
      : 'bg-surface text-text-dim border-border hover:bg-surface-hi hover:text-text');

  return (
    <div className="flex gap-2 items-center flex-wrap text-[11px]">
      <span className="text-text-mute uppercase tracking-[0.06em] font-semibold mr-1">Stage</span>
      {STAGES.map((s) => (
        <button
          key={s.key}
          onClick={() => toggle('stage', s.key, stage)}
          className={chipClass(stage === s.key)}
        >
          {s.label}
        </button>
      ))}
      <span className="text-text-mute uppercase tracking-[0.06em] font-semibold mr-1 ml-3">Min</span>
      {MINS.map((m) => (
        <button
          key={m.key}
          onClick={() => toggle('min', m.key, min)}
          className={chipClass(min === m.key)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

export function minUsdFromKey(key: string): number {
  const m = MINS.find((x) => x.key === key);
  return m ? m.usd : 0;
}
