/**
 * Conformance profile `fep-0001`: streaming trust events (port of
 * `fidetype.conformance.profiles.fep0001`).
 *
 * Input streams (line 1 = header) may carry `segment_end`, evidence fields
 * on hypothesis items and a `decode_declaration`; they must also pass the
 * v0.1 core level. Decision logs hold only `trust_decision` lines.
 */

import { blocks, runChecks } from "../checks.js";
import { DECLARATION_KEY, SCORE_SEMANTICS, SEGMENT_UNITS, TRUST_ACTIONS } from "../constants.js";
import { cpLen, get, has, isFinNum, isObj } from "../json.js";
import { readJsonlRaw } from "../raw.js";
import { CheckMeta, Ev, TargetReport, isInt, makeRes, readEvents, rejectOnFailure, repr, streamKind } from "./common.js";

export const FEP = "FEP-0001";
export const SUFFIXES = [".jsonl", ".ndjson"];
const LOGP_TOL = 1e-9;

export const CHECKS: CheckMeta[] = [
  ["FEP1-PARSE", "MUST", "6.2 (v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"],
  ["FEP1-KIND", "MUST", "3 r4 / 6.2.1", "The file is an input stream (header first) or a decision log (only trust_decision)"],
  ["FEP1-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"],
  ["FEP1-SEGMENT", "MUST", "1 table, r5", "segment_end: t a finite number not before the last frame; unit in the enum"],
  ["FEP1-EVIDENCE", "MUST", "2 table, r1, r4", "char_confidences: one number in [0, 1] per code point; logp_* finite and <= 0"],
  ["FEP1-SCORE", "MUST", "2 r3", "Every n-best item has a finite numeric score"],
  ["FEP1-DECL", "MUST", "4 table", "decode_declaration (header or hypothesis) has the defined form"],
  ["FEP1-TD-INPUT", "MUST", "3 r4", "No trust_decision event in an input stream"],
  ["FEP1-TD-FORMAT", "MUST", "3 table, r2, r8", "trust_decision fields have the defined types and ranges"],
  ["FEP1-TD-FINAL", "MUST", "3 r5-r7", "Per session: seq increases; at most one final decision per utterance; none after it"],
];
const META = Object.fromEntries(CHECKS.map((c) => [c[0], c]));
const res = makeRes(META, FEP);

/** The format errors of a `decode_declaration` (FEP-0001 section 4). Empty: valid. */
export function validateDeclaration(decl: unknown): string[] {
  if (!isObj(decl)) return [`${DECLARATION_KEY} must be a JSON object`];
  const errs: string[] = [];
  const dec = get(decl, "decoder");
  if (typeof dec !== "string" || !dec) errs.push(`${DECLARATION_KEY}.decoder must be a non-empty string`);
  for (const k of ["decoder_version", "config_id"]) {
    if (has(decl, k) && (typeof decl[k] !== "string" || !decl[k])) errs.push(`${DECLARATION_KEY}.${k} must be a non-empty string`);
  }
  if (has(decl, "frame_temperature")) {
    const t = decl.frame_temperature;
    if (!isFinNum(t) || t <= 0) errs.push(`${DECLARATION_KEY}.frame_temperature must be a finite number > 0`);
  }
  if (has(decl, "params") && !isObj(decl.params)) errs.push(`${DECLARATION_KEY}.params must be a JSON object`);
  return errs;
}

export function segmentErrors(events: Ev[]): string[] {
  const errs: string[] = [];
  let lastFrameT = -Infinity;
  for (const e of events) {
    if (e.type === "header") lastFrameT = -Infinity;
    else if (e.type === "frame" && isFinNum(get(e, "t"))) lastFrameT = e.t as number;
    else if (e.type === "segment_end") {
      const n = e._line;
      if (has(e, "t")) {
        if (!isFinNum(e.t)) errs.push(`line ${n}: segment_end t must be a finite number`);
        else if (e.t < lastFrameT) errs.push(`line ${n}: segment_end t ${e.t} is before the last frame t ${lastFrameT} (rule 5)`);
      }
      if (has(e, "unit") && !(SEGMENT_UNITS as readonly unknown[]).includes(e.unit)) {
        errs.push(`line ${n}: segment_end unit ${repr(e.unit)} is not one of ${repr(SEGMENT_UNITS)}`);
      }
    }
  }
  return errs;
}

function* items(events: Ev[]): Generator<[number, number, Record<string, unknown>]> {
  for (const e of events) {
    if (e.type === "hypothesis" && Array.isArray(get(e, "nbest"))) {
      const nb = e.nbest as unknown[];
      for (let k = 0; k < nb.length; k++) if (isObj(nb[k])) yield [e._line, k, nb[k] as Record<string, unknown>];
    }
  }
}

