/**
 * Incremental (streaming) event validation: one event at a time, as the
 * Python `StreamingTrustLayer.push` checks its input
 * (`fidetype.trust.streaming`). Use it on a live stream, where the whole
 * file is not available. For a complete file, {@link loadStream} applies
 * all core checks.
 */

import { DECLARATION_KEY, NORM_TOL, SPEC_VERSION, VOCAB_TYPES } from "./constants.js";
import { cpLen, get, has, isIntAt, isObj, parseJson } from "./json.js";
import { validateDeclaration } from "./profiles/fep0001.js";

export class StreamEventError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamEventError";
  }
}

/** Parse an event (a JSON string or an object). It must be an object with a string `type`. */
export function parseEvent(event: string | Record<string, unknown>): Record<string, unknown> {
  let ev: unknown = event;
  if (typeof event === "string") {
    try {
      ev = parseJson(event);
    } catch (e) {
      throw new StreamEventError(`event is not a JSON value: ${(e as Error).message}`);
    }
  }
  if (!isObj(ev) || typeof ev.type !== "string") throw new StreamEventError('an event must be an object with a string "type"');
  return ev;
}

function lp(x: unknown): number {
  if (x === null) return -Infinity;
  if (typeof x !== "number") throw new StreamEventError(`${JSON.stringify(x)} is not a number or null`);
  return x;
}

/** The dense float64 row of a dense or sparse frame event (spec 3.3, 6.2). Throws on a bad row. */
export function frameRow(event: Record<string, unknown>, V: number): Float64Array {
  let row: Float64Array;
  if (has(event, "log_probs")) {
    const v = event.log_probs;
    if (!Array.isArray(v)) throw new StreamEventError("log_probs is not a list");
    row = Float64Array.from(v.map(lp));
  } else if (has(event, "top_ids")) {
    const ids = event.top_ids;
    const vals = get(event, "top_log_probs");
    if (!Array.isArray(ids) || !Array.isArray(vals) || ids.length !== vals.length) {
      throw new StreamEventError("sparse frame needs top_ids and top_log_probs of the same length");
    }
    if (!ids.every((x, k) => isIntAt(ids, k) && (x as number) >= 0 && (x as number) < V) || new Set(ids).size !== ids.length) {
      throw new StreamEventError("top_ids must be unique integers in 0..V-1");
    }
    const rest = lp(get(event, "rest_log_prob"));
    row = new Float64Array(V).fill(-Infinity);
    const k = ids.length;
    if (V > k && rest > -Infinity) row.fill(rest - Math.log(V - k));
    ids.forEach((id, j) => {
      row[id as number] = lp(vals[j]);
    });
  } else throw new StreamEventError("frame has neither log_probs nor top_ids");
  if (row.length !== V) throw new StreamEventError(`frame has ${row.length} log-probabilities, vocab has ${V}`);
  if (row.some((x) => Number.isNaN(x) || x === Infinity)) throw new StreamEventError("log_probs must not contain NaN or +inf");
  let m = -Infinity;
  for (const x of row) m = Math.max(m, x);
  let lse = -Infinity;
  if (Number.isFinite(m)) {
    let s = 0;
    for (const x of row) s += Math.exp(x - m);
    lse = m + Math.log(s);
  }
  if (!(Math.abs(lse) <= NORM_TOL)) throw new StreamEventError(`frame log_probs must log-sum-exp to 0 (got ${lse})`);
  return row;
}

/** Check the n-best list of a `hypothesis` event (text, finite score, FEP-0001 evidence fields). */
export function checkNbest(event: Record<string, unknown>): void {
  const its = get(event, "nbest");
  if (!Array.isArray(its)) throw new StreamEventError("hypothesis needs an nbest list");
  for (const it of its) {
    if (!isObj(it) || typeof get(it, "text") !== "string") throw new StreamEventError("each nbest item needs a string text");
    const sc = get(it, "score");
    if (typeof sc !== "number" || !Number.isFinite(sc)) throw new StreamEventError("each nbest item needs a finite numeric score");
    for (const k of ["logp_acoustic", "logp_lm"]) {
      const v = get(it, k);
      if (v !== null && typeof v !== "number") throw new StreamEventError(`${k} must be a number`);
    }
    const cc = get(it, "char_confidences");
    if (cc !== null) {
      if (!Array.isArray(cc) || cc.length !== cpLen(it.text as string)) throw new StreamEventError("char_confidences must have one value per character");
      if (cc.some((c) => typeof c !== "number" || !(c >= 0 && c <= 1))) throw new StreamEventError("char_confidences must be numbers in [0, 1]");
    }
  }
}

