"""Tests of fidetype.trust.online_risk (M2-16)."""

import math

import numpy as np
import pytest

from fidetype.trust.online_risk import OnlineCommitRiskControl, OnlineTrustPolicy, weighted_crc_threshold
from fidetype.trust.policy import Action, DecisionPolicy, PolicyConfig, PolicyInputs
from fidetype.trust.risk_control import crc_threshold

ALPHA = 0.05


def drifting(n, rng, drift):
    """P(wrong | s) = (1 - s)^2 * (1 + drift * t), t from 0 to 1 over the stream."""
    s = rng.uniform(0, 1, n)
    t = np.linspace(0, 1, n)
    p = np.clip((1 - s) ** 2 * (1 + drift * t), 0, 1)
    return s, (rng.uniform(0, 1, n) < p).astype(float)


def run(o, s, c, f=None):
    f = np.zeros_like(c) if f is None else f
    loss, com = [], []
    for si, ci, fi in zip(s, c, f):
        tk = o.step(si, ci, fi)
        loss.append(max(ci, fi) if tk.commit else fi)
        com.append(tk.commit)
    return float(np.mean(loss)), float(np.mean(com))


# --- weighted CRC ----------------------------------------------------------


def test_weighted_crc_unit_weights_equals_crc():
    rng = np.random.default_rng(0)
    for _ in range(20):
        s, c = drifting(300, rng, 0.0)
        s[rng.uniform(0, 1, 300) < 0.1] = -math.inf
        a, b = crc_threshold(s, c, ALPHA), weighted_crc_threshold(s, c, ALPHA)
        assert a.threshold == b.threshold and a.feasible == b.feasible
        assert a.bound == pytest.approx(b.bound)


def test_weighted_crc_infeasible_cases():
    assert not weighted_crc_threshold([0.9] * 50, [0] * 50, alpha=0.0).feasible
    assert weighted_crc_threshold([], [], alpha=0.05).threshold == math.inf
    # Total weight 10 < 1 / alpha - 1: never commit.
    r = weighted_crc_threshold([0.9] * 100, [0] * 100, ALPHA, weights=[0.1] * 100)
    assert not r.feasible and r.threshold == math.inf
    with pytest.raises(ValueError):
        weighted_crc_threshold([0.5], [0], ALPHA, weights=[-1.0])


def test_weighted_crc_decay_follows_recent_items():
    # Old items: right at 0.6; new items: wrong at 0.6. Decay must stop committing at 0.6.
    s = np.r_[np.full(300, 0.6), np.full(20, 0.6), np.full(220, 0.95)]
    c = np.r_[np.zeros(300), np.ones(20), np.zeros(220)]
    order = np.r_[np.arange(300), 300 + np.argsort(np.random.default_rng(0).uniform(size=240))]
    s, c = s[order], c[order]
    uniform = weighted_crc_threshold(s, c, ALPHA)
    age = np.arange(s.size - 1, -1, -1)
    recent = weighted_crc_threshold(s, c, ALPHA, weights=0.99**age)
    assert uniform.threshold == pytest.approx(0.6)
    assert recent.threshold == pytest.approx(0.95)


# --- drift: offline CRC breaks, online methods hold -----------------------


@pytest.mark.parametrize("seed", [0, 1])
def test_drift_offline_breaks_online_holds(seed):
    rng = np.random.default_rng(seed)
    cs, cc = drifting(400, rng, 0.0)
    ts, tc = drifting(4000, rng, 4.0)
    lam = crc_threshold(cs, cc, ALPHA).threshold
    offline = float(np.mean(np.where(ts >= lam, tc, 0.0)))
    assert offline > ALPHA + 0.05  # the offline guarantee fails under drift
    for kw, tol in [
        (dict(method="aci"), 0.005),
        (dict(method="aci_window", window=300), 0.005),
        (dict(method="window", window=300), 0.01),  # approximate method
    ]:
        o = OnlineCommitRiskControl(alpha=ALPHA, **kw).fit(cs, cc)
        rate, commit = run(o, ts, tc)
        assert rate <= ALPHA + tol, (kw, rate)
        assert commit > 0.25, (kw, commit)  # not trivially "never commit"
        rep = o.report()
        if kw["method"] != "window":
            assert rep["mean_loss"] <= rep["certificate"] + 1e-12
            assert rate == pytest.approx(rep["mean_loss"])


