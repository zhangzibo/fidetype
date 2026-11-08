"""Tests of the noisy-decoder simulator.

The CER and ECE tests use 200 sentences (about 7 000 peaks). This is
enough to measure a mean CER to about +-0.01 and keeps the run short.
"""

import numpy as np
import pytest

from fidetype.eval.metrics import cer, ctc_greedy_decode, expected_calibration_error
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import PRESET_CER, NoisyDecoderSimulator, SimConfig
from fidetype.streams.vocab import LETTERS, VOCAB, key_distance

SENTENCES = sentences(200)


def _run(cfg, seed=1, sents=SENTENCES):
    sim = NoisyDecoderSimulator(cfg, seed=seed)
    return [sim.simulate(s) for s in sents]


def test_corpus_size():
    assert len(set(SENTENCES)) == 200


def test_determinism():
    cfg = SimConfig.preset("median")
    a = NoisyDecoderSimulator(cfg, seed=7).simulate("hello world")
    b = NoisyDecoderSimulator(cfg, seed=7).simulate("hello world")
    np.testing.assert_array_equal(a.stream.log_probs, b.stream.log_probs)
    np.testing.assert_array_equal(a.peak_correct, b.peak_correct)
    assert a.sampled_text == b.sampled_text
    c = NoisyDecoderSimulator(cfg, seed=8).simulate("hello world")
    assert not np.array_equal(a.stream.log_probs, c.stream.log_probs)


def test_explicit_seed_ignores_call_order():
    sim = NoisyDecoderSimulator(SimConfig.preset("worst"), seed=0)
    first = sim.simulate("abc def", seed=3)
    sim.simulate("something else")
    again = sim.simulate("abc def", seed=3)
    np.testing.assert_array_equal(first.stream.log_probs, again.stream.log_probs)


def test_stream_format():
    r = NoisyDecoderSimulator(SimConfig.preset("median"), seed=0).simulate("Hello, World!")
    s = r.stream
    assert r.text == "hello world"
    assert s.source == "simulator" and s.vocab == list(VOCAB) and s.blank_id == 0
    np.testing.assert_allclose(np.diff(s.frame_times), 0.04)  # 25 frames/s
    assert len(r.char_outcomes) == len(r.text)
    n = len(r.peak_labels)
    for arr in (r.peak_frames, r.peak_targets, r.peak_correct, r.peak_confidence, r.peak_true_prob):
        assert len(arr) == n
    assert s.meta["config"]["target_cer"] == 0.28


def test_typing_speed():
    # 152 characters/min gives about 395 ms per character (Brain2Qwerty v1).
    r = NoisyDecoderSimulator(SimConfig.preset("perfect"), seed=0).simulate(" ".join(SENTENCES[:20]))
    gap_s = np.mean(np.diff(r.peak_frames)) * 0.04
    assert 0.36 < gap_s < 0.43


def test_repeated_letters_stay_separate():
    r = NoisyDecoderSimulator(SimConfig.preset("perfect"), seed=0).simulate("aaa bookkeeper")
    assert ctc_greedy_decode(r.stream) == "aaa bookkeeper"


def test_perfect_preset_gives_zero_cer():
    for res in _run(SimConfig.preset("perfect"), sents=SENTENCES[:50]):
        assert cer(res.text, ctc_greedy_decode(res.stream)) == 0.0
        assert res.peak_correct.all()


def test_greedy_decode_equals_sampled_text():
    for res in _run(SimConfig.preset("worst"), sents=SENTENCES[:50]):
        assert ctc_greedy_decode(res.stream) == res.sampled_text


@pytest.mark.parametrize("preset", ["best", "median", "worst"])
def test_preset_cer_hits_target(preset):
    results = _run(SimConfig.preset(preset))
    mean_cer = np.mean([cer(r.text, ctc_greedy_decode(r.stream)) for r in results])
    assert abs(mean_cer - PRESET_CER[preset]) <= 0.05, mean_cer


def test_rare_letters_decode_worse():
    sim = NoisyDecoderSimulator(SimConfig.preset("median"))
    assert sim.p_correct("z") < sim.p_correct("k") < sim.p_correct("e")
    assert sim.p_correct("w") < sim.p_correct("t")
    # Space is the most robust token.
    assert sim.p_correct(" ") > max(sim.p_correct(c) for c in LETTERS)


def test_substitutions_go_to_near_keys():
    results = _run(SimConfig.preset("worst"))
    sub_d, rand_d = [], []
    for r in results:
        for t, l in zip(r.peak_targets, r.peak_labels):
            if t > 0 and t != l:
                tc = VOCAB[t]
                sub_d.append(key_distance(tc, VOCAB[l]))
                # Mean distance to a random other letter.
                rand_d.append(np.mean([key_distance(tc, c) for c in LETTERS if c != tc]))
    assert len(sub_d) > 500
    assert np.mean(sub_d) < 0.7 * np.mean(rand_d)


def _ece(temperature):
    results = _run(SimConfig.preset("median", confidence_temperature=temperature))
    conf = np.concatenate([r.peak_confidence for r in results])
    corr = np.concatenate([r.peak_correct for r in results])
    return expected_calibration_error(conf, corr), conf.mean(), corr.mean()


def test_calibration_knob():
    # Thresholds: with about 7 000 peaks in 15 bins, the sampling noise of
    # ECE for a calibrated source is about 0.01. Thus 0.03 is a safe upper
    # limit at temperature 1. Temperature 0.5 squares the odds; at a true
    # accuracy of about 0.72 the mean confidence goes above 0.9, so ECE
    # must be well above 0.1.
    ece1, conf1, acc1 = _ece(1.0)
    ece_over, conf_over, acc_over = _ece(0.5)
    ece_under, conf_under, _ = _ece(2.0)
    assert ece1 < 0.03
    assert abs(conf1 - acc1) < 0.02
    assert ece_over > 0.10 and ece_over > 4 * ece1
    assert conf_over > acc_over + 0.10  # over-confident
    assert ece_under > 0.10 and conf_under < acc1 - 0.10  # under-confident
    # The temperature does not change the labels.
    assert acc_over == acc1


def test_config_validation():
    with pytest.raises(ValueError):
        SimConfig.preset("nope")
    with pytest.raises(ValueError):
        SimConfig(confidence_temperature=0)
    with pytest.raises(ValueError):
        SimConfig(target_cer=0.01, insertion_rate=0.01, deletion_rate=0.01)
