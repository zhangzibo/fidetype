"""Latency of the collector per stage and end to end (roadmap P3-04, budget: < 50 ms added).

The collector adds latency between the moment an input event is available
and the moment an exporter has written the decision that the event caused.
:class:`LatencyRecorder` measures it inside :class:`fidetype.collector.service.Pipeline`
(option ``[service] latency = true``). All times use ``time.perf_counter``, the
clock of the WebSocket binding stamps (``ws_t_sent`` from
:class:`fidetype.adapters.ws.WSProducer`, ``ws_t_recv`` from the server) and of the
LSL receiver's private receive stamp (``_fidetype_t_recv``: the pull time from the
inlet, P3-07).

Stages (milliseconds; one sample per pipeline step that wrote at least one decision):

==========================  ==============================================================
``receive``                 the receive stamp of the trigger event (``ws_t_recv``, or ``_fidetype_t_recv``
                            for LSL input) -> the receiver's poll returns (time in the receiver queue;
                            for LSL input this includes the inlet merge-window wait)
``processor.<name>``        time in ``process()`` of one processor
``exporter.<name>``         time in ``export()`` of one exporter
``pipeline``                poll returns -> the last exporter returns
``added``                   **the budget number**: the trigger event is available (its receive stamp,
                            or the poll return for file input) -> the last exporter returns
``e2e``                     ``ws_t_sent`` of the trigger event -> the last exporter returns
                            (adds the loopback transport; same-host producers only)
==========================  ==============================================================

The trigger event of a step is the last boundary (``segment_end``, ``end``) of the batch that the
receiver gave; a segmenter-added boundary carries the stamps of the frame that caused it. Without
a stamped boundary the earliest stamp of the batch is used, so the number is an upper bound.
Each stage keeps the newest ``maxlen`` samples (bounded memory).

Our own code (Apache-2.0).
"""

from __future__ import annotations

import collections
import math
from typing import Any, Iterable

import numpy as np

#: The roadmap budget of P3-04: the collector adds less than this (milliseconds, p95 of ``added``).
BUDGET_MS = 50.0
#: Event types that close a segment (a decision follows them).
BOUNDARY_TYPES = ("segment_end", "end")
#: Receive stamps, first match wins: WebSocket (FEP-0004 server) and LSL (collector receiver, P3-07).
RECV_KEYS = ("ws_t_recv", "_fidetype_t_recv")


def quantiles(ms: Iterable[float]) -> dict[str, Any]:
    """``n``, ``p50``, ``p95``, ``p99``, ``max`` and ``mean`` of a list of milliseconds (None when empty)."""
    a = np.asarray(list(ms), dtype=np.float64)
    if a.size == 0:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None, "mean": None}
    q = np.quantile(a, [0.5, 0.95, 0.99])
    return {"n": int(a.size), "p50": round(float(q[0]), 3), "p95": round(float(q[1]), 3),
            "p99": round(float(q[2]), 3), "max": round(float(a.max()), 3), "mean": round(float(a.mean()), 3)}


def trigger_stamps(items: Iterable[tuple[str, dict[str, Any]]]) -> tuple[float | None, float | None]:
    """``(t_recv, t_sent)`` of the trigger event of a batch (module docstring), or None each."""
    recv: float | None = None
    sent: float | None = None
    first_recv: float | None = None
    first_sent: float | None = None
    for _, ev in items:
        r, s = next((ev[k] for k in RECV_KEYS if k in ev), None), ev.get("ws_t_sent")
        r = float(r) if isinstance(r, (int, float)) and not isinstance(r, bool) and math.isfinite(r) else None
        s = float(s) if isinstance(s, (int, float)) and not isinstance(s, bool) and math.isfinite(s) else None
        if r is not None and (first_recv is None or r < first_recv):
            first_recv = r
        if s is not None and (first_sent is None or s < first_sent):
            first_sent = s
        if ev.get("type") in BOUNDARY_TYPES and r is not None:
            recv, sent = r, s
    if recv is None:
        return first_recv, first_sent
    return recv, sent


class LatencyRecorder:
    """Per-stage samples in milliseconds (module docstring)."""

    def __init__(self, maxlen: int = 100_000) -> None:
        self.maxlen = int(maxlen)
        self.samples: dict[str, collections.deque[float]] = {}
        self.steps = 0

    def add(self, stage: str, seconds: float) -> None:
        d = self.samples.get(stage)
        if d is None:
            d = self.samples[stage] = collections.deque(maxlen=self.maxlen)
        d.append(seconds * 1000.0)

    def summary(self, budget_ms: float = BUDGET_MS) -> dict[str, Any]:
        """``{"budget_ms", "stages": {stage: quantiles}, "within_budget"}`` (``added`` p95 < budget)."""
        order = ["receive"] + sorted(k for k in self.samples if k.startswith("processor.")) \
            + sorted(k for k in self.samples if k.startswith("exporter.")) + ["pipeline", "added", "e2e"]
        stages = {k: quantiles(self.samples[k]) for k in order if k in self.samples}
        p95 = stages.get("added", {}).get("p95")
        return {"budget_ms": budget_ms, "decision_steps": self.steps, "stages": stages,
                "within_budget": None if p95 is None else bool(p95 < budget_ms)}
