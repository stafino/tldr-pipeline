import {
  listBacktestDates,
  loadBacktest,
  loadBacktestsForNewsletter,
  loadNewsletters,
} from '@/lib/data';
import Nav from '@/components/Nav';
import BacktestPicker from '@/components/BacktestPicker';

export const dynamic = 'force-dynamic';

const SPARK = '▁▂▃▄▅▆▇█';
function sparkline(values: number[]): string {
  if (!values.length) return '';
  return values
    .map((v) => {
      const i = Math.max(0, Math.min(SPARK.length - 1, Math.floor(v * SPARK.length)));
      return SPARK[i];
    })
    .join('');
}

export default function BacktestPage({
  searchParams,
}: {
  searchParams: { date?: string; nl?: string };
}) {
  const newsletters = loadNewsletters();
  const nlIds = Object.keys(newsletters);
  const dates = listBacktestDates();

  if (dates.length === 0) {
    return (
      <main>
        <Nav />
        <div className="px-6 py-10 text-text-mute">No backtest data yet.</div>
      </main>
    );
  }

  // Hero: aggregate recall for latest date
  const latestDate = dates[0];
  const latestResults = nlIds
    .map((nid) => loadBacktest(nid, latestDate))
    .filter((r): r is NonNullable<typeof r> => r !== null && r.available && r.predictions.length > 0);

  const totalTldr = latestResults.reduce((s, r) => s + r.tldr_titles.length, 0);
  function totalHits(k: number) {
    return latestResults.reduce((s, r) => s + (r.hits_at?.[String(k)] ?? 0), 0);
  }
  const r10 = totalTldr ? (totalHits(10) / totalTldr) * 100 : 0;
  const r25 = totalTldr ? (totalHits(25) / totalTldr) * 100 : 0;
  const r50 = totalTldr ? (totalHits(50) / totalTldr) * 100 : 0;
  const maxK = latestResults.length
    ? Math.max(...latestResults.flatMap((r) => Object.keys(r.hits_at ?? {}).map(Number)))
    : 0;
  const rAll = totalTldr
    ? (latestResults.reduce((s, r) => s + (r.hits_at?.[String(maxK)] ?? 0), 0) / totalTldr) * 100
    : 0;

  // Per-newsletter aggregates (last 7 days)
  const rows = nlIds.map((nid) => {
    const history = loadBacktestsForNewsletter(nid, 7).filter((r) => r.predictions.length > 0);
    if (history.length === 0)
      return { nid, brand: newsletters[nid].brand_name, none: true } as any;
    const aggTldr = history.reduce((s, r) => s + r.tldr_titles.length, 0);
    if (aggTldr === 0) return { nid, brand: newsletters[nid].brand_name, none: true } as any;
    function pct(k: number) {
      return history.reduce((s, r) => s + (r.hits_at?.[String(k)] ?? 0), 0) / aggTldr;
    }
    const localMaxK = Math.max(...history.flatMap((r) => Object.keys(r.hits_at ?? {}).map(Number)));
    const allPct =
      history.reduce((s, r) => s + (r.hits_at?.[String(localMaxK)] ?? 0), 0) / aggTldr;
    const spark = sparkline(history.map((r) => r.recall_at?.['10'] ?? 0));
    return {
      nid,
      brand: newsletters[nid].brand_name,
      r10: pct(10),
      r25: pct(25),
      r50: pct(50),
      rAll: allPct,
      spark,
    };
  });

  // Detail pick
  const detailDate = searchParams.date ?? latestDate;
  const detailNl = searchParams.nl ?? nlIds[0];
  const detail = loadBacktest(detailNl, detailDate);

  return (
    <main>
      <Nav />
      <div className="max-w-[1300px] mx-auto px-5 py-5">
        <div
          className="rounded-lg border border-border-strong p-6 mb-5"
          style={{ background: 'linear-gradient(135deg, #171717 0%, #1a2030 100%)' }}
        >
          <h2 className="text-[14px] font-semibold uppercase tracking-[0.1em] text-text-dim mb-1.5">
            How well we match TLDR
          </h2>
          <p className="text-[22px] font-semibold mb-3 -tracking-[0.01em]">
            {latestDate} · {latestResults.length} newsletters compared · {totalTldr} stories TLDR
            actually published
          </p>
          <div className="flex gap-8 flex-wrap">
            <Stat label="recall @ top 10" value={`${Math.round(r10)}%`} accent />
            <Stat label="recall @ top 25" value={`${Math.round(r25)}%`} accent />
            <Stat label="recall @ top 50" value={`${Math.round(r50)}%`} accent />
            <Stat label="recall @ any (full pool)" value={`${Math.round(rAll)}%`} />
          </div>
        </div>

        <p className="text-[12px] text-text-mute leading-[1.5] mb-5">
          <b className="text-text-dim">Recall</b> = "of the stories TLDR actually published, how many
          did we surface in our top N?" Matches via title-embedding similarity ≥ 0.62, with
          URL-overlap as a strong cross-check (catches the Fox/Roku case). Low numbers point to
          source coverage gaps — TLDR sources heavily from X, LinkedIn, and inside-baseball
          Substacks.
        </p>

        <table className="w-full text-[13px] border-collapse mb-6">
          <thead>
            <tr>
              <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-[0.08em] text-text-mute border-b border-border-strong">
                Newsletter
              </th>
              <th className="text-right py-2.5 px-3 text-[10px] uppercase tracking-[0.08em] text-text-mute border-b border-border-strong">
                R@10
              </th>
              <th className="text-right py-2.5 px-3 text-[10px] uppercase tracking-[0.08em] text-text-mute border-b border-border-strong">
                R@25
              </th>
              <th className="text-right py-2.5 px-3 text-[10px] uppercase tracking-[0.08em] text-text-mute border-b border-border-strong">
                R@50
              </th>
              <th className="text-right py-2.5 px-3 text-[10px] uppercase tracking-[0.08em] text-text-mute border-b border-border-strong">
                R@all
              </th>
              <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-[0.08em] text-text-mute border-b border-border-strong">
                Last 7 days (R@10)
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row: any) => (
              <tr key={row.nid} className="hover:bg-surface">
                <td className="py-2.5 px-3 border-b border-border text-text font-medium">{row.brand}</td>
                {row.none ? (
                  <td colSpan={4} className="py-2.5 px-3 border-b border-border italic text-text-mute">
                    no comparable issue yet
                  </td>
                ) : (
                  <>
                    <td className={`text-right py-2.5 px-3 border-b border-border font-mono font-semibold ${rcls(row.r10)}`}>
                      {Math.round(row.r10 * 100)}%
                    </td>
                    <td className={`text-right py-2.5 px-3 border-b border-border font-mono font-semibold ${rcls(row.r25)}`}>
                      {Math.round(row.r25 * 100)}%
                    </td>
                    <td className={`text-right py-2.5 px-3 border-b border-border font-mono font-semibold ${rcls(row.r50)}`}>
                      {Math.round(row.r50 * 100)}%
                    </td>
                    <td className={`text-right py-2.5 px-3 border-b border-border font-mono font-semibold ${rcls(row.rAll)}`}>
                      {Math.round(row.rAll * 100)}%
                    </td>
                  </>
                )}
                {!row.none && (
                  <td className="py-2.5 px-3 border-b border-border font-mono text-accent tracking-[2px]">
                    {row.spark}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="text-[14px] font-semibold mt-6 mb-3">Today vs published — side by side</h3>
        <BacktestPicker
          newsletters={Object.fromEntries(nlIds.map((id) => [id, newsletters[id].brand_name]))}
          dates={dates}
          defaultDate={detailDate}
          defaultNl={detailNl}
        />

        {detail === null || !detail.available ? (
          <div className="bg-surface border border-dashed border-border rounded-md py-10 px-6 text-center text-text-mute text-[13px]">
            No published TLDR issue for {newsletters[detailNl]?.brand_name} on {detailDate}.
          </div>
        ) : !detail.predictions || detail.predictions.length === 0 ? (
          <div className="bg-surface border border-dashed border-border rounded-md py-10 px-6 text-center text-text-mute text-[13px]">
            We have no predictions for this date.
          </div>
        ) : (
          <CompareGrid detail={detail} brand={newsletters[detailNl].brand_name} />
        )}
      </div>
    </main>
  );
}

function rcls(v: number) {
  if (v >= 0.5) return 'text-ok';
  if (v >= 0.25) return 'text-warn';
  return 'text-text-mute';
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className={`text-[28px] font-bold font-mono leading-tight ${accent ? 'text-accent' : 'text-text'}`}>
        {value}
      </div>
      <div className="text-[11px] text-text-mute uppercase tracking-[0.08em] mt-0.5">{label}</div>
    </div>
  );
}

function CompareGrid({ detail, brand }: { detail: any; brand: string }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-8 mt-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.1em] text-text-mute font-semibold mb-2.5 pb-2 border-b border-border-strong">
            TLDR {brand.replace('TLDR ', '').replace('TLDR', '')} actually published ({detail.tldr_titles.length})
          </div>
          {detail.tldr_titles.map((t: string, i: number) => {
            const hit = detail.tldr_matched?.[i];
            return (
              <div
                key={i}
                className={
                  'py-2 border-b border-border flex gap-2.5 items-baseline text-[13px] ' +
                  (hit ? 'bg-emerald-950/30 -mx-2 px-2 rounded' : '')
                }
              >
                <span className="font-mono text-[11px] text-text-mute w-6 text-right shrink-0">{i + 1}</span>
                <span className={hit ? 'text-ok' : 'text-no'}>{hit ? '✓' : '✗'}</span>
                <span className="flex-1 text-text">{t}</span>
              </div>
            );
          })}
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.1em] text-text-mute font-semibold mb-2.5 pb-2 border-b border-border-strong">
            Our top {detail.predictions.length} predictions
          </div>
          {detail.predictions.map((p: any) => {
            const matched = p.matched_tldr_idx !== null && p.matched_tldr_idx !== undefined;
            return (
              <div
                key={p.rank}
                className={
                  'py-2 border-b border-border flex gap-2.5 items-baseline text-[13px] ' +
                  (matched ? 'bg-emerald-950/30 -mx-2 px-2 rounded' : '')
                }
              >
                <span className="font-mono text-[11px] text-text-mute w-6 text-right shrink-0">{p.rank}</span>
                <span className={matched ? 'text-ok' : 'text-text-mute'}>{matched ? '✓' : '·'}</span>
                <span className="flex-1 text-text">{p.title}</span>
                <span className="font-mono text-[11px] text-text shrink-0">{Math.round(p.score)}</span>
              </div>
            );
          })}
        </div>
      </div>
      <p className="text-[11px] text-text-mute mt-4">
        Hits at @10 / @25 / @50: <b className="font-mono text-text">{detail.hits_at?.['10'] ?? 0} · {detail.hits_at?.['25'] ?? 0} · {detail.hits_at?.['50'] ?? 0}</b>{' '}
        of {detail.tldr_titles.length} TLDR titles · pool size {detail.predictions.length} predictions ·
        cached {detail.fetched_at?.slice(0, 19)}
      </p>
    </>
  );
}
