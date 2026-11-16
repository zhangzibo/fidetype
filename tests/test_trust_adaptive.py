"""Tests for fidetype.trust.adaptive (F1 guarded update loop, simulated feedback user)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fidetype.trust import FeedbackUser, GuardedUpdateLoop
from fidetype.trust.adaptive import char_error_rate
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


def fill_check(loop: GuardedUpdateLoop, start: int, n: int, score: float = 0.9, loss: float = 0.0) -> None:
    for i in range(start, start + n):
        loop.add_check_item(i, score, loss)


def test_no_commit_before_recalibration():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1", trained_on=range(10))
    d = loop.decide(1.0)
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


def test_clean_block_allows_commits_and_new_version_blocks_them():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1", trained_on=[])
    fill_check(loop, 0, 48, score=0.9, loss=0.0)
    st = loop.recalibrate()
    assert math.isfinite(st.threshold) and st.threshold <= 0.9
    d = loop.decide(0.95)
    assert d.commit and d.version == "v1"
    loop.observe(d, 0.0)
    loop.new_version("v2", trained_on=range(48))
    assert not loop.decide(0.99).commit  # the update invalidates the calibration
    loop.start_session("d2")
    assert not loop.calibrated


def test_bad_block_gives_offer_only():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session("d1")
    loop.new_version("v1")
    fill_check(loop, 0, 48, score=1.0, loss=1.0)  # every confident item is wrong
    loop.recalibrate()
    d = loop.decide(1.0)
    assert not d.commit and d.reason == "offer-only"


def test_unknown_truth_is_pessimistic():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    for i in range(48):
        loop.add_check_item(i, 1.0, None)
    assert not math.isfinite(loop.recalibrate().threshold)


def test_gate_blocks_empty_text():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.new_version("v1")
    fill_check(loop, 0, 48)
    loop.recalibrate()
    d = loop.decide(0.99, text_ok=False)
    assert not d.commit and d.reason == "gate"


def test_alarm_switches_to_offer_only():
    loop = GuardedUpdateLoop(lam_init=0.0, eta=1e-6)  # tiny eta: ACI barely reacts, so the monitor must
    loop.start_session("d1")
    loop.new_version("v1")
    fill_check(loop, 0, 48, score=0.9, loss=0.0)
    loop.recalibrate()
    for _ in range(40):
        d = loop.decide(0.95)
        if not d.commit:
            break
        loop.observe(d, 1.0)  # every commit is corrected as wrong
    assert loop.monitor.alarmed and loop.n_alarms == 1
    assert loop.decide(0.99).reason == "alarm"


def test_aci_certificate_holds_across_updates():
    r = rng(3)
    loop = GuardedUpdateLoop(lam_init=0.5, eta=0.05)
    obs = []
    for day in range(6):
        loop.start_session(day)
        loop.new_version(f"v{day}", trained_on=[(day, -1)])
        for i in range(48):
            loop.add_check_item((day, i), float(r.random()), 0.0)
        loop.recalibrate()
        for _ in range(200):
            s = float(r.random())
            d = loop.decide(s)
            wrong = float(r.random() < 0.3 * (1 - s) + 0.1 * day / 6)  # drifts with the day
            loss = loop.observe(d, wrong if d.commit else None)
            if loss is not None:
                obs.append(loss)
    rep = loop.report()["aci"]
    assert rep["n_observed"] == len(obs)
    assert np.mean(obs) <= rep["certificate"] + 1e-12
    assert loop.report()["n_recalibrations"] == 6
