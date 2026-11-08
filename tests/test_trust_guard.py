"""Tests of fidetype.trust.guard and the n-best protocol."""

from types import SimpleNamespace

import numpy as np
import pytest

from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.guard import (
    HallucinationGuard,
    auroc,
    lexicon_fluency,
    nbest_consistency,
    null_input_audit,
    semantic_entropy,
    shuffle_stream,
    uniform_stream,
)
from fidetype.trust.testing import RefCharLM, ReferenceDecoder, synthetic_nbest
from fidetype.trust.types import Candidate, NBest, from_lm_hypotheses


def test_auroc_hand_cases():
    assert auroc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert auroc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]) == 0.0
    assert auroc([0.5, 0.5, 0.5, 0.5], [0, 1, 0, 1]) == 0.5
    assert np.isnan(auroc([0.1, 0.2], [1, 1]))


def test_consistency_and_entropy():
    texts = ["a b c", "a b c d", "x y z"]
    p = np.array([0.5, 0.3, 0.2])
    assert nbest_consistency(texts[:1], p[:1]) == 1.0
    c = nbest_consistency(texts, p)
    assert c == pytest.approx(0.5 * 1 + 0.3 * 0.75 + 0.2 * 0.0)
    assert semantic_entropy(["a b", "a b"], np.array([0.5, 0.5])) == 0.0
    assert semantic_entropy(["a b", "a c"], np.array([0.5, 0.5])) == pytest.approx(np.log(2))
    assert semantic_entropy(["a b", "a c"], np.array([0.5, 0.5]), max_word_edits=1) == 0.0


def test_guard_detects_lm_pushed_text():
    """Half of the lists have a fluent wrong top-1 that the LM pushed."""
    rng = np.random.default_rng(0)
    truths = sentences(300, seed=1)
    lex = sorted({w for s in truths for w in s.split()})
    guard = HallucinationGuard()
    risks, wrong = [], []
    for t in truths:
        push = bool(rng.random() < 0.5)
        nb = synthetic_nbest(t, rng, lm_push=push, lexicon=lex)
        risks.append(guard.score(nb).risk)
        wrong.append(nb.top.text != t)
    assert sum(wrong) > 100
    assert auroc(risks, wrong) > 0.75


def test_guard_scores_empty_and_evidence():
    g = HallucinationGuard()
    assert g.score(NBest([])).risk == 1.0
    cand = Candidate("ab", 0.0, -1.0, -3.0, (0.9, 0.2))
    low, exp_err, gap = g.evidence(cand)
    assert low == 0.5
    assert exp_err == pytest.approx(0.45)
    assert gap == pytest.approx(-1.0)


def test_from_lm_hypotheses_duck_typing():
    hyps = [
        SimpleNamespace(text="hello  world ", score=-1.0, logp_acoustic=-2.0, logp_lm=-3.0,
                        char_confidences=np.full(13, 0.9)),
        {"text": "hello world", "score": -0.5, "logp_acoustic": -1.0, "logp_lm": -2.0,
         "char_confidences": [0.5] * 11},
        SimpleNamespace(text="yellow world", score=-4.0, logp_acoustic=-5.0, logp_lm=-6.0,
                        char_confidences=np.full(12, 0.8),
                        confidence_variants={"frame": np.array([0.1] * 11 + [np.nan])}),
    ]
    nb = from_lm_hypotheses(hyps)
    assert nb.texts == ["hello world", "yellow world"]  # merged, best score kept
    assert nb.top.score == -0.5
    assert len(nb.top.char_confidences) == 11
    # The acoustic ("frame") variant is preferred; NaN becomes 0.
    assert nb.candidates[1].char_confidences[-1] == 0.0
    assert nb.candidates[1].char_confidences[0] == pytest.approx(0.1)
    nb2 = from_lm_hypotheses(hyps, confidence_variant=None)
    assert nb2.candidates[1].char_confidences[0] == pytest.approx(0.8)


def test_nbest_rejects_duplicate_texts():
    with pytest.raises(ValueError):
        NBest([Candidate("a", 0.0), Candidate("a", -1.0)])


def test_null_input_audit_runs():
    sents = sentences(500, seed=3)
    test_s = sents[40:56]  # template sentences, in the LM domain
    lm = RefCharLM(5).fit(sents[100:])
    dec = ReferenceDecoder(lm, beam=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("best"), seed=0)
    streams = [sim.simulate(s, seed=i).stream for i, s in enumerate(test_s)]
    fluent = lexicon_fluency({w for s in sents for w in s.split()})
    rng = np.random.default_rng(0)
    assert shuffle_stream(streams[0], rng).n_frames == streams[0].n_frames
    assert uniform_stream(streams[0], rng, jitter=0.0).log_probs.std() < 1e-5
    guard = HallucinationGuard()
    res = null_input_audit(dec, streams, fluent, accept_fn=lambda nb: guard.score(nb).risk < 0.3, seed=1)
    assert set(res) == {"real", "shuffled", "uniform"}
    assert res["real"]["fluent_rate"] > 0.8
    for cond in res.values():
        assert 0.0 <= cond["fluent_accepted_rate"] <= cond["fluent_rate"]
    # The guard accepts real text much more often than null-input text.
    assert res["real"]["fluent_accepted_rate"] > res["shuffled"]["fluent_accepted_rate"]
    assert res["real"]["fluent_accepted_rate"] > res["uniform"]["fluent_accepted_rate"]
