"""R3 item 7: inference tightening and one set of CIs for the whole paper.

Stats review M6 (1-4, 6), M1(c, d); editor number check.

1. ``ci.json``: every CI the paper uses, recomputed with ONE bootstrap seed
   (20261112) and B = 2000, percentile 95 %, at the condition's unit (B2T
   day clusters, sEMG participant clusters, MEG two-way sentences x
   participants, plus MEG sentence-only and participant-only). The same
   seed gives the same resampling weights for the same unit, so the same
   quantity has the same CI in every table. Sources:
   - Tab. 2 / baselines: committed per-item arrays (``baselines/results/arrays-*.json``);
   - Tab. 3 / clean calibration: committed item tables (``clean-drift/results/items-*.json``);
   - ablation, user model, leakage: the round-1 scripts re-run with the
     bootstrap patched to the unified seed and B (``--stage rerun``; cached
     decodes; outputs in ``results/rerun/<module>/results``).
   All CIs are conditional on the fitted pipeline and the threshold.
2. Holm correction over the six Tab. 3 exchangeable-reference tests, with
   the plain reference and with a day-stratified permutation reference for
   B2T (stats M1(d)).
3. Day-level exact sign tests and sign-flip permutation tests for the key
   B2T paired differences (14 days); participant-level for sEMG.
4. Exact Clopper-Pearson bounds for zero-event and small-count rates
   (Tab. 2 wrong-commit counts; null-audit controls).

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/unified-ci/run.py --stage rerun --module ablation
  ... --stage rerun --module user-model ; ... --stage rerun --module leakage
  ... --stage assemble
"""

from __future__ import annotations

import argparse
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
SEED, BB = K.UNIFIED_SEED, K.UNIFIED_B
_orig_bootstrap = C.bootstrap


def unified_bootstrap(arrs, cond, B=2000, seed=11, diffs=(), scheme=None):  # noqa: ARG001
    return _orig_bootstrap(arrs, cond, B=BB, seed=SEED, diffs=diffs, scheme=scheme)


def stage_rerun(module: str) -> None:
    import shutil
    C.bootstrap = unified_bootstrap
    mod_dir = K.R1 / module
    out = OUT / "rerun" / module / "results"
    out.mkdir(parents=True, exist_ok=True)
    if module == "leakage":
        shutil.copy(K.R1 / "leakage/results/build_report.json", out / "build_report.json")
    sys.argv = [str(mod_dir / "run.py")]
    m = C.load_module(f"r1_{module.replace('-', '_')}", mod_dir / "run.py")
    m.OUT = out
    C.Log.path = out / "run.log"
    if hasattr(m, "CONFIG"):
        m.CONFIG["bootstrap_B"] = BB
    m.main()
    R = C.load_module("r1report", K.R1 / "report.py")
    R.HERE = OUT / "rerun"
    {"ablation": R.ablation, "user-model": R.user_model, "leakage": R.leakage}[module]()


# ---------------------------------------------------------------------------

B2T_DIFFS = [("trust", "always_commit"), ("trust", "never_commit"), ("trust", "gaze_only"), ("never_commit", "gaze_only"),
             ("no_guard", "trust"), ("crc", "never_commit"), ("crc", "trust"), ("always_commit", "gaze_only")]


def ns(cluster, sent=None, scheme="cluster"):
    return SimpleNamespace(cluster=np.asarray(cluster), sent=None if sent is None else np.asarray(sent), scheme=scheme)


def load_arrays(name):
    a = json.loads((K.R1 / f"baselines/results/arrays-{name}.json").read_text(encoding="utf-8"))
    arrs = {p: {k: np.asarray(v, float) for k, v in d.items()} for p, d in a["arrays"].items()}
    return arrs, np.asarray(a["cluster"]), (None if a.get("sent") is None else np.asarray(a["sent"]))


def table2() -> dict:
    out = {}
    for name in ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession", "emg-xsubject", "meg-async"):
        arrs, cl, sent = load_arrays(name)
        diffs = [d for d in B2T_DIFFS if d[0] in arrs and d[1] in arrs]
        pt = C.point(arrs)
        for p, a in arrs.items():
            n = len(a["wc"])
            k = int(round(a["wc"].sum()))
            pt[p].update({"n": n, "n_wrong_commit": k, "n_commit": int(a["com"].sum()), "n_commit_wrong": int(round(a["wcc"].sum())),
                          "wrong_commit_cp95": K.clopper_pearson(k, n), "wrong_commit_cp95_upper_one_sided": K.upper_one_sided(k, n)})
        r = {"unit": "two_way (sentences x participants)" if name.startswith("meg") else ("day" if name.startswith("b2t") else "participant"),
             "point": pt}
        if name.startswith("meg"):
            r["ci"] = C.bootstrap(arrs, ns(cl, sent, "two_way"), B=BB, seed=SEED, diffs=diffs)
            r["ci_sentences"] = C.bootstrap(arrs, ns(cl, sent, "sentences"), B=BB, seed=SEED, diffs=diffs, scheme="sentences")
            r["ci_participants"] = C.bootstrap(arrs, ns(cl, sent, "cluster"), B=BB, seed=SEED, diffs=diffs, scheme="cluster")
        else:
            r["ci"] = C.bootstrap(arrs, ns(cl), B=BB, seed=SEED, diffs=diffs)
        out[name] = r
        C.log(f"tab2 {name}: trust eWPM {pt['trust']['ewpm']:.3f} CI {r['ci']['policies']['trust']['ewpm']}")
    return out


