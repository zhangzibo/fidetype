"""Hub command line (roadmap P13-06): ``python -m fidetype.benchmark.hub`` or ``fidetype hub``.

Sub-commands:

``list [--all] [--json]``
    One line per dataset version of the registry (``--all``: also candidate and withdrawn entries).
``show DATASET [--version V] [--json]``
    One registry entry: source, licence, forms, checksums, verify commands, adapters, tracks.
``instructions DATASET [--version V]``
    How to download and verify the dataset. It prints the **official source only**. The hub never downloads,
    mirrors or re-hosts data (design rule 1).
``verify DATASET --data PATH [--version V] [--form F] [--json]``
    Size and SHA-256 of your local files against the registry. PATH is one file or the folder that holds
    them. Exit code 0 = every found file matches; 1 = a mismatch; 2 = no registered file found.
``check [--registry FILE | --entry FILE]``
    Check the committed registry (default), another registry file, or one dataset entry (a JSON object, for
    example from a pull request). Exit code 1 on a problem.
``recipe CARD [--json]``
    Print the rerun recipe of a score card (``rerun: no`` when it has none).
``rerun CARD --submission DIR --truth FILE [--out FILE]``
    Rerun a ``rescore``-level recipe and compare the new card with CARD (the ``rerun`` block is left out of
    the comparison). Exit code 0 = identical; 1 = different.

With no sub-command the command checks the committed registry (the P13-01 behaviour).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from fidetype.benchmark import hub

_GLOB = set("*?[")


def _entry(a: argparse.Namespace) -> dict[str, Any]:
    try:
        return hub.get_dataset(a.dataset, a.version)
    except KeyError as e:
        ids = sorted({d["id"] for d in hub.load_registry()["datasets"]})
        raise SystemExit(f"{e.args[0]}; known: {', '.join(ids)}") from None


def _flags(d: Mapping[str, Any]) -> str:
    return " RESEARCH ONLY" if d["licence"].get("research_only") else ""


def cmd_list(a: argparse.Namespace) -> int:
    ds = [d for d in hub.load_registry()["datasets"] if a.all or d["status"] in ("registered", "deprecated")]
    if a.json:
        print(json.dumps([{k: d[k] for k in ("id", "version", "revision", "status", "hub_role", "modality",
                                             "language")} | {"licence": d["licence"]["spdx"],
                                                             "research_only": d["licence"]["research_only"],
                                                             "tracks": [t["track"] for t in d["tracks"]]}
                          for d in ds], indent=1))
        return 0
    print(f"{'dataset':18s} {'version':26s} {'rev':>3s}  {'status':10s} {'role':8s} {'modality':13s} "
          f"{'licence':13s} tracks")
    for d in ds:
        tracks = ", ".join(f"{t['track']} ({t['split_version']})" for t in d["tracks"])
        print(f"{d['id']:18s} {d['version']:26s} {d['revision']:>3d}  {d['status']:10s} {d.get('hub_role') or '-':8s} "
              f"{d['modality']:13s} {d['licence']['spdx']:13s} {tracks}{_flags(d)}")
    return 0


def _files(d: Mapping[str, Any]) -> list[str]:
    out = []
    for f in d["forms"]:
        for fl in f.get("files", []):
            size = f"{fl['bytes']:,} bytes" if fl.get("bytes") else "size not recorded"
            sha = f"sha256 {fl['sha256']}" if fl.get("sha256") else f"no sha256: {fl.get('note')}"
            out.append(f"  [{f['form']}] {fl['name']}  ({size}; {sha})")
        if not f.get("files"):
            out.append(f"  [{f['form']}] {f['description']} (no files to check)")
    return out


def cmd_show(a: argparse.Namespace) -> int:
    d = _entry(a)
    if a.json:
        print(json.dumps(d, indent=1, ensure_ascii=False))
        return 0
    lic = d["licence"]
    L = [f"{d['id']} {d['version']} (revision {d['revision']}, {d['status']}){_flags(d)}",
         f"  {d['title']}",
         f"  modality {d['modality']}, language {d['language']}, participants {d.get('participants')}, "
         f"role {d.get('hub_role') or '-'}, steward {d['steward']}",
         f"  source: {d['url']}",
         f"  citation: {d['citation']['text']}",
         f"  licence: {lic['spdx']} (research_only {lic['research_only']}, share_alike {lic['share_alike']})",
         f"  attribution: {lic['attribution']}",
         "forms and files:", *_files(d),
         "verify:"]
    for k in ("files", "units"):
        if d["verify"].get(k):
            L.append(f"  {k}: {d['verify'][k]}")
    if d.get("prepare"):
        L.append(f"prepare: {d['prepare']}")
    L.append("adapters:")
    L += [f"  [{x['form']}] {x['module']}: {x['call']} -> {x['emits']} (transports: {', '.join(x['transports'])})"
          for x in d.get("adapters", [])]
    L.append("tracks: " + ", ".join(f"{t['track']} ({t['split_version']})" for t in d["tracks"]))
    for s in d.get("same_units") or []:
        L.append(f"same units in forms {', '.join(s['forms'])}: {s.get('note')}")
    print("\n".join(L))
    return 0


def cmd_instructions(a: argparse.Namespace) -> int:
    d = _entry(a)
    dl, vf = d["download"], d["verify"]
    L = [f"# {d['id']} {d['version']}: download and verify",
         "# Fidetype never downloads, mirrors or re-hosts this data. Get every file from the official source.",
         f"source:      {d['url']}",
         f"citation:    {d['citation']['text']}",
         f"licence:     {d['licence']['spdx']} ({d['licence']['source_text']})"
         + ("  -- RESEARCH ONLY: results and weights are non-commercial" if d["licence"]["research_only"] else ""),
         f"attribution: {d['licence']['attribution']}",
         f"login:       {'required' if dl.get('login_required') else 'not required'}",
         "",
         "1. Download (official source only):",
         f"   {dl['instructions']}",
         "2. Check the files:",
         f"   python -m fidetype.benchmark.hub verify {d['id']} --data <path>"]
    if vf.get("files"):
        L.append(f"   (same check by hand: {vf['files']})")
    L += [*_files(d)]
    n = 3
    if vf.get("units"):
        L += [f"{n}. Check the split units:", f"   {vf['units']}"]
        n += 1
    if d.get("prepare"):
        L += [f"{n}. Build the local cache (never commit it):", f"   {d['prepare']}"]
    L.append(f"Privacy: {d['personal_data'].get('note')}")
    print("\n".join(L))
    return 0


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def verify_files(d: Mapping[str, Any], data: str | Path, form: str | None = None) -> list[dict[str, Any]]:
    """Check local files against the registry entry ``d``. One row per registered file.

    Status: ``ok``, ``size-mismatch``, ``sha256-mismatch``, ``missing``, ``no-checksum`` (found, but the registry
    has no SHA-256), ``not-checkable`` (a pattern of many files, no per-file manifest yet: gap 79)."""
    data = Path(data)
    rows = []
    for f in d["forms"]:
        if form and f["form"] != form:
            continue
        for fl in f.get("files", []):
            name = fl["name"]
            row: dict[str, Any] = {"form": f["form"], "name": name}
            if _GLOB & set(name):
                rows.append(row | {"status": "not-checkable", "note": fl.get("note")})
                continue
            p = data if data.is_file() else data / name
            if data.is_file() and data.name != Path(name).name:
                continue  # one file given: check only its own registry row
            if not p.is_file():
                rows.append(row | {"status": "missing", "path": str(p)})
                continue
            size = p.stat().st_size
            row["bytes"] = size
            if fl.get("bytes") is not None and size != fl["bytes"]:
                rows.append(row | {"status": "size-mismatch", "expected_bytes": fl["bytes"]})
                continue
            if not fl.get("sha256"):
                rows.append(row | {"status": "no-checksum", "note": fl.get("note")})
                continue
            got = sha256_file(p)
            rows.append(row | {"status": "ok" if got == fl["sha256"] else "sha256-mismatch", "sha256": got})
    return rows


def cmd_verify(a: argparse.Namespace) -> int:
    d = _entry(a)
    if not Path(a.data).exists():
        raise SystemExit(f"{a.data}: no such file or folder")
    rows = verify_files(d, a.data, a.form)
    found = [r for r in rows if r["status"] not in ("missing", "not-checkable")]
    bad = [r for r in rows if r["status"].endswith("mismatch")]
    code = 1 if bad else (0 if found else 2)
    if a.json:
        print(json.dumps({"dataset": d["id"], "version": d["version"], "files": rows, "exit": code}, indent=1))
        return code
    for r in rows:
        extra = r.get("note") or r.get("path") or ""
        print(f"{r['status']:16s} [{r['form']}] {r['name']}" + (f"  ({extra})" if extra else ""))
    if not rows:
        print("no registered file matches this path")
    if d["verify"].get("units"):
        print(f"next: check the split units with\n  {d['verify']['units']}")
    print({0: "OK: every found file matches the registry", 1: "FAIL: a file does not match the registry",
           2: "no registered file found at this path"}[code], file=sys.stderr)
    return code


def cmd_check(a: argparse.Namespace) -> int:
    if a.entry:
        errs = hub.check_dataset(json.loads(Path(a.entry).read_text(encoding="utf-8")))
        name = a.entry
    else:
        reg = json.loads(Path(a.registry).read_text(encoding="utf-8")) if a.registry else hub.load_registry()
        errs = hub.check_registry(reg)
        name = a.registry or hub.REGISTRY_FILE
    for e in errs:
        print(e, file=sys.stderr)
    if not errs:
        print(f"{name}: OK")
    return 1 if errs else 0


def _card(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_recipe(a: argparse.Namespace) -> int:
    from fidetype.benchmark.hub.recipe import check_recipe, recipe_text

    card = _card(a.card)
    r = card.get("rerun")
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
    else:
        print(recipe_text(r))
    errs = check_recipe(r) if r else []
    for e in errs:
        print(e, file=sys.stderr)
    return 1 if errs else 0


def cmd_rerun(a: argparse.Namespace) -> int:
    from fidetype.benchmark.hub.recipe import card_json, rescore

    out = rescore(_card(a.card), a.submission, a.truth)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(card_json(out["card"]), encoding="utf-8")
    if out["same"]:
        print(f"{a.card}: rerun gives the same card (byte for byte, rerun block left out)")
        return 0
    print(f"{a.card}: rerun gives a DIFFERENT card; keys: {', '.join(out['diff']) or '(formatting only)'}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m fidetype.benchmark.hub",
                                 description="Benchmark hub: dataset registry tools and rerun recipes (metadata "
                                             "only; the hub never downloads or re-hosts data).")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("list", help="list the registry datasets")
    p.add_argument("--all", action="store_true", help="also candidate and withdrawn entries")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_list)
    for name, fn, help_ in (("show", cmd_show, "show one dataset entry"),
                            ("instructions", cmd_instructions,
                             "print the download and verify steps (official source only; never downloads)")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("dataset")
        p.add_argument("--version", default=None, help="upstream version (default: the newest listed)")
        if name == "show":
            p.add_argument("--json", action="store_true")
        p.set_defaults(fn=fn)
    p = sub.add_parser("verify", help="check local files against the registry sizes and SHA-256")
    p.add_argument("dataset")
    p.add_argument("--data", required=True, help="one downloaded file, or the folder that holds the files")
    p.add_argument("--version", default=None)
    p.add_argument("--form", default=None, help="check one form only (for example pkl)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("check", help="check the registry or one dataset entry")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--registry", default=None, help="a registry JSON file (default: the committed one)")
    g.add_argument("--entry", default=None, help="one dataset entry JSON file")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("recipe", help="print the rerun recipe of a score card")
    p.add_argument("card")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_recipe)
    p = sub.add_parser("rerun", help="rerun a rescore-level recipe and compare with the card")
    p.add_argument("card")
    p.add_argument("--submission", required=True, help="the local submission folder (holds decoded text)")
    p.add_argument("--truth", required=True, help="the local truth file (python -m fidetype.benchmark truth ...)")
    p.add_argument("--out", default=None, help="write the new card here")
    p.set_defaults(fn=cmd_rerun)
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if not getattr(a, "fn", None):
        return cmd_check(argparse.Namespace(entry=None, registry=None))
    return int(a.fn(a))
