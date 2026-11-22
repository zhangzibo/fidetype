r"""P15-36 runner: E1 budget-matched recipe (gap 140) - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this task, 8790238).
Reuses READ-ONLY: P15-35b ``p35b.py`` / ``p35_lib.py`` (F-R20 batch rule, libraries, text pool, test readout),
P15-33 ``p33.py`` (recipe A, aligners), P15-08 ``e1.py`` / ``run.py`` (data, splits, verdict), the P15-08 E1a runs,
the P15-33 grid runs and the P15-35b F-R20 E-b30-s0 runs. Writes only to C:\Users\zhang\bci-data\derived\p15-36\.

Stages (``all`` runs them in order and skips finished parts; every training run resumes exactly):
  train    23 F-R20 runs (arms R, T, E, S x budgets 3, 10, 30 min x seeds 0, 1, minus E-b30-s0 = reused). Val only.
  select   val-only budget-matched rule -> selection.json (no test number is read)
  test     test readout of every new F-R20 run (same weights, final step)
  verdict  V1, H1-H4, C1, C2 under the chosen recipe per budget (P15-08 verdict) -> summary.json
  seed1c2  descriptive: F-R20 / E / 30 min / seed 1 deranged run + test C2 (only if the GPU clock allows)

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-22-p15-36-budget-matched\p36.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
P35B_DIR = HERE.parent / "2026-11-21-p15-35b-synthetic-on-top"
sys.path.insert(0, str(P35B_DIR))
import p35b as B  # noqa: E402

L = B.L
p33, e1, R8 = L.p33, L.e1, L.R8

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-36")
FORBIDDEN = [Path(r"C:\Users\zhang\bci-data\derived\p15-08"), Path(r"C:\Users\zhang\bci-data\derived\p15-33"),
             Path(r"C:\Users\zhang\bci-data\derived\p15-35"), Path(r"C:\Users\zhang\bci-data\derived\p15-35b")]
PAUSED = 3
FR = "F-R20"


# --- context -------------------------------------------------------------------------------------------------------


def make_ctx(cfg_path: Path, out: Path, device: str, repo_results: Path | None = HERE / "results") -> L.Ctx35:
    return L.make_ctx(cfg_path, out, device, repo_results)


def aligner_map(cfg: dict) -> dict:
    """run name -> P15-33 recipe-A weights of the same arm, budget, seed (normal labels)."""
    root = Path(cfg["sources"]["aligners"])
    return {R8.run_name(a, b, s): str(root / R8.run_name(a, b, s) / "final.pt")
            for a in cfg["arms"] for b in cfg["frr20_budgets"] for s in cfg["seeds"]}


def bcfg(cfg: dict, budget: str) -> dict:
    """The P15-35b config shape for one budget: candidate F-R20 with the plan's steps at this budget."""
    if budget not in cfg["frr20_budgets"]:
        raise ValueError(f"F-R20 is not run at budget {budget}")
    c = dict(cfg)
    spec = {k: v for k, v in cfg["frr20"].items() if k != "steps"}
    spec["steps"] = int(cfg["frr20"]["steps"][budget])
    c.update({"budget": budget, "candidates": {FR: spec}, "control": {}, "aligner_sources": aligner_map(cfg)})
    return c


def bctx(ctx: L.Ctx35, budget: str) -> L.Ctx35:
    """Per-budget view of the context. Clock fields are copied by value; all views share t0 and base."""
    return dataclasses.replace(ctx, cfg=bcfg(ctx.cfg, budget))


def is_reused(cfg: dict, arm: str, budget: str, seed: int, ls: bool) -> bool:
    return R8.run_name(arm, budget, seed, ls) in cfg["sources"]["reuse_runs"]


def train_list(cfg: dict) -> list[tuple[str, str, int]]:
    """Plan order: seed 0 then 1; budget 3, 10, 30; arm R, T, E, S. Reused runs are left out."""
    return [(a, b, s) for s in cfg["seeds"] for b in cfg["frr20_budgets"] for a in cfg["arms"]
            if not is_reused(cfg, a, b, s, False)]


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# --- loaders (val keys only for the selection) ---------------------------------------------------------------------


