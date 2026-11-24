"""A1 decoder: a re-implementation of ATM-S (Li et al., NeurIPS 2024, arXiv:2403.07721) and an InfoNCE loss.

Our own code, Apache-2.0. The architecture follows the ATM-S model in
https://github.com/ncclab-sustech/EEG_Image_decode (``Retrieval/ATMS_retrieval.py``, commit 49cb3a2), which is
under the MIT licence:

    MIT License. Copyright (c) 2023 DongyangLi.
    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
    to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above
    copyright notice and this permission notice shall be included in all copies or substantial portions of the
    Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

We wrote the layers ourselves from that description (no file copied). Differences: no braindecode / einops / clip
imports; the loss is our own symmetric InfoNCE (ATM uses a BSD-3 ClipLoss from salesforce, not copied).
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F
from torch import nn


def sinusoidal(n: int, d: int) -> torch.Tensor:
    pos = torch.arange(n, dtype=torch.float32)[:, None]
    div = torch.exp(torch.arange(0, d, 2, dtype=torch.float32) * (-math.log(10000.0) / d))
    pe = torch.zeros(n, d)
    pe[:, 0::2] = torch.sin(pos * div)
    pe[:, 1::2] = torch.cos(pos * div[: pe[:, 1::2].shape[1]])
    return pe


class Attention(nn.Module):
    """Multi-head self-attention with d_k = d_model // heads (as ATM: 250 // 4 = 62, inner width 248)."""

    def __init__(self, d: int, heads: int, dropout: float):
        super().__init__()
        self.h, self.dk = heads, d // heads
        self.q = nn.Linear(d, self.dk * heads)
        self.k = nn.Linear(d, self.dk * heads)
        self.v = nn.Linear(d, self.dk * heads)
        self.o = nn.Linear(self.dk * heads, d)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, n, _ = x.shape
        q, k, v = (f(x).view(b, n, self.h, self.dk).transpose(1, 2) for f in (self.q, self.k, self.v))
        a = self.drop(torch.softmax(q @ k.transpose(-1, -2) / math.sqrt(self.dk), dim=-1))
        return self.o((a @ v).transpose(1, 2).reshape(b, n, self.h * self.dk))


class ChannelTransformer(nn.Module):
    """Each EEG channel is one token (its whole time course); one post-norm Transformer encoder layer."""

    def __init__(self, n_ch: int = 63, n_t: int = 250, d_ff: int = 256, n_heads: int = 4, dropout: float = 0.25,
                 n_subjects: int = 10):
        super().__init__()
        self.n_ch = n_ch
        self.value = nn.Linear(n_t, n_t)
        self.register_buffer("pe", sinusoidal(n_ch, n_t), persistent=False)
        self.subject = nn.Embedding(n_subjects, n_t)
        self.drop = nn.Dropout(dropout)
        self.attn = Attention(n_t, n_heads, dropout)
        self.ff1 = nn.Linear(n_t, d_ff)
        self.ff2 = nn.Linear(d_ff, n_t)
        self.norm1 = nn.LayerNorm(n_t)
        self.norm2 = nn.LayerNorm(n_t)
        self.norm_out = nn.LayerNorm(n_t)

    def forward(self, x: torch.Tensor, subject: torch.Tensor) -> torch.Tensor:
        h = self.value(x) + self.pe[None]
        h = torch.cat([self.subject(subject)[:, None, :], h], dim=1)  # subject token first, then 63 channel tokens
        h = self.drop(h)
        a = self.attn(h)
        h = self.norm1(h + self.drop(a))
        y = self.drop(self.ff2(self.drop(F.gelu(self.ff1(h)))))
        h = self.norm_out(self.norm2(h + y))
        return h[:, : self.n_ch]  # ATM keeps the first 63 tokens


class TemporalSpatialConv(nn.Module):
    """ShallowNet-style patch embedding: temporal conv, average pool, spatial conv; flattened."""

    def __init__(self, n_ch: int = 63, k: int = 40):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, k, (1, 25)), nn.AvgPool2d((1, 51), (1, 5)), nn.BatchNorm2d(k), nn.ELU(),
            nn.Conv2d(k, k, (n_ch, 1)), nn.BatchNorm2d(k), nn.ELU(), nn.Dropout(0.5),
            nn.Conv2d(k, k, (1, 1)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.net(x[:, None])  # [B, k, 1, W]
        return y.flatten(2).transpose(1, 2).flatten(1)  # [B, W * k]


class Projection(nn.Module):
    def __init__(self, d_in: int, d_out: int = 1024, dropout: float = 0.5):
        super().__init__()
        self.lin = nn.Linear(d_in, d_out)
        self.res = nn.Sequential(nn.GELU(), nn.Linear(d_out, d_out), nn.Dropout(dropout))
        self.norm = nn.LayerNorm(d_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.lin(x)
        return self.norm(h + self.res(h))


class ATMS(nn.Module):
    def __init__(self, n_ch: int = 63, n_t: int = 250, d_out: int = 1024, n_subjects: int = 10):
        super().__init__()
        self.enc = ChannelTransformer(n_ch, n_t, n_subjects=n_subjects)
        self.conv = TemporalSpatialConv(n_ch)
        w = ((n_t - 24) - 51) // 5 + 1
        self.proj = Projection(40 * w, d_out)
        self.logit_scale = nn.Parameter(torch.tensor(math.log(1 / 0.07)))

    def forward(self, x: torch.Tensor, subject: torch.Tensor) -> torch.Tensor:
        return self.proj(self.conv(self.enc(x, subject)))


def info_nce(eeg: torch.Tensor, target: torch.Tensor, logit_scale: torch.Tensor) -> torch.Tensor:
    """Symmetric InfoNCE over a batch; row i of ``target`` is the positive of row i of ``eeg``."""
    e = F.normalize(eeg, dim=-1)
    t = F.normalize(target, dim=-1)
    logits = logit_scale.exp() * e @ t.T
    y = torch.arange(len(e), device=e.device)
    return 0.5 * (F.cross_entropy(logits, y) + F.cross_entropy(logits.T, y))


def atm_loss(model: ATMS, eeg_emb: torch.Tensor, img: torch.Tensor, txt: torch.Tensor, w_img: float = 0.99):
    return w_img * info_nce(eeg_emb, img, model.logit_scale) + (1 - w_img) * info_nce(eeg_emb, txt, model.logit_scale)


def n_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
