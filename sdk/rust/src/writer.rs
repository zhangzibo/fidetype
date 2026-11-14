//! NeuralTextStream JSON Lines writer (spec 6.2), the Rust form of the
//! Python `fidetype.StreamWriter`. Each method checks its event and gives one
//! line to the sink. No operating system needed: the sink is a closure.
//!
//! ```
//! use fidetype::writer::{NtsWriter, WriterOptions};
//! let mut lines = Vec::new();
//! let mut w = NtsWriter::new(|l: &str| lines.push(l.to_string()), WriterOptions::new("my-decoder")).unwrap();
//! let mut row = vec![f64::NEG_INFINITY; 28];
//! row[1] = 0.0; // P("a") = 1
//! w.frame_log_probs(0.0, &row).unwrap();
//! w.segment_end(None, None).unwrap();
//! w.end().unwrap();
//! drop(w);
//! assert_eq!(lines.len(), 4);
//! ```

use alloc::collections::BTreeSet;
use alloc::string::{String, ToString};
use alloc::vec::Vec;
use alloc::format;

use crate::constants::{NORM_TOL, SCORE_SEMANTICS, SEGMENT_UNITS, SPEC_VERSION, VOCAB, VOCAB_TYPES};
use crate::error::{Error, ErrorKind};
use crate::json::{cp_len, dump_json, Map, Value};

/// Header options of a writer.
#[derive(Debug, Clone)]
pub struct WriterOptions {
    pub source: String,
    /// Default: the 28-token `char.b2q-28` vocabulary.
    pub vocab: Option<Vec<String>>,
    /// Default: `char`.
    pub vocab_type: String,
    /// Default: `Some(0)`. `None` = no blank (not a CTC decoder).
    pub blank_id: Option<usize>,
    pub frame_period: Option<f64>,
    pub latency: Option<f64>,
    pub meta: Map,
    /// Extra header keys (for example `clock_domain`, `decode_declaration`).
    pub extra_header: Map,
}

impl WriterOptions {
    pub fn new(source: &str) -> Self {
        WriterOptions {
            source: source.to_string(),
            vocab: None,
            vocab_type: "char".to_string(),
            blank_id: Some(0),
            frame_period: None,
            latency: None,
            meta: Map::new(),
            extra_header: Map::new(),
        }
    }
}

/// One n-best item of a hypothesis.
#[derive(Debug, Clone)]
pub struct NbestItem {
    pub text: String,
    pub score: f64,
    /// One value in [0, 1] per code point of `text` (FEP-0001 section 2).
    pub char_confidences: Option<Vec<f64>>,
    pub logp_acoustic: Option<f64>,
    pub logp_lm: Option<f64>,
}

impl NbestItem {
    pub fn new(text: &str, score: f64) -> Self {
        NbestItem { text: text.to_string(), score, char_confidences: None, logp_acoustic: None, logp_lm: None }
    }
}

fn usage(m: impl Into<String>) -> Error {
    Error::new(ErrorKind::Usage, m)
}

fn num(x: f64, name: &str) -> Result<f64, Error> {
    if x.is_finite() {
        Ok(x)
    } else {
        Err(usage(format!("{} must be a finite number", name)))
    }
}

fn round(x: f64, d: i32) -> f64 {
    let f = libm::pow(10.0, d as f64);
    libm::round(x * f) / f
}

/// The JSON Lines writer. `S` receives each line (without the line end).
pub struct NtsWriter<S: FnMut(&str)> {
    sink: S,
    pub vocab: Vec<String>,
    pub n_frames: usize,
    last_t: f64,
    ids: BTreeSet<String>,
    n_hyp: usize,
    ended: bool,
}

