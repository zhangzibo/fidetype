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


# --- spec v0.1 document fields (vocab_type, spec_version, optional fields) --


def test_new_fields_have_backward_compatible_defaults():
    s = _stream()
    assert s.vocab_type == "char"
    assert s.spec_version == "0.1" == s.version
    assert s.frame_period is None and s.latency is None


def test_non_ctc_word_vocab():
    lp = np.log(np.full((3, 4), 0.25))
    s = NeuralTextStream(
        lp, np.arange(3) * 0.5, ["yes", "no", "help", "stop"], blank_id=None,
        source="test", vocab_type="command", frame_period=0.5, latency=0.1,
    )
    assert s.blank_id is None and s.vocab_type == "command"


@pytest.mark.parametrize(
    "kw, msg",
    [
        (dict(vocab_type="emoji"), "vocab_type"),
        (dict(frame_period=0.0), "frame_period"),
        (dict(latency=-0.1), "latency"),
        (dict(latency=float("nan")), "latency"),
    ],
)
def test_invalid_new_fields(kw, msg):
    with pytest.raises(ValueError, match=msg):
        _stream(**kw)


def test_npz_round_trip_new_fields(tmp_path):
    s = _stream(vocab_type="key", blank_id=None, frame_period=0.04, latency=0.2)
    path = tmp_path / "stream.npz"
    s.to_npz(path)
    r = NeuralTextStream.from_npz(path)
    assert r.vocab_type == "key"
    assert r.blank_id is None
    assert r.frame_period == 0.04 and r.latency == 0.2


def test_npz_layout_without_optional_keys(tmp_path):
    path = tmp_path / "stream.npz"
    _stream().to_npz(path)
    with np.load(path, allow_pickle=False) as z:
        assert sorted(z.files) == sorted(
            ["version", "log_probs", "frame_times", "vocab", "vocab_type", "blank_id", "source", "meta_json"]
        )


def test_from_npz_reads_old_files(tmp_path):
    """A file from before vocab_type existed loads with the defaults."""
    s = _stream()
    path = tmp_path / "old.npz"
    np.savez_compressed(
        path,
        version=np.array("0.1"),
        log_probs=s.log_probs,
        frame_times=s.frame_times,
        vocab=np.array(s.vocab, dtype=np.str_),
        blank_id=np.array(0, dtype=np.int64),
        source=np.array("old"),
        meta_json=np.array("{}"),
    )
    r = NeuralTextStream.from_npz(path)
    assert r.vocab_type == "char" and r.blank_id == 0 and r.spec_version == "0.1"
    assert r.frame_period is None and r.latency is None
