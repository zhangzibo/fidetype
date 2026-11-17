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

Our own code (Apache-2.0).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np

from fidetype.live.synthetic import KEYPRESS, SEGMENT_END, SyntheticTypist, Utterance

__all__ = ["Chunk", "SyntheticSource", "ArraySource", "BrainFlowSource", "LSLSource"]


@dataclass
class Chunk:
    samples: np.ndarray  # (n, C) float32
    times: np.ndarray  # (n,) float64 seconds
    markers: list[tuple[float, str]] = field(default_factory=list)


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
    onset) and ``segment_end``. A lost stream ends the run (no reconnect;
    the ``fidetype lsl run`` path has reconnect).
    """

    def __init__(self, name: str | None = None, type: str | None = None, source_id: str | None = None,
                 markers: str = "auto", timeout: float = 10.0, modality: str | None = None) -> None:
        from fidetype.adapters import lsl as L

        self.L = L
        pl = L.require_pylsl()
        if not (name or type or source_id):
            raise ValueError("give a stream name, type or source_id")
        self.inlet = L._open_first(lambda left: L.resolve(name, type, source_id, left), L.DEFAULT_OPEN_TIMEOUT_S,
                                   timeout)
        si = self.inlet.info()
        if si.is_string or si.channel_count < 1:
            raise ValueError(f"stream {si.name!r} is not a numeric signal stream")
        self.marker_inlet = None
        q: dict[str, Any] | None = None
        if markers == "auto":
            esid = si.fidetype.get("events_source_id")
            if esid:
                q = {"source_id": esid}
        elif markers != "none":
            q = {"name": markers}
        if q is not None:
            try:
                self.marker_inlet = L._open_first(lambda left: L.resolve(timeout=left, **q), L.DEFAULT_OPEN_TIMEOUT_S,
                                                  min(timeout, 5.0))
            except L.LSLResolveError:
                if markers != "auto":
                    raise
        typ = (si.type or "").lower()
        mod = modality or (si.fidetype.get("device.modality") or ("emg" if typ == "emg" else
                                                                   "eeg" if typ == "eeg" else "other"))
        self.info = {"name": f"lsl:{si.name}", "sample_rate": float(si.nominal_srate),
                     "channels": int(si.channel_count),
                     "modality": mod, "meta": {k: v for k, v in si.fidetype.items()
                                               if k.startswith(("brainflow.", "fidetype.replay"))}}
        self._local_clock = pl.local_clock
        self._off = 0.0
        self._moff = 0.0
        self._last_tc = -1e9
        self._ended = False

    def start(self) -> None:
        pass

    def _tc(self) -> None:
        now = self._local_clock()
        if now - self._last_tc > 5.0:
            self._off = float(self.inlet.time_correction(2.0))
            if self.marker_inlet is not None:
                self._moff = float(self.marker_inlet.time_correction(2.0))
            self._last_tc = now

    def poll(self, timeout: float = 0.05) -> Chunk | None:
        if self._ended:
            return None
        try:
            self._tc()
            rows, ts = self.inlet.pull_chunk(timeout, 4096)
            mk: list[tuple[float, str]] = []
            if self.marker_inlet is not None:
                mrows, mts = self.marker_inlet.pull_chunk(0.0, 1024)
                mk = [(float(t) + self._moff, str(r[0])) for r, t in zip(mrows, mts)]
        except self.L.LSLStreamLost:
            self._ended = True
            return None
        c = self.info["channels"]
        if not rows:
            ch = _empty(c)
            ch.markers = mk
            return ch
        return Chunk(np.asarray(rows, dtype=np.float32).reshape(len(rows), c),
                     np.asarray(ts, dtype=np.float64) + self._off, mk)

    def close(self) -> None:
        self.L._close_quietly(self.inlet)
        if self.marker_inlet is not None:
            self.L._close_quietly(self.marker_inlet)
