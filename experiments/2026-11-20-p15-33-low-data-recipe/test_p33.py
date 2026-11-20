"""P15-33 unit tests and CPU smoke run (synthetic data only; no real data, no GPU).

Run (repo root):
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -m pytest -q experiments/2026-11-20-p15-33-low-data-recipe/test_p33.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("scipy.io")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p33  # noqa: E402

sys.path.insert(0, str(p33.P8_DIR))
import test_e1 as T8  # noqa: E402  (P15-08 synthetic-data helpers)

e1, R8 = p33.e1, p33.R8


def make_cache(tmp: Path) -> Path:
    for i in range(2):
        T8.write_fake_session(tmp / "raw" / f"t5.2020.01.0{i}" / "sentences.mat", i)
    c8 = T8.small_ctx(tmp / "p8")
    R8.stage_prep(c8, tmp / "raw")
    return c8.cache


def small_ctx(tmp: Path, cache: Path) -> p33.Ctx:
    raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raw["common"] = {**raw["common"], "steps": {"0.2": 6, "all": 6}, "val_every": 3, "max_frames": 2000}
    raw["search"] = {**raw["search"], "budget": "0.2", "eligible_max_val_cer": 99.0}
    raw |= {"c1_budgets": ["all"], "c2": {"arm": "E", "budget": "0.2", "seed": 0}, "h_budgets": ["0.2"],
            "roadmap_rule_budgets": ["0.2"]}
    torch.manual_seed(5)
    e_ck = tmp / "e.pt"; torch.save({"model": e1.XBody(T8.SMALL, "text").state_dict()}, e_ck)
    torch.manual_seed(6)
    t_ck = tmp / "t.pt"; torch.save({"model": e1.XBody(T8.SMALL, "text").state_dict()}, t_ck)
    trunk = {"d": 32, "kernel": 5, "dilations": [1, 2], "ff_mult": 2, "dropout": 0.1, "vocab": 98, "conv_impl": "torch"}
    ctx = p33.Ctx(out=tmp / "out", cache=cache, raw=raw, device="cpu", trunk=trunk, e_ckpt=e_ck, text_ckpt=t_ck,
                  seeds=[0, 1], budgets=["0.2", "all"], arms=list(e1.ARMS), repo_results=tmp / "repo_results")
    ctx.out.mkdir(parents=True, exist_ok=True)
    return ctx


def test_recipes_from_config():
    raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    assert set(raw["candidates"]) == {"A", "B", "C", "D"}
    a, b = p33.recipe_from(raw, "A"), p33.recipe_from(raw, "B")
    assert not a.freeze_trunk and a.chan_drop == 0.2 and a.stretch_hi == 1.25 and a.steps["30"] == 2000
    assert b.freeze_trunk and b.chan_drop == 0.0 and b.time_masks == 2 and b.lr == 1e-3


def test_stretch():
    x = np.arange(20, dtype=np.float32)[:, None].repeat(3, 1)
    y = p33.stretch(x, 1.25)
    assert y.shape == (25, 3) and y[0, 0] == 0 and abs(y[-1, 0] - 19) < 1e-5 and np.all(np.diff(y[:, 0]) > 0)
    assert p33.stretch(x, 1.0).shape == (20, 3)
    assert p33.stretch(x, 0.8).shape == (16, 3)


def test_select_rule(tmp_path):
    ctx = small_ctx(tmp_path, tmp_path)
    ctx.raw["search"] = {**ctx.raw["search"], "budget": "30", "eligible_max_val_cer": 0.80}
    vals = {("A", "R"): (0.70, 0.85), ("A", "E"): (0.65, 0.70),   # A: R passes (0.85 >= 0.80); E fails
            ("B", "R"): (0.82, None), ("B", "E"): (0.60, 0.72),   # B: R not eligible; E fails (0.72 < 0.75)
            ("C", "R"): (0.68, 0.95), ("C", "E"): (0.66, 0.90),   # C: both pass, best 0.66
            ("D", "R"): (0.90, None), ("D", "E"): (0.79, 0.95)}   # D: E passes at 0.79
    for (c, a), (v, dv) in vals.items():
        d = p33.search_dir(ctx, c, a, "30", 0, False); d.mkdir(parents=True)
        e1.save_json({"val_cer_final": v, "val_shuffled_cer_final": 0.9, "best_val_cer": v,
                      "trainable_params": 10 if c in "BC" else 100}, d / "result.json")
        if dv is not None:
            d2 = p33.search_dir(ctx, c, a, "30", 0, True); d2.mkdir(parents=True)
            e1.save_json({"val_cer_final": dv}, d2 / "result.json")
    sel = p33.select(ctx)
    assert sel["selected"] == "C" and sel["selected_arm"] == "E"
    rows = {(r["candidate"], r["arm"]): r for r in sel["rows"]}
    assert rows[("A", "R")]["c2_val_pass"] and not rows[("A", "E")]["c2_val_pass"]
    assert not rows[("B", "R")]["eligible"] and not rows[("B", "E")]["c2_val_pass"]
    assert not any(k.startswith("test") for r in sel["rows"] for k in r)


def test_frozen_trunk_trains_only_stem_norm_head(tmp_path):
    cache = make_cache(tmp_path)
    ctx = small_ctx(tmp_path, cache)
    store = R8.WillettStore(cache)
    rec = p33.recipe_from(ctx.raw, "C")
    m0 = p33.init_model(ctx, store, rec, "E", 0)
    sd0 = {k: v.clone() for k, v in m0.state_dict().items()}
    trainable = {n for n, p in m0.named_parameters() if p.requires_grad}
    assert trainable and all(n.startswith(("stem.", "out_norm.", "head.")) for n in trainable)
    p33.train_run(ctx, store, rec, "E", "0.2", 0, False, tmp_path / "frz", do_test=False)
    sd1 = torch.load(tmp_path / "frz" / "final.pt", weights_only=True)["model"]
    assert all(torch.equal(sd0[k], sd1[k]) for k in sd0 if k.startswith("blocks."))
    assert not torch.equal(sd0["stem.weight"], sd1["stem.weight"])
    r = json.loads((tmp_path / "frz" / "result.json").read_text())
    assert "test_cer_final" not in r and "val_shuffled_cer_final" in r


def test_exact_resume_with_strong_aug(tmp_path):
    cache = make_cache(tmp_path)
    ctx = small_ctx(tmp_path, cache)
    store = R8.WillettStore(cache)
    rec = p33.recipe_from(ctx.raw, "A")
    p33.train_run(ctx, store, rec, "R", "0.2", 0, False, tmp_path / "straight", do_test=True)
    r1 = p33.train_run(ctx, store, rec, "R", "0.2", 0, False, tmp_path / "resumed", do_test=True, max_steps=4)
    assert r1 == {"partial": True, "step": 4}
    p33.train_run(ctx, store, rec, "R", "0.2", 0, False, tmp_path / "resumed", do_test=True)
    a = torch.load(tmp_path / "straight" / "final.pt", weights_only=True)["model"]
    b = torch.load(tmp_path / "resumed" / "final.pt", weights_only=True)["model"]
    assert all(torch.allclose(a[k], b[k], atol=1e-6) for k in a)
    la = (tmp_path / "straight" / "metrics.jsonl").read_text().splitlines()
    lb = (tmp_path / "resumed" / "metrics.jsonl").read_text().splitlines()
    assert la == lb


def test_cpu_smoke_search_select_grid_summary(tmp_path):
    cache = make_cache(tmp_path)
    ctx = small_ctx(tmp_path, cache)
    store = R8.WillettStore(cache)
    assert p33.stage_search(ctx, store)
    # Search never computes a test number.
    for p in (ctx.out / "search").rglob("result.json"):
        assert "test_cer_final" not in json.loads(p.read_text())
    sel = p33.select(ctx)
    if sel["selected"] is None:  # random tiny models may fail the rule: force a choice for the smoke test
        sel = {**sel, "selected": "B", "selected_arm": "R"}
    assert p33.stage_grid(ctx, store, sel)
    agg = p33.stage_summary(ctx, sel)
    assert {"V1", "H1", "H2", "H3", "H4", "C1", "C2", "C2_all", "curve", "roadmap_rule"} <= set(agg)
    s = json.loads((ctx.repo_results / "summary.json").read_text(encoding="utf-8"))
    assert "test_edits_final" not in json.dumps(s["runs"])
    n_c2 = 1 + (sel["selected_arm"] != "E")
    assert len(s["runs"]) == 2 * 2 * 4 + n_c2 and len(s["C2_all"]) == n_c2
    lic = json.loads((ctx.out / "grid" / "T-ball-s1" / "licence.json").read_text())
    assert lic["research_only"] is True and lic["recipe"] == sel["selected"]


def test_refuses_p15_08_folder(tmp_path):
    assert p33.main(["select", "--out", str(p33.P8_OUT / "x")]) == 2
