"""Replay a recorded signal as live LSL streams for ``fidetype live`` (P14-04). Needs the ``[lsl]`` extra.

:func:`publish_signal` sends a signal array (N, C) on a raw-signal LSL
outlet in real time, with a marker outlet (plain strings ``keypress`` and
``segment_end``). The signal stream follows the FEP-0002 raw-signal form
of the BrainFlow bridge: ``desc/channels``, ``desc/fidetype`` with
``role`` ``signal``, ``binding``, ``events_source_id`` and
``device.modality``. A consumer finds the marker stream through
``events_source_id`` (``fidetype live --markers auto``).

:func:`replay_kt` does this for one KT-sEMG run (EMG 32 channels,
2000 Hz; key onsets from the key log; segments = typing bursts with the
benchmark rule). The markers carry the key **onset** only, never the key:
the decoder must find the key from the EMG. Onsets from the key log are
oracle timing (as in the P4-01 replay streams); a live key-onset detector
is an open gap.

Our own code (Apache-2.0). Data: KT-sEMG, copyright 2021 Nokia, CC BY 4.0.
"""

from __future__ import annotations

import json
import time
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from fidetype.adapters.lsl import BINDING_VERSION, DESC_ROOT, MARKERS_TYPE, require_pylsl

#: Catalogue metadata (P14-42): read by fidetype.adapters.registry -> docs/adapters.md.
ADAPTER_INFO = {
    "id": "kt-semg-lsl-replay", "kind": "dataset-replay", "signal": "emg", "status": "tested", "extra": "lsl",
    "target": "KT-sEMG recording replayed as live raw-signal LSL streams (fidetype live replay-kt)",
    "licence": "Code Apache-2.0. Data CC BY 4.0 (copyright 2021 Nokia). pylsl is MIT.",
    "tests": ["tests/test_live.py", "tools/ci/kt_lsl_replay.py"], "docs": "docs/live-decode.md",
    "support": "replay-only", "transport": ["dataset", "lsl"],
    "real_data_evidence": ["tools/ci/kt_lsl_replay.py"],
    "test_covers": "CI: the real KT-sEMG run3 (77 s, 32 channels, 2000 Hz) replayed over a real LSL "
                   "loopback into fidetype live; the NTS output is checked.",
    "limits": "A replay of a recording, not a live device. The guard never commits on 77 s (in-sample"
              " plumbing model).",
}

__all__ = ["publish_signal", "replay_kt"]


def make_outlets(name: str, n_ch: int, srate: float, modality: str, source_id: str,
                 extra: dict[str, str] | None = None, lsl_type: str | None = None) -> tuple[Any, Any]:
    """A raw-signal outlet and its marker outlet (pylsl)."""
    pl = require_pylsl()
    esid = source_id + ".markers"
    info = pl.StreamInfo(name, lsl_type or modality.upper(), n_ch, srate, "float32", source_id)
    chs = info.desc().append_child("channels")
    for i in range(n_ch):
        c = chs.append_child("channel")
        c.append_child_value("label", f"ch{i + 1}")
        c.append_child_value("unit", "file_units")
        c.append_child_value("type", (lsl_type or modality).upper())
    f = info.desc().append_child(DESC_ROOT)
    for k, v in {"role": "signal", "binding": BINDING_VERSION, "events_source_id": esid,
                 "device.modality": modality, **(extra or {})}.items():
        f.append_child_value(k, str(v))
    mi = pl.StreamInfo(name + ".markers", MARKERS_TYPE, 1, pl.IRREGULAR_RATE, "string", esid)
    mf = mi.desc().append_child(DESC_ROOT)
    for k, v in {"role": "signal_markers", "binding": BINDING_VERSION, "signal_source_id": source_id}.items():
        mf.append_child_value(k, v)
    return pl.StreamOutlet(info, 0, 360), pl.StreamOutlet(mi)


