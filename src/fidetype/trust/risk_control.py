"""Trust core module f: risk control for the COMMIT threshold.

The policy commits the top-1 text if its score (normally the calibrated
``p_top1``) is at least ``commit_p``. The fit in :mod:`fidetype.trust.policy`
selects ``commit_p`` with a plug-in limit: the *empirical* wrong-commit rate
on validation data must be <= alpha. That limit has no finite-sample
guarantee. On Brain-to-Text '25 the test rate was 0.059 for a 0.05 limit.

This module selects the threshold with a guarantee. Two methods:

``crc`` -- conformal risk control (Angelopoulos, Bates, Fisch, Lei &
Schuster, "Conformal Risk Control", ICLR 2024, arXiv:2208.02814, Thm. 1).
Guarantee (marginal, in expectation)::

    E[ L_{n+1}(lambda_hat) ] <= alpha

``ltt`` -- Learn then Test (Angelopoulos, Bates, Candes, Jordan & Lei,
arXiv:2110.01052) with fixed-sequence testing. Guarantee (high
probability)::

    P( R(lambda_hat) <= alpha ) >= 1 - delta

where R(lambda) is the true wrong-commit rate at threshold lambda.

Loss
----
For calibration item i with commit score ``s_i``::

    L_i(lambda) = c_i   if s_i >= lambda   (the policy commits)
                  f_i   otherwise          (the policy does something else)

``c_i`` = 1 if a commit would be wrong (top-1 != truth), else 0.
``f_i`` = the wrong-commit loss of the non-commit action (0 for OFFER,
ASK and ABSTAIN; it can be 1 for OFFER_WORDS, which asserts the words it
does not highlight). A sentence that the policy can never commit (for
example, its guard risk is too high) has ``s_i = -inf``.

Both methods need ``L_i`` to be non-increasing in lambda. We use
``max(c_i, f_i)`` in place of ``c_i``. This makes the loss monotone and
is an upper bound of the true loss, so the guarantees still hold. The
loss is in [0, B] with B = 1. At lambda = +inf (never commit) the loss
is ``f_i``.

CRC rule. With n calibration items and the empirical risk
``R_hat(lambda) = mean_i L_i(lambda)``::

    lambda_hat = min { lambda : (n * R_hat(lambda) + B) / (n + 1) <= alpha }

The minimum is over the unique calibration scores and +inf. (The paper
takes the infimum over a continuum with "commit if s > lambda". On the
calibration data our commit sets are the same; on new data ours commit
a subset, so ours is slightly more conservative and still valid.) If
even lambda = +inf fails the inequality (for example, n < B / alpha - 1
= 19 for alpha = 0.05), the result is ``feasible=False`` and the
threshold is +inf: never commit.

LTT rule. A fixed grid of thresholds, tested from the strictest (1.0)
down. For each lambda, H0: R(lambda) > alpha. The p-value is the
Hoeffding-Bentkus p-value (LTT, Prop. 3) or, for 0/1 losses, the exact
binomial tail ``P(Bin(n, alpha) <= n R_hat)``. Reject while p <= delta;
stop at the first acceptance. ``lambda_hat`` = the last rejected
lambda. If no lambda is rejected: +inf, ``feasible=False``.

Any threshold >= ``lambda_hat`` keeps the guarantee, because the loss is
non-increasing in lambda. So it is safe to tune commit_p for eWPM on the
same data and then take ``max(tuned, lambda_hat)`` (``combine="max"``).

Assumptions (read this before use)
----------------------------------
- **Exchangeability.** The calibration items and the new items must be
  exchangeable (for example, i.i.d. trials of one user in one session).
  Drift between sessions breaks the guarantee. Calibrate **per user and
  per session** (or per day), on items with known truth: for example a
  short copy-typing block at the start of the session. Re-calibrate
  after a model change or a long break. For a live stream with drift,
  see :class:`fidetype.trust.conformal.AdaptiveConformal`.
- **Fixed upstream parts.** Temperatures, conformal sets, guard and the
  other policy thresholds must be fitted on other data (or fixed in
  advance). Only ``commit_p`` is chosen on the calibration items.
- **Marginal guarantee.** CRC bounds the expected rate over random
  calibration sets and new items. One session can be above alpha. LTT
  bounds the rate with probability 1 - delta over calibration sets.
- **Single attempt.** The loss counts the first decision on an item.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Literal, Sequence

import numpy as np

Method = Literal["crc", "ltt"]
PValue = Literal["auto", "hb", "binomial"]

#: Default LTT grid: commit_p from 1.0 down to 0.0 in steps of 0.01.
DEFAULT_LTT_GRID: tuple[float, ...] = tuple(round(1.0 - 0.01 * k, 2) for k in range(101))


@dataclass(frozen=True)
class RiskControlResult:
    """The selected COMMIT threshold and its calibration statistics.

    COMMIT iff score >= ``threshold``. ``threshold = inf`` means never commit.
    """

    threshold: float
    feasible: bool
    method: str
    alpha: float
    delta: float | None
    n: int
    #: Empirical (monotonised) risk at ``threshold`` on the calibration items.
    empirical_risk: float
    #: CRC: (n R_hat + B) / (n + 1). LTT: the p-value at ``threshold`` (nan if none).
    bound: float
    #: Share of calibration items that commit at ``threshold``.
    commit_rate: float


def _as_arrays(scores, commit_losses, fallback_losses):
    s = np.asarray(scores, dtype=np.float64)
    c = np.asarray(commit_losses, dtype=np.float64)
    f = np.zeros_like(c) if fallback_losses is None else np.asarray(fallback_losses, dtype=np.float64)
    if not (s.shape == c.shape == f.shape) or s.ndim != 1:
        raise ValueError("scores, commit_losses and fallback_losses must be 1-D and of equal length")
    if np.isnan(s).any():
        raise ValueError("scores must not be nan (use -inf for 'never commit')")
    if ((c < 0) | (c > 1) | (f < 0) | (f > 1)).any():
        raise ValueError("losses must be in [0, 1]")
    return s, np.maximum(c, f), f


def empirical_risk(scores, commit_losses, threshold: float, fallback_losses=None) -> float:
    """Return the mean monotonised loss at ``threshold`` (see the module docstring)."""
    s, c, f = _as_arrays(scores, commit_losses, fallback_losses)
    if s.size == 0:
        return math.nan
    return float(np.mean(np.where(s >= threshold, c, f)))


def _risk_curve(s: np.ndarray, c: np.ndarray, f: np.ndarray, lams: np.ndarray) -> np.ndarray:
    """R_hat(lambda) for each lambda (vectorised with a sort)."""
    order = np.argsort(-s, kind="stable")
    s_sorted = s[order]
    gain = (c - f)[order]  # extra loss when the item commits (>= 0)
    cum = np.concatenate([[0.0], np.cumsum(gain)])
    # Number of items with s >= lam.
    k = np.searchsorted(-s_sorted, -lams, side="right")
    return (f.sum() + cum[k]) / s.size


def crc_threshold(
    scores: Sequence[float],
    commit_losses: Sequence[float],
    alpha: float = 0.05,
    fallback_losses: Sequence[float] | None = None,
    B: float = 1.0,
) -> RiskControlResult:
    """Conformal risk control for the COMMIT threshold (module docstring)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    s, c, f = _as_arrays(scores, commit_losses, fallback_losses)
    n = s.size
    if n == 0:
        return RiskControlResult(math.inf, False, "crc", alpha, None, 0, math.nan, math.nan, 0.0)
    fin = np.unique(s[np.isfinite(s)])
    lams = np.concatenate([fin, [math.inf]])
    risk = _risk_curve(s, c, f, lams)
    bound = (n * risk + B) / (n + 1)
    ok = bound <= alpha + 1e-12
    # risk is non-increasing in lambda: the feasible set is an upper interval.
    if not ok[-1]:
        return RiskControlResult(math.inf, False, "crc", alpha, None, n, float(risk[-1]), float(bound[-1]), 0.0)
    j = int(np.argmax(ok))  # first feasible (smallest lambda)
    lam = float(lams[j])
    return RiskControlResult(lam, True, "crc", alpha, None, n, float(risk[j]), float(bound[j]),
                             float(np.mean(s >= lam)))


