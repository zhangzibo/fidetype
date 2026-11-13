"""Opt-in conformance profiles for Fidetype Enhancement Proposals (FEPs).

The base suite (``fidetype.conformance``) tests NeuralTextStream v0.1. A
**profile** tests one FEP on top of it. A profile is opt-in: the base
suite, its levels and its 52 golden vectors do not change.

=============  =============================================  ==============================
Profile        FEP                                            Golden vectors
=============  =============================================  ==============================
``fep-0001``   Streaming trust events (``segment_end``,       ``spec/conformance/fep-0001/``
               evidence fields, decode declaration,
               ``trust_decision``)
``fep-0002``   NeuralTextStream over LSL (stream infos,       ``spec/conformance/fep-0002/``
               desc keys, markers, clock, decisions outlet)
=============  =============================================  ==============================

Each profile has: ``build_vectors()`` (the golden vectors), a reference
consumer ``consume(path) -> dict`` (returns a summary to accept, raises
to reject) and ``check_file(path) -> TargetReport`` (producer checks).

Command line::

    fidetype conformance --profile fep-0001                      # reference consumer over the vectors
    fidetype conformance consumer --profile fep-0001 --impl my_mod:read
    fidetype conformance check --profile fep-0001 decisions.jsonl
    fidetype conformance vectors --profile fep-0002 --out DIR
    fidetype conformance list --profile fep-0001
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Callable

from fidetype.conformance.vectors import MANIFEST_SCHEMA, Vector

#: Profile name -> (module, FEP number, title).
_PROFILES = {
    "fep-0001": ("fidetype.conformance.profiles.fep0001", "FEP-0001", "Streaming trust events"),
    "fep-0002": ("fidetype.conformance.profiles.fep0002", "FEP-0002", "NeuralTextStream over LSL"),
}
PROFILE_NAMES = tuple(_PROFILES)
REPORT_SCHEMA = "fidetype.conformance.profile-report/1"


@dataclass(frozen=True)
class Profile:
    name: str
    fep: str
    title: str
    module: Any

    @property
    def build_vectors(self) -> Callable[[], list[Vector]]:
        return self.module.build_vectors

    @property
    def consume(self) -> Callable[[Path], dict[str, Any]]:
        return self.module.consume

    @property
    def check_file(self) -> Callable[[Path], Any]:
        return self.module.check_file

    @property
    def checks(self) -> list[dict[str, str]]:
        """The checks of the profile: id, keyword, FEP clause, title."""
        return [dict(id=c[0], keyword=c[1], clause=c[2], title=c[3]) for c in self.module.CHECKS]

    @property
    def stream_suffixes(self) -> tuple[str, ...]:
        return self.module.SUFFIXES

    def vectors_dir(self) -> Path:
        """``spec/conformance/<name>`` of the repository."""
        return Path(__file__).resolve().parents[4] / "spec" / "conformance" / self.name

    def write_vectors(self, out_dir: str | PathLike[str]) -> dict[str, Any]:
        """Write the vectors and ``manifest.json`` to ``out_dir``. Returns the manifest."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        vectors = self.build_vectors()
        for v in vectors:
            assert v.writer is not None
            v.writer(out / v.file)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "spec_version": "0.1",
            "profile": self.name,
            "fep": self.fep,
            "generator": f"python -m fidetype.conformance vectors --profile {self.name}",
            "how_to_use": self.module.HOW_TO_USE,
            "vectors": [v.to_manifest() for v in vectors],
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                                           encoding="utf-8", newline="\n")
        return manifest


def get_profile(name: str) -> Profile:
    if name not in _PROFILES:
        raise ValueError(f"unknown profile {name!r}; known: {list(_PROFILES)}")
    mod, fep, title = _PROFILES[name]
    return Profile(name, fep, title, importlib.import_module(mod))


def profile_report(profile: Profile, reports: list[Any]) -> dict[str, Any]:
    """The JSON report of ``check --profile``: a target passes if no blocking check fails."""
    targets = []
    for r in reports:
        d = r.to_dict()
        d["ok"] = not r.failures("core")
        targets.append(d)
    return {"schema": REPORT_SCHEMA, "profile": profile.name, "fep": profile.fep,
            "ok": all(t["ok"] for t in targets) and bool(targets), "targets": targets}


def profile_summary(report: dict[str, Any], verbose: bool = False) -> str:
    lines = []
    for t in report["targets"]:
        lines.append(f"{t['target']}: {'PASS' if t['ok'] else 'FAIL'}")
        for c in t["checks"]:
            if c["outcome"] in ("fail", "warn") or (verbose and c["outcome"] != "skip"):
                lines.append(f"  {c['outcome'].upper():4} {c['id']:<22} [{c['keyword']} {c['clause']}] {c['message']}")
    n_ok = sum(t["ok"] for t in report["targets"])
    lines.append(f"[{report['fep']} profile {report['profile']}: {'PASS' if report['ok'] else 'FAIL'}] "
                 f"{n_ok}/{len(report['targets'])} targets")
    return "\n".join(lines)


__all__ = ["PROFILE_NAMES", "Profile", "get_profile", "profile_report", "profile_summary"]
