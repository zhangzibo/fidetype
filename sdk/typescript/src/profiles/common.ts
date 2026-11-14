/** Shared parts of the FEP conformance profiles. */

import { CheckResult, StreamRejected } from "../checks.js";
import { decodeUtf8, isBlank, isObj, parseJson, pyLines } from "../json.js";

export type Ev = Record<string, unknown> & { type: string; _line: number };

/** Read a JSON Lines file. Return (events with `_line`, parse errors). Port of fep0001.read_events. */
export function readEvents(bytes: Uint8Array): [Ev[], string[]] {
  const events: Ev[] = [];
  const errs: string[] = [];
  let text: string;
  try {
    text = decodeUtf8(bytes);
  } catch (e) {
    return [[], [`cannot read: ${e instanceof Error ? e.message : String(e)}`]];
  }
  pyLines(text).forEach((line, k) => {
    const n = k + 1;
    if (isBlank(line)) return;
    let obj: unknown;
    try {
      obj = parseJson(line);
    } catch (e) {
      errs.push(`line ${n}: not JSON: ${e instanceof Error ? e.message : String(e)}`);
      return;
    }
    if (!isObj(obj) || typeof obj.type !== "string") {
      errs.push(`line ${n}: not an object with a string type`);
      return;
    }
    obj._line = n;
    events.push(obj as Ev);
  });
  return [events, errs];
}

/** `input`, `decisions` or `unknown`. */
export function streamKind(events: Ev[]): "input" | "decisions" | "unknown" {
  if (!events.length) return "unknown";
  if (events[0].type === "header") return "input";
  if (events.every((e) => e.type === "trust_decision")) return "decisions";
  return "unknown";
}

export type CheckMeta = [id: string, keyword: string, clause: string, title: string];

export function makeRes(meta: Record<string, CheckMeta>, fep: string) {
  return (cid: string, errs: string[] | null, msgOk = "", skipped: string | null = null): CheckResult => {
    const [, kw, clause, title] = meta[cid];
    let status: CheckResult["status"];
    let message: string;
    if (skipped !== null) [status, message] = ["skip", skipped];
    else if (errs && errs.length) {
      status = "fail";
      message = errs.slice(0, 6).join("; ") + (errs.length > 6 ? ` (+${errs.length - 6} more)` : "");
    } else [status, message] = ["pass", msgOk];
    return { id: cid, level: "core", keyword: kw, clause: `${fep} ${clause}`, title, status, message, heuristic: false };
  };
}

/** A profile target report. */
export interface TargetReport {
  target: string;
  checks: CheckResult[];
  info: Record<string, unknown>;
}

export function failures(rep: TargetReport): CheckResult[] {
  return rep.checks.filter((c) => c.status === "fail");
}

/** Throw StreamRejected for the first failure of a report. */
export function rejectOnFailure(rep: TargetReport): void {
  const f = failures(rep);
  if (f.length) throw new StreamRejected(`[${f[0].id}, ${f[0].clause}] ${f[0].message}`, f[0].clause, f[0].id);
}

export const isInt = (o: Record<string, unknown>, k: string): boolean => {
  const v = o[k];
  return typeof v === "number" && Number.isInteger(v) && !floatMarked(o, k);
};
import { isFloatLiteral as floatMarked } from "../json.js";

export const repr = (x: unknown): string => {
  try {
    return JSON.stringify(x) ?? String(x);
  } catch {
    return String(x);
  }
};
