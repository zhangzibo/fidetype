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
  of the user. With the word model of the simulated user (partial
  correction, OFFER_WORDS), the user fixes single words. The sentence
  counts if the final text equals the target; it does not matter who
  made each word right.

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
  corrected it). For OFFER_WORDS, the system asserts the words that it
  does not highlight: the sentence counts as a wrong commit if one of
  them is wrong. The policy fit puts a limit on this rate.
- ``silent_error_rate``: share of sentences that end with a wrong text
  that the user did not correct (missed wrong commits, missed wrong
  words that were not highlighted, and accepted wrong-but-close
  offers). These errors reach the reader. This is the "not corrected
  error" of Soukoreff & MacKenzie (2003), at sentence level.
- ``abstain_rate``: share of sentences that end with ABSTAIN.
- ``committed_cer``: CER of the committed texts (before corrections),
  pooled over the sentences that end with a COMMIT.

Word-level and effort metrics
-----------------------------
- ``system_word_accuracy``: share of the intended words that the
  system's top-1 sentence (of the last attempt) has right, before any
  user action: ``sum_i max(0, words(y_i) - wed(top1_i, y_i)) / sum_i
  words(y_i)``. A sentence without a top-1 text counts 0.
- ``keystrokes_saved``: the keystroke saving rate (KSR) of AAC research
  (as in Cai et al. 2024), against typing every sentence with the
  fallback method (one keystroke per character, spaces included)::

      KSR = 1 - sum_i keystrokes_i / sum_i len(y_i)

  ``keystrokes_i`` counts the fallback-method actions of the user:
  selections, navigation, typed characters, confirms. The neural input
  is not counted. KSR = 1 means no fallback action; KSR < 0 means more
  actions than typing the sentence.
- ``share_words_system`` / ``share_words_selected`` /
  ``share_words_typed``: of all intended words, the share that ends
  right because the system showed it right, because the user selected it
  from system alternatives (a word choice or a whole candidate), or
  because the user typed it. They sum to ``communicated`` words / all
  words.

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
    #: Words right at the end: shown by the system / selected / typed.
    words_system: int = 0
    words_selected: int = 0
    words_typed: int = 0
    #: Fallback-method actions of the user (see ``keystrokes_saved``).
    keystrokes: int = 0
    #: Top-1 text of the last attempt (None if no text).
    system_text: str | None = None
    #: Wrong unhighlighted words that the user missed.
    n_missed: int = 0

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
    out["rate_offer_words"] = decisions.get("OFFER_WORDS", 0) / n_dec if n_dec else 0.0
    n_words = sum(r.n_words for r in records)
    n_chars = sum(len(r.truth) for r in records)
    out["system_word_accuracy"] = (
        sum(system_correct_words(r) for r in records) / n_words if n_words else math.nan
    )
    out["keystrokes_saved"] = 1.0 - sum(r.keystrokes for r in records) / n_chars if n_chars else math.nan
    for k in ("system", "selected", "typed"):
        out[f"share_words_{k}"] = sum(getattr(r, f"words_{k}") for r in records) / n_words if n_words else math.nan
    return out


def system_correct_words(r: SentenceRecord) -> int:
    """Intended words that the system's top-1 text has right (word alignment)."""
    if r.system_text is None:
        return 0
    d = cached_edit_distance(tuple(r.system_text.split()), tuple(r.truth.split()))
    return max(0, r.n_words - d)
