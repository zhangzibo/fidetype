//! A small NPZ reader and writer (spec 6.1): ZIP (stored or deflate) + NPY
//! v1/v2/v3. No dependency.
//!
//! The reader handles the dtypes that a NeuralTextStream uses: little and
//! big-endian floats (`f4`, `f8`), signed and unsigned integers, booleans and
//! Unicode strings (`U`). An object array (`O`) needs Python pickle, so it
//! gives [`NpyError::Pickle`]: the same case where NumPy raises with
//! `allow_pickle=False`.
//!
//! The writer ([`write_npz`]) writes stored (uncompressed) members, as
//! `numpy.savez` does.

use alloc::string::{String, ToString};
use alloc::vec;
use alloc::vec::Vec;
use alloc::format;

/// The kind of an NPY array.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NpyKind {
    F,
    I,
    U,
    B,
    Str,
}

/// One cell of an NPY array.
#[derive(Debug, Clone)]
pub enum Cell {
    Num(f64),
    Bool(bool),
    Str(String),
}

/// A parsed NPY array (row-major data).
#[derive(Debug, Clone)]
pub struct NpyArray {
    /// NumPy-like dtype name: float32, float64, int64, bool, <U5, ...
    pub dtype: String,
    pub kind: NpyKind,
    pub shape: Vec<usize>,
    pub data: Vec<Cell>,
}

/// Errors of the NPZ reader.
#[derive(Debug, Clone)]
pub enum NpyError {
    /// The member needs pickle (object or structured dtype).
    Pickle(String),
    /// Bad ZIP, DEFLATE or NPY data.
    Bad(String),
}

impl NpyError {
    pub fn message(&self) -> &str {
        match self {
            NpyError::Pickle(m) | NpyError::Bad(m) => m,
        }
    }
}

fn bad(m: &str) -> NpyError {
    NpyError::Bad(m.to_string())
}

// --- inflate (RFC 1951) ------------------------------------------------------

struct Bits<'a> {
    buf: &'a [u8],
    pos: usize,
    bit: u32,
}

impl<'a> Bits<'a> {
    fn read(&mut self, n: u32) -> Result<u32, NpyError> {
        let mut v = 0u32;
        for k in 0..n {
            if self.pos >= self.buf.len() {
                return Err(bad("deflate data ends early"));
            }
            v |= (((self.buf[self.pos] >> self.bit) & 1) as u32) << k;
            self.bit += 1;
            if self.bit == 8 {
                self.bit = 0;
                self.pos += 1;
            }
        }
        Ok(v)
    }
    fn align(&mut self) {
        if self.bit != 0 {
            self.bit = 0;
            self.pos += 1;
        }
    }
}

struct Huff {
    counts: [u16; 16],
    symbols: Vec<u16>,
}

fn huff(lengths: &[u8]) -> Huff {
    let mut counts = [0u16; 16];
    for &l in lengths {
        counts[l as usize] += 1;
    }
    counts[0] = 0;
    let mut offs = [0u16; 16];
    for i in 1..16 {
        offs[i] = offs[i - 1] + counts[i - 1];
    }
    let mut symbols = vec![0u16; lengths.len()];
    for (i, &l) in lengths.iter().enumerate() {
        if l != 0 {
            symbols[offs[l as usize] as usize] = i as u16;
            offs[l as usize] += 1;
        }
    }
    Huff { counts, symbols }
}

fn decode_sym(b: &mut Bits, h: &Huff) -> Result<u16, NpyError> {
    let mut code: i32 = 0;
    let mut first: i32 = 0;
    let mut index: i32 = 0;
    for len in 1..16 {
        code |= b.read(1)? as i32;
        let count = h.counts[len] as i32;
        if code - count < first {
            return h.symbols.get((index + (code - first)) as usize).copied().ok_or_else(|| bad("bad Huffman code"));
        }
        index += count;
        first += count;
        first <<= 1;
        code <<= 1;
    }
    Err(bad("bad Huffman code"))
}

const LBASE: [u32; 29] = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258];
const LEXT: [u32; 29] = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
const DBASE: [u32; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193,
    12289, 16385, 24577,
];
const DEXT: [u32; 30] = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
const CLORDER: [usize; 19] = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