def table3() -> dict:
    out = {}
    clean = K.R1 / "clean-drift/results"
    for f in ("ours-alternate", "ours-chrono", "published-alternate", "published-chrono", "emg-xsession", "emg-calib", "emg-xsubject"):
        items = json.loads((clean / f"items-{f}.json").read_text(encoding="utf-8"))
        ca = K.arr(items["items_cal"])
        lp = float(C.fnum(items["items_test"]["lam_old"]))
        rc, rl = K.crc(ca), K.ltt(ca)
        lams = {"plug-in (fit-A)": lp, "CRC pure (clean)": rc.threshold, "LTT pure (clean)": rl.threshold,
                "CRC max-rule (clean)": max(lp, rc.threshold), "LTT max-rule (clean)": max(lp, rl.threshold)}
        arrs = {k: C.item_arrays(items["items_test"], v) for k, v in lams.items()}
        cl = np.unique(items["days_test"] if "days_test" in items else items["participants_test"], return_inverse=True)[1]
        out[f] = {"lambda": {k: C.clean(v) for k, v in lams.items()}, "point": C.point(arrs),
                  "ci": C.bootstrap(arrs, ns(cl), B=BB, seed=SEED)}
    return out


def strat_reference(items: dict, reps: int, seed: int) -> dict:
    """Day-stratified exchangeable reference: permute calibration / test labels within each day."""
    ca, te = K.arr(items["items_cal"]), K.arr(items["items_test"])
    days = np.r_[np.asarray(items["days_cal"]), np.asarray(items["days_test"])]
    pool = {k: (np.r_[ca[k], te[k]] if isinstance(ca[k], np.ndarray) else ca[k]) for k in ca}
    pool["c"], pool["f"] = pool["loss_c"], pool["loss_f"]
    is_cal = np.r_[np.ones(ca["s"].size, bool), np.zeros(te["s"].size, bool)]
    obs = K.outcome(te, K.crc(ca).threshold)["wrong_commit"]
    rng = np.random.default_rng(seed)
    rates = []
    for _ in range(reps):
        lab = np.empty_like(is_cal)
        for d in np.unique(days):
            m = np.where(days == d)[0]
            lab[m] = rng.permutation(is_cal[m])
        cal = K.take(pool, np.where(lab)[0])
        tst = K.take(pool, np.where(~lab)[0])
        rates.append(K.outcome(tst, K.crc(cal).threshold)["wrong_commit"])
    rates = np.array(rates)
    return {"reps": reps, "observed": obs, "mean": float(rates.mean()), "p05": float(np.quantile(rates, 0.05)),
            "p95": float(np.quantile(rates, 0.95)), "p_value_ge_observed": float((np.sum(rates >= obs - 1e-12) + 1) / (reps + 1))}


def holm_block() -> dict:
    b2t = json.loads((K.R1 / "clean-drift/results/clean_drift_b2t.json").read_text(encoding="utf-8"))
    emg = json.loads((K.R1 / "clean-drift/results/clean_drift_emg.json").read_text(encoding="utf-8"))
    plain = {"b2t-ours/split A": b2t["b2t-ours/alternate"]["exchangeable_reference"]["p_value_ge_observed"],
             "b2t-ours/split B": b2t["b2t-ours/chrono"]["exchangeable_reference"]["p_value_ge_observed"],
             "b2t-published/split A": b2t["b2t-published/alternate"]["exchangeable_reference"]["p_value_ge_observed"],
             "b2t-published/split B": b2t["b2t-published/chrono"]["exchangeable_reference"]["p_value_ge_observed"],
             "emg-xsession": emg["emg-xsession"]["exchangeable_reference"]["p_value_ge_observed"],
             "emg-calib": emg["emg-calib"]["exchangeable_reference"]["p_value_ge_observed"]}
    strat = {}
    for key, f in (("b2t-ours/split A", "ours-alternate"), ("b2t-ours/split B", "ours-chrono"),
                   ("b2t-published/split A", "published-alternate"), ("b2t-published/split B", "published-chrono")):
        items = json.loads((K.R1 / f"clean-drift/results/items-{f}.json").read_text(encoding="utf-8"))
        strat[key] = strat_reference(items, 2000, SEED)
        C.log(f"day-stratified reference {key}: obs {strat[key]['observed']:.4f} mean {strat[key]['mean']:.4f} p {strat[key]['p_value_ge_observed']:.4f}")
    pstrat = {**{k: v["p_value_ge_observed"] for k, v in strat.items()}, "emg-xsession": plain["emg-xsession"], "emg-calib": plain["emg-calib"]}
    return {"tests": "one-sided: clean-CRC test rate >= exchangeable reference (Tab. 3); emg-xsubject (never commits, p = 1) left out",
            "p_plain": plain, "holm_plain": K.holm(plain), "day_stratified_reference": strat,
            "p_day_stratified_b2t": pstrat, "holm_day_stratified_b2t": K.holm(pstrat)}


