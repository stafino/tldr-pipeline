'use client';

import { useRouter, useSearchParams } from 'next/navigation';

export default function BacktestPicker({
  newsletters,
  dates,
  defaultDate,
  defaultNl,
}: {
  newsletters: Record<string, string>;
  dates: string[];
  defaultDate: string;
  defaultNl: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  function update(key: string, value: string) {
    const next = new URLSearchParams(sp.toString());
    next.set(key, value);
    router.push('?' + next.toString());
  }
  return (
    <div className="flex gap-3 mb-3">
      <select
        defaultValue={defaultDate}
        onChange={(e) => update('date', e.target.value)}
        className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 outline-none"
      >
        {dates.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </select>
      <select
        defaultValue={defaultNl}
        onChange={(e) => update('nl', e.target.value)}
        className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 outline-none"
      >
        {Object.entries(newsletters).map(([id, name]) => (
          <option key={id} value={id}>
            {name}
          </option>
        ))}
      </select>
    </div>
  );
}
