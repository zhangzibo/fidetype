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
``nb_coherence``   logits  ``coherence`` of the non-blank columns only (the blank column is left out, the
                           rows are not normalised again); P14-54
``peak``           logits  mean largest frame probability over the non-blank-argmax frames (0 if none)
``neg_entropy``    logits  minus the mean frame entropy over the non-blank-argmax frames (-log V if none)
``nb_share``       logits  share of frames whose argmax is not blank
``time_asym``      logits  ``sum D^3 / sum |D|^3`` of the frame differences ``D = P_(t+1) - P_t`` (all
                           columns); it changes sign when the frame order is reversed (P14-57)
``nb_time_asym``   logits  ``time_asym`` of the non-blank columns only (P14-57)
``nb_decay_asym``  logits  ``sum P_t P_(t+1) (P_t - P_(t+1)) / sum P_t P_(t+1) |P_t - P_(t+1)|`` over the
                           non-blank columns: > 0 when a high probability falls more slowly than it rises;
                           it changes sign when the frame order is reversed (P14-57)
``lm_direction``   logits  (forward minus backward) character-LM log-probability per character of the
                           greedy CTC text of the frames: ``(log p(s) - log p(reverse(s))) / (len(s) + 1)``,
                           ``s`` = the normalised greedy text, end marker included (``lm=``). It changes sign
                           exactly when the frame order is reversed; 0 for an empty text (P5-36)
``lm_beam_direction`` logits (forward minus reversed) best-beam score of the LM-beam readout:
                           ``(S(x) - S(rev x)) / ((n(x) + n(rev x)) / 2 + 1)``, ``S`` = the total score of
                           the best beam (acoustic + LM + length bonus, end marker included), ``n`` = its
                           tokens, ``rev x`` = the frames in reverse order (``readout=``). It changes sign
                           exactly when the frame order is reversed; 0 for no frames. It costs two beam
                           searches per scored decision (P5-36b), or one when the guard decodes with the
                           same readout (its search cache gives the forward search; P5-38)
``p_top1``         both    calibrated top-1 probability of the decision
``safety``         both    1 - guard risk of the decision
``margin``         nbest   (score 1 - score 2) / max(1, characters of item 1); 0 for one item
``conf_mean``      nbest   mean character confidence of item 1 (0 if none)
``char_lm``        nbest   mean log-probability per character of item 1 under a character LM (``lm=``)
``char_lm_best``   nbest   the largest ``char_lm`` over the n-best items
=================  ======  ===========================================================================

A feature name with a leading ``-`` (for example ``-time_asym``) is the negated feature: the gate withholds
an offer when ``-value < threshold`` (P14-57; for the time-direction features the sign of a decoder is a
property of the decoder and is chosen on calibration data).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

#: Schema tag of a saved gate.
OFFER_GATE_SCHEMA = "fidetype.offer-gate/0.1"

LOGIT_FEATURES = ("coherence", "coherence_ratio", "nb_coherence", "peak", "neg_entropy", "nb_share", "time_asym",
                  "nb_time_asym", "nb_decay_asym", "lm_direction", "lm_beam_direction", "p_top1", "safety")
NBEST_FEATURES = ("p_top1", "safety", "margin", "conf_mean", "char_lm", "char_lm_best")
FEATURES = tuple(dict.fromkeys(LOGIT_FEATURES + NBEST_FEATURES))
#: Features that need a character language model (``OfferGate(..., lm=...)``).
LM_FEATURES = ("char_lm", "char_lm_best", "lm_direction", "lm_beam_direction")
#: Features that need an LM-beam readout (``OfferGate(..., readout=...)``), P5-36b.
BEAM_FEATURES = ("lm_beam_direction",)


#: The logits features that :func:`frame_features` computes.
FRAME_FEATURES = ("coherence", "coherence_ratio", "nb_coherence", "peak", "neg_entropy", "nb_share", "time_asym",
                  "nb_time_asym", "nb_decay_asym")
#: The frame features that change sign when the frame order is reversed (P14-57).
DIRECTION_FEATURES = ("time_asym", "nb_time_asym", "nb_decay_asym")


def base_feature(name: str) -> tuple[str, float]:
    """``(feature, sign)`` of a gate feature name: ``"-x"`` -> ``("x", -1.0)``, ``"x"`` -> ``("x", 1.0)``."""
    return (name[1:], -1.0) if name.startswith("-") else (name, 1.0)


