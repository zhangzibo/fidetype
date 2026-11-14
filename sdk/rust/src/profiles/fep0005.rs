//! Conformance profile `fep-0005`: continuous-control events (port of
//! `fidetype.conformance.profiles.fep0005` and the validators of
//! `fidetype.trust.control`).
//!
//! Input streams (line 1 = header) carry a `control_declaration`, `control`,
//! `control_enable` and v0.1 `pointer` events, and may carry FEP-0003 intent
//! events (a click). Decision logs hold only `trust_decision` lines; control
//! decisions have `profile = "control"`. For a decision log the consumer
//! returns `moving_ticks` (the "acted" list of control COMMITs, NTS 1.0 6.4),
//! `acted_intents` and `acted_texts`.

use alloc::collections::{BTreeMap, BTreeSet};
use alloc::format;
use alloc::string::{String, ToString};
use alloc::vec::Vec;

use crate::checks::CheckResult;
use crate::constants::INTENT_DECLARATION_KEY;
use crate::error::Error;
use crate::json::{num_text, py_eq, repr, str_in, str_list, Map, Value};

use super::common::{etype, line_of, make_res, read_events, reject_on_failure, stream_kind, tuple_key, CheckMeta, StreamKind, TargetReport};
use super::fep0001::{td_format_errors, v01_core_failures};
use super::fep0003 as f3;

pub const FEP: &str = "FEP-0005";
pub const CONTROL_DECLARATION_KEY: &str = "control_declaration";
const CONTROL: &str = "control";
const CONTROL_ENABLE: &str = "control_enable";
const PROFILE: &str = "control";

pub const QUANTITIES: &[&str] = &["velocity", "position"];
pub const VELOCITY_UNITS: &[&str] = &["norm/s", "px/s", "mm/s", "m/s", "deg/s"];
pub const POSITION_UNITS: &[&str] = &["norm", "px", "mm", "m", "deg"];
pub const FRAMES: &[&str] = &["screen", "workspace"];
pub const UNCERTAINTY: &[&str] = &["none", "std"];
pub const SOURCES: &[&str] = &["decoder", "human"];
pub const STATES: &[&str] = &["act", "attenuate", "hold", "stop"];
pub const ENABLE_SOURCES: &[&str] = &["switch", "caregiver", "ui", "voice", "eye-tracker", "watchdog", "other"];
const TIMING_FIELDS: &[&str] = &["t_signal_start", "t_signal_end", "t_decoded", "t_emitted"];
const CONTROL_ACTIONS: &[&str] = &["COMMIT", "ABSTAIN"];
const MOVING: &[&str] = &["act", "attenuate"];
/// Reasons that mean "no signal / no engagement": a decision with one of them MUST NOT move.
pub const NO_MOTION_REASONS: &[&str] = &["no_signal", "no_signal_reference", "stale_input", "disengaged", "not_engaged", "absent"];
const SPEED_TOL: f64 = 1e-6;

pub const CHECKS: &[CheckMeta] = &[
    ("FEP5-PARSE", "MUST", "1 (6.2 v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"),
    ("FEP5-KIND", "MUST", "1", "The file is an input stream (header first) or a decision log (only trust_decision)"),
    ("FEP5-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"),
    ("FEP5-DECL", "MUST", "2 table, r1-r4", "control_declaration has the defined form (dims, quantity, units, frame, rate, click intent)"),
    ("FEP5-CONTROL", "MUST", "3 table, r1-r4", "control and pointer events: declared, dims values, std per declaration, tick and t increase"),
    ("FEP5-ENABLE", "MUST", "4 table", "control_enable events have the defined form"),
    ("FEP5-INTENT", "MUST", "5 r6 (FEP-0003 2-4)", "Intent parts of the stream follow FEP-0003"),
    ("FEP5-TD-FORMAT", "MUST", "5 table, r1-r4", "Control trust_decision fields (profile, tick, state, velocity, gain, v_max, ttl_s, engagement; no shown)"),
    ("FEP5-TD-ORDER", "MUST", "5 r5", "Per session: seq increases over all profiles; control decisions are final; a moving tick is never reused"),
    ("FEP5-SAFETY", "MUST", "6 r1-r7", "No motion on hold/stop or no-signal reasons; speed <= v_max; re-engage after stop; no intent COMMIT while stopped"),
];

