"""Tests of the P15-06 hallucination (fluent-wrong) bound: fidetype.trust.halluc_bound and calibrate(grounding=, llm=).

No language model is needed: the LLM is a mock.
"""

from __future__ import annotations

import itertools
import math
import string

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import halluc_bound as H
from fidetype.trust.grounding import ctc_log_likelihood_many, log_softmax_rows

VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]
SEP = VOCAB.index(" ")


def char_label_fn(text: str):
    t = " ".join(text.split())
    if any(c not in VOCAB[1:] for c in t):
        return None
    return [[VOCAB.index(c) for c in t]]


def peaked(text: str, rng: np.random.Generator, noise: float = 0.0, frames_per: int = 3) -> np.ndarray:
    """Log-probs with one spike per character (prob 0.9) and blanks between."""
    rows = []
    for ch in text:
        for k in range(frames_per):
            row = rng.normal(0.0, 1.0, len(VOCAB)) * noise
            if k == 0:
                row[VOCAB.index(ch)] += 7.0
            else:
                row[0] += 7.0
            rows.append(row)
    return log_softmax_rows(np.array(rows))


# --- alignment and statistics ---------------------------------------------------------------


def test_viterbi_path_is_valid_and_below_forward():
    rng = np.random.default_rng(0)
    lp = peaked("ab ba", rng, noise=0.5)
    labels = char_label_fn("ab ba")[0]
    best, path = H.ctc_viterbi_states(lp, labels)
    fwd = ctc_log_likelihood_many(lp, [labels])[0]
    assert best <= fwd + 1e-9
    # the path visits every label state in order, steps by 0, 1 or 2
    steps = np.diff(path)
    assert set(np.unique(steps)) <= {0, 1, 2}
    assert path[-1] >= 2 * len(labels) - 1
    visited = sorted({int(s) for s in path if s % 2 == 1})
    assert visited == [2 * k + 1 for k in range(len(labels))]
    ext = np.zeros(2 * len(labels) + 1, dtype=int)
    ext[1::2] = labels
    assert abs(sum(lp[t, ext[s]] for t, s in enumerate(path)) - best) < 1e-9


def test_viterbi_too_short_is_minus_inf():
    lp = log_softmax_rows(np.zeros((2, len(VOCAB))))
    best, path = H.ctc_viterbi_states(lp, [1, 1, 1])
    assert best == -math.inf and path.size == 0


def test_word_deficit_catches_one_word_swap():
    rng = np.random.default_rng(1)
    truth = "call my wife now please"
    lp = peaked(truth, rng, noise=0.3)
    g = H.CommitGrounding(char_label_fn, word_sep_id=SEP)
    s_true = g.stats(lp, truth)
    s_swap = g.stats(lp, "call my life now please")  # one letter of one word
    assert len(s_true.word_deficits) == 5
    assert s_true.max_word_deficit < 0.5
    assert s_swap.max_word_deficit > 1.0  # one of four labels has a deficit of about 7 nats
    # the swapped word is the worst word; the others stay low
    assert int(np.argmax(s_swap.word_deficits)) == 2
    assert s_swap.sentence_deficit > s_true.sentence_deficit
    # per-word check is stronger than the sentence deficit (diluted over all frames)
    assert s_swap.max_word_deficit > 5 * s_swap.sentence_deficit


def test_oov_and_anchor_fn():
    rng = np.random.default_rng(2)
    lp = peaked("yes", rng)
    g = H.CommitGrounding(char_label_fn, word_sep_id=SEP)
    assert g.stats(lp, "yes!").sentence_deficit == math.inf
    assert g.stats(lp, "yes!").max_word_deficit == math.inf
    ga = H.CommitGrounding(char_label_fn, word_sep_id=SEP, anchor_fn=lambda _lp: "yes")
    assert abs(ga.stats(lp, "yes").sentence_deficit) < 1e-12
    assert ga.stats(lp, "yet").sentence_deficit > 0.1
    # without a separator label the words are aligned one by one
    gn = H.CommitGrounding(lambda t: char_label_fn(t.replace(" ", "")) if t else [[]])
    assert len(gn.stats(peaked("ab", rng), "a b").word_deficits) == 2


