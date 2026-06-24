/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Allow reading data files at runtime in both deploy modes:
    //   ../  — GitHub integration (whole repo checked out)
    //   ./_embedded — CLI deploy after `node scripts/embed.mjs`
    outputFileTracingIncludes: {
      '/': [
        '../config/**/*',
        '../data/scored/*.jsonl',
        '../data/blurbs/*.jsonl',
        '../data/backtest/*.json',
        '../data/funding/*.jsonl',
        '../data/vc/*.jsonl',
        '_embedded/**/*',
      ],
    },
  },
  // Bandwidth controls. Pages use `revalidate = 600` (10 min ISR); these
  // headers add browser + CDN caching for static assets so repeat visits
  // don't re-fetch logos / favicons / JS bundles from origin.
  async headers() {
    return [
      {
        // Long-cache the fingerprinted JS / CSS bundles (Next.js hashes them)
        source: '/_next/static/:path*',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }],
      },
      {
        // Logos, images, fonts in /public
        source: '/:path((?:.+\\.(?:svg|png|jpg|jpeg|webp|ico|woff2|woff|ttf)))',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=2592000, immutable' }],
      },
    ];
  },
};

export default nextConfig;
