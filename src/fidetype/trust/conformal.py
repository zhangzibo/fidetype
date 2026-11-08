"""Trust core module c: conformal prediction sets.

A conformal prediction set C(x) is a set of candidate outputs. Split
conformal prediction (Angelopoulos & Bates 2021, Sec. 1) gives this
guarantee: if the calibration examples and the test example are
exchangeable, then ``P(y in C(x)) >= 1 - alpha``. The guarantee is
marginal (an average over inputs). It is not a guarantee for each input.

The recipe:

1. Define a nonconformity score s(x, y). A high score means "y is an
   unusual answer for x".
2. Compute s on n calibration examples with known truth.
3. Let q be the ceil((n + 1)(1 - alpha))-th smallest score. If this rank
   is above n, q is +inf.
4. C(x) = all candidates y with s(x, y) <= q.

Sentence sets over an n-best list
---------------------------------
The candidates are the sentences of the n-best list. The posteriors come
from :mod:`fidetype.trust.calibration`. Two scores:

- ``"lac"`` (least ambiguous classifier): s = 1 - p(y). Small sets.
- ``"aps"`` (adaptive prediction sets, non-random): s = the posterior
  mass of all candidates ranked at or above y.

An n-best list does not always hold the truth. We give two modes:

- ``mode="conditional"`` (default). Calibrate only on examples whose
  truth is in the n-best list. Guarantee: ``P(y in C | y in n-best) >=
  1 - alpha``. This is coverage "in the n-best sense". The miss rate
  ``P(y not in n-best)`` is reported separately. A set cannot cover a
  missed truth.
- ``mode="marginal"``. A missed truth gets s = +inf. The label space is
  the n-best list plus one extra label ``OTHER`` ("the truth is not in
  the list"). ``OTHER`` is in C only if q = +inf. Guarantee: ``P(y in C
  or (y missed and OTHER in C)) >= 1 - alpha``. If the miss rate is above
  alpha, q = +inf and every set is the full list plus ``OTHER``.

Word sets
---------
:class:`WordConformal` makes one set per word position of the top-1
sentence. The word posterior of w at position i is the summed posterior
of the candidates whose word aligned to position i is w. The score is 1
minus the word posterior of the true word. All word positions of all
calibration sentences are pooled. Positions in one sentence are not
independent, so the guarantee holds for a random word position of a
random sentence, not for all words of one sentence together.

Adaptive conformal inference
----------------------------
Exchangeability fails in a live session: the signal drifts and the user
gets tired. :class:`AdaptiveConformal` uses the update of Gibbs & Candes
(2021): ``alpha_{t+1} = alpha_t + gamma * (alpha - err_t)``, where
``err_t = 1`` if the set at step t missed the truth. It needs no
exchangeability. For any input sequence, the long-run miss rate is
within ``(max(alpha_1, 1 - alpha_1) + gamma) / (gamma * T)`` of alpha
(their Prop. 4.1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Sequence

import numpy as np

from fidetype.trust._align import map_positions

Score = Literal["lac", "aps"]
Mode = Literal["conditional", "marginal"]


def nonconformity(posteriors: np.ndarray, true_index: int, score: Score = "lac") -> float:
    """Return the score of the true candidate. +inf if ``true_index`` is -1."""
    if true_index < 0:
        return math.inf
    p = np.asarray(posteriors, dtype=np.float64)
    if score == "lac":
        return float(1.0 - p[true_index])
    if score == "aps":
        order = np.argsort(-p, kind="stable")
        rank = int(np.nonzero(order == true_index)[0][0])
        return float(np.sum(p[order[: rank + 1]]))
    raise ValueError(f"unknown score {score!r}")


def candidate_scores(posteriors: np.ndarray, score: Score = "lac") -> np.ndarray:
    """Return the score of every candidate of one list."""
    p = np.asarray(posteriors, dtype=np.float64)
    if score == "lac":
        return 1.0 - p
    order = np.argsort(-p, kind="stable")
    cum = np.cumsum(p[order])
    out = np.empty_like(p)
    out[order] = cum
    return out


def conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Return the split-conformal threshold q (see the module docstring)."""
    s = np.sort(np.asarray(scores, dtype=np.float64))
    n = s.size
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    k = math.ceil((n + 1) * (1.0 - alpha))
    if n == 0 or k > n:
        return math.inf
    return float(s[k - 1])


