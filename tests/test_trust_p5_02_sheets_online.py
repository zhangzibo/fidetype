"""Tests of P5-02 completion: per-policy guarantee sheets, the online drop-in guard, joint precision + halluc LTT."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import guarantee_sheet as G
from fidetype.trust import halluc_bound as H
from fidetype.trust.bandit_risk import BanditCommitRiskControl
from fidetype.trust.online_risk import OnlineCommitRiskControl
from fidetype.trust.risk_control import CommitRiskControl

from test_trust_dropin import PHRASES, fake_nbest, nbest_data, noise_nbest
from test_trust_halluc_bound import (HAZARD, SEP, VOCAB, MockLLM, char_label_fn, data, make_decode,
                                     population as halluc_population)


@pytest.fixture(scope="module")
def guards():
    xs, ts = nbest_data(600, 0)
    rng = np.random.default_rng(1)
    kw = dict(null_inputs=[noise_nbest(rng) for _ in range(60)], null_trials=60, decoder_name="test-nbest")
    return ft.calibrate(xs, ts, **kw), ft.calibrate(xs, ts, target_precision=0.9, **kw)


# --- per-policy sheets --------------------------------------------------------------------


def _roundtrip(sheets, tmp_path):
    p = G.save_sheets(sheets, tmp_path / "sheets.json")
    back = G.load_sheets(p)
    assert back == list(sheets)
    assert [s.to_dict() for s in back] == [s.to_dict() for s in sheets]
    json.loads(p.read_text(encoding="utf-8"))  # strict JSON (no NaN / Infinity)
    return back


def test_sheet_of_every_policy_type_roundtrips(guards, tmp_path):
    base, prec = guards
    rng = np.random.default_rng(0)
    s = rng.uniform(0, 1, 400)
    c = (rng.random(400) < 0.5 * (1 - s)).astype(float)
    crc = CommitRiskControl(alpha=0.1, method="crc").fit(s, c)
    ltt = CommitRiskControl(alpha=0.1, method="ltt", delta=0.1).fit(s, c)
    on = {m: OnlineCommitRiskControl(alpha=0.1, method=m).fit(s[:200], c[:200]) for m in ("aci", "aci_window", "window")}
    for m, ctrl in on.items():
        for si, ci in zip(s[200:], c[200:]):
            ctrl.step(float(si), float(ci))
    bandit = BanditCommitRiskControl(alpha=0.1, explore=0.1, lam_init=0.5, seed=1)
    for si, ci in zip(s, c):
        bandit.step(float(si), float(ci))
    sheets = (G.policy_sheets(crc) + G.policy_sheets(ltt) + G.policy_sheets(prec)
              + [G.policy_sheets(on[m])[0] for m in on] + G.policy_sheets(bandit))
    types = [x.policy_type for x in sheets]
    assert types == ["offline_crc", "offline_ltt", "offline_ltt", "precision_ltt", "online_aci",
                     "online_aci_window", "online_window", "bandit"]
    for x in sheets:
        assert x.schema == G.SHEET_SCHEMA and x.policy_type in G.POLICY_TYPES and x.validity in G.VALIDITY_KINDS
        assert x.statement and x.method and x.assumptions and x.not_guaranteed
        assert "alpha" in x.levels and "delta" in x.levels
        assert any("medical" in a for a in x.not_guaranteed) or x.policy_type in ("precision_ltt",)
        txt = str(x)
        assert x.policy_type in txt and "not guaranteed" in txt and "assumptions" in txt
    assert sheets[0].delta is None and sheets[0].validity == "finite_sample_expectation"
    assert sheets[4].delta is None and sheets[4].validity == "deterministic_long_run"
    assert sheets[6].validity == "approximate"
    assert sheets[7].validity == "deterministic_long_run+anytime_audit"
    # the online sheets carry the certificate of the controller
    assert sheets[4].status["certificate"] == pytest.approx(on["aci"].report()["certificate"])
    assert sheets[4].status["realised"] <= sheets[4].status["certificate"] + 1e-12
    _roundtrip(sheets, tmp_path)


def test_guard_sheets_match_guarantee_sheet(guards, tmp_path):
    base, prec = guards
    bs = base.policy_sheets()
    assert [x.policy_type for x in bs] == ["offline_ltt"]
    b = bs[0]
    assert (b.alpha, b.delta) == (base.alpha, base.delta) and b.config_id == base.config_id
    assert b.calibration["n_items"] == 600 and b.calibration["split"]["ltt"] == base.sheet.n_ltt
    assert [c["name"] for c in b.controls] == [c.name for c in base.sheet.controls]
    ps = prec.policy_sheets()
    q = prec.sheet.precision
    assert ps[1].levels["target_precision"] == 0.9 and ps[1].delta == q["delta_p"]
    assert ps[1].status["feasible"] == q["feasible"]
    # loading the saved guard file gives the same sheets (no decoder needed)
    path = prec.save(tmp_path / "g.json")
    back = G.load_sheets(path)
    assert [x.to_dict() | {"created_utc": ""} for x in back] == [x.to_dict() | {"created_utc": ""} for x in ps]
    assert G._main([str(path)]) == 0
    assert G._main([str(path), "--json"]) == 0


def test_sheet_schema_checks_and_forward_keys():
    d = G.sheet_from_risk_control(CommitRiskControl(method="crc").fit([0.9] * 30, [0] * 30)).to_dict()
    d["future_field"] = {"x": 1}
    s = G.PolicySheet.from_dict(d)
    assert s.extra == {"future_field": {"x": 1}} and s.to_dict()["future_field"] == {"x": 1}
    for bad in ({"schema": "fidetype.guarantee-sheet/2.0"}, {"policy_type": "magic"}, {"validity": "always"}):
        with pytest.raises(ValueError):
            G.PolicySheet.from_dict({**d, **bad})
    with pytest.raises(TypeError):
        G.policy_sheets(object())
    with pytest.raises(ValueError):
        G.sheet_from_risk_control(CommitRiskControl())


def test_lazy_exports():
    for name in ("PolicySheet", "policy_sheets", "save_sheets", "load_sheets", "OnlineGuard"):
        assert name in ft.__all__ and getattr(ft, name) is not None


# --- online drop-in guard -----------------------------------------------------------------


def drifted(n: int, seed: int, q: float):
    """Drift after calibration: with probability q the decoder is confidently wrong (truth = another phrase)."""
    rng = np.random.default_rng(seed)
    xs, ts = [], []
    for _ in range(n):
        t = str(rng.choice(PHRASES))
        x = fake_nbest(t, rng)
        if rng.random() < q:
            t = str(rng.choice([p for p in PHRASES if p != t]))
        xs.append(x)
        ts.append(t)
    return xs, ts


def test_offline_defaults_unchanged(guards):
    base, _ = guards
    xs, _ = nbest_data(30, 7)
    before = [base._decide_quiet(x) for x in xs]
    og = base.online("aci")
    for x in xs[:5]:
        og.decide(x)
    after = [base._decide_quiet(x) for x in xs]
    assert [(a.action, a.text) for a in before] == [(a.action, a.text) for a in after]
    assert base.config.policy["commit_p"] == base.sheet.commit_threshold


def test_online_aci_adapts_to_drift(guards):
    base, _ = guards
    xs, ts = drifted(1500, 3, 0.3)
    off = [base._decide_quiet(x) for x in xs]
    off_rate = sum(r.action == "commit" and r.text != t for r, t in zip(off, ts)) / len(xs)
    assert off_rate > 2 * base.alpha  # the offline bound breaks under drift
    og = base.online("aci")
    wrong = 0
    for x, t in zip(xs, ts):
        r, tk = og.decide(x)
        if r.action == "commit":
            assert r.text is not None and r.p_top1 >= og.floor
            wrong += r.text != t
        og.feedback(tk, t)
    rep = og.report()
    assert rep["n_observed"] == len(xs) and rep["pending"] == 0
    assert wrong / len(xs) == pytest.approx(rep["mean_loss"])
    assert rep["mean_loss"] <= rep["certificate"] + 1e-12
    assert rep["certificate"] <= og.controller.prior_bound(len(xs)) + 1e-12
    assert rep["mean_loss"] < off_rate and rep["mean_loss"] <= base.alpha + 0.02
    # audit records carry the online threshold; the sheet lists the offline + the online policy
    rec = base.audit_log[-1]
    assert rec["online"]["method"] == "aci" and rec["config_id"] == base.config_id
    sheets = og.policy_sheets()
    assert [s.policy_type for s in sheets] == ["offline_ltt", "online_aci"]
    assert sheets[-1].status["n_observed"] == len(xs)


def test_online_methods_and_bandit(guards):
    base, _ = guards
    xs, ts = drifted(400, 4, 0.2)
    for m in ("aci_window", "window"):
        og = base.online(m, floor=False)
        for x, t in zip(xs, ts):
            r, tk = og.decide(x)
            og.feedback(tk, t)
        rep = og.report()
        assert rep["n_observed"] == len(xs)
        if m == "aci_window":
            assert rep["mean_loss"] <= rep["certificate"] + 1e-12
        assert og.policy_sheets()[-1].policy_type == f"online_{m}"
    ob = base.online("bandit", explore=0.2, floor=False, seed=2)
    n_explore = 0
    for x, t in zip(xs, ts):
        r, tk = ob.decide(x)
        if tk.explore:
            n_explore += 1
            assert r.action == "offer" and r.text is None  # exploration never commits
        ob.feedback(tk, t if tk.shown else None)
    rep = ob.report()
    assert rep["n_explore"] == n_explore and rep["realised"] <= rep["certificate"] + 1e-12
    s = ob.policy_sheets()[-1]
    assert s.policy_type == "bandit" and s.levels["explore"] == 0.2
    obp = base.online("bandit", target="precision", alpha=0.2, floor=False)
    for x, t in zip(xs, ts):
        r, tk = obp.decide(x)
        obp.feedback(tk, t if tk.shown else None)
    rp = obp.report()
    if rp["n_commits"]:
        assert rp["realised"] <= rp["certificate"] + 1e-12
    with pytest.raises(ValueError):
        base.online("magic")
    with pytest.raises(ValueError):
        base.online("aci", explore=0.1)


def test_bandit_audit_rows_below_the_floor_are_marked_floored(guards):
    """G3 review L2: rows with a grid threshold below the floor are not bounds for that threshold."""
    base, _ = guards
    ob = base.online("bandit", explore=0.2, seed=5)
    if not math.isfinite(ob.floor):
        pytest.skip("offline guard never commits")
    xs, ts = drifted(100, 6, 0.2)
    for x, t in zip(xs, ts):
        r, tk = ob.decide(x)
        ob.feedback(tk, t if tk.shown else None)
    a = ob.report()["audit"]
    assert a["floored"] == [g < ob.floor for g in a["grid"]] and any(a["floored"])
    for g, f, ub in zip(a["grid"], a["floored"], a["upper_wrong"]):
        assert (ub is None) == f
    assert ob.controller.seed == 5 and base.online("bandit", explore=0.1).controller.seed is None
    s = ob.policy_sheets()[-1]
    assert any("floored" in x for x in s.assumptions) and any("unpredictable" in x for x in s.assumptions)


def test_online_floor_when_offline_never_commits(guards):
    base, _ = guards
    g = ft.TrustGuard(base.config.with_policy(commit_p=math.inf), base._codec, base.sheet)
    og = g.online("aci")
    xs, ts = nbest_data(50, 9)
    for x, t in zip(xs, ts):
        r, tk = og.decide(x)
        assert r.action != "commit"
        og.feedback(tk, t)


# --- joint precision + hallucination LTT ----------------------------------------------------


def test_joint_ltt_with_precision_bound_holds():
    """Three risks, one test: P(any certified risk above its level) <= delta (synthetic, exchangeable)."""
    rng = np.random.default_rng(11)
    pop = halluc_population(40000, rng)
    pa = H._arrays(pop)
    configs = H.grid([math.inf] + [round(1 - 0.05 * k, 2) for k in range(21)], (0.005, 0.02, math.inf),
                     (0.5, 2.0, math.inf))
    alpha, alpha_h, tp, delta = 0.1, 0.02, 0.85, 0.1
    viol = feasible = 0
    for _ in range(120):
        idx = rng.choice(len(pop), size=800, replace=False)
        res = H.joint_ltt([pop[i] for i in idx[:400]], [pop[i] for i in idx[400:]], configs, alpha=alpha,
                          alpha_h=alpha_h, delta=delta, target_precision=tp)
        if res.selected is None:
            continue
        feasible += 1
        assert len(res.test_pvalues) == 3 and max(res.test_pvalues) <= delta
        k = H._counts(pa, res.selected)
        viol += (k["wc_loss"] / k["n"] > alpha or k["h_loss"] / k["n"] > alpha_h
                 or (k["commits"] - k["right"]) / max(1, k["commits"]) > 1 - tp)
    assert feasible > 60
    assert viol / feasible <= delta + 3 * math.sqrt(delta * (1 - delta) / feasible)
    # without the precision target nothing changes
    a = H.joint_ltt(pop[:400], pop[400:800], configs, alpha=alpha, alpha_h=alpha_h, delta=delta)
    assert len(a.test_pvalues) == 2 and "target_precision" not in a.to_dict()
    with pytest.raises(ValueError):
        H.joint_ltt(pop[:10], pop[10:20], configs, alpha=alpha, alpha_h=alpha_h, delta=delta, target_precision=1.0)


def test_calibrate_precision_with_halluc_bound(tmp_path):
    xs, ts = data(240, 11)
    decode = make_decode()
    g = H.CommitGrounding(char_label_fn, word_sep_id=SEP, name="test-chars")
    kw = dict(alpha=0.2, delta=0.1, vocab=VOCAB, blank="_", decode_fn=decode, null_trials=30, decoder_name="t",
              seed=0, grounding=g, llm=MockLLM(HAZARD.values()), halluc_alpha=0.05, fluent_threshold=-5.0,
              halluc_grid={"commit_p": [math.inf] + [round(1 - 0.05 * k, 2) for k in range(21)],
                           "tau_commit": [0.05, 0.2, math.inf], "tau_word": [1.0, 3.0, math.inf]})
    gj = ft.calibrate(xs, ts, target_precision=0.7, precision_delta=0.05, **kw)
    q, h = gj.sheet.precision, gj.sheet.halluc
    assert q["joint_with"] == "halluc" and q["delta_p"] == 0.05 == h["delta_h"]  # one level: min(0.1, 0.05)
    assert h["target_precision"] == 0.7 and "p_precision" in h["method"]
    assert gj.config.recipe["precision_bound"]["target_precision"] == 0.7
    if q["feasible"]:
        assert q["test_counts"]["commits"] >= q["min_commits"] - q["test_counts"]["wrong"]
        tc = h["test_counts"]
        assert q["test_counts"]["wrong"] == tc["commits"] - tc["right"]
    txt = str(gj.sheet)
    assert "precision bound" in txt and "one joint test" in txt
    sheets = gj.policy_sheets()
    assert [s.policy_type for s in sheets] == ["offline_ltt", "joint_fluent_wrong"]
    assert sheets[1].levels["target_precision"] == 0.7 and len(sheets[1].risk["risks"]) == 3
    p = gj.save(tmp_path / "gj.json")
    g2 = ft.load(p, decode_fn=decode, grounding=g)
    assert g2.sheet.precision == q and g2.config_id == gj.config_id
    _roundtrip(sheets, tmp_path)
