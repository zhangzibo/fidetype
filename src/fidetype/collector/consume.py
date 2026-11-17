"""The collector as an NTS consumer: the kit contract of ``nts-conform kit`` (roadmap P7-05, P7-07).

``fidetype collector consume [--profile P] [--level L] FILE`` reads one file
through the collector's own input path and gives the kit verdict as the exit
code: 0 = accept, 1 = reject, 2 = usage error. The input path is the one that
a running collector uses:

1. a receiver:

   - JSON Lines and NPZ files: the ``file`` receiver
     (:class:`fidetype.collector.receivers.FileReceiver`; an unreadable line is
     a loss; NPZ with the reference reader, ``allow_pickle=False``);
   - LSL captures (``nts-lsl/0.1``, scenario JSON of kind ``inlet``): the
     ``lsl`` receiver (:class:`fidetype.collector.receivers.LSLReceiver`) on an
     LSL source that plays the recorded inlets
     (:func:`fidetype.conformance.capture.lsl_source`, no network);
   - WebSocket captures (``nts-ws/0.1``, kind ``ingest``): the ``websocket``
     receiver (:class:`fidetype.collector.receivers.WebSocketReceiver`). Its
     server is not started; the recorded steps go into the server's ingest core
     (:func:`fidetype.conformance.capture.play_ws_steps`, no network);
   - decision captures (LSL ``decisions``, WebSocket ``subscribe``): the
     ``trust_decision`` events that the reference subscriber reads
     (:func:`fidetype.conformance.capture.received`);

2. the ``validate`` processor (:class:`fidetype.collector.processors.ValidateProcessor`)
   at stream level ``L`` (``core``, ``trust-ready`` or ``provenance``,
   spec 9.2): header checks of the conformance suite, frame checks, the
   ``segment_end`` / ``hypothesis`` / ``signal_quality`` checks, the FEP-0001
   checks of ``trust_decision`` events (TD-F, TD-5 ... TD-9), and the intent
   (FEP-0003) and control (FEP-0005) checks of headers, events and decisions.

A file is rejected when the receiver or the processor finds any problem
(a ``gap`` or ``lost`` status of the file receiver, an invalid header, event or
decision, an event before the header) or when one file mixes input events and
decisions (TD-11). A capture is also rejected when the reference consumer of
its binding profile rejects it (``fep-0002``, ``fep-0004``:
:mod:`fidetype.conformance.profiles`): the binding rules (stream infos, clock,
order, refusals) are the same code. Loss inside a capture (``gap``, ``lost``)
is a binding event that the collector handles (no decision on a cut
utterance), so it does not reject the capture.

All suite profiles are consumed (``v0.1``, ``fep-0001`` ... ``fep-0005``)::

    nts-conform kit --require-level trust-ready --binding nts-lsl/0.1 --binding nts-ws/0.1 \\
        --cmd "fidetype-collector consume --profile {profile} --level {level} {path}"

Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

#: Suite profiles that the collector consumes.
SUPPORTED_PROFILES = ("v0.1", "fep-0001", "fep-0002", "fep-0003", "fep-0004", "fep-0005")
#: Binding profiles: their files are captures (scenario JSON).
CAPTURE_PROFILES = ("fep-0002", "fep-0004")
#: Stream levels of spec 9.2 (``--level``).
STREAM_LEVELS = ("core", "trust-ready", "provenance")
#: Polls without a new item before the capture replay stops (the inlets are played without waiting).
IDLE_POLLS = 3


def _items_from_file(p: Path, log: Callable[[str], None]) -> list[Any]:
    from fidetype.collector.receivers import FileReceiver

    rec = FileReceiver("consume", [p], log, eof="close", batch=4096)
    rec.start()
    items: list[Any] = []
    while not rec.done:
        items += rec.poll(0.0)
    return items


def _items_from_lsl(sc: dict[str, Any], log: Callable[[str], None]) -> list[Any]:
    """Replay an LSL ``inlet`` capture into the collector's LSL receiver."""
    from fidetype.collector.receivers import LSLReceiver
    from fidetype.conformance.capture import lsl_source

    rec = LSLReceiver("consume", log, lambda: lsl_source(sc))
    rec.start()
    items: list[Any] = []
    idle = 0
    try:
        for _ in range(100000):
            if rec.done:
                break
            out = rec.poll(0.0)
            items += out
            busy = any(getattr(r.inlet, "script", None) or r.lost_since is not None for r in rec.src.readers)
            idle = 0 if (busy or out) else idle + 1
            if idle >= IDLE_POLLS:
                break
        items += rec.finish()
    finally:
        rec.stop()
    return items


