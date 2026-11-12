"""R1 item 1: clean drift baseline (methods review Major 3; domain review M9).

The M2-13 / M2-16 "drift" baseline calibrated offline CRC on the same data
that fitted the temperatures, conformal sets and the policy grid. Here the
CRC calibration data are disjoint from all of those:

- B2T '25 (ours and the published-sentence gate): the fit half of each day
  is split into fit-A (temperatures, conformal, guard, policy grid:
  ``pipe.fit(A, A)``, the M6-06 recipe on fewer trials) and fit-B (CRC / LTT
  calibration only). Two splits: ``alternate`` (odd / even trials of each
  day's fit half, file order) and ``chrono`` (first / second half of each
  day's fit half: fit-B is closer in time to the test half).
- sEMG (``xsession``, ``calib``, ``xsubject``): fit-A as in M6-07; fit-B
  (policy-grid data) is split: fit-B1 = policy grid, fit-B2 = CRC calibration
  (the same split as the M6-07 ``c_crc`` rows).

Then the test half is run as in M2-16: offline plug-in gate / CRC / LTT, the
four online methods (warm start on the clean calibration items, test in
order, delay 0 and 10), and the shuffled-order control (20 shuffles). Two
references answer "is there a shift between calibration and test data?":
(a) exchangeable reference: pool calibration + test items, 1000 random
splits of the same sizes, CRC on one part, wrong-commit on the other;
p-value = share of random splits with a test rate >= the observed one;
(b) the old (reused-data) M2-16 numbers.

Time order: B2T = file order inside each post-implant day (the pickle has no
time stamps; see ``check_order``); sEMG = participant by participant (plan
order): a between-participant sequence, not a session.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/clean-drift/run.py
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
import common as C  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
M13 = C.load_module("m213run", C.REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
M16 = C.load_module("m216run", C.REPO / "experiments/2026-11-11-m2-16-online-recal/run.py")


def check_order() -> dict:
    """List the keys of the copy-task pickle and check that days are contiguous in file order."""
    from fidetype.adapters import b2t25 as B
    from fidetype.adapters.b2t25 import safe_load

    d = safe_load(json.loads((C.REPO / "experiments/2026-11-10-b2t25-trust/config.json").read_text())["pkl"], B.DRYAD_SHA256)
    days = list(d["post_implant_day"])
    runs = [days[0]]
    for x in days[1:]:
        if x != runs[-1]:
            runs.append(x)
    timeish = [k for k in d if any(w in k.lower() for w in ("time", "date", "stamp", "block", "trial", "session", "clock"))]
    return {"keys": sorted(d.keys()), "time_like_keys": timeish, "n_trials": len(days),
            "day_runs_in_file_order": [int(x) for x in runs], "days_contiguous": len(runs) == len(set(runs)),
            "days_ascending": all(int(a) < int(b) for a, b in zip(runs, runs[1:]))}


def exch_reference(tab_cal: dict, tab_test: dict, observed: float, reps: int, seed: int, cluster_cal=None, cluster_test=None) -> dict:
    """Pool calibration and test items; random splits of the same sizes; CRC on one part, rate on the other."""
    a_c, a_t = M16.Arr(tab_cal), M16.Arr(tab_test)
    n_c, n_t = a_c.s.size, a_t.s.size
    pool = M16.Arr.concat(a_c, a_t, np.arange(n_c + n_t))
    rng = np.random.default_rng(seed)
    rates, crs = [], []
    for _ in range(reps):
        perm = rng.permutation(n_c + n_t)
        cal, tst = perm[:n_c], perm[n_c:]
        lam = C.crc_threshold(pool.s[cal], pool.loss_c[cal], C.ALPHA, pool.loss_f[cal]).threshold
        on = pool.s[tst] >= lam
        rates.append(float(np.where(on, pool.wc_c[tst], pool.wc_f[tst]).mean()))
        crs.append(float(on.mean()))
    rates = np.array(rates)
    return {"reps": reps, "mean": float(rates.mean()), "p05": float(np.quantile(rates, 0.05)),
            "p95": float(np.quantile(rates, 0.95)), "share_gt_alpha": float(np.mean(rates > C.ALPHA + 1e-12)),
            "observed": observed, "p_value_ge_observed": float((np.sum(rates >= observed - 1e-12) + 1) / (reps + 1)),
            "commit_rate_mean": float(np.mean(crs))}


def offline_rows(tab_cal: dict, tab_test: dict, lam_old: float, cond) -> dict:
    th = C.thresholds(tab_cal)
    lams = {"plug-in gate (fit-A)": lam_old, "CRC (clean cal)": th["crc"], "LTT (clean cal)": th["ltt"]}
    arrs = {k: C.item_arrays(tab_test, v) for k, v in lams.items()}
    pt = C.point(arrs)
    bs = C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 3)
    # The rate on the calibration data itself at each threshold (in-sample level).
    cal_rates = {k: C.metrics(C.item_arrays(tab_cal, v)) for k, v in lams.items()}
    return {"thresholds": {k: C.clean(v) for k, v in lams.items()}, "crc_info": th, "test": pt, "test_ci": bs,
            "calibration_set_rate": cal_rates}


def online_block(tab_cal: dict, tab_test: dict) -> dict:
    a_c, a_t = M16.Arr(tab_cal), M16.Arr(tab_test)
    dr = M16.protocol_drift(a_c, a_t, eta_grid=False)
    sh = M16.protocol_shuffled(a_c, a_t, CONFIG["shuffles"], CONFIG["seed"])
    return {"drift": dr, "shuffled": sh, "iid_reference": M16.iid_reference(a_t.s.size)}


def run_b2t() -> dict:
    ctx = C.b2t_ctx()
    res: dict = {"order_check": check_order()}
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    splits = {}
    for name in CONFIG["b2t_splits"]:
        A, Bi = [], []
        for d, idx in sorted(by_day.items()):
            if name == "alternate":
                A += idx[0::2]
                Bi += idx[1::2]
            else:  # chrono: first half of the day's fit trials -> A, second half -> B
                h = (len(idx) + 1) // 2
                A += idx[:h]
                Bi += idx[h:]
        splits[name] = (sorted(A), sorted(Bi))
    old = {w: json.loads((C.REPO / f"experiments/2026-11-11-m2-16-online-recal/results/online.json").read_text(encoding="utf-8"))
           ["datasets"][f"b2t-{w}"]["drift"]["offline"] for w in ("ours", "published")}
    for sname, (ia, ib) in splits.items():
        fa = [ctx.fit[i] for i in ia]
        fb = [ctx.fit[i] for i in ib]
        A, Bc, T = ctx.items(fa), ctx.items(fb), ctx.items(ctx.test)
        for which in ("ours", "published"):
            ts = time.time()
            cond = C.b2t_condition(ctx, which)
            fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
            pipe = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA), {})
            pipe.fit(A, A)
            tab_b = M13.item_table(pipe, Bc)
            tab_t = M13.item_table(pipe, T)
            C.save_caches(ctx)
            key = f"b2t-{which}/{sname}"
            r = {"n_fit_A": len(A), "n_cal_B": len(Bc), "n_test": len(T), "fit_report": C.clean(pipe.fit_report),
                 "offline": offline_rows(tab_b, tab_t, pipe.policy.config.commit_p, cond),
                 "online": online_block(tab_b, tab_t)}
            obs = r["offline"]["test"]["CRC (clean cal)"]["wrong_commit"]
            r["exchangeable_reference"] = exch_reference(tab_b, tab_t, obs, CONFIG["exch_reps"], CONFIG["seed"])
            r["old_reused_data_offline"] = old[which]
            # Random cal/test splits inside the clean test half (M2-13 protocol, n_cal 408): the exchangeable level.
            r["within_test_random_splits"] = within_test(tab_t, 408)
            res[key] = r
            C.dump({"items_cal": tab_b, "items_test": tab_t, "days_cal": [t.post_implant_day for t in fb],
                    "days_test": ctx.days_test}, OUT / f"items-{which}-{sname}.json")
            log_row(key, r, time.time() - ts)
            C.dump(res, OUT / "clean_drift_b2t.json")
    return res


def within_test(tab_t: dict, n_cal: int, reps: int = 200) -> dict:
    a = M16.Arr(tab_t)
    n = a.s.size
    rng = np.random.default_rng(CONFIG["seed"])
    wc = []
    for _ in range(reps):
        perm = rng.permutation(n)
        cal, tst = perm[:n_cal], perm[n_cal:]
        lam = C.crc_threshold(a.s[cal], a.loss_c[cal], C.ALPHA, a.loss_f[cal]).threshold
        on = a.s[tst] >= lam
        wc.append(float(np.where(on, a.wc_c[tst], a.wc_f[tst]).mean()))
    return {"n_cal": n_cal, "reps": reps, "crc_mean": float(np.mean(wc)), "crc_p95": float(np.quantile(wc, 0.95))}


def run_emg() -> dict:
    res: dict = {}
    old = json.loads((C.REPO / "experiments/2026-11-11-m2-16-online-recal/results/online.json").read_text(encoding="utf-8"))["datasets"]
    for cname in CONFIG["emg_conditions"]:
        ts = time.time()
        cond = C.emg_condition(cname)
        h = len(cond.Bv) // 2
        B1, B2 = cond.Bv[:h], cond.Bv[h:]
        pipe = C.make_pipe(cond)
        pipe.fit(cond.A, B1)
        tab_b = M13.item_table(pipe, B2)
        tab_t = M13.item_table(pipe, cond.test)
        C.save_caches(cond)
        r = {"n_fit_A": len(cond.A), "n_grid_B1": len(B1), "n_cal_B2": len(B2), "n_test": len(cond.test),
             "fit_report": C.clean(pipe.fit_report),
             "offline": offline_rows(tab_b, tab_t, pipe.policy.config.commit_p, cond),
             "online": online_block(tab_b, tab_t)}
        obs = r["offline"]["test"]["CRC (clean cal)"]["wrong_commit"]
        r["exchangeable_reference"] = exch_reference(tab_b, tab_t, obs, CONFIG["exch_reps"], CONFIG["seed"])
        r["within_test_random_splits"] = within_test(tab_t, min(275, len(cond.test) // 2))
        if f"emg-{cname}" in old:
            r["old_reused_data_offline"] = old[f"emg-{cname}"]["drift"]["offline"]
        res[f"emg-{cname}"] = r
        C.dump({"items_cal": tab_b, "items_test": tab_t, "participants_test": cond.test_who}, OUT / f"items-emg-{cname}.json")
        log_row(f"emg-{cname}", r, time.time() - ts)
        C.dump(res, OUT / "clean_drift_emg.json")
    return res


def log_row(key, r, sec) -> None:
    off = r["offline"]["test"]
    on = r["online"]["drift"]["online"]
    C.log(f"{key}: crc lam {C.fmt(C.fnum(r['offline']['thresholds']['CRC (clean cal)']), 4)} -> test wc "
          f"{off['CRC (clean cal)']['wrong_commit']:.4f} (commit {off['CRC (clean cal)']['commit_rate']:.3f}); LTT "
          f"{off['LTT (clean cal)']['wrong_commit']:.4f}; plug-in {off['plug-in gate (fit-A)']['wrong_commit']:.4f}; "
          f"online aci {on['aci@d0']['wrong_commit']:.4f} aci_window {on['aci_window@d0']['wrong_commit']:.4f} "
          f"window {on['window@d0']['wrong_commit']:.4f} decay {on['decay@d0']['wrong_commit']:.4f}; exch p "
          f"{r['exchangeable_reference']['p_value_ge_observed']:.3f} ({sec:.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="b2t,emg")
    a = ap.parse_args()
    if "emg" in a.parts:
        run_emg()
    if "b2t" in a.parts:
        run_b2t()
    C.log("done")


if __name__ == "__main__":
    main()
