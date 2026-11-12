"""NeuralTextStream v0.1 conformance suite (M5-10).

Check that a **producer** (an adapter or a decoder) emits valid
NeuralTextStream, and that a **consumer** accepts and rejects the right
streams. Every check cites the clause of ``spec/neuraltextstream-v0.1.md``
that it tests. Three cumulative levels:

- ``core``: the MUST rules of the frame core, the serialisations and the
  Development event kinds;
- ``trust-ready``: what a trust layer needs (producer, modality,
  causality, calibration state, derived-data flag, language);
- ``provenance``: the section 4.3 keys (stream id, decoder weights hash,
  adapter name and version).

Command line::

    python -m fidetype.conformance check stream.npz --level trust-ready
    python -m fidetype.conformance check adapter:all --json report.json
    python -m fidetype.conformance consumer --cmd "my-reader {path}"

See ``wiki/concepts/conformance-suite.md``.
"""

from __future__ import annotations

from os import PathLike
from typing import Iterable

from fidetype.conformance.checks import LEVELS, REGISTRY, CheckResult, check_table, run_checks
from fidetype.conformance.io import (
    ConsumedStream,
    RawStream,
    StreamRejected,
    from_stream,
    load_stream,
    read_raw,
    write_jsonl,
)
from fidetype.conformance.report import TargetReport, build_report, levels_passed, summary_text
from fidetype.streams.spec import NeuralTextStream


def check_file(path: str | PathLike[str], truth: Iterable[str] | None = None) -> TargetReport:
    """Run all checks on a stream file (``.npz`` or ``.jsonl``)."""
    raw = read_raw(path)
    info = {"format": raw.format}
    if raw.log_probs is not None and raw.log_probs.ndim == 2:
        info.update(n_frames=int(raw.log_probs.shape[0]), vocab_size=int(raw.log_probs.shape[1]))
    return TargetReport(str(path), "file", run_checks(raw, truth), info)


def check_stream(stream: NeuralTextStream, name: str = "<stream>", truth: Iterable[str] | None = None) -> TargetReport:
    """Run all checks on an in-memory stream."""
    info = {"format": "object", "n_frames": stream.n_frames, "vocab_size": stream.vocab_size,
            "vocab_type": stream.vocab_type, "source": stream.source}
    return TargetReport(name, "adapter", run_checks(from_stream(stream), truth), info)


def check_adapter(name: str) -> list[TargetReport]:
    """Run an adapter on synthetic inputs and check every stream it emits."""
    from fidetype.conformance.producers import TARGETS

    names = list(TARGETS) if name == "all" else [name]
    out = []
    for n in names:
        if n not in TARGETS:
            raise ValueError(f"unknown adapter {n!r}; known: {sorted(TARGETS)} or 'all'")
        for p in TARGETS[n]():
            out.append(check_stream(p.stream, f"adapter:{n}:{p.name}", p.truth))
    return out


__all__ = [
    "LEVELS", "REGISTRY", "CheckResult", "ConsumedStream", "NeuralTextStream", "RawStream", "StreamRejected",
    "TargetReport", "build_report", "check_adapter", "check_file", "check_stream", "check_table", "from_stream",
    "levels_passed", "load_stream", "read_raw", "run_checks", "summary_text", "write_jsonl",
]
