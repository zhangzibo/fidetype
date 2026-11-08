"""Conv + Conformer CTC decoder for continuous MEG (our own design).

The design follows the idea of the Brain2Qwerty v2 "Encoder Async"
(see ``wiki/sources/brain2qwerty-v2.md``), but it is much smaller. The
code is our own. It does not copy the Brain2Qwerty code.

Pipeline (input [B, 306, T] at 100 Hz)::

    spatial 1x1 conv 306 -> D_s
    subject affine layer (one D_s x D_s matrix + bias per participant)
    dilated residual Conv1d stack (LayerNorm, GELU, dropout), width H
    strided conv, stride 4 -> 25 Hz frames (40 ms), width D
    auxiliary CTC head (28 classes)      <- loss weight 0.7
    (optional) self-conditioning: add a projection of the aux posteriors
    Conformer stack (macaron FFN, MHSA, depthwise conv)
    final CTC head (28 classes)          <- loss weight 0.3

Causal mode
-----------
Set ``lookahead_frames`` to an int to make the model streaming-ready:

- All convolutions pad on the left only. Output frame j of the strided
  conv sees input samples <= 4*j.
- Each attention layer lets frame i attend to frames j <= i + lookahead.
- The Conformer depthwise convolutions are causal.

With N Conformer layers, the total lookahead is ``N * lookahead_frames``
frames (see :meth:`ConvCTC.total_lookahead_frames`). ``None`` (the
default) gives the offline, bidirectional model.

LayerNorm (per time step) is used everywhere instead of BatchNorm. Thus
the model has no statistics across time, and causal mode stays causal.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, fields
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from fidetype.streams.vocab import BLANK_ID, VOCAB_SIZE


@dataclass
class ModelConfig:
    n_channels: int = 306
    n_subjects: int = 1
    spatial_dim: int = 256  # D_s
    subject_layer: bool = True
    conv_dim: int = 320  # H
    conv_blocks: int = 5
    conv_kernel: int = 5
    conv_dilation_cycle: int = 5  # dilations 1, 2, 4, ... repeat after this many blocks
    downsample: int = 4
    downsample_kernel: int = 8
    model_dim: int = 256  # D
    conformer_layers: int = 4
    conformer_heads: int = 4
    conformer_ffn: int = 1024
    conformer_kernel: int = 15
    dropout: float = 0.1
    input_dropout: float = 0.0
    self_condition: bool = True
    lookahead_frames: int | None = None
    vocab_size: int = VOCAB_SIZE
    aux_weight: float = 0.7  # loss = (1 - aux_weight) * final + aux_weight * aux

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelConfig":
        names = {f.name for f in fields(cls)}
        unknown = set(d) - names
        if unknown:
            raise ValueError(f"unknown model config keys: {sorted(unknown)}")
        return cls(**d)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _time_mask(lengths: torch.Tensor, T: int) -> torch.Tensor:
    """Return a bool mask [B, T]: True at valid time steps."""
    return torch.arange(T, device=lengths.device)[None, :] < lengths[:, None]


class ChanNorm(nn.Module):
    """LayerNorm over channels of a [B, C, T] tensor (per time step)."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.ln = nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.ln(x.transpose(1, 2)).transpose(1, 2)


#: "native" uses torch's conv1d (MIOpen / cuDNN / CPU). "gemm" computes
#: every convolution with unfold + einsum (rocBLAS GEMMs) and the
#: depthwise convolution with shifted multiply-adds. Both give the same
#: result. On ROCm, MIOpen searches kernels for each new input shape, so
#: train with MIOPEN_FIND_MODE=FAST and bucketed lengths (``pad_multiple``).
#: Measured on the RX 7800 XT (B=16, T=400-800, 10.3M params): about 80 ms
#: per step for both; gemm uses ~70% more memory.
CONV_IMPL = os.environ.get("FIDETYPE_CONV_IMPL", "native")


