"""The collector as an NTS consumer: the kit contract of ``nts-conform kit`` (roadmap P7-05).

``fidetype collector consume [--profile P] [--level L] FILE`` reads one file
through the collector's own input path and gives the kit verdict as the exit
code: 0 = accept, 1 = reject, 2 = usage error. The input path is the one that
a running collector uses:

1. the ``file`` receiver (:class:`fidetype.collector.receivers.FileReceiver`):
   JSON Lines (an unreadable line is a loss) or NPZ (the reference reader,
   ``allow_pickle=False``);
2. the ``validate`` processor (:class:`fidetype.collector.processors.ValidateProcessor`)
   at stream level ``L`` (``core``, ``trust-ready`` or ``provenance``,
   spec 9.2): header checks of the conformance suite, frame checks, the
   ``segment_end`` / ``hypothesis`` / ``signal_quality`` checks, and the
   FEP-0001 checks of ``trust_decision`` events (TD-F, TD-5 ... TD-9).

The file is rejected when the receiver or the processor finds any problem
(a ``gap`` or ``lost`` status, an invalid header, event or decision, an event
before the header) or when one file mixes input events and decisions (TD-11).

Scope (what the collector consumes today): the core profile ``v0.1`` and the
text profile ``fep-0001``. Intent (``fep-0003``) and control (``fep-0005``)
events pass the collector without their profile checks, and the collector has
no reader for LSL or WebSocket captures (``fep-0002``, ``fep-0004``): for these
profiles the command rejects with the reason "not supported", so a claim is
``--claim text`` without bindings::

    nts-conform kit --claim text --require-level trust-ready \\
        --cmd "fidetype-collector consume --profile {profile} --level {level} {path}"

Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

#: Suite profiles that the collector consumes (the others: "not supported").
SUPPORTED_PROFILES = ("v0.1", "fep-0001")
#: Stream levels of spec 9.2 (``--level``).
STREAM_LEVELS = ("core", "trust-ready", "provenance")


def consume(path: str | Path, profile: str = "v0.1", level: str = "core") -> list[str]:
    """The reasons to reject ``path`` (an empty list = accept). See the module docstring."""
    from fidetype.collector.processors import ValidateProcessor
    from fidetype.collector.receivers import STATUS, FileReceiver

    if level not in STREAM_LEVELS:
        raise ValueError(f"unknown stream level {level!r} (known: {', '.join(STREAM_LEVELS)})")
    if profile not in SUPPORTED_PROFILES:
        return [f"profile {profile} is not supported by the collector consumer (supported: "
                f"{', '.join(SUPPORTED_PROFILES)})"]
    p = Path(path)
    if p.suffix.lower() not in (".jsonl", ".ndjson", ".npz"):
        return [f"wire form {p.suffix or '(none)'} is not read by the collector file receiver (.jsonl, .npz)"]
    notes: list[str] = []

    def log(m: str) -> None:
        notes.append(m)

    rec = FileReceiver("consume", [p], log, eof="close", batch=4096)
    val = ValidateProcessor("validate", log, on_invalid="cut", level=level)
    rec.start()
    items = []
    while not rec.done:
        items += rec.poll(0.0)
    out = val.process(items)
    why: list[str] = []
    for _, ev in out:
        if ev.get("type") == STATUS and ev.get("status") in ("gap", "lost"):
            why.append(f"input loss: {ev.get('status')} ({ev.get('detail', '')})")
    c = val.counts
    for k in ("invalid_headers", "invalid_events", "invalid_decisions", "dropped_no_header"):
        if c[k]:
            why.append(f"{k.replace('_', ' ')}: {c[k]}")
    types = {ev.get("type") for _, ev in items}
    if "trust_decision" in types and types & {"header", "frame"}:
        why.append("one file holds input events and decisions (TD-11)")
    if not types - {STATUS}:
        why.append("no event")
    if why:
        why += [n for n in notes if "invalid" in n or "unreadable" in n][:3]
    return why


def kit_validator(path: str | Path, profile: str = "v0.1", level: str = "core") -> None:
    """``nts-conform kit --impl fidetype.collector.consume:kit_validator``: returns = accept, raises = reject."""
    why = consume(path, profile, level)
    if why:
        raise ValueError("; ".join(why))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fidetype collector consume",
                                 description="Consume one NTS file through the collector's input path (file "
                                             "receiver + validate processor). Exit 0 = accept, 1 = reject.")
    ap.add_argument("path", help="stream file (.jsonl, .npz) or decision log (.jsonl)")
    ap.add_argument("--profile", default="v0.1", help="suite profile of the kit entry (default v0.1)")
    ap.add_argument("--level", default="core", choices=STREAM_LEVELS, help="stream level to check (spec 9.2)")
    ap.add_argument("--quiet", "-q", action="store_true", help="print nothing")
    a = ap.parse_args(argv)
    if not Path(a.path).is_file():
        print(f"fidetype collector consume: no such file: {a.path}", file=sys.stderr)
        return 2
    why = consume(a.path, a.profile, a.level)
    if not a.quiet:
        print(f"{'reject' if why else 'accept'}: {a.path}" + (f" ({'; '.join(why)})" if why else ""))
    return 1 if why else 0
