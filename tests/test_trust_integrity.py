"""Tests of the P5-36 frame-order integrity check (fidetype.trust.integrity, TrustGuard frame_times=) and the
``lm_direction`` offer-gate feature (fidetype.trust.offer_gate)."""

from __future__ import annotations

import json

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.lm.ngram import CharNgramLM
from fidetype.trust import integrity as I
from fidetype.trust import offer_gate as og
from fidetype.trust.offer_gate import OfferGate

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits

P = 0.01  # frame period of the synthetic streams (s)


def _times(T, period=P):
    return period + period * np.arange(T)


def _reversed(t):
    return t[::-1].copy()


def _reordered(t, rng):
    """Two adjacent frames swapped (the smallest reorder)."""
    t = t.copy()
    k = int(rng.integers(0, len(t) - 1))
    t[k], t[k + 1] = t[k + 1], t[k]
    return t


def _duplicated(t, rng):
    """One frame sent twice (same time)."""
    k = int(rng.integers(0, len(t)))
    return np.insert(t, k + 1, t[k])


def _jittered(t, rng, frac=0.4):
    """Real-like clock jitter: each time moves by up to +-frac of a period (order kept for frac < 0.5)."""
    return t + rng.uniform(-frac, frac, len(t)) * P


# --- the check function ------------------------------------------------------------------------------------


def test_check_codes():
    t = _times(100)
    assert I.check_frame_times(t).ok and I.check_frame_times(t, 100).ok
    assert I.check_frame_times(t[:0]).ok and I.check_frame_times(t[:1]).ok
    r = I.check_frame_times(_reversed(t))
    assert (r.ok, r.code, r.n_bad, r.first_bad) == (False, "frame_order_reversed", 99, 0)
    s = t.copy()
    s[10], s[11] = s[11], s[10]
    r = I.check_frame_times(s)
    assert (r.code, r.first_bad) == ("frame_order", 10)
    r = I.check_frame_times(np.insert(t, 31, t[30]))
    assert (r.code, r.first_bad, r.n_bad) == ("frame_duplicate", 30, 1)
    bad = t.copy()
    bad[5] = np.nan
    assert I.check_frame_times(bad).code == "frame_times_not_finite"
    assert I.check_frame_times(t, 99).code == "frame_times_shape"
    assert I.check_frame_times(t.reshape(10, 10)).code == "frame_times_shape"
    assert I.check_frame_times(["a", "b"]).code == "frame_times_shape"
    # the order of the codes: order before duplicate
    m = np.array([0.0, 0.01, 0.01, 0.005])
    assert I.check_frame_times(m).code == "frame_order"
    assert set(I.CODES) >= {r.code for r in [I.check_frame_times(_reversed(t))]}


def test_check_tolerances():
    t = _times(50)
    gap = np.concatenate([t[:20], t[25:]])  # 5 frames dropped
    assert I.check_frame_times(gap).ok  # gaps are allowed by default (TIM-2 only)
    r = I.check_frame_times(gap, max_step=1.5 * P)
    assert (r.code, r.first_bad) == ("frame_gap", 19)
    # min_step: a step at or below it is a repeated time
    close = t.copy()
    close[20] = close[19] + 0.0005
    assert I.check_frame_times(close).ok
    assert I.check_frame_times(close, min_step=0.001).code == "frame_duplicate"
    with pytest.raises(ValueError):
        I.check_frame_times(t, min_step=-1.0)
    with pytest.raises(ValueError):
        I.check_frame_times(t, min_step=0.01, max_step=0.005)


def test_report_and_events():
    t = _times(20)
    r = I.check_frame_times(_reversed(t))
    d = json.loads(json.dumps(r.to_dict()))
    assert d["schema"] == I.INTEGRITY_SCHEMA and d["code"] == "frame_order_reversed" and not d["ok"]
    assert r.reason().startswith(I.REASON_PREFIX) and "frame_order_reversed" in r.reason()
    assert I.check_frame_times(t).reason() == ""
    ev = [{"type": "header"}] + [{"type": "frame", "t": float(x), "log_probs": [0.0]} for x in t] + [{"type": "end"}]
    assert I.check_events(ev).ok
    assert I.check_events([ev[0]] + ev[1:-1][::-1] + [ev[-1]]).code == "frame_order_reversed"
    ev[3] = dict(ev[3], t=True)
    assert I.check_events(ev).code == "frame_times_not_finite"
    assert ft.check_frame_times is I.check_frame_times and ft.IntegrityReport is I.IntegrityReport


def test_synthetic_streams_flagged_100_percent_real_0():
    """The P5-36 synthetic rule: reversed, reordered and duplicated streams 100 % flagged; real-like 0 %."""
    rng = np.random.default_rng(36)
    n = 500
    for _ in range(n):
        t = _times(int(rng.integers(2, 400)))
        assert I.check_frame_times(_reversed(t)).code in ("frame_order_reversed", "frame_order") or len(t) < 2
        assert not I.check_frame_times(_reversed(t)).ok
        assert I.check_frame_times(_reordered(t, rng)).code in ("frame_order", "frame_order_reversed")
        assert I.check_frame_times(_duplicated(t, rng)).code == "frame_duplicate"
        assert I.check_frame_times(t).ok
        assert I.check_frame_times(_jittered(t, rng)).ok


# --- the guard -----------------------------------------------------------------------------------------------


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


def _strip(r):
    ev = {k: v for k, v in r.event.items() if k != "integrity"}
    return (r.action, r.text, r.choices, r.p_top1, r.guard_risk, r.reason, r.raw_action, r.config_id, ev)


