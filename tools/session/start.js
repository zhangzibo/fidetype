#!/usr/bin/env node
// Print a short "resume context" block for a new session (or the user).
// Node built-ins only. Never throws; always exits 0.
'use strict';
const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..', '..');
const read = (p) => { try { return fs.readFileSync(path.join(REPO, p), 'utf8'); } catch { return null; } };
const HR = '-'.repeat(60);

try {
  console.log(HR);
  console.log('RESUME CONTEXT');
  console.log('Read HANDOFF.md, CLAUDE.md, agent-memory/MEMORY.md');
  console.log(HR);

  const handoff = read('HANDOFF.md');
  console.log('HANDOFF.md (first 60 lines):');
  console.log(handoff ? handoff.split(/\r?\n/).slice(0, 60).join('\n') : '(HANDOFF.md not found)');
  console.log(HR);

  const log = read(path.join('wiki', 'log.md'));
  console.log('Last 5 entries of wiki/log.md:');
  if (log) {
    const heads = log.split(/\r?\n/).filter((l) => /^## \[/.test(l));
    console.log(heads.slice(-5).join('\n') || '(no entries)');
  } else console.log('(wiki/log.md not found)');
  console.log(HR);
} catch (e) { console.error(`start: ${e && e.message}`); }
process.exit(0);
