'use client';

import type { Blurb, FundingRound } from '@/lib/types';
import { canonicalDomain } from '@/lib/utils';

function fmtUsd(usd: number | null, raw: string): string {
  if (!usd) return raw || '—';
  if (usd >= 1_000_000_000) return `$${(usd / 1_000_000_000).toFixed(usd >= 10_000_000_000 ? 0 : 1)}B`;
  if (usd >= 1_000_000) return `$${Math.round(usd / 1_000_000)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `$${usd}`;
}

export default function FundingDetailPane({
  round,
  blurb,
}: {
  round: FundingRound | null;
  blurb: Blurb | undefined;
}) {
  if (!round) {
    return (
      <div className="text-text-mute text-[12px] text-center px-6 py-9 border border-dashed border-border rounded-md">
        Click a round to load it here.
      </div>
    );
  }

  const domain = canonicalDomain(round.story_url) || round.source;

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline gap-2 mb-1">
          <h3 className="text-[16px] font-semibold m-0 text-text">{round.company}</h3>
          {round.country && (
            <span className="font-mono text-[10.5px] text-text-mute">· {round.country}</span>
          )}
        </div>
        <div className="flex items-baseline gap-2 flex-wrap text-[12px]">
          <span className="font-mono font-bold text-warn text-[14px]">
            {fmtUsd(round.amount_usd, round.amount_raw)}
          </span>
          {round.round_label && (
            <span className="font-mono text-[11px] text-text-dim uppercase tracking-[0.05em]">
              {round.round_label}
            </span>
          )}
          {round.valuation_usd ? (
            <span className="font-mono text-[11px] text-ok">
              @ {fmtUsd(round.valuation_usd, '')} val
            </span>
          ) : null}
          <span
            className={`font-mono text-[10px] px-1.5 py-0.5 rounded ml-auto ${
              round.region === 'EU'
                ? 'bg-accent-soft text-accent border border-accent'
                : 'bg-surface text-text-dim border border-border'
            }`}
          >
            {round.region}
          </span>
        </div>
      </div>

      {round.investors.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute mb-1.5 font-semibold">
            Investors
          </div>
          <div className="flex flex-wrap gap-1.5">
            {round.investors.map((inv) => (
              <span
                key={inv}
                className="font-mono text-[11px] text-text-dim bg-surface border border-border rounded px-2 py-0.5"
              >
                {inv}
              </span>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute mb-1.5 font-semibold">
          Blurb {blurb ? `· ${blurb.word_count} words` : ''}
        </div>
        {blurb ? (
          <p className="text-[13.5px] leading-[1.55] text-text whitespace-pre-wrap m-0">
            {blurb.blurb}
          </p>
        ) : (
          <p className="text-[12px] text-text-mute italic m-0">
            No blurb generated for this story yet.
          </p>
        )}
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-[0.08em] text-text-mute mb-1.5 font-semibold">
          Source
        </div>
        <a
          href={round.story_url}
          target="_blank"
          rel="noopener"
          className="text-[12px] text-accent hover:underline break-all"
        >
          {round.title}
        </a>
        <div className="text-[10.5px] text-text-mute font-mono mt-1">{domain}</div>
      </div>
    </div>
  );
}
