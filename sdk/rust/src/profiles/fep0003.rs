//! Conformance profile `fep-0003`: output profiles and discrete intent events
//! (port of `fidetype.conformance.profiles.fep0003` and the validators of
//! `fidetype.trust.intent`).

use alloc::collections::{BTreeMap, BTreeSet};
use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::checks::CheckResult;
use crate::constants::{FEEDBACK_OUTCOMES, INTENT_ACTIONS, INTENT_DECLARATION_KEY, INTENT_ROLES, RISK_CLASSES, SCORE_SEMANTICS};
use crate::error::Error;
use crate::json::{num_text, py_eq, py_strip, repr, str_in, str_list, Map, Value};

use super::common::{etype, line_of, make_res, read_events, reject_on_failure, stream_kind, tuple_key, CheckMeta, StreamKind, TargetReport};
use super::fep0001::{session_of, td_format_errors, v01_core_failures};

pub const FEP: &str = "FEP-0003";
const PROFILE: &str = "intent";
const PROFILES: &[&str] = &["text", "intent"];
const PROB_SEMANTICS: &[&str] = &["calibrated_prob", "uncalibrated_prob"];
const UNIQUE_ROLES: &[&str] = &["confirm", "cancel", "undo"];
const SUM_TOL: f64 = 1e-6;

pub const CHECKS: &[CheckMeta] = &[
    ("FEP3-PARSE", "MUST", "1 (6.2 v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"),
    ("FEP3-KIND", "MUST", "1", "The file is an input stream (header first) or a decision log (only trust_decision)"),
    ("FEP3-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"),
    ("FEP3-DECL", "MUST", "2 table, r1-r4", "intent_declaration has the defined form"),
    ("FEP3-VOCAB", "MUST", "2 r5", "On a command-vocabulary stream with a declaration, vocab (without blank) equals the declared intents"),
    ("FEP3-INTENT", "MUST", "3 table, r1-r5", "intent events: declared, unique candidates; scores fit their semantics; ranked"),
    ("FEP3-FEEDBACK", "MUST", "4 table", "intent_feedback events have the defined form"),
    ("FEP3-TD-FORMAT", "MUST", "5 table, r1-r3", "Intent trust_decision fields (profile, unit, intent, offered, risk_class, no shown)"),
    ("FEP3-TD-FINAL", "MUST", "5 r4, 7 r2", "Per session: seq increases over both profiles; one final decision per intent unit; none after it"),
    ("FEP3-SAFETY", "MUST", "6 r1-r6", "No null COMMIT; COMMIT p >= threshold; irreversible COMMIT confirmed; valid undo"),
];

fn res(cid: &str, errs: Option<Vec<String>>, msg_ok: &str, skipped: Option<&str>) -> CheckResult {
    make_res(CHECKS, FEP, cid, errs, msg_ok, skipped)
}

fn is_intent(e: &Map) -> bool {
    etype(e) == "trust_decision" && e.get("profile").as_str() == Some(PROFILE)
}
fn is_true(v: &Value) -> bool {
    matches!(v, Value::Bool(true))
}

