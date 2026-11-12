"""Trust core module a: calibration.

A confidence is *calibrated* if, of all outputs with confidence p, a
share p is correct (Guo et al. 2017). Deep networks are often
over-confident. Temperature scaling fixes this with one parameter T > 0:
the calibrated distribution is ``softmax(logits / T)``. T does not change
the argmax, so it does not change the decoded text.

This module gives:

- :class:`TemperatureScaler`: fits one T by minimising a negative
  log-likelihood (NLL). The search is a golden-section search over
  ``log T`` in a bounded interval. No scipy is needed. Three fit modes:

  * :meth:`TemperatureScaler.fit` - multi-class NLL on logit vectors
    (for example CTC frame log-probs with a target token per frame).
  * :meth:`TemperatureScaler.fit_top1` - binary NLL of "top-1 is
    correct" for lists of scores (for example n-best sentence scores).
    This mode also uses inputs where the truth is not in the list.
  * :meth:`TemperatureScaler.fit_binary` - binary NLL on single
    confidences, scaled in the logit domain:
    ``c' = sigmoid(logit(c) / T)`` (for example character confidences).

- :func:`fit_frame_temperature` and :func:`greedy_peaks`: fit T on the
  greedy CTC peaks of streams with known text. Apply it to the stream
  *before* LM fusion. This is the recommended character-level
  calibration (see the note in :meth:`NBestCalibrator.fit`).
- :class:`NBestCalibrator`: one sentence-level and one character-level
  scaler for :class:`~fidetype.trust.types.NBest` lists.
- :func:`session_recalibration`: fit on the first k sentences of a
  session, apply to the rest.
- :func:`reliability_diagram` and :func:`ece` (the ECE of
  :func:`fidetype.eval.metrics.expected_calibration_error`).

Assumptions
-----------
- The fit data and the data to calibrate come from the same
  distribution. If the decoder drifts during a session, refit (see
  :func:`session_recalibration`) or use adaptive conformal sets.
- One scalar T is enough. This is true for the simulator, which distorts
  all frames with one temperature. Real decoders can need more
  parameters (for example per-class or Platt scaling).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Sequence

import numpy as np

from fidetype.eval.metrics import expected_calibration_error
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust._align import align, hyp_correct_mask
from fidetype.trust._ctc import find_segments
from fidetype.trust.types import NBest

T_MIN = 0.05
T_MAX = 20.0
_EPS = 1e-12


def log_softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable log-softmax. ``-inf`` entries stay ``-inf``."""
    x = np.asarray(x, dtype=np.float64)
    m = np.max(x, axis=axis, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0)
    with np.errstate(divide="ignore"):
        lse = np.log(np.sum(np.exp(x - m), axis=axis, keepdims=True)) + m
    return x - lse


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    return np.exp(log_softmax(x, axis=axis))


