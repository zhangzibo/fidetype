"""P5-07 on SpanishBCBL MEG provenance streams (CC BY-NC 4.0; aggregate numbers only).

Plan: plan.md. Same 5 runs, Paper 1 clean split and control draws as M3-01
(experiments/2026-11-14-m3-01-02-ablations/run_meg.py). No text, no per-trial
rows, no participant ids are written.
Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-trust-v5-candidate/run_meg.py --runs a,b --out meg-a.json
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v5x as X  # noqa: E402

A, C, K, Q, V = X.A, X.C, X.K, X.Q, X.V
STREAMS = Path("C:/Users/zhang/bci-data/streams")
RUNS = ("m1-09-r4b-full-medium", "m1-09-r4b-full-medium-s1", "m1-09-r4b-full-medium-s2", "m1-09-r4b-full", "m1-09-r5-medium")
VAL_A_SENTENCES, SPLIT_SEED, CONTROL_SEED = 6, 0, 0


def with_logprobs(s, lp, tag):
    from fidetype.streams.spec import NeuralTextStream
    assert lp.shape == s.log_probs.shape
    return NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=s.frame_times, vocab=s.vocab, blank_id=s.blank_id,
                            source=s.source + "+" + tag, meta={**s.meta, "audit": tag}, vocab_type=s.vocab_type)


def run_one(run: str) -> dict:
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    t0 = time.time()
    root = STREAMS / f"{run}_provenance"
    orig = NeuralTextStream.__dict__["from_npz"]

    def from_npz(cls, path, _o=orig):
        st = _o.__func__(cls, path)
        st.meta.setdefault("participant", st.meta.get("spanishbcbl.participant"))
        return st
    NeuralTextStream.from_npz = classmethod(from_npz)
    try:
        cond = C.meg_ctx(root=str(root))
    finally:
        NeuralTextStream.from_npz = orig
    pn = [rr.get("subject") or s.meta.get("spanishbcbl.participant") for s, rr in cond.test_raw]
    groups = np.unique(pn, return_inverse=True)[1]
    for d in cond.cached:
        for ex in (A.CACHE5 / d.path.name, X.CACHE6 / d.path.name):
            if ex.exists():
                try:
                    d.d.update(pickle.loads(ex.read_bytes()))
                except Exception:  # noqa: BLE001
                    pass
        d.path = X.CACHE6 / d.path.name
    rng = np.random.default_rng(SPLIT_SEED)
    us = rng.permutation(int(cond.val_sent.max()) + 1)
    a_s = set(us[:VAL_A_SENTENCES].tolist())
    fitA = [it for it, s in zip(cond.val, cond.val_sent) if s in a_s]
    cal = [it for it, s in zip(cond.val, cond.val_sent) if s not in a_s]
    T = cond.test
    X.log(f"meg {run}: fit-A {len(fitA)}, cal {len(cal)}, test {len(T)}")
    truths = [it.text for it in T]
    crng = np.random.default_rng(CONTROL_SEED)
    base = [s for s, _ in cond.test_raw]
    ctl = np.load(STREAMS / f"{run}_beam-controls" / "logprobs_test.npz")
    n = len(base)
    other = []
    for i in range(n):
        same_p = [j for j in range(n) if pn[j] == pn[i] and truths[j] != truths[i]]
        pool = same_p or [j for j in range(n) if truths[j] != truths[i]]
        other.append(int(crng.choice(pool)))
    nulls = {"shuffled_meg": [with_logprobs(s, ctl["shuffled__" + rr["file"]], "shuffled_meg") for s, rr in cond.test_raw],
             "zero_input": [with_logprobs(s, ctl["zeros__" + rr["file"]], "zeros_meg") for s, rr in cond.test_raw],
             "intent_mismatch": [base[j] for j in other],
             "frame_shuffled": [shuffle_stream(s, crng) for s in base],
             "uniform": [uniform_stream(s, crng, 0.05) for s in base]}
    pipe = X.fit_sweep(cond.decode, cond.user, (fitA, fitA), base={"grid": cond.base["grid"]})
    ev = X.evaluate_split(pipe, cal, T, groups, nulls, truths, lambda s, i: cond.decode(s))
    ev.pop("_lam_of")
    ev["stability"] = X.stability(pipe)
    C.save_caches(cond)
    v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
    X.log(f"  {run} done ({time.time() - t0:.0f}s): v4 {v4['n_wrong_commit']}/{v4['n_commit']} eWPM {v4['ewpm']:.2f}; "
          f"v5 {v5['n_wrong_commit']}/{v5['n_commit']} eWPM {v5['ewpm']:.2f}; controls v4/v5: "
          + ",".join(f"{c} {d['v4']['n_commit']}/{d['v5']['n_commit']}" for c, d in ev["controls"].items()))
    return {"run": run, "n_participants_test": int(groups.max()) + 1, **X.clean_eval(ev)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=",".join(RUNS))
    ap.add_argument("--out", default="meg.json")
    a = ap.parse_args()
    X.set_log(X.OUT / f"run-{Path(a.out).stem}.log")
    out_p = X.OUT / a.out
    res = A.load_json(out_p) if out_p.exists() else {"env": A.env_note(), "runs": {}}
    for run in a.runs.split(","):
        if run in res["runs"]:
            continue
        res["runs"][run] = run_one(run)
        X.dump(res, out_p)
    X.log("done")


if __name__ == "__main__":
    main()
