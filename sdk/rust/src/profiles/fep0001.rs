//! Conformance profile `fep-0001`: streaming trust events (port of
//! `fidetype.conformance.profiles.fep0001`).
//!
//! Input streams (line 1 = header) may carry `segment_end`, evidence fields on
//! hypothesis items and a `decode_declaration`; they must also pass the v0.1
//! core level. Decision logs hold only `trust_decision` lines.

use alloc::collections::{BTreeMap, BTreeSet};
use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::checks::{blocks, run_checks, CheckResult, Level, Status};
use crate::constants::{DECLARATION_KEY, SCORE_SEMANTICS, SEGMENT_UNITS, TRUST_ACTIONS};
use crate::error::Error;
use crate::json::{cp_len, num_text, repr, str_in, str_list, Map, Value};
use crate::raw::read_jsonl_raw;

use super::common::{etype, line_of, make_res, read_events, reject_on_failure, stream_kind, tuple_key, CheckMeta, StreamKind, TargetReport};

pub const FEP: &str = "FEP-0001";
const LOGP_TOL: f64 = 1e-9;

pub const CHECKS: &[CheckMeta] = &[
    ("FEP1-PARSE", "MUST", "6.2 (v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"),
    ("FEP1-KIND", "MUST", "3 r4 / 6.2.1", "The file is an input stream (header first) or a decision log (only trust_decision)"),
    ("FEP1-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"),
    ("FEP1-SEGMENT", "MUST", "1 table, r5", "segment_end: t a finite number not before the last frame; unit in the enum"),
    ("FEP1-EVIDENCE", "MUST", "2 table, r1, r4", "char_confidences: one number in [0, 1] per code point; logp_* finite and <= 0"),
    ("FEP1-SCORE", "MUST", "2 r3", "Every n-best item has a finite numeric score"),
    ("FEP1-DECL", "MUST", "4 table", "decode_declaration (header or hypothesis) has the defined form"),
    ("FEP1-TD-INPUT", "MUST", "3 r4", "No trust_decision event in an input stream"),
    ("FEP1-TD-FORMAT", "MUST", "3 table, r2, r8", "trust_decision fields have the defined types and ranges"),
    ("FEP1-TD-FINAL", "MUST", "3 r5-r7", "Per session: seq increases; at most one final decision per utterance; none after it"),
];

fn res(cid: &str, errs: Option<Vec<String>>, msg_ok: &str, skipped: Option<&str>) -> CheckResult {
    make_res(CHECKS, FEP, cid, errs, msg_ok, skipped)
}

/// The format errors of a `decode_declaration` (FEP-0001 section 4). Empty: valid.
pub fn validate_declaration(decl: &Value) -> Vec<String> {
    let d = match decl {
        Value::Obj(m) => m,
        _ => return alloc::vec![format!("{} must be a JSON object", DECLARATION_KEY)],
    };
    let mut errs = Vec::new();
    if !matches!(d.get("decoder"), Value::Str(s) if !s.is_empty()) {
        errs.push(format!("{}.decoder must be a non-empty string", DECLARATION_KEY));
    }
    for k in ["decoder_version", "config_id"] {
        if let Some(v) = d.get_opt(k) {
            if !matches!(v, Value::Str(s) if !s.is_empty()) {
                errs.push(format!("{}.{} must be a non-empty string", DECLARATION_KEY, k));
            }
        }
    }
    if let Some(t) = d.get_opt("frame_temperature") {
        if !matches!(t, Value::Num(x, _) if x.is_finite() && *x > 0.0) {
            errs.push(format!("{}.frame_temperature must be a finite number > 0", DECLARATION_KEY));
        }
    }
    if let Some(p) = d.get_opt("params") {
        if !p.is_obj() {
            errs.push(format!("{}.params must be a JSON object", DECLARATION_KEY));
        }
    }
    errs
}

pub fn segment_errors(events: &[Map]) -> Vec<String> {
    let mut errs = Vec::new();
    let mut last_frame_t = f64::NEG_INFINITY;
    for e in events {
        match etype(e) {
            "header" => last_frame_t = f64::NEG_INFINITY,
            "frame" => {
                if let Value::Num(t, _) = e.get("t") {
                    if t.is_finite() {
                        last_frame_t = *t;
                    }
                }
            }
            "segment_end" => {
                let n = line_of(e);
                if let Some(t) = e.get_opt("t") {
                    match t {
                        Value::Num(x, _) if x.is_finite() => {
                            if *x < last_frame_t {
                                errs.push(format!(
                                    "line {}: segment_end t {} is before the last frame t {} (rule 5)",
                                    n,
                                    num_text(*x),
                                    num_text(last_frame_t)
                                ));
                            }
                        }
                        _ => errs.push(format!("line {}: segment_end t must be a finite number", n)),
                    }
                }
                if let Some(u) = e.get_opt("unit") {
                    if !str_in(u, SEGMENT_UNITS) {
                        errs.push(format!("line {}: segment_end unit {} is not one of {}", n, repr(u), repr(&str_list(SEGMENT_UNITS))));
                    }
                }
            }
            _ => {}
        }
    }
    errs
}

