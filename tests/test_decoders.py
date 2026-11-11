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
    drop = {"active_s"}  # wall time differs between runs
    assert {k: v for k, v in a["state"].items() if k not in drop} == {k: v for k, v in b["state"].items() if k not in drop}


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


# --- M1-C: keystroke auxiliary loss ---------------------------------------------------------


def test_key_frame_mapping():
    m = _model(aux_keystroke_weight=0.5)
    assert m.cfg.downsample == 4
    s = torch.tensor([[0, 3, 4, 7, 8, 399, 400]])
    assert m.key_frames(s).tolist() == [[0, 0, 1, 1, 2, 99, 100]]
    # Pooling clamps to the valid frames of each item (out length 10 for 37 samples).
    out = m(torch.randn(1, 306, 37), torch.tensor([37]), torch.tensor([0]))
    lg = m.key_logits(out, torch.tensor([[44, 200]]))  # frames 11 and 50: both clamp to 9
    torch.testing.assert_close(lg["conv"][0, 0], lg["conv"][0, 1])


def test_dataset_key_positions(cache):
    from fidetype.decoders.dataset import KEY_IGNORE, N_KEY_CLASSES, key_class

    assert N_KEY_CLASSES == 27
    assert key_class("a") == 0 and key_class("z") == 25 and key_class(" ") == 26
    assert key_class("<ret>") == KEY_IGNORE and key_class("") == KEY_IGNORE
    plain = MEGSegments(cache, ("train", "val", "test"), augment=None)
    i = next(k for k, sg in enumerate(plain.segments) if sg.subject == "S90")
    item, seg = plain[i], plain.segments[i]
    side = json.loads((cache / (seg.npz[: -len(".npz")] + ".json")).read_text())
    raw = next(sg for sg in side["segments"] if sg["trial_idx"] == seg.trial_idx)
    assert item["key_pos"].tolist() == raw["key_samples"]  # relative to the segment start
    assert item["key_label"].tolist() == [key_class(c) for c in raw["key_chars"]]
    # With start jitter and a time stretch, the keys move with the data.
    aug = MEGSegments(cache, ("train", "val", "test"), seed=0,
                      augment=AugmentConfig(end_jitter_s=0.0, stretch_min=1.2, stretch_max=1.2))
    it2 = aug[i]
    T_new = it2["x"].shape[1]
    T0 = seg.end - it2["start_sample"]
    shift = it2["start_sample"] - seg.start
    expect = np.round((np.array(raw["key_samples"]) - shift) * (T_new - 1) / (T0 - 1))
    np.testing.assert_array_equal(it2["key_pos"].numpy(), expect)
    assert int(it2["key_pos"].max()) < T_new
    # Collate pads and masks the keys.
    b = collate([plain[0], plain[1], plain[2]])
    K = max(len(plain[j]["key_pos"]) for j in range(3))
    assert b["key_samples"].shape == b["key_labels"].shape == b["key_mask"].shape == (3, K)
    for j in range(3):
        n = len(plain[j]["key_pos"])
        assert int(b["key_mask"][j].sum()) == n
        assert (b["key_labels"][j, n:] == KEY_IGNORE).all()


def test_blocks_filter(cache):
    from fidetype.decoders.dataset import block_id

    allseg = MEGSegments(cache, ("train", "val", "test"))
    ids = sorted({block_id(sg.npz) for sg in allseg.segments})
    assert len(ids) == 2
    one = MEGSegments(cache, ("train", "val", "test"), blocks=[ids[0]])
    assert {block_id(sg.npz) for sg in one.segments} == {ids[0]}
    assert 0 < len(one) < len(allseg)


@pytest.mark.parametrize("layer", ["conv", "conformer", "both"])
def test_key_head_shapes_and_loss(layer):
    m = _model(aux_keystroke_weight=0.5, aux_key_layer=layer).train()
    x = torch.randn(2, 306, 300)
    L = torch.tensor([300, 250])
    out = m(x, L, torch.tensor([0, 1]))
    ks = torch.tensor([[10, 50, 299, 0], [5, 100, 249, 0]])
    kl = torch.tensor([[0, 26, 3, -100], [4, 5, -100, -100]])
    lg = m.key_logits(out, ks)
    assert set(lg) == ({"conv", "conformer"} if layer == "both" else {layer})
    assert all(v.shape == (2, 4, 27) for v in lg.values())
    tg = torch.randint(1, 28, (2, 20))
    ls = m.loss(out, tg, torch.tensor([20, 15]), ks, kl)
    assert int(ls["key_n"]) == 5
    assert torch.isfinite(ls["loss"]) and torch.isfinite(ls["key_ce"])
    w = m.cfg.aux_weight
    ctc = (1 - w) * ls["ctc_final"] + w * ls["ctc_aux"]
    torch.testing.assert_close(ls["loss"], ctc + 0.5 * ls["key_ce"])
    ls["loss"].backward()
    assert all(h.weight.grad is not None for h in m.key_heads.values())
    # All labels ignored: the loss stays finite.
    ls0 = m.loss(m(x, L, torch.tensor([0, 1])), tg, torch.tensor([20, 15]), ks, torch.full_like(kl, -100))
    assert torch.isfinite(ls0["loss"])
    assert out["logits"].shape == (2, 75, 28)


