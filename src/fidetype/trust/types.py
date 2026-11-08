"""The data protocol of the trust core.

The trust core reads only these types. It does not import a decoder or a
language model. Any decoder can feed the trust core if it gives an
:class:`NBest` list.

- :class:`Candidate` is one sentence hypothesis with its scores.
- :class:`NBest` is the ranked list of candidates for one input.
- :func:`from_lm_hypotheses` converts the ``Hypothesis`` objects of
  :mod:`fidetype.lm.beam` (or any object with the same attributes) into
  an :class:`NBest`. This is the only place that knows the LM types.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class Candidate:
    """One sentence hypothesis.

    ``score``
        The total decoder score (higher is better). It is a log-domain
        value, for example ``logp_acoustic + w * logp_lm + bonus``. The
        trust core turns the scores of a list into posteriors with a
        softmax (see :mod:`fidetype.trust.calibration`).
    ``logp_acoustic``
        Log-probability of the text under the neural evidence only.
        ``nan`` if the decoder does not give it.
    ``logp_lm``
        Log-probability of the text under the language model only. 0.0
        if no LM was used. ``nan`` if unknown.
    ``char_confidences``
        One value in [0, 1] per character of ``text``: the acoustic
        (neural) posterior of that character. Empty if unknown.
    """

    text: str
    score: float
    logp_acoustic: float = math.nan
    logp_lm: float = math.nan
    char_confidences: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        cc = tuple(float(c) for c in self.char_confidences)
        object.__setattr__(self, "char_confidences", cc)
        if cc and len(cc) != len(self.text):
            raise ValueError(
                f"char_confidences has {len(cc)} values but text has {len(self.text)} characters"
            )

    def with_confidences(self, conf: Iterable[float]) -> "Candidate":
        """Return a copy with new character confidences."""
        return Candidate(self.text, self.score, self.logp_acoustic, self.logp_lm, tuple(conf))


@dataclass
class NBest:
    """A ranked list of candidates for one input.

    The constructor sorts the candidates by ``score``, best first. Two
    candidates must not have the same text (the decoder must merge them).
    ``stream_meta`` holds free data about the input (source, seed, ...).
    """

    candidates: list[Candidate]
    stream_meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.candidates = sorted(self.candidates, key=lambda c: -c.score)
        texts = [c.text for c in self.candidates]
        if len(set(texts)) != len(texts):
            raise ValueError("NBest candidates must have different texts")

    def __len__(self) -> int:
        return len(self.candidates)

    @property
    def texts(self) -> list[str]:
        return [c.text for c in self.candidates]

    @property
    def scores(self) -> np.ndarray:
        return np.array([c.score for c in self.candidates], dtype=np.float64)

    @property
    def top(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None

    def index_of(self, text: str) -> int:
        """Return the rank of ``text`` in the list, or -1 if it is absent."""
        for i, c in enumerate(self.candidates):
            if c.text == text:
                return i
        return -1


def _get(obj: Any, name: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _confidences(h: Any, variant: str | None) -> tuple[float, ...]:
    conf = None
    if variant is not None:
        variants = _get(h, "confidence_variants", None)
        if isinstance(variants, dict) and variant in variants:
            conf = variants[variant]
        elif variant == "frame":
            conf = _get(h, "char_frame_posteriors", None)
    if conf is None or len(conf) == 0:
        conf = _get(h, "char_confidences", None)
    if conf is None:
        return ()
    # A character without a frame span has no acoustic evidence: use 0.
    return tuple(0.0 if not math.isfinite(float(c)) else float(c) for c in conf)


def from_lm_hypotheses(
    hyps: Sequence[Any],
    stream_meta: dict[str, Any] | None = None,
    normalize: bool = True,
    confidence_variant: str | None = "frame",
) -> NBest:
    """Convert LM-agent ``Hypothesis`` objects into an :class:`NBest`.

    The function uses duck typing. Each item must have ``text`` and
    ``score``. It can have ``logp_acoustic``, ``logp_lm`` and
    ``char_confidences``. Dicts with the same keys also work.

    ``Candidate.char_confidences`` must be the *acoustic* posterior of
    each character, because the guard compares it with the LM. So the
    function takes ``confidence_variants[confidence_variant]`` if the
    hypothesis has it (``fidetype.lm.beam`` gives ``"frame"``, the
    maximum frame posterior over the aligned frames), then
    ``char_frame_posteriors``, then ``char_confidences``. NaN values (no
    aligned frame) become 0. ``confidence_variant=None`` always uses
    ``char_confidences``.

    If ``normalize`` is true, the function joins runs of spaces and strips
    the text. Hypotheses that then have the same text are merged: the
    function keeps the best score (a max, not a sum, because the scores
    can include LM terms that are not probabilities).
    """
    best: dict[str, Candidate] = {}
    for h in hyps:
        text = str(_get(h, "text", ""))
        conf = _confidences(h, confidence_variant)
        if normalize:
            norm = " ".join(text.split())
            if norm != text:
                # Keep the confidences of the kept characters only.
                if conf and len(conf) == len(text):
                    keep = []
                    prev_space = True
                    for ch, c in zip(text, conf):
                        if ch == " ":
                            if prev_space:
                                continue
                            prev_space = True
                        else:
                            prev_space = False
                        keep.append(c)
                    conf = tuple(keep[: len(norm)])
                else:
                    conf = ()
                text = norm
        if conf and len(conf) != len(text):
            conf = ()
        cand = Candidate(
            text=text,
            score=float(_get(h, "score", math.nan)),
            logp_acoustic=float(_get(h, "logp_acoustic", math.nan)),
            logp_lm=float(_get(h, "logp_lm", math.nan)),
            char_confidences=conf,
        )
        if text not in best or cand.score > best[text].score:
            best[text] = cand
    return NBest(list(best.values()), dict(stream_meta or {}))
