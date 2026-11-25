"""Tests of streaming word-by-word prefix commits within one utterance (P5-27)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.benchmark.safe_wpm import prefix_outcome, safe_wpm
from fidetype.trust import commit_score as C
from fidetype.trust import stream_commit as S

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits


def view(words: str, at_end: bool = False, gate_ok: bool = True, n: int = 10) -> S.CheckpointView:
    w = tuple(words.split())
    return S.CheckpointView(n, at_end, w, np.zeros((len(w), len(C.PREFIX_FEATURES))), gate_ok)


# --- helpers ---------------------------------------------------------------------------------------------------------


def test_checkpoints_and_times():
    assert S.checkpoint_frames(10, 3) == [3, 6, 9, 10]
    assert S.checkpoint_frames(9, 3) == [3, 6, 9]
    assert S.checkpoint_frames(2, 3) == [2]
    assert S.checkpoint_frames(0, 3) == []
    with pytest.raises(ValueError):
        S.checkpoint_frames(5, 0)
    # patch 14, stride 4, 20 ms bins: frame 1 ready at 0.28 s, n frames at 0.08 n + 0.20 s
    assert S.checkpoint_time_s(1, patch=14, stride=4, bin_s=0.02) == pytest.approx(0.28)
    assert S.checkpoint_time_s(100, patch=14, stride=4, bin_s=0.02) == pytest.approx(8.2)


def test_run_stream_is_append_only_with_conflicts_and_complete_at_end():
    vs = [view("i"), view("i need"), view("a need"), view("i need some water", at_end=True)]
    sc = [np.array([0.9]), np.array([0.9, 0.8]), np.array([0.95, 0.9]), np.array([0.9, 0.9, 0.9, 0.9])]
    r = S.run_stream(vs, sc, 0.85)
    assert [(c["k_from"], c["k_to"], c["complete"]) for c in r["commits"]] == [(0, 1, False), (1, 4, True)]
    assert r["words"] == ("i", "need", "some", "water") and r["complete"] and r["n_conflicts"] == 1
    # the last top-1 word before the end is never a complete commit
    r2 = S.run_stream([view("i need")], [np.array([0.9, 0.9])], 0.5)
    assert r2["commits"][0]["complete"] is False
    # commit gate blocks a checkpoint
    r3 = S.run_stream([view("i", gate_ok=False)], [np.array([0.99])], 0.5)
    assert r3["commits"] == []
    # wrong if any commit is wrong; a right prefix followed by a wrong complete commit is wrong
    assert not S.stream_wrong(r, vs, "i need some water".split())
    assert S.stream_wrong(r, vs, "i need some water now".split())
    assert S.stream_wrong(S.run_stream([view("you")], [np.array([0.9])], 0.5), [view("you")], ["i"])


def test_stream_rows_and_labels():
    vs = [view("i"), view("i need"), view("i need help", at_end=True)]
    rows = S.stream_rows(vs)
    f = {n: j for j, n in enumerate(C.STREAM_FEATURES)}
    assert [r.shape for r in rows] == [(1, 19), (2, 19), (3, 19)]
    assert rows[0][0, f["stable_log"]] == 0.0 and rows[0][0, f["open_last_word"]] == 1.0
    assert rows[2][0, f["stable_log"]] == pytest.approx(math.log1p(2))   # "i" seen at both earlier checkpoints
    assert rows[2][1, f["stable_log"]] == pytest.approx(math.log1p(1))   # "i need" at one
    assert rows[2][2, f["at_end"]] == 1.0 and rows[2][2, f["open_last_word"]] == 0.0
    assert S.stream_labels(vs[1], "i need water".split()).tolist() == [True, True]
    assert S.stream_labels(vs[2], "i need water".split()).tolist() == [True, True, False]
    assert S.stream_labels(view("i need", at_end=True), "i need water".split()).tolist() == [True, False]


def test_ltt_stream_threshold_safe_on_synthetic_items():
    rng = np.random.default_rng(0)
    vs, sc, tr = [], [], []
    for _ in range(400):
        right = rng.random() < 0.7
        truth = "a b c".split()
        words = "a b c" if right else "a x c"
        s = 0.5 + 0.45 * rng.random() if right else 0.4 * rng.random()
        vs.append([view(words, at_end=True)])
        sc.append([C.monotone_prefix_scores([0.99, s if not right else 0.99, s])])
        tr.append(truth)
    res = S.ltt_stream_threshold(vs, sc, tr, alpha=0.05, delta=0.1, grid=[1.0 - 0.01 * k for k in range(101)])
    assert res["feasible"] and res["empirical_risk"] <= 0.05 and res["n"] == 400
    none = S.ltt_stream_threshold(vs[:5], sc[:5], tr[:5], alpha=0.0, delta=0.1, grid=[0.5, 0.0])
    assert not none["feasible"] or none["empirical_risk"] == 0.0


def test_stream_score_unit_round_trip():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(80, len(C.STREAM_FEATURES)))
    y = X[:, 0] + 0.3 * rng.normal(size=80) > 0
    m = C.LearnedCommitScore.fit(X, y, unit="stream-prefix")
    d = m.with_threshold(0.7, {"risk": "x"}).to_dict()
    assert d["schema"] == C.STREAM_SCORE_SCHEMA and d["unit"] == "stream-prefix"
    m2 = C.LearnedCommitScore.from_dict(json.loads(json.dumps(d)))
    assert m2.unit == "stream-prefix" and m2.threshold == 0.7 and m2.score(X[0]) == pytest.approx(m.score(X[0]))
    assert all(m.coef[C.STREAM_FEATURES.index("open_last_word")] <= 0 for _ in [0])


# --- end to end (logits route) ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def stream_setup():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(160)]
    xs = [fake_logits(t, rng) for t in ts]
    base = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=30, decoder_name="test-ctc",
                        confidence="learned", commit_unit="prefix")
    g = S.calibrate_streaming(base, xs, ts, step_frames=9, null_trials=30,
                              frame_timing={"patch": 14, "stride": 4, "bin_s": 0.02})
    return base, g, xs, ts, rng


def test_calibrate_streaming_end_to_end(stream_setup, tmp_path: Path):
    base, g, xs, ts, rng = stream_setup
    sh = g.sheet
    assert sh["n_fit"] + sh["n_certify"] == len(xs) and sh["risk"].startswith("wrong-stream-commit")
    assert {c["name"] for c in sh["controls"]} == {"uniform", "shuffled"} and all(c["passed"] for c in sh["controls"])
    assert g.guarantee()["risk"] == "wrong-stream-commit"
    n_commit = 0
    for i in range(20):
        t = str(rng.choice(PHRASES))
        r = g.decide(fake_logits(t, rng), utterance_id=f"u{i}", audit_text=True)
        assert S.StreamingPrefixGuard.check_chain(r.events)
        assert r.n_commits == len(r.events) == len(r.added)
        if r.n_commits:
            n_commit += 1
            # append-only: the texts added in order give the committed text
            assert " ".join(r.added) == r.text and r.events[-1]["n_words_committed"] == r.n_words_committed
            assert all(e["t_s"] > 0 for e in r.events)
            assert all(not e["complete"] for e in r.events[:-1])
    # a broken chain is detected
    r = g.decide(xs[0], audit_text=True)
    if r.events:
        bad = [dict(r.events[0], words_added=99)] + r.events[1:]
        assert not S.StreamingPrefixGuard.check_chain(bad)
    p = g.save(tmp_path / "stream.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["schema"] == S.STREAM_GUARD_SCHEMA and d["config_id"] == g.config_id
    assert d["base_config_id"] == base.config_id and "text" not in json.dumps(d["sheet"]).lower().split('"')


def test_stream_guard_refuses_on_null_input(stream_setup):
    base, _, xs, ts, _ = stream_setup
    # with zero allowed commits and the calibration items as "null" inputs, the control must refuse
    vs = [S.stream_views(base, x, 9) for x in xs]
    cv = [("shuffled", v) for v in vs[:30]]
    with pytest.raises(ft.NullControlError):
        S.calibrate_streaming(base, xs, ts, step_frames=9, views=vs, control_views=cv, alpha=0.5, delta=0.9,
                              null_trials=30, grid=[0.0])


def test_stream_guard_checks():
    with pytest.raises(ValueError):
        S.StreamingPrefixGuard(object(), C.LearnedCommitScore.fit(np.random.default_rng(0).normal(size=(10, 16)),
                                                                  [True, False] * 5, unit="prefix"), 3)


# --- the "several commits per trial" rule (7) of safe-wpm/0.2 (adopted 2026-11-24) -------------------------------------------------------

LTT_STREAM = {"method": "ltt", "alpha": 0.5, "delta": 0.1, "n_cal": 100, "risk": "wrong-stream-commit"}


def _multi_case():
    truths = ["i need some water", "call my wife", "good morning", "open the window"]
    # final committed texts: 0 right prefix of 3 words in 2 commits; 1 wrong prefix (2 commits);
    # 2 right complete (1 commit); 3 nothing
    finals = [("i need some", False, 2), ("call me", False, 2), ("good morning", True, 1), None]
    outs = [prefix_outcome(f[0], t, f[1]) if f else None for f, t in zip(finals, truths)]
    args = ([o is not None for o in outs], [bool(o and o["correct"]) for o in outs], [len(t.split()) for t in truths],
            [len(t) for t in truths], [3.0, 4.0, 2.0, 5.0])
    kw = dict(guarantee=LTT_STREAM, metric_version="0.2",
              committed_words=[o["committed_words"] if o else math.nan for o in outs],
              complete=[bool(o and o["complete"]) for o in outs],
              penalty_chars=[o["penalty_chars"] if o else math.nan for o in outs])
    return args, kw, [f[2] if f else 0 for f in finals]


def test_v02_multi_commit_hand_computed():
    from fidetype.benchmark.safe_wpm import DEFAULT_S_PER_CHAR

    args, kw, nc = _multi_case()
    pen = 2.0 + DEFAULT_S_PER_CHAR * len("call my")
    r = safe_wpm(*args, **kw, n_commits=nc, read_s_per_commit=0.5, read_s_per_word=0.3)
    # reading: commits 2 + 2 + 1 = 5 -> 2.5 s; words 3 + 2 + 2 = 7 -> 2.1 s
    assert r["status"] == "certified" and r["value"] == pytest.approx(60 * (3 + 2) / (14.0 + pen + 2.5 + 2.1))
    mc = r["multi_commit"]
    assert mc["n_commit_events"] == 5 and mc["n_trials_with_several_commits"] == 2 and mc["max_commits_per_trial"] == 2
    assert r["n_wrong_commits"] == 1 and r["measured_wrong_commit"] == pytest.approx(0.25)
    # without reading cost the number of commits does not change the value
    r0 = safe_wpm(*args, **kw, n_commits=nc, read_s_per_commit=0.0, read_s_per_word=0.0)
    assert r0["value"] == pytest.approx(60 * 5 / (14.0 + pen))


def test_v02_multi_commit_needs_the_stream_bound_and_reduces_to_v02():
    args, kw, nc = _multi_case()
    k2 = dict(kw, guarantee=dict(LTT_STREAM, risk="wrong-prefix-commit"))
    r = safe_wpm(*args, **k2, n_commits=nc)
    assert r["status"] == "not-certified" and "wrong-stream-commit" in r["note"]
    # one commit per trial: same value as plain v0.2 (and a prefix bound is enough)
    one = [1 if c else 0 for c in args[0]]
    a = safe_wpm(*args, **k2, n_commits=one, read_s_per_commit=0.5, read_s_per_word=0.3)
    b = safe_wpm(*args, **k2, read_s_per_commit=0.5, read_s_per_word=0.3)
    assert a["value"] == pytest.approx(b["value"]) and a["status"] == b["status"] == "certified"
    # a stream bound also certifies a one-commit prefix policy
    assert safe_wpm(*args, **kw)["status"] == "certified"
    with pytest.raises(ValueError, match="safe-wpm/0.2"):
        safe_wpm(*args, guarantee=LTT_STREAM, n_commits=nc, metric_version="0.1")
    with pytest.raises(ValueError, match="min_prefix_words"):
        safe_wpm(*args, **kw, n_commits=nc, min_prefix_words=2)
    with pytest.raises(ValueError, match="n_commits"):
        safe_wpm(*args, **kw, n_commits=[0, 2, 1, 0])
    with pytest.raises(ValueError, match="n_commits"):
        safe_wpm(*args, **kw, n_commits=[1.5, 2, 1, 0])


def test_guarantee_from_a_stream_sheet():
    from fidetype.benchmark.safe_wpm import guarantee_from_sheet

    assert guarantee_from_sheet({"confidence": {"unit": "stream-prefix"}})["risk"] == "wrong-stream-commit"


def test_v02_multi_commit_cli(tmp_path: Path):
    from fidetype.benchmark.__main__ import main

    rows = [{"committed": True, "truth": "i need some water", "committed_text": "i need some", "complete": False,
             "neural_s": 3.0, "n_commits": 2},
            {"committed": False, "truth": "good morning", "neural_s": 2.0}]
    p = tmp_path / "t.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    g = tmp_path / "g.json"
    g.write_text(json.dumps(LTT_STREAM), encoding="utf-8")
    out = tmp_path / "o.json"
    assert main(["safe-wpm", "--trials", str(p), "--guarantee", str(g), "--metric-version", "0.2",
                 "--read-s-per-commit", "0.5", "--read-s-per-word", "0", "--out", str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["multi_commit"]["n_commit_events"] == 2 and r["value"] == pytest.approx(60 * 3 / (5.0 + 1.0))
