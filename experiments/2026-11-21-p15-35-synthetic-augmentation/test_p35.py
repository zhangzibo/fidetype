"""P15-35 unit tests (toy data only; no real data, no GPU).

Run (repo root):
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -m pytest -q experiments/2026-11-21-p15-35-synthetic-augmentation/test_p35.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import numpy as np
import pytest

torch = pytest.importorskip("torch")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p35  # noqa: E402

e1 = p35.e1


def toy_lp(T: int, peaks: dict[int, int], V: int = 98) -> np.ndarray:
    """Log-probs: blank everywhere except label ``peaks[t]`` at frame t."""
    lp = np.full((T, V), -20.0)
    lp[:, 0] = -0.01
    for t, tok in peaks.items():
        lp[t, :] = -20.0
        lp[t, tok] = -0.01
    return lp


def test_ctc_last_frames_follows_peaks():
    ids = np.array([5, 6, 5])
    lp = toy_lp(30, {4: 5, 12: 6, 25: 5})
    assert p35.ctc_last_frames(lp, ids) == [4, 12, 25]


def test_ctc_repeated_label_needs_blank():
    ids = np.array([7, 7])
    lp = toy_lp(10, {2: 7, 3: 7, 6: 7})
    last = p35.ctc_last_frames(lp, ids)
    assert last is not None and last[0] < last[1] and last[1] - last[0] >= 2


def test_ctc_too_short():
    assert p35.ctc_last_frames(np.zeros((2, 98)), np.array([3, 4, 5])) is None


def test_duration_bounds_follow_peaks_with_lag():
    # 3 characters written over 30 frames; the causal model emits each one 2 frames after its end
    ids = np.array([5, 6, 7])
    lp = toy_lp(40, {11: 5, 21: 6, 31: 7})
    b = p35.duration_bounds(lp, ids, 30, lag=2)
    assert b == [(0, 10), (10, 20), (20, 30)]


def test_duration_bounds_flat_is_uniform():
    lp = np.zeros((60, 98))
    b = p35.duration_bounds(lp, np.array([5, 6, 7, 8]), 48, lag=0)
    assert [y - x for x, y in b] == [12, 12, 12, 12]
    assert p35.duration_bounds(lp, np.array([5] * 5), 4, lag=0) is None


def test_duration_bounds_prior_limits_short_segments():
    # peaks ask for lengths 2 / 2 / 56; the duration prior keeps every segment >= dmin = 5
    ids = np.array([5, 6, 7])
    lp = toy_lp(60, {1: 5, 3: 6, 59: 7})
    b = p35.duration_bounds(lp, ids, 60, lag=0)
    assert b[0][0] == 0 and b[-1][1] == 60 and min(y - x for x, y in b) >= 5


def test_uniform_bounds_cover_writing_time():
    b = p35.uniform_bounds(100, 3)
    assert b[0][0] == 0 and b[-1][1] == 100 and all(x[1] > x[0] for x in b)
    assert all(b[k][1] == b[k + 1][0] for k in range(2))


def test_blocker():
    blk = p35.Blocker(["you want me to sing?", "the quick brown fox jumps over the dog"], 5, 15)
    assert blk.blocked("you want me to sing?")  # exact
    assert blk.blocked("i said the quick brown fox jumps high")  # shared word 5-gram
    assert blk.blocked("oh, you want me to sing? fine.")  # contains a short blocked text
    assert blk.blocked("brown fox jumps over")  # contained in a blocked text (>= 15 chars)
    assert not blk.blocked("we went to the park today.")


def test_text_pool_filters():
    cfg = {"text": {"chars": "abcdefghijklmnopqrstuvwxyz ,.'?", "min_len": 10, "max_len": 40, "shuffle_seed": 1,
                    "n_pool": 100, "ngram_block": 5, "contain_min_len": 15}}
    lines = ["Hello there, friend.", "Too short", "Numbers 123 are out.", "Tom\u2019s dog is big.", "hello there, friend.",
             "You want me to sing?", "x" * 50]
    pool, counts = p35.build_text_pool(cfg, lines, ["you want me to sing?"])
    assert sorted(pool) == ["hello there, friend.", "tom's dog is big."]
    assert counts["blocked_while_sampling"] == 1


def fake_store():
    rng = np.random.default_rng(0)
    meta, x = [], {}
    texts = ["ab ab", "ba", "abba a"]
    for i, t in enumerate(texts):
        nw = 12 * len(t)
        x[i] = rng.integers(0, 5, (nw + 6, e1.N_W)).astype(np.uint8)
        meta.append({"session": i % 2, "n_write": nw, "text": t})
    st = SimpleNamespace(meta=meta, x=x, tgt={i: e1.encode(t) for i, t in enumerate(texts)},
                         length={i: len(v) for i, v in x.items()},
                         mean=np.stack([np.full(e1.N_W, 1.0), np.full(e1.N_W, 2.0)]).astype(np.float32),
                         std=np.stack([np.full(e1.N_W, 0.5), np.full(e1.N_W, 2.0)]).astype(np.float32))
    return st


def test_library_and_render_roundtrip():
    st = fake_store()
    sub = [0, 1, 2]
    lib = p35.build_library(st, sub, st.tgt, "uniform", None)
    assert set(lib.snips) == {e1.TOK["a"], e1.TOK["b"], e1.TOK[" "]}
    assert lib.stats["n_snippets"] == sum(len(st.tgt[i]) for i in sub) and len(lib.tails) == 3
    rng = np.random.default_rng(3)
    ids = e1.encode("ab a")
    x, s0 = p35.render(lib, ids, st, rng, 4)
    z = (x - st.mean[s0]) / st.std[s0]
    # every frame of z is a z-scored source frame: re-normalising with s0 gives back the library values
    lens = sum(12 for _ in ids)
    assert x.shape == (lens + 4, e1.N_W)
    assert np.allclose(z[:12], lib.snips[e1.TOK["a"]][0], atol=1e-4) or any(
        np.allclose(z[:12], a, atol=1e-4) for a in lib.snips[e1.TOK["a"]])


def test_usable_texts_need_covered_chars():
    st = fake_store()
    lib = p35.build_library(st, [0, 1, 2], st.tgt, "uniform", None)
    out = p35.usable_texts(["ab ba", "abc"], lib)
    assert len(out) == 1 and e1.decode(out[0]) == "ab ba"


def test_build_batch_deterministic():
    st = fake_store()
    lib = p35.build_library(st, [0, 1, 2], st.tgt, "uniform", None)
    texts = p35.usable_texts(["ab ba", "a b", "baab"], lib)
    rec = SimpleNamespace(max_frames=10_000, stretch_lo=0.8, stretch_hi=1.25)
    ctx = SimpleNamespace(cfg={"synth": {"tail_frames": 6}})
    out = []
    for _ in range(2):
        rng = np.random.default_rng([0, 3000, 0, 17, 3502])
        items, k = p35.build_batch(ctx, st, [0, 1, 2], st.tgt, lib, texts, 0.5, rng, rec)
        out.append((items, k))
    (a, ka), (b, kb) = out
    assert ka == kb and len(a) == len(b)
    for (xa, ta, sa), (xb, tb, sb) in zip(a, b):
        assert sa == sb and np.array_equal(ta, tb) and np.allclose(xa, xb)


def test_build_batch_respects_max_frames():
    st = fake_store()
    lib = p35.build_library(st, [0, 1, 2], st.tgt, "uniform", None)
    texts = [e1.encode("ab " * 20)]
    rec = SimpleNamespace(max_frames=200, stretch_lo=1.0, stretch_hi=1.0)
    ctx = SimpleNamespace(cfg={"synth": {"tail_frames": 6}})
    for k in range(20):
        items, _ = p35.build_batch(ctx, st, [0, 1, 2], st.tgt, lib, texts, 1.0, np.random.default_rng(k), rec)
        assert len(items) >= 1
        if len(items) > 1:
            assert max(len(x) for x, _, _ in items) * len(items) <= rec.max_frames


def test_refuses_foreign_out(tmp_path):
    assert p35.main(["textpool", "--out", r"C:\Users\zhang\bci-data\derived\p15-33\x"]) == 2
