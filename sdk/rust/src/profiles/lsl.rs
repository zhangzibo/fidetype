//! NeuralTextStream over LSL (FEP-0002), scenario form: a port of the parts of
//! `fidetype.adapters.lsl` that the `fep-0002` conformance vectors use. There
//! is no network and no liblsl: a scenario scripts the chunks.
//!
//! The Python reference consumer feeds the events into its trust layer. This
//! port replaces the trust layer with a structural model: the same event
//! checks ([`crate::validate`] rules) and the same decision COUNTS (one final
//! decision per closed utterance with input; one provisional decision per
//! partial hypothesis on the hypothesis route). It does not decode or apply a
//! trust policy, so it gives no decision texts.

use alloc::collections::{BTreeMap, VecDeque};
use alloc::string::{String, ToString};
use alloc::vec;
use alloc::vec::Vec;
use alloc::format;

use crate::constants::{SPEC_VERSION, VOCAB_TYPES};
use crate::error::{Error, ErrorKind};
use crate::json::{cp_len, num_text, parse_json_opts, py_eq, py_in, py_str, py_strip, repr, str_in, Map, Value};
use crate::sha256::sha256_f64_rows;
use crate::validate::{check_header, check_hypothesis, frame_row};

// --- a minimal XML reader (the subset that liblsl's stream info XML uses) ----------------

/// An XML element (text = the text before the first child, as ElementTree).
#[derive(Debug, Clone)]
pub struct XmlEl {
    pub tag: String,
    pub text: Option<String>,
    pub children: Vec<XmlEl>,
}

fn xml_err(m: impl Into<String>) -> Error {
    Error::new(ErrorKind::Format, m)
}

fn unescape_xml(s: &str) -> Result<String, Error> {
    let mut out = String::new();
    let mut rest = s;
    while let Some(i) = rest.find('&') {
        out.push_str(&rest[..i]);
        let after = &rest[i + 1..];
        let end = after.find(';');
        let ent = end.map(|e| &after[..e]);
        let valid = match ent {
            Some(g) if g.starts_with("#x") => g.len() > 2 && g[2..].chars().all(|c| c.is_ascii_hexdigit()),
            Some(g) if g.starts_with('#') => g.len() > 1 && g[1..].chars().all(|c| c.is_ascii_digit()),
            Some(g) => !g.is_empty() && g.chars().all(|c| c.is_ascii_alphabetic()),
            None => false,
        };
        if !valid {
            // expat (Python ElementTree) refuses a bare "&"
            return Err(xml_err("not well-formed (invalid token): a bare '&'"));
        }
        let g = ent.unwrap_or("");
        let ch: String = if let Some(h) = g.strip_prefix("#x") {
            let cp = u32::from_str_radix(h, 16).ok().filter(|c| *c <= 0x10FFFF).ok_or_else(|| xml_err("Invalid code point"))?;
            char::from_u32(cp).unwrap_or('\u{FFFD}').to_string()
        } else if let Some(d) = g.strip_prefix('#') {
            let cp = d.parse::<u32>().ok().filter(|c| *c <= 0x10FFFF).ok_or_else(|| xml_err("Invalid code point"))?;
            char::from_u32(cp).unwrap_or('\u{FFFD}').to_string()
        } else {
            match g {
                "lt" => "<".into(),
                "gt" => ">".into(),
                "amp" => "&".into(),
                "quot" => "\"".into(),
                "apos" => "'".into(),
                _ => return Err(xml_err(format!("undefined entity &{};", g))),
            }
        };
        out.push_str(&ch);
        rest = &after[g.len() + 1..];
    }
    out.push_str(rest);
    Ok(out)
}

fn name_start(c: char) -> bool {
    c.is_ascii_alphabetic() || c == '_'
}
fn name_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | '-' | ':')
}
fn js_space(c: char) -> bool {
    matches!(c, '\t' | '\n' | '\u{b}' | '\u{c}' | '\r' | ' ' | '\u{a0}' | '\u{1680}' | '\u{2000}'..='\u{200a}'
        | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}' | '\u{feff}')
}

struct Xml<'a> {
    s: &'a str,
    i: usize,
}

impl<'a> Xml<'a> {
    fn rest(&self) -> &'a str {
        &self.s[self.i..]
    }
    fn skip_space(&mut self) {
        while let Some(c) = self.rest().chars().next() {
            if js_space(c) {
                self.i += c.len_utf8();
            } else {
                break;
            }
        }
    }
    fn skip_misc(&mut self) -> Result<(), Error> {
        loop {
            self.skip_space();
            let r = self.rest();
            if r.starts_with("<?") {
                let e = r.find("?>").ok_or_else(|| xml_err("unclosed processing instruction"))?;
                self.i += e + 2;
            } else if r.starts_with("<!--") {
                let e = r.find("-->").ok_or_else(|| xml_err("unclosed comment"))?;
                self.i += e + 3;
            } else if r.starts_with("<!DOCTYPE") {
                match r.find('>') {
                    Some(e) => self.i += e + 1,
                    None => self.i = 0, // as JavaScript indexOf = -1: start again (then fails)
                }
                if self.i == 0 {
                    return Err(xml_err("unclosed DOCTYPE"));
                }
            } else {
                return Ok(());
            }
        }
    }
    fn name(&mut self) -> Option<String> {
        let r = self.rest();
        let mut it = r.char_indices();
        match it.next() {
            Some((_, c)) if name_start(c) => {}
            _ => return None,
        }
        let end = r.char_indices().find(|(_, c)| !name_char(*c)).map(|(i, _)| i).unwrap_or(r.len());
        self.i += end;
        Some(r[..end].to_string())
    }
    /// `<tag attr="v" ...>` or `<tag/>`. Returns (tag, self-closing).
    fn open_tag(&mut self) -> Result<(String, bool), Error> {
        let start = self.i;
        let fail = |i: usize| xml_err(format!("not well-formed XML at position {}", i));
        if !self.rest().starts_with('<') {
            return Err(fail(start));
        }
        self.i += 1;
        let tag = self.name().ok_or_else(|| fail(start))?;
        loop {
            let before = self.i;
            let had_space = self.rest().chars().next().map_or(false, js_space);
            self.skip_space();
            let r = self.rest();
            if r.starts_with("/>") {
                self.i += 2;
                return Ok((tag, true));
            }
            if r.starts_with('>') {
                self.i += 1;
                return Ok((tag, false));
            }
            if !had_space {
                return Err(fail(start));
            }
            // attribute: name = "..." | '...'
            let an_end = r.char_indices().find(|(_, c)| !name_char(*c)).map(|(i, _)| i).unwrap_or(r.len());
            if an_end == 0 {
                return Err(fail(start));
            }
            self.i += an_end;
            self.skip_space();
            if !self.rest().starts_with('=') {
                return Err(fail(start));
            }
            self.i += 1;
            self.skip_space();
            let q = match self.rest().chars().next() {
                Some(q @ ('"' | '\'')) => q,
                _ => return Err(fail(start)),
            };
            self.i += 1;
            let e = self.rest().find(q).ok_or_else(|| fail(start))?;
            self.i += e + 1;
            if self.i == before {
                return Err(fail(start));
            }
        }
    }
    fn element(&mut self, depth: usize) -> Result<XmlEl, Error> {
        if depth > 500 {
            return Err(xml_err("XML nesting too deep"));
        }
        let (tag, selfclose) = self.open_tag()?;
        let mut el = XmlEl { tag, text: None, children: Vec::new() };
        if selfclose {
            return Ok(el);
        }
        let mut text = String::new();
        let mut saw_text = false;
        loop {
            let r = self.rest();
            if r.is_empty() {
                return Err(xml_err(format!("no closing tag for <{}>", el.tag)));
            }
            if r.starts_with("</") {
                let at = self.i;
                self.i += 2;
                let name = self.name();
                self.skip_space();
                if name.as_deref() != Some(el.tag.as_str()) || !self.rest().starts_with('>') {
                    return Err(xml_err(format!("mismatched tag at position {}", at)));
                }
                self.i += 1;
                if el.children.is_empty() && saw_text {
                    el.text = Some(text);
                }
                return Ok(el);
            }
            if r.starts_with("<!--") {
                let e = r.find("-->").ok_or_else(|| xml_err("unclosed comment"))?;
                self.i += e + 3;
                continue;
            }
            if r.starts_with("<![CDATA[") {
                let e = r.find("]]>").ok_or_else(|| xml_err("unclosed CDATA"))?;
                if el.children.is_empty() {
                    text.push_str(&r[9..e]);
                    saw_text = true;
                }
                self.i += e + 3;
                continue;
            }
            if r.starts_with('<') {
                if el.children.is_empty() && saw_text {
                    el.text = Some(text.clone());
                }
                let child = self.element(depth + 1)?;
                el.children.push(child);
                continue;
            }
            let e = r.find('<').unwrap_or(r.len());
            let chunk = &r[..e];
            if el.children.is_empty() {
                text.push_str(&unescape_xml(chunk)?);
                saw_text = true;
            }
            self.i += e;
        }
    }
}

