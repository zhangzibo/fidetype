"""P14-20: a ``trust_decision`` in a live input stream (TD-4, TD-14; NTS 1.0 RC4 amendment 5).

The cases of ``spec/conformance/streaming/td-input.json`` run here on the Python streaming trust layer and
on the collector's ``validate`` processor. The TypeScript and Rust ``StreamValidator`` run the same file
(``sdk/typescript/test/core.test.mjs``, ``sdk/rust/tests/core.rs``), so the three SDKs give the same outcome.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.collector.processors import ValidateProcessor
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import TD_INPUT_MESSAGE, StreamEventError, StreamingConfig, StreamingTrustLayer
from fidetype.trust.testing import greedy_nbest

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "spec" / "conformance" / "streaming" / "td-input.json").read_text(encoding="utf-8"))["cases"]


def _layer() -> StreamingTrustLayer:
    return StreamingTrustLayer(FrozenTrustConfig(name="p14-20"), decode_fn=greedy_nbest,
                               streaming=StreamingConfig(max_attempts=1))


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_streaming_trust_layer_outcomes(case: dict) -> None:
    layer = _layer()
    got = []
    for ev in case["events"]:
        before = layer.session_state()["ignored_events"] if "default" in layer._sessions else 0
        try:
            layer.push(json.dumps(ev))
        except StreamEventError as e:
            got.append("refuse" if "TD-4" in str(e) else "refuse-header")
            continue
        got.append("ignore" if layer.session_state()["ignored_events"] > before else "accept")
    assert got == case["expected"], case["id"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_collector_validate_outcomes(case: dict) -> None:
    """The collector cuts at a refused event (a ``gap`` status) and passes accepted and ignored events on."""
    logs: list[str] = []
    p = ValidateProcessor("validate", logs.append)
    got = []
    for ev in case["events"]:
        c0 = dict(p.counts)
        out = p.process([("s", dict(ev))])
        if p.counts["invalid_events"] > c0["invalid_events"]:
            assert out and out[0][1].get("status") == "gap"
            got.append("refuse")
        else:
            assert out and out[0][1] == ev
            got.append("accept")
    # The collector passes ignored events on. Decisions before any header are a decision log for the collector
    # (it reads decision logs and decisions channels too), so S06 is accepted there.
    want = ["accept" if x in ("ignore", "refuse-header") else x for x in case["expected"]]
    assert got == want, case["id"]
    if "refuse" in want:
        assert any(TD_INPUT_MESSAGE in m for m in logs)


def test_decision_log_is_not_an_input_stream() -> None:
    """Decisions of a stream without a header are a decision log: TD-14 does not apply (format checks only)."""
    p = ValidateProcessor("validate", lambda m: None)
    td = next(e for e in CASES[0]["events"] if e["type"] == "trust_decision")
    out = p.process([("log", dict(td))])
    assert out and out[0][1]["type"] == "trust_decision"
    assert p.counts["invalid_events"] == 0


def test_v97_is_refused_by_the_streaming_layer() -> None:
    """V97 (the file vector of NTS-TD-INPUT) gives the same verdict event by event."""
    lines = (ROOT / "spec" / "conformance" / "v0.1" / "v97-trust-decision-in-input.jsonl").read_text(encoding="utf-8")
    layer = _layer()
    refused = 0
    for line in lines.splitlines():
        try:
            layer.push(line)
        except StreamEventError as e:
            assert "TD-4" in str(e)
            refused += 1
    assert refused >= 1
