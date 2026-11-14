//! Incremental (streaming) event validation: one event at a time, as the
//! Python `StreamingTrustLayer.push` checks its input
//! (`fidetype.trust.streaming`). Use it on a live stream, where the whole
//! file is not available. For a complete file, [`crate::load_stream`]
//! applies all core checks.

use alloc::string::String;
use alloc::vec;
use alloc::vec::Vec;
use alloc::format;

use crate::constants::{DECLARATION_KEY, NORM_TOL, SPEC_VERSION, VOCAB_TYPES};
use crate::error::Error;
use crate::json::{cp_len, num_text, parse_json, repr, str_in, Map, Value};
use crate::profiles::fep0001::validate_declaration;

/// Parse an event (JSON text). It must be an object with a string `type`.
pub fn parse_event(text: &str) -> Result<Map, Error> {
    let v = parse_json(text).map_err(|e| Error::event(format!("event is not a JSON value: {}", e.message)))?;
    check_event_object(v)
}

/// The event must be an object with a string `type`.
pub fn check_event_object(v: Value) -> Result<Map, Error> {
    match v {
        Value::Obj(m) if m.get("type").is_str() => Ok(m),
        _ => Err(Error::event("an event must be an object with a string \"type\"")),
    }
}

fn lp(x: &Value) -> Result<f64, Error> {
    match x {
        Value::Null => Ok(f64::NEG_INFINITY),
        Value::Num(v, _) => Ok(*v),
        other => Err(Error::event(format!("{} is not a number or null", repr(other)))),
    }
}

/// The dense float64 row of a dense or sparse frame event (spec 3.3, 6.2). Errors on a bad row.
pub fn frame_row(event: &Map, v: usize) -> Result<Vec<f64>, Error> {
    let row: Vec<f64> = if event.has("log_probs") {
        match event.get("log_probs") {
            Value::Arr(a) => a.iter().map(lp).collect::<Result<_, _>>()?,
            _ => return Err(Error::event("log_probs is not a list")),
        }
    } else if event.has("top_ids") {
        let (ids, vals) = match (event.get("top_ids"), event.get("top_log_probs")) {
            (Value::Arr(i), Value::Arr(x)) if i.len() == x.len() => (i, x),
            _ => return Err(Error::event("sparse frame needs top_ids and top_log_probs of the same length")),
        };
        let ok_ids = ids.iter().all(|x| x.is_int() && x.as_f64().map_or(false, |x| x >= 0.0 && x < v as f64));
        let mut s: Vec<f64> = ids.iter().filter_map(|x| x.as_f64()).collect();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap_or(core::cmp::Ordering::Equal));
        if !ok_ids || s.windows(2).any(|w| w[0] == w[1]) {
            return Err(Error::event("top_ids must be unique integers in 0..V-1"));
        }
        let rest = lp(event.get("rest_log_prob"))?;
        let mut row = vec![f64::NEG_INFINITY; v];
        let k = ids.len();
        if v > k && rest > f64::NEG_INFINITY {
            let fill = rest - libm::log((v - k) as f64);
            row.iter_mut().for_each(|x| *x = fill);
        }
        for (j, id) in ids.iter().enumerate() {
            row[id.as_f64().unwrap_or(0.0) as usize] = lp(&vals[j])?;
        }
        row
    } else {
        return Err(Error::event("frame has neither log_probs nor top_ids"));
    };
    if row.len() != v {
        return Err(Error::event(format!("frame has {} log-probabilities, vocab has {}", row.len(), v)));
    }
    if row.iter().any(|x| x.is_nan() || *x == f64::INFINITY) {
        return Err(Error::event("log_probs must not contain NaN or +inf"));
    }
    let m = row.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
    let lse = if m.is_finite() { m + libm::log(row.iter().map(|&x| libm::exp(x - m)).sum::<f64>()) } else { f64::NEG_INFINITY };
    if !(libm::fabs(lse) <= NORM_TOL) {
        return Err(Error::event(format!("frame log_probs must log-sum-exp to 0 (got {})", num_text(lse))));
    }
    Ok(row)
}

