"""Trust core module h: the streaming trust layer (M4-03).

The batch path (:class:`fidetype.eval.harness.TrustPipeline`) reads a
complete stream, decodes it and selects one action. A live system gets
the stream one event at a time. :class:`StreamingTrustLayer` consumes
NeuralTextStream events (spec v0.1, section 6.2 JSON objects) as they
arrive, keeps a state per session, and emits decisions with provenance.

::

    layer = StreamingTrustLayer(FrozenTrustConfig.load("trust.json"), decode_fn=my_decoder)
    for line in socket:                      # one JSON Lines event per message
        for d in layer.push(line, session_id="user-7"):
            ui.show(d)                       # d.final, d.action, d.shown, d.provenance
    layer.end_of_utterance("user-7")         # if the producer sends no boundary event

Two input routes
----------------
``frames``
    The layer buffers the frame rows of the current utterance. At the end
    of the utterance it builds the stream, applies the frozen frame
    temperature, calls ``decode_fn(stream) -> NBest`` and runs the trust
    core. This is exactly the batch path on the same frames.
``hypothesis``
    The decoder sends ``hypothesis`` events (n-best lists). The layer runs
    the trust core on each one. A partial hypothesis (``is_final =
    false``) gives a *provisional* decision. A final hypothesis gives the
    final decision of the utterance at once.

``route="auto"`` (default) selects ``frames`` if a ``decode_fn`` is given,
else ``hypothesis``.

Decisions
---------
Each :class:`StreamDecision` has ``final`` (bool), the policy
:class:`~fidetype.trust.policy.Decision` (COMMIT / OFFER / ASK / ABSTAIN /
OFFER_WORDS), the policy inputs, the guard score and a provenance dict.
**A consumer MUST NOT commit text from a provisional decision.** It can
show it as a preview. Only a final decision is an action.

Utterance boundaries
--------------------
An utterance ends at: a final hypothesis (hypothesis route), a
``segment_end`` event (proposed in FEP-0001), an ``end`` event, a new
``header`` event, or a call of :meth:`StreamingTrustLayer.end_of_utterance`.
An utterance with no input (no frame and no hypothesis) gives no decision.
:meth:`StreamingTrustLayer.abort_utterance` drops the pending utterance
without a decision (for example after a transport loss).

Attempts
--------
The policy needs ``final_attempt`` (ASK is not possible on the last
attempt). By default the session counts attempts: after a final ASK the
next utterance is the next attempt of the same item; after any other
final action the count goes back to 0. The last attempt is attempt
``max_attempts - 1``. :meth:`StreamingTrustLayer.new_item` resets the
count. ``end_of_utterance(final_attempt=...)`` overrides it.

Online re-calibration
---------------------
Pass an :class:`~fidetype.trust.online_risk.OnlineCommitRiskControl` as
``online``. Each session gets its own copy. Final decisions then use
:class:`~fidetype.trust.online_risk.OnlineTrustPolicy` and carry a
ticket. :meth:`StreamingTrustLayer.feedback` returns the user's final
text (or None). With ``online_floor=True`` (default) the frozen
``commit_p`` is the floor of the online threshold (``lam_min``): the
online loop can make the gate stricter than the frozen configuration,
never looser.

Bounds
------
- Memory per session: at most ``max_frames`` frame rows (the current
  utterance only), one hypothesis and ``max_pending_feedback`` tickets.
  At most ``max_sessions`` sessions. An utterance longer than
  ``max_frames`` gives a final ABSTAIN ("input too long") and the rest
  of it is dropped.
- Work per event: a frame costs O(V) (checks and one append). A final
  decision on the frame route costs one decode of at most ``max_frames``
  frames. A provisional decode on the frame route runs only every
  ``partial_every_frames`` frames (off by default).
- ``latency_budget_s``: a decision that takes longer is flagged in its
  provenance (``over_budget``). The decision itself does not change, so
  replay stays deterministic.

Equivalence with the batch path
-------------------------------
On the same input, the final decision equals the batch decision
(``TrustPipeline.analyze`` + ``policy.decide``) exactly. The tests check
this on synthetic streams and on the conformance golden vectors.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Literal, Sequence

import numpy as np

from fidetype.streams.spec import NORM_TOL, SPEC_VERSION, VOCAB_TYPES, NeuralTextStream
from fidetype.trust.conformal import PredictionSet
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.guard import GuardScore
from fidetype.trust.policy import Action, Decision, DecisionPolicy, PolicyInputs, WordSlotInfo
from fidetype.trust.types import NBest, from_lm_hypotheses

Route = Literal["auto", "frames", "hypothesis"]
DecodeFn = Callable[[NeuralTextStream], NBest]

#: Event kinds the layer reads. Others are ignored (spec 6.2 rule 5).
SEGMENT_END = "segment_end"
#: Output event kind (proposed in FEP-0001).
TRUST_DECISION = "trust_decision"


class StreamEventError(ValueError):
    """An input event breaks the spec or the layer's limits. The state is unchanged."""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamDecision:
    """One decision of the streaming layer."""

    session_id: str
    #: Decision index in the session (0, 1, 2, ...), provisional ones included.
    seq: int
    #: Utterance index in the session.
    utterance: int
    #: False: provisional (a preview, never an action).
    final: bool
    route: str
    decision: Decision
    inputs: PolicyInputs
    guard: GuardScore | None
    attempt: int
    final_attempt: bool
    ticket: Any = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> Action:
        return self.decision.action

    @property
    def shown(self) -> tuple[str, ...]:
        return self.decision.shown_candidates

    def to_event(self, include_text: bool = True) -> dict[str, Any]:
        """The decision as a ``trust_decision`` JSON event (FEP-0001)."""
        ev: dict[str, Any] = {
            "type": TRUST_DECISION,
            "session": self.session_id,
            "seq": self.seq,
            "utterance": self.utterance,
            "is_final": self.final,
            "action": self.decision.action.value,
            "reason": self.decision.reason,
            "p_top1": _json_num(self.inputs.p_top1),
            "score_semantics": "calibrated_prob",
            "set_size": self.inputs.set_size,
            "guard_risk": _json_num(self.inputs.guard_risk),
            "attempt": self.attempt,
            "final_attempt": self.final_attempt,
            "config_id": self.provenance.get("config_id"),
        }
        if include_text:
            ev["shown"] = list(self.decision.shown_candidates)
        for k in ("input", "t_signal_end", "latency_s", "ledger_decision_id"):
            if k in self.provenance:
                ev[k] = self.provenance[k]
        return ev


