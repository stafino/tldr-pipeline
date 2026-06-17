import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0a',
        surface: '#171717',
        'surface-hi': '#1f1f1f',
        border: '#2a2a2a',
        'border-strong': '#404040',
        text: '#fafafa',
        'text-dim': '#a3a3a3',
        'text-mute': '#737373',
        accent: '#3b82f6',
        'accent-soft': '#1e3a8a',
        ok: '#10b981',
        'ok-soft': '#064e3b',
        warn: '#f59e0b',
        'warn-soft': '#78350f',
        no: '#ef4444',
        'no-soft': '#7f1d1d',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
export default config;
