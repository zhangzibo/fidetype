"""Paper 1, revision round 1: re-analysis of committed result files only.

No new decoding, no new harness run. Inputs are committed JSON files; the
output is ``papers/paper1/data/r1-derived.json``, which the paper cites for
every number that is not printed in an experiment's own tables.

What it computes
1. Error among commits (wrong commits / commits) for the whole-test policies
   of B2T '25 (M2-13 ``whole_test``), the ledger replay (M2-09), and sEMG
   (M6-07 ``trust.json``), with exact counts.
2. The M2-13 random CRC / LTT splits of B2T '25 (ours, published) and the G1
   async MEG splits, re-drawn with the same seeds and the same order of
   random draws as the original scripts. For each split it keeps the test
   wrong-commit rate, the commit rate, the error among commits, and the
   "pool risk": the wrong-commit rate of the chosen threshold on the whole
   test pool. In a random split of one fixed pool, the pool is the
   population, so the pool risk is the calibration-conditional risk
   R(lambda_hat) that LTT bounds with probability 1 - delta.
   The script asserts that the re-drawn means equal the committed means.

Run (repo root):  .venv/Scripts/python -I papers/paper1/analysis_r1.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
EXP = REPO / "experiments"
OUT = HERE / "data" / "r1-derived.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M13_DIR = EXP / "2026-11-11-m2-13-conformal"
G1_DIR = EXP / "2026-11-11-g1-async-meg-trust"
m13 = load_module("m213_r1", M13_DIR / "run.py")
M13_CFG = json.loads((M13_DIR / "config.json").read_text(encoding="utf-8"))
G1_CFG = json.loads((G1_DIR / "config.json").read_text(encoding="utf-8"))
ALPHA, DELTA = M13_CFG["alpha"], M13_CFG["delta"]
METHODS = ("old", "plugin", "crc", "crc_tune", "ltt")


def r(x, nd=4):
    return None if x is None or not math.isfinite(x) else round(float(x), nd)


def split_row(a, cal, tst, allidx) -> dict:
    out = {}
    for k, lam in m13.thresholds(a, cal).items():
        on = a.s[tst] >= lam
        wc = np.where(on, a.wc_c[tst], a.wc_f[tst])
        n_on = int(on.sum())
        pool_on = a.s[allidx] >= lam
        pool_wc = np.where(pool_on, a.wc_c[allidx], a.wc_f[allidx])
        out[k] = {"wc": float(wc.mean()), "commit": float(on.mean()), "n_commit": n_on,
                  "err_among": (float(a.wc_c[tst][on].sum()) / n_on) if n_on else math.nan,
                  "pool_risk": float(pool_wc.mean()), "lam": lam}
    return out


def summarise(rows: list[dict]) -> dict:
    res = {}
    for k in METHODS:
        wc = np.array([x[k]["wc"] for x in rows])
        cm = np.array([x[k]["commit"] for x in rows])
        ea = np.array([x[k]["err_among"] for x in rows])
        pr = np.array([x[k]["pool_risk"] for x in rows])
        res[k] = {
            "wrong_commit_mean": r(wc.mean()), "wrong_commit_p05": r(np.quantile(wc, 0.05)), "wrong_commit_p90": r(np.quantile(wc, 0.90)),
            "wrong_commit_p95": r(np.quantile(wc, 0.95)), "p_exceed_alpha": r(np.mean(wc > ALPHA + 1e-12), 3),
            "commit_rate_mean": r(cm.mean(), 3),
            "err_among_commits_ratio_of_means": r(wc.mean() / cm.mean(), 3) if cm.mean() > 0 else None,
            "err_among_commits_mean_over_splits": r(np.nanmean(ea), 3) if np.isfinite(ea).any() else None,
            "splits_with_commits": int(np.isfinite(ea).sum()),
            "pool_risk_mean": r(pr.mean()), "pool_risk_p90": r(np.quantile(pr, 0.90)),
            "pool_risk_share_above_alpha": r(np.mean(pr > ALPHA + 1e-12), 3),
        }
    return res


def m213_splits() -> dict:
    """Re-draw M2-13 splits in the original order (datasets, then n_cal)."""
    rng = np.random.default_rng(M13_CFG["seed"])
    committed = json.loads((M13_DIR / "results" / "splits.json").read_text(encoding="utf-8"))
    out = {}
    for name in M13_CFG["datasets"]:
        d = json.loads((M13_DIR / "results" / f"items-{name}.json").read_text(encoding="utf-8"))
        a = m13.Arr(d["test"])
        n = len(a.s)
        allidx = np.arange(n)
        out[name] = {}
        for n_cal in M13_CFG["n_cal"]:
            rows = []
            for _ in range(M13_CFG["reps"]):
                perm = rng.permutation(n)
                rows.append(split_row(a, perm[:n_cal], perm[n_cal:], allidx))
            s = summarise(rows)
            for k in METHODS:  # reproduce the committed means exactly
                ref = committed["datasets"][name]["splits"][str(n_cal)][k]["wrong_commit"]["mean"]
                assert abs(ref - s[k]["wrong_commit_mean"]) < 1e-4, (name, n_cal, k, ref, s[k])
            out[name][str(n_cal)] = s
    return out


def g1_splits() -> dict:
    """Re-draw the G1 async random splits (random_100 then random_408; grouped splits not needed)."""
    d = json.loads((G1_DIR / "results" / "items-meg-async.json").read_text(encoding="utf-8"))
    committed = json.loads((G1_DIR / "results" / "crc-splits-async.json").read_text(encoding="utf-8"))
    a = m13.Arr(d["test"])
    n = len(a.s)
    allidx = np.arange(n)
    rng = np.random.default_rng(G1_CFG["seed"])
    out = {}
    for n_cal in G1_CFG["n_cal"]:
        rows = []
        for _ in range(G1_CFG["reps"]):
            perm = rng.permutation(n)
            rows.append(split_row(a, perm[:n_cal], perm[n_cal:], allidx))
        s = summarise(rows)
        for k in METHODS:
            ref = committed["splits"][f"random_{n_cal}"][k]["wrong_commit"]["mean"]
            assert abs(ref - s[k]["wrong_commit_mean"]) < 1e-4, ("meg-async", n_cal, k, ref, s[k])
        out[str(n_cal)] = s
    return out


def whole_test() -> dict:
    sp = json.loads((M13_DIR / "results" / "splits.json").read_text(encoding="utf-8"))
    res = {}
    for name in ("b2t-ours", "b2t-published"):
        ds = sp["datasets"][name]
        n = ds["n_test"]
        rows = {}
        for pol, v in ds["whole_test"].items():
            nc, nw = round(v["commit_rate"] * n), round(v["wrong_commit"] * n)
            rows[pol] = {"n_test": n, "n_commit": nc, "n_wrong_commit": nw,
                         "wrong_commit": r(v["wrong_commit"]), "commit_rate": r(v["commit_rate"], 3),
                         "ewpm": r(v["ewpm"], 2),
                         "err_among_commits": r(nw / nc, 3) if nc else None}
        res[name] = rows
    # ledger replay counts (exact integers)
    led = json.loads((EXP / "2026-11-11-m2-09-provenance" / "results" / "summary.json").read_text(encoding="utf-8"))
    res["ledger_replay_b2t_ours"] = {}
    for g, v in led["per_gate"].items():
        nc = round(v["rate_commit"] * v["n_test"])
        res["ledger_replay_b2t_ours"][g] = {"n_commit": nc, "n_wrong_commit": v["n_wrong_commits_harness"],
                                             "err_among_commits": r(v["n_wrong_commits_harness"] / nc, 3)}
    # sEMG
    emg = json.loads((EXP / "2026-11-11-emg-toronto" / "results" / "trust.json").read_text(encoding="utf-8"))
    res["semg"] = {}
    for cond, c in emg["conditions"].items():
        res["semg"][cond] = {}
        for pol, v in c["policies"].items():
            n = v["n_test"]
            nc, nw = round(v["rate_commit"] * n), round(v["wrong_commit_rate"] * n)
            res["semg"][cond][pol] = {"n_test": n, "n_commit": nc, "n_wrong_commit": nw,
                                      "err_among_commits": r(nw / nc, 3) if nc else None,
                                      "ewpm": r(v["ewpm"], 2), "wrong_commit": r(v["wrong_commit_rate"])}
    # MEG async harness: 2 of 637 right at rank 1; trust commits 0
    return res


def main() -> None:
    out = {
        "_comment": "Generated by papers/paper1/analysis_r1.py from committed result files only. Do not edit by hand.",
        "_inputs": [
            "experiments/2026-11-11-m2-13-conformal/results/{items-*.json,splits.json}",
            "experiments/2026-11-11-g1-async-meg-trust/results/{items-meg-async.json,crc-splits-async.json}",
            "experiments/2026-11-11-m2-09-provenance/results/summary.json",
            "experiments/2026-11-11-emg-toronto/results/trust.json",
        ],
        "alpha": ALPHA, "delta": DELTA,
        "whole_test": whole_test(),
        "splits_m213": m213_splits(),
        "splits_meg_async": g1_splits(),
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
