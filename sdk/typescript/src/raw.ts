/**
 * Raw readers: read a stream WITHOUT validation, so that the checks can
 * see every problem (port of `fidetype.conformance.io`).
 */

import { EVENT_TYPES, HEADER_KNOWN, JSONL_HEADER_REQUIRED, NPZ_KNOWN, NPZ_NO_BLANK, NPZ_REQUIRED } from "./constants.js";
import { decodeUtf8, has, isBlank, isIntAt, isObj, markFloat, parseJson, pyLines } from "./json.js";
import { NpyArray, NpyPickleError, readNpz } from "./npz.js";

export interface NdArray {
  shape: number[];
  data: Float64Array;
}

export interface Issue {
  checkId: string;
  clause: string;
  message: string;
}

export interface SparseFrameInfo {
  line: number;
  top_ids: unknown;
  top_log_probs: unknown;
  rest_log_prob: unknown;
  rest?: number;
  vals?: number[];
}

/** Marker: meta was present but could not be parsed. */
export const UNPARSEABLE_META: unique symbol = Symbol("unparseable meta");

export interface RawStream {
  format: "npz" | "jsonl";
  /** The header fields that were present (a missing field is absent). */
  header: Record<string, unknown>;
  logProbs: NdArray | null;
  frameTimes: NdArray | null;
  issues: Issue[];
  /** Non-frame JSON Lines events in file order, each with `_line`. */
  events: Record<string, unknown>[];
  sparseFrames: SparseFrameInfo[];
  npzKeys: string[];
  npzDtypes: Record<string, string>;
  unknownKeys: string[];
  ignoredEvents: number;
  hasEnd: boolean;
  linesAfterEnd: number;
  parsed: boolean;
  vocabTypeDefaulted: boolean;
  metaDefaulted: boolean;
}

function emptyRaw(format: "npz" | "jsonl"): RawStream {
  return {
    format, header: {}, logProbs: null, frameTimes: null, issues: [], events: [], sparseFrames: [], npzKeys: [],
    npzDtypes: {}, unknownKeys: [], ignoredEvents: 0, hasEnd: false, linesAfterEnd: 0, parsed: true,
    vocabTypeDefaulted: false, metaDefaulted: false,
  };
}

const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

// --- JSON Lines (spec 6.2) -----------------------------------------------------------

/** One JSON log-probability: a number, or null for -inf (6.2 rule 3). */
function lpValue(x: unknown): number {
  if (x === null) return -Infinity;
  if (typeof x !== "number") throw new TypeError(`${JSON.stringify(x)} is not a number or null`);
  return x;
}

/** Read a JSON Lines stream (spec 6.2) without validation. */
export function readJsonlRaw(bytes: Uint8Array): RawStream {
  const raw = emptyRaw("jsonl");
  let text: string;
  try {
    text = decodeUtf8(bytes);
  } catch (e) {
    raw.parsed = false;
    raw.issues.push({ checkId: "NTS-PARSE", clause: "6.2", message: `cannot read the file as UTF-8: ${errMsg(e)}` });
    return raw;
  }
  const objs: [number, unknown][] = [];
  pyLines(text).forEach((line, k) => {
    if (isBlank(line)) return;
    try {
      objs.push([k + 1, parseJson(line)]);
    } catch (e) {
      raw.parsed = false;
      raw.issues.push({ checkId: "NTS-PARSE", clause: "6.2", message: `line ${k + 1} is not a JSON value: ${errMsg(e)}` });
    }
  });
  if (!raw.parsed) return raw;
  if (!objs.length) {
    raw.parsed = false;
    raw.issues.push({ checkId: "NTS-JSONL-HEADER", clause: "6.2.1", message: "the file has no header line" });
    return raw;
  }
  const head = objs[0][1];
  if (!isObj(head) || head.type !== "header") {
    raw.parsed = false;
    raw.issues.push({ checkId: "NTS-JSONL-HEADER", clause: "6.2.1", message: 'line 1 must be an object with "type": "header"' });
    return raw;
  }
  const missing = JSONL_HEADER_REQUIRED.filter((k) => !has(head, k));
  if (missing.length) {
    raw.issues.push({ checkId: "NTS-JSONL-HEADER", clause: "6.2.1", message: `the header lacks required fields ${JSON.stringify(missing)}` });
  }
  // Keep the parsed object (its float-literal marks) and drop "type" from a view.
  const header: Record<string, unknown> = head;
  raw.header = header;
  raw.unknownKeys = Object.keys(head).filter((k) => !(HEADER_KNOWN as readonly string[]).includes(k));
  if (!has(header, "meta")) {
    raw.metaDefaulted = true;
  }
  const vocab = header.vocab;
  const V = Array.isArray(vocab) ? vocab.length : null;
  const rows: Float64Array[] = [];
  const times: number[] = [];
  let stackable = true;
  for (const [n, obj] of objs.slice(1)) {
    if (raw.hasEnd) {
      raw.linesAfterEnd++;
      continue;
    }
    if (!isObj(obj) || typeof obj.type !== "string") {
      raw.issues.push({ checkId: "NTS-JSONL-FRAME", clause: "6.2", message: `line ${n} is not an event object with a string type` });
      stackable = false;
      continue;
    }
    const typ = obj.type;
    if (typ === "end") {
      raw.hasEnd = true;
      continue;
    }
    if (typ === "header") {
      raw.issues.push({ checkId: "NTS-JSONL-HEADER", clause: "6.2.1", message: `line ${n}: a second header` });
      continue;
    }
    if (!(EVENT_TYPES as readonly string[]).includes(typ)) {
      raw.ignoredEvents++; // 6.2 rule 5
      continue;
    }
    if (typ !== "frame") {
      obj._line = n;
      raw.events.push(obj);
      continue;
    }
    const t = has(obj, "t") ? obj.t : undefined;
    if (typeof t !== "number") {
      raw.issues.push({ checkId: "NTS-JSONL-FRAME", clause: "6.2.2", message: `line ${n}: frame without a numeric t` });
      stackable = false;
      continue;
    }
    let row: Float64Array | null;
    try {
      if (has(obj, "log_probs")) {
        const lp = obj.log_probs;
        if (!Array.isArray(lp)) throw new TypeError("log_probs is not a list");
        row = Float64Array.from(lp.map(lpValue));
      } else if (has(obj, "top_ids") || has(obj, "top_log_probs")) {
        row = sparseRow(obj, V, n, raw);
      } else {
        throw new TypeError("frame has neither log_probs nor top_ids/top_log_probs");
      }
    } catch (e) {
      raw.issues.push({ checkId: "NTS-JSONL-FRAME", clause: "6.2.2", message: `line ${n}: ${errMsg(e)}` });
      stackable = false;
      continue;
    }
    if (row === null) {
      stackable = false;
      continue;
    }
    rows.push(row);
    times.push(t);
  }
  if (stackable) {
    if (!rows.length) {
      raw.logProbs = { shape: [0, V ?? 0], data: new Float64Array(0) };
    } else if (new Set(rows.map((r) => r.length)).size === 1) {
      const W = rows[0].length;
      const data = new Float64Array(rows.length * W);
      rows.forEach((r, k) => data.set(r, k * W));
      raw.logProbs = { shape: [rows.length, W], data };
    } else {
      raw.issues.push({ checkId: "NTS-V-MATCH", clause: "5.1.2", message: "frames have different numbers of log-probabilities" });
    }
    raw.frameTimes = { shape: [times.length], data: Float64Array.from(times) };
  }
  return raw;
}

