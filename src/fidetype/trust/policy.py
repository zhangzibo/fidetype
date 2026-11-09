"""Trust core module e: the decision policy.

The policy reads three signals for one input and selects one action:

- ``p_top1``: the calibrated posterior of the top-1 sentence.
- ``set_size``: the size of the conformal sentence set (and whether it
  includes ``OTHER``).
- ``guard_risk``: the risk score of the hallucination guard, in [0, 1].

With ``offer_words`` it also reads the word slots of the top-1 sentence.

Actions
-------
``COMMIT``
    Write the top-1 text. Fast, but a wrong commit is a silent error if
    the user does not see it.
``OFFER``
    Show k candidates (the conformal set, best first, at most
    ``offer_max_k``). The user selects one, or rejects all.
``ASK``
    Ask the user to type the sentence again. The system then decodes a
    new attempt.
``ABSTAIN``
    Show no text. Use it when the guard says the text is not supported by
    the neural evidence (for example, no real input).
``OFFER_WORDS`` (only if ``PolicyConfig.offer_words`` is true)
    Show the top-1 sentence. Highlight each word slot with a low
    confidence, and show its ``offer_words_k`` best alternatives. The
    user corrects the sentence word by word. The policy needs
    ``PolicyInputs.word_slots`` for this action (the harness fills it
    from ``fidetype.lm.word_alternatives``).

Rules, in this order
--------------------
1. ``guard_risk >= abstain_risk``  -> ABSTAIN.
2. ``p_top1 >= commit_p`` and ``guard_risk <= commit_max_risk`` and
   (``commit_max_set`` is None or ``set_size <= commit_max_set``)
   -> COMMIT.
3. ``1 <= set_size <= offer_max_k`` and not ``includes_other``
   -> OFFER the set.
4. Only if ``offer_words``: the top-1 sentence has word slots,
   ``word_confidence >= offer_words_min_conf``, and
   (``offer_words_max_slots`` is None or the number of highlighted slots
   is ``<= offer_words_max_slots``) -> OFFER_WORDS.
5. Otherwise ASK. On the final attempt (no repeat is possible), ASK is
   replaced by ``final_fallback``: OFFER the top ``offer_max_k`` (if
   ``offer_max_k >= 1``) or ABSTAIN.

Word slots
----------
A word slot is one word of the top-1 sentence with its alternatives and
their posterior mass (see :class:`WordSlotInfo`). The *slot confidence*
is the mass of the top-1 word in its own slot. A slot is highlighted if
its confidence is ``< word_conf_threshold``. ``word_confidence`` (the
sentence-level signal of rule 4) is the mean slot confidence.

Backward compatibility: with the default ``offer_words=False`` the
policy never reads the word slots and gives the same decisions as
before. :data:`DEFAULT_GRID` does not change.

:func:`fit_thresholds` selects the thresholds on a validation set. It
maximises effective WPM subject to a maximum wrong-commit rate (and,
optionally, a maximum silent-error rate). :data:`OFFER_WORDS_GRID` is
the grid of the OFFER_WORDS thresholds.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable, Literal, Sequence


class Action(str, Enum):
    COMMIT = "COMMIT"
    OFFER = "OFFER"
    ASK = "ASK"
    ABSTAIN = "ABSTAIN"
    OFFER_WORDS = "OFFER_WORDS"


@dataclass(frozen=True)
class WordSlotInfo:
    """One word slot of the top-1 sentence, as the policy sees it.

    ``alternatives`` holds (text, posterior mass) pairs, best first. A
    text can be "" (no word in that hypothesis) or two words (a split).
    :class:`fidetype.lm.WordSlot` objects have the same attributes, so
    the policy accepts them too.
    """

    word: str
    alternatives: tuple[tuple[str, float], ...]

    @property
    def confidence(self) -> float:
        """Posterior mass of the top-1 word in this slot."""
        return slot_confidence(self)


def slot_confidence(slot: Any) -> float:
    """Return the mass of ``slot.word`` among ``slot.alternatives`` (0 if absent)."""
    return float(next((m for a, m in slot.alternatives if a == slot.word), 0.0))


@dataclass(frozen=True)
class WordChoice:
    """One highlighted word slot of an OFFER_WORDS decision."""

    #: Index of the word in ``top1.split()``.
    index: int
    #: The top-1 word (shown in the sentence).
    word: str
    #: The alternatives shown to the user, best first (at most k). They
    #: can include ``word``.
    alternatives: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class PolicyInputs:
    """The signals of one input, as the policy sees them."""

    #: Candidate texts, ranked by calibrated posterior (best first).
    texts: tuple[str, ...]
    p_top1: float
    #: Indices (into ``texts``) of the conformal set, best first.
    set_indices: tuple[int, ...]
    includes_other: bool = False
    guard_risk: float = 0.0
    #: One slot per word of ``texts[0]`` (objects with ``word`` and
    #: ``alternatives``). Empty if not computed. Only OFFER_WORDS reads it.
    word_slots: tuple[Any, ...] = ()

    @property
    def set_size(self) -> int:
        return len(self.set_indices)

    @property
    def word_confidence(self) -> float:
        """Mean slot confidence of the top-1 sentence (nan if no slots)."""
        if not self.word_slots:
            return math.nan
        return sum(slot_confidence(s) for s in self.word_slots) / len(self.word_slots)


@dataclass(frozen=True)
class Decision:
    action: Action
    shown_candidates: tuple[str, ...] = ()
    reason: str = ""
    #: OFFER_WORDS only: the highlighted slots of ``shown_candidates[0]``.
    word_choices: tuple[WordChoice, ...] = ()


@dataclass(frozen=True)
class PolicyConfig:
    commit_p: float = 0.8
    commit_max_risk: float = 1.0
    commit_max_set: int | None = None
    offer_max_k: int = 5
    abstain_risk: float = 1.01  # > 1 means "never abstain on risk"
    final_fallback: Literal["offer", "abstain"] = "offer"
    #: Enable OFFER_WORDS (rule 4). False keeps the old policy exactly.
    offer_words: bool = False
    #: Highlight a slot if its confidence is below this value. 0 means no
    #: highlight; a value above 1 highlights every slot.
    word_conf_threshold: float = 0.9
    #: Number of alternatives shown per highlighted slot.
    offer_words_k: int = 3
    #: Use OFFER_WORDS (not ASK) only if the mean slot confidence of the
    #: top-1 sentence is at least this value.
    offer_words_min_conf: float = 0.0
    #: Use OFFER_WORDS only if at most this many slots are highlighted.
    offer_words_max_slots: int | None = None


def highlight_slots(slots: Sequence[Any], threshold: float, k: int) -> tuple[WordChoice, ...]:
    """Return a :class:`WordChoice` for each slot with confidence < ``threshold``.

    Each choice shows the ``k`` best alternatives of the slot, best
    first. The top-1 word is among them if its mass is in the top k.
    """
    out = []
    for i, s in enumerate(slots):
        conf = slot_confidence(s)
        if conf < threshold:
            alts = tuple(a for a, _ in list(s.alternatives)[: max(0, k)])
            out.append(WordChoice(i, s.word, alts, conf))
    return tuple(out)


class DecisionPolicy:
    """Threshold policy over (p_top1, conformal set size, guard risk)."""

    def __init__(self, config: PolicyConfig | None = None, use_guard: bool = True) -> None:
        self.config = config or PolicyConfig()
        self.use_guard = use_guard

    def decide(self, x: PolicyInputs, final_attempt: bool = False) -> Decision:
        c = self.config
        risk = x.guard_risk if self.use_guard else 0.0
        if not x.texts:
            return Decision(Action.ABSTAIN if final_attempt else Action.ASK, (), "no candidate")
        if risk >= c.abstain_risk:
            return Decision(Action.ABSTAIN, (), f"guard risk {risk:.2f} >= {c.abstain_risk:.2f}")
        set_ok = c.commit_max_set is None or x.set_size <= c.commit_max_set
        if x.p_top1 >= c.commit_p and risk <= c.commit_max_risk and set_ok:
            return Decision(Action.COMMIT, (x.texts[0],), f"p_top1 {x.p_top1:.2f} >= {c.commit_p:.2f}")
        if 1 <= x.set_size <= c.offer_max_k and not x.includes_other:
            shown = tuple(x.texts[i] for i in x.set_indices)
            return Decision(Action.OFFER, shown, f"conformal set of {x.set_size} <= {c.offer_max_k}")
        if c.offer_words:
            d = self._offer_words(x)
            if d is not None:
                return d
        if final_attempt:
            if c.final_fallback == "offer" and c.offer_max_k >= 1:
                return Decision(Action.OFFER, tuple(x.texts[: c.offer_max_k]), "final attempt: offer top-k")
            return Decision(Action.ABSTAIN, (), "final attempt: low confidence")
        return Decision(Action.ASK, (), f"p_top1 {x.p_top1:.2f} low; set of {x.set_size} too large")

    def _offer_words(self, x: PolicyInputs) -> Decision | None:
        c = self.config
        if not x.word_slots or len(x.word_slots) != len(x.texts[0].split()):
            return None
        wc = x.word_confidence
        if wc < c.offer_words_min_conf:
            return None
        choices = highlight_slots(x.word_slots, c.word_conf_threshold, c.offer_words_k)
        if c.offer_words_max_slots is not None and len(choices) > c.offer_words_max_slots:
            return None
        return Decision(
            Action.OFFER_WORDS,
            (x.texts[0],),
            f"word confidence {wc:.2f} >= {c.offer_words_min_conf:.2f}; {len(choices)} slots highlighted",
            choices,
        )


class AlwaysCommitPolicy:
    """Baseline: COMMIT the top-1 text every time."""

    def decide(self, x: PolicyInputs, final_attempt: bool = False) -> Decision:
        if not x.texts:
            return Decision(Action.COMMIT, ("",), "always commit (empty)")
        return Decision(Action.COMMIT, (x.texts[0],), "always commit")


DEFAULT_GRID: dict[str, Sequence[Any]] = {
    "commit_p": (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 1.01),
    "commit_max_risk": (0.1, 0.2, 0.3, 0.5, 1.0),
    "offer_max_k": (0, 1, 2, 3, 5, 8),
    "abstain_risk": (0.6, 0.8, 1.01),
    "final_fallback": ("offer", "abstain"),
}

#: Grid of the OFFER_WORDS thresholds. Pass it as ``word_grid`` to
#: :func:`fit_thresholds` (this also sets ``offer_words=True``).
OFFER_WORDS_GRID: dict[str, Sequence[Any]] = {
    "word_conf_threshold": (0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.01),
    "offer_words_min_conf": (0.0, 0.3, 0.5, 0.7, 0.9),
}


@dataclass
class FitResult:
    config: PolicyConfig
    metrics: dict[str, float]
    feasible: bool
    n_evaluated: int
    table: list[tuple[dict[str, Any], dict[str, float]]] = field(default_factory=list)


def fit_thresholds(
    evaluate_fn: Callable[[PolicyConfig], dict[str, float]],
    grid: dict[str, Sequence[Any]] | None = None,
    max_wrong_commit: float = 0.05,
    base: PolicyConfig | None = None,
    keep_table: bool = False,
    word_grid: dict[str, Sequence[Any]] | None = None,
    max_silent_error: float | None = None,
) -> FitResult:
    """Grid search for the policy thresholds.

    ``evaluate_fn(config)`` must return a dict with ``"ewpm"`` and
    ``"wrong_commit_rate"`` on a validation set. The function returns the
    config with the highest eWPM among those with ``wrong_commit_rate <=
    max_wrong_commit``. If no config is feasible, it returns the config
    with the lowest wrong-commit rate (ties: highest eWPM) and
    ``feasible=False``.

    ``word_grid`` (for example :data:`OFFER_WORDS_GRID`) adds the
    OFFER_WORDS thresholds to the search and sets ``offer_words=True``
    on the base config. ``max_silent_error`` (if not None) is a second
    limit, on ``"silent_error_rate"``. With the defaults (None, None)
    the search is the same as before.
    """
    grid = dict(DEFAULT_GRID if grid is None else grid)
    base = base or PolicyConfig()
    if word_grid is not None:
        grid.update(word_grid)
        base = replace(base, offer_words=True)
    keys = list(grid)
    best: tuple[PolicyConfig, dict[str, float]] | None = None
    fallback: tuple[PolicyConfig, dict[str, float]] | None = None
    table = []
    n = 0
    for values in itertools.product(*(grid[k] for k in keys)):
        cfg = replace(base, **dict(zip(keys, values)))
        m = evaluate_fn(cfg)
        n += 1
        if keep_table:
            table.append((asdict(cfg), m))
        ok_silent = max_silent_error is None or m.get("silent_error_rate", 0.0) <= max_silent_error + 1e-12
        if m["wrong_commit_rate"] <= max_wrong_commit + 1e-12 and ok_silent:
            if best is None or m["ewpm"] > best[1]["ewpm"] + 1e-12:
                best = (cfg, m)
        key = (m["wrong_commit_rate"], -m["ewpm"])
        if fallback is None or key < (fallback[1]["wrong_commit_rate"], -fallback[1]["ewpm"]):
            fallback = (cfg, m)
    assert fallback is not None, "empty grid"
    if best is not None:
        return FitResult(best[0], best[1], True, n, table)
    return FitResult(fallback[0], fallback[1], False, n, table)
