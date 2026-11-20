r"""Export the release files of the pretrained decoders (P14-01). Our own code (Apache-2.0).

This tool reads our local training outputs (outside the repository) and writes the files that
``fidetype.pretrained`` loads: one folder per model under ``--out`` (default: the local cache
``C:\Users\zhang\bci-data\pretrained`` on the project machine). It prints the SHA-256 and the size
of each file, so they can go into ``src/fidetype/pretrained/manifests/<name>.json``.

Nothing here uploads or publishes a file. Hosting is a user step (docs/publishing-checklist.md).
The weights never go into the git repository.

Formats (no pickle in any release file):
- ``*.weights.npz``: plain float32 arrays (``np.load(..., allow_pickle=False)`` reads them).
- ``kt-semg-lda``: the ``fidetype live`` model card + JSON weights + guard (P14-04 format).

Usage (repo root)::

    .venv\Scripts\python.exe -I tools/pretrained/export_weights.py t15-m4-13 kt-semg-lda
    # .pt checkpoints need torch (CPU is enough; never the GPU here):
    C:\venvs\fidetype-rocm\Scripts\python.exe -I tools/pretrained/export_weights.py t12-v2 emg2qwerty-p11-01 willett-hw
    .venv\Scripts\python.exe -I tools/pretrained/export_weights.py --list   # SHA-256 + size of what exists
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

DATA = Path(os.environ.get("FIDETYPE_BCI_DATA", r"C:\Users\zhang\bci-data"))
DEFAULT_OUT = DATA / "pretrained"

#: model name -> (kind, sources). The sources are our local training outputs.
SOURCES: dict[str, dict] = {
    "t15-m4-13": {"kind": "npz-copy", "src": DATA / "derived/m4-13/params-m4-13-long0.npz",
                  "files": {"weights": "t15-m4-13.weights.npz"}},
    "t12-v2": {"kind": "pt-to-npz", "src": DATA / "runs/t12-v2-final/best.pt",
               "files": {"weights": "t12-v2.weights.npz"}},
    "emg2qwerty-p11-01": {"kind": "pt-to-npz", "src": DATA / "derived/p11-01-emg-decoder/train/generic/best.pt",
                          "files": {"weights": "emg2qwerty-p11-01.weights.npz"}},
    # P15-08 E1a run R-all-s0 (random init, all 506 min of Willett CC0 data), final step 3000 = the
    # primary readout (test CER 0.305). Clean track only: the run's licence.json must say research_only false.
    "willett-hw": {"kind": "pt-to-npz", "src": DATA / "derived/p15-08/runs/R-ball-s0/final.pt",
                   "licence_json": DATA / "derived/p15-08/runs/R-ball-s0/licence.json",
                   "files": {"weights": "willett-hw.weights.npz"}},
    "kt-semg-lda": {"kind": "copy", "src_dir": DATA / "derived/p14-04-live/kt",
                    "files": {"card": "kt-semg-lda.model.json", "weights": "kt-semg-lda.weights.json",
                              "guard": "kt-semg-lda.guard.json"}},
}

#: Text resources of the phoneme -> word decoder (the T15 / T12 guards). Not weights; listed with their own licence.
TEXT_SOURCES = {
    "cmudict.dict": DATA / "lexicon/cmudict/cmudict.dict",
    "eng_tatoeba_6gram_mkn.npz": DATA / "lm/eng_tatoeba_6gram_mkn.npz",
    "eng_tatoeba_word_counts.json": DATA / "lm/eng_tatoeba_word_counts.json",
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _pt_to_npz(src: Path, dst: Path) -> dict:
    os.environ["HIP_VISIBLE_DEVICES"] = "-1"  # CPU only
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch

    ck = torch.load(src, map_location="cpu", weights_only=False)
    sd = ck["model"]
    arrays = {k: v.detach().cpu().float().numpy() for k, v in sd.items()}
    tmp = dst.with_suffix(".tmp.npz")
    np.savez(tmp, **arrays)
    os.replace(tmp, dst)
    info = {k: ck[k] for k in ("sessions", "epoch", "step", "val_per", "val_cer") if k in ck}
    return {"checkpoint_sha256": sha256_file(src), **info}


def export(name: str, out: Path) -> dict:
    spec = SOURCES[name]
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    extra: dict = {}
    if spec.get("licence_json"):
        lic = json.loads(Path(spec["licence_json"]).read_text(encoding="utf-8"))
        if lic.get("research_only") is not False:
            raise SystemExit(f"{name}: the training run is not clean-track ({lic}); refusing to export")
        extra["run_licence"] = lic
    if spec["kind"] == "npz-copy":
        shutil.copyfile(spec["src"], d / spec["files"]["weights"])
    elif spec["kind"] == "pt-to-npz":
        extra.update(_pt_to_npz(spec["src"], d / spec["files"]["weights"]))
    elif spec["kind"] == "copy":
        for f in spec["files"].values():
            shutil.copyfile(spec["src_dir"] / f, d / f)
    return {"name": name, "files": describe(d, spec["files"]), **extra}


def describe(d: Path, files: dict[str, str]) -> list[dict]:
    out = []
    for role, f in files.items():
        p = d / f
        if p.is_file():
            out.append({"role": role, "name": f, "sha256": sha256_file(p), "size": p.stat().st_size})
        else:
            out.append({"role": role, "name": f, "missing": True})
    return out


def export_text(out: Path) -> list[dict]:
    d = out / "text"
    d.mkdir(parents=True, exist_ok=True)
    res = []
    for f, src in TEXT_SOURCES.items():
        shutil.copyfile(src, d / f)
        res.append({"role": "text", "name": f, "sha256": sha256_file(d / f), "size": (d / f).stat().st_size})
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help=f"models to export: {sorted(SOURCES)}; 'text' = the word-decoder files")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--list", action="store_true", help="only print SHA-256 and size of the existing files")
    a = ap.parse_args(argv)
    out = Path(a.out)
    res = []
    if a.list:
        for n, s in SOURCES.items():
            res.append({"name": n, "files": describe(out / n, s["files"])})
        res.append({"name": "text", "files": describe(out / "text", {f: f for f in TEXT_SOURCES})})
    else:
        for n in a.names:
            if n == "text":
                res.append({"name": "text", "files": export_text(out)})
            elif n in SOURCES:
                res.append(export(n, out))
            else:
                print(f"unknown model {n!r}", file=sys.stderr)
                return 2
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
