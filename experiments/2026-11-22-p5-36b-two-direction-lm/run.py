r"""P5-36b (gap 181): two-direction LM-beam direction score (offer-gate feature ``lm_beam_direction``) on
willett-hw against ``rev_out``. Plan: plan.md.

Our own code (Apache-2.0). CPU only. Stages:
  val      the 66 S val inputs (real and rev_out), both guards: coherence-only decisions, the feature; then
           the threshold fit (results/fit.json).
  test     the 80 test inputs (real, rev_out): coherence-only decisions, the feature, and the decisions with both
           gates (equivalence check); the 40 LTT val inputs with both gates.
  nulls    the P14-54 test null inputs and the P14-55 null inputs that were offers (made again from their
           recipes), with the feature.
  score    results/results.json (counts and summary values only).
  all      every stage, then the DONE file.

Run (repo root), or detached by launch.py::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 1 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-22-p5-36b-two-direction-lm/run.py all

Per-item records (actions, scores, feature values, times; no text) stay in C:\Users\zhang\bci-data\derived\p5-36b.
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
P1457 = DATA / "derived/p14-57"  # read only
OWN = DATA / "derived/p5-36b"
OUT = HERE / "results"
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-26ae951a20a0cddd"}
LM_NAME = "eng_tatoeba_6gram_mkn_noE2Q_noWillett"
FEAT = "lm_beam_direction"
KEEP = 0.95
RSS_LIMIT_MB = 3000.0
N_TEST = 80


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


def rng_for(tag: str, d: int, split: str, i: int, kind: str) -> np.random.Generator:
    h = hashlib.sha256(f"{tag}|{d}|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def load_lps(split: str, kind: str, only: set[int] | None = None) -> dict[int, np.ndarray]:
    with np.load(P1441 / f"lp_{split}_{kind}.npz") as z:
        n = len(z.files)
        return {i: np.asarray(z[f"arr_{i}"], np.float32) for i in range(n) if only is None or i in only}


def positions() -> tuple[list[int], list[int]]:
    """(S, LTT): the 66 non-LTT val positions and the 40 LTT val positions (the calibrate split)."""
    from fidetype.trust.dropin import _split

    n_fit, n_pol, _ = _split(106)
    perm = [int(i) for i in np.random.default_rng(0).permutation(106)]
    return perm[: n_fit + n_pol], perm[n_fit + n_pol:]


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


def read_jsonl(p: Path, keyf) -> dict:
    rows = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            rows[keyf(d)] = d
    return rows


# --- objects under test --------------------------------------------------------------------------------

class Env:
    def __init__(self) -> None:
        import fidetype.pretrained as ftp

        self.m = ftp.load("willett-hw")
        self.ro = self.m.lm_readout()  # the packaged LM readout; the feature uses it without its gate
        assert self.ro.settings["beam"] == 8 and self.ro.settings["lm_weight"] == 0.5, self.ro.settings
        self.g = {"builtin": self.m.guard(), "lm": self.m.guard(readout="lm")}
        for k, g in self.g.items():
            assert g.config_id == CFG[k], (k, g.config_id)
            assert len(g.offer_gates) == 1 and g.offer_gates[0].feature == "coherence", k
        self.coh = {k: g.offer_gates[0] for k, g in self.g.items()}
        self.sessions = list(self.m.manifest.architecture["sessions"])

    def dirgate(self, k: str, fit: dict):
        from fidetype.trust.offer_gate import OfferGate

        return OfferGate(FEAT, fit[k]["threshold"], lm_name=LM_NAME, readout=self.ro, note="P5-36b val-only fit")


def decide(E: Env, k: str, x, want_feature: bool = True) -> dict:
    """Coherence-only decision of guard k, then the feature on the guard's frames (timed)."""
    from fidetype.trust import offer_gate as og

    g = E.g[k]
    g.set_offer_gate([E.coh[k]])
    g.collect_offer_features = True
    t0 = time.perf_counter()
    r = g._decide_quiet(np.asarray(x))
    t_dec = time.perf_counter() - t0
    f = g.last_offer_features
    rec = {"action": str(getattr(r.action, "value", r.action)).lower(), "coh": float(f["coherence"]),
           "t_decide": t_dec}
    g.collect_offer_features = False
    if want_feature:
        t0 = time.perf_counter()
        v, d = og.lm_beam_direction(g._last_lp, E.ro, details=True)
        rec.update(D=v, t_beam2=time.perf_counter() - t0, D_per_frame=(
            (d["s_fwd"] - d["s_rev"]) / d["T"] if d["T"] and d["s_fwd"] != d["s_rev"] else 0.0), **d)
    return rec


