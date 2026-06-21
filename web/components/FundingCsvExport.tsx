'use client';

import { escapeCsv } from '@/lib/escape';
import type { FundingRound } from '@/lib/types';

/**
 * One-click CSV export of the rows currently visible on /funding. Mirrors
 * the column order Crunchbase News uses in its weekly funding wraps.
 */
function buildCsv(rounds: FundingRound[]): string {
  const header = [
    'raised_date',
    'company',
    'amount_usd',
    'amount_raw',
    'stage',
    'region',
    'country',
    'investors',
    'valuation_usd',
    'source_url',
    'title',
  ];
  const rows = rounds.map((r) =>
    [
      r.raised_date,
      r.company,
      r.amount_usd ?? '',
      r.amount_raw,
      r.round_label,
      r.region,
      r.country,
      r.investors.join('; '),
      r.valuation_usd ?? '',
      r.story_url,
      r.title,
    ]
      .map(escapeCsv)
      .join(','),
  );
  return [header.join(','), ...rows].join('\n') + '\n';
}

export default function FundingCsvExport({
  rounds,
  filename,
}: {
  rounds: FundingRound[];
  filename: string;
}) {
  function download() {
    const csv = buildCsv(rounds);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <button
      onClick={download}
      disabled={rounds.length === 0}
      className="text-[11px] text-text-mute hover:text-text px-2 py-1 rounded border border-transparent hover:border-border disabled:opacity-40 disabled:hover:border-transparent"
      title={`Export ${rounds.length} visible rounds to CSV`}
    >
      ⬇ CSV ({rounds.length})
    </button>
  );
}