@dataclass
class PredictionSet:
    """A conformal set: candidate indices (best posterior first) and the
    ``OTHER`` flag of marginal mode."""

    indices: list[int]
    includes_other: bool = False

    @property
    def size(self) -> int:
        return len(self.indices)

    def covers(self, true_index: int) -> bool:
        return true_index in self.indices or (true_index < 0 and self.includes_other)


def _predict(posteriors: np.ndarray, q: float, score: Score, with_other: bool) -> PredictionSet:
    p = np.asarray(posteriors, dtype=np.float64)
    if p.size == 0:
        return PredictionSet([], with_other and math.isinf(q))
    s = candidate_scores(p, score)
    idx = [int(i) for i in np.argsort(-p, kind="stable") if s[i] <= q + 1e-12]
    return PredictionSet(idx, with_other and math.isinf(q))


@dataclass
class SplitConformal:
    """Split conformal sets over n-best sentences.

    Fit with :meth:`fit` on calibration posteriors and the rank of the
    truth (-1 if absent). Use :meth:`predict` on new posteriors.
    """

    alpha: float = 0.1
    score: Score = "lac"
    mode: Mode = "conditional"
    q: float = math.nan
    n_calibration: int = 0
    calibration_miss_rate: float = math.nan

    def fit(self, posteriors_list: Sequence[np.ndarray], true_indices: Sequence[int]) -> "SplitConformal":
        if len(posteriors_list) != len(true_indices) or not posteriors_list:
            raise ValueError("posteriors_list and true_indices must be non-empty and of equal length")
        scores = [nonconformity(p, int(t), self.score) for p, t in zip(posteriors_list, true_indices)]
        self.calibration_miss_rate = float(np.mean([t < 0 for t in true_indices]))
        if self.mode == "conditional":
            scores = [s for s in scores if math.isfinite(s)]
        elif self.mode != "marginal":
            raise ValueError(f"unknown mode {self.mode!r}")
        self.n_calibration = len(scores)
        self.q = conformal_quantile(scores, self.alpha)
        return self

    def predict(self, posteriors: np.ndarray) -> PredictionSet:
        if math.isnan(self.q):
            raise RuntimeError("call fit() first")
        return _predict(posteriors, self.q, self.score, self.mode == "marginal")

    def evaluate(self, posteriors_list: Sequence[np.ndarray], true_indices: Sequence[int]) -> dict[str, float]:
        """Return empirical coverage, mean set size and miss rate.

        - ``coverage``: P(truth in set) over all examples (strict).
        - ``coverage_in_nbest``: the same, over examples whose truth is in
          the n-best list (the conditional-mode guarantee).
        - ``coverage_with_other``: counts ``OTHER`` as correct for missed
          truths (the marginal-mode guarantee).
        - ``mean_set_size``, ``empty_rate``, ``miss_rate``.
        """
        sets = [self.predict(p) for p in posteriors_list]
        t = np.asarray(true_indices)
        hit = np.array([s.covers(int(i)) and i >= 0 for s, i in zip(sets, t)])
        hit_other = np.array([s.covers(int(i)) for s, i in zip(sets, t)])
        in_nb = t >= 0
        return {
            "coverage": float(hit.mean()),
            "coverage_in_nbest": float(hit[in_nb].mean()) if in_nb.any() else math.nan,
            "coverage_with_other": float(hit_other.mean()),
            "mean_set_size": float(np.mean([s.size for s in sets])),
            "empty_rate": float(np.mean([s.size == 0 for s in sets])),
            "miss_rate": float(1.0 - in_nb.mean()),
        }


# --- word-level sets -----------------------------------------------------


def word_posteriors(texts: Sequence[str], posteriors: np.ndarray) -> list[dict[str, float]]:
    """Return, for each word position of ``texts[0]``, the posterior mass
    of each word. Other candidates are aligned to the top-1 words with a
    Levenshtein alignment. A deleted word counts as the empty string."""
    if not texts:
        return []
    ref = texts[0].split()
    out: list[dict[str, float]] = [dict() for _ in ref]
    for text, p in zip(texts, posteriors):
        mapped = map_positions(ref, text.split())
        for i, w in enumerate(mapped):
            key = "" if w is None else w
            out[i][key] = out[i].get(key, 0.0) + float(p)
    return out


def _true_words(top_text: str, truth: str) -> list[str | None]:
    """Truth word aligned to each top-1 word position ("" if the truth has
    no word there)."""
    mapped = map_positions(top_text.split(), truth.split())
    return ["" if w is None else w for w in mapped]


