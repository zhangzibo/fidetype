"""The trust layer as a drop-in wrapper for any decoder (P14-03).

Bring your own decoder output. Get COMMIT / OFFER / WITHHOLD decisions
with a stated wrong-commit guarantee and an audit log. You do not need
to know the NeuralTextStream (NTS) format: this module writes valid NTS
underneath and runs the normal trust layer on it.

::

    import fidetype.trust as ft

    guard = ft.calibrate(cal_logits, cal_texts, vocab=VOCAB, lexicon=WORDS)  # your labelled data
    print(guard.sheet)                        # the guarantee sheet
    r = guard.decide(new_logits)              # r.action: "commit" | "offer" | "withhold"
    guard.write_audit("audit.jsonl")          # one trust_decision record per decision
    guard.save("guard.json")                  # reload with ft.load("guard.json")

Two input kinds
---------------
``logits``
    One ``(T, V)`` matrix per utterance: CTC scores per output frame
    (logits, log-probabilities or probabilities; numpy or torch). Give
    the token list ``vocab`` (column order) and the ``blank`` column. The
    matrix goes through :mod:`fidetype.adapters.ctc_logits` (an NTS
    stream). The default text decoder is a CTC prefix beam search without
    a language model. Give it a word list (``lexicon``), or pass your own
    ``decode_fn`` (for example your beam search with a language model).
    Without either, the shuffled control usually refuses: shuffled
    frames keep their confidence, so an LM-free decoder writes confident
    nonsense.
``nbest``
    One n-best list per utterance, best first: strings, ``(text, score)``
    pairs or dicts with ``text``, ``score`` and optional
    ``char_confidences``. Scores are log-domain (higher is better). The
    lists go through :mod:`fidetype.adapters.text_nbest` (an NTS
    hypothesis-only stream).

What calibration does
---------------------
:func:`calibrate` follows the existing recipe. It adds no new trust maths:

1. A random split of the labelled items (seed ``seed``): 25 % fit the
   temperatures and the conformal threshold, 37.5 % fit the policy grid,
   37.5 % calibrate ``commit_p`` with Learn then Test (exact binomial
   p-values, ``alpha``, ``delta``, combined with the grid value by
   ``max``). This is the Paper 1 v4 recipe
   (:func:`~fidetype.trust.frozen.paper1_v4_harness_config`).
2. The M2-18 commit gate is always on (``min_chars 1``,
   ``max_guard_risk 1.0``): no empty COMMIT and no COMMIT at guard risk
   1.0. A gate only removes commits, so the bound still holds.
3. The null controls of the 2026-11-15 re-tune rule run automatically:
   a **uniform** (no-signal) control and a **shuffled** control. If the
   wrapper commits on more than ``null_max_commit_rate`` of the control
   inputs (default: ``alpha``), :func:`calibrate` raises
   :class:`NullControlError` and returns no guard.

The guarantee is stated in :class:`GuaranteeSheet`. Read
``docs/trust-guarantee.md`` before you rely on it.

Licence: our own code, Apache-2.0. See ``docs/trust-quickstart.md``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config
from fidetype.trust.policy import Action
from fidetype.trust.types import NBest, from_lm_hypotheses

__all__ = [
    "GUARD_SCHEMA",
    "COMMIT_GATE",
    "NullControlError",
    "ControlResult",
    "GuaranteeSheet",
    "TrustResult",
    "TrustGuard",
    "calibrate",
    "wrap",
    "load",
]

#: Schema name of a saved guard file (:meth:`TrustGuard.save`).
GUARD_SCHEMA = "fidetype.trust-guard/0.1"
#: The commit gate that every drop-in guard uses (M2-18; re-tune rule of 2026-11-15).
COMMIT_GATE: dict[str, Any] = {"min_chars": 1, "min_words": 0, "max_guard_risk": 1.0}
#: Name of the built-in text decoder for logits input.
BUILTIN_DECODER = "builtin:ctc-prefix-beam-16"

InputKind = Literal["auto", "logits", "nbest"]
UserAction = Literal["commit", "offer", "withhold"]
#: Your own text decoder for logits input: ``(T, V)`` natural-log probabilities -> n-best list.
UserDecodeFn = Callable[[np.ndarray], Sequence[Any]]

_ACTION_MAP: dict[Action, UserAction] = {
    Action.COMMIT: "commit",
    Action.OFFER: "offer",
    Action.OFFER_WORDS: "offer",
    Action.ASK: "withhold",
    Action.ABSTAIN: "withhold",
}

# Split of the labelled items (fractions of n): temperatures + conformal, policy grid, LTT.
_FIT_FRACTION = 0.25
_LTT_FRACTION_OF_REST = 0.5


class NullControlError(RuntimeError):
    """Calibration refused: the wrapper commits on null (no-signal or shuffled) input.

    ``report`` holds the result of each control (a list of :class:`ControlResult`).
    No guard is returned, because a guard that commits on null input does
    not depend on the signal.
    """

    def __init__(self, message: str, report: Sequence["ControlResult"]) -> None:
        super().__init__(message)
        self.report = list(report)


@dataclass(frozen=True)
class ControlResult:
    """The result of one null control."""

    #: ``"uniform"``, ``"shuffled"`` or ``"user"`` (your own null inputs).
    name: str
    #: What the control inputs are.
    description: str
    n: int
    n_commit: int
    #: Largest number of commits that passes (``floor(rate * n)``).
    allowed: int

    @property
    def passed(self) -> bool:
        return self.n_commit <= self.allowed

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "n": self.n, "n_commit": self.n_commit,
                "allowed": self.allowed, "passed": self.passed}


@dataclass(frozen=True)
class GuaranteeSheet:
    """What the guard guarantees, how it was calibrated, and the null-control results.

    ``str(sheet)`` gives a printable text. :meth:`to_dict` gives JSON data.
    See ``docs/trust-guarantee.md`` for how to read it.
    """

    config_id: str
    input_kind: str
    decoder: str
    alpha: float
    delta: float
    method: str
    n_items: int
    n_fit: int
    n_policy: int
    n_ltt: int
    #: Smallest LTT calibration set that can certify any COMMIT (0 errors).
    n_ltt_min: int
    lambda_hat: float
    feasible: bool
    commit_threshold: float
    commit_gate: dict[str, Any]
    #: Commits and wrong commits of the final guard on the LTT items (in-sample, not a test).
    ltt_commits: int
    ltt_wrong_commits: int
    controls: tuple[ControlResult, ...]
    null_max_commit_rate: float
    seed: int
    created_utc: str
    assumptions: tuple[str, ...] = ()
    not_guaranteed: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    #: Median guard risk of the final guard on the LTT items (1.0 = the commit gate blocks almost every commit).
    ltt_median_guard_risk: float = math.nan
    #: LTT items (in-sample) whose COMMIT the commit gate blocked because of guard risk 1.0.
    ltt_gate_blocked: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["controls"] = [c.to_dict() for c in self.controls]
        for k in ("assumptions", "not_guaranteed", "warnings"):
            d[k] = list(d[k])
        for k in ("lambda_hat", "commit_threshold", "ltt_median_guard_risk"):
            d[k] = _json_float(d[k])
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "GuaranteeSheet":
        kw = dict(d)
        kw["controls"] = tuple(ControlResult(**{k: v for k, v in c.items() if k != "passed"}) for c in kw["controls"])
        for k in ("assumptions", "not_guaranteed", "warnings"):
            kw[k] = tuple(kw.get(k, ()))
        for k in ("lambda_hat", "commit_threshold", "ltt_median_guard_risk"):
            if k in kw:
                kw[k] = _float_or_inf(kw[k])
        return cls(**kw)

    def __str__(self) -> str:
        thr = "never commits (no threshold certified)" if not math.isfinite(self.commit_threshold) \
            else f"{self.commit_threshold:g}"
        lines = [
            "Fidetype trust guarantee sheet",
            "==============================",
            f"config_id            {self.config_id}",
            f"input                {self.input_kind} ({self.decoder})",
            f"guarantee            P( wrong-commit rate <= {self.alpha:g} ) >= {1 - self.delta:g}",
            f"                     wrong-commit rate = wrong COMMITs / all utterances",
            f"method               {self.method}",
            f"calibration items    {self.n_items} = {self.n_fit} fit + {self.n_policy} policy grid + {self.n_ltt} LTT",
            f"LTT items needed     >= {self.n_ltt_min} LTT items (utterances, not commits) to certify any COMMIT",
            f"lambda_hat           {_fmt(self.lambda_hat)} (feasible: {self.feasible})",
            f"commit threshold     p_top1 >= {thr}",
            f"commit gate          {json.dumps(self.commit_gate, sort_keys=True)}",
            f"LTT items (in-sample) {self.ltt_commits} commits, {self.ltt_wrong_commits} wrong "
            f"(of {self.n_ltt}; {self.ltt_gate_blocked} blocked by the commit gate; "
            f"median guard risk {_fmt(self.ltt_median_guard_risk)})",
            f"null controls        pass if commits <= floor({self.null_max_commit_rate:g} x n)",
        ]
        for c in self.controls:
            lines.append(f"  {c.name:<18} {c.n_commit}/{c.n} commits (allowed {c.allowed}): "
                         f"{'PASS' if c.passed else 'FAIL'}")
        lines.append("assumptions")
        lines += [f"  - {a}" for a in self.assumptions]
        lines.append("not guaranteed")
        lines += [f"  - {a}" for a in self.not_guaranteed]
        if self.warnings:
            lines.append("warnings")
            lines += [f"  ! {w}" for w in self.warnings]
        lines.append("Details: docs/trust-guarantee.md")
        return "\n".join(lines)


@dataclass(frozen=True)
class TrustResult:
    """One decision of a :class:`TrustGuard`."""

    #: ``"commit"`` (use ``text``), ``"offer"`` (show ``choices`` to the user) or ``"withhold"`` (show nothing).
    action: UserAction
    #: The committed text (only for ``"commit"``), else None.
    text: str | None
    #: The candidates to show (``"offer"``: the choices; ``"commit"``: the committed text).
    choices: tuple[str, ...]
    #: Calibrated probability that the top-1 text is right.
    p_top1: float
    #: Hallucination-guard risk of the top-1 text, in [0, 1].
    guard_risk: float
    #: Why the guard chose this action, in plain words. Read this field, not ``p_top1`` alone.
    #: (The policy's own reason is in ``event``.)
    reason: str
    #: The trust-layer action: ``COMMIT``, ``OFFER``, ``OFFER_WORDS``, ``ASK`` or ``ABSTAIN``.
    raw_action: str
    config_id: str
    #: Decision index in this guard (0, 1, 2, ...).
    seq: int
    #: The NTS ``trust_decision`` event (FEP-0001) of this decision.
    event: dict[str, Any] = field(repr=False, default_factory=dict)


# ---------------------------------------------------------------------------
# input handling
# ---------------------------------------------------------------------------


def _json_float(x: float) -> float | str:
    x = float(x)
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return x


def _float_or_inf(x: Any) -> float:
    if isinstance(x, str):
        return {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}[x]
    return float(x)


def _fmt(x: float) -> str:
    return f"{x:g}" if math.isfinite(x) else str(x)


def _norm_text(t: str) -> str:
    """The text normalisation of the trust core: single spaces, no edge spaces."""
    if not isinstance(t, str):
        raise TypeError(f"each true text must be a string, got {type(t).__name__}")
    return " ".join(t.split())


def _is_matrix(x: Any) -> bool:
    if hasattr(x, "shape") and hasattr(x, "ndim"):
        return int(x.ndim) == 2
    if isinstance(x, (list, tuple)) and x and isinstance(x[0], (list, tuple, np.ndarray)) and len(x[0]) > 0 \
            and isinstance(x[0][0], (int, float, np.floating, np.integer)) and not isinstance(x[0][0], bool):
        return True
    return False


def _is_nbest(x: Any) -> bool:
    if isinstance(x, str):
        return True
    if isinstance(x, (list, tuple)) and x:
        first = x[0]
        return isinstance(first, (str, Mapping)) or (isinstance(first, tuple) and len(first) == 2
                                                      and isinstance(first[0], str))
    return False


def _detect_kind(x: Any) -> str:
    if _is_matrix(x):
        return "logits"
    if _is_nbest(x):
        return "nbest"
    raise TypeError("cannot tell the input kind: give a (T, V) matrix (logits) or an n-best list "
                    "(strings, (text, score) pairs or dicts); or pass input_kind=")


def _nbest_items(x: Any) -> list[Any]:
    """An n-best input as a list of items (a single string is a 1-best list)."""
    if isinstance(x, str):
        return [x]
    items = list(x)
    if not items:
        raise ValueError("an n-best list needs at least one item")
    return items


def _nbest_from_user(items: Sequence[Any]) -> NBest:
    """Your decoder's n-best output (any item form) -> NBest, with the text_nbest checks."""
    from fidetype.adapters.text_nbest import normalise_item

    return from_lm_hypotheses([normalise_item(it) for it in items], confidence_variant=None)


