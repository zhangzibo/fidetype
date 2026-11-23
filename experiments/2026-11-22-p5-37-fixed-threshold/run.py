r"""P5-37 (gap 189, option A): fixed threshold 0 for the offer-gate feature ``lm_beam_direction`` on the 781
willett-hw pool sentences (the decoder's training pool). Plan: plan.md.

Our own code (Apache-2.0). CPU only. Library code is used read only. Stages:
  check   C0: the decoder path of this script gives the stored P14-41 val log-probs again (5 val sentences of the
          first session; no new data).
  pool    per session: read the session, keep the 781 pool sentences, make the log-probs of real, time-shuffled,
          zero and rev_in input; then, per guard, the decisions (coherence only; then with both gates) of real,
          rev_out, the four nulls and frame-shuffled / near-uniform frames; the feature D.
  score   results/results.json (counts and summary values only).
  all     check, pool, score, then the DONE file.
  smoke   the whole pipeline on 2 val sentences of one session, output to a scratch folder (argument 2). Only
          for the code test before the pre-registration; it touches no pool sentence.

Run (repo root), or detached by launch.py::

    C:\venvs\fidetype-rocm\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 1 -- ^
        C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-22-p5-37-fixed-threshold/run.py all

Per-item records (actions, coherence, feature values, times; no text) stay in C:\Users\zhang\bci-data\derived\p5-37.
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
P536B = HERE.parent / "2026-11-22-p5-36b-two-direction-lm" / "results" / "fit.json"  # read only (descriptive)
OWN = DATA / "derived/p5-37"
OUT = HERE / "results"
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-f498c0637536daec"}
COH = {"builtin": 0.004183090472992479, "lm": 0.003485725778021531}
LM_NAME = "eng_tatoeba_6gram_mkn_noE2Q_noWillett"
FEAT = "lm_beam_direction"
TAU = 0.0
N_POOL = 781
LIMIT = 39  # floor(0.05 * 781)
RSS_LIMIT_MB = 2500.0
NEURAL_NULLS = ("timeshuf", "zero", "rev_in")
FRAME_NULLS = ("frameshuf", "uniform")
NULLS = NEURAL_NULLS + FRAME_NULLS


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
            last = time.time()
            log("heartbeat")


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                   encoding="utf-8")
    tmp.replace(p)


def rng_for(key: str, kind: str) -> np.random.Generator:
    h = hashlib.sha256(f"p5-37|{key}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def pct(v) -> list[float]:
    v = np.asarray([x for x in v if math.isfinite(x)], float)
    return [round(float(np.percentile(v, q)), 6) for q in (0, 5, 50, 95, 100)] if len(v) else []


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    from scipy.stats import beta

    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


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
        from fidetype.trust.offer_gate import OfferGate

        self.m = ftp.load("willett-hw")
        self.ro = self.m.lm_readout()  # the packaged LM readout; the feature uses it without its gate
        s = self.ro.settings
        assert (s["beam"], s["lm_weight"], s["bonus"], s["prune_logp"]) == (8, 0.5, 1.0, -8.0), s
        self.g = {"builtin": self.m.guard(), "lm": self.m.guard(readout="lm")}
        for k, g in self.g.items():
            assert g.config_id == CFG[k], (k, g.config_id)
            assert len(g.offer_gates) == 1 and g.offer_gates[0].feature == "coherence", k
            assert abs(g.offer_gates[0].threshold - COH[k]) <= 1e-12, (k, g.offer_gates[0].threshold)
        self.coh = {k: g.offer_gates[0] for k, g in self.g.items()}
        self.dir = OfferGate(FEAT, TAU, lm_name=LM_NAME, readout=self.ro, note="P5-37 fixed threshold 0")
        self.sessions = list(self.m.manifest.architecture["sessions"])


def act(r) -> str:
    return str(getattr(r.action, "value", r.action)).lower()


def decide(E: Env, k: str, x, feature: str) -> dict:
    """Coherence-only decision of guard k; the feature D on the guard's frames ("always" or "offer" = only if
    the coherence-only action is OFFER); then the decision with both gates (coherence, then D >= 0).

    With ``feature="offer"`` (null inputs) the both-gate decision runs only for a coherence-only OFFER: an offer
    gate can change OFFER to WITHHOLD only, so any other action stays (``both_inferred``; the C2 check tests this
    on the real and rev_out inputs, where the both-gate decision always runs)."""
    from fidetype.trust import offer_gate as og

    g = E.g[k]
    g.set_offer_gate([E.coh[k]])
    g.collect_offer_features = True
    t0 = time.perf_counter()
    r = g._decide_quiet(np.asarray(x))
    rec = {"action": act(r), "coh": float(g.last_offer_features["coherence"]), "t_decide": time.perf_counter() - t0}
    g.collect_offer_features = False
    if feature == "always" or rec["action"] == "offer":
        t0 = time.perf_counter()
        v, d = og.lm_beam_direction(g._last_lp, E.ro, details=True)
        rec.update(D=v, t_beam2=time.perf_counter() - t0, **d)
    if feature == "always" or rec["action"] == "offer":
        g.set_offer_gate([E.coh[k], E.dir])
        rec["both_action"] = act(g._decide_quiet(np.asarray(x)))
        g.set_offer_gate([E.coh[k]])
    else:
        rec["both_action"], rec["both_inferred"] = rec["action"], True
    return rec


def frame_null(lp: np.ndarray, key: str, kind: str) -> np.ndarray:
    if kind == "frameshuf":
        return np.ascontiguousarray(lp[rng_for(key, "frameshuf").permutation(len(lp))])
    T, V = lp.shape
    z = np.full((T, V), -math.log(V)) + 0.05 * rng_for(key, "uniform").standard_normal((T, V))
    return (z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32)


def split_blocks() -> tuple[dict, dict]:
    mt = json.loads((P1441 / "items.json").read_text(encoding="utf-8"))
    return ({int(s): int(b) for s, b in mt["test_blocks"].items()}, {int(s): int(b) for s, b in mt["val_blocks"].items()})


def run_items(E: Env, K: Jsonl, sess: str, items, tag: str, greedy: Jsonl | None, kinds: tuple) -> None:
    from fidetype.eval.metrics import edit_distance

    for it in items:
        key = f"{sess}|{it.extra['trial']}"
        need = [(k, s) for k in E.g for s in kinds if not K.has(k, s, key)]
        if not need and (greedy is None or greedy.has(key)):
            continue
        x = np.asarray(it.x)
        t0 = time.perf_counter()
        lp = E.m.log_probs(x, sess).astype(np.float32)
        t_lp = time.perf_counter() - t0
        if greedy is not None and not greedy.has(key):
            h = E.m.text(E.m._stream(lp, it.key))
            greedy.put((key,), {"ed": int(edit_distance(it.truth, h)), "n_ref": len(it.truth), "T": int(len(lp)),
                                "t_lp": t_lp})
        inputs = {"real": lambda: lp, "rev_out": lambda: np.ascontiguousarray(lp[::-1]),
                  "timeshuf": lambda: E.m.log_probs(x[rng_for(key, "timeshuf").permutation(len(x))], sess),
                  "zero": lambda: E.m.log_probs(np.zeros_like(x), sess),
                  "rev_in": lambda: E.m.log_probs(np.ascontiguousarray(x[::-1]), sess),
                  "frameshuf": lambda: frame_null(lp, key, "frameshuf"),
                  "uniform": lambda: frame_null(lp, key, "uniform")}
        for s in kinds:
            todo = [k for k in E.g if not K.has(k, s, key)]
            if not todo:
                continue
            xi = np.asarray(inputs[s](), np.float32)
            for k in todo:
                K.put((k, s, key), {**decide(E, k, xi, "always" if s in ("real", "rev_out") else "offer"),
                                    "tag": tag})
            del xi
        del lp, x
        gc.collect()


# --- stages --------------------------------------------------------------------------------------------

def stage_check(E: Env) -> None:
    """C0: this script's decoder path gives the stored P14-41 val log-probs again (first session, 5 sentences)."""
    from fidetype.pretrained import readers as R

    mt = json.loads((P1441 / "items.json").read_text(encoding="utf-8"))
    first = [(i, it) for i, it in enumerate(mt["val"]) if it["session"] == E.sessions[0]][:5]
    items = {it.key: it for it in R.read_willett_session(RAW / E.sessions[0])}
    diffs = []
    with np.load(P1441 / "lp_val_real.npz") as z:
        for i, rec in first:
            lp = E.m.log_probs(np.asarray(items[rec["key"]].x), E.sessions[0])
            diffs.append(float(np.max(np.abs(lp - z[f"arr_{i}"]))))
    save_json({"n": len(diffs), "max_abs_diff": max(diffs), "pass": max(diffs) <= 1e-4}, OWN / "check.json")
    log(f"check C0: max abs diff {max(diffs):.2e} over {len(diffs)} val sentences")
    assert max(diffs) <= 1e-4, diffs


