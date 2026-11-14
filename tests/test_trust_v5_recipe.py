"""Trust v5 candidate recipe (P5-07): switches, selection rule, floor, gate, offer-only. Synthetic data only."""

from __future__ import annotations

import itertools
import math
from dataclasses import asdict

import numpy as np
import pytest

from fidetype.conformance.vectors import _header
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust import recipe_v5 as V
from fidetype.trust.content import CommitGate, GatedPolicy
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig
from fidetype.trust.guard import uniform_stream
from fidetype.trust.policy import DEFAULT_GRID, Action, DecisionPolicy, PolicyConfig, PolicyInputs, fit_thresholds
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, replay
from fidetype.trust.testing import greedy_nbest
from fidetype.trust.types import Candidate, NBest


def test_v4_recipe_untouched_and_v5_is_a_new_record():
    assert PAPER1_V4_RECIPE["name"] == "paper1-v4-frozen-config"
    assert PAPER1_V4_RECIPE["commit_threshold"] == "max(grid commit_p, LTT lambda_hat)"
    r = V.TRUST_V5_CANDIDATE
    assert r["name"] == "trust-v5-candidate" and r["base"] == "paper1-v4-frozen-config"
    assert r["commit_gate"] == V.GATE_B and r["declaration_check"] == "offer-only"
    assert r["commit_max_risk_grid"] == [0.1, 0.2, 0.3, 0.5, 1.0]
    assert V.v5_recipe(V.V5Options(max_risk_grid="no-1.0"))["commit_max_risk_grid"] == [0.1, 0.2, 0.3, 0.5, 0.8]
    assert V.v5_recipe(V.V5Options(commit_gate=False))["name"] == "trust-v5-candidate-variant"
    for bad in (dict(max_risk_grid="x"), dict(declaration_check="strict"), dict(control_limit=1.0), dict(n_control=0)):
        with pytest.raises(ValueError):
            V.V5Options(**bad)
    assert V.V5Options().grid()["commit_max_risk"] == DEFAULT_GRID["commit_max_risk"]


def _random_inputs(n: int, seed: int) -> list[PolicyInputs]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        k = int(rng.integers(0, 4))
        texts = tuple(("" if (i % 7 == 0 and j == 0) else f"w{i}{j}") for j in range(k))
        risk = float(rng.choice([0.0, 0.05, 0.2, 0.5, 0.9, 1.0]))
        out.append(PolicyInputs(texts=texts, p_top1=float(rng.uniform()), set_indices=tuple(range(min(k, 2))),
                                guard_risk=risk))
    return out


@pytest.mark.parametrize("use_guard", [True, False])
@pytest.mark.parametrize("gate", [None, CommitGate(1, 0, 1.0)])
def test_input_arrays_match_the_policy(use_guard, gate):
    xs = _random_inputs(300, 1)
    arr = V.InputArrays(xs, use_guard, gate)
    grid = dict(DEFAULT_GRID, commit_max_set=(None, 1))
    for vals in itertools.islice(itertools.product(*grid.values()), 0, None, 37):
        pc = PolicyConfig(**dict(zip(grid, vals)))
        pol = GatedPolicy.wrap(DecisionPolicy(pc, use_guard), gate) if gate else DecisionPolicy(pc, use_guard)
        want = np.array([pol.decide(x, final_attempt=True).action == Action.COMMIT for x in xs])
        assert (arr.commits(pc) == want).all()


def _toy_table():
    rng = np.random.default_rng(5)
    grid = {"commit_p": (0.3, 0.6, 1.01), "commit_max_risk": (0.1, 0.5, 0.8, 1.0), "offer_max_k": (1, 3)}

    def ev(pc):
        k = (pc.commit_p, pc.commit_max_risk, pc.offer_max_k)
        r = np.random.default_rng(abs(hash(k)) % 2**32)
        wc = 0.0 if pc.commit_p > 1 else float(r.uniform(0, 0.08))
        return {"ewpm": float(r.uniform(5, 10)) + (0 if pc.commit_p > 1 else 2 * pc.commit_max_risk),
                "wrong_commit_rate": wc}
    del rng
    return grid, ev


