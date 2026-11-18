"""Benchmark hub: versioned dataset registry (roadmap P13-01, design only).

Design: ``docs/hub-design.md``. The registry file ``datasets-0.1.json``
next to this module holds **metadata only**: id, version, licence and the
research-only flag, citation, checksums, verify and download steps,
adapters and tracks. The hub never hosts participant data.

This module only loads and checks the registry (standard library only).
The hub command line (``fidetype hub ...``) is a later item (P13-06).

::

    python -m fidetype.benchmark.hub          # check the registry; exit code 1 on a problem
"""

from __future__ import annotations

import json
import re
import sys
from importlib import resources
from typing import Any, Mapping, Sequence

REGISTRY_SCHEMA = "fidetype.hub.registry/0.1"
DATASET_SCHEMA = "fidetype.hub.dataset/0.1"
REGISTRY_FILE = "datasets-0.1.json"

STATUSES = ("candidate", "registered", "deprecated", "withdrawn")
TRANSPORTS = ("file", "lsl", "ws")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SPLIT_VERSION = re.compile(r"^tracks-v\d+\.\d+$")

_REQUIRED = ("schema", "id", "version", "revision", "status", "title", "modality", "language", "citation", "url",
             "licence", "personal_data", "forms", "download", "verify", "adapters", "tracks", "steward")


def load_registry() -> dict[str, Any]:
    """Return the committed registry (``datasets-0.1.json``)."""
    text = resources.files(__package__).joinpath(REGISTRY_FILE).read_text(encoding="utf-8")
    return json.loads(text)


def _check_licence(p: str, lic: Any) -> list[str]:
    if not isinstance(lic, Mapping):
        return [f"{p}.licence: must be an object"]
    errs = []
    spdx = lic.get("spdx")
    if not isinstance(spdx, str) or not spdx:
        errs.append(f"{p}.licence.spdx: required")
        spdx = ""
    for k in ("research_only", "share_alike"):
        if not isinstance(lic.get(k), bool):
            errs.append(f"{p}.licence.{k}: must be true or false")
    # A non-commercial licence always makes the dataset research-only (project licence rule, FEP-0010).
    if "-NC" in spdx.upper() and lic.get("research_only") is not True:
        errs.append(f"{p}.licence: {spdx} is non-commercial, so research_only must be true")
    if "-SA" in spdx.upper() and lic.get("share_alike") is not True:
        errs.append(f"{p}.licence: {spdx} is share-alike, so share_alike must be true")
    if not lic.get("attribution"):
        errs.append(f"{p}.licence.attribution: required (cite the source even under CC0)")
    return errs


def _check_forms(p: str, forms: Any) -> tuple[list[str], set[str]]:
    errs: list[str] = []
    names: set[str] = set()
    if not isinstance(forms, list) or not forms:
        return [f"{p}.forms: at least one form"], names
    for i, f in enumerate(forms):
        q = f"{p}.forms[{i}]"
        name = f.get("form") if isinstance(f, Mapping) else None
        if not isinstance(name, str) or not name:
            errs.append(f"{q}.form: required")
            continue
        if name in names:
            errs.append(f"{q}.form: duplicate {name!r}")
        names.add(name)
        for j, fl in enumerate(f.get("files", [])):
            r = f"{q}.files[{j}]"
            if not isinstance(fl, Mapping) or not fl.get("name"):
                errs.append(f"{r}.name: required")
                continue
            sha = fl.get("sha256")
            if sha is None:
                if not fl.get("note"):
                    errs.append(f"{r}: no sha256, so a note must say how to verify the copy")
            elif not (isinstance(sha, str) and _SHA256.match(sha)):
                errs.append(f"{r}.sha256: must be 64 lower-case hex digits or null")
    return errs, names


