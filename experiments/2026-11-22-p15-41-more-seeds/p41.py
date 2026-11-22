r"""P15-41 runner: more seeds of the F-R20 recipe at minutes scale (gap 184) - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this task, 043486f).
Reuses READ-ONLY: P15-36 ``p36.py`` (F-R20 per-budget config, train_one) and through it the P15-35b / P15-33 /
P15-08 code; the P15-36 and P15-35b test results of seeds 0 and 1. Writes only to
C:\Users\zhang\bci-data\derived\p15-41\.

Order: seed blocks 2, 3, 4. A block starts only if the GPU clock is <= block_start_max_hours (plan.md).
Inside a block: budget 3, 10, 30 x arm T, E: recipe-A aligner (val only) -> library -> F-R20 run -> test readout;
then C2: arm E, 10 min, deranged labels (own deranged aligner) -> test readout. Then summary.json and DONE.

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-22-p15-41-more-seeds\p41.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
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
from scipy import stats as sst

HERE = Path(__file__).resolve().parent
P36_DIR = HERE.parent / "2026-11-22-p15-36-budget-matched"
sys.path.insert(0, str(P36_DIR))
import p36 as P36  # noqa: E402

B, L = P36.B, P36.L
p33, e1, R8 = L.p33, L.e1, L.R8
FR = P36.FR

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-41")
FORBIDDEN = P36.FORBIDDEN + [Path(r"C:\Users\zhang\bci-data\derived\p15-36")]
PAUSED = 3


# --- context and paths ---------------------------------------------------------------------------------------------


def make_ctx(cfg_path: Path, out: Path, device: str) -> L.Ctx35:
    # repo_results None: nothing from the library stages is written into the repo; summary.json is written below.
    return L.make_ctx(cfg_path, out, device, None)


def run_dir(ctx: L.Ctx35, arm: str, budget: str, seed: int, ls: bool, part: str = "search") -> Path:
    return B.sdir(P36.bctx(ctx, budget), FR, arm, seed, ls, part)


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def block_runs(cfg: dict, seed: int) -> list[tuple[str, str, int, bool]]:
    """Plan order inside one seed block: budget 3, 10, 30 x arm T, E (normal); then the C2 run."""
    runs = [(a, b, seed, False) for b in cfg["budgets_min"] for a in cfg["arms"]]
    runs.append((cfg["c2"]["arm"], cfg["c2"]["budget"], seed, True))
    return runs


def block_started(ctx: L.Ctx35, seed: int) -> bool:
    """Any file of this seed exists (a run, an aligner or a library): the block started in an earlier launch."""
    tag = f"-s{seed}"
    for root in (ctx.out / "search" / FR, ctx.out / "aligners"):
        if root.exists() and any(tag + "-" in p.name + "-" for p in root.iterdir()):
            return True
    lib = ctx.out / "libraries"
    return lib.exists() and any(tag + "-" in p.stem + "-" for p in lib.iterdir())


# --- training and test readout -------------------------------------------------------------------------------------


def test_one(ctx: L.Ctx35, store, arm: str, budget: str, seed: int, ls: bool) -> dict:
    if not (run_dir(ctx, arm, budget, seed, ls) / "DONE.json").exists():
        raise RuntimeError(f"test readout before the run is finished: {R8.run_name(arm, budget, seed, ls)}")
    r = B.test_readout(P36.bctx(ctx, budget), store, FR, arm, seed, ls)
    r["budget"] = str(r["budget"])
    return r


def stage_blocks(ctx: L.Ctx35, store, pool, max_steps: int | None = None) -> str:
    """Returns 'done' (all blocks run or skipped by the rule) or 'partial' (a run stopped early)."""
    cfg = ctx.cfg
    bpath = ctx.out / "blocks.json"
    blocks = read_json(bpath) if bpath.exists() else {}
    for s in cfg["seeds"]:
        key = str(s)
        if blocks.get(key, {}).get("status") == "skipped":
            continue
        if key not in blocks:
            h = L.clock_hours(ctx)
            started = block_started(ctx, s)
            if h > float(cfg["block_start_max_hours"]) and not started:
                blocks[key] = {"status": "skipped", "gpu_hours": round(h, 3), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
                e1.save_json(blocks, bpath)
                L.log(ctx, f"[block s{s}] skipped: GPU clock {h:.2f} h > {cfg['block_start_max_hours']} h (plan.md)")
                for s2 in cfg["seeds"][cfg["seeds"].index(s) + 1:]:
                    blocks.setdefault(str(s2), {"status": "skipped", "gpu_hours": round(h, 3),
                                                "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
                e1.save_json(blocks, bpath)
                return "done"
            blocks[key] = {"status": "started", "gpu_hours_at_start": round(h, 3),
                           "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
            e1.save_json(blocks, bpath)
            L.log(ctx, f"[block s{s}] start at GPU clock {h:.2f} h")
        if blocks[key].get("status") == "done":
            continue
        for arm, b, seed, ls in block_runs(cfg, s):
            r = P36.train_one(ctx, store, pool, arm, b, seed, ls, max_steps)
            if r.get("partial"):
                return "partial"
            test_one(ctx, store, arm, b, seed, ls)
        blocks[key].update({"status": "done", "gpu_hours_at_end": round(L.clock_hours(ctx), 3),
                            "time_end": time.strftime("%Y-%m-%dT%H:%M:%S")})
        e1.save_json(blocks, bpath)
        L.log(ctx, f"[block s{s}] done at GPU clock {L.clock_hours(ctx):.2f} h")
    return "done"


# --- results of all seeds ------------------------------------------------------------------------------------------


def old_result(cfg: dict, arm: str, budget: str, seed: int) -> dict:
    """Seeds 0 and 1: P15-36 test results (E-b30-s0 from P15-35b). Read-only."""
    src = cfg["sources"]["old_test"]
    name = R8.run_name(arm, budget, seed)
    root = src["p15_35b"] if name in src["p15_35b_runs"] else src["p15_36"]
    r = read_json(Path(root) / name / "result.json")
    r["budget"] = str(r["budget"])
    return r


def new_result(ctx: L.Ctx35, arm: str, budget: str, seed: int, ls: bool = False) -> dict | None:
    d = run_dir(ctx, arm, budget, seed, ls, "test")
    if not (d / "DONE.json").exists():
        return None
    r = read_json(d / "result.json")
    r["budget"] = str(r["budget"])
    return r


def all_results(ctx: L.Ctx35) -> tuple[dict, list[int]]:
    """{(arm, budget, seed): result} for old seeds and complete new seeds; list of complete seeds."""
    cfg = ctx.cfg
    res, seeds = {}, []
    for s in cfg["old_seeds"]:
        for a in cfg["arms"]:
            for b in cfg["budgets_min"]:
                res[(a, b, s)] = old_result(cfg, a, b, s)
        seeds.append(int(s))
    for s in cfg["seeds"]:
        rs = {(a, b, s): new_result(ctx, a, b, s) for a in cfg["arms"] for b in cfg["budgets_min"]}
        if all(v is not None for v in rs.values()):
            res.update(rs)
            seeds.append(int(s))
    return res, seeds


# --- statistics (pure functions) -----------------------------------------------------------------------------------


def paired_t(d: list[float], level: float = 0.95) -> dict:
    """Two-sided paired t interval of the mean of d (d = CER_T - CER_E per seed)."""
    x = np.asarray(d, float)
    n = len(x)
    m = float(x.mean()) if n else float("nan")
    if n < 2:
        return {"n": n, "mean": m, "sd": None, "ci": None, "t_crit": None, "win": False}
    sd = float(x.std(ddof=1))
    tc = float(sst.t.ppf(0.5 + level / 2, n - 1))
    half = tc * sd / math.sqrt(n)
    lo, hi = m - half, m + half
    return {"n": n, "mean": m, "sd": sd, "ci": [lo, hi], "t_crit": tc, "win": bool(m > 0 and lo > 0)}


def sign_test(d: list[float]) -> dict:
    """Exact one-sided sign test: P(X >= k), X ~ Bin(n, 0.5), k = number of d > 0 (ties count as not > 0)."""
    n = len(d)
    k = int(sum(1 for v in d if v > 0))
    p = float(sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n) if n else float("nan")
    return {"n": n, "k_positive": k, "p_one_sided": p}


def h1_status(wins: dict, primary: list[str]) -> str:
    w = sum(bool(wins[b]) for b in primary)
    return "pass" if w == len(primary) else ("partial" if w >= 1 else "fail")


def h1_verdict(res: dict, seeds: list[int], cfg: dict, rules33: dict, new_seeds: list[int]) -> dict:
    rules = cfg["rules"]
    per = {}
    for b in cfg["budgets_min"]:
        cT = [float(res[("T", b, s)]["test_cer_final"]) for s in seeds]
        cE = [float(res[("E", b, s)]["test_cer_final"]) for s in seeds]
        d = [t - e for t, e in zip(cT, cE)]
        row = {"seeds": list(seeds), "cer_T": cT, "cer_E": cE, "d_T_minus_E": d,
               "mean_T": float(np.mean(cT)), "mean_E": float(np.mean(cE)),
               "paired_t": paired_t(d, float(rules["ci_level"])), "sign_test": sign_test(d)}
        cer = {(a, b, s): float(res[(a, b, s)]["test_cer_final"]) for a in ("E", "T") for s in seeds}
        edits = {(a, b, s): np.asarray(res[(a, b, s)]["test_edits_final"], float) for a in ("E", "T") for s in seeds}
        ref = np.asarray(res[("E", b, seeds[0])]["test_ref"], float)
        for s in seeds:
            for a in ("E", "T"):
                if list(res[(a, b, s)]["test_ref"]) != list(ref):
                    raise RuntimeError(f"test references differ: {a}-b{b}-s{s}")
        row["e1a_beats_rule_descriptive"] = R8.beats(cer, edits, ref, "E", "T", b, seeds, rules33)
        nd = [d[k] for k, s in enumerate(seeds) if s in new_seeds]
        row["paired_t_new_seeds_only"] = paired_t(nd, float(rules["ci_level"]))
        per[b] = row
    wins = {b: per[b]["paired_t"]["win"] for b in cfg["budgets_min"]}
    prim = list(rules["primary_budgets"])
    return {"rule": "E wins over T at b: mean d > 0 and lower end of the paired 95 % t interval > 0 (plan.md)",
            "per_budget": per, "wins": wins, "H1": {"budgets": prim, "status": h1_status(wins, prim),
                                                    "n_wins": int(sum(wins[b] for b in prim))},
            "H1_3min_secondary": {"win": bool(wins.get("3", False))}}


def c2_row(normal: dict | None, deranged: dict | None, rules: dict) -> dict:
    if normal is None or deranged is None:
        return {"status": "missing", "pass": False}
    need = L.c2_need(rules, float(normal["test_cer_final"]))
    return {"status": "done", "normal_test_cer": normal["test_cer_final"], "deranged_test_cer": deranged["test_cer_final"],
            "needed": need, "pass": bool(deranged["test_cer_final"] >= need),
            "normal_val_cer": normal.get("val_cer_final"), "deranged_val_cer": deranged.get("val_cer_final")}


def c1_rows(results: list[dict], rules33: dict) -> dict:
    rows = []
    for r in results:
        if "c1_shuffled_cer" in r and r["test_cer_final"] <= rules33["c1_applies_if_cer_below"]:
            rows.append({"run": r["run"], "cer": r["test_cer_final"], "shuffled": r["c1_shuffled_cer"],
                         "pass": bool(r["c1_shuffled_cer"] >= rules33["c1_min_cer"])})
    return {"runs": rows, "n_applicable": len(rows), "pass": bool(all(x["pass"] for x in rows))}


# --- summary -------------------------------------------------------------------------------------------------------


def run_rows(ctx: L.Ctx35) -> list[dict]:
    """Aggregates of every new run (val, test, library, aligner val); no per-sentence numbers."""
    rows = []
    for s in ctx.cfg["seeds"]:
        for arm, b, seed, ls in block_runs(ctx.cfg, s):
            sd = run_dir(ctx, arm, b, seed, ls)
            if not (sd / "result.json").exists():
                continue
            v = read_json(sd / "result.json")
            c = read_json(sd / "config.json")
            row = {k: v.get(k) for k in ("run", "arm", "budget", "seed", "label_shuffle", "steps", "skipped",
                                         "n_train", "minutes", "val_cer_final", "val_shuffled_cer_final",
                                         "best_val_step", "best_val_cer")}
            row["library"] = {k: x for k, x in (c.get("library") or {}).items() if k != "aligner"}
            row["n_texts"] = c.get("n_texts")
            ad = ctx.out / "aligners" / R8.run_name(arm, b, seed, ls) / "result.json"
            if ad.exists():
                a = read_json(ad)
                row["aligner_val_cer_final"] = a.get("val_cer_final")
                row["aligner_steps"] = a.get("steps")
            t = new_result(ctx, arm, b, seed, ls)
            if t is not None:
                row.update({k: t[k] for k in ("test_cer_final", "test_cer_bestval", "c1_shuffled_cer") if k in t})
            rows.append(row)
    return rows


def stage_summary(ctx: L.Ctx35, status: str, repo_results: Path | None = HERE / "results") -> dict:
    cfg = ctx.cfg
    rules33 = ctx.c33.raw["rules"]
    res, seeds = all_results(ctx)
    new_seeds = [s for s in seeds if s in cfg["seeds"]]
    agg = {"note": "aggregate only; CER = total edits / total reference characters; test = 80 test sentences (last "
                   "block of each session); greedy CTC, no LM, final step; recipe F-R20 (P15-36); plan.md (043486f)",
           "status": status, "gpu_hours": round(L.clock_hours(ctx), 3),
           "blocks": read_json(ctx.out / "blocks.json") if (ctx.out / "blocks.json").exists() else {},
           "complete_seeds": seeds, "new_complete_seeds": new_seeds}
    agg["verdict"] = h1_verdict(res, seeds, cfg, rules33, new_seeds)
    c2 = {}
    a2, b2 = cfg["c2"]["arm"], cfg["c2"]["budget"]
    for s in cfg["seeds"]:
        started = agg["blocks"].get(str(s), {}).get("status") not in (None, "skipped")
        if s in new_seeds or started:
            c2[str(s)] = c2_row(new_result(ctx, a2, b2, s), new_result(ctx, a2, b2, s, True), cfg["rules"])
    agg["C2"] = c2
    newres = [r for (_, _, s), r in res.items() if s in new_seeds]
    agg["C1"] = c1_rows(newres, rules33)
    flags = [f"C2 {c2[str(s)]['status']} on seed {s}" for s in new_seeds if not c2[str(s)]["pass"]]
    flags += [f"C1 fails on {x['run']}" for x in agg["C1"]["runs"] if not x["pass"]]
    agg["control_flags"] = flags
    agg["H1_valid"] = not flags
    agg["runs"] = run_rows(ctx)
    agg["time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    agg = json.loads(json.dumps(agg, default=float))
    e1.save_json(agg, ctx.out / "summary.json")
    if repo_results is not None:
        repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, repo_results / "summary.json")
    v = agg["verdict"]
    L.log(ctx, "[summary] seeds %s H1 %s (wins %s) flags %s gpu_h %.2f" % (
        seeds, v["H1"]["status"], v["wins"], flags, agg["gpu_hours"]))
    return agg


# --- main ----------------------------------------------------------------------------------------------------------


def check_out(out: Path) -> bool:
    for f in FORBIDDEN:
        if out == f.resolve() or f.resolve() in out.parents:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-41 runner")
    ap.add_argument("stage", choices=("all", "summary"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if not check_out(out):
        print(f"never write into {out}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    ctx = make_ctx(Path(a.config), out, a.device)
    torch.set_num_threads(2)
    L.log(ctx, f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    L.clock_start(ctx)
    R8.keep_awake(True)
    try:
        pool = B.stage_textpool(ctx)
        store = R8.WillettStore(ctx.c33.cache)
        if a.stage == "summary":
            stage_summary(ctx, "summary")
            return 0
        if stage_blocks(ctx, store, pool) != "done":
            return 0
        stage_summary(ctx, "done")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        L.log(ctx, "ALL DONE")
    except p33.Paused:
        L.clock_save(ctx)
        return PAUSED
    except L.CapReached:
        L.clock_save(ctx)
        L.log(ctx, f"GPU cap {ctx.cfg['gpu_cap_hours']} h reached: stop (plan.md)")
        try:
            stage_summary(ctx, "cap")
        except Exception as ex:  # noqa: BLE001 - summary is best effort at the cap
            L.log(ctx, f"summary at cap failed: {ex!r}")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    except Exception as ex:  # noqa: BLE001 - leave a FAILED marker for the watcher
        L.log(ctx, f"FAILED: {ex!r}")
        (out / "FAILED").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + f" {ex!r}", encoding="utf-8")
        raise
    finally:
        L.clock_save(ctx)
        R8.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
