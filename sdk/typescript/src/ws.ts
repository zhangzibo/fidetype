/**
 * NeuralTextStream over WebSocket (FEP-0004, binding `nts-ws/0.1`,
 * subprotocol `nts-ws.0.1`): a port of the sans-IO parts of
 * `fidetype.adapters.ws`, plus a browser client for the decisions channel.
 *
 * - {@link IngestCore}: the server side of `/nts` without I/O (handshake,
 *   header, `ws_seq` order, batches, resume, take-over, acks, refusals).
 *   The `fep-0004` conformance profile uses it.
 * - {@link SubscriberCore}: the checks of a `/decisions` subscriber
 *   (welcome, `ws_seq` gaps, duplicates, FEP-0001 rules).
 * - {@link DecisionSubscriber}: a reconnecting `/decisions` client for the
 *   browser (or Node >= 22, or any WebSocket constructor you pass).
 *
 * Browser safe: no Node API.
 */

import { cpLen, has, isFloatLiteral, isIntAt, isObj, markFloat, parseJson } from "./json.js";
import { pyEqual } from "./conformance.js";
import { tdFinalErrors, tdFormatErrors, actedTexts } from "./profiles/fep0001.js";
import { DecisionTracker } from "./trust.js";
import type { HandledDecision } from "./trust.js";

export const WS_BINDING_VERSION = "nts-ws/0.1";
export const WS_SUBPROTOCOL = "nts-ws.0.1";
export const WS_KNOWN_BINDINGS = [WS_BINDING_VERSION];
export const WS_PATH_INGEST = "/nts";
export const WS_PATH_DECISIONS = "/decisions";
export const WS_PATH_EVENTS = "/events";
export const WS_REFUSAL_CODES = [1002, 1003, 1007, 1008, 1009, 4000];
const MAX_MESSAGE_BYTES = 1 << 20;
const MAX_STREAM_ID = 128;
const SPEC = "0.1";

type Obj = Record<string, unknown>;

/** A copy of `o` without `drop` keys that keeps the float-literal marks of the JSON parser. */
function copyWithout(o: Obj, drop: string[]): Obj {
  const out: Obj = {};
  for (const k of Object.keys(o)) {
    if (drop.includes(k)) continue;
    out[k] = o[k];
    if (isFloatLiteral(o, k)) markFloat(out, k);
  }
  return out;
}

const finNum = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);

/** Python `json.loads(text, parse_constant=reject)` + "a JSON object with a string type". */
export function parseWsMessage(text: string): Obj {
  const obj = parseJson(text);
  if (!isObj(obj) || typeof obj.type !== "string") throw new RangeError("a message must be a JSON object with a string type");
  return obj;
}

// --- input side ------------------------------------------------------------------------------

export interface IngestSettings {
  reorder_window: number;
  reorder_timeout_s: number;
  resume_timeout_s: number;
  max_batch: number;
  ack_every: number;
  window: number;
  ack_interval_s: number;
}

export const DEFAULT_INGEST_SETTINGS: IngestSettings = {
  reorder_window: 16, reorder_timeout_s: 0.25, resume_timeout_s: 10.0, max_batch: 1024, ack_every: 64, window: 4096,
  ack_interval_s: 0.1,
};

/** Settings from a JSON object (unknown keys and bad values throw, as the Python dataclass does). */
export function ingestSettings(o: Obj): IngestSettings {
  const s: IngestSettings = { ...DEFAULT_INGEST_SETTINGS };
  for (const k of Object.keys(o)) {
    if (!has(DEFAULT_INGEST_SETTINGS, k)) throw new TypeError(`unknown setting ${k}`);
    (s as unknown as Obj)[k] = o[k];
  }
  const so = s as unknown as Obj;
  const src = (k: string): Obj => (has(o, k) ? o : so);
  if (!(isIntAt(src("reorder_window"), "reorder_window") && s.reorder_window >= 0)) throw new RangeError("reorder_window must be an integer >= 0");
  for (const k of ["reorder_timeout_s", "resume_timeout_s", "ack_interval_s"]) {
    const v = so[k];
    if (!(finNum(v) && v >= 0)) throw new RangeError(`${k} must be a number >= 0`);
  }
  for (const k of ["max_batch", "ack_every", "window"]) {
    if (!(isIntAt(src(k), k) && (so[k] as number) >= 1)) throw new RangeError(`${k} must be an integer >= 1`);
  }
  return s;
}

