/**
 * Conformance profile `fep-0004`: NeuralTextStream over WebSocket (port of
 * `fidetype.conformance.profiles.fep0004`). Each vector is a JSON scenario
 * (schema `fidetype.conformance.ws-scenario/1`).
 *
 * `ingest` scenarios run through {@link IngestCore}. As in `fep-0002`, the
 * decision counts come from the structural model of the reference trust
 * layer (see `lsl.ts`); all other values come from the same binding logic
 * as the Python reference.
 */

import { StreamRejected } from "../checks.js";
import { decodeUtf8, has, isFloatLiteral, isIntAt, isObj, markFloat, parseJson } from "../json.js";
import { CheckMeta, TargetReport, makeRes } from "./common.js";
import { StructuralLayer } from "./lsl.js";
import { IngestCore, SubscriberCore, SubscriberError, WS_REFUSAL_CODES, WS_SUBPROTOCOL, ingestSettings } from "../ws.js";
import type { Effects, WsData } from "../ws.js";

export const FEP = "FEP-0004";
export const SUFFIXES = [".json"];
export const SCENARIO_SCHEMA = "fidetype.conformance.ws-scenario/1";
const STEP_KINDS = ["open", "msg", "raw", "binary", "drop", "close", "tick"];
const SETTING_KEYS = ["reorder_window", "reorder_timeout_s", "resume_timeout_s", "max_batch", "ack_every", "window", "ack_interval_s", "token"];

export const CHECKS: CheckMeta[] = [
  ["FEP4-HANDSHAKE", "MUST", "4-5", "Subprotocol nts-ws.0.1; the first message is the NTS header with a known binding"],
  ["FEP4-FRAMING", "MUST", "3, 6", "Text messages with one JSON object each; ws_seq on every event; batches consecutive"],
  ["FEP4-ORDER", "MUST", "6", "Duplicates dropped, reorder window, gaps drop the open utterance"],
  ["FEP4-RESUME", "MUST", "8", "Resume after a broken connection; no decision on a cut utterance"],
  ["FEP4-AUTH", "MUST", "9", "Token hook: a refused token closes with 1008"],
  ["FEP4-DECISIONS", "MUST", "7", "Decisions channel: welcome, ws_seq without gaps (or resubscribe), FEP-0001 rules"],
  ["FEP4-CONSUME", "MUST", "3-8", "The reference consumer accepts the scenario"],
];
const META = Object.fromEntries(CHECKS.map((c) => [c[0], c]));
const res = makeRes(META, FEP);

type Obj = Record<string, unknown>;
const finNum = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);

/** The runner part of `WSTrustRunner` with the structural layer: one layer per stream. */
class Runner {
  layers = new Map<string, StructuralLayer>();
  skip = new Set<string>();
  decisions = 0;
  finals = 0;
  aborted = 0;
  skipped = 0;
  sessions = new Set<string>();

  constructor(readonly route: "frames" | "hypothesis") {}

  private layer(sid: string): StructuralLayer {
    let l = this.layers.get(sid);
    if (!l) {
      l = new StructuralLayer(this.route);
      this.layers.set(sid, l);
    }
    return l;
  }

  private count(sid: string, l: StructuralLayer, d0: number, f0: number): void {
    if (l.decisions > d0) this.sessions.add(sid);
    this.decisions += l.decisions - d0;
    this.finals += l.finals - f0;
  }

  private abort(sid: string): void {
    const l = this.layers.get(sid);
    if (l && l.pending()) this.aborted++;
    if (l) l.abort();
  }

  handle(items: [string, Obj][]): void {
    for (const [sid, ev] of items) {
      const typ = ev.type;
      if (typ === "ws_status") {
        const st = ev.status;
        if (st === "gap") {
          this.abort(sid);
          this.skip.add(sid);
        } else if (st === "lost" || st === "replaced") {
          this.abort(sid);
          this.skip.delete(sid);
        } else if (st === "closed") {
          const l = this.layers.get(sid);
          if (l) {
            const [d0, f0] = [l.decisions, l.finals];
            l.end();
            this.count(sid, l, d0, f0);
            this.layers.delete(sid);
          }
        }
        continue;
      }
      if (this.skip.has(sid)) {
        if (typ === "frame") {
          this.skipped++;
          continue;
        }
        if (typ === "segment_end" || typ === "end" || typ === "header") this.skip.delete(sid);
      }
      const l = this.layer(sid);
      const [d0, f0] = [l.decisions, l.finals];
      l.push(ev);
      this.count(sid, l, d0, f0);
    }
  }