fn res(cid: &str, errs: Option<Vec<String>>, msg_ok: &str, skipped: Option<&str>) -> CheckResult {
    make_res(CHECKS, FEP, cid, errs, msg_ok, skipped)
}

fn is_true(v: &Value) -> bool {
    matches!(v, Value::Bool(true))
}
fn is_control(e: &Map) -> bool {
    etype(e) == "trust_decision" && e.get("profile").as_str() == Some(PROFILE)
}
fn is_intent_td(e: &Map) -> bool {
    etype(e) == "trust_decision" && e.get("profile").as_str() == Some("intent")
}
/// Python `_int(x) and x >= 0`.
fn nonneg_int(v: &Value) -> bool {
    v.is_int() && v.as_f64().unwrap_or(-1.0) >= 0.0
}
fn fin(v: &Value) -> Option<f64> {
    match v {
        Value::Num(x, _) if x.is_finite() => Some(*x),
        _ => None,
    }
}
/// A list of finite numbers.
fn fin_list(v: &Value) -> Option<Vec<f64>> {
    match v {
        Value::Arr(a) => a.iter().map(fin).collect(),
        _ => None,
    }
}
/// Python `math.sqrt(sum(float(v) ** 2 for v in xs))`. Python raises OverflowError when a square
/// overflows (any exception is a rejection); here that gives `None`.
fn norm(xs: &[f64]) -> Option<f64> {
    let mut s = 0.0;
    for v in xs {
        let q = v * v;
        if !q.is_finite() {
            return None;
        }
        s += q;
    }
    Some(libm::sqrt(s))
}
fn units_for(q: &str) -> &'static [&'static str] {
    if q == "velocity" {
        VELOCITY_UNITS
    } else {
        POSITION_UNITS
    }
}

/// The parsed form of a valid declaration (only the fields the event rules need).
#[derive(Debug, Clone, PartialEq)]
pub struct ControlDeclaration {
    pub dims: usize,
    pub uncertainty: String,
}

/// The FEP-0005 section 2 errors of a `control_declaration` (empty = valid). `intent_ids`: `None` = no intent declaration.
pub fn validate_control_declaration(d: &Value, intent_ids: Option<&[String]>, null_intents: &[String]) -> Vec<String> {
    let d = match d {
        Value::Obj(m) => m,
        _ => return alloc::vec!["control_declaration must be an object".to_string()],
    };
    let mut e = Vec::new();
    let dims = d.get("dims");
    let dims_int = dims.is_int();
    let dv = dims.as_f64().unwrap_or(0.0);
    if !(dims_int && (1.0..=3.0).contains(&dv)) {
        e.push("dims must be an integer 1-3".to_string());
    }
    let q = d.get("quantity");
    let units = d.get("units");
    if !str_in(q, QUANTITIES) {
        e.push(format!("quantity {} is not one of {}", repr(q), repr(&str_list(QUANTITIES))));
    } else {
        let us = units_for(q.as_str().unwrap_or(""));
        if !str_in(units, us) {
            e.push(format!("units {} do not fit quantity {} (one of {})", repr(units), repr(q), repr(&str_list(us))));
        }
    }
    if !str_in(d.get("frame"), FRAMES) {
        e.push(format!("frame {} is not one of {}", repr(d.get("frame")), repr(&str_list(FRAMES))));
    }
    if !fin(d.get("rate_hz")).map_or(false, |r| r > 0.0) {
        e.push("rate_hz must be a number > 0".to_string());
    }
    if let Some(ax) = d.get_opt("axes") {
        let ok = match ax {
            Value::Arr(a) => {
                let all_str = a.iter().all(|x| matches!(x, Value::Str(s) if !s.is_empty()));
                let uniq: BTreeSet<&str> = a.iter().filter_map(|x| x.as_str()).collect();
                all_str && uniq.len() == a.len() && (!dims_int || a.len() as f64 == dv)
            }
            _ => false,
        };
        if !ok {
            e.push("axes must be a list of dims unique non-empty strings".to_string());
        }
    }
    let unc_default = Value::str("none");
    let unc = d.get_opt("uncertainty").unwrap_or(&unc_default);
    if !str_in(unc, UNCERTAINTY) {
        e.push(format!("uncertainty {} is not one of {}", repr(d.get("uncertainty")), repr(&str_list(UNCERTAINTY))));
    }
    for k in ["max_speed", "latency_s", "window_s"] {
        if let Some(v) = d.get_opt(k) {
            let ok = fin(v).map_or(false, |x| x >= 0.0 && (k != "max_speed" || x > 0.0));
            if !ok {
                e.push(format!("{} must be a number {}", k, if k == "max_speed" { "> 0" } else { ">= 0" }));
            }
        }
    }
    if q.as_str() == Some("position") && units.as_str() == Some("norm") && d.get("frame").as_str() != Some("screen") {
        e.push("normalised position (units norm) is defined only in the screen frame".to_string());
    }
    if let Some(ci) = d.get_opt("click_intent") {
        match (ci, intent_ids) {
            (Value::Str(_), None) => e.push("click_intent needs an intent_declaration (FEP-0003) in the same header".to_string()),
            (Value::Str(c), Some(ids)) => {
                if !ids.iter().any(|x| x == c) {
                    e.push(format!("click_intent '{}' is not a declared intent", c));
                } else if null_intents.iter().any(|x| x == c) {
                    e.push(format!("click_intent '{}' has role null", c));
                }
            }
            _ => e.push("click_intent must be a string".to_string()),
        }
    }
    e
}

