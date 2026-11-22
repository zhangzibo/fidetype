"""Synthetic tests for the new P11-21 logic (no emg2qwerty data is read)."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def _mod():
    if "p1121run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1121run", HERE / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1121run"] = m
        spec.loader.exec_module(m)
    return sys.modules["p1121run"]


def test_p16_writes_redirected():
    m = _mod()
    P = m.p16()
    assert P.OWN == m.OWN and P.OUT == m.OUT
    assert P.own("x.json").parent == m.OWN


def test_jobs_seeds_match_prior_items():
    m = _mod()
    js = m.jobs(1)
    assert [j["name"] for j in js[:4]] == ["X01", "X07", "A01", "B01"]
    p16 = m.p16().jobs()
    assert js[0]["seed"] == p16[1]["seed"] and js[0]["boot_seed"] == p16[1]["boot_seed"]
    assert js[1]["seed"] == p16[7]["seed"] and js[1]["boot_seed"] == p16[7]["boot_seed"]
    p23 = m.p23().jobs(1)
    a = {j["name"]: j["seed"] for j in js}
    for j in p23:
        assert a[j["name"]] == j["seed"]
    assert sum(j["arm"] in "AB" for j in js) == 80
    mg = {"run_arm_m": True, "alpha_lx": 0.035}
    j2 = m.jobs(2, mg)
    s23 = m.p23().jobs(2)
    assert len(j2) == 120
    assert [j["seed"] for j in j2 if j["arm"] == "M"] == [j["seed"] for j in s23]
    assert {j["ltt_alpha"] for j in j2 if j["arm"] == "M"} == {0.035}
    assert {j["ltt_alpha"] for j in j2 if j["arm"] == "T"} == {0.0314}


def test_arm_plan_reuse():
    m = _mod()
    assert m.arm_plan({"run_arm_m": True, "alpha_lx": 0.0314}) == {"run": ["M", "P"], "reuse": {"T": "M"}}
    assert m.arm_plan({"run_arm_m": True, "alpha_lx": 0.05}) == {"run": ["M", "T"], "reuse": {"P": "M"}}
    assert m.arm_plan({"run_arm_m": True, "alpha_lx": 0.04}) == {"run": ["M", "P", "T"], "reuse": {}}
    assert m.arm_plan({"run_arm_m": False}) == {"run": ["P", "T"], "reuse": {}}


def test_margin_rule():
    m = _mod()
    d = {"A": {"n_guard": 40, "U": 0.012}, "B": {"n_guard": 35, "U": 0.004}}
    r = m.margin_rule_lx(d)
    assert r["run_arm_m"] and r["m_lx"] == 0.012 and r["alpha_lx"] == 0.038
    r = m.margin_rule_lx({"A": {"n_guard": 40, "U": -0.01}, "B": {"n_guard": 40, "U": -0.002}})
    assert r["m_lx"] == 0.0 and r["alpha_lx"] == 0.05
    assert not m.margin_rule_lx({"A": {"n_guard": 29, "U": 0.0}, "B": {"n_guard": 40, "U": 0.0}})["run_arm_m"]
    assert not m.margin_rule_lx({"A": {"n_guard": 40, "U": 0.06}, "B": {"n_guard": 40, "U": 0.0}})["run_arm_m"]
    r = m.margin_rule_lx({"A": {"n_guard": 40, "U": 0.01855}, "B": {"n_guard": 40, "U": 0.0}})
    assert r["alpha_lx"] == 0.0314


def test_verdicts():
    m = _mod()
    assert m.h1_verdict(7.0, 3.2, True) == "clearly above after calibration uncertainty"
    assert m.h1_verdict(7.0, 3.2, False) == "above, but inside the combined interval"
    assert m.h1_verdict(7.0, 3.0, True) == "above, but inside the combined interval"
    assert m.h1_verdict(3.0, 0.0, True) == "not above"
    assert [m.h2_conclusion(f) for f in (0, 1, 2, 4, 5)] == ["margin removes the excess"] * 2 + [
        "within delta, excess not removed"] * 2 + ["margin not enough"]
    assert m.a2_check(0.04, 4) == "(A2) not contradicted on test"
    assert m.a2_check(0.051, 0) == "(A2) fails on test"
    assert m.fisher_less(7, 0) < 0.01 and m.fisher_less(7, 7) > 0.5


def test_commit_flags_prefix_rule():
    m = _mod()
    decs = [{"action": "commit", "text": "the cat", "complete": False},
            {"action": "commit", "text": "the cat", "complete": True},
            {"action": "commit", "text": "a dog", "complete": False},
            {"action": "offer", "text": None, "complete": None}]
    t = ["the cat sat", "the cat sat", "the cat", "x"]
    assert m.commit_flags(decs, t) == [(True, False), (True, True), (True, True), (False, False)]


def test_prompt_weights_match_library_scheme():
    m = _mod()
    W = m.prompt_weights(7, B=5, seed=0)
    rng = np.random.default_rng(0)
    for b in range(5):
        assert np.array_equal(W[b], np.bincount(rng.integers(0, 7, 7), minlength=7))
    assert np.all(W.sum(1) == 7)


def test_certify_at_equals_p16_at_alpha():
    m = _mod()
    P = m.p16()
    rng = np.random.default_rng(3)
    items = []
    for i in range(400):
        nw = int(rng.integers(1, 5))
        words = [f"w{j}" for j in range(nw)]
        truth = list(words)
        if rng.random() < 0.15:
            truth[int(rng.integers(0, nw))] = "zz"
        items.append(({"top": " ".join(words), "s": np.sort(rng.random(nw))[::-1]}, " ".join(truth)))

    class Fake:
        def mono(self, a):
            return a["s"]

    r1 = m.certify_at(Fake(), items, 0.05)
    r2 = P.certify(Fake(), None, items)
    assert r1 == r2 or (math.isinf(r1["threshold"]) and math.isinf(r2["threshold"]))
    r3 = m.certify_at(Fake(), items, 0.0314)
    assert (r3["threshold"] >= r1["threshold"]) or math.isinf(r3["threshold"])


def test_step_gap_helpers_from_p23():
    m = _mod()
    rows = [{"i": 1}, {"i": 1}, {"i": 2}]
    uc = m.p23().user_counts(rows, [(True, True), (True, False), (False, False)])
    assert uc == {1: [2, 2, 1], 2: [1, 0, 0]}
    _ = SimpleNamespace  # keep import used


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
