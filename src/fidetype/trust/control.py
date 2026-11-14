"""Continuous-control trust layer (FEP-0005 draft, P12-03).

The control profile carries continuous decoder output (1-3 axes of velocity
or position) with an optional uncertainty. The trust layer turns each
decoder tick into one actuation command (a ``trust_decision`` with
``profile = "control"``). It only ever **removes** motion:

1. **Conformal shrinkage.** The decoder sends ``std`` (one value per axis).
   A frozen configuration holds a split-conformal quantile ``q`` of the
   score ``||v - v_hat|| / max(std)`` at level ``1 - alpha``. The radius is
   ``r = q * max(std)``. The gated velocity is the point of the ball
   ``B(v_hat, r)`` closest to zero: ``v_hat * max(0, 1 - r / ||v_hat||)``.
   If the ball covers the true velocity, the output is never faster than
   the true velocity and points within ``asin(r / ||v_hat||)`` of it.
2. **No-signal gates.** HOLD when the latest ``signal_quality`` index is
   below ``min_quality``; HOLD when ``||v_hat - v_ns|| <= r`` (``v_ns`` is
   the decoder output on all-zero input, the *no-signal reference*).
3. **Unscored input.** Without ``std`` the gain is ``unscored_gain``
   (default 0: no motion without uncertainty).
4. **Hand-off and clamps.** After an engage (``control_enable``,
   ``enabled = true``) the decoder authority ramps from 0 to 1 over
   ``handoff_s``; a human channel (``control`` events with
   ``source = "human"``) fills the rest. Speed <= ``v_max``; change per tick
   <= ``a_max * dt``; the output is then rescaled so that it is never
   faster than the gated target (stops are never delayed).
5. **Dead-man.** Motion needs an engage. ``enabled = false`` is a latched
   STOP until the next engage. Each decision carries ``ttl_s``: a bridge
   MUST NOT apply a velocity after ``t + ttl_s``. :meth:`ControlTrustLayer.poll`
   emits a HOLD when the input is stale.
6. **Discrete events.** A click is a FEP-0003 intent (``click_intent``).
   An optional :class:`~fidetype.trust.intent.IntentTrustLayer` decides it
   (shared ``seq``). No intent COMMIT while the control is not engaged.

The module also holds the structural validators used by the ``fep-0005``
conformance profile, and the fit helpers (:func:`conformal_quantile`,
:func:`fit_control_config`).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

DECLARATION_KEY = "control_declaration"
CONTROL = "control"
CONTROL_ENABLE = "control_enable"
PROFILE = "control"
TRUST_DECISION = "trust_decision"

QUANTITIES = ("velocity", "position")
UNITS = {
    "velocity": ("norm/s", "px/s", "mm/s", "m/s", "deg/s"),
    "position": ("norm", "px", "mm", "m", "deg"),
}
#: screen: x right, y down, origin top-left (OS / HID convention).
#: workspace: x right, y up, z towards the user (right-handed), origin declared by the producer.
FRAMES = ("screen", "workspace")
UNCERTAINTY = ("none", "std")
SOURCES = ("decoder", "human")
STATES = ("act", "attenuate", "hold", "stop")
ENABLE_SOURCES = ("switch", "caregiver", "ui", "voice", "eye-tracker", "watchdog", "other")
#: Machine-readable reason codes of a control decision.
REASONS = ("ok", "shrunk", "uncertain", "no_signal", "no_signal_reference", "unscored", "disengaged",
           "not_engaged", "stale_input", "absent", "handoff", "clamp_speed", "clamp_accel")
TIMING_FIELDS = ("t_signal_start", "t_signal_end", "t_decoded", "t_emitted")


class ControlEventError(ValueError):
    """A control-profile event breaks a FEP-0005 MUST rule."""


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Declaration and event validation (structural MUST rules, FEP-0005 sections 2-4)
# ---------------------------------------------------------------------------


def validate_control_declaration(d: Any, intent_ids: Sequence[str] | None = None,
                                 null_intents: Sequence[str] = ()) -> list[str]:
    """Errors of a ``control_declaration`` (FEP-0005 section 2). Empty list = valid.

    ``intent_ids``: the intents of the header's FEP-0003 declaration (None = no declaration).
    """
    if not isinstance(d, dict):
        return ["control_declaration must be an object"]
    e: list[str] = []
    dims = d.get("dims")
    if not (_int(dims) and 1 <= dims <= 3):
        e.append("dims must be an integer 1-3")
    q = d.get("quantity")
    if q not in QUANTITIES:
        e.append(f"quantity {q!r} is not one of {list(QUANTITIES)}")
    elif d.get("units") not in UNITS[q]:
        e.append(f"units {d.get('units')!r} do not fit quantity {q!r} (one of {list(UNITS[q])})")
    if d.get("frame") not in FRAMES:
        e.append(f"frame {d.get('frame')!r} is not one of {list(FRAMES)}")
    if not (_num(d.get("rate_hz")) and d["rate_hz"] > 0):
        e.append("rate_hz must be a number > 0")
    if "axes" in d:
        ax = d["axes"]
        if not (isinstance(ax, list) and all(isinstance(a, str) and a for a in ax) and len(set(ax)) == len(ax)
                and (not _int(dims) or len(ax) == dims)):
            e.append("axes must be a list of dims unique non-empty strings")
    if d.get("uncertainty", "none") not in UNCERTAINTY:
        e.append(f"uncertainty {d.get('uncertainty')!r} is not one of {list(UNCERTAINTY)}")
    for k in ("max_speed", "latency_s", "window_s"):
        if k in d and not (_num(d[k]) and d[k] >= 0 and (k != "max_speed" or d[k] > 0)):
            e.append(f"{k} must be a number {'> 0' if k == 'max_speed' else '>= 0'}")
    if q == "position" and d.get("units") == "norm" and d.get("frame") != "screen":
        e.append("normalised position (units norm) is defined only in the screen frame")
    if "click_intent" in d:
        ci = d["click_intent"]
        if not isinstance(ci, str):
            e.append("click_intent must be a string")
        elif intent_ids is None:
            e.append("click_intent needs an intent_declaration (FEP-0003) in the same header")
        elif ci not in intent_ids:
            e.append(f"click_intent {ci!r} is not a declared intent")
        elif ci in null_intents:
            e.append(f"click_intent {ci!r} has role null")
    return e


@dataclass(frozen=True)
class ControlDeclaration:
    dims: int
    quantity: str
    units: str
    frame: str
    rate_hz: float
    uncertainty: str = "none"
    axes: tuple[str, ...] = ()
    max_speed: float | None = None
    latency_s: float | None = None
    window_s: float | None = None
    click_intent: str | None = None

    @classmethod
    def from_declaration(cls, d: dict[str, Any]) -> "ControlDeclaration":
        errs = validate_control_declaration(d, intent_ids=[d["click_intent"]] if isinstance(d.get("click_intent"), str) else None)
        if errs:
            raise ControlEventError("; ".join(errs) + " (FEP-0005 section 2)")
        dims = int(d["dims"])
        return cls(dims, d["quantity"], d["units"], d["frame"], float(d["rate_hz"]), d.get("uncertainty", "none"),
                   tuple(d.get("axes") or ("x", "y", "z")[:dims]), d.get("max_speed"), d.get("latency_s"),
                   d.get("window_s"), d.get("click_intent"))

    def to_declaration(self) -> dict[str, Any]:
        out: dict[str, Any] = {"dims": self.dims, "quantity": self.quantity, "units": self.units, "frame": self.frame,
                               "rate_hz": self.rate_hz, "uncertainty": self.uncertainty, "axes": list(self.axes)}
        for k in ("max_speed", "latency_s", "window_s", "click_intent"):
            if getattr(self, k) is not None:
                out[k] = getattr(self, k)
        return out


def validate_control_event(ev: dict[str, Any], decl: ControlDeclaration | None) -> list[str]:
    """Errors of one ``control`` event (FEP-0005 section 3), without the order rules."""
    e: list[str] = []
    if decl is None:
        return ["control event without a control_declaration in the header (rule 1)"]
    if not _num(ev.get("t")):
        e.append("t must be a finite number")
    if not (_int(ev.get("tick")) and ev["tick"] >= 0):
        e.append("tick must be an integer >= 0")
    vals = ev.get("values")
    if not (isinstance(vals, list) and len(vals) == decl.dims):
        e.append(f"values must be a list of dims = {decl.dims} numbers")
        vals = None
    absent = ev.get("absent")
    if absent is not None and not (isinstance(absent, list) and len(absent) == decl.dims and all(isinstance(a, bool) for a in absent)):
        e.append("absent must be a list of dims booleans")
        absent = None
    if vals is not None:
        for j, v in enumerate(vals):
            if absent is not None and absent[j]:
                continue
            if not _num(v):
                e.append(f"values[{j}] must be a finite number (or absent)")
    src = ev.get("source", "decoder")
    if src not in SOURCES:
        e.append(f"source {src!r} is not one of {list(SOURCES)}")
    if "std" in ev:
        sd = ev["std"]
        if not (isinstance(sd, list) and len(sd) == decl.dims and all(_num(x) and x > 0 for x in sd)):
            e.append("std must be a list of dims numbers > 0")
        elif decl.uncertainty != "std":
            e.append("std given but the declaration has uncertainty = none (rule 3)")
    elif decl.uncertainty == "std" and src == "decoder":
        e.append("the declaration has uncertainty = std: a decoder control event MUST carry std (rule 3)")
    ts = [ev[k] for k in TIMING_FIELDS if k in ev]
    if any(not _num(x) for x in ts):
        e.append("timing fields must be finite numbers")
    elif ts != sorted(ts):
        e.append("timing fields must satisfy t_signal_start <= t_signal_end <= t_decoded <= t_emitted (v0.1 3.8)")
    if "id" in ev and not isinstance(ev["id"], str):
        e.append("id must be a string")
    return e


def validate_enable_event(ev: dict[str, Any]) -> list[str]:
    e = []
    if not isinstance(ev.get("enabled"), bool):
        e.append("enabled must be a boolean")
    if "t" in ev and not _num(ev["t"]):
        e.append("t must be a finite number")
    if "source" in ev and ev["source"] not in ENABLE_SOURCES:
        e.append(f"source {ev['source']!r} is not one of {list(ENABLE_SOURCES)}")
    if "reason" in ev and not isinstance(ev["reason"], str):
        e.append("reason must be a string")
    return e


# ---------------------------------------------------------------------------
# Frozen configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlTrustConfig:
    """A frozen control trust configuration (JSON, content id ``ccfg-...``).

    ``q``: conformal quantile of ``||v - v_hat|| / max(std)`` at ``level``
    (None = no calibration: every scored tick is treated as unscored).
    ``no_signal_output``: decoder output on all-zero input (None = no
    reference gate). Velocities are in the declared ``units``.
    """

    dims: int = 2
    units: str = "mm/s"
    frame: str = "workspace"
    level: float = 0.9
    q: float | None = None
    v_max: float = math.inf
    a_max: float = math.inf
    min_quality: float | None = None
    no_signal_output: tuple[float, ...] | None = None
    unscored_gain: float = 0.0
    handoff_s: float = 1.0
    ttl_ticks: int = 3
    stale_ticks: int = 3
    require_engage: bool = True
    name: str = ""
    fit: dict[str, Any] = field(default_factory=dict)

    def _payload(self) -> dict[str, Any]:
        f = lambda x: None if x is None or not math.isfinite(x) else float(x)  # noqa: E731
        return {"schema": "fidetype.control-config/1", "dims": self.dims, "units": self.units, "frame": self.frame,
                "level": float(self.level), "q": f(self.q), "v_max": f(self.v_max), "a_max": f(self.a_max),
                "min_quality": f(self.min_quality),
                "no_signal_output": None if self.no_signal_output is None else [float(x) for x in self.no_signal_output],
                "unscored_gain": float(self.unscored_gain), "handoff_s": float(self.handoff_s),
                "ttl_ticks": int(self.ttl_ticks), "stale_ticks": int(self.stale_ticks),
                "require_engage": bool(self.require_engage)}

    @property
    def config_id(self) -> str:
        return "ccfg-" + hashlib.sha256(_canonical(self._payload()).encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "name": self.name, "config_id": self.config_id, "fit": self.fit}

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ControlTrustConfig":
        g = lambda k, dflt: dflt if d.get(k) is None else d[k]  # noqa: E731
        cfg = cls(int(d["dims"]), d["units"], d["frame"], float(d["level"]),
                  None if d.get("q") is None else float(d["q"]), float(g("v_max", math.inf)),
                  float(g("a_max", math.inf)), None if d.get("min_quality") is None else float(d["min_quality"]),
                  None if d.get("no_signal_output") is None else tuple(float(x) for x in d["no_signal_output"]),
                  float(d.get("unscored_gain", 0.0)), float(d.get("handoff_s", 1.0)), int(d.get("ttl_ticks", 3)),
                  int(d.get("stale_ticks", 3)), bool(d.get("require_engage", True)), d.get("name", ""), d.get("fit") or {})
        if "config_id" in d and d["config_id"] != cfg.config_id:
            raise ValueError(f"config_id {d['config_id']!r} does not match the content ({cfg.config_id!r})")
        return cfg

    @classmethod
    def load(cls, path: str | Path) -> "ControlTrustConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def conformal_quantile(scores: np.ndarray, level: float) -> float:
    """Split-conformal quantile: the ceil((n+1) * level)-th smallest score (inf if n is too small)."""
    s = np.sort(np.asarray(scores, dtype=float).ravel())
    n = len(s)
    k = int(math.ceil((n + 1) * level))
    return math.inf if k > n or n == 0 else float(s[k - 1])


def conformal_scores(v_true: np.ndarray, v_hat: np.ndarray, std: np.ndarray | None) -> np.ndarray:
    """Normalised scores ``||v - v_hat|| / max(std)`` (std None: plain ``||v - v_hat||``)."""
    res = np.linalg.norm(np.asarray(v_true, float) - np.asarray(v_hat, float), axis=-1)
    if std is None:
        return res
    sd = np.asarray(std, float)
    return res / (sd.max(axis=-1) if sd.ndim > 1 else sd)


def fit_control_config(v_true_cal: np.ndarray, v_hat_cal: np.ndarray, std_cal: np.ndarray | None, *,
                       level: float = 0.9, units: str = "mm/s", frame: str = "workspace",
                       v_max: float = math.inf, a_max: float = math.inf, min_quality: float | None = None,
                       no_signal_output: Sequence[float] | None = None, name: str = "",
                       **kw: Any) -> ControlTrustConfig:
    """Fit ``q`` on labelled calibration ticks; freeze the other settings."""
    v_hat_cal = np.asarray(v_hat_cal, float)
    sc = conformal_scores(v_true_cal, v_hat_cal, std_cal)
    q = conformal_quantile(sc, level)
    fit = {"n_cal": int(len(sc)), "q": None if not math.isfinite(q) else q, "level": level,
           "score": "norm(v - v_hat) / max(std)" if std_cal is not None else "norm(v - v_hat)"}
    return ControlTrustConfig(dims=int(v_hat_cal.shape[1]), units=units, frame=frame, level=level,
                              q=q if math.isfinite(q) else None, v_max=v_max, a_max=a_max, min_quality=min_quality,
                              no_signal_output=None if no_signal_output is None else tuple(float(x) for x in no_signal_output),
                              name=name, fit=fit, **kw)


# ---------------------------------------------------------------------------
# The per-tick policy (pure function; used by the layer and by batch evaluation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Gated:
    """The gate result of one tick, before hand-off and clamps."""

    velocity: np.ndarray
    radius: float | None
    reasons: tuple[str, ...]


def gate(config: ControlTrustConfig, v_hat: np.ndarray, std: np.ndarray | None, quality: float | None) -> Gated:
    """Steps 1-3 of the module docstring for one tick."""
    v = np.asarray(v_hat, float)
    zero = np.zeros_like(v)
    if config.min_quality is not None and quality is not None and quality < config.min_quality:
        return Gated(zero, None, ("no_signal",))
    if std is None or config.q is None:
        g = float(config.unscored_gain)
        return Gated(v * g if g > 0 else zero, None, ("unscored",))
    r = float(config.q * float(np.max(std)))
    if config.no_signal_output is not None:
        if float(np.linalg.norm(v - np.asarray(config.no_signal_output))) <= r:
            return Gated(zero, r, ("no_signal_reference",))
    sp = float(np.linalg.norm(v))
    if sp <= r:
        return Gated(zero, r, ("uncertain",))
    return Gated(v * (1.0 - r / sp), r, ("shrunk",))


def gate_batch(config: ControlTrustConfig, v_hat: np.ndarray, std: np.ndarray | None,
               quality: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised :func:`gate`: (gated velocities T x D, radius T). No hand-off, no clamps."""
    v = np.asarray(v_hat, float)
    T = len(v)
    if std is None or config.q is None:
        out = v * float(config.unscored_gain)
        r = np.full(T, np.nan)
    else:
        sd = np.asarray(std, float)
        r = config.q * (sd.max(axis=1) if sd.ndim > 1 else sd)
        sp = np.linalg.norm(v, axis=1)
        gain = np.where(sp > r, 1.0 - r / np.maximum(sp, 1e-300), 0.0)
        out = v * gain[:, None]
        if config.no_signal_output is not None:
            near = np.linalg.norm(v - np.asarray(config.no_signal_output)[None, :], axis=1) <= r
            out[near] = 0.0
    if config.min_quality is not None and quality is not None:
        out[np.asarray(quality) < config.min_quality] = 0.0
    return out, r