def stage_pool(E: Env) -> None:
    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB

    tb, vb = split_blocks()
    vocab = set(VOCAB[1:])
    K = Jsonl(OWN / "pool.jsonl")
    G = Jsonl(OWN / "greedy.jsonl")
    t0 = time.time()
    # pass 1: the primary inputs (real, rev_out) of all sessions; pass 2: the null inputs
    for name, kinds, g in (("primary", ("real", "rev_out"), G), ("nulls", NULLS, None)):
        n_pool = 0
        for si, sess in enumerate(E.sessions):
            items = [it for it in R.read_willett_session(RAW / sess)
                     if it.truth and all(c in vocab for c in it.truth) and it.extra["block"] not in (tb[si], vb[si])]
            n_pool += len(items)
            run_items(E, K, sess, items, "pool", g, kinds)
            del items
            gc.collect()
            log(f"pool {name}: {sess} done ({n_pool} sentences so far, {time.time() - t0:.0f} s)")
        assert n_pool == N_POOL, n_pool
    K.fh.close()
    G.fh.close()


def stage_score(E: Env | None) -> None:
    from fidetype.trust.dropin import ControlResult, offer_control

    P = Jsonl(OWN / "pool.jsonl").rows
    G = Jsonl(OWN / "greedy.jsonl").rows
    keys = sorted({kk[2] for kk in P})
    assert len(keys) == N_POOL, len(keys)
    fit36b = json.loads(P536B.read_text(encoding="utf-8"))
    out: dict = {"objects": {"config_id": CFG, "coherence": COH, "lm": LM_NAME, "feature": FEAT, "tau": TAU,
                             "n": N_POOL, "limit": LIMIT},
                 "check_C0": json.loads((OWN / "check.json").read_text(encoding="utf-8"))}
    ed = sum(r["ed"] for r in G.values())
    nr = sum(r["n_ref"] for r in G.values())
    out["greedy_cer_pool"] = {"cer": round(ed / nr, 4), "edits": ed, "chars": nr, "n": len(G),
                              "reference_p14_33": {"val": 0.2603, "test": 0.3051}}
    for k in CFG:
        real = [P[(k, "real", q)] for q in keys]
        rev = [P[(k, "rev_out", q)] for q in keys]
        r0 = sum(r["action"] == "offer" for r in real)
        r1 = sum(r["both_action"] == "offer" for r in real)
        removed = sum(r["action"] == "offer" and r["both_action"] != "offer" for r in real)
        v0 = sum(r["action"] == "offer" for r in rev)
        v1 = sum(r["both_action"] == "offer" for r in rev)
        res = {
            "P1": {"rev_out_offers": v1, "coherence_only": v0, "n": N_POOL, "limit": LIMIT, "pass": v1 <= LIMIT},
            "P2": {"real_offers_removed": removed, "real_offers_coherence": r0, "real_offers_both": r1,
                   "n": N_POOL, "limit": LIMIT, "pass": removed <= LIMIT},
            "commits": {"real": sum(r["action"] == "commit" for r in real),
                        "rev_out": sum(r["action"] == "commit" for r in rev)},
        }
        res["S0_rev_out_emits"] = {"emits_both": sum(r["both_action"] in ("offer", "commit") for r in rev),
                                   "limit": LIMIT}
        res["S0_rev_out_emits"]["pass"] = res["S0_rev_out_emits"]["emits_both"] <= LIMIT
        # checks
        res["C1_antisym_1e-9"] = {"equal": sum(abs(a["D"] + b["D"]) <= 1e-9 for a, b in zip(real, rev)), "n": N_POOL}
        res["C1_coherence_equal_1e-9"] = sum(abs(a["coh"] - b["coh"]) <= 1e-9 for a, b in zip(real, rev))
        after = lambda r: "withhold" if r["action"] == "offer" and r["D"] < TAU else r["action"]  # noqa: E731
        res["C2_equivalence"] = {"equal": sum(after(r) == r["both_action"] for r in real + rev), "n": 2 * N_POOL}
        res["valid"] = bool(res["C1_antisym_1e-9"]["equal"] == N_POOL and res["C1_coherence_equal_1e-9"] == N_POOL
                            and res["C2_equivalence"]["equal"] == 2 * N_POOL and out["check_C0"]["pass"])
        res["pass"] = bool(res["P1"]["pass"] and res["P2"]["pass"] and res["valid"])
        # S1: nulls
        s1, ok1 = {}, True
        for s in NULLS:
            recs = [P[(k, s, q)] for q in keys]
            e0 = sum(r["action"] in ("offer", "commit") for r in recs)
            e1 = sum(r["both_action"] in ("offer", "commit") for r in recs)
            o1 = sum(r["both_action"] == "offer" for r in recs)
            oc = offer_control(N_POOL, r1, [ControlResult(s, s, N_POOL, 0, LIMIT, o1)], rate=0.05)
            passed = bool(e1 <= LIMIT and e1 <= e0 and oc["passed"])
            ok1 &= passed
            s1[s] = {"emit_coherence_only": e0, "emit_both": e1, "offer_both": o1,
                     "commit": sum(r["action"] == "commit" for r in recs), "cp95_upper": round(cp_upper(e1, N_POOL), 4),
                     "offer_control_pass": bool(oc["passed"]), "pass": passed}
        res["S1_nulls"] = {"pass": bool(ok1), "sets": s1}
        # descriptive
        offD = [r["D"] for r in real if r["action"] == "offer"]
        res["D_real_offers"] = pct(offD)
        res["real_offers_D_below_0"] = sum(d < 0 for d in offD)
        res["real_offers_D_equal_0"] = sum(d == 0 for d in offD)
        t36 = fit36b[k]["threshold"]
        res["descriptive_p5_36b_tau"] = {
            "tau": t36, "note": "P5-36b val-S fit; for the LM guard it was fitted with the earlier LM guard "
                                "(tcfg-26ae951a20a0cddd)",
            "real_offers_removed": sum(d < t36 for d in offD),
            "rev_out_offers": sum(r["action"] == "offer" and r["D"] >= t36 for r in rev)}
        tb = [r["t_beam2"] for r in real]
        td = [r["t_decide"] for r in real]
        res["cost_s"] = {"t_beam2_real": pct(tb), "t_decide_real": pct(td),
                         "median_ratio_beam2_to_decide": round(float(np.median(np.array(tb) / np.array(td))), 3)}
        out[k] = res
    out["pass_both_guards"] = bool(out["builtin"]["pass"] and out["lm"]["pass"])
    save_json(out, OUT / "results.json")
    log("score: " + json.dumps({k: {"P1": out[k]["P1"]["pass"], "P2": out[k]["P2"]["pass"], "valid": out[k]["valid"],
                                    "pass": out[k]["pass"], "S1": out[k]["S1_nulls"]["pass"]} for k in CFG}))


