'use client';

import { useEffect, useState } from 'react';
import { useDecisions } from './useDecisions';
import type { Blurb, Newsletter, ScoredStory } from '@/lib/types';
import { canonicalDomain } from '@/lib/utils';

interface Props {
  story: ScoredStory | null;
  newsletter: Newsletter | null;
  blurb: Blurb | undefined;
}

export default function DetailPane({ story, newsletter, blurb }: Props) {
  const { decisions, upsert, reset } = useDecisions();
  const [edited, setEdited] = useState('');

  useEffect(() => {
    if (!story || !newsletter) {
      setEdited('');
      return;
    }
    const key = `${story.story.url}||${newsletter.id}`;
    const decision = decisions[key];
    setEdited(decision?.edited_blurb || blurb?.blurb || '');
  }, [story?.story.url, newsletter?.id, blurb?.blurb, decisions]);

  if (!story || !newsletter) {
    return (
      <div className="text-text-mute text-[12px] text-center px-6 py-9 border border-dashed border-border rounded-md">
        Click a story row to load it here.
      </div>
    );
  }

  const a = story.assignments.find((x) => x.newsletter === newsletter.id) ?? story.assignments[0];
  const section = newsletter.sections.find((s) => s.id === a?.section_id);
  const sectionLabel = section?.name ?? a?.section_id;
  const domain = canonicalDomain(story.story.url) || story.story.source;

  const wc = edited.split(/\s+/).filter(Boolean).length;
  const inRange = section ? wc >= section.min_words && wc <= section.max_words : false;
  const target = section ? `${section.min_words}–${section.max_words}` : '—';

  function approve() {
    upsert(story!.story.url, newsletter!.id, {
      status: 'approved',
      edited_blurb: edited !== (blurb?.blurb || '') ? edited : undefined,
    });
  }
  function rejectIt() {
    upsert(story!.story.url, newsletter!.id, { status: 'rejected' });
  }
  function resetIt() {
    reset(story!.story.url, newsletter!.id);
    setEdited(blurb?.blurb || '');
  }

  // Persist edits as the user types
  function onChangeBlurb(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setEdited(e.target.value);
    upsert(story!.story.url, newsletter!.id, { edited_blurb: e.target.value });
  }

  return (
    <div className="px-1">
      <h2 className="text-[26px] font-bold leading-[1.25] -tracking-[0.018em] text-text mb-3.5">
        {story.story.title}
      </h2>
      <div className="flex items-center gap-2.5 flex-wrap text-[13px] text-text-dim mb-7">
        <a
          href={story.story.url}
          target="_blank"
          rel="noopener"
          className="text-accent font-medium hover:underline"
        >
          {domain} ↗
        </a>
        <span className="text-[11.5px] font-mono font-semibold bg-surface px-2 py-0.5 rounded border border-border text-text">
          score {Math.round(a?.score ?? story.score)}
        </span>
        <span className="text-[11.5px] bg-surface px-2 py-0.5 rounded border border-border">
          {newsletter.brand_name} · {sectionLabel}
        </span>
      </div>

      <div className="text-[11px] font-bold uppercase tracking-[0.1em] text-text-mute mb-2">
        Newsletter summary
      </div>
      <textarea
        value={edited}
        onChange={onChangeBlurb}
        className="w-full bg-transparent border-l-2 border-border pl-4 py-0.5 text-[15.5px] leading-[1.6] text-text outline-none resize-y min-h-[140px] focus:border-accent"
        placeholder={blurb ? '' : '(blurb not generated yet)'}
      />
      <div
        className={
          'text-[12px] mt-1.5 mb-4 ' +
          (section ? (inRange ? 'text-ok' : 'text-warn') : 'text-text-mute')
        }
      >
        {wc} words {inRange ? '✓' : section ? '⚠' : ''} · target {target} · {blurb?.minute_read ?? 5} min read
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={approve}
          className="flex-1 py-2 rounded-md text-[12px] font-medium border bg-ok-soft border-emerald-800 text-emerald-300 hover:bg-emerald-900 hover:text-white transition-colors"
        >
          ✓ approve
        </button>
        <button
          onClick={rejectIt}
          className="flex-1 py-2 rounded-md text-[12px] font-medium border bg-no-soft border-red-900 text-red-300 hover:bg-red-900 hover:text-white transition-colors"
        >
          ✗ reject
        </button>
        <button
          onClick={resetIt}
          className="flex-1 py-2 rounded-md text-[12px] font-medium border bg-surface border-border text-text hover:bg-surface-hi"
        >
          ↺ reset
        </button>
      </div>

      {story.reasoning && (
        <>
          <div className="text-[11px] font-bold uppercase tracking-[0.1em] text-text-mute mt-4 mb-2">
            Why it matters
          </div>
          <p className="text-[14px] text-text-dim leading-[1.6] mb-4">{story.reasoning}</p>
        </>
      )}

      {(story.components || story.boosts || story.hn_points) && (
        <>
          <div className="text-[11px] font-bold uppercase tracking-[0.1em] text-text-mute mt-4 mb-2">
            Why this score?
          </div>
          <ScoreBreakdown story={story} finalScore={Math.round(a?.score ?? story.score)} />
        </>
      )}
    </div>
  );
}

