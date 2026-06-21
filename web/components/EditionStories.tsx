'use client';

import { useMemo, useState } from 'react';
import { copyRichToClipboard, copyTextToClipboard } from '@/lib/clipboard';
import { downloadEml } from '@/lib/eml-builder';
import {
  buildEmailHtmlIssue,
  buildMarkdownIssue,
  buildPlainTextIssue,
  buildSemanticHtmlIssue,
  type IssueDoc,
} from '@/lib/issue-formatters';
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

  const issueDoc = useMemo<IssueDoc>(
    () => ({
      title: `${newsletterBrand} ${date}`,
      sections: sections.map((sec) => ({
        emoji: sec.emoji,
        name: sec.name,
        stories: (bySection[sec.id] ?? []).map((it) => ({
          url: it.url,
          title: it.title,
          minuteRead: it.minute_read,
          blurb: it.blurb || null,
        })),
      })),
    }),
    [newsletterBrand, date, sections, bySection],
  );
  // Edition markdown uses "Brand · Date"; plain text, email HTML and
  // semantic HTML all use "Brand Date" (no separator).
  const issueDocMd = useMemo<IssueDoc>(
    () => ({ ...issueDoc, title: `${newsletterBrand} · ${date}` }),
    [issueDoc, newsletterBrand, date],
  );

  const issueText = useMemo(
    () =>
      buildPlainTextIssue(issueDoc, {
        titleTrailingBlankLines: 2,
        extraBlankBetweenStories: true,
        blankAfterSection: true,
        blurbFallback: '(blurb not generated)',
      }),
    [issueDoc],
  );
  const issueHtml = useMemo(
    () =>
      buildEmailHtmlIssue(issueDoc, {
        titlePaddingBottom: 40,
        storyLinkPaddingBottom: 20,
        blurbPadding: { kind: 'edition', betweenStories: 40, lastInSection: 48 },
        blurbFallback: { text: '(blurb not generated)', color: '#999' },
      }),
    [issueDoc],
  );
  const issueRichHtml = useMemo(
    () => buildSemanticHtmlIssue(issueDoc, { blurbFallback: '(blurb not generated)' }),
    [issueDoc],
  );
  const issueMarkdown = useMemo(() => buildMarkdownIssue(issueDocMd), [issueDocMd]);

  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle');

  function flashOk() {
    setCopyState('copied');
    setTimeout(() => setCopyState('idle'), 3000);
  }
  function flashErr() {
    setCopyState('error');
    setTimeout(() => setCopyState('idle'), 3000);
  }

  async function copyBody() {
    // Rich HTML + plain-text fallback to clipboard - pasting into
    // Gmail/Apple Mail picks up the formatted version with real
    // hyperlinks.
    const ok = await copyRichToClipboard(issueHtml, issueText);
    ok ? flashOk() : flashErr();
    return ok;
  }

  async function exportToEmail() {
    await copyBody();
    const subject = `${newsletterBrand} ${date}`;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}`;
  }

  async function copyMarkdown() {
    // Markdown for Ghost / Notion / GitHub. Substack + Beehiiv use the
    // copyForEditor path since their editors render raw "## " text.
    const ok = await copyTextToClipboard(issueMarkdown);
    ok ? flashOk() : flashErr();
  }

  async function copyForEditor() {
    // Semantic HTML mapped to native blocks by TipTap-based editors
    // (Substack, Beehiiv).
    const ok = await copyRichToClipboard(issueRichHtml, issueText);
    ok ? flashOk() : flashErr();
  }

  function downloadEmlFile() {
    // RFC 822 multipart/alternative - opening the file in Apple Mail
    // loads it as a draft with HTML intact, no paste normalization.
    downloadEml({
      filename: `${newsletterId}-${date}.eml`,
      subject: `${newsletterBrand} ${date}`,
      plainText: issueText,
      html: issueHtml,
    });
  }

  return (
    <div className="px-4 sm:px-5 py-5 max-w-[1100px]">
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
              onClick={copyForEditor}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
              title="Paste into Substack or Beehiiv post editor - maps to native heading / bold link / paragraph blocks"
            >
              ⧉ copy for Substack/Beehiiv
            </button>
            <button
              onClick={copyMarkdown}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
              title="Paste into Ghost, Notion, GitHub, docs - any .md editor"
            >
              ⧉ copy as Markdown
            </button>
            <button
              onClick={downloadEmlFile}
              className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
              title="Double-click the file to open as a real email draft - spacing stays intact"
            >
              ⬇ download .eml (1:1)
            </button>
            {copyState === 'copied' && (
              <span className="text-[12px] text-ok">
                copied - paste (⌘V) into your email
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

