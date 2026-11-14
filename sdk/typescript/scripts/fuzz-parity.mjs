#!/usr/bin/env node
// Parity fuzz: mutate the JSON / JSON Lines golden vectors (fixed seed) and
// check that the TypeScript SDK and the Python reference give the SAME
// verdict (accept / reject) on every mutant. The golden vectors alone test
// only the cases in the manifests; the mutants test the edges between them.
//
//   node scripts/fuzz-parity.mjs [--n 20] [--seed 1] [--python PATH] [--out DIR] [--keep] [--rust BIN]
//
// --n: mutants per vector file. Files go to a temporary folder (deleted unless --keep).
// --rust BIN (or $FIDETYPE_RUST_BIN): the Rust SDK CLI (sdk/rust, M7-07) must
// also give the Python verdict on every mutant.

import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..", "..");
const args = process.argv.slice(2);
const opt = (n, d = null) => (args.includes(n) ? args[args.indexOf(n) + 1] : d);
const N = Number(opt("--n", "20"));
let seed = Number(opt("--seed", "1")) >>> 0;
const keep = args.includes("--keep");
const rustArg = opt("--rust", process.env.FIDETYPE_RUST_BIN || null);
const rustBin = rustArg && existsSync(resolve(rustArg)) ? resolve(rustArg) : rustArg; // a path, or a command on PATH

const node = await import(new URL(`file://${join(here, "..", "dist", "node.js").replace(/\\/g, "/")}`).href);

