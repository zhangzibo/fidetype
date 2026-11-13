"""Shared helpers of the M6-13 soak test: process metrics, window statistics, JSON Lines output."""

from __future__ import annotations

import ctypes
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


class _PMC(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS_EX
    _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


def proc_stats() -> dict[str, Any]:
    """RSS (working set), private bytes and handle count of this process, plus its CPU seconds."""
    out: dict[str, Any] = {"cpu_s": time.process_time(), "py_threads": None}
    try:
        import threading

        out["py_threads"] = threading.active_count()
    except Exception:  # noqa: BLE001
        pass
    if os.name != "nt":
        try:
            import resource

            out["rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except Exception:  # noqa: BLE001
            pass
        return out
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_uint32]
    k.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    h = k.GetCurrentProcess()
    c = _PMC()
    c.cb = ctypes.sizeof(c)
    k.K32GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
    n = ctypes.c_uint32(0)
    k.GetProcessHandleCount(h, ctypes.byref(n))
    out.update(rss_mb=c.WorkingSetSize / 2**20, private_mb=c.PrivateUsage / 2**20,
               peak_rss_mb=c.PeakWorkingSetSize / 2**20, handles=int(n.value))
    return out


def pstats(values: list[float], scale: float = 1e3) -> dict[str, Any]:
    """n, p50, p95, max of a list of seconds, in ms (scale 1e3)."""
    if not values:
        return {"n": 0, "p50": None, "p95": None, "max": None}
    a = np.asarray(values, dtype=np.float64) * scale
    return {"n": int(a.size), "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95)),
            "max": float(a.max())}


class LogHist:
    """A log-spaced histogram of durations (seconds) for whole-run percentiles (about 1 % bins)."""

    LO, HI, PER_DECADE = 1e-6, 100.0, 230

    def __init__(self) -> None:
        self.nb = int(math.log10(self.HI / self.LO) * self.PER_DECADE) + 2
        self.counts = np.zeros(self.nb, dtype=np.int64)
        self.max = 0.0
        self.n = 0

    def add(self, x: float) -> None:
        i = 0 if x <= self.LO else min(self.nb - 1, int(math.log10(x / self.LO) * self.PER_DECADE) + 1)
        self.counts[i] += 1
        self.n += 1
        self.max = max(self.max, x)

    def quantile(self, q: float) -> float | None:
        if self.n == 0:
            return None
        k = int(np.searchsorted(np.cumsum(self.counts), q * self.n, side="left"))
        return self.LO * 10 ** (k / self.PER_DECADE)  # upper edge of the bin

    def summary_ms(self) -> dict[str, Any]:
        f = (lambda v: None if v is None else v * 1e3)
        return {"n": self.n, "p50": f(self.quantile(0.5)), "p95": f(self.quantile(0.95)),
                "p99": f(self.quantile(0.99)), "max": self.max * 1e3 if self.n else None}


class JsonlWriter:
    """Append-only JSON Lines; each line is flushed and fsynced (a crash loses at most the open window)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "a", encoding="utf-8")

    def write(self, rec: dict[str, Any]) -> None:
        self.fh.write(json.dumps(rec, allow_nan=False, default=_default) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self) -> None:
        self.fh.close()


def _default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return str(o)


def log(msg: str) -> None:
    sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    sys.stderr.flush()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
