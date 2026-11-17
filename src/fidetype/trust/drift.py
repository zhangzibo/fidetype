"""Anytime-valid drift tests for the inputs of the trust layer (P5-01).

A calibrated guard holds its bound only while the live data look like the
calibration data. Neural signals drift from day to day, so the guard must
see when they stop doing so. This module gives two sequential tests. Both
are **anytime valid**: you may look at them after every item and stop at
any time. Under the null hypothesis, the probability of a false alarm
over the whole (infinite) stream is at most ``level`` (Ville's inequality).
Both are our own implementation of published methods.

1. :class:`ConformalDriftTest` -- drift of a score distribution (for
   example ``p_top1``, the calibrated top-1 confidence). Null hypothesis:
   the reference scores and the live scores are exchangeable (same
   distribution, no order effect). Each live score gets a smoothed
   conformal p-value: its rank in the bag of all scores so far (reference
   plus live). Under the null these p-values are independent and uniform
   on [0, 1] (Vovk, Nouretdinov, Gammerman 2003, "Testing exchangeability
   on-line", ICML). A conformal test martingale bets on them. We use the
   "Simple Jumper" betting martingale of Vovk (2021, "Testing randomness
   online", Statistical Science 36(4)), with betting functions
   ``1 + eps * (p - 1/2)``, ``eps`` in {-1, 0, 1}, and a jump rate ``J``.
   The jump lets the test react to a change late in the stream: no
   component loses all its capital (the change-point use of Vovk et al.
   2021, "Retrain or not retrain: conformal test martingales for
   change-point detection", COPA, PMLR 152).

   **Spread bets (P5-09, opt-in ``spread=True``).** The bets above react
   only to the mean of the p-values. A change of spread at the same
   centre (for example sd 1 -> 2) gives p-values near 0 *and* near 1, so
   their mean stays near 1/2 and the test does not alarm. With
   ``spread=True`` the mixture also holds the betting functions
   ``1 + eps * (|2p - 1| - 1/2)``, ``eps`` in {-1, 1}. Under the null,
   ``|2p - 1|`` is uniform on [0, 1], so each factor has mean 1 and lies
   in [1/2, 3/2]. The mixture stays a non-negative martingale and the
   anytime false-alarm bound does not change. ``eps = 1`` wins on a
   wider spread, ``eps = -1`` on a narrower one. Cost: more components
   share the capital, so a pure mean shift is detected a little later
   (``experiments/2026-11-16-p5-09-drift-spread/results.md``).

2. :class:`RiskDriftTest` -- drift of the observed wrong-commit loss.
   Null hypothesis: ``E[L_t | past] <= alpha`` at every step, where
   ``L_t`` in [0, 1] is the per-item loss (1 = a wrong commit the user saw,
   0 otherwise; an OFFER or a withhold has loss 0). The test is a betting
   e-process (Waudby-Smith and Ramdas 2024, "Estimating means of bounded
   random variables by betting", JRSSB 86(1)): wealth
   ``prod (1 + lam (L_t - alpha))`` with ``0 <= lam < 1 / alpha``, mixed
   over a grid of bets with the same jump rule. Under the null each
   component is a non-negative supermartingale, so the mixture is one.

:class:`DriftMonitor` runs both tests with a split level (default: half of
the total level each, Bonferroni), so that
``P(any false alarm) <= level_scores + level_risk``.

What the tests do not cover:

- An alarm says "the data changed" or "the observed loss rate is above
  alpha". It does not say why. The caller decides what to do
  (:mod:`fidetype.trust.personal` tightens the guard or proposes a gated
  re-calibration).
- The risk test sees only the losses the user reports. **Silent errors**
  (a wrong commit that the user does not notice) have loss 0 and are not
  covered.
- The score test needs exchangeable reference scores (from one
  calibration of one decoder version). After a decoder change or an
  accepted re-calibration, start a new test with new reference scores.
- After an alarm, a test stays alarmed. Start a new one (:meth:`reset`).
  Each new test has its own false-alarm level.
- Ville's inequality bounds the false-alarm probability; it does not
  bound the detection delay. The delay depends on the size of the change
  (see ``experiments/2026-11-16-p5-01-personal/results.md``).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

__all__ = [
    "ConformalDriftTest",
    "DriftMonitor",
    "DriftStatus",
    "RiskDriftTest",
]

#: Default bet sizes of :class:`RiskDriftTest`, as fractions ``c = lam * alpha`` of the largest allowed bet.
DEFAULT_RISK_BETS: tuple[float, ...] = (0.025, 0.05, 0.1, 0.2, 0.4)


class _Jumper:
    """Mixture of betting components with the Simple Jumper rule, kept in the log domain.

    ``w``: the share of the capital in each component (sums to 1); ``log_capital``: log of the total.
    Each step: move a share ``jump`` of the total capital evenly to all components, then multiply each
    component by its betting factor. If every factor has conditional mean <= 1 under the null, the total is
    a non-negative supermartingale with start 1.
    """

    def __init__(self, k: int, jump: float) -> None:
        if not 0.0 <= jump <= 1.0:
            raise ValueError("jump must be in [0, 1]")
        self.k = int(k)
        self.jump = float(jump)
        self.w = np.full(self.k, 1.0 / self.k)
        self.log_capital = 0.0
        self.max_log_capital = 0.0

    def step(self, factors: np.ndarray) -> float:
        w = (1.0 - self.jump) * self.w + self.jump / self.k
        g = float(np.dot(w, factors))
        if g <= 0.0:  # cannot happen with valid factors (> 0); keep the state finite
            raise ValueError("betting factors must be positive")
        self.w = w * factors / g
        self.log_capital += math.log(g)
        self.max_log_capital = max(self.max_log_capital, self.log_capital)
        return self.log_capital


@dataclass(frozen=True)
class DriftStatus:
    """The state of one test after an update."""

    name: str
    n: int
    #: Current e-value (test capital). Under the null, ``P(sup e >= 1/level) <= level``.
    e_value: float
    #: Largest e-value so far.
    e_max: float
    level: float
    alarmed: bool
    #: Item index (1-based, in this test) of the first alarm, or None.
    alarm_at: int | None

    def to_dict(self) -> dict[str, Any]:
        def f(x: float) -> Any:
            return x if math.isfinite(x) else str(x)

        return {"name": self.name, "n": self.n, "e_value": f(self.e_value), "e_max": f(self.e_max),
                "level": self.level, "alarmed": self.alarmed, "alarm_at": self.alarm_at}


def _check_level(level: float) -> float:
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0, 1)")
    return float(level)


class ConformalDriftTest:
    """Conformal test martingale on a score stream against reference scores (module docstring, test 1).

    ``reference``: scores from the calibration data (at least 1; -inf is allowed, for "no text").
    ``level``: false-alarm probability over the whole stream. ``jump``: Simple Jumper rate (Vovk 2021 uses
    0.01). ``side``: ``"both"`` (default), ``"down"`` (bet only on live scores lower than the reference) or
    ``"up"`` (only higher). ``seed``: random tie-breaking of the smoothed p-values. ``spread``: also bet on
    ``|2p - 1|`` (a change of spread at the same centre; module docstring). Default False: the P5-01 bets.

    ``update(score)`` adds one live score and returns a :class:`DriftStatus`.
    """

    name = "scores"

    def __init__(self, reference: Iterable[float], *, level: float = 0.01, jump: float = 0.01,
                 side: str = "both", seed: int = 0, spread: bool = False) -> None:
        ref = [float(x) for x in reference]
        if not ref:
            raise ValueError("reference needs at least one score")
        if any(math.isnan(x) for x in ref):
            raise ValueError("reference scores must not be nan (use -inf)")
        self.level = _check_level(level)
        eps = {"both": (-1.0, 0.0, 1.0), "down": (0.0, 1.0), "up": (-1.0, 0.0)}.get(side)
        if eps is None:
            raise ValueError("side must be 'both', 'down' or 'up'")
        self.side = side
        self._eps = np.asarray(eps)
        self.spread = bool(spread)
        #: Spread bets ``1 + eps * (|2p - 1| - 1/2)`` (P5-09); empty without ``spread``.
        self._eps_spread = np.asarray((-1.0, 1.0) if self.spread else (), dtype=float)
        self._jump = float(jump)
        self._seed = int(seed)
        self._ref = sorted(ref)
        self.reset()

    @property
    def n_reference(self) -> int:
        return len(self._ref)

    def reset(self, reference: Iterable[float] | None = None) -> None:
        """Start a new test (new false-alarm budget). ``reference``: new reference scores (None: keep)."""
        if reference is not None:
            ref = sorted(float(x) for x in reference)
            if not ref:
                raise ValueError("reference needs at least one score")
            self._ref = ref
        self._bag = list(self._ref)
        self._rng = np.random.default_rng(self._seed)
        self._mart = _Jumper(len(self._eps) + len(self._eps_spread), self._jump)
        self.n = 0
        self.alarm_at: int | None = None
        self.p_values: list[float] = []

    def p_value(self, score: float) -> float:
        """Add ``score`` to the bag and return its smoothed conformal p-value (large score -> small p)."""
        x = float(score)
        if math.isnan(x):
            raise ValueError("score must not be nan (use -inf)")
        bisect.insort(self._bag, x)
        lo, hi = bisect.bisect_left(self._bag, x), bisect.bisect_right(self._bag, x)
        n = len(self._bag)
        greater, equal = n - hi, hi - lo
        return (greater + float(self._rng.random()) * equal) / n

    def update(self, score: float) -> DriftStatus:
        p = self.p_value(score)
        self.p_values.append(p)
        self.n += 1
        f = 1.0 + self._eps * (p - 0.5)
        if self.spread:
            f = np.concatenate((f, 1.0 + self._eps_spread * (abs(2.0 * p - 1.0) - 0.5)))
        self._mart.step(f)
        if self.alarm_at is None and self._mart.log_capital >= math.log(1.0 / self.level):
            self.alarm_at = self.n
        return self.status()

    def update_many(self, scores: Iterable[float]) -> DriftStatus:
        st = self.status()
        for s in scores:
            st = self.update(s)
        return st

    @property
    def alarmed(self) -> bool:
        return self.alarm_at is not None

    @property
    def e_value(self) -> float:
        return math.exp(min(self._mart.log_capital, 700.0))

    def status(self) -> DriftStatus:
        return DriftStatus(self.name, self.n, self.e_value, math.exp(min(self._mart.max_log_capital, 700.0)),
                           self.level, self.alarmed, self.alarm_at)

    def state_summary(self) -> dict[str, Any]:
        """JSON summary (no scores): for the user profile."""
        d = self.status().to_dict()
        d.update({"test": "conformal-simple-jumper", "jump": self._jump, "side": self.side,
                  "n_reference": self.n_reference})
        if self.spread:
            d["spread"] = True
        return d


class RiskDriftTest:
    """Betting e-process for ``H0: E[L_t | past] <= alpha`` on losses in [0, 1] (module docstring, test 2).

    ``alpha``: the risk limit of the guard. ``level``: false-alarm probability over the whole stream.
    ``bets``: bet sizes as fractions ``c`` in (0, 1) of the largest bet ``1 / alpha`` (``lam = c / alpha``).
    A zero bet is always added. ``jump``: Simple Jumper rate across the bets.
    """

    name = "risk"

    def __init__(self, alpha: float, *, level: float = 0.01, bets: Sequence[float] = DEFAULT_RISK_BETS,
                 jump: float = 0.01) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = float(alpha)
        self.level = _check_level(level)
        cs = [float(c) for c in bets]
        if not cs or any(not 0.0 < c < 1.0 for c in cs):
            raise ValueError("bets must be fractions in (0, 1)")
        self._lam = np.asarray([0.0] + [c / self.alpha for c in cs])
        self._bets = tuple(cs)
        self._jump = float(jump)
        self.reset()

    def reset(self) -> None:
        """Start a new test (new false-alarm budget)."""
        self._mart = _Jumper(len(self._lam), self._jump)
        self.n = 0
        self.loss_sum = 0.0
        self.alarm_at: int | None = None

    def update(self, loss: float) -> DriftStatus:
        x = float(loss)
        if not 0.0 <= x <= 1.0:
            raise ValueError("loss must be in [0, 1]")
        self.n += 1
        self.loss_sum += x
        self._mart.step(1.0 + self._lam * (x - self.alpha))
        if self.alarm_at is None and self._mart.log_capital >= math.log(1.0 / self.level):
            self.alarm_at = self.n
        return self.status()

    def update_many(self, losses: Iterable[float]) -> DriftStatus:
        st = self.status()
        for x in losses:
            st = self.update(x)
        return st

    @property
    def alarmed(self) -> bool:
        return self.alarm_at is not None

    @property
    def e_value(self) -> float:
        return math.exp(min(self._mart.log_capital, 700.0))

    def status(self) -> DriftStatus:
        return DriftStatus(self.name, self.n, self.e_value, math.exp(min(self._mart.max_log_capital, 700.0)),
                           self.level, self.alarmed, self.alarm_at)

    def state_summary(self) -> dict[str, Any]:
        d = self.status().to_dict()
        d.update({"test": "betting-e-process", "alpha": self.alpha, "bets": list(self._bets), "jump": self._jump,
                  "observed_mean_loss": (self.loss_sum / self.n) if self.n else None})
        return d


@dataclass
class DriftMonitor:
    """Both tests together, with a split false-alarm level.

    ``reference_scores``: the score reference of :class:`ConformalDriftTest` (None: no score test).
    ``alpha``: the guard's risk limit (None: no risk test). ``level_scores`` / ``level_risk``: the levels of
    the two tests; ``P(any false alarm) <= level_scores + level_risk``. ``spread``: the score test also bets
    on a change of spread (P5-09; default False).
    """

    reference_scores: Sequence[float] | None = None
    alpha: float | None = None
    level_scores: float = 0.005
    level_risk: float = 0.005
    jump: float = 0.01
    side: str = "both"
    seed: int = 0
    spread: bool = False
    scores: ConformalDriftTest | None = field(init=False, default=None)
    risk: RiskDriftTest | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.reference_scores is not None:
            self.scores = ConformalDriftTest(self.reference_scores, level=self.level_scores, jump=self.jump,
                                             side=self.side, seed=self.seed, spread=self.spread)
        if self.alpha is not None:
            self.risk = RiskDriftTest(self.alpha, level=self.level_risk, jump=self.jump)

    @property
    def level(self) -> float:
        return (self.level_scores if self.scores else 0.0) + (self.level_risk if self.risk else 0.0)

    def update_score(self, score: float) -> DriftStatus | None:
        return None if self.scores is None else self.scores.update(score)

    def update_loss(self, loss: float) -> DriftStatus | None:
        return None if self.risk is None else self.risk.update(loss)

    @property
    def score_alarm(self) -> bool:
        return bool(self.scores is not None and self.scores.alarmed)

    @property
    def risk_alarm(self) -> bool:
        return bool(self.risk is not None and self.risk.alarmed)

    def reset(self, reference_scores: Sequence[float] | None = None) -> None:
        """Start both tests again (after an accepted re-calibration). New reference scores if given."""
        if reference_scores is not None:
            self.reference_scores = list(reference_scores)
            if self.scores is None:
                self.scores = ConformalDriftTest(self.reference_scores, level=self.level_scores, jump=self.jump,
                                                 side=self.side, seed=self.seed, spread=self.spread)
            else:
                self.scores.reset(self.reference_scores)
        elif self.scores is not None:
            self.scores.reset()
        if self.risk is not None:
            self.risk.reset()

    def summary(self) -> dict[str, Any]:
        return {"level_total": self.level,
                "scores": None if self.scores is None else self.scores.state_summary(),
                "risk": None if self.risk is None else self.risk.state_summary()}
