"""Tests of the opt-in multi-user check and per-user bound (``calibrate(users=...)``, P5-42)."""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import dropin as D
from fidetype.trust import user_check as U
from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits, nbest_data, noise_nbest


def _digest(g, tmp_path) -> str:
    p = tmp_path / "g.json"
    g.save(p)
    body = json.loads(p.read_text(encoding="utf-8"))
    body["sheet"].pop("created_utc", None)
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def _nb_guard(**kw):
    xs, ts = nbest_data(200, 3)
    rng = np.random.default_rng(9)
    nulls = [noise_nbest(rng) for _ in range(100)]
    return D.calibrate(xs, ts, null_inputs=nulls, seed=5, null_trials=50, **kw), xs, ts


# --- synthetic multi-user data (the generator of experiments/2026-11-25-p5-42-per-user-null/synth.py) -----------


def _item(rng, right: bool, conf: float):
    truth = str(rng.choice(PHRASES))
    others = [str(p) for p in rng.choice([p for p in PHRASES if p != truth], size=3, replace=False)]
    top = truth if right else others[0]
    rest = [others[0] if right else truth, others[1], others[2]]
    gap = 0.5 + 6.0 * float(np.clip(conf, 0.0, 1.0))
    return [(top, 0.0)] + [(t, float(-gap * rng.uniform(0.8, 1.2))) for t in rest], truth


def _users_data(case: str, seed: int, m: int, k: int = 4):
    rng = np.random.default_rng(seed)
    xs, ts, us = [], [], []
    for u in range(k):
        for _ in range(m):
            if case == "leak":  # B1 type: the margin and the base rate depend on the user only
                b = np.linspace(0.2, 0.95, k)[u]
                conf, right = b + rng.normal(0.0, 0.05), rng.random() < b
            else:  # within-user signal, no user effect ("bad": the last user is overconfident)
                z = rng.uniform(0.2, 1.0)
                conf, right = z, rng.random() < (0.6 * z if (case == "bad" and u == k - 1) else z)
            x, t = _item(rng, bool(right), float(conf))
            xs.append(x)
            ts.append(t)
            us.append(f"user-{u}")
    perm = rng.permutation(len(xs))
    nulls = [[(str(p), float(-rng.uniform(0.0, 0.5))) for p in rng.choice(PHRASES, size=4, replace=False)]
             for _ in range(100)]
    return [xs[i] for i in perm], [ts[i] for i in perm], [us[i] for i in perm], nulls


def _cal(case: str, seed: int = 11, m: int = 200, **kw):
    xs, ts, us, nulls = _users_data(case, seed, m)
    return ft.calibrate(xs, ts, users=us, null_inputs=nulls, null_trials=60, seed=seed, **kw), xs, ts, us


@pytest.fixture(scope="module")
def leak():
    return _cal("leak")


@pytest.fixture(scope="module")
def signal():
    return _cal("signal")


# --- opt-in: old calls do not change -------------------------------------------------------------------------


def test_config_ids_pinned_to_the_parent_commit(tmp_path):
    """Values from the code at 83da5d1 (before users= existed)."""
    g0, _, _ = _nb_guard()
    g1, _, _ = _nb_guard(users=None)
    assert g0.config_id == g1.config_id == "tcfg-e2c493219795d790"
    assert _digest(g0, tmp_path) == _digest(g1, tmp_path)
    assert "users" not in g0.sheet.to_dict() and g0.sheet.users is None
    gl, _, _ = _nb_guard(confidence="learned")
    assert gl.config_id == "tcfg-d1895d8b176cdc20"
    rng = np.random.default_rng(3)
    t2 = [str(rng.choice(PHRASES)) for _ in range(200)]
    gx = ft.calibrate([fake_logits(t, rng) for t in t2], t2, vocab=VOCAB, blank="_", lexicon=LEXICON,
                      null_trials=40, decoder_name="test-ctc")
    assert gx.config_id == "tcfg-320799cb7f75e253"