export function evidenceErrors(events: Ev[]): string[] {
  const errs: string[] = [];
  for (const [n, k, it] of items(events)) {
    const where = `line ${n} nbest[${k}]`;
    if (has(it, "char_confidences")) {
      const cc = it.char_confidences;
      const text = get(it, "text");
      if (!Array.isArray(cc)) errs.push(`${where}: char_confidences must be a list`);
      else {
        if (typeof text === "string" && cc.length !== cpLen(text)) {
          errs.push(`${where}: char_confidences has ${cc.length} values, text has ${cpLen(text)} code points (rule 1)`);
        }
        if (cc.some((c) => !isFinNum(c) || !(c >= 0 && c <= 1))) errs.push(`${where}: char_confidences values must be numbers in [0, 1]`);
      }
    }
    for (const key of ["logp_acoustic", "logp_lm"]) {
      if (has(it, key)) {
        const v = it[key];
        if (!isFinNum(v)) errs.push(`${where}: ${key} must be a finite number`);
        else if (v > LOGP_TOL) errs.push(`${where}: ${key} ${v} is a log-probability and must be <= 0 (rule 4)`);
      }
    }
  }
  return errs;
}

export function scoreErrors(events: Ev[]): string[] {
  return [...items(events)].filter(([, , it]) => !isFinNum(get(it, "score")))
    .map(([n, k]) => `line ${n} nbest[${k}]: score must be a finite number (rule 3)`);
}

export function declarationErrors(events: Ev[]): string[] {
  const errs: string[] = [];
  for (const e of events) {
    if ((e.type === "header" || e.type === "hypothesis") && has(e, DECLARATION_KEY)) {
      errs.push(...validateDeclaration(e[DECLARATION_KEY]).map((x) => `line ${e._line}: ${x}`));
    }
  }
  return errs;
}

export function tdInputErrors(events: Ev[]): string[] {
  return events.filter((e) => e.type === "trust_decision").map((e) => `line ${e._line}: trust_decision in an input stream`);
}

/** The format errors of one `trust_decision` event (FEP-0001 section 3 table, rules 2 and 8). */
export function tdFormatErrors(e: Record<string, unknown>): string[] {
  const n = has(e, "_line") ? e._line : "?";
  const errs: string[] = [];
  if (typeof get(e, "is_final") !== "boolean") errs.push("is_final must be a boolean");
  const action = get(e, "action");
  if (!(TRUST_ACTIONS as readonly unknown[]).includes(action)) errs.push(`action ${repr(action)} is not one of ${repr(TRUST_ACTIONS)}`);
  if (!has(e, "p_top1")) errs.push("p_top1 is required (number or null)");
  else if (e.p_top1 !== null && !(isFinNum(e.p_top1) && e.p_top1 >= 0 && e.p_top1 <= 1)) {
    errs.push(`p_top1 ${repr(e.p_top1)} must be a number in [0, 1] or null`);
  }
  const sem = get(e, "score_semantics");
  if (sem === null) errs.push("score_semantics is required");
  else if (!(SCORE_SEMANTICS as readonly unknown[]).includes(sem)) errs.push(`score_semantics ${repr(sem)} is not one of ${repr(SCORE_SEMANTICS)}`);
  if (has(e, "shown")) {
    const sh = e.shown;
    if (!Array.isArray(sh) || !sh.every((x) => typeof x === "string")) errs.push("shown must be a list of strings");
    else if (action === "COMMIT" && !sh.length) errs.push("a COMMIT with shown needs at least one text (rule 8)");
  }
  if (has(e, "set_size") && !(isInt(e, "set_size") && (e.set_size as number) >= 0)) errs.push("set_size must be an integer >= 0");
  if (has(e, "guard_risk") && e.guard_risk !== null && !(isFinNum(e.guard_risk) && e.guard_risk >= 0 && e.guard_risk <= 1)) {
    errs.push("guard_risk must be a number in [0, 1] or null");
  }
  if (has(e, "session") && typeof e.session !== "string") errs.push("session must be a string");
  for (const k of ["seq", "utterance"]) {
    if (has(e, k) && !(isInt(e, k) && (e[k] as number) >= 0)) errs.push(`${k} must be an integer >= 0`);
  }
  if (has(e, "config_id") && e.config_id !== null && typeof e.config_id !== "string") errs.push("config_id must be a string");
  if (has(e, "input") && !isObj(e.input)) errs.push("input must be an object");
  if (has(e, "latency_s") && !(isFinNum(e.latency_s) && e.latency_s >= 0)) errs.push("latency_s must be a number >= 0");
  return errs.map((x) => `line ${n}: ${x}`);
}

