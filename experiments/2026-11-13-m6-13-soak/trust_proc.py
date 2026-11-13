"""M6-13 soak: the trust process (LSL EEG -> toy signal decoder -> streaming trust layer -> decisions on LSL).

It is the live consumer of ``fidetype lsl run`` with the M4-08..M4-10 settings:

- ``StreamingTrustLayer(incremental=...)``: the demo decoder (segment beam 8 + char 5-gram LM) runs
  incrementally, one closed peak at a time (exact = batch, M4-08);
- the GC rule of M4-09: ``gc.collect(); gc.freeze()`` after setup, automatic GC off, one timed
  ``gc.collect()`` at each idle point (after a final decision or an aborted utterance);
- a **shadow** incremental decoder on the same frames: CTC prefix beam (16) + ``CharNgramLM`` 6-gram
  with an LRU memo bound (M4-10) and a 1 ms prewarm budget (M4-09). It makes no decision. It exists to
  run the bounded caches for hours. Every ``--exact-every`` final utterances its incremental result is
  compared with the batch decode of the same frames.

The toy signal decoder alternates between ``flat`` and ``features`` at each stream loss (bridge restart).
Both carry no text information, so every COMMIT is a wrong commit.

Every ``--window-s`` seconds one metrics line goes to ``metrics-trust.jsonl`` (flushed + fsynced).
Stop: create the ``--stop-file``. CPU only.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import JsonlWriter, LogHist, log, now_iso, proc_stats, pstats  # noqa: E402

ROOT = HERE.parents[1]
CONFIG = ROOT / "src" / "fidetype" / "demo" / "trust-config-demo.json"


class SwitchingToy:
    """A SignalDecoder that delegates to one of two toy decoders (flat / features); ``switch()`` swaps them."""

    def __init__(self, srate: float, n_ch: int, seed: int = 0) -> None:
        from fidetype.decoders.toy_signal import toy_signal_decoder

        self.decs = {m: toy_signal_decoder(m, srate, n_ch, seed=seed) for m in ("features", "flat")}
        self.mode = "features"

    @property
    def header(self) -> dict[str, Any]:
        return self.decs[self.mode].header

    def switch(self) -> None:
        self.decs[self.mode].reset()
        self.mode = "flat" if self.mode == "features" else "features"
        self.decs[self.mode].reset()

    def process(self, samples: np.ndarray, times: np.ndarray):
        return self.decs[self.mode].process(samples, times)


class Shadow:
    """The shadow CTC prefix beam + bounded CharNgramLM (see the module docstring)."""

    def __init__(self, lm_bound: int, exact_every: int) -> None:
        from fidetype.demo import lm_phrases
        from fidetype.lm import CharNgramLM
        from fidetype.trust.incremental import CTCBeamSpec

        self.lm = CharNgramLM(6, cache_size=lm_bound).train(lm_phrases())
        self.spec = CTCBeamSpec(dict(beam=16, n_best=10), lm=self.lm, prewarm_every=5, prewarm_budget_s=0.001)
        self.exact_every = exact_every
        self.header: dict[str, Any] | None = None
        self.inc = None
        self.rows: list[np.ndarray] = []
        self.times: list[float] = []
        self.n_final = 0
        self.exact_checked = 0
        self.exact_mismatch = 0
        self.mismatch_examples: list[dict[str, Any]] = []

    def on_header(self, h: dict[str, Any]) -> None:
        self.header = h
        self.drop()

    def drop(self) -> None:
        self.inc, self.rows, self.times = None, [], []

    def push(self, ev: dict[str, Any]) -> float:
        if self.header is None:
            return 0.0
        row = np.asarray(ev["log_probs"], dtype=np.float64)
        t0 = time.perf_counter()
        if self.inc is None:
            self.inc = self.spec.factory(self.header)
        self.inc.push_frames(row[None, :])
        dt = time.perf_counter() - t0
        self.rows.append(row)
        self.times.append(float(ev["t"]))
        return dt

    def _stream(self):
        from fidetype.streams import NeuralTextStream

        h = self.header or {}
        return NeuralTextStream(log_probs=np.stack(self.rows), frame_times=np.asarray(self.times), vocab=h["vocab"],
                                blank_id=h["blank_id"], source="soak-shadow", meta={},
                                frame_period=h.get("frame_period"))

    def finalize(self) -> float | None:
        """Finish the utterance; return the finalize time (s) or None (no frames)."""
        if self.inc is None or len(self.rows) < 2:
            self.drop()
            return None
        st = self._stream()
        t0 = time.perf_counter()
        nb = self.inc.finalize(st)
        dt = time.perf_counter() - t0
        self.n_final += 1
        if self.exact_every and self.n_final % self.exact_every == 0:
            ref = self.spec.decode_fn(st)
            a = [(c.text, c.score) for c in nb.candidates]
            b = [(c.text, c.score) for c in ref.candidates]
            self.exact_checked += 1
            if a != b:
                self.exact_mismatch += 1
                if len(self.mismatch_examples) < 5:
                    self.mismatch_examples.append({"n_final": self.n_final, "frames": len(self.rows),
                                                   "inc_top": a[:1], "batch_top": b[:1]})
        self.drop()
        return dt


class Window:
    def __init__(self) -> None:
        self.push: list[float] = []
        self.eou: list[float] = []
        self.e2e: list[float] = []
        self.gc: list[float] = []
        self.sh_push: list[float] = []
        self.sh_end: list[float] = []
        self.step: list[float] = []
        self.decisions = 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--stream-name", default="soak.eeg")
    ap.add_argument("--outlet-name", default="soak.decisions")
    ap.add_argument("--window-s", type=float, default=120.0)
    ap.add_argument("--shadow-lm-bound", type=int, default=20000)
    ap.add_argument("--exact-every", type=int, default=20)
    ap.add_argument("--reconnect-timeout", type=float, default=900.0)
    ap.add_argument("--epoch", type=int, default=0, help="restart counter (set by the supervisor)")
    a = ap.parse_args()

    from fidetype.adapters.lsl import DecisionOutlet, LSLMapping, LSLStreamLost, LSLTrustRunner, open_source
    from fidetype.demo import build_decoder
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.incremental import IncrementalReferenceDecoder
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    res = Path(a.results_dir)
    out = JsonlWriter(res / "metrics-trust.jsonl")
    stop = Path(a.stop_file)
    t_start = time.monotonic()
    m0 = proc_stats()

    cfg = FrozenTrustConfig.load(CONFIG)
    dec = build_decoder()
    layer = StreamingTrustLayer(cfg, decode_fn=dec, incremental=IncrementalReferenceDecoder.factory_for(dec),
                                streaming=StreamingConfig(max_attempts=1))
    shadow = Shadow(a.shadow_lm_bound, a.exact_every)
    outlet = DecisionOutlet(a.outlet_name, config_id=cfg.config_id)
    log(f"trust: outlet {a.outlet_name} up; waiting for the consumer")
    if not outlet.outlet.wait_for_consumers(120.0):
        log("trust: no consumer after 120 s; continuing")

    toy: dict[str, SwitchingToy] = {}

    def sig(info):
        toy["d"] = SwitchingToy(info.nominal_srate, info.channel_count)
        return toy["d"]

    mapping = LSLMapping(reconnect_timeout_s=a.reconnect_timeout)
    src = open_source(a.stream_name, None, None, "auto", mapping, signal_decoder=sig, timeout=300.0, log=log)
    sw = toy["d"]

    W = Window()
    H = {k: LogHist() for k in ("push", "eou", "e2e", "gc", "sh_push", "sh_end", "step")}
    C: dict[str, Any] = {"emitted": 0, "final": 0, "last_seq": None, "exceptions": 0, "forced_gc": 0,
                         "switches": 0, "actions": {m: {"COMMIT": 0, "OFFER": 0, "ABSTAIN": 0} for m in ("features", "flat")},
                         "reasons": {}, "first_exception": None}
    state = {"final_in_step": False}

    def sink(ev: dict[str, Any]) -> None:
        C["emitted"] += 1
        C["last_seq"] = ev.get("seq")
        W.decisions += 1
        if ev.get("is_final"):
            C["final"] += 1
            state["final_in_step"] = True
            act = ev.get("action")
            C["actions"][sw.mode][act] = C["actions"][sw.mode].get(act, 0) + 1
            r = str(ev.get("reason", ""))
            r = r.split(" ")[0] + " " + r.split(" ")[1] if r.count(" ") >= 1 else r
            C["reasons"][r] = C["reasons"].get(r, 0) + 1
            lat = (ev.get("lsl") or {}).get("e2e_latency_s")
            if isinstance(lat, (int, float)):
                W.e2e.append(lat)
                H["e2e"].add(lat)

    runner = LSLTrustRunner(layer, src, session_id="lsl", sink=sink, outlet=outlet, include_text=True, log=log)
    orig_push = layer.push

    def timed_push(ev, session_id="default"):
        typ = ev.get("type") if isinstance(ev, dict) else None
        t0 = time.perf_counter()
        ds = orig_push(ev, session_id)
        dt = time.perf_counter() - t0
        if typ == "frame":
            W.push.append(dt)
            H["push"].add(dt)
            sp = shadow.push(ev)
            W.sh_push.append(sp)
            H["sh_push"].add(sp)
        elif typ == "header":
            shadow.on_header(ev)
        if any(d.final for d in ds):
            if typ != "frame":
                W.eou.append(dt)
                H["eou"].add(dt)
            se = shadow.finalize()
            if se is not None:
                W.sh_end.append(se)
                H["sh_end"].add(se)
        return ds

    layer.push = timed_push  # type: ignore[method-assign]

    gc.collect()
    gc.freeze()
    gc.disable()
    m1 = proc_stats()
    log(f"trust: setup done; RSS {m1.get('rss_mb', 0):.0f} MB (start {m0.get('rss_mb', 0):.0f} MB); GC frozen + off")

    def collect() -> None:
        t0 = time.perf_counter()
        gc.collect()
        dt = time.perf_counter() - t0
        W.gc.append(dt)
        H["gc"].add(dt)
        state["last_gc"] = time.monotonic()

    state["last_gc"] = time.monotonic()
    t_win = time.monotonic()
    win_idx = 0
    lost_seen = False
    aborted_prev = 0
    last_stop_check = 0.0
    reason = "?"

    def write_window(final: bool = False) -> None:
        nonlocal W, t_win, win_idx
        now = time.monotonic()
        st = src.stats
        tl = list(st.transport_latency_s)
        st.transport_latency_s.clear()
        r = src.provenance()
        try:
            sess = layer.session_state("lsl")
        except KeyError:
            sess = {}
        rec = {
            "kind": "final" if final else "window", "epoch": a.epoch, "window": win_idx, "t_iso": now_iso(),
            "t_s": now - t_start, "window_s": now - t_win, **proc_stats(),
            "push_ms": pstats(W.push), "eou_ms": pstats(W.eou), "e2e_ms": pstats(W.e2e), "idle_gc_ms": pstats(W.gc),
            "shadow_push_ms": pstats(W.sh_push), "shadow_end_ms": pstats(W.sh_end), "step_ms": pstats(W.step),
            "transport_ms": pstats(tl), "decisions_window": W.decisions,
            "counts": {k: v for k, v in C.items() if k not in ("first_exception",)},
            "mode": sw.mode,
            "source": {k: v for k, v in st.as_dict().items() if k != "transport_latency_ms"},
            "clock": {k: r.get(k) for k in ("time_correction_s", "updates", "failures", "spread_s")},
            "runner": {"aborted": runner.summary.aborted_utterances, "rejected": runner.summary.rejected_events,
                       "events": runner.summary.events},
            "session": {k: sess.get(k) for k in ("buffered_frames", "utterance", "decisions", "pending_feedback",
                                                 "dropped_frames", "aborted_utterances")},
            "caches": {"refcharlm_entries": len(dec.lm._cache), "shadow_lm_entries": len(shadow.lm._cache),
                       "shadow_lm_bound": shadow.lm._cache.maxsize},
            "shadow": {"finals": shadow.n_final, "exact_checked": shadow.exact_checked,
                       "exact_mismatch": shadow.exact_mismatch},
            "gc": {"counts": gc.get_count(), "frozen": gc.get_freeze_count(), "garbage": len(gc.garbage)},
        }
        if final:
            rec["whole_run_ms"] = {k: h.summary_ms() for k, h in H.items()}
            rec["shadow_mismatch_examples"] = shadow.mismatch_examples
            rec["first_exception"] = C["first_exception"]
            rec["stop_reason"] = reason
        out.write(rec)
        W = Window()
        t_win = now
        win_idx += 1

    try:
        while True:
            now = time.monotonic()
            if now - last_stop_check >= 1.0:
                last_stop_check = now
                if stop.exists():
                    reason = "stop file"
                    break
            t0 = time.perf_counter()
            state["final_in_step"] = False
            try:
                runner.step(0.05)
            except LSLStreamLost:
                raise
            except Exception as e:  # noqa: BLE001 - counted; the soak criterion is 0
                C["exceptions"] += 1
                if C["first_exception"] is None:
                    C["first_exception"] = traceback.format_exc()
                log(f"trust: EXCEPTION {type(e).__name__}: {e}")
            dt = time.perf_counter() - t0
            W.step.append(dt)
            H["step"].add(dt)
            # idle points of the GC rule
            ab = runner.summary.aborted_utterances
            if state["final_in_step"] or ab != aborted_prev:
                collect()
            elif time.monotonic() - state["last_gc"] > 60.0 and not runner._pending():
                C["forced_gc"] += 1
                collect()
            if ab != aborted_prev:
                shadow.drop()
            aborted_prev = ab
            # switch the toy mode once per primary-stream loss
            lost = src.primary.lost_since is not None
            if lost and not lost_seen:
                sw.switch()
                C["switches"] += 1
                shadow.drop()
                log(f"trust: primary stream lost; toy mode -> {sw.mode}")
            lost_seen = lost
            if time.monotonic() - t_win >= a.window_s:
                write_window()
    except LSLStreamLost as e:
        reason = f"stream lost: {e}"
        log(f"trust: {reason}")
        C["first_exception"] = C["first_exception"] or traceback.format_exc()
        write_window(final=True)
        src.close()
        return 4
    except KeyboardInterrupt:
        reason = "interrupted"
    runner.finish()
    runner._abort("soak stop")
    write_window(final=True)
    src.close()
    log(f"trust: stop ({reason}); {C['final']} final decisions, {C['exceptions']} exceptions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
