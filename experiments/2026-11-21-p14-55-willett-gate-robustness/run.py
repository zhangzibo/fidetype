r"""P14-55: robustness of the willett-hw no-signal gates (gate C5 + the coherence offer gates). Plan: plan.md.

Our own code (Apache-2.0). CPU only. Stages (each item is written to a JSONL record at once; a restart skips it):
  neural   per session: test time-shuffled draws d=1..10, zero, rev_in, do_nothing; val S time-shuffled draws.
  lines    80 segments of t5.2019.06.03/straightLines.mat (day layer index 0).
  frames   test frame-shuffled + near-uniform draws d=1..10, rev_out, and the real test inputs (reference).
  score    parts A, B, C -> results/*.json (counts, thresholds, coefficients only).
  all      every stage, then the DONE file.

Run (repo root; detached form: launch.py)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-21-p14-55-willett-gate-robustness/run.py all

Per-item records (features, actions; no text) stay in C:\Users\zhang\bci-data\derived\p14-55.
"""

from __future__ import annotations

import ctypes
import gc
import hashlib
import json
import math
import os
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", r"C:\Users\zhang\bci-data\pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"  # CPU only
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DATA = Path(r"C:\Users\zhang\bci-data")
RAW = DATA / "raw/willett-handwriting/extracted/handwritingBCIData/Datasets"
P1441 = DATA / "derived/p14-41"  # read only (items.json, lp_*.npz)
OWN = DATA / "derived/p14-55"
OUT = HERE / "results"
REC = OWN / "items.jsonl"
DRAWS = tuple(range(1, 11))
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-26ae951a20a0cddd"}
LINES_SESSION, LINES_LAYER, LINES_SEED = "t5.2019.06.03", 0, 5555
SPLIT_SEED, BOOT_SEED, N_SPLITS, N_BOOT = 5556, 5557, 200, 2000
N_CHECK = 5
RSS_LIMIT_MB = 5000.0
PF_KEYS = ("n_keys", "kps", "nb_share", "peak", "neg_entropy", "log_n_keys")


# --- logging, memory, stop -----------------------------------------------------------------------------

class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QPPPU", ctypes.c_size_t), ("QPPU", ctypes.c_size_t),
                ("QPNPPU", ctypes.c_size_t), ("QNPPU", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_mb() -> tuple[float, float]:
    c = _PMC()
    c.cb = ctypes.sizeof(c)
    k = ctypes.windll.kernel32
    k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20


def log(msg: str) -> None:
    w, p = mem_mb()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] (rss {w:.0f} MB, peak {p:.0f} MB) {msg}"
    print(line, flush=True)
    with open(OWN / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def watcher() -> None:
    last = time.time()
    while True:
        time.sleep(2.0)
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)
        if mem_mb()[0] > RSS_LIMIT_MB:
            log(f"working set above {RSS_LIMIT_MB:.0f} MB: exit 3")
            os._exit(3)
        if time.time() - last > 600:
            log("heartbeat")
            last = time.time()


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                   encoding="utf-8")
    tmp.replace(p)


