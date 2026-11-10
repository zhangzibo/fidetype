"""Sentence-context keystroke decoder (M1-15; our own design and code).

**Idea.** Brain2Qwerty v1 (Levy et al. 2025; ``wiki/sources/brain2qwerty-v1.md``)
classifies each keystroke from one MEG window, then runs a Transformer over
the keystroke embeddings of the whole sentence. The Transformer step lowered
MEG CER from 0.67 to 0.36 (Fig. 2). This module applies the same idea with
our own, much smaller model. It does not copy the Brain2Qwerty code.

**Setting.** Synchronous, oracle key timing (as :mod:`fidetype.decoders.keystroke`):
the key times come from the keyboard log. Each window is -0.2 .. +0.3 s
around one key press.

Pipeline (one sentence of K key presses)::

    K windows [K, 306, W] (W = 50 samples at 100 Hz)
    spatial 1x1 conv 306 -> D_s
    participant affine layer (one D_s x D_s matrix + bias per participant)
    dilated residual Conv1d stack, width H          (same blocks as ConvCTC)
    time pooling -> one key embedding of size D     ("flatten" or "attention")
      -> per-key head (27 classes)                  <- "conv" loss, weight key_head_weight
    + positional encoding over the key index (sinusoidal)
    (optional) + embedding of log(1 + time since the previous key)
    Transformer encoder over the K key embeddings (pre-norm, MHSA + FFN)
    final head (27 classes: a-z and space)          <- main loss

The module names ``spatial``, ``subj_w``, ``subj_b``, ``conv_in`` and
``blocks`` are the same as in :class:`fidetype.decoders.conv_ctc.ConvCTC`.
Thus ``train.init_from`` can copy the conv weights of a ConvCTC checkpoint
when the shapes agree.

Causal mode
-----------
``lookahead_keys = None`` (default): non-causal. Every key sees all keys
of the sentence (the v1 setting; the output waits for the sentence end).
``lookahead_keys = n`` (int >= 0): the output at key i depends on keys
j <= i + n only (the first Transformer layer looks ahead n keys, the later
layers are strictly causal, so the total lookahead is n). With
``n = 0`` the output at key i depends only on the windows of keys 0..i,
so the decoder can run online (one output per key press). The window of
key i still reaches 0.3 s after that key press.

Participants
------------
The participant layer is indexed by the *participant*, not the subject ID.
In SpanishBCBL, S1/S18, S4/S14 and S5/S10/S21 are one person each
(:data:`fidetype.data.spanishbcbl.PARTICIPANT_GROUPS`); the cache sidecars
carry the ``participant`` field and :class:`KeySentences` maps it to one index.

Streams
-------
:func:`sentence_streams` turns the per-key log-probabilities into the CTC
form of :func:`fidetype.decoders.keystroke.keystroke_stream` (key frame,
blank frame, key frame, ...). The CTC beam + char LM and the trust core read
these streams unchanged.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset

from fidetype.decoders.conv_ctc import ChanNorm, FeedForward, MHSA, PadConv1d, ResBlock
from fidetype.decoders.dataset import KEY_IGNORE, N_KEY_CLASSES, MEGSegments
from fidetype.decoders.keystroke import KEY_CLASSES, keystroke_stream, stream_meta
from fidetype.streams.spec import NeuralTextStream

DECODER_NAME = "fidetype-keystroke-sentence"
WINDOW_S = (-0.2, 0.3)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class SentenceModelConfig:
    n_channels: int = 306
    n_subjects: int = 1  # number of participants (index of the participant layer)
    window_samples: int = 50  # W: samples per key window (0.5 s at 100 Hz)
    spatial_dim: int = 128  # D_s
    subject_layer: bool = True
    conv_dim: int = 256  # H
    conv_blocks: int = 4
    conv_kernel: int = 5
    conv_dilation_cycle: int = 5
    pool: str = "flatten"  # "flatten" (time bins -> linear) or "attention" (attention pooling)
    time_bins: int = 10  # "flatten": average the window into this many bins (W % time_bins == 0)
    key_dim: int = 192  # D
    trans_layers: int = 4
    trans_heads: int = 4
    trans_ffn: int = 512
    dropout: float = 0.3
    input_dropout: float = 0.1
    lookahead_keys: int | None = None  # None = non-causal; 0 = causal (see the module docstring)
    use_key_intervals: bool = False  # add an embedding of log(1 + seconds since the previous key)
    n_classes: int = N_KEY_CLASSES  # 27
    key_head_weight: float = 0.3  # loss weight of the per-key (conv only) head; 0 = no head
    label_smoothing: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SentenceModelConfig":
        names = {f.name for f in fields(cls)}
        unknown = set(d) - names
        if unknown:
            raise ValueError(f"unknown model config keys: {sorted(unknown)}")
        return cls(**d)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sinusoidal_positions(n: int, dim: int, device: torch.device | None = None) -> torch.Tensor:
    """Return the sinusoidal position table [n, dim] (Vaswani et al. 2017)."""
    pos = torch.arange(n, dtype=torch.float32, device=device)[:, None]
    i = torch.arange(0, dim, 2, dtype=torch.float32, device=device)
    ang = pos / torch.pow(10000.0, i / dim)
    pe = torch.zeros(n, dim, device=device)
    pe[:, 0::2] = torch.sin(ang)
    pe[:, 1::2] = torch.cos(ang[:, : dim // 2])
    return pe


class TransformerBlock(nn.Module):
    """Pre-norm Transformer encoder block (MHSA + FFN), from the ConvCTC parts."""

    def __init__(self, dim: int, heads: int, ffn: int, dropout: float) -> None:
        super().__init__()
        self.attn = MHSA(dim, heads, dropout)
        self.ff = FeedForward(dim, ffn, dropout)

    def forward(self, x: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(x, attn_mask)
        return x + self.ff(x)


class SentenceContextDecoder(nn.Module):
    """Per-key conv encoder + Transformer over the keys of one sentence."""

    def __init__(self, cfg: SentenceModelConfig) -> None:
        super().__init__()
        if cfg.pool not in ("flatten", "attention"):
            raise ValueError(f"pool must be 'flatten' or 'attention', not {cfg.pool!r}")
        if cfg.pool == "flatten" and cfg.window_samples % cfg.time_bins:
            raise ValueError("window_samples must be a multiple of time_bins")
        if cfg.key_dim % cfg.trans_heads:
            raise ValueError("key_dim must be a multiple of trans_heads")
        self.cfg = cfg
        self.in_drop = nn.Dropout(cfg.input_dropout)
        # Conv encoder: the names match ConvCTC, so its weights can initialise these.
        self.spatial = PadConv1d(cfg.n_channels, cfg.spatial_dim, 1)
        if cfg.subject_layer:
            self.subj_w = nn.Parameter(torch.eye(cfg.spatial_dim).repeat(cfg.n_subjects, 1, 1))
            self.subj_b = nn.Parameter(torch.zeros(cfg.n_subjects, cfg.spatial_dim))
        self.conv_in = PadConv1d(cfg.spatial_dim, cfg.conv_dim, 1)
        self.blocks = nn.ModuleList(
            ResBlock(cfg.conv_dim, cfg.conv_kernel, 2 ** (i % cfg.conv_dilation_cycle), cfg.dropout, False)
            for i in range(cfg.conv_blocks)
        )
        self.pool_norm = ChanNorm(cfg.conv_dim)
        if cfg.pool == "flatten":
            self.pool_proj = nn.Linear(cfg.conv_dim * cfg.time_bins, cfg.key_dim)
        else:
            self.pool_score = nn.Linear(cfg.conv_dim, 1)
            self.pool_pos = nn.Parameter(torch.zeros(cfg.window_samples))
            self.pool_proj = nn.Linear(cfg.conv_dim, cfg.key_dim)
        self.key_norm = nn.LayerNorm(cfg.key_dim)
        self.key_drop = nn.Dropout(cfg.dropout)
        if cfg.use_key_intervals:
            self.interval = nn.Linear(1, cfg.key_dim)
        self.trans = nn.ModuleList(
            TransformerBlock(cfg.key_dim, cfg.trans_heads, cfg.trans_ffn, cfg.dropout)
            for _ in range(cfg.trans_layers)
        )
        self.out_norm = nn.LayerNorm(cfg.key_dim)
        self.head = nn.Linear(cfg.key_dim, cfg.n_classes)
        self.key_head = nn.Linear(cfg.key_dim, cfg.n_classes) if cfg.key_head_weight > 0 else None

    @property
    def has_key_head(self) -> bool:
        return self.key_head is not None

    @property
    def causal(self) -> bool:
        return self.cfg.lookahead_keys is not None

    def param_count(self) -> dict[str, int]:
        def n(*mods: Any) -> int:
            tot = 0
            for m in mods:
                if m is None:
                    continue
                tot += m.numel() if isinstance(m, nn.Parameter) else sum(p.numel() for p in m.parameters())
            return tot

        c = self.cfg
        parts = {
            "spatial": n(self.spatial),
            "subject_layer": n(self.subj_w, self.subj_b) if c.subject_layer else 0,
            "conv_stack": n(self.conv_in, self.blocks),
            "pool": sum(p.numel() for k, p in self.named_parameters() if k.startswith("pool_"))
            + n(self.key_norm),
            "transformer": n(self.trans, self.out_norm) + (n(self.interval) if c.use_key_intervals else 0),
            "head": n(self.head),
            "key_head": n(self.key_head),
        }
        parts["total"] = sum(p.numel() for p in self.parameters())
        return parts

    # --- parts -------------------------------------------------------------

    def encode_windows(self, w: torch.Tensor, subjects: torch.Tensor) -> torch.Tensor:
        """w [N, C, W], subjects [N] -> key embeddings [N, D]."""
        c = self.cfg
        h = self.spatial(self.in_drop(w))
        if c.subject_layer:
            h = torch.einsum("bct,bcd->bdt", h, self.subj_w[subjects]) + self.subj_b[subjects][..., None]
        h = self.conv_in(h)
        m = torch.ones(h.shape[0], 1, h.shape[-1], dtype=h.dtype, device=h.device)
        for blk in self.blocks:
            h = blk(h, m)
        h = self.pool_norm(h)  # [N, H, W]
        if c.pool == "flatten":
            N, H, W = h.shape
            h = h.reshape(N, H, c.time_bins, W // c.time_bins).mean(-1).reshape(N, H * c.time_bins)
            e = self.pool_proj(h)
        else:
            s = self.pool_score(h.transpose(1, 2)).squeeze(-1) + self.pool_pos[: h.shape[-1]]
            e = self.pool_proj(torch.einsum("nt,nht->nh", s.float().softmax(-1).to(h.dtype), h))
        return self.key_norm(e)

    def attention_mask(self, key_mask: torch.Tensor, lookahead: int | None = -1) -> torch.Tensor:
        """Return a bool mask [B, 1, K, K]: True where query key i may see key j.

        Valid queries never see padded keys. With a lookahead ``n`` (default:
        ``cfg.lookahead_keys``), key i sees keys j <= i + n; ``None`` = no
        limit. Each query always sees itself, so a padded query never has an
        empty row (that would give NaN in the softmax).
        """
        if lookahead == -1:
            lookahead = self.cfg.lookahead_keys
        B, K = key_mask.shape
        m = key_mask[:, None, None, :].expand(B, 1, K, K)
        i = torch.arange(K, device=key_mask.device)
        if lookahead is not None:
            m = m & (i[None, :] <= i[:, None] + lookahead)[None, None]
        return m | torch.eye(K, dtype=torch.bool, device=key_mask.device)[None, None]

    # --- forward -----------------------------------------------------------

    def forward(self, x: torch.Tensor, key_mask: torch.Tensor, subjects: torch.Tensor,
                key_times: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        """x [B, K, C, W] (padded windows), key_mask [B, K] (True at real keys),
        subjects [B] (participant index), key_times [B, K] seconds (needed
        only with ``use_key_intervals``).

        Returns ``logits`` [B, K, 27], ``key_logits`` [B, K, 27] (per-key
        head, if any) and ``key_mask``. Rows at padded keys are not defined.
        """
        B, K = key_mask.shape
        D = self.cfg.key_dim
        flat_subj = subjects[:, None].expand(B, K)[key_mask]
        emb = self.encode_windows(x[key_mask], flat_subj)  # only the real windows
        e = emb.new_zeros(B, K, D)
        e[key_mask] = emb
        out: dict[str, torch.Tensor] = {"key_mask": key_mask}
        if self.key_head is not None:
            out["key_logits"] = self.key_head(e)
        h = self.key_drop(e) + sinusoidal_positions(K, D, e.device).to(e.dtype)[None]
        if self.cfg.use_key_intervals:
            if key_times is None:
                raise ValueError("use_key_intervals needs key_times")
            dt = torch.diff(key_times.float(), dim=1, prepend=key_times[:, :1].float()).clamp(min=0)
            h = h + self.interval(torch.log1p(dt)[..., None]).to(h.dtype)
        # Causal mode: only the first layer looks ahead; the later layers are
        # strictly causal. Thus the total lookahead is lookahead_keys (not
        # n_layers * lookahead_keys).
        am = self.attention_mask(key_mask)
        am_later = am if self.cfg.lookahead_keys is None else self.attention_mask(key_mask, 0)
        for li, blk in enumerate(self.trans):
            h = blk(h, am if li == 0 else am_later)
        out["logits"] = self.head(self.out_norm(h))
        return out

    def loss(self, out: dict[str, torch.Tensor], key_labels: torch.Tensor) -> dict[str, torch.Tensor]:
        """Cross-entropy over the labelled keys (labels padded with -100).

        ``loss = CE(final) + key_head_weight * CE(per-key head)``. Also
        returns the number of labelled keys and the number of correct
        argmax predictions of each head.
        """
        valid = key_labels != KEY_IGNORE
        n = valid.sum()

        def ce(lg: torch.Tensor) -> torch.Tensor:
            return F.cross_entropy(lg.float().reshape(-1, lg.shape[-1]), key_labels.reshape(-1),
                                   ignore_index=KEY_IGNORE, reduction="sum",
                                   label_smoothing=self.cfg.label_smoothing) / n.clamp(min=1)

        main = ce(out["logits"])
        res = {"loss": main, "ce": main.detach(), "n": n.detach(),
               "correct": ((out["logits"].argmax(-1) == key_labels) & valid).sum().detach()}
        if "key_logits" in out:
            kc = ce(out["key_logits"])
            res["loss"] = main + self.cfg.key_head_weight * kc
            res["ce_conv"] = kc.detach()
            res["correct_conv"] = ((out["key_logits"].argmax(-1) == key_labels) & valid).sum().detach()
        return res


def init_from_convctc(model: SentenceContextDecoder, path: str | Path) -> tuple[list[str], list[str]]:
    """Copy the conv-encoder weights of a ConvCTC (or sentence) checkpoint with
    the same names and shapes. Returns (loaded names, skipped names)."""
    src = torch.load(path, map_location="cpu", weights_only=False)["model"]
    own = model.state_dict()
    ok = {k: v for k, v in src.items() if k in own and own[k].shape == v.shape}
    own.update(ok)
    model.load_state_dict(own)
    return sorted(ok), sorted(k for k in own if k not in ok)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class KeyAugmentConfig:
    """Training augmentations for key windows. Each one is off at 0."""

    key_jitter_s: float = 0.02  # shift each window centre by up to +/- this (seconds)
    channel_offset_std: float = 0.3  # per-sentence, per-channel constant offset ~ N(0, std)
    channel_mask_n: int = 1  # channel masks per sentence
    channel_mask_max: int = 30  # channels per mask
    scale_std: float = 0.1  # per-sentence amplitude scale exp(N(0, std))

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "KeyAugmentConfig | None":
        if d is None or d is False:
            return None
        base = asdict(cls())
        unknown = set(d) - set(base)
        if unknown:
            raise ValueError(f"unknown augment keys: {sorted(unknown)}")
        base.update(d)
        return cls(**base)


def cut_windows(block: np.ndarray, centres: np.ndarray, i0: int, n_samp: int) -> np.ndarray:
    """Return windows [K, C, n_samp] of ``block`` [C, T] at ``centres + i0 ...``.

    The function reads one contiguous slice of the (memory-mapped) block.
    Samples outside the block repeat the edge sample.
    """
    C, T = block.shape
    K = len(centres)
    if K == 0:
        return np.zeros((0, C, n_samp), dtype=np.float32)
    lo = int(max(0, centres.min() + i0))
    hi = int(min(T, centres.max() + i0 + n_samp))
    part = np.asarray(block[:, lo:hi], dtype=np.float32)
    idx = np.clip(centres[:, None] + i0 + np.arange(n_samp)[None, :], 0, T - 1) - lo
    idx = np.clip(idx, 0, part.shape[1] - 1)
    return np.ascontiguousarray(part[:, idx].transpose(1, 0, 2))  # [K, C, S]


class KeySentences(Dataset):
    """One item per sentence: the MEG windows of its key presses.

    The dataset reuses :class:`fidetype.decoders.dataset.MEGSegments` to scan
    the cache and to memory-map the blocks. Practice trials are excluded.
    Keys that are not a-z or space (return, backspace) are dropped, as in
    :mod:`fidetype.decoders.keystroke`. Sentences with no such key are dropped.

    Item: ``x`` [K, C, W] float32, ``key_label`` [K] (0..26), ``key_time`` [K]
    (seconds from the segment start, no jitter), ``subject`` (participant
    index), and ``subject_id``, ``participant``, texts and ``index``.
    """

    def __init__(
        self,
        root: str | Path,
        splits: Sequence[str] = ("train",),
        subjects: Sequence[str] | None = None,
        subject_map: dict[str, int] | None = None,
        augment: KeyAugmentConfig | None = None,
        seed: int = 0,
        mmap_dir: str | Path | None = None,
        window_s: tuple[float, float] = WINDOW_S,
        blocks: Sequence[str] | None = None,
        max_segments: int | None = None,
    ) -> None:
        base = MEGSegments(root, splits, subjects, subject_map, None, seed, mmap_dir, blocks=blocks)
        self.base = base
        self.subject_map = base.subject_map
        keep = []
        for s in base.segments:
            ok = [(k, lab) for k, lab in zip(s.key_abs, s.key_labels) if lab != KEY_IGNORE]
            if ok:
                keep.append(replace(s, key_abs=tuple(k for k, _ in ok), key_labels=tuple(lab for _, lab in ok)))
        if max_segments is not None:
            keep = keep[:max_segments]
        base.segments = keep
        self.segments = keep
        self.augment = augment
        self.seed = int(seed)
        self.epoch = 0
        self.window_s = tuple(window_s)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.segments)

    def lengths(self) -> list[int]:
        """Number of keys of each sentence (for the bucket sampler)."""
        return [len(s.key_abs) for s in self.segments]

    def window_samples(self, sfreq: float = 100.0) -> int:
        return int(round((self.window_s[1] - self.window_s[0]) * sfreq))

    def __getitem__(self, i: int) -> dict[str, Any]:
        seg = self.segments[i]
        arr = self.base._array(seg.npz)
        sf = self.base._sfreq[seg.npz]
        i0 = int(round(self.window_s[0] * sf))
        n_samp = self.window_samples(sf)
        centres = np.asarray(seg.key_abs, dtype=np.int64)
        a = self.augment
        rng = np.random.default_rng([self.seed, self.epoch, i])
        if a is not None and a.key_jitter_s > 0:
            j = int(round(a.key_jitter_s * sf))
            centres = centres + rng.integers(-j, j + 1, size=len(centres))
        x = cut_windows(arr, centres, i0, n_samp)
        if a is not None:
            K, C, _ = x.shape
            if a.scale_std > 0:
                x = x * np.float32(math.exp(rng.normal(0, a.scale_std)))
            if a.channel_offset_std > 0:
                x = x + rng.normal(0, a.channel_offset_std, size=(1, C, 1)).astype(np.float32)
            for _ in range(a.channel_mask_n):
                w = int(rng.integers(0, a.channel_mask_max + 1))
                if 0 < w < C:
                    x[:, rng.choice(C, size=w, replace=False)] = 0.0
        return {
            "x": torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)),
            "key_label": torch.tensor(seg.key_labels, dtype=torch.long),
            "key_time": torch.tensor((np.asarray(seg.key_abs) - seg.start) / sf, dtype=torch.float64),
            "subject": self.subject_map[seg.participant],
            "subject_id": seg.subject,
            "participant": seg.participant,
            "target_text": seg.target_text,
            "typed_text": seg.typed_text,
            "index": i,
        }


def collate_sentences(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Pad a list of sentence items.

    Returns ``x`` [B, K_max, C, W] (zero padded), ``key_mask`` [B, K_max],
    ``key_labels`` [B, K_max] (padded with -100), ``key_times`` [B, K_max]
    (float32, padded with the last time), ``subjects`` [B] and the lists.
    """
    B = len(batch)
    _, C, W = batch[0]["x"].shape
    K = max(1, max(b["x"].shape[0] for b in batch))
    x = torch.zeros(B, K, C, W)
    km = torch.zeros(B, K, dtype=torch.bool)
    kl = torch.full((B, K), KEY_IGNORE, dtype=torch.long)
    kt = torch.zeros(B, K, dtype=torch.float32)
    for i, b in enumerate(batch):
        n = b["x"].shape[0]
        x[i, :n] = b["x"]
        km[i, :n] = True
        kl[i, :n] = b["key_label"]
        if n:
            kt[i, :n] = b["key_time"].float()
            kt[i, n:] = float(b["key_time"][-1])
    out: dict[str, Any] = {"x": x, "key_mask": km, "key_labels": kl, "key_times": kt,
                           "subjects": torch.tensor([b["subject"] for b in batch], dtype=torch.long)}
    for k in ("subject_id", "participant", "target_text", "typed_text", "index"):
        out[k] = [b[k] for b in batch]
    return out


