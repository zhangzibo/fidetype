// Tests on the golden vectors of spec/conformance (the same files as the Python suite).
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
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
    for (const ev of sdk.parseNtsText(readFileSync(join(dir, v.file)))) out.push([v.id, ev]);
  }
  return out;
}

test("schemas: every event of every accepted JSON Lines vector is valid", () => {
  let n = 0;
  for (const p of readdirSync(conf)) {
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
  const cases = { "fep-0001": ["F04", "F05", "F11", "F13", "F17", "F18", "F19", "F20", "F27", "F28", "F29", "F30", "F31", "F32", "F33", "F35"],
    "v0.1": ["V36", "V37", "V47", "V52"] };
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
