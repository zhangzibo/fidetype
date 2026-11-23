r"""P15-43 unit tests (toy numbers and temp folders only; no real data, no GPU).

Run (repo root):
  C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-23-p15-43-c2-30min/test_p43.py
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
import p43 as P  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CFG41 = json.loads((P.P41_DIR / "config.json").read_text(encoding="utf-8"))
RULES = CFG["rules"]


def test_recipe_unchanged_from_p15_41():
    for k in ("p15_33_config", "base_recipe", "frr20", "frr20_budgets", "text_pool", "synth"):
        assert CFG[k] == CFG41[k], k
    for k in ("c2_min_cer", "c2_min_gap", "val_margin", "length_guard", "shuffle_seed"):
        assert CFG["rules"][k] == CFG41["rules"][k], k
    assert CFG["gpu_cap_hours"] == 4.5 and CFG["arms"] == ["E"]
    assert [s["name"] for s in CFG["stages"]] == ["S30", "S3"]
    assert CFG["stages"][0]["seeds"] == [2, 3, 4] and not CFG["stages"][0]["stop_at_first_fail"]
    assert CFG["stages"][1]["seeds"] == [0, 1, 2, 3, 4] and CFG["stages"][1]["stop_at_first_fail"]


def test_sources_cover_every_seed():
    for b in ("3", "30"):
        for s in range(5):
            assert f"E-b{b}-s{s}" in CFG["sources"]["normal_test"]
    assert set(CFG["sources"]["old_deranged_test"]) == {"E-b30-s0-labelshuf", "E-b30-s1-labelshuf",
                                                        "E-b10-s2-labelshuf", "E-b10-s3-labelshuf",
                                                        "E-b10-s4-labelshuf"}


def test_bcfg_steps_and_aligner_root(tmp_path):
    ctx = P.make_ctx(HERE / "config.json", tmp_path, "cpu")
    for b, n in (("3", 1200), ("30", 4000)):
        c = P.P36.bcfg(CFG, b)
        assert c["candidates"][P.FR]["steps"] == n and c["candidates"][P.FR]["code"] == 3524
        for path in c["aligner_sources"].values():
            assert "p15-43" in path.replace("\\", "/")
        rec = P.B.run_recipe(P.P36.bctx(ctx, b), P.FR)
        assert rec.steps[b] == n and rec.warmup == 100
    assert ctx.rec.steps["3"] == 600 and ctx.rec.steps["30"] == 2000


def test_check_out():
    for p in ("p15-41", "p15-36", "p15-35b", "p15-33", "p15-08", "p15-35"):
        assert not P.check_out(Path(rf"C:\Users\zhang\bci-data\derived\{p}").resolve())
    assert not P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-41\x").resolve())
    assert P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-43").resolve())


def test_c2_row_rule():
    r = P.c2_row(0.765, 0.866, RULES)
    assert r["pass"] and abs(r["needed"] - 0.865) < 1e-12
    assert not P.c2_row(0.765, 0.864, RULES)["pass"]
    assert abs(P.c2_row(0.60, 0.75, RULES)["needed"] - 0.75) < 1e-12  # floor 0.75
    assert P.c2_row(0.60, 0.75, RULES)["pass"]
    assert P.c2_row(None, 0.9, RULES)["status"] == "missing" and not P.c2_row(0.7, None, RULES)["pass"]


def test_budget_status_smallest_and_outcome():
    ok = {"status": "done", "pass": True}
    bad = {"status": "done", "pass": False}
    seeds = [0, 1, 2, 3, 4]
    assert P.budget_status({str(s): ok for s in seeds}, seeds) == "pass"
    assert P.budget_status({**{str(s): ok for s in seeds}, "3": bad}, seeds) == "fail"
    assert P.budget_status({"0": bad, "1": {"status": "not_needed", "pass": False}}, seeds) == "fail"
    assert P.budget_status({str(s): ok for s in seeds[:4]}, seeds) == "not_determined"
    assert P.budget_status({"0": {"status": "not_run", "pass": False}, "2": bad}, seeds) == "fail"
    assert P.smallest_passing({"3": "fail", "10": "fail", "30": "pass"}) == "30"
    assert P.smallest_passing({"3": "pass", "10": "fail", "30": "pass"}) == "3"
    assert P.smallest_passing({"3": "fail", "10": "fail", "30": "fail"}) == "none"
    assert P.smallest_passing({"3": "not_determined", "10": "fail", "30": "pass"}) == "not_determined"
    assert P.outcome({"3": "fail", "10": "fail", "30": "pass"}) == "A"
    assert P.outcome({"3": "pass", "10": "fail", "30": "pass"}) == "B"
    assert P.outcome({"3": "fail", "10": "fail", "30": "fail"}) == "C"
    assert P.outcome({"3": "pass", "10": "fail", "30": "fail"}) == "D"
    assert P.outcome({"3": "fail", "10": "fail", "30": "not_determined"}) == "not_determined"


def _write(d: Path, cer: float, budget: str, ls: bool, done: bool = True) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text(json.dumps({"run": d.name, "test_cer_final": cer, "budget": budget,
                                               "label_shuffle": ls, "val_cer_final": cer}), encoding="utf-8")
    if done:
        (d / "DONE.json").write_text("{}", encoding="utf-8")


def _toy_ctx(tmp: Path, normal: dict, old_der: dict):
    cfg = json.loads(json.dumps(CFG))
    src = tmp / "src"
    cfg["sources"]["normal_test"] = {}
    cfg["sources"]["old_normal_10min"] = {}
    for (b, s), c in normal.items():
        name = f"E-b{b}-s{s}"
        _write(src / name, c, b, False)
        key = "old_normal_10min" if b == "10" else "normal_test"
        cfg["sources"][key][name] = str(src / name)
    cfg["sources"]["old_deranged_test"] = {}
    for (b, s), c in old_der.items():
        name = f"E-b{b}-s{s}-labelshuf"
        _write(src / name, c, b, True)
        cfg["sources"]["old_deranged_test"][name] = str(src / name)
    cp = tmp / "config.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    out = tmp / "out"
    out.mkdir()
    return P.make_ctx(cp, out, "cpu")


def test_stage_runs_sequential_rule_and_summary(tmp_path, monkeypatch):
    normal = {("30", s): 0.75 for s in range(5)}
    normal.update({("3", s): 0.80 for s in range(5)})
    normal.update({("10", s): 0.78 for s in (2, 3, 4)})
    old = {("30", 0): 0.88, ("30", 1): 0.87, ("10", 2): 0.85, ("10", 3): 0.84, ("10", 4): 0.79}
    ctx = _toy_ctx(tmp_path, normal, old)
    # toy deranged test CERs of the new runs: 30 min all pass; 3 min: seed 0 pass, seed 1 fails
    der = {("30", 2): 0.90, ("30", 3): 0.86, ("30", 4): 0.95, ("3", 0): 0.95, ("3", 1): 0.85}
    calls = []

    def fake_train(c, store, pool, arm, b, s, ls, max_steps=None):
        assert arm == "E" and ls is True
        calls.append((b, s))
        return {"val_cer_final": 0.9}

    def fake_test(c, store, arm, b, s, ls):
        d = P.P41.run_dir(c, arm, b, s, ls, "test")
        _write(d, der[(b, s)], b, True)
        return json.loads((d / "result.json").read_text(encoding="utf-8"))

    monkeypatch.setattr(P.P36, "train_one", fake_train)
    monkeypatch.setattr(P.P41, "test_one", fake_test)
    assert P.stage_runs(ctx, None, None) == "done"
    assert calls == [("30", 2), ("30", 3), ("30", 4), ("3", 0), ("3", 1)]  # S3 stops after the first fail
    st = json.loads((ctx.out / "stages.json").read_text(encoding="utf-8"))
    assert st["S3"]["seeds"]["2"]["status"] == "not_needed" and st["S3"]["seeds"]["4"]["status"] == "not_needed"
    # resume is a no-op
    calls.clear()
    assert P.stage_runs(ctx, None, None) == "done" and calls == []
    agg = P.stage_summary(ctx, "done", repo_results=None)
    assert agg["budget_status"] == {"3": "fail", "10": "fail", "30": "pass"}
    assert agg["smallest_passing_budget"] == "30" and agg["outcome"] == "A"
    assert agg["C2"]["10"]["0"]["status"] == "not_run" and agg["C2"]["10"]["4"]["pass"] is False
    assert agg["C2"]["30"]["0"]["pass"] and agg["C2"]["3"]["2"]["status"] == "missing"
    assert "test_edits_final" not in json.dumps(agg)


def test_stage_runs_partial_and_resume(tmp_path, monkeypatch):
    normal = {(b, s): 0.75 for b in ("3", "30") for s in range(5)}
    ctx = _toy_ctx(tmp_path, normal, {("30", 0): 0.9, ("30", 1): 0.9})
    n = {"k": 0}

    def fake_train(c, store, pool, arm, b, s, ls, max_steps=None):
        n["k"] += 1
        return {"partial": True} if n["k"] == 2 else {}

    def fake_test(c, store, arm, b, s, ls):
        d = P.P41.run_dir(c, arm, b, s, ls, "test")
        _write(d, 0.99, b, True)
        return json.loads((d / "result.json").read_text(encoding="utf-8"))

    monkeypatch.setattr(P.P36, "train_one", fake_train)
    monkeypatch.setattr(P.P41, "test_one", fake_test)
    assert P.stage_runs(ctx, None, None) == "partial"
    st = json.loads((ctx.out / "stages.json").read_text(encoding="utf-8"))
    assert list(st["S30"]["seeds"]) == ["2"]
    assert P.stage_runs(ctx, None, None) == "done"
    agg = P.stage_summary(ctx, "done", repo_results=None)
    assert agg["budget_status"]["30"] == "pass" and agg["budget_status"]["3"] == "pass"
    assert agg["smallest_passing_budget"] == "3" and agg["outcome"] == "B"
