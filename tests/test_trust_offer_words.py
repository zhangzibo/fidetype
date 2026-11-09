"""OFFER_WORDS (per-word choices) and the word model of the simulated user."""

import math
from dataclasses import replace

import numpy as np
import pytest

from fidetype.eval.ewpm import SentenceRecord, effective_wpm, summarize
from fidetype.interact.simulated_user import SimulatedUser, UserConfig, slot_targets
from fidetype.trust.policy import (
    DEFAULT_GRID,
    OFFER_WORDS_GRID,
    Action,
    Decision,
    DecisionPolicy,
    PolicyConfig,
    PolicyInputs,
    WordChoice,
    WordSlotInfo,
    fit_thresholds,
    highlight_slots,
)

TRUTH = "the cat sat down"
U = SimulatedUser(UserConfig.aac_gaze())
CHAR = 3.0  # 60 / 20 chars/min
READ4 = 0.5 + 0.3 * 4  # read a 4-word sentence
SCAN3 = 1.0 + 1.0 * math.log2(4)  # Hick-Hyman scan of 3 alternatives
SEL = 1.5
NAV = 3.0


def slots(*items):
    return tuple(WordSlotInfo(w, tuple(a)) for w, a in items)


SLOTS = slots(
    ("the", [("the", 1.0)]),
    ("cat", [("cat", 0.95), ("hat", 0.05)]),
    ("sad", [("sad", 0.5), ("sat", 0.3), ("said", 0.15), ("mad", 0.05)]),
    ("down", [("down", 0.8), ("dawn", 0.2)]),
)


def inputs(p_top1=0.3, set_size=8, risk=0.0, word_slots=SLOTS, texts=None):
    texts = texts or ("the cat sad down",) + tuple(f"x{i}" for i in range(9))
    return PolicyInputs(texts, p_top1, tuple(range(set_size)), False, risk, word_slots)


def ow(shown, choices=()):
    return Decision(Action.OFFER_WORDS, (shown,), "", tuple(choices))


def rng():
    return np.random.default_rng(0)


# --- highlighting and the policy --------------------------------------------


def test_highlight_threshold_and_k():
    ch = highlight_slots(SLOTS, 0.9, 3)
    assert [c.index for c in ch] == [2, 3]
    assert ch[0].alternatives == ("sad", "sat", "said")  # k = 3, best first
    assert ch[0].confidence == pytest.approx(0.5)
    assert [c.index for c in highlight_slots(SLOTS, 0.0, 3)] == []
    assert [c.index for c in highlight_slots(SLOTS, 1.01, 3)] == [0, 1, 2, 3]
    assert highlight_slots(SLOTS, 0.9, 1)[0].alternatives == ("sad",)


def test_slot_confidence_absent_word_is_zero():
    s = WordSlotInfo("foo", (("bar", 0.7), ("baz", 0.3)))
    assert s.confidence == 0.0


def test_policy_offer_words_replaces_ask():
    x = inputs()
    assert DecisionPolicy(PolicyConfig(offer_max_k=3)).decide(x).action == Action.ASK
    pol = DecisionPolicy(PolicyConfig(offer_max_k=3, offer_words=True, word_conf_threshold=0.9))
    d = pol.decide(x)
    assert d.action == Action.OFFER_WORDS
    assert d.shown_candidates == ("the cat sad down",)
    assert [c.index for c in d.word_choices] == [2, 3]


def test_policy_sentence_threshold_and_max_slots():
    x = inputs()
    assert x.word_confidence == pytest.approx((1.0 + 0.95 + 0.5 + 0.8) / 4)
    cfg = PolicyConfig(offer_max_k=3, offer_words=True, word_conf_threshold=0.9)
    assert DecisionPolicy(replace(cfg, offer_words_min_conf=0.9)).decide(x).action == Action.ASK
    assert DecisionPolicy(replace(cfg, offer_words_min_conf=0.8)).decide(x).action == Action.OFFER_WORDS
    assert DecisionPolicy(replace(cfg, offer_words_max_slots=1)).decide(x).action == Action.ASK
    assert DecisionPolicy(replace(cfg, offer_words_max_slots=2)).decide(x).action == Action.OFFER_WORDS
    # Final attempt: OFFER_WORDS comes before the final fallback.
    assert DecisionPolicy(cfg).decide(x, final_attempt=True).action == Action.OFFER_WORDS


