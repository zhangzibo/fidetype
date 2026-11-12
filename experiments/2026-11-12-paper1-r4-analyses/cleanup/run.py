"""R4 item 8: clean-up numbers (verification of reviewer statements, from committed files and cached tables).

Stats m1, m2, m6; editor M4.

1. MEG Tab. 1 CIs from the unified bootstrap (R3 unified-ci ci.json), and the
   CIs that the teaser figure uses (G1 harness, sentence bootstrap).
2. Exact Clopper-Pearson bounds for every zero / small count in the paper:
   one-sided 95 % upper, two-sided 95 % interval, rule of three.
3. Frame-temperature snapping: largest absolute and relative change per
   condition (R3 per_split.json; R4 split tables).
4. The comparator "the same fitted policy without commits": the same fit-A
   pipeline and policy with the commit threshold lambda = +inf (every trial
   takes the policy's non-commit path: offer / alternatives / retype). Per
   split: eWPM(rule) - eWPM(no commit); mean, Monte-Carlo SE, 5th-95th
   percentile over splits, share > 0; fixed splits A / B with a paired
   day-cluster bootstrap CI (unified seed, B 2000).
5. Always commit vs trust in all 9 user-model variants (R3 unified rerun):
   eWPM, paired difference trust - always commit with its CI, ranking.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/cleanup/run.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
UCI = Q.R3 / "unified-ci/results"


def meg_cis() -> dict:
    ci = json.loads((UCI / "ci.json").read_text(encoding="utf-8"))["table2_baselines"]["meg-async"]
    out = {"unified_two_way": {k: {"ewpm": ci["point"][k]["ewpm"], "ewpm_ci": ci["ci"]["policies"][k]["ewpm"]}
                               for k in ("trust", "never_commit", "gaze_only", "always_commit")},
           "printed_in_v3_tab1": {"trust": [3.02, 3.44], "gaze_only": [3.03, 3.31]}}
    g1 = Q.REPO / "experiments/2026-11-11-g1-async-meg-trust/results/harness-async.json"
    if g1.exists():
        g = json.loads(g1.read_text(encoding="utf-8"))
        bs = g["bootstrap"]["sentences"]["policies"]
        out["teaser_figure_source_G1_sentence_bootstrap"] = {k: {"ewpm": g["policies"][k]["ewpm"], "ewpm_ci": bs[k]["ewpm"]}
                                                             for k in ("commit", "trust") if k in bs}
    return out


def cp_bounds() -> dict:
    out = {}
    for k, n, what in CONFIG["counts"]:
        lo, hi = K.clopper_pearson(k, n)
        out[f"{k}/{n}"] = {"what": what, "k": k, "n": n, "cp95_one_sided_upper": K.upper_one_sided(k, n),
                           "cp95_two_sided": [lo, hi], "rule_of_three": (3.0 / n) if k == 0 else None}
    return out


def snapping() -> dict:
    ps = json.loads((Q.R3 / "repeated-splits/results/per_split.json").read_text(encoding="utf-8"))
    out = {}
    for cond, rows in ps.items():
        d = np.array([abs(r["T_used"] - r["T_fitted"]) for r in rows])
        rel = np.array([abs(r["T_used"] - r["T_fitted"]) / r["T_fitted"] for r in rows])
        out[f"R3 {cond}"] = {"R": len(rows), "max_abs": float(d.max()), "max_rel_pct": float(100 * rel.max()),
                             "T_fitted_range": [float(min(r["T_fitted"] for r in rows)), float(max(r["T_fitted"] for r in rows))]}
    for cond, guard in (("b2t-ours", 1), ("b2t-ours", 0), ("b2t-published", 0), ("emg-calib", 0), ("emg-xsession", 0), ("emg-xsubject", 0)):
        Rm = 200 if cond.startswith("b2t") else 50
        rows = Q.load_all(cond, Rm, guard)
        if not rows:
            continue
        rel = np.array([abs(r["T_used"] - r["T_fitted"]) / r["T_fitted"] for r in rows])
        out[f"R4 {cond} guard {guard}"] = {"R": len(rows), "max_abs": float(max(abs(r["T_used"] - r["T_fitted"]) for r in rows)),
                                           "max_rel_pct": float(100 * rel.max())}
    return out


def no_commit_gain() -> dict:
    out = {}
    rules = ("LTT max", "CRC max", "plug-in", "joint LTT b0.10")
    for cond in ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession"):
        for guard in (1, 0):
            Rm = 200 if cond.startswith("b2t") else 50
            allrows = Q.load_all(cond, Rm, guard)
            for tag, rr in ((f"R{len(allrows)}", allrows),) + ((("R50", allrows[:50]),) if len(allrows) > 50 else ()):
                d = {r: [] for r in rules}
                nce = []
                for sp in rr:
                    lam = Q.rule_lambdas(sp["cal"], sp["cal"]["lam_old"])
                    e0 = K.outcome(sp["test"], math.inf)["ewpm"]
                    nce.append(e0)
                    for r in rules:
                        d[r].append(K.outcome(sp["test"], lam[r])["ewpm"] - e0)
                res = {"no_commit_ewpm_mean": float(np.mean(nce))}
                for r, v in d.items():
                    v = np.array(v)
                    res[r] = {"mean": float(v.mean()), "mc_se": float(v.std(ddof=1) / math.sqrt(v.size)), "p05": float(np.quantile(v, 0.05)),
                              "p95": float(np.quantile(v, 0.95)), "share_pos": float(np.mean(v > 0)), "share_neg": float(np.mean(v < 0)), "R": int(v.size)}
                out[f"{cond}/{'guard' if guard else 'no guard'}/{tag}"] = res
    # check against the v3 proxy (beta = 0.05 selective controllers never commit)
    v3 = json.loads((Q.R3 / "v3-derived/results/v3_derived.json").read_text(encoding="utf-8"))
    out["check_v3"] = {c: {"v3 LTT max - no commit": v3[c]["LTT max-rule (clean) - no commit"]["mean"],
                           "r4 LTT max - no commit": out[f"{c}/guard/R50"]["LTT max"]["mean"]} for c in ("b2t-ours", "b2t-published")}
    # fixed splits: paired day-cluster bootstrap
    clean = K.R1 / "clean-drift/results"
    fx = {}
    for which in ("ours", "published"):
        for split, lab in (("alternate", "A"), ("chrono", "B")):
            it = json.loads((clean / f"items-{which}-{split}.json").read_text(encoding="utf-8"))
            ca, te = K.arr(it["items_cal"]), K.arr(it["items_test"])
            lam = Q.rule_lambdas(ca, te["lam_old"])
            arrs = {"no commit": C.item_arrays(it["items_test"], math.inf), **{r: C.item_arrays(it["items_test"], lam[r]) for r in rules}}
            cl = np.unique(it["days_test"], return_inverse=True)[1]
            bs = C.bootstrap(arrs, SimpleNamespace(cluster=cl, sent=None, scheme="cluster"), B=K.UNIFIED_B, seed=K.UNIFIED_SEED,
                             diffs=[(r, "no commit") for r in rules])
            pt = C.point(arrs)
            fx[f"b2t-{which}/split {lab}"] = {r: {"diff": pt[r]["ewpm"] - pt["no commit"]["ewpm"], "ci95": bs["diffs"][f"{r}-no commit"]["ewpm"],
                                                  "ewpm": pt[r]["ewpm"], "no_commit_ewpm": pt["no commit"]["ewpm"]} for r in rules}
    out["fixed_splits"] = fx
    return out


def rank_list(r) -> list:
    return list(r) if isinstance(r, (list, tuple)) else str(r).split(" > ")


def user_models() -> dict:
    u = json.loads((UCI / "rerun/user-model/results/user-model-emg-calib+emg-xsession+emg-xsubject+b2t-ours+b2t-published+meg-async.json")
                   .read_text(encoding="utf-8"))["conditions"]
    out = {}
    for cond, c in u.items():
        out[cond] = {}
        for var, v in c["variants"].items():
            p = v["point"]
            out[cond][var] = {"always_commit": p["always_commit"]["ewpm"], "trust": p["trust"]["ewpm"], "never_commit": p["never_commit"]["ewpm"],
                              "trust_minus_always_commit": p["trust"]["ewpm"] - p["always_commit"]["ewpm"],
                              "ci95": v["ci"]["diffs_ewpm"]["trust-always_commit"], "ranking": v["ranking_by_ewpm"],
                              "always_commit_fastest": rank_list(v["ranking_by_ewpm"])[0] == "always_commit",
                              "always_commit_faster_than_trust": rank_list(v["ranking_by_ewpm"]).index("always_commit") < rank_list(v["ranking_by_ewpm"]).index("trust")}
    return out


def main() -> None:
    res = {"config": CONFIG, "meg_tab1": meg_cis(), "cp_bounds": cp_bounds(), "temperature_snapping": snapping(),
           "no_commit_comparator": no_commit_gain(), "user_models_trust_vs_always_commit": user_models()}
    C.dump(res, OUT / "cleanup.json")
    write(res)


def write(res: dict) -> None:
    L = ["# Clean-up numbers: tables", "", "## 1. MEG Tab. 1 CIs", "", "| source | policy | eWPM | 95 % CI |", "|---|---|---|---|"]
    for src, d in res["meg_tab1"].items():
        for k, v in d.items():
            if isinstance(v, dict):
                L.append(f"| {src} | {k} | {v['ewpm']:.3f} | {Q.fci(v['ewpm_ci'], 3)} |")
            else:
                L.append(f"| {src} | {k} | — | {v} |")
    L += ["", "## 2. Exact Clopper-Pearson bounds", "", "| count | what | one-sided 95 % upper | two-sided 95 % | rule of three |", "|---|---|---|---|---|"]
    for k, v in res["cp_bounds"].items():
        L.append(f"| {k} | {v['what']} | {v['cp95_one_sided_upper']:.4f} | [{v['cp95_two_sided'][0]:.4f}, {v['cp95_two_sided'][1]:.4f}] | "
                 f"{Q.fmt(v['rule_of_three'], 4)} |")
    L += ["", "## 3. Frame-temperature snapping", "", "| condition | R | max |ΔT| | max relative change (%) |", "|---|---|---|---|"]
    for k, v in res["temperature_snapping"].items():
        L.append(f"| {k} | {v['R']} | {v['max_abs']:.4f} | {v['max_rel_pct']:.3f} |")
    L += ["", "## 4. Comparator: the same fitted policy without commits (λ = +∞)", "",
          "Definition: the same fit-A pipeline and policy with the commit threshold set to +∞, so no trial is committed and every trial takes "
          "the policy's non-commit path (offer the n-best / alternatives, else retype). Gain = eWPM(rule) − eWPM(no commit), paired by split.", "",
          "| condition / guard / R | no-commit eWPM | rule | gain mean (MC SE) | p05–p95 over splits | share > 0 / < 0 |", "|---|---|---|---|---|---|"]
    for key, v in res["no_commit_comparator"].items():
        if key in ("check_v3", "fixed_splits"):
            continue
        for r in ("LTT max", "CRC max", "plug-in", "joint LTT b0.10"):
            d = v[r]
            L.append(f"| {key} | {v['no_commit_ewpm_mean']:.2f} | {r} | {d['mean']:+.3f} ({d['mc_se']:.3f}) | {d['p05']:+.3f} – {d['p95']:+.3f} | "
                     f"{d['share_pos']:.2f} / {d['share_neg']:.2f} |")
    L += ["", f"Check against v3 (β = 0.05 selective controllers as the no-commit row): {json.dumps(res['no_commit_comparator']['check_v3'])}", "",
          "Fixed splits (paired day-cluster bootstrap, unified seed):", "", "| split | rule | eWPM | no commit | gain [95 % CI] |", "|---|---|---|---|---|"]
    for key, v in res["no_commit_comparator"]["fixed_splits"].items():
        for r, d in v.items():
            L.append(f"| {key} | {r} | {d['ewpm']:.2f} | {d['no_commit_ewpm']:.2f} | {d['diff']:+.3f} {Q.fci(d['ci95'], 3)} |")
    L += ["", "## 5. Trust vs always commit in the 9 user-model variants", "",
          "| condition | variant | always commit | trust | trust − always commit [CI] | fastest | always commit faster than trust |", "|---|---|---|---|---|---|---|"]
    for cond, vv in res["user_models_trust_vs_always_commit"].items():
        for var, d in vv.items():
            L.append(f"| {cond} | {var} | {d['always_commit']:.2f} | {d['trust']:.2f} | {d['trust_minus_always_commit']:+.2f} {Q.fci(d['ci95'], 2)} | "
                     f"{rank_list(d['ranking'])[0]} | {'yes' if d['always_commit_faster_than_trust'] else 'no'} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
