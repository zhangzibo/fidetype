//! The checks of the NeuralTextStream v0.1 conformance suite (port of
//! `fidetype.conformance.checks`) and the reference consumer [`load_stream`]
//! (port of `fidetype.conformance.io.load_stream`).
//!
//! Levels: `core` (MUST rules; a consumer MUST reject a stream that fails
//! one), `trust-ready`, `provenance`, and `advisory` (a warning only).

use alloc::collections::BTreeSet;
use alloc::string::{String, ToString};
use alloc::vec;
use alloc::vec::Vec;
use alloc::format;

use crate::constants::{CLOCK_DOMAINS, MODALITIES, NORM_TOL, SCORE_SEMANTICS, SPEC_VERSION, SQ_UNITS, VOCAB, VOCAB_TYPES};
use crate::error::Error;
use crate::json::{num_text, py_eq, py_in, py_space, py_split, py_strip, repr, str_in, str_list, Map, Value};
use crate::raw::{read_raw, Format, NdArray, RawStream};

/// A check level.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Level {
    Core,
    TrustReady,
    Provenance,
    Advisory,
}

impl Level {
    pub fn name(self) -> &'static str {
        match self {
            Level::Core => "core",
            Level::TrustReady => "trust-ready",
            Level::Provenance => "provenance",
            Level::Advisory => "advisory",
        }
    }
    pub fn parse(s: &str) -> Option<Level> {
        match s {
            "core" => Some(Level::Core),
            "trust-ready" => Some(Level::TrustReady),
            "provenance" => Some(Level::Provenance),
            "advisory" => Some(Level::Advisory),
            _ => None,
        }
    }
    fn rank(self) -> usize {
        match self {
            Level::Core => 0,
            Level::TrustReady => 1,
            Level::Provenance => 2,
            Level::Advisory => 3,
        }
    }
}

/// The three levels a stream can reach, in order.
pub const LEVELS: [Level; 3] = [Level::Core, Level::TrustReady, Level::Provenance];

/// The result status of one check.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Pass,
    Fail,
    Skip,
}

impl Status {
    pub fn name(self) -> &'static str {
        match self {
            Status::Pass => "pass",
            Status::Fail => "fail",
            Status::Skip => "skip",
        }
    }
}

/// The result of one check.
#[derive(Debug, Clone)]
pub struct CheckResult {
    pub id: String,
    pub level: Level,
    pub keyword: String,
    pub clause: String,
    pub title: String,
    pub status: Status,
    pub message: String,
    pub heuristic: bool,
}

impl CheckResult {
    /// The result as a JSON object (the field names of the Python report).
    pub fn to_value(&self) -> Value {
        Value::Obj(Map::from_pairs([
            ("id", Value::str(&self.id)),
            ("level", Value::str(self.level.name())),
            ("keyword", Value::str(&self.keyword)),
            ("clause", Value::str(&self.clause)),
            ("title", Value::str(&self.title)),
            ("status", Value::str(self.status.name())),
            ("message", Value::str(&self.message)),
            ("heuristic", Value::Bool(self.heuristic)),
        ]))
    }
}

type Out = (Status, String);
type Fn = fn(&RawStream) -> Out;

struct CheckDef {
    id: &'static str,
    level: Level,
    keyword: &'static str,
    clause: &'static str,
    title: &'static str,
    f: Fn,
    heuristic: bool,
    /// None: both formats.
    only: Option<Format>,
}

fn ok(m: &str) -> Out {
    (Status::Pass, m.to_string())
}
fn ok_s(m: String) -> Out {
    (Status::Pass, m)
}
fn bad(m: String) -> Out {
    (Status::Fail, m)
}
fn skip(m: &str) -> Out {
    (Status::Skip, m.to_string())
}

/// True if a failure of a check at `check_level` blocks `level`.
pub fn blocks(check_level: Level, level: Level) -> bool {
    if check_level == Level::Advisory {
        return false;
    }
    check_level.rank() <= level.rank()
}

// --- helpers -----------------------------------------------------------------------------

fn vocab_of(raw: &RawStream) -> Option<&Vec<Value>> {
    raw.header.get("vocab").as_arr()
}
static EMPTY_MAP: Map = Map::new();
fn meta_value(raw: &RawStream) -> Option<&Value> {
    // None = absent (the default {}).
    raw.header.get_opt("meta")
}
fn meta_of(raw: &RawStream) -> Option<&Map> {
    if raw.meta_unparseable {
        return None;
    }
    match meta_value(raw) {
        None => Some(&EMPTY_MAP),
        Some(Value::Obj(m)) => Some(m),
        _ => None,
    }
}
fn meta_or_empty(raw: &RawStream) -> &Map {
    meta_of(raw).unwrap_or(&EMPTY_MAP)
}
fn lp2d(raw: &RawStream) -> Option<&NdArray> {
    raw.log_probs.as_ref().filter(|a| a.shape.len() == 2)
}
fn issues(raw: &RawStream, id: &str) -> Option<Out> {
    let msgs: Vec<&str> = raw.issues.iter().filter(|i| i.check_id == id).map(|i| i.message.as_str()).collect();
    if msgs.is_empty() {
        None
    } else {
        Some(bad(msgs.join("; ")))
    }
}
fn hget<'a>(raw: &'a RawStream, k: &str) -> &'a Value {
    raw.header.get(k)
}

/// (dotted key path, value) for every leaf of a JSON value.
fn walk<'a>(obj: &'a Value, prefix: &str, out: &mut Vec<(String, &'a Value)>) {
    match obj {
        Value::Obj(m) => {
            for (k, v) in m.iter() {
                let p = if prefix.is_empty() { k.to_string() } else { format!("{}.{}", prefix, k) };
                out.push((p.clone(), v));
                walk(v, &p, out);
            }
        }
        Value::Arr(a) => {
            for (i, v) in a.iter().enumerate() {
                walk(v, &format!("{}[{}]", prefix, i), out);
            }
        }
        _ => {}
    }
}
fn walk_map(m: &Map) -> Vec<(String, &Value)> {
    let mut out = Vec::new();
    for (k, v) in m.iter() {
        out.push((k.to_string(), v));
        walk(v, k, &mut out);
    }
    out
}
fn segs(p: &str) -> Vec<String> {
    p.split(|c| c == '.' || c == '[').map(|s| s.to_lowercase()).collect()
}
fn last_seg(p: &str) -> String {
    segs(p).pop().unwrap_or_default()
}

// --- small pattern matchers (the regular expressions of the Python reference) ---------------

/// Python `re.match(...$)`: also accepts one trailing newline.
fn py_match(f: fn(&str) -> bool, s: &str) -> bool {
    f(s) || s.strip_suffix('\n').map_or(false, f)
}
fn is_sha256(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn is_bcp47(s: &str) -> bool {
    let mut parts = s.split('-');
    let first = parts.next().unwrap_or("");
    if !(2..=8).contains(&first.len()) || !first.bytes().all(|b| b.is_ascii_alphabetic()) {
        return false;
    }
    parts.all(|p| (1..=8).contains(&p.len()) && p.bytes().all(|b| b.is_ascii_alphanumeric()))
}
fn is_pseudo_id(s: &str) -> bool {
    let b = s.as_bytes();
    !b.is_empty()
        && b.len() <= 64
        && b[0].is_ascii_alphanumeric()
        && b[1..].iter().all(|&c| c.is_ascii_alphanumeric() || matches!(c, b'.' | b'_' | b':' | b'-'))
}
fn has_email(s: &str) -> bool {
    let local = |c: char| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '%' | '+' | '-');
    let dom = |c: char| c.is_ascii_alphanumeric() || matches!(c, '.' | '-');
    let chars: Vec<char> = s.chars().collect();
    for (i, &c) in chars.iter().enumerate() {
        if c != '@' || i == 0 || !local(chars[i - 1]) {
            continue;
        }
        let run: Vec<char> = chars[i + 1..].iter().copied().take_while(|&c| dom(c)).collect();
        for j in 1..run.len() {
            if run[j] == '.' && j + 2 < run.len() && run[j + 1].is_ascii_alphabetic() && run[j + 2].is_ascii_alphabetic() {
                return true;
            }
        }
    }
    false
}
fn py_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}
fn is_w3c_code(s: &str) -> bool {
    const LIT: &[&str] = &[
        "Space", "Enter", "Backspace", "Tab", "Escape", "CapsLock", "Minus", "Equal", "BracketLeft", "BracketRight",
        "Backslash", "Semicolon", "Quote", "Backquote", "Comma", "Period", "Slash", "Delete", "Home", "End", "PageUp",
        "PageDown", "Insert", "IntlBackslash", "ContextMenu", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
    ];
    if LIT.contains(&s) {
        return true;
    }
    let b = s.as_bytes();
    if let Some(r) = s.strip_prefix("Key") {
        return r.len() == 1 && r.as_bytes()[0].is_ascii_uppercase();
    }
    if let Some(r) = s.strip_prefix("Digit") {
        return r.len() == 1 && r.as_bytes()[0].is_ascii_digit();
    }
    if let Some(r) = s.strip_prefix("Numpad") {
        return !r.is_empty() && r.chars().all(py_word);
    }
    if b.first() == Some(&b'F') && (2..=3).contains(&b.len()) && b[1..].iter().all(|c| c.is_ascii_digit()) {
        return true;
    }
    for m in ["Shift", "Control", "Alt", "Meta"] {
        if let Some(r) = s.strip_prefix(m) {
            return r == "Left" || r == "Right";
        }
    }
    false
}

