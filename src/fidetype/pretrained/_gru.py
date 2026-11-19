"""NumPy inference of our causal GRU-CTC phoneme decoders (T15 M4-13, T12 v2). Our own code (Apache-2.0).

Same maths as the training modules, in eval mode:

- T15 M4-13: :mod:`fidetype.decoders.lookahead_gru` (``build_torch_model``), lookahead ``L`` bins;
- T12 v2: ``experiments/2026-11-13-confirmatory-t12-v2/train_decoder.py`` (``GRUDecoder``): the same
  pieces without the lookahead branch.

Pipeline for one utterance ``x`` (T, C) of 20 ms bins: causal half-Gaussian smoothing -> per-session
affine + softsign (the "day layer") -> patches of ``patch`` bins every ``stride`` bins -> a stack of
unidirectional GRUs -> linear output (plus the lookahead head for M4-13). The input projection of
each GRU layer runs as one matrix product over all steps; only the recurrence is a loop. This gives
the same numbers as :func:`fidetype.decoders.lookahead_gru.forward_numpy` (tested), but is faster.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from fidetype.decoders.lookahead_gru import causal_kernel

__all__ = ["gru_ctc_logits", "n_steps", "log_softmax", "required_keys"]


def required_keys(layers: int, lookahead: bool) -> list[str]:
    keys = ["day_W", "day_b", "out.weight", "out.bias"]
    for i in range(layers):
        keys += [f"grus.{i}.weight_ih_l0", f"grus.{i}.weight_hh_l0", f"grus.{i}.bias_ih_l0", f"grus.{i}.bias_hh_l0"]
    if lookahead:
        keys += ["la_in.weight", "la_in.bias", "la_out.weight", "la_out.bias", "la_emb.weight"]
    return keys


def n_steps(T: int, patch: int, stride: int) -> int:
    return max(0, (T - patch) // stride + 1)


def log_softmax(x: np.ndarray) -> np.ndarray:
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def gru_ctc_logits(p: Mapping[str, np.ndarray], x: np.ndarray, session: int, *, patch: int, stride: int, layers: int,
                   hidden: int, smooth_sd: float, la_bins: int | None = None, la_max: int = 0) -> np.ndarray:
    """Logits (K, n_out) of one utterance ``x`` (T, C). ``la_bins`` None: no lookahead head (T12 v2)."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim != 2:
        raise ValueError(f"input must be 2-D (T, C), got shape {x.shape}")
    T, C = x.shape
    if C != p["day_W"].shape[1]:
        raise ValueError(f"input has {C} channels; the model needs {p['day_W'].shape[1]}")
    if not 0 <= session < p["day_W"].shape[0]:
        raise ValueError(f"session index {session} is out of range 0..{p['day_W'].shape[0] - 1}")
    K = n_steps(T, patch, stride)
    n_out = p["out.weight"].shape[0]
    if K == 0:
        return np.zeros((0, n_out), np.float32)
    k = causal_kernel(smooth_sd)
    W = k.size
    xx = np.concatenate([np.zeros((W - 1, C), np.float32), x], 0)
    y = np.zeros((T, C), np.float32)
    for i in range(W):
        y += k[i] * xx[i:i + T]
    z = y @ p["day_W"][session] + p["day_b"][session]
    z = (z / (1.0 + np.abs(z))).astype(np.float32)
    # patches: step k reads bins [stride k, stride k + patch), flattened bin-major (bin, channel)
    win = np.lib.stride_tricks.sliding_window_view(z, patch, axis=0)[::stride][:K]  # (K, C, patch)
    a = np.ascontiguousarray(win.transpose(0, 2, 1)).reshape(K, patch * C)
    H = hidden
    for li in range(layers):
        Wi, Wh = p[f"grus.{li}.weight_ih_l0"], p[f"grus.{li}.weight_hh_l0"]
        bi, bh = p[f"grus.{li}.bias_ih_l0"], p[f"grus.{li}.bias_hh_l0"]
        gi_all = a @ Wi.T + bi  # (K, 3H), gate order r, z, n (torch)
        WhT = np.ascontiguousarray(Wh.T)
        h = np.zeros(H, np.float32)
        out = np.empty((K, H), np.float32)
        for t in range(K):
            gi = gi_all[t]
            gh = h @ WhT + bh
            r = _sigmoid(gi[:H] + gh[:H])
            zg = _sigmoid(gi[H:2 * H] + gh[H:2 * H])
            n = np.tanh(gi[2 * H:] + r * gh[2 * H:])
            h = ((1.0 - zg) * n + zg * h).astype(np.float32)
            out[t] = h
        a = out
    if la_bins is None:
        return (a @ p["out.weight"].T + p["out.bias"]).astype(np.float32)
    if not 0 <= la_bins <= la_max:
        raise ValueError(f"lookahead {la_bins} bins is out of range 0..{la_max}")
    la_proj = p["la_in.weight"].shape[0]
    base = p["la_out.bias"] + p["la_emb.weight"][la_bins]
    f = np.tile(base, (K, 1)).astype(np.float32)
    if la_bins > 0:
        u = z @ p["la_in.weight"].T + p["la_in.bias"]  # (T, la_proj)
        Wo = p["la_out.weight"]  # (H, la_max * la_proj)
        for t in range(K):
            tk = stride * t + patch - 1
            n_vis = min(la_bins, T - 1 - tk)
            if n_vis > 0:
                fut = np.zeros((la_max, la_proj), np.float32)
                fut[:n_vis] = u[tk + 1: tk + 1 + n_vis]
                f[t] += fut.reshape(-1) @ Wo.T
    return ((a + np.tanh(f)) @ p["out.weight"].T + p["out.bias"]).astype(np.float32)