def test_gate_violation_and_roundtrip():
    st = H.GroundingStats(0.01, (0.1, 3.0))
    assert H.HallucGate().violation(st) is None and H.HallucGate().is_off
    assert "word deficit" in H.HallucGate(tau_word=1.0).violation(st)
    assert "sentence deficit" in H.HallucGate(tau_commit=0.005).violation(st)
    g = H.HallucGate(0.02, math.inf)
    assert H.HallucGate.from_dict(g.to_dict()) == g


# --- joint LTT ------------------------------------------------------------------------------


def population(n: int, rng: np.random.Generator) -> list[H.ItemStats]:
    """Exchangeable items: confident items are mostly right; wrong items are often fluent and poorly grounded."""
    out = []
    p = rng.uniform(0.0, 1.0, n)
    wrong = rng.random(n) < (1.0 - p) * 0.6
    fluent = rng.random(n) < 0.5
    for i in range(n):
        wd = rng.gamma(2.0, 1.5) if wrong[i] else rng.gamma(2.0, 0.3)
        sd = rng.gamma(2.0, 0.01) if wrong[i] else rng.gamma(2.0, 0.003)
        out.append(H.ItemStats(bool(rng.random() < 0.9), float(p[i]), bool(wrong[i]), bool(fluent[i]),
                               bool(rng.random() < 0.02 and wrong[i]), H.GroundingStats(float(sd), (float(wd),))))
    return out


def true_risks(pop_arrays, c: H.Config) -> tuple[float, float]:
    k = H._counts(pop_arrays, c)
    return k["wc_loss"] / k["n"], k["h_loss"] / k["n"]


def test_joint_ltt_bound_holds_on_exchangeable_data():
    rng = np.random.default_rng(7)
    pop = population(40000, rng)
    pa = H._arrays(pop)
    configs = H.grid([math.inf] + [round(1 - 0.05 * k, 2) for k in range(21)], (0.005, 0.01, 0.02, math.inf),
                     (0.5, 1.0, 2.0, math.inf))
    alpha, alpha_h, delta = 0.1, 0.02, 0.1
    viol, feasible, commits = 0, 0, []
    reps = 150
    for r in range(reps):
        idx = rng.choice(len(pop), size=600, replace=False)
        o, t = [pop[i] for i in idx[:300]], [pop[i] for i in idx[300:]]
        res = H.joint_ltt(o, t, configs, alpha=alpha, alpha_h=alpha_h, delta=delta)
        if res.selected is None:
            continue
        feasible += 1
        r_wc, r_h = true_risks(pa, res.selected)
        commits.append(H._counts(pa, res.selected)["commits"] / len(pop))
        viol += (r_wc > alpha) or (r_h > alpha_h)
    assert feasible > reps * 0.8
    assert np.mean(commits) > 0.05  # the gate keeps useful commits
    # P(violation) <= delta, with a binomial slack of 3 standard deviations
    assert viol / feasible <= delta + 3 * math.sqrt(delta * (1 - delta) / feasible)


def test_joint_ltt_uses_gate_and_respects_min_commit_p():
    rng = np.random.default_rng(3)
    pop = population(4000, rng)
    o, t = pop[:2000], pop[2000:]
    configs = H.grid([math.inf, 0.9, 0.7, 0.5, 0.3, 0.0], (math.inf, 0.01), (math.inf, 1.0))
    res = H.joint_ltt(o, t, configs, alpha=0.2, alpha_h=0.01, delta=0.1)
    assert res.feasible and res.selected.gate.tau_word == 1.0  # the word check is needed for alpha_h = 0.01
    res2 = H.joint_ltt(o, t, configs, alpha=0.2, alpha_h=0.01, delta=0.1, min_commit_p=0.95)
    assert res2.selected is None or res2.selected.commit_p >= 0.95
    with pytest.raises(ValueError):
        H.joint_ltt(o, t, [], alpha=0.1, alpha_h=0.01, delta=0.1)


