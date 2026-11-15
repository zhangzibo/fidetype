// Unit tests of the core (browser-safe) API. Run: npm test (after npm run build).
import { test } from "node:test";
import assert from "node:assert/strict";
import { deflateRawSync } from "node:zlib";
import { createHash } from "node:crypto";
import * as sdk from "../dist/index.js";

const enc = new TextEncoder();

test("parseJson keeps the int / float difference of Python", () => {
  const v = sdk.parseJson('{"seq": 1, "unit": 1.0, "big": 1e3, "arr": [2, 2.0]}');
  assert.equal(sdk.isIntAt(v, "seq"), true);
  assert.equal(sdk.isIntAt(v, "unit"), false);
  assert.equal(sdk.isIntAt(v, "big"), false);
  assert.equal(sdk.isIntAt(v.arr, 0), true);
  assert.equal(sdk.isIntAt(v.arr, 1), false);
});

test("parseJson rejects NaN, Infinity, a BOM and trailing data", () => {
  for (const bad of ["NaN", '{"a": Infinity}', "[-Infinity]", "\ufeff{}", "{} x", "01", '{"a": 1,}', "'a'"]) {
    assert.throws(() => sdk.parseJson(bad), sdk.JsonParseError, bad);
  }
  assert.equal(Number.isNaN(sdk.parseJson("NaN", { allowConstants: true })), true);
});

test("parseJson keeps a __proto__ key as a plain own key", () => {
  const v = sdk.parseJson('{"__proto__": {"x": 1}}');
  assert.deepEqual(Object.keys(v), ["__proto__"]);
  assert.equal({}.x, undefined);
});

test("pyLines splits as Python str.splitlines()", () => {
  assert.deepEqual(sdk.pyLines("a\r\nb\rc\nd\u2028e\x85f\n"), ["a", "b", "c", "d", "e", "f"]);
  assert.deepEqual(sdk.pyLines(""), []);
});

test("inflateRaw decodes zlib raw deflate output", () => {
  const data = new Uint8Array(70000);
  for (let i = 0; i < data.length; i++) data[i] = (i * 7 + (i >> 5)) % 251;
  for (const level of [0, 1, 6, 9]) {
    const z = deflateRawSync(data, { level });
    assert.deepEqual(sdk.inflateRaw(new Uint8Array(z), data.length), data, `level ${level}`);
  }
});

test("sha256Hex matches node:crypto", () => {
  for (const s of ["", "abc", "a".repeat(55), "a".repeat(56), "a".repeat(200)]) {
    assert.equal(sdk.sha256Hex(enc.encode(s)), createHash("sha256").update(s).digest("hex"));
  }
});

function row(V, hot, p = 0.9) {
  return Array.from({ length: V }, (_, i) => (i === hot ? p : (1 - p) / (V - 1)));
}

test("NtsWriter output is accepted by the reference consumer", () => {
  const text = sdk.toJsonl({ source: "unit-test", frame_period: 0.04, meta: { "device.modality": "emg", "decoder.causal": true, "data.derived": true, language: "en" } }, (w) => {
    w.frame(0.0, { probs: row(28, 1) });
    w.frame(0.04, { logits: Array.from({ length: 28 }, (_, i) => (i === 2 ? 5 : 0)) });
    w.hypothesis([{ text: "ab", score: -1.0, char_confidences: [0.9, 0.8] }, ["a", -2]], { isFinal: true });
    w.segmentEnd(0.05);
  });
  const c = sdk.loadStream("x.jsonl", enc.encode(text));
  assert.equal(c.summary.n_frames, 2);
  assert.equal(c.summary.vocab_size, 28);
  assert.equal(c.summary.ignored_events, 1); // segment_end is not a v0.1 event kind
  assert.equal(c.summary.events, 1);
  const chk = sdk.checkStream("x.jsonl", enc.encode(text), "trust-ready");
  assert.equal(chk.ok, true, JSON.stringify(chk.failures));
  assert.equal(chk.level, "trust-ready");
  // The FEP-0001 profile accepts it too.
  assert.equal(sdk.fep0001.consume("x.jsonl", enc.encode(text)).segments, 1);
});