def clamp(config: ControlTrustConfig, target: np.ndarray, prev: np.ndarray, dt: float) -> tuple[np.ndarray, list[str]]:
    """Speed clamp, change-per-tick clamp, then never faster than the target. Zero target -> zero at once."""
    tgt = np.asarray(target, float)
    notes: list[str] = []
    sp = float(np.linalg.norm(tgt))
    if sp == 0.0:
        return np.zeros_like(tgt), notes
    if sp > config.v_max:
        tgt = tgt * (config.v_max / sp)
        sp = config.v_max
        notes.append("clamp_speed")
    out = tgt
    if math.isfinite(config.a_max) and dt > 0:
        d = tgt - prev
        dn = float(np.linalg.norm(d))
        lim = config.a_max * dt
        if dn > lim:
            out = prev + d * (lim / dn)
            notes.append("clamp_accel")
            on = float(np.linalg.norm(out))
            if on > sp:
                out = out * (sp / on)
    return out, notes


# ---------------------------------------------------------------------------
# Decisions and the streaming layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlDecision:
    """One control decision (a ``trust_decision`` with ``profile = "control"``)."""

    session_id: str
    seq: int
    tick: int
    t: float | None
    state: str
    velocity: tuple[float, ...]
    raw: tuple[float, ...] | None
    gain: float
    reasons: tuple[str, ...]
    radius: float | None
    level: float | None
    authority: float
    engagement: int
    v_max: float | None
    ttl_s: float
    units: str
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        return "COMMIT" if self.state in ("act", "attenuate") else "ABSTAIN"

    @property
    def acts(self) -> bool:
        return self.action == "COMMIT"

    def to_event(self) -> dict[str, Any]:
        r6 = lambda x: round(float(x), 6)  # noqa: E731
        ev: dict[str, Any] = {
            "type": TRUST_DECISION, "profile": PROFILE, "session": self.session_id, "seq": self.seq,
            "tick": self.tick, "is_final": True, "action": self.action, "state": self.state,
            "velocity": [r6(x) for x in self.velocity], "gain": r6(self.gain), "units": self.units,
            "reason": ",".join(self.reasons), "reasons": list(self.reasons),
            "p_top1": None, "score_semantics": "calibrated_prob" if self.radius is not None else "none",
            "authority": r6(self.authority), "engagement": self.engagement, "ttl_s": r6(self.ttl_s),
            "v_max": None if self.v_max is None or not math.isfinite(self.v_max) else r6(self.v_max),
        }
        if self.t is not None:
            ev["t"] = r6(self.t)
        if self.raw is not None:
            ev["raw"] = [r6(x) for x in self.raw]
        if self.radius is not None:
            ev["radius"] = r6(self.radius)
            ev["level"] = self.level
        for k in ("config_id", "input", "latency_s"):
            if k in self.provenance:
                ev[k] = self.provenance[k]
        return ev


