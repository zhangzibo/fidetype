r"""P11-18 run.py helpers (CPU, synthetic data only): jobs, pool split, binomial bound, decision rule.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-18-emg-above-alpha/test_p11_18.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_18_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_18_run"] = m
    spec.loader.exec_module(m)
    return m


def test_jobs_and_seeds(run):
    js = run.jobs()
    assert len(js) == 81 and js[0]["name"] == "z0" and js[0]["seed"] == 0
    assert [j["name"] for j in js[1:5]] == ["P01", "E01", "P02", "E02"]
    assert len({j["seed"] for j in js}) == 81
    assert js[1]["seed"] == int(hashlib.sha256(b"p11-18|emg|cal|1").hexdigest()[:8], 16)
    assert js[2]["pool_seed"] == int(hashlib.sha256(b"p11-18|emg|pool|1").hexdigest()[:8], 16)
    # round robin over 4 workers covers every job once
    assert sorted(i for w in range(4) for i in range(81) if i % 4 == w) == list(range(81))


def test_partition_only_order_has_no_duplicates(run):
    _, desired, info = run.p17().draw_order(1224, run.jobs()[1]["seed"], None)
    assert sorted(desired.tolist()) == list(range(1224))
    assert info["distinct_per_part"] == [306, 459, 459]


def test_pool_split(run):
    ci, hi = run.pool_split(1224, 1221, 12345)
    assert len(ci) == 1224 and len(hi) == 1221
    assert sorted(np.concatenate([ci, hi]).tolist()) == list(range(2445))
    assert 400 < int(np.sum(ci < 1224)) < 824  # mixed sessions


def test_binom_bound_and_above_alpha(run):
    assert run.binom_sig_bound() == 75
    assert run.above_alpha(62, 1221) and not run.above_alpha(61, 1221)


def test_p1117_counts(run):
    wb = run.p1117_wrong()
    assert len(wb) == 40 and sum(w / 1221 > 0.05 for w in wb) == 9 and max(wb) == 76


def test_decision_rule(run):
    r = np.random.default_rng(0)
    same = r.normal(0.0, 0.005, 40)
    shifted = same + 0.01
    d = run.decide_cause(9, 1, 1, same, same, 0)
    assert d["step1"] == "duplicates" and d["fisher_b_gt_p"] < 0.05
    assert d["sentence"] == "The excess over delta comes from duplicates."
    assert run.decide_cause(9, 3, 1, same, same, 0)["step1"] == "partly duplicates"
    assert run.decide_cause(9, 4, 1, same, same, 0)["step1"] == "partly duplicates"
    d = run.decide_cause(9, 8, 2, shifted, same, 1)
    assert d["step1"] == "noise + shift" and d["step2"] == "mainly session shift"
    assert d["sentence"].endswith("sub-cause: mainly session shift.")
    assert run.decide_cause(9, 8, 6, shifted, same, 1)["step2"] == "shift and noise"
    d = run.decide_cause(9, 8, 7, same, same, 3)
    assert d["step2"] == "mainly test-rate noise"
    assert d["step3"] == "exceedances larger than test noise explains"
    assert run.decide_cause(9, 8, 7, same, same, 2)["step3"] == "consistent with test-rate noise around alpha"
    assert run.fisher_greater(9, 2) == pytest.approx(0.0238, abs=1e-4)
