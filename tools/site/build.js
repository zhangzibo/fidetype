#!/usr/bin/env node
// Builds the static project site from files that already exist in the repository. Nothing on the
// site is hand-copied: every page is generated from a repository file at build time.
//
//   node tools/site/build.js                 build into _site/ (git-ignored)
//   node tools/site/build.js --out DIR       build into DIR
//   node tools/site/build.js --check-only    check the links of an existing build (default _site/)
//
// Pages (source -> site):
//   tools/site/templates/home.html + numbers.json + README.md (install) -> index.html (home page)
//   tools/site/templates/how-it-works.html + numbers.json  -> how-it-works.html (visual guide)
//   benchmark/site/* + tracks-v0.2 split files             -> benchmark/index.html, benchmark/leaderboard.html
//   benchmark/site/tracks/*.html (one page per track)      -> benchmark/tracks/*.html (P13-09)
//   src/fidetype/benchmark/hub/datasets-0.1.json           -> hub/index.html
//   spec/conformance/certified.json (+ evidence reports)   -> conformance/index.html
//   docs/*.md, benchmark/README.md, spec/README.md, spec/nts-1.0-rc4.md -> docs/*.html, spec/*.html
//   demo/, wiki/diagrams/, wiki/progress/ (generated HTML) -> demo/, diagrams/, progress/
//   tools/site/templates/*.css, *.js, tools/site/assets/fonts/ -> assets/ (own CSS, own JS, fonts)
//
// The site is static. It runs only our own JavaScript (assets/*.js: theme button, copy buttons, the
// home-page animation, simulation and chart; every page also works without it). It makes no external
// requests: no CDN, no web fonts from other servers (the fonts are self-hosted, SIL OFL 1.1), no
// trackers. The build fails if a generated page or stylesheet loads a script, style or font from
// another server. It works offline from file:// (every link names a file, never a bare folder), at
// phone width, in dark mode and with reduced motion.
// Numbers check: each number on the home page and on how-it-works.html comes from
// tools/site/numbers.json, and the build fails if it is not found word for word in its source file.
// Exit 0: built and no broken local links. Exit 1: a source is missing, a number check fails or a
// link is broken.
// Nothing is uploaded. Publishing is a maintainer step: docs/publishing-checklist.md (section G).
// No dependencies.
'use strict';
const fs = require('fs');
const path = require('path');
const md = require('./md');

const ROOT = path.resolve(__dirname, '..', '..');
const REPO = 'https://github.com/zhangzibo/fidetype';
const BLOB = `${REPO}/blob/main/`;
const TREE = `${REPO}/tree/main/`;
const P = path.posix;
const esc = md.esc;

function parseArgs(argv) {
  const a = { out: path.join(ROOT, '_site'), checkOnly: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--out') a.out = path.resolve(argv[++i]);
    else if (argv[i] === '--check-only') a.checkOnly = true;
    else { console.error(`unknown argument: ${argv[i]}`); process.exit(2); }
  }
  return a;
}

const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const readJson = f => JSON.parse(read(f));
const exists = f => fs.existsSync(path.join(ROOT, f));
const isDir = f => exists(f) && fs.statSync(path.join(ROOT, f)).isDirectory();

// ---------------------------------------------------------------------------------------------
// Site map. NAV = top bar. MD_PAGES = Markdown files rendered as pages. COPIED = generated HTML
// pages copied as they are (the site adds only its top bar). ASSETS = other files.

// Publishing decision D6 (docs/publishing-checklist.md): false leaves the progress dashboard
// (task times, agent token counts) off the site.
const INCLUDE_PROGRESS = true;

// The logo links the home page (index.html).
const NAV = [
  ['how-it-works.html', 'How it works'],
  ['docs/index.html', 'Docs'],
  ['benchmark/index.html', 'Benchmark'],
  ['hub/index.html', 'Hub'],
  ['spec/index.html', 'Spec'],
  ['conformance/index.html', 'Conformance'],
  ['demo/index.html', 'Demo'],
  ['research.html', 'Research'],
];

// Project internals: public, but not user documentation. Linked from the footer of each page,
// not from the top bar.
// The draw.io page holds internal research diagrams; how-it-works.html is the visual guide for users.
const INTERNALS = [
  ['diagrams/index.html', 'Research diagrams (draw.io)'],
  ['progress/index.html', 'Progress dashboard'],
].filter(([h]) => INCLUDE_PROGRESS || h !== 'progress/index.html');

// Docs that stay on GitHub only (maintainer checklists).
const DOCS_SKIP = new Set(['docs/publishing-checklist.md']);

function mdPages() {
  const pages = [];
  for (const f of fs.readdirSync(path.join(ROOT, 'docs')).sort()) {
    if (!f.endsWith('.md')) continue;
    const src = `docs/${f}`;
    if (DOCS_SKIP.has(src)) continue;
    pages.push({ src, out: f === 'README.md' ? 'docs/index.html' : `docs/${f.replace(/\.md$/, '.html')}`, nav: 'docs/index.html' });
  }
  pages.push({ src: 'RESEARCH.md', out: 'research.html', nav: 'research.html' });
  pages.push({ src: 'benchmark/README.md', out: 'benchmark/guide.html', nav: 'benchmark/index.html' });
  pages.push({ src: 'spec/README.md', out: 'spec/index.html', nav: 'spec/index.html' });
  pages.push({ src: currentSpec(), out: `spec/${P.basename(currentSpec(), '.md')}.html`, nav: 'spec/index.html' });
  return pages;
}

// The newest NTS 1.0 release candidate in spec/ (nts-1.0-rcN.md, highest N).
function currentSpec() {
  const rcs = fs.readdirSync(path.join(ROOT, 'spec')).map(f => /^nts-1\.0-rc(\d+)\.md$/.exec(f)).filter(Boolean)
    .sort((a, b) => +b[1] - +a[1]);
  if (!rcs.length) throw new Error('missing source: spec/nts-1.0-rcN.md');
  return `spec/${rcs[0][0]}`;
}

const COPIED = [
  { src: 'benchmark/site/index.html', out: 'benchmark/leaderboard.html', nav: 'benchmark/index.html' },
  { src: 'demo/index.html', out: 'demo/index.html', nav: 'demo/index.html' },
  { src: 'wiki/diagrams/index.html', out: 'diagrams/index.html', nav: 'diagrams/index.html', wikiDir: 'wiki/diagrams',
    replace: [['../../tools/drawio/viewer-static.min.js', 'viewer-static.min.js']] },
  { src: 'wiki/progress/index.html', out: 'progress/index.html', nav: 'progress/index.html', wikiDir: 'wiki/progress' },
  // P13-09: one generated page per track. Their "back" links name the leaderboard file.
  ...trackPages().map(f => ({ src: `benchmark/site/tracks/${f}`, out: `benchmark/tracks/${f}`, nav: 'benchmark/index.html',
    replace: [['href="../index.html', 'href="../leaderboard.html']], leaderboardNote: true })),
].filter(c => INCLUDE_PROGRESS || c.out !== 'progress/index.html');

// The per-track pages that the leaderboard generator wrote (benchmark/site/tracks/*.html).
function trackPages() {
  const dir = path.join(ROOT, 'benchmark/site/tracks');
  return fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.html')).sort() : [];
}

