import Link from 'next/link';
import { ISSUE_SECTIONS } from '@/lib/vc-metadata';
import { todayUTC } from '@/lib/formatters';
import { canonicalDomain } from '@/lib/utils';
import { listVcDates, loadVcRange } from '@/lib/data';
import Nav from '@/components/Nav';
import VcIssueExport from '@/components/VcIssueExport';
import VcSubjectVariants from '@/components/VcSubjectVariants';
import type { VcArticle, VcType } from '@/lib/types';

export const dynamic = 'force-dynamic';


function pickEstimatedRead(headline: string, snippet: string): number {
  const words = (snippet || headline).split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.min(6, Math.ceil(words / 200)));
}

function intro(allCount: number, byType: Partial<Record<VcType, number>>): string {
  // Deterministic editorial frame - no LLM cost. Picks the biggest signal
  // of the day and leads with it.
  if (allCount === 0) return 'Quiet day on the wire.';
  const parts: string[] = [];
  if ((byType.fund_news ?? 0) >= 2) parts.push(`${byType.fund_news} fund moves`);
  if ((byType.exit ?? 0) >= 2) parts.push(`${byType.exit} exits/IPOs`);
  if ((byType.partner_move ?? 0) >= 2) parts.push(`${byType.partner_move} partner moves`);
  if ((byType.regulatory ?? 0) >= 1) parts.push(`${byType.regulatory} regulatory beat${byType.regulatory! > 1 ? 's' : ''}`);
  if (parts.length === 0) {
    return `${allCount} stories shaping venture today - mostly signals and analysis.`;
  }
  return `Today: ${parts.join(', ')}. Curated below.`;
}

