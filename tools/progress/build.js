#!/usr/bin/env node
// Builds wiki/progress/index.html from wiki/progress/tracker.json.
// The page is self-contained (no external libraries), so it works offline.
// Usage: node tools/progress/build.js
// Optional: set PROGRESS_NOW=2026-11-08T12:00:00-08:00 to build the page for a different "now".
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const DIR = path.join(ROOT, 'wiki', 'progress');
const SRC = path.join(DIR, 'tracker.json');
const data = JSON.parse(fs.readFileSync(SRC, 'utf8'));

const START_DATE = data.start_date || '2026-11-07';
const FINAL_TARGET = data.final_target || '2026-11-15';
const AXIS_FROM = START_DATE;           // first day column
const AXIS_TO = '2026-11-16';           // last day column (inclusive)

// ---------- helpers ----------
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const pad = n => String(n).padStart(2, '0');
const DAY = 86400000;

// "now" in local wall-clock terms. All tracker times carry a UTC offset; we show wall-clock as recorded.
const nowDate = process.env.PROGRESS_NOW ? new Date(process.env.PROGRESS_NOW) : new Date();
const localIso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const NOW_WALL = process.env.PROGRESS_NOW ? process.env.PROGRESS_NOW.slice(0, 16) : localIso(nowDate);
const TODAY = NOW_WALL.slice(0, 10);

// Day number (UTC-based, so no DST issues) of a "YYYY-MM-DD" string.
const dayNum = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / DAY;
// Fractional day number from wall-clock "YYYY-MM-DDTHH:MM" (offset ignored = wall-clock as recorded).
const wallNum = s => dayNum(s.slice(0, 10)) + (s.length >= 16 ? (+s.slice(11, 13) * 60 + +s.slice(14, 16)) / 1440 : 0);

const fmtHMS = sec => {
  sec = Math.round(sec || 0);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return `${h}:${pad(m)}:${pad(s)}`;
};
const fmtDur = ms => {
  if (ms == null || isNaN(ms)) return '—';
  const min = Math.round(ms / 60000);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), m = min % 60;
  if (h < 48) return `${h} h ${pad(m)} min`;
  return `${(h / 24).toFixed(1)} d`;
};
const fmtNum = n => (n || 0).toLocaleString('en-US');
const fmtTokensShort = n => n >= 1e6 ? (n / 1e6).toFixed(2) + ' M' : n >= 1e3 ? Math.round(n / 1e3) + ' k' : String(n);
const fmtWhen = s => s ? `${s.slice(5, 10)} ${s.slice(11, 16)}` : '—';
const shortDate = s => s.slice(5, 10);

// ---------- aggregate ----------
const runs = t => t.agent_runs || [];
const sum = (arr, f) => arr.reduce((a, x) => a + (f(x) || 0), 0);
const taskAgentS = t => sum(runs(t), r => r.duration_s);
const taskTokens = t => sum(runs(t), r => r.tokens);
const taskTools = t => sum(runs(t), r => r.tool_uses);

const tasks = data.tasks;
const ext = t => t.status === 'externally_blocked';
const countable = tasks.filter(t => !ext(t));
const doneCount = countable.filter(t => t.status === 'done').length;
const extCount = tasks.length - countable.length;
const allRuns = tasks.flatMap(runs);
const totalAgentS = sum(allRuns, r => r.duration_s);
const totalTokens = sum(allRuns, r => r.tokens);
const totalTools = sum(allRuns, r => r.tool_uses);
const daysSince = dayNum(TODAY) - dayNum(START_DATE);
const daysLeft = dayNum(FINAL_TARGET) - dayNum(TODAY);

// A milestone with "no_deadline": true (or no target_end) has no due date. It is never late and has no target bar.
const noDeadline = m => m.no_deadline === true || !m.target_end;