def test_select_policy_equals_fit_thresholds_on_the_v4_values():
    grid, ev = _toy_table()
    full = fit_thresholds(ev, grid, 0.05, keep_table=True)
    v4_grid = dict(grid, commit_max_risk=(0.1, 0.5, 1.0))
    ref = fit_thresholds(ev, v4_grid, 0.05)
    cfg, m, ok = V.select_policy(full.table, 0.05, max_risk_values=(0.1, 0.5, 1.0))
    assert ok and cfg == asdict(ref.config)
    cfg_all, _, _ = V.select_policy(full.table, 0.05)
    assert cfg_all == asdict(full.config)


def test_control_aware_selection_excludes_points_that_commit_on_controls():
    grid, ev = _toy_table()
    table = fit_thresholds(ev, grid, 0.05, keep_table=True).table
    # 100 control inputs: confident, guard risk 0.7 -> committed by commit_max_risk >= 0.8 with commit_p <= 0.6
    ctl = {"uniform": V.InputArrays([PolicyInputs(("x",), 0.9, (0,), guard_risk=0.7)] * 100)}
    cfg, _, ok = V.select_policy(table, 0.05, ctl, 0.01)
    assert ok
    assert cfg["commit_max_risk"] < 0.7 or cfg["commit_p"] > 0.9
    assert all(r <= 0.01 for r in V.control_rates(ctl, cfg).values())


def test_reference_floor():
    xs = [PolicyInputs(("a",), p, (0,), guard_risk=0.1) for p in np.linspace(0.0, 0.99, 100)]
    ref = {"uniform": V.InputArrays(xs)}
    cfg = PolicyConfig(commit_p=0.3, commit_max_risk=0.5, abstain_risk=1.01)
    fl = V.reference_floor(ref, cfg, 0.01)  # 1 commit allowed of 100: lam just above the 2nd largest p (0.98)
    assert fl == pytest.approx(0.99)
    assert (V.InputArrays(xs).commits(PolicyConfig(commit_p=fl, commit_max_risk=0.5)).sum()) <= 1
    assert V.reference_floor(ref, PolicyConfig(commit_max_risk=0.05), 0.01) == -math.inf  # nothing eligible
    sure = {"zero_standin": V.InputArrays([PolicyInputs(("a",), 1.0, (0,))] * 10)}
    assert V.reference_floor(sure, cfg, 0.01) == math.inf  # p = 1.0 on no-signal input: never commit


def test_control_copies():
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=1)
    ss = [sim.simulate(s, seed=i).stream for i, s in enumerate(sentences(12, seed=1))]
    c = V.control_copies(ss, V.V5Options(n_control=5))
    assert set(c) == set(V.CONTROL_KINDS) and all(len(v) == 5 for v in c.values())
    z = c["zero_standin"][0].log_probs
    assert np.allclose(z, z[:1])
    c2 = V.control_copies(ss, V.V5Options(n_control=5))
    assert np.array_equal(c["uniform"][3].log_probs, c2["uniform"][3].log_probs)  # seeded


def _lexicon_decoder(lexicon):
    def decode(stream):
        top = greedy_nbest(stream).top
        text = " ".join(w for w in (top.text if top else "").split() if w in lexicon)
        return NBest([Candidate(text, 0.0)])
    return decode


@pytest.fixture(scope="module")
def toy():
    sents = sentences(90, seed=4)
    lex = {w for s in sents for w in s.split()}
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=4)
    items = [Item(sim.simulate(s, seed=i).stream, s) for i, s in enumerate(sents)]
    return _lexicon_decoder(lex), items[:40], items[40:70], items[70:]


def test_fit_trust_v5_end_to_end(toy):
    dec, fit, cal, test = toy
    pipe = V.fit_trust_v5(dec, fit, cal, V.V5Options(n_control=30), max_attempts=1)
    assert isinstance(pipe.policy, GatedPolicy) and pipe.policy.gate == CommitGate(**V.GATE_B)
    fr = pipe.fit_report
    assert fr["risk_control_method"].startswith("ltt")
    assert fr["v5_commit_p"] >= fr["risk_control_threshold"] or math.isinf(fr["v5_commit_p"])
    assert all(r <= 0.01 for r in fr["v5_control_rates_at_grid"].values())
    # no empty commit on uniform input (the toy decoder collapses to "" there)
    rng = np.random.default_rng(0)
    uni = [Item(uniform_stream(it.stream(0), rng, 0.05), it.text) for it in test]
    recs = pipe.run_items(uni, pipe.policy, {})
    assert not any(r.committed_text is not None for r in recs)
    fz = V.freeze_v5(pipe, "toy-v5")
    assert fz.recipe["name"] == "trust-v5-candidate" and fz.commit_gate == V.GATE_B
    assert FrozenTrustConfig.from_dict(fz.to_dict()).config_id == fz.config_id
    fz4 = FrozenTrustConfig.from_pipeline(pipe, name="toy-v5", recipe=PAPER1_V4_RECIPE)
    assert fz4.config_id != fz.config_id  # own config id


