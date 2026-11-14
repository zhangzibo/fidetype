//! Conformance profile `fep-0004`: NeuralTextStream over WebSocket (port of
//! `fidetype.conformance.profiles.fep0004`). Each vector is a JSON scenario
//! (schema `fidetype.conformance.ws-scenario/1`).
//!
//! `ingest` scenarios run through [`crate::ws::IngestCore`]. As in
//! `fep-0002`, the decision counts come from the structural model of the
//! reference trust layer (see [`super::lsl`]); all other values come from the
//! same binding logic as the Python reference.

use alloc::collections::{BTreeMap, BTreeSet};
use alloc::boxed::Box;
use alloc::format;
use alloc::string::{String, ToString};
use alloc::vec::Vec;

use crate::checks::CheckResult;
use crate::error::Error;
use crate::json::{decode_utf8, parse_json_opts, Map, Value};
use crate::ws::{Effects, IngestCore, IngestSettings, SubscriberCore, WsData, WS_REFUSAL_CODES, WS_SUBPROTOCOL};

use super::common::{make_res, CheckMeta, TargetReport};
use super::lsl::{Route, StructuralLayer};

pub const FEP: &str = "FEP-0004";
pub const SCENARIO_SCHEMA: &str = "fidetype.conformance.ws-scenario/1";
const STEP_KINDS: &[&str] = &["open", "msg", "raw", "binary", "drop", "close", "tick"];
const SETTING_KEYS: &[&str] = &["reorder_window", "reorder_timeout_s", "resume_timeout_s", "max_batch", "ack_every", "window", "ack_interval_s", "token"];

pub const CHECKS: &[CheckMeta] = &[
    ("FEP4-HANDSHAKE", "MUST", "4-5", "Subprotocol nts-ws.0.1; the first message is the NTS header with a known binding"),
    ("FEP4-FRAMING", "MUST", "3, 6", "Text messages with one JSON object each; ws_seq on every event; batches consecutive"),
    ("FEP4-ORDER", "MUST", "6", "Duplicates dropped, reorder window, gaps drop the open utterance"),
    ("FEP4-RESUME", "MUST", "8", "Resume after a broken connection; no decision on a cut utterance"),
    ("FEP4-AUTH", "MUST", "9", "Token hook: a refused token closes with 1008"),
    ("FEP4-DECISIONS", "MUST", "7", "Decisions channel: welcome, ws_seq without gaps (or resubscribe), FEP-0001 rules"),
    ("FEP4-CONSUME", "MUST", "3-8", "The reference consumer accepts the scenario"),
];

fn res(cid: &str, errs: Option<Vec<String>>, msg_ok: &str) -> CheckResult {
    make_res(CHECKS, FEP, cid, errs, msg_ok, None)
}

/// The runner part of `WSTrustRunner` with the structural layer: one layer per stream.
struct Runner {
    route: Route,
    layers: BTreeMap<String, StructuralLayer>,
    skip: BTreeSet<String>,
    decisions: usize,
    finals: usize,
    aborted: usize,
    skipped: usize,
    sessions: BTreeSet<String>,
}

impl Runner {
    fn new(route: Route) -> Self {
        Runner {
            route,
            layers: BTreeMap::new(),
            skip: BTreeSet::new(),
            decisions: 0,
            finals: 0,
            aborted: 0,
            skipped: 0,
            sessions: BTreeSet::new(),
        }
    }

    /// Push into the layer of `sid` (made on first use) and count the new decisions.
    fn with_layer(&mut self, sid: &str, f: impl FnOnce(&mut StructuralLayer) -> Result<(), Error>) -> Result<(), Error> {
        let route = self.route;
        let l = self.layers.entry(sid.to_string()).or_insert_with(|| StructuralLayer::new(route));
        let (d0, f0) = (l.decisions, l.finals);
        let r = f(l);
        let (d1, f1) = (l.decisions, l.finals);
        if d1 > d0 {
            self.sessions.insert(sid.to_string());
        }
        self.decisions += d1 - d0;
        self.finals += f1 - f0;
        r
    }

    fn abort(&mut self, sid: &str) {
        if let Some(l) = self.layers.get_mut(sid) {
            if l.pending() {
                self.aborted += 1;
            }
            l.abort();
        }
    }

