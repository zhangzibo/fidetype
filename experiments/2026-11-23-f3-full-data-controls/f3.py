r"""P15-50 runner: F3 at full data with tuned R+ / E+ arms, T, I (T15 trunk) and repeated deranged controls (gap 210).

Our own code, Apache-2.0. Plan: plan.md (pre-registered, 29c1dc9). Configuration: config.json.

Reuses READ-ONLY and UNCHANGED: P15-08 ``run.py`` (``train_run``, ``ctx_from_config``, ``WillettStore``) and ``e1.py``.
train_run is called as it is. This wrapper only sets, per run group, its own output folder, the LR and the step count of
the recipe (from selection.json), and it installs four small hooks in the P15-08 module namespace:
  - ``R8.log`` -> one central log in --out (stage-1 lines that carry a test CER are sealed: stage 1 reads val only);
  - ``R8.stop_requested`` -> a pause / stop file in --out;
  - ``R8.init_model`` -> also knows arm "I" (T15 trunk) and loads arm T from the P15-08 text checkpoint (read only);
  - ``e1.derangement`` (only during a deranged run j) -> derangement RNG [seed, 77 + j] (plan.md); j = 0 is the
    P15-08 value [seed, 77].
K arm: not run (dependency), see config.json.

Stages (``all`` runs them in order; finished parts are skipped; every part resumes from its checkpoint):
  s1        24 tuning runs (R, E x LR {2.5e-4, 5e-4, 1e-3} x steps {3,000, 6,000} x seeds 10, 11)
  select    selection.json (val CER at the final step only; written to --out and results/)
  pretrainI arm I trunk: 30,000 steps of phoneme CTC on T15 train trials
  gate      stage 2 starts only if results/selection.json is committed and on origin/main (plan stop rule)
  s2        groups in plan order (E+ R+ normal, E+ deranged x3, R+ deranged, T, I, I deranged); GPU cap 45 h
  summary   H1-H4, C1, C2, V1, outcome -> summary.json (aggregates only, also results/summary.json)

Run (repo root, GPU venv): C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-f3-full-data-controls\f3.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
Exit code 4 = stage 1 and I pretraining are done, waiting for the selection commit (re-run after the push).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import gc
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P08_DIR = HERE.parent / "2026-11-19-p15-08-e1-cross-body"
sys.path.insert(0, str(P08_DIR))
import e1  # noqa: E402
import run as R8  # noqa: E402

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-50")
DERIVED = Path(r"C:\Users\zhang\bci-data\derived")
SEL_REPO = HERE / "results" / "selection.json"
PAUSED, WAITING = 3, 4
LICENCE_I = {"data": ["Willett handwriting (CC0-1.0)", "T15 B2T'25 copy-task neural data (CC0-1.0)"],
             "research_only": False}
LICENCE_PRE_I = {"data": ["T15 B2T'25 copy-task neural data (CC0-1.0)"], "research_only": False}


class CapReached(Exception):
    pass


# --- pure rules ------------------------------------------------------------------------------------------------------


def cell_name(arm: str, lr: float, steps: int) -> str:
    return f"{arm}-lr{lr:g}-st{steps}"


def select_cell(cells: list[dict], thr: float) -> dict:
    """cells: [{"lr", "steps", "val": {seed: final-step val CER}}]. Lowest mean val CER over the tuning seeds;
    a cell with any seed > thr is excluded; ties: smaller LR, then fewer steps. Raises if every cell is excluded."""
    ok = []
    for c in cells:
        v = [float(x) for x in c["val"].values()]
        if not v or any(x > thr for x in v):
            continue
        ok.append((float(np.mean(v)), float(c["lr"]), int(c["steps"]), c))
    if not ok:
        raise RuntimeError("every grid cell is excluded (plan.md has no fallback): stop and report")
    ok.sort(key=lambda t: (t[0], t[1], t[2]))
    best = ok[0][3]
    return {"lr": float(best["lr"]), "steps": int(best["steps"]), "mean_val_cer": ok[0][0]}


T975 = {1: 12.706204736174698, 2: 4.302652729749464, 3: 3.182446305284263, 4: 2.7764451051977987,
        5: 2.570581835636314, 6: 2.4469118511449692}


def t_ci(x: list[float]) -> tuple[float, float, float]:
    """Mean and two-sided 95 % one-sample t interval (n - 1 df)."""
    a = np.asarray(x, float)
    m = float(a.mean())
    if len(a) < 2:
        return m, float("nan"), float("nan")
    h = T975[len(a) - 1] * float(a.std(ddof=1)) / math.sqrt(len(a))
    return m, m - h, m + h


def pair_rule(a: str, b: str, runs: dict, rules: dict, seeds: list[int]) -> dict:
    """'a beats b' (plan.md): d_s = CER_b - CER_a; (a) paired sentence bootstrap CI95 of d_s above 0 on >= 4 of 5
    seeds and (b) 5-seed mean of d_s > 0 with a one-sample t CI95 above 0. runs[(arm, seed)] = result dict."""
    per, have = [], [s for s in seeds if (a, s) in runs and (b, s) in runs]
    for s in have:
        ra, rb = runs[(a, s)], runs[(b, s)]
        ref = np.asarray(ra["test_ref"], float)
        if not np.array_equal(ref, np.asarray(rb["test_ref"], float)):
            raise RuntimeError("test references differ")
        bs = e1.bootstrap_delta(np.asarray(rb["test_edits_final"], float), np.asarray(ra["test_edits_final"], float),
                                ref, n=int(rules["bootstrap_n"]), seed=int(rules["bootstrap_seed"]))
        per.append({"seed": s, "cer_a": ra["test_cer_final"], "cer_b": rb["test_cer_final"],
                    "d": rb["test_cer_final"] - ra["test_cer_final"], "ci95": [bs["lo"], bs["hi"]],
                    "ci_above_0": bool(bs["lo"] > 0)})
    out = {"a": a, "b": b, "per_seed": per, "n_seeds": len(per)}
    if len(per) < len(seeds):
        out.update({"status": "not_run", "pass": None})
        return out
    n_ci = sum(p["ci_above_0"] for p in per)
    m, lo, hi = t_ci([p["d"] for p in per])
    pa = n_ci >= int(rules["seed_ci_min_wins"])
    pb = m > 0 and lo > 0
    out.update({"n_ci_above_0": n_ci, "mean_d": m, "t_ci95": [lo, hi], "part_a": bool(pa), "part_b": bool(pb),
                "pass": bool(pa and pb), "status": "done"})
    return out


def c2_need(rules: dict, normal: float) -> float:
    return max(float(rules["c2_min_cer"]), float(normal) + float(rules["c2_min_gap"]))


def c2_seed(normal: float | None, deranged: list[float | None], rules: dict, n_needed: int) -> dict:
    """One seed of one arm. E+ (3 runs): mean of the 3 >= need and >= 2 of 3 individually >= need. Others: the
    single run >= need."""
    if normal is None or len(deranged) < n_needed or any(d is None for d in deranged):
        return {"status": "missing", "pass": None, "normal": normal, "deranged": deranged}
    need = c2_need(rules, normal)
    ind = [bool(d >= need) for d in deranged]
    if n_needed == 1:
        ok = ind[0]
    else:
        ok = bool(float(np.mean(deranged)) >= need and sum(ind) >= int(rules["c2_e_min_individual"]))
    return {"status": "done", "normal": float(normal), "deranged": [float(d) for d in deranged],
            "deranged_mean": float(np.mean(deranged)), "needed": need, "individual_pass": ind,
            "margin_mean": float(np.mean(deranged)) - need, "pass": bool(ok)}


def all_seeds_pass(rows: dict) -> bool | None:
    """True if every seed passes, False if any done seed fails, None if some seed is missing and none fails."""
    vals = [r["pass"] for r in rows.values()]
    if any(v is False for v in vals):
        return False
    if any(v is None for v in vals):
        return None
    return True


def c1_rows(results: list[dict], rules: dict) -> list[dict]:
    out = []
    for r in results:
        if r["test_cer_final"] <= rules["c1_applies_if_cer_below"]:
            out.append({"run": r["run"], "cer": r["test_cer_final"], "shuffled": r.get("c1_shuffled_cer"),
                        "pass": r.get("c1_shuffled_cer") is not None and r["c1_shuffled_cer"] >= rules["c1_min_cer"]})
    return out


def outcome(v1: bool | None, h: dict, valid: dict) -> dict:
    """plan.md outcomes. h[id] = pair rule dicts (H1 E>R, H2 E>T, H1swap R>E, H2swap T>E, H3, H4); valid[arm] =
    C1 and C2 pass on every seed (True / False / None)."""
    def p(k):
        return bool(h.get(k, {}).get("pass"))

    labels = []
    if v1 is not True:
        return {"label": "N" if v1 is False else "not_determined", "labels": [], "why": "V1 gate"}
    e_ok, r_ok = valid.get("E") is True, valid.get("R") is True
    if p("H1") and p("H2"):
        labels.append("A" if e_ok else "N")
    if p("H1swap"):
        labels.append("C" if r_ok else "N")
    if p("H2") and not p("H1"):
        labels.append("B" if e_ok else "N")
    if p("H1") and not p("H2"):
        labels.append("H1-only (no pre-registered label)" if e_ok else "N")
    if p("H3"):
        labels.append("A-clean" if valid.get("K") is True else "N")
    if not any(p(k) for k in ("H1", "H2", "H1swap", "H2swap")):
        labels.append("D")
    main = next((x for x in ("A", "C", "B", "H1-only (no pre-registered label)", "N", "D") if x in labels), "D")
    return {"label": main, "labels": labels}


def check_out(out: Path, derived: Path = DERIVED, own: str = "p15-50") -> bool:
    out = out.resolve()
    d = derived.resolve()
    if out == d:
        return False
    if d in out.parents:
        return out.relative_to(d).parts[0] == own
    return True


def stage2_plan(cfg: dict) -> list[dict]:
    """Ordered list of stage-2 runs: {group, arm, seed, deranged, j, dir}."""
    out = []
    for g in cfg["stage2"]["groups_in_order"]:
        for s in cfg["stage2"]["seeds"]:
            for arm in g["arms"]:
                if g["deranged"]:
                    for j in range(int(g["n_deranged"])):
                        out.append({"group": g["name"], "arm": arm, "seed": s, "deranged": True, "j": j,
                                    "dir": f"s2/{arm}-d{j}"})
                else:
                    out.append({"group": g["name"], "arm": arm, "seed": s, "deranged": False, "j": None,
                                "dir": f"s2/{arm}"})
    return out


# --- GPU clock -------------------------------------------------------------------------------------------------------


class Clock:
    def __init__(self, path: Path):
        self.path = path
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.base = float(old.get("seconds", 0.0))
        self.launches = old.get("launches", []) + [{"start": time.strftime("%Y-%m-%dT%H:%M:%S")}]
        self.t0 = time.time()

    def hours(self) -> float:
        return (self.base + time.time() - self.t0) / 3600.0

    def save(self) -> None:
        self.launches[-1]["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.launches[-1]["seconds"] = round(time.time() - self.t0, 1)
        e1.save_json({"seconds": round(self.base + time.time() - self.t0, 1), "launches": self.launches}, self.path)


# --- hooks into the P15-08 module ----------------------------------------------------------------------------------


class Hooks:
    def __init__(self, out: Path, cfg: dict):
        self.out, self.cfg, self.seal = out, cfg, False
        self._orig_init = R8.init_model
        R8.log = self.log
        R8.stop_requested = lambda ctx: (self.out / "pause").exists() or (self.out / "stop").exists()
        R8.init_model = self.init_model
        R8.LICENCE["I"] = LICENCE_I

    def log(self, ctx, msg: str) -> None:
        if self.seal and "test CER" in msg:
            msg = msg.split(" DONE ")[0] + " DONE (stage 1: test CER sealed in result.json, never read)"
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(self.out / "run.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def init_model(self, ctx, store, arm: str, seed: int):
        if arm == "T":
            return self._orig_init(dataclasses.replace(ctx, out=Path(self.cfg["sources"]["p15_08_out_for_T"])),
                                   store, arm, seed)
        if arm == "I":
            torch.manual_seed(seed)
            model = e1.XBody(ctx.trunk, "willett", store.n_sessions)
            model.mean.copy_(torch.as_tensor(store.mean)); model.std.copy_(torch.as_tensor(store.std))
            sd = torch.load(self.out / "pretrain-I" / "final.pt", map_location="cpu", weights_only=True)["model"]
            load_trunk_no_head(model, sd)
            return model.to(ctx.device)
        return self._orig_init(ctx, store, arm, seed)


def load_trunk_no_head(model: e1.XBody, sd: dict) -> int:
    """Copy blocks.* and out_norm.* (the trunk); stem and head stay as initialised (plan.md: head is new)."""
    keep = ("blocks.", "out_norm.")
    ts = {k: v for k, v in sd.items() if k.startswith(keep)}
    own = model.state_dict()
    need = [k for k in own if k.startswith(keep)]
    if sorted(need) != sorted(ts):
        raise KeyError("I trunk keys differ")
    for k, v in ts.items():
        if own[k].shape != v.shape:
            raise ValueError(f"shape mismatch {k}")
    model.load_state_dict({**own, **ts})
    return len(ts)


@contextlib.contextmanager
def derangement_rng(seed: int, j: int):
    orig = e1.derangement
    e1.derangement = lambda n, rng: orig(n, np.random.default_rng([seed, 77 + j]))
    try:
        yield
    finally:
        e1.derangement = orig


# --- contexts and runs -----------------------------------------------------------------------------------------------


def make_ctx(cfg: dict, out: Path, device: str, lr: float, steps: int) -> R8.Ctx:
    ctx = R8.ctx_from_config(ROOT / cfg["recipe_config"], out, device, cache=Path(cfg["sources"]["willett_cache"]))
    ctx.repo_results = None
    ctx.e_ckpt = Path(cfg["sources"]["e_checkpoint"])
    ctx.ft.lr = float(lr)
    ctx.ft.steps = {**ctx.ft.steps, cfg["budget"]: int(steps)}
    if "all" not in ctx.raw.get("c1_budgets", []):
        raise RuntimeError("C1 must run at 'all'")
    return ctx


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def final_val(run_dir: Path) -> float:
    rows = [json.loads(x) for x in (run_dir / "metrics.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return float(rows[-1]["val_cer"])


def one_run(ctx, store, arm, seed, deranged, j, clock, cfg, hooks, max_steps=None) -> dict:
    name = R8.run_name(arm, cfg["budget"], seed, deranged)
    d = ctx.out / "runs" / name
    if (d / "DONE.json").exists():
        return {"done": True}
    if clock.hours() >= float(cfg["gpu_cap_hours"]):
        raise CapReached()
    hooks.log(None, f"[{ctx.out.relative_to(hooks.out).as_posix()}/{name}] start, lr {ctx.ft.lr:g}, steps "
                    f"{ctx.ft.steps[cfg['budget']]}, GPU clock {clock.hours():.2f} h")
    with (derangement_rng(seed, j) if deranged else contextlib.nullcontext()):
        r = R8.train_run(ctx, store, arm, cfg["budget"], seed, deranged, max_steps=max_steps)
    clock.save()
    return r


def stage1(cfg, out, device, store, clock, hooks, max_steps=None) -> bool:
    c = cfg["stage1"]
    hooks.seal = True
    try:
        for steps in c["steps"]:
            for lr in c["lrs"]:
                for arm in c["arms"]:
                    for s in c["seeds"]:
                        ctx = make_ctx(cfg, out / "s1" / cell_name(arm, lr, steps), device, lr, steps)
                        r = one_run(ctx, store, arm, s, False, None, clock, cfg, hooks, max_steps)
                        if r.get("partial"):
                            return False
    finally:
        hooks.seal = False
    return True


def stage_select(cfg, out) -> dict:
    c = cfg["stage1"]
    sel = {"note": "P15-50 stage 1 recipe selection (plan.md 29c1dc9): per arm the cell with the lowest mean val CER "
                   "at the final step over tuning seeds 10 and 11; a cell with any seed > 0.90 is excluded; ties: "
                   "smaller LR, then fewer steps. Val only (106 sentences); no test number is read or stored here.",
           "arms": {}, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    for arm in c["arms"]:
        cells = []
        for steps in c["steps"]:
            for lr in c["lrs"]:
                cd = out / "s1" / cell_name(arm, lr, steps) / "runs"
                val = {}
                for s in c["seeds"]:
                    rd = cd / R8.run_name(arm, cfg["budget"], s)
                    if not (rd / "DONE.json").exists():
                        raise RuntimeError(f"stage 1 run missing: {rd}")
                    val[str(s)] = final_val(rd)
                vv = list(val.values())
                cells.append({"lr": lr, "steps": steps, "val": val, "mean_val_cer": float(np.mean(vv)),
                              "excluded": bool(any(x > c["exclude_if_val_cer_above"] for x in vv))})
        sel["arms"][arm] = {"cells": cells, "chosen": select_cell(cells, c["exclude_if_val_cer_above"])}
    e1.save_json(sel, out / "selection.json")
    return sel


def selection_committed(out: Path, root: Path = ROOT) -> tuple[bool, str]:
    """results/selection.json equals the derived one, is committed, and the commit is on origin/main."""
    rel = SEL_REPO.relative_to(root).as_posix()
    try:
        here = json.loads(SEL_REPO.read_text(encoding="utf-8"))
        mine = json.loads((out / "selection.json").read_text(encoding="utf-8"))
        if here != mine:
            return False, "results/selection.json differs from the derived selection.json"
        git = ["git", "-C", str(root)]
        head = subprocess.run(git + ["show", f"HEAD:{rel}"], capture_output=True, text=True, encoding="utf-8")
        if head.returncode != 0 or json.loads(head.stdout) != mine:
            return False, "not committed in HEAD"
        c = subprocess.run(git + ["log", "-1", "--format=%H", "--", rel], capture_output=True, text=True).stdout.strip()
        anc = subprocess.run(git + ["merge-base", "--is-ancestor", c, "refs/remotes/origin/main"], capture_output=True)
        if not c or anc.returncode != 0:
            return False, "commit not on origin/main yet"
        return True, c
    except Exception as ex:  # noqa: BLE001
        return False, repr(ex)


# --- arm I pretraining on T15 phoneme CTC -------------------------------------------------------------------------


class T15Store:
    """Lazy T15 train trials from the M4-01/02 derived npz files (float16 (T, 512), already z-scored by the
    dataset; phoneme ids 0 blank, 1 SIL, 2..40). Only trials with a known phonemisation."""

    def __init__(self, derived: Path, part: str = "train", max_sessions: int | None = None):
        self.derived = derived
        sess = json.loads((derived / "sessions.json").read_text(encoding="utf-8"))[:max_sessions]
        self.z = {si: np.load(derived / f"{s}.npz") for si, s in enumerate(sess)}
        self.items, self.length = [], {}
        import numpy.lib.format as NF
        for si, z in self.z.items():
            n = int(z[f"{part}_n"]) if f"{part}_n" in z.files else 0
            known = z[f"{part}_known"] if n else []
            for i in range(n):
                if not bool(known[i]):
                    continue
                with z.zip.open(f"{part}_X{i}.npy") as fh:
                    ver = NF.read_magic(fh)
                    rd = NF.read_array_header_1_0 if ver == (1, 0) else NF.read_array_header_2_0
                    shape = rd(fh)[0]
                k = len(self.items)
                self.items.append((si, f"{part}_X{i}", f"{part}_ph{i}"))
                self.length[k] = int(shape[0])

    def get(self, k: int) -> tuple[np.ndarray, np.ndarray]:
        si, xk, pk = self.items[k]
        z = self.z[si]
        return z[xk], z[pk].astype(np.int64)


def i_model(trunk: e1.TrunkCfg, n_in: int, vocab: int) -> e1.XBody:
    m = e1.XBody(dataclasses.replace(trunk, vocab=vocab), "text")
    m.stem = nn.Linear(n_in, trunk.d)
    return m


def stage_pretrain_i(cfg, out, device, ft_aug: e1.FTCfg, trunk: e1.TrunkCfg, clock, hooks,
                     t15: T15Store | None = None, max_steps: int | None = None, steps_override: int | None = None) -> dict:
    pc = cfg["pretrain_I"]
    d = out / "pretrain-I"
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return read_json(d / "DONE.json")
    if clock.hours() >= float(cfg["gpu_cap_hours"]):
        raise CapReached()
    total = int(steps_override or pc["steps"])
    warm = min(int(pc["warmup"]), max(1, total // 4)) if steps_override else int(pc["warmup"])
    t15 = t15 or T15Store(Path(cfg["sources"]["t15_derived"]), pc["part"])
    idx = list(range(len(t15.items)))
    hooks.log(None, f"[pretrain-I] {len(idx)} T15 {pc['part']} trials, {sum(t15.length.values())} frames")
    torch.manual_seed(0)
    model = i_model(trunk, int(pc["n_in"]), int(pc["vocab"])).to(device)
    opt = R8.make_optim(model, float(pc["weight_decay"]), float(pc["lr"]))
    step = 0
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); step = int(ck["step"])
        hooks.log(None, f"[pretrain-I] resume at step {step}")
    e1.save_json({"pretrain_I": pc, "trunk": e1.cfg_json(trunk), "steps": total}, d / "config.json")
    e1.save_json(LICENCE_PRE_I, d / "licence.json")

    end = total if max_steps is None else min(total, step + max_steps)

    def batch_at(k: int) -> tuple[int, int, dict]:
        # Batch k depends on k only (deterministic resume). One worker thread reads the npz files.
        rng = np.random.default_rng([0, 41, k])
        gs, ts = int(rng.integers(2 ** 62)), int(rng.integers(2 ** 62))
        bi = e1.pack_batch(idx, t15.length, int(pc["max_frames"]), rng)
        return gs, ts, e1.collate([(x, y, 0) for x, y in (t15.get(j) for j in bi)])

    pool = ThreadPoolExecutor(1)
    futs = {k: pool.submit(batch_at, k) for k in range(step, min(end, step + 3))}

    def save_latest():
        R8.atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step}, d / "latest.pt")

    try:
        t_ck = t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0
        while step < end:
            gs, ts, b = (futs.pop(step, None) or pool.submit(batch_at, step)).result()
            if step + 3 < end and step + 3 not in futs:
                futs[step + 3] = pool.submit(batch_at, step + 3)
            gen = torch.Generator().manual_seed(gs)
            torch.manual_seed(ts)
            model.train()
            for g in opt.param_groups:
                g["lr"] = e1.lr_at(step, total, float(pc["lr"]), float(pc["lr_min"]), warm)
            x = e1.augment_w(torch.from_numpy(b["x"]).to(device), torch.from_numpy(b["lengths"]), ft_aug, gen)
            lp = model(x, None, normalised=True)
            loss = F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(device),
                              torch.from_numpy(b["lengths"]), torch.from_numpy(b["target_lengths"]),
                              blank=0, reduction="mean", zero_infinity=True)
            opt.zero_grad(set_to_none=True)
            if torch.isfinite(loss):
                loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), float(pc["clip"])); opt.step()
                losses.append(float(loss.detach()))
            else:
                skipped += 1
            step += 1
            if step % 100 == 0 or step == end:
                dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
                hooks.log(None, f"[pretrain-I] step {step}/{total} loss {np.mean(losses) if losses else float('nan'):.4f} "
                                f"{dt:.3f} s/step skipped {skipped}")
                losses = []
            if time.time() - t_ck > 60 * float(pc["ckpt_minutes"]):
                save_latest(); t_ck = time.time(); clock.save()
            if (out / "pause").exists() or (out / "stop").exists():
                save_latest()
                hooks.log(None, f"[pretrain-I] pause/stop file: saved latest.pt at step {step}, exit")
                raise R8.Paused()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    clock.save()
    if step < total:
        save_latest()
        return {"partial": True, "step": step}
    R8.atomic_save({"model": model.state_dict(), "step": step}, d / "final.pt")
    rec = {"steps": step, "skipped": skipped, "n_trials": len(idx), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    e1.save_json(rec, d / "DONE.json")
    (d / "latest.pt").unlink(missing_ok=True)
    hooks.log(None, f"[pretrain-I] DONE {rec}")
    return rec


# --- stage 2 and summary -------------------------------------------------------------------------------------------


def recipe(sel: dict, cfg: dict, arm: str) -> tuple[float, int]:
    c = sel["arms"][cfg["stage2"]["recipe_of_arm"][arm]]["chosen"]
    return float(c["lr"]), int(c["steps"])


def stage2(cfg, out, device, store, sel, clock, hooks, max_steps=None) -> bool:
    for r in stage2_plan(cfg):
        lr, steps = recipe(sel, cfg, r["arm"])
        ctx = make_ctx(cfg, out / r["dir"], device, lr, steps)
        res = one_run(ctx, store, r["arm"], r["seed"], r["deranged"], r["j"] or 0, clock, cfg, hooks, max_steps)
        if res.get("partial"):
            return False
    return True


def load_results(cfg: dict, out: Path, sel: dict | None) -> tuple[dict, dict, list[dict]]:
    normal, der, rows = {}, {}, []
    for r in stage2_plan(cfg):
        p = out / r["dir"] / "runs" / R8.run_name(r["arm"], cfg["budget"], r["seed"], r["deranged"]) / "result.json"
        row = {k: r[k] for k in ("group", "arm", "seed", "deranged", "j")}
        if not p.exists():
            rows.append({**row, "status": "not_run"})
            continue
        res = read_json(p)
        if sel is not None and int(res["steps"]) != recipe(sel, cfg, r["arm"])[1]:
            raise RuntimeError(f"{p.parent} has the wrong step count")
        if bool(res["label_shuffle"]) != r["deranged"] or res["arm"] != r["arm"]:
            raise RuntimeError(f"{p.parent} has the wrong arm or labels")
        if r["deranged"]:
            der[(r["arm"], r["seed"], r["j"])] = res
        else:
            normal[(r["arm"], r["seed"])] = res
        rows.append({**row, "status": "done", "steps": res["steps"], "skipped": res["skipped"],
                     "test_cer_final": res["test_cer_final"], "test_cer_bestval": res.get("test_cer_bestval"),
                     "best_val_cer": res["best_val_cer"], "best_val_step": res["best_val_step"],
                     "val_cer_final": final_val(p.parent), "c1_shuffled_cer": res.get("c1_shuffled_cer")})
    return normal, der, rows


def verdict(cfg: dict, normal: dict, der: dict) -> dict:
    rules, seeds = cfg["rules"], cfg["stage2"]["seeds"]
    arms = ["R", "E", "T", "I"]
    table = {}
    for a in arms:
        v = [normal[(a, s)]["test_cer_final"] for s in seeds if (a, s) in normal]
        table[a] = {"seeds": {str(s): normal[(a, s)]["test_cer_final"] for s in seeds if (a, s) in normal},
                    "mean": float(np.mean(v)) if len(v) == len(seeds) else None, "n": len(v)}
    means = [t["mean"] for t in table.values() if t["mean"] is not None]
    v1 = {"best_mean": min(means) if means else None,
          "pass": (min(means) <= rules["v1_max_cer"]) if means else None}
    nd = {"E": 3, "R": 1, "I": 1}
    c2 = {}
    for a, n in nd.items():
        c2[a] = {str(s): c2_seed(normal[(a, s)]["test_cer_final"] if (a, s) in normal else None,
                                 [der[(a, s, j)]["test_cer_final"] if (a, s, j) in der else None for j in range(n)],
                                 rules, n) for s in seeds}
        c2[a]["all_seeds"] = all_seeds_pass({k: v for k, v in c2[a].items()})
    c1 = {a: c1_rows([normal[(a, s)] for s in seeds if (a, s) in normal], rules) for a in arms}
    c1_ok = {a: (all(x["pass"] for x in c1[a]) if table[a]["n"] == len(seeds) else None) for a in arms}
    valid = {}
    for a in arms:
        c2a = c2.get(a, {}).get("all_seeds")
        valid[a] = None if (c1_ok[a] is None or c2a is None) else bool(c1_ok[a] and c2a)
    valid["K"] = None
    h = {"H1": pair_rule("E", "R", normal, rules, seeds), "H2": pair_rule("E", "T", normal, rules, seeds),
         "H1swap": pair_rule("R", "E", normal, rules, seeds), "H2swap": pair_rule("T", "E", normal, rules, seeds),
         "H4": pair_rule("I", "R", normal, rules, seeds),
         "H4_I_vs_E_descriptive": pair_rule("I", "E", normal, rules, seeds),
         "H4_E_vs_I_descriptive": pair_rule("E", "I", normal, rules, seeds),
         "H3": {"a": "K", "b": "R", "status": "not run (dependency: P11-06, gap 86)", "pass": None}}
    for k, winner in (("H1", "E"), ("H2", "E"), ("H1swap", "R"), ("H4", "I")):
        h[k]["winner_valid"] = valid.get(winner)
        h[k]["counts"] = bool(h[k].get("pass")) and valid.get(winner) is True
    return {"table": table, "V1": v1, "C1": {"runs": c1, "pass": c1_ok}, "C2": c2, "valid": valid, "H": h,
            "outcome": outcome(v1["pass"], h, valid)}


def stage_summary(cfg, out, sel, status, gpu_h, repo_results: Path | None) -> dict:
    normal, der, rows = load_results(cfg, out, sel)
    v = verdict(cfg, normal, der)
    pre = out / "pretrain-I" / "DONE.json"
    agg = {"note": "aggregate only; pooled test CER over the 80 test sentences (last block per Willett session), greedy "
                   "CTC, no LM, final step; plan.md 29c1dc9; K arm not run (dependency). Every pretrained arm comes "
                   "from other people: E (emg2qwerty, 100 users) and T differ from T5 in person and modality, I (T15) "
                   "in person only.",
           "status": status, "gpu_hours": round(gpu_h, 3),
           "selection": {a: sel["arms"][a]["chosen"] for a in sel["arms"]} if sel else None,
           "pretrain_I": read_json(pre) if pre.exists() else None,
           **v, "runs": rows, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    agg = json.loads(json.dumps(agg, default=float))
    e1.save_json(agg, out / "summary.json")
    if repo_results is not None:
        repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, repo_results / "summary.json")
    return agg


# --- main ------------------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-50 F3 full-data runner")
    ap.add_argument("stage", choices=("all", "select", "summary", "gate", "smoke"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--smoke-steps", type=int, default=20)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if not check_out(out):
        print(f"never write into {out}", file=sys.stderr)
        return 2
    if a.stage == "smoke" and out == OUT.resolve():
        print("smoke needs another --out (not the result folder)", file=sys.stderr)
        return 2
    cfg = read_json(Path(a.config))
    out.mkdir(parents=True, exist_ok=True)
    hooks = Hooks(out, cfg)
    torch.set_num_threads(2)
    hooks.log(None, f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    if a.stage == "gate":
        ok, why = selection_committed(out)
        print(ok, why)
        return 0 if ok else WAITING
    if a.stage == "select":
        sel = stage_select(cfg, out)
        print(json.dumps({k: v["chosen"] for k, v in sel["arms"].items()}))
        return 0
    if a.stage == "summary":
        sel = read_json(out / "selection.json") if (out / "selection.json").exists() else None
        c = read_json(out / "gpu_clock.json")["seconds"] / 3600 if (out / "gpu_clock.json").exists() else 0.0
        agg = stage_summary(cfg, out, sel, "summary", c, HERE / "results" if out == OUT.resolve() else None)
        hooks.log(None, f"[summary] outcome {agg['outcome']}")
        return 0
    clock = Clock(out / "gpu_clock.json")
    R8.keep_awake(True)
    try:
        store = R8.WillettStore(Path(cfg["sources"]["willett_cache"]))
        if a.stage == "smoke":
            n = a.smoke_steps
            scfg = json.loads(json.dumps(cfg))
            scfg["stage1"].update({"lrs": [0.0005], "steps": [n], "exclude_if_val_cer_above": 99.0})  # 20 steps: no exclusion
            scfg["stage2"]["seeds"] = [0]
            if not stage1(scfg, out, a.device, store, clock, hooks):
                return 0
            sel = stage_select(scfg, out)
            ctx0 = make_ctx(scfg, out / "tmp", a.device, 5e-4, n)
            stage_pretrain_i(scfg, out, a.device, ctx0.ft, ctx0.trunk, clock, hooks,
                             t15=T15Store(Path(cfg["sources"]["t15_derived"]), "train", max_sessions=2),
                             steps_override=n)
            stage2(scfg, out, a.device, store, sel, clock, hooks)
            agg = stage_summary(scfg, out, sel, "smoke", clock.hours(), None)
            hooks.log(None, f"[smoke] outcome {agg['outcome']} (smoke numbers are not results)")
            return 0
        if not stage1(cfg, out, a.device, store, clock, hooks):
            return 0
        sel = stage_select(cfg, out) if not (out / "selection.json").exists() else read_json(out / "selection.json")
        hooks.log(None, f"[select] chosen {json.dumps({k: v['chosen'] for k, v in sel['arms'].items()})}")
        if out == OUT.resolve() and not SEL_REPO.exists():
            SEL_REPO.parent.mkdir(parents=True, exist_ok=True)
            e1.save_json(sel, SEL_REPO)
        ctx0 = make_ctx(cfg, out / "s2" / "E", a.device, *recipe(sel, cfg, "E"))
        if stage_pretrain_i(cfg, out, a.device, ctx0.ft, ctx0.trunk, clock, hooks).get("partial"):
            return 0
        gc.collect()
        ok, why = selection_committed(out)
        if not ok:
            hooks.log(None, f"[gate] stage 2 waits: {why} (commit + push results/selection.json, then re-run)")
            return WAITING
        hooks.log(None, f"[gate] selection.json committed in {why}: stage 2 starts")
        if not stage2(cfg, out, a.device, store, sel, clock, hooks):
            return 0
        clock.save()
        agg = stage_summary(cfg, out, sel, "done", clock.hours(), HERE / "results")
        hooks.log(None, f"[summary] outcome {agg['outcome']} gpu_h {agg['gpu_hours']:.2f}")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        hooks.log(None, "ALL DONE")
    except R8.Paused:
        return PAUSED
    except CapReached:
        clock.save()
        hooks.log(None, f"GPU cap {cfg['gpu_cap_hours']} h reached: stop (plan.md); remaining runs 'not run (cap)'")
        sel = read_json(out / "selection.json") if (out / "selection.json").exists() else None
        stage_summary(cfg, out, sel, "cap", clock.hours(), HERE / "results" if out == OUT.resolve() else None)
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    except Exception as ex:  # noqa: BLE001
        hooks.log(None, f"FAILED: {ex!r}")
        (out / "FAILED").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + f" {ex!r}", encoding="utf-8")
        raise
    finally:
        clock.save()
        R8.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
