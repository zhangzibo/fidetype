"""Tests for fidetype.trust.adaptive (F1 guarded update loop, simulated feedback user)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from fidetype.trust import FeedbackUser, GuardedUpdateLoop
from fidetype.trust.adaptive import DEFAULT_EVIDENCE_GATE, char_error_rate
from fidetype.trust.content import CommitGate
from fidetype.trust.session_risk import min_ltt_items


def rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


# --- FeedbackUser ------------------------------------------------------------


def test_offer_accept_gives_the_truth():
    o = FeedbackUser().respond_offer(["a b", "a c"], "a c", rng())
    assert o.source == "accept" and o.label == "a c" and o.label_correct and o.truth_known
    assert o.observed_commit_loss is None and o.true_loss == 0.0


def test_offer_reject_or_retype():
    u = FeedbackUser(p_retype=0.0)
    o = u.respond_offer(["x"], "y", rng())
    assert o.source == "reject" and o.label is None and o.label_correct is None
    o = FeedbackUser(p_retype=1.0).respond_offer(["x"], "y", rng())
    assert o.source == "retype" and o.label == "y"


def test_sloppy_accept_gives_a_wrong_label():
    u = FeedbackUser(p_retype=1.0, p_sloppy=1.0, sloppy_max_cer=0.2)
    o = u.respond_offer(["hello wordd"], "hello world", rng())
    assert o.source == "sloppy-accept" and o.label == "hello wordd" and o.label_correct is False


def test_commit_right_wrong_silent():
    r = rng()
    assert FeedbackUser().respond_commit("a", "a", r).source == "kept"
    o = FeedbackUser(p_notice=1.0).respond_commit("a", "b", r)
    assert o.source == "correction" and o.observed_commit_loss == 1.0 and o.label == "b"
    o = FeedbackUser(p_notice=0.0).respond_commit("a", "b", r)
    assert o.silent_error and o.observed_commit_loss == 0.0 and o.true_loss == 1.0 and o.label == "a"
    assert o.label_correct is False


def test_notice_rate_is_respected():
    u, r = FeedbackUser(p_notice=0.5), rng(1)
    silent = np.mean([u.respond_commit("a", "b", r).silent_error for _ in range(4000)])
    assert 0.45 < silent < 0.55


def test_bad_probability_raises():
    with pytest.raises(ValueError):
        FeedbackUser(p_notice=1.5)


def test_char_error_rate():
    assert char_error_rate("abc", "abc") == 0.0
    assert char_error_rate("abd", "abc") == pytest.approx(1 / 3)
    assert char_error_rate("", "") == 0.0



# --- GuardedUpdateLoop ---------------------------------------------------------


GOOD_RISK = 0.2  # guard risk of an item with neural evidence (passes max_guard_risk 1.0)
NO_EVIDENCE = 1.0  # guard risk of an LM-only text (every character low evidence)


def fill_check(loop: GuardedUpdateLoop, start: int, n: int, score: float = 0.9, loss: float = 0.0,
               risk: float | None = GOOD_RISK, champion=None) -> None:
    for i in range(start, start + n):
        loop.add_check_item(i, score, loss, text="a b", guard_risk=risk, champion=champion)


def quiet_nulls(n: int = 20):
    """Null outputs that the gate refuses (no evidence) or that score low."""
    return [(0.99, "the cat", NO_EVIDENCE)] * (n // 2) + [(-math.inf, "a", GOOD_RISK)] * (n - n // 2)


def validate(loop: GuardedUpdateLoop, uniform=None, shuffled=None):
    loop.recalibrate()
    loop.check_null_controls(uniform=quiet_nulls() if uniform is None else uniform,
                             shuffled=quiet_nulls() if shuffled is None else shuffled)
    return loop.finish_update()


# safe-by-construction defaults


def test_default_gate_is_the_evidence_gate():
    loop = GuardedUpdateLoop()
    assert loop.commit_gate == DEFAULT_EVIDENCE_GATE and loop.evidence_gate and not loop.unsafe
    assert loop.report()["evidence_gate"] is True


def test_loop_refuses_to_start_without_evidence_gate():
    with pytest.raises(ValueError, match="evidence commit gate"):
        GuardedUpdateLoop(commit_gate=CommitGate())
    with pytest.raises(ValueError):
        GuardedUpdateLoop(commit_gate=None)
    loop = GuardedUpdateLoop(commit_gate=None, unsafe=True)  # explicit opt-out
    assert loop.commit_gate == CommitGate() and not loop.evidence_gate


def test_no_commit_before_recalibration():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1", trained_on=range(10))
    d = loop.decide(1.0, guard_risk=GOOD_RISK)
    assert not d.commit and d.reason == "check-block"


def test_check_block_must_be_fresh():
    loop = GuardedUpdateLoop()
    loop.new_version("v1", trained_on=[1, 2, 3])
    with pytest.raises(ValueError):
        loop.add_check_item(2, 0.5, 0.0)


def test_check_block_needs_min_items():
    loop = GuardedUpdateLoop()
    loop.new_version("v1")
    fill_check(loop, 0, min_ltt_items(0.05, 0.1) - 1)
    with pytest.raises(ValueError):
        loop.recalibrate()
    with pytest.raises(ValueError):
        GuardedUpdateLoop(n_check=10)


def test_no_commit_without_null_controls_and_acceptance():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    loop.recalibrate()
    d = loop.decide(0.99, text="a b", guard_risk=GOOD_RISK)
    assert not d.commit and d.reason == "update-pending"
    with pytest.raises(ValueError, match="check_null_controls"):
        loop.finish_update()
    with pytest.raises(ValueError, match="uniform and frame-shuffled"):
        loop.check_null_controls(uniform=quiet_nulls())


def test_clean_block_allows_commits_and_new_version_blocks_them():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1", trained_on=[])
    fill_check(loop, 0, 48, score=0.9, loss=0.0)
    rec = validate(loop)
    assert rec.accepted and rec.reasons == () and math.isfinite(rec.lambda_session) and rec.lambda_session <= 0.9
    d = loop.decide(0.95, text="a b", guard_risk=GOOD_RISK)
    assert d.commit and d.version == "v1"
    loop.observe(d, 0.0)
    loop.new_version("v2", trained_on=range(48))
    assert not loop.decide(0.99, guard_risk=GOOD_RISK).commit  # the update invalidates the calibration
    loop.start_session("d2")
    assert not loop.calibrated


def test_decision_without_guard_risk_never_commits():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    validate(loop)
    d = loop.decide(0.99, text="a b")
    assert not d.commit and d.reason == "gate"
    d = loop.decide(0.99, text="a b", guard_risk=NO_EVIDENCE)
    assert not d.commit and d.reason == "gate"


def test_gate_blocks_empty_text():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    validate(loop)
    d = loop.decide(0.99, text_ok=False, guard_risk=GOOD_RISK)
    assert not d.commit and d.reason == "gate"
    assert not loop.decide(0.99, text="   ", guard_risk=GOOD_RISK).commit


def test_bad_block_gives_offer_only():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1")
    fill_check(loop, 0, 48, score=1.0, loss=1.0)  # every confident item is wrong
    loop.recalibrate()
    d = loop.decide(1.0, guard_risk=GOOD_RISK)
    assert not d.commit and d.reason == "offer-only"


def test_unknown_truth_is_pessimistic():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    for i in range(48):
        loop.add_check_item(i, 1.0, None, guard_risk=GOOD_RISK)
    assert not math.isfinite(loop.recalibrate().threshold)


def test_gated_check_items_do_not_count_as_commits():
    # wrong items without evidence are refused by the gate, so they do not make the block infeasible
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    fill_check(loop, 0, 48, score=0.9, loss=0.0)
    fill_check(loop, 48, 20, score=0.95, loss=1.0, risk=NO_EVIDENCE)
    st = loop.recalibrate()
    assert math.isfinite(st.threshold) and loop.block_wrong_among_commits == 0.0
    # the same wrong items without a guard risk keep their score (conservative): now infeasible
    loop2 = GuardedUpdateLoop(lam_init=0.0)
    loop2.new_version("v1")
    fill_check(loop2, 0, 48, score=0.9, loss=0.0)
    fill_check(loop2, 48, 20, score=0.95, loss=1.0, risk=None)
    assert loop2.recalibrate().threshold > 0.95


# per-update null refusal


def test_pilot_failure_lm_only_sentence_from_uniform_input_is_refused():
    """P15-01 S5: uniform input -> LM-only sentence with p_top1 ~0.2 > day threshold (0.15-0.25)."""
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("S8")
    loop.new_version("S8-u1", trained_on=range(48))
    for i in range(48, 96):  # block: right items at 0.15 - 0.2, wrong items at 0.10 -> threshold near 0.15
        loop.add_check_item(i, 0.15 + 0.001 * (i - 48), 0.0, text="real words", guard_risk=0.4)
    for i in range(96, 116):
        loop.add_check_item(i, 0.10, 1.0, text="wrong words", guard_risk=0.4)
    loop.recalibrate()
    assert 0.10 < loop.lambda_session <= 0.2
    lm_only = [(0.2, "i do not know", NO_EVIDENCE)] * 20  # what the word route says on uniform input
    shuffled = [(0.05, "x y", 0.6)] * 20
    # with the evidence gate the LM-only sentence never commits: the update is accepted, null commits 0
    res = loop.check_null_controls(uniform=lm_only, shuffled=shuffled)
    assert [c.n_commit for c in res] == [0, 0]
    assert loop.finish_update().accepted
    assert not loop.decide(0.2, text="i do not know", guard_risk=NO_EVIDENCE).commit


def test_update_that_commits_on_uniform_input_is_rejected():
    # the same failure, seen by the null refusal: a version whose uniform outputs pass the gate
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("S8")
    loop.new_version("S8-u1", trained_on=range(48))
    fill_check(loop, 48, 48, score=0.9, loss=0.0)
    rec = validate(loop, uniform=[(0.95, "i do not know", 0.3)] * 20)
    assert not rec.accepted and "null controls failed" in rec.reasons[0] and "uniform 20/20 > 1" in rec.reasons[0]
    assert rec.controls[0].allowed == 1  # floor(0.05 * 20)
    assert rec.config_id is None and loop.config_id is None
    d = loop.decide(0.99, text="a b", guard_risk=GOOD_RISK)
    assert not d.commit and d.reason == "rejected"


def test_frame_shuffled_failure_is_rejected_and_rate_is_floor_alpha_n():
    loop = GuardedUpdateLoop(lam_init=0.0, null_max_commit_rate=0.1)
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    loop.recalibrate()
    sh = [(0.95, "x y", 0.3)] * 2 + [(-math.inf, "x", 0.3)] * 18  # 2 commits of 20: floor(0.1 * 20) = 2 -> pass
    assert all(c.passed for c in loop.check_null_controls(uniform=quiet_nulls(), shuffled=sh))
    sh = [(0.95, "x y", 0.3)] * 3 + [(-math.inf, "x", 0.3)] * 17
    assert not loop.check_null_controls(uniform=quiet_nulls(), shuffled=sh)[1].passed
    assert not loop.finish_update().accepted


# champion / challenger and config_id


def test_config_id_changes_on_every_accepted_update_and_audit_records():
    loop = GuardedUpdateLoop(lam_init=0.0)
    ids = []
    for day in range(3):
        loop.start_session(day)
        loop.new_version(f"v{day}", trained_on=[(day, -1)])
        for i in range(48):
            loop.add_check_item((day, i), 0.9, 0.0, text="a b", guard_risk=GOOD_RISK,
                                champion=None if day == 0 else (0.9, 0.0, GOOD_RISK, "a b"))
        rec = validate(loop)
        assert rec.accepted and rec.parent_config_id == (ids[-1] if ids else None)
        ids.append(loop.config_id)
    assert len(set(ids)) == 3 and all(i.startswith("gul-") for i in ids)
    aud = loop.audit_records()
    assert [a["accepted"] for a in aud] == [True, True, True] and aud[2]["champion_before"] == "v1"
    assert aud[1]["challenger_test"]["refused"] is False and aud[0]["controls"][0]["name"] == "uniform"

    json.dumps(aud)  # JSON-ready
    rep = loop.report()
    assert rep["n_accepted"] == 3 and rep["config_id"] == ids[-1]


def test_worse_challenger_is_refused_and_champion_comes_back():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    assert validate(loop).accepted
    cid = loop.config_id
    loop.start_session("d2")
    loop.new_version("v2", trained_on=range(48))
    for i in range(100, 160):  # challenger wrong on 20 items where the champion is right
        bad = i < 120
        loop.add_check_item(i, 0.1 if bad else 0.9, 1.0 if bad else 0.0, text="a b", guard_risk=GOOD_RISK,
                            champion=(0.9, 0.0, GOOD_RISK, "a b"))
    rec = validate(loop)
    assert not rec.accepted and "worse than champion" in rec.reasons[0]
    assert rec.challenger_test is not None and rec.challenger_test.worse_only == 20 and rec.challenger_test.refused
    assert rec.active_version == "v1" and loop.version == "v1" and loop.config_id == cid
    # the champion is calibrated on the same block but must pass its own null controls first
    assert loop.calibrated and not loop.decide(0.95, text="a b", guard_risk=GOOD_RISK).commit
    loop.check_null_controls(uniform=quiet_nulls(), shuffled=quiet_nulls())
    rec2 = loop.finish_update()
    assert rec2.accepted and rec2.version == "v1" and loop.config_id != cid
    assert loop.decide(0.95, text="a b", guard_risk=GOOD_RISK).commit


def test_rejected_challenger_without_champion_outputs_gives_offer_only_session():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    validate(loop)
    loop.start_session("d2")
    loop.new_version("v2")
    fill_check(loop, 100, 48)
    rec = validate(loop, uniform=[(0.95, "words", 0.3)] * 20)
    assert not rec.accepted and loop.version == "v2"
    assert loop.decide(0.99, text="a b", guard_risk=GOOD_RISK).reason == "rejected"


# precision-type check (P5-02 link)


def test_block_precision_is_reported_and_optionally_gated():
    def make(**kw):
        loop = GuardedUpdateLoop(lam_init=0.0, **kw)
        loop.new_version("v1")
        fill_check(loop, 0, 900, score=0.1, loss=1.0)  # many low-score wrong items: below the threshold
        fill_check(loop, 900, 20, score=0.95, loss=1.0)  # rare confident commits, all wrong
        return loop

    loop = make()
    rec = validate(loop)
    # the all-items bound is met (20 / 920 < alpha), but every block commit is wrong: the vacuity case
    assert rec.accepted and loop.n_block_commits >= 20 and loop.block_wrong_among_commits == pytest.approx(
        20 / loop.n_block_commits)
    assert loop.history[-1]["block_wrong_among_commits"] == loop.block_wrong_among_commits
    loop = make(max_wrong_among_commits=0.5)
    rec = validate(loop)
    assert not rec.accepted and "wrong among commits" in rec.reasons[0]


# unsafe (old) behaviour and long-run properties


def test_unsafe_flag_gives_the_old_flow():
    loop = GuardedUpdateLoop(lam_init=0.0, commit_gate=None, unsafe=True)
    loop.new_version("v1")
    for i in range(48):
        loop.add_check_item(i, 0.9, 0.0)
    loop.recalibrate()
    assert loop.decide(0.95).commit  # no guard risk, no null controls, no finish_update
    assert loop.report()["unsafe"] is True


def test_alarm_switches_to_offer_only():
    loop = GuardedUpdateLoop(lam_init=0.0, eta=1e-6)  # tiny eta: ACI barely reacts, so the monitor must
    loop.start_session("d1")
    loop.new_version("v1")
    fill_check(loop, 0, 48, score=0.9, loss=0.0)
    validate(loop)
    for _ in range(40):
        d = loop.decide(0.95, text="a b", guard_risk=GOOD_RISK)
        if not d.commit:
            break
        loop.observe(d, 1.0)  # every commit is corrected as wrong
    assert loop.monitor.alarmed and loop.n_alarms == 1
    assert loop.decide(0.99, guard_risk=GOOD_RISK).reason == "alarm"


def test_aci_certificate_holds_across_updates():
    r = rng(3)
    loop = GuardedUpdateLoop(lam_init=0.5, eta=0.05)
    obs = []
    for day in range(6):
        loop.start_session(day)
        loop.new_version(f"v{day}", trained_on=[(day, -1)])
        for i in range(48):
            loop.add_check_item((day, i), float(r.random()), 0.0, text="a b", guard_risk=GOOD_RISK)
        validate(loop)
        for _ in range(200):
            s = float(r.random())
            d = loop.decide(s, text="a b", guard_risk=float(r.random()) * 1.2)
            wrong = float(r.random() < 0.3 * (1 - s) + 0.1 * day / 6)  # drifts with the day
            loss = loop.observe(d, wrong if d.commit else None)
            if loss is not None:
                obs.append(loss)
    rep = loop.report()["aci"]
    assert rep["n_observed"] == len(obs)
    assert np.mean(obs) <= rep["certificate"] + 1e-12
    assert loop.report()["n_recalibrations"] == 6
