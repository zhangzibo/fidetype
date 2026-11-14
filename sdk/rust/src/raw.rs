//! Raw readers: read a stream WITHOUT validation, so that the checks can see
//! every problem (port of `fidetype.conformance.io`).

use alloc::string::{String, ToString};
use alloc::vec;
use alloc::vec::Vec;
use alloc::format;

use crate::constants::{EVENT_TYPES, HEADER_KNOWN, JSONL_HEADER_REQUIRED, NPZ_KNOWN, NPZ_NO_BLANK, NPZ_REQUIRED};
use crate::error::Error;
use crate::json::{decode_utf8, is_blank, num_text, parse_json, py_lines, repr, str_list, Map, Value};
use crate::npz::{read_npz, Cell, NpyArray, NpyError, NpyKind};

/// An n-dimensional float64 array (row-major).
#[derive(Debug, Clone)]
pub struct NdArray {
    pub shape: Vec<usize>,
    pub data: Vec<f64>,
}

/// A problem found while reading, reported by the check with the same id.
#[derive(Debug, Clone)]
pub struct Issue {
    pub check_id: &'static str,
    pub clause: &'static str,
    pub message: String,
}

/// A sparse frame (spec 3.3) as read.
#[derive(Debug, Clone)]
pub struct SparseFrameInfo {
    pub line: usize,
    /// The rest mass and the top-k values, when the frame was well formed.
    pub rest: Option<f64>,
    pub vals: Option<Vec<f64>>,
}

/// The serialisation of a stream file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Format {
    Npz,
    Jsonl,
}

/// A stream as read, before any check.
#[derive(Debug, Clone)]
pub struct RawStream {
    pub format: Format,
    /// The header fields that were present (a missing field is absent).
    pub header: Map,
    /// `meta` (or NPZ `meta_json`) was present but could not be parsed.
    pub meta_unparseable: bool,
    pub log_probs: Option<NdArray>,
    pub frame_times: Option<NdArray>,
    pub issues: Vec<Issue>,
    /// Non-frame JSON Lines events in file order, each with `_line`.
    pub events: Vec<Map>,
    pub sparse_frames: Vec<SparseFrameInfo>,
    pub npz_keys: Vec<String>,
    pub npz_dtypes: Vec<(String, String)>,
    pub unknown_keys: Vec<String>,
    pub ignored_events: usize,
    pub has_end: bool,
    pub lines_after_end: usize,
    pub parsed: bool,
    pub vocab_type_defaulted: bool,
    pub meta_defaulted: bool,
}

impl RawStream {
    fn empty(format: Format) -> Self {
        RawStream {
            format,
            header: Map::new(),
            meta_unparseable: false,
            log_probs: None,
            frame_times: None,
            issues: Vec::new(),
            events: Vec::new(),
            sparse_frames: Vec::new(),
            npz_keys: Vec::new(),
            npz_dtypes: Vec::new(),
            unknown_keys: Vec::new(),
            ignored_events: 0,
            has_end: false,
            lines_after_end: 0,
            parsed: true,
            vocab_type_defaulted: false,
            meta_defaulted: false,
        }
    }
    fn issue(&mut self, check_id: &'static str, clause: &'static str, message: String) {
        self.issues.push(Issue { check_id, clause, message });
    }
}

// --- JSON Lines (spec 6.2) -----------------------------------------------------------

/// One JSON log-probability: a number, or null for -inf (6.2 rule 3).
pub(crate) fn lp_value(x: &Value) -> Result<f64, String> {
    match x {
        Value::Null => Ok(f64::NEG_INFINITY),
        Value::Num(v, _) => Ok(*v),
        other => Err(format!("{} is not a number or null", repr(other))),
    }
}

