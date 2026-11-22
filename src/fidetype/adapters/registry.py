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
``file_patterns`` file readers: file-name globs (case-insensitive) that
            ``fidetype live --source file`` matches to pick the reader
``support`` implemented rows: ``real-device`` / ``replay-only`` /
            ``synthetic-only`` (:data:`SUPPORT_TEXT`); planned rows: ``untested``
``transport`` implemented rows: list of :data:`TRANSPORTS` keys
``real_data_evidence`` repository paths (tests, CI scripts, experiment
            results) where it ran on real data or a real device
``test_covers`` implemented rows: what the tests cover (CI and real data)
``limits``  implemented rows: the known limits
========== ==============================================================

Rules that keep the claims honest (:func:`validate`): ``real-device`` needs
``hardware_tested``; ``real-device`` and ``replay-only`` need
``real_data_evidence``; ``synthetic-only`` has none; ``tested`` needs
``real-device`` or ``replay-only`` (exception: a ``transport`` that ran
the real protocol library in a loopback, and a ``synthetic-source``);
``experimental`` is ``synthetic-only``.

A ``file-reader`` module also has ``open_source(path, ...)`` (the source
protocol of ``fidetype live``). :func:`pick_file_reader` and
:func:`open_file_source` choose the reader for a file from the registry.

Command line (CI runs the check through ``tests/test_adapter_registry.py``)::

    python -m fidetype.adapters.registry            # write docs/adapters.md, adapters.json, device-support.md
    python -m fidetype.adapters.registry --check    # fail if the committed files differ
    python -m fidetype.adapters.registry new my-format   # copy the adapter template

Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib
import inspect
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
#: Support level (P4-15): on what the adapter really ran. The evidence is in ``real_data_evidence``.
SUPPORT_TEXT = {
    "real-device": "It ran on a real device (column \"Real device\"). The evidence is in the repository.",
    "replay-only": "It ran on real recorded data (public dataset files, real recording files or real decoder "
                   "output). It never ran on a live device.",
    "synthetic-only": "Its tests use synthetic data only (files made by the test, a fake or synthetic board, a "
                      "loopback of the real protocol library with synthetic streams).",
    "untested": "No test runs it. Planned rows only (no code).",
}
#: How the data reaches the adapter.
TRANSPORTS = {
    "file": "reads recording or decoder-output files",
    "dataset": "reads the files of a public dataset",
    "lsl": "Lab Streaming Layer (live, network)",
    "brainflow": "BrainFlow board API (live, in the same process)",
    "websocket": "WebSocket (live, network)",
    "in-process": "a Python call in the same process",
    "generated": "makes its own synthetic signal",
}
#: Kinds that may be ``tested`` with ``synthetic-only`` support (nothing real to read, or the real protocol
#: library in a loopback; STATUS_TEXT["tested"]).
SYNTHETIC_TESTED_KINDS = ("transport", "synthetic-source")
SIGNALS = ("emg", "eeg", "meg", "opm-meg", "ecog", "intracortical", "fnirs", "other", "any")
REQUIRED = ("id", "kind", "target", "signal", "status", "licence", "tests", "docs")
#: Extra fields of an implemented (not planned) entry (P4-15).
IMPL_REQUIRED = ("support", "transport", "test_covers", "limits", "real_data_evidence")
#: Modules outside fidetype.adapters that hold readers or signal sources.
EXTRA_MODULES = ("fidetype.live.sources", "fidetype.live.replay", "fidetype.data.spanishbcbl")
#: Modules of fidetype.adapters that are tools, not adapters.
NOT_ADAPTERS = {"registry", "testing", "planned"}
ROOT = Path(__file__).resolve().parents[3]
DOC_MD = Path("docs/adapters.md")
DOC_JSON = Path("docs/adapters.json")
DOC_DEVICES = Path("docs/device-support.md")
TEMPLATE_DIR = Path("templates/adapter")
SCHEMA = "fidetype.adapter-registry/0.2"
GENERATED = {DOC_MD.as_posix(), DOC_JSON.as_posix(), DOC_DEVICES.as_posix()}
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
    planned = [_ordered({"status": "planned", "module": None, "tests": [], "support": "untested",
                         "real_data_evidence": [], **e}) for e in PLANNED]
    return sorted(impl, key=lambda e: e["id"]) + sorted(planned, key=lambda e: e["id"])