function sparseRow(obj: Record<string, unknown>, V: number | null, n: number, raw: RawStream): Float64Array | null {
  const ids = has(obj, "top_ids") ? obj.top_ids : null;
  const vals = has(obj, "top_log_probs") ? obj.top_log_probs : null;
  const rest = has(obj, "rest_log_prob") ? obj.rest_log_prob : null;
  const info: SparseFrameInfo = { line: n, top_ids: ids, top_log_probs: vals, rest_log_prob: rest };
  raw.sparseFrames.push(info);
  if (!Array.isArray(ids) || !Array.isArray(vals) || ids.length !== vals.length) {
    throw new RangeError("sparse frame needs top_ids and top_log_probs lists of the same length");
  }
  if (V === null) return null;
  const okIds = ids.every((x, k) => isIntAt(ids, k) && (x as number) >= 0 && (x as number) < V);
  if (!okIds || new Set(ids).size !== ids.length) throw new RangeError("top_ids must be unique integers in 0..V-1");
  const lv = vals.map(lpValue);
  const r = lpValue(rest);
  const row = new Float64Array(V).fill(-Infinity);
  const k = ids.length;
  if (V > k && r > -Infinity) row.fill(r - Math.log(V - k)); // 3.3: spread the rest mass uniformly
  ids.forEach((id, j) => {
    row[id as number] = lv[j];
  });
  info.rest = r;
  info.vals = lv;
  return row;
}

// --- NPZ (spec 6.1) --------------------------------------------------------------

function scalar(a: NpyArray): unknown {
  if (a.shape.length !== 0) return nested(a);
  const v = a.data[0];
  return a.kind === "b" ? Boolean(v) : v;
}

/** NumPy `tolist()`. */
function nested(a: NpyArray): unknown {
  const conv = (v: number | string | boolean): unknown => (a.kind === "b" ? Boolean(v) : v);
  if (a.shape.length === 0) return conv(a.data[0]);
  const build = (dim: number, off: number): [unknown[], number] => {
    const out: unknown[] = [];
    const size = a.shape[dim];
    for (let k = 0; k < size; k++) {
      if (dim === a.shape.length - 1) out.push(conv(a.data[off++]));
      else {
        const [sub, o] = build(dim + 1, off);
        out.push(sub);
        off = o;
      }
    }
    return [out, off];
  };
  return build(0, 0)[0];
}

/** Set `h[k] = v`, keeping Python's float/int type of NumPy scalars. */
function setTyped(h: Record<string, unknown>, k: string, v: unknown, a: NpyArray): void {
  h[k] = v;
  if (a.kind === "f" && a.shape.length === 0 && typeof v === "number" && Number.isInteger(v)) markFloat(h, k);
}