/// Read a JSON Lines stream (spec 6.2) without validation.
pub fn read_jsonl_raw(bytes: &[u8]) -> RawStream {
    let mut raw = RawStream::empty(Format::Jsonl);
    let text = match decode_utf8(bytes) {
        Ok(t) => t,
        Err(e) => {
            raw.parsed = false;
            raw.issue("NTS-PARSE", "6.2", format!("cannot read the file as UTF-8: {}", e.message));
            return raw;
        }
    };
    let mut objs: Vec<(usize, Value)> = Vec::new();
    for (k, line) in py_lines(text).into_iter().enumerate() {
        if is_blank(line) {
            continue;
        }
        match parse_json(line) {
            Ok(v) => objs.push((k + 1, v)),
            Err(e) => {
                raw.parsed = false;
                raw.issue("NTS-PARSE", "6.2", format!("line {} is not a JSON value: {}", k + 1, e.message));
            }
        }
    }
    if !raw.parsed {
        return raw;
    }
    if objs.is_empty() {
        raw.parsed = false;
        raw.issue("NTS-JSONL-HEADER", "6.2.1", "the file has no header line".to_string());
        return raw;
    }
    let mut it = objs.into_iter();
    let head = match it.next() {
        Some((_, Value::Obj(m))) if matches!(m.get("type"), Value::Str(s) if s == "header") => m,
        _ => {
            raw.parsed = false;
            raw.issue("NTS-JSONL-HEADER", "6.2.1", "line 1 must be an object with \"type\": \"header\"".to_string());
            return raw;
        }
    };
    let missing: Vec<&str> = JSONL_HEADER_REQUIRED.iter().copied().filter(|k| !head.has(k)).collect();
    if !missing.is_empty() {
        raw.issue("NTS-JSONL-HEADER", "6.2.1", format!("the header lacks required fields {}", repr(&str_list(&missing))));
    }
    raw.unknown_keys = head.keys().filter(|k| !HEADER_KNOWN.contains(k)).map(|k| k.to_string()).collect();
    if !head.has("meta") {
        raw.meta_defaulted = true;
    }
    let v_len: Option<usize> = head.get("vocab").as_arr().map(|a| a.len());
    raw.header = head;
    let mut rows: Vec<Vec<f64>> = Vec::new();
    let mut times: Vec<f64> = Vec::new();
    let mut stackable = true;
    for (n, obj) in it {
        if raw.has_end {
            raw.lines_after_end += 1;
            continue;
        }
        let mut obj = match obj {
            Value::Obj(m) if m.get("type").is_str() => m,
            _ => {
                raw.issue("NTS-JSONL-FRAME", "6.2", format!("line {} is not an event object with a string type", n));
                stackable = false;
                continue;
            }
        };
        let typ = obj.get("type").as_str().unwrap_or("").to_string();
        if typ == "end" {
            raw.has_end = true;
            continue;
        }
        if typ == "header" {
            raw.issue("NTS-JSONL-HEADER", "6.2.1", format!("line {}: a second header", n));
            continue;
        }
        if !EVENT_TYPES.contains(&typ.as_str()) {
            raw.ignored_events += 1; // 6.2 rule 5
            continue;
        }
        if typ != "frame" {
            obj.insert("_line", Value::int(n as f64));
            raw.events.push(obj);
            continue;
        }
        let t = match obj.get_opt("t") {
            Some(Value::Num(t, _)) => *t,
            _ => {
                raw.issue("NTS-JSONL-FRAME", "6.2.2", format!("line {}: frame without a numeric t", n));
                stackable = false;
                continue;
            }
        };
        let row: Result<Option<Vec<f64>>, String> = if obj.has("log_probs") {
            match obj.get("log_probs") {
                Value::Arr(a) => a.iter().map(lp_value).collect::<Result<Vec<f64>, String>>().map(Some),
                _ => Err("log_probs is not a list".to_string()),
            }
        } else if obj.has("top_ids") || obj.has("top_log_probs") {
            sparse_row(&obj, v_len, n, &mut raw)
        } else {
            Err("frame has neither log_probs nor top_ids/top_log_probs".to_string())
        };
        match row {
            Err(e) => {
                raw.issue("NTS-JSONL-FRAME", "6.2.2", format!("line {}: {}", n, e));
                stackable = false;
            }
            Ok(None) => stackable = false,
            Ok(Some(r)) => {
                rows.push(r);
                times.push(t);
            }
        }
    }
    if stackable {
        if rows.is_empty() {
            raw.log_probs = Some(NdArray { shape: vec![0, v_len.unwrap_or(0)], data: Vec::new() });
        } else if rows.iter().all(|r| r.len() == rows[0].len()) {
            let w = rows[0].len();
            let data: Vec<f64> = rows.iter().flatten().copied().collect();
            raw.log_probs = Some(NdArray { shape: vec![rows.len(), w], data });
        } else {
            raw.issue("NTS-V-MATCH", "5.1.2", "frames have different numbers of log-probabilities".to_string());
        }
        raw.frame_times = Some(NdArray { shape: vec![times.len()], data: times });
    }
    raw
}

