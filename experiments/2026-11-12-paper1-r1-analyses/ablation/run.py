"""R1 item 3: unified ablation across all six conditions (gap G5; methods Major 8; domain M7).

Conditions: B2T '25 ours and published gate, MEG async, sEMG calib / xsession /
xsubject. Variants (see ``policies.py``): trust (full), no calibration,
temperature only on the confidence (decode the raw stream; sentence
temperature on), temperature only on the beam (frame temperature before the
beam; no sentence temperature), no guard, no conformal sets, OFFER_WORDS off /
on (both on BASE_GRID), and always commit at the trust temperature (decoder
reference). CRC on / off comes from ``clean-drift`` (plug-in gate of the fit-A
pipeline vs CRC on the clean calibration items, same test items).

LM weight after calibration: the sEMG LM weight was tuned on raw fit-A streams
(M6-07). ``lm_retuned`` re-tunes it on fit-A streams scaled by the fitted frame
temperature (CER of the top-1, grid 0.5 / 1 / 1.5 / 2 / 3), then refits trust
and always commit. MEG: ``lm_retuned`` uses the M1-09 val-tuned beam on
calibrated streams (lm_weight 0.25, insertion bonus 0; the 0.475 decoder)
instead of the harness setting (0.5, 1.0).

CIs: eWPM and wrong-commit of each variant and the paired difference to the
full layer, at the condition's unit (B2T day, sEMG participant, MEG two-way).

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/ablation/run.py --conds ...
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

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
VARIANTS = ("trust", "always_commit", "no_calib", "conf_only", "beam_only", "no_guard", "no_conformal", "ow_off_base", "ow_on")


def run_variants(cond, variants, prefix: str = "") -> tuple[dict, dict]:
    cache: dict = {}
    arrs, stats = {}, {}
    for v in variants:
        ts = time.time()
        pipe = P.build(cond, v, cache)
        recs = P.score(pipe, cond.test)
        arrs[prefix + v] = C.rec_arrays(recs)
        st = P.decoder_stats(pipe, cond.test)
        st["fit_report"] = C.clean({k: v2 for k, v2 in pipe.fit_report.items() if not isinstance(v2, dict)})
        st["seconds"] = round(time.time() - ts, 1)
        stats[prefix + v] = st
        m = C.metrics(arrs[prefix + v])
        C.log(f"{cond.name} {prefix + v}: eWPM {m['ewpm']:.3f} wc {m['wrong_commit']:.4f} commit {m['commit_rate']:.3f} "
              f"CER {st['cer']:.3f} T {st['frame_T']:.2f} ({st['seconds']}s)")
        C.save_caches(cond)
    return arrs, stats


def retune_emg(cond) -> tuple[float, dict]:
    """Re-tune the sEMG LM weight on fit-A streams scaled by the fitted frame temperature."""
    from fidetype.eval.metrics import edit_distance
    from fidetype.lm import ctc_prefix_beam_search

    pipe = P.build(cond, "trust", {})
    T = pipe.frame_scaler
    A = cond.A
    out = {}
    for w in CONFIG["emg_lm_weights"]:
        kw = {**cond.E.CONFIG["beam"], "lm_weight": w}
        tops = [ctc_prefix_beam_search(T.transform_stream(it.stream(0)), cond.lm, **kw) for it in A]
        tops = [" ".join(h[0].text.split()) if h else "" for h in tops]
        out[w] = sum(edit_distance(it.text, h) for it, h in zip(A, tops)) / sum(len(it.text) for it in A)
    best = min(out, key=out.get)
    return best, {"frame_T": T.temperature, "fitA_cer_by_weight_calibrated": out, "chosen": best,
                  "original_weight_raw_tuned": cond.lm_weight}


def crc_rows(cond_name: str):
    p = HERE.parent / "clean-drift" / "results" / (f"items-{cond_name.split('-')[1]}-alternate.json" if cond_name.startswith("b2t")
                                                   else f"items-{cond_name}.json")
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    th = C.thresholds(d["items_cal"])
    return {"crc_off (fit-A plug-in)": C.item_arrays(d["items_test"], d["items_test"]["lam_old"]),
            "crc_on (clean CRC)": C.item_arrays(d["items_test"], th["crc"])}


def summarise(cond, arrs, stats, extra=None) -> dict:
    diffs = [(k, "trust") for k in arrs if k != "trust" and not k.startswith("crc_")]
    diffs += [("ow_on", "ow_off_base")] if "ow_on" in arrs else []
    diffs += [("crc_on (clean CRC)", "crc_off (fit-A plug-in)")] if "crc_on (clean CRC)" in arrs else []
    diffs += [("lm_retuned:trust", "lm_retuned:always_commit")] if "lm_retuned:trust" in arrs else []
    diffs += [(k, "gaze_only") for k in ("trust", "no_calib", "lm_retuned:trust") if k in arrs]
    res = {"n_test": len(cond.test), "ci_unit": cond.scheme, "point": C.point(arrs), "decoder": stats, "extra": extra or {},
           "bootstrap": C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 9, diffs=diffs)}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default="emg-calib,emg-xsession,emg-xsubject,meg-async,b2t-ours,b2t-published")
    a = ap.parse_args()
    out_p = OUT / f"ablation-{a.conds.replace(',', '+')}.json"
    res: dict = {"conditions": {}}
    b2t = None
    for name in a.conds.split(","):
        ts = time.time()
        extra: dict = {}
        if name.startswith("emg"):
            cond = C.emg_condition(name.split("-")[1])
            arrs, stats = run_variants(cond, VARIANTS)
            w, info = retune_emg(cond)
            extra["lm_retune"] = info
            cond2 = C.emg_condition(name.split("-")[1], lm_weight=w)
            a2, s2 = run_variants(cond2, ("trust", "always_commit", "no_calib"), prefix="lm_retuned:")
            arrs.update(a2)
            stats.update(s2)
        elif name == "meg-async":
            cond = C.meg_ctx()
            arrs, stats = run_variants(cond, VARIANTS)
            cond2 = C.meg_ctx(lm_weight=CONFIG["meg_retuned"]["lm_weight"], insertion_bonus=CONFIG["meg_retuned"]["insertion_bonus"])
            a2, s2 = run_variants(cond2, ("trust", "always_commit"), prefix="lm_retuned:")
            arrs.update(a2)
            stats.update(s2)
            extra["lm_retune"] = CONFIG["meg_retuned"]
        else:
            b2t = b2t or C.b2t_ctx()
            cond = C.b2t_condition(b2t, name.split("-")[1])
            cond.cached = b2t.cached
            arrs, stats = run_variants(cond, VARIANTS)
        cr = crc_rows(name)
        if cr:
            arrs.update(cr)
        arrs["gaze_only"] = C.gaze_arrays([it.text for it in cond.test], cond.gaze_cpm)
        res["conditions"][name] = summarise(cond, arrs, stats, extra)
        res["conditions"][name]["seconds"] = round(time.time() - ts, 1)
        C.dump(res, out_p)
    C.log("done")


if __name__ == "__main__":
    main()
