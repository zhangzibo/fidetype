"""CPU unit tests for the P15-50 wrapper: selection rule, pass rules, outcomes, run order, hooks (no data, no GPU)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import f3  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
RULES = CFG["rules"]


def test_config_matches_plan():
    s1 = CFG["stage1"]
    assert s1["lrs"] == [2.5e-4, 5e-4, 1e-3] and s1["steps"] == [3000, 6000] and s1["seeds"] == [10, 11]
    assert s1["arms"] == ["R", "E"] and s1["exclude_if_val_cer_above"] == 0.90
    assert CFG["stage2"]["seeds"] == [0, 1, 2, 3, 4]
    assert CFG["gpu_cap_hours"] == 45.0
    assert RULES["bootstrap_n"] == 10000 and RULES["bootstrap_seed"] == 0 and RULES["seed_ci_min_wins"] == 4
    assert RULES["c2_min_cer"] == 0.75 and RULES["c2_min_gap"] == 0.10 and RULES["c2_e_min_individual"] == 2
    assert RULES["c1_min_cer"] == 0.85 and RULES["c1_applies_if_cer_below"] == 0.70 and RULES["v1_max_cer"] == 0.50
    p = CFG["pretrain_I"]
    assert (p["steps"], p["lr"], p["warmup"], p["lr_min"], p["vocab"], p["n_in"]) == (30000, 1e-3, 2000, 1e-6, 41, 512)
    rec = json.loads((HERE.parent / "2026-11-19-p15-08-e1-cross-body" / "config.json").read_text(encoding="utf-8"))
    ft = rec["finetune"]
    assert (ft["warmup"], ft["lr_min"], ft["weight_decay"]) == (100, 1e-6, 0.01) and rec["trunk"]["dropout"] == 0.1
    assert "all" in rec["c1_budgets"]


def _cell(lr, steps, a, b):
    return {"lr": lr, "steps": steps, "val": {"10": a, "11": b}}


def test_select_lowest_mean_and_exclusion():
    cells = [_cell(2.5e-4, 3000, 0.5, 0.5), _cell(5e-4, 3000, 0.3, 0.95), _cell(1e-3, 6000, 0.45, 0.45)]
    c = f3.select_cell(cells, 0.90)
    assert (c["lr"], c["steps"]) == (1e-3, 6000)  # 0.3/0.95 cell is excluded (one seed > 0.90)


def test_select_ties():
    cells = [_cell(1e-3, 3000, 0.4, 0.4), _cell(5e-4, 6000, 0.4, 0.4), _cell(5e-4, 3000, 0.4, 0.4)]
    assert (f3.select_cell(cells, 0.9)["lr"], f3.select_cell(cells, 0.9)["steps"]) == (5e-4, 3000)
    assert f3.select_cell([_cell(1e-3, 3000, 0.9, 0.9)], 0.9)["lr"] == 1e-3  # 0.90 is not > 0.90


def test_select_all_excluded_raises():
    try:
        f3.select_cell([_cell(1e-3, 3000, 0.95, 0.2)], 0.9)
    except RuntimeError:
        return
    raise AssertionError("expected a stop")


def test_t_ci_4df():
    m, lo, hi = f3.t_ci([0.1, 0.2, 0.3, 0.4, 0.5])
    h = 2.7764451051977987 * np.std([0.1, 0.2, 0.3, 0.4, 0.5], ddof=1) / np.sqrt(5)
    assert abs(m - 0.3) < 1e-12 and abs(lo - (0.3 - h)) < 1e-12 and abs(hi - (0.3 + h)) < 1e-12


def _res(edits, ref):
    return {"test_edits_final": list(edits), "test_ref": list(ref), "test_cer_final": float(sum(edits) / sum(ref))}


def test_pair_rule_clear_win_and_swap():
    rng = np.random.default_rng(0)
    ref = rng.integers(20, 40, 80)
    runs = {}
    for s in range(5):
        runs[("E", s)] = _res((ref * 0.3).astype(int), ref)
        runs[("R", s)] = _res((ref * 0.6).astype(int), ref)
    h = f3.pair_rule("E", "R", runs, RULES, [0, 1, 2, 3, 4])
    assert h["pass"] and h["n_ci_above_0"] == 5 and h["mean_d"] > 0.25
    assert f3.pair_rule("R", "E", runs, RULES, [0, 1, 2, 3, 4])["pass"] is False


def test_pair_rule_needs_4_of_5_seeds():
    rng = np.random.default_rng(1)
    ref = rng.integers(20, 40, 80)
    runs = {}
    for s in range(5):
        runs[("E", s)] = _res((ref * 0.3).astype(int), ref)
        runs[("R", s)] = _res((ref * (0.6 if s < 3 else 0.3)).astype(int), ref)  # wins on 3 seeds only
    h = f3.pair_rule("E", "R", runs, RULES, [0, 1, 2, 3, 4])
    assert h["n_ci_above_0"] == 3 and h["part_a"] is False and h["pass"] is False


def test_pair_rule_missing_seed():
    ref = np.full(80, 30)
    runs = {("E", s): _res(ref // 3, ref) for s in range(5)}
    runs.update({("R", s): _res(ref // 2, ref) for s in range(4)})
    assert f3.pair_rule("E", "R", runs, RULES, [0, 1, 2, 3, 4])["status"] == "not_run"


def test_c2_e_three_runs():
    ok = f3.c2_seed(0.38, [0.80, 0.90, 0.70], RULES, 3)  # mean 0.80 >= 0.75, 2 of 3 individually
    assert ok["pass"] is True and ok["individual_pass"] == [True, True, False]
    bad = f3.c2_seed(0.38, [0.95, 0.74, 0.70], RULES, 3)  # mean 0.797 but only 1 of 3
    assert bad["pass"] is False
    bad2 = f3.c2_seed(0.70, [0.79, 0.79, 0.81], RULES, 3)  # needs 0.80: mean 0.797 fails
    assert bad2["pass"] is False
    assert f3.c2_seed(0.38, [0.9, None, 0.9], RULES, 3)["status"] == "missing"


def test_c2_single():
    assert f3.c2_seed(0.30, [0.75], RULES, 1)["pass"] is True
    assert f3.c2_seed(0.70, [0.79], RULES, 1)["pass"] is False


def test_c1_rows():
    rows = f3.c1_rows([{"run": "a", "test_cer_final": 0.4, "c1_shuffled_cer": 0.9},
                       {"run": "b", "test_cer_final": 0.71, "c1_shuffled_cer": 0.5},
                       {"run": "c", "test_cer_final": 0.70, "c1_shuffled_cer": 0.84}], RULES)
    assert [r["run"] for r in rows] == ["a", "c"] and [r["pass"] for r in rows] == [True, False]


def test_outcomes():
    P, F_ = {"pass": True}, {"pass": False}
    ok = {"E": True, "R": True}
    assert f3.outcome(True, {"H1": P, "H2": P, "H1swap": F_}, ok)["label"] == "A"
    assert f3.outcome(True, {"H1": F_, "H2": P, "H1swap": F_}, ok)["label"] == "B"
    assert f3.outcome(True, {"H1": F_, "H2": F_, "H1swap": P}, ok)["label"] == "C"
    assert f3.outcome(True, {"H1": F_, "H2": F_, "H1swap": F_, "H2swap": F_}, ok)["label"] == "D"
    assert f3.outcome(False, {"H1": P, "H2": P}, ok)["label"] == "N"
    assert f3.outcome(True, {"H1": P, "H2": P}, {"E": False, "R": True})["label"] == "N"
    assert f3.outcome(True, {"H1": F_, "H2": F_, "H1swap": P}, {"E": True, "R": False})["label"] == "N"


def test_stage2_order_and_counts():
    plan = f3.stage2_plan(CFG)
    assert len(plan) == 10 + 15 + 5 + 5 + 5 + 5
    groups = []
    for r in plan:
        if not groups or groups[-1] != r["group"]:
            groups.append(r["group"])
    assert groups == ["E+R+ normal", "E+ deranged", "R+ deranged", "T normal", "I normal", "I deranged"]
    ed = [r for r in plan if r["arm"] == "E" and r["deranged"]]
    assert sorted({(r["seed"], r["j"]) for r in ed}) == [(s, j) for s in range(5) for j in range(3)]
    assert len({(r["dir"], r["seed"], r["deranged"]) for r in plan}) == len(plan)  # no name clash
    assert not any(r["arm"] == "K" for r in plan)


def test_check_out(tmp_path):
    d = tmp_path / "derived"
    assert f3.check_out(d / "p15-50", d) and f3.check_out(d / "p15-50" / "s1", d)
    assert not f3.check_out(d / "p15-45", d) and not f3.check_out(d / "p15-08" / "runs", d)
    assert not f3.check_out(d, d) and f3.check_out(tmp_path / "scratch", d)


def test_derangement_hook():
    base = f3.e1.derangement(50, np.random.default_rng([3, 77]))
    with f3.derangement_rng(3, 0):
        j0 = f3.e1.derangement(50, np.random.default_rng([99, 99]))
    with f3.derangement_rng(3, 1):
        j1 = f3.e1.derangement(50, np.random.default_rng([3, 77]))
    assert np.array_equal(base, j0) and not np.array_equal(base, j1)
    assert not np.any(j1 == np.arange(50))
    assert np.array_equal(f3.e1.derangement(50, np.random.default_rng([3, 77])), base)  # restored


def test_i_trunk_transfer_keeps_head_new():
    trunk = f3.e1.TrunkCfg(d=32, dilations=(1, 2), vocab=98)
    pre = f3.i_model(trunk, 512, 41)
    assert pre.head.out_features == 41 and pre.stem.in_features == 512
    torch.manual_seed(5)
    tgt = f3.e1.XBody(trunk, "willett", 3)
    head0, stem0 = tgt.head.weight.clone(), tgt.stem.weight.clone()
    n = f3.load_trunk_no_head(tgt, pre.state_dict())
    assert n > 0
    assert torch.equal(tgt.blocks[0].state_dict()[next(iter(tgt.blocks[0].state_dict()))],
                       pre.blocks[0].state_dict()[next(iter(pre.blocks[0].state_dict()))])
    assert torch.equal(tgt.head.weight, head0) and torch.equal(tgt.stem.weight, stem0)


def test_selection_gate_fails_without_files(tmp_path):
    ok, why = f3.selection_committed(tmp_path)
    assert ok is False and why
