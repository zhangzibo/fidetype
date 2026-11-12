"""Conformance reports: machine-readable JSON, a short summary and a badge line."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from fidetype.conformance.checks import LEVELS, CheckResult
from fidetype.streams.spec import SPEC_VERSION

SUITE_VERSION = "0.1.0"
REPORT_SCHEMA = "fidetype.conformance.report/1"


def levels_passed(results: Iterable[CheckResult]) -> list[str]:
    """The levels whose blocking checks all pass (levels are cumulative)."""
    results = list(results)
    passed = []
    for lv in LEVELS:
        if any(r.status == "fail" and r.blocks(lv) for r in results):
            break
        passed.append(lv)
    return passed


@dataclass
class TargetReport:
    """The result for one target (a file, or one stream of an adapter)."""

    target: str
    kind: str  # "file" or "adapter"
    results: list[CheckResult]
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def levels(self) -> list[str]:
        return levels_passed(self.results)

    @property
    def level(self) -> str:
        lv = self.levels
        return lv[-1] if lv else "none"

    def counts(self) -> dict[str, int]:
        c = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
        for r in self.results:
            c[r.outcome] += 1
        return c

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target, "kind": self.kind, "level": self.level, "levels_passed": self.levels,
            "counts": self.counts(), "info": self.info, "checks": [r.to_dict() for r in self.results],
        }


def combine(reports: list[TargetReport]) -> str:
    """The level that all targets reach (the weakest one)."""
    if not reports:
        return "none"
    order = ["none", *LEVELS]
    return min((r.level for r in reports), key=order.index)


def build_report(reports: list[TargetReport], requested_level: str | None = None) -> dict[str, Any]:
    level = combine(reports)
    order = ["none", *LEVELS]
    ok = requested_level is None or order.index(level) >= order.index(requested_level)
    return {
        "schema": REPORT_SCHEMA,
        "suite_version": SUITE_VERSION,
        "spec_version": SPEC_VERSION,
        "level": level,
        "requested_level": requested_level,
        "ok": ok,
        "badge": shields_badge(level),
        "targets": [r.to_dict() for r in reports],
    }


def shields_badge(level: str) -> dict[str, Any]:
    """A shields.io "endpoint" badge object (schemaVersion 1)."""
    color = {"none": "red", "core": "yellow", "trust-ready": "green", "provenance": "brightgreen"}[level]
    return {"schemaVersion": 1, "label": f"NTS v{SPEC_VERSION}", "message": level, "color": color}


def badge_line(level: str, counts: dict[str, int]) -> str:
    marks = " ".join(f"{lv}:{'PASS' if (['none', *LEVELS].index(level) >= i + 1) else 'FAIL'}" for i, lv in enumerate(LEVELS))
    return (f"[NeuralTextStream v{SPEC_VERSION} conformance: {level.upper()}] {marks} "
            f"({counts['pass']} pass, {counts['fail']} fail, {counts['warn']} warn, {counts['skip']} skip)")


def summary_text(report: dict[str, Any], verbose: bool = False) -> str:
    """A short human-readable summary of a report dict."""
    lines = []
    total = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for t in report["targets"]:
        for k, v in t["counts"].items():
            total[k] += v
        lines.append(f"{t['target']}: level {t['level']} ({', '.join(t['levels_passed']) or 'none'})")
        for c in t["checks"]:
            if c["outcome"] in ("fail", "warn") or (verbose and c["outcome"] != "skip"):
                tag = c["outcome"].upper()
                lv = c["level"]
                lines.append(f"  {tag:4} {c['id']:<22} [{lv}, {c['keyword']} {c['clause']}] {c['message']}")
    if report.get("requested_level"):
        lines.append(f"requested level {report['requested_level']}: {'OK' if report['ok'] else 'NOT MET'}")
    lines.append(badge_line(report["level"], total))
    return "\n".join(lines)
