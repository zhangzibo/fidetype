"""P5-13 / FEP-0010: data licence keys in the stream (MET-12) and in trust decisions (TD-15).

Synthetic data only.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from fidetype.collector import Collector, parse
from fidetype.conformance.checks import DEFINED_KEYS
from fidetype.trust import licence as L
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.provenance import LedgerView, ProvenanceLedger, read_entries, verify
from fidetype.trust.streaming import StreamingTrustLayer, frame_decoder

ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "spec" / "conformance" / "fep-0001" / "f01-segments.jsonl"
TRUST = ROOT / "examples" / "collector" / "trust-example.json"

# adapter module -> benchmark track of the same dataset
ADAPTERS = {"emg2qwerty": "emg2qwerty", "kt_semg": "kt-semg", "toronto_semg": "toronto-semg",
            "willett_handwriting": "willett-hw", "spanishbcbl_meg": "spanishbcbl-meg", "b2t25": "b2t25-t15"}


def test_licence_meta_and_stream_licence():
    assert L.licence_meta("CC BY-NC 4.0") == {"data.licence": "CC-BY-NC-4.0", "data.research_only": True}
    assert L.licence_meta("CC0 1.0") == {"data.licence": "CC0-1.0", "data.research_only": False}
    assert L.licence_meta("CC-BY-4.0", "CC-BY-NC-4.0")["data.research_only"] is True  # NC decoder data
    assert L.licence_meta("CC0-1.0", research_only=True)["data.research_only"] is True  # stricter is allowed
    assert L.stream_licence({}) is None and L.stream_licence(None) is None
    assert L.stream_licence({"data.licence": "CC0-1.0"})["research_only"] is False
    assert L.stream_licence({"data.licence": "CC-BY-NC-4.0", "data.research_only": False})["research_only"] is True
    s = L.stream_licence({"data.licence": "CC-BY-4.0", "data.research_only": True})
    assert s["research_only"] and not s["commercial_ok"] and not any(s["product_ok"].values())
    assert s["licences"] == ["CC-BY-4.0"]
    assert L.stream_licence({"data.research_only": False})["research_only"] is True  # no licence: unknown
    assert L.stream_licence({"data.licence": "", "data.research_only": "yes"}) is None  # wrong types: absent
    assert {"data.licence", "data.research_only"} <= set(DEFINED_KEYS)


@pytest.mark.parametrize("module, track", sorted(ADAPTERS.items()))
def test_adapters_write_the_licence_of_their_benchmark_track(module, track):
    import importlib

    m = importlib.import_module(f"fidetype.adapters.{module}")
    lic = getattr(m, "LICENCE", None) or getattr(m, "_SPANISHBCBL_LICENCE")
    assert L.licence_meta(lic) == L.track_meta(track)
    assert "_licence_meta(" in inspect.getsource(m.stream_meta)


def test_adapter_stream_meta_passes_the_validators():
    from fidetype.adapters import spanishbcbl_meg as S

    sig = inspect.signature(S.stream_meta)
    args = {k: "x" for k, p in sig.parameters.items() if p.default is inspect.Parameter.empty}
    m = S.stream_meta(**args)
    assert m["data.licence"] == "CC-BY-NC-4.0" and m["data.research_only"] is True
    assert "spanishbcbl.licence" not in m
    for k in ("data.licence", "data.research_only"):
        assert DEFINED_KEYS[k](m[k]) is None


def _stream_file(tmp_path, meta, name="s.jsonl"):
    lines = [json.loads(x) for x in VECTOR.read_text(encoding="utf-8").splitlines() if x.strip()]
    lines[0] = {**lines[0], "meta": {**(lines[0].get("meta") or {}), **meta}}
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / name
    p.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    return p


def _run(tmp_path, meta, ledger=True):
    src = _stream_file(tmp_path, meta)
    trust = {"type": "trust", "config": str(TRUST), "decoder": "greedy"}
    if ledger:
        trust["ledger"] = {"path": "out/ledger.jsonl"}
    cfg = {"service": {"log": "quiet"}, "receivers": {"in": {"type": "file", "paths": [str(src)]}},
           "processors": {"trust": trust}, "exporters": {"log": {"type": "jsonl", "path": "out/decisions.jsonl"}},
           "pipelines": {"main": {"receivers": ["in"], "processors": ["trust"], "exporters": ["log"]}}}
    Collector(parse(cfg, base_dir=tmp_path)).run()
    out = tmp_path / "out"
    return [json.loads(x) for x in (out / "decisions.jsonl").read_text(encoding="utf-8").splitlines() if x]


def test_collector_trust_decisions_carry_research_only_and_ledger_reads_the_source(tmp_path):
    ds = _run(tmp_path, L.licence_meta("CC-BY-NC-4.0"))
    assert ds and all(d["input"]["research_only"] is True for d in ds)
    ents = read_entries(tmp_path / "out" / "ledger.jsonl")
    assert verify(ents).ok
    srcs = [e for e in ents if e["kind"] == "source"]
    assert len(srcs) == 1 and srcs[0]["body"]["source"]["licence"] == "CC-BY-NC-4.0"
    assert srcs[0]["body"]["source"]["details"] == {"from": "stream meta"}
    ctx = next(e for e in ents if e["kind"] == "context")
    assert ctx["body"]["context"]["stream_sources"] == [srcs[0]["body"]["source_id"]]
    assert ctx["body"]["licence"]["research_only"] is True
    dec = [e for e in ents if e["kind"] == "decision"]
    assert dec and all(e["body"]["licence"]["research_only"] for e in dec)
    view = LedgerView(ents)
    lin = view.lineage(dec[0]["body"]["decision_id"])
    assert [s["body"]["source_id"] for s in lin["sources"]] == [srcs[0]["body"]["source_id"]]
    # A rewrite of the source flags (with a recomputed digest) is caught by verify: the flags follow the licence.
    from fidetype.trust.provenance import body_digest, entry_hash

    forged = json.loads(json.dumps(ents))
    i = next(k for k, e in enumerate(forged) if e["kind"] == "source")
    forged[i]["body"]["licence"]["research_only"] = False
    forged[i]["body"]["licence"]["commercial_ok"] = True
    prev = None
    for e in forged:
        if prev is not None:
            e["prev_hash"] = prev
        if "salt" in e:
            e["body_sha256"] = body_digest(e["salt"], e["body"])
        e["hash"] = prev = entry_hash(e)
    assert any("source licence flags" in x for x in verify(forged).errors)


def test_collector_permissive_licence_and_no_licence(tmp_path):
    ds = _run(tmp_path / "a", L.licence_meta("CC0-1.0"))
    assert ds and all(d["input"]["research_only"] is False for d in ds)
    ds = _run(tmp_path / "b", {"data.licence": "CC-BY-4.0", "data.research_only": True}, ledger=False)
    assert all(d["input"]["research_only"] is True for d in ds)  # the stream may be stricter than its licence
    ds = _run(tmp_path / "c", {}, ledger=True)
    assert ds and all("research_only" not in d["input"] for d in ds)  # unknown: the key is absent


def test_streaming_layer_uses_the_ledger_lineage(tmp_path):
    """A CC0 stream decoded by a decoder trained on NC data: the decisions are research only (lineage)."""
    led = ProvenanceLedger(None)
    nc = led.record_source("nc data", "CC-BY-NC-4.0")
    w = led.record_artifact("weights", "decoder", derived_from=[nc])
    led.set_lineage([w])
    layer = StreamingTrustLayer(FrozenTrustConfig.load(TRUST), decode_fn=frame_decoder("greedy"), ledger=led)
    src = _stream_file(tmp_path, L.licence_meta("CC0-1.0"))
    out = []
    for line in src.read_text(encoding="utf-8").splitlines():
        out += layer.push(line, "s")
    assert out and all(d.to_event()["input"]["research_only"] is True for d in out)
    assert verify(led.entries).ok
    ctx = next(e for e in led.entries if e["kind"] == "context")
    assert ctx["body"]["context"]["lineage"] == [w] and len(ctx["body"]["context"]["stream_sources"]) == 1


def test_intent_and_control_layers_copy_research_only():
    from fidetype.trust.control import CONTROL, CONTROL_ENABLE, ControlTrustConfig, ControlTrustLayer
    from fidetype.trust.control import DECLARATION_KEY as CDK
    from fidetype.trust.intent import DECLARATION_KEY, IntentTrustConfig, IntentTrustLayer
    from fidetype.trust.intent_sim import demo_vocabulary

    V = demo_vocabulary()
    lay = IntentTrustLayer(IntentTrustConfig(V, thresholds={"safe": 0.6, "undoable": 0.8, "irreversible": 0.95}))
    hdr = {"type": "header", "spec_version": "0.1", "vocab": list(V.ids), "vocab_type": "command", "blank_id": None,
           "source": "test", DECLARATION_KEY: V.to_declaration(), "meta": L.licence_meta("CC-BY-NC-SA-4.0")}
    iid = V.ids[0]
    ev = {"type": "intent", "id": "u0", "t": 0.0, "is_final": True, "score_semantics": "uncalibrated_prob",
          "candidates": [{"intent": iid, "score": 0.99}]}
    ds = lay.push(hdr, "s") + lay.push(ev, "s")
    assert ds and ds[-1].to_event()["input"]["research_only"] is True
    lay2 = IntentTrustLayer(IntentTrustConfig(V, thresholds={"safe": 0.6, "undoable": 0.8, "irreversible": 0.95}))
    ds = lay2.push({k: v for k, v in hdr.items() if k != "meta"}, "s") + lay2.push(ev, "s")
    assert "research_only" not in ds[-1].to_event()["input"]

    decl = {"dims": 2, "quantity": "velocity", "units": "mm/s", "frame": "workspace", "rate_hz": 50.0,
            "uncertainty": "std"}
    c = ControlTrustLayer(ControlTrustConfig(q=2.0, v_max=300.0, handoff_s=0.0, level=0.9, no_signal_output=None))
    chdr = {"type": "header", "spec_version": "0.1", "vocab": ["control"], "vocab_type": "command", "blank_id": None,
            "source": "test", CDK: decl, "meta": L.licence_meta("CC0-1.0")}
    out = []
    for e in (chdr, {"type": CONTROL_ENABLE, "t": 0.0, "enabled": True, "source": "switch"},
              {"type": CONTROL, "t": 0.02, "tick": 0, "values": [100.0, 0.0], "std": [10.0, 10.0]}):
        out += c.push(e)
    assert out and all(d.to_event()["input"]["research_only"] is False for d in out)