test("NtsWriter refuses bad input", () => {
  const w = new sdk.NtsWriter(() => {}, { source: "s" });
  assert.throws(() => w.frame(0, { probs: row(28, 1, 0.5).map((x) => x * 2) }), /sum to 1/);
  w.frame(0, { probs: row(28, 1) });
  assert.throws(() => w.frame(0, { probs: row(28, 1) }), /increase strictly/);
  assert.throws(() => w.hypothesis([{ text: "ab", char_confidences: [0.5] }], { isFinal: true }), /char_confidences/);
  w.end();
  assert.throws(() => w.segmentEnd(), /ended/);
});

// The same hypothesis-only stream in the Python, TypeScript and Rust writer tests (Python bytes; same events and key order, HDR-12).
const EMPTY_VOCAB_LINES = [
  "{\"type\": \"header\", \"spec_version\": \"0.1\", \"vocab\": [], \"vocab_type\": \"char\", \"blank_id\": null, \"source\": \"t\", \"clock_domain\": \"trial\", \"meta\": {}}",
  "{\"type\": \"hypothesis\", \"id\": \"u1\", \"is_final\": true, \"score_semantics\": \"none\", \"nbest\": [{\"text\": \"hello\", \"score\": -1.5}], \"t_start\": 0.5, \"t_end\": 1.25}",
  "{\"type\": \"segment_end\", \"t\": 1.25, \"unit\": \"utterance\"}",
  "{\"type\": \"end\"}",
];

test("NtsWriter: empty vocab gives a hypothesis-only stream and refuses frames (HDR-12)", () => {
  const lines = [];
  const w = new sdk.NtsWriter((l) => lines.push(l), { source: "t", vocab: [], blank_id: null, extraHeader: { clock_domain: "trial" } });
  w.hypothesis([["hello", -1.5]], { isFinal: true, id: "u1", tStart: 0.5, tEnd: 1.25 });
  w.segmentEnd(1.25, "utterance");
  assert.throws(() => w.frame(0, { logProbs: [] }), /HDR-12/);
  assert.throws(() => w.frame(0, { probs: [] }), /HDR-12/);
  assert.throws(() => w.frame(0, { logits: [] }), /HDR-12/);
  assert.throws(() => w.event({ type: "frame", t: 0, log_probs: [] }), /HDR-12/);
  assert.throws(() => w.event({ type: "frame", t: 0, top_ids: [], top_log_probs: [], rest_log_prob: 0 }), /HDR-12/);
  assert.throws(() => w.segmentEnd(undefined, "sentence"), /unit/);
  w.end();
  // Same events, values and key order as Python (TypeScript writes compact JSON).
  const norm = (l) => JSON.stringify(JSON.parse(l));
  assert.deepEqual(lines.map(norm), EMPTY_VOCAB_LINES.map(norm));
  const chk = sdk.checkStream("x.jsonl", enc.encode(lines.join("\n") + "\n"));
  assert.equal(chk.ok, true, JSON.stringify(chk.failures));
});

test("NtsWriter: empty vocab refusals", () => {
  assert.throws(() => new sdk.NtsWriter(() => {}, { source: "t", vocab: [] }), /blank_id must be null/);
  assert.throws(() => new sdk.NtsWriter(() => {}, { source: "t", vocab: ["a", "a"], blank_id: null }), /unique/);
  assert.throws(() => new sdk.NtsWriter(() => {}, { source: "t", vocab: [], blank_id: null, extraHeader: { vocab: ["a"] } }), /extraHeader must not set 'vocab'/);
});

test("loadStream rejects with the failing clause", () => {
  const bad = '{"type":"header","spec_version":"0.2","vocab":["a","b"],"vocab_type":"char","blank_id":null}\n';
  assert.throws(() => sdk.loadStream("x.jsonl", enc.encode(bad)), (e) => e instanceof sdk.StreamRejected && e.checkId === "NTS-VERSION");
});

