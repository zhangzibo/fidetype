"""The NeuralTextStream format (version 0.1).

Every decoder in this project gives its output as a NeuralTextStream.
The trust layer reads only this format. Thus it does not depend on the
decoder type (MEG, EEG, EMG or a simulator).

The normative specification is ``spec/neuraltextstream-v0.1.md`` in the
repository. This module is the reference implementation and validator.

Format for decoder authors
--------------------------
A stream is a sequence of T frames. Each frame has a time and a
probability distribution over a character vocabulary of V tokens. The
format is the output of a CTC decoder (Graves et al. 2006), before any
decoding step.

``log_probs``
    Array of shape (T, V), dtype float32. Row t holds the natural-log
    probabilities of the V tokens at frame t. Each row must be a
    normalised distribution: ``logsumexp(row) == 0`` (tolerance 1e-3).
    ``-inf`` is allowed. NaN and ``+inf`` are not allowed. If your model
    gives logits, apply ``log_softmax`` first.
``frame_times``
    Array of shape (T,), dtype float64. The time of each frame in
    seconds. The values must increase strictly. The zero point is your
    choice (for example, the start of the trial).
``vocab``
    List of V strings. ``vocab[i]`` is the token of column i. The
    default vocabulary is :data:`fidetype.streams.vocab.VOCAB`
    (blank, ``a``-``z``, space), as in Brain2Qwerty.
``vocab_type``
    The kind of token in ``vocab``: one of ``"char"``, ``"key"``,
    ``"word"``, ``"phoneme"``, ``"command"`` or ``"other"``. The default
    is ``"char"``.
``blank_id``
    Index of the CTC blank token in ``vocab``. ``None`` if the decoder
    is not a CTC decoder.
``frame_period``, ``latency``
    Optional. The nominal frame period and the algorithmic lookahead of
    the decoder, both in seconds. ``None`` if not given.
``source``
    Short name of the producer, for example ``"simulator"`` or
    ``"spanishbcbl-replay"``.
``meta``
    Free dictionary for extra data (subject id, model name, settings).
    It must be JSON-serialisable to save it with :meth:`to_npz`.

The probabilities must be the decoder's honest output. Do not sharpen or
smooth them for display. The trust layer calibrates them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from os import PathLike
from typing import Any

import numpy as np

SPEC_VERSION = "0.1"
NORM_TOL = 1e-3


def _logsumexp_rows(x: np.ndarray) -> np.ndarray:
    """Return the log-sum-exp of each row. Rows of only -inf give -inf."""
    x64 = x.astype(np.float64)
    m = np.max(x64, axis=1, keepdims=True)
    m_safe = np.where(np.isfinite(m), m, 0.0)
    with np.errstate(divide="ignore"):
        out = np.log(np.sum(np.exp(x64 - m_safe), axis=1)) + m_safe[:, 0]
    return out


def _reject_json_constant(name: str) -> Any:
    """``json.loads`` hook: NaN and Infinity are not JSON values (spec 4.1)."""
    raise ValueError(f"meta_json holds {name}, which is not a JSON value (spec 4.1)")


#: Allowed values of :attr:`NeuralTextStream.vocab_type`.
VOCAB_TYPES = ("char", "key", "word", "phoneme", "command", "other")

#: Value of the ``blank_id`` key in an NPZ file when ``blank_id`` is None.
NPZ_NO_BLANK = -1


@dataclass
class NeuralTextStream:
    """Per-frame CTC log-probabilities from one decoder (spec v0.1).

    See the module docstring for the full format. The constructor calls
    :meth:`validate`. It raises ``ValueError`` if the data is not valid.
    """

    log_probs: np.ndarray
    frame_times: np.ndarray
    vocab: list[str]
    blank_id: int | None = 0
    source: str = "unknown"
    meta: dict[str, Any] = field(default_factory=dict)
    version: str = SPEC_VERSION
    vocab_type: str = "char"
    frame_period: float | None = None
    latency: float | None = None

    def __post_init__(self) -> None:
        self.log_probs = np.asarray(self.log_probs, dtype=np.float32)
        self.frame_times = np.asarray(self.frame_times, dtype=np.float64)
        self.vocab = list(self.vocab)
        if self.blank_id is not None:
            self.blank_id = int(self.blank_id)
        if self.frame_period is not None:
            self.frame_period = float(self.frame_period)
        if self.latency is not None:
            self.latency = float(self.latency)
        self.validate()

    # --- properties -------------------------------------------------------

    @property
    def n_frames(self) -> int:
        return int(self.log_probs.shape[0])

    @property
    def spec_version(self) -> str:
        """Return the spec version. This is the same value as ``version``."""
        return self.version

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    @property
    def probs(self) -> np.ndarray:
        """Return the probabilities (exp of ``log_probs``), shape (T, V)."""
        return np.exp(self.log_probs)

    # --- checks -----------------------------------------------------------

    def validate(self) -> None:
        """Check shapes, normalisation, times and fields.

        Raises ``ValueError`` with a clear message at the first problem.
        """
        if self.version != SPEC_VERSION:
            raise ValueError(f"version must be {SPEC_VERSION!r}, not {self.version!r}")
        lp, ft = self.log_probs, self.frame_times
        if lp.ndim != 2:
            raise ValueError(f"log_probs must be 2-D (T, V), got shape {lp.shape}")
        T, V = lp.shape
        if V != len(self.vocab):
            raise ValueError(f"log_probs has {V} columns but vocab has {len(self.vocab)} tokens")
        if len(set(self.vocab)) != len(self.vocab):
            raise ValueError("vocab tokens must be unique")
        if not all(isinstance(t, str) for t in self.vocab):
            raise ValueError("vocab tokens must be strings")
        if self.vocab_type not in VOCAB_TYPES:
            raise ValueError(f"vocab_type must be one of {VOCAB_TYPES}, not {self.vocab_type!r}")
        if self.blank_id is not None and not 0 <= self.blank_id < V:
            raise ValueError(f"blank_id {self.blank_id} is out of range 0..{V - 1}")
        if self.frame_period is not None and not (np.isfinite(self.frame_period) and self.frame_period > 0):
            raise ValueError(f"frame_period must be a positive finite number, not {self.frame_period}")
        if self.latency is not None and not (np.isfinite(self.latency) and self.latency >= 0):
            raise ValueError(f"latency must be a finite number >= 0, not {self.latency}")
        if ft.ndim != 1 or ft.shape[0] != T:
            raise ValueError(f"frame_times must have shape ({T},), got {ft.shape}")
        if np.isnan(lp).any() or np.isposinf(lp).any():
            raise ValueError("log_probs must not contain NaN or +inf")
        if not np.all(np.isfinite(ft)):
            raise ValueError("frame_times must be finite")
        if T > 1 and not np.all(np.diff(ft) > 0):
            raise ValueError("frame_times must increase strictly")
        if T > 0:
            lse = _logsumexp_rows(lp)
            bad = np.abs(lse) > NORM_TOL
            if bad.any():
                t = int(np.argmax(bad))
                raise ValueError(
                    f"log_probs rows must log-sum-exp to 0 (tol {NORM_TOL}); "
                    f"frame {t} gives {lse[t]:.4g}"
                )
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("source must be a non-empty string")
        if not isinstance(self.meta, dict):
            raise ValueError("meta must be a dict")

    # --- file I/O ---------------------------------------------------------

    def to_npz(self, path: str | PathLike[str]) -> None:
        """Save the stream to a compressed ``.npz`` file.

        ``meta`` is stored as a JSON string (NaN and infinity are refused,
        spec 4.1). The file loads without
        pickle. A ``blank_id`` of None is stored as ``-1``. The keys
        ``frame_period`` and ``latency`` are written only if they are set.
        """
        arrays: dict[str, np.ndarray] = dict(
            version=np.array(self.version),
            log_probs=self.log_probs,
            frame_times=self.frame_times,
            vocab=np.array(self.vocab, dtype=np.str_),
            vocab_type=np.array(self.vocab_type),
            blank_id=np.array(NPZ_NO_BLANK if self.blank_id is None else self.blank_id, dtype=np.int64),
            source=np.array(self.source),
            meta_json=np.array(json.dumps(self.meta, allow_nan=False)),
        )
        if self.frame_period is not None:
            arrays["frame_period"] = np.array(self.frame_period, dtype=np.float64)
        if self.latency is not None:
            arrays["latency"] = np.array(self.latency, dtype=np.float64)
        np.savez_compressed(path, **arrays)

    @classmethod
    def from_npz(cls, path: str | PathLike[str]) -> "NeuralTextStream":
        """Load a stream that :meth:`to_npz` saved. Validates it.

        Files without the optional keys (``vocab_type``, ``frame_period``,
        ``latency``) load with the default values.
        """
        with np.load(path, allow_pickle=False) as z:
            blank_id = int(z["blank_id"])
            return cls(
                log_probs=z["log_probs"],
                frame_times=z["frame_times"],
                vocab=[str(t) for t in z["vocab"]],
                blank_id=None if blank_id == NPZ_NO_BLANK else blank_id,
                source=str(z["source"]),
                meta=json.loads(str(z["meta_json"]), parse_constant=_reject_json_constant),
                version=str(z["version"]),
                vocab_type=str(z["vocab_type"]) if "vocab_type" in z.files else "char",
                frame_period=float(z["frame_period"]) if "frame_period" in z.files else None,
                latency=float(z["latency"]) if "latency" in z.files else None,
            )
