#!/usr/bin/env node
// Copy the parent repo's data/ and config/ into web/_embedded/ so that
// `vercel` CLI uploads them with the deploy bundle (the CLI only uploads
// the project directory; parent paths are unreachable on Vercel's build
// container without this step).

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const WEB_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const EMBED = path.join(WEB_ROOT, '_embedded');

const COPY = [
  ['config/newsletters.yaml', 'config/newsletters.yaml'],
  ['data/scored', 'data/scored', /\.jsonl$/],
  ['data/blurbs', 'data/blurbs', /\.jsonl$/],
  ['data/backtest', 'data/backtest', /\.json$/],
  ['data/funding', 'data/funding', /\.jsonl$/],
];

function copyFile(src, dst) {
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

function copyDir(srcDir, dstDir, pattern) {
  if (!fs.existsSync(srcDir)) return 0;
  fs.mkdirSync(dstDir, { recursive: true });
  let n = 0;
  for (const f of fs.readdirSync(srcDir)) {
    if (pattern && !pattern.test(f)) continue;
    copyFile(path.join(srcDir, f), path.join(dstDir, f));
    n++;
  }
  return n;
}

if (fs.existsSync(EMBED)) fs.rmSync(EMBED, { recursive: true });

let total = 0;
for (const [src, dst, pattern] of COPY) {
  const fullSrc = path.join(REPO_ROOT, src);
  const fullDst = path.join(EMBED, dst);
  if (pattern) {
    const n = copyDir(fullSrc, fullDst, pattern);
    console.log(`  ${src} → _embedded/${dst} (${n} files)`);
    total += n;
  } else if (fs.existsSync(fullSrc)) {
    copyFile(fullSrc, fullDst);
    console.log(`  ${src} → _embedded/${dst}`);
    total += 1;
  } else {
    console.warn(`  ! missing: ${src}`);
  }
}
console.log(`embedded ${total} files into ${EMBED}`);
