//! Helpers for `trust_decision` events (FEP-0001 section 3; intent decisions
//! of FEP-0003 section 5): what a consumer may act on, and the checks a
//! consumer can run on a live decision stream.
//!
//! - Rule 1: a consumer MUST NOT act on a decision with `is_final = false`.
//! - Rule 3: a bridge to a lossy output forwards only final COMMIT decisions
//!   (or a user selection after OFFER).
//! - Rule 9 (SHOULD): no final COMMIT with an empty or white-space text.

use alloc::collections::{BTreeMap, BTreeSet};
use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::json::{is_blank, num_text, parse_json, py_strip, Map, Value};
use crate::profiles::common::tuple_key;
use crate::profiles::fep0003::td_intent_format_errors;

/// What a consumer does with a decision.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecisionKind {
    Commit,
    Offer,
    Ask,
    Abstain,
    OfferWords,
    /// `is_final = false`: show only, never act.
    Preview,
    Invalid,
}

impl DecisionKind {
    pub fn name(self) -> &'static str {
        match self {
            DecisionKind::Commit => "commit",
            DecisionKind::Offer => "offer",
            DecisionKind::Ask => "ask",
            DecisionKind::Abstain => "abstain",
            DecisionKind::OfferWords => "offer_words",
            DecisionKind::Preview => "preview",
            DecisionKind::Invalid => "invalid",
        }
    }
    fn of_action(a: &str) -> Option<DecisionKind> {
        match a {
            "COMMIT" => Some(DecisionKind::Commit),
            "OFFER" => Some(DecisionKind::Offer),
            "ASK" => Some(DecisionKind::Ask),
            "ABSTAIN" => Some(DecisionKind::Abstain),
            "OFFER_WORDS" => Some(DecisionKind::OfferWords),
            _ => None,
        }
    }
}

/// The result of [`DecisionTracker::push`].
#[derive(Debug, Clone)]
pub struct HandledDecision {
    /// The event as received (empty if it was not a JSON object).
    pub event: Map,
    pub kind: DecisionKind,
    /// `profile`: "text" (default) or "intent".
    pub profile: String,
    /// Final COMMIT: the committed text (`shown[0]`) or the committed intent. `None` if omitted (privacy logs).
    pub committed: Option<String>,
    /// Texts or intents offered to the user (OFFER, ASK, OFFER_WORDS).
    pub offered: Vec<String>,
    /// True if a bridge to an output may forward it now (rules 1, 3 and 9).
    pub forward: bool,
    /// Rule violations (MUST): format, order, one final per utterance or unit.
    pub errors: Vec<String>,
    /// SHOULD-level findings, for example rule 9 (empty committed text).
    pub warnings: Vec<String>,
}

/// True for a final COMMIT (rule 1).
pub fn is_final_commit(d: &Map) -> bool {
    d.get("type").as_str() == Some("trust_decision")
        && matches!(d.get("is_final"), Value::Bool(true))
        && d.get("action").as_str() == Some("COMMIT")
}

/// The committed text of a final text COMMIT (`shown[0]`), or `None`.
pub fn committed_text(d: &Map) -> Option<String> {
    if !is_final_commit(d) || d.get("profile").as_str() == Some("intent") {
        return None;
    }
    match d.get("shown") {
        Value::Arr(a) => a.first().and_then(|s| s.as_str()).map(|s| s.to_string()),
        _ => None,
    }
}

/// FEP-0001 section 3 rule 9: a final COMMIT whose committed text is empty or
/// only white space. Returns a warning text, or `None`.
pub fn empty_commit_warning(d: &Map) -> Option<String> {
    let text = committed_text(d)?;
    if !is_blank(&text) {
        return None;
    }
    let why = match d.get("reason") {
        Value::Str(r) if !py_strip(r).is_empty() => format!(" (reason: {})", r),
        _ => " and gives no reason".to_string(),
    };
    Some(format!("FEP-0001 section 3 rule 9: final COMMIT with an empty committed text{}; a bridge SHOULD NOT forward it", why))
}

/// Track a stream of trust_decision events (one session or many) and tell the
/// consumer what to do with each one.
///
/// ```
/// use fidetype::trust::{DecisionTracker, DecisionKind};
/// let mut t = DecisionTracker::new();
/// let d = t.push_text(r#"{"type":"trust_decision","seq":0,"utterance":0,"is_final":true,"action":"COMMIT","p_top1":0.9,"score_semantics":"calibrated_prob","shown":["hello"]}"#);
/// assert_eq!(d.kind, DecisionKind::Commit);
/// assert!(d.forward);
/// assert_eq!(d.committed.as_deref(), Some("hello"));
/// ```
#[derive(Debug, Default, Clone)]
pub struct DecisionTracker {
    last_seq: BTreeMap<String, f64>,
    last: BTreeMap<String, f64>,
    finals: BTreeSet<String>,
    /// Number of decisions pushed.
    pub n: usize,
}

