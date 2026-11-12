"""R1 item 7: fix-check numbers (domain review section 6, rows 1, 4, 6; M6).

1. B2T '25 trial and day counts: what exactly is 1,718 / 1,628 / 14 / 15.
2. MEG: why the trust-harness top-1 CER (0.522) differs from the M1-09 beam +
   LM CER (0.475). One-factor-at-a-time decomposition on the same test streams:
   frame temperature, LM weight, insertion bonus, and the CER definition
   (pooled over characters vs mean over instances).
3. sEMG key decoder: accuracy, balanced accuracy, letter accuracy, and both
   chance levels (uniform 1/27, majority class = space).

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/fixchecks/run.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common as C  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"


def b2t_counts() -> dict:
    bt = C.load_module("b2t25run", C.REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
    by_day = defaultdict(Counter)
    for t in trials:
        by_day[t.post_implant_day][t.vocab_size] += 1
    prep = bt.load_json("prep.json")
    main = [t for t in trials if t.vocab_size == 125000]
    fit_days = Counter(t.post_implant_day for t in fit)
    test_days = Counter(t.post_implant_day for t in test)
    return {
        "n_trials_in_file": len(trials),
        "n_days_in_file": len(by_day),
        "days_in_file": sorted(by_day),
        "trials_per_day_by_vocab": {int(d): {str(k): v for k, v in c.items()} for d, c in sorted(by_day.items())},
        "n_trials_50_word": sum(1 for t in trials if t.vocab_size == 50),
        "n_trials_125k": len(main),
        "n_days_125k": len({t.post_implant_day for t in main}),
        "days_125k": sorted({t.post_implant_day for t in main}),
        "n_fit": len(fit), "n_test": len(test),
        "fit_per_day": {int(k): v for k, v in sorted(fit_days.items())},
        "test_per_day": {int(k): v for k, v in sorted(test_days.items())},
        "test_trials_per_day_min_max": [min(test_days.values()), max(test_days.values())],
        "fit_test_sentence_overlap": prep["fit_test_sentence_overlap"],
        "cue_sentences_in_tatoeba_all_125k": prep["cue_sentences_in_tatoeba"],
        "correct_description": ("The file has 1,718 copy-task trials from 15 post-implant days. 90 trials use the 50-word "
                                "vocabulary (all 50 trials of day 25 and 40 of day 27). The analysis uses the other 1,628 trials "
                                "(125,000-word vocabulary), which come from 14 days (27 to 244). Each day's 125k trials are split "
                                "in file order: first half -> fit (812), second half -> test (816)."),
    }


def meg_cer(quick: bool) -> dict:
    from fidetype.eval.metrics import cer, edit_distance

    ctx = C.meg_ctx()
    pipe = C.make_pipe(ctx)
    pipe.fit(ctx.val, ctx.val)  # the harness fit: frame temperature on the first half of val
    T_h = pipe.frame_scaler.temperature
    labels = [r for _, r in ctx.test_raw]
    tg = [r["target_text"] for r in labels]
    beam = json.loads((C.REPO / "experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full-medium/results.json").read_text())
    T_m = float(beam["grid_choice"]["temperature"])
    rows = []
    settings = [
        ("harness: T_harness, lm 0.5, bonus 1.0 (RETUNED, n_best 10)", "harness", 0.5, None),
        ("T = 1 (raw stream), lm 0.5, bonus 1.0", "raw", 0.5, None),
        ("T_harness, lm 0.25, bonus 1.0", "harness", 0.25, None),
        ("T_harness, lm 0.5, bonus 0.0", "harness", 0.5, 0.0),
        ("T_harness, lm 0.25, bonus 0.0 (= M1-09 val choice)", "harness", 0.25, 0.0),
        ("T_M1-09, lm 0.25, bonus 0.0, n_best 10 (M1-09 val-tuned beam)", "m109", 0.25, 0.0),
    ]
    for label, tmode, w, b in settings:
        ts = time.time()
        c2 = C.meg_ctx(lm_weight=w, insertion_bonus=b) if (w, b) != (0.5, None) else ctx
        if tmode == "raw":
            streams = [it.stream(0) for it in ctx.test]
        elif tmode == "harness":
            streams = [pipe.frame_scaler.transform_stream(it.stream(0)) for it in ctx.test]
        else:
            from fidetype.trust.calibration import TemperatureScaler

            sc = TemperatureScaler(T_m) if _ts_accepts_arg() else _scaler(T_m)
            streams = [sc.transform_stream(it.stream(0)) for it in ctx.test]
        tops = []
        for s in streams:
            nb = c2.decode(s)
            tops.append(nb.texts[0] if len(nb) else "")
        C.save_caches(c2)
        per = [cer(t, h) for t, h in zip(tg, tops)]
        rows.append({"setting": label, "frame_T": {"harness": T_h, "raw": 1.0, "m109": T_m}[tmode], "lm_weight": w,
                     "insertion_bonus": 1.0 if b is None else b,
                     "cer_pooled": sum(edit_distance(t, h) for t, h in zip(tg, tops)) / sum(len(t) for t in tg),
                     "cer_mean_over_instances": float(np.mean(per)),
                     "sentence_acc": float(np.mean([t == h for t, h in zip(tg, tops)])),
                     "seconds": round(time.time() - ts, 1)})
        C.log(f"meg cer: {rows[-1]}")
    return {"T_harness": T_h, "T_m109": T_m, "m109_reported_test_cer_mean": 0.475, "g1_reported_harness_cer": 0.522, "rows": rows}


def _ts_accepts_arg() -> bool:
    from fidetype.trust.calibration import TemperatureScaler

    try:
        TemperatureScaler(2.0)
        return True
    except TypeError:
        return False


def _scaler(T: float):
    from fidetype.trust.calibration import TemperatureScaler

    s = TemperatureScaler()
    s.temperature = T
    return s


def emg_decoder() -> dict:
    d = json.loads((C.REPO / "experiments/2026-11-11-emg-toronto/results/decoder.json").read_text(encoding="utf-8"))
    runs = {k: {m: v[m] for m in ("n", "acc", "balanced_acc", "acc_letters", "acc_space", "top5")} for k, v in d["runs"].items()}
    return {"chance": d["chance"], "runs": runs,
            "note": "Key accuracy on day-2 presses, 27 classes. Permuted-label accuracy is below uniform chance; "
                    "all CNN accuracies are below the majority-class rate (space), so balanced accuracy is the fair metric."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="b2t,emg,meg")
    a = ap.parse_args()
    p = OUT / "fixchecks.json"
    res = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if "b2t" in a.parts:
        res["b2t_counts"] = b2t_counts()
        C.dump(res, p)
    if "emg" in a.parts:
        res["emg_decoder"] = emg_decoder()
        C.dump(res, p)
    if "meg" in a.parts:
        res["meg_cer"] = meg_cer(False)
        C.dump(res, p)
    C.log("done")


if __name__ == "__main__":
    main()
