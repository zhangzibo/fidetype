#!/usr/bin/env node
// Self-check for tools/progress/fragments.js. Usage: node tools/progress/test-fragments.js
// Works on temporary copies only; it never changes the real tracker.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert');
const { mergeFragments, serializeTask, scan } = require('./fragments');

const ROOT = path.resolve(__dirname, '..', '..');
const REAL = path.join(ROOT, 'wiki', 'progress', 'tracker.json');
let n = 0;
const test = (name, fn) => { fn(); n++; console.log(`ok ${n} - ${name}`); };

const SMALL = `{
  "updated": "2026-11-13T10:00:00-08:00",
  "milestones": [
    {"id": "M0", "name": "Setup", "target_start": "2026-11-08", "target_end": "2026-11-09", "status": "done"},
    {"id": "M1", "name": "Decoder", "target_start": "2026-11-09", "target_end": "2026-11-11", "status": "done"}
  ],
  "tasks": [
    {"id": "M0-01", "milestone": "M0", "title": "A \\"quoted\\" {brace} [x]", "status": "done",
     "started_at": "2026-11-08T00:00:00-08:00", "finished_at": "2026-11-08T01:00:00-08:00", "approx_times": false,
     "agent_runs": [{"label": "run a", "duration_s": 10, "tokens": 100, "tool_uses": 1}],
     "orchestrator_only": false, "notes": "keep me"},

    {"id": "M0-02", "milestone": "M0", "title": "Second", "status": "in_progress",
     "started_at": "2026-11-08T02:00:00-08:00", "finished_at": null, "approx_times": false,
     "agent_runs": [{"label": "work", "duration_s": null, "tokens": null, "tool_uses": null}],
     "orchestrator_only": false, "notes": ""},
    {"id": "M1-01", "milestone": "M1", "title": "Third", "status": "todo", "started_at": null, "finished_at": null, "approx_times": false, "agent_runs": [], "orchestrator_only": false, "notes": ""}
  ]
}
`;

function sandbox(trackerText) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fidetype-frag-'));
  const trackerPath = path.join(dir, 'tracker.json');
  const fragDir = path.join(dir, 'fragments');
  fs.mkdirSync(fragDir);
  fs.writeFileSync(trackerPath, trackerText);
  const put = (name, obj) => fs.writeFileSync(path.join(fragDir, name), typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2));
  const merge = () => mergeFragments({ trackerPath, fragDir, today: '2026-11-13' });
  const read = () => fs.readFileSync(trackerPath, 'utf8');
  return { dir, trackerPath, fragDir, put, merge, read };
}

test('scanner finds every task of the real tracker', () => {
  const t = fs.readFileSync(REAL, 'utf8');
  assert.strictEqual(scan(t).elements.length, JSON.parse(t).tasks.length);
});

test('serializer round-trips every task of the real tracker', () => {
  const t = fs.readFileSync(REAL, 'utf8');
  for (const task of JSON.parse(t).tasks) assert.deepStrictEqual(JSON.parse(serializeTask(task)), task);
});

test('update fills a placeholder run, keeps other bytes, archives the fragment', () => {
  const s = sandbox(SMALL);
  s.put('M0-02.json', { id: 'M0-02', status: 'done', finished_at: '2026-11-08T03:00:00-08:00',
    agent_runs: [{ label: 'work', duration_s: 60, tokens: 5000, tool_uses: 7 }] });
  const r = s.merge();
  assert.deepStrictEqual(r.merged, ['M0-02.json']);
  const out = s.read(), d = JSON.parse(out);
  const t = d.tasks.find(x => x.id === 'M0-02');
  assert.strictEqual(t.status, 'done');
  assert.strictEqual(t.agent_runs.length, 1);
  assert.strictEqual(t.agent_runs[0].duration_s, 60);
  assert.strictEqual(t.started_at, '2026-11-08T02:00:00-08:00'); // field not in the fragment stays
  // Untouched tasks keep their exact text.
  assert.ok(out.includes('{"id": "M1-01", "milestone": "M1", "title": "Third", "status": "todo", "started_at": null'));
  assert.ok(out.startsWith(SMALL.slice(0, SMALL.indexOf('{"id": "M0-02"'))));
  assert.deepStrictEqual(fs.readdirSync(s.fragDir).filter(f => f.endsWith('.json')), []);
  assert.ok(fs.existsSync(path.join(s.fragDir, 'archive', '2026-11-13', 'M0-02.json')));
});