def per_cluster_eWPM(a: dict, cl: np.ndarray) -> np.ndarray:
    return np.array([60 * a["w"][cl == g].sum() / a["t"][cl == g].sum() for g in np.unique(cl)])


def per_cluster_rate(a: dict, key: str, cl: np.ndarray) -> np.ndarray:
    return np.array([a[key][cl == g].mean() for g in np.unique(cl)])


def cluster_tests() -> dict:
    out = {}
    pairs = [("trust", "never_commit"), ("trust", "always_commit"), ("crc", "never_commit"), ("no_guard", "trust"),
             ("trust", "gaze_only"), ("never_commit", "gaze_only")]
    for name in ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession", "emg-xsubject"):
        arrs, cl, _ = load_arrays(name)
        r = {}
        for a, b in pairs:
            if a not in arrs or b not in arrs:
                continue
            de = per_cluster_eWPM(arrs[a], cl) - per_cluster_eWPM(arrs[b], cl)
            dw = per_cluster_rate(arrs[a], "wc", cl) - per_cluster_rate(arrs[b], "wc", cl)
            r[f"{a} - {b}"] = {"ewpm": {"per_cluster": de.tolist(), "sign": K.sign_test(de), "permutation": K.perm_test_clusters(de)},
                               "wrong_commit": {"per_cluster": dw.tolist(), "sign": K.sign_test(dw), "permutation": K.perm_test_clusters(dw)}}
        out[name] = {"unit": "day" if name.startswith("b2t") else "participant", "n_clusters": int(np.unique(cl).size), "tests": r}
    return out


def zero_event() -> dict:
    rows = {"B2T null-audit controls (trust, 0 of 300 per control)": (0, 300),
            "sEMG null-audit controls (trust, 0 of 200 per condition)": (0, 200),
            "MEG controls (trust, 0 of 637)": (0, 637),
            "sEMG test (0 of 551)": (0, 551)}
    return {k: {"k": v[0], "n": v[1], "cp95_two_sided": K.clopper_pearson(*v), "cp95_upper_one_sided": K.upper_one_sided(*v),
                "rule_of_three": 3 / v[1]} for k, v in rows.items()}


def collect_reruns() -> dict:
    out = {}
    for m in ("ablation", "user-model", "leakage"):
        d = OUT / "rerun" / m / "results"
        if not d.exists():
            out[m] = "not run"
            continue
        out[m] = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))
                  if not f.name.startswith("arrays-") and f.name != "build_report.json"}
    return out


def stage_assemble() -> None:
    C.Log.path = OUT / "assemble.log"
    res = {"meta": {"seed": SEED, "B": BB, "method": "percentile bootstrap, 95 %", "conditional_on": "fitted pipeline and threshold",
                    "units": {"b2t": "day (14 test days)", "emg": "participant (19)", "meg": "two-way sentences x participants (17 x 19); also sentences, participants"},
                    "note": "Same seed + same unit -> same resampling weights: one quantity has one CI in every table."},
           "table2_baselines": table2(), "table3_clean_calibration": table3(), "holm_table3": holm_block(),
           "cluster_tests": cluster_tests(), "zero_event_bounds": zero_event(), "reruns": collect_reruns()}
    C.dump(res, OUT / "ci.json")
    write_tables(res)
    C.log("assembled")


