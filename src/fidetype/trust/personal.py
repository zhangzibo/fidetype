"""Personalisation of the trust layer: per-user profiles, gated online re-calibration, drift detection (P5-01).

A guard calibrated for one person on one day goes stale: the signal drifts,
the decoder changes, the person changes. This module keeps one guard per
person up to date **without** a weaker guarantee. It reuses the existing
parts; it adds no new way to change a live guard.

- :class:`UserProfile` -- a versioned file per user. It holds a hashed user
  id (never the raw id), the guard (:meth:`TrustGuard.to_dict
  <fidetype.trust.dropin.TrustGuard.to_dict>`: configuration, input
  settings, guarantee sheet), calibration statistics (counts, rates,
  quantiles and a sample of reference **scores**), the history of
  ``config_id`` values with the reason for each change, the last drift-test
  summary, and ``consent_ref`` (a placeholder for the consent record of
  P5-04). It holds **no text and no signal**: :meth:`UserProfile.save`
  refuses a profile with a text-like key.
- :class:`PersonalTrust` -- the live controller for one user::

      from fidetype.trust.personal import PersonalTrust, UserProfile

      pt = PersonalTrust.from_calibration("user-17", cal_x, cal_y, salt=SECRET, null_inputs=nulls,
                                          profile_path="profiles/user-17.json")   # calibrate + profile
      r = pt.decide(x)                    # a TrustResult, as from TrustGuard.decide
      pt.feedback(r, truth)               # truth: what the user meant (None: no label)
      out = pt.maybe_recalibrate()        # None, or the GuardUpdateOutcome of a gated proposal

      pt = PersonalTrust.load("profiles/user-17.json", null_inputs=nulls)      # next session

How a change happens (the rules):

1. **Drift detection.** Each decision feeds ``p_top1`` to a
   :class:`~fidetype.trust.drift.ConformalDriftTest` (reference: the
   profile's reference scores). Each feedback feeds the observed loss
   (1 = a wrong commit the user corrected) to a
   :class:`~fidetype.trust.drift.RiskDriftTest` at the guard's ``alpha``.
   Both are anytime valid: ``P(any false alarm) <= level_scores +
   level_risk`` while the data match the calibration.
   **Guard-risk test (P5-10, opt-in ``guard_risk_test=True``).** A third
   :class:`~fidetype.trust.drift.ConformalDriftTest` watches the
   ``guard_risk`` of each decision (reference: the profile's
   ``reference_guard_risk``). On the T12 replay of P5-01 the guard risk
   drifts while ``p_top1`` does not, so only this test sees the change.
   Its default action is ``"propose"``. With it, ``P(any false alarm) <=
   level_scores + level_risk + level_guard_risk``. It is off by default,
   so the default behaviour and the default false-alarm budget do not
   change. ``spread=True`` adds the P5-09 spread bets to both score-type
   tests (``p_top1`` and guard risk).
2. **Tighten at once, loosen only through the gate.** A risk alarm
   (default action ``"tighten"``) sets the commit threshold to infinity
   (offer / withhold only). A higher threshold only removes commits, so this
   step needs no evidence. A score alarm (default action ``"propose"``)
   asks for a re-calibration and keeps the guard as it is.
3. **Gated re-calibration.** A proposal waits for ``n_recal + n_check`` new
   labelled items (labelled after the trigger). It then calls
   :meth:`TrustGuardUpdater.propose_calibration
   <fidetype.trust.update_hooks.TrustGuardUpdater.propose_calibration>`:
   :func:`~fidetype.trust.dropin.calibrate` (with its null controls) on the
   first ``n_recal`` items, then the loop checks of
   :class:`~fidetype.trust.adaptive.GuardedUpdateLoop` on the last
   ``n_check`` items (block LTT, evidence gate, uniform and shuffled null
   controls, champion / challenger sign test). Only an accepted update
   changes the guard (and removes a tightening). A rejected one changes
   nothing; the proposal stays open and needs new items.
4. Each change (calibration, alarm, tightening, accepted or rejected
   update) is a history entry in the profile. With a ledger on the loop,
   each proposal and decision is also a hash-chained ``update`` entry.

What this does not cover:

- The guarantee of the live guard is the guarantee of its sheet. It holds
  while the live data are exchangeable with the check block of the last
  accepted update. The drift tests watch this assumption; they do not prove
  it.
- **Silent errors** (a wrong commit that the user does not correct) have
  observed loss 0. The risk test does not see them.
- The re-calibration items come from the user's feedback (OFFER choices,
  corrections, retyped text). Wrong labels make a wrong check block.
- The initial reference scores come from the calibration items, and the
  guard's temperature was fitted on a part of them. Give held-out items as
  ``reference_inputs=`` for a cleaner reference.
- Not legal advice. ``consent_ref`` is only a reference; P5-04 defines the
  consent record.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Hashable, Mapping, Sequence

import numpy as np

from fidetype.trust.drift import ConformalDriftTest, DriftMonitor

__all__ = [
    "PROFILE_SCHEMA",
    "PersonalTrust",
    "UserProfile",
    "calibration_stats",
    "hash_user_id",
]

PROFILE_SCHEMA = "fidetype.user-profile/0.1"

#: Keys that would hold text or signal. A profile with one of them (at any depth) is refused.
_FORBIDDEN_KEYS = frozenset({"text", "texts", "truth", "truths", "choices", "top1", "label", "labels",
                             "signal", "samples", "raw", "inputs", "utterance", "utterances", "shown", "user_id"})
#: Parts of a guard dict that may hold the decoder's word list (configuration, not user data).
_GUARD_ALLOWED = frozenset({"lexicon", "vocab"})


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _norm(t: str | None) -> str:
    return " ".join((t or "").split()).lower()


def _jf(x: float) -> Any:
    return x if math.isfinite(x) else str(x)


def _fj(x: Any) -> float:
    return float(x) if not isinstance(x, str) else float(x.replace("Infinity", "inf"))


def hash_user_id(user_id: str, salt: bytes | str | None = None) -> str:
    """A pseudonymous id: ``"u:" + HMAC-SHA256(salt, user_id)`` (first 32 hex digits).

    Without a salt it is a plain SHA-256, which anyone can recompute from a guessed id. Use a secret salt
    that is not stored next to the profiles.
    """
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("user_id must be a non-empty string")
    if salt is None:
        h = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    else:
        key = salt.encode("utf-8") if isinstance(salt, str) else bytes(salt)
        h = hmac.new(key, user_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return "u:" + h[:32]


def _check_private(d: Any, path: str = "") -> None:
    """Raise if ``d`` holds a text-like key outside the guard's decoder configuration."""
    if isinstance(d, Mapping):
        for k, v in d.items():
            p = f"{path}.{k}" if path else str(k)
            if k in _FORBIDDEN_KEYS:
                raise ValueError(f"a profile must not hold text or signal (key {p!r})")
            if path.startswith("guard") and k in _GUARD_ALLOWED:
                continue
            _check_private(v, p)
    elif isinstance(d, (list, tuple)):
        for i, v in enumerate(d):
            _check_private(v, f"{path}[{i}]")


