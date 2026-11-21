"""Frozen external per-prefix scores for the drop-in guard (P5-35).

A prefix guard (P5-24) commits the longest word prefix of the top-1 text
whose score passes a threshold that Learn then Test (LTT) certifies. With
``calibrate(confidence="learned", commit_unit="prefix")`` the library fits
that score itself from its built-in prefix features.

Some decoders have better signals than the built-in features (for
example a second decoder, a language model or a wide competitor set; see
P11-16). This module lets you bring such a score, fitted elsewhere, and
certify it inside :func:`~fidetype.trust.dropin.calibrate`::

    from fidetype.trust import FrozenPrefixScore

    score = FrozenPrefixScore(my_fn, name="my-prefix-score", version="1", spec=my_model.to_dict())
    guard = ft.calibrate(xs, texts, ..., commit_unit="prefix", prefix_score=score)

Rules
-----
- ``my_fn(ctx)`` gets a :class:`PrefixContext` (the top-1 words of the
  guard, the calibrated n-best, the frame log-probabilities for logits
  input, the built-in prefix rows). It returns one score per word prefix
  (``len(ctx.words)`` numbers, higher = surer, normally in [0, 1]), or
  ``None`` (the guard does not commit this item).
- The library makes the scores monotone (running minimum), applies the
  commit gate, and certifies the threshold by LTT on the LTT items only,
  with the loss "wrong prefix commit". The guarantee is the P5-24 one.
- The score must be **frozen**: it must not change after calibration, and
  it must not have been fitted or tuned on the LTT items of this
  calibration (fit it on other data, or on the fit + policy-grid items of
  the same split). The library cannot check this; the sheet states it as
  an assumption.
- ``spec`` is a JSON object that describes the score completely (model
  weights, feature names, decoder identity). The digest of ``name``,
  ``version`` and ``spec`` enters the frozen configuration, so
  ``config_id`` changes when the score changes. The guard file stores
  ``name``, ``version``, ``spec`` and the digest, but not the function:
  :func:`~fidetype.trust.dropin.load` refuses a guard with an external
  score unless you pass the same score again (same digest).

Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping, Sequence

import numpy as np

__all__ = [
    "EXTERNAL_PREFIX_SCHEMA",
    "PrefixContext",
    "FrozenPrefixScore",
    "ExternalPrefixCommit",
    "as_prefix_score",
]

#: Schema of the external prefix score block in a frozen configuration (``recipe["commit_score"]``).
EXTERNAL_PREFIX_SCHEMA = "fidetype.external-prefix-score/0.1"


@dataclass(frozen=True)
class PrefixContext:
    """What an external prefix score sees for one decision (read only)."""

    #: The words of the guard's top-1 text: the score must return one value per prefix 1..len(words).
    words: tuple[str, ...]
    #: The calibrated n-best texts (best first) and their calibrated posteriors.
    texts: tuple[str, ...]
    posteriors: np.ndarray
    #: The calibrated candidates (:class:`~fidetype.trust.types.Candidate`).
    candidates: tuple[Any, ...]
    #: Logits input: the frame-calibrated ``(T, V)`` natural-log probabilities that the decoder saw. None for n-best.
    log_probs: np.ndarray | None
    p_top1: float
    guard_risk: float
    n_frames: int | None
    #: The built-in P5-24 prefix rows (:data:`~fidetype.trust.commit_score.PREFIX_FEATURES`, one row per prefix).
    builtin_rows: np.ndarray = field(repr=False, default_factory=lambda: np.zeros((0, 0)))


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


class FrozenPrefixScore:
    """A frozen external per-prefix score: a function plus a JSON ``spec`` that identifies it.

    ``fn(ctx: PrefixContext) -> sequence of len(ctx.words) floats | None``.
    ``name`` and ``version`` name the score; ``spec`` (a JSON object, no
    NaN or infinity) describes it completely. :attr:`digest` is the
    SHA-256 of all three; it enters ``config_id``.
    """

    def __init__(self, fn: Callable[[PrefixContext], Sequence[float] | None], *, name: str,
                 spec: Mapping[str, Any], version: str = "0") -> None:
        if not callable(fn):
            raise TypeError("fn must be callable: fn(ctx) -> one score per word prefix, or None")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(spec, Mapping):
            raise TypeError("spec must be a JSON object (a mapping) that describes the score completely")
        try:
            canon = _canonical({"name": name, "version": str(version), "spec": dict(spec)})
        except (TypeError, ValueError) as e:
            raise TypeError(f"spec must be JSON-serialisable (no NaN, no infinity, no objects): {e}. A score that "
                            "cannot be described in JSON cannot be identified in config_id or saved in a guard "
                            "file.") from e
        self._fn = fn
        self.name = name
        self.version = str(version)
        self.spec: dict[str, Any] = json.loads(_canonical(dict(spec)))
        self._digest = "pfx-" + hashlib.sha256((EXTERNAL_PREFIX_SCHEMA + "\n" + canon).encode("utf-8")).hexdigest()[:24]

    @property
    def digest(self) -> str:
        return self._digest

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "digest": self.digest, "spec": self.spec}

    def scores(self, ctx: PrefixContext) -> np.ndarray | None:
        """The raw scores of the prefixes of ``ctx.words`` (checked), or None (no commit)."""
        out = self._fn(ctx)
        if out is None:
            return None
        s = np.asarray(out, dtype=np.float64).reshape(-1)
        if s.size != len(ctx.words):
            raise ValueError(f"external prefix score {self.name!r} returned {s.size} values for {len(ctx.words)} "
                             "words (it must return one value per word prefix, or None)")
        if np.isnan(s).any():
            raise ValueError(f"external prefix score {self.name!r} returned NaN (use -inf or None for 'no commit')")
        return s

    def __repr__(self) -> str:
        return f"FrozenPrefixScore(name={self.name!r}, version={self.version!r}, digest={self.digest!r})"


def as_prefix_score(obj: Any) -> FrozenPrefixScore:
    """Check that ``obj`` is a :class:`FrozenPrefixScore` (a bare function cannot be identified or saved)."""
    if isinstance(obj, FrozenPrefixScore):
        return obj
    raise TypeError("prefix_score must be a fidetype.trust.FrozenPrefixScore (your function plus a name, a version "
                    "and a JSON spec). A bare function has no stable identity: it cannot enter config_id or be "
                    "checked when a guard file is loaded.")


@dataclass(frozen=True)
class ExternalPrefixCommit:
    """The certified external prefix score of a guard (the counterpart of a P5-24 ``LearnedCommitScore``)."""

    score: FrozenPrefixScore
    threshold: float = math.inf
    certification: dict[str, Any] = field(default_factory=dict)
    unit: str = "prefix"
    schema: str = EXTERNAL_PREFIX_SCHEMA

    def with_threshold(self, threshold: float, certification: Mapping[str, Any]) -> "ExternalPrefixCommit":
        return replace(self, threshold=float(threshold), certification=dict(certification))

    def to_dict(self) -> dict[str, Any]:
        thr = self.threshold
        return {"schema": self.schema, "unit": self.unit, "score": self.score.to_dict(),
                "threshold": thr if math.isfinite(thr) else "inf", "certification": dict(self.certification)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], score: Any) -> "ExternalPrefixCommit":
        if d.get("schema") != EXTERNAL_PREFIX_SCHEMA or d.get("unit") != "prefix":
            raise ValueError(f"not an external prefix score block (schema {d.get('schema')!r})")
        saved = d.get("score") or {}
        if score is None:
            raise ValueError(f"this guard uses the external prefix score {saved.get('name')!r} version "
                             f"{saved.get('version')!r} (digest {saved.get('digest')}); a function cannot be stored "
                             "in a file. Pass prefix_score= (the same FrozenPrefixScore), or the guarantee does not "
                             "apply.")
        score = as_prefix_score(score)
        if score.digest != saved.get("digest"):
            raise ValueError(f"prefix_score digest {score.digest} does not match the guard's external prefix score "
                             f"{saved.get('name')!r} (digest {saved.get('digest')}): a different score voids the "
                             "guarantee")
        thr = d.get("threshold", "inf")
        return cls(score=score, threshold=math.inf if thr in ("inf", None) else float(thr),
                   certification=dict(d.get("certification") or {}))
