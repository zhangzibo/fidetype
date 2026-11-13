"""Lab Streaming Layer (LSL) adapter: live LSL streams <-> NeuralTextStream (M6-01).

LSL (https://labstreaminglayer.org/) moves time series between programs
on a network, with clock synchronisation. Its Python binding ``pylsl``
is MIT-licensed; the Windows wheel of ``pylsl`` 1.18.6 ships ``liblsl``
(``pylsl/lib/lsl.dll``). ``pylsl`` is an **optional** dependency
(``pip install "fidetype[lsl]"``). This module imports without it. Only
the functions that touch the network need it; they raise
:class:`LSLUnavailableError` with an install hint.

This is our own code (Apache-2.0). No LSL code is copied.

Directions
----------
Inlet (LSL -> NTS events)
    :class:`LSLEventSource` reads one primary LSL inlet and an optional
    events inlet. It yields NeuralTextStream events (spec v0.1, 6.2 JSON
    objects): first a ``header`` built from the LSL stream info, then
    ``frame`` events (one per LSL sample), and the events of a string
    marker stream (JSON NTS events, or plain markers mapped to
    ``segment_end`` / ``hypothesis``).
Runner (LSL -> trust layer -> decisions)
    :class:`LSLTrustRunner` pushes these events into a
    :class:`~fidetype.trust.streaming.StreamingTrustLayer` and writes
    each ``trust_decision`` event (FEP-0001) as one JSON line, and
    optionally to an LSL marker outlet ``fidetype.decisions``.
Outlet (NTS file -> LSL)
    :func:`replay_to_lsl` publishes a stream file (JSON Lines or NPZ) as
    LSL streams, paced in real time. For demos and tests.

NTS over LSL (spec 6.4, as implemented here)
--------------------------------------------
- **Frames stream**: type ``"NTS"``, V numeric channels (one per vocab
  token, in vocab order), one sample per frame, ``nominal_srate`` =
  1 / ``frame_period`` (0 if irregular). Channel labels = vocab tokens,
  channel unit ``log_prob``. The desc has a ``fidetype`` element with
  ``nts_header`` (the NTS header as JSON, so a late joiner gets it),
  ``values`` (``log_probs``) and ``events_source_id``.
- **Events stream**: type ``"Markers"``, 1 string channel, irregular
  rate. One sample = one NTS event as JSON (6.2). Its desc has the same
  ``nts_header`` and ``frames_source_id``.
- The LSL sample timestamp is the event time. The inlet sets
  ``clock_domain = "lsl"`` and replaces the ``t`` of frames with the LSL
  time. It adds ``lsl_t`` to marker events.
- Spec 6.4 names a ``float32`` frames stream. :func:`replay_to_lsl` can
  also send ``double64``: then the received rows are bit-equal to the
  file rows (float32 rounds them by about 1e-7).

Foreign streams (not made by Fidetype) work too:

- A numeric stream of class probabilities: pass ``vocab`` (or let the
  channel labels be the vocab) and ``values`` = ``log_probs``,
  ``probs`` or ``logits``.
- A raw signal stream (EEG, EMG): pass a :class:`SignalDecoder`. It
  turns sample chunks into frames. Fidetype ships no EEG decoder.
- A marker stream: JSON NTS events, or plain strings. ``boundary_markers``
  become ``segment_end``. With ``plain_markers="hypothesis"`` other
  strings become final 1-best text hypotheses (``score_semantics`` none).

Clock, order, gaps, loss
------------------------
- ``clock="receiver"`` (default): t = LSL timestamp + the inlet's
  ``time_correction()`` (refreshed every ``clock_refresh_s``). Inlets
  from the same sender host share one offset, so the merge order of a
  frames and an events stream from one host is not changed by offset
  noise. ``clock="sender"``: raw timestamps.
- Every decision carries an ``lsl`` provenance record: stream ids, clock
  mode, the current offset, the number of offset updates, and the
  per-utterance counts of gaps, clamped and dropped samples.
- **Out of order.** NTS frame times must increase strictly. A timestamp
  <= the last one is moved to just after it if it is at most
  ``clamp_tolerance_s`` behind (``out_of_order="clamp"``), else dropped
  and counted. ``"drop"`` drops all; ``"error"`` raises.
- **Gaps.** A frame step above ``gap_factor`` nominal periods is a gap.
  ``on_gap="mark"`` (default) emits an extension ``gap`` event (the
  layer ignores it; the count goes into provenance). ``"segment"`` ends
  the utterance there (a decision on the frames before the gap).
  ``"abort"`` drops the utterance without a decision.
- **Loss / reconnect.** Inlets are opened with ``recover=False``. A lost
  stream raises inside the inlet; the source emits an ``lsl_status``
  control item, the runner **aborts** the pending utterance (no
  decision on a cut input), and the source re-resolves the stream (by
  ``source_id`` if set) until ``reconnect_timeout_s``. After a
  reconnect it re-sends the header.
- Two inlets are merged by time with a watermark: an item is released
  when every other inlet has passed its time, or after
  ``merge_window_s`` of waiting.

Privacy: the host name of a stream is used only to group clock offsets.
It is never written to a header, a decision or a log line.
"""

from __future__ import annotations

import hashlib
import heapq
import itertools
import json
import math
import sys
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Protocol, Sequence, TextIO

import numpy as np

from fidetype.streams.spec import SPEC_VERSION, VOCAB_TYPES

ADAPTER_NAME = "fidetype.adapters.lsl"
ADAPTER_VERSION = "0.1"
#: LSL stream type of an NTS frames stream.
NTS_STREAM_TYPE = "NTS"
#: LSL stream type of the NTS events stream and of the decisions stream.
MARKERS_TYPE = "Markers"
DECISIONS_STREAM_NAME = "fidetype.decisions"
#: Name of the desc element that carries the Fidetype fields.
DESC_ROOT = "fidetype"
#: Control item of the source (never pushed into the trust layer).
LSL_STATUS = "lsl_status"
#: Extension event: a gap in the frames (spec 6.2 rule 5: consumers ignore it).
GAP = "gap"
#: A clamped timestamp is set this far after the previous one (seconds).
CLAMP_STEP_S = 1e-6

NUMERIC_FORMATS = ("float32", "double64", "int8", "int16", "int32", "int64")
ValuesKind = Literal["auto", "log_probs", "probs", "logits"]


class LSLUnavailableError(ImportError):
    """``pylsl`` (or its ``liblsl`` library) is not available."""


class LSLStreamLost(RuntimeError):
    """The LSL stream was lost (the sender stopped or the network broke)."""


class LSLResolveError(RuntimeError):
    """No LSL stream (or more than one) matched the query."""


_INSTALL_HINT = (
    "The LSL adapter needs pylsl (MIT licence). Install it with: pip install \"fidetype[lsl]\" "
    "(or: uv sync --extra lsl). The pylsl wheel for Windows includes liblsl. On other systems, "
    "if 'import pylsl' fails to find liblsl, install liblsl (see https://github.com/sccn/liblsl)."
)


def require_pylsl() -> Any:
    """Import and return ``pylsl``, or raise :class:`LSLUnavailableError`."""
    try:
        import pylsl  # noqa: PLC0415
    except (ImportError, OSError, RuntimeError) as e:
        raise LSLUnavailableError(f"{_INSTALL_HINT} (import error: {e})") from e
    return pylsl


