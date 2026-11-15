"""A small proto3 parser for the NTS proto files (standard library only).

It reads the subset of proto3 that spec/proto/neuraltextstream/v1/*.proto
uses: syntax, package, import, file options, messages (not nested), enums,
oneofs, fields with [options], reserved statements, and comments. It keeps
the leading comment of each declaration, because the generator writes it
into the JSON Schema as the description.

It is not a full protobuf compiler. tools/proto/check_protoc.py compiles the
same files with protoc (grpcio-tools) and compares the result with this
parser, so that the two cannot drift apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_TOKEN = re.compile(
    r"""
    (?P<ws>[ \t\r\f\v]+)
  | (?P<nl>\n)
  | (?P<lcomment>//[^\n]*)
  | (?P<bcomment>/\*.*?\*/)
  | (?P<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
  | (?P<number>-?(?:0[xX][0-9a-fA-F]+|[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?|\.[0-9]+(?:[eE][+-]?[0-9]+)?))
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
  | (?P<sym>[{}\[\]();=,<>.])
    """,
    re.VERBOSE | re.DOTALL,
)

_SIMPLE_ESC = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
               "\\": "\\", "'": "'", '"': '"', "?": "?"}


def unescape(lit: str) -> str:
    """Decode a proto string literal (with its quotes), as protoc does for C escapes."""
    body, out, i = lit[1:-1], [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        n = body[i + 1]
        if n in _SIMPLE_ESC:
            out.append(_SIMPLE_ESC[n])
            i += 2
        elif n in "xX":
            m = re.match(r"[0-9a-fA-F]{1,2}", body[i + 2:])
            out.append(chr(int(m.group(0), 16)))
            i += 2 + len(m.group(0))
        elif n in "01234567":
            m = re.match(r"[0-7]{1,3}", body[i + 1:])
            out.append(chr(int(m.group(0), 8)))
            i += 1 + len(m.group(0))
        else:
            raise ValueError(f"unsupported escape \\{n} in {lit}")
    return "".join(out)


@dataclass
class Tok:
    kind: str
    text: str
    line: int


@dataclass
class Field:
    name: str
    number: int
    type: str
    label: str  # "", "optional" or "repeated"
    options: dict[str, Any]
    comment: str
    oneof: str | None = None


@dataclass
class Message:
    name: str
    file: str
    comment: str
    fields: list[Field] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    reserved: list[Any] = field(default_factory=list)


@dataclass
class EnumValue:
    name: str
    number: int
    options: dict[str, Any]
    comment: str


@dataclass
class Enum:
    name: str
    file: str
    comment: str
    values: list[EnumValue] = field(default_factory=list)


@dataclass
class ProtoSet:
    package: str = ""
    messages: dict[str, Message] = field(default_factory=dict)
    enums: dict[str, Enum] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


class _Parser:
    def __init__(self, text: str, fname: str, out: ProtoSet) -> None:
        self.fname, self.out = fname, out
        self.toks: list[Tok] = []
        self.comments: dict[int, str] = {}  # line -> text of a // comment that is alone on its line
        line, last_code_line = 1, 0
        pos = 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m:
                raise SyntaxError(f"{fname}:{line}: cannot read {text[pos:pos + 20]!r}")
            kind, val = m.lastgroup, m.group(0)
            pos = m.end()
            if kind == "nl":
                line += 1
            elif kind == "ws":
                pass
            elif kind == "lcomment":
                if last_code_line != line:
                    self.comments[line] = val[2:].strip()
            elif kind == "bcomment":
                line += val.count("\n")
            else:
                self.toks.append(Tok(kind, val, line))
                last_code_line = line
        self.i = 0

    # --- token helpers -------------------------------------------------------------------
    def peek(self, k: int = 0) -> Tok | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, text: str) -> Tok:
        t = self.next()
        if t.text != text:
            raise SyntaxError(f"{self.fname}:{t.line}: expected {text!r}, got {t.text!r}")
        return t

    def comment_before(self, line: int) -> str:
        lines, ln = [], line - 1
        while ln in self.comments:
            lines.append(self.comments[ln])
            ln -= 1
        return " ".join(x for x in reversed(lines) if x).strip()

    def constant(self) -> Any:
        t = self.next()
        if t.kind == "string":
            s = unescape(t.text)
            while self.peek() is not None and self.peek().kind == "string":  # adjacent literals concatenate
                s += unescape(self.next().text)
            return s
        if t.kind == "number":
            return float(t.text) if any(c in t.text for c in ".eE") and not t.text.lower().startswith(("0x", "-0x")) \
                else int(t.text, 0)
        if t.text in ("true", "false"):
            return t.text == "true"
        if t.kind == "ident":
            return t.text
        raise SyntaxError(f"{self.fname}:{t.line}: bad constant {t.text!r}")

    def option_name(self) -> str:
        if self.peek().text == "(":
            self.next()
            name = self.next().text
            self.expect(")")
            if self.peek().text == ".":
                self.next()
                name += "." + self.next().text
            # options of this package may be named with or without the package prefix
            pkg = self.out.package + "."
            return name[len(pkg):] if name.startswith(pkg) else name
        return self.next().text

    def field_options(self) -> dict[str, Any]:
        opts: dict[str, Any] = {}
        if self.peek().text != "[":
            return opts
        self.next()
        while True:
            name = self.option_name()
            self.expect("=")
            opts[name] = self.constant()
            t = self.next()
            if t.text == "]":
                return opts
            if t.text != ",":
                raise SyntaxError(f"{self.fname}:{t.line}: expected ',' or ']'")

    # --- grammar -------------------------------------------------------------------------
    def parse(self) -> None:
        while self.peek() is not None:
            t = self.peek()
            if t.text == "syntax":
                self.next(); self.expect("="); v = self.constant(); self.expect(";")
                if v != "proto3":
                    raise SyntaxError(f"{self.fname}: only proto3 is supported")
            elif t.text == "package":
                self.next(); pkg = self.next().text; self.expect(";")
                if self.out.package and self.out.package != pkg:
                    raise SyntaxError(f"{self.fname}: all files must use package {self.out.package}")
                self.out.package = pkg
            elif t.text == "import":
                self.next(); self.constant(); self.expect(";")
            elif t.text == "option":
                self.next(); self.option_name(); self.expect("="); self.constant(); self.expect(";")
            elif t.text == "extend":
                self.skip_block()
            elif t.text == "message":
                self.message()
            elif t.text == "enum":
                self.enum()
            else:
                raise SyntaxError(f"{self.fname}:{t.line}: unexpected {t.text!r}")

    def skip_block(self) -> None:
        while self.next().text != "{":
            pass
        depth = 1
        while depth:
            t = self.next().text
            depth += {"{": 1, "}": -1}.get(t, 0)

    def message(self) -> None:
        start = self.next()
        name = self.next().text
        msg = Message(name, self.fname, self.comment_before(start.line))
        self.expect("{")
        oneof: str | None = None
        while True:
            t = self.peek()
            if t.text == "}":
                self.next()
                if oneof is not None:
                    oneof = None
                    continue
                break
            if t.text == "option":
                self.next()
                oname = self.option_name()
                self.expect("=")
                val = self.constant()
                self.expect(";")
                if oname == "json_rule":
                    msg.options.setdefault("json_rule", []).append(val)
                else:
                    msg.options[oname] = val
            elif t.text == "reserved":
                self.next()
                while True:
                    msg.reserved.append(self.constant())
                    if self.peek().text == "to":
                        self.next(); msg.reserved.append(("to", self.constant()))
                    if self.next().text == ";":
                        break
            elif t.text == "oneof":
                self.next()
                oneof = self.next().text
                self.expect("{")
            elif t.text in ("message", "enum"):
                raise SyntaxError(f"{self.fname}:{t.line}: nested types are not supported")
            else:
                msg.fields.append(self.field(oneof))
        if name in self.out.messages or name in self.out.enums:
            raise SyntaxError(f"{self.fname}: duplicate type {name}")
        self.out.messages[name] = msg

    def field(self, oneof: str | None) -> Field:
        first = self.peek()
        label = ""
        if first.text in ("optional", "repeated"):
            label = self.next().text
        if self.peek().text == "map":
            raise SyntaxError(f"{self.fname}:{first.line}: map fields are not supported")
        typ = self.next().text
        name = self.next().text
        self.expect("=")
        num = self.constant()
        opts = self.field_options()
        self.expect(";")
        return Field(name, int(num), typ, label, opts, self.comment_before(first.line), oneof)

    def enum(self) -> None:
        start = self.next()
        name = self.next().text
        en = Enum(name, self.fname, self.comment_before(start.line))
        self.expect("{")
        while self.peek().text != "}":
            t = self.peek()
            if t.text in ("option", "reserved"):
                while self.next().text != ";":
                    pass
                continue
            vname = self.next().text
            self.expect("=")
            num = self.constant()
            opts = self.field_options()
            self.expect(";")
            en.values.append(EnumValue(vname, int(num), opts, self.comment_before(t.line)))
        self.next()
        if name in self.out.messages or name in self.out.enums:
            raise SyntaxError(f"{self.fname}: duplicate type {name}")
        self.out.enums[name] = en


def parse_dir(root: str | Path) -> ProtoSet:
    """Parse every .proto file in ``root`` (sorted by name) into one ProtoSet."""
    out = ProtoSet()
    for p in sorted(Path(root).glob("*.proto")):
        out.files.append(p.name)
        _Parser(p.read_text(encoding="utf-8"), p.name, out).parse()
    return out
