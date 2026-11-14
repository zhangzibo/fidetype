// Merges tracker fragments (wiki/progress/fragments/<task-id>.json) into tracker.json.
//
// Why: several agents edit tracker.json at the same time and their text edits clash.
// Each agent writes its own fragment file instead; `node tools/progress/build.js`
// merges all fragments, then moves them to fragments/archive/<date>/.
//
// Rules (see tools/progress/README.md):
// - Fragment = one JSON object: {"id": "<task id>", <task fields...>, "agent_runs": [...]}.
//   Keys that start with "_" are meta: "_tracker_updated" bumps the tracker's "updated" time.
// - The fragment wins on every task field it sets. Fields it does not set stay as they are.
// - Agent runs are deduplicated by run key = run_key || label. A run with a known key replaces
//   the old run (this fills a null placeholder with the same label); a new key is appended.
// - A new task id needs "milestone" (an existing milestone) and "title".
// - Fragments are applied in file-name order. The result is the same each time (idempotent).
// - Only the touched task objects (and "updated") change in the tracker text. The rest of the
//   hand-formatted file stays byte for byte. The merge parses the new text and checks that it
//   equals the expected object before it writes anything.
'use strict';
const fs = require('fs');
const path = require('path');

const STATUSES = ['done', 'in_progress', 'todo', 'blocked', 'externally_blocked'];
const TASK_DEFAULTS = { status: 'todo', started_at: null, finished_at: null, approx_times: false, agent_runs: [], orchestrator_only: false, notes: '' };
const FIELD_ORDER = ['id', 'milestone', 'title', 'status', 'started_at', 'finished_at', 'approx_times', 'agent_runs', 'orchestrator_only', 'notes'];

const runKey = r => (r && (r.run_key || r.label)) || JSON.stringify(r);

// ---------- scanner: offsets of the top-level "updated" value and of each element of "tasks" ----------
function scan(text) {
  const out = { updated: null, elements: [] };
  let depth = 0, key = null, expectKey = false, inTasks = false, elemStart = -1;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      const s = i;
      for (i++; text[i] !== '"'; i++) if (text[i] === '\\') i++;
      if (depth === 1) {
        if (expectKey) key = JSON.parse(text.slice(s, i + 1));
        else if (key === 'updated') out.updated = [s, i + 1];
      }
    } else if (c === '{' || c === '[') {
      if (depth === 1 && c === '[' && key === 'tasks') inTasks = true;
      if (inTasks && depth === 2 && c === '{') elemStart = i;
      depth++;
      if (depth === 1) expectKey = true;
    } else if (c === '}' || c === ']') {
      depth--;
      if (inTasks && depth === 2 && c === '}') out.elements.push([elemStart, i + 1]);
      if (inTasks && depth === 1 && c === ']') inTasks = false;
    } else if (c === ':' && depth === 1) {
      expectKey = false;
    } else if (c === ',' && depth === 1) {
      expectKey = true; key = null;
    }
  }
  return out;
}

// ---------- serializer in the tracker's house style ----------
const J = v => JSON.stringify(v);
const objLine = o => '{' + Object.keys(o).map(k => `${J(k)}: ${J(o[k])}`).join(', ') + '}';
function serializeTask(t) {
  const keys = Object.keys(t);
  const ordered = FIELD_ORDER.filter(k => keys.includes(k)).concat(keys.filter(k => !FIELD_ORDER.includes(k)).sort());
  const kv = k => `${J(k)}: ${J(t[k])}`;
  const has = k => ordered.includes(k);
  const line1 = ['id', 'milestone', 'title', 'status'].filter(has).map(kv).join(', ');
  const line2 = ['started_at', 'finished_at', 'approx_times'].filter(has).map(kv).join(', ');
  const runs = t.agent_runs || [];
  const runsTxt = has('agent_runs') ? `"agent_runs": [${runs.map(objLine).join(',\n                    ')}]` : '';
  const rest = ordered.filter(k => !['id', 'milestone', 'title', 'status', 'started_at', 'finished_at', 'approx_times', 'agent_runs', 'notes'].includes(k));
  const line4 = rest.concat(has('notes') ? ['notes'] : []).map(kv).join(', ');
  const lines = [line1, line2, runsTxt, line4].filter(Boolean);
  return '    {' + lines.join(',\n     ') + '}';
}