    fn handle(&mut self, items: &[(String, Map)]) -> Result<(), Error> {
        for (sid, ev) in items {
            let typ = ev.get("type").as_str().unwrap_or("");
            if typ == "ws_status" {
                match ev.get("status").as_str() {
                    Some("gap") => {
                        self.abort(sid);
                        self.skip.insert(sid.clone());
                    }
                    Some("lost") | Some("replaced") => {
                        self.abort(sid);
                        self.skip.remove(sid);
                    }
                    Some("closed") => {
                        if self.layers.contains_key(sid) {
                            self.with_layer(sid, |l| l.end())?;
                            self.layers.remove(sid);
                        }
                    }
                    _ => {}
                }
                continue;
            }
            if self.skip.contains(sid) {
                if typ == "frame" {
                    self.skipped += 1;
                    continue;
                }
                if typ == "segment_end" || typ == "end" || typ == "header" {
                    self.skip.remove(sid);
                }
            }
            self.with_layer(sid, |l| l.push(ev))?;
        }
        Ok(())
    }

    fn flush(&mut self, sid: &str) -> Result<(), Error> {
        self.with_layer(sid, |l| l.end())
    }
}

/// The profile check that a refusal (close code, ws_error code, detail) fails.
pub fn refusal_check(code: u32, reason: &str, detail: &str) -> &'static str {
    if code == 1008 {
        "FEP4-AUTH"
    } else if code == 1002 || code == 4000 || (reason == "bad_header" && !detail.contains("resume")) {
        "FEP4-HANDSHAKE"
    } else if reason == "bad_header" {
        "FEP4-RESUME"
    } else {
        "FEP4-FRAMING"
    }
}

fn fin_num(v: &Value) -> Option<f64> {
    match v {
        Value::Num(x, _) if x.is_finite() => Some(*x),
        _ => None,
    }
}