/// Parse an XML document into elements.
pub fn parse_xml(xml: &str) -> Result<XmlEl, Error> {
    let s = xml.replace("\r\n", "\n").replace('\r', "\n");
    let mut p = Xml { s: &s, i: 0 };
    p.skip_misc()?;
    let root = p.element(0)?;
    p.skip_misc()?;
    if p.i != s.len() {
        return Err(xml_err("junk after document element"));
    }
    Ok(root)
}

fn find<'a>(el: Option<&'a XmlEl>, tag: &str) -> Option<&'a XmlEl> {
    el?.children.iter().find(|c| c.tag == tag)
}

// --- stream info --------------------------------------------------------------------------

pub const NTS_STREAM_TYPE: &str = "NTS";
pub const MARKERS_TYPE: &str = "Markers";
pub const BINDING_VERSION: &str = "nts-lsl/0.1";
const KNOWN_BINDINGS: &[&str] = &[BINDING_VERSION];
const NTS_FRAME_FORMATS: &[&str] = &["float32", "double64"];
const EVENT_CLOCKS: &[&str] = &["source", "lsl"];
const EVENT_TIME_KEYS: &[&str] = &["t", "t_start", "t_end", "t_signal_start", "t_signal_end", "t_decoded", "t_emitted"];
const SRATE_RTOL: f64 = 1e-6;
const NUMERIC_FORMATS: &[&str] = &["float32", "double64", "int8", "int16", "int32", "int64"];
const CLAMP_STEP_S: f64 = 1e-6;
const ADAPTER_NAME: &str = "fidetype.adapters.lsl";
const ADAPTER_VERSION: &str = "0.1";

/// An LSL stream info (the fields the binding reads).
#[derive(Debug, Clone)]
pub struct LslStreamInfo {
    pub name: String,
    pub type_: String,
    pub channel_count: f64,
    pub nominal_srate: f64,
    pub channel_format: String,
    pub source_id: String,
    pub uid: String,
    pub hostname: String,
    pub channel_labels: Vec<String>,
    /// Child values of desc/fidetype, in order (a later duplicate replaces the value).
    pub fidetype: Vec<(String, String)>,
}

impl LslStreamInfo {
    /// A desc/fidetype value.
    pub fn fid(&self, k: &str) -> Option<&str> {
        self.fidetype.iter().find(|(kk, _)| kk == k).map(|(_, v)| v.as_str())
    }
    fn is_string(&self) -> bool {
        self.channel_format == "string"
    }
}

/// Python `float()` of a string: white space, inf, nan, underscores between digits.
pub fn py_float(s: &str) -> Result<f64, Error> {
    let t = py_strip(s).to_lowercase();
    let unsigned = t.strip_prefix(['+', '-']).unwrap_or(&t);
    let neg = t.starts_with('-');
    if unsigned == "inf" || unsigned == "infinity" {
        return Ok(if neg { f64::NEG_INFINITY } else { f64::INFINITY });
    }
    if unsigned == "nan" {
        return Ok(f64::NAN);
    }
    let fail = || Error::value(format!("could not convert string to float: '{}'", s));
    // remove "_" between digits
    let cs: Vec<char> = t.chars().collect();
    let mut u = String::new();
    for (i, &c) in cs.iter().enumerate() {
        if c == '_' && i > 0 && i + 1 < cs.len() && cs[i - 1].is_ascii_digit() && cs[i + 1].is_ascii_digit() {
            continue;
        }
        u.push(c);
    }
    // ^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$
    let b = u.as_bytes();
    let mut i = 0;
    if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
        i += 1;
    }
    let d0 = i;
    while i < b.len() && b[i].is_ascii_digit() {
        i += 1;
    }
    let int_digits = i - d0;
    let mut frac_digits = 0;
    if i < b.len() && b[i] == b'.' {
        i += 1;
        let f0 = i;
        while i < b.len() && b[i].is_ascii_digit() {
            i += 1;
        }
        frac_digits = i - f0;
    }
    if int_digits == 0 && frac_digits == 0 {
        return Err(fail());
    }
    if i < b.len() && b[i] == b'e' {
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
            i += 1;
        }
        let e0 = i;
        while i < b.len() && b[i].is_ascii_digit() {
            i += 1;
        }
        if i == e0 {
            return Err(fail());
        }
    }
    if i != b.len() {
        return Err(fail());
    }
    u.parse::<f64>().map_err(|_| fail())
}

/// Python `int()` of a string.
fn py_int(s: &str) -> Result<f64, Error> {
    let t = py_strip(s);
    let cs: Vec<char> = t.chars().collect();
    let mut u = String::new();
    for (i, &c) in cs.iter().enumerate() {
        if c == '_' && i > 0 && i + 1 < cs.len() && cs[i - 1].is_ascii_digit() && cs[i + 1].is_ascii_digit() {
            continue;
        }
        u.push(c);
    }
    let digits = u.strip_prefix(['+', '-']).unwrap_or(&u);
    if digits.is_empty() || !digits.bytes().all(|c| c.is_ascii_digit()) {
        return Err(Error::value(format!("invalid literal for int() with base 10: '{}'", s)));
    }
    u.parse::<f64>().map_err(|_| Error::value("invalid literal for int()"))
}

/// Read a stream info from its XML.
pub fn info_from_xml(xml: &str) -> Result<LslStreamInfo, Error> {
    let root = parse_xml(xml)?;
    let txt = |tag: &str, dflt: &str| -> String {
        match find(Some(&root), tag) {
            Some(el) => match &el.text {
                Some(t) => py_strip(t).to_string(),
                None => dflt.to_string(),
            },
            None => dflt.to_string(),
        }
    };
    let mut labels = Vec::new();
    let mut fid: Vec<(String, String)> = Vec::new();
    let desc = find(Some(&root), "desc");
    if let Some(chs) = find(desc, "channels") {
        for ch in chs.children.iter().filter(|c| c.tag == "channel") {
            labels.push(find(Some(ch), "label").and_then(|l| l.text.as_deref()).map(|t| py_strip(t).to_string()).unwrap_or_default());
        }
    }
    if let Some(f) = find(desc, "fidetype") {
        for c in &f.children {
            let v = c.text.clone().unwrap_or_default();
            match fid.iter_mut().find(|(k, _)| *k == c.tag) {
                Some(e) => e.1 = v,
                None => fid.push((c.tag.clone(), v)),
            }
        }
    }
    let v = txt("nominal_srate", "0");
    let srate = if v.is_empty() { 0.0 } else { py_float(&v).unwrap_or(0.0) };
    let cc = txt("channel_count", "1");
    let channel_count = if cc.is_empty() { 1.0 } else { py_int(&cc)? };
    Ok(LslStreamInfo {
        name: txt("name", ""),
        type_: txt("type", ""),
        channel_count,
        nominal_srate: srate,
        channel_format: txt("channel_format", "float32"),
        source_id: txt("source_id", ""),
        uid: txt("uid", ""),
        hostname: txt("hostname", ""),
        channel_labels: labels,
        fidetype: fid,
    })
}

/// desc/fidetype/nts_header as an object, `None` if absent. Errors if it is not a JSON object.
pub fn nts_header(info: &LslStreamInfo) -> Result<Option<Map>, Error> {
    let raw = match info.fid("nts_header") {
        Some(r) if !r.is_empty() => r,
        _ => return Ok(None),
    };
    match parse_json_opts(raw, true) {
        Err(e) => Err(Error::value(format!("desc/fidetype/nts_header of stream '{}' is not JSON: {}", info.name, e.message))),
        Ok(Value::Obj(m)) => Ok(Some(m)),
        Ok(_) => Err(Error::value(format!("desc/fidetype/nts_header of stream '{}' is not a JSON object", info.name))),
    }
}

/// Error if the desc/fidetype keys break FEP-0002 (binding version, event clock).
pub fn check_binding(info: &LslStreamInfo) -> Result<(), Error> {
    if let Some(b) = info.fid("binding") {
        if !KNOWN_BINDINGS.contains(&py_strip(b)) {
            return Err(Error::value(format!(
                "stream '{}': binding '{}' is not supported (known: {}; FEP-0002 section 9)",
                info.name,
                b,
                KNOWN_BINDINGS.join(",")
            )));
        }
    }
    if let Some(ec) = info.fid("event_clock") {
        if !EVENT_CLOCKS.contains(&py_strip(ec)) {
            return Err(Error::value(format!("stream '{}': event_clock '{}' is not one of {}", info.name, ec, EVENT_CLOCKS.join(","))));
        }
    }
    Ok(())
}

/// Python `math.isclose(a, b, rel_tol)`.
fn is_close(a: f64, b: f64, rel: f64) -> bool {
    a == b || libm::fabs(a - b) <= rel * libm::fabs(a).max(libm::fabs(b))
}

