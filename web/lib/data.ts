import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import type {
  Blurb,
  Newsletter,
  ScoredStory,
  BacktestResult,
  Section,
  FundingRound,
} from './types';

// Data location: prefer ./_embedded (created by scripts/embed.mjs for CLI
// deploys), then ../ (local dev + GitHub-integration deploy where the whole
// repo is checked out).
function findRoot(): string {
  const candidates = [
    path.resolve(process.cwd(), '_embedded'),
    path.resolve(process.cwd(), '..'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, 'config', 'newsletters.yaml'))) return c;
  }
  return candidates[1];
}
const REPO_ROOT = findRoot();

const SCORED_DIR = path.join(REPO_ROOT, 'data', 'scored');
const BLURBS_DIR = path.join(REPO_ROOT, 'data', 'blurbs');
const BACKTEST_DIR = path.join(REPO_ROOT, 'data', 'backtest');
const FUNDING_DIR = path.join(REPO_ROOT, 'data', 'funding');
const NEWSLETTERS_PATH = path.join(REPO_ROOT, 'config', 'newsletters.yaml');

/** All scrape file dates we have scored or blurb data for, newest first. */
export function listAvailableDates(): string[] {
  const dates = new Set<string>();
  for (const dir of [SCORED_DIR, BLURBS_DIR]) {
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) {
      if (f.endsWith('.jsonl')) dates.add(f.replace('.jsonl', ''));
    }
  }
  return Array.from(dates).sort().reverse();
}

/**
 * All UTC publish dates that appear across loaded scored data, newest first.
 * Used to power the "Filter by date" dropdown — picks the day a story was
 * published, not the day the scraper happened to fetch it.
 */
export function listPublishedDates(): string[] {
  const scrapeDates = listAvailableDates();
  const dates = new Set<string>();
  for (const d of scrapeDates) {
    for (const s of loadScored(d)) {
      const pub = s.story?.published_at;
      if (typeof pub === 'string' && pub.length >= 10) {
        dates.add(pub.slice(0, 10));
      }
    }
  }
  return Array.from(dates).sort().reverse();
}

/** Keep only stories whose UTC publish date matches `date`. */
export function filterByPublishedDate<T extends { story: { published_at?: string } }>(
  items: T[],
  date: string,
): T[] {
  return items.filter(
    (s) =>
      typeof s.story?.published_at === 'string' &&
      s.story.published_at.slice(0, 10) === date,
  );
}

/** Keep only blurbs whose story_url is in `urls`. */
export function filterBlurbsByStoryUrls<T extends { story_url: string }>(
  blurbs: T[],
  urls: Set<string>,
): T[] {
  return blurbs.filter((b) => urls.has(b.story_url));
}

function readJsonl<T>(filePath: string): T[] {
  if (!fs.existsSync(filePath)) return [];
  const text = fs.readFileSync(filePath, 'utf-8');
  const out: T[] = [];
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    try {
      out.push(JSON.parse(t) as T);
    } catch {
      // skip malformed lines
    }
  }
  return out;
}

export function loadScored(date: string): ScoredStory[] {
  return readJsonl<ScoredStory>(path.join(SCORED_DIR, `${date}.jsonl`));
}

export function loadBlurbs(date: string): Blurb[] {
  return readJsonl<Blurb>(path.join(BLURBS_DIR, `${date}.jsonl`));
}

/** Load every day's scored data, deduplicated by URL (best score wins). */
export function loadScoredAll(dates: string[]): ScoredStory[] {
  const byUrl = new Map<string, ScoredStory>();
  for (const d of dates) {
    for (const ss of loadScored(d)) {
      const existing = byUrl.get(ss.story.url);
      if (!existing || ss.score > existing.score) byUrl.set(ss.story.url, ss);
    }
  }
  return Array.from(byUrl.values());
}

export function loadBlurbsAll(dates: string[]): Blurb[] {
  const byKey = new Map<string, Blurb>();
  for (const d of dates) {
    for (const b of loadBlurbs(d)) {
      const key = `${b.story_url}||${b.newsletter}`;
      if (!byKey.has(key)) byKey.set(key, b);
    }
  }
  return Array.from(byKey.values());
}

/** Index blurbs by (story_url, newsletter) for fast lookup. */
export function indexBlurbs(blurbs: Blurb[]): Map<string, Blurb> {
  const m = new Map<string, Blurb>();
  for (const b of blurbs) m.set(`${b.story_url}||${b.newsletter}`, b);
  return m;
}

let _newslettersCache: { id: string; data: Record<string, Newsletter>; ts: number } | null = null;