/// The FEP-0003 section 2 errors of an `intent_declaration` (empty = valid).
pub fn validate_intent_declaration(d: &Value) -> Vec<String> {
    let d = match d {
        Value::Obj(m) => m,
        _ => return alloc::vec!["intent_declaration must be a JSON object".to_string()],
    };
    let mut errs = Vec::new();
    for k in ["vocab_id", "vocab_version"] {
        if let Some(v) = d.get_opt(k) {
            if !matches!(v, Value::Str(s) if !s.is_empty()) {
                errs.push(format!("intent_declaration {} must be a non-empty string", k));
            }
        }
    }
    let its = match d.get("intents") {
        Value::Arr(a) if !a.is_empty() => a,
        _ => {
            errs.push("intent_declaration intents must be a non-empty list".to_string());
            return errs;
        }
    };
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut roles: BTreeMap<String, usize> = BTreeMap::new();
    for (j, it) in its.iter().enumerate() {
        let w = format!("intents[{}]", j);
        let it = match it {
            Value::Obj(m) => m,
            _ => {
                errs.push(format!("{} must be an object", w));
                continue;
            }
        };
        match it.get("id") {
            Value::Str(iid) if !py_strip(iid).is_empty() => {
                if seen.contains(iid) {
                    errs.push(format!("{} id '{}' is not unique", w, iid));
                } else {
                    seen.insert(iid.clone());
                }
            }
            _ => errs.push(format!("{} id must be a non-empty string", w)),
        }
        if !str_in(it.get("risk"), RISK_CLASSES) {
            errs.push(format!("{} risk {} is not one of {}", w, repr(it.get("risk")), repr(&str_list(RISK_CLASSES))));
        }
        let role = it.get_opt("role").cloned().unwrap_or(Value::str("action"));
        match &role {
            Value::Str(r) if INTENT_ROLES.contains(&r.as_str()) => *roles.entry(r.clone()).or_insert(0) += 1,
            _ => errs.push(format!("{} role {} is not one of {}", w, repr(&role), repr(&str_list(INTENT_ROLES)))),
        }
        if let Some(l) = it.get_opt("label") {
            if !l.is_str() {
                errs.push(format!("{} label must be a string", w));
            }
        }
    }
    for r in UNIQUE_ROLES {
        let c = roles.get(*r).copied().unwrap_or(0);
        if c > 1 {
            errs.push(format!("at most one intent may have role '{}' ({} found)", r, c));
        }
    }
    let good: Vec<&Map> = its.iter().filter_map(|i| i.as_obj()).collect();
    if good.iter().any(|it| it.get("risk").as_str() == Some("irreversible")) {
        for it in &good {
            if it.get("role").as_str() == Some("confirm") && it.get("risk").as_str() != Some("irreversible") {
                errs.push(format!(
                    "the confirm intent {} executes irreversible intents, so its risk must be 'irreversible' (FEP-0003 section 2 rule 4)",
                    repr(it.get("id"))
                ));
            }
        }
    }
    let non_null: usize = ["action", "confirm", "cancel", "undo"].iter().map(|r| roles.get(*r).copied().unwrap_or(0)).sum();
    if non_null == 0 {
        errs.push("intent_declaration needs at least one intent that is not null".to_string());
    }
    errs
}

/// Intent ids of a valid declaration.
fn decl_ids(d: &Value) -> Vec<String> {
    d.get("intents").as_arr().map(|a| a.iter().filter_map(|it| it.get("id").as_str().map(|s| s.to_string())).collect()).unwrap_or_default()
}

