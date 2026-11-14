"""Causal GRU-CTC phoneme decoder with a configurable lookahead (M4-01).

Our own code (no third-party code copied). It extends the M3-28 T12 decoder
(``experiments/2026-11-13-confirmatory-t12-v2/train_decoder.py``) with one
right-context branch.

Model
-----
Input: ``x`` (T, C) neural features at 20 ms bins, already normalised with a
causal estimate (the B2T '25 data are z-scored on the 20 previous trials).

1. Causal smoothing: a half-Gaussian kernel over the current and past bins.
2. Day layer: ``z_t = softsign(y_t W_s + b_s)`` per recording session.
3. Patches: output step ``k`` reads bins ``[S k, S k + P)`` (patch ``P``,
   stride ``S``). Its newest bin is ``t_k = S k + P - 1``.
4. A unidirectional GRU stack over the patches: ``h_k`` uses bins
   ``<= t_k`` only.
5. Lookahead branch: the bins ``t_k + 1 .. t_k + L`` (``L`` bins of 20 ms,
   at most ``L_max``) go through a per-bin projection, are masked to zero
   past ``L`` and past the end of the utterance, then a linear map plus an
   embedding of ``L`` gives ``f_k``.
6. ``logits_k = W_o (h_k + tanh(f_k)) + b_o``.

So output ``k`` depends on input bins ``<= t_k + L`` only (proved by
``tests/test_causal_lookahead.py``). One trained model can serve every
``L <= L_max``: the training samples ``L`` per batch ("variable lookahead
training"). A model trained with one fixed ``L`` is the dedicated variant.

Time stamps
-----------
We stamp output ``k`` at the end of bin ``t_k``: ``(S k + P) * 0.02`` s
(as the B2T '25 adapter does for the published decoder). In a live system
the output is ready when bin ``t_k + L`` has arrived, that is ``L * 20`` ms
after its stamp (the *algorithmic lookahead*). At the end of an utterance
the decoder flushes: it masks the missing future bins (as in training) and
does not wait.

Two implementations share the parameters: a PyTorch module for training
(:func:`build_torch_model`, imported lazily) and NumPy code for inference
and tests (:func:`forward_numpy`, :class:`StreamingLookaheadGRU`). The NumPy
streaming decoder takes bins as they arrive and returns each output row as
soon as its input is complete.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

BIN_S = 0.02


@dataclass(frozen=True)
class LookaheadGRUConfig:
    n_in: int = 512
    n_out: int = 41
    n_sessions: int = 1
    hidden: int = 768
    layers: int = 5
    patch: int = 14
    stride: int = 4
    smooth_sd: float = 2.0
    la_max: int = 25  # bins (25 x 20 ms = 500 ms)
    la_proj: int = 64
    dropout: float = 0.4

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def n_steps(self, T: int) -> int:
        return max(0, (T - self.patch) // self.stride + 1)

    def step_end_bin(self, k: int) -> int:
        """Index of the newest bin of patch ``k`` (``t_k``)."""
        return self.stride * k + self.patch - 1

    def frame_times(self, n: int) -> np.ndarray:
        """Time stamp of output ``k``: end of bin ``t_k``, in seconds from the utterance start."""
        return (np.arange(n) * self.stride + self.patch) * BIN_S


def lookahead_bins(ms: float) -> int:
    """Bins for a nominal lookahead in ms, rounded down (the lookahead never exceeds the nominal value)."""
    return int(math.floor(ms / (BIN_S * 1000) + 1e-9))


def causal_kernel(sd: float) -> np.ndarray:
    """Half-Gaussian smoothing kernel in conv order (oldest .. current bin)."""
    w = int(math.ceil(3 * sd))
    t = np.arange(w + 1, dtype=np.float64)
    k = np.exp(-0.5 * (t / sd) ** 2)
    k = k / k.sum()
    return k[::-1].astype(np.float32)


# ---------------------------------------------------------------------------
# PyTorch (training)
# ---------------------------------------------------------------------------


def build_torch_model(cfg: LookaheadGRUConfig):
    """The trainable module (needs torch). ``forward(x, sess, la_bins, lengths)`` -> logits (B, K, n_out)."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class LookaheadGRU(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.cfg = cfg
            c = cfg
            self.day_W = nn.Parameter(torch.eye(c.n_in).repeat(c.n_sessions, 1, 1))
            self.day_b = nn.Parameter(torch.zeros(c.n_sessions, c.n_in))
            self.register_buffer("kern", torch.from_numpy(causal_kernel(c.smooth_sd).copy()))
            self.grus = nn.ModuleList([nn.GRU(c.n_in * c.patch if i == 0 else c.hidden, c.hidden, 1, batch_first=True)
                                       for i in range(c.layers)])
            self.la_in = nn.Linear(c.n_in, c.la_proj)
            self.la_out = nn.Linear(c.la_max * c.la_proj, c.hidden)
            self.la_emb = nn.Embedding(c.la_max + 1, c.hidden)
            nn.init.zeros_(self.la_emb.weight)
            self.drop = nn.Dropout(c.dropout)
            self.out = nn.Linear(c.hidden, c.n_out)

        def n_frames(self, T):
            return torch.clamp((T - cfg.patch) // cfg.stride + 1, min=0)

        def features(self, x, sess):
            B, T, C = x.shape
            k = self.kern.numel()
            xs = F.pad(x.transpose(1, 2), (k - 1, 0))
            xs = F.conv1d(xs, self.kern.view(1, 1, -1).repeat(C, 1, 1), groups=C).transpose(1, 2)
            return F.softsign(torch.einsum("btc,bcd->btd", xs, self.day_W[sess]) + self.day_b[sess].unsqueeze(1))

        def forward(self, x, sess, la_bins, lengths=None):
            """``la_bins``: int (same L for the batch) or LongTensor (B,). ``lengths``: valid bins per item (B,)."""
            c = cfg
            B, T, C = x.shape
            if lengths is None:
                lengths = torch.full((B,), T, device=x.device, dtype=torch.long)
            z = self.features(x, sess)
            p = z.unfold(1, c.patch, c.stride)  # B, K, C, P
            K = p.shape[1]
            p = p.permute(0, 1, 3, 2).reshape(B, K, c.patch * C)
            h = p
            for g in self.grus:
                h, _ = g(h)
                h = self.drop(h)
            # lookahead branch: bins t_k+1 .. t_k+la_max
            u = self.la_in(z)  # B, T, la_proj
            u = F.pad(u, (0, 0, 0, c.la_max))  # zeros past T
            tk = torch.arange(K, device=x.device) * c.stride + c.patch - 1  # K
            j = torch.arange(1, c.la_max + 1, device=x.device)  # la_max
            idx = tk[:, None] + j[None, :]  # K, la_max
            fut = u[:, idx]  # B, K, la_max, la_proj
            if not torch.is_tensor(la_bins):
                la_bins = torch.full((B,), int(la_bins), device=x.device, dtype=torch.long)
            la_bins = la_bins.to(x.device).long()
            vis = (j[None, None, :] <= la_bins[:, None, None]) & (idx[None, :, :] < lengths[:, None, None])  # B, K, la_max
            fut = fut * vis.unsqueeze(-1).to(fut.dtype)
            f = self.la_out(self.drop(fut.reshape(B, K, c.la_max * c.la_proj))) + self.la_emb(la_bins).unsqueeze(1)
            return self.out(h + torch.tanh(f))

    return LookaheadGRU()


def export_numpy_params(model) -> dict[str, np.ndarray]:
    """All parameters as float32 NumPy arrays (keys of the torch state dict)."""
    return {k: v.detach().cpu().float().numpy() for k, v in model.state_dict().items()}


# ---------------------------------------------------------------------------
# NumPy (inference, tests)
# ---------------------------------------------------------------------------


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _softsign(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.abs(x))


@dataclass
class NumpyLookaheadGRU:
    """The parameters of a trained model, for NumPy inference."""

    cfg: LookaheadGRUConfig
    params: dict[str, np.ndarray]
    _kern: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._kern = causal_kernel(self.cfg.smooth_sd)
        p = self.params
        # GRU weights pre-split per gate (torch order r, z, n)
        self._gru = []
        for i in range(self.cfg.layers):
            Wi, Wh = p[f"grus.{i}.weight_ih_l0"], p[f"grus.{i}.weight_hh_l0"]
            bi, bh = p[f"grus.{i}.bias_ih_l0"], p[f"grus.{i}.bias_hh_l0"]
            self._gru.append((np.ascontiguousarray(Wi.T), np.ascontiguousarray(Wh.T), bi, bh))

    @classmethod
    def random(cls, cfg: LookaheadGRUConfig, seed: int = 0, scale: float = 0.3) -> "NumpyLookaheadGRU":
        """Random parameters (tests)."""
        r = np.random.default_rng(seed)
        c = cfg
        H = c.hidden
        p: dict[str, np.ndarray] = {
            "day_W": (np.eye(c.n_in)[None].repeat(c.n_sessions, 0) + 0.1 * r.standard_normal((c.n_sessions, c.n_in, c.n_in))).astype(np.float32),
            "day_b": (0.1 * r.standard_normal((c.n_sessions, c.n_in))).astype(np.float32),
            "la_in.weight": (scale * r.standard_normal((c.la_proj, c.n_in))).astype(np.float32),
            "la_in.bias": (scale * r.standard_normal(c.la_proj)).astype(np.float32),
            "la_out.weight": (scale * r.standard_normal((H, c.la_max * c.la_proj)) / math.sqrt(c.la_proj)).astype(np.float32),
            "la_out.bias": (scale * r.standard_normal(H)).astype(np.float32),
            "la_emb.weight": (scale * r.standard_normal((c.la_max + 1, H))).astype(np.float32),
            "out.weight": (scale * r.standard_normal((c.n_out, H))).astype(np.float32),
            "out.bias": (scale * r.standard_normal(c.n_out)).astype(np.float32),
        }
        for i in range(c.layers):
            n_in = c.n_in * c.patch if i == 0 else H
            p[f"grus.{i}.weight_ih_l0"] = (scale * r.standard_normal((3 * H, n_in)) / math.sqrt(n_in) * 3).astype(np.float32)
            p[f"grus.{i}.weight_hh_l0"] = (scale * r.standard_normal((3 * H, H)) / math.sqrt(H) * 3).astype(np.float32)
            p[f"grus.{i}.bias_ih_l0"] = (scale * r.standard_normal(3 * H)).astype(np.float32)
            p[f"grus.{i}.bias_hh_l0"] = (scale * r.standard_normal(3 * H)).astype(np.float32)
        return cls(cfg, p)

    # --- pieces ---------------------------------------------------------------

    def day_features(self, x: np.ndarray, session: int, x_hist: np.ndarray | None = None) -> np.ndarray:
        """Smoothed + day layer for bins ``x`` (n, C). ``x_hist``: the previous bins (for the causal kernel)."""
        k = self._kern
        K = k.size
        if x_hist is None:
            x_hist = np.zeros((0, x.shape[1]), np.float32)
        pad = np.zeros((max(0, K - 1 - x_hist.shape[0]), x.shape[1]), np.float32)
        xx = np.concatenate([pad, x_hist[-(K - 1):] if K > 1 else x_hist[:0], x], 0).astype(np.float32)
        n = x.shape[0]
        y = np.zeros((n, x.shape[1]), np.float32)
        for i in range(K):
            y += k[i] * xx[i:i + n]
        return _softsign(y @ self.params["day_W"][session] + self.params["day_b"][session]).astype(np.float32)

    def gru_step(self, layer: int, x: np.ndarray, h: np.ndarray) -> np.ndarray:
        Wi, Wh, bi, bh = self._gru[layer]
        H = self.cfg.hidden
        gi = x @ Wi + bi
        gh = h @ Wh + bh
        r = _sigmoid(gi[:H] + gh[:H])
        zg = _sigmoid(gi[H:2 * H] + gh[H:2 * H])
        n = np.tanh(gi[2 * H:] + r * gh[2 * H:])
        return ((1.0 - zg) * n + zg * h).astype(np.float32)

    def head(self, h: np.ndarray, fut_u: np.ndarray, la_bins: int) -> np.ndarray:
        """Logits of one step: ``fut_u`` (la_max, la_proj) projected future bins, already masked."""
        p = self.params
        f = fut_u.reshape(-1) @ p["la_out.weight"].T + p["la_out.bias"] + p["la_emb.weight"][la_bins]
        return ((h + np.tanh(f)) @ p["out.weight"].T + p["out.bias"]).astype(np.float32)

    def project(self, z: np.ndarray) -> np.ndarray:
        return (z @ self.params["la_in.weight"].T + self.params["la_in.bias"]).astype(np.float32)


def forward_numpy(m: NumpyLookaheadGRU, x: np.ndarray, session: int, la_bins: int) -> np.ndarray:
    """Batch forward of one utterance (T, C) -> logits (K, n_out). Same maths as the torch module in eval mode."""
    c = m.cfg
    assert 0 <= la_bins <= c.la_max
    T = x.shape[0]
    K = c.n_steps(T)
    z = m.day_features(x.astype(np.float32), session)
    u = m.project(z)
    hs = [np.zeros(c.hidden, np.float32) for _ in range(c.layers)]
    out = np.zeros((K, c.n_out), np.float32)
    for k in range(K):
        a = z[c.stride * k: c.stride * k + c.patch].reshape(-1)
        for i in range(c.layers):
            hs[i] = m.gru_step(i, a, hs[i])
            a = hs[i]
        tk = c.step_end_bin(k)
        fut = np.zeros((c.la_max, c.la_proj), np.float32)
        n_vis = min(la_bins, T - 1 - tk)
        if n_vis > 0:
            fut[:n_vis] = u[tk + 1: tk + 1 + n_vis]
        out[k] = m.head(a, fut, la_bins)
    return out


class StreamingLookaheadGRU:
    """Bin-by-bin causal inference. :meth:`push` returns the output rows that became complete.

    Output ``k`` is returned as soon as bin ``t_k + L`` has arrived (or at
    :meth:`flush`, with the missing future bins masked). The concatenation
    of all returned rows equals :func:`forward_numpy` on the same bins.
    """

    def __init__(self, model: NumpyLookaheadGRU, session: int, la_bins: int) -> None:
        c = model.cfg
        assert 0 <= la_bins <= c.la_max
        self.m, self.c, self.session, self.L = model, c, int(session), int(la_bins)
        self._klen = model._kern.size
        self.x_hist = np.zeros((0, c.n_in), np.float32)  # last kernel-1 raw bins
        self.z: list[np.ndarray] = []  # day features of all bins so far (bounded below)
        self.u: list[np.ndarray] = []
        self.z_off = 0  # index of self.z[0]
        self.hs = [np.zeros(c.hidden, np.float32) for _ in range(c.layers)]
        self.k_gru = 0  # next step to run through the GRU
        self.k_out = 0  # next step to emit
        self.h_pending: dict[int, np.ndarray] = {}
        self.n_bins = 0

    def _z(self, t: int) -> np.ndarray:
        return self.z[t - self.z_off]

    def _advance(self, final: bool) -> list[np.ndarray]:
        c = self.c
        rows = []
        # run the GRU on every complete patch
        while c.step_end_bin(self.k_gru) < self.n_bins:
            k = self.k_gru
            a = np.concatenate([self._z(t) for t in range(c.stride * k, c.stride * k + c.patch)])
            for i in range(c.layers):
                self.hs[i] = self.m.gru_step(i, a, self.hs[i])
                a = self.hs[i]
            self.h_pending[k] = a
            self.k_gru += 1
        # emit the steps whose lookahead is complete (or all at the end)
        while self.k_out < self.k_gru:
            k = self.k_out
            tk = c.step_end_bin(k)
            if not final and tk + self.L > self.n_bins - 1:
                break
            fut = np.zeros((c.la_max, c.la_proj), np.float32)
            n_vis = min(self.L, self.n_bins - 1 - tk)
            for j in range(n_vis):
                fut[j] = self.u[tk + 1 + j - self.z_off]
            rows.append(self.m.head(self.h_pending.pop(k), fut, self.L))
            self.k_out += 1
        # drop bins nobody needs any more
        keep_from = min(c.stride * self.k_gru, c.step_end_bin(self.k_out) + 1)
        drop = keep_from - self.z_off
        if drop > 0:
            del self.z[:drop]
            del self.u[:drop]
            self.z_off += drop
        return rows

    def push(self, bins: np.ndarray) -> np.ndarray:
        """Add (n, C) bins. Returns the newly complete output rows (m, n_out) (logits)."""
        bins = np.asarray(bins, np.float32).reshape(-1, self.c.n_in)
        if bins.shape[0]:
            z = self.m.day_features(bins, self.session, self.x_hist)
            u = self.m.project(z)
            self.z.extend(list(z))
            self.u.extend(list(u))
            self.x_hist = np.concatenate([self.x_hist, bins], 0)[-(self._klen - 1):] if self._klen > 1 else self.x_hist
            self.n_bins += bins.shape[0]
        rows = self._advance(final=False)
        return np.stack(rows) if rows else np.zeros((0, self.c.n_out), np.float32)

    def flush(self) -> np.ndarray:
        """End of the utterance: emit the remaining rows with the missing future bins masked."""
        rows = self._advance(final=True)
        return np.stack(rows) if rows else np.zeros((0, self.c.n_out), np.float32)


def log_softmax(x: np.ndarray) -> np.ndarray:
    m = x.max(-1, keepdims=True)
    return (x - m - np.log(np.exp(x - m).sum(-1, keepdims=True))).astype(np.float32)
