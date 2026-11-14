"""FEP-0005 control trust layer, velocity decoder and profile tests (synthetic data only)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.conformance.profiles import fep0005
from fidetype.decoders.velocity import (ResidualScale, StreamingVelocityDecoder, WienerVelocityDecoder, r2_score,
                                        window_total)
from fidetype.trust.control import (CONTROL, CONTROL_ENABLE, DECLARATION_KEY, ControlEventError, ControlTrustConfig,
                                    ControlTrustLayer, clamp, conformal_quantile, fit_control_config, gate, gate_batch,
                                    validate_control_declaration)
from fidetype.trust.control_sim import simulate_control

SDIR = Path(__file__).resolve().parents[1] / "spec" / "schemas" / "fep-0005"
DECL = {"dims": 2, "quantity": "velocity", "units": "mm/s", "frame": "workspace", "rate_hz": 50.0, "uncertainty": "std"}


def header(**decl):
    return {"type": "header", "spec_version": "0.1", "vocab": ["control"], "vocab_type": "command", "blank_id": None,
            "source": "test", DECLARATION_KEY: {**DECL, **decl}}


def ctl(tick, v=(100.0, 0.0), std=10.0, t=None, **kw):
    ev = {"type": CONTROL, "t": 0.02 * (tick + 1) if t is None else t, "tick": tick, "values": list(v)}
    if std is not None:
        ev["std"] = [std, std]
    ev.update(kw)
    return ev


def enable(on=True, t=0.0):
    return {"type": CONTROL_ENABLE, "t": t, "enabled": on, "source": "switch"}


def cfg(**kw):
    base = dict(q=2.0, v_max=300.0, a_max=math.inf, handoff_s=0.0, level=0.9, no_signal_output=None)
    base.update(kw)
    return ControlTrustConfig(**base)


def run(layer, events):
    out = []
    for e in events:
        out += layer.push(e)
    return out


@pytest.fixture(scope="module")
def fitted():
    s = simulate_control(T=12000, seed=3)
    c, v = s.counts, s.vel
    fit, sc, cal, te = slice(0, 4800), slice(4800, 6000), slice(6000, 8400), slice(8400, 12000)
    dec = WienerVelocityDecoder(history=10).fit(c[fit], v[fit])
    vh = dec.predict(c)
    tot = window_total(c, 10)
    scale = ResidualScale().fit(v[sc], vh[sc], tot[sc])
    sig = scale.sigma(vh, tot)
    return dict(c=c, v=v, vh=vh, sig=sig, tot=tot, dec=dec, scale=scale, cal=cal, te=te)


# --- decoder ----------------------------------------------------------------------------------


def test_decoder_learns_synthetic_velocity_and_streams_identically(fitted):
    f = fitted
    assert r2_score(f["v"][f["te"]], f["vh"][f["te"]]) > 0.7
    sd = StreamingVelocityDecoder(f["dec"], f["scale"])
    steps = [sd.step(f["c"][i]) for i in range(300)]
    assert np.allclose(np.array([s[0] for s in steps]), f["vh"][:300])
    assert np.allclose([s[1] for s in steps], f["sig"][:300])


def test_decoder_is_causal(fitted):
    c = fitted["c"][:400].copy()
    a = fitted["dec"].predict(c)
    c[200:] = 0  # changing the future must not change the past
    b = fitted["dec"].predict(c)
    assert np.allclose(a[:200], b[:200]) and not np.allclose(a[200:], b[200:])


# --- conformal calibration and the gate ----------------------------------------------------------


def test_conformal_quantile_finite_sample():
    s = np.arange(1, 10, dtype=float)  # n = 9
    assert conformal_quantile(s, 0.9) == 9.0  # ceil(10 * 0.9) = 9
    assert conformal_quantile(s, 0.5) == 5.0
    assert math.isinf(conformal_quantile(s, 0.95))  # ceil(9.5) = 10 > n


def test_coverage_at_the_stated_level_on_synthetic_data(fitted):
    f = fitted
    for lv in (0.8, 0.9):
        c = fit_control_config(f["v"][f["cal"]], f["vh"][f["cal"]], f["sig"][f["cal"]], level=lv, v_max=500.0)
        res = np.linalg.norm(f["v"][f["te"]] - f["vh"][f["te"]], axis=1)
        cov = np.mean(res <= c.q * f["sig"][f["te"]])
        assert abs(cov - lv) < 0.04


def test_shrinkage_never_faster_than_truth_when_covered(fitted):
    f = fitted
    c = fit_control_config(f["v"][f["cal"]], f["vh"][f["cal"]], f["sig"][f["cal"]], level=0.8, v_max=500.0)
    g, r = gate_batch(c, f["vh"][f["te"]], f["sig"][f["te"]])
    vt = f["v"][f["te"]]
    covered = np.linalg.norm(vt - f["vh"][f["te"]], axis=1) <= r
    sp_g, sp_t = np.linalg.norm(g, axis=1), np.linalg.norm(vt, axis=1)
    assert np.all(sp_g[covered] <= sp_t[covered] + 1e-9)
    assert np.mean(sp_g > sp_t + 1e-9) <= 1 - 0.8 + 0.04
    # the gated direction stays within asin(r / |v_hat|) of the truth when covered
    mv = covered & (sp_g > 0)
    vh = f["vh"][f["te"]][mv]
    cos = np.sum(g[mv] * vt[mv], 1) / (sp_g[mv] * sp_t[mv])
    bound = np.sqrt(np.clip(1 - (r[mv] / np.linalg.norm(vh, axis=1)) ** 2, 0, 1))
    assert np.all(cos >= bound - 1e-9)


def test_gate_matches_batch_and_reasons():
    c = cfg(no_signal_output=(5.0, 0.0), min_quality=0.3)
    assert gate(c, np.array([100.0, 0.0]), np.array([10.0, 10.0]), 0.9).reasons == ("shrunk",)
    assert np.allclose(gate(c, np.array([100.0, 0.0]), np.array([10.0, 10.0]), 0.9).velocity, [80.0, 0.0])
    assert gate(c, np.array([100.0, 0.0]), np.array([10.0, 10.0]), 0.1).reasons == ("no_signal",)
    assert gate(c, np.array([15.0, 0.0]), np.array([10.0, 10.0]), 0.9).reasons == ("no_signal_reference",)
    assert gate(c, np.array([-19.0, 0.0]), np.array([10.0, 10.0]), None).reasons == ("uncertain",)
    assert gate(c, np.array([100.0, 0.0]), None, None).reasons == ("unscored",)
    V = np.array([[100.0, 0.0], [15.0, 0.0], [-19.0, 0.0]])
    g, _ = gate_batch(c, V, np.full(3, 10.0), np.array([0.9, 0.9, 0.9]))
    assert np.allclose(g, [[80.0, 0.0], [0.0, 0.0], [0.0, 0.0]])


def test_clamp_never_faster_than_target_and_stops_at_once():
    c = cfg(v_max=100.0, a_max=1000.0)
    v, notes = clamp(c, np.array([300.0, 0.0]), np.zeros(2), 0.02)
    assert np.allclose(v, [20.0, 0.0]) and notes == ["clamp_speed", "clamp_accel"]
    v, _ = clamp(c, np.array([0.0, 50.0]), np.array([100.0, 0.0]), 0.02)
    assert np.linalg.norm(v) <= 50.0 + 1e-9
    v, _ = clamp(c, np.zeros(2), np.array([100.0, 0.0]), 0.02)
    assert np.all(v == 0)


# --- the streaming layer ----------------------------------------------------------------------


def test_no_motion_before_engage_and_after_stop():
    lay = ControlTrustLayer(cfg())
    out = run(lay, [header(), ctl(0), enable(True, 0.03), ctl(1), enable(False, 0.05), ctl(2), enable(True, 0.07), ctl(3)])
    st = [(d.state, d.engagement) for d in out]
    assert st == [("hold", 0), ("attenuate", 1), ("stop", 1), ("stop", 1), ("attenuate", 2)]
    assert all(d.velocity == (0.0, 0.0) for d in out if d.state in ("hold", "stop"))


def test_no_motion_on_zero_signal_quality_and_no_signal_reference():
    lay = ControlTrustLayer(cfg(min_quality=0.3, no_signal_output=(30.0, 0.0)))
    q = lambda v: {"type": "signal_quality", "t": 0.0, "value": v, "unit": "index"}  # noqa: E731
    out = run(lay, [header(), enable(), q(0.0), ctl(0), q(1.0), ctl(1, v=(31.0, 0.0)), ctl(2)])
    assert [d.reasons[0] for d in out] == ["no_signal", "no_signal_reference", "shrunk"]
    assert out[0].velocity == (0.0, 0.0) and out[1].velocity == (0.0, 0.0) and out[2].acts


def test_unscored_input_holds_by_default_and_pointer_maps():
    lay = ControlTrustLayer(cfg())
    out = run(lay, [header(uncertainty="none"), enable(), ctl(0, std=None),
                    {"type": "pointer", "t": 0.04, "dims": 2, "mode": "relative", "values": [1.0, 0.0]}])
    assert [d.state for d in out] == ["hold", "hold"] and out[1].raw == (50.0, 0.0)
    lay2 = ControlTrustLayer(cfg(unscored_gain=0.5))
    out2 = run(lay2, [header(uncertainty="none"), enable(), ctl(0, std=None)])
    assert out2[0].velocity == (50.0, 0.0) and out2[0].state == "attenuate"


def test_handoff_ramp_and_human_blend():
    lay = ControlTrustLayer(cfg(handoff_s=0.1, q=0.0))
    ev = [header(), enable(True, 0.0)]
    ev += [ctl(i, v=(100.0, 0.0), t=0.02 * (i + 1)) for i in range(6)]
    out = run(lay, ev)
    a = [d.authority for d in out]
    assert a == sorted(a) and a[0] < 0.5 and a[-1] == 1.0
    sp = [d.velocity[0] for d in out]
    assert sp == sorted(sp) and sp[-1] == pytest.approx(100.0)
    lay = ControlTrustLayer(cfg(handoff_s=1.0, q=0.0))
    out = run(lay, [header(), enable(True, 0.0), ctl(0, v=(0.0, 0.0), source="human", std=None, t=0.01),
                    ctl(0, v=(100.0, 0.0), t=0.5)])
    assert out[0].velocity[0] == pytest.approx(50.0) and "handoff" in out[0].reasons


def test_dead_man_poll_and_ttl():
    clock = [0.0]
    lay = ControlTrustLayer(cfg(), clock=lambda: clock[0])
    run(lay, [header(), enable(), ctl(0)])
    clock[0] = 0.05
    assert lay.poll() == []
    clock[0] = 0.2
    d = lay.poll()
    assert len(d) == 1 and d[0].state == "hold" and d[0].reasons == ("stale_input",) and d[0].velocity == (0.0, 0.0)
    assert lay.poll() == []  # once per stale period
    assert d[0].ttl_s == pytest.approx(0.06)


def test_absent_axis_holds_and_order_rules():
    lay = ControlTrustLayer(cfg())
    out = run(lay, [header(), enable(), ctl(0, v=(10.0, None), absent=[False, True])])
    assert out[0].state == "hold" and out[0].reasons == ("absent",)
    with pytest.raises(ControlEventError):
        lay.push(ctl(0, t=0.5))  # tick does not increase
    with pytest.raises(ControlEventError):
        ControlTrustLayer(cfg()).push(ctl(0))  # before the header
    with pytest.raises(ControlEventError):
        run(ControlTrustLayer(cfg()), [header(), enable(), ctl(0, std=None)])  # uncertainty std needs std
    with pytest.raises(ValueError):
        ControlTrustLayer(cfg(v_max=math.inf))  # bounded velocity is required


def test_click_intent_is_gated_by_engagement():
    from fidetype.trust.intent import IntentSpec, IntentTrustConfig, IntentTrustLayer, IntentVocabulary

    voc = IntentVocabulary((IntentSpec("intent.rest", "safe", "null"), IntentSpec("intent.click", "undoable")),
                           vocab_id="intent.cursor-v1")
    icfg = IntentTrustConfig(voc, thresholds={"safe": 0.5, "undoable": 0.6, "irreversible": math.inf})
    lay = ControlTrustLayer(cfg(), intent=IntentTrustLayer(icfg, read_frames=False))
    h = header(click_intent="intent.click")
    h["intent_declaration"] = voc.to_declaration()
    click = lambda i, t: {"type": "intent", "id": i, "t": t, "is_final": True, "score_semantics": "calibrated_prob",  # noqa: E731
                          "candidates": [{"intent": "intent.click", "score": 0.95}]}
    out = run(lay, [h, click("k0", 0.01), enable(True, 0.02), ctl(0), click("k1", 0.03)])
    kinds = [(type(d).__name__, d.action) for d in out]
    assert kinds == [("IntentDecision", "ABSTAIN"), ("ControlDecision", "COMMIT"), ("IntentDecision", "COMMIT")]
    assert [d.seq for d in out] == [0, 1, 2]


def test_layer_output_passes_the_profile_and_the_schemas(tmp_path, fitted):
    f = fitted
    c = fit_control_config(f["v"][f["cal"]], f["vh"][f["cal"]], f["sig"][f["cal"]], level=0.8, v_max=250.0,
                           a_max=5000.0, min_quality=0.2, no_signal_output=f["dec"].zero_input_output())
    lay = ControlTrustLayer(c)
    evs = [header(), enable(True, 0.0)]
    for i in range(300):
        evs.append({"type": "signal_quality", "t": 0.02 * (i + 1), "value": 0.0 if 100 <= i < 120 else 0.9, "unit": "index"})
        evs.append(ctl(i, v=f["vh"][i], std=float(f["sig"][i])))
    evs.append(enable(False, 6.1))
    out = [d.to_event() for d in run(lay, evs)]
    p = tmp_path / "log.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in out) + "\n", encoding="utf-8")
    rep = fep0005.check_file(p)
    assert not rep.failures("core"), [r.message for r in rep.failures("core")]
    assert all(e["velocity"] == [0.0, 0.0] for e in out[100:120])
    assert {e["state"] for e in out} >= {"attenuate", "hold", "stop"}
    jsonschema = pytest.importorskip("jsonschema")
    sch = json.loads((SDIR / "control-trust-decision.schema.json").read_text(encoding="utf-8"))
    for e in out:
        jsonschema.validate(e, sch)
    jsonschema.validate(header()[DECLARATION_KEY], json.loads((SDIR / "control-declaration.schema.json").read_text(encoding="utf-8")))
    jsonschema.validate(ctl(0), json.loads((SDIR / "control-event.schema.json").read_text(encoding="utf-8")))


def test_json_schemas_parse():
    names = sorted(x.name for x in SDIR.glob("*.schema.json"))
    assert names == ["control-declaration.schema.json", "control-enable.schema.json", "control-event.schema.json",
                     "control-trust-decision.schema.json"]
    for n in names:
        assert json.loads((SDIR / n).read_text(encoding="utf-8"))["$schema"].endswith("2020-12/schema")


def test_config_round_trip_and_content_id(tmp_path):
    c = cfg(no_signal_output=(1.0, 2.0), min_quality=0.2)
    c.save(tmp_path / "c.json")
    c2 = ControlTrustConfig.load(tmp_path / "c.json")
    assert c2 == c and c2.config_id.startswith("ccfg-")
    d = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    d["q"] = 3.0
    with pytest.raises(ValueError):
        ControlTrustConfig.from_dict(d)


def test_declaration_rules():
    assert validate_control_declaration(DECL) == []
    assert validate_control_declaration({**DECL, "units": "mm"})
    assert validate_control_declaration({**DECL, "click_intent": "intent.click"})  # no intent declaration
    assert validate_control_declaration({**DECL, "click_intent": "intent.click"}, ["intent.click"]) == []
    assert validate_control_declaration({**DECL, "click_intent": "intent.rest"}, ["intent.rest"], ["intent.rest"])
    assert validate_control_declaration({"dims": 2, "quantity": "position", "units": "norm", "frame": "workspace",
                                         "rate_hz": 60})


def test_synthetic_no_signal_span_gives_no_motion(fitted):
    s = simulate_control(T=3000, seed=9, no_signal_frac=0.2)
    f = fitted
    vh = f["dec"].predict(s.counts)
    tot = window_total(s.counts, 10)
    sig = f["scale"].sigma(vh, tot)
    med = float(np.median(f["tot"][f["cal"]]))
    c = fit_control_config(f["v"][f["cal"]], f["vh"][f["cal"]], f["sig"][f["cal"]], level=0.8, v_max=300.0,
                           min_quality=0.2, no_signal_output=f["dec"].zero_input_output())
    g, _ = gate_batch(c, vh, sig, np.clip(tot / med, 0, 1))
    inside = s.no_signal.copy()
    inside[np.flatnonzero(s.no_signal)[:10]] = False  # the 200 ms window still holds old spikes
    assert np.all(g[inside] == 0)


def test_cli_replay_and_profile(tmp_path, capsys):
    from fidetype.cli import main as fidetype_cli

    cfg().save(tmp_path / "c.json")
    s = tmp_path / "s.jsonl"
    s.write_text("\n".join(json.dumps(e) for e in [header(), enable(), ctl(0), ctl(1)]) + "\n", encoding="utf-8")
    assert fidetype_cli(["control", "replay", "--config", str(tmp_path / "c.json"), str(s)]) == 0
    lines = [json.loads(x) for x in capsys.readouterr().out.strip().splitlines()]
    assert [x["state"] for x in lines] == ["attenuate", "attenuate"] and lines[0]["profile"] == "control"
    assert fidetype_cli(["validate", "--profile", "fep-0005", str(s)]) == 0
    assert fidetype_cli(["conformance", "--profile", "fep-0005"]) == 0