/// Error if an NTS-native frames stream breaks FEP-0002 section 3.
pub fn check_native_frames(info: &LslStreamInfo, header: &Map) -> Result<(), Error> {
    if !NTS_FRAME_FORMATS.contains(&info.channel_format.as_str()) {
        return Err(Error::value(format!(
            "stream '{}': an NTS frames stream must be float32 or double64, not '{}' (FEP-0002 section 3)",
            info.name, info.channel_format
        )));
    }
    let empty = Vec::new();
    let vocab = header.get("vocab").as_arr().unwrap_or(&empty);
    let labels = &info.channel_labels;
    if labels.iter().any(|l| !l.is_empty())
        && (labels.len() != vocab.len()
            || labels.iter().enumerate().any(|(k, lb)| {
                k < vocab.len() && !py_strip(lb).is_empty() && py_strip(lb) != py_strip(&py_str(&vocab[k]))
            }))
    {
        return Err(Error::value(format!("stream '{}': channel labels differ from the vocab order (FEP-0002 section 3)", info.name)));
    }
    if let Value::Num(fp, _) = header.get("frame_period") {
        if *fp > 0.0 && info.nominal_srate > 0.0 && !is_close(1.0 / info.nominal_srate, *fp, SRATE_RTOL) {
            return Err(Error::value(format!(
                "stream '{}': nominal_srate {} is not 1 / frame_period ({}) (FEP-0002 section 3)",
                info.name,
                num_text(info.nominal_srate),
                num_text(*fp)
            )));
        }
    }
    Ok(())
}

pub fn decisions_info_errors(info: &LslStreamInfo) -> Vec<String> {
    let mut errs = Vec::new();
    if info.type_ != MARKERS_TYPE {
        errs.push(format!("type '{}' is not '{}'", info.type_, MARKERS_TYPE));
    }
    if info.channel_count != 1.0 || info.channel_format != "string" {
        errs.push("a decisions stream has 1 channel of format string".to_string());
    }
    if info.nominal_srate != 0.0 {
        errs.push("a decisions stream has an irregular rate (nominal_srate 0)".to_string());
    }
    if info.fid("role") != Some("trust_decisions") {
        errs.push("desc/fidetype/role must be trust_decisions".to_string());
    }
    if info.fid("event_type") != Some("trust_decision") {
        errs.push("desc/fidetype/event_type must be trust_decision".to_string());
    }
    if let Err(e) = check_binding(info) {
        errs.push(e.message);
    }
    errs
}

// --- Python value helpers -----------------------------------------------------------------------

/// Python iteration of a JSON value: list items, string characters, object keys.
pub fn py_iter(x: &Value) -> Result<Vec<Value>, Error> {
    match x {
        Value::Arr(a) => Ok(a.clone()),
        Value::Str(s) => Ok(s.chars().map(|c| Value::Str(c.to_string())).collect()),
        Value::Obj(m) => Ok(m.keys().map(Value::str).collect()),
        other => Err(Error::type_err(format!("'{}' object is not iterable", other.type_name()))),
    }
}

/// Python `float(x)` of a JSON value.
pub fn py_float_of(x: &Value) -> Result<f64, Error> {
    match x {
        Value::Num(v, _) => Ok(*v),
        Value::Bool(b) => Ok(if *b { 1.0 } else { 0.0 }),
        Value::Str(s) => py_float(s),
        other => Err(Error::type_err(format!(
            "float() argument must be a string or a real number, not '{}'",
            other.type_name()
        ))),
    }
}

/// A number for a Python comparison or arithmetic (bool counts as 0 / 1).
fn py_num(x: &Value, what: &str) -> Result<f64, Error> {
    match x {
        Value::Num(v, _) => Ok(*v),
        Value::Bool(b) => Ok(if *b { 1.0 } else { 0.0 }),
        other => Err(Error::type_err(format!("'{}' is not a number ({})", other.type_name(), what))),
    }
}

/// JavaScript `Math.max` (NaN wins).
fn js_max(r: &[f64]) -> f64 {
    let mut m = f64::NEG_INFINITY;
    for &x in r {
        if x.is_nan() {
            return f64::NAN;
        }
        if x > m {
            m = x;
        }
    }
    m
}

// --- mapping (consumer settings) ------------------------------------------------------------

/// The consumer settings (`LSLMapping`). Loosely typed values stay JSON values, as in Python.
#[derive(Debug, Clone)]
pub struct LslMapping {
    pub values: Value,
    pub vocab: Value,
    pub vocab_type: Value,
    pub blank: Value,
    pub source: Value,
    pub clock: Value,
    pub clock_refresh_s: Value,
    pub time_correction_timeout_s: Value,
    pub out_of_order: Value,
    pub clamp_tolerance_s: Value,
    pub gap_factor: Value,
    pub on_gap: Value,
    pub boundary_markers: Vec<Value>,
    pub plain_markers: Value,
    pub merge_window_s: Value,
    pub max_chunk: Value,
    pub reconnect_timeout_s: Value,
    pub reconnect_interval_s: Value,
}

const MAPPING_KEYS: &[&str] = &[
    "values", "vocab", "vocab_type", "blank", "source", "clock", "clock_refresh_s", "time_correction_timeout_s", "out_of_order",
    "clamp_tolerance_s", "gap_factor", "on_gap", "boundary_markers", "plain_markers", "merge_window_s", "max_chunk",
    "reconnect_timeout_s", "reconnect_interval_s",
];

impl LslMapping {
    fn defaults() -> Self {
        LslMapping {
            values: Value::str("auto"),
            vocab: Value::Null,
            vocab_type: Value::Null,
            blank: Value::Null,
            source: Value::Null,
            clock: Value::str("receiver"),
            clock_refresh_s: Value::float(5.0),
            time_correction_timeout_s: Value::float(2.0),
            out_of_order: Value::str("clamp"),
            clamp_tolerance_s: Value::float(0.005),
            gap_factor: Value::float(2.5),
            on_gap: Value::str("mark"),
            boundary_markers: vec![Value::str("segment_end")],
            plain_markers: Value::str("ignore"),
            merge_window_s: Value::float(0.05),
            max_chunk: Value::int(1024.0),
            reconnect_timeout_s: Value::float(30.0),
            reconnect_interval_s: Value::float(0.5),
        }
    }
    fn set(&mut self, k: &str, v: Value) -> Result<(), Error> {
        match k {
            "values" => self.values = v,
            "vocab" => self.vocab = v,
            "vocab_type" => self.vocab_type = v,
            "blank" => self.blank = v,
            "source" => self.source = v,
            "clock" => self.clock = v,
            "clock_refresh_s" => self.clock_refresh_s = v,
            "time_correction_timeout_s" => self.time_correction_timeout_s = v,
            "out_of_order" => self.out_of_order = v,
            "clamp_tolerance_s" => self.clamp_tolerance_s = v,
            "gap_factor" => self.gap_factor = v,
            "on_gap" => self.on_gap = v,
            "boundary_markers" => self.boundary_markers = py_iter(&v)?, // tuple(settings[k])
            "plain_markers" => self.plain_markers = v,
            "merge_window_s" => self.merge_window_s = v,
            "max_chunk" => self.max_chunk = v,
            "reconnect_timeout_s" => self.reconnect_timeout_s = v,
            "reconnect_interval_s" => self.reconnect_interval_s = v,
            _ => return Err(Error::type_err(format!("LSLMapping got an unexpected keyword argument '{}'", k))),
        }
        Ok(())
    }
}

/// Build a mapping as `LSLMapping(merge_window_s=1e9, reconnect_timeout_s=1.0, **settings)`; error on bad settings.
pub fn make_mapping(settings: &Map) -> Result<LslMapping, Error> {
    let mut m = LslMapping::defaults();
    let fixed = ["merge_window_s", "reconnect_timeout_s"];
    m.merge_window_s = Value::float(1e9);
    m.reconnect_timeout_s = Value::float(1.0);
    // tuple(settings["boundary_markers"]) runs before the constructor
    if let Some(b) = settings.get_opt("boundary_markers") {
        py_iter(b)?;
    }
    for (k, v) in settings.iter() {
        if !MAPPING_KEYS.contains(&k) {
            return Err(Error::type_err(format!("LSLMapping got an unexpected keyword argument '{}'", k)));
        }
        if fixed.contains(&k) {
            return Err(Error::type_err(format!("LSLMapping got multiple values for keyword argument '{}'", k)));
        }
        m.set(k, v.clone())?;
    }
    if !str_in(&m.values, &["auto", "log_probs", "probs", "logits"]) {
        return Err(Error::value(format!("unknown values kind {}", repr(&m.values))));
    }
    if !str_in(&m.clock, &["receiver", "sender"]) {
        return Err(Error::value(format!("unknown clock {}", repr(&m.clock))));
    }
    if !str_in(&m.out_of_order, &["clamp", "drop", "error"]) {
        return Err(Error::value(format!("unknown out_of_order {}", repr(&m.out_of_order))));
    }
    if !str_in(&m.on_gap, &["mark", "segment", "abort"]) {
        return Err(Error::value(format!("unknown on_gap {}", repr(&m.on_gap))));
    }
    if !str_in(&m.plain_markers, &["ignore", "hypothesis"]) {
        return Err(Error::value(format!("unknown plain_markers {}", repr(&m.plain_markers))));
    }
    if !m.vocab_type.is_null() && !str_in(&m.vocab_type, VOCAB_TYPES) {
        return Err(Error::value("vocab_type must be one of the VOCAB_TYPES"));
    }
    let bad = "gap_factor must be > 1; merge_window_s and clamp_tolerance_s >= 0";
    if py_num(&m.gap_factor, "gap_factor")? <= 1.0 {
        return Err(Error::value(bad));
    }
    if py_num(&m.merge_window_s, "merge_window_s")? < 0.0 {
        return Err(Error::value(bad));
    }
    if py_num(&m.clamp_tolerance_s, "clamp_tolerance_s")? < 0.0 {
        return Err(Error::value(bad));
    }
    Ok(m)
}

