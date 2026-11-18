"""Learned commit-confidence score for the drop-in guard (P5-23).

The default drop-in guard (P14-03) commits when the calibrated
probability of the top-1 text, ``p_top1``, is at or above a threshold
that Learn then Test (LTT) certifies. ``p_top1`` uses only the n-best
scores. Other signals also tell whether the top-1 text is right: the
margin to the second candidate, the agreement of the n-best words, the
character confidences, the guard risk, the length and the acoustic and
language-model scores.

This module combines those signals into one score with a small
logistic regression. :func:`fidetype.trust.dropin.calibrate` with
``confidence="learned"`` uses it as follows:

1. The usual random split of the labelled items: fit part (temperatures,
   conformal threshold), policy-grid part and LTT part.
2. The score is fitted on the fit part and the policy-grid part only.
3. LTT certifies the threshold of the score on the LTT part only. The
   LTT items were not used to fit the score, so the LTT guarantee holds
   as for ``p_top1``: with probability at least ``1 - delta``, the
   wrong-commit rate is at most ``alpha``.
4. The commit gate (non-empty text, guard risk below 1.0) still applies.

The model is deterministic (Newton steps, numpy only), small (one
weight per feature), saved in the guard file as part of the frozen
configuration (so the ``config_id`` covers it) and named on the
guarantee sheet.

Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

__all__ = [
    "SCORE_SCHEMA",
    "FEATURES",
    "SIGNS",
    "MODEL",
    "CONFIDENCE_KINDS",
    "LearnedCommitScore",
    "commit_features",
    "fit_logistic",
]

#: Schema name of a saved learned commit score.
SCORE_SCHEMA = "fidetype.commit-score/0.1"
#: The model, in words (guard file and guarantee sheet).
MODEL = ("logistic regression, L2 on standardised features, features clipped to the fit range, "
         "sign-constrained weights (backward elimination)")
#: The values of ``calibrate(confidence=...)``.
CONFIDENCE_KINDS = ("p_top1", "learned")

#: The feature set, in this order. A missing value (for example no acoustic score) is ``nan``.
FEATURES: tuple[str, ...] = (
    "p_top1",            # calibrated posterior of the top-1 text
    "logit_p_top1",      # log(p / (1 - p)), clipped to [-12, 12]
    "margin",            # p_top1 - p_top2 (calibrated posteriors; p_top1 if one candidate)
    "nbest_entropy",     # entropy of the calibrated posteriors / log(K) (0 if K = 1)
    "word_agreement",    # posterior-weighted share of candidates that have the top-1 word at each position
    "char_conf_mean",    # mean calibrated character confidence of the top-1 text
    "char_conf_min",     # smallest calibrated character confidence of the top-1 text
    "guard_risk",        # hallucination-guard risk of the top-1 text
    "log_n_words",       # log(1 + words of the top-1 text)
    "acoustic_per_char",  # logp_acoustic of the top-1 text / characters
    "lm_per_word",       # logp_lm of the top-1 text / words
    "acoustic_gap",      # (best logp_acoustic in the n-best - top-1 logp_acoustic) / characters
    "frames_per_char",   # input frames / characters (logits input only)
)

#: Allowed sign of each weight: +1 (more evidence -> higher score), -1 (more evidence against -> lower
#: score), 0 (free). A fitted weight with the wrong sign removes its feature (backward elimination), so
#: the score is monotone in each evidence feature: an input with less evidence on every signal never
#: gets a higher score (for example null input).
SIGNS: tuple[int, ...] = (+1, +1, +1, -1, +1, +1, +1, -1, 0, +1, +1, -1, 0)

_CLIP = 12.0
_IDX = {f: i for i, f in enumerate(FEATURES)}


def _finite(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return math.nan
    return v if math.isfinite(v) else math.nan


def commit_features(p_top1: float, guard_risk: float, posteriors: Sequence[float], candidates: Sequence[Any],
                    n_frames: int | None = None) -> np.ndarray:
    """The :data:`FEATURES` of one decision, as a float vector (``nan`` = missing).

    ``posteriors`` are the calibrated posteriors of the n-best list (best
    first) and ``candidates`` its :class:`~fidetype.trust.types.Candidate`
    objects (same order, character confidences calibrated). ``n_frames``
    is the number of input frames (None for n-best input).
    """
    post = np.asarray(posteriors, dtype=np.float64)
    out = np.full(len(FEATURES), math.nan)
    p = float(p_top1)
    out[_IDX["p_top1"]] = p
    pc = min(max(p, 1e-300), 1.0)
    lg = math.log(pc) - math.log1p(-pc) if pc < 1.0 else _CLIP
    out[_IDX["logit_p_top1"]] = min(max(lg, -_CLIP), _CLIP)
    if post.size:
        out[_IDX["margin"]] = float(post[0] - post[1]) if post.size > 1 else float(post[0])
        if post.size > 1:
            q = post[post > 0]
            out[_IDX["nbest_entropy"]] = float(-(q * np.log(q)).sum() / math.log(post.size))
        else:
            out[_IDX["nbest_entropy"]] = 0.0
    out[_IDX["guard_risk"]] = float(guard_risk)
    if candidates:
        top = candidates[0]
        text = str(top.text)
        words = text.split()
        nw, nc = len(words), max(1, len(text))
        out[_IDX["log_n_words"]] = math.log1p(nw)
        if post.size == len(candidates) and nw:
            split = [str(c.text).split() for c in candidates]
            agree = 0.0
            for j, w in enumerate(words):
                agree += sum(float(pk) for cw, pk in zip(split, post) if j < len(cw) and cw[j] == w)
            out[_IDX["word_agreement"]] = agree / nw
        cc = [float(x) for x in (top.char_confidences or ())]
        if cc:
            out[_IDX["char_conf_mean"]] = float(np.mean(cc))
            out[_IDX["char_conf_min"]] = float(np.min(cc))
        ac = _finite(getattr(top, "logp_acoustic", math.nan))
        if not math.isnan(ac):
            out[_IDX["acoustic_per_char"]] = ac / nc
            acs = [_finite(getattr(c, "logp_acoustic", math.nan)) for c in candidates]
            best = max(x for x in acs if not math.isnan(x))
            out[_IDX["acoustic_gap"]] = (best - ac) / nc
        lm = _finite(getattr(top, "logp_lm", math.nan))
        if not math.isnan(lm):
            out[_IDX["lm_per_word"]] = lm / max(1, nw)
        if n_frames is not None:
            out[_IDX["frames_per_char"]] = float(n_frames) / nc
    return out


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0, max_iter: int = 100,
                 tol: float = 1e-10) -> tuple[np.ndarray, float]:
    """L2-penalised logistic regression by Newton steps (deterministic, numpy only).

    ``X``: standardised features ``(n, d)``; ``y``: 0/1 labels. The
    intercept is not penalised. Returns ``(coef, intercept)``.
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n, d = X.shape
    A = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(d + 1)
    ybar = float(np.clip(y.mean(), 1e-6, 1 - 1e-6)) if n else 0.5
    w[0] = math.log(ybar / (1 - ybar))
    pen = np.full(d + 1, float(l2))
    pen[0] = 0.0
    for _ in range(max_iter):
        z = np.clip(A @ w, -35.0, 35.0)
        p = 1.0 / (1.0 + np.exp(-z))
        g = A.T @ (p - y) + pen * w
        H = (A * (p * (1 - p))[:, None]).T @ A + np.diag(pen) + 1e-9 * np.eye(d + 1)
        step = np.linalg.solve(H, g)
        w = w - step
        if float(np.max(np.abs(step))) < tol:
            break
    return w[1:].copy(), float(w[0])