# --- LTT p-values --------------------------------------------------------


def _log_binom_cdf(k: int, n: int, p: float) -> float:
    """log P(Bin(n, p) <= k), stable in log space."""
    if k < 0:
        return -math.inf
    if k >= n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return -math.inf
    i = np.arange(k + 1, dtype=np.float64)
    lg = np.array([math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1) for x in i])
    terms = lg + i * math.log(p) + (n - i) * math.log1p(-p)
    m = terms.max()
    return float(m + math.log(np.exp(terms - m).sum()))


def binomial_pvalue(risk_hat: float, n: int, alpha: float) -> float:
    """Exact p-value of H0: R > alpha for 0/1 losses: P(Bin(n, alpha) <= n R_hat)."""
    k = int(math.floor(n * risk_hat + 1e-9))
    return float(math.exp(_log_binom_cdf(k, n, alpha)))


def hoeffding_bentkus_pvalue(risk_hat: float, n: int, alpha: float) -> float:
    """Hoeffding-Bentkus p-value of H0: R > alpha for losses in [0, 1] (LTT Prop. 3)."""
    if n <= 0:
        return 1.0
    a = min(risk_hat, alpha)

    def h1(x: float, y: float) -> float:
        t1 = 0.0 if x <= 0 else x * math.log(x / y)
        t2 = 0.0 if x >= 1 else (1 - x) * math.log((1 - x) / (1 - y))
        return t1 + t2

    p_h = math.exp(-n * h1(a, alpha))
    k = int(math.ceil(n * risk_hat - 1e-9))
    p_b = math.e * math.exp(_log_binom_cdf(k, n, alpha))
    return float(min(1.0, p_h, p_b))