def _ordered(e: dict[str, Any]) -> dict[str, Any]:
    """Fixed key order (the JSON stays diff-friendly); defaults for the optional fields; unknown keys last."""
    base = {"extra": None, "hardware_tested": [], "roadmap": None, **e}
    keys = (*REQUIRED, "support", "hardware_tested", "real_data_evidence", "transport", "test_covers", "limits",
            "extra", "roadmap", "file_patterns", "module")
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
        if e.get("kind") == "file-reader" and st != "planned":
            pats = e.get("file_patterns")
            if not pats or not isinstance(pats, list) or not all(isinstance(x, str) and x for x in pats):
                errs.append(f"{tag}: a file reader needs file_patterns (a list of file-name globs)")
            if e.get("module") and not callable(getattr(importlib.import_module(e["module"]), "open_source", None)):
                errs.append(f"{tag}: a file reader module needs open_source(path, ...)")
        errs += _support_errors(e)
        for p in [*e.get("tests", []), *(e.get("real_data_evidence") or []), str(e.get("docs", "")).split("#")[0]]:
            if p and p not in GENERATED and not (root / p).exists():  # the generated pages may be absent
                errs.append(f"{tag}: path {p!r} does not exist")
    declared = {e["module"] for e in entries if e.get("module")}
    errs += [f"{m}: module declares no ADAPTER_INFO" for m in adapter_modules() if m not in declared]
    return errs


def _support_errors(e: dict[str, Any]) -> list[str]:
    """P4-15: the support level, the evidence and the status must agree (no claim without evidence)."""
    tag, st, sup = e.get("id", "?"), e.get("status"), e.get("support")
    ev, hw = e.get("real_data_evidence"), e.get("hardware_tested") or []
    errs = []
    if st != "planned":
        errs += [f"{tag}: missing field {k!r} (P4-15)" for k in IMPL_REQUIRED if k not in e]
        tr = e.get("transport")
        if "transport" in e and (not isinstance(tr, list) or not tr or any(t not in TRANSPORTS for t in tr)):
            errs.append(f"{tag}: transport must be a non-empty list of {list(TRANSPORTS)}")
        for k in ("test_covers", "limits"):
            if k in e and not (isinstance(e[k], str) and e[k].strip()):
                errs.append(f"{tag}: {k} must be a non-empty text")
    if sup not in SUPPORT_TEXT:
        return [*errs, f"{tag}: support {sup!r} not in {list(SUPPORT_TEXT)}"]
    if not isinstance(ev, list):
        return [*errs, f"{tag}: real_data_evidence must be a list of repository paths"]
    if (st == "planned") != (sup == "untested"):
        errs.append(f"{tag}: support 'untested' is for planned rows only (status {st!r}, support {sup!r})")
    if (sup == "real-device") != bool(hw):
        errs.append(f"{tag}: support 'real-device' needs hardware_tested, and hardware_tested needs 'real-device'")
    if sup in ("real-device", "replay-only") and not ev:
        errs.append(f"{tag}: support {sup!r} needs real_data_evidence (the test or result that shows it)")
    if sup in ("synthetic-only", "untested") and ev:
        errs.append(f"{tag}: support {sup!r} cannot list real_data_evidence")
    if st == "tested" and sup == "synthetic-only" and e.get("kind") not in SYNTHETIC_TESTED_KINDS:
        errs.append(f"{tag}: status 'tested' with synthetic-only tests (only a {' or '.join(SYNTHETIC_TESTED_KINDS)}"
                    " may be tested without real data); use 'experimental'")
    if st == "experimental" and sup != "synthetic-only":
        errs.append(f"{tag}: status 'experimental' means synthetic-only tests (support {sup!r}); use 'tested'")
    return errs


