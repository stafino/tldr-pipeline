'use client';

import { useRouter, useSearchParams } from 'next/navigation';

export default function NewsletterPicker({
  ids,
  brandNames,
  value,
  paramKey = 'nl',
  includeBacklog = false,
}: {
  ids: string[];
  brandNames: Record<string, string>;
  value: string;
  paramKey?: string;
  includeBacklog?: boolean;
}) {
  const router = useRouter();
  const sp = useSearchParams();

  function go(v: string) {
    const next = new URLSearchParams(sp.toString());
    next.set(paramKey, v);
    next.delete('story'); // clear selected story when switching newsletter
    router.push('?' + next.toString());
  }

  return (
    <div className="px-1">
      {includeBacklog && (
        <div className="text-[10px] uppercase tracking-[0.1em] text-text-mute mt-2 mb-1.5">Queue</div>
      )}
      {includeBacklog && (
        <button
          onClick={() => go('__backlog__')}
          className={
            'w-full text-left flex justify-between items-baseline px-2.5 py-1.5 rounded text-[13px] transition-colors mb-0.5 ' +
            (value === '__backlog__'
              ? 'bg-accent-soft text-text font-semibold'
              : 'text-text-dim hover:bg-surface hover:text-text')
          }
        >
          <span>
            <span className="text-amber-400 mr-1">★</span>Backlog
          </span>
        </button>
      )}
      <div className="text-[10px] uppercase tracking-[0.1em] text-text-mute mt-3 mb-1.5">Newsletters</div>
      {ids.map((id) => (
        <button
          key={id}
          onClick={() => go(id)}
          className={
            'w-full text-left px-2.5 py-1.5 rounded text-[13px] transition-colors mb-0.5 ' +
            (value === id
              ? 'bg-accent-soft text-text font-semibold border border-accent'
              : 'text-text-dim hover:bg-surface hover:text-text border border-transparent')
          }
        >
          {brandNames[id]?.replace('TLDR ', '').replace('TLDR', 'Main') ?? id}
        </button>
      ))}
    </div>
  );
}
