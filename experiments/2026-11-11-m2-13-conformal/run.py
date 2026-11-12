"""M2-13: conformal risk control (CRC) and Learn-then-Test (LTT) for the COMMIT threshold.

CPU only (2 threads). Stages:

1. ``b2t``: rebuild the M6-06 trust pipelines on Brain-to-Text '25 (our
   decoder (c) and the published-sentence gate (q)), fitted exactly as in
   M6-06 on the fit half. For every fit and test trial, save the commit
   score, the commit / fallback loss, and the eWPM terms of both outcomes
   (COMMIT or the non-commit action). ``results/items-b2t-*.json``.
2. ``meg``: the same for the MEG M1-15 full-r1 streams (trust policy fitted
   on val as in ewpm_check.py). ``results/items-meg-full-r1.json``.
3. ``splits``: 200 random calibration / test splits of each test set.
   Methods: old (the fixed M6-06 / M1-15 gate), plug-in re-tune, CRC,
   CRC + eWPM tune, LTT. Also a one-shot "earlier data" row: calibrate on
   the fit half, test on the test half. ``results/splits.json``.
4. ``tables``: ``results/tables.md``.

Run (repo root):

    .venv\\Scripts\\python.exe -I experiments/2026-11-11-m2-13-conformal/run.py
    ... run.py --stages splits,tables     # reuse the item files
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
import importlib.util
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.eval.ewpm import correct_words_strict  # noqa: E402
from fidetype.trust.policy import DecisionPolicy  # noqa: E402
from fidetype.trust.risk_control import commit_calibration_data, crc_threshold, ltt_threshold  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
ALPHA = CONFIG["alpha"]
DELTA = CONFIG["delta"]
LOG = OUT / "run.log"


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fnum(x):
    if isinstance(x, float) and not math.isfinite(x):
        return "inf" if x > 0 else "-inf" if x < 0 else "nan"
    return x


def item_table(pipe, items) -> dict:
    """Per-item arrays for both outcomes of the commit decision."""
    cache: dict = {}
    pol = pipe.policy
    lo = DecisionPolicy(replace(pol.config, commit_p=-math.inf), use_guard=pol.use_guard)
    hi = DecisionPolicy(replace(pol.config, commit_p=math.inf), use_guard=pol.use_guard)
    rec_c = pipe.run_items(items, lo, cache)
    rec_f = pipe.run_items(items, hi, cache)
    rec_o = pipe.run_items(items, pol, cache)
    inputs = [cache[(id(it), 0)].inputs for it in items]
    s, c, f = commit_calibration_data(pol, inputs, [it.text for it in items])
    elig = np.isfinite(s)
    # Checks: eligibility and losses agree with the simulated user.
    assert all((r.actions[0] == "COMMIT") == e for r, e in zip(rec_c, elig)), "eligibility mismatch"
    assert all(bool(r.wrong_commit) == bool(ci) for r, ci, e in zip(rec_c, c, elig) if e), "commit loss mismatch"
    assert all(bool(r.wrong_commit) == bool(fi) or not r.wrong_commit for r, fi in zip(rec_f, f)), "fallback loss"
    lam_old = pol.config.commit_p
    mix_ok = all((ro.time_s == (rc.time_s if si >= lam_old else rf.time_s)) for ro, rc, rf, si in zip(rec_o, rec_c, rec_f, s))
    assert mix_ok, "old-gate records are not the commit/fallback mix"
    return {
        "lam_old": lam_old,
        "policy_config": {k: fnum(v) for k, v in pol.config.__dict__.items()},
        "score": [fnum(float(x)) for x in s],
        "loss_c": c.tolist(),
        "loss_f": f.tolist(),
        "wc_c": [float(r.wrong_commit) for r in rec_c],
        "wc_f": [float(r.wrong_commit) for r in rec_f],
        "time_c": [r.time_s for r in rec_c],
        "time_f": [r.time_s for r in rec_f],
        "words_c": [correct_words_strict(r) for r in rec_c],
        "words_f": [correct_words_strict(r) for r in rec_f],
        "silent_c": [float(r.silent_error) for r in rec_c],
        "silent_f": [float(r.silent_error) for r in rec_f],
        "n": len(items),
    }


def stage_b2t() -> None:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig

    t0 = time.time()
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
    best = tune["best"]
    dec = bt.Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in fit + test}
    mk = lambda ts: [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in ts]  # noqa: E731
    fi, ti = mk(fit), mk(test)
    days_fit = [t.post_implant_day for t in fit]
    days_test = [t.post_implant_day for t in test]
    for name, fn in (("b2t-ours", dec.words_fn), ("b2t-published", dec.published_plus_fn)):
        ts = time.time()
        pipe = TrustPipeline(fn, HarnessConfig(seed=bt.SEED, user_config=user, max_wrong_commit=bt.CONFIG["max_wrong_commit"]))
        pipe.fit(fi, fi)
        res = {"fit": item_table(pipe, fi), "test": item_table(pipe, ti), "fit_report": {k: fnum(v) if isinstance(v, float) else v
                                                                                     for k, v in pipe.fit_report.items()},
               "days_fit": days_fit, "days_test": days_test}
        old = res["test"]
        s = np.array([float(x) for x in old["score"]])
        on = s >= old["lam_old"]
        wc = np.where(on, old["wc_c"], old["wc_f"]).mean()
        ew = 60 * np.where(on, old["words_c"], old["words_f"]).sum() / np.where(on, old["time_c"], old["time_f"]).sum()
        log(f"{name}: lam_old {old['lam_old']} test wrong-commit {wc:.4f} eWPM {ew:.3f} "
            f"eligible {np.isfinite(s).mean():.3f} ({time.time() - ts:.0f}s)")
        (OUT / f"items-{name}.json").write_text(json.dumps(res), encoding="utf-8")
    log(f"b2t done ({time.time() - t0:.0f}s)")


def stage_meg() -> None:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import RETUNED, CharNgramLM, ctc_prefix_beam_search
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    m2 = load_module("m2ow", REPO / "experiments/2026-11-08-m2-offer-words/run.py")
    root = Path(CONFIG["meg_streams"])

    def load_split(split):
        rows = [json.loads(x) for x in (root / split / "labels.jsonl").read_text(encoding="utf-8").splitlines() if x]
        return [(NeuralTextStream.from_npz(root / split / r["file"]), r) for r in rows]

    lm = CharNgramLM.load(m2.SPA_LM)
    kw = {**dict(RETUNED), "n_best": 10, "lm_weight": 0.5}

    def dec(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm, **kw), stream.meta, confidence_variant="frame")

    val_raw, test_raw = load_split("val"), load_split("test")
    val = [Item(s, r["target_text"]) for s, r in val_raw]
    test = [Item(s, r["target_text"]) for s, r in test_raw]
    user = UserConfig.aac_gaze()
    pipe = TrustPipeline(dec, HarnessConfig(grid=m2.BASE_GRID, max_wrong_commit=m2.MAX_WRONG_COMMIT, user_config=user,
                                            seed=m2.SEED), {})
    pipe.fit(val, val)
    log(f"meg: fitted on {len(val)} val ({time.time() - t0:.0f}s); policy {pipe.policy.config}")
    res = {"fit": item_table(pipe, val), "test": item_table(pipe, test),
           "fit_report": {k: fnum(v) if isinstance(v, float) else v for k, v in pipe.fit_report.items()},
           "participants_test": [r.get("participant") for _, r in test_raw]}
    t = res["test"]
    s = np.array([float(x) for x in t["score"]])
    log(f"meg: eligible {np.isfinite(s).mean():.3f}, top-1 right among eligible "
        f"{1 - np.mean(np.array(t['loss_c'])[np.isfinite(s)]) if np.isfinite(s).any() else float('nan'):.3f}, "
        f"top-1 right overall {1 - np.mean(t['loss_c']):.4f}")
    (OUT / "items-meg-full-r1.json").write_text(json.dumps(res), encoding="utf-8")
    log(f"meg done ({time.time() - t0:.0f}s)")


# ---------------------------------------------------------------------------
# Split analysis
# ---------------------------------------------------------------------------


class Arr:
    def __init__(self, d: dict):
        self.s = np.array([float(x) for x in d["score"]])
        for k in ("loss_c", "loss_f", "wc_c", "wc_f", "time_c", "time_f", "words_c", "words_f", "silent_c", "silent_f"):
            setattr(self, k, np.asarray(d[k], dtype=np.float64))
        self.lam_old = float(d["lam_old"])

    def metrics(self, idx: np.ndarray, lam: float) -> dict:
        on = self.s[idx] >= lam
        wc = np.where(on, self.wc_c[idx], self.wc_f[idx])
        t = np.where(on, self.time_c[idx], self.time_f[idx])
        w = np.where(on, self.words_c[idx], self.words_f[idx])
        se = np.where(on, self.silent_c[idx], self.silent_f[idx])
        return {"wrong_commit": float(wc.mean()), "commit_rate": float(on.mean()),
                "ewpm": float(60 * w.sum() / t.sum()), "silent_error": float(se.mean())}

    def tune(self, idx: np.ndarray, lam_min: float = -math.inf, max_risk: float | None = None) -> float:
        """argmax eWPM on idx over the candidate thresholds >= lam_min (and with risk <= max_risk); ties -> larger."""
        s = self.s[idx]
        cands = np.r_[np.unique(s[np.isfinite(s)]), math.inf]
        cands = cands[cands >= lam_min][::-1]  # safest first: ties keep the larger threshold
        best, best_e = math.inf, -1.0
        for lam in cands:
            m = self.metrics(idx, lam)
            if max_risk is not None and m["wrong_commit"] > max_risk + 1e-12:
                continue
            if m["ewpm"] > best_e + 1e-12:
                best, best_e = float(lam), m["ewpm"]
        return best


def thresholds(a: Arr, cal: np.ndarray) -> dict[str, float]:
    s, c, f = a.s[cal], a.loss_c[cal], a.loss_f[cal]
    crc = crc_threshold(s, c, ALPHA, f).threshold
    return {
        "old": a.lam_old,
        "plugin": a.tune(cal, max_risk=ALPHA),
        "crc": crc,
        "crc_tune": a.tune(cal, lam_min=crc),
        "ltt": ltt_threshold(s, c, ALPHA, DELTA, f).threshold,
    }


def summarise(rows: list[dict]) -> dict:
    out = {}
    for k in rows[0]:
        v = np.array([r[k] for r in rows], dtype=np.float64)
        out[k] = {"mean": float(v.mean()), "p95": float(np.quantile(v, 0.95)), "p05": float(np.quantile(v, 0.05)),
                  "se": float(v.std(ddof=1) / math.sqrt(len(v)))}
    wc = np.array([r["wrong_commit"] for r in rows])
    out["p_exceed_alpha"] = float(np.mean(wc > ALPHA + 1e-12))
    return out


def stage_splits() -> dict:
    rng = np.random.default_rng(CONFIG["seed"])
    res: dict = {"alpha": ALPHA, "delta": DELTA, "reps": CONFIG["reps"], "datasets": {}}
    for name in CONFIG["datasets"]:
        p = OUT / f"items-{name}.json"
        if not p.exists():
            log(f"splits: {name} missing, skipped")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        a_fit, a_test = Arr(d["fit"]), Arr(d["test"])
        n = len(a_test.s)
        ds: dict = {"n_test": n, "n_fit": len(a_fit.s), "lam_old": a_test.lam_old,
                    "eligible_rate": float(np.isfinite(a_test.s).mean()),
                    "top1_right_rate": float(1 - a_test.loss_c.mean()),
                    "fit_report": d.get("fit_report"), "splits": {}}
        # Reference rows on the whole test set.
        allidx = np.arange(n)
        ds["whole_test"] = {"old": a_test.metrics(allidx, a_test.lam_old),
                            "always_commit_eligible": a_test.metrics(allidx, -math.inf),
                            "never_commit": a_test.metrics(allidx, math.inf)}
        # One shot: calibrate on the fit half (earlier trials of each day), test on the test half.
        th = thresholds(a_fit, np.arange(len(a_fit.s)))
        th["old"] = a_test.lam_old
        ds["earlier_data"] = {k: {"threshold": fnum(v), **a_test.metrics(allidx, v)} for k, v in th.items()}
        for n_cal in CONFIG["n_cal"]:
            if n_cal >= n:
                continue
            per = {k: [] for k in ("old", "plugin", "crc", "crc_tune", "ltt")}
            lam = {k: [] for k in per}
            for _ in range(CONFIG["reps"]):
                perm = rng.permutation(n)
                cal, tst = perm[:n_cal], perm[n_cal:]
                th = thresholds(a_test, cal)
                for k, v in th.items():
                    per[k].append(a_test.metrics(tst, v))
                    lam[k].append(v)
            ds["splits"][str(n_cal)] = {
                k: {**summarise(per[k]), "threshold_median": fnum(float(np.median(lam[k]))),
                    "never_commit_share": float(np.mean(np.isinf(lam[k])))}
                for k in per
            }
            r = ds["splits"][str(n_cal)]
            log(f"{name} n_cal {n_cal}: " + "; ".join(
                f"{k} wc {v['wrong_commit']['mean']:.4f}/p95 {v['wrong_commit']['p95']:.4f} eWPM {v['ewpm']['mean']:.2f}"
                for k, v in r.items()))
        res["datasets"][name] = ds
    (OUT / "splits.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


NAMES = {"old": "old gate (fixed, M6-06 / M1-15 fit)", "plugin": "plug-in re-tune on cal (empirical <= alpha)",
         "crc": "CRC", "crc_tune": "CRC + eWPM tune (lambda >= lambda_CRC)", "ltt": f"LTT (delta {DELTA}, binomial)"}


def stage_tables() -> None:
    res = json.loads((OUT / "splits.json").read_text(encoding="utf-8"))
    L = [f"# M2-13 tables (alpha {ALPHA}, delta {DELTA}, {res['reps']} random splits)", ""]
    for name, ds in res["datasets"].items():
        L += [f"## {name}", "",
              f"Test trials {ds['n_test']}; old commit_p {ds['lam_old']}; eligible (other rules allow COMMIT) "
              f"{ds['eligible_rate']:.3f}; top-1 right {ds['top1_right_rate']:.3f}.", ""]
        w = ds["whole_test"]
        L += ["Whole test set: " + "; ".join(f"{k}: wrong-commit {v['wrong_commit']:.4f}, commit {v['commit_rate']:.3f}, "
                                             f"eWPM {v['ewpm']:.2f}" for k, v in w.items()), ""]
        for n_cal, rows in ds["splits"].items():
            L += [f"### Random splits, n_cal = {n_cal}, n_test = {ds['n_test'] - int(n_cal)}", "",
                  "| method | wrong-commit mean ± se | p95 | P(> alpha) | commit rate | eWPM mean [p05, p95] | silent error | median commit_p | never-commit share |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for k, v in rows.items():
                L.append(f"| {NAMES[k]} | {v['wrong_commit']['mean']:.4f} ± {v['wrong_commit']['se']:.4f} | "
                         f"{v['wrong_commit']['p95']:.4f} | {v['p_exceed_alpha']:.2f} | {v['commit_rate']['mean']:.3f} | "
                         f"{v['ewpm']['mean']:.2f} [{v['ewpm']['p05']:.2f}, {v['ewpm']['p95']:.2f}] | "
                         f"{v['silent_error']['mean']:.4f} | {v['threshold_median']} | {v['never_commit_share']:.2f} |")
            L.append("")
        L += ["### Earlier data: calibrate on the fit half, test on the whole test half (one shot, not exchangeable)", "",
              "| method | commit_p | wrong-commit | commit rate | eWPM | silent error |", "|---|---|---|---|---|---|"]
        for k, v in ds["earlier_data"].items():
            thr = v["threshold"]
            L.append(f"| {NAMES[k]} | {thr if isinstance(thr, str) else round(thr, 4)} | {v['wrong_commit']:.4f} | "
                     f"{v['commit_rate']:.3f} | {v['ewpm']:.2f} | {v['silent_error']:.4f} |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")
    log("tables written")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="b2t,meg,splits,tables")
    st = ap.parse_args().stages.split(",")
    if "b2t" in st:
        stage_b2t()
    if "meg" in st:
        stage_meg()
    if "splits" in st:
        stage_splits()
    if "tables" in st:
        stage_tables()
    log("done")


if __name__ == "__main__":
    main()
