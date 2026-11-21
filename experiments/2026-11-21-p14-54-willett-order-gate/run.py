"""P14-54: a frame-order-aware offer gate for both willett-hw guards (plan.md, pre-registered).

Usage (repo root)::

    python experiments/2026-11-21-p14-54-willett-order-gate/run.py select|eval|all builtin|lm

- ``select``: the val-only selection of plan section 5 (selection set S = the 66 non-LTT val positions).
- ``eval``: the evaluation of plan section 6 (V = ``recheck_offer_control`` of the gated guard; T = the 80 test
  sentences x five inputs).

Outputs: ``results/selection-<g>.json``, ``results/recheck-<g>-gated.json``, ``results/test-<g>.json`` (counts and
thresholds only). Per-item features, a log and ``DONE-<g>`` / ``FAILED-<g>`` go to ``bci-data/derived/p14-54``.
"""
from __future__ import annotations

import ctypes
import os

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
import hashlib
import json
import math
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p14-54"
LP = DER / "p14-41"  # read only (the p14-48 lp files are byte-identical)
REC = {"builtin": DER / "p14-41" / "decisions.jsonl", "lm": DER / "p14-49" / "decisions.jsonl"}  # read only
GUARDS = {"builtin": DER / "p14-41" / "willett-hw.guard.json", "lm": DER / "p14-49" / "willett-hw.lm2.guard.json"}
GUARD_SHA = {"builtin": "b16963ed5d2ba09ed0525fc8193b8b8a0a1d0ec7814faf12ee8b6174e93c33fc",
             "lm": "97a6c219f0bc8ed6c4483b79ece4a10a128c270ff2e0b0c0574022a5434f144e"}
CANDS = ("coherence", "coherence_ratio", "nb_coherence", "peak", "neg_entropy", "nb_share")
SEL_SEED, N_NULL, N_CHECK = 5454, 300, 5
P1441_SEED = 0
TEST_KINDS = ("real", "timeshuf", "zero", "frameshuf", "uniform")
R3_KEEP, R45_MAX = 0.90, 4


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


WHICH = "?"


