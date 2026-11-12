"""R1 item 2: baselines and selective risk for every condition of the Paper 1 main table.

Domain review M1 / M2, methods review Major 2. For B2T '25 (ours, published
gate), sEMG (calib, xsession, xsubject) and MEG (async):

- always commit (calibrated LM top-1), never commit / always offer (trust
  grid with commit disabled, refit), plain threshold on calibrated p_top1
  without guard (refit), plain threshold on raw p_top1 (no temperatures, no
  guard, refit), trust (plug-in, the main row), CRC and LTT on clean
  calibration data (B2T: the fit-A / fit-B ``alternate`` split of
  ``clean-drift``; sEMG: fit-B2 of ``clean-drift``; MEG: val split by
  sentence, val-A 6 sentences fit everything, val-B 5 sentences calibrate),
  gaze typing only.
- Metrics: eWPM, wrong-commit (marginal, P(commit and wrong)), commit rate,
  error among commits (selective risk, P(wrong | commit)), silent error.
- 95 % percentile CIs (B = 2000) at the right unit: B2T day clusters (14),
  sEMG participant clusters (19), MEG two-way sentences x participants.
- Also: selective risk of CRC / LTT in the random calibration / test splits
  of M2-13 (B2T) and G1 (MEG), n_cal 100 and 408, from the committed item files.

Run (repo root, after clean-drift): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/baselines/run.py
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
import policies as P  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
M13 = C.load_module("m213run", C.REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
CLEAN = HERE.parent / "clean-drift" / "results"
VARIANTS = ("always_commit", "never_commit", "raw_no_guard", "no_guard", "trust")
DIFFS = [("trust", "always_commit"), ("trust", "never_commit"), ("trust", "gaze_only"), ("never_commit", "gaze_only"),
         ("no_guard", "trust"), ("crc", "never_commit"), ("crc", "trust"), ("always_commit", "gaze_only")]


def clean_items(cond_name: str):
    if cond_name.startswith("b2t"):
        which = cond_name.split("-")[1]
        p = CLEAN / f"items-{which}-alternate.json"
    else:
        p = CLEAN / f"items-{cond_name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def meg_clean_crc(cond, cache) -> tuple[dict, dict, dict]:
    """MEG: split val by sentence (A: 6 sentences fit all parts; B: 5 sentences calibrate CRC / LTT)."""
    rng = np.random.default_rng(CONFIG["seed"])
    us = rng.permutation(int(cond.val_sent.max()) + 1)
    a_s = set(us[: CONFIG["meg_val_a_sentences"]].tolist())
    A = [it for it, s in zip(cond.val, cond.val_sent) if s in a_s]
    Bv = [it for it, s in zip(cond.val, cond.val_sent) if s not in a_s]
    pipe = C.make_pipe(cond, cache)
    pipe.fit(A, A)
    tab_b, tab_t = M13.item_table(pipe, Bv), M13.item_table(pipe, cond.test)
    return {"items_cal": tab_b, "items_test": tab_t}, {"n_A": len(A), "n_B": len(Bv), "fit_report": C.clean(pipe.fit_report)}, \
        {"plugin_lam": pipe.policy.config.commit_p}


def split_selective(path: Path, n_cals=(100, 408), reps: int = 200, seed: int = 0) -> dict:
    """Selective risk of CRC / LTT over random cal / test splits of a committed item file (M2-13 / G1)."""
    d = json.loads(path.read_text(encoding="utf-8"))["test"]
    s = np.array([C.fnum(x) for x in d["score"]])
    c, f = np.asarray(d["loss_c"], float), np.asarray(d["loss_f"], float)
    wc_c, wc_f = np.asarray(d["wc_c"], float), np.asarray(d["wc_f"], float)
    n = len(s)
    out = {}
    rng = np.random.default_rng(seed)
    for n_cal in n_cals:
        rows = {"crc": [], "ltt": []}
        for _ in range(reps):
            perm = rng.permutation(n)
            cal, tst = perm[:n_cal], perm[n_cal:]
            lam = {"crc": C.crc_threshold(s[cal], c[cal], C.ALPHA, f[cal]).threshold,
                   "ltt": C.ltt_threshold(s[cal], c[cal], C.ALPHA, C.DELTA, f[cal]).threshold}
            for k, l in lam.items():
                on = s[tst] >= l
                wc = np.where(on, wc_c[tst], wc_f[tst])
                rows[k].append((float(wc.mean()), float(on.mean()), float((wc * on).sum()), float(on.sum())))
        out[str(n_cal)] = {}
        for k, r in rows.items():
            r = np.array(r)
            with np.errstate(invalid="ignore", divide="ignore"):
                sel = r[:, 2] / r[:, 3]
            out[str(n_cal)][k] = {"wrong_commit_mean": float(r[:, 0].mean()), "commit_rate_mean": float(r[:, 1].mean()),
                                  "error_among_commits_pooled": float(r[:, 2].sum() / r[:, 3].sum()) if r[:, 3].sum() else None,
                                  "error_among_commits_mean_over_splits_with_commits": float(np.nanmean(sel)) if np.isfinite(sel).any() else None,
                                  "share_splits_no_commit": float(np.mean(r[:, 3] == 0))}
    return out


def run_condition(cond, clean: dict | None, extra: dict | None = None) -> dict:
    ts = time.time()
    cache: dict = {}
    recs, fit = {}, {}
    for v in VARIANTS:
        pipe = P.build(cond, v, cache)
        recs[v] = P.score(pipe, cond.test)
        fit[v] = {"policy": P.decoder_stats(pipe, cond.test)["policy"] if v != "always_commit" else "always commit",
                  "frame_T": pipe.frame_scaler.temperature}
        C.log(f"{cond.name} {v}: {C.metrics(C.rec_arrays(recs[v]))}")
    C.save_caches(cond)
    arrs = {v: C.rec_arrays(r) for v, r in recs.items()}
    arrs["gaze_only"] = C.gaze_arrays([it.text for it in cond.test], cond.gaze_cpm)
    lams = {}
    if clean is not None:
        th = C.thresholds(clean["items_cal"])
        lams = {"crc": th["crc"], "ltt": th["ltt"], "clean_plugin": clean["items_test"]["lam_old"]}
        for k in ("crc", "ltt"):
            arrs[k] = C.item_arrays(clean["items_test"], th[k])
        arrs["clean_plugin"] = C.item_arrays(clean["items_test"], clean["items_test"]["lam_old"])
        lams["crc_info"] = th
    res = {"n_test": len(cond.test), "ci_unit": cond.scheme + ("" if cond.scheme == "two_way" else f" ({cond.cluster_name})"),
           "point": C.point(arrs), "fit": fit, "clean_thresholds": C.clean(lams), "extra": extra or {},
           "bootstrap": C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 5,
                                    diffs=[d for d in DIFFS if d[0] in arrs and d[1] in arrs])}
    if cond.scheme == "two_way":  # MEG: also the sentence and participant CIs
        res["bootstrap_sentences"] = C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 6, scheme="sentences",
                                                 diffs=[d for d in DIFFS if d[0] in arrs and d[1] in arrs])
        res["bootstrap_participants"] = C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 7, scheme="cluster",
                                                    diffs=[d for d in DIFFS if d[0] in arrs and d[1] in arrs])
    res["seconds"] = round(time.time() - ts, 1)
    C.dump({"arrays": arrs, "cluster": cond.cluster, "sent": cond.sent}, OUT / f"arrays-{cond.name}.json")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default="emg-calib,emg-xsession,emg-xsubject,meg-async,b2t-ours,b2t-published")
    a = ap.parse_args()
    out_p = OUT / "baselines.json"
    res = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    res.setdefault("conditions", {})
    todo = a.conds.split(",")
    b2t = None
    for name in todo:
        if name.startswith("emg"):
            cond = C.emg_condition(name.split("-")[1])
            res["conditions"][name] = run_condition(cond, clean_items(name))
        elif name == "meg-async":
            cond = C.meg_ctx()
            cache: dict = {}
            clean, info, _ = meg_clean_crc(cond, cache)
            C.save_caches(cond)
            res["conditions"][name] = run_condition(cond, clean, {"meg_clean_split": info})
        else:
            b2t = b2t or C.b2t_ctx()
            cond = C.b2t_condition(b2t, name.split("-")[1])
            cond.cached = b2t.cached
            res["conditions"][name] = run_condition(cond, clean_items(name))
        C.dump(res, out_p)
    res["random_split_selective_risk"] = {
        "b2t-ours (M2-13)": split_selective(C.REPO / "experiments/2026-11-11-m2-13-conformal/results/items-b2t-ours.json"),
        "b2t-published (M2-13)": split_selective(C.REPO / "experiments/2026-11-11-m2-13-conformal/results/items-b2t-published.json"),
        "meg-async (G1)": split_selective(C.REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json"),
    }
    C.dump(res, out_p)
    C.log("done")


if __name__ == "__main__":
    main()