/** Check a header event as the streaming layer reads it. Returns the vocabulary size. */
export function checkHeader(ev: Record<string, unknown>): number {
  if (get(ev, "spec_version") !== SPEC_VERSION) throw new StreamEventError(`spec_version must be '${SPEC_VERSION}', not ${JSON.stringify(get(ev, "spec_version"))}`);
  const vocab = get(ev, "vocab");
  if (!Array.isArray(vocab) || !vocab.every((t) => typeof t === "string") || new Set(vocab).size !== vocab.length) {
    throw new StreamEventError("vocab must be a list of unique strings");
  }
  if (!has(ev, "blank_id") || !has(ev, "vocab_type")) throw new StreamEventError("the header needs vocab_type and blank_id (spec 6.2 rule 1)");
  if (!(VOCAB_TYPES as readonly unknown[]).includes(ev.vocab_type)) throw new StreamEventError(`vocab_type must be one of ${VOCAB_TYPES.join(", ")}`);
  const b = ev.blank_id;
  if (b !== null && !(isIntAt(ev, "blank_id") && (b as number) >= 0 && (b as number) < vocab.length)) {
    throw new StreamEventError(`blank_id must be null or an integer in 0..${vocab.length - 1}, not ${JSON.stringify(b)}`);
  }
  if (has(ev, DECLARATION_KEY)) {
    const errs = validateDeclaration(ev[DECLARATION_KEY]);
    if (errs.length) throw new StreamEventError(`${errs.join("; ")} (FEP-0001 section 4)`);
  }
  return vocab.length;
}

export type PushResult =
  | { kind: "header"; vocabSize: number }
  | { kind: "frame"; t: number; row: Float64Array }
  | { kind: "hypothesis"; isFinal: boolean }
  | { kind: "segment_end" | "end" }
  | { kind: "ignored"; reason: string }
  | { kind: "other" };

/**
 * Validate a NeuralTextStream event by event (no decoding, no trust policy).
 *
 * `push(event)` returns what the event is, or throws {@link StreamEventError}.
 * Rules: header first; frame times increase strictly; frame rows are
 * normalised; hypothesis events have a string id, a boolean is_final and a
 * valid n-best list; events after `end` are ignored (spec 10, A5);
 * unknown event types are ignored (spec 6.2 rule 5).
 */
export class StreamValidator {
  header: Record<string, unknown> | null = null;
  vocabSize = 0;
  lastT = -Infinity;
  ended = false;
  nEvents = 0;
  ignoredEvents = 0;

  push(event: string | Record<string, unknown>): PushResult {
    const ev = parseEvent(event);
    const typ = ev.type as string;
    let out: PushResult;
    if (typ === "header") {
      this.vocabSize = checkHeader(ev);
      this.header = ev;
      this.lastT = -Infinity;
      this.ended = false;
      out = { kind: "header", vocabSize: this.vocabSize };
    } else if (this.header === null) {
      throw new StreamEventError(`'${typ}' event before the header (spec 6.2 rule 1)`);
    } else if (this.ended) {
      this.ignoredEvents++;
      out = { kind: "ignored", reason: "after the end marker" };
    } else if (typ === "frame") {
      const t = get(ev, "t");
      if (typeof t !== "number" || !Number.isFinite(t)) throw new StreamEventError("frame needs a finite numeric t");
      if (!(t > this.lastT)) throw new StreamEventError(`frame t ${t} does not increase (last ${this.lastT}; spec 6.2 rule 4)`);
      const row = frameRow(ev, this.vocabSize);
      this.lastT = t;
      out = { kind: "frame", t, row };
    } else if (typ === "hypothesis") {
      if (typeof get(ev, "id") !== "string" || typeof get(ev, "is_final") !== "boolean") {
        throw new StreamEventError("hypothesis needs a string id and a boolean is_final");
      }
      checkNbest(ev);
      if (has(ev, DECLARATION_KEY)) {
        const errs = validateDeclaration(ev[DECLARATION_KEY]);
        if (errs.length) throw new StreamEventError(`${errs.join("; ")} (FEP-0001 section 4)`);
      }
      out = { kind: "hypothesis", isFinal: ev.is_final as boolean };
    } else if (typ === "segment_end") out = { kind: "segment_end" };
    else if (typ === "end") {
      this.ended = true;
      out = { kind: "end" };
    } else if (typ === "signal_quality") out = { kind: "other" };
    else {
      this.ignoredEvents++;
      out = { kind: "ignored", reason: "event type not used by the validator" };
    }
    this.nEvents++;
    return out;
  }
}
