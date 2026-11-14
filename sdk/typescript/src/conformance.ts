/**
 * Conformance runner: run a consumer over the golden vectors of a profile
 * (`spec/conformance/<profile>/manifest.json`), the same files that the
 * Python suite uses (`python -m fidetype.conformance consumer`).
 *
 * Platform neutral: the caller gives a function that reads a vector file
 * (Node: `node:fs`; browser: `fetch`). See `node.ts` for a Node helper.
 */

import { loadStream } from "./checks.js";
import { decodeUtf8, isObj, parseJson } from "./json.js";
import * as fep0001 from "./profiles/fep0001.js";
import * as fep0002 from "./profiles/fep0002.js";
import * as fep0003 from "./profiles/fep0003.js";

export type Consumer = (name: string, bytes: Uint8Array) => Record<string, unknown>;

/** Reference consumers of the TypeScript SDK, by profile name. */
export const CONSUMERS: Record<string, Consumer> = {
  "v0.1": (name, bytes) => loadStream(name, bytes).summary,
  "fep-0001": fep0001.consume,
  "fep-0002": fep0002.consume,
  "fep-0003": fep0003.consume,
};

export const PROFILE_TITLES: Record<string, string> = {
  "v0.1": "NeuralTextStream v0.1",
  "fep-0001": "FEP-0001 streaming trust events",
  "fep-0002": "FEP-0002 NeuralTextStream over LSL",
  "fep-0003": "FEP-0003 output profiles and discrete intent events",
};

export interface VectorOutcome {
  id: string;
  file: string;
  expect: string;
  actual: "accept" | "reject";
  ok: boolean;
  detail: string;
}

export interface ProfileReport {
  schema: "fidetype.conformance.consumer-report/1";
  consumer: string;
  profile: string;
  passed: number;
  total: number;
  ok: boolean;
  vectors: VectorOutcome[];
}

/** Python `==` on JSON values (1 == 1.0, deep lists and dicts). */
export function pyEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a === "number" && typeof b === "number") return a === b || (Number.isNaN(a) && Number.isNaN(b) && false);
  if (typeof a === "boolean" || typeof b === "boolean") {
    // Python: True == 1, False == 0
    const na = typeof a === "boolean" ? Number(a) : a;
    const nb = typeof b === "boolean" ? Number(b) : b;
    return typeof na === "number" && typeof nb === "number" && na === nb;
  }
  if (a === null || b === null || a === undefined || b === undefined) return false;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => pyEqual(x, b[i]));
  if (isObj(a) && isObj(b)) {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && pyEqual(a[k], b[k]));
  }
  return false;
}

/** Run a consumer over one profile's vectors. `read(file)` returns the bytes of a file in the profile folder. */
export async function runVectors(
  profile: string,
  read: (file: string) => Uint8Array | Promise<Uint8Array>,
  consumer: Consumer | undefined = Object.prototype.hasOwnProperty.call(CONSUMERS, profile) ? CONSUMERS[profile] : undefined,
  consumerName = `fidetype (TypeScript SDK) ${profile} reference consumer`,
): Promise<ProfileReport> {
  if (!consumer) throw new RangeError(`unknown profile '${profile}'; known: ${Object.keys(CONSUMERS).join(", ")}`);
  const manifest = parseJson(decodeUtf8(await read("manifest.json")));
  if (!isObj(manifest) || !Array.isArray(manifest.vectors)) throw new RangeError("manifest.json has no vectors list");
  const vectors: VectorOutcome[] = [];
  for (const v of manifest.vectors as Record<string, unknown>[]) {
    const file = String(v.file);
    let res: Record<string, unknown> | null = null;
    let actual: "accept" | "reject";
    let detail = "";
    try {
      res = consumer(file, await read(file));
      actual = "accept";
    } catch (e) {
      actual = "reject";
      detail = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
    }
    let ok = actual === v.expect;
    const expected = v.expected;
    if (ok && actual === "accept" && isObj(expected) && res) {
      const diffs = Object.entries(expected)
        .filter(([k, want]) => Object.prototype.hasOwnProperty.call(res, k) && !pyEqual(res?.[k], want))
        .map(([k, want]) => `${k}: expected ${JSON.stringify(want)}, got ${JSON.stringify(res?.[k])}`);
      if (diffs.length) {
        ok = false;
        detail = diffs.join("; ");
      }
    }
    vectors.push({ id: String(v.id), file, expect: String(v.expect), actual, ok, detail: detail.slice(0, 300) });
  }
  const passed = vectors.filter((o) => o.ok).length;
  return {
    schema: "fidetype.conformance.consumer-report/1", consumer: consumerName, profile, passed, total: vectors.length,
    ok: passed === vectors.length, vectors,
  };
}

/** One summary line, as the Python CLI prints it. */
export function reportLine(r: ProfileReport): string {
  return `[${PROFILE_TITLES[r.profile] ?? r.profile} consumer conformance: ${r.ok ? "PASS" : "FAIL"}] ${r.passed}/${r.total} golden vectors`;
}
