//! Conformance profile `fep-0002`: NeuralTextStream over LSL (port of
//! `fidetype.conformance.profiles.fep0002`). Each vector is a JSON scenario
//! (schema `fidetype.conformance.lsl-scenario/1`).
//!
//! `inlet` scenarios run through the scenario player of
//! [`super::lsl::run_inlet_scenario`]. Its decision counts come from a
//! structural model of the reference trust layer; all other values come from
//! the same binding logic as the Python reference.

use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::checks::CheckResult;
use crate::error::Error;
use crate::json::{decode_utf8, parse_json, parse_json_opts, repr, Map, Value};

use super::common::{make_res, CheckMeta, TargetReport};
use super::fep0001::{acted_texts, td_final_errors, td_format_errors};
use super::lsl::{
    check_binding, check_native_frames, decisions_info_errors, info_from_xml, nts_header, py_iter, run_inlet_scenario, LslStreamInfo,
    MARKERS_TYPE, NTS_STREAM_TYPE,
};

pub const FEP: &str = "FEP-0002";
pub const SCENARIO_SCHEMA: &str = "fidetype.conformance.lsl-scenario/1";

pub const CHECKS: &[CheckMeta] = &[
    ("FEP2-BINDING", "MUST", "9", "desc/fidetype/binding is a known version; event_clock is lsl or source"),
    ("FEP2-FRAMES", "MUST", "3", "Frames stream: type NTS, float32 or double64, V channels, labels in vocab order, srate = 1 / frame_period"),
    ("FEP2-DESC", "MUST", "4", "desc/fidetype/nts_header is a JSON object with spec_version 0.1; values is a known kind"),
    ("FEP2-MARKERS", "MUST", "5", "Events stream: type Markers, 1 string channel, irregular rate"),
    ("FEP2-DECISIONS", "MUST", "8", "Decisions stream: Markers, 1 string channel, role and event_type keys; samples are valid trust_decision events"),
    ("FEP2-CONSUME", "MUST", "3-7", "The reference consumer accepts the scenario"),
];

fn res(cid: &str, errs: Option<Vec<String>>, msg_ok: &str, skipped: Option<&str>) -> CheckResult {
    make_res(CHECKS, FEP, cid, errs, msg_ok, skipped)
}

/// Read a `decisions` scenario. Errors on rejection.
pub fn run_decisions_scenario(sc: &Map) -> Result<Value, Error> {
    let xml = sc.get_opt("info_xml").ok_or_else(|| Error::type_err("KeyError: 'info_xml'"))?;
    let xml = xml.as_str().ok_or_else(|| Error::type_err("info_xml must be a string"))?;
    let info = info_from_xml(xml)?;
    let mut errs = decisions_info_errors(&info);
    let mut events: Vec<Map> = Vec::new();
    let samples = match sc.get_opt("samples") {
        Some(s) => py_iter(s)?,
        None => Vec::new(),
    };
    for (k, s) in samples.iter().enumerate() {
        let n = k + 1;
        let text = match s {
            Value::Str(t) => t,
            // Python raises TypeError (not caught there) for a non-string sample
            _ => return Err(Error::type_err("the JSON object must be str, bytes or bytearray")),
        };
        let mut ev = match parse_json(text) {
            Ok(Value::Obj(m)) if m.get("type").as_str() == Some("trust_decision") => m,
            Ok(_) => {
                errs.push(format!("sample {}: not a trust_decision event", n));
                continue;
            }
            Err(e) => {
                errs.push(format!("sample {}: not JSON: {}", n, e.message));
                continue;
            }
        };
        ev.insert("_line", Value::int(n as f64));
        errs.extend(td_format_errors(&ev));
        events.push(ev);
    }
    errs.extend(td_final_errors(&events));
    if !errs.is_empty() {
        let first: Vec<String> = errs.into_iter().take(5).collect();
        return Err(Error::rejected(first.join("; "), &format!("{} 8", FEP), ""));
    }
    let fin = events.iter().filter(|e| matches!(e.get("is_final"), Value::Bool(true))).count();
    Ok(Value::Obj(Map::from_pairs([
        ("decisions", Value::int(events.len() as f64)),
        ("final", Value::int(fin as f64)),
        ("acted", Value::Arr(acted_texts(&events))),
    ])))
}

/// Parse a scenario file (Python `json.loads`: NaN / Infinity tokens are allowed here).
pub fn load_scenario(bytes: &[u8]) -> Result<Map, Error> {
    let text = decode_utf8(bytes)?;
    let sc = parse_json_opts(text, true)?;
    match sc {
        Value::Obj(m)
            if m.get("schema").as_str() == Some(SCENARIO_SCHEMA) && matches!(m.get("kind").as_str(), Some("inlet") | Some("decisions")) =>
        {
            Ok(m)
        }
        _ => Err(Error::rejected(format!("not a {} scenario", SCENARIO_SCHEMA), FEP, "")),
    }
}

/// Reference consumer of the profile: return a summary, or a rejection.
pub fn consume(_name: &str, bytes: &[u8]) -> Result<Value, Error> {
    let sc = load_scenario(bytes)?;
    if sc.get("kind").as_str() == Some("inlet") {
        run_inlet_scenario(&sc)
    } else {
        run_decisions_scenario(&sc)
    }
}

