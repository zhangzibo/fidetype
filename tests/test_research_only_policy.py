"""P5-18 / FEP-0010 LIC-3: the exporter option refuse_research_only (FEP-0006 section 4 rule 6).

Synthetic data only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.collector import Collector, ConfigError, parse
from fidetype.collector import exporters as E
from fidetype.trust import licence as L

ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "spec" / "conformance" / "fep-0001" / "f01-segments.jsonl"
TRUST = ROOT / "examples" / "collector" / "trust-example.json"


def _stream_file(tmp_path: Path, meta: dict) -> Path:
    lines = [json.loads(x) for x in VECTOR.read_text(encoding="utf-8").splitlines() if x.strip()]
    lines[0] = {**lines[0], "meta": {**(lines[0].get("meta") or {}), **meta}}
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "s.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    return p


def _config(tmp_path: Path, meta: dict, product: dict | None = None) -> dict:
    src = _stream_file(tmp_path, meta)
    product = {"type": "os_text", "path": "out/typed.jsonl", **(product or {})}
    return {"service": {"log": "info"}, "receivers": {"in": {"type": "file", "paths": [str(src)]}},
            "processors": {"trust": {"type": "trust", "config": str(TRUST), "decoder": "greedy"}},
            "exporters": {"log": {"type": "jsonl", "path": "out/decisions.jsonl"}, "product": product},
            "pipelines": {"main": {"receivers": ["in"], "processors": ["trust"], "exporters": ["log", "product"]}}}


def _run(tmp_path: Path, meta: dict, product: dict | None = None):
    logs: list[str] = []
    col = Collector(parse(_config(tmp_path, meta, product), base_dir=tmp_path), log=logs.append)
    col.run()
    ex = col._exporters["product"]
    decisions = [json.loads(x) for x in (tmp_path / "out" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    return ex, decisions, logs


GATE = {"refuse_research_only": True}


def test_cc_by_nc_stream_types_nothing_through_a_product_exporter(tmp_path):
    ex, decisions, logs = _run(tmp_path, L.licence_meta("CC-BY-NC-4.0"), GATE)
    commits = [d for d in decisions if E.committed_text(d) is not None]
    assert commits, "the vector must give committed text, else the test proves nothing"
    assert ex.typed == [] and ex.counts["typed"] == 0
    assert ex.counts["research_only_refused"] == len(decisions)  # the decision log keeps every decision
    assert ex.counts["licence_unknown_refused"] == 0
    assert sum("refuse_research_only: dropped a decision" in m for m in logs) == 1  # one line, then counts only
    assert (tmp_path / "out" / "typed.jsonl").read_text(encoding="utf-8") == ""
    assert ex.stats()["refuse_research_only"] == {"unknown_licence": "refuse"}


def test_cc0_stream_types_as_before(tmp_path):
    base, _, _ = _run(tmp_path / "a", L.licence_meta("CC0-1.0"))
    gated, decisions, logs = _run(tmp_path / "b", L.licence_meta("CC0-1.0"), GATE)
    assert base.typed and gated.typed == base.typed
    assert gated.counts["research_only_refused"] == gated.counts["licence_unknown_refused"] == 0
    assert all(d["input"]["research_only"] is False for d in decisions)
    assert not any("dropped a decision" in m for m in logs)


def test_default_is_unchanged_research_only_stream_still_types(tmp_path):
    ex, _, _ = _run(tmp_path, L.licence_meta("CC-BY-NC-4.0"))
    assert ex.typed and "research_only_refused" not in ex.counts and "refuse_research_only" not in ex.stats()


def test_unknown_licence_rule(tmp_path):
    """A decision without input.research_only has an unknown licence: refused by default, exported with "pass"."""
    ex, decisions, _ = _run(tmp_path / "a", {}, GATE)
    assert decisions and all("research_only" not in d["input"] for d in decisions)
    assert ex.typed == [] and ex.counts["licence_unknown_refused"] == len(decisions)
    ex2, _, _ = _run(tmp_path / "b", {}, {**GATE, "unknown_licence": "pass"})
    base, _, _ = _run(tmp_path / "c", {})
    assert ex2.typed == base.typed and ex2.typed
    # "pass" lets unknown decisions through, never research-only ones.
    ex3, _, _ = _run(tmp_path / "d", L.licence_meta("CC-BY-NC-4.0"), {**GATE, "unknown_licence": "pass"})
    assert ex3.typed == []


def test_gate_unit_decision_types_and_input_events():
    logs: list[str] = []
    # A decisions-only exporter: input events pass (P5-22 judges them per stream only where they are written).
    ex = E.StdoutExporter("s", logs.append, sorted(E.DECISION_TYPES)).refuse_research_only("refuse")
    seen: list = []
    ex.export = lambda items: seen.extend(items)  # type: ignore[method-assign]
    items = [("a", {"type": "header", "meta": {"data.research_only": True}}),
             ("a", {"type": "trust_decision", "input": {"research_only": True}}),
             ("a", {"type": "intent_decision", "input": {"research_only": False}}),
             ("a", {"type": "control_decision", "input": {"research_only": "yes"}}),  # not a boolean: unknown
             ("a", {"type": "trust_decision"})]
    ex.deliver(items)
    assert [ev["type"] for _, ev in seen] == ["header", "intent_decision"]
    assert ex.counts["research_only_refused"] == 1 and ex.counts["licence_unknown_refused"] == 2
    seen.clear()
    ex.deliver([items[1]])  # all dropped: export is not called with an empty list
    assert seen == []
    assert E.decision_research_only({"input": {"research_only": False}}) is False
    assert E.decision_research_only({"input": None}) is None
    with pytest.raises(ValueError):
        E.LicenceGate("x", logs.append, {}, "maybe")


@pytest.mark.parametrize("opts, msg", [
    ({"refuse_research_only": "yes"}, "true or false"),
    ({"unknown_licence": "pass"}, "needs refuse_research_only = true"),
    ({"refuse_research_only": True, "unknown_licence": "allow"}, "must be one of"),
])
def test_config_errors(tmp_path, opts, msg):
    with pytest.raises(ConfigError, match=msg):
        parse(_config(tmp_path, {}, opts), base_dir=tmp_path)


def test_config_takes_the_option_on_an_input_event_file(tmp_path):
    # P5-18 refused the option here; P5-22 makes it act per stream (tests/test_input_event_licence_gate.py).
    cfg = _config(tmp_path, {})
    cfg["exporters"]["log"].update(types=["header", "frame", "end"], refuse_research_only=True)
    parse(cfg, base_dir=tmp_path)
    for typ in ("jsonl", "stdout", "lsl", "websocket", "os_text"):
        assert {"refuse_research_only", "unknown_licence"} <= parse.__globals__["SCHEMA"]["exporters"][typ][0]
