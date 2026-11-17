#!/usr/bin/env python3
"""NTS semantic-convention registry: generator and agreement check (roadmap P1-04).

    python tools/semconv/semconv.py            # write spec/semconv/registry.md
    python tools/semconv/semconv.py --check    # all checks + registry.md up to date; exit 1 on an error
    python tools/semconv/semconv.py --json     # the loaded registry as JSON (for SDK generators later)

Needs PyYAML. Without a project environment:
    uv run --no-project --with pyyaml==6.0.3 python tools/semconv/semconv.py --check

The registry (spec/semconv/manifest.yaml + spec/semconv/attributes/*.yaml) is
the machine-readable form of the key conventions of the spec. The check makes
these sources agree:

1. structure   every entry uses the words of manifest.yaml (types, validators,
               requirement levels, scopes, stability); keys are unique; a meta
               key is in its declared namespace.
2. spec        the key tables of the spec (3.4, 6.1.1, 6.1.2) list the same keys
               with the same types and enumeration values; every rule id exists;
               the namespaces equal section 12.5; enumeration values and safe
               fallbacks equal the rows of 12.3.
3. proto       each container field exists and is a google.protobuf.Struct;
               each related field exists.
4. schema      each container resolves in the generated JSON Schema and is an object.
5. sdks        the hand-written meta key tables of the Python, TypeScript and Rust
               validators have the same keys and validators as the registry, the
               same modality list and the same planned namespaces (RC4, SC-2, SC-8).
6. checks      every conformance check id exists in the Python suite, and a
               requirement check belongs to the level of its scope.
7. vectors     the meta values of the accept vectors (JSON Lines) pass the
               registry validators.
8. docs        spec/semconv/registry.md equals the generated text.

Standard library + PyYAML only. It reuses the proto parser of tools/proto.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "proto"))
from protoparse import ProtoSet, parse_dir  # noqa: E402

SEMCONV = ROOT / "spec" / "semconv"
DOC = SEMCONV / "registry.md"
PROTO_DIR = ROOT / "spec" / "proto" / "neuraltextstream" / "v1"
SCHEMA = ROOT / "spec" / "schemas" / "nts-v1.schema.json"
CONFORMANCE = ROOT / "spec" / "conformance"
SDK_TABLES = {
    "python": (ROOT / "src" / "fidetype" / "conformance" / "checks.py", ROOT / "src" / "fidetype" / "conformance" / "checks.py"),
    "typescript": (ROOT / "sdk" / "typescript" / "src" / "checks.ts", ROOT / "sdk" / "typescript" / "src" / "constants.ts"),
    "rust": (ROOT / "sdk" / "rust" / "src" / "checks.rs", ROOT / "sdk" / "rust" / "src" / "constants.rs"),
}
PY_CHECKS = ROOT / "src" / "fidetype" / "conformance" / "checks.py"

ATTR_FIELDS_REQUIRED = ("key", "type", "validator", "brief", "stability")
ATTR_FIELDS_ALLOWED = set(ATTR_FIELDS_REQUIRED) | {
    "values", "unknown_value", "examples", "registered_values", "unit", "default", "requirement", "target_stability", "rules",
    "checks", "related_fields", "spec_registry_row",
}
REQ_FIELDS_ALLOWED = {"scope", "level", "condition", "checks"}
UNITS = {"s"}
LEVEL_SCOPES = ("core", "trust-ready", "provenance")


class Registry:
    """The loaded registry: the manifest plus all attributes (each with its container)."""

    def __init__(self, manifest: dict[str, Any], attributes: list[dict[str, Any]], groups: list[dict[str, Any]],
                 spec_path: Path):
        self.manifest = manifest
        self.attributes = attributes
        self.groups = groups
        self.spec_path = spec_path

    @property
    def containers(self) -> dict[str, dict[str, Any]]:
        return {c["id"]: c for c in self.manifest.get("containers", [])}

    def in_container(self, cid: str) -> list[dict[str, Any]]:
        return [a for a in self.attributes if a["_container"] == cid]


# --- load ----------------------------------------------------------------------------------


def load(root: Path = SEMCONV) -> Registry:
    """Load manifest.yaml and every attribute file that it names."""
    manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
    files: list[tuple[str, str | None]] = []
    for ns in manifest.get("namespaces", []):
        if ns.get("file"):
            files.append((ns["file"], ns["name"]))
    for cf in manifest.get("container_files", []):
        files.append((cf["file"], None))
    attributes, groups = [], []
    for rel, ns in files:
        data = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
        group = {k: v for k, v in data.items() if k != "attributes"}
        group["_file"] = rel
        group["_expected_namespace"] = ns
        groups.append(group)
        for a in data.get("attributes") or []:
            a = dict(a)
            a["_container"] = data.get("container")
            a["_namespace"] = data.get("namespace")
            a["_file"] = rel
            attributes.append(a)
    spec_path = ROOT / manifest["spec"]["document"]
    return Registry(manifest, attributes, groups, spec_path)


# --- 1. structure --------------------------------------------------------------------------


def check_structure(reg: Registry) -> list[str]:
    errs: list[str] = []
    voc = reg.manifest.get("vocabulary", {})
    types, validators = set(voc.get("types", {})), set(voc.get("validators", {}))
    levels, scopes, stab = set(voc.get("requirement_levels", {})), set(voc.get("scopes", {})), set(voc.get("stability", {}))
    containers = reg.containers
    files_seen = {g["_file"] for g in reg.groups}
    listed = [ns.get("file") for ns in reg.manifest.get("namespaces", []) if ns.get("file")]
    listed += [cf["file"] for cf in reg.manifest.get("container_files", [])]
    on_disk = {"attributes/" + p.name for p in (SEMCONV / "attributes").glob("*.yaml")} if reg.groups else set()
    for extra in sorted(on_disk - set(listed)):
        errs.append(f"structure: {extra} is not listed in manifest.yaml")
    for g in reg.groups:
        if g.get("container") not in containers:
            errs.append(f"structure: {g['_file']}: unknown container {g.get('container')!r}")
        if g["_expected_namespace"] is not None and g.get("namespace") != g["_expected_namespace"]:
            errs.append(f"structure: {g['_file']}: namespace {g.get('namespace')!r}, manifest says {g['_expected_namespace']!r}")
    for ns in reg.manifest.get("namespaces", []):
        if ns.get("status") not in ("reserved", "planned"):
            errs.append(f"structure: namespace {ns.get('name')}: status must be reserved or planned")
        if ns.get("status") == "planned" and ns.get("file"):
            errs.append(f"structure: planned namespace {ns['name']} has a file (planned namespaces have no keys)")
        if ns.get("status") == "reserved" and not ns.get("file"):
            errs.append(f"structure: reserved namespace {ns['name']} has no attribute file")
    seen: dict[tuple[str, str], str] = {}
    for a in reg.attributes:
        where = f"{a['_file']}: {a.get('key')!r}"
        for f in ATTR_FIELDS_REQUIRED:
            if f not in a:
                errs.append(f"structure: {where}: missing field {f}")
        for f in a:
            if not f.startswith("_") and f not in ATTR_FIELDS_ALLOWED:
                errs.append(f"structure: {where}: unknown field {f}")
        ident = (a["_container"], a.get("key"))
        if ident in seen:
            errs.append(f"structure: {where}: duplicate key (also in {seen[ident]})")
        seen[ident] = a["_file"]
        if a.get("type") not in types:
            errs.append(f"structure: {where}: unknown type {a.get('type')!r}")
        if a.get("validator") not in validators:
            errs.append(f"structure: {where}: unknown validator {a.get('validator')!r}")
        if a.get("stability") not in stab:
            errs.append(f"structure: {where}: unknown stability {a.get('stability')!r}")
        if a.get("target_stability") is not None and a["target_stability"] not in stab:
            errs.append(f"structure: {where}: unknown target_stability {a['target_stability']!r}")
        if a.get("unit") is not None and a["unit"] not in UNITS:
            errs.append(f"structure: {where}: unknown unit {a['unit']!r}")
        if a.get("type") == "enum":
            vals = a.get("values")
            if not vals or not all(isinstance(v, str) for v in vals) or len(set(vals)) != len(vals):
                errs.append(f"structure: {where}: an enum needs a list of unique string values")
            elif a.get("unknown_value") is not None and a["unknown_value"] not in vals:
                errs.append(f"structure: {where}: unknown_value {a['unknown_value']!r} is not a value")
        else:
            for f in ("values", "unknown_value"):
                if f in a:
                    errs.append(f"structure: {where}: {f} is only for type enum")
        if "registered_values" in a and (a.get("type") not in ("string", "string[]")
                                          or not isinstance(a["registered_values"], list)):
            errs.append(f"structure: {where}: registered_values (an open list, SC-4) is a list and only for type string "
                        "or string[]")
        if a.get("validator") == "non_empty_string_list" and a.get("type") != "string[]":
            errs.append(f"structure: {where}: validator non_empty_string_list needs type string[]")
        if a.get("validator") == "enum" and a.get("type") != "enum":
            errs.append(f"structure: {where}: validator enum needs type enum")
        key = str(a.get("key", ""))
        if a["_container"] == "header.meta":
            ns = a["_namespace"]
            flat = any(n.get("name") == ns and n.get("flat") for n in reg.manifest.get("namespaces", []))
            if flat and key != ns:
                errs.append(f"structure: {where}: a flat namespace has exactly one key, equal to its name")
            if not flat and (not key.startswith(f"{ns}.") or not re.fullmatch(r"[a-z]+(\.[a-z][a-z0-9_]*)+", key)):
                errs.append(f"structure: {where}: key must be '{ns}.<snake_case>' (MET-1)")
        elif not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            errs.append(f"structure: {where}: key must be snake_case")
        for r in a.get("requirement") or []:
            for f in r:
                if f not in REQ_FIELDS_ALLOWED:
                    errs.append(f"structure: {where}: unknown requirement field {f}")
            if r.get("scope") not in scopes:
                errs.append(f"structure: {where}: unknown scope {r.get('scope')!r}")
            if r.get("level") not in levels:
                errs.append(f"structure: {where}: unknown requirement level {r.get('level')!r}")
            if r.get("level") == "conditionally_required" and not r.get("condition"):
                errs.append(f"structure: {where}: conditionally_required needs a condition")
    for c in reg.manifest.get("containers", []):
        for f in ("id", "proto", "json_schema", "spec_section", "spec_table"):
            if f not in c:
                errs.append(f"structure: container {c.get('id')!r}: missing field {f}")
    return errs


# --- 2. spec -------------------------------------------------------------------------------


def _section_lines(spec: str, number: str) -> list[str]:
    """The lines of the section with this number, up to the next heading of any level."""
    lines = spec.splitlines()
    pat = re.compile(r"^#{2,6}\s+" + re.escape(number) + r"\s")
    for i, line in enumerate(lines):
        if pat.match(line):
            out = []
            for nxt in lines[i + 1:]:
                if re.match(r"^#{1,6}\s", nxt):
                    break
                out.append(nxt)
            return out
    return []


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def spec_table(spec: str, number: str) -> list[list[str]]:
    """The body rows of the first Markdown table of a section (cells as text)."""
    rows, started = [], False
    for line in _section_lines(spec, number):
        if line.startswith("|"):
            started = True
            rows.append(_cells(line))
        elif started:
            break
    return [r for r in rows[2:]] if len(rows) >= 2 else []


def _split_top(text: str) -> list[str]:
    """Split at commas that are not inside brackets."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


