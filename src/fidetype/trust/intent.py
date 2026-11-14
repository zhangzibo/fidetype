"""Trust core module i: discrete intent and control events (FEP-0003, P12-01 / P12-02).

The text trust layer decides once per utterance: COMMIT, OFFER, ASK or
ABSTAIN. This module does the same for **discrete intents**: select,
confirm, cancel, undo, a menu choice among N options, a mode switch, or a
device command such as "call caregiver".

Parts
-----
:class:`IntentVocabulary`
    The intent vocabulary declaration (header field ``intent_declaration``,
    FEP-0003 section 2). Each intent has an id, a **risk class**
    (``safe`` < ``undoable`` < ``irreversible``) and a role (``action``,
    ``null``, ``confirm``, ``cancel`` or ``undo``).
:class:`IntentTrustConfig`
    A frozen, content-addressed configuration (``icfg-...``): the frame
    temperature, one COMMIT threshold per risk class, the OFFER rule and
    the gates. :func:`fit_intent_config` fits it with the risk-control
    machinery of :mod:`fidetype.trust.risk_control` (LTT or CRC).
:class:`IntentPolicy`
    The stateless rule: candidate probabilities -> COMMIT / OFFER / ABSTAIN.
:class:`IntentTrustLayer`
    The stateful stream layer: it reads ``intent`` events (FEP-0003
    section 3), v0.1 ``decision`` events and command-vocabulary frames,
    runs the policy, handles the confirmation path, undo and
    ``intent_feedback``, and writes ``trust_decision`` events with
    ``profile = "intent"`` (FEP-0003 section 5).

Per-class risk control
----------------------
For risk class r and calibration item i with calibrated top-1
probability ``p_i``, top-1 intent ``k_i`` and true intent ``y_i``::

    L_i^r(lambda) = 1[ class(k_i) = r  and  gate passes  and  p_i >= lambda  and  k_i != y_i ]

``L^r`` is non-increasing in lambda, so :func:`~fidetype.trust.risk_control.ltt_threshold`
and :func:`~fidetype.trust.risk_control.crc_threshold` apply unchanged
(score ``p_i`` if ``class(k_i) = r`` and the gate passes, else ``-inf``;
commit loss ``1[k_i != y_i]``; fallback loss 0). The guarantee is per
decision unit: the rate of **wrong COMMITs of class r** (for
``irreversible``: wrong *armed* intents, see below) is at most
``alpha_r`` (CRC: in expectation; LTT: with probability ``1 - delta_r``).
LTT splits ``delta`` over the classes (Bonferroni), so all class bounds
hold together with probability ``1 - delta``.

A truth of "no intent" (a rest trial, a no-signal trial) has
``y_i = -1`` or the index of a ``null`` intent: every COMMIT on it is
wrong.

Safety rules (FEP-0003 section 6)
---------------------------------
- **Never COMMIT a null intent.** An intent with role ``null`` (rest, no
  intent) is never committed. This is the M2-18 content-gate idea: a
  "nothing" output must not look like an action.
- **No COMMIT without probability semantics.** Scores with
  ``score_semantics`` ``none``, ``power`` or ``strength`` cannot be
  calibrated. The layer can OFFER them, never COMMIT them.
- **No COMMIT on low signal quality** (``min_signal_quality``) and,
  optionally, on a near-uniform distribution (``max_norm_entropy``).
- **Irreversible intents need confirmation.** If the top-1 intent is
  irreversible and passes its (strict) threshold, the layer **arms** it:
  a final OFFER with ``confirm_required = true``. It is executed only by
  a later COMMIT with ``confirmation_of`` = the unit of that OFFER: a
  ``confirm`` intent that passes the irreversible threshold, or an
  explicit ``intent_feedback`` (outcome ``confirmed`` / ``selected``)
  from another channel (a switch, a touch screen, a caregiver).
  Confirmation only removes executions, so the wrong-execution rate is
  at most the wrong-arm rate, which risk control bounds.
- The gates only remove COMMITs. For one item the loss can only go down,
  so a fitted bound still holds with the gates on.

Undo
----
A COMMIT of an ``undo`` intent reverses the latest committed ``undoable``
(or ``safe``) action of the session within ``undo_window_units`` units
(and ``undo_window_s`` seconds of signal time, if the events carry
``t``). It carries ``undo_of``. Irreversible actions cannot be undone.
An undo is also a (noisy) user label: the layer counts it in the session
statistics.

Synthetic simulator: :mod:`fidetype.trust.intent_sim`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence

import numpy as np

from fidetype.trust.calibration import TemperatureScaler
from fidetype.trust.risk_control import DEFAULT_LTT_GRID, crc_threshold, ltt_threshold

#: Risk classes, from the least to the most strict.
RISK_CLASSES: tuple[str, ...] = ("safe", "undoable", "irreversible")
#: Roles of an intent.
ROLES: tuple[str, ...] = ("action", "null", "confirm", "cancel", "undo")
#: Roles of which a vocabulary has at most one intent.
UNIQUE_ROLES: tuple[str, ...] = ("confirm", "cancel", "undo")
#: Default wrong-commit limits per class (per decision unit).
DEFAULT_ALPHA: dict[str, float] = {"safe": 0.10, "undoable": 0.05, "irreversible": 0.01}
#: Score semantics that are probabilities (spec 3.5).
PROB_SEMANTICS = ("calibrated_prob", "uncalibrated_prob")
SCORE_SEMANTICS = ("calibrated_prob", "uncalibrated_prob", "power", "strength", "none")
#: Header key of the declaration and event kinds (FEP-0003).
DECLARATION_KEY = "intent_declaration"
INTENT = "intent"
INTENT_FEEDBACK = "intent_feedback"
FEEDBACK_OUTCOMES = ("confirmed", "cancelled", "selected", "undone", "correct", "wrong")
PROFILE = "intent"
TRUST_DECISION = "trust_decision"
#: Probability sums may exceed 1 by this much (float rounding).
SUM_TOL = 1e-6

Action = Literal["COMMIT", "OFFER", "ABSTAIN"]


class IntentEventError(ValueError):
    """An intent event or declaration breaks FEP-0003. The layer state is unchanged."""


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def stricter(a: str, b: str) -> str:
    """The stricter of two risk classes."""
    return a if RISK_CLASSES.index(a) >= RISK_CLASSES.index(b) else b


# ---------------------------------------------------------------------------
# Vocabulary declaration (FEP-0003 section 2)
# ---------------------------------------------------------------------------


def validate_intent_declaration(d: Any) -> list[str]:
    """The FEP-0003 section 2 errors of an ``intent_declaration`` object (empty list = valid)."""
    if not isinstance(d, dict):
        return ["intent_declaration must be a JSON object"]
    errs: list[str] = []
    for k in ("vocab_id", "vocab_version"):
        if k in d and not (isinstance(d[k], str) and d[k]):
            errs.append(f"intent_declaration {k} must be a non-empty string")
    items = d.get("intents")
    if not isinstance(items, list) or not items:
        return errs + ["intent_declaration intents must be a non-empty list"]
    seen: set[str] = set()
    roles: dict[str, int] = {}
    for j, it in enumerate(items):
        w = f"intents[{j}]"
        if not isinstance(it, dict):
            errs.append(f"{w} must be an object")
            continue
        iid = it.get("id")
        if not (isinstance(iid, str) and iid.strip()):
            errs.append(f"{w} id must be a non-empty string")
        elif iid in seen:
            errs.append(f"{w} id {iid!r} is not unique")
        else:
            seen.add(iid)
        if it.get("risk") not in RISK_CLASSES:
            errs.append(f"{w} risk {it.get('risk')!r} is not one of {list(RISK_CLASSES)}")
        role = it.get("role", "action")
        if role not in ROLES:
            errs.append(f"{w} role {role!r} is not one of {list(ROLES)}")
        else:
            roles[role] = roles.get(role, 0) + 1
        if "label" in it and not isinstance(it["label"], str):
            errs.append(f"{w} label must be a string")
    for r in UNIQUE_ROLES:
        if roles.get(r, 0) > 1:
            errs.append(f"at most one intent may have role {r!r} ({roles[r]} found)")
    good = [it for it in items if isinstance(it, dict)]
    if any(it.get("risk") == "irreversible" for it in good):
        for it in good:
            if it.get("role") == "confirm" and it.get("risk") != "irreversible":
                errs.append(f"the confirm intent {it.get('id')!r} executes irreversible intents, so its risk must be "
                            f"'irreversible' (FEP-0003 section 2 rule 4)")
    if roles.get("action", 0) + roles.get("confirm", 0) + roles.get("cancel", 0) + roles.get("undo", 0) == 0:
        errs.append("intent_declaration needs at least one intent that is not null")
    return errs


@dataclass(frozen=True)
class IntentSpec:
    """One intent of a vocabulary."""

    id: str
    risk: str = "undoable"
    role: str = "action"
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "risk": self.risk}
        if self.role != "action":
            d["role"] = self.role
        if self.label is not None:
            d["label"] = self.label
        return d


@dataclass(frozen=True)
class IntentVocabulary:
    """An intent vocabulary declaration (FEP-0003 section 2)."""

    intents: tuple[IntentSpec, ...]
    vocab_id: str | None = None
    vocab_version: str | None = None

    def __post_init__(self) -> None:
        errs = validate_intent_declaration(self.to_declaration())
        if errs:
            raise IntentEventError("; ".join(errs))

    @classmethod
    def from_declaration(cls, d: Any) -> "IntentVocabulary":
        errs = validate_intent_declaration(d)
        if errs:
            raise IntentEventError("; ".join(errs) + " (FEP-0003 section 2)")
        specs = tuple(IntentSpec(it["id"], it["risk"], it.get("role", "action"), it.get("label"))
                      for it in d["intents"])
        return cls(specs, d.get("vocab_id"), d.get("vocab_version"))

    @classmethod
    def simple(cls, ids: Sequence[str], risk: dict[str, str] | None = None, roles: dict[str, str] | None = None,
               default_risk: str = "undoable", vocab_id: str | None = None) -> "IntentVocabulary":
        risk, roles = risk or {}, roles or {}
        return cls(tuple(IntentSpec(i, risk.get(i, default_risk), roles.get(i, "action")) for i in ids), vocab_id)

    def to_declaration(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.vocab_id is not None:
            d["vocab_id"] = self.vocab_id
        if self.vocab_version is not None:
            d["vocab_version"] = self.vocab_version
        d["intents"] = [s.to_dict() for s in self.intents]
        return d

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(s.id for s in self.intents)

    def __len__(self) -> int:
        return len(self.intents)

    def index(self, iid: str) -> int:
        try:
            return self.ids.index(iid)
        except ValueError:
            raise IntentEventError(f"intent {iid!r} is not in the declaration") from None

    def role_id(self, role: str) -> str | None:
        for s in self.intents:
            if s.role == role:
                return s.id
        return None

    def null_mask(self) -> np.ndarray:
        return np.array([s.role == "null" for s in self.intents])


# ---------------------------------------------------------------------------
# Frozen configuration
# ---------------------------------------------------------------------------


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _thr_out(x: float) -> float | None:
    return float(x) if math.isfinite(x) else None


def _thr_in(x: Any) -> float:
    return math.inf if x is None else float(x)


@dataclass(frozen=True)
class IntentTrustConfig:
    """A frozen intent trust configuration (JSON, content id ``icfg-...``).

    ``thresholds[r]`` is the COMMIT threshold of risk class r on the
    calibrated top-1 probability; ``inf`` (JSON ``null``) means "never
    commit this class". ``risk_override`` makes intents stricter than the
    declaration (never laxer, FEP-0003 section 6 rule 7).
    """

    vocabulary: IntentVocabulary
    thresholds: dict[str, float] = field(default_factory=lambda: {r: math.inf for r in RISK_CLASSES})
    temperature: float = 1.0
    #: Floor of every COMMIT threshold: COMMIT needs p >= max(thresholds[r], min_threshold).
    #: The default 0.5 means "more likely than all other intents together". It is fixed before
    #: any data and only removes COMMITs, so a fitted bound still holds (risk_control docstring).
    #: It stops a lax class (for example ``safe`` with alpha 0.10) from committing on noise.
    min_threshold: float = 0.5
    #: OFFER the smallest top-k set with this calibrated mass ...
    offer_mass: float = 0.9
    #: ... if it has at most this many intents; else ABSTAIN.
    max_offer: int = 4
    #: Irreversible intents are armed (OFFER, confirm_required) and need a confirmation.
    confirm_irreversible: bool = True
    #: ABSTAIN while the latest signal_quality index is below this (None: off).
    min_signal_quality: float | None = None
    #: No COMMIT if the normalised entropy of the calibrated distribution is >= this (None: off).
    max_norm_entropy: float | None = None
    undo_window_units: int = 3
    undo_window_s: float | None = None
    risk_override: dict[str, str] = field(default_factory=dict)
    name: str = "intent-trust"
    #: Fit record (alpha, delta, method, n, per-class results). Not part of the content id.
    fit: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if set(self.thresholds) != set(RISK_CLASSES):
            raise ValueError(f"thresholds needs exactly the classes {list(RISK_CLASSES)}")
        if not (self.temperature > 0 and math.isfinite(self.temperature)):
            raise ValueError("temperature must be a finite number > 0")
        if not 0.0 <= self.min_threshold <= 1.0:
            raise ValueError("min_threshold must be in [0, 1]")
        if not 0.0 < self.offer_mass <= 1.0 or self.max_offer < 0:
            raise ValueError("offer_mass must be in (0, 1] and max_offer >= 0")
        for iid, r in self.risk_override.items():
            spec = self.vocabulary.intents[self.vocabulary.index(iid)]
            if r not in RISK_CLASSES or stricter(r, spec.risk) != r:
                raise ValueError(f"risk_override {iid!r}: {r!r} must be a class at least as strict as {spec.risk!r}")

    # --- risk classes -----------------------------------------------------------

    def risk_of(self, iid: str, declared: str | None = None) -> str:
        """Effective risk class: the strictest of the config, the override and a stream declaration."""
        spec = self.vocabulary.intents[self.vocabulary.index(iid)]
        r = self.risk_override.get(iid, spec.risk)
        return stricter(r, declared) if declared in RISK_CLASSES else r

    def threshold_of(self, risk: str) -> float:
        """The COMMIT threshold of a class: max(fitted threshold, min_threshold)."""
        return max(float(self.thresholds[risk]), float(self.min_threshold))

    def risk_vector(self) -> list[str]:
        return [self.risk_of(i) for i in self.vocabulary.ids]

    # --- serialisation ------------------------------------------------------------

    def _payload(self) -> dict[str, Any]:
        return {
            "kind": "fidetype.intent-trust-config/1",
            "vocabulary": self.vocabulary.to_declaration(),
            "thresholds": {r: _thr_out(self.thresholds[r]) for r in RISK_CLASSES},
            "temperature": float(self.temperature),
            "min_threshold": float(self.min_threshold),
            "offer_mass": float(self.offer_mass),
            "max_offer": int(self.max_offer),
            "confirm_irreversible": bool(self.confirm_irreversible),
            "min_signal_quality": self.min_signal_quality,
            "max_norm_entropy": self.max_norm_entropy,
            "undo_window_units": int(self.undo_window_units),
            "undo_window_s": self.undo_window_s,
            "risk_override": dict(sorted(self.risk_override.items())),
        }

    @property
    def config_id(self) -> str:
        return "icfg-" + hashlib.sha256(_canonical(self._payload()).encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "name": self.name, "config_id": self.config_id, "fit": self.fit}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntentTrustConfig":
        if d.get("kind") != "fidetype.intent-trust-config/1":
            raise ValueError(f"not an intent trust configuration: kind {d.get('kind')!r}")
        cfg = cls(
            vocabulary=IntentVocabulary.from_declaration(d["vocabulary"]),
            thresholds={r: _thr_in(d["thresholds"].get(r)) for r in RISK_CLASSES},
            temperature=float(d.get("temperature", 1.0)),
            min_threshold=float(d.get("min_threshold", 0.5)),
            offer_mass=float(d.get("offer_mass", 0.9)),
            max_offer=int(d.get("max_offer", 4)),
            confirm_irreversible=bool(d.get("confirm_irreversible", True)),
            min_signal_quality=d.get("min_signal_quality"),
            max_norm_entropy=d.get("max_norm_entropy"),
            undo_window_units=int(d.get("undo_window_units", 3)),
            undo_window_s=d.get("undo_window_s"),
            risk_override=dict(d.get("risk_override", {})),
            name=d.get("name", "intent-trust"),
            fit=dict(d.get("fit", {})),
        )
        if "config_id" in d and d["config_id"] != cfg.config_id:
            raise ValueError(f"config_id {d['config_id']!r} does not match the content ({cfg.config_id!r})")
        return cfg

    def save(self, path: str | PathLike[str]) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=1, ensure_ascii=False, allow_nan=False) + "\n",
                              encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path: str | PathLike[str]) -> "IntentTrustConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Probabilities
# ---------------------------------------------------------------------------


def calibrate(probs: np.ndarray, temperature: float) -> np.ndarray:
    """Temperature-scaled probabilities: softmax(log p / T), row-wise. Zero stays zero."""
    p = np.asarray(probs, dtype=np.float64)
    with np.errstate(divide="ignore"):
        z = np.log(np.clip(p, 0.0, None)) / float(temperature)
    z = np.where(np.isfinite(z), z, -np.inf)
    m = np.max(z, axis=-1, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0)
    e = np.exp(z - m)
    s = e.sum(axis=-1, keepdims=True)
    return np.divide(e, s, out=np.full_like(e, 1.0 / p.shape[-1]), where=s > 0)


def norm_entropy(p: np.ndarray) -> float:
    p = np.asarray(p, dtype=np.float64)
    nz = p[p > 0]
    return float(-(nz * np.log(nz)).sum() / math.log(len(p))) if len(p) > 1 else 0.0


def candidates_to_probs(cands: Sequence[dict[str, Any]], vocab: IntentVocabulary) -> np.ndarray:
    """A full distribution over the vocabulary from a (possibly top-k) candidate list.

    The missing mass (1 - sum) is spread uniformly over the intents that
    are not in the list (as spec 3.3 does for sparse frames).
    """
    n = len(vocab)
    p = np.zeros(n)
    listed = np.zeros(n, dtype=bool)
    for c in cands:
        j = vocab.index(c["intent"])
        p[j] = float(c["score"])
        listed[j] = True
    rest = max(0.0, 1.0 - p.sum())
    if (~listed).any():
        p[~listed] = rest / int((~listed).sum())
    s = p.sum()
    return p / s if s > 0 else np.full(n, 1.0 / n)


# ---------------------------------------------------------------------------
# Policy (stateless)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentChoice:
    """The stateless result of :meth:`IntentPolicy.decide`."""

    action: Action
    #: Top-1 intent id and its calibrated probability.
    top: str
    p_top1: float
    risk_class: str
    threshold: float
    #: The intent of a COMMIT or an armed intent (OFFER with confirm_required).
    intent: str | None = None
    offered: tuple[str, ...] = ()
    confirm_required: bool = False
    reason: str = ""


class IntentPolicy:
    """Candidate probabilities -> COMMIT / OFFER / ABSTAIN (module docstring)."""

    def __init__(self, config: IntentTrustConfig) -> None:
        self.config = config
        self.vocab = config.vocabulary
        self._null = self.vocab.null_mask()

    def commit_blocked(self, p_cal: np.ndarray, top: int, prob_semantics: bool = True,
                       quality: float | None = None) -> str | None:
        """Why a COMMIT of ``top`` is not allowed by the gates (None: allowed)."""
        c = self.config
        if self._null[top]:
            return "null intent is never committed"
        if not prob_semantics:
            return "scores are not probabilities"
        if c.min_signal_quality is not None and quality is not None and quality < c.min_signal_quality:
            return f"signal quality {quality:.2f} < {c.min_signal_quality:.2f}"
        if c.max_norm_entropy is not None and norm_entropy(p_cal) >= c.max_norm_entropy:
            return f"near-uniform distribution (normalised entropy >= {c.max_norm_entropy:.2f})"
        return None

    def offer_set(self, p_cal: np.ndarray) -> tuple[str, ...]:
        c = self.config
        order = [j for j in np.argsort(-p_cal, kind="stable") if not self._null[j]]
        mass, out = 0.0, []
        for j in order:
            if len(out) >= c.max_offer:
                break
            out.append(self.vocab.ids[j])
            mass += float(p_cal[j])
            if mass >= c.offer_mass - 1e-12:
                return tuple(out)
        return ()

    def decide(self, probs: np.ndarray, prob_semantics: bool = True, quality: float | None = None,
               declared_risk: dict[str, str] | None = None, calibrated: bool = False) -> IntentChoice:
        """One decision. ``probs``: a distribution over the vocabulary (raw unless ``calibrated``)."""
        c = self.config
        p_cal = np.asarray(probs, dtype=np.float64) if calibrated else calibrate(probs, c.temperature)
        top = int(np.argmax(p_cal))
        tid = self.vocab.ids[top]
        p1 = float(p_cal[top])
        risk = c.risk_of(tid, (declared_risk or {}).get(tid))
        thr = c.threshold_of(risk)
        if c.min_signal_quality is not None and quality is not None and quality < c.min_signal_quality:
            return IntentChoice("ABSTAIN", tid, p1, risk, thr, reason=f"signal quality {quality:.2f} < {c.min_signal_quality:.2f}")
        if self._null[top]:
            return IntentChoice("ABSTAIN", tid, p1, risk, thr, reason="top intent is null (no intent)")
        why = self.commit_blocked(p_cal, top, prob_semantics, quality)
        if why is None and p1 >= thr:
            if risk == "irreversible" and c.confirm_irreversible:
                return IntentChoice("OFFER", tid, p1, risk, thr, intent=tid, offered=(tid,), confirm_required=True,
                                    reason=f"armed: p {p1:.3f} >= {thr:.3f} ({risk}); needs confirmation")
            return IntentChoice("COMMIT", tid, p1, risk, thr, intent=tid,
                                reason=f"p {p1:.3f} >= {thr:.3f} ({risk})")
        off = self.offer_set(p_cal)
        base = why or (f"p {p1:.3f} < {thr:.3f} ({risk})" if math.isfinite(thr) else f"class {risk} never commits")
        if off:
            return IntentChoice("OFFER", tid, p1, risk, thr, offered=off, reason=f"{base}; offer {len(off)}")
        return IntentChoice("ABSTAIN", tid, p1, risk, thr, reason=f"{base}; no small offer set")


# ---------------------------------------------------------------------------
# Fit with per-class risk control
# ---------------------------------------------------------------------------


def class_calibration_data(config: IntentTrustConfig, probs_cal: np.ndarray, labels: np.ndarray,
                           risk: str, prob_semantics: bool = True,
                           quality: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(scores, commit_losses) of risk class ``risk`` (module docstring). ``labels`` -1 = no intent."""
    pol = IntentPolicy(config)
    rv = config.risk_vector()
    top = np.argmax(probs_cal, axis=1)
    p1 = probs_cal[np.arange(len(top)), top]
    s = np.full(len(top), -np.inf)
    for i, k in enumerate(top):
        if rv[k] != risk:
            continue
        q = None if quality is None else float(quality[i])
        if pol.commit_blocked(probs_cal[i], int(k), prob_semantics, q) is None:
            s[i] = p1[i]
    c = (top != np.asarray(labels)).astype(np.float64)
    return s, c