/// The FEP-0005 section 3 errors of one `control` event, without the order rules.
pub fn validate_control_event(ev: &Map, decl: Option<&ControlDeclaration>) -> Vec<String> {
    let decl = match decl {
        Some(d) => d,
        None => return alloc::vec!["control event without a control_declaration in the header (rule 1)".to_string()],
    };
    let mut e = Vec::new();
    if !ev.get("t").is_fin_num() {
        e.push("t must be a finite number".to_string());
    }
    if !nonneg_int(ev.get("tick")) {
        e.push("tick must be an integer >= 0".to_string());
    }
    let vals = match ev.get("values") {
        Value::Arr(a) if a.len() == decl.dims => Some(a),
        _ => {
            e.push(format!("values must be a list of dims = {} numbers", decl.dims));
            None
        }
    };
    let absent: Option<Vec<bool>> = match ev.get("absent") {
        Value::Null => None,
        Value::Arr(a) if a.len() == decl.dims && a.iter().all(|x| matches!(x, Value::Bool(_))) => {
            Some(a.iter().map(|x| is_true(x)).collect())
        }
        _ => {
            e.push("absent must be a list of dims booleans".to_string());
            None
        }
    };
    if let Some(vals) = vals {
        for (j, v) in vals.iter().enumerate() {
            if absent.as_ref().map_or(false, |a| a[j]) {
                continue;
            }
            if !v.is_fin_num() {
                e.push(format!("values[{}] must be a finite number (or absent)", j));
            }
        }
    }
    let src_default = Value::str("decoder");
    let src = ev.get_opt("source").unwrap_or(&src_default);
    if !str_in(src, SOURCES) {
        e.push(format!("source {} is not one of {}", repr(src), repr(&str_list(SOURCES))));
    }
    if let Some(sd) = ev.get_opt("std") {
        let ok = match sd {
            Value::Arr(a) => a.len() == decl.dims && a.iter().all(|x| fin(x).map_or(false, |v| v > 0.0)),
            _ => false,
        };
        if !ok {
            e.push("std must be a list of dims numbers > 0".to_string());
        } else if decl.uncertainty != "std" {
            e.push("std given but the declaration has uncertainty = none (rule 3)".to_string());
        }
    } else if decl.uncertainty == "std" && src.as_str() == Some("decoder") {
        e.push("the declaration has uncertainty = std: a decoder control event MUST carry std (rule 3)".to_string());
    }
    let ts: Vec<&Value> = TIMING_FIELDS.iter().filter_map(|k| ev.get_opt(k)).collect();
    let tf: Option<Vec<f64>> = ts.iter().map(|v| fin(v)).collect();
    match tf {
        None => e.push("timing fields must be finite numbers".to_string()),
        Some(t) => {
            if t.windows(2).any(|w| w[1] < w[0]) {
                e.push("timing fields must satisfy t_signal_start <= t_signal_end <= t_decoded <= t_emitted (v0.1 3.8)".to_string());
            }
        }
    }
    if let Some(id) = ev.get_opt("id") {
        if !id.is_str() {
            e.push("id must be a string".to_string());
        }
    }
    e
}

