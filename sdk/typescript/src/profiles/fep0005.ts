/**
 * Conformance profile `fep-0005`: continuous-control events (port of
 * `fidetype.conformance.profiles.fep0005` and the validators of
 * `fidetype.trust.control`).
 *
 * Input streams (line 1 = header) carry a `control_declaration`, `control`,
 * `control_enable` and v0.1 `pointer` events, and may carry FEP-0003 intent
 * events (a click). Decision logs hold only `trust_decision` lines; control
 * decisions have `profile = "control"`. For a decision log the consumer
 * returns `moving_ticks` (the "acted" list of control COMMITs, NTS 1.0 6.4),
 * `acted_intents` and `acted_texts`.
 */

import { INTENT_DECLARATION_KEY } from "../constants.js";
import { get, has, isFinNum, isObj } from "../json.js";
import { CheckMeta, Ev, TargetReport, isInt, makeRes, readEvents, rejectOnFailure, repr, streamKind } from "./common.js";
import { tdFormatErrors, v01CoreFailures } from "./fep0001.js";
import * as f3 from "./fep0003.js";

export const FEP = "FEP-0005";
export const SUFFIXES = [".jsonl", ".ndjson"];
export const CONTROL_DECLARATION_KEY = "control_declaration";
const CONTROL = "control";
const CONTROL_ENABLE = "control_enable";
const PROFILE = "control";

export const QUANTITIES = ["velocity", "position"] as const;
export const UNITS: Record<string, readonly string[]> = {
  velocity: ["norm/s", "px/s", "mm/s", "m/s", "deg/s"],
  position: ["norm", "px", "mm", "m", "deg"],
};
export const FRAMES = ["screen", "workspace"] as const;
export const UNCERTAINTY = ["none", "std"] as const;
export const SOURCES = ["decoder", "human"] as const;
export const STATES = ["act", "attenuate", "hold", "stop"] as const;
export const ENABLE_SOURCES = ["switch", "caregiver", "ui", "voice", "eye-tracker", "watchdog", "other"] as const;
const TIMING_FIELDS = ["t_signal_start", "t_signal_end", "t_decoded", "t_emitted"];
const CONTROL_ACTIONS = ["COMMIT", "ABSTAIN"];
const MOVING = ["act", "attenuate"];
/** Reasons that mean "no signal / no engagement": a decision with one of them MUST NOT move. */
export const NO_MOTION_REASONS = ["no_signal", "no_signal_reference", "stale_input", "disengaged", "not_engaged", "absent"];
const SPEED_TOL = 1e-6;

export const CHECKS: CheckMeta[] = [
  ["FEP5-PARSE", "MUST", "1 (6.2 v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"],
  ["FEP5-KIND", "MUST", "1", "The file is an input stream (header first) or a decision log (only trust_decision)"],
  ["FEP5-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"],
  ["FEP5-DECL", "MUST", "2 table, r1-r4", "control_declaration has the defined form (dims, quantity, units, frame, rate, click intent)"],
  ["FEP5-CONTROL", "MUST", "3 table, r1-r4", "control and pointer events: declared, dims values, std per declaration, tick and t increase"],
  ["FEP5-ENABLE", "MUST", "4 table", "control_enable events have the defined form"],
  ["FEP5-INTENT", "MUST", "5 r6 (FEP-0003 2-4)", "Intent parts of the stream follow FEP-0003"],
  ["FEP5-TD-FORMAT", "MUST", "5 table, r1-r4", "Control trust_decision fields (profile, tick, state, velocity, gain, v_max, ttl_s, engagement; no shown)"],
  ["FEP5-TD-ORDER", "MUST", "5 r5", "Per session: seq increases over all profiles; control decisions are final; a moving tick is never reused"],
  ["FEP5-SAFETY", "MUST", "6 r1-r7", "No motion on hold/stop or no-signal reasons; speed <= v_max; re-engage after stop; no intent COMMIT while stopped"],
];
const META = Object.fromEntries(CHECKS.map((c) => [c[0], c]));
const res = makeRes(META, FEP);

