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
   existing tools of :mod:`fidetype.trust.session_risk`,
   :mod:`fidetype.trust.online_risk` and :mod:`fidetype.trust.content`::

       loop = GuardedUpdateLoop(alpha=0.05, delta=0.1)     # evidence gate ON by default
       loop.start_session("day-12")             # new day: needs a new check block
       loop.set_champion("v11", trained_on=old) # optional: the version that runs now (the fallback)
       loop.new_version("v12a", trained_on=ids) # each decoder update: a challenger
       for item in check_block:                 # >= n_check items the version did NOT train on
           loop.add_check_item(item.id, score, commit_loss, text=top1, guard_risk=risk,
                               champion=(champ_score, champ_loss, champ_risk, champ_top1))
       loop.recalibrate()                       # block LTT -> session threshold
       loop.check_null_controls(uniform=[(score, text, risk), ...], shuffled=[...])
       rec = loop.finish_update()               # accept (new config_id) or reject (champion back)
       if loop.version != "v12a":               # rejected: the champion is back on the same block
           loop.check_null_controls(...)        # with the champion's outputs on null input
           loop.finish_update()
       for item in rest_of_session:
           d = loop.decide(score, text=top1, guard_risk=risk)
           ...                                  # COMMIT iff d.commit
           loop.observe(d, observed_commit_loss)

Rules the loop enforces (P15-02):

- **Evidence commit gate, on by default.** ``commit_gate`` must be a
  :class:`~fidetype.trust.content.CommitGate` with ``max_guard_risk``
  (M2-18; default ``CommitGate(min_chars=1, max_guard_risk=1.0)``, the
  drop-in ``COMMIT_GATE``). A COMMIT needs a guard risk strictly below
  ``max_guard_risk``. A decision without a guard risk never commits. The
  loop refuses to start without such a gate unless ``unsafe=True``
  (repo rule of 2026-11-15: every re-tune enables the commit gate and
  passes the uniform and frame-shuffled null controls).
- A version commits only after :meth:`recalibrate` on a fresh block of at
  least ``n_check`` items (default :func:`min_ltt_items`, 45 for alpha
  0.05, delta 0.1). A check item that the version trained on raises.
- A check item with unknown truth counts as a wrong commit at every
  threshold where it would commit (pessimistic). A check item that the
  gate is known to refuse never commits (its score becomes -inf). A check
  item without a guard risk keeps its raw score (conservative).
- **Per-update null refusal.** After :meth:`recalibrate`,
  :meth:`check_null_controls` counts the commits of the version on
  uniform (no-signal) and frame-shuffled null inputs at the session
  threshold, through the gate. A control fails if its commits exceed
  ``floor(rate * n)`` (``rate = null_max_commit_rate``, default
  ``alpha``; the rule of :func:`fidetype.trust.dropin.calibrate`).