/** A message to the core: a text message, a binary message, or an already parsed JSON value. */
export type WsData = { text: string } | { binary: true } | { value: unknown };

export interface Effects {
  sends: [number, Obj][];
  items: [string, Obj][];
  closes: [number, number, string][];
}

const noEffects = (): Effects => ({ sends: [], items: [], closes: [] });
function extend(a: Effects, b: Effects): Effects {
  a.sends.push(...b.sends);
  a.items.push(...b.items);
  a.closes.push(...b.closes);
  return a;
}

export interface IngestStats {
  streams: number; messages: number; events: number; duplicates: number; reordered: number; gaps: number;
  missing_events: number; resumes: number; takeovers: number; lost_streams: number; ignored_controls: number; refused: number;
}

interface Conn { cid: number; authed: boolean; streamId: string | null; open: boolean }
interface Stream {
  sid: string; header: Obj; conn: number | null; expected: number; held: Map<number, [Obj, number]>;
  sinceAck: number; lastAckAt: number; ended: boolean; disconnectedAt: number | null;
}

/** The server side of `/nts` without I/O (port of `fidetype.adapters.ws.IngestCore`). */
export class IngestCore {
  readonly conns = new Map<number, Conn>();
  readonly streams = new Map<string, Stream>();
  readonly stats: IngestStats = {
    streams: 0, messages: 0, events: 0, duplicates: 0, reordered: 0, gaps: 0, missing_events: 0, resumes: 0,
    takeovers: 0, lost_streams: 0, ignored_controls: 0, refused: 0,
  };
  private anon = 1;

  constructor(readonly s: IngestSettings = DEFAULT_INGEST_SETTINGS, readonly auth: ((token: string | null) => boolean) | null = null) {}

  open(cid: number, subprotocols: string[] = [WS_SUBPROTOCOL], authorization: string | null = null): Effects {
    const eff = noEffects();
    if (!subprotocols.includes(WS_SUBPROTOCOL)) {
      this.conns.set(cid, { cid, authed: false, streamId: null, open: false });
      this.stats.refused++;
      eff.closes.push([cid, 1002, `subprotocol ${WS_SUBPROTOCOL} not offered`]);
      return eff;
    }
    const tok = bearerToken(authorization);
    const authed = this.auth === null || (tok !== null && this.auth(tok));
    this.conns.set(cid, { cid, authed, streamId: null, open: true });
    return eff;
  }

  private refuse(conn: Conn, close: number, code: string, detail: string, now: number): Effects {
    const eff = noEffects();
    eff.sends.push([conn.cid, { type: "ws_error", code, detail }]);
    eff.closes.push([conn.cid, close, code]);
    this.stats.refused++;
    return extend(eff, this.disconnect(conn.cid, now));
  }

