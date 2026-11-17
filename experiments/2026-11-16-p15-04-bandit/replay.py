"""P15-04 replay (plan: plan.md). CPU only, no decoding: reads the P5-02 per-item files (read only).

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p15-04-bandit/replay.py
Per-run outputs: C:/Users/zhang/bci-data/derived/p15-04-bandit/ only. Repo: results/summary.json (aggregates).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.trust.bandit_risk import BanditCommitRiskControl, NaiveShownOnlyControl  # noqa: E402
from fidetype.trust.online_risk import OnlineCommitRiskControl  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

SRC = Path("C:/Users/zhang/bci-data/derived/p5-02-precision")  # read only
OWN = Path("C:/Users/zhang/bci-data/derived/p15-04-bandit")
assert OWN.name == "p15-04-bandit"
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOGF = OWN / "replay.log"

ALPHA, DELTA, ETA, LAM0 = 0.05, 0.1, 0.05, 0.3
ALPHA_P = 0.5
N_SEEDS, N_PERM = 200, 200
BIAS_LAMS = (0.15, 0.20, 0.25)


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(name: str) -> tuple[np.ndarray, np.ndarray]:
    d = json.loads((SRC / f"items-{name}.json").read_text(encoding="utf-8"))
    s = np.array([x["p_top1"] if x["can_commit"] else -math.inf for x in d], dtype=np.float64)
    c = np.array([float(x["wrong"]) for x in d])
    return s, c


def notice_coins(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(50000 + seed).uniform(size=n)


def seen_c(c: float, commit: bool, u: float, q: float) -> float:
    """What the controller sees for a commit: a wrong commit is noticed with probability q."""
    return c if (not commit or c == 0 or u < q) else 0.0


def run_aci(s, c, q, u):
    o = OnlineCommitRiskControl(alpha=ALPHA, method="aci", eta=ETA, lam_init=LAM0)
    com = np.zeros(len(s), bool)
    for t, (si, ci) in enumerate(zip(s, c)):
        tk = o.decide(si)
        com[t] = tk.commit
        o.observe(tk, seen_c(ci, tk.commit, u[t], q) if tk.commit else None)
    r = o.report()
    return com, r["mean_loss"], r["certificate"]


def run_window(s, c, full: bool):
    o = OnlineCommitRiskControl(alpha=ALPHA, method="window", window=200)
    o.fit([LAM0 + 1e-9], [0.0])  # tiny warm start; the window fills online
    com = np.zeros(len(s), bool)
    for t, (si, ci) in enumerate(zip(s, c)):
        tk = o.decide(si)
        com[t] = tk.commit
        o.observe(tk, ci if (full or tk.commit) else None)
    return com


def run_bandit(s, c, q, u, seed, **kw):
    rc = BanditCommitRiskControl(alpha=kw.pop("alpha", ALPHA), delta=DELTA, eta=ETA, lam_init=LAM0, seed=seed, **kw)
    com = np.zeros(len(s), bool)
    for t, (si, ci) in enumerate(zip(s, c)):
        tk = rc.decide(si)
        com[t] = tk.commit
        if tk.commit:
            rc.observe(tk, seen_c(ci, True, u[t], q))
        elif tk.shown:
            rc.observe(tk, ci)
        else:
            rc.observe(tk, None)
    return com, rc


def true_counts(s, c, grid):
    return (c[:, None] * (s[:, None] >= grid[None, :])).sum(axis=0)


def rate_row(com, c, n):
    k = int((com & (c > 0)).sum())
    return {"commits": int(com.sum()), "wrong": k, "rate": k / n, "cp95": clopper_pearson(k, n, 0.95)}


def time_order(name, s, c) -> dict:
    n = len(s)
    grid = np.asarray(BanditCommitRiskControl().grid)
    tc = true_counts(s, c, grid)
    out: dict = {"n": n, "top1_right": int((c == 0).sum()), "can_commit": int(np.isfinite(s).sum())}
    for q in (1.0, 0.9):
        u = notice_coins(n, 0)
        com, obs, cert = run_aci(s, c, q, u)
        row = rate_row(com, c, n)
        row.update(observed_rate=obs, certificate=cert, r1=bool(obs <= cert + 1e-12))
        out[f"A_aci_q{q}"] = row
    out["C_window_full"] = rate_row(run_window(s, c, True), c, n)
    out["D_window_naive"] = rate_row(run_window(s, c, False), c, n)
    for arm, kw in (("B05", dict(explore=0.05)), ("B20", dict(explore=0.20)), ("E_max", dict(explore=0.20, rule="max")),
                    ("P_bandit", dict(explore=0.05, target="precision", alpha=ALPHA_P))):
        for q in ((1.0, 0.9) if arm in ("B05", "B20") else (1.0,)):
            rates, obs_r, certs, r1, cov_fail, commits, expl, same_as_a = [], [], [], [], 0, [], [], 0
            bias_n = {lam: [] for lam in BIAS_LAMS}
            bias_i = {lam: [] for lam in BIAS_LAMS}
            com_a = run_aci(s, c, q, notice_coins(n, 0))[0]
            silent_gap = []
            for seed in range(N_SEEDS):
                u = notice_coins(n, seed)
                com, rc = run_bandit(s, c, q, u, seed, **dict(kw))
                rep = rc.report()
                wrong = int((com & (c > 0)).sum())
                if kw.get("target") == "precision":
                    rates.append(wrong / max(com.sum(), 1))
                else:
                    rates.append(wrong / n)
                obs_r.append(rep["realised"])
                certs.append(rep["certificate"])
                ok = (math.isnan(rep["certificate"]) and rep["n_commits"] == 0) or rep["realised"] <= rep["certificate"] + 1e-12
                r1.append(bool(ok))
                commits.append(int(com.sum()))
                expl.append(rep["n_explore"])
                if q == 1.0 and np.any(tc > np.asarray(rep["audit"]["upper_wrong"]) + 1e-9):
                    cov_fail += 1
                if arm == "B05" and q == 1.0:
                    same_as_a += bool(np.array_equal(com, com_a))
                if q < 1.0:
                    silent_gap.append(rates[-1] - rep["realised"])
                if q == 1.0:
                    a = rep["audit"]
                    for lam in BIAS_LAMS:
                        k = int(round(lam * 100))
                        m = s >= lam
                        tru = float(c[m].mean())
                        nv = a["naive_precision_error"][k]
                        if not (isinstance(nv, float) and math.isnan(nv)):
                            bias_n[lam].append(nv - tru)
                        bias_i[lam].append(a["ipw_wrong"][k] / a["n_at"][k] - tru)
            med = int(np.argsort(rates)[len(rates) // 2])
            row = {
                "true_rate_median": float(np.median(rates)), "true_rate_min": float(min(rates)),
                "true_rate_max": float(max(rates)), "observed_rate_median": float(np.nanmedian(obs_r)),
                "certificate_median": float(np.nanmedian(certs)) if not all(map(math.isnan, certs)) else math.nan,
                "r1_all": all(r1), "commits_median": float(np.median(commits)), "commits_max": int(max(commits)),
                "explored_median": float(np.median(expl)),
            }
            if kw.get("target") != "precision":
                k = int(round(rates[med] * n))
                row["median_seed_cp95"] = clopper_pearson(k, n, 0.95)
            if q == 1.0:
                row["audit_violation_frac"] = cov_fail / N_SEEDS
                row["bias_naive"] = {str(l): (float(np.mean(v)) if v else math.nan) for l, v in bias_n.items()}
                row["bias_ipw"] = {str(l): float(np.mean(v)) for l, v in bias_i.items()}
                row["bias_naive_n"] = {str(l): len(v) for l, v in bias_n.items()}
            if arm == "B05" and q == 1.0:
                row["same_commits_as_A_frac"] = same_as_a / N_SEEDS
            if q < 1.0:
                row["silent_gap_min"] = float(min(silent_gap))
                row["silent_gap_mean"] = float(np.mean(silent_gap))
            out[f"{arm}_q{q}"] = row
            log(name, arm, q, json.dumps({k: row[k] for k in ("true_rate_median", "commits_median", "r1_all")}))
    nv = NaiveShownOnlyControl(alpha=ALPHA_P, target="precision", lam_init=LAM0)
    com = np.array([nv.step(si, ci) for si, ci in zip(s, c)])
    out["P_naive"] = {"commits": int(com.sum()), "wrong": int((com & (c > 0)).sum()),
                      "error_among_commits": float((com & (c > 0)).sum() / max(com.sum(), 1)),
                      "cp95": clopper_pearson(int((com & (c > 0)).sum()), int(com.sum()), 0.95) if com.sum() else None}
    return out


def random_orders(name, s, c) -> dict:
    n = len(s)
    res: dict = {k: [] for k in ("A", "B05", "D", "P_bandit", "P_naive")}
    ones = np.zeros(n)
    for i in range(N_PERM):
        p = np.random.default_rng(10000 + i).permutation(n)
        sp, cp_ = s[p], c[p]
        res["A"].append(rate_row(run_aci(sp, cp_, 1.0, ones)[0], cp_, n)["rate"])
        res["B05"].append(rate_row(run_bandit(sp, cp_, 1.0, ones, i, explore=0.05)[0], cp_, n)["rate"])
        res["D"].append(rate_row(run_window(sp, cp_, False), cp_, n)["rate"])
        com = run_bandit(sp, cp_, 1.0, ones, i, explore=0.05, target="precision", alpha=ALPHA_P)[0]
        res["P_bandit"].append(float((com & (cp_ > 0)).sum() / com.sum()) if com.sum() else math.nan)
        nv = NaiveShownOnlyControl(alpha=ALPHA_P, target="precision", lam_init=LAM0)
        com = np.array([nv.step(si, ci) for si, ci in zip(sp, cp_)])
        res["P_naive"].append(float((com & (cp_ > 0)).sum() / com.sum()) if com.sum() else math.nan)
    out = {}
    for k, v in res.items():
        a = np.array(v, dtype=float)
        lim = ALPHA_P if k.startswith("P_") else ALPHA
        f = a[~np.isnan(a)]
        out[k] = {"median": float(np.median(f)) if f.size else math.nan, "p90": float(np.quantile(f, 0.9)) if f.size else math.nan,
                  "frac_above_limit": float((f > lim).mean()) if f.size else math.nan, "n_with_commits": int(f.size)}
    np.savez_compressed(OWN / f"random-orders-{name}.npz", **{k: np.array(v, dtype=float) for k, v in res.items()})
    return out


def main() -> None:
    t0 = time.time()
    summary = {"plan": "experiments/2026-11-16-p15-04-bandit/plan.md", "alpha": ALPHA, "delta": DELTA, "eta": ETA,
               "lam_init": LAM0, "alpha_precision": ALPHA_P, "n_seeds": N_SEEDS, "n_perm": N_PERM, "sets": {}}
    for name in sys.argv[1:] or ["t12", "t15"]:
        s, c = load(name)
        log(name, "items", len(s))
        summary["sets"][name] = {"time_order": time_order(name, s, c), "random_orders": random_orders(name, s, c)}
        log(name, "done", round(time.time() - t0, 1), "s")
    summary["runtime_s"] = round(time.time() - t0, 1)
    txt = json.dumps(summary, indent=1, default=float)
    (OUT / "summary.json").write_text(txt, encoding="utf-8")
    (OWN / "summary.json").write_text(txt, encoding="utf-8")
    log("all done", summary["runtime_s"])


if __name__ == "__main__":
    main()
