/**
 * Shared escapers - used by every issue-export builder + CSV export.
 * Three identical implementations existed in EditionStories, VcIssueExport
 * and FundingCsvExport. One source of truth here.
 */

const HTML_ENTITIES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Escape a string for safe use inside HTML element bodies + attribute values. */
export function escapeHtml(s: string): string {
  return (s ?? '').replace(/[&<>"']/g, (c) => HTML_ENTITIES[c] ?? c);
}

/** Escape a single cell value for CSV (RFC 4180). */
export function escapeCsv(cell: unknown): string {
  if (cell === null || cell === undefined) return '';
  const s = String(cell);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}