def _builtin_decode(stream: NeuralTextStream) -> NBest:
    """CTC prefix beam search (beam 16, 10-best, no LM); character confidences = frame posteriors."""
    from fidetype.lm.beam import ctc_prefix_beam_search

    hyps = ctc_prefix_beam_search(stream, lm=None, beam=16, n_best=10, prune_topk=None, confidence="frame")
    return from_lm_hypotheses(hyps, confidence_variant="frame")


def _lexicon_decode(lexicon: frozenset[str]) -> Callable[[NeuralTextStream], NBest]:
    """CTC prefix beam search (beam 64, 64-best, no LM), then keep only the texts whose words are all in ``lexicon``.

    Up to 10 texts are kept. If no text is left, the n-best list is
    empty: the guard risk is 1 and the guard withholds.
    """
    from fidetype.lm.beam import ctc_prefix_beam_search

    def decode(stream: NeuralTextStream) -> NBest:
        hyps = ctc_prefix_beam_search(stream, lm=None, beam=64, n_best=64, prune_topk=None, confidence="frame",
                                      search="vector")
        nb = from_lm_hypotheses(hyps, confidence_variant="frame")
        keep = [c for c in nb.candidates if c.text and all(w in lexicon for w in c.text.split())][:10]
        return NBest(keep, dict(nb.stream_meta))

    return decode


