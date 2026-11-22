"""Frame-order integrity check of a stream (P5-36).

NTS rule TIM-2: frame times MUST increase strictly from frame to frame. The streaming layer
(:class:`~fidetype.trust.streaming.StreamingTrustLayer`) and :class:`~fidetype.streams.spec.NeuralTextStream`
already **refuse** such a stream with an exception. A :class:`~fidetype.trust.TrustGuard` reads a ``(T, V)``
matrix and makes its own frame times, so it did not see the times of the producer at all.

This module gives the check as a function that returns a report (no exception), and the guard uses it when
the caller passes the producer's frame times (``guard.decide(x, frame_times=...)``,
``session.push(chunk, times=...)``). A stream that fails the check gets a WITHHOLD (``ABSTAIN``) with a
reason code; the guard never commits or offers from it.

What the check can and cannot see:

- It sees a fault that moves frames **with their times**: a reversed, reordered or repeated frame list at
  the transport or adapter level (times decrease or repeat).
- It does **not** see a fault that changes the frame **values** while the times stay in order, for example
  rows reversed after the decoder and given new times (the P14-57 ``rev_out`` input). Only a statistic of the
  frame values can see that (for example the offer-gate feature ``lm_direction``).
- Without ``frame_times`` the guard makes the times itself (``frame_period`` steps), so there is nothing to
  check.

The check is a separate integrity layer. It is **not** part of the frozen configuration and does not change
``config_id``: on a stream that meets TIM-2 it changes no decision (the decision is computed in the same way;
the times are not used for it). It only turns a decision on a stream that breaks TIM-2 into a WITHHOLD.

Codes (first match wins, in this order):

=========================  ===================================================================
code                       meaning
=========================  ===================================================================
``frame_times_shape``      not one time per frame
``frame_times_not_finite`` a time is NaN or infinite (TIM-1)
``frame_order_reversed``   every step is negative (a whole stream in reverse order; T >= 2)
``frame_order``            at least one step is < ``-min_step``: a frame goes back in time
``frame_duplicate``        a step is in ``[-min_step, min_step]`` (a repeated time; with ``min_step = 0``:
                           a step of exactly 0)
``frame_gap``              ``max_step`` is set and a step is > ``max_step`` (opt-in; dropped frames)
=========================  ===================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

#: Schema tag of a saved report.
INTEGRITY_SCHEMA = "fidetype.integrity/0.1"
#: The reason codes (module text).
CODES = ("frame_times_shape", "frame_times_not_finite", "frame_order_reversed", "frame_order", "frame_duplicate",
         "frame_gap")
#: Start of :attr:`~fidetype.trust.TrustResult.reason` for a stream that fails the check.
REASON_PREFIX = "withhold: stream integrity check failed"


@dataclass(frozen=True)
class IntegrityReport:
    """The result of :func:`check_frame_times`. ``ok`` is True if the stream passes."""

    ok: bool
    code: str | None = None
    #: Number of bad steps (of the code's kind; for ``frame_order_reversed``: all steps).
    n_bad: int = 0
    #: Index of the first frame of the first bad step (frame ``i`` to ``i + 1``), or None.
    first_bad: int | None = None
    n_frames: int = 0
    detail: str = ""
    settings: Mapping[str, Any] = field(default_factory=dict)

    def reason(self) -> str:
        """The user reason text (empty if ``ok``)."""
        if self.ok:
            return ""
        return f"{REASON_PREFIX} ({self.code}: {self.detail})"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": INTEGRITY_SCHEMA, "ok": self.ok, "code": self.code, "n_bad": self.n_bad,
                "first_bad": self.first_bad, "n_frames": self.n_frames, "detail": self.detail,
                "settings": dict(self.settings)}


def check_frame_times(times: Any, n_frames: int | None = None, *, min_step: float = 0.0,
                      max_step: float | None = None) -> IntegrityReport:
    """Check that the frame times increase strictly (TIM-2), with the stated tolerances.

    ``times``: the producer's frame times in seconds, one per frame, in the order the frames arrived.
    ``n_frames``: the number of frames they belong to (checked if given). A step ``dt = t[i+1] - t[i]``
    passes if ``dt > min_step`` (and ``dt <= max_step`` if ``max_step`` is set). ``min_step = 0`` is TIM-2
    exactly. Returns an :class:`IntegrityReport`; it never raises for bad times.
    """
    min_step = float(min_step)
    if not (math.isfinite(min_step) and min_step >= 0.0):
        raise ValueError("min_step must be a finite number >= 0")
    if max_step is not None:
        max_step = float(max_step)
        if not (math.isfinite(max_step) and max_step > min_step):
            raise ValueError("max_step must be None or a finite number > min_step")
    settings = {"min_step": min_step, "max_step": max_step}
    try:
        t = np.asarray(times, dtype=np.float64)
    except (TypeError, ValueError):
        return IntegrityReport(False, "frame_times_shape", 0, None, 0, "times are not numbers", settings)
    T = int(t.shape[0]) if t.ndim == 1 else 0
    if t.ndim != 1 or (n_frames is not None and T != int(n_frames)):
        want = "?" if n_frames is None else int(n_frames)
        return IntegrityReport(False, "frame_times_shape", 0, None, T,
                               f"times shape {tuple(t.shape)} for {want} frames", settings)
    if not np.all(np.isfinite(t)):
        i = int(np.argmin(np.isfinite(t)))
        return IntegrityReport(False, "frame_times_not_finite", int((~np.isfinite(t)).sum()), i, T,
                               f"time {i} is {t[i]}", settings)
    if T < 2:
        return IntegrityReport(True, None, 0, None, T, "", settings)
    d = np.diff(t)
    if np.all(d < -min_step):
        return IntegrityReport(False, "frame_order_reversed", int(d.size), 0, T,
                               f"all {d.size} steps go back in time", settings)
    back = d < -min_step
    if back.any():
        i = int(np.argmax(back))
        return IntegrityReport(False, "frame_order", int(back.sum()), i, T,
                               f"{int(back.sum())} of {d.size} steps go back in time, first at frame {i} "
                               f"({t[i]:.6g} -> {t[i + 1]:.6g})", settings)
    dup = d <= min_step
    if dup.any():
        i = int(np.argmax(dup))
        return IntegrityReport(False, "frame_duplicate", int(dup.sum()), i, T,
                               f"{int(dup.sum())} of {d.size} steps are <= {min_step:.6g} s, first at frame {i} "
                               f"({t[i]:.6g} -> {t[i + 1]:.6g})", settings)
    if max_step is not None:
        gap = d > max_step
        if gap.any():
            i = int(np.argmax(gap))
            return IntegrityReport(False, "frame_gap", int(gap.sum()), i, T,
                                   f"{int(gap.sum())} of {d.size} steps are > {max_step:.6g} s, first at frame {i}",
                                   settings)
    return IntegrityReport(True, None, 0, None, T, "", settings)


def check_events(events: Sequence[Mapping[str, Any]], *, min_step: float = 0.0,
                 max_step: float | None = None) -> IntegrityReport:
    """:func:`check_frame_times` on the ``t`` of the ``frame`` events of an NTS event list, in list order.

    A frame without a numeric ``t`` gives ``frame_times_not_finite``.
    """
    ts: list[float] = []
    for e in events:
        if e.get("type") != "frame":
            continue
        v = e.get("t")
        ts.append(float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else math.nan)
    return check_frame_times(np.asarray(ts, dtype=np.float64), min_step=min_step, max_step=max_step)
