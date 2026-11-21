"""P5-31: offer null control re-check of the packaged kt-semg-lda guard (no new calibration, no training).

Rebuilds the guard calibration n-best lists and the shuffled null inputs exactly as
fidetype.live.build.train_kt does (guard runs 14, 15, 16, 19, 22, 23; null rng seed 0), with the packaged
model. Writes recheck-kt.json next to this script.
"""
import ctypes
import gc
import json
import time
from pathlib import Path

import numpy as np

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL

HERE = Path(__file__).resolve().parent / "results"
PRE = Path("C:/Users/zhang/bci-data/pretrained/kt-semg-lda")
DATA = Path("C:/Users/zhang/bci-data/raw/kt-semg")
GUARD_RUNS = ["run14", "run15", "run16", "run19", "run22", "run23"]


def main() -> None:
    t0 = time.time()
    import fidetype.trust as ft
    from fidetype.adapters import kt_semg as K
    from fidetype.live import build as Bd
    from fidetype.live.model import load_model
    from fidetype.live.runner import nbest_of_frames
    from fidetype.live.sources import ArraySource

    model = load_model(PRE / "kt-semg-lda.model.json")
    runs = Bd._kt_runs(DATA)
    by_id = {r["id"]: r for rs in runs.values() for r in rs}
    nbs, texts, pools = [], [], []
    for rid in GUARD_RUNS:
        r = by_id[rid]
        rec = K.read_emg_csv(r["csv"])
        ev = Bd.kt_run_events(r["csv"], r["keys"], r["ts"], rec.n_samples)
        segs = Bd.kt_segments(ev)
        src = ArraySource(rec.emg, K.SAMPLE_RATE_HZ, Bd.kt_markers(ev, segs), speed=0, chunk_s=0.5)
        nbs += Bd.collect_nbests(model, src)
        texts += [Bd.kt_text(ev[a:b]) for a, b in segs]
        times = [ev[i].t for a, b in segs for i in range(a, b)]
        sc = model.new_scaler()
        pools.append(model.log_proba(sc.update_transform(model.features(rec.emg, times))))
        print(rid, len(segs), f"{time.time() - t0:.0f} s", flush=True)
        del rec, src
        gc.collect()
    pool = np.concatenate(pools)
    rng = np.random.default_rng(0)
    nulls = []
    for nb, t in zip(nbs, texts):
        k = max(1, len(t))
        idx = rng.integers(0, len(pool), size=k)
        nulls.append(nbest_of_frames(pool[idx], np.arange(k) * 0.25))
    guard = ft.load(PRE / "kt-semg-lda.guard.json")
    out = ft.recheck_offer_control(guard, nbs, null_inputs=nulls)
    out.update(guard="kt-semg-lda", config_id=guard.config_id, seconds=round(time.time() - t0, 1))
    (HERE / "recheck-kt.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
