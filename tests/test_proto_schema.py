"""P1-02: the proto files are the source of truth; the JSON Schema is generated from them.

- The committed spec/schemas/nts-v1.schema.json equals the generator output (drift check).
- The generated schema gives the SDK verdict on every conformance vector that fails or
  passes on schema grounds (tools/proto/parity.py; 0 mismatches).
- The mapping rules of spec/proto/README.md are enforced by the generator lint.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools" / "proto"
if not (TOOLS / "gen_jsonschema.py").exists():  # the sdist has no tools/
    pytest.skip("tools/proto is not in this checkout", allow_module_level=True)
sys.path.insert(0, str(TOOLS))

import gen_jsonschema  # noqa: E402
import parity  # noqa: E402
from jsonschema_lite import Validator, json_equal  # noqa: E402
from protoparse import parse_dir  # noqa: E402


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(gen_jsonschema.OUT.read_text(encoding="utf-8"))


def test_schema_is_up_to_date() -> None:
    assert gen_jsonschema.OUT.read_text(encoding="utf-8") == gen_jsonschema.render(), \
        "spec/schemas/nts-v1.schema.json is stale: run python tools/proto/gen_jsonschema.py"


def test_parity_with_sdk_verdicts() -> None:
    res = parity.run("lite")
    s = res["summary"]
    bad = [f"{r['id']}: expect {r['expect']}, schema {r['schema']} ({r['errors'][:1]})"
           for r in res["rows"] if r["result"] == "MISMATCH"]
    assert not bad, "\n".join(bad)
    assert s["vectors"] == 287
    assert s["stale_classes"] == []
    # A reject vector that the schema rejects is a schema vector: its class must say so.
    assert s["not_compared_but_schema_rejects"] == []
    assert s["by_class"]["accept"] + s["by_class"]["schema"] == s["compared"]


def test_every_event_type_of_registry_12_1_is_defined(schema: dict) -> None:
    types = {b["if"]["properties"]["type"]["const"] for b in schema["allOf"]}
    assert types == {"header", "frame", "segment_end", "end", "signal_quality", "decision", "hypothesis", "pointer",
                     "intent", "intent_feedback", "control", "control_enable", "trust_decision", "gap"}


def test_unknown_types_and_keys_are_allowed(schema: dict) -> None:
    v = Validator(schema)
    assert v.errors({"type": "acme.calibration_event", "x": [1, 2]}) == []  # GEN-4, EXT-2
    assert v.errors({"type": "end", "acme.note": "x"}) == []  # GEN-4
    assert v.errors({"type": "frame", "t": 0.0, "log_probs": [0.0], "lsl_t": 3.5, "ws_seq": 1}) == []
    assert v.errors({"type": 3}) != []  # GEN-2: type is a string
    assert v.errors(["header"]) != []  # GEN-2: one JSON object


def test_json_data_model_rules(schema: dict) -> None:
    v = Validator(schema)
    td = {"type": "trust_decision", "is_final": True, "action": "COMMIT", "p_top1": 0.9,
          "score_semantics": "calibrated_prob", "shown": ["ab"]}
    assert v.errors(td) == []
    assert v.errors({**td, "seq": 1.0}) == []  # GEN-5 is lexical: 1.0 is an integer in JSON Schema
    assert v.errors({**td, "seq": True}) != []  # a boolean is not a number
    assert v.errors({**td, "seq": -1}) != []  # uint: >= 0
    assert json_equal(1, 1.0) and not json_equal(True, 1)


def test_header_and_decision_examples_of_section_8_1(schema: dict) -> None:
    v = Validator(schema)
    text = (REPO / "spec" / "nts-1.0-rc2.md").read_text(encoding="utf-8")
    block = text.split("#### 8.1.1 JSON Lines (proposed Stable)", 1)[1].split("#### 8.1.2", 1)[0]
    lines = [ln for ln in block.splitlines() if ln.startswith("{")]
    assert len(lines) == 9
    for ln in lines:
        assert v.errors(json.loads(ln)) == [], ln


def test_lint_refuses_a_broken_mapping(tmp_path: Path) -> None:
    for f in gen_jsonschema.PROTO_DIR.glob("*.proto"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    p = tmp_path / "core.proto"
    p.write_text(p.read_text(encoding="utf-8").replace('VOCAB_TYPE_KEY = 2 [(json_value) = "key"];',
                                                       "VOCAB_TYPE_KEY = 2;"), encoding="utf-8")
    with pytest.raises(gen_jsonschema.MappingError, match="needs json_value"):
        gen_jsonschema.build(parse_dir(tmp_path))