function assetList() {
  const a = [
    ['benchmark/site/leaderboard.json', 'benchmark/leaderboard.json'],
    ['benchmark/site/leaderboard.md', 'benchmark/leaderboard.md'],
    ['benchmark/site/history.json', 'benchmark/history.json'],
    ['demo/decision-log.json', 'demo/decision-log.json'],
    ['tools/drawio/viewer-static.min.js', 'diagrams/viewer-static.min.js'],
    ['tools/drawio/LICENSE', 'diagrams/drawio-LICENSE.txt'],
    ['src/fidetype/benchmark/hub/datasets-0.1.json', 'hub/datasets-0.1.json'],
    ['tools/site/templates/common.js', 'assets/common.js'],
    ['tools/site/templates/home.js', 'assets/home.js'],
    ['tools/site/templates/how.js', 'assets/how.js'],
    ...FONTS.map(([, file]) => [`tools/site/assets/fonts/${file}`, `assets/fonts/${file}`]),
    ['LICENSES/OFL-1.1-fonts.txt', 'assets/fonts/OFL.txt'],
    ['spec/conformance/certified.json', 'conformance/certified.json'],
  ];
  for (const f of fs.readdirSync(path.join(ROOT, 'spec/conformance/certified')).sort())
    if (f.endsWith('.json')) a.push([`spec/conformance/certified/${f}`, `conformance/certified/${f}`]);
  if (isDir('docs/img'))
    for (const f of fs.readdirSync(path.join(ROOT, 'docs/img')).sort()) a.push([`docs/img/${f}`, `docs/img/${f}`]);
  return a;
}

// repo path -> site path, for every file that is on the site.
function siteMap() {
  const m = new Map([['README.md', 'index.html'], ['tools/site/templates/how-it-works.html', 'how-it-works.html']]);
  for (const p of mdPages()) m.set(p.src, p.out);
  for (const c of COPIED) m.set(c.src, c.out);
  for (const [from, to] of assetList()) m.set(from, to);
  return m;
}

// ---------------------------------------------------------------------------------------------
// Links

const warnings = [];

// Returns the href for a link written in repository file `fromRepo`, on site page `fromSite`.
function makeLinker(map, fromRepo, fromSite) {
  return href => {
    if (!href || /^([a-z][a-z0-9+.-]*:|\/\/|#)/i.test(href)) return href;
    const [p, ...rest] = href.split('#');
    const hash = rest.length ? `#${rest.join('#')}` : '';
    let repoPath = P.normalize(P.join(P.dirname(fromRepo), decodeURI(p)));
    if (repoPath.startsWith('..')) { warnings.push(`${fromRepo}: ${href} (outside the repository)`); return href; }
    repoPath = repoPath.replace(/\/$/, '');
    // The home page is a designed page, not a render of README.md: a link to a README section goes to
    // that section on GitHub.
    if (repoPath === 'README.md' && hash) return `${BLOB}README.md${hash}`;
    let target = map.get(repoPath);
    if (!target && isDir(repoPath)) target = map.get(`${repoPath}/README.md`);
    if (target) return siteRel(fromSite, target) + hash;
    if (!exists(repoPath)) warnings.push(`${fromRepo}: ${href} (no such file in the repository)`);
    return (isDir(repoPath) ? TREE : BLOB) + repoPath.split('/').map(encodeURIComponent).join('/') + hash;
  };
}

function siteRel(fromSite, toSite) {
  const r = P.relative(P.dirname(fromSite), toSite);
  return r || P.basename(toSite);
}

function rewriteWikiLinks(html, wikiDir) {
  // href="../concepts/x.md" (relative to wikiDir) -> absolute GitHub blob link.
  return html.replace(/(href|src)="(?!https?:|#|mailto:|data:)([^"]+\.md)(#[^"]*)?"/g, (m, attr, rel, hash) => {
    const repoPath = P.normalize(P.join(wikiDir, rel));
    if (repoPath.startsWith('..')) return m;
    return `${attr}="${BLOB}${repoPath}${hash || ''}"`;
  });
}

// ---------------------------------------------------------------------------------------------
// Layout

const CSS = `
/* Doc layout. Fonts, tokens, top bar and footer come from templates/tokens.css (the build puts them first). */
:root{--card:var(--surface);--head:var(--surface-2);--accent:var(--brand-ink);--ok:var(--commit);--bad:var(--wrong);--badbg:var(--wrong-soft);--code:var(--surface-2);--warn:#8a5a00;--warnbg:#fff4dc}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--warn:#f0c674;--warnbg:#2e2614}}
:root[data-theme="dark"]{--warn:#f0c674;--warnbg:#2e2614}
main{max-width:1100px;margin:0 auto;padding:28px 16px 56px}
main.doc{max-width:900px}
h1{font-size:1.85rem;line-height:1.25;margin:0 0 10px;font-family:var(--f-head)}
h2{font-size:1.35rem;line-height:1.3;margin:36px 0 10px;font-family:var(--f-head);padding-bottom:4px;border-bottom:1px solid var(--line)}
h3{font-size:1.1rem;margin:26px 0 8px;font-family:var(--f-head)}
h4,h5,h6{font-size:1rem;margin:20px 0 6px}
h1,h2,h3,h4,h5,h6{position:relative;scroll-margin-top:64px;overflow-wrap:anywhere}
.anchor{position:absolute;left:-0.9em;width:0.9em;color:var(--muted);text-decoration:none;opacity:0;font-weight:400}
h1:hover .anchor,h2:hover .anchor,h3:hover .anchor,h4:hover .anchor,.anchor:focus{opacity:1}
p,li{overflow-wrap:anywhere}
.lead{font-size:1.1rem;color:var(--fg)}
.muted{color:var(--muted)}
code{font:0.86em/1.4 var(--f-mono);background:var(--code);border-radius:4px;padding:0.1em 0.3em}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:12px 14px;overflow-x:auto;line-height:1.45}
pre code{background:none;padding:0;font-size:13.5px;white-space:pre}
blockquote{margin:14px 0;padding:8px 14px;border-left:4px solid var(--line);background:var(--card);border-radius:0 8px 8px 0;color:var(--fg)}
blockquote p{margin:6px 0}
blockquote.callout.status{border-left-color:var(--warn);background:var(--warnbg)}
blockquote.callout.contradiction{border-left-color:var(--bad);background:var(--badbg)}
blockquote.callout.our{border-left-color:var(--accent)}
.table-wrap{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--head);font-weight:600}
tbody tr:last-child td{border-bottom:none}
td{overflow-wrap:normal;word-break:normal;min-width:6em}
td code{white-space:normal;overflow-wrap:anywhere}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap;min-width:0}
td.nw,td.nw code{white-space:nowrap}
img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px}
hr{border:none;border-top:1px solid var(--line);margin:28px 0}
.badge{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.02em;padding:1px 7px;border-radius:999px;border:1px solid currentColor;white-space:nowrap;vertical-align:1px}
.badge.ro{color:var(--bad)}
.badge.ok{color:var(--ok)}
.badge.warn{color:var(--warn)}
.badge.muted{color:var(--muted)}
.banner{margin:0 0 18px;padding:10px 14px;border-radius:8px;border:1px solid var(--warn);background:var(--warnbg);color:var(--fg)}
.banner b{color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin:14px 0}
.card{display:block;border:1px solid var(--line);border-radius:10px;background:var(--card);padding:14px 16px;text-decoration:none;color:var(--fg)}
a.card:hover{border-color:var(--accent)}
.card h3{margin:0 0 4px;font-size:1.02rem;color:var(--accent)}
.card p{margin:0;color:var(--muted);font-size:14.5px}
.toc{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:8px 14px;margin:14px 0 20px}
.toc summary{cursor:pointer;font-weight:600}
.toc ol{margin:8px 0 4px;padding-left:20px;font-size:14.5px}
.crumbs{font-size:14px;color:var(--muted);margin:0 0 12px}
.ds{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:4px 16px 12px;margin:16px 0}
.ds h3{margin-top:14px}
dl.kv{display:grid;grid-template-columns:minmax(110px,max-content) 1fr;gap:4px 14px;margin:8px 0;font-size:14.5px}
dl.kv dt{color:var(--muted)}
dl.kv dd{margin:0;overflow-wrap:anywhere}
@media (max-width:640px){
  body{font-size:15.5px}
  h1{font-size:1.5rem}
  h2{font-size:1.2rem}
  .anchor{display:none}
  dl.kv{grid-template-columns:1fr}
  dl.kv dt{margin-top:6px}
  table{font-size:13.5px}
}
`;