  message(cid: number, data: WsData, now = 0): Effects {
    const conn = this.conns.get(cid);
    if (conn === undefined || !conn.open) return noEffects();
    this.stats.messages++;
    let msg: unknown;
    if ("binary" in data) return this.refuse(conn, 1003, "binary", "binary messages are not allowed (section 3 rule 1)", now);
    let text: string | null = "text" in data ? data.text : null;
    if (text === null && typeof (data as { value: unknown }).value === "string") text = (data as { value: string }).value;
    if (text !== null) {
      if (new TextEncoder().encode(text).length > MAX_MESSAGE_BYTES) return this.refuse(conn, 1009, "too_big", "message larger than 1 MiB", now);
      try {
        msg = parseWsMessage(text);
      } catch (e) {
        return this.refuse(conn, 1007, "bad_message", String((e as Error).message).slice(0, 200), now);
      }
    } else {
      msg = (data as { value: unknown }).value;
      if (!isObj(msg) || typeof msg.type !== "string") {
        return this.refuse(conn, 1007, "bad_message", "a message must be a JSON object with a string type", now);
      }
    }
    const m = msg as Obj;
    const typ = m.type as string;
    if (!conn.authed) {
      if (typ === "ws_auth" && this.auth !== null && this.auth(typeof m.token === "string" ? m.token : null)) {
        conn.authed = true;
        return noEffects();
      }
      return this.refuse(conn, 1008, "auth", "authentication failed or missing (section 8)", now);
    }
    if (typ === "ws_auth") {
      if (conn.streamId === null) return noEffects();
      this.stats.ignored_controls++;
      return noEffects();
    }
    if (conn.streamId === null) {
      if (typ !== "header") return this.refuse(conn, 1007, "bad_header", "the first message must be the NTS header (section 5 rule 1)", now);
      return this.openStream(conn, m, now);
    }
    const st = this.streams.get(conn.streamId);
    if (st === undefined || st.conn !== cid) return noEffects();
    if (typ === "ws_batch") return this.batch(conn, st, m, now);
    if (typ.startsWith("ws_")) {
      this.stats.ignored_controls++;
      return noEffects();
    }
    const err = seqError(m);
    if (err) return this.refuse(conn, 1007, "bad_seq", err, now);
    const eff = noEffects();
    this.sequence(st, m, now, eff);
    return eff;
  }

  private batch(conn: Conn, st: Stream, msg: Obj, now: number): Effects {
    const evs = has(msg, "events") ? msg.events : null;
    if (!Array.isArray(evs) || evs.length === 0) return this.refuse(conn, 1007, "bad_batch", "ws_batch needs a non-empty events list", now);
    if (evs.length > this.s.max_batch) return this.refuse(conn, 1009, "too_big", `ws_batch of ${evs.length} events > ${this.s.max_batch}`, now);
    for (let k = 0; k < evs.length; k++) {
      const err = seqError(evs[k]);
      if (err) return this.refuse(conn, 1007, "bad_seq", err, now);
      if (k && (evs[k] as Obj).ws_seq !== ((evs[k - 1] as Obj).ws_seq as number) + 1) {
        return this.refuse(conn, 1007, "bad_batch", "the events of a batch must have consecutive ws_seq (section 6 rule 4)", now);
      }
    }
    const eff = noEffects();
    for (const ev of evs) this.sequence(st, ev as Obj, now, eff);
    return eff;
  }

  private openStream(conn: Conn, hdr: Obj, now: number): Effects {
    const ws = has(hdr, "ws") ? hdr.ws : {};
    if (!isObj(ws)) return this.refuse(conn, 1007, "bad_header", "header ws must be an object", now);
    const binding = has(ws, "binding") ? ws.binding : WS_BINDING_VERSION;
    if (typeof binding !== "string" || !WS_KNOWN_BINDINGS.includes(binding)) {
      return this.refuse(conn, 4000, "binding", `unknown binding ${JSON.stringify(binding)} (section 10)`, now);
    }
    let sid: unknown = has(ws, "stream_id") ? ws.stream_id : null;
    if (sid === null) sid = `anon-${this.anon++}`;
    else if (!(typeof sid === "string" && cpLen(sid) >= 1 && cpLen(sid) <= MAX_STREAM_ID)) {
      return this.refuse(conn, 1007, "bad_header", "ws.stream_id must be a string of 1-128 characters", now);
    }
    const resume = has(ws, "resume") ? ws.resume : false;
    if (typeof resume !== "boolean") return this.refuse(conn, 1007, "bad_header", "ws.resume must be a boolean", now);
    if ((has(hdr, "spec_version") ? hdr.spec_version : null) !== SPEC) {
      return this.refuse(conn, 1007, "bad_header", "spec_version is not '0.1'", now);
    }
    if (has(hdr, "ws_seq")) return this.refuse(conn, 1007, "bad_header", "the header has no ws_seq (section 6 rule 1)", now);
    const id = sid as string;
    const core = copyWithout(hdr, ["ws"]);
    const eff = noEffects();
    const old = this.streams.get(id);
    if (old !== undefined && resume) {
      if (!pyEqual(old.header, core)) return this.refuse(conn, 1007, "bad_header", "the resume header differs from the first header", now);
      if (old.conn !== null && old.conn !== conn.cid) extend(eff, this.takeOver(old.conn));
      old.conn = conn.cid;
      old.disconnectedAt = null;
      old.lastAckAt = now;
      conn.streamId = id;
      this.stats.resumes++;
      eff.items.push([id, { type: "ws_status", status: "resumed", stream: id, seq: old.expected - 1 }]);
      eff.sends.push([conn.cid, this.welcome(old, true)]);
      return eff;
    }
    if (old !== undefined) {
      if (old.conn !== null && old.conn !== conn.cid) extend(eff, this.takeOver(old.conn));
      if (!old.ended) eff.items.push([id, { type: "ws_status", status: "replaced", stream: id }]);
    }
    const st: Stream = {
      sid: id, header: core, conn: conn.cid, expected: 1, held: new Map(), sinceAck: 0, lastAckAt: now, ended: false, disconnectedAt: null,
    };
    this.streams.set(id, st);
    conn.streamId = id;
    this.stats.streams++;
    eff.items.push([id, { type: "ws_status", status: "connected", stream: id }]);
    eff.items.push([id, copyWithout(core, [])]);
    eff.sends.push([conn.cid, this.welcome(st, false)]);
    return eff;
  }

