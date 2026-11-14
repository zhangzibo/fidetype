/**
 * Conformance profile `fep-0003`: output profiles and discrete intent
 * events (port of `fidetype.conformance.profiles.fep0003` and the
 * validators of `fidetype.trust.intent`).
 */

import { FEEDBACK_OUTCOMES, INTENT_ACTIONS, INTENT_DECLARATION_KEY, INTENT_ROLES, RISK_CLASSES, SCORE_SEMANTICS } from "../constants.js";
import { get, has, isFinNum, isObj } from "../json.js";
import { CheckMeta, Ev, TargetReport, isInt, makeRes, readEvents, rejectOnFailure, repr, streamKind } from "./common.js";
import { tdFormatErrors, v01CoreFailures } from "./fep0001.js";

export const FEP = "FEP-0003";
export const SUFFIXES = [".jsonl", ".ndjson"];
const PROFILE = "intent";
const PROFILES = ["text", "intent"];
const PROB_SEMANTICS = ["calibrated_prob", "uncalibrated_prob"];
const UNIQUE_ROLES = ["confirm", "cancel", "undo"];
const SUM_TOL = 1e-6;

export const CHECKS: CheckMeta[] = [
  ["FEP3-PARSE", "MUST", "1 (6.2 v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"],
  ["FEP3-KIND", "MUST", "1", "The file is an input stream (header first) or a decision log (only trust_decision)"],
  ["FEP3-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"],
  ["FEP3-DECL", "MUST", "2 table, r1-r4", "intent_declaration has the defined form"],
  ["FEP3-VOCAB", "MUST", "2 r5", "On a command-vocabulary stream with a declaration, vocab (without blank) equals the declared intents"],
  ["FEP3-INTENT", "MUST", "3 table, r1-r5", "intent events: declared, unique candidates; scores fit their semantics; ranked"],
  ["FEP3-FEEDBACK", "MUST", "4 table", "intent_feedback events have the defined form"],
  ["FEP3-TD-FORMAT", "MUST", "5 table, r1-r3", "Intent trust_decision fields (profile, unit, intent, offered, risk_class, no shown)"],
  ["FEP3-TD-FINAL", "MUST", "5 r4, 7 r2", "Per session: seq increases over both profiles; one final decision per intent unit; none after it"],
  ["FEP3-SAFETY", "MUST", "6 r1-r6", "No null COMMIT; COMMIT p >= threshold; irreversible COMMIT confirmed; valid undo"],
];
const META = Object.fromEntries(CHECKS.map((c) => [c[0], c]));
const res = makeRes(META, FEP);

const isIntent = (e: Record<string, unknown>): boolean => get(e, "type") === "trust_decision" && get(e, "profile") === PROFILE;

/** The FEP-0003 section 2 errors of an `intent_declaration` (empty = valid). */
export function validateIntentDeclaration(d: unknown): string[] {
  if (!isObj(d)) return ["intent_declaration must be a JSON object"];
  const errs: string[] = [];
  for (const k of ["vocab_id", "vocab_version"]) {
    if (has(d, k) && !(typeof d[k] === "string" && d[k])) errs.push(`intent_declaration ${k} must be a non-empty string`);
  }
  const its = get(d, "intents");
  if (!Array.isArray(its) || !its.length) return [...errs, "intent_declaration intents must be a non-empty list"];
  const seen = new Set<string>();
  const roles = new Map<string, number>();
  its.forEach((it, j) => {
    const w = `intents[${j}]`;
    if (!isObj(it)) {
      errs.push(`${w} must be an object`);
      return;
    }
    const iid = get(it, "id");
    if (!(typeof iid === "string" && iid.trim())) errs.push(`${w} id must be a non-empty string`);
    else if (seen.has(iid)) errs.push(`${w} id '${iid}' is not unique`);
    else seen.add(iid);
    if (!(RISK_CLASSES as readonly unknown[]).includes(get(it, "risk"))) errs.push(`${w} risk ${repr(get(it, "risk"))} is not one of ${repr(RISK_CLASSES)}`);
    const role = has(it, "role") ? it.role : "action";
    if (!(INTENT_ROLES as readonly unknown[]).includes(role)) errs.push(`${w} role ${repr(role)} is not one of ${repr(INTENT_ROLES)}`);
    else roles.set(role as string, (roles.get(role as string) ?? 0) + 1);
    if (has(it, "label") && typeof it.label !== "string") errs.push(`${w} label must be a string`);
  });
  for (const r of UNIQUE_ROLES) if ((roles.get(r) ?? 0) > 1) errs.push(`at most one intent may have role '${r}' (${roles.get(r)} found)`);
  const good = its.filter(isObj) as Record<string, unknown>[];
  if (good.some((it) => get(it, "risk") === "irreversible")) {
    for (const it of good) {
      if (get(it, "role") === "confirm" && get(it, "risk") !== "irreversible") {
        errs.push(`the confirm intent ${repr(get(it, "id"))} executes irreversible intents, so its risk must be 'irreversible' (FEP-0003 section 2 rule 4)`);
      }
    }
  }
  const nonNull = ["action", "confirm", "cancel", "undo"].reduce((s, r) => s + (roles.get(r) ?? 0), 0);
  if (nonNull === 0) errs.push("intent_declaration needs at least one intent that is not null");
  return errs;
}

