import Link from 'next/link';
import { canonicalDomain } from '@/lib/utils';
import { listVcDates, loadVcRange } from '@/lib/data';
import Nav from '@/components/Nav';
import type { VcArticle, VcType } from '@/lib/types';

export const dynamic = 'force-dynamic';

function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

const TYPE_LABELS: Record<VcType, { label: string; emoji: string; color: string }> = {
  fund_news: {
    label: 'Fund news',
    emoji: '💰',
    color: 'bg-ok-soft text-ok border-ok',
  },
  partner_move: {
    label: 'Partner moves',
    emoji: '🪑',
    color: 'bg-accent-soft text-accent border-accent',
  },
  exit: {
    label: 'Exits',
    emoji: '🚪',
    color: 'bg-purple-900/40 text-purple-300 border-purple-700',
  },
  market_signal: {
    label: 'Market signals',
    emoji: '📈',
    color: 'bg-warn-soft text-warn border-warn',
  },
  opinion: {
    label: 'Opinion',
    emoji: '💭',
    color: 'bg-surface text-text-dim border-border',
  },
  regulatory: {
    label: 'Regulatory',
    emoji: '⚖️',
    color: 'bg-no-soft text-no border-no',
  },
};

const TYPES_ORDER: VcType[] = [
  'fund_news',
  'partner_move',
  'exit',
  'market_signal',
  'opinion',
  'regulatory',
];

function relativeFromNow(iso: string, today: string): string {
  if (!iso) return '';
  const r = new Date((iso.slice(0, 10) || today) + 'T00:00:00Z').getTime();
  const t = new Date(today + 'T00:00:00Z').getTime();
  const days = Math.round((t - r) / (24 * 60 * 60 * 1000));
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return new Date((iso.slice(0, 10) || today) + 'T00:00:00Z').toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    timeZone: 'UTC',
  });
}

function Row({ r, today }: { r: VcArticle; today: string }) {
  const meta = TYPE_LABELS[r.vc_type] ?? TYPE_LABELS.market_signal;
  const dom = canonicalDomain(r.story_url);
  return (
    <a
      href={r.story_url}
      target="_blank"
      rel="noopener"
      className="block border-b border-border py-3 px-3 hover:bg-surface transition-colors"
    >
      <div className="flex items-baseline gap-3">
        <span
          className={`font-mono text-[10px] uppercase tracking-[0.05em] px-1.5 py-0.5 rounded border shrink-0 ${meta.color}`}
        >
          {meta.label}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-semibold text-text leading-snug">
            {r.headline_summary || r.title}
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-1 text-[10.5px] text-text-mute font-mono">
            {dom && (
              <span className="inline-flex items-center gap-1.5">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://icons.duckduckgo.com/ip3/${dom}.ico`}
                  alt=""
                  width={12}
                  height={12}
                  className="rounded-sm opacity-80"
                  loading="lazy"
                />
                {dom}
              </span>
            )}
            <span>· {relativeFromNow(r.published_at, today)}</span>
            {r.region !== 'OTHER' && <span>· {r.region}</span>}
            {r.firms.length > 0 && (
              <span className="text-text-dim normal-case">
                · {r.firms.slice(0, 3).join(' · ')}
                {r.firms.length > 3 ? `, +${r.firms.length - 3}` : ''}
              </span>
            )}
          </div>
        </div>
      </div>
    </a>
  );
}

function TypeFilterChips({ active }: { active: VcType | '' }) {
  return (
    <div className="flex gap-2 flex-wrap text-[11px]">
      <Link
        href="?"
        className={
          'px-2.5 py-1 rounded-md font-medium border transition-colors ' +
          (active === ''
            ? 'bg-accent-soft text-text border-accent'
            : 'bg-surface text-text-dim border-border hover:bg-surface-hi hover:text-text')
        }
      >
        All
      </Link>
      {TYPES_ORDER.map((t) => {
        const meta = TYPE_LABELS[t];
        const on = active === t;
        return (
          <Link
            key={t}
            href={`?type=${t}`}
            className={
              'px-2.5 py-1 rounded-md font-medium border transition-colors ' +
              (on
                ? 'bg-accent-soft text-text border-accent'
                : 'bg-surface text-text-dim border-border hover:bg-surface-hi hover:text-text')
            }
          >
            {meta.emoji} {meta.label}
          </Link>
        );
      })}
    </div>
  );
}

export default function VcPage({
  searchParams,
}: {
  searchParams: { type?: string; days?: string };
}) {
  const dates = listVcDates();
  if (dates.length === 0) {
    return (
      <main>
        <Nav />
        <div className="px-6 py-10 text-text-mute text-[13px]">
          No VC articles yet. The pipeline writes <code className="text-text font-mono">data/vc/&lt;date&gt;.jsonl</code> after each scrape.
        </div>
      </main>
    );
  }

  const today = todayUTC();
  const daysBack = Math.max(1, Math.min(30, Number(searchParams.days ?? '14') || 14));
  const to = today;
  const fromDate = new Date(today + 'T00:00:00Z');
  fromDate.setUTCDate(fromDate.getUTCDate() - (daysBack - 1));
  const from = fromDate.toISOString().slice(0, 10);

  const typeFilter = (searchParams.type ?? '') as VcType | '';
  let rounds = loadVcRange(from, to);
  if (typeFilter && TYPE_LABELS[typeFilter]) {
    rounds = rounds.filter((r) => r.vc_type === typeFilter);
  }
  rounds.sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''));

  // Counts per type for the badge in the toolbar
  const countsByType: Partial<Record<VcType, number>> = {};
  for (const r of loadVcRange(from, to)) {
    countsByType[r.vc_type] = (countsByType[r.vc_type] ?? 0) + 1;
  }

  return (
    <main>
      <Nav />
      <div className="flex flex-col gap-2 px-5 py-3 border-b border-border">
        <TypeFilterChips active={typeFilter} />
        <div className="text-[10px] text-text-mute">
          last {daysBack} days · {rounds.length} {rounds.length === 1 ? 'article' : 'articles'}
          {typeFilter && (
            <>
              {' '}· filtered by{' '}
              <span className="text-warn">{TYPE_LABELS[typeFilter].label.toLowerCase()}</span>
            </>
          )}
          {!typeFilter && (
            <span className="ml-2 text-text-dim">
              {TYPES_ORDER.map((t) => `${TYPE_LABELS[t].emoji}${countsByType[t] ?? 0}`).join(' · ')}
            </span>
          )}
        </div>
      </div>
      <div className="max-w-[900px] mx-auto px-5 py-5">
        {rounds.length === 0 ? (
          <div className="text-text-mute text-[13px] py-10 text-center border border-dashed border-border rounded">
            No VC articles matching the current filter.
          </div>
        ) : (
          <div>
            {rounds.map((r) => (
              <Row key={r.story_url} r={r} today={today} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
