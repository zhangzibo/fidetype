// A small Markdown -> HTML renderer for the static site (tools/site/build.js). No dependencies.
//
// It covers the Markdown that the repository pages use: ATX headings (with GitHub-style ids, so
// links like docs/hub-design.md#42-rules work on the site), paragraphs, fenced code, tables
// (GitHub pipe tables, `\|` escapes), block quotes, nested ordered and unordered lists, rules,
// inline code, links, images, autolinks, bold, italic and strike-through.
// All raw HTML in the source is escaped: the site never passes HTML from a page through.
//
//   const { render } = require('./md');
//   const { html, headings, title } = render(markdownText, { link: (href) => newHref });
'use strict';

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// GitHub heading ids: lower case; drop every character that is not a letter, a digit, '_', '-' or a
// space; spaces become '-'. A repeated id gets -1, -2, ...
function slugBase(plain) {
  return plain.trim().toLowerCase().replace(/[^\p{L}\p{M}\p{N}_\- ]/gu, '').replace(/ /g, '-');
}

// Plain text of inline Markdown (for heading ids and the page title).
function plainText(s) {
  return s
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/`+([^`]*)`+/g, '$1')
    .replace(/\\([\\`*_{}[\]()#+\-.!|<>~])/g, '$1')
    .replace(/(\*\*|__|~~)/g, '')
    .replace(/(^|[^\p{L}\p{N}])[*_](?=\S)/gu, '$1')
    .replace(/(\S)[*_](?=[^\p{L}\p{N}]|$)/gu, '$1')
    .replace(/<(https?:[^>\s]+)>/g, '$1');
}

function inline(src, opt) {
  const slots = [];
  const keep = h => `\u0000${slots.push(h) - 1}\u0000`;
  let s = src;
  // 1. code spans
  s = s.replace(/(`+)([\s\S]*?[^`])\1(?!`)/g, (m, ticks, code) => {
    let c = code;
    if (/^ .* $/.test(c) && c.trim()) c = c.slice(1, -1);
    return keep(`<code>${esc(c)}</code>`);
  });
  // 2. backslash escapes
  s = s.replace(/\\([\\`*_{}[\]()#+\-.!|<>~])/g, (m, ch) => keep(esc(ch)));
  // 3. autolinks <https://...>
  s = s.replace(/<(https?:\/\/[^>\s]+)>/g, (m, url) => keep(`<a href="${esc(opt.link(url))}">${esc(url)}</a>`));
  // 4. images and links (link text may hold code slots and emphasis)
  const linkRe = /(!?)\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\(\s*<?([^\s)>]*)>?(?:\s+"([^"]*)")?\s*\)/g;
  s = s.replace(linkRe, (m, bang, text, href, title) => {
    const h = esc(opt.link(href));
    const t = title ? ` title="${esc(title)}"` : '';
    if (bang) return keep(`<img src="${h}" alt="${esc(plainText(text))}"${t} loading="lazy">`);
    return keep(`<a href="${h}"${t}>${emph(esc(text))}</a>`);
  });
  // 5. bare URLs
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<>"')]*[^\s<>"').,;:!?])/g, (m, pre, url) => pre + keep(`<a href="${esc(opt.link(url))}">${esc(url)}</a>`));
  // 6. escape the rest, then emphasis
  s = emph(esc(s));
  // restore (slots can hold slots: link text)
  for (let i = 0; i < 3; i++) s = s.replace(/\u0000(\d+)\u0000/g, (m, n) => slots[+n]);
  return s;
}

function emph(s) {
  return s
    .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^\p{L}\p{N}_])__(?=\S)([\s\S]*?\S)__(?![\p{L}\p{N}_])/gu, '$1<strong>$2</strong>')
    .replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>')
    .replace(/(^|[^\p{L}\p{N}*])\*(?=[^\s*])([\s\S]*?[^\s*])\*(?![\p{L}\p{N}*])/gu, '$1<em>$2</em>')
    .replace(/(^|[^\p{L}\p{N}_])_(?=[^\s_])([\s\S]*?[^\s_])_(?![\p{L}\p{N}_])/gu, '$1<em>$2</em>');
}

