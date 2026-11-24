"""Tests of the P5-38 search cache of ``LmReadout`` (exact reuse of the forward search by the
``lm_beam_direction`` offer gate). Synthetic data only."""

from __future__ import annotations

import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.lm.ngram import CharNgramLM
from fidetype.pretrained.lmreadout import LmReadout
from fidetype.trust import offer_gate as og
from fidetype.trust.offer_gate import OfferGate

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits

SETTINGS = {"lm_weight": 0.5, "bonus": 1.0, "beam": 8, "prune_logp": -8.0, "n_best": 8}  # the willett-hw values


def _norm(x):
    return x - np.log(np.exp(x).sum(1, keepdims=True))


def _hyp_tuple(h):
    return (tuple(h.tokens), tuple(h.frames), float(h.score).hex(), float(h.logp_acoustic).hex(),
            float(h.logp_lm).hex())


@pytest.fixture(scope="module")
def lm():
    return CharNgramLM(order=4).train(PHRASES * 20)


@pytest.fixture(scope="module")
def inputs():
    rng = np.random.default_rng(5)
    return [_norm(fake_logits(str(rng.choice(PHRASES)), rng)) for _ in range(12)]


@pytest.fixture(scope="module")
def guard() -> ft.TrustGuard:
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    return ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON,
                        null_trials=40, decoder_name="test-ctc")


def test_cache_gives_the_same_hypotheses(lm, inputs):
    on = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    off = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    off.search_cache = 0
    for lp in inputs:
        for x in (lp, np.ascontiguousarray(lp[::-1])):
            for n in (1, 3, None, 1):  # the last call is served from the cache
                a = [_hyp_tuple(h) for h in on.hyps(x, n, use_gate=False)]
                b = [_hyp_tuple(h) for h in off.hyps(x, n, use_gate=False)]
                assert a == b and a
            assert on.nbest(x) == off.nbest(x)
            assert og.lm_beam_direction(x, on, details=True) == og.lm_beam_direction(x, off, details=True)
    assert on.search_stats["cached"] > 0
    assert off.search_stats["cached"] == 0


def test_cache_hits_on_bit_equal_input_only(lm, inputs):
    ro = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    lp = inputs[0].astype(np.float32)
    ro.hyps(lp, 1, use_gate=False)
    assert ro.search_stats == {"run": 1, "cached": 0}
    ro.hyps(np.asarray(lp, np.float64).copy(), 8, use_gate=False)  # another array, the same values: a hit
    assert ro.search_stats == {"run": 1, "cached": 1}
    ro.hyps(np.ascontiguousarray(lp[::-1]), 1, use_gate=False)  # reversed: a new search
    assert ro.search_stats == {"run": 2, "cached": 1}
    # a changed value is a new search, and its result equals an uncached search
    y = np.asarray(lp, np.float64).copy()
    y[3, 2] = np.nextafter(y[3, 2], 0.0)
    fresh = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    fresh.search_cache = 0
    assert [_hyp_tuple(h) for h in ro.hyps(y, None, use_gate=False)] == \
        [_hyp_tuple(h) for h in fresh.hyps(y, None, use_gate=False)]
    assert ro.search_stats["run"] == 3
    # the cache keeps 2 searches: the first input is gone now
    ro.hyps(lp, 1, use_gate=False)
    assert ro.search_stats["run"] == 4


def test_cache_copies_input_and_output(lm, inputs):
    ro = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    ref = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    ref.search_cache = 0
    x = inputs[1].copy()
    h1 = ro.hyps(x, 1, use_gate=False)
    h1[0].tokens.append(999)  # a caller that changes a result does not change the kept result
    assert [_hyp_tuple(h) for h in ro.hyps(x, 1, use_gate=False)] == [_hyp_tuple(h) for h in ref.hyps(x, 1, use_gate=False)]
    x[:5] = x[:5][::-1].copy()  # the caller changes its array in place: a new search, not the kept result
    before = ro.search_stats["run"]
    assert [_hyp_tuple(h) for h in ro.hyps(x, 1, use_gate=False)] == [_hyp_tuple(h) for h in ref.hyps(x, 1, use_gate=False)]
    assert ro.search_stats["run"] == before + 1


def test_cache_follows_settings_and_lm(lm, inputs):
    ro = LmReadout(VOCAB, lm, SETTINGS, gate=None)
    x = inputs[2]
    ro.hyps(x, 1, use_gate=False)
    ro.settings = dict(SETTINGS, beam=4)
    ref = LmReadout(VOCAB, lm, dict(SETTINGS, beam=4), gate=None)
    ref.search_cache = 0
    assert [_hyp_tuple(h) for h in ro.hyps(x, None, use_gate=False)] == \
        [_hyp_tuple(h) for h in ref.hyps(x, None, use_gate=False)]
    assert ro.search_stats == {"run": 2, "cached": 0}
    ro.lm = None
    ro.hyps(x, 1, use_gate=False)
    assert ro.search_stats == {"run": 3, "cached": 0}


def test_guard_reuses_the_forward_search_and_keeps_every_decision(guard, lm, inputs):
    """A guard that decodes with the readout and has the direction gate: one new search per offer (the
    reversed one), and the same decisions, reasons and features as without the cache."""
    out = {}
    for mode in ("off", "on"):
        ro = LmReadout(VOCAB, lm, SETTINGS, gate=None)
        ro.search_cache = 0 if mode == "off" else 2
        # no commits, choice sets up to 8: the gate sees offers
        g = ft.TrustGuard(guard.config.with_policy(commit_p=math.inf, offer_max_k=8), guard._codec, guard.sheet, decode_fn=ro.decode_fn(),
                          offer_gate=OfferGate("lm_beam_direction", 0.0, lm_name="toy", readout=ro))
        g.collect_offer_features = True
        rows = []
        for x in inputs:
            for y in (x, np.ascontiguousarray(x[::-1])):
                ro._memo.clear()  # else the reversed input of the step before is a cache hit as well
                s = dict(ro.search_stats)
                r = g._decide_quiet(y)
                rows.append((r.action, r.raw_action, r.text, r.choices, float(r.p_top1).hex(), r.reason,
                             g._offer_gate_why, {k: float(v).hex() for k, v in g.last_offer_features.items()}))
                if mode == "on":
                    # decode (1 new search) + gate: forward from the cache, reversed new
                    assert ro.search_stats["run"] - s["run"] == 2
                    assert ro.search_stats["cached"] - s["cached"] == 1
                else:
                    assert ro.search_stats["run"] - s["run"] == 3
        out[mode] = rows
    assert out["on"] == out["off"]
    acts = [r[0] for r in out["on"]]
    assert "offer" in acts and any(r[6] for r in out["on"]), acts  # offers, and offers the gate withholds
