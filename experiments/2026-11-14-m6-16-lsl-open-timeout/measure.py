"""M6-16: what the LSL inlet ``open_timeout`` costs, and a shorter default.

Three parts, real LSL on this PC (pylsl 1.18.6), unique stream names (``test-collector-m616-*``):

A. Healthy open: a live outlet; time of ``resolve()``, of the inlet open (``info()`` + ``open_stream()``)
   and of the first ``time_correction()``. 30 trials.
B. Stale open: resolve a live outlet, destroy it, then open the inlet with the old info. The open waits
   for the full ``open_timeout`` and fails. One trial per value.
C. Producer restart (the M6-14 part B set-up, thread mode): a 25 Hz NTS outlet goes away and comes back
   after 1.5 s with the same ``source_id``. Time from the stop to the reconnect, and the max loop step.
   First run (results/open_timeout-run1.json): ``reconnect_resolver = "oneshot"`` (the M6-14 path) with
   ``open_timeout_s`` 5.0, 2.0, 1.0, 0.5. Second run: ``oneshot`` vs ``continuous`` (M6-16) at 5.0 and 1.0.
   Three repeats per cell.

Output: results/open_timeout.json and tables on stdout. No participant data.
Run: python -m fidetype.utils.isolation run --class background --threads 4 -- \
     .venv\\Scripts\\python.exe experiments\\2026-11-14-m6-16-lsl-open-timeout\\measure.py
"""

from __future__ import annotations

import json
import platform
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import LSLMapping, LSLTrustRunner
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamingTrustLayer
from fidetype.trust.testing import greedy_nbest

OUT = Path(__file__).parent / "results"
CFG = FrozenTrustConfig(name="m6-16").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
SRATE = 25.0
VOCAB = ["<b>", "a", "b"]
HEADER = {"spec_version": "0.1", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0, "source": "m6-16",
          "frame_period": 1 / SRATE, "meta": {}}
ROW = list(np.log([0.9, 0.05, 0.05]))
POLL = 0.02
VALUES = (5.0, 2.0, 1.0, 0.5)
CELLS = (("oneshot", 5.0), ("oneshot", 1.0), ("continuous", 5.0), ("continuous", 1.0))


def pct(xs: list[float]) -> dict:
    a = np.asarray(xs) * 1e3
    return {"n": int(a.size), "p50_ms": float(np.percentile(a, 50)), "p95_ms": float(np.percentile(a, 95)),
            "max_ms": float(a.max())}


def make_outlet(pl, name, sid):
    info = pl.StreamInfo(name, "NTS", 3, SRATE, "float32", sid)
    d = info.desc().append_child("fidetype")
    d.append_child_value("nts_header", json.dumps(HEADER))
    d.append_child_value("values", "log_probs")
    d.append_child_value("binding", L.BINDING_VERSION)
    ch = info.desc().append_child("channels")
    for v in VOCAB:
        c = ch.append_child("channel")
        c.append_child_value("label", v)
        c.append_child_value("unit", "log_prob")
    return pl.StreamOutlet(info)


def part_a(trials: int = 30) -> dict:
    pl = L.require_pylsl()
    res, opn, tc = [], [], []
    for _ in range(trials):
        name = f"test-collector-m616-a-{uuid.uuid4().hex[:8]}"
        out = make_outlet(pl, name, name + "-sid")
        t0 = time.perf_counter()
        info = L.resolve(name=name, timeout=10.0)
        t1 = time.perf_counter()
        inlet = L.PylslInlet(info, open_timeout=5.0)
        t2 = time.perf_counter()
        inlet.time_correction(5.0)
        t3 = time.perf_counter()
        res.append(t1 - t0)
        opn.append(t2 - t1)
        tc.append(t3 - t2)
        inlet.close()
        del inlet, out
    return {"part": "A-healthy", "resolve": pct(res), "open": pct(opn), "first_time_correction": pct(tc)}