def decide_both(E: Env, k: str, x, fit: dict) -> str:
    g = E.g[k]
    g.collect_offer_features = False
    g.set_offer_gate([E.coh[k], E.dirgate(k, fit)])
    a = g._decide_quiet(np.asarray(x)).action
    g.set_offer_gate([E.coh[k]])
    return str(getattr(a, "value", a)).lower()


# --- stages --------------------------------------------------------------------------------------------

def stage_val(E: Env) -> None:
    from fidetype.trust.offer_gate import OfferGate

    K = Jsonl(OWN / "val.jsonl")
    lpv = load_lps("val", "real")
    S, _ = positions()
    t0 = time.time()
    for k in E.g:
        for i in S:
            for s, x in (("real", lpv[i]), ("rev_out", np.ascontiguousarray(lpv[i][::-1]))):
                if not K.has(k, s, i):
                    K.put((k, s, i), decide(E, k, x))
        log(f"val: {k} done ({time.time() - t0:.0f} s)")
    fit = {}
    for k in E.g:
        off = [K.rows[(k, "real", i)] for i in S if K.rows[(k, "real", i)]["action"] == "offer"]
        m = len(off)
        gate = OfferGate.fit(FEAT, [r["D"] for r in off], keep=KEEP, lm_name=LM_NAME, readout=E.ro)
        tau = gate.threshold
        rev = [K.rows[(k, "rev_out", i)] for i in S]
        fit[k] = {"threshold": tau, "m_real_offers": m, "n": len(S), "index": int(math.floor((1 - KEEP) * m + 1e-9)),
                  "val_real_removed": sum(r["D"] < tau for r in off),
                  "val_rev_out_offers_coherence": sum(r["action"] == "offer" for r in rev),
                  "val_rev_out_offers_both": sum(r["action"] == "offer" and r["D"] >= tau for r in rev),
                  "D_real_offers": pct(r["D"] for r in off)}
    save_json(fit, OUT / "fit.json")
    log("val fit: " + json.dumps({k: (v["threshold"], v["val_real_removed"], v["val_rev_out_offers_both"])
                                  for k, v in fit.items()}))
    K.fh.close()


def stage_test(E: Env) -> None:
    fit = json.loads((OUT / "fit.json").read_text(encoding="utf-8"))
    K = Jsonl(OWN / "test.jsonl")
    lpt = load_lps("test", "real")
    t0 = time.time()
    for k in E.g:
        for i in range(N_TEST):
            lp = lpt[i]
            for s, x in (("real", lp), ("rev_out", np.ascontiguousarray(lp[::-1]))):
                if not K.has(k, s, i):
                    rec = decide(E, k, x)
                    t1 = time.perf_counter()
                    rec["both_action"] = decide_both(E, k, x, fit)
                    rec["t_both"] = time.perf_counter() - t1
                    K.put((k, s, i), rec)
        log(f"test: {k} done ({time.time() - t0:.0f} s)")
    del lpt
    gc.collect()
    lpv = load_lps("val", "real")
    _, LTT = positions()
    for k in E.g:
        for i in LTT:
            if not K.has(k, "ltt", i):
                rec = decide(E, k, lpv[i])
                rec["both_action"] = decide_both(E, k, lpv[i], fit)
                K.put((k, "ltt", i), rec)
        log(f"test: {k} LTT done ({time.time() - t0:.0f} s)")
    K.fh.close()


