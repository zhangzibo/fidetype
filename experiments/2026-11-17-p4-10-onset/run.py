"""P4-10 evaluation: causal key-onset detectors on KT-sEMG (see plan.md, pre-registered).

Stages (run in order; each writes to C:/Users/zhang/bci-data/derived/p4-10-onset/):

    python run.py features --set dev     # train + tuning runs: cached step features and envelopes
    python run.py train                  # fit D-lin on the train runs
    python run.py tune                   # theta and lag of D-lin and D-env on cal run21 (frozen after this)
    python run.py features --set test    # test runs (after the plan commit)
    python run.py test                   # onset metrics on the test runs (+ streaming equivalence check)
    python run.py e2e                    # guard re-calibration (detect) + end-to-end arms on the test runs
    python run.py report                 # results/results.json

Data: KT-sEMG v1.1, copyright 2021 Nokia, CC BY 4.0 (read only). Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from fidetype.adapters import kt_semg as K
from fidetype.demo.live.keys import normalize
from fidetype.live.build import _calibrate, _kt_runs, kt_markers, kt_run_events, kt_segments, kt_text
from fidetype.live.model import load_model
from fidetype.live.onset import (EnvelopeDetector, LinearOnsetDetector, fit_linear, load_onset, match_onsets,
                                 save_onset)
from fidetype.live.runner import LiveDecoder, nbest_of_frames
from fidetype.live.sources import Chunk
from fidetype.live.synthetic import KEYPRESS, SEGMENT_END

DATA = Path(os.environ.get("P410_DATA", "C:/Users/zhang/bci-data/raw/kt-semg"))
OUT = Path(os.environ.get("P410_OUT", "C:/Users/zhang/bci-data/derived/p4-10-onset"))
KTDIR = Path("C:/Users/zhang/bci-data/derived/p14-04-live/kt")
HERE = Path(__file__).resolve().parent
FS = K.SAMPLE_RATE_HZ
C = K.N_CHANNELS

TRAIN_RUNS = ["run1", "run2", "run3", "run4", "run8", "run10"]
TUNE_RUNS = ["run21"]
GUARD_RUNS = ["run14", "run15", "run16", "run19", "run22", "run23"]
TOLS = (0.025, 0.05, 0.1)
POS_HALF_S = 0.01
NEG_EVERY = 4
DELAY_S = 0.05
CONTEXT = 20
ENV_GRID = np.linspace(0.5, 8.0, 41)
LIN_Q = np.linspace(0.50, 0.999, 41)


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    (OUT / "run.log").open("a", encoding="utf-8").write(line + "\n")


def runs_by_id() -> dict[str, dict[str, Any]]:
    return {r["id"]: r for rs in _kt_runs(DATA).values() for r in rs}


def test_runs() -> list[str]:
    return [r["id"] for r in _kt_runs(DATA)["test"]]


def iter_csv(path: str, block_s: float = 0.5, chunk_bytes: int = 64 << 20) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Stream a KT-sEMG CSV: (samples (n, 32) float32, times (n,) s from sample 0) in blocks of ``block_s``."""
    step = int(block_s * FS)
    i = 0
    with open(path, "rb") as f:
        header = f.readline().rstrip(b"\r\n").split(b"\t")
        if len(header) != C + 1:
            raise ValueError("bad header")
        rest = b""
        while True:
            new = f.read(chunk_bytes)
            blk = rest + new
            if not new:
                cut, rest = len(blk), b""
            else:
                cut = blk.rfind(b"\n") + 1
                rest = blk[cut:]
            if cut and blk[:cut].strip():
                a = K._parse_rows(blk[:cut], C + 1)[:, 1:]
                for s in range(0, len(a), step):
                    x = a[s:s + step]
                    yield x, (i + np.arange(len(x))) / FS
                    i += len(x)
            if not new:
                break


def run_truth(run: str) -> tuple[list[Any], list[tuple[int, int]], float]:
    r = runs_by_id()[run]
    n = n_samples(run)
    ev = kt_run_events(r["csv"], r["keys"], r["ts"], n)
    return ev, kt_segments(ev), n / FS


