r"""P15-33 runner: a low-data recipe for the E1 target (Willett handwriting) - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this task). Reuses the P15-08 E1a code
(e1.py, run.py) and its local Willett cache, text-only trunk and E checkpoint READ-ONLY. Writes only to
C:\Users\zhang\bci-data\derived\p15-33\.

Stages (``all`` runs them in order and skips finished parts; every training run resumes exactly):
  search   val-only recipe search: candidates A-D x arms R, E at 30 min, seed 0; a label-deranged run for
           every (candidate, arm) whose normal final val CER < 0.80. No test-block number is computed.
  select   pre-registered rule -> selection.json (val numbers only); copied to results/selection.json
  grid     selected recipe: arms R, T, E, S x budgets 3, 10, 30, 100, all x seeds 0, 1 + C2 run(s), test CER
  summary  P15-08 verdict code (V1, H1-H4, C1, C2, roadmap rule) -> summary.json (+ results/summary.json)

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-20-p15-33-low-data-recipe\p33.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
Re-run the same command to resume.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
P8_DIR = HERE.parent / "2026-11-19-p15-08-e1-cross-body"
sys.path.insert(0, str(P8_DIR))
import e1  # noqa: E402
import run as R8  # noqa: E402

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-33")
P8_OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-08")
PAUSED = 3


class Paused(Exception):
    pass


@dataclass
class Recipe:
    name: str
    freeze_trunk: bool
    lr: float
    warmup: int
    weight_decay: float
    dropout: float
    offset_sd: float
    noise_sd: float
    time_masks: int
    time_mask_max: int
    chan_drop: float
    stretch_lo: float
    stretch_hi: float
    lr_min: float = 1e-6
    clip: float = 1.0
    max_frames: int = 24_000
    val_every: int = 100
    ckpt_minutes: float = 4.0
    steps: dict = field(default_factory=dict)


def recipe_from(raw: dict, name: str) -> Recipe:
    c = raw["candidates"][name]
    return Recipe(name=name, freeze_trunk=bool(c["freeze_trunk"]), lr=float(c["lr"]), warmup=int(c["warmup"]),
                  weight_decay=float(c["weight_decay"]), dropout=float(c["dropout"]), **raw[c["aug"]],
                  **{k: v for k, v in raw["common"].items()})


@dataclass
class Ctx:
    out: Path
    cache: Path
    raw: dict
    device: str
    trunk: dict
    e_ckpt: Path
    text_ckpt: Path
    seeds: list
    budgets: list
    arms: list
    repo_results: Path | None = None


def ctx_from_config(path: Path, out: Path, device: str) -> Ctx:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ctx(out=out, cache=Path(raw["willett_cache"]), raw=raw, device=device, trunk=dict(raw["trunk"]),
               e_ckpt=Path(raw["e_checkpoint"]), text_ckpt=Path(raw["text_checkpoint"]), seeds=list(raw["seeds"]),
               budgets=list(raw["budgets_min"]), arms=list(raw["arms"]), repo_results=HERE / "results")


def log(ctx: Ctx, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(ctx.out / "run.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def stop_requested(ctx: Ctx) -> bool:
    return (ctx.out / "pause").exists() or (ctx.out / "stop").exists()


# --- model, freezing, augmentation -------------------------------------------------------------------------


def trunk_cfg(ctx: Ctx, rec: Recipe) -> e1.TrunkCfg:
    t = dict(ctx.trunk); t["dilations"] = tuple(t["dilations"]); t["dropout"] = rec.dropout
    return e1.TrunkCfg(**t)


def init_model(ctx: Ctx, store, rec: Recipe, arm: str, seed: int) -> e1.XBody:
    """Same init as P15-08 (seeded stem; T / E / S trunks), with the recipe's dropout and freezing."""
    torch.manual_seed(seed)
    model = e1.XBody(trunk_cfg(ctx, rec), "willett", store.n_sessions)
    model.mean.copy_(torch.as_tensor(store.mean)); model.std.copy_(torch.as_tensor(store.std))
    if arm == "T":
        e1.load_trunk(model, torch.load(ctx.text_ckpt, map_location="cpu", weights_only=True)["model"])
    elif arm in ("E", "S"):
        sd = torch.load(ctx.e_ckpt, map_location="cpu", weights_only=True)["model"]
        if arm == "S":
            sd = e1.shuffle_within_tensors(sd, 1000 + seed)
        e1.load_trunk(model, sd)
    elif arm != "R":
        raise ValueError(arm)
    if rec.freeze_trunk:
        for n, p in model.named_parameters():
            if n.startswith("blocks."):
                p.requires_grad_(False)
    return model.to(ctx.device)


