"""P5-01 part S: synthetic false-alarm rates and detection delays of the drift tests (plan.md, part S).

    python -I synth.py            -> results/synth.json
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from fidetype.trust.drift import ConformalDriftTest, RiskDriftTest  # noqa: E402

SEED = 20261116
OUT = HERE / "results"


def se(p: float, n: int) -> float:
    return math.sqrt(p * (1 - p) / n)


def fa_scores(level: float, runs: int, rng: np.random.Generator) -> float:
    a = 0
    for r in range(runs):
        t = ConformalDriftTest(rng.normal(size=200), level=level, seed=int(rng.integers(1 << 30)))
        t.update_many(rng.normal(size=2000))
        a += t.alarmed
    return a / runs


def fa_risk(level: float, runs: int, rng: np.random.Generator) -> float:
    return sum(RiskDriftTest(0.05, level=level).update_many(rng.random(2000) < 0.05).alarmed
               for _ in range(runs)) / runs


def summarise(d: list[float]) -> dict:
    arr = np.asarray(d, dtype=float)
    fin = arr[np.isfinite(arr)]
    return {"runs": len(d), "never_detected": int((~np.isfinite(arr)).sum()),
            "median": float(np.median(arr)) if len(fin) > len(d) / 2 else "inf",
            "p90": float(np.quantile(arr, 0.9)) if np.isfinite(np.quantile(arr, 0.9)) else "inf",
            "mean_detected": float(fin.mean()) if len(fin) else None}


def delay_scores(shift: float, sd: float, runs: int, rng: np.random.Generator) -> dict:
    d = []
    for _ in range(runs):
        t = ConformalDriftTest(rng.normal(size=200), level=0.01, seed=int(rng.integers(1 << 30)))
        t.update_many(rng.normal(size=500))
        n0 = t.n
        for x in rng.normal(shift, sd, size=5000):
            if t.update(x).alarmed:
                break
        d.append(t.n - n0 if t.alarmed and t.alarm_at > n0 else (0 if t.alarmed else math.inf))
    return summarise(d)


def delay_risk(rate: float, runs: int, rng: np.random.Generator) -> dict:
    d = []
    for _ in range(runs):
        t = RiskDriftTest(0.05, level=0.01)
        t.update_many(rng.random(300) < 0.02)
        n0 = t.n
        for x in rng.random(5000) < rate:
            if t.update(x).alarmed:
                break
        d.append(t.n - n0 if t.alarmed and t.alarm_at > n0 else (0 if t.alarmed else math.inf))
    return summarise(d)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    res: dict = {"seed": SEED, "false_alarms": [], "delays": {"scores": [], "risk": []}}
    for level in (0.01, 0.05):
        for name, fn in (("scores", fa_scores), ("risk", fa_risk)):
            r = fn(level, 1000, rng)
            lim = level + 3 * se(level, 1000)
            res["false_alarms"].append({"test": name, "level": level, "runs": 1000, "rate": r, "limit": lim,
                                        "pass": r <= lim})
            print(name, level, r, lim, flush=True)
    for shift, sd in ((-0.25, 1.0), (-0.5, 1.0), (-1.0, 1.0), (0.0, 2.0)):
        s = delay_scores(shift, sd, 200, rng)
        s.update({"shift": shift, "sd": sd})
        res["delays"]["scores"].append(s)
        print("delay scores", shift, sd, s, flush=True)
    for rate in (0.10, 0.20, 0.50):
        s = delay_risk(rate, 200, rng)
        s["rate"] = rate
        res["delays"]["risk"].append(s)
        print("delay risk", rate, s, flush=True)
    res["S1_pass"] = all(f["pass"] for f in res["false_alarms"])
    res["seconds"] = round(time.time() - t0, 1)
    (OUT / "synth.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print("done", res["S1_pass"], res["seconds"])


if __name__ == "__main__":
    main()
