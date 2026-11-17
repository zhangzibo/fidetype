"""Tests of fidetype.trust.bandit_risk (P15-04): online risk control with shown-only feedback."""

import math

import numpy as np
import pytest

from fidetype.trust.bandit_risk import (
    BanditCommitRiskControl,
    BanditTrustPolicy,
    NaiveShownOnlyControl,
    ipw_slack,
)
from fidetype.trust.policy import Action, DecisionPolicy, PolicyConfig, PolicyInputs


def stream(n, rng, steep=1.5):
    """Scores U(0, 1); P(wrong | s) = min(1, steep (1 - s)^3)."""
    s = rng.uniform(0, 1, n)
    p = np.clip(steep * (1 - s) ** 3, 0, 1)
    return s, (rng.uniform(0, 1, n) < p).astype(float)


def run(rc, s, c):
    for si, ci in zip(s, c):
        rc.step(si, ci)
    return rc.report()


# --- (G1) / (G2): deterministic certificates with shown-only feedback ---------------------------


@pytest.mark.parametrize("target", ["marginal", "precision"])
def test_aci_certificate_is_an_identity_for_adversarial_streams(target):
    rng = np.random.default_rng(1)
    for _ in range(10):
        rc = BanditCommitRiskControl(alpha=0.1, target=target, explore=0.0, lam_init=0.8, seed=None)
        wrong = commits = 0
        for t in range(1500):
            # adversary: wrong exactly when the item would commit, half the time
            s = rng.uniform(0, 1)
            tk = rc.decide(s)
            c = float(tk.commit and rng.uniform() < 0.5)
            rc.observe(tk, c if tk.shown else None)
            wrong += c if tk.commit else 0
            commits += tk.commit
        r = rc.report()
        realised = wrong / 1500 if target == "marginal" else wrong / max(commits, 1)
        assert r["realised"] == pytest.approx(realised)
        assert realised <= r["certificate"] + 1e-9
        # the threshold stays bounded, so the certificate goes to alpha
        assert r["lam_aci"] <= 1.0 + rc.eta
        if target == "marginal":
            assert r["certificate"] <= 0.1 + (1.0 + rc.eta - 0.8) / (rc.eta * 1500) + 1e-9


def test_precision_aci_holds_where_naive_shown_only_control_fails():
    """The naive controller uses shown items as if random: its long-run precision error exceeds alpha."""
    alpha = 0.1
    naive_err, aci_err, aci_cert = [], [], []
    for seed in range(12):
        rng = np.random.default_rng(seed)
        s, c = stream(3000, rng)
        nv = NaiveShownOnlyControl(alpha=alpha, target="precision", lam_init=0.9)
        for si, ci in zip(s, c):
            nv.step(si, ci)
        naive_err.append(nv.n_wrong / nv.n_commits)
        r = run(BanditCommitRiskControl(alpha=alpha, target="precision", lam_init=0.9, explore=0.05, seed=seed), s, c)
        aci_err.append(r["realised"])
        aci_cert.append(r["certificate"])
        assert r["realised"] <= r["certificate"] + 1e-9
        assert r["n_commits"] > 1000  # not safe by doing nothing
    assert np.mean(naive_err) > alpha + 0.005
    assert max(aci_err) <= alpha + 0.01
    assert np.mean(aci_cert) <= alpha + 0.01


def test_withheld_labels_are_never_used():
    rc = BanditCommitRiskControl(alpha=0.1, explore=0.0, lam_init=0.5)
    tk = rc.decide(0.2)
    assert not tk.commit and not tk.shown
    assert rc.observe(tk, 1.0) == 0.0  # the value is ignored: the system cannot see it
    r = rc.report()
    assert r["audit"]["ipw_wrong"][0] == 0.0 and r["n_shown"] == 0


def test_missing_label_on_a_commit_is_pessimistic():
    rc = BanditCommitRiskControl(alpha=0.1, explore=0.0, lam_init=0.5)
    tk = rc.decide(0.9)
    assert tk.commit
    assert rc.observe(tk, None) == 1.0
    assert rc.report()["n_missing"] == 1


# --- (G3): design-based audit -----------------------------------------------------------------


def _true_counts(s_hist, c_hist, grid):
    s = np.asarray(s_hist)[:, None]
    c = np.asarray(c_hist)[:, None]
    return (c * (s >= grid[None, :])).sum(axis=0)


