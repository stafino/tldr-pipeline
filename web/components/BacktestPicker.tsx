'use client';

import { useRouter, useSearchParams } from 'next/navigation';

export default function BacktestPicker({
  newsletters,
  defaultNl,
  includeAll = false,
  inline = false,
}: {
  newsletters: Record<string, string>;
  defaultNl: string;
  includeAll?: boolean;
  inline?: boolean;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  function update(key: string, value: string) {
    const next = new URLSearchParams(sp.toString());
    next.set(key, value);
    router.push('?' + next.toString(), { scroll: false });
  }
  return (
    <div className={inline ? 'inline-flex items-center' : 'flex gap-3 mb-3 items-center'}>
      <label className="inline-flex items-center gap-2 text-[11px] text-text-mute uppercase tracking-[0.06em] font-semibold">
        <span>Newsletter</span>
        <select
          value={defaultNl}
          onChange={(e) => update('nl', e.target.value)}
          className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 outline-none normal-case font-normal tracking-normal"
        >
          {includeAll && <option value="all">All newsletters</option>}
          {Object.entries(newsletters).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