# Spec type text -> (registry type, validator that the text implies or None).
SPEC_TYPES = {
    "string": ("string", None),
    "non-empty string": ("string", "non_empty_string"),
    "boolean": ("boolean", None),
    "enum": ("enum", None),
    "integer": ("int", None),
    "integer ≥ 1": ("int", "integer_min_1"),
    "number ≥ 0": ("double", "finite_number_min_0"),
    "[integer, integer]": ("int[2]", None),
    "[number, number]": ("double[2]", None),
    "list of strings": ("string[]", None),
    "list of non-empty strings": ("string[]", "non_empty_string_list"),
}


def parse_spec_types(cell: str, n: int) -> list[tuple[str, str | None, list[str] | None]] | str:
    """Types of the n keys of one table row: (type, implied validator, enum values) or an error text."""
    cell = cell.strip()
    if "`" in cell:  # a list of values, for example "`match`, `mismatch`, `absent`" or "`header` or `hypothesis`"
        vals = re.findall(r"`([^`]+)`", cell)
        return [("enum", None, vals)] * n
    base = re.sub(r"\s*\([^)]*\)\s*$", "", cell)
    parts = _split_top(base) if base not in SPEC_TYPES else [base]
    if len(parts) == 1:
        parts = parts * n
    if len(parts) != n:
        return f"cannot map the type {cell!r} to {n} key(s)"
    out = []
    for p in parts:
        if p not in SPEC_TYPES:
            return f"unknown spec type {p!r}"
        t, v = SPEC_TYPES[p]
        out.append((t, v, None))
    return out