/// (line, index, item) of every object n-best item of every hypothesis.
pub(crate) fn items(events: &[Map]) -> Vec<(String, usize, &Map)> {
    let mut out = Vec::new();
    for e in events {
        if etype(e) == "hypothesis" {
            if let Value::Arr(nb) = e.get("nbest") {
                for (k, it) in nb.iter().enumerate() {
                    if let Value::Obj(m) = it {
                        out.push((line_of(e), k, m));
                    }
                }
            }
        }
    }
    out
}

pub fn evidence_errors(events: &[Map]) -> Vec<String> {
    let mut errs = Vec::new();
    for (n, k, it) in items(events) {
        let w = format!("line {} nbest[{}]", n, k);
        if let Some(cc) = it.get_opt("char_confidences") {
            match cc {
                Value::Arr(a) => {
                    if let Value::Str(text) = it.get("text") {
                        if a.len() != cp_len(text) {
                            errs.push(format!(
                                "{}: char_confidences has {} values, text has {} code points (rule 1)",
                                w,
                                a.len(),
                                cp_len(text)
                            ));
                        }
                    }
                    if a.iter().any(|c| !matches!(c, Value::Num(x, _) if x.is_finite() && *x >= 0.0 && *x <= 1.0)) {
                        errs.push(format!("{}: char_confidences values must be numbers in [0, 1]", w));
                    }
                }
                _ => errs.push(format!("{}: char_confidences must be a list", w)),
            }
        }
        for key in ["logp_acoustic", "logp_lm"] {
            if let Some(v) = it.get_opt(key) {
                match v {
                    Value::Num(x, _) if x.is_finite() => {
                        if *x > LOGP_TOL {
                            errs.push(format!("{}: {} {} is a log-probability and must be <= 0 (rule 4)", w, key, num_text(*x)));
                        }
                    }
                    _ => errs.push(format!("{}: {} must be a finite number", w, key)),
                }
            }
        }
    }
    errs
}

pub fn score_errors(events: &[Map]) -> Vec<String> {
    items(events)
        .into_iter()
        .filter(|(_, _, it)| !it.get("score").is_fin_num())
        .map(|(n, k, _)| format!("line {} nbest[{}]: score must be a finite number (rule 3)", n, k))
        .collect()
}

pub fn declaration_errors(events: &[Map]) -> Vec<String> {
    let mut errs = Vec::new();
    for e in events {
        if matches!(etype(e), "header" | "hypothesis") {
            if let Some(d) = e.get_opt(DECLARATION_KEY) {
                for x in validate_declaration(d) {
                    errs.push(format!("line {}: {}", line_of(e), x));
                }
            }
        }
    }
    errs
}

pub fn td_input_errors(events: &[Map]) -> Vec<String> {
    events.iter().filter(|e| etype(e) == "trust_decision").map(|e| format!("line {}: trust_decision in an input stream", line_of(e))).collect()
}

/// `x` is a number in [0, 1].
fn unit_interval(x: &Value) -> bool {
    matches!(x, Value::Num(v, _) if v.is_finite() && *v >= 0.0 && *v <= 1.0)
}

