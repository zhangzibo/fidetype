"""Record LSL and WebSocket captures from live producers (roadmap P7-06).

``nts-conform check`` judges a binding producer from a *capture*: a scenario
JSON file that holds what a consumer received (``lsl-scenario/1`` for
NTS over LSL, FEP-0002; ``ws-scenario/1`` for NTS over WebSocket,
FEP-0004). This module records such a capture from a running producer::

    nts-conform capture --lsl fidetype.nts --seconds 10 --out cap.json
    nts-conform capture --lsl type=Markers,name=fidetype.decisions --until-stop --seconds 5 --out dec.json
    nts-conform capture --ws ws://127.0.0.1:8765/nts --seconds 10 --out ws.json        # listens; your producer connects
    nts-conform capture --ws ws://127.0.0.1:8765/decisions --seconds 10 --out wsd.json # subscribes to your server

Forms
-----
``--lsl QUERY``
    Resolves one LSL stream (``QUERY`` = a stream name, or ``key=value``
    pairs with the keys ``name``, ``type``, ``source_id``). A frames stream
    (``desc/fidetype/role`` not ``trust_decisions``) gives an ``inlet``
    capture: the frames stream and, if its desc names
    ``events_source_id``, the events stream. A decisions stream
    (``role = trust_decisions``) gives a ``decisions`` capture. The capture
    keeps the raw LSL timestamps and the inlet's ``time_correction()``.
``--ws ws://HOST:PORT/nts``
    Starts a recording server on ``HOST:PORT`` (loopback by default). It
    answers like the reference server (welcome, acks; :class:`~fidetype.adapters.ws.IngestCore`)
    and records each connection open, message and close as an ``ingest``
    step with its time.
``--ws ws://HOST:PORT/decisions``
    Subscribes (``from_seq`` 1) and records every message (welcome,
    decisions, errors) as a ``subscribe`` capture.

``--received OUT.jsonl`` also writes what the reference consumer reads from
the capture: the NTS stream (header, frames, events) of an ``inlet`` or
``ingest`` capture, or the ``trust_decision`` events (a decision log) of a
``decisions`` or ``subscribe`` capture. ``nts-conform check`` gives a
producer level only to evidence with an input stream (spec 9.6), so the
binding evidence is the capture together with its received stream.

Privacy. An LSL stream info is rewritten with only the fields that
FEP-0002 uses: the host name, uid, creation time, session id and network
addresses are removed. A WebSocket capture never records the
``Authorization`` header, an auth token or the client address.

Our own code (Apache-2.0). ``pylsl`` (MIT) and ``websockets`` (BSD-3-Clause)
are optional; the functions that need them raise an install hint.
"""

from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlsplit

LSL_SCHEMA = "fidetype.conformance.lsl-scenario/1"
WS_SCHEMA = "fidetype.conformance.ws-scenario/1"
CAPTURE_TOOL = "nts-conform capture"
#: Seconds of extra pulls after the stop condition (data already on the way).
GRACE_S = 0.3


class CaptureError(RuntimeError):
    """The capture could not start or recorded nothing usable."""


# --- shared helpers -------------------------------------------------------------------------------


def _num(v: Any) -> Any:
    """A numeric LSL sample value in scenario form (null = -inf, "NaN" = NaN)."""
    f = float(v)
    if math.isnan(f):
        return "NaN"
    if f == -math.inf:
        return None
    if f == math.inf:
        return "Infinity"
    return f


def _strict_json(text: str) -> Any:
    """``json.loads`` that refuses NaN / Infinity (they cannot be written back with ``allow_nan=False``)."""
    def bad(c: str) -> Any:
        raise ValueError(f"non-standard JSON constant {c}")

    return json.loads(text, parse_constant=bad)


