"""Synthetic tests of the pooled-guard check helpers (no real data)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def _mod():
    if "pooled_run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("pooled_run", HERE / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["pooled_run"] = m
        spec.loader.exec_module(m)
    return sys.modules["pooled_run"]


def _data(seed: int = 0):
    rng = np.random.default_rng(seed)
    users = np.repeat(np.arange(4), 25)
    comm = rng.random(100) > 0.2
    p = np.array([0.1, 0.3, 0.5, 0.8])[users]
    right = comm & (rng.random(100) < p)
    return users, comm, right


def test_derangement_has_no_fixed_point():
    M = _mod()
    rng = np.random.default_rng(1)
    for n in (2, 3, 8):
        for _ in range(50):
            p = M.derangement(rng, n)
            assert sorted(p.tolist()) == list(range(n))
            assert not np.any(p == np.arange(n))
    with pytest.raises(ValueError):
        M.derangement(rng, 1)


def test_np_and_nw_keep_counts():
    M = _mod()
    users, comm, right = _data()
    rng = np.random.default_rng(2)
    y = M.null_labels("NP", right, comm, users, rng)
    assert y[comm].sum() == right[comm].sum()
    assert np.array_equal(y[~comm], right[~comm])
    y = M.null_labels("NW", right, comm, users, rng)
    for u in range(4):
        m = comm & (users == u)
        assert y[m].sum() == right[m].sum()  # each user's base rate is kept


def test_nx_moves_base_rates_to_other_users():
    M = _mod()
    users, comm, right = _data()
    rates = [right[comm & (users == u)].mean() for u in range(4)]
    rng = np.random.default_rng(3)
    moved = 0
    for _ in range(20):
        y = M.null_labels("NX", right, comm, users, rng)
        assert np.array_equal(y[~comm], right[~comm])
        new = [y[comm & (users == u)].mean() for u in range(4)]
        moved += sum(abs(a - b) > 1e-9 for a, b in zip(new, rates))
    assert moved > 0
    with pytest.raises(ValueError):
        M.null_labels("XX", right, comm, users, rng)


def test_build_texts_gives_the_labels():
    M = _mod()
    users = np.array([0, 0, 0, 1, 1, 1])
    truths = ["a b", "c d", "e f", "g h", "i j", "k l"]
    top1 = ["a b", "x", "e f", "y", "i j", ""]
    comm = np.array([True, True, True, True, True, False])
    right = np.array([M.same(t, tr) and c for t, tr, c in zip(top1, truths, comm)])
    new = np.array([False, True, True, True, False, False])
    out = M.build_texts(truths, top1, comm, right, new, users, np.random.default_rng(0))
    got = np.array([c and M.same(t, tr) for c, t, tr in zip(comm, top1, out)])
    assert np.array_equal(got, new & comm)
    assert out[5] == truths[5]  # not committable: unchanged
    assert out[0] in ("c d", "e f")  # a wrong truth from the same user


def test_cp_upper_and_r3():
    M = _mod()
    assert M.cp_upper(0, 36) <= 0.10 < M.cp_upper(0, 35)
    assert M.cp_upper(5, 5) == 1.0
    groups = [0] * 100 + [1] * 100
    commit = np.zeros(200, bool)
    commit[:20] = True
    wrong = np.zeros(200, bool)
    wrong[:12] = True  # group 0: 12 / 100 wrong
    r = M.r3(groups, commit, wrong)
    assert r["rule"] == "R3" and r["n_above"] == 1 and not r["passed"]
    r = M.r3(groups, commit, np.zeros(200, bool))
    assert r["passed"]


def test_r3b_permutation():
    M = _mod()
    groups = [g for g in range(10) for _ in range(10)]
    wrong = np.zeros(100, bool)
    wrong[:6] = True  # all wrong commits in one group
    p = M.max_rate_perm_p(groups, wrong, n_perm=2000)
    assert p < 0.01
    wrong2 = np.zeros(100, bool)
    wrong2[::17] = True  # spread
    assert M.max_rate_perm_p(groups, wrong2, n_perm=2000) > 0.05
    r = M.r3(groups, wrong, wrong)
    assert r["rule"] == "R3b" and not r["passed"]


def test_null_rules():
    M = _mod()
    mk = lambda c, k: [{"certified": c, "ltt_commits": k} for _ in range(20)]  # noqa: E731
    r = M.null_rules({"NX": mk(True, 5), "NW": mk(True, 5), "NP": mk(True, 5)}, "ltt_commits")
    assert not r["R1"] and r["R1_ref_applies"] and r["R2"] and r["null_pass"]
    nw = [{"certified": True, "ltt_commits": 30 + i} for i in range(20)]
    np_ = [{"certified": True, "ltt_commits": i} for i in range(20)]
    r = M.null_rules({"NX": mk(False, 0), "NW": nw, "NP": np_}, "ltt_commits")
    assert r["R1"] and not r["R2"] and not r["null_pass"]
