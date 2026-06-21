'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { MIN_PRESETS, STAGE_PRESETS } from '@/lib/funding-filters';
import { filterChipClass } from '@/lib/chip-classes';

/**
 * Two rows of toggle chips: stage tier + minimum amount. Each chip is a
 * pure URL shortcut — clicking sets/clears the relevant query param.
 * Single-select within each row. Source of truth for the chip metadata
 * is lib/funding-filters.ts so the server page can read it without
 * tripping the RSC client/server boundary.
 */
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

  return (
    <div className="flex gap-2 items-center flex-wrap text-[11px]">
      <span className="text-text-mute uppercase tracking-[0.06em] font-semibold mr-1">Stage</span>
      {STAGE_PRESETS.map((s) => (
        <button
          key={s.key}
          onClick={() => toggle('stage', s.key, stage)}
          className={filterChipClass(stage === s.key)}
        >
          {s.label}
        </button>
      ))}
      <span className="text-text-mute uppercase tracking-[0.06em] font-semibold mr-1 ml-3">Min</span>
      {MIN_PRESETS.map((m) => (
        <button
          key={m.key}
          onClick={() => toggle('min', m.key, min)}
          className={filterChipClass(min === m.key)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
