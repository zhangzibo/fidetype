/**
 * NeuralTextStream over LSL (FEP-0002), scenario form: a port of the parts
 * of `fidetype.adapters.lsl` that the `fep-0002` conformance vectors use.
 * There is no network and no liblsl: a scenario scripts the chunks.
 *
 * The Python reference consumer feeds the events into its trust layer.
 * This port replaces the trust layer with a structural model: the same
 * event checks (`StreamValidator` rules) and the same decision COUNTS
 * (one final decision per closed utterance with input; one provisional
 * decision per partial hypothesis on the hypothesis route). It does not
 * decode or apply a trust policy, so it gives no decision texts.
 */

import { SPEC_VERSION, VOCAB_TYPES } from "../constants.js";
import { get, has, isObj, markFloat, parseJson } from "../json.js";
import { StreamEventError, checkHeader, checkNbest, frameRow, parseEvent } from "../validate.js";
import { validateDeclaration } from "./fep0001.js";
import { DECLARATION_KEY } from "../constants.js";

// --- a minimal XML reader (the subset that liblsl's stream info XML uses) ----------------

export interface XmlEl {
  tag: string;
  text: string | null;
  children: XmlEl[];
}

const ENT: Record<string, string> = { lt: "<", gt: ">", amp: "&", quot: '"', apos: "'" };
function unescapeXml(s: string): string {
  return s.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (m, g: string) => {
    if (g[0] === "#") return String.fromCodePoint(g[1] === "x" ? parseInt(g.slice(2), 16) : parseInt(g.slice(1), 10));
    if (Object.prototype.hasOwnProperty.call(ENT, g)) return ENT[g];
    throw new SyntaxError(`undefined entity ${m}`);
  });
}

