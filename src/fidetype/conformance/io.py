"""Raw readers and writers for the conformance suite.

The reference class :class:`fidetype.streams.spec.NeuralTextStream`
validates in its constructor and stops at the first error. A conformance
check must see *every* problem, so this module reads a stream into a
:class:`RawStream` **without** validation. The checks in
:mod:`fidetype.conformance.checks` then test each rule on its own.

Supported inputs:

- an NPZ file (spec section 6.1),
- a JSON Lines file (spec section 6.2), with dense or sparse frames and
  the Development event kinds,
- an in-memory :class:`NeuralTextStream` (for adapters).

The module also holds the **reference consumer** (:func:`load_stream`): it
reads a file, applies the rules of the spec and either returns the stream
or raises :class:`StreamRejected`.
"""

from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

import numpy as np

from fidetype.streams.spec import NPZ_NO_BLANK, NeuralTextStream

#: NPZ keys that spec 6.1 marks "Required: Yes".
NPZ_REQUIRED = ("version", "log_probs", "frame_times", "vocab", "blank_id", "source", "meta_json")
#: NPZ keys that spec 6.1 defines (required and optional).
NPZ_KNOWN = NPZ_REQUIRED + ("vocab_type", "frame_period", "latency")
#: Header fields that spec 6.2 rule 1 requires in a JSON Lines header.
JSONL_HEADER_REQUIRED = ("spec_version", "vocab", "vocab_type", "blank_id")
#: Header fields that the spec defines (3.1, 3.2, 3.4, 3.8).
HEADER_KNOWN = (
    "type", "spec_version", "vocab", "vocab_type", "blank_id", "source", "meta",
    "frame_period", "latency", "vocab_id", "vocab_version", "clock_domain",
)
#: Event kinds of spec 3.0 (JSON Lines ``type`` values), plus ``end``.
EVENT_TYPES = ("frame", "decision", "hypothesis", "pointer", "signal_quality", "end")

_MISSING = object()


class StreamRejected(ValueError):
    """The reference consumer rejects the stream. ``clause`` cites the spec."""

    def __init__(self, message: str, clause: str = "") -> None:
        super().__init__(message)
        self.clause = clause


@dataclass
class Issue:
    """A problem found while reading (before the checks run)."""

    check_id: str
    clause: str
    message: str


@dataclass
class RawStream:
    """A stream as read from its serialisation, not validated.

    ``header`` holds the header fields that were present (a missing field
    is absent from the dict). ``log_probs`` is a float64 array of shape
    (T, V) or None if the frames could not be stacked. ``events`` holds
    the non-frame JSON Lines events in file order.
    """

    format: str  # "npz", "jsonl" or "object"
    path: str | None = None
    header: dict[str, Any] = field(default_factory=dict)
    log_probs: np.ndarray | None = None
    frame_times: np.ndarray | None = None
    issues: list[Issue] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    sparse_frames: list[dict[str, Any]] = field(default_factory=list)
    npz_keys: list[str] = field(default_factory=list)
    npz_dtypes: dict[str, str] = field(default_factory=dict)
    unknown_keys: list[str] = field(default_factory=list)
    ignored_events: int = 0
    has_end: bool = False
    lines_after_end: int = 0
    parsed: bool = True

    @property
    def meta(self) -> Any:
        return self.header.get("meta", {})

    def get(self, key: str, default: Any = None) -> Any:
        return self.header.get(key, default)


# --- readers ------------------------------------------------------------------


def from_stream(stream: NeuralTextStream) -> RawStream:
    """Wrap an in-memory stream (it is valid by construction)."""
    header: dict[str, Any] = {
        "spec_version": stream.version,
        "vocab": list(stream.vocab),
        "vocab_type": stream.vocab_type,
        "blank_id": stream.blank_id,
        "source": stream.source,
        "meta": stream.meta,
    }
    if stream.frame_period is not None:
        header["frame_period"] = stream.frame_period
    if stream.latency is not None:
        header["latency"] = stream.latency
    return RawStream(
        format="object",
        header=header,
        log_probs=np.asarray(stream.log_probs, dtype=np.float64),
        frame_times=np.asarray(stream.frame_times, dtype=np.float64),
        npz_dtypes={"log_probs": str(stream.log_probs.dtype), "frame_times": str(stream.frame_times.dtype)},
    )


