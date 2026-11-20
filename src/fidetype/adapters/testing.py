"""Adapter conformance helpers for pytest (P14-42).

Every adapter runs one of two helpers on **synthetic** data. The helpers
add no new contract. They test the two contracts that exist:

- **Signal source** (a device or a file reader): the source protocol of
  :mod:`fidetype.live.sources` (``info``, ``start()``, ``poll()``,
  ``close()``; ``poll`` returns a :class:`~fidetype.live.sources.Chunk`
  or ``None`` at the end). The ``meta`` keys follow the NTS meta rules
  (spec 4.1, 4.2: defined keys and their types, namespaced custom keys,
  no truth text, no personal data). Optional ``channel_labels`` and
  ``channel_units`` use the names of the LSL binding
  (:class:`fidetype.adapters.lsl.LSLStreamInfo`, ``desc/channels``).
- **NTS producer** (a decoder-output or a replay adapter): the
  NeuralTextStream conformance suite (:func:`fidetype.conformance.check`)
  at a given level.

Both helpers also check that bad input raises :class:`ValueError` with a
message (not an ``IndexError``, a ``struct.error`` or silent garbage).

Use in a test::

    from fidetype.adapters.testing import assert_source_conforms
    assert_source_conforms(lambda: my_adapter.open_source(path), bad_inputs=[lambda: my_adapter.open_source(bad)])

Check ids (``SRC-*``) appear in the assertion message. Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

import numpy as np

__all__ = ["Finding", "check_source", "assert_source_conforms", "check_bad_inputs", "assert_nts_conforms"]


@dataclass
class Finding:
    check_id: str
    message: str


@dataclass
class SourceResult:
    findings: list[Finding] = field(default_factory=list)
    n_samples: int = 0
    n_chunks: int = 0
    markers: list[tuple[float, str]] = field(default_factory=list)

    def fail(self, check_id: str, message: str) -> None:
        self.findings.append(Finding(check_id, message))

    @property
    def ok(self) -> bool:
        return not self.findings


def _meta_findings(meta: Any, res: SourceResult) -> None:
    from fidetype.conformance.checks import DEFINED_KEYS, LEAK_KEY_NAMES, PII_KEY_NAMES, RESERVED_NAMESPACES

    if not isinstance(meta, dict):
        res.fail("SRC-META", f"info['meta'] must be a dict, got {type(meta).__name__}")
        return
    try:
        json.dumps(meta, allow_nan=False)
    except (TypeError, ValueError) as e:
        res.fail("SRC-META", f"meta is not JSON-serialisable: {e}")
    for k, v in meta.items():
        if k in DEFINED_KEYS:
            err = DEFINED_KEYS[k](v)
            if err:
                res.fail("SRC-META", f"meta[{k!r}] must be {err} (NTS 4.2), got {v!r}")
        elif "." not in k:
            res.fail("SRC-META", f"meta key {k!r} is not namespaced (NTS 4.1: use '<namespace>.{k}')")
        elif k.split(".")[0] in RESERVED_NAMESPACES:
            res.fail("SRC-META", f"custom key {k!r} is inside a defined NTS namespace (NTS 4.1, ambiguity A2)")
        last = k.rsplit(".", 1)[-1].lower()
        if last in LEAK_KEY_NAMES:
            res.fail("SRC-PRIVACY", f"meta key {k!r} looks like truth text (NTS 5.3)")
        if last in PII_KEY_NAMES:
            res.fail("SRC-PRIVACY", f"meta key {k!r} looks like personal data (NTS 5.4.1)")


def _info_findings(info: Any, res: SourceResult, require_units: bool) -> tuple[float, int]:
    from fidetype.conformance.checks import MODALITIES

    if not isinstance(info, dict):
        res.fail("SRC-INFO", f"source.info must be a dict, got {type(info).__name__}")
        return 0.0, 0
    for k in ("name", "sample_rate", "channels", "modality", "meta"):
        if k not in info:
            res.fail("SRC-INFO", f"source.info has no {k!r}")
    name, fs, ch = info.get("name"), info.get("sample_rate"), info.get("channels")
    if not (isinstance(name, str) and name):
        res.fail("SRC-INFO", f"info['name'] must be a non-empty string, got {name!r}")
    if not (isinstance(fs, (int, float)) and not isinstance(fs, bool) and math.isfinite(fs) and fs > 0):
        res.fail("SRC-INFO", f"info['sample_rate'] must be a finite number > 0 (Hz), got {fs!r}")
        fs = 0.0
    if not (isinstance(ch, int) and not isinstance(ch, bool) and ch >= 1):
        res.fail("SRC-INFO", f"info['channels'] must be an integer >= 1, got {ch!r}")
        ch = 0
    if info.get("modality") not in MODALITIES:
        res.fail("SRC-INFO", f"info['modality'] must be one of {list(MODALITIES)} (NTS device.modality), "
                             f"got {info.get('modality')!r}")
    _meta_findings(info.get("meta"), res)
    meta_mod = info.get("meta", {}).get("device.modality") if isinstance(info.get("meta"), dict) else None
    if meta_mod is not None and meta_mod != info.get("modality"):
        res.fail("SRC-INFO", f"meta['device.modality'] {meta_mod!r} differs from info['modality']")
    for key in ("channel_labels", "channel_units"):
        vals = info.get(key)
        if vals is None:
            if require_units:
                res.fail("SRC-UNITS", f"info has no {key!r} (one string per channel, as LSL desc/channels)")
            continue
        if not (isinstance(vals, list) and all(isinstance(x, str) for x in vals)) or len(vals) != ch:
            res.fail("SRC-UNITS", f"info[{key!r}] must be a list of {ch} strings, got {vals!r}")
    return float(fs), int(ch)


def check_source(make_source: Callable[[], Any], *, require_units: bool = False, expect_channels: int | None = None,
                 expect_rate: float | None = None, max_polls: int = 100_000, rate_tol: float = 0.01) -> SourceResult:
    """Run one source to its end and check the source contract. Return a :class:`SourceResult`.

    ``require_units``: file and device readers that know the channel names
    and units must give ``channel_labels`` and ``channel_units``.
    ``rate_tol``: allowed relative error of the median sample spacing.
    """
    from fidetype.live.sources import Chunk

    res = SourceResult()
    src = make_source()
    fs, ch = _info_findings(getattr(src, "info", None), res, require_units)
    if expect_channels is not None and ch != expect_channels:
        res.fail("SRC-INFO", f"channels {ch}, expected {expect_channels}")
    if expect_rate is not None and abs(fs - expect_rate) > 1e-9 * max(1.0, expect_rate):
        res.fail("SRC-INFO", f"sample_rate {fs}, expected {expect_rate}")
    src.start()
    times: list[np.ndarray] = []
    ended = False
    for _ in range(max_polls):
        c = src.poll(0.0)
        if c is None:
            ended = True
            break
        res.n_chunks += 1
        if not isinstance(c, Chunk):
            res.fail("SRC-CHUNK", f"poll() must return a Chunk or None, got {type(c).__name__}")
            break
        x, t = c.samples, c.times
        if not (isinstance(x, np.ndarray) and x.dtype == np.float32 and x.ndim == 2 and x.shape[1] == ch):
            res.fail("SRC-CHUNK", f"samples must be float32 (n, {ch}), got "
                                  f"{getattr(x, 'dtype', None)} {getattr(x, 'shape', None)}")
            break
        if not (isinstance(t, np.ndarray) and t.dtype == np.float64 and t.shape == (x.shape[0],)):
            res.fail("SRC-TIME", f"times must be float64 ({x.shape[0]},), got "
                                 f"{getattr(t, 'dtype', None)} {getattr(t, 'shape', None)}")
            break
        if not (np.isfinite(x).all() and np.isfinite(t).all()):
            res.fail("SRC-CHUNK", "samples and times must be finite")
        for m in c.markers:
            if not (isinstance(m, tuple) and len(m) == 2 and isinstance(m[1], str) and math.isfinite(float(m[0]))):
                res.fail("SRC-MARKER", f"a marker must be (time, str), got {m!r}")
                break
        res.markers += list(c.markers)
        res.n_samples += x.shape[0]
        times.append(t)
    if not ended:
        res.fail("SRC-END", f"the source did not end (poll() returned None) within {max_polls} polls")
    src.close()
    src.close()  # close() must be idempotent
    if res.n_samples == 0:
        res.fail("SRC-CHUNK", "the source gave no samples")
        return res
    tt = np.concatenate(times)
    if tt.size > 1:
        d = np.diff(tt)
        if (d <= 0).any():
            res.fail("SRC-TIME", f"times must strictly increase across chunks ({int((d <= 0).sum())} steps <= 0)")
        elif fs > 0 and abs(float(np.median(d)) * fs - 1.0) > rate_tol:
            res.fail("SRC-TIME", f"median sample spacing {float(np.median(d)):.6g} s does not match "
                                 f"sample_rate {fs} Hz (tolerance {rate_tol:.0%})")
    mt = [float(m[0]) for m in res.markers]
    if any(b < a for a, b in zip(mt, mt[1:])):
        res.fail("SRC-MARKER", "marker times must not decrease")
    return res


def check_bad_inputs(bad_inputs: Iterable[Callable[[], Any]]) -> list[Finding]:
    """Each callable must raise :class:`ValueError` (or a subclass) with a message."""
    out = []
    for i, fn in enumerate(bad_inputs):
        try:
            fn()
        except ValueError as e:
            if not str(e):
                out.append(Finding("SRC-BAD-INPUT", f"bad input {i}: ValueError without a message"))
        except Exception as e:  # noqa: BLE001 - the point is to report the wrong type
            out.append(Finding("SRC-BAD-INPUT", f"bad input {i}: raised {type(e).__name__} ({e}), not ValueError"))
        else:
            out.append(Finding("SRC-BAD-INPUT", f"bad input {i}: no error raised"))
    return out


def _raise(findings: Sequence[Finding], what: str) -> None:
    if findings:
        raise AssertionError(f"{what} does not conform:\n" + "\n".join(f"  {f.check_id}: {f.message}" for f in findings))


def assert_source_conforms(make_source: Callable[[], Any], *, bad_inputs: Iterable[Callable[[], Any]] = (),
                           **kw: Any) -> SourceResult:
    """pytest helper: :func:`check_source` plus :func:`check_bad_inputs`; raise ``AssertionError`` on a finding."""
    res = check_source(make_source, **kw)
    res.findings += check_bad_inputs(bad_inputs)
    _raise(res.findings, "signal source")
    return res


def assert_nts_conforms(make_streams: Callable[[], Iterable[Any]], *, level: str = "trust-ready",
                        truth: Iterable[str] = (), bad_inputs: Iterable[Callable[[], Any]] = ()) -> list[Any]:
    """pytest helper for NTS producers: every stream reaches ``level`` in :func:`fidetype.conformance.check`.

    ``truth``: the synthetic intended texts (enables the leakage check, NTS 5.3.1). Return the reports.
    """
    from fidetype.conformance import check

    findings, reports = [], []
    for i, s in enumerate(make_streams()):
        rep = check(s, truth=list(truth))
        reports.append(rep)
        if not rep.passes(level):
            for r in rep.failures(level):
                findings.append(Finding(r.check_id, f"stream {i}: [spec {r.clause}] {r.message}"))
    if not reports:
        findings.append(Finding("NTS-NONE", "the adapter produced no stream"))
    findings += check_bad_inputs(bad_inputs)
    _raise(findings, f"NTS producer (level {level})")
    return reports
