"""Causal key-onset detectors for EMG (P4-10): ``fidetype live --timing detect``.

A real EMG board gives no key markers. A detector finds the key onsets in
the signal itself, so ``fidetype live`` can cut one key window per onset
(as with ``markers`` timing). Both detectors are causal and stream: each
call of :meth:`process` takes new samples and returns the onsets that it
can confirm now. numpy only.

Front end (:class:`FrontEnd`): first difference per channel (removes DC
and slow drift), mean square per block of ``block_s`` (5 ms), log energy
over the last ``win_blocks`` blocks (20 ms). One frame per block.

- :class:`EnvelopeDetector` (``envelope``, no training): score = mean over
  channels of the frame log energy, as a z-score against a baseline. The
  baseline mean and variance are exponential means (``tau_s``) updated
  only on frames below the threshold (so key bursts do not lift the
  baseline). The first ``warmup_s`` (1 s) only learn the baseline. A
  score that stays above ``theta`` for more than ``max_above_s`` (0.5 s,
  longer than a key) updates the baseline too, so a lasting level change
  cannot lock the detector. An onset is an upward crossing of ``theta``,
  at most one per ``refractory_s``; time = crossing time + ``lag_s``.
- :class:`LinearOnsetDetector` (learned): frames averaged to steps of
  ``step_blocks`` blocks (10 ms), causal z-score per channel
  (:class:`BlockScaler`), the last ``context`` steps stacked, a linear
  score (binary shrinkage LDA, :func:`fit_linear`). It is trained to fire
  ``delay_s`` after the onset (it looks 50 ms past the onset; the key
  window of the decoder needs ``post_s`` after the onset anyway). An onset
  is a local maximum of the score above ``theta`` (confirmed one step
  later), at most one per ``refractory_s``; time = step time -
  ``delay_s`` + ``lag_s``.

Files: ``<name>.onset.json`` (schema ``fidetype.live.onset/1``) holds the
kind, the parameters and (learned) the weights. :func:`load_onset` reads a
file or ``"envelope"`` (default parameters, tuned on KT-sEMG cal run21;
P4-10 results).

:func:`match_onsets` scores detected onsets against true ones (one-to-one
greedy matching by distance within a tolerance).

Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import math
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

__all__ = ["FrontEnd", "BlockScaler", "EnvelopeDetector", "LinearOnsetDetector", "PeakPicker", "fit_linear",
           "load_onset", "match_onsets", "ONSET_SCHEMA", "ENVELOPE_DEFAULTS"]

ONSET_SCHEMA = "fidetype.live.onset/1"

#: Default parameters of the envelope detector (tuned on KT-sEMG cal run21, P4-10; see docs/live-decode.md).
ENVELOPE_DEFAULTS: dict[str, float] = {"theta": 1.438, "tau_s": 2.0, "refractory_s": 0.06, "lag_s": -0.0042,
                                       "block_s": 0.005, "win_blocks": 4}


class FrontEnd:
    """Streaming EMG front end: diff -> block mean square -> log energy over the last ``win_blocks`` blocks."""

    def __init__(self, sample_rate: float, channels: int, block_s: float = 0.005, win_blocks: int = 4) -> None:
        self.fs = float(sample_rate)
        self.C = int(channels)
        self.block = max(1, int(round(block_s * self.fs)))
        self.win = int(win_blocks)
        self.reset()

    def reset(self) -> None:
        self._prev: np.ndarray | None = None
        self._res = np.zeros((0, self.C), np.float64)
        self._res_t = np.zeros(0)
        self._hist = np.zeros((0, self.C), np.float64)  # last win-1 block energies

    def process(self, x: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """New samples (n, C) and times (n,) -> frames (m, C) log energy and frame times (m,)."""
        x = np.asarray(x, dtype=np.float64)
        t = np.asarray(t, dtype=np.float64)
        if len(t) == 0:
            return np.zeros((0, self.C)), np.zeros(0)
        prev = x[:1] if self._prev is None else self._prev[None, :]
        d = np.diff(np.concatenate([prev, x]), axis=0)
        self._prev = x[-1].copy()
        d = np.concatenate([self._res, d])
        tt = np.concatenate([self._res_t, t])
        nb = len(d) // self.block
        cut = nb * self.block
        self._res, self._res_t = d[cut:], tt[cut:]
        if nb == 0:
            return np.zeros((0, self.C)), np.zeros(0)
        e = (d[:cut] ** 2).reshape(nb, self.block, self.C).mean(1)
        bt = tt[self.block - 1:cut:self.block]
        allb = np.concatenate([self._hist, e])
        k0 = len(self._hist)
        cs = np.concatenate([np.zeros((1, self.C)), np.cumsum(allb, axis=0)])
        idx = np.arange(k0, len(allb))
        lo = np.maximum(0, idx - self.win + 1)
        energy = (cs[idx + 1] - cs[lo]) / (idx + 1 - lo)[:, None]
        self._hist = allb[-(self.win - 1):] if self.win > 1 else allb[:0]
        return np.log(energy + 1e-12), bt


class PeakPicker:
    """Streaming local-maximum picker with a threshold and a refractory time (one step of look-ahead)."""

    def __init__(self, theta: float, refractory_s: float) -> None:
        self.theta = float(theta)
        self.refr = float(refractory_s)
        self.reset()

    def reset(self) -> None:
        self._s1 = -math.inf  # score two steps back
        self._s0: float | None = None  # score one step back (candidate)
        self._t0 = 0.0
        self._last = -math.inf

    def push(self, s: np.ndarray, t: np.ndarray) -> list[float]:
        out: list[float] = []
        for si, ti in zip(s.tolist(), t.tolist()):
            if self._s0 is not None and self._s0 >= self.theta and self._s0 >= self._s1 and self._s0 > si \
                    and self._t0 - self._last >= self.refr:
                out.append(self._t0)
                self._last = self._t0
            self._s1 = self._s0 if self._s0 is not None else -math.inf
            self._s0, self._t0 = si, ti
        return out


class BlockScaler:
    """Causal per-feature z-score; the statistics update after every ``update_n`` rows (forgetting ``lam``).

    Each row uses only statistics of earlier blocks of rows, and the result
    does not depend on how the input is cut into chunks.
    """

    def __init__(self, mu0: np.ndarray, sd0: np.ndarray, n0: float = 200.0, update_n: int = 100,
                 forget_s: float = 60.0, step_s: float = 0.01) -> None:
        self.mean = np.asarray(mu0, dtype=np.float64).copy()
        self.var = np.asarray(sd0, dtype=np.float64) ** 2
        self.n = float(n0)
        self.update_n = int(update_n)
        self.lam = math.exp(-update_n * step_s / forget_s) if forget_s > 0 else 1.0
        self._pend: list[np.ndarray] = []
        self._npend = 0

    def transform(self, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x, dtype=np.float64)
        i = 0
        while i < len(x):
            take = min(len(x) - i, self.update_n - self._npend)
            blk = x[i:i + take]
            out[i:i + take] = (blk - self.mean) / (np.sqrt(self.var) + 1e-9)
            self._pend.append(blk)
            self._npend += take
            i += take
            if self._npend >= self.update_n:
                b = np.concatenate(self._pend)
                m = float(len(b))
                n_old = self.n * self.lam
                mean_b, var_b = b.mean(0), b.var(0)
                tot = n_old + m
                delta = mean_b - self.mean
                self.mean = self.mean + delta * m / tot
                self.var = (n_old * self.var + m * var_b + delta ** 2 * n_old * m / tot) / tot
                self.n = tot
                self._pend, self._npend = [], 0
        return out


class EnvelopeDetector:
    """Envelope threshold detector (module docstring). Needs no training."""

    kind = "envelope"

    def __init__(self, sample_rate: float, channels: int, theta: float = 2.0, tau_s: float = 2.0,
                 refractory_s: float = 0.06, lag_s: float = 0.0, block_s: float = 0.005, win_blocks: int = 4,
                 warmup_s: float = 1.0, max_above_s: float = 0.5, **_: Any) -> None:
        self.fe = FrontEnd(sample_rate, channels, block_s, win_blocks)
        self.warmup, self.max_above = float(warmup_s), float(max_above_s)
        self.params = {"theta": float(theta), "tau_s": float(tau_s), "refractory_s": float(refractory_s),
                       "lag_s": float(lag_s), "block_s": float(block_s), "win_blocks": int(win_blocks),
                       "warmup_s": float(warmup_s), "max_above_s": float(max_above_s)}
        self.theta, self.tau, self.refr, self.lag = float(theta), float(tau_s), float(refractory_s), float(lag_s)
        self.reset()

    def reset(self) -> None:
        self.fe.reset()
        self._state: list[float] | None = None  # base, var, last_t, above_since, last_onset, t_first

    @staticmethod
    def envelope(frames: np.ndarray) -> np.ndarray:
        return frames.mean(1) if len(frames) else np.zeros(0)

    def run_envelope(self, e: np.ndarray, t: np.ndarray, theta: float | None = None) -> list[float]:
        """Onsets from envelope values (also used for tuning on cached envelopes)."""
        th = self.theta if theta is None else float(theta)
        out: list[float] = []
        st = self._state
        for ei, ti in zip(e.tolist(), t.tolist()):
            if st is None:
                st = [ei, 1.0, ti, math.nan, -math.inf, ti]
                continue
            base, var, last_t, above_since, last_on, t_first = st
            dt = max(ti - last_t, 1e-6)
            warm = ti - t_first < self.warmup
            a = 1.0 - math.exp(-dt / (min(self.tau, 0.2) if warm else self.tau))
            z = (ei - base) / math.sqrt(var + 1e-12)
            update = True
            if z > th and not warm:
                if math.isnan(above_since):
                    above_since = ti
                    if ti - last_on >= self.refr:
                        out.append(ti + self.lag)
                        last_on = ti
                update = ti - above_since > self.max_above
            else:
                above_since = math.nan
            if update:
                d = ei - base
                base += a * d
                var = (1 - a) * (var + a * d * d)
            st = [base, max(var, 1e-6), ti, above_since, last_on, t_first]
        self._state = st
        return out

    def process(self, x: np.ndarray, t: np.ndarray) -> list[float]:
        f, ft = self.fe.process(x, t)
        return self.run_envelope(self.envelope(f), ft)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": ONSET_SCHEMA, "kind": self.kind, "params": dict(self.params)}


class LinearOnsetDetector:
    """Learned linear detector (module docstring)."""

    kind = "linear"

    def __init__(self, sample_rate: float, channels: int, w: Sequence[float], b: float, mu0: Sequence[float],
                 sd0: Sequence[float], theta: float = 0.0, refractory_s: float = 0.06, lag_s: float = 0.0,
                 delay_s: float = 0.05, context: int = 10, step_blocks: int = 2, block_s: float = 0.005,
                 win_blocks: int = 4, forget_s: float = 60.0, **_: Any) -> None:
        self.fe = FrontEnd(sample_rate, channels, block_s, win_blocks)
        self.C = int(channels)
        self.w = np.asarray(w, dtype=np.float64)
        self.b = float(b)
        self.mu0, self.sd0 = np.asarray(mu0, np.float64), np.asarray(sd0, np.float64)
        self.context, self.step_blocks = int(context), int(step_blocks)
        if self.w.shape != (self.context * self.C,) or self.mu0.shape != (self.C,):
            raise ValueError("onset weights do not fit the channel count / context")
        self.delay, self.lag, self.forget_s = float(delay_s), float(lag_s), float(forget_s)
        self.step_s = float(block_s) * self.step_blocks
        self.params = {"theta": float(theta), "refractory_s": float(refractory_s), "lag_s": float(lag_s),
                       "delay_s": self.delay, "context": self.context, "step_blocks": self.step_blocks,
                       "block_s": float(block_s), "win_blocks": int(win_blocks), "forget_s": self.forget_s}
        self.picker = PeakPicker(theta, refractory_s)
        self.reset()

    def reset(self) -> None:
        self.fe.reset()
        self.picker.reset()
        self.scaler = BlockScaler(self.mu0, self.sd0, forget_s=self.forget_s, step_s=self.step_s)
        self._fres = np.zeros((0, self.C))
        self._fres_t = np.zeros(0)
        self._ctx = np.zeros((0, self.C))

    def steps(self, x: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Raw step features (k, C) (not standardised) and their times."""
        f, ft = self.fe.process(x, t)
        f = np.concatenate([self._fres, f])
        ft = np.concatenate([self._fres_t, ft])
        k = len(f) // self.step_blocks
        cut = k * self.step_blocks
        self._fres, self._fres_t = f[cut:], ft[cut:]
        if k == 0:
            return np.zeros((0, self.C)), np.zeros(0)
        return f[:cut].reshape(k, self.step_blocks, self.C).mean(1), ft[self.step_blocks - 1:cut:self.step_blocks]

    def stack(self, z: np.ndarray) -> tuple[np.ndarray, int]:
        """Stack the last ``context`` standardised steps per new step. Return (rows, number of leading steps dropped)."""
        allz = np.concatenate([self._ctx, z])
        n_old = len(self._ctx)
        L = self.context
        self._ctx = allz[-(L - 1):] if L > 1 else allz[:0]
        if len(allz) < L:
            return np.zeros((0, L * self.C)), len(z)
        win = np.lib.stride_tricks.sliding_window_view(allz, (L, self.C))[:, 0]  # (len-L+1, L, C)
        rows = win.reshape(len(win), L * self.C)
        first = max(0, L - 1 - n_old)  # new steps without a full context
        return rows[len(rows) - (len(z) - first):], first

    def scores(self, x: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Score (log-odds) per step with a full context, and the step times."""
        s, st = self.steps(x, t)
        if len(s) == 0:
            return np.zeros(0), np.zeros(0)
        z = self.scaler.transform(s)
        rows, drop = self.stack(z)
        return rows @ self.w + self.b, st[drop:]

    def process(self, x: np.ndarray, t: np.ndarray) -> list[float]:
        s, st = self.scores(x, t)
        return [p - self.delay + self.lag for p in self.picker.push(s, st)]

    def to_dict(self) -> dict[str, Any]:
        return {"schema": ONSET_SCHEMA, "kind": self.kind, "params": dict(self.params),
                "weights": {"w": self.w.tolist(), "b": self.b, "mu0": self.mu0.tolist(), "sd0": self.sd0.tolist()}}


def fit_linear(X: np.ndarray, y: np.ndarray, shrinkage: float = 0.1) -> tuple[np.ndarray, float]:
    """Binary shrinkage LDA: weights and bias of the log-odds ``x @ w + b`` (class prior included)."""
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y).astype(bool)
    m1, m0 = X[y].mean(0), X[~y].mean(0)
    Xc = np.where(y[:, None], X - m1, X - m0)
    S = Xc.T @ Xc / max(1, len(X) - 2)
    S = (1 - shrinkage) * S + shrinkage * np.eye(len(S)) * np.trace(S) / len(S)
    w = np.linalg.solve(S, m1 - m0)
    p1 = float(y.mean())
    b = float(-0.5 * (m1 + m0) @ w + math.log(p1 / (1 - p1)))
    return w, b


def detector_from_dict(d: Mapping[str, Any], sample_rate: float, channels: int) -> Any:
    if d.get("schema") != ONSET_SCHEMA:
        raise ValueError(f"not an onset file (schema {d.get('schema')!r}, expected {ONSET_SCHEMA!r})")
    p = dict(d.get("params") or {})
    if d.get("kind") == "envelope":
        return EnvelopeDetector(sample_rate, channels, **p)
    if d.get("kind") == "linear":
        return LinearOnsetDetector(sample_rate, channels, **dict(d["weights"]), **p)
    raise ValueError(f"unknown onset detector kind {d.get('kind')!r}")


def load_onset(spec: str | PathLike[str] | Mapping[str, Any], sample_rate: float, channels: int) -> Any:
    """``"envelope"`` (default parameters), a ``*.onset.json`` path, or a dict of that file."""
    if isinstance(spec, Mapping):
        return detector_from_dict(spec, sample_rate, channels)
    if str(spec) == "envelope":
        return EnvelopeDetector(sample_rate, channels, **ENVELOPE_DEFAULTS)
    return detector_from_dict(json.loads(Path(spec).read_text(encoding="utf-8")), sample_rate, channels)


def save_onset(det: Any, path: str | PathLike[str]) -> Path:
    p = Path(path)
    p.write_text(json.dumps(det.to_dict(), separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return p


def match_onsets(true_t: Sequence[float], det_t: Sequence[float], tol: float) -> dict[str, Any]:
    """One-to-one greedy matching by distance within ``tol`` seconds.

    Returns tp, fp, fn, recall, precision, f1, and the signed errors (det - true) of the matched pairs, plus
    ``pairs`` (index into true, index into det).
    """
    tt = np.sort(np.asarray(true_t, dtype=np.float64))
    dd = np.sort(np.asarray(det_t, dtype=np.float64))
    cand = []
    j0 = 0
    for i, x in enumerate(tt):
        while j0 < len(dd) and dd[j0] < x - tol:
            j0 += 1
        j = j0
        while j < len(dd) and dd[j] <= x + tol:
            cand.append((abs(dd[j] - x), i, j))
            j += 1
    cand.sort()
    ut, ud = np.zeros(len(tt), bool), np.zeros(len(dd), bool)
    pairs = []
    for _, i, j in cand:
        if not ut[i] and not ud[j]:
            ut[i] = ud[j] = True
            pairs.append((i, j))
    tp = len(pairs)
    fp, fn = len(dd) - tp, len(tt) - tp
    rec = tp / len(tt) if len(tt) else float("nan")
    prec = tp / len(dd) if len(dd) else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else float("nan")
    errs = np.asarray([dd[j] - tt[i] for i, j in pairs])
    return {"tp": tp, "fp": fp, "fn": fn, "recall": rec, "precision": prec, "f1": f1, "errors": errs,
            "pairs": sorted(pairs)}
