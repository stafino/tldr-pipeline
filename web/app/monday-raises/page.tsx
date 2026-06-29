import Link from 'next/link';
import { classifyFundingStage, formatUsd, todayUTC } from '@/lib/formatters';
import {
  listAvailableDates,
  listFundingDates,
  loadBlurbsAll,
  loadFundingRange,
} from '@/lib/data';
import Nav from '@/components/Nav';
import FundingDateFilter from '@/components/FundingDateFilter';
import MondayRaisesExport from '@/components/MondayRaisesExport';
import type { IssueDoc } from '@/lib/issue-formatters';
import type { Blurb, FundingRound } from '@/lib/types';

// Edge-cache each unique URL for 10 minutes, matching the other read tabs.
export const revalidate = 600;

// Own title/OG so the personal issue page doesn't inherit the tool's
// "TLDR ..." site metadata.
export const metadata = {
  // `absolute` bypasses the layout's "%s · TLDR curator" template so the
  // personal page carries no TLDR branding.
  title: { absolute: 'FF: Monday Raises' },
  description: 'EU and US startup funding rounds from last week.',
  openGraph: { title: 'FF: Monday Raises' },
  twitter: { title: 'FF: Monday Raises' },
};

const REGION_SECTIONS = [
  { key: 'EU', emoji: '🇪🇺', name: 'Europe', tagline: 'EU + UK rounds' },
  { key: 'NA', emoji: '🇺🇸', name: 'North America', tagline: 'US + Canada rounds' },
] as const;

/** Previous complete Monday→Sunday calendar week relative to todayISO. */
function previousWeek(todayISO: string): { from: string; to: string } {
  const d = new Date(todayISO + 'T00:00:00Z');
  const sinceMonday = (d.getUTCDay() + 6) % 7; // 0 = Monday
  const thisMonday = new Date(d);
  thisMonday.setUTCDate(d.getUTCDate() - sinceMonday);
  const prevMonday = new Date(thisMonday);
  prevMonday.setUTCDate(thisMonday.getUTCDate() - 7);
  const prevSunday = new Date(thisMonday);
  prevSunday.setUTCDate(thisMonday.getUTCDate() - 1);
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  return { from: iso(prevMonday), to: iso(prevSunday) };
}

function fmtRange(from: string, to: string): string {
  const fmt = (iso: string) =>
    new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      timeZone: 'UTC',
    });
  return from === to ? fmt(from) : `${fmt(from)} to ${fmt(to)}`;
}

function headlineFor(r: FundingRound): string {
  const stage = classifyFundingStage(r.round_label).short;
  const company = r.company || '(undisclosed company)';
  const amt = r.amount_usd || r.amount_raw ? formatUsd(r.amount_usd, r.amount_raw) : '';
  if (!amt) return `${company} raises a new round${stage ? ` (${stage})` : ''}`;
  return `${company} raises ${amt}${stage ? ` ${stage}` : ''}`;
}

/** Deterministic fallback when the round has no newsletter blurb. */
function generatedBlurb(r: FundingRound): string {
  const bits: string[] = [];
  if (r.country) bits.push(`Based in ${r.country}`);
  if (r.investors.length) bits.push(`investors include ${r.investors.slice(0, 4).join(', ')}`);
  if (r.valuation_usd) bits.push(`valued at ${formatUsd(r.valuation_usd)}`);
  if (bits.length === 0) {
    const stage = classifyFundingStage(r.round_label).short;
    return `${r.company || 'The company'} closed its ${stage || 'latest'} round.`;
  }
  const s = bits.join('; ');
  return s.charAt(0).toUpperCase() + s.slice(1) + '.';
}

