/**
 * Clipboard helpers used by every export button.
 *
 * Previously copy-pasted 4+ times across EditionStories.tsx,
 * VcIssueExport.tsx, VcSubjectVariants.tsx, DecisionsSync.tsx.
 * Standardized here.
 */

/** Copy rich HTML + plain-text fallback (paste into mail clients works). */
export async function copyRichToClipboard(html: string, plain: string): Promise<boolean> {
  try {
    if (
      typeof window !== 'undefined' &&
      navigator.clipboard &&
      (window as any).ClipboardItem
    ) {
      const item = new (window as any).ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([plain], { type: 'text/plain' }),
      });
      await navigator.clipboard.write([item]);
    } else if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(plain);
    } else {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

/** Simple text copy. Returns true on success, false on permission denial. */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}
