r"""P11-23 run.py helpers (CPU, synthetic data only): jobs, step sizes, margin rule, decision rules, X6.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-23-shift-margin-steps/test_p11_23.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_23_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_23_run"] = m
    spec.loader.exec_module(m)
    return m


def sha(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def test_jobs_and_seeds(run):
    j1 = run.jobs(1)
    assert len(j1) == 80 and [j["name"] for j in j1[:4]] == ["A01", "B01", "A02", "B02"]
    assert j1[0]["seed"] == sha("p11-20|emg|m|1")  # rerun of P11-20 M01
    assert j1[1]["seed"] == sha("p11-23|emg|ba|1")
    assert all(j["ltt_alpha"] == 0.05 for j in j1)
    j2 = run.jobs(2)
    assert [j["name"] for j in j2] == [f"S{k:02d}" for k in range(1, 41)]
    assert all(j["seed"] == sha(f"p11-18|emg|cal|{j['k']}") for j in j2)
    assert [j["name"] for j in run.jobs(2, reuse_s=True)] == ["S01"]


def test_t_quantile(run):
    from scipy.stats import t

    assert abs(run.T_95_7 - t.ppf(0.95, 7)) < 1e-4


def test_user_counts_and_gaps(run):
    rows = [{"i": 0}, {"i": 0}, {"i": 1}, {"i": 1}, {"i": 1}]
    uc = run.user_counts(rows, [(True, True), (False, False), (True, False), (True, True), (False, False)])
    assert uc == {0: [2, 1, 1], 1: [3, 2, 1]}
    pu = {"0": {"L": [10, 5, 1], "Y": [20, 8, 4]}, "1": {"L": [10, 5, 0], "Y": [20, 8, 2]},
          "2": {"L": [20, 5, 2], "Y": [40, 8, 2]}}
    g = run.draw_gaps(pu)
    assert math.isclose(g["pooled"], 8 / 80 - 3 / 40)
    assert math.isclose(g["louo"]["0"], 4 / 60 - 2 / 30)
    assert math.isclose(g["louo"]["2"], 6 / 40 - 1 / 20)
    assert math.isclose(g["per_user"]["1"], 2 / 20 - 0 / 10)


def test_direction_steps_and_margin(run):
    rng = np.random.default_rng(0)
    gl = []
    for _ in range(40):
        pu = {str(u): {"L": [57, 20, int(rng.integers(0, 4))], "Y": [150, 40, int(rng.integers(0, 10))]}
              for u in range(8)}
        gl.append(run.draw_gaps(pu))
    st = run.direction_steps(gl)
    assert st["n_guard"] == 40 and len(st["louo"]) == 8 and len(st["per_user"]) == 8
    lv = np.array(st["louo"])
    assert math.isclose(st["se_jack"], math.sqrt(7 / 8 * np.sum((lv - lv.mean()) ** 2)))
    assert math.isclose(st["U"], st["s"] + run.T_95_7 * st["se_jack"])
    mg = run.margin_rule2({"A": {"n_guard": 40, "U": 0.012}, "B": {"n_guard": 40, "U": -0.003}})
    assert mg["run_arm_s2"] and mg["m2"] == 0.012 and mg["alpha_pp"] == 0.038 and not mg["reuse_p1120_s"]
    z = run.margin_rule2({"A": {"n_guard": 40, "U": -0.001}, "B": {"n_guard": 40, "U": -0.003}})
    assert z["m2"] == 0.0 and z["alpha_pp"] == 0.05
    r = run.margin_rule2({"A": {"n_guard": 40, "U": 0.0045}, "B": {"n_guard": 40, "U": 0.0}})
    assert r["alpha_pp"] == 0.0455 and r["reuse_p1120_s"]
    assert not run.margin_rule2({"A": {"n_guard": 29, "U": 0.01}, "B": {"n_guard": 40, "U": 0.0}})["run_arm_s2"]
    assert not run.margin_rule2({"A": {"n_guard": 40, "U": 0.05}, "B": {"n_guard": 40, "U": 0.0}})["run_arm_s2"]


def test_decision_rules(run):
    assert run.spread_verdict(0.0455) == run.spread_verdict(0.05) == "the one-step margin of P11-20 covers the spread"
    assert run.spread_verdict(0.0454) == "the one-step margin of P11-20 under-states the spread"
    assert run.primary_conclusion(1) == "margin removes the excess"
    assert run.primary_conclusion(4) == "within delta, excess not removed"
    assert run.primary_conclusion(5) == "margin not enough"
    assert run.assumption_check(0.04, 4) == "(A2) not contradicted on test"
    assert run.assumption_check(0.051, 0) == "(A2) fails on test"


def test_x6(run):
    ref = [{"status": "guard", "threshold": 0.5, "ltt_wrong": 3, "n_commits": 100, "n_wrong": 4}] * 40
    assert run.x6_check([dict(d) for d in ref], ref)["pass"]
    bad = [dict(d) for d in ref]
    bad[5]["n_wrong"] = 5
    x = run.x6_check(bad, ref)
    assert not x["pass"] and x["n_same"] == 39
