"""Adaptive (online) risk control on the drop-in guard (P5-02).

The drop-in guard (:func:`fidetype.trust.calibrate`) fixes ``commit_p``
once. Its guarantee needs exchangeable data. Live use is not
exchangeable: the signal drifts within a session and between days, and
the decoder can change. This module puts the existing online
controllers behind the drop-in API, so the same guard can adapt its
COMMIT threshold from the user's feedback::

    import fidetype.trust as ft

    guard = ft.calibrate(cal_inputs, cal_texts, ...)      # offline, as before
    og = guard.online("aci")                               # or "aci_window", "window", "bandit"
    r, tk = og.decide(x)                                   # r: a TrustResult (commit / offer / withhold)
    ...
    og.feedback(tk, final_text)                            # the user's final text, or None if unknown
    print(og.report()["certificate"])                      # long-run bound, any sequence
    for s in og.policy_sheets(): print(s)                  # offline sheet(s) + the online sheet

No new statistics: the controllers are
:class:`~fidetype.trust.online_risk.OnlineCommitRiskControl` (methods
``"aci"``, ``"aci_window"``, ``"window"``; M2 / P15-02) and
:class:`~fidetype.trust.bandit_risk.BanditCommitRiskControl` (method
``"bandit"``; P15-04). This module only connects them to the guard.

=================  ==========================================================  ======================
method             guarantee                                                   feedback it needs
=================  ==========================================================  ======================
``"aci"``          mean wrong-commit loss <= alpha + (lam_end - lam_1)/(eta T)  the loss of each
                   for ANY sequence (Gibbs & Candes 2021)                      decision (commit labels)
``"aci_window"``   mean loss <= alpha + (alpha_1 - alpha_end)/(gamma T), any   full feedback for the
                   sequence; window CRC at an adaptive level                   window
``"window"``       approximate only (weighted CRC)                             full feedback
``"bandit"``       (G1) marginal or (G2) precision ACI, any sequence; with     shown-only feedback
                   ``explore > 0`` also the (G3) anytime IPW audit
=================  ==========================================================  ======================

How a decision is made. The guard runs once with ``commit_p = 0`` (all
other rules, the commit gate and the P15-06 grounding gate unchanged).
If it would COMMIT, the commit score is its calibrated ``p_top1``; else
the score is ``-inf``. The controller commits iff ``score >= threshold``.
Otherwise the decision is the policy's own no-commit decision (OFFER,
OFFER_WORDS, ASK or ABSTAIN) on the same inputs; with ``"bandit"`` a
withheld item can be shown as an OFFER for exploration (never a commit).

Floor (``floor=True``, default). The online threshold never goes below
the offline ``commit_p`` of the guard: the online policy then commits a
subset of the offline commits, so the offline bound (under
exchangeability) still holds, and the online bound holds for any
sequence on top. The cost: if the offline guard never commits
(``commit_p = inf``), the online guard never commits either. With
``floor=False`` only the online bound holds.

Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Literal

from fidetype.trust.policy import Action, Decision

__all__ = ["OnlineGuard", "online", "ONLINE_METHODS"]

ONLINE_METHODS = ("aci", "aci_window", "window", "bandit")
OnlineGuardMethod = Literal["aci", "aci_window", "window", "bandit"]


class OnlineGuard:
    """A drop-in guard whose COMMIT threshold follows an online controller (module docstring).

    Make it with :meth:`fidetype.trust.dropin.TrustGuard.online` or :func:`online`. Decisions go
    into the audit log of the wrapped guard (with an ``online`` record).

    The guard's configuration is read once, here. After a decoder update that swaps the guard's
    configuration (:class:`~fidetype.trust.update_hooks.TrustGuardUpdater`), make a new online guard
    (the ACI certificate restarts with it).
    """

    def __init__(self, guard: Any, controller: Any, *, method: str, floor: float) -> None:
        from fidetype.trust.dropin import TrustGuard

        self.guard = guard
        self.controller = controller
        self.method = method
        #: The lowest threshold (the offline ``commit_p`` with ``floor=True``, else -inf).
        self.floor = float(floor)
        self._g0 = TrustGuard(guard.config.with_policy(commit_p=0.0), guard._codec, None, guard._user_decode,
                              guard.audit_text, halluc_gate=guard.halluc_gate, grounding=guard.grounding)
        self._hi = guard.config.with_policy(commit_p=math.inf).build().policy
        self._offer_k = int(guard.config.policy.get("offer_max_k", 3))
        self.n_decisions = 0

    @property
    def threshold(self) -> float:
        """The current COMMIT threshold (commit iff the commit score >= threshold)."""
        return float(self.controller.threshold)

    def decide(self, x: Any, *, utterance_id: str | None = None) -> tuple[Any, Any]:
        """Decide one input. Returns ``(TrustResult, ticket)``; give the ticket back to :meth:`feedback`."""
        from fidetype.trust.dropin import _user_reason

        events, _ = self.guard._codec.events(x)
        sd0, why = self._g0._final_gated(events)
        inputs = sd0.inputs
        can = sd0.decision.action == Action.COMMIT
        score = float(inputs.p_top1) if can else -math.inf
        if score < self.floor:
            score = -math.inf
        top1 = inputs.texts[0] if inputs.texts else None
        thr = self.threshold
        bandit = self.method == "bandit"
        d_hi = None
        if not can or score < thr:
            d_hi = self._hi.decide(inputs, final_attempt=True) if can else sd0.decision
        if bandit:
            offered = (d_hi.action in (Action.OFFER, Action.OFFER_WORDS)) if d_hi is not None else True
            tk = self.controller.decide(score, offered, top1)
        else:
            ow = d_hi is not None and d_hi.action == Action.OFFER_WORDS
            tk = self.controller.decide(score, top1, ow)
        if tk.commit:
            d = sd0.decision
        elif bandit and tk.explore:
            d = Decision(Action.OFFER, tuple(inputs.texts[:self._offer_k]), "exploration: offer (bandit audit)")
        else:
            if d_hi is None:  # the controller moved between the check and decide (not expected)
                d_hi = self._hi.decide(inputs, final_attempt=True)
            d = d_hi
        sd = replace(sd0, decision=d, provenance={**sd0.provenance, "config_id": self.guard.config_id,
                                                  "commit_threshold": thr if math.isfinite(thr) else None})
        r = self.guard._result(sd, why if (why is not None and not tk.commit) else None)
        r = replace(r, reason=(r.reason if why is not None and not tk.commit else
                               _user_reason(d.reason, float(inputs.p_top1), float(inputs.guard_risk), thr)),
                    config_id=self.guard.config_id, seq=self.guard._seq)
        self.guard._log(r, events, utterance_id, {"online": {"method": self.method, "threshold": _jf(thr),
                                                             "ticket": tk.id, "score": _jf(score),
                                                             "explore": bool(getattr(tk, "explore", False))}})
        self.n_decisions += 1
        return r, tk

    def feedback(self, ticket: Any, truth: str | None) -> float | None:
        """Feed back the user's final text for a ticket (None: unknown / not shown). Returns the loss used."""
        from fidetype.trust.dropin import _norm_text

        t = None if truth is None else _norm_text(truth)
        if self.method == "bandit":
            if not ticket.shown or t is None:
                return self.controller.observe(ticket, None)
            return self.controller.observe(ticket, float(ticket.top1 is None or ticket.top1 != t))
        ctrl = self.controller
        if t is None:
            f = ctrl.B if (ticket.fallback_offer_words and ctrl.missing == "pessimistic") else 0.0
            return ctrl.observe(ticket, None, f)
        c = float(ticket.top1 is None or ticket.top1 != t)
        return ctrl.observe(ticket, c, c if ticket.fallback_offer_words else 0.0)

    def report(self) -> dict[str, Any]:
        """The controller report (realised rate, certificate, threshold), plus the floor and the method."""
        rep = dict(self.controller.report())
        rep["floor"] = self.floor
        rep["online_method"] = self.method
        rep["base_config_id"] = self.guard.config_id
        return rep

    def policy_sheets(self) -> list[Any]:
        """The sheets of the wrapped guard (offline bounds) plus the online sheet (P5-02)."""
        from fidetype.trust import guarantee_sheet as G

        base = G.policy_sheets(self.guard) if self.guard.sheet is not None else []
        scope = f"live decisions of guard {self.guard.config_id} ({self.n_decisions} so far)"
        fl = self.floor if math.isfinite(self.floor) else None
        if self.method == "bandit":
            s = G.sheet_from_bandit(self.controller, scope=scope, config_id=self.guard.config_id, floor=fl)
        else:
            s = G.sheet_from_online(self.controller, scope=scope, config_id=self.guard.config_id, floor=fl)
        if fl is not None:
            s = replace(s, assumptions=s.assumptions + (
                f"The online threshold never goes below the offline commit_p {fl:g}, so the offline sheet(s) "
                "still hold under their own assumptions.",))
        return base + [s]

    def __repr__(self) -> str:
        return f"OnlineGuard(method={self.method!r}, threshold={self.threshold:g}, base={self.guard.config_id!r})"


