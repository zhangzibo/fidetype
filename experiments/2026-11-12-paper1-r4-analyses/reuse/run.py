"""R4 item 7: the data-reuse comparisons in full, with a test that respects split overlap.

Stats M5; editor M5. Reused calibration = the data that also fitted the
pipeline (B2T: fit-A; sEMG: fit-B1, the policy-grid data); clean = disjoint.
12 comparisons: 4 conditions (B2T ours, published; sEMG calib, xsession;
sEMG xsubject never commits) x 3 rule pairs (CRC pure, CRC max, LTT pure).

Tests (two-sided):
- Wilcoxon signed-rank over splits (R3 test). The splits re-use one pool of
  trials, so this is a test conditional on that pool, not about new data.
- Cluster-blocked sign-flip test: per day (B2T, 14) or test participant
  (sEMG, 19), the mean over splits of the paired difference of the day's test
  rate; exact sign-flip permutation of the cluster means (2^14 / 2^19 sign
  vectors). Clusters are the units of new data; the split overlap is averaged
  out inside each cluster.
- Sign test over clusters.
- Delete-a-cluster jackknife over the whole split ensemble (primary test that
  respects the overlap): for each day / participant g, remove g's items from
  the reused, clean-calibration AND test tables of every split, recompute both
  thresholds and the mean paired difference; jackknife SE over the G clusters,
  t test with G - 1 df. All splits share the clusters, so this SE includes the
  between-split dependence (the fitted pipeline is not refitted: its own
  dependence on g is not removed).
Holm over the 12 comparisons for each test family (R = 50, the paper's
splits; and R = 200 for B2T).

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/reuse/run.py
"""

from __future__ import annotations

import itertools
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
PAIRS = ("CRC pure", "CRC max", "LTT pure")
CONDS = ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession")


def lam_pair(sp: dict, rule: str) -> tuple[float, float]:
    re, ca = sp["reuse"], sp["cal"]
    plug = ca["lam_old"]
    out = []
    for a in (re, ca):
        if rule == "CRC pure":
            out.append(K.crc(a).threshold)
        elif rule == "CRC max":
            out.append(max(plug, K.crc(a).threshold))
        else:
            out.append(K.ltt(a).threshold)
    return out[0], out[1]


def exact_signflip(d: np.ndarray) -> float:
    k = d.size
    obs = abs(d.mean())
    tot, hit = 0, 0
    # chunks to keep memory small for 2^19
    signs_head = np.array(list(itertools.product([-1.0, 1.0], repeat=min(k, 10))))
    rest = k - signs_head.shape[1]
    for tail in itertools.product([-1.0, 1.0], repeat=rest):
        s = np.hstack([signs_head, np.tile(np.array(tail), (signs_head.shape[0], 1))]) if rest else signs_head
        m = np.abs((s * d).mean(1))
        hit += int(np.sum(m >= obs - 1e-12))
        tot += s.shape[0]
    return hit / tot


FIT_WHO = json.loads((Q.CACHE4 / "emg-fit-who.json").read_text(encoding="utf-8"))


def groups(sp: dict, cond: str):
    """Cluster labels of reuse / cal / test items of one split."""
    if cond.startswith("b2t"):
        return sp["reuse_group"], sp["cal_group"], sp["test_group"]
    who = np.asarray(FIT_WHO[cond[4:]])
    asg = json.loads(Q.split_path(cond, sp["r"]).read_text(encoding="utf-8"))["assign"]
    return who[np.asarray(asg["B1"])], who[np.asarray(asg["B2"])], sp["test_group"]


def thr(a: dict, rule: str, plug: float) -> float:
    if rule == "CRC pure":
        return K.crc(a).threshold
    if rule == "CRC max":
        return max(plug, K.crc(a).threshold)
    return K.ltt(a).threshold


def jackknife(rows: list[dict], cond: str, rule: str) -> dict:
    from scipy.stats import t as tdist
    G = sorted({str(x) for x in rows[0]["test_group"]})
    gs = [groups(sp, cond) for sp in rows]
    full = []
    for sp in rows:
        lu, lc = thr(sp["reuse"], rule, sp["cal"]["lam_old"]), thr(sp["cal"], rule, sp["cal"]["lam_old"])
        full.append(K.outcome(sp["test"], lu)["wrong_commit"] - K.outcome(sp["test"], lc)["wrong_commit"])
    theta = float(np.mean(full))
    loo = []
    for g in G:
        v = []
        for sp, (gr, gc, gt) in zip(rows, gs):
            ir = np.where(np.asarray(gr).astype(str) != g)[0]
            ic = np.where(np.asarray(gc).astype(str) != g)[0]
            it = np.where(np.asarray(gt).astype(str) != g)[0]
            plug = sp["cal"]["lam_old"]
            lu, lc = thr(K.take(sp["reuse"], ir), rule, plug), thr(K.take(sp["cal"], ic), rule, plug)
            v.append(K.outcome(sp["test"], lu, it)["wrong_commit"] - K.outcome(sp["test"], lc, it)["wrong_commit"])
        loo.append(float(np.mean(v)))
    loo = np.array(loo)
    n = loo.size
    se = float(np.sqrt((n - 1) / n * np.sum((loo - loo.mean()) ** 2)))
    tt = theta / se if se > 0 else 0.0
    p = float(2 * tdist.sf(abs(tt), n - 1)) if se > 0 else 1.0
    return {"theta": theta, "jackknife_se": se, "t": tt, "df": n - 1, "p_two_sided": p,
            "ci95": [theta - tdist.ppf(0.975, n - 1) * se, theta + tdist.ppf(0.975, n - 1) * se]}


