"""Emit NeuralTextStream from your decoder (SDK, M7-01).

Two ways to produce a stream:

- :func:`make_stream` builds an in-memory :class:`NeuralTextStream` from a
  ``(T, V)`` matrix of per-frame CTC log-probabilities (for example the
  output of a CTC decoder after ``log_softmax``). Save it with
  :func:`write_stream` (``.jsonl`` or ``.npz``).
- :class:`StreamWriter` writes JSON Lines (spec v0.1, section 6.2) one
  event at a time: a header, then ``frame`` / ``hypothesis`` /
  ``signal_quality`` / ``segment_end`` events, then ``end``. Use it for a
  live decoder. Every event is checked before it is written.

:func:`stream_meta` builds the ``meta`` keys (spec section 4) that the
conformance levels ``trust-ready`` and ``provenance`` ask for.

::

    import fidetype

    meta = fidetype.stream_meta(modality="eeg", decoder_name="my-ctc", decoder_version="1.2")
    with fidetype.StreamWriter("s.jsonl", vocab=fidetype.VOCAB, source="my-ctc", meta=meta,
                               frame_period=0.04) as w:
        for t, row in my_decoder():          # row: V log-probabilities
            w.frame(t, row)
"""

from __future__ import annotations

import json
import math
import uuid
from os import PathLike
from pathlib import Path
from typing import IO, Any, Iterable, Mapping, Sequence

import numpy as np

from fidetype.streams.spec import NORM_TOL, SPEC_VERSION, VOCAB_TYPES, NeuralTextStream
from fidetype.streams.vocab import VOCAB

__all__ = ["StreamWriter", "make_stream", "stream_meta", "write_stream"]

SCORE_SEMANTICS = ("calibrated_prob", "uncalibrated_prob", "power", "strength", "none")
MODALITIES = ("meg", "eeg", "emg", "ecog", "intracortical", "fnirs", "other")


def stream_meta(
    *,
    modality: str,
    decoder_name: str,
    decoder_version: str,
    causal: bool = True,
    lookahead_s: float | None = None,
    language: str = "en",
    calibration_applied: bool = False,
    calibration_method: str = "none",
    derived: bool = True,
    lm_name: str = "none",
    weights_sha256: str | None = None,
    stream_id: str | None = None,
    adapter_name: str | None = None,
    adapter_version: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the ``meta`` dict of a stream (spec section 4 keys).

    The required arguments give the ``trust-ready`` level. Add
    ``weights_sha256`` (SHA-256 of the decoder weights), ``stream_id`` (or
    ``"auto"`` for a random UUID) and an adapter name and version for the
    ``provenance`` level. Put **no** text, labels or participant names in
    ``meta`` (spec 5.3 and 5.4).
    """
    if not decoder_name or not decoder_version:
        raise ValueError("decoder_name and decoder_version must not be empty")
    m: dict[str, Any] = {
        "device.modality": modality,
        "decoder.name": decoder_name,
        "decoder.version": str(decoder_version),
        "decoder.causal": bool(causal),
        "decoder.calibration_method": calibration_method,
        "calibration.applied": bool(calibration_applied),
        "lm.name": lm_name,
        "language": language,
        "data.derived": bool(derived),
    }
    if lookahead_s is not None:
        m["decoder.lookahead_s"] = float(lookahead_s)
    if weights_sha256 is not None:
        m["decoder.weights_sha256"] = weights_sha256
    if stream_id == "auto":
        stream_id = str(uuid.uuid4())
    if stream_id is not None:
        m["stream.id"] = stream_id
    if adapter_name is not None:
        m["adapter.name"] = adapter_name
        m["adapter.version"] = str(adapter_version or "0")
    if extra:
        m.update(extra)
    return m


def make_stream(
    log_probs: Any,
    *,
    vocab: Sequence[str] = VOCAB,
    frame_period: float = 0.04,
    t0: float = 0.0,
    frame_times: Any = None,
    blank_id: int | None = 0,
    source: str = "unknown",
    meta: Mapping[str, Any] | None = None,
    vocab_type: str = "char",
    latency: float | None = None,
    normalize: bool = False,
) -> NeuralTextStream:
    """Build a :class:`NeuralTextStream` from a ``(T, V)`` log-probability matrix.

    ``frame_times`` defaults to ``t0 + frame_period * arange(T)``. With
    ``normalize=True`` each row goes through ``log_softmax`` first (use it
    for raw logits). The result is validated (spec section 2).
    """
    lp = np.asarray(log_probs, dtype=np.float64)
    if lp.ndim != 2:
        raise ValueError(f"log_probs must be 2-D (T, V), got shape {lp.shape}")
    if normalize:
        m = np.max(lp, axis=1, keepdims=True)
        lp = lp - m - np.log(np.sum(np.exp(lp - m), axis=1, keepdims=True))
    if frame_times is None:
        frame_times = t0 + frame_period * np.arange(lp.shape[0])
    return NeuralTextStream(
        log_probs=lp, frame_times=np.asarray(frame_times, dtype=np.float64), vocab=list(vocab),
        blank_id=blank_id, source=source, meta=dict(meta or {}), vocab_type=vocab_type,
        frame_period=frame_period, latency=latency,
    )


def write_stream(stream: NeuralTextStream, path: str | PathLike[str]) -> Path:
    """Save a stream as ``.jsonl`` (spec 6.2) or ``.npz`` (spec 6.1), by file extension."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".npz":
        stream.to_npz(p)
    elif suf in (".jsonl", ".ndjson"):
        from fidetype.conformance.io import write_jsonl

        write_jsonl(stream, p)
    else:
        raise ValueError(f"unknown stream file type {p.suffix!r} (use .jsonl or .npz)")
    return p


def _num(x: Any, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)):
        raise ValueError(f"{name} must be a number")
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite")
    return v


