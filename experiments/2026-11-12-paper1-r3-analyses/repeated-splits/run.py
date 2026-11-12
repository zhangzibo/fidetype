"""R3 item 1 (+ items 2 and 8 input): repeated deployment splits.

Stats review M1(b), M2, M5; editor M5(b, c). The paper reports one fit /
calibration realisation. Here the full deployment protocol is repeated over
R random splits:

- B2T '25 (ours and the published-sentence gate): every post-implant day's
  trials (main vocabulary, 1,628 trials, 14 days) are permuted at random and
  split day-stratified into fit-A (1/4), clean calibration (1/4) and test
  (1/2). The pipeline (frame + sentence temperatures, conformal sets, guard,
  policy grid) is fitted on fit-A only (``pipe.fit(A, A)``, the paper's
  fit-A recipe; fit-A in file order). Item tables are built for fit-A
  (= reused calibration data), the clean calibration set and the test set.
- sEMG (calib, xsession, xsubject): the fit sentences of every participant
  are permuted and split participant-stratified into fit-A (1/2,
  temperatures + conformal), fit-B1 (1/4, policy grid) and fit-B2 (1/4,
  clean calibration). Test = the fixed composed test sentences (their
  keystrokes come from a separate pool, and the logits from the test
  decoder run). Reused calibration = fit-B1 (the policy-grid data, same
  size as fit-B2).

Stages: ``temps`` (split assignment + fitted frame temperatures),
``warm`` (decode all B2T trials at one snapped temperature), ``tables``
(B2T item tables for a range of splits), ``emg`` (sEMG tables, one
condition), ``analyze`` (all policies, aggregation). Item tables go to the
cache outside the repo (they are derived numbers, but large); the committed
results are the per-split and aggregated metrics.

Run (repo root), see config.json for R:
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/repeated-splits/run.py --stage temps
  ... --stage warm --T 3.81          (one process per temperature in results/splits-b2t.json)
  ... --stage tables --range 0:13    (several processes)
  ... --stage emg --cond xsession
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
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
TAB = K.CACHE3 / "splits"
TAB.mkdir(exist_ok=True)
M13 = C.load_module("m213run", C.REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
ALPHA = CONFIG["alpha"]


# ---------------------------------------------------------------------------
# B2T
# ---------------------------------------------------------------------------

def b2t_setup():
    ctx = C.b2t_ctx()
    router = K.TRouter(ctx.cached[0].fn, "b2t-words")
    ctx.dec.words_fn = router
    trials = ctx.fit + ctx.test
    return ctx, router, trials


def b2t_splits(trials) -> list[dict]:
    by_day: dict = {}
    for i, t in enumerate(trials):
        by_day.setdefault(int(t.post_implant_day), []).append(i)
    rng = np.random.default_rng(CONFIG["seed"])
    out = []
    for r in range(CONFIG["R_b2t"]):
        A, Cc, T = [], [], []
        for d in sorted(by_day):
            idx = np.array(by_day[d])
            p = rng.permutation(idx.size)
            na = int(round(idx.size / 4))
            nc = int(round(idx.size / 4))
            A += idx[p[:na]].tolist()
            Cc += idx[p[na:na + nc]].tolist()
            T += idx[p[na + nc:]].tolist()
        out.append({"r": r, "A": sorted(A), "cal": sorted(Cc), "test": sorted(T)})
    return out


def stage_temps() -> None:
    ctx, _, trials = b2t_setup()
    items = ctx.items(trials)
    sp = b2t_splits(trials)
    for s in sp:
        A = [items[i] for i in s["A"]]
        n_conf = int(round(len(A) * 0.5))
        temp = A[: len(A) - n_conf]
        s["T_fitted"], _ = K.fit_T([it.stream(0) for it in temp], [it.stream_text for it in temp])
        s["T_used"] = K.snap(s["T_fitted"], CONFIG["frame_T_snap_b2t"])
        C.log(f"split {s['r']}: A {len(s['A'])} cal {len(s['cal'])} test {len(s['test'])} T {s['T_fitted']:.4f} -> {s['T_used']:.2f}")
    Ts = sorted({s["T_used"] for s in sp})
    C.dump({"n_trials": len(trials), "days": [int(t.post_implant_day) for t in trials], "splits": sp,
            "distinct_T_used": Ts}, OUT / "splits-b2t.json")
    C.log("distinct T:", Ts)


def stage_warm(T: float) -> None:
    from fidetype.trust.calibration import TemperatureScaler
    ctx, router, trials = b2t_setup()
    items = ctx.items(trials)
    sc = TemperatureScaler()
    sc.temperature = T
    K.TState.used = T
    t0 = time.time()
    for i, it in enumerate(items):
        router(sc.transform_stream(it.stream(0)))
        if (i + 1) % 200 == 0:
            router.save()
            C.log(f"warm T {T:.2f}: {i + 1}/{len(items)} ({time.time() - t0:.0f}s)")
    router.save()
    C.log(f"warm T {T:.2f} done ({time.time() - t0:.0f}s)")


def b2t_tables(r_from: int, r_to: int, stride=(0, 1)) -> None:
    K.install_snap(CONFIG["frame_T_snap_b2t"])
    ctx, router, trials = b2t_setup()
    router.save_ok = False  # the warm stage owns the caches (no concurrent writes)
    items = ctx.items(trials)
    sp = json.loads((OUT / "splits-b2t.json").read_text(encoding="utf-8"))["splits"]
    todo = [s for s in sp if r_from <= s["r"] < r_to and s["r"] % stride[1] == stride[0]]

    def warm_done(T):
        p = OUT / f"run-warm-T{T}.log"
        return p.exists() and "done" in p.read_text(encoding="utf-8")

    def pending():
        return [s for s in todo if not all((TAB / f"b2t-{w}-{s['r']:03d}.json").exists() for w in ("ours", "published"))]

    while pending():
        ready = [s for s in pending() if warm_done(s["T_used"])]
        if not ready:
            time.sleep(30)
            continue
        s = ready[0]
        router.d = {k: v for k, v in router.d.items() if k == f"{s['T_used']:.2f}"}  # keep one temperature in memory
        for which in ("ours", "published"):
            p = TAB / f"b2t-{which}-{s['r']:03d}.json"
            if p.exists():
                continue
            t0 = time.time()
            fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
            A = [items[i] for i in s["A"]]
            Cc = [items[i] for i in s["cal"]]
            T = [items[i] for i in s["test"]]
            pipe = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=ALPHA), {})
            n0 = router.new_count()
            pipe.fit(A, A)
            res = {"r": s["r"], "which": which, "T_fitted": K.TState.fitted, "T_used": K.TState.used,
                   "fit_report": C.clean(pipe.fit_report),
                   "reuse": M13.item_table(pipe, A), "cal": M13.item_table(pipe, Cc), "test": M13.item_table(pipe, T),
                   "test_idx": s["test"]}
            res["new_decodes"] = router.new_count() - n0
            C.dump(res, p)
            C.log(f"b2t-{which} split {s['r']}: T {K.TState.used:.2f} commit_p {pipe.policy.config.commit_p} "
                  f"new decodes {res['new_decodes']} ({time.time() - t0:.0f}s)")


# ---------------------------------------------------------------------------
# sEMG
# ---------------------------------------------------------------------------

def emg_tables(cname: str) -> None:
    K.install_snap(CONFIG["frame_T_snap_emg"])
    cond = C.emg_condition(cname)
    router = K.TRouter(cond.decode.fn, f"emg-{cname}-w{cond.lm_weight}")
    pool = list(cond.A) + list(cond.Bv)
    who = np.asarray(cond.fit_who)
    rng = np.random.default_rng(CONFIG["seed"] + 100)
    for r in range(CONFIG["R_emg"]):
        t0 = time.time()
        A, B1, B2 = [], [], []
        for pid in sorted(set(who.tolist())):
            idx = np.where(who == pid)[0]
            q = rng.permutation(idx)
            na, nb = int(round(idx.size / 2)), int(round(idx.size / 4))
            A += q[:na].tolist()
            B1 += q[na:na + nb].tolist()
            B2 += q[na + nb:].tolist()
        A, B1, B2 = (rng.permutation(np.array(x)).tolist() for x in (A, B1, B2))
        p = TAB / f"emg-{cname}-{r:03d}.json"
        if p.exists():
            continue
        pipe = C.TrustPipeline(router, C.HarnessConfig(seed=C.SEED, user_config=cond.user, **cond.base), {})
        pipe.fit([pool[i] for i in A], [pool[i] for i in B1])
        res = {"r": r, "cond": cname, "T_fitted": K.TState.fitted, "T_used": K.TState.used,
               "fit_report": C.clean(pipe.fit_report), "assign": {"A": A, "B1": B1, "B2": B2},
               "reuse": M13.item_table(pipe, [pool[i] for i in B1]), "cal": M13.item_table(pipe, [pool[i] for i in B2]),
               "test": M13.item_table(pipe, cond.test)}
        router.save()
        C.dump(res, p)
        C.log(f"emg-{cname} split {r}: T {K.TState.used:.2f} commit_p {pipe.policy.config.commit_p} ({time.time() - t0:.0f}s)")
    C.dump({"participants_test": cond.test_who}, OUT / f"emg-{cname}-test-participants.json")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def split_policies(tab: dict, alpha: float = ALPHA) -> dict:
    """All commit thresholds of one split and their test outcomes."""
    re, ca, te = K.arr(tab["reuse"]), K.arr(tab["cal"]), K.arr(tab["test"])
    lp = ca["lam_old"]
    rc, rl = K.crc(ca, alpha), K.ltt(ca, alpha)
    uc, ul = K.crc(re, alpha), K.ltt(re, alpha)
    lam = {"plug-in (fit-A)": lp,
           "CRC pure (clean)": rc.threshold, "CRC max-rule (clean)": max(lp, rc.threshold),
           "LTT pure (clean)": rl.threshold, "LTT max-rule (clean)": max(lp, rl.threshold),
           "CRC pure (reused)": uc.threshold, "CRC max-rule (reused)": max(lp, uc.threshold),
           "LTT pure (reused)": ul.threshold}
    out = {k: K.outcome(te, v) for k, v in lam.items()}
    info = {"lambda": lam,
            "crc_bound_at_crc": rc.bound, "crc_feasible": rc.feasible,
            "cal_bound_at_plugin": K.cal_bound(ca, lp),
            "plugin_certified": K.cal_bound(ca, lp) <= alpha + 1e-12,
            "crc_active": K.crc_active(ca, rc.threshold),
            "crc_differs_from_plugin_on_test": not K.same_decisions(te, rc.threshold, lp),
            "maxrule_changes_plugin_on_test": not K.same_decisions(te, max(lp, rc.threshold), lp),
            "crc_stricter_than_plugin": bool(rc.threshold > lp),
            "ltt_differs_from_plugin_on_test": not K.same_decisions(te, rl.threshold, lp),
            "cal_rate_at_plugin": K.outcome(ca, lp)["wrong_commit"],
            "reuse_rate_at_plugin": K.outcome(re, lp)["wrong_commit"],
            "n_cal": int(ca["s"].size), "n_reuse": int(re["s"].size), "n_test": int(te["s"].size),
            "eligible_cal": float(np.isfinite(ca["s"]).mean())}
    return {"test": out, "info": info}


def selective(tab: dict, betas=(0.05, 0.10, 0.20), alpha: float = ALPHA) -> dict:
    ca, te = K.arr(tab["cal"]), K.arr(tab["test"])
    lp = ca["lam_old"]
    rc = K.crc(ca, alpha)
    lmax = max(lp, rc.threshold)
    out = {}
    for b in betas:
        sg = K.sgr(ca["s"], ca["c"], b, C.DELTA)
        ls = K.ltt_selective(ca["s"], ca["c"], b, C.DELTA)
        out[f"{b:.2f}"] = {
            "SGR": {**K.outcome(te, sg["threshold"]), "threshold": sg["threshold"], "bound": sg["bound"]},
            "LTT-sel": {**K.outcome(te, ls["threshold"]), "threshold": ls["threshold"]},
            "joint (SGR + CRC max-rule)": {**K.outcome(te, max(sg["threshold"], lmax)), "threshold": max(sg["threshold"], lmax)},
        }
    return out


POL = ("plug-in (fit-A)", "CRC pure (clean)", "CRC max-rule (clean)", "LTT pure (clean)", "LTT max-rule (clean)",
       "CRC pure (reused)", "CRC max-rule (reused)", "LTT pure (reused)")
MET = ("wrong_commit", "commit_rate", "error_among_commits", "ewpm")


def aggregate(rows: list[dict], alpha: float = ALPHA) -> dict:
    agg: dict = {"R": len(rows), "policies": {}, "binding": {}, "reuse_vs_clean": {}}
    for p in POL:
        d = {m: K.summ([r["test"][p][m] for r in rows]) for m in MET}
        wc = np.array([r["test"][p]["wrong_commit"] for r in rows])
        d["share_wrong_commit_gt_alpha"] = float(np.mean(wc > alpha + 1e-12))
        d["share_no_commit"] = float(np.mean([r["test"][p]["n_commit"] == 0 for r in rows]))
        d["error_among_commits_pooled"] = (float(sum(r["test"][p]["n_commit_wrong"] for r in rows) /
                                           max(1, sum(r["test"][p]["n_commit"] for r in rows))))
        # Monte-Carlo standard error of the mean over splits (splits share one finite data set: not a CI for new data)
        d["wrong_commit_mc_se"] = float(wc.std(ddof=1) / math.sqrt(wc.size)) if wc.size > 1 else None
        # LTT-style check: under a valid (1 - delta) bound the share above alpha should be <= delta = 0.1
        from scipy.stats import binomtest
        k = int((wc > alpha + 1e-12).sum())
        d["binom_test_share_gt_alpha_vs_0.1"] = float(binomtest(k, wc.size, 0.1, alternative="greater").pvalue)
        agg["policies"][p] = d
    for f in ("plugin_certified", "crc_active", "crc_differs_from_plugin_on_test", "maxrule_changes_plugin_on_test",
              "crc_stricter_than_plugin", "ltt_differs_from_plugin_on_test", "crc_feasible"):
        agg["binding"][f] = float(np.mean([bool(r["info"][f]) for r in rows]))
    agg["binding"]["crc_bound_at_crc"] = K.summ([r["info"]["crc_bound_at_crc"] for r in rows])
    agg["binding"]["cal_bound_at_plugin"] = K.summ([r["info"]["cal_bound_at_plugin"] for r in rows])
    agg["binding"]["cal_rate_at_plugin"] = K.summ([r["info"]["cal_rate_at_plugin"] for r in rows])
    agg["binding"]["reuse_rate_at_plugin"] = K.summ([r["info"]["reuse_rate_at_plugin"] for r in rows])
    agg["binding"]["plugin_lambda"] = K.summ([r["info"]["lambda"]["plug-in (fit-A)"] for r in rows])
    agg["binding"]["crc_lambda"] = K.summ([C.fnum(r["info"]["lambda"]["CRC pure (clean)"]) for r in rows])
    # Paired reuse vs clean (same split, same pipeline)
    from scipy.stats import wilcoxon
    for a, b in (("CRC pure (reused)", "CRC pure (clean)"), ("CRC max-rule (reused)", "CRC max-rule (clean)"),
                 ("LTT pure (reused)", "LTT pure (clean)")):
        d = np.array([r["test"][a]["wrong_commit"] - r["test"][b]["wrong_commit"] for r in rows])
        sd = float(d.std(ddof=1)) if d.size > 1 else 0.0
        try:
            pw = float(wilcoxon(d, zero_method="wilcox").pvalue) if np.any(d != 0) else 1.0
        except ValueError:
            pw = 1.0
        agg["reuse_vs_clean"][f"{a} - {b}"] = {
            **K.summ(d), "share_reused_higher": float(np.mean(d > 1e-12)), "share_equal": float(np.mean(np.abs(d) <= 1e-12)),
            "wilcoxon_p": pw, "sign_test": K.sign_test(d),
            # smallest mean paired difference detectable at 80 % power, two-sided 5 %, given this spread (Monte-Carlo)
            "mde80_mean_paired": 2.80 * sd / math.sqrt(d.size) if d.size > 1 else None}
    # Power of a single deployment: smallest shift of the test rate that one split detects with 80 % power at one-sided 5 %
    sd_clean = agg["policies"]["CRC pure (clean)"]["wrong_commit"]["sd"] or 0.0
    agg["power"] = {"single_split_mde80_one_sided_5pct": (1.645 + 0.842) * sd_clean,
                    "sd_clean_crc_test_rate": sd_clean,
                    "guarantee_test_mean_vs_alpha_mde80": (1.645 + 0.842) * sd_clean / math.sqrt(max(1, len(rows))),
                    "note": "Splits re-use one finite data set: the spread is the split-to-split (fit + calibration + "
                            "test assignment) variation for this participant, not sampling of new data."}
    return agg


def agg_selective(rows: list[dict]) -> dict:
    out: dict = {}
    for b in rows[0]["selective"]:
        out[b] = {}
        for meth in rows[0]["selective"][b]:
            vals = [r["selective"][b][meth] for r in rows]
            d = {m: K.summ([v[m] for v in vals]) for m in MET}
            d["share_no_commit"] = float(np.mean([v["n_commit"] == 0 for v in vals]))
            nc = sum(v["n_commit"] for v in vals)
            d["error_among_commits_pooled"] = float(sum(v["n_commit_wrong"] for v in vals) / nc) if nc else None
            d["share_eac_gt_beta"] = float(np.mean([v["n_commit"] > 0 and v["error_among_commits"] > float(b) + 1e-12 for v in vals]))
            out[b][meth] = d
    return out


def per_day(rows: list[dict], days_all: list[int], sp: list[dict]) -> dict:
    """Per-day test wrong-commit / commit rate of the plug-in and CRC max-rule over the splits (item 8)."""
    out: dict = {}
    for p in ("plug-in (fit-A)", "CRC max-rule (clean)"):
        acc: dict = {}
        for r, s in zip(rows, sp):
            te = r["_te"]
            lam = r["info"]["lambda"][p]
            dd = np.array([days_all[i] for i in s["test"]])
            for d in np.unique(dd):
                o = K.outcome(te, lam, rows=np.where(dd == d)[0])
                acc.setdefault(int(d), []).append((o["wrong_commit"], o["commit_rate"], o["ewpm"]))
        out[p] = {str(d): {"wrong_commit": K.summ([x[0] for x in v]), "commit_rate": K.summ([x[1] for x in v]),
                           "ewpm": K.summ([x[2] for x in v]), "n_test_mean": None} for d, v in sorted(acc.items())}
    return out


def main_per_day() -> dict:
    """Per-day results of the paper's main (full-fit) trust row and always offer, from the committed arrays."""
    out = {}
    for which in ("ours", "published"):
        a = json.loads((K.R1 / f"baselines/results/arrays-b2t-{which}.json").read_text(encoding="utf-8"))
        cl = np.asarray(a["cluster"])
        items = json.loads((K.R1 / f"clean-drift/results/items-{which}-alternate.json").read_text(encoding="utf-8"))
        days = np.asarray(items["days_test"])
        res = {}
        for p in ("trust", "never_commit", "always_commit"):
            arrs = {k: np.asarray(v, float) for k, v in a["arrays"][p].items()}
            rows = {}
            for d in np.unique(days):
                m = days == d
                rows[str(int(d))] = {**C.metrics({k: v[m] for k, v in arrs.items()}), "n": int(m.sum())}
            res[p] = rows
        out[f"b2t-{which}"] = res
        assert len(np.unique(cl)) == len(np.unique(days))
    return out


