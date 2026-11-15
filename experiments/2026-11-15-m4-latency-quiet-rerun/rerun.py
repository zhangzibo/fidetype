"""M4-02R: rerun the M4-01/02 latency stage on a quiet machine (see plan.md).

Primary: the ORIGINAL M4-01/02 code (experiments/2026-11-13-m4-01-02-lookahead/run.py), unchanged:
stage_latency(force=True) and stage_emission(), with M4_OUT = results/ of this folder.
Secondary (only if both NumPy exports exist): the M4-12 dedicated checkpoints m4-12-fixed0 (L 0) and
m4-12-fixed25 (L 25 bins), timed with the same loop (a parameterised copy of stage_latency) in the same CPU class.

The process holds a keep-awake (SetThreadExecutionState) while it runs; it ends when the process ends.
Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-15-m4-latency-quiet-rerun/rerun.py
Only aggregate numbers are written to the repo.
"""

from __future__ import annotations

import ctypes
import gc
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ORIG = REPO / "experiments/2026-11-13-m4-01-02-lookahead"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
os.environ["M4_OUT"] = str(OUT)

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
if os.name == "nt":
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)

# the latency stage reads OUT/accuracy.json only for the accuracy-stage commit rate: use the original file (removed at the end)
shutil.copyfile(ORIG / "results/accuracy.json", OUT / "accuracy.json")

spec = importlib.util.spec_from_file_location("m4run", ORIG / "run.py")
M = importlib.util.module_from_spec(spec)
sys.modules["m4run"] = M
spec.loader.exec_module(M)

import numpy as np  # noqa: E402