fn resolve_blank(blank: &Value, vocab: &[Value]) -> Result<Value, Error> {
    let b = match blank {
        Value::Null => return Ok(Value::Null),
        Value::Str(s) => {
            let digits = s.trim_start_matches('-');
            if digits.is_empty() || !digits.chars().all(|c| c.is_ascii_digit()) {
                return match vocab.iter().position(|v| py_eq(v, blank)) {
                    Some(k) => Ok(Value::int(k as f64)),
                    None => Err(Error::value(format!("blank token '{}' is not in the vocab", s))),
                };
            }
            py_int(s)?
        }
        Value::Num(x, _) => {
            if !x.is_finite() {
                return Err(Error::value("cannot convert float to integer"));
            }
            libm::trunc(*x)
        }
        Value::Bool(t) => {
            if *t {
                1.0
            } else {
                0.0
            }
        }
        other => return Err(Error::type_err(format!("int() argument must be a string or a number, not '{}'", other.type_name()))),
    };
    if !(b >= 0.0 && b < vocab.len() as f64) {
        return Err(Error::value(format!("blank index {} is outside 0..{}", num_text(b), vocab.len() as i64 - 1)));
    }
    Ok(Value::int(b))
}

fn summary_of(info: &LslStreamInfo) -> Value {
    Value::Obj(Map::from_pairs([
        ("name", Value::str(&info.name)),
        ("type", Value::str(&info.type_)),
        ("source_id", Value::str(&info.source_id)),
        ("uid", Value::str(&info.uid)),
        ("channel_count", Value::int(info.channel_count)),
        ("nominal_srate", Value::float(info.nominal_srate)),
        ("channel_format", Value::str(&info.channel_format)),
    ]))
}

/// The NTS header event for a stream, and the values kind of its channels (port of `build_header`).
pub fn build_header(info: &LslStreamInfo, mapping: &LslMapping, lsl_extra: Map) -> Result<(Map, String), Error> {
    let mut values: String = mapping.values.as_str().unwrap_or("auto").to_string();
    check_binding(info)?;
    let native = nts_header(info)?;
    let mut h = Map::new();
    if let Some(nat) = &native {
        for (k, v) in nat.iter() {
            if k != "type" {
                h.insert(k, v.clone());
            }
        }
        if values == "auto" {
            values = info.fid("values").unwrap_or("log_probs").to_string();
        }
    } else {
        let vocab: Vec<Value> = if info.is_string() {
            if mapping.vocab.is_null() {
                Vec::new()
            } else {
                py_iter(&mapping.vocab)?
            }
        } else {
            let v: Vec<Value> = if mapping.vocab.is_null() {
                info.channel_labels.iter().map(|s| Value::str(s)).collect()
            } else {
                py_iter(&mapping.vocab)?
            };
            if v.is_empty() || v.iter().any(|x| !x.truthy()) {
                return Err(Error::value(format!("stream '{}' has no channel labels; pass the vocab", info.name)));
            }
            v
        };
        let blank = resolve_blank(&mapping.blank, &vocab)?;
        h.insert("spec_version", Value::str(SPEC_VERSION));
        h.insert("vocab", Value::Arr(vocab));
        h.insert("vocab_type", if mapping.vocab_type.truthy() { mapping.vocab_type.clone() } else { Value::str("other") });
        h.insert("blank_id", blank);
        h.insert("source", if mapping.source.truthy() { mapping.source.clone() } else { Value::Str(format!("lsl:{}", info.name)) });
        h.insert(
            "meta",
            Value::Obj(Map::from_pairs([
                ("adapter.name", Value::str(ADAPTER_NAME)),
                ("adapter.version", Value::str(ADAPTER_VERSION)),
                ("data.derived", Value::Bool(true)),
            ])),
        );
        if info.nominal_srate > 0.0 {
            h.insert("frame_period", Value::float(1.0 / info.nominal_srate));
        }
    }
    if values == "auto" {
        values = "log_probs".to_string();
    }
    if !info.is_string() {
        let n = match h.get_opt("vocab") {
            None => Some(0.0),
            Some(Value::Arr(a)) => Some(a.len() as f64),
            Some(Value::Str(s)) => Some(cp_len(s) as f64),
            Some(Value::Obj(m)) => Some(m.len() as f64),
            Some(_) => None,
        };
        match n {
            Some(n) if n == info.channel_count => {}
            Some(n) => {
                return Err(Error::value(format!(
                    "stream '{}' has {} channels but the vocab has {} tokens",
                    info.name,
                    num_text(info.channel_count),
                    num_text(n)
                )))
            }
            None => return Err(Error::type_err("object of this type has no len()")),
        }
        if !NUMERIC_FORMATS.contains(&info.channel_format.as_str()) {
            return Err(Error::value(format!("channel format '{}' cannot carry frames", info.channel_format)));
        }
        if native.is_some() {
            check_native_frames(info, &h)?;
        }
    }
    if !["log_probs", "probs", "logits"].contains(&values.as_str()) {
        return Err(Error::value(format!("unknown values kind '{}'", values)));
    }
    if mapping.source.truthy() && !h.has("source") {
        h.insert("source", mapping.source.clone());
    }
    if !h.has("spec_version") {
        h.insert("spec_version", Value::str(SPEC_VERSION));
    }
    h.insert("clock_domain", Value::str("lsl"));
    let binding = info.fid("binding").filter(|b| !b.is_empty()).unwrap_or(BINDING_VERSION);
    let event_clock = info.fid("event_clock").filter(|b| !b.is_empty()).unwrap_or("source");
    let mut lsl = Map::from_pairs([
        ("stream", summary_of(info)),
        ("clock", mapping.clock.clone()),
        ("values", Value::Str(values.clone())),
        ("binding", Value::str(py_strip(binding))),
        ("event_clock", Value::str(py_strip(event_clock))),
        (
            "adapter",
            Value::Obj(Map::from_pairs([("name", Value::str(ADAPTER_NAME)), ("version", Value::str(ADAPTER_VERSION))])),
        ),
    ]);
    for (k, v) in lsl_extra.iter() {
        lsl.insert(k, v.clone());
    }
    h.insert("lsl", Value::Obj(lsl));
    let mut out = Map::from_pairs([("type", Value::str("header"))]);
    for (k, v) in h.iter() {
        out.insert(k, v.clone());
    }
    Ok((out, values))
}

fn to_log_probs(rows: Vec<Vec<f64>>, values: &str) -> Result<Vec<Vec<f64>>, Error> {
    match values {
        "log_probs" => Ok(rows),
        "probs" => {
            if rows.iter().any(|r| r.iter().any(|x| *x < 0.0)) {
                return Err(Error::value("probability channels must be >= 0"));
            }
            Ok(rows.into_iter().map(|r| r.into_iter().map(libm::log).collect()).collect())
        }
        "logits" => Ok(rows
            .into_iter()
            .map(|r| {
                let m = js_max(&r);
                let lse = m + libm::log(r.iter().map(|x| libm::exp(x - m)).sum::<f64>());
                r.into_iter().map(|x| x - lse).collect()
            })
            .collect()),
        v => Err(Error::value(format!("unknown values kind '{}'", v))),
    }
}

// --- scripted inlets ------------------------------------------------------------------------

/// A numeric sample cell as scripted: a number, or a string that the source converts (or refuses).
#[derive(Debug, Clone)]
enum CellIn {
    N(f64),
    S(String),
}

#[derive(Debug, Clone)]
enum Samples {
    /// String-format streams: the raw JSON value (Python iterates it only when it pulls the chunk).
    Raw(Value),
    /// Numeric streams: rows of cells.
    Rows(Vec<Vec<CellIn>>),
}