/// Decompress raw DEFLATE data.
pub fn inflate_raw(data: &[u8], expected_size: usize) -> Result<Vec<u8>, NpyError> {
    let mut b = Bits { buf: data, pos: 0, bit: 0 };
    let mut out: Vec<u8> = Vec::with_capacity(expected_size.min(1 << 28));
    loop {
        let fin = b.read(1)?;
        let typ = b.read(2)?;
        if typ == 0 {
            b.align();
            if b.pos + 4 > data.len() {
                return Err(bad("stored block ends early"));
            }
            let len = data[b.pos] as usize | ((data[b.pos + 1] as usize) << 8);
            let nlen = data[b.pos + 2] as usize | ((data[b.pos + 3] as usize) << 8);
            if (len ^ 0xffff) != nlen {
                return Err(bad("bad stored block length"));
            }
            b.pos += 4;
            if b.pos + len > data.len() {
                return Err(bad("stored block ends early"));
            }
            out.extend_from_slice(&data[b.pos..b.pos + len]);
            b.pos += len;
        } else if typ == 1 || typ == 2 {
            let (lh, dh) = if typ == 1 {
                let mut l = [0u8; 288];
                l[..144].fill(8);
                l[144..256].fill(9);
                l[256..280].fill(7);
                l[280..].fill(8);
                (huff(&l), huff(&[5u8; 30]))
            } else {
                let hlit = b.read(5)? as usize + 257;
                let hdist = b.read(5)? as usize + 1;
                let hclen = b.read(4)? as usize + 4;
                let mut cl = [0u8; 19];
                for &o in CLORDER.iter().take(hclen) {
                    cl[o] = b.read(3)? as u8;
                }
                let clh = huff(&cl);
                let mut lens = vec![0u8; hlit + hdist];
                let mut k = 0;
                while k < hlit + hdist {
                    let sym = decode_sym(&mut b, &clh)?;
                    if sym < 16 {
                        lens[k] = sym as u8;
                        k += 1;
                    } else {
                        let (val, rep) = if sym == 16 {
                            if k == 0 {
                                return Err(bad("repeat without a length"));
                            }
                            (lens[k - 1], 3 + b.read(2)? as usize)
                        } else if sym == 17 {
                            (0, 3 + b.read(3)? as usize)
                        } else {
                            (0, 11 + b.read(7)? as usize)
                        };
                        if k + rep > hlit + hdist {
                            return Err(bad("too many code lengths"));
                        }
                        lens[k..k + rep].fill(val);
                        k += rep;
                    }
                }
                (huff(&lens[..hlit]), huff(&lens[hlit..]))
            };
            loop {
                let sym = decode_sym(&mut b, &lh)? as usize;
                if sym < 256 {
                    out.push(sym as u8);
                } else if sym == 256 {
                    break;
                } else {
                    let li = sym - 257;
                    if li >= 29 {
                        return Err(bad("bad length symbol"));
                    }
                    let len = (LBASE[li] + b.read(LEXT[li])?) as usize;
                    let di = decode_sym(&mut b, &dh)? as usize;
                    if di >= 30 {
                        return Err(bad("bad distance symbol"));
                    }
                    let dist = (DBASE[di] + b.read(DEXT[di])?) as usize;
                    if dist > out.len() {
                        return Err(bad("distance too far back"));
                    }
                    for _ in 0..len {
                        let c = out[out.len() - dist];
                        out.push(c);
                    }
                }
            }
        } else {
            return Err(bad("bad block type"));
        }
        if fin == 1 {
            break;
        }
    }
    Ok(out)
}

// --- ZIP ------------------------------------------------------------------------

fn u16le(b: &[u8], p: usize) -> Result<usize, NpyError> {
    b.get(p..p + 2).map(|s| u16::from_le_bytes([s[0], s[1]]) as usize).ok_or_else(|| bad("ZIP data ends early"))
}
fn u32le(b: &[u8], p: usize) -> Result<usize, NpyError> {
    b.get(p..p + 4).map(|s| u32::from_le_bytes([s[0], s[1], s[2], s[3]]) as usize).ok_or_else(|| bad("ZIP data ends early"))
}

/// A ZIP member: (name, uncompressed data).
pub type ZipEntry = (String, Vec<u8>);