/// Play an `ingest` scenario. Errors on rejection.
pub fn run_ingest_scenario(sc: &Map) -> Result<Value, Error> {
    let empty = Value::Obj(Map::new());
    let settings = match sc.get_opt("settings").unwrap_or(&empty) {
        Value::Obj(m) => m,
        _ => return Err(Error::type_err("settings must be an object")),
    };
    let bad: Vec<&str> = settings.keys().filter(|k| !SETTING_KEYS.contains(k)).collect();
    if !bad.is_empty() {
        return Err(Error::type_err(format!("unknown settings {}", bad.join(", "))));
    }
    let token: Option<String> = match settings.get("token") {
        Value::Null => None,
        Value::Str(t) if !t.is_empty() => Some(t.clone()),
        _ => return Err(Error::type_err("settings.token must be a non-empty string")),
    };
    let mut rest = settings.clone();
    rest.remove("token");
    let s = IngestSettings::from_map(&rest)?;
    let route = match sc.get_opt("route") {
        None => Route::Frames,
        Some(Value::Str(r)) if r == "frames" => Route::Frames,
        Some(Value::Str(r)) if r == "hypothesis" => Route::Hypothesis,
        Some(r) => return Err(Error::value(format!("unknown route {}", crate::json::repr(r)))),
    };
    let steps = match sc.get("steps") {
        Value::Arr(a) => a,
        _ => return Err(Error::type_err("steps must be a list")),
    };
    let auth: Option<crate::ws::AuthFn> = token.map(|tok| Box::new(move |t: Option<&str>| t == Some(tok.as_str())) as crate::ws::AuthFn);
    let mut core = IngestCore::new(s, auth);
    let mut runner = Runner::new(route);
    let mut seen_types: BTreeMap<String, usize> = BTreeMap::new();
    let mut sends: Vec<Map> = Vec::new();
    let mut closes: Vec<Value> = Vec::new();

    let mut apply = |eff: Effects, runner: &mut Runner| -> Result<(), Error> {
        for (_, m) in &eff.sends {
            sends.push(m.clone());
        }
        for (cid, code, reason) in &eff.closes {
            closes.push(Value::Arr(alloc::vec![Value::int(*cid), Value::int(*code as f64)]));
            if WS_REFUSAL_CODES.contains(code) {
                let err = eff.sends.iter().find(|(c, m)| c == cid && m.get("type").as_str() == Some("ws_error"));
                let detail = match err {
                    Some((_, m)) => match m.get("detail") {
                        Value::Str(d) => d.clone(),
                        Value::Null => String::new(),
                        other => crate::json::py_str(other),
                    },
                    None => reason.clone(),
                };
                return Err(Error::rejected(
                    format!("connection {} refused with close code {} ({}: {})", crate::json::num_text(*cid), code, reason, detail),
                    &format!("{} 9", FEP),
                    refusal_check(*code, reason, &detail),
                ));
            }
        }
        for (_, ev) in &eff.items {
            if let Value::Str(t) = ev.get("type") {
                if t != "ws_status" {
                    *seen_types.entry(t.clone()).or_insert(0) += 1;
                }
            }
        }
        runner.handle(&eff.items)
    };

    let mut at = 0.0f64;
    for (k, step) in steps.iter().enumerate() {
        let n = k + 1;
        let step = step.as_obj().ok_or_else(|| Error::type_err(format!("step {} must be an object", n)))?;
        let kinds: Vec<&str> = STEP_KINDS.iter().copied().filter(|x| step.has(x)).collect();
        if kinds.len() != 1 {
            return Err(Error::type_err(format!("step {} needs exactly one step kind", n)));
        }
        let kind = kinds[0];
        let t = match step.get_opt("at") {
            None => Some(at),
            Some(v) => fin_num(v),
        };
        at = match t {
            Some(t) if t >= at => t,
            _ => return Err(Error::value(format!("step {}: at must be a number >= the previous at", n))),
        };
        apply(core.tick(at), &mut runner)?;
        if kind == "tick" {
            continue;
        }
        let c = step.get("conn");
        if !(c.is_int() && c.as_f64().unwrap_or(0.0) >= 1.0) {
            return Err(Error::value(format!("step {}: conn must be an integer >= 1", n)));
        }
        let cid = c.as_f64().unwrap_or(1.0);
        let eff = match kind {
            "open" => {
                let o = step.get("open").as_obj().ok_or_else(|| Error::type_err(format!("step {}: open must be an object", n)))?;
                let subs: Vec<&str> = match o.get_opt("subprotocols") {
                    None => alloc::vec![WS_SUBPROTOCOL],
                    Some(Value::Arr(a)) if a.iter().all(|x| x.is_str()) => a.iter().filter_map(|x| x.as_str()).collect(),
                    Some(_) => return Err(Error::type_err(format!("step {}: subprotocols must be a list of strings", n))),
                };
                let auth = match o.get("authorization") {
                    Value::Null => None,
                    Value::Str(a) => Some(a.as_str()),
                    _ => return Err(Error::type_err(format!("step {}: authorization must be a string", n))),
                };
                core.open(cid, &subs, auth)
            }
            "msg" => core.message(cid, WsData::Value(step.get("msg").clone()), at),
            "raw" => match step.get("raw") {
                Value::Str(r) => core.message(cid, WsData::Text(r.clone()), at),
                _ => return Err(Error::type_err(format!("step {}: raw must be a string", n))),
            },
            "binary" => {
                if !matches!(step.get("binary"), Value::Bool(true)) {
                    return Err(Error::type_err(format!("step {}: binary must be true", n)));
                }
                core.message(cid, WsData::Binary, at)
            }
            _ => {
                if !matches!(step.get(kind), Value::Bool(true)) {
                    return Err(Error::type_err(format!("step {}: {} must be true", n, kind)));
                }
                core.disconnect(cid, at)
            }
        };
        apply(eff, &mut runner)?;
    }
    apply(core.finish(), &mut runner)?;
    for sid in core.live_streams() {
        runner.flush(&sid)?;
    }
    let st = &core.stats;
    let n = |x: usize| Value::int(x as f64);
    let frames = seen_types.get("frame").copied().unwrap_or(0);
    let welcomes: Vec<Value> = sends
        .iter()
        .filter(|m| m.get("type").as_str() == Some("ws_welcome"))
        .map(|m| Value::Arr(alloc::vec![m.get("stream_id").clone(), m.get("seq").clone(), m.get("resumed").clone()]))
        .collect();
    let acks: Vec<Value> = sends.iter().filter(|m| m.get("type").as_str() == Some("ws_ack")).map(|m| m.get("seq").clone()).collect();
    Ok(Value::Obj(Map::from_pairs([
        ("streams", n(st.streams)),
        ("event_types", Value::Obj(Map::from_pairs(seen_types.iter().map(|(k, v)| (k.clone(), Value::int(*v as f64)))))),
        ("frames", n(frames)),
        ("decisions", n(runner.decisions)),
        ("final_decisions", n(runner.finals)),
        ("sessions", Value::Arr(runner.sessions.iter().map(|s| Value::str(s)).collect())),
        ("aborted_utterances", n(runner.aborted)),
        ("skipped_after_gap", n(runner.skipped)),
        ("duplicates", n(st.duplicates)),
        ("reordered", n(st.reordered)),
        ("gaps", n(st.gaps)),
        ("missing_events", Value::int(st.missing_events)),
        ("resumes", n(st.resumes)),
        ("takeovers", n(st.takeovers)),
        ("lost_streams", n(st.lost_streams)),
        ("ignored_controls", n(st.ignored_controls)),
        ("welcomes", Value::Arr(welcomes)),
        ("acks", Value::Arr(acks)),
        ("closes", Value::Arr(closes)),
    ])))
}

