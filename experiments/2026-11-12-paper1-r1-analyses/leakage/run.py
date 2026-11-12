"""R1 item 5 (gap G9), step 2: re-run the affected main numbers with the leakage-cleaned LMs.

Needs ``build_lms.py`` (the cleaned LMs) and ``baselines`` (the original
per-item arrays, for paired differences).

- B2T '25: our decoder with the char LM and word unigram rebuilt without the
  B2T cue sentences and their near variants (``noB2T``); same word-decoder
  settings (tuned on fit with the original LM). Always commit and trust for
  our decoder and for the published-sentence gate (its confidences come from
  our decoder). Day-cluster CIs, paired differences clean - original.
- sEMG (calib, xsession, xsubject): char LM rebuilt without near variants of
  the sEMG fit and test sentences (``noEMG``); LM weight re-tuned on fit-A CER
  (the M6-07 procedure, raw streams). Always commit and trust. Participant-
  cluster CIs.
- Exclusion check with the original LMs: the main numbers on the test items
  whose sentence has no exact or near variant in the LM training text.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/leakage/run.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common as C  # noqa: E402
import policies as P  # noqa: E402
from fidetype.streams.vocab import normalize_text  # noqa: E402

OUT = HERE / "results"
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
LM = Path("C:/Users/zhang/bci-data/lm")
BASE = HERE.parent / "baselines" / "results"


def orig_arrays(name: str) -> dict:
    d = json.loads((BASE / f"arrays-{name}.json").read_text(encoding="utf-8"))["arrays"]
    return {k: {kk: np.asarray(vv, float) for kk, vv in v.items()} for k, v in d.items() if k in ("always_commit", "trust", "gaze_only")}


def sub_arrays(arrs: dict, keep: np.ndarray) -> dict:
    return {k: {kk: vv[keep] for kk, vv in v.items()} for k, v in arrs.items()}


def evaluate(cond, orig: dict, clean_arrs: dict, keep: np.ndarray, stats: dict) -> dict:
    arrs = {f"original:{k}": v for k, v in orig.items() if k != "gaze_only"}
    arrs.update({f"clean_lm:{k}": v for k, v in clean_arrs.items()})
    arrs["gaze_only"] = orig["gaze_only"]
    diffs = [("clean_lm:trust", "original:trust"), ("clean_lm:always_commit", "original:always_commit"),
             ("clean_lm:trust", "gaze_only"), ("clean_lm:trust", "clean_lm:always_commit")]
    res = {"point": C.point(arrs), "decoder": stats,
           "bootstrap": C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 21, diffs=diffs)}
    # Exclusion: only test items whose sentence has no exact / near variant in the LM training text.
    c2 = type(cond)(**vars(cond))
    c2.cluster = np.unique(np.asarray(cond.cluster)[keep], return_inverse=True)[1]
    sa = sub_arrays(arrs, keep)
    res["exclusion"] = {"n_kept": int(keep.sum()), "n_removed": int((~keep).sum()), "point": C.point(sa),
                        "bootstrap": C.bootstrap(sa, c2, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 22,
                                                 diffs=[("original:trust", "gaze_only"), ("original:trust", "original:always_commit")])}
    return res


def run_b2t(rep: dict) -> dict:
    wc = json.loads((LM / "eng_tatoeba_word_counts_noB2T.json").read_text(encoding="utf-8"))
    ctx = C.b2t_ctx(char_lm_path=str(LM / "eng_tatoeba_6gram_mkn_noB2T.npz"), word_counts=wc, tag="noB2T")
    leaked = set(rep["b2t"]["test_trial_sentences_with_near_variant"])
    tat = set()  # exact matches anywhere in Tatoeba English (the 64 of the B2T run)
    bt = ctx.bt
    tat = bt.tatoeba_sentences()
    keep = np.array([(normalize_text(t.cue_sentence) not in leaked) and (t.truth_words not in tat) for t in ctx.test])
    out = {}
    for which in ("ours", "published"):
        ts = time.time()
        cond = C.b2t_condition(ctx, which)
        cond.cached = ctx.cached
        cache: dict = {}
        arrs, stats = {}, {}
        for v in ("always_commit", "trust"):
            pipe = P.build(cond, v, cache)
            arrs[v] = C.rec_arrays(P.score(pipe, cond.test))
            stats[v] = P.decoder_stats(pipe, cond.test)
        C.save_caches(ctx)
        out[f"b2t-{which}"] = evaluate(cond, orig_arrays(f"b2t-{which}"), arrs, keep, stats)
        out[f"b2t-{which}"]["seconds"] = round(time.time() - ts, 1)
        C.log(f"b2t-{which}: " + "; ".join(f"{k} eWPM {v['ewpm']:.3f} wc {v['wrong_commit']:.4f}" for k, v in out[f'b2t-{which}']['point'].items()))
    return out


def run_emg(rep: dict) -> dict:
    from fidetype.eval.metrics import edit_distance
    from fidetype.lm import ctc_prefix_beam_search

    leaked = set(rep["emg"]["test_sentences_with_near_variant"])
    out = {}
    for cname in ("calib", "xsession", "xsubject"):
        ts = time.time()
        cond0 = C.emg_condition(cname, lm_path=str(LM / "eng_tatoeba_6gram_mkn_noEMG.npz"), tag="-noEMG", lm_weight=1.0)
        tune = {}
        for w in cond0.E.CONFIG["lm_weights"]:  # the M6-07 procedure: CER of the top-1 on fit-A, raw streams
            kw = {**cond0.E.CONFIG["beam"], "lm_weight": w}
            tops = [ctc_prefix_beam_search(it.stream(0), cond0.lm, **kw) for it in cond0.A]
            tops = [" ".join(h[0].text.split()) if h else "" for h in tops]
            tune[w] = sum(edit_distance(it.text, h) for it, h in zip(cond0.A, tops)) / sum(len(it.text) for it in cond0.A)
        w = min(tune, key=tune.get)
        cond = C.emg_condition(cname, lm_path=str(LM / "eng_tatoeba_6gram_mkn_noEMG.npz"), tag="-noEMG", lm_weight=w)
        cache: dict = {}
        arrs, stats = {}, {}
        for v in ("always_commit", "trust"):
            pipe = P.build(cond, v, cache)
            arrs[v] = C.rec_arrays(P.score(pipe, cond.test))
            stats[v] = P.decoder_stats(pipe, cond.test)
        C.save_caches(cond)
        keep = np.array([it.text not in leaked for it in cond.test])
        r = evaluate(cond, orig_arrays(f"emg-{cname}"), arrs, keep, stats)
        r["lm_weight_tune_clean"] = tune
        r["lm_weight_clean"] = w
        r["lm_weight_original"] = C.emg_base().old["conditions"][cname]["lm_weight"]
        r["seconds"] = round(time.time() - ts, 1)
        out[f"emg-{cname}"] = r
        C.log(f"emg-{cname} (w {w}): " + "; ".join(f"{k} eWPM {v['ewpm']:.3f} wc {v['wrong_commit']:.4f}" for k, v in r['point'].items()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="emg,b2t")
    a = ap.parse_args()
    rep = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))
    p = OUT / "leakage.json"
    res = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if "emg" in a.parts:
        res.update(run_emg(rep))
        C.dump(res, p)
    if "b2t" in a.parts:
        res.update(run_b2t(rep))
        C.dump(res, p)
    C.log("done")


if __name__ == "__main__":
    main()
