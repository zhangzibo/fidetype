/**
 * NeuralTextStream JSON Lines readers: from a complete text, or
 * incrementally from a byte or text stream (a `fetch` body, a WebSocket
 * message queue, a Node file stream). Browser safe.
 */

import { decodeUtf8, isBlank, isObj, parseJson, pyLines } from "./json.js";
import { PushResult, StreamEventError, StreamValidator } from "./validate.js";

export type ByteOrText = Uint8Array | string;
export type ChunkSource = AsyncIterable<ByteOrText> | Iterable<ByteOrText> | ReadableStream<ByteOrText>;

/** Parse a complete JSON Lines text into events (each must be an object with a string `type`). */
export function parseNtsText(text: string | Uint8Array): Record<string, unknown>[] {
  const s = typeof text === "string" ? text : decodeUtf8(text);
  const out: Record<string, unknown>[] = [];
  pyLines(s).forEach((line, k) => {
    if (isBlank(line)) return;
    let ev: unknown;
    try {
      ev = parseJson(line);
    } catch (e) {
      throw new StreamEventError(`line ${k + 1}: not JSON: ${(e as Error).message}`);
    }
    if (!isObj(ev) || typeof ev.type !== "string") throw new StreamEventError(`line ${k + 1}: not an object with a string type`);
    out.push(ev);
  });
  return out;
}

async function* chunksOf(src: ChunkSource): AsyncGenerator<ByteOrText> {
  const rs = src as ReadableStream<ByteOrText>;
  if (typeof (src as AsyncIterable<ByteOrText>)[Symbol.asyncIterator] !== "function" && typeof rs.getReader === "function") {
    const reader = rs.getReader();
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) return;
        yield value;
      }
    } finally {
      reader.releaseLock();
    }
  }
  yield* src as AsyncIterable<ByteOrText>;
}

/** Split a byte or text stream into lines (`\n`, `\r\n` or `\r`). UTF-8 is decoded strictly across chunk borders. */
export async function* readLines(src: ChunkSource): AsyncGenerator<string> {
  const dec = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
  let buf = "";
  for await (const chunk of chunksOf(src)) {
    buf += typeof chunk === "string" ? chunk : dec.decode(chunk, { stream: true });
    let m: RegExpExecArray | null;
    const re = /\r\n|\n|\r(?!$)/g;
    let last = 0;
    while ((m = re.exec(buf)) !== null) {
      yield buf.slice(last, m.index);
      last = m.index + m[0].length;
    }
    buf = buf.slice(last);
  }
  buf += dec.decode();
  if (buf.endsWith("\r")) buf = buf.slice(0, -1);
  if (buf) yield buf;
}

/** Read events from a stream, one per non-blank line. */
export async function* readNtsEvents(src: ChunkSource): AsyncGenerator<Record<string, unknown>> {
  let n = 0;
  for await (const line of readLines(src)) {
    n++;
    if (isBlank(line)) continue;
    let ev: unknown;
    try {
      ev = parseJson(line);
    } catch (e) {
      throw new StreamEventError(`line ${n}: not JSON: ${(e as Error).message}`);
    }
    if (!isObj(ev) || typeof ev.type !== "string") throw new StreamEventError(`line ${n}: not an object with a string type`);
    yield ev;
  }
}

/**
 * Read and validate events from a live stream (header first, increasing
 * frame times, normalised rows, valid hypotheses). Throws
 * {@link StreamEventError} at the first bad event.
 */
export async function* validateNtsStream(src: ChunkSource): AsyncGenerator<{ event: Record<string, unknown>; result: PushResult }> {
  const v = new StreamValidator();
  for await (const event of readNtsEvents(src)) yield { event, result: v.push(event) };
}