def time_asymmetry(lp: np.ndarray, drop: int | None = None) -> tuple[float, float]:
    """``(time_asym, decay_asym)`` of a (T, V) matrix of natural-log frame probabilities (P14-57).

    ``time_asym`` = ``sum D^3 / sum |D|^3`` with ``D = P[1:] - P[:-1]``; ``decay_asym`` =
    ``sum P_t P_(t+1) (P_t - P_(t+1)) / sum P_t P_(t+1) |P_t - P_(t+1)|``. Both are in [-1, 1], both are 0
    when no frame changes, and both change sign (exactly) when the frame order is reversed. ``drop``: a
    column to leave out (the blank).
    """
    P = np.exp(np.asarray(lp, dtype=np.float64))
    if drop is not None and P.ndim == 2 and P.shape[1] > 1:
        P = np.delete(P, int(drop), axis=1)
    if P.shape[0] < 2:
        return 0.0, 0.0
    D = P[1:] - P[:-1]
    den = float((np.abs(D) ** 3).sum())
    ta = float((D ** 3).sum()) / den if den > 0 else 0.0
    W = P[:-1] * P[1:]
    den2 = float((W * np.abs(D)).sum())
    da = float((W * -D).sum()) / den2 if den2 > 0 else 0.0
    return ta, da


def coherence(lp: np.ndarray, drop: int | None = None) -> tuple[float, float]:
    """``(coherence, coherence_ratio)`` of a (T, V) matrix of natural-log frame probabilities.

    ``drop``: a column to leave out (the blank, for ``nb_coherence``).
    """
    P = np.exp(np.asarray(lp, dtype=np.float64))
    if drop is not None and P.ndim == 2 and P.shape[1] > 1:
        P = np.delete(P, int(drop), axis=1)
    T = P.shape[0]
    if T < 2:
        return 0.0, 0.0
    adj = float(np.einsum("ij,ij->i", P[:-1], P[1:]).mean())
    s = P.sum(axis=0)
    allp = (float(s @ s) - float(np.einsum("ij,ij->", P, P))) / (T * (T - 1))
    return adj - allp, (adj / allp - 1.0) if allp > 0 else 0.0


def frame_features(lp: np.ndarray, blank: int = 0) -> dict[str, float]:
    """The logits features of one input (:data:`FRAME_FEATURES`)."""
    lp = np.asarray(lp, dtype=np.float64)
    T, V = lp.shape
    c, cr = coherence(lp)
    nbc = coherence(lp, drop=blank)[0]
    ta = time_asymmetry(lp)[0]
    nbta, nbda = time_asymmetry(lp, drop=blank)
    direction = {"time_asym": ta, "nb_time_asym": nbta, "nb_decay_asym": nbda}
    if T == 0:
        return {"coherence": c, "coherence_ratio": cr, "nb_coherence": nbc, "peak": 0.0,
                "neg_entropy": -math.log(V), "nb_share": 0.0, **direction}
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
    return {"coherence": c, "coherence_ratio": cr, "nb_coherence": nbc, "peak": peak, "neg_entropy": neg_ent,
            "nb_share": float(nb.mean()), **direction}


def greedy_text(lp: np.ndarray, vocab: Sequence[str], blank: int = 0) -> str:
    """The greedy CTC text of a (T, V) matrix: per-frame argmax, runs joined, blank removed, tokens joined."""
    a = np.asarray(lp).argmax(axis=1) if np.asarray(lp).shape[0] else np.zeros(0, np.int64)
    if a.size == 0:
        return ""
    keep = np.concatenate([[True], a[1:] != a[:-1]])
    a = a[keep]
    return "".join(str(vocab[int(i)]) for i in a[a != blank])


def lm_direction(lp: np.ndarray, vocab: Sequence[str], lm: Any, blank: int = 0) -> float:
    """The ``lm_direction`` feature (P5-36): ``(log p(s) - log p(reverse(s))) / (len(s) + 1)``.

    ``s`` = :func:`fidetype.streams.vocab.normalize_text` of :func:`greedy_text`; ``lm``: a character LM with
    ``score_sentence(text, eos=True, normalize=False)`` (for example :class:`fidetype.lm.CharNgramLM`). The
    greedy text of the reversed frames is the reversed text, and the normalisation keeps that, so the value
    changes sign exactly when the frame order is reversed. > 0: the text reads better forward than backward.
    """
    from fidetype.streams.vocab import normalize_text

    s = normalize_text(greedy_text(lp, vocab, blank))
    if not s:
        return 0.0
    f = float(lm.score_sentence(s, eos=True, normalize=False))
    r = float(lm.score_sentence(s[::-1], eos=True, normalize=False))
    return (f - r) / (len(s) + 1)


def beam_score(lp: np.ndarray, readout: Any) -> tuple[float, int]:
    """``(score, tokens)`` of the best beam of ``readout`` on a (T, V) matrix (no gate; P5-36b).

    ``readout``: an object with ``hyps(log_probs, n, use_gate=False)`` that returns hypotheses with ``score``
    and ``tokens`` (for example :class:`fidetype.pretrained.lmreadout.LmReadout`). ``(-inf, 0)`` if the search
    gives no hypothesis.
    """
    hs = readout.hyps(np.asarray(lp, dtype=np.float64), 1, use_gate=False)
    if not hs:
        return -math.inf, 0
    return float(hs[0].score), len(hs[0].tokens)


