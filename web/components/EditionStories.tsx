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

  async function copyBody() {
    // Copies the rich HTML (+ plain-text fallback) to the clipboard.
    // Pasting (⌘V) into Gmail/Apple Mail picks up the formatted version
    // with real hyperlinks; pasting into a plain-text field gets the
    // text-only version. mailto: can't carry HTML — every mail client
    // strips it — so the clipboard handoff is what makes the titles
    // render as real links.
    try {
      if (
        typeof window !== 'undefined' &&
        navigator.clipboard &&
        (window as any).ClipboardItem
      ) {
        const item = new (window as any).ClipboardItem({
          'text/html': new Blob([issueHtml], { type: 'text/html' }),
          'text/plain': new Blob([issueText], { type: 'text/plain' }),
        });
        await navigator.clipboard.write([item]);
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(issueText);
      }
      setCopyState('copied');
      setTimeout(() => setCopyState('idle'), 3000);
      return true;
    } catch {
      setCopyState('error');
      setTimeout(() => setCopyState('idle'), 3000);
      return false;
    }
  }

  async function exportToEmail() {
    await copyBody();
    const subject = `${newsletterBrand} ${date}`;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}`;
  }

  function downloadEml() {
    // A full RFC 822 message with multipart/alternative (plain + HTML).
    // Double-click the file → default mail client opens it as a draft
    // with the HTML body intact. Bypasses clipboard normalization
    // entirely, so spacing stays 1:1 with what we generated.
    const subject = `${newsletterBrand} ${date}`;
    const boundary = `=_lede_${Math.floor((Number(date.replace(/-/g, '')) || 0))}_${newsletterId}`;
    const eml = [
      `MIME-Version: 1.0`,
      `Subject: ${subject}`,
      `Content-Type: multipart/alternative; boundary="${boundary}"`,
      ``,
      `--${boundary}`,
      `Content-Type: text/plain; charset=UTF-8`,
      `Content-Transfer-Encoding: 8bit`,
      ``,
      issueText,
      `--${boundary}`,
      `Content-Type: text/html; charset=UTF-8`,
      `Content-Transfer-Encoding: 8bit`,
      ``,
      `<!doctype html><html><body>${issueHtml}</body></html>`,
      `--${boundary}--`,
      ``,
    ].join('\r\n');
    const blob = new Blob([eml], { type: 'message/rfc822' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${newsletterId}-${date}.eml`;
    a.click();
    URL.revokeObjectURL(url);
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
              onClick={copyBody}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
            >
              ⧉ copy body
            </button>
            <button
              onClick={downloadEml}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
              title="Double-click the file to open as a real email draft — spacing stays intact"
            >
              ⬇ download .eml (1:1)
            </button>
            {copyState === 'copied' && (
              <span className="text-[12px] text-ok">
                copied — paste (⌘V) into your email
              </span>
            )}
            {copyState === 'error' && (
              <span className="text-[12px] text-no">clipboard blocked by browser</span>
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
  // Mirrors the canonical TLDR newsletter whitespace: one blank line
  // between every block, two blank lines between stories.
  const lines: string[] = [];
  lines.push(`${brand} ${date}`);
  lines.push('');
  lines.push('');
  for (const sec of sections) {
    const items = bySection[sec.id] ?? [];
    if (items.length === 0) continue;
    lines.push(sec.emoji);
    lines.push(sec.name);
    lines.push('');
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      lines.push(`${it.title} (${it.minute_read} minute read)`);
      lines.push(it.url);
      lines.push('');
      lines.push(it.blurb || '(blurb not generated)');
      lines.push('');
      if (i < items.length - 1) lines.push('');
    }
    lines.push('');
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
  //
  // Cross-client gotchas this version addresses:
  // - Outlook (Windows) ignores font inheritance through <div>, so every
  //   <p> repeats the font-family + size.
  // - Gmail collapses top-level margins between <div>s erratically, so
  //   gaps are produced by explicit empty spacer divs with fixed heights
  //   instead of margin-bottom on the previous element.
  // - Gmail rewrites visited <a> colors. Wrapping the link text in an
  //   inner <span> with an explicit color prevents the recolor.
  // - Emoji rendering varies — wrap each emoji in its own font stack so
  //   Gmail-on-Windows falls back to Segoe UI Emoji instead of boxes.
  const FONT =
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
  const EMOJI_FONT =
    "'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif";
  // Gmail's compose-paste handler collapses spacer <div>s and strips many
  // margins. Padding on the element itself is the one thing it reliably
  // keeps, so all gaps are produced by padding-bottom (or padding-top on
  // the very first child after a section heading).
  const P_BASE = `font-family:${FONT};font-size:15px;line-height:1.55;color:#111;margin:0;`;

  const parts: string[] = [];
  parts.push(
    `<div style="font-family:${FONT};font-size:15px;line-height:1.55;color:#111;max-width:640px;margin:0 auto;">`,
  );
  parts.push(
    `<p style="${P_BASE}text-align:center;font-size:22px;font-weight:700;padding:0 0 40px;">${esc(brand)} ${esc(date)}</p>`,
  );

  for (const sec of sections) {
    const items = bySection[sec.id] ?? [];
    if (items.length === 0) continue;
    parts.push(
      `<p style="${P_BASE}text-align:center;font-size:32px;line-height:1;padding:0 0 8px;"><span style="font-family:${EMOJI_FONT};">${esc(sec.emoji)}</span></p>`,
    );
    parts.push(
      `<p style="${P_BASE}text-align:center;font-size:14px;font-weight:700;text-transform:uppercase;padding:0 0 28px;">${esc(sec.name)}</p>`,
    );
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const linkText = `<span style="color:#111;">${esc(it.title)} (${it.minute_read} minute read)</span>`;
      const link = `<a href="${esc(it.url)}" style="color:#111;font-weight:700;text-decoration:underline;">${linkText}</a>`;
      parts.push(`<p style="${P_BASE}padding:0 0 20px;">${link}</p>`);
      const bottomPad = i < items.length - 1 ? 40 : 48;
      if (it.blurb) {
        parts.push(`<p style="${P_BASE}padding:0 0 ${bottomPad}px;">${esc(it.blurb)}</p>`);
      } else {
        parts.push(
          `<p style="${P_BASE}padding:0 0 ${bottomPad}px;color:#999;">(blurb not generated)</p>`,
        );
      }
    }
  }
  parts.push(`</div>`);
  return parts.join('\n');
}
