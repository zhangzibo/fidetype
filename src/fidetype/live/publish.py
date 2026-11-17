"""Publish the NTS output of ``fidetype live`` over a binding in real time (roadmap P14-16).

``fidetype live --publish TARGET`` (repeat the option for more targets) sends each event that the
run writes to the target at the moment it is written. The NTS stream (header, ``frame``, final
``hypothesis``, ``segment_end``, ``lsl_status``, ``end``) goes on the stream channel; the
``trust_decision`` events go on the decisions channel only, never into the NTS stream (FEP-0001
section 3 r4: no ``trust_decision`` in an input stream). ``--out`` still writes the file.

Targets. This module adds no new outlet code: it feeds the outlets of
:mod:`fidetype.adapters.lsl` and :mod:`fidetype.adapters.ws`.

``lsl`` or ``lsl:NAME`` (FEP-0002, ``nts-lsl/0.1``; needs ``[lsl]``)
    :class:`~fidetype.adapters.lsl.NTSOutlet`: the frames stream ``NAME`` (type ``NTS``, one channel
    per key) and the events stream ``NAME.events`` (type ``Markers``). Plus
    :class:`~fidetype.adapters.lsl.DecisionOutlet`: the decisions stream ``NAME.decisions``
    (``role = trust_decisions``). Default ``NAME``: ``fidetype.live``.
``ws://HOST:PORT/nts`` (FEP-0004, ``nts-ws/0.1``; needs ``[ws]``)
    :class:`~fidetype.adapters.ws.WSProducer`: ``fidetype live`` connects to a server (for example
    ``python -m fidetype.adapters.ws run``) and sends its NTS stream, with resend on resume.
``ws://HOST:PORT/decisions`` (FEP-0004 section 7)
    :class:`~fidetype.adapters.ws.WSServer` with an :class:`~fidetype.adapters.ws.OutputHub`:
    ``fidetype live`` serves its trust decisions to subscribers (``ws_seq`` numbers, resume with
    ``from_seq``). Port 0 = a free port (the log gives the URL).

``--publish-wait S`` waits up to S seconds for a consumer on each target before the decode starts.
``--publish-linger S`` keeps the outlets open S seconds after the end, so consumers get the last
events. A target that fails (for example the server went away) stops with one log line; the decode
and the ``--out`` file go on.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import io
import json
import time
from typing import IO, Any, Callable
from urllib.parse import urlsplit

__all__ = ["DEFAULT_LSL_NAME", "EventTee", "LSLPublisher", "WSDecisionsPublisher", "WSStreamPublisher",
           "make_publisher", "parse_target"]

DEFAULT_LSL_NAME = "fidetype.live"


def parse_target(spec: str) -> tuple[str, str]:
    """``(kind, value)`` of a ``--publish`` value: ``("lsl", NAME)``, ``("ws-nts", URL)`` or ``("ws-decisions", URL)``."""
    s = spec.strip()
    if s == "lsl":
        return "lsl", DEFAULT_LSL_NAME
    if s.startswith("lsl:"):
        name = s[4:].strip()
        if not name:
            raise ValueError("lsl:NAME needs a stream name")
        return "lsl", name
    u = urlsplit(s)
    if u.scheme in ("ws", "wss") and u.hostname:
        try:
            u.port
        except ValueError as e:
            raise ValueError(f"bad port in {spec!r}") from e
        if u.path == "/nts":
            return "ws-nts", s
        if u.path == "/decisions":
            if u.scheme == "wss":
                raise ValueError("serving /decisions over wss:// is not supported here; use ws:// on 127.0.0.1")
            if u.port is None:
                raise ValueError(f"{spec!r}: give a port (0 = a free port)")
            return "ws-decisions", s
    raise ValueError(f"unknown --publish target {spec!r} (use lsl, lsl:NAME, ws://HOST:PORT/nts or "
                     "ws://HOST:PORT/decisions)")


def _config_id(header: dict[str, Any]) -> str | None:
    live = (header.get("meta") or {}).get("fidetype.live") or {}
    cid = live.get("trust_config_id") if isinstance(live, dict) else None
    return cid if isinstance(cid, str) else None


class LSLPublisher:
    """``lsl:NAME``: frames + events streams (:class:`~fidetype.adapters.lsl.NTSOutlet`) and a decisions stream.

    ``same_clock``: the stream times are LSL times already (an LSL source); the timestamps keep them.
    Else the first frame maps to the LSL time of its arrival.
    """

    kind = "lsl"

    def __init__(self, name: str = DEFAULT_LSL_NAME, same_clock: bool = False, decisions: bool = True) -> None:
        from fidetype.adapters.lsl import require_pylsl

        require_pylsl()
        self.name = name
        self.same_clock = same_clock
        self.with_decisions = decisions
        self.outlet: Any = None
        self.decisions: Any = None
        self.sent = 0

    @property
    def target(self) -> str:
        return f"lsl:{self.name}"

    def describe(self) -> str:
        s = f"LSL streams {self.name} (NTS frames) + {self.name}.events (Markers)"
        return s + (f" + {self.name}.decisions (trust decisions)" if self.with_decisions else "")

    def event(self, ev: dict[str, Any]) -> None:
        from fidetype.adapters.lsl import DecisionOutlet, NTSOutlet

        typ = ev.get("type")
        if typ == "header" and self.outlet is None:
            self.outlet = NTSOutlet(ev, self.name, frames=True, events=True)
            if self.with_decisions:
                self.decisions = DecisionOutlet(self.name + ".decisions", config_id=_config_id(ev))
            return
        if self.outlet is None:
            raise ValueError("the stream must start with a header event")
        if typ == "trust_decision":  # decisions go on the decisions stream only (FEP-0001 section 3 r4)
            if self.decisions is not None:
                self.decisions.push(ev)
                self.sent += 1
            return
        if self.outlet.base is None and self.same_clock and isinstance(ev.get("t"), (int, float)):
            self.outlet.start_clock(float(ev["t"]), base=float(ev["t"]))
        self.outlet.push(ev)
        self.sent += 1

    def wait(self, timeout: float) -> bool:
        if self.outlet is None:
            return False
        t0 = time.monotonic()
        ok = self.outlet.wait_for_consumers(timeout)
        if self.decisions is not None:
            ok = self.decisions.outlet.wait_for_consumers(max(0.0, timeout - (time.monotonic() - t0))) and ok
        return ok

    def close(self) -> None:
        if self.outlet is not None:
            self.outlet.close()
        self.outlet = None
        self.decisions = None


class WSStreamPublisher:
    """``ws://HOST:PORT/nts``: send the NTS stream to a server with :class:`~fidetype.adapters.ws.WSProducer`."""

    kind = "ws-nts"

    def __init__(self, url: str, stream_id: str | None = None, token: str | None = None,
                 log: Callable[[str], None] | None = None) -> None:
        from fidetype.adapters.ws import require_websockets

        require_websockets()
        self.url = url
        self.stream_id = stream_id
        self.token = token
        self.log = log
        self.producer: Any = None
        self.sent = 0

    @property
    def target(self) -> str:
        return self.url

    def describe(self) -> str:
        return f"WebSocket producer to {self.url}"

    def event(self, ev: dict[str, Any]) -> None:
        from fidetype.adapters.ws import WSProducer

        if ev.get("type") == "header" and self.producer is None:
            self.producer = WSProducer(self.url, ev, stream_id=self.stream_id, token=self.token, log=self.log).connect()
            return
        if self.producer is None:
            raise ValueError("the stream must start with a header event")
        if ev.get("type") == "trust_decision":  # not in an input stream (FEP-0001 section 3 r4)
            return
        self.producer.send(ev)
        self.sent += 1

    def wait(self, timeout: float) -> bool:
        return self.producer is not None  # connected at the header

    def close(self) -> None:
        if self.producer is not None:
            try:
                self.producer.close()
            finally:
                self.producer = None


