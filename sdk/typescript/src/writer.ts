/**
 * NeuralTextStream JSON Lines writer (spec 6.2), the TypeScript form of
 * the Python `fidetype.StreamWriter`. Each method checks its event and
 * emits one line to the sink. Browser safe: the sink is a function.
 *
 * ```ts
 * const lines: string[] = [];
 * const w = new NtsWriter((line) => lines.push(line), { source: "my-decoder", frame_period: 0.04 });
 * w.frame(0.0, { probs: row });
 * w.segmentEnd();
 * w.end();
 * ```
 */

import { NORM_TOL, SCORE_SEMANTICS, SPEC_VERSION, VOCAB, VOCAB_TYPES } from "./constants.js";
import { cpLen, dumpJson } from "./json.js";

export interface WriterOptions {
  source: string;
  vocab?: readonly string[];
  vocab_type?: string;
  blank_id?: number | null;
  frame_period?: number;
  latency?: number;
  meta?: Record<string, unknown>;
  /** Extra header keys (for example `clock_domain`, `decode_declaration`). */
  extraHeader?: Record<string, unknown>;
}

export interface NbestItem {
  text: string;
  score?: number;
  char_confidences?: number[];
  logp_acoustic?: number;
  logp_lm?: number;
  [key: string]: unknown;
}

const round = (x: number, d: number): number => {
  const f = 10 ** d;
  return Math.round(x * f) / f;
};

function num(x: unknown, name: string): number {
  if (typeof x !== "number" || !Number.isFinite(x)) throw new RangeError(`${name} must be a finite number`);
  return x;
}

export class NtsWriter {
  readonly vocab: string[];
  readonly V: number;
  nFrames = 0;
  private lastT = -Infinity;
  private ids = new Set<string>();
  private ended = false;

  constructor(private readonly sink: (line: string) => void, opts: WriterOptions) {
    const vocab = [...(opts.vocab ?? VOCAB)];
    if (!vocab.length || !vocab.every((v) => typeof v === "string") || new Set(vocab).size !== vocab.length) {
      throw new RangeError("vocab must be a non-empty list of unique strings");
    }
    const vt = opts.vocab_type ?? "char";
    if (!(VOCAB_TYPES as readonly string[]).includes(vt)) throw new RangeError(`vocab_type must be one of ${VOCAB_TYPES.join(", ")}`);
    const blank = opts.blank_id === undefined ? 0 : opts.blank_id;
    if (blank !== null && !(Number.isInteger(blank) && blank >= 0 && blank < vocab.length)) throw new RangeError("blank_id is out of range");
    if (!opts.source) throw new RangeError("source must not be empty");
    this.vocab = vocab;
    this.V = vocab.length;
    const head: Record<string, unknown> = { type: "header", spec_version: SPEC_VERSION, vocab, vocab_type: vt, blank_id: blank, source: opts.source };
    if (opts.frame_period !== undefined) {
      head.frame_period = num(opts.frame_period, "frame_period");
      if (!(head.frame_period as number > 0)) throw new RangeError("frame_period must be > 0");
    }
    if (opts.latency !== undefined) {
      head.latency = num(opts.latency, "latency");
      if ((head.latency as number) < 0) throw new RangeError("latency must be >= 0");
    }
    Object.assign(head, opts.extraHeader ?? {});
    head.meta = { ...(opts.meta ?? {}) };
    this.write(head);
  }

  private write(ev: Record<string, unknown>): void {
    if (this.ended) throw new Error("the stream has ended");
    this.sink(dumpJson(ev));
  }

  /** Write any other event (an object with a string `type`) as it is. */
  event(ev: Record<string, unknown>): void {
    if (typeof ev.type !== "string") throw new RangeError("an event needs a string type");
    this.write({ ...ev });
  }