def rule_ids(spec: str) -> set[str]:
    return set(re.findall(r"\*\*\[([A-Z0-9]+(?:-[A-Z0-9]+)+)\]\*\*", spec))


def check_spec(reg: Registry, spec: str | None = None) -> list[str]:
    errs: list[str] = []
    spec = spec if spec is not None else reg.spec_path.read_text(encoding="utf-8")
    ids = rule_ids(spec)
    for c in reg.manifest.get("containers", []):
        for r in c.get("rules", []):
            if r not in ids:
                errs.append(f"spec: container {c['id']}: rule {r} is not in {reg.spec_path.name}")
        rows = spec_table(spec, c["spec_table"])
        if not rows:
            errs.append(f"spec: no table in section {c['spec_table']}")
            continue
        type_col, val_col = 1, 2
        spec_keys: dict[str, tuple[str, str | None, list[str] | None]] = {}
        for row in rows:
            keys = re.findall(r"`([^`]+)`", row[0])
            types = parse_spec_types(row[type_col], len(keys))
            if isinstance(types, str):
                errs.append(f"spec: section {c['spec_table']}, row {row[0]!r}: {types}")
                continue
            for k, (t, v, vals) in zip(keys, types):
                if t == "enum" and vals is None and len(row) > val_col:
                    vals = re.findall(r"`([^`]+)`", row[val_col])
                spec_keys[k] = (t, v, vals)
        mine = {a["key"]: a for a in reg.in_container(c["id"])}
        for k in sorted(set(spec_keys) - set(mine)):
            errs.append(f"spec: {c['id']}: key {k} is in spec {c['spec_table']} but not in the registry")
        for k in sorted(set(mine) - set(spec_keys)):
            errs.append(f"spec: {c['id']}: key {k} is in the registry but not in spec {c['spec_table']}")
        for k in sorted(set(mine) & set(spec_keys)):
            t, v, vals = spec_keys[k]
            a = mine[k]
            if a["type"] != t:
                errs.append(f"spec: {c['id']}: {k}: registry type {a['type']}, spec {c['spec_table']} says {t}")
            if v is not None and a["validator"] != v:
                errs.append(f"spec: {c['id']}: {k}: validator {a['validator']}, spec type implies {v}")
            if t == "enum" and list(a.get("values") or []) != list(vals or []):
                errs.append(f"spec: {c['id']}: {k}: values {a.get('values')} differ from spec {c['spec_table']} {vals}")
    for a in reg.attributes:
        for r in a.get("rules") or []:
            if r not in ids:
                errs.append(f"spec: {a['_file']}: {a['key']}: rule {r} is not in {reg.spec_path.name}")
    # Section 12.5: reserved and planned namespaces.
    text = " ".join(_section_lines(spec, "12.5"))
    m_res = re.search(r"Reserved namespaces:(.*?)\.\s", text)
    m_plan = re.search(r"Planned modality namespaces[^:]*:(.*?)\.(?:\s|$)", text)
    spec_res = {n.rstrip(".*") for n in re.findall(r"`([^`]+)`", m_res.group(1))} if m_res else set()
    spec_plan = {n.rstrip(".*") for n in re.findall(r"`([^`]+)`", m_plan.group(1))} if m_plan else set()
    if not spec_res:
        errs.append("spec: cannot read the reserved namespaces of section 12.5")
    mine_res = {n["name"] for n in reg.manifest.get("namespaces", []) if n.get("status") == "reserved"}
    mine_plan = {n["name"] for n in reg.manifest.get("namespaces", []) if n.get("status") == "planned"}
    if spec_res and spec_res != mine_res:
        errs.append(f"spec: reserved namespaces differ from 12.5: registry only {sorted(mine_res - spec_res)}, "
                    f"spec only {sorted(spec_res - mine_res)}")
    if spec_plan != mine_plan:
        errs.append(f"spec: planned namespaces differ from 12.5: registry only {sorted(mine_plan - spec_plan)}, "
                    f"spec only {sorted(spec_plan - mine_plan)}")
    # Section 12.3: enumeration rows.
    rows123 = spec_table(spec, "12.3")
    for a in reg.attributes:
        row_name = a.get("spec_registry_row")
        if not row_name:
            if a.get("type") == "enum" and a.get("unknown_value"):
                errs.append(f"spec: {a['key']}: an enum with unknown_value needs spec_registry_row (12.3)")
            continue
        row = next((r for r in rows123 if r[0] == row_name), None)
        if row is None:
            errs.append(f"spec: {a['key']}: no row {row_name!r} in section 12.3")
            continue
        vals = re.findall(r"`([^`]+)`", row[1])
        if vals != list(a.get("values") or []):
            errs.append(f"spec: {a['key']}: values {a.get('values')} differ from 12.3 {vals}")
        fallback = row[2]
        uv = a.get("unknown_value")
        if uv is None or not re.search(r"\b(read|treated) as `" + re.escape(uv) + "`", fallback, re.I):
            errs.append(f"spec: {a['key']}: unknown_value {uv!r} does not match the 12.3 fallback {fallback!r}")
    return errs