const inList = (x: unknown, list: readonly string[]): boolean => typeof x === "string" && list.includes(x);
/** Python `a == b` for a JSON value and a number (True == 1). */
const numEq = (a: unknown, b: number): boolean => (typeof a === "number" && a === b) || (typeof a === "boolean" && Number(a) === b);
const isControl = (e: Record<string, unknown>): boolean => get(e, "type") === "trust_decision" && get(e, "profile") === PROFILE;
const isIntentTd = (e: Record<string, unknown>): boolean => get(e, "type") === "trust_decision" && get(e, "profile") === "intent";
const lineOf = (e: Record<string, unknown>): unknown => (has(e, "_line") ? e._line : "?");
const sessionKey = (e: Record<string, unknown>): string => JSON.stringify(has(e, "session") ? e.session : "");

/**
 * Python `math.sqrt(sum(float(v) ** 2 for v in xs))`. Python raises OverflowError when a square
 * overflows (any exception is a rejection); here that gives null.
 */
function norm(xs: number[]): number | null {
  let s = 0;
  for (const v of xs) {
    const q = v * v;
    if (!Number.isFinite(q)) return null;
    s += q;
  }
  return Math.sqrt(s);
}

/** The parsed form of a valid declaration (only the fields the event rules need). */
export interface ControlDeclaration {
  dims: number;
  uncertainty: string;
}

/** The FEP-0005 section 2 errors of a `control_declaration` (empty = valid). `intentIds`: null = no intent declaration. */
export function validateControlDeclaration(d: unknown, intentIds: string[] | null = null, nullIntents: string[] = []): string[] {
  if (!isObj(d)) return ["control_declaration must be an object"];
  const e: string[] = [];
  const dims = get(d, "dims");
  const dimsInt = isInt(d, "dims");
  if (!(dimsInt && (dims as number) >= 1 && (dims as number) <= 3)) e.push("dims must be an integer 1-3");
  const q = get(d, "quantity");
  if (!inList(q, QUANTITIES)) e.push(`quantity ${repr(q)} is not one of ${repr(QUANTITIES)}`);
  else if (!inList(get(d, "units"), UNITS[q as string])) e.push(`units ${repr(get(d, "units"))} do not fit quantity ${repr(q)} (one of ${repr(UNITS[q as string])})`);
  if (!inList(get(d, "frame"), FRAMES)) e.push(`frame ${repr(get(d, "frame"))} is not one of ${repr(FRAMES)}`);
  const rate = get(d, "rate_hz");
  if (!(isFinNum(rate) && rate > 0)) e.push("rate_hz must be a number > 0");
  if (has(d, "axes")) {
    const ax = d.axes;
    const ok = Array.isArray(ax) && ax.every((a) => typeof a === "string" && a.length > 0) && new Set(ax).size === ax.length
      && (!dimsInt || ax.length === dims);
    if (!ok) e.push("axes must be a list of dims unique non-empty strings");
  }
  const unc = has(d, "uncertainty") ? d.uncertainty : "none";
  if (!inList(unc, UNCERTAINTY)) e.push(`uncertainty ${repr(get(d, "uncertainty"))} is not one of ${repr(UNCERTAINTY)}`);
  for (const k of ["max_speed", "latency_s", "window_s"]) {
    if (has(d, k)) {
      const v = d[k];
      if (!(isFinNum(v) && v >= 0 && (k !== "max_speed" || v > 0))) e.push(`${k} must be a number ${k === "max_speed" ? "> 0" : ">= 0"}`);
    }
  }
  if (q === "position" && get(d, "units") === "norm" && get(d, "frame") !== "screen") {
    e.push("normalised position (units norm) is defined only in the screen frame");
  }
  if (has(d, "click_intent")) {
    const ci = d.click_intent;
    if (typeof ci !== "string") e.push("click_intent must be a string");
    else if (intentIds === null) e.push("click_intent needs an intent_declaration (FEP-0003) in the same header");
    else if (!intentIds.includes(ci)) e.push(`click_intent '${ci}' is not a declared intent`);
    else if (nullIntents.includes(ci)) e.push(`click_intent '${ci}' has role null`);
  }
  return e;
}

