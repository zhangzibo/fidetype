"""P5-07 on the Toronto sEMG data (CC BY 4.0): Paper 1 fixed split, controls (real zero input), stability.

Plan: plan.md. Same fixed split and control draw as M3-02 (run_emg.py there).
Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-trust-v5-candidate/run_emg.py
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v5x as X  # noqa: E402

A, C, K, Q, V = X.A, X.C, X.K, X.Q, X.V


def merge_cache(cond) -> None:
    for d in cond.cached:
        for extra in (Q.CACHE4 / d.path.name, A.CACHE5 / d.path.name, X.CACHE6 / d.path.name):
            if extra.exists():
                try:
                    d.d.update(pickle.loads(extra.read_bytes()))
                except Exception:  # noqa: BLE001
                    pass
        d.path = X.CACHE6 / d.path.name


def nulls_for(cond, cname):
    """The M3-02 sEMG control draw (Paper 1 audit draw + uniform)."""
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    E, b = cond.E, C.emg_base()
    truths_all = [x.text for x in cond.test]
    arng = np.random.default_rng(E.SEED)
    na = min(len(cond.test), E.CONFIG["audit_n"])
    aud = sorted(arng.choice(len(cond.test), na, replace=False).tolist())
    base = [cond.test[i].stream(0) for i in aud]
    aperm = arng.permutation(na)
    for i in range(na):
        if truths_all[aud[aperm[i]]] == truths_all[aud[i]]:
            aperm[i], aperm[(i + 1) % na] = aperm[(i + 1) % na], aperm[i]
    zero_vec = next(iter(cond.zeros.values()))
    pids = cond.test_who
    nulls = {"real": base, "intent_mismatch": [base[j] for j in aperm],
             "frame_shuffled": [shuffle_stream(s, arng) for s in base],
             "zero_input": [E.make_stream(np.repeat(zero_vec[None, :], len(cond.test_idx[i]), axis=0), b.period, pids[i], cname)
                            for i in aud]}
    nulls["uniform"] = [uniform_stream(s, arng, 0.05) for s in base]
    return nulls, [truths_all[i] for i in aud]


def main() -> None:
    X.set_log(X.OUT / "run-emg.log")
    m302 = A.load_json(A.OUT / "emg.json")
    res: dict = {"env": A.env_note(), "conditions": {}}
    for cname in ("calib", "xsession", "xsubject"):
        t0 = time.time()
        cond = C.emg_condition(cname)
        merge_cache(cond)
        h = len(cond.Bv) // 2
        B1, B2 = cond.Bv[:h], cond.Bv[h:]
        X.log(f"emg-{cname}: fit-A {len(cond.A)}, grid {len(B1)}, cal {len(B2)}, test {len(cond.test)}")
        pipe = X.fit_sweep(cond.decode, cond.user, (cond.A, B1))
        nulls, truths = nulls_for(cond, cname)
        ev = X.evaluate_split(pipe, B2, cond.test, np.asarray(cond.test_who), nulls, truths, lambda s, i: cond.decode(s))
        ev.pop("_lam_of")
        old = m302["conditions"][f"emg-{cname}"]["rows"]["v4 (baseline)"]
        new = ev["arms"]["v4"]
        ev["v4_reproduces_m302"] = (old["n_wrong_commit"], old["n_commit"]) == (new["n_wrong_commit"], new["n_commit"])
        assert ev["v4_reproduces_m302"], (old["n_wrong_commit"], old["n_commit"], new["n_wrong_commit"], new["n_commit"])
        ev["stability"] = X.stability(pipe)
        C.save_caches(cond)
        res["conditions"][f"emg-{cname}"] = X.clean_eval(ev)
        v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
        X.log(f"  emg-{cname} done ({time.time() - t0:.0f}s): v4 {v4['n_wrong_commit']}/{v4['n_commit']} eWPM {v4['ewpm']:.2f}; "
              f"v5 {v5['n_wrong_commit']}/{v5['n_commit']} eWPM {v5['ewpm']:.2f}; controls v5: "
              + ",".join(f"{c} {d['v5']['n_commit']}" for c, d in ev["controls"].items()))
        X.dump(res, X.OUT / "emg.json")
    X.log("done")


if __name__ == "__main__":
    main()
