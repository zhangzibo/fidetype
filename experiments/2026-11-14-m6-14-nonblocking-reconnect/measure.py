"""M6-14: loop stall during an LSL reconnect, before (inline) vs after (thread).

Two parts:

A. Fake inlets, a fake resolver that sleeps D seconds (D = 0.5, 2, 6).
   The runner steps with poll_timeout 0.02 s. We record the duration of
   every ``runner.step()`` while the primary is lost.
B. Real LSL on this PC (pylsl 1.18.6): a 25 Hz NTS outlet goes away
   and comes back after an outage (1.5 s and 4 s) with the same
   source_id. Same stall record. Three repeats per setting.

Output: results/stall.json and a table on stdout. No participant data.
Run: python -m fidetype.utils.isolation run --class background -- \
     .venv\\Scripts\\python.exe experiments\\2026-11-14-m6-14-nonblocking-reconnect\\measure.py
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
from fidetype.adapters.lsl import LSLEventSource, LSLMapping, LSLStreamInfo, LSLStreamLost, LSLTrustRunner
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamingTrustLayer
from fidetype.trust.testing import greedy_nbest

OUT = Path(__file__).parent / "results"
CFG = FrozenTrustConfig(name="m6-14").with_policy(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)
SRATE = 25.0
VOCAB = ["<b>", "a", "b"]
HEADER = {"spec_version": "0.1", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0, "source": "m6-14",
          "frame_period": 1 / SRATE, "meta": {}}
ROW = list(np.log([0.9, 0.05, 0.05]))
POLL = 0.02


def stats(xs: list[float]) -> dict:
    a = np.asarray(xs) * 1e3
    return {"n": int(a.size), "p50_ms": float(np.percentile(a, 50)), "p99_ms": float(np.percentile(a, 99)),
            "max_ms": float(a.max())}


class FakeInlet:
    def __init__(self, script):
        self._info = LSLStreamInfo("f", "NTS", 3, SRATE, "float32", "f1", "u", "hostA", channel_labels=VOCAB,
                                   fidetype={"nts_header": json.dumps(HEADER)})
        self.script = list(script)

    def info(self):
        return self._info

    def pull_chunk(self, timeout, max_samples):
        if not self.script:
            time.sleep(timeout)
            return [], []
        it = self.script.pop(0)
        if it == "lost":
            raise LSLStreamLost("fake loss")
        return it

    def time_correction(self, timeout):
        return 0.0

    def close(self):
        pass


def part_a(mode: str, delay: float) -> dict:
    primary = FakeInlet([([ROW] * 10, [100.0 + i / SRATE for i in range(10)]), "lost"])
    fresh = FakeInlet([([ROW] * 10, [200.0 + i / SRATE for i in range(10)])])

    def reopen():
        time.sleep(delay)
        return fresh

    src = LSLEventSource(primary, mapping=LSLMapping(reconnect_mode=mode), clock=time.perf_counter,
                         reopen_primary=reopen)
    runner = LSLTrustRunner(StreamingTrustLayer(CFG, decode_fn=greedy_nbest), src)
    st: list[float] = []
    t_lost = None
    while src.stats.reconnects == 0:
        lost = src.primary.lost_since is not None
        if lost and t_lost is None:
            t_lost = time.perf_counter()
        t0 = time.perf_counter()
        runner.step(POLL)
        if lost:
            st.append(time.perf_counter() - t0)
    rec = time.perf_counter() - (t_lost or 0)
    src.close()
    return {"part": "A-fake", "mode": mode, "resolve_delay_s": delay, "reconnect_s": rec,
            "aborted": runner.summary.aborted_utterances, **stats(st)}


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


def part_b(mode: str, outage: float) -> dict:
    pl = L.require_pylsl()
    name = f"fidetype-m614-{uuid.uuid4().hex[:8]}"
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
    src = L.open_source(name=name, timeout=10.0, events="none",
                        mapping=LSLMapping(reconnect_mode=mode, reconnect_timeout_s=30.0))
    runner = LSLTrustRunner(StreamingTrustLayer(CFG, decode_fn=greedy_nbest), src)
    st: list[float] = []
    all_steps: list[float] = []
    t_kill = t_lost = t_rec = None
    rec_step = None
    t_end = time.monotonic() + 40.0
    try:
        while time.monotonic() < t_end:
            t0 = time.perf_counter()
            runner.step(POLL)
            dt = time.perf_counter() - t0
            all_steps.append(dt)
            if t_kill is not None and t_rec is None:
                st.append(dt)  # from the producer stop until the reconnect (both included)
            if t_lost is None and src.primary.lost_since is not None:
                t_lost = time.perf_counter()  # the step that saw the loss has ended
            if t_lost is not None and t_rec is None and src.stats.reconnects:
                t_rec = time.perf_counter()
                rec_step = dt
            if t_kill is None and src.stats.frames > 50:
                with lock:
                    state["outlet"] = None
                t_kill = time.perf_counter()
                threading.Timer(outage, lambda: state.__setitem__("outlet", make_outlet(pl, name, sid))).start()
            if t_rec is not None and time.perf_counter() - t_rec > 1.0:
                break
    finally:
        state["run"] = False
        src.close()
    return {"part": "B-real-lsl", "mode": mode, "outage_s": outage,
            "detect_s": None if t_lost is None or t_kill is None else t_lost - t_kill,
            "reconnect_after_kill_s": None if t_rec is None or t_kill is None else t_rec - t_kill,
            "lost": src.stats.lost, "reconnects": src.stats.reconnects, **stats(st),
            "reconnect_step_ms": None if rec_step is None else rec_step * 1e3,
            "first_step_ms": float(all_steps[0] * 1e3)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for delay in (0.5, 2.0, 6.0):
        for mode in ("inline", "thread"):
            rows.append(part_a(mode, delay))
            print(json.dumps(rows[-1]), flush=True)
    if L.pylsl_available():
        for outage in (1.5, 4.0):
            for rep in range(3):
                for mode in ("inline", "thread"):
                    r = part_b(mode, outage)
                    r["repeat"] = rep
                    rows.append(r)
                    print(json.dumps(r), flush=True)
    meta = {"python": sys.version.split()[0], "platform": platform.platform(), "poll_timeout_s": POLL,
            "cpu_class": sys.argv[1] if len(sys.argv) > 1 else "background",
            "pylsl": getattr(L.require_pylsl(), "__version__", None) if L.pylsl_available() else None}
    (OUT / "stall.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1), encoding="utf-8")
    print("\n| part | mode | setting | n steps | p50 ms | p99 ms | max ms | reconnect s |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        setting = f"resolve {r['resolve_delay_s']} s" if r["part"] == "A-fake" else f"outage {r['outage_s']} s #{r['repeat']}"
        recs = r.get("reconnect_s", r.get("reconnect_after_kill_s"))
        print(f"| {r['part']} | {r['mode']} | {setting} | {r['n']} | {r['p50_ms']:.1f} | {r['p99_ms']:.1f} | "
              f"{r['max_ms']:.1f} | {r.get('reconnect_step_ms') or float('nan'):.1f} | "
              f"{recs if recs is None else round(recs, 2)} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