def test_key_weight_zero_is_unchanged():
    base = _model()
    off = _model(aux_keystroke_weight=0.0)
    on = _model(aux_keystroke_weight=1.0)
    assert not off.has_key_head and on.has_key_head
    assert set(base.state_dict()) == set(off.state_dict())
    assert base.param_count() == off.param_count()
    # The key heads are made last: all other parameters have the same initial values.
    for k, v in base.state_dict().items():
        torch.testing.assert_close(on.state_dict()[k], v, msg=k)
    x = torch.randn(2, 306, 300)
    L, s = torch.tensor([300, 250]), torch.tensor([0, 1])
    tg, tl = torch.randint(1, 28, (2, 20)), torch.tensor([20, 15])
    ks, kl = torch.tensor([[10, 50]]).repeat(2, 1), torch.tensor([[1, 2]]).repeat(2, 1)
    ob, oo, on_ = base(x, L, s), off(x, L, s), on(x, L, s)
    torch.testing.assert_close(ob["logits"], on_["logits"])  # the head does not change the CTC output
    lb = base.loss(ob, tg, tl)
    lo = off.loss(oo, tg, tl, ks, kl)  # keys are ignored without a head
    assert set(lo) == {"loss", "ctc_final", "ctc_aux"}
    torch.testing.assert_close(lb["loss"], lo["loss"])
    lon = on.loss(on_, tg, tl, ks, kl)
    torch.testing.assert_close(lon["ctc_final"], lb["ctc_final"])
    # Pretraining mode: ctc_weight = 0 leaves only the keystroke loss.
    pre = _model(aux_keystroke_weight=1.0, ctc_weight=0.0)
    lp = pre.loss(pre(x, L, s), tg, tl, ks, kl)
    torch.testing.assert_close(lp["loss"], lp["key_ce"])


def test_tiny_overfit_with_key_aux(tmp_path):
    from fidetype.decoders.train import train

    # A stronger signal than the shared cache. The synthetic response peaks
    # 100 ms after the key, so the head reads 2 frames (80 ms) after it.
    strong = write_synthetic_cache(tmp_path / "v1", n_subjects=2, blocks_per_subject=1, trials_per_block=14,
                                   amplitude=12.0, seed=1)
    cfg = _cfg(strong, tmp_path, patience_evals=1000, log_every_steps=1)
    cfg["optim"]["epochs"] = 25
    cfg["model"] = {**TINY, "aux_keystroke_weight": 1.0, "aux_key_layer": "both", "aux_key_shift_frames": 2}
    train(cfg, tmp_path / "run", echo=False)
    recs = [json.loads(line) for line in (tmp_path / "run" / "metrics.jsonl").read_text().splitlines()]
    tr = [r for r in recs if r["type"] == "train"]
    ep = [r for r in recs if r["type"] == "epoch"]
    assert len(ep) == 25
    assert ep[-1]["train_loss"] < 0.6 * ep[0]["train_loss"]
    first = np.mean([r["key_ce"] for r in tr[:6]])
    last = np.mean([r["key_ce"] for r in tr[-6:]])
    assert last < 0.5 * first, (first, last)
    assert np.mean([r["key_acc_conv"] for r in tr[-6:]]) > 0.5  # chance is about 0.15
    assert "val_key_acc" in ep[-1] and "val_key_acc_conformer" in ep[-1]


