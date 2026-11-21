"""P15-25 stage `logits`: log-probs of the 41 E1a `final.pt` models on the Willett test (and val) sentences.

Runs in the ROCm venv (torch). GPU if available. Our own code (Apache-2.0); it imports the P15-08 modules
(``e1``, ``run``) read only and writes only to ``C:/Users/zhang/bci-data/derived/p15-25/lp/``.

Per run folder ``lp/<run>/``: ``<split>.npy`` = float32 (sum of frames, 98) log-probs, sentences concatenated in
split order; ``<split>.json`` = offsets, sentence indices, model step. Splits: ``test`` (all runs), ``val`` (Fv
tuning runs), ``shuf`` (C1 runs: test input with frames permuted as in E1a ``eval_set``, ``default_rng(12345)``).

    C:/venvs/fidetype-rocm/Scripts/python.exe -I experiments/2026-11-20-p15-25-e1-same-lm/logits.py [--smoke]
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E1A = REPO / "experiments" / "2026-11-19-p15-08-e1-cross-body"
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402


def _load(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def forward_set(torch, model, store, idx: list[int], device: str, max_frames: int,
                shuffle_seed: int | None = None) -> list[np.ndarray]:
    """E1a ``eval_set`` batching (causal model: post-padding does not change earlier outputs); returns the
    log-probs of each sentence in ``idx`` order. The shuffle permutation equals E1a's (one rng, idx order)."""
    e1 = sys.modules["e1"]
    model.eval()
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    xs = {}
    for i in idx:
        x = store.x[i]
        xs[i] = x[rng.permutation(len(x))] if rng is not None else x
    order = sorted(idx, key=lambda i: store.length[i])
    out: dict[int, np.ndarray] = {}
    k = 0
    with torch.no_grad():
        while k < len(order):
            grp = [order[k]]
            k += 1
            while k < len(order) and store.length[order[k]] * (len(grp) + 1) <= max_frames:
                grp.append(order[k])
                k += 1
            b = e1.collate([(xs[i], store.tgt[i], store.meta[i]["session"]) for i in grp])
            lp = model(torch.from_numpy(b["x"]).to(device), torch.from_numpy(b["sess"]).to(device)).cpu().numpy()
            for j, i in enumerate(grp):
                out[i] = np.ascontiguousarray(lp[j, :store.length[i]], np.float32)
    return [out[i] for i in idx]


def save_split(d: Path, split: str, arrs: list[np.ndarray], idx: list[int], step: int) -> None:
    off = np.concatenate([[0], np.cumsum([len(a) for a in arrs])]).astype(np.int64)
    tmp = d / f"{split}.tmp.npy"
    np.save(tmp, np.concatenate(arrs, axis=0).astype(np.float32))
    os.replace(tmp, d / f"{split}.npy")
    C.save_json({"offsets": off.tolist(), "idx": list(map(int, idx)), "step": int(step)}, d / f"{split}.json")


def main(argv: list[str]) -> int:
    smoke = "--smoke" in argv
    import torch

    e1 = _load("e1", E1A / "e1.py")
    R = _load("p1508run", E1A / "run.py")
    cfg = C.config()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ctx = R.ctx_from_config(E1A / "config.json", C.E1A_OUT, dev)
    C.log(f"logits: start device {dev} torch {torch.__version__} smoke={smoke}")
    store = R.WillettStore(C.E1A_OUT / "willett")
    test_idx = list(store.splits["test"])
    val_idx = list(store.splits["val"])
    runs = C.all_runs()
    tune_runs = set(C.tune_runs(cfg))
    c1_runs = set(C.c1_runs())
    if smoke:
        runs, test_idx, val_idx = ["E-ball-s0"], test_idx[:2], val_idx[:1]
    t0 = time.time()
    for n, name in enumerate(runs, 1):
        if C.stop_requested():
            C.log("logits: STOP file seen; exit")
            return 3
        d = (C.OWN / ("smoke-lp" if smoke else "lp") / name)
        d.mkdir(parents=True, exist_ok=True)
        if (d / "DONE.json").exists():
            continue
        ck = torch.load(C.E1A_OUT / "runs" / name / cfg["checkpoint"], map_location="cpu", weights_only=True)
        model = e1.XBody(ctx.trunk, "willett", store.n_sessions)
        model.load_state_dict(ck["model"])
        model.to(dev)
        step = int(ck.get("step", -1))
        jobs = [("test", test_idx, None)]
        if name in tune_runs or smoke:
            jobs.append(("val", val_idx, None))
        if name in c1_runs or smoke:
            jobs.append(("shuf", test_idx, int(cfg["c1_shuffle_seed"])))
        for split, idx, sh in jobs:
            if (d / f"{split}.json").exists():
                continue
            arrs = forward_set(torch, model, store, idx, dev, ctx.ft.max_frames, shuffle_seed=sh)
            save_split(d, split, arrs, idx, step)
        C.save_json({"run": name, "step": step, "splits": [j[0] for j in jobs],
                     "licence": json.loads((C.E1A_OUT / "runs" / name / "licence.json").read_text(encoding="utf-8"))},
                    d / "DONE.json")
        del model
        C.log(f"logits: {n}/{len(runs)} {name} step {step} ({time.time() - t0:.0f} s; peak {C.peak_mb():.0f} MB)")
    if not smoke:
        C.save_json({"runs": len(runs), "seconds": round(time.time() - t0, 1), "device": dev,
                     "peak_mb": C.peak_mb()}, C.OWN / "lp" / "DONE.json")
    C.log(f"logits: end ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
