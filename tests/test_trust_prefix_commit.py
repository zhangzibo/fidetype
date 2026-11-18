"""Tests of certified word-prefix commits in the drop-in guard (P5-24)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.benchmark.safe_wpm import guarantee_from_sheet, prefix_outcome, safe_wpm
from fidetype.trust import commit_score as C
from fidetype.trust.guarantee_sheet import policy_sheets
from fidetype.trust.types import Candidate

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits, nbest_data, noise_nbest


@pytest.fixture(scope="module")
def nbest_cal() -> tuple[list, list[str], list]:
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    return xs, ts, [noise_nbest(rng) for _ in range(60)]


@pytest.fixture(scope="module")
def prefix_guard(nbest_cal) -> ft.TrustGuard:
    xs, ts, nulls = nbest_cal
    return ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg",
                        confidence="learned", commit_unit="prefix")


# --- the helpers ------------------------------------------------------------------------------


def test_prefix_right_and_monotone_scores():
    assert C.prefix_right("i need help".split(), "i need water".split()).tolist() == [True, True, False]
    # the complete prefix claims the whole sentence
    assert C.prefix_right("i need".split(), "i need water".split()).tolist() == [True, False]
    assert C.prefix_right("i need water".split(), "i need water".split()).tolist() == [True, True, True]
    assert C.prefix_right("i need water now".split(), "i need water".split()).tolist() == [True, True, True, False]
    assert C.prefix_right([], ["x"]).tolist() == []
    m = C.monotone_prefix_scores([0.9, 0.95, 0.5, 0.7])
    assert m.tolist() == [0.9, 0.9, 0.5, 0.5]
    assert C.longest_prefix(m, 0.8) == 2 and C.longest_prefix(m, 0.95) == 0 and C.longest_prefix(m, 0.1) == 4


def test_prefix_features_of_one_nbest():
    cands = [Candidate("call my wife", 0.0, logp_acoustic=-6.0, logp_lm=-9.0, char_confidences=(0.9,) * 12),
             Candidate("call my life", -1.0, logp_acoustic=-5.0, logp_lm=-12.0, char_confidences=(0.5,) * 12),
             Candidate("tall my wife", -2.0, logp_acoustic=-7.0, logp_lm=-12.0)]
    post = np.array([0.6, 0.3, 0.1])
    sf = C.commit_features(0.6, 0.1, post, cands, n_frames=60)
    P = C.prefix_features(sf, post, cands)
    assert P.shape == (3, len(C.PREFIX_FEATURES))
    f = [dict(zip(C.PREFIX_FEATURES, r)) for r in P]
    # mass of the candidates that share the prefix
    assert f[0]["prefix_mass"] == pytest.approx(0.9) and f[1]["prefix_mass"] == pytest.approx(0.9)
    assert f[2]["prefix_mass"] == pytest.approx(0.6)
    assert f[2]["prefix_agree_min"] == pytest.approx(0.7) and f[0]["prefix_agree_min"] == pytest.approx(0.9)
    assert f[0]["complete"] == 0.0 and f[2]["complete"] == 1.0 and f[1]["prefix_share"] == pytest.approx(2 / 3)
    assert f[0]["prefix_char_conf_mean"] == pytest.approx(0.9)
    assert f[0]["p_top1"] == 0.6 and f[2]["acoustic_per_char"] == pytest.approx(-0.5)
    assert C.prefix_features(sf, [], []).shape == (0, len(C.PREFIX_FEATURES))


def test_ltt_prefix_threshold_is_monotone_and_safe():
    # 100 items: 3-word prefixes with scores [0.9, 0.8, 0.7]; the third word is wrong on half of the items
    scores = [C.monotone_prefix_scores([0.9, 0.8, 0.7]) for _ in range(100)]
    right = [np.array([True, True, i % 2 == 0]) for i in range(100)]
    r = C.ltt_prefix_threshold(scores, right, alpha=0.1, delta=0.1, grid=np.round(np.arange(1.0, -0.001, -0.01), 2))
    # at 0.7 half the items commit a wrong full prefix (risk 0.5): the test stops above it
    assert r["feasible"] and r["threshold"] == pytest.approx(0.71) and r["empirical_risk"] == 0.0
    few = C.ltt_prefix_threshold([np.zeros(0)] * 5, [np.zeros(0, bool)] * 5, alpha=0.05, delta=0.1, grid=[0.5])
    assert not few["feasible"] and math.isinf(few["threshold"])  # 5 items cannot certify anything
    bad = C.ltt_prefix_threshold([np.array([0.9])] * 60, [np.array([False])] * 60, alpha=0.05, delta=0.1,
                                 grid=[0.95, 0.9])
    assert bad["threshold"] == 0.95 and bad["commit_rate"] == 0.0  # 0.9 fails (all wrong); 0.95 commits nothing


def test_prefix_score_file_round_trip():
    rng = np.random.default_rng(0)
    X = rng.uniform(size=(60, len(C.PREFIX_FEATURES)))
    m = C.LearnedCommitScore.fit(X, rng.uniform(size=60) < X[:, 0], unit="prefix")
    d = m.to_dict()
    assert d["schema"] == C.PREFIX_SCORE_SCHEMA and d["unit"] == "prefix"
    assert C.LearnedCommitScore.from_dict(d) == m
    d2 = dict(d, unit="sentence")
    with pytest.raises(ValueError, match="schema"):
        C.LearnedCommitScore.from_dict(d2)
    with pytest.raises(ValueError, match="unit"):
        C.LearnedCommitScore.fit(X, X[:, 0] > 0.5, unit="word")
    # a sentence score keeps the P5-23 bytes (no "unit" key)
    s = C.LearnedCommitScore.fit(rng.uniform(size=(20, len(C.FEATURES))), [True, False] * 10)
    assert "unit" not in s.to_dict() and s.unit == "sentence"


# --- calibrate(commit_unit="prefix") -----------------------------------------------------------


def test_prefix_option_checks(nbest_cal):
    xs, ts, nulls = nbest_cal
    with pytest.raises(ValueError, match="needs confidence"):
        ft.calibrate(xs, ts, null_inputs=nulls, commit_unit="prefix")
    with pytest.raises(ValueError, match="commit_unit must be"):
        ft.calibrate(xs, ts, null_inputs=nulls, confidence="learned", commit_unit="word")


def test_prefix_guard_sheet_split_and_guarantee(prefix_guard):
    g = prefix_guard
    s = g.sheet
    cf = s.confidence
    assert g.commit_unit == "prefix" and cf["unit"] == "prefix" and cf["features"] == list(C.PREFIX_FEATURES)
    assert cf["fit_items"] == s.n_fit + s.n_policy and cf["certify_items"] == s.n_ltt
    assert cf["fit_rows"] > cf["fit_items"]  # one row per prefix
    assert g.config.recipe["commit_unit"] == "prefix" and g.config.risk_control["risk"] == "wrong-prefix-commit"
    assert math.isinf(g.config.policy["commit_p"]) and math.isfinite(s.commit_threshold)
    assert all(c.passed for c in s.controls)
    text = str(s)
    assert "learned prefix score >=" in text and "first words of the" in text and "prefix rows" in text
    assert "prefix" in s.method
    sh = policy_sheets(g)
    assert sh[0].status["commit_unit"] == "prefix" and "prefix" in sh[0].risk["name"]
    assert guarantee_from_sheet(s.to_dict())["risk"] == "wrong-prefix-commit"


def test_prefix_guard_decisions_and_bound(prefix_guard):
    g = prefix_guard
    xs, ts = nbest_data(400, 7)
    rs = g.decide_many(xs)
    com = [(r, t) for r, t in zip(rs, ts) if r.action == "commit"]
    assert com
    for r, t in com:
        assert r.commit_unit == "prefix" and r.n_words_committed == len(r.text.split()) >= 1
        assert r.event["commit_unit"] == "prefix" and r.event["n_words_committed"] == r.n_words_committed
        assert r.event["complete"] == r.complete and r.event["n_words_top1"] >= r.n_words_committed
        assert r.commit_score >= g.sheet.commit_threshold
        assert r.reason.startswith("commit ") and "learned prefix score" in r.reason
    assert all(r.action != "commit" or r.text for r in rs)
    assert all(r.n_words_committed is None and r.complete is None for r in rs if r.action != "commit")
    wrong = sum(not g.is_right(r, t) for r, t in com)
    assert wrong / len(rs) <= 0.05 + 0.03  # one held-out draw
    # the audit log says how many words were committed
    recs = [rec for rec in g.audit_log if rec.get("user_action") == "commit"]
    assert recs and all("n_words_committed" in rec for rec in recs)
    # safe-wpm/0.2 scores the decisions with the prefix bound
    outs = [prefix_outcome(r.text, t, bool(r.complete)) if r.action == "commit" else None for r, t in zip(rs, ts)]
    v = safe_wpm([o is not None for o in outs], [bool(o and o["correct"]) for o in outs],
                 [len(t.split()) for t in ts], [len(t) for t in ts], [2.0] * len(ts),
                 guarantee=guarantee_from_sheet(g.sheet.to_dict()), metric_version="0.2",
                 committed_words=[o["committed_words"] if o else math.nan for o in outs],
                 complete=[bool(o and o["complete"]) for o in outs],
                 penalty_chars=[o["penalty_chars"] if o else math.nan for o in outs])
    assert v["status"] in ("certified", "above-alpha") and v["n_commits"] == len(com)
    assert v["n_wrong_commits"] == wrong


def test_is_right_rule(prefix_guard):
    r = ft.TrustResult(action="commit", text="i need", choices=("i need",), p_top1=0.5, guard_risk=0.0, reason="",
                       raw_action="COMMIT", config_id="x", seq=0, commit_unit="prefix", n_words_committed=2,
                       complete=False)
    assert prefix_guard.is_right(r, "i need help") and not prefix_guard.is_right(r, "i am here")
    r2 = ft.TrustResult(action="commit", text="i need", choices=("i need",), p_top1=0.5, guard_risk=0.0, reason="",
                        raw_action="COMMIT", config_id="x", seq=0, commit_unit="prefix", n_words_committed=2,
                        complete=True)
    assert not prefix_guard.is_right(r2, "i need help") and prefix_guard.is_right(r2, "i need")
    r3 = ft.TrustResult(action="offer", text=None, choices=("a",), p_top1=0.5, guard_risk=0.0, reason="",
                        raw_action="OFFER", config_id="x", seq=0)
    assert prefix_guard.is_right(r3, "a") is None


def test_prefix_guard_round_trips(prefix_guard, tmp_path: Path):
    g = prefix_guard
    p = g.save(tmp_path / "g.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["config"]["recipe"]["commit_score"]["schema"] == C.PREFIX_SCORE_SCHEMA
    g2 = ft.load(p)
    assert g2.config_id == g.config_id and g2.commit_unit == "prefix" and g2.sheet == g.sheet
    xs, _ = nbest_data(60, 9)
    a = [g._decide_quiet(x) for x in xs]
    b = [g2._decide_quiet(x) for x in xs]
    key = lambda r: (r.action, r.text, r.commit_score, r.n_words_committed, r.complete)  # noqa: E731
    assert [key(r) for r in a] == [key(r) for r in b]
    with pytest.raises(ValueError, match="prefix"):
        g.online()


def test_prefix_guard_logits_route_and_null_controls():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    g = ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=40,
                     decoder_name="test-ctc", confidence="learned", commit_unit="prefix")
    # the null controls ran on the prefix guard (every prefix commit counts)
    assert {c.name for c in g.sheet.controls} >= {"uniform", "shuffled"} and all(c.passed for c in g.sheet.controls)
    r = g(fake_logits("good morning", rng))
    assert r.commit_unit == "prefix" and (r.action != "commit" or r.n_words_committed >= 1)


def test_null_controls_refuse_a_prefix_guard_that_commits_on_null_input(nbest_cal):
    xs, ts, _ = nbest_cal
    with pytest.raises(ft.NullControlError):
        ft.calibrate(xs, ts, null_inputs=xs[:60], null_trials=60, confidence="learned", commit_unit="prefix",
                     null_max_commit_rate=0.0)


def test_sentence_default_unchanged(nbest_cal):
    xs, ts, nulls = nbest_cal
    a = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg",
                     confidence="learned")
    b = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg",
                     confidence="learned", commit_unit="sentence")
    assert a.config_id == b.config_id and a.commit_unit == "sentence" and "commit_unit" not in a.config.recipe
    r = a._decide_quiet(xs[0])
    assert r.commit_unit == "sentence" and "commit_unit" not in r.event
    assert r.action != "commit" or (r.complete is True and r.n_words_committed == len(r.text.split()))
