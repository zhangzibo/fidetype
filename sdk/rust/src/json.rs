//! Strict JSON with the semantics of the Python reference
//! (`json.loads(..., parse_constant=reject)`).
//!
//! - A number keeps a flag "written as a float literal" (`1.0`, `1e3`).
//!   Python keeps `1.0` (a float) apart from `1` (an int), and rules such as
//!   "seq is an integer >= 0" reject `1.0`. [`Value::is_int`] reads the flag.
//! - Objects keep their key order. A later duplicate key replaces the value
//!   in place (Python `dict` behaviour).
//! - `NaN`, `Infinity` and `-Infinity` are rejected unless the caller allows
//!   them (Python's plain `json.loads`, used for LSL markers and scenarios).
//! - A lone UTF-16 surrogate escape (`"\ud800"`) becomes U+FFFD (Rust strings
//!   are UTF-8); it still counts as one code point.
//! - [`py_lines`] splits text as Python `str.splitlines()`.

use alloc::string::{String, ToString};
use alloc::vec::Vec;
use core::fmt::Write as _;

use crate::error::{Error, ErrorKind};

/// A JSON value.
#[derive(Debug, Clone)]
pub enum Value {
    Null,
    Bool(bool),
    /// A number (always f64, as JavaScript) and `true` if it was written as a float literal.
    Num(f64, bool),
    Str(String),
    Arr(Vec<Value>),
    Obj(Map),
}

/// The shared `null` returned for absent keys.
pub static NULL: Value = Value::Null;

/// A JSON object with insertion order (Python `dict`).
#[derive(Debug, Clone, Default)]
pub struct Map {
    entries: Vec<(String, Value)>,
}

impl Map {
    pub const fn new() -> Self {
        Map { entries: Vec::new() }
    }
    pub fn len(&self) -> usize {
        self.entries.len()
    }
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
    fn pos(&self, k: &str) -> Option<usize> {
        self.entries.iter().position(|(kk, _)| kk == k)
    }
    /// The value of `k`, or `None` if the key is absent.
    pub fn get_opt(&self, k: &str) -> Option<&Value> {
        self.pos(k).map(|i| &self.entries[i].1)
    }
    /// Python `dict.get(k)`: the value, or `null` if the key is absent.
    pub fn get(&self, k: &str) -> &Value {
        self.get_opt(k).unwrap_or(&NULL)
    }
    pub fn get_mut(&mut self, k: &str) -> Option<&mut Value> {
        match self.pos(k) {
            Some(i) => Some(&mut self.entries[i].1),
            None => None,
        }
    }
    pub fn has(&self, k: &str) -> bool {
        self.pos(k).is_some()
    }
    /// Set `k`. An existing key keeps its place (Python `d[k] = v`).
    pub fn insert(&mut self, k: impl Into<String>, v: Value) {
        let k = k.into();
        match self.pos(&k) {
            Some(i) => self.entries[i].1 = v,
            None => self.entries.push((k, v)),
        }
    }
    pub fn remove(&mut self, k: &str) -> Option<Value> {
        self.pos(k).map(|i| self.entries.remove(i).1)
    }
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.entries.iter().map(|(k, _)| k.as_str())
    }
    pub fn iter(&self) -> impl Iterator<Item = (&str, &Value)> {
        self.entries.iter().map(|(k, v)| (k.as_str(), v))
    }
    /// Build a map from (key, value) pairs.
    pub fn from_pairs<I: IntoIterator<Item = (S, Value)>, S: Into<String>>(it: I) -> Self {
        let mut m = Map::new();
        for (k, v) in it {
            m.insert(k, v);
        }
        m
    }
}

