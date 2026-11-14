"""Retrain the lookahead GRU-CTC decoder on T15 with a recipe close to the published B2T '25 baseline (M4-12).

Our own code. It extends the M4-01 trainer (experiments/2026-11-13-m4-01-02-lookahead/train.py).
The model class is unchanged (fidetype.decoders.lookahead_gru), so decode.py, the NumPy
decoders and run.py work as in M4-01/02. The changes (see plan.md) are training-side only:

- step budget (not epochs), cosine LR peak 5e-3 -> 1e-4, 1,000 warmup steps
- AdamW eps 0.1; weight decay 1e-3 on weight matrices, 0 on biases and on the day layer
- init: Xavier uniform for GRU input weights and the output layer, orthogonal (per gate) GRU recurrent weights
- input dropout 0.2 after the day layer (training only: an identity at eval, so inference is unchanged)
- augmentation: white noise sd 1.0, constant offset sd 0.2 (both before the causal smoothing, as before),
  random cut of 0..3 bins at the trial start
- a GRU forward with the input projection done once for all steps (same maths and parameters as nn.GRU;
  checked against nn.GRU at start-up). The ROCm build cannot use MIOpen for the GRU backward.
- validation on val_select every ``eval_every`` steps; best.pt = lowest mean val_select PER

Detached GPU job. latest.pt every few minutes, resume from latest.pt (exact batch position).

Run (repo root, detached; see queue.ps1 and HANDOFF.md):
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -u experiments/2026-11-14-m4-12-decoder-retrain/train.py --which dedicated_0 [--resume]
Stop: create <run_dir>/stop (clean stop at the next validation) or kill pid.txt.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import types
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


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


def batches(items, bs: int, rng: np.random.Generator | None, max_bins: int | None = None):
    """Length-bucketed batches (as M4-01). ``max_bins`` caps batch size x padded length."""
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


def collate(b, dev, train: bool, rng: np.random.Generator | None = None):
    cuts = [0] * len(b)
    if train and TC["random_cut_bins"] > 0:
        cuts = [int(rng.integers(0, TC["random_cut_bins"] + 1)) for _ in b]
    xs = [x[1][c:] for x, c in zip(b, cuts)]
    Tm = max(x.shape[0] for x in xs)
    Tm = int(math.ceil(Tm / PAD_BINS) * PAD_BINS)  # few distinct shapes (ROCm/Windows allocator)
    X = np.zeros((len(b), Tm, 512), np.float32)
    for i, x in enumerate(xs):
        X[i, :x.shape[0]] = x
    X = torch.from_numpy(X).to(dev)
    lens = torch.tensor([x.shape[0] for x in xs], device=dev)
    if train:
        noise = TC["white_noise_sd"] * torch.randn_like(X) + TC["offset_sd"] * torch.randn(len(b), 1, 512, device=dev)
        valid = (torch.arange(Tm, device=dev)[None, :] < lens[:, None]).unsqueeze(-1)
        X = X + noise * valid
    sess = torch.tensor([x[0] for x in b], device=dev)
    tg = torch.cat([torch.from_numpy(x[2]) for x in b]).to(dev)
    tl = torch.tensor([len(x[2]) for x in b], device=dev)
    return X, sess, lens, tg, tl


# ---------------------------------------------------------------------------
# model patches (training side only; parameters and state-dict keys unchanged)
# ---------------------------------------------------------------------------


def fast_gru_forward(self, x, h0=None):
    """Single-layer GRU, batch first, same maths and parameters as nn.GRU (gate order r, z, n)."""
    W_ih, W_hh, b_ih, b_hh = self.weight_ih_l0, self.weight_hh_l0, self.bias_ih_l0, self.bias_hh_l0
    Bn, K, _ = x.shape
    gi = F.linear(x, W_ih, b_ih)  # one large matmul for all steps
    h = x.new_zeros(Bn, W_hh.shape[1]) if h0 is None else h0
    outs = []
    for k in range(K):
        gh = F.linear(h, W_hh, b_hh)
        i_r, i_z, i_n = gi[:, k].chunk(3, -1)
        h_r, h_z, h_n = gh.chunk(3, -1)
        r = torch.sigmoid(i_r + h_r)
        z = torch.sigmoid(i_z + h_z)
        n = torch.tanh(i_n + r * h_n)
        h = n + z * (h - n)
        outs.append(h)
    return torch.stack(outs, 1), h


def patch_model(model) -> float:
    """Init (Xavier / orthogonal), input dropout, fast GRU. Returns the max abs diff fast vs nn.GRU."""
    for g in model.grus:
        H = g.hidden_size
        nn.init.xavier_uniform_(g.weight_ih_l0)
        for q in range(3):
            nn.init.orthogonal_(g.weight_hh_l0.data[q * H:(q + 1) * H])
        nn.init.zeros_(g.bias_ih_l0)
        nn.init.zeros_(g.bias_hh_l0)
    nn.init.xavier_uniform_(model.out.weight)
    nn.init.zeros_(model.out.bias)
    # equivalence check of the fast GRU on the initialised weights
    g0 = model.grus[0]
    with torch.no_grad():
        x = torch.randn(3, 20, g0.input_size, device=g0.weight_ih_l0.device)
        a, _ = nn.GRU.forward(g0, x)
        b, _ = fast_gru_forward(g0, x)
        diff = float((a - b).abs().max())
    if TC.get("fast_gru", True):
        for g in model.grus:
            g.forward = types.MethodType(fast_gru_forward, g)
    p_in = float(TC["input_dropout"])
    if p_in > 0:
        orig = model.features

        def features(x, sess):
            z = orig(x, sess)
            return F.dropout(z, p_in, model.training)

        model.features = features
    return diff


def param_groups(model):
    day, bias, rest = [], [], []
    for n, p in model.named_parameters():
        if n.startswith("day_"):
            day.append(p)
        elif n.endswith("bias") or ".bias_" in n or n.startswith("la_emb"):
            bias.append(p)
        else:
            rest.append(p)
    return [{"params": rest, "weight_decay": TC["weight_decay"]},
            {"params": bias, "weight_decay": 0.0},
            {"params": day, "weight_decay": TC["weight_decay_day"]}]


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True, choices=sorted(T.CONFIG["runs"]))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--steps", type=int, default=None, help="override the step budget (smoke test)")
    ap.add_argument("--eval-every", type=int, default=None)
    ap.add_argument("--run-suffix", default="", help="smoke test: separate run dir")
    ap.add_argument("--limit-val", type=int, default=None, help="smoke test: val_select items")
    args = ap.parse_args()
    spec = T.CONFIG["runs"][args.which]
    run = T.RUNS / (spec["run"] + args.run_suffix)
    run.mkdir(parents=True, exist_ok=True)
    if args.steps:
        TC["total_steps"] = args.steps
    if args.eval_every:
        TC["eval_every"] = args.eval_every
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
    tr = T.load_part("train")
    va = T.load_part("val_select", args.limit_val)
    tr = [x for x in tr if (x[1].shape[0] - TC["random_cut_bins"] - 14) // 4 + 1 >= len(x[2])]
    cfg = T.model_config(len(sessions))
    la_spec = spec["lookahead_bins"]
    la_choices = T.LA_BINS if la_spec == "sample" else [int(la_spec)]
    eval_las = TC["eval_lookahead_bins"] if la_spec == "sample" else [int(la_spec)]
    torch.manual_seed(TC["seed"])
    model = build_torch_model(cfg).to(dev)
    diff = patch_model(model)
    log(f"start dev={dev} which={args.which} run={run.name} sessions={len(sessions)} train={len(tr)} val_select={len(va)} "
        f"la_choices={la_choices} fast_gru_maxdiff={diff:.2e} model={json.dumps(cfg.to_dict())} train={json.dumps(TC)}")
    assert diff < 1e-4, f"fast GRU differs from nn.GRU: {diff}"
    opt = torch.optim.AdamW(param_groups(model), lr=TC["lr_max"], betas=(0.9, 0.999), eps=TC["adam_eps"])
    total = TC["total_steps"]

    def lr_at(step):
        if step < TC["warmup_steps"]:
            return TC["lr_max"] * (step + 1) / TC["warmup_steps"]
        q = min(1.0, (step - TC["warmup_steps"]) / max(1, total - TC["warmup_steps"]))
        return TC["lr_min"] + (TC["lr_max"] - TC["lr_min"]) * 0.5 * (1 + math.cos(math.pi * q))

    state = {"epoch": 0, "step": 0, "best_per": float("inf"), "best_step": -1, "bad": 0, "batch_in_epoch": 0,
             "train_sec": 0.0}
    if args.resume and (run / "latest.pt").exists():
        ck = torch.load(run / "latest.pt", map_location=dev, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        state = ck["state"]
        log(f"resumed {state}")

    def status(s):
        (run / "status.json").write_text(json.dumps({**state, "status": s, "total_steps": total,
                                                     "time": time.strftime("%Y-%m-%dT%H:%M:%S")}))

    def save_latest():
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "state": state, "sessions": sessions,
                    "model_config": cfg.to_dict(), "train_config": TC, "which": args.which}, run / "latest.tmp")
        os.replace(run / "latest.tmp", run / "latest.pt")

    last_ck = time.time()
    status("running")
    win_loss, win_n, t_win = 0.0, 0, time.time()
    while state["step"] < total:
        ep_rng = np.random.default_rng([TC["seed"], state["epoch"]])
        for bi, b in enumerate(batches(tr, TC["batch"], ep_rng, TC["max_batch_bins"])):
            la = int(ep_rng.choice(la_choices))  # drawn for every batch (same RNG stream on resume)
            b_rng = np.random.default_rng([TC["seed"], state["epoch"], bi])  # per-batch cut RNG (resume-exact)
            if bi < state["batch_in_epoch"]:
                continue
            t_step = time.time()
            for gi, g in enumerate(opt.param_groups):
                g["lr"] = lr_at(state["step"])
            X, sess, lens, tg, tl = collate(b, dev, True, b_rng)
            lp = model(X, sess, la, lens).log_softmax(-1)
            loss = F.ctc_loss(lp.transpose(0, 1), tg, model.n_frames(lens), tl, blank=0, reduction="mean", zero_infinity=True)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), TC["grad_clip"])
            opt.step()
            lv = float(loss)
            state["step"] += 1
            state["batch_in_epoch"] = bi + 1
            state["train_sec"] += time.time() - t_step
            win_loss += lv
            win_n += 1
            if state["step"] % TC["log_every"] == 0:
                log(json.dumps({"step": state["step"], "epoch": state["epoch"], "train_loss": round(win_loss / win_n, 4),
                                "lr": lr_at(state["step"]), "s_per_step": round((time.time() - t_win) / win_n, 3)}))
                win_loss, win_n, t_win = 0.0, 0, time.time()
            done = state["step"] >= total
            if state["step"] % TC["eval_every"] == 0 or done:
                t0 = time.time()
                evs = {k: evaluate(model, va, dev, k) for k in eval_las}
                score = float(np.mean([e["per"] for e in evs.values()]))
                rec = {"step": state["step"], "epoch": state["epoch"], "val_per": {str(k): v["per"] for k, v in evs.items()},
                       "val_loss": {str(k): v["loss"] for k, v in evs.items()}, "score": score, "lr": lr_at(state["step"]),
                       "eval_sec": round(time.time() - t0, 1), "train_hours": round(state["train_sec"] / 3600, 3)}
                with open(run / "metrics.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
                if score < state["best_per"]:
                    state.update(best_per=score, best_step=state["step"], bad=0)
                    torch.save({"model": model.state_dict(), "sessions": sessions, "model_config": cfg.to_dict(),
                                "train_config": TC, "which": args.which, "epoch": state["epoch"], "step": state["step"],
                                "val_per": rec["val_per"]}, run / "best.pt")
                else:
                    state["bad"] += 1
                save_latest()
                last_ck = time.time()
                log(json.dumps(rec), f"best {state['best_per']:.4f}@{state['best_step']}")
                status("running")
                if state["bad"] >= TC["patience_evals"]:
                    status("early_stopped")
                    log("early stop")
                    return
                if (run / "stop").exists():
                    status("stopped")
                    log("stop file")
                    return
                if done:
                    break
            elif time.time() - last_ck > 60 * TC["checkpoint_minutes"]:
                save_latest()
                last_ck = time.time()
                status("running")
        else:
            state["epoch"] += 1
            state["batch_in_epoch"] = 0
            continue
        break
    status("done")
    log("done")


if __name__ == "__main__":
    main()