/// The FEP-0005 section 4 errors of one `control_enable` event.
pub fn validate_enable_event(ev: &Map) -> Vec<String> {
    let mut e = Vec::new();
    if !matches!(ev.get("enabled"), Value::Bool(_)) {
        e.push("enabled must be a boolean".to_string());
    }
    if let Some(t) = ev.get_opt("t") {
        if !t.is_fin_num() {
            e.push("t must be a finite number".to_string());
        }
    }
    if let Some(s) = ev.get_opt("source") {
        if !str_in(s, ENABLE_SOURCES) {
            e.push(format!("source {} is not one of {}", repr(s), repr(&str_list(ENABLE_SOURCES))));
        }
    }
    if let Some(r) = ev.get_opt("reason") {
        if !r.is_str() {
            e.push("reason must be a string".to_string());
        }
    }
    e
}

// --- input rules ---------------------------------------------------------------------------

/// (declared intent ids, null-role intent ids) of a header's valid FEP-0003 declaration.
fn intent_ids(h: &Map) -> (Option<Vec<String>>, Vec<String>) {
    let d = h.get(INTENT_DECLARATION_KEY);
    if d.is_obj() && f3::validate_intent_declaration(d).is_empty() {
        let its = d.get("intents").as_arr().cloned().unwrap_or_default();
        let ids = its.iter().filter_map(|it| it.get("id").as_str().map(|s| s.to_string())).collect();
        let nulls = its
            .iter()
            .filter(|it| it.get("role").as_str() == Some("null"))
            .filter_map(|it| it.get("id").as_str().map(|s| s.to_string()))
            .collect();
        return (Some(ids), nulls);
    }
    (None, Vec::new())
}

pub fn decl_errors(events: &[Map]) -> Vec<String> {
    let mut out = Vec::new();
    for h in events {
        if etype(h) == "header" {
            if let Some(d) = h.get_opt(CONTROL_DECLARATION_KEY) {
                let (ids, nulls) = intent_ids(h);
                for x in validate_control_declaration(d, ids.as_deref(), &nulls) {
                    out.push(format!("line {}: {}", line_of(h), x));
                }
            }
        }
    }
    out
}

