"""Tests of hybrid streaming + end-of-trial prefix commits (P5-28)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import commit_score as C
from fidetype.trust import hybrid_commit as H
from fidetype.trust import stream_commit as S

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits


def view(words: str, at_end: bool = False, gate_ok: bool = True, n: int = 10) -> S.CheckpointView:
    w = tuple(words.split())
    return S.CheckpointView(n, at_end, w, np.zeros((len(w), len(C.PREFIX_FEATURES))), gate_ok)


def test_run_hybrid_uses_two_thresholds_and_extends_at_the_end():
    vs = [view("i"), view("i need"), view("i need some water", at_end=True)]
    sc = [np.array([0.95]), np.array([0.95, 0.9]), np.array([0.9, 0.9, 0.9, 0.9])]
    # mid threshold 0.93: commits "i" early; end threshold 0.85: extends to the complete sentence
    r = H.run_hybrid(vs, sc, 0.93, 0.85)
    assert [(c["k_from"], c["k_to"], c["complete"], c["at_end"]) for c in r["commits"]] == [
        (0, 1, False, False), (1, 4, True, True)]
    assert r["complete"] and r["words"] == ("i", "need", "some", "water")
    # one threshold for both (the P5-27 stream rule) cannot do this
    assert S.run_stream(vs, sc, 0.93)["words"] == ("i",)
    # lam_mid = inf: only the end decision (the one-commit prefix guard)
    r1 = H.run_hybrid(vs, sc, math.inf, 0.85)
    assert [(c["k_from"], c["k_to"]) for c in r1["commits"]] == [(0, 4)]
    # an end conflict keeps the mid commit and adds nothing
    r2 = H.run_hybrid([view("i"), view("you need", at_end=True)], [np.array([0.99]), np.array([0.99, 0.99])],
                      0.9, 0.9)
    assert r2["words"] == ("i",) and r2["n_conflicts"] == 1 and not r2["complete"]
    # the loss: any wrong commit makes the trial wrong
    assert not S.stream_wrong(r, vs, "i need some water".split())
    assert S.stream_wrong(r, vs, "i need some milk".split())


def test_hybrid_scores_pick_the_score_per_checkpoint():
    rng = np.random.default_rng(0)
    mid = C.LearnedCommitScore.fit(rng.normal(size=(60, len(C.STREAM_FEATURES))), [True, False] * 30,
                                   unit="stream-prefix")
    end = C.LearnedCommitScore.fit(rng.normal(size=(60, len(C.PREFIX_FEATURES))), [True, False] * 30,
                                   unit="prefix")
    vs = [view("a b"), view("a b c", gate_ok=False), view("a b c", at_end=True)]
    s = H.hybrid_scores(vs, mid, end)
    rows = S.stream_rows(vs)
    assert np.allclose(s[0], C.monotone_prefix_scores(mid.scores(rows[0])))
    assert s[1].size == 0
    assert np.allclose(s[2], C.monotone_prefix_scores(end.scores(vs[2].rows)))
    with pytest.raises(ValueError):
        H.hybrid_scores(vs, end, end)


def test_ltt_hybrid_end_is_safe_on_synthetic_items():
    rng = np.random.default_rng(0)
    vs, sc, tr = [], [], []
    for _ in range(400):
        right = rng.random() < 0.7
        words = "a b c" if right else "a x c"
        s = 0.5 + 0.45 * rng.random() if right else 0.4 * rng.random()
        vs.append([view("a"), view(words, at_end=True)])
        sc.append([np.array([0.2]), np.full(3, s)])
        tr.append("a b c".split())
    res = H.ltt_hybrid_end(vs, sc, tr, 0.99, 0.05, 0.1, [round(1 - 0.01 * j, 2) for j in range(101)])
    assert res["feasible"] and 0.3 <= res["threshold"] <= 0.5 and res["empirical_risk"] <= 0.05
    # a mid threshold that commits wrong words on every item makes every end threshold infeasible
    sc_bad = [[np.array([0.999]), s[1]] for s in sc]
    tr_bad = ["b b c".split()] * 400
    assert not H.ltt_hybrid_end(vs, sc_bad, tr_bad, 0.5, 0.05, 0.1, [1.0, 0.5])["feasible"]


@pytest.fixture(scope="module")
def hybrid_setup():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(160)]
    xs = [fake_logits(t, rng) for t in ts]
    base = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=30, decoder_name="test-ctc",
                        confidence="learned", commit_unit="prefix")
    vs = [S.stream_views(base, x, 9) for x in xs]
    sg = S.calibrate_streaming(base, xs, ts, step_frames=9, views=vs, null_trials=30)
    cv = [(nm, S.stream_views(base, x, 9, sc)) for nm, x, sc in S.null_control_inputs(base, xs, 60, (0, 528))]
    # the toy data certify the stream threshold at 1.00; a lower mid threshold commits on shuffled toy input
    g = H.calibrate_hybrid(base, sg.score, vs, ts, step_frames=9, lam_mid=sg.threshold, control_views=cv,
                           frame_timing={"patch": 14, "stride": 4, "bin_s": 0.02})
    return base, g, xs, ts, vs, rng


def test_calibrate_hybrid_end_to_end(hybrid_setup, tmp_path: Path):
    base, g, xs, ts, vs, rng = hybrid_setup
    sh = g.sheet
    assert sh["n_certify"] == 60 and sh["risk"].startswith("wrong-stream-commit") and sh["lam_mid"] == g.lam_mid and sh["feasible"]
    assert all(c["passed"] for c in sh["controls"]) and {c["name"] for c in sh["controls"]} == {"uniform", "shuffled"}
    assert g.guarantee()["risk"] == "wrong-stream-commit" and g.guarantee()["commit_threshold"] == g.lam_end
    for i in range(20):
        t = str(rng.choice(PHRASES))
        r = g.decide(fake_logits(t, rng), utterance_id=f"u{i}", audit_text=True)
        assert H.HybridPrefixGuard.check_chain(r.events)
        if r.n_commits:
            assert " ".join(r.added) == r.text
            assert all(not e["complete"] for e in r.events[:-1])
            assert all(e["threshold"] == H._num(g.lam_end if e["at_end"] else g.lam_mid) for e in r.events)
    # with lam_mid = inf the hybrid equals the one-commit base prefix guard (same end score), if lam_end = base's
    one = H.HybridPrefixGuard(base, g.mid_score, 9, math.inf, base.commit_score.threshold)
    for x, v in zip(xs[:30], vs[:30]):
        r_b = base._decide_quiet(x)
        r_h = one.decide_views(v)
        assert (r_b.action == "commit") == (r_h.n_commits > 0)
        if r_h.n_commits:
            assert r_h.text == r_b.text and r_h.complete == r_b.complete
    p = g.save(tmp_path / "hybrid.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["schema"] == H.HYBRID_GUARD_SCHEMA and d["config_id"] == g.config_id and g.config_id.startswith("hcfg-")


def test_hybrid_refuses_on_null_input(hybrid_setup):
    base, g, xs, ts, vs, _ = hybrid_setup
    cv = [("shuffled", v) for v in vs[:30]]
    with pytest.raises(ft.NullControlError):
        H.calibrate_hybrid(base, g.mid_score, vs, ts, step_frames=9, lam_mid=0.0, control_views=cv, alpha=0.5,
                           delta=0.9, grid=[0.0])


def test_hybrid_guard_checks(hybrid_setup):
    base, g, *_ = hybrid_setup
    with pytest.raises(ValueError):
        H.HybridPrefixGuard(base, base.commit_score, 9, 0.9, 0.9)
    with pytest.raises(ValueError):
        H.HybridPrefixGuard(object(), g.mid_score, 9, 0.9, 0.9)
