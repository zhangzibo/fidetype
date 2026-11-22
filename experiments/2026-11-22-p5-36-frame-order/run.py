r"""P5-36 (gap 181): frame-order integrity check and the lm_direction offer gate on willett-hw. Plan: plan.md.

Our own code (Apache-2.0). CPU only. Stages:
  val      L0 on the 66 S val inputs (real and rev_out), both guards.
  test     80 test inputs: real, rev_out (P14-57 form), the transport forms (rows and times moved together:
           reversed, reordered, duplicated), real with exact and jittered times; the 40 LTT val inputs.
  score    results/results.json (counts and summary values only).
  all      every stage, then the DONE file.

Run (repo root)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-22-p5-36-frame-order/run.py all

Per-item records (actions, codes, feature values; no text) stay in C:\Users\zhang\bci-data\derived\p5-36.
"""

from __future__ import annotations

import ctypes
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
P1441 = DATA / "derived/p14-41"  # read only
OWN = DATA / "derived/p5-36"
OUT = HERE / "results"
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-26ae951a20a0cddd"}
LM_NAME = "eng_tatoeba_6gram_mkn_noE2Q_noWillett"
JITTER = 0.4  # of a frame period
RSS_LIMIT_MB = 5000.0


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
    while True:
        time.sleep(2.0)
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)
        if mem_mb()[0] > RSS_LIMIT_MB:
            log(f"working set above {RSS_LIMIT_MB:.0f} MB: exit 3")
            os._exit(3)


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                   encoding="utf-8")
    tmp.replace(p)


