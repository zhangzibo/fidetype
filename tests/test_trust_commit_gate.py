"""M2-18: empty commits under the v4 policy, and the opt-in commit gate.

Synthetic data only. The reproducer: an empty top-1 text gets guard
risk 1.0 (not 0); with ``commit_max_risk = 1.0`` (a value of the
default grid) the guard test ``risk <= commit_max_risk`` is always true,
so the policy COMMITs the empty text when ``p_top1 >= commit_p``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.content import REASON_PREFIX, CommitGate, GatedPolicy, gate_decision, no_commit_policy
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.guard import HallucinationGuard, uniform_stream
from fidetype.trust.policy import DEFAULT_GRID, Action, DecisionPolicy, PolicyConfig, PolicyInputs
from fidetype.trust.risk_control import commit_calibration_data
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, replay
from fidetype.trust.testing import greedy_nbest
from fidetype.trust.types import Candidate, NBest

REPO = Path(__file__).resolve().parents[1]
T12 = REPO / "experiments" / "2026-11-13-confirmatory-t12-v2" / "results"
V4_LIKE = PolicyConfig(commit_p=0.3, commit_max_risk=1.0, offer_max_k=1, abstain_risk=1.01)


def _empty_nbest(n_other: int = 0) -> NBest:
    cands = [Candidate("", 0.0)] + [Candidate(f"w{i}", -5.0 - i, char_confidences=(0.2,) * len(f"w{i}"))
                                    for i in range(n_other)]
    return NBest(cands)


def _inputs(nb: NBest, guard: HallucinationGuard | None = None) -> PolicyInputs:
    post = np.exp(nb.scores - np.logaddexp.reduce(nb.scores))
    g = (guard or HallucinationGuard()).score(nb, post)
    return PolicyInputs(texts=tuple(nb.texts), p_top1=float(post[0]), set_indices=(0,), guard_risk=g.risk)


# --- the mechanism --------------------------------------------------------------------


def test_empty_top1_gets_guard_risk_one_not_zero():
    for k in (0, 3):
        g = HallucinationGuard().score(_empty_nbest(k))
        assert g.risk == 1.0
    assert 1.0 in DEFAULT_GRID["commit_max_risk"]


def test_v4_grid_value_commits_empty_text():
    x = _inputs(_empty_nbest())
    assert x.texts[0] == "" and x.p_top1 == 1.0 and x.guard_risk == 1.0
    d = DecisionPolicy(V4_LIKE).decide(x, final_attempt=True)
    assert d.action == Action.COMMIT and d.shown_candidates == ("",)
    # every other grid value of commit_max_risk blocks it, and so does abstain_risk <= 1
    for cmr in (0.1, 0.2, 0.3, 0.5):
        pc = PolicyConfig(commit_p=0.3, commit_max_risk=cmr, offer_max_k=1, abstain_risk=1.01)
        assert DecisionPolicy(pc).decide(x, final_attempt=True).action != Action.COMMIT
    for ar in (0.6, 0.8):
        pc = PolicyConfig(commit_p=0.3, commit_max_risk=1.0, offer_max_k=1, abstain_risk=ar)
        assert DecisionPolicy(pc).decide(x, final_attempt=True).action == Action.ABSTAIN


def _lexicon_decoder(lexicon):
    """CTC greedy, then drop every word not in the lexicon (a toy word decoder)."""
    def decode(stream):
        top = greedy_nbest(stream).top
        text = " ".join(w for w in (top.text if top else "").split() if w in lexicon)
        return NBest([Candidate(text, 0.0)])
    return decode


@pytest.fixture(scope="module")
def toy():
    sents = sentences(40, seed=3)
    lex = {w for s in sents for w in s.split()}
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=3)
    rng = np.random.default_rng(3)
    real = [Item(sim.simulate(s, seed=i).stream, s) for i, s in enumerate(sents)]
    uni = [Item(uniform_stream(it.stream(0), rng, 0.05), it.text) for it in real]
    return _lexicon_decoder(lex), real, uni


def test_reproducer_uniform_streams_commit_empty_text(toy):
    dec, real, uni = toy
    pipe = TrustPipeline(dec, HarnessConfig(policy_config=V4_LIKE, fit_policy=False, use_calibration=False), {})
    recs = pipe.run_items(uni, DecisionPolicy(V4_LIKE), {})
    empty = [r for r in recs if r.committed_text is not None and r.committed_text.strip() == ""]
    assert len(empty) >= 0.8 * len(uni)  # the toy decoder collapses to "" on no-signal input
    gated = pipe.run_items(uni, GatedPolicy.wrap(DecisionPolicy(V4_LIKE), CommitGate()), {})
    assert not any(r.committed_text is not None and r.committed_text.strip() == "" for r in gated)
    strict = PolicyConfig(commit_p=0.3, commit_max_risk=0.5, offer_max_k=1, abstain_risk=1.01)
    assert not any(r.committed_text == "" for r in pipe.run_items(uni, DecisionPolicy(strict), {}))


# --- the gate -------------------------------------------------------------------------


def test_gate_violations():
    g = CommitGate()
    assert g.violation("") == "empty text" and g.violation("   ") == "empty text"
    assert g.violation("a") is None
    assert CommitGate(3, 0).violation("ab").startswith("2 characters")
    assert CommitGate(1, 2).violation("hello").startswith("1 words")
    assert CommitGate(1, 2).violation("hello you") is None
    assert CommitGate(1, 0, 1.0).violation("hello", 1.0).startswith("guard risk")
    assert CommitGate(1, 0, 1.0).violation("hello", 0.99) is None
    with pytest.raises(ValueError):
        CommitGate(-1)
    with pytest.raises(ValueError):
        CommitGate(1, 0, 1.5)
    with pytest.raises(ValueError):
        CommitGate.from_dict({"min_chars": 1, "bogus": 2})
    assert CommitGate.from_dict(CommitGate(2, 1, 1.0).to_dict()) == CommitGate(2, 1, 1.0)


def test_gated_decision_is_the_no_commit_decision():
    x = _inputs(_empty_nbest())
    pol = DecisionPolicy(V4_LIKE)
    for final in (False, True):
        d = GatedPolicy.wrap(pol).decide(x, final_attempt=final)
        ref = no_commit_policy(pol).decide(x, final_attempt=final)
        assert d.action == ref.action and d.shown_candidates == ref.shown_candidates
        assert d.reason.startswith(REASON_PREFIX + "empty text")
    # a non-COMMIT decision and a good COMMIT are not changed
    off = DecisionPolicy(PolicyConfig(commit_p=1.01)).decide(x)
    assert gate_decision(off, x, CommitGate(), pol) is off
    good = PolicyInputs(texts=("hello world",), p_top1=0.99, set_indices=(0,), guard_risk=0.0)
    d = pol.decide(good, final_attempt=True)
    assert d.action == Action.COMMIT and gate_decision(d, good, CommitGate(1, 2, 1.0), pol) is d
    assert gate_decision(d, good, None, pol) is d


def test_strict_guard_cap_blocks_full_risk_text():
    x = PolicyInputs(texts=("ah",), p_top1=0.95, set_indices=(0,), guard_risk=1.0)
    pol = DecisionPolicy(V4_LIKE)
    assert pol.decide(x, final_attempt=True).action == Action.COMMIT
    assert GatedPolicy.wrap(pol, CommitGate()).decide(x, final_attempt=True).action == Action.COMMIT
    assert GatedPolicy.wrap(pol, CommitGate(1, 0, 1.0)).decide(x, final_attempt=True).action != Action.COMMIT
    # without the guard the cap is not used
    nog = DecisionPolicy(V4_LIKE, use_guard=False)
    assert GatedPolicy.wrap(nog, CommitGate(1, 0, 1.0)).decide(x, final_attempt=True).action == Action.COMMIT


def test_gate_never_increases_the_item_loss():
    """The risk bound stays valid: gated loss <= ungated loss on every item, at every threshold."""
    rng = np.random.default_rng(0)
    texts_pool = ["", " ", "a", "hi", "hello you", "the cat sat"]
    inputs, truths = [], []
    for _ in range(300):
        k = int(rng.integers(1, 4))
        texts = tuple(rng.choice(texts_pool, k, replace=False))
        inputs.append(PolicyInputs(texts=texts, p_top1=float(rng.random()), set_indices=tuple(range(int(rng.integers(0, k + 1)))),
                                   guard_risk=float(rng.choice([0.0, 0.3, 1.0]))))
        truths.append(str(rng.choice(texts_pool[2:])))
    for pc in (V4_LIKE, PolicyConfig(commit_p=0.5, commit_max_risk=0.5, offer_max_k=0, final_fallback="abstain")):
        pol = DecisionPolicy(pc)
        s, c, f = commit_calibration_data(pol, inputs, truths)
        assert np.all(f <= c)
        gp = GatedPolicy.wrap(pol, CommitGate(1, 2, 1.0))
        for lam in (0.0, 0.3, 0.7):
            p0 = DecisionPolicy(PolicyConfig(**{**pc.__dict__, "commit_p": lam}))
            p1 = GatedPolicy.wrap(p0, gp.gate)
            for x, t in zip(inputs, truths):
                l0 = float(p0.decide(x, True).action == Action.COMMIT and x.texts[0] != t)
                l1 = float(p1.decide(x, True).action == Action.COMMIT and x.texts[0] != t)
                assert l1 <= l0


# --- frozen configuration ----------------------------------------------------------------


def test_default_keeps_v4_bytes_and_ids():
    """No commit_gate key in the file, and the pre-M2-18 config ids do not change."""
    for name, cid in (("trust-config-t12.json", "tcfg-9fb4c81c5931e00c"), ("dryrun-trust-config.json", "tcfg-845934f0792ad9fc")):
        p = T12 / name
        cfg = FrozenTrustConfig.load(p)
        assert cfg.config_id == cid
        assert cfg.commit_gate == {} and cfg.gate is None
        assert "commit_gate" not in cfg.to_dict()
        assert json.loads(cfg.to_json()) == json.loads(p.read_text(encoding="utf-8"))
        assert type(cfg.build().policy) is DecisionPolicy
    assert "commit_gate" not in FrozenTrustConfig().to_dict()


def test_with_commit_gate_roundtrip(tmp_path):
    base = FrozenTrustConfig.load(T12 / "dryrun-trust-config.json")
    g = base.with_commit_gate(1, 0, 1.0)
    assert g.config_id != base.config_id
    assert g.to_dict()["commit_gate"] == {"min_chars": 1, "min_words": 0, "max_guard_risk": 1.0}
    p = tmp_path / "g.json"
    g.save(p)
    g2 = FrozenTrustConfig.load(p)
    assert g2 == g and g2.config_id == g.config_id
    pol = g2.build().policy
    assert isinstance(pol, GatedPolicy) and pol.gate == CommitGate(1, 0, 1.0)
    bad = g.to_dict()
    bad["commit_gate"] = {"min_chars": 1, "nope": 1}
    with pytest.raises(ValueError):
        FrozenTrustConfig.from_dict(bad)


def test_from_pipeline_records_the_gate(toy):
    dec, real, _ = toy
    pipe = TrustPipeline(dec, HarnessConfig(policy_config=V4_LIKE, fit_policy=False), {})
    pipe.fit(real[:20])
    assert FrozenTrustConfig.from_pipeline(pipe).commit_gate == {}
    pipe.policy = GatedPolicy.wrap(pipe.policy, CommitGate(2, 1))
    fz = FrozenTrustConfig.from_pipeline(pipe)
    assert fz.commit_gate == {"min_chars": 2, "min_words": 1, "max_guard_risk": None}
    assert fz.policy == FrozenTrustConfig.from_pipeline(pipe).policy


# --- streaming layer ---------------------------------------------------------------------


def _empty_hyp_file(tmp_path: Path) -> Path:
    evs = [{"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b", " "], "vocab_type": "char",
            "blank_id": 0, "source": "test", "meta": {}},
           {"type": "hypothesis", "id": "h1", "is_final": True, "score_semantics": "none", "nbest": [{"text": "", "score": 0.0}]},
           {"type": "end"}]
    p = tmp_path / "empty.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    return p


def test_streaming_layer_gate(tmp_path):
    cfg = FrozenTrustConfig(policy=dict(V4_LIKE.__dict__))
    p = _empty_hyp_file(tmp_path)
    plain = StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1))
    out = replay(p, plain, session_id="a")
    assert out[-1].final and out[-1].action == Action.COMMIT and out[-1].shown == ("",)
    gated = StreamingTrustLayer(cfg.with_commit_gate(), streaming=StreamingConfig(max_attempts=1))
    out = replay(p, gated, session_id="b")
    assert out[-1].final and out[-1].action != Action.COMMIT
    assert out[-1].decision.reason.startswith(REASON_PREFIX)
    assert out[-1].provenance.get("config_id", gated.config_id) == gated.config_id


def test_streaming_gate_on_controller_path(tmp_path):
    """The gate also holds when an online controller rebuilds the policy."""
    from fidetype.trust.online_risk import OnlineCommitRiskControl

    cfg = FrozenTrustConfig(policy=dict(V4_LIKE.__dict__)).with_commit_gate()
    layer = StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1), online=OnlineCommitRiskControl(method="aci"))
    out = replay(_empty_hyp_file(tmp_path), layer, session_id="c")
    assert out[-1].final and out[-1].action != Action.COMMIT
    assert math.isfinite(out[-1].inputs.p_top1)