  private takeOver(oldCid: number): Effects {
    const eff = noEffects();
    const c = this.conns.get(oldCid);
    if (c !== undefined && c.open) {
      c.open = false;
      c.streamId = null;
      this.stats.takeovers++;
      eff.sends.push([oldCid, { type: "ws_error", code: "taken_over", detail: "a newer connection resumed this stream" }]);
      eff.closes.push([oldCid, 4001, "taken_over"]);
    }
    return eff;
  }

  private welcome(st: Stream, resumed: boolean): Obj {
    return {
      type: "ws_welcome", binding: WS_BINDING_VERSION, role: "ingest", stream_id: st.sid, seq: st.expected - 1, resumed,
      ack_every: this.s.ack_every, window: this.s.window,
    };
  }

  private sequence(st: Stream, ev: Obj, now: number, eff: Effects): void {
    const seq = ev.ws_seq as number;
    if (seq < st.expected || st.held.has(seq)) {
      this.stats.duplicates++;
      return;
    }
    if (seq === st.expected) {
      this.release(st, ev, eff);
      this.drain(st, eff, true);
    } else {
      st.held.set(seq, [ev, now]);
      if (st.held.size > this.s.reorder_window) this.gap(st, eff);
    }
    this.maybeAck(st, eff, null);
    if (st.sinceAck === 0) st.lastAckAt = now;
  }

  private release(st: Stream, ev: Obj, eff: Effects): void {
    eff.items.push([st.sid, ev]);
    st.expected++;
    st.sinceAck++;
    this.stats.events++;
    if (ev.type === "end") {
      st.ended = true;
      st.sinceAck = Math.max(st.sinceAck, this.s.ack_every);
    }
  }

  private drain(st: Stream, eff: Effects, reordered: boolean): void {
    while (st.held.has(st.expected)) {
      const [ev] = st.held.get(st.expected)!;
      st.held.delete(st.expected);
      if (reordered) this.stats.reordered++;
      this.release(st, ev, eff);
    }
  }

  private gap(st: Stream, eff: Effects): void {
    const first = Math.min(...st.held.keys());
    const missing = first - st.expected;
    this.stats.gaps++;
    this.stats.missing_events += missing;
    eff.items.push([st.sid, { type: "ws_status", status: "gap", stream: st.sid, seq_from: st.expected, seq_to: first - 1, missing }]);
    st.expected = first;
    this.drain(st, eff, false);
  }

  private maybeAck(st: Stream, eff: Effects, now: number | null): void {
    const due = st.sinceAck >= this.s.ack_every || (now !== null && st.sinceAck > 0 && now - st.lastAckAt >= this.s.ack_interval_s);
    if (due && st.conn !== null) {
      eff.sends.push([st.conn, { type: "ws_ack", stream_id: st.sid, seq: st.expected - 1 }]);
      st.sinceAck = 0;
      if (now !== null) st.lastAckAt = now;
    }
  }

