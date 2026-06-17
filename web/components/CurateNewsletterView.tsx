'use client';

import { useDecisions } from './useDecisions';
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
    </div>
  );
}
