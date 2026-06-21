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
  // Render in UTC so the row label matches the UTC-keyed "Filter by date" bucket.
  const base = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(dt);
  const year = Number(
    new Intl.DateTimeFormat('en-US', { year: 'numeric', timeZone: 'UTC' }).format(dt),
  );
  return year === targetYear ? base : `${base}, ${year}`;
}
