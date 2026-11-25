r"""P5-41 (gap 214): bit-identical speed-up of the built-in ``willett-hw`` guard's ``lm_beam_direction`` offer gate.

The gate runs two LM beam searches (``LMBeam.push`` on x and on rev x). P5-41 rewrites the per-frame loop of
``LMBeam.push`` with less numpy call overhead and the same float operations. ``before`` = the kept P11-07 loop
(``LMBeam._push_reference``), ``after`` = the new ``LMBeam.push``. Harness: the P5-38 run.py
(``experiments/2026-11-23-p5-38-fast-direction-gate/run.py``), with the mode switch changed from the readout
cache to the push loop. The readout cache (shipped on) is cleared before every decision, so no mode reuses a
search of the other mode.

Usage (repo root; CPU only), detached by launch.py::

    C:\venvs\fidetype-rocm\Scripts\python.exe experiments/2026-11-24-p5-41-fast-builtin-direction-gate/launch.py <stage>

Stages:

- ``bench`` (run it under ``--class timing``, one thread): the P5-38 sample, the first 20 of the 80 test
  sentences (real input). Per guard and sentence, 3 repetitions, modes in rotated order: ``coh`` = coherence
  gate only; ``before`` / ``after`` = shipped gate list with the old / new loop. Also the gate alone
  (``lm_beam_direction(guard._last_lp, readout)`` after a coherence-only decision), before and after. Wall time
  (``perf_counter``) and CPU time (``thread_time``). Output: ``results/bench.json``.
- ``sets:<guard>``: decisions before and after, compared field by field (action, shown candidates, reason,
  offer-gate reason, every offer-gate feature as a bit pattern), on the P5-38 sets (P5-36b val S real and
  ``rev_out``, val LTT, 80 test real and ``rev_out``). Output: ``<OWN>/sets-<guard>.jsonl`` (digests only, no
  text) and ``results/identity-sets-<guard>.json``.
- ``recheck:<guard>:<before|after>``: the P14-56 offer-control re-check (``recheck_offer_control``, P5-31 rule),
  shipped gate list, same inputs as P5-38; every ``_decide_quiet`` call recorded (digests).
  Output: ``<OWN>/recheck-<guard>-<mode>.json``.
- ``compare``: ``results/identity-recheck.json`` and the summary ``results/results.json``.

Log, DONE-<stage> / FAILED-<stage> / STOP: C:/Users/zhang/bci-data/derived/p5-41. Our own code (Apache-2.0).
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
OWN = Path("C:/Users/zhang/bci-data/derived/p5-41")
LP = Path("C:/Users/zhang/bci-data/derived/p14-41")  # read only
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-f498c0637536daec"}
OFFER_GATE_IDS: dict[str, str] = {}
N_BENCH = 20
REPS = 3
N_TEST = 80
MODES = ("before", "after")


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


_NEW_PUSH = None


def set_mode(mode: str) -> None:
    """``before``: the P11-07 loop; ``after``: the P5-41 loop (class attribute, so every LMBeam uses it)."""
    global _NEW_PUSH
    from fidetype.pretrained.lmreadout import LMBeam

    if _NEW_PUSH is None:
        _NEW_PUSH = LMBeam.push
    if mode == "before":
        LMBeam.push = LMBeam._push_reference
    elif mode == "after":
        LMBeam.push = _NEW_PUSH
    else:
        raise ValueError(mode)


def guards():
    import fidetype.pretrained as ftp

    m = ftp.load("willett-hw")
    g = {"builtin": m.guard(), "lm": m.guard(readout="lm")}
    for k, x in g.items():
        assert x.config_id == CFG[k], (k, x.config_id)
        assert [y.feature for y in x.offer_gates] == ["coherence", "lm_beam_direction"], k
        assert x.offer_gates[1].threshold == 0.0 and x.offer_gates[1].readout is not None, k
        assert x.offer_gates[1].readout.search_cache == 2, k  # shipped default
        OFFER_GATE_IDS[k] = str(getattr(x, "offer_gate_id", None))
        readout(x)
    return m, g


_RO: dict[int, object] = {}


def readout(g):
    """The LM readout of the guard's shipped direction gate (kept, because a stage may switch the gate off)."""
    if id(g) not in _RO:
        _RO[id(g)] = g.offer_gates[1].readout
    return _RO[id(g)]