test("spec_version: 0.1 and 1.<minor> are accepted, other values refused (NTS 1.0 RC2, VER-3 / VER-5)", () => {
  for (const v of ["0.1", "1.0", "1.3", "1.10"]) assert.ok(sdk.isSupportedSpecVersion(v), v);
  for (const v of ["2.0", "1.0.0", "01.0", "1.01", "0.2", "1.", "1", "", 1.0, null]) assert.ok(!sdk.isSupportedSpecVersion(v), String(v));
  const v = new sdk.StreamValidator();
  assert.equal(v.push({ type: "header", spec_version: "1.0", vocab: ["a", "b"], vocab_type: "char", blank_id: null }).kind, "header");
  assert.throws(() => new sdk.StreamValidator().push({ type: "header", spec_version: "2.0", vocab: ["a"], vocab_type: "char", blank_id: null }), /spec_version/);
});

test("StreamValidator checks events one at a time", () => {
  const v = new sdk.StreamValidator();
  assert.throws(() => v.push({ type: "frame", t: 0, log_probs: [0] }), /before the header/);
  assert.equal(v.push({ type: "header", spec_version: "0.1", vocab: ["a", "b"], vocab_type: "char", blank_id: null }).kind, "header");
  assert.equal(v.push('{"type":"frame","t":0,"log_probs":[0, null]}').kind, "frame");
  assert.throws(() => v.push({ type: "frame", t: 0, log_probs: [0, null] }), /does not increase/);
  assert.throws(() => v.push({ type: "frame", t: 1, log_probs: [0, 0] }), /log-sum-exp/);
  assert.throws(() => v.push({ type: "hypothesis", id: "h", is_final: true, nbest: [{ text: "a", score: null }] }), /finite numeric score/);
  assert.equal(v.push({ type: "acme.x" }).kind, "ignored");
  assert.equal(v.push({ type: "end" }).kind, "end");
  assert.equal(v.push({ type: "frame", t: 9, log_probs: "junk" }).kind, "ignored"); // after end (spec 10, A5)
});

test("readNtsEvents splits lines across chunk borders (UTF-8 too)", async () => {
  const text = '{"type":"header","spec_version":"0.1","vocab":["é","b"],"vocab_type":"char","blank_id":null}\r\n{"type":"end"}\n';
  const bytes = enc.encode(text);
  const cut = text.indexOf("é") + 1; // inside the 2-byte character
  async function* chunks() {
    yield bytes.slice(0, cut);
    yield bytes.slice(cut, cut + 70);
    yield bytes.slice(cut + 70);
  }
  const evs = [];
  for await (const e of sdk.readNtsEvents(chunks())) evs.push(e);
  assert.equal(evs.length, 2);
  assert.equal(evs[0].vocab[0], "é");
  const results = [];
  for await (const r of sdk.validateNtsStream([text])) results.push(r.result.kind);
  assert.deepEqual(results, ["header", "end"]);
});

test("readLines reads a web ReadableStream", async () => {
  const rs = new ReadableStream({
    start(c) {
      c.enqueue(enc.encode('{"type":"end"}\r'));
      c.enqueue(enc.encode('\n{"type":"x"}'));
      c.close();
    },
  });
  const lines = [];
  for await (const l of sdk.readLines(rs)) lines.push(l);
  assert.deepEqual(lines, ['{"type":"end"}', '{"type":"x"}']);
});

const td = (o) => ({ type: "trust_decision", session: "u1", seq: 0, utterance: 0, is_final: true, action: "COMMIT", shown: ["ab"], p_top1: 0.93, score_semantics: "calibrated_prob", ...o });

test("DecisionTracker: act only on final COMMIT (rule 1)", () => {
  const out = sdk.handleDecisions([
    td({ seq: 0, is_final: false, action: "COMMIT" }),
    td({ seq: 1 }),
    td({ seq: 2, utterance: 1, action: "OFFER", shown: ["cd", "ce"] }),
    td({ seq: 3, utterance: 2, action: "ABSTAIN", shown: [] }),
  ]);
  assert.deepEqual(out.map((d) => d.kind), ["preview", "commit", "offer", "abstain"]);
  assert.deepEqual(out.map((d) => d.forward), [false, true, false, false]);
  assert.equal(out[1].committed, "ab");
  assert.deepEqual(out[2].offered, ["cd", "ce"]);
  assert.ok(out.every((d) => !d.errors.length));
});