const msInfo = data.milestones.map(m => {
  const mt = tasks.filter(t => t.milestone === m.id);
  const mc = mt.filter(t => !ext(t));
  const md = mc.filter(t => t.status === 'done').length;
  const starts = mt.map(t => t.started_at).filter(Boolean).sort();
  const fins = mt.map(t => t.finished_at).filter(Boolean).sort();
  const allDone = mc.length > 0 && md === mc.length;
  const open = mt.some(t => t.started_at && !t.finished_at);
  let badge;
  if (allDone || (mc.length === 0 && m.status === 'done')) badge = 'done';
  else if (noDeadline(m)) badge = 'nodeadline';
  else if (dayNum(TODAY) > dayNum(m.target_end)) badge = 'late';
  else badge = 'ontrack';
  return {
    m, tasks: mt, total: mc.length, done: md, ext: mt.length - mc.length,
    firstStart: starts[0] || null,
    lastFinish: allDone ? (fins[fins.length - 1] || null) : null,
    lastAny: fins[fins.length - 1] || null,
    open, badge,
    started: starts.length > 0,
    agentS: sum(mt, taskAgentS), tokens: sum(mt, taskTokens), runs: sum(mt, t => runs(t).length),
  };
});

const BADGE = { done: ['Done', 'b-done'], late: ['Late', 'b-late'], ontrack: ['On track', 'b-ontrack'], nodeadline: ['No deadline', 'b-nodl'] };
const STATUS = {
  done: ['Done', 's-done'], in_progress: ['In progress', 's-prog'], todo: ['To do', 's-todo'],
  blocked: ['Blocked', 's-blocked'], externally_blocked: ['Ext. blocked', 's-ext'],
};
const chip = st => { const [l, c] = STATUS[st] || [st, 's-todo']; return `<span class="chip ${c}">${esc(l)}</span>`; };

// ---------- summary cards ----------
const cards = [
  ['Days since start', String(daysSince), `Start: ${START_DATE}`],
  ['Days left to target', String(daysLeft), `Target: ${FINAL_TARGET} (M1–M7)`],
  ['Tasks done', `${doneCount} / ${countable.length}`, `${extCount} externally blocked (not counted)`],
  ['Agent time', fmtHMS(totalAgentS), 'Sum of subagent run durations'],
  ['Tokens', fmtNum(totalTokens), 'Sum of subagent tokens'],
  ['Agent runs', String(allRuns.length), `${fmtNum(totalTools)} tool uses`],
].map(([k, v, s]) => `<div class="card"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div><div class="s">${esc(s)}</div></div>`).join('');

// ---------- milestone rows ----------
const msRows = msInfo.map(i => {
  const pct = i.total ? Math.round(100 * i.done / i.total) : 0;
  const [bl, bc] = BADGE[i.badge];
  const actual = i.firstStart
    ? `${fmtWhen(i.firstStart)} → ${i.lastFinish ? fmtWhen(i.lastFinish) : '<em>open</em>'}`
    : '<span class="muted">Not started</span>';
  return `<div class="ms">
    <div class="ms-head">
      <div class="ms-name"><b>${esc(i.m.id)}</b> ${esc(i.m.name)}</div>
      <span class="badge ${bc}">${bl}</span>
    </div>
    <div class="bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" title="${i.done} of ${i.total} done"><span style="width:${pct}%"></span></div>
    <div class="ms-grid">
      <div><span class="lbl">Done</span>${i.done} / ${i.total}${i.ext ? ` <span class="muted">+${i.ext} ext. blocked</span>` : ''}</div>
      <div><span class="lbl">Target</span>${noDeadline(i.m) ? '<span class="muted">No deadline</span>' : `${shortDate(i.m.target_start)} → ${shortDate(i.m.target_end)}`}</div>
      <div><span class="lbl">Actual</span>${actual}</div>
      <div><span class="lbl">Agent time</span>${fmtHMS(i.agentS)}</div>
      <div><span class="lbl">Tokens</span>${fmtNum(i.tokens)}</div>
    </div>
  </div>`;
}).join('\n');

