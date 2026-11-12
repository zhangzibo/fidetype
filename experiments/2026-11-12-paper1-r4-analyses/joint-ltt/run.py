"""R4 item 4: a joint rule with a valid guarantee (joint LTT).

Stats M3; editor m11. The R3 joint rule max(lambda_SGR, lambda_CRC max) has no
selective guarantee, because the error among commits is not monotone in
lambda. Joint LTT tests, for each lambda on a grid fixed in advance,

  H0(lambda): R_marg(lambda) > alpha  OR  R_sel(lambda) > beta,

with p(lambda) = max(p_marg, p_sel); p_marg = P(Bin(n, alpha) <= n R_hat(lambda))
(0/1 losses), p_sel = P(Bin(n_lambda, beta) <= k_lambda) conditional on the
n_lambda calibration commits (1 if no commit). Bonferroni over the grid gives
FWER <= delta for the union null, so with probability >= 1 - delta both risks
of every rejected lambda are within target (i.i.d. calibration items). The
rule takes the smallest rejected lambda (most commits). Grid 0.05..1.00 step
0.05 (20 points, = LTT-sel grid, fixed before R3); sensitivity: step 0.01.
No max rule: raising lambda keeps the marginal bound but not the selective one.

Conditions: B2T ours / published, sEMG calib / xsession / xsubject; repeated
splits (guard on: R = 50 and 200 for B2T; guard off = plain threshold, the
frozen configuration: R = 200 / 50); fixed splits A / B (B2T), fixed sEMG
tables and the MEG clean split.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/joint-ltt/run.py
"""

from __future__ import annotations

import json
import math
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
GRIDS = (("g05", Q.GRID05), ("g01", Q.GRID01))


def lambdas(ca: dict) -> dict:
    lam = Q.rule_lambdas(ca, ca["lam_old"], grids=GRIDS)
    rc = K.crc(ca)
    for b in Q.BETAS:
        sg = K.sgr(ca["s"], ca["c"], b, Q.DELTA)["threshold"]
        lam[f"R3 joint max(SGR, CRC max) b{b:.2f}"] = max(sg, max(ca["lam_old"], rc.threshold))
        lam[f"SGR b{b:.2f}"] = sg
        lam[f"joint LTT b{b:.2f} + max rule (no sel. guarantee)"] = max(ca["lam_old"], lam[f"joint LTT b{b:.2f}"])
    return lam


ORDER = ["LTT max", "CRC max"] + [x for b in Q.BETAS for x in (
    f"joint LTT b{b:.2f}", f"joint LTT b{b:.2f} g01", f"joint LTT b{b:.2f} + max rule (no sel. guarantee)", f"LTT-sel b{b:.2f}",
    f"SGR b{b:.2f}", f"R3 joint max(SGR, CRC max) b{b:.2f}")]


def beta_of(rule: str) -> float | None:
    for b in Q.BETAS:
        if f"b{b:.2f}" in rule:
            return b
    return None


def agg(rows: list[dict]) -> dict:
    per = []
    for sp in rows:
        lam = lambdas(sp["cal"])
        per.append({r: {**K.outcome(sp["test"], lam[r]), "threshold": lam[r]} for r in ORDER})
    out = {}
    for r in ORDER:
        v = [p[r] for p in per]
        wc = np.array([x["wrong_commit"] for x in v])
        com = [x for x in v if x["n_commit"] > 0]
        b = beta_of(r)
        k_gt = int(np.sum(wc > Q.ALPHA + 1e-12))
        nc = sum(x["n_commit"] for x in v)
        eac_gt = sum(1 for x in com if b is not None and x["error_among_commits"] > b + 1e-12)
        out[r] = {"R": len(v), "wrong_commit_mean": float(wc.mean()), "wrong_commit_p95": float(np.quantile(wc, 0.95)),
                  "share_gt_alpha": k_gt / len(v), "share_gt_alpha_cp95": Q.cp(k_gt, len(v)),
                  "commit_rate_mean": float(np.mean([x["commit_rate"] for x in v])),
                  "share_no_commit": float(np.mean([x["n_commit"] == 0 for x in v])),
                  "eac_pooled": (sum(x["n_commit_wrong"] for x in v) / nc) if nc else None,
                  "n_committing_splits": len(com),
                  "share_eac_gt_beta_of_committing": (eac_gt / len(com)) if com else None,
                  "share_eac_gt_beta_cp95": Q.cp(eac_gt, len(com)) if com else None,
                  "ewpm_mean": float(np.mean([x["ewpm"] for x in v]))}
    return out, per


