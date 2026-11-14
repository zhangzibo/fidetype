"""M6-11: WebSocket loopback through the streaming trust layer (latency + equality).

The same synthetic streams, frozen config and decoder as the LSL loopback
of M6-01 (``experiments/2026-11-12-m6-lsl``), so the numbers compare.
Synthetic simulator streams only (no participant data). CPU only. One
machine: server, producer and subscriber run in one process (threads) on
localhost, as the LSL runs A-D did.

Runs:
  A  frames route, real time (speed 1), one message per event, 4 utterances
  B  frames route, speed 4, one message per event, 12 utterances
  C  frames route, speed 4, ws_batch of 8 frames, 12 utterances
  D  hypothesis route, one event every 50 ms (the LSL run D stream)

Each run checks the final decisions against the file replay path
(``fidetype.trust.streaming.replay``): "exact" = Decision and PolicyInputs equal.

Latencies (``time.perf_counter`` of this one process; valid on localhost only):
  transport = server receive time - producer send stamp (``ws_t_recv - ws_t_sent``), per event
  e2e       = emission of the final decision - send stamp of the event that closed
              the utterance (segment_end / end / final hypothesis). Same definition
              as the LSL e2e (emission - LSL time of the closing event), minus the
              merge window, which WebSocket does not need (one ordered channel).
  delivery  = receipt of the decision by a /decisions subscriber - emission

Run (repo root; timing class, only when no other timing job holds the lock):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class timing -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-13-m6-11-ws/bench_ws_latency.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.adapters import ws as W  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events, replay  # noqa: E402
from fidetype.trust.testing import greedy_nbest  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
CONFIG = ROOT / "experiments" / "2026-11-12-m4-streaming" / "results" / "trust-config-synthetic.json"
LSL_RESULTS = ROOT / "experiments" / "2026-11-12-m6-lsl" / "results" / "latency.json"

# The stream builders of the LSL benchmark (same seeds, same streams).
_spec = importlib.util.spec_from_file_location("bench_lsl", ROOT / "experiments" / "2026-11-12-m6-lsl" / "bench_lsl_latency.py")
LSLB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LSLB)  # type: ignore[union-attr]


def pct(a_s) -> dict:
    a = np.asarray(a_s, dtype=np.float64) * 1e3
    if not a.size:
        return {"n": 0}
    return {"n": int(a.size), "p50_ms": float(np.percentile(a, 50)), "p95_ms": float(np.percentile(a, 95)),
            "max_ms": float(a.max()), "mean_ms": float(a.mean())}


def _subscriber(url: str, stop: threading.Event, sink: list) -> threading.Thread:
    def go() -> None:
        W.subscribe(url, lambda ev: sink.append((time.perf_counter(), ev)), stop=stop, duration_s=900)

    th = threading.Thread(target=go, daemon=True)
    th.start()
    return th


def run(path: Path, cfg: FrozenTrustConfig, decode, speed: float, batch: int, hyp_dt: float | None = None) -> dict:
    layer = StreamingTrustLayer(cfg, decode_fn=decode, streaming=StreamingConfig(max_attempts=1))
    server = W.WSServer(W.IngestSettings(), W.ServerSettings(port=0)).start()
    out: list[dict] = []
    runner = W.WSTrustRunner(layer, server, sink=out.append, hub=server.decisions, keep=True)
    sub_got: list = []
    stop = threading.Event()
    sub_th = _subscriber(server.url + W.PATH_DECISIONS, stop, sub_got)
    time.sleep(0.3)
    evs = list(iter_events(path))
    res: dict = {}

    def send() -> None:
        if hyp_dt is None:
            res["rs"] = W.replay_to_ws(evs, server.url + W.PATH_INGEST, "bench", speed=speed, batch=batch)
            return
        p = W.WSProducer(server.url + W.PATH_INGEST, evs[0], stream_id="bench-h").connect()
        for e in evs[1:]:
            p.send(e)
            time.sleep(hyp_dt)
        p.close()

    th = threading.Thread(target=send, daemon=True)
    th.start()
    s = runner.run(duration_s=900.0, max_streams=1, poll_timeout=0.005)
    th.join(30)
    time.sleep(0.3)
    stop.set()
    sub_th.join(5)
    server.stop()
    ref = replay(path, StreamingTrustLayer(cfg, decode_fn=decode, streaming=StreamingConfig(max_attempts=1)))
    e2e_final = [e["ws"]["e2e_latency_s"] for e in out if e["is_final"] and "e2e_latency_s" in e["ws"]]
    e2e_prov = [e["ws"]["e2e_latency_s"] for e in out if not e["is_final"] and "e2e_latency_s" in e["ws"]]
    srv = [e["ws"]["server_latency_s"] for e in out if e["is_final"] and "server_latency_s" in e["ws"]]
    delivery = [t - ev["ws"]["t_emit"] for t, ev in sub_got]
    acts: dict[str, int] = {}
    for d in runner.kept:
        if d.final:
            acts[d.action.value] = acts.get(d.action.value, 0) + 1
    return {"speed": speed, "batch": batch, "hyp_pacing_s": hyp_dt, "stop": s.stop_reason,
            "events_sent": len(evs) - 1, "frames": sum(e.get("type") == "frame" for e in evs), "wall_s": s.wall_s,
            "equality": LSLB.compare(runner.kept, ref), "actions": acts,
            "subscriber_received": len(sub_got), "subscriber_in_order": [ev["ws_seq"] for _, ev in sub_got] == [e["ws_seq"] for e in out],
            "transport": pct(runner._tr),
            "e2e_final": pct(e2e_final), "e2e_provisional": pct(e2e_prov), "server_final": pct(srv),
            "delivery_to_subscriber": pct(delivery), "ingest": s.ingest,
            "rejected": s.rejected_events, "aborted": s.aborted_utterances}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = FrozenTrustConfig.load(CONFIG)
    env = {"isolation_class": os.environ.get("FIDETYPE_ISOLATION_CLASS"), "cpus": os.environ.get("FIDETYPE_ISOLATION_CPUS"),
           "platform": platform.platform(), "python": platform.python_version(), "cpu": platform.processor(),
           "websockets": __import__("websockets").__version__}
    results: dict = {"config_id": cfg.config_id, "env": env, "runs": {}}
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a").mkdir()
        (d / "b").mkdir()
        f4 = LSLB.make_frames_file(d / "a", 4)
        f12 = LSLB.make_frames_file(d / "b", 12)
        hyp = LSLB.make_hyp_file(d, 30)
        plan = [("A_frames_rt_single", f4, greedy_nbest, 1.0, 1, None),
                ("B_frames_x4_single", f12, greedy_nbest, 4.0, 1, None),
                ("C_frames_x4_batch8", f12, greedy_nbest, 4.0, 8, None),
                ("D_hypothesis_50ms", hyp, None, 0.0, 1, 0.05)]
        for name, path, dec, speed, batch, dt in plan:
            t0 = time.monotonic()
            results["runs"][name] = run(path, cfg, dec, speed, batch, dt)
            r = results["runs"][name]
            print(f"{name}: {time.monotonic() - t0:.1f} s, equal {r['equality']['exact']}, "
                  f"transport p50 {r['transport'].get('p50_ms', float('nan')):.2f} ms, "
                  f"e2e final p50 {r['e2e_final'].get('p50_ms', float('nan')):.2f} ms", flush=True)
    if LSL_RESULTS.exists():
        results["lsl_reference"] = str(LSL_RESULTS.relative_to(ROOT)).replace("\\", "/")
    (OUT / "latency.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    write_md(results)


def _f(d: dict, k: str) -> str:
    return f"{d[k]:.2f}" if k in d else "-"


def write_md(r: dict) -> None:
    lines = ["# M6-11 WebSocket loopback: latency and equality", "",
             f"Synthetic simulator streams (the M6-01 LSL streams). Frozen config `{r['config_id']}` (M4-03 synthetic). "
             f"CTC greedy decoder. Localhost, one process. {r['env']['platform']}, Python {r['env']['python']}, "
             f"websockets {r['env']['websockets']}, CPU only, isolation class `{r['env']['isolation_class']}`.", "",
             "| run | frames | speed | batch | equal to file replay (exact) | transport p50 / p95 / max ms | "
             "e2e final p50 / p95 / max ms | server final p50 ms | delivery to subscriber p50 / p95 ms |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, x in r["runs"].items():
        t, e, s, dl = x["transport"] or {}, x["e2e_final"], x["server_final"], x["delivery_to_subscriber"]
        lines.append(f"| {name} | {x['frames']} | {x['speed'] or '50 ms pacing'} | {x['batch']} | {x['equality']['exact']} | "
                     f"{_f(t, 'p50_ms')} / {_f(t, 'p95_ms')} / {_f(t, 'max_ms')} | {_f(e, 'p50_ms')} / {_f(e, 'p95_ms')} / "
                     f"{_f(e, 'max_ms')} | {_f(s, 'p50_ms')} | {_f(dl, 'p50_ms')} / {_f(dl, 'p95_ms')} |")
    d = r["runs"].get("D_hypothesis_50ms")
    if d:
        lines += ["", f"Hypothesis route (D): provisional e2e p50 {_f(d['e2e_provisional'], 'p50_ms')} ms "
                      f"({d['e2e_provisional'].get('n', 0)} provisional decisions)."]
    lines += ["", "Every run: the /decisions subscriber got every decision in ws_seq order: "
              + ", ".join(f"{k} {v['subscriber_received']} ({'in order' if v['subscriber_in_order'] else 'NOT in order'})"
                          for k, v in r["runs"].items()) + "."]
    (OUT / "latency.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
