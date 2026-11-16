"""P15-01 base decoder: trunk + one day layer per base session (S0-S6), CPU only. Resumes from latest.pt.

Run (repo root, detached via launch_detached.py or directly):
  .venv/Scripts/python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      C:/venvs/fidetype-rocm/Scripts/python.exe -u experiments/2026-11-16-f1-e2-selfimprove-pilot/train_base.py
Stop: create <derived>/base/stop (clean stop after the current epoch).
"""

from __future__ import annotations

import json
import math
import time

import numpy as np
import torch

import common as C

OUT = C.OWN / "base"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "train.log"
TC = C.CONFIG["train"]


def day_batches(days: dict[int, list], bs: int, rng: np.random.Generator):
    """Batches with items of one day only (one day layer per batch), length-bucketed, shuffled."""
    bl = []
    for d, items in days.items():
        order = rng.permutation(len(items))
        for i in range(0, len(order), bs * 8):
            ch = sorted(order[i : i + bs * 8], key=lambda j: items[j]["X"].shape[0])
            bl += [(d, [items[j] for j in ch[k : k + bs]]) for k in range(0, len(ch), bs)]
    rng.shuffle(bl)
    return bl


def main() -> None:
    torch.manual_seed(TC["seed"])
    base = C.CONFIG["base_sessions"]
    train, val = {}, {}
    for k, si in enumerate(base):
        train[k] = [it for it in C.load_day(si, ("train",)) if it["ph"] is not None]
        val[k] = [it for it in C.load_day(si, ("val",)) if it["ph"] is not None]
    C.log(LOG, f"base sessions {base}: train {sum(map(len, train.values()))}, val {sum(map(len, val.values()))}")
    trunk = C.make_trunk()
    dayW = torch.nn.Parameter(torch.eye(C.C_IN).repeat(len(base), 1, 1))
    dayb = torch.nn.Parameter(torch.zeros(len(base), C.C_IN))
    params = list(trunk.parameters()) + [dayW, dayb]
    opt = torch.optim.AdamW(params, lr=TC["lr"], weight_decay=TC["weight_decay"])
    rng = np.random.default_rng(TC["seed"])
    n_per_epoch = len(day_batches(train, TC["batch"], np.random.default_rng(0)))
    total = n_per_epoch * TC["max_epochs"]

    def lr_at(step):
        if step < TC["warmup_steps"]:
            return TC["lr"] * (step + 1) / TC["warmup_steps"]
        return TC["lr"] * 0.5 * (1 + math.cos(math.pi * min(1.0, step / total)))

    state = {"epoch": 0, "step": 0, "best_per": math.inf, "bad": 0, "history": []}
    if (OUT / "latest.pt").exists():
        ck = torch.load(OUT / "latest.pt", map_location="cpu", weights_only=False)
        trunk.load_state_dict(ck["trunk"])
        with torch.no_grad():
            dayW.copy_(ck["dayW"])
            dayb.copy_(ck["dayb"])
        opt.load_state_dict(ck["opt"])
        state = ck["state"]
        rng = np.random.default_rng([TC["seed"], state["epoch"]])
        C.log(LOG, f"resumed at epoch {state['epoch']} step {state['step']} best {state['best_per']:.4f}")

    while state["epoch"] < TC["max_epochs"] and state["bad"] < TC["patience"]:
        if (OUT / "stop").exists():
            C.log(LOG, "stop file found")
            return
        t0 = time.time()
        trunk.train()
        tot = 0.0
        bl = day_batches(train, TC["batch"], rng)
        for d, items in bl:
            for g in opt.param_groups:
                g["lr"] = lr_at(state["step"])
            loss = C.ctc_loss(trunk, dayW[d], dayb[d], items, TC["noise"], True)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 5.0)
            opt.step()
            state["step"] += 1
            tot += float(loss)
        ed = n = 0
        for k in val:
            lps = C.log_probs(trunk, dayW[k].detach(), dayb[k].detach(), val[k])
            e, m = C.per_counts(lps, val[k])
            ed, n = ed + e, n + m
        per = ed / n
        state["epoch"] += 1
        state["history"].append({"epoch": state["epoch"], "loss": tot / len(bl), "val_per": per,
                                 "seconds": round(time.time() - t0, 1)})
        better = per < state["best_per"] - 1e-4
        if better:
            state["best_per"], state["bad"] = per, 0
            torch.save({"trunk": trunk.state_dict(), "dayW": dayW.detach().clone(), "dayb": dayb.detach().clone(),
                        "epoch": state["epoch"], "val_per": per, "config": C.CONFIG["model"]}, OUT / "best.pt")
        else:
            state["bad"] += 1
        torch.save({"trunk": trunk.state_dict(), "dayW": dayW.detach().clone(), "dayb": dayb.detach().clone(),
                    "opt": opt.state_dict(), "state": state}, OUT / "latest.pt")
        C.log(LOG, f"epoch {state['epoch']} loss {tot / len(bl):.4f} val PER {per:.4f}"
                   f"{' *' if better else ''} ({time.time() - t0:.0f}s)")
    (OUT / "DONE").write_text(json.dumps({"best_val_per": state["best_per"], "epochs": state["epoch"]}), encoding="utf-8")
    C.log(LOG, f"DONE best val PER {state['best_per']:.4f}")


if __name__ == "__main__":
    main()