def pylsl_available() -> bool:
    try:
        require_pylsl()
    except LSLUnavailableError:
        return False
    return True


# ---------------------------------------------------------------------------
# Stream info (our own plain model of the LSL stream info XML)
# ---------------------------------------------------------------------------


@dataclass
class LSLStreamInfo:
    """The fields of an LSL stream info that the adapter uses."""

    name: str
    type: str = ""
    channel_count: int = 1
    nominal_srate: float = 0.0
    channel_format: str = "float32"
    source_id: str = ""
    uid: str = ""
    #: Used only to group clock offsets. Never written to any output.
    hostname: str = ""
    created_at: float = 0.0
    channel_labels: list[str] = field(default_factory=list)
    channel_units: list[str] = field(default_factory=list)
    channel_types: list[str] = field(default_factory=list)
    #: Child values of the ``desc/fidetype`` element.
    fidetype: dict[str, str] = field(default_factory=dict)

    @property
    def is_string(self) -> bool:
        return self.channel_format == "string"

    @property
    def nts_header(self) -> dict[str, Any] | None:
        raw = self.fidetype.get("nts_header")
        if not raw:
            return None
        try:
            h = json.loads(raw)
        except ValueError as e:
            raise ValueError(f"desc/fidetype/nts_header of stream {self.name!r} is not JSON: {e}") from None
        if not isinstance(h, dict):
            raise ValueError(f"desc/fidetype/nts_header of stream {self.name!r} is not a JSON object")
        return h

    def summary(self) -> dict[str, Any]:
        """Identity fields for headers and provenance (no host name)."""
        return {"name": self.name, "type": self.type, "source_id": self.source_id, "uid": self.uid,
                "channel_count": self.channel_count, "nominal_srate": self.nominal_srate,
                "channel_format": self.channel_format}

    @classmethod
    def from_xml(cls, xml: str) -> "LSLStreamInfo":
        """Parse the XML of ``pylsl.StreamInfo.as_xml()``."""
        root = ET.fromstring(xml)

        def txt(tag: str, default: str = "") -> str:
            el = root.find(tag)
            return (el.text or "").strip() if el is not None and el.text is not None else default

        labels: list[str] = []
        units: list[str] = []
        types: list[str] = []
        desc = root.find("desc")
        fid: dict[str, str] = {}
        if desc is not None:
            chs = desc.find("channels")
            if chs is not None:
                for ch in chs.findall("channel"):
                    labels.append((ch.findtext("label") or "").strip())
                    units.append((ch.findtext("unit") or "").strip())
                    types.append((ch.findtext("type") or "").strip())
            f = desc.find(DESC_ROOT)
            if f is not None:
                for c in f:
                    fid[c.tag] = c.text or ""
        try:
            srate = float(txt("nominal_srate", "0") or 0)
        except ValueError:
            srate = 0.0
        try:
            created = float(txt("created_at", "0") or 0)
        except ValueError:
            created = 0.0
        return cls(name=txt("name"), type=txt("type"), channel_count=int(txt("channel_count", "1") or 1),
                   nominal_srate=srate, channel_format=txt("channel_format", "float32"),
                   source_id=txt("source_id"), uid=txt("uid"), hostname=txt("hostname"), created_at=created,
                   channel_labels=labels, channel_units=units, channel_types=types, fidetype=fid)


# ---------------------------------------------------------------------------
# Inlet protocol (pylsl wrapper and test fakes implement it)
# ---------------------------------------------------------------------------


class InletLike(Protocol):
    def info(self) -> LSLStreamInfo: ...

    def pull_chunk(self, timeout: float, max_samples: int) -> tuple[list[list[Any]], list[float]]:
        """Return (samples, timestamps). Raise :class:`LSLStreamLost` if the stream is lost."""
        ...

    def time_correction(self, timeout: float) -> float: ...

    def close(self) -> None: ...


class SignalDecoder(Protocol):
    """Turns raw signal samples (EEG, EMG, ...) into NTS frames.

    ``header``: the NTS header fields of the frames it emits (``vocab``,
    ``vocab_type``, ``blank_id``, optional ``source``, ``frame_period``,
    ``latency``, ``meta``). ``process(samples [n, C], times [n])`` returns
    a list of ``(t, log_probs)`` with t strictly increasing over calls.
    """

    header: dict[str, Any]

    def process(self, samples: np.ndarray, times: np.ndarray) -> list[tuple[float, np.ndarray]]: ...


class PylslInlet:
    """:class:`InletLike` over a ``pylsl.StreamInlet`` (``recover=False``)."""

    def __init__(self, stream_info: Any, open_timeout: float = 5.0, max_buflen: int = 360) -> None:
        pl = require_pylsl()
        self._pl = pl
        self._inlet = pl.StreamInlet(stream_info, max_buflen=max_buflen, recover=False, processing_flags=0)
        try:
            full = self._inlet.info(open_timeout)
            self._info = LSLStreamInfo.from_xml(full.as_xml())
            self._inlet.open_stream(open_timeout)
        except pl.util.LostError as e:
            raise LSLStreamLost(str(e)) from e

    def info(self) -> LSLStreamInfo:
        return self._info

    def pull_chunk(self, timeout: float, max_samples: int) -> tuple[list[list[Any]], list[float]]:
        try:
            s, ts = self._inlet.pull_chunk(timeout=timeout, max_samples=max_samples)
        except self._pl.util.LostError as e:
            raise LSLStreamLost(str(e)) from e
        return s, ts

    def time_correction(self, timeout: float) -> float:
        try:
            return float(self._inlet.time_correction(timeout))
        except self._pl.util.LostError as e:
            raise LSLStreamLost(str(e)) from e

    def close(self) -> None:
        try:
            self._inlet.close_stream()
        except Exception:  # noqa: BLE001 - best effort at shutdown
            pass


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


def _q(v: str) -> str:
    if "'" in v:
        raise ValueError(f"LSL query values must not contain a single quote: {v!r}")
    return f"'{v}'"


def lsl_predicate(name: str | None = None, type: str | None = None, source_id: str | None = None) -> str:
    """The XPath predicate for ``pylsl.resolve_bypred``."""
    parts = [f"{k}={_q(v)}" for k, v in (("name", name), ("type", type), ("source_id", source_id)) if v]
    if not parts:
        raise ValueError("give at least one of name, type, source_id")
    return " and ".join(parts)


def resolve(name: str | None = None, type: str | None = None, source_id: str | None = None,
            timeout: float = 10.0) -> Any:
    """Resolve exactly one LSL stream. Return its ``pylsl.StreamInfo``."""
    pl = require_pylsl()
    pred = lsl_predicate(name, type, source_id)
    found = pl.resolve_bypred(pred, 1, timeout)
    uniq: dict[str, Any] = {}
    for inf in found:
        uniq.setdefault(inf.uid(), inf)
    if not uniq:
        raise LSLResolveError(f"no LSL stream matches [{pred}] within {timeout} s")
    if len(uniq) > 1:
        ids = sorted(f"{i.name()} / {i.source_id()}" for i in uniq.values())
        raise LSLResolveError(f"{len(uniq)} LSL streams match [{pred}]: {ids}. Add --source-id.")
    return next(iter(uniq.values()))


def list_streams(wait_time: float = 2.0) -> list[LSLStreamInfo]:
    """All visible LSL streams (short info, no desc)."""
    pl = require_pylsl()
    return [LSLStreamInfo.from_xml(i.as_xml()) for i in pl.resolve_streams(wait_time)]


