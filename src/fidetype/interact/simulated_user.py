"""A simulated user for offline evaluation of the decision policy.

The user answers one :class:`~fidetype.trust.policy.Decision` for one
intended sentence. The model returns the time spent, the final text and
whether the intended sentence was communicated. All time costs are in
seconds. They are configurable in :class:`UserConfig`.

There are two correction models:

- **Sentence model** (``partial_correction=False``, the default, the old
  model): the user corrects a wrong text at a cost per edited character.
- **Word model** (``partial_correction=True``, see
  :meth:`UserConfig.aac_gaze`): the user fixes the wrong *words* one by
  one with a slow fallback method (for example a gaze keyboard). This is
  how AAC users fix a sentence that is almost right. OFFER_WORDS always
  uses the word model.

Time model, sentence model
--------------------------
``typing_time(text)``
    ``len(text) / (chars_per_min / 60)``. Default 152 chars/min, the
    typing speed of the Brain2Qwerty v1 participants. This is the time of
    one neural input attempt. The harness charges it for the first input
    and for each repeat.
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
    ``abstain_overhead_s``. Nothing is written. The sentence is lost
    (unless ``fallback_after_abstain``: then the user types the sentence
    with the fallback method).
Repeat
    ``repeat_overhead_s + typing_time(text)``. The harness charges it when
    it starts the next attempt.

Time model, word model
----------------------
The user aligns the shown sentence to the intended sentence word by word
(the slot convention of ``fidetype.lm.word_alternatives``). Each slot of
the shown sentence holds the intended text for that slot: one word, two
words, or "" (the shown word is extra). A slot is wrong if the two
differ. Fallback typing costs ``60 / fallback_chars_per_min`` per
character.

OFFER_WORDS
    Read the sentence (``read_time``). For each highlighted slot, scan
    its k alternatives: Hick-Hyman ``word_scan_a_s +
    word_scan_b_s_per_bit * log2(k + 1)`` (the +1 is the "type it"
    choice). If the slot is right, do nothing. If the intended text is
    among the alternatives, select it (``word_select_s``, 1 keystroke).
    Else select "type it" (``word_select_s``, 1 keystroke) and type the
    text with the fallback method. Each wrong slot that is *not*
    highlighted: the user misses it with probability
    ``p_miss_unflagged`` (it stays: a silent error), or fixes it:
    ``nav_s`` (``nav_keystrokes``: select the word, which also deletes
    it) plus fallback typing. Then the user confirms the sentence
    (``word_select_s``, 1 keystroke) if ``confirm_offer_words``.
COMMIT (word model)
    Read the sentence (if ``verify_commit``). Every slot is unflagged, so
    each wrong slot is missed or fixed as above. No confirm.
OFFER (word model)
    As in the sentence model, but a selected wrong candidate is fixed
    word by word (all errors seen: the user compares candidates on
    purpose). If no candidate is selected and no repeat is possible, the
    user retypes the sentence (if ``allow_full_retype``).
Full retype (``allow_full_retype``)
    If fixing the seen errors costs more than ``retype_overhead_s`` plus
    the fallback typing of the whole sentence, the user clears the text
    and types it all. This assumes a rational user who can judge the
    cost after reading. Retyped text has no silent error.

Keystrokes count the actions of the fallback method only: selections,
navigation, typed characters, confirms. The neural input is not a
keystroke. In the sentence model the count is approximate: 1 per
selection, ``1 + 2 * edit_distance`` per correction (delete + retype).

Sources for the default values
------------------------------
- [Cai24] Cai et al. 2024, "Using large language models to accelerate
  communication for eye gaze typing users with ALS", Nat. Commun.
  (SpeakFaster). Local: references/papers/reading-list/07-09/
  cai2024-llm-accelerate-eye-gaze-typing.txt.
- [SM03] Soukoreff & MacKenzie 2003, "Metrics for text entry research:
  an evaluation of MSD and KSPC, and a new unified error metric", CHI.
  Local: .../07-09/soukoreff2003-metrics-text-entry-msd-kspc.txt.

Default values (sentence model: assumptions, not measurements)
--------------------------------------------------------------
- Reading: 200 words/min (0.3 s/word) plus 0.5 s per candidate.
- Hick-Hyman: a = 1.0 s, b = 0.5 s/bit. A BCI selection is slower than a
  key press, so b is larger than the keyboard value (about 0.15 s/bit).
  Check: read + select of 5 phrase options of 7 words is about 15 s with
  these values. [Cai24] measured 12.7 s (scripted) and 21.2 s
  (unscripted) for an eye-gaze user to select among 5 LLM phrase options
  (Fig. 7B text). So the values are in the measured range.
- Correction: 2.0 s overhead (find the error, move the cursor) plus
  2 x the typing time of one character for each edit (delete, retype).
- p_detect_error = 0.9: the user misses 1 in 10 wrong commits.
- Repeat overhead 1.0 s, ASK overhead 0.5 s, ABSTAIN overhead 0.5 s.

Default values (word model)
---------------------------
- ``fallback_chars_per_min = 20``: [Cai24] eye-gaze user LP1 typed at
  4.05 WPM (scripted) and 4.37 WPM (unscripted) with the Tobii gaze
  keyboard baseline; 1 WPM = 5 characters/min, so 20-22 chars/min. The
  field user FP1 typed at 8.1 WPM (40 chars/min) over 6 months. LP1's
  inter-key interval was 3.5-5.0 s. We take the slower user (measured).
- Per-slot scan + select = 1.0 + 1.0 * log2(3 + 1) + 1.5 = 4.5 s for
  k = 3. [Cai24] measured 4.7 s (unscripted) and 7.0 s (scripted) for
  the eye-gaze user to select a single-word FillMask option (Fig. 7B
  text). The split into a, b and ``word_select_s`` is an **assumption**;
  only the sum is matched to the measurement.
- ``word_select_s = 1.5`` s: one gaze selection of a highlighted target
  (dwell plus gaze travel). **Assumption** (no direct source here; a
  full-keyboard key in [Cai24] costs 3.5-5.0 s because it includes the
  visual search over the keyboard).
- ``nav_s = 3.0`` s, 2 keystrokes: select the sentence, then the wrong
  word (as in the FillMask flow of [Cai24], Fig. 3: click the phrase,
  then the word "chip"). These are editing keystrokes (class F in
  [SM03]). Time = 2 x ``word_select_s``. **Assumption.**
- ``p_miss_unflagged = 0.05`` per wrong unhighlighted word.
  **Assumption.** [SM03] separates "corrected" from "not corrected"
  errors; a missed error is a not-corrected error (our silent error).
  We have no measured miss rate for AAC users.
- ``retype_overhead_s = 1.5`` s, 1 keystroke (one "clear" selection).
  **Assumption.**
- The neural input stays at 152 chars/min (the Brain2Qwerty setting).
  A gaze AAC user would not type at this speed; the model mixes the
  decoder's input rate with the fallback rate of the target users.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from functools import lru_cache

import numpy as np

from fidetype.trust._align import cached_edit_distance
from fidetype.trust.policy import Action, Decision

B2Q_CHARS_PER_MIN = 152.0
#: [Cai24]: eye-gaze user LP1, Tobii keyboard baseline, 4.05 WPM x 5.
GAZE_CHARS_PER_MIN = 20.0


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
    # --- word model (see the module docstring) ---
    #: Use the word model for COMMIT and OFFER corrections.
    partial_correction: bool = False
    fallback_chars_per_min: float = GAZE_CHARS_PER_MIN
    word_scan_a_s: float = 1.0
    word_scan_b_s_per_bit: float = 1.0
    word_select_s: float = 1.5
    nav_s: float = 3.0
    nav_keystrokes: int = 2
    p_miss_unflagged: float = 0.05
    confirm_offer_words: bool = True
    allow_full_retype: bool = True
    retype_overhead_s: float = 1.5
    #: After ABSTAIN, the user types the sentence with the fallback method.
    fallback_after_abstain: bool = False

    @classmethod
    def aac_gaze(cls, **overrides) -> "UserConfig":
        """The word model with the default (literature-based) values.

        Partial correction on; the user types an abstained sentence with
        the fallback method (a gaze keyboard at 20 chars/min).
        """
        return replace(cls(partial_correction=True, fallback_after_abstain=True), **overrides)


@dataclass
class Outcome:
    """Result of one response. ``time_s`` excludes typing time.

    ``words_system`` / ``words_selected`` / ``words_typed`` split the
    intended words that are right at the end: shown right by the system,
    selected by the user from system alternatives (a word choice or a
    whole candidate), or typed by the user. ``keystrokes`` counts the
    fallback-method actions (see the module docstring).
    """

    time_s: float
    final_text: str | None
    communicated: bool
    needs_repeat: bool = False
    wrong_commit: bool = False
    silent_error: bool = False
    corrected: bool = False
    breakdown: dict[str, float] = field(default_factory=dict)
    words_system: int = 0
    words_selected: int = 0
    words_typed: int = 0
    keystrokes: int = 0
    #: Word model: number of wrong slots and of missed wrong slots.
    n_wrong_slots: int = 0
    n_missed: int = 0


class _Truth:
    """A minimal hypothesis object for ``word_alternatives``."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.score = 0.0


