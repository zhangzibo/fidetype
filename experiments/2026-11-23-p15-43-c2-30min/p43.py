r"""P15-43 runner: C2 budget range of the F-R20 recipe (gap 194) - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this task, bd673ae).
Reuses READ-ONLY: P15-41 ``p41.py`` (and through it P15-36 ``p36.py``, P15-35b, P15-33, P15-08 code); the normal
E test results of P15-35b / P15-36 / P15-41 and the old deranged test results (seeds 0, 1 at 30 min; 2-4 at 10 min).
Writes only to C:\Users\zhang\bci-data\derived\p15-43\.

Order: stage S30 (E-b30-s{2,3,4}-labelshuf, always all 3), then stage S3 (E-b3-s{0..4}-labelshuf, stop at the
first seed that fails C2). Each run: own deranged recipe-A aligner -> deranged library -> F-R20 run -> test readout.
Then summary.json and DONE.

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-p15-43-c2-30min\p43.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
P41_DIR = HERE.parent / "2026-11-22-p15-41-more-seeds"
sys.path.insert(0, str(P41_DIR))
import p41 as P41  # noqa: E402

P36, B, L = P41.P36, P41.B, P41.L
p33, e1, R8 = P41.p33, P41.e1, P41.R8
FR = P41.FR

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-43")
FORBIDDEN = P41.FORBIDDEN + [Path(r"C:\Users\zhang\bci-data\derived\p15-41")]
PAUSED = 3
ARM = "E"
ALL_BUDGETS = ["3", "10", "30"]


def make_ctx(cfg_path: Path, out: Path, device: str) -> L.Ctx35:
    return L.make_ctx(cfg_path, out, device, None)


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# --- pure rules ----------------------------------------------------------------------------------------------------


def c2_row(normal: float | None, deranged: float | None, rules: dict) -> dict:
    """One seed at one budget. normal / deranged = final-step test CER (None = run missing)."""
    if normal is None or deranged is None:
        return {"status": "missing", "pass": False, "normal_test_cer": normal, "deranged_test_cer": deranged}
    need = L.c2_need(rules, float(normal))
    return {"status": "done", "normal_test_cer": float(normal), "deranged_test_cer": float(deranged),
            "needed": need, "margin": float(deranged) - need, "pass": bool(float(deranged) >= need)}


def budget_status(rows: dict, seeds: list[int]) -> str:
    """'pass' = done and pass on every seed; 'fail' = at least one done seed fails; else 'not_determined'."""
    st = [rows.get(str(s), {"status": "missing"}) for s in seeds]
    if any(r["status"] == "done" and not r["pass"] for r in st):
        return "fail"
    if all(r["status"] == "done" and r["pass"] for r in st):
        return "pass"
    return "not_determined"


def smallest_passing(status: dict, order: list[str] = ALL_BUDGETS) -> str:
    """Smallest budget with status 'pass'. A 'not_determined' budget before any pass stops the search."""
    for b in order:
        if status[b] == "pass":
            return b
        if status[b] == "not_determined":
            return "not_determined"
    return "none"


def outcome(status: dict) -> str:
    """Plan outcome letter from the 3- and 30-min statuses (10 min is a known fail)."""
    s3, s30 = status["3"], status["30"]
    if "not_determined" in (s3, s30):
        return "not_determined"
    return {("fail", "pass"): "A", ("pass", "pass"): "B", ("fail", "fail"): "C", ("pass", "fail"): "D"}[(s3, s30)]


# --- results -------------------------------------------------------------------------------------------------------


def normal_cer(cfg: dict, budget: str, seed: int) -> float | None:
    src = cfg["sources"]["normal_test"].get(R8.run_name(ARM, budget, seed))
    if src is None:
        src = cfg["sources"]["old_normal_10min"].get(R8.run_name(ARM, budget, seed))
    if src is None or not (Path(src) / "result.json").exists():
        return None
    r = read_json(Path(src) / "result.json")
    if bool(r.get("label_shuffle")) or str(r["budget"]) != str(budget):
        raise RuntimeError(f"normal run {src} has the wrong labels or budget")
    return float(r["test_cer_final"])


def deranged_result(ctx: L.Ctx35, budget: str, seed: int) -> dict | None:
    """New deranged run of this task, or an old one (read-only)."""
    name = R8.run_name(ARM, budget, seed, True)
    old = ctx.cfg["sources"]["old_deranged_test"].get(name)
    if old is not None:
        p = Path(old) / "result.json"
        return read_json(p) if p.exists() else None
    if budget not in ctx.cfg["budgets_min"]:
        return None
    return P41.new_result(ctx, ARM, budget, seed, True)


def c2_table(ctx: L.Ctx35) -> dict:
    cfg = ctx.cfg
    tab = {}
    for b in ALL_BUDGETS:
        rows = {}
        for s in cfg["seeds"]:
            d = deranged_result(ctx, b, s)
            n = normal_cer(cfg, b, s)
            if d is None and b == "10" and s in (0, 1):
                rows[str(s)] = {"status": "not_run", "pass": False}
                continue
            if d is not None and (not bool(d.get("label_shuffle")) or str(d["budget"]) != b):
                raise RuntimeError(f"deranged run {d.get('run')} has the wrong labels or budget")
            rows[str(s)] = c2_row(n, None if d is None else float(d["test_cer_final"]), cfg["rules"])
            if d is not None:
                rows[str(s)]["deranged_val_cer"] = d.get("val_cer_final")
        tab[b] = rows
    return tab


# --- stages --------------------------------------------------------------------------------------------------------


def stage_runs(ctx: L.Ctx35, store, pool, max_steps: int | None = None) -> str:
    """Returns 'done' or 'partial'. stages.json keeps the sequential state (stop at first fail in S3)."""
    cfg = ctx.cfg
    spath = ctx.out / "stages.json"
    st = read_json(spath) if spath.exists() else {}
    for stage in cfg["stages"]:
        name, b = stage["name"], str(stage["budget"])
        rec = st.setdefault(name, {"budget": b, "seeds": {}, "status": "started"})
        if rec["status"] == "done":
            continue
        L.log(ctx, f"[{name}] budget {b} seeds {stage['seeds']} at GPU clock {L.clock_hours(ctx):.2f} h")
        stopped = False
        for s in stage["seeds"]:
            if rec["seeds"].get(str(s), {}).get("status") in ("done", "not_needed"):
                stopped = stopped or (rec["seeds"][str(s)].get("pass") is False and stage["stop_at_first_fail"])
                continue
            if stopped:
                rec["seeds"][str(s)] = {"status": "not_needed"}
                e1.save_json(st, spath)
                continue
            r = P36.train_one(ctx, store, pool, ARM, b, s, True, max_steps)
            if r.get("partial"):
                e1.save_json(st, spath)
                return "partial"
            d = P41.test_one(ctx, store, ARM, b, s, True)
            row = c2_row(normal_cer(cfg, b, s), float(d["test_cer_final"]), cfg["rules"])
            rec["seeds"][str(s)] = {"status": "done", "pass": row["pass"]}
            e1.save_json(st, spath)
            L.log(ctx, f"[{name}] C2 seed {s}: deranged {row['deranged_test_cer']:.4f} needed {row['needed']:.4f} "
                       f"pass {row['pass']}")
            if not row["pass"] and stage["stop_at_first_fail"]:
                stopped = True
                L.log(ctx, f"[{name}] first fail at seed {s}: later seeds not needed (plan.md)")
        rec["status"] = "done"
        rec["gpu_hours_at_end"] = round(L.clock_hours(ctx), 3)
        e1.save_json(st, spath)
    return "done"


def run_rows(ctx: L.Ctx35) -> list[dict]:
    """Aggregates of every new deranged run (val, test, library, aligner); no per-sentence numbers."""
    rows = []
    for stage in ctx.cfg["stages"]:
        b = str(stage["budget"])
        for s in stage["seeds"]:
            sd = P41.run_dir(ctx, ARM, b, s, True)
            if not (sd / "result.json").exists():
                continue
            v = read_json(sd / "result.json")
            c = read_json(sd / "config.json")
            row = {k: v.get(k) for k in ("run", "arm", "budget", "seed", "label_shuffle", "steps", "skipped",
                                         "n_train", "minutes", "val_cer_final", "val_shuffled_cer_final",
                                         "best_val_step", "best_val_cer")}
            row["library"] = {k: x for k, x in (c.get("library") or {}).items() if k != "aligner"}
            row["n_texts"] = c.get("n_texts")
            ad = ctx.out / "aligners" / R8.run_name(ARM, b, s, True) / "result.json"
            if ad.exists():
                a = read_json(ad)
                row["aligner_val_cer_final"] = a.get("val_cer_final")
                row["aligner_steps"] = a.get("steps")
            t = P41.new_result(ctx, ARM, b, s, True)
            if t is not None:
                row.update({k: t[k] for k in ("test_cer_final", "test_cer_bestval") if k in t})
            rows.append(row)
    return rows


def stage_summary(ctx: L.Ctx35, status: str, repo_results: Path | None = HERE / "results") -> dict:
    cfg = ctx.cfg
    tab = c2_table(ctx)
    bst = {b: budget_status(tab[b], cfg["seeds"]) for b in ALL_BUDGETS}
    agg = {"note": "aggregate only; CER = total edits / total reference characters; test = 80 test sentences (last "
                   "block of each session); greedy CTC, no LM, final step; recipe F-R20; arm E; plan.md (bd673ae)",
           "status": status, "gpu_hours": round(L.clock_hours(ctx), 3),
           "rule": "C2 passes on a seed if deranged test CER >= max(0.75, normal + 0.10); at a budget if on every "
                   "seed 0-4",
           "stages": read_json(ctx.out / "stages.json") if (ctx.out / "stages.json").exists() else {},
           "C2": tab, "budget_status": bst, "smallest_passing_budget": smallest_passing(bst),
           "outcome": outcome(bst), "budget_100_min": "not tested (no F-R20 100-min recipe; plan.md)",
           "runs": run_rows(ctx), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    agg = json.loads(json.dumps(agg, default=float))
    e1.save_json(agg, ctx.out / "summary.json")
    if repo_results is not None:
        repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, repo_results / "summary.json")
    L.log(ctx, f"[summary] budget status {bst} smallest {agg['smallest_passing_budget']} outcome {agg['outcome']} "
               f"gpu_h {agg['gpu_hours']:.2f}")
    return agg


# --- main ----------------------------------------------------------------------------------------------------------


def check_out(out: Path) -> bool:
    for f in FORBIDDEN:
        if out == f.resolve() or f.resolve() in out.parents:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-43 runner")
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
        if a.stage == "summary":
            stage_summary(ctx, "summary")
            return 0
        pool = B.stage_textpool(ctx)
        store = R8.WillettStore(ctx.c33.cache)
        if stage_runs(ctx, store, pool) != "done":
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