def calibration_stats(guard: Any, inputs: Sequence[Any], texts: Sequence[str] | None = None, *,
                      max_reference: int = 2000, seed: int = 0) -> dict[str, Any]:
    """Statistics of ``guard`` on ``inputs`` for a profile: counts, rates, quantiles, reference scores.

    No text is kept: ``texts`` only gives the top-1 right rate and the wrong-commit rate. The reference
    scores (``p_top1``, rounded to 1e-4) are a random sample of at most ``max_reference`` items.
    """
    rs = [guard._decide_quiet(x) for x in inputs]
    if not rs:
        raise ValueError("need at least one input")
    p = np.asarray([float(r.p_top1) for r in rs])
    risk = np.asarray([float(r.guard_risk) for r in rs])
    commit = np.asarray([r.action == "commit" for r in rs])
    out: dict[str, Any] = {
        "n_items": len(rs), "commit_rate": float(commit.mean()),
        "p_top1_quantiles": {str(q): float(np.quantile(p, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
        "p_top1_mean": float(p.mean()), "guard_risk_median": float(np.median(risk)),
    }
    if texts is not None:
        if len(texts) != len(rs):
            raise ValueError("texts needs one entry per input")
        right = np.asarray([bool(r.choices) and _norm(r.choices[0]) == _norm(t) for r, t in zip(rs, texts)])
        wrong_commit = commit & ~right
        out.update({"top1_right_rate": float(right.mean()), "wrong_commit_rate": float(wrong_commit.mean()),
                    "n_commits": int(commit.sum()), "n_wrong_commits": int(wrong_commit.sum())})
    idx = np.arange(len(p))
    if len(idx) > max_reference:
        idx = np.sort(np.random.default_rng(seed).choice(len(idx), size=max_reference, replace=False))
    out["reference_scores"] = [round(float(p[i]), 4) for i in idx]
    # P5-10: the same items' guard risk, for the opt-in guard-risk drift test (no text; non-finite -> 1.0).
    out["reference_guard_risk"] = [round(float(risk[i]), 4) if math.isfinite(risk[i]) else 1.0 for i in idx]
    return out


@dataclass
class UserProfile:
    """One user's trust profile (module docstring). Make it with :meth:`new`; read it with :meth:`load`."""

    user_hash: str
    guard: dict[str, Any] | None
    calibration: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    drift: dict[str, Any] | None = None
    #: Reference to the consent record (P5-04). Placeholder: stored as given, not checked.
    consent_ref: str | None = None
    profile_version: int = 0
    created_utc: str = field(default_factory=_now)
    updated_utc: str = field(default_factory=_now)
    schema: str = PROFILE_SCHEMA
    id_hash: str = "hmac-sha256"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, user_id: str, guard: Any = None, *, salt: bytes | str | None = None,
            calibration: Mapping[str, Any] | None = None, consent_ref: str | None = None,
            reason: str = "initial calibration") -> "UserProfile":
        """A new profile. ``guard``: a :class:`~fidetype.trust.dropin.TrustGuard` or its dict (or None)."""
        gd = guard.to_dict() if hasattr(guard, "to_dict") else (dict(guard) if guard is not None else None)
        p = cls(hash_user_id(user_id, salt), gd, dict(calibration or {}), consent_ref=consent_ref,
                id_hash="hmac-sha256" if salt is not None else "sha256")
        cid = p.config_id
        p.add_history("calibrate", config_id=cid, reason=reason)
        return p

    # --- content ------------------------------------------------------------

    @property
    def config_id(self) -> str | None:
        """The guard's ``config_id`` (None without a guard)."""
        if not self.guard:
            return None
        from fidetype.trust.frozen import FrozenTrustConfig

        return FrozenTrustConfig.from_dict(self.guard["config"]).config_id

    @property
    def config_ids(self) -> list[str]:
        """Every ``config_id`` the user's guard had, in order (no repeats in a row)."""
        out: list[str] = []
        for h in self.history:
            c = h.get("config_id")
            if c and (not out or out[-1] != c):
                out.append(c)
        return out

    @property
    def reference_scores(self) -> list[float]:
        return [_fj(x) for x in self.calibration.get("reference_scores", [])]

    @property
    def reference_guard_risk(self) -> list[float]:
        """Reference guard risks of the guard-risk drift test (P5-10). Empty in profiles made before P5-10."""
        return [_fj(x) for x in self.calibration.get("reference_guard_risk", [])]

    def add_history(self, event: str, **details: Any) -> dict[str, Any]:
        rec = {"time_utc": _now(), "event": str(event)}
        rec.update({k: v for k, v in details.items() if v is not None})
        _check_private(rec, "history")
        self.history.append(rec)
        self.profile_version += 1
        self.updated_utc = rec["time_utc"]
        return rec

    def set_guard(self, guard: Any, calibration: Mapping[str, Any] | None = None) -> None:
        self.guard = guard.to_dict() if hasattr(guard, "to_dict") else dict(guard)
        if calibration is not None:
            self.calibration = dict(calibration)
        self.profile_version += 1
        self.updated_utc = _now()

    def to_dict(self) -> dict[str, Any]:
        d = {"schema": self.schema, "user_hash": self.user_hash, "id_hash": self.id_hash,
             "profile_version": self.profile_version, "created_utc": self.created_utc,
             "updated_utc": self.updated_utc, "consent_ref": self.consent_ref, "guard": self.guard,
             "calibration": self.calibration, "history": self.history, "drift": self.drift, "extra": self.extra}
        _check_private(d)
        return d

    def content_sha256(self) -> str:
        """SHA-256 of the canonical JSON of the profile (for the provenance ledger)."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                                         allow_nan=False).encode("utf-8")).hexdigest()

    # --- files --------------------------------------------------------------

    def save(self, path: str | os.PathLike[str]) -> Path:
        """Write the profile as JSON (atomic replace). Refuses text-like keys."""
        p = Path(path)
        data = json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
            os.replace(tmp, p)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return p

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "UserProfile":
        if d.get("schema") != PROFILE_SCHEMA:
            raise ValueError(f"not a user profile (schema {d.get('schema')!r}, expected {PROFILE_SCHEMA!r})")
        _check_private(d)
        return cls(user_hash=d["user_hash"], guard=d.get("guard"), calibration=dict(d.get("calibration") or {}),
                   history=list(d.get("history") or []), drift=d.get("drift"), consent_ref=d.get("consent_ref"),
                   profile_version=int(d.get("profile_version", 0)), created_utc=d.get("created_utc", _now()),
                   updated_utc=d.get("updated_utc", _now()), id_hash=d.get("id_hash", "hmac-sha256"),
                   extra=dict(d.get("extra") or {}))

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "UserProfile":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def matches(self, user_id: str, salt: bytes | str | None = None) -> bool:
        """True if ``user_id`` (with the same salt) gives this profile's hash."""
        return hmac.compare_digest(self.user_hash, hash_user_id(user_id, salt))

    def load_guard(self, decode_fn: Any = None, *, audit_text: bool = True, grounding: Any = None) -> Any:
        """The live :class:`~fidetype.trust.dropin.TrustGuard` of this profile (same checks as ``load``)."""
        if not self.guard:
            raise ValueError("this profile has no guard")
        from fidetype.trust.dropin import load

        with tempfile.TemporaryDirectory() as td:
            gp = Path(td) / "guard.json"
            gp.write_text(json.dumps(self.guard, allow_nan=False), encoding="utf-8")
            return load(gp, decode_fn, audit_text=audit_text, grounding=grounding)


@dataclass
class _Pending:
    x: Any
    action: str
    text: str | None


class PersonalTrust:
    """Live trust controller for one user (module docstring).

    ``profile`` / ``guard``: the user's profile and its live guard (``profile.load_guard()``).
    ``updater``: a :class:`~fidetype.trust.update_hooks.TrustGuardUpdater` (default: a new one with a new
    :class:`~fidetype.trust.adaptive.GuardedUpdateLoop`; pass ``loop=`` to give a loop with a ledger).
    ``level_scores`` / ``level_risk``: false-alarm levels of the two drift tests.
    ``on_score_drift`` / ``on_risk_drift``: ``"propose"`` (ask for a gated re-calibration), ``"tighten"``
    (offer-only now, and propose) or ``"ignore"`` (record only).
    ``guard_risk_test``: also run the drift test on the guard risk (P5-10; default False). It needs
    ``profile.reference_guard_risk`` (profiles from :func:`calibration_stats` have it). ``level_guard_risk`` /
    ``on_guard_risk_drift``: its level and its action. ``spread``: the score-type tests also bet on a change
    of spread (P5-09; default False).
    ``n_recal`` / ``n_check``: labelled items for the candidate's calibration / the loop's check block
    (default ``n_check``: the loop's minimum). ``recalibrate_every``: also propose after this many new labels
    (None: only on drift). ``null_inputs``: your decoder's output on null input (needed for n-best input).
    ``calibrate_kwargs``: extra arguments of :func:`~fidetype.trust.dropin.calibrate` (``vocab``, ``lexicon``,
    ``decode_fn``, ...). ``profile_path``: save the profile after each change.
    """

    def __init__(self, profile: UserProfile, guard: Any, *, updater: Any = None, loop: Any = None,
                 level_scores: float = 0.005, level_risk: float = 0.005, jump: float = 0.01,
                 on_score_drift: str = "propose", on_risk_drift: str = "tighten", n_recal: int = 200,
                 n_check: int | None = None, recalibrate_every: int | None = None,
                 null_inputs: Sequence[Any] | None = None, calibrate_kwargs: Mapping[str, Any] | None = None,
                 null_trials: int = 100, profile_path: str | os.PathLike[str] | None = None,
                 max_buffer: int = 5000, seed: int = 0, guard_risk_test: bool = False,
                 level_guard_risk: float = 0.005, on_guard_risk_drift: str = "propose", spread: bool = False) -> None:
        from fidetype.trust.update_hooks import TrustGuardUpdater

        for name, v in (("on_score_drift", on_score_drift), ("on_risk_drift", on_risk_drift),
                        ("on_guard_risk_drift", on_guard_risk_drift)):
            if v not in ("propose", "tighten", "ignore"):
                raise ValueError(f"{name} must be 'propose', 'tighten' or 'ignore'")
        self.profile = profile
        self.guard = guard
        if updater is None:
            updater = TrustGuardUpdater(guard, loop, null_trials=null_trials, seed=seed)
        elif updater.guard is not guard:
            raise ValueError("updater.guard must be the live guard")
        self.updater = updater
        self.n_check = int(n_check if n_check is not None else updater.loop.n_check)
        if self.n_check < updater.loop.n_check:
            raise ValueError(f"n_check must be >= the loop's n_check ({updater.loop.n_check})")
        if n_recal < 1:
            raise ValueError("n_recal must be >= 1")
        self.n_recal = int(n_recal)
        self.recalibrate_every = recalibrate_every
        self.on_score_drift, self.on_risk_drift = on_score_drift, on_risk_drift
        self.on_guard_risk_drift = on_guard_risk_drift
        self.null_inputs = None if null_inputs is None else list(null_inputs)
        self.calibrate_kwargs = dict(calibrate_kwargs or {})
        self.profile_path = None if profile_path is None else Path(profile_path)
        self.max_buffer = int(max_buffer)
        ref = profile.reference_scores
        self.monitor = DriftMonitor(reference_scores=ref or None, alpha=guard.alpha, level_scores=level_scores,
                                    level_risk=level_risk, jump=jump, seed=seed, spread=spread)
        #: The opt-in guard-risk drift test (P5-10), or None.
        self.guard_risk_test: ConformalDriftTest | None = None
        if guard_risk_test:
            gref = profile.reference_guard_risk
            if not gref:
                raise ValueError("guard_risk_test=True needs reference guard risks in the profile "
                                 "(calibration['reference_guard_risk'], from calibration_stats)")
            self.guard_risk_test = ConformalDriftTest(gref, level=level_guard_risk, jump=jump, seed=seed,
                                                      spread=spread)
            self.guard_risk_test.name = "guard_risk"
        self._pending: dict[int, _Pending] = {}
        self._buffer: list[tuple[Any, str]] = []
        self._labels_since = 0
        self.proposal_reason: str | None = None
        self.tightened = False
        self.n_proposals = 0
        self.outcomes: list[Any] = []
        self._alarm_seen = {"scores": False, "risk": False, "guard_risk": False}

    # --- construction -----------------------------------------------------------

    @classmethod
    def from_calibration(cls, user_id: str, inputs: Sequence[Any], texts: Sequence[str], *,
                         salt: bytes | str | None = None, consent_ref: str | None = None,
                         reference_inputs: Sequence[Any] | None = None, alpha: float = 0.05, delta: float = 0.1,
                         calibrate_kwargs: Mapping[str, Any] | None = None, null_inputs: Sequence[Any] | None = None,
                         **kwargs: Any) -> "PersonalTrust":
        """Calibrate a guard (:func:`~fidetype.trust.dropin.calibrate`), make the profile, return the controller."""
        from fidetype.trust.dropin import calibrate

        ck = dict(calibrate_kwargs or {})
        guard = calibrate(inputs, texts, alpha=alpha, delta=delta, null_inputs=null_inputs, **ck)
        stats = calibration_stats(guard, reference_inputs if reference_inputs is not None else inputs,
                                  None if reference_inputs is not None else texts)
        prof = UserProfile.new(user_id, guard, salt=salt, calibration=stats, consent_ref=consent_ref)
        pt = cls(prof, guard, null_inputs=null_inputs, calibrate_kwargs=ck, **kwargs)
        pt._save()
        return pt

    @classmethod
    def load(cls, path: str | os.PathLike[str], decode_fn: Any = None, *, grounding: Any = None,
             **kwargs: Any) -> "PersonalTrust":
        """Open a saved profile and its guard. New drift tests start (each session has its own level)."""
        prof = UserProfile.load(path)
        guard = prof.load_guard(decode_fn, grounding=grounding)
        kwargs.setdefault("profile_path", path)
        ck = dict(kwargs.pop("calibrate_kwargs", None) or {})
        if decode_fn is not None:
            ck.setdefault("decode_fn", decode_fn)
        return cls(prof, guard, calibrate_kwargs=ck, **kwargs)

    # --- live -------------------------------------------------------------------

    def decide(self, x: Any, *, utterance_id: str | None = None) -> Any:
        """:meth:`TrustGuard.decide <fidetype.trust.dropin.TrustGuard.decide>` plus the score drift test."""
        r = self.guard.decide(x, utterance_id=utterance_id)
        self._pending[r.seq] = _Pending(x, r.action, r.text)
        if len(self._pending) > self.max_buffer:
            self._pending.pop(next(iter(self._pending)))
        st = self.monitor.update_score(float(r.p_top1) if math.isfinite(r.p_top1) else -math.inf)
        if st is not None and st.alarmed and not self._alarm_seen["scores"]:
            self._alarm_seen["scores"] = True
            self._on_alarm("scores", self.on_score_drift)
        if self.guard_risk_test is not None:
            gr = float(r.guard_risk)
            gst = self.guard_risk_test.update(gr if not math.isnan(gr) else math.inf)
            if gst.alarmed and not self._alarm_seen["guard_risk"]:
                self._alarm_seen["guard_risk"] = True
                self._on_alarm("guard_risk", self.on_guard_risk_drift)
        return r

    __call__ = decide

    def feedback(self, result: Any, truth: str | None) -> float:
        """Report what the user meant for ``result`` (None: no label). Returns the observed loss.

        COMMIT: loss 1 if ``truth`` differs from the committed text, else 0 (``truth=None``: the user did not
        correct it, loss 0 -- a silent error if it was wrong). OFFER / withhold: loss 0. A given ``truth``
        becomes a re-calibration label (kept in memory only, never in the profile).
        """
        pend = self._pending.pop(result.seq, None)
        loss = 0.0
        if result.action == "commit" and truth is not None:
            loss = float(_norm(result.text) != _norm(truth))
        st = self.monitor.update_loss(loss)
        if truth is not None and pend is not None:
            self._buffer.append((pend.x, str(truth)))
            if len(self._buffer) > self.max_buffer:
                self._buffer.pop(0)
            self._labels_since += 1
            if (self.recalibrate_every and self.proposal_reason is None
                    and self._labels_since >= self.recalibrate_every):
                self._open_proposal(f"scheduled after {self._labels_since} labels", clear=False)
        if st is not None and st.alarmed and not self._alarm_seen["risk"]:
            self._alarm_seen["risk"] = True
            self._on_alarm("risk", self.on_risk_drift)
        return loss

    def _on_alarm(self, which: str, action: str) -> None:
        test = {"scores": self.monitor.scores, "risk": self.monitor.risk,
                "guard_risk": self.guard_risk_test}[which]
        self.profile.add_history("drift_alarm", test=which, config_id=self.guard.config_id, action=action,
                                 n=test.n, e_value=_jf(test.e_value), level=test.level)
        if action == "tighten":
            self.tighten(f"{which} drift alarm")
        if action in ("tighten", "propose"):
            self._open_proposal(f"{which} drift alarm")
        self.profile.drift = self.drift_summary()
        self._save()

    def _open_proposal(self, reason: str, clear: bool = True) -> None:
        if self.proposal_reason is None:
            self.proposal_reason = reason
            if clear:  # use only items labelled after the trigger
                self._buffer.clear()

    def tighten(self, reason: str) -> None:
        """Offer / withhold only from now on (commit threshold infinity). No evidence needed: it only removes
        commits. An accepted re-calibration ends it."""
        from fidetype.trust.update_hooks import swap_guard

        if self.tightened:
            return
        before = self.guard.config_id
        new = self.updater._raised(self.guard, math.inf)
        swap_guard(self.guard, new, note={"reason": f"tighten: {reason}"})
        self.tightened = True
        self.profile.set_guard(self.guard)
        self.profile.add_history("tighten", from_config_id=before, config_id=self.guard.config_id, reason=reason)
        self._save()

    @property
    def n_labels(self) -> int:
        """Re-calibration labels in memory (since the trigger)."""
        return len(self._buffer)

    @property
    def labels_needed(self) -> int:
        return self.n_recal + self.n_check

    def maybe_recalibrate(self, *, session: Hashable | None = None) -> Any:
        """Run a gated re-calibration if one is asked for and enough new labels exist. Else None.

        Returns the :class:`~fidetype.trust.update_hooks.GuardUpdateOutcome`.
        """
        if self.proposal_reason is None or len(self._buffer) < self.labels_needed:
            return None
        items = self._buffer[-self.labels_needed:]
        cal, chk = items[: self.n_recal], items[self.n_recal:]
        k = self.n_proposals
        self.n_proposals += 1
        cal_ids = [("recal", k, "cal", i) for i in range(len(cal))]
        chk_ids = [("recal", k, "check", i) for i in range(len(chk))]
        before = self.guard.config_id
        reason = self.proposal_reason
        out = self.updater.propose_calibration(
            [x for x, _ in cal], [t for _, t in cal], [x for x, _ in chk], [t for _, t in chk],
            check_ids=chk_ids, cal_ids=cal_ids, version=f"recal-{k}-{before}", session=session,
            null_inputs=self.null_inputs, **self.calibrate_kwargs)
        self.outcomes.append(out)
        self._buffer.clear()
        self._labels_since = 0
        rec = out.record
        ucid = None if rec is None else rec.config_id
        if out.accepted:
            self.tightened = False
            stats = calibration_stats(self.guard, [x for x, _ in chk], [t for _, t in chk])
            stats["source"] = "check block of the accepted update"
            self.profile.set_guard(self.guard, stats)
            self.profile.add_history("recalibrate_accepted", from_config_id=before, config_id=self.guard.config_id,
                                     update_config_id=ucid, reason=reason, n_recal=len(cal), n_check=len(chk))
            self.monitor.reset(stats["reference_scores"])
            if self.guard_risk_test is not None:
                self.guard_risk_test.reset(stats["reference_guard_risk"])
            self._alarm_seen = {"scores": False, "risk": False, "guard_risk": False}
            self.proposal_reason = None
        else:
            self.profile.add_history("recalibrate_rejected", config_id=self.guard.config_id, update_config_id=ucid,
                                     reason=reason, reasons=list(out.reasons))
        self.profile.drift = self.drift_summary()
        self._save()
        return out

    def drift_summary(self) -> dict[str, Any]:
        """The drift-test summary of the profile. The ``guard_risk`` key exists only with ``guard_risk_test``."""
        d = self.monitor.summary()
        if self.guard_risk_test is not None:
            d["guard_risk"] = self.guard_risk_test.state_summary()
            d["level_total"] = d["level_total"] + self.guard_risk_test.level
        return d

    def _save(self) -> None:
        if self.profile_path is not None:
            self.profile.save(self.profile_path)

    def report(self) -> dict[str, Any]:
        return {"user_hash": self.profile.user_hash, "config_id": self.guard.config_id,
                "tightened": self.tightened, "proposal_open": self.proposal_reason,
                "labels": len(self._buffer), "labels_needed": self.labels_needed,
                "n_proposals": self.n_proposals, "n_accepted": sum(o.accepted for o in self.outcomes),
                "drift": self.drift_summary(), "profile_version": self.profile.profile_version}