def slot_targets(shown: str, truth: str) -> list[str]:
    """Return the intended text of each word slot of ``shown``.

    Uses the slot convention of :func:`fidetype.lm.word_alternatives`
    (word-level Levenshtein alignment; an inserted word joins the slot
    before it). Each item is one word, several words, or "".
    """
    return list(_slot_targets(shown, truth))


@lru_cache(maxsize=200_000)
def _slot_targets(shown: str, truth: str) -> tuple[str, ...]:
    if not shown.split():
        return ()
    from fidetype.lm import word_alternatives  # lazy: interact does not need the LM otherwise

    slots = word_alternatives([_Truth(truth)], reference=shown, posteriors=[1.0], max_alternatives=1)
    return tuple(s.alternatives[0][0] if s.alternatives else "" for s in slots)


def _nwords(text: str) -> int:
    return len(text.split())


class SimulatedUser:
    def __init__(self, config: UserConfig | None = None, seed: int = 0) -> None:
        self.config = config or UserConfig()
        self._rng = np.random.default_rng(seed)

    # --- elementary costs ------------------------------------------------

    def typing_time(self, text: str) -> float:
        return len(text) / (self.config.chars_per_min / 60.0)

    def fallback_typing_time(self, text: str) -> float:
        """Time to type ``text`` with the fallback method (word model)."""
        return len(text) / (self.config.fallback_chars_per_min / 60.0)

    def repeat_cost(self, text: str) -> float:
        return self.config.repeat_overhead_s + self.typing_time(text)

    def retype_cost(self, text: str) -> float:
        """Clear the text and type ``text`` with the fallback method."""
        return self.config.retype_overhead_s + self.fallback_typing_time(text)

    def read_time(self, text: str) -> float:
        c = self.config
        return c.read_s_per_candidate + c.read_s_per_word * len(text.split())

    def selection_time(self, k: int) -> float:
        c = self.config
        return c.select_a_s + c.select_b_s_per_bit * math.log2(k + 1)

    def word_scan_time(self, k: int) -> float:
        """Hick-Hyman time to scan k word alternatives (+1 "type it" choice)."""
        c = self.config
        return c.word_scan_a_s + c.word_scan_b_s_per_bit * math.log2(k + 1)

    def correction_time(self, hyp: str, truth: str) -> float:
        d = cached_edit_distance(hyp, truth)
        if d == 0:
            return 0.0
        c = self.config
        return c.correction_overhead_s + c.correction_s_per_char * d

    def unflagged_fix(self, target: str) -> tuple[float, int]:
        """Time and keystrokes to fix one unhighlighted wrong slot."""
        c = self.config
        return c.nav_s + self.fallback_typing_time(target), c.nav_keystrokes + len(target)

    # --- word model --------------------------------------------------------

    def _word_pass(
        self,
        shown: str,
        truth: str,
        flagged: dict[int, tuple[str, ...]],
        rng: np.random.Generator,
        miss_unflagged: bool,
    ) -> dict:
        """Plan the word-by-word correction of ``shown``.

        ``flagged`` maps slot index -> shown alternatives. Unflagged wrong
        slots are missed with probability ``p_miss_unflagged`` if
        ``miss_unflagged``. Returns the times, keystrokes, word counts and
        the final text.
        """
        c = self.config
        words = shown.split()
        targets = slot_targets(shown, truth) if words else []
        out = {"scan": 0.0, "select": 0.0, "nav": 0.0, "type": 0.0, "keys": 0, "sys": 0, "sel": 0, "typed": 0,
               "wrong": 0, "missed": 0, "unflagged_wrong": 0}
        final: list[str] = []
        for i, (w, tgt) in enumerate(zip(words, targets)):
            if i in flagged:
                alts = flagged[i]
                out["scan"] += self.word_scan_time(len(alts))
                if tgt == w:
                    out["sys"] += 1
                    final.append(w)
                    continue
                out["wrong"] += 1
                out["select"] += c.word_select_s
                out["keys"] += 1
                if tgt in alts:
                    out["sel"] += _nwords(tgt)
                else:
                    out["type"] += self.fallback_typing_time(tgt)
                    out["keys"] += len(tgt)
                    out["typed"] += _nwords(tgt)
                final.append(tgt)
                continue
            if tgt == w:
                out["sys"] += 1
                final.append(w)
                continue
            out["wrong"] += 1
            out["unflagged_wrong"] += 1
            if miss_unflagged and rng.random() < c.p_miss_unflagged:
                out["missed"] += 1
                final.append(w)
                continue
            t, k = self.unflagged_fix(tgt)
            out["nav"] += c.nav_s
            out["type"] += t - c.nav_s
            out["keys"] += k
            out["typed"] += _nwords(tgt)
            final.append(tgt)
        if not words and truth:
            # Nothing shown: the whole sentence must be typed.
            out["wrong"] = 1
            out["type"] += self.fallback_typing_time(truth)
            out["keys"] += len(truth)
            out["typed"] += _nwords(truth)
            final = [truth]
        out["final"] = " ".join(x for x in final if x)
        out["fix_time"] = out["select"] + out["nav"] + out["type"]
        return out

    def _retype(self, truth: str, t_before: float, base: dict[str, float], **flags) -> Outcome:
        t = self.retype_cost(truth)
        return Outcome(
            t_before + t, truth, True, corrected=True, breakdown={**base, "retype": t},
            words_typed=_nwords(truth), keystrokes=1 + len(truth), **flags,
        )

    def _respond_words(self, shown: str, truth: str, flagged: dict[int, tuple[str, ...]], rng, *,
                       read: bool, confirm: bool, wrong_commit_mode: str) -> Outcome:
        """COMMIT or OFFER_WORDS in the word model."""
        c = self.config
        t_read = self.read_time(shown) if read else 0.0
        p = self._word_pass(shown, truth, flagged, rng, miss_unflagged=True)
        if wrong_commit_mode == "commit":
            wrong_commit = shown != truth
        else:  # OFFER_WORDS: the system asserted the unflagged words
            wrong_commit = p["unflagged_wrong"] > 0
        t_conf = c.word_select_s if confirm else 0.0
        if shown == truth and not flagged:
            return Outcome(t_read + t_conf, truth, True, breakdown={"read": t_read, "select": t_conf},
                           words_system=_nwords(truth), keystrokes=int(confirm))
        seen_fix = p["fix_time"]
        if c.allow_full_retype and p["wrong"] > 0 and seen_fix + p["scan"] > self.retype_cost(truth):
            return self._retype(truth, t_read, {"read": t_read}, wrong_commit=wrong_commit,
                                n_wrong_slots=p["wrong"])
        t = t_read + p["scan"] + seen_fix + t_conf
        ok = p["final"] == truth
        bd = {"read": t_read, "scan": p["scan"], "select": p["select"] + t_conf, "nav": p["nav"], "type": p["type"]}
        return Outcome(
            t, p["final"], ok, wrong_commit=wrong_commit, silent_error=not ok,
            corrected=p["wrong"] > p["missed"], breakdown=bd,
            words_system=p["sys"] if ok else 0, words_selected=p["sel"] if ok else 0,
            words_typed=p["typed"] if ok else 0, keystrokes=p["keys"] + int(confirm),
            n_wrong_slots=p["wrong"], n_missed=p["missed"],
        )

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
        if a == Action.OFFER_WORDS:
            shown = decision.shown_candidates[0] if decision.shown_candidates else ""
            flagged = {wc.index: tuple(wc.alternatives) for wc in decision.word_choices}
            return self._respond_words(shown, truth, flagged, rng, read=True, confirm=c.confirm_offer_words,
                                       wrong_commit_mode="offer_words")

        if a == Action.COMMIT:
            text = decision.shown_candidates[0] if decision.shown_candidates else ""
            if c.partial_correction:
                return self._respond_words(text, truth, {}, rng, read=c.verify_commit, confirm=False,
                                           wrong_commit_mode="commit")
            t_read = self.read_time(text) if c.verify_commit else 0.0
            n = _nwords(truth)
            if text == truth:
                return Outcome(t_read, text, True, breakdown={"read": t_read}, words_system=n)
            if rng.random() < c.p_detect_error:
                t_fix = self.correction_time(text, truth)
                ok_words = max(0, n - cached_edit_distance(tuple(text.split()), tuple(truth.split())))
                return Outcome(
                    t_read + t_fix, truth, True, wrong_commit=True, corrected=True,
                    breakdown={"read": t_read, "correct": t_fix},
                    words_system=ok_words, words_typed=n - ok_words,
                    keystrokes=1 + 2 * cached_edit_distance(text, truth),
                )
            return Outcome(t_read, text, False, wrong_commit=True, silent_error=True, breakdown={"read": t_read})

        if a == Action.OFFER:
            shown = list(decision.shown_candidates)
            k = len(shown)
            t_read = sum(self.read_time(s) for s in shown)
            t_sel = self.selection_time(k)
            base = {"read": t_read, "select": t_sel}
            n = _nwords(truth)
            if truth in shown:
                return Outcome(t_read + t_sel, truth, True, breakdown=base, words_selected=n, keystrokes=1)
            if c.p_accept_close > 0:
                for s in shown:
                    if cached_edit_distance(s, truth) <= c.close_max_cer * max(1, len(truth)):
                        if rng.random() < c.p_accept_close:
                            return Outcome(t_read + t_sel, s, False, silent_error=True, breakdown=base,
                                           keystrokes=1)
                        break
            if c.partial_correction:
                return self._offer_words_model(shown, truth, can_repeat, rng, t_read, t_sel, base)
            if c.select_and_correct and shown:
                best = min(shown, key=lambda s: cached_edit_distance(s, truth))
                t_fix = self.correction_time(best, truth)
                if not can_repeat or t_fix < self.repeat_cost(truth):
                    ok_words = max(0, n - cached_edit_distance(tuple(best.split()), tuple(truth.split())))
                    return Outcome(
                        t_read + t_sel + t_fix, truth, True, corrected=True,
                        breakdown={**base, "correct": t_fix},
                        words_selected=ok_words, words_typed=n - ok_words,
                        keystrokes=2 + 2 * cached_edit_distance(best, truth),
                    )
            # Reject all: the "none" choice also costs a selection.
            return Outcome(t_read + t_sel, None, False, needs_repeat=can_repeat, breakdown=base, keystrokes=1)

        if a == Action.ASK:
            t = c.ask_overhead_s
            return Outcome(t, None, False, needs_repeat=can_repeat, breakdown={"overhead": t})

        if a == Action.ABSTAIN:
            t = c.abstain_overhead_s
            if c.fallback_after_abstain and truth:
                return self._retype(truth, t, {"overhead": t})
            return Outcome(t, None, False, breakdown={"overhead": t})

        raise ValueError(f"unknown action {a!r}")

    def _offer_words_model(self, shown, truth, can_repeat, rng, t_read, t_sel, base) -> Outcome:
        """OFFER without the target, word model: select the closest
        candidate and fix it word by word, repeat, or retype."""
        c = self.config
        t0 = t_read + t_sel
        options: list[tuple[float, str, dict | None]] = []
        best_plan = None
        if c.select_and_correct and shown:
            best = min(shown, key=lambda s: cached_edit_distance(tuple(s.split()), tuple(truth.split())))
            best_plan = self._word_pass(best, truth, {}, rng, miss_unflagged=False)
            options.append((best_plan["fix_time"], "fix", best_plan))
        if can_repeat:
            options.append((self.repeat_cost(truth), "repeat", None))
        if c.allow_full_retype or not options:
            options.append((self.retype_cost(truth), "retype", None))
        cost, kind, plan = min(options, key=lambda o: o[0])
        if kind == "repeat":
            return Outcome(t0, None, False, needs_repeat=True, breakdown=base, keystrokes=1)
        if kind == "retype":
            o = self._retype(truth, t0, base)
            o.keystrokes += 1  # the "none of these" selection
            return o
        assert plan is not None
        bd = {**base, "select": t_sel + plan["select"], "nav": plan["nav"], "type": plan["type"]}
        return Outcome(
            t0 + plan["fix_time"], truth, True, corrected=True, breakdown=bd,
            words_selected=plan["sys"], words_typed=plan["typed"], keystrokes=1 + plan["keys"],
            n_wrong_slots=plan["wrong"],
        )