/// The FEP-0003 section 3 errors of one `intent` event (empty = valid).
pub fn validate_intent_event(ev: &Map, vocab: Option<&[String]>) -> Vec<String> {
    let mut errs = Vec::new();
    if vocab.is_none() {
        errs.push("an intent event needs an intent_declaration in the header".to_string());
    }
    if !matches!(ev.get("id"), Value::Str(s) if !s.is_empty()) {
        errs.push("id must be a non-empty string".to_string());
    }
    if !ev.get("t").is_fin_num() {
        errs.push("t must be a finite number".to_string());
    }
    if !matches!(ev.get("is_final"), Value::Bool(_)) {
        errs.push("is_final must be a boolean".to_string());
    }
    let sem = ev.get("score_semantics");
    if !str_in(sem, SCORE_SEMANTICS) {
        errs.push(format!("score_semantics {} is not one of {}", repr(sem), repr(&str_list(SCORE_SEMANTICS))));
    }
    for k in ["t_start", "t_end"] {
        if let Some(v) = ev.get_opt(k) {
            if !v.is_fin_num() {
                errs.push(format!("{} must be a finite number", k));
            }
        }
    }
    if let Some(r) = ev.get_opt("revision_of") {
        if !r.is_null() && !r.is_str() {
            errs.push("revision_of must be a string or null".to_string());
        }
    }
    let cands = match ev.get("candidates") {
        Value::Arr(a) if !a.is_empty() => a,
        _ => {
            errs.push("candidates must be a non-empty list".to_string());
            return errs;
        }
    };
    let sem_s = sem.as_str().unwrap_or("\u{0}");
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut scores: Vec<f64> = Vec::new();
    for (j, c) in cands.iter().enumerate() {
        let w = format!("candidates[{}]", j);
        let iid = match c.get("intent") {
            Value::Str(s) if c.is_obj() => s.clone(),
            _ => {
                errs.push(format!("{} must be an object with a string intent", w));
                continue;
            }
        };
        if seen.contains(&iid) {
            errs.push(format!("{} intent '{}' appears twice", w, iid));
        }
        seen.insert(iid.clone());
        if let Some(v) = vocab {
            if !v.iter().any(|x| *x == iid) {
                errs.push(format!("{} intent '{}' is not in the declaration", w, iid));
            }
        }
        let sc = c.get("score");
        if sem_s == "none" {
            if !sc.is_null() {
                errs.push(format!("{} score must be null or absent with score_semantics none", w));
            }
        } else if PROB_SEMANTICS.contains(&sem_s) {
            match sc {
                Value::Num(x, _) if x.is_finite() && *x >= 0.0 && *x <= 1.0 => scores.push(*x),
                _ => errs.push(format!("{} score must be a number in [0, 1]", w)),
            }
        } else if sem_s == "power" || sem_s == "strength" {
            match sc {
                Value::Num(x, _) if x.is_finite() => scores.push(*x),
                _ => errs.push(format!("{} score must be a finite number", w)),
            }
        }
    }
    // Python sum(): left-to-right float addition.
    let total = scores.iter().fold(0.0, |s, x| s + x);
    if PROB_SEMANTICS.contains(&sem_s) && !scores.is_empty() && total > 1.0 + SUM_TOL {
        errs.push(format!("candidate scores sum to {:.6} > 1", total));
    }
    if sem_s != "none" && scores.len() == cands.len() && scores.windows(2).any(|w| w[1] > w[0] + 1e-12) {
        errs.push("candidates must be ranked best first (scores non-increasing)".to_string());
    }
    errs
}

/// The FEP-0003 section 4 errors of one `intent_feedback` event.
pub fn validate_feedback_event(ev: &Map, vocab: Option<&[String]>) -> Vec<String> {
    let mut errs = Vec::new();
    let ru = ev.get("ref_unit");
    if !(ru.is_int() && ru.as_f64().unwrap_or(-1.0) >= 0.0) {
        errs.push("ref_unit must be an integer >= 0".to_string());
    }
    let outcome = ev.get("outcome");
    if !str_in(outcome, FEEDBACK_OUTCOMES) {
        errs.push(format!("outcome {} is not one of {}", repr(outcome), repr(&str_list(FEEDBACK_OUTCOMES))));
    }
    if outcome.as_str() == Some("selected") && !ev.get("intent").is_str() {
        errs.push("outcome selected needs the selected intent".to_string());
    }
    if let Some(i) = ev.get_opt("intent") {
        match i {
            Value::Null => {}
            Value::Str(s) => {
                if let Some(v) = vocab {
                    if !v.iter().any(|x| x == s) {
                        errs.push(format!("intent '{}' is not in the declaration", s));
                    }
                }
            }
            _ => errs.push("intent must be a string".to_string()),
        }
    }
    if let Some(t) = ev.get_opt("t") {
        if !t.is_fin_num() {
            errs.push("t must be a finite number".to_string());
        }
    }
    if let Some(s) = ev.get_opt("source") {
        if !s.is_str() {
            errs.push("source must be a string".to_string());
        }
    }
    errs
}

// --- input rules -------------------------------------------------------------------------

/// (header, declared ids if valid, declaration errors) for every header.
fn declarations(events: &[Map]) -> Vec<(&Map, Option<Vec<String>>, Vec<String>)> {
    let mut out = Vec::new();
    for e in events {
        if etype(e) != "header" {
            continue;
        }
        match e.get_opt(INTENT_DECLARATION_KEY) {
            None => out.push((e, None, Vec::new())),
            Some(d) => {
                let errs = validate_intent_declaration(d);
                let ids = if errs.is_empty() { Some(decl_ids(d)) } else { None };
                out.push((e, ids, errs));
            }
        }
    }
    out
}

