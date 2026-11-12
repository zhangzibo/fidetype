"""R4 item 2: per-day (per-session) risk under the primary rule (LTT max).

Stats M2; editor M5(c). LTT bounds the risk of the calibration distribution,
here the mixture of the 14 B2T days (or of 19 sEMG participants). This script
gives the per-day test wrong-commit rate under every rule over the repeated
splits (R = 50, the R3 splits; and R = 200), the fixed splits A / B (one
realisation, exact Clopper-Pearson CIs) and a group-conditional (Mondrian)
LTT per day (calibration items of that day only) as the named remedy.

Per day and rule: mean of the per-split day rate, pooled rate (sum of wrong
commits / sum of test items over splits; splits share trials, so this is a
mean, not an independent sample), 5th / 95th percentile, share of splits with
a day rate above alpha, mean number of test trials. sEMG: per test participant.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/per-day/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
RULES = ("LTT max", "CRC max", "plug-in", "LTT pure", "CRC pure", "joint LTT b0.10", "joint LTT b0.20")


def per_group(rows: list[dict], guard_rules=RULES) -> dict:
    acc: dict = {}
    mon: dict = {}
    for sp in rows:
        ca, te = sp["cal"], sp["test"]
        lams = Q.rule_lambdas(ca, ca["lam_old"])
        g = sp["test_group"]
        for d in np.unique(g):
            idx = np.where(g == d)[0]
            for r in guard_rules:
                o = K.outcome(te, lams[r], idx)
                acc.setdefault(r, {}).setdefault(str(d), []).append((o["wrong_commit"], o["n"], Q.wrong_count(o), o["n_commit"],
                                                                     o["commit_rate"], o["ewpm"]))
            # Mondrian LTT (max rule) on this day's calibration items only (B2T)
            if "cal_group" in sp:
                ci = np.where(sp["cal_group"] == d)[0]
                cad = K.take(ca, ci)
                lt = K.ltt(cad)
                lam = max(ca["lam_old"], lt.threshold)
                o = K.outcome(te, lam, idx)
                mon.setdefault(str(d), []).append((o["wrong_commit"], o["n"], Q.wrong_count(o), o["n_commit"], int(ci.size),
                                                   bool(np.isfinite(lt.threshold))))
    out = {}
    for r, dd in acc.items():
        out[r] = {}
        for d, v in dd.items():
            v = np.array(v, float)
            out[r][d] = {"mean": float(v[:, 0].mean()), "pooled": float(v[:, 2].sum() / v[:, 1].sum()),
                         "p05": float(np.quantile(v[:, 0], 0.05)), "p95": float(np.quantile(v[:, 0], 0.95)),
                         "share_gt_alpha": float(np.mean(v[:, 0] > Q.ALPHA + 1e-12)), "n_test_mean": float(v[:, 1].mean()),
                         "commit_rate_mean": float(v[:, 4].mean()),
                         "pooled_eac": float(v[:, 2].sum() / v[:, 3].sum()) if v[:, 3].sum() else None,
                         "ewpm_mean": float(v[:, 5].mean()), "R": int(v.shape[0])}
    res = {"rules": out}
    if mon:
        res["mondrian_ltt_max"] = {}
        for d, v in mon.items():
            v = np.array(v, float)
            res["mondrian_ltt_max"][d] = {"mean": float(v[:, 0].mean()), "pooled": float(v[:, 2].sum() / v[:, 1].sum()),
                                          "share_gt_alpha": float(np.mean(v[:, 0] > Q.ALPHA + 1e-12)),
                                          "commit_rate_mean": float(v[:, 3].sum() / v[:, 1].sum()),
                                          "n_cal_mean": float(v[:, 4].mean()), "share_ltt_feasible": float(v[:, 5].mean())}
    return res


def fixed_splits() -> dict:
    out = {}
    clean = Q.K.R1 / "clean-drift" / "results"
    for which in ("ours", "published"):
        for split, lab in (("alternate", "A"), ("chrono", "B")):
            items = json.loads((clean / f"items-{which}-{split}.json").read_text(encoding="utf-8"))
            ca, te = K.arr(items["items_cal"]), K.arr(items["items_test"])
            lams = Q.rule_lambdas(ca, te["lam_old"])
            days = np.asarray(items["days_test"])
            rows = {}
            for d in np.unique(days):
                idx = np.where(days == d)[0]
                rows[str(int(d))] = {}
                for r in ("LTT max", "CRC max", "plug-in", "joint LTT b0.10"):
                    o = K.outcome(te, lams[r], idx)
                    k = Q.wrong_count(o)
                    rows[str(int(d))][r] = {"wrong_commit": o["wrong_commit"], "n": o["n"], "n_wrong": k, "cp95": Q.cp(k, o["n"]),
                                            "commit_rate": o["commit_rate"], "n_commit": o["n_commit"]}
            out[f"b2t-{which}/split {lab}"] = rows
    return out


def main() -> None:
    res = {"config": CONFIG, "repeated": {}, "fixed": fixed_splits()}
    for cond in Q.CONDS:
        for R in CONFIG["R"]:
            if not cond.startswith("b2t") and R > 50:
                continue
            rows = Q.load_all(cond, R)
            if len(rows) < R:
                C.log(f"{cond}: only {len(rows)} of {R} splits")
            res["repeated"][f"{cond}/R{R}"] = {"R": len(rows), **per_group(rows)}
            lt = res["repeated"][f"{cond}/R{R}"]["rules"]["LTT max"]
            C.log(f"{cond} R{R}: LTT max per-group pooled: " + ", ".join(f"{d} {v['pooled']:.3f}" for d, v in lt.items()))
    C.dump(res, OUT / "per_day.json")
    write(res)


def write(res: dict) -> None:
    L = ["# Per-day (per-session) risk under the primary rule: tables", "",
         "Test wrong-commit per day (B2T) or per test participant (sEMG) over repeated splits. α = 0.05. 'pooled' = Σ wrong / Σ n over "
         "splits; 'mean' = mean of per-split day rates; '>α' = share of splits with a day rate above α. The guarantee of LTT (and CRC) is "
         "about the calibration distribution: the mixture of days (participants), not each day.", ""]
    for name, c in res["repeated"].items():
        lt, cm, pl, jt = (c["rules"][r] for r in ("LTT max", "CRC max", "plug-in", "joint LTT b0.10"))
        L += [f"## {name} (R = {c['R']})", "",
              "| group | n test (mean) | LTT max pooled | mean [p05, p95] | >α | commit | CRC max pooled | >α | plug-in pooled | joint LTT β=0.10 pooled | commit |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for d in lt:
            a = lt[d]
            L.append(f"| {d} | {a['n_test_mean']:.1f} | **{a['pooled']:.4f}** | {a['mean']:.4f} [{a['p05']:.3f}, {a['p95']:.3f}] | "
                     f"{a['share_gt_alpha']:.2f} | {a['commit_rate_mean']:.3f} | {cm[d]['pooled']:.4f} | {cm[d]['share_gt_alpha']:.2f} | "
                     f"{pl[d]['pooled']:.4f} | {jt[d]['pooled']:.4f} | {jt[d]['commit_rate_mean']:.3f} |")
        pooled = [v["pooled"] for v in lt.values()]
        L += ["", f"LTT max: groups with pooled rate > α: {sum(p > Q.ALPHA for p in pooled)} of {len(pooled)}; range "
                  f"{min(pooled):.4f}–{max(pooled):.4f}.", ""]
        if "mondrian_ltt_max" in c:
            L += ["Group-conditional (Mondrian) LTT max per day (calibration items of the day only):", "",
                  "| day | n cal (mean) | LTT feasible (share of splits) | pooled wrong-commit | commit rate | >α |", "|---|---|---|---|---|---|"]
            for d, v in c["mondrian_ltt_max"].items():
                L.append(f"| {d} | {v['n_cal_mean']:.1f} | {v['share_ltt_feasible']:.2f} | {v['pooled']:.4f} | {v['commit_rate_mean']:.3f} | "
                         f"{v['share_gt_alpha']:.2f} |")
            L.append("")
    L += ["## Fixed splits A and B (one realisation; exact CP 95 % CI per day)", ""]
    for name, rows in res["fixed"].items():
        L += [f"### {name}", "", "| day | n | LTT max wrong [CP95] | commits | CRC max wrong | plug-in wrong |", "|---|---|---|---|---|---|"]
        for d, v in rows.items():
            a = v["LTT max"]
            L.append(f"| {d} | {a['n']} | {a['n_wrong']} ({a['wrong_commit']:.3f}) {Q.fci(a['cp95'])} | {a['n_commit']} | "
                     f"{v['CRC max']['n_wrong']} ({v['CRC max']['wrong_commit']:.3f}) | {v['plug-in']['n_wrong']} ({v['plug-in']['wrong_commit']:.3f}) |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
