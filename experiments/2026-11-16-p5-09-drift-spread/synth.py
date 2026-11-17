"""P5-09: spread bets of the conformal drift test (plan.md). CPU only.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p5-09-drift-spread/synth.py
-> results/synth.json (aggregates only). Part P reads the P5-01 replay input (read only, no text field).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from fidetype.trust.drift import ConformalDriftTest  # noqa: E402

SEED = 20261117
OUT = HERE / "results"
PILOT = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot/replay/frozen")
GATED = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot-gated/replay/frozen")
VARIANTS = {"M": False, "MS": True}


def se(p: float, n: int) -> float:
    return math.sqrt(p * (1 - p) / n)


def false_alarms(level: float, runs: int, rng: np.random.Generator) -> dict:
    a = {k: 0 for k in VARIANTS}
    for _ in range(runs):
        ref, live, seed = rng.normal(size=200), rng.normal(size=2000), int(rng.integers(1 << 30))
        for k, sp in VARIANTS.items():
            t = ConformalDriftTest(ref, level=level, seed=seed, spread=sp)
            t.update_many(live)
            a[k] += t.alarmed
    lim = level + 3 * se(level, runs)
    return {"level": level, "runs": runs, "limit": lim, **{f"rate_{k}": a[k] / runs for k in VARIANTS},
            "pass_MS": a["MS"] / runs <= lim}


def summarise(d: list[float], early: int) -> dict:
    arr = np.asarray(d, dtype=float)
    fin = arr[np.isfinite(arr)]
    q90 = float(np.quantile(arr, 0.9))
    return {"runs": len(d), "detected": int(len(fin)), "detected_frac": len(fin) / len(d),
            "never_detected": int((~np.isfinite(arr)).sum()), "alarm_before_change": early,
            "median": float(np.median(arr)) if len(fin) > len(d) / 2 else "inf",
            "p90": q90 if math.isfinite(q90) else "inf",
            "mean_detected": float(fin.mean()) if len(fin) else None}


def delays(shift: float, sd: float, runs: int, rng: np.random.Generator) -> dict:
    d = {k: [] for k in VARIANTS}
    early = {k: 0 for k in VARIANTS}
    for _ in range(runs):
        ref, null = rng.normal(size=200), rng.normal(size=500)
        live, seed = rng.normal(shift, sd, size=5000), int(rng.integers(1 << 30))
        for k, sp in VARIANTS.items():
            t = ConformalDriftTest(ref, level=0.01, seed=seed, spread=sp)
            t.update_many(null)
            n0 = t.n
            if t.alarmed:
                early[k] += 1
                d[k].append(0)
                continue
            for x in live:
                if t.update(x).alarmed:
                    break
            d[k].append(t.n - n0 if t.alarmed else math.inf)
    return {"shift": shift, "sd": sd, **{k: summarise(d[k], early[k]) for k in VARIANTS}}


def load_t12() -> tuple[np.ndarray, np.ndarray]:
    sc, gr = [], []
    for day in range(8, 24):
        with open(PILOT / f"records-S{day:02d}.pkl", "rb") as f:
            a = pickle.load(f)
        with open(GATED / f"records-S{day:02d}.pkl", "rb") as f:
            b = pickle.load(f)
        if len(a) != len(b):
            raise SystemExit(f"S{day}: item counts differ")
        for x, y in zip(a, b):
            if x["id"] != y["id"] or not (x["score"] == y["score"]):
                raise SystemExit(f"S{day}: ids or scores differ")
            sc.append(float(x["score"]))
            gr.append(float(y["guard_risk"]))
    return np.asarray(sc), np.asarray(gr)


def permutation(runs: int = 200, level: float = 0.05) -> dict:
    sc, gr = load_t12()
    out: dict = {"n_items": int(len(sc)), "runs": runs, "level": level, "limit": level + 3 * se(level, runs)}
    for name, x in (("p_top1", sc), ("guard_risk", gr)):
        a = {k: 0 for k in VARIANTS}
        for r in range(runs):
            s = x[np.random.default_rng(r).permutation(len(x))]
            for k, sp in VARIANTS.items():
                t = ConformalDriftTest(s[:48], level=level, seed=r, spread=sp)
                t.update_many(s[48:])
                a[k] += t.alarmed
        out[name] = {f"rate_{k}": a[k] / runs for k in VARIANTS}
        out[name]["pass_MS"] = a["MS"] / runs <= out["limit"]
        print("perm", name, out[name], flush=True)
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    res: dict = {"seed": SEED, "plan": "experiments/2026-11-16-p5-09-drift-spread/plan.md"}
    res["S1_false_alarms"] = [false_alarms(lv, 1000, rng) for lv in (0.01, 0.05)]
    print("S1", res["S1_false_alarms"], flush=True)
    res["S2_spread"] = []
    for sd in (2.0, 0.5, 1.5):
        r = delays(0.0, sd, 200, rng)
        res["S2_spread"].append(r)
        print("S2", sd, r, flush=True)
    res["S3_mean"] = []
    for shift in (-0.25, -0.5, -1.0):
        r = delays(shift, 1.0, 200, rng)
        res["S3_mean"].append(r)
        print("S3", shift, r, flush=True)
    res["S4_permutation_t12"] = permutation()
    sp = {r["sd"]: r for r in res["S2_spread"]}
    mn = {r["shift"]: r for r in res["S3_mean"]}

    def med(r: dict) -> float:
        v = r["median"]
        return math.inf if isinstance(v, str) else float(v)

    s3 = {str(sh): med(mn[sh]["MS"]) <= 1.25 * med(mn[sh]["M"]) for sh in (-0.5, -1.0)}
    s3["-0.25"] = mn[-0.25]["MS"]["detected_frac"] >= mn[-0.25]["M"]["detected_frac"] - 0.10
    p = res["S4_permutation_t12"]
    res["criteria"] = {
        "S1": all(r["pass_MS"] for r in res["S1_false_alarms"]),
        "S2": sp[2.0]["MS"]["detected_frac"] >= 0.95 and sp[0.5]["MS"]["detected_frac"] >= 0.90,
        "S3": all(s3.values()), "S3_parts": s3,
        "S4": p["p_top1"]["pass_MS"] and p["guard_risk"]["pass_MS"],
    }
    res["seconds"] = round(time.time() - t0, 1)
    (OUT / "synth.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print("criteria", res["criteria"], "seconds", res["seconds"])


if __name__ == "__main__":
    main()