def stage_smoke(E: Env, scratch: Path) -> None:
    """Code test before the pre-registration: 2 val sentences of the first session (already-used data)."""
    from fidetype.pretrained import readers as R

    _, vb = split_blocks()
    items = [it for it in R.read_willett_session(RAW / E.sessions[0]) if it.extra["block"] == vb[0]][:2]
    K = Jsonl(scratch / "smoke.jsonl")
    G = Jsonl(scratch / "smoke-greedy.jsonl")
    run_items(E, K, E.sessions[0], items, "smoke", G, ("real", "rev_out"))
    run_items(E, K, E.sessions[0], items, "smoke", None, NULLS)
    for kk, r in K.rows.items():
        assert r["both_action"] in ("offer", "withhold", "commit", "abstain"), r
    log(f"smoke: {len(K.rows)} decisions, {len(G.rows)} greedy rows; keys ok")


def main(argv: list[str]) -> int:
    global OWN
    stages = argv[1:] or ["all"]
    if stages[0] == "smoke":
        OWN = Path(stages[1])
        OWN.mkdir(parents=True, exist_ok=True)
        stage_smoke(Env(), OWN)
        return 0
    assert all(s in ("check", "pool", "score", "all") for s in stages), stages
    if "all" in stages:
        stages = ["check", "pool", "score"]
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            E = Env()
            log(f"start {stages}; config {CFG}; coherence {COH}; tau {TAU}; readout settings {E.ro.settings}")
            for s in stages:
                {"check": stage_check, "pool": stage_pool, "score": stage_score}[s](E)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stages} ({time.time() - t0:.0f} s); peak {mem_mb()[1]:.0f} MB")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