def _scalar(a: np.ndarray) -> Any:
    if a.shape != ():
        return a.tolist()
    return a.item()


def read_npz(path: str | PathLike[str]) -> RawStream:
    """Read an NPZ stream (spec 6.1) without validation."""
    raw = RawStream(format="npz", path=str(path))
    try:
        z = np.load(path, allow_pickle=False)
    except (OSError, ValueError, zipfile.BadZipFile, EOFError) as e:
        raw.parsed = False
        raw.issues.append(Issue("NTS-PARSE", "6.1", f"cannot load the NPZ with allow_pickle=False: {e}"))
        return raw
    with z:
        raw.npz_keys = list(z.files)
        arrays: dict[str, np.ndarray] = {}
        for k in z.files:
            try:
                arrays[k] = z[k]
            except ValueError as e:  # object arrays need pickle
                raw.issues.append(Issue("NTS-PARSE", "6.1", f"key {k!r} needs pickle to load: {e}"))
                raw.parsed = False
        raw.npz_dtypes = {k: str(a.dtype) for k, a in arrays.items()}
        raw.unknown_keys = [k for k in z.files if k not in NPZ_KNOWN]
    missing = [k for k in NPZ_REQUIRED if k not in arrays]
    if missing:
        raw.issues.append(Issue("NTS-NPZ-KEYS", "6.1", f"required NPZ keys are missing: {missing}"))
    h = raw.header
    if "version" in arrays:
        h["spec_version"] = _scalar(arrays["version"])
    if "vocab" in arrays:
        v = arrays["vocab"]
        h["vocab"] = v.tolist() if v.ndim == 1 else _scalar(v)
    # 6.1: a reader MUST use "char" if vocab_type is absent.
    h["vocab_type"] = _scalar(arrays["vocab_type"]) if "vocab_type" in arrays else "char"
    if "vocab_type" not in arrays:
        h["_vocab_type_defaulted"] = True
    if "blank_id" in arrays:
        b = arrays["blank_id"]
        if b.shape == () and np.issubdtype(b.dtype, np.integer):
            h["blank_id"] = None if int(b) == NPZ_NO_BLANK else int(b)
        else:
            h["blank_id"] = _scalar(b)
    if "source" in arrays:
        h["source"] = _scalar(arrays["source"])
    if "meta_json" in arrays:
        txt = _scalar(arrays["meta_json"])
        try:
            h["meta"] = json.loads(str(txt), parse_constant=_reject_constant)
        except ValueError as e:
            raw.issues.append(Issue("NTS-META-JSON", "4.1", f"meta_json is not valid JSON: {e}"))
            h["meta"] = _MISSING_META
    for k in ("frame_period", "latency"):
        if k in arrays:
            h[k] = _scalar(arrays[k])
    if "log_probs" in arrays:
        lp = arrays["log_probs"]
        if np.issubdtype(lp.dtype, np.number):
            raw.log_probs = lp.astype(np.float64)
        else:
            raw.issues.append(Issue("NTS-LP-2D", "3.1", f"log_probs has a non-numeric dtype {lp.dtype}"))
    if "frame_times" in arrays:
        ft = arrays["frame_times"]
        if np.issubdtype(ft.dtype, np.number):
            raw.frame_times = ft.astype(np.float64)
        else:
            raw.issues.append(Issue("NTS-FT-SHAPE", "3.1", f"frame_times has a non-numeric dtype {ft.dtype}"))
    return raw


class _MissingMeta:
    """Marker: meta was present but not parseable."""

    def __repr__(self) -> str:
        return "<unparseable meta>"


_MISSING_META = _MissingMeta()


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not a JSON value")


def _lp_value(x: Any) -> float:
    """One JSON log-probability: a number, or null for -inf (6.2 rule 3)."""
    if x is None:
        return -math.inf
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{x!r} is not a number or null")
    return float(x)