// --- defined meta keys (spec 4.2) ------------------------------------------------------

type TypeFn = fn(&Value) -> Option<String>;

fn t_str(v: &Value) -> Option<String> {
    if matches!(v, Value::Str(s) if !s.is_empty()) { None } else { Some("a non-empty string".into()) }
}
fn t_bool(v: &Value) -> Option<String> {
    if matches!(v, Value::Bool(_)) { None } else { Some("a boolean".into()) }
}
fn t_modality(v: &Value) -> Option<String> {
    if str_in(v, MODALITIES) { None } else { Some(format!("one of {}", repr(&str_list(MODALITIES)))) }
}
fn t_int_ge1(v: &Value) -> Option<String> {
    if v.is_int() && v.as_f64().unwrap_or(0.0) >= 1.0 { None } else { Some("an integer >= 1".into()) }
}
fn t_nonneg(v: &Value) -> Option<String> {
    if matches!(v, Value::Num(x, _) if x.is_finite() && *x >= 0.0) { None } else { Some("a finite number >= 0".into()) }
}
fn t_sha(v: &Value) -> Option<String> {
    if matches!(v, Value::Str(s) if is_sha256(s)) { None } else { Some("64 lowercase hex characters (SHA-256)".into()) }
}
fn t_lang(v: &Value) -> Option<String> {
    if matches!(v, Value::Str(s) if py_match(is_bcp47, s)) { None } else { Some("a BCP 47 language tag".into()) }
}

/// The meta keys that spec 4.2 defines, with their type rule.
pub const DEFINED_KEYS: &[(&str, TypeFn)] = &[
    ("device.modality", t_modality),
    ("device.vendor", t_str),
    ("device.model", t_str),
    ("device.channel_count", t_int_ge1),
    ("device.invasive", t_bool),
    ("device.regulatory_status", t_str),
    ("decoder.name", t_str),
    ("decoder.version", t_str),
    ("decoder.causal", t_bool),
    ("decoder.lookahead_s", t_nonneg),
    ("decoder.calibration_id", t_str),
    ("decoder.calibration_method", t_str),
    ("decoder.weights_sha256", t_sha),
    ("adapter.name", t_str),
    ("adapter.version", t_str),
    ("stream.id", t_str),
    ("lm.name", t_str),
    ("user.personalized", t_bool),
    ("session.id", t_str),
    ("subject.id", t_str),
    ("language", t_lang),
    ("calibration.applied", t_bool),
    ("data.derived", t_bool),
    ("consent.ref", t_str),
];
fn defined(k: &str) -> bool {
    DEFINED_KEYS.iter().any(|(d, _)| *d == k)
}
fn defined_namespace(ns: &str) -> bool {
    DEFINED_KEYS.iter().any(|(d, _)| d.contains('.') && d.split('.').next() == Some(ns))
}
const LEAK_KEY_NAMES: &[&str] = &[
    "target_text", "typed_text", "truth", "ground_truth", "groundtruth", "label", "labels", "transcript", "transcription",
    "cue_sentence", "cue_text", "sentence", "reference_text", "target", "answer", "true_text", "gold",
];
const PII_KEY_NAMES: &[&str] = &[
    "name", "full_name", "first_name", "last_name", "email", "e_mail", "dob", "date_of_birth", "birthdate", "birth_date",
    "address", "phone", "phone_number", "mrn", "medical_record_number", "ssn",
];
const PERSON_NS: &[&str] = &["subject", "participant", "user", "patient", "person", "operator"];
const FREE_TEXT_KEY_NAMES: &[&str] = &["note", "notes", "comment", "comments", "remarks", "description"];
const ARPABET: &[&str] = &[
    "AA", "AE", "AH", "AO", "AW", "AY", "B", "CH", "D", "DH", "EH", "ER", "EY", "F", "G", "HH", "IH", "IY", "JH", "K", "L",
    "M", "N", "NG", "OW", "OY", "P", "R", "S", "SH", "T", "TH", "UH", "UW", "V", "W", "Y", "Z", "ZH",
];
const PHONEME_MARKERS: &[&str] = &["SIL", "SP", "sil", "sp", "|", "<sil>", "<sp>"];

fn fmt4(x: f64) -> String {
    if x.is_finite() { format!("{:.4}", x) } else { num_text(x) }
}

// --- the checks ------------------------------------------------------------------------------

