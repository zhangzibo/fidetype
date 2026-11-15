#!/usr/bin/env python3
"""Generate the JSON Schema of the NTS JSON Lines form from the proto files.

Source of truth: spec/proto/neuraltextstream/v1/*.proto (roadmap P1-02).
Output:          spec/schemas/nts-v1.schema.json (JSON Schema draft 2020-12).

    python tools/proto/gen_jsonschema.py           write the schema
    python tools/proto/gen_jsonschema.py --check   exit 1 if the file is not up to date

Standard library only. The mapping rules are in spec/proto/README.md:
- one JSON object per line; "type" selects the event message (Event oneof);
- JSON keys are the proto field names (snake_case), never lowerCamelCase;
- enums are JSON strings (option json_value). An enum field accepts any string; the known values are
  required only in data of a version that this schema implements (VER-7, VER-8: a "<Message>.known"
  definition, applied by the header and trust_decision through their spec_version);
- integers are JSON numbers in [-(2^53 - 1), 2^53 - 1] (GEN-10); uint* fields are >= 0;
- fields with json_profile (trust_decision fields of one profile) are typed only on decisions of that
  profile (PRF-5); on other decisions they are custom keys;
- fields with json_inline (Timing, Binding, ext) are keys of the parent object;
- unknown keys and unknown event types are allowed (GEN-4).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from protoparse import Field, Message, ProtoSet, parse_dir  # noqa: E402

REPO = HERE.parent.parent
PROTO_DIR = REPO / "spec" / "proto" / "neuraltextstream" / "v1"
OUT = REPO / "spec" / "schemas" / "nts-v1.schema.json"
SCHEMA_ID = "https://github.com/zhangzibo/fidetype/spec/schemas/nts-v1.schema.json"

RULE_ID = re.compile(r"\b(?:GEN|HDR|MET|FRM|SEG|SQ|DEC|HYP|EVD|DCL|PTR|TIM|TD|PRV|PRF|INT|CTL|FIL|LSL|WS|SEC|VER|EXT|CNF|FEP)"
                     r"-(?:[A-Z]+[0-9]+|[A-Z]|[0-9]+)\b")
INT_TYPES = {"int32", "int64", "sint32", "sint64", "sfixed32", "sfixed64"}
UINT_TYPES = {"uint32", "uint64", "fixed32", "fixed64"}
NUM_TYPES = {"double", "float"}
INLINE_NUMBERS = {"Timing": 900, "Binding": 1000, "google.protobuf.Struct": 2047}
ARRAY_OPTS = {"min_items": "minItems", "max_items": "maxItems", "unique_items": "uniqueItems"}
VALUE_OPTS = {"minimum": "minimum", "maximum": "maximum", "exclusive_minimum": "exclusiveMinimum",
              "exclusive_maximum": "exclusiveMaximum", "pattern": "pattern", "min_length": "minLength"}
KNOWN_FIELD_OPTS = set(ARRAY_OPTS) | set(VALUE_OPTS) | {"json_required", "json_nullable", "null_binary", "json_inline",
                                                        "json_profile"}
#: Largest portable JSON integer (GEN-10).
MAX_JSON_INT = 2**53 - 1
#: A spec_version of a newer 1.x minor version (VER-8): unknown enumeration values are allowed.
NEWER_MINOR = "^1\\.[1-9][0-9]*$"


class MappingError(Exception):
    pass


def _num(v: Any) -> Any:
    """Write 0.0 as 0 so the schema text does not depend on how an option was spelled."""
    return int(v) if isinstance(v, float) and v.is_integer() else v


def rules_in(text: str) -> list[str]:
    seen: list[str] = []
    for r in RULE_ID.findall(text):
        if r not in seen:
            seen.append(r)
    return seen


def lint(ps: ProtoSet) -> None:
    """Check the mapping rules of spec/proto/README.md. Raise MappingError on the first break."""
    if ps.package != "neuraltextstream.v1":
        raise MappingError(f"package must be neuraltextstream.v1, not {ps.package}")
    for en in ps.enums.values():
        if not en.values or en.values[0].number != 0 or not en.values[0].name.endswith("_UNSPECIFIED"):
            raise MappingError(f"enum {en.name}: value 0 must be *_UNSPECIFIED")
        prefix = re.sub(r"(?<!^)(?=[A-Z])", "_", en.name).upper() + "_"
        jv = []
        for v in en.values:
            if not v.name.startswith(prefix):
                raise MappingError(f"enum {en.name}: value {v.name} must start with {prefix}")
            if v.number == 0:
                if "json_value" in v.options:
                    raise MappingError(f"enum {en.name}: value 0 has no JSON form")
            elif "json_value" not in v.options:
                raise MappingError(f"enum {en.name}: value {v.name} needs json_value")
            else:
                jv.append(v.options["json_value"])
        if len(set(jv)) != len(jv):
            raise MappingError(f"enum {en.name}: json_value strings must be unique")
    event = ps.messages.get("Event")
    if event is None:
        raise MappingError("message Event (the envelope) is missing")
    for f in event.fields:
        if f.oneof != "body":
            raise MappingError(f"Event.{f.name}: every Event field is in oneof body")
        if f.name == "unknown":
            continue
        m = ps.messages[f.type]
        if m.options.get("json_type") != f.name:
            raise MappingError(f"Event.{f.name}: message {f.type} must have option json_type = {f.name!r}")
    for m in ps.messages.values():
        nums: set[int] = set()
        keys: set[str] = set()
        for f in m.fields:
            if f.number in nums:
                raise MappingError(f"{m.name}: field number {f.number} is used twice")
            nums.add(f.number)
            if not 1 <= f.number <= 536870911 or 19000 <= f.number <= 19999:
                raise MappingError(f"{m.name}.{f.name}: field number {f.number} is not allowed")
            unknown = set(f.options) - KNOWN_FIELD_OPTS
            if unknown:
                raise MappingError(f"{m.name}.{f.name}: unknown options {sorted(unknown)}")
            if f.options.get("json_inline"):
                if INLINE_NUMBERS.get(f.type) != f.number:
                    raise MappingError(f"{m.name}.{f.name}: inline field of type {f.type} must have number "
                                       f"{INLINE_NUMBERS.get(f.type)}")
                if f.type in ps.messages:
                    for g in ps.messages[f.type].fields:
                        if g.name in keys:
                            raise MappingError(f"{m.name}: JSON key {g.name} is defined twice")
                        keys.add(g.name)
            else:
                if f.name in keys:
                    raise MappingError(f"{m.name}: JSON key {f.name} is defined twice")
                keys.add(f.name)
                if m.name != "Event" and f.number >= 900:
                    raise MappingError(f"{m.name}.{f.name}: spec fields use 1-899; 900, 1000 and 2047 are the inline groups")
            nb = f.options.get("null_binary", "unset")
            if nb not in ("unset", "neg_inf", "nan"):
                raise MappingError(f"{m.name}.{f.name}: null_binary must be unset, neg_inf or nan")
            if nb != "unset" and f.type not in NUM_TYPES:
                raise MappingError(f"{m.name}.{f.name}: null_binary {nb} needs a double field")
            if nb == "unset" and f.options.get("json_nullable") and f.label == "repeated":
                raise MappingError(f"{m.name}.{f.name}: a repeated field with null items needs null_binary")
            if any(k in f.options for k in ARRAY_OPTS) and f.label != "repeated":
                raise MappingError(f"{m.name}.{f.name}: array options need a repeated field")
        for r in m.options.get("json_rule", []):
            frag = json.loads(r)
            if not isinstance(frag, dict) or not frag.get("$comment"):
                raise MappingError(f"{m.name}: each json_rule is a JSON object with a $comment that names its rule")


def scalar_schema(f: Field, ps: ProtoSet, strict: bool = False) -> dict[str, Any]:
    """The schema of one value of field ``f``. Enum values: any string (open), or the known values (``strict``)."""
    t = f.type
    if t == "string":
        s: dict[str, Any] = {"type": "string"}
    elif t == "bool":
        s = {"type": "boolean"}
    elif t in NUM_TYPES:
        s = {"type": "number"}
    elif t in INT_TYPES:
        s = {"type": "integer", "minimum": -MAX_JSON_INT, "maximum": MAX_JSON_INT}
    elif t in UINT_TYPES:
        s = {"type": "integer", "minimum": 0, "maximum": MAX_JSON_INT}
    elif t == "google.protobuf.Struct":
        s = {"type": "object"}
    elif t == "google.protobuf.Value":
        s = {}
    elif t == "google.protobuf.ListValue":
        s = {"type": "array"}
    elif t in ps.enums:
        s = {"$ref": f"#/$defs/{t}"} if strict else {"type": "string", "x-nts-enum": f"#/$defs/{t}"}
    elif t in ps.messages:
        s = {"$ref": f"#/$defs/{t}"}
    else:
        raise MappingError(f"{f.name}: unknown type {t}")
    for opt, kw in VALUE_OPTS.items():
        if opt in f.options:
            s[kw] = _num(f.options[opt])
    if f.options.get("json_nullable"):
        if "type" in s:
            s["type"] = [s["type"], "null"]
        else:
            s = {"anyOf": [s, {"type": "null"}]}
    return s


def field_schema(f: Field, ps: ProtoSet, strict: bool = False) -> dict[str, Any]:
    item = scalar_schema(f, ps, strict)
    if f.label == "repeated":
        s: dict[str, Any] = {"type": "array", "items": item}
        for opt, kw in ARRAY_OPTS.items():
            if opt in f.options:
                s[kw] = _num(f.options[opt])
    else:
        s = item
    desc = f.comment
    if f.options.get("null_binary", "unset") != "unset":
        desc += f" Binary form of JSON null: {'-inf' if f.options['null_binary'] == 'neg_inf' else 'NaN'}."
    if desc:
        s = {"description": desc.strip(), **s}
    r = rules_in(f.comment)
    if r:
        s["x-nts-rules"] = r
    return s


def collect(m: Message, ps: ProtoSet, props: dict[str, Any], required: list[str],
            by_profile: dict[str, dict[str, Any]] | None = None) -> None:
    for f in m.fields:
        if f.options.get("json_inline"):
            if f.type in ps.messages:
                collect(ps.messages[f.type], ps, props, required, by_profile)
            continue  # an inline Struct (ext): any other key, allowed by default
        prof = f.options.get("json_profile")
        if prof and by_profile is not None:
            by_profile.setdefault(prof, {})[f.name] = field_schema(f, ps)
            continue
        props[f.name] = field_schema(f, ps)
        if f.options.get("json_required"):
            required.append(f.name)


def _profile_rule(prof: str, props: dict[str, Any], what: str) -> dict[str, Any]:
    return {"$comment": f"PRF-5: the {prof}-profile fields {what} only on decisions with profile {prof}",
            "if": {"required": ["profile"], "properties": {"profile": {"const": prof}}},
            "then": {"properties": props}}


def has_enum(m: Message, ps: ProtoSet, seen: frozenset[str] = frozenset()) -> bool:
    """True if message ``m`` (or a message field of it, at any depth) has an enum field."""
    for f in m.fields:
        if f.type in ps.enums:
            return True
        if f.type in ps.messages and f.type not in seen and has_enum(ps.messages[f.type], ps, seen | {m.name}):
            return True
    return False


def known_schema(m: Message, ps: ProtoSet) -> dict[str, Any]:
    """``<Message>.known``: every enum value (at any depth) is a known value of this schema version (VER-7)."""
    props: dict[str, Any] = {}
    by_profile: dict[str, dict[str, Any]] = {}

    def add(f: Field) -> None:
        if f.type in ps.enums:
            s = field_schema(f, ps, strict=True)
            s.pop("description", None)
            s.pop("x-nts-rules", None)
        elif f.type in ps.messages and has_enum(ps.messages[f.type], ps):
            ref = {"$ref": f"#/$defs/{f.type}.known"}
            s = {"type": "array", "items": ref} if f.label == "repeated" else ref
        else:
            return
        prof = f.options.get("json_profile")
        (by_profile.setdefault(prof, {}) if prof else props)[f.name] = s

    for f in m.fields:
        if f.options.get("json_inline") and f.type in ps.messages:
            for g in ps.messages[f.type].fields:
                add(g)
        elif not f.options.get("json_inline"):
            add(f)
    s: dict[str, Any] = {"description": f"VER-7: the enumeration values of {m.name} are known values "
                                        "(data of a version that this schema implements).",
                         "type": "object", "properties": props}
    if by_profile:
        s["allOf"] = [_profile_rule(p, v, "have known values") for p, v in sorted(by_profile.items())]
    return s


def message_schema(m: Message, ps: ProtoSet) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    by_profile: dict[str, dict[str, Any]] = {}
    jt = m.options.get("json_type")
    if jt:
        props["type"] = {"const": jt}
        required.append("type")
    collect(m, ps, props, required, by_profile)
    s: dict[str, Any] = {}
    if m.comment:
        s["description"] = m.comment
    s["type"] = "object"
    if required:
        s["required"] = required
    s["properties"] = props
    rules = [json.loads(r) for r in m.options.get("json_rule", [])]
    rules += [_profile_rule(p, v, "have these types") for p, v in sorted(by_profile.items())]
    if "spec_version" in props and has_enum(m, ps):
        rules.append({"$comment": "VER-7, VER-8: without a newer minor spec_version (absent = 0.1), the enumeration "
                                  "values are known values; a newer minor version may use other strings",
                      "if": {"required": ["spec_version"], "properties": {"spec_version": {"pattern": NEWER_MINOR}}},
                      "else": {"$ref": f"#/$defs/{m.name}.known"}})
    if rules:
        s["allOf"] = rules
    r = rules_in(m.comment + " " + " ".join(x.get("$comment", "") for x in rules))
    if r:
        s["x-nts-rules"] = r
    s["x-proto"] = f"neuraltextstream.v1.{m.name} ({m.file})"
    return s


def enum_schema(name: str, ps: ProtoSet) -> dict[str, Any]:
    en = ps.enums[name]
    s: dict[str, Any] = {}
    if en.comment:
        s["description"] = en.comment
    s["enum"] = [v.options["json_value"] for v in en.values if v.number != 0]
    s["x-proto"] = f"neuraltextstream.v1.{name} ({en.file})"
    return s


def build(ps: ProtoSet) -> dict[str, Any]:
    lint(ps)
    event = ps.messages["Event"]
    dispatch = []
    for f in event.fields:
        if f.name == "unknown":
            continue
        dispatch.append({"if": {"required": ["type"], "properties": {"type": {"const": f.name}}},
                         "then": {"$ref": f"#/$defs/{f.type}"}})
    defs: dict[str, Any] = {}
    for name in sorted(ps.messages):
        if name in ("Event", "UnknownEvent", "Timing", "Binding"):
            continue  # Event = this root schema; Timing and Binding are inline only
        defs[name] = message_schema(ps.messages[name], ps)
        if has_enum(ps.messages[name], ps):
            defs[f"{name}.known"] = known_schema(ps.messages[name], ps)
    for name in sorted(ps.enums):
        defs[name] = enum_schema(name, ps)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "NeuralTextStream 1.0 RC3 (draft): one JSON Lines event",
        "description": (
            "GENERATED FILE. Do not edit. Source: spec/proto/neuraltextstream/v1/*.proto. Generator: "
            "tools/proto/gen_jsonschema.py (check: --check). Validates ONE line of a JSON Lines stream or decision "
            "log (or one LSL marker sample, or one WebSocket NTS message). The value of \"type\" selects the event "
            "definition; an unknown type is allowed (GEN-4). Unknown keys are allowed (GEN-4). The rules that "
            "need more than one line, the header, arithmetic or the trust rules stay in the SDK validators: "
            "see spec/proto/README.md, section 'What the schema cannot express'."
        ),
        "type": "object",
        "required": ["type"],
        "properties": {"type": {"type": "string", "description": "Event type (GEN-2, registry 12.1)."}},
        "allOf": dispatch,
        "$defs": defs,
    }


def render(ps: ProtoSet | None = None) -> str:
    return json.dumps(build(ps or parse_dir(PROTO_DIR)), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the schema file is not up to date")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print(f"{OUT.relative_to(REPO)} is not up to date. Run: python tools/proto/gen_jsonschema.py", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(REPO)} is up to date")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)} ({len(build(parse_dir(PROTO_DIR))['$defs'])} definitions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
