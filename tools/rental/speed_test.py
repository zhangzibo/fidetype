"""One-hour GPU speed test for a rented (or local) machine. Our own code.

It times a fixed number of training steps of the T15 decoder recipe (the 115,000-step causal GRU-CTC
recipe of experiments/2026-11-15-m4-13-long-train, imported unchanged) and of the short "fit" steps
that the self-teaching replay uses (day layer + last GRU layer + output layer trainable). Then it
prints the projected GPU hours of two pre-registered plans:

  * experiments/2026-11-23-t15-calibration-holdout   (one 115,000-step retrain)
  * experiments/2026-11-23-e2-self-teaching-t15      (a 30,000-step base + 230,400 fit steps)

It writes no checkpoint and no data. The only output is one small JSON file (``--out``).

Usage (repo root):
  python tools/rental/speed_test.py --derived /data/t15-derived          # real T15 features
  python tools/rental/speed_test.py --synthetic                          # no data needed (shapes only)
  python tools/rental/speed_test.py --derived ... --max-sessions 10      # faster load, same model size

The measured part stops at ``--budget-min`` minutes (default 50) even if fewer steps ran; the
projection then uses the steps that ran. Read tools/rental/README.md first.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPE_DIR = REPO / "experiments" / "2026-11-15-m4-13-long-train"

# Local reference (measured, RX 7800 XT 16 GB, ROCm 7.2.1, torch 2.9.1, Windows): M4-13 mean 1.27 s per
# step at batch 64 over 115,000 steps = 40.56 h of training (experiments/2026-11-15-m4-13-long-train/results.md).
LOCAL_REF_S_PER_STEP = 1.27
LOCAL_REF_NAME = "RX 7800 XT (ROCm, Windows)"

# Step counts fixed in the two plans (change them only together with the plans).
PLANS = {
    "calibration_holdout": {
        "plan": "experiments/2026-11-23-t15-calibration-holdout/plan.md",
        "train_steps": 115_000,
        "fit_steps": 0,
        "overhead": 1.03,  # val_select evaluations every 5 % + final decode (M4-13: about 3 %)
    },
    "e2_self_teaching_t15": {
        "plan": "experiments/2026-11-23-e2-self-teaching-t15/plan.md",
        "train_steps": 30_000,  # base decoder on sessions S0-S7
        "fit_steps": 16 * 36 * (100 + 300) + 4 * 400,  # 16 trained runs x 36 sessions x (update-1 + nightly) + S8 grid
        "overhead": 1.10,  # forward passes of every stream item per version, check blocks, null controls
    },
}


def project_hours(s_train: float, s_fit: float, plan: dict) -> float:
    """GPU hours of one plan from the measured seconds per step."""
    if s_train < 0 or s_fit < 0:
        raise ValueError("seconds per step must be >= 0")
    sec = plan["train_steps"] * s_train + plan["fit_steps"] * s_fit
    return sec * plan["overhead"] / 3600.0


def speedup_vs_local(s_train: float) -> float:
    return LOCAL_REF_S_PER_STEP / s_train if s_train > 0 else math.inf


def synthetic_items(n: int, n_sessions: int, seed: int = 0, min_bins: int = 300, max_bins: int = 1500):
    """Random items with the T15 item layout (session, X float16 (T, 512), phoneme ids, key).

    T15 trials average about 935 bins (18.7 s); phonemes about 1 per 25 bins. Every item is CTC
    feasible: frames (T - 3 - 14) // 4 + 1 >= number of phonemes.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        T = int(rng.integers(min_bins, max_bins + 1))
        L = max(1, min(T // 25, (T - 3 - 14) // 4 + 1))
        X = rng.standard_normal((T, 512)).astype(np.float16)
        ph = rng.integers(1, 41, size=L).astype(np.int64)
        out.append((int(i % n_sessions), X, ph, f"synthetic|train|{i}"))
    return out


def fit_trainable_names(model) -> list[str]:
    """Freeze all but the day layers, the last GRU layer and the output layer (the replay "fit" step)."""
    last = len(model.grus) - 1
    keep = []
    for n, p in model.named_parameters():
        ok = n.startswith("day_") or n.startswith(f"grus.{last}.") or n.startswith("out.")
        p.requires_grad_(ok)
        if ok:
            keep.append(n)
    return keep


def _load_recipe():
    """Import the recipe modules unchanged (they set threads, priority and the ROCm cuDNN switch)."""
    sys.path.insert(0, str(RECIPE_DIR))
    sys.path.insert(0, str(REPO / "src"))
    import t15 as T  # noqa: E402
    import train as TR  # noqa: E402
    return T, TR


def _cudnn_choice(torch, mode: str) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    # auto: the recipe switches cuDNN off for ROCm (MIOpen GRU backward bug); a CUDA build can use it
    return bool(torch.cuda.is_available() and getattr(torch.version, "hip", None) is None)


def run(args) -> dict:
    T, TR = _load_recipe()
    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, build_torch_model

    torch.backends.cudnn.enabled = _cudnn_choice(torch, args.cudnn)
    torch.backends.cuda.matmul.allow_tf32 = bool(args.tf32)
    torch.backends.cudnn.allow_tf32 = bool(args.tf32)
    dev = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    t_start = time.time()
    budget_s = 60.0 * args.budget_min

    # --- data ---
    if args.synthetic:
        n_sessions = 45
        tr = synthetic_items(args.synthetic_items, n_sessions, seed=0,
                             min_bins=args.synthetic_min_bins, max_bins=args.synthetic_max_bins)
        data_note = f"synthetic ({len(tr)} items)"
    else:
        T.DERIVED = Path(args.derived)  # read only
        all_sessions = T.sessions()
        n_sessions = len(all_sessions)
        if args.max_sessions:
            sub = all_sessions[:args.max_sessions]
            orig = T.sessions
            T.sessions = lambda: sub
            try:
                tr = T.load_part("train")
            finally:
                T.sessions = orig
        else:
            tr = T.load_part("train")
        data_note = f"T15 derived features, {len(tr)} train items, {args.max_sessions or n_sessions} sessions"
    tc = TR.TC
    tr = [x for x in tr if (x[1].shape[0] - tc["random_cut_bins"] - 14) // 4 + 1 >= len(x[2])]
    load_s = time.time() - t_start

    # --- model (the recipe, or a tiny one for tests) ---
    if args.tiny:
        cfg = LookaheadGRUConfig(n_sessions=n_sessions, hidden=16, layers=2, patch=14, stride=4, la_max=25,
                                 la_proj=8, dropout=0.4)
    else:
        cfg = T.model_config(n_sessions)
    torch.manual_seed(0)
    model = build_torch_model(cfg).to(dev)
    TR.patch_model(model)
    la = 0
    n_params = sum(p.numel() for p in model.parameters())

    def sync():
        if dev == "cuda":
            torch.cuda.synchronize()

    def step_fn(opt, batch, rng, lr):
        for g in opt.param_groups:
            g["lr"] = lr
        opt.zero_grad()
        lv = 0.0
        for ch in TR.micro_chunks(batch):
            X, sess, lens, tg, tl = TR.collate(ch, dev, True, rng)
            lp = model(X, sess, la, lens).log_softmax(-1)
            loss = F.ctc_loss(lp.transpose(0, 1), tg, model.n_frames(lens).cpu(), tl.cpu(), blank=0,
                              reduction="mean", zero_infinity=True)
            w = len(ch) / len(batch)
            (loss * w).backward()
            lv += float(loss.detach()) * w
        nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], tc["grad_clip"])
        opt.step()
        return lv

    def timed(opt, make_batch, n_steps, warm, lr, stop_at):
        times, losses = [], []
        for k in range(warm + n_steps):
            if time.time() > stop_at and k > warm:
                break
            b, rng = make_batch(k)
            sync()
            t0 = time.time()
            lv = step_fn(opt, b, rng, lr)
            sync()
            if k >= warm:
                times.append(time.time() - t0)
                losses.append(lv)
        return times, losses

    # --- 1. full training step (recipe batches: bucket sampler, batch 64) ---
    if args.batch:
        tc["batch"] = args.batch
    TR._EPOCHS.clear()
    TR.bucket_batch.by_id = {id(x): x for x in tr}
    opt = torch.optim.AdamW(TR.param_groups(model), lr=tc["lr_max"], betas=(0.9, 0.999), eps=tc["adam_eps"])
    stop_train = t_start + budget_s * 0.65
    t_train, l_train = timed(opt, lambda k: TR.bucket_batch(tr, k), args.steps, args.warmup, tc["lr_max"], stop_train)

    # --- 2. fit step (one day's items, batch 32, partial unfreeze) ---
    names = fit_trainable_names(model)
    opt2 = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=3e-4, eps=tc["adam_eps"])
    by_day: dict = {}
    for x in tr:
        by_day.setdefault(int(x[0]), []).append(x)
    day_items = max(by_day.values(), key=len)
    frng = np.random.default_rng(1)

    def fit_batch(k):
        idx = frng.choice(len(day_items), min(args.fit_batch, len(day_items)), replace=False)
        return [day_items[i] for i in idx], np.random.default_rng([5, k])

    t_fit, l_fit = timed(opt2, fit_batch, args.fit_steps, args.warmup, 3e-4, t_start + budget_s)

    s_train = float(np.median(t_train)) if t_train else float("nan")
    s_fit = float(np.median(t_fit)) if t_fit else float("nan")
    mem = torch.cuda.max_memory_allocated() / 2**30 if dev == "cuda" else 0.0
    proj = {k: round(project_hours(s_train, s_fit, p), 2) for k, p in PLANS.items()} if t_train and t_fit else {}
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": platform.python_version(), "torch": torch.__version__,
        "cuda": getattr(torch.version, "cuda", None), "hip": getattr(torch.version, "hip", None),
        "device": dev, "device_name": torch.cuda.get_device_name(0) if dev == "cuda" else platform.processor(),
        "cudnn_enabled": torch.backends.cudnn.enabled, "tf32": bool(args.tf32),
        "cpu_count": os.cpu_count(), "data": data_note, "load_s": round(load_s, 1),
        "model_params": n_params, "tiny_model": bool(args.tiny),
        "train_steps_timed": len(t_train), "train_batch": tc["batch"],
        "s_per_step_train_median": s_train,
        "s_per_step_train_mean": float(np.mean(t_train)) if t_train else float("nan"),
        "train_loss_first_last": [l_train[0], l_train[-1]] if l_train else None,
        "fit_steps_timed": len(t_fit), "fit_batch": args.fit_batch, "fit_trainable": names,
        "s_per_step_fit_median": s_fit,
        "max_gpu_mem_gib": round(mem, 2),
        "speedup_vs_local_ref": round(speedup_vs_local(s_train), 2) if t_train else None,
        "local_ref": f"{LOCAL_REF_NAME}: {LOCAL_REF_S_PER_STEP} s/step",
        "projected_gpu_hours": proj,
        "projection_note": ("GPU part only. CPU parts (word decoding, LLM rescoring, calibration draws) are "
                            "estimated in the plans; they scale with cpu_count."),
        "wall_s": round(time.time() - t_start, 1),
    }


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--derived", default=os.environ.get("FIDETYPE_T15_DERIVED",
                                                        "C:/Users/zhang/bci-data/derived/m4-01-02-lookahead"))
    ap.add_argument("--synthetic", action="store_true", help="random items with T15 shapes (no data needed)")
    ap.add_argument("--synthetic-items", type=int, default=512)
    ap.add_argument("--synthetic-min-bins", type=int, default=300)
    ap.add_argument("--synthetic-max-bins", type=int, default=1500)
    ap.add_argument("--max-sessions", type=int, default=None, help="load only the first N sessions")
    ap.add_argument("--steps", type=int, default=1000, help="timed full training steps (after warm-up)")
    ap.add_argument("--fit-steps", type=int, default=1000, help="timed fit steps (after warm-up)")
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--batch", type=int, default=None, help="override the recipe batch (64)")
    ap.add_argument("--fit-batch", type=int, default=32)
    ap.add_argument("--budget-min", type=float, default=50.0, help="stop timing after this many minutes")
    ap.add_argument("--cudnn", choices=["auto", "on", "off"], default="auto")
    ap.add_argument("--tf32", action="store_true", help="allow TF32 matmuls (off in the plans)")
    ap.add_argument("--device", default=None, help="cuda or cpu (default: cuda if available)")
    ap.add_argument("--tiny", action="store_true", help="tests only: a tiny model, numbers mean nothing")
    ap.add_argument("--out", default="speed_test_result.json")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse(argv)
    r = run(args)
    Path(args.out).write_text(json.dumps(r, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("device_name", "cudnn_enabled", "s_per_step_train_median",
                                         "s_per_step_fit_median", "speedup_vs_local_ref", "projected_gpu_hours",
                                         "max_gpu_mem_gib", "wall_s")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
