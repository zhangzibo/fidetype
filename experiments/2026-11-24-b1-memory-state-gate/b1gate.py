"""B1 decoder, calibration, trust gate and metrics (our own NumPy / SciPy code, Apache-2.0).

* decoder: L2 logistic regression, objective 0.5 ||w||^2 + C sum_i c_i logloss_i, C = 2.4e-4,
  class weights n / (2 n_class), unpenalised intercept, L-BFGS;
* Platt scaling on the order words of the subject;
* gates G+ / G-: ``fidetype.trust.precision_bound.precision_ltt`` pooled over subjects;
* OFFER: binary split conformal (LAC) with ``fidetype.trust.conformal.conformal_quantile``;
* metrics: AUC, Clopper-Pearson, subject-cluster bootstrap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import optimize, special, stats

from fidetype.trust.conformal import conformal_quantile
from fidetype.trust.precision_bound import DEFAULT_COMMIT_P_GRID, PrecisionItem, precision_ltt
from fidetype.utils.binomial import cp_upper

C_EZZYAT = 2.4e-4
ALPHA = 0.10
DELTA = 0.10

# ------------------------------------------------------------------------------------------ decoder


@dataclass
class LogReg:
    w: np.ndarray
    b: float

    def logit(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(X, dtype=np.float64) @ self.w + self.b


def class_weights(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y).astype(int)
    n = y.size
    n1 = int(y.sum())
    n0 = n - n1
    if n0 == 0 or n1 == 0:
        raise ValueError("training labels have one class only")
    return np.where(y == 1, n / (2.0 * n1), n / (2.0 * n0))


def fit_logreg(X: np.ndarray, y: np.ndarray, C: float = C_EZZYAT) -> LogReg:
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    cw = class_weights(y)
    d = X.shape[1]

    def f(theta: np.ndarray) -> tuple[float, np.ndarray]:
        w, b = theta[:d], theta[d]
        z = X @ w + b
        # logloss = log(1 + exp(-s z)), s = 2y - 1
        s = 2.0 * y - 1.0
        ll = np.logaddexp(0.0, -s * z)
        g = -s * special.expit(-s * z) * cw          # d logloss / dz, weighted
        val = 0.5 * float(w @ w) + C * float(cw @ ll)
        grad = np.empty(d + 1)
        grad[:d] = w + C * (X.T @ g)
        grad[d] = C * g.sum()
        return val, grad

    r = optimize.minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B",
                          options={"maxiter": 5000, "gtol": 1e-10, "ftol": 1e-15})
    return LogReg(r.x[:d].copy(), float(r.x[d]))


@dataclass
class Platt:
    a: float
    b: float

    def __call__(self, s: np.ndarray) -> np.ndarray:
        return special.expit(self.a * np.asarray(s, dtype=np.float64) + self.b)


def fit_platt(s: np.ndarray, y: np.ndarray) -> Platt:
    """2-parameter logistic of the score, maximum likelihood (L-BFGS)."""
    s = np.asarray(s, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    sc = max(float(np.std(s)), 1e-12)

    def f(t: np.ndarray) -> tuple[float, np.ndarray]:
        z = t[0] * (s / sc) + t[1]
        q = special.expit(z)
        val = float(np.sum(np.logaddexp(0.0, z) - y * z))
        g = q - y
        return val, np.array([float(g @ (s / sc)), float(g.sum())])

    m = float(np.clip(y.mean(), 1e-3, 1 - 1e-3)) if y.size else 0.5
    r = optimize.minimize(f, np.array([0.0, math.log(m / (1 - m))]), jac=True, method="L-BFGS-B")
    return Platt(float(r.x[0] / sc), float(r.x[1]))


def auc(score: np.ndarray, y: np.ndarray) -> float:
    y = np.asarray(y).astype(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return math.nan
    r = stats.rankdata(np.asarray(score, dtype=np.float64))
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


# --------------------------------------------------------------------------------------------- gates


def _items(p: np.ndarray, wrong: np.ndarray) -> list[PrecisionItem]:
    return [PrecisionItem(True, float(pi), bool(wi)) for pi, wi in zip(p, wrong)]


def fit_gate(p_order: np.ndarray, wrong_order: np.ndarray, p_cert: np.ndarray, wrong_cert: np.ndarray,
             target: float, delta: float = DELTA) -> dict:
    """Precision LTT on the 1.00 .. 0.00 grid. ``lambda = None`` -> the gate never flags."""
    res = precision_ltt(_items(p_order, wrong_order), _items(p_cert, wrong_cert), DEFAULT_COMMIT_P_GRID,
                        target_precision=float(target), delta=float(delta))
    d = res.to_dict()
    return {"lambda": res.selected, "certified_any": len(res.certified) > 0, "n_certified": len(res.certified),
            "target_precision": float(target), "delta": float(delta), "n_order": d["n_order"], "n_cert": d["n_test"],
            "order_counts": d["order_counts"], "cert_counts": d["test_counts"], "cert_pvalue": d["test_pvalue"]}


def flags(p: np.ndarray, lam: float | None) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    if lam is None:
        return np.zeros(p.shape, dtype=bool)
    return p >= float(lam)


def fit_offer(p_cert: np.ndarray, y_cert: np.ndarray, alpha: float = ALPHA) -> float:
    """LAC split conformal threshold on the binary posterior [1 - p, p]."""
    p = np.asarray(p_cert, dtype=np.float64)
    y = np.asarray(y_cert).astype(int)
    scores = np.where(y == 1, 1.0 - p, p)
    return float(conformal_quantile(scores.tolist(), alpha))


def offer_sets(p: np.ndarray, q: float) -> tuple[np.ndarray, np.ndarray]:
    """Boolean membership (in_recall, in_forget) of the conformal sets."""
    p = np.asarray(p, dtype=np.float64)
    return (1.0 - p) <= q + 1e-12, p <= q + 1e-12


# ------------------------------------------------------------------------------------------- metrics


def cp_up(k: int, n: int, level: float = 0.95) -> float | None:
    """One-sided Clopper-Pearson upper bound (confidence ``level``); None for n = 0."""
    return None if n == 0 else float(cp_upper(int(k), int(n), 1.0 - level))


def cp_lo(k: int, n: int, level: float = 0.95) -> float | None:
    return None if n == 0 else float(1.0 - cp_upper(int(n - k), int(n), 1.0 - level))


def cluster_bootstrap(per_subject: dict[str, np.ndarray], stat, n_boot: int = 10_000, seed: int = 0) -> np.ndarray:
    """Resample subjects with replacement; ``stat(sums)`` maps summed counts to a value (nan allowed)."""
    keys = list(per_subject)
    S = len(per_subject[keys[0]])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, S, size=(n_boot, S))
    sums = {k: np.asarray(v, dtype=np.float64)[idx].sum(axis=1) for k, v in per_subject.items()}
    return np.asarray(stat(sums), dtype=np.float64)


def pct(a: np.ndarray, q: float) -> float | None:
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    return None if a.size == 0 else float(np.percentile(a, q))


def gate_metrics(flag_s: list[np.ndarray], y_s: list[np.ndarray], wrong_when: int, n_boot: int = 10_000) -> dict:
    """Pooled flag metrics on test with CP (word counts) and subject-cluster bootstrap bounds.

    ``wrong_when``: the label value that makes a flag wrong (0 for G+, 1 for G-). ``base`` is the
    rate of the label the gate claims (recall for G+, forget for G-).
    """
    fl = np.array([int(np.sum(f)) for f in flag_s])
    n = np.array([len(f) for f in flag_s])
    wr = np.array([int(np.sum(f & (y == wrong_when))) for f, y in zip(flag_s, y_s)])
    pos = np.array([int(np.sum(y != wrong_when)) for y in y_s])     # words for which a flag would be right
    F, N, W, P = int(fl.sum()), int(n.sum()), int(wr.sum()), int(pos.sum())
    base = P / N if N else math.nan
    out = {"words": N, "flags": F, "wrong": W, "flag_rate": F / N if N else math.nan,
           "wrong_rate": (W / F) if F else None, "precision": (1 - W / F) if F else None,
           "base_rate": base, "precision_minus_base": ((1 - W / F) - base) if F else None,
           "flag_rate_cp_upper95": cp_up(F, N), "flag_rate_cp_lower95": cp_lo(F, N),
           "wrong_rate_cp_upper95": cp_up(W, F), "precision_cp_lower95": (1 - cp_up(W, F)) if F else None,
           "n_subjects_with_flags": int((fl > 0).sum())}
    per = {"f": fl, "n": n, "w": wr, "p": pos}
    with np.errstate(invalid="ignore", divide="ignore"):
        fr = cluster_bootstrap(per, lambda s: s["f"] / s["n"], n_boot)
        wrr = cluster_bootstrap(per, lambda s: np.where(s["f"] > 0, s["w"] / s["f"], np.nan), n_boot)
        pmb = cluster_bootstrap(per, lambda s: np.where(s["f"] > 0, 1 - s["w"] / s["f"], np.nan) - s["p"] / s["n"],
                                n_boot)
    out["boot"] = {
        "n_boot": n_boot, "zero_flag_resamples": int(np.sum(~np.isfinite(wrr))),
        "flag_rate": [pct(fr, 2.5), pct(fr, 97.5)], "flag_rate_upper_1s95": pct(fr, 95.0),
        "wrong_rate": [pct(wrr, 2.5), pct(wrr, 97.5)], "wrong_rate_upper_1s95": pct(wrr, 95.0),
        "precision_minus_base": [pct(pmb, 2.5), pct(pmb, 97.5)], "precision_minus_base_lower_1s95": pct(pmb, 5.0),
    }
    return out


def ttest_vs_half(aucs: list[float]) -> dict:
    a = np.asarray([x for x in aucs if np.isfinite(x)], dtype=np.float64)
    if a.size < 2:
        return {"n": int(a.size), "mean": float(a.mean()) if a.size else None, "sd": None, "t": None,
                "p_two_sided": None, "p_one_sided": None}
    t2 = stats.ttest_1samp(a, 0.5)
    t1 = stats.ttest_1samp(a, 0.5, alternative="greater")
    return {"n": int(a.size), "mean": float(a.mean()), "sd": float(a.std(ddof=1)), "t": float(t2.statistic),
            "p_two_sided": float(t2.pvalue), "p_one_sided": float(t1.pvalue)}
