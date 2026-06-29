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

/**
 * Export buttons for the Monday Raises issue. Substack pastes cleanest from
 * the semantic h1/h2/p HTML (same path the Edition tab uses for Substack /
 * Beehiiv); the .eml + email draft use the heavy inline-styled HTML so the
 * raw message renders standalone.
 */
export default function MondayRaisesExport({
  label,
  doc,
}: {
  label: string;
  doc: IssueDoc;
}) {
  const md = useMemo(() => buildMarkdownIssue(doc, { emitMeta: true }), [doc]);
  const txt = useMemo(
    () => buildPlainTextIssue(doc, { titleTrailingBlankLines: 1, blankBeforeSection: true }),
    [doc],
  );
  const substackHtml = useMemo(() => buildSemanticHtmlIssue(doc), [doc]);
  const emailHtml = useMemo(
    () =>
      buildEmailHtmlIssue(doc, {
        titlePaddingBottom: 8,
        taglinePaddingBottom: 32,
        taglineFontSize: 13,
        taglineColor: '#666',
        storyLinkPaddingBottom: 12,
        blurbPadding: { kind: 'fixed', value: 16 },
        metaStyle: { paddingBottom: 32, color: '#666', fontSize: 12 },
        emptyStorySpacer: true,
      }),
    [doc],
  );

  const [flash, setFlash] = useState('');
  function toast(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(''), 2500);
  }

  async function copySubstack() {
    const ok = await copyRichToClipboard(substackHtml, txt);
    toast(ok ? 'Copied - paste into the Substack editor' : 'Copy blocked by browser');
  }

  async function copyMd() {
    const ok = await copyTextToClipboard(md);
    toast(ok ? 'Markdown copied' : 'Copy blocked');
  }

  async function emailDraft() {
    const ok = await copyRichToClipboard(emailHtml, txt);
    toast(ok ? 'Copied - paste into your email' : 'Copy blocked by browser');
    window.location.href = `mailto:?subject=${encodeURIComponent(label)}`;
  }

  function downloadEmlFile() {
    downloadEml({
      filename: `monday-raises-${label.slice(-10)}.eml`,
      subject: label,
      plainText: txt,
      html: emailHtml,
    });
  }

  return (
    <div className="mt-10 pt-6 border-t border-border">
      <div className="text-[11px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-3">
        Ship this issue
      </div>
      <div className="flex flex-wrap gap-3 items-center">
        <button
          onClick={copySubstack}
          className="px-4 py-2 rounded-md bg-accent text-text text-[12px] font-medium hover:opacity-90"
        >
          ✍ Copy for Substack
        </button>
        <button
          onClick={emailDraft}
          className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
        >
          ✉ Open in email draft
        </button>
        <button
          onClick={copyMd}
          className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
        >
          ⧉ Copy markdown
        </button>
        <button
          onClick={downloadEmlFile}
          className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
        >
          ⬇ .eml (1:1 draft)
        </button>
        {flash && <span className="text-[12px] text-ok">{flash}</span>}
      </div>
    </div>
  );
}
