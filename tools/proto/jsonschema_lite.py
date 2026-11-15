"""A small JSON Schema (draft 2020-12) validator for the generated NTS schema.

Standard library only. It supports exactly the keywords that
tools/proto/gen_jsonschema.py writes, and it refuses a schema with any other
validation keyword (so that a new keyword cannot be ignored without notice).
CI also runs the parity test with the reference library ``jsonschema``
(tools/proto/parity.py --engine jsonschema); the two must agree.

JSON data model rules (as in the JSON Schema specification):
- a boolean is not a number;
- "integer" is any number with a zero fraction part, so 1.0 is an integer
  (this is why GEN-5 cannot be checked by a schema);
- const and enum use JSON equality (1 == 1.0, but true != 1).
"""

from __future__ import annotations

import math
import re
from typing import Any

ANNOTATIONS = {"$schema", "$id", "$comment", "title", "description", "$defs", "default", "x-nts-rules", "x-proto"}
KEYWORDS = {
    "$ref", "type", "enum", "const", "required", "properties", "items", "prefixItems", "minItems", "maxItems",
    "uniqueItems", "contains", "minContains", "maxContains", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "pattern", "minLength", "allOf", "anyOf", "oneOf", "not", "if", "then", "else",
}


def _kind(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "boolean"
    if isinstance(x, (int, float)):
        return "number"
    if isinstance(x, str):
        return "string"
    if isinstance(x, list):
        return "array"
    if isinstance(x, dict):
        return "object"
    raise TypeError(f"not a JSON value: {x!r}")


def json_equal(a: Any, b: Any) -> bool:
    ka, kb = _kind(a), _kind(b)
    if ka != kb:
        return False
    if ka == "array":
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    if ka == "object":
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    return a == b


def _is_type(x: Any, t: str) -> bool:
    k = _kind(x)
    if t == "integer":
        return k == "number" and (isinstance(x, int) or (math.isfinite(x) and float(x).is_integer()))
    return k == t


class Validator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.root = schema
        self._re: dict[str, re.Pattern[str]] = {}
        self._check_keywords(schema)

    def _check_keywords(self, s: Any) -> None:
        if isinstance(s, bool):
            return
        if not isinstance(s, dict):
            raise ValueError(f"a schema must be an object: {s!r}")
        bad = set(s) - KEYWORDS - ANNOTATIONS
        if bad:
            raise ValueError(f"unsupported keywords {sorted(bad)}")
        for k in ("items", "contains", "not", "if", "then", "else"):
            if k in s:
                self._check_keywords(s[k])
        for k in ("allOf", "anyOf", "oneOf", "prefixItems"):
            for sub in s.get(k, []):
                self._check_keywords(sub)
        for sub in s.get("properties", {}).values():
            self._check_keywords(sub)
        for sub in s.get("$defs", {}).values():
            self._check_keywords(sub)

    def _resolve(self, ref: str) -> Any:
        if not ref.startswith("#/"):
            raise ValueError(f"only local $ref is supported: {ref}")
        node: Any = self.root
        for part in ref[2:].split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return node

    def errors(self, x: Any, s: Any = None, path: str = "$") -> list[str]:
        """All errors of instance ``x`` against schema ``s`` (default: the root)."""
        if s is None:
            s = self.root
        if s is True:
            return []
        if s is False:
            return [f"{path}: no value is allowed"]
        out: list[str] = []
        if "$ref" in s:
            out += self.errors(x, self._resolve(s["$ref"]), path)
        if "type" in s:
            types = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_is_type(x, t) for t in types):
                return out + [f"{path}: {x!r} is not of type {types}"]
        if "enum" in s and not any(json_equal(x, v) for v in s["enum"]):
            out.append(f"{path}: {x!r} is not one of {s['enum']}")
        if "const" in s and not json_equal(x, s["const"]):
            out.append(f"{path}: {x!r} is not {s['const']!r}")
        k = _kind(x)
        if k == "number":
            if "minimum" in s and x < s["minimum"]:
                out.append(f"{path}: {x} < minimum {s['minimum']}")
            if "maximum" in s and x > s["maximum"]:
                out.append(f"{path}: {x} > maximum {s['maximum']}")
            if "exclusiveMinimum" in s and x <= s["exclusiveMinimum"]:
                out.append(f"{path}: {x} <= exclusiveMinimum {s['exclusiveMinimum']}")
            if "exclusiveMaximum" in s and x >= s["exclusiveMaximum"]:
                out.append(f"{path}: {x} >= exclusiveMaximum {s['exclusiveMaximum']}")
        if k == "string":
            if "minLength" in s and len(x) < s["minLength"]:
                out.append(f"{path}: shorter than {s['minLength']} code points")
            if "pattern" in s:
                rx = self._re.get(s["pattern"]) or self._re.setdefault(s["pattern"], re.compile(s["pattern"]))
                if not rx.search(x):
                    out.append(f"{path}: {x!r} does not match {s['pattern']!r}")
        if k == "array":
            if "minItems" in s and len(x) < s["minItems"]:
                out.append(f"{path}: fewer than {s['minItems']} items")
            if "maxItems" in s and len(x) > s["maxItems"]:
                out.append(f"{path}: more than {s['maxItems']} items")
            if s.get("uniqueItems") and any(json_equal(x[i], x[j]) for i in range(len(x)) for j in range(i)):
                out.append(f"{path}: items are not unique")
            pre = s.get("prefixItems", [])
            for i, sub in enumerate(pre[:len(x)]):
                out += self.errors(x[i], sub, f"{path}[{i}]")
            if "items" in s:
                for i in range(len(pre), len(x)):
                    out += self.errors(x[i], s["items"], f"{path}[{i}]")
            if "contains" in s:
                n = sum(1 for v in x if not self.errors(v, s["contains"], path))
                lo, hi = s.get("minContains", 1), s.get("maxContains")
                if n < lo:
                    out.append(f"{path}: {n} items match contains (need >= {lo})")
                if hi is not None and n > hi:
                    out.append(f"{path}: {n} items match contains (need <= {hi})")
        if k == "object":
            for r in s.get("required", []):
                if r not in x:
                    out.append(f"{path}: required key {r!r} is missing")
            for key, sub in s.get("properties", {}).items():
                if key in x:
                    out += self.errors(x[key], sub, f"{path}.{key}")
        for sub in s.get("allOf", []):
            out += self.errors(x, sub, path)
        if "anyOf" in s and not any(not self.errors(x, sub, path) for sub in s["anyOf"]):
            out.append(f"{path}: matches no branch of anyOf")
        if "oneOf" in s and sum(1 for sub in s["oneOf"] if not self.errors(x, sub, path)) != 1:
            out.append(f"{path}: does not match exactly one branch of oneOf")
        if "not" in s and not self.errors(x, s["not"], path):
            out.append(f"{path}: matches a schema in not")
        if "if" in s:
            if not self.errors(x, s["if"], path):
                if "then" in s:
                    out += self.errors(x, s["then"], path)
            elif "else" in s:
                out += self.errors(x, s["else"], path)
        return out
