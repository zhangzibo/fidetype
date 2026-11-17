"""Exact binomial tools without scipy: the binomial CDF and the Clopper-Pearson interval.

Moved here from :mod:`fidetype.demo.live.tracks` (P14-06, commit 9617a57) so that the trust core
(:mod:`fidetype.trust.precision_bound`, P5-02) can use the same helper. ``tracks`` re-exports the names.
The interval is found by bisection on the binomial CDF (log-space sum). It matches scipy's beta
quantiles to 4 decimals on the checked cases.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import math
from typing import Callable

__all__ = ["binom_cdf", "clopper_pearson", "cp_upper"]


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p) (log-space sum; no scipy needed)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
             for i in range(0, k + 1)]
    m = max(terms)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in terms))


def _bisect(f: Callable[[float], float], target: float, increasing: bool) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if (f(mid) < target) == increasing:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, level: float = 0.95, ndigits: int | None = 4) -> list[float | None]:
    """Exact (Clopper-Pearson) two-sided interval for k successes in n trials, by bisection on the binomial CDF.

    ``ndigits``: round the ends (default 4, as before); None keeps full precision.
    """
    if n == 0:
        return [None, None]
    a = (1.0 - level) / 2
    # lower: P(X >= k | p) = a  <=>  1 - cdf(k-1) = a (increasing in p)
    lo = 0.0 if k == 0 else _bisect(lambda p: 1.0 - binom_cdf(k - 1, n, p), a, increasing=True)
    # upper: P(X <= k | p) = a (decreasing in p)
    hi = 1.0 if k == n else _bisect(lambda p: binom_cdf(k, n, p), a, increasing=False)
    if ndigits is None:
        return [lo, hi]
    return [round(lo, ndigits), round(hi, ndigits)]


def cp_upper(k: int, n: int, delta: float) -> float:
    """One-sided Clopper-Pearson upper bound at confidence ``1 - delta`` (1.0 for n = 0; not rounded).

    It is the upper end of the two-sided interval at level ``1 - 2 delta``.
    """
    if n == 0:
        return 1.0
    return float(clopper_pearson(k, n, level=1.0 - 2.0 * delta, ndigits=None)[1])