def stage_nulls(E: Env) -> None:
    """P14-54 test nulls and P14-55 nulls: only inputs that were coherence-gated offers can change."""
    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB

    K = Jsonl(OWN / "nulls.jsonl")
    t0 = time.time()
    # P14-54 test nulls: the P14-57 coherence-only records say which were offers
    p57 = read_jsonl(P1457 / "p57.jsonl", lambda d: tuple(d["key"]))
    need54 = sorted({(kk[1][4:], kk[3]) for kk, r in p57.items() if kk[1].startswith("p54_") and r["action"] == "offer"})
    count54 = {kind: {k: sum(1 for kk, r in p57.items() if kk[0] == k and kk[1] == "p54_" + kind
                             and r["action"] == "offer") for k in CFG} for kind in ("timeshuf", "zero", "frameshuf",
                                                                                  "uniform")}
    save_json({"p54_offers_p14_57": count54, "need": need54}, OWN / "p54-need.json")
    log(f"nulls: P14-54 offered inputs to make again: {need54}")
    real_need = {i for _, i in need54}
    lpr = load_lps("test", "real", real_need)
    stored = {kind: load_lps("test", kind, {i for kd, i in need54 if kd == kind}) for kind in ("timeshuf", "zero")}
    for kind, i in need54:
        if kind in stored:
            x = stored[kind][i]
        elif kind == "frameshuf":
            x = lpr[i][rng_for("p14-41", 0, "test", i, "frameshuf").permutation(len(lpr[i]))]
        else:
            T, V = lpr[i].shape
            z = np.full((T, V), -math.log(V)) + 0.05 * rng_for("p14-41", 0, "test", i, "uniform").standard_normal((T, V))
            x = z - np.log(np.exp(z).sum(1, keepdims=True))
        for k in E.g:
            if not K.has(k, "p54_" + kind, 0, i):
                rec = decide(E, k, x)
                rec["p57_action"] = p57[(k, "p54_" + kind, 0, i)]["action"]
                rec["p57_coh"] = p57[(k, "p54_" + kind, 0, i)]["coh"]
                K.put((k, "p54_" + kind, 0, i), rec)
    del stored
    gc.collect()
    log(f"nulls: P14-54 done ({time.time() - t0:.0f} s)")
    # P14-55 nulls: the inputs that were offers there (for either guard)
    rows = read_jsonl(P1455 / "items.jsonl", lambda d: (d["set"], d["d"], d["i"]))
    need = {key: r for key, r in rows.items() if "guards" in r and key[0] not in ("real", "rev_out")
            and any(v["action"] == "offer" for v in r["guards"].values())}
    log(f"nulls: P14-55 offered null inputs to make again: {len(need)} ({sorted(set(s for s, _, _ in need))})")
    assert all(s in ("ts", "rev_in", "fs", "uni") for s, _, _ in need), sorted(set(s for s, _, _ in need))
    mt = json.loads((P1441 / "items.json").read_text(encoding="utf-8"))
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
            for k in E.g:
                if not K.has(k, "p55_" + s, d, i):
                    rec = decide(E, k, lp)
                    rec["p55_action"] = rows[(s, d, i)]["guards"][k]["action"]
                    rec["p55_coh"] = rows[(s, d, i)]["guards"][k]["coh"]
                    K.put((k, "p55_" + s, d, i), rec)
        del items
        gc.collect()
    other = [(s, d, i) for (s, d, i) in need if s in ("fs", "uni")]
    if other:
        lpr = load_lps("test", "real", {i for _, _, i in other})
        for (s, d, i) in other:
            if s == "fs":
                x = lpr[i][rng_for("p14-55", d, "test", i, "frameshuf").permutation(len(lpr[i]))]
            else:
                T, V = lpr[i].shape
                zz = np.full((T, V), -math.log(V)) + 0.05 * rng_for("p14-55", d, "test", i, "uniform").standard_normal((T, V))
                x = (zz - np.log(np.exp(zz).sum(1, keepdims=True))).astype(np.float32)
            for k in E.g:
                if not K.has(k, "p55_" + s, d, i):
                    rec = decide(E, k, x)
                    rec["p55_action"] = rows[(s, d, i)]["guards"][k]["action"]
                    rec["p55_coh"] = rows[(s, d, i)]["guards"][k]["coh"]
                    K.put((k, "p55_" + s, d, i), rec)
    log(f"nulls: P14-55 done ({time.time() - t0:.0f} s)")
    K.fh.close()


