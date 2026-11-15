#!/usr/bin/env python3
"""Compile the NTS proto files with protoc and compare them with tools/proto/protoparse.py.

Needs the grpcio-tools package (it contains protoc and the protobuf runtime).
Nothing is installed into the project. For example:

    uvx --from grpcio-tools python tools/proto/check_protoc.py
    # or: pip install grpcio-tools && python tools/proto/check_protoc.py

The check fails if protoc refuses a file, or if protoc and the small parser
disagree on a message, a field (name, number, type, label, oneof), an enum
value, or a custom option (json_type, json_rule, json_value and the field
options). This keeps the generator, which uses the small parser, honest.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from protoparse import parse_dir  # noqa: E402

REPO = HERE.parent.parent
PROTO_ROOT = REPO / "spec" / "proto"
PROTO_DIR = PROTO_ROOT / "neuraltextstream" / "v1"

SCALARS = {1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32", 6: "fixed64", 7: "fixed32", 8: "bool",
           9: "string", 12: "bytes", 13: "uint32", 15: "sfixed32", 16: "sfixed64", 17: "sint32", 18: "sint64"}
FIELD_OPTS = ("json_required", "json_nullable", "null_binary", "json_inline", "minimum", "maximum",
              "exclusive_minimum", "exclusive_maximum", "pattern", "min_length", "min_items", "max_items", "unique_items")


def main() -> int:
    import grpc_tools
    from grpc_tools import protoc
    from google.protobuf import descriptor_pb2

    inc = os.path.join(os.path.dirname(grpc_tools.__file__), "_proto")
    files = sorted(str(p.relative_to(PROTO_ROOT)).replace("\\", "/") for p in PROTO_DIR.glob("*.proto"))
    with tempfile.TemporaryDirectory() as tmp:
        ds = os.path.join(tmp, "nts.pb")
        rc = protoc.main(["protoc", f"-I{PROTO_ROOT}", f"-I{inc}", f"--descriptor_set_out={ds}", f"--python_out={tmp}",
                          *files])
        if rc != 0:
            print("protoc refused the files", file=sys.stderr)
            return 1
        sys.path.insert(0, tmp)
        opts = importlib.import_module("neuraltextstream.v1.options_pb2")
        fds = descriptor_pb2.FileDescriptorSet()
        fds.ParseFromString(Path(ds).read_bytes())

    ps = parse_dir(PROTO_DIR)
    errs: list[str] = []
    seen_msgs, seen_enums = set(), set()

    def ext(o, name):
        e = getattr(opts, name)
        rep = getattr(e, "is_repeated", None)
        if rep is None:  # older protobuf runtimes
            rep = e.label == e.LABEL_REPEATED
        if rep:
            return list(o.Extensions[e]) or None
        return o.Extensions[e] if o.HasExtension(e) else None

    for fd in fds.file:
        if not fd.name.startswith("neuraltextstream/"):
            continue
        if fd.package != ps.package:
            errs.append(f"{fd.name}: package {fd.package} != {ps.package}")
        for en in fd.enum_type:
            seen_enums.add(en.name)
            mine = ps.enums.get(en.name)
            if mine is None:
                errs.append(f"enum {en.name} missing in the parser")
                continue
            a = [(v.name, v.number, ext(v.options, "json_value")) for v in en.value]
            b = [(v.name, v.number, v.options.get("json_value")) for v in mine.values]
            if a != b:
                errs.append(f"enum {en.name}: protoc {a} != parser {b}")
        for m in fd.message_type:
            seen_msgs.add(m.name)
            mine = ps.messages.get(m.name)
            if mine is None:
                errs.append(f"message {m.name} missing in the parser")
                continue
            if (ext(m.options, "json_type") or None) != mine.options.get("json_type"):
                errs.append(f"{m.name}: json_type differs")
            if (ext(m.options, "json_rule") or []) != mine.options.get("json_rule", []):
                errs.append(f"{m.name}: json_rule differs")
            if len(m.field) != len(mine.fields):
                errs.append(f"{m.name}: {len(m.field)} fields (protoc) != {len(mine.fields)} (parser)")
            for f, g in zip(m.field, mine.fields):
                typ = SCALARS.get(f.type) or f.type_name.lstrip(".").removeprefix(ps.package + ".")
                label = "repeated" if f.label == f.LABEL_REPEATED else ("optional" if f.proto3_optional else "")
                oneof = None
                if f.HasField("oneof_index") and not f.proto3_optional:
                    oneof = m.oneof_decl[f.oneof_index].name
                a = (f.name, f.number, typ, label, oneof)
                b = (g.name, g.number, g.type, g.label, g.oneof)
                if a != b:
                    errs.append(f"{m.name}: protoc {a} != parser {b}")
                for o in FIELD_OPTS:
                    pa, pb = ext(f.options, o), g.options.get(o)
                    if pa != pb and not (isinstance(pa, float) and pb is not None and float(pb) == pa):
                        errs.append(f"{m.name}.{f.name}: option {o} protoc {pa!r} != parser {pb!r}")
    for name in set(ps.messages) - seen_msgs:
        errs.append(f"message {name} not seen by protoc")
    for name in set(ps.enums) - seen_enums:
        errs.append(f"enum {name} not seen by protoc")
    for e in errs:
        print(e, file=sys.stderr)
    print(f"protoc: {len(files)} files compiled; {len(ps.messages)} messages and {len(ps.enums)} enums compared; "
          f"{len(errs)} difference(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