pub fn control_errors(events: &[Map]) -> Vec<String> {
    let mut out = Vec::new();
    let mut decl: Option<ControlDeclaration> = None;
    let mut has = false;
    let mut last_tick: Option<f64> = None;
    let mut last_t: Option<f64> = None;
    for e in events {
        let n = line_of(e);
        match etype(e) {
            "header" => {
                has = e.has(CONTROL_DECLARATION_KEY);
                decl = None;
                last_tick = None;
                last_t = None;
                if let Some(d) = e.get_opt(CONTROL_DECLARATION_KEY) {
                    let (ids, nulls) = intent_ids(e);
                    if validate_control_declaration(d, ids.as_deref(), &nulls).is_empty() {
                        decl = Some(ControlDeclaration {
                            dims: d.get("dims").as_f64().unwrap_or(0.0) as usize,
                            uncertainty: d.get("uncertainty").as_str().unwrap_or("none").to_string(),
                        });
                    }
                }
            }
            CONTROL => {
                if !has {
                    out.push(format!("line {}: control event without a control_declaration in the header (rule 1)", n));
                    continue;
                }
                let dc = match &decl {
                    Some(d) => d,
                    None => continue, // FEP5-DECL reports it
                };
                let errs = validate_control_event(e, Some(dc));
                let bad = !errs.is_empty();
                out.extend(errs.into_iter().map(|x| format!("line {}: {}", n, x)));
                let decoder = match e.get_opt("source") {
                    None => true,
                    Some(s) => s.as_str() == Some("decoder"),
                };
                if bad || !decoder {
                    continue;
                }
                let tick = e.get("tick").as_f64().unwrap_or(0.0);
                let t = e.get("t").as_f64().unwrap_or(0.0);
                if last_tick.map_or(false, |l| tick <= l) {
                    out.push(format!("line {}: tick {} does not increase (rule 2)", n, num_text(tick)));
                }
                if last_t.map_or(false, |l| t <= l) {
                    out.push(format!("line {}: t {} does not increase (rule 2)", n, num_text(t)));
                }
                last_tick = Some(tick);
                last_t = Some(t);
            }
            "pointer" => {
                if let (true, Some(dc)) = (has, &decl) {
                    if !py_eq(e.get("dims"), &Value::int(dc.dims as f64)) {
                        out.push(format!("line {}: pointer dims {} != declared dims {} (rule 4)", n, repr(e.get("dims")), dc.dims));
                    }
                }
            }
            _ => {}
        }
    }
    out
}

pub fn enable_errors(events: &[Map]) -> Vec<String> {
    let mut out = Vec::new();
    for e in events.iter().filter(|e| etype(e) == CONTROL_ENABLE) {
        for x in validate_enable_event(e) {
            out.push(format!("line {}: {}", line_of(e), x));
        }
    }
    out
}

pub fn intent_compat_errors(events: &[Map]) -> Vec<String> {
    let mut out = f3::decl_errors(events);
    out.extend(f3::vocab_errors(events));
    out.extend(f3::intent_errors(events));
    out.extend(f3::feedback_errors(events));
    out
}

// --- decision-log rules ----------------------------------------------------------------------

/// Format errors of one trust_decision: section 5 for control decisions, FEP-0003 / FEP-0001 for the others.
pub fn td_control_format_errors(e: &Map) -> Vec<String> {
    if !is_control(e) {
        return f3::td_intent_format_errors(e);
    }
    let mut errs = td_format_errors(e);
    let n = line_of(e);
    let mut x: Vec<String> = Vec::new();
    for k in ["shown", "utterance", "unit"] {
        if e.has(k) {
            x.push(format!("a control decision MUST NOT carry {} (rule 1)", k));
        }
    }
    if !nonneg_int(e.get("tick")) {
        x.push("tick must be an integer >= 0".into());
    }
    if !is_true(e.get("is_final")) {
        x.push("a control decision MUST be final (is_final = true) (rule 2)".into());
    }
    let act = e.get("action");
    let st = e.get("state");
    if !str_in(act, CONTROL_ACTIONS) {
        x.push(format!("control action {} is not one of {}", repr(act), repr(&str_list(CONTROL_ACTIONS))));
    }
    if !str_in(st, STATES) {
        x.push(format!("state {} is not one of {}", repr(st), repr(&str_list(STATES))));
    } else if str_in(act, CONTROL_ACTIONS) && str_in(st, MOVING) != (act.as_str() == Some("COMMIT")) {
        x.push(format!("state {} does not fit action {} (act/attenuate = COMMIT, hold/stop = ABSTAIN) (rule 3)", repr(st), repr(act)));
    }
    let vel = e.get("velocity");
    if !fin_list(vel).map_or(false, |v| (1..=3).contains(&v.len())) {
        x.push("velocity must be a list of 1-3 finite numbers".into());
    }
    if let Some(raw) = e.get_opt("raw") {
        let ok = fin_list(raw).map_or(false, |r| match vel {
            Value::Arr(v) => r.len() == v.len(),
            _ => true,
        });
        if !ok {
            x.push("raw must be a list of finite numbers, one per axis".into());
        }
    }
    if !fin(e.get("gain")).map_or(false, |g| (0.0..=1.0).contains(&g)) {
        x.push("gain must be a number in [0, 1]".into());
    }
    if !e.get("units").is_str() {
        x.push("units is required (string)".into());
    }
    if !fin(e.get("v_max")).map_or(false, |v| v > 0.0) {
        x.push("v_max is required: a number > 0 (rule 4)".into());
    }
    if !fin(e.get("ttl_s")).map_or(false, |v| v > 0.0) {
        x.push("ttl_s is required: a number > 0 (rule 4)".into());
    }
    if !nonneg_int(e.get("engagement")) {
        x.push("engagement is required: an integer >= 0".into());
    }
    if let Some(a) = e.get_opt("authority") {
        if !fin(a).map_or(false, |v| (0.0..=1.0).contains(&v)) {
            x.push("authority must be a number in [0, 1]".into());
        }
    }
    if let Some(r) = e.get_opt("radius") {
        if !fin(r).map_or(false, |v| v >= 0.0) {
            x.push("radius must be a number >= 0".into());
        }
        if !fin(e.get("level")).map_or(false, |v| v > 0.0 && v < 1.0) {
            x.push("a decision with radius needs level in (0, 1)".into());
        }
    }
    if let Some(r) = e.get_opt("reasons") {
        if !matches!(r, Value::Arr(a) if a.iter().all(|s| s.is_str())) {
            x.push("reasons must be a list of strings".into());
        }
    }
    if let Some(t) = e.get_opt("t") {
        if !t.is_fin_num() {
            x.push("t must be a finite number".into());
        }
    }
    errs.extend(x.into_iter().map(|m| format!("line {}: {}", n, m)));
    errs
}

