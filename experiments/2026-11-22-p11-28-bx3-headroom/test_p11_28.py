r"""P11-28 run.py helpers (CPU, synthetic data only): jobs and seeds, rules BXS / BX2, tail and headroom bounds.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-22-p11-28-bx3-headroom/test_p11_28.py
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
    spec = importlib.util.spec_from_file_location("p11_28_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_28_run"] = m
    spec.loader.exec_module(m)
    return m


def sha(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def test_constants_and_redirect(run):
    import os

    assert run.ALPHA_PP == 0.0314 and run.J == 3 and run.NO_BCI == 3.09 and run.DELTA == 0.1
    assert list(run.K_NEW) == list(range(41, 81)) and list(run.K_OLD) == list(range(1, 41))
    assert os.environ["P1119_OWN"] == str(run.OWN) and os.environ["P1119_OUT"] == str(run.OUT)
    assert run.OWN.name == "p11-28"


def test_jobs(run):
    x = run.jobs(1)
    assert [j["name"] for j in x] == ["XF01", "XF13", "R-k01-j2", "R-k13-j3"]
    assert x[0]["delta"] == 0.1 and x[0]["gname"] == "p11-23-S01" and x[0]["seed"] == sha("p11-18|emg|cal|1")
    assert math.isclose(x[2]["delta"], 0.1 / 3) and x[2]["seed"] == sha("p11-19|emg|split|1|2")
    assert x[3]["null_seed"] == sha("p11-18|emg|cal|13") and x[3]["gname"] == "p11-19-k13-j3"
    j2 = run.jobs(2)
    assert len(j2) == 120 and j2[0]["name"] == "k41-j1" and j2[-1]["name"] == "k80-j3"
    assert j2[0]["seed"] == sha("p11-18|emg|cal|41") and j2[1]["seed"] == sha("p11-19|emg|split|41|2")
    assert all(j["null_seed"] == sha(f"p11-18|emg|cal|{j['k']}") for j in j2)
    assert all(math.isclose(j["delta"], 0.1 / 3) and j["ltt_alpha"] == 0.0314 for j in j2)
    assert len({j["seed"] for j in j2}) == 120


def test_split_seed_matches_p11_19(run):
    spec = importlib.util.spec_from_file_location("p11_19_run_t", HERE.parent / "2026-11-21-p11-19-multi-split" / "run.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert all(run.split_seed(k, j) == m.split_seed(k, j) for k in (1, 13, 40, 41, 80) for j in (1, 2, 3))


def test_pick_rules(run):
    ok = [{"j": 1, "v_in": 5.0, "ltt_rate": 0.010}, {"j": 2, "v_in": 7.0, "ltt_rate": 0.020},
          {"j": 3, "v_in": 6.0, "ltt_rate": 0.015}]
    assert run.pick("BX3", ok)["j"] == 2
    assert run.pick("BXS", ok)["j"] == 3  # j2 has the highest ltt_rate (above the median 0.015): dropped
    assert run.pick("BX2", ok)["j"] == 2
    assert run.pick("BD3", ok)["j"] == 3
    assert run.pick("J1", ok)["j"] == 1
    two = [{"j": 1, "v_in": 5.0, "ltt_rate": 0.01}, {"j": 3, "v_in": 6.0, "ltt_rate": 0.03}]
    assert run.pick("BXS", two)["j"] == 1  # median 0.02: keep j1 only
    assert run.pick("BX2", two)["j"] == 1
    tie = [{"j": 1, "v_in": 5.0, "ltt_rate": 0.01}, {"j": 2, "v_in": 5.0, "ltt_rate": 0.01}]
    assert run.pick("BXS", tie)["j"] == 1 and run.pick("BX3", tie)["j"] == 1
    assert run.pick("BX3", []) is None and run.pick("BXS", []) is None and run.pick("BX2", [ok[2]]) is None
    with pytest.raises(ValueError):
        run.pick("XX", ok)


def test_bounds(run):
    assert math.isclose(run.cp_upper(0, 40), 1 - 0.05 ** (1 / 40), rel_tol=1e-9)
    assert run.cp_upper(3, 80) <= 0.1 < run.cp_upper(4, 80)
    assert run.cp_upper(5, 5) == 1.0
    assert run.quantile_rank(80) == 77 and run.quantile_rank(40) == 40
    assert run.headroom_label(0.006) == "clear headroom" and run.headroom_label(0.001) == "thin headroom"
    assert run.headroom_label(0.0) == "no headroom" and run.headroom_label(None) == "not computable"


def test_tail_stats(run):
    r = list(np.linspace(0.01, 0.045, 77)) + [0.051, 0.052, 0.06]
    t = run.tail_stats(r)
    assert t["n"] == 80 and t["f_above_alpha"] == 3 and t["cp_upper_le_delta"]
    assert t["q_rank"] == 77 and math.isclose(t["Q"], 0.045) and math.isclose(t["headroom"], 0.005)
    assert t["headroom_label"] == "clear headroom" and t["max"] == 0.06 and t["top5"][0] == 0.06
    assert t["above_ltt_alpha"] == sum(x > 0.0314 for x in r)
    assert 0.0 < t["normal_tail_p_above_alpha"] < 1.0


def test_cluster_fraction(run):
    wrong = np.zeros((2, 10), bool)
    wrong[0, :1] = True  # rate 0.1 with equal weights
    W = np.ones((3, 10))
    W[2, 0] = 0.0  # this weight vector removes the wrong prompt
    c = run.cluster_fraction(wrong, W)
    assert c["B"] == 3 and math.isclose(c["fraction_median"], 0.5) and math.isclose(c["p_fraction_gt_delta"], 2 / 3)
    assert math.isclose(c["max_rate_p95"], 0.1)


def test_overall_verdict(run):
    assert run.overall_verdict(True, "clear headroom") == "BX3 safety holds with headroom"
    assert run.overall_verdict(True, "thin headroom") == "the claim holds, but the headroom is thin"
    assert run.overall_verdict(False, "clear headroom") == "BX3 does not keep the claim with margin"