def rng_for(i: int, split: str, kind: str) -> np.random.Generator:
    h = hashlib.sha256(f"p5-36|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(P1441 / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def positions() -> tuple[list[int], list[int]]:
    """(S, LTT): the 66 non-LTT val positions and the 40 LTT val positions (the calibrate split)."""
    from fidetype.trust.dropin import _split

    n_fit, n_pol, _ = _split(106)
    perm = [int(i) for i in np.random.default_rng(0).permutation(106)]
    return perm[: n_fit + n_pol], perm[n_fit + n_pol:]


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
        from fidetype.trust.offer_gate import OfferGate

        self.m = ftp.load("willett-hw")
        self.lm = self.m.lm_readout().lm  # the packaged Willett-blocked Tatoeba 6-gram
        self.g = {"builtin": self.m.guard(), "lm": self.m.guard(readout="lm")}
        for k, g in self.g.items():
            assert g.config_id == CFG[k], (k, g.config_id)
            assert len(g.offer_gates) == 1 and g.offer_gates[0].feature == "coherence", k
            g.offer_lm = self.lm
            g.collect_offer_features = True
        self.coh = {k: g.offer_gates[0] for k, g in self.g.items()}
        self.dirg = OfferGate("lm_direction", 0.0, lm_name=LM_NAME, lm=self.lm, note="P5-36 fixed threshold 0")
        self.period = {k: float(g._codec.frame_period) for k, g in self.g.items()}

    def gates(self, k: str, both: bool) -> None:
        self.g[k].set_offer_gate([self.coh[k], self.dirg] if both else [self.coh[k]])


def decide(g, lp, times=None) -> dict:
    """One decision (public ``decide``; the audit log is cleared): action, flags, features."""
    from fidetype.trust.integrity import REASON_PREFIX

    r = g.decide(np.asarray(lp), frame_times=times)
    g.audit_log.clear()
    f = g.last_offer_features or {}
    rep = g.last_integrity
    return {"action": r.action, "integrity_flag": r.reason.startswith(REASON_PREFIX),
            "integrity_code": None if rep is None else rep.code, "coh": float(f.get("coherence", math.nan)),
            "lm_dir": float(f.get("lm_direction", math.nan)), "reason_head": r.reason[:60]}


def times_of(T: int, p: float) -> np.ndarray:
    return p + p * np.arange(T)  # the times that fidetype.adapters.ctc_logits.from_array gives


# --- stages --------------------------------------------------------------------------------------------

def stage_val(E: Env) -> None:
    K = Jsonl(OWN / "val.jsonl")
    lpv = load_lps("val", "real")
    S, LTT = positions()
    t0 = time.time()
    for k in E.g:
        E.gates(k, both=False)
        for i in S:
            for s, x in (("real", lpv[i]), ("rev_out", np.ascontiguousarray(lpv[i][::-1]))):
                if not K.has(k, s, i):
                    K.put((k, s, i), decide(E.g[k], x))
        E.gates(k, both=True)
        for i in LTT:
            if not K.has(k, "ltt_both", i):
                K.put((k, "ltt_both", i), decide(E.g[k], lpv[i]))
        E.gates(k, both=False)
        log(f"val: {k} done ({time.time() - t0:.0f} s)")
    K.fh.close()


def forms(lp: np.ndarray, p: float, i: int) -> dict:
    """The test forms of one input: (rows, times) for each name (times None: the guard makes them)."""
    T = lp.shape[0]
    t = times_of(T, p)
    rev = np.ascontiguousarray(lp[::-1])
    k = int(rng_for(i, "test", "reorder").integers(0, T - 1))
    order = np.arange(T)
    order[k], order[k + 1] = k + 1, k
    j = int(rng_for(i, "test", "dup").integers(0, T))
    dup_idx = np.insert(np.arange(T), j + 1, j)
    jit = t + rng_for(i, "test", "jitter").uniform(-JITTER, JITTER, T) * p
    return {
        "real_times": (lp, t),
        "real_jitter": (lp, jit),
        "rev_out_times": (rev, t),            # P14-57 rev_out: rows reversed, new increasing times
        "rev_events": (rev, t[::-1].copy()),  # rows and their times reversed together
        "reordered": (np.ascontiguousarray(lp[order]), t[order]),
        "duplicated": (np.ascontiguousarray(lp[dup_idx]), t[dup_idx]),
    }


def stage_test(E: Env) -> None:
    K = Jsonl(OWN / "test.jsonl")
    lpt = load_lps("test", "real")
    t0 = time.time()
    for k in E.g:
        for i, lp in enumerate(lpt):
            if all(K.has(k, s, i) for s in ("real", "rev_out", "real_both", "rev_out_both", "real_times",
                                             "real_jitter", "rev_out_times", "rev_events", "reordered",
                                             "duplicated")):
                continue
            rev = np.ascontiguousarray(lp[::-1])
            E.gates(k, both=False)
            for s, x in (("real", lp), ("rev_out", rev)):
                if not K.has(k, s, i):
                    K.put((k, s, i), decide(E.g[k], x))
            E.gates(k, both=True)
            for s, x in (("real_both", lp), ("rev_out_both", rev)):
                if not K.has(k, s, i):
                    K.put((k, s, i), decide(E.g[k], x))
            for s, (x, t) in forms(lp, E.period[k], i).items():
                if not K.has(k, s, i):
                    K.put((k, s, i), decide(E.g[k], x, t))
            E.gates(k, both=False)
        log(f"test: {k} done ({time.time() - t0:.0f} s)")
    K.fh.close()


def stage_score(E: Env | None) -> None:
    V = Jsonl(OWN / "val.jsonl").rows
    T = Jsonl(OWN / "test.jsonl").rows
    S, LTT = positions()
    n_test = 80
    out: dict = {"objects": {"config_id": CFG, "lm": LM_NAME, "threshold": 0.0, "jitter_of_period": JITTER}}
    for k in CFG:
        # L0 (val S)
        real = [V[(k, "real", i)] for i in S]
        rev = [V[(k, "rev_out", i)] for i in S]
        off = [r for r in real if r["action"] == "offer"]
        m = len(off)
        loss = sum(r["lm_dir"] < 0.0 for r in off)
        limit = int(math.floor(0.05 * m + 1e-9))
        val = {"n": len(real), "m_real_offers": m, "loss": loss, "limit": limit, "L0_pass": loss <= limit,
               "rev_out_offers_coherence": sum(r["action"] == "offer" for r in rev),
               "rev_out_offers_with_lm_direction": sum(r["action"] == "offer" and r["lm_dir"] >= 0 for r in rev),
               "lm_dir_real_offers": pct(r["lm_dir"] for r in off),
               "antisym_1e-9": sum(abs(a["lm_dir"] + b["lm_dir"]) <= 1e-9 for a, b in zip(real, rev)),
               "coherence_equal_1e-9": sum(abs(a["coh"] - b["coh"]) <= 1e-9 for a, b in zip(real, rev))}
        ltt = [V[(k, "ltt_both", i)] for i in LTT]
        # test
        g = lambda s: [T[(k, s, i)] for i in range(n_test)]  # noqa: E731
        real_c, rev_c, real_b, rev_b = g("real"), g("rev_out"), g("real_both"), g("rev_out_both")
        real_off0 = sum(r["action"] == "offer" for r in real_c)
        real_off1 = sum(r["action"] == "offer" for r in real_b)
        removed = sum(a["action"] == "offer" and b["action"] != "offer" for a, b in zip(real_c, real_b))
        eq = 0
        for a, b in zip(real_c + rev_c, real_b + rev_b):
            want = "withhold" if a["action"] == "offer" and a["lm_dir"] < 0.0 else a["action"]
            eq += want == b["action"]
        flag = lambda s: sum(r["integrity_flag"] and r["action"] == "withhold" for r in g(s))  # noqa: E731
        codes = lambda s: sorted({str(r["integrity_code"]) for r in g(s)})  # noqa: E731
        same = sum(a["action"] == b["action"] and a["reason_head"] == b["reason_head"]
                   for a, b in zip(real_b, g("real_times")))
        res = {
            "val": val,
            "L0": {"pass": val["L0_pass"], "loss": loss, "limit": limit, "m": m},
            "L1": {"rev_out_offers": sum(r["action"] == "offer" for r in rev_b), "coherence_only": sum(
                r["action"] == "offer" for r in rev_c), "limit": 4},
            "L2": {"real_offers_removed": removed, "real_offers_coherence": real_off0, "real_offers_both": real_off1,
                   "limit": 4},
            "L3": {"ltt_real_offers": sum(r["action"] == "offer" for r in ltt), "n": len(ltt), "limit": 36},
            "I1": {s: {"flagged": flag(s), "n": n_test, "codes": codes(s)}
                   for s in ("rev_events", "reordered", "duplicated")},
            "I2": {s: {"flagged": flag(s), "n": n_test} for s in ("real_times", "real_jitter")},
            "I3": {"same_action_and_reason": same, "n": n_test},
            "R1_rev_out_p14_57_form": {"flagged": flag("rev_out_times"), "n": n_test,
                                       "offers": sum(r["action"] == "offer" for r in g("rev_out_times"))},
            "check_equivalence": {"equal": eq, "n": 2 * n_test},
            "check_antisym_test_1e-9": sum(abs(a["lm_dir"] + b["lm_dir"]) <= 1e-9 for a, b in zip(real_c, rev_c)),
            "lm_dir_real_test_offers": pct(r["lm_dir"] for r in real_c if r["action"] == "offer"),
        }
        res["L1"]["pass"] = res["L1"]["rev_out_offers"] <= 4
        res["L2"]["pass"] = removed <= 4
        res["L3"]["pass"] = res["L3"]["ltt_real_offers"] >= 36
        res["I1"]["pass"] = all(res["I1"][s]["flagged"] == n_test for s in ("rev_events", "reordered", "duplicated"))
        res["I2"]["pass"] = all(res["I2"][s]["flagged"] == 0 for s in ("real_times", "real_jitter"))
        res["I3"]["pass"] = same == n_test
        out[k] = res
    save_json(out, OUT / "results.json")
    log("score: " + json.dumps({k: {r: out[k][r].get("pass") for r in ("L0", "L1", "L2", "L3", "I1", "I2", "I3")}
                                for k in CFG}))


def main(argv: list[str]) -> int:
    stages = argv[1:] or ["all"]
    assert all(s in ("val", "test", "score", "all") for s in stages), stages
    if "all" in stages:
        stages = ["val", "test", "score"]
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            E = Env()
            log(f"start {stages}; coherence { {k: g.threshold for k, g in E.coh.items()} }; lm {LM_NAME}")
            for s in stages:
                {"val": stage_val, "test": stage_test, "score": stage_score}[s](E)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stages} ({time.time() - t0:.0f} s); peak {mem_mb()[1]:.0f} MB")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