def check_dataset(d: Mapping[str, Any], index: int = 0) -> list[str]:
    """Return the problems of one dataset entry (an empty list = valid)."""
    p = f"datasets[{index}]"
    if not isinstance(d, Mapping):
        return [f"{p}: must be an object"]
    p = f"datasets[{index}] ({d.get('id', '?')})"
    errs = [f"{p}.{k}: required" for k in _REQUIRED if k not in d]
    if d.get("schema") != DATASET_SCHEMA:
        errs.append(f"{p}.schema: must be {DATASET_SCHEMA!r}")
    if not (isinstance(d.get("id"), str) and _ID.match(d["id"])):
        errs.append(f"{p}.id: kebab-case required")
    if not (isinstance(d.get("version"), str) and d["version"]):
        errs.append(f"{p}.version: the upstream version is required")
    if not (isinstance(d.get("revision"), int) and d["revision"] >= 1):
        errs.append(f"{p}.revision: integer >= 1")
    if d.get("status") not in STATUSES:
        errs.append(f"{p}.status: one of {', '.join(STATUSES)}")
    cit = d.get("citation")
    if not (isinstance(cit, Mapping) and cit.get("text")):
        errs.append(f"{p}.citation.text: required")
    errs += _check_licence(p, d.get("licence"))
    pd = d.get("personal_data")
    # The hub never re-hosts participant data (P13-01 design rule 1).
    if not (isinstance(pd, Mapping) and pd.get("rehost") is False):
        errs.append(f"{p}.personal_data.rehost: must be false (the hub never re-hosts data)")
    ferrs, forms = _check_forms(p, d.get("forms"))
    errs += ferrs
    dl = d.get("download")
    if not (isinstance(dl, Mapping) and dl.get("instructions")):
        errs.append(f"{p}.download.instructions: required (download from the original source)")
    vf = d.get("verify")
    if not (isinstance(vf, Mapping) and (vf.get("files") or vf.get("units"))):
        errs.append(f"{p}.verify: a file checksum command or a unit verify command is required")
    for i, s in enumerate(d.get("same_units") or []):
        bad = [f for f in s.get("forms", []) if f not in forms]
        if len(s.get("forms", [])) < 2 or bad:
            errs.append(f"{p}.same_units[{i}].forms: two or more known forms (unknown: {bad})")
    ads = d.get("adapters")
    if d.get("status") == "registered" and not ads:
        errs.append(f"{p}.adapters: a registered dataset needs at least one replay adapter")
    for i, a in enumerate(ads or []):
        q = f"{p}.adapters[{i}]"
        if a.get("form") not in forms:
            errs.append(f"{q}.form: unknown form {a.get('form')!r}")
        if not str(a.get("module", "")).startswith("fidetype."):
            errs.append(f"{q}.module: must be a fidetype module (our own Apache-2.0 code)")
        tr = a.get("transports") or []
        if "file" not in tr or any(t not in TRANSPORTS for t in tr):
            errs.append(f"{q}.transports: must hold 'file' and only {', '.join(TRANSPORTS)}")
    for i, t in enumerate(d.get("tracks") or []):
        if not (isinstance(t, Mapping) and t.get("track") and _SPLIT_VERSION.match(str(t.get("split_version", "")))):
            errs.append(f"{p}.tracks[{i}]: needs track and split_version (tracks-vX.Y)")
    return errs


def check_registry(reg: Mapping[str, Any]) -> list[str]:
    """Return the problems of a whole registry (an empty list = valid)."""
    errs = []
    if reg.get("schema") != REGISTRY_SCHEMA:
        errs.append(f"schema: must be {REGISTRY_SCHEMA!r}")
    ds = reg.get("datasets")
    if not isinstance(ds, list):
        return errs + ["datasets: must be a list"]
    seen: set[tuple[str, str]] = set()
    for i, d in enumerate(ds):
        errs += check_dataset(d, i)
        key = (str(d.get("id")), str(d.get("version"))) if isinstance(d, Mapping) else ("?", "?")
        if key in seen:
            errs.append(f"datasets[{i}]: duplicate id + version {key}")
        seen.add(key)
    return errs


def get_dataset(dataset_id: str, version: str | None = None) -> dict[str, Any]:
    """Return one registered entry (the newest listed one when ``version`` is None)."""
    hits = [d for d in load_registry()["datasets"] if d["id"] == dataset_id
            and (version is None or d["version"] == version)]
    if not hits:
        raise KeyError(f"no dataset {dataset_id!r}" + (f" version {version!r}" if version else ""))
    return hits[-1]


def main(argv: Sequence[str] | None = None) -> int:
    errs = check_registry(load_registry())
    for e in errs:
        print(e, file=sys.stderr)
    if not errs:
        print(f"{REGISTRY_FILE}: OK")
    return 1 if errs else 0
