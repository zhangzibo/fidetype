"""M4-09: exact fast lexicon fallback and time-budgeted prewarm. Synthetic data only.

Main properties: ``PronLexicon.nearest`` returns exactly what
``nearest_bruteforce`` returns (words, distance, order), and a time budget on
the prewarm never changes a decode result.
"""

from __future__ import annotations

import random
import time

import numpy as np
import pytest

from fidetype.lm import RETUNED, CharNgramLM, IncrementalPrefixBeam, ctc_prefix_beam_search
from fidetype.lm.phoneme_words import (
    PhonemeWordDecoder,
    PronLexicon,
    _levenshtein_many,
    edit_distance_str,
)
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.incremental import CTCBeamSpec

ALPHA = "abcdefgh"


def _rand(rng, lo, hi, alpha=ALPHA):
    return "".join(rng.choice(alpha) for _ in range(rng.randint(lo, hi)))


def _lexicon(seed=0, n_words=600):
    rng = random.Random(seed)
    prons: dict[str, list[str]] = {}
    pool = [_rand(rng, 1, 9) for _ in range(n_words)]
    for i in range(n_words):
        ps = [pool[i]]
        if rng.random() < 0.15:
            ps.append(rng.choice(pool))  # homophones and variants
        prons[f"w{i:04d}"] = list(dict.fromkeys(ps))
    lex = PronLexicon(prons)
    words = sorted(prons)
    lex.set_fallback_words(rng.sample(words, n_words // 2) + words[:20])  # some words twice
    return lex, rng


def test_levenshtein_many_equals_scalar():
    rng = random.Random(1)
    for n in range(1, 8):
        rows = [_rand(rng, n, n) for _ in range(40)]
        codes = np.array([[ord(c) for c in r] for r in rows], dtype=np.int32)
        for _ in range(30):
            q = _rand(rng, 0, 10)
            got = _levenshtein_many(np.array([ord(c) for c in q], dtype=np.int32), codes)
            assert got.tolist() == [edit_distance_str(q, r) for r in rows]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_nearest_equals_bruteforce(seed):
    lex, rng = _lexicon(seed)
    fb = sorted({p for ps in lex._fallback.values() for p in ps})
    queries = [""] + [_rand(rng, 1, 14) for _ in range(150)] + [_rand(rng, 1, 6, "abcxyz") for _ in range(30)]
    for _ in range(150):  # edited fallback pronunciations
        p = list(rng.choice(fb))
        for _ in range(rng.randint(0, 4)):
            k = rng.randrange(len(p) + 1)
            op = rng.random()
            if op < 1 / 3 and len(p) > 1:
                p.pop(min(k, len(p) - 1))
            elif op < 2 / 3:
                p.insert(k, rng.choice(ALPHA))
            else:
                p[min(k, len(p) - 1)] = rng.choice(ALPHA)
        queries.append("".join(p))
    n_hits = 0
    for q in queries:
        for mld in (0, 1, 2, 3, -1):
            a, b = lex.nearest_bruteforce(q, mld), lex.nearest(q, mld)
            assert a == b, (q, mld)
            n_hits += bool(a)
    assert n_hits > 100  # the test covers non-empty results


def test_nearest_follows_set_fallback_words():
    lex, _ = _lexicon(3)
    q = "abcab"
    assert lex.nearest(q) == lex.nearest_bruteforce(q)  # builds the index
    lex.set_fallback_words(["w0001", "w0002"])
    assert lex.nearest(q) == lex.nearest_bruteforce(q)
    lex.set_fallback_words([])
    assert lex.nearest(q) == [] == lex.nearest_bruteforce(q)


# --- word decoder warm steps -------------------------------------------------------


class _H:
    def __init__(self, text, lp=0.0):
        self.text, self.logp_acoustic = text, lp
        self.char_confidences = [0.9] * len(text)


def _wdec(lex, lm):
    uni = {w: -1.0 - (i % 7) for i, w in enumerate(sorted(lex.prons))}
    return PhonemeWordDecoder(lex, uni, sentence_lm=lm.score_sentence, n_best=5)


def test_warm_steps_fill_the_caches_and_change_nothing():
    lex, rng = _lexicon(4)
    lm = CharNgramLM(order=3).train([" ".join(f"w{rng.randrange(600):04d}" for _ in range(5)) for _ in range(200)])
    texts = [" ".join(_rand(rng, 2, 8) for _ in range(rng.randint(1, 4))) for _ in range(12)]
    hyps = [_H(t, -float(i)) for i, t in enumerate(texts)]
    cold = _wdec(lex, lm)
    ref = cold.decode(hyps)
    warm = _wdec(lex, lm)
    n_steps = sum(1 for _ in warm.warm(texts))
    assert n_steps > 0
    assert warm._cand_cache == cold._cand_cache  # same keys, same values
    assert set(cold._lm_cache) <= set(warm._lm_cache)
    lm_calls = []
    warm.sentence_lm = lambda t: lm_calls.append(t) or lm.score_sentence(t)
    got = warm.decode(hyps)
    assert not lm_calls  # decode needed nothing new
    assert [(h.text, h.score, h.char_confidences) for h in got] == [(h.text, h.score, h.char_confidences) for h in ref]
    assert sum(1 for _ in warm.warm(texts)) == 0  # all cached


def test_warm_is_lazy():
    lex, _ = _lexicon(5)
    w = _wdec(lex, CharNgramLM(order=2).train(["w0001 w0002"]))
    it = w.warm(["abc def", "gha"])
    assert w._cand_cache == {}
    next(it)
    assert len(w._cand_cache) <= 1


# --- budgeted prewarm ---------------------------------------------------------------


@pytest.fixture(scope="module")
def streams():
    sents = sentences(40, seed=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=4)
    lm = CharNgramLM(order=4).train(sents[10:])
    return lm, [sim.simulate(s, seed=31 * i).stream for i, s in enumerate(sents[:4])]


def _same(a, b):
    assert a.texts == b.texts
    for x, y in zip(a.candidates, b.candidates):
        assert (x.score, x.logp_acoustic) == (y.score, y.logp_acoustic)
        assert np.array_equal(np.asarray(x.char_confidences), np.asarray(y.char_confidences), equal_nan=True)


def _warm_recorder():
    seen = []

    def warm(texts):
        for t in texts[:5]:
            seen.append(t)
            yield

    return seen, warm


def _run_budgeted(lm, sts, budget, warm, clock=None):
    kw = {} if clock is None else {"clock": clock}
    spec = CTCBeamSpec(dict(RETUNED, beam=24), lm=lm, prewarm_every=3, prewarm_max_new=64, prewarm_budget_s=budget,
                       on_prewarm=warm, **kw)
    n_done = n_dropped = 0
    for st in sts:
        ref = spec.decode_fn(st)
        dec = spec.factory({"vocab": list(st.vocab), "blank_id": st.blank_id})
        for t in range(st.n_frames):
            dec.push_frames(st.log_probs[t:t + 1])
        _same(dec.finalize(st), ref)
        n_done += dec.n_prewarm
        n_dropped += dec.n_prewarm_dropped
    return n_done, n_dropped


@pytest.mark.parametrize("budget", [1e-5, 5e-4, 0.05])
def test_budgeted_prewarm_equals_batch(streams, budget):
    """Real clock. How much prewarm work runs depends on the machine load
    (with 1e-5 s, on_prewarm steps run only in rare fast pushes), so this
    test asserts only results. The fake-clock test below checks coverage
    (M4-11: an ``assert seen`` here was flaky under load)."""
    lm, sts = streams
    _, warm = _warm_recorder()
    n_done, n_dropped = _run_budgeted(lm, sts, budget, warm)
    assert n_done + n_dropped > 0  # prewarms started (frame count, not time)


class _FakeClock:
    """Deterministic adversarial time source: each call advances the time by
    a step from ``steps`` (seeded choice), so a budget runs out at arbitrary
    points: inside a beam alignment loop, between steps, or at once."""

    def __init__(self, seed, steps):
        self.rng, self.steps, self.t, self.calls = random.Random(seed), steps, 0.0, 0

    def __call__(self):
        self.calls += 1
        self.t += self.rng.choice(self.steps)
        return self.t


@pytest.mark.parametrize("schedule", ["random", "bursty", "expired", "frozen"])
@pytest.mark.parametrize("seed", range(4))
def test_budgeted_prewarm_fake_clock(streams, schedule, seed):
    """M4-11: decisions never depend on the budget. With a fake clock the
    budget runs out at adversarial points; every result still equals the
    batch decode. The coverage asserts are deterministic."""
    lm, sts = streams
    budget = 1e-5
    steps = {
        "random": [0.0, 1e-6, 4e-6, 9e-6, 2e-5],  # out of budget after a few calls, at random points
        "bursty": [0.0] * 6 + [1.0],  # mostly frozen, then one large jump
        "expired": [1.0],  # every check after the start is past the deadline
        "frozen": [0.0],  # the deadline never comes: all work runs
    }[schedule]
    clock = _FakeClock(seed, steps)
    seen, warm = _warm_recorder()
    n_done, n_dropped = _run_budgeted(lm, sts, budget, warm, clock)
    assert clock.calls > 0  # the decoder used the injected clock
    if schedule == "expired":
        assert n_done == 0 and not seen  # no step ever runs
    elif schedule == "frozen":
        assert seen and n_done > 0 and n_dropped == 0  # every prewarm ends in its push
    else:
        assert seen and n_dropped > 0  # some prewarms complete their on_prewarm steps, some are cut


def test_beam_prewarm_fake_clock_cuts_mid_loop(streams):
    """The beam memo is a cache: a deadline cut at any alignment gives the same final result."""
    lm, sts = streams
    st = sts[2]
    kw = dict(RETUNED, beam=16)
    ref = ctc_prefix_beam_search(st, lm, **kw)
    kw.pop("blank_id", None)
    n_cut = 0
    for cut in range(0, 12):
        dec = IncrementalPrefixBeam(list(st.vocab), st.blank_id, lm, **kw)
        n = [0]

        def clock():  # call k returns k: the deadline passes after `cut` checks
            n[0] += 1
            return float(n[0])

        for t0 in range(0, st.n_frames, 25):
            dec.push(st.log_probs[t0:t0 + 25])
            n[0] = 0
            got_new = dec.prewarm(deadline=float(cut) + 0.5, clock=clock)
            assert got_new <= cut
            n_cut += n[0] > cut
        got = dec.finalize()
        assert [(h.text, h.score) for h in got] == [(h.text, h.score) for h in ref]
        for x, y in zip(got, ref):
            assert np.array_equal(np.asarray(x.char_confidences), np.asarray(y.char_confidences), equal_nan=True)
    assert n_cut > 0  # the deadline did cut some prewarm loops


def test_budget_bounds_the_work_per_push(streams):
    lm, sts = streams
    st = sts[0]
    steps_in_push = []
    cur = [0]

    def slow(texts):
        for _ in range(4):
            t0 = time.perf_counter()
            while time.perf_counter() - t0 < 3e-3:  # 3 ms per step, budget 1 ms
                pass
            cur[0] += 1
            yield

    spec = CTCBeamSpec(dict(RETUNED, beam=16), lm=None, prewarm_every=2, prewarm_budget_s=1e-3, on_prewarm=slow)
    dec = spec.factory({"vocab": list(st.vocab), "blank_id": st.blank_id})
    for t in range(st.n_frames):
        cur[0] = 0
        dec.push_frames(st.log_probs[t:t + 1])
        steps_in_push.append(cur[0])
    assert max(steps_in_push) == 1  # one slow step per push at most
    assert sum(steps_in_push) > 4  # the work continues across pushes
    _same(dec.finalize(st), spec.decode_fn(st))

    # Without a budget, one push runs the whole prewarm.
    spec0 = CTCBeamSpec(dict(RETUNED, beam=16), lm=None, prewarm_every=2, on_prewarm=slow)
    dec0 = spec0.factory({"vocab": list(st.vocab), "blank_id": st.blank_id})
    cur[0] = 0
    dec0.push_frames(st.log_probs[0:1])
    dec0.push_frames(st.log_probs[1:2])
    assert cur[0] == 4


def test_finalize_drops_unfinished_prewarm(streams):
    lm, sts = streams
    st = sts[1]

    def endless(texts):
        while True:
            yield

    spec = CTCBeamSpec(dict(RETUNED, beam=16), lm=lm, prewarm_every=1, prewarm_budget_s=1e-4, on_prewarm=endless)
    dec = spec.factory({"vocab": list(st.vocab), "blank_id": st.blank_id})
    for t in range(st.n_frames):
        dec.push_frames(st.log_probs[t:t + 1])
    _same(dec.finalize(st), spec.decode_fn(st))
    assert dec._pending is None and dec.n_prewarm_dropped >= 1


def test_beam_prewarm_deadline(streams):
    lm, sts = streams
    st = sts[2]
    kw = dict(RETUNED, beam=16)
    ref = ctc_prefix_beam_search(st, lm, **kw)
    kw.pop("blank_id", None)
    dec = IncrementalPrefixBeam(list(st.vocab), st.blank_id, lm, **kw)
    dec.push(st.log_probs)
    assert dec.prewarm(deadline=time.perf_counter() - 1.0) == 0  # past deadline: no new alignment
    assert dec.prewarm(deadline=time.perf_counter() + 60.0) > 0
    got = dec.finalize()
    assert [(h.text, h.score) for h in got] == [(h.text, h.score) for h in ref]


def test_budget_validation():
    with pytest.raises(ValueError):
        CTCBeamSpec({}, prewarm_budget_s=0.0)