fn sparse_row(obj: &Map, v: Option<usize>, n: usize, raw: &mut RawStream) -> Result<Option<Vec<f64>>, String> {
    let idx = raw.sparse_frames.len();
    raw.sparse_frames.push(SparseFrameInfo { line: n, rest: None, vals: None });
    let (ids, vals) = match (obj.get("top_ids"), obj.get("top_log_probs")) {
        (Value::Arr(i), Value::Arr(v)) if i.len() == v.len() => (i, v),
        _ => return Err("sparse frame needs top_ids and top_log_probs lists of the same length".to_string()),
    };
    let v = match v {
        Some(v) => v,
        None => return Ok(None),
    };
    let ok_ids = ids.iter().all(|x| x.is_int() && x.as_f64().map_or(false, |x| x >= 0.0 && x < v as f64));
    let unique = ok_ids && {
        let mut s: Vec<f64> = ids.iter().filter_map(|x| x.as_f64()).collect();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap_or(core::cmp::Ordering::Equal));
        s.windows(2).all(|w| w[0] != w[1])
    };
    if !ok_ids || !unique {
        return Err("top_ids must be unique integers in 0..V-1".to_string());
    }
    let lv: Vec<f64> = vals.iter().map(lp_value).collect::<Result<_, _>>()?;
    let r = lp_value(obj.get("rest_log_prob"))?;
    let mut row = vec![f64::NEG_INFINITY; v];
    let k = ids.len();
    if v > k && r > f64::NEG_INFINITY {
        let fill = r - libm::log((v - k) as f64); // 3.3: spread the rest mass uniformly
        row.iter_mut().for_each(|x| *x = fill);
    }
    for (j, id) in ids.iter().enumerate() {
        row[id.as_f64().unwrap_or(0.0) as usize] = lv[j];
    }
    raw.sparse_frames[idx].rest = Some(r);
    raw.sparse_frames[idx].vals = Some(lv);
    Ok(Some(row))
}

// --- NPZ (spec 6.1) --------------------------------------------------------------

fn cell_value(c: &Cell, kind: NpyKind) -> Value {
    match c {
        Cell::Num(x) => Value::Num(*x, kind == NpyKind::F),
        Cell::Bool(b) => Value::Bool(*b),
        Cell::Str(s) => Value::Str(s.clone()),
    }
}

/// NumPy `tolist()`.
fn nested(a: &NpyArray) -> Value {
    if a.shape.is_empty() {
        return a.data.first().map(|c| cell_value(c, a.kind)).unwrap_or(Value::Null);
    }
    fn build(a: &NpyArray, dim: usize, off: &mut usize) -> Value {
        let mut out = Vec::with_capacity(a.shape[dim]);
        for _ in 0..a.shape[dim] {
            if dim == a.shape.len() - 1 {
                out.push(cell_value(&a.data[*off], a.kind));
                *off += 1;
            } else {
                out.push(build(a, dim + 1, off));
            }
        }
        Value::Arr(out)
    }
    let mut off = 0;
    build(a, 0, &mut off)
}

fn is_numeric(a: &NpyArray) -> bool {
    matches!(a.kind, NpyKind::F | NpyKind::I | NpyKind::U)
}

fn nd(a: &NpyArray) -> NdArray {
    NdArray {
        shape: a.shape.clone(),
        data: a.data.iter().map(|c| if let Cell::Num(x) = c { *x } else { f64::NAN }).collect(),
    }
}