fn c_parse(raw: &RawStream) -> Out {
    issues(raw, "NTS-PARSE").unwrap_or_else(|| ok(""))
}
fn c_npz_keys(raw: &RawStream) -> Out {
    issues(raw, "NTS-NPZ-KEYS").unwrap_or_else(|| ok(""))
}
fn c_npz_dtype(raw: &RawStream) -> Out {
    let want = [("log_probs", "float32"), ("frame_times", "float64"), ("blank_id", "int64"), ("frame_period", "float64"), ("latency", "float64")];
    let diffs: Vec<String> = want
        .iter()
        .filter_map(|(k, d)| {
            raw.npz_dtypes.iter().find(|(kk, _)| kk == k).filter(|(_, dt)| dt != d).map(|(_, dt)| format!("{} is {}, table says {}", k, dt, d))
        })
        .collect();
    if diffs.is_empty() { ok("") } else { bad(diffs.join("; ")) }
}
fn c_unknown_keys(raw: &RawStream) -> Out {
    if raw.unknown_keys.is_empty() {
        ok("")
    } else {
        let v: Vec<&str> = raw.unknown_keys.iter().map(|s| s.as_str()).collect();
        ok_s(format!("unknown keys (a consumer ignores them): {}", repr(&str_list(&v))))
    }
}
fn c_jsonl_header(raw: &RawStream) -> Out {
    issues(raw, "NTS-JSONL-HEADER").unwrap_or_else(|| ok(""))
}
fn c_jsonl_frame(raw: &RawStream) -> Out {
    issues(raw, "NTS-JSONL-FRAME").unwrap_or_else(|| ok(""))
}
fn c_jsonl_end(raw: &RawStream) -> Out {
    if raw.lines_after_end > 0 {
        return bad(format!("{} line(s) after the end marker (ignored; see ambiguity A5)", raw.lines_after_end));
    }
    ok(if raw.has_end { "end marker present" } else { "no end marker (allowed, 6.2.6)" })
}
fn c_version(raw: &RawStream) -> Out {
    match raw.header.get_opt("spec_version") {
        None => skip("no spec_version (reported by the serialisation check)"),
        Some(Value::Str(s)) if s == SPEC_VERSION => ok(""),
        Some(v) => bad(format!("spec_version {} is not supported (this suite supports '{}')", repr(v), SPEC_VERSION)),
    }
}
fn c_lp_2d(raw: &RawStream) -> Out {
    if let Some(r) = issues(raw, "NTS-LP-2D") {
        return r;
    }
    match &raw.log_probs {
        None => skip("no log_probs"),
        Some(a) if a.shape.len() == 2 => ok(""),
        Some(a) => bad(format!("log_probs has shape {:?}", a.shape)),
    }
}
fn c_v_match(raw: &RawStream) -> Out {
    if let Some(r) = issues(raw, "NTS-V-MATCH") {
        return r;
    }
    match (lp2d(raw), vocab_of(raw)) {
        (Some(lp), Some(v)) => {
            if lp.shape[1] == v.len() {
                ok("")
            } else {
                bad(format!("log_probs has {} columns, vocab has {} tokens", lp.shape[1], v.len()))
            }
        }
        _ => skip("no 2-D log_probs or no vocab list"),
    }
}
fn c_ft_shape(raw: &RawStream) -> Out {
    if let Some(r) = issues(raw, "NTS-FT-SHAPE") {
        return r;
    }
    match (lp2d(raw), &raw.frame_times) {
        (Some(lp), Some(ft)) => {
            if ft.shape.len() == 1 && ft.shape[0] == lp.shape[0] {
                ok("")
            } else {
                bad(format!("frame_times has shape {:?}, expected ({},)", ft.shape, lp.shape[0]))
            }
        }
        _ => skip("no log_probs or frame_times"),
    }
}
fn c_vocab_type(raw: &RawStream) -> Out {
    let vt = hget(raw, "vocab_type");
    if vt.is_null() && !raw.header.has("vocab_type") {
        return skip("no vocab_type (reported by the serialisation check)");
    }
    if str_in(vt, VOCAB_TYPES) {
        ok("")
    } else {
        bad(format!("vocab_type {} is not one of {}", repr(vt), repr(&str_list(VOCAB_TYPES))))
    }
}
fn c_vocab_str(raw: &RawStream) -> Out {
    match raw.header.get_opt("vocab") {
        None => skip("no vocab"),
        Some(Value::Arr(v)) => {
            let bad_items: Vec<usize> = v.iter().enumerate().filter(|(_, t)| !t.is_str()).map(|(i, _)| i).collect();
            if bad_items.is_empty() {
                ok("")
            } else {
                bad(format!("vocab items {:?} are not strings", &bad_items[..bad_items.len().min(5)]))
            }
        }
        Some(_) => bad("vocab is not a list".to_string()),
    }
}
fn c_vocab_unique(raw: &RawStream) -> Out {
    let v = match vocab_of(raw) {
        Some(v) => v,
        None => return skip("no vocab list"),
    };
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut dup: Vec<Value> = Vec::new();
    for t in v {
        let k = match t {
            Value::Str(s) => format!("s:{}", s),
            other => format!("j:{}", repr(other)),
        };
        if seen.contains(&k) {
            dup.push(t.clone());
        }
        seen.insert(k);
    }
    if dup.is_empty() {
        ok("")
    } else {
        dup.truncate(5);
        bad(format!("duplicate tokens {}", repr(&Value::Arr(dup))))
    }
}
fn c_blank(raw: &RawStream) -> Out {
    let b = match raw.header.get_opt("blank_id") {
        None => return skip("no blank_id (reported by the serialisation check)"),
        Some(b) => b,
    };
    if b.is_null() {
        return ok("no blank (not a CTC decoder)");
    }
    if !b.is_int() {
        return bad(format!("blank_id {} is not an integer or null", repr(b)));
    }
    let v = match vocab_of(raw) {
        Some(v) => v,
        None => return skip("no vocab list"),
    };
    let x = b.as_f64().unwrap_or(-1.0);
    if x >= 0.0 && x < v.len() as f64 {
        ok("")
    } else {
        bad(format!("blank_id {} is out of range 0..{}", num_text(x), v.len() as i64 - 1))
    }
}
fn c_source(raw: &RawStream) -> Out {
    match raw.header.get_opt("source") {
        None => ok("absent (default \"unknown\")"),
        Some(Value::Str(s)) if !s.is_empty() => ok(""),
        Some(s) => bad(format!("source {} is not a non-empty string", repr(s))),
    }
}
fn c_meta_object(raw: &RawStream) -> Out {
    if raw.meta_unparseable {
        return skip("meta is not parseable (reported by NTS-META-JSON)");
    }
    match meta_value(raw) {
        None | Some(Value::Obj(_)) => ok(""),
        Some(_) => bad("meta is not an object".to_string()),
    }
}
fn c_meta_json(raw: &RawStream) -> Out {
    if let Some(r) = issues(raw, "NTS-META-JSON") {
        return r;
    }
    if let Some(m) = meta_value(raw) {
        // Python json.dumps(allow_nan=False): infinity (from a 1e400 literal) is not JSON.
        let mut all = Vec::new();
        walk(m, "", &mut all);
        if all.iter().any(|(_, v)| matches!(v, Value::Num(x, _) if !x.is_finite())) || matches!(m, Value::Num(x, _) if !x.is_finite()) {
            return bad("meta is not pure JSON: out of range float".to_string());
        }
    }
    ok("")
}
fn c_lp_finite(raw: &RawStream) -> Out {
    let lp = match lp2d(raw) {
        Some(lp) => lp,
        None => return skip("no 2-D log_probs"),
    };
    let n_nan = lp.data.iter().filter(|x| x.is_nan()).count();
    let n_pinf = lp.data.iter().filter(|x| **x == f64::INFINITY).count();
    if n_nan > 0 || n_pinf > 0 {
        bad(format!("{} NaN and {} +inf values", n_nan, n_pinf))
    } else {
        ok("")
    }
}

/// Log-sum-exp of each row (rows of only -inf give -inf), as the Python reference computes it.
pub fn row_lse(data: &[f64], t: usize, v: usize) -> Vec<f64> {
    let mut out = vec![0.0; t];
    for (r, o) in out.iter_mut().enumerate() {
        let row = &data[r * v..(r + 1) * v];
        let m = row.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        let ms = if m.is_finite() { m } else { 0.0 };
        let s: f64 = row.iter().map(|&x| libm::exp(x - ms)).sum();
        *o = libm::log(s) + ms;
    }
    out
}

