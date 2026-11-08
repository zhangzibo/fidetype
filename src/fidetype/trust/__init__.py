"""The trust core: calibration, conformal sets, hallucination guard and
decision policy. It reads only :mod:`fidetype.trust.types`."""

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
    Action,
    AlwaysCommitPolicy,
    Decision,
    DecisionPolicy,
    PolicyConfig,
    PolicyInputs,
    fit_thresholds,
)
from fidetype.trust.types import Candidate, NBest, from_lm_hypotheses

__all__ = [
    "Action",
    "AdaptiveConformal",
    "AlwaysCommitPolicy",
    "Candidate",
    "Decision",
    "DecisionPolicy",
    "GuardConfig",
    "GuardScore",
    "HallucinationGuard",
    "NBest",
    "NBestCalibrator",
    "PolicyConfig",
    "PolicyInputs",
    "PredictionSet",
    "SplitConformal",
    "TemperatureScaler",
    "WordConformal",
    "auroc",
    "ece",
    "fit_frame_temperature",
    "fit_thresholds",
    "from_lm_hypotheses",
    "greedy_peaks",
    "nbest_consistency",
    "null_input_audit",
    "reliability_diagram",
    "scores_to_posteriors",
    "semantic_entropy",
    "session_recalibration",
]
