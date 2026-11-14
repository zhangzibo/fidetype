// FEP-0004 (NTS over WebSocket): the sans-IO cores and the browser decisions client, with a fake WebSocket.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as sdk from "../dist/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const conf = join(here, "..", "..", "..", "spec", "conformance", "fep-0004");

const td = (wsSeq, seq, utt, final = true, action = "COMMIT", text = "ab") => ({
  type: "trust_decision", session: "s1", seq, utterance: utt, is_final: final, action, shown: [text],
  p_top1: final ? 0.9 : 0.6, score_semantics: "calibrated_prob", set_size: 1, guard_risk: 0.1, ws_seq: wsSeq,
});
const WELCOME = { type: "ws_welcome", binding: "nts-ws/0.1", role: "decisions", seq: 0, first_available: 1 };

test("SubscriberCore: a gap asks for a resubscribe; duplicates are dropped", () => {
  const c = new sdk.SubscriberCore();
  assert.equal(c.receive(WELCOME), null);
  assert.equal(c.receive(td(1, 0, 0, false, "OFFER")), null);
  assert.deepEqual(c.receive(td(3, 2, 1, true, "COMMIT", "ba")), ["resubscribe", 2]);
  assert.equal(c.receive(td(4, 3, 2)), null); // ignored until the next welcome
  c.receive({ ...WELCOME, seq: 4 });
  c.receive(td(2, 1, 0));
  c.receive(td(3, 2, 1, true, "COMMIT", "ba"));
  c.receive(td(3, 2, 1, true, "COMMIT", "ba"));
  const s = c.finish();
  assert.deepEqual(s.acted, ["ab", "ba"]);
  assert.equal(s.duplicates, 1);
  assert.deepEqual(s.gaps, [2]);
  assert.throws(() => new sdk.SubscriberCore().receive(td(1, 0, 0)), /ws_welcome/);
});

test("IngestCore: header, frames, a broken connection and a lossless resume", () => {
  const core = new sdk.IngestCore();
  const hdr = { type: "header", spec_version: "0.1", vocab: ["<blank>", "a"], vocab_type: "char", blank_id: 0, ws: { stream_id: "s1" } };
  core.open(1);
  let eff = core.message(1, { value: hdr });
  assert.equal(eff.sends[0][1].type, "ws_welcome");
  const fr = (k) => ({ type: "frame", t: k * 0.04, log_probs: [-0.1, -2.4], ws_seq: k + 1 });
  core.message(1, { value: fr(0) });
  core.message(1, { text: JSON.stringify(fr(1)) });
  core.disconnect(1, 0.5);
  core.open(2);
  eff = core.message(2, { value: { ...hdr, ws: { stream_id: "s1", resume: true } } }, 1.0);
  assert.deepEqual([eff.sends[0][1].seq, eff.sends[0][1].resumed], [2, true]);
  eff = core.message(2, { value: { type: "ws_batch", events: [fr(1), fr(2)] } }, 1.0);
  assert.equal(core.stats.duplicates, 1);
  assert.deepEqual(eff.items.map(([, e]) => e.ws_seq), [3]);
  eff = core.message(2, { binary: true });
  assert.equal(eff.closes[0][1], 1003);
});

class FakeWS {
  static all = [];
  constructor(url, protocols) {
    this.url = url;
    this.protocols = protocols;
    this.readyState = 0;
    this.sent = [];
    this.onopen = this.onmessage = this.onclose = this.onerror = null;
    FakeWS.all.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.({});
    });
  }
  send(d) {
    this.sent.push(JSON.parse(d));
  }
  close(code = 1000, reason = "") {
    this.readyState = 3;
    queueMicrotask(() => this.onclose?.({ code, reason }));
  }
  deliver(m) {
    this.onmessage?.({ data: JSON.stringify(m) });
  }
}
const tick = () => new Promise((r) => setTimeout(r, 5));

test("DecisionSubscriber: resubscribes with from_seq after a gap and keeps the order", async () => {
  FakeWS.all = [];
  const got = [];
  const sub = new sdk.DecisionSubscriber("ws://x/decisions", {
    WebSocket: FakeWS, token: "t0k", reconnectDelayMs: 0, onDecision: (d, s) => got.push([s, d.kind, d.forward, d.committed]),
  });
  sub.start();
  await tick();
  const a = FakeWS.all[0];
  assert.deepEqual(a.protocols, ["nts-ws.0.1"]);
  assert.deepEqual(a.sent.map((m) => m.type), ["ws_auth", "ws_subscribe"]);
  a.deliver(WELCOME);
  a.deliver(td(1, 0, 0, false, "OFFER"));
  a.deliver(td(3, 2, 1, true, "COMMIT", "ba")); // ws_seq 2 is missing
  await tick();
  await tick();
  const b = FakeWS.all[1];
  assert.ok(b, "a second connection");
  assert.equal(b.sent.find((m) => m.type === "ws_subscribe").from_seq, 2);
  b.deliver({ ...WELCOME, seq: 3, replayed: 2 });
  b.deliver(td(2, 1, 0));
  b.deliver(td(3, 2, 1, true, "COMMIT", "ba"));
  sub.stop();
  assert.deepEqual(got.map((g) => g[0]), [1, 2, 3]);
  assert.deepEqual(got.map((g) => g[2]), [false, true, true]);
  assert.deepEqual(got.filter((g) => g[2]).map((g) => g[3]), ["ab", "ba"]);
});

test("fep-0004: each reject vector fails its named check", () => {
  const m = JSON.parse(readFileSync(join(conf, "manifest.json"), "utf8"));
  for (const v of m.vectors) {
    const rep = sdk.fep0004.checkFile(v.file, new Uint8Array(readFileSync(join(conf, v.file))));
    const fails = rep.checks.filter((c) => c.status === "fail").map((c) => c.id);
    if (v.expect === "accept") assert.deepEqual(fails, [], v.id);
    else assert.ok(fails.includes(v.failing_check), `${v.id}: ${fails} lacks ${v.failing_check}`);
  }
});