def _r(x: float) -> float:
    """Round to 12 significant digits (stable bytes in the saved file and the config id)."""
    return float(f"{float(x):.12g}")


@dataclass(frozen=True)
class LearnedCommitScore:
    """A fitted commit score: ``sigmoid(intercept + coef . (clip(x, lo, hi) - mean) / scale)``.

    ``threshold`` is the LTT-certified commit threshold on this score
    (``inf``: never commit). Each feature is first clipped to the range
    seen on the fit items (``lo``, ``hi``): the score never extrapolates
    beyond its fit data (for example on null input). Missing feature
    values count as the fit mean (standardised value 0).
    """

    features: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float
    l2: float
    #: Smallest and largest value of each feature on the fit items (-inf / inf: feature missing; no clipping).
    lo: tuple[float, ...] = ()
    hi: tuple[float, ...] = ()
    threshold: float = math.inf
    #: Items used to fit the score (the fit part + the policy-grid part of the calibration split).
    n_fit: int = 0
    #: Right top-1 texts among the fit items.
    n_fit_positive: int = 0
    #: How the threshold was certified (method, alpha, delta, n, feasible, ...).
    certification: dict[str, Any] = field(default_factory=dict)
    #: Features whose fitted weight had the wrong sign (:data:`SIGNS`) and were removed (weight 0).
    dropped: tuple[str, ...] = ()
    schema: str = SCORE_SCHEMA

    @classmethod
    def fit(cls, X: np.ndarray, y: Sequence[bool], l2: float = 1.0) -> "LearnedCommitScore":
        """Fit the score on feature rows ``X`` (``(n, len(FEATURES))``) and labels ``y`` (top-1 right)."""
        X = np.asarray(X, dtype=np.float64)
        yv = np.asarray(y, dtype=np.float64)
        if X.ndim != 2 or X.shape[1] != len(FEATURES) or X.shape[0] != yv.size:
            raise ValueError("X must be (n, len(FEATURES)) and y of length n")
        if X.shape[0] < 2:
            raise ValueError("need at least 2 items to fit the commit score")
        mean = np.zeros(X.shape[1])
        scale = np.ones(X.shape[1])
        lo = np.full(X.shape[1], -math.inf)
        hi = np.full(X.shape[1], math.inf)
        for j in range(X.shape[1]):
            ok = ~np.isnan(X[:, j])
            if ok.any():
                lo[j], hi[j] = float(X[ok, j].min()), float(X[ok, j].max())
        Z = np.zeros_like(X)
        usable = np.zeros(X.shape[1], dtype=bool)
        for j in range(X.shape[1]):
            col = X[:, j]
            ok = ~np.isnan(col)
            if ok.sum() >= 2 and float(np.std(col[ok])) > 1e-12:
                usable[j] = True
                mean[j] = float(np.mean(col[ok]))
                scale[j] = float(np.std(col[ok]))
                Z[:, j] = np.where(ok, (col - mean[j]) / scale[j], 0.0)
            # else: constant or missing feature: mean 0, scale 1, weight 0 (no effect)
        # Backward elimination of weights with the wrong sign (SIGNS): deterministic, one feature per step.
        active = [j for j in range(X.shape[1]) if usable[j]]
        sign = np.asarray(SIGNS, dtype=np.float64)
        coef = np.zeros(X.shape[1])
        while True:
            c_act, b = fit_logistic(Z[:, active], yv, l2=l2)
            coef = np.zeros(X.shape[1])
            coef[active] = c_act
            bad = [(float(-sign[j] * coef[j]), -j) for j in active if sign[j] * coef[j] < 0]
            if not bad:
                break
            active.remove(-max(bad)[1])
        dropped = tuple(FEATURES[j] for j in range(X.shape[1]) if usable[j] and j not in active)
        return cls(features=FEATURES, mean=tuple(_r(v) for v in mean), scale=tuple(_r(v) for v in scale),
                   coef=tuple(_r(v) for v in coef), intercept=_r(b), l2=float(l2),
                   lo=tuple(float(v) for v in lo), hi=tuple(float(v) for v in hi), n_fit=int(X.shape[0]),
                   n_fit_positive=int(yv.sum()), dropped=dropped)

    def score(self, x: Sequence[float]) -> float:
        """The score of one feature vector, in (0, 1)."""
        v = np.asarray(x, dtype=np.float64)
        if v.shape != (len(self.features),):
            raise ValueError(f"expected {len(self.features)} features, got shape {v.shape}")
        if self.lo:
            lo, hi = np.asarray(self.lo), np.asarray(self.hi)
            v = np.minimum(np.maximum(v, lo), hi)  # nan stays nan (missing)
        z = (v - np.asarray(self.mean)) / np.asarray(self.scale)
        z = np.where(np.isnan(z), 0.0, z)
        t = self.intercept + float(np.dot(np.asarray(self.coef), z))
        t = min(max(t, -35.0), 35.0)
        return 1.0 / (1.0 + math.exp(-t))

    def scores(self, X: np.ndarray) -> np.ndarray:
        return np.array([self.score(r) for r in np.asarray(X, dtype=np.float64)])

    def with_threshold(self, threshold: float, certification: Mapping[str, Any]) -> "LearnedCommitScore":
        from dataclasses import replace

        return replace(self, threshold=float(threshold), certification=dict(certification))

    def to_dict(self) -> dict[str, Any]:
        thr = self.threshold
        return {"schema": self.schema, "model": MODEL,
                "features": list(self.features), "mean": list(self.mean), "scale": list(self.scale),
                "coef": list(self.coef), "intercept": self.intercept, "l2": self.l2,
                "lo": [v if math.isfinite(v) else None for v in self.lo],
                "hi": [v if math.isfinite(v) else None for v in self.hi],
                "threshold": thr if math.isfinite(thr) else "inf", "n_fit": self.n_fit,
                "n_fit_positive": self.n_fit_positive, "dropped": list(self.dropped),
                "certification": dict(self.certification)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "LearnedCommitScore":
        if d.get("schema") != SCORE_SCHEMA:
            raise ValueError(f"unknown commit-score schema {d.get('schema')!r} (expected {SCORE_SCHEMA!r})")
        feats = tuple(str(f) for f in d["features"])
        if feats != FEATURES:
            raise ValueError(f"this version knows the features {FEATURES}, the file has {feats}")
        thr = d.get("threshold", "inf")
        return cls(features=feats, mean=tuple(float(v) for v in d["mean"]),
                   scale=tuple(float(v) for v in d["scale"]), coef=tuple(float(v) for v in d["coef"]),
                   intercept=float(d["intercept"]), l2=float(d["l2"]),
                   lo=tuple(-math.inf if v is None else float(v) for v in d.get("lo") or ()),
                   hi=tuple(math.inf if v is None else float(v) for v in d.get("hi") or ()),
                   threshold=math.inf if thr in ("inf", None) else float(thr), n_fit=int(d.get("n_fit", 0)),
                   n_fit_positive=int(d.get("n_fit_positive", 0)), certification=dict(d.get("certification") or {}),
                   dropped=tuple(str(f) for f in d.get("dropped") or ()))
