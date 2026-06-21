'use client';

import { useMemo, useState } from 'react';
import { escapeHtml } from '@/lib/escape';
import { copyRichToClipboard, copyTextToClipboard } from '@/lib/clipboard';
import { downloadEml } from '@/lib/eml-builder';
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

function buildMarkdown(
  label: string,
  sections: Section[],
  bySection: Partial<Record<VcType, VcArticle[]>>,
): string {
  const lines: string[] = [];
  lines.push(`# ${label}`);
  lines.push('');
  lines.push(`*A daily digest of the venture capital industry — funds, partners, exits, signals.*`);
  lines.push('');
  for (const sec of sections) {
    const items = bySection[sec.key] ?? [];
    if (items.length === 0) continue;
    lines.push(`## ${sec.emoji} ${sec.name}`);
    lines.push('');
    for (const r of items) {
      const headline = r.headline_summary || r.title;
      const min = pickRead(r.title, r.headline_summary);
      lines.push(`**[${headline} (${min} minute read)](${r.story_url})**`);
      lines.push('');
      if (r.blurb) {
        lines.push(r.blurb);
        lines.push('');
      }
      if (r.firms.length > 0 || r.region !== 'OTHER') {
        const meta = [
          r.region !== 'OTHER' ? r.region : '',
          ...r.firms.slice(0, 4),
        ].filter(Boolean).join(' · ');
        lines.push(`*${meta}*`);
        lines.push('');
      }
    }
  }
  return lines.join('\n').trimEnd() + '\n';
}

function buildPlainText(
  label: string,
  sections: Section[],
  bySection: Partial<Record<VcType, VcArticle[]>>,
): string {
  const lines: string[] = [];
  lines.push(label);
  lines.push('A daily digest of the venture capital industry.');
  lines.push('');
  for (const sec of sections) {
    const items = bySection[sec.key] ?? [];
    if (items.length === 0) continue;
    lines.push('');
    lines.push(sec.emoji);
    lines.push(sec.name);
    lines.push('');
    for (const r of items) {
      const headline = r.headline_summary || r.title;
      const min = pickRead(r.title, r.headline_summary);
      lines.push(`${headline} (${min} minute read)`);
      lines.push(r.story_url);
      lines.push('');
      if (r.blurb) {
        lines.push(r.blurb);
        lines.push('');
      }
    }
  }
  return lines.join('\n').trimEnd() + '\n';
}

function buildHtml(
  label: string,
  sections: Section[],
  bySection: Partial<Record<VcType, VcArticle[]>>,
): string {
  const FONT =
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
  const EMOJI = "'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif";
  const P = `font-family:${FONT};font-size:15px;line-height:1.55;color:#111;margin:0;`;
  const parts: string[] = [];
  parts.push(
    `<div style="font-family:${FONT};font-size:15px;line-height:1.55;color:#111;max-width:640px;margin:0 auto;">`,
  );
  parts.push(
    `<p style="${P}text-align:center;font-size:22px;font-weight:700;padding:0 0 8px;">${escapeHtml(label)}</p>`,
  );
  parts.push(
    `<p style="${P}text-align:center;font-size:13px;color:#666;padding:0 0 32px;">A daily digest of the venture capital industry — funds, partners, exits, signals.</p>`,
  );
  for (const sec of sections) {
    const items = bySection[sec.key] ?? [];
    if (items.length === 0) continue;
    parts.push(
      `<p style="${P}text-align:center;font-size:32px;line-height:1;padding:0 0 8px;"><span style="font-family:${EMOJI};">${escapeHtml(sec.emoji)}</span></p>`,
    );
    parts.push(
      `<p style="${P}text-align:center;font-size:14px;font-weight:700;text-transform:uppercase;padding:0 0 28px;">${escapeHtml(sec.name)}</p>`,
    );
    for (const r of items) {
      const headline = r.headline_summary || r.title;
      const min = pickRead(r.title, r.headline_summary);
      const link = `<a href="${escapeHtml(r.story_url)}" style="color:#111;font-weight:700;text-decoration:underline;"><span style="color:#111;">${escapeHtml(headline)} (${min} minute read)</span></a>`;
      parts.push(`<p style="${P}padding:0 0 12px;">${link}</p>`);
      if (r.blurb) {
        parts.push(`<p style="${P}padding:0 0 16px;">${escapeHtml(r.blurb)}</p>`);
      }
      if (r.firms.length > 0 || r.region !== 'OTHER') {
        const meta = [
          r.region !== 'OTHER' ? r.region : '',
          ...r.firms.slice(0, 4),
        ].filter(Boolean).join(' · ');
        parts.push(
          `<p style="${P}padding:0 0 32px;color:#666;font-size:12px;">${escapeHtml(meta)}</p>`,
        );
      } else {
        parts.push(`<p style="${P}padding:0 0 32px;">&nbsp;</p>`);
      }
    }
  }
  parts.push(`</div>`);
  return parts.join('\n');
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
  const md = useMemo(() => buildMarkdown(issueLabel, sections, bySection), [issueLabel, sections, bySection]);
  const txt = useMemo(() => buildPlainText(issueLabel, sections, bySection), [issueLabel, sections, bySection]);
  const html = useMemo(() => buildHtml(issueLabel, sections, bySection), [issueLabel, sections, bySection]);

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
