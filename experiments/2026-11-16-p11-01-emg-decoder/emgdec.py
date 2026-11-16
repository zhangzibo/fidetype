"""P11-01 continuous EMG-to-text decoder: data access, model, decoding, metric, NTS export.

Our own implementation (Apache-2.0). We read the emg2qwerty paper (arXiv 2410.20081) for the
published numbers and the split scheme only. No code from the emg2qwerty repository is read or
copied. The feature cache comes from ``prep.py``.

Model ("CRT", causal ring-TCN):
  input (B, T, 32, 12) log band power at 100 frames/s
  -> fixed normalisation (mean / std of the generic-train sessions)
  -> per wristband: circular conv over the 16-electrode ring (kernel 5) -> linear -> d/2
  -> concat (d) -> N causal residual blocks (LayerNorm, depthwise causal dilated conv,
     pointwise feed-forward, dropout); dilations 1,2,4,8 repeated
  -> LayerNorm -> linear -> V log-probs (CTC, blank 0).
Every layer is causal: the output at frame t uses frames <= t only (no lookahead).
"""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

N_CH = 32
N_EL = 16
N_BANDS = 12
BLANK = 0
FRAME_S = 0.01  # HOP / FS
WIN_S = 0.032


# --- configuration ------------------------------------------------------------------------------


@dataclass
class ModelCfg:
    d: int = 512
    ring_c: int = 32
    ring_k: int = 5
    kernel: int = 5
    dilations: tuple[int, ...] = (1, 2, 4, 8, 1, 2, 4, 8)
    ff_mult: int = 2
    dropout: float = 0.1
    vocab: int = 98
    #: "torch" = nn.Conv1d kernels; "shift" = the same function from shifted slices + matmul (no MIOpen
    #: conv kernels on ROCm). Same parameters and state_dict; the budget pilot picks the faster one.
    conv_impl: str = "torch"

    def receptive_field(self) -> int:
        return 1 + sum((self.kernel - 1) * d for d in self.dilations)


@dataclass
class AugCfg:
    rotate: bool = True  # electrode ring rotation by -1/0/+1 per band
    jitter: int = 6  # max relative time shift between the two bands, frames (60 ms)
    time_masks: int = 2
    time_mask_max: int = 15
    band_masks: int = 1
    band_mask_max: int = 3
    gain_sd: float = 0.2  # per-channel offset in the log-power domain


@dataclass
class TrainCfg:
    window: int = 400  # frames (4 s)
    batch: int = 64
    steps: int = 60_000
    lr: float = 1e-3
    lr_min: float = 1e-6
    warmup: int = 2_000
    weight_decay: float = 0.01
    clip: float = 1.0
    seed: int = 0
    val_every: int = 2_000
    ckpt_minutes: float = 4.0
    amp: str = "none"  # none | bf16
    model: ModelCfg = field(default_factory=ModelCfg)
    aug: AugCfg = field(default_factory=AugCfg)

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "TrainCfg":
        d = dict(d)
        m = ModelCfg(**{**d.pop("model", {})})
        m.dilations = tuple(m.dilations)
        a = AugCfg(**d.pop("aug", {}))
        return TrainCfg(**d, model=m, aug=a)


# --- data -----------------------------------------------------------------------------------------


class SessionStore:
    """Read-only access to the prep.py cache. Feature files are memory-mapped on first use."""

    def __init__(self, cache: str | Path):
        self.root = Path(cache)
        self.index = json.loads((self.root / "index.json").read_text(encoding="utf-8"))
        self.vocab: list[str] = self.index["vocab"]
        self.meta = {r["session"]: r for r in self.index["sessions"]}
        z = np.load(self.root / "norm_generic_train.npz", allow_pickle=False)
        self.mean, self.std = z["mean"].astype(np.float32), z["std"].astype(np.float32)
        self._feat: dict[str, np.ndarray] = {}
        self._lab: dict[str, dict[str, np.ndarray]] = {}

    def feat(self, s: str) -> np.ndarray:
        if s not in self._feat:
            self._feat[s] = np.load(self.root / "sessions" / f"{s}.feat.npy", mmap_mode="r", allow_pickle=False)
        return self._feat[s]

    def lab(self, s: str) -> dict[str, np.ndarray]:
        if s not in self._lab:
            with np.load(self.root / "sessions" / f"{s}.lab.npz", allow_pickle=False) as z:
                self._lab[s] = {k: z[k] for k in ("key_frame", "key_tok", "prompt_lo", "prompt_hi")}
        return self._lab[s]

    def n_frames(self, s: str) -> int:
        return int(self.meta[s]["n_frames"])


