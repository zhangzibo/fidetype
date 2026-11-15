"""Long training run of the causal GRU-CTC decoder on T15, L 0 only (M4-13). Our own code.

Extends the M4-12 trainer (experiments/2026-11-14-m4-12-decoder-retrain/train.py). Model class, init,
optimiser, LR shape, augmentation and input dropout are the M4-12 recipe. Changes (see plan.md):

- step budget from config (sized by the smoke test); cosine LR stretched to that length
- sampler "days": each step draws ``days_per_batch`` distinct training days (sessions) at random, then
  batch / days_per_batch trials per day (without replacement; with replacement only if a day has fewer).
  The draw uses an RNG seeded by (seed, step), so a resume repeats the exact batch sequence.
- micro-batches (compute only): the batch is sorted by length and cut into chunks of at most
  ``micro_bins`` padded bins; the chunk losses are weighted by chunk size / batch size and summed before
  one optimiser step. With CTC mean reduction this gives the gradient of the full batch.
- validation on val_select at every ``eval_fraction`` of the budget; best.pt = lowest val_select PER
- pause / stop files are checked after EVERY step: <run>/pause or <run>/stop -> write latest.pt, set
  status "paused" / "stopped", exit 0. Resume with --resume (exact step and RNG position).

Run (repo root, detached; see queue.ps1 and HANDOFF.md):
  C:/venvs/fidetype-rocm/Scripts/python.exe -u experiments/2026-11-15-m4-13-long-train/train.py --which dedicated_0 [--resume]
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
        loss_sum += float(F.ctc_loss(lp.transpose(0, 1), tg, fl.cpu(), tl.cpu(), blank=0, reduction="sum", zero_infinity=True))
        lpn = lp.cpu().numpy()
        for i, x in enumerate(b):
            ed += edit(list(x[2]), greedy(lpn[i, :int(fl[i])]))
            n += len(x[2])
    model.train()
    return {"per": ed / max(1, n), "loss": loss_sum / max(1, len(items))}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


_EPOCHS: list = []


def bucket_batch(tr: list, step: int):
    """Sampler "bucket" (M4-12 batches: all days mixed, length buckets, max_batch_bins cap); epoch e uses
    RNG (seed, e) as in M4-12; the step-th batch over consecutive epochs (resume-exact)."""
    k = step
    e = 0
    while True:
        while len(_EPOCHS) <= e:
            _EPOCHS.append([[id(x) for x in b] for b in batches(tr, TC["batch"], np.random.default_rng([TC["seed"], len(_EPOCHS)]),
                                                                  TC["max_batch_bins"])])
        if k < len(_EPOCHS[e]):
            ids = _EPOCHS[e][k]
            break
        k -= len(_EPOCHS[e])
        e += 1
    by_id = bucket_batch.by_id
    return [by_id[i] for i in ids], np.random.default_rng([TC["seed"], 9, step])


def day_batch(by_day: dict, days: list, step: int):
    """The batch of one step (sampler "days" / "days_band"): RNG seeded by (seed, step), so resume-exact."""
    rng = np.random.default_rng([TC["seed"], 7, step])
    k = TC["days_per_batch"]
    per = TC["batch"] // k
    out = []
    if TC["sampler"] == "days_band":
        q = rng.random()  # one length quantile for the whole batch
    for d in rng.choice(days, k, replace=False):
        idx = by_day[int(d)]  # sorted by length (main)
        n = len(idx)
        if TC["sampler"] == "days_band":
            # circular window of per consecutive trials (length order) starting at quantile q of this day:
            # every trial of the day has inclusion probability per / n (uniform), and the batch has similar lengths
            st = int(q * n)
            pick = [(st + j) % n for j in range(min(per, n))]
            pick += list(rng.choice(n, per - len(pick), replace=True)) if per > n else []
        else:
            pick = rng.choice(n, per, replace=n < per)
        out += [idx[j] for j in pick]
    return out, rng


def micro_chunks(b: list) -> list:
    """Sort by length and cut into chunks of at most micro_bins padded bins (compute only)."""
    b = sorted(b, key=lambda x: x[1].shape[0])
    chunks, cur = [], []
    for x in b:
        padded = int(math.ceil(x[1].shape[0] / PAD_BINS) * PAD_BINS)
        if cur and (len(cur) + 1) * padded > TC["micro_bins"]:
            chunks.append(cur)
            cur = []
        cur.append(x)
    if cur:
        chunks.append(cur)
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True, choices=sorted(T.CONFIG["runs"]))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--steps", type=int, default=None, help="override the step budget (smoke test)")
    ap.add_argument("--stop-after", type=int, default=None, help="smoke test: pause (with checkpoint) after this step")
    ap.add_argument("--run-suffix", default="", help="smoke test: separate run dir")
    ap.add_argument("--limit-val", type=int, default=None, help="smoke test: val_select items")
    ap.add_argument("--micro-bins", type=int, default=None)
    ap.add_argument("--log-every", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--sampler", default=None, choices=["days", "days_band", "bucket"])
    ap.add_argument("--worst-case", action="store_true", help="smoke test: time the longest trials as one batch, then exit")
    args = ap.parse_args()
    spec = T.CONFIG["runs"][args.which]
    run = T.RUNS / (spec["run"] + args.run_suffix)
    assert run.name.startswith("m4-13-"), run
    run.mkdir(parents=True, exist_ok=True)
    if args.steps:
        TC["total_steps"] = args.steps
    if args.log_every:
        TC["log_every"] = args.log_every
    if args.batch:
        TC["batch"] = args.batch
    if args.sampler:
        TC["sampler"] = args.sampler
    if args.micro_bins:
        TC["micro_bins"] = args.micro_bins
    total = int(TC["total_steps"])
    assert total > 0, "total_steps not set"
    eval_every = max(1, int(round(total * TC["eval_fraction"])))
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
    by_day: dict = {}
    for x in tr:
        by_day.setdefault(int(x[0]), []).append(x)
    for d in by_day:  # length order (stable; ties keep the load order)
        by_day[d] = sorted(by_day[d], key=lambda x: x[1].shape[0])
    days = sorted(by_day)
    bucket_batch.by_id = {id(x): x for x in tr}
    cfg = T.model_config(len(sessions))
    la = int(spec["lookahead_bins"])
    torch.manual_seed(TC["seed"])
    model = build_torch_model(cfg).to(dev)
    diff = patch_model(model)
    log(f"start dev={dev} which={args.which} run={run.name} sessions={len(sessions)} train={len(tr)} train_days={len(days)} "
        f"val_select={len(va)} la={la} eval_every={eval_every} fast_gru_maxdiff={diff:.2e} model={json.dumps(cfg.to_dict())} "
        f"train={json.dumps(TC)}")
    assert diff < 1e-4, f"fast GRU differs from nn.GRU: {diff}"
    opt = torch.optim.AdamW(param_groups(model), lr=TC["lr_max"], betas=(0.9, 0.999), eps=TC["adam_eps"])
    state = {"step": 0, "best_per": float("inf"), "best_step": -1, "train_sec": 0.0}

    def lr_at(step):
        if step < TC["warmup_steps"]:
            return TC["lr_max"] * (step + 1) / TC["warmup_steps"]
        q = min(1.0, (step - TC["warmup_steps"]) / max(1, total - TC["warmup_steps"]))
        return TC["lr_min"] + (TC["lr_max"] - TC["lr_min"]) * 0.5 * (1 + math.cos(math.pi * q))

    def train_step(b, b_rng):
        for g in opt.param_groups:
            g["lr"] = lr_at(state["step"])
        opt.zero_grad()
        lv = 0.0
        for ch in micro_chunks(b):
            X, sess, lens, tg, tl = collate(ch, dev, True, b_rng)
            lp = model(X, sess, la, lens).log_softmax(-1)
            # lengths as CPU tensors: M4-13 smoke test hit a stale target_lengths read on ROCm/Windows (size mismatch error)
            loss = F.ctc_loss(lp.transpose(0, 1), tg, model.n_frames(lens).cpu(), tl.cpu(), blank=0, reduction="mean", zero_infinity=True)
            w = len(ch) / len(b)
            (loss * w).backward()
            lv += float(loss) * w
        nn.utils.clip_grad_norm_(model.parameters(), TC["grad_clip"])
        opt.step()
        return lv

    if args.worst_case:
        b = sorted(tr, key=lambda x: -x[1].shape[0])[:TC["batch"]]
        rng = np.random.default_rng(0)
        for r in range(4):
            if dev == "cuda":
                torch.cuda.synchronize()
            t0 = time.time()
            train_step(b, rng)
            if dev == "cuda":
                torch.cuda.synchronize()
            mem = torch.cuda.max_memory_allocated() / 1e9 if dev == "cuda" else 0.0
            msg = (f"worst-case batch rep {r}: {time.time() - t0:.2f} s, micro_bins {TC['micro_bins']}, "
                   f"chunks {len(micro_chunks(b))}, max_mem_gb {mem:.2f}")
            log(msg)
            print(msg, flush=True)
        return
    if args.resume and (run / "latest.pt").exists():
        ck = torch.load(run / "latest.pt", map_location=dev, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        state = ck["state"]
        log(f"resumed {state}")

    def status(s):
        (run / "status.json").write_text(json.dumps({**state, "status": s, "total_steps": total, "eval_every": eval_every,
                                                     "time": time.strftime("%Y-%m-%dT%H:%M:%S")}))

    def save_latest():
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "state": state, "sessions": sessions,
                    "model_config": cfg.to_dict(), "train_config": TC, "which": args.which}, run / "latest.tmp")
        os.replace(run / "latest.tmp", run / "latest.pt")

    for f in ("pause", "stop"):
        if (run / f).exists():
            log(f"{f} file present at start: exit without training")
            status("paused" if f == "pause" else "stopped")
            return
    last_ck = time.time()
    status("running")
    win_loss, win_n, t_win = 0.0, 0, time.time()
    while state["step"] < total:
        b, b_rng = bucket_batch(tr, state["step"]) if TC["sampler"] == "bucket" else day_batch(by_day, days, state["step"])
        t_step = time.time()
        lv = train_step(b, b_rng)
        if not math.isfinite(lv):
            log(f"non-finite loss at step {state['step']}")
        state["step"] += 1
        state["train_sec"] += time.time() - t_step
        win_loss += lv
        win_n += 1
        if state["step"] % TC["log_every"] == 0:
            log(json.dumps({"step": state["step"], "train_loss": round(win_loss / win_n, 4), "lr": lr_at(state["step"]),
                            "s_per_step": round((time.time() - t_win) / win_n, 3)}))
            win_loss, win_n, t_win = 0.0, 0, time.time()
        done = state["step"] >= total
        if state["step"] % eval_every == 0 or done:
            t0 = time.time()
            ev = evaluate(model, va, dev, la)
            frac = state["step"] / total
            rec = {"step": state["step"], "fraction": round(frac, 4), "val_per": {str(la): ev["per"]},
                   "val_loss": {str(la): ev["loss"]}, "score": ev["per"], "lr": lr_at(state["step"]),
                   "eval_sec": round(time.time() - t0, 1), "train_hours": round(state["train_sec"] / 3600, 3),
                   "report_point": any(abs(frac - r) < 1e-9 for r in TC["report_fractions"])}
            with open(run / "metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            if ev["per"] < state["best_per"]:
                state.update(best_per=ev["per"], best_step=state["step"])
                torch.save({"model": model.state_dict(), "sessions": sessions, "model_config": cfg.to_dict(),
                            "train_config": TC, "which": args.which, "step": state["step"], "epoch": None,
                            "val_per": rec["val_per"]}, run / "best.pt")
            save_latest()
            last_ck = time.time()
            log(json.dumps(rec), f"best {state['best_per']:.4f}@{state['best_step']}")
            status("running")
        elif time.time() - last_ck > 60 * TC["checkpoint_minutes"]:
            save_latest()
            last_ck = time.time()
            status("running")
        if done:
            break
        stop_now = args.stop_after is not None and state["step"] >= args.stop_after
        for f in ("pause", "stop"):
            if (run / f).exists() or (stop_now and f == "pause"):
                save_latest()
                status("paused" if f == "pause" else "stopped")
                log(f"{f} at step {state['step']}: latest.pt written")
                return
    status("done")
    log("done")


if __name__ == "__main__":
    main()
