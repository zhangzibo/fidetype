"""Hand cases for the simulated user and effective WPM."""

import math

import pytest

from fidetype.eval.ewpm import SentenceRecord, effective_wpm, summarize, wolpaw_itr_bits
from fidetype.interact.simulated_user import SimulatedUser, UserConfig
from fidetype.trust.policy import Action, Decision

TRUTH = "the cat sat down"  # 16 chars, 4 words
CFG = UserConfig(p_detect_error=1.0)
U = SimulatedUser(CFG)
CHAR_S = 60.0 / 152.0


def test_typing_and_repeat_time():
    assert U.typing_time(TRUTH) == pytest.approx(16 * CHAR_S)
    assert U.repeat_cost(TRUTH) == pytest.approx(1.0 + 16 * CHAR_S)


def test_commit_correct():
    o = U.respond(Decision(Action.COMMIT, (TRUTH,)), TRUTH)
    assert o.communicated and not o.wrong_commit
    assert o.time_s == pytest.approx(0.5 + 0.3 * 4)  # read one sentence


def test_commit_wrong_is_corrected():
    o = U.respond(Decision(Action.COMMIT, ("the cat sad dawn",)), TRUTH)  # 2 edits
    assert o.communicated and o.wrong_commit and o.corrected and not o.silent_error
    assert o.time_s == pytest.approx(0.5 + 1.2 + 2.0 + 2 * 2 * CHAR_S)


def test_commit_wrong_silent_when_not_detected():
    u = SimulatedUser(UserConfig(p_detect_error=0.0))
    o = u.respond(Decision(Action.COMMIT, ("the cat sad",)), TRUTH)
    assert not o.communicated and o.silent_error and o.final_text == "the cat sad"


def test_offer_with_target():
    shown = ("the cat sad down", TRUTH, "the bat sat down")
    o = U.respond(Decision(Action.OFFER, shown), TRUTH)
    read = 3 * (0.5 + 0.3 * 4)
    assert o.communicated
    assert o.time_s == pytest.approx(read + 1.0 + 0.5 * math.log2(4))


def test_offer_without_target_select_and_correct_or_reject():
    shown = ("the cat sat dawn",)  # 1 edit: cheaper than a repeat
    o = U.respond(Decision(Action.OFFER, shown), TRUTH)
    assert o.communicated and o.corrected
    assert o.time_s == pytest.approx((0.5 + 1.2) + 1.0 + 0.5 + 2.0 + 2 * CHAR_S)
    far = ("xxxxxxxxxxxxxxxx",)  # 16 edits: a repeat is cheaper
    o = U.respond(Decision(Action.OFFER, far), TRUTH)
    assert o.needs_repeat and not o.communicated
    o = U.respond(Decision(Action.OFFER, far), TRUTH, can_repeat=False)
    assert o.communicated and o.corrected  # last chance: correct anyway
    u = SimulatedUser(UserConfig(select_and_correct=False))
    assert u.respond(Decision(Action.OFFER, shown), TRUTH).needs_repeat


def test_offer_accepts_close_wrong_candidate():
    u = SimulatedUser(UserConfig(p_accept_close=1.0, close_max_cer=0.1))
    o = u.respond(Decision(Action.OFFER, ("the cat sat dawn",)), TRUTH)
    assert not o.communicated and o.silent_error and o.final_text == "the cat sat dawn"


def test_ask_and_abstain():
    o = U.respond(Decision(Action.ASK), TRUTH)
    assert o.needs_repeat and o.time_s == pytest.approx(0.5)
    o = U.respond(Decision(Action.ABSTAIN), TRUTH)
    assert not o.needs_repeat and not o.communicated and o.time_s == pytest.approx(0.5)


def test_ewpm_hand_case():
    recs = [
        SentenceRecord("a b c d", "a b c d", True, 30.0, ["COMMIT"], "a b c d"),
        SentenceRecord("e f g h i j", "e f x h i j", False, 30.0, ["COMMIT"], "e f x h i j", True, True),
        SentenceRecord("k l", None, False, 20.0, ["ASK", "REPEAT", "ABSTAIN"]),
    ]
    assert effective_wpm(recs) == pytest.approx(60 * 4 / 80)
    assert effective_wpm(recs, partial=True) == pytest.approx(60 * (4 + 5) / 80)
    m = summarize(recs)
    assert m["wrong_commit_rate"] == pytest.approx(1 / 3)
    assert m["silent_error_rate"] == pytest.approx(1 / 3)
    assert m["abstain_rate"] == pytest.approx(1 / 3)
    assert m["rate_ask"] == pytest.approx(1 / 4)
    assert m["mean_attempts"] == pytest.approx(4 / 3)
    assert m["committed_cer"] == pytest.approx(1 / (7 + 11))


def test_wolpaw_itr():
    assert wolpaw_itr_bits(2, 1.0) == pytest.approx(1.0)
    assert wolpaw_itr_bits(4, 0.25) == 0.0
    assert 0 < wolpaw_itr_bits(28, 0.7) < math.log2(28)