@pytest.mark.parametrize("adversarial", [False, True])
def test_audit_upper_bound_holds_uniformly_in_time(adversarial):
    """Over many seeds the bound fails (at any checkpoint, any grid threshold) in at most delta of runs."""
    delta, n, runs = 0.1, 1200, 120
    fails = 0
    for seed in range(runs):
        rng = np.random.default_rng(1000 + seed)
        rc = BanditCommitRiskControl(alpha=0.1, explore=0.1, delta=delta, lam_init=0.6, seed=seed)
        grid = np.asarray(rc.grid)
        sh, ch = [], []
        failed = False
        for t in range(n):
            s = rng.uniform(0, 1)
            if adversarial:
                # adaptive adversary: everything the current policy withholds is wrong
                c = float(s < rc.threshold or rng.uniform() < 0.05)
            else:
                c = float(rng.uniform() < 1.5 * (1 - s) ** 3)
            tk = rc.decide(s)
            rc.observe(tk, c if tk.shown else None)
            sh.append(s)
            ch.append(c)
            if (t + 1) % 100 == 0:
                if np.any(_true_counts(sh, ch, grid) > rc.audit_upper() + 1e-9):
                    failed = True
                    break
        fails += failed
    assert fails / runs <= delta + 3 * math.sqrt(delta * (1 - delta) / runs)


def test_ipw_is_unbiased_where_the_naive_estimate_is_optimistic():
    lam = 0.3
    k = 30
    naive, ipw, true = [], [], []
    for seed in range(40):
        rng = np.random.default_rng(seed)
        s, c = stream(2000, rng)
        r = run(BanditCommitRiskControl(alpha=0.1, target="precision", lam_init=0.9, explore=0.1, seed=seed), s, c)
        a = r["audit"]
        assert a["grid"][k] == pytest.approx(lam)
        naive.append(a["naive_precision_error"][k])
        ipw.append(a["ipw_wrong"][k] / a["n_at"][k])
        true.append(c[s >= lam].mean())
    bias_naive = np.mean(naive) - np.mean(true)
    bias_ipw = np.mean(ipw) - np.mean(true)
    assert bias_naive < -0.02  # optimistic
    assert abs(bias_ipw) < 0.01


def test_ipw_slack_shape_and_monotone():
    v = np.array([0.0, 10.0, 1000.0])
    sl = ipw_slack(v, 101, 0.1)
    assert sl.shape == (3,) and np.all(np.diff(sl) > 0)
    assert sl[0] == pytest.approx(math.log(101 * 12 / 0.1))  # V = 0: min at b = 1


def test_no_exploration_gives_an_infinite_audit_below_the_threshold():
    rc = BanditCommitRiskControl(alpha=0.1, explore=0.0, lam_init=0.5)
    for s in (0.2, 0.7):
        rc.step(s, 0.0)
    ub = rc.audit_upper()
    # rc.audit_upper is finite only where every item was shown with prob. 1
    assert math.isfinite(ub[70]) and ub[70] == 0.0


def test_rules_and_validation():
    with pytest.raises(ValueError):
        BanditCommitRiskControl(rule="cs", explore=0.0)
    with pytest.raises(ValueError):
        BanditCommitRiskControl(alpha=0.0)
    with pytest.raises(ValueError):
        BanditCommitRiskControl(grid=(0.5, 0.2))
    rc = BanditCommitRiskControl(rule="cs", explore=0.2)
    assert rc.threshold > 1.0  # nothing certified yet: never commit
    tk = rc.decide(0.5)
    rc.observe(tk, None)
    with pytest.raises(KeyError):
        rc.observe(tk, None)


def test_max_rule_keeps_the_aci_certificate():
    rng = np.random.default_rng(3)
    s, c = stream(4000, rng)
    rc = BanditCommitRiskControl(alpha=0.1, rule="max", explore=0.3, lam_init=0.9, seed=0)
    r = run(rc, s, c)
    assert r["realised"] <= r["certificate"] + 1e-9
    assert r["threshold"] >= r["lam_aci"] or r["threshold"] > 1.0


# --- policy wrapper ---------------------------------------------------------------------------


def _inputs(p, texts=("a b", "a c")):
    return PolicyInputs(texts=tuple(texts), p_top1=p, set_indices=tuple(range(len(texts))))


def test_policy_wrapper_explores_as_offer_and_never_commits_below_threshold():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.8, offer_max_k=1, final_fallback="abstain"))
    bp = BanditTrustPolicy(pol, BanditCommitRiskControl(alpha=0.1, explore=1.0, lam_init=0.7, seed=0))
    d, tk = bp.decide(_inputs(0.4, texts=("a b", "a c", "a d")))
    assert tk.explore and d.action == Action.OFFER and not tk.commit
    assert bp.feedback(tk, "a b") == 0.0
    d, tk = bp.decide(_inputs(0.9))
    assert tk.commit and d.action == Action.COMMIT
    assert bp.feedback(tk, "zz") == 1.0