def file_readers(entries: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The implemented ``file-reader`` entries (the readers that ``fidetype live --source file`` can use)."""
    return [e for e in (collect() if entries is None else entries)
            if e.get("kind") == "file-reader" and e.get("status") != "planned"]


def _patterns(readers: list[dict[str, Any]]) -> str:
    return "; ".join(f"{e['id']}: {', '.join(e.get('file_patterns') or [])}" for e in readers)


def match_file_readers(path: str | Path, entries: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The file readers whose ``file_patterns`` match the file name (case-insensitive)."""
    name = Path(path).name.lower()
    return [e for e in file_readers(entries)
            if any(fnmatch.fnmatchcase(name, p.lower()) for p in e.get("file_patterns") or [])]


def pick_file_reader(path: str | Path, reader: str | None = None,
                     entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The registry entry of the reader for ``path``: ``reader`` (an id) if given, else the one name match.

    Raises ``ValueError`` for an unknown id, for no match and for more than one match.
    """
    readers = file_readers(entries)
    if reader:
        for e in readers:
            if e["id"] == reader:
                return e
        raise ValueError(f"no file reader with id {reader!r}; file readers: {', '.join(e['id'] for e in readers)}")
    hits = match_file_readers(path, readers)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ValueError(f"no file reader matches the file name {Path(path).name!r} ({_patterns(readers)}); "
                         "give the reader id (--reader ID)")
    raise ValueError(f"more than one file reader matches {Path(path).name!r} ({_patterns(hits)}); "
                     "give the reader id (--reader ID)")


def open_file_source(path: str | Path, reader: str | None = None, **options: Any) -> tuple[dict[str, Any], Any]:
    """Pick the reader (:func:`pick_file_reader`) and call its ``open_source(path, **options)``.

    Options with the value None are not passed. An option that ``open_source`` does not take raises
    ``ValueError``. Returns (registry entry, source).
    """
    e = pick_file_reader(path, reader)
    fn = importlib.import_module(e["module"]).open_source
    opts = {k: v for k, v in options.items() if v is not None}
    params = inspect.signature(fn).parameters
    if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
        bad = sorted(k for k in opts if k not in params)
        if bad:
            raise ValueError(f"the {e['id']} reader does not take the option(s) {', '.join(bad)}")
    return e, fn(path, **opts)


def _link(path: str, page: Path = DOC_MD) -> str:
    """A repository path as a link from ``page`` (a generated page in docs/)."""
    base, _, anchor = path.partition("#")
    tail = f"#{anchor}" if anchor else ""
    if base == page.as_posix():
        return tail or "#"
    return f"{base[len('docs/'):]}{tail}" if base.startswith("docs/") else f"../{base}{tail}"


def _cell(s: Any) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(entries: list[dict[str, Any]]) -> str:
    impl = [e for e in entries if e["status"] != "planned"]
    planned = [e for e in entries if e["status"] == "planned"]
    count = {s: sum(e["status"] == s for e in entries) for s in STATUS_TEXT}
    n_dev = sum(e.get("support") == "real-device" for e in entries)
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
        + (f"{n_dev} adapter(s) ran on a real device (column \"Real device\")." if n_dev else "**No adapter is tested on a real device yet** (column \"Real device\"; roadmap P4-06, "
                "externally blocked)."),
        "",
        "Which device, file format or dataset works, on what data each one ran and its known limits: "
        "[device support matrix](device-support.md) (generated from the same metadata).",
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
        "| Id | Kind | Device, dataset or format | Signal | Status | Support | Real device | Licence notes | Tests "
        "| Docs |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in impl:
        tests = ", ".join(f"[{Path(t).name}]({_link(t)})" for t in e["tests"])
        extra = f" (extra `[{e['extra']}]`)" if e.get("extra") else ""
        hw = ", ".join(e["hardware_tested"]) or "none"
        L.append(f"| `{e['id']}` | {e['kind']} | {_cell(e['target'])}{extra} | {e['signal']} | "
                 f"`{e['status']}` | `{e.get('support')}` | {_cell(hw)} | {_cell(e['licence'])} | {tests} | "
                 f"[docs]({_link(e['docs'])}) |")
    L += ["", "Module of each adapter:", ""]
    L += [f"- `{e['id']}`: `{e['module']}`" for e in impl]
    readers = file_readers(entries)
    if readers:
        L += ["", "## File readers for `fidetype live`", "",
              "`fidetype live --source file --path FILE` picks the reader whose file-name pattern matches FILE "
              "(case-insensitive). `--reader ID` picks a reader by its id (for a renamed file, or when more than "
              "one pattern matches). See "
              "[live-decode.md, section 3a](live-decode.md#3a-recording-files---source-file).",
              "", "| Id | File names | Example |", "|---|---|---|"]
        L += [f"| `{e['id']}` | {', '.join(f'`{p}`' for p in e['file_patterns'])} | "
              f"`fidetype live --source file --reader {e['id']} --path FILE` |" for e in readers]
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


#: Sections of the device support matrix: (heading, kinds).
DEVICE_GROUPS = (
    ("Live devices and signal sources", ("device-source", "synthetic-source")),
    ("Recording files", ("file-reader",)),
    ("Public datasets (recorded data)", ("dataset-replay", "dataset-reader")),
    ("Decoder outputs and transports", ("decoder-output", "transport")),
)


def render_devices_md(entries: list[dict[str, Any]]) -> str:
    """docs/device-support.md (P4-15): the device support matrix, from the same metadata as the catalogue."""
    impl = [e for e in entries if e["status"] != "planned"]
    planned = [e for e in entries if e["status"] == "planned"]
    count = {s: sum(e.get("support") == s for e in entries) for s in SUPPORT_TEXT}
    real = [e for e in impl if e.get("support") == "real-device"]
    page = DOC_DEVICES
    L = [
        "# Device support matrix",
        "",
        "<!-- GENERATED FILE. DO NOT EDIT. Made by `python -m fidetype.adapters.registry` from the ADAPTER_INFO of",
        "     each adapter module and src/fidetype/adapters/planned.py (roadmap P4-15).",
        "     CI fails when this page and the metadata differ (tests/test_adapter_registry.py). -->",
        "",
        "This page tells you which devices, recording files and public datasets work with Fidetype, on what data "
        "each adapter ran, and its known limits. A script makes the page from the metadata in the code. "
        "The full catalogue (licences, tests, modules) is [adapters.md](adapters.md).",
        "",
        f"**Support:** {count['real-device']} real device, {count['replay-only']} replay only, "
        f"{count['synthetic-only']} synthetic only, {count['untested']} untested (planned).",
        "",
        (f"Real devices: {', '.join(sorted({h for e in real for h in e['hardware_tested']}))}." if real else
         "**No adapter has run on a real device yet.** The project has no EEG, EMG or MEG hardware. Real-device "
         "tests are roadmap P4-06 and M6-12 (externally blocked: they need hardware and volunteers)."),
        "",
        "## Support levels",
        "",
        "| Support | Meaning |",
        "|---|---|",
        *[f"| `{k}` | {v} |" for k, v in SUPPORT_TEXT.items()],
        "",
        "The status column uses the catalogue levels: "
        + "; ".join(f"`{k}`: {v.rstrip('.')}" for k, v in STATUS_TEXT.items() if k != "planned")
        + ". The registry refuses `tested` without real data, except for a transport (real protocol library in a "
          "loopback) and the synthetic source. The registry also refuses `real-device` or `replay-only` without "
          "a test or result in the repository (column \"Tests cover\", \"Evidence\").",
        "",
        "Transports: " + "; ".join(f"`{k}` = {v}" for k, v in TRANSPORTS.items()) + ".",
    ]
    hdr = ["| Device or format | Reader id | Modality | Transport | Status | Support | Tests cover | Known limits "
           "| Docs |", "|---|---|---|---|---|---|---|---|---|"]
    for title, kinds in DEVICE_GROUPS:
        rows = [e for e in impl if e["kind"] in kinds]
        if not rows:
            continue
        L += ["", f"## {title}", "", *hdr]
        for e in rows:
            ev = ", ".join(f"[{Path(p).name if Path(p).name != 'results.md' else Path(p).parent.name}]"
                           f"({_link(p, page)})" for p in e["real_data_evidence"])
            covers = _cell(e["test_covers"]) + (f" Evidence: {ev}." if ev else "")
            hw = f" Devices: {', '.join(e['hardware_tested'])}." if e["hardware_tested"] else ""
            extra = f" (extra `[{e['extra']}]`)" if e.get("extra") else ""
            L.append(f"| {_cell(e['target'])}{extra} | `{e['id']}` | {e['signal']} | "
                     f"{', '.join(e['transport'])} | `{e['status']}` | `{e['support']}` | {covers}{hw} | "
                     f"{_cell(e['limits'])} | [docs]({_link(e['docs'], page)}) |")
    L += ["", "## Planned (no code, not supported)", "",
          "These rows have no code. Their support is `untested`. Each row names its roadmap item.", "",
          "| Device, dataset or format | Id | Kind | Modality | Support | Roadmap |", "|---|---|---|---|---|---|"]
    L += [f"| {_cell(e['target'])} | `{e['id']}` | {e['kind']} | {e['signal']} | `{e['support']}` | "
          f"{e['roadmap']} |" for e in planned]
    L += ["", "## Add or change a row", "",
          "Edit the `ADAPTER_INFO` of the adapter module (fields `status`, `support`, `hardware_tested`, "
          "`real_data_evidence`, `transport`, `test_covers`, `limits`), then run "
          "`python -m fidetype.adapters.registry`. Do not edit this page. See "
          "[CONTRIBUTING.md, section 7](../CONTRIBUTING.md#7-adapters-add-a-decoder-or-a-device)."]
    return "\n".join(L) + "\n"


def render_json(entries: list[dict[str, Any]]) -> str:
    doc = {"schema": SCHEMA, "generated_by": "python -m fidetype.adapters.registry", "status_meaning": STATUS_TEXT,
           "support_meaning": SUPPORT_TEXT, "transports": TRANSPORTS, "kinds": KINDS, "adapters": entries}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def outputs(root: Path = ROOT) -> dict[Path, str]:
    entries = collect()
    errs = validate(entries, root)
    if errs:
        raise ValueError("invalid adapter registry:\n  " + "\n  ".join(errs))
    return {DOC_MD: render_md(entries), DOC_JSON: render_json(entries), DOC_DEVICES: render_devices_md(entries)}


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
    ap.add_argument("--check", action="store_true",
                    help="fail if docs/adapters.md, docs/adapters.json or docs/device-support.md is stale")
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
