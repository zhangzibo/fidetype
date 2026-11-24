r"""P5-38 (gap 191): faster `lm_beam_direction` offer gate. The LM readout keeps its last searches
(`LmReadout.search_cache`, exact: a search on bit-equal log-probs returns the kept result), so the gate's forward
search S(x) reuses the guard decode's search when the guard decodes with the same readout (`readout="lm"`).

Usage (repo root; CPU only), detached by launch.py::

    C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-23-p5-38-fast-direction-gate/launch.py <stage>

Stages:

- ``bench`` (run it under ``--class timing``, one thread): a small fixed sample, the first 20 of the 80 test
  sentences (real input). Per guard and sentence, 3 repetitions, modes in rotated order:
  ``coh`` = coherence gate only; ``off`` = shipped gate list, readout cache off (``search_cache = 0``, the
  P14-60 behaviour); ``on`` = shipped gate list, cache on (default). The cache is cleared before each timed
  decision. Also the gate alone (``lm_beam_direction(guard._last_lp, readout)`` after a coherence-only decision,
  the P5-36b ``t_beam2`` measure) with the cache on and off. Wall time (``perf_counter``) and CPU time
  (``thread_time``). Output: ``results/bench.json``.
- ``sets:<guard>``: decisions with the cache off and on, compared field by field (action, shown candidates,
  reason, offer-gate reason, every offer-gate feature as a bit pattern), on the P5-36b sets: the 66 S val
  sentences (real and ``rev_out``), the 40 LTT val sentences, the 80 test sentences (real and ``rev_out``).
  Output: ``<OWN>/sets-<guard>.jsonl`` (digests only, no text) and ``results/identity-sets-<guard>.json``.
- ``recheck:<guard>:<on|off>``: the P14-56 offer-control re-check (``recheck_offer_control``, P5-31 rule) with the
  shipped gate list and the cache on or off, same inputs as P14-60 (106 val log-probs, 106 time-shuffled val
  inputs); every ``_decide_quiet`` call is recorded (digest of action, candidates, reason).
  Output: ``<OWN>/recheck-<guard>-<mode>.json``.
- ``compare``: ``results/identity-recheck.json`` from the two re-check records per guard (the decision
  sequences must be equal), and the summary ``results/results.json``.

Log, DONE-<stage> / FAILED-<stage> / STOP: C:/Users/zhang/bci-data/derived/p5-38. Our own code (Apache-2.0).
"""
from __future__ import annotations

