"""Tests of the P5-02 precision-type bound: fidetype.trust.precision_bound and calibrate(target_precision=)."""

from __future__ import annotations

import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import precision_bound as P
from fidetype.utils.binomial import binom_cdf, clopper_pearson, cp_upper

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits, nbest_data, noise_nbest


# --- binomial helpers -----------------------------------------------------------------------


def test_cp_helpers_match_known_values():
    assert clopper_pearson(2, 701) == [0.0003, 0.0103]  # P14-03 T15 (scipy values)
    assert clopper_pearson(15, 400) == [0.0211, 0.0611]  # P14-03 T12
    assert clopper_pearson(0, 0) == [None, None]
    # one-sided upper bound at 1 - delta: P(Bin(n, u) <= k) = delta
    u = cp_upper(3, 50, 0.1)
    assert abs(binom_cdf(3, 50, u) - 0.1) < 1e-9
    assert cp_upper(0, 0, 0.1) == 1.0
    assert abs(cp_upper(0, 22, 0.1) - (1 - 0.1 ** (1 / 22))) < 1e-9
    from fidetype.demo.live import tracks

    assert tracks.clopper_pearson is clopper_pearson  # the old import path still works


def test_pvalue_and_min_commits():
    assert P.precision_pvalue(0, 0, 0.05) == 1.0
    assert abs(P.precision_pvalue(0, 45, 0.05) - 0.95 ** 45) < 1e-12
    assert P.min_commits_needed(0.95, 0.1) == 45
    assert P.min_commits_needed(0.9, 0.1) == 22
    assert 0.95 ** 45 <= 0.1 < 0.95 ** 44
    # p <= delta  <=>  one-sided CP upper bound <= beta
    for k, n in [(0, 45), (0, 44), (2, 100), (5, 60)]:
        assert (P.precision_pvalue(k, n, 0.05) <= 0.1) == (cp_upper(k, n, 0.1) <= 0.05)
    with pytest.raises(ValueError):
        P.min_commits_needed(1.0, 0.1)


# --- LTT on synthetic items ---------------------------------------------------------------


def population(n: int, rng: np.random.Generator) -> list[P.PrecisionItem]:
    """Exchangeable items. The wrong rate falls with p_top1, but not monotonically (a bump near 0.8)."""
    p = rng.uniform(0.0, 1.0, n)
    r = np.clip(0.9 * (1.0 - p) ** 1.5 + 0.15 * np.exp(-((p - 0.8) / 0.03) ** 2), 0.0, 1.0)
    wrong = rng.random(n) < r
    can = rng.random(n) < 0.85
    return [P.PrecisionItem(bool(can[i]), float(p[i]), bool(wrong[i])) for i in range(n)]


def true_error(pop: list[P.PrecisionItem], c: float) -> float:
    k = P.precision_counts(pop, c)
    return k["wrong"] / k["commits"]


def test_bound_holds_on_exchangeable_data():
    """P(selected threshold has precision < target) <= delta over many calibration draws."""
    rng = np.random.default_rng(11)
    pop = population(60000, rng)
    grid = [round(1 - 0.02 * k, 2) for k in range(51)]
    target, delta = 0.9, 0.1
    viol, feasible, rates = 0, 0, []
    reps = 200
    for _ in range(reps):
        idx = rng.choice(len(pop), size=1200, replace=False)
        res = P.precision_ltt([pop[i] for i in idx[:600]], [pop[i] for i in idx[600:]], grid,
                              target_precision=target, delta=delta)
        if res.selected is None:
            continue
        feasible += 1
        rates.append(P.precision_counts(pop, res.selected)["commits"] / len(pop))
        # every certified threshold must hold (the stronger statement)
        viol += any(true_error(pop, c) > 1 - target for c in res.certified)
    assert feasible >= reps * 0.8
    assert np.mean(rates) > 0.1  # useful: commits on more than 10 % of items
    assert viol / feasible <= delta + 3 * math.sqrt(delta * (1 - delta) / feasible)


def test_marginal_only_threshold_has_bad_precision_and_ltt_fixes_it():
    """A low threshold has a small marginal wrong rate when few items commit, but poor precision."""
    rng = np.random.default_rng(5)
    pop = population(4000, rng)
    o, t = pop[:2000], pop[2000:]
    res = P.precision_ltt(o, t, target_precision=0.95, delta=0.1)
    assert res.feasible
    assert res.test_precision_lower is not None and res.test_precision_lower >= 0.95 - 1e-9 or \
        res.test_counts["wrong"] / res.test_counts["commits"] <= 0.05
    assert true_error(pop, res.selected) <= 0.08
    assert true_error(pop, 0.3) > 0.1  # a loose threshold would not meet the target


def test_min_commit_p_and_infeasible_cases():
    rng = np.random.default_rng(3)
    pop = population(4000, rng)
    o, t = pop[:2000], pop[2000:]
    res = P.precision_ltt(o, t, target_precision=0.9, delta=0.1, min_commit_p=0.97)
    assert res.selected is None or res.selected >= 0.97
    small = population(30, rng)
    res2 = P.precision_ltt(small[:15], small[15:], target_precision=0.99, delta=0.1)
    assert not res2.feasible and res2.selected is None and res2.test_precision_lower is None
    all_wrong = [P.PrecisionItem(True, 0.99, True)] * 100
    assert not P.precision_ltt(all_wrong, all_wrong, target_precision=0.5, delta=0.1).feasible
    with pytest.raises(ValueError):
        P.precision_ltt(o, t, [math.inf], target_precision=0.9, delta=0.1)
    with pytest.raises(ValueError):
        P.precision_ltt(o, t, target_precision=1.0, delta=0.1)
    d = res.to_dict()
    assert d["target_precision"] == 0.9 and abs(d["beta"] - 0.1) < 1e-12


