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
4. The **offer null control** (P5-31) counts the OFFERs on the same
   control inputs. It passes if the null offer rate is clearly below the
   real offer rate (the rate on the LTT items): see
   :func:`offer_control`. Default ``offer_control="warn"``: the result
   is on the sheet and a failure is a sheet warning only.

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
    "GuardSession",
    "calibrate",
    "wrap",
    "load",
    "offer_control",
    "recheck_offer_control",
    "OFFER_NULL_MAX_RATIO",
    "OFFER_NULL_P",
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

#: Offer null control (P5-31): a control passes if its offer rate is at most this share of the real offer
#: rate ...
OFFER_NULL_MAX_RATIO = 0.5
#: ... and (if it offers on more control inputs than the commit allowance) a one-sided Fisher exact test
#: "null offer rate < real offer rate" gives a p-value of at most this value.
OFFER_NULL_P = 0.05

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
    #: OFFERs on the control inputs (P5-31), or None (not counted: an older sheet or ``offer_control="off"``).
    #: ``passed`` counts commits only; the offer verdict is in ``GuaranteeSheet.offers``.
    n_offer: int | None = None

    @property
    def passed(self) -> bool:
        return self.n_commit <= self.allowed

    def to_dict(self) -> dict[str, Any]:
        d = {"name": self.name, "description": self.description, "n": self.n, "n_commit": self.n_commit,
             "allowed": self.allowed, "passed": self.passed}
        if self.n_offer is not None:
            d["n_offer"] = self.n_offer  # pre-P5-31 sheets keep their bytes
        return d


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
    #: The hallucination (fluent-wrong) bound of P15-06, or None (not requested). See
    #: :mod:`fidetype.trust.halluc_bound`.
    halluc: dict[str, Any] | None = None
    #: The precision-type bound of P5-02 (error rate among commits), or None (not requested). See
    #: :mod:`fidetype.trust.precision_bound`.
    precision: dict[str, Any] | None = None
    #: The learned commit score of P5-23 (``calibrate(confidence="learned")``), or None (the score is
    #: ``p_top1``). See :mod:`fidetype.trust.commit_score`.
    confidence: dict[str, Any] | None = None
    #: The offer null control of P5-31 (:func:`offer_control`), or None (not run). It never changes
    #: ``feasible`` or the commit controls; with ``calibrate(offer_control="warn")`` a failure is a warning.
    offers: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["controls"] = [c.to_dict() for c in self.controls]
        for k in ("assumptions", "not_guaranteed", "warnings"):
            d[k] = list(d[k])
        for k in ("lambda_hat", "commit_threshold", "ltt_median_guard_risk"):
            d[k] = _json_float(d[k])
        if d.get("halluc") is None:
            d.pop("halluc", None)  # pre-P15-06 sheets keep their bytes
        if d.get("precision") is None:
            d.pop("precision", None)  # pre-P5-02 sheets keep their bytes
        if d.get("confidence") is None:
            d.pop("confidence", None)  # pre-P5-23 sheets keep their bytes
        if d.get("offers") is None:
            d.pop("offers", None)  # pre-P5-31 sheets keep their bytes
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
        prefix = bool(self.confidence) and self.confidence.get("unit") == "prefix"
        external = bool(self.confidence) and self.confidence.get("kind") == "external"  # P5-35
        score_name = ("external prefix score" if external else "learned prefix score" if prefix else
                      "learned commit score") if self.confidence else "p_top1"
        lines = [
            "Fidetype trust guarantee sheet",
            "==============================",
            f"config_id            {self.config_id}",
            f"input                {self.input_kind} ({self.decoder})",
            f"guarantee            P( wrong-commit rate <= {self.alpha:g} ) >= {1 - self.delta:g}",
            f"                     wrong-commit rate = wrong COMMITs / all utterances",
            *([f"                     a COMMIT of a prefix is wrong if its words are not the first words of the "
               f"true text; a COMMIT of all top-1 words is wrong unless it equals the true text"] if prefix else []),
            f"method               {self.method}",
            f"calibration items    {self.n_items} = {self.n_fit} fit + {self.n_policy} policy grid + {self.n_ltt} LTT",
            f"LTT items needed     >= {self.n_ltt_min} LTT items (utterances, not commits) to certify any COMMIT",
            f"lambda_hat           {_fmt(self.lambda_hat)} (feasible: {self.feasible})",
            f"commit threshold     {score_name} >= {thr}",
            f"commit gate          {json.dumps(self.commit_gate, sort_keys=True)}",
            f"LTT items (in-sample) {self.ltt_commits} commits, {self.ltt_wrong_commits} wrong "
            f"(of {self.n_ltt}; {self.ltt_gate_blocked} blocked by the commit gate; "
            f"median guard risk {_fmt(self.ltt_median_guard_risk)})",
            f"null controls        pass if commits <= floor({self.null_max_commit_rate:g} x n)",
        ]
        for c in self.controls:
            lines.append(f"  {c.name:<18} {c.n_commit}/{c.n} commits (allowed {c.allowed}): "
                         f"{'PASS' if c.passed else 'FAIL'}")
        if self.offers:
            lines += _offer_lines(self.offers)
        if self.confidence:
            cf = self.confidence
            if prefix:
                lines.append("commit unit          the longest word prefix of the top-1 text whose score passes "
                             "(prefix scores never rise with length)")
            if external:
                lines += [
                    f"commit score         external, frozen: {cf['name']!r} version {cf['version']!r} "
                    f"({cf['digest']}; in config_id)",
                    f"  fitted on          not by calibrate (frozen before calibration; see the assumptions)",
                    f"  certified on       {cf['certify_items']} LTT items ({cf.get('certify_no_score', 0)} without "
                    f"a score, {cf.get('certify_gate_blocked', 0)} blocked by the commit gate)",
                ]
        if self.confidence and not external:
            cf = self.confidence
            lines += [
                f"commit score         learned ({cf['model']}; {cf.get('n_used', '?')} of {len(cf['features'])} "
                f"features used, L2 {cf['l2']:g})",
                (f"  fitted on          {cf['fit_items']} items (fit + policy grid; {cf.get('fit_rows')} prefix rows, "
                 f"{cf['fit_positive']} right)" if prefix else
                 f"  fitted on          {cf['fit_items']} items (fit + policy grid; {cf['fit_positive']} right top-1)"),
                f"  certified on       {cf['certify_items']} LTT items, disjoint from the fit items",
                f"  features           {', '.join(cf['features'])}",
            ]
        if self.halluc:
            h = self.halluc
            sel = h.get("selected") or {}
            lines += [
                f"hallucination bound  P( fluent-wrong rate <= {h['alpha_h']:g} and wrong-commit rate <= "
                f"{self.alpha:g} ) >= {1 - h['delta_h']:g}",
                f"                     fluent-wrong rate = COMMITs that are wrong and {h['fluent_rule']} / all "
                "utterances",
                f"  method             {h['method']}",
                f"  selected           commit_p {sel.get('commit_p')}, tau_commit {sel.get('tau_commit')}, "
                f"tau_word {sel.get('tau_word')} (feasible: {h['feasible']})",
                f"  chain              {h['n_tested']} of {h['chain_length']} grid points tested, "
                f"{h['n_certified']} certified ({h['n_order']} ordering + {h['n_test']} test items)",
                f"  grounding          {h.get('grounding') or 'none'}",
            ]
        if self.precision:
            q = self.precision
            tc = q.get("test_counts") or {}
            lo = q.get("test_precision_lower")
            lines += [
                f"precision bound      P( error rate among commits <= {q['beta']:.4g} ) >= {1 - q['delta_p']:g}"
                f"  (precision >= {q['target_precision']:g})",
                "                     error rate among commits = wrong COMMITs / all COMMITs",
                f"  method             {q['method']}",
                f"  selected           commit_p {q.get('selected')} (feasible: {q['feasible']}; P14-03 commit_p "
                f"{q.get('base_commit_p')})",
                f"  chain              {q['n_tested']} of {q['chain_length']} thresholds tested, {q['n_certified']} "
                f"certified ({q['n_order']} ordering + {q['n_test']} test items)",
                f"  test commits       {tc.get('commits', 0)} commits, {tc.get('wrong', 0)} wrong"
                + (f" (precision lower bound {lo:.3f}, one-sided CP {1 - q['delta_p']:g})" if lo is not None else ""),
                f"  commits needed     >= {q['min_commits']} right test commits to certify any threshold",
                (f"  joint              wrong-commit, fluent-wrong and precision bounds hold together with "
                 f"probability >= {1 - q['delta_p']:g} (one joint test)" if q.get("joint_with") == "halluc" else
                 f"  joint              both bounds together hold with probability >= "
                 f"{max(0.0, 1 - self.delta - q['delta_p']):g}"),
            ]
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
    #: The learned commit score of this decision (P5-23, ``confidence="learned"``), else None. For a prefix
    #: guard (P5-24): the score of the committed prefix, or of the one-word prefix if nothing is committed.
    commit_score: float | None = None
    #: ``"sentence"`` (the whole top-1 text) or ``"prefix"`` (P5-24, ``commit_unit="prefix"``).
    commit_unit: str = "sentence"
    #: Words in ``text`` for a commit, else None.
    n_words_committed: int | None = None
    #: For a commit: True if it claims the whole sentence (every sentence-level commit; a prefix guard's commit
    #: of all top-1 words), False for a prefix commit; None if nothing is committed.
    complete: bool | None = None


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


def _builtin_search() -> Any:
    from fidetype.lm.beam import PrefixReuseSearch

    # frame_only: only the "frame" variant is read (P2-15: the same NBest, faster). PrefixReuseSearch (P2-16):
    # the same hypotheses as ctc_prefix_beam_search; a growing checkpoint of one utterance pushes only its new frames.
    return PrefixReuseSearch(beam=16, n_best=10, prune_topk=None, confidence="frame", frame_only=True)


_BUILTIN_SEARCH: Any = None


def _builtin_decode(stream: NeuralTextStream) -> NBest:
    """CTC prefix beam search (beam 16, 10-best, no LM); character confidences = frame posteriors."""
    global _BUILTIN_SEARCH
    if _BUILTIN_SEARCH is None:
        _BUILTIN_SEARCH = _builtin_search()
    return from_lm_hypotheses(_BUILTIN_SEARCH(stream), confidence_variant="frame")


def _lexicon_decode(lexicon: frozenset[str]) -> Callable[[NeuralTextStream], NBest]:
    """CTC prefix beam search (beam 64, 64-best, no LM), then keep only the texts whose words are all in ``lexicon``.

    Up to 10 texts are kept. If no text is left, the n-best list is
    empty: the guard risk is 1 and the guard withholds.
    """
    from fidetype.lm.beam import PrefixReuseSearch

    # frame_only: only the "frame" variant is read below (P2-15: the same NBest, faster). PrefixReuseSearch
    # (P2-16): the same hypotheses as ctc_prefix_beam_search; a growing checkpoint of one utterance (stream views,
    # streaming calibration) pushes only its new frames.
    search = PrefixReuseSearch(beam=64, n_best=64, prune_topk=None, confidence="frame", search="vector",
                               frame_only=True)

    def decode(stream: NeuralTextStream) -> NBest:
        hyps = search(stream)
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


def _decoder_name(user_fn: UserDecodeFn | None, lexicon: Sequence[str] | None = None, *,
                  stable: bool = False) -> str:
    """Label of the text decoder. ``stable=True``: without the Python module path (P5-21).

    The module path depends on how the defining script was loaded (``__main__`` when run, its import
    name when imported), so it must not enter a content id. The label with the module path is still
    shown in the guarantee sheet and the guard file (``stable=False``).
    """
    if user_fn is None:
        if lexicon:
            return f"builtin:ctc-prefix-beam-64+lexicon({len(lexicon)} words)"
        return BUILTIN_DECODER
    qn = getattr(user_fn, "__qualname__", type(user_fn).__name__)
    if stable:
        return f"custom:{qn}"
    mod = getattr(user_fn, "__module__", "?")
    return f"custom:{mod}.{qn}"