/// Read all members of a ZIP archive (central directory; methods 0 and 8).
pub fn read_zip(buf: &[u8]) -> Result<Vec<ZipEntry>, NpyError> {
    if buf.len() < 22 {
        return Err(bad("not a ZIP file"));
    }
    let mut eocd = None;
    let lo = buf.len().saturating_sub(22 + 65535);
    let mut p = buf.len() - 22;
    loop {
        if u32le(buf, p)? == 0x0605_4b50 {
            eocd = Some(p);
            break;
        }
        if p == lo {
            break;
        }
        p -= 1;
    }
    let eocd = eocd.ok_or_else(|| bad("not a ZIP file (no end of central directory)"))?;
    let count = u16le(buf, eocd + 10)?;
    let mut p = u32le(buf, eocd + 16)?;
    let mut out = Vec::new();
    for _ in 0..count {
        if p + 46 > buf.len() || u32le(buf, p)? != 0x0201_4b50 {
            return Err(bad("bad central directory"));
        }
        let method = u16le(buf, p + 10)?;
        let csize = u32le(buf, p + 20)?;
        let usize_ = u32le(buf, p + 24)?;
        let nlen = u16le(buf, p + 28)?;
        let xlen = u16le(buf, p + 30)?;
        let clen = u16le(buf, p + 32)?;
        let loff = u32le(buf, p + 42)?;
        let name_bytes = buf.get(p + 46..p + 46 + nlen).ok_or_else(|| bad("bad central directory"))?;
        let name = String::from_utf8_lossy(name_bytes).into_owned();
        p += 46 + nlen + xlen + clen;
        if loff + 30 > buf.len() || u32le(buf, loff)? != 0x0403_4b50 {
            return Err(bad("bad local header"));
        }
        let start = loff + 30 + u16le(buf, loff + 26)? + u16le(buf, loff + 28)?;
        let raw = buf.get(start..start + csize).ok_or_else(|| bad("member data ends early"))?;
        let data = match method {
            0 => raw.to_vec(),
            8 => inflate_raw(raw, usize_)?,
            m => return Err(NpyError::Bad(format!("unsupported compression method {}", m))),
        };
        if data.len() != usize_ {
            return Err(bad("bad uncompressed size"));
        }
        out.push((name, data));
    }
    Ok(out)
}

// --- NPY ------------------------------------------------------------------------

fn after_key<'a>(s: &'a str, key: &str) -> Option<&'a str> {
    let i = s.find(key)?;
    let rest = s[i + key.len()..].trim_start();
    let rest = rest.strip_prefix(':')?;
    Some(rest.trim_start())
}

fn parse_header_dict(s: &str) -> Result<(String, bool, Vec<usize>), NpyError> {
    let descr = after_key(s, "'descr'").and_then(|r| {
        let r = r.strip_prefix('\'')?;
        let e = r.find('\'')?;
        Some(r[..e].to_string())
    });
    let fortran = after_key(s, "'fortran_order'").and_then(|r| {
        if r.starts_with("True") {
            Some(true)
        } else if r.starts_with("False") {
            Some(false)
        } else {
            None
        }
    });
    let shape = after_key(s, "'shape'").and_then(|r| {
        let r = r.strip_prefix('(')?;
        let e = r.find(')')?;
        Some(r[..e].to_string())
    });
    let (descr, fortran, shape) = match (descr, fortran, shape) {
        (Some(d), Some(f), Some(sh)) => (d, f, sh),
        _ => {
            if after_key(s, "'descr'").map_or(false, |r| r.starts_with('[')) {
                return Err(NpyError::Pickle("structured dtypes are not supported".to_string()));
            }
            return Err(bad("bad NPY header"));
        }
    };
    let mut dims = Vec::new();
    for part in shape.split(',') {
        let t = part.trim();
        if t.is_empty() {
            continue;
        }
        let t = t.strip_suffix('L').unwrap_or(t);
        let d: usize = t.parse().map_err(|_| bad("bad NPY shape"))?;
        dims.push(d);
    }
    Ok((descr, fortran, dims))
}