# ---------------------------------------------------------------------------
# Mapping settings and header
# ---------------------------------------------------------------------------


@dataclass
class LSLMapping:
    """How LSL samples become NTS events (module docstring)."""

    #: Meaning of numeric channel values ("auto": desc/fidetype/values, else log_probs).
    values: ValuesKind = "auto"
    #: Vocab of a foreign numeric stream (default: the channel labels).
    vocab: Sequence[str] | None = None
    #: vocab_type of a foreign stream (default "other").
    vocab_type: str | None = None
    #: CTC blank of a foreign stream: an index or a token label (None: no blank).
    blank: int | str | None = None
    source: str | None = None
    clock: Literal["receiver", "sender"] = "receiver"
    clock_refresh_s: float = 5.0
    time_correction_timeout_s: float = 2.0
    out_of_order: Literal["clamp", "drop", "error"] = "clamp"
    clamp_tolerance_s: float = 0.005
    gap_factor: float = 2.5
    on_gap: Literal["mark", "segment", "abort"] = "mark"
    boundary_markers: tuple[str, ...] = ("segment_end",)
    plain_markers: Literal["ignore", "hypothesis"] = "ignore"
    merge_window_s: float = 0.05
    max_chunk: int = 1024
    reconnect_timeout_s: float = 30.0
    reconnect_interval_s: float = 0.5

    def __post_init__(self) -> None:
        if self.values not in ("auto", "log_probs", "probs", "logits"):
            raise ValueError(f"unknown values kind {self.values!r}")
        if self.clock not in ("receiver", "sender"):
            raise ValueError(f"unknown clock {self.clock!r}")
        if self.out_of_order not in ("clamp", "drop", "error"):
            raise ValueError(f"unknown out_of_order {self.out_of_order!r}")
        if self.on_gap not in ("mark", "segment", "abort"):
            raise ValueError(f"unknown on_gap {self.on_gap!r}")
        if self.plain_markers not in ("ignore", "hypothesis"):
            raise ValueError(f"unknown plain_markers {self.plain_markers!r}")
        if self.vocab_type is not None and self.vocab_type not in VOCAB_TYPES:
            raise ValueError(f"vocab_type must be one of {VOCAB_TYPES}")
        if self.gap_factor <= 1 or self.merge_window_s < 0 or self.clamp_tolerance_s < 0:
            raise ValueError("gap_factor must be > 1; merge_window_s and clamp_tolerance_s >= 0")


def _resolve_blank(blank: int | str | None, vocab: Sequence[str]) -> int | None:
    if blank is None:
        return None
    if isinstance(blank, str) and not blank.lstrip("-").isdigit():
        if blank not in vocab:
            raise ValueError(f"blank token {blank!r} is not in the vocab")
        return list(vocab).index(blank)
    b = int(blank)
    if not 0 <= b < len(vocab):
        raise ValueError(f"blank index {b} is outside 0..{len(vocab) - 1}")
    return b


def build_header(info: LSLStreamInfo, mapping: LSLMapping, signal_decoder: SignalDecoder | None = None,
                 lsl_extra: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    """The NTS header event for a stream, and the values kind of its channels.

    NTS-native streams (``desc/fidetype/nts_header``) keep their header;
    only ``clock_domain`` becomes ``"lsl"``. Other streams get a header
    from the mapping and the channel labels, with ``adapter.*`` and
    ``data.derived`` in ``meta``. LSL facts go in the extension header
    key ``lsl`` (v0.1 consumers ignore unknown keys).
    """
    values = mapping.values
    if signal_decoder is not None:
        h = {k: v for k, v in dict(signal_decoder.header).items() if k != "type"}
        meta = dict(h.get("meta") or {})
        meta.setdefault("device.channel_count", info.channel_count)
        meta.setdefault("adapter.name", ADAPTER_NAME)
        meta.setdefault("adapter.version", ADAPTER_VERSION)
        meta.setdefault("data.derived", True)
        h["meta"] = meta
        values = "log_probs"
    else:
        native = info.nts_header
        if native is not None:
            h = {k: v for k, v in native.items() if k != "type"}
            if values == "auto":
                values = info.fidetype.get("values", "log_probs")  # type: ignore[assignment]
        else:
            if info.is_string:
                vocab = list(mapping.vocab or [])
            else:
                vocab = list(mapping.vocab) if mapping.vocab is not None else list(info.channel_labels)
                if not vocab or any(not v for v in vocab):
                    raise ValueError(f"stream {info.name!r} has no channel labels; pass the vocab")
            meta = {"adapter.name": ADAPTER_NAME, "adapter.version": ADAPTER_VERSION, "data.derived": True}
            h = {"spec_version": SPEC_VERSION, "vocab": vocab, "vocab_type": mapping.vocab_type or "other",
                 "blank_id": _resolve_blank(mapping.blank, vocab), "source": mapping.source or f"lsl:{info.name}",
                 "meta": meta}
            if info.nominal_srate > 0:
                h["frame_period"] = 1.0 / info.nominal_srate
        if values == "auto":
            values = "log_probs"
        if not info.is_string and len(h.get("vocab", [])) != info.channel_count:
            raise ValueError(f"stream {info.name!r} has {info.channel_count} channels but the vocab has "
                             f"{len(h.get('vocab', []))} tokens")
        if not info.is_string and info.channel_format not in NUMERIC_FORMATS:
            raise ValueError(f"channel format {info.channel_format!r} cannot carry frames")
    if values not in ("log_probs", "probs", "logits"):
        raise ValueError(f"unknown values kind {values!r}")
    if mapping.source and "source" not in h:
        h["source"] = mapping.source
    h.setdefault("spec_version", SPEC_VERSION)
    h["clock_domain"] = "lsl"
    lsl = {"stream": info.summary(), "clock": mapping.clock, "values": values,
           "adapter": {"name": ADAPTER_NAME, "version": ADAPTER_VERSION}}
    lsl.update(lsl_extra or {})
    h["lsl"] = lsl
    return {"type": "header", **h}, values


def to_log_probs(chunk: np.ndarray, values: str) -> np.ndarray:
    """Convert a [n, V] chunk of channel values to natural-log probabilities."""
    x = np.asarray(chunk, dtype=np.float64)
    if values == "log_probs":
        return x
    if values == "probs":
        if (x < 0).any():
            raise ValueError("probability channels must be >= 0")
        with np.errstate(divide="ignore"):
            return np.log(x)
    if values == "logits":
        m = np.max(x, axis=1, keepdims=True)
        return x - (m + np.log(np.exp(x - m).sum(axis=1, keepdims=True)))
    raise ValueError(f"unknown values kind {values!r}")


# ---------------------------------------------------------------------------
# Clock synchronisation
# ---------------------------------------------------------------------------


@dataclass
class _Offset:
    value: float = 0.0
    n: int = 0
    failures: int = 0
    min: float = math.inf
    max: float = -math.inf
    updated_at: float = -math.inf


class ClockSync:
    """Per-sender-host LSL clock offsets (``inlet.time_correction()``)."""

    def __init__(self, mode: str, refresh_s: float, timeout_s: float, clock: Callable[[], float]) -> None:
        self.mode = mode
        self.refresh_s = refresh_s
        self.timeout_s = timeout_s
        self.clock = clock
        self._by_host: dict[str, _Offset] = {}

    def offset(self, host: str, inlet: InletLike, force: bool = False) -> float:
        if self.mode == "sender":
            return 0.0
        o = self._by_host.setdefault(host, _Offset())
        now = self.clock()
        if force or o.n == 0 or now - o.updated_at >= self.refresh_s:
            try:
                v = float(inlet.time_correction(self.timeout_s))
                if math.isfinite(v):
                    o.value, o.n, o.updated_at = v, o.n + 1, now
                    o.min, o.max = min(o.min, v), max(o.max, v)
                else:
                    o.failures += 1
            except LSLStreamLost:
                raise
            except Exception:  # noqa: BLE001 - a timeout keeps the old offset
                o.failures += 1
                o.updated_at = now
        return o.value

    def record(self, host: str) -> dict[str, Any]:
        if self.mode == "sender":
            return {"clock": "sender", "time_correction_s": None, "updates": 0}
        o = self._by_host.get(host, _Offset())
        return {"clock": "receiver", "time_correction_s": o.value if o.n else None, "updates": o.n,
                "failures": o.failures,
                "spread_s": (o.max - o.min) if o.n else None}


# ---------------------------------------------------------------------------
# Readers and the event source
# ---------------------------------------------------------------------------


@dataclass
class SourceStats:
    samples: int = 0
    frames: int = 0
    markers: int = 0
    ignored_markers: int = 0
    bad_markers: int = 0
    clamped: int = 0
    dropped_out_of_order: int = 0
    gaps: int = 0
    lost: int = 0
    reconnects: int = 0
    late_releases: int = 0
    #: receive time - corrected LSL timestamp, seconds (bounded sample of the latest values).
    transport_latency_s: list[float] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "transport_latency_s"}
        tl = np.asarray(self.transport_latency_s, dtype=np.float64)
        if tl.size:
            d["transport_latency_ms"] = {"n": int(tl.size), "p50": float(np.percentile(tl, 50) * 1e3),
                                         "p95": float(np.percentile(tl, 95) * 1e3), "max": float(tl.max() * 1e3)}
        return d


