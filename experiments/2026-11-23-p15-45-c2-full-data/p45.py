r"""P15-45 runner: C2 (label-deranged control) at the full-data budget of E1 (gap 197) - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this task, 20f9f5b).
Reuses READ-ONLY: P15-08 ``run.py`` / ``e1.py`` (``train_run`` unchanged, E1a recipe at budget "all", 3,000 steps),
the P15-08 Willett cache, and the normal E-ball-s0 / E-ball-s1 test results of P15-08.
Writes only to C:\Users\zhang\bci-data\derived\p15-45\.

Order (config.json ``new_runs_in_order``): deranged s0, s1; then normal + deranged for s2, s3, s4. No early stop on a
fail. GPU cap checked before each run. Then summary.json and DONE.

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-23-p15-45-c2-full-data\p45.py all
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
ROOT = HERE.parents[1]
P08_DIR = HERE.parent / "2026-11-19-p15-08-e1-cross-body"
sys.path.insert(0, str(P08_DIR))
import e1  # noqa: E402
import run as R8  # noqa: E402

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-45")
DERIVED = Path(r"C:\Users\zhang\bci-data\derived")
PAUSED = 3


class CapReached(Exception):
    pass


# --- pure rules ----------------------------------------------------------------------------------------------------


def c2_need(rules: dict, normal: float) -> float:
    return max(float(rules["c2_min_cer"]), float(normal) + float(rules["c2_min_gap"]))


def c2_row(normal: float | None, deranged: float | None, rules: dict) -> dict:
    """One seed. normal / deranged = final-step test CER (None = run missing)."""
    if normal is None or deranged is None:
        return {"status": "missing", "pass": None, "normal_test_cer": normal, "deranged_test_cer": deranged}
    need = c2_need(rules, normal)
    return {"status": "done", "normal_test_cer": float(normal), "deranged_test_cer": float(deranged),
            "needed": need, "margin": float(deranged) - need, "pass": bool(float(deranged) >= need)}


def outcome(rows: dict, n_seeds: int, min_seeds: int = 3) -> str:
    """plan.md outcomes: A (all seeds done, all pass), A3 (>= min_seeds done, all pass, some missing),
    B (some fail, some pass), C (all done seeds fail, >= min_seeds done), N (not determined)."""
    done = [r for r in rows.values() if r["status"] == "done"]
    n_pass = sum(1 for r in done if r["pass"])
    n_fail = len(done) - n_pass
    if n_fail == 0:
        if len(done) == n_seeds:
            return "A"
        return "A3" if len(done) >= min_seeds else "N"
    if n_pass > 0:
        return "B"
    return "C" if len(done) >= min_seeds else "C_partial"


def parse_run(name: str) -> tuple[str, str, int, bool]:
    """'E-ball-s2-labelshuf' -> ('E', 'all', 2, True)."""
    parts = name.split("-")
    arm, b, s = parts[0], parts[1], parts[2]
    if not (b.startswith("b") and s.startswith("s")):
        raise ValueError(name)
    return arm, b[1:], int(s[1:]), len(parts) > 3 and parts[3] == "labelshuf"


def check_out(out: Path, derived: Path = DERIVED, own: str = "p15-45") -> bool:
    """Only the own folder (or a folder outside the shared derived tree, e.g. a scratch smoke folder)."""
    out = out.resolve()
    d = derived.resolve()
    if out == d:
        return False
    if d in out.parents:
        rel = out.relative_to(d).parts
        return rel[0] == own
    return True


# --- GPU clock -----------------------------------------------------------------------------------------------------


class Clock:
    def __init__(self, path: Path):
        self.path = path
        self.base = json.loads(path.read_text(encoding="utf-8"))["seconds"] if path.exists() else 0.0
        self.t0 = time.time()
        self.launches = json.loads(path.read_text(encoding="utf-8")).get("launches", []) if path.exists() else []
        self.launches.append({"start": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def seconds(self) -> float:
        return self.base + (time.time() - self.t0)

    def hours(self) -> float:
        return self.seconds() / 3600.0

    def save(self) -> None:
        self.launches[-1]["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.launches[-1]["seconds"] = round(time.time() - self.t0, 1)
        e1.save_json({"seconds": round(self.seconds(), 1), "launches": self.launches}, self.path)


# --- runs ----------------------------------------------------------------------------------------------------------


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def make_ctx(cfg: dict, out: Path, device: str) -> R8.Ctx:
    ctx = R8.ctx_from_config(ROOT / cfg["recipe_config"], out, device, cache=Path(cfg["sources"]["willett_cache"]))
    ctx.repo_results = None  # never write into the P15-08 results folder
    if int(ctx.ft.steps[cfg["budget"]]) != int(cfg["steps"]):
        raise RuntimeError("recipe steps differ from the pre-registered value")
    return ctx


def result_of(cfg: dict, out: Path, seed: int, deranged: bool) -> dict | None:
    name = R8.run_name(cfg["arm"], cfg["budget"], seed, deranged)
    src = None if deranged else cfg["sources"]["normal_test_reused"].get(name)
    p = (Path(src) if src else out / "runs" / name) / "result.json"
    if not p.exists():
        return None
    r = read_json(p)
    if bool(r.get("label_shuffle")) != deranged or str(r["budget"]) != cfg["budget"] or r["arm"] != cfg["arm"]:
        raise RuntimeError(f"run {p.parent} has the wrong labels, budget or arm")
    if int(r["steps"]) != int(cfg["steps"]):
        raise RuntimeError(f"run {p.parent} did not finish {cfg['steps']} steps")
    return r


def c2_table(cfg: dict, out: Path) -> dict:
    rows = {}
    for s in cfg["seeds"]:
        n, d = result_of(cfg, out, s, False), result_of(cfg, out, s, True)
        rows[str(s)] = c2_row(None if n is None else n["test_cer_final"], None if d is None else d["test_cer_final"],
                              cfg["rules"])
        rows[str(s)]["normal_source"] = "P15-08 (reused)" if R8.run_name(cfg["arm"], cfg["budget"], s) in \
            cfg["sources"]["normal_test_reused"] else "P15-45 (new)"
    return rows


def run_rows(cfg: dict, out: Path) -> list[dict]:
    rows = []
    for name in cfg["new_runs_in_order"]:
        p = out / "runs" / name / "result.json"
        if not p.exists():
            rows.append({"run": name, "status": "not_run"})
            continue
        r = read_json(p)
        row = {k: r[k] for k in ("run", "arm", "budget", "seed", "label_shuffle", "steps", "skipped", "n_train",
                                 "minutes", "test_cer_final", "test_cer_bestval", "best_val_step", "best_val_cer",
                                 "c1_shuffled_cer") if k in r}
        m = out / "runs" / name / "metrics.jsonl"
        if m.exists():
            last = [json.loads(x) for x in m.read_text(encoding="utf-8").splitlines() if x.strip()][-1]
            row["val_cer_final"] = last["val_cer"]
        row["status"] = "done"
        rows.append(row)
    return rows


def stage_runs(ctx: R8.Ctx, cfg: dict, store, clock: Clock, max_steps: int | None = None) -> str:
    for name in cfg["new_runs_in_order"]:
        arm, b, s, ls = parse_run(name)
        if (ctx.out / "runs" / name / "DONE.json").exists():
            continue
        if clock.hours() >= float(cfg["gpu_cap_hours"]):
            raise CapReached()
        R8.log(ctx, f"[{name}] start at GPU clock {clock.hours():.2f} h")
        r = R8.train_run(ctx, store, arm, b, s, ls, max_steps=max_steps)
        clock.save()
        if r.get("partial"):
            return "partial"
        if ls:
            n = result_of(cfg, ctx.out, s, False) if max_steps is None else None
            if n is not None:
                row = c2_row(n["test_cer_final"], r["test_cer_final"], cfg["rules"])
                R8.log(ctx, f"[{name}] C2 seed {s}: deranged {row['deranged_test_cer']:.4f} needed "
                            f"{row['needed']:.4f} pass {row['pass']}")
    return "done"


def stage_summary(cfg: dict, out: Path, status: str, gpu_hours: float, repo_results: Path | None) -> dict:
    tab = c2_table(cfg, out)
    normals = [r["normal_test_cer"] for r in tab.values() if r["normal_test_cer"] is not None]
    agg = {"note": "aggregate only; CER = total edits / total reference characters; test = 80 test sentences (last "
                   "block of each session); greedy CTC, no LM, final step; recipe E1a at budget 'all' (3,000 steps); "
                   "arm E; plan.md (20f9f5b)",
           "status": status, "gpu_hours": round(gpu_hours, 3),
           "rule": "C2 passes on a seed if deranged test CER >= max(0.75, normal + 0.10); 'passes at full data' if "
                   "it passes on every seed that ran and >= 3 seeds ran",
           "C2": tab, "n_done": sum(1 for r in tab.values() if r["status"] == "done"),
           "n_pass": sum(1 for r in tab.values() if r["pass"]),
           "outcome": outcome(tab, len(cfg["seeds"]), int(cfg["min_seeds_done_when"])),
           "normal_test_cer_mean": (sum(normals) / len(normals)) if normals else None,
           "normal_test_cer_range": [min(normals), max(normals)] if normals else None,
           "runs": run_rows(cfg, out), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    agg = json.loads(json.dumps(agg, default=float))
    e1.save_json(agg, out / "summary.json")
    if repo_results is not None:
        repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, repo_results / "summary.json")
    return agg


# --- main ----------------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-45 runner")
    ap.add_argument("stage", choices=("all", "summary", "smoke"))
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
    ctx = make_ctx(cfg, out, a.device)
    torch.set_num_threads(2)
    R8.log(ctx, f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    if a.stage == "summary":
        c = Clock(out / "gpu_clock.json") if (out / "gpu_clock.json").exists() else None
        agg = stage_summary(cfg, out, "summary", c.base / 3600 if c else 0.0, HERE / "results")
        R8.log(ctx, f"[summary] outcome {agg['outcome']} pass {agg['n_pass']}/{agg['n_done']}")
        return 0
    clock = Clock(out / "gpu_clock.json")
    R8.keep_awake(True)
    try:
        store = R8.WillettStore(ctx.cache)
        if a.stage == "smoke":
            ctx.ft.steps = {k: a.smoke_steps for k in ctx.ft.steps}
            ctx.ft.val_every = 10
            scfg = {**cfg, "steps": a.smoke_steps, "new_runs_in_order": ["E-ball-s2", "E-ball-s2-labelshuf"],
                    "seeds": [2], "sources": {**cfg["sources"], "normal_test_reused": {}}}
            stage_runs(ctx, scfg, store, clock)
            agg = stage_summary(scfg, out, "smoke", clock.hours(), None)
            R8.log(ctx, f"[smoke] outcome {agg['outcome']} (smoke numbers are not results)")
            return 0
        if stage_runs(ctx, cfg, store, clock) != "done":
            return 0
        clock.save()
        agg = stage_summary(cfg, out, "done", clock.hours(), HERE / "results")
        R8.log(ctx, f"[summary] outcome {agg['outcome']} pass {agg['n_pass']}/{agg['n_done']} "
                    f"gpu_h {agg['gpu_hours']:.2f}")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        R8.log(ctx, "ALL DONE")
    except R8.Paused:
        return PAUSED
    except CapReached:
        clock.save()
        R8.log(ctx, f"GPU cap {cfg['gpu_cap_hours']} h reached: stop (plan.md)")
        stage_summary(cfg, out, "cap", clock.hours(), HERE / "results")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    except Exception as ex:  # noqa: BLE001 - leave a FAILED marker for the watcher
        R8.log(ctx, f"FAILED: {ex!r}")
        (out / "FAILED").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + f" {ex!r}", encoding="utf-8")
        raise
    finally:
        clock.save()
        R8.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
