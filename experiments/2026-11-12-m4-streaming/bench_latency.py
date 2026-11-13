"""M4-03: latency, memory and batch equivalence of the streaming trust layer.

Synthetic simulator streams only (no participant data). CPU only.

Measures:
- per-event cost of ``push`` for frame events (frames route),
- the latency of the final decision at the end of an utterance (decode +
  trust core), with the reference beam decoder and the CTC greedy decoder,
- the per-event cost on the hypothesis route (trust core only),
- peak buffered bytes per session and the tracemalloc peak of one session,
- 64 interleaved sessions (throughput),
- equivalence: every final decision vs the batch path (TrustPipeline).

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-m4-streaming/bench_latency.py
"""

from __future__ import annotations

import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.conformance.io import write_jsonl  # noqa: E402
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.streams.corpus import sentences  # noqa: E402
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events  # noqa: E402
from fidetype.trust.testing import RefCharLM, ReferenceDecoder, greedy_nbest  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
TMP = OUT / "_streams"  # git-ignored scratch (synthetic)
GRID = {"commit_p": (0.3, 0.5, 0.8), "commit_max_risk": (0.4, 1.0), "offer_max_k": (0, 3),
        "abstain_risk": (0.45, 1.01), "final_fallback": ("offer",)}
N_TEST = 100