class WindowSampler:
    """Deterministic batches: batch k depends only on (seed, k). This makes resume exact."""

    def __init__(self, store: SessionStore, sessions: Sequence[str], window: int, batch: int, jitter: int, seed: int):
        self.store, self.window, self.batch, self.jitter, self.seed = store, window, batch, jitter, seed
        self.sessions = [s for s in sessions if store.n_frames(s) >= window + 2 * jitter + 1]
        if not self.sessions:
            raise ValueError("no session is long enough for one window")
        w = np.array([store.n_frames(s) - window - 2 * jitter for s in self.sessions], np.float64)
        self.p = w / w.sum()

    def batch_at(self, k: int) -> dict[str, np.ndarray]:
        rng = np.random.default_rng([self.seed, k])
        W, J = self.window, self.jitter
        si = rng.choice(len(self.sessions), size=self.batch, p=self.p)
        x = np.empty((self.batch, W, N_CH, N_BANDS), np.float16)
        targets, tlen = [], []
        for b, i in enumerate(si):
            s = self.sessions[i]
            n = self.store.n_frames(s)
            o = int(rng.integers(J, n - W - J + 1))
            j = int(rng.integers(-J, J + 1)) if J else 0
            f = self.store.feat(s)
            x[b, :, :N_EL] = f[o:o + W, :N_EL]
            x[b, :, N_EL:] = f[o + j:o + j + W, N_EL:]
            lab = self.store.lab(s)
            lo, hi = np.searchsorted(lab["key_frame"], [o, o + W])
            t = lab["key_tok"][lo:hi].astype(np.int64)
            targets.append(t)
            tlen.append(len(t))
        return {"x": x, "targets": np.concatenate(targets) if targets else np.zeros(0, np.int64),
                "target_lengths": np.array(tlen, np.int64), "step": np.int64(k)}


class Prefetcher:
    """Prepare the next batches in threads (memmap reads release the GIL)."""

    def __init__(self, sampler: WindowSampler, start: int, depth: int = 4, threads: int = 4):
        self.sampler, self.next, self.depth = sampler, start, depth
        self.pool = ThreadPoolExecutor(threads)
        self.q: dict[int, object] = {}
        for k in range(start, start + depth):
            self.q[k] = self.pool.submit(sampler.batch_at, k)

    def get(self, k: int) -> dict[str, np.ndarray]:
        fut = self.q.pop(k, None) or self.pool.submit(self.sampler.batch_at, k)
        nxt = k + self.depth
        if nxt not in self.q:
            self.q[nxt] = self.pool.submit(self.sampler.batch_at, nxt)
        return fut.result()

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)


# --- model ----------------------------------------------------------------------------------------


class RingEncoder(nn.Module):
    """One wristband: circular conv over the electrode ring, then a linear projection."""

    def __init__(self, c: int, k: int, d_out: int, impl: str = "torch"):
        super().__init__()
        self.k, self.impl = k, impl
        self.conv = nn.Conv1d(N_BANDS, c, k, padding=k // 2, padding_mode="circular")
        self.proj = nn.Linear(N_EL * c, d_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, 16, 12)
        B, T, E, Fq = x.shape
        h = x.reshape(B * T, E, Fq).transpose(1, 2)  # (BT, 12, E)
        if self.impl == "shift":
            p = self.k // 2
            hp = torch.cat([h[..., E - p:], h, h[..., :p]], dim=-1)  # circular padding
            xs = torch.stack([hp[..., i:i + E] for i in range(self.k)], dim=-1)  # (BT, 12, E, k)
            h = torch.einsum("bfek,cfk->bce", xs, self.conv.weight) + self.conv.bias[None, :, None]
        else:
            h = self.conv(h)
        return self.proj(F.gelu(h).reshape(B, T, -1))


class CausalBlock(nn.Module):
    def __init__(self, d: int, k: int, dil: int, ff_mult: int, dropout: float, impl: str = "torch"):
        super().__init__()
        self.k, self.dil, self.impl = k, dil, impl
        self.pad = (k - 1) * dil
        self.norm = nn.LayerNorm(d)
        self.dw = nn.Conv1d(d, d, k, dilation=dil, groups=d)
        self.ff = nn.Sequential(nn.Linear(d, ff_mult * d), nn.GELU(), nn.Dropout(dropout), nn.Linear(ff_mult * d, d))
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, d)
        h = self.norm(x).transpose(1, 2)
        hp = F.pad(h, (self.pad, 0))
        if self.impl == "shift":
            T = h.shape[-1]
            w = self.dw.weight[:, 0, :]  # (d, k)
            h = self.dw.bias[None, :, None] + sum(w[None, :, i:i + 1] * hp[:, :, i * self.dil:i * self.dil + T]
                                                  for i in range(self.k))
        else:
            h = self.dw(hp)
        h = h.transpose(1, 2)
        return x + self.drop(self.ff(F.gelu(h)))