  flush(sid: string): void {
    const l = this.layer(sid);
    const [d0, f0] = [l.decisions, l.finals];
    l.end();
    this.count(sid, l, d0, f0);
  }
}

/** The profile check that a refusal (close code, ws_error code, detail) fails. */
export function refusalCheck(code: number, reason: string, detail: string): string {
  if (code === 1008) return "FEP4-AUTH";
  if (code === 1002 || code === 4000 || (reason === "bad_header" && !detail.includes("resume"))) return "FEP4-HANDSHAKE";
  if (reason === "bad_header") return "FEP4-RESUME";
  return "FEP4-FRAMING";
}

/** Play an `ingest` scenario. Throws on rejection. */
export function runIngestScenario(sc: Obj): Record<string, unknown> {
  const settings = has(sc, "settings") ? sc.settings : {};
  if (!isObj(settings)) throw new TypeError("settings must be an object");
  const bad = Object.keys(settings).filter((k) => !SETTING_KEYS.includes(k));
  if (bad.length) throw new TypeError(`unknown settings ${bad.join(", ")}`);
  const token = has(settings, "token") ? settings.token : null;
  if (token !== null && !(typeof token === "string" && token.length > 0)) throw new TypeError("settings.token must be a non-empty string");
  const rest: Obj = {};
  for (const k of Object.keys(settings)) if (k !== "token") rest[k] = settings[k];
  const s = ingestSettings(copyMarks(settings, rest));
  const route = has(sc, "route") ? sc.route : "frames";
  if (route !== "frames" && route !== "hypothesis") throw new RangeError(`unknown route ${JSON.stringify(route)}`);
  const steps = has(sc, "steps") ? sc.steps : null;
  if (!Array.isArray(steps)) throw new TypeError("steps must be a list");
  const core = new IngestCore(s, token !== null ? (t) => t === token : null);
  const runner = new Runner(route);
  const seen: Obj[] = [];
  const sends: Obj[] = [];
  const closes: number[][] = [];

  const apply = (eff: Effects): void => {
    for (const [, m] of eff.sends) sends.push(m);
    for (const [cid, code, reason] of eff.closes) {
      closes.push([cid, code]);
      if (WS_REFUSAL_CODES.includes(code)) {
        const err = eff.sends.find(([c, m]) => c === cid && m.type === "ws_error");
        const detail = err ? String(err[1].detail ?? "") : reason;
        throw new StreamRejected(`connection ${cid} refused with close code ${code} (${reason}: ${detail})`, `${FEP} 9`,
          refusalCheck(code, reason, detail));
      }
    }
    for (const [, ev] of eff.items) if (ev.type !== "ws_status") seen.push(ev);
    runner.handle(eff.items);
  };

  let at = 0;
  steps.forEach((step, k) => {
    const n = k + 1;
    if (!isObj(step)) throw new TypeError(`step ${n} must be an object`);
    const kinds = STEP_KINDS.filter((x) => has(step, x));
    if (kinds.length !== 1) throw new TypeError(`step ${n} needs exactly one step kind`);
    const kind = kinds[0];
    const t = has(step, "at") ? step.at : at;
    if (!(finNum(t) && t >= at)) throw new RangeError(`step ${n}: at must be a number >= the previous at`);
    at = t;
    apply(core.tick(at));
    if (kind === "tick") return;
    if (!(isIntAt(step, "conn") && (step.conn as number) >= 1)) throw new RangeError(`step ${n}: conn must be an integer >= 1`);
    const cid = step.conn as number;
    if (kind === "open") {
      const o = step.open;
      if (!isObj(o)) throw new TypeError(`step ${n}: open must be an object`);
      const subs = has(o, "subprotocols") ? o.subprotocols : [WS_SUBPROTOCOL];
      if (!(Array.isArray(subs) && subs.every((x) => typeof x === "string"))) throw new TypeError(`step ${n}: subprotocols must be a list of strings`);
      const auth = has(o, "authorization") ? o.authorization : null;
      if (auth !== null && typeof auth !== "string") throw new TypeError(`step ${n}: authorization must be a string`);
      apply(core.open(cid, subs as string[], auth as string | null));
    } else if (kind === "msg") {
      apply(core.message(cid, { value: step.msg } as WsData, at));
    } else if (kind === "raw") {
      if (typeof step.raw !== "string") throw new TypeError(`step ${n}: raw must be a string`);
      apply(core.message(cid, { text: step.raw }, at));
    } else if (kind === "binary") {
      if (step.binary !== true) throw new TypeError(`step ${n}: binary must be true`);
      apply(core.message(cid, { binary: true }, at));
    } else {
      if (step[kind] !== true) throw new TypeError(`step ${n}: ${kind} must be true`);
      apply(core.disconnect(cid, at));
    }
  });
  apply(core.finish());
  for (const sid of core.liveStreams()) runner.flush(sid);
  const types = new Map<string, number>();
  for (const e of seen) types.set(e.type as string, (types.get(e.type as string) ?? 0) + 1);
  const st = core.stats;
  const cmp = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0);
  return {
    streams: st.streams,
    event_types: Object.fromEntries([...types.entries()].sort(([a], [b]) => cmp(a, b))),
    frames: types.get("frame") ?? 0,
    decisions: runner.decisions,
    final_decisions: runner.finals,
    sessions: [...runner.sessions].sort(cmp),
    aborted_utterances: runner.aborted,
    skipped_after_gap: runner.skipped,
    duplicates: st.duplicates, reordered: st.reordered, gaps: st.gaps, missing_events: st.missing_events, resumes: st.resumes,
    takeovers: st.takeovers, lost_streams: st.lost_streams, ignored_controls: st.ignored_controls,
    welcomes: sends.filter((m) => m.type === "ws_welcome").map((m) => [m.stream_id, m.seq, m.resumed]),
    acks: sends.filter((m) => m.type === "ws_ack").map((m) => m.seq),
    closes,
  };
}