@dataclass
class WordConformal:
    """Split conformal sets per word position (pooled LAC score)."""

    alpha: float = 0.1
    q: float = math.nan

    def fit(
        self, texts_list: Sequence[Sequence[str]], posteriors_list: Sequence[np.ndarray], truths: Sequence[str]
    ) -> "WordConformal":
        scores: list[float] = []
        for texts, p, truth in zip(texts_list, posteriors_list, truths):
            if not texts:
                continue
            wp = word_posteriors(texts, p)
            for dist, w in zip(wp, _true_words(texts[0], truth)):
                scores.append(1.0 - dist.get(w, 0.0) if w in dist else math.inf)
        self.q = conformal_quantile(scores, self.alpha)
        return self

    def predict(self, texts: Sequence[str], posteriors: np.ndarray) -> list[list[str]]:
        """Return one word set per top-1 word position (best word first)."""
        if math.isnan(self.q):
            raise RuntimeError("call fit() first")
        out = []
        for dist in word_posteriors(texts, posteriors):
            words = sorted(dist, key=lambda w: -dist[w])
            out.append([w for w in words if 1.0 - dist[w] <= self.q + 1e-12])
        return out

    def evaluate(
        self, texts_list: Sequence[Sequence[str]], posteriors_list: Sequence[np.ndarray], truths: Sequence[str]
    ) -> dict[str, float]:
        hits, sizes = [], []
        for texts, p, truth in zip(texts_list, posteriors_list, truths):
            if not texts:
                continue
            for ws, w in zip(self.predict(texts, p), _true_words(texts[0], truth)):
                hits.append(w in ws)
                sizes.append(len(ws))
        return {
            "word_coverage": float(np.mean(hits)) if hits else math.nan,
            "word_mean_set_size": float(np.mean(sizes)) if sizes else math.nan,
        }


# --- adaptive conformal inference ----------------------------------------


@dataclass
class AdaptiveConformal:
    """Adaptive conformal inference (Gibbs & Candes 2021) for a stream.

    At step t the set uses the threshold ``q_t = Quantile_{1 - alpha_t}``
    of the score history (calibration scores plus the scores seen so
    far, or the last ``window`` of them). After the truth is known,
    :meth:`update` sets ``alpha_{t+1} = alpha_t + gamma * (alpha -
    err_t)``. If ``alpha_t <= 0`` the set is the full list; if ``alpha_t
    >= 1`` the set is empty.

    A missed truth (rank -1) gives ``err_t = 1`` and a score of +inf in
    the history. Thus ACI targets coverage over all inputs, misses
    included, if that is feasible.
    """

    alpha: float = 0.1
    gamma: float = 0.01
    score: Score = "lac"
    window: int | None = None
    history: list[float] = field(default_factory=list)
    alpha_t: float = math.nan
    errors: list[int] = field(default_factory=list)
    alphas: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if math.isnan(self.alpha_t):
            self.alpha_t = self.alpha
        self.history = list(self.history)

    def threshold(self) -> float:
        if self.alpha_t <= 0.0:
            return math.inf
        if self.alpha_t >= 1.0:
            return -math.inf
        hist = self.history[-self.window :] if self.window else self.history
        return conformal_quantile(hist, self.alpha_t)

    def predict(self, posteriors: np.ndarray) -> PredictionSet:
        q = self.threshold()
        if q == -math.inf:
            return PredictionSet([])
        return _predict(posteriors, q, self.score, with_other=False)

    def update(self, posteriors: np.ndarray, true_index: int, pred: PredictionSet | None = None) -> bool:
        """Record the truth of the current step. Return True if covered."""
        pred = pred if pred is not None else self.predict(posteriors)
        covered = true_index >= 0 and true_index in pred.indices
        err = 0 if covered else 1
        self.errors.append(err)
        self.alphas.append(self.alpha_t)
        self.alpha_t = self.alpha_t + self.gamma * (self.alpha - err)
        self.history.append(nonconformity(posteriors, true_index, self.score))
        return covered

    def step(self, posteriors: np.ndarray, true_index: int) -> tuple[PredictionSet, bool]:
        """Predict, then update. Return the set and the coverage flag."""
        pred = self.predict(posteriors)
        return pred, self.update(posteriors, true_index, pred)

    @property
    def miscoverage(self) -> float:
        return float(np.mean(self.errors)) if self.errors else math.nan
