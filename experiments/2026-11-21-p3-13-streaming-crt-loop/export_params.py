"""P3-13: export the eight P11-01 per-user CRT weights (best.pt) to NumPy arrays for fidetype.pretrained._crt.

Runs in the torch venv (C:/venvs/fidetype-rocm) on the CPU only: it loads the state dicts (map_location cpu) and
writes C:/Users/zhang/bci-data/derived/p3-13/params-u{i}.npz (local only: research-only weights, never committed)
plus params.json (sha256 of each best.pt; the P11-09 infer stage checked the same files against the P11-01 NTS
stream headers). No model is run here.

    C:/venvs/fidetype-rocm/Scripts/python.exe -I experiments/2026-11-21-p3-13-streaming-crt-loop/export_params.py
"""

from __future__ import annotations

import os

os.environ["HIP_VISIBLE_DEVICES"] = ""  # CPU only
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

P1101 = Path("C:/Users/zhang/bci-data/derived/p11-01-emg-decoder")  # READ ONLY
OWN = Path("C:/Users/zhang/bci-data/derived/p3-13")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    OWN.mkdir(parents=True, exist_ok=True)
    info: dict = {"users": {}}
    for i in range(8):
        w = P1101 / "train" / f"personal-u{i}" / "best.pt"
        sd = torch.load(w, map_location="cpu", weights_only=True)["model"]
        params = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in sd.items()}
        tmp = OWN / f"params-u{i}.tmp.npz"
        np.savez(tmp, **params)
        os.replace(tmp, OWN / f"params-u{i}.npz")
        info["users"][f"u{i}"] = {"weights_sha256": sha256_file(w), "n_arrays": len(params)}
        print(f"u{i}: {len(params)} arrays", flush=True)
    (OWN / "params.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