// ---------- timeline SVG ----------
const d0 = dayNum(AXIS_FROM), d1 = dayNum(AXIS_TO) + 1;
const LABEL_W = 150, DAY_W = 64, ROW_H = 30, TOP = 34, W = LABEL_W + (d1 - d0) * DAY_W + 10;
const H = TOP + msInfo.length * ROW_H + 22;
const xOf = dn => LABEL_W + (Math.min(Math.max(dn, d0), d1) - d0) * DAY_W;
let svg = `<svg class="tl" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Timeline: target window and actual window per milestone">`;
for (let d = d0; d < d1; d++) {
  const x = xOf(d);
  const ds = new Date(d * DAY).toISOString().slice(0, 10);
  const wk = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(d * DAY).getUTCDay()];
  const isTarget = ds === FINAL_TARGET;
  svg += `<line x1="${x}" y1="${TOP - 4}" x2="${x}" y2="${H - 22}" class="grid"/>`;
  svg += `<text x="${x + DAY_W / 2}" y="14" class="ax${isTarget ? ' ax-t' : ''}" text-anchor="middle">${shortDate(ds)}</text>`;
  svg += `<text x="${x + DAY_W / 2}" y="27" class="ax2" text-anchor="middle">${wk}</text>`;
}
svg += `<line x1="${xOf(d1)}" y1="${TOP - 4}" x2="${xOf(d1)}" y2="${H - 22}" class="grid"/>`;
// final target line (end of 11-15)
const xt = xOf(dayNum(FINAL_TARGET) + 1);
svg += `<line x1="${xt}" y1="${TOP - 4}" x2="${xt}" y2="${H - 22}" class="tgtline"/>`;
msInfo.forEach((i, k) => {
  const y = TOP + k * ROW_H;
  if (k % 2 === 0) svg += `<rect x="0" y="${y}" width="${W}" height="${ROW_H}" class="zebra"/>`;
  svg += `<text x="6" y="${y + ROW_H / 2 + 4}" class="rl"><tspan font-weight="700">${esc(i.m.id)}</tspan> ${esc(i.m.name.length > 16 ? i.m.name.slice(0, 15) + '…' : i.m.name)}</text>`;
  if (!noDeadline(i.m)) {
    const tx0 = xOf(dayNum(i.m.target_start)), tx1 = xOf(dayNum(i.m.target_end) + 1);
    svg += `<rect x="${tx0 + 1}" y="${y + 5}" width="${Math.max(tx1 - tx0 - 2, 2)}" height="${ROW_H - 10}" rx="4" class="tbar"><title>${esc(i.m.id)} target: ${i.m.target_start} → ${i.m.target_end}</title></rect>`;
  } else {
    svg += `<text x="${LABEL_W + 6}" y="${y + ROW_H / 2 + 4}" class="ax2">No deadline (outside timelines)</text>`;
  }
  if (i.firstStart) {
    const a0 = wallNum(i.firstStart);
    const endWall = i.lastFinish || NOW_WALL;
    let a1 = wallNum(endWall);
    if (!i.lastFinish && i.lastAny && wallNum(i.lastAny) > a1) a1 = wallNum(i.lastAny);
    const ax0 = xOf(a0), ax1 = Math.max(xOf(a1), ax0 + 6);
    svg += `<rect x="${ax0}" y="${y + 10}" width="${ax1 - ax0}" height="${ROW_H - 20}" rx="3" class="abar${i.lastFinish ? '' : ' abar-open'}"><title>${esc(i.m.id)} actual: ${fmtWhen(i.firstStart)} → ${i.lastFinish ? fmtWhen(i.lastFinish) : 'open (now ' + fmtWhen(NOW_WALL) + ')'}</title></rect>`;
  }
});
const xn = xOf(wallNum(NOW_WALL));
svg += `<line x1="${xn}" y1="${TOP - 4}" x2="${xn}" y2="${H - 18}" class="today"/>`;
svg += `<text x="${xn + 3}" y="${H - 6}" class="today-t">Today ${fmtWhen(NOW_WALL)}</text>`;
svg += `<text x="${xt - 3}" y="${H - 6}" class="tgt-t" text-anchor="end">Target end</text>`;
svg += `</svg>`;

