"""Commit gate: a minimum-content rule and a strict guard cap for COMMIT (M2-18, opt-in).

Problem
-------
The guard gives an empty top-1 text the highest risk, 1.0
(:meth:`~fidetype.trust.guard.HallucinationGuard.score`: its
low-evidence term is set to 1.0). The policy commits when
``guard_risk <= commit_max_risk``. The default policy grid contains
``commit_max_risk = 1.0``, and with that value the test is always true:
the guard limit is off. An empty text (risk 1.0) is then committed if
its calibrated ``p_top1`` is at least ``commit_p``. On near-uniform
(no-signal) streams a word decoder often returns only the empty text,
so ``p_top1`` is high. In the T12 v2 validation dry run (M3-28) the
Paper 1 v4 recipe chose ``commit_max_risk = 1.0`` and committed 335 of
400 uniform control streams: 320 empty texts and 15 short texts, all
with guard risk 1.0
(``experiments/2026-11-13-m2-18-empty-commits/results.md``).

Gate
----
:class:`CommitGate` says what a COMMIT needs:

``min_chars``
    at least this many non-white-space characters (default 1: no empty
    commit);
``min_words``
    at least this many words (default 0: no limit);
``max_guard_risk``
    if not None, the guard risk must be strictly below this value. With
    ``1.0`` a text whose guard risk is 1.0 (every character has low
    acoustic evidence, or the text is empty) is never committed, even
    if the fitted ``commit_max_risk`` is 1.0. Ignored if the policy does
    not use the guard.

If a COMMIT fails the gate, :func:`gate_decision` replaces it by the
decision of the same policy with ``commit_p = +inf`` (the "no commit"
path: OFFER, OFFER_WORDS, ASK or ABSTAIN, by the normal rules). The
reason starts with ``"commit gate: "``.

Safety of the risk bound
------------------------
The gate only removes commits. For one item the loss of the fallback
decision is at most the loss of the commit (the fallback loss is 1
only for a wrong OFFER_WORDS, and then the commit loss is 1 too; see
:func:`~fidetype.trust.risk_control.commit_calibration_data`). So a CRC
or LTT bound that holds for the policy without the gate also holds with
the gate. The gate can be added to a fitted configuration without a new
calibration.

Default
-------
Off. :class:`~fidetype.trust.frozen.FrozenTrustConfig` has the field
``commit_gate`` (an empty dict = off). With the field empty, the
configuration, its ``config_id`` and its decisions are the same as
before M2-18 (Paper 1 v4 behaviour).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from fidetype.trust.policy import Action, Decision, DecisionPolicy, PolicyConfig, PolicyInputs

#: Prefix of the reason of a gated decision.
REASON_PREFIX = "commit gate: "


@dataclass(frozen=True)
class CommitGate:
    """What a COMMIT needs (module docstring). ``CommitGate()`` forbids only an empty commit."""

    #: Minimum number of non-white-space characters.
    min_chars: int = 1
    #: Minimum number of words (white-space separated).
    min_words: int = 0
    #: If not None: COMMIT only if guard_risk < max_guard_risk (strict).
    max_guard_risk: float | None = None

    def __post_init__(self) -> None:
        if self.min_chars < 0 or self.min_words < 0:
            raise ValueError("min_chars and min_words must be >= 0")
        if self.max_guard_risk is not None and not (0.0 < float(self.max_guard_risk) <= 1.0):
            raise ValueError("max_guard_risk must be in (0, 1] or None")

    def violation(self, text: str | None, guard_risk: float | None = None) -> str | None:
        """Return why a COMMIT of ``text`` is not allowed, or None if it is."""
        t = text or ""
        n_chars = sum(not ch.isspace() for ch in t)
        n_words = len(t.split())
        if n_chars < self.min_chars:
            return "empty text" if n_chars == 0 else f"{n_chars} characters < {self.min_chars}"
        if n_words < self.min_words:
            return f"{n_words} words < {self.min_words}"
        if self.max_guard_risk is not None and guard_risk is not None and not (guard_risk < self.max_guard_risk):
            return f"guard risk {guard_risk:.2f} >= {self.max_guard_risk:.2f}"
        return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CommitGate":
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown commit_gate keys {sorted(unknown)}")
        kw: dict[str, Any] = {k: int(d[k]) for k in ("min_chars", "min_words") if k in d}
        if d.get("max_guard_risk") is not None:
            kw["max_guard_risk"] = float(d["max_guard_risk"])
        return cls(**kw)


def no_commit_policy(policy: Any) -> DecisionPolicy:
    """The same policy with ``commit_p = +inf`` (it never commits)."""
    return DecisionPolicy(replace(policy.config, commit_p=math.inf), use_guard=policy.use_guard)


def gate_decision(
    decision: Decision,
    inputs: PolicyInputs,
    gate: CommitGate | None,
    policy: Any,
    final_attempt: bool = False,
) -> Decision:
    """Apply ``gate`` to one decision of ``policy``.

    A COMMIT that fails the gate becomes the decision of
    :func:`no_commit_policy` on the same inputs. Other decisions, and all
    decisions with ``gate=None``, are returned unchanged. ``policy`` must
    have ``config`` (a :class:`PolicyConfig`) and ``use_guard``.
    """
    if gate is None or decision.action != Action.COMMIT:
        return decision
    text = decision.shown_candidates[0] if decision.shown_candidates else ""
    risk = float(inputs.guard_risk) if getattr(policy, "use_guard", True) else None
    why = gate.violation(text, risk)
    if why is None:
        return decision
    d2 = no_commit_policy(policy).decide(inputs, final_attempt=final_attempt)
    return replace(d2, reason=f"{REASON_PREFIX}{why}; {d2.reason}")


class GatedPolicy(DecisionPolicy):
    """A :class:`DecisionPolicy` whose COMMITs pass a :class:`CommitGate`.

    It is a subclass, so code that reads ``config`` and ``use_guard``
    works. Note: helpers that build a new ``DecisionPolicy`` from
    ``policy.config`` (``CommitRiskControl.apply``,
    ``commit_calibration_data``, the online controllers) drop the gate.
    That is safe for the risk bound (module docstring); re-wrap the
    result with :meth:`wrap` to keep the gate.
    :class:`~fidetype.trust.streaming.StreamingTrustLayer` applies the
    gate of its configuration on every decision path.
    """

    def __init__(self, config: PolicyConfig | None = None, use_guard: bool = True,
                 gate: CommitGate | None = None) -> None:
        super().__init__(config, use_guard=use_guard)
        self.gate = gate or CommitGate()

    @classmethod
    def wrap(cls, policy: DecisionPolicy, gate: CommitGate | None = None) -> "GatedPolicy":
        return cls(policy.config, use_guard=policy.use_guard, gate=gate)

    def decide(self, x: PolicyInputs, final_attempt: bool = False) -> Decision:
        d = super().decide(x, final_attempt=final_attempt)
        return gate_decision(d, x, self.gate, self, final_attempt)