  tick(now: number): Effects {
    const eff = noEffects();
    for (const sid of [...this.streams.keys()]) {
      const st = this.streams.get(sid)!;
      while (st.held.size && now - Math.min(...[...st.held.values()].map(([, t]) => t)) >= this.s.reorder_timeout_s) this.gap(st, eff);
      this.maybeAck(st, eff, now);
      if (st.conn === null && st.disconnectedAt !== null && now - st.disconnectedAt >= this.s.resume_timeout_s) this.lose(st, eff, "resume time-out");
    }
    return eff;
  }

  private lose(st: Stream, eff: Effects, why: string): void {
    this.stats.lost_streams++;
    eff.items.push([st.sid, { type: "ws_status", status: "lost", stream: st.sid, detail: why }]);
    this.streams.delete(st.sid);
  }

  disconnect(cid: number, now = 0): Effects {
    const eff = noEffects();
    const conn = this.conns.get(cid);
    this.conns.delete(cid);
    if (conn === undefined || conn.streamId === null) return eff;
    const st = this.streams.get(conn.streamId);
    if (st === undefined || st.conn !== cid) return eff;
    st.conn = null;
    if (st.ended) {
      eff.items.push([st.sid, { type: "ws_status", status: "closed", stream: st.sid }]);
      this.streams.delete(st.sid);
    } else {
      st.disconnectedAt = now;
      eff.items.push([st.sid, { type: "ws_status", status: "disconnected", stream: st.sid, seq: st.expected - 1 }]);
    }
    return eff;
  }

  finish(): Effects {
    const eff = noEffects();
    for (const sid of [...this.streams.keys()]) {
      const st = this.streams.get(sid)!;
      if (st.conn === null && !st.ended) this.lose(st, eff, "shutdown");
    }
    return eff;
  }

  liveStreams(): string[] {
    return [...this.streams.values()].filter((st) => st.conn !== null).map((st) => st.sid);
  }
}

function seqError(ev: unknown): string | null {
  if (!isObj(ev) || typeof ev.type !== "string") return "a batch event must be a JSON object with a string type";
  if (ev.type.startsWith("ws_")) return `control message ${JSON.stringify(ev.type)} inside a batch (section 6 rule 4)`;
  if (!(isIntAt(ev, "ws_seq") && (ev.ws_seq as number) >= 1)) return "ws_seq must be an integer >= 1 (section 6 rule 1)";
  return null;
}

/** The token of an `Authorization: Bearer <token>` value, or null. */
export function bearerToken(authorization: string | null): string | null {
  if (typeof authorization === "string" && authorization.slice(0, 7).toLowerCase() === "bearer ") {
    const tok = authorization.slice(7).replace(/^[\s\x1c-\x1f\x85\xa0]+|[\s\x1c-\x1f\x85\xa0]+$/g, "");
    return tok || null;
  }
  return null;
}

// --- subscriber side ---------------------------------------------------------------------------

export class SubscriberError extends RangeError {
  constructor(message: string) {
    super(message);
    this.name = "SubscriberError";
  }
}

/**
 * The checks of a `/decisions` subscriber (port of `fidetype.adapters.ws.SubscriberCore`).
 * {@link receive} returns `["resubscribe", fromSeq]` on a gap in `ws_seq`.
 */
export class SubscriberCore {
  last: number;
  welcomed = false;
  waiting = false;
  events: Obj[] = [];
  duplicates = 0;
  gaps: number[] = [];
  missed = 0;
  errors: string[] = [];
  ignored = 0;

  /** `fromSeq`: the `from_seq` of the first `ws_subscribe` (null: new decisions only). */
  constructor(readonly fromSeq: number | null = 1) {
    this.last = fromSeq === null ? 0 : fromSeq - 1;
  }

