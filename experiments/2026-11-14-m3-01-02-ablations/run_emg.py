"""M3-02 ablations on the Toronto sEMG data (CC BY 4.0): Paper 1 fixed split + controls.

Plan: plan.md. Conditions calib / xsession / xsubject. Fixed split = Paper 1
(fit-A temperatures + conformal, fit-B1 policy grid, fit-B2 clean calibration).
Controls = the Paper 1 sEMG audit draw (seed, audit_n 200): other sentence
(intent mismatch), frame-shuffled, the decoder's real zero-input output,
plus uniform (new, drawn after the Paper 1 draws).

Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-m3-01-02-ablations/run_emg.py
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abl as A  # noqa: E402

C, K, Q = A.C, A.K, A.Q


def merge_cache(cond) -> None:
    for d in cond.cached:
        for extra in (Q.CACHE4 / d.path.name, A.CACHE5 / d.path.name):
            if extra.exists():
                try:
                    d.d.update(pickle.loads(extra.read_bytes()))
                except Exception:  # noqa: BLE001
                    pass
        d.path = A.CACHE5 / d.path.name


def main() -> None:
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    A.set_log(A.OUT / "run-emg.log")
    res: dict = {"env": A.env_note(), "conditions": {}}
    for cname in ("calib", "xsession", "xsubject"):
        t0 = time.time()
        cond = C.emg_condition(cname)
        merge_cache(cond)
        E, b = cond.E, C.emg_base()
        h = len(cond.Bv) // 2
        B1, B2 = cond.Bv[:h], cond.Bv[h:]
        A.log(f"emg-{cname}: fit-A {len(cond.A)}, grid {len(B1)}, cal {len(B2)}, test {len(cond.test)}")
        ft = A.fit_four(cond.decode, cond.user, (cond.A, B1), B2, cond.test)
        pipes, tabs = ft["pipes"], ft["tabs"]
        blk = A.gate_block(pipes["c1g1"], cond.test)
        rows = A.arm_rows(tabs, test_groups=np.asarray(cond.test_who), gate_blk=blk)
        r = {"rows": rows, "T": {k: v["T"] for k, v in tabs.items()}, "policy": {k: v["policy"] for k, v in tabs.items()},
             "gate_blocked_test_items": int(blk.sum()), "lambdas": {k: C.clean(A.lambdas(v["cal"])) for k, v in tabs.items()}}
        # controls (Paper 1 sEMG audit draw)
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
        truths = [truths_all[i] for i in aud]
        lams = {k: A.lambdas(v["cal"]) for k, v in tabs.items()}
        r["controls"] = A.control_rows(pipes, lams, nulls, lambda s, i: cond.decode(s), truths, groups=[pids[i] for i in aud])
        C.save_caches(cond)
        res["conditions"][f"emg-{cname}"] = r
        v = rows["v4 (baseline)"]
        A.log(f"  emg-{cname} done ({time.time() - t0:.0f}s): v4 wc {v['wrong_commit']:.4f} commit {v['commit_rate']:.3f} "
              f"eWPM {v['ewpm']:.2f}; controls v4 " + ",".join(f"{c} {x['n_commit']}" for c, x in r["controls"]["v4 (baseline)"].items()))
        A.dump(res, A.OUT / "emg.json")
    A.log("done")


if __name__ == "__main__":
    main()
