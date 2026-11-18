#!/usr/bin/env node
// Assembles the static GitHub Pages site from pages that already exist in the repository.
// It does not design a new UI (that is roadmap P8-05). It copies the pages, fixes their relative
// links for the new layout, writes a plain landing page, and checks every local link offline.
//
//   node tools/site/build.js                 build into _site/ (git-ignored)
//   node tools/site/build.js --out DIR       build into DIR
//   node tools/site/build.js --check-only    check the links of an existing build (default _site/)
//
// Exit 0: the site is built and has no broken local links. Exit 1: a source is missing or a link is broken.
// Nothing is uploaded. Publishing is a maintainer step: docs/publishing-checklist.md.
// No dependencies.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const REPO = 'https://github.com/zhangzibo/fidetype';
const BLOB = `${REPO}/blob/main/`;

function parseArgs(argv) {
  const a = { out: path.join(ROOT, '_site'), checkOnly: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--out') a.out = path.resolve(argv[++i]);
    else if (argv[i] === '--check-only') a.checkOnly = true;
    else { console.error(`unknown argument: ${argv[i]}`); process.exit(2); }
  }
  return a;
}

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Each section: the folder in the site, the source files (repo-relative), and an optional rewrite.
// `wikiDir` is the repo folder of the source page; links to ../x.md are made absolute GitHub links.
const SECTIONS = [
  { dir: 'benchmark', title: 'Benchmark leaderboard', files: ['benchmark/site/index.html', 'benchmark/site/leaderboard.json', 'benchmark/site/leaderboard.md'],
    text: 'Scores of the open benchmark tracks. Research-only tracks carry a label.' },
  { dir: 'demo', title: 'Trust demo (synthetic)', files: ['demo/index.html', 'demo/decision-log.json'],
    text: 'A replay of synthetic decoder output with the trust decisions on screen. It contains no participant data.' },
  { dir: 'diagrams', title: 'Diagrams', files: ['wiki/diagrams/index.html'], wikiDir: 'wiki/diagrams',
    extra: [['tools/drawio/viewer-static.min.js', 'viewer-static.min.js'], ['tools/drawio/LICENSE', 'drawio-LICENSE.txt']],
    replace: [['../../tools/drawio/viewer-static.min.js', 'viewer-static.min.js']],
    text: 'The architecture and research diagrams of the wiki (draw.io viewer, works offline).' },
  { dir: 'progress', title: 'Project progress', files: ['wiki/progress/index.html'], wikiDir: 'wiki/progress',
    text: 'The task tracker: milestones, task times and agent effort.' },
];

// Links on the landing page to pages that are Markdown on GitHub (not rendered on the site yet: P8-01).
const GITHUB_LINKS = [
  ['Getting started', 'docs/getting-started.md'],
  ['Documentation index', 'docs/README.md'],
  ['NeuralTextStream specification', 'spec/README.md'],
  ['SDKs (Python, TypeScript, Rust)', 'docs/sdks.md'],
  ['Conformance kit', 'docs/conformance.md'],
  ['Research wiki', 'wiki/index.md'],
  ['Changelog', 'CHANGELOG.md'],
  ['Licence (Apache-2.0)', 'LICENSE'],
];

function rewriteWikiLinks(html, wikiDir) {
  // href="../concepts/x.md" (relative to wikiDir) -> absolute GitHub blob link.
  return html.replace(/(href|src)="(?!https?:|#|mailto:|data:)([^"]+\.md)(#[^"]*)?"/g, (m, attr, rel, hash) => {
    const repoPath = path.posix.normalize(path.posix.join(wikiDir, rel));
    if (repoPath.startsWith('..')) return m;
    return `${attr}="${BLOB}${repoPath}${hash || ''}"`;
  });
}

