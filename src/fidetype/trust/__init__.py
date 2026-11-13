"""The trust core: calibration, conformal sets, hallucination guard and
decision policy, risk control and the provenance ledger. It reads only :mod:`fidetype.trust.types`."""

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
from fidetype.trust.risk_control import (
    CommitRiskControl,
    RiskControlResult,
    commit_calibration_data,
    crc_threshold,
    ltt_threshold,
)
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
    "OFFER_WORDS_GRID",
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
    "SplitConformal",
    "TemperatureScaler",
    "Ticket",
    "WordChoice",
    "WordConformal",
    "WordSlotInfo",
    "audit_report",
    "auroc",
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


def __getattr__(name: str):
    if name in _PROVENANCE:
        from fidetype.trust import provenance

        return getattr(provenance, _PROVENANCE[name])
    raise AttributeError(f"module 'fidetype.trust' has no attribute {name!r}")