#[derive(Debug, Clone)]
enum Chunk {
    Data(Samples, Vec<f64>),
    Lost,
}

#[derive(Debug, Clone)]
struct ScriptedInlet {
    info: LslStreamInfo,
    script: VecDeque<Chunk>,
    tc: f64,
}

/// A failure while pulling: a scripted stream loss, or an error that rejects the scenario.
enum PullErr {
    Lost(String),
    Err(Error),
}

impl From<Error> for PullErr {
    fn from(e: Error) -> Self {
        PullErr::Err(e)
    }
}

impl ScriptedInlet {
    fn pull_chunk(&mut self) -> Result<(Samples, Vec<f64>), PullErr> {
        match self.script.pop_front() {
            None => Ok((Samples::Raw(Value::Arr(Vec::new())), Vec::new())),
            Some(Chunk::Lost) => Err(PullErr::Lost("scripted loss".to_string())),
            Some(Chunk::Data(s, t)) => Ok((s, t)),
        }
    }
}

/// A numeric sample cell: null = -inf, "NaN" / "Infinity" / "-Infinity" strings (as `fep0002._num_in`).
fn num_in(x: &Value) -> Result<CellIn, Error> {
    match x {
        Value::Null => Ok(CellIn::N(f64::NEG_INFINITY)),
        Value::Str(s) => Ok(match s.as_str() {
            "NaN" => CellIn::N(f64::NAN),
            "Infinity" => CellIn::N(f64::INFINITY),
            "-Infinity" => CellIn::N(f64::NEG_INFINITY),
            _ => CellIn::S(s.clone()), // converted (or refused) by the source, as np.asarray
        }),
        other => Ok(CellIn::N(py_float_of(other)?)),
    }
}

fn make_inlet(spec: &Value) -> Result<ScriptedInlet, Error> {
    let spec = match spec {
        Value::Obj(m) if m.has("info_xml") => m,
        _ => return Err(Error::type_err("an inlet needs info_xml")),
    };
    let xml = spec.get("info_xml").as_str().ok_or_else(|| Error::type_err("info_xml must be a string"))?;
    let info = info_from_xml(xml)?;
    let mut script = VecDeque::new();
    let chunks = match spec.get_opt("chunks") {
        Some(c) => py_iter(c)?,
        None => Vec::new(),
    };
    for ch in &chunks {
        if matches!(ch, Value::Str(s) if s == "lost") {
            script.push_back(Chunk::Lost);
            continue;
        }
        let ch = match ch {
            Value::Obj(m) => m,
            _ => return Err(Error::type_err("a chunk must be an object or \"lost\"")),
        };
        let samples_v = ch.get_opt("samples").ok_or_else(|| Error::type_err("a chunk needs samples and timestamps"))?;
        let samples = if info.is_string() {
            Samples::Raw(samples_v.clone())
        } else {
            let mut rows = Vec::new();
            for row in &py_iter(samples_v)? {
                rows.push(py_iter(row)?.iter().map(num_in).collect::<Result<Vec<_>, _>>()?);
            }
            Samples::Rows(rows)
        };
        let stamps_v = ch.get_opt("timestamps").ok_or_else(|| Error::type_err("a chunk needs samples and timestamps"))?;
        let stamps = py_iter(stamps_v)?.iter().map(py_float_of).collect::<Result<Vec<_>, _>>()?;
        script.push_back(Chunk::Data(samples, stamps));
    }
    let tc = match spec.get_opt("time_correction") {
        Some(v) => py_float_of(v)?,
        None => 0.0,
    };
    Ok(ScriptedInlet { info, script, tc })
}

// --- the event source -----------------------------------------------------------------------

#[derive(Debug, Default, Clone)]
struct Stats {
    samples: usize,
    frames: usize,
    markers: usize,
    ignored_markers: usize,
    bad_markers: usize,
    clamped: usize,
    dropped_out_of_order: usize,
    gaps: usize,
    lost: usize,
    reconnects: usize,
    late_releases: usize,
}

/// The deterministic receiver clock of the scenario runner.
struct Clock {
    ticks: u64,
}

impl Clock {
    fn tick(&mut self) -> f64 {
        let t = 1000.0 + self.ticks as f64 * 1e-3;
        self.ticks += 1;
        t
    }
}

struct ClockSync {
    by_host: BTreeMap<String, (f64, u64, f64)>,
}

/// The shared state of the event source (everything but the readers).
struct SrcState {
    stats: Stats,
    mapping: LslMapping,
    clock: Clock,
    sync: ClockSync,
    values: String,
    seq_n: u64,
    n_marker: u64,
}

impl SrcState {
    fn next_seq(&mut self) -> u64 {
        let s = self.seq_n;
        self.seq_n += 1;
        s
    }

    fn offset(&mut self, host: &str, tc: f64, force: bool) -> Result<f64, Error> {
        if self.mapping.clock.as_str() == Some("sender") {
            return Ok(0.0);
        }
        let now = self.clock.tick();
        let refresh = self.mapping.clock_refresh_s.clone();
        let o = self.sync.by_host.entry(host.to_string()).or_insert((0.0, 0, f64::NEG_INFINITY));
        // Python `force or o.n == 0 or now - o.updated_at >= refresh_s` (short circuit)
        let due = force || o.1 == 0 || (now - o.2) >= py_num(&refresh, "clock_refresh_s")?;
        if due && tc.is_finite() {
            o.0 = tc;
            o.1 += 1;
            o.2 = now;
        }
        Ok(o.0)
    }

    fn marker_event(&mut self, s_in: &Value, t: f64, offset: f64, event_clock: &str) -> Option<Map> {
        self.stats.markers += 1;
        let s = py_str(s_in);
        let txt = py_strip(&s).to_string();
        if txt.starts_with('{') {
            if let Ok(Value::Obj(mut ev)) = parse_json_opts(&txt, true) {
                if ev.get("type").is_str() {
                    ev.insert("lsl_t", Value::float(t));
                    if event_clock == "lsl" && offset != 0.0 {
                        for k in EVENT_TIME_KEYS {
                            if let Value::Num(v, _) = ev.get(k) {
                                let nv = *v + offset;
                                ev.insert(*k, Value::float(nv));
                            }
                        }
                    }
                    if ev.get("type").as_str() == Some("header") {
                        if !ev.has("spec_version") {
                            ev.insert("spec_version", Value::str(SPEC_VERSION));
                        }
                        ev.insert("clock_domain", Value::str("lsl"));
                    }
                    return Some(ev);
                }
            }
            self.stats.bad_markers += 1;
            return None;
        }
        let tv = Value::Str(txt.clone());
        if py_in(&tv, &self.mapping.boundary_markers) {
            return Some(Map::from_pairs([("type", Value::str("segment_end")), ("lsl_t", Value::float(t)), ("marker", tv)]));
        }
        if self.mapping.plain_markers.as_str() == Some("hypothesis") && !txt.is_empty() {
            self.n_marker += 1;
            let item = Value::Obj(Map::from_pairs([("text", tv), ("score", Value::float(0.0))]));
            return Some(Map::from_pairs([
                ("type", Value::str("hypothesis")),
                ("id", Value::Str(format!("lsl-{}", self.n_marker))),
                ("is_final", Value::Bool(true)),
                ("score_semantics", Value::str("none")),
                ("nbest", Value::Arr(vec![item])),
                ("lsl_t", Value::float(t)),
            ]));
        }
        self.stats.ignored_markers += 1;
        None
    }
}

type Item = (f64, u64, Map);

#[derive(Clone, Copy, PartialEq, Eq)]
enum Role {
    Frames,
    Events,
}

struct Reader {
    role: Role,
    inlet: ScriptedInlet,
    host: String,
    event_clock: String,
    last_t: f64,
    seen_t: f64,
    period: Option<f64>,
    json_frames_last_t: f64,
    clamped_pending: usize,
    dropped_pending: usize,
    lost_since: Option<f64>,
    has_reopen: bool,
}

impl Reader {
    fn new(role: Role, inlet: ScriptedInlet, has_reopen: bool) -> Result<Reader, Error> {
        let mut r = Reader {
            role,
            inlet: inlet.clone(),
            host: String::new(),
            event_clock: "source".to_string(),
            last_t: f64::NEG_INFINITY,
            seen_t: f64::NEG_INFINITY,
            period: None,
            json_frames_last_t: f64::NEG_INFINITY,
            clamped_pending: 0,
            dropped_pending: 0,
            lost_since: None,
            has_reopen,
        };
        r.attach(inlet)?;
        Ok(r)
    }