export default function MondayRaisesPage({
  searchParams,
}: {
  searchParams: { from?: string; to?: string };
}) {
  const dates = listFundingDates();
  const today = todayUTC();

  if (dates.length === 0) {
    return (
      <main>
        <Nav />
        <div className="px-6 py-10 text-text-mute text-[13px]">
          No funding data yet. Monday Raises builds itself from{' '}
          <code className="text-text font-mono">data/funding/&lt;date&gt;.jsonl</code> once the
          pipeline has run.
        </div>
      </main>
    );
  }

  const def = previousWeek(today);
  let from = searchParams.from && searchParams.to ? searchParams.from : def.from;
  let to = searchParams.from && searchParams.to ? searchParams.to : def.to;
  if (from > to) [from, to] = [to, from];

  const rounds = loadFundingRange(from, to);

  // Blurb lookup is global - a funding story is typically blurbed for one
  // newsletter; take whichever shows up first when iterating across all.
  const allBlurbs: Blurb[] = loadBlurbsAll(listAvailableDates());
  const blurbByUrl = new Map<string, Blurb>();
  for (const b of allBlurbs) if (!blurbByUrl.has(b.story_url)) blurbByUrl.set(b.story_url, b);

  const byRegion: Record<'EU' | 'NA', FundingRound[]> = { EU: [], NA: [] };
  for (const r of rounds) {
    if (r.region === 'EU') byRegion.EU.push(r);
    else if (r.region === 'NA') byRegion.NA.push(r);
  }
  for (const k of ['EU', 'NA'] as const) {
    byRegion[k].sort((a, b) => (b.amount_usd ?? 0) - (a.amount_usd ?? 0));
  }

  const total = byRegion.EU.length + byRegion.NA.length;
  const totalRaised = rounds.reduce((sum, r) => sum + (r.amount_usd ?? 0), 0);
  const rangeLabel = fmtRange(from, to);
  const tagline = 'EU and US startup funding rounds from last week. Five-minute read.';
  const issueLabel = `FF: Monday Raises · ${rangeLabel}`;

  const doc: IssueDoc = {
    title: issueLabel,
    tagline,
    sections: REGION_SECTIONS.map((sec) => ({
      emoji: sec.emoji,
      name: sec.name,
      stories: byRegion[sec.key].map((r) => ({
        url: r.story_url,
        title: headlineFor(r),
        minuteRead: null,
        blurb: blurbByUrl.get(r.story_url)?.blurb || generatedBlurb(r),
        meta: null,
      })),
    })),
  };

  return (
    <main>
      <Nav />
      <div className="flex flex-col gap-2 px-4 sm:px-5 py-3 border-b border-border">
        <FundingDateFilter dates={dates} from={from} to={to} todayISO={today} />
        <div className="text-[10px] text-text-mute">
          {rangeLabel} · {total} {total === 1 ? 'round' : 'rounds'}
          {totalRaised > 0 ? ` · ${formatUsd(totalRaised, '')} raised` : ''} · EU{' '}
          {byRegion.EU.length} · NA {byRegion.NA.length}
        </div>
      </div>

      <div className="max-w-[680px] mx-auto px-4 sm:px-5 py-6 sm:py-8">
        <div className="text-center mb-2">
          <div className="text-[10px] uppercase tracking-[0.15em] text-text-mute mb-1">
            {rangeLabel}
          </div>
          <h1 className="text-[26px] sm:text-[30px] font-bold tracking-tight mb-2">
            FF: Monday Raises
          </h1>
          <p className="text-[12.5px] sm:text-[13px] text-text-mute leading-snug max-w-md mx-auto m-0">
            {tagline}
          </p>
        </div>

        {total > 0 && (
          <div className="mt-6 mb-8 text-center text-[13px] text-text-dim italic">
            💸 {total} {total === 1 ? 'round' : 'rounds'}
            {totalRaised > 0 ? `, ${formatUsd(totalRaised, '')} raised` : ''} across Europe and
            North America.
          </div>
        )}

        {total === 0 ? (
          <div className="border border-dashed border-border rounded-md py-10 px-6 text-center text-text-mute text-[13px]">
            No raises in this window. Pick a different week above.
          </div>
        ) : (
          <div className="mt-2">
            {REGION_SECTIONS.map((sec) => {
              const items = byRegion[sec.key];
              if (items.length === 0) return null;
              return (
                <section key={sec.key} className="mb-10 sm:mb-12">
                  <div className="text-center mb-5">
                    <div className="text-[28px] sm:text-[32px] leading-none mb-1.5">{sec.emoji}</div>
                    <h2 className="text-[13px] sm:text-[14px] font-bold uppercase tracking-[0.06em] m-0">
                      {sec.name}
                    </h2>
                    <div className="text-[11px] text-text-mute mt-0.5">{sec.tagline}</div>
                  </div>
                  {items.map((r) => (
                    <article key={r.story_url} className="mb-7 sm:mb-8">
                      <a
                        href={r.story_url}
                        target="_blank"
                        rel="noopener"
                        className="block text-[15.5px] sm:text-[16px] font-bold text-text underline decoration-text-mute hover:decoration-text leading-snug mb-2"
                      >
                        {headlineFor(r)}
                      </a>
                      <p className="text-[14px] sm:text-[14.5px] text-text-dim leading-[1.6] m-0">
                        {blurbByUrl.get(r.story_url)?.blurb || generatedBlurb(r)}
                      </p>
                    </article>
                  ))}
                </section>
              );
            })}
          </div>
        )}

        <div className="mt-12 pt-6 border-t border-border text-center text-[12.5px] text-text-dim">
          <p className="m-0 mb-1">If you have any comments or feedback, just hit reply.</p>
          <p className="m-0">
            Thanks for reading,<br />
            <span className="text-text font-semibold">- Oliver</span>
          </p>
        </div>

        <MondayRaisesExport label={issueLabel} doc={doc} />
      </div>
    </main>
  );
}
