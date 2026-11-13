"""BrainFlow -> LSL bridge (M6-08): stream a BrainFlow board as a raw-signal LSL stream.

BrainFlow (https://brainflow.org, MIT licence) reads many EEG/EMG boards
through one API. Its *Synthetic* board (board id -1) makes fake EEG
(16 channels, 250 Hz) with no hardware. BrainFlow has no LSL outlet, so
this bridge reads the board and pushes the samples to LSL. ``brainflow``
and ``pylsl`` are **optional** (``pip install "fidetype[brainflow,lsl]"``);
this module imports without them. Our own code (Apache-2.0); no BrainFlow
code is copied.

Streams (FEP-0002, raw-signal stream):

- **Signal stream**: type ``EEG`` (or ``EMG``/``ExG``), one channel per
  board channel of that kind, ``float32``, ``nominal_srate`` = the board
  rate. ``desc/channels/channel``: ``label`` (the board's electrode name,
  or ``ch<N>``), ``unit`` ``microvolts``, ``type``. ``desc/acquisition``:
  ``manufacturer`` BrainFlow, ``model`` the board name.
  ``desc/fidetype``: ``role`` ``signal``, ``binding`` ``nts-lsl/0.1``,
  ``events_source_id``, ``device.board_id``, ``device.modality``. It has
  no ``nts_header``: a consumer needs a signal decoder to make frames.
- **Markers stream**: type ``Markers``, 1 string channel, irregular rate,
  ``desc/fidetype/role`` ``signal_markers``. With ``trial_s`` the bridge
  sends the plain marker ``segment_end`` every ``trial_s`` seconds (a
  fixed trial clock that starts at the first sample; the marker's LSL
  time is the trial boundary). It is sent when a sample has passed the
  boundary, or ``trial_hold_s`` after it by the LSL clock (dropout). A
  non-zero value v in the BrainFlow marker channel becomes the plain
  marker ``brainflow_marker:<v>`` (a Fidetype consumer ignores and counts it).

Timestamps. BrainFlow gives a Unix time per sample. The synthetic board
sends samples in bursts (several samples about 10 us apart, then a
16 ms step), so raw stamps would look like gaps. The bridge maps the
board time to the LSL clock (one offset at start) and smooths it: the
next stamp is the previous stamp + 1 / srate, pulled towards the board
time by ``track`` of the error per sample. If the board time is more
than ``jump_s`` ahead (lost data), the stamp jumps to the board time, so
the consumer sees a real gap.

Pauses (``pauses``: list of (at_s, for_s)) simulate a dropout: during a
pause the bridge reads and discards the board data (as a radio link that
loses packets).
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

import numpy as np

from fidetype.adapters.lsl import BINDING_VERSION, DESC_ROOT, MARKERS_TYPE, require_pylsl

__all__ = [
    "BridgeConfig", "BridgeStats", "BrainFlowBridge", "FakeBoard", "board_id_from_name", "brainflow_available",
    "open_board", "require_brainflow", "SYNTHETIC_BOARD_ID",
]

SYNTHETIC_BOARD_ID = -1
UNIT = "microvolts"
CHANNEL_KINDS = {"eeg": ("eeg_channels", "EEG"), "emg": ("emg_channels", "EMG"), "exg": ("exg_channels", "ExG")}
SEGMENT_END = "segment_end"


class BrainFlowUnavailableError(ImportError):
    pass


def require_brainflow() -> Any:
    """Import ``brainflow.board_shim`` or raise with an install hint."""
    try:
        from brainflow import board_shim
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise BrainFlowUnavailableError(
            'brainflow is not installed: pip install "fidetype[brainflow]" (MIT licence)') from e
    return board_shim


def brainflow_available() -> bool:
    try:
        require_brainflow()
        return True
    except ImportError:
        return False


def board_id_from_name(name: str) -> int:
    """``synthetic`` -> -1; other names map to ``BoardIds.<NAME>_BOARD`` (needs brainflow); digits pass through."""
    n = name.strip().lower()
    if n.lstrip("-").isdigit():
        return int(n)
    if n == "synthetic":
        return SYNTHETIC_BOARD_ID
    bs = require_brainflow()
    key = n.upper().replace("-", "_")
    for k in (key, key + "_BOARD"):
        if k in bs.BoardIds.__members__:
            return int(bs.BoardIds[k].value)
    raise ValueError(f"unknown BrainFlow board {name!r}")


class BoardLike(Protocol):
    """The part of ``brainflow.BoardShim`` the bridge uses."""

    def prepare_session(self) -> None: ...
    def start_stream(self) -> None: ...
    def get_board_data(self) -> np.ndarray: ...
    def stop_stream(self) -> None: ...
    def release_session(self) -> None: ...


class OutletLike(Protocol):
    def push_chunk(self, x: Any, timestamp: Any = 0.0, pushthrough: bool = True) -> None: ...
    def push_sample(self, x: Any, timestamp: float = 0.0, pushthrough: bool = True) -> None: ...


class FakeBoard:
    """A board without brainflow, for tests: sine waves plus noise in the BrainFlow row layout.

    ``descr`` follows ``BoardShim.get_board_descr``. ``get_board_data``
    returns the samples since the last call (by the wall clock ``clock``,
    in packets of ``packet`` samples, as the synthetic board does).
    """

    def __init__(self, srate: float = 250.0, n_eeg: int = 4, seed: int = 0, packet: int = 4,
                 clock: Callable[[], float] = time.time) -> None:
        self.srate = srate
        self.packet = packet
        self.clock = clock
        self.rng = np.random.default_rng(seed)
        eeg = list(range(1, n_eeg + 1))
        self.descr = {"name": "Fake", "sampling_rate": int(srate), "eeg_channels": eeg,
                      "eeg_names": ",".join(f"E{i}" for i in eeg), "timestamp_channel": n_eeg + 1,
                      "marker_channel": n_eeg + 2, "num_rows": n_eeg + 3}
        self.n = 0
        self.t0: float | None = None
        self.markers: list[float] = []
        self.started = False

    def prepare_session(self) -> None:
        pass

    def start_stream(self) -> None:
        self.t0 = self.clock()
        self.n = 0
        self.started = True

    def insert_marker(self, v: float) -> None:
        self.markers.append(float(v))

    def get_board_data(self) -> np.ndarray:
        assert self.t0 is not None
        due = int((self.clock() - self.t0) * self.srate)
        due -= due % self.packet
        k = max(0, due - self.n)
        d = np.zeros((self.descr["num_rows"], k))
        idx = self.n + np.arange(k)
        for j, ch in enumerate(self.descr["eeg_channels"]):
            d[ch] = 10.0 * (j + 1) * np.sin(2 * np.pi * (j + 1) * idx / self.srate) + self.rng.standard_normal(k)
        # Packet stamps: all samples of a packet carry about the packet time.
        pk = (idx // self.packet + 1) * self.packet
        d[self.descr["timestamp_channel"]] = self.t0 + pk / self.srate + 1e-5 * (idx % self.packet)
        if k and self.markers:
            d[self.descr["marker_channel"], -1] = self.markers.pop(0)
        self.n += k
        return d

    def stop_stream(self) -> None:
        self.started = False

    def release_session(self) -> None:
        pass


def open_board(board_id: int, serial_port: str = "", ip_address: str = "", ip_port: int = 0,
               mac_address: str = "", serial_number: str = "", other: str = "") -> tuple[Any, dict[str, Any]]:
    """Open a BrainFlow board (``BoardShim``) and return it with its description."""
    bs = require_brainflow()
    p = bs.BrainFlowInputParams()
    p.serial_port, p.ip_address, p.ip_port = serial_port, ip_address, ip_port
    p.mac_address, p.serial_number, p.other_info = mac_address, serial_number, other
    bs.BoardShim.disable_board_logger()
    board = bs.BoardShim(board_id, p)
    return board, dict(bs.BoardShim.get_board_descr(board_id))


@dataclass
class BridgeConfig:
    name: str = "fidetype.brainflow"
    source_id: str | None = None
    kind: str = "eeg"
    #: Seconds between ``segment_end`` markers (None: no trial clock).
    trial_s: float | None = 4.0
    #: A boundary with no sample past it is sent this long after it (LSL clock).
    trial_hold_s: float = 0.25
    poll_s: float = 0.02
    track: float = 0.01
    jump_s: float = 0.25
    pauses: Sequence[tuple[float, float]] = ()
    channel_format: str = "float32"


@dataclass
class BridgeStats:
    samples: int = 0
    chunks: int = 0
    markers: int = 0
    board_markers: int = 0
    discarded: int = 0
    jumps: int = 0
    wall_s: float = 0.0
    t_first: float | None = None
    t_last: float | None = None
    #: board-time lag at push: LSL now - stamp of the newest sample (seconds).
    push_lag_s: list[float] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "push_lag_s"}
        if self.push_lag_s:
            a = np.asarray(self.push_lag_s) * 1e3
            d["push_lag_ms"] = {"n": int(a.size), "p50": float(np.percentile(a, 50)),
                                "p95": float(np.percentile(a, 95)), "max": float(a.max())}
        return d


def stream_desc(descr: dict[str, Any], board_id: int, cfg: BridgeConfig, events_source_id: str) -> dict[str, Any]:
    """The stream fields of the signal stream (name, type, labels, desc)."""
    if cfg.kind not in CHANNEL_KINDS:
        raise ValueError(f"unknown channel kind {cfg.kind!r} (one of {tuple(CHANNEL_KINDS)})")
    key, lsl_type = CHANNEL_KINDS[cfg.kind]
    rows = list(descr.get(key) or [])
    if not rows:
        raise ValueError(f"board {descr.get('name')!r} has no {cfg.kind} channels")
    names = [s.strip() for s in str(descr.get(f"{cfg.kind}_names", "")).split(",") if s.strip()]
    labels = names if len(names) == len(rows) else [f"ch{r}" for r in rows]
    return {"rows": rows, "labels": labels, "type": lsl_type, "srate": float(descr["sampling_rate"]),
            "fidetype": {"role": "signal", "binding": BINDING_VERSION, "events_source_id": events_source_id,
                         "device.board_id": str(board_id), "device.board_name": str(descr.get("name", "")),
                         "device.modality": cfg.kind}}


def make_pylsl_outlets(sd: dict[str, Any], descr: dict[str, Any], cfg: BridgeConfig, source_id: str,
                       events_source_id: str) -> tuple[Any, Any]:
    """Create the signal and markers outlets with pylsl."""
    pl = require_pylsl()
    info = pl.StreamInfo(cfg.name, sd["type"], len(sd["rows"]), sd["srate"], cfg.channel_format, source_id)
    chs = info.desc().append_child("channels")
    for lab in sd["labels"]:
        c = chs.append_child("channel")
        c.append_child_value("label", lab)
        c.append_child_value("unit", UNIT)
        c.append_child_value("type", sd["type"])
    acq = info.desc().append_child("acquisition")
    acq.append_child_value("manufacturer", "BrainFlow")
    acq.append_child_value("model", str(descr.get("name", "")))
    f = info.desc().append_child(DESC_ROOT)
    for k, v in sd["fidetype"].items():
        f.append_child_value(k, v)
    mi = pl.StreamInfo(cfg.name + ".markers", MARKERS_TYPE, 1, pl.IRREGULAR_RATE, "string", events_source_id)
    mf = mi.desc().append_child(DESC_ROOT)
    for k, v in {"role": "signal_markers", "binding": BINDING_VERSION, "signal_source_id": source_id}.items():
        mf.append_child_value(k, v)
    return pl.StreamOutlet(info), pl.StreamOutlet(mi)


class BrainFlowBridge:
    """Read a board, push its samples to an LSL outlet (module docstring).

    ``board`` / ``descr``: a ``BoardShim`` (or :class:`FakeBoard`) and its
    description. ``outlets``: a callable ``(stream_desc, source_id,
    events_source_id) -> (signal_outlet, markers_outlet)``; default: pylsl.
    ``lsl_clock`` / ``wall_clock``: the LSL clock and the clock of the
    board stamps (Unix time).
    """

    def __init__(self, board: Any, descr: dict[str, Any], board_id: int, cfg: BridgeConfig | None = None,
                 outlets: Callable[[dict[str, Any], str, str], tuple[Any, Any]] | None = None,
                 lsl_clock: Callable[[], float] | None = None, wall_clock: Callable[[], float] = time.time,
                 log: Callable[[str], None] | None = None) -> None:
        self.board = board
        self.descr = descr
        self.board_id = board_id
        self.cfg = cfg or BridgeConfig()
        self.source_id = self.cfg.source_id or f"fidetype-brainflow-{board_id}-{self.cfg.kind}"
        self.events_source_id = self.source_id + ".markers"
        self.sd = stream_desc(descr, board_id, self.cfg, self.events_source_id)
        if outlets is None:
            def outlets(sd: dict[str, Any], sid: str, esid: str) -> tuple[Any, Any]:
                return make_pylsl_outlets(sd, descr, self.cfg, sid, esid)
        self.signal_outlet, self.marker_outlet = outlets(self.sd, self.source_id, self.events_source_id)
        if lsl_clock is None:
            lsl_clock = require_pylsl().local_clock
        self.lsl_clock = lsl_clock
        self.wall_clock = wall_clock
        self.log = log or (lambda m: None)
        self.stats = BridgeStats()
        self.period = 1.0 / self.sd["srate"]
        self._off: float | None = None
        self._last: float | None = None
        self._next_trial: float | None = None
        self._t_start: float | None = None
        self.ts_row = descr.get("timestamp_channel")
        self.marker_row = descr.get("marker_channel")

    # --- timestamps -----------------------------------------------------------

    def stamps(self, board_t: np.ndarray | None, n: int) -> np.ndarray:
        """LSL stamps of n new samples (module docstring: map, smooth, jump)."""
        now_lsl = self.lsl_clock()
        if self._off is None:
            self._off = now_lsl - self.wall_clock()
        if board_t is None or len(board_t) != n:  # no board stamps: the newest sample is "now"
            board_t = (now_lsl - self._off) - self.period * np.arange(n - 1, -1, -1)
        tb = np.asarray(board_t, dtype=np.float64) + self._off
        out = np.empty(n)
        last = self._last
        for i in range(n):
            if last is None:
                t = tb[i]
            else:
                model = last + self.period
                err = tb[i] - model
                if err > self.cfg.jump_s:
                    t = tb[i]
                    self.stats.jumps += 1
                else:
                    t = model + self.cfg.track * err
                    t = max(t, last + 0.5 * self.period)
            out[i] = t
            last = t
        self._last = last
        return out

    # --- loop ---------------------------------------------------------------

    def _paused(self, now: float) -> bool:
        if self._t_start is None:
            return False
        el = now - self._t_start
        return any(a <= el < a + d for a, d in self.cfg.pauses)

    def start(self) -> None:
        self.board.prepare_session()
        self.board.start_stream()
        self._t_start = time.monotonic()

    def _trial_markers(self, t_data: float | None) -> None:
        """Send the ``segment_end`` markers that are due.

        A boundary is due when a pushed sample has passed it, or when the
        LSL clock is ``trial_hold_s`` past it (so a boundary inside a
        dropout is still sent on time, as a stimulus computer would).
        """
        if self._next_trial is None or not self.cfg.trial_s:
            return
        due = self.lsl_clock() - self.cfg.trial_hold_s
        if t_data is not None:
            due = max(due, t_data)
        while self._next_trial <= due:
            self.marker_outlet.push_sample([SEGMENT_END], self._next_trial)
            self.stats.markers += 1
            self._next_trial += float(self.cfg.trial_s)

    def step(self) -> int:
        """Read the board once and push what it gave. Return the number of samples pushed."""
        data = np.asarray(self.board.get_board_data())
        if data.ndim != 2 or data.shape[1] == 0:
            self._trial_markers(None)
            return 0
        n = data.shape[1]
        if self._paused(time.monotonic()):
            self.stats.discarded += n
            self._trial_markers(None)
            return 0
        x = data[self.sd["rows"]].T.astype(np.float32)
        bt = data[self.ts_row] if self.ts_row is not None else None
        ts = self.stamps(bt, n)
        self.signal_outlet.push_chunk(x, ts.tolist())
        self.stats.samples += n
        self.stats.chunks += 1
        if self.stats.t_first is None:
            self.stats.t_first = float(ts[0])
            if self.cfg.trial_s:
                self._next_trial = float(ts[0]) + self.cfg.trial_s
        self.stats.t_last = float(ts[-1])
        lag = self.lsl_clock() - float(ts[-1])
        self.stats.push_lag_s.append(lag)
        if len(self.stats.push_lag_s) > 200_000:
            del self.stats.push_lag_s[:100_000]
        if self.marker_row is not None:
            for i in np.nonzero(data[self.marker_row])[0]:
                v = float(data[self.marker_row, i])
                self.marker_outlet.push_sample([f"brainflow_marker:{v:g}"], float(ts[i]))
                self.stats.board_markers += 1
        self._trial_markers(float(ts[-1]))
        return n

    def stop(self) -> None:
        try:
            self.board.stop_stream()
        finally:
            self.board.release_session()

    def run(self, duration_s: float | None = None, stop: threading.Event | None = None) -> BridgeStats:
        t0 = time.monotonic()
        self.start()
        self.log(f"streaming {self.sd['type']} '{self.cfg.name}' ({len(self.sd['rows'])} ch, {self.sd['srate']:g} Hz, "
                 f"source_id {self.source_id}); markers '{self.cfg.name}.markers'")
        try:
            while True:
                if stop is not None and stop.is_set():
                    break
                if duration_s is not None and time.monotonic() - t0 >= duration_s:
                    break
                self.step()
                time.sleep(self.cfg.poll_s)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            self.stats.wall_s = time.monotonic() - t0
        return self.stats


def parse_pause(s: str) -> tuple[float, float]:
    a, _, b = s.partition(":")
    at, dur = float(a), float(b)
    if at < 0 or dur <= 0:
        raise ValueError(f"bad pause {s!r}: use AT:FOR seconds")
    return at, dur


def add_cli(sub: Any) -> None:
    """Add the ``brainflow-bridge`` sub-command to an argparse sub-parser set."""
    b = sub.add_parser("brainflow-bridge", help="stream a BrainFlow board (default: Synthetic) to LSL")
    b.add_argument("--board", default="synthetic", help='"synthetic" (id -1), a BoardIds name (cyton, ganglion), '
                   "or an id")
    b.add_argument("--board-id", type=int, default=None, help="BrainFlow board id (overrides --board)")
    b.add_argument("--serial-port", default="")
    b.add_argument("--ip-address", default="")
    b.add_argument("--ip-port", type=int, default=0)
    b.add_argument("--mac-address", default="")
    b.add_argument("--serial-number", default="")
    b.add_argument("--other-info", default="")
    b.add_argument("--kind", choices=tuple(CHANNEL_KINDS), default="eeg", help="board channels to send")
    b.add_argument("--name", default="fidetype.brainflow", help="LSL stream name (markers: NAME.markers)")
    b.add_argument("--source-id", default=None)
    b.add_argument("--trial-s", type=float, default=4.0, help="seconds between segment_end markers (0: none)")
    b.add_argument("--poll", type=float, default=0.02, help="seconds between board reads")
    b.add_argument("--duration", type=float, default=None)
    b.add_argument("--pause", action="append", default=[], metavar="AT:FOR",
                   help="discard the board data for FOR seconds from AT seconds (simulated dropout; repeatable)")
    b.add_argument("--stats", help="write the bridge stats JSON to this file at exit")


def run_cli(a: Any, log: Callable[[str], None]) -> int:
    bid = a.board_id if a.board_id is not None else board_id_from_name(a.board)
    board, descr = open_board(bid, a.serial_port, a.ip_address, a.ip_port, a.mac_address, a.serial_number,
                              a.other_info)
    cfg = BridgeConfig(name=a.name, source_id=a.source_id, kind=a.kind, trial_s=a.trial_s or None, poll_s=a.poll,
                       pauses=[parse_pause(p) for p in a.pause])
    br = BrainFlowBridge(board, descr, bid, cfg, log=log)
    st = br.run(a.duration)
    d = st.as_dict()
    log(f"stop: {st.samples} samples, {st.markers} segment_end markers, {st.discarded} discarded, {st.jumps} jumps")
    if a.stats:
        with open(a.stats, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d, indent=2) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(prog="python -m fidetype.adapters.brainflow_bridge")
    add_cli(ap.add_subparsers(dest="cmd", required=True))
    raise SystemExit(run_cli(ap.parse_args(), lambda m: sys.stderr.write(f"[fidetype.brainflow] {m}\n")))
