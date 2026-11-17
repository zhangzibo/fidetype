"""Implementation levels NTS Core, NTS Full and NTS Trust-ready (roadmap P7-02).

The normative text is NTS 1.0 RC4, section 9.6 (amendment 3). This module is
the machine form that ``nts-conform`` uses:

* :data:`LEVELS` -- the three levels, low to high (cumulative, CNF-2).
* :func:`level_rules` -- the rule ids of each level, from the rule families of
  9.6 and the rule ids of Appendix C.1 (``rule-map.json``).
* :func:`kit_scope` -- the kit entries that a consumer claim must pass.
* :func:`consumer_level` -- the level of a consumer from its kit results (CNF-6).
* :func:`producer_level` -- the level of a producer from its check results (CNF-5).

The stream levels of 9.2 (``core``, ``trust-ready``, ``provenance``) judge one
stream; the implementation levels judge a program. ``spec/conformance/levels.json``
is a generated copy (``nts-conform levels --write``); a test keeps it current.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

LEVELS_SCHEMA = "fidetype.conformance.levels/1"
LEVELS = ("core", "full", "trust-ready")
LEVEL_TITLES = {"core": "NTS Core", "full": "NTS Full", "trust-ready": "NTS Trust-ready"}
#: Output profiles that a claim can name, and the suite profile that judges each one.
PROFILES = {"text": "fep-0001", "intent": "fep-0003", "control": "fep-0005"}
#: Bindings that a claim can add (CNF-7), and the suite profile of each one.
BINDINGS = {"nts-lsl/0.1": "fep-0002", "nts-ws/0.1": "fep-0004"}
#: The stream levels of 9.2, low to high.
STREAM_LEVELS = ("core", "trust-ready", "provenance")

# Rule families (the id prefix before the number) of each level (spec 9.6 table).
CORE_FAMILIES = ("GEN", "HDR", "MET", "FRM", "SEG", "SQ", "DEC", "PTR", "TIM", "VER", "FIL", "EXT", "SEC", "CNF")
PROFILE_FAMILIES = {
    "text": ("HYP", "EVD", "DCL", "TD", "TD-F"),
    "intent": ("PRF", "INT-D", "INT-E", "INT-F", "INT-T"),
    "control": ("CTL", "CTL-D", "CTL-E", "CTL-T"),
}
TRUST_FAMILIES = ("INT-S", "CTL-S", "PRV")
#: Rule ids that only Trust-ready requires (the definitions of the stream levels trust-ready and provenance).
TRUST_RULES = ("CNF-3", "CNF-4")
#: SHOULD rules of Core families that NTS Trust-ready makes required (the rules behind the TR-* and PV-* checks).
TRUST_PROMOTED = ("MET-5", "MET-6", "DEC-5", "SEC-2", "SEC-4")
#: Binding rule ids by their first part (LSL-F1, LSL-C3, WS-Q1, ...).
BINDING_FAMILIES = {"nts-lsl/0.1": ("LSL",), "nts-ws/0.1": ("WS",)}
#: Rule ids that belong to no level (process rules for spec authors).
PROCESS_RULES = ("FEP-1",)

def family(rule_id: str) -> str:
    """``"INT-S4"`` -> ``"INT-S"``; ``"TD-F2"`` -> ``"TD-F"``; ``"HDR-13"`` -> ``"HDR"``."""
    head, _, tail = rule_id.partition("-")
    letters = "".join(c for c in tail if c.isalpha())
    return f"{head}-{letters}" if letters else head


def level_rules(rule_ids: Iterable[str] | None = None) -> dict[str, Any]:
    """The rule ids of each level and binding (from Appendix C.1 unless ``rule_ids`` is given)."""
    if rule_ids is None:
        from fidetype.conformance.rules import load_rule_map

        rule_ids = load_rule_map()["rules"].keys()
    ids = sorted(set(rule_ids), key=_rule_sort)
    core = [r for r in ids if family(r) in CORE_FAMILIES and r not in TRUST_RULES]
    prof = {p: [r for r in ids if family(r) in fams] for p, fams in PROFILE_FAMILIES.items()}
    trust = [r for r in ids if family(r) in TRUST_FAMILIES or r in TRUST_RULES]
    bind = {b: [r for r in ids if r.split("-")[0] in fams] for b, fams in BINDING_FAMILIES.items()}
    placed = set(core) | set(trust) | {r for v in prof.values() for r in v} | {r for v in bind.values() for r in v}
    rest = [r for r in ids if r not in placed and r not in PROCESS_RULES]
    return {"core": core, "full": prof, "trust-ready": {"adds": trust, "promoted": list(TRUST_PROMOTED)},
            "bindings": bind, "process": [r for r in ids if r in PROCESS_RULES], "unplaced": rest}


def _rule_sort(r: str) -> tuple[str, int]:
    m = re.search(r"(\d+)$", r)
    return (r[: m.start()] if m else r, int(m.group(1)) if m else 0)


def kit_scope(entries: Sequence[dict[str, Any]], level: str, profiles: Sequence[str] = tuple(PROFILES),
              bindings: Sequence[str] = ()) -> list[dict[str, Any]]:
    """The kit entries that a consumer claim of ``level`` must pass (CNF-6, CNF-7)."""
    suites = ["v0.1"]
    if level in ("full", "trust-ready"):
        suites += [PROFILES[p] for p in profiles]
    suites += [BINDINGS[b] for b in bindings]
    return [e for e in entries if e["profile"] in suites]


def _rank(stream_level: str | None) -> int:
    return STREAM_LEVELS.index(stream_level) if stream_level in STREAM_LEVELS else -1


def consumer_level(rows: Sequence[dict[str, Any]], profiles: Sequence[str] = tuple(PROFILES),
                   bindings: Sequence[str] = (), levels_known: bool = True) -> dict[str, Any]:
    """The consumer level from kit rows (``nts-conform kit``).

    Each row has ``profile``, ``wire_form``, ``expect``, ``verdict_ok`` (the verdict matched) and, for an input
    stream, ``stream_level`` (expected) and ``level_actual`` (what the implementation reported, or None).
    ``levels_known`` is False when the implementation cannot report stream levels (then NTS Full is the top).
    """
    def ok(rs: Iterable[dict[str, Any]]) -> bool:
        rs = list(rs)
        return bool(rs) and all(r["verdict_ok"] for r in rs)

    by = {lv: kit_scope(rows, lv, profiles) for lv in LEVELS}
    reached: dict[str, bool] = {}
    reached["core"] = ok(by["core"])
    reached["full"] = reached["core"] and ok(by["full"]) and all(
        any(r["profile"] == PROFILES[p] for r in rows) for p in profiles)
    lvl_rows = [r for r in by["trust-ready"] if r.get("stream_level")]
    lvl_ok = levels_known and bool(lvl_rows) and all(r.get("level_actual") == r["stream_level"] for r in lvl_rows)
    reached["trust-ready"] = reached["full"] and lvl_ok
    top = next((lv for lv in reversed(LEVELS) if reached[lv]), None)
    bind = {b: ok(r for r in rows if r["profile"] == BINDINGS[b]) for b in BINDINGS
            if any(r["profile"] == BINDINGS[b] for r in rows)}
    missing = [b for b in bindings if not bind.get(b)]
    why: list[str] = []
    for lv in LEVELS:
        if reached[lv]:
            continue
        bad = [r["id"] for r in by[lv] if not r["verdict_ok"]]
        if bad:
            why.append(f"{LEVEL_TITLES[lv]}: wrong verdict on {', '.join(bad)}")
        if lv == "trust-ready" and not levels_known:
            why.append("NTS Trust-ready: the implementation does not report stream levels (use {level} in --cmd, a "
                       "level parameter in --impl, or levels in --verdicts)")
        elif lv == "trust-ready":
            wrong = [f"{r['id']} ({r.get('level_actual')} for {r['stream_level']})" for r in lvl_rows
                     if r.get("level_actual") != r["stream_level"]]
            if wrong:
                why.append(f"NTS Trust-ready: wrong stream level on {', '.join(wrong)}")
        break
    return {"class": "consumer", "level": top, "title": LEVEL_TITLES.get(top, "none") if top else "none",
            "levels": reached, "profiles": list(profiles), "bindings": bind, "bindings_missing": missing,
            "why_not_higher": why}


def coverage(form: str, objs: Sequence[Any]) -> set[str]:
    """The output profiles that one producer target covers (CNF-5, NTS Full)."""
    dicts = [o for o in objs if isinstance(o, dict)]
    types = {o.get("type") for o in dicts}
    out: set[str] = set()
    if form == "jsonl-decision-log":
        kinds = {o.get("profile", "text") for o in dicts if o.get("type") == "trust_decision"}
        out |= {k for k in kinds if k in PROFILES}
        return out
    if form != "jsonl-stream":
        return out
    hdr = next((o for o in dicts if o.get("type") == "header"), {})
    if types & {"hypothesis", "segment_end"}:
        out.add("text")
    if "intent_declaration" in hdr or types & {"intent", "intent_feedback"}:
        out.add("intent")
    if "control_declaration" in hdr or types & {"control", "control_enable"}:
        out.add("control")
    return out


def producer_level(targets: Sequence[dict[str, Any]], claim: Sequence[str] | None = None) -> dict[str, Any]:
    """The producer level from per-target results (``nts-conform check``).

    Each target has ``form``, ``ok_core`` (no failed check at stream level core), ``stream_level``
    (highest stream level reached, or None) and ``covers`` (output profiles, :func:`coverage`).
    ``claim``: the output profiles that the claim names; None = the profiles that the evidence covers.
    """
    covered = sorted({p for t in targets for p in t["covers"]}, key=list(PROFILES).index)
    profiles = list(claim) if claim else covered
    streams = [t for t in targets if t["form"] in ("jsonl-stream", "npz")]
    reached: dict[str, bool] = {}
    reached["core"] = bool(streams) and all(t["ok_core"] for t in targets)
    reached["full"] = reached["core"] and bool(profiles) and all(p in covered for p in profiles)
    reached["trust-ready"] = reached["full"] and all(t["stream_level"] == "provenance" for t in streams)
    top = next((lv for lv in reversed(LEVELS) if reached[lv]), None)
    why: list[str] = []
    if not reached["core"]:
        if not streams:
            why.append("NTS Core: the evidence has no input stream (JSON Lines stream or NPZ file)")
        bad = [t["target"] for t in targets if not t["ok_core"]]
        if bad:
            why.append(f"NTS Core: failed checks in {', '.join(bad)}")
    elif not reached["full"]:
        miss = [p for p in profiles if p not in covered] if profiles else list(PROFILES)
        why.append(f"NTS Full: no file uses the events of the profile(s) {', '.join(miss)} (text: hypothesis or "
                   "segment_end, or a text decision log; intent: intent_declaration or an intent decision log; "
                   "control: control_declaration or a control decision log)")
    elif not reached["trust-ready"]:
        low = [f"{t['target']} ({t['stream_level']})" for t in streams if t["stream_level"] != "provenance"]
        why.append(f"NTS Trust-ready: input streams below stream level provenance: {', '.join(low)}")
    bindings = sorted({b for t in targets for b, s in BINDINGS.items()
                       if t["form"] in (("lsl-capture", "lsl-decisions-capture") if s == "fep-0002"
                                        else ("ws-capture", "ws-decisions-capture")) and t["ok_core"]})
    return {"class": "producer", "level": top, "title": LEVEL_TITLES[top] if top else "none", "levels": reached,
            "profiles": profiles, "covered": covered, "bindings": bindings, "why_not_higher": why}


def render_levels() -> str:
    """The text of ``spec/conformance/levels.json``."""
    from fidetype.conformance.kit import KIT_VERSION, load_index
    from fidetype.conformance.rules import SPEC_LABEL

    es = load_index()["entries"]
    rules = level_rules()

    def ids(scope: Iterable[dict[str, Any]]) -> list[str]:
        return [e["id"] for e in scope]

    doc = {
        "schema": LEVELS_SCHEMA, "spec": SPEC_LABEL, "section": "9.6 (amendment 3)", "kit_version": KIT_VERSION,
        "generator": "nts-conform levels --write",
        "note": "Informative copy of spec 9.6. The levels are cumulative (CNF-2). Advisory checks never block a level.",
        "stream_levels": {"core": "every MUST rule that a validator can check on the stream",
                          "trust-ready": "core + the trust-ready checks (CNF-3)",
                          "provenance": "trust-ready + the provenance checks (CNF-4)"},
        "levels": {
            "core": {"title": "NTS Core", "rules": rules["core"],
                     "kit": ids(kit_scope(es, "core")),
                     "producer": "every evidence file passes nts-conform check --level core; at least one input "
                                 "stream (JSON Lines or NPZ)",
                     "consumer": "the expected verdict on every Core kit entry"},
            "full": {"title": "NTS Full", "rules_by_profile": rules["full"],
                     "kit_by_profile": {p: ids(e for e in es if e["profile"] == s) for p, s in PROFILES.items()},
                     "producer": "Core, and for each named output profile at least one file that uses its events "
                                 "(text: hypothesis or segment_end, or a text decision log; intent: intent_declaration "
                                 "or an intent decision log; control: control_declaration or a control decision log)",
                     "consumer": "Core + the expected verdict on every kit entry of each named profile (no profile "
                                 "named = all three)"},
            "trust-ready": {"title": "NTS Trust-ready", "adds": rules["trust-ready"]["adds"],
                            "promoted_should_rules": rules["trust-ready"]["promoted"],
                            "kit_stream_levels": {e["id"]: e["stream_level"] for e in es if e.get("stream_level")},
                            "producer": "Full, and every input stream reaches stream level provenance "
                                        "(nts-conform check --level provenance)",
                            "consumer": "Full + the expected stream_level of every input-stream kit entry in scope"},
        },
        "bindings": {b: {"rules": rules["bindings"][b], "kit": ids(e for e in es if e["profile"] == s)}
                     for b, s in BINDINGS.items()},
        "process_rules": rules["process"],
    }
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def levels_path():  # noqa: ANN201 - Path
    """``spec/conformance/levels.json`` (the repository copy, else the copy in the installed wheel)."""
    from fidetype.conformance.kit import kit_dir

    return kit_dir().parent / "levels.json"


__all__ = ["BINDINGS", "LEVELS", "LEVEL_TITLES", "PROFILES", "STREAM_LEVELS", "consumer_level", "coverage", "family",
           "kit_scope", "level_rules", "producer_level", "render_levels"]