def test_policy_rule_order_kept():
    cfg = PolicyConfig(offer_max_k=3, offer_words=True, abstain_risk=0.8)
    assert DecisionPolicy(cfg).decide(inputs(p_top1=0.9)).action == Action.COMMIT
    assert DecisionPolicy(cfg).decide(inputs(set_size=2)).action == Action.OFFER
    assert DecisionPolicy(cfg).decide(inputs(risk=0.9)).action == Action.ABSTAIN
    # No slots (or slots that do not match the top-1): no OFFER_WORDS.
    assert DecisionPolicy(cfg).decide(inputs(word_slots=())).action == Action.ASK
    assert DecisionPolicy(cfg).decide(inputs(word_slots=SLOTS[:2])).action == Action.ASK


def test_default_policy_ignores_word_slots():
    """Backward compatibility: old configs never read the word slots."""
    r = np.random.default_rng(3)
    for _ in range(300):
        cfg = PolicyConfig(
            commit_p=float(r.choice(DEFAULT_GRID["commit_p"])),
            commit_max_risk=float(r.choice(DEFAULT_GRID["commit_max_risk"])),
            offer_max_k=int(r.choice(DEFAULT_GRID["offer_max_k"])),
            abstain_risk=float(r.choice(DEFAULT_GRID["abstain_risk"])),
            final_fallback=str(r.choice(DEFAULT_GRID["final_fallback"])),
        )
        x = inputs(p_top1=float(r.random()), set_size=int(r.integers(0, 10)), risk=float(r.random()))
        fa = bool(r.random() < 0.5)
        a = DecisionPolicy(cfg).decide(x, fa)
        b = DecisionPolicy(cfg).decide(replace(x, word_slots=()), fa)
        assert a == b and a.action != Action.OFFER_WORDS and a.word_choices == ()


def test_fit_thresholds_word_grid():
    seen = []

    def ev(c):
        seen.append(c)
        # Pretend OFFER_WORDS with threshold 0.9 is best.
        bonus = 5.0 if (c.offer_words and c.word_conf_threshold == 0.9) else 0.0
        return {"ewpm": 10.0 + bonus - c.commit_p, "wrong_commit_rate": 0.0, "silent_error_rate": 0.0}

    small = {"commit_p": (0.5, 0.8)}
    old = fit_thresholds(ev, small)
    assert old.n_evaluated == 2 and not old.config.offer_words
    res = fit_thresholds(ev, small, word_grid=OFFER_WORDS_GRID)
    n_w = len(OFFER_WORDS_GRID["word_conf_threshold"]) * len(OFFER_WORDS_GRID["offer_words_min_conf"])
    assert res.n_evaluated == 2 * n_w
    assert res.config.offer_words and res.config.word_conf_threshold == 0.9
    # The silent-error limit.
    res2 = fit_thresholds(lambda c: {"ewpm": 1.0, "wrong_commit_rate": 0.0, "silent_error_rate": 0.5},
                          small, max_silent_error=0.1)
    assert not res2.feasible


# --- the word model of the user ------------------------------------------------


def test_slot_targets():
    assert slot_targets("the cat sad down", TRUTH) == ["the", "cat", "sat", "down"]
    assert slot_targets("the big cat sat down", TRUTH) == ["the", "", "cat", "sat", "down"]
    assert slot_targets("the sat down", TRUTH) == ["the cat", "sat", "down"]
    assert slot_targets("", TRUTH) == []


def test_offer_words_true_word_in_alternatives():
    d = ow("the cat sad down", [WordChoice(2, "sad", ("sad", "sat", "said"), 0.5)])
    o = U.respond(d, TRUTH, rng=rng())
    assert o.communicated and o.final_text == TRUTH and not o.silent_error and not o.wrong_commit
    assert o.time_s == pytest.approx(READ4 + SCAN3 + SEL + SEL)  # read, scan, select, confirm
    assert o.keystrokes == 2
    assert (o.words_system, o.words_selected, o.words_typed) == (3, 1, 0)


def test_offer_words_true_word_not_in_alternatives():
    d = ow("the cat sad down", [WordChoice(2, "sad", ("sad", "said", "mad"), 0.5)])
    o = U.respond(d, TRUTH, rng=rng())
    assert o.communicated and o.final_text == TRUTH
    assert o.time_s == pytest.approx(READ4 + SCAN3 + SEL + 3 * CHAR + SEL)
    assert o.keystrokes == 1 + 3 + 1
    assert (o.words_system, o.words_selected, o.words_typed) == (3, 0, 1)


def test_offer_words_flagged_slot_already_right_costs_a_scan():
    d = ow(TRUTH, [WordChoice(3, "down", ("down", "dawn"), 0.8)])
    o = U.respond(d, TRUTH, rng=rng())
    assert o.communicated
    assert o.time_s == pytest.approx(READ4 + (1.0 + math.log2(3)) + SEL)
    assert o.keystrokes == 1 and o.words_system == 4