// Fonts: self-hosted Latin subsets (SIL OFL 1.1, LICENSES/OFL-1.1-fonts.txt). The paths are relative to assets/.
const FONTS = [
  ['Inter', 'inter-latin-wght.woff2', '100 900'],
  ['Space Grotesk', 'space-grotesk-latin-wght.woff2', '300 700'],
  ['JetBrains Mono', 'jetbrains-mono-latin-wght.woff2', '100 800'],
];
const LATIN = 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
function fontFaces(prefix) {
  return FONTS.map(([fam, file, w]) => `@font-face{font-family:"${fam}";font-style:normal;font-display:swap;font-weight:${w};src:url("${prefix}${file}") format("woff2");unicode-range:${LATIN}}`).join('\n');
}

const TPL = path.join(__dirname, 'templates');
const tpl = f => fs.readFileSync(path.join(TPL, f), 'utf8').replace(/\r\n?/g, '\n');
// One stylesheet per page type: fonts + tokens, top bar, footer (shared) + the page parts.
const cssFor = kind => [fontFaces('fonts/'), tpl('tokens.css'),
  ...(kind === 'doc' ? [CSS.trimStart()] : [tpl('theme.css'), tpl(`${kind}.css`)])].join('\n');

const LOGO = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="8" fill="#46c7e0"/><path d="M5 17h3l2-6 3 11 3-8 2 3h3" fill="none" stroke="#06222a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><rect x="24" y="9" width="2.6" height="14" rx="1.3" fill="#06222a"/></svg>';
const THEME_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/></svg>';

function topbar(sitePath, active) {
  const links = NAV.map(([href, label]) => `<a href="${siteRel(sitePath, href)}"${href === active ? ' aria-current="page"' : ''}>${label}</a>`).join('');
  return `<a class="skip" href="#main">Skip to content</a>
<header class="bar"><div class="wrap">
<a class="logo" href="${siteRel(sitePath, 'index.html')}" aria-label="Fidetype home">${LOGO}Fidetype</a>
<nav aria-label="Site">${links}<a href="${REPO}">GitHub</a></nav>
<button class="theme-btn" id="theme-btn" type="button" aria-label="Colour theme: auto. Select to change.">${THEME_ICON}</button>
</div></header>`;
}

function footer(sources, sitePath) {
  const L = h => siteRel(sitePath, h);
  const col = (title, items) => `<div><b class="h">${title}</b><ul>${items.map(([h, t]) => `<li><a href="${/^https?:/.test(h) ? h : L(h)}">${esc(t)}</a></li>`).join('')}</ul></div>`;
  const src = sources.map(s => `<a href="${BLOB}${s}"><code>${esc(s)}</code></a>`).join(', ');
  return `<footer><div class="wrap">
<div class="cols">
<div style="max-width:340px"><a class="logo" href="${L('index.html')}" aria-label="Fidetype home">${LOGO}Fidetype</a>
<p style="margin-top:10px">Open-source toolkit for brain and body-signal typing. The name: <i>fides</i> (Latin: trust) + type.</p></div>
${col('Learn', [['how-it-works.html', 'How it works'], ['docs/getting-started.html', 'Getting started'], ['docs/trust-guarantee.html', 'The trust guarantee'], ['docs/glossary.html', 'Glossary']])}
${col('Project', [['benchmark/index.html', 'Benchmark'], ['spec/index.html', 'NTS specification'], ['research.html', 'Research status'], [REPO, 'GitHub']])}
</div>
<p class="note"><b class="h">Fidetype is research software. It is not a medical device</b>, and it is not approved for clinical use. All results so far come from offline tests on public datasets, not from studies with users. Code: Apache-2.0. Fidetype is independent. It is not affiliated with or endorsed by Meta.</p>
<p class="gen">Generated by <code>node tools/site/build.js</code> from ${src}. Do not edit the HTML by hand.${internalsLine(sitePath)}</p>
</div></footer>`;
}

function internalsLine(sitePath) {
  if (!sitePath || !INTERNALS.length) return '';
  const links = INTERNALS.map(([h, t]) => `<a href="${siteRel(sitePath, h)}">${esc(t)}</a>`).join(' · ');
  return `<br>Project internals (not needed to use Fidetype): ${links}.`;
}

// The document shell of every generated page. Our own script (assets/common.js) runs in <head>, so a
// stored colour theme applies before the first paint. No request leaves the site.
function shell({ sitePath, title, description, css, scripts = [], body, sources, active, head = '' }) {
  const A = f => siteRel(sitePath, `assets/${f}`);
  return `<!doctype html>
<html lang="en" class="no-js"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description || 'Fidetype: open-source toolkit for brain and body-signal typing.')}">
<link rel="stylesheet" href="${A(css)}">
<script src="${A('common.js')}"></script>
${scripts.map(s => `<script src="${A(s)}" defer></script>`).join('\n')}${head}
</head>
<body>
${topbar(sitePath, active)}
${body}
${footer(sources, sitePath)}
</body></html>
`;
}

function page({ sitePath, title, description, active, body, sources, wide }) {
  return shell({ sitePath, title, description, active, sources, css: 'site.css',
    body: `<main id="main"${wide ? '' : ' class="doc"'}>\n${body}\n</main>` });
}

