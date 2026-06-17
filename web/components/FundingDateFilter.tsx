'use client';

import { useRouter, useSearchParams } from 'next/navigation';

interface Preset {
  key: 'today' | 'yesterday' | 'this-week' | 'last-week';
  label: string;
}

const PRESETS: Preset[] = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'this-week', label: 'This week' },
  { key: 'last-week', label: 'Last week' },
];

function fmtChip(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  return `${dd}-${mm}`;
}

/**
 * todayISO is computed server-side so chip→URL math doesn't drift between
 * the server render and the user's local clock. The "presets" map deterministic
 * ranges off that anchor so they can be highlighted/clicked client-side.
 */
function computeRange(preset: Preset['key'], todayISO: string): { from: string; to: string } {
  const today = new Date(todayISO + 'T00:00:00Z');
  const toIso = (d: Date) => d.toISOString().slice(0, 10);
  const startOfIsoWeek = (d: Date) => {
    const day = d.getUTCDay(); // 0=Sun..6=Sat
    const diff = day === 0 ? 6 : day - 1; // back to Monday
    const mon = new Date(d);
    mon.setUTCDate(d.getUTCDate() - diff);
    return mon;
  };

  switch (preset) {
    case 'today':
      return { from: todayISO, to: todayISO };
    case 'yesterday': {
      const y = new Date(today);
      y.setUTCDate(y.getUTCDate() - 1);
      const iso = toIso(y);
      return { from: iso, to: iso };
    }
    case 'this-week': {
      const mon = startOfIsoWeek(today);
      const sun = new Date(mon);
      sun.setUTCDate(mon.getUTCDate() + 6);
      return { from: toIso(mon), to: toIso(sun) };
    }
    case 'last-week': {
      const mon = startOfIsoWeek(today);
      mon.setUTCDate(mon.getUTCDate() - 7);
      const sun = new Date(mon);
      sun.setUTCDate(mon.getUTCDate() + 6);
      return { from: toIso(mon), to: toIso(sun) };
    }
  }
}

function activePreset(
  from: string,
  to: string,
  todayISO: string,
): Preset['key'] | 'custom' {
  for (const p of PRESETS) {
    const r = computeRange(p.key, todayISO);
    if (r.from === from && r.to === to) return p.key;
  }
  return 'custom';
}

export default function FundingDateFilter({
  dates,
  from,
  to,
  todayISO,
}: {
  dates: string[]; // all dates with data, newest first
  from: string;
  to: string;
  todayISO: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  const active = activePreset(from, to, todayISO);

  function pushRange(nextFrom: string, nextTo: string) {
    const next = new URLSearchParams(sp.toString());
    next.delete('date'); // legacy single-day param
    next.set('from', nextFrom);
    next.set('to', nextTo);
    router.push('?' + next.toString(), { scroll: false });
  }

  function pickPreset(preset: Preset['key']) {
    const r = computeRange(preset, todayISO);
    pushRange(r.from, r.to);
  }

  function setFrom(v: string) {
    // Keep range valid: if new From is after To, snap To to From.
    const nextTo = v > to ? v : to;
    pushRange(v, nextTo);
  }

  function setTo(v: string) {
    const nextFrom = v < from ? v : from;
    pushRange(nextFrom, v);
  }

  const chipClass = (key: Preset['key'] | 'custom') =>
    'px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors ' +
    (active === key
      ? 'bg-accent-soft text-text border-accent'
      : 'bg-surface text-text-dim border-border hover:bg-surface-hi hover:text-text');

  return (
    <div className="flex gap-2 items-center flex-wrap">
      {PRESETS.map((p) => (
        <button key={p.key} onClick={() => pickPreset(p.key)} className={chipClass(p.key)}>
          {p.label}
        </button>
      ))}
      <span className={chipClass('custom') + ' inline-flex items-center gap-2'}>
        <span>Custom</span>
        <select
          value={dates.includes(from) ? from : (dates[dates.length - 1] ?? from)}
          onChange={(e) => setFrom(e.target.value)}
          className="bg-bg border border-border text-text text-[11px] rounded px-1.5 py-0.5 outline-none"
        >
          {dates
            .slice()
            .reverse()
            .map((d) => (
              <option key={d} value={d}>
                {fmtChip(d)}
              </option>
            ))}
        </select>
        <span className="text-text-mute">→</span>
        <select
          value={dates.includes(to) ? to : dates[0]}
          onChange={(e) => setTo(e.target.value)}
          className="bg-bg border border-border text-text text-[11px] rounded px-1.5 py-0.5 outline-none"
        >
          {dates
            .slice()
            .reverse()
            .map((d) => (
              <option key={d} value={d}>
                {fmtChip(d)}
              </option>
            ))}
        </select>
      </span>
    </div>
  );
}