function rand() {
  // mulberry32
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const pick = (a) => a[Math.floor(rand() * a.length)];

function paths(v, p = []) {
  const out = [p];
  if (Array.isArray(v)) v.forEach((x, i) => out.push(...paths(x, [...p, i])));
  else if (v && typeof v === "object") for (const [k, x] of Object.entries(v)) out.push(...paths(x, [...p, k]));
  return out;
}
const getAt = (v, p) => p.reduce((o, k) => o[k], v);

const VALUES = [null, "x", "", 1.5, -1, 0, 2, 1e400, true, false, [], {}, [0], "NaN", -0.0001, 1.0000001, "header", "COMMIT", "intent", "frame"];
let floatId = 0;
const floats = new Map();

/** Mutate a parsed JSON value in place (or return a replacement). */
function mutate(root) {
  const ps = paths(root).filter((p) => p.length);
  if (!ps.length) return root;
  const p = pick(ps);
  const parent = getAt(root, p.slice(0, -1));
  const k = p[p.length - 1];
  const op = rand();
  if (op < 0.2) {
    if (Array.isArray(parent)) parent.splice(k, 1);
    else delete parent[k];
  } else if (op < 0.35 && typeof parent[k] === "number" && Number.isInteger(parent[k])) {
    const id = `__FLOAT_${floatId++}__`;
    floats.set(id, `${parent[k]}.0`);
    parent[k] = id;
  } else if (op < 0.45 && typeof parent[k] === "number") parent[k] = parent[k] + pick([1, -1, 0.5, 1e-4, -1e-4, 100]);
  else if (op < 0.5 && Array.isArray(parent[k]) && parent[k].length) parent[k].push(parent[k][0]);
  else if (op < 0.55 && typeof parent[k] === "string") parent[k] = parent[k] + pick([" ", "x", "\u00e9", ""]);
  else parent[k] = structuredClone(pick(VALUES));
  return root;
}

function dump(v) {
  let s = JSON.stringify(v, (_k, x) => (typeof x === "number" && !Number.isFinite(x) ? `__NUM_${x}__` : x));
  s = s.replace(/"__NUM_(Infinity|-Infinity|NaN)__"/g, (_m, g) => (g === "Infinity" ? "1e400" : g === "-Infinity" ? "-1e400" : "NaN"));
  for (const [id, txt] of floats) s = s.split(`"${id}"`).join(txt);
  return s;
}

function mutateLines(text) {
  const lines = text.split("\n").filter((l) => l.length);
  const op = rand();
  if (op < 0.1 && lines.length > 1) {
    const i = Math.floor(rand() * (lines.length - 1));
    [lines[i], lines[i + 1]] = [lines[i + 1], lines[i]];
  } else if (op < 0.15) lines.splice(Math.floor(rand() * lines.length), 0, lines[Math.floor(rand() * lines.length)]);
  else if (op < 0.2 && lines.length > 1) lines.splice(Math.floor(rand() * lines.length), 1);
  else {
    const i = Math.floor(rand() * lines.length);
    lines[i] = dump(mutate(JSON.parse(lines[i])));
  }
  return lines.join("\n") + "\n";
}

const python = (() => {
  for (const c of [opt("--python"), process.env.FIDETYPE_PYTHON, join(repo, ".venv", "Scripts", "python.exe"), join(repo, ".venv", "bin", "python"), "python3", "python"].filter(Boolean)) {
    try {
      execFileSync(c, ["-c", "import fidetype"], { stdio: "ignore" });
      return c;
    } catch {
      // next
    }
  }
  throw new Error("no Python with fidetype");
})();

const vroot = join(repo, "spec", "conformance");
const work = opt("--out") ? resolve(opt("--out")) : mkdtempSync(join(tmpdir(), "fidetype-fuzz-"));
let total = 0;
let diffs = 0;
for (const p of await node.listProfiles(vroot)) {
  const src = join(vroot, p);
  const dst = join(work, p);
  mkdirSync(dst, { recursive: true });
  const vectors = [];
  for (const f of readdirSync(src).sort()) {
    if (f === "manifest.json" || !(f.endsWith(".jsonl") || f.endsWith(".json"))) continue;
    const text = readFileSync(join(src, f), "utf8");
    for (let k = 0; k < N; k++) {
      floats.clear();
      let m;
      try {
        m = f.endsWith(".jsonl") ? mutateLines(text) : dump(mutate(JSON.parse(text))) + "\n";
      } catch {
        continue;
      }
      const name = `${f.replace(/\.(jsonl|json)$/, "")}-m${k}.${f.endsWith(".jsonl") ? "jsonl" : "json"}`;
      writeFileSync(join(dst, name), m);
      vectors.push({ id: name, file: name, expect: "accept" });
    }
  }
  writeFileSync(join(dst, "manifest.json"), JSON.stringify({ schema: "fidetype.conformance.vectors/1", vectors }, null, 1));
  let pyText;
  try {
    pyText = execFileSync(python, ["-m", "fidetype.conformance", "consumer", ...(p === "v0.1" ? [] : ["--profile", p]), "--vectors", dst, "--json", "-"],
      { cwd: repo, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 256 << 20 });
  } catch (e) {
    pyText = e.stdout;
  }
  const py = new Map(JSON.parse(pyText).vectors.map((v) => [v.id, v]));
  const ts = await node.runProfileDir(p, dst);
  let rs = null;
  if (rustBin) {
    let rsText;
    try {
      rsText = execFileSync(rustBin, ["conformance", "--profile", p, "--vectors", dst, "--json", "-"],
        { cwd: repo, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 256 << 20 });
    } catch (e) {
      rsText = e.stdout;
    }
    rs = new Map(JSON.parse(rsText).reports[0].vectors.map((v) => [v.id, v]));
  }
  let d = 0;
  let dTs = 0;
  let dRs = 0;
  let acc = 0;
  for (const t of ts.vectors) {
    const q = py.get(t.id);
    const r = rs ? rs.get(t.id) : null;
    if (t.actual === "accept") acc++;
    const tsDiff = !q || q.actual !== t.actual;
    const rsDiff = rs !== null && (!q || !r || q.actual !== r.actual);
    if (tsDiff) dTs++;
    if (rsDiff) dRs++;
    if (tsDiff || rsDiff) {
      d++;
      console.log(`  DIFF ${p} ${t.id}: python ${q ? q.actual : "missing"} (${q?.detail ?? ""}) | typescript ${t.actual} (${t.detail})` +
        `${rs ? ` | rust ${r ? r.actual : "missing"} (${r?.detail ?? ""})` : ""}`);
    }
  }
  total += ts.vectors.length;
  diffs += d;
  const n = ts.vectors.length;
  console.log(`[fuzz ${p}] ${n - d}/${n} identical verdicts on mutants (${acc} accepted)` +
    `${rs ? `; typescript = python ${n - dTs}/${n}, rust = python ${n - dRs}/${n}` : ""}`);
}
if (!keep && !opt("--out")) rmSync(work, { recursive: true, force: true });
console.log(diffs ? `fuzz parity: FAIL (${diffs} of ${total} differ)` : `fuzz parity: PASS (${total} mutants, identical verdicts)`);
process.exit(diffs ? 1 : 0);