def log(msg: str) -> None:
    rss, peak = mem_mb()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] (rss {rss:.0f} MB, peak {peak:.0f} MB) {msg}"
    print(line, flush=True)
    with open(OWN / f"run-{WHICH}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1), encoding="utf-8")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(LP / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def item_rng(split: str, i: int, kind: str) -> np.random.Generator:
    """The P14-41 generator per (split, sentence, control)."""
    h = hashlib.sha256(f"p14-41|{P1441_SEED}|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def load_guard(which: str):
    import fidetype.trust as ft

    assert sha256(GUARDS[which]) == GUARD_SHA[which], "guard file changed"
    if which == "lm":
        import fidetype.pretrained as ftp

        return ft.load(GUARDS["lm"], decode_fn=ftp.load("willett-hw").lm_readout().decode_fn())
    return ft.load(GUARDS["builtin"])


# --- decisions and features ---------------------------------------------------------------------------

def decide(g, x, scale=None) -> dict:
    """A full decision with the offer-gate features of the guard (gate as set on ``g``)."""
    g.collect_offer_features = True
    r = g._decide_quiet(x, scale)
    f = {k: float(g.last_offer_features[k]) for k in CANDS}
    return {"action": r.action, "gated": g._offer_gate_why is not None, "f": f, "decided": True}


def fast_features(g, x, scale) -> dict:
    """The frame features of ``x`` as the guard sees them (codec stream, then the frozen frame temperature)."""
    from fidetype.trust import offer_gate as og

    st = g._codec.stream(x, scale)
    fs = g._layer.components.frame_scaler
    st = fs.transform_stream(st) if fs.temperature != 1.0 else st
    f = og.frame_features(np.asarray(st.log_probs, np.float64), int(g._codec.vocab.blank_id or 0))
    return {k: float(f[k]) for k in CANDS}


class Uniform:
    """Plan section 5 step 2: decide a uniform input in full only if a gate could let it through."""

    def __init__(self, g, scale):
        self.g, self.scale, self.n_seen, self.ok, self.check = g, scale, 0, True, []

    def __call__(self, x, could_pass) -> dict:
        f = fast_features(self.g, x, self.scale)
        self.n_seen += 1
        if self.n_seen <= N_CHECK or not self.ok or could_pass(f):
            rec = decide(self.g, x, self.scale)
            if self.n_seen <= N_CHECK:
                same = all(math.isclose(f[k], rec["f"][k], rel_tol=1e-6, abs_tol=1e-12) for k in CANDS)
                self.check.append(same)
                if not same:
                    self.ok = False
                    log(f"uniform fast-path check FAILED on item {self.n_seen}: {f} vs {rec['f']}")
            return rec
        return {"action": None, "gated": None, "f": f, "decided": False}

    def record(self) -> dict:
        return {"checked": len(self.check), "check_equal": all(self.check) and self.ok,
                "n": self.n_seen}


def gated_offer(rec: dict, gates: list[tuple[str, float]]) -> bool:
    if any(rec["f"][k] < t for k, t in gates):
        return False
    assert rec["decided"], "an undecided input passes the gate"
    return rec["action"] == "offer"


def control_counts(real: list[dict], nulls: dict[str, list[dict]], gates, rate: float) -> dict:
    from fidetype.trust.dropin import ControlResult, offer_control

    n_off = sum(gated_offer(r, gates) for r in real)
    cs = []
    for name, recs in nulls.items():
        n_c = sum(r["action"] == "commit" for r in recs if r["decided"])
        cs.append(ControlResult(name, name, len(recs), n_c, int(math.floor(rate * len(recs) + 1e-9)),
                                sum(gated_offer(r, gates) for r in recs)))
    oc = offer_control(len(real), n_off, cs, rate=rate)
    oc["largest_null_rate"] = max(c["offer_rate"] for c in oc["controls"])
    return oc


def summary(vals) -> list[float]:
    v = np.asarray(list(vals), float)
    return [float(np.min(v)), float(np.median(v)), float(np.max(v))] if len(v) else []


# --- stages ---------------------------------------------------------------------------------------------

def stage_select(which: str) -> dict:
    from fidetype.adapters.ctc_logits import to_log_probs

    t0 = time.time()
    g = load_guard(which)
    sh = g.sheet
    lp_val, lp_ts = load_lps("val", "real"), load_lps("val", "timeshuf")
    assert len(lp_val) == sh.n_items == 106
    S = np.random.default_rng(sh.seed).permutation(sh.n_items)[: sh.n_fit + sh.n_policy]
    log(f"select {which}: S = {len(S)} positions (seed {sh.seed}); deciding S real")
    real = [decide(g, lp_val[int(i)]) for i in S]
    offers = [r for r in real if r["action"] == "offer"]
    m = len(offers)
    log(f"select {which}: S real offers {m} / {len(S)} ({time.time() - t0:.0f} s)")
    asc = {k: sorted(r["f"][k] for r in offers) for k in CANDS}
    tau1 = {k: asc[k][0] for k in CANDS}
    tau1b = {k: asc[k][min(int(math.floor(0.05 * m + 1e-9)), m - 1)] for k in CANDS}

    rng = np.random.default_rng(SEL_SEED)
    idx = S[rng.integers(0, len(S), size=N_NULL)]
    V, scale = len(g._codec.vocab), g._codec.input_scale
    uni = Uniform(g, "logits")
    could = lambda f: any(f[k] >= tau1[k] for k in CANDS)  # tau1 <= tau1b: the smallest thresholds
    nulls: dict[str, list[dict]] = {"uniform": [], "shuffled": [], "user": []}
    for i in idx:
        T = to_log_probs(lp_val[int(i)], scale).shape[0]
        nulls["uniform"].append(uni(np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V)), could))
    log(f"select {which}: uniform done, {sum(r['decided'] for r in nulls['uniform'])} decided "
        f"({time.time() - t0:.0f} s); check {uni.record()}")
    for i in idx:
        lp = to_log_probs(lp_val[int(i)], scale)
        nulls["shuffled"].append(decide(g, lp[rng.permutation(lp.shape[0])], "log_probs"))
    log(f"select {which}: frame-shuffled done ({time.time() - t0:.0f} s)")
    nulls["user"] = [decide(g, lp_ts[int(i)]) for i in S]
    log(f"select {which}: user nulls done ({time.time() - t0:.0f} s)")
    rate = float(sh.null_max_commit_rate)

    def tier(taus):
        return {k: {"threshold": taus[k], **control_counts(real, nulls, [(k, taus[k])], rate)} for k in CANDS}

    def choose(rows):
        ok = [k for k in CANDS if rows[k]["passed"]]
        return min(ok, key=lambda k: (rows[k]["largest_null_rate"], CANDS.index(k))) if ok else None

    out: dict = {"guard": which, "config_id": g.config_id, "S_n": len(S), "S_real_offers": m,
                 "selection_seed": SEL_SEED, "uniform_fast_path": uni.record(),
                 "ungated_null_offers": {k: sum(r["action"] == "offer" for r in v if r["decided"])
                                         for k, v in nulls.items()},
                 "features_min_median_max": {
                     k: {"real_offers": summary(r["f"][k] for r in offers),
                         **{n: summary(r["f"][k] for r in v) for n, v in nulls.items()}} for k in CANDS}}
    t1 = tier(tau1)
    out["tier1"] = t1
    chosen, gates, tier_name = choose(t1), None, None
    if chosen:
        gates, tier_name = [(chosen, tau1[chosen])], "tier1"
    else:
        t1b = tier(tau1b)
        out["tier1b"] = t1b
        c = choose(t1b)
        if c:
            chosen, gates, tier_name = c, [(c, tau1b[c])], "tier1b"
        else:
            best2 = sorted(CANDS, key=lambda k: (t1[k]["largest_null_rate"], CANDS.index(k)))[:2]
            g2 = [(k, tau1[k]) for k in best2]
            t2 = control_counts(real, nulls, g2, rate)
            out["tier2"] = {"gates": g2, **t2}
            if t2["passed"]:
                chosen, gates, tier_name = "+".join(best2), g2, "tier2"
    if gates is None:
        b = min(CANDS, key=lambda k: (t1[k]["largest_null_rate"], CANDS.index(k)))
        out["chosen"] = {"tier": None, "gates": [(b, tau1[b])], "information_only": True}
    else:
        out["chosen"] = {"tier": tier_name, "gates": gates, "information_only": False}
    out["seconds"] = round(time.time() - t0, 1)
    save_json(out, RES / f"selection-{which}.json")
    with open(OWN / f"select-{which}.jsonl", "w", encoding="utf-8") as f:
        for name, recs in [("real", real)] + list(nulls.items()):
            for k, r in enumerate(recs):
                f.write(json.dumps({"set": name, "k": k, **r}) + "\n")
    log(f"select {which}: chosen {out['chosen']} ({out['seconds']} s)")
    return out