def test_unflagged_error_noticed():
    u = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=0.0))
    o = u.respond(ow("the cat sad down"), TRUTH, rng=rng())
    assert o.communicated and o.wrong_commit  # the system asserted a wrong word
    assert o.time_s == pytest.approx(READ4 + NAV + 3 * CHAR + SEL)
    assert o.keystrokes == 2 + 3 + 1
    assert o.words_typed == 1 and o.n_missed == 0


def test_unflagged_error_missed_is_silent():
    u = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=1.0))
    o = u.respond(ow("the cat sad down"), TRUTH, rng=rng())
    assert not o.communicated and o.silent_error and o.wrong_commit
    assert o.final_text == "the cat sad down" and o.n_missed == 1
    assert o.time_s == pytest.approx(READ4 + SEL)
    assert o.words_system == 0  # no credit: the sentence is wrong


def test_unflagged_extra_word_is_deleted():
    u = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=0.0))
    o = u.respond(ow("the big cat sat down"), TRUTH, rng=rng())
    assert o.communicated and o.final_text == TRUTH
    assert o.time_s == pytest.approx((0.5 + 0.3 * 5) + NAV + SEL)


def test_commit_word_model():
    u = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=0.0))
    o = u.respond(Decision(Action.COMMIT, ("the cat sad down",)), TRUTH, rng=rng())
    assert o.communicated and o.wrong_commit and o.corrected
    assert o.time_s == pytest.approx(READ4 + NAV + 3 * CHAR)  # no confirm for COMMIT
    o = u.respond(Decision(Action.COMMIT, (TRUTH,)), TRUTH, rng=rng())
    assert o.communicated and not o.wrong_commit and o.time_s == pytest.approx(READ4) and o.keystrokes == 0
    m = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=1.0))
    o = m.respond(Decision(Action.COMMIT, ("the cat sad down",)), TRUTH, rng=rng())
    assert o.silent_error and not o.communicated and o.time_s == pytest.approx(READ4)


def test_full_retype_when_cheaper():
    u = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=0.0))
    retype = 1.5 + len(TRUTH) * CHAR
    o = u.respond(Decision(Action.COMMIT, ("a b c d",)), TRUTH, rng=rng())
    # Word fixes: 4 x NAV + 13 chars = 51 s > retype 49.5 s.
    assert o.communicated and o.time_s == pytest.approx(READ4 + retype)
    assert o.keystrokes == 1 + len(TRUTH) and o.words_typed == 4
    u2 = SimulatedUser(UserConfig.aac_gaze(p_miss_unflagged=0.0, allow_full_retype=False))
    o2 = u2.respond(Decision(Action.COMMIT, ("a b c d",)), TRUTH, rng=rng())
    assert o2.time_s == pytest.approx(READ4 + 4 * NAV + 13 * CHAR)


def test_abstain_fallback_typing():
    o = U.respond(Decision(Action.ABSTAIN), TRUTH, can_repeat=False, rng=rng())
    assert o.communicated and o.time_s == pytest.approx(0.5 + 1.5 + len(TRUTH) * CHAR)
    old = SimulatedUser().respond(Decision(Action.ABSTAIN), TRUTH, can_repeat=False, rng=rng())
    assert not old.communicated and old.time_s == pytest.approx(0.5)


def test_offer_word_model_select_and_fix():
    u = SimulatedUser(UserConfig.aac_gaze())
    shown = ("the cat sad down", "the hat sat dawn")
    o = u.respond(Decision(Action.OFFER, shown), TRUTH, can_repeat=False, rng=rng())
    read = 2 * READ4
    assert o.communicated
    assert o.time_s == pytest.approx(read + 1.0 + 0.5 * math.log2(3) + NAV + 3 * CHAR)
    assert o.words_selected == 3 and o.words_typed == 1


def test_default_user_unchanged_for_offer_words_free_actions():
    """UserConfig() keeps the sentence model (values from test_trust_user_ewpm)."""
    u = SimulatedUser()
    o = u.respond(Decision(Action.COMMIT, ("the cat sad down",)), TRUTH, rng=np.random.default_rng(0))
    char_s = 60 / 152
    if o.corrected:
        assert o.time_s == pytest.approx(READ4 + 2.0 + 2 * 1 * char_s)


# --- eWPM and keystrokes saved -------------------------------------------------