impl DecisionTracker {
    pub fn new() -> Self {
        Self::default()
    }

    /// Handle one decision given as JSON text.
    pub fn push_text(&mut self, text: &str) -> HandledDecision {
        match parse_json(text) {
            Ok(Value::Obj(m)) => self.push(&m),
            Ok(_) => self.invalid("a decision must be a JSON object".to_string()),
            Err(e) => self.invalid(e.message),
        }
    }

    fn invalid(&mut self, msg: String) -> HandledDecision {
        self.n += 1;
        HandledDecision {
            event: Map::new(),
            kind: DecisionKind::Invalid,
            profile: "text".to_string(),
            committed: None,
            offered: Vec::new(),
            forward: false,
            errors: alloc::vec![msg],
            warnings: Vec::new(),
        }
    }

    /// Handle one parsed decision.
    pub fn push(&mut self, ev: &Map) -> HandledDecision {
        self.n += 1;
        let mut errors: Vec<String> = Vec::new();
        if ev.get("type").as_str() != Some("trust_decision") {
            errors.push("not a trust_decision event".to_string());
        }
        for x in td_intent_format_errors(ev) {
            // drop the "line N: " prefix
            let s = match (x.starts_with("line "), x.find(": ")) {
                (true, Some(i)) => x[i + 2..].to_string(),
                _ => x,
            };
            errors.push(s);
        }
        errors.extend(self.order(ev));
        let profile = ev.get("profile").as_str().unwrap_or("text").to_string();
        let action = ev.get("action").as_str().and_then(DecisionKind::of_action);
        let fin = matches!(ev.get("is_final"), Value::Bool(true));
        let kind = if !errors.is_empty() {
            DecisionKind::Invalid
        } else if fin {
            action.unwrap_or(DecisionKind::Invalid)
        } else if action.is_some() {
            DecisionKind::Preview
        } else {
            DecisionKind::Invalid
        };
        let offered_raw = if profile == "intent" { ev.get("offered") } else { ev.get("shown") };
        let offered: Vec<String> = match offered_raw {
            Value::Arr(a) => a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect(),
            _ => Vec::new(),
        };
        let committed = if kind == DecisionKind::Commit {
            if profile == "intent" {
                ev.get("intent").as_str().map(|s| s.to_string())
            } else {
                committed_text(ev)
            }
        } else {
            None
        };
        let mut warnings = Vec::new();
        let w = empty_commit_warning(ev);
        let forward = kind == DecisionKind::Commit && committed.is_some() && w.is_none();
        if let Some(w) = w {
            warnings.push(w);
        }
        HandledDecision {
            event: ev.clone(),
            kind,
            profile,
            committed,
            offered: if kind == DecisionKind::Commit { Vec::new() } else { offered },
            forward,
            errors,
            warnings,
        }
    }

    /// seq increases per session; one final decision per (session, utterance) or (session, unit); none after it.
    fn order(&mut self, e: &Map) -> Vec<String> {
        let mut errs = Vec::new();
        let sid = match e.get_opt("session") {
            None => String::new(),
            Some(Value::Str(s)) => s.clone(),
            Some(_) => return errs,
        };
        let seq = e.get("seq");
        if seq.is_int() {
            let s = seq.as_f64().unwrap_or(0.0);
            if let Some(&l) = self.last_seq.get(&sid) {
                if s <= l {
                    errs.push(format!("seq {} does not increase in session '{}' (rule 5)", num_text(s), sid));
                }
            }
            let m = self.last_seq.get(&sid).map_or(s, |&l| l.max(s));
            self.last_seq.insert(sid.clone(), m);
        }
        let key = if e.get("profile").as_str() == Some("intent") { "unit" } else { "utterance" };
        let kv = e.get(key);
        if !kv.is_int() {
            return errs;
        }
        let val = kv.as_f64().unwrap_or(0.0);
        let pk = tuple_key(&[&Value::Str(sid.clone()), &Value::str(key)]);
        if let Some(&l) = self.last.get(&pk) {
            if val < l {
                errs.push(format!("{} {} goes back in session '{}' (rule 5)", key, num_text(val), sid));
            }
        }
        let m = self.last.get(&pk).map_or(val, |&l| l.max(val));
        self.last.insert(pk.clone(), m);
        let fk = format!("{}{}", pk, num_text(val));
        if self.finals.contains(&fk) {
            errs.push(format!("a decision for {} {} of session '{}' after its final one (rules 6-7)", key, num_text(val), sid));
        }
        if matches!(e.get("is_final"), Value::Bool(true)) {
            self.finals.insert(fk);
        }
        errs
    }
}

/// Handle every decision of a decision log (parsed events).
pub fn handle_decisions(events: &[Map]) -> Vec<HandledDecision> {
    let mut t = DecisionTracker::new();
    events.iter().map(|e| t.push(e)).collect()
}
