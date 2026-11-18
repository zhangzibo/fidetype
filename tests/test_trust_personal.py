"""Tests of P5-01: drift tests (fidetype.trust.drift) and per-user profiles (fidetype.trust.personal)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust.adaptive import GuardedUpdateLoop
from fidetype.trust.drift import ConformalDriftTest, DriftMonitor, RiskDriftTest
from fidetype.trust.personal import PersonalTrust, UserProfile, calibration_stats, hash_user_id
from fidetype.trust.provenance import ProvenanceLedger, verify

from test_trust_dropin import PHRASES, nbest_data, noise_nbest

# --- drift tests: validity (false alarms) and power (detection delay) ---------------------------------------


def _se(p: float, n: int) -> float:
    return math.sqrt(p * (1 - p) / n)


def test_conformal_drift_false_alarm_rate_is_at_most_level():
    rng = np.random.default_rng(0)
    level, runs = 0.05, 300
    alarms = 0
    for r in range(runs):
        t = ConformalDriftTest(rng.normal(size=100), level=level, seed=r)
        t.update_many(rng.normal(size=600))
        alarms += t.alarmed
    assert alarms / runs <= level + 3 * _se(level, runs)


def test_conformal_drift_p_values_are_uniform_under_the_null():
    rng = np.random.default_rng(1)
    t = ConformalDriftTest(rng.normal(size=50), level=0.01)
    t.update_many(np.round(rng.normal(size=4000), 1))  # many ties: smoothed p-values stay uniform
    p = np.asarray(t.p_values)
    assert abs(p.mean() - 0.5) < 0.02 and abs(np.mean(p < 0.1) - 0.1) < 0.02


@pytest.mark.parametrize("shift,max_median_delay", [(-1.0, 60), (-0.5, 250), (0.5, 250)])
def test_conformal_drift_detects_a_shift_after_a_long_null_period(shift, max_median_delay):
    rng = np.random.default_rng(2)
    delays = []
    for r in range(30):
        t = ConformalDriftTest(rng.normal(size=200), level=0.01, seed=r)
        t.update_many(rng.normal(size=500))  # null period: the jump keeps the test able to react
        n0 = t.n
        for x in rng.normal(shift, 1.0, size=3000):
            if t.update(x).alarmed:
                break
        delays.append(t.n - n0 if t.alarmed else math.inf)
    assert np.median(delays) <= max_median_delay
    assert sum(math.isinf(d) for d in delays) <= 1


def test_one_sided_score_test():
    rng = np.random.default_rng(3)
    up = ConformalDriftTest(rng.normal(size=200), level=0.01, side="up")
    down = ConformalDriftTest(rng.normal(size=200), level=0.01, side="down")
    for x in rng.normal(-1.0, 1.0, size=400):  # live scores lower than the reference
        up.update(x)
        down.update(x)
    assert down.alarmed and not up.alarmed
    with pytest.raises(ValueError):
        ConformalDriftTest([0.1], side="sideways")
    with pytest.raises(ValueError):
        ConformalDriftTest([])


def test_risk_drift_false_alarm_rate_at_the_boundary_of_the_null():
    rng = np.random.default_rng(4)
    level, runs = 0.05, 300
    alarms = sum(RiskDriftTest(0.05, level=level).update_many(rng.random(1500) < 0.05).alarmed for _ in range(runs))
    assert alarms / runs <= level + 3 * _se(level, runs)


def test_risk_drift_detects_a_rate_above_alpha():
    rng = np.random.default_rng(5)
    delays = []
    for _ in range(30):
        t = RiskDriftTest(0.05, level=0.01)
        t.update_many(rng.random(300) < 0.02)
        n0 = t.n
        for x in rng.random(5000) < 0.2:
            if t.update(x).alarmed:
                break
        delays.append(t.n - n0)
    assert np.median(delays) <= 120
    with pytest.raises(ValueError):
        RiskDriftTest(0.05).update(1.5)
    with pytest.raises(ValueError):
        RiskDriftTest(0.05, bets=(1.0,))


def test_drift_monitor_splits_the_level_and_resets():
    m = DriftMonitor(reference_scores=[0.1, 0.2, 0.3], alpha=0.05, level_scores=0.01, level_risk=0.02)
    assert m.level == pytest.approx(0.03)
    for _ in range(200):
        m.update_loss(1.0)
    assert m.risk_alarm and not m.score_alarm
    m.reset([0.5, 0.6])
    assert not m.risk_alarm and m.scores.n_reference == 2 and m.risk.n == 0
    s = m.summary()
    assert s["risk"]["test"] == "betting-e-process" and json.dumps(s)


# --- profile -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def guard_and_data():
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    nulls = [noise_nbest(rng) for _ in range(60)]
    g = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, decoder_name="test-nbest")
    return g, xs, ts, nulls


def test_hash_user_id_is_salted_and_never_the_raw_id():
    a, b = hash_user_id("alice", "s1"), hash_user_id("alice", "s2")
    assert a != b and a.startswith("u:") and "alice" not in a and len(a) == 34
    assert hash_user_id("alice") == hash_user_id("alice")
    with pytest.raises(ValueError):
        hash_user_id("")


def test_profile_round_trip_holds_no_text_and_rebuilds_the_guard(guard_and_data, tmp_path):
    g, xs, ts, _ = guard_and_data
    stats = calibration_stats(g, xs, ts)
    assert stats["n_items"] == 300 and len(stats["reference_scores"]) == 300
    prof = UserProfile.new("participant-07", g, salt="secret", calibration=stats, consent_ref="consent:pending")
    path = prof.save(tmp_path / "p.json")
    raw = path.read_text(encoding="utf-8")
    assert "participant-07" not in raw
    for t in set(ts):  # no utterance text (the decoder's word list may appear in the guard config)
        assert f'"{t}"' not in raw
    back = UserProfile.load(path)
    assert back.user_hash == prof.user_hash and back.matches("participant-07", "secret")
    assert back.config_id == g.config_id and back.config_ids == [g.config_id]
    assert back.consent_ref == "consent:pending" and back.profile_version == prof.profile_version
    g2 = back.load_guard()
    assert g2.config_id == g.config_id
    assert g2.decide(xs[0]).action == g.decide(xs[0]).action
    assert len(prof.content_sha256()) == 64


def test_profile_refuses_text_and_wrong_schema(guard_and_data, tmp_path):
    g = guard_and_data[0]
    prof = UserProfile.new("u", g)
    prof.extra["notes"] = {"text": "i need help"}
    with pytest.raises(ValueError, match="text or signal"):
        prof.save(tmp_path / "bad.json")
    with pytest.raises(ValueError, match="not a user profile"):
        UserProfile.from_dict({"schema": "other"})
    with pytest.raises(ValueError):
        prof.add_history("x", truth="secret words")


# --- live controller ------------------------------------------------------------------------


def drifted_nbest(n: int, seed: int, *, gap: float, wrong_top: float = 0.0):
    """n-best lists with a fixed score gap (small gap: low confidence). ``wrong_top``: share with a confident
    wrong top-1 (the decoder got worse but still looks sure)."""
    rng = np.random.default_rng(seed)
    xs, ts = [], []
    for _ in range(n):
        t = str(rng.choice(PHRASES))
        others = [str(p) for p in rng.choice([p for p in PHRASES if p != t], size=3, replace=False)]
        if rng.random() < wrong_top:
            cands = [others[0], t, others[1], others[2]]
        else:
            cands = [t] + others
        scores = [0.0] + [-gap * float(rng.uniform(0.8, 1.2)) for _ in range(3)]
        xs.append(list(zip(cands, scores)))
        ts.append(t)
    return xs, ts


def _controller(guard_and_data, tmp_path, **kw):
    g, xs, ts, nulls = guard_and_data
    from fidetype.trust.dropin import TrustGuard

    live = TrustGuard(g.config, g._codec, g.sheet, None, g.audit_text)
    prof = UserProfile.new("user-1", live, salt="k", calibration=calibration_stats(live, xs, ts))
    loop = GuardedUpdateLoop(alpha=live.alpha, delta=live.delta, ledger=ProvenanceLedger())
    kw.setdefault("n_recal", 200)
    kw.setdefault("null_trials", 60)
    return PersonalTrust(prof, live, loop=loop, null_inputs=nulls, profile_path=tmp_path / "prof.json", **kw)


def test_no_alarm_and_no_change_on_data_like_the_calibration(guard_and_data, tmp_path):
    pt = _controller(guard_and_data, tmp_path)
    cid = pt.guard.config_id
    xs, ts = nbest_data(400, 11)
    for x, t in zip(xs, ts):
        pt.feedback(pt.decide(x), t)
        assert pt.maybe_recalibrate() is None
    assert not pt.monitor.score_alarm and not pt.monitor.risk_alarm
    assert pt.guard.config_id == cid and pt.profile.config_ids == [cid]


def test_score_drift_proposes_a_gated_recalibration(guard_and_data, tmp_path):
    pt = _controller(guard_and_data, tmp_path)
    cid0 = pt.guard.config_id
    xs, ts = drifted_nbest(900, 12, gap=0.7)  # confidence drops
    out = None
    alarm_at = None
    for i, (x, t) in enumerate(zip(xs, ts)):
        r = pt.decide(x)
        if alarm_at is None and pt.monitor.score_alarm:
            alarm_at = i
        pt.feedback(r, t)
        out = pt.maybe_recalibrate() or out
        if out is not None:
            break
    assert alarm_at is not None and alarm_at < 200
    assert out is not None
    ev = [h["event"] for h in pt.profile.history]
    assert ev[:2] == ["calibrate", "drift_alarm"]
    # Low-confidence data: the candidate calibrated on them commits on shuffled null input, so calibrate()
    # refuses it. The refusal is a recorded rejection; the live guard does not change; the proposal stays open.
    assert not out.accepted and "NullControlError" in out.reasons[0]
    assert ev[-1] == "recalibrate_rejected"
    assert pt.guard.config_id == cid0 and pt.proposal_reason is not None and pt.n_labels == 0
    led = pt.updater.loop.ledger
    assert [e["body"]["stage"] for e in led.entries if e["kind"] == "update"][-2:] in (
        ["proposed", "accepted"], ["proposed", "rejected"])
    assert verify(led.entries).ok
    saved = json.loads((tmp_path / "prof.json").read_text(encoding="utf-8"))
    assert saved["history"][-1]["event"].startswith("recalibrate_")


def test_risk_drift_tightens_at_once_and_only_an_accepted_update_loosens(guard_and_data, tmp_path):
    pt = _controller(guard_and_data, tmp_path)
    xs, ts = drifted_nbest(1500, 13, gap=6.0, wrong_top=0.5)  # confident and often wrong
    n_commit_after = 0
    tight_at = None
    for i, (x, t) in enumerate(zip(xs, ts)):
        r = pt.decide(x)
        if pt.tightened and tight_at is not None and r.action == "commit":
            n_commit_after += 1
        pt.feedback(r, t)
        if pt.tightened and tight_at is None:
            tight_at = i
        out = pt.maybe_recalibrate()
        if out is not None:
            break
    assert tight_at is not None and tight_at < 300
    assert n_commit_after == 0  # offer / withhold only while tightened
    assert math.isinf(float(pt.guard.config.policy["commit_p"])) or not pt.tightened
    ev = [h["event"] for h in pt.profile.history]
    assert "tighten" in ev and ev.index("drift_alarm") < ev.index("tighten")
    # the gated update on the new data passes the loop checks: it ends the tightening with a finite threshold
    assert out is not None and out.accepted, out and out.reasons
    assert not pt.tightened and math.isfinite(float(pt.guard.config.policy["commit_p"]))
    assert pt.profile.history[-1]["event"] == "recalibrate_accepted"
    assert pt.profile.config_ids[-1] == pt.guard.config_id and len(pt.profile.config_ids) == 3


def test_scheduled_recalibration_without_drift(guard_and_data, tmp_path):
    pt = _controller(guard_and_data, tmp_path, recalibrate_every=250)
    xs, ts = nbest_data(600, 14)
    outs = []
    for x, t in zip(xs, ts):
        pt.feedback(pt.decide(x), t)
        o = pt.maybe_recalibrate()
        if o is not None:
            outs.append(o)
    assert len(outs) >= 1
    assert all(h["reason"].startswith("scheduled") for h in pt.profile.history if h["event"].startswith("recal"))


def test_load_controller_from_a_saved_profile(guard_and_data, tmp_path):
    pt = _controller(guard_and_data, tmp_path)
    pt._save()
    pt2 = PersonalTrust.load(tmp_path / "prof.json", null_inputs=guard_and_data[3])
    assert pt2.guard.config_id == pt.guard.config_id
    assert pt2.monitor.scores.n_reference == 300 and pt2.monitor.risk.alpha == pt.guard.alpha
    with pytest.raises(ValueError):
        PersonalTrust(pt.profile, pt.guard, on_risk_drift="panic")


# --- P5-09: spread bets of the score test --------------------------------------------------------


@pytest.mark.parametrize("level", [0.05])
def test_spread_bets_keep_the_false_alarm_level(level):
    rng = np.random.default_rng(20)
    runs, alarms = 300, 0
    for r in range(runs):
        t = ConformalDriftTest(rng.normal(size=100), level=level, seed=r, spread=True)
        t.update_many(rng.normal(size=600))
        alarms += t.alarmed
    assert alarms / runs <= level + 3 * _se(level, runs)


@pytest.mark.parametrize("sd", [2.0, 0.5])
def test_spread_bets_detect_a_spread_change_at_the_same_centre(sd):
    rng = np.random.default_rng(21)
    delays, delays_old = [], []
    for r in range(30):
        ref, null, live = rng.normal(size=200), rng.normal(size=500), rng.normal(0.0, sd, size=3000)
        for spread, out in ((True, delays), (False, delays_old)):
            t = ConformalDriftTest(ref, level=0.01, seed=r, spread=spread)
            t.update_many(null)
            n0 = t.n
            for x in live:
                if t.update(x).alarmed:
                    break
            out.append(t.n - n0 if t.alarmed else math.inf)
    assert np.median(delays) <= 400 and sum(math.isinf(d) for d in delays) <= 1
    if sd == 2.0:  # the gap of P5-01: the mean bets alone do not see a wider spread
        assert sum(math.isinf(d) for d in delays_old) >= 25


def test_spread_off_is_the_p5_01_test_and_spread_on_is_reported():
    rng = np.random.default_rng(22)
    ref, live = rng.normal(size=50), rng.normal(size=300)
    a, b = ConformalDriftTest(ref, seed=3), ConformalDriftTest(ref, seed=3, spread=False)
    for x in live:
        assert a.update(x).e_value == b.update(x).e_value
    c = ConformalDriftTest(ref, seed=3, spread=True)
    c.update_many(live)
    assert c.p_values == a.p_values  # same p-values; only the bets differ
    assert c.state_summary()["spread"] is True and "spread" not in a.state_summary()
    m = DriftMonitor(reference_scores=ref, alpha=0.05, spread=True)
    assert m.scores.spread and not DriftMonitor(reference_scores=ref, alpha=0.05).scores.spread


# --- P5-10: guard-risk drift test in PersonalTrust -------------------------------------------------


class _StubResult:
    def __init__(self, seq: int, p: float, gr: float) -> None:
        self.seq, self.p_top1, self.guard_risk, self.action, self.text = seq, p, gr, "offer", None


class _StubGuard:
    """Replays recorded (p_top1, guard_risk) pairs; never commits (only the alarm path is tested)."""

    alpha, delta, config_id = 0.05, 0.1, "tcfg-stub"

    def __init__(self) -> None:
        self.seq = 0

    def decide(self, x, utterance_id=None):
        self.seq += 1
        return _StubResult(self.seq, float(x[0]), float(x[1]))


class _StubUpdater:
    def __init__(self, guard) -> None:
        self.guard = guard
        self.loop = type("L", (), {"n_check": 48})()


def _stub_controller(rng, **kw):
    g = _StubGuard()
    prof = UserProfile.new("user-2", None, salt="k", calibration={
        "reference_scores": list(rng.uniform(0.1, 0.2, size=200)),
        "reference_guard_risk": list(rng.uniform(0.0, 0.5, size=200))})
    return PersonalTrust(prof, g, updater=_StubUpdater(g), **kw)


def test_guard_risk_test_is_opt_in_and_sees_a_guard_risk_drift():
    rng = np.random.default_rng(30)
    live = [(float(p), float(gr)) for p, gr in zip(rng.uniform(0.1, 0.2, 2000), rng.uniform(0.3, 1.0, 2000))]
    old = _stub_controller(np.random.default_rng(31))  # default: p_top1 + observed risk only
    new = _stub_controller(np.random.default_rng(31), guard_risk_test=True, level_guard_risk=0.0025)
    assert old.guard_risk_test is None and "guard_risk" not in old.report()["drift"]
    alarm_at = None
    for i, x in enumerate(live):
        r0, r1 = old.decide(x), new.decide(x)
        old.feedback(r0, None)
        new.feedback(r1, None)
        if alarm_at is None and new.guard_risk_test.alarmed:
            alarm_at = i
    assert alarm_at is not None and alarm_at < 300
    assert not old.monitor.score_alarm and not new.monitor.score_alarm and old.proposal_reason is None
    ev = [h for h in new.profile.history if h["event"] == "drift_alarm"]
    assert [h["test"] for h in ev] == ["guard_risk"] and ev[0]["action"] == "propose"
    assert new.proposal_reason == "guard_risk drift alarm" and not new.tightened
    d = new.report()["drift"]
    assert d["guard_risk"]["name"] == "guard_risk" and d["level_total"] == pytest.approx(0.0125)
    assert json.dumps(new.profile.to_dict())


def test_guard_risk_test_needs_a_reference_and_real_profiles_have_one(guard_and_data, tmp_path):
    g, xs, ts, _ = guard_and_data
    stats = calibration_stats(g, xs, ts)
    assert len(stats["reference_guard_risk"]) == len(stats["reference_scores"]) == 300
    assert all(0.0 <= v <= 1.0 for v in stats["reference_guard_risk"])
    pt = _controller(guard_and_data, tmp_path, guard_risk_test=True)
    assert pt.guard_risk_test.n_reference == 300
    xs2, ts2 = nbest_data(300, 13)
    for x, t in zip(xs2, ts2):
        pt.feedback(pt.decide(x), t)
    assert not pt.guard_risk_test.alarmed and pt.guard_risk_test.n == 300
    stats.pop("reference_guard_risk")  # a profile from before P5-10
    prof = UserProfile.new("u", pt.guard, calibration=stats)
    with pytest.raises(ValueError, match="reference guard risks"):
        PersonalTrust(prof, pt.guard, guard_risk_test=True)
    with pytest.raises(ValueError):
        PersonalTrust(prof, pt.guard, on_guard_risk_drift="panic")


# --- P15-23 / P15-24: PersonalTrust re-calibrations through the default-deny gate -----------------


def test_personal_recalibration_uses_the_same_decoder_rule(guard_and_data, tmp_path):
    pt = _controller(guard_and_data, tmp_path, recalibrate_every=250)
    xs, ts = nbest_data(600, 15)
    outs = []
    for x, t in zip(xs, ts):
        pt.feedback(pt.decide(x), t)
        o = pt.maybe_recalibrate()
        if o is not None:
            outs.append(o)
    reached = [o for o in outs if o.record is not None and o.record.challenger_test is not None]
    assert reached, [o.reasons for o in outs]
    for o in reached:
        assert o.record.challenger_test.rule == "recalibration"
        assert not any("no champion outputs" in r for r in o.reasons)
    led = pt.updater.loop.ledger
    kinds = [e["body"]["details"].get("kind") for e in led.entries
             if e["kind"] == "update" and e["body"]["stage"] == "proposed"]
    assert kinds and all(k == "recalibration" for k in kinds)
    assert any(o.accepted for o in outs), [o.reasons for o in outs]
    assert verify(led.entries).ok