class CRT(nn.Module):
    def __init__(self, cfg: ModelCfg, mean: np.ndarray, std: np.ndarray):
        super().__init__()
        self.cfg = cfg
        self.register_buffer("mean", torch.as_tensor(mean, dtype=torch.float32).reshape(1, 1, N_CH, N_BANDS))
        self.register_buffer("std", torch.as_tensor(std, dtype=torch.float32).reshape(1, 1, N_CH, N_BANDS))
        self.left = RingEncoder(cfg.ring_c, cfg.ring_k, cfg.d // 2, cfg.conv_impl)
        self.right = RingEncoder(cfg.ring_c, cfg.ring_k, cfg.d // 2, cfg.conv_impl)
        self.blocks = nn.ModuleList(CausalBlock(cfg.d, cfg.kernel, dl, cfg.ff_mult, cfg.dropout, cfg.conv_impl)
                                    for dl in cfg.dilations)
        self.out_norm = nn.LayerNorm(cfg.d)
        self.head = nn.Linear(cfg.d, cfg.vocab)

    def normalise(self, x: torch.Tensor) -> torch.Tensor:
        return (x.float() - self.mean) / self.std

    def forward(self, x: torch.Tensor, normalised: bool = False) -> torch.Tensor:
        """(B, T, 32, 12) -> (B, T, V) log-probs (float32)."""
        if not normalised:
            x = self.normalise(x)
        h = torch.cat([self.left(x[:, :, :N_EL]), self.right(x[:, :, N_EL:])], dim=-1)
        for b in self.blocks:
            h = b(h)
        return F.log_softmax(self.head(self.out_norm(h)).float(), dim=-1)


def augment(x: torch.Tensor, aug: AugCfg, gen: torch.Generator) -> torch.Tensor:
    """Train-time augmentation on normalised input (B, T, 32, 12). Deterministic given ``gen``."""
    B, T = x.shape[:2]
    dev = x.device
    if aug.rotate:
        el = torch.arange(N_EL, device=dev)
        parts = []
        for band in (x[:, :, :N_EL], x[:, :, N_EL:]):
            sh = torch.randint(-1, 2, (B,), generator=gen, device="cpu").to(dev)
            idx = (el.unsqueeze(0) - sh.unsqueeze(1)) % N_EL  # (B, 16)
            idx = idx[:, None, :, None].expand(B, T, N_EL, N_BANDS)
            parts.append(torch.gather(band, 2, idx))
        x = torch.cat(parts, dim=2)
    if aug.gain_sd > 0:
        x = x + aug.gain_sd * torch.randn((B, 1, N_CH, 1), generator=gen, device="cpu").to(dev)
    if aug.time_masks or aug.band_masks:
        m = torch.ones((B, T, 1, N_BANDS), device="cpu")
        for b in range(B):
            for _ in range(aug.time_masks):
                w = int(torch.randint(0, aug.time_mask_max + 1, (1,), generator=gen))
                s = int(torch.randint(0, max(T - w, 1), (1,), generator=gen))
                m[b, s:s + w] = 0
            for _ in range(aug.band_masks):
                w = int(torch.randint(0, aug.band_mask_max + 1, (1,), generator=gen))
                s = int(torch.randint(0, N_BANDS - w + 1, (1,), generator=gen))
                m[b, :, :, s:s + w] = 0
        x = x * m.to(dev)
    return x


# --- decoding and metric ------------------------------------------------------------------------


@torch.no_grad()
def session_log_probs(model: CRT, feat: np.ndarray, device: str, chunk: int = 20_000) -> np.ndarray:
    """Causal log-probs for a whole session, computed in chunks with left context = receptive field.

    The result equals one pass over the full session (the model is causal), but memory stays bounded.
    """
    model.eval()
    rf = model.cfg.receptive_field()
    n = len(feat)
    out = np.empty((n, model.cfg.vocab), np.float32)
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        c = max(0, a - rf)
        x = torch.from_numpy(np.asarray(feat[c:b], np.float32)).unsqueeze(0).to(device)
        lp = model(x)[0, a - c:].float().cpu().numpy()
        out[a:b] = lp
    return out


def greedy(lp: np.ndarray) -> np.ndarray:
    """CTC best path: argmax per frame, collapse repeats, drop blanks."""
    if len(lp) == 0:
        return np.zeros(0, np.int64)
    a = lp.argmax(axis=1)
    keep = np.ones(len(a), bool)
    keep[1:] = a[1:] != a[:-1]
    a = a[keep]
    return a[a != BLANK]


def levenshtein(ref: Sequence[int], hyp: Sequence[int]) -> int:
    """Edit distance (unit costs). Row-wise numpy DP: O(len(ref)) numpy steps of size len(hyp)."""
    r, h = np.asarray(ref), np.asarray(hyp)
    if len(r) == 0:
        return int(len(h))
    if len(h) == 0:
        return int(len(r))
    ar = np.arange(len(h) + 1)
    prev = ar.copy()
    for i in range(1, len(r) + 1):
        tmp = np.empty_like(prev)
        tmp[0] = i
        tmp[1:] = np.minimum(prev[1:] + 1, prev[:-1] + (h != r[i - 1]))
        prev = np.minimum.accumulate(tmp - ar) + ar  # insertions along the row
    return int(prev[-1])


def session_errors(lp: np.ndarray, lab: dict[str, np.ndarray]) -> dict[str, int]:
    """Edits / reference length for the whole session and summed over text prompts."""
    ref = lab["key_tok"].astype(np.int64)
    hyp = greedy(lp)
    e_sess = levenshtein(ref, hyp)
    e_p = n_p = 0
    for lo, hi in zip(lab["prompt_lo"], lab["prompt_hi"]):
        a, b = np.searchsorted(lab["key_frame"], [lo, hi])
        r = ref[a:b]
        if len(r) == 0:
            continue
        e_p += levenshtein(r, greedy(lp[lo:hi]))
        n_p += len(r)
    return {"edits": e_sess, "ref": int(len(ref)), "hyp": int(len(hyp)), "prompt_edits": e_p, "prompt_ref": n_p}


def cer(errs: Sequence[dict[str, int]], key: str = "") -> float:
    e = sum(x[f"{key}edits"] for x in errs)
    n = sum(x[f"{key}ref" if key else "ref"] for x in errs)
    return e / max(n, 1)


# --- NTS export -------------------------------------------------------------------------------------


def nts_vocab(vocab: Sequence[str]) -> list[str]:
    """Stream vocabulary: ``<blank>`` at 0, characters as they are, Backspace / Enter as ⌫ / ⏎."""
    return list(vocab)


def prompt_streams(lp: np.ndarray, lab: dict[str, np.ndarray], vocab: Sequence[str], weights_sha256: str | None,
                   version: str, id_tag: str) -> Iterator:
    """One NTS stream per text prompt from session log-probs (causal, no lookahead)."""
    from fidetype.adapters.ctc_logits import DecoderInfo, from_array, vocab_from_list

    v = vocab_from_list(nts_vocab(vocab), blank=0, vocab_type="char", vocab_id="fidetype-p11-01-keys-v1")
    dec = DecoderInfo(modality="emg", name="fidetype-p11-01-crt", version=version, causal=True,
                      weights_sha256=weights_sha256,
                      extra={"fidetype.replay": "emg2qwerty", "fidetype.research_only": True,
                             "fidetype.licence_data": "CC-BY-NC-SA-4.0"})
    for i, (lo, hi) in enumerate(zip(lab["prompt_lo"], lab["prompt_hi"])):
        if hi - lo < 2:
            continue
        t0 = (int(lo) * 20 + 64) / 2000.0
        yield i, from_array(lp[lo:hi], v, dec, frame_period=FRAME_S, t0=t0, latency=0.0, input_kind="log_probs",
                            id_parts=(id_tag, str(i)))