@dataclass
class _CSession:
    id: str
    decl: ControlDeclaration | None = None
    engaged: bool = False
    stopped: bool = False
    engagement: int = 0
    t_engage: float | None = None
    prev: np.ndarray | None = None
    last_tick: int | None = None
    last_t: float | None = None
    last_input_clock: float | None = None
    quality: float | None = None
    human: tuple[np.ndarray, float] | None = None
    seq: int = 0
    ended: bool = False
    stale_reported: bool = False
    stats: dict[str, int] = field(default_factory=lambda: {s: 0 for s in STATES} | {"ticks": 0, "clicks_blocked": 0})


class ControlTrustLayer:
    """Streaming control trust layer: ``push(event) -> [decisions]``.

    Control decisions are :class:`ControlDecision`; with ``intent=`` the
    FEP-0003 intent decisions (``IntentDecision``) share the ``seq``
    counter.
    """

    def __init__(self, config: ControlTrustConfig, intent: Any = None, clock: Callable[[], float] | None = None,
                 max_sessions: int = 256) -> None:
        if not (math.isfinite(config.v_max) and config.v_max > 0):
            raise ValueError("the configuration needs a finite v_max > 0 (FEP-0005 section 6 rule 3: bounded velocity)")
        self.config = config
        self.intent = intent
        self.clock = clock or time.perf_counter
        self.max_sessions = max_sessions
        self._sessions: dict[str, _CSession] = {}

    def _session(self, sid: str) -> _CSession:
        s = self._sessions.get(sid)
        if s is None:
            if len(self._sessions) >= self.max_sessions:
                raise ControlEventError(f"too many sessions (max_sessions = {self.max_sessions})")
            s = self._sessions[sid] = _CSession(sid)
        return s

    def stats(self, session_id: str = "default") -> dict[str, int]:
        return dict(self._sessions[session_id].stats)

    def _alloc(self, s: _CSession) -> Callable[[], int]:
        def nxt() -> int:
            s.seq += 1
            return s.seq - 1
        return nxt

    def push(self, event: dict[str, Any] | str | bytes, session_id: str = "default") -> list[Any]:
        t0 = self.clock()
        ev = json.loads(event) if isinstance(event, (str, bytes)) else event
        if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
            raise ControlEventError("event must be a JSON object with a string type")
        s = self._session(session_id)
        typ = ev["type"]
        if typ == "header":
            return self._header(s, ev, t0)
        if s.decl is None and typ in (CONTROL, CONTROL_ENABLE, "pointer"):
            raise ControlEventError(f"{typ!r} event before a header with a control_declaration")
        if s.ended:
            return []
        if typ == CONTROL:
            return self._control(s, ev, t0)
        if typ == "pointer":
            return self._control(s, self._from_pointer(s, ev), t0)
        if typ == CONTROL_ENABLE:
            return self._enable(s, ev, t0)
        if typ == "signal_quality":
            if ev.get("unit") == "index" and _num(ev.get("value")):
                s.quality = float(ev["value"])
            out: list[Any] = []
        elif typ == "end":
            out = self._stop(s, ev.get("t"), ("disengaged",), t0) if s.engaged else []
            s.ended = True
        else:
            out = []
        if self.intent is not None and typ in ("intent", "intent_feedback", "decision", "segment_end", "end",
                                                "signal_quality"):
            out += self._intent(s, ev)
        return out

    # --- routes -------------------------------------------------------------------------

    def _header(self, s: _CSession, ev: dict[str, Any], t0: float) -> list[Any]:
        out: list[Any] = []
        if s.engaged:
            out = self._stop(s, s.last_t, ("disengaged",), t0)
        d = ev.get(DECLARATION_KEY)
        decl = None
        if d is not None:
            from fidetype.trust.intent import DECLARATION_KEY as IDK, validate_intent_declaration

            idecl = ev.get(IDK)
            ids = nulls = None
            if isinstance(idecl, dict) and not validate_intent_declaration(idecl):
                ids = [it["id"] for it in idecl["intents"]]
                nulls = [it["id"] for it in idecl["intents"] if it.get("role") == "null"]
            errs = validate_control_declaration(d, ids, nulls or ())
            if errs:
                raise ControlEventError("; ".join(errs) + " (FEP-0005 section 2)")
            decl = ControlDeclaration.from_declaration(d)
            if decl.quantity != "velocity":
                raise ControlEventError("the reference layer actuates velocity streams only (quantity = velocity)")
            if decl.dims != self.config.dims or decl.units != self.config.units:
                raise ControlEventError(f"the stream ({decl.dims} axes, {decl.units}) does not match the configuration "
                                        f"({self.config.dims} axes, {self.config.units})")
        s.decl = decl
        s.engaged = not self.config.require_engage and decl is not None
        s.stopped = False
        s.t_engage = None
        s.prev, s.last_tick, s.last_t, s.quality, s.human, s.ended = None, None, None, None, None, False
        if s.engaged:
            s.engagement += 1
        if self.intent is not None:
            out += self._intent(s, ev)
        return out

    def _intent(self, s: _CSession, ev: dict[str, Any]) -> list[Any]:
        decs = self.intent.push(ev, s.id, seq_alloc=self._alloc(s))
        out = []
        for d in decs:
            if d.final and d.action == "COMMIT" and not s.engaged:
                s.stats["clicks_blocked"] += 1
                d = replace(d, action="ABSTAIN", intent=None, confirmation_of=None, confirmed_via=None, undo_of=None,
                            reason="control not engaged: no discrete action (FEP-0005 section 6 rule 7); " + d.reason)
            out.append(d)
        return out

    def _from_pointer(self, s: _CSession, ev: dict[str, Any]) -> dict[str, Any]:
        """A v0.1 ``pointer`` (relative) as an unscored control event: velocity = values * rate_hz."""
        assert s.decl is not None
        if ev.get("mode") != "relative" or ev.get("dims") != s.decl.dims:
            raise ControlEventError("the reference layer maps only relative pointer events with the declared dims")
        tick = 0 if s.last_tick is None else s.last_tick + 1
        vals = [float(x) * s.decl.rate_hz for x in ev.get("values", [])]
        out = {"type": CONTROL, "t": ev.get("t"), "tick": tick, "values": vals}
        if "absent" in ev:
            out["absent"] = ev["absent"]
        return out

    def _enable(self, s: _CSession, ev: dict[str, Any], t0: float) -> list[Any]:
        errs = validate_enable_event(ev)
        if errs:
            raise ControlEventError("; ".join(errs) + " (FEP-0005 section 4)")
        t = ev.get("t", s.last_t)
        if ev["enabled"]:
            if not s.engaged:
                s.engaged, s.stopped = True, False
                s.engagement += 1
                s.t_engage = t
                s.prev = None
            return []
        return self._stop(s, t, ("disengaged",), t0)

    def _stop(self, s: _CSession, t: Any, reasons: tuple[str, ...], t0: float) -> list[Any]:
        s.engaged, s.stopped = False, True
        s.prev = None
        return [self._emit(s, s.last_tick if s.last_tick is not None else 0, t, "stop", None, None, reasons, None, 0.0,
                           {"kind": "control_enable"}, t0)]

    def _authority(self, s: _CSession, t: float | None) -> float:
        if self.config.handoff_s <= 0:
            return 1.0
        if s.t_engage is None:
            s.t_engage = t
        if t is None or s.t_engage is None:
            return 1.0
        return float(min(1.0, max(0.0, (t - s.t_engage) / self.config.handoff_s)))

    def _control(self, s: _CSession, ev: dict[str, Any], t0: float) -> list[Any]:
        assert s.decl is not None
        errs = validate_control_event(ev, s.decl)
        if errs:
            raise ControlEventError("; ".join(errs) + " (FEP-0005 section 3)")
        if ev.get("source", "decoder") == "human":
            s.human = (np.array([float(x) for x in ev["values"]]), float(ev["t"]))
            return []
        tick, t = int(ev["tick"]), float(ev["t"])
        if s.last_tick is not None and tick <= s.last_tick:
            raise ControlEventError(f"tick {tick} does not increase (FEP-0005 section 3 rule 2)")
        if s.last_t is not None and t <= s.last_t:
            raise ControlEventError(f"t {t} does not increase (FEP-0005 section 3 rule 2)")
        dt = t - s.last_t if s.last_t is not None else 1.0 / s.decl.rate_hz
        s.last_tick, s.last_t, s.last_input_clock, s.stale_reported = tick, t, t0, False
        s.stats["ticks"] += 1
        absent = ev.get("absent") or [False] * s.decl.dims
        raw = np.array([0.0 if a else float(v) for v, a in zip(ev["values"], absent)])
        ref = {"kind": CONTROL, "tick": tick, "sha256": _sha({k: v for k, v in ev.items() if not k.startswith("_")})}
        if not s.engaged:
            return [self._emit(s, tick, t, "stop" if s.stopped else "hold", raw, None, ("not_engaged",), None, 0.0, ref, t0)]
        if any(absent):
            return [self._emit(s, tick, t, "hold", raw, None, ("absent",), None, self._authority(s, t), ref, t0)]
        std = np.array(ev["std"], float) if "std" in ev else None
        g = gate(self.config, raw, std, s.quality)
        a = self._authority(s, t)
        target = a * g.velocity
        reasons = list(g.reasons)
        if a < 1.0:
            reasons.append("handoff")
            if s.human is not None and t - s.human[1] <= self.config.stale_ticks / s.decl.rate_hz:
                target = target + (1.0 - a) * s.human[0]
        prev = s.prev if s.prev is not None else np.zeros_like(raw)
        v, notes = clamp(self.config, target, prev, dt)
        reasons += notes
        s.prev = v
        sp_raw = float(np.linalg.norm(raw))
        gain = float(np.linalg.norm(v) / sp_raw) if sp_raw > 0 else 0.0
        if not np.any(v):
            state = "hold"
        elif gain >= 1.0 - 1e-9 and "shrunk" not in reasons and a >= 1.0:
            state = "act"
        else:
            state = "attenuate"
        return [self._emit(s, tick, t, state, raw, v, tuple(reasons), g.radius, a, ref, t0, gain=min(gain, 1.0) if state != "act" else 1.0)]

    def poll(self, session_id: str = "default", now: float | None = None) -> list[ControlDecision]:
        """Dead-man check: one HOLD decision when no decoder tick came for ``stale_ticks`` periods."""
        s = self._sessions.get(session_id)
        if s is None or s.decl is None or s.last_input_clock is None or not s.engaged or s.stale_reported:
            return []
        now = self.clock() if now is None else now
        if now - s.last_input_clock <= self.config.stale_ticks / s.decl.rate_hz:
            return []
        s.stale_reported = True
        s.prev = None
        return [self._emit(s, s.last_tick or 0, s.last_t, "hold", None, None, ("stale_input",), None,
                           self._authority(s, s.last_t), {"kind": "timer"}, now)]

    def _emit(self, s: _CSession, tick: int, t: Any, state: str, raw: np.ndarray | None, v: np.ndarray | None,
              reasons: tuple[str, ...], radius: float | None, authority: float, ref: dict[str, Any], t0: float,
              gain: float = 0.0) -> ControlDecision:
        dims = s.decl.dims if s.decl is not None else self.config.dims
        vel = tuple(float(x) for x in v) if v is not None and state in ("act", "attenuate") else (0.0,) * dims
        s.stats[state] += 1
        rate = s.decl.rate_hz if s.decl is not None else 50.0
        prov = {"config_id": self.config.config_id, "input": ref, "latency_s": round(max(0.0, self.clock() - t0), 6)}
        return ControlDecision(s.id, self._alloc(s)(), int(tick), None if t is None else float(t), state, vel,
                               None if raw is None else tuple(float(x) for x in raw), gain if state in ("act", "attenuate") else 0.0,
                               reasons, radius, self.config.level if radius is not None else None, authority,
                               s.engagement, self.config.v_max, self.config.ttl_ticks / rate, self.config.units, prov)