def e1a_result(cfg: dict, arm: str, budget: str, seed: int, ls: bool = False) -> dict:
    d = Path(cfg["sources"]["E1a_runs"]) / R8.run_name(arm, budget, seed, ls)
    r = read_json(d / "result.json")
    fin = [json.loads(ln) for ln in (d / "metrics.jsonl").read_text(encoding="utf-8").splitlines() if ln]
    fin = [m for m in fin if int(m["step"]) == int(r["steps"])]
    if not fin:
        raise RuntimeError(f"E1a run {d.name}: no final-step val line")
    r["val_cer_final"] = float(fin[-1]["val_cer"])
    r["budget"] = str(r["budget"])
    return r


def a_result(cfg: dict, arm: str, budget: str, seed: int, ls: bool = False) -> dict:
    r = read_json(Path(cfg["sources"]["A_runs"]) / R8.run_name(arm, budget, seed, ls) / "result.json")
    r["budget"] = str(r["budget"])
    return r


def frr20_val(ctx: L.Ctx35, arm: str, budget: str, seed: int, ls: bool = False) -> dict:
    """Search (val-only) result of an F-R20 run: reused from P15-35b or trained here."""
    name = R8.run_name(arm, budget, seed, ls)
    if is_reused(ctx.cfg, arm, budget, seed, ls):
        d = Path(ctx.cfg["sources"]["reuse_frr20_search"]) / name
    else:
        d = B.sdir(bctx(ctx, budget), FR, arm, seed, ls)
    r = read_json(d / "result.json")
    r["budget"] = str(r["budget"])
    lib = read_json(d / "config.json").get("library") or {}
    r["_library"] = {k: v for k, v in lib.items() if k != "aligner"}
    r["_n_texts"] = read_json(d / "config.json").get("n_texts")
    return r


def val_table(ctx: L.Ctx35) -> dict:
    """{(candidate, budget): [final val CER of the 8 normal runs]} - val numbers only."""
    cfg = ctx.cfg
    out = {}
    for b in cfg["budgets_min"]:
        for cand in cfg["candidate_order"]:
            if cand == FR and b not in cfg["frr20_budgets"]:
                continue
            vals = []
            for a in cfg["arms"]:
                for s in cfg["seeds"]:
                    r = (frr20_val(ctx, a, b, s) if cand == FR else
                         a_result(cfg, a, b, s) if cand == "A" else e1a_result(cfg, a, b, s))
                    vals.append(float(r["val_cer_final"]))
            out[(cand, b)] = vals
    return out


def c2_val_inputs(ctx: L.Ctx35) -> dict:
    """{candidate: normal / deranged final val CER of arm E, 30 min, seed 0 (+ snippet medians for F-R20)}."""
    cfg = ctx.cfg
    c2 = cfg["c2"]
    a, b, s = c2["arm"], c2["budget"], int(c2["seed"])
    out = {}
    for cand in cfg["candidate_order"]:
        if cand == FR:
            n, d = frr20_val(ctx, a, b, s), frr20_val(ctx, a, b, s, True)
            out[cand] = {"normal": n["val_cer_final"], "deranged": d["val_cer_final"],
                         "median_normal": n["_library"].get("snippet_len_median"),
                         "median_deranged": d["_library"].get("snippet_len_median")}
        else:
            f = a_result if cand == "A" else e1a_result
            out[cand] = {"normal": f(cfg, a, b, s)["val_cer_final"], "deranged": f(cfg, a, b, s, True)["val_cer_final"]}
    return out


# --- the budget-matched rule (pure function, val numbers only) -----------------------------------------------------