def part_b() -> list[dict]:
    pl = L.require_pylsl()
    rows = []
    for ot in VALUES:
        name = f"test-collector-m616-b-{uuid.uuid4().hex[:8]}"
        out = make_outlet(pl, name, name + "-sid")
        info = L.resolve(name=name, timeout=10.0)
        del out
        time.sleep(0.2)
        t0 = time.perf_counter()
        err = None
        try:
            L.PylslInlet(info, open_timeout=ot).close()
        except Exception as e:  # noqa: BLE001 - the expected outcome
            err = type(e).__name__
        rows.append({"part": "B-stale", "open_timeout_s": ot, "wait_s": time.perf_counter() - t0, "error": err})
    return rows


def part_c(ot: float, resolver: str = "continuous", outage: float = 1.5) -> dict:
    pl = L.require_pylsl()
    name = f"test-collector-m616-c-{uuid.uuid4().hex[:8]}"
    sid = f"{name}-sid"
    state = {"outlet": make_outlet(pl, name, sid), "run": True}
    lock = threading.Lock()

    def produce():
        while state["run"]:
            with lock:
                if state["outlet"] is not None:
                    state["outlet"].push_sample(ROW)
            time.sleep(1 / SRATE)

    threading.Thread(target=produce, daemon=True).start()
    t_open = time.perf_counter()
    src = L.open_source(name=name, timeout=10.0, events="none",
                        mapping=LSLMapping(reconnect_timeout_s=30.0, open_timeout_s=ot,
                                           reconnect_resolver=resolver))
    startup = time.perf_counter() - t_open
    runner = LSLTrustRunner(StreamingTrustLayer(CFG, decode_fn=greedy_nbest), src)
    st: list[float] = []
    t_kill = t_rec = None
    t_end = time.monotonic() + 40.0
    try:
        while time.monotonic() < t_end:
            t0 = time.perf_counter()
            runner.step(POLL)
            dt = time.perf_counter() - t0
            if t_kill is not None and t_rec is None:
                st.append(dt)
            if t_kill is not None and t_rec is None and src.stats.reconnects:
                t_rec = time.perf_counter()
            if t_kill is None and src.stats.frames > 50:
                with lock:
                    state["outlet"] = None
                t_kill = time.perf_counter()
                threading.Timer(outage, lambda: state.__setitem__("outlet", make_outlet(pl, name, sid))).start()
            if t_rec is not None and time.perf_counter() - t_rec > 0.5:
                break
    finally:
        state["run"] = False
        src.close()
    attempts = getattr(src.primary.reopen, "tries", None)
    return {"part": "C-restart", "resolver": resolver, "open_timeout_s": ot, "outage_s": outage,
            "startup_s": startup,
            "reconnect_after_kill_s": None if t_rec is None or t_kill is None else t_rec - t_kill,
            "lost": src.stats.lost, "reconnects": src.stats.reconnects, "aborted": runner.summary.aborted_utterances,
            "max_step_ms": max(st) * 1e3 if st else None, "attempts": attempts}


def main() -> int:
    if not L.pylsl_available():
        print("pylsl not available")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = [part_a()]
    print(json.dumps(rows[-1]), flush=True)
    for r in part_b():
        rows.append(r)
        print(json.dumps(r), flush=True)
    for rep in range(3):
        for resolver, ot in CELLS:
            r = part_c(ot, resolver)
            r["repeat"] = rep
            rows.append(r)
            print(json.dumps(r), flush=True)
    meta = {"python": sys.version.split()[0], "platform": platform.platform(), "poll_timeout_s": POLL,
            "cpu_class": "background", "pylsl": getattr(L.require_pylsl(), "__version__", None)}
    (OUT / "open_timeout.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1), encoding="utf-8")
    print()
    print("| resolver | open_timeout_s | reconnect after stop (s), 3 runs | max loop step (ms) | startup (s) |")
    print("|---|---|---|---|---|")
    for resolver, ot in CELLS:
        cs = [r for r in rows if r["part"] == "C-restart" and r["open_timeout_s"] == ot
              and r["resolver"] == resolver]
        rec = ", ".join(f"{r['reconnect_after_kill_s']:.2f}" if r["reconnect_after_kill_s"] else "-" for r in cs)
        ms = ", ".join(f"{r['max_step_ms']:.1f}" if r["max_step_ms"] else "-" for r in cs)
        su = ", ".join(f"{r['startup_s']:.2f}" for r in cs)
        print(f"| {resolver} | {ot} | {rec} | {ms} | {su} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
