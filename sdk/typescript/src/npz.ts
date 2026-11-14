/**
 * A small NPZ reader (spec 6.1): ZIP (stored or deflate) + NPY v1/v2/v3.
 * Pure TypeScript, no Node API, no dependency.
 *
 * It reads the dtypes that a NeuralTextStream uses: little/big-endian
 * floats (f2 is not supported), signed and unsigned integers, booleans and
 * Unicode strings (`U`). An object array (`O`) needs Python pickle, so it
 * raises {@link NpyPickleError}: the same case where NumPy raises with
 * `allow_pickle=False`.
 */

export type NpyKind = "f" | "i" | "u" | "b" | "U";

export interface NpyArray {
  /** NumPy-like dtype name: float32, float64, int64, bool, <U5, ... */
  dtype: string;
  kind: NpyKind;
  shape: number[];
  /** Row-major values. Numbers for numeric and bool kinds (bool: 0/1), strings for U. */
  data: (number | string | boolean)[];
}

export class NpyPickleError extends Error {}
export class ZipError extends Error {}

// --- inflate (RFC 1951) ------------------------------------------------------

class Bits {
  pos = 0;
  bit = 0;
  constructor(readonly buf: Uint8Array) {}
  read(n: number): number {
    let v = 0;
    for (let k = 0; k < n; k++) {
      if (this.pos >= this.buf.length) throw new ZipError("deflate data ends early");
      v |= ((this.buf[this.pos] >> this.bit) & 1) << k;
      if (++this.bit === 8) {
        this.bit = 0;
        this.pos++;
      }
    }
    return v;
  }
  align(): void {
    if (this.bit) {
      this.bit = 0;
      this.pos++;
    }
  }
}

interface Huff {
  counts: Uint16Array;
  symbols: Uint16Array;
}

function huff(lengths: ArrayLike<number>): Huff {
  const counts = new Uint16Array(16);
  for (let i = 0; i < lengths.length; i++) counts[lengths[i]]++;
  counts[0] = 0;
  const offs = new Uint16Array(16);
  for (let i = 1; i < 16; i++) offs[i] = offs[i - 1] + counts[i - 1];
  const symbols = new Uint16Array(lengths.length);
  for (let i = 0; i < lengths.length; i++) if (lengths[i]) symbols[offs[lengths[i]]++] = i;
  return { counts, symbols };
}

function decodeSym(b: Bits, h: Huff): number {
  let code = 0;
  let first = 0;
  let index = 0;
  for (let len = 1; len < 16; len++) {
    code |= b.read(1);
    const count = h.counts[len];
    if (code - count < first) return h.symbols[index + (code - first)];
    index += count;
    first += count;
    first <<= 1;
    code <<= 1;
  }
  throw new ZipError("bad Huffman code");
}

const LBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258];
const LEXT = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
const DBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577];
const DEXT = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
const CLORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

/** Decompress raw DEFLATE data. */
export function inflateRaw(data: Uint8Array, expectedSize?: number): Uint8Array {
  const b = new Bits(data);
  let out = new Uint8Array(expectedSize && expectedSize > 0 ? expectedSize : Math.max(1024, data.length * 4));
  let n = 0;
  const ensure = (k: number): void => {
    if (n + k <= out.length) return;
    const bigger = new Uint8Array(Math.max(out.length * 2, n + k));
    bigger.set(out.subarray(0, n));
    out = bigger;
  };
  let fixedL: Huff | null = null;
  let fixedD: Huff | null = null;
  for (;;) {
    const final = b.read(1);
    const type = b.read(2);
    if (type === 0) {
      b.align();
      if (b.pos + 4 > data.length) throw new ZipError("stored block ends early");
      const len = data[b.pos] | (data[b.pos + 1] << 8);
      const nlen = data[b.pos + 2] | (data[b.pos + 3] << 8);
      if ((len ^ 0xffff) !== nlen) throw new ZipError("bad stored block length");
      b.pos += 4;
      if (b.pos + len > data.length) throw new ZipError("stored block ends early");
      ensure(len);
      out.set(data.subarray(b.pos, b.pos + len), n);
      n += len;
      b.pos += len;
    } else if (type === 1 || type === 2) {
      let lh: Huff;
      let dh: Huff;
      if (type === 1) {
        if (!fixedL) {
          const l = new Uint8Array(288);
          l.fill(8, 0, 144);
          l.fill(9, 144, 256);
          l.fill(7, 256, 280);
          l.fill(8, 280, 288);
          fixedL = huff(l);
          fixedD = huff(new Uint8Array(30).fill(5));
        }
        lh = fixedL;
        dh = fixedD as Huff;
      } else {
        const hlit = b.read(5) + 257;
        const hdist = b.read(5) + 1;
        const hclen = b.read(4) + 4;
        const cl = new Uint8Array(19);
        for (let k = 0; k < hclen; k++) cl[CLORDER[k]] = b.read(3);
        const clh = huff(cl);
        const lens = new Uint8Array(hlit + hdist);
        let k = 0;
        while (k < hlit + hdist) {
          const sym = decodeSym(b, clh);
          if (sym < 16) lens[k++] = sym;
          else {
            let rep = 0;
            let val = 0;
            if (sym === 16) {
              if (k === 0) throw new ZipError("repeat without a length");
              val = lens[k - 1];
              rep = 3 + b.read(2);
            } else if (sym === 17) rep = 3 + b.read(3);
            else rep = 11 + b.read(7);
            if (k + rep > hlit + hdist) throw new ZipError("too many code lengths");
            lens.fill(val, k, k + rep);
            k += rep;
          }
        }
        lh = huff(lens.subarray(0, hlit));
        dh = huff(lens.subarray(hlit));
      }
      for (;;) {
        const sym = decodeSym(b, lh);
        if (sym < 256) {
          ensure(1);
          out[n++] = sym;
        } else if (sym === 256) break;
        else {
          const li = sym - 257;
          if (li >= 29) throw new ZipError("bad length symbol");
          const len = LBASE[li] + b.read(LEXT[li]);
          const di = decodeSym(b, dh);
          if (di >= 30) throw new ZipError("bad distance symbol");
          const dist = DBASE[di] + b.read(DEXT[di]);
          if (dist > n) throw new ZipError("distance too far back");
          ensure(len);
          for (let k = 0; k < len; k++, n++) out[n] = out[n - dist];
        }
      }
    } else throw new ZipError("bad block type");
    if (final) break;
  }
  return out.subarray(0, n);
}