def n_samples(run: str) -> int:
    p = OUT / "nsamples.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    if run not in d:
        r = runs_by_id()[run]
        cnt = -1
        with open(r["csv"], "rb") as f:
            for blk in iter(lambda: f.read(64 << 20), b""):
                cnt += blk.count(b"\n")
        d[run] = cnt  # header line excluded; the file ends with a newline
        p.write_text(json.dumps(d, indent=1))
    return int(d[run])


# --- stage: features ---------------------------------------------------------------------------


def features(runs: list[str]) -> None:
    for run in runs:
        dst = OUT / "feat" / f"{run}.npz"
        if dst.exists():
            log(f"features {run}: cached")
            continue
        t0 = time.time()
        r = runs_by_id()[run]
        lin = LinearOnsetDetector(FS, C, np.zeros(CONTEXT * C), 0.0, np.zeros(C), np.ones(C))
        env = EnvelopeDetector(FS, C)
        steps, st, es, et = [], [], [], []
        n = 0
        for x, t in iter_csv(r["csv"]):
            s, ts = lin.steps(x, t)
            steps.append(s.astype(np.float32))
            st.append(ts)
            f, ft = env.fe.process(x, t)
            es.append(env.envelope(f).astype(np.float32))
            et.append(ft)
            n += len(t)
        dst.parent.mkdir(parents=True, exist_ok=True)
        np.savez(dst, steps=np.concatenate(steps), step_t=np.concatenate(st), env=np.concatenate(es),
                 env_t=np.concatenate(et), n=n)
        log(f"features {run}: {n / FS:.0f} s, {sum(len(a) for a in st)} steps, {time.time() - t0:.0f} s")
        gc.collect()


def load_feat(run: str) -> dict[str, np.ndarray]:
    return dict(np.load(OUT / "feat" / f"{run}.npz"))


