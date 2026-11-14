/** Constants of NeuralTextStream v0.1 and the FEPs (copied from the spec and the Python reference). */

export const SPEC_VERSION = "0.1";
/** Tolerance of the row normalisation rule (spec 5.2.1). */
export const NORM_TOL = 1e-3;
export const VOCAB_TYPES = ["char", "key", "word", "phoneme", "command", "other"] as const;
export const SCORE_SEMANTICS = ["calibrated_prob", "uncalibrated_prob", "power", "strength", "none"] as const;
export const CLOCK_DOMAINS = ["lsl", "unix", "monotonic", "trial", "other"] as const;
export const SQ_UNITS = ["index", "snr_db", "impedance_ohm", "other"] as const;
export const MODALITIES = ["emg", "eeg", "meg", "opm-meg", "ecog", "intracortical", "fnirs", "other"] as const;
/** JSON Lines event kinds of spec 3.0, plus `end`. */
export const EVENT_TYPES = ["frame", "decision", "hypothesis", "pointer", "signal_quality", "end"] as const;
/** NPZ keys that spec 6.1 marks "Required: Yes". */
export const NPZ_REQUIRED = ["version", "log_probs", "frame_times", "vocab", "blank_id", "source", "meta_json"] as const;
export const NPZ_KNOWN = [...NPZ_REQUIRED, "vocab_type", "frame_period", "latency"] as const;
/** Header fields that spec 6.2 rule 1 requires. */
export const JSONL_HEADER_REQUIRED = ["spec_version", "vocab", "vocab_type", "blank_id"] as const;
export const HEADER_KNOWN = [
  "type", "spec_version", "vocab", "vocab_type", "blank_id", "source", "meta",
  "frame_period", "latency", "vocab_id", "vocab_version", "clock_domain",
] as const;
/** `blank_id` value meaning "no blank" in NPZ files. */
export const NPZ_NO_BLANK = -1;

/** The 28-token character vocabulary `char.b2q-28` (spec 3.4): blank, a-z, space. */
export const VOCAB: readonly string[] = ["<blank>", ..."abcdefghijklmnopqrstuvwxyz", " "];
export const BLANK_ID = 0;

/** FEP-0001 */
export const TRUST_ACTIONS = ["COMMIT", "OFFER", "ASK", "ABSTAIN", "OFFER_WORDS"] as const;
export const SEGMENT_UNITS = ["utterance", "word", "trial"] as const;
export const DECLARATION_KEY = "decode_declaration";

/** FEP-0003 */
export const INTENT_DECLARATION_KEY = "intent_declaration";
export const RISK_CLASSES = ["safe", "undoable", "irreversible"] as const;
export const INTENT_ROLES = ["action", "null", "confirm", "cancel", "undo"] as const;
export const INTENT_ACTIONS = ["COMMIT", "OFFER", "ABSTAIN"] as const;
export const FEEDBACK_OUTCOMES = ["confirmed", "cancelled", "selected", "undone", "correct", "wrong"] as const;

export type VocabType = (typeof VOCAB_TYPES)[number];
export type ScoreSemantics = (typeof SCORE_SEMANTICS)[number];
export type TrustAction = (typeof TRUST_ACTIONS)[number];
