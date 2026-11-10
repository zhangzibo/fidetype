"""Tests for the sentence-context keystroke decoder (M1-15). Synthetic data only, CPU."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
torch.set_num_threads(2)

from fidetype.decoders.keystroke import greedy_keys  # noqa: E402
from fidetype.decoders.sentence_context import (  # noqa: E402
    KeySentences,
    SentenceContextDecoder,
    SentenceModelConfig,
    collate_sentences,
    cut_windows,
    greedy_text,
    init_from_convctc,
    sentence_stream_meta,
    sentence_streams,
)
from fidetype.decoders.synthetic import write_synthetic_cache  # noqa: E402
from fidetype.eval.metrics import ctc_greedy_decode  # noqa: E402
from fidetype.lm import ctc_prefix_beam_search  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.streams.vocab import BLANK_ID, VOCAB  # noqa: E402

C, W = 8, 10
TINY = dict(n_channels=C, window_samples=W, spatial_dim=8, conv_dim=16, conv_blocks=1, conv_kernel=3,
            time_bins=5, key_dim=16, trans_layers=2, trans_heads=2, trans_ffn=32, dropout=0.0,
            input_dropout=0.0)


def _model(**kw) -> SentenceContextDecoder:
    torch.manual_seed(0)
    return SentenceContextDecoder(SentenceModelConfig(**{**TINY, "n_subjects": 2, **kw})).eval()


def _batch(lengths, seed=0):
    g = torch.Generator().manual_seed(seed)
    B, K = len(lengths), max(lengths)
    x = torch.randn(B, K, C, W, generator=g)
    km = torch.arange(K)[None, :] < torch.tensor(lengths)[:, None]
    x = x * km[..., None, None]
    kt = torch.cumsum(torch.rand(B, K, generator=g) * 0.3 + 0.05, dim=1)
    return x, km, kt


# --- shapes -------------------------------------------------------------------------------


@pytest.mark.parametrize("pool", ["flatten", "attention"])
@pytest.mark.parametrize("lookahead", [None, 0, 1])
def test_forward_shapes(pool, lookahead):
    m = _model(pool=pool, lookahead_keys=lookahead, use_key_intervals=True)
    x, km, kt = _batch([7, 3, 1])
    out = m(x, km, torch.tensor([0, 1, 0]), kt)
    assert out["logits"].shape == (3, 7, 27)
    assert out["key_logits"].shape == (3, 7, 27)
    assert torch.isfinite(out["logits"]).all()
    pc = m.param_count()
    assert pc["total"] == sum(p.numel() for p in m.parameters())
    assert pc["subject_layer"] == 2 * (8 * 8 + 8)


def test_no_key_head_when_weight_zero():
    m = _model(key_head_weight=0.0)
    x, km, kt = _batch([4])
    out = m(x, km, torch.tensor([0]))
    assert "key_logits" not in out and not m.has_key_head
    ls = m.loss(out, torch.randint(0, 27, (1, 4)))
    assert "ce_conv" not in ls and torch.allclose(ls["loss"], ls["ce"])


# --- causal mask --------------------------------------------------------------------------


@pytest.mark.parametrize("lookahead", [0, 1, 2])
def test_causal_mask_blocks_future_keys(lookahead):
    m = _model(lookahead_keys=lookahead, use_key_intervals=True)
    x, km, kt = _batch([10])
    s = torch.tensor([1])
    base = m(x, km, s, kt)["logits"]
    k = 6
    x2 = x.clone()
    x2[0, k] += 5 * torch.randn(C, W)
    kt2 = kt.clone()
    kt2[0, k:] += 0.7  # a later key time changes only the intervals from key k on
    out = m(x2, km, s, kt2)["logits"]
    first_seen = k - lookahead  # the first key whose output may see key k
    torch.testing.assert_close(out[0, :first_seen], base[0, :first_seen], atol=1e-5, rtol=1e-5)
    assert (out[0, first_seen:] - base[0, first_seen:]).abs().amax(-1).min() > 1e-4


def test_noncausal_mode_sees_future_keys():
    m = _model(lookahead_keys=None)
    x, km, kt = _batch([10])
    base = m(x, km, torch.tensor([0]), kt)["logits"]
    x2 = x.clone()
    x2[0, 9] += 5 * torch.randn(C, W)
    out = m(x2, km, torch.tensor([0]), kt)["logits"]
    assert (out[0, 0] - base[0, 0]).abs().max() > 1e-4


def test_attention_mask_rows():
    m = _model(lookahead_keys=0)
    km = torch.tensor([[True, True, False, False]])
    am = m.attention_mask(km)[0, 0]
    assert am.diagonal().all()  # never an empty row
    assert not am[0, 1] and am[1, 0]  # causal
    assert not am[1, 2] and not am[0, 3]  # valid queries never see padding


# --- padding ------------------------------------------------------------------------------


@pytest.mark.parametrize("lookahead", [None, 0])
def test_padding_does_not_change_outputs(lookahead):
    m = _model(lookahead_keys=lookahead, use_key_intervals=True)
    x, km, kt = _batch([9, 4, 2], seed=3)
    s = torch.tensor([0, 1, 1])
    out = m(x, km, s, kt)["logits"]
    # Garbage in the padded windows changes nothing.
    x_noise = x + torch.randn_like(x) * (~km)[..., None, None]
    torch.testing.assert_close(m(x_noise, km, s, kt)["logits"][km], out[km], atol=1e-5, rtol=1e-5)
    # Each padded sentence gives the same output as alone.
    for b, n in enumerate([9, 4, 2]):
        single = m(x[b : b + 1, :n], km[b : b + 1, :n], s[b : b + 1], kt[b : b + 1, :n])["logits"]
        torch.testing.assert_close(out[b, :n], single[0], atol=1e-5, rtol=1e-5)


def test_loss_ignores_padded_keys():
    m = _model()
    x, km, kt = _batch([5, 2])
    out = m(x, km, torch.tensor([0, 1]), kt)
    lab = torch.randint(0, 27, km.shape)
    lab[~km] = -100
    ls = m.loss(out, lab)
    assert int(ls["n"]) == 7 and torch.isfinite(ls["loss"])
    out2 = {k: v.clone() for k, v in out.items()}
    out2["logits"][~km] = 1e4  # junk at padded keys
    torch.testing.assert_close(m.loss(out2, lab)["ce"], ls["ce"])


def test_collate_pads_variable_lengths():
    items = []
    for n in (3, 1, 5):
        items.append({"x": torch.ones(n, C, W), "key_label": torch.arange(n), "key_time": torch.arange(n) * 0.2 + 0.1,
                      "subject": 0, "subject_id": "S1", "participant": "P01", "target_text": "a",
                      "typed_text": "a", "index": n})
    b = collate_sentences(items)
    assert b["x"].shape == (3, 5, C, W)
    assert b["key_mask"].sum(1).tolist() == [3, 1, 5]
    assert (b["key_labels"][~b["key_mask"]] == -100).all()
    assert (b["x"][~b["key_mask"]] == 0).all()
    assert (torch.diff(b["key_times"], dim=1) >= 0).all()  # padded times repeat the last time


# --- tiny overfit -------------------------------------------------------------------------


def test_tiny_overfit_synthetic():
    """Each class has its own spatial pattern; the model must learn it in a few seconds."""
    rng = np.random.default_rng(0)
    pat = rng.standard_normal((27, C)).astype(np.float32)
    lengths = [12, 9, 7, 11, 5, 8]
    K = max(lengths)
    labels = torch.full((len(lengths), K), -100, dtype=torch.long)
    x = torch.zeros(len(lengths), K, C, W)
    for b, n in enumerate(lengths):
        lab = rng.integers(0, 27, size=n)
        labels[b, :n] = torch.from_numpy(lab)
        sig = pat[lab][:, :, None] * np.hanning(W)[None, None, :]
        x[b, :n] = torch.from_numpy((2 * sig + 0.3 * rng.standard_normal((n, C, W))).astype(np.float32))
    km = labels != -100
    subj = torch.tensor([0, 1, 0, 1, 0, 1])
    m = _model(lookahead_keys=0).train()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-2)
    first = None
    for _ in range(150):
        ls = m.loss(m(x, km, subj), labels)
        first = float(ls["loss"].detach()) if first is None else first
        opt.zero_grad()
        ls["loss"].backward()
        opt.step()
    m.eval()
    with torch.no_grad():
        ls = m.loss(m(x, km, subj), labels)
    assert float(ls["loss"]) < 0.2 * first
    assert int(ls["correct"]) / int(ls["n"]) > 0.95


# --- streams ------------------------------------------------------------------------------


def test_stream_export_is_valid(tmp_path):
    m = _model(lookahead_keys=0)
    x, km, kt = _batch([6, 3])
    out = m(x, km, torch.tensor([0, 1]), kt)
    metas = [sentence_stream_meta(m, "S1", "ses1", {"split": "test"}), sentence_stream_meta(m, "S18", "ses1")]
    streams = sentence_streams(out["logits"].log_softmax(-1), km, kt, metas)
    assert len(streams) == 2
    for b, (s, n) in enumerate(zip(streams, [6, 3])):
        assert isinstance(s, NeuralTextStream)
        assert s.vocab == list(VOCAB) and s.blank_id == BLANK_ID
        assert s.n_frames == 2 * n - 1
        assert np.all(np.diff(s.frame_times) > 0)
        np.testing.assert_allclose(s.frame_times[0::2], kt[b, :n].numpy(), atol=1e-6)
        assert greedy_keys(s) == greedy_text(out["logits"][b], n)
        assert s.meta["decoder.name"] == "fidetype-keystroke-sentence"
        assert s.meta["decoder.causal"] is True and s.meta["decoder.lookahead_keys"] == 0
        p = tmp_path / f"s{b}.npz"
        s.to_npz(p)
        s2 = NeuralTextStream.from_npz(p)  # validates
        np.testing.assert_array_equal(s2.log_probs, s.log_probs)
        hyp = ctc_prefix_beam_search(s2, None, beam=8, n_best=3)
        assert hyp and isinstance(hyp[0].text, str)
        assert len(ctc_greedy_decode(s2)) <= n


# --- participants -------------------------------------------------------------------------


def test_participant_layer_sharing():
    m = _model()
    with torch.no_grad():
        m.subj_w[1] += 0.5 * torch.randn_like(m.subj_w[1])
    x, km, kt = _batch([4])
    same0 = m(x, km, torch.tensor([0]))["logits"]
    same0b = m(x, km, torch.tensor([0]))["logits"]
    other = m(x, km, torch.tensor([1]))["logits"]
    torch.testing.assert_close(same0, same0b)
    assert (same0 - other).abs().max() > 1e-4
    # The participant layer gets gradient only from its own participant.
    m.train()
    m.zero_grad()
    m.loss(m(x, km, torch.tensor([1])), torch.zeros(1, 4, dtype=torch.long))["loss"].backward()
    assert m.subj_w.grad[0].abs().sum() == 0 and m.subj_w.grad[1].abs().sum() > 0


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("cache") / "v1"
    write_synthetic_cache(root, n_subjects=2, blocks_per_subject=1, trials_per_block=8, amplitude=3.0, seed=1)
    return root


def test_one_person_two_subject_ids_share_a_participant_index(tmp_path):
    root = tmp_path / "v1"
    write_synthetic_cache(root, n_subjects=2, blocks_per_subject=1, trials_per_block=5, amplitude=1.0, seed=3)
    for sc in root.glob("*/*.json"):  # S1/S18-style: two subject IDs, one person
        meta = json.loads(sc.read_text())
        meta["participant"] = "P01"
        sc.write_text(json.dumps(meta))
    ds = KeySentences(root, ("train", "val", "test"), mmap_dir=tmp_path / "mm")
    assert ds.subject_map == {"P01": 0}
    assert len({s.subject for s in ds.segments}) == 2
    assert {ds[i]["subject"] for i in range(len(ds))} == {0}


# --- data ---------------------------------------------------------------------------------


def test_cut_windows_edges():
    block = np.arange(3 * 30, dtype=np.float32).reshape(3, 30)
    w = cut_windows(block, np.array([1, 15, 29]), -2, 5)
    assert w.shape == (3, 3, 5)
    np.testing.assert_array_equal(w[1, 0], block[0, 13:18])
    np.testing.assert_array_equal(w[0, 2], block[2, [0, 0, 1, 2, 3]])  # left edge repeats
    np.testing.assert_array_equal(w[2, 1], block[1, [27, 28, 29, 29, 29]])  # right edge repeats


def test_key_sentences_items(cache, tmp_path):
    ds = KeySentences(cache, ("train",), mmap_dir=tmp_path / "mm")
    assert len(ds) > 0
    item = ds[0]
    seg = ds.segments[0]
    K = len(seg.key_abs)
    assert item["x"].shape == (K, 306, 50)
    assert item["key_label"].shape == (K,) and int(item["key_label"].max()) < 27
    assert ds.lengths()[0] == K
    # Window k starts 0.2 s (20 samples) before key k.
    arr = np.asarray(ds.base._array(seg.npz), dtype=np.float32)
    k0 = seg.key_abs[0]
    np.testing.assert_allclose(item["x"][0].numpy(), arr[:, k0 - 20 : k0 + 30])
    np.testing.assert_allclose(item["key_time"].numpy(), (np.array(seg.key_abs) - seg.start) / 100.0)


# --- train / infer wiring -----------------------------------------------------------------

CACHE_MODEL = dict(spatial_dim=8, conv_dim=16, conv_blocks=1, conv_kernel=3, key_dim=16, trans_layers=1,
                   trans_heads=2, trans_ffn=32, dropout=0.0, input_dropout=0.0, lookahead_keys=0)


def _cfg(cache: Path, tmp: Path) -> dict:
    return {
        "run_name": "t",
        "runs_dir": str(tmp),
        "data": {"root": str(cache), "train_splits": ["train", "val", "test"], "val_splits": ["val", "test"],
                 "batch_size": 4, "eval_batch_size": 8, "augment": {}, "mmap_dir": str(tmp / "mm")},
        "model": CACHE_MODEL,
        "optim": {"lr": 3e-3, "warmup_steps": 2, "epochs": 2, "weight_decay": 0.0},
        "train": {"seed": 0, "device": "cpu", "bf16": False, "log_every_steps": 1000, "torch_threads": 2,
                  "patience_evals": 1000},
    }


def test_train_resume_and_infer(cache, tmp_path):
    from fidetype.decoders.infer_sentence import run_inference
    from fidetype.decoders.train_sentence import train

    cfg = _cfg(cache, tmp_path)
    train(cfg, tmp_path / "a", max_steps=5, echo=False)
    train(cfg, tmp_path / "b", max_steps=2, echo=False)
    res = train(cfg, tmp_path / "b", resume=True, max_steps=5, echo=False)
    assert res["global_step"] == 5
    a = torch.load(tmp_path / "a" / "latest.pt", weights_only=False)
    b = torch.load(tmp_path / "b" / "latest.pt", weights_only=False)
    for k in a["model"]:
        torch.testing.assert_close(a["model"][k], b["model"][k], atol=1e-6, rtol=1e-6, msg=k)
    train(cfg, tmp_path / "full", echo=False)  # 2 epochs with validation
    recs = [json.loads(line) for line in (tmp_path / "full" / "metrics.jsonl").read_text().splitlines()]
    ep = [r for r in recs if r["type"] == "epoch"]
    assert len(ep) == 2 and "val_cer_typed" in ep[-1] and "val_key_acc_conv" in ep[-1]

    from fidetype.lm import CharNgramLM
    from fidetype.streams.corpus import sentences

    CharNgramLM(order=3).train(sentences(40, seed=5)).save(tmp_path / "lm.npz")
    out = run_inference(tmp_path / "full", splits=("val", "train"), out_root=tmp_path / "streams", device="cpu",
                        control=True, lm_path=str(tmp_path / "lm.npz"), lm_weights=(0.5, 1.0), echo=False)
    assert out["lm_weight"] in (0.5, 1.0) and set(out["lm_weight_val_scores"]) == {0.5, 1.0}
    tr = out["splits"]["train"]
    assert {"greedy_real", "greedy_shuffled", "greedy_zeros", "gap_greedy"} <= set(tr)
    assert {"beam_lm_real", "beam_lm_shuffled", "beam_lm_zeros", "gap_beam_lm"} <= set(tr)
    assert tr["greedy_real"]["mean_over_participants"]["cer_target"] >= 0
    sdir = tmp_path / "streams" / "full" / "train"
    files = sorted(sdir.glob("*.npz"))
    labels = [json.loads(line) for line in (sdir / "labels.jsonl").read_text().splitlines()]
    assert files and len(files) == len(labels)
    for f in files:
        st = NeuralTextStream.from_npz(f)
        assert st.source == "fidetype-keystroke-sentence"
        meta_s = json.dumps(st.meta)
        assert not any(lab["target_text"] in meta_s for lab in labels)


def test_init_from_convctc_checkpoint(tmp_path):
    from fidetype.decoders.conv_ctc import ConvCTC, ModelConfig

    src = ConvCTC(ModelConfig(n_channels=C, n_subjects=2, spatial_dim=8, conv_dim=16, conv_blocks=1,
                              conv_kernel=3, model_dim=16, conformer_layers=1, conformer_heads=2,
                              conformer_ffn=32, conformer_kernel=3))
    torch.save({"model": src.state_dict()}, tmp_path / "c.pt")
    m = _model()
    loaded, _ = init_from_convctc(m, tmp_path / "c.pt")
    assert "spatial.conv.weight" in loaded and "subj_w" in loaded and "blocks.0.conv.conv.weight" in loaded
    torch.testing.assert_close(m.spatial.conv.weight, src.spatial.conv.weight)
