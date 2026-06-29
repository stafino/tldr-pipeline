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
  VcArticle,
} from './types';
import { classifyFundingStage } from './formatters';

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
const VC_DIR = path.join(REPO_ROOT, 'data', 'vc');
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
 * Used to power the "Filter by date" dropdown - picks the day a story was
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

/**
 * Sliding-window date filter: keeps stories whose UTC publish date is in
 * the inclusive [date - daysBack, date] window. Matches how a morning
 * newsletter actually reads - Tuesday's edition covers Monday-afternoon
 * through Tuesday-morning stories, not just Tuesday-published ones.
 *
 * Default daysBack = 1 (= today + yesterday).
 */
export function filterByPublishedWindow<T extends { story: { published_at?: string } }>(
  items: T[],
  date: string,
  daysBack: number = 1,
): T[] {
  const end = new Date(date + 'T00:00:00Z');
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - daysBack);
  const startIso = start.toISOString().slice(0, 10);
  return items.filter((s) => {
    const pub = s.story?.published_at;
    if (typeof pub !== 'string') return false;
    const d = pub.slice(0, 10);
    return d >= startIso && d <= date;
  });
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

function loadScored(date: string): ScoredStory[] {
  return readJsonl<ScoredStory>(path.join(SCORED_DIR, `${date}.jsonl`));
}

