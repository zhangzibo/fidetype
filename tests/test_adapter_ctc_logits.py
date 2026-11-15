"""Tests of the generic CTC-logits adapter (fidetype.adapters.ctc_logits, P4)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import ctc_logits as C
from fidetype.conformance import check_file, check_stream
from fidetype.conformance.io import load_stream, write_jsonl

LETTERS = list("abcdefghijklmnopqrstuvwxyz")
VOC = C.vocab_from_list(["<blank>", " ", *LETTERS], 0)
DEC = C.DecoderInfo(modality="eeg", name="test-ctc", version="1", weights_sha256="ab" * 32)


def _lse(x: np.ndarray) -> np.ndarray:
    m = x.max(axis=-1, keepdims=True)
    return (m + np.log(np.exp(x - m).sum(axis=-1, keepdims=True)))[..., 0]


def _logits(T: int = 30, V: int = len(VOC), seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((T, V)) * 3.0


# --- vocabularies -------------------------------------------------------------------


def test_vocab_from_list_blank_by_token_and_none():
    assert C.vocab_from_list(["a", "<blank>", "b"], "<blank>").blank_id == 1
    assert C.vocab_from_list(["a", "b"], None).blank_id is None
    assert C.vocab_from_list(["a", "b"], "none").blank_id is None
    with pytest.raises(ValueError, match="unique"):
        C.vocab_from_list(["a", "a"], 0)
    with pytest.raises(ValueError, match="out of range"):
        C.vocab_from_list(["a", "b"], 5)
    with pytest.raises(ValueError, match="not in the vocabulary"):
        C.vocab_from_list(["a", "b"], "<pad>")


def test_vocab_from_json_map_hf_conventions():
    v = C.vocab_from_json_map({"<pad>": 0, "<s>": 1, "</s>": 2, "<unk>": 3, "|": 4, "A": 5, "B": 6})
    assert v.blank_id == 0
    assert v.tokens[4] == " "  # word delimiter -> space
    assert v.tokens[5:] == ("A", "B")
    with pytest.raises(ValueError, match="0 .. V-1"):
        C.vocab_from_json_map({"<pad>": 0, "a": 2})
    with pytest.raises(ValueError, match="share id"):
        C.vocab_from_json_map({"<pad>": 0, "a": 0})
    with pytest.raises(ValueError, match="not in the vocabulary map"):
        C.vocab_from_json_map({"x": 0, "a": 1})


def test_vocab_from_tokens_txt_both_forms():
    v = C.vocab_from_tokens_txt("<blk> 0\na 1\nb 2\n")
    assert v.tokens == ("<blk>", "a", "b") and v.blank_id == 0
    v2 = C.vocab_from_tokens_txt("b 2\n<blk> 0\na 1\n")  # id order, not line order
    assert v2.tokens == ("<blk>", "a", "b")
    v3 = C.vocab_from_tokens_txt("<blank>\n \na\n")  # one token per line; blank line = space
    assert v3.tokens == ("<blank>", " ", "a") and v3.blank_id == 0
    with pytest.raises(ValueError, match="no blank"):
        C.vocab_from_tokens_txt("a\nb\n")
    assert C.vocab_from_tokens_txt("a\nb\n", blank="none").blank_id is None


def test_load_vocab_files(tmp_path: Path):
    (tmp_path / "list.json").write_text(json.dumps(["<blank>", "a"]), encoding="utf-8")
    (tmp_path / "vocab.json").write_text(json.dumps({"<pad>": 0, "|": 1, "a": 2}), encoding="utf-8")
    (tmp_path / "tokens.txt").write_text("<blk> 0\na 1\n", encoding="utf-8")
    assert C.load_vocab(tmp_path / "list.json").blank_id == 0
    assert C.load_vocab(tmp_path / "vocab.json").tokens == ("<pad>", " ", "a")
    assert C.load_vocab(tmp_path / "tokens.txt").tokens == ("<blk>", "a")


# --- scores ---------------------------------------------------------------------------


def test_detect_input_kind():
    x = _logits()
    lp = x - _lse(x)[:, None]
    assert C.detect_input_kind(x) == "logits"
    assert C.detect_input_kind(lp) == "log_probs"
    assert C.detect_input_kind(np.exp(lp)) == "probs"
    with pytest.raises(ValueError, match="NaN"):
        C.detect_input_kind(np.array([[np.nan, 0.0]]))


@pytest.mark.parametrize("kind", ["logits", "log_probs", "probs", "auto"])
def test_to_log_probs_kinds_agree(kind):
    x = _logits()
    want = x - _lse(x)[:, None]
    given = {"logits": x, "log_probs": want, "probs": np.exp(want), "auto": x}[kind]
    got = C.to_log_probs(given, kind)
    assert np.allclose(got, want, atol=1e-9)
    assert np.all(np.abs(_lse(got)) < 1e-9)


def test_to_log_probs_zero_prob_is_minus_inf_and_errors():
    p = np.array([[1.0, 0.0], [0.5, 0.5]])
    lp = C.to_log_probs(p, "probs")
    assert lp[0, 1] == -math.inf and lp[0, 0] == 0.0
    with pytest.raises(ValueError, match="sum to 1"):
        C.to_log_probs(np.array([[0.2, 0.2]]), "probs")
    with pytest.raises(ValueError, match="log-sum-exp"):
        C.to_log_probs(np.array([[-0.1, -0.1]]), "log_probs")
    with pytest.raises(ValueError, match="temperature"):
        C.to_log_probs(np.zeros((1, 2)), "logits", temperature=0.0)
    with pytest.raises(ValueError, match="input_kind"):
        C.to_log_probs(np.zeros((1, 2)), "softmax")


def test_temperature_flattens_and_marks_calibration():
    x = _logits()
    s1 = C.from_array(x, VOC, DEC, frame_period=0.04, latency=0.0)
    s2 = C.from_array(x, VOC, DEC, frame_period=0.04, latency=0.0, temperature=2.0)
    assert s2.log_probs.max(axis=1).mean() < s1.log_probs.max(axis=1).mean()
    assert s1.meta["calibration.applied"] is False
    assert s2.meta["calibration.applied"] is True
    assert s2.meta["decoder.calibration_method"] == "temperature"
    assert s2.meta["fidetype.frame_temperature"] == 2.0


class _FakeTensor:
    """Duck-typed stand-in for a torch tensor (torch is not needed)."""

    def __init__(self, a):
        self.a = a

    def detach(self):
        return self

    def cpu(self):
        return self

    def float(self):
        return self

    def numpy(self):
        return self.a


def test_tensor_like_input():
    x = _logits()
    s = C.from_array(_FakeTensor(x), VOC, DEC, frame_period=0.04, latency=0.0)
    assert np.allclose(s.log_probs, (x - _lse(x)[:, None]).astype(np.float32))


# --- streams --------------------------------------------------------------------------


def test_from_array_timing_meta_and_conformance():
    s = C.from_array(_logits(25), VOC, DEC, frame_period=0.08, t0=0.28, latency=0.0, length=20)
    assert s.n_frames == 20
    assert np.allclose(s.frame_times, 0.28 + 0.08 * np.arange(20))
    assert s.meta["adapter.name"] == C.ADAPTER_NAME
    assert s.meta["decoder.lookahead_s"] == 0.0
    assert len(s.meta["stream.id"]) == 32
    rep = check_stream(s, "ctc")
    assert not rep.failures("provenance"), [r.check_id for r in rep.failures("provenance")]


def test_default_t0_is_one_frame_period_and_explicit_times():
    s = C.from_array(_logits(5), VOC, DEC, frame_period=0.04, latency=0.0)
    assert np.allclose(s.frame_times, 0.04 * np.arange(1, 6))
    ft = np.array([0.1, 0.2, 0.35, 0.4, 0.6])
    assert np.allclose(C.from_array(_logits(5), VOC, DEC, frame_period=0.04, frame_times=ft, latency=0.0).frame_times, ft)
    with pytest.raises(ValueError, match="at least 5"):
        C.from_array(_logits(5), VOC, DEC, frame_period=0.04, frame_times=ft[:3])


def test_stream_id_is_deterministic_and_content_based():
    x = _logits()
    a = C.from_array(x, VOC, DEC, frame_period=0.04, latency=0.0).meta["stream.id"]
    b = C.from_array(x, VOC, DEC, frame_period=0.04, latency=0.0).meta["stream.id"]
    c = C.from_array(x + np.eye(x.shape[0], x.shape[1]), VOC, DEC, frame_period=0.04, latency=0.0).meta["stream.id"]
    assert a == b != c
    assert "stream.id" not in C.from_array(x, VOC, DEC, frame_period=0.04, stream_id=None).meta


def test_offline_decoder_omits_latency_met5():
    off = C.DecoderInfo(modality="meg", name="bidir", version="1", causal=False)
    s = C.from_array(_logits(), VOC, off, frame_period=0.04)
    assert s.latency is None and s.meta["decoder.causal"] is False
    assert not check_stream(s).failures("trust-ready")
    with pytest.raises(ValueError, match="MET-5"):
        C.from_array(_logits(), VOC, off, frame_period=0.04, latency=0.5)


def test_from_array_errors():
    with pytest.raises(ValueError, match="2-D"):
        C.from_array(np.zeros((2, 3, len(VOC))), VOC, DEC, frame_period=0.04)
    with pytest.raises(ValueError, match="columns"):
        C.from_array(np.zeros((3, 5)), VOC, DEC, frame_period=0.04)
    with pytest.raises(ValueError, match="frame_period"):
        C.from_array(_logits(), VOC, DEC, frame_period=0.0)
    with pytest.raises(ValueError, match="length"):
        C.from_array(_logits(5), VOC, DEC, frame_period=0.04, length=9)
    with pytest.raises(ValueError, match="modality"):
        C.DecoderInfo(modality="brainwaves", name="x", version="1")


@pytest.mark.parametrize("layout", ["BTV", "TBV"])
def test_from_batch_drops_padding(layout):
    rng = np.random.default_rng(1)
    b = rng.standard_normal((3, 12, len(VOC)))
    b[1, 7:] = 1e6  # padding garbage must not reach a stream
    x = b if layout == "BTV" else np.transpose(b, (1, 0, 2))
    ss = C.from_batch(x, VOC, DEC, lengths=[12, 7, 3], layout=layout, frame_period=0.04, latency=0.0)
    assert [s.n_frames for s in ss] == [12, 7, 3]
    assert np.allclose(ss[1].log_probs, (b[1, :7] - _lse(b[1, :7])[:, None]).astype(np.float32), atol=1e-6)
    assert len({s.meta["stream.id"] for s in ss}) == 3
    with pytest.raises(ValueError, match="lengths"):
        C.from_batch(x, VOC, DEC, lengths=[1, 2], layout=layout, frame_period=0.04)


def test_jsonl_round_trip_through_reference_consumer(tmp_path: Path):
    p = np.exp(C.to_log_probs(_logits(), "logits"))
    p[:, 3] = 0.0
    p /= p.sum(axis=1, keepdims=True)
    s = C.from_array(p, VOC, DEC, frame_period=0.04, latency=0.0, input_kind="probs")
    f = tmp_path / "s.jsonl"
    write_jsonl(s, f)
    assert not check_file(f).failures("provenance")
    back = load_stream(f).stream
    assert back.vocab == list(VOC.tokens) and back.blank_id == 0
    assert np.all(np.isneginf(back.log_probs[:, 3]))
    assert np.allclose(back.log_probs[:, :3], s.log_probs[:, :3], atol=1e-5)


def test_iter_file_npy_and_npz(tmp_path: Path):
    np.save(tmp_path / "one.npy", _logits(10).astype(np.float32))
    np.savez(tmp_path / "many.npz", a=_logits(10, seed=1), b=_logits(6, seed=2))
    one = list(C.iter_file(tmp_path / "one.npy", VOC, DEC, frame_period=0.04, latency=0.0))
    many = list(C.iter_file(tmp_path / "many.npz", VOC, DEC, frame_period=0.04, latency=0.0))
    assert [k for k, _ in one] == [""] and one[0][1].n_frames == 10
    assert [(k, s.n_frames) for k, s in many] == [("a", 10), ("b", 6)]
    assert many[0][1].meta["stream.id"] != many[1][1].meta["stream.id"]
    assert all(k not in s.meta.values() for k, s in many)  # the key does not go into meta
    with pytest.raises(ValueError, match="file type"):
        list(C.iter_file(tmp_path / "x.pt", VOC, DEC, frame_period=0.04))


def test_iter_file_refuses_pickled_arrays(tmp_path: Path):
    np.save(tmp_path / "obj.npy", np.array([{"a": 1}], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError):
        list(C.iter_file(tmp_path / "obj.npy", VOC, DEC, frame_period=0.04))


def test_cli_writes_conformant_streams(tmp_path: Path, capsys):
    np.savez(tmp_path / "lp.npz", t0=_logits(10, seed=3), t1=_logits(8, seed=4))
    (tmp_path / "vocab.json").write_text(json.dumps(list(VOC.tokens)), encoding="utf-8")
    (tmp_path / "w.bin").write_bytes(b"weights")
    rc = C.main([str(tmp_path / "lp.npz"), "--vocab", str(tmp_path / "vocab.json"), "--frame-period", "0.08",
                 "--t0", "0.28", "--latency", "0", "--modality", "intracortical", "--decoder-name", "gru",
                 "--decoder-version", "1", "--weights", str(tmp_path / "w.bin"), "--out", str(tmp_path / "out"),
                 "--level", "provenance"])
    assert rc == 0
    files = sorted((tmp_path / "out").glob("*.jsonl"))
    assert [f.name for f in files] == ["00000-t0.jsonl", "00001-t1.jsonl"]
    head = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert head["meta"]["decoder.weights_sha256"] == C.sha256_file(tmp_path / "w.bin")
    assert "2 reach level provenance" in capsys.readouterr().out


def test_cli_single_file_needs_one_matrix(tmp_path: Path):
    np.savez(tmp_path / "lp.npz", a=_logits(4), b=_logits(4))
    (tmp_path / "v.json").write_text(json.dumps(list(VOC.tokens)), encoding="utf-8")
    with pytest.raises(SystemExit):
        C.main([str(tmp_path / "lp.npz"), "--vocab", str(tmp_path / "v.json"), "--frame-period", "0.04",
                "--modality", "eeg", "--decoder-name", "x", "--decoder-version", "1", "--out", str(tmp_path / "o.jsonl")])


def test_matches_b2t25_adapter_on_synthetic_trial():
    from fidetype.adapters import b2t25 as B
    from fidetype.conformance.producers import _synthetic_trials

    tr = _synthetic_trials(1, 7)[0]
    voc = C.vocab_from_list(B.VOCAB, 0, vocab_type="phoneme", vocab_id=B.VOCAB_ID)
    dec = C.DecoderInfo(modality="intracortical", name="card2024-online-rnn", version="t15")
    s = C.from_array(tr.logits, voc, dec, frame_period=B.FRAME_PERIOD_S, t0=B.PATCH_SIZE * B.BIN_S, latency=0.0)
    ref = B.trial_stream(tr)
    assert np.allclose(s.log_probs, ref.log_probs, atol=1e-6)
    assert np.allclose(s.frame_times, ref.frame_times)


def test_producer_target_registered():
    from fidetype.conformance.producers import TARGETS

    ps = TARGETS["ctc-logits"]()
    assert len(ps) == 5
    for p in ps:
        assert not check_stream(p.stream, p.name, p.truth).failures("provenance"), p.name
