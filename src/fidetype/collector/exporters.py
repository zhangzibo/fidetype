"""Exporters of the collector (FEP-0006 section 5): they write items out. They never change an item.

- ``jsonl``: a JSON Lines file. With the default ``types = ["trust_decision"]`` it is a decision
  log (spec 6.4: no header, decisions only). A file never mixes decisions and input events (TD-11).
  P5-15: a path with ``{session}`` writes one file per stream / decision session (file name from
  :func:`fidetype.trust.erasure.session_token`), so an erasure can delete one session's whole file.
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

P5-18 (FEP-0010 LIC-3, FEP-0006 4 rule 6): every exporter takes ``refuse_research_only = true``. Then it drops
each decision whose ``input.research_only`` is ``true`` (TD-15), with the counter ``research_only_refused`` and one
log line. A decision without the key has an **unknown** licence: ``unknown_licence = "refuse"`` (the default) drops
it too (counter ``licence_unknown_refused``), ``"pass"`` exports it. Dropping is not a change of an item: an
exported decision is exported unchanged (rule 1).

P5-22: on an exporter that writes input events (``jsonl`` / ``stdout`` whose ``types`` has an input event type), the
gate also acts per stream. The ``header`` of a stream gives its licence (:func:`fidetype.trust.licence.stream_licence`
of ``meta``, the same flags that the trust layers copy into ``input.research_only``). A research-only stream is
dropped whole (header and every event up to its ``end``; counters ``research_only_streams_refused`` and
``research_only_events_refused``). A stream that declares neither key, or an event before any header, has an unknown
licence: the ``unknown_licence`` rule (counters ``licence_unknown_streams_refused``,
``licence_unknown_events_refused``). A refused stream opens no file.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, TextIO

from fidetype.adapters import ws as W
# P5-18: the licence options of every exporter (FEP-0006 4 rule 6) and the values of ``unknown_licence``.
from fidetype.collector.config import LICENCE_KEYS, UNKNOWN_LICENCE  # noqa: F401
from fidetype.collector.receivers import STATUS, Item

#: Output event types of a decision (their file key is the decision's ``session``).
DECISION_TYPES = {"trust_decision", "intent_decision", "control_decision"}




def dumps(ev: dict[str, Any]) -> str:
    return json.dumps(ev, ensure_ascii=False, allow_nan=False)


def decision_research_only(ev: dict[str, Any]) -> bool | None:
    """``input.research_only`` of a decision (TD-15): True, False, or None (absent or not a boolean: unknown)."""
    inp = ev.get("input")
    v = inp.get("research_only") if isinstance(inp, dict) else None
    return v if isinstance(v, bool) else None


class LicenceGate:
    """P5-18 (FEP-0010 LIC-3): drop research-only decisions before a (product) exporter sees them.

    ``research_only = true`` -> dropped (``research_only_refused``). No key (unknown licence) -> dropped with
    ``unknown = "refuse"`` (``licence_unknown_refused``), exported with ``"pass"``. ``research_only = false`` ->
    exported unchanged. The first drop of each kind gives one log line (no text, no session id).

    P5-22: with ``input_events = True`` (an exporter that writes input events) the gate also judges each stream by
    its ``header`` (:func:`fidetype.trust.licence.stream_licence` of ``meta``) and drops a refused stream whole: the
    header and every input event of the same stream key up to its ``end``. A new header of the same key judges the
    new stream. An input event without a header before it has an unknown licence. Without ``input_events`` every
    input event passes (the exporter ignores them anyway). Status items always pass (no exporter writes them).
    """

    #: Verdicts of a stream (P5-22).
    PASS, REFUSE_RO, REFUSE_UNKNOWN = "pass", "research_only", "licence_unknown"

    def __init__(self, exporter: str, log: Callable[[str], None], counts: dict[str, int],
                 unknown: str = "refuse", input_events: bool = False) -> None:
        if unknown not in UNKNOWN_LICENCE:
            raise ValueError(f"unknown_licence must be one of {UNKNOWN_LICENCE}, not {unknown!r}")
        self.exporter = exporter
        self.log = log
        self.counts = counts
        self.unknown = unknown
        self.input_events = input_events
        #: P5-22: stream key -> verdict of its current stream (set by its header, removed at its ``end``).
        self.streams: dict[str, str] = {}
        counts.update(research_only_refused=0, licence_unknown_refused=0)
        if input_events:
            counts.update(research_only_streams_refused=0, research_only_events_refused=0,
                          licence_unknown_streams_refused=0, licence_unknown_events_refused=0)

    def _refuse(self, key: str, why: str) -> None:
        if self.counts[key] == 0:
            self.log(f"exporters.{self.exporter}: refuse_research_only: dropped a decision ({why}); "
                     f"further drops are only counted ({key})")
        self.counts[key] += 1

    def _unknown_verdict(self) -> str:
        return self.REFUSE_UNKNOWN if self.unknown == "refuse" else self.PASS

    def _stream_verdict(self, header: dict[str, Any]) -> str:
        """The verdict of a stream from its header: the flags that a trust layer copies into ``input.research_only``."""
        from fidetype.trust.licence import stream_licence

        meta = header.get("meta")
        sl = stream_licence(meta if isinstance(meta, dict) else None)
        if sl is None:
            return self._unknown_verdict()
        return self.REFUSE_RO if sl["research_only"] else self.PASS

    def _refuse_stream(self, verdict: str) -> None:
        """Count one refused stream; the first one of each kind gives one log line (no session id, no text)."""
        key = f"{verdict}_streams_refused"
        if self.counts[key] == 0:
            why = ("its header says research only: data.research_only = true, or a data.licence without commercial "
                   "use or not known" if verdict == self.REFUSE_RO else
                   "no header with data.licence or data.research_only: unknown licence")
            self.log(f"exporters.{self.exporter}: refuse_research_only: dropped a stream with all its events "
                     f"({why}); further drops are only counted ({key})")
        self.counts[key] += 1

    def _admit_input(self, sid: str, ev: dict[str, Any]) -> bool:
        """P5-22: True if the input event ``ev`` of stream key ``sid`` goes out."""
        t = ev.get("type")
        if t == "header":
            verdict = self.streams[sid] = self._stream_verdict(ev)
            if verdict != self.PASS:
                self._refuse_stream(verdict)
        else:
            verdict = self.streams.get(sid) or ""
            if not verdict:  # no header before it: unknown licence
                verdict = self.streams[sid] = self._unknown_verdict()
                if verdict != self.PASS:
                    self._refuse_stream(verdict)
            if t == "end":
                self.streams.pop(sid, None)
        if verdict == self.PASS:
            return True
        self.counts[f"{verdict}_events_refused"] += 1
        return False

    def admit(self, items: list[Item]) -> list[Item]:
        out: list[Item] = []
        for item in items:
            ev = item[1]
            t = ev.get("type")
            if t in DECISION_TYPES:
                ro = decision_research_only(ev)
                if ro is True:
                    self._refuse("research_only_refused", "input.research_only = true")
                    continue
                if ro is None and self.unknown == "refuse":
                    self._refuse("licence_unknown_refused", "no input.research_only: unknown licence")
                    continue
            elif self.input_events and t != STATUS and not self._admit_input(str(item[0]), ev):
                continue
            out.append(item)
        return out


class Exporter:
    type = "exporter"

    def __init__(self, name: str, log: Callable[[str], None]) -> None:
        self.name = name
        self.log = log
        self.counts: dict[str, int] = {"exported": 0}
        #: Seconds the collector waits after the input is done, before it stops (standalone servers).
        self.linger_s = 0.0
        #: P5-18: the ``refuse_research_only`` gate (None: every decision goes out, the default).
        self.licence_gate: LicenceGate | None = None

    def writes_input_events(self) -> bool:
        """True if this exporter can write input events (P5-22: then the licence gate also acts per stream)."""
        return False

    def refuse_research_only(self, unknown: str = "refuse") -> "Exporter":
        """Turn on the P5-18 licence gate (the ``refuse_research_only`` option). Returns ``self``."""
        self.licence_gate = LicenceGate(self.name, self.log, self.counts, unknown,
                                        input_events=self.writes_input_events())
        return self

    def deliver(self, items: list[Item]) -> None:
        """What the pipeline calls: the licence gate (if any), then :meth:`export`."""
        if self.licence_gate is not None:
            items = self.licence_gate.admit(items)
            if not items:
                return
        self.export(items)

    def start(self) -> None:
        pass

    def export(self, items: list[Item]) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass

    def stats(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, **self.counts}
        if self.licence_gate is not None:
            out["refuse_research_only"] = {"unknown_licence": self.licence_gate.unknown}
            if self.licence_gate.input_events:
                out["refuse_research_only"]["streams"] = True  # P5-22: input events are judged per stream
        return out


class _LinesExporter(Exporter):
    def __init__(self, name: str, log: Callable[[str], None], types: list[str]) -> None:
        super().__init__(name, log)
        self.types = None if types == ["*"] else set(types)
        self.fh: TextIO | None = None

    def wants(self, ev: dict[str, Any]) -> bool:
        t = ev.get("type")
        return t != STATUS and (self.types is None or t in self.types)

    def writes_input_events(self) -> bool:
        return self.types is None or bool(self.types - DECISION_TYPES)

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
        #: P5-15: ``{session}`` in the path -> one file per session, opened at its first item.
        self.per_session = "{session}" in str(path)
        self.fhs: dict[str, TextIO] = {}
        if self.per_session:
            self.counts.update(files=0)

    def start(self) -> None:
        # P5-22: with the licence gate, the single file opens at its first exported item, so a refused stream
        # writes no file (an older file at the path stays as it is).
        if self.per_session or self.licence_gate is not None:
            return
        self._open()

    def _open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a" if self.append else "w", encoding="utf-8", newline="\n")

    def _session_fh(self, session: str) -> TextIO:
        fh = self.fhs.get(session)
        if fh is None:
            from fidetype.trust.erasure import session_path

            p = Path(session_path(str(self.path), session))
            p.parent.mkdir(parents=True, exist_ok=True)
            fh = self.fhs[session] = open(p, "a" if self.append else "w", encoding="utf-8", newline="\n")
            self.counts["files"] += 1
        return fh

    def export(self, items: list[Item]) -> None:
        if not self.per_session:
            if self.fh is None and self.licence_gate is not None and any(self.wants(ev) for _, ev in items):
                self._open()
            return super().export(items)
        touched: set[str] = set()
        for sid, ev in items:
            if not self.wants(ev):
                continue
            s = str(ev.get("session") or sid) if ev.get("type") in DECISION_TYPES else str(sid)
            self._session_fh(s).write(dumps(ev) + "\n")
            touched.add(s)
            self.counts["exported"] += 1
        for s in touched:
            self.fhs[s].flush()

    def stop(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None
        for fh in self.fhs.values():
            fh.close()
        self.fhs = {}


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


# ---------------------------------------------------------------------------
# os_text (P3-03): OS text input. v0: the "stub" backend only.
# ---------------------------------------------------------------------------

#: Backends of the ``os_text`` exporter. Only ``stub`` exists (P3-03: Windows TSF, Android IME, macOS, IBus open).
OS_TEXT_BACKENDS = ("stub",)


def committed_text(ev: dict[str, Any]) -> str | None:
    """The text that an OS input exporter may type for one item, or None.

    Only a final text COMMIT with a non-blank first ``shown`` text (roadmap P3 hard rule: "an
    exporter to an OS input method sends only committed decisions"; TD-1: no action on a
    provisional decision; TD-9: no blank COMMIT).
    """
    if ev.get("type") != "trust_decision" or ev.get("is_final") is not True or ev.get("action") != "COMMIT":
        return None
    if ev.get("profile", "text") != "text":
        return None
    sh = ev.get("shown")
    if not isinstance(sh, list) or not sh or not isinstance(sh[0], str) or not sh[0].strip():
        return None
    return sh[0]


class OsTextExporter(Exporter):
    """Type committed text into the operating system's text input (P3-03). v0: ``backend = "stub"``.

    The ``stub`` backend types into memory (:attr:`typed`) and, with ``path``, appends one JSON line
    per typed text: ``{"typed": text, "decision": <the full trust_decision>}`` (the roadmap rule
    "log the full NTS next to each output"). It is the test double of a real input-method backend:
    the same filter (:func:`committed_text`), the same log. OFFER, ASK, ABSTAIN and provisional
    decisions are counted and never typed. ``separator`` goes between two typed texts.
    """

    type = "os_text"

    def __init__(self, name: str, log: Callable[[str], None], backend: str = "stub", path: Path | None = None,
                 separator: str = " ", on_type: Callable[[str, dict[str, Any]], None] | None = None) -> None:
        super().__init__(name, log)
        if backend not in OS_TEXT_BACKENDS:
            raise ValueError(f"exporters.{name}: backend {backend!r} is not implemented (known: "
                             f"{', '.join(OS_TEXT_BACKENDS)})")
        self.backend = backend
        self.path = path
        self.separator = separator
        self.on_type = on_type
        self.typed: list[str] = []
        self.fh: TextIO | None = None
        self.counts.update(typed=0, not_committed=0)

    def start(self) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.fh = open(self.path, "w", encoding="utf-8", newline="\n")

    def export(self, items: list[Item]) -> None:
        n = 0
        for _, ev in items:
            if ev.get("type") != "trust_decision":
                continue
            text = committed_text(ev)
            if text is None:
                self.counts["not_committed"] += 1
                continue
            out = (self.separator if self.typed else "") + text
            self.typed.append(text)
            if self.on_type is not None:
                self.on_type(out, ev)
            if self.fh is not None:
                self.fh.write(dumps({"typed": out, "decision": ev}) + "\n")
            n += 1
        if n:
            if self.fh is not None:
                self.fh.flush()
            self.counts["typed"] += n
            self.counts["exported"] += n

    def stop(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None

    def stats(self) -> dict[str, Any]:
        return {**super().stats(), "backend": self.backend}  # counts only: no typed text
