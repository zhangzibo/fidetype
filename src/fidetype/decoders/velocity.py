"""Causal continuous-velocity decoders for binned spike counts (P12-03, numpy only).

Our own implementation (no third-party decoder code):

- :class:`WienerVelocityDecoder`: ridge regression on sqrt spike counts of
  the current and the ``history - 1`` previous bins (a causal linear /
  Wiener filter). Features are standardised on the fit data. Lambda by
  blocked K-fold CV.
- :class:`ResidualScale`: a ridge model of ``log(||residual|| + eps)`` on
  ``[||v_hat||, sqrt(total count of the window)]``; ``sigma = exp(pred)``.
  The decoder sends ``sigma`` as ``std`` (same value on every axis), and
  the control trust layer calibrates it by split conformal prediction.
- :class:`StreamingVelocityDecoder`: the same model, one bin at a time (a
  ring buffer of the last ``history`` bins), for live use and latency
  measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


def lagged(counts: np.ndarray, history: int) -> np.ndarray:
    """``T x (U * history)`` features: sqrt counts of bins t, t-1, ..., t-history+1 (zeros before the start)."""
    x = np.sqrt(np.asarray(counts, dtype=float))
    T, U = x.shape
    out = np.zeros((T, U * history))
    for k in range(history):
        out[k:, k * U:(k + 1) * U] = x[:T - k] if k else x
    return out


def _ridge(X: np.ndarray, Y: np.ndarray, lam: float) -> np.ndarray:
    d = X.shape[1]
    A = X.T @ X + lam * np.eye(d)
    return np.linalg.solve(A, X.T @ Y)


def r2_score(y: np.ndarray, yhat: np.ndarray) -> float:
    """Mean over axes of 1 - SSE / SST."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    sse = ((y - yhat) ** 2).sum(0)
    sst = ((y - y.mean(0)) ** 2).sum(0)
    return float(np.mean(1.0 - sse / np.maximum(sst, 1e-12)))


def pearson(y: np.ndarray, yhat: np.ndarray) -> float:
    """Mean over axes of the Pearson correlation (0 for a constant output)."""
    rs = []
    for j in range(y.shape[1]):
        a, b = y[:, j] - y[:, j].mean(), yhat[:, j] - yhat[:, j].mean()
        den = float(np.sqrt((a * a).sum() * (b * b).sum()))
        rs.append(float((a * b).sum() / den) if den > 0 else 0.0)
    return float(np.mean(rs))


@dataclass
class WienerVelocityDecoder:
    history: int = 10
    lambdas: Sequence[float] = (1.0, 10.0, 100.0, 1000.0, 10000.0)
    folds: int = 5
    lam: float | None = None
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None
    W: np.ndarray | None = None
    b: np.ndarray | None = None
    cv: dict[float, float] = field(default_factory=dict)

    def fit(self, counts: np.ndarray, vel: np.ndarray) -> "WienerVelocityDecoder":
        X = lagged(counts, self.history)
        Y = np.asarray(vel, float)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd < 1e-9] = 1.0
        Z = (X - self.mu) / self.sd
        if self.lam is None:
            T = len(Z)
            edges = np.linspace(0, T, self.folds + 1).astype(int)
            for lam in self.lambdas:
                sc = []
                for k in range(self.folds):
                    te = np.zeros(T, bool)
                    te[edges[k]:edges[k + 1]] = True
                    ym = Y[~te].mean(0)
                    W = _ridge(Z[~te], Y[~te] - ym, lam)
                    sc.append(r2_score(Y[te], Z[te] @ W + ym))
                self.cv[float(lam)] = float(np.mean(sc))
            self.lam = max(self.cv, key=self.cv.get)
        self.b = Y.mean(0)
        self.W = _ridge(Z, Y - self.b, float(self.lam))
        return self

    def predict(self, counts: np.ndarray) -> np.ndarray:
        assert self.W is not None, "fit first"
        Z = (lagged(counts, self.history) - self.mu) / self.sd
        return Z @ self.W + self.b

    def zero_input_output(self) -> np.ndarray:
        """The decoder output on all-zero input (the no-signal reference of FEP-0005 section 6 rule 1)."""
        return self.predict(np.zeros((self.history, len(self.mu) // self.history)))[-1]


def window_total(counts: np.ndarray, history: int) -> np.ndarray:
    """Total spike count of the current and the ``history - 1`` previous bins."""
    c = np.asarray(counts, float).sum(1)
    cs = np.concatenate([[0.0], np.cumsum(c)])
    T = len(c)
    lo = np.maximum(0, np.arange(T) - history + 1)
    return cs[np.arange(T) + 1] - cs[lo]


@dataclass
class ResidualScale:
    eps: float = 1.0
    lam: float = 1.0
    coef: np.ndarray | None = None

    @staticmethod
    def features(v_hat: np.ndarray, total: np.ndarray) -> np.ndarray:
        return np.column_stack([np.ones(len(v_hat)), np.linalg.norm(v_hat, axis=1), np.sqrt(np.maximum(total, 0.0))])

    def fit(self, v_true: np.ndarray, v_hat: np.ndarray, total: np.ndarray) -> "ResidualScale":
        F = self.features(v_hat, total)
        y = np.log(np.linalg.norm(np.asarray(v_true) - np.asarray(v_hat), axis=1) + self.eps)
        A = F.T @ F + self.lam * np.diag([0.0, 1.0, 1.0])
        self.coef = np.linalg.solve(A, F.T @ y)
        return self

    def sigma(self, v_hat: np.ndarray, total: np.ndarray) -> np.ndarray:
        assert self.coef is not None, "fit first"
        return np.exp(self.features(v_hat, total) @ self.coef)


class StreamingVelocityDecoder:
    """One bin at a time: ``step(counts_bin) -> (v_hat, sigma, window total)``."""

    def __init__(self, dec: WienerVelocityDecoder, scale: ResidualScale | None = None) -> None:
        assert dec.W is not None
        self.dec, self.scale = dec, scale
        self.U = len(dec.mu) // dec.history
        self.buf = np.zeros((dec.history, self.U))
        self.tot = np.zeros(dec.history)

    def step(self, counts_bin: np.ndarray) -> tuple[np.ndarray, float | None, float]:
        c = np.asarray(counts_bin, float)
        self.buf = np.roll(self.buf, 1, axis=0)
        self.buf[0] = np.sqrt(c)
        self.tot = np.roll(self.tot, 1)
        self.tot[0] = c.sum()
        z = (self.buf.reshape(-1) - self.dec.mu) / self.dec.sd
        v = z @ self.dec.W + self.dec.b
        total = float(self.tot.sum())
        sig = float(self.scale.sigma(v[None, :], np.array([total]))[0]) if self.scale is not None else None
        return v, sig, total


__all__ = ["ResidualScale", "StreamingVelocityDecoder", "WienerVelocityDecoder", "lagged", "pearson", "r2_score",
           "window_total"]
