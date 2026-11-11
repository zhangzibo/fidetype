"""Keep Windows awake during long jobs, and count only active compute time.

Two problems caused the short M1-15 r1 run (2026-11-09): the PC went to S3
sleep, and ``max_minutes`` used wall-clock time, so the sleep counted as
training time.

- :func:`keep_awake` asks Windows not to sleep while a job runs
  (``SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)``). It clears
  the request on exit, also on exceptions. On other systems it does nothing.
- :class:`ActiveTimer` adds up ``time.monotonic()`` deltas between ticks. It
  ignores any single gap longer than ``max_gap_s`` (a suspend or a hang), so a
  time budget counts compute time only.
"""

from __future__ import annotations

import contextlib
import sys
import time
from typing import Any, Callable, Iterator

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _kernel32() -> Any | None:
    if sys.platform != "win32":
        return None
    import ctypes

    return ctypes.windll.kernel32  # type: ignore[attr-defined]


def set_keep_awake(on: bool, kernel32: Any | None = None) -> bool:
    """Set (``on``) or clear the "system required" state. Returns True if a
    Windows call was made and succeeded, False otherwise (no-op off Windows)."""
    k = kernel32 if kernel32 is not None else _kernel32()
    if k is None:
        return False
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if on else ES_CONTINUOUS
    try:
        return bool(k.SetThreadExecutionState(flags))
    except Exception:  # pragma: no cover - never break a training run for this
        return False


@contextlib.contextmanager
def keep_awake(log: Callable[[str], None] | None = None, kernel32: Any | None = None) -> Iterator[bool]:
    """Context manager: keep the system awake inside the block."""
    ok = set_keep_awake(True, kernel32)
    if log is not None:
        log(f"keep_awake: {'on (SetThreadExecutionState)' if ok else 'not available (no-op)'}")
    try:
        yield ok
    finally:
        if ok:
            set_keep_awake(False, kernel32)
            if log is not None:
                log("keep_awake: cleared")


class ActiveTimer:
    """Accumulate active time from ``clock()`` deltas; skip gaps > ``max_gap_s``."""

    def __init__(self, active_s: float = 0.0, max_gap_s: float = 300.0,
                 clock: Callable[[], float] | None = None,
                 on_gap: Callable[[float], None] | None = None) -> None:
        self.active_s = float(active_s)
        self.max_gap_s = float(max_gap_s)
        self.clock = clock if clock is not None else time.monotonic
        self.on_gap = on_gap
        self.gaps: list[float] = []
        self._last = self.clock()

    def tick(self) -> float:
        """Add the time since the last tick (unless it is a gap). Returns the total."""
        now = self.clock()
        dt = now - self._last
        self._last = now
        if dt > self.max_gap_s:
            self.gaps.append(dt)
            if self.on_gap is not None:
                self.on_gap(dt)
        elif dt > 0:
            self.active_s += dt
        return self.active_s

    def exceeded(self, max_minutes: float | None) -> bool:
        return max_minutes is not None and self.active_s > max_minutes * 60
