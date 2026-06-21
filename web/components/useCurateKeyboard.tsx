'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useDecisions } from './useDecisions';

/**
 * Keyboard nav for the Curate tab.
 *   j / ↓ - next story
 *   k / ↑ - previous story
 *   a     - approve current story
 *   r     - reject current story
 *   u     - undo (reset decision)
 *   o     - open source URL in new tab
 *   ?     - show shortcut help overlay
 *   Esc   - clear selection / close help
 *
 * No-ops when an input/textarea is focused so blurb editing isn't broken.
 */
export default function useCurateKeyboard({
  orderedUrls,
  selectedUrl,
  newsletterId,
  hrefForUrl,
  openUrlForSelected,
}: {
  orderedUrls: string[];
  selectedUrl?: string;
  newsletterId: string;
  hrefForUrl: (url: string) => string;
  openUrlForSelected?: string;
}): { showHelp: boolean; closeHelp: () => void } {
  const router = useRouter();
  const sp = useSearchParams();
  const { upsert, reset } = useDecisions();
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    function isEditable(el: EventTarget | null): boolean {
      if (!(el instanceof HTMLElement)) return false;
      const tag = el.tagName;
      return (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        el.isContentEditable
      );
    }

    function onKey(e: KeyboardEvent) {
      // Allow Escape even inside inputs (universal "close" affordance).
      if (e.key === 'Escape') {
        if (showHelp) {
          setShowHelp(false);
          return;
        }
        if (isEditable(e.target)) return;
        if (selectedUrl) {
          const next = new URLSearchParams(sp.toString());
          next.delete('story');
          next.delete('nl_detail');
          router.push('?' + next.toString(), { scroll: false });
        }
        return;
      }

      if (isEditable(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const idx = selectedUrl ? orderedUrls.indexOf(selectedUrl) : -1;

      function go(nextIdx: number) {
        if (nextIdx < 0 || nextIdx >= orderedUrls.length) return;
        router.push(hrefForUrl(orderedUrls[nextIdx]), { scroll: false });
      }

      switch (e.key) {
        case 'j':
        case 'ArrowDown':
          e.preventDefault();
          go(idx < 0 ? 0 : idx + 1);
          return;
        case 'k':
        case 'ArrowUp':
          e.preventDefault();
          go(idx < 0 ? 0 : idx - 1);
          return;
        case 'a':
          if (selectedUrl) {
            e.preventDefault();
            upsert(selectedUrl, newsletterId, { status: 'approved' });
          }
          return;
        case 'r':
          if (selectedUrl) {
            e.preventDefault();
            upsert(selectedUrl, newsletterId, { status: 'rejected' });
          }
          return;
        case 'u':
          if (selectedUrl) {
            e.preventDefault();
            reset(selectedUrl, newsletterId);
          }
          return;
        case 'o':
          if (openUrlForSelected) {
            e.preventDefault();
            window.open(openUrlForSelected, '_blank', 'noopener');
          }
          return;
        case '?':
        case '/':
          e.preventDefault();
          setShowHelp((v) => !v);
          return;
      }
    }

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [
    orderedUrls,
    selectedUrl,
    newsletterId,
    hrefForUrl,
    openUrlForSelected,
    router,
    sp,
    upsert,
    reset,
    showHelp,
  ]);

  return { showHelp, closeHelp: () => setShowHelp(false) };
}