def conv1d_gemm(x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor | None, stride: int = 1,
                dilation: int = 1, groups: int = 1) -> torch.Tensor:
    """Same result as ``F.conv1d`` (no padding), computed without conv kernels."""
    B, Cin, Tp = x.shape
    Cout, Cg, k = weight.shape
    span = (k - 1) * dilation + 1
    Tout = (Tp - span) // stride + 1
    if groups == 1:
        if k == 1:
            y = torch.einsum("oc,bct->bot", weight[:, :, 0], x[:, :, : (Tout - 1) * stride + 1 : stride])
        else:
            u = x.unfold(2, span, stride)[..., ::dilation]  # [B, Cin, Tout, k]
            y = torch.einsum("bctk,ock->bot", u, weight)
    elif groups == Cin == Cout and Cg == 1:
        w = weight[:, 0, :].to(x.dtype)
        y = None
        for j in range(k):
            o = j * dilation
            term = w[None, :, j, None] * x[:, :, o : o + (Tout - 1) * stride + 1 : stride]
            y = term if y is None else y + term
    else:
        return F.conv1d(x, weight, bias, stride=stride, dilation=dilation, groups=groups)
    if bias is not None:
        y = y + bias.to(y.dtype)[None, :, None]
    return y


class PadConv1d(nn.Module):
    """Conv1d with 'same'-style length handling.

    The total padding is (k-1)*dilation, so the output length is
    ceil(T / stride). In causal mode all padding is on the left. Output j
    then sees inputs <= j * stride. Otherwise the padding is split
    between the two sides.
    """

    def __init__(self, cin: int, cout: int, k: int, stride: int = 1, dilation: int = 1,
                 causal: bool = False, groups: int = 1) -> None:
        super().__init__()
        self.conv = nn.Conv1d(cin, cout, k, stride=stride, dilation=dilation, groups=groups)
        total = (k - 1) * dilation
        self.pad = (total, 0) if causal else (total // 2, total - total // 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.pad(x, self.pad) if any(self.pad) else x
        if CONV_IMPL == "gemm":
            c = self.conv
            return conv1d_gemm(x, c.weight, c.bias, c.stride[0], c.dilation[0], c.groups)
        return self.conv(x)


class ResBlock(nn.Module):
    def __init__(self, dim: int, k: int, dilation: int, dropout: float, causal: bool) -> None:
        super().__init__()
        self.norm = ChanNorm(dim)
        self.conv = PadConv1d(dim, dim, k, dilation=dilation, causal=causal)
        self.proj = PadConv1d(dim, dim, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
        h = self.norm(x) * m
        h = self.drop(F.gelu(self.conv(h)))
        return (x + self.drop(self.proj(h))) * m


class FeedForward(nn.Module):
    def __init__(self, dim: int, hidden: int, dropout: float) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.LayerNorm(dim), nn.Linear(dim, hidden), nn.SiLU(), nn.Dropout(dropout),
                                 nn.Linear(hidden, dim), nn.Dropout(dropout))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class MHSA(nn.Module):
    def __init__(self, dim: int, heads: int, dropout: float) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.qkv = nn.Linear(dim, 3 * dim)
        self.out = nn.Linear(dim, dim)
        self.heads = heads
        self.dropout = dropout
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape
        q, k, v = self.qkv(self.norm(x)).view(B, T, 3, self.heads, D // self.heads).permute(2, 0, 3, 1, 4)
        y = F.scaled_dot_product_attention(q, k, v, attn_mask=attn_mask,
                                           dropout_p=self.dropout if self.training else 0.0)
        return self.drop(self.out(y.transpose(1, 2).reshape(B, T, D)))


class ConvModule(nn.Module):
    def __init__(self, dim: int, k: int, dropout: float, causal: bool) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.pw1 = nn.Linear(dim, 2 * dim)
        self.dw = PadConv1d(dim, dim, k, causal=causal, groups=dim)
        self.norm2 = nn.LayerNorm(dim)
        self.pw2 = nn.Linear(dim, dim)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
        h = F.glu(self.pw1(self.norm(x)), dim=-1) * m[..., None]
        h = self.dw(h.transpose(1, 2)).transpose(1, 2)
        h = self.pw2(F.silu(self.norm2(h)))
        return self.drop(h)


class ConformerBlock(nn.Module):
    def __init__(self, dim: int, heads: int, ffn: int, k: int, dropout: float, causal: bool) -> None:
        super().__init__()
        self.ff1 = FeedForward(dim, ffn, dropout)
        self.attn = MHSA(dim, heads, dropout)
        self.conv = ConvModule(dim, k, dropout, causal)
        self.ff2 = FeedForward(dim, ffn, dropout)
        self.norm = nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor, m: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
        x = x + 0.5 * self.ff1(x)
        x = x + self.attn(x, attn_mask)
        x = x + self.conv(x, m)
        x = x + 0.5 * self.ff2(x)
        return self.norm(x) * m[..., None]


class ConvCTC(nn.Module):
    """The baseline MEG-to-text CTC model. See the module docstring."""

    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()
        self.cfg = cfg
        causal = cfg.lookahead_frames is not None
        self.causal = causal
        self.in_drop = nn.Dropout(cfg.input_dropout)
        self.spatial = PadConv1d(cfg.n_channels, cfg.spatial_dim, 1)
        if cfg.subject_layer:
            eye = torch.eye(cfg.spatial_dim).repeat(cfg.n_subjects, 1, 1)
            self.subj_w = nn.Parameter(eye)
            self.subj_b = nn.Parameter(torch.zeros(cfg.n_subjects, cfg.spatial_dim))
        self.conv_in = PadConv1d(cfg.spatial_dim, cfg.conv_dim, 1)
        self.blocks = nn.ModuleList(
            ResBlock(cfg.conv_dim, cfg.conv_kernel, 2 ** (i % cfg.conv_dilation_cycle), cfg.dropout, causal)
            for i in range(cfg.conv_blocks)
        )
        self.down_norm = ChanNorm(cfg.conv_dim)
        self.down = PadConv1d(cfg.conv_dim, cfg.model_dim, cfg.downsample_kernel, stride=cfg.downsample,
                              causal=causal)
        self.frame_norm = nn.LayerNorm(cfg.model_dim)
        self.aux_head = nn.Linear(cfg.model_dim, cfg.vocab_size)
        if cfg.self_condition:
            self.cond = nn.Linear(cfg.vocab_size, cfg.model_dim)
        self.conformer = nn.ModuleList(
            ConformerBlock(cfg.model_dim, cfg.conformer_heads, cfg.conformer_ffn, cfg.conformer_kernel,
                           cfg.dropout, causal)
            for _ in range(cfg.conformer_layers)
        )
        self.head = nn.Linear(cfg.model_dim, cfg.vocab_size)

    # --- helpers -----------------------------------------------------------

    def out_lengths(self, lengths: torch.Tensor) -> torch.Tensor:
        s = self.cfg.downsample
        return torch.div(lengths + s - 1, s, rounding_mode="floor")

    def total_lookahead_frames(self) -> int | None:
        if self.cfg.lookahead_frames is None:
            return None
        return self.cfg.lookahead_frames * self.cfg.conformer_layers

    def frame_period_s(self, sfreq: float = 100.0) -> float:
        return self.cfg.downsample / sfreq

    def attention_mask(self, out_len: torch.Tensor, T: int) -> torch.Tensor:
        """Return a bool mask [B, 1, T, T]: True where query i may see key j."""
        keys = _time_mask(out_len, T)[:, None, None, :]
        if self.cfg.lookahead_frames is None:
            return keys
        i = torch.arange(T, device=out_len.device)
        lim = (i[None, :] <= i[:, None] + self.cfg.lookahead_frames)[None, None]
        return keys & lim

    def param_count(self) -> dict[str, int]:
        def n(mods: Any) -> int:
            if isinstance(mods, nn.Parameter):
                return mods.numel()
            return sum(p.numel() for p in mods.parameters())

        parts = {
            "spatial": n(self.spatial),
            "subject_layer": (n(self.subj_w) + n(self.subj_b)) if self.cfg.subject_layer else 0,
            "conv_stack": n(self.conv_in) + n(self.blocks),
            "downsample": n(self.down_norm) + n(self.down) + n(self.frame_norm),
            "aux_head": n(self.aux_head) + (n(self.cond) if self.cfg.self_condition else 0),
            "conformer": n(self.conformer),
            "head": n(self.head),
        }
        parts["total"] = sum(p.numel() for p in self.parameters())
        return parts

    # --- forward -----------------------------------------------------------

    def forward(self, x: torch.Tensor, lengths: torch.Tensor, subjects: torch.Tensor) -> dict[str, torch.Tensor]:
        """x [B, C, T] at 100 Hz. Returns logits [B, T', V], aux_logits and out_lengths [B]."""
        B, C, T = x.shape
        m = _time_mask(lengths, T)[:, None, :].to(x.dtype)
        h = self.spatial(self.in_drop(x))
        if self.cfg.subject_layer:
            h = torch.einsum("bct,bcd->bdt", h, self.subj_w[subjects]) + self.subj_b[subjects][..., None]
        h = self.conv_in(h * m) * m
        for blk in self.blocks:
            h = blk(h, m)
        h = self.down(self.down_norm(h) * m)  # [B, D, T']
        out_len = self.out_lengths(lengths)
        Tp = h.shape[-1]
        mf = _time_mask(out_len, Tp)
        h = self.frame_norm(h.transpose(1, 2)) * mf[..., None].to(h.dtype)  # [B, T', D]
        aux_logits = self.aux_head(h)
        if self.cfg.self_condition:
            h = h + self.cond(aux_logits.float().softmax(-1).to(h.dtype))
        am = self.attention_mask(out_len, Tp)
        mfd = mf.to(h.dtype)
        for blk in self.conformer:
            h = blk(h, mfd, am)
        return {"logits": self.head(h), "aux_logits": aux_logits, "out_lengths": out_len}

    def loss(self, out: dict[str, torch.Tensor], targets: torch.Tensor,
             target_lengths: torch.Tensor) -> dict[str, torch.Tensor]:
        """Return the CTC losses (mean over the batch, per target char)."""

        def ctc(logits: torch.Tensor) -> torch.Tensor:
            lp = logits.float().log_softmax(-1).transpose(0, 1)  # [T', B, V]
            return F.ctc_loss(lp, targets, out["out_lengths"], target_lengths, blank=BLANK_ID,
                              reduction="mean", zero_infinity=True)

        final, aux = ctc(out["logits"]), ctc(out["aux_logits"])
        w = self.cfg.aux_weight
        return {"loss": (1 - w) * final + w * aux, "ctc_final": final, "ctc_aux": aux}


def greedy_decode_batch(logits: torch.Tensor, out_lengths: torch.Tensor) -> list[str]:
    """CTC best-path decoding of a batch of logits [B, T', V]."""
    from fidetype.streams.vocab import VOCAB

    best = logits.argmax(-1).cpu().numpy()
    out = []
    for b, L in enumerate(out_lengths.cpu().tolist()):
        seq, prev = [], -1
        for t in best[b, :L]:
            if t != prev and t != BLANK_ID:
                seq.append(VOCAB[t])
            prev = t
        out.append("".join(seq))
    return out


def format_param_report(model: ConvCTC) -> str:
    pc = model.param_count()
    lines = [f"{k:>14}: {v:>12,}" for k, v in pc.items()]
    return "\n".join(lines)


__all__ = ["ConvCTC", "ModelConfig", "format_param_report", "greedy_decode_batch"]
