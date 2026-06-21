import Link from 'next/link';
import { ISSUE_SECTIONS } from '@/lib/vc-metadata';
import { todayUTC } from '@/lib/formatters';
import { loadVcRange } from '@/lib/data';
import Nav from '@/components/Nav';
import { canonFirm, canonPerson, dedupCanon } from '@/lib/vc-aliases';
import type { VcArticle, VcSector, VcType } from '@/lib/types';

export const dynamic = 'force-dynamic';


function isoWeek(d: Date): { year: number; week: number } {
  const tmp = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dayNum = tmp.getUTCDay() || 7;
  tmp.setUTCDate(tmp.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return { year: tmp.getUTCFullYear(), week };
}

export default function VcRecapPage() {
  // Default: last 7 days ending today. ?week=YYYY-WW for specific weeks
  // (not implemented yet — placeholder for future archive routes).
  const today = todayUTC();
  const endDate = new Date(today + 'T00:00:00Z');
  const start = new Date(endDate);
  start.setUTCDate(start.getUTCDate() - 6);
  const from = start.toISOString().slice(0, 10);

  const { year, week } = isoWeek(endDate);

  const all = loadVcRange(from, today);

  // Group + cap per section
  const bySection: Partial<Record<VcType, VcArticle[]>> = {};
  for (const r of all) (bySection[r.vc_type] ??= []).push(r);

  // Aggregate movers
  const firmCounts: Record<string, number> = {};
  const personCounts: Record<string, number> = {};
  const sectorCounts: Partial<Record<VcSector, number>> = {};
  for (const r of all) {
    for (const f of dedupCanon(r.firms ?? [], canonFirm)) {
      firmCounts[f] = (firmCounts[f] ?? 0) + 1;
    }
    for (const p of dedupCanon(r.people ?? [], canonPerson)) {
      personCounts[p] = (personCounts[p] ?? 0) + 1;
    }
    const sec = (r.sector ?? 'other') as VcSector;
    sectorCounts[sec] = (sectorCounts[sec] ?? 0) + 1;
  }

  const topFirms = Object.entries(firmCounts).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const topPeople = Object.entries(personCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const topSectors = (Object.entries(sectorCounts) as [VcSector, number][])
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const label = `TLDR VC Weekly · ${year}-W${String(week).padStart(2, '0')}`;

  return (
    <main>
      <Nav />
      <div className="flex flex-wrap items-center gap-3 px-4 sm:px-5 py-3 border-b border-border text-[11px] text-text-mute">
        <Link href="/vc" className="hover:text-text">← back to feed</Link>
        <span className="text-text-dim">
          Window: <span className="font-mono">{from} → {today}</span> ·{' '}
          <span className="font-mono">{all.length} stories</span>
        </span>
        <Link href="/vc/issue" className="ml-auto text-accent hover:underline">
          Daily issue →
        </Link>
      </div>

      <div className="max-w-[720px] mx-auto px-4 sm:px-5 py-6 sm:py-8">
        {/* Issue header */}
        <div className="text-center mb-10">
          <h1 className="text-[24px] sm:text-[30px] font-bold tracking-tight mb-1">{label}</h1>
          <p className="text-[12.5px] text-text-mute">
            The week in venture capital, in one digest.
          </p>
        </div>

        {all.length === 0 ? (
          <div className="border border-dashed border-border rounded-md py-10 px-6 text-center text-text-mute text-[13px]">
            No VC articles in the last 7 days.
          </div>
        ) : (
          <>
            {/* Recap stats card */}
            <div className="rounded-lg border border-border-strong p-5 mb-10 bg-surface">
              <div className="text-[10px] uppercase tracking-[0.1em] text-text-mute mb-3">
                Week at a glance
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
                <Stat
                  value={(bySection.fund_news?.length ?? 0).toString()}
                  label="Fund news"
                />
                <Stat
                  value={(bySection.exit?.length ?? 0).toString()}
                  label="Exits / IPOs"
                />
                <Stat
                  value={(bySection.partner_move?.length ?? 0).toString()}
                  label="Partner moves"
                />
                <Stat
                  value={all.length.toString()}
                  label="Total stories"
                />
              </div>
            </div>

            {/* Top firms + people */}
            {(topFirms.length > 0 || topPeople.length > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-10">
                {topFirms.length > 0 && (
                  <Panel title="Most-mentioned firms">
                    {topFirms.map(([f, n]) => (
                      <div key={f} className="flex items-baseline gap-2 text-[13px] py-0.5">
                        <span className="text-text">{f}</span>
                        <span className="ml-auto font-mono text-[11px] text-text-mute">{n}</span>
                      </div>
                    ))}
                  </Panel>
                )}
                {topPeople.length > 0 && (
                  <Panel title="Most-mentioned people">
                    {topPeople.map(([p, n]) => (
                      <div key={p} className="flex items-baseline gap-2 text-[13px] py-0.5">
                        <span className="text-text">{p}</span>
                        <span className="ml-auto font-mono text-[11px] text-text-mute">{n}</span>
                      </div>
                    ))}
                  </Panel>
                )}
              </div>
            )}

            {/* Sector heatmap */}
            {topSectors.length > 0 && (
              <div className="mb-10">
                <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-2">
                  Sector breakdown
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-[13px]">
                  {topSectors.map(([sec, n]) => (
                    <div key={sec} className="flex items-baseline gap-2 border border-border rounded px-3 py-1.5">
                      <span className="text-text capitalize">{sec}</span>
                      <span className="ml-auto font-mono text-text-mute">{n}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* The recap body — sections of stories */}
            {ISSUE_SECTIONS.map((sec) => {
              const items = (bySection[sec.key] ?? []).slice(0, sec.cap);
              if (items.length === 0) return null;
              return (
                <section key={sec.key} className="mb-10">
                  <div className="text-center mb-5">
                    <div className="text-[26px] leading-none mb-1">{sec.emoji}</div>
                    <h2 className="text-[14px] font-bold uppercase tracking-[0.05em] m-0">
                      {sec.name}
                    </h2>
                  </div>
                  {items.map((r) => (
                    <article key={r.story_url} className="mb-5">
                      <a
                        href={r.story_url}
                        target="_blank"
                        rel="noopener"
                        className="block text-[14.5px] font-bold text-text underline decoration-text-mute hover:decoration-text leading-snug mb-1.5"
                      >
                        {r.headline_summary || r.title}
                      </a>
                      {(r.firms.length > 0 || r.region !== 'OTHER') && (
                        <div className="text-[10.5px] text-text-mute font-mono">
                          {[
                            r.region !== 'OTHER' ? r.region : '',
                            ...dedupCanon(r.firms ?? [], canonFirm).slice(0, 4),
                          ].filter(Boolean).join(' · ')}
                        </div>
                      )}
                    </article>
                  ))}
                </section>
              );
            })}
          </>
        )}
      </div>
    </main>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-[28px] font-bold font-mono text-accent leading-none">{value}</div>
      <div className="text-[10.5px] text-text-mute mt-1">{label}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border rounded p-3">
      <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-2">
        {title}
      </div>
      <div>{children}</div>
    </div>
  );
}
