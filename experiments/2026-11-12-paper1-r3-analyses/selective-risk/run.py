"""R3 item 2: selective-risk controllers (error among commits).

Editor M3 (major), stats review §8 (round-1 D-M2). The marginal target
(P(commit and wrong) <= alpha) allows a high error among commits. Here the
commit threshold is set so that the error among commits P(wrong | commit)
is at most beta with probability >= 1 - delta (delta = 0.1):

- SGR, "selection with guaranteed risk" (Geifman & El-Yaniv 2017, Alg. 1):
  binary search over the sorted calibration scores, exact binomial upper
  bound, Bonferroni delta / ceil(log2 m).
- LTT on the error among commits: H0(lambda): P(wrong | s >= lambda) > beta,
  exact binomial p-value conditional on the number of commits, Bonferroni
  over the fixed grid lambda = 0.05 ... 1.00 (step 0.05).
- joint: max(SGR, deployable CRC max-rule): marginal <= alpha AND selective
  <= beta.

Targets beta = 0.05, 0.10, 0.20. Data:
1. repeated deployment splits (``repeated-splits``; B2T 50, sEMG 50 splits):
   copied from ``repeated-splits/results/repeated_splits.json``;
2. the paper's fixed clean splits (B2T split A / B, sEMG fit-B2, MEG val-B),
   with unified bootstrap CIs (seed 20261112, B 2000);
3. MEG sentence-grouped splits of the G1 item table (8 of 17 sentences
   calibrate, R = 1000): instance-level, no guarantee for new sentences.

Run (repo root, after repeated-splits analyze and deployable-rule):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/selective-risk/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
BETAS = CONFIG["betas"]


def controllers(ca: dict, lp: float) -> dict:
    rc = K.crc(ca)
    lmax = max(lp, rc.threshold)
    out = {"CRC max-rule (marginal only)": {"threshold": lmax}}
    for b in BETAS:
        sg = K.sgr(ca["s"], ca["c"], b, C.DELTA)
        ls = K.ltt_selective(ca["s"], ca["c"], b, C.DELTA)
        out[f"SGR β={b:.2f}"] = {"threshold": sg["threshold"], "bound": sg["bound"], "n_selected_cal": sg["n_selected"]}
        out[f"LTT-sel β={b:.2f}"] = {"threshold": ls["threshold"]}
        out[f"joint β={b:.2f} (SGR + CRC max-rule)"] = {"threshold": max(sg["threshold"], lmax)}
    return out


def fixed_rows() -> dict:
    clean = K.R1 / "clean-drift/results"
    srcs = [(f"b2t-{w}/split {s}", clean / f"items-{w}-{f}.json", "days_test")
            for w in ("ours", "published") for s, f in (("A", "alternate"), ("B", "chrono"))]
    srcs += [(f"emg-{c}", clean / f"items-emg-{c}.json", "participants_test") for c in ("calib", "xsession", "xsubject")]
    srcs += [("meg-async (val-B, instance level)", K.CACHE3 / "meg-clean-items.json", "meg")]
    out = {}
    for name, p, unit in srcs:
        if not p.exists():
            C.log(f"missing {p}")
            continue
        items = json.loads(p.read_text(encoding="utf-8"))
        ca = K.arr(items["items_cal"])
        lp = float(C.fnum(items["items_test"]["lam_old"]))
        ctl = controllers(ca, lp)
        arrs = {k: C.item_arrays(items["items_test"], v["threshold"]) for k, v in ctl.items()}
        if unit == "meg":
            cl = np.unique(items["participants_test"], return_inverse=True)[1]
            nsp = SimpleNamespace(cluster=cl, sent=np.asarray(items["sentence_ids_test"]), scheme="two_way")
        else:
            nsp = SimpleNamespace(cluster=np.unique(items[unit], return_inverse=True)[1], sent=None, scheme="cluster")
        pt = C.point(arrs)
        for k, a in arrs.items():
            pt[k]["n_commit"] = int(a["com"].sum())
            pt[k]["n_commit_wrong"] = int(round(a["wcc"].sum()))
            pt[k]["threshold"] = C.clean(ctl[k]["threshold"])
            if pt[k]["n_commit"]:
                pt[k]["eac_cp95"] = K.clopper_pearson(pt[k]["n_commit_wrong"], pt[k]["n_commit"])
        out[name] = {"n_cal": int(ca["s"].size), "n_test": len(items["items_test"]["score"]), "point": pt,
                     "ci": C.bootstrap(arrs, nsp, B=K.UNIFIED_B, seed=K.UNIFIED_SEED)}
        C.log(f"{name}: " + "; ".join(f"{k}: commit {pt[k]['commit_rate']:.3f} EAC {pt[k]['n_commit_wrong']}/{pt[k]['n_commit']}"
                                      for k in pt if k.startswith("SGR")))
    return out


def meg_grouped(reps: int = 1000, k: int = 8) -> dict:
    d = json.loads((K.REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json").read_text(encoding="utf-8"))
    a = K.arr(d["test"])
    sent = np.asarray(d["sentence_ids_test"])
    ug = np.unique(sent)
    rng = np.random.default_rng(CONFIG["seed"])
    rows: dict = {}
    for _ in range(reps):
        cg = rng.choice(ug, k, replace=False)
        m = np.isin(sent, cg)
        ca, te = K.take(a, np.where(m)[0]), K.take(a, np.where(~m)[0])
        for name, v in controllers(ca, a["lam_old"]).items():
            rows.setdefault(name, []).append(K.outcome(te, v["threshold"]))
    out = {}
    for name, v in rows.items():
        nc = sum(x["n_commit"] for x in v)
        out[name] = {"commit_rate": K.summ([x["commit_rate"] for x in v]), "wrong_commit": K.summ([x["wrong_commit"] for x in v]),
                     "share_no_commit": float(np.mean([x["n_commit"] == 0 for x in v])),
                     "error_among_commits_pooled": (sum(x["n_commit_wrong"] for x in v) / nc) if nc else None,
                     "ewpm": K.summ([x["ewpm"] for x in v])}
    return {"reps": reps, "k_cal_sentences": k, "rows": out}


def main() -> None:
    rs_p = HERE.parent / "repeated-splits/results/repeated_splits.json"
    rs = json.loads(rs_p.read_text(encoding="utf-8")) if rs_p.exists() else {"conditions": {}}
    res = {"config": CONFIG, "repeated_splits": {k: {"selective": v["selective"],
                                                     "crc_maxrule": v["aggregate"]["policies"]["CRC max-rule (clean)"],
                                                     "plugin": v["aggregate"]["policies"]["plug-in (fit-A)"]}
                                                 for k, v in rs["conditions"].items()},
           "fixed_splits": fixed_rows(), "meg_sentence_grouped": meg_grouped()}
    C.dump(res, OUT / "selective_risk.json")
    f = lambda x, nd=3: C.fmt(C.fnum(x) if x is not None else None, nd)  # noqa: E731
    L = ["# Selective-risk controllers (error among commits ≤ β with probability ≥ 0.9)", "",
         "SGR = Geifman & El-Yaniv (2017) Alg. 1; LTT-sel = LTT on the error among commits (Bonferroni grid); "
         "joint = max(SGR, CRC max-rule) (marginal ≤ 0.05 and selective ≤ β).", "",
         "## 1. Repeated deployment splits (mean [p05, p95] over splits; test set)", "",
         "| condition | β | rule | commit rate | error among commits (pooled) | share of splits with EAC > β | no-commit splits | marginal wrong-commit | eWPM |",
         "|---|---|---|---|---|---|---|---|---|"]
    for c, v in res["repeated_splits"].items():
        for b, ms in v["selective"].items():
            for m, d in ms.items():
                L.append(f"| {c} | {b} | {m} | {f(d['commit_rate']['mean'])} [{f(d['commit_rate']['p05'])}, {f(d['commit_rate']['p95'])}] | "
                         f"{f(d['error_among_commits_pooled'])} | {d['share_eac_gt_beta']:.2f} | {d['share_no_commit']:.2f} | "
                         f"{f(d['wrong_commit']['mean'], 4)} | {f(d['ewpm']['mean'], 2)} |")
        p = v["crc_maxrule"]
        L.append(f"| {c} | — | CRC max-rule (reference) | {f(p['commit_rate']['mean'])} | {f(p['error_among_commits_pooled'])} | | "
                 f"{p['share_no_commit']:.2f} | {f(p['wrong_commit']['mean'], 4)} | {f(p['ewpm']['mean'], 2)} |")
    L += ["", "## 2. The paper's fixed clean splits (test set; CI: unified bootstrap at the condition's unit)", "",
          "| condition | rule | λ | commit rate | wrong / commits (CP95) | marginal wrong-commit [CI] | eWPM [CI] |", "|---|---|---|---|---|---|---|"]
    for c, v in res["fixed_splits"].items():
        for m, d in v["point"].items():
            ci = v["ci"]["policies"][m]
            cp = d.get("eac_cp95")
            L.append(f"| {c} | {m} | {f(d['threshold'])} | {d['commit_rate']:.3f} | {d['n_commit_wrong']}/{d['n_commit']}"
                     + (f" [{cp[0]:.3f}, {cp[1]:.3f}]" if cp else "") + f" | {d['wrong_commit']:.4f} {C.fci(ci['wrong_commit'], 3)} | "
                     f"{d['ewpm']:.2f} {C.fci(ci['ewpm'], 2)} |")
    mg = res["meg_sentence_grouped"]
    L += ["", f"## 3. MEG, sentence-grouped splits ({mg['k_cal_sentences']} of 17 sentences calibrate; R = {mg['reps']}; no guarantee for new sentences)", "",
          "| rule | commit rate mean | no-commit splits | error among commits (pooled) | wrong-commit mean | eWPM mean |", "|---|---|---|---|---|---|"]
    for m, d in mg["rows"].items():
        L.append(f"| {m} | {f(d['commit_rate']['mean'], 4)} | {d['share_no_commit']:.3f} | {f(d['error_among_commits_pooled'])} | "
                 f"{f(d['wrong_commit']['mean'], 4)} | {f(d['ewpm']['mean'], 3)} |")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")
    C.log("done")


if __name__ == "__main__":
    main()