/// seq over all profiles; text / intent finals as FEP-0003; control: ticks do not go back, a moving tick is never reused.
pub fn td_order_errors(events: &[Map]) -> Vec<String> {
    let others: Vec<Map> = events.iter().filter(|e| !is_control(e)).cloned().collect();
    let mut errs = f3::td_final_errors(&others);
    let mut last_seq: BTreeMap<String, f64> = BTreeMap::new();
    let mut last_move: BTreeMap<String, f64> = BTreeMap::new();
    let mut last_tick: BTreeMap<String, f64> = BTreeMap::new();
    for e in events {
        if etype(e) != "trust_decision" {
            continue;
        }
        let sid = match e.get_opt("session") {
            None => String::new(),
            Some(Value::Str(s)) => s.clone(),
            Some(_) => continue,
        };
        let n = line_of(e);
        let seq = e.get("seq");
        if seq.is_int() {
            let s = seq.as_f64().unwrap_or(0.0);
            if last_seq.get(&sid).map_or(false, |&l| s <= l) {
                errs.push(format!("line {}: seq {} does not increase in session '{}' (rule 5)", n, num_text(s), sid));
            }
            let m = last_seq.get(&sid).map_or(s, |&l| l.max(s));
            last_seq.insert(sid.clone(), m);
        }
        let tk = e.get("tick");
        if !is_control(e) || !tk.is_int() {
            continue;
        }
        let tick = tk.as_f64().unwrap_or(0.0);
        if last_tick.get(&sid).map_or(false, |&l| tick < l) {
            errs.push(format!("line {}: tick {} goes back in session '{}' (rule 5)", n, num_text(tick), sid));
        }
        let m = last_tick.get(&sid).map_or(tick, |&l| l.max(tick));
        last_tick.insert(sid.clone(), m);
        if e.get("action").as_str() == Some("COMMIT") {
            if last_move.get(&sid).map_or(false, |&l| tick <= l) {
                errs.push(format!("line {}: a second moving decision for tick {} (rule 5: one input moves once)", n, num_text(tick)));
            }
            last_move.insert(sid, tick);
        }
    }
    // Python sorted(set(errs), key=errs.index): unique, first occurrence order.
    let mut seen: BTreeSet<String> = BTreeSet::new();
    errs.retain(|x| seen.insert(x.clone()));
    errs
}