def fixed_tables() -> dict:
    clean = Q.K.R1 / "clean-drift" / "results"
    out = {}
    specs = [(f"b2t-{w}/split {lab}", clean / f"items-{w}-{s}.json") for w in ("ours", "published") for s, lab in (("alternate", "A"), ("chrono", "B"))]
    specs += [(f"emg-{c}", clean / f"items-emg-{c}.json") for c in ("calib", "xsession", "xsubject")]
    for name, p in specs:
        d = json.loads(p.read_text(encoding="utf-8"))
        ca, te = K.arr(d["items_cal"]), K.arr(d["items_test"])
        ca["lam_old"] = te["lam_old"]
        lam = lambdas(ca)
        out[name] = {}
        for r in ORDER:
            o = K.outcome(te, lam[r])
            k = Q.wrong_count(o)
            out[name][r] = {**o, "threshold": lam[r], "n_wrong": k, "wrong_commit_cp95": Q.cp(k, o["n"]),
                            "eac_cp95": Q.cp(int(round(o["n_commit_wrong"])), o["n_commit"]) if o["n_commit"] else None}
    meg = Q.K.CACHE3 / "meg-clean-items.json"
    if meg.exists():
        d = json.loads(meg.read_text(encoding="utf-8"))
        ca, te = K.arr(d["items_cal"]), K.arr(d["items_test"])
        ca["lam_old"] = te["lam_old"]
        lam = lambdas(ca)
        out["meg-async (instance level, no guarantee for new sentences)"] = {
            r: {**K.outcome(te, lam[r]), "threshold": lam[r]} for r in ORDER}
    return out


def main() -> None:
    res = {"config": CONFIG, "repeated": {}, "fixed": fixed_tables()}
    per_split = {}
    for cond in Q.CONDS:
        for guard in (1, 0):
            R = 200 if cond.startswith("b2t") else 50
            rows = Q.load_all(cond, R, guard)
            if not rows:
                continue
            sets = [(f"R{len(rows)}", rows)]
            if len(rows) > 50:
                sets.append(("R50", rows[:50]))
            for tag, rr in sets:
                key = f"{cond}/{'guard' if guard else 'no guard'}/{tag}"
                res["repeated"][key], per = agg(rr)
                if tag != "R50":
                    per_split[key] = [{r: {k: v for k, v in x[r].items()} for r in ("LTT max", "joint LTT b0.10", "joint LTT b0.20")} for x in per]
                a = res["repeated"][key]
                C.log(f"{key}: joint b0.10 commit {a['joint LTT b0.10']['commit_rate_mean']:.3f} wc {a['joint LTT b0.10']['wrong_commit_mean']:.4f} "
                      f"eac {Q.fmt(a['joint LTT b0.10']['eac_pooled'], 3)}; joint b0.20 commit {a['joint LTT b0.20']['commit_rate_mean']:.3f} "
                      f"wc {a['joint LTT b0.20']['wrong_commit_mean']:.4f} eac {Q.fmt(a['joint LTT b0.20']['eac_pooled'], 3)}")
    C.dump(res, OUT / "joint_ltt.json")
    C.dump(per_split, OUT / "per_split.json")
    write(res)


def write(res: dict) -> None:
    L = ["# Joint LTT (marginal ≤ α and error among commits ≤ β, δ = 0.1): tables", "",
         "Repeated splits: mean test wrong-commit, share of splits > α [CP95], mean commit rate, no-commit splits, pooled EAC, share of "
         "committing splits with EAC > β [CP95], mean eWPM. 'g01' = grid step 0.01 (100 points, Bonferroni δ/100). Rules marked 'no sel. "
         "guarantee' are shown for comparison only.", ""]
    for key, a in res["repeated"].items():
        L += [f"## {key}", "", "| rule | wrong-commit mean | >α [CP95] | commit | no-commit splits | EAC pooled | EAC>β (committing splits) [CP95] | eWPM |",
              "|---|---|---|---|---|---|---|---|"]
        for r, d in a.items():
            L.append(f"| {r} | {d['wrong_commit_mean']:.4f} | {d['share_gt_alpha']:.2f} {Q.fci(d['share_gt_alpha_cp95'], 2)} | "
                     f"{d['commit_rate_mean']:.3f} | {d['share_no_commit']:.2f} | {Q.fmt(d['eac_pooled'], 3)} | "
                     f"{Q.fmt(d['share_eac_gt_beta_of_committing'], 2)} of {d['n_committing_splits']} {Q.fci(d['share_eac_gt_beta_cp95'], 2)} | "
                     f"{d['ewpm_mean']:.2f} |")
        L.append("")
    L += ["## Fixed splits", "", "| condition | rule | λ | wrong-commit [CP95] | commit | EAC [CP95] | eWPM |", "|---|---|---|---|---|---|---|"]
    for name, rr in res["fixed"].items():
        for r in ("LTT max", "joint LTT b0.10", "joint LTT b0.10 g01", "joint LTT b0.20", "joint LTT b0.20 g01", "R3 joint max(SGR, CRC max) b0.10"):
            o = rr[r]
            L.append(f"| {name} | {r} | {Q.fmt(o['threshold'], 2)} | {o['wrong_commit']:.4f} {Q.fci(o.get('wrong_commit_cp95'))} | "
                     f"{o['commit_rate']:.3f} ({o['n_commit']}) | {Q.fmt(o['error_among_commits'], 3)} {Q.fci(o.get('eac_cp95'))} | {o['ewpm']:.2f} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