def set_train(model: e1.XBody, rec: Recipe) -> None:
    model.train()
    if rec.freeze_trunk:
        model.blocks.eval()  # frozen trunk = fixed feature map (no dropout noise inside it)


def make_optim(model: torch.nn.Module, rec: Recipe) -> torch.optim.Optimizer:
    decay, no_decay = [], []
    for n, p in model.named_parameters():
        if p.requires_grad:
            (no_decay if p.ndim < 2 or "norm" in n else decay).append(p)
    return torch.optim.AdamW([{"params": decay, "weight_decay": rec.weight_decay},
                              {"params": no_decay, "weight_decay": 0.0}], lr=rec.lr)


def n_trainable(model: torch.nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))


def stretch(x: np.ndarray, r: float) -> np.ndarray:
    """Linear time resampling of (T, C) to round(T * r) frames (speed change, labels unchanged)."""
    T = len(x)
    n = max(2, int(round(T * r)))
    if n == T or T < 2:
        return np.asarray(x, np.float32)
    t = np.linspace(0.0, T - 1.0, n)
    i0 = np.floor(t).astype(np.int64); i1 = np.minimum(i0 + 1, T - 1); f = (t - i0)[:, None].astype(np.float32)
    xf = np.asarray(x, np.float32)
    return xf[i0] * (1 - f) + xf[i1] * f


def augment(xn: torch.Tensor, lengths: torch.Tensor, rec: Recipe, gen: torch.Generator) -> torch.Tensor:
    """P15-08 augmentation (offset, noise, time masks) + channel dropout (whole electrodes per sentence)."""
    xn = e1.augment_w(xn, lengths, rec, gen)
    if rec.chan_drop > 0:
        B, _, C = xn.shape
        keep = (torch.rand((B, 1, C), generator=gen) >= rec.chan_drop).float().to(xn.device)
        xn = xn * keep
    return xn


# --- one training run ------------------------------------------------------------------------------------


def _ectx(ctx: Ctx, rec: Recipe):
    return SimpleNamespace(ft=SimpleNamespace(max_frames=rec.max_frames), device=ctx.device)