function loadBlurbs(date: string): Blurb[] {
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

/** Scrape dates with a funding JSONL (file-system names, newest first). */
function listScrapeDates(): string[] {
  if (!fs.existsSync(FUNDING_DIR)) return [];
  const dates = new Set<string>();
  for (const f of fs.readdirSync(FUNDING_DIR)) {
    if (f.endsWith('.jsonl')) dates.add(f.replace('.jsonl', ''));
  }
  return Array.from(dates).sort().reverse();
}

function normCompany(r: FundingRound): string {
  return (r.company || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

function stageOf(r: FundingRound): string {
  return classifyFundingStage(r.round_label).short.toLowerCase();
}

/** Round to 2 significant figures so $535M and $540M bucket together. */
function amountBucket(usd: number): number {
  if (!usd) return 0;
  const mag = Math.pow(10, Math.floor(Math.log10(Math.abs(usd))) - 1);
  return Math.round(usd / mag) * mag;
}

/** True when two company names are identical or one's tokens are a leading
 *  prefix of the other's (e.g. "stark" vs "stark defence"). */
function companyPrefixCompatible(a: string, b: string): boolean {
  if (!a || !b) return false;
  const ta = a.split(' ');
  const tb = b.split(' ');
  const n = Math.min(ta.length, tb.length);
  for (let i = 0; i < n; i++) if (ta[i] !== tb[i]) return false;
  return true;
}

/** Blank stage is a wildcard; two known stages must match. */
function stageCompatible(a: string, b: string): boolean {
  return a === b || a === '' || b === '';
}

/** Canonical survivor of two same-round rows: prefer a known stage, then the
 *  shorter (core) company name, then the earliest raise. */
function chooseRep(a: FundingRound, b: FundingRound): FundingRound {
  const sa = stageOf(a);
  const sb = stageOf(b);
  if (!!sa !== !!sb) return sa ? a : b;
  const la = normCompany(a).length;
  const lb = normCompany(b).length;
  if (la !== lb) return la < lb ? a : b;
  return a.raised_date <= b.raised_date ? a : b;
}

/**
 * Load every funding row across every scrape file, deduplicated first by
 * story_url, then by round (same company + stage). The second pass collapses
 * the same raise covered by different sources on different days - e.g. Alan's
 * Series G reported by Sifted and tech.eu a day apart. Keeps the earliest
 * raised_date (the original announcement); later re-coverage is dropped.
 *
 * Stage is taken from the classified round label. When one source omits the
 * stage, its blank stage is treated as a wildcard and folds into the company's
 * single known stage (e.g. Nearfield "" + Nearfield "Series D" -> one round).
 * Companies with two or more distinct known stages keep blank-stage rows
 * separate, since we can't tell which round they belong to.
 */
function loadAllRows(): FundingRound[] {
  const byUrl = new Map<string, FundingRound>();
  for (const d of listScrapeDates()) {
    const file = path.join(FUNDING_DIR, `${d}.jsonl`);
    for (const r of readJsonl<FundingRound>(file)) {
      // Backwards-compat for rows written before raised_date existed.
      const fixed: FundingRound = {
        ...r,
        raised_date: r.raised_date || (r.published_at?.slice(0, 10) ?? d),
      };
      byUrl.set(fixed.story_url, fixed);
    }
  }

  // Per company, the set of distinct non-blank stages seen. Used to resolve a
  // blank-stage row to the one known stage when there's exactly one.
  const knownStages = new Map<string, Set<string>>();
  for (const r of byUrl.values()) {
    const company = normCompany(r);
    const stage = stageOf(r);
    if (!company || !stage) continue;
    let set = knownStages.get(company);
    if (!set) knownStages.set(company, (set = new Set()));
    set.add(stage);
  }

  const byRound = new Map<string, FundingRound>();
  const anonymous: FundingRound[] = [];
  for (const r of byUrl.values()) {
    const company = normCompany(r);
    if (!company) {
      anonymous.push(r); // unknown company: never collapse into another
      continue;
    }
    let stage = stageOf(r);
    if (!stage) {
      const known = knownStages.get(company);
      if (known && known.size === 1) stage = [...known][0];
    }
    const key = `${company}::${stage}`;
    const existing = byRound.get(key);
    if (!existing || r.raised_date < existing.raised_date) byRound.set(key, r);
  }

  // Pass 3: fuzzy-merge survivors that are the same raise under a different
  // company spelling - same region, same amount (to 2 sig figs), compatible
  // stage, and one company name a token-prefix of the other ("Stark" vs
  // "Stark Defence"). Conservative: requires BOTH the amount match AND the
  // name-prefix relationship, so genuinely distinct companies never collapse.
  const groups = new Map<string, FundingRound[]>();
  const unbucketed: FundingRound[] = []; // no amount → can't fuzzy-match safely
  for (const r of byRound.values()) {
    if (r.amount_usd == null) {
      unbucketed.push(r);
      continue;
    }
    const gk = `${r.region}::${amountBucket(r.amount_usd)}`;
    let g = groups.get(gk);
    if (!g) groups.set(gk, (g = []));
    g.push(r);
  }
  const merged: FundingRound[] = [...unbucketed];
  for (const group of groups.values()) {
    const used = new Array(group.length).fill(false);
    for (let i = 0; i < group.length; i++) {
      if (used[i]) continue;
      let rep = group[i];
      used[i] = true;
      for (let j = i + 1; j < group.length; j++) {
        if (used[j]) continue;
        if (
          companyPrefixCompatible(normCompany(rep), normCompany(group[j])) &&
          stageCompatible(stageOf(rep), stageOf(group[j]))
        ) {
          used[j] = true;
          rep = chooseRep(rep, group[j]);
        }
      }
      merged.push(rep);
    }
  }
  return [...merged, ...anonymous];
}

/** Distinct raised_dates across every stored round, newest first. */
export function listFundingDates(): string[] {
  const out = new Set<string>();
  for (const r of loadAllRows()) out.add(r.raised_date);
  return Array.from(out).sort().reverse();
}

/** Load funding rounds whose raised_date falls in [from, to] inclusive. */
export function loadFundingRange(from: string, to: string): FundingRound[] {
  return loadAllRows().filter((r) => r.raised_date >= from && r.raised_date <= to);
}

/* ─── VC tab ────────────────────────────────────────────────────────────── */

function listVcDates(): string[] {
  if (!fs.existsSync(VC_DIR)) return [];
  const dates = new Set<string>();
  for (const f of fs.readdirSync(VC_DIR)) {
    if (f.endsWith('.jsonl')) dates.add(f.replace('.jsonl', ''));
  }
  return Array.from(dates).sort().reverse();
}

function loadVcRows(): VcArticle[] {
  const byUrl = new Map<string, VcArticle>();
  for (const d of listVcDates()) {
    for (const r of readJsonl<VcArticle>(path.join(VC_DIR, `${d}.jsonl`))) {
      byUrl.set(r.story_url, r);
    }
  }
  return Array.from(byUrl.values());
}

export { listVcDates };

export function loadVcRange(from: string, to: string): VcArticle[] {
  return loadVcRows().filter((r) => {
    const d = (r.published_at || '').slice(0, 10);
    return d >= from && d <= to;
  });
}

