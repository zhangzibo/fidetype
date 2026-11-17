"""Hooks that put the drop-in guard and the online policy behind the gated update loop (P15-02).

A decoder update must not change what the user sees until it passed the
checks of :class:`~fidetype.trust.adaptive.GuardedUpdateLoop` (block LTT
on a fresh check block, uniform and shuffled null controls through the
commit gate, champion / challenger sign test). This module connects the
loop to the two live objects of the trust layer:

- :class:`TrustGuardUpdater` -- for a :class:`~fidetype.trust.dropin.TrustGuard`
  (P14-03). Give it a candidate guard (calibrated for the new decoder) and
  a check block that neither decoder trained on. It runs the loop. An
  accepted update swaps the candidate configuration into the **same**
  guard object, with ``commit_p`` raised to the loop's session threshold
  if that is higher (a higher threshold only removes commits). A rejected
  update leaves the guard unchanged (same object, same ``config_id``).
- :class:`OnlinePolicyUpdater` -- for an
  :class:`~fidetype.trust.online_risk.OnlineTrustPolicy`. On an accepted
  update it swaps in the policy of the new version and sets
  ``commit_floor`` to the session threshold. The ACI controller keeps its
  state across updates. A rejected update changes nothing.

::

    from fidetype.trust import calibrate, ProvenanceLedger
    from fidetype.trust.adaptive import GuardedUpdateLoop
    from fidetype.trust.update_hooks import TrustGuardUpdater

    guard = calibrate(cal_x, cal_y, vocab=VOCAB, lexicon=WORDS)            # live guard, decoder v1
    loop = GuardedUpdateLoop(alpha=guard.alpha, delta=guard.delta, ledger=ProvenanceLedger("updates.jsonl"))
    up = TrustGuardUpdater(guard, loop)
    out = up.propose_calibration(new_cal_x, new_cal_y, check_x_v2, check_y,     # decoder v2
                                 champion_inputs=check_x_v1, version="v2", vocab=VOCAB, lexicon=WORDS)
    out.accepted, guard.config_id            # same guard object; new config only if accepted

Every proposal and decision is an ``update`` entry in the ledger (if the
loop has one): see :meth:`fidetype.trust.provenance.ProvenanceLedger.record_update`.

What this does not cover: the check block must be exchangeable with the
live data and unseen by both decoders (the loop checks ids, not
content); the null controls are a refusal rule, not a bound; silent
errors are not covered (see :mod:`fidetype.trust.adaptive`). A raised
``commit_p`` keeps the wrong-commit bound of the candidate's sheet, but a
precision bound (P5-02) that was certified at the old threshold is not
re-certified: the sheet then carries a warning.
"""

from __future__ import annotations

import datetime as _dt
import inspect
import math
from dataclasses import dataclass, replace
from typing import Any, Callable, Hashable, Iterable, Mapping, Sequence

import numpy as np

from fidetype.trust.adaptive import GuardedUpdateLoop, UpdateRecord

__all__ = [
    "GuardUpdateOutcome",
    "OnlinePolicyUpdater",
    "TrustGuardUpdater",
    "swap_guard",
]


def _norm(t: str | None) -> str:
    return " ".join((t or "").split())


def _commit_p(guard: Any) -> float:
    return float(guard.config.policy.get("commit_p", math.inf))


def swap_guard(live: Any, new: Any, *, note: Mapping[str, Any] | None = None) -> None:
    """Put the configuration of guard ``new`` into the guard object ``live``.

    The audit log and the decision counter of ``live`` stay; a ``config_update`` record goes into its
    audit log. Callers that hold ``live`` see the new configuration at once. Use it only for an update
    that passed the checks (:class:`TrustGuardUpdater` does this).
    """
    from fidetype.trust.dropin import TrustGuard

    if not isinstance(live, TrustGuard) or not isinstance(new, TrustGuard):
        raise TypeError("swap_guard needs two TrustGuard objects")
    if live.input_kind != new.input_kind:
        raise ValueError(f"input kind differs ({live.input_kind} vs {new.input_kind})")
    before = live.config_id
    log, seq, audit_text = live.audit_log, live._seq, live.audit_text
    # Re-run __init__ on the live object, so that closures (frame capture for the grounding gate) bind to it.
    params = inspect.signature(TrustGuard.__init__).parameters
    kw = {k: getattr(new, k) for k in ("halluc_gate", "grounding") if k in params}
    old_state = dict(live.__dict__)
    try:
        TrustGuard.__init__(live, new.config, new._codec, new.sheet, new._user_decode, audit_text, **kw)
    except Exception:
        live.__dict__.clear()
        live.__dict__.update(old_state)
        raise
    for k, v in new.__dict__.items():  # attributes that __init__ does not set (for example per-item stats)
        if k not in live.__dict__:
            live.__dict__[k] = v
    for k in ("halluc_items", "precision_items"):
        if k in new.__dict__:
            live.__dict__[k] = new.__dict__[k]
    live.audit_log, live._seq = log, seq
    rec: dict[str, Any] = {"type": "config_update",
                           "time_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds"),
                           "from_config_id": before, "to_config_id": live.config_id, "seq_next": seq}
    rec.update(dict(note or {}))
    live.audit_log.append(rec)