// Top bar for copied pages that have their own stylesheet: scoped, self-contained styles, same look
// as the generated top bar (dark band in both colour modes). The fonts come from the site assets.
function injectedBar(sitePath, active) {
  const links = NAV.map(([href, label]) => `<a href="${siteRel(sitePath, href)}"${href === active ? ' class="on" aria-current="page"' : ''}>${label}</a>`).join('');
  return `<style>
${fontFaces(siteRel(sitePath, 'assets/fonts') + '/')}
.ftbar{--ftb:#0d1224;--ftb2:#151c36;--ftf:#eef1f8;--ftm:#a7aec4;--ftl:#2a3354;--fta:#46c7e0;background:var(--ftb);border-bottom:1px solid var(--ftl);font:14.5px/1.4 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif}
.ftbar .ftin{max-width:1140px;margin:0 auto;padding:0 16px;display:flex;gap:14px;align-items:center;min-height:54px}
.ftbar .ftbrand{display:flex;align-items:center;gap:9px;font:700 1.05rem "Space Grotesk",system-ui,sans-serif;color:var(--ftf);text-decoration:none;padding:8px 0;white-space:nowrap}
.ftbar .ftbrand svg{width:26px;height:26px}
.ftbar nav{display:flex;gap:2px;overflow-x:auto;margin-left:auto;min-width:0;scrollbar-width:none}
.ftbar nav a{color:var(--ftm);text-decoration:none;padding:7px 9px;border-radius:8px;white-space:nowrap}
.ftbar nav a:hover,.ftbar nav a.on{color:var(--ftf);background:var(--ftb2)}
.ftbar a:focus-visible{outline:3px solid var(--fta);outline-offset:2px}
@media (max-width:1000px){.ftbar .ftin{flex-wrap:wrap;gap:0 10px}.ftbar nav{flex-basis:100%;margin:0 -16px;padding:0 10px 6px}}
</style>
<div class="ftbar"><div class="ftin"><a class="ftbrand" href="${siteRel(sitePath, 'index.html')}" aria-label="Fidetype home">${LOGO}Fidetype</a><nav aria-label="Site">${links}<a href="${REPO}">GitHub</a></nav></div></div>`;
}

function toc(headings) {
  const h2 = headings.filter(h => h.level === 2);
  if (h2.length < 4) return '';
  return `<details class="toc"><summary>On this page (${h2.length} sections)</summary><ol>${h2.map(h => `<li><a href="#${esc(h.id)}">${esc(h.text)}</a></li>`).join('')}</ol></details>`;
}

// "> **Status: PROPOSED, NOT ADOPTED.** ..." -> "PROPOSED, NOT ADOPTED"
function docStatus(text) {
  const m = /^>\s*\*\*Status:\s*([^*]+?)\.?\*\*/m.exec(text);
  return m ? m[1].trim() : null;
}

// ---------------------------------------------------------------------------------------------
// Pages

function renderMdPage(p, map) {
  const text = read(p.src);
  const r = md.render(text, { link: makeLinker(map, p.src, p.out) });
  const status = docStatus(text);
  const banner = status && /PROPOSED|DRAFT|NOT ADOPTED/i.test(status)
    ? `<div class="banner"><b>${esc(status.toUpperCase())}</b>. This page describes a proposal. It is not the rule in use.</div>` : '';
  const navLabel = (NAV.find(n => n[0] === p.nav) || [])[1];
  const crumbs = p.out.endsWith('index.html') || p.out === p.nav || !navLabel ? ''
    : `<p class="crumbs"><a href="${siteRel(p.out, p.nav)}">${esc(navLabel)}</a> / ${esc(r.title || p.src)}</p>`;
  // Put the TOC after the first heading block (title + first paragraph).
  let html = r.html;
  const t = toc(r.headings);
  if (t) {
    const cut = html.indexOf('<h2 ');
    html = cut > 0 ? html.slice(0, cut) + t + '\n' + html.slice(cut) : t + html;
  }
  return page({
    sitePath: p.out, title: r.title ? `${r.title} | Fidetype` : 'Fidetype', active: p.nav,
    description: r.title || undefined, body: crumbs + banner + html, sources: [p.src],
  });
}

// README.md sections by "## " heading.
function readmeParts() {
  const text = read('README.md').replace(/\r\n?/g, '\n');
  const parts = { intro: [] };
  let cur = 'intro';
  for (const l of text.split('\n')) {
    const h = /^## (.+)$/.exec(l);
    if (h) { cur = h[1].trim(); parts[cur] = []; continue; }
    parts[cur].push(l);
  }
  return parts;
}

// ---------------------------------------------------------------------------------------------
// Numbers on the home page and on how-it-works.html (tools/site/numbers.json).
//
// Rule 1: each claim's quote is found word for word in its source file, and its value is part of the
//         quote. Rule 2: a template shows a number only through a {{claim:KEY}} slot. The build scans
//         the template text (text, aria-label, title and alt values; not scripts or styles) and fails
//         on any other number, except the few non-claim numbers in NON_CLAIM_NUMBERS.
// Not scanned: the made-up values of the hero animation and the toy simulation in home.js. The page
// labels both ("Animation · made-up values", "Simulation · not real data").

const NUMBERS_FILE = 'tools/site/numbers.json';
const NON_CLAIM_NUMBERS = [
  [/Apache-2\.0/g, 'licence name'],
  [/\b[1-6] \/ 6\b/g, 'section counter of how-it-works.html'],
  [/\b[1-6] · /g, 'step number (hero lanes, page sections)'],
  [/1 − δ/g, 'the formula of the guarantee'],
  [/\b[Qq]uestion [12]\b/g, 'question number of the decision flow'],
  [/\b100 (guesses|simulated sentences|sentences)\b/g, 'size of the toy simulation'],
  [/\b400 fake labelled guesses\b/g, 'size of the toy simulation'],
  [/\bScale 0 to 100 %/g, 'axis of the simulation bars'],
];

function loadClaims() {
  const j = readJson(NUMBERS_FILE);
  const errors = [];
  const srcCache = new Map();
  const src = f => {
    if (!srcCache.has(f)) srcCache.set(f, exists(f) ? read(f).replace(/\r\n?/g, '\n') : null);
    return srcCache.get(f);
  };
  for (const [k, c] of Object.entries(j.claims)) {
    const text = src(c.source);
    if (text == null) errors.push(`${k}: source file ${c.source} does not exist`);
    else if (!text.includes(c.quote)) errors.push(`${k}: quote not found in ${c.source}: "${c.quote}"`);
    if (!c.quote.includes(c.value)) errors.push(`${k}: value "${c.value}" is not part of its quote "${c.quote}"`);
  }
  return { claims: j.claims, chart: j.chart, errors };
}

