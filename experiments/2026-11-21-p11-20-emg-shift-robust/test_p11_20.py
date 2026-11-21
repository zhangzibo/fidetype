r"""P11-20 run.py helpers (CPU, synthetic data only): jobs, margin rule, decision rules, session list.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-20-emg-shift-robust/test_p11_20.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_20_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_20_run"] = m
    spec.loader.exec_module(m)
    return m


def sha(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def test_jobs_and_seeds(run):
    j1 = run.jobs(1)
    assert len(j1) == 81 and j1[0]["name"] == "R01" and j1[0]["seed"] == sha("p11-18|emg|cal|1")
    assert [j["name"] for j in j1[1:5]] == ["M01", "P41", "M02", "P42"]
    assert j1[1]["seed"] == sha("p11-20|emg|m|1") and j1[2]["seed"] == sha("p11-18|emg|cal|41")
    assert j1[-1]["name"] == "P80" and j1[-1]["seed"] == sha("p11-18|emg|cal|80")
    assert all(j["ltt_alpha"] == 0.05 for j in j1)
    j2 = run.jobs(2)
    assert [j["name"] for j in j2] == [f"S{k:02d}" for k in range(1, 41)]
    assert all(j["seed"] == sha(f"p11-18|emg|cal|{j['k']}") for j in j2)  # paired with P11-18 P01-P40
    assert [j["name"] for j in run.jobs(2, m_zero=True)] == ["S01"]


def test_margin_rule(run):
    r = run.margin_rule([0.01, 0.02, 0.012] * 10 + [0.0])
    assert r["run_arm_s"] and abs(r["m"] - (0.042 * 10) / 31) < 1e-12
    assert r["alpha_prime"] == 0.0364  # floor((0.05 - 0.013548...) * 1e4) / 1e4
    z = run.margin_rule([-0.01] * 35)
    assert z["m"] == 0.0 and z["alpha_prime"] == 0.05 and z["m_zero"]
    assert not run.margin_rule([0.01] * 29)["run_arm_s"]
    assert not run.margin_rule([0.06] * 40)["run_arm_s"]


def test_decision_rules(run):
    assert run.primary_conclusion(0) == run.primary_conclusion(1) == "margin removes the excess"
    assert run.primary_conclusion(2) == run.primary_conclusion(4) == "within delta, excess not removed"
    assert run.primary_conclusion(5) == "margin not enough"
    assert run.assumption_check(0.04, 4) == "(A) not contradicted on test"
    assert run.assumption_check(0.051, 0) == "(A) fails on test"
    assert run.assumption_check(0.03, 5) == "(A) fails on test"
    # plan tail values: 9 / 40 vs x / 80
    for x, p, c in ((6, 0.023, "duplicates"), (7, 0.038, "duplicates"), (8, 0.060, "partly duplicates"),
                    (9, 0.090, "noise + shift")):
        r = run.k80_conclusion(x)
        assert abs(r["fisher_b40_gt_p80"] - p) < 0.001 and r["conclusion"] == c


def test_mcnemar(run):
    a = [True, True, False, False, True]
    b = [False, True, False, True, False]
    r = run.mcnemar_exact(a, b)
    assert r["a_only"] == 2 and r["b_only"] == 1 and abs(r["p_two_sided"] - 1.0) < 1e-12
    assert run.mcnemar_exact([False] * 3, [False] * 3)["p_two_sided"] == 1.0


def test_session_ab(run):
    sp = {"test_users": ["u1", "u2"],
          "personal": {"u1": {"train": ["2020-01"], "val": ["2020-03", "2020-02"], "test": ["2020-04", "2020-05"]},
                       "u2": {"train": [], "val": ["2021-01", "2021-02"], "test": ["2021-03", "2021-04"]}}}
    ss = run.session_ab(sp)
    assert [(s["i"], s["j"], s["session"]) for s in ss] == [(0, "a", "2020-02"), (0, "b", "2020-03"),
                                                           (1, "a", "2021-01"), (1, "b", "2021-02")]
    bad = {"test_users": ["u"], "personal": {"u": {"val": ["2020-05", "2020-06"], "test": ["2020-04", "2020-07"]}}}
    with pytest.raises(AssertionError):
        run.session_ab(bad)