DER = M.DER


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def inputs_record() -> dict:
    files = ["params-m4-01-la-shared.npz", "logprobs-m4-01-la-shared.npz", "logprobs-m4-01-la-fixed0.npz",
             "logprobs-m4-01-la-fixed25.npz", "params-m4-12-fixed0.npz", "params-m4-12-fixed25.npz",
             "logprobs-m4-12-fixed0.npz", "logprobs-m4-12-fixed25.npz"]
    files += [f"trust-shared-L{la}.json" for la in M.T.LA_BINS]
    rec = {}
    for f in files:
        p = DER / f
        if p.exists():
            rec[f] = {"sha256": sha(p), "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))}
    return rec


def accuracy_stage_commits() -> dict:
    """Commits in the M4-01/02 accuracy-stage decisions of the shared model (all 701 trials)."""
    out = {}
    for la in M.T.LA_BINS:
        d = json.loads((DER / f"trust-shared-L{la}.json").read_text(encoding="utf-8"))
        acts = [x["action"] for x in d["decisions"]]
        out[f"L{la}"] = {"n": len(acts), "commits": sum(a == "COMMIT" for a in acts)}
    return out


def latency_dedicated(run: str, la: int, n_trials: int = 200) -> dict:
    """Same timed loop as M.stage_latency, for one model at one L (one isolated block per call); commits counted directly."""
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, NumpyLookaheadGRU, StreamingLookaheadGRU, log_softmax
    from fidetype.trust.incremental import CTCBeamSpec
    from fidetype.trust.types import from_lm_hypotheses
    from fidetype.utils.isolation import isolated

    ctx = M.Ctx()
    meta = json.loads((DER / f"decode-{run}.json").read_text(encoding="utf-8"))
    mc = LookaheadGRUConfig(**meta["model_config"])
    pz = np.load(DER / f"params-{run}.npz")
    model = NumpyLookaheadGRU(mc, {k: pz[k] for k in pz.files})
    lpz = np.load(DER / f"logprobs-{run}.npz")
    keys_all = sorted({k.rsplit("|", 1)[0] for k in lpz.files}, key=lambda k: (k.split("|")[0], int(k.split("|")[2])))
    rng = np.random.default_rng(20261113)
    keys = sorted(rng.choice(len(keys_all), min(n_trials, len(keys_all)), replace=False).tolist())
    keys = [keys_all[i] for i in keys]
    sess_idx = {s: i for i, s in enumerate(ctx.sessions)}
    X = {}
    for key in keys:
        s, part, i = key.split("|")
        if s not in M._NPZ:
            M._NPZ[s] = np.load(DER / f"{s}.npz")
        X[key] = M._NPZ[s][f"{part}_X{i}"].astype(np.float32)
    wdec = ctx.dec.wdec

    def post(hyps, stream):
        return from_lm_hypotheses(wdec.decode(hyps), stream.meta, confidence_variant=None)

    bspec = CTCBeamSpec(dict(ctx.dec.beam_kw), post=post)
    gc.collect()
    gc.freeze()
    with isolated("timing") as iso:
        wdec.clear_caches() if hasattr(wdec, "clear_caches") else None
        layer = M.StreamingTrustLayer(ctx.fz, incremental=bspec.factory,
                                      streaming=M.StreamingConfig(route="frames", max_attempts=1, incremental_chunk_frames=1))
        t_bin, t_frame, t_end_dec, t_end_trust, t_end_total = [], [], [], [], []
        decs, chk = [], 0.0
        for gi, key in enumerate(keys):
            s = key.split("|")[0]
            lp_ref = lpz[f"{key}|L{la}"] if gi < 20 else None
            st_meta = M.make_stream(np.full((1, 41), -math.log(41), np.float32), key, la, run, gi, meta["model_config"])
            head = M.events_of(st_meta)[0]
            gc.collect()
            gc.disable()
            layer.push(head, s)
            dec = StreamingLookaheadGRU(model, sess_idx[s], la)
            x = X[key]
            k = 0
            rows_all = []
            for b in range(x.shape[0]):
                t0 = time.perf_counter()
                rows = dec.push(x[b:b + 1])
                t1 = time.perf_counter()
                t_bin.append(t1 - t0)
                for row in rows:
                    lpr = log_softmax(row[None])[0]
                    rows_all.append(lpr)
                    ev = {"type": "frame", "t": float((k * mc.stride + mc.patch) * 0.02), "log_probs": [float(v) for v in lpr]}
                    t2 = time.perf_counter()
                    layer.push(ev, s)
                    t_frame.append(time.perf_counter() - t2)
                    k += 1
            t0 = time.perf_counter()
            rows = dec.flush()
            t1 = time.perf_counter()
            out = []
            for row in rows:
                lpr = log_softmax(row[None])[0]
                rows_all.append(lpr)
                out += layer.push({"type": "frame", "t": float((k * mc.stride + mc.patch) * 0.02),
                                   "log_probs": [float(v) for v in lpr]}, s)
                k += 1
            out += layer.push({"type": "end"}, s)
            t2 = time.perf_counter()
            gc.enable()
            t_end_dec.append(t1 - t0)
            t_end_trust.append(t2 - t1)
            t_end_total.append(t2 - t0)
            fin = [d for d in out if d.final]
            assert len(fin) == 1
            decs.append(fin[0])
            if lp_ref is not None:
                chk = max(chk, float(np.abs(np.stack(rows_all) - lp_ref).max()))
    gc.unfreeze()
    ms = lambda v: {"p50": float(np.percentile(v, 50) * 1e3), "p95": float(np.percentile(v, 95) * 1e3),  # noqa: E731
                    "max": float(np.max(v) * 1e3), "mean": float(np.mean(v) * 1e3), "n": len(v)}
    acts = [d.action.value for d in decs]
    r = {"run": run, "lookahead_bins": la, "algorithmic_lookahead_ms": la * 20, "n": len(decs),
         "decoder_push_per_bin_ms": ms(t_bin), "trust_push_per_frame_ms": ms(t_frame),
         "end_decoder_flush_ms": ms(t_end_dec), "end_trust_ms": ms(t_end_trust), "end_total_ms": ms(t_end_total),
         "numpy_vs_torch_max_abs_logprob": chk,
         "actions": {a: acts.count(a) for a in sorted(set(acts))}, "commits": acts.count("COMMIT"),
         "measurement_env": iso.record}
    M.log(f"secondary latency {run} L{la}: bin push p50/p95 {r['decoder_push_per_bin_ms']['p50']:.2f}/"
          f"{r['decoder_push_per_bin_ms']['p95']:.2f} ms; frame push p95 {r['trust_push_per_frame_ms']['p95']:.2f}; end total "
          f"p50/p95/max {r['end_total_ms']['p50']:.1f}/{r['end_total_ms']['p95']:.1f}/{r['end_total_ms']['max']:.1f} ms; "
          f"commits {r['commits']}/{r['n']}; foreign {iso.record.get('foreign_load_pct')} %")
    return r


def emission_dedicated(run0: str, run25: str) -> dict:
    """Ready time of matched phonemes, dedicated L 25 vs dedicated L 0 (same rule as M.stage_emission)."""
    per = {}
    for run, la in ((run0, 0), (run25, 25)):
        mc = json.loads((DER / f"decode-{run}.json").read_text(encoding="utf-8"))["model_config"]
        z = np.load(DER / f"logprobs-{run}.npz")
        d = {}
        for k in z.files:
            if not k.endswith(f"|L{la}"):
                continue
            key = k.rsplit("|", 1)[0]
            s, part, i = key.split("|")
            ref = [int(x) for x in M.load_ph(s, part, int(i))]
            runs = M.greedy_runs(z[k])
            mt = M.align_matches(ref, [x for x, _ in runs])
            stamp = lambda f: (f * mc["stride"] + mc["patch"]) * 0.02  # noqa: E731
            d[key] = {ri: (stamp(runs[hj][1]), stamp(runs[hj][1]) + la * 0.02) for ri, hj in mt.items()}
        per[la] = d
    ds, dav = [], []
    for key, R in per[0].items():
        Cc = per[25].get(key, {})
        for i in R:
            if i in Cc:
                ds.append(Cc[i][0] - R[i][0])
                dav.append(Cc[i][1] - R[i][1])
    q = lambda v: {"median": float(np.median(v)), "p25": float(np.percentile(v, 25)), "p75": float(np.percentile(v, 75)),  # noqa: E731
                   "n": len(v)}
    return {"comparison": f"{run25}/L25 vs {run0}/L0", "emission_stamp_delta_s": q(ds), "available_delta_s": q(dav)}


DEADLINE = time.mktime(time.strptime("2026-11-15 08:30", "%Y-%m-%d %H:%M"))
GATE = Path("C:/Users/zhang/bci-data/runs/latency-rerun.DONE")
STATUS = {"complete": False, "skipped": []}


def fits(est_s: float) -> bool:
    """True if a step of about est_s seconds ends before 08:30 (with 3 min margin)."""
    return time.time() + est_s + 180 < DEADLINE


def main() -> None:
    t0 = time.time()
    M.log(f"M4-02R start (keep-awake on); M4_OUT={OUT}")
    rec = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "inputs": inputs_record()}
    M.T.dump(rec, OUT / "inputs.json")
    import threading

    def hard_stop() -> None:
        STATUS["error"] = "hard stop at 08:30: run incomplete"
        M.log("M4-02R hard stop at 08:30: result incomplete")
        GATE.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} m4-02r status={json.dumps(STATUS)}\n", encoding="utf-8")
        os._exit(3)

    tm = threading.Timer(max(1.0, DEADLINE - time.time()), hard_stop)
    tm.daemon = True
    tm.start()
    if not fits(900):
        STATUS["skipped"].append("primary")
        M.log("primary skipped: would not end before 08:30")
        return
    # primary: original code, unchanged. The M4-12 phase-1 CPU stage (2026-11-15 05:26-05:40) overwrote
    # DER/trust-shared-L*.json with M4-12 decisions, so the stage's same-action check is invalid here.
    # We count the final actions directly: a thin subclass records them after each push returns.
    _Base = M.StreamingTrustLayer
    prim_actions: list = []

    class CountingLayer(_Base):
        def push(self, ev, *a, **k):
            out = _Base.push(self, ev, *a, **k)
            if out:
                prim_actions.extend(d.action.value for d in out if d.final)
            return out

    M.StreamingTrustLayer = CountingLayer
    M.stage_latency(force=True)
    M.StreamingTrustLayer = _Base
    nper = len(prim_actions) // len(M.T.LA_BINS)
    rec["primary_streaming_actions"] = {
        f"L{la}": {x: prim_actions[i * nper:(i + 1) * nper].count(x) for x in sorted(set(prim_actions[i * nper:(i + 1) * nper]))}
        for i, la in enumerate(M.T.LA_BINS)}
    rec["primary_note"] = ("latency.json same_action_as_accuracy_stage compares with DER/trust-shared-L*.json, which held M4-12 "
                           "decisions at run time: not valid. Use primary_streaming_actions (counted in this run).")
    M.T.dump(rec, OUT / "inputs.json")
    M.log(f"primary latency done; streaming actions {rec['primary_streaming_actions']}")
    have = lambda r: (DER / f"params-{r}.npz").exists() and (DER / f"logprobs-{r}.npz").exists()  # noqa: E731
    sec_ok = have("m4-12-fixed0") and have("m4-12-fixed25")
    sec = {"available": {r: have(r) for r in ("m4-12-fixed0", "m4-12-fixed25", "m4-12-shared")}, "latency": {}}
    todo = []
    if sec_ok:
        todo += [("m4-12-fixed0", 0), ("m4-12-fixed25", 25)]
    if have("m4-12-shared"):
        todo += [("m4-12-shared", la) for la in M.T.LA_BINS]
    for run, la in todo:
        if not fits(240):
            STATUS["skipped"].append(f"{run}/L{la}")
            M.log(f"secondary {run} L{la} skipped: would not end before 08:30")
            continue
        sec["latency"][f"{run}/L{la}"] = latency_dedicated(run, la)
        M.T.dump(sec, OUT / "secondary.json")
    M.T.dump(sec, OUT / "secondary.json")
    # not timed: emission (frame stamps) and trust counts
    M.stage_emission()
    extra = {"accuracy_stage_commits_trust_shared_files_m4_12": accuracy_stage_commits()}
    if sec_ok:
        sec["emission"] = emission_dedicated("m4-12-fixed0", "m4-12-fixed25")
        M.T.dump(sec, OUT / "secondary.json")
    rec.update(extra, finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"), wall_s=round(time.time() - t0, 1))
    M.T.dump(rec, OUT / "inputs.json")
    (OUT / "accuracy.json").unlink(missing_ok=True)
    STATUS["complete"] = not STATUS["skipped"]
    rec["status"] = STATUS
    M.T.dump(rec, OUT / "inputs.json")
    M.log(f"M4-02R done ({time.time() - t0:.0f}s) status {STATUS}")
    (OUT / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z"), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:  # noqa: BLE001
        M.log(f"M4-02R FAILED: {e!r}") if "M" in globals() else None
        STATUS["error"] = repr(e)
        raise
    finally:
        GATE.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} m4-02r status={json.dumps(STATUS)}\n", encoding="utf-8")
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