@pytest.mark.parametrize("conf", ["p_top1", "learned"])
def test_check_changes_no_decision_and_no_config_id(conf, tmp_path):
    g0, xs, ts = _nb_guard(confidence=conf)
    users = [i % 4 for i in range(len(xs))]
    g, _, _ = _nb_guard(confidence=conf, users=users)
    assert g.config_id == g0.config_id and g.sheet.commit_threshold == g0.sheet.commit_threshold
    assert [g._decide_quiet(x).action for x in xs] == [g0._decide_quiet(x).action for x in xs]
    u = g.sheet.users
    assert u["n_users"] == 4 and u["bound"] == "pooled" and "per_user" not in u
    # the score-level view reproduces the guard's own LTT step (p_top1: lambda_hat, before the max with the
    # policy-grid threshold; learned: the certified threshold and the in-sample commits)
    if conf == "learned":
        assert u["check"]["real_threshold"] == g.commit_score.threshold
        assert u["check"]["real_commits"] == g.sheet.ltt_commits
    else:
        assert u["check"]["real_threshold"] == g.sheet.lambda_hat
        assert u["check"]["real_commits"] >= g.sheet.ltt_commits
    # the block is saved and loaded with the guard; the sheet text names it
    p = tmp_path / "g.json"
    g.save(p)
    assert ft.load(p).sheet.users == json.loads(json.dumps(u))
    assert "user check" in str(g.sheet)
    off, _, _ = _nb_guard(confidence=conf, users=users, user_check="off")
    assert "check" not in off.sheet.users and off.config_id == g0.config_id


def test_users_and_groups_are_separate_options():
    g0, xs, ts = _nb_guard(groups=nbest_data(200, 3)[1])
    g, _, _ = _nb_guard(groups=ts, users=[i % 3 for i in range(len(xs))])
    assert g.config_id == g0.config_id and g.config.recipe["split"] == g0.config.recipe["split"]


# --- (a) the user-identity label null --------------------------------------------------------------------------


def test_b1_type_leak_is_flagged(leak):
    g = leak[0]
    c = g.sheet.users["check"]
    assert c["real_commits"] >= 1 and c["verdict"] == "fail" and c["p_user"] > U.P_USER_MAX
    assert c["nw_commits_median"] > c["np_commits_median"]
    assert any(w.startswith("user check FAILED") for w in g.sheet.warnings)


def test_b1_type_leak_refused_in_refuse_mode():
    with pytest.raises(ft.NullControlError, match="user_check='refuse'"):
        _cal("leak", user_check="refuse")


def test_real_within_user_signal_passes(signal):
    g = signal[0]
    c = g.sheet.users["check"]
    assert c["verdict"] == "pass" and c["p_user"] <= U.P_USER_MAX
    assert not any(w.startswith("user check") for w in g.sheet.warnings)


def test_label_null_on_arrays():
    rng = np.random.default_rng(0)
    users = np.repeat(np.arange(4), 150)
    base = np.array([0.2, 0.45, 0.7, 0.98])[users]
    w = rng.random(users.size) > base  # wrong top-1 at 1 - base rate
    s = base + rng.normal(0.0, 0.01, users.size)  # the score is the user only
    r = U.user_label_null(s, w, None, users.tolist(), 0.05, 0.1, seed=1, n_runs=100)
    assert r["verdict"] == "fail" and r["p_leak"] < U.P_LEAK_MAX
    z = rng.uniform(0.0, 1.0, users.size)
    r2 = U.user_label_null(z, rng.random(users.size) > z, None, users.tolist(), 0.05, 0.1, seed=1, n_runs=100)
    assert r2["verdict"] == "pass"
    r3 = U.user_label_null(np.full(10, -np.inf), np.zeros(10, bool), None, [0] * 5 + [1] * 5, 0.05, 0.1, n_runs=5)
    assert r3["verdict"] == "no commits"
    assert U.user_label_null(s, w, None, users.tolist(), 0.05, 0.1, seed=1, n_runs=100) == r  # deterministic


