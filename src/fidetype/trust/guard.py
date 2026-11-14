"""Trust core module d: the hallucination guard.

A language model (LM) can turn weak neural evidence into a fluent
sentence. Brain2Qwerty v2 shows this risk: its NeuroLLM improves WER but
can write fluent wrong sentences. For a patient, a fluent wrong sentence
is worse than no sentence. The guard measures how much of a candidate
the LM "invented".

Signals
-------
For one candidate with n characters:

``low_evidence_frac``
    The share of characters whose acoustic posterior (``char_confidences``)
    is below ``low_conf_threshold``. These characters come mostly from
    the LM prior, not from the neural evidence.
``expected_char_error``
    ``1 - mean(char_confidences)``: the expected share of wrong
    characters if the neural evidence alone is trusted.
``lm_acoustic_gap``
    ``logp_lm / n - logp_acoustic / n``: positive when the LM supports
    the text more than the neural evidence does (nats per character).
    ``nan`` if a term is unknown.
``consistency``
    Posterior-weighted word agreement between the top-1 and the other
    top-k candidates: ``sum_j p_j * sim(c_0, c_j) / sum_j p_j`` with
    ``sim = 1 - word_edit_distance / max(word counts)``. It is a simple
    word-overlap form of semantic entropy (Farquhar et al. 2024): no
    neural model, only surface words.
``semantic_entropy``
    Entropy (nats) of the posterior mass over clusters of candidates.
    Two candidates share a cluster if their word edit distance is at most
    ``cluster_max_word_edits``.

``risk`` combines two signals, ``e = w_evidence * low_evidence_frac``
and ``c = w_consistency * (1 - consistency)``. With ``combine="max"``
(default) it is ``max(e, c)``; with ``combine="mean"`` it is ``e + c``
(then the weights should sum to 1). The result is clipped to [0, 1].
High risk means "do not trust this text".

Why ``max``: the two signals fail in different cases. On a
time-shuffled stream, a strong LM writes fluent text and the n-best
list agrees with itself (consistency near 1), but most characters have
low acoustic evidence. On real input, a wrong top-1 shows more often as
disagreement in the n-best list. A mean dilutes the strong signal in
both cases.

Audit
-----
:func:`null_input_audit` runs a decode function on the real stream, a
time-shuffled stream and a near-uniform stream. A pipeline that writes
fluent text for (b) or (c) hallucinates: that text cannot come from the
neural evidence. The fluent-output rate on (b) and (c) is the
hallucination rate of the pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.trust._align import guard_edit_distance
from fidetype.trust.calibration import log_softmax
from fidetype.trust.types import Candidate, NBest


@dataclass(frozen=True)
class GuardConfig:
    #: Characters with an acoustic posterior below this are "low evidence".
    low_conf_threshold: float = 0.5
    #: Number of top candidates for the consistency score.
    consistency_k: int = 5
    #: Word edits allowed inside one semantic cluster.
    cluster_max_word_edits: int = 0
    #: Weights of the two risk signals.
    w_evidence: float = 1.0
    w_consistency: float = 1.0
    #: "max" or "mean" (see the module docstring).
    combine: str = "max"


@dataclass(frozen=True)
class GuardScore:
    low_evidence_frac: float
    expected_char_error: float
    lm_acoustic_gap: float
    consistency: float
    semantic_entropy: float
    risk: float


def word_similarity(a: str, b: str) -> float:
    """Return ``1 - word_edit_distance(a, b) / max(word counts)`` (1 if both empty)."""
    wa, wb = tuple(a.split()), tuple(b.split())
    n = max(len(wa), len(wb))
    if n == 0:
        return 1.0
    return 1.0 - guard_edit_distance(wa, wb) / n


def nbest_consistency(texts: Sequence[str], posteriors: np.ndarray, k: int = 5) -> float:
    """Posterior-weighted word agreement of the top-k with the top-1."""
    if not texts:
        return 0.0
    k = min(k, len(texts))
    p = np.asarray(posteriors[:k], dtype=np.float64)
    if p.sum() <= 0:
        return 1.0
    sims = np.array([word_similarity(texts[0], t) for t in texts[:k]])
    return float(np.sum(p * sims) / np.sum(p))


def semantic_entropy(texts: Sequence[str], posteriors: np.ndarray, max_word_edits: int = 0) -> float:
    """Entropy (nats) of the posterior mass over word-level clusters."""
    reps: list[tuple[str, ...]] = []
    mass: list[float] = []
    for t, p in zip(texts, posteriors):
        w = tuple(t.split())
        for i, r in enumerate(reps):
            if guard_edit_distance(w, r) <= max_word_edits:
                mass[i] += float(p)
                break
        else:
            reps.append(w)
            mass.append(float(p))
    m = np.asarray(mass)
    if m.sum() <= 0:
        return 0.0
    m = m / m.sum()
    m = m[m > 0]
    return float(-np.sum(m * np.log(m)))


class HallucinationGuard:
    """Compute :class:`GuardScore` for the top-1 candidate of an n-best list."""

    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def evidence(self, cand: Candidate) -> tuple[float, float, float]:
        """Return (low_evidence_frac, expected_char_error, lm_acoustic_gap)."""
        n = len(cand.text)
        conf = np.asarray(cand.char_confidences, dtype=np.float64)
        if conf.size:
            low = float(np.mean(conf < self.config.low_conf_threshold))
            exp_err = float(1.0 - conf.mean())
        elif n == 0:
            low, exp_err = 0.0, 0.0
        else:
            low, exp_err = math.nan, math.nan
        gap = (cand.logp_lm - cand.logp_acoustic) / n if n else math.nan
        return low, exp_err, gap

    def score(self, nbest: NBest, posteriors: np.ndarray | None = None) -> GuardScore:
        cfg = self.config
        if len(nbest) == 0:
            return GuardScore(1.0, 1.0, math.nan, 0.0, 0.0, 1.0)
        if posteriors is None:
            s = nbest.scores
            posteriors = np.exp(log_softmax(s))
        low, exp_err, gap = self.evidence(nbest.candidates[0])
        texts = nbest.texts
        cons = nbest_consistency(texts, posteriors, cfg.consistency_k)
        se = semantic_entropy(texts, posteriors, cfg.cluster_max_word_edits)
        low_term = low if math.isfinite(low) else 0.0
        if len(nbest.candidates[0].text) == 0:
            low_term = 1.0  # An empty output has no evidence for any text.
        e, c = cfg.w_evidence * low_term, cfg.w_consistency * (1.0 - cons)
        if cfg.combine == "max":
            risk = max(e, c)
        elif cfg.combine == "mean":
            risk = e + c
        else:
            raise ValueError(f"unknown combine {cfg.combine!r}")
        return GuardScore(low, exp_err, gap, cons, se, float(np.clip(risk, 0.0, 1.0)))


# --- metrics --------------------------------------------------------------


def auroc(scores: Sequence[float], labels: Sequence[bool]) -> float:
    """Area under the ROC curve (Mann-Whitney U, ties count one half).

    ``labels`` True marks the positive class (here: a wrong top-1). A
    higher score must mean "more likely positive". Returns ``nan`` if a
    class is empty.
    """
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels, dtype=bool)
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return math.nan
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=np.float64)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i : j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    u = ranks[y].sum() - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


# --- null-input audit -----------------------------------------------------


def shuffle_stream(stream: NeuralTextStream, rng: np.random.Generator) -> NeuralTextStream:
    """Return the stream with its frames in a random time order.

    The frame statistics stay the same. The link between time and text is
    broken, so no true sentence is in the stream.
    """
    perm = rng.permutation(stream.n_frames)
    return NeuralTextStream(
        log_probs=stream.log_probs[perm],
        frame_times=stream.frame_times,
        vocab=stream.vocab,
        blank_id=stream.blank_id,
        source=stream.source + "+shuffled",
        meta={**stream.meta, "audit": "shuffled"},
    )


def uniform_stream(
    stream: NeuralTextStream, rng: np.random.Generator, jitter: float = 0.05
) -> NeuralTextStream:
    """Return a stream of the same length with near-uniform frames.

    Each row is ``log_softmax(log(1/V) + jitter * N(0, 1))``. With
    ``jitter = 0`` all rows are exactly uniform.
    """
    T, V = stream.log_probs.shape
    z = np.full((T, V), -math.log(V)) + jitter * rng.standard_normal((T, V))
    return NeuralTextStream(
        log_probs=log_softmax(z, axis=1).astype(np.float32),
        frame_times=stream.frame_times,
        vocab=stream.vocab,
        blank_id=stream.blank_id,
        source=stream.source + "+uniform",
        meta={**stream.meta, "audit": "uniform"},
    )


def lexicon_fluency(lexicon: Iterable[str], min_words: int = 2, min_known: float = 0.8) -> Callable[[str], bool]:
    """Return a test "is this text fluent?".

    A text is fluent if it has at least ``min_words`` words and a share of
    at least ``min_known`` of its words is in ``lexicon``.
    """
    lex = frozenset(lexicon)

    def fluent(text: str) -> bool:
        words = text.split()
        if len(words) < min_words:
            return False
        return sum(w in lex for w in words) / len(words) >= min_known

    return fluent


def null_input_audit(
    decode_fn: Callable[[NeuralTextStream], NBest],
    streams: Sequence[NeuralTextStream],
    fluency_fn: Callable[[str], bool],
    accept_fn: Callable[[NBest], bool] | None = None,
    seed: int = 0,
    jitter: float = 0.05,
) -> dict[str, dict[str, float]]:
    """Run the decoder on real, shuffled and uniform versions of each stream.

    For each condition (``real``, ``shuffled``, ``uniform``), return:

    - ``nonempty_rate``: the top-1 text is not empty.
    - ``fluent_rate``: the top-1 text is fluent (``fluency_fn``). On
      ``shuffled`` and ``uniform`` this is the hallucination rate of the
      decoder.
    - ``accepted_rate`` and ``fluent_accepted_rate`` (only with
      ``accept_fn``): the trust layer would show the text as output
      (for example the policy COMMITs it), and the text is fluent. On the
      null inputs, ``fluent_accepted_rate`` is the hallucination rate of
      the full pipeline.
    - ``mean_chars``: mean top-1 length.
    """
    rng = np.random.default_rng(seed)
    conds: dict[str, Callable[[NeuralTextStream], NeuralTextStream]] = {
        "real": lambda s: s,
        "shuffled": lambda s: shuffle_stream(s, rng),
        "uniform": lambda s: uniform_stream(s, rng, jitter),
    }
    out: dict[str, dict[str, float]] = {}
    for name, make in conds.items():
        nonempty, fluent, acc, fl_acc, chars = [], [], [], [], []
        for s in streams:
            nb = decode_fn(make(s))
            top = nb.top.text if nb.top is not None else ""
            nonempty.append(bool(top))
            f = fluency_fn(top)
            fluent.append(f)
            chars.append(len(top))
            if accept_fn is not None:
                a = bool(accept_fn(nb))
                acc.append(a)
                fl_acc.append(a and f)
        res = {
            "nonempty_rate": float(np.mean(nonempty)),
            "fluent_rate": float(np.mean(fluent)),
            "mean_chars": float(np.mean(chars)),
        }
        if accept_fn is not None:
            res["accepted_rate"] = float(np.mean(acc))
            res["fluent_accepted_rate"] = float(np.mean(fl_acc))
        out[name] = res
    return out
