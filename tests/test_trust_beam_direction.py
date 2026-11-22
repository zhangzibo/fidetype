"""Tests of the P5-36b ``lm_beam_direction`` offer-gate feature (two-direction LM-beam score;
fidetype.trust.offer_gate, TrustGuard offer gates). Synthetic data only."""

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


@pytest.fixture(scope="module")
def readout() -> LmReadout:
    lm = CharNgramLM(order=4).train(PHRASES * 20)
    return LmReadout(VOCAB, lm, SETTINGS, gate=None, blank=0)


@pytest.fixture(scope="module")
def guard() -> ft.TrustGuard:
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    return ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON,
                        null_trials=40, decoder_name="test-ctc")


@pytest.fixture(scope="module")
def inputs():
    rng = np.random.default_rng(11)
    return [fake_logits(str(rng.choice(PHRASES)), rng) for _ in range(40)]


def test_beam_direction_is_antisymmetric_and_positive(readout, inputs):
    for x in inputs:
        lp = _norm(x)
        f, d = og.lm_beam_direction(lp, readout, details=True)
        r = og.lm_beam_direction(np.ascontiguousarray(lp[::-1]), readout)
        assert f == pytest.approx(-r, abs=1e-9)
        assert d["T"] == len(lp) and d["n_fwd"] > 0
        assert f > 0  # English-like phrases decode better forward than backward
        assert f == pytest.approx((d["s_fwd"] - d["s_rev"]) / ((d["n_fwd"] + d["n_rev"]) / 2 + 1), abs=1e-12)
    assert og.lm_beam_direction(np.zeros((0, len(VOCAB))), readout) == 0.0


def test_beam_score_is_the_readout_top1(readout, inputs):
    lp = _norm(inputs[0])
    s, n = og.beam_score(lp, readout)
    h = readout.hyps(lp, 1, use_gate=False)[0]
    assert (s, n) == (h.score, len(h.tokens))
    assert math.isfinite(s)


def test_gate_needs_readout(readout):
    with pytest.raises(ValueError, match="lm_name"):
        OfferGate("lm_beam_direction", 0.1)
    with pytest.raises(ValueError, match="LM-beam readout"):
        OfferGate("lm_beam_direction", 0.1, lm_name="toy").check_kind("logits")
    g = OfferGate("lm_beam_direction", 0.1, lm_name="toy", readout=readout)
    g.check_kind("logits")
    with pytest.raises(ValueError, match="does not apply"):
        g.check_kind("nbest")
    d = g.to_dict()
    assert "readout" not in d and d["lm_name"] == "toy"
    g2 = OfferGate.from_dict(d, readout=readout)
    assert g2 == g and g2.readout is readout
    # the fit rule of P5-33: value at index floor(0.05 m) of the ascending real offer values
    v = list(np.linspace(-1, 2, 66))
    assert OfferGate.fit("lm_beam_direction", v, keep=0.95, lm_name="toy", readout=readout).threshold == v[3]


def test_gate_in_the_guard_withholds_reversed_input(guard, readout, inputs):
    base = guard.offer_gates
    g = OfferGate("lm_beam_direction", 0.0, lm_name="toy", readout=readout)
    gated = ft.TrustGuard(guard.config, guard._codec, guard.sheet, offer_gate=g)
    assert gated.config_id == guard.config_id
    n_off = n_rev_off = 0
    for x in inputs:
        a = guard._decide_quiet(x).action
        b = gated._decide_quiet(x).action
        v = og.lm_beam_direction(gated._last_lp, readout)
        if a == "offer":
            assert b == ("offer" if v >= 0 else "withhold")
        else:
            assert b == a  # a COMMIT or a WITHHOLD never changes
        n_off += b == "offer"
        rv = gated._decide_quiet(np.ascontiguousarray(x[::-1]))
        n_rev_off += rv.action == "offer"
    assert n_rev_off == 0
    assert guard.offer_gates == base


def test_collect_features_and_lazy_gates(guard, readout, inputs, monkeypatch):
    gated = ft.TrustGuard(guard.config, guard._codec, guard.sheet)
    gated.collect_offer_features = True
    gated._decide_quiet(inputs[0])
    assert "lm_beam_direction" not in gated.last_offer_features  # no readout: not computed
    gated.offer_readout = readout
    gated._decide_quiet(inputs[0])
    assert gated.last_offer_features["lm_beam_direction"] == pytest.approx(
        og.lm_beam_direction(gated._last_lp, readout), abs=1e-12)
    # a first gate that fails: the costly feature is not computed (lazy features)
    calls = []
    real = og.lm_beam_direction
    monkeypatch.setattr(og, "lm_beam_direction", lambda *a, **k: calls.append(1) or real(*a, **k))
    g2 = ft.TrustGuard(guard.config, guard._codec, guard.sheet,
                       offer_gate=[OfferGate("coherence", 1e9), OfferGate("lm_beam_direction", 0.0, lm_name="toy",
                                                                           readout=readout)])
    for x in inputs[:5]:
        assert g2._decide_quiet(x).action != "offer"
    assert calls == []
