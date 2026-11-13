"""restamp_meg: old flat-meta MEG streams -> current adapter header (synthetic data only)."""

import json
import os

import numpy as np
import pytest

from fidetype.adapters.spanishbcbl_meg import opaque_stream_id, segment_stream
from fidetype.conformance import check_file
from fidetype.decoders.restamp_meg import restamp_run
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import VOCAB
from fidetype.trust.provenance import file_sha256


def _old_stream(rng, T=30):
    lp = rng.normal(size=(T, len(VOCAB))).astype(np.float32)
    lp = lp - np.log(np.exp(lp).sum(-1, keepdims=True))
    meta = {"run_name": "r", "checkpoint": "best.pt", "subject": "S1", "participant": "P01", "session": "ses1",
            "block": "block2", "trial_idx": 3, "split": "test", "segment_start_s": 1.5, "frame_period_s": 0.04,
            "lookahead_frames": None, "model": "conv_ctc"}
    return NeuralTextStream(log_probs=lp, frame_times=np.arange(T) * 0.04, vocab=list(VOCAB), blank_id=0,
                            source="spanishbcbl-convctc", meta=meta, vocab_type="char")


def _setup(tmp_path, rng, ck_newer=False):
    run = tmp_path / "runs" / "r"
    run.mkdir(parents=True)
    (run / "config.json").write_text(json.dumps({"model": {"conformer_layers": 4, "lookahead_frames": None}}))
    (run / "best.pt").write_bytes(b"fake weights")
    sdir = tmp_path / "streams" / "r" / "test"
    sdir.mkdir(parents=True)
    old = _old_stream(rng)
    old.to_npz(sdir / "S1_ses1_block2_3.npz")
    (sdir / "labels.jsonl").write_text("{}\n")
    t = os.path.getmtime(sdir / "S1_ses1_block2_3.npz")
    os.utime(run / "best.pt", (t + 100, t + 100) if ck_newer else (t - 100, t - 100))
    return run, old


def test_restamp_reaches_provenance_and_keeps_logprobs(tmp_path):
    run, old = _setup(tmp_path, np.random.default_rng(0))
    assert not check_file(tmp_path / "streams" / "r" / "test" / "S1_ses1_block2_3.npz").passes("provenance")
    rep = restamp_run(run, splits=("test",), streams_root=tmp_path / "streams")
    out = tmp_path / "streams" / "r_provenance" / "test" / "S1_ses1_block2_3.npz"
    assert rep["splits"]["test"]["streams"] == 1
    assert check_file(out).passes("provenance")
    new = NeuralTextStream.from_npz(out)
    assert np.array_equal(new.log_probs, old.log_probs)
    assert new.meta["stream.id"] == opaque_stream_id("r", "best.pt", "test", "S1_ses1_block2_3")
    assert new.meta["decoder.weights_sha256"] == file_sha256(run / "best.pt")
    assert "subject" not in new.meta and new.meta["spanishbcbl.participant"] == "P01"
    # Same header as a fresh infer.py write (segment_stream with the same arguments).
    ref = segment_stream(old.log_probs, 0.04, subject="S1", session="ses1", participant="P01", block="block2",
                         trial_idx=3, split="test", run_name="r", checkpoint="best.pt", segment_start_s=1.5,
                         conformer_layers=4, lookahead_frames=None, weights_sha256=file_sha256(run / "best.pt"),
                         stream_id=opaque_stream_id("r", "best.pt", "test", "S1_ses1_block2_3"))
    assert new.meta == ref.meta
    assert (tmp_path / "streams" / "r_provenance" / "test" / "labels.jsonl").exists()


def test_restamp_refuses_newer_checkpoint(tmp_path):
    run, _ = _setup(tmp_path, np.random.default_rng(1), ck_newer=True)
    with pytest.raises(RuntimeError):
        restamp_run(run, splits=("test",), streams_root=tmp_path / "streams")
