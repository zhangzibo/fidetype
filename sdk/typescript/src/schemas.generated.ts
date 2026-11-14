// GENERATED FILE. Do not edit. Source: spec/schemas/*/*.schema.json.
// Regenerate: npm run gen:schemas (sdk/typescript). Check: npm run check:schemas.
/* eslint-disable */

/** The spec schemas (15), keyed by "<folder>/<name>". */
export const SCHEMAS = {
 "fep-0001/decode-declaration": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0001/decode-declaration.schema.json",
  "title": "FEP-0001 decode_declaration (header or hypothesis field)",
  "description": "Structural schema (FEP-0001 section 4).",
  "type": "object",
  "required": [
   "decoder"
  ],
  "properties": {
   "decoder": {
    "type": "string",
    "minLength": 1
   },
   "decoder_version": {
    "type": "string",
    "minLength": 1
   },
   "frame_temperature": {
    "type": "number",
    "exclusiveMinimum": 0
   },
   "params": {
    "type": "object"
   },
   "config_id": {
    "type": "string",
    "minLength": 1
   }
  }
 },
 "fep-0001/nbest-item": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0001/nbest-item.schema.json",
  "title": "FEP-0001 n-best item of a hypothesis event (with evidence fields)",
  "description": "Structural schema (FEP-0001 section 2). One char_confidences value per Unicode code point of text (rule 1), finite numbers and the 1e-9 tolerance of rule 4 are checked by the fep-0001 conformance profile.",
  "type": "object",
  "required": [
   "text",
   "score"
  ],
  "properties": {
   "text": {
    "type": "string"
   },
   "score": {
    "type": "number"
   },
   "char_confidences": {
    "type": "array",
    "items": {
     "type": "number",
     "minimum": 0,
     "maximum": 1
    }
   },
   "logp_acoustic": {
    "type": "number",
    "maximum": 0
   },
   "logp_lm": {
    "type": "number",
    "maximum": 0
   }
  }
 },
 "fep-0001/segment-end": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0001/segment-end.schema.json",
  "title": "FEP-0001 segment_end event",
  "description": "Structural schema (FEP-0001 section 1). t not before the last frame of the segment (rule 5) is checked by the fep-0001 conformance profile.",
  "type": "object",
  "required": [
   "type"
  ],
  "properties": {
   "type": {
    "const": "segment_end"
   },
   "t": {
    "type": "number"
   },
   "unit": {
    "enum": [
     "utterance",
     "word",
     "trial"
    ]
   }
  }
 },
 "fep-0001/trust-decision": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0001/trust-decision.schema.json",
  "title": "FEP-0001 trust_decision event (text profile, trust layer output)",
  "description": "Structural schema (FEP-0001 section 3 table, rule 8). Order rules (seq increases, one final decision per utterance, none after it) are checked by the fep-0001 conformance profile. Rule 9 (no final COMMIT with an empty text) is a SHOULD; the SDKs report it as a warning. Intent decisions (profile intent) use fep-0003/intent-trust-decision.schema.json.",
  "type": "object",
  "required": [
   "type",
   "is_final",
   "action",
   "p_top1",
   "score_semantics"
  ],
  "properties": {
   "type": {
    "const": "trust_decision"
   },
   "profile": {
    "const": "text"
   },
   "is_final": {
    "type": "boolean"
   },
   "action": {
    "enum": [
     "COMMIT",
     "OFFER",
     "ASK",
     "ABSTAIN",
     "OFFER_WORDS"
    ]
   },
   "shown": {
    "type": "array",
    "items": {
     "type": "string"
    }
   },
   "p_top1": {
    "type": [
     "number",
     "null"
    ],
    "minimum": 0,
    "maximum": 1
   },
   "score_semantics": {
    "enum": [
     "calibrated_prob",
     "uncalibrated_prob",
     "power",
     "strength",
     "none"
    ]
   },
   "set_size": {
    "type": "integer",
    "minimum": 0
   },
   "guard_risk": {
    "type": [
     "number",
     "null"
    ],
    "minimum": 0,
    "maximum": 1
   },
   "session": {
    "type": "string"
   },
   "seq": {
    "type": "integer",
    "minimum": 0
   },
   "utterance": {
    "type": "integer",
    "minimum": 0
   },
   "config_id": {
    "type": [
     "string",
     "null"
    ]
   },
   "input": {
    "type": "object"
   },
   "latency_s": {
    "type": "number",
    "minimum": 0
   },
   "declaration": {
    "type": "object"
   },
   "reason": {
    "type": "string"
   }
  },
  "if": {
   "properties": {
    "action": {
     "const": "COMMIT"
    }
   },
   "required": [
    "action",
    "shown"
   ]
  },
  "then": {
   "properties": {
    "shown": {
     "minItems": 1
    }
   }
  }
 },
 "fep-0003/intent-declaration": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0003/intent-declaration.schema.json",
  "title": "FEP-0003 intent_declaration (header field)",
  "description": "Structural schema. Rules that need the whole object (unique ids, at most one confirm/cancel/undo role, confirm intent irreversible when an irreversible intent exists, at least one non-null intent) are checked by the fep-0003 conformance profile.",
  "type": "object",
  "required": [
   "intents"
  ],
  "properties": {
   "vocab_id": {
    "type": "string",
    "minLength": 1
   },
   "vocab_version": {
    "type": "string",
    "minLength": 1
   },
   "intents": {
    "type": "array",
    "minItems": 1,
    "items": {
     "type": "object",
     "required": [
      "id",
      "risk"
     ],
     "properties": {
      "id": {
       "type": "string",
       "minLength": 1
      },
      "risk": {
       "enum": [
        "safe",
        "undoable",
        "irreversible"
       ]
      },
      "role": {
       "enum": [
        "action",
        "null",
        "confirm",
        "cancel",
        "undo"
       ],
       "default": "action"
      },
      "label": {
       "type": "string"
      }
     }
    }
   }
  }
 },
 "fep-0003/intent-event": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0003/intent-event.schema.json",
  "title": "FEP-0003 intent event (decoder output)",
  "description": "Structural schema. Rules that need the declaration or several fields (declared and unique candidates, probability sum <= 1, ranked best first, no score with semantics none, unique id) are checked by the fep-0003 conformance profile.",
  "type": "object",
  "required": [
   "type",
   "id",
   "t",
   "is_final",
   "score_semantics",
   "candidates"
  ],
  "properties": {
   "type": {
    "const": "intent"
   },
   "id": {
    "type": "string",
    "minLength": 1
   },
   "t": {
    "type": "number"
   },
   "t_start": {
    "type": "number"
   },
   "t_end": {
    "type": "number"
   },
   "is_final": {
    "type": "boolean"
   },
   "revision_of": {
    "type": [
     "string",
     "null"
    ]
   },
   "score_semantics": {
    "enum": [
     "calibrated_prob",
     "uncalibrated_prob",
     "power",
     "strength",
     "none"
    ]
   },
   "candidates": {
    "type": "array",
    "minItems": 1,
    "items": {
     "type": "object",
     "required": [
      "intent"
     ],
     "properties": {
      "intent": {
       "type": "string"
      },
      "score": {
       "type": [
        "number",
        "null"
       ]
      }
     }
    }
   }
  }
 },
 "fep-0003/intent-feedback": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0003/intent-feedback.schema.json",
  "title": "FEP-0003 intent_feedback event (from the user interface or another channel)",
  "type": "object",
  "required": [
   "type",
   "ref_unit",
   "outcome"
  ],
  "properties": {
   "type": {
    "const": "intent_feedback"
   },
   "ref_unit": {
    "type": "integer",
    "minimum": 0
   },
   "outcome": {
    "enum": [
     "confirmed",
     "cancelled",
     "selected",
     "undone",
     "correct",
     "wrong"
    ]
   },
   "intent": {
    "type": [
     "string",
     "null"
    ]
   },
   "t": {
    "type": "number"
   },
   "source": {
    "type": "string"
   }
  },
  "if": {
   "properties": {
    "outcome": {
     "const": "selected"
    }
   }
  },
  "then": {
   "required": [
    "intent"
   ]
  }
 },
 "fep-0003/intent-trust-decision": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/fep-0003/intent-trust-decision.schema.json",
  "title": "FEP-0003 trust_decision with profile intent (trust layer output)",
  "description": "Structural schema. Order and safety rules (seq, one final per unit, confirmation_of, undo_of, threshold, null role) are checked by the fep-0003 conformance profile.",
  "type": "object",
  "required": [
   "type",
   "profile",
   "unit",
   "is_final",
   "action",
   "p_top1",
   "score_semantics"
  ],
  "not": {
   "anyOf": [
    {
     "required": [
      "shown"
     ]
    },
    {
     "required": [
      "utterance"
     ]
    }
   ]
  },
  "properties": {
   "type": {
    "const": "trust_decision"
   },
   "profile": {
    "const": "intent"
   },
   "session": {
    "type": "string"
   },
   "seq": {
    "type": "integer",
    "minimum": 0
   },
   "unit": {
    "type": "integer",
    "minimum": 0
   },
   "is_final": {
    "type": "boolean"
   },
   "action": {
    "enum": [
     "COMMIT",
     "OFFER",
     "ABSTAIN"
    ]
   },
   "reason": {
    "type": "string"
   },
   "p_top1": {
    "type": [
     "number",
     "null"
    ],
    "minimum": 0,
    "maximum": 1
   },
   "score_semantics": {
    "enum": [
     "calibrated_prob",
     "uncalibrated_prob",
     "power",
     "strength",
     "none"
    ]
   },
   "risk_class": {
    "enum": [
     "safe",
     "undoable",
     "irreversible",
     null
    ]
   },
   "threshold": {
    "type": [
     "number",
     "null"
    ],
    "minimum": 0,
    "maximum": 1
   },
   "intent": {
    "type": "string"
   },
   "role": {
    "enum": [
     "action",
     "null",
     "confirm",
     "cancel",
     "undo",
     null
    ]
   },
   "offered": {
    "type": "array",
    "items": {
     "type": "string"
    }
   },
   "confirm_required": {
    "type": "boolean"
   },
   "confirmation_of": {
    "type": "integer",
    "minimum": 0
   },
   "confirmed_via": {
    "enum": [
     "intent",
     "feedback"
    ]
   },
   "undo_of": {
    "type": "integer",
    "minimum": 0
   },
   "pending_cleared": {
    "type": "string"
   },
   "config_id": {
    "type": [
     "string",
     "null"
    ]
   },
   "vocab_id": {
    "type": "string"
   },
   "input": {
    "type": "object"
   },
   "latency_s": {
    "type": "number",
    "minimum": 0
   }
  },
  "allOf": [
   {
    "if": {
     "properties": {
      "action": {
       "const": "COMMIT"
      }
     }
    },
    "then": {
     "required": [
      "intent",
      "risk_class"
     ]
    }
   },
   {
    "if": {
     "properties": {
      "action": {
       "const": "OFFER"
      }
     }
    },
    "then": {
     "required": [
      "offered"
     ]
    }
   }
  ]
 },
 "nts-v0.1/decision": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/decision.schema.json",
  "title": "NeuralTextStream v0.1 decision event (Development, spec 3.5)",
  "description": "Structural schema. The score rules of 3.5 (a probability score in [0, 1], score_range for power and strength, no score for none) are written as conditions; the timing order of 3.8 is checked by the v0.1 conformance suite.",
  "type": "object",
  "required": [
   "type",
   "t",
   "label",
   "score_semantics"
  ],
  "properties": {
   "type": {
    "const": "decision"
   },
   "t": {
    "type": "number"
   },
   "label": {
    "type": "string"
   },
   "score": {
    "type": [
     "number",
     "null"
    ]
   },
   "score_semantics": {
    "enum": [
     "calibrated_prob",
     "uncalibrated_prob",
     "power",
     "strength",
     "none"
    ]
   },
   "score_range": {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "items": {
     "type": "number"
    }
   },
   "t_signal_start": {
    "type": "number"
   },
   "t_signal_end": {
    "type": "number"
   },
   "t_decoded": {
    "type": "number"
   },
   "t_emitted": {
    "type": "number"
   }
  },
  "allOf": [
   {
    "if": {
     "properties": {
      "score_semantics": {
       "enum": [
        "calibrated_prob",
        "uncalibrated_prob"
       ]
      }
     },
     "required": [
      "score_semantics"
     ]
    },
    "then": {
     "properties": {
      "score": {
       "type": [
        "number",
        "null"
       ],
       "minimum": 0,
       "maximum": 1
      }
     }
    }
   },
   {
    "if": {
     "properties": {
      "score_semantics": {
       "enum": [
        "power",
        "strength"
       ]
      }
     },
     "required": [
      "score_semantics"
     ]
    },
    "then": {
     "required": [
      "score_range"
     ]
    }
   },
   {
    "if": {
     "properties": {
      "score_semantics": {
       "const": "none"
      }
     },
     "required": [
      "score_semantics"
     ]
    },
    "then": {
     "properties": {
      "score": {
       "type": "null"
      }
     }
    }
   }
  ]
 },
 "nts-v0.1/end": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/end.schema.json",
  "title": "NeuralTextStream v0.1 end marker (spec 6.2)",
  "type": "object",
  "required": [
   "type"
  ],
  "properties": {
   "type": {
    "const": "end"
   }
  }
 },
 "nts-v0.1/frame": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/frame.schema.json",
  "title": "NeuralTextStream v0.1 frame event (dense or sparse)",
  "description": "Structural schema (spec 3.1, 3.3, 6.2 rules 2-4). null in log_probs means -inf. Normalisation, V = len(vocab), unique top_ids in 0..V-1 and strictly increasing t are checked by the v0.1 conformance suite.",
  "type": "object",
  "required": [
   "type",
   "t"
  ],
  "properties": {
   "type": {
    "const": "frame"
   },
   "t": {
    "type": "number"
   },
   "log_probs": {
    "type": "array",
    "items": {
     "type": [
      "number",
      "null"
     ]
    }
   },
   "top_ids": {
    "type": "array",
    "items": {
     "type": "integer",
     "minimum": 0
    }
   },
   "top_log_probs": {
    "type": "array",
    "items": {
     "type": [
      "number",
      "null"
     ]
    }
   },
   "rest_log_prob": {
    "type": [
     "number",
     "null"
    ]
   }
  },
  "oneOf": [
   {
    "required": [
     "log_probs"
    ]
   },
   {
    "required": [
     "top_ids",
     "top_log_probs"
    ],
    "not": {
     "required": [
      "log_probs"
     ]
    }
   }
  ]
 },
 "nts-v0.1/header": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/header.schema.json",
  "title": "NeuralTextStream v0.1 header event (JSON Lines line 1)",
  "description": "Structural schema (spec 3.1, 3.2, 3.4, 3.8, 6.2 rule 1). Rules that need more than one field (blank_id < len(vocab), unique tokens, meta key types of 4.2, leakage and privacy heuristics) are checked by the v0.1 conformance suite. Unknown keys are allowed (6.2 rule 5).",
  "type": "object",
  "required": [
   "type",
   "spec_version",
   "vocab",
   "vocab_type",
   "blank_id"
  ],
  "properties": {
   "type": {
    "const": "header"
   },
   "spec_version": {
    "const": "0.1"
   },
   "vocab": {
    "type": "array",
    "items": {
     "type": "string"
    }
   },
   "vocab_type": {
    "enum": [
     "char",
     "key",
     "word",
     "phoneme",
     "command",
     "other"
    ]
   },
   "blank_id": {
    "type": [
     "integer",
     "null"
    ],
    "minimum": 0
   },
   "source": {
    "type": "string",
    "minLength": 1
   },
   "meta": {
    "type": "object"
   },
   "frame_period": {
    "type": [
     "number",
     "null"
    ],
    "exclusiveMinimum": 0
   },
   "latency": {
    "type": [
     "number",
     "null"
    ],
    "minimum": 0
   },
   "vocab_id": {
    "type": "string"
   },
   "vocab_version": {
    "type": "string"
   },
   "clock_domain": {
    "enum": [
     "lsl",
     "unix",
     "monotonic",
     "trial",
     "other"
    ]
   }
  }
 },
 "nts-v0.1/hypothesis": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/hypothesis.schema.json",
  "title": "NeuralTextStream v0.1 hypothesis event (Development, spec 3.6)",
  "description": "Structural schema. Unique ids are checked by the v0.1 conformance suite. The FEP-0001 evidence fields of an n-best item are in fep-0001/nbest-item.schema.json.",
  "type": "object",
  "required": [
   "type",
   "id",
   "nbest",
   "score_semantics",
   "is_final"
  ],
  "properties": {
   "type": {
    "const": "hypothesis"
   },
   "id": {
    "type": "string"
   },
   "is_final": {
    "type": "boolean"
   },
   "revision_of": {
    "type": [
     "string",
     "null"
    ]
   },
   "score_semantics": {
    "enum": [
     "calibrated_prob",
     "uncalibrated_prob",
     "power",
     "strength",
     "none"
    ]
   },
   "t_start": {
    "type": "number"
   },
   "t_end": {
    "type": "number"
   },
   "nbest": {
    "type": "array",
    "items": {
     "type": "object",
     "required": [
      "text",
      "score"
     ],
     "properties": {
      "text": {
       "type": "string"
      },
      "score": {
       "type": "number"
      }
     }
    }
   }
  }
 },
 "nts-v0.1/pointer": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/pointer.schema.json",
  "title": "NeuralTextStream v0.1 pointer event (Development, spec 3.7)",
  "description": "Structural schema. len(values) = dims and absolute values in [0, 1] (unless absent) are checked by the v0.1 conformance suite.",
  "type": "object",
  "required": [
   "type",
   "t",
   "dims",
   "mode",
   "values"
  ],
  "properties": {
   "type": {
    "const": "pointer"
   },
   "t": {
    "type": "number"
   },
   "dims": {
    "type": "integer",
    "minimum": 1,
    "maximum": 3
   },
   "mode": {
    "enum": [
     "relative",
     "absolute"
    ]
   },
   "values": {
    "type": "array",
    "minItems": 1,
    "maxItems": 3,
    "items": {
     "type": "number"
    }
   },
   "absent": {
    "type": "array",
    "items": {
     "type": "boolean"
    }
   }
  }
 },
 "nts-v0.1/signal-quality": {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v0.1/signal-quality.schema.json",
  "title": "NeuralTextStream v0.1 signal_quality event (Development, spec 3.9)",
  "type": "object",
  "required": [
   "type",
   "t",
   "value",
   "unit"
  ],
  "properties": {
   "type": {
    "const": "signal_quality"
   },
   "t": {
    "type": "number"
   },
   "value": {
    "type": "number"
   },
   "unit": {
    "enum": [
     "index",
     "snr_db",
     "impedance_ohm",
     "other"
    ]
   }
  },
  "if": {
   "properties": {
    "unit": {
     "const": "index"
    }
   },
   "required": [
    "unit"
   ]
  },
  "then": {
   "properties": {
    "value": {
     "type": "number",
     "minimum": 0,
     "maximum": 1
    }
   }
  }
 }
} as const;

export type SchemaKey = "fep-0001/decode-declaration" | "fep-0001/nbest-item" | "fep-0001/segment-end" | "fep-0001/trust-decision" | "fep-0003/intent-declaration" | "fep-0003/intent-event" | "fep-0003/intent-feedback" | "fep-0003/intent-trust-decision" | "nts-v0.1/decision" | "nts-v0.1/end" | "nts-v0.1/frame" | "nts-v0.1/header" | "nts-v0.1/hypothesis" | "nts-v0.1/pointer" | "nts-v0.1/signal-quality";
