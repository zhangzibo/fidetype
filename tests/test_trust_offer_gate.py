"""Tests of the P5-33 offer gate (fidetype.trust.offer_gate, TrustGuard.offer_gates)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import offer_gate as og
from fidetype.trust.offer_gate import OfferGate

from test_trust_dropin import nbest_data, noise_nbest


def _lp(P):
    return np.log(np.clip(np.asarray(P, dtype=np.float64), 1e-12, None))


def test_coherence_reads_the_frame_order():
    rng = np.random.default_rng(0)
    T, V = 400, 8
    # runs of 20 frames of one token: adjacent frames are alike
    P = np.full((T, V), 0.02)
    for t in range(T):
        P[t, (t // 20) % V] = 1 - 0.02 * (V - 1)
    c, cr = og.coherence(_lp(P))
    assert c > 0.3 and cr > 1.0
    cs, crs = og.coherence(_lp(P[rng.permutation(T)]))
    assert abs(cs) < 0.05 and abs(crs) < 0.2
    # same per-frame statistics, different order
    assert og.frame_features(_lp(P))["peak"] == pytest.approx(og.frame_features(_lp(P[rng.permutation(T)]))["peak"])
    u = np.full((T, V), 1 / V)
    assert og.coherence(np.log(u))[0] == pytest.approx(0.0, abs=1e-12)
    assert og.coherence(np.log(u[:1])) == (0.0, 0.0)


def test_nb_coherence_ignores_the_blank_column():
    """P14-54: nb_coherence = coherence without the blank column (CTC frames are mostly blank)."""
    rng = np.random.default_rng(1)
    T, V = 600, 6
    P = np.zeros((T, V))
    P[:, 0] = 0.97  # mostly blank
    for t in range(T):
        P[t, 1 + (t // 3) % (V - 1)] += 0.03  # short runs of 3 frames of one character
    P /= P.sum(1, keepdims=True)
    lp = _lp(P)
    want = og.coherence(lp[:, 1:])[0]
    assert og.coherence(lp, drop=0)[0] == pytest.approx(want)
    f = og.frame_features(lp, blank=0)
    assert f["nb_coherence"] == pytest.approx(want) and want > 0
    fs = og.frame_features(lp[rng.permutation(T)], blank=0)
    assert abs(fs["nb_coherence"]) < 0.25 * want
    assert set(f) == set(og.FRAME_FEATURES) and "nb_coherence" in og.LOGIT_FEATURES
    assert OfferGate("nb_coherence", 0.0).label() == "nb_coherence >= 0"


def test_nbest_features():
    f = og.nbest_features([{"text": "ab", "score": -1.0, "char_confidences": [0.5, 1.0]},
                           {"text": "ac", "score": -3.0}])
    assert f == {"margin": 1.0, "conf_mean": 0.75}
    assert og.nbest_features([{"text": "abc", "score": 0.0}]) == {"margin": 0.0, "conf_mean": 0.0}

    class LM:
        def score_sentence(self, text, eos=False):
            return -float(len(text)) * (2.0 if "z" in text else 1.0)

    f = og.nbest_features([{"text": "zz", "score": 0.0}, {"text": "ab", "score": -1.0}], lm=LM())
    assert f["char_lm"] == -2.0 and f["char_lm_best"] == -1.0


def test_gate_object():
    g = OfferGate.fit("p_top1", [0.1, 0.2, 0.3, 0.4] * 5, keep=0.95)
    assert g.threshold == 0.1  # index floor(0.05 x 20) = 1 of the sorted values
    assert g.violation(0.1) is None and "p_top1" in g.violation(0.05)
    assert OfferGate.from_dict(json.loads(json.dumps(g.to_dict()))) == g
    with pytest.raises(ValueError, match="unknown"):
        OfferGate("nope", 0.0)
    with pytest.raises(ValueError, match="finite"):
        OfferGate("p_top1", math.nan)
    with pytest.raises(ValueError, match="lm_name"):
        OfferGate("char_lm", -2.0)
    with pytest.raises(ValueError, match="logits"):
        OfferGate("margin", 0.0).check_kind("logits")
    with pytest.raises(ValueError, match="needs the character LM"):
        OfferGate("char_lm", -2.0, lm_name="x").check_kind("nbest")
    OfferGate("coherence", 0.0).check_kind("logits")


@pytest.fixture(scope="module")
def data():
    xs, ts = nbest_data(240, 0)
    rng = np.random.default_rng(1)
    return xs, ts, [noise_nbest(rng) for _ in range(40)]


@pytest.fixture(scope="module")
def guard(data):
    xs, ts, nulls = data
    return ft.calibrate(xs, ts, null_inputs=nulls, null_trials=40, decoder_name="test-nbest", modality="emg")


def test_gate_changes_offers_only(data, guard, tmp_path):
    xs, _, nulls = data
    base = [guard._decide_quiet(x) for x in xs]
    guard.collect_offer_features = True
    feats = []
    for x in xs:
        guard._decide_quiet(x)
        feats.append(guard.last_offer_features)
    guard.collect_offer_features = False
    offered = [f["p_top1"] for r, f in zip(base, feats) if r.action == "offer"]
    gate = OfferGate.fit("p_top1", offered, keep=0.5)
    path = tmp_path / "g.json"
    guard.save(path)
    assert "offer_gate" not in json.loads(path.read_text(encoding="utf-8"))  # old files keep their bytes
    gated = ft.load(path, offer_gate=gate)
    assert gated.config_id == guard.config_id
    after = [gated._decide_quiet(x) for x in xs]
    for a, b in zip(base, after):
        if a.action != "offer":
            assert (b.action, b.text, b.choices) == (a.action, a.text, a.choices)
        else:
            assert b.action in ("offer", "withhold")
    n_off = sum(a.action == "offer" for a in after)
    assert 0 < n_off < len(offered)
    w = next(r for r in after if r.action == "withhold" and "offer gate" in r.reason)
    assert w.reason.startswith("withhold: no evidence of signal for an offer") and w.choices == ()
    # the decision event and the audit header name the gate
    r = gated.decide(next(x for x, a, b in zip(xs, base, after) if a.action == "offer" and b.action == "withhold"))
    assert r.action == "withhold" and gated.audit_log[-1]["offer_gate"].startswith("offer gate: p_top1")
    assert gated.audit_header()["offer_gate"] == [gate.to_dict()]
    # save / load keeps the gate; offer_gate=False switches it off
    gated.save(path)
    assert json.loads(path.read_text(encoding="utf-8"))["offer_gate"] == gate.to_dict()
    again = ft.load(path)
    assert [g.to_dict() for g in again.offer_gates] == [gate.to_dict()]
    assert [r.action for r in (again._decide_quiet(x) for x in xs)] == [r.action for r in after]
    off = ft.load(path, offer_gate=False)
    assert off.offer_gates == () and [r.action for r in (off._decide_quiet(x) for x in xs)] == \
        [r.action for r in base]


def test_recheck_sees_the_gate(data, guard):
    xs, _, nulls = data
    rc0 = ft.recheck_offer_control(guard, xs, null_inputs=nulls)
    g = ft.TrustGuard(guard.config, guard._codec, guard.sheet, offer_gate=OfferGate("p_top1", 2.0))  # no offers
    rc = ft.recheck_offer_control(g, xs, null_inputs=nulls)
    assert rc["commits_match_sheet"] is rc0["commits_match_sheet"] is True
    assert rc["ltt_commits"] == rc0["ltt_commits"]
    assert rc["real"]["n_offer"] == 0 and all(c["n_offer"] == 0 for c in rc["controls"]) and rc["passed"]
    assert rc0["controls"][0]["n_offer"] > 0


def _rise_fall(T=600, V=6, rise=6, fall=1, seed=0):
    """CTC-like frames: each character probability rises over ``rise`` frames and falls over ``fall``."""
    rng = np.random.default_rng(seed)
    P = np.zeros((T, V))
    P[:, 0] = 1.0
    t = 5
    while t + rise + fall + 3 < T:
        c = 1 + int(rng.integers(V - 1))
        up = np.linspace(0, 0.9, rise + 1)[1:]
        down = np.linspace(0.9, 0, fall + 1)[1:]
        prof = np.concatenate([up, down])
        P[t:t + len(prof), c] = prof
        P[t:t + len(prof), 0] = 1.0 - prof
        t += len(prof) + 3
    P = 0.99 * P + 0.01 / V
    return _lp(P / P.sum(1, keepdims=True))


def test_direction_features_change_sign_on_reversal():
    """P14-57: the direction features are antisymmetric in time; coherence is symmetric."""
    lp = _rise_fall()
    f, fr = og.frame_features(lp, blank=0), og.frame_features(np.ascontiguousarray(lp[::-1]), blank=0)
    for k in og.DIRECTION_FEATURES:
        assert f[k] == pytest.approx(-fr[k], abs=1e-12) and -1.0 <= f[k] <= 1.0, k
    # all columns: when only the blank and one character trade mass, their cubes cancel (time_asym ~ 0)
    assert abs(f["time_asym"]) < 1e-9
    assert f["coherence"] == pytest.approx(fr["coherence"], abs=1e-12)
    # slow rise, sharp fall: the character columns fall in large steps (time_asym < 0) and a high
    # probability rises more slowly than it falls (decay_asym < 0)
    assert f["nb_time_asym"] < 0 and f["nb_decay_asym"] < 0
    g = og.frame_features(_rise_fall(rise=1, fall=6), blank=0)
    assert g["nb_time_asym"] > 0 and g["nb_decay_asym"] > 0
    # constant frames and one frame: 0
    u = np.log(np.full((50, 6), 1 / 6))
    assert all(og.frame_features(u)[k] == 0.0 for k in og.DIRECTION_FEATURES)
    assert og.time_asymmetry(u[:1]) == (0.0, 0.0)
    assert set(og.DIRECTION_FEATURES) <= set(og.LOGIT_FEATURES)


def test_negated_feature_gate():
    g = OfferGate("-nb_time_asym", 0.0)
    assert g.base == "nb_time_asym" and g.value({"nb_time_asym": 0.25}) == -0.25
    assert g.violation(g.value({"nb_time_asym": 0.25})) is not None
    assert g.violation(g.value({"nb_time_asym": -0.25})) is None
    assert OfferGate.from_dict(json.loads(json.dumps(g.to_dict()))) == g
    g.check_kind("logits")
    with pytest.raises(ValueError, match="unknown"):
        OfferGate("-nope", 0.0)
    with pytest.raises(ValueError, match="logits"):
        OfferGate("-margin", 0.0).check_kind("logits")
    # an offer passes a plain gate iff it fails the negated gate at threshold 0 (the P14-57 sign rule)
    for v in (-0.3, 0.2):
        a, b = OfferGate("time_asym", 0.0), OfferGate("-time_asym", 0.0)
        assert (a.violation(a.value({"time_asym": v})) is None) != (b.violation(b.value({"time_asym": v})) is None)


def test_negated_gate_in_the_guard(data, guard):
    xs, _, _ = data
    base = [guard._decide_quiet(x) for x in xs]
    guard.collect_offer_features = True
    p = []
    for x in xs:
        guard._decide_quiet(x)
        p.append(guard.last_offer_features["p_top1"])
    guard.collect_offer_features = False
    cut = float(np.median([v for r, v in zip(base, p) if r.action == "offer"]))
    plain = ft.TrustGuard(guard.config, guard._codec, guard.sheet, offer_gate=OfferGate("p_top1", cut))
    neg = ft.TrustGuard(guard.config, guard._codec, guard.sheet, offer_gate=OfferGate("-p_top1", -cut))
    for x, r, v in zip(xs, base, p):
        a, b = plain._decide_quiet(x).action, neg._decide_quiet(x).action
        if r.action != "offer":
            assert a == b == r.action
        else:
            assert a == ("offer" if v >= cut else "withhold")
            assert b == ("offer" if v <= cut else "withhold")