impl<S: FnMut(&str)> NtsWriter<S> {
    /// Check the options and write the header line.
    pub fn new(sink: S, opts: WriterOptions) -> Result<Self, Error> {
        let vocab: Vec<String> = opts.vocab.clone().unwrap_or_else(|| VOCAB.iter().map(|s| s.to_string()).collect());
        let uniq: BTreeSet<&String> = vocab.iter().collect();
        if vocab.is_empty() || uniq.len() != vocab.len() {
            return Err(usage("vocab must be a non-empty list of unique strings"));
        }
        if !VOCAB_TYPES.contains(&opts.vocab_type.as_str()) {
            return Err(usage(format!("vocab_type must be one of {}", VOCAB_TYPES.join(", "))));
        }
        if let Some(b) = opts.blank_id {
            if b >= vocab.len() {
                return Err(usage("blank_id is out of range"));
            }
        }
        if opts.source.is_empty() {
            return Err(usage("source must not be empty"));
        }
        let mut head = Map::new();
        head.insert("type", Value::str("header"));
        head.insert("spec_version", Value::str(SPEC_VERSION));
        head.insert("vocab", Value::Arr(vocab.iter().map(|s| Value::Str(s.clone())).collect()));
        head.insert("vocab_type", Value::Str(opts.vocab_type.clone()));
        head.insert("blank_id", opts.blank_id.map_or(Value::Null, |b| Value::int(b as f64)));
        head.insert("source", Value::Str(opts.source.clone()));
        if let Some(fp) = opts.frame_period {
            if !(num(fp, "frame_period")? > 0.0) {
                return Err(usage("frame_period must be > 0"));
            }
            head.insert("frame_period", Value::float(fp));
        }
        if let Some(lat) = opts.latency {
            if num(lat, "latency")? < 0.0 {
                return Err(usage("latency must be >= 0"));
            }
            head.insert("latency", Value::float(lat));
        }
        for (k, v) in opts.extra_header.iter() {
            head.insert(k, v.clone());
        }
        head.insert("meta", Value::Obj(opts.meta.clone()));
        let mut w = NtsWriter { sink, vocab, n_frames: 0, last_t: f64::NEG_INFINITY, ids: BTreeSet::new(), n_hyp: 0, ended: false };
        w.write(&Value::Obj(head))?;
        Ok(w)
    }

    fn write(&mut self, ev: &Value) -> Result<(), Error> {
        if self.ended {
            return Err(usage("the stream has ended"));
        }
        let line = dump_json(ev)?;
        (self.sink)(&line);
        Ok(())
    }

    /// Write any other event (an object with a string `type`) as it is.
    pub fn event(&mut self, ev: &Map) -> Result<(), Error> {
        if !ev.get("type").is_str() {
            return Err(usage("an event needs a string type"));
        }
        self.write(&Value::Obj(ev.clone()))
    }

    /// Write one frame of natural-log probabilities at time `t` (seconds).
    /// `-inf` is allowed. The row must sum to 1 within the spec tolerance;
    /// times must increase strictly.
    pub fn frame_log_probs(&mut self, t: f64, row: &[f64]) -> Result<(), Error> {
        if row.len() != self.vocab.len() {
            return Err(usage(format!("a frame needs {} values, got {}", self.vocab.len(), row.len())));
        }
        if row.iter().any(|v| v.is_nan() || *v == f64::INFINITY) {
            return Err(usage("log-probabilities must not be NaN or +inf"));
        }
        let fin: Vec<f64> = row.iter().copied().filter(|v| v.is_finite()).collect();
        if fin.is_empty() {
            return Err(usage("a frame needs at least one finite log-probability"));
        }
        let m = fin.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        let total = m + libm::log(fin.iter().map(|&v| libm::exp(v - m)).sum::<f64>());
        if libm::fabs(total) > NORM_TOL {
            return Err(usage(format!("the frame does not sum to 1 (logsumexp = {}); use logits for raw scores", total)));
        }
        num(t, "t")?;
        if t <= self.last_t {
            return Err(usage("frame times must increase strictly (spec 2)"));
        }
        self.last_t = t;
        let lp: Vec<Value> = row.iter().map(|&v| if v == f64::NEG_INFINITY { Value::Null } else { Value::float(round(v, 6)) }).collect();
        let ev = Map::from_pairs([("type", Value::str("frame")), ("t", Value::float(round(t, 9))), ("log_probs", Value::Arr(lp))]);
        self.write(&Value::Obj(ev))?;
        self.n_frames += 1;
        Ok(())
    }

    /// Write one frame of probabilities in [0, 1].
    pub fn frame_probs(&mut self, t: f64, probs: &[f64]) -> Result<(), Error> {
        if probs.iter().any(|&v| !(v >= 0.0) || v > 1.0 + NORM_TOL) {
            return Err(usage("probs must be in [0, 1]"));
        }
        let row: Vec<f64> = probs.iter().map(|&v| libm::log(v)).collect();
        self.frame_log_probs(t, &row)
    }

    /// Write one frame of raw scores (log-softmax is applied).
    pub fn frame_logits(&mut self, t: f64, logits: &[f64]) -> Result<(), Error> {
        let m = logits.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        let lse = m + libm::log(logits.iter().map(|&v| libm::exp(v - m)).sum::<f64>());
        let row: Vec<f64> = logits.iter().map(|&v| v - lse).collect();
        self.frame_log_probs(t, &row)
    }