impl Value {
    /// A number written as an integer.
    pub fn int(v: f64) -> Value {
        Value::Num(v, false)
    }
    /// A number that Python treats as a float.
    pub fn float(v: f64) -> Value {
        Value::Num(v, true)
    }
    pub fn str(s: &str) -> Value {
        Value::Str(s.to_string())
    }
    pub fn is_null(&self) -> bool {
        matches!(self, Value::Null)
    }
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(s) => Some(s),
            _ => None,
        }
    }
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            Value::Num(x, _) => Some(*x),
            _ => None,
        }
    }
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            Value::Bool(b) => Some(*b),
            _ => None,
        }
    }
    pub fn as_arr(&self) -> Option<&Vec<Value>> {
        match self {
            Value::Arr(a) => Some(a),
            _ => None,
        }
    }
    pub fn as_obj(&self) -> Option<&Map> {
        match self {
            Value::Obj(m) => Some(m),
            _ => None,
        }
    }
    pub fn as_obj_mut(&mut self) -> Option<&mut Map> {
        match self {
            Value::Obj(m) => Some(m),
            _ => None,
        }
    }
    /// Python `isinstance(x, (int, float)) and not isinstance(x, bool)` (infinity counts).
    pub fn is_num(&self) -> bool {
        matches!(self, Value::Num(..))
    }
    /// A finite number.
    pub fn is_fin_num(&self) -> bool {
        matches!(self, Value::Num(x, _) if x.is_finite())
    }
    /// Python `isinstance(x, int) and not isinstance(x, bool)`.
    pub fn is_int(&self) -> bool {
        matches!(self, Value::Num(x, fl) if !*fl && x.is_finite() && libm::trunc(*x) == *x)
    }
    pub fn is_str(&self) -> bool {
        matches!(self, Value::Str(_))
    }
    pub fn is_obj(&self) -> bool {
        matches!(self, Value::Obj(_))
    }
    pub fn is_arr(&self) -> bool {
        matches!(self, Value::Arr(_))
    }
    /// Python truthiness.
    pub fn truthy(&self) -> bool {
        match self {
            Value::Null => false,
            Value::Bool(b) => *b,
            Value::Num(x, _) => *x != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::Arr(a) => !a.is_empty(),
            Value::Obj(m) => !m.is_empty(),
        }
    }
    /// Object member, or `null` (also for a non-object).
    pub fn get(&self, k: &str) -> &Value {
        match self {
            Value::Obj(m) => m.get(k),
            _ => &NULL,
        }
    }
    /// A Python-like type name for messages.
    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Null => "NoneType",
            Value::Bool(_) => "bool",
            Value::Num(_, true) => "float",
            Value::Num(..) => "int",
            Value::Str(_) => "str",
            Value::Arr(_) => "list",
            Value::Obj(_) => "dict",
        }
    }
}

impl From<&str> for Value {
    fn from(s: &str) -> Self {
        Value::Str(s.to_string())
    }
}
impl From<String> for Value {
    fn from(s: String) -> Self {
        Value::Str(s)
    }
}
impl From<bool> for Value {
    fn from(b: bool) -> Self {
        Value::Bool(b)
    }
}
impl From<Map> for Value {
    fn from(m: Map) -> Self {
        Value::Obj(m)
    }
}
impl From<Vec<Value>> for Value {
    fn from(v: Vec<Value>) -> Self {
        Value::Arr(v)
    }
}

/// Python `==` on JSON values (`1 == 1.0`, `True == 1`, deep lists and dicts, NaN != NaN).
pub fn py_eq(a: &Value, b: &Value) -> bool {
    fn numish(v: &Value) -> Option<f64> {
        match v {
            Value::Num(x, _) => Some(*x),
            Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
            _ => None,
        }
    }
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::Arr(x), Value::Arr(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| py_eq(p, q)),
        (Value::Obj(x), Value::Obj(y)) => {
            x.len() == y.len() && x.iter().all(|(k, v)| y.get_opt(k).map_or(false, |w| py_eq(v, w)))
        }
        _ => match (numish(a), numish(b)) {
            (Some(x), Some(y)) => x == y,
            _ => false,
        },
    }
}

/// Python `x in seq` for a list of JSON values.
pub fn py_in(x: &Value, seq: &[Value]) -> bool {
    seq.iter().any(|y| py_eq(x, y))
}