  receive(msg: unknown): ["resubscribe", number] | null {
    if (!isObj(msg) || typeof msg.type !== "string") throw new SubscriberError("a message must be a JSON object with a string type");
    const typ = msg.type;
    if (typ === "ws_welcome") {
      const b = has(msg, "binding") ? msg.binding : WS_BINDING_VERSION;
      if (typeof b !== "string" || !WS_KNOWN_BINDINGS.includes(b)) throw new SubscriberError(`welcome: unknown binding ${JSON.stringify(b)} (section 10)`);
      if ((has(msg, "role") ? msg.role : "decisions") !== "decisions") throw new SubscriberError("welcome: role is not 'decisions'");
      for (const k of ["seq", "missed", "first_available"]) {
        if (has(msg, k) && !(isIntAt(msg, k) && (msg[k] as number) >= 0)) throw new SubscriberError(`welcome: ${k} must be an integer >= 0`);
      }
      if (!this.welcomed && this.fromSeq === null && has(msg, "seq")) this.last = Math.max(this.last, msg.seq as number);
      if ((has(msg, "missed") ? (msg.missed as number) : 0) > 0) {
        this.missed += msg.missed as number;
        if (has(msg, "first_available")) this.last = Math.max(this.last, (msg.first_available as number) - 1);
      }
      this.welcomed = true;
      this.waiting = false;
      return null;
    }
    if (!this.welcomed) throw new SubscriberError("the first message must be ws_welcome (section 7 rule 2)");
    if (this.waiting || typ !== "trust_decision") {
      this.ignored++;
      return null;
    }
    if (!(isIntAt(msg, "ws_seq") && (msg.ws_seq as number) >= 1)) throw new SubscriberError("ws_seq must be an integer >= 1 (section 7 rule 3)");
    const seq = msg.ws_seq as number;
    if (seq <= this.last) {
      this.duplicates++;
      return null;
    }
    if (seq > this.last + 1) {
      this.gaps.push(this.last + 1);
      this.waiting = true;
      return ["resubscribe", this.last + 1];
    }
    msg._line = this.events.length + 1;
    this.errors.push(...tdFormatErrors(msg));
    this.events.push(msg);
    this.last = seq;
    return null;
  }

  finish(): Record<string, unknown> {
    const errs = [...this.errors, ...tdFinalErrors(this.events)];
    if (errs.length) throw new SubscriberError(errs.slice(0, 5).join("; "));
    return {
      decisions: this.events.length, final: this.events.filter((e) => e.is_final === true).length, acted: actedTexts(this.events),
      duplicates: this.duplicates, gaps: [...this.gaps], missed: this.missed, last_seq: this.last,
    };
  }
}

// --- browser client ----------------------------------------------------------------------------

/** The part of the WHATWG WebSocket API that the client uses. */
export interface WebSocketLike {
  readonly readyState: number;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number; reason: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}
export type WebSocketCtor = new (url: string, protocols?: string | string[]) => WebSocketLike;

export interface DecisionSubscriberOptions {
  /** A WebSocket constructor (default: the global `WebSocket`). */
  WebSocket?: WebSocketCtor;
  /** Resume from this `ws_seq` (default: only new decisions). */
  fromSeq?: number;
  /** A token, sent in a `ws_auth` message (a browser cannot set the Authorization header). */
  token?: string;
  /** Only decisions of this stream. */
  streamId?: string;
  /** Called once per decision, in `ws_seq` order, with what to do (`forward` = act on it). */
  onDecision: (d: HandledDecision, wsSeq: number) => void;
  /** Connection state and gap notices. */
  onStatus?: (status: "open" | "welcome" | "gap" | "closed" | "error", detail: string) => void;
  reconnectDelayMs?: number;
}

/**
 * A `/decisions` client that keeps the `ws_seq` order: on a gap or a lost
 * connection it connects again and resubscribes with `from_seq`, so no
 * decision is lost while the server still holds it (FEP-0004 section 7).
 *
 * ```ts
 * const sub = new DecisionSubscriber("ws://127.0.0.1:8765/decisions", {
 *   onDecision: (d) => { if (d.forward) output.type(d.committed!); },
 * });
 * sub.start();
 * ```
 */
