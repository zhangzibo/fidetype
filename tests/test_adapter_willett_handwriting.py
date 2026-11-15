"""Tests for the Willett 2021 handwriting adapter (synthetic fixtures only)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from fidetype.adapters import willett_handwriting as W
from fidetype.conformance import check_stream
from fidetype.conformance.producers import synthetic_willett_session
from fidetype.eval.metrics import ctc_greedy_decode


@pytest.fixture
def sess():
    return synthetic_willett_session(seed=4, n_trials=3)


def test_vocab_maps_dataset_symbols():
    assert len(W.VOCAB) == 31 and W.VOCAB[26] == " " and W.VOCAB[29] == "."
    assert W.CTC_VOCAB[0] == "<blank>" and len(W.CTC_VOCAB) == 32
    assert W.ascii_to_text("hi>there~") == "hi there."


def test_session_closed_loop_trials(sess):
    assert sess.n_trials == 3 and sess.has_rnn
    assert sess.closed_loop_trials() == [1, 2]
    assert sess.intended_text[0] == "hello world"


def test_trial_stream_frames_times_and_text(sess):
    s = W.trial_stream(sess, 1, session_index=0)
    assert s.vocab_type == "char" and s.blank_id is None and s.latency == 0.0
    assert s.n_frames == len("the cat sat~")
    assert W.greedy_text(s) == "the cat sat." == sess.decoded_text[1]
    np.testing.assert_allclose(np.logaddexp.reduce(s.log_probs, axis=1), 0, atol=1e-5)
    # frame k is at (decoded bin - (go - 1)) * 10 ms: first char 20 bins after go, then every 50 bins
    np.testing.assert_allclose(s.frame_times[:3], np.array([21, 71, 121]) * W.BIN_S)
    assert np.all(np.diff(s.frame_times) > 0)


def test_meta_has_no_text_and_no_participant_id(sess):
    s = W.trial_stream(sess, 2, session_index=3)
    blob = json.dumps(s.meta)
    for t in ("how are you", "hello", "t5", "T5"):
        assert t not in blob
    assert "subject.id" not in s.meta and "session.id" not in s.meta
    assert s.meta["fidetype.replay"] == {"dataset": W.DATASET_SLUG, "doi": W.DRYAD_DOI, "licence": W.LICENCE,
                                         "session_index": 3, "trial_index": 2, "condition": "CL Pandarinath",
                                         "excluded": False}
    assert s.meta["decoder.causal"] is True and s.meta["decoder.lookahead_s"] == 0.0
    assert s.meta["device.modality"] == "intracortical" and s.meta["device.channel_count"] == 192
    assert len(s.meta["stream.id"]) == 32
    assert W.trial_stream(sess, 2, 3).meta["stream.id"] == s.meta["stream.id"]


def test_open_loop_trial_has_no_stream(sess):
    with pytest.raises(ValueError, match="open-loop"):
        W.trial_stream(sess, 0)


def test_conformance_trust_ready_and_no_leak(sess):
    for i in sess.closed_loop_trials():
        s = W.trial_stream(sess, i, 0)
        for st in (s, W.to_ctc_stream(s)):
            rep = check_stream(st, "willett", [sess.intended_text[i], sess.decoded_text[i]])
            assert rep.passes("trust-ready"), [f.to_dict() for f in rep.failures()]
            assert [f.check_id for f in rep.failures()] == ["PV-WEIGHTS"]


def test_ctc_form_roundtrip_and_greedy(sess):
    s = W.trial_stream(sess, 1, 0)
    c = W.to_ctc_stream(s)
    assert c.n_frames == 2 * s.n_frames - 1 and c.blank_id == 0
    assert ctc_greedy_decode(c) == W.greedy_text(s)
    back = W.from_ctc_stream(c)
    np.testing.assert_allclose(back.log_probs, s.log_probs, atol=1e-4)
    np.testing.assert_allclose(back.frame_times, s.frame_times)
    assert back.meta["fidetype.vocab_id"] == W.VOCAB_ID and "fidetype.ctc_form" not in back.meta


def test_double_letters_survive_ctc(sess):
    s = W.trial_stream(sess, 1, 0)
    rows = np.exp(s.log_probs.astype(np.float64))
    rows2 = np.vstack([rows[:1], rows[:1]])  # the same character twice
    two = W.char_stream(rows2, [0.1, 0.6], s.meta)
    c = W.to_ctc_stream(two)
    assert ctc_greedy_decode(c) == "tt"


def test_session_from_dict_rejects_bad_input(sess):
    base = {
        "sentenceCondition": ["CL Corpus"], "excludedSentences": [0], "goCueOnsetTimeBin": [10],
        "sentenceEndTimeBin": [50], "sentenceBlockNums": [1], "intendedText": ["a"],
        "rnn_charProbTimeSeries": np.full((100, 31), 1 / 31, np.float32), "rnn_decodedCharTimes": [[20, 1]],
        "rnn_decodedText": ["a"], "rnn_charMapASCII": W.CHAR_MAP_ASCII,
    }
    assert W.session_from_dict(base).n_trials == 1
    for key, val, msg in (
        ("rnn_charMapASCII", "x" * 31, "rnn_charMapASCII"),
        ("rnn_charProbTimeSeries", np.zeros((100, 30)), "must be"),
        ("rnn_decodedCharTimes", [[20, 32]], "char index"),
        ("rnn_decodedCharTimes", [[100, 1]], "time bin"),
        ("sentenceEndTimeBin", [5], "ends before"),
        ("excludedSentences", [0, 1], "excluded"),
    ):
        bad = dict(base, **{key: val})
        with pytest.raises(ValueError, match=msg):
            W.session_from_dict(bad)


def test_session_without_rnn():
    d = {
        "sentenceCondition": ["OL Copy"], "excludedSentences": [0], "goCueOnsetTimeBin": [10],
        "sentenceEndTimeBin": [50], "sentenceBlockNums": [1], "intendedText": ["a"],
        "rnn_charProbTimeSeries": np.zeros((0, 0)), "rnn_decodedText": np.zeros((0, 0)),
    }
    s = W.session_from_dict(d)
    assert not s.has_rnn and s.closed_loop_trials() == []


def test_load_sentences_mat_roundtrip(tmp_path, sess):
    sio = pytest.importorskip("scipy.io")
    cell = lambda xs: np.array([[np.array(x)] for x in xs], dtype=object)  # noqa: E731
    p = tmp_path / "sentences.mat"
    sio.savemat(p, {
        "sentenceCondition": cell(sess.conditions),
        "excludedSentences": sess.excluded.astype(np.int32)[:, None],
        "goCueOnsetTimeBin": sess.go_bin.astype(np.int32)[:, None],
        "sentenceEndTimeBin": sess.end_bin.astype(np.int32)[:, None],
        "sentenceBlockNums": sess.block.astype(np.int32)[:, None],
        "intendedText": cell([t.replace(" ", ">") for t in sess.intended_text]),
        "rnn_charProbTimeSeries": sess.char_probs,
        "rnn_newCharTimeSeries": sess.new_char[:, None],
        "rnn_decodedCharTimes": np.stack([sess.decoded_times, sess.decoded_ids], 1).astype(np.int32),
        "rnn_decodedText": cell([t.replace(" ", ">").replace(".", "~") for t in sess.decoded_text]),
        "rnn_charMapASCII": W.CHAR_MAP_ASCII,
        "neuralActivityCube": np.zeros((3, 4, 2), np.uint8),  # present in the real file, never read
    })
    got = W.load_sentences(p)
    assert got.conditions == sess.conditions and got.intended_text == sess.intended_text
    np.testing.assert_array_equal(got.decoded_times, sess.decoded_times)
    pairs = list(W.iter_streams([p]))
    assert len(pairs) == 2
    assert W.greedy_text(pairs[0][0]) == pairs[0][1][1]
    with pytest.raises(ValueError, match="too large"):
        W.load_sentences(p, max_bytes=10)
    (tmp_path / "x.p").write_bytes(b"not read")
    with pytest.raises(ValueError, match="not a .mat"):
        W.load_sentences(tmp_path / "x.p")


def test_list_session_files(tmp_path):
    for name in ("t5.b", "t5.a"):
        (tmp_path / "Datasets" / name).mkdir(parents=True)
        (tmp_path / "Datasets" / name / "sentences.mat").write_bytes(b"")
    (tmp_path / "Datasets" / "t5.c").mkdir()
    assert [p.parent.name for p in W.list_session_files(tmp_path)] == ["t5.a", "t5.b"]
