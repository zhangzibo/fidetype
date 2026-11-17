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


# --- review fixes (wiki/questions/g3-audit-review.md): H1, M1, M2, L4 --------------------------


def _single(eps=0.2, delta=0.5, bet=0.1, seed=None):
    """K = J = 1 controller that never commits (threshold far above every score)."""
    return BanditCommitRiskControl(alpha=0.05, explore=eps, delta=delta, eta=1e-9, lam_init=100.0,
                                   grid=(0.5,), bets=(bet,), seed=seed)


def test_single_threshold_bound_is_tight_enough_to_catch_a_halved_slack():
    """K = J = 1, delta 0.5: true failure rate about 0.33 with the full slack, about 0.76 with half of it.

    Every item has s = 0.6 >= 0.5 and is wrong (c = 1); it is withheld and explored at rate 0.2. The
    bound is checked after every item. Runs: 300 (sd of the rate about 0.03), so the pass rule
    "rate <= delta" fails with high probability if the slack in the code were halved. The naive
    estimate (no 1/pi) must fail almost always (negative control).
    """
    eps, delta, n, runs = 0.2, 0.5, 200, 300
    fails = fails_half = fails_naive = 0
    for seed in range(runs):
        rc = _single(eps, delta, seed=10_000 + seed)
        f = fh = fn = False
        n_shown_wrong = 0
        for t in range(1, n + 1):
            tk = rc.decide(0.6)
            n_shown_wrong += tk.shown
            rc.observe(tk, 1.0 if tk.shown else None)
            slack = ipw_slack(rc._V, 1, delta, rc.bets)[0]
            f |= t > rc.audit_upper()[0] + 1e-9
            fh |= t > rc._SX[0] + 0.5 * slack + 1e-9
            fn |= t > n_shown_wrong + slack + 1e-9
        fails += f
        fails_half += fh
        fails_naive += fn
    assert fails / runs <= delta
    assert fails / runs > 0.15             # the event is not trivially empty: the bound is near its level
    assert fails_half / runs > delta + 0.1  # a halved slack would fail the same rule
    assert fails_naive / runs > 0.95        # negative control: complete-case count without 1/pi


def test_coin_adaptive_adversary():
    """The data depend on the PAST coins: after an explored item, the next 3 items are right (c = 0).

    So the adversary makes the items near a shown one right and the others wrong, as far as the past
    coins allow. It cannot see the coin of the current item.
    """
    eps, delta, n, runs = 0.2, 0.5, 200, 300
    fails = 0
    for seed in range(runs):
        rc = _single(eps, delta, seed=20_000 + seed)
        quiet = 0
        y = 0.0
        f = False
        for _ in range(n):
            c = 0.0 if quiet > 0 else 1.0
            quiet = max(0, quiet - 1)
            tk = rc.decide(0.6)
            rc.observe(tk, c if tk.shown else None)
            if tk.explore:
                quiet = 3
            y += c
            f |= y > rc.audit_upper()[0] + 1e-9
        fails += f
    assert fails / runs <= delta + 3 * math.sqrt(delta * (1 - delta) / runs)


def test_cs_rule_audit_holds_uniformly_in_time():
    """rule='cs': the threshold (and so pi_t) depends on the past coins through the audit."""
    delta, n, runs = 0.1, 1000, 60
    fails = certified = 0
    for seed in range(runs):
        rng = np.random.default_rng(3000 + seed)
        rc = BanditCommitRiskControl(alpha=0.1, rule="cs", explore=0.2, delta=delta, seed=seed)
        grid = np.asarray(rc.grid)
        sh, ch = [], []
        failed = False
        for t in range(n):
            s = rng.uniform(0, 1)
            c = float(rng.uniform() < 1.5 * (1 - s) ** 3)
            tk = rc.decide(s)
            rc.observe(tk, c if tk.shown else None)
            sh.append(s)
            ch.append(c)
            if (t + 1) % 50 == 0 and np.any(_true_counts(sh, ch, grid) > rc.audit_upper() + 1e-9):
                failed = True
        fails += failed
        certified += rc.threshold <= 1.0
    assert fails / runs <= delta + 3 * math.sqrt(delta * (1 - delta) / runs)
    assert certified >= runs // 2  # the rule really commits, so it is tested