// Canonical form for the equality check (key order ignored).
const canon = v => Array.isArray(v) ? v.map(canon)
  : v && typeof v === 'object' ? Object.keys(v).sort().reduce((o, k) => (o[k] = canon(v[k]), o), {}) : v;
const same = (a, b) => JSON.stringify(canon(a)) === JSON.stringify(canon(b));

function validate(frag, file, milestones) {
  const err = m => { throw new Error(`fragment ${file}: ${m}`); };
  if (!frag || typeof frag !== 'object' || Array.isArray(frag)) err('must be a JSON object');
  if (typeof frag.id !== 'string' || !frag.id) err('needs a string "id"');
  if (frag.status !== undefined && !STATUSES.includes(frag.status)) err(`bad status "${frag.status}" (use ${STATUSES.join(', ')})`);
  if (frag.milestone !== undefined && !milestones.has(frag.milestone)) err(`unknown milestone "${frag.milestone}"`);
  if (frag.agent_runs !== undefined) {
    if (!Array.isArray(frag.agent_runs)) err('"agent_runs" must be a list');
    frag.agent_runs.forEach((r, k) => { if (!r || typeof r !== 'object' || !(r.run_key || r.label)) err(`agent_runs[${k}] needs "label" or "run_key"`); });
  }
  for (const k of ['started_at', 'finished_at', '_tracker_updated']) {
    if (frag[k] != null && (typeof frag[k] !== 'string' || isNaN(Date.parse(frag[k])))) err(`"${k}" must be an ISO time with offset or null`);
  }
}

// Apply fragments to a parsed tracker object (in place). Returns the set of touched task ids.
function applyFragments(data, frags) {
  const milestones = new Set(data.milestones.map(m => m.id));
  const touched = new Set();
  const created = [];
  for (const { file, frag } of frags) {
    validate(frag, file, milestones);
    let task = data.tasks.find(t => t.id === frag.id);
    if (!task) {
      if (!frag.milestone || !frag.title) throw new Error(`fragment ${file}: new task "${frag.id}" needs "milestone" and "title"`);
      task = { id: frag.id, milestone: frag.milestone, title: frag.title, ...JSON.parse(JSON.stringify(TASK_DEFAULTS)) };
      data.tasks.push(task);
      created.push(frag.id);
    }
    for (const [k, v] of Object.entries(frag)) {
      if (k === 'id' || k === 'agent_runs' || k.startsWith('_')) continue;
      task[k] = v;
    }
    if (frag.agent_runs) {
      task.agent_runs = task.agent_runs || [];
      for (const r of frag.agent_runs) {
        const idx = task.agent_runs.findIndex(x => runKey(x) === runKey(r));
        if (idx >= 0) task.agent_runs[idx] = { ...task.agent_runs[idx], ...r };
        else task.agent_runs.push({ ...r });
      }
    }
    if (frag._tracker_updated && (!data.updated || Date.parse(frag._tracker_updated) > Date.parse(data.updated))) data.updated = frag._tracker_updated;
    touched.add(frag.id);
  }
  return { touched, created };
}

// Build the new tracker text from the old text + the merged object, touching only changed spans.
function rewrite(text, before, after, touched) {
  const sc = scan(text);
  const ids = sc.elements.map(([s, e]) => JSON.parse(text.slice(s, e)).id);
  if (new Set(ids).size !== ids.length) throw new Error('tracker.json has duplicate task ids');
  if (ids.length !== before.tasks.length) throw new Error('scanner found a different task count than JSON.parse');
  const edits = []; // [start, end, replacement]
  sc.elements.forEach(([s, e], k) => {
    const id = ids[k];
    if (!touched.has(id)) return;
    const t = after.tasks.find(x => x.id === id);
    const old = before.tasks.find(x => x.id === id);
    if (!same(t, old)) edits.push([s, e, serializeTask(t).replace(/^ {4}/, '')]);
  });
  // New tasks: after the last task of the same milestone, else after the last task.
  const newTasks = after.tasks.filter(t => !ids.includes(t.id));
  const inserts = new Map();
  for (const t of newTasks) {
    let k = -1;
    ids.forEach((id, j) => { if (before.tasks[j].milestone === t.milestone) k = j; });
    if (k < 0) k = ids.length - 1;
    const at = sc.elements[k][1];
    inserts.set(at, (inserts.get(at) || '') + ',\n' + serializeTask(t));
  }
  for (const [at, txt] of inserts) edits.push([at, at, txt]);
  if (after.updated !== before.updated) {
    if (!sc.updated) throw new Error('tracker.json has no top-level "updated" string');
    edits.push([sc.updated[0], sc.updated[1], J(after.updated)]);
  }
  edits.sort((a, b) => b[0] - a[0] || b[1] - a[1]);
  let out = text;
  for (const [s, e, r] of edits) out = out.slice(0, s) + r + out.slice(e);
  // Order of tasks in the merged object = order in the new text (new tasks were pushed at the end).
  const parsed = JSON.parse(out);
  const byId = new Map(after.tasks.map(t => [t.id, t]));
  const expected = { ...after, tasks: parsed.tasks.map(t => byId.get(t.id)) };
  if (parsed.tasks.length !== after.tasks.length || !same(parsed, expected)) throw new Error('self-check failed: rewritten tracker text does not equal the merged object');
  return out;
}

