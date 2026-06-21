'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import DecisionsSync from './DecisionsSync';

const TABS = [
  { href: '/', label: 'Curate' },
  { href: '/edition', label: 'Edition' },
  { href: '/funding', label: 'Funding' },
  { href: '/vc', label: 'VC' },
  { href: '/backtest', label: 'Backtest' },
];

export default function Nav({ pipelinePills }: { pipelinePills?: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex items-center gap-2 sm:gap-4 border-b border-border px-3 sm:px-5 py-2.5 overflow-x-auto scroll-y">
      <Link href="/" className="flex items-center shrink-0" aria-label="lede home">
        <Image
          src="/lede-logo-horizontal-reverse.svg"
          alt="lede"
          width={2400}
          height={785}
          priority
          className="h-5 w-auto"
        />
      </Link>
      <div className="flex items-center gap-1 ml-1 sm:ml-4 shrink-0">
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
                'px-2.5 sm:px-3 py-1.5 rounded-md text-[12.5px] sm:text-[13px] font-medium transition-colors whitespace-nowrap ' +
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
      <div className="ml-auto flex items-center gap-3 shrink-0">
        {pipelinePills}
        <DecisionsSync />
      </div>
    </div>
  );
}
