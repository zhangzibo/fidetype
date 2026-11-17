"""Binding producer runs: our own LSL and WebSocket outlets, captured on this machine (roadmap P7-06).

The self-certification list (spec 9.7) needs evidence for the code of this
repository that emits NTS over a binding. This module runs that code on
synthetic input, records what a consumer receives with
:mod:`fidetype.conformance.capture`, and writes the evidence files:

``lsl`` (``nts-lsl/0.1``, :mod:`fidetype.adapters.lsl`)
    1. :func:`~fidetype.adapters.lsl.replay_to_lsl` publishes the synthetic
       stream (frames stream + events stream) -> an ``inlet`` capture.
    2. :class:`~fidetype.adapters.lsl.LSLTrustRunner` reads that capture and
       publishes its decisions with :class:`~fidetype.adapters.lsl.DecisionOutlet`
       (the ``fidetype.decisions`` stream) -> a ``decisions`` capture.
``ws`` (``nts-ws/0.1``, :mod:`fidetype.adapters.ws`)
    1. :func:`~fidetype.adapters.ws.replay_to_ws` (:class:`~fidetype.adapters.ws.WSProducer`)
       sends the synthetic stream to a recording server -> an ``ingest`` capture.
    2. The reference server (:class:`~fidetype.adapters.ws.WSServer` +
       :class:`~fidetype.adapters.ws.WSTrustRunner`) gets the same stream; a
       subscriber of ``/decisions`` records its decisions -> a ``subscribe`` capture.

``live-lsl``, ``live-ws`` (roadmap P14-16)
    ``fidetype live --source synthetic --publish ...`` runs in a child process (the CLI as a user runs
    it) and publishes over the same outlets: ``--publish lsl:NAME`` -> an ``inlet`` capture and a
    ``decisions`` capture; ``--publish ws://HOST:PORT/nts`` + ``--publish ws://HOST:PORT/decisions``
    -> an ``ingest`` capture and a ``subscribe`` capture.

Each capture also gets its received stream (``*.received.jsonl``): the NTS
stream or the decision log that the reference consumer reads from it.
``nts-conform check DIR`` then gives the producer level and the binding.

Everything runs in one process on loopback (WebSocket on 127.0.0.1; LSL with
``ResolveScope = machine`` when :func:`loopback_lsl_config` is used). No
data from people, no GPU, no files outside ``out``.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

BINDING_TARGETS = ("lsl", "ws")
#: liblsl configuration that keeps discovery on this machine (set LSLAPICFG before the first pylsl call).
LSL_LOOPBACK_CFG = "[multicast]\nResolveScope = machine\n[ports]\nIPv6 = disable\n"


def loopback_lsl_config(folder: str | Path | None = None) -> Path | None:
    """Point ``LSLAPICFG`` to a machine-scope config unless the user set one. Return the file (or None)."""
    if os.environ.get("LSLAPICFG"):
        return None
    d = Path(folder) if folder else Path(tempfile.mkdtemp(prefix="fidetype-lslcfg-"))
    p = d / "lsl_api.cfg"
    p.write_text(LSL_LOOPBACK_CFG, encoding="utf-8")
    os.environ["LSLAPICFG"] = str(p)
    return p


def source_events() -> list[dict[str, Any]]:
    """The synthetic input: the first ``ctc-logits`` producer stream, cut into two utterances.

    Header (stream level provenance), 40 CTC frames with a ``segment_end`` after frame 20 and after the
    last frame, then ``end``. Synthetic scores, fixed seed, no data from people.
    """
    from fidetype.conformance.producers import TARGETS
    from fidetype.writer import write_stream

    ps = TARGETS["ctc-logits"]()[0]
    with tempfile.TemporaryDirectory() as td:
        f = write_stream(ps.stream, Path(td) / "src.jsonl")
        evs = [json.loads(line) for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip()]
    head, frames = evs[0], [e for e in evs if e.get("type") == "frame"]
    half = len(frames) // 2
    t_mid, t_end = frames[half - 1]["t"], frames[-1]["t"]
    fp = float(head.get("frame_period") or 0.04)
    return ([head] + frames[:half] + [{"type": "segment_end", "t": round(t_mid + fp / 2, 6)}] + frames[half:]
            + [{"type": "segment_end", "t": round(t_end + fp / 2, 6)}, {"type": "end"}])


def _layer(route: str = "frames") -> Any:
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer
    from fidetype.trust.testing import greedy_nbest

    cfg = FrozenTrustConfig(name="p7-06-binding-producers").with_policy(commit_p=0.3, commit_max_risk=1.0,
                                                                       abstain_risk=1.01)
    return StreamingTrustLayer(cfg, decode_fn=greedy_nbest if route == "frames" else None,
                               streaming=StreamingConfig(route=route, max_attempts=1)), cfg


def _thread(fn: Callable[[], Any], res: dict[str, Any], key: str) -> threading.Thread:
    def run() -> None:
        try:
            res[key] = fn()
        except BaseException as e:  # noqa: BLE001 - re-raised by the caller
            res[key + "_error"] = e

    th = threading.Thread(target=run, name=f"p7-06-{key}", daemon=True)
    th.start()
    return th


def _raise(res: dict[str, Any]) -> None:
    for k, v in res.items():
        if k.endswith("_error"):
            raise v


# --- LSL ------------------------------------------------------------------------------------------


def lsl_captures(events: list[dict[str, Any]], timeout: float = 30.0) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run our LSL outlets on ``events`` and return the ``inlet`` and the ``decisions`` captures."""
    from fidetype.adapters.lsl import DecisionOutlet, LSLEventSource, LSLMapping, LSLTrustRunner
    from fidetype.conformance.capture import capture_lsl
    from fidetype.conformance.profiles.fep0002 import _inlet

    name = f"fidetype.p7-06.{uuid.uuid4().hex[:8]}"
    res: dict[str, Any] = {}
    ready = threading.Event()
    from fidetype.adapters.lsl import replay_to_lsl

    th = _thread(lambda: replay_to_lsl(events, name, speed=0.0, channel_format="float32", wait_consumers_s=timeout,
                                       linger_s=2.0, ready=ready), res, "replay")
    if not ready.wait(timeout):
        raise TimeoutError("replay_to_lsl did not create its outlets")
    frames = capture_lsl({"name": name}, seconds=timeout,
                         description="P7-06: fidetype.adapters.lsl.replay_to_lsl (frames + events streams) on the "
                                     "synthetic ctc-logits stream, recorded by nts-conform capture")
    th.join(timeout)
    _raise(res)

    # The decisions outlet: the reference runner reads the recorded capture and publishes its decisions.
    layer, cfg = _layer()
    dec_name = f"fidetype.decisions.p7-06.{uuid.uuid4().hex[:8]}"
    outlet = DecisionOutlet(dec_name, config_id=cfg.config_id)
    stop, cready = threading.Event(), threading.Event()
    th = _thread(lambda: capture_lsl({"name": dec_name}, seconds=timeout, ready=cready, stop=stop,
                                     description="P7-06: fidetype.adapters.lsl.DecisionOutlet of LSLTrustRunner "
                                                 "(fidetype.decisions stream), recorded by nts-conform capture"),
                 res, "decisions")
    if not cready.wait(timeout) or not outlet.outlet.wait_for_consumers(timeout):
        stop.set()
        th.join(timeout)
        _raise(res)
        raise TimeoutError("the decisions capture did not connect")
    inl = frames["inlets"]
    src = LSLEventSource(_inlet(inl["primary"]), _inlet(inl["events"]) if inl.get("events") else None,
                         LSLMapping(merge_window_s=1e9, reconnect_timeout_s=1.0, reconnect_mode="inline"))
    runner = LSLTrustRunner(layer, src, session_id="p7-06-lsl", outlet=outlet, on_bad_event="raise")
    for _ in range(10000):
        runner.step(0.0)
        if runner.summary.ended or not any(getattr(r.inlet, "script", None) for r in src.readers):
            break
    runner.finish()
    if not runner.summary.ended:
        runner.flush()
    src.close()
    stop.set()
    th.join(timeout)
    del outlet
    _raise(res)
    return frames, res["decisions"]


