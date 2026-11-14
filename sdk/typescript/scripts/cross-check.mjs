#!/usr/bin/env node
// Cross-check: the TypeScript SDK and the Python reference must give the SAME
// verdict on every golden vector of every profile.
//
//   node scripts/cross-check.mjs [--python PATH] [--vectors DIR] [--json OUT]
//
// For each profile folder in spec/conformance/ it runs
//   python -m fidetype.conformance consumer [--profile P] --vectors DIR --json -
// and the TypeScript runner, then compares per vector:
//   - actual: accept / reject (the verdict), and
//   - ok: the verdict equals the manifest AND the expected values match.
// Exit 0 only if every vector agrees. Python: --python, $FIDETYPE_PYTHON,
// the repo .venv, then python3 / python.

import { execFileSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..", "..");
const args = process.argv.slice(2);
const opt = (n, d = null) => (args.includes(n) ? args[args.indexOf(n) + 1] : d);

const distNode = join(here, "..", "dist", "node.js");
if (!existsSync(distNode)) {
  console.error("cross-check: run `npm run build` first");
  process.exit(2);
}
const node = await import(new URL(`file://${distNode.replace(/\\/g, "/")}`).href);

function findPython() {
  const cands = [opt("--python"), process.env.FIDETYPE_PYTHON,
    join(repo, ".venv", "Scripts", "python.exe"), join(repo, ".venv", "bin", "python"), "python3", "python"].filter(Boolean);
  for (const c of cands) {
    try {
      execFileSync(c, ["-c", "import fidetype.conformance"], { stdio: "ignore", cwd: repo });
      return c;
    } catch {
      // try the next one
    }
  }
  throw new Error("no Python with the fidetype package found (set --python or FIDETYPE_PYTHON)");
}

const python = findPython();
const vectorsRoot = resolve(opt("--vectors", join(repo, "spec", "conformance")));
const profiles = await node.listProfiles(vectorsRoot);
const out = { schema: "fidetype.sdk-ts.cross-check/1", python, profiles: [] };
let allAgree = true;

for (const p of profiles) {
  const dir = join(vectorsRoot, p);
  const pyArgs = ["-m", "fidetype.conformance", "consumer", ...(p === "v0.1" ? [] : ["--profile", p]), "--vectors", dir, "--json", "-"];
  let pyText;
  try {
    pyText = execFileSync(python, pyArgs, { cwd: repo, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 << 20 });
  } catch (e) {
    pyText = e.stdout; // exit 1 when a vector fails; the JSON is still on stdout
  }
  const py = JSON.parse(pyText);
  const ts = await node.runProfileDir(p, dir);
  const pyById = new Map(py.vectors.map((v) => [v.id, v]));
  const rows = [];
  for (const t of ts.vectors) {
    const q = pyById.get(t.id);
    const agree = q !== undefined && q.actual === t.actual && q.ok === t.ok;
    rows.push({ id: t.id, python: q ? `${q.actual}${q.ok ? "" : " (not ok)"}` : "missing", typescript: `${t.actual}${t.ok ? "" : " (not ok)"}`, agree });
  }
  for (const q of py.vectors) if (!ts.vectors.some((t) => t.id === q.id)) rows.push({ id: q.id, python: q.actual, typescript: "missing", agree: false });
  const n = rows.filter((r) => r.agree).length;
  const accepts = ts.vectors.filter((t) => t.actual === "accept").length;
  out.profiles.push({ profile: p, vectors: rows.length, agree: n, accept: accepts, reject: ts.vectors.length - accepts,
    python_passed: py.passed, typescript_passed: ts.passed, rows });
  allAgree &&= n === rows.length;
  for (const r of rows) if (!r.agree) console.log(`  DIFF ${p} ${r.id}: python ${r.python}, typescript ${r.typescript}`);
  console.log(`[cross-check ${p}] ${n}/${rows.length} identical verdicts (python ${py.passed}/${py.total} pass, typescript ${ts.passed}/${ts.total} pass)`);
}
out.ok = allAgree && profiles.length > 0;
const jsonOut = opt("--json");
if (jsonOut) writeFileSync(jsonOut, JSON.stringify(out, null, 1) + "\n");
console.log(out.ok ? "cross-check: PASS (TypeScript = Python on every vector)" : "cross-check: FAIL");
process.exit(out.ok ? 0 : 1);
