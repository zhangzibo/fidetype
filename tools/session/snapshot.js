#!/usr/bin/env node
// Mirror Claude Code's memory notes (*.md) into the repo at agent-memory/.
// Source of truth stays in ~/.claude/projects/<slug>/memory/. Node built-ins only.
// Never throws; always exits 0. Does not commit.
'use strict';

// Memory files to NOT mirror (repo is public). Add a file name here if a note
// holds secrets, tokens, email addresses or other personal data.
const EXCLUDE = [];

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const SLUG = 'C--Users-zhang-OneDrive-Documents-GitHub-stealth-project';
const REPO = path.resolve(__dirname, '..', '..');
const SRC = path.join(os.homedir(), '.claude', 'projects', SLUG, 'memory');
const DST = path.join(REPO, 'agent-memory');

function main() {
  let copied = 0, unchanged = 0, removed = 0, excluded = 0, errors = 0;
  let progress = 'skipped';

  if (!fs.existsSync(SRC)) {
    console.log(`snapshot: memory folder not found (${SRC}); nothing mirrored.`);
  } else {
    fs.mkdirSync(DST, { recursive: true });
    const srcFiles = fs.readdirSync(SRC).filter((f) => f.toLowerCase().endsWith('.md'));
    const keep = new Set();
    for (const f of srcFiles) {
      if (EXCLUDE.includes(f)) { excluded++; continue; }
      keep.add(f);
      try {
        const data = fs.readFileSync(path.join(SRC, f));
        const out = path.join(DST, f);
        if (fs.existsSync(out) && fs.readFileSync(out).equals(data)) { unchanged++; continue; }
        fs.writeFileSync(out, data);
        copied++;
      } catch (e) { errors++; console.error(`snapshot: cannot copy ${f}: ${e.message}`); }
    }
    // Mirror deletions (and new exclusions), .md files only.
    for (const f of fs.readdirSync(DST)) {
      if (!f.toLowerCase().endsWith('.md') || keep.has(f)) continue;
      try { fs.unlinkSync(path.join(DST, f)); removed++; }
      catch (e) { errors++; console.error(`snapshot: cannot remove ${f}: ${e.message}`); }
    }
  }

  const build = path.join(REPO, 'tools', 'progress', 'build.js');
  if (fs.existsSync(build)) {
    const r = spawnSync(process.execPath, [build], { cwd: REPO, encoding: 'utf8' });
    progress = r.status === 0 ? 'rebuilt' : `failed (exit ${r.status})`;
    if (r.status !== 0 && r.stderr) console.error(r.stderr.trim());
  }

  console.log(`snapshot: ${copied} copied, ${unchanged} unchanged, ${removed} removed, ` +
    `${excluded} excluded, ${errors} errors -> agent-memory/; progress dashboard ${progress}.`);
}

try { main(); } catch (e) { console.error(`snapshot: ${e && e.message}`); }
process.exit(0);