/// True if `v` is a string in `set`.
pub fn str_in(v: &Value, set: &[&str]) -> bool {
    matches!(v, Value::Str(s) if set.contains(&s.as_str()))
}

// --- parser --------------------------------------------------------------------------

/// Parse one JSON text (no `NaN` / `Infinity`). Errors are [`ErrorKind::Json`].
pub fn parse_json(text: &str) -> Result<Value, Error> {
    parse_json_opts(text, false)
}

/// Parse one JSON text. `allow_constants`: accept `NaN`, `Infinity`, `-Infinity` (Python's plain `json.loads`).
pub fn parse_json_opts(text: &str, allow_constants: bool) -> Result<Value, Error> {
    let mut p = Parser { s: text.as_bytes(), text, i: 0, allow_constants, depth: 0 };
    let v = p.value()?;
    p.skip();
    if p.i != p.s.len() {
        return Err(p.fail("Extra data"));
    }
    Ok(v)
}

struct Parser<'a> {
    s: &'a [u8],
    text: &'a str,
    i: usize,
    allow_constants: bool,
    depth: usize,
}

const MAX_DEPTH: usize = 900;

impl<'a> Parser<'a> {
    fn fail(&self, msg: &str) -> Error {
        Error::new(ErrorKind::Json, alloc::format!("{} at position {}", msg, self.i))
    }
    fn skip(&mut self) {
        while self.i < self.s.len() && matches!(self.s[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }
    fn starts(&self, tok: &str) -> bool {
        self.s[self.i..].starts_with(tok.as_bytes())
    }
    fn value(&mut self) -> Result<Value, Error> {
        self.skip();
        if self.i >= self.s.len() {
            return Err(self.fail("Expecting value"));
        }
        match self.s[self.i] {
            b'{' => self.object(),
            b'[' => self.array(),
            b'"' => Ok(Value::Str(self.string()?)),
            b't' if self.starts("true") => {
                self.i += 4;
                Ok(Value::Bool(true))
            }
            b'f' if self.starts("false") => {
                self.i += 5;
                Ok(Value::Bool(false))
            }
            b'n' if self.starts("null") => {
                self.i += 4;
                Ok(Value::Null)
            }
            _ => {
                for (tok, val) in [("NaN", f64::NAN), ("Infinity", f64::INFINITY), ("-Infinity", f64::NEG_INFINITY)] {
                    if self.starts(tok) {
                        if !self.allow_constants {
                            return Err(self.fail(&alloc::format!("{} is not a JSON value", tok)));
                        }
                        self.i += tok.len();
                        return Ok(Value::Num(val, true));
                    }
                }
                self.number()
            }
        }
    }
    fn number(&mut self) -> Result<Value, Error> {
        let s = self.s;
        let start = self.i;
        let mut j = self.i;
        if j < s.len() && s[j] == b'-' {
            j += 1;
        }
        if j < s.len() && s[j] == b'0' {
            j += 1;
        } else if j < s.len() && (b'1'..=b'9').contains(&s[j]) {
            while j < s.len() && s[j].is_ascii_digit() {
                j += 1;
            }
        } else {
            return Err(self.fail("Expecting value"));
        }
        let mut is_float = false;
        if j + 1 < s.len() && s[j] == b'.' && s[j + 1].is_ascii_digit() {
            j += 1;
            while j < s.len() && s[j].is_ascii_digit() {
                j += 1;
            }
            is_float = true;
        }
        if j < s.len() && (s[j] == b'e' || s[j] == b'E') {
            let mut k = j + 1;
            if k < s.len() && (s[k] == b'+' || s[k] == b'-') {
                k += 1;
            }
            if k < s.len() && s[k].is_ascii_digit() {
                while k < s.len() && s[k].is_ascii_digit() {
                    k += 1;
                }
                j = k;
                is_float = true;
            }
        }
        let lit = &self.text[start..j];
        let v: f64 = lit.parse().map_err(|_| self.fail("Expecting value"))?;
        self.i = j;
        Ok(Value::Num(v, is_float))
    }
    fn hex4(&self, at: usize) -> Option<u32> {
        if at + 4 > self.s.len() {
            return None;
        }
        let mut v = 0u32;
        for &c in &self.s[at..at + 4] {
            v = v * 16 + (c as char).to_digit(16)?;
        }
        Some(v)
    }
    fn string(&mut self) -> Result<String, Error> {
        self.i += 1; // opening quote
        let mut out = String::new();
        let mut start = self.i;
        loop {
            if self.i >= self.s.len() {
                return Err(self.fail("Unterminated string"));
            }
            let c = self.s[self.i];
            if c == b'"' {
                out.push_str(&self.text[start..self.i]);
                self.i += 1;
                return Ok(out);
            }
            if c < 0x20 {
                return Err(self.fail("Invalid control character in string"));
            }
            if c == b'\\' {
                out.push_str(&self.text[start..self.i]);
                self.i += 1;
                let e = if self.i < self.s.len() { self.s[self.i] } else { 0 };
                let simple = match e {
                    b'"' => Some('"'),
                    b'\\' => Some('\\'),
                    b'/' => Some('/'),
                    b'b' => Some('\u{8}'),
                    b'f' => Some('\u{c}'),
                    b'n' => Some('\n'),
                    b'r' => Some('\r'),
                    b't' => Some('\t'),
                    _ => None,
                };
                if let Some(ch) = simple {
                    out.push(ch);
                    self.i += 1;
                } else if e == b'u' {
                    let hi = match self.hex4(self.i + 1) {
                        Some(h) => h,
                        None => return Err(self.fail("Invalid \\uXXXX escape")),
                    };
                    self.i += 5;
                    if (0xD800..0xDC00).contains(&hi)
                        && self.i + 1 < self.s.len()
                        && self.s[self.i] == b'\\'
                        && self.s[self.i + 1] == b'u'
                    {
                        if let Some(lo) = self.hex4(self.i + 2) {
                            if (0xDC00..0xE000).contains(&lo) {
                                let cp = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00);
                                out.push(char::from_u32(cp).unwrap_or('\u{FFFD}'));
                                self.i += 6;
                                start = self.i;
                                continue;
                            }
                        }
                    }
                    out.push(char::from_u32(hi).unwrap_or('\u{FFFD}'));
                } else {
                    return Err(self.fail("Invalid \\escape"));
                }
                start = self.i;
                continue;
            }
            self.i += 1;
        }
    }
    fn enter(&mut self) -> Result<(), Error> {
        self.depth += 1;
        if self.depth > MAX_DEPTH {
            return Err(self.fail("maximum recursion depth exceeded"));
        }
        Ok(())
    }
    fn array(&mut self) -> Result<Value, Error> {
        self.enter()?;
        self.i += 1;
        let mut out = Vec::new();
        self.skip();
        if self.i < self.s.len() && self.s[self.i] == b']' {
            self.i += 1;
            self.depth -= 1;
            return Ok(Value::Arr(out));
        }
        loop {
            out.push(self.value()?);
            self.skip();
            match self.s.get(self.i) {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    self.depth -= 1;
                    return Ok(Value::Arr(out));
                }
                _ => return Err(self.fail("Expecting ',' delimiter")),
            }
        }
    }
    fn object(&mut self) -> Result<Value, Error> {
        self.enter()?;
        self.i += 1;
        let mut out = Map::new();
        self.skip();
        if self.i < self.s.len() && self.s[self.i] == b'}' {
            self.i += 1;
            self.depth -= 1;
            return Ok(Value::Obj(out));
        }
        loop {
            self.skip();
            if self.s.get(self.i) != Some(&b'"') {
                return Err(self.fail("Expecting property name enclosed in double quotes"));
            }
            let k = self.string()?;
            self.skip();
            if self.s.get(self.i) != Some(&b':') {
                return Err(self.fail("Expecting ':' delimiter"));
            }
            self.i += 1;
            let v = self.value()?;
            out.insert(k, v);
            self.skip();
            match self.s.get(self.i) {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    self.depth -= 1;
                    return Ok(Value::Obj(out));
                }
                _ => return Err(self.fail("Expecting ',' delimiter")),
            }
        }
    }
}

