"""P5-35: reproduce the P11-16 LX-FL prefix guard through the native ``calibrate(prefix_score=...)`` path. CPU only.

RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. The P11-16 code and its derived files
(C:/Users/zhang/bci-data/derived/p11-16/) are read only: the window memo is loaded, never saved. The guard file
goes to C:/Users/zhang/bci-data/derived/p5-35/ (outside the repo). The repo gets counts only (results.json).

Steps:
  1. Load the frozen LX-FL model of P11-16 (model fitted on the fit + policy-grid items of the seed split).
  2. Wrap it as a ``FrozenPrefixScore`` (the P11-16 ``Scorer`` rule: FL decode -> 11 features per prefix ->
     sign-constrained logistic). The guard's own top-1 words must equal the FL top-1 words; otherwise no score.
  3. ``fidetype.trust.calibrate`` with the P11-16 / BX-FL settings + ``commit_unit="prefix", prefix_score=``.
  4. Compare with P11-16: threshold, LTT record, null controls, and the decisions on the 1,221 track-test
     prompts (real, time-shuffled, zero EMG). Save, reload and decide again (real prompts).

Run (repo root): python -m fidetype.utils.isolation run --class background --threads 2 -- \
    .venv/Scripts/python.exe experiments/2026-11-21-p5-35-external-prefix-score/run.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
EXP1116 = REPO / "experiments" / "2026-11-21-p11-16-emg-prefix-confidence"
DER = Path("C:/Users/zhang/bci-data/derived")
P1116 = DER / "p11-16"  # READ ONLY
OWN = DER / "p5-35"  # guard file only
ARM = "LX-FL"
KINDS = ("real", "shuffled", "zeros")
# P11-16 reference (results.md, guard-LX-FL.status.json)
REF = {"threshold": 0.86, "commits": 671, "prefix_commits": 592, "wrong": 46, "n_eval": 1221,
       "controls": {"uniform": 0, "shuffled": 5, "user": 0}}


def p1116():
    """The P11-16 runner as a module. Its OUT goes to a temp folder; its memo is never saved."""
    os.environ["P1116_OUT"] = tempfile.mkdtemp(prefix="p5-35-p1116-out-")
    name = "p1116run"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, EXP1116 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    return sys.modules[name]


def lx_score(P, an, md: dict):
    """The frozen LX-FL model of P11-16 as a FrozenPrefixScore (and a counter of top-1 word mismatches)."""
    from fidetype.trust import FrozenPrefixScore

    model = P.PLearned.from_dict(md)
    stats = {"calls": 0, "no_analysis": 0, "word_mismatch": 0}

    def fn(ctx):
        stats["calls"] += 1
        if ctx.log_probs is None:
            return None
        a = an.get(ctx.log_probs, P.DEC)
        r = an.rows(a)
        if r is None or len(r[1]) == 0:
            stats["no_analysis"] += 1
            return None
        X, words = r
        if tuple(words) != tuple(ctx.words):
            stats["word_mismatch"] += 1
            return None
        return model.prob(X)

    dec = json.loads(json.dumps(P.m14().DECODERS[P.DEC], default=str))
    spec = {"model": model.to_dict(), "model_digest": md["digest"], "decoder": {"name": P.DEC, "config": dec},
            "rule": "P11-16 LX: FL decode -> FEATS16 rows per word prefix -> sign-constrained L2 logistic; "
                    "no score if the FL analysis fails or its top-1 words differ from the guard's",
            "fitted_on": "fit + policy-grid items of the calibrate seed split (P11-16)"}
    return FrozenPrefixScore(fn, name="p11-16-LX-FL", version="1", spec=spec), stats


def compare(native: list[dict], ref: list[dict]) -> dict:
    n = len(ref)
    same_commit = sum((a["action"] == "commit") == (b["action"] == "commit") for a, b in zip(native, ref))
    same_text = sum((a["action"] == "commit") == (b["action"] == "commit")
                    and (a["action"] != "commit" or (a["text"] == b["text"] and a["n_words_committed"]
                                                     == b["n_words_committed"] and a["complete"] == b["complete"]))
                    for a, b in zip(native, ref))
    same_action = sum(a["action"] == b["action"] for a, b in zip(native, ref))
    return {"n": n, "commits_native": sum(a["action"] == "commit" for a in native),
            "commits_p11_16": sum(b["action"] == "commit" for b in ref),
            "same_commit_or_not": same_commit, "same_commit_text": same_text, "same_action_3way": same_action,
            "commit_decisions_equal": same_text == n}


def outcome_counts(decs: list[dict], truths: list[str]) -> dict:
    from fidetype.benchmark.safe_wpm import prefix_outcome

    com = pre = wrong = 0
    for x, t in zip(decs, truths):
        if x["action"] != "commit":
            continue
        com += 1
        pre += not x["complete"]
        wrong += not prefix_outcome(x["text"] or "", t, bool(x["complete"]))["correct"]
    return {"commits": com, "prefix_commits": pre, "wrong": wrong}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    import fidetype.trust as ft

    P = p1116()
    M, R, cal, ev = P.setup()
    an = P.make_analyser()  # loads the P11-16 memo (read only)
    an.save = lambda: None  # never write the P11-16 memo
    W = R.p1109().Windows()
    st = json.loads((P1116 / f"guard-{ARM}.status.json").read_text(encoding="utf-8"))
    md = st["model"]
    score, stats = lx_score(P, an, md)

    n = len(cal)
    xs = [W.get(r) for r in cal]
    nulls = [W.get(cal[i], "shuffled") for i in R.null_pick(n)]
    name, ver = M.decoder_meta("BL-FL")
    g = ft.calibrate(xs, [R.intended_truth(r) for r in cal], alpha=R.ALPHA, delta=R.DELTA, input_kind="logits",
                     vocab=an.KV, blank=0, input_scale="log_probs", frame_period=R.FRAME_S,
                     decode_fn=M.GuardFn(an, "BL-FL"), null_inputs=nulls, decoder_name=name + "+LX-prefix",
                     decoder_version=ver, modality="emg", name="p5-35-LX-FL", seed=R.SEED, audit_text=False,
                     commit_unit="prefix", prefix_score=score)
    t_cal = time.time() - t0
    sh = g.sheet
    cf = sh.confidence
    ref_sheet = st["sheet"]
    calib_stats = dict(stats)
    ctl_native = {c.name: c.n_commit for c in sh.controls}
    ctl_ref = {c["name"]: c["n_commit"] for c in ref_sheet["controls"]}

    # decisions on the evaluation prompts
    ref_dec = json.loads((P1116 / f"decisions-{ARM}.json").read_text(encoding="utf-8"))
    truths = [R.intended_truth(r) for r in ev]
    dec_cmp, counts = {}, {}
    native_real: list[dict] = []
    for kind in KINDS:
        ds = []
        for r in ev:
            res = g._decide_quiet(W.get(r, kind))
            ds.append({"action": res.action, "text": res.text, "complete": res.complete,
                       "n_words_committed": res.n_words_committed or 0})
        dec_cmp[kind] = compare(ds, ref_dec[kind])
        counts[kind] = outcome_counts(ds, truths)
        if kind == "real":
            native_real = ds

    # guard file: save, reload with the same score, decide again (real prompts)
    OWN.mkdir(parents=True, exist_ok=True)
    gp = g.save(OWN / f"guard-{ARM}.json")
    g2 = ft.load(gp, decode_fn=M.GuardFn(an, "BL-FL"), prefix_score=score)
    re_ds = []
    for r in ev:
        res = g2._decide_quiet(W.get(r))
        re_ds.append({"action": res.action, "text": res.text, "complete": res.complete,
                      "n_words_committed": res.n_words_committed or 0})
    reload_cmp = compare(re_ds, native_real)
    refused_without = False
    try:
        ft.load(gp, decode_fn=M.GuardFn(an, "BL-FL"))
    except ValueError:
        refused_without = True

    thr_native = float(g.commit_score.threshold)
    checks = {
        "threshold_equal": round(thr_native, 2) == REF["threshold"] == round(float(ref_sheet["commit_threshold"]), 2),
        "ltt_equal": (cf["certify_items"] == ref_sheet["ltt"]["n"]
                      and abs(g.commit_score.certification["empirical_risk"] - ref_sheet["ltt"]["empirical_risk"]) < 1e-12
                      and abs(g.commit_score.certification["ltt_commit_rate"] - ref_sheet["ltt"]["commit_rate"]) < 1e-12),
        "decisions_equal": all(dec_cmp[k]["commit_decisions_equal"] for k in KINDS),
        "real_counts_equal": counts["real"] == {"commits": REF["commits"], "prefix_commits": REF["prefix_commits"],
                                                "wrong": REF["wrong"]},
        "controls_pass": all(c.passed for c in sh.controls),
        "reload_equal": reload_cmp["commit_decisions_equal"] and reload_cmp["same_action_3way"] == reload_cmp["n"],
        "load_refused_without_score": refused_without,
        "config_id": g.config_id.startswith("tcfg-"),
    }
    res = {
        "task": "P5-35", "date": time.strftime("%Y-%m-%d %H:%M"), "research_only": "emg2qwerty, CC BY-NC-SA 4.0",
        "note": "counts only (no text, no per-user value, no id)",
        "config_id": g.config_id, "score_digest": score.digest,
        "threshold": {"native": round(thr_native, 2), "p11_16": round(float(ref_sheet["commit_threshold"]), 2)},
        "ltt": {"native": {"n": cf["certify_items"], "empirical_risk": g.commit_score.certification["empirical_risk"],
                           "p_value": g.commit_score.certification["p_value"],
                           "commit_rate": g.commit_score.certification["ltt_commit_rate"],
                           "no_score": cf["certify_no_score"], "gate_blocked": cf["certify_gate_blocked"]},
                "p11_16": ref_sheet["ltt"]},
        "in_sample_ltt": {"commits": sh.ltt_commits, "wrong": sh.ltt_wrong_commits, "gate_blocked": sh.ltt_gate_blocked},
        "controls": {"native": ctl_native, "p11_16": ctl_ref, "limit": sh.controls[0].allowed},
        "offer_control": None if sh.offers is None else {"passed": sh.offers.get("passed")},
        "frame_temperature": float(g.config.frame_temperature),
        "decisions": dec_cmp, "outcomes_native": counts, "reference": REF, "reload": reload_cmp,
        "score_calls_during_calibrate": calib_stats, "checks": checks, "pass": all(checks.values()),
        "seconds": {"calibrate": round(t_cal, 1), "total": round(time.time() - t0, 1)},
    }
    (out / "results.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": res["pass"], "checks": checks, "threshold": res["threshold"],
                      "controls": res["controls"], "config_id": g.config_id}, indent=1))
    print(str(sh))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
