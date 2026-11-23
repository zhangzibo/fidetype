#!/usr/bin/env node
// Public-wording check for the user-facing Markdown pages and tutorial scripts.
//
//   node tools/hygiene/wording.js            report every internal id found in the public pages
//   node tools/hygiene/wording.js --ci       the same, but exit 1 if there is a finding (CI job "hygiene")
//   node tools/hygiene/wording.js --count    one line per file with the number of findings
//   node tools/hygiene/wording.js FILE...    check only these files
//
// Public pages must not show internal project-management ids. Those ids belong in the internal
// records (wiki/, experiments/, HANDOFF.md). A public page may link to a record ("Details: ...").
// Forbidden: roadmap task codes (P5-37), gap numbers ("gap 98"), calibration-run ids (tcfg-...),
// and "user decision" text. Not checked: design records, maintainer pages, docs/archive/ and
// CHANGELOG.md (they are records by nature). Text inside links is checked; link targets are not
// (a "Details:" link may point to a record whose file name has a code). No dependencies.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');

// Pages that are records or maintainer pages. They carry a first-line label instead.
const EXEMPT = new Set([
  'docs/hub-design.md',
  'docs/safe-wpm-v0.2-proposal.md',
  'docs/publishing-checklist.md',
  'docs/RELEASING.md',
]);
const EXTRA = ['README.md', 'benchmark/README.md', 'spec/README.md',
  'sdk/typescript/README.md', 'sdk/rust/README.md'];

const RULES = [
  [/\bP\d{1,2}-\d+[a-z]?\b/g, 'roadmap task code'],
  [/\bgaps? \d+/gi, 'gap number'],
  [/\btcfg-[0-9a-f]{6,}/g, 'calibration-run id'],
  [/\buser decisions?\b/gi, '"user decision" text'],
];

function defaultFiles() {
  const docs = fs.readdirSync(path.join(ROOT, 'docs'))
    .filter((f) => f.endsWith('.md')).map((f) => 'docs/' + f)
    .filter((f) => !EXEMPT.has(f));
  const tut = fs.readdirSync(path.join(ROOT, 'tutorials'))
    .filter((f) => /^\d\d_.*\.py$/.test(f)).map((f) => 'tutorials/' + f);
  return [...EXTRA, ...docs, ...tut].filter((f) => fs.existsSync(path.join(ROOT, f)));
}

// Remove markdown link targets "](...)" so that file names of linked records do not count.
function stripTargets(line) {
  return line.replace(/\]\([^)]*\)/g, ']()').replace(/<a [^>]*href="[^"]*"[^>]*>/g, '');
}

function check(rel) {
  const out = [];
  const lines = fs.readFileSync(path.join(ROOT, rel), 'utf8').split(/\r?\n/);
  lines.forEach((raw, i) => {
    const line = stripTargets(raw);
    for (const [re, why] of RULES) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(line)) !== null) out.push({ rel, line: i + 1, text: m[0], why });
    }
  });
  return out;
}

function main() {
  const args = process.argv.slice(2);
  const ci = args.includes('--ci');
  const count = args.includes('--count');
  const files = args.filter((a) => !a.startsWith('--'));
  const list = files.length ? files.map((f) => f.replace(/\\/g, '/')) : defaultFiles();
  let total = 0;
  for (const rel of list) {
    const found = check(rel);
    total += found.length;
    if (count) { if (found.length) console.log(`${String(found.length).padStart(4)}  ${rel}`); continue; }
    for (const f of found) console.log(`${f.rel}:${f.line}: ${f.why}: ${f.text}`);
  }
  console.log(`wording: ${list.length} files checked, ${total} internal ids found`);
  if (total) {
    console.log('Fix: say it in plain words and link the internal record ("Details: ..."). '
      + 'Rules: tools/hygiene/wording.js header.');
  }
  if (ci && total) process.exit(1);
}

main();
