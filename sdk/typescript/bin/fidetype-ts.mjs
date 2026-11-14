#!/usr/bin/env node
// Command line of the Fidetype TypeScript SDK (Node >= 18). Run `npm run build` first.
//
//   fidetype-ts conformance [--profile NAME|all] [--vectors DIR] [--json OUT]
//   fidetype-ts validate FILE [--level core|trust-ready|provenance] [--json]
//   fidetype-ts consume [--profile NAME] FILE     exit 0 = accept (prints the summary as JSON), 1 = reject
//   fidetype-ts decisions FILE                    print what a consumer does with each trust_decision
//
// `consume` follows the external-consumer contract of the Python suite, so
//   python -m fidetype.conformance consumer --cmd "node sdk/typescript/bin/fidetype-ts.mjs consume {path}"
// runs the Python suite against this SDK.

import { existsSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dist = join(here, "..", "dist");
if (!existsSync(join(dist, "index.js"))) {
  console.error("fidetype-ts: dist/ is missing. Run `npm run build` in sdk/typescript first.");
  process.exit(2);
}
const sdk = await import(new URL(`file://${join(dist, "index.js").replace(/\\/g, "/")}`).href);
const node = await import(new URL(`file://${join(dist, "node.js").replace(/\\/g, "/")}`).href);

const argv = process.argv.slice(2);
const cmd = argv.shift();
function opt(name, dflt = null) {
  const i = argv.indexOf(name);
  if (i < 0) return dflt;
  const v = argv[i + 1];
  argv.splice(i, 2);
  return v;
}
function flag(name) {
  const i = argv.indexOf(name);
  if (i < 0) return false;
  argv.splice(i, 1);
  return true;
}
const defaultVectors = resolve(here, "..", "..", "..", "spec", "conformance");

async function conformance() {
  const profile = opt("--profile", "all");
  const vectors = resolve(opt("--vectors", defaultVectors));
  const jsonOut = opt("--json");
  const profiles = profile === "all" ? await node.listProfiles(vectors) : [profile];
  const reports = [];
  for (const p of profiles) {
    const dir = profile === "all" || existsSync(join(vectors, p, "manifest.json")) ? join(vectors, p) : vectors;
    const r = await node.runProfileDir(p, dir);
    reports.push(r);
    for (const o of r.vectors) if (!o.ok) console.log(`  FAIL ${p} ${o.id}: expected ${o.expect}, got ${o.actual}. ${o.detail}`);
    console.log(sdk.reportLine(r));
  }
  if (jsonOut) {
    const text = JSON.stringify({ schema: "fidetype.sdk-ts.conformance/1", sdk_version: sdk.SDK_VERSION, reports }, null, 1) + "\n";
    if (jsonOut === "-") process.stdout.write(text);
    else writeFileSync(jsonOut, text);
  }
  return reports.every((r) => r.ok) ? 0 : 1;
}

async function validate() {
  const level = opt("--level", "core");
  const asJson = flag("--json");
  const file = argv[0];
  if (!file) throw new Error("usage: fidetype-ts validate FILE [--level L] [--json]");
  const rep = await node.checkStreamFile(file, level);
  if (asJson) {
    process.stdout.write(JSON.stringify({ target: file, level_reached: rep.level, ok: rep.ok, checks: rep.results }, null, 1) + "\n");
  } else {
    for (const r of rep.results) {
      if (r.status === "fail") console.log(`  ${r.level === "advisory" ? "WARN" : "FAIL"} ${r.id.padEnd(22)} [${r.keyword} ${r.clause}] ${r.message}`);
    }
    console.log(`${file}: ${rep.ok ? "PASS" : "FAIL"} (level ${level}; highest level reached: ${rep.level ?? "none"})`);
  }
  return rep.ok ? 0 : 1;
}

async function consume() {
  const profile = opt("--profile", "v0.1");
  const file = argv[0];
  const consumer = sdk.CONSUMERS[profile];
  if (!file || !consumer) throw new Error("usage: fidetype-ts consume [--profile NAME] FILE");
  try {
    const res = consumer(basename(file), await node.readBytes(file));
    process.stdout.write(JSON.stringify(res) + "\n");
    return 0;
  } catch (e) {
    console.error(e instanceof Error ? `${e.name}: ${e.message}` : String(e));
    return 1;
  }
}

async function decisions() {
  const file = argv[0];
  if (!file) throw new Error("usage: fidetype-ts decisions FILE");
  let bad = 0;
  for (const d of await node.handleDecisionFile(file)) {
    const e = d.event;
    const who = `${e.session ?? ""}#${e.seq ?? "?"}`;
    const what = d.kind === "commit" ? `COMMIT ${JSON.stringify(d.committed)}` : d.kind === "preview" ? `preview ${e.action} (not final: do not act)` : `${String(e.action)} ${d.offered.length ? JSON.stringify(d.offered) : ""}`;
    console.log(`${who.padEnd(10)} ${what}${d.forward ? "  -> forward" : ""}`);
    for (const w of d.warnings) console.log(`           warning: ${w}`);
    for (const x of d.errors) console.log(`           error: ${x}`);
    if (d.errors.length) bad++;
  }
  return bad ? 1 : 0;
}

const commands = { conformance, validate, consume, decisions };
if (!commands[cmd]) {
  console.error("usage: fidetype-ts <conformance|validate|consume|decisions> ...");
  process.exit(2);
}
try {
  process.exit(await commands[cmd]());
} catch (e) {
  console.error(`fidetype-ts: ${e instanceof Error ? e.message : String(e)}`);
  process.exit(2);
}