/// Parse one `.npy` file.
pub fn read_npy(buf: &[u8]) -> Result<NpyArray, NpyError> {
    if buf.len() < 10 || buf[0] != 0x93 || &buf[1..6] != b"NUMPY" {
        return Err(bad("not an NPY file"));
    }
    let major = buf[6];
    let (hlen, hstart) = match major {
        1 => (u16le(buf, 8)?, 10),
        2 | 3 => (u32le(buf, 8)?, 12),
        m => return Err(NpyError::Bad(format!("unknown NPY version {}", m))),
    };
    let hbytes = buf.get(hstart..hstart + hlen).ok_or_else(|| bad("NPY header ends early"))?;
    let header: String = if major == 3 {
        String::from_utf8_lossy(hbytes).into_owned()
    } else {
        hbytes.iter().map(|&b| b as char).collect()
    };
    let (descr, fortran, shape) = parse_header_dict(&header)?;
    let d = descr.as_bytes();
    let (order, rest) = match d.first() {
        Some(b'<') | Some(b'>') | Some(b'|') | Some(b'=') => (d[0] as char, &descr[1..]),
        _ => (' ', descr.as_str()),
    };
    let mut chars = rest.chars();
    let kind_raw = chars.next().ok_or_else(|| NpyError::Bad(format!("unsupported dtype {}", descr)))?;
    let size_raw: String = chars.collect();
    if !kind_raw.is_ascii_alphabetic() || !size_raw.chars().all(|c| c.is_ascii_digit()) {
        return Err(NpyError::Bad(format!("unsupported dtype {}", descr)));
    }
    if kind_raw == 'O' {
        return Err(NpyError::Pickle("Object arrays cannot be loaded when allow_pickle=False".to_string()));
    }
    let little = order != '>';
    let size: usize = if size_raw.is_empty() { 0 } else { size_raw.parse().map_err(|_| bad("bad dtype size"))? };
    let count: usize = shape.iter().try_fold(1usize, |a, &d| a.checked_mul(d)).ok_or_else(|| bad("NPY shape too large"))?;
    let (kind, dtype) = match (kind_raw, size) {
        ('f', 4) => (NpyKind::F, "float32".to_string()),
        ('f', 8) => (NpyKind::F, "float64".to_string()),
        ('i', 1 | 2 | 4 | 8) => (NpyKind::I, format!("int{}", size * 8)),
        ('u', 1 | 2 | 4 | 8) => (NpyKind::U, format!("uint{}", size * 8)),
        ('b', 1) => (NpyKind::B, "bool".to_string()),
        ('U', _) => (NpyKind::Str, if order == '|' || order == ' ' { format!("U{}", size) } else { format!("{}U{}", order, size) }),
        _ => return Err(NpyError::Bad(format!("unsupported dtype {}", descr))),
    };
    let item = if kind == NpyKind::Str { 4 * size } else { size };
    let mut off = hstart + hlen;
    let need = item.checked_mul(count).ok_or_else(|| bad("NPY shape too large"))?;
    if off + need > buf.len() {
        return Err(bad("NPY data ends early"));
    }
    let rd = |o: usize, n: usize| -> [u8; 8] {
        let mut a = [0u8; 8];
        if little {
            a[..n].copy_from_slice(&buf[o..o + n]);
        } else {
            for k in 0..n {
                a[k] = buf[o + n - 1 - k];
            }
        }
        a
    };
    let mut data = Vec::with_capacity(count);
    for _ in 0..count {
        let cell = match kind {
            NpyKind::F => {
                let a = rd(off, size);
                if size == 4 {
                    Cell::Num(f32::from_le_bytes([a[0], a[1], a[2], a[3]]) as f64)
                } else {
                    Cell::Num(f64::from_le_bytes(a))
                }
            }
            NpyKind::I => {
                let a = rd(off, size);
                let v = match size {
                    1 => a[0] as i8 as f64,
                    2 => i16::from_le_bytes([a[0], a[1]]) as f64,
                    4 => i32::from_le_bytes([a[0], a[1], a[2], a[3]]) as f64,
                    _ => i64::from_le_bytes(a) as f64,
                };
                Cell::Num(v)
            }
            NpyKind::U => {
                let a = rd(off, size);
                let v = match size {
                    1 => a[0] as f64,
                    2 => u16::from_le_bytes([a[0], a[1]]) as f64,
                    4 => u32::from_le_bytes([a[0], a[1], a[2], a[3]]) as f64,
                    _ => u64::from_le_bytes(a) as f64,
                };
                Cell::Num(v)
            }
            NpyKind::B => Cell::Bool(buf[off] != 0),
            NpyKind::Str => {
                let mut s = String::new();
                for c in 0..size {
                    let a = rd(off + 4 * c, 4);
                    let cp = u32::from_le_bytes([a[0], a[1], a[2], a[3]]);
                    if cp == 0 {
                        break; // NumPy strips trailing NULs
                    }
                    if cp > 0x10FFFF {
                        return Err(NpyError::Bad(format!("Invalid code point {}", cp)));
                    }
                    s.push(char::from_u32(cp).unwrap_or('\u{FFFD}'));
                }
                Cell::Str(s)
            }
        };
        data.push(cell);
        off += item;
    }
    if fortran && shape.len() > 1 {
        // Re-order column-major data into row-major order.
        let mut stride_f = Vec::with_capacity(shape.len());
        let mut acc = 1;
        for &d in &shape {
            stride_f.push(acc);
            acc *= d;
        }
        let mut idx = vec![0usize; shape.len()];
        let mut rm = Vec::with_capacity(count);
        for _ in 0..count {
            let f: usize = idx.iter().zip(&stride_f).map(|(i, s)| i * s).sum();
            rm.push(data[f].clone());
            for a in (0..shape.len()).rev() {
                idx[a] += 1;
                if idx[a] < shape[a] {
                    break;
                }
                idx[a] = 0;
            }
        }
        data = rm;
    }
    Ok(NpyArray { dtype, kind, shape, data })
}

