"""P5-02 precision-type guarantee on the P14-03 replay sets (plan: plan.md). CPU only.

Public API for the guards: fidetype.trust.calibrate(..., target_precision=) -> TrustGuard.decide(x). The data
loaders and the user's decode_fn are imported from the P14-03 run.py (read only, not changed).

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p5-02-precision/run.py t15 t12
Per-trial outputs: C:/Users/zhang/bci-data/derived/p5-02-precision/ only. Repo: aggregates only.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.trust import precision_bound as P  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-02-precision"  # the only place this task writes per-trial files
assert OWN.name == "p5-02-precision"
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOGF = OUT / "run.log"
ALPHA, DELTA, DELTA_P = 0.05, 0.1, 0.1
TARGETS = (0.5, 0.8, 0.9, 0.95)
SEED = 0
N_DRAWS = 1000
DRAW_SIZE = {"t15": 175, "t12": 133}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_p14_03():
    path = REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py"
    spec = importlib.util.spec_from_file_location("p14_03_run", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cp(k: int, n: int) -> list:
    return clopper_pearson(k, n, 0.95)


def resample(items: list[P.PrecisionItem], size: int, c0: float, rng: np.random.Generator) -> dict:
    """Bound check with the held-out items as the population (plan, measure 3)."""
    out = {}
    for tp in TARGETS:
        viol = feas = 0
        rates, precs = [], []
        for _ in range(N_DRAWS):
            idx = rng.choice(len(items), size=2 * size, replace=False)
            res = P.precision_ltt([items[i] for i in idx[:size]], [items[i] for i in idx[size:]],
                                  target_precision=tp, delta=DELTA_P, min_commit_p=c0)
            if res.selected is None:
                continue
            feas += 1
            k = P.precision_counts(items, res.selected)
            prec = 1.0 - k["wrong"] / k["commits"]
            precs.append(prec)
            rates.append(k["commits"] / len(items))
            viol += prec < tp - 1e-12
        se = math.sqrt(DELTA_P * (1 - DELTA_P) / feas) if feas else math.nan
        out[str(tp)] = {"draws": N_DRAWS, "feasible": feas, "violations": viol,
                        "violation_rate": (viol / feas) if feas else None,
                        "limit": (DELTA_P + 3 * se) if feas else None,
                        "pass": (viol / feas <= DELTA_P + 3 * se) if feas >= 50 else None,
                        "mean_population_precision": float(np.mean(precs)) if precs else None,
                        "mean_commit_rate": float(np.mean(rates)) if rates else None}
    return out


def run_set(name: str, M) -> dict:
    t0 = time.time()
    loader = {"t15": M.data_t15, "t12": M.data_t12}[name]
    (cx, ct, cph), (hx, ht, hph), dec, cpm, split = loader()
    fn = M.make_decode_fn(dec)
    ht = [" ".join(t.split()) for t in ht]
    log(f"{name}: calibration {len(cx)}, held out {len(hx)}")
    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=0.08, decode_fn=fn, stream_texts=cph, decoder_name=f"p5-02-{name}",
              modality="intracortical", name=f"p5-02-{name}", seed=SEED)
    out: dict = {"split": split, "n_calibration": len(cx), "n_held_out": len(hx), "alpha": ALPHA, "delta": DELTA,
                 "delta_p": DELTA_P, "targets": {}}
    base = ft.calibrate(cx, ct, **kw)
    c0 = base.sheet.commit_threshold
    log(f"{name}: base {base.config_id} commit_p {c0} in {time.time() - t0:.0f}s")
    # per-item statistics of the held-out set with the base guard at commit_p 0 (resampling + diagnostic)
    from fidetype.trust.dropin import TrustGuard

    g0 = TrustGuard(base.config.with_policy(commit_p=0.0), base._codec, None, fn, True)
    items = []
    for x, t in zip(hx, ht):
        r = g0._decide_quiet(x)
        can = r.action == "commit"
        top = r.text if can else (r.choices[0] if r.choices else "")
        items.append(P.PrecisionItem(can, float(r.p_top1), top != t))
    (OWN / f"items-{name}.json").write_text(json.dumps(
        [{"can_commit": it.can_commit, "p_top1": it.p_top1, "wrong": it.wrong} for it in items]), encoding="utf-8")
    curve = P.precision_curve(items, [1.0, 0.99, 0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])
    out["base"] = {"config_id": base.config_id, "commit_p": c0, "held_out_can_commit": sum(i.can_commit for i in items),
                   "held_out_top1_right": sum(not i.wrong for i in items), "held_out_curve": curve}
    for tp in TARGETS:
        ta = time.time()
        guard = ft.calibrate(cx, ct, target_precision=tp, precision_delta=DELTA_P, **kw)
        sh = guard.sheet
        q = sh.precision
        log(f"{name} target {tp}: {guard.config_id} commit_p {sh.commit_threshold} feasible {q['feasible']} "
            f"(test {q['test_counts']}, {q['n_certified']} certified) in {time.time() - ta:.0f}s")
        res = [guard.decide(x, utterance_id=f"{name}-{i}") for i, x in enumerate(hx)]
        n = len(res)
        com = [(r, t) for r, t in zip(res, ht) if r.action == "commit"]
        nw = sum(r.text != t for r, t in com)
        nr = len(com) - nw
        row = {
            "config_id": guard.config_id, "commit_p": sh.commit_threshold, "feasible": q["feasible"],
            "certified": q["n_certified"], "calibration_test_counts": q["test_counts"],
            "calibration_precision_lower": q["test_precision_lower"], "min_commits": q["min_commits"],
            "controls": [c.to_dict() for c in sh.controls],
            "controls_pass": all(c.passed for c in sh.controls),
            "n": n, "commits": len(com), "wrong": nw, "commit_rate": len(com) / n,
            "precision": (nr / len(com)) if com else None,
            "precision_cp95": cp(nr, len(com)) if com else None,
            "wrong_commit_rate": nw / n, "wrong_commit_cp95": cp(nw, n),
        }
        row["p1_pass"] = (nw / len(com) <= 1 - tp + 1e-12) if com else None
        row["marginal_le_alpha"] = nw / n <= ALPHA
        out["targets"][str(tp)] = row
        tag = f"{name}-p{tp:.2f}"
        guard.save(OWN / f"guard-{tag}.json")
        (OWN / f"decisions-{tag}.json").write_text(json.dumps(
            [{"i": i, "action": r.action, "p_top1": r.p_top1, "text": r.text, "truth": t}
             for i, (r, t) in enumerate(zip(res, ht))]), encoding="utf-8")
        log(f"{name} target {tp}: held out {len(com)}/{n} commits, {nw} wrong, precision {row['precision']} "
            f"CP95 {row['precision_cp95']}; controls pass {row['controls_pass']}")
    rng = np.random.default_rng([SEED, 502, len(name)])
    finite_c0 = c0 if math.isfinite(c0) else math.inf
    out["resampling"] = resample(items, DRAW_SIZE[name], finite_c0, rng)
    out["resampling_unconstrained"] = resample(items, DRAW_SIZE[name], -math.inf, rng)
    log(f"{name}: resampling {json.dumps(out['resampling'])}")
    log(f"{name}: resampling (no min_commit_p) {json.dumps(out['resampling_unconstrained'])}")
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main() -> None:
    stages = sys.argv[1:] or ["t15", "t12"]
    M = load_p14_03()
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = FT_VERSION
    for st in stages:
        log(f"stage {st} start")
        allr[st] = run_set(st, M)
        path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
        log(f"stage {st} done")


if __name__ == "__main__":
    main()
