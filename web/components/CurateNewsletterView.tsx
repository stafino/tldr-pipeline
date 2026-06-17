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

  const approved = candidates.filter((c) => approvedUrls.has(c.story.story.url));
  // Keep approved order stable across sections by their primary section
  approved.sort((a, b) => {
    const ai = sections.findIndex((s) => s.id === a.sectionId);
    const bi = sections.findIndex((s) => s.id === b.sectionId);
    if (ai !== bi) return ai - bi;
    return b.scoreInSection - a.scoreInSection;
  });

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
  const totalShown = approved.length + remainingCount;

  return (
    <div>
      <div className="flex items-baseline gap-3 pb-3 mb-1 border-b border-border-strong">
        <h2 className="text-[13px] font-bold tracking-tight m-0">{newsletterBrand}</h2>
        <span className="text-[11px] text-text-mute ml-auto">
          {approved.length > 0 ? `${approved.length} accepted · ` : ''}
          {totalShown} stories · {selectedDate}
        </span>
      </div>

      {totalShown === 0 && (
        <div className="text-text-mute text-[12px] py-5 px-1">
          No stories assigned to {newsletterBrand} for {selectedDate}.
        </div>
      )}

      {approved.length > 0 && (
        <div>
          <div className="flex items-center gap-2.5 pt-4 pb-2 border-b border-border bg-bg">
            <span className="text-[14px] leading-none text-ok">✓</span>
            <h3 className="text-[12px] uppercase tracking-[0.06em] font-semibold m-0 text-ok">
              Accepted
            </h3>
            <span className="text-[11px] text-text-mute ml-auto">{approved.length}</span>
          </div>
          {approved.map((c, i) => {
            const sec = sections.find((s) => s.id === c.sectionId);
            return (
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
                sectionMin={sec?.min_words ?? 40}
                sectionMax={sec?.max_words ?? 80}
                publishedShort={c.publishedShort}
              />
            );
          })}
        </div>
      )}

      {sections.map((sec) => {
        const stories = bySec[sec.id];
        if (!stories || stories.length === 0) return null;
        return (
          <div key={sec.id}>
            <div className="flex items-center gap-2.5 pt-4 pb-2 border-b border-border bg-bg">
              <span className="text-[16px]">{sec.emoji}</span>
              <h3 className="text-[12px] uppercase tracking-[0.06em] font-semibold m-0">
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
  );
}