// --- ZIP ------------------------------------------------------------------------

export interface ZipEntry {
  name: string;
  data: Uint8Array;
}

/** Read all members of a ZIP archive (central directory; methods 0 and 8). */
export function readZip(buf: Uint8Array): ZipEntry[] {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (buf.length < 22) throw new ZipError("not a ZIP file");
  let eocd = -1;
  for (let p = buf.length - 22; p >= Math.max(0, buf.length - 22 - 65535); p--) {
    if (dv.getUint32(p, true) === 0x06054b50) {
      eocd = p;
      break;
    }
  }
  if (eocd < 0) throw new ZipError("not a ZIP file (no end of central directory)");
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const out: ZipEntry[] = [];
  const dec = new TextDecoder("utf-8");
  for (let k = 0; k < count; k++) {
    if (p + 46 > buf.length || dv.getUint32(p, true) !== 0x02014b50) throw new ZipError("bad central directory");
    const method = dv.getUint16(p + 10, true);
    const csize = dv.getUint32(p + 20, true);
    const usize = dv.getUint32(p + 24, true);
    const nlen = dv.getUint16(p + 28, true);
    const xlen = dv.getUint16(p + 30, true);
    const clen = dv.getUint16(p + 32, true);
    const loff = dv.getUint32(p + 42, true);
    const name = dec.decode(buf.subarray(p + 46, p + 46 + nlen));
    p += 46 + nlen + xlen + clen;
    if (loff + 30 > buf.length || dv.getUint32(loff, true) !== 0x04034b50) throw new ZipError("bad local header");
    const start = loff + 30 + dv.getUint16(loff + 26, true) + dv.getUint16(loff + 28, true);
    const raw = buf.subarray(start, start + csize);
    if (raw.length !== csize) throw new ZipError("member data ends early");
    let data: Uint8Array;
    if (method === 0) data = raw;
    else if (method === 8) data = inflateRaw(raw, usize);
    else throw new ZipError(`unsupported compression method ${method}`);
    if (data.length !== usize) throw new ZipError("bad uncompressed size");
    out.push({ name, data });
  }
  return out;
}

// --- NPY ------------------------------------------------------------------------

function parseHeaderDict(s: string): { descr: string; fortran: boolean; shape: number[] } {
  const descr = /'descr'\s*:\s*'([^']*)'/.exec(s);
  const fortran = /'fortran_order'\s*:\s*(True|False)/.exec(s);
  const shape = /'shape'\s*:\s*\(([^)]*)\)/.exec(s);
  if (!descr || !fortran || !shape) {
    if (/'descr'\s*:\s*\[/.test(s)) throw new NpyPickleError("structured dtypes are not supported");
    throw new ZipError("bad NPY header");
  }
  const dims = shape[1]
    .split(",")
    .map((x) => x.trim())
    .filter((x) => x !== "")
    .map((x) => Number(x.replace(/L$/, "")));
  if (dims.some((d) => !Number.isInteger(d) || d < 0)) throw new ZipError("bad NPY shape");
  return { descr: descr[1], fortran: fortran[1] === "True", shape: dims };
}