def _decode_fn_for(user_fn: UserDecodeFn | None,
                   lexicon: Sequence[str] | None = None) -> Callable[[NeuralTextStream], NBest]:
    if user_fn is None:
        return _lexicon_decode(frozenset(lexicon)) if lexicon else _builtin_decode

    def decode(stream: NeuralTextStream) -> NBest:
        out = user_fn(np.asarray(stream.log_probs, dtype=np.float64))
        if isinstance(out, NBest):
            return out
        items = list(out) if not isinstance(out, str) else [out]
        if not items:
            return NBest([])
        return _nbest_from_user(items)

    return decode


def _decoder_name(user_fn: UserDecodeFn | None, lexicon: Sequence[str] | None = None) -> str:
    if user_fn is None:
        if lexicon:
            return f"builtin:ctc-prefix-beam-64+lexicon({len(lexicon)} words)"
        return BUILTIN_DECODER
    mod = getattr(user_fn, "__module__", "?")
    qn = getattr(user_fn, "__qualname__", type(user_fn).__name__)
    return f"custom:{mod}.{qn}"


@dataclass
class _Codec:
    """Turns user input into NTS events (and streams) for one input kind."""

    kind: str
    decoder: dict[str, Any]
    vocab: Any = None  # CTCVocab for logits
    frame_period: float = 0.02
    input_scale: str = "auto"
    #: Word list of the built-in decoder (logits only; None = no lexicon).
    lexicon: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "decoder": dict(self.decoder)}
        if self.kind == "logits":
            d.update({"vocab": list(self.vocab.tokens), "blank_id": self.vocab.blank_id,
                      "vocab_type": self.vocab.vocab_type, "frame_period": self.frame_period,
                      "input_scale": self.input_scale})
            if self.lexicon:
                d["lexicon"] = list(self.lexicon)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "_Codec":
        vocab = None
        if d["kind"] == "logits":
            from fidetype.adapters.ctc_logits import CTCVocab

            vocab = CTCVocab(tuple(d["vocab"]), d["blank_id"], d.get("vocab_type", "char"))
        lex = d.get("lexicon")
        return cls(d["kind"], dict(d["decoder"]), vocab, float(d.get("frame_period", 0.02)),
                   d.get("input_scale", "auto"), tuple(lex) if lex else None)

    # --- logits ---------------------------------------------------------

    def stream(self, x: Any, input_scale: str | None = None) -> NeuralTextStream:
        from fidetype.adapters.ctc_logits import DecoderInfo, from_array

        dec = DecoderInfo(modality=self.decoder["modality"], name=self.decoder["name"],
                          version=self.decoder["version"], causal=False)
        return from_array(x, self.vocab, dec, frame_period=self.frame_period,
                          input_kind=input_scale or self.input_scale)

    @staticmethod
    def stream_events(st: NeuralTextStream) -> list[dict[str, Any]]:
        head: dict[str, Any] = {"type": "header", "spec_version": st.version, "vocab": list(st.vocab),
                                "vocab_type": st.vocab_type, "blank_id": st.blank_id, "source": st.source,
                                "meta": dict(st.meta)}
        if st.frame_period is not None:
            head["frame_period"] = st.frame_period
        if st.latency is not None:
            head["latency"] = st.latency
        ev = [head]
        ev += [{"type": "frame", "t": float(t), "log_probs": [None if v == -math.inf else float(v) for v in row]}
               for t, row in zip(st.frame_times, st.log_probs)]
        ev.append({"type": "end"})
        return ev

    # --- n-best ---------------------------------------------------------

    def nbest_events(self, x: Any, uid: str = "u1") -> list[dict[str, Any]]:
        from fidetype.adapters.text_nbest import TextDecoderInfo, Utterance, stream_events

        dec = TextDecoderInfo(modality=self.decoder["modality"], name=self.decoder["name"],
                              version=self.decoder["version"], causal=False)
        return stream_events([Utterance(_nbest_items(x), id=uid)], dec, score_semantics="none")

    def events(self, x: Any, input_scale: str | None = None) -> tuple[list[dict[str, Any]], NeuralTextStream | None]:
        if self.kind == "logits":
            st = self.stream(x, input_scale)
            return self.stream_events(st), st
        return self.nbest_events(x), None


