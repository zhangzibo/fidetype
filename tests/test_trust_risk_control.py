"""Tests of fidetype.trust.risk_control (M2-13)."""

import math

import numpy as np
import pytest

from fidetype.trust.policy import Action, DecisionPolicy, PolicyConfig, PolicyInputs
from fidetype.trust.risk_control import (
    CommitRiskControl,
    binomial_pvalue,
    commit_calibration_data,
    crc_threshold,
    empirical_risk,
    hoeffding_bentkus_pvalue,
    ltt_threshold,
)


def synthetic(n, rng, skew=1.0):
    """Scores in [0, 1]; P(wrong | s) = (1 - s) ** skew. Some items are not eligible."""
    s = rng.uniform(0, 1, n)
    wrong = (rng.uniform(0, 1, n) < (1 - s) ** skew).astype(float)
    s[rng.uniform(0, 1, n) < 0.1] = -math.inf
    return s, wrong


def test_crc_hand_example():
    # 20 items: 10 right at 0.9, 10 wrong at 0.1.
    s = np.r_[np.full(10, 0.9), np.full(10, 0.1)]
    c = np.r_[np.zeros(10), np.ones(10)]
    r = crc_threshold(s, c, alpha=0.05)
    assert r.feasible and r.threshold == pytest.approx(0.9)
    assert r.empirical_risk == 0.0 and r.bound == pytest.approx(1 / 21)
    assert r.commit_rate == pytest.approx(0.5)


def test_crc_small_n_infeasible_never_commits():
    # n = 10 < 1 / alpha - 1 = 19: even "never commit" fails the bound.
    r = crc_threshold(np.full(10, 0.99), np.zeros(10), alpha=0.05)
    assert not r.feasible and math.isinf(r.threshold)
    # n = 19 is just enough: B / (n + 1) = 0.05.
    r = crc_threshold(np.full(19, 0.99), np.zeros(19), alpha=0.05)
    assert r.feasible and r.threshold == pytest.approx(0.99)


def test_crc_all_wrong_commits_little():
    rng = np.random.default_rng(0)
    s = rng.uniform(0, 1, 400)
    r = crc_threshold(s, np.ones(400), alpha=0.05)
    # It spends the risk budget: about (0.05 * 401 - 1) / 400 = 0.0476 of items commit.
    assert r.feasible
    assert r.commit_rate <= (0.05 * 401 - 1) / 400 + 1e-9
    assert r.commit_rate > 0.03


def test_crc_fallback_floor_infeasible():
    # The non-commit action is itself wrong too often: no threshold works.
    n = 200
    r = crc_threshold(np.full(n, 0.5), np.zeros(n), alpha=0.05, fallback_losses=np.r_[np.ones(20), np.zeros(n - 20)])
    assert not r.feasible and math.isinf(r.threshold)


def test_monotonised_loss_is_upper_bound():
    s = np.array([0.9, 0.2, -np.inf])
    c = np.array([0.0, 0.0, 1.0])
    f = np.array([1.0, 0.0, 0.0])
    # Item 0: commit loss 0 but fallback loss 1 -> monotonised commit loss 1.
    assert empirical_risk(s, c, 0.5, f) == pytest.approx(1 / 3)
    assert empirical_risk(s, c, math.inf, f) == pytest.approx(1 / 3)


def test_input_validation():
    with pytest.raises(ValueError):
        crc_threshold([0.5, np.nan], [0, 1])
    with pytest.raises(ValueError):
        crc_threshold([0.5], [2.0])
    with pytest.raises(ValueError):
        crc_threshold([0.5], [0.0], alpha=0.0)
    with pytest.raises(ValueError):
        ltt_threshold([0.5], [0.5], pvalue="binomial")


def test_pvalues():
    # Zero losses: binomial p = (1 - alpha)^n.
    assert binomial_pvalue(0.0, 100, 0.05) == pytest.approx(0.95**100)
    # HB is never smaller than the exact binomial tail for 0/1 data at R_hat = 0.
    assert hoeffding_bentkus_pvalue(0.0, 100, 0.05) >= binomial_pvalue(0.0, 100, 0.05) - 1e-12
    # Risk above alpha: p-value is large.
    assert binomial_pvalue(0.1, 200, 0.05) > 0.5
    assert hoeffding_bentkus_pvalue(0.1, 200, 0.05) == pytest.approx(1.0)
    # Monotone in R_hat.
    ps = [binomial_pvalue(r, 300, 0.05) for r in (0.0, 0.01, 0.02, 0.03, 0.04)]
    assert all(a <= b for a, b in zip(ps, ps[1:]))


def test_ltt_is_stricter_than_crc():
    rng = np.random.default_rng(1)
    s, w = synthetic(500, rng)
    crc = crc_threshold(s, w, 0.05)
    ltt = ltt_threshold(s, w, 0.05, delta=0.1)
    assert crc.feasible and ltt.feasible
    assert ltt.threshold >= crc.threshold - 0.011  # grid step 0.01
    assert ltt.method == "ltt-binomial"
    assert ltt_threshold(s, w, 0.05, delta=0.1, pvalue="hb").threshold >= ltt.threshold


