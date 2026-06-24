import Link from 'next/link';
import { todayUTC } from '@/lib/formatters';
import { loadVcRange } from '@/lib/data';
import Nav from '@/components/Nav';
import { canonFirm, dedupCanon } from '@/lib/vc-aliases';
import type { VcSector, VcType } from '@/lib/types';

// Edge-cache each unique URL for 10 minutes. Curtails bandwidth
// vs the previous force-dynamic mode that re-read every JSONL on
// every visitor + bot crawl.
export const revalidate = 600;

/**
 * Public-facing pitch page. Shareable URL: trylede.com/vc/preview
 * Designed to be the artifact you DM to a publisher / TLDR team
 * instead of explaining the concept in text.
 */
export default function VcPreviewPage() {
  const today = todayUTC();
  // Sample window: last 14 days for the "what 2 weeks of TLDR VC looks like" pitch
  const fromDate = new Date(today + 'T00:00:00Z');
  fromDate.setUTCDate(fromDate.getUTCDate() - 13);
  const from = fromDate.toISOString().slice(0, 10);
  const all = loadVcRange(from, today);

  const countsByType: Partial<Record<VcType, number>> = {};
  const countsBySector: Partial<Record<VcSector, number>> = {};
  const firmCounts: Record<string, number> = {};
  for (const r of all) {
    countsByType[r.vc_type] = (countsByType[r.vc_type] ?? 0) + 1;
    countsBySector[(r.sector ?? 'other') as VcSector] =
      (countsBySector[(r.sector ?? 'other') as VcSector] ?? 0) + 1;
    for (const f of dedupCanon(r.firms ?? [], canonFirm)) {
      firmCounts[f] = (firmCounts[f] ?? 0) + 1;
    }
  }
  const dailyAvg = Math.round(all.length / 14);
  const topFirms = Object.entries(firmCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  // A small snapshot of the most recent issue's marquee headlines
  const recent = all
    .slice()
    .sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''))
    .slice(0, 5);

  return (
    <main>
      <Nav />

      <section className="max-w-[820px] mx-auto px-4 sm:px-5 py-10 sm:py-12">
        {/* Hero */}
        <div className="mb-10">
          <div className="text-[11px] uppercase tracking-[0.12em] text-text-mute mb-2">
            Niche newsletter proposal
          </div>
          <h1 className="text-[34px] sm:text-[40px] font-bold tracking-tight leading-[1.05] mb-4">
            TLDR VC
          </h1>
          <p className="text-[16px] sm:text-[18px] text-text-dim leading-snug mb-6 max-w-[560px]">
            A 5-minute daily on venture. Funds, exits, people, signals. The wedge nobody ships yet.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/vc/issue"
              className="px-5 py-2.5 rounded-md bg-accent text-text text-[13px] font-medium hover:opacity-90"
            >
              See today&apos;s issue →
            </Link>
            <Link
              href="/vc"
              className="px-5 py-2.5 rounded-md bg-surface border border-border text-text text-[13px] font-medium hover:bg-surface-hi"
            >
              Browse the full feed
            </Link>
          </div>
        </div>

        {/* Volume proof */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12 pb-10 border-b border-border">
          <Stat label="Articles / day" value={dailyAvg.toString()} sub="last 14 days" />
          <Stat label="Fund news" value={(countsByType.fund_news ?? 0).toString()} sub="fortnight" />
          <Stat label="Exits" value={(countsByType.exit ?? 0).toString()} sub="fortnight" />
          <Stat label="Partner moves" value={(countsByType.partner_move ?? 0).toString()} sub="fortnight" />
        </div>

        {/* Wedge */}
        <div className="mb-12">
          <h2 className="text-[22px] font-bold tracking-tight mb-4">
            What makes it different
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[13.5px]">
            <Card title="🇪🇺 EU + global" body="Term Sheet skews US. TLDR VC pulls Sifted, tech.eu, Silicon Canals, plus the US wire." />
            <Card title="🪑 Partner radar" body="Hires, departures, founding moves. Aggregated across firms daily." />
            <Card title="📈 Signal, not stenography" body="LLM rewrites every story into one punchy line. Reader sees the takeaway, not the press release." />
          </div>
        </div>

        {/* Sample sectors */}
        <div className="mb-12">
          <h2 className="text-[22px] font-bold tracking-tight mb-4">
            Sectors covered (last 14 days)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 text-[13px]">
            {(Object.entries(countsBySector) as [VcSector, number][])
              .sort((a, b) => b[1] - a[1])
              .filter(([, n]) => n > 0)
              .map(([sec, n]) => (
                <div key={sec} className="flex items-baseline gap-2 border border-border rounded px-3 py-1.5">
                  <span className="capitalize text-text">{sec}</span>
                  <span className="ml-auto font-mono text-text-mute">{n}</span>
                </div>
              ))}
          </div>
        </div>

        {/* Investor leaderboard preview */}
        <div className="mb-12">
          <h2 className="text-[22px] font-bold tracking-tight mb-4">
            Most-mentioned investors (last 14 days)
          </h2>
          {topFirms.length === 0 ? (
            <p className="text-text-mute text-[13px]">No firm mentions yet.</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5 text-[13px]">
              {topFirms.map(([firm, n]) => (
                <div key={firm} className="flex items-baseline gap-2 px-3 py-1">
                  <span className="text-text">{firm}</span>
                  <span className="ml-auto font-mono text-text-mute">{n}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent headlines as proof of curation */}
        {recent.length > 0 && (
          <div className="mb-12">
            <h2 className="text-[22px] font-bold tracking-tight mb-4">
              Today&apos;s marquee headlines
            </h2>
            <ul className="space-y-3">
              {recent.map((r) => (
                <li key={r.story_url}>
                  <a
                    href={r.story_url}
                    target="_blank"
                    rel="noopener"
                    className="text-[14.5px] text-text font-semibold hover:text-accent"
                  >
                    {r.headline_summary || r.title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Closing CTA */}
        <div className="border-t border-border pt-8 text-center">
          <p className="text-[13.5px] text-text-dim mb-4">
            Built by <a href="https://www.oliverstafurik.com" className="text-accent hover:underline" target="_blank" rel="noopener">Oliver Stafurik</a> on the <Link href="/" className="text-accent hover:underline">lede curation pipeline</Link> - same backbone as the 13 existing TLDR titles.
          </p>
          <Link
            href="/vc/issue"
            className="inline-block px-5 py-2.5 rounded-md bg-accent text-text text-[13px] font-medium hover:opacity-90"
          >
            See today&apos;s rendered issue →
          </Link>
        </div>
      </section>
    </main>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <div className="text-[36px] font-bold font-mono text-accent leading-none">{value}</div>
      <div className="text-[12px] text-text-dim mt-1.5">{label}</div>
      <div className="text-[10px] text-text-mute mt-0.5">{sub}</div>
    </div>
  );
}

function Card({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-border rounded-md p-4">
      <div className="text-[14px] font-semibold mb-1.5">{title}</div>
      <div className="text-[12.5px] text-text-dim leading-snug">{body}</div>
    </div>
  );
}