export default function VcIssuePage({
  searchParams,
}: {
  searchParams: { date?: string; days?: string };
}) {
  const today = todayUTC();
  const daysBack = Math.max(1, Math.min(7, Number(searchParams.days ?? '2') || 2));
  const to = searchParams.date ?? today;
  const fromDate = new Date(to + 'T00:00:00Z');
  fromDate.setUTCDate(fromDate.getUTCDate() - (daysBack - 1));
  const from = fromDate.toISOString().slice(0, 10);

  const all = loadVcRange(from, to);

  // Issue number = days since the first scrape we have data for
  const allDates = listVcDates();
  const firstDate = allDates[allDates.length - 1];
  const issueNum =
    firstDate && to >= firstDate
      ? Math.round(
          (new Date(to + 'T00:00:00Z').getTime() -
            new Date(firstDate + 'T00:00:00Z').getTime()) /
            (24 * 60 * 60 * 1000),
        ) + 1
      : 1;

  // Group by section, then split into "main" (top per-section by recency)
  // and "quickLinks" (overflow that goes into the ⚡ catch-all at the end).
  const bySectionAll: Partial<Record<VcType, VcArticle[]>> = {};
  for (const r of all) (bySectionAll[r.vc_type] ??= []).push(r);
  const bySection: Partial<Record<VcType, VcArticle[]>> = {};
  const quickLinks: VcArticle[] = [];
  for (const sec of ISSUE_SECTIONS) {
    const list = (bySectionAll[sec.key] ?? []).slice().sort(
      (a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''),
    );
    bySection[sec.key] = list.slice(0, sec.cap);
    quickLinks.push(...list.slice(sec.cap));
  }
  // Sort overflow by recency for the Quick Links section
  quickLinks.sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''));

  const totalShown =
    Object.values(bySection).reduce((sum, list) => sum + (list?.length ?? 0), 0) +
    quickLinks.length;

  const countsByType: Partial<Record<VcType, number>> = {};
  for (const r of all) countsByType[r.vc_type] = (countsByType[r.vc_type] ?? 0) + 1;
  const headerIntro = intro(all.length, countsByType);

  const issueLabel = `TLDR VC · ${to}`;
  const issueHeader = `TLDR VC #${issueNum}`;

  return (
    <main>
      <Nav />
      <div className="flex items-center gap-3 px-4 sm:px-5 py-3 border-b border-border text-[11px] text-text-mute flex-wrap">
        <Link href="/vc" className="hover:text-text">← back to feed</Link>
        <span className="text-text-dim hidden sm:inline">
          Window: <span className="font-mono">{from} → {to}</span> ·{' '}
          <span className="font-mono">{totalShown} stories</span>
        </span>
        <Link href="/vc/preview" className="ml-auto text-accent hover:underline">
          pitch page →
        </Link>
      </div>

      <div className="max-w-[680px] mx-auto px-4 sm:px-5 py-6 sm:py-8">
        {/* Issue header */}
        <div className="text-center mb-2">
          <div className="text-[10px] uppercase tracking-[0.15em] text-text-mute mb-1">
            {to}
          </div>
          <h1 className="text-[26px] sm:text-[30px] font-bold tracking-tight mb-2">
            {issueHeader}
          </h1>
          <p className="text-[12.5px] sm:text-[13px] text-text-mute leading-snug max-w-md mx-auto m-0">
            A 5-minute daily on venture. Funds, exits, people, signals.
          </p>
        </div>

        {/* Editor's intro - short, deterministic, no LLM cost */}
        {all.length > 0 && (
          <div className="mt-6 mb-8 text-center text-[13px] text-text-dim italic">
            💌 {headerIntro}
          </div>
        )}

        {/* Subject-line variants for A/B framing */}
        {all.length > 0 && (
          <VcSubjectVariants
            issueNum={issueNum}
            topByType={Object.fromEntries(
              ISSUE_SECTIONS.map((s) => [s.key, bySection[s.key]?.[0]]),
            ) as Record<VcType, VcArticle | undefined>}
          />
        )}

        {totalShown === 0 ? (
          <div className="border border-dashed border-border rounded-md py-10 px-6 text-center text-text-mute text-[13px]">
            No VC stories for this window. Pick an earlier date or widen with{' '}
            <Link href="?days=7" className="text-accent hover:underline">days=7</Link>.
          </div>
        ) : (
          <div className="mt-2">
            {ISSUE_SECTIONS.map((sec) => {
              const items = bySection[sec.key] ?? [];
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
                  {items.map((r) => {
                    const dom = canonicalDomain(r.story_url);
                    const min = pickEstimatedRead(r.title, r.headline_summary);
                    const headline = r.headline_summary || r.title;
                    return (
                      <article key={r.story_url} className="mb-7 sm:mb-8">
                        <a
                          href={r.story_url}
                          target="_blank"
                          rel="noopener"
                          className="block text-[15.5px] sm:text-[16px] font-bold text-text underline decoration-text-mute hover:decoration-text leading-snug mb-2"
                        >
                          {headline} ({min} minute read)
                        </a>
                        {r.blurb ? (
                          <p className="text-[14px] sm:text-[14.5px] text-text-dim leading-[1.6] m-0">
                            {r.blurb}
                          </p>
                        ) : null}
                        {(r.firms.length > 0 || dom) && (
                          <div className="flex flex-wrap gap-2 mt-1.5 text-[10.5px] text-text-mute font-mono">
                            {dom && <span>{dom}</span>}
                            {r.region !== 'OTHER' && <span>· {r.region}</span>}
                            {r.firms.slice(0, 4).map((f) => (
                              <span key={f}>· {f}</span>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })}
                </section>
              );
            })}

            {/* Quick Links - overflow from any section, one-liners */}
            {quickLinks.length > 0 && (
              <section className="mb-10 sm:mb-12">
                <div className="text-center mb-5">
                  <div className="text-[28px] sm:text-[32px] leading-none mb-1.5">⚡</div>
                  <h2 className="text-[13px] sm:text-[14px] font-bold uppercase tracking-[0.06em] m-0">
                    Quick Links
                  </h2>
                  <div className="text-[11px] text-text-mute mt-0.5">
                    Worth a click - short version
                  </div>
                </div>
                {quickLinks.map((r) => {
                  const min = pickEstimatedRead(r.title, r.headline_summary);
                  return (
                    <div key={r.story_url} className="mb-3">
                      <a
                        href={r.story_url}
                        target="_blank"
                        rel="noopener"
                        className="block text-[13.5px] sm:text-[14px] font-semibold text-text underline decoration-text-mute hover:decoration-text leading-snug"
                      >
                        {r.headline_summary || r.title} ({min} minute read)
                      </a>
                    </div>
                  );
                })}
              </section>
            )}
          </div>
        )}

        {/* Curator signoff */}
        <div className="mt-12 pt-6 border-t border-border text-center text-[12.5px] text-text-dim">
          <p className="m-0 mb-1">If you have any comments or feedback, just hit reply.</p>
          <p className="m-0">
            Thanks for reading,<br />
            <span className="text-text font-semibold">- Oliver</span>
          </p>
        </div>

        <VcIssueExport issueLabel={issueLabel} sections={ISSUE_SECTIONS} bySection={bySection} />
      </div>
    </main>
  );
}