/// The format errors of one `trust_decision` event (FEP-0001 section 3 table, rules 2 and 8).
pub fn td_format_errors(e: &Map) -> Vec<String> {
    let n = line_of(e);
    let mut errs: Vec<String> = Vec::new();
    if !matches!(e.get("is_final"), Value::Bool(_)) {
        errs.push("is_final must be a boolean".into());
    }
    let action = e.get("action");
    if !str_in(action, TRUST_ACTIONS) {
        errs.push(format!("action {} is not one of {}", repr(action), repr(&str_list(TRUST_ACTIONS))));
    }
    match e.get_opt("p_top1") {
        None => errs.push("p_top1 is required (number or null)".into()),
        Some(p) if !p.is_null() && !unit_interval(p) => errs.push(format!("p_top1 {} must be a number in [0, 1] or null", repr(p))),
        _ => {}
    }
    let sem = e.get("score_semantics");
    if sem.is_null() {
        errs.push("score_semantics is required".into());
    } else if !str_in(sem, SCORE_SEMANTICS) {
        errs.push(format!("score_semantics {} is not one of {}", repr(sem), repr(&str_list(SCORE_SEMANTICS))));
    }
    if let Some(sh) = e.get_opt("shown") {
        match sh {
            Value::Arr(a) if a.iter().all(|x| x.is_str()) => {
                if action.as_str() == Some("COMMIT") && a.is_empty() {
                    errs.push("a COMMIT with shown needs at least one text (rule 8)".into());
                }
            }
            _ => errs.push("shown must be a list of strings".into()),
        }
    }
    if let Some(s) = e.get_opt("set_size") {
        if !(s.is_int() && s.as_f64().unwrap_or(-1.0) >= 0.0) {
            errs.push("set_size must be an integer >= 0".into());
        }
    }
    if let Some(g) = e.get_opt("guard_risk") {
        if !g.is_null() && !unit_interval(g) {
            errs.push("guard_risk must be a number in [0, 1] or null".into());
        }
    }
    if let Some(s) = e.get_opt("session") {
        if !s.is_str() {
            errs.push("session must be a string".into());
        }
    }
    for k in ["seq", "utterance"] {
        if let Some(v) = e.get_opt(k) {
            if !(v.is_int() && v.as_f64().unwrap_or(-1.0) >= 0.0) {
                errs.push(format!("{} must be an integer >= 0", k));
            }
        }
    }
    if let Some(c) = e.get_opt("config_id") {
        if !c.is_null() && !c.is_str() {
            errs.push("config_id must be a string".into());
        }
    }
    if let Some(i) = e.get_opt("input") {
        if !i.is_obj() {
            errs.push("input must be an object".into());
        }
    }
    if let Some(l) = e.get_opt("latency_s") {
        if !matches!(l, Value::Num(x, _) if x.is_finite() && *x >= 0.0) {
            errs.push("latency_s must be a number >= 0".into());
        }
    }
    errs.into_iter().map(|x| format!("line {}: {}", n, x)).collect()
}

/// The session id of a decision: `session`, `""` if absent, `None` if not a string.
pub(crate) fn session_of(e: &Map) -> Option<String> {
    match e.get_opt("session") {
        None => Some(String::new()),
        Some(Value::Str(s)) => Some(s.clone()),
        Some(_) => None,
    }
}

/// is_final semantics per session (FEP-0001 section 3 rules 5-7).
pub fn td_final_errors(events: &[Map]) -> Vec<String> {
    let mut errs = Vec::new();
    let mut last_seq: BTreeMap<String, f64> = BTreeMap::new();
    let mut last_utt: BTreeMap<String, f64> = BTreeMap::new();
    let mut finals: BTreeSet<String> = BTreeSet::new();
    for e in events {
        if etype(e) != "trust_decision" {
            continue;
        }
        let n = line_of(e);
        let sid = match session_of(e) {
            Some(s) => s,
            None => continue,
        };
        let seq = e.get("seq");
        if seq.is_int() {
            let s = seq.as_f64().unwrap_or(0.0);
            if let Some(&l) = last_seq.get(&sid) {
                if s <= l {
                    errs.push(format!("line {}: seq {} does not increase in session '{}' (rule 5)", n, num_text(s), sid));
                }
            }
            let m = last_seq.get(&sid).map_or(s, |&l| l.max(s));
            last_seq.insert(sid.clone(), m);
        }
        let utt = e.get("utterance");
        if utt.is_int() {
            let u = utt.as_f64().unwrap_or(0.0);
            if let Some(&l) = last_utt.get(&sid) {
                if u < l {
                    errs.push(format!("line {}: utterance {} goes back in session '{}' (rule 5)", n, num_text(u), sid));
                }
            }
            let m = last_utt.get(&sid).map_or(u, |&l| l.max(u));
            last_utt.insert(sid.clone(), m);
            let key = tuple_key(&[&Value::Str(sid.clone()), &Value::int(u)]);
            let is_final = matches!(e.get("is_final"), Value::Bool(true));
            if finals.contains(&key) {
                let kind = if is_final { "a second final decision" } else { "a decision" };
                errs.push(format!("line {}: {} for utterance {} of session '{}' after its final one (rules 6-7)", n, kind, num_text(u), sid));
            }
            if is_final {
                finals.insert(key);
            }
        }
    }
    errs
}

/// The texts a bridge may act on: `shown[0]` of each final COMMIT (null if the text is omitted).
pub fn acted_texts(decisions: &[Map]) -> Vec<Value> {
    decisions
        .iter()
        .filter(|e| etype(e) == "trust_decision" && matches!(e.get("is_final"), Value::Bool(true)) && e.get("action").as_str() == Some("COMMIT"))
        .map(|e| match e.get("shown") {
            Value::Arr(a) if !a.is_empty() => a[0].clone(),
            _ => Value::Null,
        })
        .collect()
}