def test_curve_and_items_from_dicts():
    items = P.items_from_dicts([{"can_commit": True, "p_top1": 0.9, "wrong": False},
                                {"can_commit": True, "p_top1": 0.5, "wrong": True},
                                {"can_commit": False, "p_top1": 0.95, "wrong": False}])
    cur = {r["commit_p"]: r for r in P.precision_curve(items, [0.9, 0.5, 0.0])}
    assert cur[0.9]["commits"] == 1 and cur[0.9]["precision"] == 1.0
    assert cur[0.5]["commits"] == 2 and cur[0.5]["precision"] == 0.5


# --- calibrate(target_precision=) end to end ---------------------------------------------


@pytest.fixture(scope="module")
def nbest_pair():
    xs, ts = nbest_data(600, 0)
    rng = np.random.default_rng(1)
    null = [noise_nbest(rng) for _ in range(60)]
    kw = dict(null_inputs=null, null_trials=60, decoder_name="test-nbest", modality="emg")
    base = ft.calibrate(xs, ts, **kw)
    prec = ft.calibrate(xs, ts, target_precision=0.9, **kw)
    return base, prec, xs, ts


def test_default_path_unchanged(nbest_pair):
    base, _, _, _ = nbest_pair
    assert base.sheet.precision is None
    assert "precision" not in base.sheet.to_dict()
    assert "precision bound" not in str(base.sheet)
    assert base.precision_items is None


def test_precision_guard_composes_with_base(nbest_pair):
    base, prec, xs, ts = nbest_pair
    q = prec.sheet.precision
    assert q is not None and q["target_precision"] == 0.9 and q["min_commits"] == 22
    c0 = base.sheet.commit_threshold
    c = prec.sheet.commit_threshold
    assert c >= c0  # never below the P14-03 threshold: the marginal bound still holds
    assert all(cr.passed for cr in prec.sheet.controls)
    assert prec.config_id != base.config_id
    assert prec.config.recipe["precision_bound"]["target_precision"] == 0.9
    assert prec.alpha == base.alpha and prec.delta == base.delta
    if q["feasible"]:
        # the LTT counts are the final guard's in-sample counts (the commit rule is monotone in commit_p)
        assert (prec.sheet.ltt_commits, prec.sheet.ltt_wrong_commits) == (q["test_counts"]["commits"],
                                                                          q["test_counts"]["wrong"])
        assert not any("not monotone" in w for w in prec.sheet.warnings)
    assert len(prec.precision_items["order"]) == prec.sheet.n_policy
    assert len(prec.precision_items["test"]) == prec.sheet.n_ltt
    text = str(prec.sheet)
    assert "precision bound" in text and "error rate among commits" in text
    assert not any(a.startswith("The error rate among commits") for a in prec.sheet.not_guaranteed)


def test_precision_guard_on_new_data(nbest_pair):
    _, prec, _, _ = nbest_pair
    if not prec.sheet.precision["feasible"]:
        pytest.skip("not feasible on this draw")
    xs, ts = nbest_data(800, 99)
    res = [prec._decide_quiet(x) for x in xs]
    com = [(r, t) for r, t in zip(res, ts) if r.action == "commit"]
    assert com
    err = sum(r.text != t for r, t in com) / len(com)
    assert err <= 0.1 + 3 * math.sqrt(0.1 * 0.9 / len(com))


def test_save_load_roundtrip(nbest_pair, tmp_path):
    _, prec, xs, _ = nbest_pair
    path = prec.save(tmp_path / "g.json")
    g2 = ft.load(path)
    assert g2.config_id == prec.config_id
    assert g2.sheet.precision == prec.sheet.precision
    assert g2.decide(xs[0]).action == prec.decide(xs[1 - 1]).action


def test_logits_route_runs():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(80)]
    g = ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON,
                     null_trials=20, null_max_commit_rate=0.1, decoder_name="test-ctc", target_precision=0.8,
                     precision_delta=0.2)
    q = g.sheet.precision
    assert q["delta_p"] == 0.2 and q["n_test"] == g.sheet.n_ltt
    base = q["base_commit_p"]
    assert g.sheet.commit_threshold >= (math.inf if base == "inf" else base)


def test_bad_arguments():
    xs, ts = nbest_data(60, 2)
    null = [noise_nbest(np.random.default_rng(0)) for _ in range(20)]
    with pytest.raises(ValueError, match="target_precision"):
        ft.calibrate(xs, ts, null_inputs=null, target_precision=1.0)
    with pytest.raises(ValueError, match="need target_precision"):
        ft.calibrate(xs, ts, null_inputs=null, precision_delta=0.1)
    with pytest.raises(ValueError, match="finite"):
        ft.calibrate(xs, ts, null_inputs=null, target_precision=0.9, precision_grid=[math.inf])
    # since P5-02 completion, target_precision combines with the hallucination bound (joint LTT); see
    # tests/test_trust_p5_02_sheets_online.py::test_calibrate_precision_with_halluc_bound