/// Check the n-best list of a `hypothesis` event (text, finite score, FEP-0001 evidence fields).
pub fn check_nbest(event: &Map) -> Result<(), Error> {
    let its = match event.get("nbest") {
        Value::Arr(a) => a,
        _ => return Err(Error::event("hypothesis needs an nbest list")),
    };
    for it in its {
        let text = match it.get("text") {
            Value::Str(s) if it.is_obj() => s,
            _ => return Err(Error::event("each nbest item needs a string text")),
        };
        if !it.get("score").is_fin_num() {
            return Err(Error::event("each nbest item needs a finite numeric score"));
        }
        for k in ["logp_acoustic", "logp_lm"] {
            let v = it.get(k);
            if !v.is_null() && !v.is_num() {
                return Err(Error::event(format!("{} must be a number", k)));
            }
        }
        let cc = it.get("char_confidences");
        if !cc.is_null() {
            match cc {
                Value::Arr(a) if a.len() == cp_len(text) => {
                    if a.iter().any(|c| !matches!(c, Value::Num(x, _) if *x >= 0.0 && *x <= 1.0)) {
                        return Err(Error::event("char_confidences must be numbers in [0, 1]"));
                    }
                }
                _ => return Err(Error::event("char_confidences must have one value per character")),
            }
        }
    }
    Ok(())
}

/// Check a header event as the streaming layer reads it. Returns the vocabulary size.
pub fn check_header(ev: &Map) -> Result<usize, Error> {
    if ev.get("spec_version").as_str() != Some(SPEC_VERSION) {
        return Err(Error::event(format!("spec_version must be '{}', not {}", SPEC_VERSION, repr(ev.get("spec_version")))));
    }
    let vocab = match ev.get("vocab") {
        Value::Arr(a) if a.iter().all(|t| t.is_str()) => a,
        _ => return Err(Error::event("vocab must be a list of unique strings")),
    };
    let mut toks: Vec<&str> = vocab.iter().filter_map(|t| t.as_str()).collect();
    toks.sort_unstable();
    if toks.windows(2).any(|w| w[0] == w[1]) {
        return Err(Error::event("vocab must be a list of unique strings"));
    }
    if !ev.has("blank_id") || !ev.has("vocab_type") {
        return Err(Error::event("the header needs vocab_type and blank_id (spec 6.2 rule 1)"));
    }
    if !str_in(ev.get("vocab_type"), VOCAB_TYPES) {
        return Err(Error::event(format!("vocab_type must be one of {}", VOCAB_TYPES.join(", "))));
    }
    let b = ev.get("blank_id");
    if !b.is_null() && !(b.is_int() && b.as_f64().map_or(false, |x| x >= 0.0 && x < vocab.len() as f64)) {
        return Err(Error::event(format!(
            "blank_id must be null or an integer in 0..{}, not {}",
            vocab.len() as i64 - 1,
            repr(b)
        )));
    }
    if let Some(d) = ev.get_opt(DECLARATION_KEY) {
        let errs = validate_declaration(d);
        if !errs.is_empty() {
            return Err(Error::event(format!("{} (FEP-0001 section 4)", errs.join("; "))));
        }
    }
    Ok(vocab.len())
}

/// Check a hypothesis event as the streaming layer reads it.
pub fn check_hypothesis(ev: &Map) -> Result<bool, Error> {
    let fin = match (ev.get("id"), ev.get("is_final")) {
        (Value::Str(_), Value::Bool(f)) => *f,
        _ => return Err(Error::event("hypothesis needs a string id and a boolean is_final")),
    };
    check_nbest(ev)?;
    if let Some(d) = ev.get_opt(DECLARATION_KEY) {
        let errs = validate_declaration(d);
        if !errs.is_empty() {
            return Err(Error::event(format!("{} (FEP-0001 section 4)", errs.join("; "))));
        }
    }
    Ok(fin)
}

