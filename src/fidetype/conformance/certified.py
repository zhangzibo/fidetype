"""The self-certification list (roadmap P7-02, spec 9.7).

``spec/conformance/certified.json`` lists implementations that claim an NTS
implementation level (spec 9.6) and link the evidence: the JSON report of
``nts-conform kit`` (consumers) or ``nts-conform check`` (producers), made with
the kit version that the entry names. ``nts-conform certified --check`` checks
every entry against its evidence file. A pull request adds an entry and its
evidence (``docs/conformance.md``, "Self-certification").

The list is self-certification: the project checks the evidence file, not the
implementation. It is not a trademark licence (roadmap P7-03).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fidetype.conformance.levels import BINDINGS, LEVEL_TITLES, LEVELS, PROFILES

CERTIFIED_SCHEMA = "fidetype.conformance.certified/1"
CLASSES = ("producer", "consumer")
REQUIRED = ("id", "implementation", "language", "class", "level", "level_title", "profiles", "bindings", "spec",
            "kit_version", "version", "evidence", "evidence_command", "maintainer", "repository", "licence", "date")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def certified_path() -> Path:
    from fidetype.conformance.kit import kit_dir

    return kit_dir().parent / "certified.json"


def load_certified(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or certified_path()).read_text(encoding="utf-8"))


def check_entry(e: dict[str, Any], root: Path) -> list[str]:
    """Problems of one list entry (empty: the entry matches its evidence)."""
    from fidetype.conformance.nts_conform import KIT_REPORT_SCHEMA, REPORT_SCHEMA

    eid = e.get("id", "?")
    out = [f"{eid}: missing field {k!r}" for k in REQUIRED if k not in e]
    if out:
        return out
    if not _ID.match(e["id"]):
        out.append(f"{eid}: id must be lower-case letters, digits and '-'")
    if e["class"] not in CLASSES:
        out.append(f"{eid}: class must be one of {list(CLASSES)}")
    if e["level"] not in LEVELS or e["level_title"] != LEVEL_TITLES.get(e["level"]):
        out.append(f"{eid}: level must be one of {list(LEVELS)} with its title")
    if not set(e["profiles"]) <= set(PROFILES) or not set(e["bindings"]) <= set(BINDINGS):
        out.append(f"{eid}: unknown profile or binding")
    if not _DATE.match(str(e["date"])):
        out.append(f"{eid}: date must be YYYY-MM-DD")
    if "(draft)" not in e["spec"]:
        out.append(f"{eid}: spec must name the draft RC, for example 'NTS 1.0 RC4 (draft)' (CNF-1)")
    ev = root / e["evidence"]
    if not ev.is_file():
        return out + [f"{eid}: evidence file {e['evidence']} not found"]
    rep = json.loads(ev.read_text(encoding="utf-8"))
    want = KIT_REPORT_SCHEMA if e["class"] == "consumer" else REPORT_SCHEMA
    if rep.get("schema") != want:
        return out + [f"{eid}: evidence schema {rep.get('schema')!r}, expected {want!r} for a {e['class']}"]
    if rep.get("kit_version") != e["kit_version"]:
        out.append(f"{eid}: evidence kit_version {rep.get('kit_version')!r} != {e['kit_version']!r}")
    if rep.get("spec") != e["spec"]:
        out.append(f"{eid}: evidence spec {rep.get('spec')!r} != {e['spec']!r}")
    lv = rep.get("level") if e["class"] == "consumer" else rep.get("producer")
    if not isinstance(lv, dict) or not lv.get("levels", {}).get(e["level"]):
        out.append(f"{eid}: the evidence does not reach {e['level_title']}")
        return out
    if e["class"] == "consumer":
        if lv.get("note"):
            out.append(f"{eid}: the evidence is a partial kit run ({lv['note']})")
        if set(e["profiles"]) - set(lv.get("profiles", [])):
            out.append(f"{eid}: profiles {e['profiles']} are not all in the evidence claim {lv.get('profiles')}")
        miss = [b for b in e["bindings"] if not lv.get("bindings", {}).get(b)]
    else:
        if set(e["profiles"]) - set(lv.get("covered", [])):
            out.append(f"{eid}: profiles {e['profiles']} are not all covered by the evidence {lv.get('covered')}")
        miss = [b for b in e["bindings"] if b not in lv.get("bindings", [])]
    if miss:
        out.append(f"{eid}: bindings {miss} are not passed in the evidence")
    return out


def check_certified(path: str | Path | None = None) -> list[str]:
    """Problems of the whole list (empty: every entry matches its evidence)."""
    p = Path(path or certified_path())
    doc = load_certified(p)
    out = []
    if doc.get("schema") != CERTIFIED_SCHEMA:
        out.append(f"schema must be {CERTIFIED_SCHEMA!r}")
    ids = [e.get("id") for e in doc.get("entries", [])]
    if len(ids) != len(set(ids)):
        out.append("entry ids must be unique")
    for e in doc.get("entries", []):
        out += check_entry(e, p.parent)
    return out


__all__ = ["CERTIFIED_SCHEMA", "check_certified", "check_entry", "certified_path", "load_certified"]