/** Intent ids of a valid declaration. */
const declIds = (d: unknown): string[] => ((d as Record<string, unknown>).intents as Record<string, unknown>[]).map((it) => it.id as string);

/** The FEP-0003 section 3 errors of one `intent` event (empty = valid). */
export function validateIntentEvent(ev: Record<string, unknown>, vocab: string[] | null): string[] {
  const errs: string[] = [];
  if (vocab === null) errs.push("an intent event needs an intent_declaration in the header");
  const id = get(ev, "id");
  if (typeof id !== "string" || !id) errs.push("id must be a non-empty string");
  if (!isFinNum(get(ev, "t"))) errs.push("t must be a finite number");
  if (typeof get(ev, "is_final") !== "boolean") errs.push("is_final must be a boolean");
  const sem = get(ev, "score_semantics");
  if (!(SCORE_SEMANTICS as readonly unknown[]).includes(sem)) errs.push(`score_semantics ${repr(sem)} is not one of ${repr(SCORE_SEMANTICS)}`);
  for (const k of ["t_start", "t_end"]) if (has(ev, k) && !isFinNum(ev[k])) errs.push(`${k} must be a finite number`);
  if (has(ev, "revision_of") && ev.revision_of !== null && typeof ev.revision_of !== "string") errs.push("revision_of must be a string or null");
  const cands = get(ev, "candidates");
  if (!Array.isArray(cands) || !cands.length) return [...errs, "candidates must be a non-empty list"];
  const seen = new Set<string>();
  const scores: number[] = [];
  cands.forEach((c, j) => {
    const w = `candidates[${j}]`;
    if (!isObj(c) || typeof get(c, "intent") !== "string") {
      errs.push(`${w} must be an object with a string intent`);
      return;
    }
    const iid = c.intent as string;
    if (seen.has(iid)) errs.push(`${w} intent '${iid}' appears twice`);
    seen.add(iid);
    if (vocab !== null && !vocab.includes(iid)) errs.push(`${w} intent '${iid}' is not in the declaration`);
    const sc = get(c, "score");
    if (sem === "none") {
      if (sc !== null) errs.push(`${w} score must be null or absent with score_semantics none`);
    } else if (PROB_SEMANTICS.includes(sem as string)) {
      if (!(isFinNum(sc) && sc >= 0 && sc <= 1)) errs.push(`${w} score must be a number in [0, 1]`);
      else scores.push(sc);
    } else if (sem === "power" || sem === "strength") {
      if (!isFinNum(sc)) errs.push(`${w} score must be a finite number`);
      else scores.push(sc);
    }
  });
  // Python sum(): left-to-right float addition.
  const total = scores.reduce((s, x) => s + x, 0);
  if (PROB_SEMANTICS.includes(sem as string) && scores.length && total > 1 + SUM_TOL) errs.push(`candidate scores sum to ${total.toFixed(6)} > 1`);
  if (sem !== "none" && scores.length === cands.length && scores.some((b, k) => k > 0 && b > scores[k - 1] + 1e-12)) {
    errs.push("candidates must be ranked best first (scores non-increasing)");
  }
  return errs;
}