class _Reader:
    """One inlet: pulls chunks, fixes order, finds gaps, makes items."""

    def __init__(self, role: str, inlet: InletLike, src: "LSLEventSource",
                 reopen: Callable[[], InletLike] | None) -> None:
        self.role = role  # "frames" | "events" | "signal"
        self.src = src
        self.reopen = reopen
        self.lost_since: float | None = None
        self._attach(inlet)

    def _attach(self, inlet: InletLike) -> None:
        self.inlet = inlet
        self.info = inlet.info()
        self.host = self.info.hostname or self.info.source_id or self.info.name
        self.last_t = -math.inf  # last accepted (corrected) sample time
        self.seen_t = -math.inf  # watermark: newest time seen
        self.period: float | None = None
        self.json_frames_last_t = -math.inf
        #: Counts carried on the next frame event (``lsl_clamped`` / ``lsl_dropped_before``).
        self.clamped_pending = 0
        self.dropped_pending = 0

    def set_period(self, header: dict[str, Any]) -> None:
        fp = header.get("frame_period") if self.role == "frames" else None
        if self.role == "signal" and self.info.nominal_srate > 0:
            fp = 1.0 / self.info.nominal_srate
        if fp is None and self.info.nominal_srate > 0 and self.role == "frames":
            fp = 1.0 / self.info.nominal_srate
        self.period = float(fp) if fp else None

    def _order(self, t: float, last: float) -> float | None:
        """Return the accepted time (maybe clamped) or None (drop)."""
        m = self.src.mapping
        if t > last:
            return t
        st = self.src.stats
        if m.out_of_order == "error":
            raise ValueError(f"LSL timestamp {t} does not increase (last {last}) on stream {self.info.name!r}")
        if m.out_of_order == "clamp" and last - t <= m.clamp_tolerance_s:
            st.clamped += 1
            self.clamped_pending += 1
            return last + CLAMP_STEP_S
        st.dropped_out_of_order += 1
        self.dropped_pending += 1
        return None

    def pull(self, timeout: float) -> list[tuple[float, int, dict[str, Any]]]:
        src = self.src
        samples, stamps = self.inlet.pull_chunk(timeout, src.mapping.max_chunk)
        if not stamps:
            return []
        off = src.clock_sync.offset(self.host, self.inlet)
        now = src.clock()
        src.stats.samples += len(stamps)
        items: list[tuple[float, int, dict[str, Any]]] = []
        if self.role == "events":
            for s, ts in zip(samples, stamps):
                t = float(ts) + off
                self._note_latency(now, t)
                ev = src.marker_event(s[0] if isinstance(s, (list, tuple)) else s, t)
                if ev is None:
                    continue
                if ev.get("type") == "frame":
                    tt = self._order(t, self.json_frames_last_t)
                    if tt is None:
                        continue
                    self.json_frames_last_t = tt
                    ev = {**ev, "t_source": ev.get("t"), "t": tt}
                items.append((t, next(src.seq), ev))
            if stamps:
                self.seen_t = max(self.seen_t, float(stamps[-1]) + off)
            return items
        arr = np.asarray(samples, dtype=np.float64)
        if arr.ndim == 1:
            arr = arr.reshape(len(stamps), -1)
        keep_rows: list[int] = []
        keep_t: list[float] = []
        for i, ts in enumerate(stamps):
            t = float(ts) + off
            self._note_latency(now, t)
            tt = self._order(t, self.last_t)
            if tt is None:
                continue
            if self.period is not None and math.isfinite(self.last_t) and tt - self.last_t > src.mapping.gap_factor * self.period:
                items += self._gap(self.last_t, tt, keep_rows, keep_t, arr)
                keep_rows, keep_t = [], []
            keep_rows.append(i)
            keep_t.append(tt)
            self.last_t = tt
        items += self._frames(arr, keep_rows, keep_t)
        self.seen_t = max(self.seen_t, self.last_t)
        return items

    def _note_latency(self, now: float, t: float) -> None:
        tl = self.src.stats.transport_latency_s
        tl.append(now - t)
        if len(tl) > 100_000:
            del tl[: len(tl) - 50_000]

    def _frames(self, arr: np.ndarray, rows: list[int], times: list[float]) -> list[tuple[float, int, dict[str, Any]]]:
        if not rows:
            return []
        src = self.src
        chunk = arr[rows]
        if self.role == "signal":
            assert src.signal_decoder is not None
            out = src.signal_decoder.process(chunk, np.asarray(times))
            pairs = [(float(t), np.asarray(r, dtype=np.float64)) for t, r in out]
        else:
            lp = to_log_probs(chunk, src.values)
            pairs = list(zip(times, lp))
        items = []
        for t, row in pairs:
            src.stats.frames += 1
            ev: dict[str, Any] = {"type": "frame", "t": t, "log_probs": row.tolist()}
            if self.clamped_pending:
                ev["lsl_clamped"] = self.clamped_pending
                self.clamped_pending = 0
            if self.dropped_pending:
                ev["lsl_dropped_before"] = self.dropped_pending
                self.dropped_pending = 0
            items.append((t, next(src.seq), ev))
        return items

    def _gap(self, t0: float, t1: float, rows: list[int], times: list[float], arr: np.ndarray) -> list:
        src = self.src
        src.stats.gaps += 1
        items = self._frames(arr, rows, times)  # frames before the gap first
        missing = int(round((t1 - t0) / self.period)) - 1 if self.period else None
        info = {"t_start": t0, "t_end": t1, "missing_frames": missing, "stream": self.info.name}
        mode = src.mapping.on_gap
        tg = t1 - 1e-9  # just before the first frame after the gap
        if mode == "mark":
            items.append((tg, next(src.seq), {"type": GAP, **info}))
        elif mode == "segment":
            items.append((tg, next(src.seq), {"type": "segment_end", "lsl_t": tg, "reason": "gap", **info}))
        else:
            items.append((tg, next(src.seq), {"type": LSL_STATUS, "status": "gap_abort", **info}))
        return items


