//! Constants of NeuralTextStream v0.1 and the FEPs (copied from the spec and the Python reference).

pub const SPEC_VERSION: &str = "0.1";
/// Tolerance of the row normalisation rule (spec 5.2.1).
pub const NORM_TOL: f64 = 1e-3;
pub const VOCAB_TYPES: &[&str] = &["char", "key", "word", "phoneme", "command", "other"];
pub const SCORE_SEMANTICS: &[&str] = &["calibrated_prob", "uncalibrated_prob", "power", "strength", "none"];
pub const CLOCK_DOMAINS: &[&str] = &["lsl", "unix", "monotonic", "trial", "other"];
pub const SQ_UNITS: &[&str] = &["index", "snr_db", "impedance_ohm", "other"];
pub const MODALITIES: &[&str] = &["emg", "eeg", "meg", "opm-meg", "ecog", "intracortical", "fnirs", "other"];
/// JSON Lines event kinds of spec 3.0, plus `end`.
pub const EVENT_TYPES: &[&str] = &["frame", "decision", "hypothesis", "pointer", "signal_quality", "end"];
/// NPZ keys that spec 6.1 marks "Required: Yes".
pub const NPZ_REQUIRED: &[&str] = &["version", "log_probs", "frame_times", "vocab", "blank_id", "source", "meta_json"];
pub const NPZ_KNOWN: &[&str] =
    &["version", "log_probs", "frame_times", "vocab", "blank_id", "source", "meta_json", "vocab_type", "frame_period", "latency"];
/// Header fields that spec 6.2 rule 1 requires.
pub const JSONL_HEADER_REQUIRED: &[&str] = &["spec_version", "vocab", "vocab_type", "blank_id"];
pub const HEADER_KNOWN: &[&str] = &[
    "type", "spec_version", "vocab", "vocab_type", "blank_id", "source", "meta", "frame_period", "latency", "vocab_id",
    "vocab_version", "clock_domain",
];
/// `blank_id` value meaning "no blank" in NPZ files.
pub const NPZ_NO_BLANK: f64 = -1.0;

/// The 28-token character vocabulary `char.b2q-28` (spec 3.4): blank, a-z, space.
pub const VOCAB: &[&str] = &[
    "<blank>", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v",
    "w", "x", "y", "z", " ",
];
pub const BLANK_ID: usize = 0;

// FEP-0001
pub const TRUST_ACTIONS: &[&str] = &["COMMIT", "OFFER", "ASK", "ABSTAIN", "OFFER_WORDS"];
pub const SEGMENT_UNITS: &[&str] = &["utterance", "word", "trial"];
pub const DECLARATION_KEY: &str = "decode_declaration";

// FEP-0003
pub const INTENT_DECLARATION_KEY: &str = "intent_declaration";
pub const RISK_CLASSES: &[&str] = &["safe", "undoable", "irreversible"];
pub const INTENT_ROLES: &[&str] = &["action", "null", "confirm", "cancel", "undo"];
pub const INTENT_ACTIONS: &[&str] = &["COMMIT", "OFFER", "ABSTAIN"];
pub const FEEDBACK_OUTCOMES: &[&str] = &["confirmed", "cancelled", "selected", "undone", "correct", "wrong"];