def _nbest_of_events(events: Sequence[Mapping[str, Any]]) -> NBest:
    from fidetype.trust.streaming import nbest_from_hypothesis

    hyps = [e for e in events if e.get("type") == "hypothesis"]
    if len(hyps) != 1:
        raise ValueError("expected exactly one hypothesis event")
    return nbest_from_hypothesis(dict(hyps[0]))


def _placeholder_stream() -> NeuralTextStream:
    """A one-frame, blank-only stream: n-best items carry no frames (no frame temperature is fitted)."""
    return NeuralTextStream(log_probs=np.array([[0.0, -np.inf]], dtype=np.float32), frame_times=np.array([0.0]),
                            vocab=["<blank>", "?"], blank_id=0, source="fidetype.trust.dropin")


# ---------------------------------------------------------------------------
# the guard
# ---------------------------------------------------------------------------


class TrustGuard:
    """A calibrated trust layer for one decoder. Make it with :func:`calibrate`, :func:`wrap` or :func:`load`.

    ``guard.decide(x)`` (or ``guard(x)``) returns a :class:`TrustResult`.
    Each decision is also kept in :attr:`audit_log` (write it with
    :meth:`write_audit`). :attr:`sheet` is the guarantee sheet.
    """

    def __init__(self, config: FrozenTrustConfig, codec: _Codec, sheet: GuaranteeSheet | None = None,
                 decode_fn: UserDecodeFn | None = None, audit_text: bool = True) -> None:
        from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

        if not config.commit_gate:
            raise ValueError("a drop-in guard needs a configuration with the commit gate on")
        self.config = config
        self._codec = codec
        self.sheet = sheet
        self._user_decode = decode_fn
        self.audit_text = bool(audit_text)
        self.audit_log: list[dict[str, Any]] = []
        self._seq = 0
        frames = codec.kind == "logits"
        self._layer = StreamingTrustLayer(
            config, decode_fn=_decode_fn_for(decode_fn, codec.lexicon) if frames else None,
            streaming=StreamingConfig(route="frames" if frames else "hypothesis", max_attempts=1,
                                      provisional=False),
        )

    # --- properties -----------------------------------------------------

    @property
    def input_kind(self) -> str:
        """``"logits"`` or ``"nbest"``."""
        return self._codec.kind

    @property
    def config_id(self) -> str:
        """The content id of the frozen trust configuration (``tcfg-...``)."""
        return self.config.config_id

    @property
    def alpha(self) -> float:
        return float(self.config.risk_control.get("alpha", math.nan))

    @property
    def delta(self) -> float:
        return float(self.config.risk_control.get("delta", math.nan))

    # --- decisions ------------------------------------------------------

    def _final(self, events: Sequence[Mapping[str, Any]]) -> Any:
        self._layer.new_item("default")
        out = []
        for ev in events:
            out += self._layer.push(dict(ev), "default")
        out += self._layer.end_of_utterance("default", final_attempt=True)
        fin = [d for d in out if d.final]
        if len(fin) != 1:
            raise RuntimeError(f"expected one final decision, got {len(fin)}")
        return fin[0]

    def _result(self, sd: Any) -> TrustResult:
        d = sd.decision
        act = _ACTION_MAP[d.action]
        shown = tuple(d.shown_candidates)
        ev = sd.to_event(include_text=True)
        return TrustResult(
            action=act, text=shown[0] if act == "commit" and shown else None, choices=shown,
            p_top1=float(sd.inputs.p_top1), guard_risk=float(sd.inputs.guard_risk),
            reason=_user_reason(d.reason, float(sd.inputs.p_top1), float(sd.inputs.guard_risk),
                                float(self.config.policy.get("commit_p", math.inf))),
            raw_action=d.action.value, config_id=self.config_id, seq=self._seq, event=ev,
        )

    def _decide_quiet(self, x: Any, input_scale: str | None = None) -> TrustResult:
        """A decision that is not logged (used by calibration and the null controls)."""
        events, _ = self._codec.events(x, input_scale)
        return self._result(self._final(events))

    def decide(self, x: Any, *, utterance_id: str | None = None) -> TrustResult:
        """Decide what to do with one decoded utterance.

        ``x`` has the input kind of the calibration: a ``(T, V)`` score
        matrix (logits) or an n-best list. ``utterance_id`` is your own
        reference; it goes into the audit log only. Returns a
        :class:`TrustResult`. Use ``result.text`` only if
        ``result.action == "commit"``.
        """
        events, st = self._codec.events(x)
        sd = self._final(events)
        r = self._result(sd)
        rec: dict[str, Any] = dict(r.event)
        rec["seq"] = r.seq
        if not self.audit_text:
            rec.pop("shown", None)
        rec["user_action"] = r.action
        rec["time_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds")
        rec["input_kind"] = self.input_kind
        rec["input_sha256"] = _input_sha(events)
        if utterance_id is not None:
            rec["utterance_id"] = str(utterance_id)
        self.audit_log.append(rec)
        self._seq += 1
        return r

    __call__ = decide

    def decide_many(self, xs: Iterable[Any]) -> list[TrustResult]:
        """:meth:`decide` for each input, in order."""
        return [self.decide(x) for x in xs]

    def nts_events(self, x: Any) -> list[dict[str, Any]]:
        """The NTS events that the guard reads for input ``x`` (header first, ``end`` last).

        Write them as JSON Lines to get a valid NTS file of your decoder
        output (check it with ``fidetype.validate``).
        """
        return self._codec.events(x)[0]

    # --- audit log ------------------------------------------------------

    def audit_header(self) -> dict[str, Any]:
        """The first record of the audit log file: configuration id and guarantee sheet."""
        from fidetype import __version__

        return {"type": "audit_header", "schema": "fidetype.trust-audit/0.1", "fidetype_version": __version__,
                "config_id": self.config_id, "input_kind": self.input_kind,
                "guarantee": self.sheet.to_dict() if self.sheet is not None else None}

    def write_audit(self, path: str | PathLike[str]) -> Path:
        """Write the audit log as JSON Lines: :meth:`audit_header`, then one record per decision."""
        p = Path(path)
        lines = [self.audit_header(), *self.audit_log]
        p.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
                             for r in lines), encoding="utf-8", newline="\n")
        return p

    # --- files ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {"schema": GUARD_SCHEMA, "config": self.config.to_dict(), "input": self._codec.to_dict(),
                "decode_fn": _decoder_name(self._user_decode, self._codec.lexicon)
                if self.input_kind == "logits" else None,
                "sheet": self.sheet.to_dict() if self.sheet is not None else None}

    def save(self, path: str | PathLike[str]) -> Path:
        """Save the guard (configuration, input settings, sheet) as JSON. It holds no signal and no text."""
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
                     + "\n", encoding="utf-8", newline="\n")
        return p

    def __repr__(self) -> str:
        return (f"TrustGuard(input_kind={self.input_kind!r}, config_id={self.config_id!r}, "
                f"alpha={self.alpha:g}, delta={self.delta:g})")


