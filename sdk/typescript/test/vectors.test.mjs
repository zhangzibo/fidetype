// Tests on the golden vectors of spec/conformance (the same files as the Python suite).
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as sdk from "../dist/index.js";
import * as node from "../dist/node.js";

const here = dirname(fileURLToPath(import.meta.url));
const conf = join(here, "..", "..", "..", "spec", "conformance");

test("every profile present passes its golden vectors", async () => {
  const profiles = await node.listProfiles(conf);
  assert.ok(profiles.includes("v0.1") && profiles.includes("fep-0001") && profiles.includes("fep-0002"), profiles.join());
  for (const p of profiles) {
    const r = await node.runProfileDir(p, join(conf, p));
    const bad = r.vectors.filter((v) => !v.ok).map((v) => `${v.id}: ${v.detail}`);
    assert.deepEqual(bad, [], `${p}: ${bad.join("; ")}`);
    assert.ok(r.total > 0);
  }
});

test("a reject vector names the same failing check as the manifest (v0.1)", async () => {
  const m = JSON.parse(readFileSync(join(conf, "v0.1", "manifest.json"), "utf8"));
  for (const v of m.vectors.filter((x) => x.expect === "reject" && x.failing_check)) {
    const res = sdk.checkStream(v.file, await node.readBytes(join(conf, "v0.1", v.file)));
    assert.ok(res.failures.some((f) => f.id === v.failing_check), `${v.id}: ${res.failures.map((f) => f.id)} lacks ${v.failing_check}`);
  }
});

test("the NPZ reader reads the NPZ vectors", async () => {
  const c = await node.loadStreamFile(join(conf, "v0.1", "v07-minus-inf-row.npz"));
  assert.equal(c.summary.n_frames, 3);
  assert.equal(c.summary.neg_inf_cells, 81);
  const raw = sdk.readNpzRaw(await node.readBytes(join(conf, "v0.1", "v26-pickled-object.npz")));
  assert.equal(raw.parsed, false);
});

function eventsOfAccepted(profile) {
  const dir = join(conf, profile);
  const m = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  const out = [];
  for (const v of m.vectors.filter((x) => x.expect === "accept" && x.file.endsWith(".jsonl"))) {
    const evs = sdk.parseNtsText(readFileSync(join(dir, v.file)));
    // NTS 1.0 RC3, VER-8: data of a newer minor version may hold unknown enumeration values. The hand-written
    // schemas are 1.0 structural schemas, so such vectors are out of their scope (the generated nts-v1 schema covers them).
    if (evs.some((e) => sdk.isNewerMinor(e.spec_version))) continue;
    for (const ev of evs) out.push([v.id, ev]);
  }
  return out;
}

test("schemas: every event of every accepted JSON Lines vector is valid", () => {
  let n = 0;
  // The profile folders, then the conformance kit (P7-01) folders.
  const dirs = [...readdirSync(conf), ...readdirSync(join(conf, "kit")).map((p) => join("kit", p))];
  for (const p of dirs.filter((d) => existsSync(join(conf, d, "manifest.json")))) {
    for (const [id, ev] of eventsOfAccepted(p)) {
      const errs = sdk.validateEventSchema(ev);
      assert.deepEqual(errs, [], `${p} ${id} ${ev.type}: ${JSON.stringify(errs)}`);
      n++;
    }
  }
  assert.ok(n > 100, `only ${n} events checked`);
});

test("schemas: structural reject vectors break their schema", async () => {
  // Vectors whose only fault is structural: the schema must reject them too.
  // Not F50 / V61 (an integer written as 1.0, GEN-5): JSON Schema counts 1.0 as an integer; the validators check it.
  const cases = { "fep-0001": ["F04", "F05", "F11", "F13", "F17", "F18", "F19", "F20", "F27", "F28", "F29", "F30", "F31", "F32", "F33", "F35", "F46", "F47", "F51", "F52", "F53", "F54"],
    "v0.1": ["V36", "V37", "V47", "V52", "V55", "V56", "V57", "V58", "V59"] };
  for (const [p, ids] of Object.entries(cases)) {
    const m = JSON.parse(readFileSync(join(conf, p, "manifest.json"), "utf8"));
    for (const id of ids) {
      const v = m.vectors.find((x) => x.id === id);
      const evs = sdk.parseNtsText(readFileSync(join(conf, p, v.file)));
      assert.ok(evs.some((e) => sdk.validateEventSchema(e).length), `${p} ${id}: no schema error`);
    }
  }
});

test("the generated types match the schemas (drift check)", () => {
  const out = execFileSync(process.execPath, [join(here, "..", "scripts", "gen-schemas.mjs"), "--check"], { encoding: "utf8" });
  assert.match(out, /schemas OK/);
});

test("the core build is browser safe", () => {
  const out = execFileSync(process.execPath, [join(here, "..", "scripts", "check-browser-safe.mjs")], { encoding: "utf8" });
  assert.match(out, /OK/);
});

test("decision logs: acted texts equal the manifest (FEP-0001 rule 1)", async () => {
  const m = JSON.parse(readFileSync(join(conf, "fep-0001", "manifest.json"), "utf8"));
  for (const v of m.vectors.filter((x) => x.expect === "accept" && x.expected?.kind === "decisions")) {
    const ds = await node.handleDecisionFile(join(conf, "fep-0001", v.file));
    const acted = ds.filter((d) => d.kind === "commit").map((d) => d.committed);
    assert.deepEqual(acted, v.expected.acted, v.id);
    assert.ok(ds.every((d) => !d.errors.length), v.id);
  }
});

