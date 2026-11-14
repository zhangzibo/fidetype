"""Stage decode: run a trained lookahead decoder (best.pt) on val_eval at each lookahead L.

Writes log-probabilities (float32) and the NumPy parameters outside the repo:
  DERIVED/logprobs-<run>.npz      keys "<session>|val_eval|<i>|L<bins>"
  DERIVED/params-<run>.npz        torch state dict as NumPy arrays (for the streaming NumPy decoder)
  DERIVED/decode-<run>.json       checkpoint hash, epoch, config
CPU by default (the GPU trains); --gpu when no training runs.

Run (repo root): C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -u experiments/2026-11-13-m4-01-02-lookahead/decode.py --which shared [--gpu]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t15 as T  # noqa: E402

T.set_threads(4)
T.below_normal_priority()

import numpy as np  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True, choices=sorted(T.CONFIG["runs"]))
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--ckpt", default="best.pt")
    ap.add_argument("--limit", type=int, default=None, help="smoke test only")
    a = ap.parse_args()
    if not a.gpu:
        os.environ["HIP_VISIBLE_DEVICES"] = "-1"
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch

    torch.set_num_threads(4)
    torch.backends.cudnn.enabled = False
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, build_torch_model, export_numpy_params

    spec = T.CONFIG["runs"][a.which]
    run = T.RUNS / spec["run"]
    ck_path = run / a.ckpt
    sha = hashlib.sha256(ck_path.read_bytes()).hexdigest()
    dev = "cuda" if a.gpu and torch.cuda.is_available() else "cpu"
    ck = torch.load(ck_path, map_location=dev, weights_only=False)
    cfg = LookaheadGRUConfig(**ck["model_config"])
    model = build_torch_model(cfg).to(dev)
    model.load_state_dict(ck["model"])
    model.eval()
    las = T.LA_BINS if spec["lookahead_bins"] == "sample" else [int(spec["lookahead_bins"])]
    items = T.load_part("val_eval", a.limit)
    out = {}
    order = sorted(range(len(items)), key=lambda j: items[j][1].shape[0])
    bs = 16
    with torch.no_grad():
        for la in las:
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
                    # padding is masked (lengths) and the model is causal, so the valid rows equal a single-item pass
                    out[f"{items[j][3]}|L{la}"] = lp[r, :int(nf[r])].astype(np.float32)
            print(a.which, "L", la, "done", flush=True)
    T.DERIVED.mkdir(parents=True, exist_ok=True)
    np.savez(T.DERIVED / f"logprobs-{spec['run']}.npz", **out)
    np.savez(T.DERIVED / f"params-{spec['run']}.npz", **export_numpy_params(model))
    meta = {"run": spec["run"], "which": a.which, "checkpoint": str(ck_path), "checkpoint_sha256": sha, "epoch": ck.get("epoch"),
            "val_select_per": ck.get("val_per"), "lookahead_bins": las, "n_items": len(items), "model_config": ck["model_config"],
            "device": dev, "limit": a.limit}
    (T.DERIVED / f"decode-{spec['run']}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