// --- text helpers ----------------------------------------------------------------------

/// Python `str.splitlines()` (no line ends kept).
pub fn py_lines(text: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut last = 0;
    let mut it = text.char_indices().peekable();
    while let Some((i, c)) = it.next() {
        let brk = matches!(
            c,
            '\n' | '\r' | '\u{b}' | '\u{c}' | '\u{1c}' | '\u{1d}' | '\u{1e}' | '\u{85}' | '\u{2028}' | '\u{2029}'
        );
        if brk {
            out.push(&text[last..i]);
            let mut end = i + c.len_utf8();
            if c == '\r' {
                if let Some(&(_, '\n')) = it.peek() {
                    it.next();
                    end += 1;
                }
            }
            last = end;
        }
    }
    if last < text.len() {
        out.push(&text[last..]);
    }
    out
}

/// Python `str.isspace()` for one character.
pub fn py_space(c: char) -> bool {
    matches!(c,
        '\t' | '\n' | '\u{b}' | '\u{c}' | '\r' | '\u{1c}'..='\u{1f}' | ' ' | '\u{85}' | '\u{a0}' | '\u{1680}'
        | '\u{2000}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}')
}

/// Python `not s.strip()`: the text is empty or white space only.
pub fn is_blank(s: &str) -> bool {
    s.chars().all(py_space)
}