def analyze(rows: list[dict], cond: str = "") -> dict:
    from scipy.stats import wilcoxon
    out = {}
    for rule in PAIRS:
        diffs, by_cl = [], {}
        for sp in rows:
            lu, lc = lam_pair(sp, rule)
            te, g = sp["test"], sp["test_group"]
            diffs.append(K.outcome(te, lu)["wrong_commit"] - K.outcome(te, lc)["wrong_commit"])
            for cl in np.unique(g):
                idx = np.where(g == cl)[0]
                by_cl.setdefault(str(cl), []).append(K.outcome(te, lu, idx)["wrong_commit"] - K.outcome(te, lc, idx)["wrong_commit"])
        d = np.array(diffs)
        try:
            pw = float(wilcoxon(d, zero_method="wilcox").pvalue) if np.any(d != 0) else 1.0
        except ValueError:
            pw = 1.0
        cm = np.array([np.mean(v) for v in by_cl.values()])
        out[rule] = {"R": len(rows), "mean_diff": float(d.mean()), "p05": float(np.quantile(d, 0.05)), "p95": float(np.quantile(d, 0.95)),
                     "share_reused_higher": float(np.mean(d > 1e-12)), "share_equal": float(np.mean(np.abs(d) <= 1e-12)),
                     "wilcoxon_p_splits": pw, "sign_test_splits": K.sign_test(d),
                     "n_clusters": int(cm.size), "cluster_mean_diffs": {k: float(np.mean(v)) for k, v in by_cl.items()},
                     "cluster_mean_of_means": float(cm.mean()),
                     "signflip_p_clusters_exact": exact_signflip(cm) if np.any(np.abs(cm) > 1e-15) else 1.0,
                     "sign_test_clusters": K.sign_test(cm)}
        jk = jackknife(rows, cond, rule)
        out[rule]["jackknife"] = jk
        out[rule]["jackknife_p"] = jk["p_two_sided"]
    return out


def main() -> None:
    res = {"config": CONFIG, "families": {}}
    for fam, R in (("R50", 50), ("R200", 200)):
        comps = {}
        for cond in CONDS:
            if fam == "R200" and not cond.startswith("b2t"):
                rows = Q.load_all(cond, 50)  # sEMG: 50 splits only
            else:
                rows = Q.load_all(cond, R)
            a = analyze(rows, cond)
            for rule, v in a.items():
                comps[f"{cond} / {rule}"] = v
            C.log(f"{fam} {cond}: " + "; ".join(f"{r} {v['mean_diff']:+.4f} W p {v['wilcoxon_p_splits']:.3g} cl p {v['signflip_p_clusters_exact']:.3g} jk p {v['jackknife_p']:.3g}"
                                               for r, v in a.items()))
        for key in ("wilcoxon_p_splits", "signflip_p_clusters_exact", "jackknife_p"):
            h = K.holm({k: v[key] for k, v in comps.items()})
            for k in comps:
                comps[k][key.replace("_p", "_holm")] = h[k]
        res["families"][fam] = comps
    C.dump(res, OUT / "reuse.json")
    write(res)


def write(res: dict) -> None:
    L = ["# Data reuse: all comparisons (reused − clean test wrong-commit)", "",
         "Wilcoxon over splits is conditional on one pool of trials. The cluster sign-flip test uses the per-day (B2T) or per-participant (sEMG) "
         "mean difference over splits, exact over all sign vectors; it covers test-day sampling only and treats days as independent although "
         "one threshold per split is shared by all days (anti-conservative). The delete-a-cluster jackknife (primary) recomputes both thresholds "
         "and the test rates without each day / participant over all splits; its SE includes the split overlap. Holm over the 12 comparisons per family.", ""]
    for fam, comps in res["families"].items():
        L += [f"## {fam}", "", "| comparison | R | mean diff [p05, p95] | reused higher / equal | Wilcoxon p (Holm) | sign test splits +/− p | "
              "clusters | cluster sign-flip p (Holm) | cluster sign +/− p | jackknife SE | jackknife 95 % CI | jackknife p (Holm) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in comps.items():
            s, sc = v["sign_test_splits"], v["sign_test_clusters"]
            L.append(f"| {k} | {v['R']} | {v['mean_diff']:+.4f} [{v['p05']:+.3f}, {v['p95']:+.3f}] | {v['share_reused_higher']:.2f} / {v['share_equal']:.2f} | "
                     f"{v['wilcoxon_p_splits']:.3g} ({v['wilcoxon_holm_splits']:.3g}) | {s['positive']}/{s['negative']} {s['p_two_sided']:.3g} | "
                     f"{v['n_clusters']} | {v['signflip_p_clusters_exact']:.3g} ({v['signflip_holm_clusters_exact']:.3g}) | "
                     f"{sc['positive']}/{sc['negative']} {sc['p_two_sided']:.3g} | {v['jackknife']['jackknife_se']:.4f} | "
                     f"[{v['jackknife']['ci95'][0]:+.4f}, {v['jackknife']['ci95'][1]:+.4f}] | {v['jackknife_p']:.3g} ({v['jackknife_holm']:.3g}) |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
