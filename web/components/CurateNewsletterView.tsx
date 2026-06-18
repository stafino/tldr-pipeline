'use client';

import { useSearchParams } from 'next/navigation';
import { useDecisions } from './useDecisions';
import useCurateKeyboard from './useCurateKeyboard';
import StoryRow from './StoryRow';
import type { ScoredStory, Blurb } from '@/lib/types';

interface SectionData {
  id: string;
  name: string;
  emoji: string;
  min_words: number;
  max_words: number;
  target_count: number;
}

interface Candidate {
  story: ScoredStory;
  blurb: Blurb | null;
  sectionId: string;
  scoreInSection: number;
  publishedShort: string;
}

export default function CurateNewsletterView({
  newsletterId,
  newsletterBrand,
  sections,
  candidates,
  selectedDate,
  selectedStoryUrl,
  selectedDetailNlId,
}: {
  newsletterId: string;
  newsletterBrand: string;
  sections: SectionData[];
  candidates: Candidate[];
  selectedDate: string;
  selectedStoryUrl?: string;
  selectedDetailNlId: string;
}) {
  const { decisions } = useDecisions();

  const approvedUrls = new Set<string>();
  for (const c of candidates) {
    const d = decisions[`${c.story.story.url}||${newsletterId}`];
    if (d?.status === 'approved') approvedUrls.add(c.story.story.url);
  }

  // Group accepted by section in the same order as the newsletter's sections,
  // so the "Accepted" block mirrors the section breakdown below.
  const approvedBySec: Record<string, Candidate[]> = {};
  for (const sec of sections) approvedBySec[sec.id] = [];
  for (const c of candidates) {
    if (!approvedUrls.has(c.story.story.url)) continue;
    if (approvedBySec[c.sectionId]) approvedBySec[c.sectionId].push(c);
  }
  for (const sec of sections) {
    approvedBySec[sec.id].sort((a, b) => b.scoreInSection - a.scoreInSection);
  }
  const approvedCount = sections.reduce(
    (sum, s) => sum + approvedBySec[s.id].length,
    0,
  );

  // Per-section view: top-N by section score, excluding already-accepted stories.
  const bySec: Record<string, Candidate[]> = {};
  for (const sec of sections) bySec[sec.id] = [];
  for (const c of candidates) {
    if (approvedUrls.has(c.story.story.url)) continue;
    if (bySec[c.sectionId]) bySec[c.sectionId].push(c);
  }
  for (const sec of sections) {
    bySec[sec.id].sort((a, b) => b.scoreInSection - a.scoreInSection);
    bySec[sec.id] = bySec[sec.id].slice(0, sec.target_count);
  }

  const remainingCount = sections.reduce((sum, s) => sum + bySec[s.id].length, 0);
  const totalShown = approvedCount + remainingCount;

  // Flatten the visible stories in the exact render order so j/k navigation
  // matches what the user sees. Accepted block first, then Backlog.
  const orderedUrls: string[] = [];
  for (const sec of sections) {
    for (const c of approvedBySec[sec.id] ?? []) orderedUrls.push(c.story.story.url);
  }
  for (const sec of sections) {
    for (const c of bySec[sec.id] ?? []) orderedUrls.push(c.story.story.url);
  }

  const sp = useSearchParams();
  function hrefForUrl(url: string): string {
    const next = new URLSearchParams(sp.toString());
    next.set('story', url);
    next.set('nl_detail', newsletterId);
    if (!next.has('nl')) next.set('nl', newsletterId);
    return '?' + next.toString();
  }

  const { showHelp, closeHelp } = useCurateKeyboard({
    orderedUrls,
    selectedUrl: selectedStoryUrl,
    newsletterId,
    hrefForUrl,
    openUrlForSelected: selectedStoryUrl,
  });

  return (
    <div>
      <div className="flex items-baseline gap-3 pb-3 mb-1 border-b border-border-strong">
        <h2 className="text-[13px] font-bold tracking-tight m-0">{newsletterBrand}</h2>
        <span className="text-[11px] text-text-mute ml-auto">
          {approvedCount > 0 ? `${approvedCount} accepted · ` : ''}
          {totalShown} stories · {selectedDate}
        </span>
      </div>

      {totalShown === 0 && (
        <div className="text-text-mute text-[12px] py-5 px-1">
          No stories assigned to {newsletterBrand} for {selectedDate}.
        </div>
      )}

      {approvedCount > 0 && (
        <div className="mb-1">
          <div className="flex items-center gap-2.5 pt-4 pb-2 border-b border-border-strong bg-bg">
            <span className="text-[14px] leading-none text-ok">✓</span>
            <h2 className="text-[12px] uppercase tracking-[0.06em] font-semibold m-0 text-ok">
              Accepted
            </h2>
            <span className="text-[11px] text-text-mute ml-auto">{approvedCount}</span>
          </div>
          {sections.map((sec) => {
            const stories = approvedBySec[sec.id];
            if (!stories || stories.length === 0) return null;
            return (
              <div key={`accepted-${sec.id}`}>
                <div className="flex items-center gap-2.5 pt-3 pb-1.5 border-b border-border bg-bg pl-1">
                  <span className="text-[14px]">{sec.emoji}</span>
                  <h3 className="text-[11px] uppercase tracking-[0.06em] font-semibold m-0 text-text-dim">
                    {sec.name}
                  </h3>
                  <span className="text-[11px] text-text-mute ml-auto">{stories.length}</span>
                </div>
                {stories.map((c, i) => (
                  <StoryRow
                    key={c.story.story.url}
                    story={c.story}
                    newsletterId={newsletterId}
                    detailNewsletterId={newsletterId}
                    rank={i + 1}
                    blurb={c.blurb ?? undefined}
                    selected={
                      selectedStoryUrl === c.story.story.url &&
                      selectedDetailNlId === newsletterId
                    }
                    sectionMin={sec.min_words}
                    sectionMax={sec.max_words}
                    publishedShort={c.publishedShort}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}

      {remainingCount > 0 && (
        <div>
          <div className="flex items-center gap-2.5 pt-6 pb-2 border-b border-border-strong bg-bg">
            <span className="text-[14px] leading-none text-warn">★</span>
            <h2 className="text-[12px] uppercase tracking-[0.06em] font-semibold m-0 text-warn">
              Backlog
            </h2>
            <span className="text-[11px] text-text-mute ml-auto">{remainingCount}</span>
          </div>
          {sections.map((sec) => {
            const stories = bySec[sec.id];
            if (!stories || stories.length === 0) return null;
            return (
              <div key={sec.id}>
                <div className="flex items-center gap-2.5 pt-3 pb-1.5 border-b border-border bg-bg pl-1">
                  <span className="text-[14px]">{sec.emoji}</span>
                  <h3 className="text-[11px] uppercase tracking-[0.06em] font-semibold m-0 text-text-dim">
                    {sec.name}
                  </h3>
                  <span className="text-[11px] text-text-mute ml-auto">{stories.length}</span>
                </div>
                {stories.map((c, i) => (
                  <StoryRow
                    key={c.story.story.url}
                    story={c.story}
                    newsletterId={newsletterId}
                    detailNewsletterId={newsletterId}
                    rank={i + 1}
                    blurb={c.blurb ?? undefined}
                    selected={
                      selectedStoryUrl === c.story.story.url &&
                      selectedDetailNlId === newsletterId
                    }
                    sectionMin={sec.min_words}
                    sectionMax={sec.max_words}
                    publishedShort={c.publishedShort}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}

      {showHelp && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={closeHelp}
        >
          <div
            className="bg-surface border border-border-strong rounded-lg p-6 max-w-md w-[90%]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-baseline justify-between mb-3 pb-2 border-b border-border">
              <h3 className="text-[14px] font-semibold m-0">Keyboard shortcuts</h3>
              <button
                onClick={closeHelp}
                className="text-text-mute text-[11px] hover:text-text"
              >
                Esc to close
              </button>
            </div>
            <div className="grid grid-cols-[60px_1fr] gap-y-2 gap-x-4 text-[12.5px]">
              <kbd className="font-mono text-text-dim">j / ↓</kbd>
              <span>Next story</span>
              <kbd className="font-mono text-text-dim">k / ↑</kbd>
              <span>Previous story</span>
              <kbd className="font-mono text-text-dim">a</kbd>
              <span>Approve current story</span>
              <kbd className="font-mono text-text-dim">r</kbd>
              <span>Reject current story</span>
              <kbd className="font-mono text-text-dim">u</kbd>
              <span>Undo (reset decision)</span>
              <kbd className="font-mono text-text-dim">o</kbd>
              <span>Open source URL in new tab</span>
              <kbd className="font-mono text-text-dim">?</kbd>
              <span>Toggle this help</span>
              <kbd className="font-mono text-text-dim">Esc</kbd>
              <span>Clear selection / close help</span>
            </div>
            <p className="text-[11px] text-text-mute mt-4 mb-0">
              Shortcuts pause while you&apos;re typing in the blurb editor.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