fn c_norm(raw: &RawStream) -> Out {
    let lp = match lp2d(raw) {
        Some(lp) => lp,
        None => return skip("no 2-D log_probs"),
    };
    let (t, v) = (lp.shape[0], lp.shape[1]);
    if t == 0 {
        return ok("no frames");
    }
    if lp.data.iter().any(|x| x.is_nan() || *x == f64::INFINITY) {
        return skip("non-finite values (reported by NTS-LP-FINITE)");
    }
    let lse = row_lse(&lp.data, t, v);
    let bad_rows: Vec<usize> = lse.iter().enumerate().filter(|(_, x)| !(libm::fabs(**x) <= NORM_TOL)).map(|(i, _)| i).collect();
    if let Some(&b0) = bad_rows.first() {
        return bad(format!("{} row(s) not normalised; frame {} gives log-sum-exp {}", bad_rows.len(), b0, fmt4(lse[b0])));
    }
    ok("")
}
fn c_ft_finite(raw: &RawStream) -> Out {
    match &raw.frame_times {
        None => skip("no frame_times"),
        Some(ft) if ft.data.iter().all(|x| x.is_finite()) => ok(""),
        Some(_) => bad("frame_times has non-finite values".to_string()),
    }
}
fn c_ft_mono(raw: &RawStream) -> Out {
    let ft = match &raw.frame_times {
        Some(ft) if ft.shape.len() == 1 => ft,
        _ => return skip("no 1-D frame_times"),
    };
    if ft.data.len() < 2 {
        return ok("fewer than 2 frames");
    }
    for i in 0..ft.data.len() - 1 {
        if !(ft.data[i + 1] - ft.data[i] > 0.0) {
            return bad(format!(
                "frame {} time {} is not greater than frame {} time {}",
                i + 1,
                num_text(ft.data[i + 1]),
                i,
                num_text(ft.data[i])
            ));
        }
    }
    ok("")
}
fn c_frame_period(raw: &RawStream) -> Out {
    let v = hget(raw, "frame_period");
    if v.is_null() {
        return ok("absent");
    }
    if matches!(v, Value::Num(x, _) if x.is_finite() && *x > 0.0) {
        ok("")
    } else {
        bad(format!("frame_period {} is not finite and > 0", repr(v)))
    }
}
fn c_latency(raw: &RawStream) -> Out {
    let v = hget(raw, "latency");
    if v.is_null() {
        return ok("absent");
    }
    if matches!(v, Value::Num(x, _) if x.is_finite() && *x >= 0.0) {
        ok("")
    } else {
        bad(format!("latency {} is not finite and >= 0", repr(v)))
    }
}
fn c_sparse(raw: &RawStream) -> Out {
    if raw.sparse_frames.is_empty() {
        return skip("no sparse frames");
    }
    for f in &raw.sparse_frames {
        let vals = match &f.vals {
            Some(v) => v,
            None => continue, // malformed: reported by NTS-JSONL-FRAME
        };
        let mut all = vals.clone();
        all.push(f.rest.unwrap_or(f64::NEG_INFINITY));
        if all.iter().any(|x| x.is_nan() || *x == f64::INFINITY) {
            return bad(format!("line {}: NaN or +inf in a sparse frame", f.line));
        }
        let m = all.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        let lse = if m.is_finite() { libm::log(all.iter().map(|&x| libm::exp(x - m)).sum::<f64>()) + m } else { f64::NEG_INFINITY };
        if !(libm::fabs(lse) <= NORM_TOL) {
            return bad(format!("line {}: top-k plus rest log-sum-exp is {}", f.line, fmt4(lse)));
        }
    }
    ok_s(format!("{} sparse frame(s)", raw.sparse_frames.len()))
}
fn c_meta_types(raw: &RawStream) -> Out {
    let m = match meta_of(raw) {
        Some(m) => m,
        None => return skip("meta is not an object"),
    };
    let mut errs = Vec::new();
    for (k, f) in DEFINED_KEYS {
        if let Some(v) = m.get_opt(k) {
            if let Some(want) = f(v) {
                errs.push(format!("{} = {} must be {}", k, repr(v), want));
            }
        }
    }
    if errs.is_empty() { ok("") } else { bad(errs.join("; ")) }
}
fn c_meta_lookahead(raw: &RawStream) -> Out {
    let m = meta_of(raw);
    let lat = hget(raw, "latency");
    let la = match m.and_then(|m| m.get_opt("decoder.lookahead_s")) {
        Some(la) if !lat.is_null() => la,
        _ => return skip("not both present"),
    };
    match (la, lat) {
        (Value::Num(a, _), Value::Num(b, _)) => {
            if libm::fabs(a - b) <= 1e-9 {
                ok("")
            } else {
                bad(format!("decoder.lookahead_s {} != latency {}", num_text(*a), num_text(*b)))
            }
        }
        _ => skip("not numeric (reported elsewhere)"),
    }
}
fn c_namespace(raw: &RawStream) -> Out {
    let m = match meta_of(raw) {
        Some(m) => m,
        None => return skip("meta is not an object"),
    };
    let flat: Vec<&str> = m.keys().filter(|k| !k.contains('.') && !defined(k)).collect();
    let custom: Vec<&str> =
        m.keys().filter(|k| k.contains('.') && !defined(k) && defined_namespace(k.split('.').next().unwrap_or(""))).collect();
    let mut msgs = Vec::new();
    if !flat.is_empty() {
        msgs.push(format!("not namespaced: {}", repr(&str_list(&flat))));
    }
    if !custom.is_empty() {
        msgs.push(format!("custom keys inside a defined namespace: {} (see ambiguity A2)", repr(&str_list(&custom))));
    }
    if msgs.is_empty() { ok("") } else { bad(msgs.join("; ")) }
}
fn c_leak_keys(raw: &RawStream) -> Out {
    let m = match meta_of(raw) {
        Some(m) => m,
        None => return skip("meta is not an object"),
    };
    let hits: Vec<String> = walk_map(m).into_iter().map(|(p, _)| p).filter(|p| LEAK_KEY_NAMES.contains(&last_seg(p).as_str())).collect();
    if hits.is_empty() {
        ok("")
    } else {
        let v: Vec<&str> = hits.iter().map(|s| s.as_str()).collect();
        bad(format!("keys that suggest ground truth: {}", repr(&str_list(&v))))
    }
}
fn c_privacy(raw: &RawStream) -> Out {
    let m = match meta_of(raw) {
        Some(m) => m,
        None => return skip("meta is not an object"),
    };
    let mut hits: BTreeSet<String> = BTreeSet::new();
    for (p, v) in walk_map(m) {
        let parts = segs(&p);
        let last = parts.last().cloned().unwrap_or_default();
        if !defined(&p) && PII_KEY_NAMES.contains(&last.as_str()) {
            let person = parts[..parts.len() - 1].iter().any(|s| PERSON_NS.contains(&s.as_str()));
            if last != "name" || person || parts.len() == 1 {
                hits.insert(format!("key {}", p));
            }
        }
        if let Value::Str(s) = v {
            if has_email(s) {
                hits.insert(format!("e-mail address in {}", p));
            }
        }
    }
    for k in ["stream.id", "consent.ref"] {
        if let Value::Str(s) = m.get(k) {
            if s.chars().any(py_space) && py_split(py_strip(s)).len() > 3 {
                hits.insert(format!("{} looks like free text, not an opaque id", k));
            }
        }
    }
    if hits.is_empty() {
        ok("")
    } else {
        bad(hits.into_iter().collect::<Vec<_>>().join("; "))
    }
}
fn c_free_text(raw: &RawStream) -> Out {
    let m = match meta_of(raw) {
        Some(m) => m,
        None => return skip("meta is not an object"),
    };
    let hits: Vec<String> = walk_map(m).into_iter().map(|(p, _)| p).filter(|p| FREE_TEXT_KEY_NAMES.contains(&last_seg(p).as_str())).collect();
    if hits.is_empty() {
        ok("")
    } else {
        let v: Vec<&str> = hits.iter().map(|s| s.as_str()).collect();
        bad(format!("free-text keys: {}", repr(&str_list(&v))))
    }
}
fn c_vocab_id(raw: &RawStream) -> Out {
    let vid = hget(raw, "vocab_id");
    if vid.is_null() {
        return skip("no header vocab_id");
    }
    if vid.is_arr() || vid.is_obj() {
        return bad("check raised TypeError: unhashable vocab_id".to_string()); // as Python's dict lookup
    }
    if vid.as_str() != Some("char.b2q-28") {
        return skip(&format!("vocab_id {} is not in the suite's registry copy", repr(vid)));
    }
    let empty = Vec::new();
    let v = vocab_of(raw).unwrap_or(&empty);
    if v.len() == VOCAB.len() && v.iter().zip(VOCAB).all(|(t, w)| t.as_str() == Some(*w)) {
        ok("")
    } else {
        bad("vocab does not match char.b2q-28".to_string())
    }
}
fn not_blank_index(i: usize, b: &Value) -> bool {
    !py_eq(&Value::int(i as f64), b)
}
fn c_vt_char(raw: &RawStream) -> Out {
    let v = match vocab_of(raw) {
        Some(v) if hget(raw, "vocab_type").as_str() == Some("char") => v,
        _ => return skip("not a char vocabulary"),
    };
    let b = hget(raw, "blank_id");
    let bad_t: Vec<Value> = v
        .iter()
        .enumerate()
        .filter(|(i, t)| not_blank_index(*i, b) && !matches!(t, Value::Str(s) if s.chars().count() == 1))
        .map(|(_, t)| t.clone())
        .take(6)
        .collect();
    if bad_t.is_empty() { ok("") } else { bad(format!("tokens that are not one character: {}", repr(&Value::Arr(bad_t)))) }
}
fn c_vt_key(raw: &RawStream) -> Out {
    let v = match vocab_of(raw) {
        Some(v) if hget(raw, "vocab_type").as_str() == Some("key") => v,
        _ => return skip("not a key vocabulary"),
    };
    let b = hget(raw, "blank_id");
    let bad_t: Vec<Value> = v
        .iter()
        .enumerate()
        .filter(|(i, t)| not_blank_index(*i, b) && !matches!(t, Value::Str(s) if py_match(is_w3c_code, s)))
        .map(|(_, t)| t.clone())
        .take(6)
        .collect();
    if bad_t.is_empty() { ok("") } else { bad(format!("tokens that are not W3C code names: {}", repr(&Value::Arr(bad_t)))) }
}
fn c_vt_phoneme(raw: &RawStream) -> Out {
    let v = match vocab_of(raw) {
        Some(v) if hget(raw, "vocab_type").as_str() == Some("phoneme") => v,
        _ => return skip("not a phoneme vocabulary"),
    };
    let b = hget(raw, "blank_id");
    let toks: Vec<&str> = v.iter().enumerate().filter(|(i, _)| not_blank_index(*i, b)).filter_map(|(_, t)| t.as_str()).collect();
    let non_ascii = |t: &str| t.chars().any(|c| (c as u32) > 127);
    let arpa = toks.iter().all(|t| {
        let up = t.to_uppercase();
        let stripped = up.trim_end_matches(|c| c == '0' || c == '1' || c == '2');
        ARPABET.contains(&stripped) || PHONEME_MARKERS.contains(t)
    });
    let ipa = toks.iter().all(|t| {
        non_ascii(t)
            || (!t.is_empty() && t.bytes().all(|c| c.is_ascii_lowercase()) && t.chars().count() <= 3)
            || PHONEME_MARKERS.contains(t)
    });
    if arpa {
        return ok("ARPAbet");
    }
    if ipa && toks.iter().any(|t| non_ascii(t)) {
        return ok("IPA");
    }
    bad("tokens are neither ARPAbet nor IPA (an encoded phoneme set? see ambiguity A3)".to_string())
}
fn c_vt_other(raw: &RawStream) -> Out {
    if hget(raw, "vocab_type").as_str() != Some("other") {
        return skip("not vocab_type other");
    }
    let m = meta_or_empty(raw);
    if m.keys().any(|k| k.contains("vocab")) || hget(raw, "vocab_id").truthy() {
        ok("")
    } else {
        bad("no meta key describes the vocabulary".to_string())
    }
}
fn c_blank_token(raw: &RawStream) -> Out {
    let b = hget(raw, "blank_id");
    let v = match vocab_of(raw) {
        Some(v) if raw.header.get("blank_id").is_int() && b.as_f64().map_or(false, |x| x >= 0.0 && x < v.len() as f64) => v,
        _ => return skip("no valid blank"),
    };
    let t = &v[b.as_f64().unwrap_or(0.0) as usize];
    match t {
        Value::Str(s) if py_strip(s).is_empty() => bad(format!("blank token {} can be confused with text", repr(t))),
        _ => ok(""),
    }
}
fn c_sharpened(raw: &RawStream) -> Out {
    let lp = match lp2d(raw) {
        Some(lp) if lp.shape[0] >= 10 && !lp.data.iter().any(|x| x.is_nan()) => lp,
        _ => return skip("fewer than 10 frames"),
    };
    let (t, v) = (lp.shape[0], lp.shape[1]);
    let mut hot = 0;
    for r in 0..t {
        let m = lp.data[r * v..(r + 1) * v].iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        if m >= -1e-6 {
            hot += 1;
        }
    }
    let frac = hot as f64 / t as f64;
    let pct = libm::round(frac * 100.0) as i64;
    if frac > 0.9 { bad(format!("{}% of rows are one-hot", pct)) } else { ok_s(format!("{}% one-hot rows", pct)) }
}
fn c_fp_consist(raw: &RawStream) -> Out {
    let fp = match hget(raw, "frame_period") {
        Value::Num(x, _) => *x,
        _ => return skip("no frame_period or fewer than 3 frames"),
    };
    let ft = match &raw.frame_times {
        Some(ft) if ft.shape.len() == 1 && ft.data.len() >= 3 && fp > 0.0 => ft,
        _ => return skip("no frame_period or fewer than 3 frames"),
    };
    let mut d: Vec<f64> = ft.data.windows(2).map(|w| w[1] - w[0]).collect();
    d.sort_by(|a, b| a.partial_cmp(b).unwrap_or(core::cmp::Ordering::Equal));
    let n = d.len();
    let med = if n % 2 == 1 { d[(n - 1) / 2] } else { (d[n / 2 - 1] + d[n / 2]) / 2.0 };
    if libm::fabs(med - fp) <= 0.25 * fp {
        ok_s(format!("median step {} s", num_text(med)))
    } else {
        bad(format!("median step {} s vs frame_period {}", num_text(med), num_text(fp)))
    }
}

