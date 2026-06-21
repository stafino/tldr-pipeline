'use client';

import { useMemo, useState } from 'react';
import { copyRichToClipboard, copyTextToClipboard } from '@/lib/clipboard';
import { downloadEml } from '@/lib/eml-builder';
import {
  buildEmailHtmlIssue,
  buildMarkdownIssue,
  buildPlainTextIssue,
  type IssueDoc,
} from '@/lib/issue-formatters';
import type { VcArticle, VcType } from '@/lib/types';
import { canonicalDomain } from '@/lib/utils';

interface Section {
  key: VcType;
  emoji: string;
  name: string;
}

function pickRead(headline: string, summary: string): number {
  const w = (summary || headline).split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.min(6, Math.ceil(w / 200)));
}

function buildMetaLine(r: VcArticle): string | null {
  if (r.firms.length === 0 && r.region === 'OTHER') return null;
  return [r.region !== 'OTHER' ? r.region : '', ...r.firms.slice(0, 4)]
    .filter(Boolean)
    .join(' · ');
}

function toIssueDoc(
  label: string,
  sections: Section[],
  bySection: Partial<Record<VcType, VcArticle[]>>,
  tagline: string | null,
): IssueDoc {
  return {
    title: label,
    tagline,
    sections: sections.map((sec) => ({
      emoji: sec.emoji,
      name: sec.name,
      stories: (bySection[sec.key] ?? []).map((r) => ({
        url: r.story_url,
        title: r.headline_summary || r.title,
        minuteRead: pickRead(r.title, r.headline_summary),
        blurb: r.blurb || null,
        meta: buildMetaLine(r),
      })),
    })),
  };
}

export default function VcIssueExport({
  issueLabel,
  sections,
  bySection,
}: {
  issueLabel: string;
  sections: Section[];
  bySection: Partial<Record<VcType, VcArticle[]>>;
}) {
  // VC plain-text strips the tagline em-dash flourish for a tighter look;
  // markdown + email HTML keep the full "— funds, partners, exits, signals"
  // version. Build two docs with the differing taglines.
  const docFull = useMemo<IssueDoc>(
    () =>
      toIssueDoc(
        issueLabel,
        sections,
        bySection,
        'A daily digest of the venture capital industry — funds, partners, exits, signals.',
      ),
    [issueLabel, sections, bySection],
  );
  const docPlain = useMemo<IssueDoc>(
    () =>
      toIssueDoc(
        issueLabel,
        sections,
        bySection,
        'A daily digest of the venture capital industry.',
      ),
    [issueLabel, sections, bySection],
  );

  const md = useMemo(() => buildMarkdownIssue(docFull, { emitMeta: true }), [docFull]);
  const txt = useMemo(
    () =>
      buildPlainTextIssue(docPlain, {
        titleTrailingBlankLines: 1,
        blankBeforeSection: true,
      }),
    [docPlain],
  );
  const html = useMemo(
    () =>
      buildEmailHtmlIssue(docFull, {
        titlePaddingBottom: 8,
        taglinePaddingBottom: 32,
        taglineFontSize: 13,
        taglineColor: '#666',
        storyLinkPaddingBottom: 12,
        blurbPadding: { kind: 'fixed', value: 16 },
        metaStyle: { paddingBottom: 32, color: '#666', fontSize: 12 },
        emptyStorySpacer: true,
      }),
    [docFull],
  );

  const [flash, setFlash] = useState<string>('');
  function toast(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(''), 2500);
  }

  async function copyRich() {
    const ok = await copyRichToClipboard(html, txt);
    toast(ok ? 'Issue copied — paste into your email' : 'Copy blocked by browser');
  }

  async function copyMd() {
    const ok = await copyTextToClipboard(md);
    toast(ok ? 'Markdown copied' : 'Copy blocked');
  }

  async function emailDraft() {
    await copyRich();
    window.location.href = `mailto:?subject=${encodeURIComponent(issueLabel)}`;
  }

  function downloadEmlFile() {
    downloadEml({
      filename: `tldr-vc-${issueLabel.slice(-10)}.eml`,
      subject: issueLabel,
      plainText: txt,
      html,
    });
  }

  return (
    <div className="mt-10 pt-6 border-t border-border">
      <div className="text-[11px] uppercase tracking-[0.08em] text-text-mute font-semibold mb-3">
        Ship this issue
      </div>
      <div className="flex flex-wrap gap-3 items-center">
        <button
          onClick={emailDraft}
          className="px-4 py-2 rounded-md bg-accent text-text text-[12px] font-medium hover:opacity-90"
        >
          ✉ Open in email draft
        </button>
        <button
          onClick={copyRich}
          className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
        >
          ⧉ Copy formatted
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