def ltt_threshold(
    scores: Sequence[float],
    commit_losses: Sequence[float],
    alpha: float = 0.05,
    delta: float = 0.1,
    fallback_losses: Sequence[float] | None = None,
    grid: Sequence[float] | None = None,
    pvalue: PValue = "auto",
) -> RiskControlResult:
    """Learn then Test (fixed-sequence) for the COMMIT threshold.

    ``grid`` must be fixed before the data is seen (default
    :data:`DEFAULT_LTT_GRID`). It is tested from its largest value down.
    ``pvalue="auto"`` uses the exact binomial p-value if all losses are 0
    or 1, else Hoeffding-Bentkus.
    """
    if not 0.0 < alpha < 1.0 or not 0.0 < delta < 1.0:
        raise ValueError("alpha and delta must be in (0, 1)")
    s, c, f = _as_arrays(scores, commit_losses, fallback_losses)
    n = s.size
    lams = np.array(sorted(DEFAULT_LTT_GRID if grid is None else grid, reverse=True), dtype=np.float64)
    if n == 0 or lams.size == 0:
        return RiskControlResult(math.inf, False, "ltt", alpha, delta, n, math.nan, math.nan, 0.0)
    binary = bool(np.all((c == 0) | (c == 1)) and np.all((f == 0) | (f == 1)))
    kind = ("binomial" if binary else "hb") if pvalue == "auto" else pvalue
    if kind == "binomial" and not binary:
        raise ValueError("binomial p-values need 0/1 losses")
    pv = binomial_pvalue if kind == "binomial" else hoeffding_bentkus_pvalue
    risk = _risk_curve(s, c, f, lams)
    best = None
    for lam, r in zip(lams, risk):
        p = pv(float(r), n, alpha)
        if p > delta:
            break
        best = (float(lam), float(r), p)
    if best is None:
        r_inf = float(np.mean(f))
        return RiskControlResult(math.inf, False, f"ltt-{kind}", alpha, delta, n, r_inf, math.nan, 0.0)
    lam, r, p = best
    return RiskControlResult(lam, True, f"ltt-{kind}", alpha, delta, n, r, p, float(np.mean(s >= lam)))


