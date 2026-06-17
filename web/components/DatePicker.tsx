'use client';

import { useRouter, useSearchParams } from 'next/navigation';

export default function DatePicker({ dates, value }: { dates: string[]; value: string }) {
  const router = useRouter();
  const sp = useSearchParams();
  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(sp.toString());
    next.set('date', e.target.value);
    router.push('?' + next.toString());
  }
  return (
    <select
      value={value}
      onChange={onChange}
      className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 focus:border-accent outline-none"
    >
      <option value="All">All</option>
      {dates.map((d) => (
        <option key={d} value={d}>
          {d}
        </option>
      ))}
    </select>
  );
}