/// An opened NPZ archive.
pub struct NpzFile {
    /// Key names in archive order (".npy" removed), as NumPy's `NpzFile.files`.
    pub files: Vec<String>,
    members: Vec<(String, Vec<u8>)>,
}

impl NpzFile {
    /// Load one key.
    pub fn get(&self, key: &str) -> Result<NpyArray, NpyError> {
        let d = self.members.iter().rev().find(|(k, _)| k == key).ok_or_else(|| NpyError::Bad(format!("no key {}", key)))?;
        read_npy(&d.1)
    }
}

/// Open an NPZ archive.
pub fn read_npz(buf: &[u8]) -> Result<NpzFile, NpyError> {
    let entries = read_zip(buf)?;
    let mut files = Vec::new();
    let mut members = Vec::new();
    for (name, data) in entries {
        let key = name.strip_suffix(".npy").unwrap_or(&name).to_string();
        files.push(key.clone());
        members.push((key, data));
    }
    Ok(NpzFile { files, members })
}

// --- writer ---------------------------------------------------------------------

/// An array to write with [`write_npz`].
#[derive(Debug, Clone)]
pub enum NpyData {
    F32 { shape: Vec<usize>, data: Vec<f32> },
    F64 { shape: Vec<usize>, data: Vec<f64> },
    I64 { shape: Vec<usize>, data: Vec<i64> },
    /// Unicode strings (`<U{n}`); `shape` = [] for a scalar.
    Str { shape: Vec<usize>, data: Vec<String> },
}

fn crc32(data: &[u8]) -> u32 {
    let mut c = 0xFFFF_FFFFu32;
    for &b in data {
        c ^= b as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { (c >> 1) ^ 0xEDB8_8320 } else { c >> 1 };
        }
    }
    !c
}