# --- 3. proto and 4. schema ----------------------------------------------------------------


def _proto_field(ps: ProtoSet, dotted: str):
    pkg = ps.package + "."
    if not dotted.startswith(pkg):
        return None, f"{dotted}: not in package {ps.package}"
    msg_name, _, field_name = dotted[len(pkg):].rpartition(".")
    msg = ps.messages.get(msg_name)
    if msg is None:
        return None, f"{dotted}: no message {msg_name}"
    f = next((f for f in msg.fields if f.name == field_name), None)
    if f is None:
        return None, f"{dotted}: no field {field_name} in {msg_name}"
    return f, None


def check_proto(reg: Registry, ps: ProtoSet | None = None) -> list[str]:
    errs: list[str] = []
    ps = ps if ps is not None else parse_dir(PROTO_DIR)
    for c in reg.manifest.get("containers", []):
        f, err = _proto_field(ps, c["proto"])
        if err:
            errs.append(f"proto: container {c['id']}: {err}")
        elif f.type != "google.protobuf.Struct" or f.label == "repeated":
            errs.append(f"proto: container {c['id']}: {c['proto']} is {f.label} {f.type}, not google.protobuf.Struct")
    for a in reg.attributes:
        for rf in a.get("related_fields") or []:
            _, err = _proto_field(ps, rf)
            if err:
                errs.append(f"proto: {a['key']}: related field {err}")
    return errs


