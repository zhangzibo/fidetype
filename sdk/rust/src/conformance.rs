//! Conformance runner: run a consumer over the golden vectors of a profile
//! (`spec/conformance/<profile>/manifest.json`), the same files that the
//! Python suite uses (`python -m fidetype.conformance consumer`).
//!
//! Platform neutral: the caller gives a function that reads a vector file.
//! See [`crate::io`] (feature `std`) for a file-system helper.

use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::checks::load_stream;
use crate::error::Error;
use crate::json::{decode_utf8, num_text, parse_json, py_eq, repr, Map, Value};
use crate::profiles::{fep0001, fep0002, fep0003};

/// A reference consumer: (file name, bytes) -> summary, or a rejection.
pub type Consumer = fn(&str, &[u8]) -> Result<Value, Error>;

fn v01(name: &str, bytes: &[u8]) -> Result<Value, Error> {
    load_stream(name, bytes).map(|s| Value::Obj(s.summary))
}

/// The profiles this SDK knows, in report order.
pub const PROFILES: &[&str] = &["v0.1", "fep-0001", "fep-0002", "fep-0003"];

/// The reference consumer of a profile.
pub fn consumer_for(profile: &str) -> Option<Consumer> {
    match profile {
        "v0.1" => Some(v01),
        "fep-0001" => Some(fep0001::consume),
        "fep-0002" => Some(fep0002::consume),
        "fep-0003" => Some(fep0003::consume),
        _ => None,
    }
}

/// The title of a profile (as the Python CLI prints it).
pub fn profile_title(profile: &str) -> &str {
    match profile {
        "v0.1" => "NeuralTextStream v0.1",
        "fep-0001" => "FEP-0001 streaming trust events",
        "fep-0002" => "FEP-0002 NeuralTextStream over LSL",
        "fep-0003" => "FEP-0003 output profiles and discrete intent events",
        p => p,
    }
}

/// The outcome of one vector.
#[derive(Debug, Clone)]
pub struct VectorOutcome {
    pub id: String,
    pub file: String,
    pub expect: String,
    /// "accept" or "reject".
    pub actual: &'static str,
    /// The verdict equals `expect` and, for an accepted vector, the expected values match.
    pub ok: bool,
    pub detail: String,
}

/// The report of one profile run (schema `fidetype.conformance.consumer-report/1`).
#[derive(Debug, Clone)]
pub struct ProfileReport {
    pub consumer: String,
    pub profile: String,
    pub passed: usize,
    pub total: usize,
    pub ok: bool,
    pub vectors: Vec<VectorOutcome>,
}

impl ProfileReport {
    /// The report as JSON (the same fields as the Python report).
    pub fn to_value(&self) -> Value {
        let vectors: Vec<Value> = self
            .vectors
            .iter()
            .map(|o| {
                Value::Obj(Map::from_pairs([
                    ("id", Value::str(&o.id)),
                    ("file", Value::str(&o.file)),
                    ("expect", Value::str(&o.expect)),
                    ("actual", Value::str(o.actual)),
                    ("ok", Value::Bool(o.ok)),
                    ("detail", Value::str(&o.detail)),
                ]))
            })
            .collect();
        Value::Obj(Map::from_pairs([
            ("schema", Value::str("fidetype.conformance.consumer-report/1")),
            ("consumer", Value::str(&self.consumer)),
            ("profile", Value::str(&self.profile)),
            ("passed", Value::int(self.passed as f64)),
            ("total", Value::int(self.total as f64)),
            ("ok", Value::Bool(self.ok)),
            ("vectors", Value::Arr(vectors)),
        ]))
    }

    /// One summary line, as the Python CLI prints it.
    pub fn line(&self) -> String {
        format!(
            "[{} consumer conformance: {}] {}/{} golden vectors",
            profile_title(&self.profile),
            if self.ok { "PASS" } else { "FAIL" },
            self.passed,
            self.total
        )
    }
}

fn js_string(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        Value::Num(x, _) => num_text(*x),
        Value::Null => "null".to_string(),
        other => repr(other),
    }
}

/// Run a consumer over one profile's vectors. `read(file)` returns the bytes of a file in the profile folder.
pub fn run_vectors(
    profile: &str,
    read: &mut dyn FnMut(&str) -> Result<Vec<u8>, Error>,
    consumer: Option<Consumer>,
) -> Result<ProfileReport, Error> {
    let consumer = consumer.or_else(|| consumer_for(profile)).ok_or_else(|| {
        Error::value(format!("unknown profile '{}'; known: {}", profile, PROFILES.join(", ")))
    })?;
    let mbytes = read("manifest.json")?;
    let manifest = parse_json(decode_utf8(&mbytes)?)?;
    let list = match manifest.get("vectors") {
        Value::Arr(a) => a.clone(),
        _ => return Err(Error::value("manifest.json has no vectors list")),
    };
    let mut vectors = Vec::new();
    for v in &list {
        let file = js_string(v.get("file"));
        let result = read(&file).and_then(|b| consumer(&file, &b));
        let (actual, mut detail, res) = match result {
            Ok(r) => ("accept", String::new(), Some(r)),
            Err(e) => ("reject", e.to_string(), None),
        };
        let mut ok = v.get("expect").as_str() == Some(actual);
        if ok && actual == "accept" {
            if let (Value::Obj(expected), Some(Value::Obj(res))) = (v.get("expected"), &res) {
                let diffs: Vec<String> = expected
                    .iter()
                    .filter(|(k, want)| res.get_opt(k).map_or(false, |got| !py_eq(got, want)))
                    .map(|(k, want)| format!("{}: expected {}, got {}", k, repr(want), repr(res.get(k))))
                    .collect();
                if !diffs.is_empty() {
                    ok = false;
                    detail = diffs.join("; ");
                }
            }
        }
        let detail: String = detail.chars().take(300).collect();
        vectors.push(VectorOutcome {
            id: js_string(v.get("id")),
            file,
            expect: js_string(v.get("expect")),
            actual,
            ok,
            detail,
        });
    }
    let passed = vectors.iter().filter(|o| o.ok).count();
    Ok(ProfileReport {
        consumer: format!("fidetype (Rust SDK) {} reference consumer", profile),
        profile: profile.to_string(),
        passed,
        total: vectors.len(),
        ok: passed == vectors.len(),
        vectors,
    })
}
