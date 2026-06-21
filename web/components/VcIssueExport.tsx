'use client';

import { useMemo, useState } from 'react';
import type { VcArticle, VcType } from '@/lib/types';
import { canonicalDomain } from '@/lib/utils';

interface Section {
  key: VcType;
  emoji: string;
  name: string;
}

function escHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
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
      if (r.headline_summary && r.title !== r.headline_summary) {
        lines.push(r.title);
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
      if (r.headline_summary && r.title !== r.headline_summary) {
        lines.push(r.title);
      }
      lines.push('');
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
    `<p style="${P}text-align:center;font-size:22px;font-weight:700;padding:0 0 8px;">${escHtml(label)}</p>`,
  );
  parts.push(
    `<p style="${P}text-align:center;font-size:13px;color:#666;padding:0 0 32px;">A daily digest of the venture capital industry — funds, partners, exits, signals.</p>`,
  );
  for (const sec of sections) {
    const items = bySection[sec.key] ?? [];
    if (items.length === 0) continue;
    parts.push(
      `<p style="${P}text-align:center;font-size:32px;line-height:1;padding:0 0 8px;"><span style="font-family:${EMOJI};">${escHtml(sec.emoji)}</span></p>`,
    );
    parts.push(
      `<p style="${P}text-align:center;font-size:14px;font-weight:700;text-transform:uppercase;padding:0 0 28px;">${escHtml(sec.name)}</p>`,
    );
    for (const r of items) {
      const headline = r.headline_summary || r.title;
      const min = pickRead(r.title, r.headline_summary);
      const link = `<a href="${escHtml(r.story_url)}" style="color:#111;font-weight:700;text-decoration:underline;"><span style="color:#111;">${escHtml(headline)} (${min} minute read)</span></a>`;
      parts.push(`<p style="${P}padding:0 0 12px;">${link}</p>`);
      if (r.headline_summary && r.title !== r.headline_summary) {
        parts.push(`<p style="${P}padding:0 0 8px;">${escHtml(r.title)}</p>`);
      }
      if (r.firms.length > 0 || r.region !== 'OTHER') {
        const meta = [
          r.region !== 'OTHER' ? r.region : '',
          ...r.firms.slice(0, 4),
        ].filter(Boolean).join(' · ');
        parts.push(
          `<p style="${P}padding:0 0 32px;color:#666;font-size:12px;">${escHtml(meta)}</p>`,
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
    try {
      if (typeof window !== 'undefined' && (window as any).ClipboardItem) {
        const item = new (window as any).ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([txt], { type: 'text/plain' }),
        });
        await navigator.clipboard.write([item]);
      } else {
        await navigator.clipboard.writeText(txt);
      }
      toast('Issue copied — paste into your email');
    } catch {
      toast('Copy blocked by browser');
    }
  }

  async function copyMd() {
    try {
      await navigator.clipboard.writeText(md);
      toast('Markdown copied');
    } catch {
      toast('Copy blocked');
    }
  }

  async function emailDraft() {
    await copyRich();
    const subject = issueLabel;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}`;
  }

  function downloadEml() {
    const subject = issueLabel;
    const boundary = `=_tldrvc_${Date.now().toString(36)}`;
    const eml = [
      `MIME-Version: 1.0`,
      `Subject: ${subject}`,
      `Content-Type: multipart/alternative; boundary="${boundary}"`,
      ``,
      `--${boundary}`,
      `Content-Type: text/plain; charset=UTF-8`,
      `Content-Transfer-Encoding: 8bit`,
      ``,
      txt,
      `--${boundary}`,
      `Content-Type: text/html; charset=UTF-8`,
      `Content-Transfer-Encoding: 8bit`,
      ``,
      `<!doctype html><html><body>${html}</body></html>`,
      `--${boundary}--`,
      ``,
    ].join('\r\n');
    const blob = new Blob([eml], { type: 'message/rfc822' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tldr-vc-${issueLabel.slice(-10)}.eml`;
    a.click();
    URL.revokeObjectURL(url);
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
          onClick={downloadEml}
          className="px-4 py-2 rounded-md bg-surface border border-border text-text text-[12px] font-medium hover:bg-surface-hi"
        >
          ⬇ .eml (1:1 draft)
        </button>
        {flash && <span className="text-[12px] text-ok">{flash}</span>}
      </div>
    </div>
  );
}
