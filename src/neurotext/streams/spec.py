"""The NeuralTextStream format (version 0.1).

Every decoder in this project gives its output as a NeuralTextStream.
The trust layer reads only this format. Thus it does not depend on the
decoder type (MEG, EEG, EMG or a simulator).

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
    default vocabulary is :data:`neurotext.streams.vocab.VOCAB`
    (blank, ``a``-``z``, space), as in Brain2Qwerty.
``blank_id``
    Index of the CTC blank token in ``vocab``.
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


@dataclass
class NeuralTextStream:
    """Per-frame CTC log-probabilities from one decoder (spec v0.1).

    See the module docstring for the full format. The constructor calls
    :meth:`validate`. It raises ``ValueError`` if the data is not valid.
    """

    log_probs: np.ndarray
    frame_times: np.ndarray
    vocab: list[str]
    blank_id: int = 0
    source: str = "unknown"
    meta: dict[str, Any] = field(default_factory=dict)
    version: str = SPEC_VERSION

    def __post_init__(self) -> None:
        self.log_probs = np.asarray(self.log_probs, dtype=np.float32)
        self.frame_times = np.asarray(self.frame_times, dtype=np.float64)
        self.vocab = list(self.vocab)
        self.blank_id = int(self.blank_id)
        self.validate()

    # --- properties -------------------------------------------------------

    @property
    def n_frames(self) -> int:
        return int(self.log_probs.shape[0])

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
        if not 0 <= self.blank_id < V:
            raise ValueError(f"blank_id {self.blank_id} is out of range 0..{V - 1}")
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

        ``meta`` is stored as a JSON string. The file loads without
        pickle.
        """
        np.savez_compressed(
            path,
            version=np.array(self.version),
            log_probs=self.log_probs,
            frame_times=self.frame_times,
            vocab=np.array(self.vocab, dtype=np.str_),
            blank_id=np.array(self.blank_id, dtype=np.int64),
            source=np.array(self.source),
            meta_json=np.array(json.dumps(self.meta)),
        )

    @classmethod
    def from_npz(cls, path: str | PathLike[str]) -> "NeuralTextStream":
        """Load a stream that :meth:`to_npz` saved. Validates it."""
        with np.load(path, allow_pickle=False) as z:
            return cls(
                log_probs=z["log_probs"],
                frame_times=z["frame_times"],
                vocab=[str(t) for t in z["vocab"]],
                blank_id=int(z["blank_id"]),
                source=str(z["source"]),
                meta=json.loads(str(z["meta_json"])),
                version=str(z["version"]),
            )