def pct(x) -> dict:
    a = np.asarray(x, dtype=np.float64) * 1e3  # ms
    return {"n": int(a.size), "p50_ms": float(np.percentile(a, 50)), "p95_ms": float(np.percentile(a, 95)),
            "p99_ms": float(np.percentile(a, 99)), "max_ms": float(a.max()), "mean_ms": float(a.mean())}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    sents = sentences(900, seed=5)
    lm = RefCharLM(5).fit(sents[300:])
    beam = ReferenceDecoder(lm, beam=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=3)
    items = [Item(sim.simulate(s, seed=17 * i).stream, s) for i, s in enumerate(sents[:80 + N_TEST])]
    cal, val, test = items[:30], items[30:80], items[80:]
    pipe = TrustPipeline(beam, HarnessConfig(grid=GRID, max_wrong_commit=0.1), {})
    pipe.fit(cal, val)
    cfg = FrozenTrustConfig.from_pipeline(pipe, "m4-bench-synthetic")
    cfg.save(OUT / "trust-config-synthetic.json")
    files = []
    for i, it in enumerate(test):
        p = TMP / f"s{i:03d}.jsonl"
        write_jsonl(it.stream(0), p)
        files.append(p)
    events = [list(iter_events(p)) for p in files]
    n_frames = [it.stream(0).n_frames for it in test]
    res: dict = {"description": __doc__.strip().splitlines()[0], "n_streams": len(test),
                 "frames_per_stream": {"mean": float(np.mean(n_frames)), "max": int(max(n_frames))},
                 "frame_period_s": test[0].stream(0).frame_period, "vocab_size": test[0].stream(0).vocab_size,
                 "machine": {"python": platform.python_version(), "processor": platform.processor(),
                             "system": platform.system()},
                 "config_id": cfg.config_id}

    for name, dec in (("beam", beam), ("greedy", greedy_nbest)):
        layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=1))
        frame_t, final_t, peak_bytes, decisions = [], [], 0, []
        for i, evs in enumerate(events):
            sid = f"s{i}"
            for ev in evs[:-1]:
                t0 = time.perf_counter()
                layer.push(ev, sid)
                dt = time.perf_counter() - t0
                if ev["type"] == "frame":
                    frame_t.append(dt)
            peak_bytes = max(peak_bytes, layer.session_state(sid)["buffered_bytes"])
            t0 = time.perf_counter()
            out = layer.push(evs[-1], sid)
            final_t.append(time.perf_counter() - t0)
            decisions.append(out[0])
            layer.close(sid)
        # Equivalence with the batch path on the same files.
        bp = pipe if dec is beam else _with_decoder(pipe, dec)
        same = 0
        for it_file, d in zip(files, decisions):
            from fidetype.conformance.io import load_stream

            an = bp.analyze(bp.decode(Item(load_stream(it_file).stream, ""), 0))
            bd = bp.policy.decide(an.inputs, final_attempt=True)
            same += int(bd == d.decision and an.inputs == d.inputs)
        acts: dict[str, int] = {}
        for d in decisions:
            acts[d.action.value] = acts.get(d.action.value, 0) + 1
        res[f"frames_route_{name}"] = {
            "push_frame": pct(frame_t), "final_decision": pct(final_t),
            "peak_buffered_bytes_per_session": peak_bytes,
            "equal_to_batch": f"{same}/{len(decisions)}", "actions": acts,
        }

    # Hypothesis route: the decoder sends n-best lists; the layer runs the trust core only.
    layer = StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1))
    hyp_t, same, n = [], 0, 0
    from fidetype.trust.streaming import nbest_from_hypothesis

    for i, it in enumerate(test):
        nb = beam(pipe.frame_scaler.transform_stream(it.stream(0)))
        items_ = [{"text": c.text, "score": c.score, "char_confidences": list(c.char_confidences)} for c in nb.candidates]
        evs = [{"type": "header", "spec_version": "0.1", "vocab": list(it.stream(0).vocab), "vocab_type": "char",
                "blank_id": 0, "source": "bench", "meta": {}}]
        for k in range(1, 4):  # growing partial hypotheses, then the final one
            evs.append({"type": "hypothesis", "id": f"h{k}", "is_final": False, "score_semantics": "none",
                        "nbest": items_[: max(1, len(items_) * k // 4)]})
        evs.append({"type": "hypothesis", "id": "hf", "is_final": True, "score_semantics": "none", "nbest": items_})
        sid = f"h{i}"
        for ev in evs:
            t0 = time.perf_counter()
            out = layer.push(ev, sid)
            if ev["type"] == "hypothesis":
                hyp_t.append(time.perf_counter() - t0)
        an = pipe.analyze(nbest_from_hypothesis(evs[-1]))
        same += int(pipe.policy.decide(an.inputs, final_attempt=True) == out[-1].decision)
        n += 1
        layer.close(sid)
    res["hypothesis_route"] = {"push_hypothesis": pct(hyp_t), "equal_to_batch": f"{same}/{n}"}

    # 64 interleaved sessions, greedy decoder, plus the memory peak of the run.
    layer = StreamingTrustLayer(cfg, decode_fn=greedy_nbest, streaming=StreamingConfig(max_attempts=1))
    tracemalloc.start()
    t0 = time.perf_counter()
    n_ev = 0
    ses = events[:64]
    for k in range(max(map(len, ses))):
        for i, evs in enumerate(ses):
            if k < len(evs):
                layer.push(evs[k], f"m{i}")
                n_ev += 1
    wall = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    res["interleaved_64_sessions_greedy"] = {"events": n_ev, "wall_s": wall, "events_per_s": n_ev / wall,
                                             "tracemalloc_peak_bytes": peak}
    (OUT / "latency.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    for p in TMP.iterdir():
        p.unlink()
    TMP.rmdir()
    write_md(res)
    print(json.dumps(res, indent=2))


def _with_decoder(pipe, dec):
    import copy

    bp = copy.copy(pipe)
    bp.decode_fn, bp.decode_cache = dec, {}
    return bp


def write_md(r: dict) -> None:
    L = ["# M4-03 streaming trust layer: latency and equivalence", "",
         f"Synthetic simulator streams (median preset), {r['n_streams']} utterances, mean "
         f"{r['frames_per_stream']['mean']:.0f} frames (max {r['frames_per_stream']['max']}), "
         f"V = {r['vocab_size']}. Config `{r['config_id']}`. "
         f"Machine: {r['machine']['system']}, Python {r['machine']['python']}, CPU only.", "",
         "| path | measure | p50 ms | p95 ms | p99 ms | max ms | equal to batch |", "|---|---|---|---|---|---|---|"]
    for k, lab in (("frames_route_beam", "frames, beam decoder"), ("frames_route_greedy", "frames, greedy decoder")):
        x = r[k]
        for m, ml in (("push_frame", "push(frame)"), ("final_decision", "end -> final decision")):
            s = x[m]
            L.append(f"| {lab} | {ml} | {s['p50_ms']:.3f} | {s['p95_ms']:.3f} | {s['p99_ms']:.3f} | {s['max_ms']:.3f} | "
                     f"{x['equal_to_batch'] if m == 'final_decision' else ''} |")
    s = r["hypothesis_route"]["push_hypothesis"]
    L.append(f"| hypothesis | push(hypothesis) | {s['p50_ms']:.3f} | {s['p95_ms']:.3f} | {s['p99_ms']:.3f} | "
             f"{s['max_ms']:.3f} | {r['hypothesis_route']['equal_to_batch']} |")
    m = r["interleaved_64_sessions_greedy"]
    L += ["", f"Actions (beam): {r['frames_route_beam']['actions']}.", "",
          f"Peak buffered frame bytes per session: {r['frames_route_beam']['peak_buffered_bytes_per_session']} "
          f"(float64 rows of the current utterance only; freed at the end of the utterance).", "",
          f"64 interleaved sessions (greedy): {m['events']} events in {m['wall_s']:.2f} s "
          f"({m['events_per_s']:.0f} events/s); tracemalloc peak {m['tracemalloc_peak_bytes'] / 1e6:.1f} MB.", ""]
    (OUT / "latency.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