def stage_analyze() -> None:
    res: dict = {"config": CONFIG, "conditions": {}}
    spb = json.loads((OUT / "splits-b2t.json").read_text(encoding="utf-8"))
    per_split_out: dict = {}
    for name in ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession", "emg-xsubject"):
        files = sorted(TAB.glob(f"{name}-[0-9][0-9][0-9].json"))
        if not files:
            C.log(f"{name}: no tables")
            continue
        rows = []
        for f in files:
            tab = json.loads(f.read_text(encoding="utf-8"))
            r = split_policies(tab)
            r["selective"] = selective(tab)
            r["r"] = tab["r"]
            r["T_used"], r["T_fitted"] = tab["T_used"], tab["T_fitted"]
            r["policy_config"] = tab["fit_report"].get("policy_config")
            if name.startswith("b2t"):
                r["_te"] = K.arr(tab["test"])
            rows.append(r)
        cres = {"aggregate": aggregate(rows), "selective": agg_selective(rows),
                "T_used": K.summ([r["T_used"] for r in rows]), "T_fitted": K.summ([r["T_fitted"] for r in rows]),
                "max_abs_snap": float(max(abs(r["T_used"] - r["T_fitted"]) for r in rows))}
        if name.startswith("b2t"):
            sp = [spb["splits"][r["r"]] for r in rows]
            cres["per_day"] = per_day(rows, spb["days"], sp)
        res["conditions"][name] = cres
        per_split_out[name] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
        a = cres["aggregate"]["policies"]
        C.log(f"{name} R={len(rows)}: " + "; ".join(
            f"{p}: wc {a[p]['wrong_commit']['mean']:.4f} [{a[p]['wrong_commit']['p05']:.4f}, {a[p]['wrong_commit']['p95']:.4f}] "
            f">a {a[p]['share_wrong_commit_gt_alpha']:.2f}" for p in POL[:5]))
    res["main_pipeline_per_day"] = main_per_day()
    C.dump(res, OUT / "repeated_splits.json")
    C.dump(per_split_out, OUT / "per_split.json")
    write_tables(res)