def write_capture(sc: dict[str, Any], path: str | Path) -> Path:
    """Write a capture as UTF-8 JSON (the form that ``nts-conform check`` reads)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sc, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
                 newline="\n")
    return p


# --- LSL ------------------------------------------------------------------------------------------


def parse_query(query: str) -> dict[str, str]:
    """``"fidetype.nts"`` -> ``{"name": ...}``; ``"type=NTS,source_id=x"`` -> ``{"type": "NTS", "source_id": "x"}``."""
    if "=" not in query:
        return {"name": query}
    out: dict[str, str] = {}
    for part in query.split(","):
        k, sep, v = part.partition("=")
        k = k.strip()
        if not sep or k not in ("name", "type", "source_id") or not v.strip():
            raise ValueError(f"bad LSL query part {part!r} (use name=..., type=..., source_id=...)")
        out[k] = v.strip()
    return out


def sanitize_info_xml(xml: str) -> str:
    """The stream info with only the fields that FEP-0002 uses (no host name, uid, time or address)."""
    from fidetype.adapters.lsl import LSLStreamInfo, info_to_xml

    info = LSLStreamInfo.from_xml(xml)
    info.hostname, info.uid, info.created_at = "", "", 0.0
    return info_to_xml(info)


class _LSLRecorder:
    """One pylsl inlet and the chunks it received."""

    def __init__(self, pl: Any, stream_info: Any, open_timeout: float) -> None:
        self.pl = pl
        self.inlet = pl.StreamInlet(stream_info, max_buflen=360, recover=False, processing_flags=0)
        full = self.inlet.info(open_timeout)
        self.raw_xml = full.as_xml()
        from fidetype.adapters.lsl import LSLStreamInfo

        self.info = LSLStreamInfo.from_xml(self.raw_xml)
        # Before open_stream: a producer that waits for consumers starts to send at open_stream.
        self.time_correction = float(self.inlet.time_correction(max(1.0, open_timeout)))
        self.inlet.open_stream(open_timeout)
        self.chunks: list[dict[str, Any]] = []
        self.samples = 0

    def pull(self) -> list[list[Any]]:
        try:
            s, ts = self.inlet.pull_chunk(timeout=0.0, max_samples=1024)
        except self.pl.util.LostError:
            return []
        if not ts:
            return []
        rows = [[str(v) for v in r] if self.info.is_string else [_num(v) for v in r] for r in s]
        self.chunks.append({"samples": rows, "timestamps": [float(t) for t in ts]})
        self.samples += len(ts)
        return rows

    def spec(self) -> dict[str, Any]:
        return {"info_xml": sanitize_info_xml(self.raw_xml), "time_correction": self.time_correction,
                "chunks": self.chunks}

    def close(self) -> None:
        try:
            self.inlet.close_stream()
        except Exception:  # noqa: BLE001 - best effort at shutdown
            pass


def _resolve_one(query: dict[str, str], timeout: float) -> Any:
    from fidetype.adapters.lsl import resolve

    return resolve(timeout=timeout, **query)


def capture_lsl(query: str | dict[str, str], seconds: float = 30.0, until_end: bool = True, events: str = "auto",
                resolve_timeout: float = 10.0, open_timeout: float = 5.0, ready: threading.Event | None = None,
                stop: threading.Event | None = None, description: str | None = None,
                log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Record one LSL producer as an ``lsl-scenario/1`` capture (module docstring).

    ``until_end``: an ``inlet`` capture stops after the events stream sent ``{"type": "end"}``. Else (and
    always for a ``decisions`` capture) it stops after ``seconds`` or when ``stop`` is set. ``events``:
    ``"auto"`` (the events stream named by ``desc/fidetype/events_source_id``) or ``"none"``. ``ready`` is
    set when the inlets are open (start the producer after it).
    """
    from fidetype.adapters.lsl import require_pylsl

    pl = require_pylsl()
    log = log or (lambda m: None)
    q = parse_query(query) if isinstance(query, str) else dict(query)
    primary = _LSLRecorder(pl, _resolve_one(q, resolve_timeout), open_timeout)
    recs = [primary]
    is_dec = primary.info.fidetype.get("role") == "trust_decisions"
    ev_rec = None
    if not is_dec and events == "auto" and primary.info.fidetype.get("events_source_id"):
        ev_rec = _LSLRecorder(pl, _resolve_one({"source_id": primary.info.fidetype["events_source_id"]},
                                               resolve_timeout), open_timeout)
        recs.append(ev_rec)
    log(f"recording {', '.join(r.info.name for r in recs)}")
    if ready is not None:
        ready.set()
    t0 = time.monotonic()
    end_at: float | None = None
    try:
        while True:
            now = time.monotonic()
            if end_at is not None and now >= end_at:
                break
            if end_at is None and (now - t0 >= seconds or (stop is not None and stop.is_set())):
                end_at = now + GRACE_S
            got = 0
            for r in recs:
                rows = r.pull()
                got += len(rows)
                if r is ev_rec and until_end and end_at is None:
                    for row in rows:
                        try:
                            ev = _strict_json(row[0])
                        except (ValueError, IndexError):
                            continue
                        if isinstance(ev, dict) and ev.get("type") == "end":
                            end_at = time.monotonic() + GRACE_S
            if not got:
                time.sleep(0.002)
    finally:
        for r in recs:
            r.close()
    desc = description or f"{CAPTURE_TOOL}: LSL stream {primary.info.name!r}"
    base = {"schema": LSL_SCHEMA, "fep": "FEP-0002", "description": desc,
            "capture": {"tool": CAPTURE_TOOL, "seconds": round(time.monotonic() - t0, 3)}}
    if is_dec:
        rows = [s for ch in primary.chunks for s in ch["samples"]]
        stamps = [t for ch in primary.chunks for t in ch["timestamps"]]
        return {**base, "kind": "decisions", "info_xml": sanitize_info_xml(primary.raw_xml),
                "samples": [r[0] for r in rows], "timestamps": stamps}
    inlets = {"primary": primary.spec()}
    if ev_rec is not None:
        inlets["events"] = ev_rec.spec()
    return {**base, "kind": "inlet", "route": "frames", "inlets": inlets}


