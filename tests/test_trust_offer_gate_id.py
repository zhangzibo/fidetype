"""Tests of the offer-gate identity: ``offer_gate_id`` and ``TrustGuard.guard_id`` (P5-39, gap 200).

``config_id`` covers the frozen trust config only; an offer gate never changes it. The gate digest
``offer_gate_id`` names the ordered gate list (feature, threshold, LM name), and ``guard_id`` joins the two.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust.offer_gate import OfferGate, offer_gate_id

from test_trust_dropin import nbest_data, noise_nbest

ID_RE = re.compile(r"^ogate-[0-9a-f]{16}$")


@pytest.fixture(scope="module")
def guard():
    xs, ts = nbest_data(240, 0)
    rng = np.random.default_rng(1)
    nulls = [noise_nbest(rng) for _ in range(40)]
    return ft.calibrate(xs, ts, null_inputs=nulls, null_trials=40, decoder_name="test-nbest", modality="emg"), xs


def test_offer_gate_id_is_stable_and_ordered():
    a, b = OfferGate("p_top1", 0.5), OfferGate("margin", 0.1)
    assert offer_gate_id([]) is None and offer_gate_id(None) is None
    one = offer_gate_id([a])
    assert ID_RE.match(one)
    # the same list gives the same id, also from the file form (dicts) and with another note
    assert offer_gate_id([OfferGate("p_top1", 0.5, note="other text")]) == one
    assert offer_gate_id([a.to_dict()]) == one
    assert offer_gate_id(a) == one
    # feature, threshold, LM name and order all change the id
    ids = {offer_gate_id(g) for g in ([a], [b], [a, b], [b, a], [OfferGate("p_top1", 0.51)],
                                      [OfferGate("-p_top1", 0.5)], [OfferGate("char_lm", -2.0, lm_name="x")],
                                      [OfferGate("char_lm", -2.0, lm_name="y")])}
    assert len(ids) == 8
    # a pinned value: the digest rule must not change silently
    assert offer_gate_id([OfferGate("coherence", 0.187)]) == offer_gate_id(
        [{"schema": "fidetype.offer-gate/0.1", "feature": "coherence", "threshold": 0.187, "card": "x"}])


def test_guard_id_differs_only_by_gate_list(guard, tmp_path):
    g, xs = guard
    path = tmp_path / "g.json"
    g.save(path)
    plain = ft.load(path)
    g1 = ft.load(path, offer_gate=OfferGate("p_top1", 0.5))
    g2 = ft.load(path, offer_gate=[OfferGate("p_top1", 0.5), OfferGate("margin", 0.1)])
    g3 = ft.load(path, offer_gate=[OfferGate("margin", 0.1), OfferGate("p_top1", 0.5)])
    # config_id does not change with the gate list
    assert plain.config_id == g1.config_id == g2.config_id == g3.config_id == g.config_id
    # no gate: guard_id is config_id, no gate digest (old ids and old audit records keep their form)
    assert plain.offer_gate_id is None and plain.guard_id == plain.config_id
    # different gate lists: different guard identities
    ids = [x.guard_id for x in (plain, g1, g2, g3)]
    assert len(set(ids)) == 4
    assert g2.guard_id == f"{g2.config_id}+{g2.offer_gate_id}" and ID_RE.match(g2.offer_gate_id)
    # save / load keeps the gate digest
    g2.save(tmp_path / "g2.json")
    assert ft.load(tmp_path / "g2.json").guard_id == g2.guard_id
    assert "offer_gate_id=" in repr(g2) and "offer_gate_id" not in repr(plain)


def test_audit_record_names_the_gate_list(guard, tmp_path):
    g, xs = guard
    path = tmp_path / "g.json"
    g.save(path)
    plain = ft.load(path)
    gated = ft.load(path, offer_gate=[OfferGate("p_top1", 0.5), OfferGate("margin", 0.1)])
    for x in xs[:3]:
        plain.decide(x)
        gated.decide(x)
    h = gated.audit_header()
    assert h["config_id"] == gated.config_id
    assert h["offer_gate_id"] == gated.offer_gate_id and h["guard_id"] == gated.guard_id
    assert all(r["offer_gate_id"] == gated.offer_gate_id for r in gated.audit_log)
    hp = plain.audit_header()
    assert "offer_gate_id" not in hp and "guard_id" not in hp
    assert all("offer_gate_id" not in r for r in plain.audit_log)
    lines = gated.write_audit(tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["offer_gate_id"] == gated.offer_gate_id
    assert all(json.loads(x)["offer_gate_id"] == gated.offer_gate_id for x in lines[1:])


def test_manifest_gate_ids_and_config_ids_unchanged():
    from fidetype.pretrained.manifest import all_manifests

    m = {x.name: x for x in all_manifests()}["willett-hw"]
    # the existing config ids stay the same: the gate digest is separate
    assert m.trust["config_id"] == "tcfg-39aac48688b8bd12"
    assert m.raw["readouts"]["lm"]["trust"]["config_id"] == "tcfg-f498c0637536daec"
    d, lm = m.offer_gate_id(), m.offer_gate_id("lm")
    assert ID_RE.match(d) and ID_RE.match(lm) and d != lm  # the coherence thresholds differ
    assert d == offer_gate_id(m.trust["offer_gate"])
    assert m.guard_id() == f"tcfg-39aac48688b8bd12+{d}"
    assert m.guard_id("lm") == f"tcfg-f498c0637536daec+{lm}"
    card = m.card()
    assert f"guard id: tcfg-39aac48688b8bd12+{d}" in card
    assert f"guard id (readout lm): tcfg-f498c0637536daec+{lm}" in card
    # the packaged t15-m4-13 guard: config_id as in its manifest, guard_id adds the manifest gate digest
    from fidetype.pretrained import manifest_offer_gates

    t = {x.name: x for x in all_manifests()}["t15-m4-13"]
    from importlib import resources

    gp = resources.files("fidetype.pretrained").joinpath(str(t.trust["config"]))
    g = ft.load(str(gp), decode_fn=lambda lp: [], offer_gate=manifest_offer_gates(t.trust["offer_gate"]))
    assert g.config_id == t.trust["config_id"] == "tcfg-1016759f08a3f9a1"
    assert g.offer_gate_id == t.offer_gate_id() and g.guard_id == t.guard_id()
    # a model without an offer gate: no gate digest, guard id = config id
    k = {x.name: x for x in all_manifests()}.get("kt-semg-lda")
    if k is not None and k.trust:
        assert k.offer_gate_id() is None and k.guard_id() == k.trust.get("config_id")
