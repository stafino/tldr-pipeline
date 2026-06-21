/**
 * Firm + people name canonicalization for the VC tab.
 *
 * Why: the LLM extracts whatever string appears in the article, so
 * "Tiger Global Management" and "Tiger" and "Tiger Global" all end up
 * as separate entries. This kills leaderboard accuracy.
 *
 * Simple lookup-table approach - explicit > clever. Each entry maps
 * any variant to a single canonical name. Unknown firms pass through
 * untouched.
 */

const FIRM_ALIASES: Record<string, string> = {
  // Top-tier US
  'andreessen horowitz': 'a16z',
  'andreessen': 'a16z',
  'a16z crypto': 'a16z',
  'sequoia capital': 'Sequoia',
  'sequoia': 'Sequoia',
  'kleiner perkins': 'Kleiner Perkins',
  'kpcb': 'Kleiner Perkins',
  'kleiner': 'Kleiner Perkins',
  'tiger global management': 'Tiger Global',
  'tiger global': 'Tiger Global',
  'tiger': 'Tiger Global',
  'general catalyst partners': 'General Catalyst',
  'general catalyst': 'General Catalyst',
  'gc': 'General Catalyst',
  'lightspeed venture partners': 'Lightspeed',
  'lightspeed': 'Lightspeed',
  'accel partners': 'Accel',
  'accel': 'Accel',
  'bessemer venture partners': 'Bessemer',
  'bessemer': 'Bessemer',
  'index ventures': 'Index Ventures',
  'index': 'Index Ventures',
  'first round capital': 'First Round',
  'first round': 'First Round',
  'founders fund': 'Founders Fund',
  'greylock partners': 'Greylock',
  'greylock': 'Greylock',
  'benchmark capital': 'Benchmark',
  'benchmark': 'Benchmark',
  'insight partners': 'Insight Partners',
  'insight venture partners': 'Insight Partners',
  'insight': 'Insight Partners',
  'coatue management': 'Coatue',
  'coatue': 'Coatue',
  'khosla ventures': 'Khosla Ventures',
  'khosla': 'Khosla Ventures',
  'gv': 'GV',
  'google ventures': 'GV',
  'thrive capital': 'Thrive Capital',
  'nea': 'NEA',
  'new enterprise associates': 'NEA',
  // EU
  'atomico partners': 'Atomico',
  'atomico': 'Atomico',
  'index ventures europe': 'Index Ventures',
  'balderton capital': 'Balderton',
  'balderton': 'Balderton',
  'northzone ventures': 'Northzone',
  'northzone': 'Northzone',
  'creandum': 'Creandum',
  // Asia/Growth
  'softbank vision fund': 'SoftBank Vision Fund',
  'softbank': 'SoftBank',
  'jio platforms': 'Jio Platforms',
  // Common YC variants
  'y combinator': 'Y Combinator',
  'ycombinator': 'Y Combinator',
  'yc': 'Y Combinator',
};

const PEOPLE_ALIASES: Record<string, string> = {
  'marc andreessen': 'Marc Andreessen',
  'pmarca': 'Marc Andreessen',
  'andreessen marc': 'Marc Andreessen',
  'ben horowitz': 'Ben Horowitz',
  'paul graham': 'Paul Graham',
  'pg': 'Paul Graham',
  'sam altman': 'Sam Altman',
  'altman sam': 'Sam Altman',
  'satya nadella': 'Satya Nadella',
  'elon musk': 'Elon Musk',
  'noam shazeer': 'Noam Shazeer',
  'john jumper': 'John Jumper',
  'andre cronje': 'Andre Cronje',
};

function normalize(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

export function canonFirm(raw: string): string {
  if (!raw) return raw;
  return FIRM_ALIASES[normalize(raw)] ?? raw.trim();
}

export function canonPerson(raw: string): string {
  if (!raw) return raw;
  return PEOPLE_ALIASES[normalize(raw)] ?? raw.trim();
}

export function dedupCanon(items: string[], canon: (s: string) => string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of items) {
    const c = canon(item);
    if (!c) continue;
    const key = c.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}
