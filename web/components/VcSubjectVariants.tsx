'use client';

import { useState } from 'react';
import type { VcArticle, VcType } from '@/lib/types';

/**
 * Beehiiv-style A/B subject-line picker. Derives three angles from the
 * day's top stories — no LLM call, pure deterministic. Click any
 * variant to copy it.
 */
export default function VcSubjectVariants({
  issueNum,
  topByType,
}: {
  issueNum: number;
  topByType: Record<VcType, VcArticle | undefined>;
}) {
  const [flash, setFlash] = useState<string>('');

  function shorten(s: string, max: number): string {
    if (!s) return s;
    if (s.length <= max) return s;
    return s.slice(0, max - 1).trimEnd() + '…';
  }

  // Three angles: lead-with-exit, lead-with-fund, lead-with-people
  const lead = topByType.exit ?? topByType.fund_news ?? topByType.partner_move ?? topByType.market_signal;
  const fund = topByType.fund_news;
  const move = topByType.partner_move;
  const exit = topByType.exit;

  const variants: { label: string; value: string }[] = [];
  if (lead) {
    variants.push({
      label: 'Marquee',
      value: `TLDR VC #${issueNum} — ${shorten(lead.headline_summary || lead.title, 65)}`,
    });
  }
  if (exit) {
    variants.push({
      label: 'Exits angle',
      value: shorten(`🚪 ${exit.headline_summary || exit.title}`, 75),
    });
  } else if (fund) {
    variants.push({
      label: 'Funds angle',
      value: shorten(`💰 ${fund.headline_summary || fund.title}`, 75),
    });
  }
  if (move) {
    variants.push({
      label: 'People angle',
      value: shorten(`🪑 ${move.headline_summary || move.title}`, 75),
    });
  }
  if (variants.length < 3 && fund && exit) {
    variants.push({
      label: 'Funds angle',
      value: shorten(`💰 ${fund.headline_summary || fund.title}`, 75),
    });
  }
  if (variants.length === 0) {
    variants.push({
      label: 'Default',
      value: `TLDR VC #${issueNum} — your daily venture digest`,
    });
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setFlash('subject copied');
      setTimeout(() => setFlash(''), 2000);
    } catch {
      setFlash('copy blocked');
      setTimeout(() => setFlash(''), 2000);
    }
  }

  return (
    <details className="my-6 border border-border rounded-md bg-surface/30">
      <summary className="px-3 py-2 text-[11px] uppercase tracking-[0.08em] text-text-mute font-semibold cursor-pointer hover:text-text">
        Subject line variants (click to copy)
        {flash && <span className="ml-2 text-ok normal-case tracking-normal">— {flash}</span>}
      </summary>
      <div className="px-3 pb-3 space-y-2">
        {variants.map((v) => (
          <button
            key={v.value}
            onClick={() => copy(v.value)}
            className="block w-full text-left text-[12.5px] px-3 py-2 rounded border border-border hover:border-accent hover:bg-surface-hi transition-colors"
            title="Click to copy"
          >
            <span className="text-text-mute font-mono text-[10px] uppercase mr-2">{v.label}</span>
            <span className="text-text">{v.value}</span>
          </button>
        ))}
      </div>
    </details>
  );
}