pub fn decl_errors(events: &[Map]) -> Vec<String> {
    declarations(events).into_iter().flat_map(|(h, _, errs)| errs.into_iter().map(move |x| format!("line {}: {}", line_of(h), x))).collect()
}

pub fn vocab_errors(events: &[Map]) -> Vec<String> {
    let mut out = Vec::new();
    for (h, v, _) in declarations(events) {
        let ids = match v {
            Some(ids) if h.get("vocab_type").as_str() == Some("command") => ids,
            _ => continue,
        };
        let empty = Vec::new();
        let vocab = match h.get("vocab") {
            Value::Arr(a) if !a.is_empty() => a,
            _ => &empty,
        };
        let b = h.get("blank_id");
        let toks: Vec<&Value> = vocab.iter().enumerate().filter(|(j, _)| !py_eq(&Value::int(*j as f64), b)).map(|(_, t)| t).collect();
        let all_str = toks.iter().all(|t| t.is_str());
        let tset: BTreeSet<&str> = toks.iter().filter_map(|t| t.as_str()).collect();
        let iset: BTreeSet<&str> = ids.iter().map(|s| s.as_str()).collect();
        if !(all_str && tset == iset) {
            out.push(format!("line {}: command vocab without blank != declared intents (rule 5)", line_of(h)));
        }
    }
    out
}

pub fn intent_errors(events: &[Map]) -> Vec<String> {
    let mut out = Vec::new();
    let mut vocab: Option<Vec<String>> = None;
    let mut has_decl = false;
    let mut ids: BTreeSet<String> = BTreeSet::new();
    for e in events {
        match etype(e) {
            "header" => {
                has_decl = e.has(INTENT_DECLARATION_KEY);
                vocab = None;
                if let Some(d) = e.get_opt(INTENT_DECLARATION_KEY) {
                    if validate_intent_declaration(d).is_empty() {
                        vocab = Some(decl_ids(d));
                    }
                }
                ids.clear();
            }
            "intent" => {
                let n = line_of(e);
                if !has_decl {
                    out.push(format!("line {}: intent event without an intent_declaration in the header (rule 1)", n));
                    continue;
                }
                let v = match &vocab {
                    Some(v) => v,
                    None => continue, // FEP3-DECL reports it
                };
                for x in validate_intent_event(e, Some(v)) {
                    out.push(format!("line {}: {}", n, x));
                }
                if let Value::Str(id) = e.get("id") {
                    if ids.contains(id) {
                        out.push(format!("line {}: intent id '{}' is not unique in the stream", n, id));
                    }
                    ids.insert(id.clone());
                }
            }
            _ => {}
        }
    }
    out
}

pub fn feedback_errors(events: &[Map]) -> Vec<String> {
    let mut out = Vec::new();
    let mut vocab: Option<Vec<String>> = None;
    for e in events {
        match etype(e) {
            "header" => {
                let d = e.get(INTENT_DECLARATION_KEY);
                vocab = if !d.is_null() && validate_intent_declaration(d).is_empty() { Some(decl_ids(d)) } else { None };
            }
            "intent_feedback" => {
                for x in validate_feedback_event(e, vocab.as_deref()) {
                    out.push(format!("line {}: {}", line_of(e), x));
                }
            }
            _ => {}
        }
    }
    out
}

// --- decision-log rules ----------------------------------------------------------------------

