"""Tests of the character n-gram LM and the CTC prefix beam search.

All tests use numpy only and the built-in corpus. They download nothing.
"""

import math
import time

import numpy as np
import pytest

from fidetype.eval.metrics import cer, ctc_greedy_decode
from fidetype.lm import (
    EOS,
    CharNgramLM,
    align_pairs,
    ctc_forced_align,
    ctc_prefix_beam_search,
    exclude_sentences,
    n_best_to_posteriors,
)
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.streams.vocab import VOCAB, encode

ALL = sentences(1200, seed=0)
TEST = ALL[1100:1150]
TRAIN = exclude_sentences(ALL[:1000], TEST)


@pytest.fixture(scope="module")
def lm():
    return CharNgramLM(order=6).train(TRAIN)


# --- n-gram LM ------------------------------------------------------------


@pytest.mark.parametrize("smoothing", ["mkn", "kn", "mle"])
@pytest.mark.parametrize("order", [1, 3, 6])
def test_probabilities_sum_to_one(smoothing, order):
    model = CharNgramLM(order=order, smoothing=smoothing).train(TRAIN)
    for ctx in ["", "t", "the qu", "my sister works", "zzqx", "a lazy zebra w"]:
        for bos in (True, False):
            p = np.exp(model.logprobs_vocab(ctx, bos=bos))
            assert p.shape == (28,)
            assert abs(p.sum() - 1.0) < 1e-9


def test_logprob_matches_vector(lm):
    v = lm.logprobs_vocab("the qu")
    assert lm.logprob("i", "the qu") == pytest.approx(v[VOCAB.index("i")])
    assert lm.logprob(EOS, "the qu") == pytest.approx(v[0])
    assert lm.logprob("i", "the qu") > lm.logprob("x", "the qu")
    with pytest.raises(ValueError):
        lm.logprob("?", "abc")


def test_score_sentence_is_sum(lm):
    s = "the cat"
    tot = sum(lm.logprob(c, s[:i]) for i, c in enumerate(s)) + lm.logprob(EOS, s)
    assert lm.score_sentence(s) == pytest.approx(tot)
    assert lm.score_sentence(s, eos=False) == pytest.approx(tot - lm.logprob(EOS, s))


def test_kn_beats_unsmoothed_on_heldout():
    # Train on the template sentences; hold out the 40 hand-written ones.
    train, held = ALL[40:1000], ALL[:40]
    assert set(train).isdisjoint(held)
    mkn = CharNgramLM(order=6, smoothing="mkn").train(train).perplexity(held)
    kn = CharNgramLM(order=6, smoothing="kn").train(train).perplexity(held)
    mle = CharNgramLM(order=6, smoothing="mle").train(train).perplexity(held)
    uni = CharNgramLM(order=1, smoothing="mkn").train(train).perplexity(held)
    assert math.isfinite(mkn) and math.isfinite(kn)
    assert mkn < mle and kn < mle
    assert mkn < uni


def test_kn_beats_unsmoothed_on_unseen_words():
    # Held-out text with words that are not in the training text.
    train = ["the cat sat on the mat", "the dog sat on the log", "a cat and a dog"]
    held = ["the rat sat on the hat", "a bird and a fox"]
    mkn = CharNgramLM(order=4).train(train).perplexity(held)
    mle = CharNgramLM(order=4, smoothing="mle").train(train).perplexity(held)
    assert math.isfinite(mkn) and mkn < mle


def test_save_load_roundtrip(lm, tmp_path):
    path = tmp_path / "lm.npz"
    lm.meta["note"] = "test"
    lm.save(path)
    lm2 = CharNgramLM.load(path)
    assert lm2.order == lm.order and lm2.meta["note"] == "test"
    for ctx in ["", "the qu", "xyz"]:
        np.testing.assert_allclose(lm2.logprobs_vocab(ctx), lm.logprobs_vocab(ctx), atol=1e-5)
    with np.load(path, allow_pickle=False):
        pass  # The file loads without pickle.


def test_exclude_sentences():
    corpus = ["Hello World!", "keep me", "hello   world", "", "Another one"]
    out = exclude_sentences(corpus, ["HELLO WORLD"])
    assert out == ["keep me", "Another one"]
    assert set(TRAIN).isdisjoint(TEST)


# --- beam search ----------------------------------------------------------


def _frames(labels, sharp=0.9):
    """Return log-probs (T, 28) with ``sharp`` mass on each frame label."""
    T = len(labels)
    p = np.full((T, 28), (1 - sharp) / 27)
    for t, lab in enumerate(labels):
        p[t, lab] = sharp
    return np.log(p)


def _ids(text):
    return [VOCAB.index(c) for c in text]


def test_beam1_no_lm_equals_greedy():
    rng = np.random.default_rng(0)
    for _ in range(30):
        labels = []
        for c in _ids("the cat sat"):
            labels += [0] * int(rng.integers(1, 3)) + [c] * int(rng.integers(1, 3))
        labels += [0]
        lp = _frames(labels, sharp=float(rng.uniform(0.6, 0.99)))
        h = ctc_prefix_beam_search(lp, lm=None, beam=1, n_best=1)
        greedy = ctc_greedy_decode_arr(lp)
        assert h[0].text == greedy == "the cat sat"


def ctc_greedy_decode_arr(lp):
    best = np.argmax(lp, axis=1)
    out, prev = [], -1
    for b in best:
        if b != prev and b != 0:
            out.append(VOCAB[b])
        prev = b
    return "".join(out)


