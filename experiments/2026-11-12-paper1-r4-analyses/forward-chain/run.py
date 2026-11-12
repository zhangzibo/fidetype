"""R4 item 1: forward-chaining (time-ordered) deployment on Brain-to-Text '25.

Editor M1, stats M1. The R3 repeated splits permute trials inside each day,
so calibration and test items are exchangeable by construction. Here the
calibration data always come BEFORE the test data in time:

Days D_1 < ... < D_14 (post-implant days; 30-208 main-vocabulary trials each;
order inside a day = file order, the only time order in the pickle).
For every prefix j (fit on all trials of D_1..D_j; ``pipe.fit(F, F)``, the
fit-A recipe), item tables are built for every later day. Variants:

- **V1 (previous day):** test day D_k; fit D_1..D_{k-2}; calibrate on D_{k-1}.
- **V2 (all earlier non-fit days):** fit once on D_1..D_3; calibrate on
  D_4..D_{k-1} (all earlier days not used for fitting); test D_k (k >= 5).
- **V4 (two previous days):** fit D_1..D_{k-3}; calibrate on D_{k-2}, D_{k-1}.
- **V3 (session start):** fit D_1..D_{k-1}; calibrate on the first half
  (file order) of D_k; test on its second half.

Rules: plug-in (fit policy), CRC max, LTT max, CRC / LTT pure, joint LTT
(beta 0.10 / 0.20; ``common4.joint_ltt``). Guard on (paper configuration) and
guard off (plain threshold, the frozen configuration). Per test day: wrong-commit
rate with exact Clopper-Pearson 95 % CI, commit rate, error among commits,
eWPM; days above alpha. Also the staleness view: the V1 / V2 threshold applied
to every later day.

sEMG: no session-order version is possible (see results.md).

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/forward-chain/run.py --stage build --worker 0 --nworkers 3
  ... --stage analyze
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
FC = Q.CACHE4 / "forward"
FC.mkdir(exist_ok=True)
WHICH = ("ours", "published")
GUARDS = (1, 0)


def day_index(trials):
    days = sorted({int(t.post_implant_day) for t in trials})
    by = {d: sorted([i for i, t in enumerate(trials) if int(t.post_implant_day) == d], key=lambda i: trials[i].index)
          for d in days}
    return days, by


def stage_build(worker: int, nworkers: int) -> None:
    ctx, router, trials, items = Q.b2t_env(CONFIG["frame_T_snap_b2t"])
    days, by = day_index(trials)
    for j in range(len(days) - 1):
        if j % nworkers != worker:
            continue
        F = [i for d in days[: j + 1] for i in by[d]]
        for which in WHICH:
            for g in GUARDS:
                p = FC / f"b2t-{which}-g{g}-p{j:02d}.json"
                if p.exists():
                    continue
                t0 = time.time()
                n0 = router.new_count()
                sets = {str(d): [items[i] for i in by[d]] for d in days[j + 1:]}
                try:
                    res = Q.b2t_tables(ctx, which, [items[i] for i in F], sets, use_guard=bool(g))
                    res["ok"] = True
                except Exception as e:  # noqa: BLE001  (a 30-trial fit can fail)
                    res = {"ok": False, "error": repr(e)}
                res.update({"prefix": j, "fit_days": days[: j + 1], "n_fit": len(F), "which": which, "guard": g,
                            "day_idx": {str(d): by[d] for d in days[j + 1:]}, "new_decodes": router.new_count() - n0})
                C.dump(res, p)
                router.save()
                C.log(f"prefix {j} ({len(F)} fit) {which} g{g}: ok {res['ok']} T {res.get('T_used')} "
                      f"commit_p {res.get('fit_report', {}).get('policy_config', {}).get('commit_p') if res['ok'] else None} "
                      f"new decodes {res['new_decodes']} ({time.time() - t0:.0f}s)")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

RULES = ("plug-in", "CRC max", "LTT max", "CRC pure", "LTT pure", "joint LTT b0.10", "joint LTT b0.20")
MAIN = ("plug-in", "CRC max", "LTT max", "joint LTT b0.10", "joint LTT b0.20")


def concat(tabs: list[dict]) -> dict:
    a = [K.arr(t) for t in tabs]
    out = {k: np.concatenate([x[k] for x in a]) for k in a[0] if isinstance(a[0][k], np.ndarray)}
    out["lam_old"] = a[0]["lam_old"]
    out["c"], out["f"] = out["loss_c"], out["loss_f"]
    return out


def half(tab: dict, first: bool) -> dict:
    a = K.arr(tab)
    n = a["s"].size
    h = (n + 1) // 2
    idx = np.arange(h) if first else np.arange(h, n)
    return K.take(a, idx)


def row(te: dict, lam: float) -> dict:
    o = K.outcome(te, lam)
    k = Q.wrong_count(o)
    o["n_wrong_commit"] = k
    o["wrong_commit_cp95"] = Q.cp(k, o["n"])
    o["threshold"] = lam
    return o


def fold_rows(ca: dict, te: dict, plug: float) -> dict:
    lams = Q.rule_lambdas(ca, plug)
    return {r: row(te, lams[r]) for r in RULES}


def summarize(folds: list[dict]) -> dict:
    out = {}
    for r in RULES:
        rows = [f["rules"][r] for f in folds]
        n = sum(x["n"] for x in rows)
        k = sum(x["n_wrong_commit"] for x in rows)
        nc = sum(x["n_commit"] for x in rows)
        above = [f["test_day"] for f in folds if f["rules"][r]["wrong_commit"] > Q.ALPHA + 1e-12]
        sig_above = [f["test_day"] for f in folds if (f["rules"][r]["wrong_commit_cp95"][0] or 0) > Q.ALPHA]
        out[r] = {"n_days": len(rows), "days_above_alpha": len(above), "which_days_above_alpha": above,
                  "share_days_above_alpha": len(above) / max(1, len(rows)),
                  "share_days_above_alpha_cp95": Q.cp(len(above), len(rows)),
                  "days_cp_lower_above_alpha": sig_above,
                  "pooled_wrong_commit": k / n if n else None, "pooled_wrong_commit_cp95": Q.cp(k, n),
                  "pooled_commit_rate": nc / n if n else None,
                  "pooled_error_among_commits": (k / nc) if nc else None,
                  "mean_day_wrong_commit": float(np.mean([x["wrong_commit"] for x in rows])),
                  "max_day_wrong_commit": float(np.max([x["wrong_commit"] for x in rows])),
                  "mean_day_ewpm": float(np.mean([x["ewpm"] for x in rows])),
                  "days_no_commit": int(sum(x["n_commit"] == 0 for x in rows))}
    return out


def load(which, g, j):
    p = FC / f"b2t-{which}-g{g}-p{j:02d}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d if d.get("ok") else None


def stage_analyze() -> None:
    days = sorted(set(Q.DAYS_ALL))
    nd = len(days)
    res: dict = {"config": CONFIG, "days": days, "n_per_day": {str(d): Q.DAYS_ALL.count(d) for d in days}, "conditions": {}}
    for which in WHICH:
        for g in GUARDS:
            name = f"b2t-{which}/{'guard' if g else 'no guard'}"
            P = {j: load(which, g, j) for j in range(nd - 1)}
            fails = [j for j, v in P.items() if v is None]
            cres: dict = {"failed_prefixes": fails, "prefix_info": {
                str(j): {"n_fit": v["n_fit"], "T_used": v["T_used"], "T_fitted": v["T_fitted"],
                         "commit_p": v["fit_report"]["policy_config"]["commit_p"] if "policy_config" in v["fit_report"] else None}
                for j, v in P.items() if v is not None}, "variants": {}}
            # V1: fit D_1..D_{k-2}, cal D_{k-1}, test D_k  (0-based: prefix j = k-2, cal days[k-1], test days[k])
            for vname, spec in (("V1 previous day", "v1"), ("V4 two previous days", "v4"), ("V2 fixed fit D1-D3, all earlier days", "v2"),
                                ("V3 session start (first half of the test day)", "v3")):
                folds = []
                for k in range(nd):
                    if spec == "v1":
                        j = k - 2
                        if j < 0 or P.get(j) is None:
                            continue
                        cal_t = [P[j][str(days[k - 1])]]
                        te = K.arr(P[j][str(days[k])])
                        ca = concat(cal_t)
                    elif spec == "v4":
                        j = k - 3
                        if j < 0 or P.get(j) is None:
                            continue
                        ca = concat([P[j][str(days[k - 2])], P[j][str(days[k - 1])]])
                        te = K.arr(P[j][str(days[k])])
                    elif spec == "v2":
                        j = 2
                        if k < 4 or P.get(j) is None:
                            continue
                        ca = concat([P[j][str(days[i])] for i in range(3, k)])
                        te = K.arr(P[j][str(days[k])])
                    else:
                        j = k - 1
                        if j < 0 or P.get(j) is None:
                            continue
                        tab = P[j][str(days[k])]
                        ca, te = half(tab, True), half(tab, False)
                    plug = ca["lam_old"]
                    folds.append({"test_day": days[k], "prefix": j, "fit_days": days[: j + 1], "n_fit": P[j]["n_fit"],
                                  "n_cal": int(ca["s"].size), "n_test": int(te["s"].size), "rules": fold_rows(ca, te, plug)})
                cres["variants"][vname] = {"folds": folds, "summary": summarize(folds),
                                           "summary_fit_ge_2_days": summarize([f for f in folds if len(f["fit_days"]) >= 2])}
            # Staleness: V1-type threshold of prefix j (cal day D_{j+1}) applied to every later day D_{j+2..14}
            stale = []
            for j, v in P.items():
                if v is None or j + 2 >= nd:
                    continue
                ca = K.arr(v[str(days[j + 1])])
                lams = Q.rule_lambdas(ca, ca["lam_old"])
                for k in range(j + 2, nd):
                    te = K.arr(v[str(days[k])])
                    stale.append({"prefix": j, "test_day": days[k], "lag_days": k - (j + 1),
                                  "rules": {r: row(te, lams[r]) for r in ("LTT max", "CRC max", "joint LTT b0.10")}})
            cres["staleness"] = stale
            res["conditions"][name] = cres
            s1 = cres["variants"]["V1 previous day"]["summary"]
            C.log(f"{name}: V1 " + "; ".join(f"{r}: {s1[r]['days_above_alpha']}/{s1[r]['n_days']} days > a, pooled "
                                              f"{Q.fmt(s1[r]['pooled_wrong_commit'])}" for r in MAIN))
    C.dump(res, OUT / "forward_chain.json")
    write_tables(res)


def write_tables(res: dict) -> None:
    L = ["# Forward-chaining deployment on B2T '25: tables", "",
         "Calibration data always precede the test data in time. α = 0.05, δ = 0.1. Wrong-commit per test day with exact "
         "Clopper-Pearson 95 % CI; '>α' = days with a test rate above α. 'CP>α' = days whose CP lower bound is above α. "
         "Joint LTT: marginal ≤ α and error among commits ≤ β on the grid 0.05..1.00, Bonferroni.", "",
         "Trials per day: " + ", ".join(f"{d}: {n}" for d, n in res["n_per_day"].items()), ""]
    for name, c in res["conditions"].items():
        L += [f"## {name}", "", f"Failed prefix fits: {c['failed_prefixes'] or 'none'}.", ""]
        for vname, v in c["variants"].items():
            L += [f"### {vname}", "", "Summary over test days (pooled = all test trials of the variant):", "",
                  "| rule | days >α | share [CP95] | CP>α days | pooled wrong-commit [CP95] | pooled commit | pooled EAC | max day | mean day eWPM | no-commit days |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for r, s in v["summary"].items():
                L.append(f"| {r} | {s['days_above_alpha']}/{s['n_days']} {s['which_days_above_alpha']} | {s['share_days_above_alpha']:.2f} "
                         f"{Q.fci(s['share_days_above_alpha_cp95'], 2)} | {s['days_cp_lower_above_alpha']} | {Q.fmt(s['pooled_wrong_commit'])} "
                         f"{Q.fci(s['pooled_wrong_commit_cp95'])} | {Q.fmt(s['pooled_commit_rate'], 3)} | {Q.fmt(s['pooled_error_among_commits'], 3)} | "
                         f"{Q.fmt(s['max_day_wrong_commit'], 3)} | {Q.fmt(s['mean_day_ewpm'], 2)} | {s['days_no_commit']} |")
            s2 = v["summary_fit_ge_2_days"]
            L += ["", "Folds with ≥ 2 fit days only: " + "; ".join(
                f"{r} {s2[r]['days_above_alpha']}/{s2[r]['n_days']}" for r in MAIN if r in s2), "",
                  "Per test day (wrong-commit [CP95] / commit rate / EAC / eWPM):", "",
                  "| test day | fit days | n cal | n test | " + " | ".join(MAIN) + " |", "|---|---|---|---|" + "---|" * len(MAIN)]
            for f in v["folds"]:
                cells = []
                for r in MAIN:
                    o = f["rules"][r]
                    cells.append(f"{o['wrong_commit']:.3f} {Q.fci(o['wrong_commit_cp95'])} / {o['commit_rate']:.2f} / "
                                 f"{Q.fmt(o['error_among_commits'], 2)} / {o['ewpm']:.2f}")
                L.append(f"| {f['test_day']} | {len(f['fit_days'])} ({f['n_fit']}) | {f['n_cal']} | {f['n_test']} | " + " | ".join(cells) + " |")
            L.append("")
        st = c["staleness"]
        if st:
            L += ["### Staleness (threshold calibrated on day D_{j+1}, applied to later days)", "",
                  "| lag (days in sequence) | n pairs | LTT max mean wrong-commit | share >α | CRC max mean | share >α |", "|---|---|---|---|---|---|"]
            lags = sorted({x["lag_days"] for x in st})
            for lg in lags:
                xs = [x for x in st if x["lag_days"] == lg]
                lt = [x["rules"]["LTT max"]["wrong_commit"] for x in xs]
                cm = [x["rules"]["CRC max"]["wrong_commit"] for x in xs]
                L.append(f"| {lg} | {len(xs)} | {np.mean(lt):.4f} | {np.mean(np.array(lt) > Q.ALPHA):.2f} | {np.mean(cm):.4f} | "
                         f"{np.mean(np.array(cm) > Q.ALPHA):.2f} |")
            L.append("")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--worker", type=int, default=0)
    ap.add_argument("--nworkers", type=int, default=1)
    a = ap.parse_args()
    C.Log.path = OUT / f"run-{a.stage}{f'-w{a.worker}' if a.stage == 'build' else ''}.log"
    if a.stage == "build":
        stage_build(a.worker, a.nworkers)
    else:
        stage_analyze()
    C.log("done", a.stage)


if __name__ == "__main__":
    main()
