"""P5-07 repeated splits: B2T '25 (R3 generator, r = 0..49, both decoders) and sEMG (R3 generator, seed 3 + 100).

Plan: plan.md. Every split is refitted (sweep + all arms); no test-time controls
here (the fixed splits carry them). Per-split aggregate records go to
C:/Users/zhang/bci-data/cache/trust-v5/splits/ (outside the repo); the summary
goes to results/splits.json (stage ``summary``).

Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-trust-v5-candidate/run_splits.py --cond b2t-ours --worker 0 --nworkers 2
  ... --cond emg-calib ; ... --stage summary
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v5x as X  # noqa: E402

A, C, K, Q, V = X.A, X.C, X.K, X.Q, X.V
TAB = X.CACHE6 / "splits"
TAB.mkdir(exist_ok=True)
R3CFG = json.loads((X.REPO / "experiments/2026-11-12-paper1-r3-analyses/repeated-splits/config.json").read_text(encoding="utf-8"))
R_B2T, R_EMG = 50, 50


def redirect(router) -> None:
    """New decodes of this task go to CACHE6 (the R3/R4 cache files are read, never written)."""
    orig_get = router.get

    def get(T, _g=orig_get):
        dc = _g(T)
        if not getattr(dc, "_v5", False):
            p6 = X.CACHE6 / dc.path.name
            if p6.exists():
                try:
                    dc.d.update(pickle.loads(p6.read_bytes()))
                except Exception:  # noqa: BLE001
                    pass
            dc.path = p6
            dc._v5 = True
        return dc
    router.get = get


def run_b2t(which: str, worker: int, nworkers: int) -> None:
    ctx, router, trials, items = Q.b2t_env(R3CFG["frame_T_snap_b2t"])
    redirect(router)
    fn = Q.decoder_fn(ctx, which)
    sp = Q.splits200()[:R_B2T]
    mine = [s for s in sp if s["r"] % nworkers == worker]
    for s in mine:
        p = TAB / f"b2t-{which}-{s['r']:03d}.json"
        if p.exists():
            continue
        t0 = time.time()
        fa = [items[i] for i in s["A"]]
        pipe = X.fit_sweep(fn, ctx.user, (fa, fa))
        ev = X.evaluate_split(pipe, [items[i] for i in s["cal"]], [items[i] for i in s["test"]])
        ev.pop("_lam_of")
        row = {"r": s["r"], "cond": f"b2t-{which}", "T_fitted": K.TState.fitted, **X.split_row(ev)}
        C.dump(row, p)
        router.save()
        v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
        X.log(f"b2t-{which} r {s['r']}: T {ev['T']:.2f}; v4 {v4['wrong_commit']:.4f} ({v4['n_commit']}) eWPM {v4['ewpm']:.2f}; "
              f"v5 {v5['wrong_commit']:.4f} ({v5['n_commit']}) eWPM {v5['ewpm']:.2f} ({time.time() - t0:.0f}s)")
    router.save()


def run_emg(cname: str) -> None:
    K.install_snap(R3CFG["frame_T_snap_emg"])
    cond = C.emg_condition(cname)
    router = K.TRouter(cond.decode.fn, f"emg-{cname}-w{cond.lm_weight}")
    redirect(router)
    pool = list(cond.A) + list(cond.Bv)
    who = np.asarray(cond.fit_who)
    rng = np.random.default_rng(R3CFG["seed"] + 100)
    for r in range(R_EMG):
        A_, B1, B2 = [], [], []
        for pid in sorted(set(who.tolist())):
            idx = np.where(who == pid)[0]
            q = rng.permutation(idx)
            na, nb = int(round(idx.size / 2)), int(round(idx.size / 4))
            A_ += q[:na].tolist()
            B1 += q[na:na + nb].tolist()
            B2 += q[na + nb:].tolist()
        A_, B1, B2 = (rng.permutation(np.array(x)).tolist() for x in (A_, B1, B2))
        p = TAB / f"emg-{cname}-{r:03d}.json"
        if p.exists():
            continue
        t0 = time.time()
        pipe = X.fit_sweep(router, cond.user, ([pool[i] for i in A_], [pool[i] for i in B1]), base=dict(cond.base))
        ev = X.evaluate_split(pipe, [pool[i] for i in B2], cond.test)
        ev.pop("_lam_of")
        C.dump({"r": r, "cond": f"emg-{cname}", "T_fitted": K.TState.fitted, **X.split_row(ev)}, p)
        router.save()
        v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
        X.log(f"emg-{cname} r {r}: v4 {v4['wrong_commit']:.4f} ({v4['n_commit']}); v5 {v5['wrong_commit']:.4f} ({v5['n_commit']}) "
              f"({time.time() - t0:.0f}s)")
    router.save()


def summary() -> None:
    res = {"env": A.env_note()}
    for cond, R in (("b2t-ours", R_B2T), ("b2t-published", R_B2T), ("emg-calib", R_EMG), ("emg-xsession", R_EMG),
                    ("emg-xsubject", R_EMG)):
        rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TAB.glob(f"{cond}-*.json"))]
        rows = [r for r in rows if r["r"] < R]
        if rows:
            res[cond] = X.summarise_splits(rows)
            X.log(f"{cond}: R {len(rows)}, share > alpha v4 {res[cond]['v4']['share_gt_alpha']:.3f}, v5 {res[cond]['v5']['share_gt_alpha']:.3f}")
    X.dump(res, X.OUT / "splits.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", default=None)
    ap.add_argument("--stage", default="run")
    ap.add_argument("--worker", type=int, default=0)
    ap.add_argument("--nworkers", type=int, default=1)
    a = ap.parse_args()
    if a.stage == "summary":
        X.set_log(X.OUT / "run-splits-summary.log")
        summary()
        return
    X.set_log(X.OUT / f"run-splits-{a.cond}-w{a.worker}.log")
    if a.cond.startswith("b2t-"):
        run_b2t(a.cond[4:], a.worker, a.nworkers)
    else:
        run_emg(a.cond[4:])
    X.log("done")


if __name__ == "__main__":
    main()
