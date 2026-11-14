"""blank_id null (no blank class, spec 3.1) on the greedy decoder (M7-11)."""

from __future__ import annotations

import numpy as np

from fidetype.eval.metrics import ctc_greedy_ids
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust._ctc import find_segments
from fidetype.trust.testing import greedy_nbest


def _stream(rows: list[list[float]], blank_id: int | None) -> NeuralTextStream:
    lp = np.log(np.asarray(rows, dtype=np.float64)).astype(np.float32)
    return NeuralTextStream(log_probs=lp, frame_times=np.arange(len(rows)) * 0.25, vocab=["a", "b", "c"],
                            blank_id=blank_id, source="test", vocab_type="command")


ROWS = [[0.7, 0.2, 0.1], [0.6, 0.3, 0.1], [0.1, 0.8, 0.1], [0.2, 0.2, 0.6], [0.1, 0.1, 0.8]]


def test_no_blank_every_frame_is_a_token_frame() -> None:
    s = _stream(ROWS, None)
    assert find_segments(s) == [(0, 2, 0), (2, 3, 2), (3, 5, 4)]
    assert greedy_nbest(s).candidates[0].text == "abc"
    # Same rule as the metric decoder: collapse runs, remove nothing.
    assert [s.vocab[i] for i in ctc_greedy_ids(s)] == ["a", "b", "c"]


def test_blank_id_still_removes_blank_runs() -> None:
    s = _stream(ROWS, 0)
    assert find_segments(s) == [(2, 3, 2), (3, 5, 4)]
    assert greedy_nbest(s).candidates[0].text == "bc"
