/**
 * Shared issue-body builders for the email/markdown/HTML export buttons in
 * EditionStories (TLDR Marketing edition) and VcIssueExport (TLDR VC issue).
 *
 * Two callers, same scaffolding (title → sections → stories), but different
 * per-story labels (Edition has no meta line, VC has REGION · firms), blurb
 * fallback rules (Edition shows "(blurb not generated)", VC omits), and a few
 * spacing values in the inline-styled email HTML.
 *
 * Each builder takes a neutral IssueDoc + a small options bag so each caller
 * can produce byte-identical output to its original hand-rolled version.
 */
import { escapeHtml } from '@/lib/escape';

// ---------- Common document shape ----------

export interface IssueStory {
  /** Story link */
  url: string;
  /** Displayed link text (headline) */
  title: string;
  /** "(N minute read)" suffix */
  minuteRead: number;
  /** Body paragraph below the link; null/empty → fallback or omitted */
  blurb: string | null;
  /** Optional sub-line (VC issue: "REGION · firm1 · firm2"); Edition leaves unset */
  meta?: string | null;
}

export interface IssueSection {
  emoji: string;
  name: string;
  stories: IssueStory[];
}

export interface IssueDoc {
  /** Top-of-issue title — e.g. "TLDR Marketing · 2026-06-21" or "TLDR VC 2026-06-21" */
  title: string;
  /** Optional tagline directly under the title (VC issue uses this; Edition does not) */
  tagline?: string | null;
  sections: IssueSection[];
}

// ---------- Plain text ----------

export interface PlainTextOptions {
  /**
   * Edition mirrors the canonical TLDR newsletter whitespace: a blank line
   * between blocks AND a second blank between stories. VC keeps it tight at
   * one blank between blocks.
   */
  extraBlankBetweenStories?: boolean;
  /** Edition emits a blank after each completed section. */
  blankAfterSection?: boolean;
  /** VC emits a leading blank before each section. */
  blankBeforeSection?: boolean;
  /**
   * Edition shows "(blurb not generated)" when missing; VC just skips the
   * paragraph entirely.
   */
  blurbFallback?: string | null;
  /**
   * Edition: two blank lines after the title before the first section.
   * VC: title + tagline + one blank.
   */
  titleTrailingBlankLines?: number;
}

export function buildPlainTextIssue(doc: IssueDoc, opts: PlainTextOptions): string {
  const lines: string[] = [];
  lines.push(doc.title);
  if (doc.tagline) lines.push(doc.tagline);
  const trailing = opts.titleTrailingBlankLines ?? 1;
  for (let i = 0; i < trailing; i++) lines.push('');

  for (const sec of doc.sections) {
    if (sec.stories.length === 0) continue;
    if (opts.blankBeforeSection) lines.push('');
    lines.push(sec.emoji);
    lines.push(sec.name);
    lines.push('');
    for (let i = 0; i < sec.stories.length; i++) {
      const it = sec.stories[i];
      lines.push(`${it.title} (${it.minuteRead} minute read)`);
      lines.push(it.url);
      lines.push('');
      if (it.blurb) {
        lines.push(it.blurb);
        lines.push('');
      } else if (opts.blurbFallback != null) {
        lines.push(opts.blurbFallback);
        lines.push('');
      }
      if (opts.extraBlankBetweenStories && i < sec.stories.length - 1) {
        lines.push('');
      }
    }
    if (opts.blankAfterSection) lines.push('');
  }
  return lines.join('\n').trimEnd() + '\n';
}

// ---------- Markdown ----------

export interface MarkdownOptions {
  /** Edition: none; VC: italic "*REGION · firm*" line under blurb. */
  emitMeta?: boolean;
  /** Edition omits blurb when missing; VC same. */
  blurbFallback?: string | null;
}