def _items_from_ws(sc: dict[str, Any], log: Callable[[str], None]) -> list[Any]:
    """Replay a WebSocket ``ingest`` capture into the collector's WebSocket receiver (server not started)."""
    from fidetype.collector.receivers import WebSocketReceiver
    from fidetype.conformance.capture import play_ws_steps, ws_ingest_settings

    rec = WebSocketReceiver("consume", log, ingest=ws_ingest_settings(sc))
    srv = rec.server
    now = [0.0]
    srv.clock = lambda: now[0]

    def call(fn: Any, *a: Any) -> Any:
        if a and isinstance(a[-1], float):
            now[0] = a[-1]
        return srv._core(fn, *a)  # queue the items as the network handler does

    play_ws_steps(sc, srv.core, call)
    return rec.poll(0.0) + rec.finish()


def _capture_items(p: Path, profile: str, log: Callable[[str], None]) -> tuple[list[Any], list[str]]:
    """(collector items, reasons to reject) of one capture: binding reference consumer + receiver replay."""
    from fidetype.conformance.capture import LSL_SCHEMA, WS_SCHEMA, received
    from fidetype.conformance.profiles import get_profile

    try:
        get_profile(profile).consume(p)
    except Exception as e:  # noqa: BLE001 - any exception is a rejection
        return [], [f"binding {profile}: {type(e).__name__}: {e}"[:300]]
    sc = json.loads(p.read_text(encoding="utf-8"))
    kind = (sc.get("schema"), sc.get("kind"))
    try:
        if kind == (LSL_SCHEMA, "inlet"):
            return _items_from_lsl(sc, log), []
        if kind == (WS_SCHEMA, "ingest"):
            return _items_from_ws(sc, log), []
        return [("decisions", ev) for ev in received(sc)], []
    except Exception as e:  # noqa: BLE001
        return [], [f"receiver replay: {type(e).__name__}: {e}"[:300]]


def consume(path: str | Path, profile: str = "v0.1", level: str = "core") -> list[str]:
    """The reasons to reject ``path`` (an empty list = accept). See the module docstring."""
    from fidetype.collector.processors import ValidateProcessor
    from fidetype.collector.receivers import STATUS

    if level not in STREAM_LEVELS:
        raise ValueError(f"unknown stream level {level!r} (known: {', '.join(STREAM_LEVELS)})")
    if profile not in SUPPORTED_PROFILES:
        return [f"profile {profile} is not supported by the collector consumer (supported: "
                f"{', '.join(SUPPORTED_PROFILES)})"]
    p = Path(path)
    capture = profile in CAPTURE_PROFILES
    want = (".json",) if capture else (".jsonl", ".ndjson", ".npz")
    if p.suffix.lower() not in want:
        return [f"wire form {p.suffix or '(none)'} is not read by the collector for {profile} ({', '.join(want)})"]
    notes: list[str] = []

    def log(m: str) -> None:
        notes.append(m)

    if capture:
        items, why = _capture_items(p, profile, log)
        if why:
            return why
    else:
        items = _items_from_file(p, log)
    val = ValidateProcessor("validate", log, on_invalid="cut", level=level)
    out = val.process(items)
    why = []
    if not capture:
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
                                 description="Consume one NTS file or capture through the collector's input path "
                                             "(file, LSL or WebSocket receiver + validate processor). Exit 0 = "
                                             "accept, 1 = reject.")
    ap.add_argument("path", help="stream file (.jsonl, .npz), decision log (.jsonl) or LSL / WebSocket capture (.json)")
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