/** Copy the float-literal marks of `from` onto the same keys of `to` (the settings check needs them). */
function copyMarks(from: Obj, to: Obj): Obj {
  for (const k of Object.keys(to)) if (isFloatLiteral(from, k)) markFloat(to, k);
  return to;
}

/** Feed a `subscribe` scenario to the reference subscriber. Throws on rejection. */
export function runSubscribeScenario(sc: Obj): Record<string, unknown> {
  const msgs = has(sc, "messages") ? sc.messages : null;
  if (!Array.isArray(msgs)) throw new TypeError("messages must be a list");
  const fromSeq = has(sc, "from_seq") ? sc.from_seq : 1;
  if (has(sc, "from_seq") && fromSeq !== null && !(isIntAt(sc, "from_seq") && (fromSeq as number) >= 1)) throw new TypeError("from_seq must be an integer >= 1 or null");
  const core = new SubscriberCore(fromSeq as number | null);
  try {
    for (const m of msgs) core.receive(m);
    return core.finish();
  } catch (e) {
    if (e instanceof SubscriberError) throw new StreamRejected(e.message, `${FEP} 7`);
    throw e;
  }
}

export function loadScenario(bytes: Uint8Array): Obj {
  const sc = parseJson(decodeUtf8(bytes), { allowConstants: true });
  if (!isObj(sc) || sc.schema !== SCENARIO_SCHEMA || (sc.kind !== "ingest" && sc.kind !== "subscribe")) {
    throw new StreamRejected(`not a ${SCENARIO_SCHEMA} scenario`, FEP);
  }
  return sc;
}

/** Reference consumer of the profile: return a summary, or throw. */
export function consume(_name: string, bytes: Uint8Array): Record<string, unknown> {
  const sc = loadScenario(bytes);
  return sc.kind === "ingest" ? runIngestScenario(sc) : runSubscribeScenario(sc);
}

/** Producer check: a scenario `.json` file. */
export function checkFile(name: string, bytes: Uint8Array): TargetReport {
  let sc: Obj;
  try {
    sc = loadScenario(bytes);
  } catch (e) {
    return { target: name, checks: [res("FEP4-CONSUME", [`${(e as Error).name}: ${(e as Error).message}`])], info: { format: "ws-scenario" } };
  }
  const cid = sc.kind === "subscribe" ? "FEP4-DECISIONS" : "FEP4-CONSUME";
  let r;
  try {
    if (sc.kind === "ingest") runIngestScenario(sc);
    else runSubscribeScenario(sc);
    r = res(cid, [], "accepted");
  } catch (e) {
    const id = e instanceof StreamRejected && e.checkId ? e.checkId : cid;
    r = res(id, [`${(e as Error).name}: ${(e as Error).message}`]);
  }
  return { target: name, checks: [r], info: { format: "ws-scenario", kind: sc.kind } };
}

/** Keys of the ingest summary that the structural trust model computes from counts only. */
export const STRUCTURAL_KEYS = ["decisions", "final_decisions", "aborted_utterances", "sessions"];
