"""P15-01 tables: pre-registered criteria S1-S6 and descriptive D1-D3 from results/arms/*.json (aggregates only).

Runs on the repo .venv (no torch needed):  .venv/Scripts/python.exe -I experiments/2026-11-16-f1-e2-selfimprove-pilot/tables.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = Path(os.environ.get("F1E2_RES", str(HERE / "results")))  # override: the P15-02 gated re-run
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
ALPHA, DELTA = CFG["loop"]["alpha"], CFG["loop"]["delta"]
GUARDED = ("frozen", "feedback-p0.5", "feedback-p0.9", "feedback-p1.0", "oracle", "selftrain", "shuffled-labels")
ORDER = GUARDED + ("feedback-p0.9-naive",)


def cp(k: int, n: int, level: float = 0.95) -> list:
    from scipy.stats import beta

    a = 1 - level
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


def per_c(days, idx=None):
    idx = range(len(days)) if idx is None else idx
    e = sum(days[i]["ph_ed_c"] for i in idx)
    n = sum(days[i]["ph_n_c"] for i in idx)
    return e / max(1, n)


def boot_diff(da, db, B: int, seed: int) -> list:
    rng = np.random.default_rng(seed)
    m = len(da)
    out = []
    for _ in range(B):
        idx = rng.integers(0, m, m)
        out.append(per_c(da, idx) - per_c(db, idx))
    return [float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))]


def f(x, nd=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main() -> None:
    arms = {}
    for a in ORDER:
        p = RES / "arms" / f"{a}.json"
        if p.exists():
            arms[a] = json.loads(p.read_text(encoding="utf-8"))
    bs = CFG["bootstrap"]
    rows, crit = [], {}
    for a, r in arms.items():
        t = r["totals"]
        days = r["days"]
        day_risk_c = [d["wrong_commits_c"] / max(1, d["n_phase_c"]) for d in days]
        nul = r["null"]
        n_null = nul["n_uniform"] + nul["n_shuffled"]
        rows.append({
            "arm": a, "per_c": r["per_phase_c"], "per_all": r["per_all"], "wer": r["wer_all"],
            "top1_exact": t["top1_right"] / t["n"], "offer_hit": t["offer_hit"] / t["n"],
            "n": t["n"], "commits": t["commits"], "wrong": int(t["wrong_commits"]), "observed_wrong": int(t["observed_wrong"]),
            "silent": t["silent"], "true_rate": r["true_wrong_commit_rate"], "cp95": r["true_wrong_commit_cp95"],
            "obs_mean_c": r["observed_mean_loss_c"], "certificate": r["aci"].get("certificate"),
            "alarms": r["n_alarms"], "feasible_days": r["n_feasible_days"], "days": r["n_days"],
            "days_over_alpha": int(sum(x > ALPHA for x in day_risk_c)),
            "null_commits": nul["uniform"] + nul["shuffled"], "n_null": n_null,
            "labels": t["labels"], "wrong_labels": t["wrong_labels"], "ewpm": r["ewpm"],
        })
    R = {r["arm"]: r for r in rows}
    # S1-S3 per guarded arm
    for a in GUARDED:
        if a not in R:
            continue
        r = R[a]
        vac = r["commits"] < 10
        crit.setdefault("S1", {})[a] = {"value": r["true_rate"], "pass": r["true_rate"] <= ALPHA, "vacuous": vac}
        share = r["days_over_alpha"] / max(1, r["days"])
        crit.setdefault("S2", {})[a] = {"value": share, "pass": share <= DELTA, "vacuous": vac}
        ok3 = r["obs_mean_c"] is None or r["certificate"] is None or r["obs_mean_c"] <= r["certificate"] + 1e-12
        crit.setdefault("S3", {})[a] = {"observed": r["obs_mean_c"], "certificate": r["certificate"], "pass": ok3}
    for a in R:
        r = R[a]
        crit.setdefault("S5", {})[a] = {"null_commits": r["null_commits"], "n_null": r["n_null"],
                                       "pass": r["n_null"] == 0 or r["null_commits"] <= 0.05 * r["n_null"],
                                       "target_zero": r["null_commits"] == 0}
    if "feedback-p0.9" in arms and "frozen" in arms:
        da, db = arms["feedback-p0.9"]["days"], arms["frozen"]["days"]
        d = per_c(da) - per_c(db)
        ci = boot_diff(da, db, bs["B"], bs["seed"])
        crit["S4"] = {"diff": d, "ci95": ci, "pass": d <= -0.03 and ci[1] < 0}
    if "shuffled-labels" in arms and "frozen" in arms:
        d = per_c(arms["shuffled-labels"]["days"]) - per_c(arms["frozen"]["days"])
        crit["S6"] = {"diff": d, "pass": d > -0.01 and crit.get("S1", {}).get("shuffled-labels", {}).get("pass", False)}
    desc = {}
    if "frozen" in arms:
        fz = arms["frozen"]["days"]
        for a in ("selftrain", "feedback-p0.5", "feedback-p0.9", "feedback-p1.0", "oracle", "shuffled-labels"):
            if a in arms:
                dd = [per_c([x]) - per_c([y]) for x, y in zip(arms[a]["days"], fz)]
                slope = float(np.polyfit(np.arange(len(dd)), dd, 1)[0]) if len(dd) > 1 else None
                desc[f"{a}-minus-frozen"] = {"mean_day_diff": float(np.mean(dd)), "slope_per_day": slope,
                                             "ci95": boot_diff(arms[a]["days"], fz, bs["B"], bs["seed"]),
                                             "first4": float(np.mean(dd[:4])), "last4": float(np.mean(dd[-4:]))}
    if "oracle" in arms:
        for a in ("feedback-p0.5", "feedback-p0.9", "feedback-p1.0"):
            if a in arms:
                desc[f"{a}-minus-oracle"] = per_c(arms[a]["days"]) - per_c(arms["oracle"]["days"])
    summary = {"alpha": ALPHA, "delta": DELTA, "rows": rows, "criteria": crit, "descriptive": desc}
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")

    md = ["# P15-01 tables (generated by tables.py; aggregates only)", "",
          "## Per arm (16 replay days)", "",
          "| arm | PER phase C | PER all | WER | top-1 exact | offer hit | commits | wrong (true) | observed wrong | silent | true wrong-commit rate [CP95] | ACI: observed mean / certificate | alarms | feasible days | null commits | labels (wrong) | eWPM |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['arm']} | {f(r['per_c'])} | {f(r['per_all'])} | {f(r['wer'])} | {f(r['top1_exact'])} | "
                  f"{f(r['offer_hit'])} | {r['commits']} | {r['wrong']} | {r['observed_wrong']} | {r['silent']} | "
                  f"{f(r['true_rate'])} [{f(r['cp95'][0])}, {f(r['cp95'][1])}] | {f(r['obs_mean_c'])} / {f(r['certificate'])} | "
                  f"{r['alarms']} | {r['feasible_days']}/{r['days']} | {r['null_commits']}/{r['n_null']} | "
                  f"{r['labels']} ({r['wrong_labels']}) | {f(r['ewpm'], 2)} |")
    md += ["", "## Pre-registered criteria", "", "| id | arm | value | pass |", "|---|---|---|---|"]
    for k in ("S1", "S2", "S3", "S5"):
        for a, v in crit.get(k, {}).items():
            val = v.get("value", v.get("observed", v.get("null_commits")))
            extra = " (vacuous: < 10 commits)" if v.get("vacuous") else ""
            md.append(f"| {k} | {a} | {f(val) if not isinstance(val, int) else val} | {'yes' if v['pass'] else 'NO'}{extra} |")
    for k in ("S4", "S6"):
        if k in crit:
            v = crit[k]
            md.append(f"| {k} | {'feedback-p0.9 - frozen' if k == 'S4' else 'shuffled-labels - frozen'} | "
                      f"{f(v['diff'])}{(' CI95 [' + f(v['ci95'][0]) + ', ' + f(v['ci95'][1]) + ']') if 'ci95' in v else ''} | "
                      f"{'yes' if v['pass'] else 'NO'} |")
    md += ["", "## Descriptive (PER phase C, arm minus frozen, per day)", "",
           "| comparison | mean day diff | CI95 (pooled, day bootstrap) | first 4 days | last 4 days | slope per day |",
           "|---|---|---|---|---|---|"]
    for k, v in desc.items():
        if isinstance(v, dict):
            md.append(f"| {k} | {f(v['mean_day_diff'])} | [{f(v['ci95'][0])}, {f(v['ci95'][1])}] | {f(v['first4'])} | "
                      f"{f(v['last4'])} | {f(v['slope_per_day'], 5)} |")
        else:
            md.append(f"| {k} | {f(v)} | | | | |")
    md += ["", "## PER phase C per replay day", ""]
    names = [a for a in ORDER if a in arms]
    md.append("| day | " + " | ".join(names) + " |")
    md.append("|---" * (len(names) + 1) + "|")
    nd = max(len(arms[a]["days"]) for a in names) if names else 0
    for i in range(nd):
        cells = []
        for a in names:
            dd = arms[a]["days"]
            cells.append(f(per_c([dd[i]]), 3) + (f" ({dd[i]['commits']}c)" if dd[i]["commits"] else "") if i < len(dd) else "-")
        md.append(f"| {i + 1} | " + " | ".join(cells) + " |")
    (RES / "tables.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