// ---------- task table ----------
const taskRows = msInfo.map(i => {
  const head = `<tr class="grp"><th colspan="10">${esc(i.m.id)} · ${esc(i.m.name)} <span class="muted">(${i.done}/${i.total} done${i.ext ? `, ${i.ext} ext. blocked` : ''})</span></th></tr>`;
  const rows = i.tasks.map(t => {
    const approx = t.approx_times ? ' <span class="approx" title="Approximate time">≈</span>' : '';
    let elapsed = '—';
    if (t.started_at) {
      const endMs = t.finished_at ? Date.parse(t.finished_at) : nowDate.getTime();
      elapsed = fmtDur(endMs - Date.parse(t.started_at)) + (t.finished_at ? '' : ' (open)');
    }
    const nr = runs(t).length;
    const agent = t.orchestrator_only ? '<span class="muted">Orchestrator only</span>' : nr ? fmtHMS(taskAgentS(t)) + (nr > 1 ? ` <span class="muted">(${nr} runs)</span>` : '') : '—';
    const runLabels = runs(t).map(r => r.label).filter(Boolean).join('; ');
    const notes = [t.notes, runLabels ? `Runs: ${runLabels}` : ''].filter(Boolean).join(' ');
    return `<tr class="${ext(t) ? 'is-ext' : ''}">
      <td data-l="ID"><span><code>${esc(t.id)}</code></span></td>
      <td data-l="Task" class="title"><span>${esc(t.title)}</span></td>
      <td data-l="Status"><span>${chip(t.status)}</span></td>
      <td data-l="Start" class="num"><span>${fmtWhen(t.started_at)}${t.started_at ? approx : ''}</span></td>
      <td data-l="Finish" class="num"><span>${fmtWhen(t.finished_at)}${t.finished_at ? approx : ''}</span></td>
      <td data-l="Elapsed" class="num"><span>${elapsed}</span></td>
      <td data-l="Agent time" class="num"><span>${agent}</span></td>
      <td data-l="Tokens" class="num"><span>${nr ? fmtNum(taskTokens(t)) : '—'}</span></td>
      <td data-l="Tools" class="num"><span>${nr ? taskTools(t) : '—'}</span></td>
      <td data-l="Notes" class="notes"><span>${esc(notes)}</span></td>
    </tr>`;
  }).join('');
  return head + rows;
}).join('\n');