def test_v5_switches_off_give_the_v4_grid_choice(toy):
    dec, fit, cal, test = toy
    off = V.V5Options(commit_gate=False, control_aware_fit=False, no_signal_reference=False, n_control=10)
    p5 = V.V5Pipeline(dec, V.trust_v5_harness_config(off, max_attempts=1), {}, off)
    p5.fit(fit, fit)
    p4 = TrustPipeline(dec, HarnessConfig(use_guard=True, max_wrong_commit=0.05, max_attempts=1), {})
    p4.fit(fit, fit)
    assert type(p5.policy) is DecisionPolicy and p5.policy.config == p4.policy.config


def test_keep_item_outcomes(toy):
    dec, fit, _, _ = toy
    o = V.V5Options(n_control=10)
    p = V.V5Pipeline(dec, V.trust_v5_harness_config(o, max_attempts=1, grid=dict(DEFAULT_GRID, offer_max_k=(1,),
                                                                                    final_fallback=("offer",))), {}, o)
    p.keep_item_outcomes = True
    p.fit(fit, fit)
    assert len(p.fit_outcomes) == len(p.fit_table)
    for (cfg, m), o_ in itertools.islice(zip(p.fit_table, p.fit_outcomes), 0, None, 7):
        assert o_["wrong_commit"].mean() == pytest.approx(m["wrong_commit_rate"])
        assert 60 * o_["words"].sum() / o_["time_s"].sum() == pytest.approx(m["ewpm"])


# --- (e) declaration check "offer-only" -------------------------------------------------

CFG = FrozenTrustConfig(name="v5-decl-test", frame_temperature=1.25).with_policy(
    commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01, offer_max_k=3)


def _hyp(text="ab"):
    return {"type": "hypothesis", "id": "h1", "is_final": True, "score_semantics": "none",
            "nbest": [{"text": text, "score": -1.0, "char_confidences": [0.9] * len(text)},
                      {"text": text + "c", "score": -1.6}]}


def _run(cfg, decl, mode):
    layer = StreamingTrustLayer(cfg, streaming=StreamingConfig(declaration_check=mode))
    (d,) = replay([_header(decode_declaration=decl), _hyp()], layer)
    return d


def test_declaration_offer_only_blocks_commit_and_keeps_offer():
    good = {"decoder": "acme", "frame_temperature": 1.25}
    bad = {"decoder": "acme"}  # no temperature = 1.0: mismatch
    base = _run(CFG, good, "offer-only")
    assert base.action == Action.COMMIT  # a match changes nothing
    assert _run(CFG, bad, "warn").action == Action.COMMIT
    assert _run(CFG, bad, "abstain").action == Action.ABSTAIN
    o = _run(CFG, bad, "offer-only")
    assert o.action in (Action.OFFER, Action.ASK) and o.action != Action.COMMIT
    assert o.decision.reason.startswith("decode declaration mismatch (offer-only)")
    assert o.provenance["declaration"]["status"] == "mismatch" and o.provenance["declaration"]["mode"] == "offer-only"
    assert o.provenance["commit_threshold"] is None or o.provenance["commit_threshold"] in ("inf", math.inf)
    # gated v5-style config: same behaviour
    g = CFG.with_commit_gate(**V.GATE_B)
    assert _run(g, bad, "offer-only").action != Action.COMMIT
    always = FrozenTrustConfig(name="ac", frame_temperature=1.25, policy_class="always_commit")
    assert _run(always, bad, "offer-only").action == Action.ABSTAIN
    assert V.V5Options().streaming_config().declaration_check == "offer-only"
