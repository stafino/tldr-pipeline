'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

/**
 * Debounced URL-backed search input. The filter is applied server-side via
 * ?q= so it survives reloads and is shareable, but typing doesn't push a
 * URL change every keystroke (300ms debounce keeps the back-stack clean).
 */
export default function SearchFilter({ value, placeholder = 'Filter…' }: { value: string; placeholder?: string }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [local, setLocal] = useState(value);

  useEffect(() => setLocal(value), [value]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (local === value) return;
      const next = new URLSearchParams(sp.toString());
      if (local) next.set('q', local);
      else next.delete('q');
      router.push('?' + next.toString(), { scroll: false });
    }, 300);
    return () => clearTimeout(t);
  }, [local, value, sp, router]);

  return (
    <label className="inline-flex items-center gap-2 text-[11px] text-text-mute uppercase tracking-[0.06em] font-semibold">
      <span>Search</span>
      <input
        type="search"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder}
        className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 outline-none focus:border-accent normal-case font-normal tracking-normal w-[180px]"
      />
      {local && (
        <button
          type="button"
          onClick={() => setLocal('')}
          className="text-text-mute hover:text-text text-[14px] normal-case font-normal -ml-1"
          title="Clear search"
        >
          ×
        </button>
      )}
    </label>
  );
}
