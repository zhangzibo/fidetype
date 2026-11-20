"""Tests of the P14-05 safe-WPM metric (fidetype.benchmark.safe_wpm), its scorer block, leaderboard cell and CLI."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from fidetype.benchmark.leaderboard import safe_wpm_text
from fidetype.benchmark.safe_wpm import (
    DEFAULT_S_PER_CHAR,
    CorrectionRule,
    certification,
    controls_from_sheet,
    guarantee_from_sheet,
    model_neural_s,
    safe_wpm,
)

LTT = {"method": "ltt", "alpha": 0.5, "delta": 0.1, "n_cal": 100}


def test_hand_computed_value() -> None:
    # 1 right commit (2 words), 1 wrong commit (15 chars), 1 offer.
    r = safe_wpm([True, True, False], [True, False, True], [2, 4, 2], [11, 15, 7], [3.0, 4.0, 2.0], guarantee=LTT)
    pen = 2.0 + DEFAULT_S_PER_CHAR * 15
    assert r["status"] == "certified"
    assert r["value"] == pytest.approx(60 * 2 / (9.0 + pen))
    assert r["wpm_no_penalty"] == pytest.approx(60 * 2 / 9.0)
    assert r["n_commits"] == 2 and r["n_wrong_commits"] == 1 and r["committed_correct_words"] == 2
    assert r["measured_wrong_commit"] == pytest.approx(1 / 3)
    assert r["alpha"] == 0.5 and r["delta"] == 0.1 and r["n_cal"] == 100 and r["method"] == "ltt"


def test_offered_text_counts_zero_even_if_right() -> None:
    # "correct" is ignored where nothing is committed.
    r = safe_wpm([False, False], [True, True], [5, 5], [20, 20], [5.0, 5.0], guarantee=LTT)
    assert r["status"] == "vacuous" and r["value"] == 0.0 and r["committed_correct_words"] == 0


def test_no_bound_is_not_certified() -> None:
    r = safe_wpm([True], [True], [3], [12], [4.0], guarantee={"method": "none"})
    assert r["status"] == "not-certified" and r["value"] is None
    assert r["unguarded_wpm"] == pytest.approx(45.0)
    r2 = safe_wpm([True], [True], [3], [12], [4.0], guarantee=None)
    assert r2["status"] == "not-certified"


def test_infeasible_guarantee_certifies_only_no_commits() -> None:
    """P5-30: feasible false + at least one commit -> not-certified; feasible false + no commit -> vacuous."""
    g = {**LTT, "feasible": False}
    r = safe_wpm([True, False], [True, False], [3, 3], [12, 12], [4.0, 4.0], guarantee=g)
    assert r["status"] == "not-certified" and r["value"] is None and r["ci"] is None
    assert "P5-30" in r["note"] and r["unguarded_wpm"] == pytest.approx(60 * 3 / 8.0)
    assert "ABOVE" not in safe_wpm_text(r)
    r0 = safe_wpm([False, False], [True, False], [3, 3], [12, 12], [4.0, 4.0], guarantee=g)
    assert r0["status"] == "vacuous" and r0["value"] == 0.0 and "never commits" in r0["note"]
    # v0.2 (sentence and prefix commits) follows the same rule
    gp = {**g, "risk": "wrong-prefix-commit"}
    r2 = safe_wpm([True, False], [True, False], [3, 3], [12, 12], [4.0, 4.0], guarantee=gp, metric_version="0.2",
                  complete=[False, True], committed_words=[1, 0], penalty_chars=[4, 0])
    assert r2["status"] == "not-certified" and r2["value"] is None and "P5-30" in r2["note"]
    r3 = safe_wpm([False], [False], [3], [12], [4.0], guarantee=gp, metric_version="0.2")
    assert r3["status"] == "vacuous"
    # a feasible guarantee is unchanged
    assert safe_wpm([True], [True], [3], [12], [4.0], guarantee={**LTT, "feasible": True})["status"] == "certified"
    # an earlier v0.2 reason (prefix commits under a sentence bound) keeps its note
    r4 = safe_wpm([True], [True], [3], [12], [4.0], guarantee=g, metric_version="0.2", complete=[False],
                  committed_words=[1], penalty_chars=[4])
    assert r4["status"] == "not-certified" and "wrong-prefix" in r4["note"]
    # the drop-in sheet route
    sheet = {"alpha": 0.05, "delta": 0.1, "n_ltt": 271, "n_items": 722, "n_fit": 180, "n_policy": 271,
             "feasible": False, "config_id": "tcfg-x"}
    r5 = safe_wpm([True], [True], [3], [12], [4.0], guarantee=guarantee_from_sheet(sheet))
    assert r5["status"] == "not-certified"


def test_above_alpha_is_marked() -> None:
    g = {"method": "crc", "alpha": 0.05, "n_cal": 50}
    r = safe_wpm([True] * 10, [True] * 8 + [False] * 2, [3] * 10, [12] * 10, [4.0] * 10, guarantee=g)
    assert r["status"] == "above-alpha" and r["value"] is not None
    assert r["delta"] is None and "expectation" in r["confidence"]
    assert "ABOVE alpha" in safe_wpm_text(r)


def test_wrong_commits_cost_time_and_lower_the_value() -> None:
    base = safe_wpm([True, False], [True, False], [3, 3], [12, 12], [4.0, 4.0], guarantee=LTT)
    worse = safe_wpm([True, True], [True, False], [3, 3], [12, 12], [4.0, 4.0], guarantee=LTT)
    assert worse["value"] < base["value"]
    none = safe_wpm([True, True], [True, False], [3, 3], [12, 12], [4.0, 4.0], guarantee=LTT,
                    rule=CorrectionRule(name="none"))
    assert none["value"] == pytest.approx(base["value"])


def test_bad_inputs() -> None:
    with pytest.raises(ValueError):
        safe_wpm([True], [True, False], [1], [1], [1.0], guarantee=LTT)
    with pytest.raises(ValueError):
        safe_wpm([True], [True], [1], [1], [math.nan], guarantee=LTT)
    with pytest.raises(ValueError):
        CorrectionRule(name="magic").penalty(np.array([3.0]))


def test_cluster_ci_brackets_the_value() -> None:
    rng = np.random.default_rng(0)
    n = 200
    cm = rng.random(n) < 0.5
    ok = rng.random(n) < 0.9
    cl = [{"day": f"d{i % 10}"} for i in range(n)]
    r = safe_wpm(cm, ok, np.full(n, 5), np.full(n, 25), rng.uniform(3, 8, n), guarantee={**LTT, "alpha": 0.2},
                 clusters=cl, ci_unit="day", B=300)
    assert r["ci"][0] <= r["value"] <= r["ci"][1]


def test_model_timing_and_certification() -> None:
    assert model_neural_s([60, 30], 60.0).tolist() == [60.0, 30.0]
    assert certification({"method": "ltt", "alpha": 0.05, "delta": 0.1})["certified"]
    assert not certification({"method": "ltt"})["certified"]  # no alpha, no bound


def test_dropin_sheet_helpers() -> None:
    sheet = {"alpha": 0.05, "delta": 0.1, "n_ltt": 271, "n_items": 722, "n_fit": 180, "n_policy": 271,
             "feasible": True, "config_id": "tcfg-x",
             "controls": [{"name": "uniform", "n": 300, "n_commit": 0, "allowed": 15, "passed": True},
                          {"name": "shuffled", "n": 300, "n_commit": 1, "allowed": 15, "passed": True}]}
    g = guarantee_from_sheet(sheet)
    assert g["method"] == "ltt" and g["n_cal"] == 271
    c = controls_from_sheet(sheet)
    assert c["passed"] and c["null_commit"]["commit_rate_zeros"] == 0.0
    r = safe_wpm([True], [True], [3], [12], [4.0], guarantee=g, controls=c)
    assert r["controls"]["passed"] and r["controls"]["shuffled"] == "pass"


def test_scorer_adds_the_block() -> None:
    from fidetype.benchmark.registry import get_track
    from fidetype.benchmark.scoring import build_result, score_trials
    from fidetype.benchmark.submission import TrialOutput

    t = get_track("b2t25-t15-copytask")
    ids = [f"t{i}" for i in range(8)]
    truth = {i: "hello there world" for i in ids}
    clusters = {i: {"day": f"day{k % 2}"} for k, i in enumerate(ids)}
    outs = {i: TrialOutput(trial_id=i, texts=["hello there world" if k < 6 else "yellow there"],
                           action="commit" if k % 2 == 0 else "offer", offer_k=3) for k, i in enumerate(ids)}
    sc = score_trials(t, outs, truth, clusters, ids, durations={i: 2.0 for i in ids})
    assert all(s.neural_measured and s.neural_s == 2.0 for s in sc)
    res = build_result(t, sc, decoder={"name": "d"}, policy={"name": "p"},
                       guarantee={"method": "ltt", "alpha": 0.5, "delta": 0.1, "n_cal": 10}, B=50)
    sw = res["safe_wpm"]
    assert sw["status"] == "certified" and sw["n_commits"] == 4 and sw["n_wrong_commits"] == 1
    assert "measured" in sw["timing"]
    sc2 = score_trials(t, outs, truth, clusters, ids)  # no durations: track rate model
    assert not sc2[0].neural_measured
    assert sc2[0].neural_s == pytest.approx(len("hello there world") * 60 / t.user_model.config["chars_per_min"])


def test_cli(tmp_path, capsys) -> None:
    from fidetype.benchmark.__main__ import main

    p = tmp_path / "t.jsonl"
    rows = [{"committed": True, "correct": True, "truth": "hello world", "neural_s": 3.0},
            {"committed": False, "truth": "not now"}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = tmp_path / "r.json"
    assert main(["safe-wpm", "--trials", str(p), "--method", "ltt", "--alpha", "0.1", "--delta", "0.1"]) == 2
    assert main(["safe-wpm", "--trials", str(p), "--method", "ltt", "--alpha", "0.1", "--delta", "0.1",
                 "--chars-per-min", "60", "--out", str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["status"] == "certified" and r["value"] == pytest.approx(60 * 2 / 10.0)
    assert "rate model" in r["timing"]


# --- safe-wpm/0.2 (P14-26, proposed, not adopted) ------------------------------------------------

LTT_PREFIX = dict(LTT, risk="wrong-prefix-commit")


def test_v02_prefix_outcome() -> None:
    from fidetype.benchmark.safe_wpm import prefix_outcome

    t = "i need some water now"
    assert prefix_outcome("i need", t, False) == {"correct": True, "committed_words": 2, "complete": False,
                                                  "credit_words": 2, "penalty_chars": 6}
    assert prefix_outcome("i need sun", t, False)["correct"] is False
    assert prefix_outcome("i need sun", t, False)["penalty_chars"] == len("i need some")
    # a complete commit claims the whole sentence: a right prefix is still a wrong complete commit
    assert prefix_outcome("i need", t, True) == {"correct": False, "committed_words": 2, "complete": True,
                                                 "credit_words": 0, "penalty_chars": len(t)}
    assert prefix_outcome(t, t, True)["credit_words"] == 5
    # a prefix longer than the truth is wrong
    assert prefix_outcome("i need some water now please", t, False)["correct"] is False
    with pytest.raises(ValueError):
        prefix_outcome("  ", t, False)


def test_v01_is_the_default_and_refuses_v02_fields() -> None:
    a = safe_wpm([True], [True], [2], [11], [3.0], guarantee=LTT)
    assert a["definition"] == "safe-wpm/0.1" and "n_prefix_commits" not in a
    with pytest.raises(ValueError, match="metric_version"):
        safe_wpm([True], [True], [2], [11], [3.0], guarantee=LTT, committed_words=[1])
    with pytest.raises(ValueError, match="metric_version must be"):
        safe_wpm([True], [True], [2], [11], [3.0], guarantee=LTT, metric_version="0.3")


def test_v02_equals_v01_for_sentence_commits() -> None:
    rng = np.random.default_rng(0)
    n = 50
    cm, ok = rng.random(n) < 0.5, rng.random(n) < 0.7
    nw, nc, ns = rng.integers(1, 9, n), rng.integers(5, 40, n), rng.uniform(2, 9, n)
    a = safe_wpm(cm, ok, nw, nc, ns, guarantee=LTT)
    b = safe_wpm(cm, ok, nw, nc, ns, guarantee=LTT, metric_version="0.2")
    assert b["definition"] == "safe-wpm/0.2" and "proposed" in b["definition_status"]
    for k in ("value", "status", "unguarded_wpm", "wpm_no_penalty", "measured_wrong_commit", "n_commits",
              "n_wrong_commits", "committed_correct_words", "minutes_correction"):
        assert a[k] == b[k], k
    assert b["n_prefix_commits"] == 0


def test_v02_hand_computed_prefix_value() -> None:
    from fidetype.benchmark.safe_wpm import prefix_outcome

    truths = ["i need some water", "call my wife", "good morning", "open the window"]
    # trial 0: right prefix (2 words); 1: wrong prefix; 2: right complete; 3: withhold
    outs = [prefix_outcome("i need", truths[0], False), prefix_outcome("call me", truths[1], False),
            prefix_outcome("good morning", truths[2], True), None]
    cm = [o is not None for o in outs]
    r = safe_wpm(cm, [bool(o and o["correct"]) for o in outs], [len(t.split()) for t in truths],
                 [len(t) for t in truths], [3.0, 4.0, 2.0, 5.0], guarantee=LTT_PREFIX, metric_version="0.2",
                 committed_words=[o["committed_words"] if o else math.nan for o in outs],
                 complete=[bool(o and o["complete"]) for o in outs],
                 penalty_chars=[o["penalty_chars"] if o else math.nan for o in outs],
                 speech_s=[2.0, 2.0, 1.0, 3.0], speech_timing="test")
    pen = 2.0 + DEFAULT_S_PER_CHAR * len("call my")
    assert r["status"] == "certified" and r["risk"] == "wrong-prefix-commit"
    assert r["value"] == pytest.approx(60 * (2 + 2) / (14.0 + pen))
    assert r["committed_correct_words"] == 4 and r["n_prefix_commits"] == 2 and r["n_complete_commits"] == 1
    assert r["n_wrong_commits"] == 1 and r["measured_wrong_commit"] == pytest.approx(0.25)
    assert r["speech_time"]["value"] == pytest.approx(60 * 4 / (8.0 + pen))
    # the same prefix decisions under a sentence-level bound are not certified
    r2 = safe_wpm(cm, [bool(o and o["correct"]) for o in outs], [4, 3, 2, 3], [len(t) for t in truths],
                  [3.0, 4.0, 2.0, 5.0], guarantee=LTT, metric_version="0.2",
                  committed_words=[2, 2, 2, math.nan], complete=[False, False, True, False],
                  penalty_chars=[6, 7, 0, math.nan])
    assert r2["status"] == "not-certified" and r2["value"] is None and "wrong-prefix-commit" in r2["note"]
    with pytest.raises(ValueError, match="committed_words"):
        safe_wpm(cm, [True] * 4, [4, 3, 2, 3], [10] * 4, [1.0] * 4, guarantee=LTT_PREFIX, metric_version="0.2",
                 complete=[False, True, True, True])


def test_v02_guarantee_from_a_prefix_sheet() -> None:
    sheet = {"alpha": 0.05, "delta": 0.1, "n_ltt": 271, "n_items": 722, "n_fit": 180, "n_policy": 271,
             "confidence": {"unit": "prefix"}}
    assert guarantee_from_sheet(sheet)["risk"] == "wrong-prefix-commit"
    assert "risk" not in guarantee_from_sheet(dict(sheet, confidence={"kind": "learned"}))


def test_v02_cli(tmp_path) -> None:
    from fidetype.benchmark.__main__ import main

    p = tmp_path / "t.jsonl"
    rows = [{"committed": True, "committed_text": "hello", "complete": False, "truth": "hello world",
             "neural_s": 3.0, "speech_s": 2.0},
            {"committed": False, "truth": "not now", "neural_s": 2.0, "speech_s": 1.0}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = tmp_path / "r.json"
    g = json.dumps({"method": "ltt", "alpha": 0.5, "delta": 0.1, "risk": "wrong-prefix-commit"})
    assert main(["safe-wpm", "--trials", str(p), "--guarantee", g, "--metric-version", "0.2", "--out", str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["definition"] == "safe-wpm/0.2" and r["value"] == pytest.approx(60 * 1 / 5.0)
    assert r["speech_time"]["value"] == pytest.approx(60 * 1 / 3.0)
    # v0.1 (default) scores the same file with the v0.1 rule: "correct" is false (no exact sentence)
    assert main(["safe-wpm", "--trials", str(p), "--guarantee", g, "--out", str(out)]) == 0
    r1 = json.loads(out.read_text(encoding="utf-8"))
    assert r1["definition"] == "safe-wpm/0.1" and r1["n_wrong_commits"] == 1


def _prefix_case():
    from fidetype.benchmark.safe_wpm import prefix_outcome

    truths = ["i need some water", "call my wife", "good morning", "open the window", "yes please"]
    # 0: right 2-word prefix; 1: wrong 2-word prefix; 2: right complete; 3: withhold; 4: right 1-word prefix
    outs = [prefix_outcome("i need", truths[0], False), prefix_outcome("call me", truths[1], False),
            prefix_outcome("good morning", truths[2], True), None, prefix_outcome("yes", truths[4], False)]
    kw = dict(guarantee=LTT_PREFIX, metric_version="0.2",
              committed_words=[o["committed_words"] if o else math.nan for o in outs],
              complete=[bool(o and o["complete"]) for o in outs],
              penalty_chars=[o["penalty_chars"] if o else math.nan for o in outs])
    args = ([o is not None for o in outs], [bool(o and o["correct"]) for o in outs],
            [len(t.split()) for t in truths], [len(t) for t in truths], [3.0, 4.0, 2.0, 5.0, 1.0])
    return args, kw


def test_v02_reading_cost_defaults_change_nothing() -> None:
    args, kw = _prefix_case()
    a = safe_wpm(*args, **kw)
    b = safe_wpm(*args, **kw, read_s_per_commit=0.0, read_s_per_word=0.0, min_prefix_words=1)
    assert a == b and "reading_cost" not in a


def test_v02_reading_cost_hand_computed() -> None:
    args, kw = _prefix_case()
    pen = 2.0 + DEFAULT_S_PER_CHAR * len("call my")
    base = 15.0 + pen
    r = safe_wpm(*args, **kw, read_s_per_commit=1.0, read_s_per_word=0.5)
    # 4 commits, committed words 2 + 2 + 2 + 1 = 7: reading 4 * 1.0 + 7 * 0.5 = 7.5 s, right or wrong
    assert r["value"] == pytest.approx(60 * (2 + 2 + 1) / (base + 7.5))
    rc = r["reading_cost"]
    assert rc["minutes_reading"] == pytest.approx(7.5 / 60) and rc["n_prefix_commits_dropped"] == 0
    assert rc["wpm_without_reading"] == pytest.approx(60 * 5 / base)
    assert r["n_commits"] == 4 and r["status"] == "certified"


def test_v02_min_prefix_words() -> None:
    args, kw = _prefix_case()
    pen = 2.0 + DEFAULT_S_PER_CHAR * len("call my")
    r2 = safe_wpm(*args, **kw, min_prefix_words=2)  # drops the 1-word prefix (trial 4)
    assert r2["value"] == pytest.approx(60 * 4 / (15.0 + pen))
    assert r2["n_commits"] == 3 and r2["n_prefix_commits"] == 2 and r2["reading_cost"]["n_prefix_commits_dropped"] == 1
    r3 = safe_wpm(*args, **kw, min_prefix_words=3)  # drops all prefix commits, also the wrong one; complete stays
    assert r3["value"] == pytest.approx(60 * 2 / 15.0)
    assert r3["n_commits"] == 1 and r3["n_wrong_commits"] == 0 and r3["n_complete_commits"] == 1
    # reading cost and minimum length together; speech time also pays the reading cost
    r4 = safe_wpm(*args, **kw, min_prefix_words=2, read_s_per_commit=2.0, speech_s=[1.0] * 5)
    assert r4["value"] == pytest.approx(60 * 4 / (15.0 + pen + 3 * 2.0))
    assert r4["speech_time"]["value"] == pytest.approx(60 * 4 / (5.0 + pen + 3 * 2.0))


def test_v02_reading_cost_refused_with_v01_and_bad_values() -> None:
    args, kw = _prefix_case()
    with pytest.raises(ValueError, match="metric_version"):
        safe_wpm(*args, guarantee=LTT, read_s_per_commit=1.0)
    with pytest.raises(ValueError, match="metric_version"):
        safe_wpm(*args, guarantee=LTT, min_prefix_words=2)
    for bad in ({"read_s_per_commit": -1.0}, {"read_s_per_word": math.inf}, {"min_prefix_words": 0},
                {"min_prefix_words": 1.5}):
        with pytest.raises(ValueError):
            safe_wpm(*args, **kw, **bad)


def test_v02_sentence_policy_with_reading_cost_uses_truth_length() -> None:
    # complete commits without committed_words: k = truth words
    r = safe_wpm([True, True, False], [True, False, False], [3, 2, 4], [12, 8, 15], [3.0, 3.0, 3.0],
                 guarantee=LTT, metric_version="0.2", read_s_per_word=1.0)
    pen = 2.0 + DEFAULT_S_PER_CHAR * 8
    assert r["value"] == pytest.approx(60 * 3 / (9.0 + pen + 5.0))


def test_v02_cli_reading_cost(tmp_path) -> None:
    from fidetype.benchmark.__main__ import main

    p = tmp_path / "t.jsonl"
    rows = [{"committed": True, "committed_text": "hello", "complete": False, "truth": "hello world",
             "neural_s": 3.0},
            {"committed": False, "truth": "not now", "neural_s": 2.0}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = tmp_path / "r.json"
    g = json.dumps({"method": "ltt", "alpha": 0.5, "delta": 0.1, "risk": "wrong-prefix-commit"})
    assert main(["safe-wpm", "--trials", str(p), "--guarantee", g, "--metric-version", "0.2", "--out", str(out),
                 "--read-s-per-commit", "1", "--read-s-per-word", "0.5"]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["value"] == pytest.approx(60 * 1 / 6.5)
    assert main(["safe-wpm", "--trials", str(p), "--guarantee", g, "--metric-version", "0.2", "--out", str(out),
                 "--min-prefix-words", "2"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["value"] == 0.0
    assert main(["safe-wpm", "--trials", str(p), "--guarantee", g, "--read-s-per-commit", "1"]) == 2


# --- P15-29: interval over calibration draws (proposed reporting addition) -------------------------------------


def _toy_draw(rng: np.random.Generator, n: int, p_commit: float, p_right: float) -> dict:
    cm = rng.random(n) < p_commit
    ok = cm & (rng.random(n) < p_right)
    return {"committed": cm.tolist(), "correct": ok.tolist(), "guarantee": LTT}


def _toy_eval(n: int = 200, seed: int = 1):
    rng = np.random.default_rng(seed)
    nw = rng.integers(3, 12, n).astype(float)
    nc = nw * 5.0
    ns = rng.uniform(5.0, 20.0, n)
    return rng, nw, nc, ns


def test_calibration_interval_one_draw_is_the_trial_bootstrap() -> None:
    from fidetype.benchmark.safe_wpm import calibration_draw_interval

    rng, nw, nc, ns = _toy_eval()
    d = _toy_draw(rng, len(ns), 0.4, 0.9)
    r = calibration_draw_interval([d], nw, nc, ns, B=500, seed=0)
    one = safe_wpm(d["committed"], d["correct"], nw, nc, ns, guarantee=LTT)
    assert r["value"] == pytest.approx(one["value"])
    assert r["n_draws"] == 1 and r["sd_between_draws"] == 0.0
    # same resamples as the P15-22 paired bootstrap: rng.integers(0, n, n) -> bincount weights
    g = np.random.default_rng(0)
    cm, ok = np.array(d["committed"]), np.array(d["correct"])
    pen = CorrectionRule().penalty(nc)
    vals = []
    for _ in range(500):
        w = np.bincount(g.integers(0, len(ns), len(ns)), minlength=len(ns))
        vals.append(60 * (np.where(ok, nw, 0) * w).sum() / ((ns * w).sum() + (np.where(cm & ~ok, pen, 0) * w).sum()))
    assert r["interval"] == pytest.approx([np.percentile(vals, 2.5), np.percentile(vals, 97.5)])
    assert r["interval"] == r["draws"][0]["conditional_interval"]


def test_calibration_interval_widens_with_draw_spread_and_credit_rule() -> None:
    from fidetype.benchmark.safe_wpm import calibration_draw_interval

    rng, nw, nc, ns = _toy_eval()
    draws = [_toy_draw(rng, len(ns), p, 0.95) for p in (0.2, 0.35, 0.5, 0.65)]
    r = calibration_draw_interval(draws, nw, nc, ns, B=400, reference=0.0)
    single = calibration_draw_interval(draws[1:2], nw, nc, ns, B=400)
    assert r["interval"][1] - r["interval"][0] > single["interval"][1] - single["interval"][0]
    vals = [d["value"] for d in r["draws"]]
    assert r["value"] == pytest.approx(np.mean(vals))
    assert r["sd_between_draws"] == pytest.approx(np.std(vals, ddof=1))
    assert r["sd_total"] == pytest.approx(math.hypot(r["sd_between_draws"], r["sd_within_draw"]))
    assert r["lower_above_reference"] is True and r["fraction_of_draws_above_reference"] == 1.0
    # credit rule: a refused draw and a not-certified draw add 0.0
    bad = dict(draws[0], guarantee=None)
    r2 = calibration_draw_interval(draws + [{"refused": True}, bad], nw, nc, ns, B=400)
    assert r2["n_draws"] == 6 and r2["n_credited"] == 4
    assert r2["statuses"] == {"certified": 4, "not-certified": 1, "refused": 1}
    assert r2["value"] == pytest.approx(sum(vals) / 6)
    assert r2["interval"][0] == 0.0  # 1/3 of the pooled values are 0.0


def test_calibration_interval_bad_inputs() -> None:
    from fidetype.benchmark.safe_wpm import calibration_draw_interval

    rng, nw, nc, ns = _toy_eval(20)
    d = _toy_draw(rng, 20, 0.5, 0.9)
    with pytest.raises(ValueError, match="level"):
        calibration_draw_interval([d], nw, nc, ns, level=0.05 * 100)
    with pytest.raises(ValueError, match="empty"):
        calibration_draw_interval([], nw, nc, ns)
    with pytest.raises(ValueError, match="one value per evaluation trial"):
        calibration_draw_interval([dict(d, committed=d["committed"][:5])], nw, nc, ns)
