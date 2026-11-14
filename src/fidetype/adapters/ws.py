"""WebSocket adapter: NeuralTextStream over WebSocket in both directions (M6-11, FEP-0004).

FEP-0004 (``spec/feps/0004-nts-over-websocket.md``) is the normative
binding (version ``nts-ws/0.1``, subprotocol ``nts-ws.0.1``). This module
is its reference implementation. It follows the pattern of the LSL adapter
(:mod:`fidetype.adapters.lsl`): a source of NTS events, a runner that feeds
a :class:`~fidetype.trust.streaming.StreamingTrustLayer`, a replay tool
and a command line.

``websockets`` (BSD-3-Clause) is an **optional** dependency
(``pip install "fidetype[ws]"``). This module imports without it. Only
the functions that open sockets need it; they raise
:class:`WSUnavailableError` with an install hint.

This is our own code (Apache-2.0). No code is copied.

Paths of the reference server
-----------------------------
``/nts``        input: a producer (decoder) sends NTS events; the server feeds the trust layer.
``/decisions``  output: ``trust_decision`` events (FEP-0001) with ``ws_seq``; resumable.
``/events``     output: a tap of the NTS events after sequencing (monitoring; not resumable).

Parts
-----
:class:`IngestCore`
    The input side without I/O ("sans-IO"): handshake, header, ``ws_seq``
    order (duplicates, reorder window, gaps), batches, resume, take-over,
    acks, refusals. The live server and the conformance profile use it.
:class:`SubscriberCore`
    The checks of a decisions subscriber: welcome, ``ws_seq`` gaps
    (resubscribe), duplicates, FEP-0001 rules.
:class:`OutputHub`
    The output side: a ring buffer of decisions for resume, one bounded
    queue per subscriber.
:class:`WSServer`, :class:`WSEventSource`, :class:`WSTrustRunner`
    The live server (``websockets`` sync API, one thread per connection),
    the poll interface of the LSL runner, and the runner.
:class:`WSProducer`, :func:`replay_to_ws`, :func:`subscribe`
    Clients: a producer with resend-on-resume, a paced file replay, and a
    decisions subscriber.

Privacy: tokens are never logged, echoed or forwarded. The client
address is never written to a header, a decision or a log line.
"""

from __future__ import annotations

import collections
import hmac
import itertools
import json
import math
import mimetypes
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence, TextIO

import numpy as np

from fidetype.streams.spec import SPEC_VERSION

ADAPTER_NAME = "fidetype.adapters.ws"
ADAPTER_VERSION = "0.1"
#: Binding version (FEP-0004 section 10) and its WebSocket subprotocol token.
BINDING_VERSION = "nts-ws/0.1"
SUBPROTOCOL = "nts-ws.0.1"
KNOWN_BINDINGS = (BINDING_VERSION,)
PATH_INGEST = "/nts"
PATH_DECISIONS = "/decisions"
PATH_EVENTS = "/events"
DEFAULT_PORT = 8765
#: Control message types (FEP-0004 section 4). NTS events never use the ``ws_`` prefix.
WS_WELCOME = "ws_welcome"
WS_ACK = "ws_ack"
WS_ERROR = "ws_error"
WS_BATCH = "ws_batch"
WS_AUTH = "ws_auth"
WS_SUBSCRIBE = "ws_subscribe"
#: Control item of the source (never pushed into the trust layer).
WS_STATUS = "ws_status"
#: Close codes that refuse a connection (FEP-0004 section 9).
CLOSE_PROTOCOL = 1002
CLOSE_BINARY = 1003
CLOSE_INVALID = 1007
CLOSE_POLICY = 1008
CLOSE_TOO_BIG = 1009
CLOSE_TRY_LATER = 1013
CLOSE_BINDING = 4000
CLOSE_TAKEN_OVER = 4001
REFUSAL_CODES = (CLOSE_PROTOCOL, CLOSE_BINARY, CLOSE_INVALID, CLOSE_POLICY, CLOSE_TOO_BIG, CLOSE_BINDING)
#: Largest text message the reference accepts (bytes of UTF-8).
MAX_MESSAGE_BYTES = 1 << 20
MAX_STREAM_ID = 128


# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------


class WSUnavailableError(ImportError):
    """``websockets`` is not installed."""


class WSRefused(RuntimeError):
    """The peer refused the connection (a ``ws_error`` and a refusal close code)."""


class SubscriberError(ValueError):
    """A decisions channel breaks FEP-0004 (subscriber view)."""


def require_websockets() -> Any:
    try:
        import websockets  # noqa: F401
        import websockets.sync.client  # noqa: F401
        import websockets.sync.server  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise WSUnavailableError(
            'the WebSocket adapter needs the optional dependency websockets: pip install "fidetype[ws]"') from e
    return websockets


def websockets_available() -> bool:
    try:
        require_websockets()
        return True
    except WSUnavailableError:
        return False


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _reject_constant(name: str) -> Any:
    raise ValueError(f"JSON constant {name} is not allowed (FEP-0004 section 3 rule 2)")


def parse_message(text: str) -> dict[str, Any]:
    """Parse one text message: a JSON object with a string ``type`` (no NaN / Infinity tokens)."""
    obj = json.loads(text, parse_constant=_reject_constant)
    if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
        raise ValueError("a message must be a JSON object with a string type")
    return obj