def publish_signal(signal: np.ndarray, srate: float, markers: Sequence[tuple[float, str]], name: str,
                   modality: str = "other", source_id: str | None = None, speed: float = 1.0, chunk_s: float = 0.02,
                   wait_consumers: float = 30.0, linger_s: float = 1.0, extra: dict[str, str] | None = None,
                   stop: Any = None, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Send ``signal`` (N, C) and ``markers`` ((t, string), t in seconds from sample 0) on LSL. Return stats."""
    pl = require_pylsl()
    log = log or (lambda m: None)
    x = np.asarray(signal, dtype=np.float32)
    n, c = x.shape
    sid = source_id or f"fidetype-replay-{name}"
    sig, mk = make_outlets(name, c, srate, modality, sid, extra)
    t_wait = time.monotonic() + wait_consumers
    while not sig.have_consumers() and time.monotonic() < t_wait:
        time.sleep(0.02)
    if not sig.have_consumers():
        log(f"no consumer after {wait_consumers} s; sending anyway")
    # give the consumer time to open the marker inlet too
    t_wait = time.monotonic() + min(5.0, wait_consumers)
    while not mk.have_consumers() and time.monotonic() < t_wait:
        time.sleep(0.02)
    log(f"sending {n / srate:.1f} s of {c}-channel signal at {srate:g} Hz on '{name}' ({len(markers)} markers)")
    step = max(1, int(round(chunk_s * srate)))
    base = pl.local_clock()
    w0 = time.monotonic()
    mlist = sorted(markers)
    mi = 0
    i = 0
    while i < n:
        if stop is not None and stop.is_set():
            break
        j = min(n, i + step)
        if speed > 0:
            due = w0 + (j / srate) / speed
            d = due - time.monotonic()
            if d > 0:
                time.sleep(d)
        ts = (base + np.arange(i, j) / srate).tolist()
        sig.push_chunk(x[i:j], ts)
        t_hi = j / srate
        while mi < len(mlist) and mlist[mi][0] < t_hi:
            mk.push_sample([mlist[mi][1]], base + mlist[mi][0])
            mi += 1
        i = j
    while mi < len(mlist):
        mk.push_sample([mlist[mi][1]], base + mlist[mi][0])
        mi += 1
    time.sleep(linger_s)
    wall = time.monotonic() - w0
    del sig, mk
    return {"samples": int(i), "markers": len(mlist), "wall_s": round(wall, 3)}


def replay_kt(data: str | PathLike[str], run: str = "run28", start_s: float = 0.0, duration_s: float | None = None,
              speed: float = 1.0, name: str = "fidetype.replay.kt-semg", wait_consumers: float = 30.0,
              truth_path: str | PathLike[str] | None = None,
              log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Publish one KT-sEMG run (module docstring). ``truth_path``: write the sent segments' texts (local only)."""
    require_pylsl()
    from fidetype.adapters import kt_semg as K
    from fidetype.live.build import _kt_runs, kt_markers, kt_run_events, kt_segments, kt_text

    log = log or (lambda m: None)
    runs = {r["id"]: r for rs in _kt_runs(data).values() for r in rs}
    if run not in runs:
        raise ValueError(f"unknown run {run!r} (have {sorted(runs)})")
    r = runs[run]
    rec = K.read_emg_csv(r["csv"])
    ev = kt_run_events(r["csv"], r["keys"], r["ts"], rec.n_samples)
    fs = K.SAMPLE_RATE_HZ
    i0 = int(round(start_s * fs))
    i1 = rec.n_samples if duration_s is None else min(rec.n_samples, i0 + int(round(duration_s * fs)))
    segs = [(a, b) for a, b in kt_segments(ev) if ev[a].t - K.WINDOW_PRE_S >= start_s and
            ev[b - 1].t + 1.0 <= i1 / fs]
    mk = [(t - start_s, m) for t, m in kt_markers(ev, segs)]
    if truth_path:
        Path(truth_path).write_text(json.dumps({"run": run, "segments": [
            {"t_end": round(ev[b - 1].t + 0.5 - start_s, 4), "keys": b - a, "text": kt_text(ev[a:b])}
            for a, b in segs]}, indent=1) + "\n", encoding="utf-8")
    sig = rec.emg[i0:i1]
    del rec
    log(f"{run}: {len(segs)} segments in [{start_s:g}, {i1 / fs:.1f}] s")
    st = publish_signal(sig, fs, mk, name, modality="emg", speed=speed, wait_consumers=wait_consumers,
                        extra={"fidetype.replay": f"kt-semg {run} (CC BY 4.0, Nokia)"}, log=log)
    st["segments"] = len(segs)
    return st
