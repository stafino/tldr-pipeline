import Link from 'next/link';
import { canonicalDomain } from '@/lib/utils';
import { listVcDates, loadVcRange } from '@/lib/data';
import Nav from '@/components/Nav';
import { canonFirm, dedupCanon } from '@/lib/vc-aliases';
import type { VcArticle, VcRegion, VcSector, VcType } from '@/lib/types';

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

const SECTOR_LABELS: Record<VcSector, { label: string; emoji: string }> = {
  ai: { label: 'AI', emoji: '🤖' },
  fintech: { label: 'Fintech', emoji: '💳' },
  crypto: { label: 'Crypto', emoji: '⛓️' },
  climate: { label: 'Climate', emoji: '🌱' },
  biotech: { label: 'Biotech', emoji: '🧬' },
  enterprise: { label: 'Enterprise', emoji: '🏢' },
  consumer: { label: 'Consumer', emoji: '🛍️' },
  deeptech: { label: 'Deep tech', emoji: '🔬' },
  other: { label: 'Other', emoji: '·' },
};

const SECTORS_ORDER: VcSector[] = [
  'ai',
  'fintech',
  'crypto',
  'enterprise',
  'deeptech',
  'climate',
  'biotech',
  'consumer',
  'other',
];

const REGION_LABELS: Record<VcRegion, { label: string; flag: string }> = {
  NA: { label: 'North America', flag: '🇺🇸' },
  EU: { label: 'Europe', flag: '🇪🇺' },
  ASIA: { label: 'Asia', flag: '🌏' },
  GLOBAL: { label: 'Global', flag: '🌐' },
  OTHER: { label: 'Other', flag: '·' },
};

const REGIONS_ORDER: VcRegion[] = ['NA', 'EU', 'ASIA', 'GLOBAL', 'OTHER'];

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

// TypeFilterChips removed — the type pivots live in the hero banner now