def dumps(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def bearer_token(authorization: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header value, or None."""
    if isinstance(authorization, str) and authorization[:7].lower() == "bearer ":
        tok = authorization[7:].strip()
        return tok or None
    return None


def token_checker(expected: str) -> Callable[[str | None], bool]:
    """A constant-time shared-token check (the simplest auth hook)."""
    want = expected.encode("utf-8")

    def check(tok: str | None) -> bool:
        return isinstance(tok, str) and hmac.compare_digest(tok.encode("utf-8"), want)

    return check


# ---------------------------------------------------------------------------
# Input side, sans-IO
# ---------------------------------------------------------------------------


@dataclass
class IngestSettings:
    """Settings of the input side (FEP-0004 sections 5-8). The defaults are the reference values."""

    #: Messages held while an earlier ``ws_seq`` is missing (0 = a missing seq is a gap at once).
    reorder_window: int = 16
    #: A held message older than this declares a gap (seconds).
    reorder_timeout_s: float = 0.25
    #: A disconnected stream waits this long for a resume, then its open utterance is dropped (seconds).
    resume_timeout_s: float = 10.0
    #: Largest ``ws_batch`` (events).
    max_batch: int = 1024
    #: Send a ``ws_ack`` after this many released events (and at ``end``).
    ack_every: int = 64
    #: The producer may have at most this many unacknowledged events (told in the welcome).
    window: int = 4096
    #: Also send a ``ws_ack`` when released events wait this long for one (seconds; checked by :meth:`IngestCore.tick`).
    ack_interval_s: float = 0.1

    def __post_init__(self) -> None:
        if not (_is_int(self.reorder_window) and self.reorder_window >= 0):
            raise ValueError("reorder_window must be an integer >= 0")
        for k in ("reorder_timeout_s", "resume_timeout_s", "ack_interval_s"):
            v = getattr(self, k)
            if not (_is_num(v) and v >= 0):
                raise ValueError(f"{k} must be a number >= 0")
        for k in ("max_batch", "ack_every", "window"):
            v = getattr(self, k)
            if not (_is_int(v) and v >= 1):
                raise ValueError(f"{k} must be an integer >= 1")


@dataclass
class Effects:
    """What the I/O layer must do after a core call."""

    #: (connection id, message) to send.
    sends: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    #: (stream id, NTS event or ``ws_status`` item) for the trust runner, in order.
    items: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    #: (connection id, close code, reason) to close.
    closes: list[tuple[int, int, str]] = field(default_factory=list)

    def extend(self, other: "Effects") -> "Effects":
        self.sends += other.sends
        self.items += other.items
        self.closes += other.closes
        return self


@dataclass
class IngestStats:
    streams: int = 0
    messages: int = 0
    events: int = 0
    duplicates: int = 0
    reordered: int = 0
    gaps: int = 0
    missing_events: int = 0
    resumes: int = 0
    takeovers: int = 0
    lost_streams: int = 0
    ignored_controls: int = 0
    refused: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class _Conn:
    cid: int
    authed: bool
    stream_id: str | None = None
    open: bool = True


@dataclass
class _Stream:
    sid: str
    header: dict[str, Any]
    conn: int | None
    expected: int = 1
    held: dict[int, tuple[dict[str, Any], float]] = field(default_factory=dict)
    since_ack: int = 0
    last_ack_at: float = 0.0
    ended: bool = False
    disconnected_at: float | None = None


class IngestCore:
    """The input side of FEP-0004 without I/O.

    Call :meth:`open` when a connection is opened (after the HTTP upgrade),
    :meth:`message` for each message (``str`` text, ``bytes`` binary, or an
    already parsed ``dict``), :meth:`disconnect` when it ends, and
    :meth:`tick` now and then (reorder and resume time-outs). Each call
    returns :class:`Effects`. ``now`` is any monotonic clock in seconds.

    ``auth``: an optional hook ``auth(token) -> bool``. If set, a connection
    must give a token in the ``Authorization: Bearer`` header or in a
    ``ws_auth`` message before the header. ``stamp``: add ``ws_t_recv``
    (= ``now``) to each released event (the live server uses it for
    latency).
    """

    def __init__(self, settings: IngestSettings | None = None, auth: Callable[[str | None], bool] | None = None,
                 stamp: bool = False) -> None:
        self.s = settings or IngestSettings()
        self.auth = auth
        self.stamp = stamp
        self.conns: dict[int, _Conn] = {}
        self.streams: dict[str, _Stream] = {}
        self.stats = IngestStats()
        self._anon = itertools.count(1)

    # --- connections ---------------------------------------------------------------

    def open(self, cid: int, subprotocols: Sequence[str] = (SUBPROTOCOL,), authorization: str | None = None,
             now: float = 0.0) -> Effects:
        """A new connection on the input path. ``subprotocols``: offered by the client."""
        eff = Effects()
        if SUBPROTOCOL not in list(subprotocols):
            # The real server refuses this in the HTTP upgrade (status 400).
            self.conns[cid] = _Conn(cid, False, open=False)
            self.stats.refused += 1
            eff.closes.append((cid, CLOSE_PROTOCOL, f"subprotocol {SUBPROTOCOL} not offered"))
            return eff
        tok = bearer_token(authorization)
        authed = self.auth is None or (tok is not None and bool(self.auth(tok)))
        self.conns[cid] = _Conn(cid, authed)
        return eff

    def _refuse(self, conn: _Conn, close: int, code: str, detail: str, now: float) -> Effects:
        eff = Effects()
        eff.sends.append((conn.cid, {"type": WS_ERROR, "code": code, "detail": detail}))
        eff.closes.append((conn.cid, close, code))
        self.stats.refused += 1
        eff.extend(self.disconnect(conn.cid, now))
        return eff

    def message(self, cid: int, data: str | bytes | dict[str, Any], now: float = 0.0) -> Effects:
        conn = self.conns.get(cid)
        if conn is None or not conn.open:
            return Effects()
        self.stats.messages += 1
        if isinstance(data, (bytes, bytearray, memoryview)):
            return self._refuse(conn, CLOSE_BINARY, "binary", "binary messages are not allowed (section 3 rule 1)", now)
        if isinstance(data, str):
            if len(data.encode("utf-8")) > MAX_MESSAGE_BYTES:
                return self._refuse(conn, CLOSE_TOO_BIG, "too_big", "message larger than 1 MiB", now)
            try:
                msg = parse_message(data)
            except ValueError as e:
                return self._refuse(conn, CLOSE_INVALID, "bad_message", str(e)[:200], now)
        else:
            msg = data
            if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
                return self._refuse(conn, CLOSE_INVALID, "bad_message",
                                    "a message must be a JSON object with a string type", now)
        typ = msg["type"]
        if not conn.authed:
            if typ == WS_AUTH and self.auth is not None and bool(self.auth(msg.get("token") if isinstance(msg.get("token"), str) else None)):
                conn.authed = True
                return Effects()
            return self._refuse(conn, CLOSE_POLICY, "auth", "authentication failed or missing (section 8)", now)
        if typ == WS_AUTH:
            if conn.stream_id is None:
                return Effects()  # no auth needed, or already authed
            self.stats.ignored_controls += 1
            return Effects()
        if conn.stream_id is None:
            if typ != "header":
                return self._refuse(conn, CLOSE_INVALID, "bad_header",
                                    "the first message must be the NTS header (section 5 rule 1)", now)
            return self._open_stream(conn, msg, now)
        st = self.streams.get(conn.stream_id)
        if st is None or st.conn != cid:
            return Effects()  # taken over or lost: the close is on its way
        if typ == WS_BATCH:
            return self._batch(conn, st, msg, now)
        if typ.startswith("ws_"):
            self.stats.ignored_controls += 1  # unknown control message (section 4 rule 3)
            return Effects()
        err = self._seq_error(msg)
        if err:
            return self._refuse(conn, CLOSE_INVALID, "bad_seq", err, now)
        eff = Effects()
        self._sequence(st, msg, now, eff)
        return eff

    @staticmethod
    def _seq_error(ev: Any) -> str | None:
        if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
            return "a batch event must be a JSON object with a string type"
        if ev["type"].startswith("ws_"):
            return f"control message {ev['type']!r} inside a batch (section 6 rule 4)"
        seq = ev.get("ws_seq")
        if not (_is_int(seq) and seq >= 1):
            return f"ws_seq {seq!r} must be an integer >= 1 (section 6 rule 1)"
        return None

    def _batch(self, conn: _Conn, st: _Stream, msg: dict[str, Any], now: float) -> Effects:
        evs = msg.get("events")
        if not isinstance(evs, list) or not evs:
            return self._refuse(conn, CLOSE_INVALID, "bad_batch", "ws_batch needs a non-empty events list", now)
        if len(evs) > self.s.max_batch:
            return self._refuse(conn, CLOSE_TOO_BIG, "too_big", f"ws_batch of {len(evs)} events > {self.s.max_batch}", now)
        for k, ev in enumerate(evs):
            err = self._seq_error(ev)
            if err:
                return self._refuse(conn, CLOSE_INVALID, "bad_seq", err, now)
            if k and ev["ws_seq"] != evs[k - 1]["ws_seq"] + 1:
                return self._refuse(conn, CLOSE_INVALID, "bad_batch",
                                    "the events of a batch must have consecutive ws_seq (section 6 rule 4)", now)
        eff = Effects()
        for ev in evs:
            self._sequence(st, ev, now, eff)
        return eff

    def _open_stream(self, conn: _Conn, hdr: dict[str, Any], now: float) -> Effects:
        ws = hdr.get("ws", {})
        if not isinstance(ws, dict):
            return self._refuse(conn, CLOSE_INVALID, "bad_header", "header ws must be an object", now)
        binding = ws.get("binding", BINDING_VERSION)
        if not isinstance(binding, str) or binding not in KNOWN_BINDINGS:
            return self._refuse(conn, CLOSE_BINDING, "binding", f"unknown binding {binding!r} (section 10)", now)
        sid = ws.get("stream_id")
        if sid is None:
            sid = f"anon-{next(self._anon)}"
        elif not (isinstance(sid, str) and 1 <= len(sid) <= MAX_STREAM_ID):
            return self._refuse(conn, CLOSE_INVALID, "bad_header", "ws.stream_id must be a string of 1-128 characters", now)
        resume = ws.get("resume", False)
        if not isinstance(resume, bool):
            return self._refuse(conn, CLOSE_INVALID, "bad_header", "ws.resume must be a boolean", now)
        if hdr.get("spec_version") != SPEC_VERSION:
            return self._refuse(conn, CLOSE_INVALID, "bad_header",
                                f"spec_version {hdr.get('spec_version')!r} is not {SPEC_VERSION!r}", now)
        if "ws_seq" in hdr:
            return self._refuse(conn, CLOSE_INVALID, "bad_header", "the header has no ws_seq (section 6 rule 1)", now)
        core = {k: v for k, v in hdr.items() if k != "ws"}
        eff = Effects()
        old = self.streams.get(sid)
        if old is not None and resume:
            if old.header != core:
                return self._refuse(conn, CLOSE_INVALID, "bad_header", "the resume header differs from the first header", now)
            if old.conn is not None and old.conn != conn.cid:
                eff.extend(self._take_over(old.conn, now))
            old.conn, old.disconnected_at, old.last_ack_at = conn.cid, None, now
            conn.stream_id = sid
            self.stats.resumes += 1
            eff.items.append((sid, {"type": WS_STATUS, "status": "resumed", "stream": sid, "seq": old.expected - 1}))
            eff.sends.append((conn.cid, self._welcome(old, True)))
            return eff
        if old is not None:
            if old.conn is not None and old.conn != conn.cid:
                eff.extend(self._take_over(old.conn, now))
            if not old.ended:
                eff.items.append((sid, {"type": WS_STATUS, "status": "replaced", "stream": sid}))
        st = _Stream(sid, core, conn.cid, last_ack_at=now)
        self.streams[sid] = st
        conn.stream_id = sid
        self.stats.streams += 1
        eff.items.append((sid, {"type": WS_STATUS, "status": "connected", "stream": sid}))
        eff.items.append((sid, dict(core)))
        eff.sends.append((conn.cid, self._welcome(st, False)))
        return eff

    def _take_over(self, old_cid: int, now: float) -> Effects:
        eff = Effects()
        c = self.conns.get(old_cid)
        if c is not None and c.open:
            c.open = False
            c.stream_id = None
            self.stats.takeovers += 1
            eff.sends.append((old_cid, {"type": WS_ERROR, "code": "taken_over",
                                        "detail": "a newer connection resumed this stream"}))
            eff.closes.append((old_cid, CLOSE_TAKEN_OVER, "taken_over"))
        return eff

    def _welcome(self, st: _Stream, resumed: bool) -> dict[str, Any]:
        return {"type": WS_WELCOME, "binding": BINDING_VERSION, "role": "ingest", "stream_id": st.sid,
                "seq": st.expected - 1, "resumed": resumed, "ack_every": self.s.ack_every, "window": self.s.window}

    # --- order ---------------------------------------------------------------------

    def _sequence(self, st: _Stream, ev: dict[str, Any], now: float, eff: Effects) -> None:
        seq = ev["ws_seq"]
        if seq < st.expected or seq in st.held:
            self.stats.duplicates += 1
            return
        if seq == st.expected:
            self._release(st, ev, now, eff)
            self._drain(st, now, eff, reordered=True)
        else:
            st.held[seq] = (ev, now)
            if len(st.held) > self.s.reorder_window:
                self._gap(st, now, eff)
        self._maybe_ack(st, eff)
        if st.since_ack == 0:
            st.last_ack_at = now

    def _release(self, st: _Stream, ev: dict[str, Any], now: float, eff: Effects) -> None:
        out = dict(ev)
        if self.stamp:
            out["ws_t_recv"] = now
        eff.items.append((st.sid, out))
        st.expected += 1
        st.since_ack += 1
        self.stats.events += 1
        if out.get("type") == "end":
            st.ended = True
            st.since_ack = max(st.since_ack, self.s.ack_every)

    def _drain(self, st: _Stream, now: float, eff: Effects, reordered: bool) -> None:
        while st.expected in st.held:
            ev, _ = st.held.pop(st.expected)
            if reordered:
                self.stats.reordered += 1
            self._release(st, ev, now, eff)

    def _gap(self, st: _Stream, now: float, eff: Effects) -> None:
        first = min(st.held)
        missing = first - st.expected
        self.stats.gaps += 1
        self.stats.missing_events += missing
        eff.items.append((st.sid, {"type": WS_STATUS, "status": "gap", "stream": st.sid, "seq_from": st.expected,
                                   "seq_to": first - 1, "missing": missing}))
        st.expected = first
        self._drain(st, now, eff, reordered=False)

    def _maybe_ack(self, st: _Stream, eff: Effects, now: float | None = None) -> None:
        due = st.since_ack >= self.s.ack_every or (
            now is not None and st.since_ack > 0 and now - st.last_ack_at >= self.s.ack_interval_s)
        if due and st.conn is not None:
            eff.sends.append((st.conn, {"type": WS_ACK, "stream_id": st.sid, "seq": st.expected - 1}))
            st.since_ack = 0
            if now is not None:
                st.last_ack_at = now

    # --- time-outs and loss ------------------------------------------------------------

    def tick(self, now: float) -> Effects:
        eff = Effects()
        for sid in list(self.streams):
            st = self.streams[sid]
            while st.held and now - min(t for _, t in st.held.values()) >= self.s.reorder_timeout_s:
                self._gap(st, now, eff)
            self._maybe_ack(st, eff, now)
            if st.conn is None and st.disconnected_at is not None and now - st.disconnected_at >= self.s.resume_timeout_s:
                self._lose(st, eff, "resume time-out")
        return eff

    def _lose(self, st: _Stream, eff: Effects, why: str) -> None:
        self.stats.lost_streams += 1
        eff.items.append((st.sid, {"type": WS_STATUS, "status": "lost", "stream": st.sid, "detail": why}))
        del self.streams[st.sid]

    def disconnect(self, cid: int, now: float = 0.0) -> Effects:
        """The connection ended (close handshake or not)."""
        eff = Effects()
        conn = self.conns.pop(cid, None)
        if conn is None or conn.stream_id is None:
            return eff
        st = self.streams.get(conn.stream_id)
        if st is None or st.conn != cid:
            return eff
        st.conn = None
        if st.ended:
            eff.items.append((st.sid, {"type": WS_STATUS, "status": "closed", "stream": st.sid}))
            del self.streams[st.sid]
        else:
            st.disconnected_at = now
            eff.items.append((st.sid, {"type": WS_STATUS, "status": "disconnected", "stream": st.sid,
                                       "seq": st.expected - 1}))
        return eff

    def finish(self, now: float = 0.0) -> Effects:
        """At shutdown: every stream that waits for a resume is lost (no decision on its cut utterance)."""
        eff = Effects()
        for sid in list(self.streams):
            st = self.streams[sid]
            if st.conn is None and not st.ended:
                self._lose(st, eff, "shutdown")
        return eff

    def live_streams(self) -> list[str]:
        """Streams with an open connection."""
        return [sid for sid, st in self.streams.items() if st.conn is not None]


# ---------------------------------------------------------------------------
# Output side
# ---------------------------------------------------------------------------


class _Subscriber:
    def __init__(self, maxsize: int, types: set[str] | None, stream: str | None) -> None:
        import queue

        self.q: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize)
        self.types = types
        self.stream = stream
        self.overflow = False

    def wants(self, msg: dict[str, Any]) -> bool:
        if self.types is not None and msg.get("type") not in self.types:
            return False
        return self.stream is None or msg.get("stream_id") in (None, self.stream)


class OutputHub:
    """Fan-out of output messages to subscribers (FEP-0004 section 7).

    ``resumable`` (the decisions channel): each message gets ``ws_seq``
    (1, 2, 3, ... with no gap) and stays in a ring buffer of ``history``
    messages, so a subscriber can resume with ``from_seq``. A subscriber
    whose queue (``queue_size``) is full is marked ``overflow``; the server
    closes it with 1013 and it resubscribes. A slow subscriber never blocks
    the trust layer.
    """

    def __init__(self, role: str, resumable: bool = True, history: int = 4096, queue_size: int = 1024,
                 welcome_extra: dict[str, Any] | None = None) -> None:
        self.role = role
        self.resumable = resumable
        self.ring: collections.deque[dict[str, Any]] = collections.deque(maxlen=history if resumable else 0)
        self.queue_size = queue_size
        self.seq = 0
        self.subs: list[_Subscriber] = []
        self.lock = threading.Lock()
        self.welcome_extra = dict(welcome_extra or {})
        self.dropped_subscribers = 0

    @property
    def has_subscribers(self) -> bool:
        return bool(self.subs)

    def publish(self, msg: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            out = dict(msg)
            if self.resumable:
                self.seq += 1
                out["ws_seq"] = self.seq
                self.ring.append(out)
            for sub in self.subs:
                if sub.overflow or not sub.wants(out):
                    continue
                try:
                    sub.q.put_nowait(out)
                except Exception:  # queue.Full
                    sub.overflow = True
                    self.dropped_subscribers += 1
            return out

    def subscribe(self, request: dict[str, Any]) -> tuple[_Subscriber, dict[str, Any], list[dict[str, Any]]]:
        """Register a subscriber from a ``ws_subscribe`` message. Raise ValueError if it is invalid."""
        binding = request.get("binding", BINDING_VERSION)
        if not isinstance(binding, str) or binding not in KNOWN_BINDINGS:
            raise ValueError(f"unknown binding {binding!r}")
        from_seq = request.get("from_seq")
        if from_seq is not None and not (_is_int(from_seq) and from_seq >= 1):
            raise ValueError("from_seq must be an integer >= 1")
        types = request.get("types")
        if types is not None and not (isinstance(types, list) and all(isinstance(t, str) for t in types)):
            raise ValueError("types must be a list of strings")
        stream = request.get("stream_id")
        if stream is not None and not isinstance(stream, str):
            raise ValueError("stream_id must be a string")
        with self.lock:
            sub = _Subscriber(self.queue_size, set(types) if types is not None else None, stream)
            replay: list[dict[str, Any]] = []
            welcome: dict[str, Any] = {"type": WS_WELCOME, "binding": BINDING_VERSION, "role": self.role,
                                       **self.welcome_extra}
            if self.resumable:
                first = self.ring[0]["ws_seq"] if self.ring else self.seq + 1
                welcome.update(seq=self.seq, first_available=first)
                if from_seq is not None:
                    replay = [m for m in self.ring if m["ws_seq"] >= from_seq and sub.wants(m)]
                    welcome["replayed"] = len(replay)
                    if from_seq < first:
                        welcome["missed"] = first - from_seq
            self.subs.append(sub)
            return sub, welcome, replay

    def unsubscribe(self, sub: _Subscriber) -> None:
        with self.lock:
            if sub in self.subs:
                self.subs.remove(sub)


class SubscriberCore:
    """The checks of a decisions subscriber (FEP-0004 section 7; FEP-0001 rules).

    ``from_seq``: the ``from_seq`` of the first ``ws_subscribe`` (None: new decisions only).
    Feed every received message to :meth:`receive`. It returns
    ``("resubscribe", from_seq)`` when it finds a gap in ``ws_seq``: the
    client closes, connects again and sends ``ws_subscribe`` with that
    ``from_seq``; the messages before the next welcome are ignored.
    :meth:`finish` checks the FEP-0001 order rules and returns a summary.
    """

    def __init__(self, from_seq: int | None = 1) -> None:
        if from_seq is not None and not (_is_int(from_seq) and from_seq >= 1):
            raise ValueError("from_seq must be an integer >= 1 or None")
        #: None: the client asked for new decisions only; the first welcome's seq is the start point.
        self.from_seq = from_seq
        self.last = 0 if from_seq is None else from_seq - 1
        self.welcomed = False
        self.waiting = False
        self.events: list[dict[str, Any]] = []
        self.duplicates = 0
        self.gaps: list[int] = []
        self.missed = 0
        self.errors: list[str] = []
        self.ignored = 0

    def receive(self, msg: Any) -> tuple[str, int] | None:
        from fidetype.conformance.profiles.fep0001 import td_format_errors

        if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
            raise SubscriberError("a message must be a JSON object with a string type")
        typ = msg["type"]
        if typ == WS_WELCOME:
            b = msg.get("binding", BINDING_VERSION)
            if not isinstance(b, str) or b not in KNOWN_BINDINGS:
                raise SubscriberError(f"welcome: unknown binding {b!r} (section 10)")
            if msg.get("role", "decisions") != "decisions":
                raise SubscriberError(f"welcome: role {msg.get('role')!r} is not 'decisions'")
            for k in ("seq", "missed", "first_available"):
                if k in msg and not (_is_int(msg[k]) and msg[k] >= 0):
                    raise SubscriberError(f"welcome: {k} must be an integer >= 0")
            if not self.welcomed and self.from_seq is None and "seq" in msg:
                self.last = max(self.last, msg["seq"])  # new decisions only (section 7 rule 2)
            if msg.get("missed", 0) > 0:
                # The history before first_available is gone: count it and go on from there (section 7 rule 5).
                self.missed += msg["missed"]
                if "first_available" in msg:
                    self.last = max(self.last, msg["first_available"] - 1)
            self.welcomed, self.waiting = True, False
            return None
        if not self.welcomed:
            raise SubscriberError("the first message must be ws_welcome (section 7 rule 2)")
        if self.waiting:
            self.ignored += 1
            return None
        if typ != "trust_decision":
            self.ignored += 1  # ws_error, unknown types (spec 6.2 rule 5)
            return None
        seq = msg.get("ws_seq")
        if not (_is_int(seq) and seq >= 1):
            raise SubscriberError(f"ws_seq {seq!r} must be an integer >= 1 (section 7 rule 3)")
        if seq <= self.last:
            self.duplicates += 1
            return None
        if seq > self.last + 1:
            self.gaps.append(self.last + 1)
            self.waiting = True
            return ("resubscribe", self.last + 1)
        ev = dict(msg)
        ev["_line"] = len(self.events) + 1
        self.errors += td_format_errors(ev)
        self.events.append(ev)
        self.last = seq
        return None

    def finish(self) -> dict[str, Any]:
        from fidetype.conformance.profiles.fep0001 import acted_texts, td_final_errors

        errs = self.errors + td_final_errors(self.events)
        if errs:
            raise SubscriberError("; ".join(errs[:5]))
        return {"decisions": len(self.events), "final": sum(e.get("is_final") is True for e in self.events),
                "acted": acted_texts(self.events), "duplicates": self.duplicates, "gaps": list(self.gaps),
                "missed": self.missed, "last_seq": self.last}


# ---------------------------------------------------------------------------
# The trust runner (shared by the live server and the conformance profile)
# ---------------------------------------------------------------------------


@dataclass
class WSRunSummary:
    decisions: int = 0
    final_decisions: int = 0
    events: int = 0
    rejected_events: int = 0
    aborted_utterances: int = 0
    skipped_after_gap: int = 0
    streams_closed: int = 0
    ended_streams: int = 0
    wall_s: float = 0.0
    stop_reason: str = ""
    ingest: dict[str, Any] = field(default_factory=dict)
    e2e_latency_ms: dict[str, float] = field(default_factory=dict)
    server_latency_ms: dict[str, float] = field(default_factory=dict)
    transport_latency_ms: dict[str, float] = field(default_factory=dict)


def _pct_ms(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {}
    a = np.asarray(xs, dtype=np.float64) * 1e3
    return {"n": int(a.size), "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95)),
            "max": float(a.max())}


class WSTrustRunner:
    """Push the items of an :class:`IngestCore` (via a source) into a trust layer, one session per stream.

    Each decision becomes a ``trust_decision`` event (FEP-0001) with ``session`` = the stream id and an
    extra ``ws`` record (stream id, binding, receive and latency times). ``sink`` gets each event;
    ``hub`` (an :class:`OutputHub`) publishes it on ``/decisions``; ``events_hub`` gets the NTS events.

    Loss rules (FEP-0004 section 8): a ``gap`` (missing ``ws_seq``), a ``lost`` stream (resume
    time-out) or a ``replaced`` stream drops the open utterance **without** a decision. After a gap
    the ``frame`` events up to the next ``segment_end``, ``end`` or ``header`` are dropped too: they
    are the tail of the cut utterance, and a decision on them could commit a cut text.
    """

    def __init__(self, layer: Any, source: Any = None, sink: Callable[[dict[str, Any]], None] | None = None,
                 hub: OutputHub | None = None, events_hub: OutputHub | None = None, include_text: bool = True,
                 on_bad_event: Literal["skip", "raise"] = "skip", keep: bool = False,
                 clock: Callable[[], float] = time.perf_counter, log: Callable[[str], None] | None = None) -> None:
        self.layer = layer
        self.source = source
        self.sink = sink
        self.hub = hub
        self.events_hub = events_hub
        self.include_text = include_text
        self.on_bad_event = on_bad_event
        self.keep = keep
        self.kept: list[Any] = []
        self.clock = clock
        self.log = log or (lambda m: None)
        self.summary = WSRunSummary()
        self.utt: dict[str, dict[str, int]] = {}
        #: Streams that drop frames until the next utterance boundary (after a gap).
        self.skip: set[str] = set()
        self._e2e: list[float] = []
        self._srv: list[float] = []
        self._tr: list[float] = []

    def _pending(self, sid: str) -> bool:
        try:
            st = self.layer.session_state(sid)
        except KeyError:
            return False
        return bool(st["buffered_frames"] or st["has_hypothesis"])

    def abort(self, sid: str, why: str) -> None:
        if self._pending(sid):
            self.summary.aborted_utterances += 1
            self.log(f"abort utterance of stream {sid}: {why}")
        self.layer.abort_utterance(sid)
        self.utt[sid] = {"frames": 0, "gaps": 0}

    def handle(self, items: Iterable[tuple[str, dict[str, Any]]]) -> list[Any]:
        from fidetype.trust.streaming import StreamEventError

        out: list[Any] = []
        for sid, ev in items:
            typ = ev.get("type")
            u = self.utt.setdefault(sid, {"frames": 0, "gaps": 0})
            if typ == WS_STATUS:
                st = ev.get("status")
                self.log(f"stream {sid}: {st}" + (f" ({ev.get('missing')} events missing)" if st == "gap" else ""))
                if st == "gap":
                    u["gaps"] += 1
                    self.abort(sid, "ws_seq gap")
                    self.skip.add(sid)
                elif st in ("lost", "replaced"):
                    self.abort(sid, str(st))
                    self.skip.discard(sid)
                elif st == "closed":
                    self.summary.streams_closed += 1
                    for d in self.layer.close(sid):
                        out.append(self._emit(sid, d, None))
                continue
            if "ws_t_sent" in ev and "ws_t_recv" in ev and _is_num(ev["ws_t_sent"]) and _is_num(ev["ws_t_recv"]):
                self._tr.append(float(ev["ws_t_recv"]) - float(ev["ws_t_sent"]))
            if self.events_hub is not None and self.events_hub.has_subscribers:
                self.events_hub.publish({**ev, "stream_id": sid})
            if sid in self.skip:
                if typ == "frame":
                    self.summary.skipped_after_gap += 1
                    continue
                if typ in ("segment_end", "end", "header"):
                    self.skip.discard(sid)
            if typ == "frame":
                u["frames"] += 1
            self.summary.events += 1
            try:
                ds = self.layer.push(ev, sid)
            except StreamEventError as e:
                self.summary.rejected_events += 1
                self.log(f"stream {sid}: rejected {typ} event: {e}")
                if self.on_bad_event == "raise":
                    raise
                continue
            for d in ds:
                out.append(self._emit(sid, d, ev))
            if typ == "end":
                self.summary.ended_streams += 1
        return out

    def flush(self, sid: str) -> list[Any]:
        return [self._emit(sid, d, None) for d in self.layer.end_of_utterance(sid)]

    def _emit(self, sid: str, d: Any, trigger: dict[str, Any] | None) -> Any:
        now = self.clock()
        rec: dict[str, Any] = {"stream_id": sid, "binding": BINDING_VERSION,
                               "utterance": dict(self.utt.get(sid, {}))}
        if trigger is not None:
            if _is_num(trigger.get("ws_seq")):
                rec["trigger_seq"] = trigger["ws_seq"]
            if _is_num(trigger.get("ws_t_recv")):
                rec["server_latency_s"] = now - float(trigger["ws_t_recv"])
                if d.final:
                    self._srv.append(rec["server_latency_s"])
            if _is_num(trigger.get("ws_t_sent")):
                rec["e2e_latency_s"] = now - float(trigger["ws_t_sent"])
                if d.final:
                    self._e2e.append(rec["e2e_latency_s"])
        rec["t_emit"] = now
        d.provenance["ws"] = rec
        ev = d.to_event(include_text=self.include_text)
        ev["ws"] = rec
        if self.hub is not None:
            ev = self.hub.publish(ev)
        if self.sink is not None:
            self.sink(ev)
        self.summary.decisions += 1
        if d.final:
            self.summary.final_decisions += 1
            self.utt[sid] = {"frames": 0, "gaps": 0}
        if self.keep:
            self.kept.append(d)
        return d

    def step(self, timeout: float = 0.05) -> list[Any]:
        return self.handle(self.source.poll(timeout))

    def run(self, duration_s: float | None = None, max_decisions: int | None = None,
            max_streams: int | None = None, poll_timeout: float = 0.05,
            stop: threading.Event | None = None) -> WSRunSummary:
        """Loop until the duration, the decision count, ``max_streams`` ended streams, or ``stop``."""
        t0 = time.monotonic()
        reason = ""
        try:
            while True:
                if stop is not None and stop.is_set():
                    reason = "stopped"
                    break
                if duration_s is not None and time.monotonic() - t0 >= duration_s:
                    reason = "duration"
                    break
                self.step(poll_timeout)
                if max_decisions is not None and self.summary.final_decisions >= max_decisions:
                    reason = "max_decisions"
                    break
                if max_streams is not None and self.summary.ended_streams >= max_streams:
                    reason = "max_streams"
                    break
        except KeyboardInterrupt:
            reason = "interrupted"
        self.handle(self.source.finish())
        for sid in list(self.layer.sessions):
            if self._pending(sid):
                self.abort(sid, f"run stopped ({reason}) inside an utterance")
        self.summary.stop_reason = reason
        self.summary.wall_s = time.monotonic() - t0
        self.summary.ingest = self.source.core.stats.as_dict()
        self.summary.e2e_latency_ms = _pct_ms(self._e2e)
        self.summary.server_latency_ms = _pct_ms(self._srv)
        self.summary.transport_latency_ms = _pct_ms(self._tr)
        return self.summary


# ---------------------------------------------------------------------------
# The live server
# ---------------------------------------------------------------------------


@dataclass
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    #: Allowed ``Origin`` values for browser clients (None: any origin, and clients without Origin).
    origins: Sequence[str] | None = None
    #: Shared token (auth hook). None: no auth.
    token: str | None = None
    #: An ``ssl.SSLContext`` for wss:// (else plain ws://; see FEP-0004 section 9).
    ssl: Any = None
    #: Items waiting for the runner before a producer handler stops reading (back-pressure).
    queue_max: int = 8192
    #: Plain HTTP GET routes for the browser example: URL prefix -> directory.
    static: dict[str, str] = field(default_factory=dict)
    ping_interval: float | None = 5.0
    ping_timeout: float | None = 10.0
    subscribe_timeout_s: float = 5.0


class WSServer:
    """The reference server: ``/nts`` input, ``/decisions`` and ``/events`` output.

    Producer handlers run :class:`IngestCore` under one lock and put the items in one ordered
    queue. The runner thread reads them with :meth:`poll` (which also runs the time-outs).
    """

    def __init__(self, ingest: IngestSettings | None = None, settings: ServerSettings | None = None,
                 decisions: OutputHub | None = None, events: OutputHub | None = None,
                 clock: Callable[[], float] = time.perf_counter, log: Callable[[str], None] | None = None) -> None:
        self.settings = settings or ServerSettings()
        auth = token_checker(self.settings.token) if self.settings.token else None
        self.core = IngestCore(ingest, auth=auth, stamp=True)
        self.decisions = decisions or OutputHub("decisions")
        self.events = events or OutputHub("events", resumable=False)
        self.clock = clock
        self.log = log or (lambda m: None)
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        self.items: collections.deque[tuple[str, dict[str, Any]]] = collections.deque()
        self.conns: dict[int, Any] = {}
        self._cid = itertools.count(1)
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self.stopping = threading.Event()

    # --- lifecycle -------------------------------------------------------------------

    @property
    def port(self) -> int:
        return int(self._server.socket.getsockname()[1])

    @property
    def url(self) -> str:
        scheme = "wss" if self.settings.ssl is not None else "ws"
        return f"{scheme}://{self.settings.host}:{self.port}"

    def start(self) -> "WSServer":
        require_websockets()
        from websockets.sync.server import serve

        s = self.settings
        self._server = serve(self._handler, s.host, s.port, subprotocols=[SUBPROTOCOL],
                             origins=list(s.origins) if s.origins is not None else None,
                             process_request=self._process_request, max_size=MAX_MESSAGE_BYTES, ssl=s.ssl,
                             ping_interval=s.ping_interval, ping_timeout=s.ping_timeout, close_timeout=2.0)
        self._thread = threading.Thread(target=self._server.serve_forever, name="fidetype-ws-server", daemon=True)
        self._thread.start()
        self.log(f"listening on {self.url} (paths {PATH_INGEST}, {PATH_DECISIONS}, {PATH_EVENTS})")
        return self

    def stop(self) -> None:
        self.stopping.set()
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(5)

    def __enter__(self) -> "WSServer":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    # --- HTTP (static files for the browser example) ---------------------------------

    def _process_request(self, connection: Any, request: Any) -> Any:
        path = request.path.split("?", 1)[0]
        upgrade = request.headers.get("Upgrade", "").lower() == "websocket"
        if upgrade:
            if path not in (PATH_INGEST, PATH_DECISIONS, PATH_EVENTS):
                return connection.respond(404, "unknown path\n")
            return None
        return self._static(connection, path)

    def _static(self, connection: Any, path: str) -> Any:
        from websockets.datastructures import Headers
        from websockets.http11 import Response

        for prefix, root in sorted(self.settings.static.items(), key=lambda kv: -len(kv[0])):
            if not path.startswith(prefix):
                continue
            rel = path[len(prefix):].lstrip("/") or "index.html"
            base = Path(root).resolve()
            p = (base / rel).resolve()
            if base not in p.parents or not p.is_file():
                break
            body = p.read_bytes()
            ctype = {".js": "text/javascript", ".mjs": "text/javascript", ".html": "text/html", ".css": "text/css",
                     ".map": "application/json", ".json": "application/json"}.get(p.suffix.lower()) \
                or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            headers = Headers([("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text") else ctype),
                               ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                               ("X-Content-Type-Options", "nosniff")])
            return Response(200, "OK", headers, body)
        return connection.respond(404, "not found\n")

    # --- connections -----------------------------------------------------------------

    def _apply(self, eff: Effects) -> None:
        """Send and close (outside the core lock). Items are queued inside the lock by the caller."""
        from websockets.exceptions import ConnectionClosed

        for cid, msg in eff.sends:
            c = self.conns.get(cid)
            if c is None:
                continue
            try:
                c.send(dumps(msg))
            except ConnectionClosed:
                pass
        for cid, code, reason in eff.closes:
            c = self.conns.get(cid)
            if c is not None:
                threading.Thread(target=c.close, args=(code, reason), daemon=True).start()

    def _core(self, fn: Callable[..., Effects], *args: Any) -> Effects:
        with self.cv:
            eff = fn(*args)
            if eff.items:
                self.items.extend(eff.items)
                self.cv.notify_all()
        self._apply(eff)
        return eff

    def _handler(self, connection: Any) -> None:
        path = connection.request.path.split("?", 1)[0]
        if path == PATH_INGEST:
            self._producer(connection)
        else:
            self._subscriber(connection, self.decisions if path == PATH_DECISIONS else self.events)

    def _producer(self, connection: Any) -> None:
        from websockets.exceptions import ConnectionClosed

        cid = next(self._cid)
        self.conns[cid] = connection
        self._core(self.core.open, cid, [connection.subprotocol] if connection.subprotocol else [],
                   connection.request.headers.get("Authorization"), self.clock())
        try:
            for data in connection:
                eff = self._core(self.core.message, cid, data, self.clock())
                if eff.closes and any(c == cid for c, _, _ in eff.closes):
                    break
                # Back-pressure: stop reading while the runner is behind (TCP then slows the producer).
                while len(self.items) > self.settings.queue_max and not self.stopping.is_set():
                    time.sleep(0.002)
        except ConnectionClosed:
            pass
        finally:
            self._core(self.core.disconnect, cid, self.clock())
            self.conns.pop(cid, None)

    def _subscriber(self, connection: Any, hub: OutputHub) -> None:
        import queue

        from websockets.exceptions import ConnectionClosed

        auth = token_checker(self.settings.token) if self.settings.token else None
        authed = auth is None or auth(bearer_token(connection.request.headers.get("Authorization")))
        sub = None
        try:
            req: dict[str, Any] | None = None
            deadline = time.monotonic() + self.settings.subscribe_timeout_s
            while req is None:
                raw = connection.recv(timeout=max(0.01, deadline - time.monotonic()))
                if not isinstance(raw, str):
                    connection.close(CLOSE_BINARY, "binary")
                    return
                try:
                    msg = parse_message(raw)
                except ValueError as e:
                    connection.send(dumps({"type": WS_ERROR, "code": "bad_message", "detail": str(e)[:200]}))
                    connection.close(CLOSE_INVALID, "bad_message")
                    return
                if msg["type"] == WS_AUTH and not authed:
                    authed = auth is not None and auth(msg.get("token") if isinstance(msg.get("token"), str) else None)
                    continue
                if not authed:
                    connection.send(dumps({"type": WS_ERROR, "code": "auth", "detail": "authentication failed"}))
                    connection.close(CLOSE_POLICY, "auth")
                    return
                if msg["type"] == WS_SUBSCRIBE:
                    req = msg
            try:
                sub, welcome, replay = hub.subscribe(req)
            except ValueError as e:
                connection.send(dumps({"type": WS_ERROR, "code": "bad_subscribe", "detail": str(e)}))
                connection.close(CLOSE_INVALID if "binding" not in str(e) else CLOSE_BINDING, "bad_subscribe")
                return
            connection.send(dumps(welcome))
            for m in replay:
                connection.send(dumps(m))
            while not self.stopping.is_set():
                if sub.overflow:
                    connection.send(dumps({"type": WS_ERROR, "code": "slow_consumer",
                                           "detail": "subscriber queue full; resubscribe with from_seq"}))
                    connection.close(CLOSE_TRY_LATER, "slow_consumer")
                    return
                try:
                    m = sub.q.get(timeout=0.25)
                except queue.Empty:
                    continue
                connection.send(dumps(m))
        except (ConnectionClosed, TimeoutError):
            pass
        finally:
            if sub is not None:
                hub.unsubscribe(sub)

    # --- the poll interface of the runner ---------------------------------------------

    def poll(self, timeout: float = 0.05) -> list[tuple[str, dict[str, Any]]]:
        with self.cv:
            eff = self.core.tick(self.clock())
            self.items.extend(eff.items)
            if not self.items and timeout > 0:
                self.cv.wait(timeout)
                eff2 = self.core.tick(self.clock())
                self.items.extend(eff2.items)
                eff.sends += eff2.sends
                eff.closes += eff2.closes
            out = list(self.items)
            self.items.clear()
        self._apply(Effects(eff.sends, [], eff.closes))
        return out

    def finish(self) -> list[tuple[str, dict[str, Any]]]:
        with self.cv:
            eff = self.core.finish(self.clock())
            out = list(self.items) + eff.items
            self.items.clear()
        return out


#: The runner's source is the server itself (``poll``, ``finish``, ``core``).
WSEventSource = WSServer


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class WSProducer:
    """A producer client of ``/nts`` with resend-on-resume (FEP-0004 sections 5-8).

    It numbers the events (``ws_seq`` 1, 2, ...), keeps the unacknowledged ones, and waits when
    ``window`` of them are in flight (back-pressure). If the connection breaks, the next call
    connects again with ``ws.resume = true`` and resends every event after the server's ``seq``.

    Test hooks: :meth:`drop` breaks the TCP connection without a close handshake; ``lose`` is a
    set of ``ws_seq`` values that are counted but never sent (to make gaps).
    """

    def __init__(self, url: str, header: dict[str, Any], stream_id: str | None = None, token: str | None = None,
                 batch: int = 1, window: int | None = None, reconnect_timeout_s: float = 10.0,
                 stamp: bool = True, clock: Callable[[], float] = time.perf_counter, open_timeout: float = 10.0,
                 ssl: Any = None, lose: Iterable[int] = (), log: Callable[[str], None] | None = None) -> None:
        require_websockets()
        self.url = url
        self.header = {k: v for k, v in header.items() if k != "ws"}
        self.header["type"] = "header"
        self.stream_id = stream_id
        self.token = token
        self.batch = max(1, int(batch))
        self.window = window
        self.reconnect_timeout_s = reconnect_timeout_s
        self.stamp = stamp
        self.clock = clock
        self.open_timeout = open_timeout
        self.ssl = ssl
        self.lose = set(lose)
        self.log = log or (lambda m: None)
        self.conn: Any = None
        self.seq = 0
        self.acked = 0
        self.unacked: collections.deque[dict[str, Any]] = collections.deque()
        self.pending: list[dict[str, Any]] = []
        #: Highest ws_seq handed to the socket (events after it are in ``pending``).
        self.sent_upto = 0
        self.reconnects = 0
        self.welcome: dict[str, Any] = {}

    def _connect(self, resume: bool) -> None:
        from websockets.sync.client import connect

        hdrs = {"Authorization": f"Bearer {self.token}"} if self.token else None
        # legacy=True: a long-lived connection object (websockets 17 otherwise expects a context manager).
        self.conn = connect(self.url, subprotocols=[SUBPROTOCOL], additional_headers=hdrs,
                            open_timeout=self.open_timeout, max_size=MAX_MESSAGE_BYTES, ssl=self.ssl,
                            close_timeout=2.0, legacy=True)
        ws: dict[str, Any] = {"binding": BINDING_VERSION, "resume": resume}
        if self.stream_id:
            ws["stream_id"] = self.stream_id
        self.conn.send(dumps({**self.header, "ws": ws}))
        w = parse_message(self.conn.recv(timeout=self.open_timeout))
        if w.get("type") == WS_ERROR:
            raise WSRefused(f"{w.get('code')}: {w.get('detail')}")
        if w.get("type") != WS_WELCOME:
            raise WSRefused(f"expected ws_welcome, got {w.get('type')!r}")
        self.welcome = w
        self.stream_id = w.get("stream_id", self.stream_id)
        if self.window is None:
            self.window = int(w.get("window", 4096))
        if resume and not w.get("resumed"):
            raise WSRefused("the server lost the stream state; start a new stream")
        self._trim(int(w.get("seq", 0)))

    def connect(self) -> "WSProducer":
        self._connect(resume=False)
        return self

    def _trim(self, seq: int) -> None:
        self.acked = max(self.acked, seq)
        while self.unacked and self.unacked[0]["ws_seq"] <= self.acked:
            self.unacked.popleft()

    def _handle_control(self, raw: Any) -> None:
        if not isinstance(raw, str):
            return
        m = parse_message(raw)
        if m.get("type") == WS_ACK and _is_int(m.get("seq")):
            self._trim(m["seq"])
        elif m.get("type") == WS_ERROR:
            raise WSRefused(f"{m.get('code')}: {m.get('detail')}")

    def _pump(self, block: bool) -> None:
        from websockets.exceptions import ConnectionClosed

        while True:
            try:
                raw = self.conn.recv(timeout=0.5 if block else 0)
            except TimeoutError:
                return
            except ConnectionClosed:
                raise
            self._handle_control(raw)
            block = False

    def _transmit(self, evs: list[dict[str, Any]]) -> None:
        evs = [e for e in evs if e["ws_seq"] not in self.lose]
        if not evs:
            return
        if self.stamp:
            t = self.clock()
            evs = [{**e, "ws_t_sent": t} for e in evs]
        if len(evs) == 1:
            self.conn.send(dumps(evs[0]))
        else:
            for i in range(0, len(evs), 1024):
                self.conn.send(dumps({"type": WS_BATCH, "events": evs[i:i + 1024]}))

    def _with_reconnect(self, fn: Callable[[], None]) -> None:
        from websockets.exceptions import ConnectionClosed, InvalidHandshake

        t0 = time.monotonic()
        while True:
            try:
                if self.conn is None:
                    self._connect(resume=True)
                    self.reconnects += 1
                    self.log(f"resumed stream {self.stream_id} at seq {self.acked}; resending {len(self.unacked)}")
                    resend = [e for e in self.unacked if e["ws_seq"] <= self.sent_upto]
                    if resend:
                        self._transmit(resend)
                fn()
                return
            except (ConnectionClosed, OSError, InvalidHandshake, TimeoutError) as e:
                self.conn = None
                if time.monotonic() - t0 > self.reconnect_timeout_s:
                    raise WSRefused(f"cannot resume within {self.reconnect_timeout_s} s: {e}") from e
                time.sleep(0.05)

    def send(self, event: dict[str, Any]) -> None:
        """Queue one NTS event. Sends when a batch is full or the event is not a frame.

        The first header goes with the constructor (the handshake). A later ``header`` (a new NTS
        stream inside this WebSocket stream, spec 6.2) is an ordinary event with a ``ws_seq``.
        """
        self.seq += 1
        ev = {**event, "ws_seq": self.seq}
        self.unacked.append(ev)
        self.pending.append(ev)
        if len(self.pending) >= self.batch or ev.get("type") != "frame":
            self.flush()

    def flush(self) -> None:
        def go() -> None:
            if self.pending:
                self._transmit(self.pending)
                self.sent_upto = self.pending[-1]["ws_seq"]
                self.pending = []
            self._pump(block=False)
            while self.window is not None and len(self.unacked) >= self.window:
                self._pump(block=True)

        self._with_reconnect(go)

    def drop(self) -> None:
        """Test hook: break the TCP connection without a close handshake. The next call resumes."""
        import socket

        if self.conn is not None:
            try:
                self.conn.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.conn = None

    def close(self, wait_ack_s: float = 5.0) -> None:
        """Flush, wait until the server acknowledged every event (or the time-out), then close."""
        self.flush()
        t0 = time.monotonic()

        def wait() -> None:
            while self.unacked and time.monotonic() - t0 < wait_ack_s:
                self._pump(block=True)

        self._with_reconnect(wait)
        if self.conn is not None:
            self.conn.close()
            self.conn = None


@dataclass
class ReplaySummary:
    events: int = 0
    frames: int = 0
    stream_id: str | None = None
    reconnects: int = 0
    wall_s: float = 0.0


def _event_list(source: str | PathLike[str] | Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    from fidetype.trust.streaming import iter_events, parse_event

    if isinstance(source, (str, PathLike)):
        return list(iter_events(source))
    return [parse_event(e) for e in source]


def replay_to_ws(source: str | PathLike[str] | Iterable[dict[str, Any]], url: str, stream_id: str | None = None,
                 speed: float = 1.0, batch: int = 1, token: str | None = None, drop_at: Iterable[int] = (),
                 lose: Iterable[int] = (), stop: threading.Event | None = None, ssl: Any = None,
                 log: Callable[[str], None] | None = None) -> ReplaySummary:
    """Send a NeuralTextStream (file or events) to ``url`` (the ``/nts`` path), paced by the frame times.

    ``speed`` 1.0 = real time, 0 = no pacing. A non-frame event goes right after the previous frame.
    ``drop_at``: event indices (1 = first event after the header) before which the connection is
    broken (test hook; the producer resumes). ``lose``: ``ws_seq`` values that are never sent.
    """
    evs = _event_list(source)
    if not evs or evs[0].get("type") != "header":
        raise ValueError("the stream must start with a header event")
    drops = set(drop_at)
    rs = ReplaySummary()
    w0 = time.monotonic()
    prod = WSProducer(url, evs[0], stream_id=stream_id, token=token, batch=batch, ssl=ssl, lose=lose, log=log).connect()
    rs.stream_id = prod.stream_id
    t_file0 = next((float(e["t"]) for e in evs if e.get("type") == "frame"), 0.0)
    base = time.perf_counter()
    for k, e in enumerate(evs[1:], 1):
        if stop is not None and stop.is_set():
            break
        if k in drops:
            prod.flush()
            prod.drop()
        if e.get("type") == "frame" and speed > 0:
            wait = base + (float(e["t"]) - t_file0) / speed - time.perf_counter()
            if wait > 0:
                prod.flush()
                time.sleep(wait)
            rs.frames += 1
        elif e.get("type") == "frame":
            rs.frames += 1
        prod.send(e)
        rs.events += 1
    prod.close()
    rs.reconnects = prod.reconnects
    rs.wall_s = time.monotonic() - w0
    return rs


def subscribe(url: str, on_decision: Callable[[dict[str, Any]], None], from_seq: int | None = None,
              token: str | None = None, types: Sequence[str] | None = None, stop: threading.Event | None = None,
              max_decisions: int | None = None, duration_s: float | None = None, reconnect: bool = True,
              ssl: Any = None, log: Callable[[str], None] | None = None) -> SubscriberCore:
    """Subscribe to ``/decisions``; call ``on_decision`` once per decision, in ``ws_seq`` order.

    On a gap or a lost connection it resubscribes with ``from_seq`` = the next expected ``ws_seq``.
    Returns the :class:`SubscriberCore` (counts, gaps, duplicates).
    """
    require_websockets()
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    log = log or (lambda m: None)
    core = SubscriberCore(from_seq)
    t0 = time.monotonic()
    nxt = from_seq
    while True:
        if stop is not None and stop.is_set():
            break
        if duration_s is not None and time.monotonic() - t0 >= duration_s:
            break
        try:
            hdrs = {"Authorization": f"Bearer {token}"} if token else None
            with connect(url, subprotocols=[SUBPROTOCOL], additional_headers=hdrs, ssl=ssl, close_timeout=2.0) as c:
                req: dict[str, Any] = {"type": WS_SUBSCRIBE, "binding": BINDING_VERSION}
                if nxt is not None:
                    req["from_seq"] = nxt
                if types is not None:
                    req["types"] = list(types)
                c.send(dumps(req))
                while True:
                    if stop is not None and stop.is_set():
                        return core
                    if duration_s is not None and time.monotonic() - t0 >= duration_s:
                        return core
                    try:
                        raw = c.recv(timeout=0.25)
                    except TimeoutError:
                        continue
                    msg = parse_message(raw) if isinstance(raw, str) else None
                    if msg is None:
                        continue
                    if msg.get("type") == WS_ERROR and msg.get("code") not in ("slow_consumer",):
                        raise WSRefused(f"{msg.get('code')}: {msg.get('detail')}")
                    n0 = len(core.events)
                    act = core.receive(msg)
                    if len(core.events) > n0:
                        on_decision(core.events[-1])
                        if max_decisions is not None and sum(e.get("is_final") is True for e in core.events) >= max_decisions:
                            return core
                    if act is not None:
                        nxt = act[1]
                        log(f"gap in ws_seq: resubscribe from {nxt}")
                        break
                    if msg.get("type") == WS_WELCOME and nxt is None:
                        nxt = core.last + 1
        except (ConnectionClosed, OSError) as e:
            if not reconnect:
                raise
            log(f"connection lost ({type(e).__name__}); resubscribe")
            time.sleep(0.1)
        nxt = core.last + 1 if core.last else nxt
    return core


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _stderr(msg: str) -> None:
    sys.stderr.write(f"[fidetype.ws] {msg}\n")
    sys.stderr.flush()


def _jsonl_sink(fh: TextIO) -> Callable[[dict[str, Any]], None]:
    def sink(ev: dict[str, Any]) -> None:
        fh.write(json.dumps(ev, ensure_ascii=False, allow_nan=False) + "\n")
        fh.flush()

    return sink


def _token_from_env(name: str | None) -> str | None:
    import os

    if not name:
        return None
    tok = os.environ.get(name)
    if not tok:
        raise SystemExit(f"environment variable {name} is empty or not set")
    return tok


def _ssl_context(certfile: str | None, keyfile: str | None, server: bool) -> Any:
    if not certfile:
        return None
    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile, keyfile)
    return ctx


def example_static_routes() -> dict[str, str]:
    """The routes of ``run --serve-example``: the browser page and the built TypeScript SDK."""
    root = Path(__file__).resolve().parents[3]
    return {"/sdk/": str(root / "sdk" / "typescript" / "dist"), "/": str(root / "examples" / "ws-browser")}


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m fidetype.adapters.ws {run,replay-to-ws,subscribe}``"""
    import argparse

    ap = argparse.ArgumentParser(prog="python -m fidetype.adapters.ws",
                                 description="WebSocket input/output for Fidetype (M6-11, FEP-0004).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="WebSocket server: /nts -> streaming trust layer -> /decisions (+ JSON Lines on stdout)")
    r.add_argument("--config", required=True, help="FrozenTrustConfig JSON file")
    r.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    r.add_argument("--port", type=int, default=DEFAULT_PORT)
    r.add_argument("--decoder", choices=("none", "greedy", "demo"), default="none",
                   help="frame decoder: none (hypothesis route), greedy (CTC greedy) or demo (beam + LM)")
    r.add_argument("--reorder-window", type=int, default=16)
    r.add_argument("--reorder-timeout", type=float, default=0.25)
    r.add_argument("--resume-timeout", type=float, default=10.0)
    r.add_argument("--token-env", help="require this shared token (read from the named environment variable)")
    r.add_argument("--allow-origin", action="append", default=None, help="allowed browser Origin (repeatable)")
    r.add_argument("--certfile", help="TLS certificate (PEM) for wss://")
    r.add_argument("--keyfile", help="TLS private key (PEM)")
    r.add_argument("--serve-example", action="store_true",
                   help="also serve the browser example (examples/ws-browser) and the TS SDK over HTTP")
    r.add_argument("--duration", type=float, default=None)
    r.add_argument("--max-decisions", type=int, default=None)
    r.add_argument("--max-streams", type=int, default=None, help="stop after this many streams sent end")
    r.add_argument("--no-text", action="store_true", help="omit the shown texts from the output")
    r.add_argument("--quiet", action="store_true", help="no decisions on stdout")
    r.add_argument("--max-attempts", type=int, default=2)
    r.add_argument("--summary", help="write the run summary JSON to this file")

    p = sub.add_parser("replay-to-ws", help="send a NeuralTextStream file to a server's /nts path")
    p.add_argument("file")
    p.add_argument("--url", default=f"ws://127.0.0.1:{DEFAULT_PORT}{PATH_INGEST}")
    p.add_argument("--stream-id")
    p.add_argument("--speed", type=float, default=1.0, help="1 = real time, 0 = no pacing")
    p.add_argument("--batch", type=int, default=1, help="frames per ws_batch message")
    p.add_argument("--token-env")
    p.add_argument("--loop", type=int, default=1)

    s = sub.add_parser("subscribe", help="print the decisions of a server's /decisions path as JSON Lines")
    s.add_argument("--url", default=f"ws://127.0.0.1:{DEFAULT_PORT}{PATH_DECISIONS}")
    s.add_argument("--from-seq", type=int, default=None)
    s.add_argument("--token-env")
    s.add_argument("--max-decisions", type=int, default=None)
    s.add_argument("--duration", type=float, default=None)

    a = ap.parse_args(argv)
    try:
        if a.cmd == "replay-to-ws":
            for i in range(max(1, a.loop)):
                sid = f"{a.stream_id}-{i}" if (a.stream_id and a.loop > 1) else a.stream_id
                rs = replay_to_ws(a.file, a.url, sid, a.speed, a.batch, _token_from_env(a.token_env), log=_stderr)
                _stderr(f"sent {rs.events} events ({rs.frames} frames) in {rs.wall_s:.2f} s, "
                        f"{rs.reconnects} reconnects (pass {i + 1})")
            return 0
        if a.cmd == "subscribe":
            out = _jsonl_sink(sys.stdout)
            core = subscribe(a.url, out, a.from_seq, _token_from_env(a.token_env), max_decisions=a.max_decisions,
                             duration_s=a.duration, log=_stderr)
            _stderr(f"{len(core.events)} decisions, {len(core.gaps)} resubscribes, {core.duplicates} duplicates")
            return 0
        return _run_cli(a)
    except WSUnavailableError as e:
        _stderr(str(e))
        return 2
    except WSRefused as e:
        _stderr(f"refused: {e}")
        return 3
    except OSError as e:
        _stderr(f"connection failed: {e}")
        return 3


def _run_cli(a: Any) -> int:
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, frame_decoder

    cfg = FrozenTrustConfig.load(a.config)
    layer = StreamingTrustLayer(cfg, decode_fn=frame_decoder(a.decoder),
                                streaming=StreamingConfig(max_attempts=a.max_attempts))
    ingest = IngestSettings(reorder_window=a.reorder_window, reorder_timeout_s=a.reorder_timeout,
                            resume_timeout_s=a.resume_timeout)
    settings = ServerSettings(host=a.host, port=a.port, origins=a.allow_origin, token=_token_from_env(a.token_env),
                              ssl=_ssl_context(a.certfile, a.keyfile, server=True),
                              static=example_static_routes() if a.serve_example else {})
    if a.host not in ("127.0.0.1", "localhost", "::1") and settings.ssl is None:
        _stderr("WARNING: listening beyond localhost without TLS; use wss:// (FEP-0004 section 9)")
    hub = OutputHub("decisions", welcome_extra={"spec": "FEP-0001", "config_id": cfg.config_id})
    server = WSServer(ingest, settings, decisions=hub, log=_stderr).start()
    if a.serve_example:
        _stderr(f"browser example: http://{a.host}:{server.port}/")
    runner = WSTrustRunner(layer, server, sink=None if a.quiet else _jsonl_sink(sys.stdout), hub=hub,
                           events_hub=server.events, include_text=not a.no_text, log=_stderr)
    try:
        s = runner.run(duration_s=a.duration, max_decisions=a.max_decisions, max_streams=a.max_streams)
    finally:
        server.stop()
    _stderr(f"stop ({s.stop_reason}): {s.final_decisions} final decisions, {s.events} events, "
            f"{s.rejected_events} rejected, {s.aborted_utterances} aborted")
    if a.summary:
        Path(a.summary).write_text(json.dumps(asdict(s), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
