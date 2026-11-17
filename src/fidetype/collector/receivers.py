"""Receivers of the collector (FEP-0006 section 3): they turn a source into ``(stream_id, event)`` items.

An item is a pair ``(stream_id, event)``. ``event`` is an NTS event (a
dict with a string ``type``) or a stream-status item of type
``ws_status`` (the same control item that :class:`fidetype.adapters.ws.IngestCore`
emits). Status values used here:

``gap``     events are missing inside the stream (the open utterance is cut);
``lost``    the stream stopped inside an utterance (the open utterance is cut);
``closed``  the stream is complete; the trust layer may close its last utterance.

The processors never see a transport. A receiver never drops an event
silently: an event that it cannot read becomes a ``gap`` status.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from fidetype.adapters import ws as W

Item = tuple[str, dict[str, Any]]
STATUS = W.WS_STATUS


def status(sid: str, value: str, detail: str = "") -> Item:
    ev: dict[str, Any] = {"type": STATUS, "status": value, "stream": sid}
    if detail:
        ev["detail"] = detail
    return sid, ev


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


class Receiver:
    """Base class. ``done`` is True when the receiver has no more input (a finite source)."""

    type = "receiver"

    def __init__(self, name: str, log: Callable[[str], None]) -> None:
        self.name = name
        self.log = log
        self.done = False
        self.counts: dict[str, int] = {"items": 0, "streams": 0, "ended_streams": 0}

    def start(self) -> None:
        pass

    def poll(self, timeout: float) -> list[Item]:
        raise NotImplementedError

    def finish(self) -> list[Item]:
        return []

    def stop(self) -> None:
        pass

    def stats(self) -> dict[str, Any]:
        return {"type": self.type, "done": self.done, **self.counts}


class FileReceiver(Receiver):
    """JSON Lines files (spec 8.1.1), one stream per file, read in order; optional tail mode.

    - Empty lines are skipped (GEN-6). Lines after ``end`` are ignored and counted (GEN-7).
    - A line that is not a JSON object with a string ``type`` becomes a ``gap`` status: the open
      utterance is cut, so no final decision can come from a part of it.
    - End of file: after ``end`` the stream is ``closed``. Without ``end``: ``eof = "close"``
      (default; the same as ``fidetype trust``, spec GEN-8 allows a stream without ``end``) closes
      the stream, logs one warning for that stream and counts it (``closed_without_end``);
      ``eof = "cut"`` treats it as a loss (no final decision on the open utterance).
    - ``follow = true`` (tail mode): at the end of the file the receiver waits for new lines. When no
      line comes for ``idle_timeout_s`` and the stream has no ``end``, the stream is **lost** (cut).
    - Back-pressure: at most ``batch`` lines per poll. The pipeline reads the next lines only after
      the processors and exporters took the last ones; nothing is dropped.
    - The stream id is ``stream_id`` (one file only) or ``<receiver>-<index>``. The file name is not
      used: it can hold personal data (SEC-6).
    - An ``.npz`` file (spec 6.1) is read whole with the reference reader (``allow_pickle=False``)
      and becomes ``header``, one ``frame`` per row and ``end``. A file that the reader cannot load
      becomes a ``lost`` status (no event of it reaches a processor). No tail mode for NPZ.
    """

    type = "file"

    def __init__(self, name: str, paths: list[Path], log: Callable[[str], None], follow: bool = False,
                 eof: str = "close", batch: int = 256, idle_timeout_s: float = 10.0, poll_interval_s: float = 0.05,
                 stream_id: str | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(name, log)
        self.paths = list(paths)
        self.follow = follow
        self.eof = eof
        self.batch = batch
        self.idle_timeout_s = idle_timeout_s
        self.poll_interval_s = poll_interval_s
        self.stream_id = stream_id
        self.clock = clock
        self.index = -1
        self.fh: Any = None
        self.sid = ""
        self.partial = ""
        self.ended = False
        self.last_data = 0.0
        self.npz: list[Item] | None = None
        self.counts.update(lines=0, bad_lines=0, lines_after_end=0, cut_streams=0, closed_without_end=0)

    def start(self) -> None:
        for p in self.paths:
            if not p.is_file():
                raise FileNotFoundError(f"receivers.{self.name}: input file not found: {p}")
        self._next_file()

    def _next_file(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None
        self.index += 1
        if self.index >= len(self.paths):
            self.done = True
            return
        self.sid = self.stream_id or f"{self.name}-{self.index}"
        self.npz = None
        self.partial = ""
        self.ended = False
        if self.paths[self.index].suffix.lower() == ".npz":
            self.npz = self._npz_items(self.paths[self.index])
            self.counts["streams"] += 1
            return
        self.fh = open(self.paths[self.index], "r", encoding="utf-8", newline="")
        self.partial = ""
        self.ended = False
        self.last_data = self.clock()
        self.counts["streams"] += 1

    def _line(self, line: str, out: list[Item]) -> None:
        self.counts["lines"] += 1
        if not line.strip():
            return
        if self.ended:
            self.counts["lines_after_end"] += 1
            return
        try:
            ev = json.loads(line, parse_constant=_reject_constant)
            if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
                raise ValueError("not a JSON object with a string type")
        except ValueError as e:
            self.counts["bad_lines"] += 1
            self.log(f"receivers.{self.name}: stream {self.sid}: line {self.counts['lines']} unreadable ({e}); "
                     "the open utterance is cut")
            out.append(status(self.sid, "gap", "unreadable line"))
            return
        if ev["type"] == "end":
            self.ended = True
            self.counts["ended_streams"] += 1
        out.append((self.sid, ev))

    def _close_stream(self, out: list[Item], cut: bool, why: str) -> None:
        if cut and not self.ended:
            self.counts["cut_streams"] += 1
            self.log(f"receivers.{self.name}: stream {self.sid} {why}; its open utterance gets no decision")
            out.append(status(self.sid, "lost", why))
        elif not self.ended:
            # eof = "close": GEN-8 allows a stream without end, but a truncated file looks the same.
            self.counts["closed_without_end"] += 1
            self.log(f"receivers.{self.name}: WARNING: stream {self.sid} ended without an end event; it is "
                     "closed (eof = \"close\"), so its last utterance can get a final decision. If the file can "
                     "be cut short, set eof = \"cut\"")
        out.append(status(self.sid, "closed"))
        self._next_file()

    def _npz_items(self, path: Path) -> list[Item]:
        """The events of an NPZ stream (header, frames, end), or a ``lost`` status if it cannot be read."""
        import math

        from fidetype.conformance.io import read_npz

        raw = read_npz(path)
        lp, ft = raw.log_probs, raw.frame_times
        if raw.issues or lp is None or ft is None or lp.ndim != 2 or ft.shape != (lp.shape[0],):
            why = raw.issues[0].message if raw.issues else "log_probs / frame_times missing or of the wrong shape"
            self.counts["bad_lines"] += 1
            self.log(f"receivers.{self.name}: stream {self.sid}: NPZ file unreadable ({why})")
            return [status(self.sid, "lost", "unreadable NPZ file")]
        hdr = {k: v for k, v in raw.header.items() if not k.startswith("_")}
        items: list[Item] = [(self.sid, {"type": "header", **hdr})]
        items += [(self.sid, {"type": "frame", "t": float(t),
                              "log_probs": [None if v == -math.inf else float(v) for v in row]})
                  for t, row in zip(ft, lp)]
        items.append((self.sid, {"type": "end"}))
        return items

    def _poll_npz(self) -> list[Item]:
        assert self.npz is not None
        out, self.npz = self.npz[: self.batch], self.npz[self.batch:]
        if not self.npz:
            if out and out[-1][1].get("type") == "end":
                self.counts["ended_streams"] += 1
            out.append(status(self.sid, "closed"))
            self.npz = None
            self._next_file()
        self.counts["items"] += len(out)
        return out

    def poll(self, timeout: float) -> list[Item]:
        out: list[Item] = []
        if self.done:
            return out
        if self.npz is not None:
            return self._poll_npz()
        n = 0
        while n < self.batch:
            chunk = self.fh.readline()
            if not chunk:
                break
            self.last_data = self.clock()
            if not chunk.endswith("\n"):
                self.partial += chunk  # tail mode: the rest of the line is not written yet
                if not self.follow:
                    continue
                break
            line, self.partial = self.partial + chunk, ""
            self._line(line, out)
            n += 1
            if self.ended and not self.follow:
                break
        if n < self.batch:  # at the end of the file (for now)
            if not self.follow:
                if self.partial:
                    line, self.partial = self.partial, ""
                    self._line(line, out)
                self._close_stream(out, cut=self.eof == "cut", why="ended without an end event (eof = cut)")
            elif self.ended:
                self._close_stream(out, cut=False, why="")
            elif self.clock() - self.last_data >= self.idle_timeout_s:
                self._close_stream(out, cut=True, why=f"had no new line for {self.idle_timeout_s:g} s (tail mode)")
            elif not out and timeout > 0:
                time.sleep(min(timeout, self.poll_interval_s))
        self.counts["items"] += len(out)
        return out

    def finish(self) -> list[Item]:
        """At shutdown: the open stream (tail mode, or a stop before EOF) is cut unless it ended."""
        out: list[Item] = []
        while not self.done:
            self._close_stream(out, cut=True, why="was open when the collector stopped")
        return out

    def stop(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None


class WebSocketReceiver(Receiver):
    """The ``/nts`` input of the FEP-0004 WebSocket binding, from :class:`fidetype.adapters.ws.WSServer`.

    The server does the binding work (subprotocol, auth, ``ws_seq`` order, reorder window, gaps,
    resume, back-pressure by not reading, WS-A3). It emits ``gap``, ``lost``, ``replaced`` and
    ``closed`` status items; the trust processor applies the loss rules (WS-Q5, WS-R2).
    The same server serves ``/decisions`` for a ``websocket`` exporter (``hub``).
    The token comes from an environment variable and never appears in an output.
    """

    type = "websocket"

    def __init__(self, name: str, log: Callable[[str], None], host: str = "127.0.0.1", port: int = W.DEFAULT_PORT,
                 token: str | None = None, origins: list[str] | None = None, ssl: Any = None,
                 ingest: W.IngestSettings | None = None, queue_max: int = 8192) -> None:
        super().__init__(name, log)
        self.hub = W.OutputHub("decisions", welcome_extra={"spec": "FEP-0001"})
        settings = W.ServerSettings(host=host, port=port, origins=origins, token=token, ssl=ssl, queue_max=queue_max)
        self.server = W.WSServer(ingest, settings, decisions=self.hub, log=lambda m: log(f"receivers.{name}: {m}"))
        self.host = host
        self.counts.update(lost_streams=0, gaps=0)

    def start(self) -> None:
        if self.host not in ("127.0.0.1", "localhost", "::1") and self.server.settings.ssl is None:
            self.log(f"receivers.{self.name}: WARNING: listening beyond localhost without TLS (WS-T4 needs wss://)")
        self.server.start()

    @property
    def port(self) -> int:
        return self.server.port

    def _count(self, items: list[Item]) -> list[Item]:
        for _, ev in items:
            t = ev.get("type")
            if t == "header":
                self.counts["streams"] += 1
            elif t == "end":
                self.counts["ended_streams"] += 1
            elif t == STATUS and ev.get("status") == "lost":
                self.counts["lost_streams"] += 1
            elif t == STATUS and ev.get("status") == "gap":
                self.counts["gaps"] += 1
        self.counts["items"] += len(items)
        return items

    def poll(self, timeout: float) -> list[Item]:
        return self._count(self.server.poll(timeout))

    def finish(self) -> list[Item]:
        return self._count(self.server.finish())

    def stop(self) -> None:
        self.server.stop()

    def stats(self) -> dict[str, Any]:
        # No address, host name or token here (LSL-C3, WS-T3).
        return {**super().stats(), "live_streams": len(self.server.core.live_streams()),
                "ingest": self.server.core.stats.as_dict(), "decision_subscribers": len(self.hub.subs)}


#: Events that end an utterance (a gap right after one cuts no utterance).
BOUNDARY_TYPES = ("segment_end", "end", "header")


class LSLReceiver(Receiver):
    """LSL frames and events streams (spec 8.2, FEP-0002), via :class:`fidetype.adapters.lsl.LSLEventSource`.

    The LSL source does the binding work: resolve by name / type / ``source_id``, the events inlet,
    clock correction (LSL-C3), order (LSL-C4), merge (LSL-C6), gap modes (LSL-G1) and the
    non-blocking reconnect (M6-14) with ``open_timeout_s`` (M6-16). This receiver maps its control
    items to the collector's status items:

    - LSL loss (``lsl_status lost``) -> ``lost``: the trust processor drops the open utterance
      without a decision (LSL-G2). After a reconnect the source sends the header again; the
      ``reconnected`` item itself is only counted.
    - ``on_gap = "abort"`` (the collector default) -> ``gap`` at the place of the gap: the open
      utterance is dropped, and the frames up to the next boundary too (FEP-0006 3.2). A gap right
      after a boundary (``segment_end``, ``end``, a header; a producer pause between utterances)
      cuts no utterance: it is counted (``gaps_between_utterances``), and no status is sent.
    - ``on_gap = "mark"``: the ``gap`` extension event is counted (``gaps_marked`` inside an
      utterance, else ``gaps_between_utterances``) and not passed on (a v0.1 consumer ignores it).
      The utterance goes on. ``"segment"``: the source sends a
      ``segment_end`` with ``reason = "gap"`` (a final decision on the frames before the gap).
    - ``end`` -> the event, then ``closed``. With ``stop_at_end`` (default) the receiver is done.
    - The source gives up after ``reconnect_timeout_s``: the receiver is done (the loss already
      sent ``lost``). At shutdown an open stream is ``lost``.

    The stream id is ``stream_id`` or ``<receiver>-0``: never the LSL stream name or a host name
    (SEC-6, LSL-C3). Metrics hold counters only.
    """

    type = "lsl"

    def __init__(self, name: str, log: Callable[[str], None], open_source: Callable[[], Any],
                 stream_id: str | None = None, stop_at_end: bool = True) -> None:
        super().__init__(name, log)
        self._open_source = open_source
        self.sid = stream_id or f"{name}-0"
        self.stop_at_end = stop_at_end
        self.src: Any = None
        self.ended = False
        self._frames_open = 0  # frames since the last boundary (0: no utterance is open)
        self.counts.update(lost_streams=0, reconnects=0, gaps=0, gaps_marked=0, gaps_between_utterances=0,
                           headers=0, frames=0)

    def start(self) -> None:
        from fidetype.adapters import lsl as L

        try:
            self.src = self._open_source()
        except L.LSLResolveError as e:
            raise ConnectionError(f"receivers.{self.name}: {e}") from None  # exit code 3 (an I/O error)
        self.counts["streams"] += 1

    def _map(self, evs: list[dict[str, Any]]) -> list[Item]:
        from fidetype.adapters import lsl as L

        out: list[Item] = []
        sid = self.sid
        for ev in evs:
            typ = ev.get("type")
            if typ == L.LSL_STATUS:
                st = ev.get("status")
                if st == "lost":
                    self.counts["lost_streams"] += 1
                    self._frames_open = 0
                    self.log(f"receivers.{self.name}: stream {sid} lost; its open utterance gets no decision "
                             "(LSL-G2); reconnecting")
                    out.append(status(sid, "lost", "LSL stream lost"))
                elif st == "reconnected":
                    self.counts["reconnects"] += 1
                    self.log(f"receivers.{self.name}: stream {sid} reconnected")
                elif st == "gap_abort":
                    if self._frames_open:
                        self.counts["gaps"] += 1
                        self._frames_open = 0
                        out.append(status(sid, "gap", "LSL frame gap (on_gap = abort)"))
                    else:
                        self.counts["gaps_between_utterances"] += 1
                continue
            if typ == L.GAP:
                self.counts["gaps_marked" if self._frames_open else "gaps_between_utterances"] += 1
                continue
            if typ == "frame":
                self.counts["frames"] += 1
                self._frames_open += 1
            elif typ in BOUNDARY_TYPES:
                self._frames_open = 0
                if typ == "header":
                    self.counts["headers"] += 1
            out.append((sid, ev))
            if typ == "end":
                self.counts["ended_streams"] += 1
                out.append(status(sid, "closed"))
                if self.stop_at_end:
                    self.ended = True
                    self.done = True
                    break
        return out

    def poll(self, timeout: float) -> list[Item]:
        from fidetype.adapters import lsl as L

        if self.done:
            return []
        try:
            out = self._map(self.src.poll(timeout))
        except L.LSLStreamLost:
            self.log(f"receivers.{self.name}: stream {self.sid} was not reconnected within the reconnect time; "
                     "the receiver stops")
            self.done = self.ended = True  # the loss already sent ``lost``
            out = []
        self.counts["items"] += len(out)
        return out

    def finish(self) -> list[Item]:
        """At shutdown: release what the merge holds; an open stream is ``lost`` (no final decision)."""
        if self.src is None or self.ended:
            return []
        out = [] if self.done else self._map(self.src.drain())
        if not self.ended:
            out.append(status(self.sid, "lost", "was open when the collector stopped"))
            self.ended = True
        self.done = True
        self.counts["items"] += len(out)
        return out

    def stop(self) -> None:
        if self.src is not None:
            self.src.close()

    def stats(self) -> dict[str, Any]:
        # Counters only: no stream name, host name or address (LSL-C3).
        s = super().stats()
        if self.src is not None:
            st = self.src.stats.as_dict()
            s["lsl"] = {k: st[k] for k in ("samples", "markers", "ignored_markers", "bad_markers", "clamped",
                                           "dropped_out_of_order", "late_releases", "transport_latency_ms")
                        if k in st}
        return s
