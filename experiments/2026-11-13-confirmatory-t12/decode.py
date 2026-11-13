"""Stage decode: run the final decoder (best.pt) on the decoder-validation part and the
trust pool of every session. Writes log-probabilities (float16) outside the repo.
This stage computes no outcome on the trust pool.

Run (repo root): C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -u experiments/2026-11-13-confirmatory-t12/decode.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_decoder as TD  # noqa: E402


def main() -> None:
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ck_path = TD.RUN / "best.pt"
    sha = hashlib.sha256(ck_path.read_bytes()).hexdigest()
    ck = torch.load(ck_path, map_location=dev, weights_only=False)
    sessions = ck["sessions"]
    DC = ck["config"]
    model = TD.GRUDecoder(len(sessions), DC["n_in"], DC["hidden"], DC["gru_layers"], DC["dropout"], DC["patch"],
                          DC["stride"], DC["smooth_sd_bins"]).to(dev)
    model.load_state_dict(ck["model"])
    model.eval()
    out = {}
    with torch.no_grad():
        for si, s in enumerate(sessions):
            z = np.load(TD.DERIVED / f"{s}.npz")
            for p in ("val", "pool"):
                for i in range(int(z[f"{p}_n"])):
                    X = torch.from_numpy(z[f"{p}_X{i}"].astype(np.float32)).unsqueeze(0).to(dev)
                    if X.shape[1] < DC["patch"]:
                        X = torch.nn.functional.pad(X, (0, 0, 0, DC["patch"] - X.shape[1]))
                    lp = model(X, torch.tensor([si], device=dev)).log_softmax(-1)[0].cpu().numpy()
                    out[f"{s}|{p}|{i}"] = lp.astype(np.float32)
            print(s, flush=True)
    np.savez(TD.DERIVED / "logprobs.npz", **out)
    meta = {"checkpoint": str(ck_path), "checkpoint_sha256": sha, "epoch": ck["epoch"], "val_per_greedy": ck["val_per"],
            "n_streams": len(out), "config": DC}
    (TD.DERIVED / "logprobs-meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