def fit_intent_config(
    vocabulary: IntentVocabulary,
    fit_probs: np.ndarray,
    fit_labels: np.ndarray,
    cal_probs: np.ndarray,
    cal_labels: np.ndarray,
    alpha: dict[str, float] | None = None,
    method: Literal["ltt", "crc"] = "ltt",
    delta: float = 0.1,
    grid: Sequence[float] | None = None,
    fit_temperature: bool = True,
    no_signal_probs: np.ndarray | None = None,
    **config_kw: Any,
) -> IntentTrustConfig:
    """Fit an :class:`IntentTrustConfig`.

    1. Temperature on ``fit_*`` (NLL, :class:`~fidetype.trust.calibration.TemperatureScaler`;
       rows with label -1 are ignored).
    2. One COMMIT threshold per risk class on ``cal_*`` with LTT
       (``delta / 3`` per class, Bonferroni) or CRC. An infeasible class gets
       ``inf`` (never commit).

    3. Optional **no-signal reference** (``no_signal_probs``): decoder
       outputs on known no-signal input (an all-zero or a rest recording;
       no labels needed). Each class threshold is raised just above the
       highest calibrated top-1 probability that this reference gives for
       that class. So the configuration does not COMMIT on that input. It
       only raises thresholds, so the risk bound still holds.

    The two sets must be disjoint, and exchangeable with the deployment
    data (same user and session; see :mod:`fidetype.trust.risk_control`).
    """
    alpha = {**DEFAULT_ALPHA, **(alpha or {})}
    T = 1.0
    if fit_temperature:
        with np.errstate(divide="ignore"):
            lp = np.log(np.clip(np.asarray(fit_probs, dtype=np.float64), 1e-300, None))
        T = TemperatureScaler().fit(lp, np.asarray(fit_labels)).temperature
    base = IntentTrustConfig(vocabulary, temperature=T, **config_kw)
    pc = calibrate(cal_probs, T)
    thr: dict[str, float] = {}
    rec: dict[str, Any] = {}
    k = len(RISK_CLASSES)
    for r in RISK_CLASSES:
        s, c = class_calibration_data(base, pc, np.asarray(cal_labels), r)
        if method == "ltt":
            res = ltt_threshold(s, c, alpha[r], delta / k, grid=grid or DEFAULT_LTT_GRID)
        elif method == "crc":
            res = crc_threshold(s, c, alpha[r])
        else:
            raise ValueError(f"unknown method {method!r}")
        thr[r] = res.threshold
        rec[r] = {"alpha": alpha[r], "threshold": _thr_out(res.threshold), "feasible": res.feasible,
                  "empirical_risk": res.empirical_risk, "commit_rate": res.commit_rate,
                  "n_class_top1": int(np.isfinite(s).sum())}
    if no_signal_probs is not None:
        p0 = calibrate(np.atleast_2d(no_signal_probs), T)
        top0 = np.argmax(p0, axis=1)
        rv = base.risk_vector()
        pol = IntentPolicy(base)
        for r in RISK_CLASSES:
            m = [float(p0[i, k]) for i, k in enumerate(top0)
                 if rv[k] == r and pol.commit_blocked(p0[i], int(k)) is None]
            floor = min(1.0, max(m) + 1e-9) if m else None
            rec[r]["no_signal_floor"] = floor
            if floor is not None and floor > thr[r]:
                thr[r] = floor if floor < 1.0 else math.inf
    fit = {"method": method, "delta": delta if method == "ltt" else None, "n_fit": int(len(fit_labels)),
           "n_cal": int(len(cal_labels)), "temperature": T, "classes": rec,
           "no_signal_reference": None if no_signal_probs is None else int(np.atleast_2d(no_signal_probs).shape[0])}
    return replace(base, thresholds=thr, fit=fit)


