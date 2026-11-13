"""M6-01: LSL loopback through the streaming trust layer (latency + equality).

Synthetic simulator streams only (no participant data). CPU only. One
machine: the outlet and the inlet run on localhost.

Runs:
  A  frames route, float32 frames (spec 6.4), real time (speed 1), merge window 50 ms
  B  frames route, double64 frames, speed 4, merge window 50 ms (bit-equal rows)
  C  frames route, float32 frames, speed 4, merge window 10 ms
  D  hypothesis route (n-best JSON on the marker stream), real time
  E  the two CLIs in two processes: ``replay-to-lsl`` -> ``run --outlet``,
     compared with ``python -m fidetype.trust.streaming replay``

Each run checks the decisions against the file replay path
(``fidetype.trust.streaming.replay``): same final decisions in the same
order. "exact" = Decision and PolicyInputs equal; "action+shown" = the
action and the shown texts equal.

Latencies (LSL local_clock, receiver side):
  transport = receive time - (LSL timestamp + time_correction), per sample
  e2e       = emission of the final decision - LSL time of the event that
              closed the utterance (segment_end / end / final hypothesis).
              It includes the merge wait, the decode and the trust core.

Run (repo root, needs pylsl: uv pip install pylsl):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-m6-lsl/bench_lsl_latency.py
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.adapters import lsl as L  # noqa: E402
from fidetype.conformance.io import write_jsonl  # noqa: E402
from fidetype.streams.corpus import sentences  # noqa: E402
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events, replay  # noqa: E402
from fidetype.trust.testing import greedy_nbest  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
#: The frozen synthetic config of M4-03 (numbers only, no data).
CONFIG = ROOT / "experiments" / "2026-11-12-m4-streaming" / "results" / "trust-config-synthetic.json"
N_UTT = 12


def pct(a_s) -> dict:
    a = np.asarray(a_s, dtype=np.float64) * 1e3
    if not a.size:
        return {"n": 0}
    return {"n": int(a.size), "p50_ms": float(np.percentile(a, 50)), "p95_ms": float(np.percentile(a, 95)),
            "max_ms": float(a.max()), "mean_ms": float(a.mean())}


def make_frames_file(d: Path, n: int, seed: int = 5) -> Path:
    sents = sentences(200, seed=seed)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=seed)
    events, off = [], 0.0
    one = d / "_one.jsonl"
    for k, s in enumerate(sents[:n]):
        write_jsonl(sim.simulate(s, seed=13 * k).stream, one)
        evs = list(iter_events(one))
        if k == 0:
            events.append(evs[0])
        for ev in evs[1:-1]:
            events.append({**ev, "t": round(ev["t"] + off, 9)})
        events.append({"type": "segment_end"})
        off = events[-2]["t"] + 0.5  # a 0.5 s pause between utterances
    events[-1] = {"type": "end"}
    p = d / "frames.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p


def make_hyp_file(d: Path, n: int, seed: int = 9) -> Path:
    """Hypothesis-only stream: growing partial hypotheses, then a final 2-best list per utterance."""
    rng = np.random.default_rng(seed)
    sents = sentences(200, seed=seed)
    events = [{"type": "header", "spec_version": "0.1", "vocab": [], "vocab_type": "char", "blank_id": None,
               "source": "synthetic-text-decoder", "meta": {"data.derived": True}}]
    for k, s in enumerate(sents[:n]):
        words = s.split()
        for j in range(1, len(words)):
            events.append({"type": "hypothesis", "id": f"u{k}-p{j}", "is_final": False, "score_semantics": "none",
                           "nbest": [{"text": " ".join(words[:j]), "score": -float(j)}]})
        alt = s[:-1] + ("a" if s[-1] != "a" else "b")
        sc = float(rng.normal(-2, 1))
        events.append({"type": "hypothesis", "id": f"u{k}-f", "is_final": True, "score_semantics": "none",
                       "nbest": [{"text": s, "score": sc}, {"text": alt, "score": sc - abs(rng.normal(1, 1))}]})
    events.append({"type": "end"})
    p = d / "hyp.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p


def compare(got, ref) -> dict:
    gf = [d for d in got if d.final]
    rf = [d for d in ref if d.final]
    exact = sum(int(a.decision == b.decision and a.inputs == b.inputs) for a, b in zip(gf, rf))
    act = sum(int(a.action == b.action and a.shown == b.shown) for a, b in zip(gf, rf))
    dp = [abs(a.inputs.p_top1 - b.inputs.p_top1) for a, b in zip(gf, rf)]
    return {"n_ref": len(rf), "n_got": len(gf), "exact": f"{exact}/{len(rf)}", "action_and_shown": f"{act}/{len(rf)}",
            "max_abs_dp_top1": float(max(dp)) if dp else None}


def loopback(path: Path, cfg: FrozenTrustConfig, decode, fmt: str, speed: float, merge: float) -> dict:
    name = f"fidetype-bench-{uuid.uuid4().hex[:8]}"
    ready = threading.Event()
    res: dict = {}

    def send():
        res["rs"] = L.replay_to_lsl(path, name, speed=speed, channel_format=fmt, wait_consumers_s=30.0,
                                    linger_s=1.0, ready=ready)

    th = threading.Thread(target=send, daemon=True)
    th.start()
    ready.wait(10)
    src = L.open_source(name=name, timeout=10.0, mapping=L.LSLMapping(merge_window_s=merge))
    layer = StreamingTrustLayer(cfg, decode_fn=decode, streaming=StreamingConfig(max_attempts=1))
    out: list[dict] = []
    runner = L.LSLTrustRunner(layer, src, sink=out.append, keep=True)
    s = runner.run(duration_s=900.0, poll_timeout=0.005)
    src.close()
    th.join(60)
    ref = replay(path, StreamingTrustLayer(cfg, decode_fn=decode, streaming=StreamingConfig(max_attempts=1)))
    e2e = [e["lsl"]["e2e_latency_s"] for e in out if e["is_final"] and "e2e_latency_s" in e["lsl"]]
    acts: dict[str, int] = {}
    for d in runner.kept:
        if d.final:
            acts[d.action.value] = acts.get(d.action.value, 0) + 1
    tl = np.asarray(runner.source.stats.transport_latency_s)
    return {"channel_format": fmt, "speed": speed, "merge_window_s": merge, "stop": s.stop_reason,
            "frames_sent": res["rs"].frames, "events_sent": res["rs"].events, "wall_s": s.wall_s,
            "equality": compare(runner.kept, ref), "actions": acts,
            "transport": pct(tl), "e2e_final": pct(e2e),
            "time_correction_s": out[-1]["lsl"]["time_correction_s"] if out else None,
            "clock_updates": out[-1]["lsl"]["updates"] if out else None,
            "source_stats": {k: v for k, v in s.source.items() if k != "transport_latency_ms"},
            "rejected": s.rejected_events, "aborted": s.aborted_utterances}


def loopback_hyp(path: Path, cfg: FrozenTrustConfig, dt: float) -> dict:
    """Hypothesis route: a paced marker outlet (one event every dt s).

    ``replay_to_lsl`` paces by frame times only; a stream without frames is
    sent back to back. So this run uses its own outlet.
    """
    pl = L.require_pylsl()
    evs = list(iter_events(path))
    head = {k: v for k, v in evs[0].items() if k != "type"}
    name = f"fidetype-bench-h-{uuid.uuid4().hex[:8]}"
    info = pl.StreamInfo(name, L.MARKERS_TYPE, 1, pl.IRREGULAR_RATE, "string", name)
    info.desc().append_child(L.DESC_ROOT).append_child_value("nts_header", json.dumps(head))
    outlet = pl.StreamOutlet(info)
    stop = threading.Event()

    def send():
        outlet.wait_for_consumers(30)
        time.sleep(0.2)
        for e in evs[1:]:
            outlet.push_sample([json.dumps(e)], pl.local_clock())
            time.sleep(dt)
        time.sleep(1.0)
        stop.set()

    th = threading.Thread(target=send, daemon=True)
    th.start()
    src = L.open_source(name=name, timeout=10.0, mapping=L.LSLMapping())
    layer = StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1))
    out: list[dict] = []
    runner = L.LSLTrustRunner(layer, src, sink=out.append, keep=True)
    s = runner.run(duration_s=600.0, poll_timeout=0.005)
    src.close()
    th.join(30)
    ref = replay(path, StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1)))
    e2e_final = [e["lsl"]["e2e_latency_s"] for e in out if e["is_final"]]
    e2e_prov = [e["lsl"]["e2e_latency_s"] for e in out if not e["is_final"]]
    return {"events_sent": len(evs) - 1, "pacing_s": dt, "stop": s.stop_reason, "equality": compare(runner.kept, ref),
            "provisional_decisions": len(e2e_prov), "e2e_final": pct(e2e_final), "e2e_provisional": pct(e2e_prov),
            "transport": pct(runner.source.stats.transport_latency_s)}


def cli_run(path: Path, cfg_path: Path, tmp: Path) -> dict:
    """Run E: the two CLIs in two processes, compared with the streaming replay CLI."""
    import os

    py = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    name = f"fidetype-cli-{uuid.uuid4().hex[:8]}"
    sender = subprocess.Popen([py, "-m", "fidetype.adapters.lsl", "replay-to-lsl", str(path), "--name", name,
                               "--speed", "4", "--wait-consumers", "60"], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
    summ = tmp / "summary.json"
    run = subprocess.run([py, "-m", "fidetype.adapters.lsl", "run", "--config", str(cfg_path), "--stream-name", name,
                          "--decoder", "greedy", "--max-attempts", "1", "--outlet", "--summary", str(summ),
                          "--resolve-timeout", "20"], env=env, capture_output=True, text=True, timeout=600)
    sender.wait(60)
    ref = subprocess.run([py, "-m", "fidetype.trust.streaming", "replay", "--config", str(cfg_path),
                          "--decoder", "greedy", str(path)], env=env, capture_output=True, text=True, timeout=600)
    got = [json.loads(x) for x in run.stdout.splitlines() if x.strip()]
    exp = [json.loads(x) for x in ref.stdout.splitlines() if x.strip()]
    keys = ("action", "shown", "p_top1", "set_size", "guard_risk", "is_final", "utterance")
    same = sum(int(all(a.get(k) == b.get(k) for k in keys)) for a, b in zip(got, exp))
    s = json.loads(summ.read_text(encoding="utf-8")) if summ.exists() else {}
    return {"exit_codes": {"replay-to-lsl": sender.returncode, "run": run.returncode, "streaming replay": ref.returncode},
            "decisions": len(got), "reference_decisions": len(exp), "equal_fields": list(keys),
            "equal": f"{same}/{len(exp)}" if len(got) == len(exp) else f"count differs ({len(got)} vs {len(exp)})",
            "stop": s.get("stop_reason"), "e2e_latency_ms": s.get("e2e_latency_ms"),
            "note": "max_attempts 1 in run; the streaming replay CLI uses the default (2), so the attempt fields "
                    "are not compared"}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    pl = L.require_pylsl()
    cfg = FrozenTrustConfig.load(CONFIG)
    res: dict = {"description": "M6-01 LSL loopback through the streaming trust layer (synthetic, localhost)",
                 "machine": {"python": platform.python_version(), "system": platform.system(),
                             "processor": platform.processor(), "pylsl": pl.__version__,
                             "liblsl": pl.library_version()},
                 "config_id": cfg.config_id, "n_utterances": N_UTT}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fpath = make_frames_file(tmp, N_UTT)
        res["frames_in_file"] = sum(1 for e in iter_events(fpath) if e["type"] == "frame")
        runs = {
            "A_float32_rt_merge50": ("float32", 1.0, 0.05),
            "B_double64_x4_merge50": ("double64", 4.0, 0.05),
            "C_float32_x4_merge10": ("float32", 4.0, 0.01),
        }
        for k, (fmt, sp, mw) in runs.items():
            print(f"run {k} ...", flush=True)
            res[k] = loopback(fpath, cfg, greedy_nbest, fmt, sp, mw)
            print(json.dumps(res[k]["equality"]), res[k]["e2e_final"], flush=True)
        print("run D ...", flush=True)
        hpath = make_hyp_file(tmp, 30)
        res["D_hypothesis_rt"] = loopback_hyp(hpath, cfg, 0.05)
        print(json.dumps(res["D_hypothesis_rt"]["equality"]), flush=True)
        print("run E ...", flush=True)
        cfg_copy = tmp / "trust.json"
        cfg.save(cfg_copy)
        res["E_cli_two_processes"] = cli_run(fpath, cfg_copy, tmp)
        print(json.dumps(res["E_cli_two_processes"]), flush=True)
    (OUT / "latency.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    write_md(res)


def write_md(r: dict) -> None:
    m = r["machine"]
    L_ = ["# M6-01 LSL loopback: latency and equality", "",
          f"Synthetic simulator streams, {r['n_utterances']} utterances, {r['frames_in_file']} frames (40 ms), "
          f"one file with `segment_end` between utterances. Frozen config `{r['config_id']}` (M4-03 synthetic). "
          f"CTC greedy decoder. Localhost. {m['system']}, Python {m['python']}, pylsl {m['pylsl']}, "
          f"liblsl {m['liblsl']}, CPU only.", "",
          "| run | frames | speed | merge window | equal to file replay (exact / action+shown) | "
          "transport p50 / p95 / max ms | e2e final p50 / p95 / max ms |",
          "|---|---|---|---|---|---|---|"]
    for k in ("A_float32_rt_merge50", "B_double64_x4_merge50", "C_float32_x4_merge10"):
        x = r[k]
        t, e, q = x["transport"], x["e2e_final"], x["equality"]
        L_.append(f"| {k} | {x['channel_format']} | {x['speed']} | {x['merge_window_s'] * 1e3:.0f} ms | "
                  f"{q['exact']} / {q['action_and_shown']} | {t['p50_ms']:.2f} / {t['p95_ms']:.2f} / {t['max_ms']:.2f} | "
                  f"{e['p50_ms']:.1f} / {e['p95_ms']:.1f} / {e['max_ms']:.1f} |")
    d = r["D_hypothesis_rt"]
    L_ += ["", f"Hypothesis route (D): {d['events_sent']} marker events, one every {d['pacing_s'] * 1e3:.0f} ms; "
           f"equal {d['equality']['exact']}; e2e final p50 {d['e2e_final']['p50_ms']:.2f} ms, "
           f"p95 {d['e2e_final']['p95_ms']:.2f} ms, max {d['e2e_final']['max_ms']:.2f} ms; "
           f"provisional p50 {d['e2e_provisional']['p50_ms']:.2f} ms ({d['provisional_decisions']} provisional).", "",
           f"Two processes, the CLIs (E): {json.dumps(r['E_cli_two_processes'])}", "",
           "Max |p_top1 difference| with float32 frames (A): "
           f"{r['A_float32_rt_merge50']['equality']['max_abs_dp_top1']}.", ""]
    (OUT / "latency.md").write_text("\n".join(L_), encoding="utf-8")


if __name__ == "__main__":
    main()
