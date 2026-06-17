'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Decision, DecisionStatus } from '@/lib/types';

const STORAGE_KEY = 'lede.decisions.v1';

type DecisionMap = Record<string, Decision>; // key = `${story_url}||${newsletter}`

export function useDecisions() {
  const [decisions, setDecisions] = useState<DecisionMap>({});

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setDecisions(JSON.parse(raw));
    } catch {
      // ignore
    }
  }, []);

  const persist = useCallback((next: DecisionMap) => {
    setDecisions(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // ignore
    }
  }, []);

  const upsert = useCallback(
    (story_url: string, newsletter: string, patch: Partial<Decision>) => {
      const key = `${story_url}||${newsletter}`;
      setDecisions((prev) => {
        const existing = prev[key] ?? {
          story_url,
          newsletter,
          status: 'pending' as DecisionStatus,
          edited_blurb: undefined,
        };
        const merged: Decision = { ...existing, ...patch };
        const next = { ...prev, [key]: merged };
        try {
          window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        } catch {}
        return next;
      });
    },
    [],
  );

  const reset = useCallback((story_url: string, newsletter: string) => {
    const key = `${story_url}||${newsletter}`;
    setDecisions((prev) => {
      const next = { ...prev };
      delete next[key];
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  }, []);

  return { decisions, upsert, reset, persist };
}