def _lsl_received(sc: dict[str, Any]) -> list[dict[str, Any]]:
    """The NTS events that the reference LSL consumer reads from an ``inlet`` capture."""
    import itertools

    from fidetype.adapters.lsl import LSL_STATUS, LSLEventSource, LSLMapping
    from fidetype.conformance.profiles.fep0002 import _inlet

    inl = sc["inlets"]
    primary = _inlet(inl["primary"])
    events = _inlet(inl["events"]) if inl.get("events") else None
    settings = dict(sc.get("consumer_settings") or {})
    if "boundary_markers" in settings:
        settings["boundary_markers"] = tuple(settings["boundary_markers"])
    mapping = LSLMapping(merge_window_s=1e9, reconnect_timeout_s=1.0, reconnect_mode="inline", **settings)
    ticks = itertools.count()
    src = LSLEventSource(primary, events, mapping, clock=lambda: 1000.0 + next(ticks) * 1e-3)
    seen: list[dict[str, Any]] = []
    idle = 0
    for _ in range(100000):
        out = src.poll(0.0)
        seen += out
        if any(e.get("type") == "end" for e in out):
            break
        busy = any(getattr(r.inlet, "script", None) for r in src.readers)
        idle = 0 if (busy or out) else idle + 1
        if idle >= 3:
            break
    seen += src.drain()
    src.close()
    return [e for e in seen if e.get("type") != LSL_STATUS]


# --- WebSocket ------------------------------------------------------------------------------------


class _RecordingCore:
    """Wraps an :class:`~fidetype.adapters.ws.IngestCore`: records each open, message and close as a step."""

    def __init__(self, core: Any) -> None:
        self._core = core
        self.steps: list[dict[str, Any]] = []
        self.t0: float | None = None
        self.saw_end = False
        self.closed = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._core, name)

    def _at(self, now: float) -> float:
        if self.t0 is None:
            self.t0 = now
        at = round(now - self.t0, 6)
        if self.steps:
            at = max(at, self.steps[-1]["at"])
        return at

    def open(self, cid: int, subprotocols: Sequence[str] = (), authorization: str | None = None,
             now: float = 0.0) -> Any:
        # The Authorization header is never recorded (privacy).
        self.steps.append({"at": self._at(now), "conn": cid, "open": {"subprotocols": list(subprotocols)}})
        return self._core.open(cid, subprotocols, authorization, now)

    def message(self, cid: int, data: Any, now: float = 0.0) -> Any:
        step: dict[str, Any] = {"at": self._at(now), "conn": cid}
        if isinstance(data, (bytes, bytearray)):
            step["binary"] = True
        else:
            try:
                obj = _strict_json(data)
            except ValueError:
                obj = None
            if isinstance(obj, dict):
                if obj.get("type") == "ws_auth":
                    obj = {k: v for k, v in obj.items() if k != "token"}  # never record a token
                step["msg"] = obj
                evs = obj.get("events") if obj.get("type") == "ws_batch" else [obj]
                if isinstance(evs, list) and any(isinstance(e, dict) and e.get("type") == "end" for e in evs):
                    self.saw_end = True
            else:
                step["raw"] = data
        self.steps.append(step)
        return self._core.message(cid, data, now)

    def disconnect(self, cid: int, now: float = 0.0) -> Any:
        self.steps.append({"at": self._at(now), "conn": cid, "close": True})
        self.closed += 1
        return self._core.disconnect(cid, now)


