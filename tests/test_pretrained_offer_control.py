"""The offer null control on the packaged manifests and model cards (P14-56, gap 153).

The manifests copy the P5-31 re-check counts (``experiments/2026-11-21-p5-31-offer-control/results``).
These tests check that the copy equals the re-check JSON files, and that the parser refuses a bad block.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from fidetype.pretrained.manifest import ManifestError, all_manifests, manifest_dir, parse_manifest

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "experiments" / "2026-11-21-p5-31-offer-control" / "results"
RESULTS_P533 = REPO / "experiments" / "2026-11-21-p5-33-withhold" / "results"
RESULTS_P1460 = REPO / "experiments" / "2026-11-23-p14-60-ship-direction-gate" / "results"

# (model, guard key in Manifest.offer_controls, recheck file, the trust block that holds the guard)
CASES = [
    ("willett-hw", "default", "../../2026-11-23-p14-60-ship-direction-gate/results/recheck-builtin-gated.json"),
    ("willett-hw", "lm", "../../2026-11-23-p14-60-ship-direction-gate/results/recheck-lm-gated.json"),
    ("t15-m4-13", "default", "../../2026-11-21-p5-33-withhold/results/recheck-t15-gated.json"),
    ("kt-semg-lda", "default", "recheck-kt.json"),
]


def _trust_block(m, key):
    return m.trust if key == "default" else m.raw["readouts"][key]["trust"]


@pytest.mark.parametrize("model,key,fname", CASES)
def test_manifest_offer_control_equals_recheck(model, key, fname):
    path = (RESULTS / fname).resolve()
    if not path.is_file():
        pytest.skip("re-check results are only in the source tree")
    rc = json.loads(path.read_text(encoding="utf-8"))
    m = {x.name: x for x in all_manifests()}[model]
    oc = m.offer_controls[key]
    assert _trust_block(m, key)["config_id"] == rc["config_id"]
    assert oc["verdict"] == ("pass" if rc["passed"] else "fail")
    assert oc["mode"] == rc["mode"] == "warn"
    assert oc["real"] == {"n": rc["real"]["n"], "n_offer": rc["real"]["n_offer"]}
    assert oc["ltt_commits"] == rc["ltt_commits"]
    assert oc["commits_match_sheet"] is rc["commits_match_sheet"] is True
    assert oc["source"] == path.relative_to(REPO).as_posix()
    assert [(c["name"], c["n"], c["n_offer"], c["passed"]) for c in oc["controls"]] == \
        [(c["name"], c["n"], c["n_offer"], c["passed"]) for c in rc["controls"]]
    assert [c["p_value"] for c in oc["controls"]] == pytest.approx([c["p_value"] for c in rc["controls"]])
    # the model card shows the verdict and every count
    card = m.card()
    line = next(x for x in card.splitlines() if x.lstrip().startswith("offer control")
                and (key == "default") == ("readout" not in x))
    assert oc["verdict"].upper() in line and f"real {rc['real']['n_offer']}/{rc['real']['n']}" in line
    for c in rc["controls"]:
        assert f"{c['n_offer']}/{c['n']} {'pass' if c['passed'] else 'FAIL'}" in line


def test_every_packaged_guard_has_an_offer_control():
    ms = {m.name: m for m in all_manifests()}
    have = {(n, k) for n, m in ms.items() for k in m.offer_controls}
    assert have == {(n, k) for n, k, _ in CASES}
    # the known P5-31 counts (gap 153 brief)
    get = {(n, k): {c["label"]: (c["n_offer"], c["n"]) for c in ms[n].offer_controls[k]["controls"]}
           for n, k, _ in CASES}
    # P14-54: both willett-hw guards have an offer gate; the P5-31 counts are kept in before_gate
    for key, before in (("default", 297), ("lm", 289)):
        assert get[("willett-hw", key)]["frame-shuffled decoder frames"] == (0, 300)
        bg = ms["willett-hw"].offer_controls[key]["before_gate"]
        assert dict((c["name"], (c["n_offer"], c["n"])) for c in bg["controls"])["shuffled"] == (before, 300)
        assert bg["verdict"] == "fail"
    # P5-33: the t15 guard has an offer gate; its block shows the gated re-check, and the counts before the gate
    assert get[("t15-m4-13", "default")] == {"uniform score matrices": (0, 300),
                                             "frame-shuffled decoder frames": (0, 300)}
    before = ms["t15-m4-13"].offer_controls["default"]["before_gate"]
    assert [(c["name"], c["n_offer"], c["n"]) for c in before["controls"]] == [("uniform", 300, 300),
                                                                               ("shuffled", 300, 300)]
    assert get[("kt-semg-lda", "default")]["uniform n-best lists"] == (300, 300)
    assert get[("kt-semg-lda", "default")]["user nulls: key windows drawn at random"] == (173, 173)
    verdicts = {(n, k): oc["verdict"] for n, m in ms.items() for k, oc in m.offer_controls.items()}
    assert verdicts == {("willett-hw", "default"): "pass", ("willett-hw", "lm"): "pass",
                        ("t15-m4-13", "default"): "pass", ("kt-semg-lda", "default"): "fail"}


def test_t15_manifest_offer_gate():
    """P5-33: the manifest gate equals the gate of the gated re-check, and guard() applies it by default."""
    import fidetype.trust as ft
    from fidetype.trust.offer_gate import OfferGate

    rc = RESULTS_P533 / "recheck-t15-gated.json"
    if not rc.is_file():
        pytest.skip("re-check results are only in the source tree")
    m = {x.name: x for x in all_manifests()}["t15-m4-13"]
    g = m.trust["offer_gate"]
    want = json.loads(rc.read_text(encoding="utf-8"))["offer_gate"][0]
    assert (g["feature"], g["threshold"]) == (want["feature"], want["threshold"]) == ("coherence", want["threshold"])
    assert OfferGate.from_dict(g).label().startswith("coherence >= ")
    assert "offer gate: withhold an offer if coherence <" in m.card()
    # the packaged guard file has no gate (its bytes and config_id do not change)
    path = REPO / "src/fidetype/pretrained/guards/t15-m4-13.guard.json"
    assert "offer_gate" not in json.loads(path.read_text(encoding="utf-8"))
    # PretrainedDecoder.guard: the manifest gate by default, offer_gate=False switches it off
    from types import SimpleNamespace

    from fidetype.pretrained import PretrainedDecoder

    stub = SimpleNamespace(manifest=m, guard_path=lambda: path)
    on = PretrainedDecoder.guard(stub, decode_fn=lambda lp: [])
    off = PretrainedDecoder.guard(stub, decode_fn=lambda lp: [], offer_gate=False)
    assert [x.to_dict() for x in on.offer_gates] == [OfferGate.from_dict(g).to_dict()] and off.offer_gates == ()
    assert on.config_id == off.config_id == m.trust["config_id"] == ft.load(path, decode_fn=lambda lp: []).config_id


def test_willett_manifest_offer_gates():
    """P14-54 / P14-60: both willett-hw guards carry the gate list of their gated re-check (coherence, then
    lm_beam_direction >= 0); guard() applies it by default and passes the LM readout to the direction gate."""
    import os
    from types import SimpleNamespace

    import fidetype.trust as ft
    from fidetype.pretrained import PretrainedDecoder, XBodyCtcDecoder
    from fidetype.trust.offer_gate import OfferGate

    m = {x.name: x for x in all_manifests()}["willett-hw"]
    blocks = {"default": m.trust, "lm": m.raw["readouts"]["lm"]["trust"]}
    for key, which in (("default", "builtin"), ("lm", "lm")):
        gl = blocks[key]["offer_gate"]
        assert isinstance(gl, list) and [OfferGate.from_dict(g).feature for g in gl] == ["coherence",
                                                                                         "lm_beam_direction"]
        assert gl[1]["threshold"] == 0.0 and gl[1]["lm_name"] == "eng_tatoeba_6gram_mkn_noE2Q_noWillett"
        rc = RESULTS_P1460 / f"recheck-{which}-gated.json"
        if rc.is_file():
            want = json.loads(rc.read_text(encoding="utf-8"))["offer_gate"]
            assert [(g["feature"], g["threshold"]) for g in gl] == [(w["feature"], w["threshold"]) for w in want]
    card = m.card()
    assert "offer gate: withhold an offer if coherence <" in card
    assert "offer gate (readout lm): withhold an offer if coherence <" in card
    assert "offer gate: withhold an offer if lm_beam_direction < 0 " in card
    assert "offer gate (readout lm): withhold an offer if lm_beam_direction < 0 " in card
    # the model card states the rule, the cost, and that the built-in guard was tested on training data only
    line = next(x for x in card.splitlines() if x.startswith("  offer gate: direction gate:"))
    assert "Fixed threshold 0, not fitted" in line and "Cost:" in line and "Tested on training data only" in line
    assert any(x.startswith("  offer gate (readout lm): direction gate:") for x in card.splitlines())
    # the guard files are local only (not in the wheel): check the default on/off switch if they are here
    base = Path(os.environ.get("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")) / "willett-hw"
    paths = {"default": base / "willett-hw.guard.json", "lm": base / "willett-hw.lm3.guard.json"}
    if not all(p.is_file() for p in paths.values()):
        pytest.skip("willett-hw guard files are local only")
    ro = SimpleNamespace(hyps=lambda lp, n, use_gate=False: [], decode_fn=lambda: (lambda lp: []))  # LM readout stub
    calls = []

    def lm_readout():
        calls.append(1)
        return ro

    stub = SimpleNamespace(manifest=m, guard_path=lambda: paths["default"], lm_readout=lm_readout,
                           files={p.name: p for p in paths.values()})
    for key in ("default", "lm"):
        calls.clear()
        if key == "default":
            on = PretrainedDecoder.guard(stub, decode_fn=lambda lp: [])
            off = PretrainedDecoder.guard(stub, decode_fn=lambda lp: [], offer_gate=False)
        else:
            on = XBodyCtcDecoder.guard(stub, readout="lm")  # decode_fn and the direction gate share one readout
            off = XBodyCtcDecoder.guard(stub, decode_fn=lambda lp: [], readout="lm", offer_gate=False)
        assert [x.to_dict() for x in on.offer_gates] == [OfferGate.from_dict(g).to_dict()
                                                         for g in blocks[key]["offer_gate"]]
        assert on.offer_gates[0].readout is None and on.offer_gates[1].readout is ro
        assert len(calls) == 1  # one readout object, built once
        assert off.offer_gates == ()
        assert on.config_id == off.config_id == blocks[key]["config_id"]
        assert "offer_gate" not in json.loads(paths[key].read_text(encoding="utf-8"))
        assert ft.load(paths[key], decode_fn=lambda lp: []).config_id == blocks[key]["config_id"]


def test_manifest_offer_gates_needs_a_readout():
    """P14-60: a direction gate in a manifest gate list needs the LM readout; a missing one is a clear error."""
    from fidetype.pretrained import NoTrustConfig, PretrainedError, manifest_offer_gates

    m = {x.name: x for x in all_manifests()}["willett-hw"]
    gl = m.trust["offer_gate"]
    assert manifest_offer_gates(gl[:1]) and manifest_offer_gates(None) == []
    with pytest.raises(NoTrustConfig, match="needs an LM-beam readout"):
        manifest_offer_gates(gl)

    def missing():
        raise PretrainedError("LM file not found")

    with pytest.raises(NoTrustConfig, match="offer_gate=False"):
        manifest_offer_gates(gl, missing)


def test_parser_refuses_bad_offer_control():
    good = json.loads((manifest_dir() / "willett-hw.json").read_text(encoding="utf-8"))
    parse_manifest(good)
    for mutate, msg in [
        (lambda d: d["trust"].update(offer_gate={"feature": "nope", "threshold": 0.0}), "offer_gate"),
        (lambda d: d["readouts"]["lm"]["trust"].update(offer_gate={"feature": "nope", "threshold": 0.0}),
         r"readouts\.lm\.trust\.offer_gate"),
        (lambda d: d["trust"]["offer_control"].update(verdict="fail"), "does not match"),
        (lambda d: d["trust"]["offer_control"].update(verdict="maybe"), "verdict must be"),
        (lambda d: d["trust"]["offer_control"]["controls"][1].update(n_offer=301), r"n_offer must be"),
        (lambda d: d["trust"]["offer_control"]["controls"][0].pop("passed"), "passed"),
        (lambda d: d["trust"]["offer_control"].update(controls=[]), "must not be empty"),
        (lambda d: d["readouts"]["lm"]["trust"]["offer_control"].update(verdict="fail"), "readouts.lm.trust"),
        (lambda d: d["trust"].update(offer_control="fail"), "an object is needed"),
        (lambda d: d["trust"]["offer_gate"][1].update(feature="nope"), r"trust\.offer_gate\[1\]"),
        (lambda d: d["trust"].update(offer_gate=[]), "empty list"),
        (lambda d: d["trust"]["offer_gate"].append("x"), "an object is needed"),
        (lambda d: d["readouts"]["lm"]["trust"]["offer_gate"][1].pop("lm_name"), "lm_name"),
    ]:
        d = copy.deepcopy(good)
        mutate(d)
        with pytest.raises(ManifestError, match=msg):
            parse_manifest(d)


def test_gated_guard_must_pass_offer_control():
    """User decision 2026-11-22 (gap 152): offer_control stays "warn" by default; a guard that ships an
    offer gate is held to "refuse", so its manifest needs a passing offer_control block."""
    import inspect

    import fidetype.trust as ft

    assert inspect.signature(ft.calibrate).parameters["offer_control"].default == "warn"
    good = json.loads((manifest_dir() / "willett-hw.json").read_text(encoding="utf-8"))
    for block in (lambda d: d["trust"], lambda d: d["readouts"]["lm"]["trust"]):
        d = copy.deepcopy(good)
        oc = block(d)["offer_control"]
        oc["verdict"] = "fail"
        oc["controls"][1]["passed"] = False  # consistent block: only the policy refuses it
        with pytest.raises(ManifestError, match="ships an offer_gate"):
            parse_manifest(d)
        d = copy.deepcopy(good)
        block(d).pop("offer_control")
        with pytest.raises(ManifestError, match="ships an offer_gate"):
            parse_manifest(d)
    # a guard without an offer gate may ship a failing block ("warn": kt-semg-lda)
    kt = json.loads((manifest_dir() / "kt-semg-lda.json").read_text(encoding="utf-8"))
    assert "offer_gate" not in kt["trust"] and kt["trust"]["offer_control"]["verdict"] == "fail"
    parse_manifest(kt)