function strayNumbers(html, where) {
  let t = html.replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ').replace(/\{\{[^}]*\}\}/g, ' ');
  const attrs = [...t.matchAll(/\b(?:aria-label|title|alt)="([^"]*)"/g)].map(m => m[1]);
  t = [t.replace(/<[^>]*>/g, ' '), ...attrs].join(' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
  for (const [re] of NON_CLAIM_NUMBERS) t = t.replace(re, ' ');
  return [...t.matchAll(/(?<![\p{L}\p{N}_])\d+(?:[.,]\d+)*/gu)].map(m => `${where}: number "${m[0]}" near "${t.slice(Math.max(0, m.index - 30), m.index + 30).replace(/\s+/g, ' ').trim()}" has no {{claim:...}} slot`);
}

// Fills {{claim:K}}, {{src:K}} and the named slots. An unknown slot or claim fails the build.
function fillSlots(html, claims, slots, where) {
  return html.replace(/\{\{([a-z_]+)(?::([a-z0-9_]+))?\}\}/g, (m, name, key) => {
    if (name === 'claim' || name === 'src') {
      const c = claims[key];
      if (!c) throw new Error(`${where}: unknown claim {{${name}:${key}}} (add it to ${NUMBERS_FILE})`);
      return esc(name === 'claim' ? c.value : c.source);
    }
    if (!(name in slots)) throw new Error(`${where}: unknown slot ${m}`);
    return slots[name];
  });
}

// Install tabs from the README "## Install" code block ("command   # comment" per line).
function installTabs() {
  const parts = readmeParts();
  if (!parts.Install) throw new Error('missing source: README.md section "## Install"');
  const block = /```[a-z]*\n([\s\S]*?)```/.exec(parts.Install.join('\n'));
  if (!block) throw new Error('README.md "## Install": no code block');
  const LANG = { pip: ['py', 'Python'], npm: ['ts', 'TypeScript'], cargo: ['rs', 'Rust'] };
  const rows = block[1].split('\n').map(l => /^(\S.*?)\s+#\s*(.+)$/.exec(l.trim())).filter(Boolean).map(m => {
    const tool = m[1].split(/\s+/)[0];
    const [id, label] = LANG[tool] || [tool.replace(/[^a-z0-9]/gi, ''), tool];
    return { id, label, cmd: m[1], note: m[2] };
  });
  if (!rows.length) throw new Error('README.md "## Install": no "command  # comment" lines');
  const tabs = rows.map((r, i) => `<button role="tab" id="t-${r.id}" aria-controls="p-${r.id}" aria-selected="${i === 0}"${i ? ' tabindex="-1"' : ''}>${esc(r.label)}</button>`).join('\n');
  const panels = rows.map((r, i) => `<div role="tabpanel" id="p-${r.id}" aria-labelledby="t-${r.id}"${i ? ' hidden' : ''}>
<pre class="code" id="c-${r.id}" data-copy="${esc(r.cmd)}"><code><span class="c"># ${esc(r.note)}</span>
${esc(r.cmd)}</code><button class="copy" type="button" data-for="c-${r.id}">Copy</button></pre>
</div>`).join('\n');
  return `<div class="tabs" role="tablist" aria-label="Choose a language">\n${tabs}\n</div>\n${panels}\n`;
}

function versionLine(version) {
  return `<p class="hint" style="font-size:.85rem;color:var(--muted);margin-top:10px">Python package version ${esc(version)}. Releases are on <a href="https://pypi.org/project/fidetype/">PyPI</a>, <a href="https://www.npmjs.com/package/@fidetype/sdk">npm</a> and <a href="https://crates.io/crates/fidetype">crates.io</a>. The APIs can still change.</p>`;
}

function specName() {
  return P.basename(currentSpec(), '.md').toUpperCase().replace('NTS-1.0-', 'NTS 1.0 ');
}

// Returns { home, how } HTML. Throws with every claim error at once.
function homeAndHow(version) {
  const { claims, chart, errors } = loadClaims();
  const homeT = tpl('home.html');
  const howT = tpl('how-it-works.html');
  errors.push(...strayNumbers(homeT, 'templates/home.html'), ...strayNumbers(howT, 'templates/how-it-works.html'));
  const rows = chart.map((r, i) => {
    for (const f of ['label', 'sub', 'verdict']) errors.push(...strayNumbers(r[f], `${NUMBERS_FILE} chart[${i}].${f}`));
    const num = f => {
      const c = claims[r[f]];
      if (!c) { errors.push(`${NUMBERS_FILE} chart[${i}].${f}: unknown claim ${r[f]}`); return 0; }
      if (Number(c.value).toFixed(2) !== c.value) errors.push(`${NUMBERS_FILE} chart[${i}].${f}: value "${c.value}" does not show as written (2 decimals)`);
      return Number(c.value);
    };
    const text = s => s.replace(/\{\{claim:([a-z0-9_]+)\}\}/g, (m, k) => {
      if (!claims[k]) { errors.push(`${NUMBERS_FILE} chart[${i}]: unknown claim ${k}`); return m; }
      return claims[k].value;
    });
    return { l: text(r.label), s: text(r.sub), v: num('v'), lo: num('lo'), hi: num('hi'), b: num('b'), verdict: text(r.verdict), ci: claims.ci && claims.ci.value };
  });
  if (errors.length) throw new Error(`site numbers check failed (${errors.length}):\n  ${errors.join('\n  ')}`);
  const slots = { repo: REPO, install_tabs: installTabs() + versionLine(version), spec_name: esc(specName()) };
  const data = JSON.stringify(rows).replace(/</g, '\\u003c');
  const numSources = [...new Set(Object.values(claims).map(c => c.source))];
  const home = shell({
    sitePath: 'index.html', title: 'Fidetype: trusted typing from brain and body signals', active: 'index.html', css: 'home.css', scripts: ['home.js'],
    description: 'Fidetype is an open-source toolkit that turns brain and muscle signals into text, and types only when it is confident.',
    head: `\n<script type="application/json" id="numbers-data">${data}</script>`,
    body: `<main id="main">\n${fillSlots(homeT, claims, slots, 'templates/home.html')}</main>\n<div id="tip" role="tooltip"></div>`,
    sources: ['tools/site/templates/home.html', NUMBERS_FILE, 'README.md', ...numSources.filter(s => s !== 'README.md')],
  });
  const how = shell({
    sitePath: 'how-it-works.html', title: 'How Fidetype works', active: 'how-it-works.html', css: 'how.css', scripts: ['how.js'],
    description: 'A visual guide to Fidetype: the open NTS format, the Collector and the trust layer that commits, offers or withholds each sentence.',
    body: `<main id="main">\n${fillSlots(howT, claims, slots, 'templates/how-it-works.html')}</main>`,
    sources: ['tools/site/templates/how-it-works.html', NUMBERS_FILE, 'docs/trust-guarantee.md', 'docs/concepts.md'],
  });
  return { home, how };
}

function trackSplits() {
  const dir = 'src/fidetype/benchmark/splits/tracks-v0.2';
  return fs.readdirSync(path.join(ROOT, dir)).filter(f => f.endsWith('.json')).sort().map(f => {
    const j = readJson(`${dir}/${f}`);
    return { track: j.track, dataset: j.dataset, licence: j.licence, research_only: !!j.research_only, version: j.version,
      counts: j.counts || {}, digest: j.digest, rule: j.rule, file: `${dir}/${f}` };
  });
}

function fmt(x, d = 2) { return x == null || Number.isNaN(x) ? '—' : Number(x).toFixed(d); }