def _jf(x: float) -> float | str:
    return x if math.isfinite(x) else ("inf" if x > 0 else "-inf")


def online(guard: Any, method: OnlineGuardMethod = "aci", *, alpha: float | None = None, floor: bool = True,
           eta: float = 0.05, gamma: float = 0.005, window: int | None = 200, decay: float | None = None,
           missing: Literal["skip", "pessimistic"] = "skip", target: Literal["marginal", "precision"] = "marginal",
           rule: Literal["aci", "cs", "max"] = "aci", explore: float = 0.0, delta: float | None = None,
           lam_init: float | None = None, seed: int | None = 0) -> OnlineGuard:
    """Wrap a calibrated :class:`~fidetype.trust.dropin.TrustGuard` in an online controller.

    Parameters
    ----------
    method
        ``"aci"`` (default), ``"aci_window"``, ``"window"`` or ``"bandit"`` (see the module table).
    alpha
        Allowed rate (default: the guard's alpha). ``"bandit"`` with ``target="precision"``: the
        allowed error rate among commits.
    floor
        Keep the online threshold at or above the guard's offline ``commit_p`` (default True).
    eta, gamma, window, decay, missing
        Controller settings (:class:`~fidetype.trust.online_risk.OnlineCommitRiskControl`).
    target, rule, explore, delta
        ``"bandit"`` only (:class:`~fidetype.trust.bandit_risk.BanditCommitRiskControl`; ``delta``
        defaults to the guard's delta). ``explore > 0`` shows withheld items as an OFFER at that rate
        and turns on the audit.
    lam_init
        Start threshold. Default: the offline ``commit_p`` if finite, else "never commit" (ACI then
        lowers it while the losses stay below alpha).
    seed
        ``"bandit"``: seed of the exploration coins.
    """
    from fidetype.trust.bandit_risk import BanditCommitRiskControl
    from fidetype.trust.online_risk import OnlineCommitRiskControl

    if method not in ONLINE_METHODS:
        raise ValueError(f"method must be one of {ONLINE_METHODS}, not {method!r}")
    if method != "bandit" and (target != "marginal" or rule != "aci" or explore != 0.0):
        raise ValueError("target, rule and explore are for method='bandit' only")
    a = float(guard.alpha if alpha is None else alpha)
    c0 = float(guard.config.policy.get("commit_p", math.inf))
    fl = c0 if floor else -math.inf
    start = lam_init if lam_init is not None else (c0 if math.isfinite(c0) else None)
    lam_min = max(0.0, fl) if math.isfinite(fl) else 0.0
    if floor and not math.isfinite(c0):
        lam_min, start = 0.0, None  # the floor removes every commit; the score check in decide() does it
    if method == "bandit":
        ctrl = BanditCommitRiskControl(alpha=a, target=target, rule=rule, explore=float(explore),
                                       delta=float(guard.delta if delta is None else delta), eta=eta,
                                       lam_init=start, lam_min=lam_min, seed=seed)
    else:
        ctrl = OnlineCommitRiskControl(alpha=a, method=method, window=window, decay=decay, eta=eta, gamma=gamma,
                                       lam_init=start, lam_min=lam_min, missing=missing)
    return OnlineGuard(guard, ctrl, method=method, floor=fl)