export function buildMarkdownIssue(doc: IssueDoc, opts: MarkdownOptions = {}): string {
  const lines: string[] = [];
  lines.push(`# ${doc.title}`);
  lines.push('');
  if (doc.tagline) {
    lines.push(`*${doc.tagline}*`);
    lines.push('');
  }
  for (const sec of doc.sections) {
    if (sec.stories.length === 0) continue;
    lines.push(`## ${sec.emoji} ${sec.name}`);
    lines.push('');
    for (const it of sec.stories) {
      const titleText = `${it.title} (${it.minuteRead} minute read)`;
      lines.push(`**[${titleText}](${it.url})**`);
      lines.push('');
      if (it.blurb) {
        lines.push(it.blurb);
        lines.push('');
      } else if (opts.blurbFallback != null) {
        lines.push(opts.blurbFallback);
        lines.push('');
      }
      if (opts.emitMeta && it.meta) {
        lines.push(`*${it.meta}*`);
        lines.push('');
      }
    }
  }
  return lines.join('\n').trimEnd() + '\n';
}

// ---------- Semantic HTML (Substack / Beehiiv paste) ----------

export interface SemanticHtmlOptions {
  blurbFallback?: string | null;
}

export function buildSemanticHtmlIssue(
  doc: IssueDoc,
  opts: SemanticHtmlOptions = {},
): string {
  const parts: string[] = [];
  parts.push(`<h1>${escapeHtml(doc.title)}</h1>`);
  for (const sec of doc.sections) {
    if (sec.stories.length === 0) continue;
    parts.push(`<h2>${escapeHtml(sec.emoji)} ${escapeHtml(sec.name)}</h2>`);
    for (const it of sec.stories) {
      parts.push(
        `<p><strong><a href="${escapeHtml(it.url)}">${escapeHtml(it.title)} (${it.minuteRead} minute read)</a></strong></p>`,
      );
      if (it.blurb) {
        parts.push(`<p>${escapeHtml(it.blurb)}</p>`);
      } else if (opts.blurbFallback != null) {
        parts.push(`<p><em>${escapeHtml(opts.blurbFallback)}</em></p>`);
      }
    }
  }
  return parts.join('\n');
}

// ---------- Email HTML (heavy inline styles for direct rendering) ----------

/**
 * Cross-client gotchas this version addresses (carried over verbatim from
 * the original Edition export):
 * - Outlook (Windows) ignores font inheritance through <div>, so every
 *   <p> repeats the font-family + size.
 * - Gmail collapses top-level margins between <div>s erratically, so
 *   gaps are produced by padding on the element itself rather than margin.
 * - Gmail rewrites visited <a> colors. Wrapping the link text in an
 *   inner <span> with an explicit color prevents the recolor.
 * - Emoji rendering varies — wrap each emoji in its own font stack so
 *   Gmail-on-Windows falls back to Segoe UI Emoji instead of boxes.
 */
const EMAIL_FONT =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
const EMAIL_EMOJI_FONT =
  "'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif";
const EMAIL_P_BASE = `font-family:${EMAIL_FONT};font-size:15px;line-height:1.55;color:#111;margin:0;`;

export interface EmailHtmlOptions {
  /** Padding-bottom on the title row. Edition: 40 (no tagline). VC: 8 (tagline follows). */
  titlePaddingBottom: number;
  /** Padding-bottom on the tagline row (only used if doc.tagline is set). VC: 32. */
  taglinePaddingBottom?: number;
  /** Tagline font size. VC: 13. */
  taglineFontSize?: number;
  /** Tagline text color. VC: #666. */
  taglineColor?: string;
  /** Padding-bottom on the story <a> paragraph. Edition: 20. VC: 12. */
  storyLinkPaddingBottom: number;
  /**
   * Padding-bottom on the blurb (or fallback) paragraph.
   * Edition uses different values for non-last vs last story in a section
   * (40 vs 48) — set `edition` to enable that branching.
   * VC: single value (16).
   */
  blurbPadding:
    | { kind: 'fixed'; value: number }
    | { kind: 'edition'; betweenStories: number; lastInSection: number };
  /** When blurb is missing, render fallback paragraph with this text. Edition only. */
  blurbFallback?: { text: string; color?: string } | null;
  /**
   * VC emits a per-story meta paragraph after the blurb when firms/region
   * are present. Edition does not use this.
   */
  metaStyle?: { paddingBottom: number; color: string; fontSize: number };
  /**
   * VC: when there's neither a blurb nor a meta line, emit a `&nbsp;` spacer
   * paragraph with `metaStyle.paddingBottom` so the rhythm stays even.
   */
  emptyStorySpacer?: boolean;
}

