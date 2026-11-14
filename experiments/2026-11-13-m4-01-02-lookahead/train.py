"""Train the lookahead GRU-CTC decoder on T15 (M4-01). Our own code (extends the M3-28 trainer).

Detached GPU job. latest.pt every few minutes (mid-epoch too), best.pt on a better
val_select PER, resume from latest.pt. 4 CPU threads, below-normal priority.

Run (repo root, detached; see HANDOFF.md):
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -u experiments/2026-11-13-m4-01-02-lookahead/train.py --which shared|dedicated_0|dedicated_25 [--resume]
Stop: create <run_dir>/stop (clean stop after the epoch) or kill pid.txt.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t15 as T  # noqa: E402

T.set_threads(4)
T.below_normal_priority()

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from fidetype.decoders.lookahead_gru import build_torch_model  # noqa: E402

torch.set_num_threads(4)
torch.backends.cudnn.enabled = False  # MIOpen GRU backward fails on this ROCm build (M3-28 results.md)
TC = dict(T.CONFIG["train"])
PAD_BINS = 100


def batches(items, bs: int, rng: np.random.Generator | None, max_bins: int | None = None):
    """Length-bucketed batches. ``max_bins``: cap on batch_size x padded length (keeps GPU memory flat;
    a 2,500-bin batch of 64 made the ROCm/Windows allocator slow for all later steps)."""
    order = np.arange(len(items)) if rng is None else rng.permutation(len(items))
    chunks = [order[i:i + bs * 20] for i in range(0, len(order), bs * 20)]
    for ch in chunks:
        ch = sorted(ch, key=lambda j: items[j][1].shape[0])
        bl, cur = [], []
        for j in ch:
            n = items[j][1].shape[0]
            padded = int(math.ceil(n / PAD_BINS) * PAD_BINS)
            if cur and (len(cur) >= bs or (max_bins and (len(cur) + 1) * padded > max_bins)):
                bl.append(cur)
                cur = []
            cur.append(j)
        if cur:
            bl.append(cur)
        if rng is not None:
            rng.shuffle(bl)
        for b in bl:
            yield [items[j] for j in b]


def collate(b, dev, train: bool):
    Tm = max(x[1].shape[0] for x in b)
    Tm = int(math.ceil(Tm / PAD_BINS) * PAD_BINS)  # few distinct shapes: new shapes are slow on ROCm/Windows (allocator)
    X = np.zeros((len(b), Tm, 512), np.float32)
    for i, x in enumerate(b):
        X[i, :x[1].shape[0]] = x[1]
    X = torch.from_numpy(X).to(dev)
    lens = torch.tensor([x[1].shape[0] for x in b], device=dev)
    if train:
        noise = TC["white_noise_sd"] * torch.randn_like(X) + TC["offset_sd"] * torch.randn(len(b), 1, 512, device=dev)
        valid = (torch.arange(Tm, device=dev)[None, :] < lens[:, None]).unsqueeze(-1)
        X = X + noise * valid  # padding stays zero (the lookahead branch masks it anyway)
    sess = torch.tensor([x[0] for x in b], device=dev)
    tg = torch.cat([torch.from_numpy(x[2]) for x in b]).to(dev)
    tl = torch.tensor([len(x[2]) for x in b], device=dev)
    return X, sess, lens, tg, tl


def edit(a, b) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[-1]


def greedy(lp: np.ndarray) -> list[int]:
    a = lp.argmax(-1)
    out, prev = [], -1
    for t in a:
        if t != prev and t != 0:
            out.append(int(t))
        prev = t
    return out


@torch.no_grad()
def evaluate(model, items, dev, la: int) -> dict:
    model.eval()
    ed = n = 0
    loss_sum = 0.0
    for b in batches(items, 32, None, TC["max_batch_bins"]):
        X, sess, lens, tg, tl = collate(b, dev, False)
        lp = model(X, sess, la, lens).log_softmax(-1)
        fl = model.n_frames(lens)
        loss_sum += float(F.ctc_loss(lp.transpose(0, 1), tg, fl, tl, blank=0, reduction="sum", zero_infinity=True))
        lpn = lp.cpu().numpy()
        for i, x in enumerate(b):
            ed += edit(list(x[2]), greedy(lpn[i, :int(fl[i])]))
            n += len(x[2])
    model.train()
    return {"per": ed / max(1, n), "loss": loss_sum / max(1, len(items))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True, choices=sorted(T.CONFIG["runs"]))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-epochs", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None, help="smoke test: items per part")
    args = ap.parse_args()
    spec = T.CONFIG["runs"][args.which]
    run = T.RUNS / spec["run"]
    run.mkdir(parents=True, exist_ok=True)
    if args.max_epochs:
        TC["max_epochs"] = args.max_epochs
    (run / "pid.txt").write_text(str(os.getpid()))
    logf = open(run / "train.log", "a", encoding="utf-8")

    def log(*a):
        logf.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(map(str, a)) + "\n")
        logf.flush()

    try:
        from fidetype.utils.power import set_keep_awake
        set_keep_awake(True)
    except Exception:  # noqa: BLE001
        pass
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    sessions = T.sessions()
    tr = T.load_part("train", args.limit)
    va = T.load_part("val_select", args.limit)
    tr = [x for x in tr if (x[1].shape[0] - 14) // 4 + 1 >= len(x[2])]
    cfg = T.model_config(len(sessions))
    la_spec = spec["lookahead_bins"]
    la_choices = T.LA_BINS if la_spec == "sample" else [int(la_spec)]
    eval_las = TC["eval_lookahead_bins"] if la_spec == "sample" else [int(la_spec)]
    log(f"start dev={dev} which={args.which} sessions={len(sessions)} train={len(tr)} val_select={len(va)} "
        f"la_choices={la_choices} model={json.dumps(cfg.to_dict())} train={json.dumps(TC)}")
    torch.manual_seed(TC["seed"])
    model = build_torch_model(cfg).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=TC["lr"], weight_decay=TC["weight_decay"])
    spe = sum(1 for _ in batches(tr, TC["batch"], np.random.default_rng(0), TC["max_batch_bins"]))
    total = spe * TC["max_epochs"]

    def lr_at(step):
        if step < TC["warmup_steps"]:
            return TC["lr"] * (step + 1) / TC["warmup_steps"]
        return TC["lr"] * 0.5 * (1 + math.cos(math.pi * min(1.0, (step - TC["warmup_steps"]) / max(1, total - TC["warmup_steps"]))))

    state = {"epoch": 0, "step": 0, "best_per": float("inf"), "best_epoch": -1, "bad": 0, "batch_in_epoch": 0}
    if args.resume and (run / "latest.pt").exists():
        ck = torch.load(run / "latest.pt", map_location=dev, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        state = ck["state"]
        log(f"resumed {state}")

    def status(s):
        (run / "status.json").write_text(json.dumps({**state, "status": s, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}))

    def save_latest():
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "state": state, "sessions": sessions,
                    "model_config": cfg.to_dict(), "train_config": TC, "which": args.which}, run / "latest.tmp")
        os.replace(run / "latest.tmp", run / "latest.pt")

    last_ck = time.time()
    status("running")
    while state["epoch"] < TC["max_epochs"]:
        t0 = time.time()
        tot, nb = 0.0, 0
        ep_rng = np.random.default_rng([TC["seed"], state["epoch"]])
        for bi, b in enumerate(batches(tr, TC["batch"], ep_rng, TC["max_batch_bins"])):
            la = int(ep_rng.choice(la_choices))  # drawn for every batch (keeps the RNG stream equal on resume)
            if bi < state["batch_in_epoch"]:
                continue  # resume inside an epoch: skip the batches already done
            for g in opt.param_groups:
                g["lr"] = lr_at(state["step"])
            X, sess, lens, tg, tl = collate(b, dev, True)
            lp = model(X, sess, la, lens).log_softmax(-1)
            loss = F.ctc_loss(lp.transpose(0, 1), tg, model.n_frames(lens), tl, blank=0, reduction="mean", zero_infinity=True)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            opt.step()
            state["step"] += 1
            state["batch_in_epoch"] = bi + 1
            tot += float(loss)
            nb += 1
            if time.time() - last_ck > 60 * TC["checkpoint_minutes"]:
                save_latest()
                last_ck = time.time()
                status("running")
        state["epoch"] += 1
        state["batch_in_epoch"] = 0
        evs = {la: evaluate(model, va, dev, la) for la in eval_las}
        score = float(np.mean([e["per"] for e in evs.values()]))
        rec = {"epoch": state["epoch"], "train_loss": tot / max(1, nb), "val_per": {str(k): v["per"] for k, v in evs.items()},
               "val_loss": {str(k): v["loss"] for k, v in evs.items()}, "score": score, "lr": lr_at(state["step"]),
               "sec": round(time.time() - t0, 1)}
        with open(run / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if score < state["best_per"]:
            state.update(best_per=score, best_epoch=state["epoch"], bad=0)
            torch.save({"model": model.state_dict(), "sessions": sessions, "model_config": cfg.to_dict(), "train_config": TC,
                        "which": args.which, "epoch": state["epoch"], "val_per": rec["val_per"]}, run / "best.pt")
        else:
            state["bad"] += 1
        save_latest()
        last_ck = time.time()
        log(json.dumps(rec), f"best {state['best_per']:.4f}@{state['best_epoch']}")
        status("running")
        if state["bad"] >= TC["patience"]:
            status("early_stopped")
            log("early stop")
            return
        if (run / "stop").exists():
            status("stopped")
            log("stop file")
            return
    status("done")
    log("done")


if __name__ == "__main__":
    main()