/// The bytes of one `.npy` file (version 1.0).
pub fn npy_bytes(a: &NpyData) -> Vec<u8> {
    let (descr, shape, body): (String, &Vec<usize>, Vec<u8>) = match a {
        NpyData::F32 { shape, data } => ("<f4".into(), shape, data.iter().flat_map(|x| x.to_le_bytes()).collect()),
        NpyData::F64 { shape, data } => ("<f8".into(), shape, data.iter().flat_map(|x| x.to_le_bytes()).collect()),
        NpyData::I64 { shape, data } => ("<i8".into(), shape, data.iter().flat_map(|x| x.to_le_bytes()).collect()),
        NpyData::Str { shape, data } => {
            let n = data.iter().map(|s| s.chars().count()).max().unwrap_or(0).max(1);
            let mut body = Vec::new();
            for s in data {
                let mut k = 0;
                for c in s.chars() {
                    body.extend_from_slice(&(c as u32).to_le_bytes());
                    k += 1;
                }
                for _ in k..n {
                    body.extend_from_slice(&[0, 0, 0, 0]);
                }
            }
            (format!("<U{}", n), shape, body)
        }
    };
    let shape_txt = match shape.len() {
        0 => "()".to_string(),
        1 => format!("({},)", shape[0]),
        _ => format!("({})", shape.iter().map(|d| d.to_string()).collect::<Vec<_>>().join(", ")),
    };
    let mut header = format!("{{'descr': '{}', 'fortran_order': False, 'shape': {}, }}", descr, shape_txt);
    let total = 10 + header.len() + 1;
    let pad = (64 - total % 64) % 64;
    for _ in 0..pad {
        header.push(' ');
    }
    header.push('\n');
    let mut out = Vec::with_capacity(10 + header.len() + body.len());
    out.extend_from_slice(b"\x93NUMPY\x01\x00");
    out.extend_from_slice(&(header.len() as u16).to_le_bytes());
    out.extend_from_slice(header.as_bytes());
    out.extend_from_slice(&body);
    out
}

/// Write an NPZ archive (stored members, `<key>.npy`), as `numpy.savez`.
pub fn write_npz(arrays: &[(&str, NpyData)]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut central = Vec::new();
    for (key, arr) in arrays {
        let name = format!("{}.npy", key);
        let data = npy_bytes(arr);
        let crc = crc32(&data);
        let off = out.len() as u32;
        let sz = data.len() as u32;
        // local file header
        out.extend_from_slice(&0x0403_4b50u32.to_le_bytes());
        out.extend_from_slice(&[20, 0, 0, 0, 0, 0, 0, 0, 0x21, 0]); // version, flags, method 0, time, date
        out.extend_from_slice(&crc.to_le_bytes());
        out.extend_from_slice(&sz.to_le_bytes());
        out.extend_from_slice(&sz.to_le_bytes());
        out.extend_from_slice(&(name.len() as u16).to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(name.as_bytes());
        out.extend_from_slice(&data);
        // central directory entry
        central.extend_from_slice(&0x0201_4b50u32.to_le_bytes());
        central.extend_from_slice(&[20, 0, 20, 0, 0, 0, 0, 0, 0, 0, 0x21, 0]);
        central.extend_from_slice(&crc.to_le_bytes());
        central.extend_from_slice(&sz.to_le_bytes());
        central.extend_from_slice(&sz.to_le_bytes());
        central.extend_from_slice(&(name.len() as u16).to_le_bytes());
        central.extend_from_slice(&[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]); // extra, comment, disk, int attr, ext attr
        central.extend_from_slice(&off.to_le_bytes());
        central.extend_from_slice(name.as_bytes());
    }
    let cd_off = out.len() as u32;
    let cd_len = central.len() as u32;
    out.extend_from_slice(&central);
    out.extend_from_slice(&0x0605_4b50u32.to_le_bytes());
    out.extend_from_slice(&[0, 0, 0, 0]);
    out.extend_from_slice(&(arrays.len() as u16).to_le_bytes());
    out.extend_from_slice(&(arrays.len() as u16).to_le_bytes());
    out.extend_from_slice(&cd_len.to_le_bytes());
    out.extend_from_slice(&cd_off.to_le_bytes());
    out.extend_from_slice(&[0, 0]);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn npz_roundtrip() {
        let z = write_npz(&[
            ("a", NpyData::F32 { shape: vec![2, 2], data: vec![1.0, -2.5, 3.0, 0.0] }),
            ("s", NpyData::Str { shape: vec![], data: vec!["héllo".into()] }),
            ("i", NpyData::I64 { shape: vec![], data: vec![-1] }),
        ]);
        let f = read_npz(&z).unwrap();
        assert_eq!(f.files, ["a", "s", "i"]);
        let a = f.get("a").unwrap();
        assert_eq!(a.dtype, "float32");
        assert_eq!(a.shape, [2, 2]);
        assert!(matches!(a.data[1], Cell::Num(x) if x == -2.5));
        assert!(matches!(&f.get("s").unwrap().data[0], Cell::Str(s) if s == "héllo"));
        assert!(matches!(f.get("i").unwrap().data[0], Cell::Num(x) if x == -1.0));
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    }
}