def write_tables(res: dict) -> None:
    L = ["# Unified CIs and inference checks", "",
         f"One bootstrap: seed {SEED}, B = {BB}, percentile 95 %, conditional on the fitted pipeline and the threshold. Full data: `ci.json`.", "",
         "## Tab. 2 (baselines): eWPM and wrong-commit with unified CIs", "",
         "| condition | policy | eWPM [CI] | wrong-commit [CI] | wrong / n (CP95 two-sided) | commit rate | error among commits (counts if < 30 commits) |",
         "|---|---|---|---|---|---|---|"]
    for name, r in res["table2_baselines"].items():
        for p, v in r["point"].items():
            ci = r["ci"]["policies"][p]
            eac = (f"{v['n_commit_wrong']}/{v['n_commit']}" if v["n_commit"] < 30 else C.fmt(v["error_among_commits"], 3))
            cp = v["wrong_commit_cp95"]
            L.append(f"| {name} | {p} | {v['ewpm']:.2f} {C.fci(ci['ewpm'], 2)} | {v['wrong_commit']:.4f} {C.fci(ci['wrong_commit'], 3)} | "
                     f"{v['n_wrong_commit']}/{v['n']} [{cp[0]:.4f}, {cp[1]:.4f}] | {v['commit_rate']:.3f} | {eac} |")
    L += ["", "Paired differences (eWPM CI; wrong-commit CI):", ""]
    for name, r in res["table2_baselines"].items():
        L.append(f"- {name}: " + "; ".join(f"{k} {C.fci(v['ewpm'], 2)} / {C.fci(v['wrong_commit'], 3)}" for k, v in r["ci"]["diffs"].items()))
        if "ci_sentences" in r:
            L.append(f"  - sentences only: " + "; ".join(f"{k} {C.fci(v['ewpm'], 2)}" for k, v in r["ci_sentences"]["diffs"].items()))
            L.append(f"  - participants only: " + "; ".join(f"{k} {C.fci(v['ewpm'], 2)}" for k, v in r["ci_participants"]["diffs"].items()))
    L += ["", "## Tab. 3 (clean calibration): test wrong-commit [CI]", "", "| condition | plug-in (fit-A) | CRC pure | LTT pure | CRC max-rule | LTT max-rule |", "|---|---|---|---|---|---|"]
    for f, r in res["table3_clean_calibration"].items():
        L.append(f"| {f} | " + " | ".join(f"{r['point'][k]['wrong_commit']:.4f} {C.fci(r['ci']['policies'][k]['wrong_commit'], 3)}"
                                          for k in ("plug-in (fit-A)", "CRC pure (clean)", "LTT pure (clean)", "CRC max-rule (clean)", "LTT max-rule (clean)")) + " |")
    h = res["holm_table3"]
    L += ["", "## Holm correction over the six Tab. 3 tests", "", "| test | p (plain reference) | Holm | p (day-stratified reference for B2T) | Holm |", "|---|---|---|---|---|"]
    for k in h["p_plain"]:
        L.append(f"| {k} | {h['p_plain'][k]:.4f} | {h['holm_plain'][k]:.4f} | {h['p_day_stratified_b2t'][k]:.4f} | {h['holm_day_stratified_b2t'][k]:.4f} |")
    L += ["", "Day-stratified reference (B2T): " + "; ".join(f"{k}: observed {v['observed']:.4f}, mean {v['mean']:.4f} ({v['p05']:.4f}–{v['p95']:.4f})"
                                                      for k, v in h["day_stratified_reference"].items()), ""]
    L += ["## Cluster-level tests (B2T: 14 days; sEMG: 19 participants)", "",
          "| condition | difference | eWPM: positive / negative clusters | sign p | sign-flip p | wrong-commit: + / − | sign p | sign-flip p |", "|---|---|---|---|---|---|---|---|"]
    for name, r in res["cluster_tests"].items():
        for k, v in r["tests"].items():
            e, w = v["ewpm"], v["wrong_commit"]
            L.append(f"| {name} | {k} | {e['sign']['positive']}/{e['sign']['negative']} | {e['sign']['p_two_sided']:.4f} | {e['permutation']['p_two_sided']:.4f} | "
                     f"{w['sign']['positive']}/{w['sign']['negative']} | {w['sign']['p_two_sided']:.4f} | {w['permutation']['p_two_sided']:.4f} |")
    L += ["", "## Exact bounds for zero-event rates (items treated as independent: optimistic under clustering)", "",
          "| rate | k / n | CP95 two-sided | one-sided 95 % upper | rule of three |", "|---|---|---|---|---|"]
    for k, v in res["zero_event_bounds"].items():
        L.append(f"| {k} | {v['k']}/{v['n']} | [{v['cp95_two_sided'][0]:.4f}, {v['cp95_two_sided'][1]:.4f}] | {v['cp95_upper_one_sided']:.4f} | {v['rule_of_three']:.4f} |")
    L += ["", "## Re-runs with the unified bootstrap", ""]
    for m, v in res["reruns"].items():
        L.append(f"- {m}: " + ("not run" if isinstance(v, str) else f"results/rerun/{m}/results/ ({', '.join(v)})"))
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--module")
    a = ap.parse_args()
    if a.stage == "rerun":
        stage_rerun(a.module)
    else:
        stage_assemble()


if __name__ == "__main__":
    main()
