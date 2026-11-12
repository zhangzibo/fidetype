"""R3 item 9: trust-layer run time per decision (CPU).

Editor M8 (run time TODO). For each device the main trust pipeline is
fitted as in the paper (cached decodes). Then, for every test item, the
trust-layer steps after the decoder are timed separately:

- ``frame_T``: frame temperature applied to the stream (before the decoder),
- ``analyze``: sentence / character calibration, conformal set, guard,
  policy inputs,
- ``decide``: the commit / offer / abstain policy,
- ``trust_total`` = frame_T + analyze + decide (the per-decision cost of the
  layer; the decoder itself is not part of the layer).

The decoder (beam search + LM) is timed on a few uncached items for scale.
Each item is timed ``passes`` times; median and 95th percentile over all
timings. Single thread (OMP/MKL/OpenBLAS = 1). The machine was also running
a GPU training job (seed queue) and other CPU jobs: the numbers are upper
bounds for an idle machine.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/runtime/run.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"

import json  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
P = C.load_module("r1policies", K.R1 / "policies.py")


def hardware() -> dict:
    def ps(cmd):
        try:
            return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:  # noqa: BLE001
            return f"n/a ({e})"
    import numpy
    return {"cpu": ps("(Get-CimInstance Win32_Processor).Name"),
            "cores_logical": os.cpu_count(),
            "ram_gb": ps("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)"),
            "os": platform.platform(), "python": platform.python_version(), "numpy": numpy.__version__,
            "threads": 1, "load_note": "GPU training job (MEG seed queue) and other CPU analyses ran at the same time"}


def time_pipe(pipe, items, passes: int) -> dict:
    t_f, t_a, t_d = [], [], []
    for _ in range(passes):
        for it in items:
            s = it.stream(0)
            t0 = time.perf_counter_ns()
            if pipe.frame_scaler.temperature != 1.0:
                pipe.frame_scaler.transform_stream(s)
            t1 = time.perf_counter_ns()
            nb = pipe.decode(it, 0)  # cached: not timed
            t2 = time.perf_counter_ns()
            an = pipe.analyze(nb)
            t3 = time.perf_counter_ns()
            pipe.policy.decide(an.inputs, final_attempt=False)
            t4 = time.perf_counter_ns()
            t_f.append(t1 - t0)
            t_a.append(t3 - t2)
            t_d.append(t4 - t3)
    f, a, d = (np.array(x) / 1e6 for x in (t_f, t_a, t_d))
    tot = f + a + d

    def st(v):
        return {"median_ms": float(np.median(v)), "p95_ms": float(np.quantile(v, 0.95)), "mean_ms": float(v.mean()),
                "max_ms": float(v.max())}
    return {"n_items": len(items), "passes": passes, "frame_T": st(f), "analyze": st(a), "decide": st(d), "trust_total": st(tot),
            "frames_median": float(np.median([it.stream(0).log_probs.shape[0] for it in items]))}


def time_decoder(fn, pipe, items, n: int) -> dict:
    ts = []
    for it in items[:n]:
        s = pipe.frame_scaler.transform_stream(it.stream(0)) if pipe.frame_scaler.temperature != 1.0 else it.stream(0)
        t0 = time.perf_counter_ns()
        fn(s)
        ts.append((time.perf_counter_ns() - t0) / 1e6)
    ts = np.array(ts)
    return {"n": int(ts.size), "median_ms": float(np.median(ts)), "p95_ms": float(np.quantile(ts, 0.95))}


def main() -> None:
    res = {"hardware": hardware(), "devices": {}}
    passes = CONFIG["passes"]
    # sEMG
    for c in ("calib", "xsession", "xsubject"):
        cond = C.emg_condition(c)
        pipe = P.build(cond, "trust", {})
        r = time_pipe(pipe, cond.test, passes)
        r["decoder_uncached"] = time_decoder(cond.decode.fn, pipe, cond.test, CONFIG["decoder_items"])
        res["devices"][f"emg-{c}"] = r
        C.log(f"emg-{c}: trust median {r['trust_total']['median_ms']:.3f} ms p95 {r['trust_total']['p95_ms']:.3f}; decoder {r['decoder_uncached']['median_ms']:.1f} ms")
        C.dump(res, OUT / "runtime.json")
    # MEG
    cond = C.meg_ctx()
    pipe = P.build(cond, "trust", {})
    r = time_pipe(pipe, cond.test, passes)
    r["decoder_uncached"] = time_decoder(cond.decode.fn, pipe, cond.test, CONFIG["decoder_items"])
    res["devices"]["meg-async"] = r
    C.log(f"meg: trust median {r['trust_total']['median_ms']:.3f} ms p95 {r['trust_total']['p95_ms']:.3f}")
    C.dump(res, OUT / "runtime.json")
    # B2T
    ctx = C.b2t_ctx()
    for which in ("ours", "published"):
        cond = C.b2t_condition(ctx, which)
        cond.cached = ctx.cached
        pipe = P.build(cond, "trust", {})
        r = time_pipe(pipe, cond.test, passes)
        fn = ctx.cached[0].fn if which == "ours" else None
        if fn is not None:
            r["decoder_uncached"] = time_decoder(fn, pipe, cond.test, CONFIG["decoder_items"])
        res["devices"][f"b2t-{which}"] = r
        C.log(f"b2t-{which}: trust median {r['trust_total']['median_ms']:.3f} ms p95 {r['trust_total']['p95_ms']:.3f}")
        C.dump(res, OUT / "runtime.json")
    L = ["# Trust-layer run time per decision (CPU, single thread)", "",
         f"Hardware: {res['hardware']['cpu']}, {res['hardware']['cores_logical']} logical cores, {res['hardware']['ram_gb']} GB RAM; "
         f"{res['hardware']['os']}; Python {res['hardware']['python']}, NumPy {res['hardware']['numpy']}. One thread. "
         f"{res['hardware']['load_note']}: upper bounds for an idle machine.", "",
         "| device | items x passes | frame T median / p95 (ms) | analyze median / p95 | decide median / p95 | trust layer total median / p95 | decoder (uncached) median / p95 |",
         "|---|---|---|---|---|---|---|"]
    for k, r in res["devices"].items():
        dd = r.get("decoder_uncached")
        L.append(f"| {k} | {r['n_items']} x {r['passes']} | {r['frame_T']['median_ms']:.3f} / {r['frame_T']['p95_ms']:.3f} | "
                 f"{r['analyze']['median_ms']:.3f} / {r['analyze']['p95_ms']:.3f} | {r['decide']['median_ms']:.4f} / {r['decide']['p95_ms']:.4f} | "
                 f"**{r['trust_total']['median_ms']:.3f} / {r['trust_total']['p95_ms']:.3f}** | "
                 + (f"{dd['median_ms']:.1f} / {dd['p95_ms']:.1f} (n {dd['n']})" if dd else "— (shares our decoder)") + " |")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")
    C.log("done")


if __name__ == "__main__":
    main()