#: Values of the ``decoder_label`` argument of :func:`calibrate` (P5-21).
DECODER_LABELS = ("stable", "module")


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
    def header_event(st: NeuralTextStream) -> dict[str, Any]:
        head: dict[str, Any] = {"type": "header", "spec_version": st.version, "vocab": list(st.vocab),
                                "vocab_type": st.vocab_type, "blank_id": st.blank_id, "source": st.source,
                                "meta": dict(st.meta)}
        if st.frame_period is not None:
            head["frame_period"] = st.frame_period
        if st.latency is not None:
            head["latency"] = st.latency
        return head

    @staticmethod
    def frame_event(t: Any, row: Any) -> dict[str, Any]:
        return {"type": "frame", "t": float(t), "log_probs": [None if v == -math.inf else float(v) for v in row]}

    @staticmethod
    def stream_events(st: NeuralTextStream) -> list[dict[str, Any]]:
        ev = [_Codec.header_event(st)]
        ev += [_Codec.frame_event(t, row) for t, row in zip(st.frame_times, st.log_probs)]
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
                 decode_fn: UserDecodeFn | None = None, audit_text: bool = True, *,
                 halluc_gate: Any = None, grounding: Any = None, language: str = "en",
                 offer_gate: Any = None, prefix_score: Any = None) -> None:
        from fidetype.lang import check_tag
        from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

        if not config.commit_gate:
            raise ValueError("a drop-in guard needs a configuration with the commit gate on")
        self.config = config
        #: BCP 47 tag of the calibration text (P14-34). Saved in the guard file only if it is not ``"en"``.
        self.language = check_tag(language, "language")
        self._codec = codec
        self.sheet = sheet
        self._user_decode = decode_fn
        self.audit_text = bool(audit_text)
        self.audit_log: list[dict[str, Any]] = []
        self._seq = 0
        frames = codec.kind == "logits"
        #: P15-06 commit grounding gate (:class:`~fidetype.trust.halluc_bound.HallucGate`) and its statistics
        #: (:class:`~fidetype.trust.halluc_bound.CommitGrounding`). None: off (P14-03 behaviour).
        self.halluc_gate = None if halluc_gate is None or halluc_gate.is_off else halluc_gate
        self.grounding = grounding
        if self.halluc_gate is not None and (grounding is None or not frames):
            raise ValueError("a commit grounding gate needs grounding= and logits input")
        self._last_lp: np.ndarray | None = None
        #: Per-item statistics of the P15-06 calibration (set by :func:`calibrate`; not saved).
        self.halluc_items: dict[str, Any] | None = None
        #: Per-item statistics of the P5-02 precision calibration (set by :func:`calibrate`; not saved).
        self.precision_items: dict[str, Any] | None = None
        #: P5-23 learned commit score (:class:`~fidetype.trust.commit_score.LearnedCommitScore`), read from the
        #: frozen configuration (``recipe["commit_score"]``, so ``config_id`` covers it). None: ``p_top1``.
        self.commit_score = None
        cs = (config.recipe or {}).get("commit_score")
        if cs:
            from fidetype.trust.commit_score import LearnedCommitScore
            from fidetype.trust.external_score import EXTERNAL_PREFIX_SCHEMA, ExternalPrefixCommit

            if math.isfinite(float(config.policy.get("commit_p", math.inf))):
                raise ValueError("a configuration with a learned commit score must have commit_p = inf")
            if self.halluc_gate is not None:
                raise ValueError("a learned commit score cannot be combined with a commit grounding gate (yet)")
            if cs.get("schema") == EXTERNAL_PREFIX_SCHEMA:
                # P5-35: a frozen external prefix score; the file holds its digest, the caller gives the function
                self.commit_score = ExternalPrefixCommit.from_dict(cs, prefix_score)
            else:
                self.commit_score = LearnedCommitScore.from_dict(cs)
        if prefix_score is not None and not _is_external(self.commit_score):
            raise ValueError("prefix_score= is only for a guard calibrated with an external prefix score (P5-35)")
        #: ``"sentence"`` or ``"prefix"`` (P5-24: commit the longest certified word prefix of the top-1 text).
        self.commit_unit = self.commit_score.unit if self.commit_score is not None else "sentence"
        self._last_nb: NBest | None = None
        #: P5-33 offer gates (:class:`~fidetype.trust.offer_gate.OfferGate`, all must pass), or ``()`` (off).
        #: They change OFFER to WITHHOLD only; commits and ``config_id`` do not change.
        self.offer_gates: tuple[Any, ...] = ()
        self.set_offer_gate(offer_gate)
        #: If True, :attr:`last_offer_features` holds the offer-gate features of every decision (P5-33 analysis).
        self.collect_offer_features = False
        self.last_offer_features: dict[str, float] | None = None
        #: A character LM for the ``char_lm`` features when no gate carries one (P5-33 analysis).
        self.offer_lm: Any = None
        self._offer_gate_why: str | None = None
        self._last_score: float | None = None
        self._last_prefix: tuple[int, int] | None = None
        decode = _decode_fn_for(decode_fn, codec.lexicon) if frames else None

        def capture(stream: NeuralTextStream) -> NBest:
            # the frame-calibrated log-probabilities that the decoder sees (the grounding gate reads them)
            self._last_lp = np.asarray(stream.log_probs, dtype=np.float64)
            nb = decode(stream)
            self._last_nb = nb
            return nb

        sc = StreamingConfig(route="frames" if frames else "hypothesis", max_attempts=1, provisional=False)
        self._layer = StreamingTrustLayer(config, decode_fn=capture if frames else None, streaming=sc)
        self._nocommit_layer = None
        if self.halluc_gate is not None:
            self._nocommit_layer = StreamingTrustLayer(config.with_policy(commit_p=math.inf), decode_fn=capture,
                                                       streaming=sc)

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

    def _run_layer(self, layer: Any, events: Sequence[Mapping[str, Any]]) -> Any:
        layer.new_item("default")
        out = []
        for ev in events:
            out += layer.push(dict(ev), "default")
        out += layer.end_of_utterance("default", final_attempt=True)
        fin = [d for d in out if d.final]
        if len(fin) != 1:
            raise RuntimeError(f"expected one final decision, got {len(fin)}")
        return fin[0]

    def _final(self, events: Sequence[Mapping[str, Any]]) -> Any:
        return self._final_gated(events)[0]

    def _nb_parts(self, events: Sequence[Mapping[str, Any]]) -> tuple[Any, Any, int | None]:
        """Calibrated posteriors, calibrated candidates and frame count of the last decision (P5-23 / P5-24)."""
        if self.input_kind == "logits":
            nb, n_frames = self._last_nb, (None if self._last_lp is None else int(self._last_lp.shape[0]))
        else:
            nb, n_frames = _nbest_of_events(events), None
        if nb is None or not len(nb):
            return [], [], n_frames
        cal = self._layer.components.calibrator
        return cal.posteriors(nb), cal.calibrate_chars(nb).candidates, n_frames

    def _features(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> np.ndarray:
        """The P5-23 commit-score features of one decision (:data:`~fidetype.trust.commit_score.FEATURES`)."""
        from fidetype.trust.commit_score import commit_features

        post, cands, n_frames = self._nb_parts(events)
        return commit_features(float(sd.inputs.p_top1), float(sd.inputs.guard_risk), post, cands, n_frames)

    def _prefix_rows(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, list[str]]:
        """P5-24: the prefix features of the top-1 text (one row per word prefix) and its words."""
        from fidetype.trust.commit_score import commit_features, prefix_features

        post, cands, n_frames = self._nb_parts(events)
        f = commit_features(float(sd.inputs.p_top1), float(sd.inputs.guard_risk), post, cands, n_frames)
        rows = prefix_features(f, post, cands)
        words = str(cands[0].text).split() if len(cands) else []
        return rows, words

    def _prefix_context(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> Any:
        """P5-35: the :class:`~fidetype.trust.external_score.PrefixContext` of one decision."""
        from fidetype.trust.commit_score import commit_features, prefix_features
        from fidetype.trust.external_score import PrefixContext

        post, cands, n_frames = self._nb_parts(events)
        f = commit_features(float(sd.inputs.p_top1), float(sd.inputs.guard_risk), post, cands, n_frames)
        lp = self._last_lp if self.input_kind == "logits" else None
        return PrefixContext(words=tuple(str(cands[0].text).split()) if len(cands) else (),
                             texts=tuple(str(c.text) for c in cands), posteriors=np.asarray(post, dtype=np.float64),
                             candidates=tuple(cands), log_probs=lp, p_top1=float(sd.inputs.p_top1),
                             guard_risk=float(sd.inputs.guard_risk), n_frames=n_frames,
                             builtin_rows=prefix_features(f, post, cands))

    def _prefix_mono(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray | None, list[str]]:
        """The monotone prefix scores of the top-1 words (None: no commit possible) and the words."""
        from fidetype.trust.commit_score import monotone_prefix_scores

        cs = self.commit_score
        if _is_external(cs):  # P5-35
            ctx = self._prefix_context(sd, events)
            words = list(ctx.words)
            raw = cs.score.scores(ctx) if words else None
            return (None if raw is None or not len(raw) else monotone_prefix_scores(raw)), words
        rows, words = self._prefix_rows(sd, events)
        return (monotone_prefix_scores(cs.scores(rows)) if len(rows) else None), words

    def _prefix_commit(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> tuple[Any, float | None]:
        """Commit the longest prefix of the top-1 text whose monotone score passes (P5-24). (decision, score)."""
        from fidetype.trust.commit_score import longest_prefix
        from fidetype.trust.content import REASON_PREFIX
        from fidetype.trust.policy import Decision

        cs = self.commit_score
        self._last_prefix = None
        mono, words = self._prefix_mono(sd, events)
        if mono is None or not sd.inputs.texts:
            return sd, None
        thr = cs.threshold
        k = longest_prefix(mono, thr)
        m = len(words)
        if k == 0:
            return sd, float(mono[0])
        s = float(mono[k - 1])
        gate = self.config.gate
        why = (gate.violation(sd.inputs.texts[0], float(sd.inputs.guard_risk) if self.config.use_guard else None)
               if gate is not None else None)
        if why is not None:
            d = replace(sd.decision, reason=f"{REASON_PREFIX}{why}; {sd.decision.reason}")
            return replace(sd, decision=d), s
        text = " ".join(words[:k])
        prov = dict(sd.provenance)
        prov["commit_threshold"] = float(thr)
        self._last_prefix = (k, m)
        kind = "external" if _is_external(cs) else "learned"
        d = Decision(Action.COMMIT, (text,), f"{kind} prefix score {s:.2f} >= {thr:.2f} ({k} of {m} words)")
        return replace(sd, decision=d, provenance=prov), s

    def _learned_commit(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> tuple[Any, float]:
        """Apply the learned commit score to a no-commit decision (P5-23). Returns (decision, score)."""
        from fidetype.trust.content import REASON_PREFIX
        from fidetype.trust.policy import Decision

        cs = self.commit_score
        s = cs.score(self._features(sd, events))
        thr = cs.threshold
        if not (s >= thr) or not sd.inputs.texts:
            return sd, s
        text = sd.inputs.texts[0]
        gate = self.config.gate
        why = (gate.violation(text, float(sd.inputs.guard_risk) if self.config.use_guard else None)
               if gate is not None else None)
        if why is not None:
            d = replace(sd.decision, reason=f"{REASON_PREFIX}{why}; {sd.decision.reason}")
            return replace(sd, decision=d), s
        prov = dict(sd.provenance)
        prov["commit_threshold"] = float(thr)
        d = Decision(Action.COMMIT, (text,), f"learned commit score {s:.2f} >= {thr:.2f}")
        return replace(sd, decision=d, provenance=prov), s

    def _final_gated(self, events: Sequence[Mapping[str, Any]]) -> tuple[Any, str | None]:
        """The final decision, with the P15-06 grounding gate applied to a COMMIT (reason or None)."""
        return self._gate_final(self._run_layer(self._layer, events), events)

    # --- P5-33 offer gate ---------------------------------------------------

    def set_offer_gate(self, gate: Any) -> None:
        """Set the P5-33 offer gate: an :class:`~fidetype.trust.offer_gate.OfferGate`, a sequence of them
        (all must pass) or None (off). Commits and ``config_id`` do not change."""
        if gate is None or gate is False:
            gates: tuple[Any, ...] = ()
        elif isinstance(gate, (list, tuple)):
            gates = tuple(gate)
        else:
            gates = (gate,)
        for g in gates:
            g.check_kind(self.input_kind)
        self.offer_gates = gates

    def _offer_features(self, sd: Any, events: Sequence[Mapping[str, Any]],
                        names: Sequence[str] | None = None) -> dict[str, float]:
        """The P5-33 offer-gate features of one decision (all features of this input kind, or ``names``)."""
        from fidetype.trust import offer_gate as og

        out: dict[str, float] = {"p_top1": float(sd.inputs.p_top1), "safety": 1.0 - float(sd.inputs.guard_risk)}
        want = set(names) if names is not None else None
        if self.input_kind == "logits":
            if want is None or want & set(og.FRAME_FEATURES):
                lp = self._last_lp
                if lp is None:
                    lp = np.zeros((0, len(self._codec.vocab)))
                out.update(og.frame_features(lp, int(self._codec.vocab.blank_id or 0)))
        elif want is None or want & {"margin", "conf_mean", "char_lm", "char_lm_best"}:
            lm = next((g.lm for g in self.offer_gates if g.lm is not None), self.offer_lm)
            out.update(og.nbest_features(list(_nbest_of_events(events).candidates), lm))
        return out

    def _apply_offer_gate(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> Any:
        from fidetype.trust.policy import Decision

        self._offer_gate_why = None
        self.last_offer_features = None
        is_offer = sd.decision.action in (Action.OFFER, Action.OFFER_WORDS)
        if self.collect_offer_features:
            self.last_offer_features = self._offer_features(sd, events)
        if not (self.offer_gates and is_offer):
            return sd
        feats = self.last_offer_features or self._offer_features(sd, events, [g.feature for g in self.offer_gates])
        for g in self.offer_gates:
            why = g.violation(float(feats[g.feature]))
            if why is not None:
                self._offer_gate_why = why
                return replace(sd, decision=Decision(Action.ABSTAIN, (), f"{why}; {sd.decision.reason}"))
        return sd

    def _gate_final(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> tuple[Any, str | None]:
        """The steps of :meth:`_final_gated` after the layer's final decision ``sd`` (last: the P5-33 offer gate)."""
        sd, why = self._gate_final_commit(sd, events)
        return self._apply_offer_gate(sd, events), why

    def _gate_final_commit(self, sd: Any, events: Sequence[Mapping[str, Any]]) -> tuple[Any, str | None]:
        self._last_score = None
        self._last_prefix = None
        if self.commit_score is not None:
            if self.commit_unit == "prefix":
                sd, self._last_score = self._prefix_commit(sd, events)
            else:
                sd, self._last_score = self._learned_commit(sd, events)
            return sd, None
        if self.halluc_gate is None or sd.decision.action != Action.COMMIT:
            return sd, None
        text = sd.decision.shown_candidates[0] if sd.decision.shown_candidates else ""
        lp = self._last_lp
        st = self.grounding.stats(lp, text) if lp is not None else None
        why = "no frames" if st is None else self.halluc_gate.violation(st)
        if why is None:
            return sd, None
        return self._run_layer(self._nocommit_layer, events), why

    def _result(self, sd: Any, halluc_why: str | None = None) -> TrustResult:
        d = sd.decision
        act = _ACTION_MAP[d.action]
        shown = tuple(d.shown_candidates)
        ev = sd.to_event(include_text=True)
        score = self._last_score if self.commit_score is not None else None
        prefix = self.commit_unit == "prefix"
        if self.commit_score is not None and (score is not None or prefix):
            reason = _learned_reason(d.reason, math.nan if score is None else score,
                                     float(self.commit_score.threshold), float(sd.inputs.p_top1),
                                     float(sd.inputs.guard_risk), unit=self.commit_unit,
                                     external=_is_external(self.commit_score))
        else:
            reason = _user_reason(d.reason, float(sd.inputs.p_top1), float(sd.inputs.guard_risk),
                                  float(self.config.policy.get("commit_p", math.inf)))
        if halluc_why is not None:
            ev["config_id"] = self.config_id
            ev["reason"] = f"{_HALLUC_REASON} ({halluc_why}); {d.reason}"
            reason = f"{_HALLUC_REASON} ({halluc_why}); {reason}"
        if self._offer_gate_why is not None and d.action == Action.ABSTAIN:
            reason = f"withhold: no evidence of signal for an offer ({self._offer_gate_why})"
            ev["offer_gate"] = self._offer_gate_why
        text = shown[0] if act == "commit" and shown else None
        n_words = len(text.split()) if text is not None else None
        complete = None if text is None else True
        if prefix:
            ev["commit_unit"] = "prefix"
            if text is not None and self._last_prefix is not None:
                k, m = self._last_prefix
                complete = k == m
                ev.update(n_words_committed=k, n_words_top1=m, complete=complete)
        return TrustResult(
            action=act, text=text, choices=shown,
            p_top1=float(sd.inputs.p_top1), guard_risk=float(sd.inputs.guard_risk), reason=reason,
            raw_action=d.action.value, config_id=self.config_id, seq=self._seq, event=ev,
            commit_score=None if score is None else float(score), commit_unit=self.commit_unit,
            n_words_committed=n_words, complete=complete,
        )

    def _decide_quiet(self, x: Any, input_scale: str | None = None) -> TrustResult:
        """A decision that is not logged (used by calibration and the null controls)."""
        events, _ = self._codec.events(x, input_scale)
        return self._result(*self._final_gated(events))

    def decide(self, x: Any, *, utterance_id: str | None = None) -> TrustResult:
        """Decide what to do with one decoded utterance.

        ``x`` has the input kind of the calibration: a ``(T, V)`` score
        matrix (logits) or an n-best list. ``utterance_id`` is your own
        reference; it goes into the audit log only. Returns a
        :class:`TrustResult`. Use ``result.text`` only if
        ``result.action == "commit"``.
        """
        events, st = self._codec.events(x)
        r = self._result(*self._final_gated(events))
        self._log(r, events, utterance_id, None if r.commit_score is None else {"commit_score": r.commit_score})
        return r

    def is_right(self, result: TrustResult, truth: str) -> bool | None:
        """Whether a commit is right under this guard's loss (None if ``result`` is not a commit).

        Sentence guard: the text equals the truth (after the whitespace
        normalisation). Prefix guard (P5-24): a prefix commit is right if
        its words are the first words of the truth; a complete commit only
        if it equals the truth.
        """
        if result.action != "commit" or result.text is None:
            return None
        c, t = str(result.text).split(), str(truth).split()
        if result.commit_unit == "prefix" and result.complete is False:
            return len(t) >= len(c) and t[:len(c)] == c
        return c == t

    def _log(self, r: TrustResult, events: Sequence[Mapping[str, Any]], utterance_id: str | None,
             extra: Mapping[str, Any] | None = None, input_sha: str | None = None) -> None:
        """Append the audit record of one decision (``extra``: more keys, e.g. the online threshold).

        ``input_sha``: the hash of ``events`` if the caller has it already (:class:`GuardSession`).
        """
        rec: dict[str, Any] = dict(r.event)
        rec["seq"] = r.seq
        if not self.audit_text:
            rec.pop("shown", None)
        rec["user_action"] = r.action
        rec["time_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds")
        rec["input_kind"] = self.input_kind
        rec["input_sha256"] = _input_sha(events) if input_sha is None else input_sha
        if utterance_id is not None:
            rec["utterance_id"] = str(utterance_id)
        if extra:
            rec.update(extra)
        self.audit_log.append(rec)
        self._seq += 1

    __call__ = decide

    def session(self, *, utterance_id: str | None = None) -> "GuardSession":
        """An incremental decision for one utterance (logits input; P3-12).

        Push the rows while they arrive (``s.push(chunk)``), then call ``s.end()``.
        The result and the audit record are those of :meth:`decide` on all rows,
        but most of the work is done before the end of the utterance.
        """
        return GuardSession(self, utterance_id)

    def decide_many(self, xs: Iterable[Any]) -> list[TrustResult]:
        """:meth:`decide` for each input, in order."""
        return [self.decide(x) for x in xs]

    def nts_events(self, x: Any) -> list[dict[str, Any]]:
        """The NTS events that the guard reads for input ``x`` (header first, ``end`` last).

        Write them as JSON Lines to get a valid NTS file of your decoder
        output (check it with ``fidetype.validate``).
        """
        return self._codec.events(x)[0]

    # --- P5-02: online use and the per-policy guarantee sheets ------------

    def online(self, method: str = "aci", **kwargs: Any) -> Any:
        """An online guard that re-calibrates ``commit_p`` from feedback during use (P5-02).

        ``method``: ``"aci"`` (default), ``"aci_window"``, ``"window"`` or ``"bandit"``. See
        :func:`fidetype.trust.online_guard.online` for the arguments and the guarantee of each method.
        This guard is not changed.
        """
        if self.commit_score is not None:
            raise ValueError("online re-calibration works on p_top1; it is not available for a guard with a learned "
                             "commit score (P5-23) or prefix commits (P5-24)")
        from fidetype.trust.online_guard import online

        return online(self, method, **kwargs)

    def policy_sheets(self) -> list[Any]:
        """One uniform :class:`~fidetype.trust.guarantee_sheet.PolicySheet` per guarantee of this guard (P5-02)."""
        from fidetype.trust.guarantee_sheet import policy_sheets

        return policy_sheets(self)

    # --- audit log ------------------------------------------------------

    def audit_header(self) -> dict[str, Any]:
        """The first record of the audit log file: configuration id and guarantee sheet."""
        from fidetype import __version__

        return {"type": "audit_header", "schema": "fidetype.trust-audit/0.1", "fidetype_version": __version__,
                "config_id": self.config_id, "input_kind": self.input_kind,
                "guarantee": self.sheet.to_dict() if self.sheet is not None else None,
                **({"offer_gate": [g.to_dict() for g in self.offer_gates]} if self.offer_gates else {})}

    def write_audit(self, path: str | PathLike[str]) -> Path:
        """Write the audit log as JSON Lines: :meth:`audit_header`, then one record per decision."""
        p = Path(path)
        lines = [self.audit_header(), *self.audit_log]
        p.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
                             for r in lines), encoding="utf-8", newline="\n")
        return p

    # --- files ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = {"schema": GUARD_SCHEMA, "config": self.config.to_dict(), "input": self._codec.to_dict(),
             "decode_fn": _decoder_name(self._user_decode, self._codec.lexicon)
             if self.input_kind == "logits" else None,
             "sheet": self.sheet.to_dict() if self.sheet is not None else None}
        if self.halluc_gate is not None:
            d["halluc_gate"] = self.halluc_gate.to_dict()
            d["grounding"] = getattr(self.grounding, "name", "?")
        if self.language != "en":
            d["language"] = self.language
        if self.offer_gates:
            gs = [g.to_dict() for g in self.offer_gates]
            d["offer_gate"] = gs[0] if len(gs) == 1 else gs
        return d

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


def _is_external(cs: Any) -> bool:
    """True for a P5-35 external prefix score (:class:`~fidetype.trust.external_score.ExternalPrefixCommit`)."""
    return str(getattr(cs, "schema", "")).startswith("fidetype.external-prefix-score/")


def _learned_reason(raw: str, score: float, thr: float, p_top1: float, guard_risk: float,
                    unit: str = "sentence", external: bool = False) -> str:
    """:attr:`TrustResult.reason` for a guard with a learned commit score (P5-23) or prefix score (P5-24), or a
    frozen external prefix score (P5-35, ``external=True``)."""
    from fidetype.trust.content import REASON_PREFIX

    t = f"{thr:.2f}" if math.isfinite(thr) else "none (never commits)"
    if raw.startswith("learned commit score"):
        return f"commit: learned commit score {score:.2f} >= threshold {t} (p_top1 {p_top1:.2f})"
    if raw.startswith(("learned prefix score", "external prefix score")):
        words = raw[raw.rfind("(") + 1:raw.rfind(")")] if raw.endswith(")") else ""
        kind = raw.split(" ", 1)[0]
        return f"commit {words}: {kind} prefix score {score:.2f} >= threshold {t} (p_top1 {p_top1:.2f})"
    name = ("external prefix score" if external else "learned prefix score") if unit == "prefix" else         "learned commit score"
    if raw.startswith(REASON_PREFIX):
        why, _, rest = raw[len(REASON_PREFIX):].partition("; ")
        if why.startswith("guard risk"):
            lead = (f"commit blocked: low acoustic evidence (guard risk {guard_risk:.2f}; the commit gate needs < "
                    f"{why.rsplit('>=', 1)[-1].strip()}) although {name} {score:.2f}")
        else:
            lead = f"commit blocked by the commit gate ({why})"
        return f"{lead}; " + ("offer the top choices" if "offer" in rest else "withhold")
    if raw == "no candidate":
        return "withhold: the decoder gave no text"
    what = "offer" if ("offer" in raw or "conformal set" in raw) else "withhold"
    if math.isnan(score):
        return f"{what}: no prefix to score (p_top1 {p_top1:.2f})"
    return f"{what}: {name} {score:.2f} < threshold {t} (p_top1 {p_top1:.2f})"
_HALLUC_REASON = "commit blocked: text not grounded in the signal"


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


def _event_line(e: Mapping[str, Any]) -> bytes:
    """The canonical JSON form of one event, as the audit hash reads it."""
    return json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _input_sha(events: Sequence[Mapping[str, Any]]) -> str:
    h = hashlib.sha256()
    for e in events:
        h.update(_event_line(e))
        h.update(b"\n")
    return h.hexdigest()


class GuardSession:
    """One utterance, decided incrementally while its frames arrive (P3-12). Make it with :meth:`TrustGuard.session`.

    ``push(chunk)`` takes the next ``(n, V)`` rows of the score matrix. It does the per-frame work at once:
    the row normalisation, the frame event and its part of the audit hash. ``end()`` then gives the
    :class:`TrustResult` of ``guard.decide(all rows)`` and writes the same audit record (only
    ``time_utc`` differs), but it costs far less at the end of the utterance: the frames go to the trust layer
    in one batch (:meth:`~fidetype.trust.streaming.StreamingTrustLayer.push_frames`).

    ``push`` returns the normalised rows as the guard's stream carries them (float32 values as float64). With
    your own ``decode_fn`` (frame temperature 1.0) these are the rows that ``decode_fn`` gets at ``end()``,
    so a streaming decoder fed with them gives the same n-best list as the offline guard.

    Not incremental (``end()`` falls back to ``guard.decide``, the same result): a guard with
    ``input_scale="auto"`` (the scale is detected on the whole matrix) or with a P15-06 commit grounding gate.
    """

    def __init__(self, guard: "TrustGuard", utterance_id: str | None = None) -> None:
        if guard.input_kind != "logits":
            raise ValueError("a guard session is for logits input only")
        self._g = guard
        self._uid = utterance_id
        c = guard._codec
        self._V = len(c.vocab.tokens)
        self._incremental = c.input_scale != "auto" and guard.halluc_gate is None
        self._raw: list[np.ndarray] = []
        self._rows: list[np.ndarray] = []
        self._lines: list[bytes] = []
        self._n = 0
        self._closed = False

    @property
    def n_frames(self) -> int:
        return self._n

    def push(self, chunk: Any) -> np.ndarray:
        """Add the next ``(n, V)`` rows. Returns the normalised rows (see the class text)."""
        from fidetype.adapters.ctc_logits import to_log_probs

        if self._closed:
            raise RuntimeError("this session has ended")
        a = np.asarray(chunk)
        if a.ndim != 2 or a.shape[1] != self._V:
            raise ValueError(f"a chunk must be (n, {self._V}), got shape {a.shape}")
        self._raw.append(a)
        c = self._g._codec
        scale = c.input_scale if c.input_scale != "auto" else "auto"
        lp32 = to_log_probs(a, scale).astype(np.float32)
        if self._incremental:
            p = float(c.frame_period)
            ts = p + p * np.arange(self._n, self._n + a.shape[0])  # from_array: t0 = frame_period
            self._lines += [_event_line(_Codec.frame_event(t, row)) for t, row in zip(ts, lp32)]
            self._rows.append(lp32)
        self._n += a.shape[0]
        return lp32.astype(np.float64)

    def end(self) -> TrustResult:
        """The decision on all pushed rows (the same as ``guard.decide``); the session closes."""
        if self._closed:
            raise RuntimeError("this session has ended")
        self._closed = True
        g = self._g
        x = np.concatenate(self._raw, axis=0) if self._raw else np.zeros((0, self._V))
        if not self._incremental:
            return g.decide(x, utterance_id=self._uid)
        st = g._codec.stream(x)
        rows = np.concatenate(self._rows, axis=0) if self._rows else np.zeros((0, self._V), np.float32)
        p = float(g._codec.frame_period)
        if (len(self._lines) != st.log_probs.shape[0] or not np.array_equal(rows, st.log_probs)
                or not np.array_equal(p + p * np.arange(self._n), st.frame_times)):
            return g.decide(x, utterance_id=self._uid)  # safety net: never a different result
        head = _Codec.header_event(st)
        end = {"type": "end"}
        layer = g._layer
        layer.new_item("default")
        out = layer.push(dict(head), "default")
        out += layer.push_frames(st.frame_times, st.log_probs, "default")
        out += layer.push(dict(end), "default")
        out += layer.end_of_utterance("default", final_attempt=True)
        fin = [d for d in out if d.final]
        if len(fin) != 1:
            raise RuntimeError(f"expected one final decision, got {len(fin)}")
        events: list[dict[str, Any]] = [head, end]  # only the header is read on the logits path
        r = g._result(*g._gate_final(fin[0], events))
        h = hashlib.sha256()
        for line in [_event_line(head), *self._lines, _event_line(end)]:
            h.update(line)
            h.update(b"\n")
        g._log(r, events, self._uid, None if r.commit_score is None else {"commit_score": r.commit_score},
               input_sha=h.hexdigest())
        return r


def load(path: str | PathLike[str], decode_fn: UserDecodeFn | None = None, *,
         audit_text: bool = True, grounding: Any = None, offer_gate: Any = None, lm: Any = None,
         prefix_score: Any = None) -> TrustGuard:
    """Load a guard saved with :meth:`TrustGuard.save`.

    If the guard was calibrated with your own ``decode_fn``, pass the
    same function again: a function cannot be stored in a file, and a
    different decoder voids the guarantee. The same holds for
    ``grounding`` (P15-06): a guard with a commit grounding gate needs the
    same :class:`~fidetype.trust.halluc_bound.CommitGrounding` again.

    ``offer_gate`` (P5-33): None (default) uses the gate in the file, if there is one; an
    :class:`~fidetype.trust.offer_gate.OfferGate` (or a list) replaces it; ``False`` switches it off.
    ``lm``: the character LM of a ``char_lm`` gate.

    ``prefix_score`` (P5-35): a guard calibrated with a frozen external prefix score needs the same
    :class:`~fidetype.trust.external_score.FrozenPrefixScore` again (the file keeps its digest and spec, not the
    function). A missing or different score (other digest) raises ``ValueError``.
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
    gate = None
    if d.get("halluc_gate"):
        from fidetype.trust.halluc_bound import HallucGate

        gate = HallucGate.from_dict(d["halluc_gate"])
        if grounding is None:
            raise ValueError(f"this guard has a commit grounding gate ({d.get('grounding')}); pass grounding= "
                             "(the same CommitGrounding), or the hallucination bound does not apply")
        grounding = _as_commit_grounding(grounding)
    if offer_gate is None and d.get("offer_gate"):
        from fidetype.trust.offer_gate import OfferGate

        raw = d["offer_gate"]
        offer_gate = [OfferGate.from_dict(x, lm=lm) for x in (raw if isinstance(raw, list) else [raw])]
    return TrustGuard(FrozenTrustConfig.from_dict(d["config"]), codec, sheet, decode_fn, audit_text,
                      halluc_gate=gate, grounding=grounding, language=d.get("language", "en"),
                      offer_gate=offer_gate, prefix_score=prefix_score)


def _as_commit_grounding(g: Any) -> Any:
    from fidetype.trust.halluc_bound import CommitGrounding

    if g is None or isinstance(g, CommitGrounding):
        return g
    if hasattr(g, "label_fn"):
        return CommitGrounding.from_grounding_check(g)
    raise TypeError("grounding must be a CommitGrounding or a GroundingCheck")


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
#: P5-35: the extra assumption of a guard with a frozen external prefix score.
_EXTERNAL_ASSUMPTION = ("The external prefix score was frozen before calibration and was not fitted, tuned or "
                        "selected on the LTT items of this calibration.")
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
    grounding: Any = None,
    llm: Any = None,
    halluc_alpha: float = 0.01,
    halluc_delta: float | None = None,
    fluent_threshold: float | None = None,
    halluc_grid: Mapping[str, Sequence[float]] | None = None,
    halluc_select: str = "fewest_halluc",
    target_precision: float | None = None,
    precision_delta: float | None = None,
    precision_grid: Sequence[float] | None = None,
    decoder_label: str = "stable",
    confidence: str = "p_top1",
    confidence_l2: float = 1.0,
    commit_unit: str = "sentence",
    language: str = "en",
    offer_control: str = "warn",
    prefix_score: Any = None,
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
    offer_control
        The offer null control of P5-31 (:func:`offer_control`): the
        share of control inputs on which the guard OFFERs, against the
        offer rate on the LTT items. ``"warn"`` (default): the result is
        in ``sheet.offers`` and a failure adds a sheet warning; the guard
        and its status do not change. ``"refuse"``: a failure raises
        :class:`NullControlError`. ``"off"``: not run (the sheet bytes of
        a guard before P5-31). The counts come from the same control
        decisions as the commit controls (no extra decoding).
    decoder_name, decoder_version, modality
        Stream metadata (NTS ``meta``). ``modality`` is one of ``meg``,
        ``eeg``, ``emg``, ``ecog``, ``intracortical``, ``fnirs``, ``other``.
        With your own ``decode_fn``, ``decoder_name@decoder_version`` is
        also the decoder identity in the configuration (``decoder_id``,
        part of ``config_id``): give a stable, meaningful name.
    decoder_label
        ``"stable"`` (default, P5-21): the configuration names your
        ``decode_fn`` by its qualified name only, so ``config_id`` does
        not depend on how the defining script was loaded (run as
        ``__main__`` or imported). ``"module"``: the label before P5-21
        (with the module path); use it only to reproduce an old id.
    name
        A free name for the configuration.
    seed
        Seed of the random split and of the controls.
    audit_text
        Keep the shown text in the audit log (default True). False keeps
        only actions, scores and hashes.
    grounding, llm, halluc_alpha, halluc_delta, fluent_threshold, halluc_grid, halluc_select
        Optional hallucination bound (P15-06, :mod:`fidetype.trust.halluc_bound`).
        Off by default: with ``grounding=None`` and ``llm=None`` nothing
        changes. ``grounding`` (logits only): a
        :class:`~fidetype.trust.halluc_bound.CommitGrounding` (or a
        :class:`~fidetype.trust.grounding.GroundingCheck`); it adds a
        commit gate on the evidence of the committed text (sentence and
        word deficits). ``llm``: a sentence scorer (``score(texts) ->
        log-probs``, see :mod:`fidetype.lm.llm`) that defines the
        fluent-wrong loss; without it every wrong commit counts. Then
        ``commit_p`` and the gate thresholds are chosen together by Learn
        then Test on the policy-grid items (ordering) and the LTT items
        (test), so that with probability at least ``1 - halluc_delta``
        (default ``delta``) the fluent-wrong commit rate is at most
        ``halluc_alpha`` and the wrong-commit rate at most ``alpha``. The
        chosen ``commit_p`` is never below the P14-03 one, so the P14-03
        bound and the null controls still hold. ``fluent_threshold``: LLM
        log-probability per word at or above which a text is fluent
        (default: the median of the true texts of the fit items).
        ``halluc_grid``: optional ``{"commit_p": [...], "tau_commit": [...],
        "tau_word": [...]}``. ``halluc_select``: how to pick one of the
        certified configurations (``"fewest_halluc"`` or ``"most_right"``,
        see :func:`~fidetype.trust.halluc_bound.joint_ltt`); both keep the
        guarantee.
    target_precision, precision_delta, precision_grid
        Optional precision-type bound (P5-02,
        :mod:`fidetype.trust.precision_bound`): "when it types, it is
        right". Off by default (``None``: nothing changes). With
        ``target_precision=0.95``, ``commit_p`` is raised (never lowered)
        so that with probability at least ``1 - precision_delta`` (default
        ``delta``) the error rate **among commits** (wrong COMMITs / all
        COMMITs) is at most ``1 - target_precision``. Learn then Test over
        the thresholds ``precision_grid`` (default 1.00 -> 0.00 step 0.01):
        test order from the policy-grid items, fixed-sequence test on the
        LTT items, exact binomial p-values on the commits. The P14-03
        bound and the null controls still hold. If no threshold is
        certified, the guard never commits. With the hallucination bound
        (``grounding=`` / ``llm=``) the precision risk joins the same joint
        Learn then Test as a third risk (p-value ``max(p_wc, p_h, p_prec)``,
        one fixed-sequence test at level ``min(halluc_delta,
        precision_delta)``): all three bounds then hold together with that
        probability (see ``docs/trust-guarantee.md`` section 10).

    confidence, confidence_l2
        The commit score (P5-23, :mod:`fidetype.trust.commit_score`).
        ``"p_top1"`` (default): commit when the calibrated top-1
        probability is at or above the LTT threshold (P14-03, unchanged).
        ``"learned"``: fit a small logistic regression (L2 weight
        ``confidence_l2`` on standardised features) on the fit and
        policy-grid items, from the n-best and decoder outputs (``p_top1``,
        margin, n-best entropy and word agreement, character confidences,
        guard risk, conformal set size, length, acoustic and LM scores);
        then certify its threshold by Learn then Test on the LTT items
        only (disjoint from the fit items). Same guarantee, same commit
        gate, same null controls (they run on the final guard). The score
        is part of the configuration (``config_id``) and of the guard
        file. Not combined with ``grounding``, ``llm`` or
        ``target_precision`` in this version, and :meth:`TrustGuard.online`
        is not available for it.

    commit_unit
        What a COMMIT holds (P5-24, :mod:`fidetype.trust.commit_score`).
        ``"sentence"`` (default): the whole top-1 text (unchanged).
        ``"prefix"``: the longest word prefix of the top-1 text whose
        learned prefix score passes the certified threshold (needs
        ``confidence="learned"``). The prefix score is fitted on the fit
        and policy-grid items (one row per prefix); its threshold is
        certified by Learn then Test on the LTT items only, with the loss
        "the committed prefix is wrong" (its words are not the first words
        of the true text; a commit of all top-1 words must equal the true
        text). The guarantee is on wrong prefix commits / all utterances.
        :class:`TrustResult` and the decision event give the number of
        committed words (``n_words_committed``) and ``complete``. The null
        controls count every prefix commit. Score prefix guards with
        ``safe-wpm/0.2`` (proposed), not v0.1.
    prefix_score
        Optional frozen external per-prefix score (P5-35): a
        :class:`~fidetype.trust.external_score.FrozenPrefixScore` (your
        function ``fn(ctx) -> one score per word prefix | None``, plus a
        name, a version and a JSON ``spec``). Needs
        ``commit_unit="prefix"``. The library fits no score; it certifies
        the threshold of your score by the same Learn then Test on the LTT
        items only (loss "wrong prefix commit"), with the same commit gate
        and null controls. The score must not have been fitted or tuned on
        the LTT items of this calibration (for example fit it on the fit +
        policy-grid items of the same ``seed`` split, or on other data).
        The digest of the score enters ``config_id``; the guard file keeps
        the digest and the spec, and :func:`load` needs the same score
        again (``prefix_score=``). Not combined with ``grounding``,
        ``llm`` or ``target_precision``.
    language
        BCP 47 tag of the true texts (P14-34, :mod:`fidetype.lang`). It
        must resolve in the language registry. The guard keeps it
        (:attr:`TrustGuard.language`) and its file stores it if it is not
        ``"en"``. It changes no decision. ``commit_unit="prefix"`` needs a
        language with words separated by spaces.

    Raises
    ------
    NullControlError
        The calibrated guard commits on null input more often than allowed
        (or, with ``offer_control="refuse"``, offers on null input about as
        often as on real input). No guard is returned.
    ValueError
        Bad input (lengths differ, too few items, unknown kind, missing
        ``vocab`` or ``null_inputs``).
    """
    from fidetype.eval.harness import Item, TrustPipeline
    from fidetype.trust.session_risk import min_ltt_items

    from fidetype.lang import check_tag, get as _get_language

    language = check_tag(language, "language")
    if commit_unit == "prefix" and not _get_language(language).wpm_defined:
        raise ValueError(f"commit_unit='prefix' needs word boundaries; language {language!r} has none "
                         "(docs/language-support.md, follow-up P14-39)")
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
    if offer_control not in ("off", "warn", "refuse"):
        raise ValueError("offer_control must be 'off', 'warn' or 'refuse'")
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
    halluc_on = grounding is not None or llm is not None
    if grounding is not None and kind != "logits":
        raise ValueError("grounding is for logits input only (it needs the frames)")
    if halluc_on:
        h_delta = float(delta if halluc_delta is None else halluc_delta)
        if not (0.0 < halluc_alpha < 1.0 and 0.0 < h_delta < 1.0):
            raise ValueError("halluc_alpha and halluc_delta must be in (0, 1)")
        if halluc_grid is not None:
            bad = sorted(set(halluc_grid) - {"commit_p", "tau_commit", "tau_word"})
            if bad:
                raise ValueError(f"unknown halluc_grid keys {bad}")
        from fidetype.trust.halluc_bound import SELECT_RULES

        if halluc_select not in SELECT_RULES:
            raise ValueError(f"halluc_select must be one of {SELECT_RULES}")
    prec_on = target_precision is not None
    if prec_on:
        p_delta = float(delta if precision_delta is None else precision_delta)
        if not (0.0 < float(target_precision) < 1.0 and 0.0 < p_delta < 1.0):
            raise ValueError("target_precision and precision_delta must be in (0, 1)")
        if precision_grid is not None and not any(math.isfinite(float(c)) for c in precision_grid):
            raise ValueError("precision_grid has no finite threshold")
    elif precision_delta is not None or precision_grid is not None:
        raise ValueError("precision_delta and precision_grid need target_precision=")
    lex = tuple(sorted({w for entry in lexicon for w in str(entry).split()})) if lexicon is not None else None
    if lex is not None and not lex:
        raise ValueError("lexicon is empty")
    from fidetype.writer import MODALITIES

    if modality not in MODALITIES:
        raise ValueError(f"modality must be one of {MODALITIES}")
    dec_meta = {"name": str(decoder_name), "version": str(decoder_version), "modality": modality}

    if decoder_label not in DECODER_LABELS:
        raise ValueError(f"decoder_label must be one of {DECODER_LABELS}")
    from fidetype.trust.commit_score import CONFIDENCE_KINDS

    if confidence not in CONFIDENCE_KINDS:
        raise ValueError(f"confidence must be one of {CONFIDENCE_KINDS}, not {confidence!r}")
    ext_score = None
    if prefix_score is not None:  # P5-35: a frozen external prefix score (certified here, not fitted here)
        from fidetype.trust.external_score import as_prefix_score

        ext_score = as_prefix_score(prefix_score)
        if commit_unit != "prefix":
            raise ValueError('prefix_score= needs commit_unit="prefix"')
        if halluc_on or prec_on:
            raise ValueError("prefix_score= cannot be combined with grounding=, llm= or target_precision= in this "
                             "version")
    learned = confidence == "learned" or ext_score is not None
    if learned and (halluc_on or prec_on):
        raise ValueError('confidence="learned" cannot be combined with grounding=, llm= or target_precision= '
                         "in this version")
    if learned and not (float(confidence_l2) > 0.0 and math.isfinite(float(confidence_l2))):
        raise ValueError("confidence_l2 must be a positive number")
    from fidetype.trust.commit_score import COMMIT_UNITS

    if commit_unit not in COMMIT_UNITS:
        raise ValueError(f"commit_unit must be one of {COMMIT_UNITS}, not {commit_unit!r}")
    prefix_on = commit_unit == "prefix"
    if prefix_on and not learned:
        raise ValueError('commit_unit="prefix" needs confidence="learned" (a learned prefix score; a plain n-best '
                         "prefix posterior cannot be certified: prefixes that all candidates share get mass 1.0)")

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
    stable = decoder_label == "stable"
    recipe.update({"fitted_by": "fidetype.trust.calibrate (P14-03 drop-in)", "input_kind": kind,
                   "decoder": _decoder_name(decode_fn, lex, stable=stable) if kind == "logits" else "user n-best",
                   "split": {"fit": n_fit, "policy_grid": n_pol, "ltt": n_ltt, "seed": seed},
                   "commit_gate": "always on (re-tune rule 2026-11-15)",
                   "frame_temperature": ("fitted on stream_texts" if stream_texts is not None else
                                         "fitted on texts" if frame_fit else "not fitted (1.0)"),
                   "null_controls": "uniform + shuffled, automatic"})
    if stable and kind == "logits" and decode_fn is not None:
        # P5-21: a stable identity of your decoder (decoder_name / decoder_version), not its module path
        recipe["decoder_id"] = f"{dec_meta['name']}@{dec_meta['version']}"
    frozen = FrozenTrustConfig.from_pipeline(pipe, name, recipe).with_commit_gate(**COMMIT_GATE)
    score_info: dict[str, Any] | None = None
    if learned:
        frozen, score_info = _fit_commit_score(frozen, codec, decode_fn if kind == "logits" else None, audit_text,
                                               inputs, texts, order, n_fit, n_pol, alpha, delta,
                                               float(confidence_l2), unit=commit_unit, external=ext_score)

    guard = TrustGuard(frozen, codec, None, decode_fn if kind == "logits" else None, audit_text,
                       prefix_score=ext_score)

    # --- in-sample LTT check -------------------------------------------
    ltt_inputs = [inputs[i] for i in order[n_fit + n_pol:]]
    ltt_texts = [texts[i] for i in order[n_fit + n_pol:]]
    n_com = n_wrong = n_off = 0
    risks: list[float] = []
    n_blocked = 0
    for x, t in zip(ltt_inputs, ltt_texts):
        r = guard._decide_quiet(x)
        risks.append(r.guard_risk)
        n_blocked += r.reason.startswith(_GATE_RISK_REASON)
        n_off += r.action == "offer"
        if r.action == "commit":
            n_com += 1
            n_wrong += int(not guard.is_right(r, t))

    # --- null controls --------------------------------------------------
    import copy

    rng_controls = copy.deepcopy(rng)  # the same control inputs again for a P15-06 guard
    controls = _run_controls(guard, inputs, kind, rng, null_trials, rate, null_inputs)
    offers = None
    if offer_control == "off":
        controls = [replace(c, n_offer=None) for c in controls]
    else:
        offers = _offer_control(len(ltt_inputs), n_off, controls, rate=rate, mode=offer_control)

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
    commit_thr = (float(guard.commit_score.threshold) if guard.commit_score is not None
                  else float(frozen.policy.get("commit_p", math.inf)))
    can_commit = math.isfinite(commit_thr)
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
    warnings = _with_offers(offers, warnings)
    sheet = GuaranteeSheet(
        config_id=frozen.config_id, input_kind=kind,
        decoder=_decoder_name(decode_fn, lex) if kind == "logits" else "your n-best lists",
        alpha=float(alpha), delta=float(delta),
        method=(f"Learn then Test on the frozen external prefix score {ext_score.name!r} version "
                f"{ext_score.version!r} ({ext_score.digest}; not fitted by calibrate), loss = wrong prefix commit, "
                "exact binomial p-values, fixed-sequence grid 1.00 -> 0.00 step 0.01, on the LTT items only"
                if ext_score is not None else
                "Learn then Test on the learned prefix score (fitted on the fit + policy-grid items, one row per "
                "word prefix), loss = wrong prefix commit, exact binomial p-values, fixed-sequence grid 1.00 -> 0.00 "
                "step 0.01, on the LTT items only" if prefix_on else
                "Learn then Test on the learned commit score (fitted on the fit + policy-grid items), exact "
                "binomial p-values, fixed-sequence grid 1.00 -> 0.00 step 0.01, on the LTT items only" if learned else
                "Learn then Test, exact binomial p-values, fixed-sequence grid 1.00 -> 0.00 step 0.01, "
                "combined with the policy-grid threshold by max"),
        n_items=len(items), n_fit=n_fit, n_policy=n_pol, n_ltt=n_ltt, n_ltt_min=n_min,
        lambda_hat=float(rc.get("threshold", math.nan)), feasible=bool(rc.get("feasible", False)),
        commit_threshold=commit_thr, commit_gate=dict(frozen.commit_gate),
        ltt_commits=n_com, ltt_wrong_commits=n_wrong, controls=tuple(controls), null_max_commit_rate=rate,
        seed=int(seed), created_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        assumptions=_ASSUMPTIONS + ((_EXTERNAL_ASSUMPTION,) if ext_score is not None else ()),
        not_guaranteed=_NOT_GUARANTEED, warnings=tuple(warnings),
        ltt_median_guard_risk=med_risk, ltt_gate_blocked=int(n_blocked), confidence=score_info, offers=offers,
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
    if offers is not None and offer_control == "refuse" and not offers["passed"]:
        raise NullControlError("calibration refused (offer_control='refuse'): " + _offer_warning(offers)
                               + " No configuration was produced.", controls)
    guard.sheet = sheet
    if halluc_on:
        guard = _halluc_bound(guard, sheet, inputs, texts, order, n_fit, n_pol, kind, decode_fn, audit_text,
                              _as_commit_grounding(grounding), llm, float(halluc_alpha), h_delta,
                              fluent_threshold, halluc_grid, rng_controls, null_trials, rate, null_inputs,
                              halluc_select, target_precision=float(target_precision) if prec_on else None,
                              delta_p=p_delta if prec_on else None)
    elif prec_on:
        guard = _precision_bound(guard, sheet, inputs, texts, order, n_fit, n_pol, kind, decode_fn, audit_text,
                                 float(target_precision), p_delta, precision_grid, rng_controls, null_trials, rate,
                                 null_inputs)
    guard.language = language
    return guard


def _fit_commit_score(frozen: FrozenTrustConfig, codec: _Codec, decode_fn: UserDecodeFn | None, audit_text: bool,
                      inputs: Sequence[Any], texts: Sequence[str], order: np.ndarray, n_fit: int, n_pol: int,
                      alpha: float, delta: float, l2: float,
                      unit: str = "sentence", external: Any = None) -> tuple[FrozenTrustConfig, dict[str, Any]]:
    """P5-23: fit the learned commit score on the fit + policy-grid items; certify it by LTT on the LTT items.

    Returns the configuration with ``commit_p = inf`` (the trust layer alone never commits), the score in
    ``recipe["commit_score"]`` (so ``config_id`` covers it) and the LTT record in ``risk_control``; and the
    ``confidence`` block of the guarantee sheet.
    """
    from fidetype.trust.commit_score import FEATURES, MODEL, LearnedCommitScore
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID, ltt_threshold

    base = frozen.with_policy(commit_p=math.inf)
    g0 = TrustGuard(base, codec, None, decode_fn, audit_text)
    gate = base.gate
    if unit == "prefix" and external is not None:
        return _certify_external_prefix(frozen, base, g0, codec, inputs, texts, order, n_fit, n_pol, alpha, delta,
                                        external)
    if unit == "prefix":
        return _fit_prefix_score(frozen, base, g0, codec, inputs, texts, order, n_fit, n_pol, alpha, delta, l2)
    feats, right, gate_ok = [], [], []
    for i in order:
        events, _ = codec.events(inputs[i])
        sd = g0._run_layer(g0._layer, events)
        feats.append(g0._features(sd, events))
        top = _norm_text(sd.inputs.texts[0]) if sd.inputs.texts else ""
        right.append(bool(sd.inputs.texts) and top == texts[i])
        ok = bool(sd.inputs.texts) and (gate is None or gate.violation(
            sd.inputs.texts[0], float(sd.inputs.guard_risk) if base.use_guard else None) is None)
        gate_ok.append(ok)
    X = np.array(feats, dtype=np.float64).reshape(len(order), len(FEATURES))
    y = np.array(right, dtype=bool)
    k = n_fit + n_pol
    model = LearnedCommitScore.fit(X[:k], y[:k], l2=l2)
    s_ltt = np.array([model.score(r) if ok else -math.inf for r, ok in zip(X[k:], gate_ok[k:])])
    loss = (~y[k:]).astype(np.float64)
    res = ltt_threshold(s_ltt, loss, alpha=alpha, delta=delta, grid=DEFAULT_LTT_GRID, pvalue="binomial")
    cert = {"method": res.method, "alpha": float(alpha), "delta": float(delta), "n": int(res.n),
            "feasible": bool(res.feasible), "empirical_risk": None if math.isnan(res.empirical_risk) else
            float(res.empirical_risk), "p_value": None if math.isnan(res.bound) else float(res.bound),
            "ltt_commit_rate": float(res.commit_rate), "grid": "1.00 -> 0.00 step 0.01"}
    model = model.with_threshold(res.threshold, cert)
    rc = {"method": res.method, "alpha": float(alpha), "delta": float(delta),
          "threshold": res.threshold, "feasible": bool(res.feasible), "n": int(res.n),
          "bound": res.bound, "combine": "none (learned commit score, P5-23)", "score": "learned"}
    recipe = dict(frozen.recipe)
    recipe.update({"commit_score": model.to_dict(),
                   "commit_score_split": {"fit": "fit + policy_grid items", "n_fit": int(k),
                                          "certify": "ltt items", "n_certify": int(len(order) - k)},
                   "fitted_by": str(recipe.get("fitted_by", "")) + " + P5-23 learned commit score"})
    out = replace(base, recipe=recipe, risk_control=rc)
    info = {"kind": "learned", "schema": model.schema, "model": MODEL,
            "features": list(FEATURES), "dropped": list(model.dropped),
            "n_used": int(sum(c != 0.0 for c in model.coef)), "l2": float(l2), "fit_items": int(k),
            "fit_positive": int(y[:k].sum()),
            "certify_items": int(len(order) - k), "threshold": _json_float(res.threshold),
            "feasible": bool(res.feasible),
            "coef": {f: float(c) for f, c in zip(FEATURES, model.coef)}, "intercept": float(model.intercept)}
    return out, info


def _fit_prefix_score(frozen: FrozenTrustConfig, base: FrozenTrustConfig, g0: TrustGuard, codec: _Codec,
                      inputs: Sequence[Any], texts: Sequence[str], order: np.ndarray, n_fit: int, n_pol: int,
                      alpha: float, delta: float, l2: float) -> tuple[FrozenTrustConfig, dict[str, Any]]:
    """P5-24: fit the learned prefix score on the fit + policy-grid items (one row per word prefix of the top-1
    text); certify its threshold by LTT on the LTT items with the loss "wrong prefix commit"."""
    from fidetype.trust.commit_score import (MODEL, PREFIX_FEATURES, RISK_PREFIX, LearnedCommitScore,
                                             ltt_prefix_threshold, monotone_prefix_scores, prefix_right)
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    gate = base.gate
    per_item: list[tuple[np.ndarray, np.ndarray, bool]] = []
    for i in order:
        events, _ = codec.events(inputs[i])
        sd = g0._run_layer(g0._layer, events)
        rows, words = g0._prefix_rows(sd, events)
        right = prefix_right(words, texts[i].split()) if len(rows) else np.zeros(0, bool)
        ok = bool(sd.inputs.texts) and len(rows) > 0 and (gate is None or gate.violation(
            sd.inputs.texts[0], float(sd.inputs.guard_risk) if base.use_guard else None) is None)
        per_item.append((rows, right, ok))
    k = n_fit + n_pol
    fit_rows = [r for r, _, _ in per_item[:k] if len(r)]
    X = (np.vstack(fit_rows) if fit_rows else np.zeros((0, len(PREFIX_FEATURES))))
    y = np.concatenate([y for r, y, _ in per_item[:k] if len(r)]) if fit_rows else np.zeros(0, bool)
    model = LearnedCommitScore.fit(X, y, l2=l2, unit="prefix")
    s_ltt = [monotone_prefix_scores(model.scores(r)) if ok else np.zeros(0) for r, _, ok in per_item[k:]]
    r_ltt = [y for _, y, _ in per_item[k:]]
    res = ltt_prefix_threshold(s_ltt, r_ltt, alpha=alpha, delta=delta, grid=DEFAULT_LTT_GRID)
    cert = {"method": "ltt-binomial (prefix loss)", "alpha": float(alpha), "delta": float(delta), "n": int(res["n"]),
            "feasible": bool(res["feasible"]),
            "empirical_risk": None if math.isnan(res["empirical_risk"]) else float(res["empirical_risk"]),
            "p_value": None if math.isnan(res["p_value"]) else float(res["p_value"]),
            "ltt_commit_rate": float(res["commit_rate"]), "grid": "1.00 -> 0.00 step 0.01", "risk": RISK_PREFIX}
    model = model.with_threshold(res["threshold"], cert)
    rc = {"method": "ltt-binomial", "alpha": float(alpha), "delta": float(delta), "threshold": res["threshold"],
          "feasible": bool(res["feasible"]), "n": int(res["n"]),
          "bound": res["p_value"], "combine": "none (learned prefix score, P5-24)", "score": "learned-prefix",
          "risk": "wrong-prefix-commit"}
    recipe = dict(frozen.recipe)
    n_rows_pos = int(y.sum())
    recipe.update({"commit_score": model.to_dict(),
                   "commit_score_split": {"fit": "fit + policy_grid items", "n_fit": int(k), "n_fit_rows": int(len(y)),
                                          "certify": "ltt items", "n_certify": int(len(order) - k)},
                   "commit_unit": "prefix",
                   "fitted_by": str(recipe.get("fitted_by", "")) + " + P5-24 learned prefix score"})
    out = replace(base, recipe=recipe, risk_control=rc)
    info = {"kind": "learned", "unit": "prefix", "schema": model.schema, "model": MODEL,
            "features": list(PREFIX_FEATURES), "dropped": list(model.dropped),
            "n_used": int(sum(c != 0.0 for c in model.coef)), "l2": float(l2), "fit_items": int(k),
            "fit_positive": n_rows_pos, "fit_rows": int(len(y)),
            "certify_items": int(len(order) - k), "threshold": _json_float(res["threshold"]),
            "feasible": bool(res["feasible"]), "risk": RISK_PREFIX,
            "coef": {f: float(c) for f, c in zip(PREFIX_FEATURES, model.coef)}, "intercept": float(model.intercept)}
    return out, info


def _certify_external_prefix(frozen: FrozenTrustConfig, base: FrozenTrustConfig, g0: TrustGuard, codec: _Codec,
                             inputs: Sequence[Any], texts: Sequence[str], order: np.ndarray, n_fit: int, n_pol: int,
                             alpha: float, delta: float, score: Any) -> tuple[FrozenTrustConfig, dict[str, Any]]:
    """P5-35: certify the threshold of a frozen external prefix score by LTT on the LTT items (nothing is fitted).

    Same loss, grid, commit gate and test as the P5-24 learned prefix score (:func:`_fit_prefix_score`).
    """
    from fidetype.trust.commit_score import RISK_PREFIX, ltt_prefix_threshold, monotone_prefix_scores, prefix_right
    from fidetype.trust.external_score import ExternalPrefixCommit
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    gate = base.gate
    k = n_fit + n_pol
    s_ltt: list[np.ndarray] = []
    r_ltt: list[np.ndarray] = []
    n_none = n_blocked = 0
    for i in order[k:]:
        events, _ = codec.events(inputs[i])
        sd = g0._run_layer(g0._layer, events)
        ctx = g0._prefix_context(sd, events)
        words = list(ctx.words)
        raw = score.scores(ctx) if (words and sd.inputs.texts) else None
        n_none += raw is None
        ok = raw is not None and len(raw) > 0 and (gate is None or gate.violation(
            sd.inputs.texts[0], float(sd.inputs.guard_risk) if base.use_guard else None) is None)
        n_blocked += raw is not None and not ok
        s_ltt.append(monotone_prefix_scores(raw) if ok else np.zeros(0))
        r_ltt.append(prefix_right(words, texts[i].split()) if words else np.zeros(0, bool))
    res = ltt_prefix_threshold(s_ltt, r_ltt, alpha=alpha, delta=delta, grid=DEFAULT_LTT_GRID)
    cert = {"method": "ltt-binomial (prefix loss)", "alpha": float(alpha), "delta": float(delta), "n": int(res["n"]),
            "feasible": bool(res["feasible"]),
            "empirical_risk": None if math.isnan(res["empirical_risk"]) else float(res["empirical_risk"]),
            "p_value": None if math.isnan(res["p_value"]) else float(res["p_value"]),
            "ltt_commit_rate": float(res["commit_rate"]), "grid": "1.00 -> 0.00 step 0.01", "risk": RISK_PREFIX}
    ext = ExternalPrefixCommit(score=score).with_threshold(res["threshold"], cert)
    rc = {"method": "ltt-binomial", "alpha": float(alpha), "delta": float(delta), "threshold": res["threshold"],
          "feasible": bool(res["feasible"]), "n": int(res["n"]),
          "bound": res["p_value"], "combine": "none (external prefix score, P5-35)", "score": "external-prefix",
          "risk": "wrong-prefix-commit"}
    recipe = dict(frozen.recipe)
    recipe.update({"commit_score": ext.to_dict(),
                   "commit_score_split": {"fit": "none (frozen external score)", "n_fit": 0,
                                          "certify": "ltt items", "n_certify": int(len(order) - k)},
                   "commit_unit": "prefix",
                   "fitted_by": str(recipe.get("fitted_by", "")) + " + P5-35 external prefix score"})
    out = replace(base, recipe=recipe, risk_control=rc)
    info = {"kind": "external", "unit": "prefix", "schema": ext.schema, "name": score.name,
            "version": score.version, "digest": score.digest, "certify_items": int(len(order) - k),
            "certify_no_score": int(n_none), "certify_gate_blocked": int(n_blocked),
            "threshold": _json_float(res["threshold"]), "feasible": bool(res["feasible"]), "risk": RISK_PREFIX}
    return out, info


def _precision_bound(guard: TrustGuard, sheet: GuaranteeSheet, inputs: Sequence[Any], texts: Sequence[str],
                     order: np.ndarray, n_fit: int, n_pol: int, kind: str, decode_fn: UserDecodeFn | None,
                     audit_text: bool, target_precision: float, delta_p: float,
                     grid: Sequence[float] | None, rng_controls: np.random.Generator, null_trials: int,
                     rate: float, null_inputs: Sequence[Any] | None) -> TrustGuard:
    """The P5-02 step of :func:`calibrate`: LTT on the error rate among commits; a new guard."""
    from fidetype.trust import precision_bound as P

    frozen = guard.config
    codec = guard._codec
    user_fn = decode_fn if kind == "logits" else None
    g0 = TrustGuard(frozen.with_policy(commit_p=0.0), codec, None, user_fn, audit_text)

    def item(i: int) -> P.PrecisionItem:
        r0 = g0._decide_quiet(inputs[i])
        can = r0.action == "commit"
        top = r0.text if can else (r0.choices[0] if r0.choices else "")
        return P.PrecisionItem(can, float(r0.p_top1), top != texts[i])

    o_items = [item(int(i)) for i in order[n_fit:n_fit + n_pol]]
    t_items = [item(int(i)) for i in order[n_fit + n_pol:]]
    thr = tuple(grid) if grid is not None else P.DEFAULT_COMMIT_P_GRID
    c0 = float(frozen.policy.get("commit_p", math.inf))
    res = P.precision_ltt(o_items, t_items, thr, target_precision=target_precision, delta=delta_p, min_commit_p=c0)
    sel = res.selected if res.selected is not None else math.inf
    info = {
        "target_precision": target_precision,
        "beta": 1.0 - target_precision,
        "delta_p": delta_p,
        "method": "Learn then Test over commit_p; exact binomial p-value P(Bin(commits, beta) <= wrong) per "
                  "threshold; order from the policy-grid items, fixed-sequence test on the LTT items; select the "
                  f"most commits with commit_p >= {_fmt(c0)} (P14-03 value)",
        "grid": len({float(c) for c in thr if math.isfinite(float(c))}),
        "base_commit_p": _json_float(c0),
        "base_config_id": frozen.config_id,
        "min_commits": P.min_commits_needed(target_precision, delta_p),
        **{k: v for k, v in res.to_dict().items() if k not in ("target_precision", "beta", "delta")},
        "selected": _json_float(sel),
    }
    recipe = dict(frozen.recipe)
    recipe["precision_bound"] = {k: info[k] for k in ("target_precision", "delta_p", "method", "selected")}
    final = replace(frozen.with_policy(commit_p=sel), recipe=recipe)
    new = TrustGuard(final, codec, None, user_fn, audit_text)
    # in-sample LTT check and null controls of the final guard (same control inputs as before)
    n_com = n_wrong = n_blocked = n_off = 0
    risks = []
    for i in order[n_fit + n_pol:]:
        r = new._decide_quiet(inputs[int(i)])
        risks.append(r.guard_risk)
        n_blocked += r.reason.startswith(_GATE_RISK_REASON)
        n_off += r.action == "offer"
        if r.action == "commit":
            n_com += 1
            n_wrong += int(r.text != texts[int(i)])
    controls = _run_controls(new, inputs, kind, rng_controls, null_trials, rate, null_inputs)
    controls, offers = _final_offers(sheet, controls, len(order) - n_fit - n_pol, n_off, rate)
    info["controls_final"] = [c.to_dict() for c in controls]
    warnings = _with_offers(offers, list(sheet.warnings))
    if res.selected is None:
        warnings.append(f"precision bound: no threshold certified for precision {target_precision:g}, so the guard "
                        f"never commits. About {info['min_commits']} or more right commits on the LTT part are needed.")
    elif n_com < info["min_commits"]:
        warnings.append(f"precision bound: only {n_com} in-sample commits (fewer than {info['min_commits']}).")
    if res.selected is not None and (n_com, n_wrong) != (res.test_counts.get("commits", 0),
                                                         res.test_counts.get("wrong", 0)):
        warnings.append("precision bound: the final guard's in-sample commits differ from the LTT count; the commit "
                        "rule is not monotone in commit_p for this policy, so check the held-out precision.")
    new.sheet = replace(sheet, config_id=final.config_id, commit_threshold=float(sel), ltt_commits=n_com,
                        ltt_wrong_commits=n_wrong, ltt_gate_blocked=int(n_blocked),
                        ltt_median_guard_risk=float(np.median(risks)) if risks else math.nan,
                        controls=tuple(controls), warnings=tuple(warnings), precision=info, offers=offers,
                        assumptions=sheet.assumptions + _PRECISION_ASSUMPTIONS,
                        not_guaranteed=tuple(a for a in sheet.not_guaranteed if not a.startswith(
                            "The error rate among commits")) + _PRECISION_NOT_GUARANTEED)
    new.precision_items = {"order": o_items, "test": t_items}  # per-item statistics (not saved)
    return new


_PRECISION_ASSUMPTIONS = (
    "Precision bound: the same exchangeability as above, for the utterances on which the guard commits.",
)
_PRECISION_NOT_GUARANTEED = (
    "Precision bound: the error rate among commits of one session or one user; any single commit; precision when "
    "the guard commits rarely is a rate over few events (the bound is still valid, but a long run is needed to see it).",
)


def _halluc_bound(guard: TrustGuard, sheet: GuaranteeSheet, inputs: Sequence[Any], texts: Sequence[str],
                  order: np.ndarray, n_fit: int, n_pol: int, kind: str, decode_fn: UserDecodeFn | None,
                  audit_text: bool, grounding: Any, llm: Any, alpha_h: float, delta_h: float,
                  fluent_threshold: float | None, halluc_grid: Mapping[str, Sequence[float]] | None,
                  rng_controls: np.random.Generator, null_trials: int, rate: float,
                  null_inputs: Sequence[Any] | None, select: str = "fewest_halluc", *,
                  target_precision: float | None = None, delta_p: float | None = None) -> TrustGuard:
    """The P15-06 step of :func:`calibrate`: joint LTT of (commit_p, tau_commit, tau_word); a new guard.

    With ``target_precision`` (P5-02), the precision risk is a third risk of the same joint test, at level
    ``min(delta_h, delta_p)``.
    """
    from fidetype.trust import halluc_bound as H

    joint_p = target_precision is not None
    if joint_p:
        delta_h = min(float(delta_h), float(delta_p if delta_p is not None else delta_h))

    frozen = guard.config
    codec = guard._codec
    user_fn = decode_fn if kind == "logits" else None
    if llm is not None:
        thr = (float(fluent_threshold) if fluent_threshold is not None else
               H.fluent_threshold_from_texts([texts[i] for i in order[:n_fit]], llm))
        fluent_rule = f"fluent (LLM log-prob per word >= {thr:.4g})"
    else:
        thr = math.nan
        fluent_rule = "any text (no LLM: every wrong commit counts)"
    g0 = TrustGuard(frozen.with_policy(commit_p=0.0), codec, None, user_fn, audit_text)
    g_inf = TrustGuard(frozen.with_policy(commit_p=math.inf), codec, None, user_fn, audit_text)

    def item(i: int) -> H.ItemStats:
        x, t = inputs[i], texts[i]
        r0 = g0._decide_quiet(x)
        top = r0.choices[0] if r0.choices else ""
        if r0.action != "commit":
            return H.ItemStats(False, r0.p_top1, top != t, False, r0.raw_action == "OFFER_WORDS" and top != t)
        lp = g0._last_lp
        st = grounding.stats(lp, r0.text) if (grounding is not None and lp is not None) else H.GroundingStats(0.0, ())
        wrong = r0.text != t
        fluent = H.is_fluent(r0.text, llm, thr) if wrong else False
        fb = g_inf._decide_quiet(x)
        fb_top = fb.choices[0] if fb.choices else ""
        return H.ItemStats(True, r0.p_top1, wrong, fluent, fb.raw_action == "OFFER_WORDS" and fb_top != t, st)

    o_items = [item(int(i)) for i in order[n_fit:n_fit + n_pol]]
    t_items = [item(int(i)) for i in order[n_fit + n_pol:]]
    hg = dict(halluc_grid or {})
    if grounding is None:
        hg["tau_commit"], hg["tau_word"] = [math.inf], [math.inf]
    configs = H.grid(hg.get("commit_p", H.DEFAULT_COMMIT_P_GRID), hg.get("tau_commit", H.DEFAULT_TAU_COMMIT_GRID),
                     hg.get("tau_word", H.DEFAULT_TAU_WORD_GRID))
    c0 = float(frozen.policy.get("commit_p", math.inf))
    res = H.joint_ltt(o_items, t_items, configs, alpha=float(guard.alpha), alpha_h=alpha_h, delta=delta_h,
                      min_commit_p=c0, select=select, target_precision=target_precision)
    sel = res.selected if res.selected is not None else H.Config(math.inf, H.HallucGate())
    info = {
        "loss": "fluent_wrong" if llm is not None else "wrong",
        "fluent_rule": fluent_rule,
        "fluent_threshold": _json_float(thr),
        "alpha_h": alpha_h,
        "delta_h": delta_h,
        "method": "Learn then Test over the joint grid (commit_p, tau_commit, tau_word); p-value "
                  + ("max(p_wc, p_h, p_precision)" if joint_p else "max(p_wc, p_h)") + ", "
                  "exact binomial; order from the policy-grid items, fixed-sequence test on the LTT items; "
                  f"select commit_p >= {_fmt(c0)} (P14-03 value), rule {select!r}",
        "grid": {"commit_p": len(set(c.commit_p for c in configs)),
                 "tau_commit": len(set(c.gate.tau_commit for c in configs)),
                 "tau_word": len(set(c.gate.tau_word for c in configs))},
        "grounding": getattr(grounding, "name", None) if grounding is not None else None,
        "base_commit_p": _json_float(c0),
        "base_config_id": frozen.config_id,
        **{k: v for k, v in res.to_dict().items() if k not in ("alpha", "alpha_h", "delta")},
        "selected": {k: v for k, v in sel.to_dict().items()},
    }
    recipe = dict(frozen.recipe)
    info["select"] = select
    recipe["halluc_bound"] = {k: info[k] for k in ("loss", "fluent_threshold", "alpha_h", "delta_h", "method",
                                                   "grounding", "selected", "select")}
    prec_info = None
    if joint_p:
        prec_info = _joint_precision_info(res, float(target_precision), float(delta_h), c0, frozen.config_id,
                                          len({c.commit_p for c in configs if math.isfinite(c.commit_p)}))
        info["target_precision"] = float(target_precision)
        recipe["precision_bound"] = {k: prec_info[k] for k in ("target_precision", "delta_p", "method", "selected")}
    final = replace(frozen.with_policy(commit_p=sel.commit_p), recipe=recipe)
    gate = None if sel.gate.is_off or grounding is None else sel.gate
    new = TrustGuard(final, codec, None, user_fn, audit_text, halluc_gate=gate,
                     grounding=grounding if gate is not None else None)
    # in-sample LTT check and null controls of the final guard (same control inputs as before)
    ltt_idx = order[n_fit + n_pol:]
    n_com = n_wrong = n_blocked = n_off = 0
    risks = []
    for i in ltt_idx:
        r = new._decide_quiet(inputs[int(i)])
        risks.append(r.guard_risk)
        n_blocked += r.reason.startswith(_GATE_RISK_REASON)
        n_off += r.action == "offer"
        if r.action == "commit":
            n_com += 1
            n_wrong += int(r.text != texts[int(i)])
    controls = _run_controls(new, inputs, kind, rng_controls, null_trials, rate, null_inputs)
    controls, offers = _final_offers(sheet, controls, len(ltt_idx), n_off, rate)
    info["controls_final"] = [c.to_dict() for c in controls]
    warnings = _with_offers(offers, list(sheet.warnings))
    if res.selected is None:
        warnings.append("hallucination bound: no configuration certified, so the guard never commits.")
    assumptions = sheet.assumptions + _HALLUC_ASSUMPTIONS
    not_guaranteed = sheet.not_guaranteed + _HALLUC_NOT_GUARANTEED
    if joint_p:
        if res.selected is not None and n_com < prec_info["min_commits"]:
            warnings.append(f"precision bound: only {n_com} in-sample commits (fewer than {prec_info['min_commits']}).")
        assumptions += _PRECISION_ASSUMPTIONS
        not_guaranteed = tuple(a for a in not_guaranteed if not a.startswith("The error rate among commits"))             + _PRECISION_NOT_GUARANTEED
    new.sheet = replace(sheet, config_id=final.config_id, commit_threshold=float(sel.commit_p),
                        ltt_commits=n_com, ltt_wrong_commits=n_wrong, ltt_gate_blocked=int(n_blocked),
                        ltt_median_guard_risk=float(np.median(risks)) if risks else math.nan,
                        controls=tuple(controls), warnings=tuple(warnings), halluc=info, precision=prec_info,
                        offers=offers,
                        assumptions=assumptions, not_guaranteed=not_guaranteed)
    new.halluc_items = {"order": o_items, "test": t_items}  # per-item statistics (not saved)
    return new


def _joint_precision_info(res: Any, target_precision: float, delta_j: float, c0: float, base_id: str,
                          n_grid: int) -> dict[str, Any]:
    """The sheet "precision bound" block when the precision risk is part of the P15-06 joint test."""
    from fidetype.trust import precision_bound as P
    from fidetype.utils.binomial import cp_upper

    tc = dict(res.test_counts)
    oc = dict(res.order_counts)
    commits = int(tc.get("commits", 0))
    wrong = commits - int(tc.get("right", 0))
    pvs = list(res.test_pvalues)
    sel = res.selected.commit_p if res.selected is not None else math.inf
    return {
        "target_precision": target_precision,
        "beta": 1.0 - target_precision,
        "delta_p": delta_j,
        "joint_with": "halluc",
        "method": "joint with the hallucination bound: third risk of the same Learn then Test (p-value "
                  "max(p_wc, p_h, p_precision); P(Bin(commits, beta) <= wrong) on the commits of each grid point); "
                  "order from the policy-grid items, fixed-sequence test on the LTT items; one level for all risks",
        "grid": n_grid,
        "base_commit_p": _json_float(c0),
        "base_config_id": base_id,
        "min_commits": P.min_commits_needed(target_precision, delta_j),
        "feasible": res.selected is not None,
        "n_certified": len(res.certified),
        "chain_length": res.chain_length,
        "n_tested": res.n_tested,
        "n_order": res.n_order,
        "n_test": res.n_test,
        "min_commit_p": _json_float(c0),
        "order_counts": {"n": int(oc.get("n", 0)), "commits": int(oc.get("commits", 0)),
                         "wrong": int(oc.get("commits", 0)) - int(oc.get("right", 0))} if oc else {},
        "test_counts": {"n": int(tc.get("n", 0)), "commits": commits, "wrong": wrong} if tc else {},
        "test_pvalue": pvs[2] if len(pvs) == 3 and pvs[2] is not None and not math.isnan(pvs[2]) else None,
        "test_precision_lower": (1.0 - cp_upper(wrong, commits, delta_j)) if commits else None,
        "selected": _json_float(sel),
    }


_HALLUC_ASSUMPTIONS = (
    "Hallucination bound: the LLM, its fluent threshold and the grounding statistics do not change after "
    "calibration (they define the loss and the gate).",
)
_HALLUC_NOT_GUARANTEED = (
    "Hallucination bound: wrong commits that the LLM does not find fluent count only in the wrong-commit bound. "
    "The gate is not a proof that each committed word was said.",
)


def _final_offers(sheet: GuaranteeSheet, controls: list[ControlResult], n_real: int, n_real_offer: int,
                  rate: float) -> tuple[list[ControlResult], dict[str, Any] | None]:
    """The offer null control of a final (P5-02 / P15-06) guard, in the mode of the base sheet."""
    if sheet.offers is None:
        return [replace(c, n_offer=None) for c in controls], None
    offers = offer_control(n_real, n_real_offer, controls, rate=rate, mode=sheet.offers["mode"])
    if offers["mode"] == "refuse" and not offers["passed"]:
        raise NullControlError("calibration refused (offer_control='refuse'): " + _offer_warning(offers)
                               + " No configuration was produced.", controls)
    return controls, offers


def _run_controls(guard: TrustGuard, inputs: Sequence[Any], kind: str, rng: np.random.Generator, n_trials: int,
                  rate: float, null_inputs: Sequence[Any] | None) -> list[ControlResult]:
    idx = rng.integers(0, len(inputs), size=n_trials)
    allowed = int(math.floor(rate * n_trials + 1e-9))
    out: list[ControlResult] = []

    def count(xs: Iterable[Any], input_scale: str | None = None) -> tuple[int, int]:
        """(commits, offers) on the control inputs (P5-31: offers are counted in the same pass)."""
        n_c = n_o = 0
        for x in xs:
            a = guard._decide_quiet(x, input_scale).action
            n_c += a == "commit"
            n_o += a == "offer"
        return n_c, n_o

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

        n_u, o_u = count((uniform(inputs[i]) for i in idx), "logits")
        n_s, o_s = count((shuffled(inputs[i]) for i in idx), "log_probs")
        out.append(ControlResult("uniform", "near-uniform frames (log 1/V + 0.05 N(0,1)), same lengths", n_trials,
                                 n_u, allowed, o_u))
        out.append(ControlResult("shuffled", "calibration frames in a random time order", n_trials, n_s, allowed,
                                 o_s))
    else:
        def flat(x: Any) -> list[dict[str, Any]]:
            from fidetype.adapters.text_nbest import normalise_item

            its = [normalise_item(it) for it in _nbest_items(x)]
            return [{"text": it["text"], "score": 0.0} for it in its]

        n_u, o_u = count(flat(inputs[i]) for i in idx)
        out.append(ControlResult("uniform", "calibration n-best lists with equal scores and no character "
                                 "confidences (no evidence)", n_trials, n_u, allowed, o_u))
    if null_inputs:
        nl = list(null_inputs)
        a_user = int(math.floor(rate * len(nl) + 1e-9))
        n_n, o_n = count(nl)
        out.append(ControlResult("shuffled" if kind == "nbest" else "user",
                                 "your decoder output on null input (null_inputs)", len(nl), n_n, a_user, o_n))
    return out


def _fisher_less_p(k_null: int, n_null: int, k_real: int, n_real: int) -> float:
    """One-sided Fisher exact p-value of "the null offer rate is lower than the real offer rate".

    P(X <= k_null) for X ~ Hypergeometric(population n_null + n_real, successes k_null + k_real,
    draws n_null). Exact, with integer binomial coefficients.
    """
    K, N = k_null + k_real, n_null + n_real
    lo = max(0, n_null - (N - K))
    num = sum(math.comb(K, x) * math.comb(N - K, n_null - x) for x in range(lo, min(k_null, K) + 1))
    return min(1.0, num / math.comb(N, n_null))


def offer_control(n_real: int, n_real_offer: int, controls: Sequence[ControlResult], *, rate: float,
                  mode: str = "warn", max_ratio: float = OFFER_NULL_MAX_RATIO,
                  p_max: float = OFFER_NULL_P) -> dict[str, Any]:
    """The offer null control of P5-31: does the guard offer less on null input than on real input?

    ``n_real_offer`` of ``n_real`` real utterances get an OFFER (in :func:`calibrate`: the LTT items).
    Each control in ``controls`` must carry ``n_offer``. A control passes if both hold:

    1. null offer rate <= ``max_ratio`` x real offer rate (pre-stated: 0.5), and
    2. the control offers on at most ``floor(rate * n)`` inputs (the commit allowance), **or** the
       one-sided Fisher exact test "null offer rate < real offer rate" gives p <= ``p_max`` (0.05).

    Rule 1 asks for a clear drop, not only a significant one. Rule 2 asks for evidence when the null
    offers are more than a few. A guard that never offers passes (0 <= 0). The result is a JSON-ready
    dict (``GuaranteeSheet.offers``). It checks the offer list only: it does not change the commit
    guarantee.
    """
    if mode not in ("warn", "refuse"):
        raise ValueError("mode must be 'warn' or 'refuse'")
    real_rate = n_real_offer / n_real if n_real else 0.0
    rows = []
    for c in controls:
        if c.n_offer is None:
            raise ValueError(f"control {c.name!r} has no offer count (n_offer)")
        null_rate = c.n_offer / c.n if c.n else 0.0
        allowed = int(math.floor(rate * c.n + 1e-9))
        p = _fisher_less_p(c.n_offer, c.n, n_real_offer, n_real) if (n_real and c.n) else 1.0
        ratio_ok = null_rate <= max_ratio * real_rate + 1e-12
        ok = bool(ratio_ok and (c.n_offer <= allowed or p <= p_max))
        rows.append({"name": c.name, "n": c.n, "n_offer": c.n_offer, "offer_rate": round(null_rate, 6),
                     "ratio_to_real": round(null_rate / real_rate, 6) if real_rate > 0 else None,
                     "allowed_without_test": allowed, "p_value": float(f"{p:.6g}"), "passed": ok})
    return {
        "rule": (f"pass if null offer rate <= {max_ratio:g} x real offer rate, and (null offers <= floor("
                 f"{rate:g} x n) or one-sided Fisher exact p <= {p_max:g}); real = the LTT items"),
        "mode": mode, "max_ratio": max_ratio, "p_max": p_max,
        "real": {"n": n_real, "n_offer": n_real_offer, "offer_rate": round(real_rate, 6)},
        "controls": rows,
        "passed": all(r["passed"] for r in rows),
    }


def _offer_lines(o: Mapping[str, Any]) -> list[str]:
    real = o.get("real") or {}
    lines = [f"offer null control   pass if null offer rate <= {o.get('max_ratio'):g} x real rate and "
             f"(few offers or Fisher p <= {o.get('p_max'):g}); mode {o.get('mode')}",
             f"  {'real (LTT items)':<18} {real.get('n_offer')}/{real.get('n')} offers"]
    for r in o.get("controls", ()):
        lines.append(f"  {r['name']:<18} {r['n_offer']}/{r['n']} offers (p {r['p_value']:.3g}): "
                     f"{'PASS' if r['passed'] else 'FAIL'}")
    return lines


def _offer_warning(o: Mapping[str, Any]) -> str:
    bad = [f"{r['name']} {r['n_offer']}/{r['n']}" for r in o["controls"] if not r["passed"]]
    real = o["real"]
    return (f"offer null control (P5-31) FAILED: the guard offers on null input about as often as on real input "
            f"({', '.join(bad)} vs real {real['n_offer']}/{real['n']}). The offer list does not depend on the "
            "signal: do not show it as a suggestion of the user's intent. The commit guarantee is not affected.")


def _with_offers(offers: Mapping[str, Any] | None, warnings: list[str]) -> list[str]:
    """``warnings`` without an old offer warning, plus the new one if ``offers`` fails."""
    out = [w for w in warnings if not w.startswith("offer null control (P5-31)")]
    if offers is not None and not offers["passed"]:
        out.append(_offer_warning(offers))
    return out


def recheck_offer_control(guard: TrustGuard, inputs: Sequence[Any], *, null_inputs: Sequence[Any] | None = None,
                          null_trials: int | None = None) -> dict[str, Any]:
    """Run the P5-31 offer null control on a saved guard, without a new calibration.

    ``inputs`` must be the calibration inputs of the guard, in the same order (and ``null_inputs`` the
    same user null inputs, if it had them). The function makes the same split and the same control
    inputs as :func:`calibrate` from ``guard.sheet.seed``, so the commit counts must equal the sheet
    (``commits_match_sheet``). Returns :func:`offer_control` plus ``commits_match_sheet``, the LTT
    commit count and the control commit counts. The guard is not changed.
    """
    sh = guard.sheet
    if sh is None:
        raise ValueError("the guard has no guarantee sheet")
    inputs = list(inputs)
    if len(inputs) != sh.n_items:
        raise ValueError(f"inputs ({len(inputs)}) must be the {sh.n_items} calibration inputs of the guard")
    n_trials = int(null_trials if null_trials is not None else next(
        (c.n for c in sh.controls if c.name == "uniform"), 300))
    rng = np.random.default_rng(sh.seed)
    order = rng.permutation(len(inputs))
    n_com = n_off = 0
    ltt = order[sh.n_fit + sh.n_policy:]
    for i in ltt:
        a = guard._decide_quiet(inputs[int(i)]).action
        n_com += a == "commit"
        n_off += a == "offer"
    controls = _run_controls(guard, inputs, sh.input_kind, rng, n_trials, sh.null_max_commit_rate, null_inputs)
    out = offer_control(len(ltt), n_off, controls, rate=sh.null_max_commit_rate)
    out["commits_match_sheet"] = (n_com == sh.ltt_commits and
                                  [(c.name, c.n, c.n_commit) for c in controls] ==
                                  [(c.name, c.n, c.n_commit) for c in sh.controls])
    out["ltt_commits"] = n_com
    out["control_commits"] = {c.name: f"{c.n_commit}/{c.n}" for c in controls}
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


#: :func:`calibrate` has a parameter named ``offer_control``; it reaches the function by this name.
_offer_control = offer_control
