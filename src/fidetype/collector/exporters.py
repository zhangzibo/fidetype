"""Exporters of the collector (FEP-0006 section 5): they write items out. They never change an item.

- ``jsonl``: a JSON Lines file. With the default ``types = ["trust_decision"]`` it is a decision
  log (spec 6.4: no header, decisions only). A file never mixes decisions and input events (TD-11).
- ``stdout``: JSON Lines on standard output (logs go to standard error).
- ``websocket``: the ``/decisions`` channel (FEP-0004, WS-D1 ... WS-D4) of a websocket receiver's
  server. Each decision gets the channel ``ws_seq``. A slow subscriber is closed (WS-D4); it never
  slows the pipeline.

Status items (``ws_status``) are internal and never exported.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, TextIO

from fidetype.collector.receivers import STATUS, Item


def dumps(ev: dict[str, Any]) -> str:
    return json.dumps(ev, ensure_ascii=False, allow_nan=False)


class Exporter:
    type = "exporter"

    def __init__(self, name: str, log: Callable[[str], None]) -> None:
        self.name = name
        self.log = log
        self.counts: dict[str, int] = {"exported": 0}

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
