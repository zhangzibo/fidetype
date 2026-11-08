"""Error and calibration metrics.

- CER and WER use the Levenshtein edit distance, as in Brain2Qwerty
  v1 and v2.
- ECE is the expected calibration error of Guo et al. (2017), with
  equal-width bins.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream


def edit_distance(ref: Sequence, hyp: Sequence) -> int:
    """Return the Levenshtein distance (substitutions, insertions,
    deletions, each with cost 1) between two sequences."""
    if len(ref) < len(hyp):
        ref, hyp = hyp, ref  # Keep the shorter sequence in the inner loop.
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cur[j] = min(
                prev[j] + 1,  # deletion
                cur[j - 1] + 1,  # insertion
                prev[j - 1] + (r != h),  # substitution or match
            )
        prev = cur
    return prev[-1]


def _rate(ref: Sequence, hyp: Sequence) -> float:
    if len(ref) == 0:
        # No reference: zero error if the hypothesis is also empty.
        return 0.0 if len(hyp) == 0 else 1.0
    return edit_distance(ref, hyp) / len(ref)


def cer(ref: str, hyp: str) -> float:
    """Return the character error rate: edit distance / len(ref).

    The value can be above 1 if ``hyp`` has many insertions. If ``ref`` is
    empty, the result is 0.0 for an empty ``hyp`` and 1.0 otherwise.
    """
    return _rate(ref, hyp)


def wer(ref: str, hyp: str) -> float:
    """Return the word error rate. Words are split on whitespace."""
    return _rate(ref.split(), hyp.split())


def ctc_greedy_ids(stream: NeuralTextStream) -> list[int]:
    """Return the CTC best-path token ids: take the argmax of each frame,
    collapse repeats, then remove blanks."""
    if stream.n_frames == 0:
        return []
    best = np.argmax(stream.log_probs, axis=1)
    keep = np.ones(best.shape[0], dtype=bool)
    keep[1:] = best[1:] != best[:-1]
    best = best[keep]
    return [int(i) for i in best if i != stream.blank_id]


def ctc_greedy_decode(stream: NeuralTextStream) -> str:
    """Return the CTC best-path text of a stream."""
    return "".join(stream.vocab[i] for i in ctc_greedy_ids(stream))


def expected_calibration_error(
    confidences: Sequence[float] | np.ndarray,
    correct: Sequence[bool] | np.ndarray,
    n_bins: int = 15,
) -> float:
    """Return the expected calibration error (Guo et al. 2017).

    The function puts the predictions into ``n_bins`` equal-width bins
    over [0, 1]. Bin b holds confidences in (b/n, (b+1)/n]; the first bin
    also holds 0. ECE is the sum over bins of
    ``(bin size / N) * |accuracy(bin) - mean confidence(bin)|``.
    """
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    corr = np.asarray(correct, dtype=np.float64).ravel()
    if conf.shape != corr.shape:
        raise ValueError("confidences and correct must have the same length")
    if conf.size == 0:
        raise ValueError("ECE needs at least one prediction")
    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")
    if np.any((conf < 0) | (conf > 1)):
        raise ValueError("confidences must be in [0, 1]")
    bins = np.clip(np.ceil(conf * n_bins).astype(int) - 1, 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = bins == b
        if m.any():
            ece += m.mean() * abs(corr[m].mean() - conf[m].mean())
    return float(ece)
