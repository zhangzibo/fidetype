"""M4-10: LRU bounds on the decoder memos. Synthetic data only.

Main property: a size bound on a memo changes no result. The word decoder
and the character LM give exactly the same output with any bound as with
no bound, also when the memos evict entries all the time.
"""

from __future__ import annotations

import pickle
import random

import numpy as np
import pytest

from fidetype.lm import RETUNED, CharNgramLM
from fidetype.lm.cache import LRUCache
from fidetype.lm.phoneme_words import DEFAULT_CAND_CACHE_SIZE, DEFAULT_LM_CACHE_SIZE, PhonemeWordDecoder, PronLexicon
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.incremental import CTCBeamSpec
from fidetype.trust.types import from_lm_hypotheses

ALPHA = "abcdefgh"


# --- LRUCache -------------------------------------------------------------------------


def test_lru_evicts_least_recently_used():
    c = LRUCache(3)
    for k in "abc":
        c[k] = k.upper()
    assert c.get("a") == "A"  # a is now the most recent
    c["d"] = "D"
    assert list(c) == ["c", "a", "d"] and "b" not in c
    assert c["c"] == "C"  # [] also refreshes
    c["e"] = "E"
    assert list(c) == ["d", "c", "e"]
    c["d"] = "D2"  # replace: no eviction, most recent
    assert list(c) == ["c", "e", "d"] and c.evictions == 2
    assert c.get("zz") is None and c.get("zz", 5) == 5
    assert c.info() == {"size": 3, "maxsize": 3, "hits": 1, "misses": 2, "evictions": 2}


def test_lru_unbounded_resize_and_validation():
    c = LRUCache(None)
    for i in range(1000):
        c[i] = i
    assert len(c) == 1000 and c.evictions == 0
    c.get(0)
    c.resize(10)
    assert len(c) == 10 and 0 in c and 1 not in c
    for bad in (0, -1, 2.5, True):
        with pytest.raises(ValueError):
            LRUCache(bad)
    with pytest.raises(ValueError):
        c.resize(0)


def test_lru_equality_pickle_copy():
    a, b = LRUCache(5), LRUCache(None)
    a["x"], a["y"] = 1, 2
    b["y"], b["x"] = 2, 1
    assert a == b == {"x": 1, "y": 2}  # order does not matter
    assert a != {"x": 1}
    a.get("x")
    r = pickle.loads(pickle.dumps(a))
    assert isinstance(r, LRUCache) and r.maxsize == 5 and list(r) == ["y", "x"] and r == a
    cp = a.copy()
    assert isinstance(cp, LRUCache) and cp.maxsize == 5 and list(cp) == list(a)
    cp["z"] = 3
    assert "z" not in a


# --- word decoder -------------------------------------------------------------------


def _rand(rng, lo, hi, alpha=ALPHA):
    return "".join(rng.choice(alpha) for _ in range(rng.randint(lo, hi)))


