'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useDecisions } from './useDecisions';
import type { ScoredStory, Blurb } from '@/lib/types';

interface Props {
  story: ScoredStory;
  newsletterId: string;       // the newsletter context this row is being shown under
  detailNewsletterId: string; // which newsletter's blurb to show in detail (often same)
  rank: number;
  blurb: Blurb | undefined;
  selected: boolean;
  sectionMin: number;
  sectionMax: number;
  publishedShort: string;
}

export default function StoryRow({
  story,
  newsletterId,
  detailNewsletterId,
  rank,
  blurb,
  selected,
  sectionMin,
  sectionMax,
  publishedShort,
}: Props) {
  const sp = useSearchParams();
  const { decisions } = useDecisions();
  const a = story.assignments.find((x) => x.newsletter === detailNewsletterId) ?? story.assignments[0];
  const score = Math.round(a?.score ?? story.score);

  const decision = decisions[`${story.story.url}||${detailNewsletterId}`];
  const wc = blurb?.word_count ?? 0;
  const wcOut = wc > 0 && (wc < sectionMin || wc > sectionMax);

  let statusGlyph = '●';
  let statusCls = 'text-text-mute';
  if (decision?.status === 'approved') {
    statusGlyph = '✓';
    statusCls = 'text-ok';
  } else if (decision?.status === 'rejected') {
    statusGlyph = '✗';
    statusCls = 'text-no';
  } else if (blurb?.needs_review || wcOut) {
    statusGlyph = '⚠';
    statusCls = 'text-warn';
  }

  const otherChips = story.assignments
    .filter((x) => x.newsletter !== detailNewsletterId)
    .map((x) => x.newsletter.replace('tldr_', ''));

  // Build the href preserving current query params, just updating story selection.
  const next = new URLSearchParams(sp.toString());
  next.set('story', story.story.url);
  next.set('nl_detail', detailNewsletterId);
  if (!next.has('nl')) next.set('nl', newsletterId);

  return (
    <Link
      href={'?' + next.toString()}
      scroll={false}
      className={
        'flex items-start gap-3 px-2 py-2.5 border-b border-border cursor-pointer transition-colors ' +
        (selected ? 'bg-accent-soft border-l-2 border-accent pl-1.5' : 'hover:bg-surface')
      }
    >
      <span className="font-mono text-[11px] text-text-mute w-6 text-right shrink-0 pt-0.5">{rank}</span>
      <span className="font-mono text-[12px] font-bold text-text w-8 shrink-0 pt-0.5">{score}</span>
      <span className="flex-1 min-w-0">
        <span className="text-[13.5px] text-text break-words">{story.story.title}</span>
        <span className="flex flex-wrap items-center gap-1.5 mt-1 text-[10.5px] text-text-mute">
          {publishedShort && (
            <span className="font-mono">
              {publishedShort}<span className="text-border-strong mx-1">·</span>
            </span>
          )}
          {otherChips.map((c) => (
            <span
              key={c}
              className="font-mono px-1.5 py-0.5 rounded bg-surface-hi text-text-dim border border-border"
            >
              {c}
            </span>
          ))}
        </span>
      </span>
      <span className={`text-[14px] leading-none w-6 text-center shrink-0 pt-1 ${statusCls}`}>{statusGlyph}</span>
    </Link>
  );
}
