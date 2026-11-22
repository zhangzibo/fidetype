"""The trust core: calibration, conformal sets, hallucination guard and
decision policy, risk control and the provenance ledger. It reads only :mod:`fidetype.trust.types`.

Drop-in wrapper for any decoder (P14-03, :mod:`fidetype.trust.dropin`)::

    guard = fidetype.trust.calibrate(cal_logits, cal_texts, vocab=VOCAB, lexicon=WORDS, alpha=0.05)
    result = guard.decide(new_logits)        # result.action: "commit" | "offer" | "withhold"
"""

from fidetype.trust.calibration import (
    NBestCalibrator,
    TemperatureScaler,
    ece,
    fit_frame_temperature,
    greedy_peaks,
    reliability_diagram,
    scores_to_posteriors,
    session_recalibration,
)
from fidetype.trust.conformal import AdaptiveConformal, PredictionSet, SplitConformal, WordConformal
from fidetype.trust.guard import (
    GuardConfig,
    GuardScore,
    HallucinationGuard,
    auroc,
    nbest_consistency,
    null_input_audit,
    semantic_entropy,
)
from fidetype.trust.policy import (
    OFFER_WORDS_GRID,
    Action,
    AlwaysCommitPolicy,
    Decision,
    DecisionPolicy,
    PolicyConfig,
    PolicyInputs,
    WordChoice,
    WordSlotInfo,
    fit_thresholds,
    highlight_slots,
)
from fidetype.trust.online_risk import (
    OnlineCommitRiskControl,
    OnlineTrustPolicy,
    Ticket,
    weighted_crc_threshold,
)
from fidetype.trust.bandit_risk import BanditCommitRiskControl, BanditTicket, BanditTrustPolicy
from fidetype.trust.risk_control import (
    CommitRiskControl,
    RiskControlResult,
    commit_calibration_data,
    crc_threshold,
    ltt_threshold,
)
from fidetype.trust.session_risk import (
    SessionRiskMonitor,
    block_ltt,
    block_test,
    eb_session_threshold,
    min_ltt_items,
    mondrian_ltt,
)
from fidetype.trust.adaptive import FeedbackOutcome, FeedbackUser, GuardedDecision, GuardedUpdateLoop
from fidetype.trust.update_hooks import GuardUpdateOutcome, OnlinePolicyUpdater, TrustGuardUpdater, swap_guard
from fidetype.trust.content import CommitGate, GatedPolicy, gate_decision
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config
from fidetype.trust.streaming import (
    StreamDecision,
    StreamEventError,
    StreamingConfig,
    StreamingTrustLayer,
    iter_events,
    nbest_from_hypothesis,
    replay,
)
from fidetype.trust.types import Candidate, NBest, from_lm_hypotheses

__all__ = [
    "BanditCommitRiskControl",
    "BanditTicket",
    "BanditTrustPolicy",
    "FeedbackOutcome",
    "FeedbackUser",
    "GuardedDecision",
    "GuardedUpdateLoop",
    "GuardUpdateOutcome",
    "OnlinePolicyUpdater",
    "TrustGuardUpdater",
    "swap_guard",
    "OFFER_WORDS_GRID",
    "CommitGate",
    "GatedPolicy",
    "gate_decision",
    "PAPER1_V4_RECIPE",
    "FrozenTrustConfig",
    "StreamDecision",
    "StreamEventError",
    "StreamingConfig",
    "StreamingTrustLayer",
    "iter_events",
    "nbest_from_hypothesis",
    "paper1_v4_harness_config",
    "replay",
    "Action",
    "AdaptiveConformal",
    "AlwaysCommitPolicy",
    "CommitRiskControl",
    "Candidate",
    "Decision",
    "DecisionPolicy",
    "GuardConfig",
    "GuardScore",
    "HallucinationGuard",
    "LedgerView",
    "LedgeredPolicy",
    "NBest",
    "NBestCalibrator",
    "OnlineCommitRiskControl",
    "OnlineTrustPolicy",
    "PolicyConfig",
    "PolicyInputs",
    "PredictionSet",
    "ProvenanceLedger",
    "RiskControlResult",
    "SessionRiskMonitor",
    "SplitConformal",
    "TemperatureScaler",
    "Ticket",
    "WordChoice",
    "WordConformal",
    "WordSlotInfo",
    "audit_report",
    "auroc",
    "block_ltt",
    "block_test",
    "eb_session_threshold",
    "min_ltt_items",
    "mondrian_ltt",
    "commit_calibration_data",
    "crc_threshold",
    "ece",
    "fit_frame_temperature",
    "fit_thresholds",
    "from_lm_hypotheses",
    "greedy_peaks",
    "highlight_slots",
    "ltt_threshold",
    "nbest_consistency",
    "null_input_audit",
    "reliability_diagram",
    "scores_to_posteriors",
    "semantic_entropy",
    "session_recalibration",
    "weighted_crc_threshold",
]

#: Provenance names, imported on first use (so that
#: ``python -m fidetype.trust.provenance`` runs without a double import).
_PROVENANCE = {
    "LedgerView": "LedgerView",
    "LedgeredPolicy": "LedgeredPolicy",
    "ProvenanceLedger": "ProvenanceLedger",
    "audit_report": "audit_report",
    "verify_ledger": "verify",
}


#: Drop-in wrapper names (P14-03), imported on first use: ``fidetype.trust.calibrate(...)``.
_DROPIN = (
    "calibrate",
    "wrap",
    "load",
    "TrustGuard",
    "TrustResult",
    "GuaranteeSheet",
    "ControlResult",
    "NullControlError",
    "offer_control",
    "recheck_offer_control",
)
__all__ += list(_DROPIN)

#: P5-02 names (per-policy guarantee sheets, online drop-in guard), imported on first use.
_P5_02 = {
    "PolicySheet": "fidetype.trust.guarantee_sheet",
    "policy_sheets": "fidetype.trust.guarantee_sheet",
    "save_sheets": "fidetype.trust.guarantee_sheet",
    "load_sheets": "fidetype.trust.guarantee_sheet",
    "OnlineGuard": "fidetype.trust.online_guard",
    "OfferGate": "fidetype.trust.offer_gate",
    "check_frame_times": "fidetype.trust.integrity",
    "IntegrityReport": "fidetype.trust.integrity",
    "FrozenPrefixScore": "fidetype.trust.external_score",
    "PrefixContext": "fidetype.trust.external_score",
}
__all__ += list(_P5_02)


def __getattr__(name: str):
    if name in _PROVENANCE:
        from fidetype.trust import provenance

        return getattr(provenance, _PROVENANCE[name])
    if name in _DROPIN:
        from fidetype.trust import dropin

        return getattr(dropin, name)
    if name in _P5_02:
        import importlib

        return getattr(importlib.import_module(_P5_02[name]), name)
    raise AttributeError(f"module 'fidetype.trust' has no attribute {name!r}")
