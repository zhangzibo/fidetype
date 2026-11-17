"""Make the evidence of our own entries in spec/conformance/certified.json (roadmap P7-02).

Maintainer tool. It runs ``nts-conform`` on the reference implementations of
this repository and writes one JSON report per entry to
``spec/conformance/certified/``, then rewrites ``certified.json`` from the
levels that the reports reach. No network, no GPU, synthetic data only.

    python tools/conformance/certify.py            # all entries (needs npm run build and the Rust release CLI)
    python tools/conformance/certify.py --python-only

Entries:

* ``fidetype-collector``: consumer, claim ``text`` (P7-05): ``--cmd "fidetype-collector consume ..."``.
* ``fidetype-python``, ``fidetype-typescript``, ``fidetype-rust``: consumers. ``nts-conform kit`` with the
  reference (Python) or ``--cmd "... consume --profile {profile} --level {level} {path}"``.
* ``adapter-<name>``: producers. The synthetic streams of ``fidetype.conformance.producers`` (the adapter code
  on synthetic input), written as JSON Lines with ``fidetype.writer.write_stream``, then ``nts-conform check``.
* ``adapter-text-nbest``: producer. A hypothesis-only stream of ``fidetype.adapters.text_nbest``.
* ``binding-lsl``, ``binding-ws``: binding producers (P7-06). ``fidetype.conformance.binding_producers`` runs our
  LSL outlets (``replay_to_lsl``, ``DecisionOutlet``) and our WebSocket producer and ``/decisions`` channel in
  this process on loopback; ``nts-conform capture`` records them; then ``nts-conform check`` on the captures and
  their received streams. ``binding-lsl`` needs pylsl (``--extra lsl``), ``binding-ws`` needs websockets.
* ``fidetype-live-lsl``, ``fidetype-live-ws``: ``fidetype live --publish`` (P14-16). The same module runs the CLI
  (``fidetype live --source synthetic``) in a child process with ``--publish lsl:NAME`` or ``--publish
  ws://127.0.0.1:PORT/nts --publish ws://127.0.0.1:PORT/decisions`` and records it with ``nts-conform capture``.

Third-party implementations add their own entry by pull request (docs/conformance.md, "Self-certification");
this tool never writes them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "spec" / "conformance" / "certified"
LIST = REPO / "spec" / "conformance" / "certified.json"
DATE = "2026-11-17"
URL = "https://github.com/zhangzibo/fidetype"
ADAPTER_MODULES = {
    "spanishbcbl": "src/fidetype/adapters/spanishbcbl_meg.py", "b2t25": "src/fidetype/adapters/b2t25.py",
    "toronto": "src/fidetype/adapters/toronto_semg.py", "ctc-logits": "src/fidetype/adapters/ctc_logits.py",
    "willett": "src/fidetype/adapters/willett_handwriting.py", "kt-semg": "src/fidetype/adapters/kt_semg.py",
    "emg2qwerty": "src/fidetype/adapters/emg2qwerty.py",
}


def _clean(obj: object, tmp: Path | None = None) -> object:
    """Replace machine paths with repository-relative or temporary-folder-relative paths."""
    text = json.dumps(obj, ensure_ascii=False)
    for root, rel in ((tmp, "evidence"), (REPO, ".")):
        if root is None:
            continue
        for form in (str(root), str(root).replace("\\", "/"), json.dumps(str(root))[1:-1]):
            text = text.replace(form + "\\\\", rel + "/").replace(form + "/", rel + "/").replace(form, rel)
    return _posix(json.loads(text))


def _posix(obj: object) -> object:
    """Forward slashes in the path fields (the reports are the same on every OS)."""
    if isinstance(obj, dict):
        return {k: (v.replace("\\", "/") if k in ("target", "kit", "path") and isinstance(v, str) else _posix(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_posix(x) for x in obj]
    return obj


def _write(name: str, rep: object, tmp: Path | None = None) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(_clean(rep, tmp), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return f"certified/{name}"


def _versions() -> dict[str, str]:
    import tomllib

    import fidetype

    ts = json.loads((REPO / "sdk" / "typescript" / "package.json").read_text(encoding="utf-8"))["version"]
    rs = tomllib.loads((REPO / "sdk" / "rust" / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    return {"python": fidetype.__version__, "typescript": ts, "rust": rs}


def consumer_entries(python_only: bool) -> list[dict]:
    from fidetype.conformance import nts_conform as NC

    v = _versions()
    base = {"class": "consumer", "profiles": ["text", "intent", "control"], "maintainer": "Fidetype project",
            "repository": URL, "licence": "Apache-2.0", "date": DATE}
    out = []
    rep = NC.run_kit(name="reference (fidetype Python: consumer + producer check)")
    out.append({**base, "id": "fidetype-python", "implementation": "fidetype (Python reference: reader, validator, "
                "nts-conform)", "language": "Python", "version": v["python"],
                "evidence": _write("fidetype-python.kit-report.json", rep),
                "evidence_command": "nts-conform kit --json spec/conformance/certified/fidetype-python.kit-report.json",
                "_rep": rep})
    # P7-05: the collector's input path (file receiver + validate processor). Claim: text, no bindings
    # (it has no reader for LSL / WebSocket captures and no intent / control checks; docs/collector.md).
    cmd = f'"{sys.executable}" -m fidetype.collector consume -q --profile {{profile}} --level {{level}} {{path}}'
    rep = NC.run_kit(validator=NC._cmd_validator(cmd), claim=["text"],
                     name="fidetype-collector consume -q --profile {profile} --level {level} {path}")
    out.append({**base, "profiles": ["text"], "id": "fidetype-collector",
                "implementation": "fidetype-collector (collector input path: file receiver + validate processor, "
                "FEP-0006)", "language": "Python", "version": v["python"],
                "evidence": _write("fidetype-collector.kit-report.json", rep),
                "evidence_command": 'nts-conform kit --claim text --cmd "fidetype-collector consume -q --profile '
                                    '{profile} --level {level} {path}" --json '
                                    'spec/conformance/certified/fidetype-collector.kit-report.json',
                "_rep": rep})
    if python_only:
        return out
    node = shutil.which("node")
    ts_cli = REPO / "sdk" / "typescript" / "bin" / "fidetype-ts.mjs"
    if node and (REPO / "sdk" / "typescript" / "dist" / "index.js").is_file():
        cmd = f'"{node}" "{ts_cli}" consume --profile {{profile}} --level {{level}} {{path}}'
        rep = NC.run_kit(validator=NC._cmd_validator(cmd), name="node sdk/typescript/bin/fidetype-ts.mjs consume "
                         "--profile {profile} --level {level} {path}")
        out.append({**base, "id": "fidetype-typescript", "implementation": "@fidetype/sdk (TypeScript SDK: reader, "
                    "validator)", "language": "TypeScript", "version": v["typescript"],
                    "evidence": _write("fidetype-typescript.kit-report.json", rep),
                    "evidence_command": 'nts-conform kit --cmd "node sdk/typescript/bin/fidetype-ts.mjs consume '
                                        '--profile {profile} --level {level} {path}" --json '
                                        'spec/conformance/certified/fidetype-typescript.kit-report.json',
                    "_rep": rep})
    else:
        print("certify: skip TypeScript (run npm run build in sdk/typescript)", file=sys.stderr)
    exe = REPO / "sdk" / "rust" / "target" / "release" / ("fidetype-rs.exe" if sys.platform == "win32" else "fidetype-rs")
    if exe.is_file():
        cmd = f'"{exe}" consume --profile {{profile}} --level {{level}} {{path}}'
        rep = NC.run_kit(validator=NC._cmd_validator(cmd), name="fidetype-rs consume --profile {profile} "
                         "--level {level} {path}")
        out.append({**base, "id": "fidetype-rust", "implementation": "fidetype (Rust SDK crate: reader, validator)",
                    "language": "Rust", "version": v["rust"], "evidence": _write("fidetype-rust.kit-report.json", rep),
                    "evidence_command": 'nts-conform kit --cmd "sdk/rust/target/release/fidetype-rs consume '
                                        '--profile {profile} --level {level} {path}" --json '
                                        'spec/conformance/certified/fidetype-rust.kit-report.json',
                    "_rep": rep})
    else:
        print("certify: skip Rust (run cargo build --release --bin fidetype-rs in sdk/rust)", file=sys.stderr)
    return out


def producer_entries() -> list[dict]:
    from fidetype.adapters import text_nbest as TN
    from fidetype.conformance import nts_conform as NC
    from fidetype.conformance.producers import TARGETS
    from fidetype.writer import write_stream

    v = _versions()
    base = {"class": "producer", "language": "Python", "version": v["python"], "maintainer": "Fidetype project",
            "repository": URL, "licence": "Apache-2.0", "date": DATE, "bindings": []}
    out = []
    for name, make in TARGETS.items():
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            files = []
            for i, ps in enumerate(make()):
                f = tmp / name / f"{i:02d}-{ps.name.replace('/', '-').replace(' ', '-')}.jsonl"
                f.parent.mkdir(parents=True, exist_ok=True)
                files.append(write_stream(ps.stream, f))
            results = [NC.conform_file(f, "core") for f in files]
            rep = NC.build_report(results, "core")
            ev = _write(f"adapter-{name}.report.json", rep, tmp)
        out.append({**base, "id": f"adapter-{name}", "implementation": f"fidetype adapter {name} "
                    f"({ADAPTER_MODULES[name]}) on synthetic input, written with fidetype.writer",
                    "evidence": ev, "evidence_command": "python tools/conformance/certify.py (writes the synthetic "
                    f"streams of fidetype.conformance.producers '{name}' as JSON Lines, then nts-conform check --json)",
                    "_rep": rep})
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        f = tmp / "text-nbest" / "hypotheses.jsonl"
        f.parent.mkdir(parents=True)
        utts = [TN.Utterance([{"text": "hello world", "score": -1.2}, {"text": "hello word", "score": -2.0}], id="u1"),
                TN.Utterance([{"text": "good morning", "score": -0.8}], id="u2")]
        dec = TN.TextDecoderInfo(modality="emg", name="synthetic-text-decoder", version="1.0.0",
                                 weights_sha256="0" * 64, extra={"data.derived": True})
        TN.write_stream(utts, dec, f)
        rep = NC.build_report([NC.conform_file(f, "core")], "core")
        ev = _write("adapter-text-nbest.report.json", rep, tmp)
    out.append({**base, "id": "adapter-text-nbest", "implementation": "fidetype adapter text_nbest "
                "(src/fidetype/adapters/text_nbest.py): text n-best lists to hypothesis events", "evidence": ev,
                "evidence_command": "python tools/conformance/certify.py (writes a hypothesis-only stream with "
                "fidetype.adapters.text_nbest.write_stream, then nts-conform check --json)", "_rep": rep})
    return out


BINDING_IMPL = {
    "lsl": ("src/fidetype/adapters/lsl.py", "replay_to_lsl (frames + events streams) and DecisionOutlet of "
            "LSLTrustRunner (fidetype.decisions stream)"),
    "ws": ("src/fidetype/adapters/ws.py", "WSProducer / replay_to_ws (/nts) and the /decisions channel of WSServer + "
           "WSTrustRunner"),
}
#: P14-16: ``fidetype live --publish`` (target of fidetype.conformance.binding_producers -> entry id, implementation).
LIVE_IMPL = {
    "live-lsl": ("fidetype-live-lsl", "fidetype live --publish lsl (src/fidetype/live/publish.py): NTSOutlet (frames + "
                 "events streams) and DecisionOutlet (NAME.decisions stream), live decode of the synthetic typist"),
    "live-ws": ("fidetype-live-ws", "fidetype live --publish ws://HOST:PORT/nts and ws://HOST:PORT/decisions "
                "(src/fidetype/live/publish.py): WSProducer and the /decisions channel of WSServer + OutputHub, live "
                "decode of the synthetic typist"),
}


def binding_entries() -> list[dict]:
    """Binding producers (P7-06): captures of our own LSL and WebSocket outlets, recorded on loopback."""
    from fidetype.adapters.lsl import pylsl_available
    from fidetype.adapters.ws import websockets_available
    from fidetype.conformance import nts_conform as NC
    from fidetype.conformance.binding_producers import write_evidence

    v = _versions()
    base = {"class": "producer", "language": "Python", "version": v["python"], "maintainer": "Fidetype project",
            "repository": URL, "licence": "Apache-2.0", "date": DATE}
    have = {"lsl": pylsl_available(), "ws": websockets_available()}
    out = []
    for name, (module, what) in BINDING_IMPL.items():
        if not have[name]:
            print(f"certify: skip binding-{name} (install the {name} extra)", file=sys.stderr)
            continue
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            files = write_evidence(name, tmp / name)
            rep = NC.build_report([NC.conform_file(f, "core") for f in files], "core")
            ev = _write(f"binding-{name}.report.json", rep, tmp)
        out.append({**base, "id": f"binding-{name}", "implementation": f"fidetype {name.upper()} binding "
                    f"({module}): {what}, on the synthetic ctc-logits stream", "bindings": rep["producer"]["bindings"],
                    "evidence": ev, "evidence_command": "python -m fidetype.conformance.binding_producers --out DIR "
                    f"--target {name} (nts-conform capture of our own outlets on loopback), then nts-conform check "
                    f"DIR/{name} --json", "_rep": rep})
    for target, (eid, what) in LIVE_IMPL.items():
        need = "lsl" if target == "live-lsl" else "ws"
        if not have[need]:
            print(f"certify: skip {eid} (install the {need} extra)", file=sys.stderr)
            continue
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            files = write_evidence(target, tmp / target)
            rep = NC.build_report([NC.conform_file(f, "core") for f in files], "core")
            ev = _write(f"{eid}.report.json", rep, tmp)
        out.append({**base, "id": eid, "implementation": what, "bindings": rep["producer"]["bindings"],
                    "evidence": ev, "evidence_command": "python -m fidetype.conformance.binding_producers --out DIR "
                    f"--target {target} (runs fidetype live --publish in a child process; nts-conform capture on "
                    f"loopback), then nts-conform check DIR/{target} --json", "_rep": rep})
    return out


def main(argv: list[str] | None = None) -> int:
    from fidetype.conformance.binding_producers import loopback_lsl_config
    from fidetype.conformance.certified import CERTIFIED_SCHEMA, check_certified
    from fidetype.conformance.kit import KIT_VERSION
    from fidetype.conformance.levels import LEVEL_TITLES
    from fidetype.conformance.rules import SPEC_LABEL

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--python-only", action="store_true", help="skip the TypeScript and Rust consumers")
    a = ap.parse_args(argv)
    loopback_lsl_config()
    entries = consumer_entries(a.python_only) + producer_entries() + binding_entries()
    rows = []
    for e in entries:
        rep = e.pop("_rep")
        lv = rep["level"] if e["class"] == "consumer" else rep["producer"]
        if not lv["level"]:
            print(f"certify: {e['id']} reaches no level; not listed ({lv.get('why_not_higher')})", file=sys.stderr)
            continue
        e.update(level=lv["level"], level_title=LEVEL_TITLES[lv["level"]], spec=SPEC_LABEL, kit_version=KIT_VERSION)
        if e["class"] == "consumer":
            e["bindings"] = [b for b, ok in lv["bindings"].items() if ok]
        else:
            e["profiles"] = lv["covered"] if lv["level"] != "core" else []
            sl = sorted({t["stream_level"] for t in rep["targets"] if t.get("stream_level")})
            e["stream_levels"] = sl
            if lv.get("why_not_higher"):
                e["note"] = "; ".join(lv["why_not_higher"])
        rows.append(e)
    order = ["id", "implementation", "language", "class", "level", "level_title", "profiles", "bindings", "spec",
             "kit_version", "version", "evidence", "evidence_command", "maintainer", "repository", "licence", "date"]
    rows = [{k: r[k] for k in order} | {k: v for k, v in r.items() if k not in order} for r in rows]
    doc = {"schema": CERTIFIED_SCHEMA, "spec": SPEC_LABEL, "section": "9.7 (amendment 3)",
           "note": "Self-certification list. Each entry links the nts-conform JSON report (evidence) that reaches the "
                   "claimed level with the named kit version. The project checks the evidence file "
                   "(nts-conform certified --check), not the implementation. Not a trademark licence. Add an entry "
                   "by pull request: docs/conformance.md, section Self-certification.",
           "generator": "tools/conformance/certify.py (entries of this repository); pull requests (other entries)",
           "entries": rows}
    LIST.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    problems = check_certified(LIST)
    for e in rows:
        print(f"{e['id']:<26} {e['class']:<9} {e['level_title']:<16} {e.get('stream_levels', '')}")
    print(f"wrote {LIST} ({len(rows)} entries); problems: {problems or 'none'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
