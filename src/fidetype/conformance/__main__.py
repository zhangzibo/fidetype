"""Command line of the conformance suite: ``python -m fidetype.conformance``.

Sub-commands:

``check TARGET [TARGET ...] [--level L] [--json OUT] [--truth FILE] [--verbose]``
    TARGET is a stream file (``.npz``, ``.jsonl``), a directory (all stream
    files in it), ``adapter:<name>`` or ``adapter:all``. Prints a short
    summary and a badge line. ``--json OUT`` writes the machine-readable
    report (``-`` for stdout; the summary then goes to stderr). The exit
    code is 0 if every target reaches ``--level`` (default ``core``).
``consumer [--vectors DIR] [--impl MODULE:FUNC | --cmd "PROG {path}"] [--json OUT]``
    Runs a consumer over the golden vectors. The default consumer is the
    reference reader (:func:`fidetype.conformance.io.load_stream`).
``vectors --out DIR``
    Writes the golden vectors and ``manifest.json``.
``list [--markdown]``
    Lists every check with its level, keyword and spec clause.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from fidetype.conformance import check_adapter, check_file
from fidetype.conformance.checks import LEVELS, check_table
from fidetype.conformance.report import build_report, summary_text

STREAM_SUFFIXES = (".npz", ".jsonl", ".ndjson")


def _targets(specs: Sequence[str], truth: list[str] | None) -> list:
    reports = []
    for t in specs:
        if t.startswith("adapter:"):
            reports += check_adapter(t.split(":", 1)[1])
            continue
        p = Path(t)
        if p.is_dir():
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in STREAM_SUFFIXES)
            if not files:
                raise SystemExit(f"no stream files in {p}")
            reports += [check_file(f, truth) for f in files]
        elif p.exists():
            reports.append(check_file(p, truth))
        else:
            raise SystemExit(f"no such file or adapter: {t}")
    return reports


def _write_json(obj: Any, out: str) -> None:
    text = json.dumps(obj, indent=1, ensure_ascii=False)
    if out == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(out).write_text(text + "\n", encoding="utf-8")


def cmd_check(a: argparse.Namespace) -> int:
    truth = None
    if a.truth:
        truth = [ln.strip() for ln in Path(a.truth).read_text(encoding="utf-8").splitlines() if ln.strip()]
    reports = _targets(a.targets, truth)
    report = build_report(reports, a.level)
    if a.json:
        _write_json(report, a.json)
    print(summary_text(report, verbose=a.verbose), file=sys.stderr if a.json == "-" else sys.stdout)
    return 0 if report["ok"] else 1


def _load_impl(spec: str):
    mod, _, fn = spec.partition(":")
    if not fn:
        raise SystemExit("--impl must be MODULE:FUNCTION")
    return getattr(importlib.import_module(mod), fn)


def cmd_consumer(a: argparse.Namespace) -> int:
    from fidetype.conformance.io import load_stream
    from fidetype.conformance.vectors import command_consumer, run_consumer

    if a.cmd:
        consume, name = command_consumer(a.cmd), a.cmd
    elif a.impl:
        consume, name = _load_impl(a.impl), a.impl
    else:
        consume, name = load_stream, "fidetype.conformance.io:load_stream (reference)"
    outcomes = run_consumer(consume, a.vectors)
    n_ok = sum(o.ok for o in outcomes)
    rep = {"schema": "fidetype.conformance.consumer-report/1", "consumer": name, "passed": n_ok, "total": len(outcomes),
           "ok": n_ok == len(outcomes), "vectors": [o.to_dict() for o in outcomes]}
    if a.json:
        _write_json(rep, a.json)
    out = sys.stderr if a.json == "-" else sys.stdout
    for o in outcomes:
        if not o.ok:
            print(f"  FAIL {o.vid}: expected {o.expect}, got {o.actual}. {o.detail}", file=out)
    print(f"[NeuralTextStream v0.1 consumer conformance: {'PASS' if rep['ok'] else 'FAIL'}] "
          f"{n_ok}/{len(outcomes)} golden vectors", file=out)
    return 0 if rep["ok"] else 1


def cmd_vectors(a: argparse.Namespace) -> int:
    from fidetype.conformance.vectors import write_vectors

    m = write_vectors(a.out)
    print(f"wrote {len(m['vectors'])} vectors and manifest.json to {a.out}")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    rows = check_table()
    if a.markdown:
        print("| Id | Level | Keyword | Spec clause | Check |")
        print("|---|---|---|---|---|")
        for r in rows:
            h = " (heuristic)" if r["heuristic"] else ""
            print(f"| `{r['id']}` | {r['level']} | {r['keyword']} | {r['clause']} | {r['title']}{h} |")
    else:
        for r in rows:
            print(f"{r['id']:<24} {r['level']:<12} {r['keyword']:<9} {r['clause']:<20} {r['title']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m fidetype.conformance",
                                description="NeuralTextStream v0.1 conformance suite")
    sub = p.add_subparsers(dest="cmd_name", required=True)
    c = sub.add_parser("check", help="check stream files or adapters (producer conformance)")
    c.add_argument("targets", nargs="+", help="stream file, directory, adapter:<name> or adapter:all")
    c.add_argument("--level", choices=LEVELS, default="core", help="level that every target must reach (default core)")
    c.add_argument("--json", help="write the JSON report to this file ('-' = stdout)")
    c.add_argument("--truth", help="text file with ground-truth lines; fails if one appears in the header or meta")
    c.add_argument("--verbose", "-v", action="store_true", help="also list passed checks")
    c.set_defaults(func=cmd_check)
    k = sub.add_parser("consumer", help="run a consumer over the golden vectors")
    k.add_argument("--vectors", help="vector directory (default spec/conformance/v0.1)")
    g = k.add_mutually_exclusive_group()
    g.add_argument("--impl", help="Python consumer MODULE:FUNCTION; returns a value to accept, raises to reject")
    g.add_argument("--cmd", help='external consumer, e.g. "node reader.js {path}"; exit 0 = accept')
    k.add_argument("--json", help="write the JSON report to this file ('-' = stdout)")
    k.set_defaults(func=cmd_consumer)
    v = sub.add_parser("vectors", help="write the golden vectors")
    v.add_argument("--out", required=True)
    v.set_defaults(func=cmd_vectors)
    ls = sub.add_parser("list", help="list all checks")
    ls.add_argument("--markdown", action="store_true")
    ls.set_defaults(func=cmd_list)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
