#!/usr/bin/env node
// Builds wiki/diagrams/index.html from the .drawio files listed in wiki/diagrams/slides.json.
// The page uses the local draw.io viewer (tools/drawio/viewer-static.min.js), so the page works offline.
// Usage: node tools/drawio/build.js
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const DIR = path.join(ROOT, 'wiki', 'diagrams');
const manifest = JSON.parse(fs.readFileSync(path.join(DIR, 'slides.json'), 'utf8'));

const escHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const sections = manifest.slides.map((s, i) => {
  const xml = fs.readFileSync(path.join(DIR, s.file), 'utf8');
  const cfg = { highlight: '#0000ff', nav: true, resize: true, 'auto-fit': true, toolbar: 'zoom lightbox', edit: null, xml };
  return `
  <section id="s${i + 1}">
    <h2>${escHtml(s.title)}</h2>
    <p class="caption">${escHtml(s.caption)}</p>
    <div class="frame"><div class="mxgraph" data-mxgraph="${escHtml(JSON.stringify(cfg))}"></div></div>
    <p class="meta">Source: <code>${escHtml(s.file)}</code>${s.wiki ? ` · Wiki: <a href="${escHtml(s.wiki)}">${escHtml(s.wiki.replace('../', ''))}</a>` : ''}</p>
  </section>`;
}).join('\n');

const toc = manifest.slides.map((s, i) => `<a href="#s${i + 1}">${escHtml(s.title)}</a>`).join('');

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escHtml(manifest.title)}</title>
<style>
  :root { --bg:#f7f7f5; --fg:#1d1d1f; --muted:#5f6368; --card:#ffffff; --line:#e3e3e0; --accent:#3b5bdb; }
  @media (prefers-color-scheme: dark) { :root { --bg:#16171a; --fg:#ececec; --muted:#a0a4ab; --card:#ffffff; --line:#2c2e33; --accent:#8ea2ff; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
  header { padding:40px 24px 16px; max-width:1100px; margin:0 auto; }
  h1 { margin:0 0 6px; font-size:28px; }
  .sub { color:var(--muted); margin:0; }
  nav { position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line); }
  nav .inner { max-width:1100px; margin:0 auto; padding:10px 24px; display:flex; gap:18px; overflow-x:auto; white-space:nowrap; }
  nav a { color:var(--accent); text-decoration:none; font-size:14px; }
  main { max-width:1100px; margin:0 auto; padding:8px 24px 64px; }
  section { padding:28px 0; border-bottom:1px solid var(--line); scroll-margin-top:50px; }
  h2 { margin:0 0 6px; font-size:21px; }
  .caption { margin:0 0 14px; max-width:75ch; }
  .frame { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; overflow:auto; }
  .meta { color:var(--muted); font-size:13px; margin:8px 0 0; }
  .meta a { color:var(--accent); }
  code { font-size:12.5px; }
</style>
</head>
<body>
<header>
  <h1>${escHtml(manifest.title)}</h1>
  <p class="sub">${escHtml(manifest.subtitle)}</p>
</header>
<nav><div class="inner">${toc}</div></nav>
<main>
${sections}
</main>
<script src="../../tools/drawio/viewer-static.min.js"></script>
</body>
</html>
`;

fs.writeFileSync(path.join(DIR, 'index.html'), html);
console.log(`Built wiki/diagrams/index.html (${manifest.slides.length} diagrams)`);