export function loadNewsletters(): Record<string, Newsletter> {
  // Lightweight 1-second cache so a single page render doesn't re-parse the YAML
  if (_newslettersCache && Date.now() - _newslettersCache.ts < 1000) return _newslettersCache.data;
  if (!fs.existsSync(NEWSLETTERS_PATH)) return {};
  const parsed = yaml.load(fs.readFileSync(NEWSLETTERS_PATH, 'utf-8')) as Record<string, any>;
  const out: Record<string, Newsletter> = {};
  for (const [id, raw] of Object.entries(parsed)) {
    if (id === 'default' || typeof raw !== 'object' || raw === null) continue;
    const r = raw as any;
    const sections: Section[] = (r.sections || []).map((s: any) => ({
      id: s.id,
      name: s.name,
      emoji: s.emoji,
      min_words: Number(s.min_words),
      max_words: Number(s.max_words),
      target_count: Number(s.target_count),
      description: String(s.description ?? '').trim(),
    }));
    out[id] = {
      id,
      brand_name: r.brand_name,
      voice_skill: r.voice_skill,
      sections,
      topics: r.topics ?? [],
      edition_size: Number(r.edition_size ?? 12),
    };
  }
  _newslettersCache = { id: 'snapshot', data: out, ts: Date.now() };
  return out;
}

export function defaultNewsletterId(): string {
  if (!fs.existsSync(NEWSLETTERS_PATH)) return 'tldr_tech';
  const parsed = yaml.load(fs.readFileSync(NEWSLETTERS_PATH, 'utf-8')) as any;
  return parsed?.default ?? 'tldr_tech';
}

/** Return stories per section for one newsletter, sorted by per-newsletter score, capped at target_count. */
export function topPerSection(
  scored: ScoredStory[],
  newsletterId: string,
  newsletters: Record<string, Newsletter>,
): Record<string, ScoredStory[]> {
  const nl = newsletters[newsletterId];
  if (!nl) return {};
  const groups: Record<string, ScoredStory[]> = {};
  for (const sec of nl.sections) groups[sec.id] = [];
  for (const s of scored) {
    const a = s.assignments.find((a) => a.newsletter === newsletterId);
    if (!a) continue;
    if (groups[a.section_id]) groups[a.section_id].push(s);
  }
  for (const sec of nl.sections) {
    groups[sec.id].sort((a, b) => {
      const sa = a.assignments.find((x) => x.newsletter === newsletterId)?.score ?? 0;
      const sb = b.assignments.find((x) => x.newsletter === newsletterId)?.score ?? 0;
      return sb - sa;
    });
    groups[sec.id] = groups[sec.id].slice(0, sec.target_count);
  }
  return groups;
}

/** Available backtest dates (latest first). */
export function listBacktestDates(): string[] {
  if (!fs.existsSync(BACKTEST_DIR)) return [];
  const dates = new Set<string>();
  for (const f of fs.readdirSync(BACKTEST_DIR)) {
    if (f.endsWith('.json') && f.length >= 14) dates.add(f.slice(0, 10));
  }
  return Array.from(dates).sort().reverse();
}

export function loadBacktest(newsletterId: string, date: string): BacktestResult | null {
  const file = path.join(BACKTEST_DIR, `${date}-${newsletterId}.json`);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8')) as BacktestResult;
  } catch {
    return null;
  }
}

/** All dates that have a funding JSONL, newest first. */
export function listFundingDates(): string[] {
  if (!fs.existsSync(FUNDING_DIR)) return [];
  const dates = new Set<string>();
  for (const f of fs.readdirSync(FUNDING_DIR)) {
    if (f.endsWith('.jsonl')) dates.add(f.replace('.jsonl', ''));
  }
  return Array.from(dates).sort().reverse();
}

export function loadFunding(date: string): FundingRound[] {
  return readJsonl<FundingRound>(path.join(FUNDING_DIR, `${date}.jsonl`));
}

/** Load every day's funding data, deduplicated by story_url (latest wins). */
export function loadFundingAll(dates: string[]): FundingRound[] {
  const byUrl = new Map<string, FundingRound>();
  for (const d of dates) {
    for (const r of loadFunding(d)) {
      byUrl.set(r.story_url, r);
    }
  }
  return Array.from(byUrl.values());
}

/** Load funding rounds whose scrape date falls in [from, to] inclusive. */
export function loadFundingRange(from: string, to: string): FundingRound[] {
  const dates = listFundingDates().filter((d) => d >= from && d <= to);
  return loadFundingAll(dates);
}

export function loadBacktestsForNewsletter(newsletterId: string, lastNDays = 7): BacktestResult[] {
  const out: BacktestResult[] = [];
  const dates = listBacktestDates().slice(0, lastNDays);
  for (const d of dates) {
    const r = loadBacktest(newsletterId, d);
    if (r) out.push(r);
  }
  return out;
}
