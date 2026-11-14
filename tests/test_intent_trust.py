"""P12-01 / P12-02: FEP-0003 intent events and the intent trust layer.

All data is synthetic (fixed seeds, ``fidetype.trust.intent_sim``). No data from people.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from fidetype.cli import main as fidetype_cli
from fidetype.conformance.profiles import fep0001 as P1
from fidetype.conformance.profiles import fep0003 as P3
from fidetype.conformance.vectors import _header
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.intent import (
    DECLARATION_KEY,
    DEFAULT_ALPHA,
    RISK_CLASSES,
    IntentEventError,
    IntentPolicy,
    IntentTrustConfig,
    IntentTrustLayer,
    IntentVocabulary,
    calibrate,
    candidates_to_probs,
    evaluate_policy,
    fit_intent_config,
    validate_intent_declaration,
)
from fidetype.trust.intent_sim import demo_vocabulary, shuffled_control, simulate_trials, trials_to_events, uniform_control
from fidetype.trust.streaming import StreamEventError, StreamingTrustLayer

V = demo_vocabulary()
THR = {"safe": 0.6, "undoable": 0.8, "irreversible": 0.95}


def cfg(**kw):
    return IntentTrustConfig(V, thresholds=dict(THR), **kw)


def onehot(iid: str, p: float = 0.99) -> np.ndarray:
    q = np.full(len(V), (1 - p) / (len(V) - 1))
    q[V.index(iid)] = p
    return q


def header(**over):
    h = {"type": "header", "spec_version": "0.1", "vocab": list(V.ids), "vocab_type": "command", "blank_id": None,
         "source": "test", DECLARATION_KEY: V.to_declaration()}
    h.update(over)
    return h


def intent_ev(iid: str, p: float = 0.99, n: int = 0, final: bool = True, sem: str = "uncalibrated_prob"):
    rest = [j for j in V.ids if j != iid][:2]
    cands = [{"intent": iid, "score": p}] + [{"intent": r, "score": round((1 - p) / 3, 6)} for r in rest]
    if sem == "none":
        cands = [{"intent": c["intent"]} for c in cands]
    return {"type": "intent", "id": f"u{n}", "t": float(n), "is_final": final, "score_semantics": sem, "candidates": cands}


# --- declaration and configuration -------------------------------------------------------------


def test_declaration_rules():
    assert validate_intent_declaration(V.to_declaration()) == []
    assert validate_intent_declaration([]) != []
    dup = {"intents": [{"id": "a", "risk": "safe"}, {"id": "a", "risk": "safe"}]}
    assert any("not unique" in e for e in validate_intent_declaration(dup))
    weak = {"intents": [{"id": "ok", "risk": "undoable", "role": "confirm"}, {"id": "go", "risk": "irreversible"}]}
    assert any("confirm" in e for e in validate_intent_declaration(weak))
    only_null = {"intents": [{"id": "rest", "risk": "safe", "role": "null"}]}
    assert validate_intent_declaration(only_null)
    with pytest.raises(IntentEventError):
        IntentVocabulary.from_declaration(dup)


def test_config_round_trip_and_override(tmp_path):
    c = cfg(risk_override={"intent.select": "irreversible"})
    c.save(tmp_path / "c.json")
    c2 = IntentTrustConfig.load(tmp_path / "c.json")
    assert c2.config_id == c.config_id and c2.config_id.startswith("icfg-")
    assert c2.risk_of("intent.select") == "irreversible"
    assert cfg().config_id != c.config_id
    with pytest.raises(ValueError):  # laxer than the declaration
        cfg(risk_override={"intent.call-caregiver": "safe"})
    inf = IntentTrustConfig(V)  # default: never commit
    assert json.loads(json.dumps(inf.to_dict()))["thresholds"]["safe"] is None
    assert IntentTrustConfig.from_dict(inf.to_dict()).config_id == inf.config_id


def test_stream_declaration_can_only_make_stricter():
    c = cfg()
    assert c.risk_of("intent.next", "irreversible") == "irreversible"
    assert c.risk_of("intent.call-caregiver", "safe") == "irreversible"


# --- policy ------------------------------------------------------------------------------------


def test_policy_commit_arm_offer_abstain():
    pol = IntentPolicy(cfg())
    assert pol.decide(onehot("intent.select")).action == "COMMIT"
    ch = pol.decide(onehot("intent.call-caregiver"))
    assert ch.action == "OFFER" and ch.confirm_required and ch.intent == "intent.call-caregiver"
    two = np.full(len(V), 0.01)
    two[V.index("intent.select")], two[V.index("intent.next")] = 0.5, 0.4
    ch = pol.decide(two / two.sum())
    assert ch.action == "OFFER" and set(ch.offered) == {"intent.select", "intent.next"}
    assert pol.decide(np.full(len(V), 1 / len(V))).action == "ABSTAIN"


def test_null_intent_is_never_committed():
    pol = IntentPolicy(cfg(min_threshold=0.0))
    ch = pol.decide(onehot("intent.rest", 0.999999))
    assert ch.action == "ABSTAIN" and ch.intent is None
    assert "intent.rest" not in pol.offer_set(calibrate(onehot("intent.rest", 0.5), 1.0))


def test_no_commit_without_probabilities_or_with_low_quality():
    pol = IntentPolicy(cfg(min_signal_quality=0.5))
    assert pol.decide(onehot("intent.select"), prob_semantics=False).action != "COMMIT"
    assert pol.decide(onehot("intent.select"), quality=0.2).action == "ABSTAIN"
    assert pol.decide(onehot("intent.select"), quality=0.9).action == "COMMIT"


def test_min_threshold_floor_blocks_lax_class():
    c = IntentTrustConfig(V, thresholds={"safe": 0.0, "undoable": 0.0, "irreversible": 0.0})
    p = np.full(len(V), 0.6 / (len(V) - 1))
    p[V.index("intent.stop")] = 0.4
    assert IntentPolicy(c).decide(p).action != "COMMIT"  # floor 0.5
    assert IntentPolicy(IntentTrustConfig(V, thresholds=c.thresholds, min_threshold=0.0)).decide(p).action == "COMMIT"


def test_candidates_fill_missing_mass_uniformly():
    p = candidates_to_probs([{"intent": "intent.select", "score": 0.78}], V)
    assert p[V.index("intent.select")] == pytest.approx(0.78)
    assert p.sum() == pytest.approx(1.0)
    assert np.allclose(np.delete(p, V.index("intent.select")), 0.22 / (len(V) - 1))


def test_evaluate_policy_matches_decide():
    t = simulate_trials(V, 600, seed=4)
    c = cfg(min_signal_quality=0.5)
    pol = IntentPolicy(c)
    acts = [pol.decide(p, quality=q) for p, q in zip(t.probs, t.quality)]
    e = evaluate_policy(c, t.probs, t.labels, t.quality)
    assert e["commit"] == sum(a.action == "COMMIT" for a in acts)
    assert e["armed"] == sum(a.confirm_required for a in acts)
    assert e["offer"] == sum(a.action == "OFFER" and not a.confirm_required for a in acts)
    assert e["n"] == e["commit"] + e["armed"] + e["offer"] + e["abstain"]


# --- fit and risk control ------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["ltt", "crc"])
def test_per_class_risk_control_on_simulator(method):
    rates = {r: [] for r in RISK_CLASSES}
    for s in range(12):
        fit = simulate_trials(V, 500, seed=100 + s)
        cal = simulate_trials(V, 500, seed=200 + s)
        test = simulate_trials(V, 2000, seed=300 + s)
        c = fit_intent_config(V, fit.probs, fit.labels, cal.probs, cal.labels, method=method)
        assert c.fit["method"] == method and set(c.fit["classes"]) == set(RISK_CLASSES)
        e = evaluate_policy(c, test.probs, test.labels)
        for r in RISK_CLASSES:
            rates[r].append(e[f"wrong_{r}"] / e["n"])
    for r in RISK_CLASSES:  # mean over sessions at or below alpha (with a small Monte-Carlo margin)
        assert np.mean(rates[r]) <= DEFAULT_ALPHA[r] * 1.15, (r, np.mean(rates[r]))


def test_controls_uniform_and_quality_gate():
    fit, cal, test = (simulate_trials(V, 500, seed=s) for s in (1, 2, 3))
    c = fit_intent_config(V, fit.probs, fit.labels, cal.probs, cal.labels, min_signal_quality=0.5)
    u = uniform_control(test)
    e = evaluate_policy(c, u.probs, u.labels, u.quality)
    assert e["commit"] == e["armed"] == 0
    ns = test.kind == "nosignal"
    e = evaluate_policy(c, test.probs[ns], test.labels[ns], test.quality[ns])
    assert e["commit"] == e["armed"] == 0
    sh = shuffled_control(test)
    assert evaluate_policy(c, sh.probs, sh.labels, sh.quality)["n"] == len(test)


def test_infeasible_class_never_commits():
    fit, cal = simulate_trials(V, 200, seed=5), simulate_trials(V, 30, seed=6)
    c = fit_intent_config(V, fit.probs, fit.labels, cal.probs, cal.labels, alpha={"irreversible": 0.001})
    assert math.isinf(c.thresholds["irreversible"])
    assert IntentPolicy(c).decide(onehot("intent.call-caregiver", 0.9999)).action != "COMMIT"


# --- stream layer ----------------------------------------------------------------------------------


def push_all(layer, events, sid="s"):
    out = []
    for e in events:
        out += layer.push(e, sid)
    return out


def test_confirmation_path_by_intent():
    lay = IntentTrustLayer(cfg())
    ds = push_all(lay, [header(), intent_ev("intent.call-caregiver", n=0), intent_ev("intent.confirm", 0.99, n=1)])
    assert ds[0].action == "OFFER" and ds[0].confirm_required and not ds[0].acts
    assert ds[1].action == "COMMIT" and ds[1].intent == "intent.call-caregiver"
    assert ds[1].confirmation_of == 0 and ds[1].confirmed_via == "intent" and ds[1].acts
    # a weak confirmation drops the armed intent
    ds = push_all(lay, [intent_ev("intent.call-caregiver", n=2), intent_ev("intent.confirm", 0.9, n=3)])
    assert ds[1].action == "ABSTAIN" and ds[1].pending_cleared == "confirmation failed"
    # another unit clears the armed intent; a later confirm has nothing to confirm
    ds = push_all(lay, [intent_ev("intent.call-caregiver", n=4), intent_ev("intent.select", n=5),
                        intent_ev("intent.confirm", n=6)])
    assert ds[1].pending_cleared and ds[2].action == "ABSTAIN" and "nothing to confirm" in ds[2].reason
    assert lay.stats("s")["confirmed"] == 1


def test_confirmation_by_feedback_and_selection():
    lay = IntentTrustLayer(cfg())
    ds = push_all(lay, [header(), intent_ev("intent.call-caregiver", n=0),
                        {"type": "intent_feedback", "ref_unit": 0, "outcome": "confirmed", "source": "switch"}])
    assert ds[1].acts and ds[1].confirmed_via == "feedback" and ds[1].p_top1 is None
    # a selection from an OFFER list; a stale feedback is ignored
    two = {"type": "intent", "id": "x", "t": 5.0, "is_final": True, "score_semantics": "uncalibrated_prob",
           "candidates": [{"intent": "intent.select", "score": 0.5}, {"intent": "intent.next", "score": 0.45}]}
    ds = push_all(lay, [two, {"type": "intent_feedback", "ref_unit": 2, "outcome": "selected", "intent": "intent.next"},
                        {"type": "intent_feedback", "ref_unit": 2, "outcome": "selected", "intent": "intent.next"}])
    assert ds[0].action == "OFFER" and len(ds) == 2 and ds[1].intent == "intent.next"
    with pytest.raises(IntentEventError):
        lay.push({"type": "intent_feedback", "ref_unit": 0, "outcome": "maybe"}, "s")


def test_undo_and_irreversible_blocks_undo():
    lay = IntentTrustLayer(cfg())
    ds = push_all(lay, [header(), intent_ev("intent.select", n=0), intent_ev("intent.undo", n=1)])
    assert ds[1].action == "COMMIT" and ds[1].undo_of == 0
    ds = push_all(lay, [intent_ev("intent.undo", n=2)])  # already undone
    assert ds[0].action == "ABSTAIN"
    ds = push_all(lay, [intent_ev("intent.select", n=3), intent_ev("intent.call-caregiver", n=4),
                        intent_ev("intent.confirm", n=5), intent_ev("intent.undo", n=6)])
    assert ds[2].acts and ds[3].action == "ABSTAIN"


def test_provisional_intent_never_acts_and_none_semantics_never_commit():
    lay = IntentTrustLayer(cfg())
    ds = push_all(lay, [header(), intent_ev("intent.select", n=0, final=False), intent_ev("intent.select", n=1, sem="none")])
    assert not ds[0].final and not ds[0].acts and ds[0].unit == ds[1].unit == 0
    assert ds[1].action != "COMMIT"


def test_null_and_unknown_and_missing_declaration():
    lay = IntentTrustLayer(cfg(min_threshold=0.0))
    ds = push_all(lay, [header(), intent_ev("intent.rest", 0.999, n=0)])
    assert ds[0].action == "ABSTAIN"
    with pytest.raises(IntentEventError):
        lay.push({**intent_ev("intent.select", n=1), "candidates": [{"intent": "intent.fly", "score": 0.5}]}, "s")
    lay2 = IntentTrustLayer(cfg())
    lay2.push(header(**{DECLARATION_KEY: None}) | {"vocab_type": "char"}, "t")
    with pytest.raises(IntentEventError):
        lay2.push(intent_ev("intent.select"), "t")


def test_command_frames_route_and_v01_decision():
    lay = IntentTrustLayer(cfg())
    lp = np.log(onehot("intent.select", 0.97))
    ds = push_all(lay, [header(), {"type": "frame", "t": 0.0, "log_probs": lp.tolist()},
                        {"type": "frame", "t": 0.04, "log_probs": lp.tolist()}, {"type": "segment_end", "t": 0.1},
                        {"type": "decision", "t": 0.5, "label": "intent.stop", "score": 0.9, "score_semantics": "uncalibrated_prob"},
                        {"type": "decision", "t": 0.6, "label": "intent.stop", "score_semantics": "none"}])
    assert ds[0].acts and ds[0].provenance["input"]["kind"] == "frames"
    assert ds[1].acts and ds[1].intent == "intent.stop"
    assert ds[2].action != "COMMIT"


def test_layer_output_passes_fep0003_and_fep0001(tmp_path):
    t = simulate_trials(V, 200, seed=8)
    lay = IntentTrustLayer(cfg())
    evs = trials_to_events(V, t)
    evs.insert(5, {"type": "intent_feedback", "ref_unit": 1, "outcome": "wrong"})
    ds = push_all(lay, evs)
    log = tmp_path / "d.jsonl"
    log.write_text("\n".join(json.dumps(d.to_event()) for d in ds) + "\n", encoding="utf-8")
    assert P3.check_file(log).failures("core") == []
    assert P1.check_file(log).failures("core") == []  # an older FEP-0001 consumer accepts the log
    assert all(x is None for x in P1.acted_texts([d.to_event() for d in ds]))  # and never types an intent id
    stream = tmp_path / "s.jsonl"
    stream.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    assert P3.check_file(stream).failures("core") == []


def test_streaming_layer_shares_seq_with_text():
    text_cfg = FrozenTrustConfig(name="t", frame_temperature=1.0).with_policy(commit_p=0.3, commit_max_risk=1.0,
                                                                             abstain_risk=1.01)
    layer = StreamingTrustLayer(text_cfg, intent=IntentTrustLayer(cfg()))
    hyp = {"type": "hypothesis", "id": "h1", "is_final": True, "score_semantics": "none",
           "nbest": [{"text": "ab", "score": -0.1}, {"text": "a", "score": -3.0}]}
    out = []
    for e in [_header(**{DECLARATION_KEY: V.to_declaration()}), intent_ev("intent.select", n=0), hyp,
              intent_ev("intent.call-caregiver", n=1), intent_ev("intent.confirm", n=2), {"type": "end"}]:
        out += layer.push(e, "u")
    evs = [d.to_event() for d in out]
    assert [e["seq"] for e in evs] == list(range(len(evs)))
    assert [e.get("profile", "text") for e in evs] == ["intent", "text", "intent", "intent"]
    for i, e in enumerate(evs):
        e["_line"] = i + 1
    assert P3.td_final_errors(evs) == [] and P3.safety_errors(evs) == []
    with pytest.raises(StreamEventError):
        layer.push({**intent_ev("intent.select", n=9), "candidates": []}, "v")  # before header -> also an error


def test_cli_intent_replay_and_validate(tmp_path, capsys):
    c = cfg()
    c.save(tmp_path / "c.json")
    s = tmp_path / "s.jsonl"
    s.write_text("\n".join(json.dumps(e) for e in [header(), intent_ev("intent.select")]) + "\n", encoding="utf-8")
    assert fidetype_cli(["intent", "replay", "--config", str(tmp_path / "c.json"), str(s)]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    assert line["profile"] == "intent" and line["intent"] == "intent.select" and "shown" not in line
    assert fidetype_cli(["validate", "--profile", "fep-0003", str(s)]) == 0
    assert fidetype_cli(["conformance", "--profile", "fep-0003"]) == 0


def test_json_schemas_parse():
    from pathlib import Path

    sdir = Path(__file__).resolve().parents[1] / "spec" / "schemas" / "fep-0003"
    names = sorted(x.name for x in sdir.glob("*.schema.json"))
    assert names == ["intent-declaration.schema.json", "intent-event.schema.json", "intent-feedback.schema.json",
                     "intent-trust-decision.schema.json"]
    for n in names:
        assert json.loads((sdir / n).read_text(encoding="utf-8"))["$schema"].endswith("2020-12/schema")


def test_json_schemas_accept_the_layer_output(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    from pathlib import Path

    sdir = Path(__file__).resolve().parents[1] / "spec" / "schemas" / "fep-0003"
    load = lambda n: json.loads((sdir / n).read_text(encoding="utf-8"))  # noqa: E731
    jsonschema.validate(V.to_declaration(), load("intent-declaration.schema.json"))
    jsonschema.validate(intent_ev("intent.select"), load("intent-event.schema.json"))
    lay = IntentTrustLayer(cfg())
    for d in push_all(lay, [header(), intent_ev("intent.select")]):
        jsonschema.validate(d.to_event(), load("intent-trust-decision.schema.json"))


def test_no_signal_reference_blocks_a_confident_constant_output():
    fit, cal = simulate_trials(V, 500, seed=11), simulate_trials(V, 500, seed=12)
    const = onehot("intent.select", 0.995)  # a decoder that outputs one confident intent on zero input
    c0 = fit_intent_config(V, fit.probs, fit.labels, cal.probs, cal.labels)
    c1 = fit_intent_config(V, fit.probs, fit.labels, cal.probs, cal.labels, no_signal_probs=const[None, :])
    assert IntentPolicy(c0).decide(const).action == "COMMIT"
    assert IntentPolicy(c1).decide(const).action != "COMMIT"
    assert c1.thresholds["undoable"] >= c0.thresholds["undoable"]  # only stricter
    assert c1.thresholds["safe"] == c0.thresholds["safe"]
    assert c1.fit["classes"]["undoable"]["no_signal_floor"] is not None and c1.fit["no_signal_reference"] == 1