def _ws_url(url: str) -> tuple[str, str, int, str]:
    u = urlsplit(url)
    if u.scheme not in ("ws", "wss") or not u.hostname or u.path not in ("/nts", "/decisions"):
        raise ValueError(f"--ws needs ws://HOST:PORT/nts (listen) or ws://HOST:PORT/decisions (subscribe), got {url!r}")
    return u.scheme, u.hostname, u.port or (443 if u.scheme == "wss" else 80), u.path


def capture_ws_ingest(host: str = "127.0.0.1", port: int = 0, seconds: float = 30.0, until_end: bool = True,
                      ready: Callable[[str], None] | None = None, stop: threading.Event | None = None,
                      description: str | None = None, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Listen on ``ws://host:port/nts`` and record the producers as a ``ws-scenario/1`` ``ingest`` capture.

    ``until_end``: stop when an ``end`` event arrived and every connection is closed. Else stop after
    ``seconds`` or when ``stop`` is set. ``ready(url)`` is called with the ``/nts`` URL when the server
    listens (``port`` 0 = a free port).
    """
    from fidetype.adapters.ws import PATH_INGEST, ServerSettings, WSServer

    log = log or (lambda m: None)
    server = WSServer(settings=ServerSettings(host=host, port=port))
    rec = _RecordingCore(server.core)
    server.core = rec  # type: ignore[assignment]
    server.start()
    url = f"ws://{host}:{server.port}{PATH_INGEST}"
    log(f"recording producers on {url}")
    if ready is not None:
        ready(url)
    t0 = time.monotonic()
    try:
        while True:
            server.poll(0.05)  # runs the time-outs and acks; the items are not needed
            if time.monotonic() - t0 >= seconds or (stop is not None and stop.is_set()):
                break
            if until_end and rec.saw_end and not server.conns and rec.closed:
                break
    finally:
        server.stop()
    if not rec.steps:
        raise CaptureError(f"no producer connected to {url} within {seconds} s")
    desc = description or f"{CAPTURE_TOOL}: WebSocket producers on {PATH_INGEST}"
    return {"schema": WS_SCHEMA, "kind": "ingest", "fep": "FEP-0004", "description": desc, "route": "frames",
            "capture": {"tool": CAPTURE_TOOL, "seconds": round(time.monotonic() - t0, 3)}, "steps": rec.steps}


def capture_ws_decisions(url: str, seconds: float = 30.0, from_seq: int | None = 1,
                         max_decisions: int | None = None, ready: threading.Event | None = None,
                         stop: threading.Event | None = None, description: str | None = None,
                         log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Subscribe to ``url`` (a ``/decisions`` path) and record every message as a ``subscribe`` capture.

    Stops after ``seconds``, after ``max_decisions`` final decisions, when ``stop`` is set (after a short
    grace), or when the server closes the connection. No reconnect: a capture records one session.
    """
    from fidetype.adapters.ws import BINDING_VERSION, SUBPROTOCOL, WS_SUBSCRIBE, dumps, require_websockets

    require_websockets()
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    log = log or (lambda m: None)
    msgs: list[Any] = []
    t0 = time.monotonic()
    end_at: float | None = None
    with connect(url, subprotocols=[SUBPROTOCOL], close_timeout=2.0) as c:
        req: dict[str, Any] = {"type": WS_SUBSCRIBE, "binding": BINDING_VERSION}
        if from_seq is not None:
            req["from_seq"] = from_seq
        c.send(dumps(req))
        log(f"subscribed to {url}")
        if ready is not None:
            ready.set()
        while True:
            now = time.monotonic()
            if end_at is not None and now >= end_at:
                break
            if end_at is None and (now - t0 >= seconds or (stop is not None and stop.is_set())):
                end_at = now + GRACE_S
            try:
                raw = c.recv(timeout=0.05)
            except TimeoutError:
                continue
            except ConnectionClosed:
                break
            if not isinstance(raw, str):
                continue
            try:
                msgs.append(_strict_json(raw))
            except ValueError:
                msgs.append(raw)
            if max_decisions is not None and sum(isinstance(m, dict) and m.get("type") == "trust_decision"
                                                 and m.get("is_final") is True for m in msgs) >= max_decisions:
                break
    if not msgs:
        raise CaptureError(f"no message from {url} within {seconds} s")
    desc = description or f"{CAPTURE_TOOL}: WebSocket subscriber of {urlsplit(url).path}"
    sc: dict[str, Any] = {"schema": WS_SCHEMA, "kind": "subscribe", "fep": "FEP-0004", "description": desc,
                          "capture": {"tool": CAPTURE_TOOL, "seconds": round(time.monotonic() - t0, 3)}}
    sc["from_seq"] = from_seq
    sc["messages"] = msgs
    return sc


def _ws_received(sc: dict[str, Any]) -> list[dict[str, Any]]:
    """The NTS events that the reference server core releases from an ``ingest`` capture (stream order)."""
    from fidetype.adapters.ws import WS_STATUS, IngestCore, IngestSettings

    core = IngestCore(IngestSettings(**{k: v for k, v in (sc.get("settings") or {}).items() if k != "token"}))
    out: list[dict[str, Any]] = []

    def take(eff: Any) -> None:
        out.extend(ev for _, ev in eff.items if ev.get("type") != WS_STATUS)

    at = 0.0
    for st in sc["steps"]:
        at = float(st.get("at", at))
        take(core.tick(at))
        cid = st["conn"]
        if "open" in st:
            take(core.open(cid, st["open"].get("subprotocols", []), None, at))
        elif "msg" in st:
            take(core.message(cid, st["msg"], at))
        elif "raw" in st:
            take(core.message(cid, st["raw"], at))
        elif "binary" in st:
            take(core.message(cid, b"\x00", at))
        elif "close" in st or "drop" in st:
            take(core.disconnect(cid, at))
    take(core.finish(at))
    return out


# --- received stream ------------------------------------------------------------------------------


def received(sc: dict[str, Any]) -> list[dict[str, Any]]:
    """What the reference consumer reads from a capture: NTS events, or ``trust_decision`` events."""
    schema, kind = sc.get("schema"), sc.get("kind")
    if schema == LSL_SCHEMA and kind == "inlet":
        return _lsl_received(sc)
    if schema == LSL_SCHEMA and kind == "decisions":
        evs = []
        for s in sc.get("samples", []):
            try:
                ev = _strict_json(s)
            except ValueError:
                continue
            if isinstance(ev, dict) and ev.get("type") == "trust_decision":
                evs.append(ev)
        return evs
    if schema == WS_SCHEMA and kind == "ingest":
        return _ws_received(sc)
    if schema == WS_SCHEMA and kind == "subscribe":
        return [m for m in sc.get("messages", []) if isinstance(m, dict) and m.get("type") == "trust_decision"]
    raise ValueError(f"not a capture: schema {schema!r}, kind {kind!r}")


def _jsonable(ev: dict[str, Any]) -> dict[str, Any]:
    """-inf log-probs become null (spec 6.2); other non-finite numbers stay an error."""
    if ev.get("type") == "frame" and isinstance(ev.get("log_probs"), list):
        ev = {**ev, "log_probs": [None if (isinstance(v, float) and v == -math.inf) else v for v in ev["log_probs"]]}
    return ev


def write_received(sc: dict[str, Any], path: str | Path) -> Path:
    """Write :func:`received` as JSON Lines (one event per line)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for ev in received(sc):
            f.write(json.dumps(_jsonable(ev), ensure_ascii=False, allow_nan=False) + "\n")
    return p


# --- command line (nts-conform capture) -----------------------------------------------------------


def cmd_capture(a: Any) -> int:
    """``nts-conform capture``: exit 0 = capture written; usage, resolve or empty-capture errors = exit 2."""
    from fidetype.adapters.lsl import LSLResolveError, LSLUnavailableError
    from fidetype.adapters.ws import WSUnavailableError
    from fidetype.conformance.nts_conform import InputError

    try:
        return _capture(a)
    except (ValueError, CaptureError, LSLResolveError, LSLUnavailableError, WSUnavailableError, TimeoutError,
            OSError) as e:
        raise InputError(f"capture: {e}") from e


def _capture(a: Any) -> int:
    import sys

    def log(m: str) -> None:
        print(f"[nts-conform capture] {m}", file=sys.stderr)

    if bool(a.lsl) == bool(a.ws):
        raise ValueError("give exactly one of --lsl QUERY or --ws URL")
    if a.lsl:
        sc = capture_lsl(a.lsl, seconds=a.seconds, until_end=not a.no_wait_end, events=a.events,
                         resolve_timeout=a.resolve_timeout, log=log)
    else:
        scheme, host, port, path = _ws_url(a.ws)
        if path == "/nts":
            if scheme != "ws":
                raise ValueError("the recording server speaks plain ws:// (use a loopback address)")
            if host not in ("127.0.0.1", "localhost", "::1"):
                log(f"WARNING: listening on {host} (not loopback)")
            sc = capture_ws_ingest(host, port, seconds=a.seconds, until_end=not a.no_wait_end, log=log)
        else:
            sc = capture_ws_decisions(a.ws, seconds=a.seconds, from_seq=a.from_seq, max_decisions=a.max_decisions,
                                      log=log)
    out = write_capture(sc, a.out)
    n = (sum(len(c["samples"]) for i in sc.get("inlets", {}).values() for c in i["chunks"]) if sc["kind"] == "inlet"
         else len(sc.get("samples") or sc.get("steps") or sc.get("messages") or []))
    log(f"wrote {out} ({sc['kind']} capture, {n} samples/steps/messages)")
    if a.received:
        log(f"wrote {write_received(sc, a.received)} (what the reference consumer reads)")
    return 0


def add_parser(sub: Any) -> None:
    cp = sub.add_parser("capture", help="record an LSL or WebSocket capture from a live producer (scenario JSON)")
    g = cp.add_mutually_exclusive_group(required=True)
    g.add_argument("--lsl", help='LSL stream: a name, or "type=NTS,source_id=..." (keys name, type, source_id)')
    g.add_argument("--ws", help="ws://HOST:PORT/nts (listen; your producer connects) or ws://HOST:PORT/decisions "
                                "(subscribe to your server)")
    cp.add_argument("--out", required=True, help="capture file (.json)")
    cp.add_argument("--seconds", type=float, default=30.0, help="longest capture time (default 30)")
    cp.add_argument("--no-wait-end", action="store_true",
                    help="do not stop at the end event; record for --seconds")
    cp.add_argument("--events", choices=("auto", "none"), default="auto",
                    help="LSL: also record the events stream named by desc/fidetype/events_source_id (default auto)")
    cp.add_argument("--resolve-timeout", type=float, default=10.0)
    cp.add_argument("--from-seq", type=int, default=1, help="WebSocket /decisions: from_seq of the subscribe")
    cp.add_argument("--max-decisions", type=int, help="WebSocket /decisions: stop after N final decisions")
    cp.add_argument("--received", help="also write what the reference consumer reads (JSON Lines)")
    cp.set_defaults(func=cmd_capture)


__all__ = ["CaptureError", "capture_lsl", "capture_ws_decisions", "capture_ws_ingest", "parse_query", "received",
           "sanitize_info_xml", "write_capture", "write_received"]