def test_joint_ltt_infeasible_when_too_few_items():
    rng = np.random.default_rng(4)
    pop = population(60, rng)
    res = H.joint_ltt(pop[:30], pop[30:], H.grid([0.5], (math.inf,), (math.inf,)), alpha=0.05, alpha_h=0.001,
                      delta=0.1)
    assert res.selected is None and res.certified == []
    # an infeasible result serialises to strict JSON (no NaN p-values; a guard sheet uses allow_nan=False)
    import json

    d = res.to_dict()
    assert d["test_pvalues"] == [None, None] and not d["feasible"]
    json.dumps(d, allow_nan=False)


class MockLLM:
    """Log-prob per word: -2 for texts in ``fluent``, -12 else."""

    def __init__(self, fluent):
        self.fluent = set(fluent)
        self.calls = 0

    def score(self, texts):
        self.calls += len(texts)
        return [(-2.0 if t in self.fluent else -12.0) * max(1, len(t.split())) for t in texts]


def test_is_fluent_and_threshold():
    m = MockLLM({"good text"})
    assert H.is_fluent("good text", m, -5.0) and not H.is_fluent("bad text", m, -5.0)
    assert H.is_fluent("anything", None, -5.0)  # no LLM: counts as fluent (upper bound)
    assert H.fluent_threshold_from_texts(["good text", "bad text", "good text"], m) == -2.0


# --- calibrate(grounding=, llm=) end to end ------------------------------------------------

PHRASES = ["yes please", "thank you", "i am thirsty", "call my wife", "turn on the light", "i need help",
           "open the window", "good morning", "how are you", "more water please"]
#: Fluent but wrong phrases that the "LLM" pushes on top (close in spelling to a true phrase).
HAZARD = {"call my wife": "call my life", "i need help": "i need kelp", "good morning": "good mourning"}


def fake_logits(text: str, rng: np.random.Generator) -> np.ndarray:
    noise = rng.uniform(0.0, 1.0)
    rows = []
    for ch in text:
        for k in range(3):
            row = rng.normal(0.0, 1.0, len(VOCAB))
            if k == 0:
                row[VOCAB.index(ch)] += 9.0 - 5.0 * noise
            else:
                row[0] += 7.0
            rows.append(row)
    return np.array(rows)


def make_decode():
    """Lexicon decoder (CTC score of each phrase) + an "LLM" that puts a fluent-wrong phrase on top.

    The hazard fires on ``HAZARD`` phrases for about half of the inputs (by a hash of the frames), with a
    confident score, so the trust gate alone commits it. Frames that fit no phrase give no candidate.
    """
    cands = PHRASES + list(HAZARD.values())
    labels = [char_label_fn(c)[0] for c in cands]

    def decode(lp: np.ndarray):
        ll = ctc_log_likelihood_many(lp, labels)
        if np.max(ll) / lp.shape[0] < -0.6:  # no phrase fits the frames (noise, shuffled frames): no candidate
            return []
        items = sorted(({"text": c, "score": float(s)} for c, s in zip(cands, ll) if c in PHRASES),
                       key=lambda d: -d["score"])[:4]
        top = items[0]["text"]
        if top in HAZARD and (int(abs(lp[0, 0]) * 1e6) % 2 == 0):
            items.insert(0, {"text": HAZARD[top], "score": items[0]["score"] + 50.0})
            items[1]["score"] -= 50.0
        return items

    return decode


def data(n: int, seed: int):
    rng = np.random.default_rng(seed)
    ts = [str(rng.choice(PHRASES)) for _ in range(n)]
    return [fake_logits(t, rng) for t in ts], ts