# ---------------------------------------------------------------------------
# Decoding and streams
# ---------------------------------------------------------------------------


def greedy_text(logits: torch.Tensor, n_keys: int) -> str:
    """Argmax character of each of the first ``n_keys`` keys (one key = one char)."""
    if n_keys == 0:
        return ""
    return "".join(KEY_CLASSES[int(i)] for i in logits[:n_keys].argmax(-1).tolist())


def sentence_streams(
    log_probs: torch.Tensor | np.ndarray,
    key_mask: torch.Tensor | np.ndarray,
    key_times: torch.Tensor | np.ndarray,
    metas: Sequence[dict[str, Any] | None],
    **kw: Any,
) -> list[NeuralTextStream]:
    """Return one CTC-form keystroke stream per sentence of a batch.

    ``log_probs`` [B, K, 27] (log-softmax or logits; each row is renormalised),
    ``key_mask`` [B, K], ``key_times`` [B, K] seconds. ``kw`` goes to
    :func:`fidetype.decoders.keystroke.keystroke_stream` (``key_blank``,
    ``gap_nonblank``).
    """
    lp = log_probs.detach().float().cpu().numpy() if isinstance(log_probs, torch.Tensor) else np.asarray(log_probs)
    km = key_mask.cpu().numpy() if isinstance(key_mask, torch.Tensor) else np.asarray(key_mask)
    kt = key_times.cpu().numpy() if isinstance(key_times, torch.Tensor) else np.asarray(key_times)
    out = []
    for b in range(lp.shape[0]):
        n = int(km[b].sum())
        out.append(keystroke_stream(lp[b, :n].astype(np.float64), kt[b, :n].astype(np.float64),
                                    dict(metas[b] or {}), source=DECODER_NAME, **kw))
    return out


def sentence_stream_meta(model: SentenceContextDecoder, subject: str, session: str,
                         extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """The namespaced stream ``meta`` (no labels) for this decoder."""
    meta = stream_meta(subject, session, {
        "decoder.name": DECODER_NAME,
        "decoder.causal": model.cfg.lookahead_keys == 0,
        "decoder.lookahead_keys": model.cfg.lookahead_keys,
        "decoder.context": "sentence",
    })
    meta.update(extra or {})
    return meta


__all__ = [
    "DECODER_NAME",
    "KeyAugmentConfig",
    "KeySentences",
    "SentenceContextDecoder",
    "SentenceModelConfig",
    "collate_sentences",
    "cut_windows",
    "greedy_text",
    "init_from_convctc",
    "sentence_stream_meta",
    "sentence_streams",
    "sinusoidal_positions",
]