function landing(version) {
  const cards = SECTIONS.map(s => `  <li><a href="${s.dir}/">${esc(s.title)}</a><br><span>${esc(s.text)}</span></li>`).join('\n');
  const gh = GITHUB_LINKS.map(([t, p]) => `  <li><a href="${BLOB + p}">${esc(t)}</a></li>`).join('\n');
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fidetype</title>
<meta name="description" content="Fidetype: an open trust layer for neural text entry.">
<style>
:root{--bg:#fbfaf8;--fg:#1d1d1f;--muted:#5c5c66;--line:#dedbd5;--card:#ffffff;--accent:#2f5d8a}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#16171a;--fg:#e8e6e1;--muted:#a3a3ad;--line:#33353b;--card:#1d1f23;--accent:#8bb6e0}}
:root[data-theme="dark"]{--bg:#16171a;--fg:#e8e6e1;--muted:#a3a3ad;--line:#33353b;--card:#1d1f23;--accent:#8bb6e0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 48px}h1{font-size:1.7rem;margin:0 0 4px}h2{font-size:1.15rem;margin:28px 0 8px}
p{margin:6px 0;color:var(--muted)}a{color:var(--accent)}code{font-size:13px}
ul.cards{list-style:none;padding:0;margin:0;display:grid;gap:10px}ul.cards li{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:12px 14px}
ul.cards a{font-weight:600}ul.cards span{color:var(--muted);font-size:14px}
pre{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow-x:auto}
footer{margin-top:36px;font-size:13px;color:var(--muted)}
</style></head>
<body><main>
<h1>Fidetype</h1>
<p>An open trust layer for neural text entry: calibrated, abstaining, hallucination-aware BCI text decoding. It defines the NeuralTextStream (NTS) format for the output of any neural input decoder.</p>
<p>Status: pre-alpha (Python package ${esc(version)}). The format and the APIs can change.</p>
<h2>Pages on this site</h2>
<ul class="cards">
${cards}
</ul>
<h2>Install</h2>
<pre><code>pip install fidetype
npm install @fidetype/sdk
cargo add fidetype</code></pre>
<p>These commands work only after the packages are on PyPI, npm and crates.io.</p>
<h2>Documentation and source (GitHub)</h2>
<ul>
${gh}
</ul>
<footer>Code: Apache-2.0. Source: <a href="${REPO}">${REPO.replace('https://', '')}</a>. This site is built by <code>node tools/site/build.js</code> from pages in the repository.</footer>
</main></body></html>
`;
}

function pythonVersion() {
  const src = fs.readFileSync(path.join(ROOT, 'src', 'fidetype', '__init__.py'), 'utf8');
  const m = src.match(/__version__ = "([^"]+)"/);
  return m ? m[1] : 'unknown';
}

function build(out) {
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  for (const s of SECTIONS) {
    const dst = path.join(out, s.dir);
    fs.mkdirSync(dst, { recursive: true });
    for (const f of s.files) {
      const srcFile = path.join(ROOT, f);
      if (!fs.existsSync(srcFile)) throw new Error(`missing source: ${f}`);
      const name = path.basename(f);
      if (name.endsWith('.html')) {
        let html = fs.readFileSync(srcFile, 'utf8');
        for (const [a, b] of s.replace || []) html = html.split(a).join(b);
        if (s.wikiDir) html = rewriteWikiLinks(html, s.wikiDir);
        fs.writeFileSync(path.join(dst, name), html);
      } else {
        fs.copyFileSync(srcFile, path.join(dst, name));
      }
    }
    for (const [from, to] of s.extra || []) fs.copyFileSync(path.join(ROOT, from), path.join(dst, to));
  }
  fs.writeFileSync(path.join(out, 'index.html'), landing(pythonVersion()));
  // GitHub Pages: serve files as they are (no Jekyll processing).
  fs.writeFileSync(path.join(out, '.nojekyll'), '');
}

function walk(dir) {
  const r = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) r.push(...walk(p)); else r.push(p);
  }
  return r;
}

// Returns { broken: [...], external: Set, files: n }.
function checkLinks(out) {
  const broken = [];
  const external = new Set();
  const files = walk(out);
  const idsCache = new Map();
  const idsOf = file => {
    if (!idsCache.has(file)) {
      const html = fs.readFileSync(file, 'utf8');
      idsCache.set(file, new Set([...html.matchAll(/\b(?:id|name)="([^"]+)"/g)].map(m => m[1])));
    }
    return idsCache.get(file);
  };
  for (const file of files.filter(f => f.endsWith('.html'))) {
    const html = fs.readFileSync(file, 'utf8');
    for (const m of html.matchAll(/\b(?:href|src)="([^"]*)"/g)) {
      const link = m[1].replace(/&amp;/g, '&');
      if (!link || /^(mailto:|data:|javascript:)/.test(link)) continue;
      if (/^(https?:)?\/\//.test(link)) { external.add(link); continue; }
      const [p, hash] = link.split('#');
      let target = p ? path.resolve(path.dirname(file), decodeURI(p.split('?')[0])) : file;
      if (p && (p.endsWith('/') || (fs.existsSync(target) && fs.statSync(target).isDirectory()))) target = path.join(target, 'index.html');
      const rel = path.relative(out, file).split(path.sep).join('/');
      if (!target.startsWith(out)) { broken.push(`${rel}: ${link} (outside the site)`); continue; }
      if (!fs.existsSync(target)) { broken.push(`${rel}: ${link} (no file)`); continue; }
      if (hash && target.endsWith('.html') && !idsOf(target).has(hash)) broken.push(`${rel}: ${link} (no anchor #${hash})`);
    }
  }
  return { broken, external, files: files.length };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.checkOnly) build(args.out);
  const { broken, external, files } = checkLinks(args.out);
  console.log(`site: ${path.relative(process.cwd(), args.out) || args.out} (${files} files, ${external.size} external links not fetched)`);
  if (broken.length) {
    console.error(`broken local links: ${broken.length}`);
    for (const b of broken) console.error(`  ${b}`);
    process.exit(1);
  }
  console.log('local links: all OK');
}

if (require.main === module) main();
module.exports = { build, checkLinks, rewriteWikiLinks, SECTIONS };