def stage_eval(which: str) -> dict:
    import fidetype.trust as ft
    from fidetype.trust.dropin import ControlResult, offer_control
    from fidetype.trust.offer_gate import OfferGate

    t0 = time.time()
    sel = json.loads((RES / f"selection-{which}.json").read_text(encoding="utf-8"))
    gates_ft = [(str(k), float(t)) for k, t in sel["chosen"]["gates"]]
    info = bool(sel["chosen"]["information_only"])
    g = load_guard(which)
    gates = [OfferGate(k, t, note=f"P14-54 val-only selection ({sel['chosen']['tier']})") for k, t in gates_ft]
    g.set_offer_gate(gates)
    log(f"eval {which}: gates {[x.label() for x in gates]} (information only: {info})")

    # V: the P5-31 re-check of the gated guard
    lp_val, lp_ts = load_lps("val", "real"), load_lps("val", "timeshuf")
    rc = ft.recheck_offer_control(g, lp_val, null_inputs=lp_ts)
    rc.update(guard=which, config_id=g.config_id, offer_gate=[x.to_dict() for x in gates],
              before_gate_source=f"experiments/2026-11-21-p5-31-offer-control/results/recheck-{which}.json",
              seconds=round(time.time() - t0, 1))
    save_json(rc, RES / f"recheck-{which}-gated.json")
    log(f"eval {which}: V re-check passed {rc['passed']}: "
        f"{[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}, real {rc['real']}")
    del lp_val, lp_ts

    # T: 80 test sentences x five inputs
    t1 = time.time()
    cache = {k: load_lps("test", k) for k in ("real", "timeshuf", "zero")}
    rec_old = {}
    for line in REC[which].read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            rec_old[(d["kind"], int(d["i"]))] = d["action"]
    uni = Uniform(g, None)
    could = lambda f: all(f[k] >= t for k, t in gates_ft)
    rows, per = {}, []
    for kind in TEST_KINDS:
        recs = []
        for i, lp_real in enumerate(cache["real"]):
            if kind in ("real", "timeshuf", "zero"):
                x = cache[kind][i]
            elif kind == "frameshuf":
                x = lp_real[item_rng("test", i, "frameshuf").permutation(len(lp_real))]
            else:
                T, V = lp_real.shape
                z = np.full((T, V), -math.log(V)) + 0.05 * item_rng("test", i, "uniform").standard_normal((T, V))
                x = z - np.log(np.exp(z).sum(1, keepdims=True))
            r = uni(x, could) if kind == "uniform" else decide(g, x)
            if r["decided"]:
                ungated = "offer" if r["gated"] else r["action"]
            else:  # fast path: below the gate, so not a gated offer; recorded ungated action
                r["action"], r["gated"] = "withhold", rec_old[(kind, i)] == "offer"
                ungated = rec_old[(kind, i)]
            r["ungated"] = ungated
            r["ungated_matches_record"] = ungated == rec_old[(kind, i)]
            recs.append(r)
            per.append({"kind": kind, "i": i, **r})
        n = len(recs)
        rows[kind] = {"n": n, "commit": sum(r["action"] == "commit" for r in recs),
                      "offer": sum(r["action"] == "offer" for r in recs),
                      "withhold": sum(r["action"] == "withhold" for r in recs),
                      "gated_by_offer_gate": sum(bool(r["gated"]) for r in recs),
                      "ungated_offer": sum(r["ungated"] == "offer" for r in recs),
                      "ungated_commit": sum(r["ungated"] == "commit" for r in recs),
                      "ungated_matches_record": sum(r["ungated_matches_record"] for r in recs),
                      "decided": sum(r["decided"] for r in recs)}
        rows[kind]["emit"] = rows[kind]["commit"] + rows[kind]["offer"]
        log(f"eval {which}: test {kind}: {rows[kind]} ({time.time() - t1:.0f} s)")
    with open(OWN / f"test-{which}.jsonl", "w", encoding="utf-8") as f:
        for p in per:
            f.write(json.dumps(p) + "\n")
    fs = rows["frameshuf"]
    r6 = offer_control(rows["real"]["n"], rows["real"]["offer"],
                       [ControlResult("shuffled", "test frame-shuffled", fs["n"], fs["commit"],
                                      int(math.floor(0.05 * fs["n"] + 1e-9)), fs["offer"])], rate=0.05)
    ltt_ungated = 40
    rules = {
        "R1": {"pass": bool(rc["passed"]), "value": [(c["name"], c["n_offer"], c["n"], c["passed"]) for c in rc["controls"]]},
        "R2": {"pass": bool(rc["commits_match_sheet"] and rc["ltt_commits"] == 0),
               "value": {"commits_match_sheet": rc["commits_match_sheet"], "ltt_commits": rc["ltt_commits"]}},
        "R3": {"pass": rc["real"]["n_offer"] >= math.ceil(R3_KEEP * ltt_ungated),
               "value": f"{rc['real']['n_offer']} / {rc['real']['n']} (limit >= {math.ceil(R3_KEEP * ltt_ungated)})"},
        "R4": {"pass": all(rows[k]["emit"] <= R45_MAX for k in ("timeshuf", "zero", "uniform")),
               "value": {k: f"{rows[k]['emit']} / {rows[k]['n']}" for k in ("timeshuf", "zero", "uniform")}},
        "R5": {"pass": rows["real"]["gated_by_offer_gate"] <= R45_MAX,
               "value": f"{rows['real']['gated_by_offer_gate']} / {rows['real']['n']}"},
        "R6": {"pass": bool(r6["passed"]), "value": r6},
        "R7": {"pass": all(rows[k]["commit"] == rows[k]["ungated_commit"] == 0 for k in TEST_KINDS),
               "value": {k: rows[k]["commit"] for k in TEST_KINDS}},
    }
    out = {"guard": which, "config_id": g.config_id, "gates": [x.to_dict() for x in gates],
           "information_only": info, "test": rows, "uniform_fast_path": uni.record(), "rules": rules,
           "all_pass": all(v["pass"] for v in rules.values()) and not info,
           "seconds_recheck": rc["seconds"], "seconds_test": round(time.time() - t1, 1)}
    save_json(out, RES / f"test-{which}.json")
    log(f"eval {which}: rules {{{', '.join(k + ':' + str(v['pass']) for k, v in rules.items())}}}; "
        f"all pass {out['all_pass']}")
    return out


def main(argv: list[str]) -> int:
    global WHICH
    stage, WHICH = argv[1], argv[2]
    assert stage in ("select", "eval", "all") and WHICH in GUARDS
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / f"DONE-{WHICH}", OWN / f"FAILED-{WHICH}"):
        p.unlink(missing_ok=True)
    try:
        if stage in ("select", "all"):
            stage_select(WHICH)
        if stage in ("eval", "all"):
            stage_eval(WHICH)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / f"FAILED-{WHICH}").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stage} {WHICH}; peak {mem_mb()[1]:.0f} MB")
    (OWN / f"DONE-{WHICH}").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