def _json_num(x: float) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None


# ---------------------------------------------------------------------------
# Settings and session state
# ---------------------------------------------------------------------------


@dataclass
class StreamingConfig:
    """Runtime limits and options of :class:`StreamingTrustLayer`."""

    route: Route = "auto"
    #: Frame rows kept per utterance (10 min at 40 ms frames).
    max_frames: int = 15000
    max_sessions: int = 256
    #: Attempts per item (as ``HarnessConfig.max_attempts``).
    max_attempts: int = 2
    #: Frame route: a provisional decode every N frames (None: off).
    partial_every_frames: int | None = None
    #: Hypothesis route: a provisional decision for each partial hypothesis.
    provisional: bool = True
    #: ABSTAIN while the latest ``signal_quality`` index is below this (None: off).
    min_signal_quality: float | None = None
    #: Flag decisions slower than this in their provenance (None: off).
    latency_budget_s: float | None = None
    #: Tickets kept per session; the oldest is closed as "feedback missing".
    max_pending_feedback: int = 1024
    #: The frozen commit_p is the floor of the online threshold.
    online_floor: bool = True
    #: Hash the raw stream of each final frame-route decision (SHA-256).
    fingerprint_streams: bool = True

    def __post_init__(self) -> None:
        if self.route not in ("auto", "frames", "hypothesis"):
            raise ValueError(f"unknown route {self.route!r}")
        if self.max_frames < 1 or self.max_sessions < 1 or self.max_attempts < 1:
            raise ValueError("max_frames, max_sessions and max_attempts must be >= 1")
        if self.partial_every_frames is not None and self.partial_every_frames < 1:
            raise ValueError("partial_every_frames must be >= 1 or None")


@dataclass
class _Session:
    id: str
    header: dict[str, Any] | None = None
    V: int = 0
    rows: list[np.ndarray] = field(default_factory=list)
    times: list[float] = field(default_factory=list)
    last_t: float = -math.inf
    hyp: dict[str, Any] | None = None
    hyp_nbest: NBest | None = None
    quality: float | None = None
    overflow: bool = False
    #: An ``end`` event was seen: later events are ignored until a new header (spec A5).
    ended: bool = False
    dropped_frames: int = 0
    utterance: int = 0
    attempt: int = 0
    seq: int = 0
    n_events: int = 0
    utt_first_event: int | None = None
    frames_since_partial: int = 0
    ignored_events: int = 0
    aborted_utterances: int = 0
    controller: Any = None
    online_policy: Any = None
    tickets: "OrderedDict[int, Any]" = field(default_factory=OrderedDict)
    ledger_context: str | None = None
    ledger_ids: dict[int, str] = field(default_factory=dict)

    @property
    def has_input(self) -> bool:
        return bool(self.rows) or self.hyp is not None

    def reset_utterance(self) -> None:
        self.rows = []
        self.times = []
        self.hyp = None
        self.hyp_nbest = None
        self.overflow = False
        self.utt_first_event = None
        self.frames_since_partial = 0

    def reset_stream(self) -> None:
        self.reset_utterance()
        self.header = None
        self.V = 0
        self.last_t = -math.inf
        self.quality = None
        self.ended = False


