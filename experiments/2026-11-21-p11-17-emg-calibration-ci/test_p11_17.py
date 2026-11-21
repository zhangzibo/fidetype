r"""P11-17 run.py helpers (CPU, synthetic data only): draw order, cluster weights, combined interval.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-17-emg-calibration-ci/test_p11_17.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_17_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_17_run"] = m
    spec.loader.exec_module(m)
    return m


def test_draw_order_matches_calibrate_split(run):
    from fidetype.trust.dropin import _split

    n = 1224
    for seed, boot in ((0, None), (123, 456)):
        L, desired, info = run.draw_order(n, seed, boot)
        o = np.random.default_rng(seed).permutation(n)
        assert np.array_equal(L[o], desired)  # calibrate's item j = input L[o[j]]
        a, b, c = _split(n)
        assert info["split"] == [a, b, c] == [306, 459, 459]
        parts = [set(desired[:a]), set(desired[a:a + b]), set(desired[a + b:])]
        assert not (parts[0] & parts[1]) and not (parts[0] & parts[2]) and not (parts[1] & parts[2])
        if boot is None:
            assert sorted(desired.tolist()) == list(range(n))
        else:
            assert sum(info["distinct_per_part"]) < n  # resampling with replacement makes duplicates


def test_tuning_items_of_z0_equal_p1114(run):
    _, desired, _ = run.draw_order(1224, 0, None)
    order = np.random.default_rng(0).permutation(1224)
    assert sorted(desired[:765].tolist()) == sorted(order[:765].tolist())


def _toy(n=120, groups=6, seed=1):
    r = np.random.default_rng(seed)
    com = r.random(n) < 0.4
    cor = com & (r.random(n) < 0.85)
    nw = r.integers(2, 9, n)
    nch = nw * 5
    ns = r.uniform(3, 9, n)
    cl = [{"group": f"u{i % groups}"} for i in range(n)]
    return com, cor, nw, nch, ns, cl


def test_k1_equals_safe_wpm_cluster_ci(run):
    from fidetype.benchmark import safe_wpm as SW

    com, cor, nw, nch, ns, cl = _toy()
    g = {"alpha": 0.5, "delta": 0.1, "method": "ltt", "n_cal": 100}
    r = SW.safe_wpm(com.tolist(), cor.tolist(), nw, nch, ns, guarantee=g, clusters=cl, ci_unit="group",
                    B=500, seed=0)
    W = run.cluster_weights(cl, B_=500, seed=0)
    out = run.combined_interval([{"committed": com, "correct": cor, "value": r["unguarded_wpm"], "credited": True}],
                                nw, nch, ns, W, reference=None)
    assert np.allclose(out["interval"], r["ci"])
    assert out["value"] == pytest.approx(r["unguarded_wpm"])
    assert r["status"] == "certified"


def test_credit_rule_adds_zeros_and_verdicts(run):
    com, cor, nw, nch, ns, cl = _toy()
    W = run.cluster_weights(cl, B_=200, seed=0)
    good = {"committed": com, "correct": cor, "value": 5.0, "credited": True}
    bad = {"committed": com, "correct": cor, "value": 9.0, "credited": False}
    out = run.combined_interval([good] * 19 + [bad], nw, nch, ns, W, reference=1.0)
    assert out["n_credited"] == 19
    assert out["value"] == pytest.approx(5.0 * 19 / 20)
    assert out["zero_fraction_pooled"] >= 0.05
    assert out["interval"][0] == 0.0  # 5 % zeros -> the 2.5th percentile is 0.0
    assert out["verdict"] == "above, but inside the combined interval"
    assert run.verdict(5.0, 3.5, 3.09).startswith("clearly above")
    assert run.verdict(3.0, 0.0, 3.09) == "not above"


def test_seeds_are_fixed(run):
    js = run.jobs()
    assert js[0]["name"] == "z0" and js[0]["seed"] == 0 and js[0]["boot_seed"] is None
    assert len(js) == 41 and len({j["seed"] for j in js}) == 41
    assert js[1]["seed"] == int(__import__("hashlib").sha256(b"p11-17|emg|cal|1").hexdigest()[:8], 16)