/// Format errors of one trust_decision (FEP-0001 table for all; section 5 for intent decisions).
pub fn td_intent_format_errors(e: &Map) -> Vec<String> {
    let mut errs = td_format_errors(e);
    let n = line_of(e);
    let prof = e.get_opt("profile").cloned().unwrap_or(Value::str("text"));
    if !str_in(&prof, PROFILES) {
        errs.push(format!("line {}: profile {} is not one of {}", n, repr(&prof), repr(&str_list(PROFILES))));
        return errs;
    }
    if prof.as_str() != Some(PROFILE) {
        return errs;
    }
    let mut x: Vec<String> = Vec::new();
    let action = e.get("action");
    let act = action.as_str();
    if e.has("shown") {
        x.push("an intent decision MUST NOT carry shown (rule 2)".into());
    }
    if e.has("utterance") {
        x.push("an intent decision uses unit, not utterance (rule 1)".into());
    }
    let unit = e.get("unit");
    if !(unit.is_int() && unit.as_f64().unwrap_or(-1.0) >= 0.0) {
        x.push("unit must be an integer >= 0".into());
    }
    if !str_in(action, INTENT_ACTIONS) {
        x.push(format!("intent action {} is not one of {}", repr(action), repr(&str_list(INTENT_ACTIONS))));
    }
    if act == Some("COMMIT") && !e.get("intent").is_str() {
        x.push("a COMMIT needs the committed intent (rule 3)".into());
    }
    if let Some(i) = e.get_opt("intent") {
        if !i.is_str() {
            x.push("intent must be a string".into());
        }
    }
    if let Some(o) = e.get_opt("offered") {
        if !matches!(o, Value::Arr(a) if a.iter().all(|i| i.is_str())) {
            x.push("offered must be a list of strings".into());
        }
    }
    if act == Some("OFFER") && !matches!(e.get("offered"), Value::Arr(a) if !a.is_empty()) {
        x.push("an OFFER needs a non-empty offered list (rule 3)".into());
    }
    if let Some(r) = e.get_opt("risk_class") {
        if !r.is_null() && !str_in(r, RISK_CLASSES) {
            x.push(format!("risk_class {} is not one of {}", repr(r), repr(&str_list(RISK_CLASSES))));
        }
    }
    if act == Some("COMMIT") && !str_in(e.get("risk_class"), RISK_CLASSES) {
        x.push("a COMMIT needs risk_class (rule 3)".into());
    }
    if let Some(r) = e.get_opt("role") {
        if !r.is_null() && !str_in(r, INTENT_ROLES) {
            x.push(format!("role {} is not one of {}", repr(r), repr(&str_list(INTENT_ROLES))));
        }
    }
    if let Some(t) = e.get_opt("threshold") {
        if !t.is_null() && !matches!(t, Value::Num(v, _) if v.is_finite() && *v >= 0.0 && *v <= 1.0) {
            x.push("threshold must be a number in [0, 1] or null".into());
        }
    }
    if let Some(c) = e.get_opt("confirm_required") {
        if !matches!(c, Value::Bool(_)) {
            x.push("confirm_required must be a boolean".into());
        }
    }
    if is_true(e.get("confirm_required")) && act != Some("OFFER") {
        x.push("confirm_required is only allowed on an OFFER".into());
    }
    for k in ["confirmation_of", "undo_of"] {
        if let Some(v) = e.get_opt(k) {
            if !(v.is_int() && v.as_f64().unwrap_or(-1.0) >= 0.0) {
                x.push(format!("{} must be an integer >= 0", k));
            }
        }
    }
    if let Some(c) = e.get_opt("confirmed_via") {
        if !str_in(c, &["intent", "feedback"]) {
            x.push("confirmed_via must be 'intent' or 'feedback'".into());
        }
    }
    errs.extend(x.into_iter().map(|m| format!("line {}: {}", n, m)));
    errs
}

/// seq per session over both profiles; one final decision per text utterance and per intent unit.
pub fn td_final_errors(events: &[Map]) -> Vec<String> {
    let mut errs = Vec::new();
    let mut last_seq: BTreeMap<String, f64> = BTreeMap::new();
    let mut last: BTreeMap<String, f64> = BTreeMap::new();
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
                    errs.push(format!("line {}: seq {} does not increase in session '{}' (section 7 rule 2)", n, num_text(s), sid));
                }
            }
            let m = last_seq.get(&sid).map_or(s, |&l| l.max(s));
            last_seq.insert(sid.clone(), m);
        }
        let key = if is_intent(e) { "unit" } else { "utterance" };
        let kv = e.get(key);
        if !kv.is_int() {
            continue;
        }
        let val = kv.as_f64().unwrap_or(0.0);
        let pk = format!("{}\u{1}{}", sid, key);
        if let Some(&l) = last.get(&pk) {
            if val < l {
                errs.push(format!("line {}: {} {} goes back in session '{}'", n, key, num_text(val), sid));
            }
        }
        let m = last.get(&pk).map_or(val, |&l| l.max(val));
        last.insert(pk.clone(), m);
        let fk = format!("{}\u{1}{}", pk, num_text(val));
        let fin = is_true(e.get("is_final"));
        if finals.contains(&fk) {
            let kind = if fin { "a second final decision" } else { "a decision" };
            errs.push(format!("line {}: {} for {} {} of session '{}' after its final one (rule 4)", n, kind, key, num_text(val), sid));
        }
        if fin {
            finals.insert(fk);
        }
    }
    errs
}

