/**
 * The checks of the NeuralTextStream v0.1 conformance suite (port of
 * `fidetype.conformance.checks`) and the reference consumer
 * {@link loadStream} (port of `fidetype.conformance.io.load_stream`).
 *
 * Levels: `core` (MUST rules; a consumer MUST reject a stream that fails
 * one), `trust-ready`, `provenance`, and `advisory` (a warning only).
 */

import {
  CLOCK_DOMAINS, MODALITIES, NORM_TOL, SCORE_SEMANTICS, SPEC_VERSION, SQ_UNITS, VOCAB, VOCAB_TYPES,
} from "./constants.js";
import { get, has, isIntAt, isNum, isObj } from "./json.js";
import { NdArray, RawStream, UNPARSEABLE_META, readRaw } from "./raw.js";

export const LEVELS = ["core", "trust-ready", "provenance"] as const;
export type Level = (typeof LEVELS)[number] | "advisory";
export type Status = "pass" | "fail" | "skip";

export interface CheckResult {
  id: string;
  level: Level;
  keyword: string;
  clause: string;
  title: string;
  status: Status;
  message: string;
  heuristic: boolean;
}

type Fn = (raw: RawStream) => [Status, string];

interface CheckDef {
  id: string;
  level: Level;
  keyword: string;
  clause: string;
  title: string;
  fn: Fn;
  heuristic: boolean;
  formats: string[];
}

const REGISTRY: CheckDef[] = [];
const ALL_FORMATS = ["npz", "jsonl"];

function check(id: string, level: Level, keyword: string, clause: string, title: string, fn: Fn,
  opts: { heuristic?: boolean; formats?: string[] } = {}): void {
  REGISTRY.push({ id, level, keyword, clause, title, fn, heuristic: opts.heuristic ?? false, formats: opts.formats ?? ALL_FORMATS });
}

const ok = (m = ""): [Status, string] => ["pass", m];
const bad = (m: string): [Status, string] => ["fail", m];
const skip = (m: string): [Status, string] => ["skip", m];
const repr = (x: unknown): string => {
  try {
    return typeof x === "symbol" ? "<unparseable meta>" : JSON.stringify(x) ?? String(x);
  } catch {
    return String(x);
  }
};

/** True if a failure of a check at `checkLevel` blocks `level`. */
export function blocks(checkLevel: Level, level: Level): boolean {
  if (checkLevel === "advisory") return false;
  return LEVELS.indexOf(checkLevel as (typeof LEVELS)[number]) <= LEVELS.indexOf(level as (typeof LEVELS)[number]);
}

// --- helpers -----------------------------------------------------------------------------

const vocabOf = (raw: RawStream): unknown[] | null => (Array.isArray(raw.header.vocab) ? (raw.header.vocab as unknown[]) : null);
const metaOf = (raw: RawStream): Record<string, unknown> | null => {
  const m = metaValue(raw);
  return isObj(m) ? m : null;
};
const metaValue = (raw: RawStream): unknown => (has(raw.header, "meta") ? raw.header.meta : {});
const lp2d = (raw: RawStream): NdArray | null => (raw.logProbs && raw.logProbs.shape.length === 2 ? raw.logProbs : null);
const isIntV = (o: Record<string, unknown>, k: string): boolean => isIntAt(o, k);
const issues = (raw: RawStream, id: string): [Status, string] | null => {
  const msgs = raw.issues.filter((i) => i.checkId === id).map((i) => i.message);
  return msgs.length ? bad(msgs.join("; ")) : null;
};
const hget = (raw: RawStream, k: string): unknown => get(raw.header, k);