/** Parse one `.npy` file. */
export function readNpy(buf: Uint8Array): NpyArray {
  if (buf.length < 10 || buf[0] !== 0x93 || String.fromCharCode(...buf.subarray(1, 6)) !== "NUMPY") {
    throw new ZipError("not an NPY file");
  }
  const major = buf[6];
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  let hlen: number;
  let hstart: number;
  if (major === 1) {
    hlen = dv.getUint16(8, true);
    hstart = 10;
  } else if (major === 2 || major === 3) {
    hlen = dv.getUint32(8, true);
    hstart = 12;
  } else throw new ZipError(`unknown NPY version ${major}`);
  const header = new TextDecoder(major === 3 ? "utf-8" : "latin1").decode(buf.subarray(hstart, hstart + hlen));
  const { descr, fortran, shape } = parseHeaderDict(header);
  const m = /^([<>|=]?)([a-zA-Z])(\d*)$/.exec(descr);
  if (!m) throw new ZipError(`unsupported dtype ${descr}`);
  const [, order, kindRaw, sizeRaw] = m;
  if (kindRaw === "O") throw new NpyPickleError("Object arrays cannot be loaded when allow_pickle=False");
  const little = order !== ">";
  const size = Number(sizeRaw || "0");
  const count = shape.reduce((a, d) => a * d, 1);
  let off = hstart + hlen;
  const data: (number | string | boolean)[] = new Array(count);
  let kind: NpyKind;
  let dtype: string;
  if (kindRaw === "f" && (size === 4 || size === 8)) {
    kind = "f";
    dtype = size === 4 ? "float32" : "float64";
  } else if ((kindRaw === "i" || kindRaw === "u") && [1, 2, 4, 8].includes(size)) {
    kind = kindRaw;
    dtype = `${kindRaw === "i" ? "int" : "uint"}${size * 8}`;
  } else if (kindRaw === "b" && size === 1) {
    kind = "b";
    dtype = "bool";
  } else if (kindRaw === "U") {
    kind = "U";
    dtype = `${order === "|" ? "" : order}U${size}`;
  } else throw new ZipError(`unsupported dtype ${descr}`);
  const item = kind === "U" ? 4 * size : size;
  if (off + item * count > buf.length) throw new ZipError("NPY data ends early");
  for (let k = 0; k < count; k++, off += item) {
    if (kind === "f") data[k] = size === 4 ? dv.getFloat32(off, little) : dv.getFloat64(off, little);
    else if (kind === "i" || kind === "u") {
      const s = kind === "i";
      if (size === 1) data[k] = s ? dv.getInt8(off) : dv.getUint8(off);
      else if (size === 2) data[k] = s ? dv.getInt16(off, little) : dv.getUint16(off, little);
      else if (size === 4) data[k] = s ? dv.getInt32(off, little) : dv.getUint32(off, little);
      else data[k] = Number(s ? dv.getBigInt64(off, little) : dv.getBigUint64(off, little));
    } else if (kind === "b") data[k] = buf[off] !== 0;
    else {
      let str = "";
      for (let c = 0; c < size; c++) {
        const cp = dv.getUint32(off + 4 * c, little);
        if (cp === 0) break; // NumPy strips trailing NULs
        str += String.fromCodePoint(cp);
      }
      data[k] = str;
    }
  }
  if (fortran && shape.length > 1) {
    // Re-order column-major data into row-major order.
    const rm = new Array(count);
    const strideF: number[] = [];
    let acc = 1;
    for (const d of shape) {
      strideF.push(acc);
      acc *= d;
    }
    const idx = new Array(shape.length).fill(0);
    for (let k = 0; k < count; k++) {
      let f = 0;
      for (let a = 0; a < shape.length; a++) f += idx[a] * strideF[a];
      rm[k] = data[f];
      for (let a = shape.length - 1; a >= 0; a--) {
        if (++idx[a] < shape[a]) break;
        idx[a] = 0;
      }
    }
    return { dtype, kind, shape, data: rm };
  }
  return { dtype, kind, shape, data };
}

export interface NpzFile {
  /** Key names in archive order (".npy" removed), as NumPy's `NpzFile.files`. */
  files: string[];
  /** Load one key. Throws {@link NpyPickleError} for object arrays. */
  get(key: string): NpyArray;
}

/** Open an NPZ archive. Throws {@link ZipError} if it is not a ZIP. */
export function readNpz(buf: Uint8Array): NpzFile {
  const entries = readZip(buf);
  const map = new Map<string, Uint8Array>();
  const files: string[] = [];
  for (const e of entries) {
    const key = e.name.endsWith(".npy") ? e.name.slice(0, -4) : e.name;
    files.push(key);
    map.set(key, e.data);
  }
  return {
    files,
    get(key: string): NpyArray {
      const d = map.get(key);
      if (!d) throw new ZipError(`no key ${key}`);
      return readNpy(d);
    },
  };
}