export default function VcPage({
  searchParams,
}: {
  searchParams: { type?: string; days?: string; sector?: string; region?: string };
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
  const sectorFilter = (searchParams.sector ?? '') as VcSector | '';
  const regionFilter = (searchParams.region ?? '') as VcRegion | '';

  const allRounds = loadVcRange(from, to);
  let rounds = allRounds;
  if (typeFilter && TYPE_LABELS[typeFilter]) {
    rounds = rounds.filter((r) => r.vc_type === typeFilter);
  }
  if (sectorFilter && SECTOR_LABELS[sectorFilter]) {
    rounds = rounds.filter((r) => (r.sector ?? 'other') === sectorFilter);
  }
  if (regionFilter && REGION_LABELS[regionFilter]) {
    rounds = rounds.filter((r) => r.region === regionFilter);
  }
  rounds.sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''));

  // ─── Aggregates for the volume / heatmap / leaderboard banners ────────
  const countsByType: Partial<Record<VcType, number>> = {};
  const countsBySector: Partial<Record<VcSector, number>> = {};
  const countsByRegion: Partial<Record<VcRegion, number>> = {};
  const firmCounts: Record<string, number> = {};
  for (const r of allRounds) {
    countsByType[r.vc_type] = (countsByType[r.vc_type] ?? 0) + 1;
    const sec: VcSector = (r.sector ?? 'other') as VcSector;
    countsBySector[sec] = (countsBySector[sec] ?? 0) + 1;
    countsByRegion[r.region] = (countsByRegion[r.region] ?? 0) + 1;
    for (const firm of dedupCanon(r.firms ?? [], canonFirm)) {
      firmCounts[firm] = (firmCounts[firm] ?? 0) + 1;
    }
  }
  const topFirms = Object.entries(firmCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);
  const maxSector = Math.max(1, ...Object.values(countsBySector).map((v) => v ?? 0));

  return (
    <main>
      <Nav />
      <div className="flex items-center gap-3 px-5 py-3 border-b border-border text-[10px] text-text-mute">
        Window: <span className="text-text-dim font-mono">last {daysBack} days</span>
        {rounds.length !== allRounds.length && (
          <span className="text-warn">
            (filtered: {rounds.length} of {allRounds.length})
          </span>
        )}
        <span className="ml-auto flex gap-3 text-[11px]">
          <Link href="/vc/issue" className="text-accent hover:underline">
            📰 Today&apos;s issue
          </Link>
          <Link href="/vc/recap" className="text-accent hover:underline">
            🗓️ Weekly recap
          </Link>
          <Link href="/vc/preview" className="text-accent hover:underline">
            🎯 Pitch page
          </Link>
        </span>
      </div>
      <div className="max-w-[1100px] mx-auto px-5 py-5">
        {/* Volume + signal hero — the "this is a real newsletter" banner */}
        <div
          className="rounded-lg border border-border-strong p-5 mb-6"
          style={{ background: 'linear-gradient(135deg, #171717 0%, #1a2030 100%)' }}
        >
          <div className="text-[11px] uppercase tracking-[0.1em] text-text-dim mb-1.5">
            TLDR VC · last {daysBack} days
          </div>
          <div className="text-[26px] font-bold tracking-tight mb-3">
            {allRounds.length} VC-relevant {allRounds.length === 1 ? 'article' : 'articles'}
            <span className="text-text-dim">{' '}· ~{Math.round(allRounds.length / daysBack)}/day</span>
          </div>
          <div className="flex flex-wrap gap-4 text-[12.5px]">
            {TYPES_ORDER.map((t) => (
              <Link
                key={t}
                href={t === typeFilter ? '?' : `?type=${t}`}
                className={
                  'flex items-baseline gap-1.5 hover:text-text transition-colors ' +
                  (t === typeFilter ? 'text-warn' : 'text-text-dim')
                }
              >
                <span className="text-[16px]">{TYPE_LABELS[t].emoji}</span>
                <span className="font-mono font-bold text-text">{countsByType[t] ?? 0}</span>
                <span>{TYPE_LABELS[t].label.toLowerCase()}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Sector heatmap + Geographic split + Investor leaderboard — three small cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {/* Sector heatmap */}
          <div className="border border-border rounded-md p-3">
            <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-2.5">
              Sectors covered
            </div>
            <div className="space-y-1.5">
              {SECTORS_ORDER.filter((s) => (countsBySector[s] ?? 0) > 0).map((s) => {
                const n = countsBySector[s] ?? 0;
                const pct = (n / maxSector) * 100;
                const active = sectorFilter === s;
                return (
                  <Link
                    key={s}
                    href={active ? '?' : `?sector=${s}`}
                    className={`block group ${active ? 'opacity-100' : 'opacity-90 hover:opacity-100'}`}
                  >
                    <div className="flex items-baseline gap-2 mb-0.5">
                      <span className="text-[12px]">{SECTOR_LABELS[s].emoji}</span>
                      <span className={`text-[12px] ${active ? 'text-warn font-semibold' : 'text-text'}`}>
                        {SECTOR_LABELS[s].label}
                      </span>
                      <span className="ml-auto font-mono text-[11px] text-text-mute">{n}</span>
                    </div>
                    <div className="h-1 bg-surface rounded-sm overflow-hidden">
                      <div
                        className={active ? 'h-full bg-warn' : 'h-full bg-accent group-hover:bg-accent'}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Geographic split */}
          <div className="border border-border rounded-md p-3">
            <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-2.5">
              By region
            </div>
            <div className="space-y-1.5">
              {REGIONS_ORDER.filter((r) => (countsByRegion[r] ?? 0) > 0).map((r) => {
                const n = countsByRegion[r] ?? 0;
                const active = regionFilter === r;
                return (
                  <Link
                    key={r}
                    href={active ? '?' : `?region=${r}`}
                    className="flex items-baseline gap-2 text-[12.5px] hover:bg-surface rounded px-1 py-0.5 -mx-1"
                  >
                    <span>{REGION_LABELS[r].flag}</span>
                    <span className={active ? 'text-warn font-semibold' : 'text-text'}>
                      {REGION_LABELS[r].label}
                    </span>
                    <span className="ml-auto font-mono text-[11px] text-text-mute">{n}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Investor leaderboard */}
          <div className="border border-border rounded-md p-3">
            <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-2.5">
              Most-mentioned investors
            </div>
            {topFirms.length === 0 ? (
              <div className="text-[11px] text-text-mute py-2">No firm mentions yet.</div>
            ) : (
              <div className="space-y-1">
                {topFirms.map(([firm, n]) => (
                  <div key={firm} className="flex items-baseline gap-2 text-[12.5px]">
                    <span className="text-text truncate">{firm}</span>
                    <span className="ml-auto font-mono text-[11px] text-text-mute">{n}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {(sectorFilter || regionFilter || typeFilter) && (
          <div className="mb-3 flex items-baseline gap-2 text-[11px]">
            <span className="text-text-mute">Active filters:</span>
            {typeFilter && (
              <Link href={`?${[
                sectorFilter ? `sector=${sectorFilter}` : '',
                regionFilter ? `region=${regionFilter}` : '',
              ].filter(Boolean).join('&')}`}
                className="text-warn hover:underline">
                ✕ {TYPE_LABELS[typeFilter].label}
              </Link>
            )}
            {sectorFilter && (
              <Link href={`?${[
                typeFilter ? `type=${typeFilter}` : '',
                regionFilter ? `region=${regionFilter}` : '',
              ].filter(Boolean).join('&')}`}
                className="text-warn hover:underline">
                ✕ {SECTOR_LABELS[sectorFilter].label}
              </Link>
            )}
            {regionFilter && (
              <Link href={`?${[
                typeFilter ? `type=${typeFilter}` : '',
                sectorFilter ? `sector=${sectorFilter}` : '',
              ].filter(Boolean).join('&')}`}
                className="text-warn hover:underline">
                ✕ {REGION_LABELS[regionFilter].label}
              </Link>
            )}
            <Link href="?" className="text-accent hover:underline ml-1">
              clear all
            </Link>
          </div>
        )}

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
