"""GRU-CTC phoneme decoder for T12 (M3-27). Our own code (no third-party code copied).

Detached GPU job with checkpoints (latest.pt every few minutes, best.pt on a
better validation PER) and resume. Data: the derived per-session npz files of
prep.py (decoder-train and decoder-validation parts only; the trust pool is
never loaded here).

Run (detached; see HANDOFF.md):
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -u experiments/2026-11-13-confirmatory-t12/train_decoder.py [--resume]
Stop: create <run_dir>/stop (clean stop after the current epoch) or kill pid.txt.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
DC = CONFIG["decoder"]
DERIVED = Path(CONFIG["derived_dir"])
RUN = Path(CONFIG["run_dir"])
N_OUT = 41

torch.backends.cudnn.enabled = False  # MIOpen GRU backward fails on this ROCm build (see results.md)


def causal_kernel(sd: float) -> torch.Tensor:
    w = int(math.ceil(3 * sd))
    t = torch.arange(w + 1, dtype=torch.float32)  # 0 = current bin, w = oldest
    k = torch.exp(-0.5 * (t / sd) ** 2)
    k = k / k.sum()
    return k.flip(0)  # conv1d order: oldest .. current


class GRUDecoder(nn.Module):
    def __init__(self, n_sessions: int, n_in: int = 512, hidden: int = 512, layers: int = 5, dropout: float = 0.4,
                 patch: int = 14, stride: int = 4, smooth_sd: float = 2.0) -> None:
        super().__init__()
        self.patch, self.stride, self.n_in = patch, stride, n_in
        self.day_W = nn.Parameter(torch.eye(n_in).repeat(n_sessions, 1, 1))
        self.day_b = nn.Parameter(torch.zeros(n_sessions, n_in))
        self.register_buffer("kern", causal_kernel(smooth_sd))
        self.grus = nn.ModuleList([nn.GRU(n_in * patch if i == 0 else hidden, hidden, 1, batch_first=True)
                                   for i in range(layers)])
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(hidden, N_OUT)

    def n_frames(self, T: torch.Tensor) -> torch.Tensor:
        return torch.clamp((T - self.patch) // self.stride + 1, min=0)

    def forward(self, x: torch.Tensor, sess: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        k = self.kern.numel()
        xs = F.pad(x.transpose(1, 2), (k - 1, 0))  # causal
        xs = F.conv1d(xs, self.kern.view(1, 1, -1).repeat(C, 1, 1), groups=C).transpose(1, 2)
        xs = F.softsign(torch.einsum("btc,bcd->btd", xs, self.day_W[sess]) + self.day_b[sess].unsqueeze(1))
        xs = xs.unfold(1, self.patch, self.stride)  # B, T', C, patch
        xs = xs.permute(0, 1, 3, 2).reshape(B, xs.shape[1], self.patch * C)
        y = xs
        for g in self.grus:
            y, _ = g(y)
            y = self.drop(y)
        return self.out(y)  # logits B, T', 41


def load_parts(parts: tuple[str, ...]):
    """Items (session index, X float32, targets) with known phonemes, for the named parts."""
    sessions = sorted(p.stem for p in DERIVED.glob("t12.*.npz"))
    data = {p: [] for p in parts}
    for si, s in enumerate(sessions):
        z = np.load(DERIVED / f"{s}.npz")
        for p in parts:
            known = z[f"{p}_known"]
            for i in range(int(z[f"{p}_n"])):
                if not known[i]:
                    continue
                ph = z[f"{p}_ph{i}"].astype(np.int64)
                X = z[f"{p}_X{i}"]  # float16 in RAM
                if len(ph) == 0 or (X.shape[0] - DC["patch"]) // DC["stride"] + 1 < len(ph):
                    continue
                data[p].append((si, X, ph))
    return sessions, data


def batches(items, bs: int, rng: np.random.Generator | None):
    order = np.arange(len(items)) if rng is None else rng.permutation(len(items))
    # bucket by length inside chunks of 20 batches to cut padding
    chunks = [order[i:i + bs * 20] for i in range(0, len(order), bs * 20)]
    for ch in chunks:
        ch = sorted(ch, key=lambda j: items[j][1].shape[0])
        bl = [ch[i:i + bs] for i in range(0, len(ch), bs)]
        if rng is not None:
            rng.shuffle(bl)
        for b in bl:
            yield [items[j] for j in b]


def collate(b, dev, train: bool, rng: np.random.Generator | None):
    T = max(x[1].shape[0] for x in b)
    X = np.zeros((len(b), T, DC["n_in"]), np.float32)
    for i, (_, x, _) in enumerate(b):
        X[i, :x.shape[0]] = x
    X = torch.from_numpy(X).to(dev)
    if train:
        X = X + DC["white_noise_sd"] * torch.randn_like(X) + DC["offset_sd"] * torch.randn(len(b), 1, DC["n_in"], device=dev)
    sess = torch.tensor([x[0] for x in b], device=dev)
    lens = torch.tensor([x[1].shape[0] for x in b], device=dev)
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
def evaluate(model, items, dev) -> dict:
    model.eval()
    ed = n = 0
    loss_sum = 0.0
    for b in batches(items, 32, None):
        X, sess, lens, tg, tl = collate(b, dev, False, None)
        lg = model(X, sess)
        fl = model.n_frames(lens)
        lp = lg.log_softmax(-1)
        loss_sum += float(F.ctc_loss(lp.transpose(0, 1), tg, fl, tl, blank=0, reduction="sum", zero_infinity=True))
        lpn = lp.cpu().numpy()
        for i, (_, _, ph) in enumerate(b):
            hyp = greedy(lpn[i, :int(fl[i])])
            ed += edit(list(ph), hyp)
            n += len(ph)
    model.train()
    return {"per": ed / max(1, n), "loss": loss_sum / max(1, len(items))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "pid.txt").write_text(str(os.getpid()))
    logf = open(RUN / "train.log", "a", encoding="utf-8")

    def log(*a):
        logf.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(map(str, a)) + "\n")
        logf.flush()

    sys.path.insert(0, str(HERE.parents[1] / "src"))
    try:
        from fidetype.utils.power import set_keep_awake
        set_keep_awake(True)
    except Exception:  # noqa: BLE001
        pass
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    sessions, data = load_parts(("train", "val"))
    tr, va = data["train"], data["val"]
    log(f"start dev={dev} sessions={len(sessions)} train={len(tr)} val={len(va)} config={json.dumps(DC)}")
    torch.manual_seed(DC["seed"])
    rng = np.random.default_rng(DC["seed"])
    model = GRUDecoder(len(sessions), DC["n_in"], DC["hidden"], DC["gru_layers"], DC["dropout"], DC["patch"],
                       DC["stride"], DC["smooth_sd_bins"]).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=DC["lr"], weight_decay=DC["weight_decay"])
    steps_per_epoch = math.ceil(len(tr) / DC["batch"])
    total = steps_per_epoch * DC["max_epochs"]

    def lr_at(step):
        if step < DC["warmup_steps"]:
            return DC["lr"] * (step + 1) / DC["warmup_steps"]
        return DC["lr"] * 0.5 * (1 + math.cos(math.pi * min(1.0, (step - DC["warmup_steps"]) / max(1, total - DC["warmup_steps"]))))

    state = {"epoch": 0, "step": 0, "best_per": float("inf"), "best_epoch": -1, "bad": 0}
    if args.resume and (RUN / "latest.pt").exists():
        ck = torch.load(RUN / "latest.pt", map_location=dev, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        state = ck["state"]
        rng = np.random.default_rng([DC["seed"], state["epoch"], state["step"]])
        log(f"resumed {state}")
    status = lambda s: (RUN / "status.json").write_text(json.dumps({**state, "status": s, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}))  # noqa: E731
    last_ck = time.time()

    def save_latest():
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "state": state, "sessions": sessions, "config": DC},
                   RUN / "latest.tmp")
        os.replace(RUN / "latest.tmp", RUN / "latest.pt")

    status("running")
    while state["epoch"] < DC["max_epochs"]:
        t0 = time.time()
        tot, nb = 0.0, 0
        ep_rng = np.random.default_rng([DC["seed"], state["epoch"]])
        for b in batches(tr, DC["batch"], ep_rng):
            for g in opt.param_groups:
                g["lr"] = lr_at(state["step"])
            X, sess, lens, tg, tl = collate(b, dev, True, ep_rng)
            lp = model(X, sess).log_softmax(-1)
            loss = F.ctc_loss(lp.transpose(0, 1), tg, model.n_frames(lens), tl, blank=0, reduction="mean", zero_infinity=True)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            opt.step()
            state["step"] += 1
            tot += float(loss)
            nb += 1
            if time.time() - last_ck > 60 * DC["checkpoint_minutes"]:
                save_latest()  # mid-epoch: a resume restarts this epoch
                last_ck = time.time()
        state["epoch"] += 1
        ev = evaluate(model, va, dev)
        rec = {"epoch": state["epoch"], "train_loss": tot / max(1, nb), "val_per": ev["per"], "val_loss": ev["loss"],
               "lr": lr_at(state["step"]), "sec": round(time.time() - t0, 1)}
        with open(RUN / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if ev["per"] < state["best_per"]:
            state.update(best_per=ev["per"], best_epoch=state["epoch"], bad=0)
            torch.save({"model": model.state_dict(), "sessions": sessions, "config": DC, "epoch": state["epoch"],
                        "val_per": ev["per"]}, RUN / "best.pt")
        else:
            state["bad"] += 1
        save_latest()
        last_ck = time.time()
        log(json.dumps(rec), f"best {state['best_per']:.4f}@{state['best_epoch']}")
        status("running")
        if state["bad"] >= DC["patience"]:
            status("early_stopped")
            log("early stop")
            return
        if (RUN / "stop").exists():
            status("stopped")
            log("stop file")
            return
    status("done")
    log("done")


if __name__ == "__main__":
    main()