_GATE_RISK_REASON = "commit blocked: low acoustic evidence"


def _user_reason(raw: str, p_top1: float, guard_risk: float, commit_p: float) -> str:
    """The policy reason in plain words for :attr:`TrustResult.reason`.

    A gated commit ("commit gate: guard risk 1.00 >= 1.00; final attempt:
    low confidence") reads as a contradiction next to ``p_top1 = 1.00``.
    This text says which check stopped the commit.
    """
    from fidetype.trust.content import REASON_PREFIX

    thr = f"{commit_p:.2f}" if math.isfinite(commit_p) else "none (never commits)"
    rest = raw
    lead = ""
    if raw.startswith(REASON_PREFIX):
        why, _, rest = raw[len(REASON_PREFIX):].partition("; ")
        if why.startswith("guard risk"):
            lead = (f"commit blocked: low acoustic evidence (guard risk {guard_risk:.2f}; the commit gate needs < "
                    f"{why.rsplit('>=', 1)[-1].strip()}) although p_top1 {p_top1:.2f}")
        else:
            lead = f"commit blocked by the commit gate ({why})"
    if rest == "final attempt: low confidence":
        tail = "withhold" if lead else (f"withhold: p_top1 {p_top1:.2f} < commit threshold {thr} and no small "
                                        "choice set")
    elif rest == "final attempt: offer top-k":
        tail = "offer the top choices" if lead else f"offer: p_top1 {p_top1:.2f} < commit threshold {thr}"
    elif rest == "no candidate":
        tail = "withhold: the decoder gave no text"
    elif rest.startswith("guard risk"):
        tail = f"withhold: low acoustic evidence ({rest})"
    else:
        tail = rest
    return f"{lead}; {tail}" if lead else tail


def _input_sha(events: Sequence[Mapping[str, Any]]) -> str:
    h = hashlib.sha256()
    for e in events:
        h.update(json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                            allow_nan=False).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def load(path: str | PathLike[str], decode_fn: UserDecodeFn | None = None, *,
         audit_text: bool = True) -> TrustGuard:
    """Load a guard saved with :meth:`TrustGuard.save`.

    If the guard was calibrated with your own ``decode_fn``, pass the
    same function again: a function cannot be stored in a file, and a
    different decoder voids the guarantee.
    """
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") != GUARD_SCHEMA:
        raise ValueError(f"not a trust guard file (schema {d.get('schema')!r}, expected {GUARD_SCHEMA!r})")
    codec = _Codec.from_dict(d["input"])
    saved = d.get("decode_fn")
    if codec.kind == "logits" and saved and not saved.startswith("builtin:") and decode_fn is None:
        raise ValueError(f"this guard was calibrated with your own decoder ({saved}); pass decode_fn= "
                         "(the same function), or the guarantee does not apply")
    sheet = GuaranteeSheet.from_dict(d["sheet"]) if d.get("sheet") else None
    return TrustGuard(FrozenTrustConfig.from_dict(d["config"]), codec, sheet, decode_fn, audit_text)


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------

_ASSUMPTIONS = (
    "Exchangeable data: the calibration utterances and the live utterances come from the same "
    "distribution (same user, device, decoder, task and session type). Use a random sample, not a hand-picked one.",
    "The decoder, its weights, the vocabulary and the decode settings do not change after calibration.",
    "The true texts are right, and they use the same text normalisation as the decoder output "
    "(the wrapper joins runs of spaces and strips the ends; nothing else).",
    "Each utterance is decided once (no repeats), and the calibration items were used for nothing else.",
)
_NOT_GUARANTEED = (
    "Any single utterance: the bound is on the rate over many utterances.",
    "A bound per session, per user or per sentence type: the bound is on the mix of the calibration data.",
    "Data that differ from the calibration data (a new day, a new electrode position, a new user, drift).",
    "The error rate among commits (precision): with few commits it can be high.",
    "The quality of offered choices, or how often the guard commits (it may commit rarely or never).",
    "Correctness of the text that the guard withholds or offers.",
    "Any medical or legal claim. Fidetype is research software, not a medical device.",
)


def _split(n: int) -> tuple[int, int, int]:
    n_fit = max(2, int(round(n * _FIT_FRACTION)))
    rest = n - n_fit
    n_ltt = int(round(rest * _LTT_FRACTION_OF_REST))
    n_pol = rest - n_ltt
    return n_fit, n_pol, n_ltt