export function buildEmailHtmlIssue(doc: IssueDoc, opts: EmailHtmlOptions): string {
  const P = EMAIL_P_BASE;
  const parts: string[] = [];
  parts.push(
    `<div style="font-family:${EMAIL_FONT};font-size:15px;line-height:1.55;color:#111;max-width:640px;margin:0 auto;">`,
  );
  parts.push(
    `<p style="${P}text-align:center;font-size:22px;font-weight:700;padding:0 0 ${opts.titlePaddingBottom}px;">${escapeHtml(doc.title)}</p>`,
  );
  if (doc.tagline) {
    const tagFs = opts.taglineFontSize ?? 13;
    const tagColor = opts.taglineColor ?? '#666';
    const tagPad = opts.taglinePaddingBottom ?? 32;
    parts.push(
      `<p style="${P}text-align:center;font-size:${tagFs}px;color:${tagColor};padding:0 0 ${tagPad}px;">${escapeHtml(doc.tagline)}</p>`,
    );
  }

  for (const sec of doc.sections) {
    if (sec.stories.length === 0) continue;
    parts.push(
      `<p style="${P}text-align:center;font-size:32px;line-height:1;padding:0 0 8px;"><span style="font-family:${EMAIL_EMOJI_FONT};">${escapeHtml(sec.emoji)}</span></p>`,
    );
    parts.push(
      `<p style="${P}text-align:center;font-size:14px;font-weight:700;text-transform:uppercase;padding:0 0 28px;">${escapeHtml(sec.name)}</p>`,
    );
    for (let i = 0; i < sec.stories.length; i++) {
      const it = sec.stories[i];
      const linkText = `<span style="color:#111;">${escapeHtml(it.title)} (${it.minuteRead} minute read)</span>`;
      const link = `<a href="${escapeHtml(it.url)}" style="color:#111;font-weight:700;text-decoration:underline;">${linkText}</a>`;
      parts.push(`<p style="${P}padding:0 0 ${opts.storyLinkPaddingBottom}px;">${link}</p>`);

      const blurbPad =
        opts.blurbPadding.kind === 'fixed'
          ? opts.blurbPadding.value
          : i < sec.stories.length - 1
          ? opts.blurbPadding.betweenStories
          : opts.blurbPadding.lastInSection;

      if (it.blurb) {
        parts.push(`<p style="${P}padding:0 0 ${blurbPad}px;">${escapeHtml(it.blurb)}</p>`);
      } else if (opts.blurbFallback) {
        const c = opts.blurbFallback.color;
        const colorRule = c ? `color:${c};` : '';
        parts.push(
          `<p style="${P}padding:0 0 ${blurbPad}px;${colorRule}">${escapeHtml(opts.blurbFallback.text)}</p>`,
        );
      }

      if (opts.metaStyle) {
        const m = opts.metaStyle;
        if (it.meta) {
          parts.push(
            `<p style="${P}padding:0 0 ${m.paddingBottom}px;color:${m.color};font-size:${m.fontSize}px;">${escapeHtml(it.meta)}</p>`,
          );
        } else if (opts.emptyStorySpacer) {
          parts.push(`<p style="${P}padding:0 0 ${m.paddingBottom}px;">&nbsp;</p>`);
        }
      }
    }
  }
  parts.push(`</div>`);
  return parts.join('\n');
}