def evaluate_policy(config: IntentTrustConfig, probs: np.ndarray, labels: np.ndarray,
                    quality: np.ndarray | None = None, prob_semantics: bool = True) -> dict[str, Any]:
    """Stateless metrics of :class:`IntentPolicy` on labelled items (vectorised; same rule as ``decide``).

    Returns counts and rates per decision unit: ``commit`` (COMMIT of a
    non-irreversible intent), ``armed`` (irreversible intent armed for
    confirmation), ``offer``, ``abstain``; ``wrong_<class>`` = wrong COMMITs
    (for ``irreversible``: wrong arms) of that class / n; ``truth_in_offer``.
    ``labels`` -1 = no intent.
    """
    c = config
    pol = IntentPolicy(c)
    y = np.asarray(labels)
    n = len(y)
    pc = calibrate(probs, c.temperature)
    top = np.argmax(pc, axis=1)
    p1 = pc[np.arange(n), top]
    rv = np.array(c.risk_vector())
    cls = rv[top]
    thr_of = {r: c.threshold_of(r) for r in RISK_CLASSES}
    thr = np.array([thr_of[r] for r in cls], dtype=np.float64)
    null = pol._null[top]
    gate_ok = ~null & bool(prob_semantics)
    if c.min_signal_quality is not None and quality is not None:
        gate_ok &= ~(np.asarray(quality) < c.min_signal_quality)
    if c.max_norm_entropy is not None:
        gate_ok &= np.array([norm_entropy(r) < c.max_norm_entropy for r in pc])
    pass_ = gate_ok & (p1 >= thr)
    armed = pass_ & (cls == "irreversible") & c.confirm_irreversible
    commit = pass_ & ~armed
    wrong = top != y
    rest = ~pass_
    q_abst = np.zeros(n, dtype=bool)
    if c.min_signal_quality is not None and quality is not None:
        q_abst = np.asarray(quality) < c.min_signal_quality
    offer = np.zeros(n, dtype=bool)
    tio = 0
    for i in np.where(rest & ~q_abst & ~null)[0]:
        off = pol.offer_set(pc[i])
        if off:
            offer[i] = True
            tio += int(y[i] >= 0 and c.vocabulary.ids[y[i]] in off)
    out: dict[str, Any] = {"n": n, "commit": int(commit.sum()), "armed": int(armed.sum()), "offer": int(offer.sum()),
                           "abstain": int(n - commit.sum() - armed.sum() - offer.sum()), "truth_in_offer": tio,
                           "commit_correct": int((commit & ~wrong).sum())}
    for r in RISK_CLASSES:
        sel = (armed if r == "irreversible" and c.confirm_irreversible else commit) & (cls == r)
        out[f"wrong_{r}"] = int((sel & wrong).sum())
        out[f"acted_{r}"] = int(sel.sum())
    out["wrong_any"] = int(((commit | armed) & wrong).sum())
    return out


