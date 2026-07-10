import type { MetadataRoute } from 'next';

const SITE_URL = 'https://www.trylede.com';

// Crawlers were hitting unbounded `?date=&nl=&q=&story=…` permutations, each a
// dynamic function invocation. Disallow any URL with a query string so bots
// only crawl the canonical, cacheable pathnames.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/', disallow: '/*?' }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