/** The FEP-0005 section 3 errors of one `control` event, without the order rules. */
export function validateControlEvent(ev: Record<string, unknown>, decl: ControlDeclaration | null): string[] {
  if (decl === null) return ["control event without a control_declaration in the header (rule 1)"];
  const e: string[] = [];
  if (!isFinNum(get(ev, "t"))) e.push("t must be a finite number");
  if (!(isInt(ev, "tick") && (ev.tick as number) >= 0)) e.push("tick must be an integer >= 0");
  let vals = get(ev, "values") as unknown[] | null;
  if (!(Array.isArray(vals) && vals.length === decl.dims)) {
    e.push(`values must be a list of dims = ${decl.dims} numbers`);
    vals = null;
  }
  let absent = get(ev, "absent") as unknown[] | null;
  if (absent !== null && !(Array.isArray(absent) && absent.length === decl.dims && absent.every((a) => typeof a === "boolean"))) {
    e.push("absent must be a list of dims booleans");
    absent = null;
  }
  if (vals !== null) {
    vals.forEach((v, j) => {
      if (absent !== null && absent[j] === true) return;
      if (!isFinNum(v)) e.push(`values[${j}] must be a finite number (or absent)`);
    });
  }
  const src = has(ev, "source") ? ev.source : "decoder";
  if (!inList(src, SOURCES)) e.push(`source ${repr(src)} is not one of ${repr(SOURCES)}`);
  if (has(ev, "std")) {
    const sd = ev.std;
    if (!(Array.isArray(sd) && sd.length === decl.dims && sd.every((x) => isFinNum(x) && x > 0))) e.push("std must be a list of dims numbers > 0");
    else if (decl.uncertainty !== "std") e.push("std given but the declaration has uncertainty = none (rule 3)");
  } else if (decl.uncertainty === "std" && src === "decoder") {
    e.push("the declaration has uncertainty = std: a decoder control event MUST carry std (rule 3)");
  }
  const ts = TIMING_FIELDS.filter((k) => has(ev, k)).map((k) => ev[k]);
  if (ts.some((x) => !isFinNum(x))) e.push("timing fields must be finite numbers");
  else if ((ts as number[]).some((x, k) => k > 0 && x < (ts[k - 1] as number))) {
    e.push("timing fields must satisfy t_signal_start <= t_signal_end <= t_decoded <= t_emitted (v0.1 3.8)");
  }
  if (has(ev, "id") && typeof ev.id !== "string") e.push("id must be a string");
  return e;
}

/** The FEP-0005 section 4 errors of one `control_enable` event. */
export function validateEnableEvent(ev: Record<string, unknown>): string[] {
  const e: string[] = [];
  if (typeof get(ev, "enabled") !== "boolean") e.push("enabled must be a boolean");
  if (has(ev, "t") && !isFinNum(ev.t)) e.push("t must be a finite number");
  if (has(ev, "source") && !inList(ev.source, ENABLE_SOURCES)) e.push(`source ${repr(ev.source)} is not one of ${repr(ENABLE_SOURCES)}`);
  if (has(ev, "reason") && typeof ev.reason !== "string") e.push("reason must be a string");
  return e;
}

// --- input rules ---------------------------------------------------------------------------

/** (declared intent ids, null-role intent ids) of a header's valid FEP-0003 declaration; [null, []] otherwise. */
function intentIds(h: Record<string, unknown>): [string[] | null, string[]] {
  const d = get(h, INTENT_DECLARATION_KEY);
  if (isObj(d) && !f3.validateIntentDeclaration(d).length) {
    const its = d.intents as Record<string, unknown>[];
    return [its.map((it) => it.id as string), its.filter((it) => get(it, "role") === "null").map((it) => it.id as string)];
  }
  return [null, []];
}

export function declErrors(events: Ev[]): string[] {
  const out: string[] = [];
  for (const h of events) {
    if (h.type === "header" && has(h, CONTROL_DECLARATION_KEY)) {
      const [ids, nulls] = intentIds(h);
      out.push(...validateControlDeclaration(h[CONTROL_DECLARATION_KEY], ids, nulls).map((x) => `line ${h._line}: ${x}`));
    }
  }
  return out;
}