    /// Write a text n-best list (spec 3.6). Items are best first. Returns the hypothesis id.
    pub fn hypothesis(
        &mut self,
        nbest: &[NbestItem],
        is_final: bool,
        id: Option<&str>,
        score_semantics: &str,
        t_range: Option<(f64, f64)>,
    ) -> Result<String, Error> {
        if !SCORE_SEMANTICS.contains(&score_semantics) {
            return Err(usage(format!("score_semantics must be one of {}", SCORE_SEMANTICS.join(", "))));
        }
        if nbest.is_empty() {
            return Err(usage("nbest must not be empty"));
        }
        let mut items = Vec::new();
        for it in nbest {
            let mut d = Map::new();
            d.insert("text", Value::Str(it.text.clone()));
            d.insert("score", Value::float(num(it.score, "score")?));
            if let Some(cc) = &it.char_confidences {
                if cc.len() != cp_len(&it.text) || cc.iter().any(|c| !(*c >= 0.0 && *c <= 1.0)) {
                    return Err(usage("char_confidences needs one value in [0, 1] per character"));
                }
                d.insert("char_confidences", Value::Arr(cc.iter().map(|&c| Value::float(c)).collect()));
            }
            if let Some(x) = it.logp_acoustic {
                d.insert("logp_acoustic", Value::float(num(x, "logp_acoustic")?));
            }
            if let Some(x) = it.logp_lm {
                d.insert("logp_lm", Value::float(num(x, "logp_lm")?));
            }
            items.push(Value::Obj(d));
        }
        let id = match id {
            Some(s) => s.to_string(),
            None => format!("h{}", self.n_hyp + 1),
        };
        if self.ids.contains(&id) {
            return Err(usage(format!("hypothesis id '{}' is already used", id)));
        }
        let mut ev = Map::from_pairs([
            ("type", Value::str("hypothesis")),
            ("id", Value::Str(id.clone())),
            ("is_final", Value::Bool(is_final)),
            ("score_semantics", Value::str(score_semantics)),
            ("nbest", Value::Arr(items)),
        ]);
        if let Some((a, b)) = t_range {
            ev.insert("t_start", Value::float(num(a, "t_start")?));
            ev.insert("t_end", Value::float(num(b, "t_end")?));
        }
        self.write(&Value::Obj(ev))?;
        self.ids.insert(id.clone());
        self.n_hyp += 1;
        Ok(id)
    }

    /// Write a signal-quality event (spec 3.9). `index` values are in [0, 1].
    pub fn signal_quality(&mut self, t: f64, value: f64, unit: &str) -> Result<(), Error> {
        num(value, "value")?;
        if unit == "index" && !(value >= 0.0 && value <= 1.0) {
            return Err(usage("an index value must be in [0, 1]"));
        }
        let ev = Map::from_pairs([
            ("type", Value::str("signal_quality")),
            ("t", Value::float(num(t, "t")?)),
            ("value", Value::float(value)),
            ("unit", Value::str(unit)),
        ]);
        self.write(&Value::Obj(ev))
    }

    /// Mark the end of an utterance (`segment_end`, FEP-0001 section 1).
    pub fn segment_end(&mut self, t: Option<f64>, unit: Option<&str>) -> Result<(), Error> {
        let mut ev = Map::from_pairs([("type", Value::str("segment_end"))]);
        if let Some(t) = t {
            ev.insert("t", Value::float(num(t, "t")?));
        }
        if let Some(u) = unit {
            if !SEGMENT_UNITS.contains(&u) {
                return Err(usage(format!("unit must be one of {}", SEGMENT_UNITS.join(", "))));
            }
            ev.insert("unit", Value::str(u));
        }
        self.write(&Value::Obj(ev))
    }

    /// Write the `end` event. Later writes fail.
    pub fn end(&mut self) -> Result<(), Error> {
        if !self.ended {
            self.write(&Value::Obj(Map::from_pairs([("type", Value::str("end"))])))?;
            self.ended = true;
        }
        Ok(())
    }
}

/// Build a complete JSON Lines text (header, events from `build`, `end`) in memory.
pub fn to_jsonl(
    opts: WriterOptions,
    build: impl FnOnce(&mut NtsWriter<&mut dyn FnMut(&str)>) -> Result<(), Error>,
) -> Result<String, Error> {
    let mut lines: Vec<String> = Vec::new();
    {
        let mut push = |l: &str| lines.push(l.to_string());
        let sink: &mut dyn FnMut(&str) = &mut push;
        let mut w = NtsWriter::new(sink, opts)?;
        build(&mut w)?;
        w.end()?;
    }
    let mut s = lines.join("\n");
    s.push('\n');
    Ok(s)
}
