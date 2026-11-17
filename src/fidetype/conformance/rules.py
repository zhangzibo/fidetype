"""Map conformance check ids to the rule ids of the NTS 1.0 spec (P7-01).

The spec (``spec/nts-1.0-rc4.md``, Appendix C.1) has one row per normative
rule: the rule id, its keyword, the check ids that test it and the vectors.
This module reads that table and inverts it: check id -> rule ids. The
``nts-conform`` report uses the map to name the rules behind each check.

The committed copy is ``spec/conformance/kit/rule-map.json`` (it ships in
the wheel with the vectors). Regenerate it after a change of Appendix C::

    nts-conform rules --write

A test fails if the committed copy is stale.

Finer mapping (P7-02). Some checks test many rules at once (``FEP2-CONSUME``
maps to 17 rule ids). A level report that lists all 17 for one failure is not
accurate. :data:`REFINE` maps known messages of these broad checks to the one
or two rules that the message is about. ``rules_for`` uses it, and the
committed ``rule-map.json`` carries it under ``refine`` so that other tools
can use the same table. A message that no pattern matches keeps the full list.
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

# --- finer mapping of broad checks (P7-02) --------------------------------------------------------
# (regular expression on the finding message, rule ids). Every pattern that matches adds its rules; a
# template "CTL-S{1}" takes the number of the FEP rule that the message names ("(rule 3)" -> CTL-S3).
_LSL = [
    (r"is not JSON|no desc/fidetype/nts_header|nts_header must be a JSON object", ["LSL-D1"]),
    (r"channels but the vocab", ["LSL-F2"]),
    (r"must be float32 or double64|type '[^']*' is not 'NTS'", ["LSL-F1"]),
    (r"channel labels differ", ["LSL-F3"]),
    (r"nominal_srate", ["LSL-F6"]),
    (r"binding '[^']*' is not supported", ["LSL-V1", "VER-9"]),
    (r"events stream must have", ["LSL-E1"]),
    (r"NaN or \+inf", ["LSL-F5"]),
    (r"spec_version", ["LSL-D2", "VER-5"]),
    (r"values kind|values '[^']*' is not", ["LSL-D3", "VER-9"]),
    (r"event_clock", ["LSL-C5"]),
]
REFINE: dict[str, list[tuple[str, list[str]]]] = {
    "FEP2-CONSUME": _LSL,
    "FEP2-FRAMES": _LSL,
    "FEP2-DESC": _LSL,
    "FEP2-DECISIONS": [
        (r"decisions stream has 1 channel|event_type must be", ["LSL-X1"]),
        (r"second final decision|after its final one", ["TD-6", "LSL-X2"]),
        (r"not JSON|must be a|is not one of|is required", ["LSL-X2"]),
    ],
    "FEP1-TD-FORMAT": [
        (r"spec_version", ["TD-F3", "VER-5"]),
        (r"\(rule 8\)", ["TD-8"]),
        (r"\(rule 9", ["TD-9"]),
        (r"\b(is_final|action|p_top1|score_semantics)\b", ["TD-F1"]),
        (r"\b(shown|seq|session|utterance|config_id|input|latency_s|guard_risk|set_size|reason|declaration) must",
         ["TD-F2"]),
    ],
    "FEP1-TD-FINAL": [
        (r"does not increase", ["TD-5"]),
        (r"second final decision", ["TD-6"]),
        (r"a decision for .* after its final one", ["TD-7"]),
    ],
    "FEP3-DECL": [
        (r"is not unique", ["INT-D1"]),
        (r"risk '[^']*' is not one of", ["INT-D2"]),
        (r"at most one intent may have role", ["INT-D3"]),
        (r"confirm intent .* must be 'irreversible'", ["INT-D4"]),
    ],
    "FEP3-INTENT": [
        (r"without an intent_declaration", ["INT-E1"]),
        (r"is not in the declaration|appears twice", ["INT-E2"]),
        (r"score must be|scores sum to", ["INT-E3"]),
        (r"ranked best first", ["INT-E4"]),
        (r"is not unique in the stream", ["INT-E5"]),
        (r"\b(is_final|id|t|candidates) must be", ["INT-E7"]),
    ],
    "FEP3-TD-FORMAT": [
        (r"uses unit|unit must be", ["INT-T1"]),
        (r"MUST NOT carry shown", ["INT-T2"]),
        (r"COMMIT needs (the committed intent|risk_class)|risk_class '", ["INT-T3"]),
        (r"profile '[^']*' is not one of", ["PRF-4"]),
        (r"intent action '", ["TD-F1"]),
        (r"confirm_required", ["INT-T7"]),
        (r"\b(vocab_id|pending_cleared) must", ["INT-T8"]),
    ],
    "FEP3-TD-FINAL": [
        (r"second final decision", ["INT-T4"]),
        (r"does not increase", ["TD-5", "INT-T6"]),
    ],
    "FEP3-SAFETY": [(r"\(rule ([1-5])\)", ["INT-S{1}"])],
    "FEP4-HANDSHAKE": [
        (r"first message must be the NTS header", ["WS-S1"]),
        (r"subprotocol", ["WS-H2"]),
        (r"unknown binding", ["WS-V1", "VER-9"]),
        (r"spec_version", ["HDR-2", "VER-5", "WS-S1"]),
        (r"meta must be a JSON object", ["HDR-8", "WS-S1"]),
    ],
    "FEP4-FRAMING": [
        (r"binary messages", ["WS-F1"]),
        (r"bad_message", ["WS-F2", "GEN-2"]),
        (r"ws_seq .* must be an integer", ["WS-Q1"]),
        (r"consecutive ws_seq|ws_batch of", ["WS-Q4"]),
    ],
    "FEP4-DECISIONS": [
        (r"ws_welcome|unknown binding", ["WS-D1", "WS-V1"]),
        (r"ws_seq", ["WS-D3"]),
        (r"second final decision", ["TD-6"]),
    ],
    "FEP5-CONTROL": [
        (r"without a control_declaration", ["CTL-1"]),
        (r"does not increase", ["CTL-2"]),
        (r"MUST carry std", ["CTL-3"]),
        (r"\b(values|std|values\[\d+\]) must be", ["CTL-4"]),
        (r"timing fields", ["TIM-4"]),
        (r"pointer dims", ["CTL-12"]),
    ],
    "FEP5-SAFETY": [(r"\(rule ([1-8])\)", ["CTL-S{1}"])],
    "FEP5-TD-FORMAT": [(r"\(rule ([1-4])\)", ["CTL-T{1}"]), (r"state '[^']*' is not one of", ["CTL-T3"]),
                       (r"\(TD-F2\)", ["TD-F2"]), (r"\b(gain|velocity|raw|authority|engagement|units) must", ["CTL-T4"]),
                       (r"\b(radius|level) must", ["CTL-T8"]), (r"\breasons\b", ["CTL-T9"])],
}


def refine(check_id: str, message: str) -> list[str]:
    """The rule ids that :data:`REFINE` finds in a message of a broad check (empty: no pattern matched)."""
    out: list[str] = []
    for pat, rules in REFINE.get(check_id, []):
        for m in re.finditer(pat, message or ""):
            for r in rules:
                r = r.replace("{1}", m.group(1)) if "{1}" in r else r
                if r not in out:
                    out.append(r)
    return out


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
            "checks": dict(sorted(checks.items())), "rules": dict(sorted(rules.items())),
            "refine": {c: [[pat, rs] for pat, rs in pats] for c, pats in sorted(REFINE.items())}}


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
    """The rule ids that a check tests.

    If the message names rule ids of that check, keep only those. Else, if a
    :data:`REFINE` pattern of the check matches the message, use its rules
    (finer mapping, P7-02). Else all rules of the check.
    """
    rm = load_rule_map()
    mapped = list(rm["checks"].get(check_id, []))
    named = [r for r in _RULE.findall(message or "") if r in rm["rules"]]
    narrowed = [r for r in named if r in mapped]
    if narrowed:
        return list(dict.fromkeys(narrowed))
    fine = [r for r in refine(check_id, message) if r in rm["rules"]]
    return fine or mapped


__all__ = ["REFINE", "RULE_MAP_SCHEMA", "SPEC_LABEL", "load_rule_map", "parse_appendix_c", "refine", "render_rule_map",
           "rules_for"]