def f(x, nd=4):
    return C.fmt(C.fnum(x) if x is not None else None, nd)


def write_tables(res: dict) -> None:
    L = ["# Repeated deployment splits: tables", "",
         f"R = {res['config']['R_b2t']} (B2T) / {res['config']['R_emg']} (sEMG) random splits; alpha = {ALPHA}; delta = 0.1. "
         "Mean [5th, 95th percentile] over splits of the test-set value. '>α' = share of splits with test wrong-commit > α. "
         "Splits re-use one finite data set: the spread is split-to-split variation, not a CI for new data.", ""]
    for name, c in res["conditions"].items():
        a = c["aggregate"]
        L += [f"## {name} (R = {a['R']}; frame T used {c['T_used']['mean']:.3f}, max snap {c['max_abs_snap']:.4f})", "",
              "| policy | wrong-commit mean [p05, p95] | >α | commit rate mean [p05, p95] | error among commits (pooled) | no-commit splits | eWPM mean [p05, p95] |",
              "|---|---|---|---|---|---|---|"]
        for p in POL:
            d = a["policies"][p]
            L.append(f"| {p} | {f(d['wrong_commit']['mean'])} [{f(d['wrong_commit']['p05'])}, {f(d['wrong_commit']['p95'])}] | "
                     f"{d['share_wrong_commit_gt_alpha']:.2f} | {f(d['commit_rate']['mean'], 3)} [{f(d['commit_rate']['p05'], 3)}, "
                     f"{f(d['commit_rate']['p95'], 3)}] | {f(d['error_among_commits_pooled'], 3)} | {d['share_no_commit']:.2f} | "
                     f"{f(d['ewpm']['mean'], 2)} [{f(d['ewpm']['p05'], 2)}, {f(d['ewpm']['p95'], 2)}] |")
        b = a["binding"]
        L += ["", f"Binding: CRC constraint active (excludes an eligible calibration item) in {b['crc_active']:.2f} of splits; "
              f"CRC stricter than plug-in {b['crc_stricter_than_plugin']:.2f}; max-rule changes a test decision {b['maxrule_changes_plugin_on_test']:.2f}; "
              f"pure CRC differs from plug-in on test {b['crc_differs_from_plugin_on_test']:.2f}; plug-in certified by the calibration bound "
              f"(n R̂(λ_plug-in) + 1)/(n + 1) ≤ α in {b['plugin_certified']:.2f}. "
              f"CRC bound at λ̂: mean {f(b['crc_bound_at_crc']['mean'])}; calibration bound at plug-in λ: mean {f(b['cal_bound_at_plugin']['mean'])} "
              f"[{f(b['cal_bound_at_plugin']['p05'])}, {f(b['cal_bound_at_plugin']['p95'])}]. Plug-in λ mean {f(b['plugin_lambda']['mean'], 3)} "
              f"[{f(b['plugin_lambda']['p05'], 2)}, {f(b['plugin_lambda']['p95'], 2)}].", ""]
        L += ["Reused vs clean calibration (paired by split; reused − clean test wrong-commit):", "",
              "| pair | mean diff [p05, p95] | reused higher | equal | Wilcoxon p | sign test (+/−) p | MDE80 (mean) |", "|---|---|---|---|---|---|---|"]
        for k, d in a["reuse_vs_clean"].items():
            st = d["sign_test"]
            L.append(f"| {k} | {f(d['mean'])} [{f(d['p05'])}, {f(d['p95'])}] | {d['share_reused_higher']:.2f} | {d['share_equal']:.2f} | "
                     f"{d['wilcoxon_p']:.3g} | {st['positive']}/{st['negative']} p {st['p_two_sided']:.3g} | {f(d['mde80_mean_paired'])} |")
        pw = a["power"]
        L += ["", f"Power: SD of the clean-CRC test rate over splits {f(pw['sd_clean_crc_test_rate'])}; one deployment detects a shift of "
              f"{f(pw['single_split_mde80_one_sided_5pct'])} with 80 % power (one-sided 5 %); the mean over R splits resolves "
              f"{f(pw['guarantee_test_mean_vs_alpha_mde80'])} (Monte-Carlo).", ""]
        L += ["Selective-risk controllers (target error among commits β; δ = 0.1; clean calibration):", "",
              "| β | method | commit rate mean [p05, p95] | error among commits pooled | share EAC > β | no-commit splits | wrong-commit mean | eWPM mean |",
              "|---|---|---|---|---|---|---|---|"]
        for bb, ms in c["selective"].items():
            for m, d in ms.items():
                L.append(f"| {bb} | {m} | {f(d['commit_rate']['mean'], 3)} [{f(d['commit_rate']['p05'], 3)}, {f(d['commit_rate']['p95'], 3)}] | "
                         f"{f(d['error_among_commits_pooled'], 3)} | {d['share_eac_gt_beta']:.2f} | {d['share_no_commit']:.2f} | "
                         f"{f(d['wrong_commit']['mean'])} | {f(d['ewpm']['mean'], 2)} |")
        L.append("")
        if "per_day" in c:
            L += ["Per-day test results over splits (mean [p05, p95]):", "",
                  "| day | plug-in wrong-commit | plug-in commit rate | CRC max-rule wrong-commit | CRC max-rule commit rate |", "|---|---|---|---|---|"]
            pd_, cm = c["per_day"]["plug-in (fit-A)"], c["per_day"]["CRC max-rule (clean)"]
            for d in pd_:
                L.append(f"| {d} | {f(pd_[d]['wrong_commit']['mean'])} [{f(pd_[d]['wrong_commit']['p05'])}, {f(pd_[d]['wrong_commit']['p95'])}] | "
                         f"{f(pd_[d]['commit_rate']['mean'], 3)} | {f(cm[d]['wrong_commit']['mean'])} [{f(cm[d]['wrong_commit']['p05'])}, "
                         f"{f(cm[d]['wrong_commit']['p95'])}] | {f(cm[d]['commit_rate']['mean'], 3)} |")
            L.append("")
    L += ["## Main (full-fit) pipeline per day (committed arrays; the paper's trust row)", ""]
    for name, c in res["main_pipeline_per_day"].items():
        L += [f"### {name}", "", "| day | n | trust wrong-commit | trust commit rate | trust eWPM | always offer eWPM | trust − always offer eWPM |", "|---|---|---|---|---|---|---|"]
        for d, v in c["trust"].items():
            nv = c["never_commit"][d]
            L.append(f"| {d} | {v['n']} | {v['wrong_commit']:.4f} | {v['commit_rate']:.3f} | {v['ewpm']:.2f} | {nv['ewpm']:.2f} | {v['ewpm'] - nv['ewpm']:+.2f} |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--T", type=float)
    ap.add_argument("--range", default="0:1000")
    ap.add_argument("--cond")
    ap.add_argument("--stride", default="0/1")
    a = ap.parse_args()
    C.Log.path = OUT / f"run-{a.stage}{'-' + a.cond if a.cond else ''}{'-' + a.stride.replace('/', 'of') if a.stage == 'tables' else ''}{'-T' + str(a.T) if a.T else ''}.log"
    if a.stage == "temps":
        stage_temps()
    elif a.stage == "warm":
        stage_warm(a.T)
    elif a.stage == "tables":
        lo, hi = (int(x) for x in a.range.split(":"))
        w, n = (int(x) for x in a.stride.split("/"))
        b2t_tables(lo, hi, (w, n))
    elif a.stage == "emg":
        emg_tables(a.cond)
    elif a.stage == "analyze":
        stage_analyze()
    C.log("done", a.stage)


if __name__ == "__main__":
    main()
