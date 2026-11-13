"""Trust core module h: per-session (per-day) risk control of the COMMIT threshold.

:mod:`fidetype.trust.risk_control` bounds the wrong-commit rate of the
*calibration distribution*. When the calibration items mix many sessions
(days), that is the risk of the mixture, not of each session. Paper 1
found one B2T '25 day (day 34, published gate) at about 2 alpha under the
pooled LTT max rule. A user meets one session at a time. This module
gives four per-session remedies. All are our own implementation.

Notation: item i has a commit score ``s_i``, a commit loss ``c_i`` and a
fallback loss ``f_i`` (see :mod:`fidetype.trust.risk_control`). The loss
at threshold lambda is ``L_i(lambda) = max(c_i, f_i)`` if ``s_i >= lambda``,
else ``f_i``. alpha = target wrong-commit rate, delta = LTT error level.

Methods and guarantees
----------------------
1. :func:`mondrian_ltt` -- group-conditional (Mondrian) LTT. LTT on the
   calibration items of each group (session) alone. Guarantee per group
   ``g`` with ``n_g >= n_min``: ``P(R_g(lambda_g) <= alpha) >= 1 - delta``
   (items of the group exchangeable). A group with fewer items gets a
   fallback: ``"never"`` (offer-only; trivially safe), ``"global"`` (the
   pooled threshold; **no per-group guarantee**) or ``"mixture"`` (pooled
   LTT at level ``alpha * pi_g``; valid per group only if ``pi_g`` is the
   group's true share of the mixture, because
   ``R_g <= R_mix / pi_g``).

   Sample-size floor. With 0/1 losses and the exact binomial p-value,
   LTT can reject ``R > alpha`` only if ``(1 - alpha) ** n <= delta``, so
   ``n >= ceil(log(delta) / log(1 - alpha))`` (:func:`min_ltt_items`; 45
   for alpha = 0.05, delta = 0.1). No per-session LTT exists below it.

2. :func:`block_ltt` -- session-start calibration block. The first ``k``
   items of a session have known truth (a copy-typing block, or an
   offer-only warm-up whose OFFER picks reveal the truth). LTT on the
   block, combined with a base (global) threshold by max: it can only get
   stricter. Guarantee: ``P(R_session(lambda) <= alpha) >= 1 - delta`` for
   the rest of the session, if the rest is exchangeable with the block.
   It needs ``k >= min_ltt_items``; below that it never commits.

   :func:`block_test` is the weak form for small ``k``: an exact test of
   ``H0: R_session(lambda) <= alpha`` on the block. A rejection is an
   alarm (switch the session to offer-only). Guarantee: **false alarms
   only** (``P(alarm | good session) <= gamma``). No risk guarantee.

3. :class:`SessionRiskMonitor` -- online, anytime-valid alarm. An
   e-process for ``H0: E[L_t | past] <= alpha`` for every t (so it also
   allows drift that stays below alpha)::

       K_t = mean_j prod_{i <= t} (1 + b_j (L_i - alpha)),   0 <= b_j <= 1 / alpha

   Each product is a non-negative supermartingale under H0, so the mean
   is too. By Ville's inequality ``P(sup_t K_t >= 1 / gamma) <= gamma``.
   The alarm (``K_t >= 1 / gamma``) switches the session to offer-only.
   Guarantee: **false alarm <= gamma per session**, at any stopping time,
   with no model of the drift. No bound on the risk before the alarm.
   The bets ``b_j`` are Kelly bets for fixed alternatives
   ``rho_j > alpha`` (``b = (rho - alpha) / (alpha (1 - alpha))``), capped
   at ``max_bet_fraction / alpha``. It needs only the realised loss
   (commit feedback: the user corrects a wrong commit).

4. :func:`eb_session_threshold` -- hierarchical (empirical-Bayes)
   shrinkage. At each grid lambda, a beta prior for the session risk is
   fitted on the risks of reference sessions (method of moments); the
   session's block updates it; the threshold is the smallest
   lambda >= base with posterior ``P(R > alpha) <= delta``. It borrows
   strength across days and works with a small block (even k = 0).
   Guarantee: **none** (a Bayesian heuristic; the prior is estimated).

Assumptions
-----------
- Losses in [0, 1]. Exact binomial p-values need 0/1 losses; otherwise
  Hoeffding(-Bentkus) p-values are used.
- "Session" = a run of items that the method treats as exchangeable (or,
  for the monitor, with conditional risk <= alpha under H0).
- Silent errors (wrong commits the user never corrects) are invisible to
  the monitor; it then sees a lower loss than the true one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from fidetype.trust.risk_control import (
    DEFAULT_LTT_GRID,
    _as_arrays,
    _log_binom_cdf,
    _risk_curve,
    ltt_threshold,
)

Fallback = Literal["never", "global", "mixture"]

#: Default alternatives of :class:`SessionRiskMonitor` (true session risks it bets on).
DEFAULT_ALTERNATIVES: tuple[float, ...] = (0.075, 0.10, 0.15, 0.20, 0.30)


def min_ltt_items(alpha: float = 0.05, delta: float = 0.1) -> int:
    """Smallest n for which an exact binomial LTT can certify ``R <= alpha`` (0 errors in n)."""
    if not 0.0 < alpha < 1.0 or not 0.0 < delta < 1.0:
        raise ValueError("alpha and delta must be in (0, 1)")
    n = math.ceil(math.log(delta) / math.log1p(-alpha))
    # Guard against float rounding at the boundary.
    while n > 1 and (1.0 - alpha) ** (n - 1) <= delta:
        n -= 1
    while (1.0 - alpha) ** n > delta:
        n += 1
    return int(n)


def binomial_upper_pvalue(k: int, n: int, alpha: float) -> float:
    """Exact p-value of ``H0: R <= alpha`` for k errors in n 0/1 items: ``P(Bin(n, alpha) >= k)``."""
    if n <= 0 or k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return float(max(0.0, -math.expm1(_log_binom_cdf(k - 1, n, alpha))))


# ---------------------------------------------------------------------------
# 1. Mondrian (group-conditional) LTT
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupThreshold:
    """Threshold of one group (session). COMMIT iff score >= threshold."""

    threshold: float
    #: "group" (own LTT), "group-infeasible" (own LTT rejected nothing),
    #: "fallback-never", "fallback-global", "fallback-mixture".
    source: str
    n: int
    #: True if the threshold carries a per-group finite-sample guarantee.
    per_group_guarantee: bool


def mondrian_ltt(
    scores: Sequence[float],
    commit_losses: Sequence[float],
    groups: Sequence[Any],
    alpha: float = 0.05,
    delta: float = 0.1,
    fallback_losses: Sequence[float] | None = None,
    base_threshold: float | None = None,
    fallback: Fallback = "never",
    n_min: int | None = None,
    grid: Sequence[float] | None = None,
) -> dict[Any, GroupThreshold]:
    """Group-conditional LTT (module docstring, method 1).

    ``base_threshold`` (for example the plug-in commit_p, or the pooled
    LTT max threshold) is combined by max with every group threshold. The
    pooled threshold for ``fallback="global"`` is LTT on all items (max
    with ``base_threshold``).
    """
    s, c, f = _as_arrays(scores, commit_losses, fallback_losses)
    g = np.asarray(list(groups), dtype=object)
    if g.shape != s.shape:
        raise ValueError("groups must have one label per item")
    if fallback not in ("never", "global", "mixture"):
        raise ValueError(f"unknown fallback {fallback!r}")
    nmin = min_ltt_items(alpha, delta) if n_min is None else int(n_min)
    base = -math.inf if base_threshold is None else float(base_threshold)
    pooled = None
    if fallback == "global":
        pooled = max(base, ltt_threshold(s, c, alpha, delta, f, grid).threshold)
    out: dict[Any, GroupThreshold] = {}
    labels = list(dict.fromkeys(g.tolist()))
    for lab in labels:
        idx = np.where(g == lab)[0]
        n = int(idx.size)
        if n >= nmin:
            r = ltt_threshold(s[idx], c[idx], alpha, delta, f[idx], grid)
            out[lab] = GroupThreshold(max(base, r.threshold), "group" if r.feasible else "group-infeasible", n, True)
        elif fallback == "never":
            out[lab] = GroupThreshold(math.inf, "fallback-never", n, True)
        elif fallback == "global":
            out[lab] = GroupThreshold(float(pooled), "fallback-global", n, False)
        else:
            pi = n / s.size
            r = ltt_threshold(s, c, alpha * pi, delta, f, grid)
            out[lab] = GroupThreshold(max(base, r.threshold), "fallback-mixture", n, False)
    return out


# ---------------------------------------------------------------------------
# 2. Session-start calibration block
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionThreshold:
    """Threshold for the rest of a session. COMMIT iff score >= threshold."""

    threshold: float
    method: str
    n_block: int
    #: The block's own threshold (LTT or EB) before the max with the base threshold.
    block_threshold: float
    base_threshold: float
    guarantee: str


def block_ltt(
    block_scores: Sequence[float],
    block_commit_losses: Sequence[float],
    base_threshold: float | None = None,
    alpha: float = 0.05,
    delta: float = 0.1,
    block_fallback_losses: Sequence[float] | None = None,
    grid: Sequence[float] | None = None,
) -> SessionThreshold:
    """LTT on a session-start block, combined with ``base_threshold`` by max (method 2)."""
    s, c, f = _as_arrays(block_scores, block_commit_losses, block_fallback_losses)
    base = -math.inf if base_threshold is None else float(base_threshold)
    r = ltt_threshold(s, c, alpha, delta, f, grid) if s.size else None
    lam_b = math.inf if r is None else r.threshold
    return SessionThreshold(max(base, lam_b), "block-ltt", int(s.size), lam_b, base,
                            "per-session LTT: P(R_session <= alpha) >= 1 - delta (exchangeable within the session)")


@dataclass(frozen=True)
class BlockTest:
    """Exact test of ``H0: R_session(threshold) <= alpha`` on a block."""

    p_value: float
    reject: bool
    risk_hat: float
    n: int
    gamma: float


def block_test(
    block_scores: Sequence[float],
    block_commit_losses: Sequence[float],
    threshold: float,
    alpha: float = 0.05,
    gamma: float = 0.1,
    block_fallback_losses: Sequence[float] | None = None,
) -> BlockTest:
    """Test whether a session is worse than alpha at ``threshold`` (method 2, weak form).

    0/1 losses: exact binomial ``P(Bin(n, alpha) >= k)``. Other losses in
    [0, 1]: Hoeffding ``exp(-2 n (R_hat - alpha)^2)`` for ``R_hat > alpha``.
    """
    if not 0.0 < gamma < 1.0:
        raise ValueError("gamma must be in (0, 1)")
    s, c, f = _as_arrays(block_scores, block_commit_losses, block_fallback_losses)
    n = int(s.size)
    if n == 0:
        return BlockTest(1.0, False, math.nan, 0, gamma)
    loss = np.where(s >= threshold, c, f)
    r = float(loss.mean())
    if np.all((loss == 0) | (loss == 1)):
        p = binomial_upper_pvalue(int(round(loss.sum())), n, alpha)
    else:
        p = 1.0 if r <= alpha else float(math.exp(-2.0 * n * (r - alpha) ** 2))
    return BlockTest(p, bool(p <= gamma), r, n, gamma)


# ---------------------------------------------------------------------------
# 3. Online anytime-valid monitor
# ---------------------------------------------------------------------------


@dataclass
class SessionRiskMonitor:
    """Anytime-valid alarm for one session (module docstring, method 3).

    Use::

        mon = SessionRiskMonitor(alpha=0.05, gamma=0.1)
        for item in session:              # before the alarm, commit at the session threshold
            ...
            if mon.update(realised_loss): # True once K_t >= 1 / gamma
                ...                       # switch the session to offer-only

    ``update`` after the alarm is allowed and changes nothing (the alarm
    is absorbing).
    """

    alpha: float = 0.05
    gamma: float = 0.1
    alternatives: Sequence[float] = DEFAULT_ALTERNATIVES
    #: Cap of each bet as a share of 1 / alpha (keeps a factor >= 1 - fraction for a zero loss).
    max_bet_fraction: float = 0.5
    #: Unknown truth of a commit: "skip" (no update) or "pessimistic" (loss 1).
    missing: Literal["skip", "pessimistic"] = "skip"

    # --- state ---
    n: int = 0
    n_missing: int = 0
    sum_loss: float = 0.0
    alarm_at: int | None = None
    log_wealth: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0 or not 0.0 < self.gamma < 1.0:
            raise ValueError("alpha and gamma must be in (0, 1)")
        if not 0.0 < self.max_bet_fraction < 1.0:
            raise ValueError("max_bet_fraction must be in (0, 1)")
        alts = [float(a) for a in self.alternatives]
        if not alts or any(not self.alpha < a < 1.0 for a in alts):
            raise ValueError("alternatives must be in (alpha, 1)")
        if self.missing not in ("skip", "pessimistic"):
            raise ValueError(f"unknown missing {self.missing!r}")
        self.alternatives = tuple(alts)
        if not self.log_wealth:
            self.log_wealth = [0.0] * len(alts)

    @property
    def bets(self) -> tuple[float, ...]:
        cap = self.max_bet_fraction / self.alpha
        return tuple(min(cap, (a - self.alpha) / (self.alpha * (1.0 - self.alpha))) for a in self.alternatives)

    @property
    def e_value(self) -> float:
        lw = np.asarray(self.log_wealth)
        m = float(lw.max())
        return float(math.exp(m) * np.mean(np.exp(lw - m)))

    @property
    def alarmed(self) -> bool:
        return self.alarm_at is not None

    def update(self, loss: float | None) -> bool:
        """Add one realised loss (None: unknown truth). Return the alarm state."""
        if self.alarmed:
            return True
        if loss is None:
            self.n_missing += 1
            if self.missing == "skip":
                return False
            loss = 1.0
        x = float(loss)
        if not 0.0 <= x <= 1.0:
            raise ValueError("loss must be in [0, 1]")
        self.n += 1
        self.sum_loss += x
        self.log_wealth = [lw + math.log1p(b * (x - self.alpha)) for lw, b in zip(self.log_wealth, self.bets)]
        if self.e_value >= 1.0 / self.gamma:
            self.alarm_at = self.n
        return self.alarmed

    def reset(self) -> None:
        self.n = self.n_missing = 0
        self.sum_loss = 0.0
        self.alarm_at = None
        self.log_wealth = [0.0] * len(self.alternatives)

    def state(self) -> dict[str, Any]:
        return {"n": self.n, "n_missing": self.n_missing, "mean_loss": (self.sum_loss / self.n) if self.n else None,
                "e_value": self.e_value, "alarm": self.alarmed, "alarm_at": self.alarm_at,
                "alpha": self.alpha, "gamma": self.gamma}


def first_alarm(losses: Sequence[float], alpha: float = 0.05, gamma: float = 0.1,
                alternatives: Sequence[float] = DEFAULT_ALTERNATIVES, max_bet_fraction: float = 0.5) -> int | None:
    """1-based index of the first alarm of :class:`SessionRiskMonitor` on ``losses`` (None: no alarm)."""
    mon = SessionRiskMonitor(alpha, gamma, alternatives, max_bet_fraction)
    for x in losses:
        if mon.update(float(x)):
            return mon.alarm_at
    return None


# ---------------------------------------------------------------------------
# 4. Empirical-Bayes shrinkage (no finite-sample guarantee)
# ---------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta function (modified Lentz)."""
    tiny, eps = 1e-300, 3e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 10001):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta ``I_x(a, b)`` = P(Beta(a, b) <= x) (numpy-free of scipy)."""
    if a <= 0 or b <= 0:
        raise ValueError("a and b must be > 0")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return float(math.exp(lbt) * _betacf(a, b, x) / a)
    return float(1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b)


def fit_beta_prior(counts: Sequence[tuple[float, int]], kappa_min: float = 2.0, kappa_max: float = 100.0,
                   mean_floor: float = 1e-3) -> tuple[float, float]:
    """Method-of-moments beta prior from per-group (errors, n). Returns (a, b).

    Mean m = sum x / sum n. Between-group variance tau^2 = weighted variance
    of the group rates minus the mean binomial variance. Concentration
    kappa = m (1 - m) / tau^2 - 1, clipped to [kappa_min, kappa_max].
    """
    cs = [(float(x), int(n)) for x, n in counts if int(n) > 0]
    if not cs:
        raise ValueError("need at least one group with n > 0")
    x = np.array([v[0] for v in cs])
    n = np.array([v[1] for v in cs], dtype=np.float64)
    m = float(np.clip(x.sum() / n.sum(), mean_floor, 1.0 - mean_floor))
    if len(cs) < 2:
        kappa = kappa_max
    else:
        r = x / n
        w = n / n.sum()
        var_w = float(np.sum(w * (r - np.sum(w * r)) ** 2))
        tau2 = var_w - m * (1.0 - m) * float(np.mean(1.0 / n))
        kappa = kappa_max if tau2 <= 0 else m * (1.0 - m) / tau2 - 1.0
    kappa = float(np.clip(kappa, kappa_min, kappa_max))
    return m * kappa, (1.0 - m) * kappa


def eb_session_threshold(
    block_scores: Sequence[float],
    block_commit_losses: Sequence[float],
    reference: Sequence[tuple[Sequence[float], Sequence[float], Sequence[float] | None]] | None = None,
    base_threshold: float | None = None,
    alpha: float = 0.05,
    delta: float = 0.1,
    block_fallback_losses: Sequence[float] | None = None,
    grid: Sequence[float] | None = None,
    prior: Mapping[float, tuple[float, float]] | tuple[float, float] | None = None,
    kappa_min: float = 2.0,
    kappa_max: float = 100.0,
) -> SessionThreshold:
    """Empirical-Bayes session threshold (module docstring, method 4). **No finite-sample guarantee.**

    ``reference``: (scores, commit_losses, fallback_losses) of other
    sessions; the prior at each lambda is fitted on their losses at lambda.
    Or give ``prior``: one (a, b) for all lambdas, or a map lambda -> (a, b).
    The block may be empty (k = 0: prior only).
    """
    if (reference is None) == (prior is None):
        raise ValueError("give exactly one of reference and prior")
    s, c, f = _as_arrays(block_scores, block_commit_losses, block_fallback_losses)
    lams = np.array(sorted(DEFAULT_LTT_GRID if grid is None else grid), dtype=np.float64)
    base = -math.inf if base_threshold is None else float(base_threshold)
    k_blk = _risk_curve(s, c, f, lams) * s.size if s.size else np.zeros_like(lams)
    refs = []
    if reference is not None:
        for rs, rc, rf in reference:
            a_s, a_c, a_f = _as_arrays(rs, rc, rf)
            if a_s.size:
                refs.append((a_s.size, _risk_curve(a_s, a_c, a_f, lams) * a_s.size))
        if not refs:
            raise ValueError("reference sessions are empty")
    lam_b = math.inf
    for j, lam in enumerate(lams):
        if lam < base:
            continue
        if reference is not None:
            a, b = fit_beta_prior([(r[1][j], r[0]) for r in refs], kappa_min, kappa_max)
        elif isinstance(prior, Mapping):
            a, b = prior[float(lam)]
        else:
            a, b = prior  # type: ignore[misc]
        x = float(k_blk[j])
        p_bad = 1.0 - beta_cdf(alpha, a + x, b + s.size - x)
        if p_bad <= delta:
            lam_b = float(lam)
            break
    return SessionThreshold(max(base, lam_b), "eb-shrinkage", int(s.size), lam_b, base,
                            "none (empirical-Bayes heuristic; no finite-sample guarantee)")
