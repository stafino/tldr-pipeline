'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useDecisions } from './useDecisions';

interface Candidate {
  url: string;
  title: string;
  domain: string;
  sectionId: string;
  score: number;
  blurb: string;
  minute_read: number;
}

interface Section {
  id: string;
  name: string;
  emoji: string;
}

interface Props {
  newsletterId: string;
  newsletterBrand: string;
  editionSize: number;
  sections: Section[];
  candidates: Candidate[];
  date: string;
}

export default function EditionStories({
  newsletterId,
  newsletterBrand,
  editionSize,
  sections,
  candidates,
  date,
}: Props) {
  const { decisions } = useDecisions();

  const approved = useMemo(() => {
    return candidates.filter((c) => {
      const d = decisions[`${c.url}||${newsletterId}`];
      return d?.status === 'approved';
    });
  }, [candidates, decisions, newsletterId]);

  const bySection: Record<string, Candidate[]> = {};
  for (const sec of sections) bySection[sec.id] = [];
  for (const a of approved) {
    if (bySection[a.sectionId]) bySection[a.sectionId].push(a);
  }
  for (const sid in bySection) bySection[sid].sort((x, y) => y.score - x.score);

  const nApproved = approved.length;
  const capacityColor =
    nApproved < editionSize ? 'text-warn' : nApproved === editionSize ? 'text-ok' : 'text-no';
  const capacityText =
    nApproved < editionSize
      ? 'needs more'
      : nApproved === editionSize
      ? 'ready to publish'
      : 'over capacity';

  const issueText = useMemo(
    () => buildIssueText(newsletterBrand, date, sections, bySection),
    [newsletterBrand, date, sections, bySection],
  );
  const issueHtml = useMemo(
    () => buildIssueHtml(newsletterBrand, date, sections, bySection),
    [newsletterBrand, date, sections, bySection],
  );

  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle');

  function downloadTxt() {
    const blob = new Blob([issueText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${newsletterId}-${date}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function exportToEmail() {
    // Copy rich HTML + plain text to clipboard so paste-into-mail picks up
    // the formatted version with real hyperlinks. Open a fresh mailto: with
    // just the subject pre-filled — the user pastes (⌘V) into the body for
    // the formatted version.
    try {
      if (navigator.clipboard && typeof window !== 'undefined' && (window as any).ClipboardItem) {
        const item = new (window as any).ClipboardItem({
          'text/html': new Blob([issueHtml], { type: 'text/html' }),
          'text/plain': new Blob([issueText], { type: 'text/plain' }),
        });
        await navigator.clipboard.write([item]);
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(issueText);
      }
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('error');
      setTimeout(() => setCopyState('idle'), 2500);
    }
    const subject = `${newsletterBrand} ${date}`;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}`;
  }

  async function copyHtml() {
    try {
      if (navigator.clipboard && typeof window !== 'undefined' && (window as any).ClipboardItem) {
        const item = new (window as any).ClipboardItem({
          'text/html': new Blob([issueHtml], { type: 'text/html' }),
          'text/plain': new Blob([issueText], { type: 'text/plain' }),
        });
        await navigator.clipboard.write([item]);
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(issueText);
      }
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 2500);
    } catch {
      setCopyState('error');
      setTimeout(() => setCopyState('idle'), 2500);
    }
  }

  return (
    <div className="px-5 py-5 max-w-[1100px]">
      <div
        className="rounded-lg border border-border-strong p-5 mb-6"
        style={{ background: 'linear-gradient(135deg, #171717 0%, #1a2030 100%)' }}
      >
        <h2 className="text-[16px] font-semibold mb-1.5">
          {newsletterBrand} · {date}
        </h2>
        <div className="text-[14px] text-text-dim">
          <span className={`font-semibold ${capacityColor}`}>
            {nApproved}/{editionSize}
          </span>{' '}
          stories approved <span className="text-text-mute text-[12px] ml-1">· {capacityText}</span>
        </div>
      </div>

      {nApproved === 0 ? (
        <div className="bg-surface border border-dashed border-border rounded-md py-9 px-6 text-center text-text-mute text-[13px]">
          No stories approved yet. Go to{' '}
          <Link href="/" className="text-accent hover:underline">
            Curate
          </Link>{' '}
          to review candidates and approve the ones you want.
        </div>
      ) : (
        <>
          {sections.map((sec) => {
            const items = bySection[sec.id] ?? [];
            if (items.length === 0) return null;
            return (
              <div key={sec.id}>
                <div className="flex items-center gap-2.5 my-5 pb-2 border-b border-border-strong">
                  <span className="text-[16px]">{sec.emoji}</span>
                  <h3 className="text-[12px] uppercase tracking-[0.06em] font-bold m-0">
                    {sec.name}
                  </h3>
                  <span className="ml-auto text-[11px] text-text-mute">{items.length} approved</span>
                </div>
                {items.map((it, i) => (
                  <div key={it.url} className="py-3 border-b border-border last:border-b-0">
                    <div className="flex items-baseline gap-2.5 mb-1.5">
                      <span className="font-mono text-[11px] text-text-mute w-6 shrink-0">{i + 1}</span>
                      <a
                        href={it.url}
                        target="_blank"
                        rel="noopener"
                        className="flex-1 text-[15px] font-semibold text-text hover:text-accent leading-snug"
                      >
                        {it.title}
                      </a>
                      <span className="text-[11px] text-text-mute whitespace-nowrap">
                        {it.minute_read} min read · {it.domain}
                      </span>
                    </div>
                    {it.blurb && (
                      <p className="text-[14px] text-text-dim leading-[1.55] ml-8 mb-0">
                        {it.blurb}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            );
          })}

          <div className="mt-6 flex gap-3 items-center flex-wrap">
            <button
              onClick={exportToEmail}
              className="px-4 py-2 rounded-md bg-accent text-text text-[12px] font-medium hover:opacity-90"
            >
              ✉ export to email
            </button>
            <button
              onClick={copyHtml}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
            >
              ⧉ copy formatted
            </button>
            <button
              onClick={downloadTxt}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
            >
              ⬇ download .txt
            </button>
            {copyState === 'copied' && (
              <span className="text-[12px] text-ok">copied — paste into your email</span>
            )}
            {copyState === 'error' && (
              <span className="text-[12px] text-no">clipboard blocked — try copy formatted</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function buildIssueText(
  brand: string,
  date: string,
  sections: Section[],
  bySection: Record<string, Candidate[]>,
): string {
  // No TLDR branding at the top — keeps it safely yours to forward.
  const lines: string[] = [];
  lines.push(`${brand} ${date}`);
  lines.push('');
  for (const sec of sections) {
    const items = bySection[sec.id] ?? [];
    if (items.length === 0) continue;
    lines.push(sec.emoji);
    lines.push(sec.name);
    lines.push('');
    for (const it of items) {
      lines.push(`${it.title} (${it.minute_read} minute read)`);
      lines.push(it.url);
      lines.push('');
      lines.push(it.blurb || '(blurb not generated)');
      lines.push('');
    }
  }
  return lines.join('\n').trimEnd() + '\n';
}

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildIssueHtml(
  brand: string,
  date: string,
  sections: Section[],
  bySection: Record<string, Candidate[]>,
): string {
  // Inline styles only — Gmail, Apple Mail and Outlook all strip <style>
  // blocks but keep style="..." attributes on individual elements.
  const FONT =
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
  const parts: string[] = [];
  parts.push(
    `<div style="font-family:${FONT};font-size:15px;line-height:1.55;color:#111;max-width:640px;margin:0 auto;">`,
  );
  parts.push(
    `<div style="font-size:18px;font-weight:700;margin:0 0 24px;">${esc(brand)} ${esc(date)}</div>`,
  );
  for (const sec of sections) {
    const items = bySection[sec.id] ?? [];
    if (items.length === 0) continue;
    parts.push(
      `<div style="text-align:center;font-size:28px;line-height:1;margin:32px 0 6px;">${esc(sec.emoji)}</div>`,
    );
    parts.push(
      `<div style="text-align:center;font-size:14px;font-weight:700;letter-spacing:0.03em;margin:0 0 20px;">${esc(sec.name)}</div>`,
    );
    for (const it of items) {
      const link = `<a href="${esc(it.url)}" style="color:#111;font-weight:700;text-decoration:underline;">${esc(it.title)} (${it.minute_read} minute read)</a>`;
      parts.push(`<p style="margin:0 0 8px;">${link}</p>`);
      if (it.blurb) {
        parts.push(`<p style="margin:0 0 24px;">${esc(it.blurb)}</p>`);
      } else {
        parts.push(`<p style="margin:0 0 24px;color:#999;">(blurb not generated)</p>`);
      }
    }
  }
  parts.push(`</div>`);
  return parts.join('\n');
}