/// Python `s.strip()`.
pub fn py_strip(s: &str) -> &str {
    s.trim_matches(py_space)
}

/// Python `s.split()` (white-space split, no empty parts).
pub fn py_split(s: &str) -> Vec<&str> {
    s.split(py_space).filter(|p| !p.is_empty()).collect()
}

/// Number of Unicode code points (Python `len(str)`).
pub fn cp_len(s: &str) -> usize {
    s.chars().count()
}

/// Decode UTF-8 strictly, keeping a byte order mark (Python `bytes.decode("utf-8")`).
pub fn decode_utf8(bytes: &[u8]) -> Result<&str, Error> {
    core::str::from_utf8(bytes).map_err(|e| Error::value(alloc::format!("'utf-8' codec can't decode bytes: {}", e)))
}

// --- output ----------------------------------------------------------------------------

/// JavaScript `String(number)`-like text (messages, Python `str()` of an int).
pub fn num_text(x: f64) -> String {
    if x.is_nan() {
        return "NaN".to_string();
    }
    if x.is_infinite() {
        return if x > 0.0 { "Infinity".to_string() } else { "-Infinity".to_string() };
    }
    if libm::trunc(x) == x && libm::fabs(x) < 1e21 {
        let mut s = String::new();
        let _ = write!(s, "{}", x);
        if s == "-0" {
            return "0".to_string();
        }
        return s;
    }
    let mut s = String::new();
    let _ = write!(s, "{:?}", x);
    s
}

/// JSON text of a number. `float`: an integral value gets `.0` (as Python writes a float).
fn num_json(out: &mut String, x: f64, float: bool) {
    if float && libm::trunc(x) == x && libm::fabs(x) < 1e16 {
        let _ = write!(out, "{}", x);
        if !out.ends_with(".0") {
            out.push_str(".0");
        }
    } else {
        out.push_str(&num_text(x));
    }
}