def _delayed_run(seed, mode, n=2000, lag=300, eps=0.05):
    """Reviewer probe B: lam fixed 0.6, every item below 0.6 is wrong. Shown items get their label late
    (``mode="lag"``: a random lag up to ``lag``, out of order) or never (``mode="never"``); withheld items
    are fed back at once. Returns (audit failed, old observe-time accounting failed)."""
    rng = np.random.default_rng(seed)
    rc = BanditCommitRiskControl(alpha=0.05, explore=eps, delta=0.1, eta=1e-9, lam_init=0.6, seed=seed)
    grid = np.asarray(rc.grid)
    K = grid.size
    sh, ch = [], []
    queue = []  # (due time, ticket, c)
    old_sx, old_v = np.zeros(K), np.zeros(K)  # what the pre-fix code summed (observed items only)

    def feed(tk, c):
        rc.observe(tk, c)
        above = tk.score >= grid
        if tk.shown:
            old_sx[:] += above * ((1.0 if c is None else c) / tk.propensity)
        if tk.propensity < 1.0:
            old_v[:] += above / tk.propensity

    failed = failed_old = False
    for t in range(n):
        s = rng.uniform(0, 1)
        c = 1.0 if s < 0.6 else float(rng.uniform() < 0.05)
        tk = rc.decide(s)
        sh.append(s)
        ch.append(c)
        if not tk.shown:
            feed(tk, None)
        elif mode == "lag":
            queue.append((t + int(rng.integers(1, lag + 1)), tk, c))
        due = [q for q in queue if q[0] <= t]
        queue = [q for q in queue if q[0] > t]
        for q in sorted(due, key=lambda q: rng.uniform()):  # out of order
            feed(q[1], q[2])
        if (t + 1) % 100 == 0:
            true = _true_counts(sh, ch, grid)
            failed |= bool(np.any(true > rc.audit_upper() + 1e-9))
            failed_old |= bool(np.any(true > old_sx + ipw_slack(old_v, K, 0.1, rc.bets) + 1e-9))
    return failed, failed_old


@pytest.mark.parametrize("mode", ["lag", "never"])
def test_audit_holds_with_delayed_or_never_returned_feedback(mode):
    """H1: the audit counts every decided item at decide time, so missing labels cannot break it."""
    runs = 40
    res = [_delayed_run(500 + seed, mode) for seed in range(runs)]
    fails = sum(r[0] for r in res)
    assert fails / runs <= 0.1 + 3 * math.sqrt(0.1 * 0.9 / runs)
    if mode == "never":
        # negative control: the old accounting (sums updated in observe) fails in (almost) every run
        assert sum(r[1] for r in res) / runs >= 0.9


def test_pending_shown_item_counts_as_wrong_until_its_label_arrives():
    rc = BanditCommitRiskControl(alpha=0.1, explore=1.0, eta=1e-9, lam_init=0.9, seed=0)
    tk = rc.decide(0.5)
    assert tk.explore and tk.propensity == 1.0
    k = 50  # grid point 0.50
    rep = rc.report()
    assert rc._SX[k] == 1.0 and rep["n_decided"] == 1 and rep["n_observed"] == 0
    rc.observe(tk, 0.0)
    assert rc._SX[k] == 0.0
    rc2 = BanditCommitRiskControl(alpha=0.1, explore=0.5, eta=1e-9, lam_init=0.9, seed=1)
    tks = [rc2.decide(0.5) for _ in range(40)]
    before = rc2.audit_upper().copy()
    for tk in tks:
        rc2.observe(tk, 0.0 if tk.shown else None)
    after = rc2.audit_upper()
    assert np.all(after <= before + 1e-9) and after[k] < before[k]  # labels only lower the bound
    assert rc2._N[k] == 40  # every decided item is in the audit


def test_forbidden_items_are_never_explored_and_the_coin_stream_is_unchanged():
    """L4: s = -inf adds nothing to the audit, so it is never shown for exploration."""
    rc = BanditCommitRiskControl(alpha=0.1, explore=1.0, eta=1e-9, lam_init=0.9, seed=7)
    for _ in range(20):
        tk = rc.decide(-math.inf)
        assert not tk.shown and not tk.explore and tk.propensity == 0.0
        rc.observe(tk, None)
    assert rc.n_explore == 0 and np.all(rc._V == 0) and np.all(rc._SX == 0)
    # one coin per withheld item, whatever the score: the next coins continue the same stream
    rng = np.random.default_rng(7)
    rng.random(20)
    rc.explore = 0.5
    u = rng.random(10)
    got = [rc.decide(0.3).explore for _ in range(10)]
    assert got == list(u < 0.5)


def test_default_seed_draws_fresh_coins():
    """M1: the default seed is None (OS entropy); fixed seeds reproduce."""
    assert BanditCommitRiskControl().seed is None
    a = [BanditCommitRiskControl(explore=0.5, lam_init=0.9).decide(0.3).explore for _ in range(64)]
    assert 0 < sum(a) < 64  # independent streams, not one fixed coin repeated
    s1 = [BanditCommitRiskControl(explore=0.5, lam_init=0.9, seed=3) for _ in range(2)]
    assert [s1[0].decide(0.3).explore for _ in range(30)] == [s1[1].decide(0.3).explore for _ in range(30)]
