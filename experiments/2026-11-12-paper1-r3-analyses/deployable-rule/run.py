"""R3 item 3: the deployable rule rows, and the attribution of 0.059 -> 0.0245.

Editor M1, M2; stats review M2, M3. The recommended rule is the fit-A
plug-in gate plus clean calibration with the max rule
lambda = max(lambda_plug-in, lambda_CRC) (or lambda_LTT). Rows per
condition and split, with the calibration bound and binding flags:

- B2T ours / published, split A (``alternate``) and split B (``chrono``):
  committed clean-drift item tables.
- sEMG calib / xsession / xsubject: committed clean-drift item tables.
- MEG async: the baselines clean split (val-A 6 sentences fit, val-B 5
  sentences calibrate), rebuilt here from cached decodes. Instance-level;
  no guarantee for new sentences (see ``meg-grouped``).

CIs: percentile bootstrap at the condition's unit, unified seed and B (see
``unified-ci``), conditional on the fitted pipeline and the threshold.

Attribution (B2T ours): full-fit plug-in (paper trust row, 812 fit trials)
-> fit-A plug-in -> + CRC max-rule, and the two cross-over pipelines
(full-fit calibration + fit-A policy config; fit-A calibration + full-fit
policy config) to split the refit effect into calibration and policy grid.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/deployable-rule/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CLEAN = K.R1 / "clean-drift" / "results"
M13 = C.load_module("m213run", C.REPO / "experiments/2026-11-11-m2-13-conformal/run.py")


def rows_for(items: dict, cond_ns) -> dict:
    ca, te = K.arr(items["items_cal"]), K.arr(items["items_test"])
    lp = te["lam_old"]
    rc, rl = K.crc(ca), K.ltt(ca)
    lams = {"plug-in (fit-A)": lp, "CRC max-rule (clean) [deployable]": max(lp, rc.threshold),
            "LTT max-rule (clean)": max(lp, rl.threshold), "CRC pure (clean)": rc.threshold, "LTT pure (clean)": rl.threshold}
    arrs = {k: C.item_arrays(items["items_test"], v) for k, v in lams.items()}
    pt = {k: {**C.metrics(a), "n_commit": int(a["com"].sum()), "n_commit_wrong": int(a["wcc"].sum())} for k, a in arrs.items()}
    bs = C.bootstrap(arrs, cond_ns, B=K.UNIFIED_B, seed=K.UNIFIED_SEED)
    info = {"lambda": {k: C.clean(v) for k, v in lams.items()}, "crc_bound_at_crc": rc.bound,
            "cal_bound_at_plugin": K.cal_bound(ca, lp), "plugin_certified": K.cal_bound(ca, lp) <= C.ALPHA + 1e-12,
            "crc_active": K.crc_active(ca, rc.threshold), "crc_stricter_than_plugin": bool(rc.threshold > lp),
            "maxrule_changes_plugin_on_test": not K.same_decisions(te, max(lp, rc.threshold), lp),
            "ltt_maxrule_changes_plugin_on_test": not K.same_decisions(te, max(lp, rl.threshold), lp),
            "n_cal": int(ca["s"].size), "n_test": int(te["s"].size), "eligible_cal": float(np.isfinite(ca["s"]).mean()),
            "eligible_test": float(np.isfinite(te["s"]).mean())}
    # Exact zero-event upper bounds for the counts (item 7)
    for k, a in arrs.items():
        nw = int(round(a["wc"].sum()))
        pt[k]["n_wrong_commit"] = nw
        pt[k]["wrong_commit_cp95_upper"] = K.upper_one_sided(nw, len(a["wc"]))
    return {"point": pt, "ci": bs, "info": info}


def ns(cluster, scheme="cluster", sent=None):
    from types import SimpleNamespace
    return SimpleNamespace(cluster=np.asarray(cluster), sent=sent, scheme=scheme)


def b2t_rows() -> dict:
    out = {}
    for which in ("ours", "published"):
        for split, lab in (("alternate", "split A"), ("chrono", "split B")):
            items = json.loads((CLEAN / f"items-{which}-{split}.json").read_text(encoding="utf-8"))
            cl = np.unique(items["days_test"], return_inverse=True)[1]
            out[f"b2t-{which}/{lab}"] = rows_for(items, ns(cl))
            C.log(f"b2t-{which} {lab}: " + "; ".join(f"{k} {v['wrong_commit']:.4f}/{v['commit_rate']:.3f}"
                                                   for k, v in out[f"b2t-{which}/{lab}"]["point"].items()))
    return out


def emg_rows() -> dict:
    out = {}
    for c in ("calib", "xsession", "xsubject"):
        items = json.loads((CLEAN / f"items-emg-{c}.json").read_text(encoding="utf-8"))
        cl = np.unique(items["participants_test"], return_inverse=True)[1]
        out[f"emg-{c}"] = rows_for(items, ns(cl))
        C.log(f"emg-{c}: " + "; ".join(f"{k} {v['wrong_commit']:.4f}/{v['commit_rate']:.3f}" for k, v in out[f"emg-{c}"]["point"].items()))
    return out


def meg_rows() -> dict:
    B = C.load_module("r1baselines", K.R1 / "baselines" / "run.py")
    cond = C.meg_ctx()
    clean, info, _ = B.meg_clean_crc(cond, {})
    C.save_caches(cond)
    C.dump({**clean, "sentence_ids_test": cond.sent, "participants_test": cond.part_names, "info": info},
           K.CACHE3 / "meg-clean-items.json")
    r = rows_for(clean, ns(cond.cluster, "two_way", cond.sent))
    r["note"] = ("Instance-level CRC on 5 calibration sentences (199 instances). Instances of one sentence are dependent; "
                 "the exchangeable unit is the sentence, so this row carries no guarantee for new sentences.")
    C.log("meg: " + "; ".join(f"{k} {v['wrong_commit']:.4f}/{v['commit_rate']:.3f}" for k, v in r["point"].items()))
    return {"meg-async": r}


def attribution() -> dict:
    """B2T ours: split the 0.0588 -> 0.0245 / 0.0600 change into the refit of calibration vs policy grid, and CRC."""
    from dataclasses import replace  # noqa: F401
    from fidetype.trust.policy import DecisionPolicy
    P = C.load_module("r1policies", K.R1 / "policies.py")
    ctx = C.b2t_ctx()
    cond = C.b2t_condition(ctx, "ours")
    cond.cached = ctx.cached
    full = P.build(cond, "trust", {})  # paper trust row: fit(fit, fit), 812 trials
    T = ctx.items(ctx.test)
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    out = {"full_fit": {"policy": C.clean(full.policy.config.__dict__), "frame_T": full.frame_scaler.temperature}}

    def test_rate(pipe, policy=None):
        recs = pipe.run_items(T, policy) if policy is not None else pipe.run_items(T)
        a = C.rec_arrays(recs)
        return C.metrics(a)

    out["full_fit"]["test"] = test_rate(full)
    for split, lab in (("alternate", "split A"), ("chrono", "split B")):
        A = []
        for d, idx in sorted(by_day.items()):
            if split == "alternate":
                A += idx[0::2]
            else:
                A += idx[: (len(idx) + 1) // 2]
        A = [ctx.fit[i] for i in sorted(A)]
        pa = C.TrustPipeline(ctx.dec.words_fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA), {})
        pa.fit(ctx.items(A), ctx.items(A))
        r = {"fitA_policy": C.clean(pa.policy.config.__dict__), "fitA_frame_T": pa.frame_scaler.temperature,
             "fitA_plugin": test_rate(pa),
             "full_calibration + fitA_policy": test_rate(full, DecisionPolicy(pa.policy.config, use_guard=True)),
             "fitA_calibration + full_policy": test_rate(pa, DecisionPolicy(full.policy.config, use_guard=True))}
        items = json.loads((CLEAN / f"items-ours-{split}.json").read_text(encoding="utf-8"))
        ca = K.arr(items["items_cal"])
        rc = K.crc(ca)
        lam = max(pa.policy.config.commit_p, rc.threshold)
        r["fitA + CRC max-rule"] = K.outcome(K.arr(items["items_test"]), lam)
        r["fitA + CRC pure"] = K.outcome(K.arr(items["items_test"]), rc.threshold)
        out[lab] = r
        C.log(f"attribution {lab}: full {out['full_fit']['test']['wrong_commit']:.4f} -> fit-A {r['fitA_plugin']['wrong_commit']:.4f}; "
              f"full cal + fit-A policy {r['full_calibration + fitA_policy']['wrong_commit']:.4f}; fit-A cal + full policy "
              f"{r['fitA_calibration + full_policy']['wrong_commit']:.4f}; + CRC max {r['fitA + CRC max-rule']['wrong_commit']:.4f}")
    C.save_caches(ctx)
    return out


def write_tables(res: dict) -> None:
    L = ["# Deployable rule rows (fit-A plug-in + clean CRC / LTT, max rule)", "",
         f"95 % percentile CIs: bootstrap at the condition's unit (B2T day, sEMG participant, MEG two-way), seed {K.UNIFIED_SEED}, "
         f"B = {K.UNIFIED_B}, conditional on the fitted pipeline and the threshold. CP95 = exact one-sided 95 % upper bound "
         "(Clopper-Pearson, items treated as independent: optimistic under clustering).", ""]
    for name, r in res["rows"].items():
        i = r["info"]
        L += [f"## {name}", "", f"n_cal {i['n_cal']}, n_test {i['n_test']}; λ plug-in {C.fmt(C.fnum(i['lambda']['plug-in (fit-A)']), 3)}, "
              f"λ CRC {C.fmt(C.fnum(i['lambda']['CRC pure (clean)']), 4)}, λ LTT {C.fmt(C.fnum(i['lambda']['LTT pure (clean)']), 3)}; "
              f"CRC bound at λ̂ {C.fmt(i['crc_bound_at_crc'], 4)}; calibration bound at plug-in λ {C.fmt(i['cal_bound_at_plugin'], 4)} "
              f"(plug-in certified: {i['plugin_certified']}); CRC constraint active: {i['crc_active']}; max rule changes a test decision: "
              f"{i['maxrule_changes_plugin_on_test']} (LTT: {i['ltt_maxrule_changes_plugin_on_test']}).", "",
              "| rule | wrong-commit [CI] | wrong commits / n (CP95 upper) | commit rate | error among commits | eWPM [CI] |", "|---|---|---|---|---|---|"]
        for k, v in r["point"].items():
            ci = r["ci"]["policies"][k]
            eac = f"{v['n_commit_wrong']}/{v['n_commit']}" if v["n_commit"] < 30 else C.fmt(v["error_among_commits"], 3)
            L.append(f"| {k} | {v['wrong_commit']:.4f} {C.fci(ci['wrong_commit'], 3)} | {v['n_wrong_commit']}/{i['n_test']} "
                     f"({v['wrong_commit_cp95_upper']:.4f}) | {v['commit_rate']:.3f} | {eac} | {v['ewpm']:.2f} {C.fci(ci['ewpm'], 2)} |")
        if "note" in r:
            L += ["", r["note"]]
        L.append("")
    a = res.get("attribution")
    if a:
        L += ["## Attribution of the B2T-ours change (test wrong-commit / commit rate)", "",
              "| step | split A | split B |", "|---|---|---|"]
        g = lambda d: f"{d['wrong_commit']:.4f} / {d['commit_rate']:.3f}"  # noqa: E731
        L.append(f"| full-fit plug-in (paper trust row, 812 fit trials) | {g(a['full_fit']['test'])} | {g(a['full_fit']['test'])} |")
        for k in ("full_calibration + fitA_policy", "fitA_calibration + full_policy", "fitA_plugin", "fitA + CRC max-rule", "fitA + CRC pure"):
            L.append(f"| {k} | {g(a['split A'][k])} | {g(a['split B'][k])} |")
        L += ["", f"Full-fit policy: commit_p {a['full_fit']['policy']['commit_p']}, commit_max_risk {a['full_fit']['policy']['commit_max_risk']}, "
              f"offer_max_k {a['full_fit']['policy']['offer_max_k']}; frame T {a['full_fit']['frame_T']:.3f}. "
              f"Fit-A policy split A: commit_p {a['split A']['fitA_policy']['commit_p']}, commit_max_risk {a['split A']['fitA_policy']['commit_max_risk']}; "
              f"split B: commit_p {a['split B']['fitA_policy']['commit_p']}, commit_max_risk {a['split B']['fitA_policy']['commit_max_risk']}.", ""]
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    res = {"config": CONFIG, "rows": {}}
    res["rows"].update(b2t_rows())
    res["rows"].update(emg_rows())
    res["rows"].update(meg_rows())
    C.dump(res, OUT / "deployable.json")
    res["attribution"] = attribution()
    C.dump(res, OUT / "deployable.json")
    write_tables(res)
    C.log("done")


if __name__ == "__main__":
    main()