def lm_beam_direction(lp: np.ndarray, readout: Any, *, details: bool = False) -> Any:
    """The ``lm_beam_direction`` feature (P5-36b): ``(S(x) - S(rev x)) / ((n(x) + n(rev x)) / 2 + 1)``.

    ``S``, ``n``: :func:`beam_score` of the frames ``x`` and of the frames in reverse order. The normaliser is
    the same for ``x`` and ``rev x``, so the value changes sign exactly when the frame order is reversed.
    > 0: the frames decode better forward than backward. 0 for no frames (and if neither search gives a
    hypothesis). ``details=True`` returns ``(value, {"s_fwd", "s_rev", "n_fwd", "n_rev", "T"})``.
    """
    lp = np.asarray(lp, dtype=np.float64)
    T = int(lp.shape[0]) if lp.ndim == 2 else 0
    if T == 0:
        v, d = 0.0, {"s_fwd": 0.0, "s_rev": 0.0, "n_fwd": 0, "n_rev": 0, "T": 0}
    else:
        sf, nf = beam_score(lp, readout)
        sr, nr = beam_score(np.ascontiguousarray(lp[::-1]), readout)
        v = 0.0 if sf == sr else (sf - sr) / ((nf + nr) / 2.0 + 1.0)  # sf == sr: also both -inf
        d = {"s_fwd": sf, "s_rev": sr, "n_fwd": nf, "n_rev": nr, "T": T}
    return (float(v), d) if details else float(v)


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
    :class:`fidetype.lm.CharNgramLM`); needed for ``char_lm``, ``char_lm_best`` and ``lm_direction``. It is
    not saved; ``lm_name`` names it in the file. ``readout``: an LM-beam readout (for example
    :class:`fidetype.pretrained.lmreadout.LmReadout`); needed for ``lm_beam_direction`` only (P5-36b). It is
    not saved; ``lm_name`` names its LM in the file.
    """

    feature: str
    threshold: float
    lm_name: str | None = None
    note: str = ""
    lm: Any = field(default=None, repr=False, compare=False)
    readout: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if base_feature(self.feature)[0] not in FEATURES:
            raise ValueError(f"unknown offer-gate feature {self.feature!r}; use one of {FEATURES}")
        if not math.isfinite(float(self.threshold)):
            raise ValueError("the offer-gate threshold must be finite")
        self.threshold = float(self.threshold)
        if self.base in LM_FEATURES and self.lm_name is None:
            raise ValueError(f"feature {self.feature!r} needs lm_name= (the character LM it was fitted with)")

    @property
    def base(self) -> str:
        """The feature name without a leading ``-``."""
        return base_feature(self.feature)[0]

    def value(self, features: Mapping[str, float]) -> float:
        """The gate value of one decision from its feature dict (negated for a ``-`` feature)."""
        name, sign = base_feature(self.feature)
        return sign * float(features[name])

    def check_kind(self, kind: str) -> None:
        ok = LOGIT_FEATURES if kind == "logits" else NBEST_FEATURES
        if self.base not in ok:
            raise ValueError(f"offer-gate feature {self.feature!r} does not apply to {kind} input")
        if self.base in BEAM_FEATURES:
            if self.readout is None:
                raise ValueError(f"offer-gate feature {self.feature!r} needs an LM-beam readout with the LM "
                                 f"{self.lm_name!r}: pass readout= (for example model.lm_readout())")
        elif self.base in LM_FEATURES and self.lm is None:
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
    def from_dict(cls, d: Mapping[str, Any], lm: Any = None, readout: Any = None) -> "OfferGate":
        if d.get("schema", OFFER_GATE_SCHEMA) != OFFER_GATE_SCHEMA:
            raise ValueError(f"not an offer gate (schema {d.get('schema')!r})")
        return cls(str(d["feature"]), float(d["threshold"]), d.get("lm_name"), str(d.get("note", "")), lm=lm,
                   readout=readout)

    @classmethod
    def fit(cls, feature: str, real_offer_values: Sequence[float], keep: float = 0.95, **kw: Any) -> "OfferGate":
        """The P5-33 fit rule: threshold = the value at index ``floor((1 - keep) m)`` of the ascending values
        of the m real calibration OFFERs (so about ``keep`` of them stay offers)."""
        v = sorted(float(x) for x in real_offer_values if math.isfinite(float(x)))
        if not v:
            raise ValueError("the offer gate needs at least one finite real offer value")
        i = int(math.floor((1.0 - keep) * len(v) + 1e-9))
        return cls(feature, v[min(i, len(v) - 1)], **kw)