# --- WebSocket ------------------------------------------------------------------------------------


def ws_captures(events: list[dict[str, Any]], timeout: float = 30.0) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run our WebSocket producer and server on ``events``; return the ``ingest`` and ``subscribe`` captures."""
    from fidetype.adapters.ws import OutputHub, ServerSettings, WSServer, WSTrustRunner, replay_to_ws
    from fidetype.conformance.capture import capture_ws_decisions, capture_ws_ingest

    res: dict[str, Any] = {}
    url_box: list[str] = []
    up = threading.Event()

    def ready(url: str) -> None:
        url_box.append(url)
        up.set()

    th = _thread(lambda: capture_ws_ingest("127.0.0.1", 0, seconds=timeout, ready=ready,
                                           description="P7-06: fidetype.adapters.ws.replay_to_ws (WSProducer) on the "
                                                       "synthetic ctc-logits stream, recorded by nts-conform capture"),
                 res, "ingest")
    if not up.wait(timeout):
        th.join(1)
        _raise(res)
        raise TimeoutError("the recording server did not start")
    replay_to_ws(events, url_box[0], stream_id="p7-06-ws", speed=0.0)
    th.join(timeout)
    _raise(res)

    # The decisions channel of the reference server.
    layer, cfg = _layer()
    hub = OutputHub("decisions", welcome_extra={"spec": "FEP-0001", "config_id": cfg.config_id})
    server = WSServer(settings=ServerSettings(host="127.0.0.1", port=0), decisions=hub).start()
    try:
        runner = WSTrustRunner(layer, server, hub=hub, events_hub=server.events)
        rth = _thread(lambda: runner.run(duration_s=timeout, max_streams=1), res, "runner")
        replay_to_ws(events, f"ws://127.0.0.1:{server.port}/nts", stream_id="p7-06-ws", speed=0.0)
        rth.join(timeout)
        _raise(res)
        n = runner.summary.decisions
        dec = capture_ws_decisions(f"ws://127.0.0.1:{server.port}/decisions", seconds=timeout,
                                   max_decisions=runner.summary.final_decisions or None,
                                   description="P7-06: the /decisions channel of fidetype.adapters.ws.WSServer + "
                                               "WSTrustRunner, recorded by nts-conform capture")
        if n and sum(1 for m in dec["messages"] if isinstance(m, dict) and m.get("type") == "trust_decision") < n:
            raise RuntimeError("the subscriber missed decisions")
    finally:
        server.stop()
    return res["ingest"], dec


# --- fidetype live --publish (P14-16) -------------------------------------------------------------

#: The ``fidetype live`` run of the live targets: the synthetic typist (no data from people), no pacing.
LIVE_ARGS = ("--source", "synthetic", "--utterances", "4", "--seed", "7", "--speed", "0", "--json")


def _live_proc(args: list[str], timeout: float) -> Any:
    """Start ``python -m fidetype.live`` (no window, stdout dropped, stderr kept) with ``args``."""
    import subprocess
    import sys

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    cmd = [sys.executable, "-m", "fidetype.live", *LIVE_ARGS, "--publish-wait", f"{timeout:g}",
           "--publish-linger", "2", *args]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", creationflags=flags, env=dict(os.environ))


def _live_end(proc: Any, timeout: float) -> str:
    try:
        _, err = proc.communicate(timeout=timeout)
    except BaseException:
        proc.kill()
        proc.communicate()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"fidetype live exited with {proc.returncode}:\n{err[-2000:]}")
    if "failed (" in err:
        raise RuntimeError(f"a publish target of fidetype live failed:\n{err[-2000:]}")
    return err


def live_lsl_captures(timeout: float = 30.0) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run ``fidetype live --publish lsl:NAME``; return the ``inlet`` capture and the ``decisions`` capture."""
    from fidetype.conformance.capture import capture_lsl

    name = f"fidetype.live.p14-16.{uuid.uuid4().hex[:8]}"
    proc = _live_proc(["--publish", f"lsl:{name}"], timeout)
    res: dict[str, Any] = {}
    stop = threading.Event()
    try:
        th = _thread(lambda: capture_lsl({"name": name + ".decisions"}, seconds=3 * timeout, stop=stop,
                                         resolve_timeout=timeout,
                                         description="P14-16: fidetype live --publish lsl (DecisionOutlet: the "
                                                     "NAME.decisions stream), recorded by nts-conform capture"),
                     res, "decisions")
        frames = capture_lsl({"name": name}, seconds=3 * timeout, resolve_timeout=timeout,
                             description="P14-16: fidetype live --source synthetic --publish lsl (NTSOutlet: frames + "
                                         "events streams), recorded by nts-conform capture")
        _live_end(proc, timeout)
    finally:
        stop.set()
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    th.join(timeout)
    _raise(res)
    return frames, res["decisions"]


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def live_ws_captures(timeout: float = 30.0) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run ``fidetype live --publish ws://.../nts --publish ws://.../decisions``; return ``ingest`` + ``subscribe``."""
    import socket
    import time

    from fidetype.conformance.capture import capture_ws_decisions, capture_ws_ingest

    res: dict[str, Any] = {}
    url_box: list[str] = []
    up = threading.Event()

    def ready(url: str) -> None:
        url_box.append(url)
        up.set()

    th = _thread(lambda: capture_ws_ingest("127.0.0.1", 0, seconds=3 * timeout, ready=ready,
                                           description="P14-16: fidetype live --source synthetic --publish "
                                                       "ws://HOST:PORT/nts (WSProducer), recorded by nts-conform "
                                                       "capture"), res, "ingest")
    if not up.wait(timeout):
        th.join(1)
        _raise(res)
        raise TimeoutError("the recording server did not start")
    port = _free_port()
    proc = _live_proc(["--publish", url_box[0], "--publish", f"ws://127.0.0.1:{port}/decisions"], timeout)
    stop = threading.Event()
    dth = None
    try:
        t0 = time.monotonic()
        while True:  # wait until fidetype live serves /decisions
            if proc.poll() is not None:
                _live_end(proc, timeout)
                raise RuntimeError("fidetype live ended before it served /decisions")
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                if time.monotonic() - t0 > timeout:
                    raise TimeoutError("fidetype live did not serve /decisions") from None
                time.sleep(0.05)
        dth = _thread(lambda: capture_ws_decisions(f"ws://127.0.0.1:{port}/decisions", seconds=3 * timeout, stop=stop,
                                                   description="P14-16: fidetype live --publish "
                                                               "ws://HOST:PORT/decisions (WSServer + OutputHub), "
                                                               "recorded by nts-conform capture"), res, "decisions")
        _live_end(proc, 3 * timeout)
    finally:
        stop.set()
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    if dth is not None:
        dth.join(timeout)
    th.join(timeout)
    _raise(res)
    return res["ingest"], res["decisions"]