def stage_score(E: Env | None) -> None:
    from fidetype.trust.dropin import ControlResult, offer_control

    fit = json.loads((OUT / "fit.json").read_text(encoding="utf-8"))
    V = Jsonl(OWN / "val.jsonl").rows
    T = Jsonl(OWN / "test.jsonl").rows
    N = Jsonl(OWN / "nulls.jsonl").rows
    R5 = read_jsonl(P1455 / "items.jsonl", lambda d: (d["set"], d["d"], d["i"]))
    need54 = json.loads((OWN / "p54-need.json").read_text(encoding="utf-8"))
    S, LTT = positions()
    out: dict = {"objects": {"config_id": CFG, "lm": LM_NAME, "feature": FEAT, "keep": KEEP}, "fit": fit}
    for k in CFG:
        tau = fit[k]["threshold"]
        after = lambda r: "withhold" if r["action"] == "offer" and r["D"] < tau else r["action"]  # noqa: E731
        real = [T[(k, "real", i)] for i in range(N_TEST)]
        rev = [T[(k, "rev_out", i)] for i in range(N_TEST)]
        ltt = [T[(k, "ltt", i)] for i in LTT]
        r0 = sum(r["action"] == "offer" for r in real)
        r1 = sum(after(r) == "offer" for r in real)
        v0 = sum(r["action"] == "offer" for r in rev)
        v1 = sum(after(r) == "offer" for r in rev)
        removed = sum(r["action"] == "offer" and after(r) != "offer" for r in real)
        res = {
            "threshold": tau,
            "B1": {"rev_out_offers": v1, "coherence_only": v0, "n": N_TEST, "limit": 4, "pass": v1 <= 4},
            "B2": {"real_offers_removed": removed, "real_offers_coherence": r0, "real_offers_both": r1, "n": N_TEST,
                   "limit": 4, "pass": removed <= 4},
            "B3": {"ltt_real_offers": sum(after(r) == "offer" for r in ltt),
                   "ltt_real_offers_coherence": sum(r["action"] == "offer" for r in ltt), "n": len(ltt), "limit": 36},
        }
        res["B3"]["pass"] = res["B3"]["ltt_real_offers"] >= 36
        # checks
        vs = [(V[(k, "real", i)], V[(k, "rev_out", i)]) for i in S]
        res["check_antisym_1e-9"] = {"val": sum(abs(a["D"] + b["D"]) <= 1e-9 for a, b in vs), "n_val": len(vs),
                                     "test": sum(abs(a["D"] + b["D"]) <= 1e-9 for a, b in zip(real, rev)),
                                     "n_test": N_TEST}
        res["check_coherence_equal_1e-9"] = sum(abs(a["coh"] - b["coh"]) <= 1e-9 for a, b in zip(real, rev))
        res["check_equivalence"] = {"equal": sum(after(r) == r["both_action"] for r in real + rev + ltt),
                                    "n": len(real) + len(rev) + len(ltt)}
        # B4: P14-54 test nulls
        b4 = {}
        ok4, rep4 = True, True
        for kind, cnt in need54["p54_offers_p14_57"].items():
            recs = [r for kk, r in N.items() if kk[0] == k and kk[1] == "p54_" + kind]
            rep4 &= all(r["action"] == r["p57_action"] and abs(r["coh"] - r["p57_coh"]) <= 1e-6 for r in recs)
            rep4 &= sum(r["action"] == "offer" for r in recs) == cnt[k]
            now = sum(after(r) in ("offer", "commit") for r in recs)
            b4[kind] = {"emit_p14_57_coherence_only": cnt[k], "emit_both": now, "n": N_TEST}
            ok4 &= now <= 4
        res["B4"] = {"pass": bool(ok4 and rep4), "repeat_ok": bool(rep4), "sets": b4}
        # B5: P14-55 nulls (P14-57 D3 rules)
        b5 = {}
        ok5, rep5 = True, True
        for s, n in {"ts": 800, "fs": 800, "uni": 800, "rev_in": 80, "do_nothing": 27, "lines": 80}.items():
            before = sum(1 for (ss, d, i), r in R5.items() if ss == s and "guards" in r
                         and r["guards"][k]["action"] == "offer")
            recs = [r for kk, r in N.items() if kk[0] == k and kk[1] == "p55_" + s]
            rep = sum(r["action"] == r["p55_action"] and abs(r["coh"] - r["p55_coh"]) <= 1e-6 for r in recs)
            rep5 &= rep == len(recs) and sum(r["action"] == "offer" for r in recs) == before
            now = sum(after(r) == "offer" for r in recs)
            oc = offer_control(N_TEST, r1, [ControlResult(s, s, n, 0, int(math.floor(0.05 * n + 1e-9)), now)],
                               rate=0.05)
            lim_ok = cp_upper(now, n) <= 0.05 if s in ("ts", "fs", "uni") else now <= int(math.floor(0.05 * n + 1e-9))
            passed = bool(lim_ok and oc["passed"] and now <= before)
            ok5 &= passed
            b5[s] = {"n": n, "offer_p14_55": before, "made_again": len(recs), "repeat_equal": rep, "offer_both": now,
                     "cp95_upper": cp_upper(now, n), "offer_control_pass": bool(oc["passed"]), "pass": passed}
        res["B5"] = {"pass": bool(ok5 and rep5), "repeat_ok": bool(rep5), "sets": b5}
        # descriptive
        res["D_real_test_offers"] = pct(r["D"] for r in real if r["action"] == "offer")
        res["D_per_frame_real_test_offers"] = pct(r["D_per_frame"] for r in real if r["action"] == "offer")
        res["real_test_D_below_0"] = sum(r["action"] == "offer" and r["D"] < 0 for r in real)
        res["n_fwd_minus_n_rev_real_test"] = pct(r["n_fwd"] - r["n_rev"] for r in real)
        # cost: the two beam searches per decision vs the coherence-only decision
        tb = [r["t_beam2"] for r in real]
        td = [r["t_decide"] for r in real]
        res["cost_s"] = {"t_beam2_real_test": pct(tb), "t_decide_real_test": pct(td),
                         "median_ratio_beam2_to_decide": round(float(np.median(np.array(tb) / np.array(td))), 3),
                         "t_beam2_per_frame_ms_median": round(float(np.median([r["t_beam2"] / r["T"] * 1e3
                                                                                for r in real])), 4),
                         "T_real_test": pct(r["T"] for r in real)}
        out[k] = res
    save_json(out, OUT / "results.json")
    log("score: " + json.dumps({k: {r: out[k][r]["pass"] for r in ("B1", "B2", "B3", "B4", "B5")} for k in CFG}))


def main(argv: list[str]) -> int:
    stages = argv[1:] or ["all"]
    assert all(s in ("val", "test", "nulls", "score", "all") for s in stages), stages
    if "all" in stages:
        stages = ["val", "test", "nulls", "score"]
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            E = Env()
            log(f"start {stages}; coherence { {k: g.threshold for k, g in E.coh.items()} }; lm {LM_NAME}; "
                f"readout settings {E.ro.settings}")
            for s in stages:
                {"val": stage_val, "test": stage_test, "nulls": stage_nulls, "score": stage_score}[s](E)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stages} ({time.time() - t0:.0f} s); peak {mem_mb()[1]:.0f} MB")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
