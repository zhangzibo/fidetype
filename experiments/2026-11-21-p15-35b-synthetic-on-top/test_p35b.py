r"""P15-35b unit tests (toy data only; no real data, no GPU).

Run (repo root):
  C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-21-p15-35b-synthetic-on-top/test_p35b.py
"""

from __future__ import annotations

import json
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
import p35b  # noqa: E402

L, e1 = p35b.L, p35b.e1


def fake_store(n: int = 6):
    rng = np.random.default_rng(0)
    meta, x = [], {}
    texts = ["ab ab", "ba", "abba a", "a b", "bab", "aa bb"][:n]
    for i, t in enumerate(texts):
        nw = 12 * len(t)
        x[i] = rng.integers(0, 5, (nw + 6, e1.N_W)).astype(np.uint8)
        meta.append({"session": i % 2, "n_write": nw, "text": t})
    return SimpleNamespace(meta=meta, x=x, tgt={i: e1.encode(t) for i, t in enumerate(texts)},
                           length={i: len(v) for i, v in x.items()},
                           mean=np.stack([np.full(e1.N_W, 1.0), np.full(e1.N_W, 2.0)]).astype(np.float32),
                           std=np.stack([np.full(e1.N_W, 0.5), np.full(e1.N_W, 2.0)]).astype(np.float32))


def setup(max_frames=400, stretch=(1.0, 1.0)):
    st = fake_store()
    sub = list(range(6))
    lib = L.build_library(st, sub, st.tgt, "uniform", None)
    texts = L.usable_texts(["ab ba", "a b", "baab"], lib)
    rec = SimpleNamespace(max_frames=max_frames, stretch_lo=stretch[0], stretch_hi=stretch[1])
    ctx = SimpleNamespace(cfg={"synth": {"tail_frames": 6}})
    return st, sub, lib, texts, rec, ctx


def real_part(st, sub, rec, seed):
    return e1.pack_batch(sub, st.length, rec.max_frames, np.random.default_rng(seed))


def test_n_extra_mean():
    rng = np.random.default_rng(0)
    v = [p35b.n_extra(0.5, 3, rng) for _ in range(20000)]
    assert set(v) <= {1, 2} and abs(np.mean(v) - 1.5) < 0.02
    assert p35b.n_extra(1.0, 4, rng) == 4 and p35b.n_extra(0.0, 4, rng) == 0


def test_ontop_keeps_all_real_items():
    st, sub, lib, texts, rec, ctx = setup()
    spec = {"mode": "ontop", "extra": 1.0}
    for k in range(30):
        bi = real_part(st, sub, rec, k)
        items, k_syn, k_real = p35b.build_batch_b(ctx, st, sub, st.tgt, lib, texts, spec, np.random.default_rng(k), rec)
        assert k_real == len(bi)  # the real part is the P15-33 packing, never dropped
        for (x, t, s), i in zip(items[:k_real], bi):
            assert np.array_equal(t, st.tgt[i]) and s == st.meta[i]["session"] and len(x) == len(st.x[i])
        assert k_syn <= len(bi)
        if k_syn:
            assert max(len(x) for x, _, _ in items) * len(items) <= 2 * rec.max_frames


def test_none_equals_real_packing():
    st, sub, lib, texts, rec, ctx = setup()
    items, k_syn, k_real = p35b.build_batch_b(ctx, st, sub, st.tgt, None, [], {"mode": "none"},
                                              np.random.default_rng(5), rec)
    assert k_syn == 0 and k_real == len(real_part(st, sub, rec, 5))


def test_replace_cap_and_share():
    st, sub, lib, texts, rec, ctx = setup()
    spec = {"mode": "replace", "synth_frac": 0.2}
    n_s = n_all = 0
    for k in range(300):
        items, k_syn, k_real = p35b.build_batch_b(ctx, st, sub, st.tgt, lib, texts, spec, np.random.default_rng(k), rec)
        n_s += k_syn; n_all += k_syn + k_real
        if len(items) > 1:
            assert max(len(x) for x, _, _ in items) * len(items) <= rec.max_frames or k_syn == 0
    assert 0.1 < n_s / n_all < 0.3


def test_deterministic():
    st, sub, lib, texts, rec, ctx = setup(stretch=(0.8, 1.25))
    spec = {"mode": "ontop", "extra": 0.5}
    a = p35b.build_batch_b(ctx, st, sub, st.tgt, lib, texts, spec, np.random.default_rng([0, 3, 0, 17, 3521]), rec)
    b = p35b.build_batch_b(ctx, st, sub, st.tgt, lib, texts, spec, np.random.default_rng([0, 3, 0, 17, 3521]), rec)
    assert a[1:] == b[1:]
    for (xa, ta, sa), (xb, tb, sb) in zip(a[0], b[0]):
        assert sa == sb and np.array_equal(ta, tb) and np.allclose(xa, xb)


def test_config_specs():
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    specs = p35b.all_specs(cfg)
    assert set(cfg["candidates"]).isdisjoint(cfg["control"])
    assert all(s["steps"] == 4000 for s in specs.values())
    assert len({s["code"] for s in specs.values()}) == len(specs)
    assert cfg["gpu_cap_hours"] <= 8.0 and cfg["rules"]["val_margin"] == 0.03


def test_refuses_foreign_out():
    for f in ("p15-33", "p15-08", "p15-35"):
        assert p35b.main(["textpool", "--out", rf"C:\Users\zhang\bci-data\derived\{f}\x"]) == 2