def check_schema(reg: Registry, schema: dict[str, Any] | None = None) -> list[str]:
    errs: list[str] = []
    schema = schema if schema is not None else json.loads(SCHEMA.read_text(encoding="utf-8"))
    for c in reg.manifest.get("containers", []):
        ptr = c["json_schema"]
        node: Any = schema
        try:
            if not ptr.startswith("#/"):
                raise KeyError(ptr)
            for part in ptr[2:].split("/"):
                node = node[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            errs.append(f"schema: container {c['id']}: {ptr} does not resolve in {SCHEMA.name}")
            continue
        if node.get("type") != "object":
            errs.append(f"schema: container {c['id']}: {ptr} has type {node.get('type')!r}, not object")
    return errs


# --- 5. SDK key tables ---------------------------------------------------------------------

VALIDATOR_OF_FN = {
    "str": "non_empty_string", "bool": "boolean", "enum": "enum", "modality": "enum", "intge1": "integer_min_1",
    "nonneg": "finite_number_min_0", "sha": "sha256_hex", "lang": "bcp47_tag", "strlist": "non_empty_string_list",
}


def _fn_validator(fn: str) -> str:
    s = re.sub(r"\(.*\)$", "", fn).lower()
    for pre in ("_t_", "t_", "t"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return VALIDATOR_OF_FN.get(s.replace("_", ""), f"?{fn}")


def sdk_table(lang: str, checks_src: str, consts_src: str) -> tuple[dict[str, str], list[str]]:
    """(key -> validator, modality list) of one SDK, read from its source text."""
    if lang == "python":
        block = re.search(r"DEFINED_KEYS[^=]*=\s*\{(.*?)\n\}", checks_src, re.S)
        pairs = re.findall(r'"([^"]+)"\s*:\s*(_t_\w+(?:\([A-Z_]+\))?)', block.group(1)) if block else []
        mods = re.search(r"^MODALITIES\s*=\s*\((.*?)\)", consts_src, re.S | re.M)
    elif lang == "typescript":
        block = re.search(r"export const DEFINED_KEYS[^=]*=\s*\{(.*?)\n\};", checks_src, re.S)
        raw = re.findall(r'(?:"([^"]+)"|\b([A-Za-z_]\w*))\s*:\s*(t[A-Z]\w*(?:\([A-Z_]+\))?)', block.group(1)) if block else []
        pairs = [(a or b, fn) for a, b, fn in raw]
        mods = re.search(r"export const MODALITIES\s*=\s*\[(.*?)\]", consts_src, re.S)
    elif lang == "rust":
        block = re.search(r"pub const DEFINED_KEYS[^=]*=\s*&\[(.*?)\n\];", checks_src, re.S)
        pairs = re.findall(r'\(\s*"([^"]+)"\s*,\s*(t_\w+)\s*\)', block.group(1)) if block else []
        mods = re.search(r"pub const MODALITIES[^=]*=\s*&\[(.*?)\]", consts_src, re.S)
    else:
        raise ValueError(lang)
    table = {k: _fn_validator(fn) for k, fn in pairs}
    modalities = re.findall(r'"([^"]+)"', mods.group(1)) if mods else []
    return table, modalities


PLANNED_PATTERNS = {
    "python": r"^PLANNED_NAMESPACES\s*=\s*\((.*?)\)",
    "typescript": r"export const PLANNED_NAMESPACES\s*=\s*\[(.*?)\]",
    "rust": r"pub const PLANNED_NAMESPACES[^=]*=\s*&\[(.*?)\]",
}


def sdk_planned_namespaces(lang: str, consts_src: str) -> list[str]:
    """The planned namespaces of one SDK (RC4, SC-2), read from its constants source."""
    m = re.search(PLANNED_PATTERNS[lang], consts_src, re.S | re.M)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def check_sdks(reg: Registry, sources: dict[str, tuple[str, str]] | None = None) -> list[str]:
    errs: list[str] = []
    if sources is None:
        sources = {lang: (a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8"))
                   for lang, (a, b) in SDK_TABLES.items()}
    mine = {a["key"]: a for a in reg.in_container("header.meta")}
    for lang, (checks_src, consts_src) in sources.items():
        table, mods = sdk_table(lang, checks_src, consts_src)
        if not table:
            errs.append(f"sdks: {lang}: cannot read the DEFINED_KEYS table")
            continue
        for k in sorted(set(table) - set(mine)):
            errs.append(f"sdks: {lang}: key {k} is in the validator but not in the registry")
        for k in sorted(set(mine) - set(table)):
            errs.append(f"sdks: {lang}: key {k} is in the registry but not in the validator")
        for k in sorted(set(mine) & set(table)):
            if table[k] != mine[k]["validator"]:
                errs.append(f"sdks: {lang}: {k}: validator {table[k]}, registry says {mine[k]['validator']}")
            if mine[k]["validator"] == "enum" and mods != list(mine[k].get("values") or []):
                errs.append(f"sdks: {lang}: {k}: MODALITIES {mods} differ from the registry {mine[k].get('values')}")
        planned = [n["name"] for n in reg.manifest.get("namespaces", []) if n.get("status") == "planned"]
        theirs = sdk_planned_namespaces(lang, consts_src)
        if theirs != planned:
            errs.append(f"sdks: {lang}: PLANNED_NAMESPACES {theirs} differ from the registry {planned} "
                        "(SC-2: a custom key in a planned namespace gets the MET-3 warning)")
    return errs


# --- 6. conformance check ids --------------------------------------------------------------


def suite_checks(src: str | None = None) -> dict[str, str]:
    """check id -> level, from the @check decorators of the Python suite."""
    src = src if src is not None else PY_CHECKS.read_text(encoding="utf-8")
    out = {}
    for cid, level in re.findall(r'@check\(\s*"([A-Z0-9-]+)"\s*,\s*("?[\w-]+"?)', src):
        out[cid] = "advisory" if level == "ADVISORY" else level.strip('"')
    return out


def check_check_ids(reg: Registry, suite: dict[str, str] | None = None) -> list[str]:
    errs: list[str] = []
    suite = suite if suite is not None else suite_checks()
    for a in reg.attributes:
        for cid in a.get("checks") or []:
            if cid not in suite:
                errs.append(f"checks: {a['key']}: check {cid} is not in the Python suite")
        for r in a.get("requirement") or []:
            for cid in r.get("checks") or []:
                if cid not in suite:
                    errs.append(f"checks: {a['key']}: check {cid} is not in the Python suite")
                elif r.get("scope") in LEVEL_SCOPES and suite[cid] != r["scope"]:
                    errs.append(f"checks: {a['key']}: check {cid} has level {suite[cid]}, requirement scope {r['scope']}")
    return errs


# --- 7. vectors ----------------------------------------------------------------------------

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BCP47_RE = re.compile(r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")


def _is_int(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return abs(v) <= 2 ** 53 - 1
    return isinstance(v, float) and math.isfinite(v) and v.is_integer() and abs(v) <= 2 ** 53 - 1


def value_ok(attr: dict[str, Any], v: Any, newer_minor: bool = False) -> bool:
    """Does v pass the registry validator of attr? (newer_minor: VER-8 allows unknown enum strings.)"""
    kind = attr["validator"]
    if kind == "none":
        return True
    if kind == "non_empty_string":
        return isinstance(v, str) and v != ""
    if kind == "non_empty_string_list":
        return isinstance(v, list) and all(isinstance(x, str) and x != "" for x in v)
    if kind == "boolean":
        return isinstance(v, bool)
    if kind == "integer_min_1":
        return _is_int(v) and v >= 1
    if kind == "finite_number_min_0":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
    if kind == "sha256_hex":
        return isinstance(v, str) and bool(_SHA256_RE.match(v))
    if kind == "bcp47_tag":
        return isinstance(v, str) and bool(_BCP47_RE.match(v))
    if kind == "enum":
        return v in (attr.get("values") or []) or (newer_minor and isinstance(v, str))
    raise ValueError(kind)


def _newer_minor(version: Any) -> bool:
    m = re.fullmatch(r"1\.(\d+)", version) if isinstance(version, str) else None
    return bool(m) and int(m.group(1)) > 0


def check_vectors(reg: Registry, root: Path = CONFORMANCE) -> tuple[list[str], dict[str, int]]:
    """Meta values of the JSON Lines accept vectors; returns (errors, key -> number of vectors that use it)."""
    errs: list[str] = []
    usage: dict[str, int] = {}
    mine = {a["key"]: a for a in reg.in_container("header.meta")}
    for man in sorted(root.glob("*/manifest.json")):
        for vec in json.loads(man.read_text(encoding="utf-8"))["vectors"]:
            if vec.get("format") != "jsonl" or vec.get("expect") != "accept":
                continue
            path = man.parent / vec["file"]
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict) or obj.get("type") != "header" or not isinstance(obj.get("meta"), dict):
                    continue
                newer = _newer_minor(obj.get("spec_version"))
                for k, v in obj["meta"].items():
                    if k in mine:
                        usage[k] = usage.get(k, 0) + 1
                        if not value_ok(mine[k], v, newer):
                            errs.append(f"vectors: {man.parent.name}/{vec['id']}: meta {k} = {v!r} fails {mine[k]['validator']}")
    return errs, usage


# --- 8. docs -------------------------------------------------------------------------------


def slug(heading: str) -> str:
    """GitHub heading anchor (same rules as tools/hygiene/links.js)."""
    s = heading.strip().lower()
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[`*~]", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s", "-", s)


def section_anchor(spec: str, number: str) -> str:
    for line in spec.splitlines():
        m = re.match(r"^#{2,6}\s+(" + re.escape(number) + r"\s.*?)\s*$", line)
        if m:
            return slug(m.group(1))
    return ""


def _md(text: Any) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _type_text(a: dict[str, Any]) -> str:
    if a["type"] == "enum":
        return "enum: " + ", ".join(f"`{v}`" for v in a["values"])
    return f"`{a['type']}`"


def _req_text(a: dict[str, Any]) -> str:
    reqs = a.get("requirement") or []
    if not reqs:
        return "optional"
    parts = []
    for r in reqs:
        t = f"{r['scope']}: {r['level'].replace('_', ' ')}"
        if r.get("condition") and r["condition"] != "always":
            t += f" ({_md(r['condition'])})"
        parts.append(t)
    return "<br>".join(parts)


def _stab_text(a: dict[str, Any]) -> str:
    t = a["stability"]
    if a.get("target_stability"):
        t += f" (proposed {a['target_stability']})"
    return t


def render(reg: Registry, usage: dict[str, int] | None = None) -> str:
    spec = reg.spec_path.read_text(encoding="utf-8")
    spec_rel = "../" + reg.spec_path.name
    man = reg.manifest
    voc = man["vocabulary"]
    out: list[str] = []
    w = out.append
    w("<!-- GENERATED by tools/semconv/semconv.py from spec/semconv/*.yaml. Do not edit by hand. -->")
    w("")
    w("# NTS semantic-convention registry")
    w("")
    w(f"This page lists the convention keys of NeuralTextStream {man['spec']['version']} "
      f"([spec]({spec_rel})). The source of truth is the YAML in this folder: "
      "[manifest.yaml](manifest.yaml) and [attributes/](attributes/). It is normative for the key names, "
      "types, value lists and validators; the key tables of the spec are informative copies (spec 3.4, "
      "resolution SC-7). "
      "The check `python tools/semconv/semconv.py --check` makes the YAML, the spec tables, the proto "
      "files, the JSON Schema and the three SDK validators agree. How to use it: "
      "[docs/semconv.md](../../docs/semconv.md).")
    w("")
    n_keys = len(reg.attributes)
    n_meta = len(reg.in_container("header.meta"))
    w(f"Counts: {n_keys} keys ({n_meta} `meta` keys), {len(man['containers'])} containers, "
      f"{sum(1 for n in man['namespaces'] if n['status'] == 'reserved')} reserved and "
      f"{sum(1 for n in man['namespaces'] if n['status'] == 'planned')} planned namespaces, "
      f"{len(man.get('open_questions', []))} open question(s), "
      f"{len(man.get('resolved_questions', []))} resolved question(s).")
    w("")
    w("## How to read the tables")
    w("")
    w("| Column | Meaning |")
    w("|---|---|")
    w("| Key | The key name inside its container |")
    w("| Type | The JSON type (see the list below). An enum lists its values |")
    w("| Unit | The unit of a physical quantity (`s` = seconds, TIM-1). `-`: the key is a count, an index, a flag, an identifier or a text and has no unit (SC-6) |")
    w("| Requirement | Per scope: a producer level of spec 9.2 or a conformance class of 9.1. Levels are cumulative. Without an entry, the key is optional |")
    w("| Stability | The level now (all entries are Development until 1.0 is final, spec 12) and the level that spec 2.3 proposes for 1.0 |")
    w("| Validator | What the Python, TypeScript and Rust validators check |")
    w("| Rules | Rule ids of the spec |")
    w("")
    w("| Word | Kind | Meaning |")
    w("|---|---|---|")
    for group, kind in (("types", "type"), ("validators", "validator"), ("requirement_levels", "requirement")):
        for k, v in voc[group].items():
            w(f"| `{k}` | {kind} | {_md(v)} |")
    w("")
    w("## Containers")
    w("")
    w("| Container | Proto field | JSON Schema | Spec | Rules | Custom keys |")
    w("|---|---|---|---|---|---|")
    for c in man["containers"]:
        anchor = section_anchor(spec, c["spec_section"])
        w(f"| `{c['id']}` | `{c['proto']}` | `{c['json_schema']}` | [{c['spec_section']}]({spec_rel}#{anchor}) | "
          f"{', '.join(c.get('rules', []))} | {_md(c.get('custom_keys', ''))} |")
    w("")
    w("## Namespaces of `meta`")
    w("")
    w(f"Spec [12.5]({spec_rel}#{section_anchor(spec, '12.5')}). Policy: only a spec version (through a FEP) "
      "adds a key to a reserved namespace. Keys outside these namespaces are custom keys (MET-3).")
    w("")
    w("| Namespace | Status | Keys |")
    w("|---|---|---|")
    for ns in man["namespaces"]:
        keys = [a["key"] for a in reg.in_container("header.meta") if a["_namespace"] == ns["name"]]
        name = f"`{ns['name']}`" if ns.get("flat") else f"`{ns['name']}.*`"
        status = ns["status"] + (" (no keys defined yet, open question SC-9)" if ns["status"] == "planned" else "")
        w(f"| {name} | {status} | {', '.join(f'`{k}`' for k in keys) or '-'} |")
    w("")
    for g in reg.groups:
        cont = reg.containers[g["container"]]
        title = f"`{g['namespace']}`" if g.get("namespace") else f"`{g['container']}`"
        where = "header `meta`" if g["container"] == "header.meta" else f"`{g['container']}`"
        w(f"## {title}")
        w("")
        w(f"{_md(g.get('brief', ''))} Container: {where}. Spec "
          f"[{cont['spec_section']}]({spec_rel}#{section_anchor(spec, cont['spec_section'])}). "
          f"Source: [{g['_file']}]({g['_file']}).")
        w("")
        w("| Key | Type | Unit | Requirement | Stability | Validator | Description | Rules |")
        w("|---|---|---|---|---|---|---|---|")
        for a in [a for a in reg.attributes if a["_file"] == g["_file"]]:
            desc = _md(a["brief"])
            if a.get("examples"):
                desc += " Examples: " + ", ".join(f"`{e}`" for e in a["examples"]) + "."
            if a.get("registered_values"):
                desc += (" Open list (SC-4). Registered values: " + ", ".join(f"`{e}`" for e in a["registered_values"])
                         + ". Other values are valid.")
            elif a.get("type") == "enum":
                desc += " Closed list (SC-4)."
            if a.get("unknown_value"):
                desc += f" Unknown value of a newer minor version: read as `{a['unknown_value']}`."
            if "default" in a:
                desc += f" Default: `{json.dumps(a['default'])}`."
            if usage and a["key"] in usage and g["container"] == "header.meta":
                desc += f" Used in {usage[a['key']]} accept vector(s)."
            checks = sorted(set((a.get("checks") or []) + [c for r in a.get("requirement") or [] for c in r.get("checks") or []]))
            rules = ", ".join(a.get("rules") or [])
            if checks:
                rules += ("<br>" if rules else "") + "checks: " + ", ".join(checks)
            w(f"| `{a['key']}` | {_type_text(a)} | {a.get('unit') or '-'} | {_req_text(a)} | {_stab_text(a)} | "
              f"`{a['validator']}` | {desc} | {rules} |")
        w("")
    w("## Open questions")
    w("")
    w("The registry adds no semantics. These gaps need a spec change (a FEP or the next RC).")
    w("")
    for q in man.get("open_questions", []):
        w(f"- **{q['id']} {_md(q['title'])}.** {_md(q['text'])}")
    w("")
    if man.get("resolved_questions"):
        w("## Resolved questions")
        w("")
        w(f"Answered by the spec version of this registry ({_md(man['spec']['version'])}).")
        w("")
        w("| Id | Question | Resolution |")
        w("|---|---|---|")
        for q in man["resolved_questions"]:
            w(f"| {q['id']} | {_md(q['title'])} | {_md(q['resolution'])} |")
        w("")
    return "\n".join(out)


# --- main ----------------------------------------------------------------------------------


def run_checks(reg: Registry) -> tuple[list[str], dict[str, int]]:
    errs = check_structure(reg)
    errs += check_spec(reg)
    errs += check_proto(reg)
    errs += check_schema(reg)
    errs += check_sdks(reg)
    errs += check_check_ids(reg)
    verrs, usage = check_vectors(reg)
    return errs + verrs, usage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="run all checks and compare registry.md; write nothing")
    ap.add_argument("--json", action="store_true", help="print the loaded registry as JSON")
    args = ap.parse_args(argv)
    reg = load()
    if args.json:
        print(json.dumps({"manifest": reg.manifest,
                          "attributes": [{k: v for k, v in a.items() if not k.startswith("_")} | {"container": a["_container"]}
                                         for a in reg.attributes]}, indent=1, ensure_ascii=False))
        return 0
    errs, usage = run_checks(reg)
    text = render(reg, usage)
    if args.check:
        current = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
        if current.replace("\r\n", "\n") != text:
            errs.append(f"docs: {DOC.relative_to(ROOT).as_posix()} is out of date: run python tools/semconv/semconv.py")
    for e in errs:
        print("ERROR", e)
    if errs:
        print(f"semconv: {len(errs)} error(s)")
        return 1
    if not args.check:
        DOC.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {DOC.relative_to(ROOT).as_posix()}")
    print(f"semconv: OK ({len(reg.attributes)} keys, {len(reg.manifest['containers'])} containers; "
          f"spec, proto, schema, 3 SDKs, suite checks and {sum(usage.values())} vector uses agree)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
