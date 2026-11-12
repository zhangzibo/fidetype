"""Trust core module g: online re-calibration of the COMMIT threshold.

:mod:`fidetype.trust.risk_control` (M2-13) fixes ``commit_p`` once, on a
calibration set. Its guarantee needs exchangeable data. Under drift inside
a session it can fail: on Brain-to-Text '25 (calibrate on the earlier half
of each day, test on the later half) CRC gave wrong-commit 0.0625 for
alpha = 0.05. This module re-calibrates the threshold *during* the session
from the user's feedback.

Feedback model (read this first)
--------------------------------
Item t has a commit score ``s_t`` (calibrated ``p_top1`` if the other
policy rules allow COMMIT, else -inf; see
:func:`fidetype.trust.risk_control.commit_calibration_data`). The policy
commits iff ``s_t >= lambda_t``. The loss of item t is::

    L_t = c_t  if it commits   (c_t = 1 if the top-1 text is wrong)
          f_t  otherwise       (0 for OFFER / ASK / ABSTAIN; it can be 1
                                for OFFER_WORDS)

What the system can observe, and when:

==================  ==========================================  ===========================
action              what the user does                          what the system learns
==================  ==========================================  ===========================
COMMIT, right       nothing (keeps the text)                    c_t = 0, *if* "no correction
                                                                within the timeout" means right
COMMIT, wrong       deletes or corrects the text                c_t = 1, after a delay (the
                                                                user must notice the error)
OFFER               picks a candidate, or retypes               the final text = the truth, so
                                                                c_t (top-1 right?) is known; L_t = 0
ASK                 repeats the attempt                         nothing new about this attempt
ABSTAIN / gives up  nothing                                     truth unknown; L_t = f_t = 0
==================  ==========================================  ===========================

So two feedback levels exist:

- **Realised loss** ("commit feedback"). ``L_t`` is known for every item:
  the system knows ``f_t`` itself, and the user's correction gives
  ``c_t`` for a commit. This is all that :class:`method="aci"` needs.
- **Full feedback.** ``c_t`` is also known for items that did *not*
  commit, because the user's final text (OFFER pick, retyped text) is the
  truth. The window methods need this: they re-fit CRC on past
  ``(s_i, c_i)`` pairs. Items whose truth stays unknown (ABSTAIN, given
  up) are left out of the window. That is a selection bias; the "aci"
  bound does not depend on it.

Feedback can come late (delay ``d``) and in any order: :meth:`decide`
returns a :class:`Ticket`, :meth:`observe` takes it back later. A missed
wrong commit that the user never corrects (a *silent error*) looks like a
right commit. No method can see it. The guarantees below are about the
losses the system observes; silent errors are measured separately.

Methods and guarantees
----------------------
``method="window"`` -- sliding-window / weighted CRC. At each step, CRC
on the last ``window`` items with known truth (and / or weights
``decay ** age``), plus the offline calibration items as the oldest part
of the history::

    lambda_t = min { lam : (sum_i w_i L_i(lam) + w_test B) / (sum_i w_i + w_test) <= alpha }

Guarantee: **approximate only.** For fixed weights, non-exchangeable
conformal risk control (Farinhas et al., ICLR 2024, arXiv:2310.01262;
after Barber et al. 2023, arXiv:2202.13415) gives::

    E[ L_test ] <= alpha + B * sum_i w~_i * d_TV(Z, Z^(i)),  w~_i = w_i / (w_test + sum_j w_j)

The extra term is small only if the recent items (high weight) are close
in distribution to the next one. Under exchangeability the bound is
alpha. With weights, it needs ``sum_i w_i >= B / alpha - w_test`` (19
for alpha = 0.05) to commit at all. Needs **full feedback**.

``method="aci"`` -- online risk control in threshold space (the
"quantile tracking" / P-control update of Gibbs & Candes 2021,
arXiv:2106.00170, and Angelopoulos, Candes & Tibshirani 2023,
arXiv:2307.16895; "rolling risk control" of Feldman et al. 2023,
arXiv:2205.09095)::

    lambda_{t+1} = max( lam_min, lambda_t + eta * (L_t - alpha) )

A loss above alpha makes the gate stricter; a loss below makes it looser.
Guarantee: **for any sequence** (no exchangeability, no model of the
drift), after T observed losses::

    (1/T) sum_t L_t  <=  alpha + (lambda_{T+1} - lambda_1) / (eta * T)

This is an identity plus the lower clip (the clip only raises lambda).
:meth:`report` returns the right-hand side as ``certificate``. It is
also bounded in advance: if all scores are <= ``score_max`` and the
non-commit loss is 0, lambda cannot pass ``score_max + eta (B - alpha)
(1 + d)`` (above ``score_max`` nothing commits, so only the <= d pending
losses can still raise it). So::

    (1/T) sum_t L_t  <=  alpha + (score_max - lambda_1 + eta B (1 + d)) / (eta T)

It is a **long-run average** bound: it says nothing about one short
window, and the slack is O(1 / (eta T)). It needs only the **realised
loss**. With OFFER_WORDS (``f_t`` can be 1) the identity still holds, but
lambda is bounded only if the mean fallback loss stays below alpha.

``method="aci_window"`` -- adaptive conformal inference on the level
(Gibbs & Candes 2021): the window CRC is run at level ``alpha_t`` and::

    alpha_{t+1} = min( alpha_max, alpha_t + gamma * (alpha - L_t) )

Guarantee: **for any sequence**::

    (1/T) sum_t L_t  <=  alpha + (alpha_1 - alpha_{T+1}) / (gamma * T)

(``certificate`` in :meth:`report`). alpha_t is bounded below: when it
is below the CRC feasibility level, CRC never commits, the loss is 0 and
alpha_t rises again. It combines the window's data use with the
long-run guarantee. Needs **full feedback** for the window part; the
alpha_t update needs only the realised loss.

Clipping. ``lam_min`` (default 0) is a safe floor: the gate never commits
below it, and the bound above still holds. An upper clip ``lam_max``
would break the "aci" identity when it binds; it is off by default and
:meth:`report` flags any binding (certificate = nan). ``alpha_max``
(default 2 alpha) is safe for "aci_window".

Missing feedback. A commit whose loss never arrives (``observe(ticket,
None)``): ``missing="skip"`` drops it (the bound then covers only the
observed items); ``missing="pessimistic"`` counts it as a wrong commit
(loss B). Use "pessimistic" with a timeout when a missing correction is
not a reliable "right" signal.

All three are our own implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Sequence

import numpy as np

from fidetype.trust.risk_control import RiskControlResult, _as_arrays, crc_threshold

OnlineMethod = Literal["window", "aci", "aci_window"]
Missing = Literal["skip", "pessimistic"]


def weighted_crc_threshold(
    scores: Sequence[float],
    commit_losses: Sequence[float],
    alpha: float = 0.05,
    fallback_losses: Sequence[float] | None = None,
    weights: Sequence[float] | None = None,
    w_test: float = 1.0,
    B: float = 1.0,
) -> RiskControlResult:
    """Weighted (non-exchangeable) conformal risk control.

    ``lambda_hat = min { lam : (sum_i w_i L_i(lam) + w_test B) / (sum_i w_i + w_test) <= alpha }``
    over the unique scores and +inf. With all weights 1 and ``w_test = 1``
    this is :func:`~fidetype.trust.risk_control.crc_threshold`. ``alpha``
    may be <= 0 (then: never commit, ``feasible=False``).
    """
    s, c, f = _as_arrays(scores, commit_losses, fallback_losses)
    w = np.ones_like(s) if weights is None else np.asarray(weights, dtype=np.float64)
    if w.shape != s.shape or (w < 0).any():
        raise ValueError("weights must be >= 0 and match the scores")
    keep = w > 0
    s, c, f, w = s[keep], c[keep], f[keep], w[keep]
    n = int(s.size)
    W = float(w.sum())
    if n == 0 or alpha <= 0:
        r = float(np.sum(w * f) / W) if W > 0 else math.nan
        return RiskControlResult(math.inf, False, "wcrc", alpha, None, n, r, math.nan, 0.0)
    lams = np.concatenate([np.unique(s[np.isfinite(s)]), [math.inf]])
    order = np.argsort(-s, kind="stable")
    s_sorted = s[order]
    cum = np.concatenate([[0.0], np.cumsum((w * (c - f))[order])])
    k = np.searchsorted(-s_sorted, -lams, side="right")
    risk = (float(np.sum(w * f)) + cum[k]) / W  # weighted empirical risk
    bound = (W * risk + w_test * B) / (W + w_test)
    ok = bound <= alpha + 1e-12
    if not ok[-1]:
        return RiskControlResult(math.inf, False, "wcrc", alpha, None, n, float(risk[-1]), float(bound[-1]), 0.0)
    j = int(np.argmax(ok))
    lam = float(lams[j])
    cr = float(np.sum(w * (s >= lam)) / W)
    return RiskControlResult(lam, True, "wcrc", alpha, None, n, float(risk[j]), float(bound[j]), cr)


@dataclass(frozen=True)
class Ticket:
    """One commit decision, waiting for its feedback."""

    id: int
    score: float
    threshold: float
    commit: bool
    #: Policy wrapper only: the top-1 text and whether the non-commit action is OFFER_WORDS.
    top1: str | None = None
    fallback_offer_words: bool = False


@dataclass
class OnlineCommitRiskControl:
    """Online re-calibration of ``commit_p`` (module docstring).

    Same use as :class:`~fidetype.trust.risk_control.CommitRiskControl`
    (``fit`` / ``fit_policy`` / ``threshold`` / ``apply``), plus the online
    loop::

        rc = OnlineCommitRiskControl(alpha=0.05, method="aci")
        rc.fit(cal_scores, cal_commit_losses)    # warm start (optional)
        for item in session:
            tk = rc.decide(score(item))           # commit iff tk.commit
            ...                                   # later, maybe out of order:
            rc.observe(tk, commit_loss)           # None if the truth stays unknown
        rc.report()                               # realised rate + certificate
    """

    alpha: float = 0.05
    method: OnlineMethod = "aci"
    #: window methods: keep the last ``window`` items with known truth (None: all).
    window: int | None = 200
    #: window methods: weight ``decay ** age`` (age 0 = newest). None: no decay.
    decay: float | None = None
    #: "aci": step size on the threshold.
    eta: float = 0.05
    #: "aci_window": step size on the level.
    gamma: float = 0.005
    #: Start threshold ("aci") if :meth:`fit` is not called; None: never commit at the start.
    lam_init: float | None = None
    #: Safe floor of the threshold (never commit below it).
    lam_min: float = 0.0
    #: Optional upper clip (breaks the "aci" certificate if it binds).
    lam_max: float = math.inf
    #: Upper clip of alpha_t ("aci_window"); None: 2 alpha.
    alpha_max: float | None = None
    #: Largest possible score (calibrated probabilities: 1.0).
    score_max: float = 1.0
    missing: Missing = "skip"
    B: float = 1.0

    # --- state (not constructor arguments in normal use) ---
    hist_s: list[float] = field(default_factory=list)
    hist_c: list[float] = field(default_factory=list)
    hist_f: list[float] = field(default_factory=list)
    lam_t: float = math.nan
    lam_1: float = math.nan
    alpha_t: float = math.nan
    alpha_1: float = math.nan
    n_obs: int = 0
    n_missing: int = 0
    sum_loss: float = 0.0
    lam_max_seen: float = -math.inf
    upper_clip_hits: int = 0
    result: RiskControlResult | None = None
    _next_id: int = 0
    _pending: dict[int, Ticket] = field(default_factory=dict)
    _cache: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        if self.method not in ("window", "aci", "aci_window"):
            raise ValueError(f"unknown method {self.method!r}")
        if self.eta <= 0 or self.gamma <= 0:
            raise ValueError("eta and gamma must be > 0")
        if self.decay is not None and not 0.0 < self.decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")
        if self.alpha_max is None:
            self.alpha_max = min(2.0 * self.alpha, 0.999)
        if math.isnan(self.alpha_t):
            self.alpha_t = self.alpha
        if math.isnan(self.alpha_1):
            self.alpha_1 = self.alpha_t
        if math.isnan(self.lam_t):
            self._set_lam_start(self.lam_init)

    # --- helpers -----------------------------------------------------------

    @property
    def _never(self) -> float:
        """Smallest threshold above every possible score (never commit)."""
        return math.nextafter(self.score_max, math.inf)

    def _set_lam_start(self, lam: float | None) -> None:
        lam = self._never if lam is None or not math.isfinite(lam) else float(lam)
        lam = max(self.lam_min, lam)
        self.lam_t = self.lam_1 = lam
        self.lam_max_seen = lam

    def _weights(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        s, c, f = np.array(self.hist_s), np.array(self.hist_c), np.array(self.hist_f)
        if self.window is not None:
            s, c, f = s[-self.window :], c[-self.window :], f[-self.window :]
        age = np.arange(s.size - 1, -1, -1, dtype=np.float64)
        w = np.ones_like(s) if self.decay is None else self.decay**age
        return s, c, f, w

    def window_result(self, level: float | None = None) -> RiskControlResult:
        """Weighted CRC on the current history at ``level`` (default alpha)."""
        s, c, f, w = self._weights()
        return weighted_crc_threshold(s, c, self.alpha if level is None else level, f, w, 1.0, self.B)

    # --- offline warm start (same API as CommitRiskControl) ----------------

    def fit(self, scores, commit_losses, fallback_losses=None) -> "OnlineCommitRiskControl":
        """Warm start on calibration items (oldest first). Resets the online state.

        "aci": lambda_1 = the offline CRC threshold (never commit if CRC is
        infeasible). Window methods: the items fill the history.
        """
        s, c, f = _as_arrays(scores, commit_losses, fallback_losses)
        self.hist_s, self.hist_c, self.hist_f = s.tolist(), c.tolist(), f.tolist()
        self.result = crc_threshold(s, c, self.alpha, f, self.B)
        self._set_lam_start(self.result.threshold)
        self.alpha_t = self.alpha_1 = self.alpha
        self.n_obs, self.n_missing, self.sum_loss, self.upper_clip_hits = 0, 0, 0.0, 0
        self._pending.clear()
        self._cache = None
        return self

    def fit_policy(self, policy: Any, inputs: Sequence[Any], truths: Sequence[str]) -> "OnlineCommitRiskControl":
        from fidetype.trust.risk_control import commit_calibration_data

        return self.fit(*commit_calibration_data(policy, inputs, truths))

    @property
    def threshold(self) -> float:
        """The current COMMIT threshold (commit iff score >= threshold)."""
        if self.method == "aci":
            return self.lam_t
        if self._cache is None:
            level = self.alpha if self.method == "window" else self.alpha_t
            lam = self.window_result(level).threshold
            self._cache = max(self.lam_min, min(lam, self.lam_max)) if math.isfinite(lam) else math.inf
        return self._cache

    def apply(self, policy: Any, combine: Literal["replace", "max"] = "replace") -> Any:
        """A new DecisionPolicy with the *current* threshold (as CommitRiskControl.apply)."""
        from fidetype.trust.policy import DecisionPolicy

        lam = self.threshold
        cp = max(lam, policy.config.commit_p) if combine == "max" else lam
        return DecisionPolicy(replace(policy.config, commit_p=cp), use_guard=policy.use_guard)

    # --- online loop ---------------------------------------------------------

    def decide(self, score: float, top1: str | None = None, fallback_offer_words: bool = False) -> Ticket:
        """Decide COMMIT for one item; keep a ticket for its feedback."""
        if math.isnan(score):
            raise ValueError("score must not be nan (use -inf for 'never commit')")
        lam = self.threshold
        tk = Ticket(self._next_id, float(score), lam, bool(score >= lam), top1, fallback_offer_words)
        self._next_id += 1
        self._pending[tk.id] = tk
        return tk

    @property
    def pending(self) -> int:
        return len(self._pending)

    def observe(self, ticket: Ticket, commit_loss: float | None, fallback_loss: float = 0.0) -> float | None:
        """Feed back one item. Return the realised loss used (None if skipped).

        ``commit_loss`` = c (1 if the top-1 text is wrong, else 0), or None
        if the truth stays unknown. ``fallback_loss`` = f (known to the system).
        """
        if self._pending.pop(ticket.id, None) is None:
            raise KeyError(f"ticket {ticket.id} is not pending (observed twice?)")
        for v in (commit_loss, fallback_loss):
            if v is not None and not 0.0 <= v <= self.B:
                raise ValueError("losses must be in [0, B]")
        if ticket.commit:
            if commit_loss is None:
                self.n_missing += 1
                if self.missing == "skip":
                    return None
                loss = self.B
            else:
                loss = max(float(commit_loss), float(fallback_loss))  # monotone loss, as in M2-13
        else:
            loss = float(fallback_loss)
        self.n_obs += 1
        self.sum_loss += loss
        if commit_loss is not None and self.method != "aci":
            self.hist_s.append(ticket.score)
            self.hist_c.append(max(float(commit_loss), float(fallback_loss)))
            self.hist_f.append(float(fallback_loss))
        if self.method == "aci":
            lam = max(self.lam_min, self.lam_t + self.eta * (loss - self.alpha))
            if lam > self.lam_max:
                lam = self.lam_max
                self.upper_clip_hits += 1
            self.lam_t = lam
            self.lam_max_seen = max(self.lam_max_seen, lam)
        elif self.method == "aci_window":
            self.alpha_t = min(self.alpha_max, self.alpha_t + self.gamma * (self.alpha - loss))
        self._cache = None
        return loss

    def step(self, score: float, commit_loss: float | None, fallback_loss: float = 0.0) -> Ticket:
        """decide() then observe() at once (no feedback delay)."""
        tk = self.decide(score)
        self.observe(tk, commit_loss, fallback_loss)
        return tk

    def report(self) -> dict[str, Any]:
        """Realised mean loss over the observed items and the guarantee certificate.

        ``certificate`` is a deterministic upper bound of ``mean_loss`` that
        holds for any sequence ("aci", "aci_window"; nan for "window", which
        has no such bound, and for "aci" if the upper clip ever bound).
        """
        T = self.n_obs
        mean = self.sum_loss / T if T else math.nan
        cert = math.nan
        if T and self.method == "aci" and self.upper_clip_hits == 0:
            cert = self.alpha + (self.lam_t - self.lam_1) / (self.eta * T)
        elif T and self.method == "aci_window":
            cert = self.alpha + (self.alpha_1 - self.alpha_t) / (self.gamma * T)
        return {
            "method": self.method,
            "alpha": self.alpha,
            "n_observed": T,
            "n_missing": self.n_missing,
            "pending": self.pending,
            "mean_loss": mean,
            "certificate": cert,
            "threshold": self.threshold,
            "lam_1": self.lam_1,
            "alpha_t": self.alpha_t,
            "upper_clip_hits": self.upper_clip_hits,
            "guarantee": {
                "window": "approximate (weighted CRC; exact only under exchangeability)",
                "aci": "long-run average, any sequence (realised-loss feedback)",
                "aci_window": "long-run average, any sequence (window needs full feedback)",
            }[self.method],
        }

    def prior_bound(self, T: int, delay: int = 0) -> float:
        """"aci" only: the bound fixed in advance (module docstring), for T observed items."""
        if self.method != "aci":
            raise ValueError("prior_bound is defined for method='aci'")
        return self.alpha + (self.score_max - self.lam_1 + self.eta * self.B * (1 + delay)) / (self.eta * T)


class OnlineTrustPolicy:
    """A :class:`~fidetype.trust.policy.DecisionPolicy` whose ``commit_p``
    follows an :class:`OnlineCommitRiskControl`.

    Works with any NeuralTextStream decoder: it reads only
    :class:`~fidetype.trust.policy.PolicyInputs`::

        op = OnlineTrustPolicy(policy, OnlineCommitRiskControl(method="aci"))
        decision, tk = op.decide(x)
        ...
        op.feedback(tk, final_text)   # the user's final text, or None if unknown
    """

    def __init__(self, policy: Any, controller: OnlineCommitRiskControl) -> None:
        from fidetype.trust.policy import DecisionPolicy

        self.policy = policy
        self.controller = controller
        self._lo = DecisionPolicy(replace(policy.config, commit_p=-math.inf), use_guard=policy.use_guard)
        self._hi = DecisionPolicy(replace(policy.config, commit_p=math.inf), use_guard=policy.use_guard)

    def decide(self, x: Any, final_attempt: bool = False) -> tuple[Any, Ticket]:
        from fidetype.trust.policy import Action

        d_lo = self._lo.decide(x, final_attempt=final_attempt)
        score = float(x.p_top1) if d_lo.action == Action.COMMIT else -math.inf
        d_hi = self._hi.decide(x, final_attempt=final_attempt)
        top1 = x.texts[0] if x.texts else None
        tk = self.controller.decide(score, top1, d_hi.action == Action.OFFER_WORDS)
        return (d_lo if tk.commit else d_hi), tk

    def feedback(self, ticket: Ticket, truth: str | None) -> float | None:
        """Feed back the true text (None: unknown). Return the realised loss used."""
        if truth is None:
            f = self.controller.B if (ticket.fallback_offer_words and self.controller.missing == "pessimistic") else 0.0
            return self.controller.observe(ticket, None, f)
        c = float(ticket.top1 is None or ticket.top1 != truth)
        f = c if ticket.fallback_offer_words else 0.0
        return self.controller.observe(ticket, c, f)
