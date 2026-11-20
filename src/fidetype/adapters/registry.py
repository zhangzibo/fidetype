"""Adapter registry and catalogue generator (P14-42).

The registry is **built from adapter metadata**, not kept by hand. Each
adapter module declares ``ADAPTER_INFO`` (a dict, or a list of dicts for
a module with several adapters). The registry imports every module of
:mod:`fidetype.adapters` plus the reader modules in
:data:`EXTRA_MODULES`, and adds the planned rows of
:mod:`fidetype.adapters.planned` (devices and datasets with no code yet).

Fields of one entry:

========== ==============================================================
``id``      unique, kebab-case
``kind``    one of :data:`KINDS`
``target``  the device, dataset or format
``signal``  an NTS ``device.modality`` value, or ``any``
``status``  ``tested`` / ``experimental`` / ``planned`` (:data:`STATUS_TEXT`)
``licence`` licence notes (code, dependencies, data)
``tests``   repository paths of the tests (and CI scripts) that run it
``docs``    repository path of the documentation (``#anchor`` allowed)
``extra``   optional: the pip extra that the adapter needs
``hardware_tested`` optional: real devices it ran on (default: none)
``roadmap`` planned rows: the roadmap item
========== ==============================================================

Command line (CI runs the check through ``tests/test_adapter_registry.py``)::

    python -m fidetype.adapters.registry            # write docs/adapters.md and docs/adapters.json
    python -m fidetype.adapters.registry --check    # fail if the committed files differ
    python -m fidetype.adapters.registry new my-format   # copy the adapter template

Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import re
import sys
from pathlib import Path
from typing import Any

KINDS = {
    "dataset-replay": "reads a public dataset and emits NTS streams",
    "dataset-reader": "reads the raw files of a public dataset",
    "decoder-output": "turns the output of any decoder into NTS",
    "transport": "moves NTS between programs (network)",
    "device-source": "reads a live device (signal source)",
    "file-reader": "reads a recording file format (signal source)",
    "synthetic-source": "makes synthetic signals (no real data)",
}
STATUS_TEXT = {
    "tested": "CI tests run it, and it ran on the real thing it reads: real public dataset files, or the real "
              "protocol library (pylsl, websockets, BrainFlow) in a loopback.",
    "experimental": "Code and CI tests on synthetic data exist. It has not run on real recordings or a real device.",
    "planned": "No code yet. Not supported.",
}
SIGNALS = ("emg", "eeg", "meg", "opm-meg", "ecog", "intracortical", "fnirs", "other", "any")
REQUIRED = ("id", "kind", "target", "signal", "status", "licence", "tests", "docs")
#: Modules outside fidetype.adapters that hold readers or signal sources.
EXTRA_MODULES = ("fidetype.live.sources", "fidetype.live.replay", "fidetype.data.spanishbcbl")
#: Modules of fidetype.adapters that are tools, not adapters.
NOT_ADAPTERS = {"registry", "testing", "planned"}
ROOT = Path(__file__).resolve().parents[3]
DOC_MD = Path("docs/adapters.md")
DOC_JSON = Path("docs/adapters.json")
TEMPLATE_DIR = Path("templates/adapter")
SCHEMA = "fidetype.adapter-registry/0.1"
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def adapter_modules() -> list[str]:
    import fidetype.adapters as pkg

    names = [f"fidetype.adapters.{m.name}" for m in pkgutil.iter_modules(pkg.__path__) if m.name not in NOT_ADAPTERS]
    return sorted(names) + list(EXTRA_MODULES)


def collect() -> list[dict[str, Any]]:
    """All entries: the implemented ones (from module metadata) first, then the planned ones. Sorted by id."""
    from fidetype.adapters.planned import PLANNED

    impl = []
    for mod in adapter_modules():
        info = getattr(importlib.import_module(mod), "ADAPTER_INFO", None)
        for e in ([info] if isinstance(info, dict) else list(info or [])):
            impl.append(_ordered({"module": mod, **e}))
    planned = [_ordered({"status": "planned", "module": None, "tests": [], **e}) for e in PLANNED]
    return sorted(impl, key=lambda e: e["id"]) + sorted(planned, key=lambda e: e["id"])


def _ordered(e: dict[str, Any]) -> dict[str, Any]:
    """Fixed key order (the JSON stays diff-friendly); defaults for the optional fields; unknown keys last."""
    base = {"extra": None, "hardware_tested": [], "roadmap": None, **e}
    keys = (*REQUIRED, "hardware_tested", "extra", "roadmap", "module")
    return {**{k: base[k] for k in keys if k in base}, **{k: v for k, v in base.items() if k not in keys}}


def validate(entries: list[dict[str, Any]], root: Path = ROOT) -> list[str]:
    """Errors of the registry (empty list: valid). Also: every adapter module declares ``ADAPTER_INFO``."""
    errs, seen = [], set()
    for e in entries:
        tag = e.get("id", "?")
        errs += [f"{tag}: missing field {k!r}" for k in REQUIRED if k not in e]
        if not _ID_RE.match(str(tag)):
            errs.append(f"{tag}: id must be kebab-case")
        if tag in seen:
            errs.append(f"{tag}: duplicate id (an implemented adapter must leave planned.py)")
        seen.add(tag)
        if e.get("kind") not in KINDS:
            errs.append(f"{tag}: kind {e.get('kind')!r} not in {sorted(KINDS)}")
        if e.get("signal") not in SIGNALS:
            errs.append(f"{tag}: signal {e.get('signal')!r} not in {list(SIGNALS)}")
        st = e.get("status")
        if st not in STATUS_TEXT:
            errs.append(f"{tag}: status {st!r} not in {list(STATUS_TEXT)}")
        if st == "planned" and (e.get("module") or e.get("tests")):
            errs.append(f"{tag}: a planned entry has no module and no tests")
        if st != "planned" and not e.get("tests"):
            errs.append(f"{tag}: an implemented adapter needs at least one test")
        if st == "planned" and not e.get("roadmap"):
            errs.append(f"{tag}: a planned entry names its roadmap item")
        for p in [*e.get("tests", []), str(e.get("docs", "")).split("#")[0]]:
            if p and p != DOC_MD.as_posix() and not (root / p).exists():  # the catalogue is generated
                errs.append(f"{tag}: path {p!r} does not exist")
    declared = {e["module"] for e in entries if e.get("module")}
    errs += [f"{m}: module declares no ADAPTER_INFO" for m in adapter_modules() if m not in declared]
    return errs


def _link(path: str) -> str:
    """A repository path as a link from docs/adapters.md."""
    base, _, anchor = path.partition("#")
    tail = f"#{anchor}" if anchor else ""
    if base == DOC_MD.as_posix():
        return tail or "#"
    return f"{base[len('docs/'):]}{tail}" if base.startswith("docs/") else f"../{base}{tail}"


def _cell(s: Any) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(entries: list[dict[str, Any]]) -> str:
    impl = [e for e in entries if e["status"] != "planned"]
    planned = [e for e in entries if e["status"] == "planned"]
    count = {s: sum(e["status"] == s for e in entries) for s in STATUS_TEXT}
    L = [
        "# Adapter catalogue",
        "",
        "<!-- Generated by `python -m fidetype.adapters.registry` from the ADAPTER_INFO of each adapter module and",
        "     src/fidetype/adapters/planned.py. Do not edit by hand. CI fails when this page is stale. -->",
        "",
        "An **adapter** connects a device, a recording file, a public dataset or a decoder to Fidetype. "
        "This page lists every adapter in the repository and the adapters that we plan. "
        f"The machine-readable registry is [adapters.json](adapters.json) (schema `{SCHEMA}`).",
        "",
        f"**Counts:** {count['tested']} tested, {count['experimental']} experimental, {count['planned']} planned. "
        "**No adapter is tested on a real device yet** (column \"Real device\"; roadmap P4-06, externally blocked).",
        "",
        "To add an adapter, read [CONTRIBUTING.md, section 7](../CONTRIBUTING.md#7-adapters-add-a-decoder-or-a-device). "
        "The template is in [templates/adapter/](../templates/adapter/).",
        "",
        "## Status",
        "",
        "| Status | Meaning |",
        "|---|---|",
        *[f"| `{k}` | {v} |" for k, v in STATUS_TEXT.items()],
        "",
        "## Kinds",
        "",
        "| Kind | Meaning |",
        "|---|---|",
        *[f"| `{k}` | {v} |" for k, v in KINDS.items()],
        "",
        "## Adapters in the repository",
        "",
        "| Id | Kind | Device, dataset or format | Signal | Status | Real device | Licence notes | Tests | Docs |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for e in impl:
        tests = ", ".join(f"[{Path(t).name}]({_link(t)})" for t in e["tests"])
        extra = f" (extra `[{e['extra']}]`)" if e.get("extra") else ""
        hw = ", ".join(e["hardware_tested"]) or "none"
        L.append(f"| `{e['id']}` | {e['kind']} | {_cell(e['target'])}{extra} | {e['signal']} | "
                 f"`{e['status']}` | {_cell(hw)} | {_cell(e['licence'])} | {tests} | "
                 f"[docs]({_link(e['docs'])}) |")
    L += ["", "Module of each adapter:", ""]
    L += [f"- `{e['id']}`: `{e['module']}`" for e in impl]
    L += ["", "## Planned (not supported)", "",
          "These rows have **no code**. They are not supported. Each row names its roadmap item.", "",
          "| Id | Kind | Device, dataset or format | Signal | Roadmap | Licence notes | Docs |",
          "|---|---|---|---|---|---|---|"]
    for e in planned:
        L.append(f"| `{e['id']}` | {e['kind']} | {_cell(e['target'])} | {e['signal']} | {e['roadmap']} | "
                 f"{_cell(e['licence'])} | [docs]({_link(e['docs'])}) |")
    L += _details(impl)
    return "\n".join(L) + "\n"


def _details(impl: list[dict[str, Any]]) -> list[str]:
    """One section per adapter whose docs live on this page: the module docstring (the single source)."""
    out = []
    for e in impl:
        if e["docs"].split("#")[0] != DOC_MD.as_posix():
            continue
        doc = (importlib.import_module(e["module"]).__doc__ or "").replace("``", "`").strip()
        paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", doc) if p.strip()]
        out += ["", f"### {e['id']}", "", f"Module `{e['module']}`.", ""]
        out += [x for p in paras for x in (p, "")][:-1]
    return ["", "## Details of adapters without their own page", *out] if out else []


def render_json(entries: list[dict[str, Any]]) -> str:
    doc = {"schema": SCHEMA, "generated_by": "python -m fidetype.adapters.registry", "status_meaning": STATUS_TEXT,
           "kinds": KINDS, "adapters": entries}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def outputs(root: Path = ROOT) -> dict[Path, str]:
    entries = collect()
    errs = validate(entries, root)
    if errs:
        raise ValueError("invalid adapter registry:\n  " + "\n  ".join(errs))
    return {DOC_MD: render_md(entries), DOC_JSON: render_json(entries)}


def check(root: Path = ROOT) -> list[str]:
    """Regenerate in memory; return the differences with the committed files (empty: fresh)."""
    errs = []
    for rel, text in outputs(root).items():
        p = root / rel
        if not p.exists():
            errs.append(f"{rel} is missing; run: python -m fidetype.adapters.registry")
        elif p.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            errs.append(f"{rel} is stale; run: python -m fidetype.adapters.registry")
    return errs


def scaffold(adapter_id: str, root: Path = ROOT) -> list[Path]:
    """Copy the template: ``src/fidetype/adapters/<module>.py`` and ``tests/test_adapter_<module>.py``."""
    if not _ID_RE.match(adapter_id):
        raise ValueError(f"id {adapter_id!r} must be kebab-case, for example 'my-format'")
    mod = adapter_id.replace("-", "_")
    out = []
    for name, dest in (("my_format.py", f"src/fidetype/adapters/{mod}.py"),
                       ("test_my_format.py", f"tests/test_adapter_{mod}.py")):
        p = root / dest
        if p.exists():
            raise ValueError(f"{dest} exists already")
        text = (root / TEMPLATE_DIR / name).read_text(encoding="utf-8")
        p.write_text(text.replace("my_format", mod).replace("my-format", adapter_id), encoding="utf-8", newline="\n")
        out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.adapters.registry",
                                 description="Build the adapter catalogue, check it, or copy the adapter template.")
    ap.add_argument("command", nargs="?", choices=["build", "new"], default="build")
    ap.add_argument("id", nargs="?", help="new: the adapter id (kebab-case)")
    ap.add_argument("--check", action="store_true", help="fail if docs/adapters.md or docs/adapters.json is stale")
    a = ap.parse_args(argv)
    if a.command == "new":
        if not a.id:
            ap.error("new needs an id")
        for p in scaffold(a.id):
            print(f"wrote {p.relative_to(ROOT)}")
        return 0
    if a.check:
        errs = check()
        for e in errs:
            print(e, file=sys.stderr)
        return 1 if errs else 0
    for rel, text in outputs().items():
        (ROOT / rel).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
