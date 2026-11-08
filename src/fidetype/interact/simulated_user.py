"""A simulated user for offline evaluation of the decision policy.

The user answers one :class:`~fidetype.trust.policy.Decision` for one
intended sentence. The model returns the time spent, the final text and
whether the intended sentence was communicated. All time costs are in
seconds. They are configurable in :class:`UserConfig`.

Time model
----------
``typing_time(text)``
    ``len(text) / (chars_per_min / 60)``. Default 152 chars/min, the
    typing speed of the Brain2Qwerty v1 participants. The harness charges
    it for the first input and for each repeat.
COMMIT
    If ``verify_commit``: read the committed sentence
    (``read_s_per_candidate + read_s_per_word * words``). If the text is
    wrong, the user sees the error with probability ``p_detect_error``.
    Then the user corrects it: ``correction_overhead_s +
    correction_s_per_char * edit_distance``. If the user does not see the
    error, it stays: a *silent error*.
OFFER of k candidates
    Read all k candidates, then select: a Hick-Hyman term
    ``select_a_s + select_b_s_per_bit * log2(k + 1)`` (the +1 is the
    "none of these" choice). Then:

    1. The target is shown: select it. Communicated.
    2. Else, with probability ``p_accept_close``, accept the first shown
       candidate with CER <= ``close_max_cer`` (a wrong but close text).
       Default 0: the user accepts only the exact target.
    3. Else, if ``select_and_correct`` and the correction of the closest
       candidate costs less than a repeat (or no repeat is possible):
       select it and correct it. Communicated. The user looks at the
       candidates on purpose here, so the error is always seen.
    4. Else reject all. The user must repeat (``needs_repeat``).
ASK
    ``ask_overhead_s`` to read the request. Then the user repeats.
ABSTAIN
    ``abstain_overhead_s``. Nothing is written. The sentence is lost.
Repeat
    ``repeat_overhead_s + typing_time(text)``. The harness charges it when
    it starts the next attempt.

Default values (assumptions, not measurements)
----------------------------------------------
- Reading: 200 words/min (0.3 s/word) plus 0.5 s per candidate.
- Hick-Hyman: a = 1.0 s, b = 0.5 s/bit. A BCI selection is slower than a
  key press, so b is larger than the keyboard value (about 0.15 s/bit).
- Correction: 2.0 s overhead (find the error, move the cursor) plus
  2 x the typing time of one character for each edit (delete, retype).
- p_detect_error = 0.9: the user misses 1 in 10 wrong commits.
- Repeat overhead 1.0 s, ASK overhead 0.5 s, ABSTAIN overhead 0.5 s.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fidetype.trust._align import cached_edit_distance
from fidetype.trust.policy import Action, Decision

B2Q_CHARS_PER_MIN = 152.0


@dataclass(frozen=True)
class UserConfig:
    chars_per_min: float = B2Q_CHARS_PER_MIN
    read_s_per_word: float = 0.3
    read_s_per_candidate: float = 0.5
    select_a_s: float = 1.0
    select_b_s_per_bit: float = 0.5
    verify_commit: bool = True
    p_detect_error: float = 0.9
    correction_overhead_s: float = 2.0
    correction_s_per_char: float = 2.0 * 60.0 / B2Q_CHARS_PER_MIN
    p_accept_close: float = 0.0
    close_max_cer: float = 0.1
    select_and_correct: bool = True
    ask_overhead_s: float = 0.5
    abstain_overhead_s: float = 0.5
    repeat_overhead_s: float = 1.0


@dataclass
class Outcome:
    """Result of one response. ``time_s`` excludes typing time."""

    time_s: float
    final_text: str | None
    communicated: bool
    needs_repeat: bool = False
    wrong_commit: bool = False
    silent_error: bool = False
    corrected: bool = False
    breakdown: dict[str, float] = field(default_factory=dict)


class SimulatedUser:
    def __init__(self, config: UserConfig | None = None, seed: int = 0) -> None:
        self.config = config or UserConfig()
        self._rng = np.random.default_rng(seed)

    # --- elementary costs ------------------------------------------------

    def typing_time(self, text: str) -> float:
        return len(text) / (self.config.chars_per_min / 60.0)

    def repeat_cost(self, text: str) -> float:
        return self.config.repeat_overhead_s + self.typing_time(text)

    def read_time(self, text: str) -> float:
        c = self.config
        return c.read_s_per_candidate + c.read_s_per_word * len(text.split())

    def selection_time(self, k: int) -> float:
        c = self.config
        return c.select_a_s + c.select_b_s_per_bit * math.log2(k + 1)

    def correction_time(self, hyp: str, truth: str) -> float:
        d = cached_edit_distance(hyp, truth)
        if d == 0:
            return 0.0
        c = self.config
        return c.correction_overhead_s + c.correction_s_per_char * d

    # --- response --------------------------------------------------------

    def respond(
        self,
        decision: Decision,
        truth: str,
        can_repeat: bool = True,
        rng: np.random.Generator | None = None,
    ) -> Outcome:
        """Respond to one decision for the intended sentence ``truth``."""
        rng = rng if rng is not None else self._rng
        c = self.config
        a = decision.action
        if a == Action.COMMIT:
            text = decision.shown_candidates[0] if decision.shown_candidates else ""
            t_read = self.read_time(text) if c.verify_commit else 0.0
            if text == truth:
                return Outcome(t_read, text, True, breakdown={"read": t_read})
            if rng.random() < c.p_detect_error:
                t_fix = self.correction_time(text, truth)
                return Outcome(
                    t_read + t_fix, truth, True, wrong_commit=True, corrected=True,
                    breakdown={"read": t_read, "correct": t_fix},
                )
            return Outcome(t_read, text, False, wrong_commit=True, silent_error=True, breakdown={"read": t_read})

        if a == Action.OFFER:
            shown = list(decision.shown_candidates)
            k = len(shown)
            t_read = sum(self.read_time(s) for s in shown)
            t_sel = self.selection_time(k)
            base = {"read": t_read, "select": t_sel}
            if truth in shown:
                return Outcome(t_read + t_sel, truth, True, breakdown=base)
            if c.p_accept_close > 0:
                for s in shown:
                    if cached_edit_distance(s, truth) <= c.close_max_cer * max(1, len(truth)):
                        if rng.random() < c.p_accept_close:
                            return Outcome(t_read + t_sel, s, False, silent_error=True, breakdown=base)
                        break
            if c.select_and_correct and shown:
                best = min(shown, key=lambda s: cached_edit_distance(s, truth))
                t_fix = self.correction_time(best, truth)
                if not can_repeat or t_fix < self.repeat_cost(truth):
                    return Outcome(
                        t_read + t_sel + t_fix, truth, True, corrected=True,
                        breakdown={**base, "correct": t_fix},
                    )
            # Reject all: the "none" choice also costs a selection.
            return Outcome(t_read + t_sel, None, False, needs_repeat=can_repeat, breakdown=base)

        if a == Action.ASK:
            t = c.ask_overhead_s
            return Outcome(t, None, False, needs_repeat=can_repeat, breakdown={"overhead": t})

        if a == Action.ABSTAIN:
            t = c.abstain_overhead_s
            return Outcome(t, None, False, breakdown={"overhead": t})

        raise ValueError(f"unknown action {a!r}")