  /**
   * Write one frame at time `t` (seconds). Give exactly one of `logProbs`
   * (natural log, -Infinity allowed), `probs` ([0, 1]) or `logits` (log-softmax
   * is applied). The row must sum to 1 within the spec tolerance; times must
   * increase strictly.
   */
  frame(t: number, values: { logProbs?: ArrayLike<number>; probs?: ArrayLike<number>; logits?: ArrayLike<number> }): void {
    const given = [values.logProbs, values.probs, values.logits].filter((x) => x !== undefined).length;
    if (given !== 1) throw new RangeError("give exactly one of logProbs, probs or logits");
    let row: number[];
    if (values.logits) {
      const x = Array.from(values.logits);
      const m = Math.max(...x);
      const lse = m + Math.log(x.reduce((s, v) => s + Math.exp(v - m), 0));
      row = x.map((v) => v - lse);
    } else if (values.probs) {
      const p = Array.from(values.probs);
      if (p.some((v) => !(v >= 0) || v > 1 + NORM_TOL)) throw new RangeError("probs must be in [0, 1]");
      row = p.map((v) => Math.log(v));
    } else row = Array.from(values.logProbs as ArrayLike<number>);
    if (row.length !== this.V) throw new RangeError(`a frame needs ${this.V} values, got ${row.length}`);
    if (row.some((v) => Number.isNaN(v) || v === Infinity)) throw new RangeError("log-probabilities must not be NaN or +inf");
    const fin = row.filter((v) => Number.isFinite(v));
    if (!fin.length) throw new RangeError("a frame needs at least one finite log-probability");
    const m = Math.max(...fin);
    const total = m + Math.log(fin.reduce((s, v) => s + Math.exp(v - m), 0));
    if (Math.abs(total) > NORM_TOL) throw new RangeError(`the frame does not sum to 1 (logsumexp = ${total}); use logits for raw scores`);
    num(t, "t");
    if (t <= this.lastT) throw new RangeError("frame times must increase strictly (spec 2)");
    this.lastT = t;
    this.write({ type: "frame", t: round(t, 9), log_probs: row.map((v) => (v === -Infinity ? null : round(v, 6))) });
    this.nFrames++;
  }

  /** Write many frames: `times` (T) and T rows. */
  frames(times: ArrayLike<number>, rows: ArrayLike<ArrayLike<number>>): void {
    if (times.length !== rows.length) throw new RangeError("give one time per row");
    for (let k = 0; k < times.length; k++) this.frame(times[k], { logProbs: rows[k] });
  }

  /** Write a text n-best list (spec 3.6). Items are best first. Returns the hypothesis id. */
  hypothesis(nbest: (NbestItem | [string, number] | string)[], opts: {
    isFinal: boolean; id?: string; revisionOf?: string; scoreSemantics?: string; tStart?: number; tEnd?: number;
  }): string {
    const sem = opts.scoreSemantics ?? "none";
    if (!(SCORE_SEMANTICS as readonly string[]).includes(sem)) throw new RangeError(`scoreSemantics must be one of ${SCORE_SEMANTICS.join(", ")}`);
    const items = nbest.map((it) => {
      if (typeof it === "string") return { text: it, score: 0.0 };
      if (Array.isArray(it)) return { text: it[0], score: num(it[1], "score") };
      if (typeof it.text !== "string") throw new RangeError("each n-best item needs a string text");
      const d: NbestItem = { ...it, score: num(it.score ?? 0, "score") };
      if (it.char_confidences !== undefined) {
        const cc = it.char_confidences.map(Number);
        if (cc.length !== cpLen(it.text) || cc.some((c) => !(c >= 0 && c <= 1))) throw new RangeError("char_confidences needs one value in [0, 1] per character");
        d.char_confidences = cc;
      }
      return d;
    });
    if (!items.length) throw new RangeError("nbest must not be empty");
    const id = opts.id ?? `h${this.ids.size + 1}`;
    if (this.ids.has(id)) throw new RangeError(`hypothesis id '${id}' is already used`);
    this.ids.add(id);
    const ev: Record<string, unknown> = { type: "hypothesis", id, is_final: Boolean(opts.isFinal), score_semantics: sem, nbest: items };
    if (opts.revisionOf !== undefined) ev.revision_of = opts.revisionOf;
    if (opts.tStart !== undefined) ev.t_start = num(opts.tStart, "tStart");
    if (opts.tEnd !== undefined) ev.t_end = num(opts.tEnd, "tEnd");
    this.write(ev);
    return id;
  }

  /** Write a signal-quality event (spec 3.9). `index` values are in [0, 1]. */
  signalQuality(t: number, value: number, unit = "index"): void {
    num(value, "value");
    if (unit === "index" && !(value >= 0 && value <= 1)) throw new RangeError("an index value must be in [0, 1]");
    this.write({ type: "signal_quality", t: num(t, "t"), value, unit });
  }

  /** Mark the end of an utterance (`segment_end`, FEP-0001 section 1). */
  segmentEnd(t?: number, unit?: "utterance" | "word" | "trial"): void {
    const ev: Record<string, unknown> = { type: "segment_end" };
    if (t !== undefined) ev.t = num(t, "t");
    if (unit !== undefined) ev.unit = unit;
    this.write(ev);
  }

  /** Write the `end` event. Later writes throw. */
  end(): void {
    if (!this.ended) {
      this.write({ type: "end" });
      this.ended = true;
    }
  }
}

/** Build a complete JSON Lines text (header, frames, events, end) in memory. */
export function toJsonl(opts: WriterOptions, build: (w: NtsWriter) => void, end = true): string {
  const lines: string[] = [];
  const w = new NtsWriter((l) => lines.push(l), opts);
  build(w);
  if (end) w.end();
  return lines.join("\n") + "\n";
}
