/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow reading data files from the repo root at runtime
  outputFileTracingIncludes: {
    '/': [
      '../config/**/*',
      '../data/scored/*.jsonl',
      '../data/blurbs/*.jsonl',
      '../data/backtest/*.json',
    ],
  },
  experimental: {
    // tighten payloads
  },
};

export default nextConfig;
