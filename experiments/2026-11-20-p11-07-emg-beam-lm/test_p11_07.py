"""Unit tests of the P11-07 in-beam LM decoder (synthetic inputs and a tiny trained LM; no emg2qwerty data)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

import lmbeam as LB  # noqa: E402
from fidetype.lm.beam import IncrementalPrefixBeam  # noqa: E402
from fidetype.lm.ngram import CharNgramLM  # noqa: E402

KV = ["<blank>", *"abcdefghijklmnopqrstuvwxyz", "_", ".", ",", "'", "⌫", "⏎"]


@pytest.fixture(scope="module")
def lm():
    m = CharNgramLM(order=4, smoothing="mkn")
    m.train(["the cat sat on the mat", "a dog ran far", "hello world", "the dog sat", "cats and dogs"] * 5)
    return m


def rand_lp(T: int, V: int, seed: int, peaky: bool = True) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 2.0, (T, V))
    if peaky:
        x[:, 0] += 3.0
    return x - np.logaddexp.reduce(x, axis=1, keepdims=True)


def indep_lm_score(lm, dec: LB.LMBeam, toks: list[int]) -> float:
    """Independent LM score of a key sequence: intended text with stack semantics, LM over sentences."""
    stack: list[tuple[str, float]] = []  # (normalised char or '|' reset, delta)
    def ctx_of(st):
        s = ""
        for ch, _ in st:
            s = "" if ch == "|" else s + ch
        return s
    for t in toks:
        k = dec.kinds[t]
        if k == LB.K_BS:
            if stack:
                stack.pop()
            continue
        ctx = ctx_of(stack)
        if k == LB.K_ENTER:
            stack.append(("|", 0.0))
        elif k == LB.K_LETTER:
            stack.append((dec.letters[t], float(lm.logprobs_vocab(ctx[-(lm.order - 1):])[ord(dec.letters[t]) - 96])))
        else:
            if ctx == "" or ctx.endswith(" "):
                stack.append(("", 0.0))
            else:
                stack.append((" ", float(lm.logprobs_vocab(ctx[-(lm.order - 1):])[27])))
    return sum(d for _, d in stack)


def test_no_lm_equals_reference_beam():
    for seed in range(8):
        x = rand_lp(120, len(KV), seed)
        ref = IncrementalPrefixBeam(KV, 0, lm=None, beam=16, n_best=3, prune_topk=None, prune_logp=-8.0, align=False,
                                    search="vector")
        ref.push(x)
        r = ref.finalize()[0]
        d = LB.LMBeam(KV, 0, lm=None, beam=16, prune_logp=-8.0)
        d.push(x)
        h = d.nbest(1)[0]
        assert "".join(KV[t] for t in h.tokens) == r.text
        assert h.logp_acoustic == pytest.approx(r.logp_acoustic, abs=1e-9)


def test_chunking_is_exact(lm):
    x = rand_lp(200, len(KV), 3)
    a = LB.LMBeam(KV, 0, lm=lm, lm_weight=0.7, bonus=1.0, beam=12)
    a.push(x)
    b = LB.LMBeam(KV, 0, lm=lm, lm_weight=0.7, bonus=1.0, beam=12)
    for s in range(0, 200, 7):
        b.push(x[s:s + 7])
    ha, hb = a.nbest(5), b.nbest(5)
    assert [h.tokens for h in ha] == [h.tokens for h in hb]
    assert [h.score for h in ha] == pytest.approx([h.score for h in hb])


def test_lm_accounting_matches_independent_scorer(lm):
    for seed in range(5):
        x = rand_lp(150, len(KV), 10 + seed, peaky=False)
        d = LB.LMBeam(KV, 0, lm=lm, lm_weight=0.8, bonus=0.5, beam=16)
        d.push(x)
        for h in d.nbest(5, eos=False):
            assert h.logp_lm == pytest.approx(indep_lm_score(lm, d, h.tokens), abs=1e-9)
            assert h.score == pytest.approx(h.logp_acoustic + 0.8 * h.logp_lm + 0.5 * len(h.tokens), abs=1e-9)


def test_backspace_refunds_lm_and_enter_resets(lm):
    d = LB.LMBeam(KV, 0, lm=lm, lm_weight=1.0)
    ids = {c: i for i, c in enumerate(KV)}
    n0 = 0
    n1 = d._push_intended(n0, ids["t"])
    n2 = d._push_intended(n1, ids["q"])
    n3 = d._push_intended(n2, ids["⌫"])
    assert n3 == n1 and d.i_cum[n3] == d.i_cum[n1]
    n4 = d._push_intended(n1, ids["⏎"])
    assert d.i_ctx[n4] == "" and d.i_cum[n4] == d.i_cum[n1]
    assert d._push_intended(n4, ids["⌫"]) == n1
    # punctuation acts as a space; runs collapse
    n5 = d._push_intended(n1, ids["."])
    n6 = d._push_intended(n5, ids["_"])
    assert d.i_ctx[n5].endswith(" ") and d.i_cum[n6] == d.i_cum[n5]
    # leading backspace is a no-op
    assert d._push_intended(0, ids["⌫"]) == 0


def test_lexicon_term(lm):
    lex = frozenset({"the", "cat"})
    d = LB.LMBeam(KV, 0, lm=lm, lm_weight=1.0, lexicon=lex, lam=3.0)
    ids = {c: i for i, c in enumerate(KV)}
    n = 0
    for c in "cat":
        n = d._push_intended(n, ids[c])
    m = 0
    for c in "cqt":
        m = d._push_intended(m, ids[c])
    sp_in = d._push_intended(n, ids["_"])
    sp_out = d._push_intended(m, ids["_"])
    lp = float(lm.logprobs_vocab("cat")[27]), float(lm.logprobs_vocab("cqt")[27])
    assert d.i_cum[sp_in] - d.i_cum[n] == pytest.approx(lp[0])
    assert d.i_cum[sp_out] - d.i_cum[m] == pytest.approx(lp[1] - 3.0)
    # the row agrees with the push
    assert d._row(m)[ids["_"]] == pytest.approx(lp[1] - 3.0)


def test_98_vocab_kinds():
    v = ["<blank>", " ", "!", "A", "a", "_", "1", "⌫", "⏎"]
    k, letters = LB.token_table(v)
    assert list(k) == [LB.K_BLANK, LB.K_SPACE, LB.K_PUNCT, LB.K_LETTER, LB.K_LETTER, LB.K_PUNCT, LB.K_PUNCT,
                       LB.K_BS, LB.K_ENTER]
    assert letters[3] == "a"


def test_causal_prefix_does_not_see_future(lm):
    x = rand_lp(160, len(KV), 7)
    a = LB.LMBeam(KV, 0, lm=lm, lm_weight=0.5, beam=8)
    a.push(x[:80])
    snap = sorted(zip(a.nodes.tolist(), a.pb.tolist(), a.pnb.tolist()))
    y = x.copy()
    y[80:] = rand_lp(80, len(KV), 99)
    b = LB.LMBeam(KV, 0, lm=lm, lm_weight=0.5, beam=8)
    b.push(y[:80])
    assert sorted(zip(b.nodes.tolist(), b.pb.tolist(), b.pnb.tolist())) == snap