fn str_json(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn dump_into(out: &mut String, v: &Value, strict: bool) -> Result<(), Error> {
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Num(x, fl) => {
            if !x.is_finite() {
                if strict {
                    return Err(Error::value(alloc::format!("Out of range float values are not JSON compliant: {}", num_text(*x))));
                }
                out.push_str("null");
            } else {
                num_json(out, *x, *fl);
            }
        }
        Value::Str(s) => str_json(out, s),
        Value::Arr(a) => {
            out.push('[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                dump_into(out, x, strict)?;
            }
            out.push(']');
        }
        Value::Obj(m) => {
            out.push('{');
            for (i, (k, x)) in m.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                str_json(out, k);
                out.push(':');
                dump_into(out, x, strict)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

/// Compact JSON text (`allow_nan=False`): errors on NaN or infinity.
pub fn dump_json(v: &Value) -> Result<String, Error> {
    let mut s = String::new();
    dump_into(&mut s, v, true)?;
    Ok(s)
}

/// JSON text for messages: NaN and infinity become `null` (JavaScript `JSON.stringify`).
pub fn repr(v: &Value) -> String {
    let mut s = String::new();
    let _ = dump_into(&mut s, v, false);
    s
}

/// A list of strings as a JSON value.
pub fn str_list(items: &[&str]) -> Value {
    Value::Arr(items.iter().map(|s| Value::Str((*s).to_string())).collect())
}

/// Python `str(x)` of a JSON value (`None`, `True`, `{'a': 1}`, ...).
pub fn py_str(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        _ => py_repr(v),
    }
}

/// Python `repr(x)` of a JSON value.
pub fn py_repr(v: &Value) -> String {
    match v {
        Value::Null => "None".to_string(),
        Value::Bool(b) => (if *b { "True" } else { "False" }).to_string(),
        Value::Num(x, fl) => {
            if x.is_nan() {
                "nan".to_string()
            } else if x.is_infinite() {
                (if *x > 0.0 { "inf" } else { "-inf" }).to_string()
            } else {
                let mut s = String::new();
                num_json(&mut s, *x, *fl);
                s
            }
        }
        Value::Str(s) => {
            let mut o = String::from("'");
            for c in s.chars() {
                match c {
                    '\'' => o.push_str("\\'"),
                    '\\' => o.push_str("\\\\"),
                    '\n' => o.push_str("\\n"),
                    c => o.push(c),
                }
            }
            o.push('\'');
            o
        }
        Value::Arr(a) => {
            let parts: Vec<String> = a.iter().map(py_repr).collect();
            alloc::format!("[{}]", parts.join(", "))
        }
        Value::Obj(m) => {
            let parts: Vec<String> = m.iter().map(|(k, x)| alloc::format!("{}: {}", py_repr(&Value::str(k)), py_repr(x))).collect();
            alloc::format!("{{{}}}", parts.join(", "))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_literals() {
        let v = parse_json(r#"{"a": 1, "b": 1.0, "c": 1e3, "d": -0}"#).unwrap();
        assert!(v.get("a").is_int());
        assert!(!v.get("b").is_int());
        assert!(!v.get("c").is_int());
        assert!(v.get("d").is_int());
    }

    #[test]
    fn rejects_non_json() {
        for t in ["NaN", "[Infinity]", "01", "1.", "\u{feff}{}", "{'a': 1}", "[1,]", "\"\t\""] {
            assert!(parse_json(t).is_err(), "{}", t);
        }
        assert!(parse_json_opts("[NaN, -Infinity]", true).is_ok());
    }

    #[test]
    fn duplicate_key_keeps_place() {
        let v = parse_json(r#"{"a": 1, "b": 2, "a": 3.0}"#).unwrap();
        let m = v.as_obj().unwrap();
        assert_eq!(m.keys().collect::<Vec<_>>(), ["a", "b"]);
        assert!(!m.get("a").is_int());
    }

    #[test]
    fn splitlines() {
        assert_eq!(py_lines("a\r\nb\rc\u{2028}d\n"), ["a", "b", "c", "d"]);
        assert_eq!(py_lines("a\n\nb"), ["a", "", "b"]);
    }

    #[test]
    fn dump_roundtrip() {
        let v = parse_json(r#"{"t":0.0,"n":3,"s":"a\"bé","l":[null,true,-1.5]}"#).unwrap();
        assert_eq!(dump_json(&v).unwrap(), r#"{"t":0.0,"n":3,"s":"a\"bé","l":[null,true,-1.5]}"#);
        assert!(dump_json(&Value::float(f64::NAN)).is_err());
    }
}