def select_rule(vals: dict, c2v: dict, cfg: dict) -> dict:
    """plan.md rule. vals[(cand, budget)] = 8 val CERs; c2v[cand] = arm-E seed-0 30-min val numbers."""
    rules = cfg["rules"]
    order = list(cfg["candidate_order"])
    adm_b = cfg["admissible_budget"]
    c2rows = {}
    for cand, v in c2v.items():
        need = L.c2_need(rules, float(v["normal"])) + float(rules["val_margin"])
        row = {"normal_val_cer": v["normal"], "deranged_val_cer": v["deranged"], "needed_with_margin": need}
        ok = float(v["deranged"]) >= need
        if v.get("median_normal") is not None:
            ratio = float(v["median_deranged"]) / float(v["median_normal"])
            guard = abs(ratio - 1.0) <= float(rules["length_guard"])
            row.update({"length_ratio": round(ratio, 4), "length_guard_pass": bool(guard)})
            ok = ok and guard
        row["val_c2_with_margin_pass"] = bool(ok)
        c2rows[cand] = row
    per_budget, chosen = {}, {}
    for b in cfg["budgets_min"]:
        rows = []
        for k, cand in enumerate(order):
            if (cand, b) not in vals:
                continue
            adm = True if b != adm_b else bool(c2rows.get(cand, {}).get("val_c2_with_margin_pass", False))
            rows.append({"candidate": cand, "mean_val_cer": float(np.mean(vals[(cand, b)])),
                         "n_runs": len(vals[(cand, b)]), "admissible": adm, "_k": k})
        ok = sorted((r for r in rows if r["admissible"]), key=lambda r: (r["mean_val_cer"], r["_k"]))
        for r in rows:
            r.pop("_k")
        per_budget[b] = rows
        chosen[b] = ok[0]["candidate"] if ok else None
    return {"note": "val block only (no test-block number); plan.md rule", "chosen": chosen,
            "per_budget": per_budget, "val_c2_30min_arm_E_seed0": c2rows,
            "no_recipe": chosen.get(adm_b) is None, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}


def stage_select(ctx: L.Ctx35) -> dict:
    p = ctx.out / "selection.json"
    if p.exists():
        return read_json(p)
    sel = select_rule(val_table(ctx), c2_val_inputs(ctx), ctx.cfg)
    e1.save_json(sel, p)
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(sel, ctx.repo_results / "selection.json")
    L.log(ctx, f"[select] chosen {sel['chosen']}")
    return sel


# --- training and test readout -------------------------------------------------------------------------------------


def train_one(ctx: L.Ctx35, store, pool, arm: str, budget: str, seed: int, ls: bool,
              max_steps: int | None = None) -> dict:
    bc = bctx(ctx, budget)
    d = B.sdir(bc, FR, arm, seed, ls)
    if not (d / "DONE.json").exists():
        L.check_cap(ctx)
        lib = L.get_library(bc, store, "forced", arm, seed, ls)
        n_txt = len(L.usable_texts(pool, lib))
        if (d / "latest.pt").exists() is False:
            L.log(ctx, f"[{FR}/{R8.run_name(arm, budget, seed, ls)}] usable texts {n_txt}, chars "
                       f"'{lib.stats['chars_covered']}', median snippet {lib.stats['snippet_len_median']}")
        if n_txt == 0:
            raise RuntimeError(f"no usable synthetic text for {R8.run_name(arm, budget, seed, ls)}")
    return B.train_b(bc, store, pool, FR, arm, seed, ls, d, False, max_steps)


def stage_train(ctx: L.Ctx35, store, pool, max_steps: int | None = None) -> bool:
    for arm, b, s in train_list(ctx.cfg):
        r = train_one(ctx, store, pool, arm, b, s, False, max_steps)
        if r.get("partial"):
            return False
    return True


def frr20_test(ctx: L.Ctx35, store, arm: str, budget: str, seed: int, ls: bool = False) -> dict:
    name = R8.run_name(arm, budget, seed, ls)
    if is_reused(ctx.cfg, arm, budget, seed, ls):
        r = read_json(Path(ctx.cfg["sources"]["reuse_frr20_test"]) / name / "result.json")
    else:
        if not (ctx.out / "selection.json").exists():
            raise RuntimeError("test readout before selection.json (plan.md)")
        r = B.test_readout(bctx(ctx, budget), store, FR, arm, seed, ls)
    r["budget"] = str(r["budget"])
    return r


def stage_test(ctx: L.Ctx35, store) -> None:
    for a in ctx.cfg["arms"]:
        for b in ctx.cfg["frr20_budgets"]:
            for s in ctx.cfg["seeds"]:
                frr20_test(ctx, store, a, b, s)


def test_result(ctx: L.Ctx35, store, cand: str, arm: str, budget: str, seed: int, ls: bool = False) -> dict:
    if cand == FR:
        return frr20_test(ctx, store, arm, budget, seed, ls)
    return (a_result if cand == "A" else e1a_result)(ctx.cfg, arm, budget, seed, ls)


