"""Metrics and evaluation."""

from importlib import import_module
from typing import Any

from fidetype.eval.metrics import (
    cer,
    ctc_greedy_decode,
    ctc_greedy_ids,
    edit_distance,
    expected_calibration_error,
    wer,
)

# ewpm and harness import fidetype.trust, and fidetype.trust imports
# fidetype.eval.metrics. Load them lazily (PEP 562) to avoid an import cycle.
_LAZY = {
    "SentenceRecord": "fidetype.eval.ewpm",
    "effective_wpm": "fidetype.eval.ewpm",
    "wolpaw_itr_bits": "fidetype.eval.ewpm",
    "HarnessConfig": "fidetype.eval.harness",
    "TrustPipeline": "fidetype.eval.harness",
    "run_harness": "fidetype.eval.harness",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        return getattr(import_module(_LAZY[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "cer",
    "ctc_greedy_decode",
    "ctc_greedy_ids",
    "edit_distance",
    "expected_calibration_error",
    "wer",
    *_LAZY,
]