test("DecisionTracker: FEP-0001 rule 9 warning on an empty final COMMIT", () => {
  const [d] = sdk.handleDecisions([td({ shown: ["  "] })]);
  assert.equal(d.kind, "commit");
  assert.equal(d.forward, false);
  assert.match(d.warnings[0], /rule 9/);
  assert.equal(sdk.emptyCommitWarning(td({ shown: ["ab"] })), null);
  assert.equal(sdk.emptyCommitWarning(td({ shown: [""], is_final: false })), null); // a preview: rule 1 already forbids acting
  assert.match(sdk.emptyCommitWarning(td({ shown: [""], reason: "gate off" })), /reason: gate off/);
});

test("DecisionTracker: TD-12 drops blank candidates; a warning for 1.x decisions only", () => {
  const out = sdk.handleDecisions([
    td({ seq: 0, action: "OFFER", shown: ["", "ab", " \u00a0"], spec_version: "1.0" }),
    td({ seq: 1, utterance: 1, action: "ASK", shown: ["\t"], spec_version: "1.0" }),
    td({ seq: 2, utterance: 2, action: "OFFER", shown: ["", "cd"] }), // 0.1 rules: no warning, still dropped
    td({ seq: 3, utterance: 3, action: "OFFER_WORDS", shown: ["ef"], spec_version: "1.0" }),
  ]);
  assert.deepEqual(out.map((d) => d.offered), [["ab"], [], ["cd"], ["ef"]]);
  assert.deepEqual(out.map((d) => d.warnings.length), [1, 1, 0, 0]);
  assert.match(out[0].warnings[0], /TD-12/);
  assert.match(out[0].warnings[0], /2 blank candidate/);
  assert.ok(out.every((d) => !d.errors.length && !d.forward));
  assert.equal(sdk.blankCandidateWarning(td({ action: "OFFER", shown: ["ab"], spec_version: "1.0" })), null);
  assert.equal(sdk.blankCandidateWarning(td({ action: "OFFER", shown: [""], spec_version: "0.1" })), null);
  // the fep-0001 consumer accepts with a warning (advisory check FEP1-TD-SHOWN), and its summary drops the blank texts
  const log = [td({ action: "OFFER", shown: ["ab", ""], spec_version: "1.0" })].map((e) => JSON.stringify(e)).join("\n") + "\n";
  const rep = sdk.fep0001.checkFile("x.jsonl", enc.encode(log));
  const c = rep.checks.find((r) => r.id === "FEP1-TD-SHOWN");
  assert.equal(c.status, "fail");
  assert.equal(c.level, "advisory");
  const sum = sdk.fep0001.consume("x.jsonl", enc.encode(log));
  assert.deepEqual(sum.offered, [["ab"]]);
  assert.equal(sum.advisories, 1);
});

test("DecisionTracker: order and format errors (rules 5-8)", () => {
  const out = sdk.handleDecisions([td({ seq: 0 }), td({ seq: 1, action: "OFFER" }), td({ seq: 1, utterance: 1 }), td({ seq: 5, utterance: 2, shown: [] }), td({ seq: 6, utterance: 3, set_size: 1.0 })]);
  assert.match(out[1].errors.join(), /after its final one/);
  assert.match(out[2].errors.join(), /does not increase/);
  assert.match(out[3].errors.join(), /rule 8/);
  assert.equal(out[4].kind, "commit"); // 1.0 from an object literal is an integer in JavaScript
  const parsed = sdk.handleDecisions(['{"type":"trust_decision","is_final":true,"action":"COMMIT","shown":["a"],"p_top1":0.9,"score_semantics":"calibrated_prob","set_size":1.0}']);
  assert.match(parsed[0].errors.join(), /set_size/); // 1.0 in JSON text is a float, as in Python
});

