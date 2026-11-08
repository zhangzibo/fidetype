import numpy as np
import pytest

from fidetype.eval.metrics import (
    cer,
    ctc_greedy_decode,
    edit_distance,
    expected_calibration_error,
    wer,
)
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import VOCAB


def test_edit_distance():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("", "abc") == 3
    assert edit_distance("abc", "") == 3
    assert edit_distance("abc", "abc") == 0
    assert edit_distance("flaw", "lawn") == 2


def test_cer_wer():
    assert cer("abcd", "abcd") == 0.0
    assert cer("abcd", "abxd") == 0.25
    assert cer("ab", "abcd") == 1.0
    assert cer("", "") == 0.0 and cer("", "a") == 1.0
    assert wer("the cat sat", "the cat sat") == 0.0
    assert wer("the cat sat", "the bat sat") == pytest.approx(1 / 3)
    assert wer("the cat sat", "the cat") == pytest.approx(1 / 3)


def _onehot_stream(ids):
    lp = np.full((len(ids), len(VOCAB)), np.log(1e-4 / 27))
    lp[np.arange(len(ids)), ids] = np.log(1 - 1e-4)
    return NeuralTextStream(lp, np.arange(len(ids)) * 0.04, list(VOCAB), source="test")


def test_ctc_greedy_decode():
    h, e, l, o, sp, b = 8, 5, 12, 15, 27, 0
    s = _onehot_stream([b, h, h, e, b, l, l, b, l, o, sp, sp, b])
    assert ctc_greedy_decode(s) == "hello "


def test_ctc_greedy_empty():
    s = NeuralTextStream(np.zeros((0, 28)), np.zeros(0), list(VOCAB), source="test")
    assert ctc_greedy_decode(s) == ""


def test_ece_perfect_and_worst():
    assert expected_calibration_error([1.0, 1.0], [True, True]) == 0.0
    assert expected_calibration_error([1.0, 1.0], [False, False]) == 1.0
    # Confidence 0.75 with accuracy 0.75 is calibrated.
    assert expected_calibration_error([0.75] * 4, [1, 1, 1, 0]) == pytest.approx(0.0)


def test_ece_two_bins():
    conf = [0.9, 0.9, 0.2, 0.2]
    corr = [1, 0, 0, 0]
    # Bin of 0.9: |0.5 - 0.9| = 0.4. Bin of 0.2: |0 - 0.2| = 0.2. Mean 0.3.
    assert expected_calibration_error(conf, corr, n_bins=10) == pytest.approx(0.3)


def test_ece_rejects_bad_input():
    with pytest.raises(ValueError):
        expected_calibration_error([1.2], [1])
    with pytest.raises(ValueError):
        expected_calibration_error([0.5, 0.5], [1])
    with pytest.raises(ValueError):
        expected_calibration_error([], [])
