r"""P11-19 run.py helpers (CPU, synthetic data only): jobs and seeds, selection rules, AND, why-not formulas, X1.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-19-multi-split/test_p11_19.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_19_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_19_run"] = m
    spec.loader.exec_module(m)
    return m


def sha(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def test_constants(run):
    assert run.ALPHA_PP == 0.0314 and run.J == 3 and math.isclose(run.SPLIT_DELTA, 0.1 / 3)
    assert run.NO_BCI == 3.09 and run.K == 40


def test_jobs_and_seeds(run):
    x = run.jobs(1)
    assert [j["name"] for j in x] == ["X01", "X13"]
    assert x[1]["seed"] == sha("p11-18|emg|cal|13") and x[1]["delta"] == 0.1 and x[1]["gname"] == "p11-23-S13"
    j2 = run.jobs(2)
    assert len(j2) == 120 and [j["name"] for j in j2[:4]] == ["k01-j1", "k01-j2", "k01-j3", "k02-j1"]
    assert j2[0]["seed"] == sha("p11-18|emg|cal|1")  # split 1 = the P11-18 / P11-23 partition
    assert j2[1]["seed"] == sha("p11-19|emg|split|1|2") and j2[2]["seed"] == sha("p11-19|emg|split|1|3")
    assert all(j["null_seed"] == sha(f"p11-18|emg|cal|{j['k']}") for j in j2)  # one user-null set per draw
    assert all(math.isclose(j["delta"], 0.1 / 3) and j["ltt_alpha"] == 0.0314 for j in j2)
    assert len({j["seed"] for j in j2}) == 120


def test_select(run):
    c = [{"j": 1, "v": 5.0}, {"j": 2, "v": 7.0}, {"j": 3, "v": 6.0}]
    assert run.select(c, "BX3")["j"] == 2
    assert run.select(c, "BD3")["j"] == 3
    tie = [{"j": 1, "v": 5.0}, {"j": 2, "v": 5.0}, {"j": 3, "v": 4.0}]
    assert run.select(tie, "BX3")["j"] == 1  # ties: lowest j
    assert run.select(tie, "BD3")["j"] == 1  # sorted (4, j3), (5, j1), (5, j2) -> median j1
    two = [{"j": 1, "v": 6.0}, {"j": 3, "v": 4.0}]
    assert run.select(two, "BD3")["j"] == 3  # two guards: the lower one
    assert run.select([{"j": 2, "v": 1.0}], "BD3")["j"] == 2
    assert run.select([], "BX3") is None
    with pytest.raises(ValueError):
        run.select(c, "XX")


def test_and_actions(run):
    same = lambda a, b: a.strip().lower() == b.strip().lower()  # noqa: E731
    d1 = [{"action": "commit", "text": "a b"}, {"action": "commit", "text": "x"}, {"action": "abstain", "text": None}]
    d2 = [{"action": "commit", "text": "A b"}, {"action": "commit", "text": "y"}, {"action": "commit", "text": "z"}]
    d3 = [{"action": "commit", "text": "a b"}, {"action": "commit", "text": "x"}, {"action": "commit", "text": "z"}]
    out = run.and_actions([d1, d2, d3], same)
    assert [o["action"] for o in out] == ["commit", "abstain", "abstain"]
    assert out[0]["text"] == "a b"


def test_why_not_formulas(run):
    assert math.isclose(run.floor_w(5.47, 1.23), 5.47 - 1.959963984540054 * 1.23)
    d = run.data_needed(6.0, 0.5, 1.2)
    h = (6.0 - 3.09) / 1.959963984540054
    assert math.isclose(d["n_users"], 8 * 1.44 / (h * h - 0.25))
    assert math.isclose(d["n_cal"], 1224 * 0.25 / (h * h - 1.44))
    d2 = run.data_needed(5.0, 1.0, 1.2)  # h = 0.974 < sd_b and < sd_w
    assert d2["n_users"] is None and d2["n_cal"] is None
    assert d2["n_users_note"] and d2["n_cal_note"]
    assert run.data_needed(3.0, 0.5, 1.0)["n_users"] is None


def test_h2(run):
    assert run.h2_conclusion(0) == run.h2_conclusion(1) == "multi-split keeps the excess removed"
    assert run.h2_conclusion(4) == "within delta"
    assert run.h2_conclusion(5) == "selection raises the risk"


def test_same_analysis_and_x1(run):
    a = {"status": "ok", "top": "t", "native": [("t", -1.0)], "sig": {"s": 0.5}}
    b = {"status": "ok", "top": "t", "native": [("t", -1.0 + 1e-12)], "sig": {"s": 0.5}}
    assert run.same_analysis(a, b, ["s"])
    assert not run.same_analysis(a, {**b, "native": [("t", -1.0 + 1e-6)]}, ["s"])
    assert run.same_analysis(None, None, ["s"]) and not run.same_analysis(a, None, ["s"])
    dec = {k: [{"action": "commit", "text": "t"}] for k in ("real", "shuffled", "zeros")}
    m = {"name": "X01", "threshold": 0.3, "n_commits": 1, "n_wrong": 0, "value": 2.0, "status": "guard",
         "safe_status": "certified", "model": {"digest": "abc"}, "decisions": dec}
    assert run.x1_compare(m, dict(m))["pass"]
    assert not run.x1_compare(m, {**m, "model": {"digest": "abd"}})["pass"]
    dec2 = {**dec, "zeros": [{"action": "abstain", "text": None}]}
    assert not run.x1_compare(m, {**m, "decisions": dec2})["pass"]