def train_run(ctx: Ctx, store, rec: Recipe, arm: str, budget: str, seed: int, label_shuffle: bool, d: Path,
              do_test: bool, max_steps: int | None = None) -> dict:
    """Train one run into ``d``. Batch k depends only on (seed, budget, label_shuffle, k): exact resume.
    ``do_test`` False (search): only val numbers are computed. True (grid): the P15-08 test readout."""
    name = R8.run_name(arm, budget, seed, label_shuffle)
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    total = int(rec.steps[budget])
    bc = R8.budget_code(budget)
    sub = e1.budget_subset(store.meta, store.splits["pool"], None if budget == "all" else float(budget),
                           ctx.raw["salt"], seed)
    tgt = {i: store.tgt[i] for i in sub}
    if label_shuffle:
        perm = e1.derangement(len(sub), np.random.default_rng([seed, 77]))
        tgt = {sub[j]: store.tgt[sub[int(perm[j])]] for j in range(len(sub))}
    model = init_model(ctx, store, rec, arm, seed)
    opt = make_optim(model, rec)
    step, best = 0, {"cer": float("inf"), "step": -1}
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=ctx.device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        step, best = int(ck["step"]), {"cer": float(ck["best_cer"]), "step": int(ck["best_step"])}
        log(ctx, f"[{rec.name}/{name}] resume at step {step} (best val {best['cer']:.4f} @ {best['step']})")
        # metrics.jsonl may hold val lines written after the checkpoint: drop them (exact resume).
        mp = d / "metrics.jsonl"
        if mp.exists():
            keep = [ln for ln in mp.read_text(encoding="utf-8").splitlines() if ln and json.loads(ln)["step"] <= step]
            mp.write_text("".join(k + "\n" for k in keep), encoding="utf-8")
    e1.save_json({**R8.LICENCE[arm], "arm": arm, "label_shuffle": label_shuffle, "recipe": rec.name}, d / "licence.json")
    e1.save_json({"recipe": rec.__dict__, "trainable_params": n_trainable(model)}, d / "config.json")

    def save_latest() -> None:
        R8.atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step,
                        "best_cer": best["cer"], "best_step": best["step"]}, d / "latest.pt")

    ectx = _ectx(ctx, rec)
    end = total if max_steps is None else min(total, step + max_steps)
    t_ck = t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0
    val_idx = store.splits["val"]
    while step < end:
        rng = np.random.default_rng([seed, bc, int(label_shuffle), step])
        gen = torch.Generator().manual_seed(int(rng.integers(2 ** 62)))
        torch.manual_seed(int(rng.integers(2 ** 62)))
        bi = e1.pack_batch(sub, store.length, rec.max_frames, rng)
        if rec.stretch_hi > rec.stretch_lo:
            rs = rng.uniform(rec.stretch_lo, rec.stretch_hi, len(bi))
            items = [(stretch(store.x[i], float(r)), tgt[i], store.meta[i]["session"]) for i, r in zip(bi, rs)]
        else:
            items = [(store.x[i], tgt[i], store.meta[i]["session"]) for i in bi]
        b = e1.collate(items)
        set_train(model, rec)
        for g in opt.param_groups:
            g["lr"] = e1.lr_at(step, total, rec.lr, rec.lr_min, rec.warmup)
        x = torch.from_numpy(b["x"]).to(ctx.device)
        sess = torch.from_numpy(b["sess"]).to(ctx.device)
        lengths = torch.from_numpy(b["lengths"])
        xn = augment(model.normalise(x, sess), lengths, rec, gen)
        # Zero the padding after normalisation (stretched items are float; padding must stay neutral).
        pad = (torch.arange(xn.shape[1])[None, :] >= lengths[:, None]).to(xn.device)
        xn = xn.masked_fill(pad[:, :, None], 0.0)
        lp = model(xn, sess, normalised=True)
        loss = F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(ctx.device), lengths,
                          torch.from_numpy(b["target_lengths"]), blank=e1.BLANK, reduction="mean", zero_infinity=True)
        opt.zero_grad(set_to_none=True)
        if torch.isfinite(loss):
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], rec.clip)
            opt.step()
            losses.append(float(loss.detach()))
        else:
            skipped += 1
        step += 1
        if step % 100 == 0 or step == end:
            dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
            log(ctx, f"[{rec.name}/{name}] step {step}/{total} loss {np.mean(losses) if losses else float('nan'):.4f} "
                     f"{dt:.3f} s/step skipped {skipped}")
            losses = []
        if step % rec.val_every == 0 or step == total:
            v = R8.eval_set(ectx, model, store, val_idx)
            with open(d / "metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"step": step, "val_cer": v["cer"]}) + "\n")
            if v["cer"] < best["cer"]:
                best = {"cer": v["cer"], "step": step}
                R8.atomic_save({"model": model.state_dict(), "step": step, "val_cer": v["cer"]}, d / "best.pt")
            save_latest(); t_ck = time.time()
        elif time.time() - t_ck > 60 * rec.ckpt_minutes:
            save_latest(); t_ck = time.time()
        if stop_requested(ctx):
            save_latest()
            log(ctx, f"[{rec.name}/{name}] pause/stop file: saved latest.pt at step {step}, exit")
            raise Paused()
    if step < total:
        save_latest()
        return {"partial": True, "step": step}
    R8.atomic_save({"model": model.state_dict(), "step": step}, d / "final.pt")
    return finish_run(ctx, store, rec, arm, budget, seed, label_shuffle, d, do_test, model, best, skipped, sub)


def finish_run(ctx: Ctx, store, rec: Recipe, arm: str, budget: str, seed: int, label_shuffle: bool, d: Path,
               do_test: bool, model: e1.XBody, best: dict, skipped: int, sub: list[int]) -> dict:
    """Readout of a finished run (final weights in ``model``). Search: val only. Grid: P15-08 test readout."""
    name = R8.run_name(arm, budget, seed, label_shuffle)
    ectx = _ectx(ctx, rec)
    val_idx = store.splits["val"]
    vf = R8.eval_set(ectx, model, store, val_idx)
    res = {"run": name, "recipe": rec.name, "arm": arm, "budget": budget, "seed": seed, "label_shuffle": label_shuffle,
           "steps": int(rec.steps[budget]), "skipped": skipped, "n_train": len(sub),
           "minutes": round(e1.minutes_of(store.meta, sub), 3), "trainable_params": n_trainable(model),
           "val_cer_final": vf["cer"], "best_val_step": best["step"], "best_val_cer": best["cer"]}
    if not do_test:
        res["val_shuffled_cer_final"] = R8.eval_set(ectx, model, store, val_idx,
                                                    shuffle_seed=int(ctx.raw["search"]["shuffle_seed"]))["cer"]
    else:
        test_idx = store.splits["test"]
        fin = R8.eval_set(ectx, model, store, test_idx, keep_text=True)
        res.update({"test_cer_final": fin["cer"], "test_edits_final": fin["edits"], "test_ref": fin["ref"]})
        if budget in ctx.raw.get("c1_budgets", []) and not label_shuffle:
            res["c1_shuffled_cer"] = R8.eval_set(ectx, model, store, test_idx, shuffle_seed=12345)["cer"]
        if (d / "best.pt").exists():
            model.load_state_dict(torch.load(d / "best.pt", map_location=ctx.device, weights_only=True)["model"])
            bv = R8.eval_set(ectx, model, store, test_idx)
            res["test_cer_bestval"] = bv["cer"]; res["test_edits_bestval"] = bv["edits"]
        e1.save_json({"examples_final": list(zip([store.meta[i]["text"] for i in test_idx[:5]], fin["hyp"][:5]))},
                     d / "examples_local.json")
    e1.save_json(res, d / "result.json")
    e1.save_json({"done": time.strftime("%Y-%m-%dT%H:%M:%S")}, d / "DONE.json")
    (d / "latest.pt").unlink(missing_ok=True)
    msg = (f"test CER final {res['test_cer_final']:.4f}" if do_test else
           f"val CER final {res['val_cer_final']:.4f} val shuffled {res['val_shuffled_cer_final']:.4f}")
    log(ctx, f"[{rec.name}/{name}] DONE {msg} (val best {best['cer']:.4f} @ {best['step']}) minutes {res['minutes']}"
             + (f" C1 {res['c1_shuffled_cer']:.4f}" if "c1_shuffled_cer" in res else ""))
    return res


# --- search and selection -----------------------------------------------------------------------------------


def search_dir(ctx: Ctx, cand: str, arm: str, budget: str, seed: int, ls: bool) -> Path:
    return ctx.out / "search" / cand / R8.run_name(arm, budget, seed, ls)


def stage_search(ctx: Ctx, store, max_steps: int | None = None) -> bool:
    s = ctx.raw["search"]
    b, seed = s["budget"], int(s["seed"])
    for cand in ctx.raw["candidates"]:
        rec = recipe_from(ctx.raw, cand)
        for arm in s["arms"]:
            r = train_run(ctx, store, rec, arm, b, seed, False, search_dir(ctx, cand, arm, b, seed, False), False, max_steps)
            if r.get("partial"):
                return False
            if r["val_cer_final"] < float(s["eligible_max_val_cer"]):
                r2 = train_run(ctx, store, rec, arm, b, seed, True, search_dir(ctx, cand, arm, b, seed, True), False,
                               max_steps)
                if r2.get("partial"):
                    return False
    return True


def select(ctx: Ctx) -> dict:
    """Pre-registered rule (plan.md): an arm passes val-C2 if it is eligible (normal final val CER < 0.80) and
    its deranged final val CER >= max(0.75, normal + 0.10). A candidate passes if >= 1 arm passes. Pick the
    passing candidate with the lowest normal final val CER over its passing arms; tie -> fewer trainable params."""
    s = ctx.raw["search"]
    b, seed = s["budget"], int(s["seed"])
    rows, passing = [], []
    for cand in ctx.raw["candidates"]:
        best_arm = None
        for arm in s["arms"]:
            r = json.loads((search_dir(ctx, cand, arm, b, seed, False) / "result.json").read_text(encoding="utf-8"))
            row = {"candidate": cand, "arm": arm, "val_cer": r["val_cer_final"], "val_shuffled_cer": r["val_shuffled_cer_final"],
                   "best_val_cer": r["best_val_cer"], "trainable_params": r["trainable_params"],
                   "eligible": r["val_cer_final"] < float(s["eligible_max_val_cer"])}
            p2 = search_dir(ctx, cand, arm, b, seed, True) / "result.json"
            if row["eligible"] and p2.exists():
                r2 = json.loads(p2.read_text(encoding="utf-8"))
                need = max(float(s["c2_min_cer"]), r["val_cer_final"] + float(s["c2_min_gap"]))
                row.update({"deranged_val_cer": r2["val_cer_final"], "needed": need,
                            "c2_val_pass": bool(r2["val_cer_final"] >= need)})
            else:
                row["c2_val_pass"] = False
            rows.append(row)
            if row["c2_val_pass"] and (best_arm is None or row["val_cer"] < best_arm["val_cer"]):
                best_arm = row
        if best_arm is not None:
            passing.append(best_arm)
    passing.sort(key=lambda r: (r["val_cer"], r["trainable_params"]))
    sel = {"note": "val block only (no test-block number); plan.md rule", "rows": rows,
           "selected": passing[0]["candidate"] if passing else None,
           "selected_arm": passing[0]["arm"] if passing else None, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return sel


def stage_select(ctx: Ctx) -> dict:
    p = ctx.out / "selection.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    sel = select(ctx)
    e1.save_json(sel, p)
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(sel, ctx.repo_results / "selection.json")
    log(ctx, f"[select] selected {sel['selected']} (arm {sel['selected_arm']})")
    return sel


# --- grid with the selected recipe -------------------------------------------------------------------------


def grid_list(ctx: Ctx, sel: dict) -> list[tuple[str, str, int, bool]]:
    g = [(a, b, s, False) for s in ctx.seeds for b in ctx.budgets for a in ctx.arms]
    c2 = ctx.raw["c2"]
    g.append((c2["arm"], c2["budget"], int(c2["seed"]), True))
    if sel["selected_arm"] and sel["selected_arm"] != c2["arm"]:
        g.append((sel["selected_arm"], c2["budget"], int(c2["seed"]), True))
    return g


def grid_run(ctx: Ctx, store, rec: Recipe, arm: str, budget: str, seed: int, ls: bool, max_steps: int | None = None) -> dict:
    d = ctx.out / "grid" / R8.run_name(arm, budget, seed, ls)
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    src = search_dir(ctx, rec.name, arm, budget, seed, ls)
    s = ctx.raw["search"]
    if budget == s["budget"] and seed == int(s["seed"]) and (src / "DONE.json").exists() and (src / "final.pt").exists():
        # Same recipe, arm, budget, seed and batches as the search run: reuse its weights, add the test readout.
        d.mkdir(parents=True, exist_ok=True)
        for f in ("final.pt", "best.pt", "metrics.jsonl"):
            if (src / f).exists():
                shutil.copy(src / f, d / f)
        sr = json.loads((src / "result.json").read_text(encoding="utf-8"))
        e1.save_json({**R8.LICENCE[arm], "arm": arm, "label_shuffle": ls, "recipe": rec.name,
                      "reused_from": str(src)}, d / "licence.json")
        model = init_model(ctx, store, rec, arm, seed)
        model.load_state_dict(torch.load(d / "final.pt", map_location=ctx.device, weights_only=True)["model"])
        sub = e1.budget_subset(store.meta, store.splits["pool"], float(budget), ctx.raw["salt"], seed)
        log(ctx, f"[{rec.name}/{R8.run_name(arm, budget, seed, ls)}] reuse search weights for the test readout")
        return finish_run(ctx, store, rec, arm, budget, seed, ls, d, True, model,
                          {"cer": sr["best_val_cer"], "step": sr["best_val_step"]}, sr["skipped"], sub)
    return train_run(ctx, store, rec, arm, budget, seed, ls, d, True, max_steps)


def stage_grid(ctx: Ctx, store, sel: dict, max_steps: int | None = None) -> bool:
    rec = recipe_from(ctx.raw, sel["selected"])
    for arm, b, s, ls in grid_list(ctx, sel):
        r = grid_run(ctx, store, rec, arm, b, s, ls, max_steps)
        if r.get("partial"):
            return False
    return True


def stage_summary(ctx: Ctx, sel: dict) -> dict:
    results = []
    for arm, b, s, ls in grid_list(ctx, sel):
        p = ctx.out / "grid" / R8.run_name(arm, b, s, ls) / "result.json"
        if not p.exists():
            raise FileNotFoundError(f"missing run {p.parent.name}")
        results.append(json.loads(p.read_text(encoding="utf-8")))
    v = R8.verdict(results, ctx.raw, ctx.seeds, ctx.budgets)
    rules = ctx.raw["rules"]
    main = {(r["arm"], r["budget"], r["seed"]): r["test_cer_final"] for r in results if not r["label_shuffle"]}
    c2_all = []
    for r in results:
        if r["label_shuffle"]:
            normal = main[(r["arm"], r["budget"], r["seed"])]
            need = max(rules["c2_min_cer"], normal + rules["c2_min_gap"])
            c2_all.append({"run": r["run"], "cer": r["test_cer_final"], "normal_cer": normal, "needed": need,
                           "pass": bool(r["test_cer_final"] >= need)})
    keys = ("run", "recipe", "arm", "budget", "seed", "label_shuffle", "steps", "skipped", "n_train", "minutes",
            "trainable_params", "test_cer_final", "val_cer_final", "best_val_step", "best_val_cer",
            "test_cer_bestval", "c1_shuffled_cer")
    agg = {"note": "aggregate only; CER = total edits / total reference characters over the 80 test sentences (last "
                   "block of each Willett session), greedy CTC, no LM, final step; recipe chosen on the val block "
                   "only (selection.json); plan.md",
           "recipe": recipe_from(ctx.raw, sel["selected"]).__dict__, "selection": sel,
           "runs": [{k: r[k] for k in keys if k in r} for r in results], **v, "C2_all": c2_all,
           "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    e1.save_json(agg, ctx.out / "summary.json")
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, ctx.repo_results / "summary.json")
    log(ctx, "[summary] V1 %s H1 %s H2 %s H3 %s H4 %s C1 %s C2 %s" % (
        v["V1"]["pass"], v.get("H1", {}).get("status"), v.get("H2", {}).get("status"), v.get("H3", {}).get("status"),
        v.get("H4", {}).get("status"), v["C1"]["pass"], [c["pass"] for c in c2_all]))
    return agg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-33 runner")
    ap.add_argument("stage", choices=("all", "search", "select", "grid", "summary"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if out.resolve() == P8_OUT.resolve() or P8_OUT.resolve() in out.resolve().parents:
        print("never write into the P15-08 folder", file=sys.stderr)
        return 2
    ctx = ctx_from_config(Path(a.config), out, a.device)
    torch.set_num_threads(2)
    log(ctx, f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    R8.keep_awake(True)
    try:
        store = R8.WillettStore(ctx.cache)
        if a.stage in ("all", "search"):
            if not stage_search(ctx, store):
                return 0
        if a.stage in ("all", "select", "grid", "summary"):
            sel = stage_select(ctx)
            if sel["selected"] is None:
                log(ctx, "[select] no candidate passes val-C2: stop (no test grid; plan.md)")
                if a.stage == "all":
                    (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " no_recipe", encoding="utf-8")
                return 0
            if a.stage in ("all", "grid"):
                if not stage_grid(ctx, store, sel):
                    return 0
            if a.stage in ("all", "summary"):
                stage_summary(ctx, sel)
        if a.stage == "all":
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
            log(ctx, "ALL DONE")
    except Paused:
        return PAUSED
    finally:
        R8.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