@dataclass(frozen=True)
class GuardUpdateOutcome:
    """The result of one :meth:`TrustGuardUpdater.propose`."""

    accepted: bool
    #: The loop's record (None if the proposal never reached the loop checks: see ``reasons``).
    record: UpdateRecord | None
    config_id_before: str
    config_id_after: str
    commit_p_before: float
    commit_p_after: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        def f(x: float) -> Any:
            return x if math.isfinite(x) else str(x)

        return {"accepted": self.accepted, "config_id_before": self.config_id_before,
                "config_id_after": self.config_id_after, "commit_p_before": f(self.commit_p_before),
                "commit_p_after": f(self.commit_p_after), "reasons": list(self.reasons),
                "record": None if self.record is None else self.record.to_dict()}


class TrustGuardUpdater:
    """Gate every configuration change of a :class:`~fidetype.trust.dropin.TrustGuard` with the update loop.

    ``loop``: a :class:`GuardedUpdateLoop` (default: a new one with the guard's alpha and delta). Its
    champion is the live guard (version name: its ``config_id``, unless ``champion_version`` is given).
    ``null_trials``: inputs per null control (uniform and shuffled, made from the check block like
    :func:`~fidetype.trust.dropin.calibrate` does). ``raise_threshold``: on accept, set ``commit_p`` to
    ``max(candidate commit_p, loop session threshold)``.
    """

    hook_name = "trust_guard"

    def __init__(self, guard: Any, loop: GuardedUpdateLoop | None = None, *, null_trials: int = 100,
                 seed: int = 0, raise_threshold: bool = True, champion_version: Hashable | None = None) -> None:
        self.guard = guard
        self.loop = loop if loop is not None else GuardedUpdateLoop(alpha=guard.alpha, delta=guard.delta)
        if null_trials < 1:
            raise ValueError("null_trials must be >= 1")
        self.null_trials = int(null_trials)
        self.rng = np.random.default_rng(seed)
        self.raise_threshold = bool(raise_threshold)
        if self.loop.champion is None:
            self.loop.set_champion(champion_version if champion_version is not None else guard.config_id)
        self._pending: tuple[Hashable, Any] | None = None
        self.outcomes: list[GuardUpdateOutcome] = []
        self.loop.add_listener(self._on_update)

    # --- loop listener ----------------------------------------------------------

    def _on_update(self, rec: UpdateRecord, loop: GuardedUpdateLoop) -> dict[str, Any] | None:
        pend, self._pending = self._pending, None
        if pend is None or rec.version != pend[0]:
            return None  # not one of our proposals (for example a champion re-check)
        if not rec.accepted:
            return {"guard_swapped": False, "guard_config_id": self.guard.config_id}
        before = self.guard.config_id
        new = pend[1]
        swap_guard(self.guard, new, note={"update_config_id": rec.config_id, "version": repr(rec.version)})
        return {"guard_swapped": True, "guard_config_before": before, "guard_config_after": self.guard.config_id,
                "commit_p": _commit_p(self.guard)}

    # --- inputs ---------------------------------------------------------------

    def _item(self, g: Any, x: Any, input_scale: str | None = None) -> tuple[float, str, float, str]:
        """(loop score, top-1 text, guard risk, action) of guard ``g`` on input ``x`` (not logged)."""
        r = g._decide_quiet(x, input_scale)
        top1 = _norm(r.choices[0]) if r.choices else ""
        score = float(r.p_top1) if r.action == "commit" else -math.inf
        return score, top1, float(r.guard_risk), r.action

    def _null_items(self, g: Any, inputs: Sequence[Any], null_inputs: Sequence[Any] | None
                    ) -> tuple[list, list, list]:
        """Null-control outputs of guard ``g`` as (score, text, guard_risk) for the loop."""
        rng = self.rng
        idx = rng.integers(0, len(inputs), size=self.null_trials)

        def out(xs: Iterable[Any], scale: str | None = None) -> list:
            res = []
            for x in xs:
                s, t, risk, _ = self._item(g, x, scale)
                res.append((s, t if t else False, risk))
            return res

        user: list = []
        if g.input_kind == "logits":
            from fidetype.adapters.ctc_logits import to_log_probs

            V = len(g._codec.vocab)
            scale = g._codec.input_scale

            def uniform(x: Any) -> np.ndarray:
                T = to_log_probs(x, scale).shape[0]
                return np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V))

            def shuffled(x: Any) -> np.ndarray:
                lp = to_log_probs(x, scale)
                return lp[rng.permutation(lp.shape[0])]

            uni = out((uniform(inputs[i]) for i in idx), "logits")
            shu = out((shuffled(inputs[i]) for i in idx), "log_probs")
            if null_inputs:
                user = out(null_inputs)
        else:
            from fidetype.adapters.text_nbest import normalise_item
            from fidetype.trust.dropin import _nbest_items

            def items(x: Any) -> list[dict[str, Any]]:
                return [normalise_item(it) for it in _nbest_items(x)]

            def flat(x: Any) -> list[dict[str, Any]]:
                return [{"text": it["text"], "score": 0.0} for it in items(x)]

            uni = out(flat(inputs[i]) for i in idx)
            # n-best lists hold no frames to shuffle: the caller's null inputs are the second control
            if not null_inputs:
                raise ValueError("n-best input: give null_inputs= (your decoder's output on null input); "
                                 "it is the second null control of every update")
            shu = out(null_inputs)
        return uni, shu, user

    # --- proposals ----------------------------------------------------------------

    def _outcome(self, accepted: bool, rec: UpdateRecord | None, before: str, cp_before: float,
                 reasons: Sequence[str]) -> GuardUpdateOutcome:
        o = GuardUpdateOutcome(accepted, rec, before, self.guard.config_id, cp_before, _commit_p(self.guard),
                               tuple(reasons))
        self.outcomes.append(o)
        return o

    def propose(self, candidate: Any, check_inputs: Sequence[Any], check_texts: Sequence[str], *,
                champion_inputs: Sequence[Any] | None = None, check_ids: Sequence[Hashable] | None = None,
                trained_on: Iterable[Hashable] = (), version: Hashable | None = None,
                session: Hashable | None = None, null_inputs: Sequence[Any] | None = None) -> GuardUpdateOutcome:
        """Run the loop checks for ``candidate`` (a calibrated guard of the new decoder).

        ``check_inputs``: the new decoder's outputs on the check block; ``champion_inputs``: the live
        decoder's outputs on the same items (None: the same inputs, for a re-calibration of the same
        decoder). ``check_texts``: the true texts. ``check_ids`` / ``trained_on``: item ids, so that the
        loop refuses a check item the candidate trained on. ``session``: a new session id starts a new
        loop session. ``null_inputs``: your decoder's output on null input (logits: an extra control;
        n-best: the shuffled control).
        """
        from fidetype.trust.dropin import TrustGuard

        if not isinstance(candidate, TrustGuard):
            raise TypeError("candidate must be a TrustGuard (make it with calibrate())")
        if candidate.input_kind != self.guard.input_kind:
            raise ValueError(f"candidate input kind {candidate.input_kind} != live {self.guard.input_kind}")
        n = len(check_inputs)
        if len(check_texts) != n or (champion_inputs is not None and len(champion_inputs) != n):
            raise ValueError("check_inputs, check_texts and champion_inputs need the same length")
        if n < self.loop.n_check:
            raise ValueError(f"check block has {n} items; the loop needs >= {self.loop.n_check}")
        ids = list(check_ids) if check_ids is not None else [("check", len(self.outcomes), i) for i in range(n)]
        if len(ids) != n:
            raise ValueError("check_ids needs one id per check item")
        loop = self.loop
        if version is None:
            version = candidate.config_id
        if version == loop.champion:
            raise ValueError(f"version {version!r} is the live champion")
        before, cp_before = self.guard.config_id, _commit_p(self.guard)
        if session is not None and session != loop.session:
            loop.start_session(session)
        loop.new_version(version, trained_on)
        champ_x = check_inputs if champion_inputs is None else champion_inputs
        for i in range(n):
            s, t, risk, _ = self._item(candidate, check_inputs[i])
            cs, ct, crisk, _ = self._item(self.guard, champ_x[i])
            truth = _norm(check_texts[i])
            loop.add_check_item(ids[i], s, float(t != truth), text=t or None, text_ok=bool(t), guard_risk=risk,
                                champion=(cs, float(ct != truth), crisk, ct))
        loop.recalibrate()
        uni, shu, user = self._null_items(candidate, check_inputs, null_inputs)
        loop.check_null_controls(uniform=uni, shuffled=shu, user=user)
        new = candidate
        lam = loop.lambda_session
        if self.raise_threshold and lam > _commit_p(candidate):  # inf (infeasible block): never commit
            new = self._raised(candidate, lam)
        self._pending = (version, new)
        try:
            rec = loop.finish_update()
        finally:
            self._pending = None
        return self._outcome(rec.accepted, rec, before, cp_before, rec.reasons)

    def propose_calibration(self, cal_inputs: Sequence[Any], cal_texts: Sequence[str],
                            check_inputs: Sequence[Any], check_texts: Sequence[str], *,
                            champion_inputs: Sequence[Any] | None = None,
                            check_ids: Sequence[Hashable] | None = None,
                            cal_ids: Iterable[Hashable] = (), version: Hashable | None = None,
                            session: Hashable | None = None, null_inputs: Sequence[Any] | None = None,
                            **calibrate_kwargs: Any) -> GuardUpdateOutcome:
        """:func:`~fidetype.trust.dropin.calibrate` a candidate, then :meth:`propose` it.

        If the calibration refuses (:class:`~fidetype.trust.dropin.NullControlError`, or any
        ``ValueError``), the proposal is recorded as rejected and the guard stays unchanged.
        ``cal_ids``: ids of the calibration items (the candidate trained on them).
        """
        from fidetype.trust.dropin import NullControlError, calibrate

        cal_ids = list(cal_ids)
        try:
            cand = calibrate(cal_inputs, cal_texts, alpha=self.guard.alpha, delta=self.guard.delta,
                             input_kind=self.guard.input_kind, null_inputs=null_inputs, **calibrate_kwargs)
        except (NullControlError, ValueError) as e:
            before, cp = self.guard.config_id, _commit_p(self.guard)
            loop = self.loop
            if session is not None and session != loop.session:
                loop.start_session(session)
            v = version if version is not None else f"candidate-{len(self.outcomes)}"
            loop.new_version(v, cal_ids)
            rec = loop.reject_proposal(f"calibration refused: {type(e).__name__}: {e}")
            return self._outcome(False, rec, before, cp, rec.reasons)
        return self.propose(cand, check_inputs, check_texts, champion_inputs=champion_inputs, check_ids=check_ids,
                            trained_on=cal_ids, version=version, session=session, null_inputs=null_inputs)

    def _raised(self, candidate: Any, lam: float) -> Any:
        """A copy of ``candidate`` with ``commit_p = lam`` (only removes commits) and an updated sheet."""
        from fidetype.trust.dropin import TrustGuard

        cfg = candidate.config.with_policy(commit_p=float(lam))
        sheet = candidate.sheet
        if sheet is not None:
            warn = (f"commit threshold raised from {_commit_p(candidate):g} to {lam:g} by the update loop "
                    "(P15-02 session threshold; only removes commits)")
            if getattr(sheet, "precision", None):
                warn += "; the precision bound was certified at the old threshold and is not re-certified"
            sheet = replace(sheet, config_id=cfg.config_id, commit_threshold=float(lam),
                            warnings=tuple(sheet.warnings) + (warn,))
        params = inspect.signature(TrustGuard.__init__).parameters
        kw = {k: getattr(candidate, k) for k in ("halluc_gate", "grounding") if k in params}
        return TrustGuard(cfg, candidate._codec, sheet, candidate._user_decode, candidate.audit_text, **kw)