def test_mwu_matches_scipy():
    sp = pytest.importorskip("scipy.stats")
    rng = np.random.default_rng(4)
    for _ in range(5):
        a = rng.integers(0, 8, 60).astype(float)
        b = rng.integers(0, 7, 50).astype(float)
        ref = sp.mannwhitneyu(a, b, alternative="greater", method="asymptotic", use_continuity=True).pvalue
        assert U.mwu_greater_p(a, b) == pytest.approx(ref, rel=1e-9, abs=1e-12)
    assert U.mwu_greater_p([1.0, 1.0], [1.0]) == 1.0


# --- (b) per-user bound -----------------------------------------------------------------------------------------


def test_per_user_bound_each(tmp_path):
    g0, xs, ts, us = _cal("bad")
    g, _, _, _ = _cal("bad", user_bound="each")
    p = g.sheet.users["per_user"]
    assert p["mode"] == "each" and p["level_per_user"] == 0.1 and p["n_users"] == 4
    assert g.sheet.commit_threshold >= g0.sheet.commit_threshold and g.config_id != g0.config_id
    assert g.config.recipe["user_bound"]["mode"] == "each" and "user_bound" not in g0.config.recipe
    assert g.sheet.ltt_commits <= g0.sheet.ltt_commits and p["ltt_commits"] == g.sheet.ltt_commits
    assert g.sheet.controls and all(c.passed for c in g.sheet.controls)
    # each user meets its own LTT bound at the final threshold (in-sample check of the construction)
    order = np.random.default_rng(11).permutation(len(xs))
    n_fit, n_pol, _ = D._split(len(xs))
    s, w, o = D._user_view(g, xs, ts, order[n_fit + n_pol:], None)
    uu = np.array([us[i] for i in order[n_fit + n_pol:]])
    for u in set(us):
        m = uu == u
        lam, _ = U.certified(s[m], w[m], o[m], 0.05, 0.1)
        assert g.sheet.commit_threshold >= lam
    q = tmp_path / "g.json"
    g.save(q)
    h = ft.load(q)
    assert h.config_id == g.config_id and [h._decide_quiet(x).action for x in xs[:50]] == \
        [g._decide_quiet(x).action for x in xs[:50]]
    assert any("Per-user bound" in a for a in g.sheet.assumptions)


def test_per_user_bound_learned_score():
    g0, _, _, _ = _cal("bad", confidence="learned")
    g, _, _, _ = _cal("bad", confidence="learned", user_bound="each")
    assert g.commit_score.threshold == g.sheet.commit_threshold >= g0.commit_score.threshold
    assert g.config.recipe["commit_score"]["certification"]["user_bound"]["mode"] == "each"


def test_per_user_bound_needs_enough_items():
    with pytest.raises(ValueError, match="LTT items per user"):
        _cal("signal", m=100, user_bound="all")  # about 37 LTT items per user; 'all' needs 72


def test_input_checks():
    xs, ts = nbest_data(60, 1)
    nulls = [noise_nbest(np.random.default_rng(2)) for _ in range(30)]
    kw = dict(null_inputs=nulls, null_trials=20)
    with pytest.raises(ValueError, match="need users"):
        ft.calibrate(xs, ts, user_bound="each", **kw)
    with pytest.raises(ValueError, match="need users"):
        ft.calibrate(xs, ts, user_check="refuse", **kw)
    with pytest.raises(ValueError, match="one entry per input"):
        ft.calibrate(xs, ts, users=[0] * 59, **kw)
    with pytest.raises(ValueError, match="user_bound must be"):
        ft.calibrate(xs, ts, users=[0] * 60, user_bound="every", **kw)
    with pytest.raises(ValueError, match="sentence commits only"):
        ft.calibrate(xs, ts, users=[0] * 60, confidence="learned", commit_unit="prefix", **kw)
    with pytest.raises(ValueError):
        U.per_user_thresholds([0.5] * 4, [False] * 4, None, [0, 0, 1, 1], 0.05, 0.1, "pooled")
    assert math.isinf(U.certified(np.zeros(3), np.ones(3, bool), np.zeros(3, bool), 0.05, 0.1)[0])
