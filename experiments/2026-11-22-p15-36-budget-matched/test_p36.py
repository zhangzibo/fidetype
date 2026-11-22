r"""P15-36 unit tests (toy numbers and temp folders only; no real data, no GPU).

Run (repo root):
  C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-22-p15-36-budget-matched/test_p36.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import pytest

torch = pytest.importorskip("torch")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p36 as P  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def ctx_in(tmp: Path, cfg: dict | None = None) -> P.L.Ctx35:
    c = P.make_ctx(HERE / "config.json", tmp, "cpu", repo_results=None)
    if cfg is not None:
        c.cfg = cfg
    return c


def test_bcfg_steps_and_code():
    for b, n in (("3", 1200), ("10", 2000), ("30", 4000)):
        c = P.bcfg(CFG, b)
        spec = c["candidates"][P.FR]
        assert c["budget"] == b and spec["steps"] == n
        assert spec["code"] == 3524 and spec["mode"] == "replace" and spec["synth_frac"] == 0.2
        assert spec["align"] == "forced" and c["control"] == {}
    with pytest.raises(ValueError):
        P.bcfg(CFG, "100")


def test_recipe_steps_via_p35b(tmp_path):
    ctx = ctx_in(tmp_path)
    for b, n in (("3", 1200), ("10", 2000), ("30", 4000)):
        rec = P.B.run_recipe(P.bctx(ctx, b), P.FR)
        assert rec.steps[b] == n and rec.warmup == 100 and rec.weight_decay == 0.05 and rec.dropout == 0.3


def test_train_list_order_and_reuse():
    tl = P.train_list(CFG)
    assert len(tl) == 23
    assert ("E", "30", 0) not in tl
    assert tl[0] == ("R", "3", 0) and tl[-1] == ("S", "30", 1)
    assert [t[2] for t in tl] == sorted(t[2] for t in tl)


def test_aligner_map_paths():
    m = P.aligner_map(CFG)
    assert len(m) == 24
    assert m["T-b3-s1"].replace("\\", "/").endswith("p15-33/grid/T-b3-s1/final.pt")
    assert "E-b30-s1-labelshuf" not in m


def test_check_out():
    assert not P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-35b").resolve())
    assert not P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-08\x").resolve())
    assert P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-36").resolve())


def vals_fixture(fr=(0.85, 0.78, 0.74), a=(0.82, 0.79, 0.77, 0.80, 0.90), e=(0.90, 0.88, 0.80, 0.77, 0.40)):
    v = {}
    for k, b in enumerate(CFG["budgets_min"]):
        if k < 3:
            v[("F-R20", b)] = [fr[k]] * 8
        v[("A", b)] = [a[k]] * 8
        v[("E1a", b)] = [e[k]] * 8
    return v


def c2_fixture(fr_ok=True, a_ok=False, e_ok=False, guard=True):
    return {"F-R20": {"normal": 0.745, "deranged": 0.897 if fr_ok else 0.86,
                      "median_normal": 87.0, "median_deranged": 64.0 if guard else 40.0},
            "A": {"normal": 0.769, "deranged": 0.95 if a_ok else 0.871},
            "E1a": {"normal": 0.70, "deranged": 0.90 if e_ok else 0.75}}


def test_select_rule_basic():
    s = P.select_rule(vals_fixture(), c2_fixture(), CFG)
    assert s["chosen"] == {"3": "A", "10": "F-R20", "30": "F-R20", "100": "E1a", "all": "E1a"}
    assert not s["no_recipe"]
    c2 = s["val_c2_30min_arm_E_seed0"]
    assert c2["F-R20"]["val_c2_with_margin_pass"] and abs(c2["F-R20"]["needed_with_margin"] - 0.875) < 1e-9
    assert not c2["A"]["val_c2_with_margin_pass"]


def test_select_rule_admissibility_only_at_30():
    # E1a has the lowest val CER at 30 min but fails val-C2: F-R20 is chosen there; at 3 min no condition.
    s = P.select_rule(vals_fixture(fr=(0.9, 0.9, 0.80), e=(0.5, 0.88, 0.70, 0.77, 0.40)), c2_fixture(), CFG)
    assert s["chosen"]["30"] == "F-R20" and s["chosen"]["3"] == "E1a"


def test_select_rule_guard_and_no_recipe():
    s = P.select_rule(vals_fixture(), c2_fixture(guard=False), CFG)
    assert s["chosen"]["30"] is None and s["no_recipe"]
    assert not s["val_c2_30min_arm_E_seed0"]["F-R20"]["length_guard_pass"]


def test_select_rule_tie_order():
    s = P.select_rule(vals_fixture(fr=(0.8, 0.8, 0.8), a=(0.8, 0.8, 0.8, 0.8, 0.8), e=(0.8,) * 5),
                      c2_fixture(a_ok=True, e_ok=True), CFG)
    assert s["chosen"]["3"] == "F-R20" and s["chosen"]["30"] == "F-R20" and s["chosen"]["all"] == "A"


def test_select_reads_no_test_numbers(tmp_path):
    """The loaders used by the rule must not need any test key."""
    root = tmp_path / "e1a"
    cfg = json.loads(json.dumps(CFG))
    cfg["sources"]["E1a_runs"] = str(root)
    d = root / "E-b10-s0"
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"steps": 800, "budget": "10", "arm": "E", "seed": 0}), encoding="utf-8")
    (d / "metrics.jsonl").write_text("".join(json.dumps({"step": s, "val_cer": 1.0 - s / 1e4}) + "\n"
                                             for s in (100, 700, 800)), encoding="utf-8")
    r = P.e1a_result(cfg, "E", "10", 0)
    assert abs(r["val_cer_final"] - 0.92) < 1e-12
    (d / "metrics.jsonl").write_text(json.dumps({"step": 700, "val_cer": 0.5}) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        P.e1a_result(cfg, "E", "10", 0)


def test_test_readout_needs_selection(tmp_path):
    ctx = ctx_in(tmp_path)
    with pytest.raises(RuntimeError):
        P.frr20_test(ctx, None, "R", "3", 0)


def test_rule_verdict_assembly(tmp_path, monkeypatch):
    ctx = ctx_in(tmp_path)
    seen = []

    def fake(ctx_, store, cand, arm, budget, seed, ls=False):
        seen.append((cand, arm, budget, seed, ls))
        base = {"R": 0.9, "T": 0.85, "E": 0.7, "S": 0.88}[arm] - (0.3 if budget == "all" else 0.0)
        cer = base + 0.01 * seed + (0.2 if ls else 0.0)
        n = 80
        return {"run": P.R8.run_name(arm, budget, seed, ls), "arm": arm, "budget": budget, "seed": seed,
                "label_shuffle": ls, "minutes": 1.0, "test_cer_final": cer, "test_ref": [10] * n,
                "test_edits_final": [cer * 10] * n}

    monkeypatch.setattr(P, "test_result", fake)
    chosen = {"3": "F-R20", "10": "F-R20", "30": "F-R20", "100": "E1a", "all": "E1a"}
    v = P.rule_verdict(ctx, None, chosen)
    assert len(seen) == 41 and seen[-1] == ("F-R20", "E", "30", 0, True)
    assert all(c == chosen[b] for c, _, b, _, _ in seen)
    assert v["V1"]["pass"] and v["H2"]["status"] == "pass" and v["C2"]["pass"]
    assert v["recipes"] == chosen