def test_ewpm_and_ksr_hand_case():
    recs = [
        SentenceRecord(TRUTH, TRUTH, True, 20.0, ["OFFER_WORDS"], wrong_commit=False,
                       words_system=3, words_selected=1, keystrokes=2, system_text="the cat sad down"),
        SentenceRecord(TRUTH, "the cat sad down", False, 10.0, ["OFFER_WORDS"], wrong_commit=True,
                       silent_error=True, keystrokes=1, system_text="the cat sad down", n_missed=1),
        SentenceRecord("hello", "hello", True, 30.0, ["ABSTAIN"], words_typed=1, keystrokes=6, system_text=None),
    ]
    m = summarize(recs)
    assert m["ewpm"] == pytest.approx(60 * (4 + 1) / 60)
    assert effective_wpm(recs) == pytest.approx(5.0)
    assert m["silent_error_rate"] == pytest.approx(1 / 3)
    assert m["wrong_commit_rate"] == pytest.approx(1 / 3)
    assert m["rate_offer_words"] == pytest.approx(2 / 3)
    assert m["system_word_accuracy"] == pytest.approx((3 + 3 + 0) / 9)
    n_chars = 16 + 16 + 5
    assert m["keystrokes_saved"] == pytest.approx(1 - 9 / n_chars)
    assert m["share_words_system"] == pytest.approx(3 / 9)
    assert m["share_words_selected"] == pytest.approx(1 / 9)
    assert m["share_words_typed"] == pytest.approx(1 / 9)


def test_ksr_full_typing_is_zero_or_less():
    r = SentenceRecord(TRUTH, TRUTH, True, 50.0, ["ABSTAIN"], words_typed=4, keystrokes=len(TRUTH))
    assert summarize([r])["keystrokes_saved"] == pytest.approx(0.0)
    r.keystrokes += 1  # a "clear" action
    assert summarize([r])["keystrokes_saved"] < 0


# --- harness -------------------------------------------------------------------


@pytest.fixture(scope="module")
def setup():
    from fidetype.eval.harness import Item
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
    from fidetype.trust.testing import RefCharLM, ReferenceDecoder

    sents = sentences(600, seed=4)
    dec = ReferenceDecoder(RefCharLM(5).fit(sents[150:]), beam=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("worst", confidence_temperature=1.0), seed=2)
    items = [Item(sim.simulate(s, seed=100 * i).stream, s) for i, s in enumerate(sents[40:100])]
    return dec, items[:20], items[20:40], items[40:]


GRID = {"commit_p": (0.8, 1.01), "commit_max_risk": (1.0,), "offer_max_k": (0, 3),
        "abstain_risk": (1.01,), "final_fallback": ("offer", "abstain")}


def test_harness_offer_words_runs(setup):
    from fidetype.eval.harness import HarnessConfig, TrustPipeline

    dec, cal, val, test = setup
    cache: dict = {}
    cfg = HarnessConfig(grid=GRID, offer_words=True, user_config=UserConfig.aac_gaze(),
                        word_grid={"word_conf_threshold": (0.9, 1.01), "offer_words_min_conf": (0.0,)})
    pipe = TrustPipeline(dec, cfg, cache).fit(cal, val)
    an = pipe.analyze(pipe.decode(test[0], 0))
    assert len(an.inputs.word_slots) == len(an.inputs.texts[0].split())
    m = pipe.evaluate(test)
    assert pipe.fit_report["policy_config"]["offer_words"]
    for k in ("ewpm", "keystrokes_saved", "system_word_accuracy", "rate_offer_words", "silent_error_rate"):
        assert k in m and not math.isnan(m[k]), k
    total = m["share_words_system"] + m["share_words_selected"] + m["share_words_typed"]
    comm_words = sum(r.n_words for r in m["records"] if r.communicated) / sum(r.n_words for r in m["records"])
    assert total == pytest.approx(comm_words)


def test_harness_default_has_no_word_slots(setup):
    from fidetype.eval.harness import HarnessConfig, TrustPipeline

    dec, cal, val, test = setup
    pipe = TrustPipeline(dec, HarnessConfig(grid=GRID)).fit(cal, val)
    assert pipe.analyze(pipe.decode(test[0], 0)).inputs.word_slots == ()
    assert not pipe.fit_report["policy_config"]["offer_words"]


def test_harness_gated_offer_words_equals_old_policy(setup):
    """An OFFER_WORDS policy that never fires gives the old records exactly."""
    from fidetype.eval.harness import HarnessConfig, TrustPipeline

    dec, cal, val, test = setup
    pc = PolicyConfig(commit_p=0.9, offer_max_k=2)
    old = TrustPipeline(dec, HarnessConfig(policy_config=pc, fit_policy=False)).fit(cal)
    new = TrustPipeline(dec, HarnessConfig(policy_config=replace(pc, offer_words=True, offer_words_min_conf=2.0),
                                           fit_policy=False)).fit(cal)
    ra, rb = old.evaluate(test)["records"], new.evaluate(test)["records"]
    assert [(r.final_text, r.time_s, r.actions, r.wrong_commit) for r in ra] == \
        [(r.final_text, r.time_s, r.actions, r.wrong_commit) for r in rb]