def test_exchangeable_stream_costs_little_commit_rate():
    rng = np.random.default_rng(3)
    cs, cc = drifting(400, rng, 0.0)
    ts, tc = drifting(4000, rng, 0.0)
    lam = crc_threshold(cs, cc, ALPHA).threshold
    crc_commit = float(np.mean(ts >= lam))
    for method in ("aci", "aci_window", "window"):
        o = OnlineCommitRiskControl(alpha=ALPHA, method=method).fit(cs, cc)
        rate, commit = run(o, ts, tc)
        assert rate <= ALPHA + 0.01
        assert commit >= 0.85 * crc_commit, (method, commit, crc_commit)


# --- adversarial sequences: the long-run bound holds for any sequence -----


@pytest.mark.parametrize("method", ["aci", "aci_window"])
def test_all_wrong_bursts_any_sequence(method):
    rng = np.random.default_rng(4)
    n = 3000
    s = rng.uniform(0.5, 1.0, n)
    c = np.zeros(n)
    for start in range(200, n, 600):  # bursts of 100 confident wrong items
        c[start : start + 100] = 1.0
    s[c == 1] = 1.0  # the worst case: maximal confidence when wrong
    o = OnlineCommitRiskControl(alpha=ALPHA, method=method, lam_init=0.5, window=100)
    rate, _ = run(o, s, c)
    rep = o.report()
    assert rate <= rep["certificate"] + 1e-12
    assert rate <= ALPHA + 0.01
    if method == "aci":
        assert rate <= o.prior_bound(n) + 1e-12


def test_aci_threshold_bounded_and_floor():
    o = OnlineCommitRiskControl(alpha=ALPHA, method="aci", lam_init=0.3, lam_min=0.2, eta=0.1)
    for _ in range(200):  # always right, always confident: lambda falls to the floor
        o.step(0.99, 0.0)
    assert o.threshold == pytest.approx(0.2)
    for _ in range(200):  # always wrong at score 1.0: lambda rises just past 1, then stops
        o.step(1.0, 1.0)
    assert 1.0 < o.lam_max_seen <= 1.0 + o.eta * (1 - ALPHA) + 1e-12
    rep = o.report()
    assert rep["mean_loss"] <= rep["certificate"] + 1e-12


def test_upper_clip_voids_certificate():
    o = OnlineCommitRiskControl(alpha=ALPHA, method="aci", lam_init=0.5, lam_max=0.6)
    for _ in range(50):
        o.step(0.9, 1.0)
    assert o.upper_clip_hits > 0 and math.isnan(o.report()["certificate"])


# --- feedback edge cases ----------------------------------------------------


def test_no_feedback_keeps_threshold():
    o = OnlineCommitRiskControl(alpha=ALPHA, method="aci", lam_init=0.7)
    tks = [o.decide(x) for x in (0.9, 0.5, 0.8)]
    assert [t.commit for t in tks] == [True, False, True]
    assert o.threshold == 0.7 and o.pending == 3
    rep = o.report()
    assert rep["n_observed"] == 0 and math.isnan(rep["mean_loss"])


def test_cold_start_window_never_commits_until_enough_feedback():
    o = OnlineCommitRiskControl(alpha=ALPHA, method="window", window=None)
    assert o.threshold == math.inf
    n = 0
    while o.threshold == math.inf:
        tk = o.decide(0.9)
        assert not tk.commit
        o.observe(tk, 0.0)  # full feedback: the truth is known after OFFER
        n += 1
    assert n == 19  # (n * 0 + 1) / (n + 1) <= 0.05  <=>  n >= 19


@pytest.mark.parametrize("method", ["aci", "aci_window"])
def test_delayed_feedback(method):
    rng = np.random.default_rng(5)
    cs, cc = drifting(400, rng, 0.0)
    ts, tc = drifting(4000, rng, 4.0)
    d = 10
    o = OnlineCommitRiskControl(alpha=ALPHA, method=method).fit(cs, cc)
    queue, losses = [], []
    for s, c in zip(ts, tc):
        tk = o.decide(s)
        queue.append((tk, c))
        losses.append(c if tk.commit else 0.0)
        if len(queue) > d:
            o.observe(*queue.pop(0))
    assert o.pending == d
    rep = o.report()
    assert rep["mean_loss"] <= rep["certificate"] + 1e-12
    T = len(ts)
    # The d unobserved items can add at most d / T.
    assert np.mean(losses) <= rep["certificate"] * rep["n_observed"] / T + d / T + 1e-12
    assert np.mean(losses) <= ALPHA + 0.01
    if method == "aci":
        assert np.mean(losses) <= o.prior_bound(T, delay=d) + 1e-12


