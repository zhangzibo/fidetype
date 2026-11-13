"""Track A item 2: per-session (per-day) risk control.

Paper 1 (R4 per-day analysis): the LTT max rule bounds the wrong-commit
rate of the calibration *mixture* of days, not of each day. On the
published gate, day 34 ran at about 0.10 (2 alpha) over random re-splits.
This script evaluates per-session remedies (``fidetype.trust.session_risk``)
on the cached Paper 1 item tables (no new decodes, CPU only):

- ``global``: the paper's LTT max rule (baseline).
- ``mondrian-*``: per-day LTT on the day's calibration items; fallback
  never / global / mixture for days with < 45 items (paper split design).
- ``block-ltt``, ``block-test``, ``eb``: session-start block of k items.
  Mode W: the block is an offer-only warm-up (threshold +inf; labels from
  the OFFER picks or a copy-typing block). Mode F: the block runs at the
  global threshold and its labels come from the user's feedback.
- ``monitor``: anytime-valid e-process alarm (gamma = 0.1) -> offer-only.
- ``aci``: ``OnlineCommitRiskControl(method="aci")`` per session, floor =
  the global threshold (can only get stricter).

Settings: B2T '25 random re-splits (R = 200, both decoders, guard on),
B2T forward chain (V1, V3), sEMG random re-splits (R = 50). See
config.json for the session definitions. Fixed seeds.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-13-a2-per-session-risk/run.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments/2026-11-12-paper1-r4-analyses"))
import common4 as Q  # noqa: E402

from fidetype.trust.online_risk import OnlineCommitRiskControl  # noqa: E402
from fidetype.trust.risk_control import ltt_threshold  # noqa: E402
from fidetype.trust.session_risk import (  # noqa: E402
    SessionRiskMonitor,
    binomial_upper_pvalue,
    block_ltt,
    block_test,
    eb_session_threshold,
    min_ltt_items,
    mondrian_ltt,
)

K = Q.K
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
A, D, G = CFG["alpha"], CFG["delta"], CFG["gamma"]
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
FC = Q.CACHE4 / "forward"
INF = math.inf


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------------------
# Method engine: a threshold per session item
# ---------------------------------------------------------------------------

def ltt_max(base: float, a: dict) -> float:
    if a["s"].size == 0:
        return INF
    return max(base, ltt_threshold(a["s"], a["c"], A, D, a["f"]).threshold)


def losses_at(a: dict, lam: float) -> np.ndarray:
    return np.where(a["s"] >= lam, np.maximum(a["c"], a["f"]), a["f"])


def method_specs() -> list[tuple[str, str, int, str]]:
    """(name, kind, k, mode)."""
    sp = [("global", "global", 0, "-"), ("monitor", "monitor", 0, "-"), ("aci", "aci", 0, "-"), ("eb k=0", "eb", 0, "-")]
    for k in CFG["block_k"]:
        for mode in ("W", "F"):
            sp += [(f"block-ltt k={k} {mode}", "block-ltt", k, mode), (f"block-test k={k} {mode}", "block-test", k, mode)]
    for k in CFG["eb_k"]:
        if k:
            for mode in ("W", "F"):
                sp.append((f"eb k={k} {mode}", "eb", k, mode))
    sp.append(("block-test k=20 F + monitor", "block-test+monitor", 20, "F"))
    for k in (45, 60):
        sp.append((f"block-ltt k={k} W + monitor", "block-ltt+monitor", k, "W"))
    # Sensitivity added after the R = 3 smoke run: weaker prior (kappa <= eb_kappa_max_sens)
    for k in CFG["eb_sens_k"]:
        sp.append((f"eb k={k} F kappa<={CFG['eb_kappa_max_sens']:g}", "eb-sens", k, "F"))
    return sp


SPECS = method_specs()


def run_method(kind: str, k: int, mode: str, sess: dict, lam_g: float, eb_ref=None, eb_prior=None) -> tuple[np.ndarray, dict]:
    n = sess["s"].size
    lam = np.full(n, lam_g, float)
    info: dict = {}
    if kind == "global":
        return lam, info
    if kind in ("monitor", "block-test+monitor"):
        start = 0
        if kind == "block-test+monitor":
            kb = min(k, n)
            bt = block_test(sess["s"][:kb], sess["c"][:kb], lam_g, A, G, sess["f"][:kb])
            if bt.reject:
                lam[kb:] = INF
                info["alarm_at"] = kb
                return lam, info
            start = kb
        mon = SessionRiskMonitor(A, G, CFG["monitor_alternatives"], CFG["monitor_max_bet_fraction"])
        L = losses_at(sess, lam_g)
        for t in range(start, n):
            if mon.update(float(L[t])):
                lam[t + 1:] = INF
                info["alarm_at"] = t + 1
                break
        return lam, info
    if kind == "aci":
        if not math.isfinite(lam_g):
            return lam, info
        ctl = OnlineCommitRiskControl(alpha=A, method="aci", eta=CFG["aci_eta"], lam_init=lam_g, lam_min=lam_g)
        for t in range(n):
            tk = ctl.step(float(sess["s"][t]), float(sess["c"][t]), float(sess["f"][t]))
            lam[t] = tk.threshold
        info["aci_certificate"] = ctl.report().get("certificate")
        return lam, info
    kb = min(k, n)
    blk = K.take(sess, np.arange(kb))
    if mode == "W":
        lam[:kb] = INF
    if kind == "block-ltt+monitor":
        thr = block_ltt(blk["s"], blk["c"], lam_g, A, D, blk["f"]).threshold
        lam[kb:] = thr
        info["session_threshold"] = thr
        if math.isfinite(thr):
            mon = SessionRiskMonitor(A, G, CFG["monitor_alternatives"], CFG["monitor_max_bet_fraction"])
            L = losses_at(sess, thr)
            for t in range(kb, n):
                if mon.update(float(L[t])):
                    lam[t + 1:] = INF
                    info["alarm_at"] = t + 1
                    break
        return lam, info
    if kind == "block-ltt":
        thr = block_ltt(blk["s"], blk["c"], lam_g, A, D, blk["f"]).threshold
    elif kind == "block-test":
        thr = INF if block_test(blk["s"], blk["c"], lam_g, A, G, blk["f"]).reject else lam_g
    elif kind in ("eb", "eb-sens"):
        kw = dict(kappa_min=CFG["eb_kappa_min"], kappa_max=CFG["eb_kappa_max" if kind == "eb" else "eb_kappa_max_sens"])
        if eb_ref is not None:
            thr = eb_session_threshold(blk["s"], blk["c"], reference=eb_ref, base_threshold=lam_g, alpha=A, delta=D,
                                       block_fallback_losses=blk["f"], **kw).threshold
        else:
            thr = eb_session_threshold(blk["s"], blk["c"], prior=eb_prior, base_threshold=lam_g, alpha=A, delta=D,
                                       block_fallback_losses=blk["f"]).threshold
    else:
        raise ValueError(kind)
    lam[kb:] = thr
    info["session_threshold"] = thr
    return lam, info


def evaluate(sess: dict, lam: np.ndarray, k: int, mode: str) -> dict:
    on = sess["s"] >= lam
    wc = np.where(on, sess["wc_c"], sess["wc_f"])
    w = np.where(on, sess["words_c"], sess["words_f"])
    t = np.where(on, sess["time_c"], sess["time_f"])
    n = int(on.size)
    kb = min(k, n) if mode in ("W", "F") else 0
    out = {"n": n, "wrong": float(wc.sum()), "commits": int(on.sum()), "words": float(w.sum()), "time": float(t.sum()),
           "n_post": n - kb, "wrong_post": float(wc[kb:].sum()), "commits_post": int(on[kb:].sum())}
    if mode == "W" and kb:
        # copy-typing accounting: block items give no user text; time = one attempt (time_c)
        out["words_copy"] = float(w[kb:].sum())
        out["time_copy"] = float(sess["time_c"][:kb].sum() + t[kb:].sum())
    else:
        out["words_copy"], out["time_copy"] = out["words"], out["time"]
    return out


def all_methods(sess: dict, lam_g: float, eb_ref=None, eb_prior=None, extra: dict | None = None) -> dict:
    res = {}
    for name, kind, k, mode in SPECS:
        lam, info = run_method(kind, k, mode, sess, lam_g, eb_ref, eb_prior)
        r = evaluate(sess, lam, k, mode)
        r.update(info)
        res[name] = r
    for name, (lam_val, sub) in (extra or {}).items():
        b = K.take(sess, sub) if sub is not None else sess
        res[name] = evaluate(b, np.full(b["s"].size, lam_val), 0, "-")
    return res


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def agg_repeated(per: dict) -> dict:
    """per[method][group] = list of per-split dicts -> pooled stats."""
    out = {}
    for m, gd in per.items():
        out[m] = {}
        for g, rows in gd.items():
            n = sum(r["n"] for r in rows)
            wr = sum(r["wrong"] for r in rows)
            rates = np.array([r["wrong"] / r["n"] for r in rows if r["n"]])
            npost = sum(r["n_post"] for r in rows)
            alarms = [r["alarm_at"] for r in rows if r.get("alarm_at") is not None]
            out[m][g] = {
                "R": len(rows), "n_mean": n / len(rows), "pooled": wr / n if n else None,
                "mean": float(rates.mean()) if rates.size else None,
                "p05": float(np.quantile(rates, 0.05)) if rates.size else None,
                "p95": float(np.quantile(rates, 0.95)) if rates.size else None,
                "share_gt_alpha": float(np.mean(rates > A + 1e-12)) if rates.size else None,
                "commit_rate": sum(r["commits"] for r in rows) / n if n else None,
                "ewpm": 60.0 * sum(r["words"] for r in rows) / sum(r["time"] for r in rows),
                "ewpm_copy": 60.0 * sum(r["words_copy"] for r in rows) / sum(r["time_copy"] for r in rows),
                "pooled_post": (sum(r["wrong_post"] for r in rows) / npost) if npost else None,
                "commit_rate_post": (sum(r["commits_post"] for r in rows) / npost) if npost else None,
                "alarm_share": len(alarms) / len(rows),
                "alarm_delay_median": float(np.median(alarms)) if alarms else None,
                "alarm_delay_p25_p75": [float(np.quantile(alarms, 0.25)), float(np.quantile(alarms, 0.75))] if alarms else None,
            }
    return out


def summary_over_groups(agg: dict, bad: str | None = None) -> dict:
    out = {}
    for m, gd in agg.items():
        pooled = {g: v["pooled"] for g, v in gd.items() if v["pooled"] is not None}
        above = [g for g, p in pooled.items() if p > A + 1e-12]
        good = [g for g in gd if g != bad]
        out[m] = {"groups": len(pooled), "groups_above_alpha": len(above), "which_above": above,
                  "max_group_pooled": max(pooled.values()) if pooled else None,
                  "mean_commit_rate": float(np.mean([gd[g]["commit_rate"] for g in gd])),
                  "mean_ewpm": float(np.mean([gd[g]["ewpm"] for g in gd])),
                  "mean_ewpm_copy": float(np.mean([gd[g]["ewpm_copy"] for g in gd])),
                  "false_alarm_share_good_groups": float(np.mean([gd[g]["alarm_share"] for g in good])) if good else None}
    return out


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def rs_b2t(cond: str) -> dict:
    R = CFG["R_b2t"]
    per: dict = {}
    mon_per: dict = {}
    sp200 = Q.splits200()
    for r in range(R):
        sp = Q.load_split(cond, r)
        if sp is None:
            log(f"{cond}: split {r} missing")
            continue
        ca, te = sp["cal"], sp["test"]
        cal_idx, test_idx = np.array(sp200[r]["cal"]), np.array(sp200[r]["test"])
        cg, tg = sp["cal_group"], sp["test_group"]
        plug = ca["lam_old"]
        lam_paper = ltt_max(plug, ca)
        mond = {fb: mondrian_ltt(ca["s"], ca["c"], cg.tolist(), A, D, ca["f"], base_threshold=plug, fallback=fb)
                for fb in ("never", "global", "mixture")}
        for d in np.unique(tg):
            ci, ti = np.where(cg == d)[0], np.where(tg == d)[0]
            lam_g = ltt_max(plug, K.take(ca, np.where(cg != d)[0]))
            refs = [(K.take(ca, np.where(cg == e)[0])) for e in np.unique(cg) if e != d]
            refs = [(x["s"], x["c"], x["f"]) for x in refs]
            # session = calibration + test items of day d, in file order
            parts = [K.take(ca, ci), K.take(te, ti)]
            gidx = np.concatenate([cal_idx[ci], test_idx[ti]])
            order = np.argsort(gidx, kind="stable")
            sess = {kk: np.concatenate([parts[0][kk], parts[1][kk]])[order] for kk in parts[0] if isinstance(parts[0][kk], np.ndarray)}
            sess["c"], sess["f"] = sess["loss_c"], sess["loss_f"]
            res = all_methods(sess, lam_g, eb_ref=refs)
            # paper reproduction and Mondrian: paper split design (cal incl. day d; test items of day d only)
            tb = K.take(te, ti)
            res["paper LTT max (test items)"] = evaluate(tb, np.full(ti.size, lam_paper), 0, "-")
            res["global LOO (test items)"] = evaluate(tb, np.full(ti.size, lam_g), 0, "-")
            for fb, mt in mond.items():
                gt = mt.get(d)
                lam_d = gt.threshold if gt is not None else (INF if fb == "never" else lam_paper)
                o = evaluate(tb, np.full(ti.size, lam_d), 0, "-")
                o["mondrian_source"] = gt.source if gt is not None else "no-cal-items"
                res[f"mondrian-{fb} (test items)"] = o
            for m, v in res.items():
                per.setdefault(m, {}).setdefault(str(int(d)), []).append(v)
            mon_per.setdefault(str(int(d)), []).append({"n_cal_day": int(ci.size), "lam_g": lam_g, "lam_paper": lam_paper})
        if r % 25 == 0:
            log(f"{cond}: split {r} done")
    agg = agg_repeated(per)
    mond_feas = {d: float(np.mean([x["n_cal_day"] >= min_ltt_items(A, D) for x in v])) for d, v in mon_per.items()}
    return {"R": R, "per_day": agg, "summary": summary_over_groups(agg, bad="34"), "mondrian_share_n_ge_45": mond_feas,
            "lam_g_mean": {d: float(np.mean([x["lam_g"] for x in v if math.isfinite(x["lam_g"])] or [np.nan])) for d, v in mon_per.items()}}


def rs_emg(cond: str) -> dict:
    R = CFG["R_emg"]
    per: dict = {}
    for r in range(R):
        sp = Q.load_split(cond, r)
        if sp is None:
            continue
        ca, te, tg = sp["cal"], sp["test"], sp["test_group"]
        lam_g = ltt_max(ca["lam_old"], ca)
        groups = list(dict.fromkeys(tg.tolist()))
        for p in groups:
            ti = np.where(tg == p)[0]
            sess = K.take(te, ti)
            refs = [K.take(te, np.where(tg == q)[0]) for q in groups if q != p]
            refs = [(x["s"], x["c"], x["f"]) for x in refs]
            res = all_methods(sess, lam_g, eb_ref=refs)
            for m, v in res.items():
                per.setdefault(m, {}).setdefault(p, []).append(v)
    agg = agg_repeated(per)
    return {"R": R, "per_participant": agg, "summary": summary_over_groups(agg)}


def fc_load(which: str, j: int):
    p = FC / f"b2t-{which}-g1-p{j:02d}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d if d.get("ok") else None


def fc_b2t(which: str) -> dict:
    days = sorted(set(Q.DAYS_ALL))
    nd = len(days)
    P = {j: fc_load(which, j) for j in range(nd - 1)}
    out = {}
    kap = CFG["fc_prior_kappa"]
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID, _risk_curve
    for design in ("V1", "V3"):
        folds = {}
        for k in range(1, nd):
            j = k - 2 if design == "V1" else k - 1
            if j < 0 or P.get(j) is None:
                continue
            sess = K.arr(P[j][str(days[k])])
            if design == "V1":
                ca = K.arr(P[j][str(days[k - 1])])
                lam_g = ltt_max(ca["lam_old"], ca)
                lams = np.array(sorted(DEFAULT_LTT_GRID))
                rk = _risk_curve(ca["s"], np.maximum(ca["c"], ca["f"]), ca["f"], lams)
                prior = {float(l): (max(1e-3, float(m)) * kap, (1 - max(1e-3, float(m))) * kap) for l, m in zip(lams, rk)}
            else:
                lam_g = sess["lam_old"]
                prior = (A * kap, (1 - A) * kap)
            res = all_methods(sess, lam_g, eb_prior=prior)
            for m, v in res.items():
                k_ = int(round(v["wrong"]))
                v["wrong_cp95"] = Q.cp(k_, v["n"])
                v["rate"] = v["wrong"] / v["n"]
            folds[str(days[k])] = {"prefix": j, "n": int(sess["s"].size), "lam_g": lam_g, "methods": res}
        out[design] = {"days": folds, "summary": fc_summary(folds)}
    return out


def fc_summary(folds: dict) -> dict:
    rng = np.random.default_rng(CFG["seed"])
    dks = list(folds)
    out = {}
    base_ewpm = np.array([60 * folds[d]["methods"]["global"]["words"] / folds[d]["methods"]["global"]["time"] for d in dks])
    idx = rng.integers(0, len(dks), size=(CFG["bootstrap_B"], len(dks)))
    for m in folds[dks[0]]["methods"]:
        rows = [folds[d]["methods"][m] for d in dks]
        n = sum(r["n"] for r in rows)
        wr = sum(r["wrong"] for r in rows)
        above = [d for d, r in zip(dks, rows) if r["wrong"] / r["n"] > A + 1e-12]
        sig = [d for d, r in zip(dks, rows) if (r["wrong_cp95"][0] or 0) > A]
        ew = np.array([60 * r["words"] / r["time"] for r in rows])
        diff = ew - base_ewpm
        bs = diff[idx].mean(axis=1)
        out[m] = {"n_days": len(rows), "days_above_alpha": len(above), "which_above": above, "days_cp_lower_above_alpha": sig,
                  "pooled": wr / n, "pooled_cp95": Q.cp(int(round(wr)), n), "commit_rate": sum(r["commits"] for r in rows) / n,
                  "mean_day_ewpm": float(ew.mean()), "ewpm_diff_vs_global": float(diff.mean()),
                  "ewpm_diff_boot95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))],
                  "max_day_rate": max(r["wrong"] / r["n"] for r in rows),
                  "alarms": [d for d, r in zip(dks, rows) if r.get("alarm_at") is not None]}
    return out


# ---------------------------------------------------------------------------
# Analytic / simulated power
# ---------------------------------------------------------------------------

def power_tables() -> dict:
    rng = np.random.default_rng(CFG["seed"])
    T, reps = CFG["power_sim_T"], CFG["power_sim_reps"]
    mon = {}
    for rho in CFG["power_rhos"]:
        x = rng.uniform(size=(reps, T)) < rho
        bets = SessionRiskMonitor(A, G, CFG["monitor_alternatives"], CFG["monitor_max_bet_fraction"]).bets
        lw = np.zeros((reps, len(bets)))
        first = np.full(reps, -1)
        for t in range(T):
            lw += np.log1p(np.outer(x[:, t] - A, bets))
            m = lw.max(axis=1)
            e = np.exp(m) * np.mean(np.exp(lw - m[:, None]), axis=1)
            hit = (e >= 1 / G) & (first < 0)
            first[hit] = t + 1
        al = first[first > 0]
        mon[str(rho)] = {"alarm_within_50": float(np.mean((first > 0) & (first <= 50))),
                         "alarm_within_100": float(np.mean((first > 0) & (first <= 100))),
                         "alarm_within_400": float(np.mean(first > 0)),
                         "median_delay_if_alarm": float(np.median(al)) if al.size else None}
    # exact block test power: reject iff P(Bin(k, alpha) >= x) <= gamma
    bt = {}
    for k in CFG["block_k"]:
        crit = next(x for x in range(k + 2) if binomial_upper_pvalue(x, k, A) <= G) if binomial_upper_pvalue(k, k, A) <= G else None
        row = {"critical_errors": crit, "false_alarm": binomial_upper_pvalue(crit, k, A) if crit is not None else 0.0}
        for rho in CFG["power_rhos"]:
            row[str(rho)] = binomial_upper_pvalue(crit, k, rho) if crit is not None else 0.0
        bt[str(k)] = row
    # block LTT: smallest k that certifies alpha with x errors at a threshold
    nmin = {}
    for x in range(6):
        n = x + 1
        while math.exp(Q._log_binom_cdf(x, n, A)) > D:
            n += 1
        nmin[str(x)] = n
    return {"monitor_bernoulli": mon, "block_test_power": bt, "block_ltt_min_k_for_x_errors": nmin,
            "min_ltt_items": min_ltt_items(A, D)}


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

HEAD = ["global", "monitor", "aci", "eb k=0", "eb k=20 F", "block-test k=20 F", "block-test k=20 F + monitor",
        "block-ltt k=45 W", "block-ltt k=45 W + monitor", "block-ltt k=45 F", "block-ltt k=60 W", "mondrian-never (test items)"]


def f3(x, nd=3):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def write_tables(res: dict) -> None:
    L = ["# A2 per-session risk control: tables", "",
         f"α = {A}, δ = {D}, γ = {G}. Generated by run.py; do not edit by hand. 'pooled' = Σ wrong commits / Σ items over "
         "splits (splits share trials). '>α' = share of splits with a session rate above α. eWPM: block items count as normal use "
         "(W: offer-only, F: global threshold); 'eWPM copy' counts a W block as copy typing (no user words). "
         "Methods marked † have no finite-sample guarantee.", ""]
    P = res["power"]
    L += ["## Sample-size facts", "",
          f"- Smallest block for any per-session LTT commit: k = {P['min_ltt_items']} (0 errors).",
          "- Smallest k that certifies α with x errors: " + ", ".join(f"x={x}: {n}" for x, n in P["block_ltt_min_k_for_x_errors"].items()) + ".",
          "", "Exact block test (alarm iff P(Bin(k, α) ≥ x) ≤ γ): power by true session risk ρ", "",
          "| k | critical errors | false alarm (ρ = α) | " + " | ".join(f"ρ={r}" for r in CFG["power_rhos"]) + " |",
          "|---|---|---|" + "---|" * len(CFG["power_rhos"])]
    for k, v in P["block_test_power"].items():
        L.append(f"| {k} | {v['critical_errors']} | {f3(v['false_alarm'])} | " + " | ".join(f3(v[str(r)]) for r in CFG["power_rhos"]) + " |")
    L += ["", f"Online monitor on Bernoulli(ρ) losses ({CFG['power_sim_reps']} runs of {CFG['power_sim_T']} items):", "",
          "| ρ | alarm ≤ 50 items | ≤ 100 | ≤ 400 | median delay (if alarm) |", "|---|---|---|---|---|"]
    for r, v in P["monitor_bernoulli"].items():
        L.append(f"| {r} | {f3(v['alarm_within_50'])} | {f3(v['alarm_within_100'])} | {f3(v['alarm_within_400'])} | {f3(v['median_delay_if_alarm'], 0)} |")
    L.append("")
    for cond in ("b2t-published", "b2t-ours"):
        c = res["rs"][cond]
        L += [f"## {cond}: random re-splits (R = {c['R']})", "", "### Day 34", "",
              "| method | n/session | pooled | mean [p05, p95] | >α | commit | eWPM | eWPM copy | post-block pooled | alarm share | median delay |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for m in list(c["per_day"]):
            v = c["per_day"][m]["34"]
            L.append(f"| {m} | {v['n_mean']:.1f} | **{f3(v['pooled'])}** | {f3(v['mean'])} [{f3(v['p05'])}, {f3(v['p95'])}] | {f3(v['share_gt_alpha'], 2)} | "
                     f"{f3(v['commit_rate'])} | {f3(v['ewpm'], 2)} | {f3(v['ewpm_copy'], 2)} | {f3(v['pooled_post'])} | {f3(v['alarm_share'], 2)} | {f3(v['alarm_delay_median'], 0)} |")
        L += ["", "### All 14 days", "", "| method | days pooled > α | which | max day | mean commit | mean eWPM | mean eWPM copy | alarm share (13 other days) |",
              "|---|---|---|---|---|---|---|---|"]
        for m, v in c["summary"].items():
            L.append(f"| {m} | {v['groups_above_alpha']}/{v['groups']} | {', '.join(v['which_above'])} | {f3(v['max_group_pooled'])} | "
                     f"{f3(v['mean_commit_rate'])} | {f3(v['mean_ewpm'], 2)} | {f3(v['mean_ewpm_copy'], 2)} | {f3(v['false_alarm_share_good_groups'], 3)} |")
        L += ["", "Per-day pooled wrong-commit (selected methods):", "", "| day | " + " | ".join(HEAD) + " |", "|---|" + "---|" * len(HEAD)]
        for d in c["per_day"]["global"]:
            L.append(f"| {d} | " + " | ".join(f3(c["per_day"][m][d]["pooled"]) for m in HEAD) + " |")
        L += ["", "Share of splits whose day-d calibration has ≥ 45 items (Mondrian feasible): " +
              ", ".join(f"{d}: {v:.2f}" for d, v in c["mondrian_share_n_ge_45"].items()), ""]
    for which in ("published", "ours"):
        for design in ("V1", "V3"):
            f = res["fc"][which][design]
            L += [f"## b2t-{which}: forward chain {design}", "",
                  "| method | days > α | which | CP>α | pooled [CP95] | commit | mean day eWPM | Δ eWPM vs global [boot95] | alarms |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for m, v in f["summary"].items():
                L.append(f"| {m} | {v['days_above_alpha']}/{v['n_days']} | {', '.join(v['which_above'])} | {', '.join(v['days_cp_lower_above_alpha'])} | "
                         f"{f3(v['pooled'])} {Q.fci(v['pooled_cp95'])} | {f3(v['commit_rate'])} | {f3(v['mean_day_ewpm'], 2)} | "
                         f"{v['ewpm_diff_vs_global']:+.2f} {Q.fci(v['ewpm_diff_boot95'], 2)} | {', '.join(v['alarms'])} |")
            if "34" in f["days"]:
                d34 = f["days"]["34"]
                L += ["", f"Day 34 ({design}, n = {d34['n']}, global threshold {f3(d34['lam_g'], 2)}):", "",
                      "| method | wrong [CP95] | commits | eWPM | alarm at |", "|---|---|---|---|---|"]
                for m, v in d34["methods"].items():
                    L.append(f"| {m} | {int(round(v['wrong']))}/{v['n']} = {f3(v['rate'])} {Q.fci(v['wrong_cp95'])} | {v['commits']} | "
                             f"{f3(60 * v['words'] / v['time'], 2)} | {v.get('alarm_at') or ''} |")
            L.append("")
    for cond, c in res["emg"].items():
        L += [f"## {cond}: per test participant (R = {c['R']})", "",
              "| method | participants pooled > α | max | mean commit | mean eWPM | alarm share |", "|---|---|---|---|---|---|"]
        for m, v in c["summary"].items():
            L.append(f"| {m} | {v['groups_above_alpha']}/{v['groups']} | {f3(v['max_group_pooled'])} | {f3(v['mean_commit_rate'])} | "
                     f"{f3(v['mean_ewpm'], 2)} | {f3(v['false_alarm_share_good_groups'], 3)} |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    (OUT / "run.log").write_text("", encoding="utf-8")
    t0 = time.time()
    res = {"config": CFG, "methods": [{"name": n, "kind": k, "k": kk, "mode": m} for n, k, kk, m in SPECS]}
    res["power"] = power_tables()
    C = Q.C
    C.dump(res["power"], OUT / "power.json")
    log("power tables done")
    res["fc"] = {w: fc_b2t(w) for w in ("published", "ours")}
    C.dump(res["fc"], OUT / "forward_chain.json")
    log("forward chain done")
    res["emg"] = {c: rs_emg(c) for c in ("emg-calib", "emg-xsession", "emg-xsubject")}
    C.dump(res["emg"], OUT / "emg.json")
    log("sEMG done")
    res["rs"] = {}
    for cond in ("b2t-published", "b2t-ours"):
        res["rs"][cond] = rs_b2t(cond)
        C.dump(res["rs"][cond], OUT / f"rs-{cond}.json")
        log(f"{cond} done")
    write_tables(res)
    log(f"all done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
