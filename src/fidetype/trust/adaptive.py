"""Trust core module: keep the COMMIT guarantee valid while the decoder learns (F1, P15-01 / P15-02).

A self-improving decoder changes after every update. A threshold that was
calibrated for the old decoder says nothing about the new one. This module
gives two parts for a feedback loop. Both are our own implementation.

1. :class:`FeedbackUser` -- a simulated user that answers COMMIT and OFFER
   decisions from the known intended text. It returns the label the system
   will learn from and the loss the system can see. A wrong commit that the
   user does not notice is a **silent error**: the system sees loss 0 and
   takes the wrong text as a label.

2. :class:`GuardedUpdateLoop` -- a champion / challenger gate around the
   existing tools of :mod:`fidetype.trust.session_risk` and
   :mod:`fidetype.trust.online_risk`::

       loop = GuardedUpdateLoop(alpha=0.05, delta=0.1)
       loop.start_session("day-12")             # new day: needs a new check block
       loop.new_version("v12a", trained_on=ids) # each decoder update: a new version
       for item in check_block:                 # >= n_check items the version did NOT train on
           loop.add_check_item(item.id, score, commit_loss)   # offer-only meanwhile
       loop.recalibrate()                       # block LTT -> session threshold
       for item in rest_of_session:
           d = loop.decide(score, text_ok=bool(text.strip()))
           ...                                  # COMMIT iff d.commit
           loop.observe(d, observed_commit_loss)

Rules the loop enforces:

- A version commits only after :meth:`recalibrate` on a fresh block of at
  least ``n_check`` items (default :func:`min_ltt_items`, 45 for alpha
  0.05, delta 0.1). A check item that the version trained on raises.
- A check item with unknown truth counts as a wrong commit at every
  threshold where it would commit (pessimistic).
- COMMIT iff ``score >= max(lambda_session, lambda_aci)``, the commit gate
  (``text_ok``) is open and the session monitor has not alarmed.
- The ACI controller (``method="aci"``) runs across all sessions and all
  versions. It is fed only while the loop can commit.

Guarantees (and what they do not cover):

- Per session, after a recalibration: ``P(R <= alpha) >= 1 - delta`` for
  the rest of the session, if the rest is exchangeable with the check
  block and the version does not change (:func:`block_ltt`).
- Long run, any sequence, across all updates:
  ``(1/T) sum L_obs <= alpha + (lambda_T+1 - lambda_1) / (eta T)`` on the
  **observed** losses (:class:`OnlineCommitRiskControl`). The telescoping
  argument does not depend on how the commit was decided, so the max with
  the session threshold keeps it.
- :class:`SessionRiskMonitor`: false alarm <= gamma per session.
- **Silent errors are not covered.** The observed loss of a silent error
  is 0. Measure the silent-error rate separately (``FeedbackOutcome``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Hashable, Iterable, Sequence

import numpy as np

from fidetype.trust.online_risk import OnlineCommitRiskControl, Ticket
from fidetype.trust.session_risk import SessionRiskMonitor, SessionThreshold, block_ltt, min_ltt_items

__all__ = ["FeedbackOutcome", "FeedbackUser", "GuardedDecision", "GuardedUpdateLoop", "char_error_rate"]


def char_error_rate(hyp: str, ref: str) -> float:
    """Levenshtein distance of the characters / len(ref) (1.0 for an empty ref and a non-empty hyp)."""
    if not ref:
        return 0.0 if not hyp else 1.0
    d = list(range(len(ref) + 1))
    for i in range(1, len(hyp) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(ref) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (hyp[i - 1] != ref[j - 1]))
            prev, d[j] = d[j], cur
    return d[-1] / len(ref)


@dataclass(frozen=True)
class FeedbackOutcome:
    """What one user response gives the system, and the truth about it."""

    #: Text the system will treat as the truth (None: no label). Wrong for a silent error or a sloppy accept.
    label: str | None
    #: "accept", "sloppy-accept", "retype", "reject", "kept", "correction" or "silent".
    source: str
    #: Loss of a COMMIT as the system sees it (None for an OFFER).
    observed_commit_loss: float | None
    #: True loss: 1 for a wrong COMMIT, else 0.
    true_loss: float
    silent_error: bool
    #: Is the label equal to the truth? (None if there is no label.)
    label_correct: bool | None

    @property
    def truth_known(self) -> bool:
        """True if the system holds the correct text and knows it (accept, retype, correction)."""
        return self.source in ("accept", "retype", "correction")


@dataclass
class FeedbackUser:
    """Simulated user for a feedback loop (accept / reject / retype / correct).

    - OFFER: accept if the truth is in the offered list. Else, with
      ``p_sloppy``, accept the first offered text with a character error
      rate <= ``sloppy_max_cer`` (a wrong label); else retype the truth with
      ``p_retype``, else reject (no label).
    - COMMIT right: kept (the label is the committed text).
    - COMMIT wrong: corrected with ``p_notice`` (the label is the truth,
      observed loss 1); else a silent error (the label is the wrong text,
      observed loss 0, true loss 1).
    """

    p_notice: float = 1.0
    p_retype: float = 1.0
    p_sloppy: float = 0.0
    sloppy_max_cer: float = 0.1

    def __post_init__(self) -> None:
        for k in ("p_notice", "p_retype", "p_sloppy"):
            v = getattr(self, k)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{k} must be in [0, 1]")

    def respond_offer(self, offered: Sequence[str], truth: str, rng: np.random.Generator) -> FeedbackOutcome:
        if truth in offered:
            return FeedbackOutcome(truth, "accept", None, 0.0, False, True)
        if self.p_sloppy > 0.0 and rng.random() < self.p_sloppy:
            for c in offered:
                if char_error_rate(c, truth) <= self.sloppy_max_cer:
                    return FeedbackOutcome(c, "sloppy-accept", None, 0.0, False, c == truth)
        if rng.random() < self.p_retype:
            return FeedbackOutcome(truth, "retype", None, 0.0, False, True)
        return FeedbackOutcome(None, "reject", None, 0.0, False, None)

    def respond_commit(self, text: str, truth: str, rng: np.random.Generator) -> FeedbackOutcome:
        if text == truth:
            return FeedbackOutcome(text, "kept", 0.0, 0.0, False, True)
        if rng.random() < self.p_notice:
            return FeedbackOutcome(truth, "correction", 1.0, 1.0, False, True)
        return FeedbackOutcome(text, "silent", 0.0, 1.0, True, False)


@dataclass(frozen=True)
class GuardedDecision:
    """One decision of :class:`GuardedUpdateLoop`."""

    commit: bool
    score: float
    threshold: float
    version: Hashable | None
    #: "commit", "below-threshold", "gate", "check-block" (no valid calibration yet), "offer-only" (infeasible), "alarm".
    reason: str
    ticket: Ticket | None = None


@dataclass
class GuardedUpdateLoop:
    """Champion / challenger gate: re-calibrate the COMMIT threshold after every decoder update (module docstring)."""

    alpha: float = 0.05
    delta: float = 0.1
    gamma: float = 0.1
    eta: float = 0.05
    n_check: int | None = None
    lam_init: float | None = None
    score_max: float = 1.0
    grid: Sequence[float] | None = None

    # --- state ---
    aci: OnlineCommitRiskControl = field(init=False)
    monitor: SessionRiskMonitor = field(init=False)
    version: Hashable | None = None
    session: Hashable | None = None
    lambda_session: float = math.inf
    calibrated: bool = False
    trained_on: set = field(default_factory=set)
    check_ids: list = field(default_factory=list)
    check_scores: list = field(default_factory=list)
    check_losses: list = field(default_factory=list)
    history: list = field(default_factory=list)
    n_alarms: int = 0
    n_versions: int = 0

    def __post_init__(self) -> None:
        if self.n_check is None:
            self.n_check = min_ltt_items(self.alpha, self.delta)
        if self.n_check < min_ltt_items(self.alpha, self.delta):
            raise ValueError(f"n_check must be >= min_ltt_items(alpha, delta) = {min_ltt_items(self.alpha, self.delta)}")
        self.aci = OnlineCommitRiskControl(alpha=self.alpha, method="aci", eta=self.eta, lam_init=self.lam_init,
                                           score_max=self.score_max)
        self.monitor = SessionRiskMonitor(alpha=self.alpha, gamma=self.gamma)

    # --- lifecycle -------------------------------------------------------------

    def _invalidate(self) -> None:
        self.lambda_session = math.inf
        self.calibrated = False
        self.check_ids, self.check_scores, self.check_losses = [], [], []

    def start_session(self, session: Hashable) -> None:
        """A new session (day): the old check block no longer describes the data. New monitor."""
        self.session = session
        self.monitor = SessionRiskMonitor(alpha=self.alpha, gamma=self.gamma)
        self._invalidate()

    def new_version(self, version: Hashable, trained_on: Iterable[Hashable] = ()) -> None:
        """Register a decoder update. It may not commit before :meth:`recalibrate` on a fresh block."""
        self.version = version
        self.trained_on = set(trained_on)
        self.n_versions += 1
        self._invalidate()

    def add_check_item(self, item_id: Hashable, score: float, commit_loss: float | None) -> None:
        """Add one item of the check block (scored by the current version; truth via OFFER feedback).

        ``commit_loss`` = 1 if the version's top-1 text is wrong, 0 if right, None if the truth stays unknown.
        """
        if item_id in self.trained_on:
            raise ValueError(f"check item {item_id!r} was used to train version {self.version!r}")
        if math.isnan(score):
            raise ValueError("score must not be nan (use -inf)")
        self.check_ids.append(item_id)
        self.check_scores.append(float(score))
        self.check_losses.append(1.0 if commit_loss is None else float(commit_loss))  # pessimistic

    @property
    def n_check_items(self) -> int:
        return len(self.check_ids)

    def recalibrate(self) -> SessionThreshold:
        """Block LTT on the check block. Sets the session threshold (inf if infeasible)."""
        if self.n_check_items < self.n_check:
            raise ValueError(f"check block has {self.n_check_items} items; need >= {self.n_check}")
        st = block_ltt(self.check_scores, self.check_losses, None, self.alpha, self.delta, None, self.grid)
        self.lambda_session = st.threshold
        self.calibrated = True
        self.history.append({"session": self.session, "version": self.version, "n_check": self.n_check_items,
                             "lambda_session": st.threshold,
                             "feasible": math.isfinite(st.threshold) and st.threshold <= self.score_max})
        return st

    # --- online ------------------------------------------------------------------

    @property
    def can_commit(self) -> bool:
        """True if the loop is in commit mode (calibrated, feasible, no alarm)."""
        return (self.calibrated and math.isfinite(self.lambda_session) and self.lambda_session <= self.score_max
                and not self.monitor.alarmed)

    @property
    def threshold(self) -> float:
        return max(self.lambda_session, self.aci.threshold) if self.can_commit else math.inf

    def decide(self, score: float, text_ok: bool = True) -> GuardedDecision:
        """COMMIT iff in commit mode, ``score >= max(lambda_session, lambda_aci)`` and ``text_ok``."""
        if math.isnan(score):
            raise ValueError("score must not be nan (use -inf)")
        if not self.calibrated:
            return GuardedDecision(False, score, math.inf, self.version, "check-block")
        if self.monitor.alarmed:
            return GuardedDecision(False, score, math.inf, self.version, "alarm")
        if not self.can_commit:
            return GuardedDecision(False, score, math.inf, self.version, "offer-only")
        eff = score if (text_ok and score >= self.lambda_session) else -math.inf
        tk = self.aci.decide(eff)
        thr = max(self.lambda_session, tk.threshold)
        if tk.commit:
            reason = "commit"
        elif not text_ok:
            reason = "gate"
        else:
            reason = "below-threshold"
        return GuardedDecision(bool(tk.commit), score, thr, self.version, reason, tk)

    def observe(self, decision: GuardedDecision, observed_commit_loss: float | None) -> float | None:
        """Feed back the loss the system sees (0 for an OFFER; for a COMMIT 1 if corrected, else 0)."""
        if decision.ticket is None:
            return None
        loss = self.aci.observe(decision.ticket, observed_commit_loss if decision.commit else None)
        if loss is not None:
            was = self.monitor.alarmed
            if self.monitor.update(loss) and not was:
                self.n_alarms += 1
        return loss

    def report(self) -> dict[str, Any]:
        r = self.aci.report()
        return {"alpha": self.alpha, "delta": self.delta, "gamma": self.gamma, "n_check": self.n_check,
                "aci": r, "n_alarms": self.n_alarms, "n_versions": self.n_versions,
                "n_recalibrations": len(self.history),
                "n_feasible": sum(h["feasible"] for h in self.history),
                "silent_errors": "not covered (observed losses only)"}