function withLock(lockPath, fn) {
  const t0 = Date.now();
  let fd;
  for (;;) {
    try { fd = fs.openSync(lockPath, 'wx'); break; } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      let age = 0;
      try { age = Date.now() - fs.statSync(lockPath).mtimeMs; } catch { continue; }
      if (age > 60000) { try { fs.unlinkSync(lockPath); } catch { /* another process took it */ } continue; }
      if (Date.now() - t0 > 30000) throw new Error(`tracker merge lock is busy: ${lockPath}`);
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 200);
    }
  }
  try { fs.writeSync(fd, String(process.pid)); return fn(); } finally { fs.closeSync(fd); try { fs.unlinkSync(lockPath); } catch { /* gone */ } }
}

// Merge all fragments in fragDir into trackerPath. Options: archive (default true), dryRun.
function mergeFragments({ trackerPath, fragDir, archive = true, dryRun = false, today } = {}) {
  if (!fs.existsSync(fragDir)) return { merged: [], created: [], changed: false };
  const files = fs.readdirSync(fragDir).filter(f => f.endsWith('.json')).sort();
  if (!files.length) return { merged: [], created: [], changed: false };
  return withLock(path.join(fragDir, '.merge.lock'), () => {
    const text = fs.readFileSync(trackerPath, 'utf8');
    const before = JSON.parse(text);
    const after = JSON.parse(text);
    const frags = files.map(f => {
      try { return { file: f, frag: JSON.parse(fs.readFileSync(path.join(fragDir, f), 'utf8')) }; } catch (e) { throw new Error(`fragment ${f}: not valid JSON (${e.message})`); }
    });
    const { touched, created } = applyFragments(after, frags);
    const out = rewrite(text, before, after, touched);
    const changed = out !== text;
    if (!dryRun) {
      if (changed) {
        const tmp = trackerPath + '.tmp';
        fs.writeFileSync(tmp, out);
        fs.renameSync(tmp, trackerPath);
      }
      const d = new Date(), pad = n => String(n).padStart(2, '0');
      const day = today || `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; // local date
      const arch = path.join(fragDir, 'archive', day);
      for (const f of files) {
        const src = path.join(fragDir, f);
        if (!archive) { fs.unlinkSync(src); continue; }
        fs.mkdirSync(arch, { recursive: true });
        let dst = path.join(arch, f), n = 1;
        while (fs.existsSync(dst)) dst = path.join(arch, f.replace(/\.json$/, `.${++n}.json`));
        fs.renameSync(src, dst);
      }
    }
    return { merged: files, created, changed, text: out };
  });
}

module.exports = { mergeFragments, applyFragments, rewrite, serializeTask, scan, runKey };

if (require.main === module) {
  // node tools/progress/fragments.js [--dry-run]   (merge only; build.js also merges)
  const ROOT = path.resolve(__dirname, '..', '..');
  const r = mergeFragments({
    trackerPath: path.join(ROOT, 'wiki', 'progress', 'tracker.json'),
    fragDir: path.join(ROOT, 'wiki', 'progress', 'fragments'),
    dryRun: process.argv.includes('--dry-run'),
  });
  console.log(r.merged.length ? `Merged ${r.merged.length} fragment(s): ${r.merged.join(', ')}${r.created.length ? ` (new tasks: ${r.created.join(', ')})` : ''}${r.changed ? '' : ' (no change)'}` : 'No fragments to merge.');
}