function ScoreBreakdown({ story, finalScore }: { story: ScoredStory; finalScore: number }) {
  const comp = story.components ?? {};
  const boosts = story.boosts ?? {};
  const compLabels: Array<[keyof typeof comp, string, string]> = [
    ['technical', 'Technical substance', '30%'],
    ['novelty', 'Novelty', '25%'],
    ['implications', 'Implications', '20%'],
    ['credibility', 'Source credibility', '15%'],
    ['mainstream', 'Mainstream relevance', '10%'],
  ];
  const boostLabels: Array<[keyof typeof boosts, string]> = [
    ['freshness', 'Freshness'],
    ['source_weight', 'Learned source pref.'],
    ['engagement', 'HN engagement'],
    ['already_covered', 'Already covered'],
  ];

  function cls(v: number) {
    if (v >= 80) return 'text-ok';
    if (v >= 60) return 'text-warn';
    return 'text-text-mute';
  }

  return (
    <table className="w-full text-[12px] my-2.5 border-collapse">
      <tbody>
        {Object.keys(comp).length > 0 && (
          <>
            <tr>
              <td colSpan={3} className="text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold pt-2.5 pb-1.5 border-b border-border-strong">
                Rubric Components
              </td>
            </tr>
            {compLabels.map(([k, label, weight]) => (
              <tr key={k}>
                <td className="text-text-dim py-1.5">{label}</td>
                <td className={`font-mono font-semibold text-right w-12 ${cls(comp[k] ?? 0)}`}>
                  {comp[k] ?? '-'}
                </td>
                <td className="font-mono text-[11px] text-text-mute text-right w-20">{weight}</td>
              </tr>
            ))}
          </>
        )}
        {Object.keys(boosts).length > 0 && (
          <>
            <tr>
              <td colSpan={3} className="text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold pt-3 pb-1.5 border-b border-border-strong">
                Score Boosts
              </td>
            </tr>
            {boostLabels.map(([k, label]) => {
              const v = boosts[k];
              if (v === undefined || v === null) return null;
              const sign = v >= 0 ? '+' : '';
              return (
                <tr key={k}>
                  <td className="text-text-dim py-1.5">{label}</td>
                  <td colSpan={2} className="font-mono text-right">
                    {sign}{v}
                  </td>
                </tr>
              );
            })}
          </>
        )}
        {(story.hn_points || story.hn_comments) && (
          <>
            <tr>
              <td colSpan={3} className="text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold pt-3 pb-1.5 border-b border-border-strong">
                External Signal
              </td>
            </tr>
            <tr>
              <td className="text-text-dim py-1.5">HN points</td>
              <td colSpan={2} className="font-mono text-right">{story.hn_points ?? 0}</td>
            </tr>
            <tr>
              <td className="text-text-dim py-1.5">HN comments</td>
              <td colSpan={2} className="font-mono text-right">{story.hn_comments ?? 0}</td>
            </tr>
          </>
        )}
        <tr>
          <td className="text-text font-bold pt-3">Final score</td>
          <td colSpan={2} className="font-mono font-bold text-right pt-3">{finalScore}</td>
        </tr>
      </tbody>
    </table>
  );
}
