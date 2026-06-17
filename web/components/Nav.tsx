'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/', label: 'Curate' },
  { href: '/edition', label: 'Edition' },
  { href: '/backtest', label: 'Backtest' },
];

export default function Nav({ pipelinePills }: { pipelinePills?: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex items-center gap-4 border-b border-border px-5 py-2.5">
      <div className="flex items-center gap-3">
        <h1 className="text-[14px] font-semibold tracking-tight">lede</h1>
        <span className="text-[11px] text-text-mute">TLDR curation pipeline</span>
      </div>
      <div className="flex items-center gap-1 ml-4">
        {TABS.map((t) => {
          const active =
            t.href === '/'
              ? pathname === '/' || pathname === ''
              : pathname.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={
                'px-3 py-1.5 rounded-md text-[13px] font-medium transition-colors ' +
                (active
                  ? 'bg-accent-soft text-text border border-accent'
                  : 'text-text-dim hover:bg-surface hover:text-text border border-transparent')
              }
            >
              {t.label}
            </Link>
          );
        })}
      </div>
      <div className="ml-auto">{pipelinePills}</div>
    </div>
  );
}