    fn attach(&mut self, inlet: ScriptedInlet) -> Result<(), Error> {
        let info = &inlet.info;
        self.host = [&info.hostname, &info.source_id, &info.name].iter().find(|s| !s.is_empty()).map(|s| s.to_string()).unwrap_or_default();
        check_binding(info)?;
        self.event_clock = py_strip(info.fid("event_clock").filter(|e| !e.is_empty()).unwrap_or("source")).to_string();
        self.inlet = inlet;
        self.last_t = f64::NEG_INFINITY;
        self.seen_t = f64::NEG_INFINITY;
        self.period = None;
        self.json_frames_last_t = f64::NEG_INFINITY;
        self.clamped_pending = 0;
        self.dropped_pending = 0;
        Ok(())
    }

    fn set_period(&mut self, header: &Map) -> Result<(), Error> {
        let mut fp = if self.role == Role::Frames { header.get("frame_period").clone() } else { Value::Null };
        if fp.is_null() && self.inlet.info.nominal_srate > 0.0 && self.role == Role::Frames {
            fp = Value::float(1.0 / self.inlet.info.nominal_srate);
        }
        self.period = if fp.truthy() { Some(py_float_of(&fp)?) } else { None };
        Ok(())
    }

    fn order(&mut self, st: &mut SrcState, t: f64, last: f64) -> Result<Option<f64>, Error> {
        if t > last {
            return Ok(Some(t));
        }
        let mode = st.mapping.out_of_order.as_str().unwrap_or("");
        if mode == "error" {
            return Err(Error::value(format!(
                "LSL timestamp {} does not increase (last {}) on stream '{}'",
                num_text(t),
                num_text(last),
                self.inlet.info.name
            )));
        }
        if mode == "clamp" && last - t <= py_num(&st.mapping.clamp_tolerance_s, "clamp_tolerance_s")? {
            st.stats.clamped += 1;
            self.clamped_pending += 1;
            return Ok(Some(last + CLAMP_STEP_S));
        }
        st.stats.dropped_out_of_order += 1;
        self.dropped_pending += 1;
        Ok(None)
    }

    fn pull(&mut self, st: &mut SrcState) -> Result<Vec<Item>, PullErr> {
        let (samples, stamps) = self.inlet.pull_chunk()?;
        if stamps.is_empty() {
            return Ok(Vec::new());
        }
        let off = st.offset(&self.host.clone(), self.inlet.tc, false)?;
        st.clock.tick();
        st.stats.samples += stamps.len();
        let mut items: Vec<Item> = Vec::new();
        if self.role == Role::Events {
            let raw: Vec<Value> = match &samples {
                Samples::Raw(r) => py_iter(r)?, // zip(samples, stamps)
                Samples::Rows(_) => Vec::new(),
            };
            let n = raw.len().min(stamps.len());
            for k in 0..n {
                let s = &raw[k];
                let t = stamps[k] + off;
                let cell = match s {
                    Value::Arr(a) => match a.first() {
                        Some(c) => c,
                        None => return Err(Error::value("list index out of range").into()),
                    },
                    other => other,
                };
                let ev = match st.marker_event(cell, t, off, &self.event_clock.clone()) {
                    Some(ev) => ev,
                    None => continue,
                };
                let ev = if ev.get("type").as_str() == Some("frame") {
                    let tt = match self.order(st, t, self.json_frames_last_t)? {
                        Some(tt) => tt,
                        None => continue,
                    };
                    self.json_frames_last_t = tt;
                    let mut e = ev.clone();
                    let ts = e.get("t").clone();
                    e.insert("t", Value::float(tt));
                    e.insert("t_source", ts);
                    e
                } else {
                    ev
                };
                items.push((t, st.next_seq(), ev));
            }
            self.seen_t = self.seen_t.max(stamps[stamps.len() - 1] + off);
            return Ok(items);
        }
        // numeric: np.asarray(samples, float64)
        let rows_in = match samples {
            Samples::Rows(r) => r,
            Samples::Raw(_) => Vec::new(),
        };
        let mut arr: Vec<Vec<f64>> = Vec::with_capacity(rows_in.len());
        for r in &rows_in {
            let mut row = Vec::with_capacity(r.len());
            for c in r {
                row.push(match c {
                    CellIn::N(x) => *x,
                    CellIn::S(s) => py_float(s)?,
                });
            }
            arr.push(row);
        }
        if arr.is_empty() {
            // np.asarray([]).reshape(len(stamps), -1) fails
            return Err(Error::value("cannot reshape an empty chunk into rows").into());
        }
        if arr.iter().any(|r| r.len() != arr[0].len()) {
            return Err(Error::value("setting an array element with a sequence (ragged chunk)").into());
        }
        let mut keep_rows: Vec<usize> = Vec::new();
        let mut keep_t: Vec<f64> = Vec::new();
        for (i, ts) in stamps.iter().enumerate() {
            let t = ts + off;
            let tt = match self.order(st, t, self.last_t)? {
                Some(tt) => tt,
                None => continue,
            };
            if let Some(p) = self.period {
                if self.last_t.is_finite() && tt - self.last_t > py_num(&st.mapping.gap_factor, "gap_factor")? * p {
                    let g = self.gap(st, self.last_t, tt, &keep_rows, &keep_t, &arr)?;
                    items.extend(g);
                    keep_rows.clear();
                    keep_t.clear();
                }
            }
            keep_rows.push(i);
            keep_t.push(tt);
            self.last_t = tt;
        }
        let f = self.frames(st, &arr, &keep_rows, &keep_t)?;
        items.extend(f);
        self.seen_t = self.seen_t.max(self.last_t);
        Ok(items)
    }

    fn frames(&mut self, st: &mut SrcState, arr: &[Vec<f64>], rows: &[usize], times: &[f64]) -> Result<Vec<Item>, Error> {
        if rows.is_empty() {
            return Ok(Vec::new());
        }
        let mut chunk = Vec::with_capacity(rows.len());
        for &r in rows {
            match arr.get(r) {
                Some(row) => chunk.push(row.clone()),
                None => return Err(Error::value("index out of bounds (more timestamps than samples)")),
            }
        }
        let lp = to_log_probs(chunk, &st.values)?;
        let mut items = Vec::new();
        for (k, &t) in times.iter().enumerate() {
            st.stats.frames += 1;
            let mut ev = Map::from_pairs([
                ("type", Value::str("frame")),
                ("t", Value::float(t)),
                ("log_probs", Value::Arr(lp[k].iter().map(|&x| Value::float(x)).collect())),
            ]);
            if self.clamped_pending > 0 {
                ev.insert("lsl_clamped", Value::int(self.clamped_pending as f64));
                self.clamped_pending = 0;
            }
            if self.dropped_pending > 0 {
                ev.insert("lsl_dropped_before", Value::int(self.dropped_pending as f64));
                self.dropped_pending = 0;
            }
            items.push((t, st.next_seq(), ev));
        }
        Ok(items)
    }

    fn gap(&mut self, st: &mut SrcState, t0: f64, t1: f64, rows: &[usize], times: &[f64], arr: &[Vec<f64>]) -> Result<Vec<Item>, Error> {
        st.stats.gaps += 1;
        let mut items = self.frames(st, arr, rows, times)?;
        // Python int(round(x)) - 1: half to even; an error for inf / nan
        let missing = match self.period {
            Some(p) if p != 0.0 => {
                let q = (t1 - t0) / p;
                if !q.is_finite() {
                    return Err(Error::value("cannot convert float infinity or NaN to integer"));
                }
                Value::int(libm::rint(q) - 1.0)
            }
            _ => Value::Null,
        };
        let tg = t1 - 1e-9;
        let info = [
            ("t_start", Value::float(t0)),
            ("t_end", Value::float(t1)),
            ("missing_frames", missing),
            ("stream", Value::str(&self.inlet.info.name)),
        ];
        let mut ev = match st.mapping.on_gap.as_str() {
            Some("mark") => Map::from_pairs([("type", Value::str("gap"))]),
            Some("segment") => Map::from_pairs([
                ("type", Value::str("segment_end")),
                ("lsl_t", Value::float(tg)),
                ("reason", Value::str("gap")),
            ]),
            _ => Map::from_pairs([("type", Value::str("lsl_status")), ("status", Value::str("gap_abort"))]),
        };
        for (k, v) in info {
            ev.insert(k, v);
        }
        items.push((tg, st.next_seq(), ev));
        Ok(items)
    }
}

struct EventSource {
    st: SrcState,
    readers: Vec<Reader>,
    heap: Vec<(f64, u64, f64, Map)>,
    last_released: f64,
    header_ev: Option<Map>,
    pending_header: bool,
    /// The reconnect inlets of the primary stream (`primary_after_reconnect`).
    pending: Vec<Value>,
}

impl EventSource {
    fn new(primary: ScriptedInlet, events: Option<ScriptedInlet>, mapping: LslMapping, reopen: bool, pending: Vec<Value>) -> Result<Self, Error> {
        let role = if primary.info.is_string() { Role::Events } else { Role::Frames };
        let st = SrcState {
            stats: Stats::default(),
            mapping,
            clock: Clock { ticks: 0 },
            sync: ClockSync { by_host: BTreeMap::new() },
            values: "log_probs".to_string(),
            seq_n: 0,
            n_marker: 0,
        };
        let mut readers = vec![Reader::new(role, primary, reopen)?];
        if let Some(ev) = events {
            if !ev.info.is_string() {
                return Err(Error::value("the events stream must have the string channel format"));
            }
            readers.push(Reader::new(Role::Events, ev, false)?);
        }
        Ok(EventSource { st, readers, heap: Vec::new(), last_released: f64::NEG_INFINITY, header_ev: None, pending_header: true, pending })
    }