class WSDecisionsPublisher:
    """``ws://HOST:PORT/decisions``: serve the trust decisions on a :class:`~fidetype.adapters.ws.WSServer`."""

    kind = "ws-decisions"

    def __init__(self, url: str, log: Callable[[str], None] | None = None) -> None:
        from fidetype.adapters.ws import require_websockets

        require_websockets()
        u = urlsplit(url)
        self.host = u.hostname or "127.0.0.1"
        self.port = int(u.port or 0)
        self.log = log or (lambda m: None)
        self.hub: Any = None
        self.server: Any = None
        self.sent = 0

    @property
    def target(self) -> str:
        return self.url

    @property
    def url(self) -> str:
        port = self.server.port if self.server is not None else self.port
        return f"ws://{self.host}:{port}/decisions"

    def describe(self) -> str:
        return f"WebSocket /decisions channel on {self.url}"

    def event(self, ev: dict[str, Any]) -> None:
        from fidetype.adapters.ws import OutputHub, ServerSettings, WSServer

        typ = ev.get("type")
        if typ == "header" and self.server is None:
            extra: dict[str, Any] = {"spec": "FEP-0001"}
            cid = _config_id(ev)
            if cid:
                extra["config_id"] = cid
            self.hub = OutputHub("decisions", welcome_extra=extra)
            self.server = WSServer(settings=ServerSettings(host=self.host, port=self.port), decisions=self.hub).start()
            self.log(f"serving trust decisions on {self.url}")
            return
        if self.hub is None:
            raise ValueError("the stream must start with a header event")
        if typ == "trust_decision":
            self.hub.publish(ev)
            self.sent += 1

    def wait(self, timeout: float) -> bool:
        t0 = time.monotonic()
        while self.hub is not None and not self.hub.has_subscribers:
            if time.monotonic() - t0 >= timeout:
                return False
            time.sleep(0.02)
        return self.hub is not None

    def close(self) -> None:
        if self.server is not None:
            try:
                self.server.stop()
            finally:
                self.server = None


