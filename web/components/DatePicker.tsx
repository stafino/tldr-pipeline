'use client';

import { useRouter, useSearchParams } from 'next/navigation';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function todayUTCISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtLabel(iso: string): string {
  if (iso === 'All') return 'All dates';
  const today = todayUTCISO();
  // Parse the iso (YYYY-MM-DD) as a UTC date so weekday math stays
  // consistent with the UTC publish-date filter buckets.
  const d = new Date(iso + 'T00:00:00Z');
  const dd = iso.slice(8, 10);
  const mm = iso.slice(5, 7);
  const yyyy = iso.slice(0, 4);
  const weekday = WEEKDAYS[d.getUTCDay()];
  const human = `${dd}-${mm}-${yyyy}`;
  if (iso === today) return `Today · ${human}`;
  return `${weekday} · ${human}`;
}

export default function DatePicker({
  dates,
  value,
  allowAll = true,
}: {
  dates: string[];
  value: string;
  allowAll?: boolean;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(sp.toString());
    next.set('date', e.target.value);
    router.push('?' + next.toString(), { scroll: false });
  }
  return (
    <label className="inline-flex items-center gap-2 text-[11px] text-text-mute uppercase tracking-[0.06em] font-semibold">
      <span>Filter by date</span>
      <select
        value={value}
        onChange={onChange}
        className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 focus:border-accent outline-none normal-case font-normal tracking-normal"
      >
        {allowAll && <option value="All">All dates</option>}
        {dates.map((d) => (
          <option key={d} value={d}>
            {fmtLabel(d)}
          </option>
        ))}
      </select>
    </label>
  );
}
