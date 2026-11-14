/**
 * Strict JSON for NeuralTextStream, with the same results as the Python
 * reference (`json.loads(..., parse_constant=reject)`).
 *
 * Why not `JSON.parse` alone:
 * - Python keeps `1.0` (a float) apart from `1` (an int). Rules such as
 *   "seq is an integer >= 0" reject `1.0` in Python. This parser records
 *   each integral number that was written as a float literal, and
 *   {@link isIntAt} reads that record.
 * - Python splits lines with `str.splitlines()`, which also splits on
 *   `\r`, `\v`, `\f`, `\x1c`-`\x1e`, `\x85`, `\u2028` and `\u2029`.
 *   {@link pyLines} does the same.
 *
 * The parser rejects `NaN`, `Infinity`, a byte order mark and every
 * other non-JSON token. No Node API is used (browser safe).
 */

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

const floatLiterals = new WeakMap<object, Set<string | number>>();

/** Mark `container[key]` as a number written as a float literal (for example `2.0` or `1e3`). */
export function markFloat(container: object, key: string | number): void {
  let s = floatLiterals.get(container);
  if (!s) {
    s = new Set();
    floatLiterals.set(container, s);
  }
  s.add(key);
}

/** True if `container[key]` was written as a float literal (`2.0`, `1e3`) although its value is integral. */
export function isFloatLiteral(container: object, key: string | number): boolean {
  return floatLiterals.get(container)?.has(key) ?? false;
}

/** Python `isinstance(x, int) and not isinstance(x, bool)` for `container[key]`. */
export function isIntAt(container: object, key: string | number): boolean {
  const v = (container as Record<string | number, unknown>)[key];
  return typeof v === "number" && Number.isInteger(v) && !isFloatLiteral(container, key);
}

export class JsonParseError extends SyntaxError {
  constructor(message: string, readonly position: number) {
    super(`${message} at position ${position}`);
    this.name = "JsonParseError";
  }
}

const WS = new Set([0x20, 0x09, 0x0a, 0x0d]);