export class DecisionSubscriber {
  readonly core: SubscriberCore;
  readonly tracker = new DecisionTracker();
  private ws: WebSocketLike | null = null;
  private stopped = false;
  private next: number | null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(readonly url: string, readonly opts: DecisionSubscriberOptions) {
    this.next = opts.fromSeq ?? null;
    this.core = new SubscriberCore(this.next);
  }

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== null) clearTimeout(this.timer);
    this.ws?.close(1000, "client stop");
    this.ws = null;
  }

  private status(s: Parameters<NonNullable<DecisionSubscriberOptions["onStatus"]>>[0], detail = ""): void {
    this.opts.onStatus?.(s, detail);
  }

  private connect(): void {
    const Ctor = this.opts.WebSocket ?? (globalThis as unknown as { WebSocket?: WebSocketCtor }).WebSocket;
    if (!Ctor) throw new Error("no WebSocket constructor (pass opts.WebSocket)");
    const ws = new Ctor(this.url, [WS_SUBPROTOCOL]);
    this.ws = ws;
    ws.onopen = () => {
      this.status("open");
      if (this.opts.token) ws.send(JSON.stringify({ type: "ws_auth", token: this.opts.token }));
      const req: Obj = { type: "ws_subscribe", binding: WS_BINDING_VERSION };
      if (this.next !== null) req.from_seq = this.next;
      if (this.opts.streamId) req.stream_id = this.opts.streamId;
      ws.send(JSON.stringify(req));
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      let msg: Obj;
      try {
        msg = parseWsMessage(ev.data);
      } catch (e) {
        this.status("error", `bad message: ${(e as Error).message}`);
        return;
      }
      if (msg.type === "ws_error") {
        this.status("error", `${String(msg.code)}: ${String(msg.detail)}`);
        return;
      }
      const n0 = this.core.events.length;
      let act: ["resubscribe", number] | null;
      try {
        act = this.core.receive(msg);
      } catch (e) {
        this.status("error", (e as Error).message);
        return;
      }
      if (msg.type === "ws_welcome") {
        this.status("welcome", `server seq ${String(msg.seq)}`);
        if (this.next === null) this.next = this.core.last + 1;
      }
      if (this.core.events.length > n0) {
        const d = this.core.events[this.core.events.length - 1];
        this.opts.onDecision(this.tracker.push(d), d.ws_seq as number);
      }
      if (act !== null) {
        this.next = act[1];
        this.status("gap", `resubscribe from ws_seq ${act[1]}`);
        ws.close(1000, "resubscribe");
      }
    };
    ws.onclose = (ev) => {
      if (this.ws === ws) this.ws = null;
      this.status("closed", `code ${ev.code}`);
      if (this.core.last) this.next = this.core.last + 1;
      if (!this.stopped) this.timer = setTimeout(() => this.connect(), this.opts.reconnectDelayMs ?? 500);
    };
    ws.onerror = () => this.status("error", "connection error");
  }
}

/** Subscribe to the `/events` tap (NTS events of all streams, for example `hypothesis`). Returns a stop function. */
export function subscribeEvents(url: string, onEvent: (ev: Obj) => void,
  opts: { types?: string[]; token?: string; WebSocket?: WebSocketCtor } = {}): () => void {
  const Ctor = opts.WebSocket ?? (globalThis as unknown as { WebSocket?: WebSocketCtor }).WebSocket;
  if (!Ctor) throw new Error("no WebSocket constructor (pass opts.WebSocket)");
  const ws = new Ctor(url, [WS_SUBPROTOCOL]);
  ws.onopen = () => {
    if (opts.token) ws.send(JSON.stringify({ type: "ws_auth", token: opts.token }));
    const req: Obj = { type: "ws_subscribe", binding: WS_BINDING_VERSION };
    if (opts.types) req.types = opts.types;
    ws.send(JSON.stringify(req));
  };
  ws.onmessage = (ev) => {
    if (typeof ev.data !== "string") return;
    try {
      const m = parseWsMessage(ev.data);
      if (m.type !== "ws_welcome") onEvent(m);
    } catch {
      // ignore a bad message
    }
  };
  return () => ws.close(1000, "client stop");
}