    fn header(&mut self) -> Result<Map, Error> {
        if self.header_ev.is_none() {
            let host = self.readers[0].host.clone();
            let tc = self.readers[0].inlet.tc;
            let off = self.st.offset(&host, tc, true)?;
            let mut extra = Map::new();
            extra.insert("time_correction_s", if self.st.mapping.clock.as_str() == Some("receiver") { Value::float(off) } else { Value::Null });
            if self.readers.len() > 1 {
                extra.insert("events_stream", summary_of(&self.readers[1].inlet.info));
                extra.insert("event_clock", Value::Str(self.readers[1].event_clock.clone()));
            }
            let (h, values) = build_header(&self.readers[0].inlet.info, &self.st.mapping, extra)?;
            self.st.values = values;
            for rd in self.readers.iter_mut() {
                rd.set_period(&h)?;
            }
            self.header_ev = Some(h);
        }
        Ok(self.header_ev.clone().unwrap_or_default())
    }

    fn reopen(&mut self) -> Result<ScriptedInlet, Error> {
        if !self.pending.is_empty() && !self.pending[0].is_null() {
            let spec = self.pending.remove(0);
            return make_inlet(&spec);
        }
        Err(Error::value("no stream"))
    }

    fn poll(&mut self) -> Result<Vec<Map>, Error> {
        let mut out = Vec::new();
        if self.pending_header {
            out.push(self.header()?);
            self.pending_header = false;
        }
        let now = self.st.clock.tick();
        for i in 0..self.readers.len() {
            if self.readers[i].lost_since.is_some() {
                let r = self.try_reconnect(i, now)?;
                out.extend(r);
                continue;
            }
            let res = {
                let (readers, st) = (&mut self.readers, &mut self.st);
                readers[i].pull(st)
            };
            let items = match res {
                Ok(items) => items,
                Err(PullErr::Lost(why)) => {
                    let l = self.lost(i, &why, now);
                    out.extend(l);
                    continue;
                }
                Err(PullErr::Err(e)) => return Err(e),
            };
            let arrival = self.st.clock.tick();
            for (t, sq, ev) in items {
                self.heap_push((t, sq, arrival, ev));
            }
        }
        let now2 = self.st.clock.tick();
        out.extend(self.release(now2, false)?);
        Ok(out)
    }

    fn drain(&mut self) -> Result<Vec<Map>, Error> {
        self.release(f64::INFINITY, true)
    }

    fn heap_push(&mut self, x: (f64, u64, f64, Map)) {
        self.heap.push(x);
        self.heap.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(core::cmp::Ordering::Equal).then(a.1.cmp(&b.1)));
    }

    fn release(&mut self, now: f64, force: bool) -> Result<Vec<Map>, Error> {
        let mut out = Vec::new();
        let mw = py_num(&self.st.mapping.merge_window_s, "merge_window_s")?;
        while let Some(first) = self.heap.first() {
            let (t, arrival) = (first.0, first.2);
            let ok = force
                || self.readers.len() == 1
                || self.readers.iter().filter(|r| r.lost_since.is_none()).all(|r| r.seen_t >= t)
                || now - arrival >= mw;
            if !ok {
                break;
            }
            let (t, _, _, ev) = self.heap.remove(0);
            if t < self.last_released {
                self.st.stats.late_releases += 1;
            }
            self.last_released = self.last_released.max(t);
            out.push(ev);
        }
        Ok(out)
    }

    fn lost(&mut self, i: usize, why: &str, now: f64) -> Vec<Map> {
        self.st.stats.lost += 1;
        self.readers[i].lost_since = Some(now);
        let mut held = self.release(f64::INFINITY, true).unwrap_or_default();
        held.push(Map::from_pairs([
            ("type", Value::str("lsl_status")),
            ("status", Value::str("lost")),
            ("stream", Value::str(&self.readers[i].inlet.info.name)),
            ("detail", Value::str(why)),
        ]));
        held
    }

    fn try_reconnect(&mut self, i: usize, now: f64) -> Result<Vec<Map>, Error> {
        let lost_since = self.readers[i].lost_since.unwrap_or(now);
        let timeout = py_num(&self.st.mapping.reconnect_timeout_s, "reconnect_timeout_s")?;
        if !self.readers[i].has_reopen || now - lost_since > timeout {
            return Err(Error::new(ErrorKind::Value, format!("stream '{}' lost and not reconnected", self.readers[i].inlet.info.name)));
        }
        let inlet = match self.reopen() {
            Ok(inlet) => inlet,
            Err(_) => return Ok(Vec::new()),
        };
        self.readers[i].attach(inlet)?;
        self.readers[i].lost_since = None;
        self.st.stats.reconnects += 1;
        let mut out = vec![Map::from_pairs([
            ("type", Value::str("lsl_status")),
            ("status", Value::str("reconnected")),
            ("stream", Value::str(&self.readers[i].inlet.info.name)),
        ])];
        if i == 0 {
            self.header_ev = None;
            out.push(self.header()?);
        } else {
            let h = self.header()?;
            self.readers[i].set_period(&h)?;
        }
        Ok(out)
    }
}

// --- the structural trust model + runner ------------------------------------------------------

#[derive(PartialEq, Eq, Clone, Copy)]
enum Route {
    Frames,
    Hypothesis,
}

/// Counts what the reference StreamingTrustLayer does, without decoding. Errors as it does.
struct StructuralLayer {
    route: Route,
    header: Option<Map>,
    v: usize,
    last_t: f64,
    ended: bool,
    rows: usize,
    hyp: bool,
    has_session: bool,
    decisions: usize,
    finals: usize,
}

impl StructuralLayer {
    fn pending(&self) -> bool {
        self.has_session && (self.rows > 0 || self.hyp)
    }

    fn push(&mut self, ev: &Map) -> Result<(), Error> {
        let typ = match ev.get("type") {
            Value::Str(s) => s.clone(),
            _ => return Err(Error::event("an event must be an object with a string \"type\"")),
        };
        self.has_session = true;
        if typ == "header" {
            self.end()?;
            self.v = check_header(ev)?;
            self.header = Some(ev.clone());
            self.last_t = f64::NEG_INFINITY;
            self.ended = false;
            self.rows = 0;
            self.hyp = false;
        } else if self.header.is_none() {
            return Err(Error::event(format!("'{}' event before the header (spec 6.2 rule 1)", typ)));
        } else if self.ended {
            // lines after the end marker are ignored
        } else if typ == "frame" {
            let t = match ev.get("t") {
                Value::Num(t, _) if t.is_finite() => *t,
                _ => return Err(Error::event("frame needs a finite numeric t")),
            };
            if !(t > self.last_t) {
                return Err(Error::event(format!("frame t {} does not increase (last {}; spec 6.2 rule 4)", num_text(t), num_text(self.last_t))));
            }
            frame_row(ev, self.v)?;
            self.last_t = t;
            if self.route == Route::Frames {
                self.rows += 1;
            }
        } else if typ == "hypothesis" {
            let fin = check_hypothesis(ev)?;
            if self.route == Route::Hypothesis {
                self.hyp = true;
                if fin {
                    self.end()?;
                } else {
                    self.decisions += 1; // a provisional decision (StreamingConfig.provisional = True)
                }
            }
        } else if typ == "segment_end" {
            self.end()?;
        } else if typ == "end" {
            self.end()?;
            self.ended = true;
        }
        Ok(())
    }

    /// Close the utterance: one final decision if it had input.
    fn end(&mut self) -> Result<(), Error> {
        let h = match &self.header {
            Some(h) => h,
            None => return Ok(()),
        };
        if (self.route == Route::Frames && self.rows > 0) || (self.route == Route::Hypothesis && self.hyp) {
            if self.route == Route::Frames {
                // blank_id null = no blank class (spec 3.1): the greedy decoder still decodes (vector L32).
                check_stream_fields(h)?;
            }
            self.decisions += 1;
            self.finals += 1;
        }
        self.rows = 0;
        self.hyp = false;
        Ok(())
    }

    fn abort(&mut self) {
        self.rows = 0;
        self.hyp = false;
    }
}

