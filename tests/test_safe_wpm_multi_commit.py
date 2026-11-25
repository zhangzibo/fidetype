"""Several commits per trial in safe-wpm/0.2 (rule (7), adopted 2026-11-24).

- rule (7): every commit event pays read_s_per_commit, every committed word read_s_per_word once;
  a report with several commits per trial is an adopted v0.2 headline (hand-computed cases);
- the scorer hole: a ``wrong-stream-commit`` guarantee without ``n_commits`` is never an adopted headline;
- single-commit reports do not change (golden digests of the reports before the change);
- the T15 numbers of the decision record (single 4.67, stream 2.34, hybrid 4.89; local data, else skipped).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import warnings
from pathlib import Path

import pytest

import fidetype.benchmark.safe_wpm as SW
from fidetype.benchmark.safe_wpm import (DEFAULT_S_PER_CHAR, MULTI_COMMIT_STATUS, STREAM_WITHOUT_N_COMMITS,
                                         calibration_draw_interval, prefix_outcome, safe_wpm)

REPO = Path(__file__).resolve().parents[1]
LTT = {"method": "ltt", "alpha": 0.5, "delta": 0.1, "n_cal": 100}
LTT_STREAM = dict(LTT, risk="wrong-stream-commit")
LTT_PREFIX = dict(LTT, risk="wrong-prefix-commit")
PEN = lambda s: 2.0 + DEFAULT_S_PER_CHAR * len(s)  # noqa: E731


def _case():
    """Four trials: a right 3-word prefix (2 events), a wrong prefix (2 events), a right sentence (1), nothing."""
    truths = ["i need some water", "call my wife", "good morning", "open the window"]
    finals = [("i need some", False, 2), ("call me", False, 2), ("good morning", True, 1), None]
    outs = [prefix_outcome(f[0], t, f[1]) if f else None for f, t in zip(finals, truths)]
    args = ([o is not None for o in outs], [bool(o and o["correct"]) for o in outs], [len(t.split()) for t in truths],
            [len(t) for t in truths], [3.0, 4.0, 2.0, 5.0])
    kw = dict(committed_words=[o["committed_words"] if o else math.nan for o in outs],
              complete=[bool(o and o["complete"]) for o in outs],
              penalty_chars=[o["penalty_chars"] if o else math.nan for o in outs])
    return args, kw, [f[2] if f else 0 for f in finals]


# --- rule (7) is adopted ---------------------------------------------------------------------------------------------


def test_rule7_hand_computed_and_adopted():
    args, kw, nc = _case()
    r = safe_wpm(*args, **kw, guarantee=LTT_STREAM, n_commits=nc)
    # credit 3 + 2; time 14 s neural + penalty("call my") + 5 events * 0.5 s + 7 committed words * 0.3 s
    assert r["value"] == pytest.approx(60 * 5 / (14.0 + PEN("call my") + 2.5 + 2.1))
    assert r["status"] == "certified" and r["adopted_headline"] is True and "not_headline_because" not in r
    assert r["definition_status"] == SW.V02_STATUS
    mc = r["multi_commit"]
    assert mc["status"] == MULTI_COMMIT_STATUS and "adopted 2026-11-24" in mc["status"]
    assert (mc["n_commit_events"], mc["n_trials_with_several_commits"], mc["max_commits_per_trial"]) == (5, 2, 2)
    assert r["reading_cost"]["minutes_reading"] == pytest.approx((2.5 + 2.1) / 60)


def test_rule7_splitting_a_commit_costs_the_fee_per_event():
    args, kw, nc = _case()
    base = safe_wpm(*args, **kw, guarantee=LTT_STREAM, n_commits=nc)
    split = safe_wpm(*args, **kw, guarantee=LTT_STREAM, n_commits=[3, 2, 1, 0])  # trial 0: 3 one-word commits
    t0, t1 = 60 * 5 / base["value"], 60 * 5 / split["value"]
    assert t1 - t0 == pytest.approx(0.5) and split["adopted_headline"] is True


def test_rule7_needs_the_stream_bound():
    args, kw, nc = _case()
    r = safe_wpm(*args, **kw, guarantee=LTT_PREFIX, n_commits=nc)
    assert r["status"] == "not-certified" and r["value"] is None and "wrong-stream-commit" in r["note"]


def test_rule7_sensitivity_variant_stays_a_variant():
    args, kw, nc = _case()
    r = safe_wpm(*args, **kw, guarantee=LTT_STREAM, n_commits=nc, read_s_per_commit=0.0)
    assert r["adopted_headline"] is False and any("read_s_per_commit" in x for x in r["not_headline_because"])


# --- the scorer hole: wrong-stream-commit without n_commits ---------------------------------------------------------


def test_stream_guarantee_without_n_commits_is_not_a_headline():
    args, kw, nc = _case()
    r = safe_wpm(*args, **kw, guarantee=LTT_STREAM)
    # value and status as before (one reading fee per committed trial), but never an adopted headline
    assert r["value"] == pytest.approx(60 * 5 / (14.0 + PEN("call my") + 1.5 + 2.1))
    assert r["status"] == "certified" and r["adopted_headline"] is False
    assert r["not_headline_because"] == [STREAM_WITHOUT_N_COMMITS]
    assert r["definition_status"] == SW.V02_VARIANT_STATUS and "multi_commit" not in r
    # with the events given (here one per committed trial) the same policy is an adopted headline
    one = [int(c) for c in args[0]]
    a = safe_wpm(*args, **kw, guarantee=LTT_STREAM, n_commits=one)
    assert a["value"] == r["value"] and a["adopted_headline"] is True
    # other bounds without n_commits are not affected
    p = safe_wpm(*args, **kw, guarantee=LTT_PREFIX)
    assert p["adopted_headline"] is True and p["value"] == r["value"]
    # a stream bound on a policy that commits nothing: vacuous, nothing to charge
    v = safe_wpm([False] * 4, [False] * 4, *args[2:], guarantee=LTT_STREAM)
    assert v["status"] == "vacuous" and v["adopted_headline"] is True


def test_calibration_interval_with_commit_events():
    args, kw, nc = _case()
    cm, ok, nw, nch, ns = args
    d = dict(committed=cm, correct=ok, guarantee=LTT_STREAM, n_commits=nc, **kw)
    r = calibration_draw_interval([d] * 80, nw, nch, ns, B=50, seed=0, draw_scheme="partition")
    one = safe_wpm(*args, **kw, guarantee=LTT_STREAM, n_commits=nc)
    assert r["adopted_headline"] is True and "not_headline_because" not in r
    assert r["value"] == pytest.approx(one["value"]) and r["sd_between_draws"] == 0.0
    # the inner bootstrap charges every commit event (same pooled values as safe_wpm on each resample)
    with pytest.warns(SW.CalibrationIntervalWarning):
        k1 = calibration_draw_interval([d], nw, nch, ns, B=50, seed=0, draw_scheme="partition")
    assert k1["draws"][0]["value"] == pytest.approx(one["value"])
    no_ev = dict(d)
    del no_ev["n_commits"]
    r2 = calibration_draw_interval([no_ev] * 80, nw, nch, ns, B=50, seed=0, draw_scheme="partition")
    assert r2["adopted_headline"] is False and r2["not_headline_because"] == [STREAM_WITHOUT_N_COMMITS]
    assert r2["value"] > r["value"]  # one fee per trial: the cheaper (wrong) reading time


def test_cli_stream_bound_reads_the_commit_events(tmp_path: Path):
    from fidetype.benchmark.__main__ import main

    g = tmp_path / "g.json"
    g.write_text(json.dumps(LTT_STREAM), encoding="utf-8")

    def run(rows):
        p, out = tmp_path / "t.jsonl", tmp_path / "o.json"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        assert main(["safe-wpm", "--trials", str(p), "--guarantee", str(g), "--out", str(out)]) == 0
        return json.loads(out.read_text(encoding="utf-8"))

    row = {"committed": True, "truth": "i need some water", "committed_text": "i need", "complete": False,
           "neural_s": 3.0}
    off = {"committed": False, "truth": "good morning", "neural_s": 2.0}
    with_events = run([dict(row, n_commits=1), off])
    assert with_events["adopted_headline"] is True and with_events["multi_commit"]["n_commit_events"] == 1
    without = run([row, off])
    assert without["adopted_headline"] is False and without["not_headline_because"] == [STREAM_WITHOUT_N_COMMITS]
    assert without["value"] == with_events["value"]
    two = run([dict(row, n_commits=2), off])
    assert two["adopted_headline"] is True and two["value"] == pytest.approx(60 * 2 / (5.0 + 1.0 + 0.6))


# --- single-commit reports do not change ----------------------------------------------------------------------------


def single_commit_cases():
    """(name, fn(module) -> report) for single-commit inputs; also used to make the golden digests below."""
    args, kw, _ = _case()
    cm, ok, nw, nch, ns = args
    sent = ([True, True, True, False], [True, False, True, False], nw, nch, ns)
    clusters = [{"u": "a"}, {"u": "a"}, {"u": "b"}, {"u": "b"}]
    crc = {"method": "crc", "alpha": 0.1, "n_cal": 50}
    cases = [
        ("sentence_ltt_ci", lambda m: m.safe_wpm(*sent, guarantee=LTT, clusters=clusters, ci_unit="u", B=200)),
        ("sentence_v01_ci", lambda m: m.safe_wpm(*sent, guarantee=LTT, clusters=clusters, ci_unit="u", B=200,
                                                 metric_version="0.1")),
        ("sentence_crc_above_alpha", lambda m: m.safe_wpm(*sent, guarantee=crc)),
        ("sentence_none", lambda m: m.safe_wpm(*sent, guarantee={"method": "none"})),
        ("sentence_risk_wrong_commit", lambda m: m.safe_wpm(*sent, guarantee=dict(LTT, risk="wrong-commit"))),
        ("prefix_ltt", lambda m: m.safe_wpm(*args, **kw, guarantee=LTT_PREFIX, speech_s=[2.0, 3.0, 1.5, 4.0])),
        ("prefix_variant_no_reading", lambda m: m.safe_wpm(*args, **kw, guarantee=LTT_PREFIX, read_s_per_commit=0,
                                                           read_s_per_word=0)),
        ("prefix_sentence_bound", lambda m: m.safe_wpm(*args, **kw, guarantee=LTT)),
        ("prefix_min2", lambda m: m.safe_wpm(*args, **kw, guarantee=LTT_PREFIX, min_prefix_words=3)),
        ("interval_v02", lambda m: m.calibration_draw_interval(
            [dict(committed=cm, correct=ok, guarantee=LTT_PREFIX, **kw), {"refused": True},
             dict(committed=sent[0], correct=sent[1], guarantee=LTT)], nw, nch, ns, B=100, seed=1)),
        ("interval_v01", lambda m: m.calibration_draw_interval(
            [dict(committed=sent[0], correct=sent[1], guarantee=LTT)] * 3, nw, nch, ns, B=100, metric_version="0.1",
            draw_scheme="partition")),
    ]
    return cases


def digest(report) -> str:
    """SHA-256 of a report with floats rounded to 10 significant digits (robust to last-bit platform noise)."""
    def canon(x):
        if isinstance(x, float):
            return float(f"{x:.10g}") if math.isfinite(x) else str(x)
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [canon(v) for v in x]
        return x
    return hashlib.sha256(json.dumps(canon(report), sort_keys=True).encode("utf-8")).hexdigest()


#: Digests made with the scorer before rule (7) was adopted (commit 1b4307b), by the same ``single_commit_cases``.
GOLDEN = {
    "sentence_ltt_ci": "9ee13076fd5309a2a8421d9d93fdc56524b2ff7120e63abad0b212ecaa0ac2ef",
    "sentence_v01_ci": "eaba00e4c0e2085b6d971082770b7e7f4d584c8bda494e5f8df5cc379fdf8ede",
    "sentence_crc_above_alpha": "c728c5bf66848e7ce3f29d8f645dbc98aee1f58b0ded28545ae3258053031360",
    "sentence_none": "34a400ec85f81a4df96894f28056090e5385fc2803d29eb31f130ee6c00f9862",
    "sentence_risk_wrong_commit": "7484319977f1fdb7715431654ec465a914d4ef92d9e4337b3b548230d3d0b0bc",
    "prefix_ltt": "85088845536d174b59630619bc0847836d1923f0ffe02caf598513122299e642",
    "prefix_variant_no_reading": "20e52d247fbcb1dad40dbb9433bb53261bd49c628243f2a1b7d321a5099effd3",
    "prefix_sentence_bound": "331e99e279f6c87170ffe3a4ae59c5dfae499bf40e0096e629d626acbf839eef",
    "prefix_min2": "9b48762652111b36e537270e93f58750b5f9b914759e60ce4ffbc4059e51fd25",
    "interval_v02": "a589010c96be8ff7c4ad298e2e5a4e6c109be0a7f9da17d372d06b017f0a0b60",
    "interval_v01": "7b44a03bbfad11779a9829109b771aaf144b6c0a23879303c6c95ab738840c91",
}


@pytest.mark.parametrize("name,fn", single_commit_cases(), ids=[c[0] for c in single_commit_cases()])
def test_single_commit_reports_unchanged(name, fn):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert digest(fn(SW)) == GOLDEN[name]


# --- T15 numbers of the decision record (local data only) -----------------------------------------------------------

DER = Path("C:/Users/zhang/bci-data/derived")
T15_FILES = [DER / "p5-27" / "decisions-single.json", DER / "p5-27" / "decisions-stream.json",
             DER / "p5-28" / "decisions-hybrid.json", DER / "m4-01-02-lookahead" / "sessions.json",
             DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"]


@pytest.mark.skipif(not all(p.is_file() for p in T15_FILES), reason="local T15 decision logs not on this machine")
def test_t15_numbers_of_the_decision_record():
    spec = importlib.util.spec_from_file_location(
        "p1463_analyse", REPO / "experiments" / "2026-11-24-p14-63-multi-commit-decision" / "analyse.py")
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    ns = list(A.durations())
    recorded = {"single": 4.667061076225306, "stream": 2.343539936697323, "hybrid": 4.890195222754168}
    files = {"single": T15_FILES[0], "stream": T15_FILES[1], "hybrid": T15_FILES[2]}
    risk = {"single": "wrong-prefix-commit", "stream": "wrong-stream-commit", "hybrid": "wrong-stream-commit"}
    for arm, f in files.items():
        rows = json.loads(f.read_text(encoding="utf-8"))
        nev = [int(x) for x in A.per_trial(rows, "R7")["nev"]]
        po = [prefix_outcome(r["text"], r["truth"], bool(r["complete"])) if r["action"] == "commit" else None
              for r in rows]
        g = {"method": "ltt", "alpha": 0.05, "delta": 0.1, "n_cal": 271, "risk": risk[arm]}
        kw = dict(guarantee=g, committed_words=[p["committed_words"] if p else math.nan for p in po],
                  complete=[p["complete"] if p else True for p in po],
                  penalty_chars=[p["penalty_chars"] if p else math.nan for p in po])
        args = ([p is not None for p in po], [bool(p and p["correct"]) for p in po],
                [len(r["truth"].split()) for r in rows], [len(r["truth"]) for r in rows], ns)
        r = safe_wpm(*args, n_commits=nev, **kw)
        assert r["value"] == pytest.approx(recorded[arm], abs=1e-9)
        assert r["status"] == "certified" and r["adopted_headline"] is True
        if arm == "hybrid":
            assert round(r["value"], 2) == 4.89 and r["multi_commit"]["n_commit_events"] == 803
            hole = safe_wpm(*args, **kw)  # the case the decision record found: 4.94 labelled as a headline
            assert round(hole["value"], 2) == 4.94 and hole["adopted_headline"] is False
            assert hole["not_headline_because"] == [STREAM_WITHOUT_N_COMMITS]
        if arm == "stream":
            assert round(r["value"], 2) == 2.34 and r["multi_commit"]["n_commit_events"] == 446
        if arm == "single":
            assert round(r["value"], 2) == 4.67 and r["multi_commit"]["n_trials_with_several_commits"] == 0