def rule_verdict(ctx: L.Ctx35, store, chosen: dict) -> dict:
    """P15-08 verdict on the runs of the chosen recipe per budget, plus the C2 run of the 30-min recipe."""
    cfg = ctx.cfg
    results = [test_result(ctx, store, chosen[b], a, b, s) for s in cfg["seeds"] for b in cfg["budgets_min"]
               for a in cfg["arms"]]
    c2 = cfg["c2"]
    results.append(test_result(ctx, store, chosen[c2["budget"]], c2["arm"], c2["budget"], int(c2["seed"]), True))
    v = R8.verdict(results, ctx.c33.raw, list(cfg["seeds"]), list(cfg["budgets_min"]))
    v["recipes"] = dict(chosen)
    return v


def recipe_tables(ctx: L.Ctx35, store) -> dict:
    """Descriptive: per budget and candidate, mean val and test CER per arm (means over the 2 seeds)."""
    cfg = ctx.cfg
    out = {}
    for b in cfg["budgets_min"]:
        for cand in cfg["candidate_order"]:
            if cand == FR and b not in cfg["frr20_budgets"]:
                continue
            row = {}
            for a in cfg["arms"]:
                rs = [test_result(ctx, store, cand, a, b, s) for s in cfg["seeds"]]
                row[a] = {"val_mean": float(np.mean([r["val_cer_final"] for r in rs])),
                          "test_mean": float(np.mean([r["test_cer_final"] for r in rs])),
                          "test_seeds": [float(r["test_cer_final"]) for r in rs]}
            out[f"{cand}@{b}"] = row
    return out


# --- descriptive seed-1 C2 -----------------------------------------------------------------------------------------


def stage_seed1c2(ctx: L.Ctx35, store, pool) -> dict:
    c = ctx.cfg["seed1_c2"]
    a, b, s = c["arm"], c["budget"], int(c["seed"])
    bc = bctx(ctx, b)
    d = B.sdir(bc, FR, a, s, True)
    if L.clock_hours(ctx) > float(c["start_max_hours"]) and not d.exists() and not (ctx.out / "aligners").exists():
        L.log(ctx, f"[seed1c2] skipped: GPU clock {L.clock_hours(ctx):.2f} h > {c['start_max_hours']} h")
        return {"status": "skipped", "gpu_hours_at_start": round(L.clock_hours(ctx), 3)}
    r = train_one(ctx, store, pool, a, b, s, True)
    if r.get("partial"):
        return {"status": "partial"}
    n = frr20_test(ctx, store, a, b, s)
    dr = frr20_test(ctx, store, a, b, s, True)
    need = L.c2_need(ctx.cfg["rules"], n["test_cer_final"])
    nv = frr20_val(ctx, a, b, s)
    dv = frr20_val(ctx, a, b, s, True)
    return {"status": "done", "run": dr["run"], "normal_test_cer": n["test_cer_final"],
            "deranged_test_cer": dr["test_cer_final"], "needed": need, "pass": bool(dr["test_cer_final"] >= need),
            "normal_val_cer": nv["val_cer_final"], "deranged_val_cer": dv["val_cer_final"],
            "val_needed_with_margin": L.c2_need(ctx.cfg["rules"], nv["val_cer_final"]) + ctx.cfg["rules"]["val_margin"],
            "library_deranged": dv["_library"], "library_normal": nv["_library"]}


# --- summary -------------------------------------------------------------------------------------------------------


def strip(v: dict) -> dict:
    """Keep aggregates only (the verdict has no per-sentence numbers, but be safe)."""
    return json.loads(json.dumps(v, default=float))


