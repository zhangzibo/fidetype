"""Trust core module e: the decision policy.

The policy reads three signals for one input and selects one action:

- ``p_top1``: the calibrated posterior of the top-1 sentence.
- ``set_size``: the size of the conformal sentence set (and whether it
  includes ``OTHER``).
- ``guard_risk``: the risk score of the hallucination guard, in [0, 1].

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

Rules, in this order
--------------------
1. ``guard_risk >= abstain_risk``  -> ABSTAIN.
2. ``p_top1 >= commit_p`` and ``guard_risk <= commit_max_risk`` and
   (``commit_max_set`` is None or ``set_size <= commit_max_set``)
   -> COMMIT.
3. ``1 <= set_size <= offer_max_k`` and not ``includes_other``
   -> OFFER the set.
4. Otherwise ASK. On the final attempt (no repeat is possible), ASK is
   replaced by ``final_fallback``: OFFER the top ``offer_max_k`` (if
   ``offer_max_k >= 1``) or ABSTAIN.

:func:`fit_thresholds` selects the thresholds on a validation set. It
maximises effective WPM subject to a maximum wrong-commit rate.
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

    @property
    def set_size(self) -> int:
        return len(self.set_indices)


@dataclass(frozen=True)
class Decision:
    action: Action
    shown_candidates: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class PolicyConfig:
    commit_p: float = 0.8
    commit_max_risk: float = 1.0
    commit_max_set: int | None = None
    offer_max_k: int = 5
    abstain_risk: float = 1.01  # > 1 means "never abstain on risk"
    final_fallback: Literal["offer", "abstain"] = "offer"


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
        if final_attempt:
            if c.final_fallback == "offer" and c.offer_max_k >= 1:
                return Decision(Action.OFFER, tuple(x.texts[: c.offer_max_k]), "final attempt: offer top-k")
            return Decision(Action.ABSTAIN, (), "final attempt: low confidence")
        return Decision(Action.ASK, (), f"p_top1 {x.p_top1:.2f} low; set of {x.set_size} too large")


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
) -> FitResult:
    """Grid search for the policy thresholds.

    ``evaluate_fn(config)`` must return a dict with ``"ewpm"`` and
    ``"wrong_commit_rate"`` on a validation set. The function returns the
    config with the highest eWPM among those with ``wrong_commit_rate <=
    max_wrong_commit``. If no config is feasible, it returns the config
    with the lowest wrong-commit rate (ties: highest eWPM) and
    ``feasible=False``.
    """
    grid = dict(DEFAULT_GRID if grid is None else grid)
    base = base or PolicyConfig()
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
        if m["wrong_commit_rate"] <= max_wrong_commit + 1e-12:
            if best is None or m["ewpm"] > best[1]["ewpm"] + 1e-12:
                best = (cfg, m)
        key = (m["wrong_commit_rate"], -m["ewpm"])
        if fallback is None or key < (fallback[1]["wrong_commit_rate"], -fallback[1]["ewpm"]):
            fallback = (cfg, m)
    assert fallback is not None, "empty grid"
    if best is not None:
        return FitResult(best[0], best[1], True, n, table)
    return FitResult(fallback[0], fallback[1], False, n, table)