test("DecisionTracker: intent decisions (FEP-0003)", () => {
  const out = sdk.handleDecisions([
    { type: "trust_decision", profile: "intent", session: "s", seq: 0, unit: 0, is_final: true, action: "OFFER", offered: ["intent.call"], p_top1: 0.6, score_semantics: "calibrated_prob", confirm_required: true },
    { type: "trust_decision", profile: "intent", session: "s", seq: 1, unit: 1, is_final: true, action: "COMMIT", intent: "intent.call", risk_class: "irreversible", confirmation_of: 0, p_top1: 0.97, score_semantics: "calibrated_prob" },
  ]);
  assert.deepEqual(out.map((d) => d.kind), ["offer", "commit"]);
  assert.equal(out[1].committed, "intent.call");
  assert.equal(out[1].forward, true);
});

const cd = (o) => ({ type: "trust_decision", profile: "control", session: "c", seq: 0, tick: 0, is_final: true, action: "COMMIT", state: "attenuate", velocity: [30, -9], raw: [40, -12], gain: 0.75, units: "mm/s", reasons: ["shrunk"], p_top1: null, score_semantics: "none", engagement: 1, v_max: 400, ttl_s: 0.06, ...o });
const hold = (o) => cd({ action: "ABSTAIN", state: "hold", velocity: [0, 0], gain: 0, reasons: ["uncertain"], ...o });
const click = (o) => ({ type: "trust_decision", profile: "intent", session: "c", seq: 0, unit: 0, is_final: true, action: "COMMIT", intent: "intent.click", risk_class: "undoable", p_top1: 0.97, score_semantics: "calibrated_prob", ...o });

test("DecisionTracker: control decisions (CTL-T1 … T5, acted list = moving ticks)", () => {
  const out = sdk.handleDecisions([
    hold({ seq: 0, tick: 0, reasons: ["not_engaged"], engagement: 0 }),
    cd({ seq: 1, tick: 1 }),
    hold({ seq: 2, tick: 1, reasons: ["stale_input"] }), // a HOLD may repeat the last tick
    cd({ seq: 3, tick: 2, state: "act", gain: 1, velocity: [40, -12], reasons: ["ok"] }),
    hold({ seq: 4, tick: 2, state: "stop", reasons: ["disengaged"] }),
  ]);
  assert.deepEqual(out.map((d) => d.errors), [[], [], [], [], []]);
  assert.deepEqual(out.map((d) => d.kind), ["abstain", "commit", "abstain", "commit", "abstain"]);
  assert.deepEqual(out.map((d) => d.profile), ["control", "control", "control", "control", "control"]);
  assert.deepEqual(out.filter((d) => d.forward).map((d) => d.tick), [1, 2]);
  assert.ok(out.every((d) => d.committed === null && d.offered.length === 0));
});

test("DecisionTracker: control order errors (seq over all profiles, ticks, one move per tick)", () => {
  const t = new sdk.DecisionTracker();
  assert.deepEqual(t.push(cd({ seq: 0, tick: 4 })).errors, []);
  const twice = t.push(cd({ seq: 1, tick: 4 }));
  assert.equal(twice.kind, "invalid");
  assert.equal(twice.forward, false);
  assert.match(twice.errors.join(), /second moving decision for tick 4/);
  assert.match(t.push(hold({ seq: 2, tick: 3 })).errors.join(), /tick 3 goes back/);
  assert.match(t.push(click({ seq: 2 })).errors.join(), /seq 2 does not increase/); // seq is shared with the intent profile
  const p = sdk.handleDecisions([cd({ is_final: false })])[0];
  assert.equal(p.kind, "invalid");
  assert.match(p.errors.join(), /MUST be final/);
});

test("DecisionTracker: control safety (CTL-S1, S3, S5)", () => {
  const out = sdk.handleDecisions([
    hold({ seq: 0, tick: 0, velocity: [3, 0] }),
    cd({ seq: 1, tick: 1, velocity: [400, 300], raw: [400, 300], gain: 1, state: "act" }),
    hold({ seq: 2, tick: 1, state: "stop", reasons: ["disengaged"] }),
    cd({ seq: 3, tick: 2 }),
    cd({ seq: 4, tick: 3, engagement: 2 }),
  ]);
  assert.match(out[0].errors.join(), /non-zero velocity/);
  assert.match(out[1].errors.join(), /above v_max/);
  assert.match(out[3].errors.join(), /motion after a stop without a new engagement/);
  assert.deepEqual(out[4].errors, []);
  assert.equal(out[4].forward, true);
});

