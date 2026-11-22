r"""P14-57 (direction-aware offer gate) and P14-58 (C5 threshold rule) for willett-hw. Plan: plan.md.

Our own code (Apache-2.0). CPU only. Stages:
  select   P14-57 selection on the 66 S val inputs (both guards).
  p57      P14-57 test: real + rev_out, P14-55 offered nulls made again, P14-54 nulls, P14-54 V re-check.
  p58      P14-58: lo_new from val, split stability, new time-shuffled test draws d=11..20.
  score    results/*.json (counts, thresholds and summary values only).
  all      every stage, then the DONE file.

Run (repo root; detached form: launch.py)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-21-p14-57-direction-aware-offer/run.py all

Per-item records (features, actions; no text) stay in C:\Users\zhang\bci-data\derived\p14-57.
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
P1441 = DATA / "derived/p14-41"  # read only
P1455 = DATA / "derived/p14-55"  # read only
OWN = DATA / "derived/p14-57"
OUT = HERE / "results"
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-26ae951a20a0cddd"}
CANDS = ("nb_decay_asym", "-nb_decay_asym", "nb_time_asym", "-nb_time_asym", "time_asym", "-time_asym")
DIR_BASE = ("time_asym", "nb_time_asym", "nb_decay_asym")
NEW_DRAWS = tuple(range(11, 21))
OLD_DRAWS = tuple(range(1, 11))
SPLIT_SEED, BOOT_SEED, N_SPLITS, N_BOOT = 5556, 5757, 200, 2000
HD_Q, NULL_Q = 0.03, 0.99
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


def rng_for(tag: str, d: int, split: str, i: int, kind: str) -> np.random.Generator:
    h = hashlib.sha256(f"{tag}|{d}|{split}|{i}|{kind}".encode()).digest()
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


def p1455_rows() -> dict:
    rows = {}
    for line in (P1455 / "items.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            rows[(d["set"], d["d"], d["i"])] = d
    return rows


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    from scipy.stats import beta

    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


def pct(v) -> list[float]:
    v = np.asarray(list(v), float)
    return [round(float(np.percentile(v, q)), 6) for q in (0, 5, 50, 95, 100)] if len(v) else []


class Jsonl:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows: dict = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    self.rows[tuple(d["key"])] = d
        self.fh = open(path, "a", encoding="utf-8")

    def has(self, *key) -> bool:
        return tuple(key) in self.rows

    def put(self, key, rec) -> None:
        d = {"key": list(key), **rec}
        self.fh.write(json.dumps(d) + "\n")
        self.fh.flush()
        self.rows[tuple(key)] = d


# --- objects under test --------------------------------------------------------------------------------

class Env:
    def __init__(self) -> None:
        import fidetype.pretrained as ftp

        self.m = ftp.load("willett-hw")
        self.rg = self.m.lm_readout()
        self.c5 = self.rg.gate
        self.g = {"builtin": self.m.guard(), "lm": self.m.guard(readout="lm")}
        for k, g in self.g.items():
            assert g.config_id == CFG[k], (k, g.config_id)
            assert len(g.offer_gates) == 1 and g.offer_gates[0].feature == "coherence", k
        self.coh = {k: g.offer_gates[0] for k, g in self.g.items()}
        self.sessions = list(self.m.manifest.architecture["sessions"])


def decide(g, lp) -> dict:
    """Decision of the guard as set (offer features on): action, offer-gate flag, coherence, direction values."""
    g.collect_offer_features = True
    r = g._decide_quiet(np.asarray(lp), None)
    f = g.last_offer_features
    return {"action": str(getattr(r.action, "value", r.action)).lower(), "gated": g._offer_gate_why is not None,
            "coh": float(f["coherence"]), "dir": {k: float(f[k]) for k in DIR_BASE}}


def cand_value(rec: dict, cand: str) -> float:
    from fidetype.trust.offer_gate import base_feature

    b, s = base_feature(cand)
    return s * rec["dir"][b]


def after(rec: dict, cand: str) -> str:
    """The action with the direction gate (threshold 0) added after the coherence gate."""
    if rec["action"] == "offer" and cand_value(rec, cand) < 0.0:
        return "withhold"
    return rec["action"]


# --- P14-57 select -------------------------------------------------------------------------------------

def stage_select(E: Env) -> dict:
    K = Jsonl(OWN / "select.jsonl")
    lpv = load_lps("val", "real")
    S = s_positions()
    t0 = time.time()
    for k, g in E.g.items():
        for i in S:
            if not K.has(k, "real", i):
                K.put((k, "real", i), decide(g, lpv[i]))
            if not K.has(k, "rev_out", i):
                K.put((k, "rev_out", i), decide(g, np.ascontiguousarray(lpv[i][::-1])))
        log(f"select: {k} done ({time.time() - t0:.0f} s)")
    out = {}
    for k in E.g:
        real = [K.rows[(k, "real", i)] for i in S]
        rev = [K.rows[(k, "rev_out", i)] for i in S]
        off = [r for r in real if r["action"] == "offer"]
        m = len(off)
        loss = {c: sum(cand_value(r, c) < 0.0 for r in off) for c in CANDS}
        chosen = min(CANDS, key=lambda c: (loss[c], CANDS.index(c)))
        limit = int(math.floor(0.05 * m + 1e-9))
        out[k] = {"m_real_offers": m, "n": len(real), "loss": loss, "chosen": chosen, "loss_limit": limit,
                  "information_only": loss[chosen] > limit,
                  "values_real_offers": {c: pct(cand_value(r, c) for r in off) for c in CANDS},
                  "rev_out_val": {"offer_coherence_only": sum(r["action"] == "offer" for r in rev),
                                  "offer_with_direction": sum(after(r, chosen) == "offer" for r in rev),
                                  "n": len(rev)},
                  "rev_coherence_equal_1e-9": sum(abs(a["coh"] - b["coh"]) <= 1e-9 for a, b in zip(real, rev)),
                  "rev_direction_antisym_1e-9": sum(all(abs(a["dir"][x] + b["dir"][x]) <= 1e-9 for x in DIR_BASE)
                                                    for a, b in zip(real, rev))}
    save_json(out, OUT / "p57-selection.json")
    log("select: " + json.dumps({k: (v["chosen"], v["loss"][v["chosen"]], v["m_real_offers"]) for k, v in out.items()}))
    K.fh.close()
    return out


# --- P14-57 test ---------------------------------------------------------------------------------------

def stage_p57(E: Env) -> None:
    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB
    from fidetype.trust.offer_gate import OfferGate

    sel = json.loads((OUT / "p57-selection.json").read_text(encoding="utf-8"))
    K = Jsonl(OWN / "p57.jsonl")
    mt = meta()
    lp_real = load_lps("test", "real")
    t0 = time.time()
    # real + rev_out: coherence-gated decisions, then the same with both gates (equivalence check)
    for k, g in E.g.items():
        both = OfferGate(sel[k]["chosen"], 0.0, note="P14-57 val-only selection")
        for i, lp in enumerate(lp_real):
            for s, x in (("real", lp), ("rev_out", np.ascontiguousarray(lp[::-1]))):
                if not K.has(k, s, 0, i):
                    g.set_offer_gate([E.coh[k]])
                    a = decide(g, x)
                    g.set_offer_gate([E.coh[k], both])
                    b = decide(g, x)
                    g.set_offer_gate([E.coh[k]])
                    K.put((k, s, 0, i), {**a, "both_action": b["action"]})
        log(f"p57: {k} real + rev_out done ({time.time() - t0:.0f} s)")
    # P14-54 test nulls, decided with both gates in full (plus the coherence-only action)
    cache = {"timeshuf": load_lps("test", "timeshuf"), "zero": load_lps("test", "zero")}
    for kind in ("timeshuf", "zero", "frameshuf", "uniform"):
        for i, lpr in enumerate(lp_real):
            if all(K.has(k, "p54_" + kind, 0, i) for k in E.g):
                continue
            if kind in cache:
                x = cache[kind][i]
            elif kind == "frameshuf":
                x = lpr[rng_for("p14-41", 0, "test", i, "frameshuf").permutation(len(lpr))]
            else:
                T, V = lpr.shape
                z = np.full((T, V), -math.log(V)) + 0.05 * rng_for("p14-41", 0, "test", i, "uniform").standard_normal((T, V))
                x = z - np.log(np.exp(z).sum(1, keepdims=True))
            for k, g in E.g.items():
                if not K.has(k, "p54_" + kind, 0, i):
                    g.set_offer_gate([E.coh[k]])
                    K.put((k, "p54_" + kind, 0, i), decide(g, x))
        log(f"p57: P14-54 {kind} done ({time.time() - t0:.0f} s)")
    # P14-55 nulls: only the inputs that were offers there can change; make them again
    rows = p1455_rows()
    need: dict = {}
    for (s, d, i), r in rows.items():
        if "guards" in r and s not in ("real", "rev_out"):
            if any(v["action"] == "offer" for v in r["guards"].values()):
                need[(s, d, i)] = r
    log(f"p57: P14-55 offered null inputs to make again: {len(need)} "
        f"({sorted(set(s for s, _, _ in need))})")
    assert all(s in ("ts", "rev_in", "fs", "uni") for s, _, _ in need), sorted(set(s for s, _, _ in need))
    by_sess: dict = {}
    for (s, d, i) in need:
        if s in ("ts", "rev_in"):
            by_sess.setdefault(mt["test"][i]["session"], []).append((s, d, i))
    vocab = set(VOCAB[1:])
    for sess, keys in sorted(by_sess.items()):
        if all(K.has(k, "p55_" + s, d, i) for s, d, i in keys for k in E.g):
            continue
        items = {it.key: it for it in R.read_willett_session(RAW / sess)
                 if it.truth and all(c in vocab for c in it.truth)}
        for s, d, i in keys:
            x = np.asarray(items[mt["test"][i]["key"]].x)
            xs = (x[rng_for("p14-55", d, "test", i, "timeshuf").permutation(len(x))] if s == "ts"
                  else np.ascontiguousarray(x[::-1]))
            lp = E.m.log_probs(xs, sess)
            for k, g in E.g.items():
                if not K.has(k, "p55_" + s, d, i):
                    g.set_offer_gate([E.coh[k]])
                    rec = decide(g, lp)
                    rec["p55_action"] = rows[(s, d, i)]["guards"][k]["action"]
                    rec["p55_coh"] = rows[(s, d, i)]["guards"][k]["coh"]
                    K.put((k, "p55_" + s, d, i), rec)
        del items
        gc.collect()
    for (s, d, i) in need:
        if s in ("fs", "uni"):
            lpr = lp_real[i]
            if s == "fs":
                x = lpr[rng_for("p14-55", d, "test", i, "frameshuf").permutation(len(lpr))]
            else:
                T, V = lpr.shape
                zz = np.full((T, V), -math.log(V)) + 0.05 * rng_for("p14-55", d, "test", i, "uniform").standard_normal((T, V))
                x = (zz - np.log(np.exp(zz).sum(1, keepdims=True))).astype(np.float32)
            for k, g in E.g.items():
                if not K.has(k, "p55_" + s, d, i):
                    g.set_offer_gate([E.coh[k]])
                    rec = decide(g, x)
                    rec["p55_action"] = rows[(s, d, i)]["guards"][k]["action"]
                    rec["p55_coh"] = rows[(s, d, i)]["guards"][k]["coh"]
                    K.put((k, "p55_" + s, d, i), rec)
    log(f"p57: P14-55 nulls made again ({time.time() - t0:.0f} s)")
    # P14-54 V re-check with both gates
    import fidetype.trust as ft

    lpv, lpvt = load_lps("val", "real"), load_lps("val", "timeshuf")
    for k, g in E.g.items():
        p = OUT / f"p57-recheck-{k}.json"
        if p.exists():
            continue
        g.set_offer_gate([E.coh[k], OfferGate(sel[k]["chosen"], 0.0)])
        rc = ft.recheck_offer_control(g, lpv, null_inputs=lpvt)
        g.set_offer_gate([E.coh[k]])
        rc.update(guard=k, config_id=g.config_id, gates=[E.coh[k].to_dict(), OfferGate(sel[k]["chosen"], 0.0).to_dict()])
        save_json(rc, p)
        log(f"p57: V re-check {k}: passed {rc['passed']}, real {rc['real']}, "
            f"{[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]} ({time.time() - t0:.0f} s)")
    K.fh.close()


# --- P14-58 --------------------------------------------------------------------------------------------

def pfeat(lp) -> dict:
    from fidetype.pretrained._xbody import BIN_S
    from fidetype.pretrained.lmreadout import posterior_features

    f = posterior_features(np.asarray(lp, np.float64), BIN_S)
    return {k: float(f[k]) for k in PF_KEYS}


def fit_logit(fr: list[dict], fn: list[dict], ridge: float = 1.0) -> dict:
    """The ScoreGate.fit rule (feature logit) on precomputed features (copy of P14-55 run.py, checked there)."""
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
    gate = {"mean": mu, "scale": sd, "coef": w[1:], "intercept": float(w[0]),
            "r_max": float(2.0 * max(f["kps"] for f in fr))}
    m = int(math.floor(0.01 * len(fr) + 1e-9))
    gate["lo_min_rule"] = float(sorted(score_f(gate, f) for f in fr)[m])
    return gate


def score_f(gate: dict, f: dict) -> float:
    from fidetype.pretrained.lmreadout import LOGIT_INPUTS

    z = np.array([f[k] for k in LOGIT_INPUTS])
    return float(gate["intercept"] + np.dot(gate["coef"], (z - np.asarray(gate["mean"])) / np.asarray(gate["scale"])))


def pass_f(gate: dict, f: dict, lo: float) -> bool:
    return bool(f["n_keys"] >= 1 and f["kps"] <= gate["r_max"] and score_f(gate, f) >= lo)


def stage_p58(E: Env) -> None:
    from fidetype.pretrained.lmreadout import quantile_lo

    t0 = time.time()
    S = s_positions()
    rows = p1455_rows()
    shipped = E.c5.to_dict()
    lpv, lpvt = load_lps("val", "real"), load_lps("val", "timeshuf")
    fr = {i: pfeat(lpv[i]) for i in S}
    f0 = {i: pfeat(lpvt[i]) for i in S}
    del lpv, lpvt
    fnew = {(d, i): rows[("val_ts", d, i)]["pf"] for d in OLD_DRAWS for i in S}
    real_sc = [score_f(shipped, fr[i]) for i in S]
    null_sc = [score_f(shipped, f0[i]) for i in S] + [score_f(shipped, fnew[(d, i)]) for d in OLD_DRAWS for i in S]
    # check: our score copy equals the shipped gate's score on the P14-55 records
    chk = max(abs(score_f(shipped, fnew[(d, i)]) - rows[("val_ts", d, i)]["c5_score"]) for d in OLD_DRAWS for i in S)
    lo_new, parts = quantile_lo(real_sc, null_sc, q=HD_Q, null_q=NULL_Q)
    gate_new = E.c5.with_lo(lo_new)
    log(f"p58: lo_new {lo_new:.5f} parts {parts} (shipped lo {E.c5.lo:.5f}); score check {chk:.2e}")
    # stability over the P14-55 half splits
    srng = np.random.default_rng(SPLIT_SEED)
    splits = []
    for _ in range(N_SPLITS):
        p = srng.permutation(len(S))
        a, b = [S[j] for j in p[:33]], [S[j] for j in p[33:]]
        g = fit_logit([fr[i] for i in a], [f0[i] for i in a])
        nA = [score_f(g, f0[i]) for i in a] + [score_f(g, fnew[(d, i)]) for d in OLD_DRAWS for i in a]
        lo_q, _ = quantile_lo([score_f(g, fr[i]) for i in a], nA, q=HD_Q, null_q=NULL_Q)
        nullB = [f0[i] for i in b] + [fnew[(d, i)] for d in OLD_DRAWS for i in b]
        row = {}
        for name, lo in (("min_rule", g["lo_min_rule"]), ("new_rule", lo_q)):
            row[name] = {"lo": lo, "B_real_gated": sum(not pass_f(g, fr[i], lo) for i in b),
                         "B_null_pass": sum(pass_f(g, f, lo) for f in nullB)}
        splits.append(row)
    stab = {name: {"lo": pct(r[name]["lo"] for r in splits),
                   "B_real_gated_of_33": pct(r[name]["B_real_gated"] for r in splits),
                   "B_real_gated_sum": sum(r[name]["B_real_gated"] for r in splits),
                   "B_null_pass_of_363": pct(r[name]["B_null_pass"] for r in splits),
                   "B_null_pass_sum": sum(r[name]["B_null_pass"] for r in splits)} for name in ("min_rule", "new_rule")}
    stab["n_splits"] = N_SPLITS
    stab["eval_n_per_split"] = {"real": 33, "null": 363}
    save_json({"lo_new": lo_new, "parts": parts, "shipped_lo": E.c5.lo, "hd_q": HD_Q, "null_q": NULL_Q,
               "n_real": len(real_sc), "n_null": len(null_sc), "score_copy_check_maxabs": chk,
               "real_val_gated_new": sum(s < lo_new for s in real_sc),
               "null_val_pass_new_score_only": sum(s >= lo_new for s in null_sc),
               "stability": stab, "gate_new": gate_new.to_dict()}, OUT / "p58-rule.json")
    log(f"p58: stability done ({time.time() - t0:.0f} s)")
    # new time-shuffled test draws d = 11..20
    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB

    K = Jsonl(OWN / "p58.jsonl")
    mt = meta()
    vocab = set(VOCAB[1:])
    for si, sess in enumerate(E.sessions):
        test_i = [i for i, r in enumerate(mt["test"]) if r["session"] == sess]
        if all(K.has("ts", d, i) for i in test_i for d in NEW_DRAWS):
            continue
        items = {it.key: it for it in R.read_willett_session(RAW / sess)
                 if it.truth and all(c in vocab for c in it.truth)}
        for i in test_i:
            x = np.asarray(items[mt["test"][i]["key"]].x)
            assert len(x) == mt["test"][i]["T"]
            for d in NEW_DRAWS:
                if K.has("ts", d, i):
                    continue
                lp = np.asarray(E.m.log_probs(x[rng_for("p14-57", d, "test", i, "timeshuf").permutation(len(x))], sess),
                                np.float64)
                p_new, p_old = bool(gate_new.passes(lp)), bool(E.c5.passes(lp))
                txt = len(E.rg.text(lp, use_gate=False)) > 0 if (p_new or p_old) else False
                K.put(("ts", d, i), {"score": float(E.c5.score(lp)), "pass_new": p_new, "pass_old": p_old,
                                     "emit_new": p_new and txt, "emit_old": p_old and txt})
        del items
        gc.collect()
        log(f"p58: session {si + 1}/10 {sess} done ({time.time() - t0:.0f} s)")
    # real test inputs (and the stored d = 0 / zero inputs) under both lo
    lpt = load_lps("test", "real")
    for s, lps in (("real", lpt), ("ts0", load_lps("test", "timeshuf")), ("zero", load_lps("test", "zero"))):
        for i, lp in enumerate(lps):
            if not K.has(s, 0, i):
                lp = np.asarray(lp, np.float64)
                p_new, p_old = bool(gate_new.passes(lp)), bool(E.c5.passes(lp))
                txt = len(E.rg.text(lp, use_gate=False)) > 0 if (p_new or p_old) else False
                K.put((s, 0, i), {"score": float(E.c5.score(lp)), "pass_new": p_new, "pass_old": p_old,
                                  "emit_new": p_new and txt, "emit_old": p_old and txt})
    log(f"p58: test done ({time.time() - t0:.0f} s)")
    K.fh.close()


# --- score ---------------------------------------------------------------------------------------------

def stage_score(E: Env) -> None:
    from fidetype.trust.dropin import ControlResult, offer_control

    res: dict = {"config_id": {k: g.config_id for k, g in E.g.items()},
                 "coherence_threshold": {k: E.coh[k].threshold for k in E.g}}
    sel = json.loads((OUT / "p57-selection.json").read_text(encoding="utf-8"))
    K = Jsonl(OWN / "p57.jsonl")
    R5 = p1455_rows()
    n_test = 80
    P = {}
    for k in E.g:
        c = sel[k]["chosen"]
        real = [K.rows[(k, "real", 0, i)] for i in range(n_test)]
        rev = [K.rows[(k, "rev_out", 0, i)] for i in range(n_test)]
        real_off0 = sum(r["action"] == "offer" for r in real)
        real_off1 = sum(after(r, c) == "offer" for r in real)
        rev_off0 = sum(r["action"] == "offer" for r in rev)
        rev_off1 = sum(after(r, c) == "offer" for r in rev)
        equiv = sum(after(r, c) == r["both_action"] for r in real + rev)
        row = {"chosen": c, "information_only": sel[k]["information_only"],
               "real": {"n": n_test, "offer_coherence_only": real_off0, "offer_both": real_off1,
                        "removed_by_direction": real_off0 - real_off1,
                        "direction_value": pct(cand_value(r, c) for r in real)},
               "rev_out": {"n": n_test, "offer_coherence_only": rev_off0, "offer_both": rev_off1},
               "equivalence_check": f"{equiv} / {2 * n_test}",
               "p55_coherence_equal_real_rev": sum(abs(a["coh"] - b["coh"]) <= 1e-9 for a, b in zip(real, rev))}
        row["D1"] = {"pass": rev_off1 <= 4, "value": f"{rev_off1} / {n_test}"}
        row["D2"] = {"pass": real_off0 - real_off1 <= 4, "value": f"{real_off0 - real_off1} / {n_test}"}
        # D3: P14-55 sets
        d3 = {}
        p55_n = {"ts": 800, "fs": 800, "uni": 800, "rev_in": 80, "do_nothing": 27, "lines": 80}
        ok3 = True
        repeat_ok = True
        for s, n in p55_n.items():
            before = sum(1 for (ss, d, i), r in R5.items() if ss == s and "guards" in r
                         and r["guards"][k]["action"] == "offer")
            recs = [r for kk, r in K.rows.items() if kk[0] == k and kk[1] == "p55_" + s]
            rep = sum(r["action"] == r["p55_action"] and abs(r["coh"] - r["p55_coh"]) <= 1e-6 for r in recs)
            repeat_ok &= rep == len(recs) == before
            now = sum(after(r, c) == "offer" for r in recs)
            oc = offer_control(n_test, real_off1, [ControlResult(s, s, n, 0, int(math.floor(0.05 * n + 1e-9)), now)],
                               rate=0.05)
            if s in ("ts", "fs", "uni"):
                lim_ok = cp_upper(now, n) <= 0.05
            else:
                lim_ok = now <= int(math.floor(0.05 * n + 1e-9))
            passed = bool(lim_ok and oc["passed"] and now <= before)
            ok3 &= passed
            d3[s] = {"n": n, "offer_p14_55": before, "made_again": len(recs), "repeat_equal": rep,
                     "offer_both": now, "cp95_upper": cp_upper(now, n), "offer_control_pass": bool(oc["passed"]),
                     "pass": passed}
        row["D3"] = {"pass": bool(ok3 and repeat_ok), "repeat_ok": bool(repeat_ok), "sets": d3}
        # D4: P14-54 test sets + V re-check
        d4 = {}
        ok4 = True
        for kind in ("timeshuf", "zero", "frameshuf", "uniform"):
            recs = [K.rows[(k, "p54_" + kind, 0, i)] for i in range(n_test)]
            e0 = sum(r["action"] in ("offer", "commit") for r in recs)
            e1 = sum(after(r, c) in ("offer", "commit") for r in recs)
            d4[kind] = {"emit_coherence_only": e0, "emit_both": e1, "n": n_test}
            ok4 &= e1 <= 4
        rc = json.loads((OUT / f"p57-recheck-{k}.json").read_text(encoding="utf-8"))
        d4["V_recheck"] = {"passed": bool(rc["passed"]), "real": rc["real"],
                           "controls": [(x["name"], x["n_offer"], x["n"]) for x in rc["controls"]],
                           "commits_match_sheet": bool(rc["commits_match_sheet"])}
        ok4 &= bool(rc["passed"]) and rc["real"]["n_offer"] >= 36 and bool(rc["commits_match_sheet"])
        row["D4"] = {"pass": bool(ok4), "sets": d4}
        P[k] = row
    res["p57"] = P
    K.fh.close()
    # P14-58
    rule = json.loads((OUT / "p58-rule.json").read_text(encoding="utf-8"))
    K8 = Jsonl(OWN / "p58.jsonl")
    M = np.array([[K8.rows[("ts", d, i)]["emit_new"] for d in NEW_DRAWS] for i in range(n_test)], float)
    Mo = np.array([[K8.rows[("ts", d, i)]["emit_old"] for d in NEW_DRAWS] for i in range(n_test)], float)
    rng = np.random.default_rng(BOOT_SEED)
    boot = [M[rng.integers(0, n_test, n_test)].mean() for _ in range(N_BOOT)]
    k_new, k_old = int(M.sum()), int(Mo.sum())
    real = [K8.rows[("real", 0, i)] for i in range(n_test)]
    lo_new = rule["lo_new"]
    gd = E.c5.to_dict()

    def known(s, ds):
        rr = [R5[(s, d, i)] for d in ds for i in range(n_test)]
        return {"n": len(rr), "pass_new": sum(pass_f(gd, r["pf"], lo_new) for r in rr),
                "pass_old": sum(bool(r["c5_pass"]) for r in rr), "emit_old": sum(bool(r["c5_emit"]) for r in rr)}

    res["p58"] = {
        "lo_new": lo_new, "parts": rule["parts"], "shipped_lo": rule["shipped_lo"],
        "val": {"real_gated_new": rule["real_val_gated_new"], "n_real": rule["n_real"],
                "null_pass_score_only": rule["null_val_pass_new_score_only"], "n_null": rule["n_null"],
                "score_copy_check_maxabs": rule["score_copy_check_maxabs"]},
        "stability": rule["stability"],
        "test_new_draws": {"n": M.size, "emit_new": k_new, "cp95_new": cp_upper(k_new, M.size),
                           "per_draw_new": [int(v) for v in M.sum(0)], "cluster_boot95_new": float(np.percentile(boot, 95)),
                           "pass_new": sum(K8.rows[("ts", d, i)]["pass_new"] for d in NEW_DRAWS for i in range(n_test)),
                           "emit_shipped": k_old, "cp95_shipped": cp_upper(k_old, M.size),
                           "per_draw_shipped": [int(v) for v in Mo.sum(0)],
                           "sentences_ever_emit_new": int((M.sum(1) > 0).sum())},
        "test_real": {"n": n_test, "gated_new": sum(not r["pass_new"] for r in real),
                      "gated_shipped": sum(not r["pass_old"] for r in real),
                      "emit_new": sum(r["emit_new"] for r in real), "emit_shipped": sum(r["emit_old"] for r in real)},
        "test_known_draws": {"ts_d1_10": known("ts", OLD_DRAWS), "uni_d1_10": known("uni", OLD_DRAWS),
                             "ts_d0": {"pass_new": sum(K8.rows[("ts0", 0, i)]["pass_new"] for i in range(n_test)),
                                       "emit_new": sum(K8.rows[("ts0", 0, i)]["emit_new"] for i in range(n_test))},
                             "zero": {"pass_new": sum(K8.rows[("zero", 0, i)]["pass_new"] for i in range(n_test))},
                             "rev_in": known("rev_in", (0,)), "lines": known("lines", (0,))}}
    res["p58"]["E1"] = {"pass": res["p58"]["test_new_draws"]["cp95_new"] <= 0.04,
                        "value": res["p58"]["test_new_draws"]["cp95_new"]}
    res["p58"]["E2"] = {"pass": res["p58"]["test_real"]["gated_new"] <= 4,
                        "value": f"{res['p58']['test_real']['gated_new']} / {n_test}"}
    K8.fh.close()
    save_json(res, OUT / "results.json")
    log("score: " + json.dumps({"p57": {k: {r: v[r]["pass"] for r in ("D1", "D2", "D3", "D4")} for k, v in P.items()},
                                "p58": {"E1": res["p58"]["E1"], "E2": res["p58"]["E2"]}}))


def main(argv: list[str]) -> int:
    stages = argv[1:] or ["all"]
    assert all(s in ("select", "p57", "p58", "score", "all") for s in stages), stages
    if "all" in stages:
        stages = ["select", "p57", "p58", "score"]
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            E = Env()
            log(f"start {stages}; coherence thresholds { {k: g.threshold for k, g in E.coh.items()} }; C5 lo {E.c5.lo}")
            for s in stages:
                {"select": stage_select, "p57": stage_p57, "p58": stage_p58, "score": stage_score}[s](E)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stages} ({time.time() - t0:.0f} s); peak {mem_mb()[1]:.0f} MB")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
