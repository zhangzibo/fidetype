"""``nts-conform``: the NTS conformance kit runner (roadmap P7-01).

Sub-commands::

    nts-conform check FILE [FILE ...] [--level L] [--profile P ...] [--json OUT] [--verbose]
        Producer check. FILE is a stream file (.jsonl, .npz), a decision log (.jsonl),
        an LSL or WebSocket capture (scenario .json), an LSL stream info (.xml), a
        directory of them, or "-" (JSON Lines or NPZ on stdin, for a live capture).
        The tool detects the wire form, runs every suite profile that applies and
        prints one line per rule: PASS / FAIL / WARN, the rule ids (spec Appendix C),
        the check id, the location (line, frame, step) and the message.
    nts-conform kit [--kit DIR] [--profile P] [--cmd "PROG {path} {profile}" | --impl MOD:FUNC
                    | --verdicts FILE] [--json OUT]
        Run the kit. Without an implementation it runs the reference: the consumer
        verdict and the producer check of every kit file must give the expected
        verdict. With --cmd, --impl or --verdicts it checks YOUR validator's verdicts
        on all kit files (exit 0 of --cmd = accept).
    nts-conform list [--kit DIR] [--markdown]     the kit entries
    nts-conform build --out DIR                   write the kit (maintainers)
    nts-conform rules [--write | --check]         the check -> rule map from spec Appendix C

Exit codes: 0 = conforming (every target passes; every kit verdict matches);
1 = not conforming; 2 = usage or input error (no such file, unknown form).

The same as ``python -m fidetype.conformance.nts_conform``. The TypeScript and
Rust SDKs run the kit with their own consumers::

    node sdk/typescript/bin/fidetype-ts.mjs conformance --vectors spec/conformance/kit
    fidetype-rs conformance --vectors spec/conformance/kit
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from fidetype.conformance.checks import ADVISORY, LEVELS, CheckResult

TOOL_VERSION = "0.1.0"
REPORT_SCHEMA = "fidetype.nts-conform.report/1"
KIT_REPORT_SCHEMA = "fidetype.nts-conform.kit-report/1"
FORMS = ("jsonl-stream", "jsonl-decision-log", "npz", "lsl-capture", "lsl-decisions-capture", "lsl-stream-info",
         "ws-capture", "ws-decisions-capture")
_LOC = re.compile(r"\b((?:line|frame|step|sample|chunk|message|decision sample) \d+(?: nbest\[\d+\])?"
                  r"|inlet \w+|decisions stream)")


class InputError(Exception):
    """A target that the tool cannot read (exit code 2)."""


# --- wire-form detection ---------------------------------------------------------------------


def _jsonl_objects(path: Path, limit: int = 100000) -> list[Any]:
    out: list[Any] = []
    with path.open("rb") as f:
        for n, raw in enumerate(f):
            if n >= limit:
                break
            try:
                out.append(json.loads(raw.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                out.append(None)
    return out


def detect(path: Path) -> tuple[str, list[str]]:
    """The wire form of a file and the suite profiles that judge it."""
    suf = path.suffix.lower()
    if suf == ".npz":
        return "npz", ["v0.1"]
    if suf == ".xml":
        return "lsl-stream-info", ["fep-0002"]
    if suf == ".json":
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise InputError(f"{path}: not JSON ({e})") from e
        schema = d.get("schema") if isinstance(d, dict) else None
        if schema == "fidetype.conformance.lsl-scenario/1":
            return ("lsl-decisions-capture" if d.get("kind") == "decisions" else "lsl-capture"), ["fep-0002"]
        if schema == "fidetype.conformance.ws-scenario/1":
            return ("ws-decisions-capture" if d.get("kind") == "subscribe" else "ws-capture"), ["fep-0004"]
        raise InputError(f"{path}: a .json target must be an LSL or WebSocket capture (lsl-scenario/1 or ws-scenario/1)")
    if suf not in (".jsonl", ".ndjson"):
        raise InputError(f"{path}: unknown wire form (use .jsonl, .ndjson, .npz, .json or .xml)")
    objs = [o for o in _jsonl_objects(path) if o is not None]
    dicts = [o for o in objs if isinstance(o, dict)]
    first = dicts[0] if dicts else {}
    types = {o.get("type") for o in dicts}
    if first.get("type") != "header" and "header" not in types and "trust_decision" in types:
        kinds = {o.get("profile", "text") for o in dicts if o.get("type") == "trust_decision"}
        profs = []
        if kinds & {"text"} or not kinds <= {"intent", "control"}:
            profs.append("fep-0001")
        if "intent" in kinds:
            profs.append("fep-0003")
        if "control" in kinds:
            profs.append("fep-0005")
        return "jsonl-decision-log", profs
    profs = ["v0.1", "fep-0001"]
    hdr = next((o for o in dicts if o.get("type") == "header"), {})
    if "intent_declaration" in hdr or types & {"intent", "intent_feedback"}:
        profs.append("fep-0003")
    if "control_declaration" in hdr or types & {"control", "control_enable"}:
        profs.append("fep-0005")
    return "jsonl-stream", profs


# --- per-rule results ------------------------------------------------------------------------


@dataclass
class RuleResult:
    outcome: str  # pass | fail | warn
    check: str
    profile: str
    rules: list[str]
    level: str
    keyword: str
    clause: str
    location: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "rules": self.rules, "check": self.check, "profile": self.profile,
                "level": self.level, "keyword": self.keyword, "clause": self.clause, "location": self.location,
                "message": self.message}


@dataclass
class TargetResult:
    target: str
    form: str
    profiles: list[str]
    level: str
    results: list[RuleResult] = field(default_factory=list)
    skipped: int = 0

    @property
    def fails(self) -> list[RuleResult]:
        return [r for r in self.results if r.outcome == "fail"]

    @property
    def warns(self) -> list[RuleResult]:
        return [r for r in self.results if r.outcome == "warn"]

    @property
    def verdict(self) -> str:
        if self.fails:
            return "fail"
        return "pass-with-warnings" if self.warns else "pass"

    def rule_outcomes(self) -> dict[str, str]:
        order = {"pass": 0, "warn": 1, "fail": 2}
        out: dict[str, str] = {}
        for r in self.results:
            for rid in r.rules:
                if order[r.outcome] >= order.get(out.get(rid, "pass"), 0):
                    out[rid] = r.outcome
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, Any]:
        counts = {k: sum(r.outcome == k for r in self.results) for k in ("pass", "fail", "warn")}
        counts["skip"] = self.skipped
        return {"target": self.target, "form": self.form, "profiles": self.profiles, "level": self.level,
                "verdict": self.verdict, "ok": not self.fails, "counts": counts, "rules": self.rule_outcomes(),
                "results": [r.to_dict() for r in self.results]}


def _outcome(c: CheckResult, level: str) -> str:
    if c.outcome == "warn" or (c.status == "fail" and c.level == ADVISORY):
        return "warn"
    if c.status == "fail":
        return "fail" if c.blocks(level) else "warn"
    return c.status


def _lsl_info_results(path: Path) -> list[CheckResult]:
    """The stream-info checks (FEP2-BINDING, -DESC, -FRAMES, -MARKERS, -DECISIONS) of every info in an LSL capture."""
    from dataclasses import replace

    from fidetype.adapters.lsl import LSLStreamInfo
    from fidetype.conformance.profiles.fep0002 import check_info

    d = json.loads(path.read_text(encoding="utf-8"))
    infos = [(f"inlet {k}", v.get("info_xml")) for k, v in (d.get("inlets") or {}).items() if isinstance(v, dict)]
    if d.get("kind") == "decisions":
        infos.append(("decisions stream", d.get("info_xml")))
    out: list[CheckResult] = []
    for where, xml in infos:
        if not isinstance(xml, str):
            continue
        try:
            info = LSLStreamInfo.from_xml(xml)
        except Exception:  # noqa: BLE001 - the scenario check reports an unreadable info
            continue
        out += [replace(c, message=f"{where}: {c.message}") if c.message else replace(c, message=where)
                for c in check_info(info)]
    return out


def _run_profile(profile: str, path: Path) -> list[CheckResult]:
    if profile == "v0.1":
        from fidetype.conformance import check_file

        return check_file(path).results
    from fidetype.conformance.profiles import get_profile

    res = get_profile(profile).check_file(path).results
    if profile == "fep-0002" and path.suffix.lower() == ".json":
        res = _lsl_info_results(path) + res
    return res


def conform_file(path: str | Path, level: str = "core", profiles: Sequence[str] | None = None) -> TargetResult:
    """Run the producer checks of every applicable profile on one file."""
    from fidetype.conformance.rules import rules_for

    p = Path(path)
    if not p.is_file():
        raise InputError(f"no such file: {p}")
    form, auto = detect(p)
    profs = list(profiles) if profiles else auto
    tr = TargetResult(str(path), form, profs, level)
    seen: set[tuple[str, str]] = set()
    for prof in profs:
        for c in _run_profile(prof, p):
            if c.check_id.endswith("-V01-CORE") and "v0.1" in profs:
                continue  # the base profile already reports these checks one by one
            out = _outcome(c, level)
            if out == "skip":
                tr.skipped += 1
                continue
            key = (out, c.message)
            if out != "pass" and key in seen:
                continue  # the same finding from a second profile (for example FEP3-INTENT and FEP5-INTENT)
            seen.add(key)
            m = _LOC.search(c.message or "")
            tr.results.append(RuleResult(out, c.check_id, prof, rules_for(c.check_id, c.message), c.level,
                                         c.keyword, c.clause, m.group(1) if m else "", c.message))
    return tr


def _expand(targets: Sequence[str]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in (".jsonl", ".ndjson", ".npz", ".json", ".xml")
                           and f.name not in ("manifest.json", "kit.json", "rule-map.json"))
            if not files:
                raise InputError(f"no stream files in {p}")
            out += files
        else:
            out.append(p)
    return out


def _stdin_file(tmp: Path) -> Path:
    data = sys.stdin.buffer.read()
    f = tmp / ("stdin.npz" if data[:2] == b"PK" else "stdin.jsonl")
    f.write_bytes(data)
    return f


def build_report(results: list[TargetResult], level: str) -> dict[str, Any]:
    from fidetype.conformance.rules import SPEC_LABEL

    return {"schema": REPORT_SCHEMA, "tool": "nts-conform", "tool_version": TOOL_VERSION, "spec": SPEC_LABEL,
            "level": level, "ok": bool(results) and all(not t.fails for t in results),
            "targets": [t.to_dict() for t in results]}


def report_text(results: list[TargetResult], verbose: bool = False) -> str:
    lines = []
    for t in results:
        lines.append(f"{t.target}  [{t.form}; profiles {', '.join(t.profiles)}; level {t.level}]")
        for r in t.results:
            if r.outcome == "pass" and not verbose:
                continue
            rules = ",".join(r.rules[:4]) + (f",+{len(r.rules) - 4}" if len(r.rules) > 4 else "") or f"({r.clause})"
            loc = r.location or "-"
            msg = r.message[len(loc) + 2:] if loc != "-" and r.message.startswith(loc + ":") else r.message
            lines.append(f"  {r.outcome.upper():4}  {rules:<22} {r.check:<20} {loc:<14} {msg}".rstrip())
        n_rules = t.rule_outcomes()
        lines.append(f"  => {t.verdict.upper()}: {len(t.fails)} failed and {len(t.warns)} warning checks of "
                     f"{len(t.results)} run ({t.skipped} not applicable); rules: {sum(v == 'pass' for v in n_rules.values())} "
                     f"no finding, {sum(v == 'fail' for v in n_rules.values())} named by a failed check, "
                     f"{sum(v == 'warn' for v in n_rules.values())} by a warning")
    ok = bool(results) and all(not t.fails for t in results)
    lines.append(f"[nts-conform: {'PASS' if ok else 'FAIL'}] {sum(not t.fails for t in results)}/{len(results)} targets pass")
    return "\n".join(lines)


def _write_json(obj: Any, out: str) -> None:
    text = json.dumps(obj, indent=1, ensure_ascii=False)
    if out == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(out).write_text(text + "\n", encoding="utf-8")


# --- the kit -----------------------------------------------------------------------------------


def _entries(kit: Path, profile: str | None) -> list[dict[str, Any]]:
    from fidetype.conformance.kit import load_index

    es = load_index(kit)["entries"]
    return [e for e in es if profile is None or e["profile"] == profile]


def _reference_consume(path: Path, profile: str) -> None:
    if profile == "v0.1":
        from fidetype.conformance.io import load_stream

        load_stream(path)
    else:
        from fidetype.conformance.profiles import get_profile

        get_profile(profile).consume(path)


def _cmd_validator(cmd: str, timeout: float = 60.0) -> Callable[[Path, str], str]:
    def run(path: Path, profile: str) -> str:
        args = [a.replace("{path}", str(path)).replace("{profile}", profile) for a in shlex.split(cmd, posix=True)]
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return "accept" if p.returncode == 0 else "reject"

    return run


def _impl_validator(spec: str) -> Callable[[Path, str], str]:
    mod, _, fn = spec.partition(":")
    if not fn:
        raise InputError("--impl must be MODULE:FUNCTION")
    f = getattr(importlib.import_module(mod), fn)
    two = len(inspect.signature(f).parameters) >= 2

    def run(path: Path, profile: str) -> str:
        try:
            f(path, profile) if two else f(path)
            return "accept"
        except Exception:  # noqa: BLE001 - any exception is a rejection
            return "reject"

    return run


def _verdicts_file(path: str) -> dict[str, str]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict) and isinstance(d.get("entries"), list):
        d = {e["id"]: e.get("actual", e.get("verdict")) for e in d["entries"]}
    if not isinstance(d, dict):
        raise InputError("--verdicts must be a JSON object {id: verdict} or {\"entries\": [{id, verdict}]}")
    return {k: ("reject" if str(v).startswith("reject") or v in ("fail", False) else "accept") for k, v in d.items()}


def run_kit(kit: str | Path | None = None, profile: str | None = None,
            validator: Callable[[Path, str], str] | None = None, verdicts: dict[str, str] | None = None,
            name: str = "reference") -> dict[str, Any]:
    """Check verdicts on every kit file. Without ``validator``/``verdicts``: the reference (consumer + producer)."""
    from fidetype.conformance.kit import kit_dir

    root = Path(kit) if kit is not None else kit_dir()
    rows = []
    for e in _entries(root, profile):
        path = root / e["path"]
        row: dict[str, Any] = {"id": e["id"], "path": e["path"], "profile": e["profile"], "wire_form": e["wire_form"],
                               "expect": e["expect"], "verdict": e["verdict"], "rules": e["rules"]}
        problems: list[str] = []
        if verdicts is not None:
            actual = verdicts.get(e["id"], "missing")
            row["actual"] = actual
            if actual != e["expect"]:
                problems.append(f"verdict {actual}, expected {e['expect']}")
        elif validator is not None:
            row["actual"] = actual = validator(path, e["profile"])
            if actual != e["expect"]:
                problems.append(f"verdict {actual}, expected {e['expect']}")
        else:
            try:
                _reference_consume(path, e["profile"])
                consumer = "accept"
            except Exception as x:  # noqa: BLE001
                consumer, row["consumer_detail"] = "reject", f"{type(x).__name__}: {x}"[:300]
            tr = conform_file(path, "core")
            producer = "reject" if tr.fails else "accept"
            row.update(actual=consumer, producer=producer, producer_verdict=tr.verdict,
                       failing_checks=sorted({r.check for r in tr.fails}), warning_checks=sorted({r.check for r in tr.warns}))
            if consumer != e["expect"]:
                problems.append(f"consumer {consumer}, expected {e['expect']}")
            if producer != e["expect"]:
                problems.append(f"producer check {tr.verdict}, expected {e['verdict']}")
            miss = [c for c in e.get("failing_checks", []) if c not in row["failing_checks"]]
            if miss:
                problems.append(f"checks {miss} did not fail")
            want_w = e.get("warning_checks", [])
            if e["verdict"] == "accept-with-warnings" and [c for c in want_w if c not in row["warning_checks"]]:
                problems.append(f"warnings {want_w} expected, got {row['warning_checks']}")
            if e["verdict"] == "accept" and row["warning_checks"]:
                problems.append(f"unexpected warnings {row['warning_checks']}")
        row["ok"] = not problems
        row["detail"] = "; ".join(problems)
        rows.append(row)
    n = sum(r["ok"] for r in rows)
    return {"schema": KIT_REPORT_SCHEMA, "tool": "nts-conform", "tool_version": TOOL_VERSION, "validator": name,
            "kit": str(root), "passed": n, "total": len(rows), "ok": n == len(rows) and bool(rows), "entries": rows}


# --- command line ------------------------------------------------------------------------------


def cmd_check(a: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        paths = [_stdin_file(Path(tmp)) if t == "-" else None for t in a.targets]
        files = []
        for t, p in zip(a.targets, paths):
            files += [p] if p is not None else _expand([t])
        results = [conform_file(f, a.level, a.profile) for f in files]
        rep = build_report(results, a.level)
    if a.json:
        _write_json(rep, a.json)
    print(report_text(results, a.verbose), file=sys.stderr if a.json == "-" else sys.stdout)
    return 0 if rep["ok"] else 1


def cmd_kit(a: argparse.Namespace) -> int:
    validator, verdicts, name = None, None, "reference (fidetype Python: consumer + producer check)"
    if a.cmd:
        validator, name = _cmd_validator(a.cmd), a.cmd
    elif a.impl:
        validator, name = _impl_validator(a.impl), a.impl
    elif a.verdicts:
        verdicts, name = _verdicts_file(a.verdicts), f"verdicts file {a.verdicts}"
    rep = run_kit(a.kit, a.profile, validator, verdicts, name)
    if a.json:
        _write_json(rep, a.json)
    out = sys.stderr if a.json == "-" else sys.stdout
    for r in rep["entries"]:
        tag = "ok  " if r["ok"] else "FAIL"
        if a.verbose or not r["ok"]:
            print(f"  {tag} {r['id']} {r['path']:<44} expect {r['verdict']:<20} {r['detail']}".rstrip(), file=out)
    print(f"[nts-conform kit: {'PASS' if rep['ok'] else 'FAIL'}] {rep['passed']}/{rep['total']} kit files give the "
          f"expected verdict ({name})", file=out)
    return 0 if rep["ok"] else 1


def cmd_list(a: argparse.Namespace) -> int:
    from fidetype.conformance.kit import kit_dir

    es = _entries(Path(a.kit) if a.kit else kit_dir(), a.profile)
    if a.markdown:
        print("| Id | File | Wire form | Verdict | Rules | Description |")
        print("|---|---|---|---|---|---|")
    for e in es:
        if a.markdown:
            print(f"| {e['id']} | `{e['path']}` | {e['wire_form']} | {e['verdict']} | {', '.join(e['rules'])} | "
                  f"{e['description']} |")
        else:
            print(f"{e['id']:<4} {e['verdict']:<21} {e['wire_form']:<22} {e['path']:<44} {', '.join(e['rules'])}")
    return 0


def cmd_build(a: argparse.Namespace) -> int:
    from fidetype.conformance.kit import write_kit

    idx = write_kit(a.out)
    print(f"wrote {len(idx['entries'])} kit files, kit.json, rule-map.json and the profile manifests to {a.out}")
    return 0


def cmd_rules(a: argparse.Namespace) -> int:
    from fidetype.conformance.rules import render_rule_map, rule_map_path

    text = render_rule_map()
    if a.write:
        rule_map_path().write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {rule_map_path()}")
        return 0
    if a.check:
        cur = rule_map_path().read_text(encoding="utf-8") if rule_map_path().is_file() else ""
        same = cur.replace("\r\n", "\n") == text
        print("rule-map.json is up to date" if same else "rule-map.json is stale: run nts-conform rules --write")
        return 0 if same else 1
    sys.stdout.write(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    from fidetype.conformance.profiles import PROFILE_NAMES

    profiles = ("v0.1", *PROFILE_NAMES)
    p = argparse.ArgumentParser(prog="nts-conform", description="NTS conformance kit runner (NTS 1.0 RC4 draft)")
    sub = p.add_subparsers(dest="cmd_name", required=True)
    c = sub.add_parser("check", help="producer check of files or captures: per-rule report")
    c.add_argument("targets", nargs="+", help='file, directory, or "-" for stdin')
    c.add_argument("--level", choices=LEVELS, default="core", help="failures below this level are FAIL, above are WARN")
    c.add_argument("--profile", action="append", choices=profiles, help="run only these suite profiles (repeatable)")
    c.add_argument("--json", help="write the JSON report here ('-' = stdout)")
    c.add_argument("--verbose", "-v", action="store_true", help="also list passed checks")
    c.set_defaults(func=cmd_check)
    k = sub.add_parser("kit", help="run the kit: reference, or check your validator's verdicts")
    k.add_argument("--kit", help="kit directory (default spec/conformance/kit)")
    k.add_argument("--profile", choices=profiles, help="only the entries of this suite profile")
    g = k.add_mutually_exclusive_group()
    g.add_argument("--cmd", help='your validator: "PROG {path} {profile}"; exit 0 = accept, other = reject')
    g.add_argument("--impl", help="Python validator MODULE:FUNCTION(path[, profile]); returns = accept, raises = reject")
    g.add_argument("--verdicts", help="JSON file with your verdicts: {id: accept|reject}")
    k.add_argument("--json", help="write the JSON report here ('-' = stdout)")
    k.add_argument("--verbose", "-v", action="store_true", help="list every entry")
    k.set_defaults(func=cmd_kit)
    ls = sub.add_parser("list", help="list the kit entries")
    ls.add_argument("--kit")
    ls.add_argument("--profile", choices=profiles)
    ls.add_argument("--markdown", action="store_true")
    ls.set_defaults(func=cmd_list)
    b = sub.add_parser("build", help="write the kit files (maintainers)")
    b.add_argument("--out", required=True)
    b.set_defaults(func=cmd_build)
    r = sub.add_parser("rules", help="the check -> rule map from spec Appendix C")
    gr = r.add_mutually_exclusive_group()
    gr.add_argument("--write", action="store_true")
    gr.add_argument("--check", action="store_true")
    r.set_defaults(func=cmd_rules)
    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (InputError, FileNotFoundError) as e:
        print(f"nts-conform: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
