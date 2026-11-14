"""P12 intent evaluation: time-shuffled EMG control for the Toronto sEMG key-choice recast (CPU only).

For the session-calibrated runs ``calib_a`` and ``calib_b`` (M6-07,
``experiments/2026-11-11-emg-toronto``) this script re-runs the trained
CNN on its own predict windows:

1. ``clean``: the windows as they are (a check: the logits must equal the
   stored ``preds.npz`` up to float rounding);
2. ``timeshuffled``: in each 0.5 s crop the time samples are permuted
   (one permutation per window, the same for all 16 channels; seed 20261113).
   This keeps the per-channel amplitude distribution and breaks the
   temporal shape of the muscle activity (the "frame-shuffled" control).

CPU only (the GPU is in use by another job): 2 threads, below-normal priority.
Output (outside the repo, derived data): ``C:/Users/zhang/bci-data/runs/p12-intent/<run>_controls.npz``.

Run (repo root)::

    C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -I experiments/2026-11-13-p12-intent-events/shuffle_control.py
"""

from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["HIP_VISIBLE_DEVICES"] = ""

import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.set_num_threads(2)
if sys.platform == "win32":
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TRAIN = REPO / "experiments" / "2026-11-11-emg-toronto" / "train.py"
OUT = Path("C:/Users/zhang/bci-data/runs/p12-intent")
SEED = 20261113


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with (OUT / "shuffle_control.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("emg_train", TRAIN)
    tr = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(tr)
    dev = torch.device("cpu")
    log("loading windows (CPU, 2 threads, below-normal priority)")
    d = np.load(tr.CACHE / "windows.npz", allow_pickle=False)
    X = d["X"]
    log(f"X {X.shape} {X.dtype}")
    rng = np.random.default_rng(SEED)
    for run in ("calib_a", "calib_b"):
        dst = OUT / f"{run}_controls.npz"
        if dst.exists():
            log(f"{run}: done before, skip")
            continue
        rdir = tr.RUNS / run
        pr = np.load(rdir / "preds.npz")
        idx = pr["idx"]
        model = tr.ConvNet().to(dev)
        model.load_state_dict(torch.load(rdir / "best.pt", map_location=dev))
        model.eval()
        clean, shuf = [], []
        total = X.shape[2]
        c0 = (total - tr.CROP) // 2
        with torch.no_grad():
            for i in range(0, len(idx), 512):
                xb = torch.from_numpy(X[idx[i:i + 512], :, c0:c0 + tr.CROP].astype(np.float32))
                clean.append(model(xb).numpy())
                perm = np.stack([rng.permutation(tr.CROP) for _ in range(xb.shape[0])])
                xs = torch.gather(xb, 2, torch.from_numpy(perm)[:, None, :].expand(-1, xb.shape[1], -1))
                shuf.append(model(xs).numpy())
        clean_l, shuf_l = np.concatenate(clean), np.concatenate(shuf)
        diff = float(np.max(np.abs(clean_l - pr["logits"])))
        log(f"{run}: n {len(idx)}, max |clean - stored| = {diff:.2e}")
        np.savez(dst, idx=idx, clean=clean_l, timeshuffled=shuf_l, max_abs_diff=diff)
    (OUT / "shuffle_control.done").write_text(json.dumps({"finished": time.strftime("%Y-%m-%d %H:%M:%S")}))
    log("done")


if __name__ == "__main__":
    main()
