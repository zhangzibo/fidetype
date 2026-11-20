"""The adapter conformance helpers (P14-42) on existing adapters, and on broken sources.

Synthetic data only. The helpers must pass good adapters and catch each
kind of contract break.
"""

from __future__ import annotations

import numpy as np
import pytest

from fidetype.adapters.testing import assert_nts_conforms, assert_source_conforms, check_bad_inputs, check_source
from fidetype.live.sources import ArraySource, Chunk


def test_synthetic_typist_conforms():
    from fidetype.live.sources import SyntheticSource

    res = assert_source_conforms(lambda: SyntheticSource(n_utterances=2, seed=0, speed=0.0))
    assert res.n_samples > 0 and res.markers


def test_brainflow_source_with_fake_board_conforms():
    from fidetype.adapters.brainflow_bridge import FakeBoard
    from fidetype.live.sources import BrainFlowSource

    clock = iter(np.arange(0.0, 100.0, 0.02))
    board = FakeBoard(srate=250.0, n_eeg=4, clock=lambda: float(next(clock)))

    class Stopping(BrainFlowSource):  # a live board never ends: stop after 20 polls
        n = 0

        def poll(self, timeout=0.05):
            self.n += 1
            return None if self.n > 20 else super().poll(0.0)

    res = assert_source_conforms(lambda: Stopping(board=board, descr=board.descr, poll_s=0.0, trial_s=0.0),
                                 rate_tol=0.05)
    assert res.n_samples > 0


def test_ctc_logits_producer_conforms():
    from fidetype.adapters import ctc_logits as C

    vocab = C.vocab_from_list(["_", "a", "b", " "], blank=0)
    dec = C.DecoderInfo(modality="eeg", name="synthetic", version="0", causal=True)
    rng = np.random.default_rng(0)
    assert_nts_conforms(lambda: [C.from_array(rng.standard_normal((20, 4)), vocab, dec, frame_period=0.04)],
                        level="trust-ready", truth=["ab ba"],
                        bad_inputs=[lambda: C.from_array(np.zeros((20, 5)), vocab, dec, frame_period=0.04),
                                    lambda: C.from_array(np.zeros((20, 4)), vocab, dec, frame_period=-1.0)])


class _Broken(ArraySource):
    """An array source with one contract break."""

    def __init__(self, fault):
        super().__init__(np.zeros((100, 2)), 100.0, [(0.5, "keypress")], speed=0.0, name="broken", modality="eeg",
                         meta={"device.modality": "eeg"})
        self.fault = fault
        if fault == "flat-meta":
            self.info["meta"]["subject"] = "S1"
        if fault == "truth-meta":
            self.info["meta"]["my.target_text"] = "hello"
        if fault == "modality":
            self.info["modality"] = "brainwaves"
        if fault == "units":
            self.info["channel_units"] = ["uV"]

    def poll(self, timeout=0.05):
        c = super().poll(timeout)
        if c is None:
            return None if self.fault != "no-end" else Chunk(np.zeros((0, 2), np.float32), np.zeros(0))
        if self.fault == "float64":
            c.samples = c.samples.astype(np.float64)
        if self.fault == "time-reset":
            c.times = c.times - c.times[0]
        if self.fault == "rate":
            c.times = c.times * 2
        return c


@pytest.mark.parametrize("fault,check_id", [
    ("flat-meta", "SRC-META"), ("truth-meta", "SRC-PRIVACY"), ("modality", "SRC-INFO"), ("units", "SRC-UNITS"),
    ("float64", "SRC-CHUNK"), ("time-reset", "SRC-TIME"), ("rate", "SRC-TIME"), ("no-end", "SRC-END")])
def test_helper_catches_each_break(fault, check_id):
    res = check_source(lambda: _Broken(fault), max_polls=200)
    assert check_id in {f.check_id for f in res.findings}, res.findings
    assert check_source(lambda: _Broken("none")).ok


def test_bad_input_must_be_value_error():
    def index_error():
        return [][1]

    def value_error():
        raise ValueError("clear message")

    found = check_bad_inputs([index_error, value_error, lambda: None])
    assert [f.message.split(":")[0] for f in found] == ["bad input 0", "bad input 2"]
