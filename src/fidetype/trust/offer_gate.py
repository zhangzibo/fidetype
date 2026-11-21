"""Offer gate: WITHHOLD an offer when the input shows no evidence of signal (P5-33).

The P5-31 offer null control (:func:`fidetype.trust.offer_control`) found that some guards offer on
every null input: the policy offers when it is not sure, and null input is the least sure input. An
:class:`OfferGate` stops this. It reads one evidence feature of the decision. If the value is below the
threshold, an OFFER becomes a WITHHOLD.

The gate acts **only on OFFER decisions**. It never changes a COMMIT or a WITHHOLD. So the commit bound,
the commit threshold, the commit null controls and ``config_id`` do not change. The gate is not part of
the frozen configuration; a guard file stores it under the key ``offer_gate`` (only if it is set, so old
guard files keep their bytes).

Features (higher = more evidence that the signal was read):

=================  ======  ===========================================================================
name               input   value
=================  ======  ===========================================================================
``coherence``      logits  mean ``P_t . P_(t+1)`` minus the mean ``P_s . P_t`` over all pairs s != t of
                           the frame probabilities (expected value 0 under a random frame order)
``coherence_ratio`` logits (adjacent mean) / (all-pairs mean) - 1
``peak``           logits  mean largest frame probability over the non-blank-argmax frames (0 if none)
``neg_entropy``    logits  minus the mean frame entropy over the non-blank-argmax frames (-log V if none)
``nb_share``       logits  share of frames whose argmax is not blank
``p_top1``         both    calibrated top-1 probability of the decision
``safety``         both    1 - guard risk of the decision
``margin``         nbest   (score 1 - score 2) / max(1, characters of item 1); 0 for one item
``conf_mean``      nbest   mean character confidence of item 1 (0 if none)
``char_lm``        nbest   mean log-probability per character of item 1 under a character LM (``lm=``)
``char_lm_best``   nbest   the largest ``char_lm`` over the n-best items
=================  ======  ===========================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

#: Schema tag of a saved gate.
OFFER_GATE_SCHEMA = "fidetype.offer-gate/0.1"

LOGIT_FEATURES = ("coherence", "coherence_ratio", "peak", "neg_entropy", "nb_share", "p_top1", "safety")
NBEST_FEATURES = ("p_top1", "safety", "margin", "conf_mean", "char_lm", "char_lm_best")
FEATURES = tuple(dict.fromkeys(LOGIT_FEATURES + NBEST_FEATURES))
#: Features that need a character language model (``OfferGate(..., lm=...)``).
LM_FEATURES = ("char_lm", "char_lm_best")


def coherence(lp: np.ndarray) -> tuple[float, float]:
    """``(coherence, coherence_ratio)`` of a (T, V) matrix of natural-log frame probabilities."""
    P = np.exp(np.asarray(lp, dtype=np.float64))
    T = P.shape[0]
    if T < 2:
        return 0.0, 0.0
    adj = float(np.einsum("ij,ij->i", P[:-1], P[1:]).mean())
    s = P.sum(axis=0)
    allp = (float(s @ s) - float(np.einsum("ij,ij->", P, P))) / (T * (T - 1))
    return adj - allp, (adj / allp - 1.0) if allp > 0 else 0.0


def frame_features(lp: np.ndarray, blank: int = 0) -> dict[str, float]:
    """The logits features of one input (``coherence``, ``coherence_ratio``, ``peak``, ``neg_entropy``,
    ``nb_share``)."""
    lp = np.asarray(lp, dtype=np.float64)
    T, V = lp.shape
    c, cr = coherence(lp)
    if T == 0:
        return {"coherence": c, "coherence_ratio": cr, "peak": 0.0, "neg_entropy": -math.log(V), "nb_share": 0.0}
    am = lp.argmax(axis=1)
    nb = am != blank
    P = np.exp(lp)
    if nb.any():
        peak = float(P[nb].max(axis=1).mean())
        with np.errstate(invalid="ignore"):
            ent = -(P[nb] * np.where(P[nb] > 0, lp[nb], 0.0)).sum(axis=1)
        neg_ent = -float(ent.mean())
    else:
        peak, neg_ent = 0.0, -math.log(V)
    return {"coherence": c, "coherence_ratio": cr, "peak": peak, "neg_entropy": neg_ent,
            "nb_share": float(nb.mean())}


def _lm_per_char(lm: Any, text: str) -> float:
    t = str(text)
    if not t:
        return -math.inf
    return float(lm.score_sentence(t, eos=False)) / len(t)


def nbest_features(candidates: Sequence[Any], lm: Any = None) -> dict[str, float]:
    """The n-best features ``margin``, ``conf_mean`` (and ``char_lm``, ``char_lm_best`` with ``lm``).

    ``candidates``: the raw n-best items in order (objects with ``text``, ``score`` and
    ``char_confidences``, or dicts with these keys).
    """
    def get(c: Any, k: str, d: Any = None) -> Any:
        return c.get(k, d) if isinstance(c, Mapping) else getattr(c, k, d)

    out: dict[str, float] = {"margin": 0.0, "conf_mean": 0.0}
    if not candidates:
        if lm is not None:
            out.update(char_lm=-math.inf, char_lm_best=-math.inf)
        return out
    t1 = str(get(candidates[0], "text", ""))
    if len(candidates) > 1:
        out["margin"] = (float(get(candidates[0], "score", 0.0)) - float(get(candidates[1], "score", 0.0))) / max(
            1, len(t1))
    cc = get(candidates[0], "char_confidences")
    if cc:
        out["conf_mean"] = float(np.mean([float(v) for v in cc]))
    if lm is not None:
        vals = [_lm_per_char(lm, str(get(c, "text", ""))) for c in candidates]
        out["char_lm"] = vals[0]
        out["char_lm_best"] = max(vals)
    return out


@dataclass
class OfferGate:
    """Withhold an OFFER when ``feature < threshold`` (P5-33). See the module text.

    ``lm``: a character LM with ``score_sentence(text, eos=False)`` (for example
    :class:`fidetype.lm.CharNgramLM`); needed for ``char_lm`` and ``char_lm_best`` only. It is not saved;
    ``lm_name`` names it in the file.
    """

    feature: str
    threshold: float
    lm_name: str | None = None
    note: str = ""
    lm: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.feature not in FEATURES:
            raise ValueError(f"unknown offer-gate feature {self.feature!r}; use one of {FEATURES}")
        if not math.isfinite(float(self.threshold)):
            raise ValueError("the offer-gate threshold must be finite")
        self.threshold = float(self.threshold)
        if self.feature in LM_FEATURES and self.lm_name is None:
            raise ValueError(f"feature {self.feature!r} needs lm_name= (the character LM it was fitted with)")

    def check_kind(self, kind: str) -> None:
        ok = LOGIT_FEATURES if kind == "logits" else NBEST_FEATURES
        if self.feature not in ok:
            raise ValueError(f"offer-gate feature {self.feature!r} does not apply to {kind} input")
        if self.feature in LM_FEATURES and self.lm is None:
            raise ValueError(f"offer-gate feature {self.feature!r} needs the character LM {self.lm_name!r}: "
                             "pass lm= (for example fidetype.lm.CharNgramLM.load(path))")

    def violation(self, value: float) -> str | None:
        """None if the offer may stay; else the reason text."""
        if value >= self.threshold:
            return None
        return f"offer gate: {self.feature} {value:.4g} < {self.threshold:.4g}"

    def label(self) -> str:
        return f"{self.feature} >= {self.threshold:.6g}"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"schema": OFFER_GATE_SCHEMA, "feature": self.feature, "threshold": self.threshold}
        if self.lm_name is not None:
            d["lm_name"] = self.lm_name
        if self.note:
            d["note"] = self.note
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], lm: Any = None) -> "OfferGate":
        if d.get("schema", OFFER_GATE_SCHEMA) != OFFER_GATE_SCHEMA:
            raise ValueError(f"not an offer gate (schema {d.get('schema')!r})")
        return cls(str(d["feature"]), float(d["threshold"]), d.get("lm_name"), str(d.get("note", "")), lm=lm)

    @classmethod
    def fit(cls, feature: str, real_offer_values: Sequence[float], keep: float = 0.95, **kw: Any) -> "OfferGate":
        """The P5-33 fit rule: threshold = the value at index ``floor((1 - keep) m)`` of the ascending values
        of the m real calibration OFFERs (so about ``keep`` of them stay offers)."""
        v = sorted(float(x) for x in real_offer_values if math.isfinite(float(x)))
        if not v:
            raise ValueError("the offer gate needs at least one finite real offer value")
        i = int(math.floor((1.0 - keep) * len(v) + 1e-9))
        return cls(feature, v[min(i, len(v) - 1)], **kw)
