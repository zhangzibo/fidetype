"""P5-42 synthetic validation of calibrate(users=...): cases A-D of plan.md. CPU only.

Pre-registration: plan.md (this folder, commit ad51861). n-best input, alpha 0.05, delta 0.1, 4 users x 300
items, 20 replicates (seeds 1-20) per case. Writes results/synth.json (synthetic data only).

Usage (repo root): python experiments/2026-11-25-p5-42-per-user-null/synth.py [--jobs 3]
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
ALPHA, DELTA = 0.05, 0.1
K, M = 4, 300  # users, items per user (calibration)
M_TEST = 3000  # case D test items per user
SEEDS = tuple(range(1, 21))
PHRASES = ["yes please", "thank you", "i am thirsty", "call my wife", "turn on the light", "i need help",
           "open the window", "good morning", "how are you", "more water please"]


def item(rng: np.random.Generator, right: bool, conf: float) -> tuple[list[tuple[str, float]], str]:
    """One n-best list and its truth: the top-1 margin grows with ``conf``; the top-1 is the truth iff ``right``."""
    truth = str(rng.choice(PHRASES))
    others = [str(p) for p in rng.choice([p for p in PHRASES if p != truth], size=3, replace=False)]
    top = truth if right else others[0]
    rest = [others[0] if right else truth, others[1], others[2]]
    gap = 0.5 + 6.0 * float(np.clip(conf, 0.0, 1.0))
    nb = [(top, 0.0)] + [(t, float(-gap * rng.uniform(0.8, 1.2))) for t in rest]
    return nb, truth


def draw(case: str, rng: np.random.Generator, m: int) -> tuple[list, list[str], list[int]]:
    xs, ts, us = [], [], []
    for u in range(K):
        for _ in range(m):
            if case == "A":  # pure base-rate leak: the margin depends on the user only
                b = (0.2, 0.45, 0.7, 0.95)[u]
                conf, right = b + rng.normal(0.0, 0.05), rng.random() < b
            else:
                if case == "C":
                    mu = (0.35, 0.55, 0.75, 0.9)[u]
                    z = rng.beta(mu * 6.0, (1.0 - mu) * 6.0)
                else:  # B, D
                    z = rng.uniform(0.2, 1.0)
                p = 0.6 * z if (case == "D" and u == K - 1) else z
                conf, right = z, rng.random() < p
            nb, t = item(rng, bool(right), float(conf))
            xs.append(nb)
            ts.append(t)
            us.append(u)
    perm = rng.permutation(len(xs))
    return [xs[i] for i in perm], [ts[i] for i in perm], [us[i] for i in perm]


def nulls(rng: np.random.Generator, n: int = 100) -> list:
    return [[(str(p), float(-rng.uniform(0.0, 0.5))) for p in rng.choice(PHRASES, size=4, replace=False)]
            for _ in range(n)]


def per_user_test(guard, case: str, seed: int) -> dict:
    rng = np.random.default_rng([seed, 99])
    xs, ts, us = draw(case, rng, M_TEST)
    rate = np.zeros(K)
    com = np.zeros(K)
    for x, t, u in zip(xs, ts, us):
        r = guard._decide_quiet(x)
        if r.action == "commit":
            com[u] += 1
            rate[u] += int(r.text.split() != t.split())
    return {"wrong_rate": (rate / M_TEST).tolist(), "commits": com.astype(int).tolist()}


def run(job: tuple[str, int]) -> dict:
    import fidetype.trust as ft

    case, seed = job
    t0 = time.time()
    rng = np.random.default_rng([20261125, seed, ord(case)])
    xs, ts, us = draw(case, rng, M)
    nl = nulls(rng)
    kw = dict(alpha=ALPHA, delta=DELTA, null_inputs=nl, null_trials=100, seed=seed, decoder_name="p5-42-synth")
    rec: dict = {"case": case, "seed": seed}
    g = ft.calibrate(xs, ts, users=us, **kw)
    c = g.sheet.users["check"]
    rec.update(verdict=c["verdict"], p_user=c["p_user"], p_leak=c["p_leak"], k_real=c["real_commits"],
               nw_median=c["nw_commits_median"], np_median=c["np_commits_median"], ltt_commits=g.sheet.ltt_commits,
               config_id=g.config_id)
    if case == "D":
        rec["pooled_test"] = per_user_test(g, case, seed)
        try:
            ga = ft.calibrate(xs, ts, users=us, user_bound="all", **kw)
        except ValueError as e:
            rec["all"] = {"refused": str(e)[:300]}
        else:
            rec["all"] = {"threshold": ga.sheet.commit_threshold, "ltt_commits": ga.sheet.ltt_commits,
                          "test": per_user_test(ga, case, seed)}
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def rules(recs: list[dict]) -> dict:
    by = {c: [r for r in recs if r["case"] == c] for c in "ABCD"}
    a = by["A"]
    a_com = [r for r in a if r["k_real"] >= 1]
    a_fail = sum(r["verdict"] == "fail" for r in a_com)
    out = {"A": {"k_real_ge_1": len(a_com), "fail": a_fail,
                 "validity": len(a_com) >= 15, "rule": bool(a_com) and a_fail >= 0.9 * len(a_com)}}
    b = by["B"]
    out["B"] = {"pass": sum(r["verdict"] == "pass" for r in b), "verdicts": _count(b)}
    out["B"]["rule"] = out["B"]["pass"] >= 18
    c = by["C"]
    out["C"] = {"not_fail": sum(r["verdict"] != "fail" for r in c), "partial": sum(r["verdict"] == "partial" for r in c),
                "verdicts": _count(c)}
    out["C"]["rule"] = out["C"]["not_fail"] >= 18
    d = by["D"]
    exceed = sum(r["pooled_test"]["wrong_rate"][K - 1] > ALPHA for r in d)
    ok_all = sum(("test" in r["all"]) and max(r["all"]["test"]["wrong_rate"]) <= ALPHA + 0.01 for r in d)
    out["D"] = {"pooled_bad_user_above_alpha": exceed, "validity": exceed >= 10,
                "all_users_within": ok_all, "rule": ok_all >= 16,
                "all_refused": sum("refused" in r["all"] for r in d),
                "pooled_test_commits_median": float(np.median([sum(r["pooled_test"]["commits"]) for r in d])),
                "all_test_commits_median": float(np.median([sum(r["all"]["test"]["commits"]) for r in d
                                                            if "test" in r["all"]] or [0])),
                "verdicts": _count(d)}
    out["all_rules_pass"] = bool(out["A"]["validity"] and out["A"]["rule"] and out["B"]["rule"] and out["C"]["rule"]
                                 and out["D"]["validity"] and out["D"]["rule"])
    return out


def _count(rs: list[dict]) -> dict:
    v: dict = {}
    for r in rs:
        v[r["verdict"]] = v.get(r["verdict"], 0) + 1
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    jobs = [(c, s) for c in "ABCD" for s in SEEDS]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        recs = list(ex.map(run, jobs))
    res = {"plan": "plan.md (ad51861)", "alpha": ALPHA, "delta": DELTA, "users": K, "items_per_user": M,
           "test_items_per_user": M_TEST, "seconds": round(time.time() - t0, 1), "rules": rules(recs), "runs": recs}
    OUT.mkdir(exist_ok=True)
    (OUT / "synth.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res["rules"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
