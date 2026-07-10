import type { MetadataRoute } from 'next';

const SITE_URL = 'https://www.trylede.com';

// Only the canonical, query-less pathnames. Keeps crawlers off the
// query-string permutations that drove the function-invocation blowup.
const PATHS = [
  '/',
  '/edition',
  '/funding',
  '/monday-raises',
  '/vc',
  '/vc/issue',
  '/vc/recap',
  '/vc/preview',
  '/backtest',
];

export default function sitemap(): MetadataRoute.Sitemap {
  return PATHS.map((p) => ({ url: `${SITE_URL}${p}`, changeFrequency: 'daily', priority: p === '/' ? 1 : 0.6 }));
}