- **Champion / challenger.** :meth:`finish_update` accepts the version
  only if both null controls pass, the optional precision check passes
  and the champion / challenger test passes on the same check block
  (``challenger_test``, level ``challenger_level``; see "Champion /
  challenger test" below). An accepted update gets a new ``config_id``. A
  rejected one is logged; the champion comes back (calibrated on the same
  block, if its block outputs were given) and must pass its own null
  controls before it commits. Without champion outputs the session is
  offer-only.
- **No champion outputs, no acceptance (P15-23, 2026-11-18).** With the
  default test, a challenger whose champion outputs on the check block are
  missing (for some or all items) is refused: the comparison cannot run,
  and default deny counts that against the challenger. The explicit,
  recorded opt-out is ``allow_missing_champion=True`` (the decision record
  then carries a note). ``challenger_test="sign"`` keeps the P15-02
  behaviour (the test is skipped). The first version without a champion
  and the champion's own re-check after a rollback need no comparison.
- Each :meth:`finish_update` writes an :class:`UpdateRecord`
  (:attr:`updates`, :meth:`audit_records`).
- **Ledger (optional).** With ``ledger=`` (a
  :class:`~fidetype.trust.provenance.ProvenanceLedger`), every proposal
  (:meth:`new_version`, the first decision on an initial champion, a
  rollback) and every decision (:meth:`finish_update`,
  :meth:`reject_proposal`) is written as an append-only, hash-chained
  ``update`` entry (chain ``ledger_chain``). Session ids and versions go
  through the ledger's ``id_mode``; trained-on ids only as a count and a
  hash.
- **Hooks.** :meth:`add_listener` registers ``fn(record, loop)``. It runs
  after each decision, before the ledger entry; a returned dict goes into
  the entry (``details.hooks``). :mod:`fidetype.trust.update_hooks` uses
  this to swap a :class:`~fidetype.trust.dropin.TrustGuard` configuration
  or an :class:`~fidetype.trust.online_risk.OnlineTrustPolicy` policy only
  on an accepted update.
- COMMIT iff the active version was accepted in this session,
  ``score >= max(lambda_session, lambda_aci)``, the gate passes and the
  session monitor has not alarmed.
- The ACI controller (``method="aci"``) runs across all sessions and all
  versions. It is fed only while the loop can commit.

Precision check (P5-02 link). The bounds below count wrong commits over
**all** items. With rare commits they hold at any precision (the P15-01
pilot: 88-100 % of commits wrong). :meth:`recalibrate` therefore reports
the share of wrong items among the block items that would commit
(``block_wrong_among_commits``). With ``max_wrong_among_commits`` set,
:meth:`finish_update` rejects a version whose share is above it. Default:
``None`` (report only). This check is a plug-in estimate, not a
guarantee.

Champion / challenger test (P15-13, 2026-11-18). Two tests are available:

- ``challenger_test="noninferiority"`` (default, "default deny"). The
  challenger must **show** that it is not materially worse. Each check
  item is a pair (challenger, champion). Primary loss: top-1 right or
  wrong. Tie-break: the character error rate (CER) of the top-1 texts,
  when the truth is known (``truth=`` of :meth:`add_check_item`). An item
  with unknown truth is never evidence for the challenger: if the
  challenger could be worse there, the pair counts as **worse**. Rules:
  identical top-1 texts are a tie; a challenger that is right is never
  worse; a champion known to be wrong (``commit_loss`` 1, or its text is
  in ``not_truth``) makes the pair a tie when the challenger's result is
  unknown; every other pair with an unknown side counts as worse.
  With ``w`` worse (unknown included), ``b`` better, ``n = w + b`` and
  ``N`` items, the test passes if ``p = min(1, 2 min(p_ni, p_abs)) <=
  challenger_level``, where ``p_ni = P(Bin(n, 0.5 + challenger_margin)
  <= w)`` (among the items where the two differ, the challenger is worse
  on less than ``0.5 + margin``) and ``p_abs = P(Bin(N,
  challenger_margin_abs) <= w)`` (the challenger is worse on less than
  ``margin_abs`` of all items). If the two top-1 texts are equal on every
  item, the test passes (no top-1 change). Guarantee: if the true share
  of worse items among differing items is at least ``0.5 + margin`` and
  the true share of worse items is at least ``margin_abs``, the gate
  accepts with probability at most ``challenger_level`` (exact binomial
  tests, Bonferroni; unknown items only add to ``w``). Few labelled
  items therefore give a rejection, never an acceptance.
- **Same-decoder re-calibration rule (P15-24, 2026-11-18).** A proposal
  registered with ``new_version(..., kind="recalibration")`` keeps the
  decoder and changes only the guard (thresholds, temperatures). Its
  top-1 texts differ from the champion's on few items, so the first
  branch has almost no data, and the Bonferroni split leaves the second
  branch at ``level / 2``: with ``N = 48`` and ``margin_abs`` 0.1 no
  worse item is allowed. With ``recalibration_rule="absolute"`` (default)
  such a proposal uses the absolute branch alone at the full level: pass
  if ``p_abs = P(Bin(N, margin_abs) <= w) <= challenger_level`` (``N =
  48``: ``w <= 1``), or if the top-1 texts are identical. Guarantee: if
  the true share of worse items is at least ``margin_abs``, the gate
  accepts with probability at most ``challenger_level``. This null
  hypothesis contains the null hypothesis of the decoder rule, so the
  documented guarantee holds for any proposal, also for a decoder change
  that is wrongly declared a re-calibration (such a proposal only loses
  power). The new thresholds themselves are checked by the block LTT on
  the same check block, as for every version.
  ``recalibration_rule="decoder"`` uses the decoder rule (the P15-13
  behaviour).
- ``challenger_test="sign"`` (the P15-02 behaviour, kept for
  reproducibility). Paired exact sign test on top-1 errors; unknown truth
  counts as wrong for **both** sides; reject only if the challenger is
  significantly worse. With partial feedback most pairs are "both wrong"
  and the test has no power: on M4-13 it accepted a time-reversed decoder
  (P15-03a, 2 worse vs 0 better, p 0.25).

``unsafe=True`` (not for real use) gives the pre-P15-02 behaviour: any
gate (``None`` = refuse empty text only), no null controls and no
:meth:`finish_update` needed (:meth:`recalibrate` makes the version live).

Guarantees (and what they do not cover):

- Per session, after a recalibration: ``P(R <= alpha) >= 1 - delta`` for
  the rest of the session, if the rest is exchangeable with the check
  block and the version does not change (:func:`block_ltt`). The gate and
  the null refusal only remove commits, so they keep this bound.
- Long run, any sequence, across all updates:
  ``(1/T) sum L_obs <= alpha + (lambda_T+1 - lambda_1) / (eta T)`` on the
  **observed** losses (:class:`OnlineCommitRiskControl`). The telescoping
  argument does not depend on how the commit was decided, so the max with
  the session threshold keeps it.
- :class:`SessionRiskMonitor`: false alarm <= gamma per session.
- The null controls are a refusal rule, not a bound: a version that
  passes them can still commit on other kinds of null input.
- **Silent errors are not covered.** The observed loss of a silent error
  is 0. Measure the silent-error rate separately (``FeedbackOutcome``).

Breaking change (P15-02, 2026-11-16): with the default (safe) settings,
the old flow ``new_version -> add_check_item -> recalibrate -> decide``
no longer commits. Add guard risks, :meth:`check_null_controls` and
:meth:`finish_update`, or pass ``unsafe=True`` for the old behaviour.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Hashable, Iterable, Mapping, Sequence

import numpy as np

from fidetype.trust.content import CommitGate
from fidetype.trust.dropin import ControlResult
from fidetype.trust.online_risk import OnlineCommitRiskControl, Ticket
from fidetype.trust.session_risk import (
    SessionRiskMonitor,
    SessionThreshold,
    binomial_upper_pvalue,
    block_ltt,
    min_ltt_items,
)
from fidetype.utils.binomial import binom_cdf

__all__ = [
    "DEFAULT_EVIDENCE_GATE",
    "ChallengerTest",
    "FeedbackOutcome",
    "FeedbackUser",
    "GuardedDecision",
    "GuardedUpdateLoop",
    "UpdateRecord",
    "char_error_rate",
]

#: The default commit gate of :class:`GuardedUpdateLoop` (M2-18; same as the drop-in ``COMMIT_GATE``).
DEFAULT_EVIDENCE_GATE = CommitGate(min_chars=1, min_words=0, max_guard_risk=1.0)


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
    #: "commit", "below-threshold", "gate", "check-block" (no valid calibration yet), "offer-only" (infeasible),
    #: "alarm", "update-pending" (no accepted :meth:`GuardedUpdateLoop.finish_update` yet), "rejected".
    reason: str
    ticket: Ticket | None = None


@dataclass(frozen=True)
class ChallengerTest:
    """Champion / challenger test on the check block (module docstring, "Champion / challenger test").

    ``method="sign"`` (P15-02): paired exact sign test on top-1 errors; ``p_value`` =
    ``P(Bin(worse_only + better_only, 0.5) >= worse_only)``; refused if ``p_value <= level``.
    ``method="noninferiority"`` (P15-13 default): ``worse_only`` includes the pairs with unknown truth
    (``n_unknown``); ``p_value`` = ``min(1, 2 min(p_noninferior, p_abs))``; refused unless
    ``passed_by`` is set. The ``legacy_*`` fields give the P15-02 sign test on the same block (report only).
    ``rule="recalibration"`` (P15-24): ``p_value`` = ``p_abs`` (the absolute branch at the full level).
    """

    n: int
    challenger_wrong: int
    champion_wrong: int
    #: Items where the challenger is worse / better than the champion.
    worse_only: int
    better_only: int
    p_value: float
    level: float
    method: str = "sign"
    margin: float | None = None
    margin_abs: float | None = None
    #: Pairs counted as worse because a result is unknown (included in ``worse_only``).
    n_unknown: int = 0
    #: Pairs with identical top-1 texts / other ties.
    n_identical: int = 0
    n_tie: int = 0
    #: Pairs where the two top-1 results differ only in CER (both wrong, truth known).
    n_cer_decided: int = 0
    p_noninferior: float | None = None
    p_abs: float | None = None
    #: Why the test passed ("noninferior", "few worse items", "identical top-1"); None: refused.
    passed_by: str | None = None
    legacy_worse: int | None = None
    legacy_better: int | None = None
    legacy_p_value: float | None = None
    #: "decoder" (two branches, Bonferroni) or "recalibration" (P15-24: the absolute branch at the full level).
    rule: str = "decoder"

    @property
    def refused(self) -> bool:
        if self.method == "sign":
            return self.p_value <= self.level
        return self.passed_by is None

    def to_dict(self) -> dict[str, Any]:
        d = {"n": self.n, "challenger_wrong": self.challenger_wrong, "champion_wrong": self.champion_wrong,
             "worse_only": self.worse_only, "better_only": self.better_only, "p_value": self.p_value,
             "level": self.level, "refused": self.refused}
        if self.method != "sign":  # the P15-02 records keep their exact keys
            d.update(method=self.method, margin=self.margin, margin_abs=self.margin_abs, n_unknown=self.n_unknown,
                     n_identical=self.n_identical, n_tie=self.n_tie, n_cer_decided=self.n_cer_decided,
                     p_noninferior=self.p_noninferior, p_abs=self.p_abs, passed_by=self.passed_by,
                     legacy_worse=self.legacy_worse, legacy_better=self.legacy_better,
                     legacy_p_value=self.legacy_p_value)
            if self.rule != "decoder":  # the P15-13 records keep their exact keys
                d["rule"] = self.rule
        return d


@dataclass(frozen=True)
class UpdateRecord:
    """Audit record of one :meth:`GuardedUpdateLoop.finish_update` decision."""

    index: int
    session: Hashable | None
    version: Hashable | None
    champion_before: Hashable | None
    accepted: bool
    #: Why the update was refused (empty if accepted).
    reasons: tuple[str, ...]
    parent_config_id: str | None
    #: The loop's ``config_id`` after the decision (new on accept, unchanged on reject).
    config_id: str | None
    #: The version that is active after the decision (the champion after a rollback).
    active_version: Hashable | None
    lambda_session: float
    feasible: bool
    n_check: int
    n_block_commits: int
    block_wrong_among_commits: float | None
    controls: tuple[ControlResult, ...]
    challenger_test: ChallengerTest | None
    gate: Mapping[str, Any] | None
    unsafe: bool
    #: Recorded notes, for example an opt-out of a default-deny rule (P15-23). Empty: no key in the dict.
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        def j(x: Any) -> Any:
            if isinstance(x, float) and not math.isfinite(x):
                return str(x)
            return x if isinstance(x, (str, int, float, bool)) or x is None else repr(x)

        return {"index": self.index, "session": j(self.session), "version": j(self.version),
                "champion_before": j(self.champion_before), "accepted": self.accepted,
                "reasons": list(self.reasons), "parent_config_id": self.parent_config_id,
                "config_id": self.config_id, "active_version": j(self.active_version),
                "lambda_session": j(float(self.lambda_session)), "feasible": self.feasible, "n_check": self.n_check,
                "n_block_commits": self.n_block_commits, "block_wrong_among_commits": self.block_wrong_among_commits,
                "controls": [c.to_dict() for c in self.controls],
                "challenger_test": None if self.challenger_test is None else self.challenger_test.to_dict(),
                "gate": None if self.gate is None else dict(self.gate), "unsafe": self.unsafe,
                **({"notes": list(self.notes)} if self.notes else {})}


def _status(loss: float | None, text: str | None, truth: str | None, not_truth: frozenset) -> tuple:
    """One side of a check pair: ("right", 0.0), ("wrong", cer or None) or ("unknown", None)."""
    if truth is not None and text is not None:
        t, r = " ".join(text.split()), " ".join(str(truth).split())
        return ("right", 0.0) if t == r else ("wrong", min(1.0, char_error_rate(t, r)))
    if loss is not None:
        return ("right", 0.0) if float(loss) < 0.5 else ("wrong", None)
    if text is not None and " ".join(text.split()) in not_truth:
        return ("wrong", None)
    return ("unknown", None)


def _pair_outcome(ch: tuple, cp: tuple, identical: bool) -> str:
    """Outcome of one (challenger, champion) pair: worse, better, tie or unknown (counted as worse)."""
    if ch[0] != "unknown" and cp[0] != "unknown":
        if ch[0] == cp[0] == "right":
            return "tie"
        if ch[0] == "right":
            return "better"
        if cp[0] == "right":
            return "worse"
        if ch[1] is not None and cp[1] is not None:  # both wrong, truth known: CER tie-break
            if ch[1] > cp[1] + 1e-12:
                return "worse"
            if ch[1] < cp[1] - 1e-12:
                return "better"
        return "tie"
    if identical or ch[0] == "right" or cp[0] == "wrong":
        return "tie"  # equal texts; a right challenger is never worse; a wrong champion cannot be beaten
    return "unknown"


def _null_item(x: Any) -> tuple[float, str | None, bool, float | None]:
    """(score, text, text_ok, guard_risk) from ``(score, text_or_ok[, guard_risk])`` or a dict."""
    if isinstance(x, Mapping):
        score, text, risk = x["score"], x.get("text"), x.get("guard_risk")
        ok = x.get("text_ok", True)
    else:
        t = tuple(x)
        score = t[0]
        text = t[1] if len(t) > 1 else None
        risk = t[2] if len(t) > 2 else None
        ok = True
    if isinstance(text, bool):
        ok, text = text, None
    s = float(score)
    if math.isnan(s):
        raise ValueError("score must not be nan (use -inf)")
    return s, text, bool(ok), (None if risk is None else float(risk))


@dataclass
class GuardedUpdateLoop:
    """Champion / challenger gate: re-calibrate and re-check the COMMIT rule after every decoder update.

    See the module docstring for the lifecycle, the rules and the guarantees.
    """

    alpha: float = 0.05
    delta: float = 0.1
    gamma: float = 0.1
    eta: float = 0.05
    n_check: int | None = None
    lam_init: float | None = None
    score_max: float = 1.0
    grid: Sequence[float] | None = None
    #: The COMMIT gate. Must have ``max_guard_risk`` unless ``unsafe`` (None + unsafe: empty text refused only).
    commit_gate: CommitGate | None = field(default_factory=lambda: DEFAULT_EVIDENCE_GATE)
    #: Null-control pass rule: commits <= floor(rate * n). None: ``alpha``.
    null_max_commit_rate: float | None = None
    #: If set: reject a version whose block share of wrong among commits is above this (P5-02 link).
    max_wrong_among_commits: float | None = None
    #: Level of the champion / challenger test.
    challenger_level: float = 0.05
    #: "noninferiority" (P15-13 default: default deny) or "sign" (P15-02 behaviour, for reproducibility).
    challenger_test: str = "noninferiority"
    #: Non-inferiority margins (module docstring); fixed before a run.
    challenger_margin: float = 0.1
    challenger_margin_abs: float = 0.1
    #: P15-23: accept a challenger without champion outputs (explicit, recorded opt-out of default deny).
    allow_missing_champion: bool = False
    #: P15-24: test for ``kind="recalibration"`` proposals: "absolute" (default) or "decoder" (P15-13 behaviour).
    recalibration_rule: str = "absolute"
    #: Pre-P15-02 behaviour (no evidence gate needed, no null controls, no finish_update). Not for real use.
    unsafe: bool = False
    #: Optional :class:`~fidetype.trust.provenance.ProvenanceLedger`: one ``update`` entry per proposal / decision.
    ledger: Any = field(default=None, repr=False, compare=False)
    #: Chain name of this loop in the ledger.
    ledger_chain: str = "guarded-update-loop"

    # --- state ---
    aci: OnlineCommitRiskControl = field(init=False)
    monitor: SessionRiskMonitor = field(init=False)
    version: Hashable | None = None
    #: "decoder" or "recalibration" (P15-24): the kind of the current proposal (see :meth:`new_version`).
    version_kind: str = "decoder"
    session: Hashable | None = None
    lambda_session: float = math.inf
    calibrated: bool = False
    trained_on: set = field(default_factory=set)
    check_ids: list = field(default_factory=list)
    check_scores: list = field(default_factory=list)
    check_losses: list = field(default_factory=list)
    check_champion: list = field(default_factory=list)
    #: Per check item: (challenger status, champion status, identical top-1 texts); see ``_status``.
    check_pairs: list = field(default_factory=list)
    history: list = field(default_factory=list)
    n_alarms: int = 0
    n_versions: int = 0
    champion: Hashable | None = None
    champion_trained_on: set = field(default_factory=set)
    config_id: str | None = None
    accepted: bool = False
    rejected: bool = False
    controls: list = field(default_factory=list)
    controls_passed: bool | None = None
    n_block_commits: int = 0
    block_wrong_among_commits: float | None = None
    updates: list = field(default_factory=list)
    listeners: list = field(default_factory=list, repr=False, compare=False)
    #: update_id of the open (undecided) proposal in the ledger, and its origin.
    open_update: str | None = field(default=None, repr=False)
    _n_proposals: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self.n_check is None:
            self.n_check = min_ltt_items(self.alpha, self.delta)
        if self.n_check < min_ltt_items(self.alpha, self.delta):
            raise ValueError(f"n_check must be >= min_ltt_items(alpha, delta) = {min_ltt_items(self.alpha, self.delta)}")
        if not self.unsafe and (self.commit_gate is None or self.commit_gate.max_guard_risk is None):
            raise ValueError(
                "GuardedUpdateLoop needs an evidence commit gate: CommitGate(max_guard_risk=...) (M2-18). "
                "A loop without it commits LM-only text on no-signal input (P15-01 pilot, S5). "
                "Pass unsafe=True only for experiments that reproduce the old behaviour.")
        if self.commit_gate is None:
            self.commit_gate = CommitGate()
        if self.null_max_commit_rate is not None and not 0.0 <= self.null_max_commit_rate < 1.0:
            raise ValueError("null_max_commit_rate must be in [0, 1)")
        if self.max_wrong_among_commits is not None and not 0.0 <= self.max_wrong_among_commits <= 1.0:
            raise ValueError("max_wrong_among_commits must be in [0, 1]")
        if not 0.0 < self.challenger_level < 1.0:
            raise ValueError("challenger_level must be in (0, 1)")
        if self.challenger_test not in ("noninferiority", "sign"):
            raise ValueError("challenger_test must be 'noninferiority' or 'sign'")
        if not 0.0 <= self.challenger_margin < 0.5:
            raise ValueError("challenger_margin must be in [0, 0.5)")
        if not 0.0 < self.challenger_margin_abs < 1.0:
            raise ValueError("challenger_margin_abs must be in (0, 1)")
        if self.recalibration_rule not in ("absolute", "decoder"):
            raise ValueError("recalibration_rule must be 'absolute' or 'decoder'")
        self.aci = OnlineCommitRiskControl(alpha=self.alpha, method="aci", eta=self.eta, lam_init=self.lam_init,
                                           score_max=self.score_max)
        self.monitor = SessionRiskMonitor(alpha=self.alpha, gamma=self.gamma)
        if self.ledger is not None and self.config_id is None:
            # continue the chain of an existing ledger file
            self.config_id = self.ledger.chain_head(self.ledger_chain)

    # --- hooks and ledger --------------------------------------------------------

    def add_listener(self, fn: Any) -> Any:
        """Register ``fn(record: UpdateRecord, loop) -> dict | None``; it runs after each update decision.

        A returned dict goes into the ledger entry (``details.hooks``). An exception in a listener is
        written to the ledger (``details.hook_error``) and then raised again. Returns ``fn``.
        """
        self.listeners.append(fn)
        return fn

    def _lid(self, x: Any) -> Any:
        return None if x is None else self.ledger.id_value(repr(x))

    def _propose(self, origin: str) -> None:
        """Write a ``proposed`` ledger entry for the current version (no-op without a ledger)."""
        if self.ledger is None:
            return
        if self.open_update is not None and self.ledger.is_open_update(self.open_update):
            # a superseded proposal: close it as rejected, so that every proposal has a decision
            self.ledger.record_update("rejected", self.open_update, chain=self.ledger_chain,
                                      parent_config_id=self.config_id, config_id=self.config_id,
                                      details={"reasons": ["superseded by a new proposal before a decision"]})
        uid = f"{self.ledger_chain}/{self._n_proposals}"
        while self.ledger.has_update(uid):  # a continued ledger file: skip the ids already used
            self._n_proposals += 1
            uid = f"{self.ledger_chain}/{self._n_proposals}"
        self._n_proposals += 1
        tr = sorted(repr(t) for t in self.trained_on)
        self.ledger.record_update("proposed", uid, chain=self.ledger_chain, parent_config_id=self.config_id,
                                  config_id=None, details={
                                      "origin": origin, "version": self._lid(self.version),
                                      "session": self._lid(self.session), "champion": self._lid(self.champion),
                                      "n_trained_on": len(tr),
                                      "trained_on_sha256": hashlib.sha256(
                                          json.dumps(tr).encode("utf-8")).hexdigest(),
                                      "alpha": self.alpha, "delta": self.delta, "unsafe": self.unsafe,
                                      **({"kind": self.version_kind} if self.version_kind != "decoder" else {})})
        self.open_update = uid

    def _decide_hooks(self, rec: "UpdateRecord") -> None:
        """Run the listeners, then write the decision to the ledger."""
        hooks: dict[str, Any] = {}
        error: BaseException | None = None
        for i, fn in enumerate(self.listeners):
            try:
                out = fn(rec, self)
            except Exception as e:  # noqa: BLE001 -- written to the ledger, then raised
                error = e
                break
            if out:
                name = getattr(fn, "hook_name", None) or getattr(getattr(fn, "__self__", None), "hook_name", None)
                hooks[name or f"hook{i}"] = out
        if self.ledger is not None:
            if self.open_update is None or not self.ledger.is_open_update(self.open_update):
                raise RuntimeError("internal: no open ledger proposal for this update")
            d = rec.to_dict()
            for k in ("session", "version", "champion_before", "active_version"):
                d[k] = self._lid(getattr(rec, k))
            d["hooks"] = hooks
            if error is not None:
                d["hook_error"] = f"{type(error).__name__}: {error}"
            self.ledger.record_update("accepted" if rec.accepted else "rejected", self.open_update,
                                      chain=self.ledger_chain, parent_config_id=rec.parent_config_id,
                                      config_id=rec.config_id, details=d)
            self.open_update = None
        if error is not None:
            raise error

    # --- gate ------------------------------------------------------------------

    @property
    def evidence_gate(self) -> bool:
        """True if the gate needs a guard risk below ``max_guard_risk`` (the P15-02 default)."""
        return self.commit_gate is not None and self.commit_gate.max_guard_risk is not None

    def gate_violation(self, text: str | None = None, guard_risk: float | None = None, text_ok: bool = True,
                       *, need_risk: bool = True) -> str | None:
        """Why the gate refuses a COMMIT (None: it allows it).

        ``text`` None: only ``text_ok`` says if the text is non-empty. ``need_risk``: with the evidence
        gate, a missing guard risk refuses (decisions); with ``need_risk=False`` it is ignored (check items).
        """
        g = self.commit_gate
        assert g is not None
        if not text_ok:
            return "empty text"
        if text is None:
            if g.min_chars > 1 or g.min_words > 0:
                return "text needed for the gate (min_chars > 1 or min_words > 0)"
            t = "x"
        else:
            t = text
        if g.max_guard_risk is not None and guard_risk is None and need_risk:
            return "no guard risk (evidence unknown)"
        if guard_risk is not None and math.isnan(guard_risk):
            return "guard risk nan"
        return g.violation(t, guard_risk)

    # --- lifecycle -------------------------------------------------------------

    def _invalidate(self) -> None:
        self.lambda_session = math.inf
        self.calibrated = False
        self.accepted = False
        self.rejected = False
        self.controls, self.controls_passed = [], None
        self.n_block_commits, self.block_wrong_among_commits = 0, None
        self.check_ids, self.check_scores, self.check_losses, self.check_champion = [], [], [], []
        self.check_pairs = []

    def start_session(self, session: Hashable) -> None:
        """A new session (day): the old check block no longer describes the data. New monitor."""
        self.session = session
        self.monitor = SessionRiskMonitor(alpha=self.alpha, gamma=self.gamma)
        self._invalidate()

    def set_champion(self, version: Hashable, trained_on: Iterable[Hashable] = ()) -> None:
        """Declare the fallback version (for example the decoder that runs now after an offline update).

        It does not make the version live: it commits only after a :meth:`finish_update` accepts it in
        this session (directly, or after a rollback from a rejected challenger).
        """
        self.champion = version
        self.champion_trained_on = set(trained_on)
        if self.version is None:
            self.version, self.trained_on = version, set(trained_on)
            self.version_kind = "decoder"

    def new_version(self, version: Hashable, trained_on: Iterable[Hashable] = (), *, kind: str = "decoder") -> None:
        """Register a decoder update (a challenger). It may not commit before the checks on a fresh block.

        ``kind``: ``"decoder"`` (default: a changed decoder) or ``"recalibration"`` (the same decoder, only the
        guard configuration changes; P15-24). The kind selects the champion / challenger rule (module
        docstring) and goes into the ledger proposal.
        """
        if kind not in ("decoder", "recalibration"):
            raise ValueError("kind must be 'decoder' or 'recalibration'")
        self.version = version
        self.version_kind = kind
        self.trained_on = set(trained_on)
        self.n_versions += 1
        self._invalidate()
        self._propose("new_version")

    def add_check_item(self, item_id: Hashable, score: float, commit_loss: float | None, *,
                       text: str | None = None, text_ok: bool = True, guard_risk: float | None = None,
                       champion: Sequence[Any] | None = None, truth: str | None = None,
                       not_truth: Iterable[str] = ()) -> None:
        """Add one item of the check block (scored by the current version; truth via OFFER feedback).

        ``commit_loss`` = 1 if the version's top-1 text is wrong, 0 if right, None if the truth stays unknown.
        ``text`` / ``text_ok`` / ``guard_risk``: the gate inputs of the item (a known gate refusal sets the
        score to -inf; no guard risk keeps the raw score). ``champion``: the champion's
        ``(score, commit_loss[, guard_risk[, text]])`` on the same item, for the champion / challenger test
        and a rollback. Give it for all items of the block or for none.
        ``truth`` (optional): the known true text; the non-inferiority test then breaks "both wrong" ties by
        the CER of the two top-1 texts. ``not_truth`` (optional): texts the user rejected on this item (for
        example the offered list when the truth stays unknown); a side whose top-1 text is in it is wrong.
        """
        if item_id in self.trained_on:
            raise ValueError(f"check item {item_id!r} was used to train version {self.version!r}")
        if math.isnan(score):
            raise ValueError("score must not be nan (use -inf)")
        eff = -math.inf if self.gate_violation(text, guard_risk, text_ok, need_risk=False) else float(score)
        self.check_ids.append(item_id)
        self.check_scores.append(eff)
        self.check_losses.append(1.0 if commit_loss is None else float(commit_loss))  # pessimistic
        nt = frozenset(" ".join(str(x).split()) for x in not_truth)
        ch_text = text if isinstance(text, str) else ("" if not text_ok else None)
        ch_status = _status(commit_loss, ch_text, truth, nt)
        if champion is not None:
            if item_id in self.champion_trained_on:
                raise ValueError(f"check item {item_id!r} was used to train the champion {self.champion!r}")
            c = tuple(champion)
            cs, cl = float(c[0]), (1.0 if c[1] is None else float(c[1]))
            if math.isnan(cs):
                raise ValueError("champion score must not be nan (use -inf)")
            cr = None if len(c) < 3 or c[2] is None else float(c[2])
            ct = c[3] if len(c) > 3 else None
            ok = not (isinstance(ct, str) and not ct.strip())
            ceff = -math.inf if self.gate_violation(ct if isinstance(ct, str) else None, cr, ok,
                                                    need_risk=False) else cs
            self.check_champion.append((ceff, cl))
            cp_text = ct if isinstance(ct, str) else None
            cp_status = _status(c[1], cp_text, truth, nt)
            ident = ch_text is not None and cp_text is not None and " ".join(ch_text.split()) == " ".join(
                cp_text.split())
            self.check_pairs.append((ch_status, cp_status, ident))
        else:
            self.check_champion.append(None)
            self.check_pairs.append(None)

    @property
    def n_check_items(self) -> int:
        return len(self.check_ids)

    def _calibrate(self, scores: Sequence[float], losses: Sequence[float]) -> SessionThreshold:
        st = block_ltt(scores, losses, None, self.alpha, self.delta, None, self.grid)
        self.lambda_session = st.threshold
        self.calibrated = True
        self.accepted = self.unsafe  # unsafe: live at once (old behaviour); safe: needs finish_update
        self.rejected = False
        self.controls, self.controls_passed = [], None
        if math.isfinite(st.threshold):
            com = [ls for s, ls in zip(scores, losses) if s >= st.threshold]
            self.n_block_commits = len(com)
            self.block_wrong_among_commits = (float(np.mean(com)) if com else None)
        else:
            self.n_block_commits, self.block_wrong_among_commits = 0, None
        self.history.append({"session": self.session, "version": self.version, "n_check": len(scores),
                             "lambda_session": st.threshold,
                             "feasible": math.isfinite(st.threshold) and st.threshold <= self.score_max,
                             "n_block_commits": self.n_block_commits,
                             "block_wrong_among_commits": self.block_wrong_among_commits})
        return st

    def recalibrate(self) -> SessionThreshold:
        """Block LTT on the check block. Sets the session threshold (inf if infeasible).

        Also sets ``n_block_commits`` and ``block_wrong_among_commits`` (the precision report).
        """
        if self.n_check_items < self.n_check:
            raise ValueError(f"check block has {self.n_check_items} items; need >= {self.n_check}")
        return self._calibrate(self.check_scores, self.check_losses)

    def _would_commit(self, score: float, text: str | None, text_ok: bool, guard_risk: float | None) -> bool:
        thr = self.lambda_session
        if not (math.isfinite(thr) and thr <= self.score_max) or score < thr:
            return False
        return self.gate_violation(text, guard_risk, text_ok, need_risk=True) is None

    def check_null_controls(self, uniform: Iterable[Any] = (), shuffled: Iterable[Any] = (),
                            user: Iterable[Any] = ()) -> list[ControlResult]:
        """Run the null controls of the current version at the session threshold, through the gate.

        Each item is ``(score, text_or_text_ok[, guard_risk])`` or a dict with ``score``, ``text`` /
        ``text_ok`` and ``guard_risk``: the version's output on one null input. A control fails if its
        commits exceed ``floor(rate * n)``. Both ``uniform`` and ``shuffled`` are required unless ``unsafe``.
        """
        if not self.calibrated:
            raise ValueError("recalibrate() before the null controls")
        sets = {"uniform": [_null_item(x) for x in uniform], "shuffled": [_null_item(x) for x in shuffled],
                "user": [_null_item(x) for x in user]}
        if not self.unsafe and (not sets["uniform"] or not sets["shuffled"]):
            raise ValueError("both uniform and frame-shuffled null controls are required")
        rate = float(self.alpha if self.null_max_commit_rate is None else self.null_max_commit_rate)
        desc = {"uniform": "uniform (no-signal) input", "shuffled": "frame-shuffled real input",
                "user": "caller null input"}
        out: list[ControlResult] = []
        for name, items in sets.items():
            if not items:
                continue
            k = sum(self._would_commit(s, t, ok, r) for s, t, ok, r in items)
            out.append(ControlResult(name, f"{desc[name]} through version {self.version!r}", len(items), int(k),
                                     int(math.floor(rate * len(items) + 1e-9))))
        self.controls = out
        self.controls_passed = all(c.passed for c in out)
        return out

    def _needs_comparison(self) -> bool:
        """True if a champion exists and the current version is a challenger to it."""
        return self.champion is not None and self.version != self.champion

    def _champion_outputs_missing(self) -> bool:
        """True if the champion's outputs are missing for at least one check item (P15-23)."""
        return not self.check_champion or any(c is None for c in self.check_champion)

    def _challenger_test(self) -> ChallengerTest | None:
        if not self._needs_comparison() or self._champion_outputs_missing():
            return None
        ch = np.asarray(self.check_losses) >= 0.5
        cp = np.asarray([c[1] for c in self.check_champion]) >= 0.5
        b, c = int(np.sum(ch & ~cp)), int(np.sum(~ch & cp))
        p = binomial_upper_pvalue(b, b + c, 0.5) if b + c else 1.0
        if self.challenger_test == "sign":
            return ChallengerTest(int(ch.size), int(ch.sum()), int(cp.sum()), b, c, float(p), self.challenger_level)
        return self._noninferiority_test(int(ch.sum()), int(cp.sum()), b, c, float(p))

    def _noninferiority_test(self, ch_wrong: int, cp_wrong: int, leg_b: int, leg_c: int,
                             leg_p: float) -> ChallengerTest:
        """Default-deny non-inferiority test (module docstring). Unknown results count against the challenger."""
        pairs = self.check_pairs
        if len(pairs) != len(self.check_ids) or any(q is None for q in pairs):
            raise RuntimeError("internal: champion outputs missing for the non-inferiority test")
        worse = better = unknown = ident = cer = 0
        for ch_s, cp_s, same in pairs:
            ident += bool(same)
            k = _pair_outcome(ch_s, cp_s, same)
            worse += k == "worse"
            better += k == "better"
            unknown += k == "unknown"
            if k in ("worse", "better") and ch_s[0] == "wrong" and cp_s[0] == "wrong":
                cer += 1
        n_items = len(pairs)
        w = worse + unknown
        n = w + better
        m, m_abs, lev = self.challenger_margin, self.challenger_margin_abs, self.challenger_level
        p_ni = binom_cdf(w, n, 0.5 + m) if n else 1.0
        p_abs = binom_cdf(w, n_items, m_abs) if n_items else 1.0
        recal = self.version_kind == "recalibration" and self.recalibration_rule == "absolute"
        p = p_abs if recal else min(1.0, 2.0 * min(p_ni, p_abs))
        passed: str | None = None
        if n_items and ident == n_items and w == 0:
            passed = "identical top-1"
        elif p <= lev:
            if recal:
                passed = "re-calibration: few worse items"
            else:
                passed = "noninferior" if p_ni <= p_abs else "few worse items"
        return ChallengerTest(n_items, ch_wrong, cp_wrong, w, better, float(p), lev, method="noninferiority",
                              margin=m, margin_abs=m_abs, n_unknown=unknown, n_identical=ident,
                              n_tie=n_items - w - better, n_cer_decided=cer, p_noninferior=float(p_ni),
                              p_abs=float(p_abs), passed_by=passed, legacy_worse=leg_b, legacy_better=leg_c,
                              legacy_p_value=leg_p, rule="recalibration" if recal else "decoder")

    def _new_config_id(self) -> str:
        g = self.commit_gate.to_dict() if self.commit_gate is not None else None
        lam = self.lambda_session
        payload = {"parent": self.config_id, "index": len(self.updates), "session": repr(self.session),
                   "version": repr(self.version), "lambda_session": lam if math.isfinite(lam) else str(lam),
                   "gate": g, "alpha": self.alpha, "delta": self.delta,
                   "null_max_commit_rate": self.null_max_commit_rate, "unsafe": self.unsafe}
        if self.challenger_test != "sign":  # P15-02 loops (sign test) keep their ids
            payload["challenger"] = {"test": self.challenger_test, "level": self.challenger_level,
                                     "margin": self.challenger_margin, "margin_abs": self.challenger_margin_abs}
            if self.allow_missing_champion:  # P15-13 loops keep their ids
                payload["challenger"]["allow_missing_champion"] = True
            if self.version_kind == "recalibration":
                payload["challenger"]["recalibration_rule"] = self.recalibration_rule
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f"gul-{h[:16]}"

    def finish_update(self) -> UpdateRecord:
        """Accept or reject the current version (module docstring). Returns the audit record.

        Accept: the version becomes the champion and goes live; ``config_id`` changes. Reject: the
        version is not used; if the champion's block outputs were given, the champion is calibrated on
        the same block and needs :meth:`check_null_controls` + :meth:`finish_update` before it commits;
        else the session is offer-only.
        """
        if not self.calibrated:
            raise ValueError("recalibrate() before finish_update()")
        if self.controls_passed is None and not self.unsafe:
            raise ValueError("check_null_controls() before finish_update()")
        if self.ledger is not None and (self.open_update is None or not self.ledger.is_open_update(self.open_update)):
            self._propose("initial" if not self.updates else "rollback")
        reasons: list[str] = []
        if self.controls_passed is False:
            bad = ", ".join(f"{c.name} {c.n_commit}/{c.n} > {c.allowed}" for c in self.controls if not c.passed)
            reasons.append(f"null controls failed ({bad})")
        if (self.max_wrong_among_commits is not None and self.block_wrong_among_commits is not None
                and self.block_wrong_among_commits > self.max_wrong_among_commits):
            reasons.append(f"block wrong among commits {self.block_wrong_among_commits:.3f} > "
                           f"{self.max_wrong_among_commits:.3f}")
        notes: list[str] = []
        test = self._challenger_test()
        if (test is None and self.challenger_test != "sign" and self._needs_comparison()
                and self._champion_outputs_missing()):
            k = sum(c is None for c in self.check_champion)
            msg = (f"no champion outputs for {k} of {self.n_check_items} check items: the champion / challenger "
                   f"test against {self.champion!r} cannot run")
            if self.allow_missing_champion:
                notes.append(f"{msg}; accepted without the comparison (allow_missing_champion=True)")
            else:
                reasons.append(f"{msg} (default deny; give champion= for every item, or set "
                               "allow_missing_champion=True)")
        if test is not None and test.refused:
            if test.method == "sign":
                reasons.append(f"worse than champion {self.champion!r} (sign test p {test.p_value:.4g} <= "
                               f"{test.level:g}; {test.worse_only} worse vs {test.better_only} better)")
            else:
                rule = " (re-calibration rule)" if test.rule == "recalibration" else ""
                reasons.append(f"worse than champion {self.champion!r} or not shown non-inferior{rule} (p "
                               f"{test.p_value:.4g} > {test.level:g}; {test.worse_only} worse incl. "
                               f"{test.n_unknown} unknown vs {test.better_only} better of {test.n}; margins "
                               f"{test.margin:g} / {test.margin_abs:g})")
        accepted = not reasons
        parent, champ_before, version = self.config_id, self.champion, self.version
        lam, n_chk = self.lambda_session, self.n_check_items
        n_bc, wac = self.n_block_commits, self.block_wrong_among_commits
        controls = tuple(self.controls)
        feasible = math.isfinite(lam) and lam <= self.score_max
        if accepted:
            self.config_id = self._new_config_id()
            self.champion, self.champion_trained_on = self.version, set(self.trained_on)
            self.accepted, self.rejected = True, False
        else:
            self.accepted, self.rejected = False, True
            can_roll_back = (champ_before is not None and version != champ_before and self.check_champion
                             and all(c is not None for c in self.check_champion))
            if can_roll_back:
                self.version, self.trained_on = champ_before, set(self.champion_trained_on)
                self.version_kind = "decoder"
                self._calibrate([c[0] for c in self.check_champion], [c[1] for c in self.check_champion])
                self.check_scores = [c[0] for c in self.check_champion]
                self.check_losses = [c[1] for c in self.check_champion]
                self.check_champion = [None] * len(self.check_ids)
                self.check_pairs = [None] * len(self.check_ids)
                self.accepted, self.rejected = self.unsafe, False  # safe: the champion needs its own null controls
        rec = UpdateRecord(len(self.updates), self.session, version, champ_before, accepted, tuple(reasons), parent,
                           self.config_id, self.version, lam, feasible, n_chk, n_bc, wac, controls, test,
                           None if self.commit_gate is None else self.commit_gate.to_dict(), self.unsafe,
                           tuple(notes))
        self.updates.append(rec)
        self._decide_hooks(rec)
        return rec

    def reject_proposal(self, reason: str) -> UpdateRecord:
        """Reject the current version without the checks (for example: its calibration failed).

        The champion comes back, but the session stays offer-only until a new check block. The
        decision is recorded like any other (:attr:`updates`, listeners, ledger).
        """
        if not reason:
            raise ValueError("give a reason")
        if self.ledger is not None and (self.open_update is None or not self.ledger.is_open_update(self.open_update)):
            self._propose("initial" if not self.updates else "rollback")
        version, champ_before = self.version, self.champion
        self._invalidate()
        self.rejected = True
        if champ_before is not None and version != champ_before:
            self.version, self.trained_on = champ_before, set(self.champion_trained_on)
            self.version_kind = "decoder"
        rec = UpdateRecord(len(self.updates), self.session, version, champ_before, False, (str(reason),),
                           self.config_id, self.config_id, self.version, math.inf, False, 0, 0, None, (), None,
                           None if self.commit_gate is None else self.commit_gate.to_dict(), self.unsafe)
        self.updates.append(rec)
        self._decide_hooks(rec)
        return rec

    def audit_records(self) -> list[dict[str, Any]]:
        """JSON-ready audit records of all update decisions (one per :meth:`finish_update`)."""
        return [u.to_dict() for u in self.updates]

    # --- online ------------------------------------------------------------------

    @property
    def can_commit(self) -> bool:
        """True if the loop is in commit mode (calibrated, feasible, accepted, no alarm)."""
        return (self.calibrated and math.isfinite(self.lambda_session) and self.lambda_session <= self.score_max
                and self.accepted and not self.monitor.alarmed)

    @property
    def threshold(self) -> float:
        return max(self.lambda_session, self.aci.threshold) if self.can_commit else math.inf

    def decide(self, score: float, text_ok: bool = True, *, text: str | None = None,
               guard_risk: float | None = None) -> GuardedDecision:
        """COMMIT iff in commit mode, ``score >= max(lambda_session, lambda_aci)`` and the gate passes.

        With the evidence gate (default), give ``guard_risk``; without it the item never commits.
        """
        if math.isnan(score):
            raise ValueError("score must not be nan (use -inf)")
        if not self.calibrated:
            return GuardedDecision(False, score, math.inf, self.version, "check-block")
        if self.monitor.alarmed:
            return GuardedDecision(False, score, math.inf, self.version, "alarm")
        if not (math.isfinite(self.lambda_session) and self.lambda_session <= self.score_max):
            return GuardedDecision(False, score, math.inf, self.version, "offer-only")
        if not self.accepted:
            return GuardedDecision(False, score, math.inf, self.version,
                                   "rejected" if self.rejected else "update-pending")
        gate_ok = self.gate_violation(text, guard_risk, text_ok, need_risk=True) is None
        eff = score if (gate_ok and score >= self.lambda_session) else -math.inf
        tk = self.aci.decide(eff)
        thr = max(self.lambda_session, tk.threshold)
        if tk.commit:
            reason = "commit"
        elif not gate_ok:
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
                "commit_gate": None if self.commit_gate is None else self.commit_gate.to_dict(),
                "evidence_gate": self.evidence_gate, "unsafe": self.unsafe,
                "null_max_commit_rate": self.alpha if self.null_max_commit_rate is None else self.null_max_commit_rate,
                "max_wrong_among_commits": self.max_wrong_among_commits,
                "n_updates": len(self.updates), "n_accepted": sum(u.accepted for u in self.updates),
                "n_rejected": sum(not u.accepted for u in self.updates), "config_id": self.config_id,
                "silent_errors": "not covered (observed losses only)"}
