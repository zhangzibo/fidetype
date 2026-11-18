"""P5-22: refuse_research_only on input-event exporters, per stream by its header (FEP-0006 section 4 rule 6).

Synthetic data only (the FEP-0001 conformance vector f01 with licence keys added to its header).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.collector import Collector, ConfigError, parse
from fidetype.collector import exporters as E
from fidetype.collector.receivers import STATUS
from fidetype.trust import licence as L

ROOT = Path(__file__).resolve().parents[1]
VECTOR = ROOT / "spec" / "conformance" / "fep-0001" / "f01-segments.jsonl"
INPUT_TYPES = ["header", "frame", "segment_end", "end"]
GATE = {"refuse_research_only": True}
NC, CC0 = L.licence_meta("CC-BY-NC-4.0"), L.licence_meta("CC0-1.0")


def _vector() -> list[dict]:
    return [json.loads(x) for x in VECTOR.read_text(encoding="utf-8").splitlines() if x.strip()]


def _stream(folder: Path, name: str, meta: dict) -> Path:
    lines = _vector()
    lines[0] = {**lines[0], "meta": {**(lines[0].get("meta") or {}), **meta}}
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    return p


def _run(tmp_path: Path, metas: list[dict], gate: dict | None = None, path: str = "out/streams/{session}.jsonl"):
    srcs = [str(_stream(tmp_path / "in", f"s{i}.jsonl", m)) for i, m in enumerate(metas)]
    exporters: dict = {"streams": {"type": "jsonl", "path": path, "types": INPUT_TYPES, **(gate or {})}}
    pipe: dict = {"receivers": ["in"], "exporters": ["streams"]}
    cfg = {"service": {"log": "info"}, "receivers": {"in": {"type": "file", "paths": srcs}},
           "exporters": exporters, "pipelines": {"main": pipe}}
    logs: list[str] = []
    col = Collector(parse(cfg, base_dir=tmp_path), log=logs.append)
    col.run()
    out = tmp_path / "out"
    files = {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*.jsonl"))} if out.exists() else {}
    return col._exporters["streams"], files, logs


def _streams(files: dict[str, bytes]) -> list[bytes]:
    return [v for k, v in files.items() if k.startswith("streams/")]


@pytest.mark.parametrize("path", ["out/streams/{session}.jsonl", "out/streams/one.jsonl"])
def test_cc_by_nc_stream_writes_no_file(tmp_path, path):
    ex, files, logs = _run(tmp_path, [NC], GATE, path)
    assert _streams(files) == []
    n = len(_vector())
    assert ex.counts["research_only_streams_refused"] == 1 and ex.counts["research_only_events_refused"] == n
    assert ex.counts["licence_unknown_streams_refused"] == ex.counts["licence_unknown_events_refused"] == 0
    assert ex.counts["exported"] == 0
    lines = [m for m in logs if "dropped a stream" in m]
    assert len(lines) == 1 and "s0" not in lines[0] and "in-0" not in lines[0]  # no session id in the log line
    assert ex.stats()["refuse_research_only"] == {"unknown_licence": "refuse", "streams": True}


@pytest.mark.parametrize("path", ["out/streams/{session}.jsonl", "out/streams/one.jsonl"])
def test_cc0_stream_writes_the_same_file_as_before(tmp_path, path):
    _, base, _ = _run(tmp_path / "a", [CC0], None, path)
    ex, gated, logs = _run(tmp_path / "b", [CC0], GATE, path)
    assert _streams(base) and gated == base
    assert sum(ex.counts[k] for k in ex.counts if k.endswith("_refused")) == 0
    assert not any("dropped" in m for m in logs)


def test_unknown_licence_rule_both_ways(tmp_path):
    ex, files, logs = _run(tmp_path / "a", [{}], GATE)
    assert _streams(files) == []
    assert ex.counts["licence_unknown_streams_refused"] == 1
    assert ex.counts["licence_unknown_events_refused"] == len(_vector())
    assert sum("unknown licence" in m and "dropped a stream" in m for m in logs) == 1
    _, base, _ = _run(tmp_path / "b", [{}])
    ex2, passed, _ = _run(tmp_path / "c", [{}], {**GATE, "unknown_licence": "pass"})
    assert _streams(base) and passed == base and ex2.counts["licence_unknown_events_refused"] == 0
    # "pass" never lets a research-only stream through ...
    ex3, f3, _ = _run(tmp_path / "d", [NC], {**GATE, "unknown_licence": "pass"})
    assert _streams(f3) == [] and ex3.counts["research_only_streams_refused"] == 1
    # ... nor a stream that says research_only = false without a licence: FEP-0010 reads it as an unknown
    # licence that is research only, the same flag that a trust layer writes into input.research_only.
    ex4, f4, _ = _run(tmp_path / "e", [{L.META_RESEARCH_ONLY: False}], {**GATE, "unknown_licence": "pass"})
    assert _streams(f4) == [] and ex4.counts["research_only_streams_refused"] == 1


def test_multi_stream_pipeline_refuses_per_stream(tmp_path):
    """Three streams in one run (one receiver, three files): only the CC0 stream gets its per-session file."""
    _, base, _ = _run(tmp_path / "a", [NC, CC0, {}])
    ex, gated, _ = _run(tmp_path / "b", [NC, CC0, {}], GATE)
    assert len(_streams(base)) == 3 and len(_streams(gated)) == 1
    assert _streams(gated)[0] in _streams(base)
    assert json.loads(_streams(gated)[0].splitlines()[0])["meta"][L.META_LICENCE] == "CC0-1.0"
    assert ex.counts["files"] == 1
    assert ex.counts["research_only_streams_refused"] == ex.counts["licence_unknown_streams_refused"] == 1


def test_gate_unit_per_stream_state():
    logs: list[str] = []
    ex = E.StdoutExporter("s", logs.append, INPUT_TYPES).refuse_research_only("refuse")
    seen: list = []
    ex.export = lambda items: seen.extend(items)  # type: ignore[method-assign]
    nc = {"type": "header", "meta": dict(NC)}
    cc0 = {"type": "header", "meta": dict(CC0)}
    frame, end = {"type": "frame", "t": 0.0}, {"type": "end"}
    st = {"type": STATUS, "value": "gap"}
    items = [("a", nc), ("b", cc0), ("a", frame), ("b", frame), ("a", st), ("a", end), ("b", end),
             ("a", cc0), ("a", frame),  # a new header on the same key: a new stream, judged again
             ("c", frame), ("c", end)]  # no header before it: unknown licence
    ex.deliver(items)
    assert [(s, ev["type"]) for s, ev in seen] == [("b", "header"), ("b", "frame"), ("a", STATUS), ("b", "end"),
                                                  ("a", "header"), ("a", "frame")]
    assert all(any(ev is x for _, x in items) for _, ev in seen)  # the same objects: never a changed item
    assert ex.counts["research_only_streams_refused"] == 1 and ex.counts["research_only_events_refused"] == 3
    assert ex.counts["licence_unknown_streams_refused"] == 1 and ex.counts["licence_unknown_events_refused"] == 2
    assert ex.licence_gate is not None and set(ex.licence_gate.streams) == {"a"}  # "end" forgets a stream
    assert len([m for m in logs if "dropped a stream" in m]) == 2  # one line per kind
    # A decisions-only exporter never judges input events and has no stream counters.
    dec = E.JsonlExporter("d", logs.append, Path("unused.jsonl"), ["trust_decision"]).refuse_research_only()
    assert dec.licence_gate is not None and not dec.licence_gate.input_events
    assert "research_only_streams_refused" not in dec.counts
    assert dec.licence_gate.admit([("a", nc), ("a", frame)]) == [("a", nc), ("a", frame)]


@pytest.mark.parametrize("opts, msg", [
    ({"refuse_research_only": 1}, "true or false"),
    ({"unknown_licence": "refuse"}, "needs refuse_research_only = true"),
    ({"refuse_research_only": True, "unknown_licence": "drop"}, "must be one of"),
])
def test_config_errors_on_an_input_event_exporter(tmp_path, opts, msg):
    src = _stream(tmp_path, "s.jsonl", NC)
    cfg = {"receivers": {"in": {"type": "file", "paths": [str(src)]}},
           "exporters": {"streams": {"type": "jsonl", "path": "out/s.jsonl", "types": INPUT_TYPES, **opts}},
           "pipelines": {"main": {"receivers": ["in"], "exporters": ["streams"]}}}
    with pytest.raises(ConfigError, match=msg):
        parse(cfg, base_dir=tmp_path)