def test_out_of_order_and_double_observe():
    o = OnlineCommitRiskControl(alpha=ALPHA, method="aci", lam_init=0.5)
    a, b = o.decide(0.9), o.decide(0.95)
    o.observe(b, 0.0)
    o.observe(a, 1.0)
    with pytest.raises(KeyError):
        o.observe(a, 1.0)
    with pytest.raises(ValueError):
        o.observe(o.decide(0.9), 2.0)


def test_missing_skip_vs_pessimistic():
    for missing, n_obs, loss in (("skip", 0, 0.0), ("pessimistic", 1, 1.0)):
        o = OnlineCommitRiskControl(alpha=ALPHA, method="aci", lam_init=0.5, missing=missing)
        tk = o.decide(0.9)
        assert tk.commit
        o.observe(tk, None)
        rep = o.report()
        assert rep["n_missing"] == 1 and rep["n_observed"] == n_obs
        if n_obs:
            assert rep["mean_loss"] == loss and o.threshold > 0.5


def test_window_skips_unknown_truth():
    o = OnlineCommitRiskControl(alpha=ALPHA, method="window")
    o.fit([0.9] * 30, [0] * 30)
    n = len(o.hist_s)
    tk = o.decide(0.1)  # does not commit; the user gives up: truth unknown
    o.observe(tk, None)
    assert len(o.hist_s) == n


def test_invalid_arguments():
    with pytest.raises(ValueError):
        OnlineCommitRiskControl(alpha=0.0)
    with pytest.raises(ValueError):
        OnlineCommitRiskControl(method="nope")
    with pytest.raises(ValueError):
        OnlineCommitRiskControl(decay=1.5)
    with pytest.raises(ValueError):
        OnlineCommitRiskControl().decide(math.nan)


# --- policy integration -----------------------------------------------------


def _inputs(p, risk=0.0, texts=("a b", "a c")):
    return PolicyInputs(texts=texts, p_top1=p, set_indices=(0, 1), guard_risk=risk)


def test_online_trust_policy_matches_decision_policy():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.8, commit_max_risk=0.3, offer_max_k=3))
    op = OnlineTrustPolicy(pol, OnlineCommitRiskControl(alpha=ALPHA, method="aci", lam_init=0.7))
    d, tk = op.decide(_inputs(0.75))
    assert d.action == Action.COMMIT and tk.commit and tk.threshold == 0.7
    assert op.feedback(tk, "x y") == 1.0  # wrong commit: threshold rises
    assert op.controller.threshold == pytest.approx(0.7 + 0.05 * 0.95)
    d, tk = op.decide(_inputs(0.95, risk=0.5))  # guard blocks the commit
    assert d.action == Action.OFFER and not tk.commit and tk.score == -math.inf
    assert op.feedback(tk, "a b") == 0.0
    d, tk = op.decide(_inputs(0.99))
    assert d.action == Action.COMMIT
    op.feedback(tk, None)  # no feedback: skipped
    assert op.controller.report()["n_missing"] == 1
    # apply() gives a plain DecisionPolicy at the current threshold.
    p2 = op.controller.apply(pol)
    assert p2.config.commit_p == pytest.approx(op.controller.threshold)
    assert op.controller.apply(pol, "max").config.commit_p == pytest.approx(max(0.8, op.controller.threshold))


def test_fit_policy_warm_start_equals_offline_crc():
    rng = np.random.default_rng(6)
    pol = DecisionPolicy(PolicyConfig(commit_p=0.5, offer_max_k=3))
    ps = rng.uniform(0, 1, 200)
    xs = [_inputs(float(p)) for p in ps]
    truths = ["a b" if rng.uniform() < p else "zz" for p in ps]
    o = OnlineCommitRiskControl(alpha=0.1, method="aci").fit_policy(pol, xs, truths)
    assert o.result.feasible and o.threshold == pytest.approx(o.result.threshold)
    o2 = OnlineCommitRiskControl(alpha=0.1, method="window", window=None).fit_policy(pol, xs, truths)
    assert o2.threshold == pytest.approx(o.result.threshold)