// ---------- page ----------
const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project progress</title>
<style>
  :root { color-scheme: light; --bg:#f7f7f5; --card:#ffffff; --fg:#1d1d1f; --muted:#5f6368; --line:#e3e3e0; --zebra:#f6f6f3;
    --accent:#2a78d6; --tbar:#cde2fb; --tbar-line:#86b6ef; --abar:#1c5cab; --today:#d03b3b; --tgt:#7a6a00;
    --good:#0a7d0a; --good-bg:#e3f4e3; --prog:#1c5cab; --prog-bg:#e3eefc; --todo:#5f6368; --todo-bg:#efefec;
    --bad:#b52f2f; --bad-bg:#fbe5e5; --ext:#8a5a00; --ext-bg:#fff3d6; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark; --bg:#16171a; --card:#1f2024; --fg:#ececec; --muted:#a0a4ab; --line:#33353b; --zebra:#232429;
    --accent:#86b6ef; --tbar:#1f3557; --tbar-line:#3e6aa8; --abar:#5598e7; --today:#e66767; --tgt:#d9c25a;
    --good:#7fd67f; --good-bg:#183a1c; --prog:#9ec5f4; --prog-bg:#1b2f4d; --todo:#b9bcc2; --todo-bg:#2b2d33;
    --bad:#ff9a9a; --bad-bg:#4a1f1f; --ext:#f5c661; --ext-bg:#3d3015; } }
  :root[data-theme="dark"] { color-scheme: dark; --bg:#16171a; --card:#1f2024; --fg:#ececec; --muted:#a0a4ab; --line:#33353b; --zebra:#232429;
    --accent:#86b6ef; --tbar:#1f3557; --tbar-line:#3e6aa8; --abar:#5598e7; --today:#e66767; --tgt:#d9c25a;
    --good:#7fd67f; --good-bg:#183a1c; --prog:#9ec5f4; --prog-bg:#1b2f4d; --todo:#b9bcc2; --todo-bg:#2b2d33;
    --bad:#ff9a9a; --bad-bg:#4a1f1f; --ext:#f5c661; --ext-bg:#3d3015; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  .wrap { max-width:1150px; margin:0 auto; padding:28px 16px 48px; }
  h1 { margin:0 0 4px; font-size:26px; }
  h2 { margin:32px 0 10px; font-size:19px; }
  .sub, .muted { color:var(--muted); }
  .sub { margin:0 0 4px; }
  .note { margin:0 0 18px; font-size:14px; color:var(--muted); max-width:90ch; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
  .card .k { font-size:13px; color:var(--muted); }
  .card .v { font-size:26px; font-weight:650; font-variant-numeric:tabular-nums; margin:2px 0; }
  .card .s { font-size:12px; color:var(--muted); }
  .mss { display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:12px; }
  .ms { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
  .ms-head { display:flex; justify-content:space-between; align-items:center; gap:8px; }
  .ms-name { font-size:15px; }
  .bar { height:8px; background:var(--todo-bg); border-radius:4px; margin:8px 0 10px; overflow:hidden; }
  .bar span { display:block; height:100%; background:var(--accent); border-radius:4px; }
  .ms-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px 14px; font-size:13px; font-variant-numeric:tabular-nums; }
  .ms-grid .lbl { display:block; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }
  .badge { font-size:12px; font-weight:600; padding:2px 9px; border-radius:999px; white-space:nowrap; }
  .badge::before { margin-right:4px; }
  .b-done { color:var(--good); background:var(--good-bg); } .b-done::before { content:"✓"; }
  .b-late { color:var(--bad); background:var(--bad-bg); } .b-late::before { content:"!"; }
  .b-ontrack { color:var(--prog); background:var(--prog-bg); } .b-ontrack::before { content:"→"; }
  .b-nodl { color:var(--todo); background:var(--todo-bg); border:1px dashed var(--todo); } .b-nodl::before { content:"∞"; }
  .tl-box { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; overflow-x:auto; }
  .tl { display:block; max-width:none; }
  .tl .grid { stroke:var(--line); stroke-width:1; }
  .tl .zebra { fill:var(--zebra); }
  .tl .ax { fill:var(--fg); font-size:12px; font-weight:600; }
  .tl .ax-t { fill:var(--tgt); }
  .tl .ax2 { fill:var(--muted); font-size:11px; }
  .tl .rl { fill:var(--fg); font-size:12px; }
  .tl .tbar { fill:var(--tbar); stroke:var(--tbar-line); stroke-width:1; }
  .tl .abar { fill:var(--abar); }
  .tl .abar-open { opacity:.75; }
  .tl .today { stroke:var(--today); stroke-width:2; }
  .tl .today-t { fill:var(--today); font-size:11px; font-weight:600; }
  .tl .tgtline { stroke:var(--tgt); stroke-width:2; stroke-dasharray:5 3; }
  .tl .tgt-t { fill:var(--tgt); font-size:11px; font-weight:600; }
  .legend { display:flex; flex-wrap:wrap; gap:14px; font-size:13px; color:var(--muted); margin:8px 2px 0; }
  .legend i { display:inline-block; width:22px; height:10px; border-radius:3px; vertical-align:middle; margin-right:5px; }
  .lg-t { background:var(--tbar); border:1px solid var(--tbar-line); } .lg-a { background:var(--abar); }
  .lg-n { width:3px !important; height:14px !important; background:var(--today); border-radius:0 !important; }
  .lg-g { width:14px !important; height:0 !important; border-top:2px dashed var(--tgt); border-radius:0 !important; }
  table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; font-size:13px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
  thead th { font-size:12px; color:var(--muted); font-weight:600; background:var(--zebra); }
  tr.grp th { background:var(--zebra); font-size:14px; padding-top:10px; }
  td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
  td.title { min-width:220px; }
  td.notes { color:var(--muted); font-size:12px; min-width:160px; }
  tr.is-ext td { background:color-mix(in srgb, var(--ext-bg) 35%, transparent); }
  code { font-size:12px; white-space:nowrap; }
  .chip { display:inline-block; font-size:11.5px; font-weight:600; padding:1px 8px; border-radius:999px; white-space:nowrap; }
  .s-done { color:var(--good); background:var(--good-bg); }
  .s-prog { color:var(--prog); background:var(--prog-bg); }
  .s-todo { color:var(--todo); background:var(--todo-bg); }
  .s-blocked { color:var(--bad); background:var(--bad-bg); }
  .s-ext { color:var(--ext); background:var(--ext-bg); border:1px dashed var(--ext); }
  .approx { color:var(--muted); cursor:help; }
  footer { margin-top:28px; font-size:13px; color:var(--muted); border-top:1px solid var(--line); padding-top:12px; }
  @media (max-width: 760px) {
    .cards { grid-template-columns:1fr 1fr; gap:8px; }
    .card .v { font-size:22px; }
    .mss { grid-template-columns:1fr; }
    table, thead, tbody, tr, th, td { display:block; }
    thead { display:none; }
    table { border-radius:10px; }
    tr { border-bottom:1px solid var(--line); padding:6px 0; }
    tr.grp th { border-bottom:none; }
    td { border:none; padding:2px 10px; display:grid; grid-template-columns:96px 1fr; gap:8px; }
    td::before { content:attr(data-l); color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.03em; padding-top:2px; }
    td.title, td.notes { min-width:0; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>Project progress</h1>
  <p class="sub">Actual effort and dates against the targets. Built ${esc(fmtWhen(NOW_WALL))} (${esc(TODAY)}). Tracker updated ${esc(String(data.updated).slice(0, 16).replace('T', ' '))}.</p>
  <p class="note">${esc(data.target_note)}</p>

  <div class="cards">${cards}</div>

  <h2>Milestones</h2>
  <div class="mss">
${msRows}
  </div>

  <h2>Timeline</h2>
  <div class="tl-box">${svg}</div>
  <div class="legend"><span><i class="lg-t"></i>Target window</span><span><i class="lg-a"></i>Actual window (lighter = still open)</span><span><i class="lg-n"></i>Today</span><span><i class="lg-g"></i>Target end (${esc(FINAL_TARGET)})</span></div>

  <h2>Tasks</h2>
  <p class="note">≈ = approximate time. Elapsed = wall-clock time from start to finish. Agent time = sum of subagent run durations. Externally blocked tasks depend on outside people. They do not count as late and are not in the "done" total. Milestones marked "No deadline" (for example PUB, publications) have no due date, never count as late and are not part of the ${esc(FINAL_TARGET)} target.</p>
  <table>
    <thead><tr><th>ID</th><th>Task</th><th>Status</th><th>Start</th><th>Finish</th><th>Elapsed</th><th>Agent time</th><th>Tokens</th><th>Tools</th><th>Notes</th></tr></thead>
    <tbody>
${taskRows}
    </tbody>
  </table>

  <footer>Source: wiki/progress/tracker.json. Rebuild: node tools/progress/build.js</footer>
</div>
</body>
</html>
`;

fs.writeFileSync(path.join(DIR, 'index.html'), html);
console.log(`Built wiki/progress/index.html: ${doneCount}/${countable.length} tasks done, ${extCount} externally blocked, ${allRuns.length} agent runs, ${fmtHMS(totalAgentS)} agent time, ${fmtNum(totalTokens)} tokens, ${totalTools} tool uses.`);
