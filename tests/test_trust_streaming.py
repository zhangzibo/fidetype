"""M4-03: the streaming trust layer.

The main test is equivalence: on the same input, the streaming layer's
final decision equals the batch path (``TrustPipeline.analyze`` +
``policy.decide``). Inputs: synthetic simulator streams and the
conformance golden vectors. No participant data.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.conformance.io import load_stream, write_jsonl
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config
from fidetype.trust.online_risk import OnlineCommitRiskControl
from fidetype.trust.policy import Action
from fidetype.trust.provenance import ProvenanceLedger, verify
from fidetype.trust.streaming import (
    StreamEventError,
    StreamingConfig,
    StreamingTrustLayer,
    iter_events,
    main,
    nbest_from_hypothesis,
    replay,
)
from fidetype.trust.testing import RefCharLM, ReferenceDecoder, greedy_nbest

VECTORS = Path(__file__).resolve().parents[1] / "spec" / "conformance" / "v0.1"
SMALL_GRID = {
    "commit_p": (0.5, 0.8, 0.95),
    "commit_max_risk": (0.3, 1.0),
    "offer_max_k": (0, 3),
    "abstain_risk": (0.8, 1.01),
    "final_fallback": ("offer",),
}


@pytest.fixture(scope="module")
def setup():
    sents = sentences(700, seed=21)
    lm = RefCharLM(5).fit(sents[120:])
    dec = ReferenceDecoder(lm, beam=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=7)
    items = [Item(sim.simulate(s, seed=31 * i).stream, s) for i, s in enumerate(sents[:100])]
    cal, val, test = items[:30], items[30:80], items[80:]
    plain = TrustPipeline(dec, HarnessConfig(grid=SMALL_GRID, max_wrong_commit=0.1), {})
    plain.fit(cal, val)
    p1 = TrustPipeline(dec, paper1_v4_harness_config(grid=SMALL_GRID), {})
    p1.fit(cal, val)
    return dec, plain, p1, test


def _batch(pipe, stream, final_attempt=True):
    nb = pipe.decode(Item(stream, ""), 0)
    an = pipe.analyze(nb)
    return pipe.policy.decide(an.inputs, final_attempt=final_attempt), an


def _same(sd, d, an):
    assert sd.final
    assert sd.decision == d
    assert sd.inputs == an.inputs
    assert sd.guard == an.guard


def _layer(cfg, dec, tmp_path, **kw):
    p = tmp_path / "trust.json"
    cfg.save(p)
    return StreamingTrustLayer(FrozenTrustConfig.load(p), decode_fn=dec,
                               streaming=StreamingConfig(max_attempts=1, **kw))


# --- frozen configuration ------------------------------------------------------


def test_frozen_config_roundtrip(setup, tmp_path):
    _, plain, p1, _ = setup
    for pipe, name in ((plain, "plain"), (p1, "p1")):
        cfg = FrozenTrustConfig.from_pipeline(pipe, name, PAPER1_V4_RECIPE if name == "p1" else None)
        cfg.save(tmp_path / f"{name}.json")
        text = (tmp_path / f"{name}.json").read_text(encoding="utf-8")
        json.loads(text)  # strict JSON (no NaN / Infinity tokens)
        assert "NaN" not in text and "Infinity" not in text
        back = FrozenTrustConfig.load(tmp_path / f"{name}.json")
        assert back.config_id == cfg.config_id
        comp = back.build()
        assert comp.policy.config == pipe.policy.config
        assert comp.frame_scaler.temperature == pipe.frame_scaler.temperature
        assert comp.calibrator.sentence.temperature == pipe.calibrator.sentence.temperature
        q1, q2 = comp.conformal.q, pipe.conformal.q
        assert q1 == q2 or (math.isnan(q1) and math.isnan(q2))
    cfg1 = FrozenTrustConfig.from_pipeline(p1, "p1", PAPER1_V4_RECIPE)
    assert cfg1.risk_control["method"].startswith("ltt")
    assert cfg1.risk_control["alpha"] == 0.05 and cfg1.risk_control["delta"] == 0.1
    assert cfg1.risk_control["combine"] == "max"
    assert cfg1.use_guard
    # LTT max: the final commit_p is at least the LTT threshold.
    assert cfg1.policy["commit_p"] >= cfg1.risk_control["threshold"]


def test_frozen_config_rejects_unknown(tmp_path):
    d = FrozenTrustConfig().to_dict()
    d["bogus"] = 1
    with pytest.raises(ValueError):
        FrozenTrustConfig.from_dict(d)
    d = FrozenTrustConfig().to_dict()
    d["schema"] = "other/9"
    with pytest.raises(ValueError):
        FrozenTrustConfig.from_dict(d)


# --- equivalence: synthetic streams --------------------------------------------


@pytest.mark.parametrize("which", ["plain", "p1", "p1-loose"])
@pytest.mark.parametrize("fmt", ["jsonl", "npz"])
def test_replay_equals_batch(setup, tmp_path, which, fmt):
    dec, plain, p1, test = setup
    pipe = plain if which == "plain" else p1
    cfg = FrozenTrustConfig.from_pipeline(pipe, which)
    if which == "p1-loose":
        # Same recipe, looser gate: exercises COMMIT / OFFER paths too.
        cfg = cfg.with_policy(commit_p=0.3, commit_max_risk=0.4, abstain_risk=0.45)
        pipe = copy.copy(pipe)
        pipe.policy = cfg.build().policy
    layer = _layer(cfg, dec, tmp_path)
    actions = set()
    for i, it in enumerate(test):
        path = tmp_path / f"s{i}.{fmt}"
        if fmt == "jsonl":
            write_jsonl(it.stream(0), path)
        else:
            it.stream(0).to_npz(path)
        out = replay(path, layer, session_id=f"s{i}")
        assert len(out) == 1
        d, an = _batch(pipe, load_stream(path).stream)
        _same(out[0], d, an)
        assert out[0].provenance["config_id"] == cfg.config_id
        assert out[0].provenance["input"]["stream_sha256"]
        actions.add(out[0].action)
    if which == "p1-loose":
        assert len(actions) >= 2, actions


def test_frames_route_is_incremental(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), dec, tmp_path)
    path = tmp_path / "a.jsonl"
    write_jsonl(test[0].stream(0), path)
    evs = list(iter_events(path))
    for ev in evs[:-1]:
        assert layer.push(ev, "x") == []  # header and frames: no decision yet
    assert layer.session_state("x")["buffered_frames"] == test[0].stream(0).n_frames
    out = layer.push(evs[-1], "x")  # end
    assert len(out) == 1 and out[0].final
    st = layer.session_state("x")
    assert st["buffered_frames"] == 0 and st["buffered_bytes"] == 0
    # Lines after the end marker are ignored (spec 10, A5).
    assert layer.push(evs[1], "x") == []
    assert layer.session_state("x")["ignored_events"] == 1


def test_segment_end_splits_utterances(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), dec, tmp_path)
    a, b = test[1].stream(0), test[2].stream(0)
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_jsonl(a, pa)
    write_jsonl(b, pb)
    ea, eb = list(iter_events(pa)), list(iter_events(pb))
    off = float(a.frame_times[-1]) + 1.0
    events = ea[:-1] + [{"type": "segment_end"}]
    for ev in eb[1:-1]:
        events.append({**ev, "t": ev["t"] + off})
    events.append({"type": "end"})
    out = []
    for ev in events:
        out += layer.push(ev, "s")
    assert [d.utterance for d in out] == [0, 1]
    da, ana = _batch(plain, load_stream(pa).stream)
    db, anb = _batch(plain, load_stream(pb).stream)
    _same(out[0], da, ana)
    assert out[1].decision == db and out[1].inputs == anb.inputs


def test_sessions_are_isolated(setup, tmp_path):
    dec, plain, _, test = setup
    cfg = FrozenTrustConfig.from_pipeline(plain)
    paths = []
    for i in range(3):
        p = tmp_path / f"i{i}.jsonl"
        write_jsonl(test[i].stream(0), p)
        paths.append(p)
    solo = [replay(p, _layer(cfg, dec, tmp_path), session_id="s")[0] for p in paths]
    layer = _layer(cfg, dec, tmp_path)
    its = [list(iter_events(p)) for p in paths]
    out = {}
    for k in range(max(map(len, its))):  # round-robin interleave
        for i, evs in enumerate(its):
            if k < len(evs):
                for d in layer.push(evs[k], f"u{i}"):
                    out[i] = d
    for i in range(3):
        assert out[i].decision == solo[i].decision and out[i].inputs == solo[i].inputs
        assert out[i].session_id == f"u{i}"


def test_provisional_frames_do_not_change_final(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), dec, tmp_path, partial_every_frames=10)
    p = tmp_path / "a.jsonl"
    write_jsonl(test[3].stream(0), p)
    out = replay(p, layer)
    prov = [d for d in out if not d.final]
    fin = [d for d in out if d.final]
    assert len(prov) == test[3].stream(0).n_frames // 10 and len(fin) == 1
    d, an = _batch(plain, load_stream(p).stream)
    _same(fin[0], d, an)
    assert [x.seq for x in out] == list(range(len(out)))


# --- hypothesis route ---------------------------------------------------------------


def _hyp_events(nb, stream):
    head = {"type": "header", "spec_version": "0.1", "vocab": list(stream.vocab), "vocab_type": "char",
            "blank_id": 0, "source": "test-decoder", "meta": {}}
    items = [{"text": c.text, "score": c.score, "char_confidences": list(c.char_confidences)} for c in nb.candidates]
    part = {"type": "hypothesis", "id": "h1", "is_final": False, "score_semantics": "none", "nbest": items[:2]}
    fin = {"type": "hypothesis", "id": "h2", "revision_of": "h1", "is_final": True, "score_semantics": "none",
           "nbest": items}
    return [head, part, fin, {"type": "end"}]


def test_hypothesis_route_equals_batch(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), None, tmp_path)
    assert layer.route == "hypothesis"
    for i, it in enumerate(test[:8]):
        nb = dec(plain.frame_scaler.transform_stream(it.stream(0)))
        evs = _hyp_events(nb, it.stream(0))
        p = tmp_path / f"h{i}.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
        out = replay(p, layer, session_id=f"h{i}")
        assert [d.final for d in out] == [False, True]
        d, an = plain.policy.decide(plain.analyze(nbest_from_hypothesis(evs[2])).inputs, final_attempt=True), None
        assert out[1].decision == d
        assert out[1].provenance["input"]["hypothesis_id"] == "h2"
        assert out[1].provenance["input"]["revision_of"] == "h1"


def test_hypothesis_validation():
    with pytest.raises(StreamEventError):
        nbest_from_hypothesis({"nbest": [{"text": "ab", "score": None}]})
    with pytest.raises(StreamEventError):
        nbest_from_hypothesis({"nbest": [{"text": "ab", "score": 1.0, "char_confidences": [0.5]}]})
    with pytest.raises(StreamEventError):
        nbest_from_hypothesis({"nbest": [{"text": "ab", "score": 1.0, "char_confidences": [0.5, 1.5]}]})
    nb = nbest_from_hypothesis({"nbest": [{"text": "a b", "score": 1.0}, {"text": "a  b", "score": 2.0}]})
    assert nb.texts == ["a b"] and nb.top.score == 2.0  # merged, best score kept


# --- equivalence: conformance golden vectors ------------------------------------------


def _manifest():
    return json.loads((VECTORS / "manifest.json").read_text(encoding="utf-8"))["vectors"]


def test_golden_vectors_equal_batch(setup, tmp_path):
    _, plain, _, _ = setup
    cfg = FrozenTrustConfig.from_pipeline(plain)
    bp = copy.copy(plain)
    bp.decode_fn, bp.decode_cache = greedy_nbest, {}
    hyp_layer = StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1))
    n_compared = 0
    for v in _manifest():
        if v["expect"] != "accept":
            continue
        path = VECTORS / v["file"]
        cs = load_stream(path)
        layer = StreamingTrustLayer(cfg, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1))
        try:
            ref = _batch(bp, cs.stream)
        except Exception as e:  # noqa: BLE001 - the decoder may not support this vocab
            with pytest.raises(type(e)):
                replay(path, layer)
            continue
        out = replay(path, layer)
        if cs.stream.n_frames == 0:
            assert out == []  # an utterance with no input gives no decision
            continue
        assert len(out) == 1, v["file"]
        _same(out[0], *ref)
        n_compared += 1
        hyps = [e for e in cs.events if e.get("type") == "hypothesis"]
        if hyps:
            hout = replay(path, hyp_layer, session_id=v["file"])
            an = plain.analyze(nbest_from_hypothesis(hyps[-1]))
            assert hout[-1].final and hout[-1].decision == plain.policy.decide(an.inputs, final_attempt=True)
    assert n_compared >= 10


@pytest.mark.parametrize("vid", ["V41", "V43", "V44", "V45", "V46", "V47", "V50"])
def test_golden_reject_vectors_raise(setup, vid):
    _, plain, _, _ = setup
    v = next(x for x in _manifest() if x["id"] == vid)
    assert v["expect"] == "reject"
    layer = StreamingTrustLayer(FrozenTrustConfig.from_pipeline(plain), decode_fn=greedy_nbest)
    with pytest.raises(StreamEventError):
        replay(VECTORS / v["file"], layer)


# --- limits, errors, attempts ---------------------------------------------------------


def test_bad_events_leave_state_unchanged(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), dec, tmp_path)
    p = tmp_path / "a.jsonl"
    write_jsonl(test[0].stream(0), p)
    evs = list(iter_events(p))
    with pytest.raises(StreamEventError):
        layer.push(evs[1], "s")  # frame before header
    layer.push(evs[0], "s")
    layer.push(evs[1], "s")
    with pytest.raises(StreamEventError):
        layer.push(evs[1], "s")  # same t again
    bad = dict(evs[2])
    bad["log_probs"] = [0.0] * len(bad["log_probs"])  # sums to V
    with pytest.raises(StreamEventError):
        layer.push(bad, "s")
    with pytest.raises(StreamEventError):
        layer.push("{not json", "s")
    for ev in evs[2:]:
        layer.push(ev, "s")
    # The stream after the errors is the original stream.
    d, an = _batch(plain, load_stream(p).stream)
    out = layer.flush("s")
    assert out == []  # the end event already closed the utterance
    assert layer.session_state("s")["decisions"] == 1


def test_max_frames_abstains(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), dec, tmp_path, max_frames=5)
    p = tmp_path / "a.jsonl"
    write_jsonl(test[0].stream(0), p)
    out = replay(p, layer)
    assert len(out) == 1 and out[0].final and out[0].action == Action.ABSTAIN
    assert "max_frames" in out[0].decision.reason
    st = layer.session_state()
    assert st["buffered_frames"] == 0 and st["dropped_frames"] == test[0].stream(0).n_frames - 5


def test_max_sessions(setup):
    _, plain, _, _ = setup
    layer = StreamingTrustLayer(FrozenTrustConfig.from_pipeline(plain), streaming=StreamingConfig(max_sessions=2))
    layer.new_item("a")
    layer.new_item("b")
    with pytest.raises(StreamEventError):
        layer.new_item("c")
    layer.close("a")
    layer.new_item("c")
    assert sorted(layer.sessions) == ["b", "c"]


def test_attempts_after_ask(setup, tmp_path):
    dec, plain, _, test = setup
    cfg = FrozenTrustConfig.from_pipeline(plain).with_policy(commit_p=1.01, offer_max_k=0, abstain_risk=1.01)
    layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=2))
    p = tmp_path / "a.jsonl"
    write_jsonl(test[0].stream(0), p)
    first = replay(p, layer, session_id="s")
    assert first[0].action == Action.ASK and not first[0].final_attempt and first[0].attempt == 0
    second = replay(p, layer, session_id="s")  # the repeat
    assert second[0].attempt == 1 and second[0].final_attempt
    assert second[0].action != Action.ASK
    third = replay(p, layer, session_id="s")  # a new item
    assert third[0].attempt == 0


def test_signal_quality_gate(setup, tmp_path):
    dec, plain, _, test = setup
    layer = _layer(FrozenTrustConfig.from_pipeline(plain), dec, tmp_path, min_signal_quality=0.5)
    p = tmp_path / "a.jsonl"
    write_jsonl(test[0].stream(0), p, events=[{"type": "signal_quality", "t": 0.0, "value": 0.2, "unit": "index"}])
    out = replay(p, layer)
    assert out[0].action == Action.ABSTAIN and "signal quality" in out[0].decision.reason


# --- online re-calibration and provenance ------------------------------------------------


def test_online_hook_and_ledger(setup, tmp_path):
    dec, plain, _, test = setup
    cfg = FrozenTrustConfig.from_pipeline(plain).with_policy(commit_p=0.3, commit_max_risk=1.0)
    ledger = ProvenanceLedger(text_mode="hash")
    online = OnlineCommitRiskControl(alpha=0.1, method="aci", eta=0.05, lam_init=0.1)
    layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=1),
                                online=online, ledger=ledger)
    losses = []
    for i, it in enumerate(test[:10]):
        p = tmp_path / f"o{i}.jsonl"
        write_jsonl(it.stream(0), p)
        (d,) = replay(p, layer, session_id="user")
        assert d.ticket is not None
        assert d.provenance["commit_threshold"] >= 0.3  # frozen commit_p is the floor
        assert d.provenance["ledger_decision_id"]
        losses.append(layer.feedback(d, it.text))
    assert all(x is not None for x in losses)
    st = layer.session_state("user")
    assert st["pending_feedback"] == 0 and st["online_threshold"] >= 0.3
    assert online.n_obs == 0  # the template is not shared with the session
    assert verify(ledger.entries).ok
    kinds = [e["kind"] for e in ledger.entries]
    assert kinds.count("decision") == 10 and kinds.count("correction") == 10 and kinds.count("context") == 1


def test_cli_replay(setup, tmp_path, capsys):
    dec, plain, _, test = setup
    cfgp = tmp_path / "trust.json"
    FrozenTrustConfig.from_pipeline(plain).save(cfgp)
    p = tmp_path / "a.jsonl"
    write_jsonl(test[0].stream(0), p)
    assert main(["replay", "--config", str(cfgp), "--decoder", "greedy", "--no-text", str(p)]) == 0
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert len(lines) == 1 and lines[0]["type"] == "trust_decision" and lines[0]["is_final"]
    assert "shown" not in lines[0]