/// The NeuralTextStream constructor checks on the header fields of a decoded utterance.
fn check_stream_fields(h: &Map) -> Result<(), Error> {
    let src = h.get_opt("source").cloned().unwrap_or(Value::str("unknown"));
    if !matches!(&src, Value::Str(s) if !s.is_empty()) {
        return Err(Error::value("source must be a non-empty string"));
    }
    let fp = h.get("frame_period");
    if !fp.is_null() && !matches!(fp, Value::Num(x, _) if x.is_finite() && *x > 0.0) {
        return Err(Error::value("frame_period must be a positive finite number"));
    }
    let lat = h.get("latency");
    if !lat.is_null() && !matches!(lat, Value::Num(x, _) if x.is_finite() && *x >= 0.0) {
        return Err(Error::value("latency must be a finite number >= 0"));
    }
    let meta = h.get("meta");
    if meta.truthy() && !meta.is_obj() {
        return Err(Error::type_err("meta must be a dict"));
    }
    Ok(())
}

/// Play an `inlet` scenario. Errors on rejection. Returns the FEP-0002 section 10 values.
pub fn run_inlet_scenario(sc: &Map) -> Result<Value, Error> {
    let inl = sc.get_opt("inlets").ok_or_else(|| Error::type_err("a scenario needs inlets"))?;
    let inl = inl.as_obj().ok_or_else(|| Error::type_err("a scenario needs inlets"))?;
    let primary = make_inlet(inl.get_opt("primary").ok_or_else(|| Error::type_err("inlets needs primary"))?)?;
    let events = if inl.get("events").truthy() { Some(make_inlet(inl.get("events"))?) } else { None };
    let after = inl.get("primary_after_reconnect").clone();
    let settings: Map = match sc.get("consumer_settings") {
        v if !v.truthy() => Map::new(),
        Value::Obj(m) => m.clone(),
        Value::Arr(a) => {
            // dict(list of pairs)
            let mut m = Map::new();
            for p in a {
                let kv = py_iter(p)?;
                if kv.len() != 2 {
                    return Err(Error::value("dictionary update sequence element has the wrong length"));
                }
                match &kv[0] {
                    Value::Str(k) => m.insert(k.clone(), kv[1].clone()),
                    _ => return Err(Error::type_err("keywords must be strings")),
                }
            }
            m
        }
        other => return Err(Error::type_err(format!("'{}' object is not iterable as a dict", other.type_name()))),
    };
    let mapping = make_mapping(&settings)?;
    let mut src = EventSource::new(primary, events, mapping, after.truthy(), vec![after.clone()])?;
    let route = match sc.get_opt("route") {
        None => Route::Frames,
        Some(Value::Str(r)) if r == "frames" => Route::Frames,
        Some(Value::Str(r)) if r == "auto" || r == "hypothesis" => Route::Hypothesis, // auto without decode_fn = hypothesis
        Some(r) => return Err(Error::value(format!("unknown route {}", repr(r)))),
    };
    let mut layer = StructuralLayer {
        route,
        header: None,
        v: 0,
        last_t: f64::NEG_INFINITY,
        ended: false,
        rows: 0,
        hyp: false,
        has_session: false,
        decisions: 0,
        finals: 0,
    };
    let mut seen: Vec<Map> = Vec::new();
    let mut aborted = 0usize;
    let mut ended = false;
    src.st.clock.tick(); // runner init: _last_event_at = source.clock()
    let receiver = src.st.mapping.clock.as_str() == Some("receiver");

    fn handle(
        evs: &[Map],
        src: &mut EventSource,
        layer: &mut StructuralLayer,
        aborted: &mut usize,
        ended: &mut bool,
        receiver: bool,
    ) -> Result<(), Error> {
        src.st.clock.tick();
        for ev in evs {
            let typ = ev.get("type").as_str().unwrap_or("");
            if typ == "lsl_status" {
                if matches!(ev.get("status").as_str(), Some("lost") | Some("gap_abort")) {
                    if layer.pending() {
                        *aborted += 1;
                    }
                    layer.abort();
                }
                continue;
            }
            if typ == "gap" {
                continue;
            }
            let before = layer.decisions;
            layer.push(ev)?;
            // _emit: one clock() per decision with a numeric trigger time (receiver clock)
            let trig = match ev.get_opt("lsl_t") {
                Some(v) => v.clone(),
                None if typ == "frame" => ev.get("t").clone(),
                None => Value::Null,
            };
            if receiver && trig.is_num() {
                for _ in before..layer.decisions {
                    src.st.clock.tick();
                }
            }
            if typ == "end" {
                *ended = true;
            }
        }
        Ok(())
    }

    let mut idle = 0;
    for _ in 0..10000 {
        let n0 = seen.len();
        let evs = src.poll()?;
        seen.extend(evs.iter().cloned());
        handle(&evs, &mut src, &mut layer, &mut aborted, &mut ended, receiver)?;
        src.st.clock.tick();
        if ended {
            break;
        }
        let busy = src.readers.iter().any(|r| r.lost_since.is_some() || !r.inlet.script.is_empty());
        idle = if busy || seen.len() != n0 { 0 } else { idle + 1 };
        if idle >= 3 {
            break;
        }
    }
    let drained = src.drain()?;
    seen.extend(drained.iter().cloned());
    handle(&drained, &mut src, &mut layer, &mut aborted, &mut ended, receiver)?;
    if !ended {
        layer.end()?;
    }

    let frames: Vec<&Map> = seen.iter().filter(|e| e.get("type").as_str() == Some("frame")).collect();
    let mut rows: Vec<Vec<f64>> = Vec::new();
    for e in &frames {
        let lp = e.get_opt("log_probs").ok_or_else(|| Error::value("KeyError: 'log_probs'"))?;
        rows.push(py_iter(lp)?.iter().map(py_float_of).collect::<Result<_, _>>()?);
    }
    if rows.iter().any(|r| r.len() != rows[0].len()) {
        return Err(Error::value("frames have different lengths"));
    }
    let mut types: BTreeMap<String, usize> = BTreeMap::new();
    for e in &seen {
        if let Value::Str(t) = e.get("type") {
            if t != "lsl_status" {
                *types.entry(t.clone()).or_insert(0) += 1;
            }
        }
    }
    let head = seen.iter().find(|e| e.get("type").as_str() == Some("header")).ok_or_else(|| Error::value("no header"))?;
    let lsl = head.get("lsl");
    let vocab_size = match head.get("vocab") {
        Value::Arr(a) => a.len(),
        _ => return Err(Error::type_err("the header vocab has no length")),
    };
    let neg: usize = rows.iter().map(|r| r.iter().filter(|v| **v == f64::NEG_INFINITY).count()).sum();
    let n = |x: usize| Value::int(x as f64);
    let st = &src.st.stats;
    Ok(Value::Obj(Map::from_pairs([
        ("clock_domain", head.get("clock_domain").clone()),
        ("binding", lsl.get("binding").clone()),
        ("event_clock", lsl.get("event_clock").clone()),
        ("vocab_size", n(vocab_size)),
        ("frames", n(frames.len())),
        ("first_frame_t", frames.first().map_or(Value::Null, |f| f.get("t").clone())),
        ("rows_sha256", Value::Str(sha256_f64_rows(&rows))),
        ("neg_inf_cells", n(neg)),
        ("event_types", Value::Obj(Map::from_pairs(types.into_iter().map(|(k, v)| (k, Value::int(v as f64)))))),
        (
            "hypothesis_times",
            Value::Arr(
                seen.iter()
                    .filter(|e| e.get("type").as_str() == Some("hypothesis"))
                    .map(|e| Value::Arr(vec![e.get("t_start").clone(), e.get("t_end").clone()]))
                    .collect(),
            ),
        ),
        ("marker_lsl_t", Value::Arr(seen.iter().filter_map(|e| e.get_opt("lsl_t").cloned()).collect())),
        ("decisions", n(layer.decisions)),
        ("final_decisions", n(layer.finals)),
        ("aborted_utterances", n(aborted)),
        ("gaps", n(st.gaps)),
        ("clamped", n(st.clamped)),
        ("dropped_out_of_order", n(st.dropped_out_of_order)),
        ("reconnects", n(st.reconnects)),
        ("bad_markers", n(st.bad_markers)),
        ("ignored_markers", n(st.ignored_markers)),
    ])))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn xml_and_floats() {
        let x = parse_xml("<?xml version=\"1.0\"?><info><name>a &amp; b</name><hostname /><desc><fidetype><values>probs</values></fidetype></desc></info>").unwrap();
        assert_eq!(x.tag, "info");
        let info = info_from_xml("<info><name> n </name><nominal_srate>1_0.5</nominal_srate><desc><fidetype><binding>nts-lsl/0.1</binding></fidetype></desc></info>").unwrap();
        assert_eq!(info.name, "n");
        assert_eq!(info.nominal_srate, 10.5);
        assert_eq!(info.fid("binding"), Some("nts-lsl/0.1"));
        assert!(py_float(" -Inf ").unwrap().is_infinite());
        assert!(py_float("1e").is_err());
        assert_eq!(py_float(".5").unwrap(), 0.5);
        assert!(parse_xml("<a><b></a>").is_err());
    }
}