def calibrate(
    inputs: Sequence[Any],
    texts: Sequence[str],
    *,
    alpha: float = 0.05,
    delta: float = 0.1,
    input_kind: InputKind = "auto",
    vocab: Any = None,
    blank: int | str | None = 0,
    word_delimiter: str | None = None,
    input_scale: str = "auto",
    frame_period: float = 0.02,
    decode_fn: UserDecodeFn | None = None,
    lexicon: Iterable[str] | None = None,
    null_inputs: Sequence[Any] | None = None,
    stream_texts: Sequence[str | Sequence[str]] | None = None,
    guard_settings: Mapping[str, Any] | None = None,
    null_trials: int = 300,
    null_max_commit_rate: float | None = None,
    decoder_name: str = "my-decoder",
    decoder_version: str = "0",
    modality: str = "other",
    name: str = "",
    seed: int = 0,
    audit_text: bool = True,
) -> TrustGuard:
    """Calibrate the trust layer on your labelled data. Return a :class:`TrustGuard`.

    Parameters
    ----------
    inputs
        One decoder output per labelled utterance: ``(T, V)`` score
        matrices (``input_kind="logits"``) or n-best lists
        (``input_kind="nbest"``). ``"auto"`` detects the kind.
    texts
        The true text of each utterance (what the user meant).
    alpha, delta
        The guarantee: with probability at least ``1 - delta`` over the
        calibration draw, the rate of wrong COMMITs over all utterances
        is at most ``alpha``.
    vocab, blank, word_delimiter
        Logits only. ``vocab`` is the token of each column (a list, a
        :class:`~fidetype.adapters.ctc_logits.CTCVocab`, or a path to a
        ``vocab.json`` / ``tokens.txt``). ``blank`` is the CTC blank
        column (index or token). ``word_delimiter`` (for example ``"|"``)
        is written as a space.
    input_scale
        Logits only: ``"logits"``, ``"log_probs"``, ``"probs"`` or ``"auto"``.
    frame_period
        Logits only: seconds between output frames (stream metadata only).
    decode_fn
        Logits only: your own text decoder, ``f(log_probs (T, V)) -> n-best list``
        (strings, ``(text, score)`` pairs or dicts; log-domain scores). It
        gets the frame-calibrated log-probabilities. Default: a CTC
        prefix beam search (beam 16, 10-best, no language model).
    lexicon
        Logits with the built-in decoder only: a word list. The decoder
        then keeps only texts whose words are all in the list (beam 64).
        A decoder with no language model and no lexicon usually fails the
        shuffled control, because shuffled frames keep their confidence.
    stream_texts
        Logits only, optional: the true text of each utterance in the
        token space of the decoder (a string with one character per
        token, or a list of tokens), for example the phoneme string when
        the decoder outputs phonemes and ``texts`` are words. It is used
        only to fit the frame temperature. Without it, the frame
        temperature is fitted on ``texts`` with the built-in decoder, and
        it stays 1.0 (not fitted) with your own ``decode_fn``, because
        ``texts`` can then be in another space than the tokens (the
        guarantee sheet says so).
    guard_settings
        Optional: changes to the hallucination-guard settings
        (:class:`~fidetype.trust.guard.GuardConfig` fields, for example
        ``{"low_conf_threshold": 0.3}``). Default: unchanged. The commit
        gate blocks a commit at guard risk 1.0, so a guard that is too
        strict for your decoder never commits (see the sheet warnings).
        The settings are part of the configuration and of its
        ``config_id``; the guarantee still holds.
    null_inputs
        Optional: your decoder's output on null input (for example on
        time-shuffled or no-signal recordings), in the same input kind.
        **Required for n-best input**: Fidetype does not run your decoder,
        so it cannot make a shuffled control for text. For logits input it
        is an extra control on top of the automatic ones.
    null_trials
        Number of control inputs per automatic control (drawn from the
        calibration inputs with replacement; default 300).
    null_max_commit_rate
        A control passes if the guard commits on at most
        ``floor(rate * n)`` control inputs. Default: ``alpha`` (every
        commit on null input is a wrong commit). The target is 0.
    decoder_name, decoder_version, modality
        Stream metadata (NTS ``meta``). ``modality`` is one of ``meg``,
        ``eeg``, ``emg``, ``ecog``, ``intracortical``, ``fnirs``, ``other``.
    name
        A free name for the configuration.
    seed
        Seed of the random split and of the controls.
    audit_text
        Keep the shown text in the audit log (default True). False keeps
        only actions, scores and hashes.

    Raises
    ------
    NullControlError
        The calibrated guard commits on null input more often than allowed.
        No guard is returned.
    ValueError
        Bad input (lengths differ, too few items, unknown kind, missing
        ``vocab`` or ``null_inputs``).
    """
    from fidetype.eval.harness import Item, TrustPipeline
    from fidetype.trust.session_risk import min_ltt_items

    inputs = list(inputs)
    texts = [_norm_text(t) for t in texts]
    if len(inputs) != len(texts):
        raise ValueError(f"inputs ({len(inputs)}) and texts ({len(texts)}) must have the same length")
    if len(inputs) < 20:
        raise ValueError(f"calibrate needs at least 20 labelled utterances, got {len(inputs)} "
                         f"(about {math.ceil(min_ltt_items(alpha, delta) / 0.375)} or more to certify any COMMIT)")
    if not (0.0 < alpha < 1.0 and 0.0 < delta < 1.0):
        raise ValueError("alpha and delta must be in (0, 1)")
    kind = _detect_kind(inputs[0]) if input_kind == "auto" else input_kind
    if kind not in ("logits", "nbest"):
        raise ValueError(f"input_kind must be 'auto', 'logits' or 'nbest', not {input_kind!r}")
    rate = float(alpha if null_max_commit_rate is None else null_max_commit_rate)
    if not 0.0 <= rate < 1.0:
        raise ValueError("null_max_commit_rate must be in [0, 1)")
    if null_trials < 1:
        raise ValueError("null_trials must be >= 1")
    if kind == "nbest" and not null_inputs:
        raise ValueError(
            "n-best input needs null_inputs=: your decoder's n-best output on null input, for example on "
            "time-shuffled or no-signal recordings (about 100 or more). Fidetype does not run your decoder, so it "
            "cannot make this control itself. The rule: every calibration passes a uniform and a shuffled control.")
    if kind == "nbest" and (decode_fn is not None or lexicon is not None):
        raise ValueError("decode_fn and lexicon are for logits input only")
    if stream_texts is not None:
        if kind != "logits":
            raise ValueError("stream_texts is for logits input only")
        stream_texts = [t if isinstance(t, str) else [str(x) for x in t] for t in stream_texts]
        if len(stream_texts) != len(inputs):
            raise ValueError(f"stream_texts ({len(stream_texts)}) and inputs ({len(inputs)}) must have the same length")
    if decode_fn is not None and lexicon is not None:
        raise ValueError("lexicon is for the built-in decoder; put the lexicon into your own decode_fn")
    lex = tuple(sorted({w for entry in lexicon for w in str(entry).split()})) if lexicon is not None else None
    if lex is not None and not lex:
        raise ValueError("lexicon is empty")
    from fidetype.writer import MODALITIES

    if modality not in MODALITIES:
        raise ValueError(f"modality must be one of {MODALITIES}")
    dec_meta = {"name": str(decoder_name), "version": str(decoder_version), "modality": modality}

    # --- codec and items ------------------------------------------------
    if kind == "logits":
        if vocab is None:
            raise ValueError("logits input needs vocab= (the token of each column, blank included)")
        from fidetype.adapters.ctc_logits import CTCVocab, load_vocab, vocab_from_list

        if isinstance(vocab, CTCVocab):
            cv = vocab
        elif isinstance(vocab, (str, PathLike)):
            cv = load_vocab(vocab, blank, word_delimiter=word_delimiter)
        else:
            cv = vocab_from_list(list(vocab), blank, word_delimiter=word_delimiter)
        codec = _Codec("logits", dec_meta, cv, float(frame_period), input_scale, lex)
        streams = [codec.stream(x) for x in inputs]
        decode = _decode_fn_for(decode_fn, lex)
    else:
        codec = _Codec("nbest", dec_meta)
        nbs = [_nbest_of_events(codec.nbest_events(x)) for x in inputs]
        streams = [_placeholder_stream() for _ in inputs]
        lookup = {id(s): nb for s, nb in zip(streams, nbs)}

        def decode(stream: NeuralTextStream) -> NBest:
            return lookup[id(stream)]

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(inputs))
    st_texts = stream_texts if stream_texts is not None else [None] * len(inputs)
    items = [Item(streams[i], texts[i], stream_text=st_texts[i]) for i in order]
    # The frame temperature needs the truth in the token space. With your own decode_fn the texts
    # can be in another space (words vs phonemes), so it is fitted only with stream_texts.
    frame_fit = kind == "logits" and (stream_texts is not None or decode_fn is None)
    n_fit, n_pol, n_ltt = _split(len(items))

    # --- fit (Paper 1 v4 recipe, LTT) ------------------------------------
    hc = paper1_v4_harness_config(max_wrong_commit=alpha, risk_control_delta=delta, max_attempts=1, seed=seed,
                                  risk_control_fraction=n_ltt / (n_pol + n_ltt))
    if kind == "nbest":
        hc = replace(hc, conformal_fraction=0.5)
    if not frame_fit:
        hc = replace(hc, fit_frame_temperature=False)
    if guard_settings:
        from dataclasses import fields as _fields

        known = {f.name for f in _fields(hc.guard_config)}
        bad = sorted(set(guard_settings) - known)
        if bad:
            raise ValueError(f"unknown guard_settings keys {bad}; known: {sorted(known)}")
        hc = replace(hc, guard_config=replace(hc.guard_config, **dict(guard_settings)))
    pipe = TrustPipeline(decode, hc, {})
    pipe.fit(items[:n_fit], items[n_fit:])
    recipe = dict(PAPER1_V4_RECIPE)
    recipe["risk_control"] = dict(recipe["risk_control"], alpha=alpha, delta=delta)
    recipe.update({"fitted_by": "fidetype.trust.calibrate (P14-03 drop-in)", "input_kind": kind,
                   "decoder": _decoder_name(decode_fn, lex) if kind == "logits" else "user n-best",
                   "split": {"fit": n_fit, "policy_grid": n_pol, "ltt": n_ltt, "seed": seed},
                   "commit_gate": "always on (re-tune rule 2026-11-15)",
                   "frame_temperature": ("fitted on stream_texts" if stream_texts is not None else
                                         "fitted on texts" if frame_fit else "not fitted (1.0)"),
                   "null_controls": "uniform + shuffled, automatic"})
    frozen = FrozenTrustConfig.from_pipeline(pipe, name, recipe).with_commit_gate(**COMMIT_GATE)

    guard = TrustGuard(frozen, codec, None, decode_fn if kind == "logits" else None, audit_text)

    # --- in-sample LTT check -------------------------------------------
    ltt_inputs = [inputs[i] for i in order[n_fit + n_pol:]]
    ltt_texts = [texts[i] for i in order[n_fit + n_pol:]]
    n_com = n_wrong = 0
    risks: list[float] = []
    n_blocked = 0
    for x, t in zip(ltt_inputs, ltt_texts):
        r = guard._decide_quiet(x)
        risks.append(r.guard_risk)
        n_blocked += r.reason.startswith(_GATE_RISK_REASON)
        if r.action == "commit":
            n_com += 1
            n_wrong += int(r.text != t)

    # --- null controls --------------------------------------------------
    controls = _run_controls(guard, inputs, kind, rng, null_trials, rate, null_inputs)

    rc = frozen.risk_control
    warnings: list[str] = []
    n_min = min_ltt_items(alpha, delta)
    if n_ltt < n_min:
        warnings.append(f"only {n_ltt} LTT items (< {n_min}): no threshold can be certified, so the guard never "
                        "commits. Give more labelled utterances.")
    if kind == "logits" and not frame_fit:
        warnings.append("frame temperature not fitted (1.0): with your own decode_fn, pass stream_texts= (the "
                        "truth in the decoder's token space) to fit it. The guarantee does not depend on it.")
    med_risk = float(np.median(risks)) if risks else math.nan
    can_commit = math.isfinite(float(frozen.policy.get("commit_p", math.inf)))
    if not can_commit:
        warnings.append("the guard never commits (no certified threshold). It still offers and withholds.")
    if n_blocked and n_blocked >= n_com:
        warnings.append(
            f"the commit gate blocked {n_blocked} in-sample commits for guard risk 1.00 and let {n_com} through "
            f"(median guard risk {med_risk:.2f}): the guard will commit rarely. Usual cause: low per-character confidence (frame temperature "
            f"{frozen.frame_temperature:.2f}; characters below low_conf_threshold "
            f"{hc.guard_config.low_conf_threshold:g} count as no evidence). Check the decoder's confidence on clean "
            "data, give char_confidences (n-best), or pass guard_settings={'low_conf_threshold': ...}.")
    if can_commit and n_com < n_min:
        warnings.append(
            f"only {n_com} of {n_ltt} LTT items commit in-sample (fewer than {n_min}): expect few or no commits on "
            "new data. The bound still holds.")
    sheet = GuaranteeSheet(
        config_id=frozen.config_id, input_kind=kind,
        decoder=_decoder_name(decode_fn, lex) if kind == "logits" else "your n-best lists",
        alpha=float(alpha), delta=float(delta),
        method="Learn then Test, exact binomial p-values, fixed-sequence grid 1.00 -> 0.00 step 0.01, "
               "combined with the policy-grid threshold by max",
        n_items=len(items), n_fit=n_fit, n_policy=n_pol, n_ltt=n_ltt, n_ltt_min=n_min,
        lambda_hat=float(rc.get("threshold", math.nan)), feasible=bool(rc.get("feasible", False)),
        commit_threshold=float(frozen.policy.get("commit_p", math.inf)), commit_gate=dict(frozen.commit_gate),
        ltt_commits=n_com, ltt_wrong_commits=n_wrong, controls=tuple(controls), null_max_commit_rate=rate,
        seed=int(seed), created_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        assumptions=_ASSUMPTIONS, not_guaranteed=_NOT_GUARANTEED, warnings=tuple(warnings),
        ltt_median_guard_risk=med_risk, ltt_gate_blocked=int(n_blocked),
    )
    failed = [c for c in controls if not c.passed]
    if failed:
        detail = "; ".join(f"{c.name}: {c.n_commit}/{c.n} commits, allowed {c.allowed}" for c in failed)
        hint = ""
        if kind == "logits" and decode_fn is None and lex is None and any(c.name == "shuffled" for c in failed):
            hint = (" The built-in decoder has no language model and no lexicon, so frames in a random order keep "
                    "their confidence and give confident nonsense text. Pass lexicon= (your word list) or your own "
                    "decode_fn with a language model.")
        raise NullControlError(
            f"calibration refused: the guard commits on null input ({detail}). A guard that commits without "
            "signal does not depend on your decoder's evidence." + hint + " Other checks: the inputs are per-frame "
            "scores (logits) or real n-best scores; the decoder's confidence drops on noise. "
            "No configuration was produced.", controls)
    guard.sheet = sheet
    return guard