def clear(g) -> None:
    """Empty the readout search cache (the LM guard decodes with the same readout object)."""
    readout(g)._memo.clear()


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
           "note": "the P15-50 GPU training job of another agent ran at the same time (not pinned to these cores)",
           "guards": {}}
    for k, g in G.items():
        both = list(g.offer_gates)
        ro = readout(g)
        rows = []
        for i, x in enumerate(lp_test):
            t = {mode: [] for mode in ("coh", "before", "after", "gate_before", "gate_after")}
            c = {mode: [] for mode in t}
            acts = {}
            for rep in range(REPS):
                modes = ["coh", "before", "after"]
                modes = modes[rep % 3:] + modes[: rep % 3]
                for mode in modes:
                    g.set_offer_gate(both[:1] if mode == "coh" else both)
                    set_mode("before" if mode == "before" else "after")
                    clear(g)
                    s = ro.search_stats.copy()
                    w0, c0 = time.perf_counter(), time.thread_time()
                    r = g._decide_quiet(x)
                    t[mode].append(time.perf_counter() - w0)
                    c[mode].append(time.thread_time() - c0)
                    acts[mode] = act(r)
                    acts[mode + "_searches"] = {kk: ro.search_stats[kk] - s[kk] for kk in s}
                # the gate alone after a coherence-only decision (P5-36b t_beam2), before and after
                for mode in (("gate_after", "gate_before") if rep % 2 == 0 else ("gate_before", "gate_after")):
                    g.set_offer_gate(both[:1])
                    set_mode("after")
                    clear(g)
                    g._decide_quiet(x)  # as in a real decision (the LM guard decode fills the cache)
                    lp = g._last_lp
                    set_mode(mode[5:])  # same cache state in both modes (LM guard: the forward search is kept)
                    w0, c0 = time.perf_counter(), time.thread_time()
                    og.lm_beam_direction(lp, ro)
                    t[mode].append(time.perf_counter() - w0)
                    c[mode].append(time.thread_time() - c0)
            g.set_offer_gate(both)
            set_mode("after")
            clear(g)
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
                "extra_per_offer_median_s": {"before": med_extra("before"), "after": med_extra("after")},
                "extra_per_offer_cpu_median_s": {"before": med_extra("before", "cpu"), "after": med_extra("after", "cpu")},
                "gate_alone_median_s": {"before": med("gate_before"), "after": med("gate_after")},
                "gate_alone_cpu_median_s": {"before": med("gate_before", "cpu"), "after": med("gate_after", "cpu")},
                "searches_per_offer_decision": {
                    mode: sorted({json.dumps(r["actions"][mode + "_searches"]) for r in offers})
                    for mode in ("coh", "before", "after")},
                "actions_equal_before_after": all(r["actions"]["before"] == r["actions"]["after"] for r in rows)}
        summ["extra_ratio_after_before"] = round(summ["extra_per_offer_median_s"]["after"]
                                                 / summ["extra_per_offer_median_s"]["before"], 3)
        summ["gate_alone_ratio_after_before"] = round(summ["gate_alone_median_s"]["after"]
                                                      / summ["gate_alone_median_s"]["before"], 3)
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
        for mode in (MODES if n % 2 == 0 else MODES[::-1]):
            set_mode(mode)
            clear(g)
            rec[mode] = record(g, g._decide_quiet(x))
        d = {"key": list(key), **rec, "equal": rec["before"] == rec["after"]}
        fh.write(json.dumps(d) + "\n")
        fh.flush()
        done[key] = d
        if n % 50 == 0:
            log(f"sets {k}: {n + 1} / {len(items)} ({time.time() - t0:.0f} s)")
    fh.close()
    g.collect_offer_features = False
    set_mode("after")
    rows = [done[k2] for k2 in [(a, b, c) for a, b, c in items]]
    by = {}
    for r in rows:
        name = f"{r['key'][0]}:{r['key'][1]}"
        b = by.setdefault(name, {"n": 0, "equal": 0, "offers_before": 0, "offers_after": 0})
        b["n"] += 1
        b["equal"] += r["equal"]
        b["offers_before"] += r["before"]["action"] == "offer"
        b["offers_after"] += r["after"]["action"] == "offer"
    res = {"guard": k, "config_id": g.config_id, "offer_gate_id": OFFER_GATE_IDS[k], "n": len(rows),
           "n_equal": sum(r["equal"] for r in rows), "all_equal": all(r["equal"] for r in rows), "by_set": by,
           "compared": "action, shown candidates (digest), reason (digest), offer-gate reason (digest), every "
                       "offer-gate feature incl. lm_beam_direction (float bit pattern); old vs new LMBeam.push loop",
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
    set_mode(mode)
    clear(g)
    seq = []
    orig = g._decide_quiet

    def rec(*a, **kw):
        r = orig(*a, **kw)
        seq.append(record(g, r))
        return r

    g._decide_quiet = rec
    lp_val, lp_ts = load_lps("val", "real"), load_lps("val", "timeshuf")
    t0 = time.time()
    rc = ft.recheck_offer_control(g, lp_val, null_inputs=lp_ts)
    del g._decide_quiet
    rc.update(guard=k, mode=mode, config_id=g.config_id, offer_gate_id=OFFER_GATE_IDS[k],
              offer_gate=[x.to_dict() for x in g.offer_gates], seconds=round(time.time() - t0, 1), decisions=seq)
    save_json(rc, out)
    log(f"recheck {k} {mode}: passed {rc['passed']}: "
        f"{[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}, real {rc['real']} ({rc['seconds']} s)")


def stage_compare(m, G) -> None:
    res = {}
    for k in CFG:
        a = json.loads((OWN / f"recheck-{k}-before.json").read_text(encoding="utf-8"))
        b = json.loads((OWN / f"recheck-{k}-after.json").read_text(encoding="utf-8"))
        da, db = a.pop("decisions"), b.pop("decisions")
        strip = ("seconds", "mode")
        same_summary = {x: v for x, v in a.items() if x not in strip} == {x: v for x, v in b.items() if x not in strip}
        res[k] = {"n_decisions": [len(da), len(db)], "n_equal_in_order": sum(x == y for x, y in zip(da, db)),
                  "decisions_equal": da == db, "summary_equal": same_summary,
                  "n_offer_before": sum(d["action"] == "offer" for d in da),
                  "n_offer_after": sum(d["action"] == "offer" for d in db),
                  "controls": [(c["name"], c["n_offer"], c["n"]) for c in b["controls"]], "real": b["real"],
                  "passed": b["passed"], "config_id": b["config_id"], "offer_gate_id": b["offer_gate_id"],
                  "seconds": {"before": a["seconds"], "after": b["seconds"]}}
        log(f"compare {k}: {res[k]}")
    save_json({"compared": "every _decide_quiet call of recheck_offer_control (real LTT, uniform, frame-shuffled, "
                           "time-shuffled), in order: action, shown candidates, reason, offer-gate reason (digests); "
                           "and the re-check result dict; old vs new LMBeam.push loop", **res},
              RES / "identity-recheck.json")
    bench = json.loads((RES / "bench.json").read_text(encoding="utf-8"))
    sets = {k: json.loads((RES / f"identity-sets-{k}.json").read_text(encoding="utf-8")) for k in CFG}
    save_json({"bench": {k: v["summary"] for k, v in bench["guards"].items()},
               "identity_sets": {k: {x: v[x] for x in ("config_id", "offer_gate_id", "n", "n_equal", "all_equal",
                                                       "by_set")} for k, v in sets.items()},
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