import os

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = ""
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import hashlib  # noqa: E402
import json  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
RES = HERE / "results"
OWN = Path("C:/Users/zhang/bci-data/derived/p5-38")
LP = Path("C:/Users/zhang/bci-data/derived/p14-41")  # read only
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-f498c0637536daec"}
N_BENCH = 20
REPS = 3
N_TEST = 80


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(OWN / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def watcher() -> None:
    while True:
        time.sleep(2.0)
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    tmp.replace(p)


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(LP / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def positions() -> tuple[list[int], list[int]]:
    """(S, LTT): the 66 non-LTT val positions and the 40 LTT val positions (the calibrate split; as P5-36b)."""
    from fidetype.trust.dropin import _split

    n_fit, n_pol, _ = _split(106)
    perm = [int(i) for i in np.random.default_rng(0).permutation(106)]
    return perm[: n_fit + n_pol], perm[n_fit + n_pol:]


def guards():
    import fidetype.pretrained as ftp

    m = ftp.load("willett-hw")
    g = {"builtin": m.guard(), "lm": m.guard(readout="lm")}
    for k, x in g.items():
        assert x.config_id == CFG[k], (k, x.config_id)
        assert [y.feature for y in x.offer_gates] == ["coherence", "lm_beam_direction"], k
        assert x.offer_gates[1].threshold == 0.0 and x.offer_gates[1].readout is not None, k
        readout(x)
    # the LM guard's direction gate uses the same readout object as its decode_fn (P14-60 wiring)
    return m, g


_RO: dict[int, object] = {}


def readout(g):
    """The LM readout of the guard's shipped direction gate (kept, because a stage may switch the gate off)."""
    if id(g) not in _RO:
        _RO[id(g)] = g.offer_gates[1].readout
    return _RO[id(g)]


def set_cache(g, on: bool) -> None:
    ro = readout(g)
    ro.search_cache = 2 if on else 0
    ro._memo.clear()


def act(r) -> str:
    return str(getattr(r.action, "value", r.action)).lower()


def h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def bits(v: float) -> str:
    return float(v).hex()


def record(g, r) -> dict:
    """Digest of one decision (no text in the file)."""
    feats = g.last_offer_features
    return {"action": act(r), "raw_action": str(r.raw_action), "cand": h([r.text, list(r.choices)]),
            "p": [bits(r.p_top1), bits(r.guard_risk)], "reason": h(str(r.reason)), "gate_why": h(str(g._offer_gate_why)),
            "feats": None if feats is None else {k: bits(v) for k, v in sorted(feats.items())}}


# --- stages --------------------------------------------------------------------------------------------

def stage_bench(m, G) -> None:
    from fidetype.trust import offer_gate as og
    from fidetype.utils.isolation import describe_current

    lp_test = load_lps("test", "real")[:N_BENCH]
    out = {"sample": f"test sentences 0..{N_BENCH - 1} (real input)", "reps": REPS, "env": describe_current(),
           "guards": {}}
    for k, g in G.items():
        both = list(g.offer_gates)
        ro = readout(g)
        rows = []
        for i, x in enumerate(lp_test):
            t = {mode: [] for mode in ("coh", "off", "on", "gate_off", "gate_on")}
            c = {mode: [] for mode in t}
            acts = {}
            for rep in range(REPS):
                modes = ["coh", "off", "on"]
                modes = modes[rep % 3:] + modes[: rep % 3]
                for mode in modes:
                    g.set_offer_gate(both[:1] if mode == "coh" else both)
                    set_cache(g, mode != "off")
                    s = ro.search_stats.copy()
                    w0, c0 = time.perf_counter(), time.thread_time()
                    r = g._decide_quiet(x)
                    t[mode].append(time.perf_counter() - w0)
                    c[mode].append(time.thread_time() - c0)
                    acts[mode] = act(r)
                    acts[mode + "_searches"] = {kk: ro.search_stats[kk] - s[kk] for kk in s}
                # the gate alone after a coherence-only decision (P5-36b t_beam2), cache on and off
                for mode in (("gate_on", "gate_off") if rep % 2 == 0 else ("gate_off", "gate_on")):
                    g.set_offer_gate(both[:1])
                    set_cache(g, True)
                    g._decide_quiet(x)  # the decode fills the cache (LM guard) as in a real decision
                    lp = g._last_lp
                    if mode == "gate_off":
                        set_cache(g, False)
                    w0, c0 = time.perf_counter(), time.thread_time()
                    og.lm_beam_direction(lp, ro)
                    t[mode].append(time.perf_counter() - w0)
                    c[mode].append(time.thread_time() - c0)
            g.set_offer_gate(both)
            set_cache(g, True)
            row = {"i": i, "T": int(x.shape[0]), "actions": acts,
                   "wall": {mm: statistics.median(v) for mm, v in t.items()},
                   "cpu": {mm: statistics.median(v) for mm, v in c.items()}}
            rows.append(row)
        offers = [r for r in rows if r["actions"]["coh"] == "offer"]

        def med(key, clock="wall"):
            return round(statistics.median(r[clock][key] for r in offers), 4)

        def med_extra(mode, clock="wall"):
            return round(statistics.median(r[clock][mode] - r[clock]["coh"] for r in offers), 4)

        summ = {"n": len(rows), "n_coherence_offers": len(offers),
                "decision_coh_median_s": med("coh"),
                "extra_per_offer_median_s": {"off": med_extra("off"), "on": med_extra("on")},
                "extra_per_offer_cpu_median_s": {"off": med_extra("off", "cpu"), "on": med_extra("on", "cpu")},
                "gate_alone_median_s": {"off": med("gate_off"), "on": med("gate_on")},
                "gate_alone_cpu_median_s": {"off": med("gate_off", "cpu"), "on": med("gate_on", "cpu")},
                "searches_per_offer_decision": {
                    mode: sorted({json.dumps(r["actions"][mode + "_searches"]) for r in offers})
                    for mode in ("coh", "off", "on")},
                "actions_equal_off_on": all(r["actions"]["off"] == r["actions"]["on"] for r in rows)}
        summ["gate_alone_ratio_on_off"] = round(summ["gate_alone_median_s"]["on"] / summ["gate_alone_median_s"]["off"], 3)
        out["guards"][k] = {"summary": summ, "rows": rows}
        log(f"bench {k}: {json.dumps(summ)}")
    save_json(out, RES / "bench.json")


def stage_sets(m, G, k: str) -> None:
    g = G[k]
    lpv, lpt = load_lps("val", "real"), load_lps("test", "real")
    S, LTT = positions()
    items = ([("val_S", s, i) for i in S for s in ("real", "rev_out")] + [("val_ltt", "real", i) for i in LTT]
             + [("test", s, i) for i in range(N_TEST) for s in ("real", "rev_out")])
    path = OWN / f"sets-{k}.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                done[tuple(d["key"])] = d
    fh = open(path, "a", encoding="utf-8")
    g.collect_offer_features = True  # every offer-gate feature of every decision, as bit patterns
    t0 = time.time()
    for n, (split, s, i) in enumerate(items):
        key = (split, s, i)
        if key in done:
            continue
        base = (lpt if split == "test" else lpv)[i]
        x = base if s == "real" else np.ascontiguousarray(base[::-1])
        rec = {}
        for mode in (("off", "on") if n % 2 == 0 else ("on", "off")):
            set_cache(g, mode == "on")
            rec[mode] = record(g, g._decide_quiet(x))
        d = {"key": list(key), **rec, "equal": rec["off"] == rec["on"]}
        fh.write(json.dumps(d) + "\n")
        fh.flush()
        done[key] = d
        if n % 50 == 0:
            log(f"sets {k}: {n + 1} / {len(items)} ({time.time() - t0:.0f} s)")
    fh.close()
    g.collect_offer_features = False
    set_cache(g, True)
    rows = [done[k2] for k2 in [(a, b, c) for a, b, c in items]]
    by = {}
    for r in rows:
        name = f"{r['key'][0]}:{r['key'][1]}"
        b = by.setdefault(name, {"n": 0, "equal": 0, "offers_off": 0, "offers_on": 0})
        b["n"] += 1
        b["equal"] += r["equal"]
        b["offers_off"] += r["off"]["action"] == "offer"
        b["offers_on"] += r["on"]["action"] == "offer"
    res = {"guard": k, "config_id": g.config_id, "n": len(rows), "n_equal": sum(r["equal"] for r in rows),
           "all_equal": all(r["equal"] for r in rows), "by_set": by,
           "compared": "action, shown candidates (digest), reason (digest), offer-gate reason (digest), every "
                       "offer-gate feature incl. lm_beam_direction (float bit pattern); cache off vs on",
           "seconds": round(time.time() - t0, 1)}
    save_json(res, RES / f"identity-sets-{k}.json")
    log(f"sets {k}: all_equal {res['all_equal']} ({res['n_equal']} / {res['n']}); {by}")


def stage_recheck(m, G, k: str, mode: str) -> None:
    import fidetype.trust as ft

    out = OWN / f"recheck-{k}-{mode}.json"
    if out.exists():
        log(f"recheck {k} {mode}: done before, skipped")
        return
    g = G[k]
    set_cache(g, mode == "on")
    seq = []
    orig = g._decide_quiet

    def rec(*a, **kw):
        r = orig(*a, **kw)
        seq.append(record(g, r))
        return r

    g._decide_quiet = rec
    lp_val, lp_ts = load_lps("val", "real"), load_lps("val", "timeshuf")
    t0 = time.time()
    s0 = dict(readout(g).search_stats)  # the counters are per process (earlier stages add to them)
    rc = ft.recheck_offer_control(g, lp_val, null_inputs=lp_ts)
    del g._decide_quiet
    rc.update(guard=k, cache=mode, config_id=g.config_id, offer_gate=[x.to_dict() for x in g.offer_gates],
              seconds=round(time.time() - t0, 1), searches={x: readout(g).search_stats[x] - s0[x] for x in s0}, decisions=seq)
    save_json(rc, out)
    log(f"recheck {k} {mode}: passed {rc['passed']}: "
        f"{[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}, real {rc['real']} ({rc['seconds']} s)")


def stage_compare(m, G) -> None:
    res = {}
    for k in CFG:
        a = json.loads((OWN / f"recheck-{k}-off.json").read_text(encoding="utf-8"))
        b = json.loads((OWN / f"recheck-{k}-on.json").read_text(encoding="utf-8"))
        da, db = a.pop("decisions"), b.pop("decisions")
        strip = ("seconds", "cache", "searches")
        same_summary = {x: v for x, v in a.items() if x not in strip} == {x: v for x, v in b.items() if x not in strip}
        res[k] = {"n_decisions": [len(da), len(db)], "decisions_equal": da == db, "summary_equal": same_summary,
                  "n_offer_off": sum(d["action"] == "offer" for d in da),
                  "n_offer_on": sum(d["action"] == "offer" for d in db),
                  "controls": [(c["name"], c["n_offer"], c["n"]) for c in b["controls"]], "real": b["real"],
                  "passed": b["passed"], "seconds": {"off": a["seconds"], "on": b["seconds"]}}
        log(f"compare {k}: {res[k]}")
    save_json({"compared": "every _decide_quiet call of recheck_offer_control (real LTT, uniform, frame-shuffled, "
                           "time-shuffled), in order: action, shown candidates, reason, offer-gate reason (digests); "
                           "and the re-check result dict; cache off vs on", **res}, RES / "identity-recheck.json")
    bench = json.loads((RES / "bench.json").read_text(encoding="utf-8"))
    sets = {k: json.loads((RES / f"identity-sets-{k}.json").read_text(encoding="utf-8")) for k in CFG}
    save_json({"bench": {k: v["summary"] for k, v in bench["guards"].items()},
               "identity_sets": {k: {x: v[x] for x in ("n", "n_equal", "all_equal", "by_set")} for k, v in sets.items()},
               "identity_recheck": res}, RES / "results.json")


def main() -> int:
    stages = sys.argv[1:]
    if not stages:
        print(__doc__)
        return 2
    OWN.mkdir(parents=True, exist_ok=True)
    tag = "_".join(s.replace(":", "-") for s in stages)
    for p in (OWN / f"DONE-{tag}", OWN / f"FAILED-{tag}"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            m, G = guards()
            log(f"start {stages}")
            for s in stages:
                parts = s.split(":")
                if parts[0] == "bench":
                    stage_bench(m, G)
                elif parts[0] == "sets":
                    stage_sets(m, G, parts[1])
                elif parts[0] == "recheck":
                    stage_recheck(m, G, parts[1], parts[2])
                elif parts[0] == "compare":
                    stage_compare(m, G)
                else:
                    raise ValueError(f"unknown stage {s!r}")
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / f"FAILED-{tag}").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stages} ({time.time() - t0:.0f} s)")
    (OWN / f"DONE-{tag}").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