class OnlinePolicyUpdater:
    """Swap the policy of an :class:`~fidetype.trust.online_risk.OnlineTrustPolicy` only on an accepted update.

    ``policies``: the decision policy of each version, as a mapping or a function ``version -> policy``
    (None, or a missing version: keep the current policy and only set the floor). ``use_floor``: set
    ``commit_floor`` to the loop's session threshold on accept. The ACI controller keeps its state.
    """

    hook_name = "online_policy"

    def __init__(self, online_policy: Any, loop: GuardedUpdateLoop,
                 policies: Mapping[Hashable, Any] | Callable[[Hashable], Any] | None = None, *,
                 use_floor: bool = True) -> None:
        self.online_policy = online_policy
        self.loop = loop
        self.policies = policies
        self.use_floor = bool(use_floor)
        loop.add_listener(self._on_update)

    def _policy_for(self, version: Hashable) -> Any:
        if self.policies is None:
            return None
        if callable(self.policies) and not isinstance(self.policies, Mapping):
            return self.policies(version)
        return self.policies.get(version)

    def _on_update(self, rec: UpdateRecord, loop: GuardedUpdateLoop) -> dict[str, Any]:
        op = self.online_policy
        if not rec.accepted:
            return {"policy_swapped": False, "commit_floor": _jf(op.commit_floor)}
        pol = self._policy_for(rec.active_version)
        floor = float(loop.lambda_session) if self.use_floor else None
        op.swap_policy(pol if pol is not None else op.policy, commit_floor=floor, config_id=rec.config_id)
        return {"policy_swapped": pol is not None, "commit_floor": _jf(op.commit_floor)}


def _jf(x: float) -> Any:
    return x if math.isfinite(x) else str(x)