/// Section 6: null, threshold, confirmation and undo rules on final intent decisions.
pub fn safety_errors(events: &[Map]) -> Vec<String> {
    let mut errs = Vec::new();
    let mut offers: BTreeMap<String, Vec<Value>> = BTreeMap::new();
    let mut used: BTreeSet<String> = BTreeSet::new();
    let mut commits: BTreeMap<String, Value> = BTreeMap::new();
    let empty_sid = Value::str("");
    for e in events {
        if !is_intent(e) || !is_true(e.get("is_final")) {
            continue;
        }
        let n = line_of(e);
        let sid = e.get_opt("session").unwrap_or(&empty_sid);
        let unit = e.get("unit");
        let act = e.get("action").as_str();
        if act == Some("OFFER") {
            if let Value::Arr(o) = e.get("offered") {
                offers.insert(tuple_key(&[sid, unit]), o.clone());
            }
        }
        if act != Some("COMMIT") {
            continue;
        }
        if e.get("role").as_str() == Some("null") {
            errs.push(format!("line {}: COMMIT of a null intent (rule 1)", n));
        }
        let via_feedback = e.get("confirmed_via").as_str() == Some("feedback");
        if let (Value::Num(p, _), Value::Num(thr, _)) = (e.get("p_top1"), e.get("threshold")) {
            if !via_feedback && p.is_finite() && thr.is_finite() && *p < *thr - 1e-12 {
                errs.push(format!("line {}: COMMIT with p_top1 {} below its threshold {} (rule 3)", n, num_text(*p), num_text(*thr)));
            }
        }
        let sem = e.get("input").get("score_semantics");
        if str_in(sem, &["none", "power", "strength"]) && !via_feedback {
            errs.push(format!("line {}: COMMIT on input with score_semantics '{}' (rule 2)", n, sem.as_str().unwrap_or("")));
        }
        if e.get("risk_class").as_str() == Some("irreversible") {
            let rf = e.get("confirmation_of");
            let key = tuple_key(&[sid, rf]);
            if !rf.is_int() {
                errs.push(format!("line {}: irreversible COMMIT without confirmation_of (rule 4)", n));
            } else if !offers.get(&key).map_or(false, |o| o.iter().any(|x| py_eq(x, e.get("intent")))) {
                errs.push(format!(
                    "line {}: confirmation_of {} is not an earlier final OFFER of {} (rule 4)",
                    n,
                    repr(rf),
                    repr(e.get("intent"))
                ));
            } else if used.contains(&key) {
                errs.push(format!("line {}: OFFER unit {} is confirmed twice (rule 4)", n, repr(rf)));
            } else {
                used.insert(key);
            }
        }
        if let Some(u) = e.get_opt("undo_of") {
            let key = tuple_key(&[sid, u]);
            match commits.get(&key) {
                None => errs.push(format!("line {}: undo_of {} is not an earlier final COMMIT (rule 5)", n, repr(u))),
                Some(rc) if rc.as_str() == Some("irreversible") => {
                    errs.push(format!("line {}: undo_of {} targets an irreversible COMMIT (rule 5)", n, repr(u)))
                }
                _ => {}
            }
        }
        if unit.is_int() {
            commits.insert(tuple_key(&[sid, unit]), e.get("risk_class").clone());
        }
    }
    errs
}

