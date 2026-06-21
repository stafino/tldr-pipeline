'use client';

import { useCallback, useSyncExternalStore } from 'react';
import type { Decision, DecisionStatus } from '@/lib/types';

const STORAGE_KEY = 'lede.decisions.v1';

type DecisionMap = Record<string, Decision>; // key = `${story_url}||${newsletter}`

// Module-level cache so every useDecisions() instance reads from one source.
// Without this, DetailPane's upsert would only update DetailPane's local state
// - CurateNewsletterView, NewsletterPicker, etc. would stay stale until they
// re-mount.
let cache: DecisionMap = {};
let loaded = false;
const listeners = new Set<() => void>();
const EMPTY: DecisionMap = {};

function loadCache(): DecisionMap {
  if (loaded) return cache;
  if (typeof window === 'undefined') return EMPTY;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    cache = raw ? JSON.parse(raw) : {};
  } catch {
    cache = {};
  }
  loaded = true;
  return cache;
}

function commit(next: DecisionMap) {
  cache = next;
  loaded = true;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {}
  for (const cb of listeners) cb();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  // Also react to cross-tab updates: other tabs writing the same key.
  function onStorage(e: StorageEvent) {
    if (e.key !== STORAGE_KEY) return;
    loaded = false;
    loadCache();
    cb();
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', onStorage);
  }
  return () => {
    listeners.delete(cb);
    if (typeof window !== 'undefined') {
      window.removeEventListener('storage', onStorage);
    }
  };
}

function getSnapshot(): DecisionMap {
  return loadCache();
}

function getServerSnapshot(): DecisionMap {
  return EMPTY;
}

export function useDecisions() {
  const decisions = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const upsert = useCallback(
    (story_url: string, newsletter: string, patch: Partial<Decision>) => {
      const key = `${story_url}||${newsletter}`;
      const current = loadCache();
      const existing = current[key] ?? {
        story_url,
        newsletter,
        status: 'pending' as DecisionStatus,
        edited_blurb: undefined,
      };
      const merged: Decision = { ...existing, ...patch };
      commit({ ...current, [key]: merged });
    },
    [],
  );

  const reset = useCallback((story_url: string, newsletter: string) => {
    const key = `${story_url}||${newsletter}`;
    const current = loadCache();
    const next = { ...current };
    delete next[key];
    commit(next);
  }, []);

  const persist = useCallback((next: DecisionMap) => {
    commit(next);
  }, []);

  return { decisions, upsert, reset, persist };
}