// Split a table row on pipes that are not escaped. (GitHub also splits inside code spans unless `\|`.)
function splitRow(line) {
  let t = line.trim();
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|') && !t.endsWith('\\|')) t = t.slice(0, -1);
  const cells = [];
  let cur = '';
  for (let i = 0; i < t.length; i++) {
    if (t[i] === '\\' && t[i + 1] === '|') { cur += '\\|'; i++; continue; }
    if (t[i] === '|') { cells.push(cur); cur = ''; continue; }
    cur += t[i];
  }
  cells.push(cur);
  return cells.map(c => c.trim().replace(/\\\|/g, '|'));
}
// After splitting, a `\|` inside a code span must show as `|`. splitRow already replaced it; but the
// inline pass would read `|` literally, which is right. Outside code, `|` is plain text too.

const isSep = l => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l) && l.includes('-');
const isFence = l => /^\s{0,3}(```+|~~~+)/.exec(l);
const listMarker = l => /^(\s*)([-*+]|\d{1,9}[.)])(\s+|$)(.*)$/.exec(l);
const isHr = l => /^\s{0,3}([-*_])(\s*\1){2,}\s*$/.test(l);
const isHeading = l => /^\s{0,3}(#{1,6})(?:\s+(.*?))?\s*#*\s*$/.exec(l);

function renderBlocks(lines, ctx) {
  const out = [];
  let i = 0;
  const startsBlock = l => isFence(l) || isHeading(l) || /^\s{0,3}>/.test(l) || listMarker(l) || isHr(l);
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    // fenced code
    const f = isFence(line);
    if (f) {
      const fence = f[1];
      const lang = line.trim().slice(fence.length).trim().split(/\s+/)[0];
      const indent = line.match(/^\s*/)[0].length;
      const body = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[0].repeat(fence.length))) {
        body.push(lines[i].slice(Math.min(indent, lines[i].match(/^\s*/)[0].length)));
        i++;
      }
      i++;
      out.push(`<pre><code${lang ? ` class="language-${esc(lang)}"` : ''}>${esc(body.join('\n'))}</code></pre>`);
      continue;
    }
    // heading
    const h = isHeading(line);
    if (h) {
      const level = h[1].length;
      const text = (h[2] || '').trim();
      const plain = plainText(text);
      let id = slugBase(plain);
      const n = ctx.ids.get(id) || 0;
      ctx.ids.set(id, n + 1);
      if (n) id = `${id}-${n}`;
      ctx.headings.push({ level, text: plain, id });
      out.push(`<h${level} id="${esc(id)}"><a class="anchor" href="#${esc(id)}" aria-hidden="true">#</a>${inline(text, ctx.opt)}</h${level}>`);
      i++;
      continue;
    }
    if (isHr(line)) { out.push('<hr>'); i++; continue; }
    // collapsed section: only the exact lines "<details>", "<summary>text</summary>", "</details>"
    const det = /^\s*(<details>|<\/details>|<summary>([^<]*)<\/summary>)\s*$/.exec(line);
    if (det) {
      out.push(det[2] !== undefined ? `<summary>${inline(det[2], ctx.opt)}</summary>` : det[1]);
      i++;
      continue;
    }
    // block quote
    if (/^\s{0,3}>/.test(line)) {
      const body = [];
      while (i < lines.length && lines[i].trim() && (/^\s{0,3}>/.test(lines[i]) || (body.length && !startsBlock(lines[i])))) {
        body.push(lines[i].replace(/^\s{0,3}> ?/, ''));
        i++;
      }
      const inner = renderBlocks(body, ctx);
      const first = body.join(' ');
      let cls = '';
      if (/^\*\*(Our take|Contradiction|Status|Warning|Note)\b/i.test(first)) cls = ` class="callout ${first.match(/^\*\*(\w+)/)[1].toLowerCase()}"`;
      out.push(`<blockquote${cls}>${inner}</blockquote>`);
      continue;
    }
    // table
    if (line.includes('|') && i + 1 < lines.length && isSep(lines[i + 1])) {
      const head = splitRow(line);
      const aligns = splitRow(lines[i + 1]).map(c => (c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : ''));
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes('|')) { rows.push(splitRow(lines[i])); i++; }
      const al = k => (aligns[k] ? ` style="text-align:${aligns[k]}"` : '');
      const th = head.map((c, k) => `<th${al(k)}>${inline(c, ctx.opt)}</th>`).join('');
      const tb = rows.map(r => `<tr>${head.map((_, k) => `<td${al(k)}>${inline(r[k] || '', ctx.opt)}</td>`).join('')}</tr>`).join('\n');
      out.push(`<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>\n${tb}\n</tbody></table></div>`);
      continue;
    }
    // list
    const lm = listMarker(line);
    if (lm) {
      const baseIndent = lm[1].length;
      const ordered = /\d/.test(lm[2]);
      const start = ordered ? parseInt(lm[2], 10) : 1;
      const items = [];
      let cur = null;
      while (i < lines.length) {
        const l = lines[i];
        const m = listMarker(l);
        if (m && m[1].length === baseIndent && /\d/.test(m[2]) === ordered) {
          cur = { lines: [m[4]], contentIndent: baseIndent + m[2].length + Math.max(1, m[3].length) };
          items.push(cur);
          i++;
          continue;
        }
        if (!l.trim()) {
          // a blank line ends the list unless the next line continues an item
          const nxt = lines[i + 1];
          if (nxt !== undefined && nxt.trim() && (nxt.match(/^\s*/)[0].length > baseIndent)) { cur.lines.push(''); i++; continue; }
          const nm = nxt !== undefined && listMarker(nxt);
          if (nm && nm[1].length === baseIndent && /\d/.test(nm[2]) === ordered) { i++; continue; }
          break;
        }
        const ind = l.match(/^\s*/)[0].length;
        if (ind > baseIndent) { cur.lines.push(l.slice(Math.min(ind, cur.contentIndent))); i++; continue; }
        if (m || startsBlock(l)) break;
        cur.lines.push(l.trim()); // lazy continuation
        i++;
      }
      const lis = items.map(it => {
        const body = renderBlocks(it.lines, ctx);
        // tight list: unwrap a single leading paragraph
        const tight = body.replace(/^<p>([\s\S]*?)<\/p>/, '$1');
        return `<li>${it.lines.includes('') ? body : tight}</li>`;
      }).join('\n');
      out.push(ordered ? `<ol${start !== 1 ? ` start="${start}"` : ''}>\n${lis}\n</ol>` : `<ul>\n${lis}\n</ul>`);
      continue;
    }
    // paragraph
    const para = [];
    while (i < lines.length && lines[i].trim() && !startsBlock(lines[i]) &&
           !(lines[i].includes('|') && i + 1 < lines.length && isSep(lines[i + 1]))) {
      para.push(lines[i]);
      i++;
    }
    if (!para.length) { para.push(lines[i]); i++; }
    const text = para.map((l, k) => (k < para.length - 1 && / {2,}$/.test(l) ? l.trimEnd() + '\u0001' : l.trim())).join('\n');
    out.push(`<p>${inline(text, ctx.opt).replace(/\u0001\n/g, '<br>\n')}</p>`);
  }
  return out.join('\n');
}

// Returns { html, headings: [{level, text, id}], title, frontmatter }.
function render(src, opt = {}) {
  const o = { link: opt.link || (x => x) };
  let text = String(src).replace(/\r\n?/g, '\n');
  let frontmatter = null;
  const fm = /^---\n([\s\S]*?)\n---\n/.exec(text);
  if (fm) { frontmatter = fm[1]; text = text.slice(fm[0].length); }
  const ctx = { opt: o, ids: new Map(), headings: [] };
  const html = renderBlocks(text.split('\n'), ctx);
  const h1 = ctx.headings.find(h => h.level === 1);
  return { html, headings: ctx.headings, title: h1 ? h1.text : null, frontmatter };
}

module.exports = { render, slugBase, plainText, inline: (s, opt = {}) => inline(s, { link: opt.link || (x => x) }), esc };
