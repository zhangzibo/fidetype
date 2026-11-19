r"""P15-08 E1a runner (our own code, Apache-2.0). Plan: plan.md (frozen in 60620ab before any result).

Stages (``all`` runs them in order and skips finished parts; every training part resumes exactly):
  prep     Willett sentences.mat -> cache (uint8 frames, metadata, splits, per-session norm stats)
  text     arm T pretraining on synthetic key renderings (no body signal), 30,000 steps
  grid     40 adaptation runs (arms R, T, E, S x budgets 3, 10, 30, 100, all min x seeds 0, 1) + C2
  summary  aggregate CERs, bootstrap, V1 / H1-H4 / C1 / C2 / roadmap rule -> summary.json
           (also copied, aggregate only, to results/summary.json in the repo)

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-19-p15-08-e1-cross-body\run.py all
A file ``pause`` or ``stop`` in --out makes the job save ``latest.pt`` after the current step and
exit with code 3. Re-run the same command to resume. ``--quick`` = dry run (few steps, seed 0,
budgets 3 and all) into another --out.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e1  # noqa: E402

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-08")
RAW = Path(r"C:\Users\zhang\bci-data\raw\willett-handwriting\extracted\handwritingBCIData\Datasets")
P11_CACHE = Path(r"C:\Users\zhang\bci-data\derived\p11-01-emg-decoder")
PAUSED = 3
LICENCE = {"R": {"data": ["Willett handwriting (CC0-1.0)"], "research_only": False},
           "T": {"data": ["Willett handwriting (CC0-1.0)", "emg2qwerty key sequences (CC-BY-NC-SA-4.0)"],
                 "research_only": True},
           "E": {"data": ["Willett handwriting (CC0-1.0)", "emg2qwerty sEMG (CC-BY-NC-SA-4.0)"], "research_only": True},
           "S": {"data": ["Willett handwriting (CC0-1.0)", "emg2qwerty sEMG (CC-BY-NC-SA-4.0)"], "research_only": True}}


class Paused(Exception):
    pass


@dataclass
class Ctx:
    out: Path
    cache: Path
    raw: dict
    device: str
    trunk: e1.TrunkCfg
    ft: e1.FTCfg
    tx: e1.TextCfg
    e_ckpt: Path
    p11_cache: Path
    seeds: list = field(default_factory=lambda: [0, 1])
    budgets: list = field(default_factory=lambda: ["3", "10", "30", "100", "all"])
    arms: list = field(default_factory=lambda: list(e1.ARMS))
    repo_results: Path | None = None


def keep_awake(on: bool) -> None:
    if os.name == "nt":
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def log(ctx: Ctx, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(ctx.out / "run.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def atomic_save(obj: dict, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


def stop_requested(ctx: Ctx) -> bool:
    return (ctx.out / "pause").exists() or (ctx.out / "stop").exists()


def make_optim(model: torch.nn.Module, wd: float, lr: float) -> torch.optim.Optimizer:
    decay, no_decay = [], []
    for n, p in model.named_parameters():
        (no_decay if p.ndim < 2 or "norm" in n else decay).append(p)
    return torch.optim.AdamW([{"params": decay, "weight_decay": wd}, {"params": no_decay, "weight_decay": 0.0}], lr=lr)


def ctx_from_config(path: Path, out: Path, device: str, cache: Path | None = None, quick: bool = False) -> Ctx:
    raw = json.loads(path.read_text(encoding="utf-8"))
    t = dict(raw["trunk"]); t["dilations"] = tuple(t["dilations"])
    ctx = Ctx(out=out, cache=cache or (out / "willett"), raw=raw, device=device, trunk=e1.TrunkCfg(**t),
              ft=e1.FTCfg(**raw["finetune"]), tx=e1.TextCfg(**raw["text_pretrain"]), e_ckpt=Path(raw["e_checkpoint"]),
              p11_cache=P11_CACHE, seeds=list(raw["seeds"]), budgets=list(raw["budgets_min"]), arms=list(raw["arms"]),
              repo_results=None if quick else HERE / "results")
    if quick:
        ctx.tx.steps, ctx.tx.warmup = 30, 5
        ctx.ft.steps = {k: 20 for k in ctx.ft.steps}
        ctx.ft.val_every, ctx.ft.warmup = 10, 5
        ctx.seeds, ctx.budgets = [0], ["3", "all"]
        ctx.raw = {**raw, "c1_budgets": ["all"], "c2": {"arm": "E", "budget": "3", "seed": 0},
                   "h_budgets": ["3"], "roadmap_rule_budgets": ["3"]}
    return ctx


# --- prep -----------------------------------------------------------------------------------------------


def stage_prep(ctx: Ctx, raw_dir: Path = RAW) -> dict:
    c = ctx.cache
    if (c / "DONE.json").exists():
        return json.loads((c / "DONE.json").read_text(encoding="utf-8"))
    c.mkdir(parents=True, exist_ok=True)
    sess_dirs = [p for p in sorted(raw_dir.glob("t5.*")) if (p / "sentences.mat").exists()]
    meta, n_sess = [], len(sess_dirs)
    for si, sd in enumerate(sess_dirs):
        rows = e1.load_willett_session(sd / "sentences.mat")
        xs, off = [], [0]
        for r in rows:
            ok = (not r["excluded"]) and len(r["text"]) > 0 and all(ch in e1.TOK for ch in r["text"])
            meta.append({"session": si, "session_name": sd.name, "block": r["block"], "trial": r["trial"],
                         "n_write": r["n_write"], "T": int(len(r["x"])), "ok": bool(ok), "cond": r["cond"],
                         "text": r["text"], "row": len(xs)})
            xs.append(r["x"]); off.append(off[-1] + len(r["x"]))
        np.savez(c / f"sess{si}.npz", x=np.concatenate(xs), off=np.array(off, np.int64))
        log(ctx, f"[prep] {sd.name}: {len(rows)} sentences")
    splits = e1.make_splits(meta, ctx.raw["salt"])
    # Per-session normalisation from non-test sentences only (no labels used).
    mean = np.zeros((n_sess, e1.N_W), np.float32); std = np.ones((n_sess, e1.N_W), np.float32)
    test = set(splits["test"])
    for si in range(n_sess):
        z = np.load(c / f"sess{si}.npz")
        rows = [r for i, r in enumerate(meta) if r["session"] == si and r["ok"] and i not in test]
        x = np.concatenate([z["x"][z["off"][r["row"]]:z["off"][r["row"] + 1]] for r in rows]).astype(np.float64)
        mean[si] = x.mean(0); std[si] = np.maximum(x.std(0), 0.1)
    np.savez(c / "norm.npz", mean=mean, std=std)
    e1.save_json(meta, c / "meta.json")
    e1.save_json(splits, c / "splits.json")
    rec = {"sessions": n_sess, "sentences": len(meta), "ok": sum(r["ok"] for r in meta),
           **{f"n_{k}": len(splits[k]) for k in ("test", "val", "pool")},
           **{f"min_{k}": round(e1.minutes_of(meta, splits[k]), 2) for k in ("test", "val", "pool")}}
    e1.save_json(rec, c / "DONE.json")
    log(ctx, f"[prep] DONE {rec}")
    return rec


class WillettStore:
    def __init__(self, cache: Path):
        self.meta = json.loads((cache / "meta.json").read_text(encoding="utf-8"))
        self.splits = json.loads((cache / "splits.json").read_text(encoding="utf-8"))
        z = np.load(cache / "norm.npz")
        self.mean, self.std = z["mean"], z["std"]
        self.x: dict[int, np.ndarray] = {}
        arrs = {}
        for i, r in enumerate(self.meta):
            if not r["ok"]:
                continue
            s = r["session"]
            if s not in arrs:
                arrs[s] = np.load(cache / f"sess{s}.npz")
                arrs[s] = (arrs[s]["x"], arrs[s]["off"])
            xa, off = arrs[s]
            self.x[i] = xa[off[r["row"]]:off[r["row"] + 1]]
        self.tgt = {i: e1.encode(self.meta[i]["text"]) for i in self.x}
        self.length = {i: len(v) for i, v in self.x.items()}
        self.n_sessions = len(self.mean)


# --- arm T: text-only pretraining -----------------------------------------------------------------------


class TextSampler:
    """Deterministic synthetic batches from emg2qwerty key sequences: batch k depends on k only."""

    def __init__(self, labs: list[dict], n_frames: list[int], c: e1.TextCfg, seed: int = 0):
        self.labs, self.c, self.seed = labs, c, seed
        ok = [i for i, n in enumerate(n_frames) if n > c.window + 1]
        self.idx = ok
        w = np.array([n_frames[i] - c.window for i in ok], np.float64)
        self.p = w / w.sum()
        self.n = n_frames
        self.emb = e1.text_embeddings(seed)

    @staticmethod
    def from_p11(cache: Path, c: e1.TextCfg) -> "TextSampler":
        index = json.loads((cache / "index.json").read_text(encoding="utf-8"))
        splits = json.loads((cache / "splits.json").read_text(encoding="utf-8"))
        nf = {r["session"]: int(r["n_frames"]) for r in index["sessions"]}
        labs, n = [], []
        for s in splits["generic_train"]:
            with np.load(cache / "sessions" / f"{s}.lab.npz", allow_pickle=False) as z:
                labs.append({"key_frame": z["key_frame"].astype(np.int64), "key_tok": z["key_tok"].astype(np.int64)})
            n.append(nf[s])
        return TextSampler(labs, n, c)

    def batch_at(self, k: int) -> dict:
        c = self.c
        rng = np.random.default_rng([self.seed, 31, k])
        si = rng.choice(len(self.idx), size=c.batch, p=self.p)
        x = np.empty((c.batch, c.window, e1.TEXT_DIM), np.float32)
        tg, tl = [], []
        for b, j in enumerate(si):
            i = self.idx[j]
            o = int(rng.integers(0, self.n[i] - c.window))
            lab = self.labs[i]
            lo, hi = np.searchsorted(lab["key_frame"], [o, o + c.window])
            kf, kt = lab["key_frame"][lo:hi] - o, lab["key_tok"][lo:hi]
            x[b] = e1.render_text(kf, kt, c.window, self.emb, c, rng)
            tg.append(kt); tl.append(len(kt))
        return {"x": x, "targets": np.concatenate(tg) if tg else np.zeros(0, np.int64),
                "target_lengths": np.array(tl, np.int64)}


def stage_text(ctx: Ctx, sampler: TextSampler | None = None, max_steps: int | None = None) -> dict:
    d = ctx.out / "text"
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "DONE.json").read_text(encoding="utf-8"))
    c = ctx.tx
    sampler = sampler or TextSampler.from_p11(ctx.p11_cache, c)
    torch.manual_seed(0)
    model = e1.XBody(ctx.trunk, "text").to(ctx.device)
    opt = make_optim(model, c.weight_decay, c.lr)
    step = 0
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=ctx.device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); step = int(ck["step"])
        log(ctx, f"[text] resume at step {step}")
    e1.save_json({"text_pretrain": e1.cfg_json(c), "trunk": e1.cfg_json(ctx.trunk)}, d / "config.json")
    e1.save_json(LICENCE["T"], d / "licence.json")
    pool = ThreadPoolExecutor(2)
    futs = {k: pool.submit(sampler.batch_at, k) for k in range(step, min(c.steps, step + 3))}
    end = c.steps if max_steps is None else min(c.steps, step + max_steps)
    t_ck = t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0
    try:
        while step < end:
            b = (futs.pop(step, None) or pool.submit(sampler.batch_at, step)).result()
            if step + 3 < c.steps and step + 3 not in futs:
                futs[step + 3] = pool.submit(sampler.batch_at, step + 3)
            torch.manual_seed(1_000_003 + step)
            model.train()
            for g in opt.param_groups:
                g["lr"] = e1.lr_at(step, c.steps, c.lr, c.lr_min, c.warmup)
            x = torch.from_numpy(b["x"]).to(ctx.device)
            lp = model(x)
            B, T = lp.shape[:2]
            loss = F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(ctx.device),
                              torch.full((B,), T, dtype=torch.long), torch.from_numpy(b["target_lengths"]),
                              blank=e1.BLANK, reduction="mean", zero_infinity=True)
            opt.zero_grad(set_to_none=True)
            if torch.isfinite(loss):
                loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), c.clip); opt.step()
                losses.append(float(loss.detach()))
            else:
                skipped += 1
            step += 1
            if step % 100 == 0 or step == end:
                dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
                log(ctx, f"[text] step {step}/{c.steps} loss {np.mean(losses) if losses else float('nan'):.4f} "
                         f"{dt:.3f} s/step skipped {skipped}")
                losses = []
            if time.time() - t_ck > 60 * c.ckpt_minutes:
                atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step}, d / "latest.pt")
                t_ck = time.time()
            if stop_requested(ctx):
                atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step}, d / "latest.pt")
                log(ctx, f"[text] pause/stop file: saved latest.pt at step {step}, exit")
                raise Paused()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if step < c.steps:
        atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step}, d / "latest.pt")
        return {"partial": True, "step": step}
    atomic_save({"model": model.state_dict(), "step": step}, d / "final.pt")
    rec = {"steps": step, "skipped": skipped, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    e1.save_json(rec, d / "DONE.json")
    (d / "latest.pt").unlink(missing_ok=True)
    log(ctx, f"[text] DONE {rec}")
    return rec


# --- adaptation runs ------------------------------------------------------------------------------------


def run_name(arm: str, budget: str, seed: int, label_shuffle: bool = False) -> str:
    return f"{arm}-b{budget}-s{seed}" + ("-labelshuf" if label_shuffle else "")


def budget_code(budget: str) -> int:
    return 999_999 if budget == "all" else int(round(float(budget) * 100))


def init_model(ctx: Ctx, store: WillettStore, arm: str, seed: int) -> e1.XBody:
    torch.manual_seed(seed)
    model = e1.XBody(ctx.trunk, "willett", store.n_sessions)
    model.mean.copy_(torch.as_tensor(store.mean)); model.std.copy_(torch.as_tensor(store.std))
    if arm == "T":
        e1.load_trunk(model, torch.load(ctx.out / "text" / "final.pt", map_location="cpu", weights_only=True)["model"])
    elif arm in ("E", "S"):
        sd = torch.load(ctx.e_ckpt, map_location="cpu", weights_only=True)["model"]
        if arm == "S":
            sd = e1.shuffle_within_tensors(sd, 1000 + seed)
        e1.load_trunk(model, sd)
    elif arm != "R":
        raise ValueError(arm)
    return model.to(ctx.device)


@torch.no_grad()
def eval_set(ctx: Ctx, model: e1.XBody, store: WillettStore, idx: list[int], shuffle_seed: int | None = None,
             keep_text: bool = False) -> dict:
    """Batched causal eval (post-padding does not change earlier outputs). Per-sentence edits in ``idx`` order."""
    model.eval()
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    xs = {}
    for i in idx:
        x = store.x[i]
        xs[i] = x[rng.permutation(len(x))] if rng is not None else x
    order = sorted(idx, key=lambda i: store.length[i])
    edits, hyps = {}, {}
    k = 0
    while k < len(order):
        grp = [order[k]]
        k += 1
        while k < len(order) and store.length[order[k]] * (len(grp) + 1) <= ctx.ft.max_frames:
            grp.append(order[k]); k += 1
        b = e1.collate([(xs[i], store.tgt[i], store.meta[i]["session"]) for i in grp])
        lp = model(torch.from_numpy(b["x"]).to(ctx.device), torch.from_numpy(b["sess"]).to(ctx.device)).cpu().numpy()
        for j, i in enumerate(grp):
            e, n, h = e1.sentence_errors(lp[j, :store.length[i]], store.tgt[i])
            edits[i] = e
            hyps[i] = h
    ed = [edits[i] for i in idx]
    ref = [len(store.tgt[i]) for i in idx]
    out = {"cer": e1.pooled_cer(ed, ref), "edits": ed, "ref": ref}
    if keep_text:
        out["hyp"] = [hyps[i] for i in idx]
    return out


def train_run(ctx: Ctx, store: WillettStore, arm: str, budget: str, seed: int, label_shuffle: bool = False,
              max_steps: int | None = None) -> dict:
    name = run_name(arm, budget, seed, label_shuffle)
    d = ctx.out / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    c = ctx.ft
    total = int(c.steps[budget])
    bc = budget_code(budget)
    sub = e1.budget_subset(store.meta, store.splits["pool"], None if budget == "all" else float(budget),
                           ctx.raw["salt"], seed)
    tgt = {i: store.tgt[i] for i in sub}
    if label_shuffle:
        perm = e1.derangement(len(sub), np.random.default_rng([seed, 77]))
        tgt = {sub[j]: store.tgt[sub[int(perm[j])]] for j in range(len(sub))}
    model = init_model(ctx, store, arm, seed)
    opt = make_optim(model, c.weight_decay, c.lr)
    step, best = 0, {"cer": float("inf"), "step": -1}
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=ctx.device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        step, best = int(ck["step"]), {"cer": float(ck["best_cer"]), "step": int(ck["best_step"])}
        log(ctx, f"[{name}] resume at step {step} (best val {best['cer']:.4f} @ {best['step']})")
    e1.save_json({**LICENCE[arm], "arm": arm, "label_shuffle": label_shuffle}, d / "licence.json")

    def save_latest() -> None:
        atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step,
                     "best_cer": best["cer"], "best_step": best["step"]}, d / "latest.pt")

    end = total if max_steps is None else min(total, step + max_steps)
    t_ck = t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0
    val_idx = store.splits["val"]
    while step < end:
        rng = np.random.default_rng([seed, bc, int(label_shuffle), step])
        gen = torch.Generator().manual_seed(int(rng.integers(2 ** 62)))
        torch.manual_seed(int(rng.integers(2 ** 62)))
        bi = e1.pack_batch(sub, store.length, c.max_frames, rng)
        b = e1.collate([(store.x[i], tgt[i], store.meta[i]["session"]) for i in bi])
        model.train()
        for g in opt.param_groups:
            g["lr"] = e1.lr_at(step, total, c.lr, c.lr_min, c.warmup)
        x = torch.from_numpy(b["x"]).to(ctx.device)
        sess = torch.from_numpy(b["sess"]).to(ctx.device)
        xn = e1.augment_w(model.normalise(x, sess), torch.from_numpy(b["lengths"]), c, gen)
        lp = model(xn, sess, normalised=True)
        loss = F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(ctx.device),
                          torch.from_numpy(b["lengths"]), torch.from_numpy(b["target_lengths"]),
                          blank=e1.BLANK, reduction="mean", zero_infinity=True)
        opt.zero_grad(set_to_none=True)
        if torch.isfinite(loss):
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), c.clip); opt.step()
            losses.append(float(loss.detach()))
        else:
            skipped += 1
        step += 1
        if step % 100 == 0 or step == end:
            dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
            log(ctx, f"[{name}] step {step}/{total} loss {np.mean(losses) if losses else float('nan'):.4f} "
                     f"{dt:.3f} s/step skipped {skipped}")
            losses = []
        if step % c.val_every == 0 or step == total:
            v = eval_set(ctx, model, store, val_idx)
            with open(d / "metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"step": step, "val_cer": v["cer"]}) + "\n")
            if v["cer"] < best["cer"]:
                best = {"cer": v["cer"], "step": step}
                atomic_save({"model": model.state_dict(), "step": step, "val_cer": v["cer"]}, d / "best.pt")
            save_latest(); t_ck = time.time()
        elif time.time() - t_ck > 60 * c.ckpt_minutes:
            save_latest(); t_ck = time.time()
        if stop_requested(ctx):
            save_latest()
            log(ctx, f"[{name}] pause/stop file: saved latest.pt at step {step}, exit")
            raise Paused()
    if step < total:
        save_latest()
        return {"partial": True, "step": step}
    atomic_save({"model": model.state_dict(), "step": step}, d / "final.pt")
    test_idx = store.splits["test"]
    fin = eval_set(ctx, model, store, test_idx, keep_text=True)
    res = {"run": name, "arm": arm, "budget": budget, "seed": seed, "label_shuffle": label_shuffle,
           "steps": step, "skipped": skipped, "n_train": len(sub), "minutes": round(e1.minutes_of(store.meta, sub), 3),
           "test_cer_final": fin["cer"], "test_edits_final": fin["edits"], "test_ref": fin["ref"],
           "best_val_step": best["step"], "best_val_cer": best["cer"]}
    if budget in ctx.raw.get("c1_budgets", []) and not label_shuffle:
        res["c1_shuffled_cer"] = eval_set(ctx, model, store, test_idx, shuffle_seed=12345)["cer"]
    if (d / "best.pt").exists():
        model.load_state_dict(torch.load(d / "best.pt", map_location=ctx.device, weights_only=True)["model"])
        bv = eval_set(ctx, model, store, test_idx)
        res["test_cer_bestval"] = bv["cer"]; res["test_edits_bestval"] = bv["edits"]
    e1.save_json(res, d / "result.json")
    e1.save_json({"examples_final": list(zip([store.meta[i]["text"] for i in test_idx[:5]], fin["hyp"][:5]))},
                 d / "examples_local.json")
    e1.save_json({"done": time.strftime("%Y-%m-%dT%H:%M:%S")}, d / "DONE.json")
    (d / "latest.pt").unlink(missing_ok=True)
    log(ctx, f"[{name}] DONE test CER final {fin['cer']:.4f} bestval {res.get('test_cer_bestval', float('nan')):.4f} "
             f"(val best {best['cer']:.4f} @ {best['step']}) minutes {res['minutes']}"
             + (f" C1 {res['c1_shuffled_cer']:.4f}" if "c1_shuffled_cer" in res else ""))
    return res


def grid(ctx: Ctx) -> list[tuple[str, str, int, bool]]:
    """Run order: seed 0 before seed 1; small budgets first; C2 last."""
    g = [(a, b, s, False) for s in ctx.seeds for b in ctx.budgets for a in ctx.arms]
    c2 = ctx.raw["c2"]
    g.append((c2["arm"], c2["budget"], int(c2["seed"]), True))
    return g


def stage_grid(ctx: Ctx, store: WillettStore, max_steps: int | None = None) -> bool:
    for arm, b, s, ls in grid(ctx):
        r = train_run(ctx, store, arm, b, s, ls, max_steps=max_steps)
        if r.get("partial"):
            return False
    return True


# --- summary and verdict --------------------------------------------------------------------------------


def beats(cer: dict, edits: dict, ref: np.ndarray, a: str, b: str, budget: str, seeds: list, rules: dict,
          need_ci: bool = True) -> dict:
    """Does arm a beat arm b at a budget (plan rule)? cer[(arm, budget, seed)], edits[...] per-sentence."""
    ca = [cer[(a, budget, s)] for s in seeds]
    cb = [cer[(b, budget, s)] for s in seeds]
    delta = float(np.mean(cb) - np.mean(ca))
    spread = float(max(max(ca) - min(ca), max(cb) - min(cb)))
    ea = np.mean([edits[(a, budget, s)] for s in seeds], axis=0)
    eb = np.mean([edits[(b, budget, s)] for s in seeds], axis=0)
    bs = e1.bootstrap_delta(eb, ea, ref, n=int(rules["bootstrap_n"]), seed=int(rules["bootstrap_seed"]))
    win = delta > spread and delta > float(rules.get("win_min_abs", 0.0)) and (bs["lo"] > 0 or not need_ci)
    return {"a": a, "b": b, "budget": budget, "cer_a": float(np.mean(ca)), "cer_b": float(np.mean(cb)),
            "delta": delta, "spread": spread, "ci95": [bs["lo"], bs["hi"]], "win": bool(win)}


def minutes_to(curve: list[tuple[float, float]], thr: float) -> float | None:
    """First crossing of CER <= thr on a curve [(minutes, cer)], linear in log minutes."""
    pts = sorted(curve)
    for (m0, c0), (m1, c1) in zip(pts, pts[1:]):
        if c0 <= thr:
            return m0
        if c1 <= thr:
            f = (c0 - thr) / (c0 - c1)
            return float(np.exp(np.log(m0) + f * (np.log(m1) - np.log(m0))))
    return pts[0][0] if pts and pts[0][1] <= thr else None


def verdict(results: list[dict], raw: dict, seeds: list, budgets: list) -> dict:
    rules = raw["rules"]
    main = [r for r in results if not r["label_shuffle"]]
    cer = {(r["arm"], r["budget"], r["seed"]): r["test_cer_final"] for r in main}
    edits = {(r["arm"], r["budget"], r["seed"]): np.asarray(r["test_edits_final"], float) for r in main}
    ref = np.asarray(main[0]["test_ref"], float)
    arms = sorted({r["arm"] for r in main}, key=list(e1.ARMS).index)
    table = {a: {b: {"mean": float(np.mean([cer[(a, b, s)] for s in seeds])),
                     "seeds": [cer[(a, b, s)] for s in seeds],
                     "minutes": float(np.mean([r["minutes"] for r in main if r["arm"] == a and r["budget"] == b])),
                     "bestval_mean": float(np.mean([r.get("test_cer_bestval", np.nan) for r in main
                                                    if r["arm"] == a and r["budget"] == b]))}
                 for b in budgets} for a in arms}
    out: dict = {"table": table}
    best_all = min(table[a]["all"]["mean"] for a in arms) if "all" in budgets else min(
        table[a][budgets[-1]]["mean"] for a in arms)
    v1 = best_all <= rules["v1_max_cer_all"]
    out["V1"] = {"best_cer_all": best_all, "pass": bool(v1)}
    hb = raw["h_budgets"]
    for hid, (a, b) in {"H1": ("E", "T"), "H2": ("E", "R"), "H3": ("T", "R"), "H4": ("E", "S")}.items():
        if a not in arms or b not in arms:
            continue
        per = [beats(cer, edits, ref, a, b, bb, seeds, rules) for bb in hb]
        wins = sum(p["win"] for p in per)
        status = "pass" if wins >= rules["h_min_wins"] else ("partial" if wins == 1 else "fail")
        if not v1:
            status = "inconclusive"
        out[hid] = {"claim": f"{a} beats {b}", "per_budget": per, "wins": wins, "status": status}
    if "E" in arms and "T" in arms:
        per = [beats(cer, edits, ref, "E", "T", bb, seeds, rules, need_ci=False) for bb in raw["roadmap_rule_budgets"]]
        out["roadmap_rule"] = {"per_budget": per, "pass": bool(any(p["win"] for p in per))}
    c1 = []
    for r in main:
        if "c1_shuffled_cer" in r and r["test_cer_final"] <= rules["c1_applies_if_cer_below"]:
            c1.append({"run": r["run"], "cer": r["test_cer_final"], "shuffled": r["c1_shuffled_cer"],
                       "pass": r["c1_shuffled_cer"] >= rules["c1_min_cer"]})
    out["C1"] = {"runs": c1, "pass": bool(all(x["pass"] for x in c1)), "n_applicable": len(c1)}
    ls = [r for r in results if r["label_shuffle"]]
    if ls:
        r = ls[0]
        normal = cer[(r["arm"], r["budget"], r["seed"])]
        need = max(rules["c2_min_cer"], normal + rules["c2_min_gap"])
        out["C2"] = {"run": r["run"], "cer": r["test_cer_final"], "normal_cer": normal, "needed": need,
                     "pass": bool(r["test_cer_final"] >= need)}
    curve = {}
    for a in arms:
        pts = [(table[a][b]["minutes"], table[a][b]["mean"]) for b in budgets]
        curve[a] = {"points": pts, "minutes_to_cer": minutes_to(pts, rules["curve_cer_threshold"])}
    out["curve"] = {"threshold": rules["curve_cer_threshold"], "arms": curve}
    return out


def stage_summary(ctx: Ctx) -> dict:
    results = []
    for arm, b, s, ls in grid(ctx):
        p = ctx.out / "runs" / run_name(arm, b, s, ls) / "result.json"
        if not p.exists():
            raise FileNotFoundError(f"missing run {p.parent.name}")
        results.append(json.loads(p.read_text(encoding="utf-8")))
    v = verdict(results, ctx.raw, ctx.seeds, ctx.budgets)
    agg = {"note": "aggregate only; CER = total edits / total reference characters over the 80 test sentences "
                   "(last block of each Willett session), greedy CTC, no LM, final step; plan.md (60620ab)",
           "runs": [{k: r[k] for k in ("run", "arm", "budget", "seed", "label_shuffle", "steps", "skipped", "n_train",
                                       "minutes", "test_cer_final", "best_val_step", "best_val_cer")
                     if k in r} | {k: r[k] for k in ("test_cer_bestval", "c1_shuffled_cer") if k in r}
                    for r in results],
           "text_pretrain": json.loads((ctx.out / "text" / "DONE.json").read_text(encoding="utf-8")),
           "prep": json.loads((ctx.cache / "DONE.json").read_text(encoding="utf-8")),
           **v, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    e1.save_json(agg, ctx.out / "summary.json")
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, ctx.repo_results / "summary.json")
    log(ctx, "[summary] V1 %s H1 %s H2 %s H3 %s H4 %s C1 %s C2 %s" % (
        v["V1"]["pass"], v.get("H1", {}).get("status"), v.get("H2", {}).get("status"), v.get("H3", {}).get("status"),
        v.get("H4", {}).get("status"), v["C1"]["pass"], v.get("C2", {}).get("pass")))
    return agg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-08 E1a runner")
    ap.add_argument("stage", choices=("all", "prep", "text", "grid", "summary"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cache", default=None, help="Willett cache folder (default <out>/willett)")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--quick", action="store_true", help="dry run: few steps, seed 0, budgets 3 and all")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.quick and out.resolve() == OUT.resolve():
        print("--quick needs another --out", file=sys.stderr)
        return 2
    ctx = ctx_from_config(Path(a.config), out, a.device, Path(a.cache) if a.cache else None, quick=a.quick)
    torch.set_num_threads(4)
    log(ctx, f"start stage={a.stage} device={a.device} torch={torch.__version__} quick={a.quick} pid={os.getpid()}")
    keep_awake(True)
    try:
        if a.stage in ("all", "prep"):
            stage_prep(ctx)
        if a.stage in ("all", "text"):
            if stage_text(ctx).get("partial"):
                return 0
        if a.stage in ("all", "grid"):
            store = WillettStore(ctx.cache)
            if not stage_grid(ctx, store):
                return 0
        if a.stage in ("all", "summary"):
            stage_summary(ctx)
        if a.stage == "all":
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
            log(ctx, "ALL DONE")
    except Paused:
        return PAUSED
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
