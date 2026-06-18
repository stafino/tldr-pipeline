import Link from 'next/link';
import {
  listAvailableDates,
  listFundingDates,
  loadBlurbsAll,
  loadFundingRange,
} from '@/lib/data';
import Nav from '@/components/Nav';
import FundingDateFilter from '@/components/FundingDateFilter';
import FundingFilterChips, { minUsdFromKey } from '@/components/FundingFilterChips';
import FundingDetailPane from '@/components/FundingDetailPane';
import type { Blurb, FundingRound } from '@/lib/types';

export const dynamic = 'force-dynamic';

function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatAmount(usd: number | null, raw: string): string {
  if (!usd) return raw || '—';
  if (usd >= 1_000_000_000) return `$${(usd / 1_000_000_000).toFixed(usd >= 10_000_000_000 ? 0 : 1)}B`;
  if (usd >= 1_000_000) return `$${Math.round(usd / 1_000_000)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `$${usd}`;
}

/**
 * Normalize a free-form round_label into a short chip code + a stage tier
 * so we can color-code stages consistently:
 *   - "early" (pre-seed, seed) → green
 *   - "growth" (A / B) → blue
 *   - "late" (C+ / pre-IPO / growth) → purple
 *   - "extension" → amber
 *   - "strategic" / fallback → neutral
 */
function classifyStage(label: string): { short: string; tier: 'early' | 'growth' | 'late' | 'ext' | 'other' } {
  const t = (label || '').trim().toLowerCase();
  if (!t) return { short: '', tier: 'other' };
  if (t.includes('pre-seed') || t.includes('preseed')) return { short: 'Pre-seed', tier: 'early' };
  if (t === 'seed' || t.startsWith('seed ') || t.includes('seed round')) return { short: 'Seed', tier: 'early' };
  const m = t.match(/series\s+([a-h])/);
  if (m) {
    const letter = m[1].toUpperCase();
    const tier: 'growth' | 'late' = ['A', 'B'].includes(letter) ? 'growth' : 'late';
    return { short: `Series ${letter}`, tier };
  }
  if (t.includes('extension')) return { short: 'Extension', tier: 'ext' };
  if (t.includes('bridge')) return { short: 'Bridge', tier: 'ext' };
  if (t.includes('growth')) return { short: 'Growth', tier: 'late' };
  if (t.includes('pre-ipo') || t.includes('pre ipo')) return { short: 'Pre-IPO', tier: 'late' };
  if (t.includes('strategic')) return { short: 'Strategic', tier: 'other' };
  return { short: label.length > 12 ? label.slice(0, 12) + '…' : label, tier: 'other' };
}

function stageChipClass(tier: 'early' | 'growth' | 'late' | 'ext' | 'other'): string {
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

function Row({
  r,
  selected,
  hrefQuery,
}: {
  r: FundingRound;
  selected: boolean;
  hrefQuery: string;
}) {
  return (
    <Link
      href={hrefQuery}
      scroll={false}
      className={
        'block border-b border-border py-3 px-3 cursor-pointer transition-colors ' +
        (selected
          ? 'bg-accent-soft border-l-2 border-l-accent pl-2.5'
          : 'hover:bg-surface')
      }
    >
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[13px] font-bold text-warn shrink-0 w-[68px]">
          {formatAmount(r.amount_usd, r.amount_raw)}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[14px] font-semibold text-text">
              {r.company || '(unknown company)'}
            </span>
            {(() => {
              const stage = classifyStage(r.round_label);
              if (!stage.short) return null;
              return (
                <span
                  className={`font-mono text-[10px] uppercase tracking-[0.05em] px-1.5 py-0.5 rounded border ${stageChipClass(stage.tier)}`}
                >
                  {stage.short}
                </span>
              );
            })()}
            {r.country && (
              <span className="font-mono text-[10.5px] text-text-mute">· {r.country}</span>
            )}
          </div>
          {r.investors.length > 0 && (
            <div className="text-[11px] text-text-dim mt-0.5 truncate">
              {r.investors.slice(0, 3).join(', ')}
              {r.investors.length > 3 ? `, +${r.investors.length - 3}` : ''}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}

function Column({
  label,
  rows,
  selectedUrl,
  hrefForRow,
}: {
  label: string;
  rows: FundingRound[];
  selectedUrl?: string;
  hrefForRow: (r: FundingRound) => string;
}) {
  const total = rows.reduce((sum, r) => sum + (r.amount_usd ?? 0), 0);
  return (
    <div>
      <div className="flex items-baseline gap-3 pb-2 mb-1 border-b border-border-strong px-3">
        <h2 className="text-[12px] uppercase tracking-[0.08em] font-bold text-warn m-0">{label}</h2>
        <span className="text-[11px] text-text-mute ml-auto font-mono">
          {rows.length} {rows.length === 1 ? 'round' : 'rounds'}
          {total > 0 ? ` · ${formatAmount(total, '')} total` : ''}
        </span>
      </div>
      {rows.length === 0 ? (
        <div className="text-text-mute text-[12px] py-6 px-3">
          No {label} rounds for this date.
        </div>
      ) : (
        rows.map((r) => (
          <Row
            key={r.story_url}
            r={r}
            selected={selectedUrl === r.story_url}
            hrefQuery={hrefForRow(r)}
          />
        ))
      )}
    </div>
  );
}

function fmtRange(from: string, to: string): string {
  const fmt = (iso: string) =>
    new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      timeZone: 'UTC',
    });
  if (from === to) return fmt(from);
  return `${fmt(from)} → ${fmt(to)}`;
}

export default function FundingPage({
  searchParams,
}: {
  searchParams: { date?: string; from?: string; to?: string; story?: string; stage?: string; min?: string };
}) {
  const dates = listFundingDates();

  if (dates.length === 0) {
    return (
      <main>
        <Nav />
        <div className="px-6 py-10 text-text-mute text-[13px]">
          No funding data yet. The pipeline writes <code className="text-text font-mono">data/funding/&lt;date&gt;.jsonl</code> after each
          scrape; first one lands after the next cron run.
        </div>
      </main>
    );
  }

  const today = todayUTC();
  // Resolve the requested range. Priority:
  //   1. explicit ?from=&to= range params (new model)
  //   2. legacy ?date= param (kept for shareable links from before this change)
  //   3. default: today (which may be empty if cron hasn't caught up)
  let from: string;
  let to: string;
  if (searchParams.from && searchParams.to) {
    from = searchParams.from;
    to = searchParams.to;
    if (from > to) [from, to] = [to, from];
  } else if (searchParams.date) {
    from = to = searchParams.date;
  } else {
    from = to = today;
  }

  const stageFilter = (searchParams.stage ?? '').toLowerCase();
  const minFilter = (searchParams.min ?? '').toLowerCase();
  const minUsd = minUsdFromKey(minFilter);

  let rounds = loadFundingRange(from, to);
  if (stageFilter) {
    rounds = rounds.filter((r) => classifyStage(r.round_label).tier === stageFilter);
  }
  if (minUsd > 0) {
    rounds = rounds.filter((r) => (r.amount_usd ?? 0) >= minUsd);
  }
  const eu = rounds
    .filter((r) => r.region === 'EU')
    .sort((a, b) => (b.amount_usd ?? 0) - (a.amount_usd ?? 0));
  const na = rounds
    .filter((r) => r.region === 'NA')
    .sort((a, b) => (b.amount_usd ?? 0) - (a.amount_usd ?? 0));

  // Blurb lookup is global — a funding story is typically blurbed for
  // tldr_founders or tldr_fintech (sometimes both); we take whichever
  // shows up first when iterating across newsletters.
  const allBlurbs: Blurb[] = loadBlurbsAll(listAvailableDates());
  const blurbByUrl = new Map<string, Blurb>();
  for (const b of allBlurbs) {
    if (!blurbByUrl.has(b.story_url)) blurbByUrl.set(b.story_url, b);
  }

  const selectedRound = searchParams.story
    ? rounds.find((r) => r.story_url === searchParams.story) ?? null
    : null;
  const selectedBlurb = selectedRound ? blurbByUrl.get(selectedRound.story_url) : undefined;

  function hrefForRow(r: FundingRound): string {
    const next = new URLSearchParams();
    next.set('from', from);
    next.set('to', to);
    next.set('story', r.story_url);
    return '?' + next.toString();
  }

  return (
    <main>
      <Nav />
      <div className="flex flex-col gap-2 px-5 py-3 border-b border-border">
        <FundingDateFilter dates={dates} from={from} to={to} todayISO={today} />
        <FundingFilterChips stage={stageFilter} min={minFilter} />
        <div className="text-[10px] text-text-mute">
          {fmtRange(from, to)} · {rounds.length} {rounds.length === 1 ? 'round' : 'rounds'} · EU{' '}
          {eu.length} · NA {na.length}
          {(stageFilter || minFilter) && (
            <span className="ml-2 text-warn">· filters active</span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,_1fr)_minmax(0,_1fr)_minmax(0,_1fr)] gap-6 px-5 py-5">
        <Column label="🇪🇺 Europe" rows={eu} selectedUrl={selectedRound?.story_url} hrefForRow={hrefForRow} />
        <Column label="🇺🇸 North America" rows={na} selectedUrl={selectedRound?.story_url} hrefForRow={hrefForRow} />
        <div className="lg:border-l lg:border-border lg:pl-6 lg:sticky lg:top-0 lg:self-start lg:max-h-screen lg:overflow-y-auto">
          <FundingDetailPane round={selectedRound} blurb={selectedBlurb} />
        </div>
      </div>
    </main>
  );
}
