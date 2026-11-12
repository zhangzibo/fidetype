"""R4 item 3: population risk that is not biased low; exceedance shares with exact CIs.

Stats M4(b, c). App. R computed "the rate of the chosen threshold on the
whole pool", but the pool contained the calibration items, so that rate is
biased low. Here:

(a) App. R pools (the full-fit pipeline's test tables, M2-13 / M2-16 items;
    B2T 816 trials, sEMG 551 sentences), n_cal in {100, 408 (B2T) / 275 (sEMG)},
    M draws per design:
    - ``incl-cal``: calibration drawn without replacement, risk on the whole
      pool (the App. R computation, biased low; reproduced for reference);
    - ``held-out``: without replacement, risk on the items not drawn;
    - ``with-replacement``: calibration drawn i.i.d. with replacement from the
      pool; the risk of the chosen threshold on the pool is then the exact
      population risk of the i.i.d. theory (the pool is the population).
(b) Repeated splits (R = 50 and 200): pool = clean calibration + test items of
    one split (fixed fit-A pipeline); M_split draws with replacement of the
    split's calibration size; exact pool risk.
(c) Test-set exceedance over the splits ("> alpha" shares of Tab. 2) with
    exact Clopper-Pearson CIs, and an exact McNemar test of LTT max vs CRC max
    (paired by split).

Rules: CRC pure, LTT pure, CRC max, LTT max (plug-in lambda of the fitted
pipeline; it does not depend on the pool draw). Fixed seeds.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/population-risk/run.py
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
RULES = ("CRC pure", "LTT pure", "CRC max", "LTT max")
A = Q.ALPHA


def thresholds(ca: dict, plug: float) -> dict:
    rc, rl = K.crc(ca), K.ltt(ca)
    return {"CRC pure": rc.threshold, "LTT pure": rl.threshold, "CRC max": max(plug, rc.threshold), "LTT max": max(plug, rl.threshold)}


def risk(a: dict, lam: float, idx=None) -> float:
    b = a if idx is None else K.take(a, idx)
    on = b["s"] >= lam
    return float(np.where(on, b["wc_c"], b["wc_f"]).mean())


def summ_exc(v: list[float]) -> dict:
    v = np.asarray(v, float)
    k = int(np.sum(v > A + 1e-12))
    return {"M": int(v.size), "mean": float(v.mean()), "p95": float(np.quantile(v, 0.95)), "n_gt_alpha": k,
            "share_gt_alpha": k / v.size, "share_cp95": Q.cp(k, v.size)}


def app_r_pools() -> dict:
    R = Q.REPO / "experiments"
    pools = {"b2t-ours": R / "2026-11-11-m2-13-conformal/results/items-b2t-ours.json",
             "b2t-published": R / "2026-11-11-m2-13-conformal/results/items-b2t-published.json",
             "emg-calib": R / "2026-11-11-m2-16-online-recal/results/items-emg-calib.json",
             "emg-xsession": R / "2026-11-11-m2-16-online-recal/results/items-emg-xsession.json",
             "emg-xsubject": R / "2026-11-11-m2-16-online-recal/results/items-emg-xsubject.json"}
    out = {}
    for name, p in pools.items():
        d = json.loads(p.read_text(encoding="utf-8"))
        a = K.arr(d["test"])
        n = a["s"].size
        rng = np.random.default_rng(CONFIG["seed"])
        res = {"n_pool": n, "pool_rate_at_lambda": {}}
        for ncal in (CONFIG["n_cal_small"], n // 2):
            des = {"incl-cal": {r: [] for r in RULES}, "held-out": {r: [] for r in RULES}, "with-replacement": {r: [] for r in RULES}}
            for _ in range(CONFIG["M_pool"]):
                perm = rng.permutation(n)
                ci, ho = perm[:ncal], perm[ncal:]
                lam = thresholds(K.take(a, ci), a["lam_old"])
                for r in RULES:
                    des["incl-cal"][r].append(risk(a, lam[r]))
                    des["held-out"][r].append(risk(a, lam[r], ho))
                wi = rng.integers(0, n, ncal)
                lam = thresholds(K.take(a, wi), a["lam_old"])
                for r in RULES:
                    des["with-replacement"][r].append(risk(a, lam[r]))
            res[f"n_cal={ncal}"] = {dn: {r: summ_exc(v) for r, v in dd.items()} for dn, dd in des.items()}
        out[name] = res
        C.log(f"App. R pool {name}: " + "; ".join(f"{k} " + ", ".join(
            f"{dn}/{r} {v[r]['share_gt_alpha']:.3f}" for dn, v in res[k].items() for r in ("LTT pure", "CRC pure"))
            for k in res if k.startswith("n_cal")))
    return out


def mcnemar(x: np.ndarray, y: np.ndarray) -> dict:
    from scipy.stats import binomtest
    b = int(np.sum(x & ~y))
    c = int(np.sum(~x & y))
    p = float(binomtest(b, b + c, 0.5).pvalue) if b + c else 1.0
    return {"only_first": b, "only_second": c, "p_exact_two_sided": p}


def split_pools() -> dict:
    out = {}
    for cond in Q.CONDS:
        Rmax = 200 if cond.startswith("b2t") else 50
        rows_all = Q.load_all(cond, Rmax)
        for tag, rows in ((f"R{len(rows_all)}", rows_all),) + ((("R50", rows_all[:50]),) if len(rows_all) > 50 else ()):
            rng = np.random.default_rng(CONFIG["seed"] + 1)
            test_exc = {r: [] for r in RULES}
            pop = {r: [] for r in RULES}
            per_split_share = {r: [] for r in RULES}
            for sp in rows:
                ca, te = sp["cal"], sp["test"]
                lam = thresholds(ca, ca["lam_old"])
                for r in RULES:
                    test_exc[r].append(risk(te, lam[r]))
                pool = {k: (np.concatenate([ca[k], te[k]]) if isinstance(ca[k], np.ndarray) else ca[k]) for k in ca}
                pool["c"], pool["f"] = pool["loss_c"], pool["loss_f"]
                n, ncal = pool["s"].size, ca["s"].size
                vals = {r: [] for r in RULES}
                for _ in range(CONFIG["M_split"]):
                    wi = rng.integers(0, n, ncal)
                    lm = thresholds(K.take(pool, wi), ca["lam_old"])
                    for r in RULES:
                        vals[r].append(risk(pool, lm[r]))
                for r in RULES:
                    pop[r] += vals[r]
                    per_split_share[r].append(float(np.mean(np.array(vals[r]) > A + 1e-12)))
            te_s = {r: summ_exc(v) for r, v in test_exc.items()}
            mc = mcnemar(np.array(test_exc["LTT max"]) > A + 1e-12, np.array(test_exc["CRC max"]) > A + 1e-12)
            mc_pure = mcnemar(np.array(test_exc["LTT pure"]) > A + 1e-12, np.array(test_exc["CRC pure"]) > A + 1e-12)
            out[f"{cond}/{tag}"] = {
                "R": len(rows), "test_exceedance": te_s, "mcnemar_LTTmax_vs_CRCmax": mc, "mcnemar_LTTpure_vs_CRCpure": mc_pure,
                "population_with_replacement": {r: {**summ_exc(v), "per_split_share_max": float(np.max(per_split_share[r])),
                                                    "per_split_share_mean": float(np.mean(per_split_share[r]))} for r, v in pop.items()}}
            C.log(f"{cond}/{tag}: test >a " + ", ".join(f"{r} {te_s[r]['n_gt_alpha']}/{len(rows)}" for r in RULES)
                  + f"; McNemar LTTmax vs CRCmax p {mc['p_exact_two_sided']:.3g}; pop >a " +
                  ", ".join(f"{r} {out[f'{cond}/{tag}']['population_with_replacement'][r]['share_gt_alpha']:.3f}" for r in RULES))
    return out


def main() -> None:
    res = {"config": CONFIG, "app_r_pools": app_r_pools(), "split_pools": split_pools()}
    C.dump(res, OUT / "population_risk.json")
    write(res)


def write(res: dict) -> None:
    L = ["# Population risk and exceedance shares: tables", "",
         "α = 0.05, δ = 0.1. Share > α with exact Clopper-Pearson 95 % CI. 'with-replacement': calibration drawn i.i.d. from the pool; the "
         "pool risk of the chosen threshold is the exact population risk (theory: LTT share ≤ δ, CRC mean ≤ α). 'incl-cal' is the App. R "
         "computation (biased low). 'held-out' contains test-sampling noise.", "", "## (a) App. R pools (full-fit pipeline, test pool)", ""]
    for name, r in res["app_r_pools"].items():
        L += [f"### {name} (pool {r['n_pool']})", "", "| n_cal | design | rule | mean risk | share > α [CP95] | p95 |", "|---|---|---|---|---|---|"]
        for k, v in r.items():
            if not k.startswith("n_cal"):
                continue
            for dn, dd in v.items():
                for rule, s in dd.items():
                    L.append(f"| {k[6:]} | {dn} | {rule} | {s['mean']:.4f} | {s['share_gt_alpha']:.3f} {Q.fci(s['share_cp95'])} | {s['p95']:.4f} |")
        L.append("")
    L += ["## (b, c) Repeated splits: test-set exceedance and exact population risk (with replacement)", ""]
    for key, r in res["split_pools"].items():
        L += [f"### {key}", "", "| rule | test: splits > α | share [CP95] | population (w.r.): mean | share > α [CP95] | max per-split share |",
              "|---|---|---|---|---|---|"]
        for rule in RULES:
            t, p = r["test_exceedance"][rule], r["population_with_replacement"][rule]
            L.append(f"| {rule} | {t['n_gt_alpha']}/{t['M']} | {t['share_gt_alpha']:.3f} {Q.fci(t['share_cp95'])} | {p['mean']:.4f} | "
                     f"{p['share_gt_alpha']:.4f} {Q.fci(p['share_cp95'], 4)} | {p['per_split_share_max']:.3f} |")
        m, mp = r["mcnemar_LTTmax_vs_CRCmax"], r["mcnemar_LTTpure_vs_CRCpure"]
        L += ["", f"Exact McNemar (test exceedance, paired by split): LTT max vs CRC max: {m['only_first']} vs {m['only_second']} discordant, "
                  f"p = {m['p_exact_two_sided']:.3g}; LTT pure vs CRC pure: {mp['only_first']} vs {mp['only_second']}, p = {mp['p_exact_two_sided']:.3g}.", ""]
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