def frr20_rows(ctx: L.Ctx35, store, with_test: bool) -> list[dict]:
    keys = ("run", "arm", "budget", "seed", "steps", "skipped", "n_train", "minutes", "val_cer_final",
            "val_shuffled_cer_final", "best_val_step", "best_val_cer", "test_cer_final", "test_cer_bestval",
            "c1_shuffled_cer")
    rows = []
    for s in ctx.cfg["seeds"]:
        for b in ctx.cfg["frr20_budgets"]:
            for a in ctx.cfg["arms"]:
                try:
                    v = frr20_val(ctx, a, b, s)
                except FileNotFoundError:
                    continue
                row = {k: v[k] for k in keys if k in v}
                row.update({"library": v["_library"], "n_texts": v["_n_texts"],
                            "reused_from_p15_35b": is_reused(ctx.cfg, a, b, s, False)})
                if with_test:
                    t = frr20_test(ctx, store, a, b, s)
                    row.update({k: t[k] for k in ("test_cer_final", "test_cer_bestval", "c1_shuffled_cer") if k in t})
                rows.append(row)
    return rows


def stage_summary(ctx: L.Ctx35, store, sel: dict | None, seed1: dict | None, status: str) -> dict:
    agg = {"note": "aggregate only; CER = total edits / total reference characters; val = 106 val sentences, test = 80 "
                   "test sentences (last block of each session); greedy CTC, no LM, final step; plan.md (8790238)",
           "status": status, "selection": sel, "gpu_hours": round(L.clock_hours(ctx), 3)}
    have_test = sel is not None and not sel.get("no_recipe") and status in ("done", "verdict")
    agg["frr20_runs"] = frr20_rows(ctx, store, have_test)
    if have_test:
        agg["primary"] = strip(rule_verdict(ctx, store, sel["chosen"]))
        fixed = {b: (FR if b in ctx.cfg["frr20_budgets"] else "E1a") for b in ctx.cfg["budgets_min"]}
        agg["fixed_rule_descriptive"] = (None if fixed == sel["chosen"] else strip(rule_verdict(ctx, store, fixed)))
        agg["fixed_rule"] = fixed
        agg["recipe_tables_descriptive"] = recipe_tables(ctx, store)
    agg["seed1_c2_descriptive"] = seed1
    agg["time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    e1.save_json(agg, ctx.out / "summary.json")
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, ctx.repo_results / "summary.json")
    if "primary" in agg:
        v = agg["primary"]
        L.log(ctx, "[summary] V1 %s H1 %s H2 %s H3 %s H4 %s C1 %s C2 %s gpu_h %.2f" % (
            v["V1"]["pass"], v.get("H1", {}).get("status"), v.get("H2", {}).get("status"),
            v.get("H3", {}).get("status"), v.get("H4", {}).get("status"), v["C1"]["pass"],
            v.get("C2", {}).get("pass"), agg["gpu_hours"]))
    return agg


# --- main ----------------------------------------------------------------------------------------------------------


def check_out(out: Path) -> bool:
    for f in FORBIDDEN:
        if out == f.resolve() or f.resolve() in out.parents:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-36 runner")
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
    store = None
    try:
        pool = B.stage_textpool(ctx)
        store = R8.WillettStore(ctx.c33.cache)
        if a.stage == "summary":
            sel = read_json(out / "selection.json") if (out / "selection.json").exists() else None
            s1p = out / "seed1c2.json"
            stage_summary(ctx, store, sel, read_json(s1p) if s1p.exists() else None, "done" if sel else "partial")
            return 0
        if not stage_train(ctx, store, pool):
            return 0
        sel = stage_select(ctx)
        if sel["no_recipe"]:
            stage_summary(ctx, store, sel, None, "no_recipe")
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " no_recipe", encoding="utf-8")
            L.log(ctx, "ALL DONE (no_recipe)")
            return 0
        stage_test(ctx, store)
        stage_summary(ctx, store, sel, None, "verdict")
        s1p = out / "seed1c2.json"
        if s1p.exists():
            s1 = read_json(s1p)
        else:
            s1 = stage_seed1c2(ctx, store, pool)
            if s1["status"] == "partial":
                return 0
            e1.save_json(s1, s1p)
        stage_summary(ctx, store, sel, s1, "done")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        L.log(ctx, "ALL DONE")
    except p33.Paused:
        L.clock_save(ctx)
        return PAUSED
    except L.CapReached:
        L.clock_save(ctx)
        L.log(ctx, f"GPU cap {ctx.cfg['gpu_cap_hours']} h reached: stop (plan.md)")
        try:
            sel = read_json(out / "selection.json") if (out / "selection.json").exists() else None
            stage_summary(ctx, store, sel, None, "cap" if sel is None else "verdict")
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