/** (dotted key path, value) for every leaf of a JSON value. */
function* walk(obj: unknown, prefix = ""): Generator<[string, unknown]> {
  if (isObj(obj)) {
    for (const [k, v] of Object.entries(obj)) {
      const p = prefix ? `${prefix}.${k}` : k;
      yield [p, v];
      yield* walk(v, p);
    }
  } else if (Array.isArray(obj)) {
    for (let i = 0; i < obj.length; i++) yield* walk(obj[i], `${prefix}[${i}]`);
  }
}
const lastSeg = (p: string): string => {
  const parts = p.split(/[.[]/);
  return parts[parts.length - 1].toLowerCase();
};

// --- defined meta keys (spec 4.2) ------------------------------------------------------

const SHA256_RE = /^[0-9a-f]{64}$/;
const BCP47_RE = /^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$/;
type TypeFn = (m: Record<string, unknown>, k: string) => string | null;
const tStr: TypeFn = (m, k) => (typeof m[k] === "string" && m[k] !== "" ? null : "a non-empty string");
const tBool: TypeFn = (m, k) => (typeof m[k] === "boolean" ? null : "a boolean");
const tEnum = (vals: readonly string[]): TypeFn => (m, k) => (vals.includes(m[k] as string) ? null : `one of ${repr(vals)}`);
const tIntGe1: TypeFn = (m, k) => (isIntV(m, k) && (m[k] as number) >= 1 ? null : "an integer >= 1");
const tNonneg: TypeFn = (m, k) => (isNum(m[k]) && Number.isFinite(m[k]) && (m[k] as number) >= 0 ? null : "a finite number >= 0");
const tSha: TypeFn = (m, k) => (typeof m[k] === "string" && SHA256_RE.test(m[k] as string) ? null : "64 lowercase hex characters (SHA-256)");
const tLang: TypeFn = (m, k) => (typeof m[k] === "string" && pyMatch(BCP47_RE, m[k] as string) ? null : "a BCP 47 language tag");
/** Python `re.match` with a `$` anchor also accepts one trailing newline. */
const pyMatch = (re: RegExp, s: string): boolean => re.test(s) || (s.endsWith("\n") && re.test(s.slice(0, -1)));

export const DEFINED_KEYS: Record<string, TypeFn> = {
  "device.modality": tEnum(MODALITIES), "device.vendor": tStr, "device.model": tStr, "device.channel_count": tIntGe1,
  "device.invasive": tBool, "device.regulatory_status": tStr, "decoder.name": tStr, "decoder.version": tStr,
  "decoder.causal": tBool, "decoder.lookahead_s": tNonneg, "decoder.calibration_id": tStr,
  "decoder.calibration_method": tStr, "decoder.weights_sha256": tSha, "adapter.name": tStr, "adapter.version": tStr,
  "stream.id": tStr, "lm.name": tStr, "user.personalized": tBool, "session.id": tStr, "subject.id": tStr,
  language: tLang, "calibration.applied": tBool, "data.derived": tBool, "consent.ref": tStr,
};
const DEFINED_NAMESPACES = [...new Set(Object.keys(DEFINED_KEYS).filter((k) => k.includes(".")).map((k) => k.split(".")[0]))].sort();
const KNOWN_VOCAB_IDS: Record<string, readonly string[]> = { "char.b2q-28": VOCAB };
const LEAK_KEY_NAMES = new Set(["target_text", "typed_text", "truth", "ground_truth", "groundtruth", "label", "labels", "transcript",
  "transcription", "cue_sentence", "cue_text", "sentence", "reference_text", "target", "answer", "true_text", "gold"]);
const PII_KEY_NAMES = new Set(["name", "full_name", "first_name", "last_name", "email", "e_mail", "dob", "date_of_birth",
  "birthdate", "birth_date", "address", "phone", "phone_number", "mrn", "medical_record_number", "ssn"]);
const PERSON_NS = new Set(["subject", "participant", "user", "patient", "person", "operator"]);
const FREE_TEXT_KEY_NAMES = new Set(["note", "notes", "comment", "comments", "remarks", "description"]);
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const PSEUDO_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/;
const ARPABET = new Set("AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K L M N NG OW OY P R S SH T TH UH UW V W Y Z ZH".split(" "));
const PHONEME_MARKERS = new Set(["SIL", "SP", "sil", "sp", "|", "<sil>", "<sp>"]);
const W3C_CODE_RE = new RegExp(
  "^(Key[A-Z]|Digit[0-9]|Numpad\\w+|F[0-9]{1,2}|Arrow(Up|Down|Left|Right)|Space|Enter|Backspace|Tab|Escape|" +
  "(Shift|Control|Alt|Meta)(Left|Right)|CapsLock|Minus|Equal|BracketLeft|BracketRight|Backslash|Semicolon|" +
  "Quote|Backquote|Comma|Period|Slash|Delete|Home|End|PageUp|PageDown|Insert|IntlBackslash|ContextMenu)$",
);

// --- parse and serialisation (6.1, 6.2) ------------------------------------------------------

check("NTS-PARSE", "core", "MUST", "6.1 / 6.2", "The file loads in its serialisation (NPZ without pickle; UTF-8 JSON Lines)",
  (raw) => issues(raw, "NTS-PARSE") ?? ok());
check("NTS-NPZ-KEYS", "core", "MUST", "6.1", "The NPZ file has all required keys", (raw) => issues(raw, "NTS-NPZ-KEYS") ?? ok(),
  { formats: ["npz"] });
check("NTS-NPZ-DTYPE", "advisory", "SHOULD", "6.1", "NPZ dtypes follow the 6.1 table (log_probs float32, frame_times float64, blank_id int64)",
  (raw) => {
    const want: Record<string, string> = { log_probs: "float32", frame_times: "float64", blank_id: "int64", frame_period: "float64", latency: "float64" };
    const diffs = Object.entries(want).filter(([k, d]) => has(raw.npzDtypes, k) && raw.npzDtypes[k] !== d)
      .map(([k, d]) => `${k} is ${raw.npzDtypes[k]}, table says ${d}`);
    return diffs.length ? bad(diffs.join("; ")) : ok();
  }, { formats: ["npz"] });
check("NTS-UNKNOWN-KEYS", "advisory", "MUST", "6.1 note / 6.2.5", "Unknown keys are reported; a consumer MUST ignore them",
  (raw) => ok(raw.unknownKeys.length ? `unknown keys (a consumer ignores them): ${repr(raw.unknownKeys)}` : ""));
check("NTS-JSONL-HEADER", "core", "MUST", "6.2.1", "Line 1 is the header with type, spec_version, vocab, vocab_type, blank_id",
  (raw) => issues(raw, "NTS-JSONL-HEADER") ?? ok(), { formats: ["jsonl"] });
check("NTS-JSONL-FRAME", "core", "MUST", "6.2.2 / 6.2.3", "Each frame has t and log_probs (numbers or null) or the sparse keys",
  (raw) => issues(raw, "NTS-JSONL-FRAME") ?? ok(), { formats: ["jsonl"] });
check("NTS-JSONL-END", "advisory", "SHOULD", "6.2", "No lines after the end marker", (raw) => {
  if (raw.linesAfterEnd) return bad(`${raw.linesAfterEnd} line(s) after the end marker (ignored; see ambiguity A5)`);
  return ok(raw.hasEnd ? "end marker present" : "no end marker (allowed, 6.2.6)");
}, { formats: ["jsonl"] });

// --- frame core structure (3.1, 5.1) -------------------------------------------------------

check("NTS-VERSION", "core", "MUST", "5.1.4", 'spec_version is a version the consumer supports ("0.1")', (raw) => {
  if (!has(raw.header, "spec_version")) return skip("no spec_version (reported by the serialisation check)");
  const v = raw.header.spec_version;
  return v === SPEC_VERSION ? ok() : bad(`spec_version ${repr(v)} is not supported (this suite supports '${SPEC_VERSION}')`);
});
check("NTS-LP-2D", "core", "MUST", "5.1.1", "log_probs has exactly 2 dimensions [T, V]", (raw) => {
  const r = issues(raw, "NTS-LP-2D");
  if (r) return r;
  if (!raw.logProbs) return skip("no log_probs");
  return raw.logProbs.shape.length === 2 ? ok() : bad(`log_probs has shape ${repr(raw.logProbs.shape)}`);
});
check("NTS-V-MATCH", "core", "MUST", "5.1.2", "V equals the length of vocab", (raw) => {
  const r = issues(raw, "NTS-V-MATCH");
  if (r) return r;
  const lp = lp2d(raw);
  const v = vocabOf(raw);
  if (!lp || !v) return skip("no 2-D log_probs or no vocab list");
  return lp.shape[1] === v.length ? ok() : bad(`log_probs has ${lp.shape[1]} columns, vocab has ${v.length} tokens`);
});
check("NTS-FT-SHAPE", "core", "MUST", "5.1.3", "frame_times has shape [T]", (raw) => {
  const r = issues(raw, "NTS-FT-SHAPE");
  if (r) return r;
  const lp = lp2d(raw);
  const ft = raw.frameTimes;
  if (!lp || !ft) return skip("no log_probs or frame_times");
  return ft.shape.length === 1 && ft.shape[0] === lp.shape[0] ? ok() : bad(`frame_times has shape ${repr(ft.shape)}, expected (${lp.shape[0]},)`);
});
check("NTS-VOCAB-TYPE", "core", "MUST", "5.1.5", "vocab_type is one of char, key, word, phoneme, command, other", (raw) => {
  const vt = hget(raw, "vocab_type");
  if (vt === null && !has(raw.header, "vocab_type")) return skip("no vocab_type (reported by the serialisation check)");
  return (VOCAB_TYPES as readonly unknown[]).includes(vt) ? ok() : bad(`vocab_type ${repr(vt)} is not one of ${repr(VOCAB_TYPES)}`);
});
check("NTS-VOCAB-STR", "core", "MUST", "3.1", "vocab is a list of strings", (raw) => {
  if (!has(raw.header, "vocab")) return skip("no vocab");
  const v = raw.header.vocab;
  if (!Array.isArray(v)) return bad("vocab is not a list");
  const badItems = v.map((t, i) => (typeof t === "string" ? -1 : i)).filter((i) => i >= 0);
  return badItems.length ? bad(`vocab items ${repr(badItems.slice(0, 5))} are not strings`) : ok();
});
check("NTS-VOCAB-UNIQUE", "core", "MUST", "5.2.4", "vocab tokens are unique", (raw) => {
  const v = vocabOf(raw);
  if (!v) return skip("no vocab list");
  const seen = new Set<string>();
  const dup: unknown[] = [];
  for (const t of v) {
    const k = typeof t === "string" ? `s:${t}` : `j:${JSON.stringify(t)}`;
    if (seen.has(k)) dup.push(t);
    seen.add(k);
  }
  return dup.length ? bad(`duplicate tokens ${repr(dup.slice(0, 5))}`) : ok();
});
check("NTS-BLANK", "core", "MUST", "3.1 / 5.1.6", "blank_id is null or an integer in 0..V-1", (raw) => {
  if (!has(raw.header, "blank_id")) return skip("no blank_id (reported by the serialisation check)");
  const b = raw.header.blank_id;
  if (b === null) return ok("no blank (not a CTC decoder)");
  if (!isIntV(raw.header, "blank_id")) return bad(`blank_id ${repr(b)} is not an integer or null`);
  const v = vocabOf(raw);
  if (!v) return skip("no vocab list");
  return (b as number) >= 0 && (b as number) < v.length ? ok() : bad(`blank_id ${b} is out of range 0..${v.length - 1}`);
});
check("NTS-SOURCE", "core", "MUST", "5.1.7", "source, if present, is a non-empty string", (raw) => {
  if (!has(raw.header, "source")) return ok('absent (default "unknown")');
  const s = raw.header.source;
  return typeof s === "string" && s ? ok() : bad(`source ${repr(s)} is not a non-empty string`);
});
check("NTS-META-OBJECT", "core", "MUST", "5.1.7", "meta, if present, is a JSON object", (raw) => {
  const m = metaValue(raw);
  if (m === UNPARSEABLE_META) return skip("meta is not parseable (reported by NTS-META-JSON)");
  return isObj(m) ? ok() : bad("meta is not an object");
});
check("NTS-META-JSON", "core", "MUST", "4.1", "meta values are JSON values (no NaN, no infinity, no other types)", (raw) => {
  const r = issues(raw, "NTS-META-JSON");
  if (r) return r;
  const m = metaValue(raw);
  // Python json.dumps(allow_nan=False): infinity (from a 1e400 literal) is not JSON.
  for (const [, v] of walk(m)) if (typeof v === "number" && !Number.isFinite(v)) return bad("meta is not pure JSON: out of range float");
  if (typeof m === "number" && !Number.isFinite(m)) return bad("meta is not pure JSON: out of range float");
  return ok();
});

// --- values (5.2) -------------------------------------------------------------------------

check("NTS-LP-FINITE", "core", "MUST", "5.2.2", "log_probs has no NaN and no +inf (-inf is allowed)", (raw) => {
  const lp = lp2d(raw);
  if (!lp) return skip("no 2-D log_probs");
  let nNan = 0;
  let nPinf = 0;
  for (const x of lp.data) {
    if (Number.isNaN(x)) nNan++;
    else if (x === Infinity) nPinf++;
  }
  return nNan || nPinf ? bad(`${nNan} NaN and ${nPinf} +inf values`) : ok();
});

/** Log-sum-exp of each row (rows of only -inf give -inf), as the Python reference computes it. */
export function rowLse(data: ArrayLike<number>, T: number, V: number): Float64Array {
  const out = new Float64Array(T);
  for (let t = 0; t < T; t++) {
    let m = -Infinity;
    for (let v = 0; v < V; v++) m = Math.max(m, data[t * V + v]);
    const ms = Number.isFinite(m) ? m : 0;
    let s = 0;
    for (let v = 0; v < V; v++) s += Math.exp(data[t * V + v] - ms);
    out[t] = Math.log(s) + ms;
  }
  return out;
}

check("NTS-NORM", "core", "MUST", "5.2.1", `Each row of log_probs log-sum-exps to 0 (tolerance ${NORM_TOL})`, (raw) => {
  const lp = lp2d(raw);
  if (!lp) return skip("no 2-D log_probs");
  const [T, V] = lp.shape;
  if (T === 0) return ok("no frames");
  for (const x of lp.data) if (Number.isNaN(x) || x === Infinity) return skip("non-finite values (reported by NTS-LP-FINITE)");
  const lse = rowLse(lp.data, T, V);
  const badRows: number[] = [];
  lse.forEach((x, t) => {
    if (!(Math.abs(x) <= NORM_TOL)) badRows.push(t);
  });
  if (badRows.length) return bad(`${badRows.length} row(s) not normalised; frame ${badRows[0]} gives log-sum-exp ${lse[badRows[0]].toPrecision(4)}`);
  return ok();
});
check("NTS-FT-FINITE", "core", "MUST", "5.2.3", "frame_times are finite", (raw) => {
  const ft = raw.frameTimes;
  if (!ft) return skip("no frame_times");
  return ft.data.every((x) => Number.isFinite(x)) ? ok() : bad("frame_times has non-finite values");
});
check("NTS-FT-MONO", "core", "MUST", "5.2.3 / 6.2.4", "frame_times increase strictly", (raw) => {
  const ft = raw.frameTimes;
  if (!ft || ft.shape.length !== 1) return skip("no 1-D frame_times");
  if (ft.data.length < 2) return ok("fewer than 2 frames");
  for (let i = 0; i + 1 < ft.data.length; i++) {
    if (!(ft.data[i + 1] - ft.data[i] > 0)) return bad(`frame ${i + 1} time ${ft.data[i + 1]} is not greater than frame ${i} time ${ft.data[i]}`);
  }
  return ok();
});
check("NTS-FRAME-PERIOD", "core", "MUST", "3.2 / 5.2.5", "frame_period, if present, is finite and > 0", (raw) => {
  const v = hget(raw, "frame_period");
  if (v === null) return ok("absent");
  return isNum(v) && Number.isFinite(v) && v > 0 ? ok() : bad(`frame_period ${repr(v)} is not finite and > 0`);
});
check("NTS-LATENCY", "core", "MUST", "3.2 / 5.2.5", "latency, if present, is finite and >= 0", (raw) => {
  const v = hget(raw, "latency");
  if (v === null) return ok("absent");
  return isNum(v) && Number.isFinite(v) && v >= 0 ? ok() : bad(`latency ${repr(v)} is not finite and >= 0`);
});

// --- sparse frames (3.3) -------------------------------------------------------------------

check("NTS-SPARSE", "core", "MUST", "3.3", "Sparse frames: k values plus rest_log_prob are normalised", (raw) => {
  if (!raw.sparseFrames.length) return skip("no sparse frames");
  for (const f of raw.sparseFrames) {
    if (!f.vals) continue; // malformed: reported by NTS-JSONL-FRAME
    const vals = [...f.vals, f.rest as number];
    if (vals.some((x) => Number.isNaN(x) || x === Infinity)) return bad(`line ${f.line}: NaN or +inf in a sparse frame`);
    const m = Math.max(...vals);
    const lse = Number.isFinite(m) ? Math.log(vals.reduce((s, x) => s + Math.exp(x - m), 0)) + m : -Infinity;
    if (!(Math.abs(lse) <= NORM_TOL)) return bad(`line ${f.line}: top-k plus rest log-sum-exp is ${lse.toPrecision(4)}`);
  }
  return ok(`${raw.sparseFrames.length} sparse frame(s)`);
}, { formats: ["jsonl"] });

// --- semantic conventions (4.1, 4.2) --------------------------------------------------------

check("NTS-META-TYPES", "core", "MUST", "4.1 / 4.2", "Defined meta keys have the type and values of section 4.2", (raw) => {
  const m = metaOf(raw);
  if (!m) return skip("meta is not an object");
  const errs: string[] = [];
  for (const [k, fn] of Object.entries(DEFINED_KEYS)) {
    if (has(m, k)) {
      const want = fn(m, k);
      if (want) errs.push(`${k} = ${repr(m[k])} must be ${want}`);
    }
  }
  return errs.length ? bad(errs.join("; ")) : ok();
});
check("NTS-META-LOOKAHEAD", "core", "MUST", "4.2", "decoder.lookahead_s equals latency when both are present", (raw) => {
  const m = metaOf(raw);
  const lat = hget(raw, "latency");
  if (!m || !has(m, "decoder.lookahead_s") || lat === null) return skip("not both present");
  const la = m["decoder.lookahead_s"];
  if (!isNum(la) || !isNum(lat)) return skip("not numeric (reported elsewhere)");
  return Math.abs(la - lat) <= 1e-9 ? ok() : bad(`decoder.lookahead_s ${la} != latency ${lat}`);
});
check("NTS-NAMESPACE", "advisory", "SHOULD", "4.1", "meta keys are namespaced; custom keys avoid the defined namespaces", (raw) => {
  const m = metaOf(raw);
  if (!m) return skip("meta is not an object");
  const flat = Object.keys(m).filter((k) => !k.includes(".") && !has(DEFINED_KEYS, k));
  const custom = Object.keys(m).filter((k) => k.includes(".") && !has(DEFINED_KEYS, k) && DEFINED_NAMESPACES.includes(k.split(".")[0]));
  const msgs: string[] = [];
  if (flat.length) msgs.push(`not namespaced: ${repr(flat)}`);
  if (custom.length) msgs.push(`custom keys inside a defined namespace: ${repr(custom)} (see ambiguity A2)`);
  return msgs.length ? bad(msgs.join("; ")) : ok();
});
check("NTS-LEAK-KEYS", "core", "MUST", "5.3.1", "meta has no key that names ground truth or target labels", (raw) => {
  const m = metaOf(raw);
  if (!m) return skip("meta is not an object");
  const hits = [...walk(m)].map(([p]) => p).filter((p) => LEAK_KEY_NAMES.has(lastSeg(p)));
  return hits.length ? bad(`keys that suggest ground truth: ${repr(hits)}`) : ok();
}, { heuristic: true });
check("NTS-PRIVACY", "core", "MUST", "5.4.1 / 4.2", "meta has no personal identifiers (e-mail, name, birth date keys)", (raw) => {
  const m = metaOf(raw);
  if (!m) return skip("meta is not an object");
  const hits = new Set<string>();
  for (const [p, v] of walk(m)) {
    const parts = p.split(/[.[]/).map((s) => s.toLowerCase());
    const last = parts[parts.length - 1];
    if (!has(DEFINED_KEYS, p) && PII_KEY_NAMES.has(last)) {
      if (last !== "name" || parts.slice(0, -1).some((s) => PERSON_NS.has(s)) || parts.length === 1) hits.add(`key ${p}`);
    }
    if (typeof v === "string" && EMAIL_RE.test(v)) hits.add(`e-mail address in ${p}`);
  }
  for (const k of ["stream.id", "consent.ref"]) {
    const v = get(m, k);
    if (typeof v === "string" && /\s/.test(v) && v.trim().split(/\s+/).length > 3) hits.add(`${k} looks like free text, not an opaque id`);
  }
  return hits.size ? bad([...hits].sort().join("; ")) : ok();
}, { heuristic: true });
check("NTS-FREE-TEXT", "advisory", "SHOULD NOT", "5.4.3", "meta has no free-text note fields", (raw) => {
  const m = metaOf(raw);
  if (!m) return skip("meta is not an object");
  const hits = [...walk(m)].map(([p]) => p).filter((p) => FREE_TEXT_KEY_NAMES.has(lastSeg(p)));
  return hits.length ? bad(`free-text keys: ${repr(hits)}`) : ok();
}, { heuristic: true });

// --- vocabulary identity and kinds (3.1, 3.4) -------------------------------------------------

check("NTS-VOCAB-ID", "core", "MUST", "3.4", "If a header vocab_id names a known registry entry, vocab matches it", (raw) => {
  const vid = hget(raw, "vocab_id");
  if (vid === null) return skip("no header vocab_id");
  if (Array.isArray(vid) || isObj(vid)) return bad("check raised TypeError: unhashable vocab_id"); // as Python's dict lookup
  if (typeof vid !== "string" || !has(KNOWN_VOCAB_IDS, vid)) return skip(`vocab_id ${repr(vid)} is not in the suite's registry copy`);
  const v = vocabOf(raw) ?? [];
  const want = KNOWN_VOCAB_IDS[vid];
  return v.length === want.length && v.every((t, i) => t === want[i]) ? ok() : bad(`vocab does not match ${vid}`);
});
check("NTS-VT-CHAR", "trust-ready", "PROFILE", "3.1", "char vocabulary: each non-blank token is one character", (raw) => {
  const v = vocabOf(raw);
  if (hget(raw, "vocab_type") !== "char" || !v) return skip("not a char vocabulary");
  const b = hget(raw, "blank_id");
  const badT = v.filter((t, i) => i !== b && !(typeof t === "string" && [...t].length === 1));
  return badT.length ? bad(`tokens that are not one character: ${repr(badT.slice(0, 6))}`) : ok();
});
check("NTS-VT-KEY", "advisory", "SHOULD", "3.1 / 10.7", "key vocabulary: tokens are W3C KeyboardEvent.code names", (raw) => {
  const v = vocabOf(raw);
  if (hget(raw, "vocab_type") !== "key" || !v) return skip("not a key vocabulary");
  const b = hget(raw, "blank_id");
  const badT = v.filter((t, i) => i !== b && !(typeof t === "string" && pyMatch(W3C_CODE_RE, t)));
  return badT.length ? bad(`tokens that are not W3C code names: ${repr(badT.slice(0, 6))}`) : ok();
});
check("NTS-VT-PHONEME", "advisory", "SHOULD", "3.1 / 3.4", "phoneme vocabulary: tokens are ARPAbet (plus silence markers) or IPA", (raw) => {
  const v = vocabOf(raw);
  if (hget(raw, "vocab_type") !== "phoneme" || !v) return skip("not a phoneme vocabulary");
  const b = hget(raw, "blank_id");
  const toks = v.filter((t, i) => i !== b && typeof t === "string") as string[];
  const nonAscii = (t: string): boolean => [...t].some((c) => (c.codePointAt(0) as number) > 127);
  const arpa = toks.every((t) => ARPABET.has(t.toUpperCase().replace(/[012]+$/, "")) || PHONEME_MARKERS.has(t));
  const ipa = toks.every((t) => nonAscii(t) || (/^\p{L}+$/u.test(t) && t === t.toLowerCase() && /\p{Ll}/u.test(t) && [...t].length <= 3) || PHONEME_MARKERS.has(t));
  if (arpa) return ok("ARPAbet");
  if (ipa && toks.some(nonAscii)) return ok("IPA");
  return bad("tokens are neither ARPAbet nor IPA (an encoded phoneme set? see ambiguity A3)");
});
check("NTS-VT-OTHER", "advisory", "SHOULD", "3.1", "vocab_type other: meta describes the tokens", (raw) => {
  if (hget(raw, "vocab_type") !== "other") return skip("not vocab_type other");
  const m = metaOf(raw) ?? {};
  return Object.keys(m).some((k) => k.includes("vocab")) || hget(raw, "vocab_id") ? ok() : bad("no meta key describes the vocabulary");
});
check("NTS-BLANK-TOKEN", "advisory", "SHOULD", "3.1", "The blank token is not a whitespace or empty string", (raw) => {
  const v = vocabOf(raw);
  const b = hget(raw, "blank_id");
  if (!v || !isIntV(raw.header, "blank_id") || (b as number) < 0 || (b as number) >= v.length) return skip("no valid blank");
  const t = v[b as number];
  return typeof t === "string" && !t.trim() ? bad(`blank token ${repr(t)} can be confused with text`) : ok();
});

// --- honest probabilities (2.4) ----------------------------------------------------------------

check("NTS-SHARPENED", "advisory", "MUST NOT", "2.4.4", "Rows are not all one-hot (a sign of sharpened output)", (raw) => {
  const lp = lp2d(raw);
  if (!lp || lp.shape[0] < 10 || lp.data.some((x) => Number.isNaN(x))) return skip("fewer than 10 frames");
  const [T, V] = lp.shape;
  let hot = 0;
  for (let t = 0; t < T; t++) {
    let m = -Infinity;
    for (let v = 0; v < V; v++) m = Math.max(m, lp.data[t * V + v]);
    if (m >= -1e-6) hot++;
  }
  const frac = hot / T;
  return frac > 0.9 ? bad(`${Math.round(frac * 100)}% of rows are one-hot`) : ok(`${Math.round(frac * 100)}% one-hot rows`);
});
check("NTS-FP-CONSIST", "advisory", "SHOULD", "3.2", "frame_period agrees with the median frame step (within 25 %)", (raw) => {
  const fp = hget(raw, "frame_period");
  const ft = raw.frameTimes;
  if (!isNum(fp) || !ft || ft.shape.length !== 1 || ft.data.length < 3 || !(fp > 0)) return skip("no frame_period or fewer than 3 frames");
  const d = [];
  for (let i = 0; i + 1 < ft.data.length; i++) d.push(ft.data[i + 1] - ft.data[i]);
  d.sort((a, b) => a - b);
  const med = d.length % 2 ? d[(d.length - 1) / 2] : (d[d.length / 2 - 1] + d[d.length / 2]) / 2;
  return Math.abs(med - fp) <= 0.25 * fp ? ok(`median step ${med} s`) : bad(`median step ${med} s vs frame_period ${fp}`);
});

// --- events (3.5-3.9, Development) ----------------------------------------------------------------

const eventsOf = (raw: RawStream, typ: string): Record<string, unknown>[] => raw.events.filter((e) => e.type === typ);

function scoreErrors(e: Record<string, unknown>, needSemantics: boolean, ignoreScore = false): string[] {
  const errs: string[] = [];
  const sem = get(e, "score_semantics");
  if (sem === null) {
    if (needSemantics) errs.push("no score_semantics");
    return errs;
  }
  if (!(SCORE_SEMANTICS as readonly unknown[]).includes(sem)) return [`score_semantics ${repr(sem)} is not one of ${repr(SCORE_SEMANTICS)}`];
  const sc = ignoreScore ? null : get(e, "score");
  if ((sem === "calibrated_prob" || sem === "uncalibrated_prob") && sc !== null && !(isNum(sc) && sc >= 0 && sc <= 1)) {
    errs.push(`score ${repr(sc)} is not in [0, 1] for ${sem} (3.5 rule 2)`);
  }
  if (sem === "power" || sem === "strength") {
    const rng = get(e, "score_range");
    if (!(Array.isArray(rng) && rng.length === 2 && rng.every(isNum))) errs.push(`score_semantics ${sem} needs score_range [min, max] (3.5 table)`);
  }
  if (sem === "none" && sc !== null) errs.push("score_semantics none needs a null or absent score");
  return errs;
}

check("NTS-EVT-DECISION", "core", "MUST", "3.5", "decision events: label, t, score_semantics and score rules", (raw) => {
  const evs = eventsOf(raw, "decision");
  if (!evs.length) return skip("no decision events");
  const errs: string[] = [];
  for (const e of evs) {
    const n = e._line;
    if (typeof get(e, "label") !== "string") errs.push(`line ${n}: no string label`);
    if (!isNum(get(e, "t"))) errs.push(`line ${n}: no numeric t`);
    errs.push(...scoreErrors(e, true).map((x) => `line ${n}: ${x}`));
  }
  return errs.length ? bad(errs.join("; ")) : ok(`${evs.length} decision event(s)`);
}, { formats: ["jsonl"] });
check("NTS-EVT-LABEL", "advisory", "SHOULD", "3.5", "decision labels are tokens in vocab", (raw) => {
  const evs = eventsOf(raw, "decision");
  const v = vocabOf(raw);
  if (!evs.length || !v) return skip("no decision events");
  const out = [...new Set(evs.map((e) => get(e, "label")).filter((l) => !v.includes(l)))];
  return out.length ? bad(`labels not in vocab: ${repr(out.slice(0, 5))}`) : ok();
}, { formats: ["jsonl"] });
check("NTS-EVT-HYPOTHESIS", "core", "MUST", "3.6", "hypothesis events: id, nbest, score_semantics, is_final", (raw) => {
  const evs = eventsOf(raw, "hypothesis");
  if (!evs.length) return skip("no hypothesis events");
  const errs: string[] = [];
  const ids = new Set<string>();
  for (const e of evs) {
    const n = e._line;
    const id = get(e, "id");
    if (typeof id !== "string") errs.push(`line ${n}: no string id`);
    else if (ids.has(id)) errs.push(`line ${n}: id '${id}' is not unique`);
    else ids.add(id);
    const nb = get(e, "nbest");
    if (!Array.isArray(nb) || !nb.every((x) => isObj(x) && typeof get(x, "text") === "string" && isNum(get(x, "score")))) {
      errs.push(`line ${n}: nbest must be a list of {text, score}`);
    }
    if (typeof get(e, "is_final") !== "boolean") errs.push(`line ${n}: is_final must be a boolean`);
    errs.push(...scoreErrors(e, true, true).map((x) => `line ${n}: ${x}`));
  }
  return errs.length ? bad(errs.join("; ")) : ok(`${evs.length} hypothesis event(s)`);
}, { formats: ["jsonl"] });
check("NTS-EVT-POINTER", "core", "MUST", "3.7", "pointer events: t, dims 1-3, mode, values", (raw) => {
  const evs = eventsOf(raw, "pointer");
  if (!evs.length) return skip("no pointer events");
  const errs: string[] = [];
  for (const e of evs) {
    const n = e._line;
    const d = get(e, "dims");
    if (!isNum(get(e, "t"))) errs.push(`line ${n}: no numeric t`);
    if (!(has(e, "dims") && isIntAt(e, "dims") && (d as number) >= 1 && (d as number) <= 3)) {
      errs.push(`line ${n}: dims must be 1-3`);
      continue;
    }
    const mode = get(e, "mode");
    if (mode !== "relative" && mode !== "absolute") errs.push(`line ${n}: mode must be relative or absolute`);
    const vals = get(e, "values");
    if (!(Array.isArray(vals) && vals.length === d && vals.every(isNum))) errs.push(`line ${n}: values must be ${d} numbers`);
    else if (mode === "absolute") {
      const absentRaw = get(e, "absent");
      const absent: unknown[] = pyTruthy(absentRaw) && Array.isArray(absentRaw) ? absentRaw : new Array(d as number).fill(false);
      const len = Math.min(vals.length, absent.length);
      for (let k = 0; k < len; k++) {
        const x = vals[k] as number;
        if (!pyTruthy(absent[k]) && !(x >= 0 && x <= 1)) {
          errs.push(`line ${n}: absolute values must be in [0, 1]`);
          break;
        }
      }
    }
  }
  return errs.length ? bad(errs.join("; ")) : ok(`${evs.length} pointer event(s)`);
}, { formats: ["jsonl"] });

/** Python truthiness of a JSON value. */
export function pyTruthy(x: unknown): boolean {
  if (x === null || x === undefined || x === false || x === 0 || x === "") return false;
  if (Array.isArray(x)) return x.length > 0;
  if (isObj(x)) return Object.keys(x).length > 0;
  if (typeof x === "number" && Number.isNaN(x)) return true;
  return true;
}

check("NTS-EVT-SIGNAL-QUALITY", "core", "MUST", "3.9", "signal_quality events: t, value, unit; index in [0, 1]", (raw) => {
  const evs = eventsOf(raw, "signal_quality");
  if (!evs.length) return skip("no signal_quality events");
  const errs: string[] = [];
  for (const e of evs) {
    const n = e._line;
    if (!isNum(get(e, "t")) || !isNum(get(e, "value"))) errs.push(`line ${n}: needs numeric t and value`);
    const unit = get(e, "unit");
    if (!(SQ_UNITS as readonly unknown[]).includes(unit)) errs.push(`line ${n}: unit must be one of ${repr(SQ_UNITS)}`);
    else if (unit === "index" && isNum(get(e, "value")) && !((e.value as number) >= 0 && (e.value as number) <= 1)) {
      errs.push(`line ${n}: index value must be in [0, 1]`);
    }
  }
  return errs.length ? bad(errs.join("; ")) : ok(`${evs.length} signal_quality event(s)`);
}, { formats: ["jsonl"] });
check("NTS-EVT-TIMING", "core", "MUST", "3.8", "t_signal_start <= t_signal_end <= t_decoded <= t_emitted when present", (raw) => {
  const keys = ["t_signal_start", "t_signal_end", "t_decoded", "t_emitted"];
  const evs = raw.events.filter((e) => keys.some((k) => has(e, k)));
  if (!evs.length) return skip("no extended timing");
  const errs: string[] = [];
  for (const e of evs) {
    const vals = keys.filter((k) => has(e, k)).map((k) => [k, e[k]] as [string, unknown]);
    if (!vals.every(([, v]) => isNum(v))) {
      errs.push(`line ${e._line}: timing values must be numbers`);
      continue;
    }
    for (let i = 0; i + 1 < vals.length; i++) {
      if ((vals[i][1] as number) > (vals[i + 1][1] as number)) errs.push(`line ${e._line}: ${vals[i][0]} ${vals[i][1]} > ${vals[i + 1][0]} ${vals[i + 1][1]}`);
    }
  }
  return errs.length ? bad(errs.join("; ")) : ok();
}, { formats: ["jsonl"] });
check("NTS-CLOCK", "core", "MUST", "3.8", "clock_domain, if present, is lsl, unix, monotonic, trial or other", (raw) => {
  if (!has(raw.header, "clock_domain")) return ok("absent (default trial)");
  const cd = raw.header.clock_domain;
  return (CLOCK_DOMAINS as readonly unknown[]).includes(cd) ? ok() : bad(`clock_domain ${repr(cd)} is not one of ${repr(CLOCK_DOMAINS)}`);
});

// --- trust-ready profile ------------------------------------------------------------------------

const metaOrEmpty = (raw: RawStream): Record<string, unknown> => metaOf(raw) ?? {};
check("TR-SOURCE", "trust-ready", "PROFILE", "3.2", 'source names the producer (present and not "unknown")', (raw) => {
  const s = hget(raw, "source");
  return typeof s === "string" && s && s !== "unknown" ? ok() : bad('source is absent or "unknown"');
});
check("TR-MODALITY", "trust-ready", "PROFILE", "4.2", "meta has device.modality", (raw) => {
  const m = metaOrEmpty(raw);
  return has(m, "device.modality") ? ok(String(m["device.modality"])) : bad("no device.modality");
});
check("TR-CAUSAL", "trust-ready", "SHOULD", "3.2 / 4.2", "meta has decoder.causal", (raw) =>
  has(metaOrEmpty(raw), "decoder.causal") ? ok() : bad("no decoder.causal (a consumer cannot tell online from offline output)"));
check("TR-OFFLINE-LATENCY", "trust-ready", "SHOULD", "3.2", "A non-causal (offline) decoder omits latency", (raw) => {
  const m = metaOrEmpty(raw);
  if (get(m, "decoder.causal") !== false) return skip("decoder.causal is not false");
  return hget(raw, "latency") !== null ? bad("decoder.causal is false but latency is set (see ambiguity A1)") : ok();
});
check("TR-DERIVED", "trust-ready", "SHOULD", "4.2 / 5.4.4", "meta has data.derived = true", (raw) => {
  const m = metaOrEmpty(raw);
  if (!has(m, "data.derived")) return bad("no data.derived");
  return m["data.derived"] === true ? ok() : bad(`data.derived is ${repr(m["data.derived"])}`);
});
const CALIB_HINT = /calibrat|temperature/i;
/** Python `v in (None, False, 1, 1.0)` (True == 1 and False == 0 in Python). */
const calibNeutral = (v: unknown): boolean => v === null || v === false || v === true || v === 0 || v === 1;
check("TR-CALIB", "trust-ready", "MUST", "4.1 / 4.2 / 3.5.3", "calibration.applied is consistent with the calibration keys", (raw) => {
  const m = metaOrEmpty(raw);
  const applied = has(m, "calibration.applied") ? m["calibration.applied"] : false;
  if (applied === true) {
    const meth = get(m, "decoder.calibration_method");
    if (typeof meth !== "string" || meth === "" || meth === "none") return bad('calibration.applied is true but decoder.calibration_method is absent or "none"');
    return ok();
  }
  const hints = Object.keys(m).filter((k) => CALIB_HINT.test(k) && !has(DEFINED_KEYS, k) && !calibNeutral(m[k]));
  return hints.length ? bad(`keys ${repr(hints)} suggest a calibration step, but calibration.applied is not true (default false)`) : ok();
});
check("TR-LANGUAGE", "trust-ready", "PROFILE", "4.2", "Text vocabularies (char, word, phoneme) state the language", (raw) => {
  if (!["char", "word", "phoneme"].includes(hget(raw, "vocab_type") as string)) return skip("not a text vocabulary");
  const m = metaOrEmpty(raw);
  return has(m, "language") ? ok(String(m.language)) : bad("no language");
});

// --- provenance profile (4.3) --------------------------------------------------------------------

check("PV-STREAM-ID", "provenance", "PROFILE", "4.3.1", "meta has an opaque stream.id", (raw) => {
  const v = get(metaOrEmpty(raw), "stream.id");
  return typeof v === "string" && v ? ok() : bad("no stream.id (a consumer must hash the content)");
});
check("PV-DECODER", "provenance", "SHOULD", "4.3.2", "meta has decoder.name and decoder.version", (raw) => {
  const m = metaOrEmpty(raw);
  const miss = ["decoder.name", "decoder.version"].filter((k) => !has(m, k));
  return miss.length ? bad(`missing ${repr(miss)}`) : ok();
});
check("PV-WEIGHTS", "provenance", "SHOULD", "4.2 / 4.3.2", "meta has decoder.weights_sha256", (raw) =>
  has(metaOrEmpty(raw), "decoder.weights_sha256") ? ok() : bad("no decoder.weights_sha256"));
check("PV-ADAPTER", "provenance", "SHOULD", "4.2 / 4.3.2", "adapter.name and adapter.version are both present or both absent", (raw) => {
  const m = metaOrEmpty(raw);
  const a = has(m, "adapter.name");
  const b = has(m, "adapter.version");
  if (a !== b) return bad("only one of adapter.name / adapter.version");
  return ok(a ? "adapter keys present" : "no adapter keys");
});
check("PV-CALIB-ID", "provenance", "SHOULD", "3.5.3 / 4.3.2", "A calibrated stream has decoder.calibration_id", (raw) => {
  const m = metaOrEmpty(raw);
  if (get(m, "calibration.applied") !== true) return skip("calibration.applied is not true");
  return has(m, "decoder.calibration_id") ? ok() : bad("no decoder.calibration_id");
});
check("PV-PSEUDONYM", "provenance", "MUST", "5.4.2 / 4.3.4", "subject.id and session.id look like pseudonymous codes", (raw) => {
  const m = metaOrEmpty(raw);
  const errs = ["subject.id", "session.id"].filter((k) => typeof get(m, k) === "string" && !pyMatch(PSEUDO_ID_RE, m[k] as string))
    .map((k) => `${k} = ${repr(m[k])}`);
  return errs.length ? bad(`ids that do not look like codes: ${repr(errs)}`) : ok();
}, { heuristic: true });

// --- runner ---------------------------------------------------------------------------------------

/** Run every check that applies to the format of `raw`. */
export function runChecks(raw: RawStream): CheckResult[] {
  const out: CheckResult[] = [];
  for (const c of REGISTRY) {
    if (!c.formats.includes(raw.format)) continue;
    let status: Status;
    let message: string;
    if (!raw.parsed && c.id !== "NTS-PARSE" && c.id !== "NTS-JSONL-HEADER") {
      [status, message] = ["skip", "the file did not parse"];
    } else {
      try {
        [status, message] = c.fn(raw);
      } catch (e) {
        [status, message] = ["fail", `check raised ${e instanceof Error ? `${e.name}: ${e.message}` : String(e)}`];
      }
    }
    out.push({ id: c.id, level: c.level, keyword: c.keyword, clause: c.clause, title: c.title, status, message, heuristic: c.heuristic });
  }
  return out;
}

/** The list of all checks (id, level, keyword, clause, title). */
export function checkTable(): { id: string; level: Level; keyword: string; clause: string; title: string; heuristic: boolean; formats: string[] }[] {
  return REGISTRY.map(({ fn: _fn, ...rest }) => ({ ...rest, formats: [...rest.formats] }));
}

/** Highest level a set of results reaches: "provenance", "trust-ready", "core" or null. */
export function levelReached(results: CheckResult[]): (typeof LEVELS)[number] | null {
  let best: (typeof LEVELS)[number] | null = null;
  for (const lv of LEVELS) {
    if (results.some((r) => r.status === "fail" && blocks(r.level, lv))) break;
    best = lv;
  }
  return best;
}

// --- reference consumer ---------------------------------------------------------------------------

export class StreamRejected extends Error {
  constructor(message: string, readonly clause = "", readonly checkId = "") {
    super(message);
    this.name = "StreamRejected";
  }
}

/** What the reference consumer returns for an accepted file. */
export interface ConsumedStream {
  header: Record<string, unknown>;
  /** [T, V] log-probabilities (row-major, float64), -inf allowed. */
  logProbs: NdArray;
  frameTimes: Float64Array;
  events: Record<string, unknown>[];
  ignoredEvents: number;
  unknownKeys: string[];
  vocabTypeDefaulted: boolean;
  summary: {
    n_frames: number; vocab_size: number; vocab_type: string; blank_id: number | null; neg_inf_cells: number;
    ignored_events: number; unknown_keys: string[]; vocab_type_defaulted: boolean; events: number;
  };
}

/**
 * The reference consumer: accept a stream when every core check passes,
 * else throw {@link StreamRejected} with the first failing clause.
 * `name` gives the format by its extension (`.npz`, `.jsonl`).
 */
export function loadStream(name: string, bytes: Uint8Array): ConsumedStream {
  return consumeRaw(readRaw(name, bytes));
}

export function consumeRaw(raw: RawStream): ConsumedStream {
  for (const r of runChecks(raw)) {
    if (r.status === "fail" && blocks(r.level, "core")) throw new StreamRejected(`[${r.id}, spec ${r.clause}] ${r.message}`, r.clause, r.id);
  }
  const h = raw.header;
  const vocab = h.vocab as string[];
  const lp = raw.logProbs ?? { shape: [0, vocab.length], data: new Float64Array(0) };
  // The Python NeuralTextStream stores log_probs as float32 and validates again.
  const [T, V] = lp.shape;
  const f32 = Float64Array.from(lp.data, (x) => Math.fround(x));
  if (f32.some((x) => Number.isNaN(x) || x === Infinity)) throw new StreamRejected("log_probs must not contain NaN or +inf", "5.2.2");
  if (T > 0) {
    const lse = rowLse(f32, T, V);
    const t = lse.findIndex((x) => Math.abs(x) > NORM_TOL);
    if (t >= 0) throw new StreamRejected(`log_probs rows must log-sum-exp to 0 (tol ${NORM_TOL}); frame ${t} gives ${lse[t]}`, "5.2.1");
  }
  let neg = 0;
  for (const x of f32) if (x === -Infinity) neg++;
  const events = raw.events.map((e) => {
    const { _line, ...rest } = e;
    void _line;
    return rest;
  });
  const vt = (has(h, "vocab_type") ? h.vocab_type : "char") as string;
  const blank = (has(h, "blank_id") ? h.blank_id : null) as number | null;
  return {
    header: h,
    logProbs: { shape: [T, V], data: f32 },
    frameTimes: raw.frameTimes ? raw.frameTimes.data : new Float64Array(0),
    events,
    ignoredEvents: raw.ignoredEvents,
    unknownKeys: raw.unknownKeys,
    vocabTypeDefaulted: raw.vocabTypeDefaulted,
    summary: {
      n_frames: T, vocab_size: vocab.length, vocab_type: vt, blank_id: blank, neg_inf_cells: neg,
      ignored_events: raw.ignoredEvents, unknown_keys: raw.unknownKeys, vocab_type_defaulted: raw.vocabTypeDefaulted,
      events: events.length,
    },
  };
}
