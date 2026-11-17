#!/usr/bin/env python3
"""Parity of the generated JSON Schema with the SDK verdicts on the conformance vectors.

    python tools/proto/parity.py                    # report; exit 1 on a mismatch
    python tools/proto/parity.py --engine jsonschema  # same with the reference library (pip/uv: jsonschema)
    python tools/proto/parity.py --json             # machine-readable result

For every vector of the profiles v0.1, fep-0001 ... fep-0005 (and every file of the
conformance kit, spec/conformance/kit/, P7-01), the runner takes
the JSON objects that the vector holds in a JSON form (JSON Lines lines, LSL
marker samples and nts_header, WebSocket NTS messages) and validates each one
against spec/schemas/nts-v1.schema.json. The schema verdict of a vector is
"reject" if one object fails, else "accept".

The three SDKs give the manifest verdict ("expect") on every vector. Each
reject vector has a class below: "schema" if the reason is a rule that the
schema expresses, else the reason why a one-line schema cannot see it.

- An accept vector MUST be accepted by the schema.
- A reject vector of class "schema" MUST be rejected by the schema.
- A reject vector of another class is not compared. Its schema verdict is
  reported (normally accept: the schema does not see the reason).
A break of the first two rules is a mismatch.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parent.parent
VECTORS = REPO / "spec" / "conformance"
SCHEMA = REPO / "spec" / "schemas" / "nts-v1.schema.json"
PROFILES = ("v0.1", "fep-0001", "fep-0002", "fep-0003", "fep-0004", "fep-0005")
# P7-01: the conformance kit (spec/conformance/kit/<profile>/manifest.json). A kit entry carries its
# reject class in the manifest ("schema_class"), so it needs no row in REJECT_CLASS.
KIT = VECTORS / "kit"

# Why a reject vector is (or is not) a schema verdict. Classes:
#   schema      a rule on one JSON object that the schema expresses
#   cross-field two fields of one object: lengths, order, index < length, membership in another field
#   arithmetic  a computed value: log-sum-exp (FRM-3), a sum of scores
#   cross-line  needs other lines: the header (V, declarations), order, uniqueness in the stream
#   trust       a semantic rule of a trust layer (TD-9, INT-S*, CTL-S*)
#   lexical     GEN-5: 1.0 and 1 are the same JSON number; a schema cannot see the spelling
#   parse       not JSON (GEN-2, LSL-X2, WS-F2): there is no object to validate
#   binding     a transport rule of LSL or WebSocket (stream info, framing, sequence, auth)
#   npz         an NPZ vector: not a JSON form
#   semconv     a semantic-convention value in meta (MET-7 ... MET-11): meta is a free object
#               (google.protobuf.Struct); the registry (spec/semconv) and the validators check it
CLASSES = ("schema", "cross-field", "arithmetic", "cross-line", "trust", "lexical", "parse", "binding", "npz", "semconv")
REJECT_CLASS: dict[str, tuple[str, str]] = {
    # v0.1 (NPZ vectors are class npz automatically)
    "V36": ("schema", "DEC-2"), "V37": ("schema", "DEC-3"), "V39": ("cross-field", "TIM-4 order of 4 fields"),
    "V41": ("parse", "GEN-2 NaN token"), "V43": ("arithmetic", "FRM-3 sparse sum"), "V44": ("cross-line", "TIM-2"),
    "V45": ("cross-line", "HDR-1 header first"), "V46": ("cross-line", "FRM-1 V from the header"),
    "V47": ("schema", "HDR-6 type"), "V50": ("schema", "HDR-1 required vocab_type"), "V52": ("schema", "HDR-11"),
    "V55": ("schema", "VER-5"), "V56": ("schema", "VER-5"), "V57": ("schema", "VER-5"), "V58": ("schema", "VER-5"),
    "V59": ("schema", "VER-5 number"), "V61": ("lexical", "GEN-5 blank_id 0.0"),
    "V63": ("arithmetic", "FRM-3 empty row (HDR-12)"), "V64": ("arithmetic", "FRM-3 empty sparse row (HDR-12)"),
    "V65": ("cross-field", "HDR-6 blank_id < len(vocab)"),
    # fep-0001
    "F04": ("cross-line", "SEG-5: an unknown value is an error only under a header of a known version (VER-7)"), "F05": ("schema", "SEG-4 type"), "F06": ("cross-line", "SEG-4 order"),
    "F09": ("cross-field", "EVD-1 count = code points"), "F10": ("schema", "EVD-1 range"),
    "F11": ("schema", "EVD-1 type"), "F12": ("schema", "EVD-4"), "F13": ("schema", "EVD-4 type"),
    "F14": ("schema", "EVD-3 / HYP-1"), "F17": ("schema", "DCL-1"), "F18": ("schema", "DCL-1"),
    "F19": ("schema", "DCL-1"), "F20": ("schema", "DCL-1"), "F21": ("cross-line", "TD-4"),
    "F27": ("schema", "TD-F1"), "F28": ("schema", "TD-F1"), "F29": ("schema", "TD-F1"), "F30": ("schema", "TD-F1"),
    "F31": ("schema", "TD-F1"), "F32": ("schema", "TD-F1"), "F33": ("schema", "TD-F2"), "F34": ("schema", "TD-F2"),
    "F35": ("schema", "TD-8"), "F36": ("cross-line", "TD-6"), "F37": ("cross-line", "TD-7"),
    "F38": ("cross-line", "TD-5"), "F39": ("cross-line", "TD-11"), "F40": ("arithmetic", "FRM-3"),
    "F43": ("trust", "TD-9 (1.x)"), "F44": ("trust", "TD-9 (1.x)"), "F46": ("schema", "TD-F3"),
    "F47": ("schema", "TD-F3"), "F49": ("schema", "VER-5 header"), "F50": ("lexical", "GEN-5 seq 1.0"),
    "F51": ("schema", "TD-F2"), "F52": ("schema", "TD-F2"), "F53": ("schema", "TD-F2"), "F54": ("schema", "TD-F2"),
    # fep-0002 (LSL)
    "L15": ("parse", "LSL-D1 nts_header not JSON"), "L16": ("binding", "LSL-F2"), "L17": ("binding", "LSL-F1"),
    "L18": ("binding", "LSL-F3"), "L19": ("binding", "LSL-V1"), "L20": ("binding", "LSL-F6"),
    "L21": ("binding", "LSL-E1"), "L22": ("binding", "LSL-F5 NaN in a numeric sample"),
    "L23": ("schema", "LSL-D2 / HDR-2"), "L24": ("binding", "LSL-D3"), "L25": ("binding", "LSL-C5"),
    "L27": ("parse", "LSL-X2 sample not JSON"), "L28": ("schema", "LSL-X2 / TD-F1"), "L29": ("binding", "LSL-X1"),
    "L30": ("binding", "LSL-X1"), "L31": ("cross-line", "TD-6"), "L34": ("schema", "VER-5"),
    "L35": ("schema", "VER-5"),
    # fep-0003
    "D07": ("schema", "INT-T3"), "D08": ("schema", "INT-T2"), "D09": ("schema", "INT-T1"), "D10": ("schema", "INT-T3"),
    "D11": ("schema", "INT-T3 risk_class enum"), "D12": ("schema", "PRF-4"), "D13": ("cross-line", "INT-T4"),
    "D14": ("cross-line", "INT-T6"), "D15": ("trust", "INT-S1"), "D16": ("trust", "INT-S3"),
    "D17": ("trust", "INT-S4"), "D18": ("trust", "INT-S4"), "D19": ("trust", "INT-S4"), "D20": ("trust", "INT-S5"),
    "D21": ("trust", "INT-S2"), "I07": ("schema", "INT-D1 type"), "I08": ("cross-field", "INT-D1 unique ids"),
    "I09": ("schema", "INT-D2"), "I10": ("schema", "INT-D3"), "I11": ("schema", "INT-D4"),
    "I12": ("cross-field", "INT-D5 vocab = ids"), "I13": ("cross-line", "INT-E1"), "I14": ("cross-line", "INT-E2"),
    "I15": ("cross-field", "INT-E2 not twice"), "I16": ("schema", "INT-E3 range"), "I17": ("arithmetic", "INT-E3 sum"),
    "I18": ("cross-field", "INT-E4 ranking"), "I19": ("schema", "INT-E3 none"), "I20": ("schema", "INT-E7"),
    "I21": ("cross-line", "INT-E5"), "I22": ("cross-line", "INT-F1: an unknown value is an error only under a header of a known version (VER-7)"), "I23": ("arithmetic", "FRM-3"),
    # fep-0004 (WebSocket)
    "W18": ("cross-line", "WS-S1 header first"), "W19": ("binding", "WS-H2"), "W20": ("binding", "WS-V1"),
    "W21": ("schema", "WS-S1 / HDR-2"), "W22": ("binding", "WS-F1"), "W23": ("parse", "WS-F2"),
    "W24": ("binding", "WS-Q1 ws_seq required on /nts"), "W25": ("schema", "WS-Q1 ws_seq integer"),
    "W26": ("binding", "WS-Q4"), "W27": ("binding", "WS-Q4"), "W28": ("cross-line", "WS-R1"),
    "W29": ("binding", "WS-T2"), "W30": ("cross-line", "FRM-1 V from the header"),
    "W34": ("binding", "WS-D1 welcome first"), "W35": ("binding", "WS-V1"),
    "W36": ("binding", "WS-D1 ws_seq required on /decisions"), "W37": ("cross-line", "TD-6"),
    "W38": ("schema", "HDR-8 / WS-S1"), "W41": ("schema", "VER-5"), "W42": ("schema", "VER-5"),
    "W43": ("lexical", "GEN-5 ws_seq 2.0"),
    # fep-0005
    "C06": ("schema", "CTL-D1"), "C07": ("schema", "CTL-D1 units fit quantity"), "C08": ("schema", "CTL-D1"),
    "C09": ("schema", "CTL-D1"), "C10": ("schema", "CTL-D3 (intent_declaration present)"),
    "C11": ("cross-field", "CTL-D3 role of the click intent"), "C12": ("cross-line", "CTL-1"),
    "C13": ("cross-line", "CTL-4 dims from the header"), "C14": ("cross-line", "CTL-2"), "C15": ("cross-line", "CTL-2"),
    "C16": ("cross-line", "CTL-3 uncertainty from the header"), "C17": ("schema", "CTL-4 std > 0"),
    "C18": ("cross-field", "CTL-4 null only with absent"), "C19": ("cross-field", "TIM-4"),
    "C20": ("schema", "CTL-E1"), "C21": ("cross-line", "CTL-12"), "C22": ("cross-line", "INT-E2"),
    "C23": ("arithmetic", "FRM-3"), "E05": ("trust", "CTL-S1"), "E06": ("trust", "CTL-S3"), "E07": ("trust", "CTL-S5"),
    "E08": ("trust", "CTL-S2"), "E09": ("schema", "CTL-T2"), "E10": ("schema", "CTL-T3"), "E11": ("schema", "CTL-T4"),
    "E12": ("schema", "CTL-T4"), "E13": ("schema", "CTL-T4 gain"), "E14": ("schema", "CTL-T1"),
    "E15": ("cross-line", "CTL-T5"), "E16": ("cross-line", "CTL-T5"), "E17": ("trust", "CTL-S7"),
    "E18": ("trust", "CTL-S6"), "E19": ("trust", "CTL-S1"), "E20": ("trust", "CTL-S7"),
    # NTS 1.0 RC3: unknown enumeration values (VER-6 ... VER-10), integer range (GEN-10), declaration (TD-F2)
    "V67": ("schema", "VER-7 / HDR-11 under a 1.0 header"), "V68": ("schema", "HDR-5 type (VER-8: an unknown value is a string)"),
    "F59": ("schema", "VER-7 / TD-F1 under spec_version 1.0"), "F60": ("schema", "GEN-10 seq above 2^53 - 1"),
    "F62": ("schema", "TD-F2 declaration is an object"), "D23": ("schema", "VER-7 / INT-T3 risk_class under 1.0"),
    "E23": ("schema", "VER-7 / CTL-T3 state under 1.0"), "E24": ("trust", "CTL-S7 after an unknown state (VER-10)"),
    "W44": ("schema", "GEN-10 ws_seq above 2^53 - 1"),
    # NTS 1.0 RC4 (gap G-12, FEP-0008): optional fields have their types (GEN-11)
    "V70": ("schema", "HYP-5 t_start type"), "V71": ("schema", "HYP-5 span char_start >= 0"),
    "V72": ("schema", "HYP-5 revision_of type"), "V73": ("schema", "SQ-1 channels type"),
    "V74": ("cross-line", "VER-7 / PTR-1 score_semantics under a 1.0 header"),
    "V75": ("cross-field", "PTR-1 absent length = dims"), "V76": ("schema", "DEC-6 score_range type"),
    "V77": ("schema", "DEC-6 score type"), "V78": ("schema", "HDR-16 vocab_id type"),
    "V79": ("schema", "TIM-4 t_emitted type on a frame"), "V81": ("schema", "DEC-6 score type (unknown semantics, 1.1)"),
    "V82": ("schema", "GEN-9 pointer score_semantics null"), "V80": ("cross-field", "TIM-4 order on a frame"),
    "F64": ("schema", "SEG-6 reason type"), "F65": ("schema", "TIM-4 t_emitted type on segment_end"),
    "F66": ("schema", "TD-F2 reason type"), "D25": ("schema", "INT-T8 vocab_id type"),
    "D26": ("schema", "INT-T8 pending_cleared type"), "I25": ("schema", "TIM-4 t_decoded type on an intent event"),
    "C25": ("schema", "TIM-4 t_emitted type on control_enable"), "E26": ("schema", "CTL-T8 level type"),
    "E27": ("schema", "TD-F2 reason type"),
    # NTS 1.0 RC4 amendment (gap G-13 a, option A2): sparse keys on a dense frame keep their types (FRM-2, GEN-11)
    "V89": ("schema", "FRM-2 / GEN-11 top_ids type on a dense frame"),
    "V90": ("schema", "FRM-2 / GEN-11 top_log_probs type on a dense frame"),
    "V91": ("schema", "FRM-2 / GEN-11 rest_log_prob type on a dense frame"),
    "V92": ("schema", "FRM-2 / GEN-11 top_ids unique on a dense frame"),
}


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _loads(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_constant)


def objects_jsonl(path: Path) -> tuple[list[tuple[str, Any]], list[str]]:
    """JSON Lines: one object per non-empty line (GEN-6); stop after end (GEN-7)."""
    objs, notes = [], []
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        return [], [f"not UTF-8: {e}"]
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = _loads(line)
        except ValueError as e:
            notes.append(f"line {n}: not JSON ({e})")
            continue
        objs.append((f"line {n}", obj))
        if isinstance(obj, dict) and obj.get("type") == "end":
            break
    return objs, notes


def _desc_header(info_xml: str) -> tuple[Any, str | None]:
    """The desc/fidetype/nts_header of an LSL stream info: (object or None, note)."""
    root = ET.fromstring(info_xml)
    node = root.find("./desc/fidetype/nts_header")
    if node is None or node.text is None:
        return None, None
    try:
        h = _loads(node.text)
    except ValueError as e:
        return None, f"nts_header is not JSON ({e})"
    if isinstance(h, dict) and "type" not in h:
        h = {"type": "header", **h}  # 8.2.3: type MAY be absent in nts_header
    return h, None


def _is_markers(info_xml: str) -> bool:
    fmt = ET.fromstring(info_xml).findtext("channel_format")
    return fmt == "string"


def objects_lsl(d: dict[str, Any]) -> tuple[list[tuple[str, Any]], list[str]]:
    objs: list[tuple[str, Any]] = []
    notes: list[str] = []
    if d.get("kind") == "decisions":
        for i, s in enumerate(d.get("samples", [])):
            try:
                objs.append((f"decision sample {i}", _loads(s)))
            except (ValueError, TypeError) as e:
                notes.append(f"decision sample {i} is not JSON ({e})")
        return objs, notes
    for name, inlet in d.get("inlets", {}).items():
        h, note = _desc_header(inlet["info_xml"])
        if note:
            notes.append(f"{name}: {note}")
        if h is not None:
            objs.append((f"{name} nts_header", h))
        if not _is_markers(inlet["info_xml"]):
            continue  # numeric frames: channel samples, not JSON events
        for c, chunk in enumerate(inlet.get("chunks", [])):
            if not isinstance(chunk, dict):
                continue
            for j, sample in enumerate(chunk.get("samples", [])):
                s = sample[0] if isinstance(sample, list) and sample else sample
                if not isinstance(s, str) or not s.startswith("{"):
                    continue  # LSL-E3: plain strings are mapped or ignored
                try:
                    obj = _loads(s)
                except ValueError:
                    continue  # LSL-E4: malformed JSON is ignored and counted
                if isinstance(obj, dict) and isinstance(obj.get("type"), str):
                    objs.append((f"{name} chunk {c} sample {j}", obj))
    return objs, notes


def _ws_message(where: str, m: Any, objs: list, notes: list) -> None:
    if not isinstance(m, dict):
        objs.append((where, m))
        return
    t = m.get("type")
    if isinstance(t, str) and t.startswith("ws_"):
        if t == "ws_batch" and isinstance(m.get("events"), list):
            for k, ev in enumerate(m["events"]):
                objs.append((f"{where} batch[{k}]", ev))
        return  # other ws_ control messages are binding messages, not NTS events (WS-M1)
    objs.append((where, m))


def objects_ws(d: dict[str, Any]) -> tuple[list[tuple[str, Any]], list[str]]:
    objs: list[tuple[str, Any]] = []
    notes: list[str] = []
    for i, step in enumerate(d.get("steps", [])):
        if "msg" in step:
            _ws_message(f"step {i}", step["msg"], objs, notes)
        elif "raw" in step:
            try:
                _ws_message(f"step {i}", _loads(step["raw"]), objs, notes)
            except ValueError as e:
                notes.append(f"step {i}: text message is not JSON ({e})")
        elif step.get("binary"):
            notes.append(f"step {i}: binary message")
    for i, m in enumerate(d.get("messages", [])):
        _ws_message(f"message {i}", m, objs, notes)
    return objs, notes


def load_engine(name: str, schema: dict[str, Any]):
    """Return a function obj -> list of error strings."""
    if name == "lite":
        from jsonschema_lite import Validator
        v = Validator(schema)
        return v.errors
    import jsonschema  # reference implementation (optional dependency)
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    return lambda obj: [f"{'/'.join(map(str, e.absolute_path)) or '$'}: {e.message}" for e in v.iter_errors(obj)]


def run(engine: str = "lite") -> dict[str, Any]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate = load_engine(engine, schema)
    rows: list[dict[str, Any]] = []
    sets = [(VECTORS, prof, False) for prof in PROFILES]
    sets += [(KIT, prof, True) for prof in PROFILES if (KIT / prof / "manifest.json").is_file()]
    for root, prof, is_kit in sets:
        man = json.loads((root / prof / "manifest.json").read_text(encoding="utf-8"))
        for v in man["vectors"]:
            vid, path = v["id"], root / prof / v["file"]
            row: dict[str, Any] = {"profile": prof, "id": vid, "kit": is_kit, "expect": v["expect"],
                                   "check": v.get("failing_check"), "description": v["description"]}
            fmt = v.get("format") or path.suffix.lstrip(".")
            if fmt == "npz":
                row.update(cls="npz", reason="NPZ form", schema="n/a", objects=0, notes=[], errors=[])
                row["result"] = "out of scope"
                rows.append(row)
                continue
            if fmt == "jsonl":
                objs, notes = objects_jsonl(path)
            else:
                d = json.loads(path.read_text(encoding="utf-8"))
                objs, notes = (objects_lsl(d) if prof == "fep-0002" else objects_ws(d))
            errs = []
            for where, obj in objs:
                e = validate(obj)
                if e:
                    errs.append(f"{where}: {e[0]}" + (f" (+{len(e) - 1} more)" if len(e) > 1 else ""))
            verdict = "reject" if errs else "accept"
            if v["expect"] == "accept":
                cls, reason = "accept", ""
            elif is_kit:
                if v.get("schema_class") not in CLASSES:
                    raise SystemExit(f"kit entry {vid} has no valid schema_class")
                cls, reason = v["schema_class"], ", ".join(v.get("rules", []))
            else:
                if vid not in REJECT_CLASS:
                    raise SystemExit(f"reject vector {vid} has no class in REJECT_CLASS")
                cls, reason = REJECT_CLASS[vid]
            row.update(cls=cls, reason=reason, schema=verdict, objects=len(objs), notes=notes, errors=errs)
            if cls in ("accept", "schema"):
                row["result"] = "match" if verdict == v["expect"] else "MISMATCH"
            else:
                row["result"] = "not compared"
            rows.append(row)
    known = {r["id"] for r in rows if not r["kit"]}
    stale = sorted(set(REJECT_CLASS) - known)
    summary = {
        "engine": engine,
        "vectors": sum(not r["kit"] for r in rows),
        "kit_vectors": sum(r["kit"] for r in rows),
        "compared": sum(r["result"] in ("match", "MISMATCH") for r in rows),
        "match": sum(r["result"] == "match" for r in rows),
        "mismatch": sum(r["result"] == "MISMATCH" for r in rows),
        "not_compared": sum(r["result"] == "not compared" for r in rows),
        "out_of_scope_npz": sum(r["result"] == "out of scope" for r in rows),
        "by_class": {c: sum(r["cls"] == c for r in rows) for c in ("accept",) + CLASSES},
        "not_compared_but_schema_rejects": [r["id"] for r in rows if r["result"] == "not compared" and r["schema"] == "reject"],
        "stale_classes": stale,
    }
    return {"summary": summary, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", choices=("lite", "jsonschema"), default="lite")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true", help="list every vector")
    args = ap.parse_args(argv)
    res = run(args.engine)
    s = res["summary"]
    if args.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        for r in res["rows"]:
            if args.verbose or r["result"] == "MISMATCH":
                print(f"{r['result']:13} {r['id']:4} expect={r['expect']:6} schema={r['schema']:6} class={r['cls']:11} "
                      f"{r['reason']} | {(r['errors'] or [''])[0][:140]}")
        print(json.dumps(s, indent=1))
    ok = s["mismatch"] == 0 and not s["stale_classes"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