@pytest.fixture(scope="module")
def guards():
    xs, ts = data(240, 11)
    decode = make_decode()
    kw = dict(alpha=0.2, delta=0.1, vocab=VOCAB, blank="_", decode_fn=decode, null_trials=30,
              decoder_name="test-halluc", seed=0)
    base = ft.calibrate(xs, ts, **kw)
    llm = MockLLM(HAZARD.values())
    g = H.CommitGrounding(char_label_fn, word_sep_id=SEP, name="test-chars")
    hb = ft.calibrate(xs, ts, grounding=g, llm=llm, halluc_alpha=0.05, fluent_threshold=-5.0,
                      halluc_grid={"commit_p": [math.inf] + [round(1 - 0.05 * k, 2) for k in range(21)],
                                   "tau_commit": [0.05, 0.2, math.inf], "tau_word": [1.0, 3.0, math.inf]},
                      **kw)
    return base, hb, g, decode, llm


def test_default_path_unchanged(guards):
    base, _, _, _, _ = guards
    assert base.halluc_gate is None and base.sheet.halluc is None
    assert "halluc" not in base.sheet.to_dict() and "halluc_gate" not in base.to_dict()


def test_fluent_wrong_commit_is_blocked(guards):
    base, hb, _, decode, llm = guards
    assert llm.calls > 0
    assert hb.sheet.halluc is not None and hb.sheet.halluc["feasible"]
    assert hb.halluc_gate is not None
    assert hb.sheet.commit_threshold >= base.sheet.commit_threshold
    rng = np.random.default_rng(99)
    blocked = base_hazard = hb_hazard = hb_right = base_right = 0
    for k in range(400):
        t = str(rng.choice(PHRASES))
        x = fake_logits(t, rng)
        rb, rh = base.decide(x), hb.decide(x)
        if rb.action == "commit" and rb.text in HAZARD.values():
            base_hazard += 1
            blocked += rh.action != "commit"
            if rh.action != "commit":
                assert rh.reason.startswith("commit blocked: text not grounded")
        hb_hazard += rh.action == "commit" and rh.text in HAZARD.values()
        hb_right += rh.action == "commit" and rh.text == t
        base_right += rb.action == "commit" and rb.text == t
    assert base_hazard >= 5            # the trust gate alone commits fluent-wrong text
    assert hb_hazard == 0              # the grounding gate blocks all of them
    assert blocked == base_hazard
    assert hb_right >= 0.5 * base_right  # and keeps most right commits


def test_sheet_text_and_save_load(guards, tmp_path):
    _, hb, g, decode, _ = guards
    txt = str(hb.sheet)
    assert "hallucination bound" in txt and "fluent-wrong rate" in txt
    p = hb.save(tmp_path / "g.json")
    with pytest.raises(ValueError, match="grounding"):
        ft.load(p, decode_fn=decode)
    g2 = ft.load(p, decode_fn=decode, grounding=g)
    assert g2.config_id == hb.config_id and g2.halluc_gate == hb.halluc_gate
    rng = np.random.default_rng(5)
    for t in itertools.islice(itertools.cycle(PHRASES), 20):
        x = fake_logits(t, rng)
        a, b = hb.decide(x), g2.decide(x)
        assert (a.action, a.text) == (b.action, b.text)
    d = hb.sheet.to_dict()
    assert ft.GuaranteeSheet.from_dict(d).halluc == d["halluc"]


def test_controls_of_final_guard_pass(guards):
    _, hb, _, _, _ = guards
    assert all(c.passed for c in hb.sheet.controls)
    assert hb.sheet.halluc["controls_final"]


def test_bad_arguments():
    xs, ts = data(30, 1)
    with pytest.raises(ValueError, match="halluc_alpha"):
        ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=make_decode(), llm=MockLLM([]), halluc_alpha=0.0)
    with pytest.raises(ValueError, match="halluc_grid"):
        ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=make_decode(), llm=MockLLM([]),
                     halluc_grid={"tau": [1.0]})
    nb = [[(t, 0.0)] for t in ts]
    with pytest.raises(ValueError, match="grounding is for logits"):
        ft.calibrate(nb, ts, null_inputs=nb, grounding=H.CommitGrounding(char_label_fn))
