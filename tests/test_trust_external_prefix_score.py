"""Tests of the native calibrate path for frozen external per-prefix scores (P5-35)."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import commit_score as C
from fidetype.trust.external_score import EXTERNAL_PREFIX_SCHEMA, FrozenPrefixScore, PrefixContext
from fidetype.trust.guarantee_sheet import policy_sheets

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits, nbest_data, noise_nbest

KW = dict(null_trials=60, decoder_name="test-nbest", modality="emg")


@pytest.fixture(scope="module")
def nbest_cal() -> tuple[list, list[str], list]:
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    return xs, ts, [noise_nbest(rng) for _ in range(60)]


@pytest.fixture(scope="module")
def learned_guard(nbest_cal) -> ft.TrustGuard:
    xs, ts, nulls = nbest_cal
    return ft.calibrate(xs, ts, null_inputs=nulls, confidence="learned", commit_unit="prefix", **KW)


def frozen_copy(model: C.LearnedCommitScore, name: str = "copy-of-p5-24") -> FrozenPrefixScore:
    """The learned P5-24 score of a guard as an external score (it reads the built-in prefix rows)."""
    spec = model.with_threshold(math.inf, {}).to_dict()

    def fn(ctx: PrefixContext):
        return model.scores(ctx.builtin_rows) if len(ctx.builtin_rows) else None

    return FrozenPrefixScore(fn, name=name, version="1", spec=spec)


@pytest.fixture(scope="module")
def external_guard(nbest_cal, learned_guard) -> tuple[ft.TrustGuard, FrozenPrefixScore]:
    xs, ts, nulls = nbest_cal
    score = frozen_copy(learned_guard.commit_score)
    g = ft.calibrate(xs, ts, null_inputs=nulls, commit_unit="prefix", prefix_score=score, **KW)
    return g, score


def key(r):
    return (r.action, r.text, r.n_words_committed, r.complete)


# --- FrozenPrefixScore ------------------------------------------------------------------------


def test_frozen_score_digest_and_checks():
    a = FrozenPrefixScore(lambda c: None, name="s", version="1", spec={"w": [1.0, 2.0], "b": 0.5})
    b = FrozenPrefixScore(lambda c: [0.0], name="s", version="1", spec={"b": 0.5, "w": [1.0, 2.0]})
    assert a.digest == b.digest and a.digest.startswith("pfx-")  # key order and function do not matter
    assert FrozenPrefixScore(lambda c: None, name="s", version="2", spec={"b": 0.5, "w": [1.0, 2.0]}).digest != a.digest
    assert FrozenPrefixScore(lambda c: None, name="s", version="1", spec={"b": 0.6, "w": [1.0, 2.0]}).digest != a.digest
    with pytest.raises(TypeError, match="JSON"):
        FrozenPrefixScore(lambda c: None, name="s", spec={"w": np.zeros(2)})
    with pytest.raises(TypeError, match="JSON"):
        FrozenPrefixScore(lambda c: None, name="s", spec={"w": float("nan")})
    with pytest.raises(ValueError, match="name"):
        FrozenPrefixScore(lambda c: None, name="", spec={})
    with pytest.raises(TypeError, match="callable"):
        FrozenPrefixScore(None, name="s", spec={})  # type: ignore[arg-type]
    ctx = PrefixContext(words=("a", "b"), texts=("a b",), posteriors=np.ones(1), candidates=(), log_probs=None,
                        p_top1=1.0, guard_risk=0.0, n_frames=None)
    assert FrozenPrefixScore(lambda c: [0.9, 0.5], name="s", spec={}).scores(ctx).tolist() == [0.9, 0.5]
    with pytest.raises(ValueError, match="one value per word prefix"):
        FrozenPrefixScore(lambda c: [0.9], name="s", spec={}).scores(ctx)
    with pytest.raises(ValueError, match="NaN"):
        FrozenPrefixScore(lambda c: [0.9, float("nan")], name="s", spec={}).scores(ctx)
    assert "FrozenPrefixScore" in ft.__all__ and ft.FrozenPrefixScore is FrozenPrefixScore


def test_option_checks(nbest_cal):
    xs, ts, nulls = nbest_cal
    score = FrozenPrefixScore(lambda c: None, name="s", spec={})
    with pytest.raises(ValueError, match='commit_unit="prefix"'):
        ft.calibrate(xs, ts, null_inputs=nulls, prefix_score=score)
    with pytest.raises(TypeError, match="FrozenPrefixScore"):
        ft.calibrate(xs, ts, null_inputs=nulls, commit_unit="prefix", prefix_score=lambda c: None)
    with pytest.raises(ValueError, match="target_precision"):
        ft.calibrate(xs, ts, null_inputs=nulls, commit_unit="prefix", prefix_score=score, target_precision=0.9)


# --- the external path reproduces the learned P5-24 guard -------------------------------------


def test_external_copy_reproduces_the_learned_prefix_guard(nbest_cal, learned_guard, external_guard):
    g, score = external_guard
    lg = learned_guard
    # same certified threshold, same LTT commits, same null-control counts
    assert g.commit_score.threshold == lg.commit_score.threshold and math.isfinite(g.commit_score.threshold)
    assert g.commit_unit == "prefix" and g.sheet.commit_threshold == lg.sheet.commit_threshold
    assert (g.sheet.ltt_commits, g.sheet.ltt_wrong_commits) == (lg.sheet.ltt_commits, lg.sheet.ltt_wrong_commits)
    assert [(c.name, c.n_commit) for c in g.sheet.controls] == [(c.name, c.n_commit) for c in lg.sheet.controls]
    # same decisions on new data
    xs, _ = nbest_data(120, 7)
    a = [g._decide_quiet(x) for x in xs]
    b = [lg._decide_quiet(x) for x in xs]
    assert [key(r) for r in a] == [key(r) for r in b] and any(r.action == "commit" for r in a)
    # a new config_id that covers the external score
    rec = g.config.recipe
    assert rec["commit_score"]["schema"] == EXTERNAL_PREFIX_SCHEMA
    assert rec["commit_score"]["score"]["digest"] == score.digest and rec["commit_unit"] == "prefix"
    assert g.config_id.startswith("tcfg-") and g.config_id != lg.config_id
    other = frozen_copy(lg.commit_score, name="another-name")
    xs0, ts0, nulls0 = nbest_cal
    g2 = ft.calibrate(xs0, ts0, null_inputs=nulls0, commit_unit="prefix", prefix_score=other, **KW)
    assert g2.config_id != g.config_id and g2.commit_score.threshold == g.commit_score.threshold


def test_sheet_names_the_external_score(external_guard):
    g, score = external_guard
    cf = g.sheet.confidence
    assert cf["kind"] == "external" and cf["digest"] == score.digest and cf["certify_items"] == g.sheet.n_ltt
    s = str(g.sheet)
    assert "external prefix score >=" in s and score.digest in s and "frozen" in s
    assert any("frozen before calibration" in a for a in g.sheet.assumptions)
    ps = policy_sheets(g.sheet)
    assert ps[0].status["commit_score"] == "external" and ps[0].status["commit_unit"] == "prefix"
    assert ps[0].status["commit_score_model"]["digest"] == score.digest
    r = next(r for r in (g._decide_quiet(x) for x in nbest_data(60, 3)[0]) if r.action == "commit")
    assert "external prefix score" in r.event["reason"] and r.reason.startswith("commit ")
    assert "external prefix score" in r.reason
    rs = [g._decide_quiet(x) for x in nbest_data(60, 4)[0]]
    assert all("learned" not in q.reason for q in rs)


def test_guard_file_round_trip_and_refusals(external_guard, tmp_path: Path):
    g, score = external_guard
    p = g.save(tmp_path / "g.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["config"]["recipe"]["commit_score"]["score"]["spec"] == score.spec  # spec and digest are in the file
    with pytest.raises(ValueError, match="Pass prefix_score="):
        ft.load(p)
    with pytest.raises(ValueError, match="does not match"):
        ft.load(p, prefix_score=FrozenPrefixScore(lambda c: None, name="other", spec={}))
    with pytest.raises(TypeError, match="FrozenPrefixScore"):
        ft.load(p, prefix_score=lambda c: None)
    g2 = ft.load(p, prefix_score=score)
    assert g2.config_id == g.config_id and g2.sheet == g.sheet
    assert g2.save(tmp_path / "g2.json").read_bytes() == p.read_bytes()
    xs, _ = nbest_data(60, 9)
    assert [key(g._decide_quiet(x)) for x in xs] == [key(g2._decide_quiet(x)) for x in xs]
    with pytest.raises(ValueError, match="online"):
        g.online()


def test_prefix_score_refused_on_other_guards(learned_guard, tmp_path: Path):
    p = learned_guard.save(tmp_path / "learned.json")
    with pytest.raises(ValueError, match="only for a guard calibrated with an external"):
        ft.load(p, prefix_score=FrozenPrefixScore(lambda c: None, name="s", spec={}))
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "score" not in d["config"]["recipe"]["commit_score"]  # old learned files keep their layout


def test_none_scores_never_commit_and_null_controls_run(nbest_cal):
    xs, ts, nulls = nbest_cal
    never = FrozenPrefixScore(lambda c: None, name="never", spec={})
    g = ft.calibrate(xs, ts, null_inputs=nulls, commit_unit="prefix", prefix_score=never, **KW)
    # nothing ever commits, so every threshold has risk 0 (the test passes down to the end of the grid)
    assert g.sheet.confidence["certify_no_score"] == g.sheet.n_ltt and g.sheet.ltt_commits == 0
    assert all(r.action != "commit" for r in (g._decide_quiet(x) for x in xs[:50]))
    # a guard that commits on (here: real) null input is refused by the null controls
    always = FrozenPrefixScore(lambda c: [c.p_top1] * len(c.words), name="p-top1", spec={})
    with pytest.raises(ft.NullControlError):
        ft.calibrate(xs, ts, null_inputs=xs[:60], commit_unit="prefix", prefix_score=always,
                     null_max_commit_rate=0.0, **KW)


def test_logits_context_has_the_frames():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    seen: list[tuple[int, int]] = []

    def fn(ctx: PrefixContext):
        assert ctx.log_probs is not None and ctx.log_probs.shape[1] == len(VOCAB)
        seen.append(ctx.log_probs.shape)
        return np.full(len(ctx.words), ctx.p_top1)

    score = FrozenPrefixScore(fn, name="p-top1-per-prefix", spec={"rule": "p_top1"})
    g = ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=40,
                     decoder_name="test-ctc", commit_unit="prefix", prefix_score=score)
    assert seen and all(c.passed for c in g.sheet.controls) and g.sheet.confidence["kind"] == "external"


# --- local reproduction of P11-16 LX-FL (needs the derived data; skipped without it) -------------------


P1116 = Path("C:/Users/zhang/bci-data/derived/p11-16")
EXP = Path(__file__).resolve().parents[1] / "experiments" / "2026-11-21-p5-35-external-prefix-score"


@pytest.mark.skipif(not (P1116 / "guard-LX-FL.status.json").exists() or os.environ.get("P5_35_LOCAL") != "1",
                    reason="local P11-16 data and P5_35_LOCAL=1 needed (slow: decodes about 5,000 windows)")
def test_local_lxfl_reproduction(tmp_path: Path):
    import subprocess
    import sys

    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(EXP / "run.py"), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert res["threshold"]["native"] == res["threshold"]["p11_16"] == 0.86
    assert res["pass"] is True