def _run_controls(guard: TrustGuard, inputs: Sequence[Any], kind: str, rng: np.random.Generator, n_trials: int,
                  rate: float, null_inputs: Sequence[Any] | None) -> list[ControlResult]:
    idx = rng.integers(0, len(inputs), size=n_trials)
    allowed = int(math.floor(rate * n_trials + 1e-9))
    out: list[ControlResult] = []

    def count(xs: Iterable[Any], input_scale: str | None = None) -> int:
        return sum(guard._decide_quiet(x, input_scale).action == "commit" for x in xs)

    if kind == "logits":
        from fidetype.adapters.ctc_logits import to_log_probs

        V = len(guard._codec.vocab)
        scale = guard._codec.input_scale

        def uniform(x: Any) -> np.ndarray:
            T = to_log_probs(x, scale).shape[0]
            # Logits (the adapter applies log_softmax), as in fidetype.trust.guard.uniform_stream.
            return np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V))

        def shuffled(x: Any) -> np.ndarray:
            lp = to_log_probs(x, scale)
            return lp[rng.permutation(lp.shape[0])]

        n_u = count((uniform(inputs[i]) for i in idx), "logits")
        n_s = count((shuffled(inputs[i]) for i in idx), "log_probs")
        out.append(ControlResult("uniform", "near-uniform frames (log 1/V + 0.05 N(0,1)), same lengths", n_trials,
                                 n_u, allowed))
        out.append(ControlResult("shuffled", "calibration frames in a random time order", n_trials, n_s, allowed))
    else:
        def flat(x: Any) -> list[dict[str, Any]]:
            from fidetype.adapters.text_nbest import normalise_item

            its = [normalise_item(it) for it in _nbest_items(x)]
            return [{"text": it["text"], "score": 0.0} for it in its]

        n_u = count(flat(inputs[i]) for i in idx)
        out.append(ControlResult("uniform", "calibration n-best lists with equal scores and no character "
                                 "confidences (no evidence)", n_trials, n_u, allowed))
    if null_inputs:
        nl = list(null_inputs)
        a_user = int(math.floor(rate * len(nl) + 1e-9))
        out.append(ControlResult("shuffled" if kind == "nbest" else "user",
                                 "your decoder output on null input (null_inputs)", len(nl), count(nl), a_user))
    return out


def wrap(calibration_set: Iterable[tuple[Any, str]], *, alpha: float = 0.05, **kwargs: Any) -> TrustGuard:
    """Same as :func:`calibrate`, with ``(decoder output, true text)`` pairs.

    ::

        guard = fidetype.trust.wrap(zip(cal_logits, cal_texts), alpha=0.05, vocab=VOCAB)
        result = guard(new_logits)
    """
    pairs = list(calibration_set)
    if not pairs:
        raise ValueError("calibration_set is empty")
    xs, ts = zip(*pairs)
    return calibrate(list(xs), list(ts), alpha=alpha, **kwargs)