/** is_final semantics per session (FEP-0001 section 3 rules 5-7). */
export function tdFinalErrors(events: Record<string, unknown>[]): string[] {
  const errs: string[] = [];
  const lastSeq = new Map<string, number>();
  const lastUtt = new Map<string, number>();
  const finals = new Set<string>();
  for (const e of events) {
    if (get(e, "type") !== "trust_decision") continue;
    const n = has(e, "_line") ? e._line : "?";
    const sid = has(e, "session") ? e.session : "";
    if (typeof sid !== "string") continue;
    const seq = get(e, "seq");
    const utt = get(e, "utterance");
    if (has(e, "seq") && isInt(e, "seq")) {
      const s = seq as number;
      if (lastSeq.has(sid) && s <= (lastSeq.get(sid) as number)) errs.push(`line ${n}: seq ${s} does not increase in session '${sid}' (rule 5)`);
      lastSeq.set(sid, Math.max(s, lastSeq.get(sid) ?? s));
    }
    if (has(e, "utterance") && isInt(e, "utterance")) {
      const u = utt as number;
      if (lastUtt.has(sid) && u < (lastUtt.get(sid) as number)) errs.push(`line ${n}: utterance ${u} goes back in session '${sid}' (rule 5)`);
      lastUtt.set(sid, Math.max(u, lastUtt.get(sid) ?? u));
      const key = JSON.stringify([sid, u]);
      if (finals.has(key)) {
        const kind = get(e, "is_final") === true ? "a second final decision" : "a decision";
        errs.push(`line ${n}: ${kind} for utterance ${u} of session '${sid}' after its final one (rules 6-7)`);
      }
      if (get(e, "is_final") === true) finals.add(key);
    }
  }
  return errs;
}

/** The texts a bridge may act on: `shown[0]` of each final COMMIT (null if the text is omitted). */
export function actedTexts(decisions: Record<string, unknown>[]): (string | null)[] {
  const out: (string | null)[] = [];
  for (const e of decisions) {
    if (get(e, "type") === "trust_decision" && get(e, "is_final") === true && get(e, "action") === "COMMIT") {
      const sh = get(e, "shown");
      out.push(Array.isArray(sh) && sh.length ? (sh[0] as string) : null);
    }
  }
  return out;
}

export function checkEvents(events: Ev[], parseErrors: string[] = []) {
  const out = [res("FEP1-PARSE", parseErrors)];
  const kind = streamKind(events);
  out.push(res("FEP1-KIND", kind !== "unknown" ? [] : ["line 1 is neither a header nor a trust_decision, or a decision log has other events"], kind));
  const inp = kind === "input";
  const dec = kind === "decisions";
  const naIn = inp ? null : "not an input stream";
  const naDec = dec ? null : "not a decision log";
  out.push(res("FEP1-SEGMENT", inp ? segmentErrors(events) : null, "", naIn));
  out.push(res("FEP1-EVIDENCE", inp ? evidenceErrors(events) : null, "", naIn));
  out.push(res("FEP1-SCORE", inp ? scoreErrors(events) : null, "", naIn));
  out.push(res("FEP1-DECL", inp ? declarationErrors(events) : null, "", naIn));
  out.push(res("FEP1-TD-INPUT", inp ? tdInputErrors(events) : null, "", naIn));
  out.push(res("FEP1-TD-FORMAT", dec ? events.flatMap((e) => tdFormatErrors(e)) : null, `${events.length} decision(s)`, naDec));
  out.push(res("FEP1-TD-FINAL", dec ? tdFinalErrors(events) : null, "", naDec));
  return out;
}

/** v0.1 core failures of a JSON Lines input stream (as `fidetype.conformance.check_file`). */
export function v01CoreFailures(bytes: Uint8Array): string[] {
  return runChecks(readJsonlRaw(bytes)).filter((r) => r.status === "fail" && blocks(r.level, "core")).map((r) => `${r.id}: ${r.message}`);
}

/** Producer check of one JSON Lines file under the profile. */
export function checkFile(name: string, bytes: Uint8Array): TargetReport {
  const [events, perr] = readEvents(bytes);
  const results = checkEvents(events, perr);
  const kind = streamKind(events);
  if (kind === "input" && !perr.length) results.splice(2, 0, res("FEP1-V01-CORE", v01CoreFailures(bytes), "v0.1 core passed"));
  else results.splice(2, 0, res("FEP1-V01-CORE", null, "", "not an input stream"));
  return { target: name, checks: results, info: { format: "jsonl", kind, events: events.length } };
}

export function summarize(events: Ev[]): Record<string, unknown> {
  const kind = streamKind(events);
  if (kind === "decisions") {
    return { kind, decisions: events.length, final: events.filter((e) => get(e, "is_final") === true).length, acted: actedTexts(events) };
  }
  let segs = 0;
  let hasInput = false;
  let ends = 0;
  for (const e of events) {
    const t = e.type;
    if (t === "frame" || t === "hypothesis") hasInput = true;
    else if (t === "segment_end" || t === "end" || t === "header") {
      if (hasInput) segs++;
      hasInput = false;
      if (t === "segment_end") ends++;
    }
  }
  if (hasInput) segs++;
  return {
    kind,
    n_frames: events.filter((e) => e.type === "frame").length,
    segments: segs,
    segment_ends: ends,
    hypotheses: events.filter((e) => e.type === "hypothesis").length,
    evidence_items: [...items(events)].filter(([, , it]) => ["char_confidences", "logp_acoustic", "logp_lm"].some((k) => has(it, k))).length,
    declarations: events.filter((e) => (e.type === "header" || e.type === "hypothesis") && has(e, DECLARATION_KEY)).length,
  };
}

/** Reference consumer of the profile: return a summary, or throw StreamRejected. */
export function consume(name: string, bytes: Uint8Array): Record<string, unknown> {
  rejectOnFailure(checkFile(name, bytes));
  return summarize(readEvents(bytes)[0]);
}