pub fn check_events(events: &[Map], parse_errors: Vec<String>) -> Vec<CheckResult> {
    let mut out = alloc::vec![res("FEP1-PARSE", Some(parse_errors), "", None)];
    let kind = stream_kind(events);
    let kerr = if kind != StreamKind::Unknown {
        Vec::new()
    } else {
        alloc::vec!["line 1 is neither a header nor a trust_decision, or a decision log has other events".to_string()]
    };
    out.push(res("FEP1-KIND", Some(kerr), kind.name(), None));
    let inp = kind == StreamKind::Input;
    let dec = kind == StreamKind::Decisions;
    let na_in = if inp { None } else { Some("not an input stream") };
    let na_dec = if dec { None } else { Some("not a decision log") };
    out.push(res("FEP1-SEGMENT", inp.then(|| segment_errors(events)), "", na_in));
    out.push(res("FEP1-EVIDENCE", inp.then(|| evidence_errors(events)), "", na_in));
    out.push(res("FEP1-SCORE", inp.then(|| score_errors(events)), "", na_in));
    out.push(res("FEP1-DECL", inp.then(|| declaration_errors(events)), "", na_in));
    out.push(res("FEP1-TD-INPUT", inp.then(|| td_input_errors(events)), "", na_in));
    let msg = format!("{} decision(s)", events.len());
    out.push(res("FEP1-TD-FORMAT", dec.then(|| events.iter().flat_map(td_format_errors).collect()), &msg, na_dec));
    out.push(res("FEP1-TD-FINAL", dec.then(|| td_final_errors(events)), "", na_dec));
    out
}

/// v0.1 core failures of a JSON Lines input stream (as `fidetype.conformance.check_file`).
pub fn v01_core_failures(bytes: &[u8]) -> Vec<String> {
    run_checks(&read_jsonl_raw(bytes))
        .into_iter()
        .filter(|r| r.status == Status::Fail && blocks(r.level, Level::Core))
        .map(|r| format!("{}: {}", r.id, r.message))
        .collect()
}

/// Producer check of one JSON Lines file under the profile.
pub fn check_file(name: &str, bytes: &[u8]) -> TargetReport {
    let (events, perr) = read_events(bytes);
    let no_perr = perr.is_empty();
    let mut results = check_events(&events, perr);
    let kind = stream_kind(&events);
    let v01 = if kind == StreamKind::Input && no_perr {
        res("FEP1-V01-CORE", Some(v01_core_failures(bytes)), "v0.1 core passed", None)
    } else {
        res("FEP1-V01-CORE", None, "", Some("not an input stream"))
    };
    results.insert(2, v01);
    let info = Map::from_pairs([
        ("format", Value::str("jsonl")),
        ("kind", Value::str(kind.name())),
        ("events", Value::int(events.len() as f64)),
    ]);
    TargetReport { target: name.to_string(), checks: results, info }
}

pub fn summarize(events: &[Map]) -> Map {
    let kind = stream_kind(events);
    if kind == StreamKind::Decisions {
        let fin = events.iter().filter(|e| matches!(e.get("is_final"), Value::Bool(true))).count();
        return Map::from_pairs([
            ("kind", Value::str(kind.name())),
            ("decisions", Value::int(events.len() as f64)),
            ("final", Value::int(fin as f64)),
            ("acted", Value::Arr(acted_texts(events))),
        ]);
    }
    let mut segs = 0;
    let mut has_input = false;
    let mut ends = 0;
    for e in events {
        match etype(e) {
            "frame" | "hypothesis" => has_input = true,
            t @ ("segment_end" | "end" | "header") => {
                if has_input {
                    segs += 1;
                }
                has_input = false;
                if t == "segment_end" {
                    ends += 1;
                }
            }
            _ => {}
        }
    }
    if has_input {
        segs += 1;
    }
    let count = |t: &str| events.iter().filter(|e| etype(e) == t).count();
    let evidence = items(events)
        .into_iter()
        .filter(|(_, _, it)| ["char_confidences", "logp_acoustic", "logp_lm"].iter().any(|k| it.has(k)))
        .count();
    let decls = events.iter().filter(|e| matches!(etype(e), "header" | "hypothesis") && e.has(DECLARATION_KEY)).count();
    Map::from_pairs([
        ("kind", Value::str(kind.name())),
        ("n_frames", Value::int(count("frame") as f64)),
        ("segments", Value::int(segs as f64)),
        ("segment_ends", Value::int(ends as f64)),
        ("hypotheses", Value::int(count("hypothesis") as f64)),
        ("evidence_items", Value::int(evidence as f64)),
        ("declarations", Value::int(decls as f64)),
    ])
}

/// Reference consumer of the profile: return a summary, or a rejection.
pub fn consume(name: &str, bytes: &[u8]) -> Result<Value, Error> {
    reject_on_failure(&check_file(name, bytes))?;
    Ok(Value::Obj(summarize(&read_events(bytes).0)))
}