test("DecisionTracker: CTL-S7 no intent COMMIT while the control is not engaged", () => {
  const before = sdk.handleDecisions([hold({ seq: 0, reasons: ["not_engaged"], engagement: 0 }), click({ seq: 1 })]);
  assert.equal(before[1].kind, "invalid");
  assert.equal(before[1].forward, false);
  assert.match(before[1].errors.join(), /not engaged \(rule 7\)/);
  const stopped = sdk.handleDecisions([cd({ seq: 0 }), hold({ seq: 1, state: "stop", reasons: ["disengaged"] }), click({ seq: 2 })]);
  assert.match(stopped[2].errors.join(), /not engaged/);
  const engaged = sdk.handleDecisions([cd({ seq: 0 }), click({ seq: 1 })]);
  assert.deepEqual(engaged[1].errors, []);
  assert.equal(engaged[1].committed, "intent.click");
  const reengaged = sdk.handleDecisions([hold({ seq: 0, state: "stop", reasons: ["disengaged"] }), hold({ seq: 1, tick: 1, engagement: 2 }), click({ seq: 2 })]);
  assert.deepEqual(reengaged[2].errors, []);
  // Only past decisions count: no control decision yet in the session, no CTL-S7 check.
  assert.deepEqual(sdk.handleDecisions([click({ seq: 0 }), hold({ seq: 1, reasons: ["not_engaged"], engagement: 0 })])[0].errors, []);
  // Another session is not affected.
  assert.deepEqual(sdk.handleDecisions([hold({ seq: 0, reasons: ["not_engaged"], engagement: 0 }), click({ seq: 1, session: "other" })])[1].errors, []);
});

test("fep0005.safetyErrors: CTL-S7 before the first engage and after a stop", () => {
  const notEng = hold({ seq: 0, reasons: ["not_engaged"], engagement: 0 });
  assert.match(sdk.fep0005.safetyErrors([notEng, click({ seq: 1 })]).join(), /not engaged \(rule 7\)/);
  assert.deepEqual(sdk.fep0005.safetyErrors([cd({ seq: 0 }), click({ seq: 1 })]), []);
  assert.deepEqual(sdk.fep0005.engagedAfter(hold({ state: "stop", engagement: 3 }), null), [false, 3]);
  assert.deepEqual(sdk.fep0005.engagedAfter(hold({ engagement: 3 }), 3), [false, 3]);
  assert.deepEqual(sdk.fep0005.engagedAfter(hold({ engagement: 4 }), 3), [true, null]);
  assert.deepEqual(sdk.fep0005.engagedAfter(hold({ engagement: 1, reasons: ["disengaged"] }), null), [false, null]);
});

test("validateSchema: the supported keywords", () => {
  const s = { type: "object", required: ["a"], properties: { a: { type: "integer", minimum: 0 }, b: { enum: ["x", null] } }, if: { properties: { a: { const: 1 } } }, then: { required: ["b"] } };
  assert.equal(sdk.validateSchema({ a: 2 }, s).length, 0);
  assert.equal(sdk.validateSchema({ a: 1 }, s).length, 1);
  assert.equal(sdk.validateSchema({ a: -1, b: "y" }, s).length, 2);
  assert.throws(() => sdk.validateSchema(1, { format: "date" }), /unsupported/);
});

test("validateEventSchema dispatches by type and profile", () => {
  assert.equal(sdk.schemaKeyFor({ type: "trust_decision", profile: "intent" }), "fep-0003/intent-trust-decision");
  assert.equal(sdk.validateEventSchema({ type: "acme.unknown" }).length, 0);
  assert.ok(sdk.validateEventSchema(td({ shown: [] })).some((e) => e.path === "/shown"));
  assert.ok(sdk.validateEventSchema({ type: "header", spec_version: "0.1", vocab: [], vocab_type: "char", blank_id: null, decode_declaration: { decoder: "" } })
    .some((e) => e.path === "/decode_declaration/decoder"));
});