fn events_of<'a>(raw: &'a RawStream, typ: &str) -> Vec<&'a Map> {
    raw.events.iter().filter(|e| e.get("type").as_str() == Some(typ)).collect()
}
fn line_of(e: &Map) -> String {
    match e.get("_line") {
        Value::Num(x, _) => num_text(*x),
        _ => "?".to_string(),
    }
}

fn score_errors(e: &Map, need_semantics: bool, ignore_score: bool) -> Vec<String> {
    let mut errs = Vec::new();
    let sem = e.get("score_semantics");
    if sem.is_null() {
        if need_semantics {
            errs.push("no score_semantics".to_string());
        }
        return errs;
    }
    if !str_in(sem, SCORE_SEMANTICS) {
        return vec![format!("score_semantics {} is not one of {}", repr(sem), repr(&str_list(SCORE_SEMANTICS)))];
    }
    let sem = sem.as_str().unwrap_or("");
    let sc = if ignore_score { &crate::json::NULL } else { e.get("score") };
    if (sem == "calibrated_prob" || sem == "uncalibrated_prob")
        && !sc.is_null()
        && !matches!(sc, Value::Num(x, _) if *x >= 0.0 && *x <= 1.0)
    {
        errs.push(format!("score {} is not in [0, 1] for {} (3.5 rule 2)", repr(sc), sem));
    }
    if sem == "power" || sem == "strength" {
        let ok_rng = matches!(e.get("score_range"), Value::Arr(a) if a.len() == 2 && a.iter().all(|x| x.is_num()));
        if !ok_rng {
            errs.push(format!("score_semantics {} needs score_range [min, max] (3.5 table)", sem));
        }
    }
    if sem == "none" && !sc.is_null() {
        errs.push("score_semantics none needs a null or absent score".to_string());
    }
    errs
}

fn c_evt_decision(raw: &RawStream) -> Out {
    let evs = events_of(raw, "decision");
    if evs.is_empty() {
        return skip("no decision events");
    }
    let mut errs = Vec::new();
    for e in &evs {
        let n = line_of(e);
        if !e.get("label").is_str() {
            errs.push(format!("line {}: no string label", n));
        }
        if !e.get("t").is_num() {
            errs.push(format!("line {}: no numeric t", n));
        }
        for x in score_errors(e, true, false) {
            errs.push(format!("line {}: {}", n, x));
        }
    }
    if errs.is_empty() { ok_s(format!("{} decision event(s)", evs.len())) } else { bad(errs.join("; ")) }
}
fn c_evt_label(raw: &RawStream) -> Out {
    let evs = events_of(raw, "decision");
    let v = match vocab_of(raw) {
        Some(v) if !evs.is_empty() => v,
        _ => return skip("no decision events"),
    };
    let mut out: Vec<Value> = Vec::new();
    for e in &evs {
        let l = e.get("label");
        if !py_in(l, v) && !py_in(l, &out) {
            out.push(l.clone());
        }
    }
    if out.is_empty() {
        ok("")
    } else {
        out.truncate(5);
        bad(format!("labels not in vocab: {}", repr(&Value::Arr(out))))
    }
}
fn c_evt_hypothesis(raw: &RawStream) -> Out {
    let evs = events_of(raw, "hypothesis");
    if evs.is_empty() {
        return skip("no hypothesis events");
    }
    let mut errs = Vec::new();
    let mut ids: BTreeSet<String> = BTreeSet::new();
    for e in &evs {
        let n = line_of(e);
        match e.get("id") {
            Value::Str(id) => {
                if ids.contains(id) {
                    errs.push(format!("line {}: id '{}' is not unique", n, id));
                } else {
                    ids.insert(id.clone());
                }
            }
            _ => errs.push(format!("line {}: no string id", n)),
        }
        let nb_ok = matches!(e.get("nbest"), Value::Arr(a) if a.iter().all(|x| x.is_obj() && x.get("text").is_str() && x.get("score").is_num()));
        if !nb_ok {
            errs.push(format!("line {}: nbest must be a list of {{text, score}}", n));
        }
        if !matches!(e.get("is_final"), Value::Bool(_)) {
            errs.push(format!("line {}: is_final must be a boolean", n));
        }
        for x in score_errors(e, true, true) {
            errs.push(format!("line {}: {}", n, x));
        }
    }
    if errs.is_empty() { ok_s(format!("{} hypothesis event(s)", evs.len())) } else { bad(errs.join("; ")) }
}
fn c_evt_pointer(raw: &RawStream) -> Out {
    let evs = events_of(raw, "pointer");
    if evs.is_empty() {
        return skip("no pointer events");
    }
    let mut errs = Vec::new();
    for e in &evs {
        let n = line_of(e);
        let d = e.get("dims");
        if !e.get("t").is_num() {
            errs.push(format!("line {}: no numeric t", n));
        }
        let dv = d.as_f64().unwrap_or(0.0);
        if !(e.has("dims") && d.is_int() && (1.0..=3.0).contains(&dv)) {
            errs.push(format!("line {}: dims must be 1-3", n));
            continue;
        }
        let dn = dv as usize;
        let mode = e.get("mode");
        if !str_in(mode, &["relative", "absolute"]) {
            errs.push(format!("line {}: mode must be relative or absolute", n));
        }
        match e.get("values") {
            Value::Arr(vals) if vals.len() == dn && vals.iter().all(|x| x.is_num()) => {
                if mode.as_str() == Some("absolute") {
                    let absent_raw = e.get("absent");
                    let fill = vec![Value::Bool(false); dn];
                    let absent: &Vec<Value> = match absent_raw {
                        Value::Arr(a) if absent_raw.truthy() => a,
                        _ => &fill,
                    };
                    let len = vals.len().min(absent.len());
                    for k in 0..len {
                        let x = vals[k].as_f64().unwrap_or(0.0);
                        if !absent[k].truthy() && !(x >= 0.0 && x <= 1.0) {
                            errs.push(format!("line {}: absolute values must be in [0, 1]", n));
                            break;
                        }
                    }
                }
            }
            _ => errs.push(format!("line {}: values must be {} numbers", n, dn)),
        }
    }
    if errs.is_empty() { ok_s(format!("{} pointer event(s)", evs.len())) } else { bad(errs.join("; ")) }
}
fn c_evt_signal_quality(raw: &RawStream) -> Out {
    let evs = events_of(raw, "signal_quality");
    if evs.is_empty() {
        return skip("no signal_quality events");
    }
    let mut errs = Vec::new();
    for e in &evs {
        let n = line_of(e);
        if !e.get("t").is_num() || !e.get("value").is_num() {
            errs.push(format!("line {}: needs numeric t and value", n));
        }
        let unit = e.get("unit");
        if !str_in(unit, SQ_UNITS) {
            errs.push(format!("line {}: unit must be one of {}", n, repr(&str_list(SQ_UNITS))));
        } else if unit.as_str() == Some("index") {
            if let Value::Num(x, _) = e.get("value") {
                if !(*x >= 0.0 && *x <= 1.0) {
                    errs.push(format!("line {}: index value must be in [0, 1]", n));
                }
            }
        }
    }
    if errs.is_empty() { ok_s(format!("{} signal_quality event(s)", evs.len())) } else { bad(errs.join("; ")) }
}
fn c_evt_timing(raw: &RawStream) -> Out {
    let keys = ["t_signal_start", "t_signal_end", "t_decoded", "t_emitted"];
    let evs: Vec<&Map> = raw.events.iter().filter(|e| keys.iter().any(|k| e.has(k))).collect();
    if evs.is_empty() {
        return skip("no extended timing");
    }
    let mut errs = Vec::new();
    for e in &evs {
        let vals: Vec<(&str, &Value)> = keys.iter().filter_map(|k| e.get_opt(k).map(|v| (*k, v))).collect();
        if !vals.iter().all(|(_, v)| v.is_num()) {
            errs.push(format!("line {}: timing values must be numbers", line_of(e)));
            continue;
        }
        for w in vals.windows(2) {
            let (a, b) = (w[0].1.as_f64().unwrap_or(0.0), w[1].1.as_f64().unwrap_or(0.0));
            if a > b {
                errs.push(format!("line {}: {} {} > {} {}", line_of(e), w[0].0, num_text(a), w[1].0, num_text(b)));
            }
        }
    }
    if errs.is_empty() { ok("") } else { bad(errs.join("; ")) }
}
fn c_clock(raw: &RawStream) -> Out {
    match raw.header.get_opt("clock_domain") {
        None => ok("absent (default trial)"),
        Some(cd) if str_in(cd, CLOCK_DOMAINS) => ok(""),
        Some(cd) => bad(format!("clock_domain {} is not one of {}", repr(cd), repr(&str_list(CLOCK_DOMAINS)))),
    }
}

