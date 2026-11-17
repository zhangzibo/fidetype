"""Precision-type guarantee: "when it types, it is right" (P5-02).

Problem
-------
The P14-03 drop-in guard bounds the **marginal** wrong-commit rate:
wrong COMMITs / all utterances <= alpha. A guard that commits rarely
meets that bound even if most of its commits are wrong (P14-03: T15 2 of
2 commits wrong, T12 15 of 25; F1 pilot: 88-100 % of commits wrong). A
user needs the other number: the error rate **among commits**.

What this module adds
---------------------
A distribution-free bound on the conditional risk

    R(lambda) = P(commit is wrong | the guard commits at threshold lambda)

with Learn then Test (LTT) over the commit threshold ``lambda``
(``commit_p``, the threshold on the calibrated ``p_top1``):

1. **Valid p-value per threshold.** Fix ``lambda``. With exchangeable
   items, the items that commit at ``lambda`` are, given their number
   ``n``, an exchangeable sample of the commit distribution. So the
   number of wrong commits ``k`` is ``Binomial(n, R(lambda))`` given
   ``n``. The exact p-value of ``H_lambda: R(lambda) > beta`` is
   ``P(Bin(n, beta) <= k)`` (1.0 if ``n = 0``). It is valid given ``n``,
   so also without the condition. ``beta = 1 - target_precision``.
   ``p <= delta`` is the same test as "the one-sided Clopper-Pearson
   upper bound at confidence ``1 - delta`` is at most ``beta``"
   (:func:`fidetype.utils.binomial.cp_upper`).
2. **Test order from separate data.** ``R(lambda)`` is not monotone in
   ``lambda``, and a strict threshold has few commits (``p = 1``). So the
   order is not "strict to loose". The order comes from an **ordering**
   split: smallest p-value there first; ties: more commits, then the
   stricter threshold. The order does not depend on the test split.
3. **Fixed-sequence test** on the **test** split: certify the chain
   prefix whose p-values are all ``<= delta``. With exchangeable data,
   ``P(every certified lambda has R(lambda) <= beta) >= 1 - delta``.
   Any selection rule among the certified thresholds keeps the guarantee.

Selection (fixed): among certified thresholds with ``commit_p >=
min_commit_p``, the one with the most commits on ordering + test items,
then the stricter one. If none is certified, the guard never commits
(``commit_p = inf``).

Composition with the drop-in guard
----------------------------------
:func:`fidetype.trust.calibrate` (``target_precision=``) uses the
policy-grid items as the ordering split and the LTT items as the test
split, and passes the P14-03 threshold as ``min_commit_p``. A higher
``commit_p`` only removes commits, so the P14-03 marginal bound and the
null controls still hold. Both statements together hold with probability
at least ``1 - delta - delta_p`` (union bound).

This module needs no decoder. It works on per-item statistics
(:class:`PrecisionItem`). Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from fidetype.trust.risk_control import binomial_pvalue
from fidetype.utils.binomial import cp_upper

__all__ = [
    "DEFAULT_COMMIT_P_GRID",
    "PrecisionItem",
    "PrecisionLTTResult",
    "min_commits_needed",
    "precision_counts",
    "precision_curve",
    "precision_ltt",
    "precision_pvalue",
]

#: Default commit thresholds (the P14-03 LTT grid): 1.00 -> 0.00 in steps of 0.01.
DEFAULT_COMMIT_P_GRID: tuple[float, ...] = tuple(round(1.0 - 0.01 * k, 2) for k in range(101))


@dataclass(frozen=True)
class PrecisionItem:
    """What :func:`precision_ltt` needs from one labelled item.

    ``can_commit``: the guard COMMITs this item at ``commit_p = 0`` (all
    other commit conditions and the commit gate pass). ``p_top1``: the
    calibrated probability of the top-1 text. ``wrong``: the top-1 text
    is not the true text. The item commits at ``lambda`` if
    ``can_commit and p_top1 >= lambda``.
    """

    can_commit: bool
    p_top1: float
    wrong: bool


def _arrays(items: Sequence[PrecisionItem]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    can = np.array([it.can_commit for it in items], dtype=bool)
    p = np.array([it.p_top1 for it in items], dtype=np.float64)
    wrong = np.array([it.wrong for it in items], dtype=bool)
    return can, p, wrong


def precision_counts(items: Sequence[PrecisionItem], commit_p: float) -> dict[str, int]:
    """Commits and wrong commits of ``items`` at threshold ``commit_p``."""
    can, p, wrong = _arrays(items)
    return _counts(can, p, wrong, commit_p)


def _counts(can: np.ndarray, p: np.ndarray, wrong: np.ndarray, commit_p: float) -> dict[str, int]:
    com = can & (p >= commit_p)
    return {"n": int(can.shape[0]), "commits": int(com.sum()), "wrong": int((com & wrong).sum())}


def precision_pvalue(wrong: int, commits: int, beta: float) -> float:
    """Exact p-value of ``H: P(wrong | commit) > beta``: ``P(Bin(commits, beta) <= wrong)``; 1.0 for no commits."""
    if commits <= 0:
        return 1.0
    return binomial_pvalue(wrong / commits, commits, beta)


def min_commits_needed(target_precision: float, delta: float) -> int:
    """Fewest commits (all right) that can certify ``target_precision`` at level ``delta``.

    ``n >= log(delta) / log(target_precision)``; for 0.95 and 0.1 it is 45.
    """
    if not (0.0 < target_precision < 1.0 and 0.0 < delta < 1.0):
        raise ValueError("target_precision and delta must be in (0, 1)")
    return int(math.ceil(math.log(delta) / math.log(target_precision) - 1e-12))


def precision_curve(items: Sequence[PrecisionItem], grid: Iterable[float] = DEFAULT_COMMIT_P_GRID) -> list[dict[str, Any]]:
    """Commits, wrong commits and precision per threshold (a diagnostic; no guarantee)."""
    can, p, wrong = _arrays(items)
    out = []
    for c in grid:
        k = _counts(can, p, wrong, float(c))
        out.append({"commit_p": float(c), "commits": k["commits"], "wrong": k["wrong"],
                    "precision": (1.0 - k["wrong"] / k["commits"]) if k["commits"] else None})
    return out


@dataclass
class PrecisionLTTResult:
    """Output of :func:`precision_ltt`."""

    #: The selected threshold, or None (no threshold certified: never commit).
    selected: float | None
    #: Every certified threshold (the chain prefix), in test order.
    certified: list[float]
    chain_length: int
    n_tested: int
    target_precision: float
    delta: float
    n_order: int
    n_test: int
    min_commit_p: float = -math.inf
    #: Counts of the selected threshold on the ordering and test items.
    order_counts: dict[str, int] = field(default_factory=dict)
    test_counts: dict[str, int] = field(default_factory=dict)
    test_pvalue: float = math.nan

    @property
    def feasible(self) -> bool:
        return self.selected is not None

    @property
    def beta(self) -> float:
        return 1.0 - self.target_precision

    @property
    def test_precision_lower(self) -> float | None:
        """``1 -`` the one-sided Clopper-Pearson upper bound (confidence ``1 - delta``) on the test commits.

        Descriptive: the guarantee is the certification, not this number.
        """
        if not self.test_counts or not self.test_counts.get("commits"):
            return None
        return 1.0 - cp_upper(self.test_counts["wrong"], self.test_counts["commits"], self.delta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": _jf(self.selected) if self.selected is not None else None,
            "feasible": self.feasible, "target_precision": self.target_precision, "beta": self.beta,
            "delta": self.delta, "n_certified": len(self.certified), "chain_length": self.chain_length,
            "n_tested": self.n_tested, "n_order": self.n_order, "n_test": self.n_test,
            "min_commit_p": _jf(self.min_commit_p), "order_counts": dict(self.order_counts),
            "test_counts": dict(self.test_counts),
            "test_pvalue": None if math.isnan(self.test_pvalue) else float(self.test_pvalue),
            "test_precision_lower": self.test_precision_lower,
        }


def _jf(x: float) -> float | str:
    return x if math.isfinite(x) else ("inf" if x > 0 else "-inf")


def precision_ltt(order_items: Sequence[PrecisionItem], test_items: Sequence[PrecisionItem],
                  grid: Iterable[float] = DEFAULT_COMMIT_P_GRID, *, target_precision: float, delta: float,
                  min_commit_p: float = -math.inf) -> PrecisionLTTResult:
    """Learn then Test for ``P(wrong | commit) <= 1 - target_precision`` over the thresholds ``grid``.

    See the module docstring. ``order_items`` set the test order only; ``test_items`` certify. With
    exchangeable items: ``P(every certified threshold has precision >= target_precision) >= 1 - delta``.
    ``min_commit_p`` limits the selection only (not the test), so it may depend on the test items.
    """
    if not (0.0 < target_precision < 1.0 and 0.0 < delta < 1.0):
        raise ValueError("target_precision and delta must be in (0, 1)")
    thr = sorted({float(c) for c in grid if math.isfinite(float(c))}, reverse=True)
    if not thr:
        raise ValueError("the grid has no finite threshold")
    beta = 1.0 - float(target_precision)
    co, po, wo = _arrays(order_items)
    ct, pt, wt = _arrays(test_items)
    keyed = []
    for c in thr:
        ko = _counts(co, po, wo, c)
        keyed.append((precision_pvalue(ko["wrong"], ko["commits"], beta), -ko["commits"], -c, c, ko))
    keyed.sort(key=lambda r: (r[0], r[1], r[2]))
    certified: list[tuple[float, dict[str, int], dict[str, int], float]] = []
    n_tested = 0
    for pv_o, _, _, c, ko in keyed:
        kt = _counts(ct, pt, wt, c)
        pv = precision_pvalue(kt["wrong"], kt["commits"], beta)
        n_tested += 1
        if pv > delta:
            break
        certified.append((c, ko, kt, pv))
    res = PrecisionLTTResult(None, [r[0] for r in certified], len(keyed), n_tested, float(target_precision),
                             float(delta), len(order_items), len(test_items), float(min_commit_p))
    pool = [r for r in certified if r[0] >= min_commit_p]
    if pool:
        c, ko, kt, pv = min(pool, key=lambda r: (-(r[1]["commits"] + r[2]["commits"]), -r[0]))
        res.selected, res.order_counts, res.test_counts, res.test_pvalue = c, ko, kt, pv
    return res


def items_from_dicts(rows: Sequence[Mapping[str, Any]]) -> list[PrecisionItem]:
    """:class:`PrecisionItem` list from dicts with ``can_commit``, ``p_top1`` and ``wrong``."""
    return [PrecisionItem(bool(r["can_commit"]), float(r["p_top1"]), bool(r["wrong"])) for r in rows]