def read_jsonl(path: str | PathLike[str]) -> RawStream:
    """Read a JSON Lines stream (spec 6.2) without validation.

    Unknown event types are counted and ignored (6.2 rule 5). Sparse
    frames are kept in ``sparse_frames`` and also expanded to dense rows
    as spec 3.3 says (rest mass spread uniformly).
    """
    raw = RawStream(format="jsonl", path=str(path))
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raw.parsed = False
        raw.issues.append(Issue("NTS-PARSE", "6.2", f"cannot read the file as UTF-8: {e}"))
        return raw
    objs: list[tuple[int, Any]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue  # blank lines: see the spec ambiguity list (A4)
        try:
            objs.append((n, json.loads(line, parse_constant=_reject_constant)))
        except ValueError as e:
            raw.parsed = False
            raw.issues.append(Issue("NTS-PARSE", "6.2", f"line {n} is not a JSON value: {e}"))
    if not raw.parsed:
        return raw
    if not objs:
        raw.parsed = False
        raw.issues.append(Issue("NTS-JSONL-HEADER", "6.2.1", "the file has no header line"))
        return raw
    n0, head = objs[0]
    if not isinstance(head, dict) or head.get("type") != "header":
        raw.parsed = False
        raw.issues.append(Issue("NTS-JSONL-HEADER", "6.2.1", 'line 1 must be an object with "type": "header"'))
        return raw
    missing = [k for k in JSONL_HEADER_REQUIRED if k not in head]
    if missing:
        raw.issues.append(Issue("NTS-JSONL-HEADER", "6.2.1", f"the header lacks required fields {missing}"))
    raw.header = {k: v for k, v in head.items() if k != "type"}
    raw.unknown_keys = [k for k in head if k not in HEADER_KNOWN]
    if "meta" not in raw.header:
        raw.header["meta"] = {}
        raw.header["_meta_defaulted"] = True
    vocab = raw.header.get("vocab")
    V = len(vocab) if isinstance(vocab, list) else None
    rows: list[np.ndarray] = []
    times: list[float] = []
    stackable = True
    for n, obj in objs[1:]:
        if raw.has_end:
            raw.lines_after_end += 1
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
            raw.issues.append(Issue("NTS-JSONL-FRAME", "6.2", f"line {n} is not an event object with a string type"))
            stackable = False
            continue
        typ = obj["type"]
        if typ == "end":
            raw.has_end = True
            continue
        if typ == "header":
            raw.issues.append(Issue("NTS-JSONL-HEADER", "6.2.1", f"line {n}: a second header"))
            continue
        if typ not in EVENT_TYPES:
            raw.ignored_events += 1  # 6.2 rule 5
            continue
        if typ != "frame":
            obj = dict(obj)
            obj["_line"] = n
            raw.events.append(obj)
            continue
        t = obj.get("t", _MISSING)
        if isinstance(t, bool) or not isinstance(t, (int, float)):
            raw.issues.append(Issue("NTS-JSONL-FRAME", "6.2.2", f"line {n}: frame without a numeric t"))
            stackable = False
            continue
        try:
            if "log_probs" in obj:
                lp = obj["log_probs"]
                if not isinstance(lp, list):
                    raise TypeError("log_probs is not a list")
                row = np.array([_lp_value(x) for x in lp], dtype=np.float64)
            elif "top_ids" in obj or "top_log_probs" in obj:
                row = _sparse_row(obj, V, n, raw)
            else:
                raise TypeError("frame has neither log_probs nor top_ids/top_log_probs")
        except (TypeError, ValueError) as e:
            raw.issues.append(Issue("NTS-JSONL-FRAME", "6.2.2", f"line {n}: {e}"))
            stackable = False
            continue
        if row is None:
            stackable = False
            continue
        rows.append(row)
        times.append(float(t))
    if stackable:
        if not rows:
            raw.log_probs = np.zeros((0, V or 0), dtype=np.float64)
        elif len({r.shape[0] for r in rows}) == 1:
            raw.log_probs = np.stack(rows)
        else:
            raw.issues.append(Issue("NTS-V-MATCH", "5.1.2", "frames have different numbers of log-probabilities"))
        raw.frame_times = np.array(times, dtype=np.float64)
    return raw


def _sparse_row(obj: dict, V: int | None, n: int, raw: RawStream) -> np.ndarray | None:
    ids = obj.get("top_ids")
    vals = obj.get("top_log_probs")
    rest = obj.get("rest_log_prob", None)
    info = {"_line": n, "top_ids": ids, "top_log_probs": vals, "rest_log_prob": rest}
    raw.sparse_frames.append(info)
    if not isinstance(ids, list) or not isinstance(vals, list) or len(ids) != len(vals):
        raise ValueError("sparse frame needs top_ids and top_log_probs lists of the same length")
    if V is None:
        return None
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < V for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("top_ids must be unique integers in 0..V-1")
    lv = [_lp_value(x) for x in vals]
    r = _lp_value(rest)
    row = np.full(V, -math.inf)
    k = len(ids)
    if V > k and r > -math.inf:
        row[:] = r - math.log(V - k)  # 3.3: spread the rest mass uniformly
    for i, x in zip(ids, lv):
        row[i] = x
    info["_rest"] = r
    info["_vals"] = lv
    return row


def read_raw(path: str | PathLike[str]) -> RawStream:
    """Read a file by its extension: ``.npz`` or ``.jsonl`` / ``.ndjson``."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".npz":
        return read_npz(p)
    if suf in (".jsonl", ".ndjson", ".json"):
        return read_jsonl(p)
    raise ValueError(f"unknown stream file type {p.suffix!r} (use .npz or .jsonl)")


# --- writers ------------------------------------------------------------------


def _json_lp(row: np.ndarray, decimals: int = 6) -> list[float | None]:
    return [None if v == -math.inf else round(float(v), decimals) for v in row]


def write_jsonl(
    stream: NeuralTextStream,
    path: str | PathLike[str],
    events: list[dict[str, Any]] | None = None,
    end: bool = True,
    extra_header: dict[str, Any] | None = None,
) -> None:
    """Write the frame core of ``stream`` as JSON Lines (spec 6.2).

    ``events`` are written after the frames (each a dict with ``type``).
    ``-inf`` becomes ``null`` (6.2 rule 3).
    """
    head: dict[str, Any] = {
        "type": "header",
        "spec_version": stream.version,
        "vocab": list(stream.vocab),
        "vocab_type": stream.vocab_type,
        "blank_id": stream.blank_id,
        "source": stream.source,
    }
    if stream.frame_period is not None:
        head["frame_period"] = stream.frame_period
    if stream.latency is not None:
        head["latency"] = stream.latency
    head.update(extra_header or {})
    head["meta"] = stream.meta
    lines = [json.dumps(head, ensure_ascii=False, allow_nan=False)]
    for t, row in zip(stream.frame_times, stream.log_probs):
        lines.append(json.dumps({"type": "frame", "t": round(float(t), 9), "log_probs": _json_lp(row)}, allow_nan=False))
    for e in events or []:
        lines.append(json.dumps(e, ensure_ascii=False, allow_nan=False))
    if end:
        lines.append(json.dumps({"type": "end"}))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- reference consumer ------------------------------------------------------------


@dataclass
class ConsumedStream:
    """What the reference consumer returns for an accepted file."""

    stream: NeuralTextStream
    events: list[dict[str, Any]]
    ignored_events: int
    unknown_keys: list[str]
    vocab_type_defaulted: bool


def load_stream(path: str | PathLike[str]) -> ConsumedStream:
    """The reference consumer: read a stream file and accept or reject it.

    It accepts a file when every Core-level MUST check passes (see
    :mod:`fidetype.conformance.checks`). Otherwise it raises
    :class:`StreamRejected` with the first failing clause.
    """
    from fidetype.conformance.checks import run_checks  # local import: no cycle at import time

    raw = read_raw(path)
    results = run_checks(raw)
    for r in results:
        if r.status == "fail" and r.blocks("core"):
            raise StreamRejected(f"[{r.check_id}, spec {r.clause}] {r.message}", r.clause)
    h = raw.header
    stream = NeuralTextStream(
        log_probs=raw.log_probs if raw.log_probs is not None else np.zeros((0, len(h["vocab"]))),
        frame_times=raw.frame_times if raw.frame_times is not None else np.zeros(0),
        vocab=list(h["vocab"]),
        blank_id=h.get("blank_id"),
        source=h.get("source", "unknown"),
        meta=dict(h.get("meta") or {}),
        version=h["spec_version"],
        vocab_type=h.get("vocab_type", "char"),
        frame_period=h.get("frame_period"),
        latency=h.get("latency"),
    )
    events = [{k: v for k, v in e.items() if k != "_line"} for e in raw.events]
    return ConsumedStream(stream, events, raw.ignored_events, raw.unknown_keys, bool(h.get("_vocab_type_defaulted")))
