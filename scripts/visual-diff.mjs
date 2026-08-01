#!/usr/bin/env node
// Pixel diff for visual regression. Compares same-named PNGs in two directories.
//
//   node scripts/visual-diff.mjs <baselineDir> <currentDir> [--threshold 0.1] [--out DIR]
//
// Exit 0 = no shot exceeded the threshold. Exit 1 = at least one did.
// Prints one line per screenshot plus a JSON summary at the end.

import { readdir, mkdir, writeFile } from 'node:fs/promises';
import { join, basename } from 'node:path';
import sharp from 'sharp';

const args = process.argv.slice(2);
const positional = args.filter((a) => !a.startsWith('--'));
const flag = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? fallback : args[i + 1];
};

const [baselineDir, currentDir] = positional;
if (!baselineDir || !currentDir) {
  console.error('usage: node scripts/visual-diff.mjs <baselineDir> <currentDir> [--threshold 0.1] [--out DIR]');
  process.exit(2);
}

// Percent of pixels allowed to differ before a shot is flagged.
const threshold = Number(flag('threshold', '0.1'));
const outDir = flag('out', join(currentDir, '__diff__'));
// Per-channel delta below this is treated as identical — absorbs PNG encoder
// noise and sub-pixel antialiasing without hiding real changes.
const CHANNEL_TOLERANCE = 12;

const pngs = async (dir) =>
  (await readdir(dir).catch(() => [])).filter((f) => f.toLowerCase().endsWith('.png')).sort();

const baseFiles = await pngs(baselineDir);
const currFiles = await pngs(currentDir);

if (baseFiles.length === 0) {
  console.error(`no baseline PNGs in ${baselineDir} — capture a baseline first`);
  process.exit(2);
}

await mkdir(outDir, { recursive: true });

const results = [];
let failed = false;

for (const name of baseFiles) {
  if (!currFiles.includes(name)) {
    results.push({ name, status: 'missing-current' });
    failed = true;
    console.log(`MISSING  ${name}  (no matching screenshot in current run)`);
    continue;
  }

  const load = (dir) =>
    sharp(join(dir, name)).ensureAlpha().raw().toBuffer({ resolveWithObject: true });

  const [a, b] = await Promise.all([load(baselineDir), load(currentDir)]);

  if (a.info.width !== b.info.width || a.info.height !== b.info.height) {
    results.push({
      name,
      status: 'size-mismatch',
      baseline: `${a.info.width}x${a.info.height}`,
      current: `${b.info.width}x${b.info.height}`,
    });
    failed = true;
    console.log(
      `SIZE     ${name}  baseline ${a.info.width}x${a.info.height} vs current ${b.info.width}x${b.info.height}`,
    );
    continue;
  }

  const { width, height } = a.info;
  const total = width * height;
  const diffBuf = Buffer.alloc(total * 4);
  let changed = 0;
  // Bounding box of the changed region, so the report can say *where*.
  let minX = width, minY = height, maxX = -1, maxY = -1;

  for (let p = 0; p < total; p++) {
    const i = p * 4;
    const dr = Math.abs(a.data[i] - b.data[i]);
    const dg = Math.abs(a.data[i + 1] - b.data[i + 1]);
    const db = Math.abs(a.data[i + 2] - b.data[i + 2]);
    const isDiff = dr > CHANNEL_TOLERANCE || dg > CHANNEL_TOLERANCE || db > CHANNEL_TOLERANCE;

    if (isDiff) {
      changed++;
      const x = p % width;
      const y = (p / width) | 0;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      // Magenta over the changed pixel.
      diffBuf[i] = 255; diffBuf[i + 1] = 0; diffBuf[i + 2] = 255; diffBuf[i + 3] = 255;
    } else {
      // Dimmed grayscale of the current frame, so the diff reads in context.
      const gray = ((a.data[i] + a.data[i + 1] + a.data[i + 2]) / 3) * 0.35;
      diffBuf[i] = gray; diffBuf[i + 1] = gray; diffBuf[i + 2] = gray; diffBuf[i + 3] = 255;
    }
  }

  const pct = (changed / total) * 100;
  const over = pct > threshold;
  if (over) failed = true;

  const entry = {
    name,
    status: over ? 'changed' : 'ok',
    changedPercent: Number(pct.toFixed(4)),
    changedPixels: changed,
    dimensions: `${width}x${height}`,
  };

  if (over) {
    const diffPath = join(outDir, `diff-${basename(name)}`);
    await sharp(diffBuf, { raw: { width, height, channels: 4 } }).png().toFile(diffPath);
    entry.diffImage = diffPath;
    entry.region = { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 };
    console.log(
      `CHANGED  ${name}  ${pct.toFixed(3)}% of pixels  region ${entry.region.x},${entry.region.y} ` +
        `${entry.region.width}x${entry.region.height}  -> ${diffPath}`,
    );
  } else {
    console.log(`ok       ${name}  ${pct.toFixed(3)}%`);
  }

  results.push(entry);
}

for (const name of currFiles.filter((f) => !baseFiles.includes(f))) {
  results.push({ name, status: 'new' });
  console.log(`NEW      ${name}  (no baseline — capture one if this route is here to stay)`);
}

const summaryPath = join(outDir, 'summary.json');
await writeFile(summaryPath, JSON.stringify({ baselineDir, currentDir, threshold, results }, null, 2));

const changedCount = results.filter((r) => r.status !== 'ok').length;
console.log(`\n${changedCount} of ${results.length} shots need review. Summary: ${summaryPath}`);
process.exit(failed ? 1 : 0);
