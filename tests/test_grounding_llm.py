"""Tests for the grounding check (fidetype.trust.grounding) and the LLM rescoring logic (fidetype.lm.llm).

No language model is needed: the LLM is a mock.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from fidetype.lm.llm import (
    CachedRewriter,
    CachedScorer,
    SentenceRewriter,
    SentenceScorer,
    add_rewrite,
    lattice_words,
    normalize_text,
    rescore,
    rewrite_confidences,
    within_lattice,
)
from fidetype.trust.grounding import (
    GroundingCheck,
    ctc_log_likelihood_many,
    fit_tau,
    lexicon_label_fn,
    log_softmax_rows,
)


def brute_ctc(lp: np.ndarray, labels, blank: int = 0) -> float:
    """CTC likelihood by enumerating every frame path (tiny cases only)."""
    T, V = lp.shape
    tot = -math.inf
    for path in itertools.product(range(V), repeat=T):
        out, prev = [], None
        for p in path:
            if p != prev and p != blank:
                out.append(p)
            prev = p
        if out == list(labels):
            tot = np.logaddexp(tot, sum(lp[t, p] for t, p in enumerate(path)))
    return float(tot)


def test_ctc_forward_matches_brute_force():
    rng = np.random.default_rng(0)
    lp = log_softmax_rows(rng.normal(size=(5, 3)))
    seqs = [[1], [1, 2], [1, 1], [2, 1, 2], [], [1, 2, 1, 2, 1, 2]]
    got = ctc_log_likelihood_many(lp, seqs, blank=0)
    for s, g in zip(seqs, got):
        want = brute_ctc(lp, s)
        if math.isinf(want):
            assert math.isinf(g)
        else:
            assert g == pytest.approx(want, abs=1e-9)


def test_ctc_forward_batch_equals_single():
    rng = np.random.default_rng(1)
    lp = log_softmax_rows(rng.normal(size=(30, 6)))
    seqs = [[1, 2, 3], [4, 4], [5], [1, 2, 3, 4, 5, 1, 2]]
    batch = ctc_log_likelihood_many(lp, seqs)
    single = [ctc_log_likelihood_many(lp, [s])[0] for s in seqs]
    assert np.allclose(batch, single)


PRONS = {"hi": ["ab", "ac"], "yo": ["cb"], "a": ["a"]}
SYM = {"<blank>": 0, " ": 1, "a": 2, "b": 3, "c": 4}


def peaked(seq_syms: str, frames_per: int = 3, V: int = 5, p: float = 0.9) -> np.ndarray:
    rows = []
    for ch in seq_syms:
        r = np.full(V, (1 - p) / (V - 1))
        r[SYM[ch]] = p
        rows += [r] * frames_per
        b = np.full(V, (1 - p) / (V - 1))
        b[0] = p
        rows.append(b)
    return np.log(np.array(rows))


def test_lexicon_label_fn_variants_and_oov():
    fn = lexicon_label_fn(PRONS, SYM)
    assert fn("hi yo") == [[2, 3, 1, 4, 3], [2, 4, 1, 4, 3]]
    assert fn("hi zz") is None
    assert fn("") == [[]]
    assert len(lexicon_label_fn(PRONS, SYM, max_variants=1)("hi hi")) == 1


def test_grounding_prefers_supported_text_and_gates():
    fn = lexicon_label_fn(PRONS, SYM)
    x = peaked("ab cb")  # "hi yo"
    g = GroundingCheck(fn, tau=0.1)
    d = g.deficits(x, ["hi yo", "yo hi", "hi zz"], anchor="hi yo")
    assert d[0] == pytest.approx(0.0)
    assert d[1] > 0.1 and math.isinf(d[2])
    items = [{"text": "yo hi", "score": 5.0}, {"text": "hi yo", "score": 1.0}]
    out, dd = g.apply(items, x, anchor="hi yo")
    # P15-27: the list is re-sorted after demotion, so out[0] is the grounded top-1
    assert out[0]["text"] == "hi yo" and out[0]["grounded"]
    assert out[1]["text"] == "yo hi" and not out[1]["grounded"] and out[1]["score"] < out[0]["score"]
    assert dd[0] > 0.1 and dd[1] == pytest.approx(0.0)  # deficits stay in input order
    # nothing passes -> empty list (the trust layer withholds)
    out2, _ = g.apply([{"text": "yo hi", "score": 1.0}], x, anchor="hi yo")
    assert out2 == []
    out3, _ = g.apply([{"text": "yo hi", "score": 1.0}], x, anchor="hi yo", drop_if_none_pass=False)
    assert [o["text"] for o in out3] == ["yo hi"] and out3[0]["score"] == 1.0


def test_grounding_apply_top1_equals_nbest_top1():
    """P15-27: the first item of apply() is the top-1 of the NBest the guard builds from the same list."""
    from fidetype.trust.dropin import _nbest_from_user

    fn = lexicon_label_fn(PRONS, SYM)
    x = peaked("ab cb")  # "hi yo"
    g = GroundingCheck(fn, tau=0.1)
    rng = np.random.default_rng(3)
    texts = ["yo hi", "hi yo", "hi zz", "yo yo", "hi hi", "a"]
    for _ in range(50):
        sc = rng.normal(size=len(texts)) * 3
        items = sorted(({"text": t, "score": float(s)} for t, s in zip(texts, sc)), key=lambda d: -d["score"])
        out, dd = g.apply(items, x, anchor="hi yo")
        assert out, "the anchor text always passes"
        assert out[0]["grounded"]
        assert all(out[i]["score"] >= out[i + 1]["score"] for i in range(len(out) - 1))
        assert sorted(o["text"] for o in out) == sorted(texts)  # failing candidates stay in the list
        assert _nbest_from_user(out).top.text == out[0]["text"]
        assert list(dd) == list(g.deficits(x, [d["text"] for d in items], anchor="hi yo"))


def test_grounding_cache_key_gives_same_values():
    fn = lexicon_label_fn(PRONS, SYM)
    x = peaked("ab")
    g = GroundingCheck(fn)
    a = g.log_likelihoods(x, ["hi", "yo"], key=b"k")
    b = g.log_likelihoods(x, ["hi", "yo"], key=b"k")
    assert np.array_equal(a, b)


def test_fit_tau_conformal_rank():
    assert fit_tau([0.1, 0.2, 0.3, 0.4], coverage=0.5) == pytest.approx(0.3)
    assert fit_tau([0.1] * 5, coverage=0.95) == math.inf
    assert fit_tau([float("inf")] * 30 + [0.0] * 70, coverage=0.5) == 0.0


class MockLLM:
    """A fake LLM: log p(text) = -1 per word, -10 per word not in a small vocabulary."""

    VOCAB = {"i", "want", "to", "go", "home", "now"}

    def __init__(self):
        self.n_score = 0
        self.n_rewrite = 0

    def score(self, texts):
        self.n_score += len(texts)
        return [sum(-1.0 if w in self.VOCAB else -10.0 for w in t.split()) for t in texts]

    def rewrite(self, nbest_texts, constrained=True):
        self.n_rewrite += 1
        return "i want to go home now" if not constrained else nbest_texts[-1]


def test_mock_satisfies_protocols():
    m = MockLLM()
    assert isinstance(m, SentenceScorer) and isinstance(m, SentenceRewriter)


def test_rescore_reorders_and_weight_zero_keeps():
    items = [{"text": "eye want two go", "score": 0.0}, {"text": "i want to go", "score": -1.0}]
    m = MockLLM()
    assert [d["text"] for d in rescore(items, m, 0.0)] == ["eye want two go", "i want to go"]
    assert m.n_score == 0
    out = rescore(items, m, 1.0)
    assert out[0]["text"] == "i want to go" and "logp_llm_large" in out[0]


def test_cached_scorer_and_rewriter():
    m = MockLLM()
    cs = CachedScorer(m)
    cs.score(["a b", "a b", "c"])
    cs.score(["a b"])
    assert m.n_score == 2
    cr = CachedRewriter(m)
    cr.rewrite(["x", "y"])
    cr.rewrite(["x", "y"])
    cr.rewrite(["x", "y"], constrained=False)
    assert m.n_rewrite == 2


def test_lattice_and_add_rewrite():
    items = [{"text": "eye want two go", "score": 0.0, "char_confidences": [0.9] * 15},
             {"text": "i want to go", "score": -1.0, "char_confidences": [0.5] * 12}]
    assert lattice_words([d["text"] for d in items]) == {"eye", "want", "two", "go", "i", "to"}
    assert within_lattice("i want two go", [d["text"] for d in items])
    assert not within_lattice("i want to go home", [d["text"] for d in items])
    assert not within_lattice("", [d["text"] for d in items])
    out = add_rewrite(items, "i want two go")
    assert out[0]["text"] == "i want two go" and out[0]["rewrite"]
    assert len(out[0]["char_confidences"]) == len("i want two go")
    out2 = add_rewrite(items, "i want to go")
    assert out2[0]["text"] == "i want to go" and len(out2) == 2
    assert add_rewrite(items, "") == items


def test_rewrite_confidences_use_positions_then_any():
    items = [{"text": "a b", "char_confidences": [0.9, 0.9, 0.2]}, {"text": "b a", "char_confidences": [0.4, 0.4, 0.8]}]
    c = rewrite_confidences("a b", items)
    assert c == [0.9, 0.2, 0.2]
    c2 = rewrite_confidences("z", items)
    assert c2 == [0.0]


def test_normalize_text():
    assert normalize_text("I Want, to GO!  now.") == "i want to go now"
    assert normalize_text("that's it") == "that's it"
