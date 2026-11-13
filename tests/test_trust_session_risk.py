"""A2: per-session risk control (fidetype.trust.session_risk). Synthetic data only."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fidetype.trust.risk_control import ltt_threshold
from fidetype.trust.session_risk import (
    SessionRiskMonitor,
    beta_cdf,
    binomial_upper_pvalue,
    block_ltt,
    block_test,
    eb_session_threshold,
    first_alarm,
    fit_beta_prior,
    min_ltt_items,
    mondrian_ltt,
)


def _session(rng, n, risk_at, grid_lo=0.0):
    """Synthetic session: scores U(0, 1); a commit at score s is wrong with prob risk_at(s)."""
    s = rng.uniform(grid_lo, 1.0, n)
    c = (rng.uniform(size=n) < np.vectorize(risk_at)(s)).astype(float)
    return s, c


# --- sample-size floor and p-values ---------------------------------------------


def test_min_ltt_items_matches_ltt():
    assert min_ltt_items(0.05, 0.1) == 45
    assert min_ltt_items(0.05, 0.05) == 59
    for n, ok in ((44, False), (45, True)):
        r = ltt_threshold(np.ones(n), np.zeros(n), 0.05, 0.1, grid=(1.0, 0.5))
        assert r.feasible is ok


def test_binomial_upper_pvalue_bruteforce():
    from math import comb

    for n in (5, 20, 37):
        for k in range(0, n + 1):
            want = sum(comb(n, j) * 0.05**j * 0.95 ** (n - j) for j in range(k, n + 1))
            assert binomial_upper_pvalue(k, n, 0.05) == pytest.approx(min(1.0, want), abs=1e-12)


@pytest.mark.parametrize("a,b", [(1.0, 1.0), (0.5, 3.0), (2.5, 40.0), (12.0, 200.0), (300.0, 5.0)])
def test_beta_cdf_against_quadrature(a, b):
    for x in (0.01, 0.05, 0.3, 0.9):
        t = np.linspace(0.0, x, 200001)[1:]
        logpdf = (a - 1) * np.log(t) + (b - 1) * np.log1p(-t) + math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        num = float(np.trapezoid(np.exp(logpdf), t)) if a >= 1 else None
        got = beta_cdf(x, a, b)
        assert 0.0 <= got <= 1.0
        if num is not None:
            assert got == pytest.approx(num, abs=2e-4)
    assert beta_cdf(0.3, 1.0, 1.0) == pytest.approx(0.3)
    assert beta_cdf(0.0, 2, 2) == 0.0 and beta_cdf(1.0, 2, 2) == 1.0


def test_fit_beta_prior():
    a, b = fit_beta_prior([(5, 100)] * 10)  # no extra spread -> max concentration
    assert a / (a + b) == pytest.approx(0.05) and a + b == pytest.approx(100.0)
    a, b = fit_beta_prior([(0, 100), (30, 100), (2, 100), (25, 100)])  # strong spread -> low concentration
    assert a + b < 20
    with pytest.raises(ValueError):
        fit_beta_prior([])


# --- Mondrian LTT ------------------------------------------------------------------


def test_mondrian_fallbacks_and_guarantee_flags():
    rng = np.random.default_rng(1)
    s1, c1 = _session(rng, 200, lambda s: 0.3 * (1 - s))
    s2, c2 = _session(rng, 20, lambda s: 0.3 * (1 - s))
    s = np.concatenate([s1, s2])
    c = np.concatenate([c1, c2])
    g = ["big"] * 200 + ["small"] * 20
    out = mondrian_ltt(s, c, g, fallback="never")
    assert out["big"].source == "group" and out["big"].per_group_guarantee
    assert math.isfinite(out["big"].threshold)
    assert out["small"].source == "fallback-never" and out["small"].threshold == math.inf
    out = mondrian_ltt(s, c, g, fallback="global", base_threshold=0.2)
    assert out["small"].source == "fallback-global" and not out["small"].per_group_guarantee
    assert out["small"].threshold >= 0.2
    pooled = ltt_threshold(s, c, 0.05, 0.1).threshold
    assert out["small"].threshold == pytest.approx(max(0.2, pooled))
    out = mondrian_ltt(s, c, g, fallback="mixture")
    assert out["small"].source == "fallback-mixture"
    assert out["small"].threshold >= pooled  # level alpha * pi is stricter
    with pytest.raises(ValueError):
        mondrian_ltt(s, c, g[:-1])


def test_mondrian_per_group_coverage_on_heterogeneous_groups():
    """The pooled rule fails on the bad group; Mondrian LTT holds it at alpha with prob >= 1 - delta."""
    rng = np.random.default_rng(2)
    bad = lambda s: 0.25 * (1 - s) ** 0.5  # noqa: E731
    good = lambda s: 0.04 * (1 - s)  # noqa: E731
    fail_pooled = fail_mon = 0
    R = 150
    for _ in range(R):
        sb, cb = _session(rng, 120, bad)
        sg, cg = _session(rng, 1200, good)
        s = np.concatenate([sb, sg])
        c = np.concatenate([cb, cg])
        g = np.array(["bad"] * 120 + ["good"] * 1200, dtype=object)
        lam_pool = ltt_threshold(s, c).threshold
        lam_bad = mondrian_ltt(s, c, g)["bad"].threshold
        # true risk of the bad group at a threshold (fresh large sample)
        st, ct = _session(rng, 20000, bad)
        fail_pooled += float(np.mean(np.where(st >= lam_pool, ct, 0))) > 0.05
        fail_mon += float(np.mean(np.where(st >= lam_bad, ct, 0))) > 0.05
    assert fail_pooled / R > 0.5
    assert fail_mon / R <= 0.1 + 0.05


# --- session-start block -------------------------------------------------------------


def test_block_ltt_needs_min_items_and_only_gets_stricter():
    zeros = np.zeros(44)
    r = block_ltt(np.ones(44), zeros, base_threshold=0.3)
    assert r.threshold == math.inf and r.block_threshold == math.inf
    r = block_ltt(np.ones(80) * 0.9, np.zeros(80), base_threshold=0.3)
    assert r.threshold == pytest.approx(0.3)  # block threshold looser -> base wins
    assert r.block_threshold <= 0.3
    r = block_ltt(np.ones(80) * 0.9, np.zeros(80), base_threshold=0.95)
    assert r.threshold == pytest.approx(0.95)
    assert "per-session" in r.guarantee
    r = block_ltt([], [], base_threshold=0.5)
    assert r.threshold == math.inf and r.n_block == 0


def test_block_test_exact_and_hoeffding():
    s = np.ones(20)
    c = np.zeros(20)
    c[:4] = 1
    t = block_test(s, c, threshold=0.5, alpha=0.05, gamma=0.1)
    assert t.p_value == pytest.approx(binomial_upper_pvalue(4, 20, 0.05))
    assert t.reject and t.risk_hat == pytest.approx(0.2)
    t = block_test(s, c, threshold=2.0)  # nothing commits -> loss 0
    assert not t.reject and t.p_value == 1.0
    t = block_test(s, np.full(20, 0.5), threshold=0.5)  # non-binary loss -> Hoeffding
    assert t.p_value == pytest.approx(math.exp(-2 * 20 * 0.45**2))
    assert block_test([], [], 0.5).n == 0


def test_block_ltt_coverage_simulation():
    """Exchangeable session: block LTT (k = 80) keeps the session risk <= alpha w.p. >= 1 - delta."""
    rng = np.random.default_rng(3)
    risk = lambda s: 0.2 * (1 - s)  # noqa: E731
    st, ct = _session(rng, 50000, risk)
    fails = 0
    R = 200
    for _ in range(R):
        sb, cb = _session(rng, 80, risk)
        lam = block_ltt(sb, cb).threshold
        fails += float(np.mean(np.where(st >= lam, ct, 0))) > 0.05
    assert fails / R <= 0.1 + 0.05


# --- online monitor --------------------------------------------------------------------


def test_monitor_false_alarm_rate_under_null():
    rng = np.random.default_rng(4)
    R, T, gamma = 1500, 300, 0.1
    alarms = sum(first_alarm(rng.uniform(size=T) < 0.05, 0.05, gamma) is not None for _ in range(R))
    assert alarms / R <= gamma  # Ville: P(sup K_t >= 1/gamma) <= gamma (here far below)


def test_monitor_detects_bad_session_and_is_absorbing():
    rng = np.random.default_rng(5)
    delays = [first_alarm(rng.uniform(size=400) < 0.3, 0.05, 0.1) for _ in range(200)]
    assert all(d is not None for d in delays)
    assert np.median(delays) < 30
    mon = SessionRiskMonitor(alpha=0.05, gamma=0.1)
    for _ in range(10):
        mon.update(1.0)
    assert mon.alarmed and mon.alarm_at is not None
    at = mon.alarm_at
    assert mon.update(0.0) and mon.alarm_at == at and mon.n == at  # absorbing, no more updates
    st = mon.state()
    assert st["alarm"] and st["e_value"] >= 10
    mon.reset()
    assert not mon.alarmed and mon.e_value == pytest.approx(1.0)


def test_monitor_missing_and_validation():
    mon = SessionRiskMonitor(missing="skip")
    assert not mon.update(None) and mon.n == 0 and mon.n_missing == 1
    mon = SessionRiskMonitor(missing="pessimistic")
    mon.update(None)
    assert mon.n == 1 and mon.sum_loss == 1.0
    for kw in ({"alpha": 0.0}, {"gamma": 1.0}, {"alternatives": (0.04,)}, {"max_bet_fraction": 1.0},
               {"missing": "drop"}):
        with pytest.raises(ValueError):
            SessionRiskMonitor(**kw)
    with pytest.raises(ValueError):
        SessionRiskMonitor().update(1.5)
    # bets are Kelly bets, capped at max_bet_fraction / alpha
    b = SessionRiskMonitor(alternatives=(0.1, 0.9)).bets
    assert b[0] == pytest.approx(0.05 / (0.05 * 0.95)) and b[1] == pytest.approx(0.5 / 0.05)


def test_first_alarm_equals_monitor():
    rng = np.random.default_rng(6)
    x = (rng.uniform(size=200) < 0.15).astype(float)
    mon = SessionRiskMonitor()
    at = None
    for v in x:
        if mon.update(v):
            at = mon.alarm_at
            break
    assert first_alarm(x) == at


# --- empirical-Bayes shrinkage ---------------------------------------------------------


def test_eb_threshold_shrinks_and_is_labelled():
    rng = np.random.default_rng(7)
    good = lambda s: 0.06 * (1 - s)  # noqa: E731
    refs = [(*_session(rng, 60, good), None) for _ in range(12)]
    # all reference sessions good, empty block: the prior alone allows the base threshold
    r = eb_session_threshold([], [], reference=refs, base_threshold=0.5)
    assert r.threshold == pytest.approx(0.5) and "no finite-sample" in r.guarantee
    # a bad block raises the threshold above the base
    sb = np.full(15, 0.6)
    cb = np.zeros(15)
    cb[:5] = 1
    r2 = eb_session_threshold(sb, cb, reference=refs, base_threshold=0.5)
    assert r2.threshold > 0.6
    # heterogeneous references make even k = 0 stricter than the base
    bad = lambda s: 0.5 * (1 - s)  # noqa: E731
    het = refs[:6] + [(*_session(rng, 60, bad), None) for _ in range(6)]
    r3 = eb_session_threshold([], [], reference=het, base_threshold=0.5)
    assert r3.threshold > 0.5
    # a fixed prior works too; exactly one of reference / prior
    r4 = eb_session_threshold(sb, cb, prior=(1.0, 19.0), base_threshold=0.0)
    assert r4.threshold > 0.6
    with pytest.raises(ValueError):
        eb_session_threshold([], [], base_threshold=0.5)


# --- StreamingTrustLayer opt-in policy -------------------------------------------------


@pytest.fixture(scope="module")
def stream_setup():
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.testing import RefCharLM, ReferenceDecoder

    sents = sentences(500, seed=21)
    lm = RefCharLM(5).fit(sents[80:])
    dec = ReferenceDecoder(lm, beam=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=7)
    items = [Item(sim.simulate(s, seed=31 * i).stream, s) for i, s in enumerate(sents[:60])]
    grid = {"commit_p": (0.5, 0.8), "commit_max_risk": (1.0,), "offer_max_k": (3,), "abstain_risk": (1.01,),
            "final_fallback": ("offer",)}
    pipe = TrustPipeline(dec, HarnessConfig(grid=grid, max_wrong_commit=0.1), {})
    pipe.fit(items[:20], items[20:40])
    # A loose gate: (almost) every final decision is a COMMIT.
    cfg = FrozenTrustConfig.from_pipeline(pipe).with_policy(commit_p=0.0, commit_max_risk=1.0, abstain_risk=1.01)
    return dec, cfg, items[40:]


def _run(layer, items, tmp_path, truth_fn, sid="u"):
    from fidetype.conformance.io import write_jsonl
    from fidetype.trust.streaming import replay

    out = []
    for i, it in enumerate(items):
        p = tmp_path / f"{sid}{i}.jsonl"
        write_jsonl(it.stream(0), p)
        (d,) = [x for x in replay(p, layer, session_id=sid) if x.final]
        layer.feedback(d, truth_fn(d, it))
        out.append(d)
    return out


def test_streaming_session_risk_default_off(stream_setup, tmp_path):
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    dec, cfg, items = stream_setup
    layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=1))
    ds = _run(layer, items[:3], tmp_path, lambda d, it: it.text)
    assert all("session_risk" not in d.provenance for d in ds)
    assert layer.session_state("u")["session_risk"] is None


def test_streaming_session_risk_alarm_switches_to_offer_only(stream_setup, tmp_path):
    from fidetype.trust.policy import Action
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    dec, cfg, items = stream_setup
    mon = SessionRiskMonitor(alpha=0.05, gamma=0.1)
    layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=1), session_risk=mon)
    # Every committed text is reported wrong (the user retypes something else).
    ds = _run(layer, items, tmp_path, lambda d, it: "zz " + it.text)
    first = [d.action for d in ds]
    assert first[0] == Action.COMMIT
    st = layer.session_state("u")["session_risk"]
    assert st["alarm"] and st["alarm_at"] <= 5
    k = st["alarm_at"]
    assert all(a != Action.COMMIT for a in first[k:])  # offer-only after the alarm
    assert ds[k].provenance["session_risk"]["alarm"] and ds[k].provenance["commit_threshold"] is None
    assert mon.n == 0 and not mon.alarmed  # the template is not shared
    # another session starts fresh
    ds2 = _run(layer, items[:2], tmp_path, lambda d, it: it.text, sid="v")
    assert ds2[0].action == Action.COMMIT and not layer.session_state("v")["session_risk"]["alarm"]


def test_streaming_session_risk_good_session_no_alarm(stream_setup, tmp_path):
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    dec, cfg, items = stream_setup
    layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=1),
                                session_risk=SessionRiskMonitor(alpha=0.05, gamma=0.1))
    # The user keeps every text: realised loss 0.
    ds = _run(layer, items, tmp_path, lambda d, it: d.shown[0] if d.shown else it.text)
    st = layer.session_state("u")["session_risk"]
    assert not st["alarm"] and st["n"] == len(ds) and st["e_value"] < 1.0
