r"""CPU decode of a T15 part with a trained M4-12 / M4-13 checkpoint (L 0). Our own code (same maths as
experiments/2026-11-15-m4-13-long-train/decode.py, which writes only to derived/m4-13; this script writes only to
derived/trust-reruns-m4-13).

Why CPU: the P11-01 waiter starts GPU training on the same DONE marker as this queue. One GPU job at a time, so the
extra decode (val_select, for calibration) runs on the CPU. The GPU is hidden from torch (HIP/CUDA_VISIBLE_DEVICES=-1).

Streams one session at a time (RAM: one session of features + the model), writes one part file per session
(resume: done sessions are skipped), then merges them into
  OUT/logprobs-<run>-<part>.npz   keys "<session>|<part>|<i>|L0"  (float32 log-softmax, valid frames only)
  OUT/decode-<run>-<part>.json    checkpoint SHA-256, step, config, device, seconds

Run (repo root, CPU torch venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe -u experiments/2026-11-17-trust-reruns-m4-13/decode_cpu.py
      --run m4-13-long0 --part val_select [--limit N] [--out DIR]
"""

from __future__ import annotations

import os

os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
D_IN = Path("C:/Users/zhang/bci-data/derived/m4-01-02-lookahead")  # READ ONLY
RUNS = Path("C:/Users/zhang/bci-data/runs")  # READ ONLY
OUT = Path("C:/Users/zhang/bci-data/derived/trust-reruns-m4-13")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="m4-13-long0")
    ap.add_argument("--ckpt", default="best.pt")
    ap.add_argument("--part", default="val_select", choices=["val_select", "val_eval"])
    ap.add_argument("--limit", type=int, default=0, help="items per session (smoke test only)")
    ap.add_argument("--sessions", type=int, default=0, help="first N sessions only (smoke test only)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    assert "m4-13" != a.out.name and "m4-01-02-lookahead" != a.out.name, "never write into a foreign folder"
    import torch

    torch.set_num_threads(a.threads)
    torch.backends.cudnn.enabled = False
    assert not torch.cuda.is_available(), "GPU must stay hidden"
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, build_torch_model

    t0 = time.time()
    ck_path = RUNS / a.run / a.ckpt
    sha = hashlib.sha256(ck_path.read_bytes()).hexdigest()
    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    cfg = LookaheadGRUConfig(**ck["model_config"])
    model = build_torch_model(cfg)
    model.load_state_dict(ck["model"])
    model.eval()
    step = ck.get("step", ck.get("epoch"))
    val_per = ck.get("val_per")
    del ck
    la = 0
    parts = a.out / f"parts-{a.run}-{a.part}-{sha[:12]}"
    parts.mkdir(parents=True, exist_ok=True)
    sessions = json.loads((D_IN / "sessions.json").read_text(encoding="utf-8"))
    if a.sessions:
        sessions = sessions[: a.sessions]
    n_items = 0
    for si, s in enumerate(sessions):
        pf = parts / f"{si:02d}-{s}.npz"
        if pf.exists():
            n_items += len(np.load(pf).files)
            continue
        z = np.load(D_IN / f"{s}.npz")
        n = int(z[f"{a.part}_n"]) if f"{a.part}_n" in z else 0
        items = [(i, z[f"{a.part}_X{i}"]) for i in range(n) if bool(z[f"{a.part}_known"][i])]
        if a.limit:
            items = items[: a.limit]
        out = {}
        order = sorted(range(len(items)), key=lambda j: items[j][1].shape[0])
        with torch.no_grad():
            for b0 in range(0, len(order), 8):
                idx = order[b0:b0 + 8]
                Tm = max(items[j][1].shape[0] for j in idx)
                X = np.zeros((len(idx), Tm, 512), np.float32)
                for r, j in enumerate(idx):
                    X[r, :items[j][1].shape[0]] = items[j][1]
                lens = torch.tensor([items[j][1].shape[0] for j in idx])
                sess = torch.full((len(idx),), si, dtype=torch.long)
                lp = model(torch.from_numpy(X), sess, la, lens).log_softmax(-1).numpy()
                nf = model.n_frames(lens).numpy()
                for r, j in enumerate(idx):
                    out[f"{s}|{a.part}|{items[j][0]}|L{la}"] = lp[r, :int(nf[r])].astype(np.float32)
        tmp = pf.with_name(pf.stem + ".tmp.npz")
        np.savez(tmp, **out)
        tmp.replace(pf)
        n_items += len(out)
        print(f"{time.strftime('%H:%M:%S')} session {si + 1}/{len(sessions)} {s}: {len(out)} items, "
              f"{time.time() - t0:.0f} s", flush=True)
    merged = {}
    for pf in sorted(parts.glob("*.npz")):
        if pf.name.endswith(".tmp.npz"):
            continue
        z = np.load(pf)
        merged.update({k: z[k] for k in z.files})
    dst = a.out / f"logprobs-{a.run}-{a.part}.npz"
    tmp = dst.with_name(dst.stem + ".tmp.npz")
    np.savez(tmp, **merged)
    tmp.replace(dst)
    meta = {"run": a.run, "checkpoint": str(ck_path), "checkpoint_sha256": sha, "step": step,
            "val_select_per": val_per, "part": a.part, "lookahead_bins": [la], "n_items": len(merged),
            "model_config": cfg.to_dict() if hasattr(cfg, "to_dict") else None, "device": "cpu",
            "threads": a.threads, "limit": a.limit, "sessions": a.sessions or None,
            "seconds": round(time.time() - t0, 1), "script": "experiments/2026-11-17-trust-reruns-m4-13/decode_cpu.py"}
    (a.out / f"decode-{a.run}-{a.part}.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("run", "part", "n_items", "step", "seconds")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
