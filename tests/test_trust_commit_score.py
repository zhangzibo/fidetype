"""Tests of the learned commit-confidence score of the drop-in guard (P5-23)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import commit_score as C
from fidetype.trust import dropin as D
from fidetype.trust.guarantee_sheet import load_sheets, policy_sheets, save_sheets
from fidetype.trust.types import Candidate

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits, nbest_data, noise_nbest


@pytest.fixture(scope="module")
def nbest_cal() -> tuple[list, list[str], list]:
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    return xs, ts, [noise_nbest(rng) for _ in range(60)]


@pytest.fixture(scope="module")
def learned_guard(nbest_cal) -> ft.TrustGuard:
    xs, ts, nulls = nbest_cal
    return ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg",
                        confidence="learned")


# --- the model ------------------------------------------------------------------------------


def test_fit_logistic_recovers_a_known_direction():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((400, 2))
    y = (1.0 / (1.0 + np.exp(-(2.0 * X[:, 0] - 1.0 * X[:, 1]))) > rng.uniform(size=400)).astype(float)
    coef, b = C.fit_logistic(X, y, l2=1.0)
    assert coef[0] > 1.0 and coef[1] < -0.4 and abs(b) < 0.5
    coef2, b2 = C.fit_logistic(X, y, l2=1.0)
    assert np.array_equal(coef, coef2) and b == b2  # deterministic


def test_features_of_one_nbest():
    cands = [Candidate("call my wife", 0.0, logp_acoustic=-6.0, logp_lm=-9.0, char_confidences=(0.9,) * 12),
             Candidate("call my life", -1.0, logp_acoustic=-5.0, logp_lm=-12.0, char_confidences=(0.5,) * 12)]
    post = np.array([0.75, 0.25])
    f = dict(zip(C.FEATURES, C.commit_features(0.75, 0.1, post, cands, n_frames=60)))
    assert f["p_top1"] == 0.75 and f["margin"] == pytest.approx(0.5)
    assert f["logit_p_top1"] == pytest.approx(math.log(3.0))
    assert f["word_agreement"] == pytest.approx((1.0 + 1.0 + 0.75) / 3)
    assert f["char_conf_mean"] == pytest.approx(0.9) and f["char_conf_min"] == pytest.approx(0.9)
    assert f["acoustic_per_char"] == pytest.approx(-6.0 / 12) and f["acoustic_gap"] == pytest.approx(1.0 / 12)
    assert f["lm_per_word"] == pytest.approx(-3.0) and f["frames_per_char"] == pytest.approx(5.0)
    assert f["log_n_words"] == pytest.approx(math.log(4.0)) and f["guard_risk"] == 0.1
    g = C.commit_features(0.0, 1.0, [], [], None)
    assert g.shape == (len(C.FEATURES),) and math.isnan(g[C.FEATURES.index("margin")])


def test_signs_hold_and_clipping_stops_extrapolation():
    rng = np.random.default_rng(2)
    n = 300
    X = np.full((n, len(C.FEATURES)), np.nan)
    p = rng.uniform(0.2, 1.0, n)
    X[:, 0] = p
    X[:, 1] = np.log(p / (1 - p + 1e-9))
    X[:, C.FEATURES.index("guard_risk")] = rng.uniform(0, 0.5, n)
    y = rng.uniform(size=n) < p
    # a feature that the labels push to the wrong sign: guard risk higher on right items
    X[:, C.FEATURES.index("guard_risk")] += 0.3 * y
    m = C.LearnedCommitScore.fit(X, y)
    for f, c, s in zip(C.FEATURES, m.coef, C.SIGNS):
        assert s * c >= 0, (f, c)
    assert "guard_risk" in m.dropped
    x = X[0].copy()
    x[0] = 50.0  # far outside the fit range: clipped to the largest fit value
    x2 = X[0].copy()
    x2[0] = float(np.nanmax(X[:, 0]))
    assert m.score(x) == pytest.approx(m.score(x2))
    d = m.to_dict()
    json.dumps(d, allow_nan=False)
    assert C.LearnedCommitScore.from_dict(d) == m


def test_score_file_checks():
    with pytest.raises(ValueError, match="schema"):
        C.LearnedCommitScore.from_dict({"schema": "x"})
    m = C.LearnedCommitScore.fit(np.random.default_rng(0).uniform(size=(20, len(C.FEATURES))), [True, False] * 10)
    d = m.to_dict()
    d["features"] = list(d["features"])[::-1]
    with pytest.raises(ValueError, match="features"):
        C.LearnedCommitScore.from_dict(d)


# --- calibrate(confidence="learned") ------------------------------------------------------------


def test_default_is_unchanged(nbest_cal):
    xs, ts, nulls = nbest_cal
    a = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg")
    b = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg",
                     confidence="p_top1")
    assert a.config_id == b.config_id and a.commit_score is None
    assert "commit_score" not in a.config.recipe and "confidence" not in a.sheet.to_dict()
    assert all("commit_score" not in s.status for s in policy_sheets(a))
    r = a._decide_quiet(xs[0])
    assert r.commit_score is None


def test_learned_guard_split_sheet_and_guarantee(learned_guard, nbest_cal):
    g = learned_guard
    s = g.sheet
    cf = s.confidence
    assert cf and cf["kind"] == "learned" and cf["features"] == list(C.FEATURES)
    # three-way split: score fitted on fit + policy-grid items, certified on the disjoint LTT items
    assert cf["fit_items"] == s.n_fit + s.n_policy and cf["certify_items"] == s.n_ltt
    assert cf["fit_items"] + cf["certify_items"] == s.n_items
    assert g.config.recipe["commit_score_split"]["n_certify"] == s.n_ltt
    assert math.isinf(g.config.policy["commit_p"])  # the trust layer alone never commits
    assert s.commit_threshold == g.commit_score.threshold and math.isfinite(s.commit_threshold)
    assert s.feasible and g.config.risk_control["score"] == "learned"
    assert all(c.passed for c in s.controls)
    text = str(s)
    assert "learned commit score >=" in text and "certified on" in text
    xs, ts = nbest_data(400, 7)
    rs = g.decide_many(xs)
    assert all(r.commit_score is not None and 0.0 < r.commit_score < 1.0 for r in rs)
    com = [(r, t) for r, t in zip(rs, ts) if r.action == "commit"]
    assert com
    assert all(r.commit_score >= s.commit_threshold for r, _ in com)
    assert all(r.reason.startswith("commit: learned commit score") for r, _ in com)
    assert all(r.action != "commit" or r.text for r in rs)
    wrong = sum(r.text != t for r, t in com)
    assert wrong / len(rs) <= 0.05 + 0.03  # one held-out draw; the bound holds with prob >= 1 - delta
    assert all("commit_score" in rec for rec in g.audit_log)


def test_learned_guard_round_trips_and_config_id_covers_the_score(learned_guard, tmp_path: Path):
    g = learned_guard
    p = g.save(tmp_path / "g.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["config"]["recipe"]["commit_score"]["schema"] == C.SCORE_SCHEMA
    g2 = ft.load(p)
    assert g2.config_id == g.config_id and g2.sheet == g.sheet and g2.commit_score == g.commit_score
    xs, _ = nbest_data(50, 9)
    a = [g._decide_quiet(x) for x in xs]
    b = [g2._decide_quiet(x) for x in xs]
    assert [(r.action, r.text, r.commit_score) for r in a] == [(r.action, r.text, r.commit_score) for r in b]
    # a changed weight changes the config id
    d["config"]["recipe"]["commit_score"]["coef"][0] += 0.5
    cfg2 = D.FrozenTrustConfig.from_dict(d["config"])
    assert cfg2.config_id != g.config_id
    # the policy sheets show the learned score and round-trip
    sh = policy_sheets(g)
    assert sh[0].policy_type == "offline_ltt" and sh[0].status["commit_score"] == "learned"
    assert sh[0].calibration["score_fit_items"] == g.sheet.confidence["fit_items"]
    assert load_sheets(save_sheets(sh, tmp_path / "s.json")) == sh


def test_learned_guard_logits_route():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    g = ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=40,
                     decoder_name="test-ctc", confidence="learned")
    assert all(c.passed for c in g.sheet.controls)
    coef = g.sheet.confidence["coef"]
    assert coef["char_conf_mean"] != 0.0 or coef["char_conf_min"] != 0.0 or coef["p_top1"] != 0.0
    r = g(fake_logits("good morning", rng))
    assert r.commit_score is not None


def test_learned_option_checks(nbest_cal, learned_guard):
    xs, ts, nulls = nbest_cal
    with pytest.raises(ValueError, match="confidence must be"):
        ft.calibrate(xs, ts, null_inputs=nulls, confidence="bogus")
    with pytest.raises(ValueError, match="cannot be combined"):
        ft.calibrate(xs, ts, null_inputs=nulls, confidence="learned", target_precision=0.9)
    with pytest.raises(ValueError, match="confidence_l2"):
        ft.calibrate(xs, ts, null_inputs=nulls, confidence="learned", confidence_l2=0.0)
    with pytest.raises(ValueError, match="online"):
        learned_guard.online()
    bad = learned_guard.config.with_policy(commit_p=0.5)
    with pytest.raises(ValueError, match="commit_p = inf"):
        D.TrustGuard(bad, learned_guard._codec)


def test_null_controls_run_on_the_learned_guard(nbest_cal):
    xs, ts, nulls = nbest_cal
    # null inputs equal to real calibration inputs: a guard that commits on them must be refused
    with pytest.raises(ft.NullControlError):
        ft.calibrate(xs, ts, null_inputs=xs[:60], null_trials=60, confidence="learned", null_max_commit_rate=0.0)