/// Feed a `subscribe` scenario to the reference subscriber. Errors on rejection.
pub fn run_subscribe_scenario(sc: &Map) -> Result<Value, Error> {
    let msgs = match sc.get("messages") {
        Value::Arr(a) => a,
        _ => return Err(Error::type_err("messages must be a list")),
    };
    let from_seq = match sc.get_opt("from_seq") {
        None => Some(1.0),
        Some(Value::Null) => None,
        Some(v) if v.is_int() && v.as_f64().unwrap_or(0.0) >= 1.0 => v.as_f64(),
        Some(_) => return Err(Error::type_err("from_seq must be an integer >= 1 or null")),
    };
    let mut core = SubscriberCore::new(from_seq);
    let clause = format!("{} 7", FEP);
    for m in msgs {
        core.receive(m).map_err(|e| Error::rejected(e.message, &clause, ""))?;
    }
    core.finish().map_err(|e| Error::rejected(e.message, &clause, ""))
}

/// Parse a scenario file (Python `json.loads`: NaN / Infinity tokens are allowed here).
pub fn load_scenario(bytes: &[u8]) -> Result<Map, Error> {
    let text = decode_utf8(bytes)?;
    match parse_json_opts(text, true)? {
        Value::Obj(m)
            if m.get("schema").as_str() == Some(SCENARIO_SCHEMA) && matches!(m.get("kind").as_str(), Some("ingest") | Some("subscribe")) =>
        {
            Ok(m)
        }
        _ => Err(Error::rejected(format!("not a {} scenario", SCENARIO_SCHEMA), FEP, "")),
    }
}

/// Reference consumer of the profile: return a summary, or a rejection.
pub fn consume(_name: &str, bytes: &[u8]) -> Result<Value, Error> {
    let sc = load_scenario(bytes)?;
    if sc.get("kind").as_str() == Some("ingest") {
        run_ingest_scenario(&sc)
    } else {
        run_subscribe_scenario(&sc)
    }
}

/// Producer check: a scenario `.json` file.
pub fn check_file(name: &str, bytes: &[u8]) -> TargetReport {
    let sc = match load_scenario(bytes) {
        Ok(sc) => sc,
        Err(e) => {
            return TargetReport {
                target: name.to_string(),
                checks: alloc::vec![res("FEP4-CONSUME", Some(alloc::vec![e.to_string()]), "")],
                info: Map::from_pairs([("format", Value::str("ws-scenario"))]),
            }
        }
    };
    let ingest = sc.get("kind").as_str() == Some("ingest");
    let cid = if ingest { "FEP4-CONSUME" } else { "FEP4-DECISIONS" };
    let r = if ingest { run_ingest_scenario(&sc) } else { run_subscribe_scenario(&sc) };
    let check = match r {
        Ok(_) => res(cid, Some(Vec::new()), "accepted"),
        Err(e) => {
            let id = if e.check_id.is_empty() { cid.to_string() } else { e.check_id.clone() };
            res(&id, Some(alloc::vec![e.to_string()]), "")
        }
    };
    TargetReport {
        target: name.to_string(),
        checks: alloc::vec![check],
        info: Map::from_pairs([("format", Value::str("ws-scenario")), ("kind", sc.get("kind").clone())]),
    }
}

/// Keys of the ingest summary that the structural trust model computes from counts only.
pub const STRUCTURAL_KEYS: &[&str] = &["decisions", "final_decisions", "aborted_utterances", "sessions"];