/** The FEP-0003 section 4 errors of one `intent_feedback` event. */
export function validateFeedbackEvent(ev: Record<string, unknown>, vocab: string[] | null = null): string[] {
  const errs: string[] = [];
  if (!(isInt(ev, "ref_unit") && (ev.ref_unit as number) >= 0)) errs.push("ref_unit must be an integer >= 0");
  const outcome = get(ev, "outcome");
  if (!(FEEDBACK_OUTCOMES as readonly unknown[]).includes(outcome)) errs.push(`outcome ${repr(outcome)} is not one of ${repr(FEEDBACK_OUTCOMES)}`);
  if (outcome === "selected" && typeof get(ev, "intent") !== "string") errs.push("outcome selected needs the selected intent");
  if (has(ev, "intent") && ev.intent !== null) {
    if (typeof ev.intent !== "string") errs.push("intent must be a string");
    else if (vocab !== null && !vocab.includes(ev.intent)) errs.push(`intent '${ev.intent}' is not in the declaration`);
  }
  if (has(ev, "t") && !isFinNum(ev.t)) errs.push("t must be a finite number");
  if (has(ev, "source") && typeof ev.source !== "string") errs.push("source must be a string");
  return errs;
}

// --- input rules -------------------------------------------------------------------------

function* declarations(events: Ev[]): Generator<[Ev, string[] | null, string[]]> {
  for (const e of events) {
    if (e.type !== "header") continue;
    if (!has(e, INTENT_DECLARATION_KEY)) {
      yield [e, null, []];
      continue;
    }
    const errs = validateIntentDeclaration(e[INTENT_DECLARATION_KEY]);
    yield [e, errs.length ? null : declIds(e[INTENT_DECLARATION_KEY]), errs];
  }
}

export function declErrors(events: Ev[]): string[] {
  return [...declarations(events)].flatMap(([h, , errs]) => errs.map((x) => `line ${h._line}: ${x}`));
}

export function vocabErrors(events: Ev[]): string[] {
  const out: string[] = [];
  for (const [h, v] of declarations(events)) {
    if (v === null || get(h, "vocab_type") !== "command") continue;
    const vocabRaw = get(h, "vocab");
    const vocab = (Array.isArray(vocabRaw) && vocabRaw.length ? vocabRaw : []) as unknown[];
    const b = get(h, "blank_id");
    const toks = new Set(vocab.filter((_t, j) => j !== b));
    const ids = new Set(v);
    const same = toks.size === ids.size && [...toks].every((t) => ids.has(t as string));
    if (!same) out.push(`line ${h._line}: command vocab without blank != declared intents (rule 5)`);
  }
  return out;
}

export function intentErrors(events: Ev[]): string[] {
  const out: string[] = [];
  let vocab: string[] | null = null;
  let hasDecl = false;
  let ids = new Set<string>();
  for (const e of events) {
    if (e.type === "header") {
      hasDecl = has(e, INTENT_DECLARATION_KEY);
      vocab = null;
      if (hasDecl && !validateIntentDeclaration(e[INTENT_DECLARATION_KEY]).length) vocab = declIds(e[INTENT_DECLARATION_KEY]);
      ids = new Set();
    } else if (e.type === "intent") {
      const n = e._line;
      if (!hasDecl) {
        out.push(`line ${n}: intent event without an intent_declaration in the header (rule 1)`);
        continue;
      }
      if (vocab === null) continue; // FEP3-DECL reports it
      out.push(...validateIntentEvent(e, vocab).map((x) => `line ${n}: ${x}`));
      const id = get(e, "id");
      if (typeof id === "string") {
        if (ids.has(id)) out.push(`line ${n}: intent id '${id}' is not unique in the stream`);
        ids.add(id);
      }
    }
  }
  return out;
}