fn info_role(info: &LslStreamInfo) -> &'static str {
    if info.fid("role") == Some("trust_decisions") {
        "decisions"
    } else if info.channel_format == "string" {
        "events"
    } else {
        "frames"
    }
}

/// Producer checks of one LSL stream info.
pub fn check_info(info: &LslStreamInfo) -> Vec<CheckResult> {
    let role = info_role(info);
    let b_err: Vec<String> = match check_binding(info) {
        Ok(()) => Vec::new(),
        Err(e) => alloc::vec![e.message],
    };
    let mut out = alloc::vec![res("FEP2-BINDING", Some(b_err), info.fid("binding").unwrap_or("absent (0.1 assumed)"), None)];
    let mut header: Option<Map> = None;
    if role != "decisions" {
        let mut d_err: Vec<String> = Vec::new();
        match nts_header(info) {
            Ok(h) => header = h,
            Err(e) => d_err.push(e.message),
        }
        match &header {
            None if d_err.is_empty() => d_err.push("no desc/fidetype/nts_header".to_string()),
            Some(h) if h.get("spec_version").as_str() != Some("0.1") => {
                d_err.push(format!("nts_header spec_version {} is not '0.1'", repr(h.get("spec_version"))))
            }
            _ => {}
        }
        let values = info.fid("values").unwrap_or("log_probs");
        if !["log_probs", "probs", "logits"].contains(&values) {
            d_err.push(format!("values '{}' is not log_probs, probs or logits", values));
        }
        out.push(res("FEP2-DESC", Some(d_err), "", None));
    } else {
        out.push(res("FEP2-DESC", None, "", Some("decisions stream")));
    }
    if role == "frames" {
        let mut f_err = if info.type_ == NTS_STREAM_TYPE { Vec::new() } else { alloc::vec![format!("type '{}' is not '{}'", info.type_, NTS_STREAM_TYPE)] };
        if let Some(h) = &header {
            let n = h.get("vocab").as_arr().map_or(0, |a| a.len());
            if n as f64 != info.channel_count {
                f_err.push(format!("{} channels but the vocab has {} tokens", info.channel_count, n));
            }
            if let Err(e) = check_native_frames(info, h) {
                f_err.push(e.message);
            }
        }
        out.push(res("FEP2-FRAMES", Some(f_err), "", None));
    } else {
        out.push(res("FEP2-FRAMES", None, "", Some("not a frames stream")));
    }
    if role == "events" {
        let mut m_err = if info.type_ == MARKERS_TYPE { Vec::new() } else { alloc::vec![format!("type '{}' is not '{}'", info.type_, MARKERS_TYPE)] };
        if info.channel_count != 1.0 {
            m_err.push("an events stream has 1 channel".to_string());
        }
        if info.nominal_srate != 0.0 {
            m_err.push("an events stream has an irregular rate (nominal_srate 0)".to_string());
        }
        out.push(res("FEP2-MARKERS", Some(m_err), "", None));
    } else {
        out.push(res("FEP2-MARKERS", None, "", Some("not an events stream")));
    }
    if role == "decisions" {
        out.push(res("FEP2-DECISIONS", Some(decisions_info_errors(info)), "", None));
    } else {
        out.push(res("FEP2-DECISIONS", None, "", Some("not a decisions stream")));
    }
    out
}

/// Producer check: a stream info `.xml` file, or a scenario `.json` file.
pub fn check_file(name: &str, bytes: &[u8]) -> TargetReport {
    if name.to_lowercase().ends_with(".xml") {
        let info = decode_utf8(bytes).and_then(info_from_xml);
        return match info {
            Ok(info) => TargetReport {
                target: name.to_string(),
                checks: check_info(&info),
                info: Map::from_pairs([("format", Value::str("lsl-info-xml")), ("role", Value::str(info_role(&info)))]),
            },
            Err(e) => TargetReport {
                target: name.to_string(),
                checks: alloc::vec![res("FEP2-BINDING", Some(alloc::vec![e.to_string()]), "", None)],
                info: Map::from_pairs([("format", Value::str("lsl-info-xml"))]),
            },
        };
    }
    let sc = match load_scenario(bytes) {
        Ok(sc) => sc,
        Err(e) => {
            return TargetReport {
                target: name.to_string(),
                checks: alloc::vec![res("FEP2-CONSUME", Some(alloc::vec![e.to_string()]), "", None)],
                info: Map::from_pairs([("format", Value::str("lsl-scenario"))]),
            }
        }
    };
    let decisions = sc.get("kind").as_str() == Some("decisions");
    let cid = if decisions { "FEP2-DECISIONS" } else { "FEP2-CONSUME" };
    let r = if decisions { run_decisions_scenario(&sc) } else { run_inlet_scenario(&sc) };
    let check = match r {
        Ok(_) => res(cid, Some(Vec::new()), "accepted", None),
        Err(e) => res(cid, Some(alloc::vec![e.to_string()]), "", None),
    };
    TargetReport {
        target: name.to_string(),
        checks: alloc::vec![check],
        info: Map::from_pairs([("format", Value::str("lsl-scenario")), ("kind", sc.get("kind").clone())]),
    }
}

/// Keys of the inlet summary that the structural trust model computes from
/// counts only. They match the Python reference on the golden vectors, but
/// they are not a trust-layer implementation.
pub const STRUCTURAL_KEYS: &[&str] = &["decisions", "final_decisions", "aborted_utterances"];