/// What [`StreamValidator::push`] found.
#[derive(Debug, Clone, PartialEq)]
pub enum PushResult {
    Header { vocab_size: usize },
    Frame { t: f64, row: Vec<f64> },
    Hypothesis { is_final: bool },
    SegmentEnd,
    End,
    Ignored { reason: &'static str },
    Other,
}

impl PushResult {
    /// A short name: header, frame, hypothesis, segment_end, end, ignored, other.
    pub fn kind(&self) -> &'static str {
        match self {
            PushResult::Header { .. } => "header",
            PushResult::Frame { .. } => "frame",
            PushResult::Hypothesis { .. } => "hypothesis",
            PushResult::SegmentEnd => "segment_end",
            PushResult::End => "end",
            PushResult::Ignored { .. } => "ignored",
            PushResult::Other => "other",
        }
    }
}

/// Validate a NeuralTextStream event by event (no decoding, no trust policy).
///
/// Rules: header first; frame times increase strictly; frame rows are
/// normalised; hypothesis events have a string id, a boolean is_final and a
/// valid n-best list; events after `end` are ignored (spec 10, A5); unknown
/// event types are ignored (spec 6.2 rule 5).
#[derive(Debug, Clone)]
pub struct StreamValidator {
    pub header: Option<Map>,
    pub vocab_size: usize,
    pub last_t: f64,
    pub ended: bool,
    pub n_events: usize,
    pub ignored_events: usize,
}

impl Default for StreamValidator {
    fn default() -> Self {
        StreamValidator { header: None, vocab_size: 0, last_t: f64::NEG_INFINITY, ended: false, n_events: 0, ignored_events: 0 }
    }
}

impl StreamValidator {
    pub fn new() -> Self {
        Self::default()
    }

    /// Validate one event given as JSON text.
    pub fn push_text(&mut self, text: &str) -> Result<PushResult, Error> {
        let ev = parse_event(text)?;
        self.push(&ev)
    }

    /// Validate one parsed event.
    pub fn push(&mut self, ev: &Map) -> Result<PushResult, Error> {
        let typ: String = match ev.get("type") {
            Value::Str(s) => s.clone(),
            _ => return Err(Error::event("an event must be an object with a string \"type\"")),
        };
        let out = if typ == "header" {
            self.vocab_size = check_header(ev)?;
            self.header = Some(ev.clone());
            self.last_t = f64::NEG_INFINITY;
            self.ended = false;
            PushResult::Header { vocab_size: self.vocab_size }
        } else if self.header.is_none() {
            return Err(Error::event(format!("'{}' event before the header (spec 6.2 rule 1)", typ)));
        } else if self.ended {
            self.ignored_events += 1;
            PushResult::Ignored { reason: "after the end marker" }
        } else if typ == "frame" {
            let t = match ev.get("t") {
                Value::Num(t, _) if t.is_finite() => *t,
                _ => return Err(Error::event("frame needs a finite numeric t")),
            };
            if !(t > self.last_t) {
                return Err(Error::event(format!(
                    "frame t {} does not increase (last {}; spec 6.2 rule 4)",
                    num_text(t),
                    num_text(self.last_t)
                )));
            }
            let row = frame_row(ev, self.vocab_size)?;
            self.last_t = t;
            PushResult::Frame { t, row }
        } else if typ == "hypothesis" {
            PushResult::Hypothesis { is_final: check_hypothesis(ev)? }
        } else if typ == "segment_end" {
            PushResult::SegmentEnd
        } else if typ == "end" {
            self.ended = true;
            PushResult::End
        } else if typ == "signal_quality" {
            PushResult::Other
        } else {
            self.ignored_events += 1;
            PushResult::Ignored { reason: "event type not used by the validator" }
        };
        self.n_events += 1;
        Ok(out)
    }
}