/// Section 6: no motion on hold / stop or no-signal reasons, speed bound, re-engage after a stop, no intent COMMIT while stopped.
pub fn safety_errors(events: &[Map]) -> Vec<String> {
    let others: Vec<Map> = events.iter().filter(|e| !is_control(e)).cloned().collect();
    let mut errs = f3::safety_errors(&others);
    // session -> engagement of the latched stop (-1 if not an integer); absent = not stopped (Python None).
    let mut stopped: BTreeMap<String, Value> = BTreeMap::new();
    let empty_sid = Value::str("");
    for e in events {
        if etype(e) != "trust_decision" {
            continue;
        }
        let sid = tuple_key(&[e.get_opt("session").unwrap_or(&empty_sid)]);
        let n = line_of(e);
        if !is_control(e) {
            if is_intent_td(e) && is_true(e.get("is_final")) && e.get("action").as_str() == Some("COMMIT") && stopped.contains_key(&sid) {
                errs.push(format!("line {}: intent COMMIT while the control is stopped (rule 7)", n));
            }
            continue;
        }
        let vel = match fin_list(e.get("velocity")) {
            Some(v) => v,
            None => continue,
        };
        let sp = match norm(&vel) {
            Some(s) => s,
            None => {
                errs.push(format!("line {}: velocity too large (Python OverflowError)", n));
                continue;
            }
        };
        let act = e.get("action").as_str();
        let st = e.get("state");
        let eng = e.get("engagement");
        let gain = fin(e.get("gain"));
        if act == Some("ABSTAIN") && sp != 0.0 {
            errs.push(format!("line {}: a {} decision with non-zero velocity (rule 1)", n, repr(st)));
        }
        if act == Some("ABSTAIN") {
            if let Some(g) = gain {
                if g != 0.0 {
                    errs.push(format!("line {}: a {} decision with gain {} (rule 1)", n, repr(st), num_text(g)));
                }
            }
        }
        if act == Some("COMMIT") {
            let bad: Vec<Value> = match e.get("reasons") {
                Value::Arr(a) => a.iter().filter(|r| str_in(r, NO_MOTION_REASONS)).cloned().collect(),
                _ => Vec::new(),
            };
            if !bad.is_empty() {
                errs.push(format!("line {}: a moving decision with the no-motion reason(s) {} (rule 2)", n, repr(&Value::Arr(bad))));
            }
            if let Some(vm) = fin(e.get("v_max")) {
                if sp > vm * (1.0 + SPEED_TOL) + SPEED_TOL {
                    errs.push(format!("line {}: speed {} above v_max {} (rule 3)", n, num_text(sp), num_text(vm)));
                }
            }
            if sp == 0.0 {
                errs.push(format!("line {}: a COMMIT with zero velocity (use hold) (rule 1)", n));
            }
            if let Some(s) = stopped.get(&sid) {
                if py_eq(eng, s) {
                    errs.push(format!("line {}: motion after a stop without a new engagement (rule 5)", n));
                }
            }
            if let (Some(raw), Some(_)) = (e.get_opt("raw").and_then(fin_list), gain) {
                let rs = match norm(&raw) {
                    Some(r) => r,
                    None => {
                        errs.push(format!("line {}: raw too large (Python OverflowError)", n));
                        continue;
                    }
                };
                let full = match e.get_opt("authority") {
                    None => true,
                    Some(a) => py_eq(a, &Value::float(1.0)),
                };
                if rs > 0.0 && full && sp > rs * (1.0 + SPEED_TOL) + SPEED_TOL {
                    errs.push(format!("line {}: output faster than the decoder output at full authority (rule 6)", n));
                }
            }
        }
        if st.as_str() == Some("stop") {
            let v = if eng.is_int() { eng.clone() } else { Value::int(-1.0) };
            stopped.insert(sid, v);
        } else if act == Some("COMMIT") && eng.is_int() {
            if let Some(s) = stopped.get(&sid) {
                if !py_eq(eng, s) {
                    stopped.remove(&sid);
                }
            }
        }
    }
    errs
}