export function feedbackErrors(events: Ev[]): string[] {
  const out: string[] = [];
  let vocab: string[] | null = null;
  for (const e of events) {
    if (e.type === "header") {
      const d = get(e, INTENT_DECLARATION_KEY);
      vocab = d !== null && !validateIntentDeclaration(d).length ? declIds(d) : null;
    } else if (e.type === "intent_feedback") {
      out.push(...validateFeedbackEvent(e, vocab).map((x) => `line ${e._line}: ${x}`));
    }
  }
  return out;
}

// --- decision-log rules ----------------------------------------------------------------------

/** Format errors of one trust_decision (FEP-0001 table for all; section 5 for intent decisions). */
export function tdIntentFormatErrors(e: Record<string, unknown>): string[] {
  const errs = tdFormatErrors(e);
  const n = has(e, "_line") ? e._line : "?";
  const prof = has(e, "profile") ? e.profile : "text";
  if (!PROFILES.includes(prof as string)) return [...errs, `line ${n}: profile ${repr(prof)} is not one of ${repr(PROFILES)}`];
  if (prof !== PROFILE) return errs;
  const x: string[] = [];
  const action = get(e, "action");
  if (has(e, "shown")) x.push("an intent decision MUST NOT carry shown (rule 2)");
  if (has(e, "utterance")) x.push("an intent decision uses unit, not utterance (rule 1)");
  if (!(isInt(e, "unit") && (e.unit as number) >= 0)) x.push("unit must be an integer >= 0");
  if (!(INTENT_ACTIONS as readonly unknown[]).includes(action)) x.push(`intent action ${repr(action)} is not one of ${repr(INTENT_ACTIONS)}`);
  if (action === "COMMIT" && typeof get(e, "intent") !== "string") x.push("a COMMIT needs the committed intent (rule 3)");
  if (has(e, "intent") && typeof e.intent !== "string") x.push("intent must be a string");
  if (has(e, "offered") && !(Array.isArray(e.offered) && e.offered.every((i) => typeof i === "string"))) x.push("offered must be a list of strings");
  const off = get(e, "offered");
  if (action === "OFFER" && !(Array.isArray(off) && off.length)) x.push("an OFFER needs a non-empty offered list (rule 3)");
  if (has(e, "risk_class") && e.risk_class !== null && !(RISK_CLASSES as readonly unknown[]).includes(e.risk_class)) {
    x.push(`risk_class ${repr(e.risk_class)} is not one of ${repr(RISK_CLASSES)}`);
  }
  if (action === "COMMIT" && !(RISK_CLASSES as readonly unknown[]).includes(get(e, "risk_class"))) x.push("a COMMIT needs risk_class (rule 3)");
  if (has(e, "role") && e.role !== null && !(INTENT_ROLES as readonly unknown[]).includes(e.role)) x.push(`role ${repr(e.role)} is not one of ${repr(INTENT_ROLES)}`);
  if (has(e, "threshold") && e.threshold !== null && !(isFinNum(e.threshold) && e.threshold >= 0 && e.threshold <= 1)) {
    x.push("threshold must be a number in [0, 1] or null");
  }
  if (has(e, "confirm_required") && typeof e.confirm_required !== "boolean") x.push("confirm_required must be a boolean");
  if (get(e, "confirm_required") === true && action !== "OFFER") x.push("confirm_required is only allowed on an OFFER");
  for (const k of ["confirmation_of", "undo_of"]) if (has(e, k) && !(isInt(e, k) && (e[k] as number) >= 0)) x.push(`${k} must be an integer >= 0`);
  if (has(e, "confirmed_via") && e.confirmed_via !== "intent" && e.confirmed_via !== "feedback") x.push("confirmed_via must be 'intent' or 'feedback'");
  return [...errs, ...x.map((m) => `line ${n}: ${m}`)];
}

