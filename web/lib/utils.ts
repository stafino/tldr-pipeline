export function canonicalDomain(url: string | undefined): string {
  if (!url) return '';
  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();
    return host.startsWith('www.') ? host.slice(4) : host;
  } catch {
    return '';
  }
}

export function shortDate(iso: string | undefined, targetYear: number): string {
  if (!iso) return '';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return '';
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  const base = new Intl.DateTimeFormat('en-US', opts).format(dt);
  return dt.getFullYear() === targetYear ? base : `${base}, ${dt.getFullYear()}`;
}

export function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}
