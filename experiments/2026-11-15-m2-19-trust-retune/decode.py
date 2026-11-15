"""M2-19 decode: run the M4-12 checkpoints (unchanged) on val_select and val_eval at L 0.

Writes ONLY to C:/Users/zhang/bci-data/derived/m2-19-trust-retune/ (file names carry m2-19):
  logprobs-m2-19-<run>.npz   keys "<session>|<part>|<i>|L0"
  decode-m2-19-<run>.json    checkpoint hash, parts, device
Reads (never writes) the M4-01/02 derived features through the M4-12 t15 module.

Run (repo root): C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -u experiments/2026-11-15-m2-19-trust-retune/decode.py --run m4-12-fixed0 --gpu
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-11-14-m4-12-decoder-retrain"))
import t15 as T  # noqa: E402  (read-only use: paths, load_part)

OWN = Path("C:/Users/zhang/bci-data/derived/m2-19-trust-retune")
assert OWN.name == "m2-19-trust-retune"
T.set_threads(4)
T.below_normal_priority()

import numpy as np  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, choices=["m4-12-fixed0", "m4-12-shared"])
    ap.add_argument("--gpu", action="store_true")
    a = ap.parse_args()
    if not a.gpu:
        os.environ["HIP_VISIBLE_DEVICES"] = "-1"
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch

    torch.set_num_threads(4)
    torch.backends.cudnn.enabled = False
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, build_torch_model

    ck_path = T.RUNS / a.run / "best.pt"
    sha = hashlib.sha256(ck_path.read_bytes()).hexdigest()
    dev = "cuda" if a.gpu and torch.cuda.is_available() else "cpu"
    ck = torch.load(ck_path, map_location=dev, weights_only=False)
    model = build_torch_model(LookaheadGRUConfig(**ck["model_config"])).to(dev)
    model.load_state_dict(ck["model"])
    model.eval()
    la = 0
    out = {}
    parts = ["val_select", "val_eval"]
    counts = {}
    with torch.no_grad():
        for part in parts:
            items = T.load_part(part)
            counts[part] = len(items)
            order = sorted(range(len(items)), key=lambda j: items[j][1].shape[0])
            bs = 16  # same batching as M4-12 decode.py
            for b0 in range(0, len(order), bs):
                idx = order[b0:b0 + bs]
                Tm = max(items[j][1].shape[0] for j in idx)
                X = np.zeros((len(idx), Tm, 512), np.float32)
                for r, j in enumerate(idx):
                    X[r, :items[j][1].shape[0]] = items[j][1]
                lens = torch.tensor([items[j][1].shape[0] for j in idx], device=dev)
                sess = torch.tensor([items[j][0] for j in idx], device=dev)
                lp = model(torch.from_numpy(X).to(dev), sess, la, lens).log_softmax(-1).cpu().numpy()
                nf = model.n_frames(lens).cpu().numpy()
                for r, j in enumerate(idx):
                    out[f"{items[j][3]}|L{la}"] = lp[r, :int(nf[r])].astype(np.float32)
            print(a.run, part, len(items), "done", flush=True)
    OWN.mkdir(parents=True, exist_ok=True)
    np.savez(OWN / f"logprobs-m2-19-{a.run}.npz", **out)
    meta = {"run": a.run, "checkpoint": str(ck_path), "checkpoint_sha256": sha, "epoch": ck.get("epoch"), "lookahead_bins": [la],
            "parts": counts, "model_config": ck["model_config"], "device": dev}
    (OWN / f"decode-m2-19-{a.run}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "model_config"}))


if __name__ == "__main__":
    main()
