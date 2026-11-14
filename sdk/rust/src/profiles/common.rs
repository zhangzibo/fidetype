//! Shared parts of the FEP conformance profiles.

use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::checks::{CheckResult, Level, Status};
use crate::error::Error;
use crate::json::{decode_utf8, is_blank, num_text, parse_json, py_lines, Map, Value};

/// Read a JSON Lines file. Return (events with `_line`, parse errors). Port of `fep0001.read_events`.
pub fn read_events(bytes: &[u8]) -> (Vec<Map>, Vec<String>) {
    let mut events = Vec::new();
    let mut errs = Vec::new();
    let text = match decode_utf8(bytes) {
        Ok(t) => t,
        Err(e) => return (events, alloc::vec![format!("cannot read: {}", e.message)]),
    };
    for (k, line) in py_lines(text).into_iter().enumerate() {
        let n = k + 1;
        if is_blank(line) {
            continue;
        }
        match parse_json(line) {
            Err(e) => errs.push(format!("line {}: not JSON: {}", n, e.message)),
            Ok(Value::Obj(mut m)) if m.get("type").is_str() => {
                m.insert("_line", Value::int(n as f64));
                events.push(m);
            }
            Ok(_) => errs.push(format!("line {}: not an object with a string type", n)),
        }
    }
    (events, errs)
}

/// The kind of a JSON Lines file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StreamKind {
    Input,
    Decisions,
    Unknown,
}

impl StreamKind {
    pub fn name(self) -> &'static str {
        match self {
            StreamKind::Input => "input",
            StreamKind::Decisions => "decisions",
            StreamKind::Unknown => "unknown",
        }
    }
}

pub fn etype(e: &Map) -> &str {
    e.get("type").as_str().unwrap_or("")
}

/// `input` (header first), `decisions` (only trust_decision) or `unknown`.
pub fn stream_kind(events: &[Map]) -> StreamKind {
    if events.is_empty() {
        return StreamKind::Unknown;
    }
    if etype(&events[0]) == "header" {
        return StreamKind::Input;
    }
    if events.iter().all(|e| etype(e) == "trust_decision") {
        return StreamKind::Decisions;
    }
    StreamKind::Unknown
}

/// (id, keyword, clause, title) of a profile check.
pub type CheckMeta = (&'static str, &'static str, &'static str, &'static str);

/// Build one profile check result. `errs = None` with `skipped` = skip.
pub fn make_res(meta: &[CheckMeta], fep: &str, cid: &str, errs: Option<Vec<String>>, msg_ok: &str, skipped: Option<&str>) -> CheckResult {
    let m = meta.iter().find(|m| m.0 == cid).copied().unwrap_or((cid, "MUST", "", ""));
    let (status, message) = if let Some(s) = skipped {
        (Status::Skip, s.to_string())
    } else {
        match errs {
            Some(e) if !e.is_empty() => {
                let mut msg = e[..e.len().min(6)].join("; ");
                if e.len() > 6 {
                    msg.push_str(&format!(" (+{} more)", e.len() - 6));
                }
                (Status::Fail, msg)
            }
            _ => (Status::Pass, msg_ok.to_string()),
        }
    };
    CheckResult {
        id: cid.to_string(),
        level: Level::Core,
        keyword: m.1.to_string(),
        clause: format!("{} {}", fep, m.2),
        title: m.3.to_string(),
        status,
        message,
        heuristic: false,
    }
}

/// A profile target report.
#[derive(Debug, Clone)]
pub struct TargetReport {
    pub target: String,
    pub checks: Vec<CheckResult>,
    pub info: Map,
}

/// The failures of a report.
pub fn failures(rep: &TargetReport) -> Vec<&CheckResult> {
    rep.checks.iter().filter(|c| c.status == Status::Fail).collect()
}

/// A rejection for the first failure of a report.
pub fn reject_on_failure(rep: &TargetReport) -> Result<(), Error> {
    match failures(rep).first() {
        Some(f) => Err(Error::rejected(format!("[{}, {}] {}", f.id, f.clause, f.message), &f.clause, &f.id)),
        None => Ok(()),
    }
}

/// The `_line` of an event for messages (`?` if absent).
pub fn line_of(e: &Map) -> String {
    match e.get_opt("_line") {
        Some(Value::Num(x, _)) => num_text(*x),
        Some(Value::Str(s)) => s.clone(),
        Some(v) => crate::json::repr(v),
        None => "?".to_string(),
    }
}

/// A dictionary key for Python tuples of JSON values (`(sid, unit)`): equal keys for `1` and `1.0`.
pub fn tuple_key(parts: &[&Value]) -> String {
    let mut s = String::new();
    for p in parts {
        s.push_str(&key_text(p));
        s.push('\u{1}');
    }
    s
}

fn key_text(v: &Value) -> String {
    match v {
        Value::Null => "n".to_string(),
        Value::Bool(b) => format!("d{}", if *b { 1.0 } else { 0.0 }),
        Value::Num(x, _) => format!("d{}", num_text(*x)),
        Value::Str(s) => format!("s{}", s),
        other => format!("j{}", crate::json::repr(other)),
    }
}