/** Parse an XML document into elements (text = the text before the first child, as ElementTree). */
export function parseXml(xml: string): XmlEl {
  const s = xml.replace(/\r\n?/g, "\n");
  let i = 0;
  const skipMisc = (): void => {
    for (;;) {
      while (i < s.length && /\s/.test(s[i])) i++;
      if (s.startsWith("<?", i)) {
        const e = s.indexOf("?>", i);
        if (e < 0) throw new SyntaxError("unclosed processing instruction");
        i = e + 2;
      } else if (s.startsWith("<!--", i)) {
        const e = s.indexOf("-->", i);
        if (e < 0) throw new SyntaxError("unclosed comment");
        i = e + 3;
      } else if (s.startsWith("<!DOCTYPE", i)) {
        const e = s.indexOf(">", i);
        i = e + 1;
      } else return;
    }
  };
  const element = (): XmlEl => {
    const m = /^<([A-Za-z_][\w.\-:]*)((?:\s+[\w.\-:]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>/.exec(s.slice(i));
    if (!m) throw new SyntaxError(`not well-formed XML at position ${i}`);
    i += m[0].length;
    const el: XmlEl = { tag: m[1], text: null, children: [] };
    if (m[3] === "/") return el;
    let text = "";
    let sawText = false;
    for (;;) {
      if (i >= s.length) throw new SyntaxError(`no closing tag for <${el.tag}>`);
      if (s.startsWith("</", i)) {
        const c = /^<\/([A-Za-z_][\w.\-:]*)\s*>/.exec(s.slice(i));
        if (!c || c[1] !== el.tag) throw new SyntaxError(`mismatched tag at position ${i}`);
        i += c[0].length;
        if (!el.children.length && sawText) el.text = text;
        return el;
      }
      if (s.startsWith("<!--", i)) {
        const e = s.indexOf("-->", i);
        if (e < 0) throw new SyntaxError("unclosed comment");
        i = e + 3;
        continue;
      }
      if (s.startsWith("<![CDATA[", i)) {
        const e = s.indexOf("]]>", i);
        if (e < 0) throw new SyntaxError("unclosed CDATA");
        if (!el.children.length) {
          text += s.slice(i + 9, e);
          sawText = true;
        }
        i = e + 3;
        continue;
      }
      if (s[i] === "<") {
        if (!el.children.length && sawText) el.text = text;
        el.children.push(element());
        continue;
      }
      const e = s.indexOf("<", i);
      const chunk = s.slice(i, e < 0 ? s.length : e);
      if (!el.children.length) {
        text += unescapeXml(chunk);
        sawText = true;
      }
      i += chunk.length;
    }
  };
  skipMisc();
  const root = element();
  skipMisc();
  if (i !== s.length) throw new SyntaxError("junk after document element");
  return root;
}

const find = (el: XmlEl | undefined, tag: string): XmlEl | undefined => el?.children.find((c) => c.tag === tag);

// --- stream info --------------------------------------------------------------------------

export const NTS_STREAM_TYPE = "NTS";
export const MARKERS_TYPE = "Markers";
export const BINDING_VERSION = "nts-lsl/0.1";
const KNOWN_BINDINGS = [BINDING_VERSION];
const NTS_FRAME_FORMATS = ["float32", "double64"];
const EVENT_CLOCKS = ["source", "lsl"];
const EVENT_TIME_KEYS = ["t", "t_start", "t_end", "t_signal_start", "t_signal_end", "t_decoded", "t_emitted"];
const SRATE_RTOL = 1e-6;
const NUMERIC_FORMATS = ["float32", "double64", "int8", "int16", "int32", "int64"];
const CLAMP_STEP_S = 1e-6;
const ADAPTER_NAME = "fidetype.adapters.lsl";
const ADAPTER_VERSION = "0.1";

export interface LSLStreamInfo {
  name: string;
  type: string;
  channel_count: number;
  nominal_srate: number;
  channel_format: string;
  source_id: string;
  uid: string;
  hostname: string;
  channel_labels: string[];
  /** Child values of desc/fidetype. */
  fidetype: Record<string, string>;
}

/** Python float(): accepts surrounding white space, inf, nan, underscores between digits. */
export function pyFloat(s: string): number {
  const t = s.trim().toLowerCase();
  if (/^[+-]?(inf|infinity)$/.test(t)) return t.startsWith("-") ? -Infinity : Infinity;
  if (/^[+-]?nan$/.test(t)) return NaN;
  const u = t.replace(/(\d)_(?=\d)/g, "$1");
  if (!/^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/.test(u)) throw new RangeError(`could not convert string to float: '${s}'`);
  return Number(u);
}

/** Python int() of a string. */
function pyInt(s: string): number {
  const t = s.trim().replace(/(\d)_(?=\d)/g, "$1");
  if (!/^[+-]?\d+$/.test(t)) throw new RangeError(`invalid literal for int(): '${s}'`);
  return Number(t);
}

export function infoFromXml(xml: string): LSLStreamInfo {
  const root = parseXml(xml);
  const txt = (tag: string, dflt = ""): string => {
    const el = find(root, tag);
    return el !== undefined && el.text !== null ? el.text.trim() : dflt;
  };
  const labels: string[] = [];
  const fid: Record<string, string> = {};
  const desc = find(root, "desc");
  if (desc) {
    const chs = find(desc, "channels");
    if (chs) for (const ch of chs.children.filter((c) => c.tag === "channel")) labels.push((find(ch, "label")?.text ?? "").trim());
    const f = find(desc, "fidetype");
    if (f) for (const c of f.children) fid[c.tag] = c.text ?? "";
  }
  let srate: number;
  try {
    const v = txt("nominal_srate", "0");
    srate = v ? pyFloat(v) : 0;
  } catch {
    srate = 0;
  }
  const cc = txt("channel_count", "1");
  return {
    name: txt("name"), type: txt("type"), channel_count: cc ? pyInt(cc) : 1, nominal_srate: srate,
    channel_format: txt("channel_format", "float32"), source_id: txt("source_id"), uid: txt("uid"), hostname: txt("hostname"),
    channel_labels: labels, fidetype: fid,
  };
}

const isString = (info: LSLStreamInfo): boolean => info.channel_format === "string";

/** desc/fidetype/nts_header as an object, null if absent. Throws if it is not a JSON object. */
export function ntsHeader(info: LSLStreamInfo): Record<string, unknown> | null {
  const raw = info.fidetype.nts_header;
  if (!raw) return null;
  let h: unknown;
  try {
    h = parseJson(raw, { allowConstants: true });
  } catch (e) {
    throw new RangeError(`desc/fidetype/nts_header of stream '${info.name}' is not JSON: ${(e as Error).message}`);
  }
  if (!isObj(h)) throw new RangeError(`desc/fidetype/nts_header of stream '${info.name}' is not a JSON object`);
  return h;
}

/** Throw if the desc/fidetype keys break FEP-0002 (binding version, event clock). */
export function checkBinding(info: LSLStreamInfo): void {
  const b = has(info.fidetype, "binding") ? info.fidetype.binding : null;
  if (b !== null && !KNOWN_BINDINGS.includes(b.trim())) {
    throw new RangeError(`stream '${info.name}': binding '${b}' is not supported (known: ${KNOWN_BINDINGS}; FEP-0002 section 9)`);
  }
  const ec = has(info.fidetype, "event_clock") ? info.fidetype.event_clock : null;
  if (ec !== null && !EVENT_CLOCKS.includes(ec.trim())) throw new RangeError(`stream '${info.name}': event_clock '${ec}' is not one of ${EVENT_CLOCKS}`);
}

/** Python math.isclose(a, b, rel_tol). */
const isClose = (a: number, b: number, rel: number): boolean => a === b || Math.abs(a - b) <= rel * Math.max(Math.abs(a), Math.abs(b));

/** Throw if an NTS-native frames stream breaks FEP-0002 section 3. */
export function checkNativeFrames(info: LSLStreamInfo, header: Record<string, unknown>): void {
  if (!NTS_FRAME_FORMATS.includes(info.channel_format)) {
    throw new RangeError(`stream '${info.name}': an NTS frames stream must be float32 or double64, not '${info.channel_format}' (FEP-0002 section 3)`);
  }
  const vocab = (Array.isArray(get(header, "vocab")) ? header.vocab : []) as string[];
  const labels = info.channel_labels;
  if (labels.some((l) => l) && (labels.length !== vocab.length || labels.some((lb, k) => k < vocab.length && lb.trim() && lb.trim() !== String(vocab[k]).trim()))) {
    throw new RangeError(`stream '${info.name}': channel labels differ from the vocab order (FEP-0002 section 3)`);
  }
  const fp = get(header, "frame_period");
  if (typeof fp === "number" && fp > 0 && info.nominal_srate > 0 && !isClose(1 / info.nominal_srate, fp, SRATE_RTOL)) {
    throw new RangeError(`stream '${info.name}': nominal_srate ${info.nominal_srate} is not 1 / frame_period (${fp}) (FEP-0002 section 3)`);
  }
}

export function decisionsInfoErrors(info: LSLStreamInfo): string[] {
  const errs: string[] = [];
  if (info.type !== MARKERS_TYPE) errs.push(`type '${info.type}' is not '${MARKERS_TYPE}'`);
  if (info.channel_count !== 1 || info.channel_format !== "string") errs.push("a decisions stream has 1 channel of format string");
  if (info.nominal_srate !== 0) errs.push("a decisions stream has an irregular rate (nominal_srate 0)");
  if (info.fidetype.role !== "trust_decisions") errs.push("desc/fidetype/role must be trust_decisions");
  if (info.fidetype.event_type !== "trust_decision") errs.push("desc/fidetype/event_type must be trust_decision");
  try {
    checkBinding(info);
  } catch (e) {
    errs.push((e as Error).message);
  }
  return errs;
}

// --- mapping (consumer settings) ------------------------------------------------------------

export interface LSLMapping {
  values: string;
  vocab: string[] | null;
  vocab_type: string | null;
  blank: number | string | null;
  source: string | null;
  clock: string;
  clock_refresh_s: number;
  time_correction_timeout_s: number;
  out_of_order: string;
  clamp_tolerance_s: number;
  gap_factor: number;
  on_gap: string;
  boundary_markers: string[];
  plain_markers: string;
  merge_window_s: number;
  max_chunk: number;
  reconnect_timeout_s: number;
  reconnect_interval_s: number;
}

const MAPPING_DEFAULTS: LSLMapping = {
  values: "auto", vocab: null, vocab_type: null, blank: null, source: null, clock: "receiver", clock_refresh_s: 5.0,
  time_correction_timeout_s: 2.0, out_of_order: "clamp", clamp_tolerance_s: 0.005, gap_factor: 2.5, on_gap: "mark",
  boundary_markers: ["segment_end"], plain_markers: "ignore", merge_window_s: 0.05, max_chunk: 1024, reconnect_timeout_s: 30.0,
  reconnect_interval_s: 0.5,
};

/** Build a mapping as `LSLMapping(merge_window_s=1e9, reconnect_timeout_s=1.0, **settings)`; throw on bad settings. */
export function makeMapping(settings: Record<string, unknown>, fixed: Partial<LSLMapping>): LSLMapping {
  const m: LSLMapping = { ...MAPPING_DEFAULTS, ...fixed };
  for (const [k, v] of Object.entries(settings)) {
    if (!Object.prototype.hasOwnProperty.call(MAPPING_DEFAULTS, k)) throw new TypeError(`LSLMapping got an unexpected keyword argument '${k}'`);
    if (Object.prototype.hasOwnProperty.call(fixed, k)) throw new TypeError(`LSLMapping got multiple values for keyword argument '${k}'`);
    (m as unknown as Record<string, unknown>)[k] = k === "boundary_markers" && Array.isArray(v) ? [...v] : v;
  }
  if (!["auto", "log_probs", "probs", "logits"].includes(m.values)) throw new RangeError(`unknown values kind '${m.values}'`);
  if (!["receiver", "sender"].includes(m.clock)) throw new RangeError(`unknown clock '${m.clock}'`);
  if (!["clamp", "drop", "error"].includes(m.out_of_order)) throw new RangeError(`unknown out_of_order '${m.out_of_order}'`);
  if (!["mark", "segment", "abort"].includes(m.on_gap)) throw new RangeError(`unknown on_gap '${m.on_gap}'`);
  if (!["ignore", "hypothesis"].includes(m.plain_markers)) throw new RangeError(`unknown plain_markers '${m.plain_markers}'`);
  if (m.vocab_type !== null && !(VOCAB_TYPES as readonly string[]).includes(m.vocab_type)) throw new RangeError("vocab_type must be one of the VOCAB_TYPES");
  if (m.gap_factor <= 1 || m.merge_window_s < 0 || m.clamp_tolerance_s < 0) throw new RangeError("gap_factor must be > 1; merge_window_s and clamp_tolerance_s >= 0");
  return m;
}

function resolveBlank(blank: number | string | null, vocab: string[]): number | null {
  if (blank === null) return null;
  if (typeof blank === "string" && !/^\d+$/.test(blank.replace(/^-+/, ""))) {
    const k = vocab.indexOf(blank);
    if (k < 0) throw new RangeError(`blank token '${blank}' is not in the vocab`);
    return k;
  }
  const b = typeof blank === "string" ? pyInt(blank) : Math.trunc(blank);
  if (!(b >= 0 && b < vocab.length)) throw new RangeError(`blank index ${b} is outside 0..${vocab.length - 1}`);
  return b;
}

const summaryOf = (info: LSLStreamInfo): Record<string, unknown> => ({
  name: info.name, type: info.type, source_id: info.source_id, uid: info.uid, channel_count: info.channel_count,
  nominal_srate: info.nominal_srate, channel_format: info.channel_format,
});

/** The NTS header event for a stream, and the values kind of its channels (port of build_header). */
export function buildHeader(info: LSLStreamInfo, mapping: LSLMapping, lslExtra: Record<string, unknown>): [Record<string, unknown>, string] {
  let values = mapping.values;
  checkBinding(info);
  const native = ntsHeader(info);
  let h: Record<string, unknown>;
  if (native !== null) {
    h = {};
    for (const [k, v] of Object.entries(native)) if (k !== "type") h[k] = v;
    if (values === "auto") values = has(info.fidetype, "values") ? info.fidetype.values : "log_probs";
  } else {
    let vocab: string[];
    if (isString(info)) vocab = [...(mapping.vocab ?? [])];
    else {
      vocab = mapping.vocab !== null ? [...mapping.vocab] : [...info.channel_labels];
      if (!vocab.length || vocab.some((v) => !v)) throw new RangeError(`stream '${info.name}' has no channel labels; pass the vocab`);
    }
    h = {
      spec_version: SPEC_VERSION, vocab, vocab_type: mapping.vocab_type || "other", blank_id: resolveBlank(mapping.blank, vocab),
      source: mapping.source || `lsl:${info.name}`, meta: { "adapter.name": ADAPTER_NAME, "adapter.version": ADAPTER_VERSION, "data.derived": true },
    };
    if (info.nominal_srate > 0) {
      h.frame_period = 1 / info.nominal_srate;
      if (Number.isInteger(h.frame_period)) markFloat(h, "frame_period");
    }
  }
  if (values === "auto") values = "log_probs";
  const hv = get(h, "vocab");
  const hvLen = Array.isArray(hv) || typeof hv === "string" ? (hv as unknown[] | string).length : NaN;
  if (!isString(info) && (has(h, "vocab") ? hvLen : 0) !== info.channel_count) {
    throw new RangeError(`stream '${info.name}' has ${info.channel_count} channels but the vocab has ${hvLen} tokens`);
  }
  if (!isString(info) && !NUMERIC_FORMATS.includes(info.channel_format)) throw new RangeError(`channel format '${info.channel_format}' cannot carry frames`);
  if (native !== null && !isString(info)) checkNativeFrames(info, h);
  if (!["log_probs", "probs", "logits"].includes(values)) throw new RangeError(`unknown values kind '${values}'`);
  if (mapping.source && !has(h, "source")) h.source = mapping.source;
  if (!has(h, "spec_version")) h.spec_version = SPEC_VERSION;
  h.clock_domain = "lsl";
  h.lsl = {
    stream: summaryOf(info), clock: mapping.clock, values,
    binding: (info.fidetype.binding || BINDING_VERSION).trim(),
    event_clock: (info.fidetype.event_clock || "source").trim(),
    adapter: { name: ADAPTER_NAME, version: ADAPTER_VERSION },
    ...lslExtra,
  };
  return [{ type: "header", ...h }, values];
}

function toLogProbs(rows: number[][], values: string): number[][] {
  if (values === "log_probs") return rows.map((r) => [...r]);
  if (values === "probs") {
    if (rows.some((r) => r.some((x) => x < 0))) throw new RangeError("probability channels must be >= 0");
    return rows.map((r) => r.map((x) => Math.log(x)));
  }
  if (values === "logits") {
    return rows.map((r) => {
      const m = Math.max(...r);
      const lse = m + Math.log(r.reduce((s, x) => s + Math.exp(x - m), 0));
      return r.map((x) => x - lse);
    });
  }
  throw new RangeError(`unknown values kind '${values}'`);
}

// --- scripted inlets ------------------------------------------------------------------------

class StreamLost extends Error {}

type Chunk = [unknown[], number[]] | "lost";

class ScriptedInlet {
  script: Chunk[];
  constructor(readonly info: LSLStreamInfo, script: Chunk[], readonly tc: number) {
    this.script = [...script];
  }
  pullChunk(): [unknown[], number[]] {
    if (!this.script.length) return [[], []];
    const it = this.script.shift() as Chunk;
    if (it === "lost") throw new StreamLost("scripted loss");
    return it;
  }
}

/** Python iteration of a JSON value: list items, string characters, object keys. */
export function pyIter(x: unknown): unknown[] {
  if (Array.isArray(x)) return x;
  if (typeof x === "string") return [...x];
  if (isObj(x)) return Object.keys(x);
  throw new TypeError(`'${x === null ? "NoneType" : typeof x}' object is not iterable`);
}

/** Python `float(x)` of a JSON value. */
function pyFloatOf(x: unknown): number {
  if (typeof x === "number") return x;
  if (typeof x === "boolean") return x ? 1 : 0;
  if (typeof x === "string") return pyFloat(x);
  throw new TypeError(`float() argument must be a string or a real number, not '${x === null ? "NoneType" : typeof x}'`);
}

/** A numeric sample cell: null = -inf, "NaN" / "Infinity" / "-Infinity" strings (as fep0002._num_in, then np.asarray). */
function numIn(x: unknown): number {
  if (x === null) return -Infinity;
  if (typeof x === "string") {
    const special: Record<string, number> = { NaN: NaN, Infinity: Infinity, "-Infinity": -Infinity };
    return Object.prototype.hasOwnProperty.call(special, x) ? special[x] : (x as unknown as number); // other strings: converted (or refused) in pull, as np.asarray
  }
  if (typeof x === "number") return x;
  if (typeof x === "boolean") return x ? 1 : 0;
  throw new TypeError("a sample cell must be a number, null or a string");
}

function makeInlet(spec: unknown): ScriptedInlet {
  if (!isObj(spec) || !has(spec, "info_xml")) throw new TypeError("an inlet needs info_xml");
  const info = infoFromXml(String(spec.info_xml));
  const script: Chunk[] = [];
  const chunks = has(spec, "chunks") ? spec.chunks : [];
  for (const ch of pyIter(chunks)) {
    if (ch === "lost") {
      script.push("lost");
      continue;
    }
    if (!isObj(ch)) throw new TypeError("a chunk must be an object or \"lost\"");
    if (!has(ch, "samples") || !has(ch, "timestamps")) throw new TypeError("a chunk needs samples and timestamps");
    let samples = pyIter(ch.samples);
    if (!isString(info)) samples = samples.map((row) => pyIter(row).map(numIn));
    const stamps = pyIter(ch.timestamps).map(pyFloatOf);
    script.push([samples, stamps]);
  }
  return new ScriptedInlet(info, script, pyFloatOf(has(spec, "time_correction") ? spec.time_correction : 0.0));
}

// --- the event source -----------------------------------------------------------------------

interface Stats {
  samples: number; frames: number; markers: number; ignored_markers: number; bad_markers: number; clamped: number;
  dropped_out_of_order: number; gaps: number; lost: number; reconnects: number; late_releases: number;
}

type Item = [number, number, Record<string, unknown>];

class Reader {
  inlet!: ScriptedInlet;
  info!: LSLStreamInfo;
  host = "";
  eventClock = "source";
  lastT = -Infinity;
  seenT = -Infinity;
  period: number | null = null;
  jsonFramesLastT = -Infinity;
  clampedPending = 0;
  droppedPending = 0;
  lostSince: number | null = null;

  constructor(readonly role: "frames" | "events", inlet: ScriptedInlet, readonly src: EventSource, readonly reopen: (() => ScriptedInlet) | null) {
    this.attach(inlet);
  }

  attach(inlet: ScriptedInlet): void {
    this.inlet = inlet;
    this.info = inlet.info;
    this.host = this.info.hostname || this.info.source_id || this.info.name;
    checkBinding(this.info);
    this.eventClock = (this.info.fidetype.event_clock || "source").trim();
    this.lastT = -Infinity;
    this.seenT = -Infinity;
    this.period = null;
    this.jsonFramesLastT = -Infinity;
    this.clampedPending = 0;
    this.droppedPending = 0;
  }

  setPeriod(header: Record<string, unknown>): void {
    let fp = this.role === "frames" ? get(header, "frame_period") : null;
    if (fp === null && this.info.nominal_srate > 0 && this.role === "frames") fp = 1 / this.info.nominal_srate;
    this.period = fp ? pyFloatOf(fp) : null;
  }

  order(t: number, last: number): number | null {
    const m = this.src.mapping;
    if (t > last) return t;
    const st = this.src.stats;
    if (m.out_of_order === "error") throw new RangeError(`LSL timestamp ${t} does not increase (last ${last}) on stream '${this.info.name}'`);
    if (m.out_of_order === "clamp" && last - t <= m.clamp_tolerance_s) {
      st.clamped++;
      this.clampedPending++;
      return last + CLAMP_STEP_S;
    }
    st.dropped_out_of_order++;
    this.droppedPending++;
    return null;
  }

  pull(): Item[] {
    const src = this.src;
    const [samples, stamps] = this.inlet.pullChunk();
    if (!stamps.length) return [];
    const off = src.clockSync.offset(this.host, this.inlet);
    src.clock();
    src.stats.samples += stamps.length;
    const items: Item[] = [];
    if (this.role === "events") {
      const n = Math.min(samples.length, stamps.length);
      for (let k = 0; k < n; k++) {
        const s = samples[k];
        const t = stamps[k] + off;
        if (Array.isArray(s) && !s.length) throw new RangeError("list index out of range");
        let ev = src.markerEvent(Array.isArray(s) ? s[0] : s, t, off, this.eventClock);
        if (ev === null) continue;
        if (ev.type === "frame") {
          const tt = this.order(t, this.jsonFramesLastT);
          if (tt === null) continue;
          this.jsonFramesLastT = tt;
          ev = { ...ev, t_source: get(ev, "t"), t: tt };
        }
        items.push([t, src.nextSeq(), ev]);
      }
      this.seenT = Math.max(this.seenT, stamps[stamps.length - 1] + off);
      return items;
    }
    // numeric: np.asarray(samples, float64); a 1-D array is reshaped to (len(stamps), -1)
    let arr: number[][];
    const conv = (v: unknown): number => (typeof v === "string" ? pyFloat(v) : (v as number));
    if (samples.every((r) => Array.isArray(r))) {
      arr = (samples as unknown[][]).map((r) => r.map(conv));
      const w = new Set(arr.map((r) => r.length));
      if (w.size > 1) throw new RangeError("setting an array element with a sequence (ragged chunk)");
    } else if (samples.every((r) => typeof r === "number")) {
      const flat = samples as number[];
      if (flat.length % stamps.length) throw new RangeError("cannot reshape the chunk");
      const w = flat.length / stamps.length;
      arr = [];
      for (let r = 0; r < stamps.length; r++) arr.push(flat.slice(r * w, (r + 1) * w));
    } else throw new RangeError("setting an array element with a sequence");
    let keepRows: number[] = [];
    let keepT: number[] = [];
    stamps.forEach((ts, i) => {
      const t = ts + off;
      const tt = this.order(t, this.lastT);
      if (tt === null) return;
      if (this.period !== null && Number.isFinite(this.lastT) && tt - this.lastT > src.mapping.gap_factor * this.period) {
        items.push(...this.gap(this.lastT, tt, keepRows, keepT, arr));
        keepRows = [];
        keepT = [];
      }
      keepRows.push(i);
      keepT.push(tt);
      this.lastT = tt;
    });
    items.push(...this.frames(arr, keepRows, keepT));
    this.seenT = Math.max(this.seenT, this.lastT);
    return items;
  }

  frames(arr: number[][], rows: number[], times: number[]): Item[] {
    if (!rows.length) return [];
    const src = this.src;
    const chunk = rows.map((r) => {
      if (r >= arr.length) throw new RangeError("index out of bounds (more timestamps than samples)");
      return arr[r];
    });
    const lp = toLogProbs(chunk, src.values);
    const items: Item[] = [];
    times.forEach((t, k) => {
      src.stats.frames++;
      const ev: Record<string, unknown> = { type: "frame", t, log_probs: lp[k] };
      if (this.clampedPending) {
        ev.lsl_clamped = this.clampedPending;
        this.clampedPending = 0;
      }
      if (this.droppedPending) {
        ev.lsl_dropped_before = this.droppedPending;
        this.droppedPending = 0;
      }
      items.push([t, src.nextSeq(), ev]);
    });
    return items;
  }

  gap(t0: number, t1: number, rows: number[], times: number[], arr: number[][]): Item[] {
    const src = this.src;
    src.stats.gaps++;
    const items = this.frames(arr, rows, times);
    const missing = this.period ? Math.round((t1 - t0) / this.period) - 1 : null;
    const info = { t_start: t0, t_end: t1, missing_frames: missing, stream: this.info.name };
    const tg = t1 - 1e-9;
    const mode = src.mapping.on_gap;
    if (mode === "mark") items.push([tg, src.nextSeq(), { type: "gap", ...info }]);
    else if (mode === "segment") items.push([tg, src.nextSeq(), { type: "segment_end", lsl_t: tg, reason: "gap", ...info }]);
    else items.push([tg, src.nextSeq(), { type: "lsl_status", status: "gap_abort", ...info }]);
    return items;
  }
}

class ClockSync {
  private byHost = new Map<string, { value: number; n: number; updatedAt: number }>();
  constructor(readonly mode: string, readonly refreshS: number, readonly clock: () => number) {}
  offset(host: string, inlet: ScriptedInlet, force = false): number {
    if (this.mode === "sender") return 0;
    let o = this.byHost.get(host);
    if (!o) {
      o = { value: 0, n: 0, updatedAt: -Infinity };
      this.byHost.set(host, o);
    }
    const now = this.clock();
    if (force || o.n === 0 || now - o.updatedAt >= this.refreshS) {
      const v = inlet.tc;
      if (Number.isFinite(v)) {
        o.value = v;
        o.n++;
        o.updatedAt = now;
      }
    }
    return o.value;
  }
}

class EventSource {
  stats: Stats = { samples: 0, frames: 0, markers: 0, ignored_markers: 0, bad_markers: 0, clamped: 0, dropped_out_of_order: 0, gaps: 0, lost: 0, reconnects: 0, late_releases: 0 };
  readers: Reader[];
  clockSync: ClockSync;
  values = "log_probs";
  private seqN = 0;
  private heap: [number, number, number, Record<string, unknown>][] = [];
  private lastReleased = -Infinity;
  private headerEv: Record<string, unknown> | null = null;
  private pendingHeader = true;
  private nMarker = 0;

  constructor(primary: ScriptedInlet, events: ScriptedInlet | null, readonly mapping: LSLMapping, reopenPrimary: (() => ScriptedInlet) | null,
    readonly clock: () => number) {
    this.clockSync = new ClockSync(mapping.clock, mapping.clock_refresh_s, clock);
    const role = isString(primary.info) ? "events" : "frames";
    this.readers = [new Reader(role, primary, this, reopenPrimary)];
    if (events !== null) {
      if (!isString(events.info)) throw new RangeError("the events stream must have the string channel format");
      this.readers.push(new Reader("events", events, this, null));
    }
  }

  nextSeq(): number {
    return this.seqN++;
  }

  get primary(): Reader {
    return this.readers[0];
  }

  header(): Record<string, unknown> {
    if (this.headerEv === null) {
      const r = this.primary;
      const off = this.clockSync.offset(r.host, r.inlet, true);
      const extra: Record<string, unknown> = { time_correction_s: this.mapping.clock === "receiver" ? off : null };
      if (this.readers.length > 1) {
        extra.events_stream = summaryOf(this.readers[1].info);
        extra.event_clock = this.readers[1].eventClock;
      }
      const [h, values] = buildHeader(r.info, this.mapping, extra);
      this.headerEv = h;
      this.values = values;
      for (const rd of this.readers) rd.setPeriod(h);
    }
    return this.headerEv;
  }

  markerEvent(sIn: unknown, t: number, offset: number, eventClock: string): Record<string, unknown> | null {
    this.stats.markers++;
    const m = this.mapping;
    const s = typeof sIn === "string" ? sIn : pyStr(sIn);
    const txt = s.trim();
    if (txt.startsWith("{")) {
      let ev: unknown = null;
      try {
        ev = parseJson(txt, { allowConstants: true });
      } catch {
        ev = null;
      }
      if (isObj(ev) && typeof ev.type === "string") {
        ev.lsl_t = t;
        if (eventClock === "lsl" && offset) {
          for (const k of EVENT_TIME_KEYS) {
            const v = get(ev, k);
            if (typeof v === "number") ev[k] = v + offset;
          }
        }
        if (ev.type === "header") {
          if (!has(ev, "spec_version")) ev.spec_version = SPEC_VERSION;
          ev.clock_domain = "lsl";
        }
        return ev;
      }
      this.stats.bad_markers++;
      return null;
    }
    if (m.boundary_markers.includes(txt)) return { type: "segment_end", lsl_t: t, marker: txt };
    if (m.plain_markers === "hypothesis" && txt) {
      this.nMarker++;
      return { type: "hypothesis", id: `lsl-${this.nMarker}`, is_final: true, score_semantics: "none", nbest: [{ text: txt, score: 0.0 }], lsl_t: t };
    }
    this.stats.ignored_markers++;
    return null;
  }

  poll(): Record<string, unknown>[] {
    const out: Record<string, unknown>[] = [];
    if (this.pendingHeader) {
      out.push({ ...this.header() });
      this.pendingHeader = false;
    }
    const now = this.clock();
    this.readers.forEach((r) => {
      if (r.lostSince !== null) {
        out.push(...this.tryReconnect(r, now));
        return;
      }
      let items: Item[];
      try {
        items = r.pull();
      } catch (e) {
        if (e instanceof StreamLost) {
          out.push(...this.lost(r, e.message, now));
          return;
        }
        throw e;
      }
      const arrival = this.clock();
      for (const [t, sq, ev] of items) this.heapPush([t, sq, arrival, ev]);
    });
    out.push(...this.release(this.clock()));
    return out;
  }

  drain(): Record<string, unknown>[] {
    return this.release(Infinity, true);
  }

  private heapPush(x: [number, number, number, Record<string, unknown>]): void {
    this.heap.push(x);
    this.heap.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  }

  private release(now: number, force = false): Record<string, unknown>[] {
    const out: Record<string, unknown>[] = [];
    while (this.heap.length) {
      const [t, , arrival, ev] = this.heap[0];
      const others = this.readers.filter((rd) => rd.lostSince === null).map((rd) => rd.seenT);
      const ok = force || this.readers.length === 1 || others.every((x) => x >= t) || now - arrival >= this.mapping.merge_window_s;
      if (!ok) break;
      this.heap.shift();
      if (t < this.lastReleased) this.stats.late_releases++;
      this.lastReleased = Math.max(this.lastReleased, t);
      out.push(ev);
    }
    return out;
  }

  private lost(r: Reader, why: string, now: number): Record<string, unknown>[] {
    this.stats.lost++;
    r.lostSince = now;
    const held = this.release(Infinity, true);
    return [...held, { type: "lsl_status", status: "lost", stream: r.info.name, detail: why }];
  }

  private tryReconnect(r: Reader, now: number): Record<string, unknown>[] {
    if (r.reopen === null || now - (r.lostSince as number) > this.mapping.reconnect_timeout_s) {
      throw new StreamLost(`stream '${r.info.name}' lost and not reconnected`);
    }
    let inlet: ScriptedInlet;
    try {
      inlet = r.reopen();
    } catch {
      return [];
    }
    r.attach(inlet);
    r.lostSince = null;
    this.stats.reconnects++;
    const out: Record<string, unknown>[] = [{ type: "lsl_status", status: "reconnected", stream: r.info.name }];
    if (r === this.primary) {
      this.headerEv = null;
      out.push({ ...this.header() });
    } else r.setPeriod(this.header());
    return out;
  }
}

/** Python `str(x)` for a non-string marker sample. */
function pyStr(x: unknown): string {
  if (x === null || x === undefined) return "None";
  if (typeof x === "boolean") return x ? "True" : "False";
  if (typeof x === "number") return String(x);
  return JSON.stringify(x);
}

// --- the structural trust model + runner ------------------------------------------------------

/** Counts what the reference StreamingTrustLayer does, without decoding. Throws StreamEventError as it does. */
class StructuralLayer {
  header: Record<string, unknown> | null = null;
  V = 0;
  lastT = -Infinity;
  ended = false;
  rows = 0;
  hyp = false;
  hasSession = false;
  decisions = 0;
  finals = 0;

  constructor(readonly route: "frames" | "hypothesis") {}

  pending(): boolean {
    return this.hasSession && (this.rows > 0 || this.hyp);
  }

  push(evIn: Record<string, unknown>): void {
    const ev = parseEvent(evIn);
    this.hasSession = true;
    const typ = ev.type as string;
    if (typ === "header") {
      this.end();
      this.V = checkHeader(ev);
      this.header = ev;
      this.lastT = -Infinity;
      this.ended = false;
      this.rows = 0;
      this.hyp = false;
    } else if (this.header === null) throw new StreamEventError(`'${typ}' event before the header (spec 6.2 rule 1)`);
    else if (this.ended) {
      // lines after the end marker are ignored
    } else if (typ === "frame") {
      const t = get(ev, "t");
      if (typeof t !== "number" || !Number.isFinite(t)) throw new StreamEventError("frame needs a finite numeric t");
      if (!(t > this.lastT)) throw new StreamEventError(`frame t ${t} does not increase (last ${this.lastT}; spec 6.2 rule 4)`);
      frameRow(ev, this.V);
      this.lastT = t;
      if (this.route === "frames") this.rows++;
    } else if (typ === "hypothesis") {
      if (typeof get(ev, "id") !== "string" || typeof get(ev, "is_final") !== "boolean") {
        throw new StreamEventError("hypothesis needs a string id and a boolean is_final");
      }
      checkNbest(ev);
      if (has(ev, DECLARATION_KEY)) {
        const errs = validateDeclaration(ev[DECLARATION_KEY]);
        if (errs.length) throw new StreamEventError(`${errs.join("; ")} (FEP-0001 section 4)`);
      }
      if (this.route === "hypothesis") {
        this.hyp = true;
        if (ev.is_final === true) this.end();
        else this.decisions++; // a provisional decision (StreamingConfig.provisional = True)
      }
    } else if (typ === "segment_end") this.end();
    else if (typ === "end") {
      this.end();
      this.ended = true;
    }
  }

  /** Close the utterance: one final decision if it had input. */
  end(): void {
    if (this.header === null) return;
    if ((this.route === "frames" && this.rows > 0) || (this.route === "hypothesis" && this.hyp)) {
      if (this.route === "frames") checkStreamFields(this.header);
      this.decisions++;
      this.finals++;
    }
    this.rows = 0;
    this.hyp = false;
  }

  abort(): void {
    this.rows = 0;
    this.hyp = false;
  }
}

/** The NeuralTextStream constructor checks on the header fields of a decoded utterance. */
function checkStreamFields(h: Record<string, unknown>): void {
  const src = has(h, "source") ? h.source : "unknown";
  if (typeof src !== "string" || !src) throw new RangeError("source must be a non-empty string");
  const fp = get(h, "frame_period");
  if (fp !== null && !(typeof fp === "number" && Number.isFinite(fp) && fp > 0)) throw new RangeError("frame_period must be a positive finite number");
  const lat = get(h, "latency");
  if (lat !== null && !(typeof lat === "number" && Number.isFinite(lat) && lat >= 0)) throw new RangeError("latency must be a finite number >= 0");
  const meta = get(h, "meta");
  if (meta !== null && meta !== false && meta !== 0 && meta !== "" && !isObj(meta) && !(Array.isArray(meta) && meta.length === 0)) {
    throw new TypeError("meta must be a dict");
  }
}

function deepCount(types: Map<string, number>, ev: Record<string, unknown>): void {
  const t = ev.type as string;
  if (t !== "lsl_status") types.set(t, (types.get(t) ?? 0) + 1);
}

/** Play an `inlet` scenario. Throws on rejection. Returns the FEP-0002 section 10 values. */
export function runInletScenario(sc: Record<string, unknown>): Record<string, unknown> {
  const inl = sc.inlets as Record<string, unknown>;
  if (!isObj(inl)) throw new TypeError("a scenario needs inlets");
  const primary = makeInlet(inl.primary);
  const events = pyTruthy(get(inl, "events")) ? makeInlet(inl.events) : null;
  const after = get(inl, "primary_after_reconnect");
  const pending: unknown[] = [after];
  const reopen = (): ScriptedInlet => {
    if (pending.length && pending[0] !== null && pending[0] !== undefined) return makeInlet(pending.shift());
    throw new Error("no stream");
  };
  const settings = (get(sc, "consumer_settings") ?? {}) as Record<string, unknown>;
  const mapping = makeMapping(isObj(settings) ? settings : {}, { merge_window_s: 1e9, reconnect_timeout_s: 1.0 });
  let ticks = 0;
  const clock = (): number => 1000.0 + ticks++ * 1e-3;
  const src = new EventSource(primary, events, mapping, pyTruthy(after) ? reopen : null, clock);
  const routeRaw = has(sc, "route") ? sc.route : "frames";
  if (!["auto", "frames", "hypothesis"].includes(routeRaw as string)) throw new RangeError(`unknown route ${JSON.stringify(routeRaw)}`);
  const route: "frames" | "hypothesis" = routeRaw === "frames" ? "frames" : "hypothesis"; // auto without decode_fn = hypothesis
  const layer = new StructuralLayer(route);
  const seen: Record<string, unknown>[] = [];
  let aborted = 0;
  let ended = false;
  clock(); // runner init: _last_event_at = source.clock()

  const handle = (evs: Record<string, unknown>[]): void => {
    clock();
    for (const ev of evs) {
      const typ = ev.type;
      if (typ === "lsl_status") {
        if (ev.status === "lost" || ev.status === "gap_abort") {
          if (layer.pending()) aborted++;
          layer.abort();
        }
        continue;
      }
      if (typ === "gap") continue;
      const before = layer.decisions;
      layer.push(ev);
      // _emit: one clock() per decision with a numeric trigger time (receiver clock)
      const trig = has(ev, "lsl_t") ? ev.lsl_t : typ === "frame" ? get(ev, "t") : null;
      if (mapping.clock === "receiver" && typeof trig === "number") for (let k = before; k < layer.decisions; k++) clock();
      if (typ === "end") ended = true;
    }
  };

  let idle = 0;
  for (let step = 0; step < 10000; step++) {
    const n0 = seen.length;
    const evs = src.poll();
    seen.push(...evs);
    handle(evs);
    clock();
    if (ended) break;
    const busy = src.readers.some((r) => r.lostSince !== null || r.inlet.script.length > 0);
    idle = busy || seen.length !== n0 ? 0 : idle + 1;
    if (idle >= 3) break;
  }
  const drained = src.drain();
  seen.push(...drained);
  handle(drained);
  if (!ended) layer.end();

  const frames = seen.filter((e) => e.type === "frame");
  const rows = frames.map((e) => (e.log_probs as unknown[]).map((v) => pyFloatOf(v)));
  if (new Set(rows.map((r) => r.length)).size > 1) throw new RangeError("frames have different lengths");
  const types = new Map<string, number>();
  for (const e of seen) deepCount(types, e);
  const head = seen.find((e) => e.type === "header") as Record<string, unknown>;
  const lsl = head.lsl as Record<string, unknown>;
  return {
    clock_domain: get(head, "clock_domain"),
    binding: lsl.binding,
    event_clock: lsl.event_clock,
    vocab_size: (head.vocab as unknown[]).length,
    frames: frames.length,
    first_frame_t: frames.length ? frames[0].t : null,
    rows_sha256: rowsSha(rows),
    neg_inf_cells: rows.reduce((s, r) => s + r.filter((v) => v === -Infinity).length, 0),
    event_types: Object.fromEntries([...types.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))),
    hypothesis_times: seen.filter((e) => e.type === "hypothesis").map((e) => [get(e, "t_start"), get(e, "t_end")]),
    marker_lsl_t: seen.filter((e) => has(e, "lsl_t")).map((e) => e.lsl_t),
    decisions: layer.decisions,
    final_decisions: layer.finals,
    aborted_utterances: aborted,
    gaps: src.stats.gaps, clamped: src.stats.clamped, dropped_out_of_order: src.stats.dropped_out_of_order,
    reconnects: src.stats.reconnects, bad_markers: src.stats.bad_markers, ignored_markers: src.stats.ignored_markers,
  };
}

import { sha256Float64Rows } from "../sha256.js";
import { pyTruthy } from "../checks.js";
const rowsSha = (rows: number[][]): string => sha256Float64Rows(rows);
