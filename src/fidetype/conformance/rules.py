"""Map conformance check ids to the rule ids of the NTS 1.0 spec (P7-01).

The spec (``spec/nts-1.0-rc4.md``, Appendix C.1) has one row per normative
rule: the rule id, its keyword, the check ids that test it and the vectors.
This module reads that table and inverts it: check id -> rule ids. The
``nts-conform`` report uses the map to name the rules behind each check.

The committed copy is ``spec/conformance/kit/rule-map.json`` (it ships in
the wheel with the vectors). Regenerate it after a change of Appendix C::

    nts-conform rules --write

A test fails if the committed copy is stale.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

RULE_MAP_SCHEMA = "fidetype.conformance.rule-map/1"
SPEC_FILE = "nts-1.0-rc4.md"
SPEC_LABEL = "NTS 1.0 RC4 (draft)"

_RULE = re.compile(r"\b([A-Z]{2,4}-[A-Z]{0,2}\d+)\b")  # HDR-1, INT-D1, TD-F2, CTL-T5, WS-H2
_RANGE = re.compile(r"\b([A-Z]{2,4}-[A-Z]{0,2})(\d+)\s*…\s*\1(\d+)\b")  # "INT-D1 … INT-D4"
_CHECK = re.compile(r"\b((?:NTS|TR|PV|FEP\d)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b")
# Rows of C.1 whose check cell is only the word "advisory": the advisory check that tests the rule.
_ADVISORY_ONLY = {"FIL-5": ["NTS-NPZ-DTYPE"]}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def spec_path() -> Path:
    return repo_root() / "spec" / SPEC_FILE


def _expand_rules(cell: str) -> list[str]:
    """``"INT-D1 … INT-D4"`` -> INT-D1, INT-D2, INT-D3, INT-D4; ``"TD-9 (1.x)"`` -> TD-9."""
    out: list[str] = []
    for m in _RANGE.finditer(cell):
        out += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)]
    for r in _RULE.findall(_RANGE.sub("", cell)):
        out.append(r)
    seen: list[str] = []
    for r in out:
        if r not in seen:
            seen.append(r)
    return seen


def known_check_ids() -> set[str]:
    from fidetype.conformance.checks import REGISTRY
    from fidetype.conformance.profiles import PROFILE_NAMES, get_profile

    ids = {c.check_id for c in REGISTRY}
    for p in PROFILE_NAMES:
        ids |= {c["id"] for c in get_profile(p).checks}
    return ids


def parse_appendix_c(text: str) -> dict[str, Any]:
    """Read table C.1 of the spec text. Returns the rule-map document."""
    start = text.index("### C.1 Table")
    end = text.index("### C.2", start)
    known = known_check_ids()
    checks: dict[str, list[str]] = {}
    rules: dict[str, dict[str, Any]] = {}
    for line in text[start:end].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("Rule", "") or set(cells[0]) <= {"-"}:
            continue
        rule_ids = _expand_rules(cells[0])
        check_ids = [c for c in _CHECK.findall(cells[2]) if c in known]
        if not check_ids and cells[2] == "advisory":
            check_ids = [c for r in rule_ids for c in _ADVISORY_ONLY.get(r, [])]
        for r in rule_ids:
            ent = rules.setdefault(r, {"keyword": cells[1], "checks": [], "status": cells[4]})
            for c in check_ids:
                if c not in ent["checks"]:
                    ent["checks"].append(c)
        for c in check_ids:
            lst = checks.setdefault(c, [])
            lst += [r for r in rule_ids if r not in lst]
    return {"schema": RULE_MAP_SCHEMA, "spec": SPEC_LABEL, "source": f"spec/{SPEC_FILE} Appendix C.1",
            "generator": "nts-conform rules --write",
            "checks": dict(sorted(checks.items())), "rules": dict(sorted(rules.items()))}


def render_rule_map() -> str:
    doc = parse_appendix_c(spec_path().read_text(encoding="utf-8"))
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def rule_map_path() -> Path:
    from fidetype.conformance.kit import kit_dir

    return kit_dir() / "rule-map.json"


@lru_cache(maxsize=1)
def load_rule_map() -> dict[str, Any]:
    """The committed map (``spec/conformance/kit/rule-map.json``); empty maps if it is absent."""
    p = rule_map_path()
    if not p.is_file():
        return {"schema": RULE_MAP_SCHEMA, "spec": SPEC_LABEL, "checks": {}, "rules": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def rules_for(check_id: str, message: str = "") -> list[str]:
    """The rule ids that a check tests. If the message names rule ids of that check, keep only those."""
    rm = load_rule_map()
    mapped = list(rm["checks"].get(check_id, []))
    named = [r for r in _RULE.findall(message or "") if r in rm["rules"]]
    narrowed = [r for r in named if r in mapped]
    if narrowed:
        return list(dict.fromkeys(narrowed))
    return mapped


__all__ = ["RULE_MAP_SCHEMA", "SPEC_LABEL", "load_rule_map", "parse_appendix_c", "render_rule_map", "rules_for"]
