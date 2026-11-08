"""Effective words per minute (eWPM) and safety metrics.

Definition
----------
A session has N intended sentences y_1 .. y_N. For each sentence i the
interaction (decode, policy, user) gives:

- ``time_i``: all the time the user spends on sentence i, in seconds:
  the first input (typing), plus reading, selection, ASK/ABSTAIN
  overheads, all repeats (overhead + typing again) and all corrections.
- ``final_i``: the text that the sentence ends with (``None`` if no text).
- ``communicated_i``: ``final_i == y_i`` exactly, after the corrections
  of the user.

Then::

    eWPM = 60 * sum_i [communicated_i] * words(y_i) / sum_i time_i

``words(y)`` is the number of whitespace-separated words of y. A sentence
counts only if it is exactly right at the end. A sentence with one wrong
word counts zero words. This is strict on purpose: for an AAC user, one
wrong word can change the meaning.

``ewpm_partial`` is a lenient variant. It credits
``max(0, words(y_i) - word_edit_distance(final_i, y_i))`` words for every
sentence that ends with text.

Safety metrics
--------------
- ``wrong_commit_rate``: share of sentences where the system COMMITted a
  text that is not the intended text (whether or not the user then
  corrected it). The policy fit puts a limit on this rate.
- ``silent_error_rate``: share of sentences that end with a wrong text
  that the user did not correct (missed wrong commits and accepted
  wrong-but-close offers). These errors reach the reader.
- ``abstain_rate``: share of sentences that end with ABSTAIN.
- ``committed_cer``: CER of the committed texts (before corrections),
  pooled over the sentences that end with a COMMIT.

Relation to other metrics
-------------------------
- **Wolpaw ITR** (Wolpaw et al. 1998; :func:`wolpaw_itr_bits`) gives bits
  per selection for an N-way forced choice with accuracy P. It assumes
  that every trial gives an output, that errors spread evenly over the
  N - 1 wrong classes, and that an error costs nothing extra. eWPM drops
  these assumptions. It charges the real time of a correction and of a
  repeat, and it gives zero credit, but no extra cost, for an
  abstention. So an abstention is better than a wrong commit when the
  correction costs more than the abstention overhead.
- **RAS** (arXiv 2604.24278), as we read the project brief, is a score
  that rewards abstention over a wrong answer. eWPM gets the same
  ordering from time costs, not from a fixed reward. We did not check
  the RAS formula against the paper; do not cite this comparison until
  someone has read it.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from fidetype.trust._align import cached_edit_distance


@dataclass
class SentenceRecord:
    """The full interaction for one intended sentence."""

    truth: str
    final_text: str | None
    communicated: bool
    time_s: float
    actions: list[str] = field(default_factory=list)
    committed_text: str | None = None
    wrong_commit: bool = False
    silent_error: bool = False
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def n_words(self) -> int:
        return len(self.truth.split())

    @property
    def n_attempts(self) -> int:
        return sum(a != "REPEAT" for a in self.actions)


def correct_words_strict(r: SentenceRecord) -> int:
    return r.n_words if r.communicated else 0


def correct_words_partial(r: SentenceRecord) -> int:
    if r.final_text is None:
        return 0
    d = cached_edit_distance(tuple(r.final_text.split()), tuple(r.truth.split()))
    return max(0, r.n_words - d)


def effective_wpm(records: Sequence[SentenceRecord], partial: bool = False) -> float:
    """Return eWPM (see the module docstring)."""
    t = sum(r.time_s for r in records)
    if t <= 0:
        return 0.0
    f = correct_words_partial if partial else correct_words_strict
    return 60.0 * sum(f(r) for r in records) / t


def wolpaw_itr_bits(n_classes: int, p_correct: float) -> float:
    """Wolpaw information transfer rate, in bits per selection."""
    n, p = n_classes, p_correct
    if n < 2:
        return 0.0
    if p <= 1.0 / n:
        return 0.0
    bits = math.log2(n) + p * math.log2(p)
    if p < 1.0:
        bits += (1 - p) * math.log2((1 - p) / (n - 1))
    return bits


def summarize(records: Sequence[SentenceRecord]) -> dict[str, float]:
    """Return eWPM, safety metrics and action rates for a session."""
    n = len(records)
    if n == 0:
        return {}
    decisions = Counter(a for r in records for a in r.actions if a != "REPEAT")
    n_dec = sum(decisions.values())
    final = Counter(r.actions[-1] if r.actions else "NONE" for r in records)
    committed = [r for r in records if r.committed_text is not None]
    ed = sum(cached_edit_distance(r.committed_text, r.truth) for r in committed)
    chars = sum(len(r.truth) for r in committed)
    out = {
        "n_sentences": float(n),
        "ewpm": effective_wpm(records),
        "ewpm_partial": effective_wpm(records, partial=True),
        "communicated_rate": float(np.mean([r.communicated for r in records])),
        "wrong_commit_rate": float(np.mean([r.wrong_commit for r in records])),
        "silent_error_rate": float(np.mean([r.silent_error for r in records])),
        "abstain_rate": final.get("ABSTAIN", 0) / n,
        "committed_cer": ed / chars if chars else math.nan,
        "commit_share": len(committed) / n,
        "mean_time_s": float(np.mean([r.time_s for r in records])),
        "mean_attempts": float(np.mean([r.n_attempts for r in records])),
    }
    for a in ("COMMIT", "OFFER", "ASK", "ABSTAIN"):
        out[f"rate_{a.lower()}"] = decisions.get(a, 0) / n_dec if n_dec else 0.0
    return out