class StreamWriter:
    """Write NeuralTextStream JSON Lines one event at a time (spec 6.2).

    The header is written at once. Each method checks its event, writes
    one line and (with ``flush=True``) flushes it, so a live consumer can
    read the file or pipe as it grows. Use it as a context manager: the
    ``end`` event is written on a normal exit, not after an exception.

    ``target`` is a path or an open text file (for example ``sys.stdout``
    or a socket file).
    """

    def __init__(
        self,
        target: str | PathLike[str] | IO[str],
        *,
        vocab: Sequence[str] = VOCAB,
        source: str,
        vocab_type: str = "char",
        blank_id: int | None = 0,
        frame_period: float | None = None,
        latency: float | None = None,
        meta: Mapping[str, Any] | None = None,
        flush: bool = True,
    ) -> None:
        vocab = list(vocab)
        if not vocab or not all(isinstance(v, str) for v in vocab) or len(set(vocab)) != len(vocab):
            raise ValueError("vocab must be a non-empty list of unique strings")
        if vocab_type not in VOCAB_TYPES:
            raise ValueError(f"vocab_type must be one of {VOCAB_TYPES}")
        if blank_id is not None and not 0 <= int(blank_id) < len(vocab):
            raise ValueError("blank_id is out of range")
        if not source:
            raise ValueError("source must not be empty")
        self.vocab = vocab
        self.V = len(vocab)
        self._flush = flush
        if isinstance(target, (str, PathLike)):
            self.path: Path | None = Path(target)
            self._f: IO[str] = self.path.open("w", encoding="utf-8", newline="\n")
            self._own = True
        else:
            self.path = None
            self._f = target
            self._own = False
        self._last_t = -math.inf
        self._ids: set[str] = set()
        self._ended = False
        self.n_frames = 0
        head: dict[str, Any] = {"type": "header", "spec_version": SPEC_VERSION, "vocab": vocab,
                                "vocab_type": vocab_type, "blank_id": None if blank_id is None else int(blank_id),
                                "source": source}
        if frame_period is not None:
            head["frame_period"] = _num(frame_period, "frame_period")
        if latency is not None:
            head["latency"] = _num(latency, "latency")
        head["meta"] = dict(meta or {})
        self._write(head)

    # --- low level ------------------------------------------------------------

    def _write(self, ev: dict[str, Any]) -> None:
        if self._ended:
            raise ValueError("the stream has ended")
        self._f.write(json.dumps(ev, ensure_ascii=False, allow_nan=False) + "\n")
        if self._flush:
            self._f.flush()

    def event(self, ev: Mapping[str, Any]) -> None:
        """Write any other event (a dict with ``type``) as it is."""
        if not isinstance(ev.get("type"), str):
            raise ValueError("an event needs a string type")
        self._write(dict(ev))

    # --- events ---------------------------------------------------------------

    def frame(self, t: float, log_probs: Any = None, *, probs: Any = None, logits: Any = None) -> None:
        """Write one frame at time ``t`` (seconds).

        Give exactly one of ``log_probs`` (natural log, may contain
        ``-inf``), ``probs`` (in [0, 1]) or ``logits`` (any real numbers;
        ``log_softmax`` is applied). The row must sum to 1 within the spec
        tolerance. Times must increase strictly.
        """
        given = [x is not None for x in (log_probs, probs, logits)]
        if sum(given) != 1:
            raise ValueError("give exactly one of log_probs, probs or logits")
        if logits is not None:
            row = np.asarray(logits, dtype=np.float64)
            m = np.max(row)
            row = row - m - math.log(float(np.sum(np.exp(row - m))))
        elif probs is not None:
            pr = np.asarray(probs, dtype=np.float64)
            if np.any(pr < 0) or np.any(pr > 1 + NORM_TOL):
                raise ValueError("probs must be in [0, 1]")
            with np.errstate(divide="ignore"):
                row = np.log(pr)
        else:
            row = np.asarray(log_probs, dtype=np.float64)
        if row.shape != (self.V,):
            raise ValueError(f"a frame needs {self.V} values, got shape {row.shape}")
        if np.any(np.isnan(row)) or np.any(row == math.inf):
            raise ValueError("log-probabilities must not be NaN or +inf")
        fin = row[np.isfinite(row)]
        if fin.size == 0:
            raise ValueError("a frame needs at least one finite log-probability")
        m = float(np.max(fin))
        total = m + math.log(float(np.sum(np.exp(fin - m))))
        if abs(total) > NORM_TOL:
            raise ValueError(f"the frame does not sum to 1 (logsumexp = {total:.3g}); use logits= for raw scores")
        t = _num(t, "t")
        if t <= self._last_t:
            raise ValueError("frame times must increase strictly (spec 2)")
        self._last_t = t
        self._write({"type": "frame", "t": round(t, 9),
                     "log_probs": [None if v == -math.inf else round(float(v), 6) for v in row]})
        self.n_frames += 1

    def frames(self, times: Iterable[float], log_probs: Any) -> None:
        """Write many frames: ``times`` (T) and a ``(T, V)`` matrix."""
        lp = np.asarray(log_probs, dtype=np.float64)
        ts = list(times)
        if lp.ndim != 2 or lp.shape[0] != len(ts):
            raise ValueError("log_probs must be (T, V) with one time per row")
        for t, row in zip(ts, lp):
            self.frame(t, row)

    def hypothesis(
        self,
        nbest: Sequence[Mapping[str, Any] | tuple[str, float] | str],
        *,
        is_final: bool,
        id: str | None = None,
        revision_of: str | None = None,
        score_semantics: str = "none",
        t_start: float | None = None,
        t_end: float | None = None,
    ) -> str:
        """Write a text n-best list (spec 3.6). Return its ``id``.

        Each item is a dict (``text``, ``score`` and the optional FEP-0001
        keys ``char_confidences``, ``logp_acoustic``, ``logp_lm``), a
        ``(text, score)`` pair or a plain string (score 0). Best first.
        """
        if score_semantics not in SCORE_SEMANTICS:
            raise ValueError(f"score_semantics must be one of {SCORE_SEMANTICS}")
        items: list[dict[str, Any]] = []
        for it in nbest:
            if isinstance(it, str):
                d: dict[str, Any] = {"text": it, "score": 0.0}
            elif isinstance(it, tuple):
                d = {"text": it[0], "score": _num(it[1], "score")}
            else:
                d = dict(it)
                if not isinstance(d.get("text"), str):
                    raise ValueError("each n-best item needs a string text")
                d["score"] = _num(d.get("score", 0.0), "score")
                cc = d.get("char_confidences")
                if cc is not None:
                    cc = [float(c) for c in cc]
                    if len(cc) != len(d["text"]) or any(not 0.0 <= c <= 1.0 for c in cc):
                        raise ValueError("char_confidences needs one value in [0, 1] per character")
                    d["char_confidences"] = cc
            items.append(d)
        if not items:
            raise ValueError("nbest must not be empty")
        if id is None:
            id = f"h{len(self._ids) + 1}"
        if id in self._ids:
            raise ValueError(f"hypothesis id {id!r} is already used")
        self._ids.add(id)
        ev: dict[str, Any] = {"type": "hypothesis", "id": id, "is_final": bool(is_final),
                              "score_semantics": score_semantics, "nbest": items}
        if revision_of is not None:
            ev["revision_of"] = revision_of
        if t_start is not None:
            ev["t_start"] = _num(t_start, "t_start")
        if t_end is not None:
            ev["t_end"] = _num(t_end, "t_end")
        self._write(ev)
        return id

    def signal_quality(self, t: float, value: float, unit: str = "index") -> None:
        """Write a signal-quality event (spec 3.9). ``index`` values are in [0, 1]."""
        v = _num(value, "value")
        if unit == "index" and not 0.0 <= v <= 1.0:
            raise ValueError("an index value must be in [0, 1]")
        self._write({"type": "signal_quality", "t": _num(t, "t"), "value": v, "unit": unit})

    def segment_end(self, t: float | None = None) -> None:
        """Mark the end of an utterance (``segment_end``, proposed in FEP-0001)."""
        ev: dict[str, Any] = {"type": "segment_end"}
        if t is not None:
            ev["t"] = _num(t, "t")
        self._write(ev)

    def end(self) -> None:
        """Write the ``end`` event. Later writes raise an error."""
        if not self._ended:
            self._write({"type": "end"})
            self._ended = True

    def close(self) -> None:
        """Write ``end`` (if not written) and close a file that this writer opened."""
        try:
            self.end()
        finally:
            if self._own and not self._f.closed:
                self._f.close()

    def __enter__(self) -> "StreamWriter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self.close()
        elif self._own and not self._f.closed:
            self._f.close()