function benchmarkPage(map) {
  const lb = readJson('benchmark/site/leaderboard.json');
  const splits = trackSplits();
  const v2 = new Set(splits.map(s => s.track));
  // Headline: safe-wpm/0.2 (adopted 2026-11-22; fields safe_wpm*). Tracks v0.1 have v0.1 values only (safe_wpm_v01*).
  const bestBy = (entries, val, st) => {
    const c = (entries || []).filter(e => e[st] === 'certified' && e[val] != null);
    return c.length ? c.reduce((a, b) => (b[val] > a[val] ? b : a)) : null;
  };
  const best = entries => bestBy(entries, 'safe_wpm', 'safe_wpm_status');
  const best01 = entries => bestBy(entries, 'safe_wpm_v01', 'safe_wpm_v01_status');
  const testN = s => {
    const parts = Object.entries(s.counts).map(([unit, c]) => (c && c.test != null ? `${c.test} ${unit}s` : null)).filter(Boolean);
    return parts.join(', ') || '—';
  };
  // P13-09: each track cell links to the generated track page (stable URL), when there is one.
  const pages = lb.track_pages || {};
  const trackCell = t => {
    const pg = pages[t] && pages[t].page;
    const f = pg && P.basename(pg);
    return f && trackPages().includes(f) ? `<a href="tracks/${esc(f)}"><code>${esc(t)}</code></a>` : `<code>${esc(t)}</code>`;
  };
  const rowsFor = list => list.map(s => {
    const e = lb.tracks[s.track] || [];
    const b = best(e);
    return `<tr><td class="nw">${trackCell(s.track)}${s.research_only ? '<br><span class="badge ro">RESEARCH ONLY</span>' : ''}</td><td class="nw"><code>${esc(s.dataset)}</code></td><td>${esc(s.licence)}</td><td class="num">${esc(testN(s))}</td><td class="num">${e.length}</td><td>${b ? `<span class="num">${fmt(b.safe_wpm)}</span> <span class="muted">(${esc(b.decoder)}; ${esc(b.policy)})</span>` : '<span class="muted">none certified</span>'}</td></tr>`;
  }).join('\n');
  const head = '<thead><tr><th>Track</th><th>Dataset</th><th>Licence</th><th>Test units</th><th>Entries</th><th>Best certified safe WPM (v0.2)</th></tr></thead>';
  const clean = splits.filter(s => !s.research_only);
  const ro = splits.filter(s => s.research_only);
  const legacy = Object.keys(lb.tracks).filter(t => !v2.has(t)).map(t => {
    const e = lb.tracks[t];
    const b = best01(e);
    const ro = pages[t] && pages[t].research_only ? '<br><span class="badge ro">RESEARCH ONLY</span>' : '';
    return `<tr><td class="nw">${trackCell(t)}${ro}</td><td class="num">${e.length}</td><td>${b ? fmt(b.safe_wpm_v01) : '<span class="muted">none certified</span>'}</td></tr>`;
  }).join('\n');
  const prop = read('docs/safe-wpm-v0.2-proposal.md');
  const propStatus = docStatus(prop) || 'see the page';
  const metrics = `<div class="table-wrap"><table><thead><tr><th>Metric version</th><th>State</th><th>Definition</th></tr></thead><tbody>
<tr><td><code>safe-wpm/0.2</code></td><td><span class="badge ok">${esc(propStatus.toUpperCase())}</span> Headline column of the leaderboard since 2026-11-22: prefix credit and a reading cost of 0.5 s + 0.3 s per committed word per commit</td><td><a href="${siteRel('benchmark/index.html', map.get('docs/safe-wpm.md'))}">Safe WPM</a> (section 6a), <a href="${siteRel('benchmark/index.html', map.get('docs/safe-wpm-v0.2-proposal.md'))}">v0.2 text and history</a></td></tr>
<tr><td><code>safe-wpm/0.1</code></td><td><span class="badge">EARLIER</span> Second column of the leaderboard. Every earlier number keeps its value and its v0.1 label</td><td><a href="${siteRel('benchmark/index.html', map.get('docs/safe-wpm.md'))}">Safe WPM</a></td></tr>
</tbody></table></div>`;
  const L = f => siteRel('benchmark/index.html', map.get(f));
  const body = `<h1>Benchmark</h1>
<p class="lead">The open benchmark scores neural text entry from NeuralTextStream files. It ships no data and no weights. You download every dataset from its original source.</p>
<div class="grid">
<a class="card" href="leaderboard.html"><h3>Leaderboard</h3><p>All entries with CER, WER, eWPM against gaze typing, wrong-commit rate, controls and safe WPM.</p></a>
<a class="card" href="${L('docs/benchmark-tracks.md')}"><h3>Tracks</h3><p>Seven tracks v0.2 with fixed, hash-only splits. Verify your dataset copy.</p></a>
<a class="card" href="${L('docs/benchmark-submission.md')}"><h3>Submit a result</h3><p>Submission format v0.2, required controls, the one-command scorer.</p></a>
<a class="card" href="${L('docs/hallucination-benchmark.md')}"><h3>Hallucination benchmark</h3><p>Null, scrambled and swapped-signal tracks: does a decoder invent text?</p></a>
<a class="card" href="${siteRel('benchmark/index.html', 'hub/index.html')}"><h3>Hub dataset registry</h3><p>Dataset versions, licences, checksums and replay adapters.</p></a>
<a class="card" href="guide.html"><h3>Benchmark guide</h3><p>How the benchmark works, how to run the scorer, how to submit.</p></a>
</div>
<h2 id="safe-wpm">Safe WPM versions</h2>
<p>Safe WPM counts the words that the system types right by itself, and only when the trust layer has a certified bound on the wrong-commit rate.</p>
${metrics}
<h2 id="tracks-v02">Tracks v0.2: commercially clean data</h2>
<div class="table-wrap"><table>${head}<tbody>
${rowsFor(clean)}
</tbody></table></div>
<h2 id="research-only">Tracks v0.2: research-only data</h2>
<p>These datasets carry a non-commercial licence. Results, streams and weights from them are research only.</p>
<div class="table-wrap"><table>${head}<tbody>
${rowsFor(ro)}
</tbody></table></div>
<h2 id="tracks-v01">Tracks v0.1 (earlier splits)</h2>
<p class="muted">These entries were not scored again under v0.2. They show safe WPM v0.1 only.</p>
<div class="table-wrap"><table><thead><tr><th>Track</th><th>Entries</th><th>Best certified safe WPM (v0.1)</th></tr></thead><tbody>
${legacy}
</tbody></table></div>
<p class="muted">Machine-readable: <a href="leaderboard.json">leaderboard.json</a>, <a href="leaderboard.md">leaderboard.md</a>. Benchmark version ${esc(lb.benchmark_version)}.</p>`;
  return page({ sitePath: 'benchmark/index.html', title: 'Benchmark | Fidetype', active: 'benchmark/index.html', body, wide: true,
    sources: ['benchmark/site/leaderboard.json', 'src/fidetype/benchmark/splits/tracks-v0.2/', 'docs/safe-wpm-v0.2-proposal.md'] });
}

