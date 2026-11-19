"""``fidetype decoders``: list, check and run the pretrained decoders (P14-01).

::

    fidetype decoders list                       # models, status, licence flags
    fidetype decoders info t15-m4-13             # the model card (add --json for the manifest)
    fidetype decoders path t15-m4-13             # where the release files are looked for
    fidetype decoders verify t15-m4-13           # SHA-256 + size of the local files
    fidetype decoders decode t15-m4-13 t15.2023.08.13/data_val.hdf5 --limit 3 --out streams/
    fidetype decoders decode emg2qwerty-p11-01 session.hdf5 --accept-research-only

``decode`` writes one NTS JSON Lines file per stream (with ``--out``), checks each stream with the
conformance suite (``--level``, default ``provenance``) and prints one line per stream. ``--text``
adds the greedy readout (it prints decoded text: keep it out of committed files).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import fidetype.pretrained as ftp


def _cmd_list(a: argparse.Namespace) -> int:
    ms = ftp.list_models()
    if a.json:
        print(json.dumps([m.raw for m in ms], indent=1, ensure_ascii=False))
        return 0
    print(f"{'name':<20} {'status':<10} {'modality':<14} {'data licence':<18} {'research only':<13} title")
    for m in ms:
        print(f"{m.name:<20} {m.status:<10} {m.modality:<14} {m.data_licence:<18} "
              f"{str(m.research_only).lower():<13} {m.title}")
    print(f"\ncache: {ftp.default_cache_dir()} (set {ftp.ENV_DIR} or pass --weights)")
    return 0


def _cmd_info(a: argparse.Namespace) -> int:
    m = ftp.info(a.name)
    print(json.dumps(m.raw, indent=1, ensure_ascii=False) if a.json else m.card())
    return 0


def _cmd_path(a: argparse.Namespace) -> int:
    cache = Path(a.cache_dir) if a.cache_dir else ftp.default_cache_dir()
    print(f"cache: {cache}")
    names = [a.name] if a.name else [m.name for m in ftp.list_models("available")]
    for n in names:
        m = ftp.info(n)
        for f in m.files:
            p = (cache / "text" / f.name) if f.role == "text" and not (cache / m.name / f.name).exists() else cache / m.name / f.name
            print(f"  {m.name:<20} {f.role:<7} {'present' if p.is_file() else 'MISSING':<8} {p}")
    return 0


def _cmd_verify(a: argparse.Namespace) -> int:
    roles = ("weights", "card", "guard", "text")
    files = ftp.resolve_files(a.name, weights=a.weights, cache_dir=a.cache_dir, roles=roles,
                              accept_research_only=a.accept_research_only)
    for name, p in files.items():
        print(f"ok  {name}  {p}")
    return 0


def _cmd_decode(a: argparse.Namespace) -> int:
    import fidetype.conformance as C

    m = ftp.load(a.name, weights=a.weights, cache_dir=a.cache_dir, accept_research_only=a.accept_research_only)
    pairs = m.decode_file(a.file, limit=a.limit, with_items=True)
    paths = m.save([s for _, s in pairs], a.out) if a.out else [None] * len(pairs)
    bad = 0
    for (it, st), p in zip(pairs, paths):
        rep = C.check(st)
        ok = rep.passes(a.level)
        bad += not ok
        line = f"{it.key}  frames {st.n_frames}  level {rep.level}{'' if ok else ' (BELOW ' + a.level + ')'}"
        if p is not None:
            line += f"  -> {p}"
        if a.text:
            line += f"\n    {m.text(st)}"
        print(line)
    print(f"{len(pairs)} streams from {m.name} (weights sha256 {m.weights_sha256[:16]}..., data licence "
          f"{m.manifest.data_licence}, research_only {str(m.research_only).lower()}); {bad} below level {a.level}")
    return 1 if bad else 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fidetype decoders", description="pretrained decoders (P14-01)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="list the models")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("info", help="print the model card")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("path", help="show where the release files are looked for")
    p.add_argument("name", nargs="?")
    p.add_argument("--cache-dir")
    for nm, hp in (("verify", "check SHA-256 and size of the local release files"),
                   ("decode", "decode a data file into NTS streams")):
        p = sub.add_parser(nm, help=hp)
        p.add_argument("name")
        if nm == "decode":
            p.add_argument("file")
            p.add_argument("--out", help="folder for the .nts.jsonl files")
            p.add_argument("--limit", type=int)
            p.add_argument("--level", default="provenance", choices=["core", "trust-ready", "provenance"])
            p.add_argument("--text", action="store_true", help="also print the greedy readout")
        p.add_argument("--weights", help="folder with the release files (or the weights file)")
        p.add_argument("--cache-dir")
        p.add_argument("--accept-research-only", action="store_true",
                       help="opt in to a research-only model (non-commercial licence; you accept its terms)")
    a = ap.parse_args(argv)
    try:
        return {"list": _cmd_list, "info": _cmd_info, "path": _cmd_path, "verify": _cmd_verify,
                "decode": _cmd_decode}[a.cmd](a)
    except (ftp.PretrainedError, ftp.ManifestError, KeyError) as e:
        print(f"fidetype decoders: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