def test_valid_times_change_nothing(guard, inputs):
    cid = guard.config_id
    rng = np.random.default_rng(5)
    for x in inputs:
        a = guard.decide(x)
        b = guard.decide(x, frame_times=_times(len(x)))
        c = guard.decide(x, frame_times=_jittered(_times(len(x)), rng))
        assert _strip(a)[:-1] == _strip(b)[:-1] == _strip(c)[:-1]
        assert {k: v for k, v in a.event.items() if k not in ("seq", "latency_s", "utterance")} == \
            {k: v for k, v in _strip(b)[-1].items() if k not in ("seq", "latency_s", "utterance")}
        assert b.event["integrity"]["ok"] and "integrity" not in a.event
        assert guard.last_integrity.ok
    assert guard.config_id == cid
    assert guard.audit_log[-1]["integrity"]["ok"] is True


def test_bad_times_withhold_every_action(guard, inputs):
    rng = np.random.default_rng(6)
    acts = set()
    for x in inputs:
        base = guard.decide(x).action
        acts.add(base)
        t = _times(len(x))
        for bad, code in ((_reversed(t), "frame_order_reversed"), (_reordered(t, rng), "frame_order")):
            r = guard.decide(x, frame_times=bad)
            assert r.action == "withhold" and r.text is None and r.choices == ()
            assert r.raw_action == "ABSTAIN" and r.reason.startswith(I.REASON_PREFIX) and code in r.reason
            assert guard.audit_log[-1]["integrity"]["code"] == code
            assert guard.audit_log[-1]["user_action"] == "withhold"
            assert r.config_id == guard.config_id
    assert "commit" in acts  # a commit is also stopped
    # a duplicated frame: the times belong to one more row than the input has
    x = inputs[0]
    k = 7
    x2 = np.insert(x, k + 1, x[k], axis=0)
    r = guard.decide(x2, frame_times=np.insert(_times(len(x)), k + 1, _times(len(x))[k]))
    assert r.action == "withhold" and "frame_duplicate" in r.reason
    r = guard.decide(x, frame_times=_times(len(x) + 1))
    assert r.action == "withhold" and "frame_times_shape" in r.reason


def test_session_with_times(guard, inputs):
    x = inputs[1]
    t = _times(len(x))
    ref = guard.decide(x)
    s = guard.session()
    for i in range(0, len(x), 9):
        s.push(x[i:i + 9], times=t[i:i + 9])
    r = s.end()
    assert _strip(r)[:-1] == _strip(ref)[:-1] and r.event["integrity"]["ok"]
    s = guard.session()
    for i in range(0, len(x), 9):
        s.push(x[i:i + 9], times=_reversed(t)[i:i + 9])
    r = s.end()
    assert r.action == "withhold" and "frame_order_reversed" in r.reason
    s = guard.session()
    s.push(x[:5], times=t[:5])
    with pytest.raises(ValueError, match="every chunk"):
        s.push(x[5:10])
    s = guard.session()
    with pytest.raises(ValueError, match="one value per row"):
        s.push(x[:5], times=t[:4])
    s = guard.session()  # no times: the old path, no integrity record
    s.push(x)
    assert "integrity" not in s.end().event


def test_nbest_guard_refuses_times():
    from test_trust_dropin import nbest_data, noise_nbest

    xs, ts = nbest_data(200, 0)
    rng = np.random.default_rng(1)
    g = ft.calibrate(xs, ts, null_inputs=[noise_nbest(rng) for _ in range(40)], null_trials=40,
                     decoder_name="test-nbest", modality="emg")
    with pytest.raises(ValueError, match="logits"):
        g.decide(xs[0], frame_times=[0.0])


# --- lm_direction ----------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lm() -> CharNgramLM:
    return CharNgramLM(order=4).train(PHRASES * 20)


def test_lm_direction_is_antisymmetric(lm, inputs):
    vocab = VOCAB
    for x in inputs:
        lp = x - np.log(np.exp(x).sum(1, keepdims=True))
        f = og.lm_direction(lp, vocab, lm, blank=0)
        r = og.lm_direction(np.ascontiguousarray(lp[::-1]), vocab, lm, blank=0)
        assert f == pytest.approx(-r, abs=1e-9)
        assert og.greedy_text(lp[::-1], vocab, 0) == og.greedy_text(lp, vocab, 0)[::-1]
        assert f > 0  # forward English-like phrases read better forward
    assert og.lm_direction(np.log(np.full((5, len(vocab)), 1 / len(vocab))), vocab, lm, blank=0) == 0.0
    assert og.lm_direction(np.zeros((0, len(vocab))), vocab, lm, blank=0) == 0.0


def test_lm_direction_gate_in_the_guard(guard, inputs, lm):
    g = OfferGate("lm_direction", 0.0, lm_name="toy", lm=lm)
    g.check_kind("logits")
    with pytest.raises(ValueError, match="lm_name"):
        OfferGate("lm_direction", 0.0)
    with pytest.raises(ValueError, match="needs the character LM"):
        OfferGate("lm_direction", 0.0, lm_name="toy").check_kind("logits")
    gated = ft.TrustGuard(guard.config, guard._codec, guard.sheet, offer_gate=g)
    assert gated.config_id == guard.config_id
    gated.collect_offer_features = True
    n_rev_offer = 0
    for x in inputs:
        a = guard._decide_quiet(x).action
        b = gated._decide_quiet(x).action
        v = gated.last_offer_features["lm_direction"]
        if a == "offer":
            assert b == ("offer" if v >= 0 else "withhold")
        else:
            assert b == a
        rv = gated._decide_quiet(np.ascontiguousarray(x[::-1]))
        n_rev_offer += rv.action == "offer"
        assert gated.last_offer_features["lm_direction"] == pytest.approx(-v, abs=1e-9)
    assert n_rev_offer == 0
