#!/usr/bin/env node
// Relative-link check for the user-facing Markdown pages (task R-23).
//
//   node tools/hygiene/links.js            check README.md, docs/*.md, sdk/*/README.md, CONTRIBUTING.md, ...
//   node tools/hygiene/links.js --ci       exit 1 if a link is broken (CI job "hygiene")
//   node tools/hygiene/links.js FILE...    check only these files
//
// It checks that each relative link points to an existing file or folder, and that a "#anchor"
// into a Markdown file matches a heading there (GitHub slug rules). External links (http, mailto)
// are not fetched. Links inside code blocks and inline code are ignored. No dependencies.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT = ['README.md', 'CONTRIBUTING.md', 'GOVERNANCE.md', 'SECURITY.md', 'CHANGELOG.md',
  'benchmark/README.md', 'sdk/typescript/README.md', 'sdk/rust/README.md', 'spec/README.md'];

function defaultFiles() {
  const docs = fs.readdirSync(path.join(ROOT, 'docs')).filter((f) => f.endsWith('.md')).map((f) => 'docs/' + f);
  return [...DEFAULT, ...docs].filter((f) => fs.existsSync(path.join(ROOT, f)));
}

// GitHub heading slug: lower case, drop punctuation except "-" and "_", spaces to "-".
function slug(h) {
  return h.trim().toLowerCase()
    .replace(/<[^>]+>/g, '')
    .replace(/[`*~]/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[^\p{L}\p{N}\s_-]/gu, '')
    .replace(/\s/g, '-');
}

const anchorCache = new Map();
function anchors(file) {
  if (anchorCache.has(file)) return anchorCache.get(file);
  const set = new Set();
  const seen = new Map();
  let inCode = false;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    if (/^\s*(```|~~~)/.test(line)) { inCode = !inCode; continue; }
    if (inCode) continue;
    const m = /^#{1,6}\s+(.*?)\s*#*\s*$/.exec(line);
    if (!m) continue;
    const base = slug(m[1]);
    const n = seen.get(base) || 0;
    seen.set(base, n + 1);
    set.add(n ? `${base}-${n}` : base);
  }
  anchorCache.set(file, set);
  return set;
}

function links(text) {
  const out = [];
  let inCode = false;
  text.split(/\r?\n/).forEach((line, i) => {
    if (/^\s*(```|~~~)/.test(line)) { inCode = !inCode; return; }
    if (inCode) return;
    const clean = line.replace(/`[^`]*`/g, '');
    for (const m of clean.matchAll(/\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) out.push([m[1], i + 1]);
  });
  return out;
}

function main() {
  const args = process.argv.slice(2);
  const ci = args.includes('--ci');
  const files = args.filter((a) => !a.startsWith('--'));
  const targets = files.length ? files : defaultFiles();
  const bad = [];
  let n = 0;
  for (const rel of targets) {
    const file = path.resolve(ROOT, rel);
    for (const [href, line] of links(fs.readFileSync(file, 'utf8'))) {
      if (/^(https?:|mailto:)/i.test(href)) continue;
      n += 1;
      const [p, frag] = href.split('#');
      const dest = p ? path.resolve(path.dirname(file), decodeURIComponent(p)) : file;
      if (!fs.existsSync(dest)) { bad.push(`${rel}:${line}: missing ${href}`); continue; }
      if (frag && dest.endsWith('.md') && !anchors(dest).has(frag.toLowerCase())) {
        bad.push(`${rel}:${line}: no heading for #${frag} in ${path.relative(ROOT, dest).replace(/\\/g, '/')}`);
      }
    }
  }
  console.log(`Checked ${n} relative links in ${targets.length} files.`);
  if (bad.length) {
    console.log(`BROKEN (${bad.length}):`);
    for (const b of bad) console.log('  ' + b);
    if (ci) process.exit(1);
  } else {
    console.log('Links: OK');
  }
}

main();
