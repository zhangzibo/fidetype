"""Tests of fidetype.trust.calibration."""

import math

import numpy as np
import pytest

from fidetype.eval.metrics import expected_calibration_error
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.calibration import (
    NBestCalibrator,
    TemperatureScaler,
    fit_frame_temperature,
    golden_section_min,
    greedy_peaks,
    reliability_diagram,
    session_recalibration,
    softmax,
)
from fidetype.trust.testing import synthetic_nbest
from fidetype.trust.types import Candidate, NBest


def test_golden_section_finds_minimum():
    x = golden_section_min(lambda v: (v - 1.3) ** 2, -5, 5)
    assert abs(x - 1.3) < 1e-4


def test_multiclass_fit_recovers_known_temperature():
    rng = np.random.default_rng(0)
    z = rng.normal(0, 2, size=(4000, 6))
    y = np.array([rng.choice(6, p=softmax(r)) for r in z])
    # The model reports z / 0.5: over-confident by a factor of 2.
    sc = TemperatureScaler().fit(z / 0.5, y)
    assert abs(sc.temperature - 2.0) < 0.2
    assert sc.nll_after < sc.nll_before


def test_binary_fit_recovers_known_temperature():
    rng = np.random.default_rng(1)
    logit = rng.normal(0, 1.5, 5000)
    y = rng.random(5000) < 1 / (1 + np.exp(-logit))
    reported = 1 / (1 + np.exp(-logit * 3.0))  # over-confident
    sc = TemperatureScaler().fit_binary(reported, y)
    assert abs(sc.temperature - 3.0) < 0.4
    cal = sc.transform_confidences(reported)
    assert expected_calibration_error(cal, y) < expected_calibration_error(reported, y)


def test_temperature_scaling_fixes_simulator_overconfidence():
    """confidence_temperature = 0.5: ECE must drop by more than 50 %."""
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=3)
    sents = sentences(160, seed=2)
    res = [sim.simulate(s, seed=i) for i, s in enumerate(sents)]
    fit_r, test_r = res[:80], res[80:]
    sc = fit_frame_temperature([r.stream for r in fit_r], [r.text for r in fit_r])
    # The simulator divides log-probs by 0.5, so the inverse is T = 2.
    assert 1.6 < sc.temperature < 2.4
    conf_b, conf_a, ok = [], [], []
    for r in test_r:
        pk = greedy_peaks(r.stream, r.text)
        lp = sc.transform_logits(r.stream.log_probs[pk["centres"]])
        conf_b.append(pk["confidence"])
        conf_a.append(np.exp(lp[np.arange(len(pk["labels"])), pk["labels"]]))
        ok.append(pk["correct"])
    conf_b, conf_a, ok = map(np.concatenate, (conf_b, conf_a, ok))
    before = expected_calibration_error(conf_b, ok)
    after = expected_calibration_error(conf_a, ok)
    assert after < 0.5 * before, (before, after)


def test_transform_stream_keeps_argmax_and_validates():
    sim = NoisyDecoderSimulator(SimConfig.preset("worst"), seed=0)
    st = sim.simulate("hello there", seed=1).stream
    sc = TemperatureScaler(temperature=2.0)
    st2 = sc.transform_stream(st)
    np.testing.assert_array_equal(st.log_probs.argmax(1), st2.log_probs.argmax(1))
    assert st2.meta["calibration_temperature"] == 2.0


def test_transform_stream_keeps_all_metadata():
    """M2-15: vocab_type, frame_period, latency (and all other fields) survive."""
    import dataclasses

    from fidetype.streams.spec import NeuralTextStream

    rng = np.random.default_rng(0)
    vocab = ["_", "a", "b", " "]
    logits = rng.normal(size=(12, len(vocab)))
    lp = logits - np.log(np.exp(logits).sum(1, keepdims=True))
    st = NeuralTextStream(
        log_probs=lp, frame_times=np.arange(12) * 0.04, vocab=vocab, blank_id=0,
        source="unit-test", meta={"subject": "S1"}, vocab_type="char",
        frame_period=0.04, latency=0.25,
    )
    st2 = TemperatureScaler(temperature=1.7).transform_stream(st)
    for f in dataclasses.fields(NeuralTextStream):
        if f.name in ("log_probs", "meta"):
            continue
        a, b = getattr(st, f.name), getattr(st2, f.name)
        if isinstance(a, np.ndarray):
            np.testing.assert_array_equal(a, b)
        else:
            assert a == b, f.name
    assert st2.frame_period == 0.04 and st2.latency == 0.25 and st2.vocab_type == "char"
    assert st2.meta == {"subject": "S1", "calibration_temperature": 1.7, "calibration.applied": True,
                        "decoder.calibration_method": "temperature", "decoder.calibration_id": "temperature:1.7"}
    assert st.meta == {"subject": "S1"}  # the input is not changed
    assert not np.allclose(st.log_probs, st2.log_probs)


def _sharpen(nb, factor):
    """Multiply all scores: an over-confident decoder."""
    return NBest([Candidate(c.text, c.score * factor, c.logp_acoustic, c.logp_lm, c.char_confidences)
                  for c in nb.candidates])


def test_fit_top1_and_nbest_calibrator():
    rng = np.random.default_rng(4)
    truths = sentences(400, seed=5)
    nbs = [_sharpen(synthetic_nbest(t, rng, truth_in_list=bool(rng.random() < 0.8)), 4.0) for t in truths]
    fit_nb, fit_t, test_nb, test_t = nbs[:200], truths[:200], nbs[200:], truths[200:]
    cal = NBestCalibrator.fit(fit_nb, fit_t)
    assert cal.sentence.temperature > 1.5
    p_raw = [NBestCalibrator.identity().posteriors(nb)[0] for nb in test_nb]
    p_cal = [cal.posteriors(nb)[0] for nb in test_nb]
    ok = [nb.index_of(t) == 0 for nb, t in zip(test_nb, test_t)]
    assert expected_calibration_error(p_cal, ok) < expected_calibration_error(p_raw, ok)
    nb2 = cal.calibrate_chars(test_nb[0])
    assert len(nb2.candidates[0].char_confidences) == len(nb2.texts[0])


def test_session_recalibration_splits():
    rng = np.random.default_rng(6)
    truths = sentences(30, seed=7)
    nbs = [synthetic_nbest(t, rng) for t in truths]
    cal, posts = session_recalibration(nbs, truths, k=10)
    assert len(posts) == 20
    assert all(abs(p.sum() - 1) < 1e-9 for p in posts)
    with pytest.raises(ValueError):
        session_recalibration(nbs, truths, k=0)


def test_reliability_diagram():
    conf = np.array([0.05, 0.15, 0.95, 0.95, 0.9])
    ok = np.array([0, 0, 1, 1, 0])
    rd = reliability_diagram(conf, ok, n_bins=10)
    assert rd["count"].sum() == 5
    assert math.isclose(rd["ece"], expected_calibration_error(conf, ok, 10))
    assert rd["accuracy"][9] == 1.0