def scores_to_posteriors(scores: Sequence[float] | np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Return ``softmax(scores / temperature)`` for one n-best list."""
    s = np.asarray(scores, dtype=np.float64)
    if s.size == 0:
        return s
    return softmax(s / temperature)


def golden_section_min(
    f: Callable[[float], float], lo: float, hi: float, tol: float = 1e-5, max_iter: int = 200
) -> float:
    """Return the x in [lo, hi] that minimises a unimodal f (golden-section search)."""
    g = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(max_iter):
        if abs(b - a) < tol:
            break
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return 0.5 * (a + b)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p) - np.log1p(-p)


def _bce(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, _EPS, 1 - _EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


@dataclass
class TemperatureScaler:
    """One scalar temperature, fitted by NLL.

    ``temperature`` is 1.0 (no change) until a fit method runs. Use the
    transform that matches the fit mode (see the module docstring).
    """

    temperature: float = 1.0
    t_min: float = T_MIN
    t_max: float = T_MAX
    #: NLL at T = 1 and at the fitted T (set by the fit methods).
    nll_before: float = math.nan
    nll_after: float = math.nan

    def _search(self, nll: Callable[[float], float]) -> "TemperatureScaler":
        self.nll_before = nll(1.0)
        log_t = golden_section_min(lambda lt: nll(math.exp(lt)), math.log(self.t_min), math.log(self.t_max))
        t = math.exp(log_t)
        self.nll_after = nll(t)
        # Keep T = 1 if the search did not improve the NLL.
        if not self.nll_after < self.nll_before:
            t, self.nll_after = 1.0, self.nll_before
        self.temperature = float(t)
        return self

    # --- multi-class ------------------------------------------------------

    def fit(self, logits: np.ndarray, labels: Sequence[int] | np.ndarray) -> "TemperatureScaler":
        """Fit T on logit (or log-prob) rows ``(N, K)`` and labels ``(N,)``.

        Rows with label -1 are ignored.
        """
        z = np.asarray(logits, dtype=np.float64)
        y = np.asarray(labels, dtype=np.int64)
        keep = y >= 0
        z, y = z[keep], y[keep]
        if z.shape[0] == 0:
            raise ValueError("fit needs at least one row with a label")
        # Replace -inf with a large negative value so the NLL stays finite.
        z = np.where(np.isfinite(z), z, -1e4)

        def nll(t: float) -> float:
            lp = log_softmax(z / t, axis=1)
            return float(-np.mean(lp[np.arange(len(y)), y]))

        return self._search(nll)

    def transform_logits(self, logits: np.ndarray) -> np.ndarray:
        """Return calibrated log-probs ``log_softmax(logits / T)``."""
        return log_softmax(np.asarray(logits, dtype=np.float64) / self.temperature, axis=-1)

    def transform_stream(self, stream: NeuralTextStream) -> NeuralTextStream:
        """Return a copy of the stream with calibrated frame log-probs.

        All other stream fields (vocab, vocab_type, frame_period, latency,
        version, ...) are kept. ``meta`` gets ``calibration_temperature``
        and the spec 4.2 keys ``calibration.applied = true``,
        ``decoder.calibration_method = "temperature"`` and
        ``decoder.calibration_id`` (conformance finding M5-10: before, a
        calibrated stream still said, by the default of
        ``calibration.applied``, that no calibration step had run).
        """
        lp = self.transform_logits(stream.log_probs).astype(np.float32)
        meta = dict(stream.meta)
        meta["calibration_temperature"] = self.temperature
        meta["calibration.applied"] = True
        meta["decoder.calibration_method"] = "temperature"
        meta["decoder.calibration_id"] = f"temperature:{float(self.temperature):.6g}"
        return replace(
            stream,
            log_probs=lp,
            frame_times=np.array(stream.frame_times, copy=True),
            vocab=list(stream.vocab),
            meta=meta,
        )

    # --- n-best top-1 -----------------------------------------------------

    def fit_top1(
        self, score_lists: Sequence[Sequence[float]], top1_correct: Sequence[bool]
    ) -> "TemperatureScaler":
        """Fit T so that ``softmax(scores / T)[0]`` predicts "top-1 is correct".

        ``score_lists[i]`` holds the scores of list i, best first. Lists
        where the truth is absent count as top-1 wrong. This makes the
        top-1 posterior an estimate of P(top-1 correct), not of
        P(top-1 correct | truth in list).
        """
        lists = [np.asarray(s, dtype=np.float64) for s in score_lists]
        y = np.asarray(top1_correct, dtype=np.float64)
        if len(lists) != len(y) or not lists:
            raise ValueError("score_lists and top1_correct must be non-empty and of equal length")

        def nll(t: float) -> float:
            p = np.array([scores_to_posteriors(s, t)[0] if s.size else 0.0 for s in lists])
            return _bce(p, y)

        return self._search(nll)

    def posteriors(self, scores: Sequence[float] | np.ndarray) -> np.ndarray:
        """Return ``softmax(scores / T)``."""
        return scores_to_posteriors(scores, self.temperature)

    # --- binary confidences ----------------------------------------------

    def fit_binary(self, confidences: Sequence[float], correct: Sequence[bool]) -> "TemperatureScaler":
        """Fit T on single confidences with ``c' = sigmoid(logit(c) / T)``."""
        lg = _logit(np.asarray(confidences, dtype=np.float64))
        y = np.asarray(correct, dtype=np.float64)
        if lg.size == 0 or lg.shape != y.shape:
            raise ValueError("confidences and correct must be non-empty and of equal length")

        def nll(t: float) -> float:
            return _bce(1.0 / (1.0 + np.exp(-lg / t)), y)

        return self._search(nll)

    def transform_confidences(self, confidences: Sequence[float] | np.ndarray) -> np.ndarray:
        lg = _logit(np.asarray(confidences, dtype=np.float64))
        return 1.0 / (1.0 + np.exp(-lg / self.temperature))


# --- frame-level helpers ------------------------------------------------


def greedy_peaks(stream: NeuralTextStream, truth: str | None = None) -> dict[str, np.ndarray]:
    """Return the greedy CTC peaks of a stream and, with ``truth``, their targets.

    Keys: ``centres`` (frame index), ``labels`` (argmax token id),
    ``confidence`` (probability of the label at the centre). With
    ``truth``: ``targets`` (the true token aligned to each peak by a
    Levenshtein alignment of the greedy text to the truth; the blank id
    for an inserted peak) and ``correct`` (label == target).
    """

    segs = find_segments(stream)
    centres = np.array([c for _, _, c in segs], dtype=np.int64)
    if centres.size:
        labels = np.argmax(stream.log_probs[centres], axis=1).astype(np.int64)
        conf = np.exp(stream.log_probs[centres, labels].astype(np.float64))
    else:
        labels = np.zeros(0, dtype=np.int64)
        conf = np.zeros(0)
    out = {"centres": centres, "labels": labels, "confidence": conf}
    if truth is not None:
        tok = {t: i for i, t in enumerate(stream.vocab)}
        hyp = [stream.vocab[i] for i in labels]
        targets = np.full(len(labels), stream.blank_id, dtype=np.int64)
        for i, j in align(list(truth), hyp):
            if i is not None and j is not None and truth[i] in tok:
                targets[j] = tok[truth[i]]
        out["targets"] = targets
        out["correct"] = targets == labels
    return out


def fit_frame_temperature(streams: Sequence[NeuralTextStream], truths: Sequence[str]) -> TemperatureScaler:
    """Fit a :class:`TemperatureScaler` on the greedy peak frames of streams.

    The targets come from :func:`greedy_peaks`. Only peak centres are used:
    blank frames carry almost no information about the character
    distribution. Use :meth:`TemperatureScaler.transform_stream` on new
    streams *before* LM fusion (architecture: calibrate, then fuse).
    """
    rows, ys = [], []
    for s, t in zip(streams, truths):
        pk = greedy_peaks(s, t)
        if pk["centres"].size:
            rows.append(s.log_probs[pk["centres"]].astype(np.float64))
            ys.append(pk["targets"])
    if not rows:
        return TemperatureScaler()
    return TemperatureScaler().fit(np.concatenate(rows), np.concatenate(ys))


# --- n-best helpers -------------------------------------------------------


def nbest_labels(nbest: NBest, truth: str) -> tuple[int, bool]:
    """Return (rank of the truth or -1, top-1 is correct)."""
    idx = nbest.index_of(truth)
    return idx, idx == 0


def char_labels(nbest: NBest, truth: str) -> tuple[list[float], list[bool]]:
    """Return the top-1 character confidences and per-character
    correctness (Levenshtein alignment to the truth)."""
    top = nbest.top
    if top is None or not top.char_confidences:
        return [], []
    return list(top.char_confidences), hyp_correct_mask(truth, top.text)


@dataclass
class NBestCalibrator:
    """Sentence-level and character-level temperature scaling for n-best lists.

    - ``sentence``: fitted with :meth:`TemperatureScaler.fit_top1` on the
      candidate scores.
    - ``char``: fitted with :meth:`TemperatureScaler.fit_binary` on the
      top-1 character confidences.
    """

    sentence: TemperatureScaler
    char: TemperatureScaler

    @classmethod
    def identity(cls) -> "NBestCalibrator":
        return cls(TemperatureScaler(), TemperatureScaler())

    @classmethod
    def fit(cls, nbests: Sequence[NBest], truths: Sequence[str], fit_char: bool = True) -> "NBestCalibrator":
        """Fit both scalers.

        ``fit_char=False`` keeps the character scaler at T = 1. Use it
        when the stream was calibrated at frame level before decoding.
        Note: after LM fusion, a character with a low acoustic posterior
        can still be correct (the LM fixed it). A binary temperature on
        such confidences can make their ECE worse. Frame-level
        calibration (:func:`fit_frame_temperature`) does not have this
        problem.
        """
        if len(nbests) != len(truths) or not nbests:
            raise ValueError("nbests and truths must be non-empty and of equal length")
        sent = TemperatureScaler().fit_top1(
            [nb.scores for nb in nbests], [nb.index_of(t) == 0 for nb, t in zip(nbests, truths)]
        )
        if not fit_char:
            return cls(sent, TemperatureScaler())
        confs: list[float] = []
        corr: list[bool] = []
        for nb, t in zip(nbests, truths):
            c, k = char_labels(nb, t)
            confs += c
            corr += k
        char = TemperatureScaler().fit_binary(confs, corr) if confs else TemperatureScaler()
        return cls(sent, char)

    def posteriors(self, nbest: NBest) -> np.ndarray:
        return self.sentence.posteriors(nbest.scores)

    def calibrate_chars(self, nbest: NBest) -> NBest:
        """Return a copy of the list with calibrated character confidences."""
        if self.char.temperature == 1.0:
            return nbest
        cands = [
            c.with_confidences(self.char.transform_confidences(c.char_confidences)) if c.char_confidences else c
            for c in nbest.candidates
        ]
        return NBest(cands, dict(nbest.stream_meta))


def session_recalibration(
    nbests: Sequence[NBest], truths: Sequence[str], k: int
) -> tuple[NBestCalibrator, list[np.ndarray]]:
    """Fit a calibrator on the first ``k`` sentences of one session.

    Return the calibrator and the calibrated posteriors of the other
    sentences (``nbests[k:]``). The truth of the first k sentences must be
    known (for example a short copy-typing block at the session start).
    """
    if not 0 < k < len(nbests):
        raise ValueError("k must be in 1 .. len(nbests) - 1")
    cal = NBestCalibrator.fit(nbests[:k], truths[:k])
    return cal, [cal.posteriors(nb) for nb in nbests[k:]]


# --- diagnostics ----------------------------------------------------------


def ece(confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 15) -> float:
    """Expected calibration error (Guo et al. 2017); see
    :func:`fidetype.eval.metrics.expected_calibration_error`."""
    return expected_calibration_error(confidences, correct, n_bins)


def reliability_diagram(
    confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 15
) -> dict[str, np.ndarray | float]:
    """Return the data of a reliability diagram.

    The bins are the same as in :func:`ece`. Keys: ``bin_lower``,
    ``bin_upper``, ``mean_confidence``, ``accuracy``, ``count`` (empty
    bins have ``nan`` means), and ``ece``.
    """
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    corr = np.asarray(correct, dtype=np.float64).ravel()
    bins = np.clip(np.ceil(conf * n_bins).astype(int) - 1, 0, n_bins - 1)
    mean_c = np.full(n_bins, np.nan)
    acc = np.full(n_bins, np.nan)
    count = np.zeros(n_bins, dtype=np.int64)
    for b in range(n_bins):
        m = bins == b
        count[b] = int(m.sum())
        if count[b]:
            mean_c[b] = conf[m].mean()
            acc[b] = corr[m].mean()
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    return {
        "bin_lower": edges[:-1],
        "bin_upper": edges[1:],
        "mean_confidence": mean_c,
        "accuracy": acc,
        "count": count,
        "ece": ece(conf, corr, n_bins),
    }