/** seq per session over both profiles; one final decision per text utterance and per intent unit. */
export function tdFinalErrors(events: Record<string, unknown>[]): string[] {
  const errs: string[] = [];
  const lastSeq = new Map<string, number>();
  const last = new Map<string, number>();
  const finals = new Set<string>();
  for (const e of events) {
    if (get(e, "type") !== "trust_decision") continue;
    const n = has(e, "_line") ? e._line : "?";
    const sid = has(e, "session") ? e.session : "";
    if (typeof sid !== "string") continue;
    if (isInt(e, "seq")) {
      const s = e.seq as number;
      if (lastSeq.has(sid) && s <= (lastSeq.get(sid) as number)) errs.push(`line ${n}: seq ${s} does not increase in session '${sid}' (section 7 rule 2)`);
      lastSeq.set(sid, Math.max(s, lastSeq.get(sid) ?? s));
    }
    const key = isIntent(e) ? "unit" : "utterance";
    if (!isInt(e, key)) continue;
    const val = e[key] as number;
    const pk = JSON.stringify([sid, key]);
    if (last.has(pk) && val < (last.get(pk) as number)) errs.push(`line ${n}: ${key} ${val} goes back in session '${sid}'`);
    last.set(pk, Math.max(val, last.get(pk) ?? val));
    const fk = JSON.stringify([sid, key, val]);
    if (finals.has(fk)) {
      const kind = get(e, "is_final") === true ? "a second final decision" : "a decision";
      errs.push(`line ${n}: ${kind} for ${key} ${val} of session '${sid}' after its final one (rule 4)`);
    }
    if (get(e, "is_final") === true) finals.add(fk);
  }
  return errs;
}

/** Python dict key of (sid, unit): unit may be any JSON value. */
const pk2 = (sid: unknown, unit: unknown): string => JSON.stringify([sid, unit]);

/** Section 6: null, threshold, confirmation and undo rules on final intent decisions. */
export function safetyErrors(events: Record<string, unknown>[]): string[] {
  const errs: string[] = [];
  const offers = new Map<string, unknown[]>();
  const used = new Set<string>();
  const commits = new Map<string, unknown>();
  for (const e of events) {
    if (!isIntent(e) || get(e, "is_final") !== true) continue;
    const n = has(e, "_line") ? e._line : "?";
    const sid = has(e, "session") ? e.session : "";
    const unit = get(e, "unit");
    const act = get(e, "action");
    if (act === "OFFER" && Array.isArray(get(e, "offered"))) offers.set(pk2(sid, unit), [...(e.offered as unknown[])]);
    if (act !== "COMMIT") continue;
    if (get(e, "role") === "null") errs.push(`line ${n}: COMMIT of a null intent (rule 1)`);
    const p = get(e, "p_top1");
    const thr = get(e, "threshold");
    if (get(e, "confirmed_via") !== "feedback" && isFinNum(p) && isFinNum(thr) && p < thr - 1e-12) {
      errs.push(`line ${n}: COMMIT with p_top1 ${p} below its threshold ${thr} (rule 3)`);
    }
    const inp = get(e, "input");
    const sem = isObj(inp) ? get(inp, "score_semantics") : null;
    if ((sem === "none" || sem === "power" || sem === "strength") && get(e, "confirmed_via") !== "feedback") {
      errs.push(`line ${n}: COMMIT on input with score_semantics '${sem}' (rule 2)`);
    }
    if (get(e, "risk_class") === "irreversible") {
      const ref = get(e, "confirmation_of");
      const key = pk2(sid, ref);
      if (!isInt(e, "confirmation_of")) errs.push(`line ${n}: irreversible COMMIT without confirmation_of (rule 4)`);
      else if (!offers.has(key) || !(offers.get(key) as unknown[]).includes(get(e, "intent"))) {
        errs.push(`line ${n}: confirmation_of ${ref} is not an earlier final OFFER of ${repr(get(e, "intent"))} (rule 4)`);
      } else if (used.has(key)) errs.push(`line ${n}: OFFER unit ${ref} is confirmed twice (rule 4)`);
      else used.add(key);
    }
    if (has(e, "undo_of")) {
      const key = pk2(sid, e.undo_of);
      if (!commits.has(key)) errs.push(`line ${n}: undo_of ${repr(e.undo_of)} is not an earlier final COMMIT (rule 5)`);
      else if (commits.get(key) === "irreversible") errs.push(`line ${n}: undo_of ${repr(e.undo_of)} targets an irreversible COMMIT (rule 5)`);
    }
    if (isInt(e, "unit")) commits.set(pk2(sid, unit), get(e, "risk_class"));
  }
  return errs;
}

