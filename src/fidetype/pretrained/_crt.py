"""NumPy inference of the P11-01 causal ring-TCN ("CRT") EMG-to-text decoder. Our own code (Apache-2.0).

Same maths as ``experiments/2026-11-16-p11-01-emg-decoder/emgdec.py`` (``CRT``) in eval mode, and the
same features as its ``prep.py``. No emg2qwerty code is read or copied (P11-01 plan).

Features: 2 kHz EMG (n, 32) -> windows of 64 samples every 20 samples (100 frames/s) -> channel
mean removed -> Hann -> rfft -> power in 12 bands (bins 1..32, about log spaced) -> log. Frame ``k``
covers samples ``[20 k, 20 k + 64)``; its time is the end of the window (causal).

Model: fixed normalisation -> per wristband a circular conv over the 16-electrode ring + linear ->
concat -> causal residual blocks (LayerNorm, depthwise causal dilated conv, GELU, feed-forward) ->
LayerNorm -> linear -> log-softmax over 98 tokens (CTC blank 0). Every layer is causal.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

__all__ = ["WIN", "HOP", "FS", "N_BANDS", "N_CH", "VOCAB", "BAND_EDGES", "n_frames", "frames_from_block",
           "TrunkStream", "CRTStream",
           "receptive_field", "crt_log_probs", "trunk_log_probs", "trunk_keys", "required_keys", "erf",
           "gelu"]

FS = 2000
WIN = 64
HOP = 20
N_CH = 32
N_EL = 16
BAND_EDGES = (1, 2, 3, 4, 5, 6, 8, 10, 13, 16, 20, 25, 33)
N_BANDS = len(BAND_EDGES) - 1
LOG_EPS = 1e-6
LN_EPS = 1e-5
BACKSPACE = "⌫"
ENTER = "⏎"
VOCAB: tuple[str, ...] = ("<blank>", *[chr(c) for c in range(32, 127)], BACKSPACE, ENTER)  # 98 tokens


def _band_matrix() -> np.ndarray:
    m = np.zeros((WIN // 2 + 1, N_BANDS), np.float32)
    for b in range(N_BANDS):
        lo, hi = BAND_EDGES[b], BAND_EDGES[b + 1]
        m[lo:hi, b] = 1.0 / (hi - lo)
    return m


_HANN = np.hanning(WIN).astype(np.float32)
_BANDS = _band_matrix()


def n_frames(n_samples: int) -> int:
    return 0 if n_samples < WIN else (n_samples - WIN) // HOP + 1


def frames_from_block(x: np.ndarray) -> np.ndarray:
    """(m, 32) float32 samples -> (n_frames(m), 32, 12) float32 log band power."""
    x = np.asarray(x, np.float32)
    if not np.all(np.isfinite(x)):
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    nf = n_frames(len(x))
    if nf == 0:
        return np.zeros((0, x.shape[1] if x.ndim == 2 else N_CH, N_BANDS), np.float32)
    w = np.lib.stride_tricks.sliding_window_view(x, WIN, axis=0)[::HOP][:nf]  # (nf, 32, WIN)
    w = w - w.mean(axis=2, keepdims=True)
    spec = np.fft.rfft(w * _HANN, axis=2)
    pw = (spec.real ** 2 + spec.imag ** 2).astype(np.float32)
    return np.log(pw @ _BANDS + LOG_EPS)


def erf(x: np.ndarray) -> np.ndarray:
    """Error function, Abramowitz and Stegun 7.1.26 (max abs error 1.5e-7). NumPy has no erf."""
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-a * a)
    return (s * y).astype(x.dtype, copy=False)


def gelu(x: np.ndarray) -> np.ndarray:
    """Exact GELU (the torch default): x * Phi(x)."""
    return (0.5 * x * (1.0 + erf(x / np.float32(np.sqrt(2.0))))).astype(np.float32)


def _layer_norm(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    mu = x.mean(axis=-1, keepdims=True)
    var = ((x - mu) ** 2).mean(axis=-1, keepdims=True)
    return ((x - mu) / np.sqrt(var + LN_EPS) * w + b).astype(np.float32)


def receptive_field(kernel: int, dilations: Sequence[int]) -> int:
    return 1 + sum((kernel - 1) * d for d in dilations)


def trunk_keys(n_blocks: int) -> list[str]:
    """The arrays of the shared trunk and head (residual blocks, output LayerNorm, linear head)."""
    keys = ["out_norm.weight", "out_norm.bias", "head.weight", "head.bias"]
    for i in range(n_blocks):
        keys += [f"blocks.{i}.{k}" for k in ("norm.weight", "norm.bias", "dw.weight", "dw.bias", "ff.0.weight",
                                              "ff.0.bias", "ff.3.weight", "ff.3.bias")]
    return keys


def required_keys(n_blocks: int) -> list[str]:
    keys = ["mean", "std"]
    for side in ("left", "right"):
        keys += [f"{side}.conv.weight", f"{side}.conv.bias", f"{side}.proj.weight", f"{side}.proj.bias"]
    return keys + trunk_keys(n_blocks)


def _ring(p: Mapping[str, np.ndarray], side: str, x: np.ndarray, k: int) -> np.ndarray:
    """(T, 16, 12) -> (T, d/2): circular conv over the electrodes, GELU, linear."""
    T, E, F = x.shape
    w, b = p[f"{side}.conv.weight"], p[f"{side}.conv.bias"]  # (c, 12, k), (c,)
    h = x.transpose(0, 2, 1)  # (T, 12, E)
    pad = k // 2
    hp = np.concatenate([h[..., E - pad:], h, h[..., :pad]], axis=-1)  # circular padding
    xs = np.stack([hp[..., i:i + E] for i in range(k)], axis=-1)  # (T, 12, E, k)
    c = np.einsum("tfek,cfk->tce", xs, w, optimize=True) + b[None, :, None]  # (T, c, E)
    g = gelu(c.astype(np.float32)).reshape(T, -1)  # channel-major (c, E), as torch reshape
    return (g @ p[f"{side}.proj.weight"].T + p[f"{side}.proj.bias"]).astype(np.float32)


def _forward(p: Mapping[str, np.ndarray], feat: np.ndarray, *, ring_k: int, kernel: int,
             dilations: Sequence[int]) -> np.ndarray:
    """(T, 32, 12) raw features -> (T, V) log-probs (one causal pass, zero left padding)."""
    x = (np.asarray(feat, np.float32) - p["mean"].reshape(N_CH, N_BANDS)) / p["std"].reshape(N_CH, N_BANDS)
    h = np.concatenate([_ring(p, "left", x[:, :N_EL], ring_k), _ring(p, "right", x[:, N_EL:], ring_k)], axis=-1)
    return trunk_log_probs(p, h, kernel=kernel, dilations=dilations)


def trunk_log_probs(p: Mapping[str, np.ndarray], h: np.ndarray, *, kernel: int, dilations: Sequence[int]) -> np.ndarray:
    """(T, d) stem output -> (T, V) log-probs: causal residual blocks -> LayerNorm -> head -> log-softmax.

    The trunk and head are shared by the EMG model (ring stem) and the Willett model (linear stem,
    :mod:`fidetype.pretrained._xbody`). Zero left padding: one causal pass from the first frame.
    """
    h = np.asarray(h, np.float32)
    T = h.shape[0]
    for i, dil in enumerate(dilations):
        q = f"blocks.{i}."
        n = _layer_norm(h, p[q + "norm.weight"], p[q + "norm.bias"])
        pad = (kernel - 1) * dil
        npad = np.concatenate([np.zeros((pad, n.shape[1]), np.float32), n], 0)
        w = p[q + "dw.weight"][:, 0, :]  # (d, k)
        c = np.broadcast_to(p[q + "dw.bias"], n.shape).astype(np.float32).copy()
        for j in range(kernel):
            c += w[:, j] * npad[j * dil:j * dil + T]
        f = gelu(c) @ p[q + "ff.0.weight"].T + p[q + "ff.0.bias"]
        f = gelu(f.astype(np.float32)) @ p[q + "ff.3.weight"].T + p[q + "ff.3.bias"]
        h = (h + f).astype(np.float32)
    o = _layer_norm(h, p["out_norm.weight"], p["out_norm.bias"]) @ p["head.weight"].T + p["head.bias"]
    m = o.max(axis=1, keepdims=True)
    return (o - m - np.log(np.exp(o - m).sum(axis=1, keepdims=True))).astype(np.float32)


def crt_log_probs(p: Mapping[str, np.ndarray], feat: np.ndarray, *, ring_k: int, kernel: int,
                  dilations: Sequence[int], chunk: int = 4000) -> np.ndarray:
    """Causal log-probs (T, V) of a feature sequence, in chunks with left context = receptive field.

    The result equals one pass over the whole sequence (the model is causal); memory stays bounded.
    """
    rf = receptive_field(kernel, dilations)
    n = len(feat)
    V = p["head.weight"].shape[0]
    out = np.empty((n, V), np.float32)
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        c = max(0, a - rf)
        out[a:b] = _forward(p, feat[c:b], ring_k=ring_k, kernel=kernel, dilations=dilations)[a - c:]
    return out


class TrunkStream:
    """Streaming form of :func:`trunk_log_probs` (P3-12): push stem frames in chunks, get their log-probs.

    Each residual block keeps the last ``(kernel - 1) * dilation`` LayerNorm outputs, so a chunk of ``n``
    frames costs ``n`` frames of work (the batch form recomputes the whole receptive field for each chunk).
    The state starts at zeros, the same as the zero left padding of :func:`trunk_log_probs`. The maths is the
    same; float32 sums can differ in the last bits because the matrix products run on fewer rows.
    """

    def __init__(self, p: Mapping[str, np.ndarray], *, kernel: int, dilations: Sequence[int]) -> None:
        self.kernel = int(kernel)
        self.dilations = tuple(int(d) for d in dilations)
        self._blocks = []
        for i, dil in enumerate(self.dilations):
            q = f"blocks.{i}."
            d = p[q + "norm.weight"].shape[0]
            self._blocks.append({
                "dil": dil, "pad": (self.kernel - 1) * dil,
                "nw": np.asarray(p[q + "norm.weight"], np.float32), "nb": np.asarray(p[q + "norm.bias"], np.float32),
                "w": np.ascontiguousarray(p[q + "dw.weight"][:, 0, :], np.float32),
                "b": np.asarray(p[q + "dw.bias"], np.float32),
                "f0": np.ascontiguousarray(np.asarray(p[q + "ff.0.weight"], np.float32).T),
                "f0b": np.asarray(p[q + "ff.0.bias"], np.float32),
                "f3": np.ascontiguousarray(np.asarray(p[q + "ff.3.weight"], np.float32).T),
                "f3b": np.asarray(p[q + "ff.3.bias"], np.float32),
                "hist": np.zeros(((self.kernel - 1) * dil, d), np.float32)})
        self._onw = np.asarray(p["out_norm.weight"], np.float32)
        self._onb = np.asarray(p["out_norm.bias"], np.float32)
        self._hw = np.ascontiguousarray(np.asarray(p["head.weight"], np.float32).T)
        self._hb = np.asarray(p["head.bias"], np.float32)
        self.t = 0

    def reset(self) -> None:
        """Back to the zero state (a new stream)."""
        for blk in self._blocks:
            blk["hist"][:] = 0.0
        self.t = 0

    def push(self, h: np.ndarray) -> np.ndarray:
        """(n, d) stem output of the next ``n`` frames -> (n, V) log-probs."""
        h = np.asarray(h, np.float32)
        T = h.shape[0]
        if T == 0:
            return np.zeros((0, self._hw.shape[1]), np.float32)
        k = self.kernel
        for blk in self._blocks:
            n = _layer_norm(h, blk["nw"], blk["nb"])
            pad, dil = blk["pad"], blk["dil"]
            npad = np.concatenate([blk["hist"], n], 0)
            w = blk["w"]
            c = np.broadcast_to(blk["b"], n.shape).astype(np.float32).copy()
            for j in range(k):
                c += w[:, j] * npad[j * dil:j * dil + T]
            blk["hist"] = npad[-pad:].copy() if pad else blk["hist"]
            f = gelu(c) @ blk["f0"] + blk["f0b"]
            f = gelu(f.astype(np.float32)) @ blk["f3"] + blk["f3b"]
            h = (h + f).astype(np.float32)
        o = _layer_norm(h, self._onw, self._onb) @ self._hw + self._hb
        m = o.max(axis=1, keepdims=True)
        self.t += T
        return (o - m - np.log(np.exp(o - m).sum(axis=1, keepdims=True))).astype(np.float32)


class CRTStream:
    """Streaming form of the CRT EMG model (P3-12): ``push(feat_chunk)`` -> log-probs of those frames.

    The ring stem works frame by frame (no state); the trunk is a :class:`TrunkStream`. A stream that starts
    at frame ``a`` gives the same log-probs (up to float32 rounding) as :func:`_forward` on ``feat[a:]``.
    """

    def __init__(self, p: Mapping[str, np.ndarray], *, ring_k: int, kernel: int, dilations: Sequence[int]) -> None:
        self.p = p
        self.ring_k = int(ring_k)
        self._mean = np.asarray(p["mean"], np.float32).reshape(N_CH, N_BANDS)
        self._std = np.asarray(p["std"], np.float32).reshape(N_CH, N_BANDS)
        self.trunk = TrunkStream(p, kernel=kernel, dilations=dilations)

    def reset(self) -> None:
        self.trunk.reset()

    def push(self, feat: np.ndarray) -> np.ndarray:
        """(n, 32, 12) raw features of the next ``n`` frames -> (n, V) log-probs."""
        if len(feat) == 0:
            return self.trunk.push(np.zeros((0, 0), np.float32))
        x = (np.asarray(feat, np.float32) - self._mean) / self._std
        h = np.concatenate([_ring(self.p, "left", x[:, :N_EL], self.ring_k),
                            _ring(self.p, "right", x[:, N_EL:], self.ring_k)], axis=-1)
        return self.trunk.push(h)
