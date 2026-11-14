"""M6-11: the 816 Brain-to-Text '25 test trials over WebSocket, compared with batch and in-process replay.

Input: the hypothesis-route NTS files of M4-06 (``<derived>/m4-06-real-replay/streams/hyp-ours``)
and the frozen real-data config ``trust-config-b2t25-ours-splitA.json``. These files stay outside
the repo (derived from a dataset with its own licence). The repo gets aggregate counts only: no
texts, no per-trial values.

Each session day is one WebSocket stream (stream id = ``session.id``, as M4-06 used one trust
session per day). Its trials go in M4-06 order (header, hypothesis, end, header, ...). Four
producers send at the same time. The final decision of each trial is compared with:
  - the in-process streaming replay (M4-06 ``replay_files``): Decision and PolicyInputs equal;
  - the batch harness (``batch-ours.json``): action, shown, p_top1, guard risk, prediction set.

Run (repo root; background class):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-13-m6-11-ws/b2t_replay_ws.py
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.adapters import ws as W  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events  # noqa: E402

DER = Path.home() / "bci-data" / "derived" / "m4-06-real-replay"
STREAMS = DER / "streams" / "hyp-ours"
CONFIG = ROOT / "experiments" / "2026-11-13-m4-06-real-replay" / "configs" / "trust-config-b2t25-ours-splitA.json"
OUT = Path(__file__).resolve().parent / "results"


def layer(cfg: FrozenTrustConfig) -> StreamingTrustLayer:
    return StreamingTrustLayer(cfg, streaming=StreamingConfig(route="hypothesis", max_attempts=1))


def batch_equal(d, b: dict) -> bool:
    gr = float(d.guard.risk) if d.guard is not None else float("nan")
    return (d.action.value == b["action"] and list(d.shown) == b["shown"] and float(d.inputs.p_top1) == float(b["p_top1"])
            and (gr == float(b["guard_risk"]) or (math.isnan(gr) and math.isnan(float(b["guard_risk"]))))
            and list(d.inputs.set_indices) == b["set"])


def main() -> None:
    cfg = FrozenTrustConfig.load(CONFIG)
    batch = json.loads((DER / "batch-ours.json").read_text(encoding="utf-8"))
    trials = batch["trials"]
    files = {t: list(iter_events(STREAMS / f"trial-{t:04d}.jsonl")) for t in trials}
    sess = {t: files[t][0]["meta"]["session.id"] for t in trials}
    by_sess: OrderedDict[str, list[int]] = OrderedDict()
    for t in trials:
        by_sess.setdefault(sess[t], []).append(t)

    # In-process streaming replay (as M4-06): one session per day, files in order.
    ref_layer = layer(cfg)
    ref: dict[int, object] = {}
    for t in trials:
        got = []
        for ev in files[t]:
            got += ref_layer.push(ev, sess[t])
        got += ref_layer.end_of_utterance(sess[t])
        fin = [d for d in got if d.final]
        assert len(fin) == 1
        ref[t] = fin[0]

    # WebSocket: server + runner here, four producers (one stream per day).
    ws_layer = layer(cfg)
    server = W.WSServer(W.IngestSettings(), W.ServerSettings(port=0)).start()
    runner = W.WSTrustRunner(ws_layer, server, hub=server.decisions, keep=True)

    def send(sid: str) -> int:
        evs = [e for t in by_sess[sid] for e in files[t]]
        p = W.WSProducer(server.url + W.PATH_INGEST, evs[0], stream_id=sid, batch=1).connect()
        for e in evs[1:]:
            p.send(e)
        p.close(wait_ack_s=30)
        return len(evs)

    t0 = time.monotonic()
    pool = ThreadPoolExecutor(4)
    futs = [pool.submit(send, sid) for sid in by_sess]
    done = threading.Event()
    threading.Thread(target=lambda: ([f.result() for f in futs], done.set()), daemon=True).start()
    while not (done.is_set() and runner.summary.streams_closed >= len(by_sess)):
        runner.step(0.01)
        for f in futs:
            if f.done() and f.exception() is not None:
                raise f.exception()
        if time.monotonic() - t0 > 600:
            raise SystemExit("time-out")
    s_events = sum(f.result() for f in futs)
    wall = time.monotonic() - t0
    server.stop()
    finals: dict[str, list] = {}
    for d in runner.kept:
        if d.final:
            finals.setdefault(d.session_id, []).append(d)
    ws_dec = {t: finals[sid][k] for sid, ts in by_sess.items() for k, t in enumerate(ts)}
    assert all(len(finals[sid]) == len(ts) for sid, ts in by_sess.items())

    eq_ref = sum(ws_dec[t].decision == ref[t].decision and ws_dec[t].inputs == ref[t].inputs for t in trials)
    eq_batch = sum(batch_equal(ws_dec[t], b) for t, b in zip(trials, batch["decisions"]))
    ref_batch = sum(batch_equal(ref[t], b) for t, b in zip(trials, batch["decisions"]))
    acts: dict[str, int] = {}
    for t in trials:
        acts[ws_dec[t].action.value] = acts.get(ws_dec[t].action.value, 0) + 1
    res = {"config_id": cfg.config_id, "trials": len(trials), "sessions": len(by_sess), "events_sent": s_events,
           "concurrent_producers": 4, "wall_s": wall,
           "ws_equal_in_process_exact": f"{eq_ref}/{len(trials)}",
           "ws_equal_batch_harness": f"{eq_batch}/{len(trials)}",
           "in_process_equal_batch_harness": f"{ref_batch}/{len(trials)}",
           "actions": dict(sorted(acts.items())), "rejected": runner.summary.rejected_events,
           "aborted": runner.summary.aborted_utterances, "ingest": server.core.stats.as_dict(),
           "note": "aggregate counts only; the trial files and texts stay outside the repo"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b2t-replay.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