def test_ltt_no_rejection():
    r = ltt_threshold(np.full(20, 0.99), np.ones(20), 0.05, delta=0.1)
    assert not r.feasible and math.isinf(r.threshold)


@pytest.mark.parametrize("n_cal", [50, 200])
def test_crc_mean_risk_controlled_monte_carlo(n_cal):
    """Over many random calibration/test draws, the mean test wrong-commit rate is <= alpha."""
    rng = np.random.default_rng(42 + n_cal)
    alpha, reps, n_test = 0.05, 2000, 200
    risks = []
    for _ in range(reps):
        s, w = synthetic(n_cal, rng)
        lam = crc_threshold(s, w, alpha).threshold
        st, wt = synthetic(n_test, rng)
        risks.append(empirical_risk(st, wt, lam))
    risks = np.array(risks)
    se = risks.std(ddof=1) / math.sqrt(reps)
    assert risks.mean() <= alpha + 3 * se
    # CRC is not trivially conservative: it uses most of the budget.
    assert risks.mean() >= alpha - 0.02


def test_plugin_rule_overshoots_where_crc_holds():
    """The plug-in rule (empirical risk <= alpha) has mean risk above alpha for small n."""
    rng = np.random.default_rng(7)
    alpha, reps = 0.05, 2000
    plug, crc = [], []
    for _ in range(reps):
        s, w = synthetic(40, rng)
        lams = np.r_[np.unique(s[np.isfinite(s)]), np.inf]
        r = np.array([empirical_risk(s, w, x) for x in lams])
        lam_plug = lams[np.argmax(r <= alpha)]
        st, wt = synthetic(300, rng)
        plug.append(empirical_risk(st, wt, lam_plug))
        crc.append(empirical_risk(st, wt, crc_threshold(s, w, alpha).threshold))
    assert np.mean(plug) > alpha
    assert np.mean(crc) <= alpha + 3 * np.std(crc) / math.sqrt(reps)


def test_ltt_high_probability_monte_carlo():
    """P(true risk at lambda_hat > alpha) <= delta (true risk from a large test set)."""
    rng = np.random.default_rng(3)
    alpha, delta, reps = 0.05, 0.1, 400
    st, wt = synthetic(200_000, rng)
    fails = 0
    for _ in range(reps):
        s, w = synthetic(300, rng)
        lam = ltt_threshold(s, w, alpha, delta).threshold
        fails += empirical_risk(st, wt, lam) > alpha
    assert fails / reps <= delta + 3 * math.sqrt(delta * (1 - delta) / reps)


def _inputs(p, risk=0.0, texts=("a b", "a c")):
    return PolicyInputs(texts=texts, p_top1=p, set_indices=(0, 1), guard_risk=risk)


def test_commit_calibration_data_respects_other_rules():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.8, commit_max_risk=0.3, offer_max_k=3))
    xs = [_inputs(0.9), _inputs(0.95, risk=0.5), _inputs(0.2)]
    s, c, f = commit_calibration_data(pol, xs, ["a b", "a b", "x"])
    assert s[0] == pytest.approx(0.9)
    assert s[1] == -math.inf  # guard blocks the commit at any threshold
    assert s[2] == pytest.approx(0.2)
    assert list(c) == [0.0, 0.0, 1.0]
    assert list(f) == [0.0, 0.0, 0.0]


def test_commit_risk_control_apply():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.5, offer_max_k=3))
    rng = np.random.default_rng(0)
    xs, truths = [], []
    for _ in range(300):
        p = float(rng.uniform())
        ok = rng.uniform() < p
        xs.append(_inputs(p))
        truths.append("a b" if ok else "zzz")
    rc = CommitRiskControl(alpha=0.05).fit_policy(pol, xs, truths)
    new = rc.apply(pol)
    assert new.config.commit_p == pytest.approx(rc.threshold)
    assert new.config.offer_max_k == 3
    assert rc.apply(DecisionPolicy(PolicyConfig(commit_p=0.999)), "max").config.commit_p == pytest.approx(0.999)
    # Decisions follow the new threshold.
    assert new.decide(_inputs(min(1.0, rc.threshold + 1e-6)), final_attempt=True).action == Action.COMMIT
    assert new.decide(_inputs(rc.threshold - 1e-3), final_attempt=True).action != Action.COMMIT
    inf_rc = CommitRiskControl(alpha=0.05).fit(np.full(5, 0.9), np.zeros(5))
    assert inf_rc.apply(pol).decide(_inputs(1.0), final_attempt=True).action != Action.COMMIT
    with pytest.raises(RuntimeError):
        CommitRiskControl().threshold
