"""Toronto sEMG typing: train small key-press classifiers (GPU or CPU).

One process runs all runs in order (at most one heavy job). Each run
checkpoints every epoch (``latest.pt``) and resumes from it; a finished
run (``status.json`` = done) is skipped. Logs go to ``<runs>/train.log``.

Runs (27 classes: a-z, space; one window per key press, oracle timing):

- ``xsession``: train on day 1 (T1) of all 19 participants; predict day 2 (T2).
- ``xsession_linear``: same split; logistic regression on log-RMS features
  (16 channels x 10 bins of 50 ms).
- ``xsession_permuted``: same split; training labels permuted (control).
- ``calib_a`` / ``calib_b``: session-calibrated, cross-fitted. Train on T1
  plus the T2 recordings of one half (``a``: the first recording of each
  letter; ``b``: the later ones); predict the other half of T2.
- ``xsubject_f0`` .. ``f3``: 4 participant folds; train on both sessions
  of the other participants; predict both sessions of the fold.

For each run: ``preds.npz`` (window index, logits) for its predict set and
the logits of an all-zero input (control); ``metrics.json``.

Run (repo root, GPU venv; see launch.ps1 for the detached form):
    C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -I experiments/2026-11-11-emg-toronto/train.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from fidetype.utils.power import keep_awake  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CACHE = Path(CONFIG["cache"])
RUNS = Path(CONFIG["runs"])
TC = CONFIG["train"]
FS = 1000
CROP = int(round(CONFIG["crop_s"] * FS))
N_CLASSES = 27
LOGF = RUNS / "train.log"


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def h01(s: str) -> float:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


# --- data ----------------------------------------------------------------------


def load():
    d = np.load(CACHE / "windows.npz", allow_pickle=False)
    files = json.loads((CACHE / "files.json").read_text(encoding="utf-8"))
    return d["X"], d["label"].astype(np.int64), d["file_idx"], files


def splits(files, file_idx):
    """{run: (train_idx, val_idx, predict_idx)} over windows."""
    nf = len(files)
    part = np.array([f["participant"] for f in files])
    sess = np.array([f["session"] for f in files])
    order = np.array([f["order"] for f in files])
    is_val = np.array([h01("val:" + f["key"]) < TC["val_fraction"] for f in files])
    pids = sorted(set(part), key=lambda p: int(p[1:]))
    rng = np.random.default_rng(CONFIG["seed"])
    perm = rng.permutation(len(pids))
    k = CONFIG["xsubject_folds"]
    fold_of = {pids[j]: int(i % k) for i, j in enumerate(perm)}
    fold = np.array([fold_of[p] for p in part])

    def win(mask_f):
        return np.where(mask_f[file_idx])[0]

    out = {}
    t1, t2 = sess == "T1", sess == "T2"
    out["xsession"] = (win(t1 & ~is_val), win(t1 & is_val), win(t2))
    out["xsession_linear"] = out["xsession"]
    out["xsession_permuted"] = out["xsession"]
    first = t2 & (order == 1)
    later = t2 & (order >= 2)
    out["calib_a"] = (win((t1 | first) & ~is_val), win((t1 | first) & is_val), win(later))
    out["calib_b"] = (win((t1 | later) & ~is_val), win((t1 | later) & is_val), win(first))
    for f in range(k):
        tr = fold != f
        out[f"xsubject_f{f}"] = (win(tr & ~is_val), win(tr & is_val), win(fold == f))
    assert nf == len(part)
    return out, fold_of


# --- models --------------------------------------------------------------------


class ConvNet(nn.Module):
    def __init__(self, c_in: int = 16, n: int = N_CLASSES, dropout: float = 0.3) -> None:
        super().__init__()
        chans = [c_in, 64, 96, 128, 128]
        ks = [7, 5, 5, 3]
        layers = []
        for i in range(4):
            layers += [nn.Conv1d(chans[i], chans[i + 1], ks[i], stride=2, padding=ks[i] // 2, bias=False),
                       nn.BatchNorm1d(chans[i + 1]), nn.GELU()]
        self.body = nn.Sequential(*layers)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(2 * chans[-1], n)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.body(x)
        h = torch.cat([h.mean(dim=2), h.amax(dim=2)], dim=1)
        return self.head(self.drop(h))


def logrms_features(x: torch.Tensor, n_bins: int = 10) -> torch.Tensor:
    b, c, t = x.shape
    x = x[:, :, : (t // n_bins) * n_bins].reshape(b, c, n_bins, -1)
    return torch.log(x.pow(2).mean(dim=3) + 1e-4).reshape(b, c * n_bins)


class LinearNet(nn.Module):
    def __init__(self, c_in: int = 16, n: int = N_CLASSES, n_bins: int = 10) -> None:
        super().__init__()
        self.norm = nn.BatchNorm1d(c_in * n_bins, affine=False)
        self.head = nn.Linear(c_in * n_bins, n)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.norm(logrms_features(x)))


# --- training --------------------------------------------------------------------


def crop(xb: torch.Tensor, train: bool, gen: torch.Generator | None) -> torch.Tensor:
    total = xb.shape[2]
    c0 = (total - CROP) // 2
    if not train:
        return xb[:, :, c0 : c0 + CROP]
    s = int(round(TC["shift_s"] * FS))
    off = torch.randint(-s, s + 1, (xb.shape[0],), generator=gen, device="cpu")
    idx = (c0 + off)[:, None] + torch.arange(CROP)[None, :]
    idx = idx.to(xb.device)
    return torch.gather(xb, 2, idx[:, None, :].expand(-1, xb.shape[1], -1))


def augment(x: torch.Tensor, gen: torch.Generator) -> torch.Tensor:
    b, c, _ = x.shape
    a = 1.0 + TC["amp_jitter"] * (2 * torch.rand(b, c, 1, generator=gen) - 1)
    x = x * a.to(x.device)
    return x + TC["noise"] * torch.randn(x.shape, generator=gen).to(x.device)


@torch.no_grad()
def predict(model: nn.Module, X: torch.Tensor, idx: np.ndarray, dev, bs: int = 1024) -> np.ndarray:
    model.eval()
    out = []
    for i in range(0, len(idx), bs):
        xb = X[torch.as_tensor(idx[i : i + bs])].to(dev).float()
        out.append(model(crop(xb, False, None)).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, N_CLASSES), np.float32)


def run_one(name: str, sp, X: torch.Tensor, y: np.ndarray, files, file_idx, dev) -> dict:
    rdir = RUNS / name
    rdir.mkdir(parents=True, exist_ok=True)
    st = rdir / "status.json"
    if st.exists() and json.loads(st.read_text())["status"] == "done":
        log(f"{name}: already done, skip")
        return json.loads((rdir / "metrics.json").read_text())
    tr, va, pr = sp
    seed = CONFIG["seed"] + int(h01(name) * 1000)
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    ytr = y[tr].copy()
    if name.endswith("_permuted"):
        ytr = np.random.default_rng(seed).permutation(ytr)
    model = (LinearNet() if name.endswith("_linear") else ConvNet(dropout=TC["dropout"])).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=TC["lr"], weight_decay=TC["weight_decay"])
    E = TC["epochs"]
    steps_per = math.ceil(len(tr) / TC["batch_size"])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=TC["lr"], total_steps=E * steps_per, pct_start=0.15)
    cnt = np.bincount(ytr, minlength=N_CLASSES).astype(np.float64)
    w = torch.tensor(cnt.sum() / (N_CLASSES * np.maximum(cnt, 1)), dtype=torch.float32, device=dev)
    yt = torch.as_tensor(ytr, device=dev)
    yva = torch.as_tensor(y[va], device=dev)
    ep0, best, bad, hist = 0, (float("inf"), -1), 0, []
    if (rdir / "latest.pt").exists():
        ck = torch.load(rdir / "latest.pt", map_location=dev, weights_only=False)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); sched.load_state_dict(ck["sched"])
        ep0, best, bad, hist = ck["epoch"] + 1, tuple(ck["best"]), ck["bad"], ck["hist"]
        gen.set_state(ck["gen"])
        log(f"{name}: resume at epoch {ep0}")
    st.write_text(json.dumps({"status": "running", "epoch": ep0}))
    log(f"{name}: train {len(tr)} val {len(va)} predict {len(pr)} model {type(model).__name__}")
    t0 = time.time()
    for ep in range(ep0, E):
        model.train()
        perm = torch.randperm(len(tr), generator=gen)
        tl, n = 0.0, 0
        for i in range(0, len(tr), TC["batch_size"]):
            bi = perm[i : i + TC["batch_size"]]
            xb = X[torch.as_tensor(tr)[bi]].to(dev).float()
            xb = augment(crop(xb, True, gen), gen)
            loss = F.cross_entropy(model(xb), yt[bi.to(dev)], weight=w)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            tl += float(loss) * len(bi); n += len(bi)
        lv = predict(model, X, va, dev)
        vl = float(F.cross_entropy(torch.as_tensor(lv, device=dev), yva, weight=w))
        vacc = float((lv.argmax(1) == y[va]).mean())
        hist.append({"epoch": ep, "train_loss": tl / n, "val_loss": vl, "val_acc": vacc})
        improved = vl < best[0]
        if improved:
            best, bad = (vl, ep), 0
            torch.save(model.state_dict(), rdir / "best.pt")
        else:
            bad += 1
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(), "epoch": ep,
                    "best": list(best), "bad": bad, "hist": hist, "gen": gen.get_state()}, rdir / "latest.pt")
        st.write_text(json.dumps({"status": "running", "epoch": ep}))
        log(f"{name}: ep {ep} train {tl / n:.3f} val {vl:.3f} acc {vacc:.3f}{' *' if improved else ''}")
        if bad >= TC["patience"]:
            log(f"{name}: early stop at epoch {ep}")
            break
    model.load_state_dict(torch.load(rdir / "best.pt", map_location=dev))
    lp = predict(model, X, pr, dev)
    zero = model.eval()(torch.zeros(1, X.shape[1], CROP, device=dev)).detach().float().cpu().numpy()[0]
    np.savez(rdir / "preds.npz", idx=pr, logits=lp.astype(np.float32), zero_logits=zero.astype(np.float32))
    acc = lp.argmax(1) == y[pr]
    letters = y[pr] < 26
    part = np.array([files[file_idx[i]]["participant"] for i in pr])
    m = {"run": name, "n_train": int(len(tr)), "n_val": int(len(va)), "n_predict": int(len(pr)),
         "best_epoch": best[1], "best_val_loss": best[0], "predict_acc": float(acc.mean()),
         "predict_acc_letters": float(acc[letters].mean()), "predict_acc_space": float(acc[~letters].mean()),
         "predict_acc_by_participant": {p: float(acc[part == p].mean()) for p in sorted(set(part), key=lambda s: int(s[1:]))},
         "zero_input_argmax": int(zero.argmax()), "seconds": round(time.time() - t0, 1), "history": hist}
    (rdir / "metrics.json").write_text(json.dumps(m, indent=1))
    st.write_text(json.dumps({"status": "done", "epoch": best[1]}))
    (rdir / "latest.pt").unlink(missing_ok=True)
    log(f"{name}: DONE predict acc {m['predict_acc']:.3f} (letters {m['predict_acc_letters']:.3f}, space {m['predict_acc_space']:.3f})")
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="xsession,xsession_linear,xsession_permuted,calib_a,calib_b,xsubject_f0,xsubject_f1,xsubject_f2,xsubject_f3")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "pid.txt").write_text(str(os.getpid()))
    dev = torch.device("cuda" if torch.cuda.is_available() and not a.cpu else "cpu")
    with keep_awake(log):
        Xn, y, file_idx, files = load()
        sp, fold_of = splits(files, file_idx)
        (RUNS / "splits.json").write_text(json.dumps({"xsubject_fold_of": fold_of,
                                                      **{k: [len(v) for v in s] for k, s in sp.items()}}, indent=1))
        X = torch.from_numpy(Xn)  # float16, CPU; batches move to the device
        if dev.type == "cuda":
            X = X.to(dev)
        log(f"device {dev}; windows {tuple(X.shape)}; runs {a.runs}")
        summary = {}
        for name in a.runs.split(","):
            summary[name] = {k: v for k, v in run_one(name, sp[name], X, y, files, file_idx, dev).items() if k != "history"}
        (RUNS / "summary.json").write_text(json.dumps(summary, indent=1))
        (RUNS / "ALL_DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
        log("ALL DONE")


if __name__ == "__main__":
    main()