def rng_for(d: int, split: str, i: int, kind: str) -> np.random.Generator:
    h = hashlib.sha256(f"p14-55|{d}|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(P1441 / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def meta() -> dict:
    return json.loads((P1441 / "items.json").read_text(encoding="utf-8"))


def s_positions() -> list[int]:
    from fidetype.trust.dropin import _split

    n_fit, n_pol, _ = _split(106)
    return [int(i) for i in np.random.default_rng(0).permutation(106)[: n_fit + n_pol]]


# --- the objects under test ----------------------------------------------------------------------------

class Env:
    def __init__(self) -> None:
        import fidetype.pretrained as ftp

        self.m = ftp.load("willett-hw")
        self.rg = self.m.lm_readout()  # default gate = C5
        self.c5 = self.rg.gate
        self.g = {"builtin": self.m.guard(), "lm": self.m.guard(readout="lm")}
        for k, g in self.g.items():
            assert g.config_id == CFG[k], (k, g.config_id)
            assert len(g.offer_gates) == 1 and g.offer_gates[0].feature == "coherence", k
        self.thr = {k: float(g.offer_gates[0].threshold) for k, g in self.g.items()}
        self.sessions = list(self.m.manifest.architecture["sessions"])
        self.uni_seen = {k: 0 for k in self.g}
        self.uni_ok = {k: True for k in self.g}
        self.uni_check: dict[str, list[bool]] = {k: [] for k in self.g}


def pfeat(lp) -> dict:
    from fidetype.pretrained._xbody import BIN_S
    from fidetype.pretrained.lmreadout import posterior_features

    f = posterior_features(lp, BIN_S)
    return {k: float(f[k]) for k in PF_KEYS}


def c5_part(E: Env, lp, lm: bool = True) -> dict:
    lp64 = np.asarray(lp, np.float64)
    ok = bool(E.c5.passes(lp64))
    rec = {"pf": pfeat(lp64), "c5_score": float(E.c5.score(lp64)), "c5_pass": ok}
    if lm:
        rec["c5_emit"] = bool(ok and len(E.rg.text(lp64)) > 0)
    return rec


def decide(g, lp) -> dict:
    g.collect_offer_features = True
    r = g._decide_quiet(lp, None)
    return {"action": str(getattr(r.action, "value", r.action)).lower(), "gated": g._offer_gate_why is not None,
            "coh": float(g.last_offer_features["coherence"]), "decided": True}


def fast_coh(g, lp) -> float:
    from fidetype.trust import offer_gate as og

    st = g._codec.stream(lp, None)
    fs = g._layer.components.frame_scaler
    st = fs.transform_stream(st) if fs.temperature != 1.0 else st
    return float(og.frame_features(np.asarray(st.log_probs, np.float64), int(g._codec.vocab.blank_id or 0))["coherence"])


def guard_part(E: Env, lp, uniform: bool = False) -> dict:
    out = {}
    for k, g in E.g.items():
        if not uniform:
            out[k] = decide(g, lp)
            continue
        c = fast_coh(g, lp)
        E.uni_seen[k] += 1
        if E.uni_seen[k] <= N_CHECK or not E.uni_ok[k] or c >= E.thr[k]:
            r = decide(g, lp)
            if E.uni_seen[k] <= N_CHECK:
                same = math.isclose(c, r["coh"], rel_tol=1e-6, abs_tol=1e-12)
                E.uni_check[k].append(same)
                if not same:
                    E.uni_ok[k] = False
                    log(f"uniform fast-path check FAILED ({k}): {c} vs {r['coh']}")
            out[k] = r
        else:  # below the offer-gate threshold: cannot be an offer; the guards never commit
            out[k] = {"action": "withhold", "gated": None, "coh": c, "decided": False}
    return out


class Sink:
    def __init__(self) -> None:
        self.done = set()
        if REC.exists():
            for line in REC.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    self.done.add((d["set"], d["d"], d["i"]))
        self.fh = open(REC, "a", encoding="utf-8")

    def has(self, s, d, i) -> bool:
        return (s, d, i) in self.done

    def put(self, s, d, i, rec) -> None:
        self.fh.write(json.dumps({"set": s, "d": d, "i": i, **rec}) + "\n")
        self.fh.flush()
        self.done.add((s, d, i))


def full(E, lp, uniform=False, lm=True) -> dict:
    return {**c5_part(E, lp, lm), "guards": guard_part(E, lp, uniform)}


# --- stages --------------------------------------------------------------------------------------------

def stage_neural(E: Env, K: Sink) -> None:
    import scipy.io

    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB

    vocab = set(VOCAB[1:])
    mt = meta()
    S = set(s_positions())
    lp_test_real = load_lps("test", "real")
    lp_val_real = load_lps("val", "real")
    checks = json.loads((OWN / "checks.json").read_text(encoding="utf-8")) if (OWN / "checks.json").exists() else {}
    t0 = time.time()
    for si, sess in enumerate(E.sessions):
        test_i = [i for i, r in enumerate(mt["test"]) if r["session"] == sess]
        val_i = [i for i, r in enumerate(mt["val"]) if r["session"] == sess and i in S]
        # only some singleLetters.mat files hold doNothing trials (run-time finding: t5.2019.05.08 only)
        dn = [w for w in scipy.io.whosmat(str(RAW / sess / "singleLetters.mat")) if w[0] == "neuralActivityCube_doNothing"]
        n_dn = int(dn[0][1][0]) if dn else 0
        todo = ([("ts", d, i) for i in test_i for d in DRAWS] + [("zero", 0, i) for i in test_i]
                + [("rev_in", 0, i) for i in test_i] + [("val_ts", d, i) for i in val_i for d in DRAWS]
                + [("do_nothing", 0, si * 27 + k) for k in range(n_dn)])
        if all(K.has(*t) for t in todo) and sess in checks:
            continue
        items = {it.key: it for it in R.read_willett_session(RAW / sess)
                 if it.truth and all(c in vocab for c in it.truth)}
        # check: the decoder on the raw sentence gives the P14-41 log-probs
        if sess not in checks:
            i0, v0 = test_i[0], val_i[0] if val_i else None
            x = np.asarray(items[mt["test"][i0]["key"]].x)
            dif = float(np.abs(E.m.log_probs(x, sess) - lp_test_real[i0]).max())
            difv = (float(np.abs(E.m.log_probs(np.asarray(items[mt["val"][v0]["key"]].x), sess)
                                 - lp_val_real[v0]).max()) if v0 is not None else None)
            checks[sess] = {"test_maxabs": dif, "val_maxabs": difv}
            assert dif < 1e-3 and (difv is None or difv < 1e-3), checks[sess]
            save_json(checks, OWN / "checks.json")
        for i in test_i:
            r = mt["test"][i]
            x = np.asarray(items[r["key"]].x)
            assert len(x) == r["T"], (r["key"], len(x), r["T"])
            for d in DRAWS:
                if not K.has("ts", d, i):
                    xs = x[rng_for(d, "test", i, "timeshuf").permutation(len(x))]
                    K.put("ts", d, i, full(E, E.m.log_probs(xs, sess)))
            if not K.has("zero", 0, i):
                K.put("zero", 0, i, full(E, E.m.log_probs(np.zeros_like(x), sess)))
            if not K.has("rev_in", 0, i):
                K.put("rev_in", 0, i, full(E, E.m.log_probs(np.ascontiguousarray(x[::-1]), sess)))
        for i in val_i:
            x = np.asarray(items[mt["val"][i]["key"]].x)
            for d in DRAWS:
                if not K.has("val_ts", d, i):
                    xs = x[rng_for(d, "val", i, "timeshuf").permutation(len(x))]
                    K.put("val_ts", d, i, c5_part(E, E.m.log_probs(xs, sess), lm=False))
        del items
        gc.collect()
        if n_dn:
            cube = scipy.io.loadmat(str(RAW / sess / "singleLetters.mat"),
                                    variable_names=["neuralActivityCube_doNothing"])["neuralActivityCube_doNothing"]
            assert cube.shape == (n_dn, 201, 192) and n_dn <= 27, cube.shape
            for k in range(n_dn):
                if not K.has("do_nothing", 0, si * 27 + k):
                    K.put("do_nothing", 0, si * 27 + k, full(E, E.m.log_probs(np.asarray(cube[k]), sess)))
            del cube
        gc.collect()
        log(f"neural: session {si + 1}/10 {sess} done ({time.time() - t0:.0f} s)")


def stage_lines(E: Env, K: Sink) -> None:
    import scipy.io

    mt = meta()
    if all(K.has("lines", 0, i) for i in range(len(mt["test"]))):
        log("lines: done, skipped")
        return
    z = scipy.io.loadmat(str(RAW / LINES_SESSION / "straightLines.mat"),
                         variable_names=["neuralActivityTimeSeries", "blockNumsTimeSeries"])
    ts, b = z["neuralActivityTimeSeries"], z["blockNumsTimeSeries"].ravel()
    cut = np.nonzero(np.diff(b) != 0)[0] + 1
    runs = list(zip(np.concatenate([[0], cut]).tolist(), np.concatenate([cut, [len(b)]]).tolist()))
    rng = np.random.default_rng(LINES_SEED)
    segs = []
    for r in mt["test"]:
        T = int(r["T"])
        el = [(a, e) for a, e in runs if e - a >= T]
        a, e = el[int(rng.integers(len(el)))]
        s0 = a + int(rng.integers(0, e - a - T + 1))
        segs.append((s0, T))
    save_json({"runs": runs, "segments": segs}, OWN / "lines-segments.json")
    t0 = time.time()
    for i, (s0, T) in enumerate(segs):
        if not K.has("lines", 0, i):
            K.put("lines", 0, i, full(E, E.m.log_probs(np.asarray(ts[s0:s0 + T]), LINES_LAYER)))
    log(f"lines: {len(segs)} segments from {len(runs)} blocks ({time.time() - t0:.0f} s)")


def stage_frames(E: Env, K: Sink) -> None:
    lp_real = load_lps("test", "real")
    t0 = time.time()
    for i, lp in enumerate(lp_real):
        if not K.has("real", 0, i):
            K.put("real", 0, i, full(E, lp))
        if not K.has("rev_out", 0, i):
            K.put("rev_out", 0, i, full(E, np.ascontiguousarray(lp[::-1])))
    log(f"frames: real + rev_out done ({time.time() - t0:.0f} s)")
    for d in DRAWS:
        for i, lp in enumerate(lp_real):
            if not K.has("fs", d, i):
                K.put("fs", d, i, full(E, lp[rng_for(d, "test", i, "frameshuf").permutation(len(lp))]))
        log(f"frames: frame-shuffled draw {d} done ({time.time() - t0:.0f} s)")
    for d in DRAWS:
        for i, lp in enumerate(lp_real):
            if not K.has("uni", d, i):
                T, V = lp.shape
                zz = np.full((T, V), -math.log(V)) + 0.05 * rng_for(d, "test", i, "uniform").standard_normal((T, V))
                x = (zz - np.log(np.exp(zz).sum(1, keepdims=True))).astype(np.float32)
                K.put("uni", d, i, full(E, x, uniform=True))
        log(f"frames: uniform draw {d} done ({time.time() - t0:.0f} s)")
    save_json({k: {"seen_this_run": E.uni_seen[k], "checked": len(E.uni_check[k]),
                   "check_equal": all(E.uni_check[k]) and E.uni_ok[k]} for k in E.g},
              OWN / f"uniform-check-{int(time.time())}.json")


# --- score ---------------------------------------------------------------------------------------------

def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    from scipy.stats import beta

    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


def pct(v) -> list[float]:
    v = np.asarray(list(v), float)
    return [round(float(np.percentile(v, q)), 6) for q in (0, 5, 50, 95, 100)] if len(v) else []


def fit_logit(fr: list[dict], fn: list[dict], ridge: float = 1.0):
    """The ScoreGate.fit rule (feature logit) on precomputed features; checked against the shipped gate."""
    from fidetype.pretrained.lmreadout import LOGIT_INPUTS

    Z = np.array([[f[k] for k in LOGIT_INPUTS] for f in fr + fn])
    y = np.concatenate([np.ones(len(fr)), np.zeros(len(fn))])
    mu, sd = Z.mean(0), Z.std(0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    X = np.column_stack([np.ones(len(Z)), (Z - mu) / sd])
    w = np.zeros(X.shape[1])
    pen = np.full(X.shape[1], float(ridge))
    pen[0] = 0.0
    for _ in range(100):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        g = X.T @ (p - y) + pen * w
        H = (X * (p * (1 - p))[:, None]).T @ X + np.diag(pen) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w = w - step
        if float(np.abs(step).max()) < 1e-10:
            break
    m = int(math.floor(0.01 * len(fr) + 1e-9))
    gate = {"mean": mu, "scale": sd, "coef": w[1:], "intercept": float(w[0]),
            "r_max": float(2.0 * max(f["kps"] for f in fr))}
    sc = sorted(score_f(gate, f) for f in fr)
    gate["lo"] = float(sc[m])
    return gate


def score_f(gate: dict, f: dict) -> float:
    from fidetype.pretrained.lmreadout import LOGIT_INPUTS

    z = np.array([f[k] for k in LOGIT_INPUTS])
    return float(gate["intercept"] + np.dot(gate["coef"], (z - np.asarray(gate["mean"])) / np.asarray(gate["scale"])))


def pass_f(gate: dict, f: dict) -> bool:
    return bool(f["n_keys"] >= 1 and f["kps"] <= gate["r_max"] and score_f(gate, f) >= gate["lo"])


def stage_score(E: Env) -> None:
    from fidetype.trust.dropin import ControlResult, offer_control

    rows: dict = {}
    for line in REC.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            rows[(d["set"], d["d"], d["i"])] = d
    mt = meta()
    n_test = len(mt["test"])
    res: dict = {"config_id": {k: g.config_id for k, g in E.g.items()}, "offer_gate_threshold": E.thr,
                 "c5_gate": E.c5.to_dict(), "n_records": len(rows),
                 "checks": json.loads((OWN / "checks.json").read_text(encoding="utf-8"))}

    def recs(s, ds=(0,), n=n_test):
        if s == "do_nothing":  # keys si * 27 + k of the sessions that have doNothing trials
            return [rows[k] for k in sorted(k for k in rows if k[0] == s)]
        return [rows[(s, d, i)] for d in ds for i in range(n)]

    n_dn = len(recs("do_nothing"))

    # ---- part A: C5 emits on the new draws
    rng = np.random.default_rng(BOOT_SEED)
    A = {}
    for s in ("ts", "uni", "fs"):
        per_draw = [sum(r["c5_emit"] for r in recs(s, (d,))) for d in DRAWS]
        k, n = sum(per_draw), len(DRAWS) * n_test
        M = np.array([[rows[(s, d, i)]["c5_emit"] for d in DRAWS] for i in range(n_test)], float)
        boot = [M[rng.integers(0, n_test, n_test)].mean() for _ in range(N_BOOT)]
        A[s] = {"emit": k, "n": n, "rate": k / n, "cp95_upper": cp_upper(k, n),
                "per_draw": per_draw, "per_draw_min_med_max": [min(per_draw), float(np.median(per_draw)), max(per_draw)],
                "draws_above_4": sum(c > 4 for c in per_draw),
                "cluster_boot95_upper": float(np.percentile(boot, 95)),
                "c5_pass": sum(r["c5_pass"] for r in recs(s, DRAWS)),
                "sentences_ever_emit": int((M.sum(1) > 0).sum())}
    for s, n in (("zero", n_test), ("real", n_test), ("rev_in", n_test), ("rev_out", n_test), ("lines", n_test),
                 ("do_nothing", n_dn)):
        rr = recs(s, n=n)
        A[s] = {"emit": sum(r["c5_emit"] for r in rr), "c5_pass": sum(r["c5_pass"] for r in rr), "n": len(rr)}
    vts = [rows[("val_ts", d, i)] for d in DRAWS for i in s_positions()]
    A["val_ts"] = {"c5_pass": sum(r["c5_pass"] for r in vts), "n": len(vts)}
    A["rules"] = {"A1": {"pass": A["ts"]["cp95_upper"] <= 0.05, "value": A["ts"]["cp95_upper"]},
                  "A2": {"pass": A["uni"]["cp95_upper"] <= 0.05, "value": A["uni"]["cp95_upper"]},
                  "A3": {"pass": A["zero"]["emit"] == 0, "value": f"{A['zero']['emit']} / {n_test}"}}
    res["part_A"] = A

    # ---- part B: re-fits of C5 (val only fits)
    S = s_positions()
    lpv, lpvt = load_lps("val", "real"), load_lps("val", "timeshuf")
    fr = {i: pfeat(lpv[i]) for i in S}
    f0 = {i: pfeat(lpvt[i]) for i in S}
    del lpv, lpvt
    fnew = {(d, i): rows[("val_ts", d, i)]["pf"] for d in DRAWS for i in S}
    shipped = E.c5.to_dict()
    g_all = fit_logit([fr[i] for i in S], [f0[i] for i in S])
    res["part_B_check_refit_equals_shipped"] = {
        "coef_maxabs": float(np.abs(np.asarray(g_all["coef"]) - np.asarray(shipped["coef"])).max()),
        "lo_abs": abs(g_all["lo"] - shipped["lo"]), "r_max_abs": abs(g_all["r_max"] - shipped["r_max"])}
    lpt, lptt = load_lps("test", "real"), load_lps("test", "timeshuf")
    ft_real = [pfeat(x) for x in lpt]
    ft_ts0 = [pfeat(x) for x in lptt]
    del lpt, lptt
    ft_tsn = [rows[("ts", d, i)]["pf"] for d in DRAWS for i in range(n_test)]

    def gsum(g):
        return {"coef": [float(c) for c in g["coef"]], "intercept": g["intercept"], "lo": g["lo"], "r_max": g["r_max"]}

    srng = np.random.default_rng(SPLIT_SEED)
    splits = []
    for _ in range(N_SPLITS):
        p = srng.permutation(len(S))
        a, b = [S[j] for j in p[:33]], [S[j] for j in p[33:]]
        g = fit_logit([fr[i] for i in a], [f0[i] for i in a])
        splits.append({**gsum(g), "B_real_gated": sum(not pass_f(g, fr[i]) for i in b),
                       "B_ts0_pass": sum(pass_f(g, f0[i]) for i in b),
                       "B_tsnew_pass": sum(pass_f(g, fnew[(d, i)]) for d in DRAWS for i in b)})
    draws = []
    for d in DRAWS:
        g = fit_logit([fr[i] for i in S], [fnew[(d, i)] for i in S])
        draws.append({"d": d, **gsum(g), "test_real_gated": sum(not pass_f(g, f) for f in ft_real),
                      "test_ts0_pass": sum(pass_f(g, f) for f in ft_ts0),
                      "test_tsnew_pass": sum(pass_f(g, f) for f in ft_tsn)})
    names = ["peak", "neg_entropy", "nb_share", "kps", "log_n_keys"]

    def spread(lst):
        o = {f"coef_{nm}": pct(x["coef"][j] for x in lst) for j, nm in enumerate(names)}
        o.update(intercept=pct(x["intercept"] for x in lst), lo=pct(x["lo"] for x in lst),
                 r_max=pct(x["r_max"] for x in lst))
        o["sign_flips_vs_shipped"] = {nm: sum(np.sign(x["coef"][j]) != np.sign(shipped["coef"][j]) for x in lst)
                                      for j, nm in enumerate(names)}
        return o

    res["part_B"] = {
        "shipped": {"coef": dict(zip(names, shipped["coef"])), "intercept": shipped["intercept"], "lo": shipped["lo"],
                    "r_max": shipped["r_max"]},
        "splits": {"n": N_SPLITS, "spread_0_5_50_95_100": spread(splits),
                   "B_real_gated_of_33": pct(x["B_real_gated"] for x in splits),
                   "B_real_gated_sum": sum(x["B_real_gated"] for x in splits),
                   "B_ts0_pass_of_33": pct(x["B_ts0_pass"] for x in splits),
                   "B_ts0_pass_sum": sum(x["B_ts0_pass"] for x in splits),
                   "B_tsnew_pass_of_330": pct(x["B_tsnew_pass"] for x in splits),
                   "B_tsnew_pass_sum": sum(x["B_tsnew_pass"] for x in splits),
                   "eval_n_per_split": {"real": 33, "ts0": 33, "tsnew": 330}},
        "draw_refits": {"rows": draws, "spread_0_5_50_95_100": spread(draws),
                        "test_n": {"real": n_test, "ts0": n_test, "tsnew": len(ft_tsn)}}}
    save_json(splits, OWN / "refit-splits.json")

    # ---- part C: the coherence offer gates
    C = {}
    for k in E.g:
        real = recs("real")
        n_real_off = sum(r["guards"][k]["action"] == "offer" for r in real)
        row = {"real": {"n": n_test, "offer": n_real_off,
                        "gated_by_offer_gate": sum(bool(r["guards"][k]["gated"]) for r in real),
                        "commit": sum(r["guards"][k]["action"] == "commit" for r in real),
                        "coh_min_med_max": pct(r["guards"][k]["coh"] for r in real)}}
        rules = {}
        for rid, s, ds, n, kind in (("C1", "ts", DRAWS, n_test, "pooled"), ("C2", "fs", DRAWS, n_test, "pooled"),
                                    ("C3", "uni", DRAWS, n_test, "pooled"), ("C4", "rev_in", (0,), n_test, "count"),
                                    ("C5r", "do_nothing", (0,), n_dn, "count"), ("C6", "lines", (0,), n_test, "count"),
                                    ("C7", "rev_out", (0,), n_test, "none")):
            rr = recs(s, ds, n)
            g = [r["guards"][k] for r in rr]
            n_off = sum(x["action"] == "offer" for x in g)
            n_com = sum(x["action"] == "commit" for x in g)
            emit, nn = n_off + n_com, len(g)
            oc = offer_control(n_test, n_real_off, [ControlResult(s, s, nn, n_com, int(math.floor(0.05 * nn + 1e-9)),
                                                                  n_off)], rate=0.05)
            ent = {"n": nn, "offer": n_off, "commit": n_com, "emit": emit,
                   "gated_by_offer_gate": sum(bool(x["gated"]) for x in g),
                   "ungated_offer_known": sum((x["action"] == "offer") or bool(x["gated"]) for x in g if x["decided"]),
                   "decided": sum(x["decided"] for x in g),
                   "coh_0_5_50_95_100": pct(x["coh"] for x in g),
                   "coh_at_or_above_threshold": sum(x["coh"] >= E.thr[k] for x in g),
                   "offer_control": {"passed": bool(oc["passed"]), "p_value": oc["controls"][0].get("p_value"),
                                     "offer_rate": oc["controls"][0]["offer_rate"]}}
            if kind == "pooled":
                per = [sum(r["guards"][k]["action"] in ("offer", "commit") for r in recs(s, (d,))) for d in DRAWS]
                ent.update(cp95_upper=cp_upper(emit, nn), per_draw=per, draws_above_4=sum(c > 4 for c in per))
                ok = ent["cp95_upper"] <= 0.05 and oc["passed"]
            elif kind == "count":
                ok = emit <= int(math.floor(0.05 * nn + 1e-9)) and oc["passed"]
            else:
                ok = None
            if s == "rev_out":
                cr = [r["guards"][k]["coh"] for r in real]
                ent["coh_equal_to_real_1e-9"] = sum(abs(a - b) <= 1e-9 for a, b in zip(cr, [x["coh"] for x in g]))
            row[s] = ent
            rules[rid] = {"set": s, "pass": ok}
        C[k] = {"rows": row, "rules": rules,
                "all_rules_pass": all(v["pass"] for v in rules.values() if v["pass"] is not None)}
    res["part_C"] = C
    res["uniform_fast_path_checks"] = [json.loads(p.read_text(encoding="utf-8"))
                                       for p in sorted(OWN.glob("uniform-check-*.json"))]
    res["lines"] = {"session": LINES_SESSION, "layer_index": LINES_LAYER,
                    "n_blocks": len(json.loads((OWN / "lines-segments.json").read_text(encoding="utf-8"))["runs"])}
    save_json(res, OUT / "results.json")
    log("score: written results/results.json; A " + json.dumps(A["rules"]) + "; C "
        + json.dumps({k: v["rules"] for k, v in C.items()}))


def main(argv: list[str]) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    assert stage in ("neural", "lines", "frames", "score", "all")
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            E = Env()
            log(f"start {stage}; offer-gate thresholds {E.thr}; C5 lo {E.c5.lo}")
            if stage in ("neural", "lines", "frames", "all"):
                K = Sink()
                if stage in ("neural", "all"):
                    stage_neural(E, K)
                if stage in ("lines", "all"):
                    stage_lines(E, K)
                if stage in ("frames", "all"):
                    stage_frames(E, K)
                K.fh.close()
            if stage in ("score", "all"):
                stage_score(E)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stage} ({time.time() - t0:.0f} s); peak {mem_mb()[1]:.0f} MB")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