test("fep-0005: each reject vector fails its named check; decision logs give the moving ticks", () => {
  const dir = join(conf, "fep-0005");
  const m = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  assert.equal(m.vectors.length, 53);
  for (const v of m.vectors) {
    const bytes = new Uint8Array(readFileSync(join(dir, v.file)));
    const rep = sdk.fep0005.checkFile(v.file, bytes);
    const fails = rep.checks.filter((c) => c.status === "fail").map((c) => c.id);
    if (v.expect === "reject") assert.ok(fails.includes(v.failing_check), `${v.id}: ${fails} lacks ${v.failing_check}`);
    else assert.deepEqual(fails, [], v.id);
    if (v.expect === "accept" && v.expected?.moving_ticks) {
      assert.deepEqual(sdk.fep0005.consume(v.file, bytes).moving_ticks, v.expected.moving_ticks, v.id);
    }
  }
});

test("fep-0005: DecisionTracker accepts exactly the accept decision logs and acts on the moving ticks", () => {
  const dir = join(conf, "fep-0005");
  const m = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  const logs = m.vectors.filter((v) => v.file.startsWith("e"));
  assert.ok(logs.length >= 21);
  for (const v of logs) {
    const lines = readFileSync(join(dir, v.file), "utf8").split("\n").filter((l) => l.trim());
    const out = sdk.handleDecisions(lines);
    const errs = out.flatMap((d) => d.errors);
    if (v.expect === "accept") {
      assert.deepEqual(errs, [], v.id);
      const ticks = out.filter((d) => d.profile === "control" && d.forward).map((d) => d.tick);
      if (v.expected?.moving_ticks) assert.deepEqual(ticks, v.expected.moving_ticks, v.id);
    } else {
      assert.ok(errs.length > 0, `${v.id}: the tracker found no error`);
    }
  }
});

test("the conformance kit (P7-01) gives the expected verdict on every entry", async () => {
  const kit = join(conf, "kit");
  const profiles = await node.listProfiles(kit);
  assert.deepEqual(profiles, ["v0.1", "fep-0001", "fep-0002", "fep-0003", "fep-0004", "fep-0005"]);
  let total = 0;
  for (const p of profiles) {
    const r = await node.runProfileDir(p, join(kit, p));
    const bad = r.vectors.filter((v) => !v.ok).map((v) => `${v.id}: ${v.detail}`);
    assert.deepEqual(bad, [], `kit ${p}: ${bad.join("; ")}`);
    total += r.total;
  }
  assert.equal(total, 36); // P7-01: 31; P7-02 / P1-16 (kit 0.2.0): K32-K36
});

test("MET-11 modality match is an advisory warning; the summary gives warnings and the stream level (P1-16, P7-02)", async () => {
  const kit = join(conf, "kit", "v0.1");
  const k32 = sdk.loadStream("k32-modality-mismatch.jsonl", await node.readBytes(join(kit, "k32-modality-mismatch.jsonl")));
  assert.deepEqual(k32.summary.warnings, ["NTS-MODALITY-MATCH"]);
  assert.equal(k32.summary.level, "provenance");
  const res = sdk.checkStream("k32-modality-mismatch.jsonl", await node.readBytes(join(kit, "k32-modality-mismatch.jsonl")));
  const r = res.results.find((x) => x.id === "NTS-MODALITY-MATCH");
  assert.equal(r.level, "advisory");
  assert.equal(r.status, "fail");
  assert.match(r.message, /emg\.placement.*MET-11/);
  const levels = { "k33-core-only.jsonl": "core", "k34-trust-ready-no-provenance.jsonl": "trust-ready",
    "k35-offline-with-latency.jsonl": "core", "k36-calibration-without-method.jsonl": "core" };
  for (const [f, want] of Object.entries(levels)) {
    assert.equal(sdk.loadStream(f, await node.readBytes(join(kit, f))).summary.level, want, f);
  }
});

test("MET-12 licence match is an advisory warning; the licence table equals Python and Rust (P5-19)", async () => {
  // The same lists as tests/test_licence_match.py and the Rust test licence_table.
  for (const id of ["CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-NC-ND-3.0-IGO", "cc-by-nc-2.5", "CC-BY-SA-NC-4.0", "LicenseRef-unknown", "licenseref-UNKNOWN"]) {
    assert.equal(sdk.noCommercialId(id), true, id);
  }
  for (const id of ["CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-ND-4.0", "CC0-1.0", "MIT", "LicenseRef-fidetype-consented", "CC BY-NC 4.0", "CC-BY-NC-4.0\n", "CC-BY-NC-4.0-IGOX", "CC-BY-NC-40", "CC-BY-NCX-4.0", "CC-BY-NC-4.0-I", "CC-BY-NC-4.0-1G", "", "CC-BY-NC-4.٠", 4, null]) {
    assert.equal(sdk.noCommercialId(id), false, String(id));
  }
  const v = join(conf, "v0.1");
  const want = { "v101-licence-nc-not-research-only.jsonl": ["NTS-LICENCE-MATCH"], "v102-licence-unknown-not-research-only.npz": ["NTS-LICENCE-MATCH"],
    "v103-licence-nc-lowercase-igo.jsonl": ["NTS-LICENCE-MATCH"], "v104-licence-sa-not-research-only.jsonl": [], "v98-data-licence-keys.jsonl": [] };
  for (const [f, w] of Object.entries(want)) {
    assert.deepEqual(sdk.loadStream(f, await node.readBytes(join(v, f))).summary.warnings, w, f);
  }
  const res = sdk.checkStream("v101.jsonl", await node.readBytes(join(v, "v101-licence-nc-not-research-only.jsonl")));
  const r = res.results.find((x) => x.id === "NTS-LICENCE-MATCH");
  assert.equal(r.level, "advisory");
  assert.equal(r.status, "fail");
  assert.match(r.message, /CC-BY-NC-4\.0.*MET-12/);
});