def test_greedy_equivalence_on_simulator_stream():
    sim = NoisyDecoderSimulator(SimConfig.preset("perfect"), seed=1)
    for s in TEST[:10]:
        r = sim.simulate(s)
        h = ctc_prefix_beam_search(r.stream, beam=1, n_best=1)
        assert h[0].text == ctc_greedy_decode(r.stream)


def test_repeats_need_blank():
    a = VOCAB.index("a")
    assert ctc_prefix_beam_search(_frames([0, a, a, 0]), beam=8)[0].text == "a"
    assert ctc_prefix_beam_search(_frames([0, a, 0, a, 0]), beam=8)[0].text == "aa"
    assert ctc_prefix_beam_search(_frames([a, a, a]), beam=8)[0].text == "a"
    assert ctc_prefix_beam_search(_frames([0, 0, 0]), beam=8)[0].text == ""


def test_prefix_probability_sums_paths():
    # Two frames, uniform over {blank, a}: paths "a-", "-a", "aa" all give "a".
    p = np.full((2, 28), 1e-12)
    p[:, 0] = p[:, 1] = 0.5
    p /= p.sum(axis=1, keepdims=True)
    hyps = ctc_prefix_beam_search(np.log(p), beam=8, n_best=8, prune_logp=-5)
    d = {h.text: math.exp(h.logp_acoustic) for h in hyps}
    assert d["a"] == pytest.approx(0.75, rel=1e-6)
    assert d[""] == pytest.approx(0.25, rel=1e-6)
    assert d["aa"] == pytest.approx(0.0, abs=1e-6) if "aa" in d else True


def test_nbest_sorted_and_posteriors(lm):
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=2)
    r = sim.simulate(TEST[0])
    hyps = ctc_prefix_beam_search(r.stream, lm=lm, lm_weight=1.0, insertion_bonus=0.0, beam=16, n_best=10)
    assert 1 < len(hyps) <= 10
    scores = [h.score for h in hyps]
    assert scores == sorted(scores, reverse=True)
    assert len({h.text for h in hyps}) == len(hyps)
    for t in (0.5, 1.0, 3.0):
        p = n_best_to_posteriors(hyps, temperature=t)
        assert p.sum() == pytest.approx(1.0)
        assert np.all(np.diff(p) <= 1e-12)
    h = hyps[0]
    w = 1.0
    assert h.score == pytest.approx(h.logp_acoustic + w * h.logp_lm)
    assert h.logp_lm == pytest.approx(lm.score_sentence(h.text, normalize=False))
    for key in ("fused", "nbest", "frame"):
        c = h.confidence_variants[key]
        assert c.shape == (len(h.text),)
        assert np.all((c >= 0) & (c <= 1))
    assert len(h.frame_spans) == len(h.text)
    assert all(s <= e for s, e in h.frame_spans)
    assert all(h.frame_spans[i][1] < h.frame_spans[i + 1][0] for i in range(len(h.text) - 1))


def test_insertion_bonus_in_score():
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=4)
    r = sim.simulate(TEST[1])
    h = ctc_prefix_beam_search(r.stream, insertion_bonus=0.5)[0]
    assert h.score == pytest.approx(h.logp_acoustic + 0.5 * len(h.text))


def test_forced_align():
    a, b = VOCAB.index("a"), VOCAB.index("b")
    lp = _frames([0, a, a, 0, b, 0, 0, a, 0])
    assert ctc_forced_align(lp, [a, b, a]) == [(1, 2), (4, 4), (7, 7)]
    assert ctc_forced_align(lp[:2], [a, a, a]) is None  # Too short.


def test_align_pairs():
    pairs = align_pairs("kitten", "sitting")
    a_idx = [i for i, _ in pairs if i is not None]
    b_idx = [j for _, j in pairs if j is not None]
    assert a_idx == list(range(6)) and b_idx == list(range(7))
    cost = sum(1 for i, j in pairs if i is None or j is None or "kitten"[i] != "sitting"[j])
    assert cost == 3


def test_beam_lm_beats_greedy_on_simulator(lm):
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=11)
    g = b = 0.0
    for s in TEST:
        r = sim.simulate(s)
        g += cer(r.text, ctc_greedy_decode(r.stream))
        b += cer(r.text, ctc_prefix_beam_search(r.stream, lm=lm, lm_weight=1.0, beam=16, align=False)[0].text)
    assert b / len(TEST) < g / len(TEST) - 0.05


def test_deterministic(lm):
    sim = NoisyDecoderSimulator(SimConfig.preset("worst"), seed=5)
    r = sim.simulate(TEST[3])
    a = ctc_prefix_beam_search(r.stream, lm=lm, beam=16, n_best=10)
    b = ctc_prefix_beam_search(r.stream, lm=lm, beam=16, n_best=10)
    assert [(h.text, h.score) for h in a] == [(h.text, h.score) for h in b]
    for x, y in zip(a, b):
        np.testing.assert_array_equal(x.char_confidences, y.char_confidences)


def test_speed_40_chars(lm):
    s = "the old man walked slowly up the hill ok"
    assert len(s) == 40
    r = NoisyDecoderSimulator(SimConfig.preset("median"), seed=6).simulate(s)
    ctc_prefix_beam_search(r.stream, lm=lm, beam=16)  # Warm the LM cache.
    lm._cache.clear()
    t0 = time.perf_counter()
    ctc_prefix_beam_search(r.stream, lm=lm, beam=16, align=False)
    assert time.perf_counter() - t0 < 1.0


def test_lm_needs_default_vocab(lm):
    with pytest.raises(ValueError):
        ctc_prefix_beam_search(np.log(np.full((3, 5), 0.2)), lm=lm)
    assert encode("ab") == [1, 2]
