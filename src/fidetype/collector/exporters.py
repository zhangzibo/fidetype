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

Status items (``ws_status``) are internal and never exported.
"""

from __future__ import annotations

import json
import sys
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