test('same fragment twice gives the same text (idempotent); no fragments = no change', () => {
  const s = sandbox(SMALL);
  const frag = { id: 'M0-01', notes: 'new note', agent_runs: [{ run_key: 'agent-x', label: 'x', duration_s: 5, tokens: 9, tool_uses: 1 }] };
  s.put('M0-01.json', frag); s.merge(); const once = s.read();
  s.put('M0-01.json', frag); s.merge(); assert.strictEqual(s.read(), once);
  const r = s.merge(); assert.strictEqual(r.changed, false); assert.strictEqual(s.read(), once);
  assert.strictEqual(JSON.parse(once).tasks[0].agent_runs.length, 2);
  assert.ok(fs.existsSync(path.join(s.fragDir, 'archive', '2026-11-13', 'M0-01.2.json')));
});

test('runs are deduplicated by run_key; the fragment wins', () => {
  const s = sandbox(SMALL);
  s.put('a.json', { id: 'M1-01', agent_runs: [{ run_key: 'k1', label: 'first', duration_s: 1, tokens: 1, tool_uses: 1 }] });
  s.put('b.json', { id: 'M1-01', agent_runs: [{ run_key: 'k1', label: 'first (final)', duration_s: 2, tokens: 2, tool_uses: 2 }] });
  s.merge();
  const runs = JSON.parse(s.read()).tasks.find(x => x.id === 'M1-01').agent_runs;
  assert.deepStrictEqual(runs, [{ run_key: 'k1', label: 'first (final)', duration_s: 2, tokens: 2, tool_uses: 2 }]);
});

test('new task goes after the last task of its milestone, with defaults', () => {
  const s = sandbox(SMALL);
  s.put('M0-03.json', { id: 'M0-03', milestone: 'M0', title: 'New', status: 'in_progress', started_at: '2026-11-13T09:00:00-08:00' });
  const r = s.merge();
  assert.deepStrictEqual(r.created, ['M0-03']);
  const d = JSON.parse(s.read());
  assert.deepStrictEqual(d.tasks.map(t => t.id), ['M0-01', 'M0-02', 'M0-03', 'M1-01']);
  const t = d.tasks[2];
  assert.strictEqual(t.finished_at, null); assert.deepStrictEqual(t.agent_runs, []); assert.strictEqual(t.notes, '');
});

test('_tracker_updated only moves "updated" forward', () => {
  const s = sandbox(SMALL);
  s.put('a.json', { id: 'M1-01', _tracker_updated: '2026-11-13T09:00:00-08:00' });
  s.merge(); assert.strictEqual(JSON.parse(s.read()).updated, '2026-11-13T10:00:00-08:00');
  s.put('a.json', { id: 'M1-01', _tracker_updated: '2026-11-13T11:30:00-08:00' });
  s.merge(); assert.strictEqual(JSON.parse(s.read()).updated, '2026-11-13T11:30:00-08:00');
});

test('a bad fragment fails clearly and changes nothing', () => {
  for (const [bad, msg] of [
    [{ id: 'M1-01', status: 'finished' }, /bad status/],
    [{ id: 'M9-01', title: 'x', milestone: 'M9' }, /unknown milestone/],
    [{ id: 'M0-09', status: 'todo' }, /needs "milestone" and "title"/],
    [{ id: 'M1-01', agent_runs: [{ duration_s: 3 }] }, /needs "label" or "run_key"/],
    ['{ not json', /not valid JSON/],
  ]) {
    const s = sandbox(SMALL);
    s.put('x.json', bad);
    assert.throws(() => s.merge(), msg);
    assert.strictEqual(s.read(), SMALL);
    assert.ok(fs.existsSync(path.join(s.fragDir, 'x.json')));
    assert.ok(!fs.existsSync(path.join(s.fragDir, '.merge.lock')));
  }
});

test('merge into a copy of the real tracker touches only the fragment task', () => {
  const real = fs.readFileSync(REAL, 'utf8');
  const s = sandbox(real);
  const d0 = JSON.parse(real);
  const id = d0.tasks[d0.tasks.length - 1].id;
  s.put(`${id}.json`, { id, notes: 'changed by test' });
  s.merge();
  const d1 = JSON.parse(s.read());
  assert.strictEqual(d1.tasks.length, d0.tasks.length);
  d0.tasks[d0.tasks.length - 1].notes = 'changed by test';
  assert.deepStrictEqual(d1, d0);
});

console.log(`All ${n} fragment checks passed.`);