export function controlErrors(events: Ev[]): string[] {
  const out: string[] = [];
  let decl: ControlDeclaration | null = null;
  let hasDecl = false;
  let lastTick: number | null = null;
  let lastT: number | null = null;
  for (const e of events) {
    const n = lineOf(e);
    if (e.type === "header") {
      hasDecl = has(e, CONTROL_DECLARATION_KEY);
      [decl, lastTick, lastT] = [null, null, null];
      if (hasDecl) {
        const [ids, nulls] = intentIds(e);
        const d = e[CONTROL_DECLARATION_KEY];
        if (!validateControlDeclaration(d, ids, nulls).length) {
          const dd = d as Record<string, unknown>;
          decl = { dims: dd.dims as number, uncertainty: has(dd, "uncertainty") ? (dd.uncertainty as string) : "none" };
        }
      }
    } else if (e.type === CONTROL) {
      if (!hasDecl) {
        out.push(`line ${n}: control event without a control_declaration in the header (rule 1)`);
        continue;
      }
      if (decl === null) continue; // FEP5-DECL reports it
      const errs = validateControlEvent(e, decl);
      out.push(...errs.map((x) => `line ${n}: ${x}`));
      if (errs.length || (has(e, "source") ? e.source : "decoder") !== "decoder") continue;
      const tick = e.tick as number;
      const t = e.t as number;
      if (lastTick !== null && tick <= lastTick) out.push(`line ${n}: tick ${tick} does not increase (rule 2)`);
      if (lastT !== null && t <= lastT) out.push(`line ${n}: t ${t} does not increase (rule 2)`);
      [lastTick, lastT] = [tick, t];
    } else if (e.type === "pointer" && hasDecl && decl !== null) {
      if (!numEq(get(e, "dims"), decl.dims)) out.push(`line ${n}: pointer dims ${repr(get(e, "dims"))} != declared dims ${decl.dims} (rule 4)`);
    }
  }
  return out;
}

export function enableErrors(events: Ev[]): string[] {
  return events.filter((e) => e.type === CONTROL_ENABLE).flatMap((e) => validateEnableEvent(e).map((x) => `line ${e._line}: ${x}`));
}

export function intentCompatErrors(events: Ev[]): string[] {
  return [...f3.declErrors(events), ...f3.vocabErrors(events), ...f3.intentErrors(events), ...f3.feedbackErrors(events)];
}

// --- decision-log rules ----------------------------------------------------------------------

/** Format errors of one trust_decision: section 5 for control decisions, FEP-0003 / FEP-0001 for the others. */
export function tdControlFormatErrors(e: Record<string, unknown>): string[] {
  if (!isControl(e)) return f3.tdIntentFormatErrors(e);
  const errs = tdFormatErrors(e);
  const n = lineOf(e);
  const x: string[] = [];
  for (const k of ["shown", "utterance", "unit"]) if (has(e, k)) x.push(`a control decision MUST NOT carry ${k} (rule 1)`);
  if (!(isInt(e, "tick") && (e.tick as number) >= 0)) x.push("tick must be an integer >= 0");
  if (get(e, "is_final") !== true) x.push("a control decision MUST be final (is_final = true) (rule 2)");
  const act = get(e, "action");
  const st = get(e, "state");
  if (!inList(act, CONTROL_ACTIONS)) x.push(`control action ${repr(act)} is not one of ${repr(CONTROL_ACTIONS)}`);
  if (!inList(st, STATES)) x.push(`state ${repr(st)} is not one of ${repr(STATES)}`);
  else if (inList(act, CONTROL_ACTIONS) && MOVING.includes(st as string) !== (act === "COMMIT")) {
    x.push(`state ${repr(st)} does not fit action ${repr(act)} (act/attenuate = COMMIT, hold/stop = ABSTAIN) (rule 3)`);
  }
  const vel = get(e, "velocity");
  if (!(Array.isArray(vel) && vel.length >= 1 && vel.length <= 3 && vel.every(isFinNum))) x.push("velocity must be a list of 1-3 finite numbers");
  if (has(e, "raw")) {
    const raw = e.raw;
    if (!(Array.isArray(raw) && raw.every(isFinNum) && (!Array.isArray(vel) || raw.length === vel.length))) x.push("raw must be a list of finite numbers, one per axis");
  }
  const gain = get(e, "gain");
  if (!(isFinNum(gain) && gain >= 0 && gain <= 1)) x.push("gain must be a number in [0, 1]");
  if (typeof get(e, "units") !== "string") x.push("units is required (string)");
  const vmax = get(e, "v_max");
  if (!(isFinNum(vmax) && vmax > 0)) x.push("v_max is required: a number > 0 (rule 4)");
  const ttl = get(e, "ttl_s");
  if (!(isFinNum(ttl) && ttl > 0)) x.push("ttl_s is required: a number > 0 (rule 4)");
  if (!(isInt(e, "engagement") && (e.engagement as number) >= 0)) x.push("engagement is required: an integer >= 0");
  if (has(e, "authority") && !(isFinNum(e.authority) && e.authority >= 0 && e.authority <= 1)) x.push("authority must be a number in [0, 1]");
  if (has(e, "radius")) {
    if (!(isFinNum(e.radius) && e.radius >= 0)) x.push("radius must be a number >= 0");
    const lv = get(e, "level");
    if (!(isFinNum(lv) && lv > 0 && lv < 1)) x.push("a decision with radius needs level in (0, 1)");
  }
  if (has(e, "reasons") && !(Array.isArray(e.reasons) && e.reasons.every((r) => typeof r === "string"))) x.push("reasons must be a list of strings");
  if (has(e, "t") && !isFinNum(e.t)) x.push("t must be a finite number");
  return [...errs, ...x.map((m) => `line ${n}: ${m}`)];
}