class LSLEventSource:
    """LSL inlets -> NTS events (module docstring).

    ``primary``: the frames stream (numeric), a raw signal stream (with
    ``signal_decoder``) or a marker stream (hypothesis-only producers).
    ``events``: an optional marker stream (JSON NTS events or plain
    markers). ``reopen_*``: callables that open the stream again after a
    loss (they may raise; the source retries until
    ``mapping.reconnect_timeout_s``).
    """

    def __init__(
        self,
        primary: InletLike,
        events: InletLike | None = None,
        mapping: LSLMapping | None = None,
        signal_decoder: SignalDecoder | None = None,
        reopen_primary: Callable[[], InletLike] | None = None,
        reopen_events: Callable[[], InletLike] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.mapping = mapping or LSLMapping()
        self.signal_decoder = signal_decoder
        if clock is None:
            clock = require_pylsl().local_clock if pylsl_available() else time.perf_counter
        self.clock = clock
        self.clock_sync = ClockSync(self.mapping.clock, self.mapping.clock_refresh_s,
                                    self.mapping.time_correction_timeout_s, clock)
        self.stats = SourceStats()
        self.seq = itertools.count()
        pi = primary.info()
        role = "events" if pi.is_string else ("signal" if signal_decoder is not None else "frames")
        self.readers = [_Reader(role, primary, self, reopen_primary)]
        if events is not None:
            if not events.info().is_string:
                raise ValueError("the events stream must have the string channel format")
            self.readers.append(_Reader("events", events, self, reopen_events))
        self._heap: list[tuple[float, int, float, dict[str, Any]]] = []
        self._last_released = -math.inf
        self._header: dict[str, Any] | None = None
        self.values = "log_probs"
        self._pending_header = True
        self.n_marker = 0
        self.ended = False

    # --- header -------------------------------------------------------------

    @property
    def primary(self) -> _Reader:
        return self.readers[0]

    def header(self) -> dict[str, Any]:
        """The header event of the primary stream (computed on first use)."""
        if self._header is None:
            r = self.primary
            off = self.clock_sync.offset(r.host, r.inlet, force=True)
            extra = {"time_correction_s": off if self.mapping.clock == "receiver" else None}
            if len(self.readers) > 1:
                extra["events_stream"] = self.readers[1].info.summary()
            h, values = build_header(r.info, self.mapping, self.signal_decoder, extra)
            self._header, self.values = h, values
            for rd in self.readers:
                rd.set_period(h)
        return self._header

    def provenance(self) -> dict[str, Any]:
        """The ``lsl`` provenance record (stream ids and the current clock state)."""
        r = self.primary
        rec: dict[str, Any] = {"streams": [rd.info.summary() for rd in self.readers]}
        rec.update(self.clock_sync.record(r.host))
        rec["reconnects"] = self.stats.reconnects
        return rec

    # --- markers ------------------------------------------------------------

    def marker_event(self, s: Any, t: float) -> dict[str, Any] | None:
        """One marker sample -> one NTS event (or None: ignored)."""
        self.stats.markers += 1
        m = self.mapping
        if not isinstance(s, str):
            s = str(s)
        txt = s.strip()
        if txt.startswith("{"):
            try:
                ev = json.loads(txt)
            except ValueError:
                ev = None
            if isinstance(ev, dict) and isinstance(ev.get("type"), str):
                ev["lsl_t"] = t
                if ev["type"] == "header":
                    ev.setdefault("spec_version", SPEC_VERSION)
                    ev["clock_domain"] = "lsl"
                return ev
            self.stats.bad_markers += 1
            return None
        if txt in m.boundary_markers:
            return {"type": "segment_end", "lsl_t": t, "marker": txt}
        if m.plain_markers == "hypothesis" and txt:
            self.n_marker += 1
            return {"type": "hypothesis", "id": f"lsl-{self.n_marker}", "is_final": True, "score_semantics": "none",
                    "nbest": [{"text": txt, "score": 0.0}], "lsl_t": t}
        self.stats.ignored_markers += 1
        return None

    # --- polling ------------------------------------------------------------

    def poll(self, timeout: float = 0.05) -> list[dict[str, Any]]:
        """Pull what the inlets have (wait up to ``timeout``) and return released events."""
        out: list[dict[str, Any]] = []
        if self._pending_header:
            out.append(dict(self.header()))
            self._pending_header = False
        now = self.clock()
        for i, r in enumerate(self.readers):
            if r.lost_since is not None:
                out += self._try_reconnect(r, now)
                continue
            try:
                items = r.pull(timeout if i == 0 else 0.0)
            except LSLStreamLost as e:
                out += self._lost(r, str(e), now)
                continue
            arrival = self.clock()
            for t, sq, ev in items:
                heapq.heappush(self._heap, (t, sq, arrival, ev))
        out += self._release(self.clock())
        for ev in out:
            if ev.get("type") == "end":
                self.ended = True
        return out

    def drain(self) -> list[dict[str, Any]]:
        """Release all held items (at shutdown)."""
        return self._release(math.inf, force=True)

    def _release(self, now: float, force: bool = False) -> list[dict[str, Any]]:
        out = []
        while self._heap:
            t, sq, arrival, ev = self._heap[0]
            others = [rd.seen_t for rd in self.readers if rd.lost_since is None]
            ok = force or len(self.readers) == 1 or all(x >= t for x in others) or now - arrival >= self.mapping.merge_window_s
            if not ok:
                break
            heapq.heappop(self._heap)
            if t < self._last_released:
                self.stats.late_releases += 1
            self._last_released = max(self._last_released, t)
            out.append(ev)
        return out

    def _lost(self, r: _Reader, why: str, now: float) -> list[dict[str, Any]]:
        self.stats.lost += 1
        r.lost_since = now
        held = self._release(math.inf, force=True)  # what arrived before the loss keeps its order
        return held + [{"type": LSL_STATUS, "status": "lost", "stream": r.info.name, "detail": why}]

    def _try_reconnect(self, r: _Reader, now: float) -> list[dict[str, Any]]:
        assert r.lost_since is not None
        if r.reopen is None or now - r.lost_since > self.mapping.reconnect_timeout_s:
            raise LSLStreamLost(f"stream {r.info.name!r} lost and not reconnected"
                                + ("" if r.reopen is None else f" within {self.mapping.reconnect_timeout_s} s"))
        try:
            inlet = r.reopen()
        except Exception:  # noqa: BLE001 - try again on the next poll
            time.sleep(min(self.mapping.reconnect_interval_s, 0.05))
            return []
        r._attach(inlet)
        r.lost_since = None
        self.stats.reconnects += 1
        out = [{"type": LSL_STATUS, "status": "reconnected", "stream": r.info.name}]
        if r is self.primary:
            self._header = None
            out.append(dict(self.header()))  # a new header resets the session's stream state
        else:
            r.set_period(self.header())
        return out

    def close(self) -> None:
        for r in self.readers:
            r.inlet.close()


# ---------------------------------------------------------------------------
# Runner: source -> StreamingTrustLayer -> decisions
# ---------------------------------------------------------------------------


@dataclass
class RunSummary:
    decisions: int = 0
    final_decisions: int = 0
    events: int = 0
    rejected_events: int = 0
    aborted_utterances: int = 0
    idle_flushes: int = 0
    ended: bool = False
    wall_s: float = 0.0
    source: dict[str, Any] = field(default_factory=dict)
    e2e_latency_ms: dict[str, float] = field(default_factory=dict)
    stop_reason: str = ""


class LSLTrustRunner:
    """Feed an :class:`LSLEventSource` into a :class:`~fidetype.trust.streaming.StreamingTrustLayer`.

    Each decision becomes a ``trust_decision`` event (FEP-0001) with an
    extra ``lsl`` record (stream ids, clock offset, utterance counts,
    ``e2e_latency_s`` = emission time - LSL time of the triggering event).
    ``sink`` gets each event as a dict; ``outlet`` (a
    :class:`DecisionOutlet`) publishes it on LSL.
    """

    def __init__(self, layer: Any, source: LSLEventSource, session_id: str = "lsl",
                 sink: Callable[[dict[str, Any]], None] | None = None, outlet: "DecisionOutlet | None" = None,
                 include_text: bool = True, on_bad_event: Literal["skip", "raise"] = "skip", keep: bool = False,
                 log: Callable[[str], None] | None = None) -> None:
        self.layer = layer
        self.source = source
        self.session_id = session_id
        self.sink = sink
        self.outlet = outlet
        self.include_text = include_text
        self.on_bad_event = on_bad_event
        self.keep = keep
        self.kept: list[Any] = []
        self.log = log or (lambda msg: None)
        self.summary = RunSummary()
        self._lat: list[float] = []
        self._last_event_at = source.clock()
        self.utt: dict[str, int] = {}
        self._reset_utt()

    def _reset_utt(self) -> None:
        """Counts of the current utterance (from the released events, so they match the decision)."""
        self.utt = {"frames": 0, "gaps": 0, "clamped": 0, "dropped_out_of_order": 0}

    def _pending(self) -> bool:
        try:
            st = self.layer.session_state(self.session_id)
        except KeyError:
            return False
        return bool(st["buffered_frames"] or st["has_hypothesis"])

    def _abort(self, why: str) -> None:
        if self._pending():
            self.summary.aborted_utterances += 1
            self.log(f"abort utterance: {why}")
        self.layer.abort_utterance(self.session_id)
        self._reset_utt()

    def step(self, timeout: float = 0.05, idle_flush_s: float | None = None) -> list[Any]:
        """One poll. Return the decisions it caused."""
        evs = self.source.poll(timeout)
        out = self._handle(evs)
        now = self.source.clock()
        if idle_flush_s is not None and not evs and now - self._last_event_at >= idle_flush_s and self._pending():
            self.summary.idle_flushes += 1
            for d in self.layer.end_of_utterance(self.session_id):
                out.append(self._emit(d, None))
        return out

    def finish(self) -> list[Any]:
        """Release and handle the items that the merge still holds (at shutdown)."""
        return self._handle(self.source.drain())

    def _handle(self, evs: list[dict[str, Any]]) -> list[Any]:
        from fidetype.trust.streaming import StreamEventError

        out: list[Any] = []
        now = self.source.clock()
        for ev in evs:
            typ = ev.get("type")
            self._last_event_at = now
            if typ == LSL_STATUS:
                self.log(f"lsl {ev.get('status')}: {ev.get('stream')} {ev.get('detail', '')}".rstrip())
                if ev.get("status") in ("lost", "gap_abort"):
                    self._abort(str(ev.get("status")))
                continue
            if typ == GAP:
                self.utt["gaps"] += 1
                continue  # a v0.1 consumer ignores it
            if typ == "frame":
                self.utt["frames"] += 1
                self.utt["clamped"] += int(ev.get("lsl_clamped", 0))
                self.utt["dropped_out_of_order"] += int(ev.get("lsl_dropped_before", 0))
            self.summary.events += 1
            try:
                ds = self.layer.push(ev, self.session_id)
            except StreamEventError as e:
                self.summary.rejected_events += 1
                self.log(f"rejected {typ} event: {e}")
                if self.on_bad_event == "raise":
                    raise
                continue
            for d in ds:
                out.append(self._emit(d, ev))
            if typ == "end":
                self.summary.ended = True
        return out

    def _emit(self, d: Any, trigger: dict[str, Any] | None) -> Any:
        rec = self.source.provenance()
        rec["utterance"] = dict(self.utt)
        if trigger is not None:
            tt = trigger.get("lsl_t", trigger.get("t") if trigger.get("type") == "frame" else None)
            if isinstance(tt, (int, float)) and self.source.mapping.clock == "receiver":
                lat = self.source.clock() - float(tt)
                rec["t_trigger"] = float(tt)
                rec["e2e_latency_s"] = lat
                if d.final:
                    self._lat.append(lat)
        d.provenance["lsl"] = rec
        ev = d.to_event(include_text=self.include_text)
        ev["lsl"] = rec
        if self.sink is not None:
            self.sink(ev)
        if self.outlet is not None:
            self.outlet.push(ev)
        self.summary.decisions += 1
        if d.final:
            self.summary.final_decisions += 1
            self._reset_utt()
        if self.keep:
            self.kept.append(d)
        return d

    def run(self, duration_s: float | None = None, max_decisions: int | None = None, until_end: bool = True,
            idle_flush_s: float | None = None, poll_timeout: float = 0.05,
            stop: threading.Event | None = None) -> RunSummary:
        """Loop until ``end`` (``until_end``), the duration, the decision count, or ``stop``."""
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
                self.step(poll_timeout, idle_flush_s)
                if max_decisions is not None and self.summary.final_decisions >= max_decisions:
                    reason = "max_decisions"
                    break
                if until_end and self.summary.ended:
                    reason = "end"
                    break
        except KeyboardInterrupt:
            reason = "interrupted"
        if reason != "end":
            self.finish()
        if reason != "end" and not self.summary.ended:
            self._abort(f"run stopped ({reason}) inside an utterance")
        self.summary.stop_reason = reason
        self.summary.wall_s = time.monotonic() - t0
        self.summary.source = self.source.stats.as_dict()
        if self._lat:
            a = np.asarray(self._lat) * 1e3
            self.summary.e2e_latency_ms = {"n": int(a.size), "p50": float(np.percentile(a, 50)),
                                           "p95": float(np.percentile(a, 95)), "max": float(a.max())}
        return self.summary


# ---------------------------------------------------------------------------
# Outlets
# ---------------------------------------------------------------------------


class DecisionOutlet:
    """An LSL marker outlet that carries ``trust_decision`` events as JSON strings."""

    def __init__(self, name: str = DECISIONS_STREAM_NAME, source_id: str | None = None,
                 config_id: str | None = None) -> None:
        pl = require_pylsl()
        self._pl = pl
        sid = source_id or f"{name}.{config_id or 'default'}"
        info = pl.StreamInfo(name, MARKERS_TYPE, 1, pl.IRREGULAR_RATE, "string", sid)
        f = info.desc().append_child(DESC_ROOT)
        f.append_child_value("role", "trust_decisions")
        f.append_child_value("event_type", "trust_decision")
        f.append_child_value("spec", "FEP-0001")
        if config_id:
            f.append_child_value("config_id", config_id)
        self.outlet = pl.StreamOutlet(info)

    def push(self, event: dict[str, Any]) -> None:
        self.outlet.push_sample([json.dumps(event, ensure_ascii=False, allow_nan=False)], self._pl.local_clock())


def _stable_id(*parts: str) -> str:
    return "fidetype-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _event_list(source: str | PathLike[str] | Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    from fidetype.trust.streaming import iter_events, parse_event

    if isinstance(source, (str, PathLike)):
        return list(iter_events(source))
    return [parse_event(e) for e in source]


@dataclass
class ReplaySummary:
    frames: int = 0
    events: int = 0
    frames_source_id: str | None = None
    events_source_id: str | None = None
    t_first_lsl: float | None = None
    wall_s: float = 0.0
    consumers: bool = False


def replay_to_lsl(
    source: str | PathLike[str] | Iterable[dict[str, Any]],
    name: str = "fidetype.nts",
    source_id: str | None = None,
    speed: float = 1.0,
    channel_format: Literal["float32", "double64"] = "float32",
    wait_consumers_s: float = 10.0,
    linger_s: float = 1.0,
    lead_s: float = 0.1,
    stop: threading.Event | None = None,
    ready: threading.Event | None = None,
    log: Callable[[str], None] | None = None,
) -> ReplaySummary:
    """Publish a NeuralTextStream (file or events) as LSL streams (module docstring).

    Frames go to a numeric ``NTS`` stream ``name``, other events (except
    the first header) to a ``Markers`` stream ``name + ".events"``. A
    non-frame event gets the time of the previous frame plus a small
    step, so the merge at the inlet keeps the file order. ``speed`` 1.0 =
    real time, 2.0 = twice as fast, 0 = no pacing (timestamps still
    follow the file times). ``ready`` is set when the outlets exist.
    """
    pl = require_pylsl()
    log = log or (lambda m: None)
    evs = _event_list(source)
    if not evs or evs[0].get("type") != "header":
        raise ValueError("the stream must start with a header event")
    head = {k: v for k, v in evs[0].items() if k != "type"}
    V = len(head.get("vocab", []))
    has_frames = any(e.get("type") == "frame" for e in evs)
    others = [e for e in evs[1:] if e.get("type") != "frame"]
    for e in others:
        if e.get("type") == "header" and list(e.get("vocab", [])) != list(head.get("vocab", [])):
            raise ValueError("a later header changes the vocab; publish each stream separately")
    base_id = source_id or _stable_id(name, json.dumps(head, sort_keys=True))
    fid, eid = (base_id if has_frames else None), (base_id + ".events" if (others or not has_frames) else None)
    header_json = json.dumps(head, ensure_ascii=False, allow_nan=False)
    fp = head.get("frame_period")
    outlets = []
    frames_out = events_out = None
    if fid is not None:
        info = pl.StreamInfo(name, NTS_STREAM_TYPE, V, (1.0 / fp) if fp else pl.IRREGULAR_RATE, channel_format, fid)
        d = info.desc()
        chs = d.append_child("channels")
        for tok in head["vocab"]:
            c = chs.append_child("channel")
            c.append_child_value("label", tok)
            c.append_child_value("unit", "log_prob")
            c.append_child_value("type", "nts.log_prob")
        f = d.append_child(DESC_ROOT)
        f.append_child_value("nts_header", header_json)
        f.append_child_value("values", "log_probs")
        f.append_child_value("role", "nts_frames")
        if eid:
            f.append_child_value("events_source_id", eid)
        frames_out = pl.StreamOutlet(info, chunk_size=0, max_buffered=360)
        outlets.append(frames_out)
    if eid is not None:
        info = pl.StreamInfo(name + ".events" if fid else name, MARKERS_TYPE, 1, pl.IRREGULAR_RATE, "string", eid)
        f = info.desc().append_child(DESC_ROOT)
        f.append_child_value("nts_header", header_json)
        f.append_child_value("role", "nts_events")
        if fid:
            f.append_child_value("frames_source_id", fid)
        events_out = pl.StreamOutlet(info, chunk_size=0)
        outlets.append(events_out)
    if ready is not None:
        ready.set()
    rs = ReplaySummary(frames_source_id=fid, events_source_id=eid)
    t_wait = time.monotonic()
    rs.consumers = all(o.wait_for_consumers(max(0.0, wait_consumers_s - (time.monotonic() - t_wait))) for o in outlets)
    if not rs.consumers:
        log(f"no consumer after {wait_consumers_s} s; sending anyway")
    time.sleep(0.05)  # let the inlets finish their connection set-up
    t_file0 = next((float(e["t"]) for e in evs if e.get("type") == "frame"), 0.0)
    base = pl.local_clock() + lead_s
    rs.t_first_lsl = base
    eps = 1e-4 if not fp else min(1e-4, float(fp) / 10)
    last_ts = base - 1.0  # events before the first frame go well before it
    k = 0
    w0 = time.monotonic()
    for e in evs[1:]:
        if stop is not None and stop.is_set():
            break
        typ = e.get("type")
        if typ == "frame":
            dt = float(e["t"]) - t_file0
            ts = base + (dt / speed if speed > 0 else dt)
            k = 0
        else:
            k += 1
            ts = last_ts + eps * k
        if speed > 0:
            wait = ts - pl.local_clock()
            if wait > 0:
                time.sleep(wait)
        if typ == "frame":
            assert frames_out is not None
            row = [(-math.inf if v is None else float(v)) for v in e["log_probs"]]
            frames_out.push_sample(row, ts, True)
            rs.frames += 1
            last_ts = ts
        else:
            assert events_out is not None
            events_out.push_sample([json.dumps(e, ensure_ascii=False, allow_nan=False)], ts, True)
            rs.events += 1
    time.sleep(max(0.0, linger_s))
    rs.wall_s = time.monotonic() - w0
    del frames_out, events_out
    outlets.clear()
    return rs


# ---------------------------------------------------------------------------
# Opening a source from a query
# ---------------------------------------------------------------------------


def open_source(
    name: str | None = None,
    type: str | None = None,
    source_id: str | None = None,
    events: Literal["auto", "none"] | str = "auto",
    mapping: LSLMapping | None = None,
    signal_decoder: SignalDecoder | None = None,
    timeout: float = 10.0,
    log: Callable[[str], None] | None = None,
) -> LSLEventSource:
    """Resolve the primary stream (and its events stream) and build a source.

    ``events``: ``"auto"`` (the ``events_source_id`` from the primary's
    desc, if any), ``"none"``, or the name of a marker stream.
    """
    pl = require_pylsl()
    log = log or (lambda m: None)
    mapping = mapping or LSLMapping()
    pinfo = resolve(name, type, source_id, timeout)
    primary = PylslInlet(pinfo)
    pi = primary.info()
    log(f"connected: {pi.name} ({pi.type}, {pi.channel_count} ch, {pi.channel_format}, {pi.nominal_srate} Hz)")
    psid = pi.source_id

    def reopen_primary() -> InletLike:
        q = {"source_id": psid} if psid else {"name": pi.name, "type": pi.type or None}
        return PylslInlet(resolve(timeout=mapping.reconnect_interval_s, **q))

    ev_inlet = None
    reopen_events = None
    ev_query: dict[str, Any] | None = None
    if events == "auto":
        esid = pi.fidetype.get("events_source_id")
        if esid:
            ev_query = {"source_id": esid}
    elif events != "none":
        ev_query = {"name": events}
    if ev_query is not None:
        try:
            ev_inlet = PylslInlet(resolve(timeout=min(timeout, 5.0), **ev_query))
            log(f"connected events stream: {ev_inlet.info().name}")

            def reopen_events() -> InletLike:  # noqa: F811
                return PylslInlet(resolve(timeout=mapping.reconnect_interval_s, **ev_query))
        except LSLResolveError as e:
            if events != "auto":
                raise
            log(f"no events stream: {e}")
    return LSLEventSource(primary, ev_inlet, mapping, signal_decoder, reopen_primary, reopen_events, pl.local_clock)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _stderr(msg: str) -> None:
    sys.stderr.write(f"[fidetype.lsl] {msg}\n")
    sys.stderr.flush()


def _jsonl_sink(fh: TextIO) -> Callable[[dict[str, Any]], None]:
    def sink(ev: dict[str, Any]) -> None:
        fh.write(json.dumps(ev, ensure_ascii=False, allow_nan=False) + "\n")
        fh.flush()

    return sink


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m fidetype.adapters.lsl {run,replay-to-lsl,list}``"""
    import argparse

    ap = argparse.ArgumentParser(prog="python -m fidetype.adapters.lsl",
                                 description="Lab Streaming Layer input/output for Fidetype (M6-01).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="LSL stream -> streaming trust layer -> trust_decision JSON Lines on stdout")
    r.add_argument("--config", required=True, help="FrozenTrustConfig JSON file")
    r.add_argument("--stream-name")
    r.add_argument("--stream-type")
    r.add_argument("--source-id")
    r.add_argument("--events", default="auto", help='"auto" (from the desc), "none", or a marker stream name')
    r.add_argument("--decoder", choices=("none", "greedy", "demo"), default="none",
                   help="frame decoder: none (hypothesis route), greedy (CTC greedy, frames route) or demo "
                        "(the beam + LM decoder of fidetype.demo)")
    r.add_argument("--values", choices=("auto", "log_probs", "probs", "logits"), default="auto")
    r.add_argument("--vocab", help="comma-separated vocab of a foreign stream (default: channel labels)")
    r.add_argument("--vocab-type", choices=VOCAB_TYPES)
    r.add_argument("--blank", help="CTC blank of a foreign stream: index or token")
    r.add_argument("--clock", choices=("receiver", "sender"), default="receiver")
    r.add_argument("--on-gap", choices=("mark", "segment", "abort"), default="mark")
    r.add_argument("--out-of-order", choices=("clamp", "drop", "error"), default="clamp")
    r.add_argument("--boundary-marker", action="append", default=None,
                   help="plain marker string that ends an utterance (repeatable; default: segment_end)")
    r.add_argument("--plain-markers", choices=("ignore", "hypothesis"), default="ignore")
    r.add_argument("--merge-window", type=float, default=0.05, help="seconds to wait for the other inlet")
    r.add_argument("--idle-flush", type=float, default=None, help="end the utterance after this many idle seconds")
    r.add_argument("--resolve-timeout", type=float, default=10.0)
    r.add_argument("--duration", type=float, default=None, help="stop after this many seconds")
    r.add_argument("--max-decisions", type=int, default=None, help="stop after this many final decisions")
    r.add_argument("--no-until-end", action="store_true", help="keep running after an end event")
    r.add_argument("--session", default="lsl")
    r.add_argument("--outlet", action="store_true", help=f"also publish decisions on LSL ({DECISIONS_STREAM_NAME})")
    r.add_argument("--outlet-name", default=DECISIONS_STREAM_NAME)
    r.add_argument("--no-text", action="store_true", help="omit the shown texts from the output")
    r.add_argument("--max-attempts", type=int, default=2)
    r.add_argument("--summary", help="write the run summary JSON to this file")

    p = sub.add_parser("replay-to-lsl", help="publish a NeuralTextStream file as LSL streams")
    p.add_argument("file")
    p.add_argument("--name", default="fidetype.nts")
    p.add_argument("--source-id")
    p.add_argument("--speed", type=float, default=1.0, help="1 = real time, 0 = no pacing")
    p.add_argument("--channel-format", choices=("float32", "double64"), default="float32")
    p.add_argument("--wait-consumers", type=float, default=30.0)
    p.add_argument("--linger", type=float, default=1.0)
    p.add_argument("--loop", type=int, default=1, help="number of times to send the file")

    ls = sub.add_parser("list", help="list the visible LSL streams")
    ls.add_argument("--wait", type=float, default=2.0)

    a = ap.parse_args(argv)
    try:
        if a.cmd == "list":
            for inf in list_streams(a.wait):
                print(json.dumps(inf.summary()))
            return 0
        if a.cmd == "replay-to-lsl":
            for i in range(max(1, a.loop)):
                rs = replay_to_lsl(a.file, a.name, a.source_id, a.speed, a.channel_format, a.wait_consumers,
                                   a.linger, log=_stderr)
                _stderr(f"sent {rs.frames} frames and {rs.events} events in {rs.wall_s:.2f} s (pass {i + 1})")
            return 0
        return _run_cli(a)
    except LSLUnavailableError as e:
        _stderr(str(e))
        return 2
    except LSLResolveError as e:
        _stderr(str(e))
        return 3


def _run_cli(a: Any) -> int:
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    if not (a.stream_name or a.stream_type or a.source_id):
        _stderr("give --stream-name, --stream-type or --source-id")
        return 2
    blank: int | str | None = a.blank
    mapping = LSLMapping(values=a.values, vocab=a.vocab.split(",") if a.vocab else None, vocab_type=a.vocab_type,
                         blank=blank, clock=a.clock, on_gap=a.on_gap, out_of_order=a.out_of_order,
                         boundary_markers=tuple(a.boundary_marker or ("segment_end",)),
                         plain_markers=a.plain_markers, merge_window_s=a.merge_window)
    from fidetype.trust.streaming import frame_decoder

    dec = frame_decoder(a.decoder)
    cfg = FrozenTrustConfig.load(a.config)
    layer = StreamingTrustLayer(cfg, decode_fn=dec, streaming=StreamingConfig(max_attempts=a.max_attempts))
    src = open_source(a.stream_name, a.stream_type, a.source_id, a.events, mapping, timeout=a.resolve_timeout,
                      log=_stderr)
    outlet = DecisionOutlet(a.outlet_name, config_id=cfg.config_id) if a.outlet else None
    runner = LSLTrustRunner(layer, src, session_id=a.session, sink=_jsonl_sink(sys.stdout), outlet=outlet,
                            include_text=not a.no_text, log=_stderr)
    try:
        s = runner.run(duration_s=a.duration, max_decisions=a.max_decisions, until_end=not a.no_until_end,
                       idle_flush_s=a.idle_flush)
    except LSLStreamLost as e:
        _stderr(str(e))
        return 4
    finally:
        src.close()
    _stderr(f"stop ({s.stop_reason}): {s.final_decisions} final decisions, {s.events} events, "
            f"{s.rejected_events} rejected, {s.aborted_utterances} aborted")
    if a.summary:
        Path(a.summary).write_text(json.dumps(s.__dict__, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