# ---------------------------------------------------------------------------
# Stream layer
# ---------------------------------------------------------------------------


def validate_intent_event(ev: dict[str, Any], vocab: IntentVocabulary | None) -> list[str]:
    """The FEP-0003 section 3 errors of one ``intent`` event (empty = valid)."""
    errs: list[str] = []
    if vocab is None:
        errs.append("an intent event needs an intent_declaration in the header")
    if not isinstance(ev.get("id"), str) or not ev.get("id"):
        errs.append("id must be a non-empty string")
    if not _num(ev.get("t")):
        errs.append("t must be a finite number")
    if not isinstance(ev.get("is_final"), bool):
        errs.append("is_final must be a boolean")
    sem = ev.get("score_semantics")
    if sem not in SCORE_SEMANTICS:
        errs.append(f"score_semantics {sem!r} is not one of {list(SCORE_SEMANTICS)}")
    for k in ("t_start", "t_end"):
        if k in ev and not _num(ev[k]):
            errs.append(f"{k} must be a finite number")
    if "revision_of" in ev and ev["revision_of"] is not None and not isinstance(ev["revision_of"], str):
        errs.append("revision_of must be a string or null")
    cands = ev.get("candidates")
    if not isinstance(cands, list) or not cands:
        return errs + ["candidates must be a non-empty list"]
    seen: set[str] = set()
    scores: list[float] = []
    for j, c in enumerate(cands):
        w = f"candidates[{j}]"
        if not isinstance(c, dict) or not isinstance(c.get("intent"), str):
            errs.append(f"{w} must be an object with a string intent")
            continue
        iid = c["intent"]
        if iid in seen:
            errs.append(f"{w} intent {iid!r} appears twice")
        seen.add(iid)
        if vocab is not None and iid not in vocab.ids:
            errs.append(f"{w} intent {iid!r} is not in the declaration")
        sc = c.get("score")
        if sem == "none":
            if sc is not None:
                errs.append(f"{w} score must be null or absent with score_semantics none")
        elif sem in PROB_SEMANTICS:
            if not (_num(sc) and 0.0 <= sc <= 1.0):
                errs.append(f"{w} score must be a number in [0, 1]")
            else:
                scores.append(float(sc))
        elif sem in ("power", "strength"):
            if not _num(sc):
                errs.append(f"{w} score must be a finite number")
            else:
                scores.append(float(sc))
    if sem in PROB_SEMANTICS and scores and sum(scores) > 1.0 + SUM_TOL:
        errs.append(f"candidate scores sum to {sum(scores):.6f} > 1")
    if sem != "none" and len(scores) == len(cands) and any(b > a + 1e-12 for a, b in zip(scores, scores[1:])):
        errs.append("candidates must be ranked best first (scores non-increasing)")
    return errs