def make_publisher(spec: str, *, same_clock: bool = False, log: Callable[[str], None] | None = None) -> Any:
    """The publisher of one ``--publish`` value. Raises ValueError (bad value) or ImportError (missing extra)."""
    kind, value = parse_target(spec)
    if kind == "lsl":
        return LSLPublisher(value, same_clock=same_clock)
    if kind == "ws-nts":
        return WSStreamPublisher(value, log=log)
    return WSDecisionsPublisher(value, log=log)


class EventTee(io.TextIOBase):
    """A text target for :class:`~fidetype.writer.StreamWriter` that copies each event to the publishers.

    The writer writes one JSON line per event. The tee writes the line to ``file`` (if any) and gives
    the parsed event to each publisher. A publisher that raises an error is stopped (one log line);
    the others and the file go on.
    """

    def __init__(self, publishers: list[Any], file: IO[str] | None = None,
                 log: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self.publishers = list(publishers)
        self.file = file
        self.log = log or (lambda m: None)
        self.failed: dict[str, str] = {}
        self._buf = ""

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:
        if self.file is not None:
            self.file.write(s)
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._send(json.loads(line))
        return len(s)

    def flush(self) -> None:
        if self.file is not None:
            self.file.flush()

    def _send(self, ev: dict[str, Any]) -> None:
        for p in list(self.publishers):
            try:
                p.event(ev)
            except Exception as e:  # noqa: BLE001 - a broken target must not stop the decode
                self.failed[p.target] = f"{type(e).__name__}: {e}"
                self.log(f"publish target {p.target} failed ({type(e).__name__}: {e}); it stops, the decode goes on")
                self.publishers.remove(p)
                try:
                    p.close()
                except Exception:  # noqa: BLE001
                    pass

    def wait(self, timeout: float) -> dict[str, bool]:
        """Wait up to ``timeout`` seconds in total for a consumer on each publisher."""
        t0 = time.monotonic()
        return {p.target: p.wait(max(0.0, timeout - (time.monotonic() - t0))) for p in self.publishers}

    def finish(self, linger_s: float = 0.0) -> dict[str, Any]:
        """Wait ``linger_s`` (consumers get the last events), close the publishers and the file; return counts."""
        if self.publishers and linger_s > 0:
            time.sleep(linger_s)
        out: dict[str, Any] = {}
        for p in self.publishers:
            try:
                p.close()
                out[p.target] = {"sent": p.sent}
            except Exception as e:  # noqa: BLE001
                self.failed[p.target] = f"{type(e).__name__}: {e}"
        for t, why in self.failed.items():
            out[t] = {"failed": why}
        if self.file is not None and not self.file.closed:
            self.file.close()
        return out
