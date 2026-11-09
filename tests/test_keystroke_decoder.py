"""Tests for the synchronous keystroke decoder (synthetic data only)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from fidetype.decoders.keystroke import (
    KEY_CLASSES,
    N_CLASSES,
    LogRegDecoder,
    fit_logreg_cv,
    greedy_keys,
    key_class,
    keystroke_stream,
    stream_meta,
    trials_from_segments,
    window_features,
)
from fidetype.eval.metrics import ctc_greedy_decode
from fidetype.lm import ctc_prefix_beam_search
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID, VOCAB


def _onehot_logp(text: str, p: float = 0.9) -> np.ndarray:
    lp = np.full((len(text), N_CLASSES), math.log((1 - p) / (N_CLASSES - 1)))
    for i, ch in enumerate(text):
        lp[i, KEY_CLASSES.index(ch)] = math.log(p)
    return lp


def _separable(n_per: int, n_feat: int, sep: float, seed: int, noise_seed: int = 0):
    centres = np.random.default_rng(seed).standard_normal((N_CLASSES, n_feat)) * sep
    y = np.repeat(np.arange(N_CLASSES), n_per)
    X = centres[y] + np.random.default_rng([seed, noise_seed]).standard_normal((len(y), n_feat))
    groups = np.arange(len(y)) // 9  # "trials" of 9 keys
    return X.astype(np.float32), y, groups


# --- stream construction ---------------------------------------------------


def test_key_class():
    assert key_class("a") == 0 and key_class("z") == 25 and key_class(" ") == 26
    for k in ("<ret>", "<bs>", "<?>", "A", "", "ab"):
        assert key_class(k) is None


def test_stream_is_valid_with_blanks_between_keys(tmp_path):
    text = "el cc"
    times = np.array([0.1, 0.3, 0.45, 0.6, 0.6])  # one tie: must still increase strictly
    s = keystroke_stream(_onehot_logp(text), times, stream_meta("S1", "ses1"))
    assert isinstance(s, NeuralTextStream)
    assert s.vocab == list(VOCAB) and s.blank_id == BLANK_ID and s.vocab_type == "char"
    assert s.n_frames == 2 * len(text) - 1
    assert np.all(np.diff(s.frame_times) > 0)
    np.testing.assert_allclose(s.frame_times[0::2][:4], times[:4])
    # Odd frames are blank frames; even frames are key frames.
    assert np.all(s.log_probs[1::2].argmax(1) == BLANK_ID)
    assert np.all(s.log_probs[0::2].argmax(1) != BLANK_ID)
    np.testing.assert_allclose(np.exp(s.log_probs[0::2, BLANK_ID]), 1e-3, rtol=1e-3)
    # The blank frames keep the double "c": greedy CTC gives back the text.
    assert ctc_greedy_decode(s) == text
    assert greedy_keys(s) == text
    # Round trip through NPZ.
    p = tmp_path / "s.npz"
    s.to_npz(p)
    s2 = NeuralTextStream.from_npz(p)
    np.testing.assert_array_equal(s2.log_probs, s.log_probs)
    assert s2.meta == s.meta


def test_stream_meta_has_no_text():
    target = "el procesador ejecuta"
    meta = stream_meta("S1", "ses2", {"fidetype.trial_id": "S1-ses2-block1-t004"})
    s = keystroke_stream(_onehot_logp(target), np.arange(len(target)) * 0.2, meta)
    blob = json.dumps(s.meta)
    for word in ("procesador", "ejecuta", target):
        assert word not in blob
    for v in s.meta.values():  # no value is the text or a word of it
        assert not (isinstance(v, str) and v in target.split() + [target])
    assert not any("text" in k or "label" in k for k in s.meta)
    assert s.meta["device.modality"] == "meg"
    assert s.meta["decoder.name"] == "fidetype-keystroke-sync"
    assert s.meta["decoder.causal"] is False
    assert s.meta["decoder.timing"] == "oracle-keystroke"
    assert s.meta["calibration.applied"] is False
    assert s.meta["subject.id"] == "S1" and s.meta["session.id"] == "S1-ses2"


def test_empty_and_single_key_streams():
    s0 = keystroke_stream(np.zeros((0, N_CLASSES)), np.zeros(0))
    assert s0.n_frames == 0
    s1 = keystroke_stream(_onehot_logp("a"), np.array([0.5]))
    assert s1.n_frames == 1 and ctc_greedy_decode(s1) == "a"


def test_stream_works_with_beam():
    text = "la casa"
    s = keystroke_stream(_onehot_logp(text, 0.95), np.arange(len(text)) * 0.25)
    hyps = ctc_prefix_beam_search(s, None)
    assert hyps[0].text == text


# --- features ----------------------------------------------------------------


def test_window_features_shape_and_bins():
    C, T, sf = 3, 400, 100.0
    data = np.tile(np.arange(T, dtype=np.float32), (C, 1))
    F = window_features(data, [100, 200], sf, (-0.2, 0.3), 10)
    assert F.shape == (2, C * 10)
    # Channel 0, bin 0 of key at 100: mean of samples 80..84 = 82.
    assert F[0, 0] == pytest.approx(82.0)
    # Edge keys are padded, not dropped.
    assert window_features(data, [0, T - 1], sf).shape == (2, C * 10)


def test_trials_from_segments_drops_non_char_keys():
    data = np.random.default_rng(0).standard_normal((4, 1000)).astype(np.float32)
    side = {
        "subject": "S9",
        "session": "ses1",
        "block": "block1",
        "segments": [
            {
                "trial_idx": 2, "is_training": False, "start_sample": 100, "end_sample": 600,
                "target_text": "la", "typed_text": "la", "split": "val",
                "key_samples": [30, 60, 90, 120], "key_chars": ["l", "<bs>", "a", "<ret>"],
            }
        ],
    }
    (t,) = trials_from_segments(data, 100.0, side)
    assert t.typed_keys == "la" and t.n_keys == 2
    np.testing.assert_allclose(t.key_times, [0.3, 0.9])
    assert t.features.shape == (2, 40)
    assert t.trial_id == "S9-ses1-block1-t002"


# --- training ---------------------------------------------------------------


def test_logreg_learns_separable_data():
    X, y, g = _separable(30, 40, 1.5, seed=1)
    Xt, yt, _ = _separable(10, 40, 1.5, seed=1, noise_seed=1)  # same centres, new noise
    dec, info = fit_logreg_cv(X, y, g, lams=(0.01, 0.1, 1.0))
    acc = (dec.predict(Xt) == yt).mean()
    assert acc > 0.9, acc
    lp = dec.predict_log_proba(Xt)
    np.testing.assert_allclose(np.exp(lp).sum(1), 1.0, atol=1e-6)
    assert info["lam"] in (0.01, 0.1, 1.0)


def test_label_permutation_control_gives_chance():
    X, y, g = _separable(30, 40, 1.5, seed=2)
    Xt, yt, _ = _separable(20, 40, 1.5, seed=2, noise_seed=1)
    yp = np.random.default_rng(0).permutation(y)
    dec = LogRegDecoder(lam=1.0).fit(X, yp)
    acc = (dec.predict(Xt) == yt).mean()
    assert acc < 0.12, acc  # chance is 1/27 = 0.037


def test_shared_mlp_runs():
    pytest.importorskip("torch")
    from fidetype.decoders.keystroke import SharedMLPDecoder

    X, y, g = _separable(20, 30, 2.0, seed=3)
    data = {"A": (X[::2], y[::2], g[::2]), "B": (X[1::2], y[1::2], g[1::2])}
    m = SharedMLPDecoder(30, ["A", "B"], hidden=64, epochs=30, seed=0).fit(data)
    lp = m.predict_log_proba("A", X[:50])
    assert lp.shape == (50, N_CLASSES)
    assert (lp.argmax(1) == y[:50]).mean() > 0.5
