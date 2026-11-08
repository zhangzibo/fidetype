"""Tests for the ConvCTC decoder. They need torch (GPU env) and skip without it."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from fidetype.decoders.conv_ctc import ConvCTC, ModelConfig  # noqa: E402
from fidetype.decoders.dataset import (  # noqa: E402
    AugmentConfig,
    BucketBatchSampler,
    MEGSegments,
    collate,
    time_stretch,
)
from fidetype.decoders.synthetic import write_synthetic_cache  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402

TINY = dict(spatial_dim=32, conv_dim=48, conv_blocks=2, model_dim=32, conformer_layers=2,
            conformer_heads=2, conformer_ffn=64, conformer_kernel=5, dropout=0.0)


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("cache") / "v1"
    write_synthetic_cache(root, n_subjects=2, blocks_per_subject=1, trials_per_block=14, amplitude=3.0, seed=1)
    return root


def _model(**kw) -> ConvCTC:
    torch.manual_seed(0)
    return ConvCTC(ModelConfig(**{**TINY, "n_subjects": 2, **kw})).eval()


@pytest.mark.parametrize("lookahead", [None, 0, 2])
def test_forward_shapes(lookahead):
    m = _model(lookahead_frames=lookahead)
    x = torch.randn(3, 306, 401)
    L = torch.tensor([401, 300, 37])
    out = m(x, L, torch.tensor([0, 1, 0]))
    assert out["logits"].shape == (3, 101, 28)
    assert out["aux_logits"].shape == (3, 101, 28)
    assert out["out_lengths"].tolist() == [101, 75, 10]
    assert m.param_count()["total"] == sum(p.numel() for p in m.parameters())


def test_batch_matches_single():
    m = _model()
    x = torch.randn(2, 306, 200)
    L = torch.tensor([200, 120])
    out = m(x, L, torch.tensor([0, 1]))
    single = m(x[1:, :, :120], L[1:], torch.tensor([1]))
    torch.testing.assert_close(out["logits"][1, :30], single["logits"][0], atol=1e-4, rtol=1e-4)


@pytest.mark.parametrize("lookahead", [0, 2])
def test_causal_mode_is_causal(lookahead):
    m = _model(lookahead_frames=lookahead)
    T = 400
    x = torch.randn(1, 306, T)
    L, s = torch.tensor([T]), torch.tensor([0])
    base = m(x, L, s)["logits"]
    j = 40  # check frames 0..j
    total = m.total_lookahead_frames()
    first_free = 4 * (j + total) + 1  # the first sample that frame j must not see
    x2 = x.clone()
    x2[:, :, first_free:] = torch.randn(1, 306, T - first_free) * 5
    out2 = m(x2, L, s)["logits"]
    torch.testing.assert_close(base[:, : j + 1], out2[:, : j + 1], atol=1e-5, rtol=1e-5)
    # The change must reach later frames (else the test proves nothing).
    assert not torch.allclose(base[:, j + total + 2 :], out2[:, j + total + 2 :])


def test_offline_mode_sees_future():
    m = _model()
    x = torch.randn(1, 306, 400)
    L, s = torch.tensor([400]), torch.tensor([0])
    x2 = x.clone()
    x2[:, :, 300:] += 5
    assert not torch.allclose(m(x, L, s)["logits"][:, :10], m(x2, L, s)["logits"][:, :10])


def test_ctc_loss_finite():
    m = _model()
    x = torch.randn(2, 306, 300)
    out = m(x, torch.tensor([300, 250]), torch.tensor([0, 1]))
    tg = torch.randint(1, 28, (2, 20))
    ls = m.loss(out, tg, torch.tensor([20, 15]))
    assert all(torch.isfinite(v) for v in ls.values())
    ls["loss"].backward()


def test_dataset_and_collate(cache):
    ds = MEGSegments(cache, ("train", "val", "test"), augment=AugmentConfig(), seed=0)
    assert len(ds) == 2 * 12  # practice trials 0 and 1 are excluded
    assert set(ds.subject_map.values()) == {0, 1}
    a, b = ds[0], ds[0]
    torch.testing.assert_close(a["x"], b["x"])  # same (seed, epoch, index)
    ds.set_epoch(1)
    c = ds[0]
    assert c["x"].shape != a["x"].shape or not torch.equal(c["x"], a["x"])
    batch = collate([ds[i] for i in range(4)])
    assert batch["x"].shape[:2] == (4, 306)
    assert batch["x"].dtype == torch.float32
    assert batch["lengths"].max() == batch["x"].shape[2]
    plain = MEGSegments(cache, ("train", "val", "test"), augment=None)
    seg = plain.segments[0]
    assert plain[0]["x"].shape[1] == seg.end - seg.start
    assert isinstance(plain._arrays[seg.npz], np.memmap)


def test_time_stretch():
    x = np.random.default_rng(0).standard_normal((3, 100)).astype(np.float32)
    assert time_stretch(x, 1.1).shape == (3, 110)
    np.testing.assert_allclose(time_stretch(x, 1.0), x, atol=1e-6)


def test_sampler_skip():
    s = BucketBatchSampler(list(range(50)), 8, seed=3)
    s.set_epoch(2)
    full = list(s)
    s.set_epoch(2, skip=3)
    assert list(s) == full[3:]
    assert sorted(i for b in full for i in b) == list(range(50))


def _cfg(cache: Path, tmp: Path, **train) -> dict:
    return {
        "run_name": "t",
        "runs_dir": str(tmp),
        "data": {"root": str(cache), "train_splits": ["train", "val", "test"], "val_splits": ["val"],
                 "batch_size": 4, "eval_batch_size": 8, "augment": None, "mmap_dir": str(tmp / "mm")},
        "model": TINY,
        "optim": {"lr": 3e-3, "warmup_steps": 5, "epochs": 40, "weight_decay": 0.0},
        "train": {"seed": 0, "device": "cpu", "bf16": False, "log_every_steps": 1000, **train},
    }


def test_tiny_overfit(cache, tmp_path):
    from fidetype.decoders.train import train

    cfg = _cfg(cache, tmp_path, patience_evals=1000)
    cfg["optim"]["epochs"] = 30
    train(cfg, tmp_path / "run", echo=False)
    lines = (tmp_path / "run" / "metrics.jsonl").read_text().splitlines()
    ep = [r["train_loss"] for r in map(json.loads, lines) if r["type"] == "epoch"]
    assert len(ep) == 30
    assert ep[-1] < 0.6 * ep[0], ep


def test_checkpoint_resume_identical(cache, tmp_path):
    from fidetype.decoders.train import train

    cfg = _cfg(cache, tmp_path, patience_evals=1000)
    cfg["optim"]["epochs"] = 3
    cfg["data"]["augment"] = {}  # default augmentations on: they must be reproducible too
    cfg["model"] = {**TINY, "dropout": 0.1}
    train(cfg, tmp_path / "a", max_steps=14, echo=False)
    train(cfg, tmp_path / "b", max_steps=8, echo=False)  # stops in the middle of epoch 1 (6 steps/epoch)
    res = train(cfg, tmp_path / "b", resume=True, max_steps=14, echo=False)
    assert res["global_step"] == 14
    a = torch.load(tmp_path / "a" / "latest.pt", weights_only=False)
    b = torch.load(tmp_path / "b" / "latest.pt", weights_only=False)
    for k in a["model"]:
        torch.testing.assert_close(a["model"][k], b["model"][k], atol=1e-6, rtol=1e-6, msg=k)
    assert a["state"] == b["state"]


def test_infer_writes_valid_streams(cache, tmp_path):
    from fidetype.decoders.infer import run_inference
    from fidetype.decoders.train import train

    cfg = _cfg(cache, tmp_path)
    cfg["optim"]["epochs"] = 1
    cfg["data"]["train_splits"] = ["train"]
    train(cfg, tmp_path / "run", echo=False)
    res = run_inference(tmp_path / "run", splits=("train", "val"), out_root=tmp_path / "streams",
                        device="cpu", echo=False, control=True)
    assert set(res["splits"]["train"]["meg_control"]) == {"real", "shuffled", "zeros"}
    sdir = tmp_path / "streams" / "run" / "train"
    files = sorted(sdir.glob("*.npz"))
    assert files
    labels = [json.loads(line) for line in (sdir / "labels.jsonl").read_text().splitlines()]
    assert len(labels) == len(files)
    for f in files:
        st = NeuralTextStream.from_npz(f)  # from_npz validates the stream
        assert st.source == "spanishbcbl-convctc"
        assert st.vocab_size == 28
        np.testing.assert_allclose(np.diff(st.frame_times), 0.04, atol=1e-9)
        assert "target_text" not in st.meta and "typed_text" not in st.meta
        meta_s = json.dumps(st.meta)
        assert not any(lab["target_text"] in meta_s for lab in labels if lab["target_text"])
        assert st.meta["split"] == "train"
    tr = res["splits"]["train"]
    assert tr["n_sentences"] == len(files)
    assert tr["mean_over_subjects"]["cer_target"] >= 0
    assert (tmp_path / "streams" / "run" / "metrics.json").exists()