def replay(config: ControlTrustConfig, events: Iterable[dict[str, Any]], session_id: str = "default",
           intent: Any = None) -> list[Any]:
    layer = ControlTrustLayer(config, intent=intent)
    out: list[Any] = []
    for ev in events:
        out += layer.push(ev, session_id)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m fidetype.trust.control replay --config ccfg.json stream.jsonl`` -> trust_decision JSON Lines."""
    import argparse
    import sys

    def iter_events(path: str):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)

    ap = argparse.ArgumentParser(prog="fidetype control", description="FEP-0005 control trust layer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="run the control trust layer on JSON Lines streams; print trust_decision lines")
    r.add_argument("--config", required=True, help="control trust configuration (JSON, ccfg-...)")
    r.add_argument("streams", nargs="+")
    a = ap.parse_args(list(argv) if argv is not None else None)
    cfg = ControlTrustConfig.load(a.config)
    rc = 0
    for path in a.streams:
        try:
            for d in replay(cfg, iter_events(path), session_id=Path(path).stem):
                print(json.dumps(d.to_event(), ensure_ascii=False))
        except (ControlEventError, ValueError) as e:
            print(f"{path}: {e}", file=sys.stderr)
            rc = 1
    return rc


__all__ = [
    "CONTROL", "CONTROL_ENABLE", "DECLARATION_KEY", "FRAMES", "PROFILE", "QUANTITIES", "REASONS", "STATES", "UNITS",
    "ControlDeclaration", "ControlDecision", "ControlEventError", "ControlTrustConfig", "ControlTrustLayer", "Gated",
    "clamp", "conformal_quantile", "conformal_scores", "fit_control_config", "gate", "gate_batch", "replay",
    "validate_control_declaration", "validate_control_event", "validate_enable_event",
]

if __name__ == "__main__":
    raise SystemExit(main())