# --- policy integration ---------------------------------------------------


def commit_calibration_data(
    policy: Any, inputs: Sequence[Any], truths: Sequence[str], final_attempt: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (scores, commit_losses, fallback_losses) for a policy.

    ``policy`` is a :class:`fidetype.trust.policy.DecisionPolicy`;
    ``inputs`` are its :class:`~fidetype.trust.policy.PolicyInputs` (one
    per calibration item, first attempt) and ``truths`` the true texts.

    - score: ``p_top1`` if the policy commits with ``commit_p = -inf``
      (all other rules unchanged), else -inf.
    - commit loss: 1 if the top-1 text != truth.
    - fallback loss: the decision with ``commit_p = +inf``. 1 if it is
      OFFER_WORDS and the top-1 text != truth (an upper bound: OFFER_WORDS
      is a wrong commit only if an unhighlighted word is wrong), else 0.
    """
    from fidetype.trust.policy import Action, DecisionPolicy

    lo = DecisionPolicy(replace(policy.config, commit_p=-math.inf), use_guard=policy.use_guard)
    hi = DecisionPolicy(replace(policy.config, commit_p=math.inf), use_guard=policy.use_guard)
    s, c, f = [], [], []
    for x, t in zip(inputs, truths):
        wrong = float(not x.texts or x.texts[0] != t)
        d = lo.decide(x, final_attempt=final_attempt)
        s.append(float(x.p_top1) if d.action == Action.COMMIT else -math.inf)
        c.append(wrong)
        d2 = hi.decide(x, final_attempt=final_attempt)
        f.append(wrong if d2.action == Action.OFFER_WORDS else 0.0)
    return np.array(s), np.array(c), np.array(f)


@dataclass
class CommitRiskControl:
    """Select ``commit_p`` of a policy with CRC or LTT.

    Example (per-user, per-session calibration)::

        rc = CommitRiskControl(alpha=0.05, method="crc")
        rc.fit_policy(policy, calib_inputs, calib_truths)
        policy = rc.apply(policy)            # commit_p = lambda_hat
        policy = rc.apply(policy, "max")     # keep a stricter tuned commit_p

    The calibration items must be exchangeable with the items the policy
    will see (see the module docstring), and must not have been used to
    fit the other parts of the trust core.
    """

    alpha: float = 0.05
    method: Method = "crc"
    delta: float = 0.1
    grid: Sequence[float] | None = None
    pvalue: PValue = "auto"
    result: RiskControlResult | None = None

    def fit(self, scores, commit_losses, fallback_losses=None) -> "CommitRiskControl":
        if self.method == "crc":
            self.result = crc_threshold(scores, commit_losses, self.alpha, fallback_losses)
        elif self.method == "ltt":
            self.result = ltt_threshold(scores, commit_losses, self.alpha, self.delta, fallback_losses,
                                        self.grid, self.pvalue)
        else:
            raise ValueError(f"unknown method {self.method!r}")
        return self

    def fit_policy(self, policy: Any, inputs: Sequence[Any], truths: Sequence[str]) -> "CommitRiskControl":
        return self.fit(*commit_calibration_data(policy, inputs, truths))

    @property
    def threshold(self) -> float:
        if self.result is None:
            raise RuntimeError("call fit() first")
        return self.result.threshold

    def apply(self, policy: Any, combine: Literal["replace", "max"] = "replace") -> Any:
        """Return a new DecisionPolicy with the calibrated ``commit_p``.

        ``combine="max"`` keeps the policy's own commit_p if it is
        stricter (the guarantee still holds; see the module docstring).
        """
        from fidetype.trust.policy import DecisionPolicy

        lam = self.threshold
        cp = max(lam, policy.config.commit_p) if combine == "max" else lam
        return DecisionPolicy(replace(policy.config, commit_p=cp), use_guard=policy.use_guard)
