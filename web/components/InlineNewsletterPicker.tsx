'use client';

import { useRouter, useSearchParams } from 'next/navigation';

export default function InlineNewsletterPicker({
  ids,
  brandNames,
  value,
}: {
  ids: string[];
  brandNames: Record<string, string>;
  value: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(sp.toString());
    next.set('nl', e.target.value);
    router.push('?' + next.toString(), { scroll: false });
  }
  return (
    <label className="inline-flex items-center gap-2 text-[11px] text-text-mute uppercase tracking-[0.06em] font-semibold">
      <span>Newsletter</span>
      <select
        value={value}
        onChange={onChange}
        className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 outline-none normal-case font-normal tracking-normal"
      >
        {ids.map((id) => (
          <option key={id} value={id}>
            {brandNames[id] ?? id}
          </option>
        ))}
      </select>
    </label>
  );
}