/** (acted intents, acted texts): final intent COMMITs and final text COMMITs. */
export function acted(decisions: Record<string, unknown>[]): [(string | null)[], (string | null)[]] {
  const ai: (string | null)[] = [];
  const at: (string | null)[] = [];
  for (const e of decisions) {
    if (get(e, "type") !== "trust_decision" || get(e, "is_final") !== true || get(e, "action") !== "COMMIT") continue;
    if (isIntent(e)) ai.push(get(e, "intent") as string | null);
    else {
      const sh = get(e, "shown");
      at.push(Array.isArray(sh) && sh.length ? (sh[0] as string) : null);
    }
  }
  return [ai, at];
}

export function checkEvents(events: Ev[], parseErrors: string[] = []) {
  const out = [res("FEP3-PARSE", parseErrors)];
  const kind = streamKind(events);
  out.push(res("FEP3-KIND", kind !== "unknown" ? [] : ["line 1 is neither a header nor a trust_decision, or a decision log has other events"], kind));
  const inp = kind === "input";
  const dec = kind === "decisions";
  const naIn = inp ? null : "not an input stream";
  const naDec = dec ? null : "not a decision log";
  out.push(res("FEP3-DECL", inp ? declErrors(events) : null, "", naIn));
  out.push(res("FEP3-VOCAB", inp ? vocabErrors(events) : null, "", naIn));
  out.push(res("FEP3-INTENT", inp ? intentErrors(events) : null, "", naIn));
  out.push(res("FEP3-FEEDBACK", inp ? feedbackErrors(events) : null, "", naIn));
  out.push(res("FEP3-TD-FORMAT", dec ? events.flatMap((e) => tdIntentFormatErrors(e)) : null, `${events.length} decision(s)`, naDec));
  out.push(res("FEP3-TD-FINAL", dec ? tdFinalErrors(events) : null, "", naDec));
  out.push(res("FEP3-SAFETY", dec ? safetyErrors(events) : null, "", naDec));
  return out;
}

export function checkFile(name: string, bytes: Uint8Array): TargetReport {
  const [events, perr] = readEvents(bytes);
  const results = checkEvents(events, perr);
  const kind = streamKind(events);
  if (kind === "input" && !perr.length) results.splice(2, 0, res("FEP3-V01-CORE", v01CoreFailures(bytes), "v0.1 core passed"));
  else results.splice(2, 0, res("FEP3-V01-CORE", null, "", "not an input stream"));
  return { target: name, checks: results, info: { format: "jsonl", kind, events: events.length } };
}

export function summarize(events: Ev[]): Record<string, unknown> {
  const kind = streamKind(events);
  if (kind === "decisions") {
    const [ai, at] = acted(events);
    return {
      kind, decisions: events.length, intent_decisions: events.filter(isIntent).length,
      final: events.filter((e) => get(e, "is_final") === true).length, acted_intents: ai, acted_texts: at,
    };
  }
  const count = (f: (e: Ev) => boolean): number => events.filter(f).length;
  return {
    kind,
    declarations: count((e) => e.type === "header" && has(e, INTENT_DECLARATION_KEY)),
    intents: count((e) => e.type === "intent"),
    final_intents: count((e) => e.type === "intent" && get(e, "is_final") === true),
    feedback: count((e) => e.type === "intent_feedback"),
    hypotheses: count((e) => e.type === "hypothesis"),
    n_frames: count((e) => e.type === "frame"),
  };
}

export function consume(name: string, bytes: Uint8Array): Record<string, unknown> {
  rejectOnFailure(checkFile(name, bytes));
  return summarize(readEvents(bytes)[0]);
}
