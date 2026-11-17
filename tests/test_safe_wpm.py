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
