import {
  listAvailableDates,
  listFundingDates,
  loadFunding,
  loadFundingAll,
} from '@/lib/data';
import Nav from '@/components/Nav';
import DatePicker from '@/components/DatePicker';
import type { FundingRound } from '@/lib/types';

export const dynamic = 'force-dynamic';

function formatAmount(usd: number | null, raw: string): string {
  if (!usd) return raw || '—';
  if (usd >= 1_000_000_000) return `$${(usd / 1_000_000_000).toFixed(usd >= 10_000_000_000 ? 0 : 1)}B`;
  if (usd >= 1_000_000) return `$${Math.round(usd / 1_000_000)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `$${usd}`;
}

function formatValuation(usd: number | null): string {
  if (!usd) return '';
  if (usd >= 1_000_000_000) return `$${(usd / 1_000_000_000).toFixed(usd >= 10_000_000_000 ? 0 : 1)}B`;
  if (usd >= 1_000_000) return `$${Math.round(usd / 1_000_000)}M`;
  return `$${usd}`;
}

function Row({ r }: { r: FundingRound }) {
  return (
    <a
      href={r.story_url}
      target="_blank"
      rel="noopener"
      className="block border-b border-border py-3 hover:bg-surface transition-colors"
    >
      <div className="flex items-baseline gap-3 px-3">
        <span className="font-mono text-[13px] font-bold text-warn shrink-0 w-[68px]">
          {formatAmount(r.amount_usd, r.amount_raw)}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-[14px] font-semibold text-text">
              {r.company || '(unknown company)'}
            </span>
            {r.round_label && (
              <span className="font-mono text-[10.5px] text-text-mute uppercase tracking-[0.05em]">
                {r.round_label}
              </span>
            )}
            {r.valuation_usd ? (
              <span className="font-mono text-[10.5px] text-ok">
                @ {formatValuation(r.valuation_usd)} val
              </span>
            ) : null}
            {r.country && (
              <span className="font-mono text-[10.5px] text-text-mute">· {r.country}</span>
            )}
          </div>
          {r.investors.length > 0 && (
            <div className="text-[11px] text-text-dim mt-0.5">
              {r.investors.slice(0, 4).join(', ')}
              {r.investors.length > 4 ? `, +${r.investors.length - 4} more` : ''}
            </div>
          )}
          <div className="text-[10.5px] text-text-mute mt-0.5 truncate">{r.title}</div>
        </div>
      </div>
    </a>
  );
}

function Column({ label, rows }: { label: string; rows: FundingRound[] }) {
  const total = rows.reduce((sum, r) => sum + (r.amount_usd ?? 0), 0);
  return (
    <div>
      <div className="flex items-baseline gap-3 pb-2 mb-1 border-b border-border-strong px-3">
        <h2 className="text-[12px] uppercase tracking-[0.08em] font-bold text-warn m-0">
          {label}
        </h2>
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
        rows.map((r) => <Row key={r.story_url} r={r} />)
      )}
    </div>
  );
}

export default function FundingPage({
  searchParams,
}: {
  searchParams: { date?: string };
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

  const selectedDate = searchParams.date ?? dates[0];
  const rounds = selectedDate === 'All' ? loadFundingAll(dates) : loadFunding(selectedDate);

  const eu = rounds.filter((r) => r.region === 'EU');
  const na = rounds.filter((r) => r.region === 'NA');

  return (
    <main>
      <Nav />
      <div className="flex gap-3 px-5 py-3 border-b border-border items-center">
        <DatePicker dates={dates} value={selectedDate} />
        <div className="text-[10px] text-text-mute">
          {rounds.length} rounds · EU {eu.length} · NA {na.length}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 px-5 py-5">
        <Column label="🇪🇺 Europe" rows={eu} />
        <Column label="🇺🇸 North America" rows={na} />
      </div>
    </main>
  );
}