/// The "acted" list of control decisions (NTS 1.0 6.4): the tick of each final control COMMIT.
pub fn moving_ticks(decisions: &[Map]) -> Vec<Value> {
    decisions
        .iter()
        .filter(|e| is_control(e) && is_true(e.get("is_final")) && e.get("action").as_str() == Some("COMMIT") && e.get("tick").is_int())
        .map(|e| e.get("tick").clone())
        .collect()
}

// --- checks, report, reference consumer -----------------------------------------------------

pub fn check_events(events: &[Map], parse_errors: Vec<String>) -> Vec<CheckResult> {
    let mut out = alloc::vec![res("FEP5-PARSE", Some(parse_errors), "", None)];
    let kind = stream_kind(events);
    let kerr = if kind != StreamKind::Unknown {
        Vec::new()
    } else {
        alloc::vec!["line 1 is neither a header nor a trust_decision, or a decision log has other events".to_string()]
    };
    out.push(res("FEP5-KIND", Some(kerr), kind.name(), None));
    let inp = kind == StreamKind::Input;
    let dec = kind == StreamKind::Decisions;
    let na_in = if inp { None } else { Some("not an input stream") };
    let na_dec = if dec { None } else { Some("not a decision log") };
    out.push(res("FEP5-DECL", inp.then(|| decl_errors(events)), "", na_in));
    out.push(res("FEP5-CONTROL", inp.then(|| control_errors(events)), "", na_in));
    out.push(res("FEP5-ENABLE", inp.then(|| enable_errors(events)), "", na_in));
    out.push(res("FEP5-INTENT", inp.then(|| intent_compat_errors(events)), "", na_in));
    let msg = format!("{} decision(s)", events.len());
    out.push(res("FEP5-TD-FORMAT", dec.then(|| events.iter().flat_map(td_control_format_errors).collect()), &msg, na_dec));
    out.push(res("FEP5-TD-ORDER", dec.then(|| td_order_errors(events)), "", na_dec));
    out.push(res("FEP5-SAFETY", dec.then(|| safety_errors(events)), "", na_dec));
    out
}

pub fn check_file(name: &str, bytes: &[u8]) -> TargetReport {
    let (events, perr) = read_events(bytes);
    let no_perr = perr.is_empty();
    let mut results = check_events(&events, perr);
    let kind = stream_kind(&events);
    let v01 = if kind == StreamKind::Input && no_perr {
        res("FEP5-V01-CORE", Some(v01_core_failures(bytes)), "v0.1 core passed", None)
    } else {
        res("FEP5-V01-CORE", None, "", Some("not an input stream"))
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
    let n = |x: usize| Value::int(x as f64);
    if kind == StreamKind::Decisions {
        let others: Vec<Map> = events.iter().filter(|e| !is_control(e)).cloned().collect();
        let (ai, at) = f3::acted(&others);
        return Map::from_pairs([
            ("kind", Value::str(kind.name())),
            ("decisions", n(events.len())),
            ("control_decisions", n(events.iter().filter(|e| is_control(e)).count())),
            ("moving_ticks", Value::Arr(moving_ticks(events))),
            ("acted_intents", Value::Arr(ai)),
            ("acted_texts", Value::Arr(at)),
        ]);
    }
    let count = |f: &dyn Fn(&Map) -> bool| events.iter().filter(|e| f(e)).count();
    Map::from_pairs([
        ("kind", Value::str(kind.name())),
        ("declarations", n(count(&|e| etype(e) == "header" && e.has(CONTROL_DECLARATION_KEY)))),
        ("controls", n(count(&|e| etype(e) == CONTROL))),
        ("pointers", n(count(&|e| etype(e) == "pointer"))),
        ("enables", n(count(&|e| etype(e) == CONTROL_ENABLE))),
        ("intents", n(count(&|e| etype(e) == "intent"))),
        ("n_frames", n(count(&|e| etype(e) == "frame"))),
    ])
}

pub fn consume(name: &str, bytes: &[u8]) -> Result<Value, Error> {
    reject_on_failure(&check_file(name, bytes))?;
    Ok(Value::Obj(summarize(&read_events(bytes).0)))
}