// --- trust-ready profile ------------------------------------------------------------------------

fn c_tr_source(raw: &RawStream) -> Out {
    match hget(raw, "source") {
        Value::Str(s) if !s.is_empty() && s != "unknown" => ok(""),
        _ => bad("source is absent or \"unknown\"".to_string()),
    }
}
fn c_tr_modality(raw: &RawStream) -> Out {
    match meta_or_empty(raw).get_opt("device.modality") {
        Some(v) => ok_s(crate::json::py_str(v)),
        None => bad("no device.modality".to_string()),
    }
}
fn c_tr_causal(raw: &RawStream) -> Out {
    if meta_or_empty(raw).has("decoder.causal") {
        ok("")
    } else {
        bad("no decoder.causal (a consumer cannot tell online from offline output)".to_string())
    }
}
fn c_tr_offline_latency(raw: &RawStream) -> Out {
    if !matches!(meta_or_empty(raw).get("decoder.causal"), Value::Bool(false)) {
        return skip("decoder.causal is not false");
    }
    if !hget(raw, "latency").is_null() {
        bad("decoder.causal is false but latency is set (see ambiguity A1)".to_string())
    } else {
        ok("")
    }
}
fn c_tr_derived(raw: &RawStream) -> Out {
    match meta_or_empty(raw).get_opt("data.derived") {
        None => bad("no data.derived".to_string()),
        Some(Value::Bool(true)) => ok(""),
        Some(v) => bad(format!("data.derived is {}", repr(v))),
    }
}
/// Python `v in (None, False, 1, 1.0)` (True == 1 and False == 0 in Python).
fn calib_neutral(v: &Value) -> bool {
    match v {
        Value::Null | Value::Bool(_) => true,
        Value::Num(x, _) => *x == 0.0 || *x == 1.0,
        _ => false,
    }
}
fn c_tr_calib(raw: &RawStream) -> Out {
    let m = meta_or_empty(raw);
    let applied = m.get_opt("calibration.applied").cloned().unwrap_or(Value::Bool(false));
    if matches!(applied, Value::Bool(true)) {
        return match m.get("decoder.calibration_method") {
            Value::Str(s) if !s.is_empty() && s != "none" => ok(""),
            _ => bad("calibration.applied is true but decoder.calibration_method is absent or \"none\"".to_string()),
        };
    }
    let hints: Vec<&str> = m
        .iter()
        .filter(|(k, v)| {
            let l = k.to_lowercase();
            (l.contains("calibrat") || l.contains("temperature")) && !defined(k) && !calib_neutral(v)
        })
        .map(|(k, _)| k)
        .collect();
    if hints.is_empty() {
        ok("")
    } else {
        bad(format!("keys {} suggest a calibration step, but calibration.applied is not true (default false)", repr(&str_list(&hints))))
    }
}
fn c_tr_language(raw: &RawStream) -> Out {
    if !str_in(hget(raw, "vocab_type"), &["char", "word", "phoneme"]) {
        return skip("not a text vocabulary");
    }
    match meta_or_empty(raw).get_opt("language") {
        Some(v) => ok_s(crate::json::py_str(v)),
        None => bad("no language".to_string()),
    }
}
fn c_pv_stream_id(raw: &RawStream) -> Out {
    match meta_or_empty(raw).get("stream.id") {
        Value::Str(s) if !s.is_empty() => ok(""),
        _ => bad("no stream.id (a consumer must hash the content)".to_string()),
    }
}
fn c_pv_decoder(raw: &RawStream) -> Out {
    let m = meta_or_empty(raw);
    let miss: Vec<&str> = ["decoder.name", "decoder.version"].into_iter().filter(|k| !m.has(k)).collect();
    if miss.is_empty() { ok("") } else { bad(format!("missing {}", repr(&str_list(&miss)))) }
}
fn c_pv_weights(raw: &RawStream) -> Out {
    if meta_or_empty(raw).has("decoder.weights_sha256") { ok("") } else { bad("no decoder.weights_sha256".to_string()) }
}
fn c_pv_adapter(raw: &RawStream) -> Out {
    let m = meta_or_empty(raw);
    let (a, b) = (m.has("adapter.name"), m.has("adapter.version"));
    if a != b {
        return bad("only one of adapter.name / adapter.version".to_string());
    }
    ok(if a { "adapter keys present" } else { "no adapter keys" })
}
fn c_pv_calib_id(raw: &RawStream) -> Out {
    let m = meta_or_empty(raw);
    if !matches!(m.get("calibration.applied"), Value::Bool(true)) {
        return skip("calibration.applied is not true");
    }
    if m.has("decoder.calibration_id") { ok("") } else { bad("no decoder.calibration_id".to_string()) }
}
fn c_pv_pseudonym(raw: &RawStream) -> Out {
    let m = meta_or_empty(raw);
    let errs: Vec<String> = ["subject.id", "session.id"]
        .into_iter()
        .filter_map(|k| match m.get(k) {
            Value::Str(s) if !py_match(is_pseudo_id, s) => Some(format!("{} = {}", k, repr(m.get(k)))),
            _ => None,
        })
        .collect();
    if errs.is_empty() {
        ok("")
    } else {
        let v: Vec<&str> = errs.iter().map(|s| s.as_str()).collect();
        bad(format!("ids that do not look like codes: {}", repr(&str_list(&v))))
    }
}

