import Link from 'next/link';
import { canonicalDomain } from '@/lib/utils';
import { loadVcRange } from '@/lib/data';
import Nav from '@/components/Nav';
import VcIssueExport from '@/components/VcIssueExport';
import type { VcArticle, VcType } from '@/lib/types';

export const dynamic = 'force-dynamic';

function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

const SECTIONS: { key: VcType; emoji: string; name: string }[] = [
  { key: 'fund_news', emoji: '💰', name: 'Funds & LPs' },
  { key: 'exit', emoji: '🚪', name: 'Exits & IPOs' },
  { key: 'partner_move', emoji: '🪑', name: 'People & Moves' },
  { key: 'market_signal', emoji: '📈', name: 'Market Signals' },
  { key: 'opinion', emoji: '💭', name: 'Opinion & Analysis' },
  { key: 'regulatory', emoji: '⚖️', name: 'Regulatory' },
];

function pickEstimatedRead(headline: string, snippet: string): number {
  const words = (snippet || headline).split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.min(6, Math.ceil(words / 200)));
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
  // Group + cap per section so the issue doesn't sprawl
  const bySection: Partial<Record<VcType, VcArticle[]>> = {};
  for (const r of all) {
    (bySection[r.vc_type] ??= []).push(r);
  }
  for (const k of Object.keys(bySection) as VcType[]) {
    bySection[k] = (bySection[k] ?? []).slice(0, 6);
  }

  const totalShown = Object.values(bySection).reduce(
    (sum, list) => sum + (list?.length ?? 0),
    0,
  );

  const issueLabel = `TLDR VC · ${to}`;

  return (
    <main>
      <Nav />
      <div className="flex items-center gap-4 px-5 py-3 border-b border-border text-[11px] text-text-mute">
        <Link href="/vc" className="hover:text-text">← back to feed</Link>
        <span className="text-text-dim">
          Window: <span className="font-mono text-text-dim">{from} → {to}</span> ·{' '}
          <span className="font-mono text-text-dim">{totalShown} stories</span>
        </span>
        <span className="ml-auto">
          <Link href="/vc/preview" className="text-accent hover:underline">
            ← see the pitch / preview page
          </Link>
        </span>
      </div>

      <div className="max-w-[680px] mx-auto px-5 py-6">
        {/* Issue header */}
        <div className="text-center mb-8">
          <h1 className="text-[28px] font-bold tracking-tight mb-1">{issueLabel}</h1>
          <p className="text-[12px] text-text-mute">
            A daily digest of the venture capital industry — funds, partners, exits, signals.
          </p>
        </div>

        {totalShown === 0 ? (
          <div className="border border-dashed border-border rounded-md py-10 px-6 text-center text-text-mute text-[13px]">
            No VC stories for this window. Pick an earlier date or widen with{' '}
            <Link href="?days=7" className="text-accent hover:underline">days=7</Link>.
          </div>
        ) : (
          <div>
            {SECTIONS.map((sec) => {
              const items = bySection[sec.key] ?? [];
              if (items.length === 0) return null;
              return (
                <section key={sec.key} className="mb-10">
                  <div className="text-center mb-5">
                    <div className="text-[28px] leading-none mb-1">{sec.emoji}</div>
                    <h2 className="text-[14px] font-bold uppercase tracking-[0.05em] m-0">
                      {sec.name}
                    </h2>
                  </div>
                  {items.map((r) => {
                    const dom = canonicalDomain(r.story_url);
                    const min = pickEstimatedRead(r.title, r.headline_summary);
                    return (
                      <article key={r.story_url} className="mb-7">
                        <a
                          href={r.story_url}
                          target="_blank"
                          rel="noopener"
                          className="block text-[15.5px] font-bold text-text underline decoration-text-mute hover:decoration-text leading-snug mb-2"
                        >
                          {r.headline_summary || r.title} ({min} minute read)
                        </a>
                        {(r.headline_summary && r.title !== r.headline_summary) && (
                          <p className="text-[13.5px] text-text-dim leading-[1.55] m-0">
                            {r.title}
                          </p>
                        )}
                        {(r.firms.length > 0 || r.people.length > 0 || dom) && (
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
          </div>
        )}

        <VcIssueExport issueLabel={issueLabel} sections={SECTIONS} bySection={bySection} />
      </div>
    </main>
  );
}
