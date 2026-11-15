#!/usr/bin/env node
// Repository hygiene check (task R-23). Reads the list of TRACKED files (git ls-files) and
// reports files that must not be in a public repository, plus a short size report.
//
//   node tools/hygiene/check.js            report: errors, warnings, sizes, counts per folder
//   node tools/hygiene/check.js --ci       the same, but exit 1 if there is an error (CI job "hygiene")
//   node tools/hygiene/check.js --top 30   list the 30 largest tracked files (default 15)
//
// Errors (CI fails): caches and build output, data / model files, secrets, third-party reference
// files, per-trial participant texts, private e-mail addresses, files larger than MAX_BYTES.
// Warnings (CI passes): files larger than WARN_BYTES, PDFs outside papers/, logs (count only).
// Rules and the cleanup checklist: wiki/questions/repo-hygiene.md. No dependencies.
'use strict';
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const MAX_BYTES = 5 * 1024 * 1024;   // a larger file is an error (use a release asset or keep it out of git)
const WARN_BYTES = 1024 * 1024;      // a larger file is a warning (check that it must be in git)

// [regex on the repo-relative path, reason]. Any match is an error.
const FORBIDDEN_PATHS = [
  [/(^|\/)__pycache__\//, 'Python cache'],
  [/\.py[cod]$/, 'compiled Python'],
  [/(^|\/)\.(pytest_cache|ruff_cache|mypy_cache|ipynb_checkpoints|venv)\//, 'tool cache or virtual env'],
  [/(^|\/)venv\//, 'virtual env'],
  [/(^|\/)node_modules\//, 'npm dependencies'],
  [/^sdk\/rust\/target\//, 'Rust build output'],
  [/^sdk\/typescript\/dist\//, 'TypeScript build output'],
  [/^(dist|build)\//, 'package build output'],
  [/\.egg-info\//, 'Python build metadata'],
  [/\.tgz$/, 'npm pack output'],
  [/(^|\/)(\.DS_Store|Thumbs\.db|desktop\.ini)$/i, 'OS file'],
  [/(^|\/)\.env(\..*)?$/, 'environment / secrets file'],
  [/\.(key|pem|p12|pfx)$/i, 'key or certificate'],
  [/(^|\/)(id_rsa|id_ed25519)(\.pub)?$/, 'SSH key'],
  [/\.(fif|edf|bdf|mat|npy|h5|hdf5|nwb|xdf|set|fdt|vhdr|eeg|con|sqd)$/i, 'raw or preprocessed recording / data file'],
  [/\.(pt|pth|ckpt|safetensors|onnx|pkl|pickle|joblib)$/i, 'model weights or pickled data'],
  [/^references\/(papers|repos)\//, 'third-party reference file (git-ignored by rule)'],
  [/^data\/(?!\.gitkeep$)/, 'local dataset folder'],
  [/^experiments\/.*\/results\/trials\.json$/, 'per-trial participant texts (LICENSES/DATA.md)'],
  [/(^|\/)checkpoints?\//, 'training checkpoint'],
  [/(^|\/)\.merge\.lock$/, 'tracker merge lock'],
];
// NPZ is allowed only for the synthetic golden conformance vectors.
const NPZ_ALLOWED = /^spec\/conformance\//;

// Secret patterns in text files.
const SECRETS = [
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----/, 'private key'],
  [/\bghp_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b/, 'GitHub token'],
  [/\bsk-(ant-)?[A-Za-z0-9_-]{30,}\b/, 'API key (sk-...)'],
  [/\bAKIA[0-9A-Z]{16}\b/, 'AWS access key'],
  [/\bxox[abpr]-[A-Za-z0-9-]{10,}\b/, 'Slack token'],
  [/\bnpm_[A-Za-z0-9]{36}\b/, 'npm token'],
];
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g;
// Allowed addresses: documentation placeholders and no-reply addresses.
const EMAIL_OK = /@(example\.(com|org|net)|users\.noreply\.github\.com|anthropic\.com)$|^noreply@|^no-reply@/i;
// Vendored third-party files: skip the text scans (licence headers name their authors).
const SCAN_SKIP = new Set(['tools/drawio/viewer-static.min.js']);
const TEXT_EXT = /\.(md|txt|py|js|mjs|ts|rs|json|jsonl|toml|yml|yaml|cff|tex|bib|sh|ps1|html|proto|cfg|ini|log|drawio|svg)$/i;

function gitFiles() {
  const out = execFileSync('git', ['ls-files', '-z'], { cwd: ROOT, maxBuffer: 64 * 1024 * 1024 });
  return out.toString('utf8').split('\0').filter(Boolean);
}

function fmt(n) {
  if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(2) + ' MB';
  if (n >= 1024) return (n / 1024).toFixed(1) + ' kB';
  return n + ' B';
}

function main() {
  const args = process.argv.slice(2);
  const ci = args.includes('--ci');
  const ti = args.indexOf('--top');
  const top = ti >= 0 ? parseInt(args[ti + 1], 10) || 15 : 15;

  const files = gitFiles();
  const errors = [];
  const warnings = [];
  const sizes = [];
  const perTop = new Map();
  let logs = 0;

  for (const f of files) {
    const abs = path.join(ROOT, f);
    let size = 0;
    try { size = fs.statSync(abs).size; } catch { continue; }   // deleted in the work tree, not yet committed
    sizes.push([size, f]);
    const t = f.includes('/') ? f.split('/')[0] + '/' : f;
    const e = perTop.get(t) || { n: 0, bytes: 0 };
    e.n += 1; e.bytes += size; perTop.set(t, e);

    for (const [re, why] of FORBIDDEN_PATHS) if (re.test(f)) errors.push(`${f}: ${why}`);
    if (/\.npz$/i.test(f) && !NPZ_ALLOWED.test(f)) errors.push(`${f}: NPZ outside spec/conformance (data file)`);
    if (size > MAX_BYTES) errors.push(`${f}: ${fmt(size)} > ${fmt(MAX_BYTES)}`);
    else if (size > WARN_BYTES) warnings.push(`${f}: ${fmt(size)} (large; must it be in git?)`);
    if (/\.pdf$/i.test(f) && !f.startsWith('papers/')) warnings.push(`${f}: PDF outside papers/ (third-party PDFs must not be committed)`);
    if (/\.log$/i.test(f)) logs += 1;

    if (SCAN_SKIP.has(f) || !TEXT_EXT.test(f) || size > 8 * 1024 * 1024) continue;
    const text = fs.readFileSync(abs, 'utf8');
    for (const [re, why] of SECRETS) if (re.test(text)) errors.push(`${f}: looks like a ${why}`);
    const bad = new Set();
    for (const m of text.matchAll(EMAIL)) {
      const a = m[0];
      if (EMAIL_OK.test(a)) continue;
      if (/\.(png|jpg|svg|js|ts|py|md|json)$/i.test(a)) continue;   // file names like icon@2x.png
      bad.add(a);
    }
    for (const a of bad) errors.push(`${f}: e-mail address "${a}" (use you@example.com or a noreply address)`);
  }

  const total = sizes.reduce((s, [n]) => s + n, 0);
  console.log(`Tracked files: ${files.length}, total ${fmt(total)}`);
  console.log('\nPer top-level entry (files, size):');
  for (const [t, e] of [...perTop].sort((a, b) => b[1].bytes - a[1].bytes)) {
    if (e.bytes >= 50 * 1024 || e.n >= 10) console.log(`  ${t.padEnd(22)} ${String(e.n).padStart(5)}  ${fmt(e.bytes)}`);
  }
  console.log(`\nLargest ${top} tracked files:`);
  for (const [n, f] of sizes.sort((a, b) => b[0] - a[0]).slice(0, top)) console.log(`  ${fmt(n).padStart(9)}  ${f}`);
  console.log(`\nTracked .log files: ${logs} (provenance logs; see wiki/questions/repo-hygiene.md)`);

  if (warnings.length) {
    console.log(`\nWarnings (${warnings.length}):`);
    for (const w of warnings) console.log('  ' + w);
  }
  if (errors.length) {
    console.log(`\nERRORS (${errors.length}):`);
    for (const e of errors) console.log('  ' + e);
    console.log('\nFix: git rm --cached <file> (keep it locally) or git rm <file>, then add a .gitignore rule.');
  } else {
    console.log('\nHygiene: OK (no forbidden files, no secrets, no private e-mail addresses, no file > 5 MB).');
  }
  if (ci && errors.length) process.exit(1);
}

main();