macro_rules! chk {
    ($id:expr, $lv:ident, $kw:expr, $cl:expr, $title:expr, $f:expr) => {
        CheckDef { id: $id, level: Level::$lv, keyword: $kw, clause: $cl, title: $title, f: $f, heuristic: false, only: None }
    };
    ($id:expr, $lv:ident, $kw:expr, $cl:expr, $title:expr, $f:expr, heuristic) => {
        CheckDef { id: $id, level: Level::$lv, keyword: $kw, clause: $cl, title: $title, f: $f, heuristic: true, only: None }
    };
    ($id:expr, $lv:ident, $kw:expr, $cl:expr, $title:expr, $f:expr, $fmt:ident) => {
        CheckDef { id: $id, level: Level::$lv, keyword: $kw, clause: $cl, title: $title, f: $f, heuristic: false, only: Some(Format::$fmt) }
    };
}

static REGISTRY: &[CheckDef] = &[
    chk!("NTS-PARSE", Core, "MUST", "6.1 / 6.2", "The file loads in its serialisation (NPZ without pickle; UTF-8 JSON Lines)", c_parse),
    chk!("NTS-NPZ-KEYS", Core, "MUST", "6.1", "The NPZ file has all required keys", c_npz_keys, Npz),
    chk!("NTS-NPZ-DTYPE", Advisory, "SHOULD", "6.1", "NPZ dtypes follow the 6.1 table (log_probs float32, frame_times float64, blank_id int64)", c_npz_dtype, Npz),
    chk!("NTS-UNKNOWN-KEYS", Advisory, "MUST", "6.1 note / 6.2.5", "Unknown keys are reported; a consumer MUST ignore them", c_unknown_keys),
    chk!("NTS-JSONL-HEADER", Core, "MUST", "6.2.1", "Line 1 is the header with type, spec_version, vocab, vocab_type, blank_id", c_jsonl_header, Jsonl),
    chk!("NTS-JSONL-FRAME", Core, "MUST", "6.2.2 / 6.2.3", "Each frame has t and log_probs (numbers or null) or the sparse keys", c_jsonl_frame, Jsonl),
    chk!("NTS-JSONL-END", Advisory, "SHOULD", "6.2", "No lines after the end marker", c_jsonl_end, Jsonl),
    chk!("NTS-VERSION", Core, "MUST", "5.1.4", "spec_version is a version the consumer supports (\"0.1\")", c_version),
    chk!("NTS-LP-2D", Core, "MUST", "5.1.1", "log_probs has exactly 2 dimensions [T, V]", c_lp_2d),
    chk!("NTS-V-MATCH", Core, "MUST", "5.1.2", "V equals the length of vocab", c_v_match),
    chk!("NTS-FT-SHAPE", Core, "MUST", "5.1.3", "frame_times has shape [T]", c_ft_shape),
    chk!("NTS-VOCAB-TYPE", Core, "MUST", "5.1.5", "vocab_type is one of char, key, word, phoneme, command, other", c_vocab_type),
    chk!("NTS-VOCAB-STR", Core, "MUST", "3.1", "vocab is a list of strings", c_vocab_str),
    chk!("NTS-VOCAB-UNIQUE", Core, "MUST", "5.2.4", "vocab tokens are unique", c_vocab_unique),
    chk!("NTS-BLANK", Core, "MUST", "3.1 / 5.1.6", "blank_id is null or an integer in 0..V-1", c_blank),
    chk!("NTS-SOURCE", Core, "MUST", "5.1.7", "source, if present, is a non-empty string", c_source),
    chk!("NTS-META-OBJECT", Core, "MUST", "5.1.7", "meta, if present, is a JSON object", c_meta_object),
    chk!("NTS-META-JSON", Core, "MUST", "4.1", "meta values are JSON values (no NaN, no infinity, no other types)", c_meta_json),
    chk!("NTS-LP-FINITE", Core, "MUST", "5.2.2", "log_probs has no NaN and no +inf (-inf is allowed)", c_lp_finite),
    chk!("NTS-NORM", Core, "MUST", "5.2.1", "Each row of log_probs log-sum-exps to 0 (tolerance 0.001)", c_norm),
    chk!("NTS-FT-FINITE", Core, "MUST", "5.2.3", "frame_times are finite", c_ft_finite),
    chk!("NTS-FT-MONO", Core, "MUST", "5.2.3 / 6.2.4", "frame_times increase strictly", c_ft_mono),
    chk!("NTS-FRAME-PERIOD", Core, "MUST", "3.2 / 5.2.5", "frame_period, if present, is finite and > 0", c_frame_period),
    chk!("NTS-LATENCY", Core, "MUST", "3.2 / 5.2.5", "latency, if present, is finite and >= 0", c_latency),
    chk!("NTS-SPARSE", Core, "MUST", "3.3", "Sparse frames: k values plus rest_log_prob are normalised", c_sparse, Jsonl),
    chk!("NTS-META-TYPES", Core, "MUST", "4.1 / 4.2", "Defined meta keys have the type and values of section 4.2", c_meta_types),
    chk!("NTS-META-LOOKAHEAD", Core, "MUST", "4.2", "decoder.lookahead_s equals latency when both are present", c_meta_lookahead),
    chk!("NTS-NAMESPACE", Advisory, "SHOULD", "4.1", "meta keys are namespaced; custom keys avoid the defined namespaces", c_namespace),
    chk!("NTS-LEAK-KEYS", Core, "MUST", "5.3.1", "meta has no key that names ground truth or target labels", c_leak_keys, heuristic),
    chk!("NTS-PRIVACY", Core, "MUST", "5.4.1 / 4.2", "meta has no personal identifiers (e-mail, name, birth date keys)", c_privacy, heuristic),
    chk!("NTS-FREE-TEXT", Advisory, "SHOULD NOT", "5.4.3", "meta has no free-text note fields", c_free_text, heuristic),
    chk!("NTS-VOCAB-ID", Core, "MUST", "3.4", "If a header vocab_id names a known registry entry, vocab matches it", c_vocab_id),
    chk!("NTS-VT-CHAR", TrustReady, "PROFILE", "3.1", "char vocabulary: each non-blank token is one character", c_vt_char),
    chk!("NTS-VT-KEY", Advisory, "SHOULD", "3.1 / 10.7", "key vocabulary: tokens are W3C KeyboardEvent.code names", c_vt_key),
    chk!("NTS-VT-PHONEME", Advisory, "SHOULD", "3.1 / 3.4", "phoneme vocabulary: tokens are ARPAbet (plus silence markers) or IPA", c_vt_phoneme),
    chk!("NTS-VT-OTHER", Advisory, "SHOULD", "3.1", "vocab_type other: meta describes the tokens", c_vt_other),
    chk!("NTS-BLANK-TOKEN", Advisory, "SHOULD", "3.1", "The blank token is not a whitespace or empty string", c_blank_token),
    chk!("NTS-SHARPENED", Advisory, "MUST NOT", "2.4.4", "Rows are not all one-hot (a sign of sharpened output)", c_sharpened),
    chk!("NTS-FP-CONSIST", Advisory, "SHOULD", "3.2", "frame_period agrees with the median frame step (within 25 %)", c_fp_consist),
    chk!("NTS-EVT-DECISION", Core, "MUST", "3.5", "decision events: label, t, score_semantics and score rules", c_evt_decision, Jsonl),
    chk!("NTS-EVT-LABEL", Advisory, "SHOULD", "3.5", "decision labels are tokens in vocab", c_evt_label, Jsonl),
    chk!("NTS-EVT-HYPOTHESIS", Core, "MUST", "3.6", "hypothesis events: id, nbest, score_semantics, is_final", c_evt_hypothesis, Jsonl),
    chk!("NTS-EVT-POINTER", Core, "MUST", "3.7", "pointer events: t, dims 1-3, mode, values", c_evt_pointer, Jsonl),
    chk!("NTS-EVT-SIGNAL-QUALITY", Core, "MUST", "3.9", "signal_quality events: t, value, unit; index in [0, 1]", c_evt_signal_quality, Jsonl),
    chk!("NTS-EVT-TIMING", Core, "MUST", "3.8", "t_signal_start <= t_signal_end <= t_decoded <= t_emitted when present", c_evt_timing, Jsonl),
    chk!("NTS-CLOCK", Core, "MUST", "3.8", "clock_domain, if present, is lsl, unix, monotonic, trial or other", c_clock),
    chk!("TR-SOURCE", TrustReady, "PROFILE", "3.2", "source names the producer (present and not \"unknown\")", c_tr_source),
    chk!("TR-MODALITY", TrustReady, "PROFILE", "4.2", "meta has device.modality", c_tr_modality),
    chk!("TR-CAUSAL", TrustReady, "SHOULD", "3.2 / 4.2", "meta has decoder.causal", c_tr_causal),
    chk!("TR-OFFLINE-LATENCY", TrustReady, "SHOULD", "3.2", "A non-causal (offline) decoder omits latency", c_tr_offline_latency),
    chk!("TR-DERIVED", TrustReady, "SHOULD", "4.2 / 5.4.4", "meta has data.derived = true", c_tr_derived),
    chk!("TR-CALIB", TrustReady, "MUST", "4.1 / 4.2 / 3.5.3", "calibration.applied is consistent with the calibration keys", c_tr_calib),
    chk!("TR-LANGUAGE", TrustReady, "PROFILE", "4.2", "Text vocabularies (char, word, phoneme) state the language", c_tr_language),
    chk!("PV-STREAM-ID", Provenance, "PROFILE", "4.3.1", "meta has an opaque stream.id", c_pv_stream_id),
    chk!("PV-DECODER", Provenance, "SHOULD", "4.3.2", "meta has decoder.name and decoder.version", c_pv_decoder),
    chk!("PV-WEIGHTS", Provenance, "SHOULD", "4.2 / 4.3.2", "meta has decoder.weights_sha256", c_pv_weights),
    chk!("PV-ADAPTER", Provenance, "SHOULD", "4.2 / 4.3.2", "adapter.name and adapter.version are both present or both absent", c_pv_adapter),
    chk!("PV-CALIB-ID", Provenance, "SHOULD", "3.5.3 / 4.3.2", "A calibrated stream has decoder.calibration_id", c_pv_calib_id),
    CheckDef {
        id: "PV-PSEUDONYM",
        level: Level::Provenance,
        keyword: "MUST",
        clause: "5.4.2 / 4.3.4",
        title: "subject.id and session.id look like pseudonymous codes",
        f: c_pv_pseudonym,
        heuristic: true,
        only: None,
    },
];

