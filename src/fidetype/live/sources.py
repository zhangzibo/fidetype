"""Signal sources of ``fidetype live`` (P14-04): synthetic, BrainFlow, LSL.

Every source has ``info`` (a dict: ``name``, ``sample_rate``,
``channels``, ``modality``, ``meta``), ``start()``, ``poll(timeout)`` and
``close()``. ``poll`` returns a :class:`Chunk` (new samples, their times,
new markers) or ``None`` when the source has ended. Times are seconds on
one clock per source (the LSL clock for LSL and BrainFlow).

- :class:`SyntheticSource`: the synthetic typist of
  :mod:`fidetype.live.synthetic`, paced in real time (or as fast as
  possible with ``speed=0``). No optional package.
- :class:`BrainFlowSource`: a BrainFlow board (default: the Synthetic
  board, id -1; OpenBCI Cyton = 0, Ganglion = 1, ...). It reuses
  :class:`fidetype.adapters.brainflow_bridge.BrainFlowBridge` (board
  open, time stamps, ``segment_end`` trial clock) with in-memory outlets,
  so no LSL hop is needed. Needs the ``[brainflow]`` extra, unless a
  ``board`` object (for example :class:`~fidetype.adapters.brainflow_bridge.FakeBoard`) is given.
- :class:`LSLSource`: a raw-signal LSL stream and its markers stream. It
  reuses :func:`fidetype.adapters.lsl.resolve` and
  :class:`fidetype.adapters.lsl.PylslInlet`. Needs the ``[lsl]`` extra.
  Times are corrected to the receiver clock (``time_correction()``).
  **Reconnect (P4-11):** a lost stream is resolved again (same query:
  ``source_id`` if the stream has one, else name and type) with the
  reconnect code of :mod:`fidetype.adapters.lsl` (``_Reopener``,
  ``_Reconnector``, with backoff). The chunk at the loss has
  ``lost=True``; the first chunk after the reconnect (or after a time
  jump of more than ``gap_factor`` sample periods) carries ``gap``, the
  LSL-G3 fields of the discontinuity.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np

from fidetype.live.synthetic import KEYPRESS, SEGMENT_END, SyntheticTypist, Utterance

#: Catalogue metadata (P14-42): read by fidetype.adapters.registry -> docs/adapters.md.
ADAPTER_INFO = [
    {"id": "lsl-signal-source", "kind": "device-source", "signal": "any", "status": "tested", "extra": "lsl",
     "target": "Any raw-signal LSL stream and its marker stream (LSLSource of fidetype live; reconnect P4-11)",
     "licence": "Code Apache-2.0. pylsl is MIT.", "tests": ["tests/test_live_reconnect.py", "tests/test_live.py"],
     "docs": "docs/live-decode.md"},
    {"id": "synthetic-typist", "kind": "synthetic-source", "signal": "other", "status": "tested",
     "target": "Synthetic typist signal with key-press markers (SyntheticSource; no real data)",
     "licence": "Code Apache-2.0. Synthetic data, no licence needed.",
     "tests": ["tests/test_live.py", "tests/test_adapter_conformance.py"], "docs": "docs/live-decode.md"},
]

__all__ = ["Chunk", "SyntheticSource", "ArraySource", "BrainFlowSource", "LSLSource"]


@dataclass
class Chunk:
    samples: np.ndarray  # (n, C) float32
    times: np.ndarray  # (n,) float64 seconds
    markers: list[tuple[float, str]] = field(default_factory=list)
    #: True on the chunk at which the source lost its stream (no samples after this point until ``gap``).
    lost: bool = False
    #: A discontinuity before ``samples[0]`` (P4-11): the LSL-G3 fields ``t_start`` (last sample before),
    #: ``t_end`` (first sample after), ``missing_frames``, ``stream``, plus ``cause`` ("lost" or "timestamp").
    gap: dict[str, Any] | None = None


def _empty(c: int) -> Chunk:
    return Chunk(np.zeros((0, c), np.float32), np.zeros(0))


class ArraySource:
    """Replay a recorded signal (N, C) with marker strings, in real time (``speed`` 1) or faster (0: no pacing).

    ``t0`` is the time of sample 0. The synthetic source and the tests use it.
    """

    def __init__(self, signal: np.ndarray, sample_rate: float, markers: Sequence[tuple[float, str]] = (),
                 speed: float = 1.0, chunk_s: float = 0.02, t0: float = 0.0, name: str = "array",
                 modality: str = "other", meta: dict[str, Any] | None = None,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        self.x = np.asarray(signal, dtype=np.float32)
        self.fs = float(sample_rate)
        self.markers = deque(sorted(markers))
        self.speed = float(speed)
        self.step = max(1, int(round(chunk_s * self.fs)))
        self.t0 = float(t0)
        self.i = 0
        self.clock = clock
        self._wall0: float | None = None
        self.info = {"name": name, "sample_rate": self.fs, "channels": int(self.x.shape[1]), "modality": modality,
                     "meta": dict(meta or {})}

    def start(self) -> None:
        self._wall0 = self.clock()

    def poll(self, timeout: float = 0.05) -> Chunk | None:
        if self._wall0 is None:
            self.start()
        n = self.x.shape[0]
        if self.i >= n:
            return None
        if self.speed > 0:
            due = int((self.clock() - self._wall0) * self.speed * self.fs)  # type: ignore[operator]
            if due <= self.i:
                wait = (self.i + self.step - due) / (self.fs * self.speed)
                time.sleep(min(max(wait, 0.0), timeout))
                due = int((self.clock() - self._wall0) * self.speed * self.fs)  # type: ignore[operator]
            j = min(n, max(due, self.i))
        else:
            j = min(n, self.i + self.step)
        x = self.x[self.i:j]
        t = self.t0 + np.arange(self.i, j) / self.fs
        self.i = j
        t_hi = self.t0 + j / self.fs
        mk = []
        while self.markers and self.markers[0][0] < t_hi:
            mk.append(self.markers.popleft())
        if self.i >= n:  # flush the markers after the last sample
            mk += list(self.markers)
            self.markers.clear()
        return Chunk(x, t, mk)

    def close(self) -> None:
        pass


class SyntheticSource(ArraySource):
    """The synthetic typist (:mod:`fidetype.live.synthetic`) as a live source.

    ``utterances`` holds the truth (text per utterance) for tests and
    demos; it never goes into a stream or a decision.
    """

    def __init__(self, n_utterances: int = 10, seed: int = 0, sample_rate: float = 250.0, channels: int = 16,
                 speed: float = 1.0, chunk_s: float = 0.02, null: bool = False, noise: float = 11.0) -> None:
        typ = SyntheticTypist(sample_rate=sample_rate, channels=channels, seed=seed, noise=noise)
        self.utterances: list[Utterance] = list(typ.utterances(n_utterances))
        sig = typ.render(self.utterances, null=null)
        mk: list[tuple[float, str]] = []
        for u in self.utterances:
            mk += [(t, KEYPRESS) for t in u.key_times]
            mk.append((u.t_end, SEGMENT_END))
        meta = {"fidetype.synthetic": True, "device.model": "fidetype synthetic typist (no real data)"}
        super().__init__(sig, sample_rate, mk, speed, chunk_s, 0.0, "synthetic", "other", meta)


class _MemOutlet:
    """An in-memory stand-in for an LSL outlet (the bridge pushes into it)."""

    def __init__(self) -> None:
        self.chunks: deque[tuple[np.ndarray, list[float]]] = deque()
        self.samples: deque[tuple[list[Any], float]] = deque()

    def push_chunk(self, x: Any, timestamp: Any = 0.0, pushthrough: bool = True) -> None:
        self.chunks.append((np.asarray(x, dtype=np.float32), list(timestamp)))

    def push_sample(self, x: Any, timestamp: float = 0.0, pushthrough: bool = True) -> None:
        self.samples.append((list(x), float(timestamp)))


class BrainFlowSource:
    """A BrainFlow board read in-process through :class:`~fidetype.adapters.brainflow_bridge.BrainFlowBridge`.

    ``trial_s``: seconds between ``segment_end`` markers (the bridge's
    trial clock). ``board``/``descr``: give an open board object (tests);
    else the board is opened with :func:`~fidetype.adapters.brainflow_bridge.open_board`.
    """

    def __init__(self, board_id: int = -1, kind: str = "eeg", trial_s: float = 2.0, poll_s: float = 0.02,
                 serial_port: str = "", ip_address: str = "", ip_port: int = 0, mac_address: str = "",
                 serial_number: str = "", other: str = "", board: Any = None, descr: dict[str, Any] | None = None,
                 lsl_clock: Callable[[], float] | None = None, wall_clock: Callable[[], float] = time.time) -> None:
        from fidetype.adapters import brainflow_bridge as B

        if board is None:
            board, descr = B.open_board(board_id, serial_port, ip_address, ip_port, mac_address, serial_number, other)
        assert descr is not None
        self.sig, self.mk = _MemOutlet(), _MemOutlet()

        def outlets(sd: dict[str, Any], sid: str, esid: str) -> tuple[Any, Any]:
            return self.sig, self.mk

        cfg = B.BridgeConfig(name="fidetype.live.brainflow", kind=kind, trial_s=trial_s or None, poll_s=poll_s)
        clock = lsl_clock or time.perf_counter
        self.bridge = B.BrainFlowBridge(board, descr, board_id, cfg, outlets=outlets, lsl_clock=clock,
                                        wall_clock=wall_clock)
        self.poll_s = poll_s
        sd = self.bridge.sd
        self.info = {"name": f"brainflow:{descr.get('name', board_id)}", "sample_rate": float(sd["srate"]),
                     "channels": len(sd["rows"]), "modality": sd["fidetype"]["device.modality"],
                     "meta": {"brainflow.board_id": str(board_id), "brainflow.board_name": str(descr.get("name", "")),
                              "device.model": f"BrainFlow board {descr.get('name', board_id)}"}}
        self._started = False
        self._stopped = False

    def start(self) -> None:
        if not self._started:
            self.bridge.start()
            self._started = True

    def poll(self, timeout: float = 0.05) -> Chunk | None:
        if self._stopped:
            return None
        self.start()
        time.sleep(min(self.poll_s, timeout))
        self.bridge.step()
        c = self.info["channels"]
        xs, ts = [], []
        while self.sig.chunks:
            x, t = self.sig.chunks.popleft()
            xs.append(x)
            ts.append(np.asarray(t, dtype=np.float64))
        mk = []
        while self.mk.samples:
            v, t = self.mk.samples.popleft()
            mk.append((t, str(v[0])))
        if not xs:
            ch = _empty(c)
            ch.markers = mk
            return ch
        return Chunk(np.concatenate(xs), np.concatenate(ts), mk)

    def close(self) -> None:
        if self._started and not self._stopped:
            self._stopped = True
            self.bridge.stop()


class LSLSource:
    """A raw-signal LSL stream (EMG, EEG) and an optional marker stream.

    Find the signal stream by ``name``, ``type`` or ``source_id``. The
    marker stream: ``markers="auto"`` uses ``desc/fidetype/events_source_id``
    of the signal stream (the BrainFlow bridge and ``fidetype live
    replay-kt`` set it), ``"none"`` reads none, any other value is a
    stream name. Marker samples are plain strings: ``keypress`` (key
    onset) and ``segment_end``.

    Reconnect (P4-11). When an inlet is lost (signal or markers), the
    source closes both inlets and resolves both streams again on worker
    threads (:class:`fidetype.adapters.lsl._Reopener` and ``_Reconnector``:
    a continuous resolver that prefers a new outlet; the wait after the
    k-th failed try is ``retry_s * backoff**(k-1)``, at most
    ``max_retry_s``). It gives up after ``reconnect_timeout`` seconds per
    loss, or at a loss after ``max_reconnects`` reconnects in one run
    (0: no reconnect, the P14-04 behaviour). Then ``poll`` returns
    ``None`` and :attr:`stop_reason` says why. A new stream must have the
    same channel count and rate. ``inlet`` / ``marker_inlet`` / ``reopen``
    / ``reopen_markers`` inject fakes (tests); then no stream is resolved.
    """

    def __init__(self, name: str | None = None, type: str | None = None, source_id: str | None = None,
                 markers: str = "auto", timeout: float = 10.0, modality: str | None = None, *,
                 max_reconnects: int = 5, reconnect_timeout: float = 30.0, retry_s: float = 0.05,
                 backoff: float = 2.0, max_retry_s: float = 2.0, gap_factor: float = 2.5,
                 inlet: Any = None, marker_inlet: Any = None, reopen: Callable[[], Any] | None = None,
                 reopen_markers: Callable[[], Any] | None = None, clock: Callable[[], float] | None = None,
                 log: Callable[[str], None] | None = None) -> None:
        from fidetype.adapters import lsl as L

        self.L = L
        self.log = log or (lambda m: None)
        if max_reconnects < 0 or reconnect_timeout < 0 or gap_factor <= 1 or backoff < 1:
            raise ValueError("max_reconnects and reconnect_timeout must be >= 0; gap_factor > 1; backoff >= 1")
        self.max_reconnects = int(max_reconnects)
        self.reconnect_timeout = float(reconnect_timeout)
        self.retry_s, self.backoff, self.max_retry_s = float(retry_s), float(backoff), float(max_retry_s)
        self.gap_factor = float(gap_factor)
        injected = inlet is not None
        mapping = L.LSLMapping(reconnect_timeout_s=reconnect_timeout)
        if not injected:
            pl = L.require_pylsl()
            if not (name or type or source_id):
                raise ValueError("give a stream name, type or source_id")
            inlet = L._open_first(lambda left: L.resolve(name, type, source_id, left), L.DEFAULT_OPEN_TIMEOUT_S,
                                  timeout)
            self._local_clock = pl.local_clock
        else:
            self._local_clock = clock or time.perf_counter
        self.inlet = inlet
        si = self.inlet.info()
        if si.is_string or si.channel_count < 1:
            raise ValueError(f"stream {si.name!r} is not a numeric signal stream")
        if reopen is None and not injected:
            q = {"source_id": si.source_id} if si.source_id else {"name": si.name, "type": si.type or None}
            reopen = L._Reopener(q, si.uid, mapping)
        self.reopen = reopen
        self.marker_inlet = marker_inlet
        self.reopen_markers = reopen_markers
        q2: dict[str, Any] | None = None
        if not injected and markers != "none":
            if markers == "auto":
                esid = si.fidetype.get("events_source_id")
                if esid:
                    q2 = {"source_id": esid}
            else:
                q2 = {"name": markers}
        if q2 is not None:
            try:
                self.marker_inlet = L._open_first(lambda left: L.resolve(timeout=left, **q2),
                                                  L.DEFAULT_OPEN_TIMEOUT_S, min(timeout, 5.0))
                self.reopen_markers = L._Reopener(q2, self.marker_inlet.info().uid, mapping)
            except L.LSLResolveError:
                if markers != "auto":
                    raise
        typ = (si.type or "").lower()
        mod = modality or (si.fidetype.get("device.modality") or ("emg" if typ == "emg" else
                                                                   "eeg" if typ == "eeg" else "other"))
        self.stream_name = si.name
        self.info = {"name": f"lsl:{si.name}", "sample_rate": float(si.nominal_srate),
                     "channels": int(si.channel_count),
                     "modality": mod, "meta": {k: v for k, v in si.fidetype.items()
                                               if k.startswith(("brainflow.", "fidetype.replay"))}}
        self._period = 1.0 / float(si.nominal_srate) if si.nominal_srate > 0 else None
        self._off = 0.0
        self._moff = 0.0
        self._last_tc = -1e9
        self._ended = False
        #: Why the source ended ("" while it runs), for the run summary.
        self.stop_reason = ""
        self.reconnects = 0
        self.losses = 0
        self.gaps = 0
        self._last_t = -math.inf  # last delivered sample time (corrected)
        self._lost_since: float | None = None
        self._lost_t: float | None = None
        self._rc: dict[str, Any] = {}
        self._got: dict[str, Any] = {}
        self._pending_gap: dict[str, Any] | None = None
        self._stash: Chunk | None = None

    def start(self) -> None:
        pass

    def _tc(self) -> None:
        now = self._local_clock()
        if now - self._last_tc > 5.0:
            self._off = float(self.inlet.time_correction(2.0))
            if self.marker_inlet is not None:
                self._moff = float(self.marker_inlet.time_correction(2.0))
            self._last_tc = now

    # --- loss and reconnect ---------------------------------------------------------------

    def _end(self, why: str) -> None:
        self._ended = True
        self.stop_reason = why
        for rc in self._rc.values():
            rc.cancel()
        self._rc, self._got = {}, {}
        self.log(why)

    def _worker(self, reopen: Callable[[], Any], role: str) -> Any:
        return self.L._Reconnector(reopen, retry_s=self.retry_s, prewarm_tc_s=0.0,
                                   give_up_s=self.reconnect_timeout + 1.0, name=f"live-{role}",
                                   backoff=self.backoff, max_retry_s=self.max_retry_s)

    def _on_lost(self, why: str) -> Chunk | None:
        self.losses += 1
        self.L._close_quietly(self.inlet)
        if self.marker_inlet is not None:
            self.L._close_quietly(self.marker_inlet)
        ch = _empty(self.info["channels"])
        ch.lost = True  # the consumer drops the open segment; the next poll ends the run if we give up
        if self.reopen is None or self.max_reconnects == 0:
            self._end(f"stream {self.stream_name!r} lost ({why}); reconnect is off")
            return ch
        if self.reconnects >= self.max_reconnects:
            self._end(f"stream {self.stream_name!r} lost ({why}); max_reconnects {self.max_reconnects} reached")
            return ch
        self.log(f"stream {self.stream_name!r} lost ({why}); resolving it again (up to {self.reconnect_timeout:g} s)")
        self._lost_since = time.monotonic()
        self._lost_t = self._last_t if math.isfinite(self._last_t) else None
        self._rc = {"signal": self._worker(self.reopen, "signal")}
        if self.reopen_markers is not None:
            self._rc["markers"] = self._worker(self.reopen_markers, "markers")
        self._got = {}
        return ch

    def _try_reconnect(self, timeout: float) -> Chunk | None:
        assert self._lost_since is not None
        for k, rc in list(self._rc.items()):
            if k in self._got:
                continue
            # one consistent read (P4-14): two done() calls could see a worker that has just
            # set its inlet, start a second worker and call reopen() once more
            got, ended = rc.take_or_ended(timeout if not self._got else 0.0)
            if got is not None:
                self._got[k] = got
            elif ended:  # the worker ended without an inlet: start a new one
                self._rc[k] = self._worker(rc._reopen, k)
        if len(self._got) < len(self._rc):
            if time.monotonic() - self._lost_since > self.reconnect_timeout:
                for v in self._got.values():
                    self.L._close_quietly(v)
                self._end(f"stream {self.stream_name!r} lost and not back within {self.reconnect_timeout:g} s")
                return None
            return _empty(self.info["channels"])
        sig = self._got["signal"]
        si = sig.info()
        if int(si.channel_count) != self.info["channels"] or \
                abs(float(si.nominal_srate) - self.info["sample_rate"]) > 1e-9:
            for v in self._got.values():
                self.L._close_quietly(v)
            self._end(f"stream {si.name!r} came back with {si.channel_count} ch at {si.nominal_srate} Hz; "
                      f"expected {self.info['channels']} ch at {self.info['sample_rate']:g} Hz")
            return None
        self.inlet = sig
        if "markers" in self._got:
            self.marker_inlet = self._got["markers"]
        self.reconnects += 1
        self.log(f"stream {si.name!r} reconnected after {time.monotonic() - self._lost_since:.2f} s "
                 f"(reconnect {self.reconnects})")
        self._rc, self._got = {}, {}
        self._lost_since = None
        self._last_tc = -1e9  # a new outlet: ask for the clock offset again
        self._pending_gap = {"t_start": self._lost_t}
        return _empty(self.info["channels"])

    def _gap_fields(self, t0: float | None, t1: float, cause: str) -> dict[str, Any]:
        missing = None
        if self._period is not None and t0 is not None:
            missing = max(0, int(round((t1 - t0) / self._period)) - 1)
        self.gaps += 1
        return {"t_start": t0 if t0 is not None else t1, "t_end": t1, "missing_frames": missing,
                "stream": self.stream_name, "cause": cause}

    # --- polling ----------------------------------------------------------------------------

    def poll(self, timeout: float = 0.05) -> Chunk | None:
        if self._ended:
            return None
        if self._stash is not None:
            ch, self._stash = self._stash, None
            return ch
        if self._lost_since is not None:
            return self._try_reconnect(timeout)
        try:
            self._tc()
            rows, ts = self.inlet.pull_chunk(timeout, 4096)
            mk: list[tuple[float, str]] = []
            if self.marker_inlet is not None:
                mrows, mts = self.marker_inlet.pull_chunk(0.0, 1024)
                mk = [(float(t) + self._moff, str(r[0])) for r, t in zip(mrows, mts)]
        except self.L.LSLStreamLost as e:
            return self._on_lost(str(e))
        c = self.info["channels"]
        if not rows:
            ch = _empty(c)
            ch.markers = mk
            return ch
        x = np.asarray(rows, dtype=np.float32).reshape(len(rows), c)
        t = np.asarray(ts, dtype=np.float64) + self._off
        gap = None
        if self._pending_gap is not None:  # the first samples after a reconnect
            gap = self._gap_fields(self._pending_gap["t_start"], float(t[0]), "lost")
            self._pending_gap = None
        elif self._period is not None and math.isfinite(self._last_t) and \
                t[0] - self._last_t > self.gap_factor * self._period:
            gap = self._gap_fields(self._last_t, float(t[0]), "timestamp")
        if self._period is not None and len(t) > 1:  # a time jump inside the chunk: deliver it in two parts
            k = np.flatnonzero(np.diff(t) > self.gap_factor * self._period)
            if k.size:
                j = int(k[0]) + 1
                self._stash = Chunk(x[j:], t[j:], [m for m in mk if m[0] >= t[j]],
                                    gap=self._gap_fields(float(t[j - 1]), float(t[j]), "timestamp"))
                mk = [m for m in mk if m[0] < t[j]]
                x, t = x[:j], t[:j]
                self._last_t = float(self._stash.times[-1])
                return Chunk(x, t, mk, gap=gap)
        self._last_t = float(t[-1])
        return Chunk(x, t, mk, gap=gap)

    def close(self) -> None:
        for rc in self._rc.values():
            rc.cancel()
        self._rc, self._got = {}, {}
        self.L._close_quietly(self.inlet)
        if self.marker_inlet is not None:
            self.L._close_quietly(self.marker_inlet)
