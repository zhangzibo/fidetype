"""Tests of the opt-in group-aware calibration split (``calibrate(groups=...)``, fidetype.trust.dropin)."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from fidetype.trust import dropin as D
from test_trust_dropin import PHRASES, nbest_data, noise_nbest


def _guard(seed: int = 5, **kw):
    xs, ts = nbest_data(200, 3)
    rng = np.random.default_rng(9)
    nulls = [noise_nbest(rng) for _ in range(100)]
    return D.calibrate(xs, ts, null_inputs=nulls, seed=seed, null_trials=50, **kw), ts


def _digest(g, tmp_path) -> str:
    p = tmp_path / "g.json"
    g.save(p)
    body = json.loads(p.read_text(encoding="utf-8"))
    body["sheet"].pop("created_utc", None)  # the only field that changes from run to run
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def test_default_split_is_unchanged(tmp_path):
    """groups=None is the old path: same configuration id as before the option existed (value from the code at the
    parent commit) and the same guard file as a call without the argument."""
    g0, _ = _guard()
    g1, _ = _guard(groups=None)
    assert g0.config_id == g1.config_id == "tcfg-e2c493219795d790"
    assert _digest(g0, tmp_path) == _digest(g1, tmp_path)
    assert "group_aware" not in g0.config.recipe["split"]


def _parts(order, n_fit, n_pol):
    return order[:n_fit], order[n_fit:n_fit + n_pol], order[n_fit + n_pol:]


def test_group_split_keeps_groups_together_and_sizes_close():
    rng = np.random.default_rng(0)
    groups = [f"s{int(rng.integers(0, 300))}" for _ in range(1000)]  # many repeated sentences
    perm = np.random.default_rng(1).permutation(len(groups))
    order, n_fit, n_pol, n_ltt = D._group_split(perm, groups, 7)
    assert sorted(order.tolist()) == list(range(len(groups))) and n_fit + n_pol + n_ltt == len(groups)
    parts = _parts(order, n_fit, n_pol)
    sets = [{groups[i] for i in p} for p in parts]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    t = D._split(len(groups))
    biggest = max(groups.count(g) for g in set(groups))
    assert all(abs(a - b) <= biggest for a, b in zip((n_fit, n_pol, n_ltt), t))
    # inside a group, the items keep their order in the plain permutation
    pos = {int(i): k for k, i in enumerate(perm)}
    for g in list(set(groups))[:20]:
        mine = [int(i) for i in order if groups[int(i)] == g]
        assert mine == sorted(mine, key=lambda i: pos[i])


def test_group_split_deterministic_seeded_and_unique_groups_like_plain():
    groups = [f"g{i % 50}" for i in range(400)]
    perm = np.random.default_rng(3).permutation(400)
    a = D._group_split(perm, groups, 1)
    b = D._group_split(perm, groups, 1)
    c = D._group_split(perm, groups, 2)
    assert np.array_equal(a[0], b[0]) and a[1:] == b[1:] and not np.array_equal(a[0], c[0])
    uniq = [str(i) for i in range(400)]  # one item per group: the sizes are exactly the plain sizes
    assert D._group_split(perm, uniq, 1)[1:] == D._split(400)


def test_group_split_errors():
    perm = np.arange(10)
    with pytest.raises(ValueError):
        D._group_split(perm, ["a"] * 9, 0)  # length
    with pytest.raises(ValueError):
        D._group_split(perm, ["a"] * 5 + ["b"] * 5, 0)  # fewer than 3 groups


def test_calibrate_with_groups(tmp_path):
    xs, ts = nbest_data(200, 3)
    g0, _ = _guard()
    g, _ = _guard(groups=ts)  # the sentence text as the group: 10 phrases repeat about 20 times each
    sp = g.config.recipe["split"]
    assert sp["group_aware"] is True and sp["n_groups"] == len(set(ts)) <= len(PHRASES)
    assert sp["fit"] + sp["policy_grid"] + sp["ltt"] == 200 and g.config_id != g0.config_id
    # the same split, rebuilt from the same seed, has no group in two parts
    order, n_fit, n_pol, _ = D._group_split(np.random.default_rng(5).permutation(200), ts, 5)
    assert (n_fit, n_pol) == (sp["fit"], sp["policy_grid"])
    sets = [{ts[i] for i in p} for p in _parts(order, n_fit, n_pol)]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    with pytest.raises(ValueError):
        _guard(groups=ts[:-1])
