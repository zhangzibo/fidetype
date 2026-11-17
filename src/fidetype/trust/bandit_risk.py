"""Trust core module (P15-04): online risk control with shown-only (bandit) feedback.

The problem
-----------
In real use the user gives feedback only on text that the system SHOWED:
a COMMIT (the user corrects a wrong one) or an OFFER (the user picks a
candidate or retypes). For a withheld item (ASK / ABSTAIN) the truth stays
unknown. This is *semi-bandit* feedback: the label of item t is seen only
if the item was shown (Ge, Bastani & Bastani 2024, arXiv:2405.13268; Yang,
Kim & Park 2026, arXiv:2604.17984: "the label is revealed only when it is
inside the prediction set").

Two kinds of statement need different data:

1. **The realised policy.** "Of the items that the system decided, at most
   a fraction alpha were wrong commits" (marginal), or "of the commits, at
   most a fraction alpha_p were wrong" (precision). The loss of a decision
   is known exactly from shown-only feedback: a commit is shown, so its
   label arrives; a non-commit has wrong-commit loss 0. So an ACI-type
   controller (Gibbs & Candes 2021, arXiv:2106.00170; Angelopoulos, Candes
   & Tibshirani 2023, arXiv:2307.16895) is valid under bandit feedback with
   no change: its certificate is an identity on the realised losses.
2. **A counterfactual threshold** (or a new decoder). "If we had used
   threshold lam, how many wrong commits would we have made?" This needs
   labels of items that the current policy withheld. A complete-case
   ("naive") estimate from the shown items only is biased: the shown items
   are the high-score ones. This module removes the bias with forced
   exploration at a known rate and inverse-propensity weighting (Horvitz &
   Thompson 1952), and it gives an anytime-valid upper bound
   (Freedman / Bennett supermartingale + Ville's inequality; the same tools
   as the off-policy confidence sequences of Karampatziakis, Mineiro &
   Ramdas 2021, arXiv:2102.09540, and Waudby-Smith et al. 2022,
   arXiv:2210.10768).

Exploration never commits. An explored item is SHOWN AS AN OFFER (the
user must confirm it), so exploration costs user effort, not wrong commits.

Notation
--------
Item t has commit score ``s_t`` (``-inf``: the policy rules forbid COMMIT)
and top-1 error ``c_t`` in {0, 1} (or [0, 1]). At threshold lam the
counterfactual wrong-commit loss is ``Y_t(lam) = c_t 1[s_t >= lam]``.
The system commits iff ``s_t >= lam_t``. Otherwise the item is shown
anyway if the policy OFFERs it (``offered=True``), else it is explored
(shown as an offer) with probability ``explore``. So the probability that
item t is shown is::

    pi_t = 1          if s_t >= lam_t or offered
           0          if s_t = -inf (the policy forbids COMMIT: never explored)
           explore    otherwise

``pi_t`` depends only on the past and on ``s_t``. The coin is drawn after
``s_t`` and ``c_t`` are fixed. The IPW term ``X_t(lam) = O_t c^_t 1[s_t >= lam] / pi_t``
(``O_t`` = shown; ``c^_t`` = the label, or 1 if a shown item gets no
label: pessimistic) has ``E[X_t | past, s_t, c_t] >= Y_t(lam)``.

An item with ``s_t = -inf`` adds 0 to every ``Y``, ``X`` and ``V`` (no grid
threshold commits it), so exploring it costs user effort and gives the audit
no information. It is never shown for exploration (``pi_t = 0``). A coin is
still drawn for every withheld item, so the coin stream does not depend on
the scores.

Audit accounting (decision order). The audit adds item t at ``decide`` time,
before its label can arrive: ``N``, ``V`` and, for a shown item, ``X`` with a
provisional ``c^_t = 1``. When the label arrives, ``observe`` lowers ``X`` to
the true ``c^_t``. So at every moment the audit sum contains EVERY decided
item, in decision order, and each term is ``>=`` the term of the proof.
Late, out-of-order or never-returned feedback can only make the bound larger.
(Before this fix the sums were updated in ``observe``: explored offers that
waited for a label were missing, the set in the sum depended on the coins,
and with never-returned feedback the bound failed with probability 1; see
``wiki/questions/g3-audit-review.md``, finding H1.)

Coins (seed). The probability in (G3) is over the exploration coins. The
coins must be unpredictable to whatever produces the data (the user, the
decoder, the integration). The default ``seed=None`` takes fresh OS entropy.
A fixed seed gives a fixed, public coin stream (the repo is public): use it
only for replays and tests.

Guarantees (what this module claims; the full scope is in the wiki page
``wiki/questions/f1-guarantee-scope.md``)
---------------------------------------------------------------------------
(G1) ``rule="aci"``, ``target="marginal"`` (default). Update after each
decided item: ``lam_{t+1} = max(lam_min, lam_t + eta (L_t - alpha))`` with
``L_t = c_t 1[commit_t]``. For ANY sequence (adversarial, adaptive)::

    (1/T) sum_t L_t <= alpha + (lam_{T+1} - lam_1) / (eta T)

(deterministic; ``certificate`` in :meth:`report`). Needs only the labels
of commits, which shown-only feedback gives.

(G2) ``rule="aci"``, ``target="precision"``. Update only at commits:
``lam_{t+1} = max(lam_min, lam_t + eta (c_t - alpha))``. For ANY sequence,
with N_c commits::

    (wrong commits) / N_c <= alpha + (lam_{T+1} - lam_1) / (eta N_c)

(deterministic). Same proof: sum the updates. ``alpha`` here is the
allowed error rate among commits (``1 - target precision``).

(G3) Audit (needs ``explore > 0``). For every threshold lam_k of a fixed
grid (K points) and every time t at once, with probability >= 1 - delta
over the exploration coins only (``s_t`` and ``c_t`` may be ANY adaptive
sequence that does not see the coin of item t, and the coins are
unpredictable to the data source: ``seed=None`` in live use)::

    sum_{i<=t} Y_i(lam_k) <= sum_{i<=t} X_i(lam_k)
                             + min_b [ psi(b) V_t(lam_k) + log(K J / delta) ] / b

with ``psi(b) = e^b - 1 - b``, ``V_t(lam) = sum_{i<=t, pi_i<1} 1[s_i >= lam] / pi_i``
(known: the scores are always seen) and b over a fixed grid of J bets.
Proof sketch: ``D_i = Y_i - X_i <= 1`` has conditional mean <= 0 and
``E[D_i^2 | .] <= 1[s_i >= lam] / pi_i`` (0 if pi_i = 1, because then
D_i <= 0); Bennett's lemma ``E e^{b D} <= exp(psi(b) E D^2)`` makes
``exp(b sum D - psi(b) V)`` a non-negative supermartingale; Ville's
inequality and a union bound over (lam_k, b) finish it.

Why late labels are safe. The label of a shown item arrives AFTER its coin,
and whether (and when) it arrives may depend on the coin. So the ``c^_t``
that the code uses is not fixed at step t. The supermartingale is therefore
built on ``D'_t = Y_t - X'_t`` with ``X'_t = O_t c_t 1[s_t >= lam] / pi_t``
(the TRUE ``c_t``, fixed before the coin: the steps above hold for ``D'_t``).
The code holds ``X_t`` with ``c^_t`` in {provisional 1, label 1 if missing,
true ``c_t``}, so ``X_t >= X'_t`` for every item at every moment, and the
bound on ``sum Y`` with ``X'`` implies the bound with ``X``.

This is a design-based statement: it bounds the wrong commits that threshold
lam_k WOULD HAVE MADE on the items DECIDED so far (all of them, whether their
feedback arrived or not). Divided by the known count
``N_t(lam_k) = sum 1[s_i >= lam_k]`` it bounds the counterfactual precision
error. It does not say anything about future items unless they are like
the past (exchangeable / stationary).

``rule="cs"`` uses (G3) to pick the threshold: the smallest grid lam whose
audit bound is <= alpha (marginal: per item seen; precision: per commit at
lam). Forward validity needs stationarity. ``rule="max"`` applies
``max(lam_aci, lam_cs)``: it keeps (G1) / (G2) (the ACI identity holds for
any decisions, and lam_aci > score_max still means no commit) and adds the
audit condition.

What is NOT covered (also in the wiki page): silent errors (a wrong commit
that the user never corrects looks like a right one: every statement above
is about OBSERVED labels); one short window or one session (the bounds are
long-run, slack O(1 / (eta T))); items whose score was never computed; a
user whose intended text changes because of what was shown.

All of this is our own implementation; no code was copied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Sequence

import numpy as np

BanditTarget = Literal["marginal", "precision"]
BanditRule = Literal["aci", "cs", "max"]

#: Default threshold grid for the audit and for ``rule="cs"``: 0.00, 0.01, ..., 1.00.
DEFAULT_GRID: tuple[float, ...] = tuple(round(0.01 * k, 2) for k in range(101))
#: Default bets b (geometric, 1 down to 2^-11).
DEFAULT_BETS: tuple[float, ...] = tuple(2.0 ** (-j) for j in range(12))


def bennett_psi(b: float | np.ndarray) -> float | np.ndarray:
    """``psi(b) = e^b - 1 - b`` (Bennett)."""
    return np.expm1(b) - b


def ipw_slack(var_proxy: np.ndarray | float, n_tests: int, delta: float,
              bets: Sequence[float] = DEFAULT_BETS) -> np.ndarray:
    """Slack of (G3): ``min_b [psi(b) V + log(n_tests J / delta)] / b`` (vectorised over V)."""
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0, 1)")
    b = np.asarray(bets, dtype=np.float64)
    if b.size == 0 or (b <= 0).any():
        raise ValueError("bets must be > 0")
    V = np.atleast_1d(np.asarray(var_proxy, dtype=np.float64))
    log_term = math.log(n_tests * b.size / delta)
    vals = (bennett_psi(b)[None, :] * V[:, None] + log_term) / b[None, :]
    return vals.min(axis=1)


@dataclass(frozen=True)
class BanditTicket:
    """One decision, waiting for its feedback."""

    id: int
    score: float
    threshold: float
    commit: bool
    #: The item is shown to the user (commit, policy OFFER, or exploration).
    shown: bool
    #: Shown only because of forced exploration (shown as an OFFER, never committed).
    explore: bool
    #: Probability that this item is shown, given the past and its score.
    propensity: float
    top1: str | None = None


@dataclass
class BanditCommitRiskControl:
    """Online COMMIT threshold with shown-only feedback (module docstring)::

        rc = BanditCommitRiskControl(alpha=0.05, explore=0.05)   # seed=None: OS entropy
        for item in session:
            tk = rc.decide(score(item), offered=policy_offers(item))
            if tk.commit: insert top-1          # the user may correct it
            elif tk.shown: show as OFFER        # the user picks or retypes
            else: withhold (ASK / ABSTAIN)
            ...                                 # later, maybe out of order:
            rc.observe(tk, commit_loss)         # None if no label arrived
        rc.report()                             # realised rate, certificate, audit

    The audit counts every item at ``decide`` time (a shown item as wrong until
    its label arrives), so late, out-of-order or never-returned feedback keeps
    (G3) valid; it only makes the bound larger. The ACI state (G1 / G2) moves
    at ``observe`` time, on the realised losses.
    """

    #: marginal: allowed wrong-commit rate per decided item; precision: allowed error rate among commits.
    alpha: float = 0.05
    target: BanditTarget = "marginal"
    rule: BanditRule = "aci"
    #: Forced exploration rate for withheld items (shown as an OFFER). 0: no audit, rule "aci" only.
    explore: float = 0.05
    delta: float = 0.1
    eta: float = 0.05
    #: Start threshold; None: never commit at the start (ACI moves it down).
    lam_init: float | None = None
    lam_min: float = 0.0
    score_max: float = 1.0
    grid: Sequence[float] = DEFAULT_GRID
    bets: Sequence[float] = DEFAULT_BETS
    #: Seed of the exploration coins. None (default): fresh OS entropy, required for (G3) in live use
    #: (the coins must be unpredictable to the data source). Fixed seeds: replays and tests only.
    seed: int | None = None

    # --- state ---
    lam_t: float = math.nan
    lam_1: float = math.nan
    n_obs: int = 0
    n_commit_obs: int = 0
    n_commits: int = 0
    n_explore: int = 0
    n_shown: int = 0
    n_missing: int = 0
    sum_loss: float = 0.0
    _next_id: int = 0
    _pending: dict[int, BanditTicket] = field(default_factory=dict)
    _rng: Any = None

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        if self.target not in ("marginal", "precision"):
            raise ValueError(f"unknown target {self.target!r}")
        if self.rule not in ("aci", "cs", "max"):
            raise ValueError(f"unknown rule {self.rule!r}")
        if not 0.0 <= self.explore <= 1.0:
            raise ValueError("explore must be in [0, 1]")
        if self.rule != "aci" and self.explore <= 0:
            raise ValueError("rules 'cs' and 'max' need explore > 0")
        if self.eta <= 0:
            raise ValueError("eta must be > 0")
        g = np.asarray(self.grid, dtype=np.float64)
        if g.ndim != 1 or g.size == 0 or not np.all(np.isfinite(g)) or np.any(np.diff(g) <= 0):
            raise ValueError("grid must be finite and strictly increasing")
        self._g = g
        K = g.size
        self._SX = np.zeros(K)      # sum of IPW terms X_i(lam_k)
        self._V = np.zeros(K)       # variance proxy V_t(lam_k)
        self._N = np.zeros(K)       # N_t(lam_k): decided items with s_i >= lam_k
        self._NC_lab = np.zeros(K)  # naive complete case: labelled items with s_i >= lam_k
        self._NW_lab = np.zeros(K)  # naive complete case: labelled wrong items with s_i >= lam_k
        self._n_lab = 0
        self._n_seen = 0            # items in the audit (= decided items; added at decide time)
        self._rng = np.random.default_rng(self.seed)
        if math.isnan(self.lam_t):
            lam = self._never if self.lam_init is None or not math.isfinite(self.lam_init) else float(self.lam_init)
            self.lam_t = self.lam_1 = max(self.lam_min, lam)
        self._cs_cache: float | None = None

    @property
    def _never(self) -> float:
        return math.nextafter(self.score_max, math.inf)

    # --- audit (G3) ---------------------------------------------------------

    def audit_upper(self) -> np.ndarray:
        """(G3) upper bound of the counterfactual wrong-commit COUNT per grid threshold (inf if explore = 0)."""
        if self.explore <= 0:
            return np.where(self._V > 0, math.inf, self._SX)
        return self._SX + ipw_slack(self._V, self._g.size, self.delta, self.bets)

    def _lam_cs(self) -> float:
        if self._cs_cache is not None:
            return self._cs_cache
        ub = self.audit_upper()
        if self.target == "marginal":
            ok = (self._n_seen > 0) & (ub <= self.alpha * self._n_seen)
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                ok = (self._N >= 1) & (ub <= self.alpha * self._N)
        # smallest certified grid point; the certified set need not be an interval, take the first
        idx = np.flatnonzero(ok)
        lam = float(self._g[idx[0]]) if idx.size else math.inf
        self._cs_cache = lam = max(self.lam_min, lam) if math.isfinite(lam) else self._never
        return lam

    @property
    def threshold(self) -> float:
        """The current COMMIT threshold (commit iff score >= threshold)."""
        if self.rule == "aci":
            return self.lam_t
        if self.rule == "cs":
            return self._lam_cs()
        return max(self.lam_t, self._lam_cs())

    # --- online loop ----------------------------------------------------------

    def decide(self, score: float, offered: bool = False, top1: str | None = None) -> BanditTicket:
        """Decide one item. ``offered``: the policy shows it anyway as an OFFER (propensity 1)."""
        if math.isnan(score):
            raise ValueError("score must not be nan (use -inf for 'never commit')")
        lam = self.threshold
        commit = bool(score >= lam)
        explore = False
        if commit or offered:
            shown, pi = True, 1.0
        else:
            # one coin per withheld item (the stream does not depend on the score);
            # s = -inf: no grid threshold commits it, so it is never explored (pi = 0)
            pi = float(self.explore) if score > -math.inf else 0.0
            u = self._rng.random() if self.explore > 0 else 1.0
            explore = shown = bool(pi > 0 and u < pi)
        tk = BanditTicket(self._next_id, float(score), lam, commit, shown, explore, pi, top1)
        self._next_id += 1
        self._pending[tk.id] = tk
        self.n_explore += explore
        self.n_shown += shown
        # (G3) audit, in decision order: add the item NOW (H1 fix); a shown item counts as wrong
        # (c^ = 1) until observe() lowers it to its label
        above = score >= self._g
        self._n_seen += 1
        self._N += above
        if shown:
            self._SX += above * (1.0 / pi)
        if pi < 1.0 and score > -math.inf:
            self._V += above / max(pi, 1e-300)
        self._cs_cache = None
        return tk

    @property
    def pending(self) -> int:
        return len(self._pending)

    def observe(self, ticket: BanditTicket, commit_loss: float | None) -> float:
        """Feed back one item. Return its realised wrong-commit loss.

        ``commit_loss`` = c (1 if the top-1 text is wrong), or None if no
        label arrived. For a withheld item pass None (any value is ignored:
        the system does not see it). A shown item with no label counts as
        c = 1 in the audit (pessimistic) and, for a commit, in the loss.
        """
        if self._pending.pop(ticket.id, None) is None:
            raise KeyError(f"ticket {ticket.id} is not pending (observed twice?)")
        if commit_loss is not None and not 0.0 <= commit_loss <= 1.0:
            raise ValueError("commit_loss must be in [0, 1]")
        c = None if not ticket.shown else commit_loss
        if ticket.shown and c is None:
            self.n_missing += 1
        c_hat = 1.0 if c is None else float(c)
        loss = c_hat if ticket.commit else 0.0
        self.n_obs += 1
        self.n_commits += ticket.commit
        self.sum_loss += loss
        # audit: decide() added this item with c^ = 1; lower X to the label (never raises it)
        above = ticket.score >= self._g
        if ticket.shown and c_hat < 1.0:
            self._SX -= above * ((1.0 - c_hat) / ticket.propensity)
        if ticket.shown and c is not None:
            self._n_lab += 1
            self._NC_lab += above
            self._NW_lab += above * float(c)
        self._cs_cache = None
        # ACI state (G1 / G2)
        if self.target == "marginal":
            self.lam_t = max(self.lam_min, self.lam_t + self.eta * (loss - self.alpha))
        elif ticket.commit:
            self.n_commit_obs += 1
            self.lam_t = max(self.lam_min, self.lam_t + self.eta * (loss - self.alpha))
        return loss

    def step(self, score: float, commit_loss: float | None, offered: bool = False) -> BanditTicket:
        """decide() then observe() at once. ``commit_loss`` is the TRUE c; it is hidden unless shown."""
        tk = self.decide(score, offered)
        self.observe(tk, commit_loss if tk.shown else None)
        return tk

    def report(self) -> dict[str, Any]:
        """Realised rate, the (G1)/(G2) certificate and the (G3) audit at every grid threshold."""
        T = self.n_obs
        mean = self.sum_loss / T if T else math.nan
        nc = self.n_commit_obs
        cert = math.nan
        if self.target == "marginal" and T:
            cert = self.alpha + (self.lam_t - self.lam_1) / (self.eta * T)
            realised = mean
        else:
            realised = self.sum_loss / nc if nc else math.nan
            if nc:
                cert = self.alpha + (self.lam_t - self.lam_1) / (self.eta * nc)
        ub = self.audit_upper()
        with np.errstate(divide="ignore", invalid="ignore"):
            n = max(self._n_seen, 1)
            audit = {
                "grid": self._g.tolist(),
                "n_at": self._N.tolist(),
                "ipw_wrong": self._SX.tolist(),
                "upper_wrong": ub.tolist(),
                "upper_marginal": (ub / n).tolist(),
                "upper_precision_error": np.where(self._N > 0, ub / np.maximum(self._N, 1), math.nan).tolist(),
                "naive_marginal": (self._NW_lab / max(self._n_lab, 1)).tolist(),
                "naive_precision_error": np.where(self._NC_lab > 0, self._NW_lab / np.maximum(self._NC_lab, 1),
                                                  math.nan).tolist(),
            }
        return {
            "target": self.target,
            "rule": self.rule,
            "alpha": self.alpha,
            "explore": self.explore,
            "delta": self.delta,
            "n_observed": T,
            "n_decided": self._n_seen,
            "n_commits": self.n_commits,
            "n_shown": self.n_shown,
            "n_explore": self.n_explore,
            "n_missing": self.n_missing,
            "pending": self.pending,
            "realised": realised,
            "certificate": cert,
            "threshold": self.threshold,
            "lam_aci": self.lam_t,
            "lam_1": self.lam_1,
            "audit": audit,
            "guarantee": {
                "marginal": "(G1) long-run wrong-commit rate per item, any sequence, observed labels only",
                "precision": "(G2) long-run error rate among commits, any sequence, observed labels only",
            }[self.target] + ("; (G3) audit, design-based, prob >= 1 - delta over the exploration coins"
                              if self.explore > 0 else ""),
        }



@dataclass
class NaiveShownOnlyControl:
    """The BIASED baseline (for tests and replays only; do not deploy).

    Picks the smallest grid threshold whose complete-case error estimate
    (computed from the SHOWN items only, as if they were a random sample)
    is <= alpha (plug-in, no correction). ``target="precision"``:
    wrong / commits among labelled items with ``s >= lam``. The shown items
    are the high-score ones, so at thresholds below the current one the
    estimate is too optimistic. No exploration, no weights.
    """

    alpha: float = 0.05
    target: BanditTarget = "precision"
    grid: Sequence[float] = DEFAULT_GRID
    min_labels: int = 10
    lam_init: float | None = None
    score_max: float = 1.0
    n_obs: int = 0
    n_commits: int = 0
    n_wrong: int = 0

    def __post_init__(self) -> None:
        self._g = np.asarray(self.grid, dtype=np.float64)
        self._C = np.zeros(self._g.size)
        self._W = np.zeros(self._g.size)
        self._n_lab = 0
        self._lam = math.nextafter(self.score_max, math.inf) if self.lam_init is None else float(self.lam_init)

    @property
    def threshold(self) -> float:
        return self._lam

    def step(self, score: float, commit_loss: float, offered: bool = False) -> bool:
        commit = bool(score >= self._lam)
        self.n_obs += 1
        if commit:
            self.n_commits += 1
            self.n_wrong += commit_loss
        if commit or offered:  # shown: the label arrives
            above = score >= self._g
            self._n_lab += 1
            self._C += above
            self._W += above * float(commit_loss)
            if self._n_lab >= self.min_labels:
                if self.target == "precision":
                    est = self._W / np.maximum(self._C, 1.0)
                    ok = (self._C >= 1) & (est <= self.alpha)
                else:
                    ok = self._W / self._n_lab <= self.alpha
                idx = np.flatnonzero(ok)
                self._lam = float(self._g[idx[0]]) if idx.size else math.nextafter(self.score_max, math.inf)
        return commit


class BanditTrustPolicy:
    """A :class:`~fidetype.trust.policy.DecisionPolicy` whose COMMIT threshold follows a
    :class:`BanditCommitRiskControl`; an explored item is shown as an OFFER (never committed).

    Same use as :class:`~fidetype.trust.online_risk.OnlineTrustPolicy`::

        bp = BanditTrustPolicy(policy, BanditCommitRiskControl(explore=0.05))
        decision, tk = bp.decide(x)
        ...
        bp.feedback(tk, final_text)   # the user's final text if shown, else None
    """

    def __init__(self, policy: Any, controller: BanditCommitRiskControl) -> None:
        from fidetype.trust.policy import DecisionPolicy

        self.controller = controller
        self.policy = policy
        self._lo = DecisionPolicy(replace(policy.config, commit_p=-math.inf), use_guard=policy.use_guard)
        self._hi = DecisionPolicy(replace(policy.config, commit_p=math.inf), use_guard=policy.use_guard)

    def decide(self, x: Any, final_attempt: bool = False) -> tuple[Any, BanditTicket]:
        from fidetype.trust.policy import Action, Decision

        d_lo = self._lo.decide(x, final_attempt=final_attempt)
        score = float(x.p_top1) if d_lo.action == Action.COMMIT else -math.inf
        d_hi = self._hi.decide(x, final_attempt=final_attempt)
        offered = d_hi.action in (Action.OFFER, Action.OFFER_WORDS)
        top1 = x.texts[0] if x.texts else None
        tk = self.controller.decide(score, offered, top1)
        if tk.commit:
            return d_lo, tk
        if tk.explore:
            k = self.policy.config.offer_max_k
            return Decision(Action.OFFER, tuple(x.texts[:k]), "exploration: offer (bandit audit)"), tk
        return d_hi, tk

    def feedback(self, ticket: BanditTicket, truth: str | None) -> float:
        """Feed back the true text if the item was shown (None: no label). Return the realised loss."""
        if not ticket.shown or truth is None:
            return self.controller.observe(ticket, None)
        return self.controller.observe(ticket, float(ticket.top1 is None or ticket.top1 != truth))