/** seq over all profiles; text / intent finals as FEP-0003; control: ticks do not go back, a moving tick is never reused. */
export function tdOrderErrors(events: Record<string, unknown>[]): string[] {
  const errs = f3.tdFinalErrors(events.filter((e) => !isControl(e)));
  const lastSeq = new Map<string, number>();
  const lastMove = new Map<string, number>();
  const lastTick = new Map<string, number>();
  for (const e of events) {
    const sidRaw = has(e, "session") ? e.session : "";
    if (get(e, "type") !== "trust_decision" || typeof sidRaw !== "string") continue;
    const sid = sidRaw;
    const n = lineOf(e);
    if (isInt(e, "seq")) {
      const seq = e.seq as number;
      if (lastSeq.has(sid) && seq <= (lastSeq.get(sid) as number)) errs.push(`line ${n}: seq ${seq} does not increase in session '${sid}' (rule 5)`);
      lastSeq.set(sid, Math.max(seq, lastSeq.get(sid) ?? seq));
    }
    if (!isControl(e) || !isInt(e, "tick")) continue;
    const tick = e.tick as number;
    if (lastTick.has(sid) && tick < (lastTick.get(sid) as number)) errs.push(`line ${n}: tick ${tick} goes back in session '${sid}' (rule 5)`);
    lastTick.set(sid, Math.max(tick, lastTick.get(sid) ?? tick));
    if (get(e, "action") === "COMMIT") {
      if (lastMove.has(sid) && tick <= (lastMove.get(sid) as number)) errs.push(`line ${n}: a second moving decision for tick ${tick} (rule 5: one input moves once)`);
      lastMove.set(sid, tick);
    }
  }
  return [...new Set(errs)];
}

/** Section 6: no motion on hold / stop or no-signal reasons, speed bound, re-engage after a stop, no intent COMMIT while stopped. */
export function safetyErrors(events: Record<string, unknown>[]): string[] {
  const errs = f3.safetyErrors(events.filter((e) => !isControl(e)));
  // session -> engagement of the latched stop (-1 if not an integer); absent = not stopped (Python None).
  const stopped = new Map<string, number>();
  for (const e of events) {
    if (get(e, "type") !== "trust_decision") continue;
    const sid = sessionKey(e);
    const n = lineOf(e);
    if (!isControl(e)) {
      if (isIntentTd(e) && get(e, "is_final") === true && get(e, "action") === "COMMIT" && stopped.has(sid)) {
        errs.push(`line ${n}: intent COMMIT while the control is stopped (rule 7)`);
      }
      continue;
    }
    const vel = get(e, "velocity");
    if (!(Array.isArray(vel) && vel.every(isFinNum))) continue;
    const sp = norm(vel as number[]);
    if (sp === null) {
      errs.push(`line ${n}: velocity too large (Python OverflowError)`);
      continue;
    }
    const act = get(e, "action");
    const st = get(e, "state");
    const eng = get(e, "engagement");
    const reasons = Array.isArray(get(e, "reasons")) ? (e.reasons as unknown[]) : [];
    const gain = get(e, "gain");
    if (act === "ABSTAIN" && sp !== 0) errs.push(`line ${n}: a ${repr(st)} decision with non-zero velocity (rule 1)`);
    if (act === "ABSTAIN" && isFinNum(gain) && gain !== 0) errs.push(`line ${n}: a ${repr(st)} decision with gain ${gain} (rule 1)`);
    if (act === "COMMIT") {
      const bad = reasons.filter((r) => inList(r, NO_MOTION_REASONS));
      if (bad.length) errs.push(`line ${n}: a moving decision with the no-motion reason(s) ${repr(bad)} (rule 2)`);
      const vmax = get(e, "v_max");
      if (isFinNum(vmax) && sp > vmax * (1 + SPEED_TOL) + SPEED_TOL) errs.push(`line ${n}: speed ${sp} above v_max ${vmax} (rule 3)`);
      if (sp === 0) errs.push(`line ${n}: a COMMIT with zero velocity (use hold) (rule 1)`);
      if (stopped.has(sid) && numEq(eng, stopped.get(sid) as number)) errs.push(`line ${n}: motion after a stop without a new engagement (rule 5)`);
      const raw = get(e, "raw");
      if (has(e, "raw") && Array.isArray(raw) && raw.every(isFinNum) && isFinNum(gain)) {
        const rs = norm(raw as number[]);
        if (rs === null) {
          errs.push(`line ${n}: raw too large (Python OverflowError)`);
          continue;
        }
        const auth = has(e, "authority") ? e.authority : 1.0;
        if (rs > 0 && numEq(auth, 1) && sp > rs * (1 + SPEED_TOL) + SPEED_TOL) {
          errs.push(`line ${n}: output faster than the decoder output at full authority (rule 6)`);
        }
      }
    }
    if (st === "stop") stopped.set(sid, isInt(e, "engagement") ? (eng as number) : -1);
    else if (act === "COMMIT" && isInt(e, "engagement") && stopped.has(sid) && eng !== stopped.get(sid)) stopped.delete(sid);
  }
  return errs;
}