const isNumeric = (a: NpyArray): boolean => a.kind === "f" || a.kind === "i" || a.kind === "u";

/** Read an NPZ stream (spec 6.1) without validation. */
export function readNpzRaw(bytes: Uint8Array): RawStream {
  const raw = emptyRaw("npz");
  let z;
  try {
    z = readNpz(bytes);
  } catch (e) {
    raw.parsed = false;
    raw.issues.push({ checkId: "NTS-PARSE", clause: "6.1", message: `cannot load the NPZ with allow_pickle=False: ${errMsg(e)}` });
    return raw;
  }
  raw.npzKeys = [...z.files];
  const arrays: Record<string, NpyArray> = Object.create(null);
  for (const k of z.files) {
    try {
      arrays[k] = z.get(k);
    } catch (e) {
      if (e instanceof NpyPickleError) {
        raw.issues.push({ checkId: "NTS-PARSE", clause: "6.1", message: `key '${k}' needs pickle to load: ${errMsg(e)}` });
        raw.parsed = false;
      } else {
        // A corrupt member: NumPy raises outside its pickle path; the file does not load.
        raw.issues.push({ checkId: "NTS-PARSE", clause: "6.1", message: `key '${k}' cannot be loaded: ${errMsg(e)}` });
        raw.parsed = false;
      }
    }
  }
  for (const [k, a] of Object.entries(arrays)) raw.npzDtypes[k] = a.dtype;
  raw.unknownKeys = z.files.filter((k) => !(NPZ_KNOWN as readonly string[]).includes(k));
  const missing = NPZ_REQUIRED.filter((k) => !(k in arrays));
  if (missing.length) {
    raw.issues.push({ checkId: "NTS-NPZ-KEYS", clause: "6.1", message: `required NPZ keys are missing: ${JSON.stringify(missing)}` });
  }
  const h = raw.header;
  if (arrays.version) setTyped(h, "spec_version", scalar(arrays.version), arrays.version);
  if (arrays.vocab) {
    const v = arrays.vocab;
    h.vocab = v.shape.length === 1 ? nested(v) : scalar(v);
  }
  // 6.1: a reader MUST use "char" if vocab_type is absent.
  if (arrays.vocab_type) setTyped(h, "vocab_type", scalar(arrays.vocab_type), arrays.vocab_type);
  else {
    h.vocab_type = "char";
    raw.vocabTypeDefaulted = true;
  }
  if (arrays.blank_id) {
    const b = arrays.blank_id;
    if (b.shape.length === 0 && (b.kind === "i" || b.kind === "u")) {
      h.blank_id = b.data[0] === NPZ_NO_BLANK ? null : b.data[0];
    } else setTyped(h, "blank_id", scalar(b), b);
  }
  if (arrays.source) setTyped(h, "source", scalar(arrays.source), arrays.source);
  if (arrays.meta_json) {
    const txt = scalar(arrays.meta_json);
    try {
      h.meta = parseJson(pyStr(txt));
    } catch (e) {
      raw.issues.push({ checkId: "NTS-META-JSON", clause: "4.1", message: `meta_json is not valid JSON: ${errMsg(e)}` });
      h.meta = UNPARSEABLE_META;
    }
  }
  for (const k of ["frame_period", "latency"]) {
    if (arrays[k]) setTyped(h, k, scalar(arrays[k]), arrays[k]);
  }
  if (arrays.log_probs) {
    const lp = arrays.log_probs;
    if (isNumeric(lp)) raw.logProbs = { shape: lp.shape, data: Float64Array.from(lp.data as number[]) };
    else raw.issues.push({ checkId: "NTS-LP-2D", clause: "3.1", message: `log_probs has a non-numeric dtype ${lp.dtype}` });
  }
  if (arrays.frame_times) {
    const ft = arrays.frame_times;
    if (isNumeric(ft)) raw.frameTimes = { shape: ft.shape, data: Float64Array.from(ft.data as number[]) };
    else raw.issues.push({ checkId: "NTS-FT-SHAPE", clause: "3.1", message: `frame_times has a non-numeric dtype ${ft.dtype}` });
  }
  return raw;
}

/** Python `str(x)` for the values that `meta_json` can hold. */
function pyStr(x: unknown): string {
  if (typeof x === "string") return x;
  if (typeof x === "boolean") return x ? "True" : "False";
  if (typeof x === "number") return Number.isInteger(x) ? String(x) : String(x);
  return JSON.stringify(x);
}

/** Read a stream file by its name: `.npz`, or `.jsonl` / `.ndjson` / `.json`. */
export function readRaw(name: string, bytes: Uint8Array): RawStream {
  const suf = name.toLowerCase().slice(name.lastIndexOf("."));
  if (suf === ".npz") return readNpzRaw(bytes);
  if (suf === ".jsonl" || suf === ".ndjson" || suf === ".json") return readJsonlRaw(bytes);
  throw new RangeError(`unknown stream file type '${suf}' (use .npz or .jsonl)`);
}