def validate_feedback_event(ev: dict[str, Any], vocab: IntentVocabulary | None = None) -> list[str]:
    """The FEP-0003 section 4 errors of one ``intent_feedback`` event."""
    errs: list[str] = []
    if not (_int(ev.get("ref_unit")) and ev["ref_unit"] >= 0):
        errs.append("ref_unit must be an integer >= 0")
    if ev.get("outcome") not in FEEDBACK_OUTCOMES:
        errs.append(f"outcome {ev.get('outcome')!r} is not one of {list(FEEDBACK_OUTCOMES)}")
    if ev.get("outcome") == "selected" and not isinstance(ev.get("intent"), str):
        errs.append("outcome selected needs the selected intent")
    if "intent" in ev and ev["intent"] is not None:
        if not isinstance(ev["intent"], str):
            errs.append("intent must be a string")
        elif vocab is not None and ev["intent"] not in vocab.ids:
            errs.append(f"intent {ev['intent']!r} is not in the declaration")
    if "t" in ev and not _num(ev["t"]):
        errs.append("t must be a finite number")
    if "source" in ev and not isinstance(ev["source"], str):
        errs.append("source must be a string")
    return errs


def _sha(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IntentDecision:
    """One decision of :class:`IntentTrustLayer` (a ``trust_decision`` with ``profile = "intent"``)."""

    session_id: str
    seq: int
    unit: int
    final: bool
    action: Action
    p_top1: float | None
    risk_class: str | None
    threshold: float | None
    reason: str
    intent: str | None = None
    role: str | None = None
    offered: tuple[str, ...] = ()
    confirm_required: bool = False
    confirmation_of: int | None = None
    confirmed_via: str | None = None
    undo_of: int | None = None
    pending_cleared: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def acts(self) -> bool:
        """True if a bridge may actuate this decision (final COMMIT)."""
        return self.final and self.action == "COMMIT" and self.intent is not None

    def to_event(self) -> dict[str, Any]:
        """The decision as a ``trust_decision`` JSON event (FEP-0003 section 5). Never carries ``shown``."""
        ev: dict[str, Any] = {
            "type": TRUST_DECISION,
            "profile": PROFILE,
            "session": self.session_id,
            "seq": self.seq,
            "unit": self.unit,
            "is_final": self.final,
            "action": self.action,
            "reason": self.reason,
            "p_top1": None if self.p_top1 is None or not math.isfinite(self.p_top1) else round(float(self.p_top1), 6),
            "score_semantics": "calibrated_prob",
            "risk_class": self.risk_class,
            "threshold": None if self.threshold is None or not math.isfinite(self.threshold) else float(self.threshold),
        }
        if self.intent is not None:
            ev["intent"] = self.intent
        if self.role is not None:
            ev["role"] = self.role
        if self.offered:
            ev["offered"] = list(self.offered)
        if self.confirm_required:
            ev["confirm_required"] = True
        for k in ("confirmation_of", "confirmed_via", "undo_of", "pending_cleared"):
            v = getattr(self, k)
            if v is not None:
                ev[k] = v
        for k in ("config_id", "vocab_id", "input", "latency_s"):
            if k in self.provenance:
                ev[k] = self.provenance[k]
        return ev


@dataclass
class _ISession:
    id: str
    header: dict[str, Any] | None = None
    declared: dict[str, str] = field(default_factory=dict)
    vocab_ok: bool = True
    frames: list[np.ndarray] = field(default_factory=list)
    frame_t: list[float] = field(default_factory=list)
    frame_vocab: list[str] | None = None
    blank_id: int | None = None
    quality: float | None = None
    unit: int = 0
    seq: int = 0
    ended: bool = False
    #: The armed irreversible intent: (unit, intent, t).
    pending: tuple[int, str, float | None] | None = None
    #: Final OFFERs that a feedback may answer: unit -> offered intents.
    offers: dict[int, tuple[str, ...]] = field(default_factory=dict)
    #: Committed actions: (unit, intent, risk class, t, undone).
    commits: list[list[Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: {
        "units": 0, "commits": 0, "offers": 0, "abstains": 0, "armed": 0, "confirmed": 0, "undone": 0,
        "feedback_wrong": 0, "feedback_correct": 0, "ignored_events": 0})


class IntentTrustLayer:
    """Streaming intent trust layer: ``push(event) -> [IntentDecision]`` (module docstring).

    Input routes: ``intent`` events (any header with an ``intent_declaration``);
    v0.1 ``decision`` events (one label; probability score semantics give a
    one-candidate distribution); and, on a ``vocab_type = "command"`` stream,
    frames: the mean probability of the frames of a segment (``segment_end``,
    ``end``) is one decision unit. When embedded in
    :class:`~fidetype.trust.streaming.StreamingTrustLayer` (``intent=``), the
    frames belong to the text route and only events are read here.
    """

    def __init__(self, config: IntentTrustConfig, read_frames: bool = True, max_sessions: int = 256,
                 clock: Callable[[], float] | None = None) -> None:
        import time

        self.config = config
        self.policy = IntentPolicy(config)
        self.vocab = config.vocabulary
        self.read_frames = read_frames
        self.max_sessions = max_sessions
        self.clock = clock or time.perf_counter
        self._sessions: dict[str, _ISession] = {}

    def _session(self, sid: str) -> _ISession:
        s = self._sessions.get(sid)
        if s is None:
            if len(self._sessions) >= self.max_sessions:
                raise IntentEventError(f"too many sessions (max_sessions = {self.max_sessions})")
            s = self._sessions[sid] = _ISession(sid)
        return s

    def stats(self, session_id: str = "default") -> dict[str, int]:
        return dict(self._sessions[session_id].stats)

    # --- input --------------------------------------------------------------------

    def push(self, event: dict[str, Any] | str | bytes, session_id: str = "default",
             seq_alloc: Callable[[], int] | None = None) -> list[IntentDecision]:
        """Consume one event; return the intent decisions it causes.

        ``seq_alloc`` (optional) gives the next ``seq`` of the session; a
        layer that shares a decision log with a text layer passes the text
        layer's counter (FEP-0003 section 7 rule 2).
        """
        t0 = self.clock()
        ev = json.loads(event) if isinstance(event, (str, bytes)) else event
        if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
            raise IntentEventError("event must be a JSON object with a string type")
        s = self._session(session_id)
        typ = ev["type"]
        alloc = seq_alloc or (lambda: self._next_seq(s))
        if typ == "header":
            out = self._flush_frames(s, alloc, t0)
            self._read_header(s, ev)
            return out
        if s.header is None:
            raise IntentEventError(f"{typ!r} event before the header")
        if s.ended:
            s.stats["ignored_events"] += 1
            return []
        if typ == INTENT:
            return self._intent(s, ev, alloc, t0)
        if typ == INTENT_FEEDBACK:
            return self._feedback(s, ev, alloc, t0)
        if typ == "decision":
            return self._v01_decision(s, ev, alloc, t0)
        if typ == "signal_quality":
            v = ev.get("value")
            if ev.get("unit") == "index" and _num(v):
                s.quality = float(v)
            return []
        if typ == "frame" and s.frame_vocab is not None:
            self._frame(s, ev)
            return []
        if typ in ("segment_end", "end"):
            out = self._flush_frames(s, alloc, t0)
            s.ended = typ == "end"
            return out
        s.stats["ignored_events"] += 1
        return []

    def _next_seq(self, s: _ISession) -> int:
        s.seq += 1
        return s.seq - 1

    def _read_header(self, s: _ISession, ev: dict[str, Any]) -> None:
        # A new header starts a new stream. seq, unit and stats stay (FEP-0001 section 3 rule 5).
        s.header = {k: v for k, v in ev.items() if k != "type"}
        s.declared, s.frames, s.frame_t, s.frame_vocab, s.blank_id = {}, [], [], None, None
        s.quality, s.ended, s.pending, s.offers = None, False, None, {}
        d = ev.get(DECLARATION_KEY)
        if d is not None:
            v = IntentVocabulary.from_declaration(d)
            unknown = set(v.ids) - set(self.vocab.ids)
            missing = set(self.vocab.ids) - set(v.ids)
            if unknown or missing:
                raise IntentEventError(f"the stream declaration does not match the configuration vocabulary "
                                       f"(unknown {sorted(unknown)}, missing {sorted(missing)})")
            s.declared = {it.id: it.risk for it in v.intents}
        if self.read_frames and ev.get("vocab_type") == "command" and d is not None:
            vocab = list(ev.get("vocab") or [])
            b = ev.get("blank_id")
            toks = [t for j, t in enumerate(vocab) if j != b]
            if set(toks) != set(self.vocab.ids):
                raise IntentEventError("command vocab (without blank) must equal the declared intents (FEP-0003 section 2 rule 5)")
            s.frame_vocab, s.blank_id = vocab, b

    def _frame(self, s: _ISession, ev: dict[str, Any]) -> None:
        lp = ev.get("log_probs")
        if not isinstance(lp, list) or len(lp) != len(s.frame_vocab or []):
            raise IntentEventError("frame log_probs must have one value per vocab token")
        row = np.array([-np.inf if x is None else float(x) for x in lp])
        s.frames.append(np.exp(row))
        s.frame_t.append(float(ev.get("t", math.nan)))

    def _flush_frames(self, s: _ISession, alloc: Callable[[], int], t0: float) -> list[IntentDecision]:
        if not s.frames:
            return []
        P = np.mean(np.stack(s.frames), axis=0)
        vocab = s.frame_vocab or []
        p = np.zeros(len(self.vocab))
        for j, tok in enumerate(vocab):
            if j != s.blank_id:
                p[self.vocab.index(tok)] = P[j]
        p = p / p.sum() if p.sum() > 0 else np.full(len(self.vocab), 1.0 / len(self.vocab))
        t = s.frame_t[-1] if s.frame_t else None
        ref = {"kind": "frames", "n_frames": len(s.frames), "t_end": t}
        s.frames, s.frame_t = [], []
        return self._decide(s, p, True, ref, t, alloc, t0)

    def _intent(self, s: _ISession, ev: dict[str, Any], alloc: Callable[[], int], t0: float) -> list[IntentDecision]:
        vocab = self.vocab if s.header and s.header.get(DECLARATION_KEY) is not None else None
        errs = validate_intent_event(ev, vocab)
        if errs:
            raise IntentEventError("; ".join(errs) + " (FEP-0003 section 3)")
        sem = ev["score_semantics"]
        prob = sem in PROB_SEMANTICS
        if prob:
            p = candidates_to_probs(ev["candidates"], self.vocab)
        else:  # no probabilities: rank only; uniform mass, top-1 first (never committed)
            p = np.full(len(self.vocab), 1e-6)
            for r, c in enumerate(ev["candidates"]):
                p[self.vocab.index(c["intent"])] = 1.0 - 1e-3 * r
            p = p / p.sum()
        ref = {"kind": "intent", "intent_id": ev["id"], "score_semantics": sem,
               "sha256": _sha({k: v for k, v in ev.items() if not k.startswith("_")})}
        if ev.get("revision_of"):
            ref["revision_of"] = ev["revision_of"]
        return self._decide(s, p, prob, ref, ev.get("t"), alloc, t0, final=ev["is_final"])

    def _v01_decision(self, s: _ISession, ev: dict[str, Any], alloc: Callable[[], int], t0: float) -> list[IntentDecision]:
        label = ev.get("label")
        if not isinstance(label, str) or label not in self.vocab.ids:
            s.stats["ignored_events"] += 1
            return []
        sem = ev.get("score_semantics")
        sc = ev.get("score")
        prob = sem in PROB_SEMANTICS and _num(sc) and 0.0 <= sc <= 1.0
        cand = [{"intent": label, "score": float(sc) if prob else 1.0}]
        p = candidates_to_probs(cand, self.vocab)
        ref = {"kind": "decision", "label": label, "score_semantics": sem, "sha256": _sha(ev)}
        return self._decide(s, p, bool(prob), ref, ev.get("t"), alloc, t0)

    # --- decisions --------------------------------------------------------------------

    def _emit(self, s: _ISession, alloc: Callable[[], int], t0: float, final: bool, ref: dict[str, Any] | None,
              **kw: Any) -> IntentDecision:
        prov = {"config_id": self.config.config_id, "latency_s": round(max(0.0, self.clock() - t0), 6)}
        if self.vocab.vocab_id:
            prov["vocab_id"] = self.vocab.vocab_id
        if ref is not None:
            prov["input"] = ref
        d = IntentDecision(s.id, alloc(), s.unit, final, provenance=prov, **kw)
        if final:
            s.offers = {}  # a feedback may answer only the latest final OFFER
            s.unit += 1
            s.stats["units"] += 1
            s.stats[{"COMMIT": "commits", "OFFER": "offers", "ABSTAIN": "abstains"}[d.action]] += 1
        return d

    def _role(self, iid: str | None) -> str | None:
        if iid is None:
            return None
        return self.vocab.intents[self.vocab.index(iid)].role

    def _decide(self, s: _ISession, p: np.ndarray, prob: bool, ref: dict[str, Any], t: Any,
                alloc: Callable[[], int], t0: float, final: bool = True) -> list[IntentDecision]:
        # The configuration temperature is always applied: its thresholds were fitted on scores scaled by it.
        p_cal = calibrate(p, self.config.temperature)
        ch = self.policy.decide(p_cal, prob_semantics=prob, quality=s.quality, declared_risk=s.declared,
                                calibrated=True)
        t = float(t) if _num(t) else None
        if not final:  # a provisional preview: never an action, no state change
            return [self._emit(s, alloc, t0, False, ref, action=ch.action, p_top1=ch.p_top1, risk_class=ch.risk_class,
                               threshold=ch.threshold, reason=ch.reason, intent=ch.intent, role=self._role(ch.intent),
                               offered=ch.offered, confirm_required=ch.confirm_required)]
        role = self._role(ch.top)
        pending, s.pending = s.pending, None
        cleared = None if pending is None else "superseded by a new unit"
        allowed = self.policy.commit_blocked(p_cal, self.vocab.index(ch.top), prob, s.quality) is None
        # role intents: confirm / cancel / undo
        if role == "confirm":
            if pending is None:
                return [self._emit(s, alloc, t0, True, ref, action="ABSTAIN", p_top1=ch.p_top1, risk_class=ch.risk_class,
                                   threshold=ch.threshold, reason="confirm: nothing to confirm", role=role)]
            p_unit, p_intent, _ = pending
            thr = self.config.threshold_of(self.config.risk_of(p_intent, s.declared.get(p_intent)))
            if allowed and ch.p_top1 >= thr:
                s.stats["confirmed"] += 1
                d = self._emit(s, alloc, t0, True, ref, action="COMMIT", p_top1=ch.p_top1, risk_class="irreversible",
                               threshold=thr, reason=f"confirmed: p {ch.p_top1:.3f} >= {thr:.3f}", intent=p_intent,
                               role=self._role(p_intent), confirmation_of=p_unit, confirmed_via="intent")
                s.commits.append([d.unit, p_intent, "irreversible", t, False])
                return [d]
            return [self._emit(s, alloc, t0, True, ref, action="ABSTAIN", p_top1=ch.p_top1, risk_class="irreversible",
                               threshold=thr, reason=f"confirmation not certain (p {ch.p_top1:.3f} < {thr:.3f}); "
                               f"armed intent dropped", role=role, pending_cleared="confirmation failed")]
        if role == "undo" and ch.action == "COMMIT":
            target = self._undo_target(s, t)
            if target is None:
                return [self._emit(s, alloc, t0, True, ref, action="ABSTAIN", p_top1=ch.p_top1, risk_class=ch.risk_class,
                                   threshold=ch.threshold, reason="undo: nothing undoable in the window", role=role,
                                   pending_cleared=cleared)]
            target[4] = True
            s.stats["undone"] += 1
            d = self._emit(s, alloc, t0, True, ref, action="COMMIT", p_top1=ch.p_top1, risk_class=ch.risk_class,
                           threshold=ch.threshold, reason=ch.reason + f"; undo unit {target[0]}", intent=ch.intent,
                           role=role, undo_of=int(target[0]), pending_cleared=cleared)
            return [d]
        if role == "cancel" and ch.action == "COMMIT" and pending is not None:
            cleared = "cancelled"
        d = self._emit(s, alloc, t0, True, ref, action=ch.action, p_top1=ch.p_top1, risk_class=ch.risk_class,
                       threshold=ch.threshold, reason=ch.reason, intent=ch.intent, role=self._role(ch.intent) or role,
                       offered=ch.offered, confirm_required=ch.confirm_required, pending_cleared=cleared)
        if d.action == "OFFER":
            s.offers[d.unit] = d.offered
            if d.confirm_required:
                s.pending = (d.unit, d.intent, t)  # type: ignore[assignment]
                s.stats["armed"] += 1
        elif d.action == "COMMIT" and role == "action":
            s.commits.append([d.unit, d.intent, d.risk_class, t, False])
        return [d]

    def _undo_target(self, s: _ISession, t: float | None) -> list[Any] | None:
        c = self.config
        for rec in reversed(s.commits):
            unit, _iid, risk, t_c, undone = rec
            if s.unit - unit > c.undo_window_units:
                return None
            if c.undo_window_s is not None and t is not None and t_c is not None and t - t_c > c.undo_window_s:
                return None
            if undone:
                continue
            return rec if risk in ("safe", "undoable") else None  # an irreversible action blocks undo
        return None

    def _feedback(self, s: _ISession, ev: dict[str, Any], alloc: Callable[[], int], t0: float) -> list[IntentDecision]:
        errs = validate_feedback_event(ev, self.vocab)
        if errs:
            raise IntentEventError("; ".join(errs) + " (FEP-0003 section 4)")
        ref_unit, outcome = int(ev["ref_unit"]), ev["outcome"]
        ref = {"kind": "feedback", "ref_unit": ref_unit, "outcome": outcome, "source": ev.get("source")}
        if outcome == "wrong":
            s.stats["feedback_wrong"] += 1
            return []
        if outcome == "correct":
            s.stats["feedback_correct"] += 1
            return []
        if outcome == "undone":
            for rec in s.commits:
                if rec[0] == ref_unit and rec[2] != "irreversible":
                    rec[4] = True
                    s.stats["undone"] += 1
            return []
        if outcome == "cancelled":
            if s.pending is not None and s.pending[0] == ref_unit:
                s.pending = None
            return []
        # confirmed / selected: an explicit choice from another channel
        if ref_unit not in s.offers:
            s.stats["ignored_events"] += 1
            return []
        offered = s.offers.pop(ref_unit)
        iid = ev.get("intent") if outcome == "selected" else (s.pending[1] if s.pending and s.pending[0] == ref_unit else None)
        if iid is None or iid not in offered:
            s.stats["ignored_events"] += 1
            return []
        if self._role(iid) == "null":
            return []
        if s.pending is not None and s.pending[0] == ref_unit:
            s.pending = None
        risk = self.config.risk_of(iid, s.declared.get(iid))
        if risk == "irreversible":
            s.stats["confirmed"] += 1
        d = self._emit(s, alloc, t0, True, ref, action="COMMIT", p_top1=None, risk_class=risk, threshold=None,
                       reason=f"explicit {outcome} by {ev.get('source', 'user')}", intent=iid, role=self._role(iid),
                       confirmation_of=ref_unit, confirmed_via="feedback")
        s.commits.append([d.unit, iid, risk, ev.get("t"), False])
        return [d]


# ---------------------------------------------------------------------------
# Replay helper and command line
# ---------------------------------------------------------------------------


def replay(config: IntentTrustConfig, events: Iterable[dict[str, Any]], session_id: str = "default") -> list[IntentDecision]:
    layer = IntentTrustLayer(config)
    out: list[IntentDecision] = []
    for ev in events:
        out += layer.push(ev, session_id)
    s = layer._sessions.get(session_id)
    if s is not None and s.header is not None and not s.ended:
        out += layer.push({"type": "end"}, session_id)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m fidetype.trust.intent replay --config icfg.json stream.jsonl`` -> trust_decision JSON Lines."""
    import argparse
    import sys

    from fidetype.trust.streaming import iter_events

    ap = argparse.ArgumentParser(prog="fidetype intent", description="FEP-0003 intent trust layer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="run the intent trust layer on JSON Lines streams; print trust_decision lines")
    r.add_argument("--config", required=True, help="intent trust configuration (JSON, icfg-...)")
    r.add_argument("streams", nargs="+")
    r.add_argument("--finals-only", action="store_true")
    a = ap.parse_args(list(argv) if argv is not None else None)
    cfg = IntentTrustConfig.load(a.config)
    rc = 0
    for path in a.streams:
        try:
            for d in replay(cfg, iter_events(path), session_id=Path(path).stem):
                if d.final or not a.finals_only:
                    print(json.dumps(d.to_event(), ensure_ascii=False))
        except (IntentEventError, ValueError) as e:
            print(f"{path}: {e}", file=sys.stderr)
            rc = 1
    return rc


__all__ = [
    "DECLARATION_KEY", "DEFAULT_ALPHA", "FEEDBACK_OUTCOMES", "INTENT", "INTENT_FEEDBACK", "PROFILE",
    "RISK_CLASSES", "ROLES", "IntentChoice", "IntentDecision", "IntentEventError", "IntentPolicy",
    "IntentSpec", "IntentTrustConfig", "IntentTrustLayer", "IntentVocabulary", "calibrate",
    "candidates_to_probs", "class_calibration_data", "evaluate_policy", "fit_intent_config", "norm_entropy", "replay",
    "stricter", "validate_feedback_event", "validate_intent_declaration", "validate_intent_event",
]

if __name__ == "__main__":
    raise SystemExit(main())