# --- evidence -------------------------------------------------------------------------------------

#: ``fidetype live --publish`` targets (P14-16): the CLI in a child process, captured on loopback.
LIVE_TARGETS = ("live-lsl", "live-ws")


def write_evidence(target: str, out: str | Path, timeout: float = 30.0) -> list[Path]:
    """Run one binding target and write its captures and received streams to ``out``. Return the files."""
    from fidetype.conformance.capture import write_capture, write_received

    if target not in BINDING_TARGETS + LIVE_TARGETS:
        raise ValueError(f"unknown binding target {target!r} (known: {list(BINDING_TARGETS + LIVE_TARGETS)})")
    d = Path(out)
    d.mkdir(parents=True, exist_ok=True)
    if target == "live-lsl":
        a, b = live_lsl_captures(timeout)
        names = ("live-lsl-frames", "live-lsl-decisions")
    elif target == "live-ws":
        a, b = live_ws_captures(timeout)
        names = ("live-ws-ingest", "live-ws-decisions")
    elif target == "lsl":
        a, b = lsl_captures(source_events(), timeout)
        names = ("lsl-frames", "lsl-decisions")
    else:
        a, b = ws_captures(source_events(), timeout)
        names = ("ws-ingest", "ws-decisions")
    files = []
    for sc, nm in zip((a, b), names):
        files.append(write_capture(sc, d / f"{nm}.capture.json"))
        files.append(write_received(sc, d / f"{nm}.received.jsonl"))
    return files


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Record the binding producer evidence of this repository (P7-06).")
    ap.add_argument("--out", required=True, help="folder for the captures (one sub-folder per target)")
    ap.add_argument("--target", action="append", choices=BINDING_TARGETS + LIVE_TARGETS,
                    help="default: lsl and ws; live-lsl / live-ws run fidetype live --publish (P14-16)")
    ap.add_argument("--timeout", type=float, default=30.0)
    a = ap.parse_args(argv)
    loopback_lsl_config()
    for t in a.target or BINDING_TARGETS:
        for f in write_evidence(t, Path(a.out) / t, a.timeout):
            print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