/** The "acted" list of control decisions (NTS 1.0 6.4): the tick of each final control COMMIT. */
export function movingTicks(decisions: Record<string, unknown>[]): number[] {
  return decisions
    .filter((e) => isControl(e) && get(e, "is_final") === true && get(e, "action") === "COMMIT" && isInt(e, "tick"))
    .map((e) => e.tick as number);
}

// --- checks, report, reference consumer -----------------------------------------------------

export function checkEvents(events: Ev[], parseErrors: string[] = []) {
  const out = [res("FEP5-PARSE", parseErrors)];
  const kind = streamKind(events);
  out.push(res("FEP5-KIND", kind !== "unknown" ? [] : ["line 1 is neither a header nor a trust_decision, or a decision log has other events"], kind));
  const inp = kind === "input";
  const dec = kind === "decisions";
  const naIn = inp ? null : "not an input stream";
  const naDec = dec ? null : "not a decision log";
  out.push(res("FEP5-DECL", inp ? declErrors(events) : null, "", naIn));
  out.push(res("FEP5-CONTROL", inp ? controlErrors(events) : null, "", naIn));
  out.push(res("FEP5-ENABLE", inp ? enableErrors(events) : null, "", naIn));
  out.push(res("FEP5-INTENT", inp ? intentCompatErrors(events) : null, "", naIn));
  out.push(res("FEP5-TD-FORMAT", dec ? events.flatMap((e) => tdControlFormatErrors(e)) : null, `${events.length} decision(s)`, naDec));
  out.push(res("FEP5-TD-ORDER", dec ? tdOrderErrors(events) : null, "", naDec));
  out.push(res("FEP5-SAFETY", dec ? safetyErrors(events) : null, "", naDec));
  return out;
}

export function checkFile(name: string, bytes: Uint8Array): TargetReport {
  const [events, perr] = readEvents(bytes);
  const results = checkEvents(events, perr);
  const kind = streamKind(events);
  if (kind === "input" && !perr.length) results.splice(2, 0, res("FEP5-V01-CORE", v01CoreFailures(bytes), "v0.1 core passed"));
  else results.splice(2, 0, res("FEP5-V01-CORE", null, "", "not an input stream"));
  return { target: name, checks: results, info: { format: "jsonl", kind, events: events.length } };
}

export function summarize(events: Ev[]): Record<string, unknown> {
  const kind = streamKind(events);
  if (kind === "decisions") {
    const [ai, at] = f3.acted(events.filter((e) => !isControl(e)));
    return {
      kind, decisions: events.length, control_decisions: events.filter(isControl).length,
      moving_ticks: movingTicks(events), acted_intents: ai, acted_texts: at,
    };
  }
  const count = (f: (e: Ev) => boolean): number => events.filter(f).length;
  return {
    kind,
    declarations: count((e) => e.type === "header" && has(e, CONTROL_DECLARATION_KEY)),
    controls: count((e) => e.type === CONTROL),
    pointers: count((e) => e.type === "pointer"),
    enables: count((e) => e.type === CONTROL_ENABLE),
    intents: count((e) => e.type === "intent"),
    n_frames: count((e) => e.type === "frame"),
  };
}

export function consume(name: string, bytes: Uint8Array): Record<string, unknown> {
  rejectOnFailure(checkFile(name, bytes));
  return summarize(readEvents(bytes)[0]);
}