/// Read an NPZ stream (spec 6.1) without validation.
pub fn read_npz_raw(bytes: &[u8]) -> RawStream {
    let mut raw = RawStream::empty(Format::Npz);
    let z = match read_npz(bytes) {
        Ok(z) => z,
        Err(e) => {
            raw.parsed = false;
            raw.issue("NTS-PARSE", "6.1", format!("cannot load the NPZ with allow_pickle=False: {}", e.message()));
            return raw;
        }
    };
    raw.npz_keys = z.files.clone();
    let mut arrays: Vec<(String, NpyArray)> = Vec::new();
    let mut seen: Vec<&str> = Vec::new();
    for k in &z.files {
        if seen.contains(&k.as_str()) {
            continue;
        }
        seen.push(k);
        match z.get(k) {
            Ok(a) => arrays.push((k.clone(), a)),
            Err(NpyError::Pickle(m)) => {
                raw.issue("NTS-PARSE", "6.1", format!("key '{}' needs pickle to load: {}", k, m));
                raw.parsed = false;
            }
            Err(NpyError::Bad(m)) => {
                // A corrupt member: NumPy raises outside its pickle path; the file does not load.
                raw.issue("NTS-PARSE", "6.1", format!("key '{}' cannot be loaded: {}", k, m));
                raw.parsed = false;
            }
        }
    }
    raw.npz_dtypes = arrays.iter().map(|(k, a)| (k.clone(), a.dtype.clone())).collect();
    raw.unknown_keys = z.files.iter().filter(|k| !NPZ_KNOWN.contains(&k.as_str())).cloned().collect();
    let get = |k: &str| arrays.iter().find(|(kk, _)| kk == k).map(|(_, a)| a);
    let missing: Vec<&str> = NPZ_REQUIRED.iter().copied().filter(|k| get(k).is_none()).collect();
    if !missing.is_empty() {
        raw.issue("NTS-NPZ-KEYS", "6.1", format!("required NPZ keys are missing: {}", repr(&str_list(&missing))));
    }
    let mut h = Map::new();
    if let Some(a) = get("version") {
        h.insert("spec_version", nested(a));
    }
    if let Some(a) = get("vocab") {
        h.insert("vocab", nested(a));
    }
    // 6.1: a reader MUST use "char" if vocab_type is absent.
    if let Some(a) = get("vocab_type") {
        h.insert("vocab_type", nested(a));
    } else {
        h.insert("vocab_type", Value::str("char"));
        raw.vocab_type_defaulted = true;
    }
    if let Some(b) = get("blank_id") {
        if b.shape.is_empty() && matches!(b.kind, NpyKind::I | NpyKind::U) {
            let v = match b.data.first() {
                Some(Cell::Num(x)) => *x,
                _ => f64::NAN,
            };
            h.insert("blank_id", if v == NPZ_NO_BLANK { Value::Null } else { Value::int(v) });
        } else {
            h.insert("blank_id", nested(b));
        }
    }
    if let Some(a) = get("source") {
        h.insert("source", nested(a));
    }
    if let Some(a) = get("meta_json") {
        let txt = match nested(a) {
            Value::Str(s) => s,
            Value::Bool(b) => (if b { "True" } else { "False" }).to_string(),
            Value::Num(x, _) => num_text(x),
            other => repr(&other),
        };
        match parse_json(&txt) {
            Ok(m) => h.insert("meta", m),
            Err(e) => {
                raw.issue("NTS-META-JSON", "4.1", format!("meta_json is not valid JSON: {}", e.message));
                h.insert("meta", Value::Null);
                raw.meta_unparseable = true;
            }
        }
    }
    for k in ["frame_period", "latency"] {
        if let Some(a) = get(k) {
            h.insert(k, nested(a));
        }
    }
    if let Some(lp) = get("log_probs") {
        if is_numeric(lp) {
            raw.log_probs = Some(nd(lp));
        } else {
            raw.issue("NTS-LP-2D", "3.1", format!("log_probs has a non-numeric dtype {}", lp.dtype));
        }
    }
    if let Some(ft) = get("frame_times") {
        if is_numeric(ft) {
            raw.frame_times = Some(nd(ft));
        } else {
            raw.issue("NTS-FT-SHAPE", "3.1", format!("frame_times has a non-numeric dtype {}", ft.dtype));
        }
    }
    raw.header = h;
    raw
}

/// Read a stream file by its name: `.npz`, or `.jsonl` / `.ndjson` / `.json`.
pub fn read_raw(name: &str, bytes: &[u8]) -> Result<RawStream, Error> {
    let lower = name.to_lowercase();
    let suf = lower.rfind('.').map(|i| &lower[i..]).unwrap_or("");
    match suf {
        ".npz" => Ok(read_npz_raw(bytes)),
        ".jsonl" | ".ndjson" | ".json" => Ok(read_jsonl_raw(bytes)),
        _ => Err(Error::value(format!("unknown stream file type '{}' (use .npz or .jsonl)", suf))),
    }
}
