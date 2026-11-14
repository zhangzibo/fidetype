/**
 * Helpers for `trust_decision` events (FEP-0001 section 3; intent decisions
 * of FEP-0003 section 5): what a consumer may act on, and the checks a
 * consumer can run on a live decision stream.
 *
 * Rule 1: a consumer MUST NOT act on a decision with `is_final = false`.
 * Rule 3: a bridge to a lossy output forwards only final COMMIT decisions
 * (or a user selection after OFFER).
 * Rule 9 (SHOULD): no final COMMIT with an empty or white-space text.
 */

import { get, has, isObj, parseJson } from "./json.js";
import { tdIntentFormatErrors } from "./profiles/fep0003.js";
import { isInt } from "./profiles/common.js";

export type DecisionKind = "commit" | "offer" | "ask" | "abstain" | "offer_words" | "preview" | "invalid";

export interface HandledDecision {
  /** The event as received. */
  event: Record<string, unknown>;
  /** What a consumer does: act only on "commit" (and on a user selection after "offer"). "preview": is_final = false. */
  kind: DecisionKind;
  /** `profile`: "text" (default) or "intent". */
  profile: string;
  /** Final COMMIT: the committed text (`shown[0]`) or the committed intent. null if omitted (privacy logs). */
  committed: string | null;
  /** Texts or intents offered to the user (OFFER, ASK, OFFER_WORDS). */
  offered: string[];
  /** True if a bridge to an output may forward it now (rules 1, 3 and 9). */
  forward: boolean;
  /** Rule violations (MUST): format, order, one final per utterance or unit. */
  errors: string[];
  /** SHOULD-level findings, for example rule 9 (empty committed text). */
  warnings: string[];
}

/** Python `str.strip()` emptiness (white space only). */
const blankText = (s: string): boolean => /^[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/.test(s);

/** True for a final COMMIT (rule 1). */
export function isFinalCommit(d: Record<string, unknown>): boolean {
  return get(d, "type") === "trust_decision" && get(d, "is_final") === true && get(d, "action") === "COMMIT";
}

/** The committed text of a final text COMMIT (`shown[0]`), or null. */
export function committedText(d: Record<string, unknown>): string | null {
  if (!isFinalCommit(d) || get(d, "profile") === "intent") return null;
  const sh = get(d, "shown");
  return Array.isArray(sh) && sh.length && typeof sh[0] === "string" ? sh[0] : null;
}

/**
 * FEP-0001 section 3 rule 9: a final COMMIT whose committed text is empty
 * or only white space. Returns a warning text, or null.
 */
export function emptyCommitWarning(d: Record<string, unknown>): string | null {
  if (!isFinalCommit(d) || get(d, "profile") === "intent") return null;
  const sh = get(d, "shown");
  if (!Array.isArray(sh) || !sh.length || typeof sh[0] !== "string" || !blankText(sh[0])) return null;
  const why = typeof get(d, "reason") === "string" && (d.reason as string).trim() ? ` (reason: ${d.reason})` : " and gives no reason";
  return `FEP-0001 section 3 rule 9: final COMMIT with an empty committed text${why}; a bridge SHOULD NOT forward it`;
}

const KIND: Record<string, DecisionKind> = { COMMIT: "commit", OFFER: "offer", ASK: "ask", ABSTAIN: "abstain", OFFER_WORDS: "offer_words" };

/**
 * Track a stream of trust_decision events (one session or many) and tell
 * the consumer what to do with each one.
 *
 * ```ts
 * const t = new DecisionTracker();
 * for (const ev of events) {
 *   const d = t.push(ev);
 *   if (d.forward) output.type(d.committed!);
 * }
 * ```
 */
export class DecisionTracker {
  private lastSeq = new Map<string, number>();
  private last = new Map<string, number>();
  private finals = new Set<string>();
  private n = 0;

  push(input: string | Record<string, unknown>): HandledDecision {
    this.n++;
    let ev: Record<string, unknown>;
    try {
      const parsed = typeof input === "string" ? parseJson(input) : input;
      if (!isObj(parsed)) throw new TypeError("a decision must be a JSON object");
      ev = parsed;
    } catch (e) {
      return { event: {}, kind: "invalid", profile: "text", committed: null, offered: [], forward: false, errors: [(e as Error).message], warnings: [] };
    }
    const errors: string[] = [];
    if (get(ev, "type") !== "trust_decision") errors.push("not a trust_decision event");
    // Pass the parsed object itself: a copy would lose its float-literal marks (1.0 is not an integer).
    errors.push(...tdIntentFormatErrors(ev).map((x) => x.replace(/^line [^:]+: /, "")));
    errors.push(...this.order(ev));
    const profile = typeof get(ev, "profile") === "string" ? (ev.profile as string) : "text";
    const action = get(ev, "action");
    const final = get(ev, "is_final") === true;
    let kind: DecisionKind = errors.length ? "invalid" : final ? (Object.prototype.hasOwnProperty.call(KIND, action as string) ? KIND[action as string] : "invalid") : "preview";
    if (!errors.length && !final && !(typeof action === "string" && Object.prototype.hasOwnProperty.call(KIND, action))) kind = "invalid";
    const offeredRaw = profile === "intent" ? get(ev, "offered") : get(ev, "shown");
    const offered = Array.isArray(offeredRaw) ? offeredRaw.filter((x): x is string => typeof x === "string") : [];
    let committed: string | null = null;
    if (kind === "commit") committed = profile === "intent" ? ((get(ev, "intent") as string | null) ?? null) : committedText(ev);
    const warnings: string[] = [];
    const w = emptyCommitWarning(ev);
    if (w) warnings.push(w);
    const forward = kind === "commit" && committed !== null && !w;
    return { event: ev, kind, profile, committed, offered: kind === "commit" ? [] : offered, forward, errors, warnings };
  }

  /** seq increases per session; one final decision per (session, utterance) or (session, unit); none after it. */
  private order(e: Record<string, unknown>): string[] {
    const errs: string[] = [];
    const sid = has(e, "session") ? e.session : "";
    if (typeof sid !== "string") return errs;
    if (isInt(e, "seq")) {
      const s = e.seq as number;
      if (this.lastSeq.has(sid) && s <= (this.lastSeq.get(sid) as number)) errs.push(`seq ${s} does not increase in session '${sid}' (rule 5)`);
      this.lastSeq.set(sid, Math.max(s, this.lastSeq.get(sid) ?? s));
    }
    const key = get(e, "profile") === "intent" ? "unit" : "utterance";
    if (!isInt(e, key)) return errs;
    const val = e[key] as number;
    const pk = JSON.stringify([sid, key]);
    if (this.last.has(pk) && val < (this.last.get(pk) as number)) errs.push(`${key} ${val} goes back in session '${sid}' (rule 5)`);
    this.last.set(pk, Math.max(val, this.last.get(pk) ?? val));
    const fk = JSON.stringify([sid, key, val]);
    if (this.finals.has(fk)) errs.push(`a decision for ${key} ${val} of session '${sid}' after its final one (rules 6-7)`);
    if (get(e, "is_final") === true) this.finals.add(fk);
    return errs;
  }
}

/** Handle every decision of a decision log (JSON Lines text or parsed events). */
export function handleDecisions(events: Iterable<string | Record<string, unknown>>): HandledDecision[] {
  const t = new DecisionTracker();
  return [...events].map((e) => t.push(e));
}