/** Parse one JSON text. Throws {@link JsonParseError} (Python `ValueError`) on anything that is not JSON. */
export function parseJson(text: string, opts: { allowConstants?: boolean } = {}): JsonValue {
  let i = 0;
  const n = text.length;

  const fail = (msg: string): never => {
    throw new JsonParseError(msg, i);
  };
  const skip = (): void => {
    while (i < n && WS.has(text.charCodeAt(i))) i++;
  };

  // Returns [value, isFloatLiteralIntegral]
  const value = (): [JsonValue, boolean] => {
    skip();
    if (i >= n) fail("Expecting value");
    const c = text[i];
    if (c === "{") return [object(), false];
    if (c === "[") return [array(), false];
    if (c === '"') return [str(), false];
    if (c === "t" && text.startsWith("true", i)) {
      i += 4;
      return [true, false];
    }
    if (c === "f" && text.startsWith("false", i)) {
      i += 5;
      return [false, false];
    }
    if (c === "n" && text.startsWith("null", i)) {
      i += 4;
      return [null, false];
    }
    // Python json.loads accepts NaN / Infinity / -Infinity unless parse_constant rejects them.
    for (const [tok, val] of [["NaN", NaN], ["Infinity", Infinity], ["-Infinity", -Infinity]] as const) {
      if (text.startsWith(tok, i)) {
        if (!opts.allowConstants) fail(`${tok} is not a JSON value`);
        i += tok.length;
        return [val, false];
      }
    }
    return number();
  };

  const number = (): [number, boolean] => {
    const m = /^-?(?:0|[1-9]\d*)(\.\d+)?([eE][-+]?\d+)?/.exec(text.slice(i, i + 400));
    if (!m) return fail("Expecting value");
    i += m[0].length;
    const v = Number(m[0]);
    const isFloat = m[1] !== undefined || m[2] !== undefined;
    return [v, isFloat && Number.isInteger(v)];
  };

  const str = (): string => {
    i++; // opening quote
    let out = "";
    let start = i;
    for (;;) {
      if (i >= n) fail("Unterminated string");
      const code = text.charCodeAt(i);
      if (code === 0x22) {
        out += text.slice(start, i);
        i++;
        return out;
      }
      if (code < 0x20) fail("Invalid control character in string");
      if (code === 0x5c) {
        out += text.slice(start, i);
        i++;
        const e = text[i];
        const simple: Record<string, string> = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };
        if (e !== undefined && e in simple) {
          out += simple[e];
          i++;
        } else if (e === "u") {
          const hex = text.slice(i + 1, i + 5);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) fail("Invalid \\uXXXX escape");
          out += String.fromCharCode(parseInt(hex, 16));
          i += 5;
        } else {
          fail("Invalid \\escape");
        }
        start = i;
        continue;
      }
      i++;
    }
  };

  const array = (): JsonValue[] => {
    i++;
    const out: JsonValue[] = [];
    skip();
    if (text[i] === "]") {
      i++;
      return out;
    }
    for (;;) {
      const [v, fl] = value();
      if (fl) markFloat(out, out.length);
      out.push(v);
      skip();
      if (text[i] === ",") {
        i++;
        continue;
      }
      if (text[i] === "]") {
        i++;
        return out;
      }
      fail("Expecting ',' delimiter");
    }
  };

  const object = (): JsonObject => {
    i++;
    const out: JsonObject = {};
    skip();
    if (text[i] === "}") {
      i++;
      return out;
    }
    for (;;) {
      skip();
      if (text[i] !== '"') fail("Expecting property name enclosed in double quotes");
      const k = str();
      skip();
      if (text[i] !== ":") fail("Expecting ':' delimiter");
      i++;
      const [v, fl] = value();
      // defineProperty: a "__proto__" key stays a plain own key.
      Object.defineProperty(out, k, { value: v, enumerable: true, writable: true, configurable: true });
      if (fl) markFloat(out, k);
      else floatLiterals.get(out)?.delete(k); // a later duplicate key wins (as in Python)
      skip();
      if (text[i] === ",") {
        i++;
        continue;
      }
      if (text[i] === "}") {
        i++;
        return out;
      }
      fail("Expecting ',' delimiter");
    }
  };

  const [v] = value();
  skip();
  if (i !== n) fail("Extra data");
  return v;
}

/** Python `str.splitlines()` (no line ends kept). */
export function pyLines(text: string): string[] {
  const out: string[] = [];
  const re = /\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    out.push(text.slice(last, m.index));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Python `str.strip()` emptiness test (white space only). */
export function isBlank(line: string): boolean {
  // Python str.isspace() characters (not U+FEFF, which JavaScript \s includes).
  return /^[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/.test(line);
}

/** Decode UTF-8 strictly, keeping a byte order mark (Python `bytes.decode("utf-8")`). */
export function decodeUtf8(bytes: Uint8Array): string {
  return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes);
}

/** Python `json.dumps(..., ensure_ascii=False, allow_nan=False)`-like text for writers. Throws on NaN or infinity. */
export function dumpJson(value: unknown): string {
  return JSON.stringify(value, (_k, v) => {
    if (typeof v === "number" && !Number.isFinite(v)) throw new RangeError(`${v} is not a JSON value`);
    return v;
  });
}

// --- small Python-semantics helpers used by the validators -------------------------

export function isObj(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

export function has(o: object, k: string): boolean {
  return Object.prototype.hasOwnProperty.call(o, k);
}

/** Python `dict.get(k)`: the value, or null when the key is absent. */
export function get(o: Record<string, unknown>, k: string): unknown {
  return has(o, k) ? o[k] : null;
}

/** Python `isinstance(x, (int, float)) and not isinstance(x, bool)` (infinity counts). */
export function isNum(x: unknown): x is number {
  return typeof x === "number";
}

/** A finite number (the FEP profiles' `_num`). */
export function isFinNum(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** Number of Unicode code points (Python `len(str)`). */
export function cpLen(s: string): number {
  let n = 0;
  for (const _ of s) n++;
  return n;
}