# ---------------------------------------------------------------------------
# Event parsing helpers
# ---------------------------------------------------------------------------


def _reject_constant(name: str) -> Any:
    raise StreamEventError(f"{name} is not a JSON value")


def parse_event(event: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Return the event as a dict (a JSON string is parsed)."""
    if isinstance(event, (str, bytes)):
        try:
            event = json.loads(event, parse_constant=_reject_constant)
        except ValueError as e:
            raise StreamEventError(f"event is not a JSON value: {e}") from None
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise StreamEventError('an event must be an object with a string "type"')
    return event


def _lp(x: Any) -> float:
    if x is None:
        return -math.inf
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise StreamEventError(f"{x!r} is not a number or null")
    return float(x)


def frame_row(event: dict[str, Any], V: int) -> np.ndarray:
    """The dense float64 row of a dense or sparse frame event (spec 3.3, 6.2)."""
    if "log_probs" in event:
        lp = event["log_probs"]
        if not isinstance(lp, list):
            raise StreamEventError("log_probs is not a list")
        row = np.array([_lp(x) for x in lp], dtype=np.float64)
    elif "top_ids" in event:
        ids, vals = event.get("top_ids"), event.get("top_log_probs")
        if not isinstance(ids, list) or not isinstance(vals, list) or len(ids) != len(vals):
            raise StreamEventError("sparse frame needs top_ids and top_log_probs of the same length")
        if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < V for i in ids) or len(set(ids)) != len(ids):
            raise StreamEventError("top_ids must be unique integers in 0..V-1")
        rest = _lp(event.get("rest_log_prob"))
        row = np.full(V, -math.inf)
        k = len(ids)
        if V > k and rest > -math.inf:
            row[:] = rest - math.log(V - k)
        for i, x in zip(ids, vals):
            row[i] = _lp(x)
    else:
        raise StreamEventError("frame has neither log_probs nor top_ids")
    if row.shape[0] != V:
        raise StreamEventError(f"frame has {row.shape[0]} log-probabilities, vocab has {V}")
    if np.isnan(row).any() or np.isposinf(row).any():
        raise StreamEventError("log_probs must not contain NaN or +inf")
    m = row.max() if V else -math.inf
    lse = m + math.log(np.exp(row - m).sum()) if math.isfinite(m) else -math.inf
    if not abs(lse) <= NORM_TOL:
        raise StreamEventError(f"frame log_probs must log-sum-exp to 0 (got {lse:.4g})")
    return row


def nbest_from_hypothesis(event: dict[str, Any]) -> NBest:
    """Convert a ``hypothesis`` event into an :class:`NBest`.

    Each n-best item needs ``text`` and a finite ``score``. Optional
    (FEP-0001): ``char_confidences`` (one acoustic posterior in [0, 1]
    per character; the guard reads it), ``logp_acoustic`` and
    ``logp_lm``. Duplicate texts are merged as in
    :func:`~fidetype.trust.types.from_lm_hypotheses` (best score kept).
    """
    items = event.get("nbest")
    if not isinstance(items, list):
        raise StreamEventError("hypothesis needs an nbest list")
    hyps = []
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("text"), str):
            raise StreamEventError("each nbest item needs a string text")
        sc = it.get("score")
        if isinstance(sc, bool) or not isinstance(sc, (int, float)) or not math.isfinite(sc):
            raise StreamEventError("each nbest item needs a finite numeric score")
        h: dict[str, Any] = {"text": it["text"], "score": float(sc)}
        for k in ("logp_acoustic", "logp_lm"):
            v = it.get(k)
            if v is not None:
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise StreamEventError(f"{k} must be a number")
                h[k] = float(v)
        cc = it.get("char_confidences")
        if cc is not None:
            if not isinstance(cc, list) or len(cc) != len(it["text"]):
                raise StreamEventError("char_confidences must have one value per character")
            if any(isinstance(c, bool) or not isinstance(c, (int, float)) or not 0.0 <= c <= 1.0 for c in cc):
                raise StreamEventError("char_confidences must be numbers in [0, 1]")
            h["char_confidences"] = [float(c) for c in cc]
        hyps.append(h)
    return from_lm_hypotheses(hyps, confidence_variant=None)


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The layer
# ---------------------------------------------------------------------------


class StreamingTrustLayer:
    """Streaming trust layer: ``push(event) -> [StreamDecision]`` (module docstring)."""

    def __init__(
        self,
        config: FrozenTrustConfig,
        decode_fn: DecodeFn | None = None,
        streaming: StreamingConfig | None = None,
        online: Any = None,
        ledger: Any = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.config = config
        self.components = config.build()
        self.decode_fn = decode_fn
        self.streaming = streaming or StreamingConfig()
        route = self.streaming.route
        self.route = ("frames" if decode_fn is not None else "hypothesis") if route == "auto" else route
        if self.route == "frames" and decode_fn is None:
            raise ValueError('route "frames" needs a decode_fn')
        self.online_template = online
        self.ledger = ledger
        self.clock = clock
        self.config_id = config.config_id
        self._sessions: dict[str, _Session] = {}
        self._needs_slots = bool(config.policy.get("offer_words", False))

    @classmethod
    def from_file(cls, path: str | PathLike[str], **kw: Any) -> "StreamingTrustLayer":
        return cls(FrozenTrustConfig.load(path), **kw)

    # --- sessions -----------------------------------------------------------

    def _session(self, sid: str) -> _Session:
        s = self._sessions.get(sid)
        if s is None:
            if len(self._sessions) >= self.streaming.max_sessions:
                raise StreamEventError(f"too many sessions (max_sessions = {self.streaming.max_sessions})")
            s = _Session(sid)
            if self.online_template is not None:
                from fidetype.trust.online_risk import OnlineTrustPolicy

                ctrl = copy.deepcopy(self.online_template)
                pol = self.components.policy
                if self.streaming.online_floor and isinstance(pol, DecisionPolicy) and math.isfinite(pol.config.commit_p):
                    floor = float(pol.config.commit_p)
                    ctrl.lam_min = max(ctrl.lam_min, floor)
                    if ctrl.n_obs == 0 and math.isfinite(ctrl.lam_t) and ctrl.lam_t < ctrl.lam_min:
                        ctrl.lam_t = ctrl.lam_1 = ctrl.lam_min
                        ctrl.lam_max_seen = max(ctrl.lam_max_seen, ctrl.lam_t)
                    ctrl._cache = None
                s.controller = ctrl
                s.online_policy = OnlineTrustPolicy(pol, ctrl)
            self._sessions[sid] = s
        return s

    @property
    def sessions(self) -> list[str]:
        return list(self._sessions)

    def session_state(self, session_id: str = "default") -> dict[str, Any]:
        """A small summary of one session (for monitoring)."""
        s = self._sessions[session_id]
        return {
            "has_header": s.header is not None,
            "buffered_frames": len(s.rows),
            "buffered_bytes": int(sum(r.nbytes for r in s.rows)),
            "has_hypothesis": s.hyp is not None,
            "utterance": s.utterance,
            "attempt": s.attempt,
            "decisions": s.seq,
            "events": s.n_events,
            "ignored_events": s.ignored_events,
            "dropped_frames": s.dropped_frames,
            "aborted_utterances": s.aborted_utterances,
            "pending_feedback": len(s.tickets),
            "online_threshold": None if s.controller is None else s.controller.threshold,
        }

    def new_item(self, session_id: str = "default") -> None:
        """The next utterance is the first attempt of a new item."""
        self._session(session_id).attempt = 0

    def close(self, session_id: str = "default") -> list[StreamDecision]:
        """End the pending utterance, then drop all state of the session."""
        out = self.end_of_utterance(session_id) if session_id in self._sessions else []
        s = self._sessions.pop(session_id, None)
        if s is not None and s.online_policy is not None:
            for tk in list(s.tickets.values()):
                s.online_policy.feedback(tk, None)
        return out

    def flush(self, session_id: str | None = None) -> list[StreamDecision]:
        """End the pending utterance of one session (or of all sessions)."""
        ids = list(self._sessions) if session_id is None else [session_id]
        out: list[StreamDecision] = []
        for sid in ids:
            out += self.end_of_utterance(sid)
        return out

    # --- input ----------------------------------------------------------------

    def push(self, event: dict[str, Any] | str | bytes, session_id: str = "default") -> list[StreamDecision]:
        """Consume one event. Return the decisions it causes (often none)."""
        t0 = self.clock()
        ev = parse_event(event)
        s = self._session(session_id)
        typ = ev["type"]
        out: list[StreamDecision] = []
        if typ == "header":
            out += self._end(s, None, t0)
            self._read_header(s, ev)
        elif s.header is None:
            raise StreamEventError(f"{typ!r} event before the header (spec 6.2 rule 1)")
        elif s.ended:
            s.ignored_events += 1  # lines after the end marker (spec 10, A5)
        elif typ == "frame":
            out += self._frame(s, ev, t0)
        elif typ == "hypothesis":
            out += self._hypothesis(s, ev, t0)
        elif typ == "signal_quality":
            v = ev.get("value")
            if ev.get("unit") == "index" and isinstance(v, (int, float)) and not isinstance(v, bool):
                s.quality = float(v)
        elif typ == SEGMENT_END:
            out += self._end(s, None, t0)
        elif typ == "end":
            out += self._end(s, None, t0)
            s.ended = True
        else:
            s.ignored_events += 1  # decision, pointer, unknown types (6.2 rule 5)
        s.n_events += 1
        return out

    def end_of_utterance(self, session_id: str = "default", final_attempt: bool | None = None) -> list[StreamDecision]:
        """Close the current utterance and return its final decision (if it had input)."""
        s = self._session(session_id)
        return self._end(s, final_attempt, self.clock())

    def abort_utterance(self, session_id: str = "default") -> int:
        """Drop the pending utterance **without** a decision. Return the number of frames dropped.

        Use it when the input of the utterance is incomplete, for example
        when the transport connection broke (``fidetype.adapters.lsl``). A
        decision on a part of an utterance could commit a cut text. The
        header, the attempt count and the online state stay. The next event
        starts a new utterance.
        """
        s = self._sessions.get(session_id)
        if s is None:
            return 0
        n = len(s.rows)
        if s.has_input or s.overflow:
            s.aborted_utterances += 1
        if s.overflow:
            s.utterance += 1  # its ABSTAIN was already emitted
        s.reset_utterance()
        return n

    def _read_header(self, s: _Session, ev: dict[str, Any]) -> None:
        if ev.get("spec_version") != SPEC_VERSION:
            raise StreamEventError(f"spec_version must be {SPEC_VERSION!r}, not {ev.get('spec_version')!r}")
        vocab = ev.get("vocab")
        if not isinstance(vocab, list) or not all(isinstance(t, str) for t in vocab) or len(set(vocab)) != len(vocab):
            raise StreamEventError("vocab must be a list of unique strings")
        if "blank_id" not in ev or "vocab_type" not in ev:
            raise StreamEventError("the header needs vocab_type and blank_id (spec 6.2 rule 1)")
        if ev["vocab_type"] not in VOCAB_TYPES:
            raise StreamEventError(f"vocab_type must be one of {VOCAB_TYPES}, not {ev['vocab_type']!r}")
        b = ev["blank_id"]
        if b is not None and (isinstance(b, bool) or not isinstance(b, int) or not 0 <= b < len(vocab)):
            raise StreamEventError(f"blank_id must be null or an integer in 0..{len(vocab) - 1}, not {b!r}")
        s.reset_stream()
        s.header = {k: v for k, v in ev.items() if k != "type"}
        s.V = len(vocab)

    def _mark(self, s: _Session) -> None:
        if s.utt_first_event is None:
            s.utt_first_event = s.n_events

    def _frame(self, s: _Session, ev: dict[str, Any], t0: float) -> list[StreamDecision]:
        t = ev.get("t")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise StreamEventError("frame needs a finite numeric t")
        if not t > s.last_t:
            raise StreamEventError(f"frame t {t} does not increase (last {s.last_t}; spec 6.2 rule 4)")
        row = frame_row(ev, s.V)
        s.last_t = float(t)
        if s.overflow:
            s.dropped_frames += 1
            return []
        if self.route != "frames":
            return []  # the hypothesis route does not keep frames
        self._mark(s)
        if len(s.rows) >= self.streaming.max_frames:
            s.overflow = True
            s.dropped_frames += 1
            d = Decision(Action.ABSTAIN, (), f"input too long: more than max_frames = {self.streaming.max_frames}")
            out = [self._emit(s, d, PolicyInputs((), 0.0, ()), None, True, self._final_attempt(s, None), "frames",
                              {"kind": "frames", "frame_range": [0, len(s.rows)], "overflow": True}, t0, None)]
            s.rows, s.times = [], []
            return out
        s.rows.append(row)
        s.times.append(float(t))
        p = self.streaming.partial_every_frames
        if p is not None:
            s.frames_since_partial += 1
            if s.frames_since_partial >= p:
                s.frames_since_partial = 0
                return self._decide_frames(s, final=False, final_attempt=self._final_attempt(s, None), t0=t0)
        return []

    def _hypothesis(self, s: _Session, ev: dict[str, Any], t0: float) -> list[StreamDecision]:
        hid = ev.get("id")
        if not isinstance(hid, str) or not isinstance(ev.get("is_final"), bool):
            raise StreamEventError("hypothesis needs a string id and a boolean is_final")
        nb = nbest_from_hypothesis(ev)
        if self.route != "hypothesis":
            s.ignored_events += 1
            return []
        self._mark(s)
        s.hyp, s.hyp_nbest = ev, nb  # latest wins (revision_of replaces the earlier one)
        if ev["is_final"]:
            return self._end(s, None, t0)
        if self.streaming.provisional:
            return [self._decide_nbest(s, nb, False, self._final_attempt(s, None), "hypothesis",
                                       self._hyp_ref(ev), t0, None)]
        return []

    # --- decisions --------------------------------------------------------------

    def _final_attempt(self, s: _Session, override: bool | None) -> bool:
        if override is not None:
            return bool(override)
        return s.attempt >= self.streaming.max_attempts - 1

    @staticmethod
    def _hyp_ref(ev: dict[str, Any]) -> dict[str, Any]:
        ref = {"kind": "hypothesis", "hypothesis_id": ev.get("id"), "is_final": ev.get("is_final"),
               "hypothesis_sha256": _sha({k: v for k, v in ev.items() if k != "_line"})}
        if ev.get("revision_of") is not None:
            ref["revision_of"] = ev.get("revision_of")
        for k in ("t_start", "t_end"):
            if isinstance(ev.get(k), (int, float)):
                ref[k] = float(ev[k])
        return ref

    def _end(self, s: _Session, final_attempt: bool | None, t0: float) -> list[StreamDecision]:
        if s.header is None:
            return []
        out: list[StreamDecision] = []
        fa = self._final_attempt(s, final_attempt)
        if s.overflow:
            pass  # the ABSTAIN was emitted when the limit was hit
        elif self.route == "frames" and s.rows:
            out = self._decide_frames(s, final=True, final_attempt=fa, t0=t0)
        elif self.route == "hypothesis" and s.hyp_nbest is not None:
            out = [self._decide_nbest(s, s.hyp_nbest, True, fa, "hypothesis", self._hyp_ref(s.hyp or {}), t0, None)]
        if out or s.overflow:
            s.utterance += 1
        s.reset_utterance()
        return out

    def stream_of(self, s: _Session) -> NeuralTextStream:
        """The buffered frames of the utterance as a NeuralTextStream (as the reference consumer builds it)."""
        h = s.header or {}
        lp = np.stack(s.rows) if s.rows else np.zeros((0, s.V))
        return NeuralTextStream(
            log_probs=lp,
            frame_times=np.array(s.times, dtype=np.float64),
            vocab=list(h["vocab"]),
            blank_id=h.get("blank_id"),
            source=h.get("source", "unknown"),
            meta=dict(h.get("meta") or {}),
            version=h["spec_version"],
            vocab_type=h.get("vocab_type", "char"),
            frame_period=h.get("frame_period"),
            latency=h.get("latency"),
        )

    def _decide_frames(self, s: _Session, final: bool, final_attempt: bool, t0: float) -> list[StreamDecision]:
        assert self.decode_fn is not None
        raw_stream = self.stream_of(s)
        fs = self.components.frame_scaler
        stream = fs.transform_stream(raw_stream) if fs.temperature != 1.0 else raw_stream
        nb = self.decode_fn(stream)
        ref: dict[str, Any] = {"kind": "frames", "frame_range": [0, len(s.rows)],
                               "t_range": [s.times[0], s.times[-1]]}
        if final and self.streaming.fingerprint_streams:
            from fidetype.trust.provenance import stream_fingerprint

            ref["stream_sha256"] = stream_fingerprint(raw_stream)
        return [self._decide_nbest(s, nb, final, final_attempt, "frames", ref, t0, raw_stream)]

    def analyze(self, raw: NBest) -> tuple[PolicyInputs, GuardScore]:
        """The trust-core analysis of one n-best list (same steps as ``TrustPipeline.analyze``)."""
        c = self.components
        nb = c.calibrator.calibrate_chars(raw)
        post = c.calibrator.posteriors(raw)
        if math.isnan(c.conformal.q):
            pset = PredictionSet(list(range(len(raw))))
        else:
            pset = c.conformal.predict(post)
        g = c.guard.score(nb, post)
        slots: tuple = ()
        if self._needs_slots and len(nb):
            from fidetype.lm import word_alternatives  # lazy: only for OFFER_WORDS

            ws = word_alternatives(nb.candidates, posteriors=post, max_alternatives=self.config.word_max_alternatives)
            slots = tuple(WordSlotInfo(w.word, tuple(w.alternatives)) for w in ws)
        inputs = PolicyInputs(
            texts=tuple(nb.texts),
            p_top1=float(post[0]) if len(post) else 0.0,
            set_indices=tuple(pset.indices),
            includes_other=pset.includes_other,
            guard_risk=g.risk,
            word_slots=slots,
        )
        return inputs, g

    def _decide_nbest(self, s: _Session, nb: NBest, final: bool, final_attempt: bool, route: str,
                      ref: dict[str, Any], t0: float, stream: NeuralTextStream | None) -> StreamDecision:
        inputs, g = self.analyze(nb)
        ticket = None
        policy = self.components.policy
        thr = getattr(getattr(policy, "config", None), "commit_p", None)
        q = s.quality
        msq = self.streaming.min_signal_quality
        if msq is not None and q is not None and q < msq:
            d = Decision(Action.ABSTAIN, (), f"signal quality {q:.2f} < {msq:.2f}")
        elif s.online_policy is not None and final:
            d, ticket = s.online_policy.decide(inputs, final_attempt=final_attempt)
            thr = ticket.threshold
        elif s.controller is not None:
            thr = s.controller.threshold
            d = s.controller.apply(policy).decide(inputs, final_attempt=final_attempt)
        else:
            d = policy.decide(inputs, final_attempt=final_attempt)
        return self._emit(s, d, inputs, g, final, final_attempt, route, ref, t0, ticket, stream, thr)

    def _emit(self, s: _Session, d: Decision, inputs: PolicyInputs, g: GuardScore | None, final: bool,
              final_attempt: bool, route: str, ref: dict[str, Any], t0: float, ticket: Any,
              stream: NeuralTextStream | None = None, threshold: float | None = None) -> StreamDecision:
        h = s.header or {}
        lat = self.clock() - t0
        prov: dict[str, Any] = {
            "config_id": self.config_id,
            "config_name": self.config.name,
            "session": s.id,
            "utterance": s.utterance,
            "route": route,
            "input": ref,
            "events": [s.utt_first_event if s.utt_first_event is not None else s.n_events, s.n_events],
            "source": h.get("source"),
            "stream_ref": (h.get("meta") or {}).get("stream.id"),
            "commit_threshold": _json_num(threshold) if threshold is not None else None,
            "latency_s": lat,
        }
        tr = ref.get("t_range")
        if tr:
            prov["t_signal_end"] = tr[1]
        b = self.streaming.latency_budget_s
        if b is not None:
            prov["over_budget"] = lat > b
        if final and self.ledger is not None:
            prov.update(self._ledger_decision(s, d, inputs, stream, ref, final_attempt, threshold))
        sd = StreamDecision(s.id, s.seq, s.utterance, final, route, d, inputs, g, s.attempt, final_attempt, ticket, prov)
        s.seq += 1
        if final:
            if ticket is not None:
                s.tickets[sd.seq] = ticket
                while len(s.tickets) > self.streaming.max_pending_feedback:
                    _, old = s.tickets.popitem(last=False)
                    s.online_policy.feedback(old, None)
            s.attempt = s.attempt + 1 if d.action == Action.ASK else 0
        return sd

    # --- provenance ledger ----------------------------------------------------

    def _ledger_decision(self, s: _Session, d: Decision, inputs: PolicyInputs, stream: NeuralTextStream | None,
                         ref: dict[str, Any], final_attempt: bool, threshold: float | None) -> dict[str, Any]:
        from fidetype import __version__

        if s.ledger_context is None:
            ctx = {
                "software": {"package": "fidetype", "version": __version__, "component": "StreamingTrustLayer"},
                "trust_config": {"id": self.config_id, "name": self.config.name, "config": self.config.to_dict()},
                "stream_meta": dict((s.header or {}).get("meta") or {}),
                "route": self.route,
                "online": None if s.controller is None else {"method": s.controller.method, "alpha": s.controller.alpha},
            }
            s.ledger_context = self.ledger.record_context(ctx)
        kw: dict[str, Any] = {}
        if stream is not None:
            kw["stream"] = stream
            kw["stream_id"] = ref.get("stream_sha256")
        else:
            kw["stream_id"] = ref.get("hypothesis_sha256")
        e = self.ledger.record_decision(
            context_id=s.ledger_context, decision=d, inputs=inputs, attempt=s.attempt, final_attempt=final_attempt,
            item_ref=f"{s.id}/utt-{s.utterance}",
            scores={"commit_threshold": _json_num(threshold) if threshold is not None else None,
                    "route": ref.get("kind")},
            **kw,
        )
        did = e["body"]["decision_id"]
        s.ledger_ids[s.seq] = did
        return {"ledger_decision_id": did, "ledger_entry_hash": e["hash"]}

    # --- feedback -------------------------------------------------------------

    def feedback(self, decision: StreamDecision, truth: str | None) -> float | None:
        """Give the user's final text for a final decision (None: unknown).

        Feeds the online controller (if any; returns the realised loss) and
        writes a correction to the ledger (if any and the truth is known).
        """
        if not decision.final:
            raise ValueError("feedback applies to final decisions only")
        s = self._sessions.get(decision.session_id)
        if s is None:
            raise KeyError(f"unknown session {decision.session_id!r}")
        loss = None
        tk = s.tickets.pop(decision.seq, None)
        if tk is not None:
            loss = s.online_policy.feedback(tk, truth)
        did = s.ledger_ids.pop(decision.seq, None)
        if did is not None and truth is not None:
            self.ledger.record_correction(did, truth)
        return loss


# ---------------------------------------------------------------------------
# Replay: file -> events -> layer
# ---------------------------------------------------------------------------


def iter_events(path: str | PathLike[str]) -> Iterator[dict[str, Any]]:
    """Yield the events of a stream file in order.

    JSON Lines (spec 6.2): one event per non-blank line, as written.
    NPZ (spec 6.1): a header, one frame event per row, then ``end``.
    """
    p = Path(path)
    if p.suffix.lower() == ".npz":
        st = NeuralTextStream.from_npz(p)
        head: dict[str, Any] = {"type": "header", "spec_version": st.version, "vocab": list(st.vocab),
                                "vocab_type": st.vocab_type, "blank_id": st.blank_id, "source": st.source,
                                "meta": dict(st.meta)}
        if st.frame_period is not None:
            head["frame_period"] = st.frame_period
        if st.latency is not None:
            head["latency"] = st.latency
        yield head
        for t, row in zip(st.frame_times, st.log_probs):
            yield {"type": "frame", "t": float(t), "log_probs": [None if v == -math.inf else float(v) for v in row]}
        yield {"type": "end"}
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield parse_event(line)


def replay(
    source: str | PathLike[str] | Iterable[dict[str, Any] | str],
    layer: StreamingTrustLayer,
    session_id: str = "default",
    flush: bool = True,
) -> list[StreamDecision]:
    """Push every event of a file (or an iterable of events) into ``layer``.

    With ``flush`` (default) a stream that ends without an ``end`` event
    (allowed by spec 6.2 rule 6) is closed with :meth:`end_of_utterance`.
    """
    events = iter_events(source) if isinstance(source, (str, PathLike)) else source
    out: list[StreamDecision] = []
    for ev in events:
        out += layer.push(ev, session_id)
    if flush:
        out += layer.end_of_utterance(session_id)
    return out


def frame_decoder(name: str) -> DecodeFn | None:
    """A named frame decoder for the command lines: ``none``, ``greedy`` or ``demo``."""
    if name == "none":
        return None
    if name == "greedy":
        from fidetype.trust.testing import greedy_nbest

        return greedy_nbest
    if name == "demo":
        from fidetype.demo import build_decoder

        return build_decoder()
    raise ValueError(f"unknown decoder {name!r} (none, greedy or demo)")


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m fidetype.trust.streaming replay --config trust.json stream.jsonl``"""
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m fidetype.trust.streaming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="replay stream files; print trust_decision events as JSON Lines")
    r.add_argument("files", nargs="+")
    r.add_argument("--config", required=True, help="FrozenTrustConfig JSON file")
    r.add_argument("--decoder", choices=("none", "greedy", "demo"), default="none",
                   help="frame decoder: none (hypothesis route), greedy (CTC greedy, frame route) or demo "
                        "(the beam + LM decoder of fidetype.demo, frame route)")
    r.add_argument("--max-attempts", type=int, default=2, help="attempts per item (1: no ASK; default 2)")
    r.add_argument("--no-text", action="store_true", help="omit the shown texts from the output")
    a = ap.parse_args(argv)
    dec = frame_decoder(a.decoder)
    layer = StreamingTrustLayer.from_file(a.config, decode_fn=dec,
                                          streaming=StreamingConfig(max_attempts=a.max_attempts))
    for i, fp in enumerate(a.files):
        for d in replay(fp, layer, session_id=f"file-{i}"):
            sys.stdout.write(json.dumps(d.to_event(include_text=not a.no_text), ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