def test_init_from_and_infer_key_head(cache, tmp_path):
    from fidetype.decoders.infer import bootstrap_mean_ci, run_inference
    from fidetype.decoders.train import train

    cfg = _cfg(cache, tmp_path)
    cfg["optim"]["epochs"] = 2
    cfg["model"] = {**TINY, "aux_keystroke_weight": 1.0, "ctc_weight": 0.0}
    cfg["train"]["early_stop_metric"] = "val_key_err"
    train(cfg, tmp_path / "pre", echo=False)
    cfg2 = _cfg(cache, tmp_path)
    cfg2["optim"]["epochs"] = 1
    cfg2["model"] = {**TINY, "aux_keystroke_weight": 0.5}
    cfg2["train"]["init_from"] = str(tmp_path / "pre" / "best.pt")
    train(cfg2, tmp_path / "ft", echo=False)
    assert "init_from" in (tmp_path / "ft" / "train.log").read_text()
    res = run_inference(tmp_path / "ft", splits=("val",), out_root=tmp_path / "streams", device="cpu",
                        echo=False, control=True)
    v = res["splits"]["val"]
    assert 0 <= v["keystroke_head"]["acc_conv"] <= 1
    assert set(v["meg_control"]) == {"real", "shuffled", "zeros"}
    assert "key_acc_conv" in v["meg_control"]["real"]
    g = v["meg_control_gap"]["cer_target"]
    assert g["ci95_lo"] <= g["mean"] <= g["ci95_hi"]
    ci = bootstrap_mean_ci(np.ones(10))
    assert ci["mean"] == ci["ci95_lo"] == ci["ci95_hi"] == 1.0


def test_one_person_two_subject_ids_share_a_subject_layer(tmp_path):
    """SpanishBCBL S1 and S18 are one person (P01). Segments of both IDs
    must use one subject index, and the summary must count the person once."""
    root = tmp_path / "v1"
    write_synthetic_cache(root, n_subjects=2, blocks_per_subject=1, trials_per_block=6, amplitude=1.0, seed=3)
    subjects = sorted({p.parent.name for p in root.glob("*/*.json")})
    assert len(subjects) == 2
    for sc in root.glob("*/*.json"):  # give both subject IDs one participant
        meta = json.loads(sc.read_text())
        meta["participant"] = "P01"
        sc.write_text(json.dumps(meta))
    ds = MEGSegments(root, ("train", "val", "test"))
    assert ds.subject_map == {"P01": 0}
    assert {s.subject for s in ds.segments} == set(subjects)


def test_summarize_counts_each_participant_once():
    from fidetype.decoders.infer import summarize

    def row(subject, participant, c):
        return {"subject": subject, "participant": participant,
                "cer_target": c, "cer_typed": c, "wer_target": c, "wer_typed": c}

    rows = [row("S1", "P01", 0.2), row("S18", "P01", 0.4), row("S18", "P01", 0.4), row("S3", "P03", 0.8)]
    out = summarize(rows)
    assert set(out["per_subject"]) == {"S1", "S18", "S3"}
    assert set(out["per_participant"]) == {"P01", "P03"}
    assert out["per_participant"]["P01"]["n"] == 3
    assert out["mean_over_subjects"]["cer_target"] == pytest.approx((0.2 + 0.4 + 0.8) / 3)
    assert out["mean_over_participants"]["cer_target"] == pytest.approx(((0.2 + 0.4 + 0.4) / 3 + 0.8) / 2)
    # Rows without a participant key fall back to the subject ID.
    legacy = summarize([{k: v for k, v in r.items() if k != "participant"} for r in rows])
    assert set(legacy["per_participant"]) == {"S1", "S18", "S3"}


def test_trend_update_ema_and_min_delta():
    from fidetype.decoders.train import trend_update

    st: dict = {}
    assert trend_update(st, 1.0, 0.5, 0.01)  # first value starts the EMA
    assert st["smooth"] == 1.0
    assert trend_update(st, 0.8, 0.5, 0.01)  # EMA 0.9 < 1.0 - 0.01
    assert abs(st["smooth"] - 0.9) < 1e-12
    assert not trend_update(st, 0.88, 0.5, 0.01)  # EMA 0.89: drop 0.01 is not > min_delta
    assert not trend_update(st, 1.5, 0.5, 0.01)  # one bad value raises the EMA: no improvement
    assert st["best_smooth"] == 0.9


def test_trend_stop_in_training(cache, tmp_path):
    from fidetype.decoders.train import train

    cfg = _cfg(cache, tmp_path, patience_evals=2, smooth_alpha=0.3, min_delta=10.0)
    cfg["optim"]["epochs"] = 20
    res = train(cfg, tmp_path / "run", echo=False)
    # min_delta 10 > any CER drop: only the first eval improves, so the stop fires after 1 + 2 evals.
    assert res["stop_reason"] == "early_stop" and res["epoch"] == 3, res
    recs = [json.loads(x) for x in (tmp_path / "run" / "metrics.jsonl").read_text().splitlines()]
    assert all("val_smooth" in r for r in recs if r["type"] == "epoch")
    assert (tmp_path / "run" / "best.pt").exists()
    st = json.loads((tmp_path / "run" / "status.json").read_text())
    assert st["status"] == "early_stopped" and st["smooth"] is not None