def lin_scores(det: LinearOnsetDetector, steps: np.ndarray, step_t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Scores from cached raw steps through the detector's own scaler and stacking code."""
    det.reset()
    z = det.scaler.transform(steps.astype(np.float64))
    rows, drop = det.stack(z)
    return rows @ det.w + det.b, step_t[drop:]


def key_times(run: str) -> np.ndarray:
    ev, _, _ = run_truth(run)
    return np.asarray([e.t for e in ev])


# --- stage: train ------------------------------------------------------------------------------


def train() -> None:
    allsteps = [load_feat(r)["steps"].astype(np.float64) for r in TRAIN_RUNS]
    cat = np.concatenate(allsteps)
    mu0, sd0 = cat.mean(0), cat.std(0) + 1e-9
    del cat
    Xs, ys = [], []
    for run, steps in zip(TRAIN_RUNS, allsteps):
        f = load_feat(run)
        det = LinearOnsetDetector(FS, C, np.zeros(CONTEXT * C), 0.0, mu0, sd0, context=CONTEXT, delay_s=DELAY_S)
        z = det.scaler.transform(steps)
        rows, drop = det.stack(z)
        t = f["step_t"][drop:] - DELAY_S
        kt = key_times(run)
        j = np.searchsorted(kt, t)
        d = np.minimum(np.abs(t - kt[np.clip(j - 1, 0, len(kt) - 1)]), np.abs(t - kt[np.clip(j, 0, len(kt) - 1)]))
        y = d <= POS_HALF_S
        keep = y | (np.arange(len(y)) % NEG_EVERY == 0)
        Xs.append(rows[keep].astype(np.float32))
        ys.append(y[keep])
        log(f"train {run}: {len(kt)} keys, {int(y.sum())} positive steps, {int(keep.sum())} rows")
    X, y = np.concatenate(Xs).astype(np.float64), np.concatenate(ys)
    w, b = fit_linear(X, y, shrinkage=0.1)
    det = LinearOnsetDetector(FS, C, w, b, mu0, sd0, context=CONTEXT, delay_s=DELAY_S)
    save_onset(det, OUT / "d-lin.untuned.onset.json")
    log(f"train: D-lin fitted on {len(y)} rows ({int(y.sum())} positive)")


# --- stage: tune -------------------------------------------------------------------------------


def _pick_lin(det: LinearOnsetDetector, s: np.ndarray, t: np.ndarray, theta: float) -> np.ndarray:
    from fidetype.live.onset import PeakPicker

    pk = PeakPicker(theta, det.params["refractory_s"])
    return np.asarray(pk.push(s, t)) - det.delay


def _env_onsets(e: np.ndarray, t: np.ndarray, theta: float, lag: float = 0.0) -> np.ndarray:
    det = EnvelopeDetector(FS, C, theta=theta, lag_s=lag)
    return np.asarray(det.run_envelope(e, t))


def tune() -> None:
    run = TUNE_RUNS[0]
    f = load_feat(run)
    kt = key_times(run)
    det = load_onset(OUT / "d-lin.untuned.onset.json", FS, C)
    s, st = lin_scores(det, f["steps"], f["step_t"])
    grid = np.quantile(s, LIN_Q)
    rows = []
    for th in grid:
        m = match_onsets(kt, _pick_lin(det, s, st, th), 0.05)
        rows.append((m["f1"], th, m))
    best = max(rows, key=lambda r: r[0])
    lag = -float(np.median(best[2]["errors"]))
    d = det.to_dict()
    d["params"].update(theta=float(best[1]), lag_s=lag)
    (OUT / "d-lin.onset.json").write_text(json.dumps(d, separators=(",", ":")) + "\n", encoding="utf-8")
    m2 = match_onsets(kt, _pick_lin(det, s, st, best[1]) + lag, 0.05)
    log(f"tune D-lin on {run}: theta {best[1]:.4f} (F1 {best[0]:.3f} before lag), lag {lag * 1e3:.1f} ms, "
        f"F1 after lag {m2['f1']:.3f}")
    erows = []
    for th in ENV_GRID:
        m = match_onsets(kt, _env_onsets(f["env"], f["env_t"], th), 0.05)
        erows.append((m["f1"], th, m))
    eb = max(erows, key=lambda r: r[0])
    elag = -float(np.median(eb[2]["errors"])) if len(eb[2]["errors"]) else 0.0
    me = match_onsets(kt, _env_onsets(f["env"], f["env_t"], eb[1], elag), 0.05)
    env = {"schema": "fidetype.live.onset/1", "kind": "envelope",
           "params": {"theta": float(eb[1]), "tau_s": 2.0, "refractory_s": 0.06, "lag_s": elag, "block_s": 0.005,
                      "win_blocks": 4}}
    (OUT / "d-env.onset.json").write_text(json.dumps(env) + "\n", encoding="utf-8")
    log(f"tune D-env on {run}: theta {eb[1]:.3f} (F1 {eb[0]:.3f} before lag), lag {elag * 1e3:.1f} ms, "
        f"F1 after lag {me['f1']:.3f}")
    tun = {"run": run, "keys": int(len(kt)),
           "lin": {"theta": float(best[1]), "lag_s": lag, "f1_50": m2["f1"], "recall": m2["recall"],
                   "precision": m2["precision"],
                   "curve": [[float(q), float(th), r[2]["f1"]] for q, th, r in zip(LIN_Q, grid, rows)]},
           "env": {"theta": float(eb[1]), "lag_s": elag, "f1_50": me["f1"], "recall": me["recall"],
                   "precision": me["precision"], "curve": [[float(th), r[2]["f1"]] for th, r in zip(ENV_GRID, erows)]}}
    (OUT / "tune.json").write_text(json.dumps(tun, indent=1) + "\n", encoding="utf-8")


# --- stage: test (onset metrics) -----------------------------------------------------------------


def metrics(kt: np.ndarray, det_t: np.ndarray, dur_s: float, bursts: list[tuple[float, float]]) -> dict[str, Any]:
    out: dict[str, Any] = {"true": int(len(kt)), "detected": int(len(det_t)), "dur_min": dur_s / 60.0,
                           "det_per_key": len(det_t) / max(1, len(kt))}
    for tol in TOLS:
        m = match_onsets(kt, det_t, tol)
        e = m["errors"]
        matched_det = {j for _, j in m["pairs"]}
        fa = [x for j, x in enumerate(np.sort(det_t)) if j not in matched_det]
        in_b = sum(1 for x in fa if any(a <= x <= b for a, b in bursts))
        bmin = sum(b - a for a, b in bursts) / 60.0
        out[f"tol{int(tol * 1e3)}"] = {
            "tp": m["tp"], "fp": m["fp"], "fn": m["fn"], "recall": m["recall"], "precision": m["precision"],
            "f1": m["f1"], "fa_per_min": m["fp"] / max(1e-9, dur_s / 60.0),
            "fa_per_min_in_bursts": in_b / max(1e-9, bmin),
            "err_median_abs_ms": float(np.median(np.abs(e)) * 1e3) if len(e) else None,
            "err_mean_signed_ms": float(np.mean(e) * 1e3) if len(e) else None,
            "err_p90_abs_ms": float(np.percentile(np.abs(e), 90) * 1e3) if len(e) else None}
    return out


def pooled(per: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tol in TOLS:
        k = f"tol{int(tol * 1e3)}"
        tp = sum(p[k]["tp"] for p in per.values())
        fp = sum(p[k]["fp"] for p in per.values())
        fn = sum(p[k]["fn"] for p in per.values())
        mins = sum(p["dur_min"] for p in per.values())
        out[k] = {"tp": tp, "fp": fp, "fn": fn, "recall": tp / (tp + fn), "precision": tp / max(1, tp + fp),
                  "f1": 2 * tp / (2 * tp + fp + fn), "fa_per_min": fp / mins,
                  "f1_run_range": [min(p[k]["f1"] for p in per.values()), max(p[k]["f1"] for p in per.values())]}
    return out


def test() -> None:
    lin = load_onset(OUT / "d-lin.onset.json", FS, C)
    res: dict[str, Any] = {"lin": {}, "env": {}}
    ep = json.loads((OUT / "d-env.onset.json").read_text())["params"]
    for run in test_runs():
        f = load_feat(run)
        ev, segs, dur = run_truth(run)
        kt = np.asarray([e.t for e in ev])
        bursts = [(ev[a].t - 0.5, ev[b - 1].t + 0.5) for a, b in segs]
        s, st = lin_scores(lin, f["steps"], f["step_t"])
        dl = _pick_lin(lin, s, st, lin.params["theta"]) + lin.lag
        de = _env_onsets(f["env"], f["env_t"], ep["theta"], ep["lag_s"])
        np.savez(OUT / f"onsets-{run}.npz", lin=dl, env=de, true=kt)
        res["lin"][run] = metrics(kt, dl, dur, bursts)
        res["env"][run] = metrics(kt, de, dur, bursts)
        log(f"test {run}: keys {len(kt)}; D-lin F1@50 {res['lin'][run]['tol50']['f1']:.3f} "
            f"(R {res['lin'][run]['tol50']['recall']:.3f}, P {res['lin'][run]['tol50']['precision']:.3f}); "
            f"D-env F1@50 {res['env'][run]['tol50']['f1']:.3f}")
    res["pooled"] = {"lin": pooled(res["lin"]), "env": pooled(res["env"])}
    wins = sum(res["lin"][r]["tol50"]["f1"] > res["env"][r]["tol50"]["f1"] for r in res["lin"])
    res["H2_wins"] = wins
    # equivalence: the streaming process() on the raw CSV gives the same onsets as the cached path
    run = min(test_runs(), key=lambda r: Path(runs_by_id()[r]["csv"]).stat().st_size)
    lin2 = load_onset(OUT / "d-lin.onset.json", FS, C)
    env2 = load_onset(OUT / "d-env.onset.json", FS, C)
    a, b = [], []
    for x, t in iter_csv(runs_by_id()[run]["csv"], block_s=0.37):
        a += lin2.process(x, t)
        b += env2.process(x, t)
    o = np.load(OUT / f"onsets-{run}.npz")
    res["stream_equivalence"] = {"run": run, "lin_same": bool(len(a) == len(o["lin"]) and np.allclose(a, o["lin"])),
                                 "env_same": bool(len(b) == len(o["env"]) and np.allclose(b, o["env"])),
                                 "lin_n": [len(a), int(len(o["lin"]))], "env_n": [len(b), int(len(o["env"]))]}
    log(f"stream equivalence on {run}: {res['stream_equivalence']}")
    (OUT / "test.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    P = res["pooled"]
    log(f"pooled: D-lin F1@50 {P['lin']['tol50']['f1']:.3f}, D-env F1@50 {P['env']['tol50']['f1']:.3f}; "
        f"D-lin wins {wins}/6")


# --- stage: e2e ----------------------------------------------------------------------------------


class Capture:
    """A writer stand-in: keeps the frames (time, log-probs) of a decoder."""

    def __init__(self) -> None:
        self.frames: list[tuple[float, np.ndarray]] = []

    def frame(self, t: float, lp: Any) -> None:
        self.frames.append((float(t), np.asarray(lp)))

    def hypothesis(self, *a: Any, **k: Any) -> None:
        pass

    def event(self, *a: Any, **k: Any) -> None:
        pass

    def segment_end(self, *a: Any, **k: Any) -> None:
        pass


def _arms(model: Any, guards: dict[str, Any], detect: bool = True) -> dict[str, tuple[LiveDecoder, Capture]]:
    class Null:
        info = {"name": "csv", "sample_rate": FS, "channels": C, "modality": "emg", "meta": {}}

    arms = {}
    specs = {"oracle": ("markers", None, guards.get("oracle"))}
    if detect:
        specs["lin"] = ("detect", OUT / "d-lin.onset.json", guards.get("lin"))
        specs["env"] = ("detect", OUT / "d-env.onset.json", guards.get("env"))
        if guards.get("oracle") is not None:
            specs["lin_oracle_guard"] = ("detect", OUT / "d-lin.onset.json", guards.get("oracle"))
    for k, (timing, det, g) in specs.items():
        cap = Capture()
        dec = LiveDecoder(model, g, Null(), timing=timing, writer=cap,
                          detector=load_onset(det, FS, C) if det else None)
        arms[k] = (dec, cap)
    return arms


def _feed_run(run: str, arms: dict[str, tuple[LiveDecoder, Capture]]) -> tuple[list[Any], list[tuple[int, int]]]:
    ev, segs, _ = run_truth(run)
    mk = sorted(kt_markers(ev, segs))
    mi = 0
    for x, t in iter_csv(runs_by_id()[run]["csv"]):
        hi = t[-1] + 1 / FS
        cm = []
        while mi < len(mk) and mk[mi][0] < hi:
            cm.append(mk[mi])
            mi += 1
        for dec, _ in arms.values():
            dec.feed(Chunk(x, t, list(cm)))
    for dec, _ in arms.values():
        dec._due_frames()
        dec._due_segments(final=True)
    return ev, segs


def _seg_of(t_end: float, ends: list[float]) -> int | None:
    j = int(np.argmin([abs(t_end - e) for e in ends])) if ends else -1
    return j if j >= 0 and abs(t_end - ends[j]) < 1e-6 else None


def calibrate_detect() -> None:
    model = load_model(KTDIR / "kt-semg-lda.model.json")
    keys = ("lin", "env")
    texts: dict[str, list[str]] = {k: [] for k in keys}
    nbs: dict[str, list[Any]] = {k: [] for k in keys}
    pools: dict[str, list[np.ndarray]] = {k: [] for k in keys}
    for run in GUARD_RUNS:
        # fresh decoders per run: every run's clock starts at 0
        arms = {k: v for k, v in _arms(model, {}).items() if k in keys}
        ev, segs = _feed_run(run, arms)
        ends = [float(ev[b - 1].t) + 0.5 for a, b in segs]
        for k, (d, cap) in arms.items():
            pools[k] += [lp for _, lp in cap.frames]
            for nb, t0, t1 in d.collected:
                j = _seg_of(t1, ends)
                if j is None:
                    continue
                a, b = segs[j]
                nbs[k].append(nb)
                texts[k].append(kt_text(ev[a:b]))
        log(f"guard collect {run}: {len(segs)} segments; " +
            ", ".join(f"{k} {len(nbs[k])} items, {d.stats.onsets} onsets" for k, (d, _) in arms.items()))
        gc.collect()
    rng = np.random.default_rng(0)
    out = {}
    for k in keys:
        pool = np.stack(pools[k])
        nulls = []
        for t in texts[k]:
            m = max(1, len(t))
            nulls.append(nbest_of_frames(pool[rng.integers(0, len(pool), size=m)], np.arange(m) * 0.25))
        g = _calibrate(nbs[k], texts[k], nulls, 0.05, 0.1, f"kt-semg-lda-detect-{k}", "emg", model)
        g.save(OUT / f"guard-detect-{k}.guard.json")
        exact = float(np.mean([normalize(nb[0]["text"]) == t for nb, t in zip(nbs[k], texts[k])]))
        out[k] = {"items": len(nbs[k]), "top1_exact": exact, "config_id": g.config_id,
                  "controls": [(c.name, bool(c.passed)) for c in g.sheet.controls] if g.sheet else None}
        log(f"guard detect-{k}: {len(nbs[k])} items, top-1 exact {exact:.3f}, {g.config_id}")
    (OUT / "guard-detect.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")


def _cer(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(1, len(b))


def e2e() -> None:
    import fidetype.trust as ft

    if not (OUT / "guard-detect-lin.guard.json").exists():
        calibrate_detect()
    model = load_model(KTDIR / "kt-semg-lda.model.json")
    guards = {"oracle": ft.load(KTDIR / "kt-semg-lda.guard.json"),
              "lin": ft.load(OUT / "guard-detect-lin.guard.json"),
              "env": ft.load(OUT / "guard-detect-env.guard.json")}
    from fidetype.adapters.kt_semg import key_class

    tot: dict[str, dict[str, Any]] = {}
    for run in test_runs():
        arms = _arms(model, guards)
        ev, segs = _feed_run(run, arms)
        ends = [float(ev[b - 1].t) + 0.5 for a, b in segs]
        burst_keys = [(ev[i].t, key_class(ev[i].char)) for a, b in segs for i in range(a, b)]
        bk_t = np.asarray([t for t, _ in burst_keys])
        bk_c = [c for _, c in burst_keys]
        for k, (d, cap) in arms.items():
            T = tot.setdefault(k, {"keys": 0, "keys_scored": 0, "key_right": 0, "matched": 0, "segments": 0,
                                   "decisions": 0, "commit": 0, "commit_wrong": 0, "offer": 0, "offer_hit": 0,
                                   "withhold": 0, "exact": 0, "cer_sum": 0.0, "onsets": 0, "frames": 0})
            ft_t = np.asarray([t for t, _ in cap.frames])
            ft_c = [int(np.argmax(lp)) for _, lp in cap.frames]
            m = match_onsets(bk_t, ft_t, 0.05) if k != "oracle" else {"pairs": [(i, i) for i in range(len(bk_t))]}
            if k == "oracle":  # oracle frames are the burst keys in order (late keys aside)
                m = match_onsets(bk_t, ft_t, 1e-4)
            right = sum(1 for i, j in m["pairs"] if bk_c[i] is not None and ft_c[j] == bk_c[i])
            scored = sum(1 for i, j in m["pairs"] if bk_c[i] is not None)
            T["keys"] += sum(1 for c in bk_c if c is not None)
            T["keys_scored"] += scored
            T["key_right"] += right
            T["matched"] += len(m["pairs"])
            T["segments"] += len(segs)
            T["onsets"] += d.stats.onsets
            T["frames"] += d.stats.frames
            for dd in d.decisions:
                j = _seg_of(dd.t_end, ends)
                if j is None:
                    continue
                a, b = segs[j]
                truth = kt_text(ev[a:b])
                T["decisions"] += 1
                top = dd.nbest[0]["text"] if dd.nbest else ""
                T["exact"] += int(normalize(top) == truth)
                T["cer_sum"] += _cer(top, truth)
                if dd.action == "commit":
                    T["commit"] += 1
                    T["commit_wrong"] += int(normalize(dd.text or "") != truth)
                elif dd.action == "offer":
                    T["offer"] += 1
                    T["offer_hit"] += int(any(normalize(c) == truth for c in dd.choices))
                else:
                    T["withhold"] += 1
        log(f"e2e {run}: {len(segs)} segments; " + ", ".join(
            f"{k} acc {tot[k]['key_right'] / max(1, tot[k]['keys']):.3f} dec {tot[k]['decisions']} "
            f"commit {tot[k]['commit']}" for k in arms))
        del arms
        gc.collect()
    (OUT / "e2e.json").write_text(json.dumps(tot, indent=1) + "\n", encoding="utf-8")


def _cp95(k: int, n: int) -> list[float]:
    from math import comb

    def cdf(p: float, kk: int) -> float:
        return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(kk + 1))

    def solve(f: Any, lo: float = 0.0, hi: float = 1.0) -> float:
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    if n == 0:
        return [0.0, 1.0]
    lo = 0.0 if k == 0 else solve(lambda p: 1 - cdf(p, k - 1) < 0.025)
    hi = 1.0 if k == n else solve(lambda p: cdf(p, k) > 0.025)
    return [round(lo, 4), round(hi, 4)]


def report() -> None:
    res: dict[str, Any] = {"plan": "experiments/2026-11-17-p4-10-onset/plan.md", "data": K.ATTRIBUTION}
    for name in ("tune", "test", "guard-detect", "e2e"):
        p = OUT / f"{name}.json"
        if p.exists():
            res[name] = json.loads(p.read_text())
    if "test" in res:
        t = res["test"]
        res["test"] = {"pooled": t["pooled"], "H2_wins": t["H2_wins"], "stream_equivalence": t["stream_equivalence"],
                       "per_run": {k: {r: {"true": v["true"], "detected": v["detected"], "tol50": v["tol50"]}
                                       for r, v in t[k].items()} for k in ("lin", "env")}}
    if "e2e" in res:
        for k, T in res["e2e"].items():
            T["key_acc_effective"] = T["key_right"] / max(1, T["keys"])
            T["key_acc_matched"] = T["key_right"] / max(1, T["keys_scored"])
            T["cer"] = T["cer_sum"] / max(1, T["decisions"])
            T["wrong_commit_rate"] = T["commit_wrong"] / max(1, T["decisions"])
            T["wrong_commit_cp95"] = _cp95(T["commit_wrong"], T["decisions"])
    tp = res.get("test", {}).get("pooled", {})
    e = res.get("e2e", {})
    res["hypotheses"] = {
        "H1_lin_f1_50_ge_0.70": (tp["lin"]["tol50"]["f1"] >= 0.70) if tp else None,
        "H2_lin_beats_env_on_ge_5_of_6": (res["test"]["H2_wins"] >= 5) if tp else None,
        "H3_effective_acc_ge_0.8x_oracle": (e["lin"]["key_acc_effective"] >= 0.8 * e["oracle"]["key_acc_effective"])
        if e else None,
        "S_wrong_commit_le_alpha": (e["lin"]["wrong_commit_rate"] <= 0.05) if e else None,
    }
    dst = HERE / "results"
    dst.mkdir(exist_ok=True)
    (dst / "results.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    log(f"report: {json.dumps(res['hypotheses'])}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("features", "train", "tune", "test", "e2e", "report"))
    ap.add_argument("--set", choices=("dev", "test", "guard"), default="dev")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"stage {a.stage} {a.set if a.stage == 'features' else ''}")
    if a.stage == "features":
        features({"dev": TRAIN_RUNS + TUNE_RUNS, "test": test_runs(), "guard": GUARD_RUNS}[a.set])
    else:
        {"train": train, "tune": tune, "test": test, "e2e": e2e, "report": report}[a.stage]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