// --- runner ---------------------------------------------------------------------------------------

/// Run every check that applies to the format of `raw`.
pub fn run_checks(raw: &RawStream) -> Vec<CheckResult> {
    let mut out = Vec::new();
    for c in REGISTRY {
        if let Some(f) = c.only {
            if f != raw.format {
                continue;
            }
        }
        let (status, message) = if !raw.parsed && c.id != "NTS-PARSE" && c.id != "NTS-JSONL-HEADER" {
            (Status::Skip, "the file did not parse".to_string())
        } else {
            (c.f)(raw)
        };
        out.push(CheckResult {
            id: c.id.to_string(),
            level: c.level,
            keyword: c.keyword.to_string(),
            clause: c.clause.to_string(),
            title: c.title.to_string(),
            status,
            message,
            heuristic: c.heuristic,
        });
    }
    out
}

/// One row of the check table.
#[derive(Debug, Clone)]
pub struct CheckInfo {
    pub id: &'static str,
    pub level: Level,
    pub keyword: &'static str,
    pub clause: &'static str,
    pub title: &'static str,
    pub heuristic: bool,
    /// The formats the check applies to ("npz", "jsonl").
    pub formats: &'static [&'static str],
}

/// The list of all checks.
pub fn check_table() -> Vec<CheckInfo> {
    REGISTRY
        .iter()
        .map(|c| CheckInfo {
            id: c.id,
            level: c.level,
            keyword: c.keyword,
            clause: c.clause,
            title: c.title,
            heuristic: c.heuristic,
            formats: match c.only {
                None => &["npz", "jsonl"],
                Some(Format::Npz) => &["npz"],
                Some(Format::Jsonl) => &["jsonl"],
            },
        })
        .collect()
}

/// Highest level a set of results reaches: provenance, trust-ready, core or `None`.
pub fn level_reached(results: &[CheckResult]) -> Option<Level> {
    let mut best = None;
    for lv in LEVELS {
        if results.iter().any(|r| r.status == Status::Fail && blocks(r.level, lv)) {
            break;
        }
        best = Some(lv);
    }
    best
}

// --- reference consumer ---------------------------------------------------------------------------

/// What the reference consumer returns for an accepted file.
#[derive(Debug, Clone)]
pub struct ConsumedStream {
    pub header: Map,
    /// [T, V] log-probabilities (row-major, float32 values as f64), -inf allowed.
    pub log_probs: NdArray,
    pub frame_times: Vec<f64>,
    /// Non-frame events (without `_line`).
    pub events: Vec<Map>,
    pub ignored_events: usize,
    pub unknown_keys: Vec<String>,
    pub vocab_type_defaulted: bool,
    /// The summary of the Python reference (`n_frames`, `vocab_size`, ...).
    pub summary: Map,
}

/// The reference consumer: accept a stream when every core check passes, else
/// return a rejection with the first failing clause. `name` gives the format
/// by its extension (`.npz`, `.jsonl`).
pub fn load_stream(name: &str, bytes: &[u8]) -> Result<ConsumedStream, Error> {
    consume_raw(read_raw(name, bytes)?)
}

/// The reference consumer on a raw stream.
pub fn consume_raw(raw: RawStream) -> Result<ConsumedStream, Error> {
    for r in run_checks(&raw) {
        if r.status == Status::Fail && blocks(r.level, Level::Core) {
            return Err(Error::rejected(format!("[{}, spec {}] {}", r.id, r.clause, r.message), &r.clause, &r.id));
        }
    }
    let h = raw.header.clone();
    let vocab_len = h.get("vocab").as_arr().map_or(0, |a| a.len());
    let lp = raw.log_probs.clone().unwrap_or(NdArray { shape: vec![0, vocab_len], data: Vec::new() });
    // The Python NeuralTextStream stores log_probs as float32 and validates again.
    let (t, v) = (lp.shape[0], lp.shape.get(1).copied().unwrap_or(0));
    let f32s: Vec<f64> = lp.data.iter().map(|&x| x as f32 as f64).collect();
    if f32s.iter().any(|x| x.is_nan() || *x == f64::INFINITY) {
        return Err(Error::rejected("log_probs must not contain NaN or +inf", "5.2.2", ""));
    }
    if t > 0 {
        let lse = row_lse(&f32s, t, v);
        if let Some((i, x)) = lse.iter().enumerate().find(|(_, x)| libm::fabs(**x) > NORM_TOL) {
            return Err(Error::rejected(
                format!("log_probs rows must log-sum-exp to 0 (tol {}); frame {} gives {}", NORM_TOL, i, num_text(*x)),
                "5.2.1",
                "",
            ));
        }
    }
    let neg = f32s.iter().filter(|x| **x == f64::NEG_INFINITY).count();
    let events: Vec<Map> = raw
        .events
        .iter()
        .map(|e| {
            let mut e = e.clone();
            e.remove("_line");
            e
        })
        .collect();
    let vt = h.get_opt("vocab_type").cloned().unwrap_or(Value::str("char"));
    let blank = h.get_opt("blank_id").cloned().unwrap_or(Value::Null);
    let uk: Vec<&str> = raw.unknown_keys.iter().map(|s| s.as_str()).collect();
    let summary = Map::from_pairs([
        ("n_frames", Value::int(t as f64)),
        ("vocab_size", Value::int(vocab_len as f64)),
        ("vocab_type", vt),
        ("blank_id", blank),
        ("neg_inf_cells", Value::int(neg as f64)),
        ("ignored_events", Value::int(raw.ignored_events as f64)),
        ("unknown_keys", str_list(&uk)),
        ("vocab_type_defaulted", Value::Bool(raw.vocab_type_defaulted)),
        ("events", Value::int(events.len() as f64)),
    ]);
    Ok(ConsumedStream {
        header: h,
        log_probs: NdArray { shape: vec![t, v], data: f32s },
        frame_times: raw.frame_times.map(|f| f.data).unwrap_or_default(),
        events,
        ignored_events: raw.ignored_events,
        unknown_keys: raw.unknown_keys,
        vocab_type_defaulted: raw.vocab_type_defaulted,
        summary,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn patterns() {
        assert!(has_email("write to a.b@example.org now"));
        assert!(!has_email("a@b.c"));
        assert!(!has_email("@example.org"));
        assert!(is_w3c_code("KeyA") && is_w3c_code("F12") && is_w3c_code("ShiftLeft") && is_w3c_code("Numpad1"));
        assert!(!is_w3c_code("Keya") && !is_w3c_code("F123"));
        assert!(py_match(is_bcp47, "en-US\n") && !is_bcp47("e"));
        assert!(is_pseudo_id("S01") && !is_pseudo_id("John Smith"));
        assert_eq!(check_table().len(), 59); // the same 59 checks as the Python REGISTRY
    }
}