/// (acted intents, acted texts): final intent COMMITs and final text COMMITs.
pub fn acted(decisions: &[Map]) -> (Vec<Value>, Vec<Value>) {
    let mut ai = Vec::new();
    let mut at = Vec::new();
    for e in decisions {
        if etype(e) != "trust_decision" || !is_true(e.get("is_final")) || e.get("action").as_str() != Some("COMMIT") {
            continue;
        }
        if is_intent(e) {
            ai.push(e.get("intent").clone());
        } else {
            at.push(match e.get("shown") {
                Value::Arr(a) if !a.is_empty() => a[0].clone(),
                _ => Value::Null,
            });
        }
    }
    (ai, at)
}

pub fn check_events(events: &[Map], parse_errors: Vec<String>) -> Vec<CheckResult> {
    let mut out = alloc::vec![res("FEP3-PARSE", Some(parse_errors), "", None)];
    let kind = stream_kind(events);
    let kerr = if kind != StreamKind::Unknown {
        Vec::new()
    } else {
        alloc::vec!["line 1 is neither a header nor a trust_decision, or a decision log has other events".to_string()]
    };
    out.push(res("FEP3-KIND", Some(kerr), kind.name(), None));
    let inp = kind == StreamKind::Input;
    let dec = kind == StreamKind::Decisions;
    let na_in = if inp { None } else { Some("not an input stream") };
    let na_dec = if dec { None } else { Some("not a decision log") };
    out.push(res("FEP3-DECL", inp.then(|| decl_errors(events)), "", na_in));
    out.push(res("FEP3-VOCAB", inp.then(|| vocab_errors(events)), "", na_in));
    out.push(res("FEP3-INTENT", inp.then(|| intent_errors(events)), "", na_in));
    out.push(res("FEP3-FEEDBACK", inp.then(|| feedback_errors(events)), "", na_in));
    let msg = format!("{} decision(s)", events.len());
    out.push(res("FEP3-TD-FORMAT", dec.then(|| events.iter().flat_map(td_intent_format_errors).collect()), &msg, na_dec));
    out.push(res("FEP3-TD-FINAL", dec.then(|| td_final_errors(events)), "", na_dec));
    out.push(res("FEP3-SAFETY", dec.then(|| safety_errors(events)), "", na_dec));
    out
}

pub fn check_file(name: &str, bytes: &[u8]) -> TargetReport {
    let (events, perr) = read_events(bytes);
    let no_perr = perr.is_empty();
    let mut results = check_events(&events, perr);
    let kind = stream_kind(&events);
    let v01 = if kind == StreamKind::Input && no_perr {
        res("FEP3-V01-CORE", Some(v01_core_failures(bytes)), "v0.1 core passed", None)
    } else {
        res("FEP3-V01-CORE", None, "", Some("not an input stream"))
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
        let (ai, at) = acted(events);
        return Map::from_pairs([
            ("kind", Value::str(kind.name())),
            ("decisions", n(events.len())),
            ("intent_decisions", n(events.iter().filter(|e| is_intent(e)).count())),
            ("final", n(events.iter().filter(|e| is_true(e.get("is_final"))).count())),
            ("acted_intents", Value::Arr(ai)),
            ("acted_texts", Value::Arr(at)),
        ]);
    }
    let count = |f: &dyn Fn(&Map) -> bool| events.iter().filter(|e| f(e)).count();
    Map::from_pairs([
        ("kind", Value::str(kind.name())),
        ("declarations", n(count(&|e| etype(e) == "header" && e.has(INTENT_DECLARATION_KEY)))),
        ("intents", n(count(&|e| etype(e) == "intent"))),
        ("final_intents", n(count(&|e| etype(e) == "intent" && is_true(e.get("is_final"))))),
        ("feedback", n(count(&|e| etype(e) == "intent_feedback"))),
        ("hypotheses", n(count(&|e| etype(e) == "hypothesis"))),
        ("n_frames", n(count(&|e| etype(e) == "frame"))),
    ])
}

pub fn consume(name: &str, bytes: &[u8]) -> Result<Value, Error> {
    reject_on_failure(&check_file(name, bytes))?;
    Ok(Value::Obj(summarize(&read_events(bytes).0)))
}
