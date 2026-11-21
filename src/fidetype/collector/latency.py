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

The budget gate (P2-13; :func:`gate_check`, :func:`gate_verdict`): mode ``strict`` (default on a local
machine) is one run with p95 ``added`` below the limit. Mode ``ci`` (default when ``GITHUB_ACTIONS`` or ``CI``
is set; override with ``FIDETYPE_LATENCY_GATE``) keeps the median rule strict on every run and asks for the
p95 rule in at least one of :data:`CI_ATTEMPTS` independent runs. Reason: on shared runners one thread stall
of about 100 ms in one of 8 to 12 decision steps moves the p95 above 50 ms (CI runs 44673291448 and
44913077810), while our processing (``pipeline``) stays near 1 ms. See ``docs/collector.md``.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import collections
import math
import os
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


# --- the budget gate: strict on a quiet machine, repeat-and-take-best on shared CI runners (P2-13) -------------

#: Gate modes (:func:`gate_mode`). ``strict``: one run; p50 and p95 of ``added`` below the limit (the P3-04 rule).
#: ``ci``: the p50 rule on every run; the p95 rule on at least one of :data:`CI_ATTEMPTS` runs.
GATE_MODES = ("strict", "ci")
#: Runs of the ``ci`` gate at most (the first run, plus repeats only after a tail-only failure).
CI_ATTEMPTS = 3


def gate_mode(env: dict[str, str] | None = None) -> str:
    """The gate mode: ``FIDETYPE_LATENCY_GATE`` (``strict`` or ``ci``) when it is set; else ``ci`` on GitHub
    Actions (``GITHUB_ACTIONS=true``) or another CI (``CI=true`` / ``1``); else ``strict``."""
    e = os.environ if env is None else env
    v = e.get("FIDETYPE_LATENCY_GATE", "").strip().lower()
    if v:
        if v not in GATE_MODES:
            raise ValueError(f"FIDETYPE_LATENCY_GATE must be one of {GATE_MODES}, not {v!r}")
        return v
    if e.get("GITHUB_ACTIONS", "").lower() == "true" or e.get("CI", "").lower() in ("true", "1"):
        return "ci"
    return "strict"


def gate_attempts(mode: str) -> int:
    """Runs at most: 1 for ``strict``, :data:`CI_ATTEMPTS` for ``ci``."""
    if mode not in GATE_MODES:
        raise ValueError(f"mode must be one of {GATE_MODES}")
    return 1 if mode == "strict" else CI_ATTEMPTS


def gate_check(summary: dict[str, Any], limit_ms: float) -> dict[str, Any]:
    """The gate numbers of one run (a :meth:`LatencyRecorder.summary`) against ``limit_ms``.

    ``median_ok``: p50 of ``added`` and of ``pipeline`` below the limit. A slow step in our code, or a wait in
    our receive path, happens on every decision, so it moves the median. ``tail_ok``: p95 of ``added`` below the
    limit (the budget number). ``tail_stage``: the stage that holds most of the ``added`` p95: ``receive`` (the
    event waits in the receiver queue: thread wake-up, runner load) or ``pipeline`` (our processors and exporters).
    """
    st = summary.get("stages", {})

    def q(stage: str, k: str) -> float | None:
        v = st.get(stage, {}).get(k)
        return None if v is None else float(v)

    a50, a95 = q("added", "p50"), q("added", "p95")
    p50, p95, r95 = q("pipeline", "p50"), q("pipeline", "p95"), q("receive", "p95")
    median_ok = a50 is not None and a50 < limit_ms and (p50 is None or p50 < limit_ms)
    tail_ok = a95 is not None and a95 < limit_ms
    tail_stage = None
    if a95 is not None:
        tail_stage = "receive" if (r95 or 0.0) > (p95 or 0.0) else "pipeline"
    return {"limit_ms": limit_ms, "added_p50": a50, "added_p95": a95, "pipeline_p50": p50, "pipeline_p95": p95,
            "receive_p95": r95, "median_ok": median_ok, "tail_ok": tail_ok, "tail_stage": tail_stage}


def gate_verdict(checks: list[dict[str, Any]], mode: str) -> tuple[bool, str]:
    """``(ok, reason)`` of the gate over the runs ``checks`` (:func:`gate_check`, in run order).

    ``strict``: exactly one run; median and tail rules. ``ci``: the median rule on every run (no repeat can hide
    a slow median), and the tail rule on at least one run, at most :data:`CI_ATTEMPTS` runs (a rare runner stall
    does not repeat in independent runs; a slow path of our code does).
    """
    if not checks:
        return False, "no run"
    if mode == "strict":
        if len(checks) != 1:
            raise ValueError("the strict gate takes exactly one run")
        c = checks[0]
        if not c["median_ok"]:
            return False, f"p50 added {c['added_p50']} ms or p50 pipeline {c['pipeline_p50']} ms >= {c['limit_ms']:g} ms"
        if not c["tail_ok"]:
            return False, f"p95 added {c['added_p95']} ms >= {c['limit_ms']:g} ms (tail in {c['tail_stage']})"
        return True, "p50 and p95 added below the limit"
    if mode != "ci":
        raise ValueError(f"mode must be one of {GATE_MODES}")
    if len(checks) > CI_ATTEMPTS:
        raise ValueError(f"the ci gate takes at most {CI_ATTEMPTS} runs")
    for i, c in enumerate(checks, 1):
        if not c["median_ok"]:
            return False, (f"run {i}: p50 added {c['added_p50']} ms or p50 pipeline {c['pipeline_p50']} ms >= "
                           f"{c['limit_ms']:g} ms (median rule, no repeat)")
    good = [i for i, c in enumerate(checks, 1) if c["tail_ok"]]
    if good:
        return True, f"p95 added below the limit in run {good[0]} of {len(checks)}; p50 below in all runs"
    tails = ", ".join(f"{c['added_p95']} ms ({c['tail_stage']})" for c in checks)
    return False, f"p95 added >= {checks[0]['limit_ms']:g} ms in all {len(checks)} runs: {tails}"


def gate_needs_repeat(checks: list[dict[str, Any]], mode: str) -> bool:
    """True when the ``ci`` gate needs one more run: only tail failures so far, and runs left."""
    return (mode == "ci" and 0 < len(checks) < CI_ATTEMPTS and all(c["median_ok"] for c in checks)
            and not any(c["tail_ok"] for c in checks))
