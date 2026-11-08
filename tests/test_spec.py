import numpy as np
import pytest

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import VOCAB


def _stream(T=5, V=len(VOCAB), **kw):
    rng = np.random.default_rng(0)
    x = rng.standard_normal((T, V))
    lp = x - np.log(np.exp(x).sum(axis=1, keepdims=True))
    args = dict(log_probs=lp, frame_times=np.arange(T) * 0.04, vocab=list(VOCAB), blank_id=0, source="test")
    args.update(kw)
    return NeuralTextStream(**args)


def test_valid_stream():
    s = _stream()
    assert s.log_probs.dtype == np.float32
    assert s.frame_times.dtype == np.float64
    assert s.n_frames == 5 and s.vocab_size == 28
    assert s.version == "0.1"
    np.testing.assert_allclose(s.probs.sum(axis=1), 1.0, atol=1e-5)


def test_empty_stream_is_valid():
    s = NeuralTextStream(np.zeros((0, 28)), np.zeros(0), list(VOCAB), source="test")
    assert s.n_frames == 0


@pytest.mark.parametrize(
    "kw, msg",
    [
        (dict(log_probs=np.zeros((5, 28))), "log-sum-exp"),
        (dict(log_probs=np.zeros(28)), "2-D"),
        (dict(vocab=list(VOCAB)[:-1]), "columns"),
        (dict(frame_times=np.zeros(5)), "increase"),
        (dict(frame_times=np.arange(4) * 0.04), "shape"),
        (dict(blank_id=28), "blank_id"),
        (dict(source=""), "source"),
        (dict(meta=[1]), "meta"),
        (dict(version="9.9"), "version"),
    ],
)
def test_invalid_stream(kw, msg):
    with pytest.raises(ValueError, match=msg):
        _stream(**kw)


def test_nan_rejected():
    s = _stream()
    lp = s.log_probs.copy()
    lp[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        _stream(log_probs=lp)


def test_minus_inf_allowed():
    lp = np.full((2, 28), -np.inf)
    lp[:, 0] = 0.0
    s = _stream(T=2, log_probs=lp)
    assert np.isneginf(s.log_probs[0, 1])


def test_npz_round_trip(tmp_path):
    s = _stream(meta={"subject": "s01", "settings": {"a": 1}})
    path = tmp_path / "stream.npz"
    s.to_npz(path)
    r = NeuralTextStream.from_npz(path)
    np.testing.assert_array_equal(r.log_probs, s.log_probs)
    np.testing.assert_array_equal(r.frame_times, s.frame_times)
    assert r.vocab == s.vocab
    assert r.blank_id == s.blank_id
    assert r.source == "test"
    assert r.meta == {"subject": "s01", "settings": {"a": 1}}
    assert r.version == "0.1"