def _lexicon(seed=0, n_words=500):
    rng = random.Random(seed)
    pool = [_rand(rng, 1, 9) for _ in range(n_words)]
    prons = {f"w{i:04d}": [pool[i]] for i in range(n_words)}
    lex = PronLexicon(prons)
    lex.set_fallback_words(rng.sample(sorted(prons), n_words // 2))
    return lex, rng


class _H:
    def __init__(self, text, lp, conf):
        self.text, self.logp_acoustic, self.char_confidences = text, lp, conf


def _key(hyps):
    return [(h.text, h.score, h.logp_acoustic, h.logp_lm, h.char_confidences, h.edits, h.words_conf) for h in hyps]


def test_default_bound_is_set():
    lex, _ = _lexicon(1)
    d = PhonemeWordDecoder(lex, {})
    info = d.cache_info()
    assert info["candidates"]["maxsize"] == DEFAULT_CAND_CACHE_SIZE
    assert info["sentence_lm"]["maxsize"] == DEFAULT_LM_CACHE_SIZE
    u = PhonemeWordDecoder(lex, {}, cand_cache_size=None, lm_cache_size=None).cache_info()
    assert u["candidates"]["maxsize"] is None and u["sentence_lm"]["maxsize"] is None


@pytest.mark.parametrize("seed", [0, 1])
def test_word_decoder_bound_changes_no_result(seed):
    lex, rng = _lexicon(seed)
    lm = CharNgramLM(order=3).train([" ".join(f"w{rng.randrange(500):04d}" for _ in range(5)) for _ in range(300)])
    uni = {w: -1.0 - (i % 7) for i, w in enumerate(sorted(lex.prons))}
    # A long "session": 120 n-best lists; segments repeat across utterances, so hits and evictions mix.
    seg_pool = [_rand(rng, 1, 10) for _ in range(60)] + [_rand(rng, 1, 6, "abcxyz") for _ in range(10)]
    session = []
    for _ in range(120):
        nb = []
        for j in range(rng.randint(1, 6)):
            t = " ".join(rng.choice(seg_pool) for _ in range(rng.randint(1, 4)))
            nb.append(_H(t, -float(j) - rng.random(), [rng.random() for _ in t]))
        session.append(nb)
    sizes = (1, 2, 7, 40, None)
    decs = {n: PhonemeWordDecoder(lex, uni, sentence_lm=lm.score_sentence, n_best=5, cand_cache_size=n, lm_cache_size=n)
            for n in sizes}
    for i, nb in enumerate(session):
        outs = {}
        for n, d in decs.items():
            if i % 3 == 0:  # interleave warm steps (as a budgeted prewarm does), sometimes cut short
                for k, _ in enumerate(d.warm([h.text for h in nb])):
                    if k > 4 * (i % 4):
                        break
            outs[n] = _key(d.decode(nb))
        for n in sizes:
            assert outs[n] == outs[None], (i, n)
    for n, d in decs.items():
        info = d.cache_info()
        if n is not None:
            assert info["candidates"]["size"] <= n and info["sentence_lm"]["size"] <= n
            if n <= 7:
                assert info["candidates"]["evictions"] > 0 and info["sentence_lm"]["evictions"] > 0
        else:
            assert info["candidates"]["evictions"] == 0
    # Shrinking a filled cache keeps the results too.
    d = decs[None]
    d.set_cache_sizes(3, 2)
    assert d.cache_info()["candidates"]["size"] <= 3
    assert _key(d.decode(session[5])) == _key(decs[1].decode(session[5]))
    d.clear_caches()
    assert d.cache_info()["candidates"]["size"] == 0


def test_char_lm_bound_changes_no_result():
    sents = sentences(200, seed=3)
    big = CharNgramLM(order=5, cache_size=None).train(sents)
    small = CharNgramLM(order=5, cache_size=7).train(sents)
    rng = random.Random(4)
    for _ in range(3):
        for s in sents[:60]:
            a, b = big.score_sentence(s), small.score_sentence(s)
            assert a == b
            ctx = s[: rng.randint(0, len(s))]
            assert np.array_equal(big.logprobs_vocab(ctx), small.logprobs_vocab(ctx))
    assert len(small._cache) <= 7 and small._cache.evictions > 0
    assert big._cache.evictions == 0 and len(big._cache) > 7


# --- streaming: bounded caches + budgeted prewarm = unbounded batch -----------------------


def test_streaming_with_tiny_caches_equals_unbounded_batch():
    sents = sentences(30, seed=11)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=6)
    sts = [sim.simulate(s, seed=17 * i).stream for i, s in enumerate(sents[:8])]
    words = sorted({w for s in sentences(300, seed=2) for w in s.split()} | {w for s in sents for w in s.split()})
    lex = PronLexicon({w: [w] for w in words})  # spelling as the "pronunciation": char streams work
    lex.set_fallback_words(words[::2])
    lm = CharNgramLM(order=4, cache_size=None).train(sentences(300, seed=2))
    lm_small = CharNgramLM(order=4, cache_size=5).train(sentences(300, seed=2))
    uni = {w: -1.0 - (i % 5) for i, w in enumerate(words)}
    ref_dec = PhonemeWordDecoder(lex, uni, sentence_lm=lm.score_sentence, n_best=5, cand_cache_size=None, lm_cache_size=None)
    small = PhonemeWordDecoder(lex, uni, sentence_lm=lm_small.score_sentence, n_best=5, cand_cache_size=3, lm_cache_size=3)

    def post_for(d):
        return lambda hyps, st: from_lm_hypotheses(d.decode(hyps), st.meta, confidence_variant=None)

    kw = dict(RETUNED, beam=24)
    batch = CTCBeamSpec(kw, lm=None, post=post_for(ref_dec))
    inc = CTCBeamSpec(kw, lm=None, post=post_for(small), prewarm_every=3, prewarm_max_new=64, prewarm_budget_s=2e-4,
                      on_prewarm=lambda texts: small.warm(texts[:5]))
    for st in sts:
        ref = batch.decode_fn(st)
        dec = inc.factory({"vocab": list(st.vocab), "blank_id": st.blank_id})
        for t in range(st.n_frames):
            dec.push_frames(st.log_probs[t:t + 1])
        got = dec.finalize(st)
        assert got.texts == ref.texts
        for x, y in zip(got.candidates, ref.candidates):
            assert (x.score, x.logp_acoustic) == (y.score, y.logp_acoustic)
            assert np.array_equal(np.asarray(x.char_confidences), np.asarray(y.char_confidences), equal_nan=True)
    info = small.cache_info()
    assert info["candidates"]["size"] <= 3 and info["candidates"]["evictions"] > 0