function hubPage(map) {
  const reg = readJson('src/fidetype/benchmark/hub/datasets-0.1.json');
  const ds = reg.datasets;
  const roBadge = d => (d.licence.research_only ? ' <span class="badge ro">RESEARCH ONLY</span>' : '');
  const status = s => `<span class="badge ${s === 'registered' ? 'ok' : s === 'candidate' ? 'warn' : 'muted'}">${esc(s)}</span>`;
  const anchor = d => `ds-${d.id}-${d.version}`.replace(/[^a-z0-9-]/gi, '-').toLowerCase();
  const row = d => `<tr><td class="nw"><a href="#${anchor(d)}"><code>${esc(d.id)}</code></a>${d.licence.research_only ? '<br><span class="badge ro">RESEARCH ONLY</span>' : ''}</td><td class="nw"><code>${esc(d.version)}</code> r${esc(d.revision)}</td><td>${status(d.status)}</td><td>${esc(d.hub_role || '—')}</td><td>${esc(d.modality)}</td><td>${esc(d.language)}</td><td>${esc(d.licence.spdx)}</td><td>${d.tracks.map(t => `<code>${esc(t.track)}</code> <span class="muted">(${esc(t.split_version)})</span>`).join('<br>')}</td></tr>`;
  const head = '<thead><tr><th>Dataset</th><th>Version</th><th>Status</th><th>Hub role</th><th>Modality</th><th>Language</th><th>Licence</th><th>Tracks</th></tr></thead>';
  const doi = x => (x ? `<a href="https://doi.org/${esc(x)}">${esc(x)}</a>` : '—');
  const bytes = b => (b == null ? '—' : b >= 1e9 ? `${(b / 1e9).toFixed(2)} GB` : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${b} B`);
  const link = makeLinker(map, 'docs/hub-design.md', 'hub/index.html');
  const inl = s => md.inline(String(s ?? ''), { link });
  const detail = d => {
    const files = d.forms.map(f => `<tr><td><code>${esc(f.form)}</code></td><td>${inl(f.description)}</td><td>${f.files.map(x => `<code>${esc(x.name)}</code> <span class="muted">${bytes(x.bytes)}</span>`).join('<br>')}</td><td>${f.files.map(x => (x.sha256 ? `<code>${esc(x.sha256)}</code>` : `<span class="badge warn">no checksum</span> ${inl(x.note || '')}`)).join('<br>')}</td></tr>`).join('\n');
    const adapters = (d.adapters || []).map(a => `<tr><td><code>${esc(a.form)}</code></td><td><code>${esc(a.module)}</code></td><td><code>${esc(a.call)}</code></td><td>${inl(a.emits)}</td><td>${a.transports.map(esc).join(', ')}</td></tr>`).join('\n');
    const same = (d.same_units || []).map(s => `<p><span class="badge warn">same units</span> forms ${s.forms.map(f => `<code>${esc(f)}</code>`).join(' and ')}: ${inl(s.note)}</p>`).join('');
    const verify = Object.entries(d.verify || {}).filter(([, v]) => v).map(([k, v]) => `<dt>Verify (${esc(k)})</dt><dd><code>${esc(v)}</code></dd>`).join('');
    return `<section class="ds" id="${anchor(d)}">
<h3>${esc(d.title)}${roBadge(d)}</h3>
<dl class="kv">
<dt>Registry key</dt><dd><code>${esc(d.id)}</code> @ <code>${esc(d.version)}</code>, revision ${esc(d.revision)}, ${status(d.status)}</dd>
<dt>Citation</dt><dd>${inl(d.citation.text)}<br>Paper: ${doi(d.citation.doi)}. Data: ${doi(d.citation.data_doi)}</dd>
<dt>Source</dt><dd><a href="${esc(d.url)}">${esc(d.url)}</a></dd>
<dt>Licence</dt><dd>${esc(d.licence.source_text)} (<code>${esc(d.licence.spdx)}</code>). ${inl(d.licence.attribution || '')}</dd>
<dt>Participants</dt><dd>${d.participants == null ? 'not stated' : esc(d.participants)}. ${inl(d.personal_data.note || '')} Re-hosted: <b>${d.personal_data.rehost ? 'yes' : 'no'}</b>.</dd>
<dt>Download</dt><dd>${inl(d.download.instructions)}${d.download.login_required ? ' <span class="badge muted">login required</span>' : ''}</dd>
${verify}
${d.prepare ? `<dt>Prepare</dt><dd><code>${esc(d.prepare)}</code></dd>` : ''}
<dt>Steward</dt><dd>${esc(d.steward)}</dd>
</dl>
<h4>Forms and files</h4>
<div class="table-wrap"><table><thead><tr><th>Form</th><th>Content</th><th>Files</th><th>SHA-256</th></tr></thead><tbody>
${files}
</tbody></table></div>
${same}
<h4>Replay adapters</h4>
<div class="table-wrap"><table><thead><tr><th>Form</th><th>Module</th><th>Call</th><th>Emits</th><th>Transports</th></tr></thead><tbody>
${adapters || '<tr><td colspan="5" class="muted">none yet</td></tr>'}
</tbody></table></div>
</section>`;
  };
  const clean = ds.filter(d => !d.licence.research_only);
  const ro = ds.filter(d => d.licence.research_only);
  const design = siteRel('hub/index.html', map.get('docs/hub-design.md'));
  const body = `<h1>Benchmark hub: dataset registry</h1>
<p class="lead">The hub turns the leaderboard into a reproducible benchmark. Each entry below is one dataset version with its licence, checksums, download and verify commands, and replay adapters.</p>
<div class="banner"><b>Rule:</b> ${esc(reg.rule)}</div>
<p>Registry <code>${esc(reg.schema)}</code>, version ${esc(reg.registry_version)}, updated ${esc(reg.updated)}. Design: <a href="${design}">benchmark hub design</a>. Machine-readable: <a href="datasets-0.1.json">datasets-0.1.json</a>. Check a copy with <code>python -m fidetype.benchmark.hub</code>.</p>
<h2 id="commercially-clean">Commercially clean datasets</h2>
<div class="table-wrap"><table>${head}<tbody>
${clean.map(row).join('\n')}
</tbody></table></div>
<h2 id="research-only">Research-only datasets</h2>
<p>A research-only dataset gives research-only streams, results and weights. The licence flags travel with the data into every stream header.</p>
<div class="table-wrap"><table>${head}<tbody>
${ro.map(row).join('\n') || '<tr><td colspan="8" class="muted">none</td></tr>'}
</tbody></table></div>
<h2 id="entries">Entries</h2>
${[...clean, ...ro].map(detail).join('\n')}`;
  return page({ sitePath: 'hub/index.html', title: 'Hub registry | Fidetype', active: 'hub/index.html', body, wide: true,
    sources: ['src/fidetype/benchmark/hub/datasets-0.1.json'] });
}

function conformancePage(map) {
  const c = readJson('spec/conformance/certified.json');
  const levelBadge = l => `<span class="badge ${l === 'trust-ready' ? 'ok' : l === 'full' ? 'warn' : 'muted'}">${esc(l)}</span>`;
  const rows = c.entries.map(e => `<tr><td><b>${esc(e.id)}</b><br><span class="muted">${esc(e.implementation)}</span></td><td>${esc(e.language || '—')}</td><td>${esc(e.class || '—')}</td><td>${levelBadge(e.level)}</td><td>${(e.profiles || []).map(esc).join(', ') || '—'}</td><td class="nw">${(e.bindings || []).map(b => `<code>${esc(b)}</code>`).join('<br>') || '—'}</td><td class="num">${esc(e.kit_version || '—')}</td><td class="num">${esc(e.date || '—')}</td><td>${e.evidence ? `<a href="${esc(e.evidence)}">report</a>` : '—'}</td></tr>`).join('\n');
  const counts = {};
  for (const e of c.entries) counts[e.level] = (counts[e.level] || 0) + 1;
  const docs = siteRel('conformance/index.html', map.get('docs/conformance.md'));
  const body = `<h1>Certified implementations</h1>
<p class="lead">The self-certification list for ${esc(c.spec)} (section ${esc(c.section)}). ${c.entries.length} entries: ${Object.entries(counts).map(([k, v]) => `${v} ${esc(k)}`).join(', ')}.</p>
<div class="banner">${esc(c.note)}</div>
<p>How to run the kit and join the list: <a href="${docs}">conformance guide</a>. Machine-readable: <a href="certified.json">certified.json</a>.</p>
<div class="table-wrap"><table><thead><tr><th>Implementation</th><th>Language</th><th>Class</th><th>Level</th><th>Profiles</th><th>Bindings</th><th>Kit</th><th>Date</th><th>Evidence</th></tr></thead><tbody>
${rows}
</tbody></table></div>`;
  return page({ sitePath: 'conformance/index.html', title: 'Certified implementations | Fidetype', active: 'conformance/index.html', body, wide: true,
    sources: ['spec/conformance/certified.json'] });
}

function leaderboardNote(map, from = 'benchmark/leaderboard.html') {
  const href = siteRel(from, map.get('docs/safe-wpm.md'));
  return `<div class="ftbar" style="border-bottom:none"><div class="ftin" style="display:block;padding:8px 16px;color:var(--ftm)">The headline column "Safe WPM v0.2 @ alpha" uses <code>safe-wpm/0.2</code>, <b style="color:var(--ftf)">ADOPTED 2026-11-22</b> (with the reading cost). The "Safe WPM v0.1 @ alpha" column keeps the earlier values and labels: <a style="color:var(--fta)" href="${href}">definition</a>.</div></div>`;
}

function pythonVersion() {
  const src = read('src/fidetype/__init__.py');
  const m = src.match(/__version__ = "([^"]+)"/);
  return m ? m[1] : 'unknown';
}

function write(out, rel, content) {
  const f = path.join(out, rel);
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, content);
}

function build(out) {
  warnings.length = 0;
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  const map = siteMap();
  const { home, how } = homeAndHow(pythonVersion()); // number check first: fail before writing pages
  write(out, 'assets/site.css', cssFor('doc'));
  write(out, 'assets/home.css', cssFor('home'));
  write(out, 'assets/how.css', cssFor('how'));
  for (const [from, to] of assetList()) {
    if (!exists(from)) throw new Error(`missing source: ${from}`);
    fs.mkdirSync(path.dirname(path.join(out, to)), { recursive: true });
    fs.copyFileSync(path.join(ROOT, from), path.join(out, to));
  }
  for (const c of COPIED) {
    if (!exists(c.src)) throw new Error(`missing source: ${c.src}`);
    let html = read(c.src);
    for (const [a, b] of c.replace || []) html = html.split(a).join(b);
    if (c.wikiDir) html = rewriteWikiLinks(html, c.wikiDir);
    let bar = injectedBar(c.out, c.nav);
    if (c.out === 'benchmark/leaderboard.html' || c.leaderboardNote) bar += leaderboardNote(map, c.out);
    html = /<body[^>]*>/i.test(html) ? html.replace(/<body[^>]*>/i, m => `${m}\n${bar}`) : bar + html;
    write(out, c.out, html);
  }
  for (const p of mdPages()) {
    if (!exists(p.src)) throw new Error(`missing source: ${p.src}`);
    write(out, p.out, renderMdPage(p, map));
  }
  write(out, 'index.html', home);
  write(out, 'how-it-works.html', how);
  write(out, 'benchmark/index.html', benchmarkPage(map));
  write(out, 'hub/index.html', hubPage(map));
  write(out, 'conformance/index.html', conformancePage(map));
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
      idsCache.set(file, new Set([...html.matchAll(/\b(?:id|name)="([^"]+)"/g)].map(m => m[1].replace(/&amp;/g, '&').replace(/&quot;/g, '"'))));
    }
    return idsCache.get(file);
  };
  for (const file of files.filter(f => f.endsWith('.html'))) {
    const html = fs.readFileSync(file, 'utf8');
    for (const m of html.matchAll(/\b(?:href|src)="([^"]*)"/g)) {
      const link = m[1].replace(/&amp;/g, '&').replace(/&quot;/g, '"');
      if (!link || /^(mailto:|data:|javascript:)/.test(link)) continue;
      if (/^(https?:)?\/\//.test(link)) { external.add(link); continue; }
      const [p, hash] = link.split('#');
      let target = p ? path.resolve(path.dirname(file), decodeURI(p.split('?')[0])) : file;
      if (p && (p.endsWith('/') || (fs.existsSync(target) && fs.statSync(target).isDirectory()))) target = path.join(target, 'index.html');
      const rel = path.relative(out, file).split(path.sep).join('/');
      if (!target.startsWith(out)) { broken.push(`${rel}: ${link} (outside the site)`); continue; }
      if (!fs.existsSync(target)) { broken.push(`${rel}: ${link} (no file)`); continue; }
      if (hash && target.endsWith('.html') && !idsOf(target).has(decodeURIComponent(hash))) broken.push(`${rel}: ${link} (no anchor #${hash})`);
    }
  }
  return { broken, external, files: files.length };
}

