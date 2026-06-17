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
        '_embedded/**/*',
      ],
    },
  },
};

export default nextConfig;
