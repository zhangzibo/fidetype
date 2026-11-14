// GENERATED FILE. Do not edit. Source: spec/schemas/*/*.schema.json.
// Regenerate: npm run gen:schemas (sdk/typescript). Check: npm run check:schemas.
/* eslint-disable */

// Each type comes from one schema. Conditional rules (if/then, not) and the
// semantic rules of the conformance profiles are not part of the types.

/** FEP-0001 decode_declaration (header or hypothesis field)
 *
 * Structural schema (FEP-0001 section 4).
 *
 * Source: spec/schemas/fep-0001/decode-declaration.schema.json */
export interface Fep0001DecodeDeclaration {
  decoder: string;
  decoder_version?: string;
  frame_temperature?: number;
  params?: Record<string, unknown>;
  config_id?: string;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0001 n-best item of a hypothesis event (with evidence fields)
 *
 * Structural schema (FEP-0001 section 2). One char_confidences value per Unicode code point of text (rule 1), finite numbers and the 1e-9 tolerance of rule 4 are checked by the fep-0001 conformance profile.
 *
 * Source: spec/schemas/fep-0001/nbest-item.schema.json */
export interface Fep0001NbestItem {
  text: string;
  score: number;
  char_confidences?: number[];
  logp_acoustic?: number;
  logp_lm?: number;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0001 segment_end event
 *
 * Structural schema (FEP-0001 section 1). t not before the last frame of the segment (rule 5) is checked by the fep-0001 conformance profile.
 *
 * Source: spec/schemas/fep-0001/segment-end.schema.json */
export interface Fep0001SegmentEnd {
  type: "segment_end";
  t?: number;
  unit?: "utterance" | "word" | "trial";
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0001 trust_decision event (text profile, trust layer output)
 *
 * Structural schema (FEP-0001 section 3 table, rule 8). Order rules (seq increases, one final decision per utterance, none after it) are checked by the fep-0001 conformance profile. Rule 9 (no final COMMIT with an empty text) is a SHOULD; the SDKs report it as a warning. Intent decisions (profile intent) use fep-0003/intent-trust-decision.schema.json.
 *
 * Source: spec/schemas/fep-0001/trust-decision.schema.json */
export interface Fep0001TrustDecision {
  type: "trust_decision";
  profile?: "text";
  is_final: boolean;
  action: "COMMIT" | "OFFER" | "ASK" | "ABSTAIN" | "OFFER_WORDS";
  shown?: string[];
  p_top1: number | null;
  score_semantics: "calibrated_prob" | "uncalibrated_prob" | "power" | "strength" | "none";
  set_size?: number;
  guard_risk?: number | null;
  session?: string;
  seq?: number;
  utterance?: number;
  config_id?: string | null;
  input?: Record<string, unknown>;
  latency_s?: number;
  declaration?: Record<string, unknown>;
  reason?: string;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0003 intent_declaration (header field)
 *
 * Structural schema. Rules that need the whole object (unique ids, at most one confirm/cancel/undo role, confirm intent irreversible when an irreversible intent exists, at least one non-null intent) are checked by the fep-0003 conformance profile.
 *
 * Source: spec/schemas/fep-0003/intent-declaration.schema.json */
export interface Fep0003IntentDeclaration {
  vocab_id?: string;
  vocab_version?: string;
  intents: {
    id: string;
    risk: "safe" | "undoable" | "irreversible";
    role?: "action" | "null" | "confirm" | "cancel" | "undo";
    label?: string;
    /** Unknown keys are allowed (a consumer ignores them). */
    [key: string]: unknown;
  }[];
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0003 intent event (decoder output)
 *
 * Structural schema. Rules that need the declaration or several fields (declared and unique candidates, probability sum <= 1, ranked best first, no score with semantics none, unique id) are checked by the fep-0003 conformance profile.
 *
 * Source: spec/schemas/fep-0003/intent-event.schema.json */
export interface Fep0003IntentEvent {
  type: "intent";
  id: string;
  t: number;
  t_start?: number;
  t_end?: number;
  is_final: boolean;
  revision_of?: string | null;
  score_semantics: "calibrated_prob" | "uncalibrated_prob" | "power" | "strength" | "none";
  candidates: {
    intent: string;
    score?: number | null;
    /** Unknown keys are allowed (a consumer ignores them). */
    [key: string]: unknown;
  }[];
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0003 intent_feedback event (from the user interface or another channel)
 *
 * Source: spec/schemas/fep-0003/intent-feedback.schema.json */
export interface Fep0003IntentFeedback {
  type: "intent_feedback";
  ref_unit: number;
  outcome: "confirmed" | "cancelled" | "selected" | "undone" | "correct" | "wrong";
  intent?: string | null;
  t?: number;
  source?: string;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0003 trust_decision with profile intent (trust layer output)
 *
 * Structural schema. Order and safety rules (seq, one final per unit, confirmation_of, undo_of, threshold, null role) are checked by the fep-0003 conformance profile.
 *
 * Source: spec/schemas/fep-0003/intent-trust-decision.schema.json */
export interface Fep0003IntentTrustDecision {
  type: "trust_decision";
  profile: "intent";
  session?: string;
  seq?: number;
  unit: number;
  is_final: boolean;
  action: "COMMIT" | "OFFER" | "ABSTAIN";
  reason?: string;
  p_top1: number | null;
  score_semantics: "calibrated_prob" | "uncalibrated_prob" | "power" | "strength" | "none";
  risk_class?: "safe" | "undoable" | "irreversible" | null;
  threshold?: number | null;
  intent?: string;
  role?: "action" | "null" | "confirm" | "cancel" | "undo" | null;
  offered?: string[];
  confirm_required?: boolean;
  confirmation_of?: number;
  confirmed_via?: "intent" | "feedback";
  undo_of?: number;
  pending_cleared?: string;
  config_id?: string | null;
  vocab_id?: string;
  input?: Record<string, unknown>;
  latency_s?: number;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0005 control declaration (header key control_declaration)
 *
 * Structural schema. Rules that need several fields (units fit the quantity, axes length = dims, normalised position only in the screen frame, click_intent declared in the FEP-0003 intent_declaration and not null) are checked by the fep-0005 conformance profile.
 *
 * Source: spec/schemas/fep-0005/control-declaration.schema.json */
export interface Fep0005ControlDeclaration {
  dims: number;
  quantity: "velocity" | "position";
  units: "norm/s" | "px/s" | "mm/s" | "m/s" | "deg/s" | "norm" | "px" | "mm" | "m" | "deg";
  frame: "screen" | "workspace";
  rate_hz: number;
  axes?: string[];
  uncertainty?: "none" | "std";
  max_speed?: number;
  latency_s?: number;
  window_s?: number;
  click_intent?: string;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0005 control_enable event (engage or safe-stop from a channel other than the decoder)
 *
 * enabled = true engages decoder control (starts the hand-off ramp); enabled = false is a latched stop.
 *
 * Source: spec/schemas/fep-0005/control-enable.schema.json */
export interface Fep0005ControlEnable {
  type: "control_enable";
  enabled: boolean;
  t?: number;
  source?: "switch" | "caregiver" | "ui" | "voice" | "eye-tracker" | "watchdog" | "other";
  reason?: string;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0005 control event (decoder or human-channel output)
 *
 * Structural schema. Rules that need the declaration or the stream (values and std have dims entries, std present exactly when the declaration says uncertainty = std, tick and t strictly increase, timing fields in order, absent values ignored) are checked by the fep-0005 conformance profile.
 *
 * Source: spec/schemas/fep-0005/control-event.schema.json */
export interface Fep0005ControlEvent {
  type: "control";
  id?: string;
  t: number;
  tick: number;
  values: (number | null)[];
  absent?: boolean[];
  std?: number[];
  source?: "decoder" | "human";
  t_signal_start?: number;
  t_signal_end?: number;
  t_decoded?: number;
  t_emitted?: number;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** FEP-0005 control trust_decision (one actuation command per decoder tick)
 *
 * Structural schema. Semantic rules (state fits action, zero velocity on hold/stop, speed <= v_max, no motion with a no-signal reason, re-engage after stop, a moving tick never reused, seq across profiles, no intent COMMIT while stopped) are checked by the fep-0005 conformance profile.
 *
 * Source: spec/schemas/fep-0005/control-trust-decision.schema.json */
export interface Fep0005ControlTrustDecision {
  type: "trust_decision";
  profile: "control";
  session?: string;
  seq?: number;
  tick: number;
  t?: number;
  is_final: true;
  action: "COMMIT" | "ABSTAIN";
  state: "act" | "attenuate" | "hold" | "stop";
  velocity: number[];
  raw?: number[];
  gain: number;
  units: string;
  radius?: number;
  level?: number;
  authority?: number;
  engagement: number;
  v_max: number;
  ttl_s: number;
  reason?: string;
  reasons?: string[];
  p_top1: null;
  score_semantics: "calibrated_prob" | "uncalibrated_prob" | "power" | "strength" | "none";
  config_id?: string;
  input?: Record<string, unknown>;
  latency_s?: number;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 decision event (Development, spec 3.5)
 *
 * Structural schema. The score rules of 3.5 (a probability score in [0, 1], score_range for power and strength, no score for none) are written as conditions; the timing order of 3.8 is checked by the v0.1 conformance suite.
 *
 * Source: spec/schemas/nts-v0.1/decision.schema.json */
export interface NtsDecision {
  type: "decision";
  t: number;
  label: string;
  score?: number | null;
  score_semantics: "calibrated_prob" | "uncalibrated_prob" | "power" | "strength" | "none";
  score_range?: number[];
  t_signal_start?: number;
  t_signal_end?: number;
  t_decoded?: number;
  t_emitted?: number;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 end marker (spec 6.2)
 *
 * Source: spec/schemas/nts-v0.1/end.schema.json */
export interface NtsEnd {
  type: "end";
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 frame event (dense or sparse)
 *
 * Structural schema (spec 3.1, 3.3, 6.2 rules 2-4). null in log_probs means -inf. Normalisation, V = len(vocab), unique top_ids in 0..V-1 and strictly increasing t are checked by the v0.1 conformance suite.
 *
 * Source: spec/schemas/nts-v0.1/frame.schema.json */
export interface NtsFrame {
  type: "frame";
  t: number;
  log_probs?: (number | null)[];
  top_ids?: number[];
  top_log_probs?: (number | null)[];
  rest_log_prob?: number | null;
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 header event (JSON Lines line 1)
 *
 * Structural schema (spec 3.1, 3.2, 3.4, 3.8, 6.2 rule 1). Rules that need more than one field (blank_id < len(vocab), unique tokens, meta key types of 4.2, leakage and privacy heuristics) are checked by the v0.1 conformance suite. Unknown keys are allowed (6.2 rule 5).
 *
 * Source: spec/schemas/nts-v0.1/header.schema.json */
export interface NtsHeader {
  type: "header";
  spec_version: "0.1";
  vocab: string[];
  vocab_type: "char" | "key" | "word" | "phoneme" | "command" | "other";
  blank_id: number | null;
  source?: string;
  meta?: Record<string, unknown>;
  frame_period?: number | null;
  latency?: number | null;
  vocab_id?: string;
  vocab_version?: string;
  clock_domain?: "lsl" | "unix" | "monotonic" | "trial" | "other";
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 hypothesis event (Development, spec 3.6)
 *
 * Structural schema. Unique ids are checked by the v0.1 conformance suite. The FEP-0001 evidence fields of an n-best item are in fep-0001/nbest-item.schema.json.
 *
 * Source: spec/schemas/nts-v0.1/hypothesis.schema.json */
export interface NtsHypothesis {
  type: "hypothesis";
  id: string;
  is_final: boolean;
  revision_of?: string | null;
  score_semantics: "calibrated_prob" | "uncalibrated_prob" | "power" | "strength" | "none";
  t_start?: number;
  t_end?: number;
  nbest: {
    text: string;
    score: number;
    /** Unknown keys are allowed (a consumer ignores them). */
    [key: string]: unknown;
  }[];
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 pointer event (Development, spec 3.7)
 *
 * Structural schema. len(values) = dims and absolute values in [0, 1] (unless absent) are checked by the v0.1 conformance suite.
 *
 * Source: spec/schemas/nts-v0.1/pointer.schema.json */
export interface NtsPointer {
  type: "pointer";
  t: number;
  dims: number;
  mode: "relative" | "absolute";
  values: number[];
  absent?: boolean[];
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** NeuralTextStream v0.1 signal_quality event (Development, spec 3.9)
 *
 * Source: spec/schemas/nts-v0.1/signal-quality.schema.json */
export interface NtsSignalQuality {
  type: "signal_quality";
  t: number;
  value: number;
  unit: "index" | "snr_db" | "impedance_ohm" | "other";
  /** Unknown keys are allowed (a consumer ignores them). */
  [key: string]: unknown;
}

/** Type name of each schema key. */
export interface SchemaTypes {
  "fep-0001/decode-declaration": Fep0001DecodeDeclaration;
  "fep-0001/nbest-item": Fep0001NbestItem;
  "fep-0001/segment-end": Fep0001SegmentEnd;
  "fep-0001/trust-decision": Fep0001TrustDecision;
  "fep-0003/intent-declaration": Fep0003IntentDeclaration;
  "fep-0003/intent-event": Fep0003IntentEvent;
  "fep-0003/intent-feedback": Fep0003IntentFeedback;
  "fep-0003/intent-trust-decision": Fep0003IntentTrustDecision;
  "fep-0005/control-declaration": Fep0005ControlDeclaration;
  "fep-0005/control-enable": Fep0005ControlEnable;
  "fep-0005/control-event": Fep0005ControlEvent;
  "fep-0005/control-trust-decision": Fep0005ControlTrustDecision;
  "nts-v0.1/decision": NtsDecision;
  "nts-v0.1/end": NtsEnd;
  "nts-v0.1/frame": NtsFrame;
  "nts-v0.1/header": NtsHeader;
  "nts-v0.1/hypothesis": NtsHypothesis;
  "nts-v0.1/pointer": NtsPointer;
  "nts-v0.1/signal-quality": NtsSignalQuality;
}
