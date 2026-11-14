"""Exporters of the collector (FEP-0006 section 5): they write items out. They never change an item.

- ``jsonl``: a JSON Lines file. With the default ``types = ["trust_decision"]`` it is a decision
  log (spec 6.4: no header, decisions only). A file never mixes decisions and input events (TD-11).
- ``stdout``: JSON Lines on standard output (logs go to standard error).
- ``websocket``: the ``/decisions`` channel (FEP-0004, WS-D1 ... WS-D4). With ``receiver`` it is
  served by that websocket receiver's server. Without ``receiver`` the exporter starts its own
  **standalone** server that serves ``/decisions`` only (``/nts`` and ``/events`` give 404), for
  example for a file replay demo. Each decision gets the channel ``ws_seq``. A slow subscriber is
  closed (WS-D4); it never slows the pipeline. ``linger_s`` keeps a standalone server open after
  the input is done, so a late subscriber can still read the decisions (``from_seq = 1``).

- ``lsl``: an LSL decisions outlet (spec 8.2.6, LSL-X1 ... LSL-X3). Option ``no_text`` removes the
  decoded text (SEC-7): the one exporter option that changes an item (FEP-0006 4, rule 1).

Status items (``ws_status``) are internal and never exported.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, TextIO

from fidetype.adapters import ws as W
from fidetype.collector.receivers import STATUS, Item


def dumps(ev: dict[str, Any]) -> str:
    return json.dumps(ev, ensure_ascii=False, allow_nan=False)


class Exporter:
    type = "exporter"

    def __init__(self, name: str, log: Callable[[str], None]) -> None:
        self.name = name
        self.log = log
        self.counts: dict[str, int] = {"exported": 0}
        #: Seconds the collector waits after the input is done, before it stops (standalone servers).
        self.linger_s = 0.0

    def start(self) -> None:
        pass

    def export(self, items: list[Item]) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass

    def stats(self) -> dict[str, Any]:
        return {"type": self.type, **self.counts}


class _LinesExporter(Exporter):
    def __init__(self, name: str, log: Callable[[str], None], types: list[str]) -> None:
        super().__init__(name, log)
        self.types = None if types == ["*"] else set(types)
        self.fh: TextIO | None = None

    def wants(self, ev: dict[str, Any]) -> bool:
        t = ev.get("type")
        return t != STATUS and (self.types is None or t in self.types)

    def export(self, items: list[Item]) -> None:
        if self.fh is None:
            return
        n = 0
        for _, ev in items:
            if self.wants(ev):
                self.fh.write(dumps(ev) + "\n")
                n += 1
        if n:
            self.fh.flush()
            self.counts["exported"] += n


class JsonlExporter(_LinesExporter):
    type = "jsonl"

    def __init__(self, name: str, log: Callable[[str], None], path: Path, types: list[str],
                 append: bool = False) -> None:
        super().__init__(name, log, types)
        self.path = path
        self.append = append

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a" if self.append else "w", encoding="utf-8", newline="\n")

    def stop(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None


class StdoutExporter(_LinesExporter):
    type = "stdout"

    def __init__(self, name: str, log: Callable[[str], None], types: list[str], stream: TextIO | None = None) -> None:
        super().__init__(name, log, types)
        self._stream = stream

    def start(self) -> None:
        self.fh = self._stream or sys.stdout


class WebSocketExporter(Exporter):
    """Publish decisions on the ``/decisions`` path of a websocket receiver (its :class:`OutputHub`)."""

    type = "websocket"

    def __init__(self, name: str, log: Callable[[str], None], hub: Any) -> None:
        super().__init__(name, log)
        self.hub = hub

    def export(self, items: list[Item]) -> None:
        for _, ev in items:
            if ev.get("type") == "trust_decision":
                self.hub.publish(ev)
                self.counts["exported"] += 1

    def stats(self) -> dict[str, Any]:
        return {**super().stats(), "subscribers": len(self.hub.subs),
                "slow_subscribers_closed": self.hub.dropped_subscribers}


class _DecisionsOnlyServer(W.WSServer):
    """A :class:`fidetype.adapters.ws.WSServer` that serves ``/decisions`` only (no ``/nts`` input)."""

    def _process_request(self, connection: Any, request: Any) -> Any:
        path = request.path.split("?", 1)[0]
        if path != W.PATH_DECISIONS:
            return connection.respond(404, "this server serves /decisions only\n")
        return super()._process_request(connection, request)


class StandaloneWebSocketExporter(WebSocketExporter):
    """A ``websocket`` exporter with its own ``/decisions`` server (no websocket receiver needed).

    The server is the reference :class:`fidetype.adapters.ws.WSServer` (subprotocol, token, origins,
    TLS, ``ws_seq``, replay with ``from_seq``, slow-subscriber close), limited to ``/decisions``.
    The token comes from an environment variable and never appears in an output.
    """

    type = "websocket"

    def __init__(self, name: str, log: Callable[[str], None], host: str = "127.0.0.1", port: int = W.DEFAULT_PORT,
                 token: str | None = None, origins: list[str] | None = None, ssl: Any = None,
                 linger_s: float = 0.0) -> None:
        hub = W.OutputHub("decisions", welcome_extra={"spec": "FEP-0001"})
        super().__init__(name, log, hub)
        settings = W.ServerSettings(host=host, port=port, origins=origins, token=token, ssl=ssl)
        self.server = _DecisionsOnlyServer(None, settings, decisions=hub,
                                           log=lambda m: log(f"exporters.{name}: {m}"))
        self.host = host
        self.linger_s = float(linger_s)

    @property
    def port(self) -> int:
        return self.server.port

    def start(self) -> None:
        from fidetype.collector.config import is_loopback

        if not is_loopback(self.host) and self.server.settings.ssl is None:
            self.log(f"exporters.{self.name}: WARNING: /decisions listens beyond localhost without TLS "
                     "(WS-T4 needs wss://)")
        if not is_loopback(self.host) and not self.server.settings.token:
            self.log(f"exporters.{self.name}: WARNING: /decisions listens beyond localhost without a token "
                     "(set token_env); decoded text is personal data (SEC-7)")
        self.server.start()

    def stop(self) -> None:
        self.server.stop()

    def stats(self) -> dict[str, Any]:
        # No address, host name or token here (WS-T3).
        return {**super().stats(), "standalone": True}


def without_text(ev: dict[str, Any]) -> dict[str, Any]:
    """A copy of a ``trust_decision`` without ``shown`` and with ``redaction`` (the ``no_text`` option, SEC-7)."""
    if "shown" not in ev:
        return ev
    out = {k: v for k, v in ev.items() if k != "shown"}
    out.setdefault("redaction", {"mode": "drop"})
    return out


class LSLExporter(Exporter):
    """Publish decisions on an LSL decisions outlet (spec 8.2.6, LSL-X1 ... LSL-X3).

    It reuses :class:`fidetype.adapters.lsl.DecisionOutlet`: type ``Markers``, 1 string channel,
    irregular rate, desc keys ``role = trust_decisions``, ``event_type = trust_decision``,
    ``spec = FEP-0001``, ``binding = nts-lsl/0.1`` and ``config_id`` (from the option, else from the
    trust processor of the pipeline). One sample is one ``trust_decision`` as JSON; the sample
    timestamp is the emission time (LSL-X2). Subscribers MUST NOT act on ``is_final = false`` (LSL-X3).

    LSL has no access control: every host on the network can read the outlet. ``no_text = true``
    removes ``shown`` from each decision and adds ``redaction = {"mode": "drop"}`` (SEC-7, the same
    as a ``redact`` processor with ``mode = "drop"``). Without it the exporter logs a warning at start.
    The exporter writes no host name (LSL-C3); liblsl itself announces the host of the outlet.
    """

    type = "lsl"

    def __init__(self, name: str, log: Callable[[str], None], stream_name: str | None = None,
                 source_id: str | None = None, config_id: str | None = None, no_text: bool = False,
                 outlet_factory: Callable[..., Any] | None = None) -> None:
        super().__init__(name, log)
        from fidetype.adapters import lsl as L

        self.stream_name = stream_name or L.DECISIONS_STREAM_NAME
        self.source_id = source_id
        self.config_id = config_id
        self.no_text = no_text
        self._factory = outlet_factory or L.DecisionOutlet
        self.outlet: Any = None
        self.counts.update(text_removed=0)

    def start(self) -> None:
        self.outlet = self._factory(self.stream_name, source_id=self.source_id, config_id=self.config_id)
        if not self.no_text:
            self.log(f"exporters.{self.name}: WARNING: the LSL decisions outlet carries decoded text, and every "
                     "host on the network can read it (SEC-7); set no_text = true or add a redact processor")

    def export(self, items: list[Item]) -> None:
        if self.outlet is None:
            return
        for _, ev in items:
            if ev.get("type") != "trust_decision":
                continue
            if self.no_text and "shown" in ev:
                ev = without_text(ev)
                self.counts["text_removed"] += 1
            self.outlet.push(ev)
            self.counts["exported"] += 1

    #: At stop, wait this long before the outlet goes away while a subscriber is connected (seconds).
    #: liblsl sends asynchronously: without the wait, a subscriber can miss the last decisions.
    FLUSH_S = 0.5

    def stop(self) -> None:
        if self.outlet is None:
            return
        lsl_outlet = getattr(self.outlet, "outlet", None)
        try:
            if self.counts["exported"] and lsl_outlet is not None and lsl_outlet.have_consumers():
                time.sleep(self.FLUSH_S)
        except Exception:  # noqa: BLE001 - best effort at shutdown
            pass
        self.outlet = None  # liblsl destroys the outlet with the object

    def stats(self) -> dict[str, Any]:
        # Counters only: no stream name, host name or address (LSL-C3).
        return {**super().stats(), "no_text": self.no_text}
