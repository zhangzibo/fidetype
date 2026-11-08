"""Tests of fidetype.trust.conformal."""

import math

import numpy as np
import pytest

from fidetype.trust.conformal import (
    AdaptiveConformal,
    SplitConformal,
    WordConformal,
    conformal_quantile,
    nonconformity,
    word_posteriors,
)
from fidetype.trust.testing import drifting_posteriors


def test_quantile_rank():
    s = np.arange(1, 10) / 10.0  # 9 scores
    assert conformal_quantile(s, 0.1) == pytest.approx(0.9)  # rank ceil(10*0.9) = 9
    assert conformal_quantile(s[:5], 0.1) == math.inf  # rank 6 > 5


def test_nonconformity_scores():
    p = np.array([0.6, 0.3, 0.1])
    assert nonconformity(p, 1, "lac") == pytest.approx(0.7)
    assert nonconformity(p, 1, "aps") == pytest.approx(0.9)
    assert nonconformity(p, -1) == math.inf


@pytest.mark.parametrize("score", ["lac", "aps"])
def test_split_conformal_coverage_held_out(score):
    """Stationary but mis-calibrated posteriors: coverage still holds."""
    rng = np.random.default_rng(0)
    data = drifting_posteriors(3000, rng, temp_start=0.6, temp_end=0.6)
    cal, test = data[:1000], data[1000:]
    alpha = 0.1
    sc = SplitConformal(alpha, score).fit([p for p, _ in cal], [y for _, y in cal])
    ev = sc.evaluate([p for p, _ in test], [y for _, y in test])
    assert ev["coverage"] >= 1 - alpha - 0.025
    assert ev["miss_rate"] == 0.0
    assert ev["mean_set_size"] < 10  # smaller than the full list


def test_conditional_vs_marginal_with_misses():
    rng = np.random.default_rng(1)
    data = drifting_posteriors(2000, rng, temp_start=1.0, temp_end=1.0)
    # Remove the truth from 30 % of the lists.
    idx = [y if rng.random() > 0.3 else -1 for _, y in data]
    posts = [p for p, _ in data]
    cond = SplitConformal(0.1, mode="conditional").fit(posts[:1000], idx[:1000])
    ev = cond.evaluate(posts[1000:], idx[1000:])
    assert ev["coverage_in_nbest"] >= 0.9 - 0.03
    assert 0.25 < ev["miss_rate"] < 0.35
    marg = SplitConformal(0.1, mode="marginal").fit(posts[:1000], idx[:1000])
    assert marg.q == math.inf  # miss rate 0.3 > alpha
    ev2 = marg.evaluate(posts[1000:], idx[1000:])
    assert ev2["coverage_with_other"] == 1.0
    assert ev2["mean_set_size"] == 10


def test_word_sets_hand_case():
    texts = ["the cat sat", "the hat sat", "the cat set"]
    p = np.array([0.5, 0.3, 0.2])
    wp = word_posteriors(texts, p)
    assert wp[0] == {"the": pytest.approx(1.0)}
    assert wp[1] == {"cat": pytest.approx(0.7), "hat": pytest.approx(0.3)}
    wc = WordConformal(0.1)
    wc.q = 0.75  # include words with posterior >= 0.25
    sets = wc.predict(texts, p)
    assert sets[1] == ["cat", "hat"]
    assert sets[2] == ["sat"]
    wc2 = WordConformal(0.2).fit([texts] * 20, [p] * 20, ["the hat sat"] * 20)
    ev = wc2.evaluate([texts], [p], ["the hat sat"])
    assert ev["word_coverage"] == 1.0


def test_adaptive_conformal_tracks_target_on_drift():
    """Over-confidence grows with time. Static split conformal under-covers
    late in the session; ACI keeps the long-run miss rate near alpha."""
    rng = np.random.default_rng(2)
    alpha, n = 0.1, 3000
    data = drifting_posteriors(n + 300, rng, temp_start=1.0, temp_end=0.3)
    cal, stream = data[:300], data[300:]
    static = SplitConformal(alpha).fit([p for p, _ in cal], [y for _, y in cal])
    static_err = np.array([not static.predict(p).covers(y) for p, y in stream])
    aci = AdaptiveConformal(alpha, gamma=0.02, history=[nonconformity(p, y) for p, y in cal], window=300)
    for p, y in stream:
        aci.step(p, y)
    aci_err = np.array(aci.errors)
    late = slice(2 * n // 3, n)
    assert static_err[late].mean() > alpha + 0.05  # static fails under drift
    assert abs(aci_err.mean() - alpha) < 0.02  # ACI long-run guarantee
    assert abs(aci_err[late].mean() - alpha) < 0.04
    # Gibbs & Candes bound on the average error.
    bound = (max(alpha, 1 - alpha) + aci.gamma) / (aci.gamma * n)
    assert abs(aci_err.mean() - alpha) <= bound + 1e-9