// Files that make the browser load a resource from another server (script, stylesheet, font, image,
// frame, preconnect). Links that the reader follows (a href) are fine.
function externalLoads(out) {
  const found = [];
  const res = [
    /<(?:script|img|iframe|audio|video|source|embed)\b[^>]*\bsrc="(?:https?:)?\/\/[^"]*"/gi,
    /<link\b[^>]*\bhref="(?:https?:)?\/\/[^"]*"[^>]*>/gi,
    /@import\s+(?:url\()?['"]?(?:https?:)?\/\//gi,
    /url\(\s*['"]?(?:https?:)?\/\/[^)]*\)/gi,
  ];
  for (const file of walk(out).filter(f => /\.(html|css)$/.test(f))) {
    const text = fs.readFileSync(file, 'utf8');
    const rel = path.relative(out, file).split(path.sep).join('/');
    for (const re of res) for (const m of text.matchAll(re)) found.push(`${rel}: ${m[0].slice(0, 120)}`);
  }
  return found;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.checkOnly) {
    try { build(args.out); } catch (e) { console.error(`build failed: ${e.message}`); process.exit(1); }
  }
  const { broken, external, files } = checkLinks(args.out);
  console.log(`site: ${path.relative(process.cwd(), args.out) || args.out} (${files} files, ${external.size} external links not fetched)`);
  if (warnings.length) {
    console.log(`source links that point at no repository file (sent to GitHub, not broken on the site): ${warnings.length}`);
    for (const w of [...new Set(warnings)]) console.log(`  ${w}`);
  }
  const ext = externalLoads(args.out);
  if (ext.length) {
    console.error(`resources loaded from other servers (not allowed): ${ext.length}`);
    for (const e of ext) console.error(`  ${e}`);
    process.exit(1);
  }
  console.log('external loads: none');
  if (broken.length) {
    console.error(`broken local links: ${broken.length}`);
    for (const b of broken) console.error(`  ${b}`);
    process.exit(1);
  }
  console.log('local links: all OK');
}

if (require.main === module) main();
module.exports = { build, checkLinks, rewriteWikiLinks, siteMap, mdPages, COPIED };
