'use client';

import { useRef, useState } from 'react';
import { useDecisions } from './useDecisions';

/**
 * Tiny export/import widget for the curation decisions stored in
 * localStorage. Lets the user carry their approve/reject state across
 * browsers and machines without us needing a backend or auth.
 *
 * Lives in the Nav as a single ⇅ icon; click reveals a popover.
 */
export default function DecisionsSync() {
  const { decisions, persist } = useDecisions();
  const [open, setOpen] = useState(false);
  const [flash, setFlash] = useState<string>('');
  const fileRef = useRef<HTMLInputElement>(null);

  const count = Object.keys(decisions).length;

  function exportNow() {
    const blob = new Blob(
      [JSON.stringify({ exportedAt: new Date().toISOString(), decisions }, null, 2)],
      { type: 'application/json' },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lede-decisions-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setFlash(`Exported ${count} decisions`);
    setTimeout(() => setFlash(''), 2500);
  }

  function importNow() {
    fileRef.current?.click();
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const incoming =
        data && typeof data === 'object' && data.decisions ? data.decisions : data;
      if (!incoming || typeof incoming !== 'object') {
        setFlash('Invalid file - expected JSON map');
        setTimeout(() => setFlash(''), 3000);
        return;
      }
      // Merge incoming onto existing - keep both, incoming wins on key
      // collision (more recent edit assumed).
      const merged = { ...decisions, ...incoming };
      persist(merged);
      const added = Object.keys(incoming).length;
      setFlash(`Imported ${added} decisions (${Object.keys(merged).length} total)`);
      setTimeout(() => setFlash(''), 3000);
    } catch (err) {
      setFlash('Import failed - invalid JSON');
      setTimeout(() => setFlash(''), 3000);
    }
    if (fileRef.current) fileRef.current.value = '';
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-[12px] text-text-mute hover:text-text px-2 py-1 rounded border border-transparent hover:border-border"
        title="Sync your approve/reject decisions across devices"
      >
        ⇅ Sync
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-50 bg-surface border border-border-strong rounded-md shadow-lg py-2 px-3 min-w-[240px]">
            <div className="text-[11px] text-text-mute mb-2">
              {count} decision{count === 1 ? '' : 's'} stored on this device
            </div>
            <div className="flex flex-col gap-1.5">
              <button
                onClick={exportNow}
                className="text-left text-[12.5px] py-1.5 px-2 rounded hover:bg-surface-hi text-text"
              >
                ⬇ Export to .json
              </button>
              <button
                onClick={importNow}
                className="text-left text-[12.5px] py-1.5 px-2 rounded hover:bg-surface-hi text-text"
              >
                ⬆ Import from .json
              </button>
            </div>
            {flash && (
              <div className="text-[11px] text-ok mt-2 border-t border-border pt-2">{flash}</div>
            )}
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={onFile}
            />
          </div>
        </>
      )}
    </div>
  );
}
