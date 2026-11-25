"""P5-41: the faster ``LMBeam.push`` loop gives bit-equal search states and hypotheses to the P11-07 loop
(``LMBeam._push_reference``). Synthetic data only, CPU, seconds."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fidetype.lm.ngram import CharNgramLM
from fidetype.pretrained._xbody import VOCAB as XVOCAB
from fidetype.pretrained.lmreadout import LMBeam, LmReadout

# a small key vocabulary with every token kind: blank, letters, Space, punctuation, Backspace, Enter, no-kind
SMALL = ["<b>", *"abcdefghijklmnopqrstuvwxyz", " ", ".", ",", "⌫", "⏎", "<unk>"]
PHRASES = ["the cat sat on the mat", "a dog ran far", "hello there", "we will see", "see the dog"]


@pytest.fixture(scope="module")
def lm():
    return CharNgramLM(order=4).train(PHRASES * 10)


def _norm(z):
    return z - np.log(np.exp(z).sum(1, keepdims=True))


def _peaky(rng, T, V, peak):
    z = rng.standard_normal((T, V)) * 3.0
    z[:, 0] += peak
    return _norm(z)


def _state(d: LMBeam):
    bits = [np.asarray(a, np.float64).view(np.uint64).tobytes() for a in (d.pb, d.pnb, d.lms, d.ln, d.L)]
    hyps = [(tuple(h.tokens), tuple(h.frames), float(h.score).hex(), float(h.logp_acoustic).hex(),
             float(h.logp_lm).hex()) for h in d.nbest(None)]
    return (d.nodes.tolist(), d.par.tolist(), d.last.tolist(), d.L.shape, bits, d.k_par, d.k_tok, d.k_fr, d.k_in,
            d.i_par, [float(v).hex() for v in d.i_cum], d.i_ctx, d.i_word, d.t, hyps)


def _check(vocab, lm, lp, chunks=(None,), **kw):
    """Push ``lp`` with the new and the reference loop (in the same chunks) and compare after each chunk."""
    a, b = LMBeam(vocab, 0, lm=lm, **kw), LMBeam(vocab, 0, lm=lm, **kw)
    cuts = [0] + [c for c in chunks if c is not None] + [lp.shape[0]]
    for s, e in zip(cuts[:-1], cuts[1:]):
        a.push(lp[s:e])
        b._push_reference(lp[s:e])
        assert _state(a) == _state(b)
    return a


SETTINGS = [dict(lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0),  # the willett-hw values
            dict(lm_weight=0.0, bonus=0.0, beam=4, prune_logp=-8.0),
            dict(lm_weight=1.0, bonus=2.0, beam=16, prune_logp=-6.0)]


@pytest.mark.parametrize("kw", SETTINGS)
def test_equal_on_peaky_input_full_and_chunked(lm, kw):
    rng = np.random.default_rng(1)
    for vocab in (SMALL, list(XVOCAB)):
        for k in range(3):
            lp = _peaky(rng, 150 + 50 * k, len(vocab), peak=1.0 + 1.5 * k)
            _check(vocab, lm, lp, **kw)
            _check(vocab, lm, lp, chunks=(1, 37, 90), **kw)
            _check(vocab, None, lp, **kw)  # no LM


def test_equal_with_ties_many_keys_and_infinities(lm):
    rng = np.random.default_rng(2)
    V = len(SMALL)
    # coarse values: many equal scores, so the argpartition cut and the rank see ties
    tied = np.round(_peaky(rng, 200, V, 1.0) * 2.0) / 2.0
    _check(SMALL, lm, tied, lm_weight=0.0, bonus=0.0, beam=4, prune_logp=-8.0)
    _check(SMALL, lm, tied, lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0)
    # near-flat frames: most keys pass the prune, so beam x keys > 64 (the numpy candidate path)
    flat = _norm(rng.standard_normal((120, len(XVOCAB))) * 0.3)
    _check(list(XVOCAB), lm, flat, lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0)
    # -inf values, all-blank frames, and frames with every value -inf (the beam can empty)
    x = _peaky(rng, 160, V, 2.0)
    x[10:20, 1:] = -np.inf
    x[20:30] = -np.inf
    x[40:45, 0] = -np.inf
    _check(SMALL, lm, x, lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0)
    _check(SMALL, lm, x[20:60], lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0)
    # an empty chunk changes nothing
    _check(SMALL, lm, x[:50], chunks=(25, 25), lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0)


def test_equal_with_lexicon_term(lm):
    rng = np.random.default_rng(3)
    lex = frozenset("the cat sat on mat a dog ran far hello there we will see".split())
    lp = _peaky(rng, 200, len(SMALL), 1.5)
    _check(SMALL, lm, lp, lm_weight=0.5, bonus=1.0, beam=8, prune_logp=-8.0, lexicon=lex, lam=2.0)


def test_readout_and_direction_feature_unchanged(lm, monkeypatch):
    """The readout n-best and the lm_beam_direction value are bit-equal with the reference loop."""
    from fidetype.trust import offer_gate as og

    rng = np.random.default_rng(4)
    ro = LmReadout(list(XVOCAB), lm, {"lm_weight": 0.5, "bonus": 1.0, "beam": 8, "prune_logp": -8.0}, None)
    ro.search_cache = 0
    xs = [_peaky(rng, 180, len(XVOCAB), 2.0 + k) for k in range(3)]
    new = [(ro.nbest(x), og.lm_beam_direction(x, ro, details=True)) for x in xs]
    monkeypatch.setattr(LMBeam, "push", LMBeam._push_reference)
    old = [(ro.nbest(x), og.lm_beam_direction(x, ro, details=True)) for x in xs]
    for (nb1, (v1, d1)), (nb2, (v2, d2)) in zip(new, old):
        assert nb1 == nb2
        assert float(v1).hex() == float(v2).hex() and d1 == d2
        assert math.isfinite(v1)


def test_bad_shape_raises():
    d = LMBeam(SMALL, 0)
    with pytest.raises(ValueError):
        d.push(np.zeros((3, len(SMALL) + 1)))
