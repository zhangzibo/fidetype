"""P5-07 on T12 v2 (M3-28 data, aggregate only): validation dry run and trust pool, 240-trial fit sets.

Plan: plan.md. **Exploratory**: the confirmatory M3-28 result does not change;
the trust-pool test set was already used once by M3-28. Same items, user model,
seed and control draws as M3-28 / M2-18 (t12_dryrun.py), plus a zero stand-in.
Writes aggregate numbers only (no text, no signals).

Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-trust-v5-candidate/run_t12.py --part val
  ... --part pool
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v5x as X  # noqa: E402

A, C, K, Q, V = X.A, X.C, X.K, X.Q, X.V
_spec = importlib.util.spec_from_file_location("m218_t12", X.REPO / "experiments/2026-11-13-m2-18-empty-commits/t12_dryrun.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
R = M.R


def run(part: str) -> None:
    from fidetype.interact.simulated_user import UserConfig
    t0 = time.time()
    D = R.Data("logprobs-val" if part == "val" else "logprobs")
    bt = R.load_b2t25()
    dec = R.decoders(bt)
    S = D.sessions
    p = "val" if part == "val" else "pool"
    fitA, _ = D.items(p, [s for s in S if D.role[s] == "fit_a"])
    cal, _ = D.items(p, [s for s in S if D.role[s] == "calibration"])
    test, test_sess = D.items(p, [s for s in S if D.role[s] == "test"])
    user = UserConfig.aac_gaze(chars_per_min=D.prep["speech_rate_decoder_train"]["chars_per_min"])
    X.log(f"t12 {part}: fit-A {len(fitA)}, cal {len(cal)}, test {len(test)}")
    ctl = M.controls(test, M.CFG["controls_seed"])
    nulls = {k: [it.stream(0) for it in v] for k, v in ctl.items()}
    nulls["zero_standin"] = [A.zero_standin(it.stream(0)) for it in test]
    truths = [it.text for it in test]
    pipe = X.fit_sweep(dec.words_fn, user, (fitA, fitA), base={"seed": M.CFG["trust"]["seed"]})
    ev = X.evaluate_split(pipe, cal, test, np.array(test_sess), nulls, truths, lambda s, i: dec.words_fn(s))
    ev.pop("_lam_of")
    ev["stability"] = X.stability(pipe)
    ev["m328_reference"] = {"val": "test 22 commits (11 wrong), uniform 335/400", "pool": "test 1 commit (0 wrong)"}[part]
    res = {"part": part, "env": A.env_note(), "exploratory": True, **X.clean_eval(ev)}
    X.dump(res, X.OUT / f"t12-{part}.json")
    v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
    X.log(f"  t12 {part} done ({time.time() - t0:.0f}s): v4 {v4['n_wrong_commit']}/{v4['n_commit']} eWPM {v4['ewpm']:.2f}; "
          f"v5 {v5['n_wrong_commit']}/{v5['n_commit']} eWPM {v5['ewpm']:.2f}; controls v4/v5: "
          + ",".join(f"{c} {d['v4']['n_commit']}/{d['v5']['n_commit']}" for c, d in ev["controls"].items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["val", "pool"])
    a = ap.parse_args()
    X.set_log(X.OUT / f"run-t12-{a.part}.log")
    run(a.part)
    X.log("done")


if __name__ == "__main__":
    main()
