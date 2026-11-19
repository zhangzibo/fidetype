"""P15-08 E1 stage 1: cross-body pretraining -> few-minute adaptation on Willett handwriting.

Our own implementation (Apache-2.0). Shared parts (causal blocks, greedy CTC, edit distance) are
imported from the P11-01 module ``emgdec`` (also our own code). Nothing from third-party code.

Model ("XBody"): a modality stem -> the P11-01 causal trunk (8 residual blocks, d = 512) -> LayerNorm
-> the shared 98-token character head of P11-01 (the emg2qwerty key vocabulary, blank 0).
  stem "willett": per-session z-score (fixed stats) -> Linear(192 -> d)
  stem "text":    Linear(TEXT_DIM -> d)   (synthetic key renderings, text-only pretraining)
Every layer is causal: the output at frame t uses frames <= t only.

Willett data: ``Datasets/<session>/sentences.mat`` (CC0), read with scipy.io.loadmat (MATLAB 5: plain
arrays, no code), only the variables in :data:`W_VARS`. 192 electrodes, threshold crossings in 10 ms
bins = 100 frames/s (the same frame rate as the P11-01 EMG features).
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
P11 = HERE.parent / "2026-11-16-p11-01-emg-decoder"
sys.path.insert(0, str(P11))
import emgdec as ED  # noqa: E402

BLANK = 0
N_W = 192
TEXT_DIM = 64
#: The P11-01 vocabulary (index.json of its cache). Copied here so that tests need no cache.
VOCAB: list[str] = (["<blank>"] + [chr(c) for c in range(32, 127)] + ["⌫", "⏎"])
assert len(VOCAB) == 98 and VOCAB[1] == " " and VOCAB[97] == "⏎"
TOK = {c: i for i, c in enumerate(VOCAB)}
W_VARS = ("sentencePrompt", "intendedText", "numTimeBinsPerSentence", "sentenceCondition", "sentenceBlockNums",
          "excludedSentences", "neuralActivityTimeSeries", "blockNumsTimeSeries", "goCueOnsetTimeBin",
          "sentenceEndTimeBin")
TAIL = 100  # frames kept after sentence end (T5's decoder emitted about 1 s late; causal model needs them)
ARMS = ("R", "T", "E", "S")


# --- text targets ----------------------------------------------------------------------------------


def willett_text(s: str) -> str:
    """intendedText -> plain text: '>' = space, '~' = period, '#' (pause cue) dropped."""
    return s.replace(">", " ").replace("~", ".").replace("#", "")


def encode(text: str) -> np.ndarray:
    """Characters -> P11-01 key tokens. Raises on a character outside the vocabulary."""
    return np.array([TOK[c] for c in text], np.int64)


def decode(toks: Sequence[int]) -> str:
    return "".join(VOCAB[int(t)] for t in toks)


# --- splits (salted hash, nested budgets) ---------------------------------------------------------


def salted_rank(salt: str, *parts: object) -> str:
    return hashlib.sha256("|".join([salt, *map(str, parts)]).encode("utf-8")).hexdigest()


def make_splits(meta: list[dict], salt: str) -> dict:
    """Test = last block of each session. Val = one other block per session, by salted SHA-256
    (diagnostic only). Train pool = the rest. ``meta`` rows: session, block, trial, n_write, ok."""
    by_sess: dict[int, set[int]] = {}
    for r in meta:
        if r["ok"]:
            by_sess.setdefault(r["session"], set()).add(r["block"])
    test_b, val_b = {}, {}
    for s, blocks in by_sess.items():
        bl = sorted(blocks)
        test_b[s] = bl[-1]
        rest = bl[:-1]
        val_b[s] = min(rest, key=lambda b: salted_rank(salt, "val", s, b)) if rest else None
    out = {"test": [], "val": [], "pool": []}
    for i, r in enumerate(meta):
        if not r["ok"]:
            continue
        part = "test" if r["block"] == test_b[r["session"]] else ("val" if r["block"] == val_b[r["session"]] else "pool")
        out[part].append(i)
    out["test_blocks"] = {str(k): int(v) for k, v in test_b.items()}
    out["val_blocks"] = {str(k): (int(v) if v is not None else None) for k, v in val_b.items()}
    return out


def budget_subset(meta: list[dict], pool: Sequence[int], minutes: float | None, salt: str, seed: int) -> list[int]:
    """Pool sentences in salted-hash order (per seed); the shortest prefix with >= ``minutes`` of
    writing time. ``None`` = the whole pool. Budgets of one seed are nested."""
    order = sorted(pool, key=lambda i: salted_rank(salt, "budget", seed, meta[i]["session"], meta[i]["trial"]))
    if minutes is None:
        return order
    out, tot = [], 0.0
    for i in order:
        if tot >= minutes * 60 * 100:
            break
        out.append(i)
        tot += meta[i]["n_write"]
    return out


def minutes_of(meta: list[dict], idx: Sequence[int]) -> float:
    return sum(meta[i]["n_write"] for i in idx) / 100.0 / 60.0


def derangement(n: int, rng: np.random.Generator) -> np.ndarray:
    """A permutation with no fixed point (n >= 2)."""
    while True:
        p = rng.permutation(n)
        if n < 2 or not np.any(p == np.arange(n)):
            return p


# --- Willett cache ----------------------------------------------------------------------------------


def load_willett_session(path: Path) -> list[dict]:
    """One sessions.mat -> list of sentence dicts (neural uint8 (T, 192) incl. TAIL, target text)."""
    import scipy.io as sio

    m = sio.loadmat(str(path), variable_names=list(W_VARS))
    ts = m["neuralActivityTimeSeries"]
    bts = m["blockNumsTimeSeries"].ravel()
    go = m["goCueOnsetTimeBin"].ravel().astype(np.int64) - 1  # MATLAB 1-based -> 0-based
    nb = m["numTimeBinsPerSentence"].ravel().astype(np.int64)
    blk = m["sentenceBlockNums"].ravel().astype(np.int64)
    exc = m["excludedSentences"].ravel().astype(bool)
    txt = [str(p[0][0]) if p[0].size else "" for p in m["intendedText"]]
    cond = [str(p[0][0]) if p[0].size else "" for p in m["sentenceCondition"]]
    out = []
    for i in range(len(nb)):
        a, b = int(go[i]), int(go[i] + nb[i])
        c = b
        while c < min(len(ts), b + TAIL) and bts[c] == bts[a]:
            c += 1
        x = np.asarray(ts[a:c], np.float64)
        out.append({"trial": i, "block": int(blk[i]), "excluded": bool(exc[i]), "cond": cond[i],
                    "text": willett_text(txt[i]), "n_write": int(nb[i]),
                    "x": np.clip(x, 0, 255).astype(np.uint8)})
    return out


# --- configuration ----------------------------------------------------------------------------------


@dataclass
class TrunkCfg:
    d: int = 512
    kernel: int = 5
    dilations: tuple[int, ...] = (1, 2, 4, 8, 1, 2, 4, 8)
    ff_mult: int = 2
    dropout: float = 0.1
    vocab: int = 98
    conv_impl: str = "torch"

    def receptive_field(self) -> int:
        return 1 + sum((self.kernel - 1) * d for d in self.dilations)


@dataclass
class FTCfg:
    lr: float = 5e-4
    lr_min: float = 1e-6
    warmup: int = 100
    weight_decay: float = 0.01
    clip: float = 1.0
    max_frames: int = 24_000
    val_every: int = 100
    ckpt_minutes: float = 4.0
    noise_sd: float = 0.3
    offset_sd: float = 0.2
    time_masks: int = 2
    time_mask_max: int = 20
    steps: dict = field(default_factory=lambda: {"3": 500, "10": 800, "30": 1200, "100": 2000, "all": 3000})


@dataclass
class TextCfg:
    steps: int = 30_000
    window: int = 400
    batch: int = 64
    lr: float = 1e-3
    lr_min: float = 1e-6
    warmup: int = 2000
    weight_decay: float = 0.01
    clip: float = 1.0
    ckpt_minutes: float = 4.0
    p_drop: float = 0.25
    p_sub: float = 0.15
    noise_sd: float = 1.0
    bump_min: int = 8
    bump_max: int = 20
    delay_max: int = 10
    amp: float = 3.0


def lr_at(step: int, total: int, lr: float, lr_min: float, warmup: int) -> float:
    if step < warmup:
        return lr * (step + 1) / warmup
    p = min(1.0, (step - warmup) / max(1, total - warmup))
    return lr_min + 0.5 * (lr - lr_min) * (1 + math.cos(math.pi * p))


# --- model ---------------------------------------------------------------------------------------------


class XBody(nn.Module):
    """Stem -> P11-01 causal trunk -> shared character head. ``stem`` in {"willett", "text"}."""

    def __init__(self, cfg: TrunkCfg, stem: str, n_sessions: int = 1):
        super().__init__()
        self.cfg, self.stem_kind = cfg, stem
        d_in = N_W if stem == "willett" else TEXT_DIM
        self.register_buffer("mean", torch.zeros(n_sessions, d_in))
        self.register_buffer("std", torch.ones(n_sessions, d_in))
        self.stem = nn.Linear(d_in, cfg.d)
        self.blocks = nn.ModuleList(ED.CausalBlock(cfg.d, cfg.kernel, dl, cfg.ff_mult, cfg.dropout, cfg.conv_impl)
                                    for dl in cfg.dilations)
        self.out_norm = nn.LayerNorm(cfg.d)
        self.head = nn.Linear(cfg.d, cfg.vocab)

    def normalise(self, x: torch.Tensor, sess: torch.Tensor | None) -> torch.Tensor:
        if self.stem_kind != "willett":
            return x.float()
        s = torch.zeros(x.shape[0], dtype=torch.long, device=x.device) if sess is None else sess
        return (x.float() - self.mean[s][:, None]) / self.std[s][:, None]

    def forward(self, x: torch.Tensor, sess: torch.Tensor | None = None, normalised: bool = False) -> torch.Tensor:
        """(B, T, d_in) -> (B, T, V) log-probs."""
        if not normalised:
            x = self.normalise(x, sess)
        h = self.stem(x)
        for b in self.blocks:
            h = b(h)
        return F.log_softmax(self.head(self.out_norm(h)).float(), dim=-1)


TRUNK_PREFIXES = ("blocks.", "out_norm.", "head.")


def trunk_state(sd: dict) -> dict:
    """The shared part of a state dict (trunk + head), from an XBody or a P11-01 CRT."""
    return {k: v for k, v in sd.items() if k.startswith(TRUNK_PREFIXES)}


def load_trunk(model: XBody, sd: dict) -> int:
    """Copy trunk + head weights into ``model``; the stem stays as initialised. Returns #tensors."""
    ts = trunk_state(sd)
    own = model.state_dict()
    missing = [k for k in own if k.startswith(TRUNK_PREFIXES) and k not in ts]
    if missing:
        raise KeyError(f"trunk weights missing: {missing[:3]}")
    for k, v in ts.items():
        if own[k].shape != v.shape:
            raise ValueError(f"shape mismatch {k}: {tuple(own[k].shape)} vs {tuple(v.shape)}")
    model.load_state_dict({**own, **ts})
    return len(ts)


def shuffle_within_tensors(sd: dict, seed: int) -> dict:
    """Control S: permute the entries of every trunk / head tensor (seeded). Keeps each tensor's
    value distribution (scale, sign mix), destroys the learned function."""
    g = torch.Generator().manual_seed(seed)
    out = {}
    for k in sorted(sd):
        v = sd[k]
        if k.startswith(TRUNK_PREFIXES) and v.numel() > 1 and v.is_floating_point():
            flat = v.reshape(-1)
            out[k] = flat[torch.randperm(flat.numel(), generator=g)].reshape(v.shape).clone()
        else:
            out[k] = v
    return out


# --- augmentation and batches -------------------------------------------------------------------------


def augment_w(x: torch.Tensor, lengths: torch.Tensor, c: FTCfg, gen: torch.Generator) -> torch.Tensor:
    """Normalised Willett input (B, T, 192): per-channel offset, white noise, time masks."""
    B, T, C = x.shape
    dev = x.device
    if c.offset_sd > 0:
        x = x + c.offset_sd * torch.randn((B, 1, C), generator=gen).to(dev)
    if c.noise_sd > 0:
        x = x + c.noise_sd * torch.randn((B, T, C), generator=gen).to(dev)
    if c.time_masks:
        m = torch.ones((B, T, 1))
        for b in range(B):
            L = int(lengths[b])
            for _ in range(c.time_masks):
                w = int(torch.randint(0, c.time_mask_max + 1, (1,), generator=gen))
                s = int(torch.randint(0, max(L - w, 1), (1,), generator=gen))
                m[b, s:s + w] = 0
        x = x * m.to(dev)
    return x


def pack_batch(idx_pool: Sequence[int], lengths: dict[int, int], max_frames: int, rng: np.random.Generator) -> list[int]:
    """Random sentences until (n x max length) would pass ``max_frames``; at least one."""
    order = rng.permutation(len(idx_pool))
    out: list[int] = []
    mx = 0
    for j in order:
        i = idx_pool[int(j)]
        m2 = max(mx, lengths[i])
        if out and m2 * (len(out) + 1) > max_frames:
            break
        out.append(i)
        mx = m2
    return out


def collate(items: list[tuple[np.ndarray, np.ndarray, int]]) -> dict:
    """[(x (T, C) uint8/float, targets, session)] -> padded float32 batch (post-padding)."""
    T = max(len(x) for x, _, _ in items)
    C = items[0][0].shape[1]
    x = np.zeros((len(items), T, C), np.float32)
    for b, (xi, _, _) in enumerate(items):
        x[b, :len(xi)] = xi
    return {"x": x, "lengths": np.array([len(xi) for xi, _, _ in items], np.int64),
            "targets": np.concatenate([t for _, t, _ in items]).astype(np.int64),
            "target_lengths": np.array([len(t) for _, t, _ in items], np.int64),
            "sess": np.array([s for _, _, s in items], np.int64)}


def render_text(key_frame: np.ndarray, key_tok: np.ndarray, window: int, emb: np.ndarray, c: TextCfg,
                rng: np.random.Generator) -> np.ndarray:
    """Text-only input: each key becomes a Hann bump of its fixed random embedding near its frame;
    keys are dropped (p_drop) or replaced by a random key (p_sub); white noise everywhere."""
    x = c.noise_sd * rng.standard_normal((window, emb.shape[1])).astype(np.float32)
    V = emb.shape[0]
    for f, t in zip(key_frame, key_tok):
        u = rng.random()
        if u < c.p_drop:
            continue
        tok = int(rng.integers(1, V)) if u < c.p_drop + c.p_sub else int(t)
        L = int(rng.integers(c.bump_min, c.bump_max + 1))
        s = int(f) + int(rng.integers(0, c.delay_max + 1)) - L // 2
        w = np.hanning(L + 2)[1:-1].astype(np.float32)
        a, b = max(0, s), min(window, s + L)
        if a < b:
            x[a:b] += c.amp * w[a - s:b - s, None] * emb[tok][None, :]
    return x


def text_embeddings(seed: int = 0) -> np.ndarray:
    e = np.random.default_rng([seed, 8]).standard_normal((len(VOCAB), TEXT_DIM)).astype(np.float32)
    return e / np.linalg.norm(e, axis=1, keepdims=True)


# --- decoding and metric ---------------------------------------------------------------------------------


greedy = ED.greedy
levenshtein = ED.levenshtein


@torch.no_grad()
def sentence_log_probs(model: XBody, x: np.ndarray, sess: int, device: str) -> np.ndarray:
    model.eval()
    xt = torch.from_numpy(np.asarray(x, np.float32)).unsqueeze(0).to(device)
    return model(xt, torch.tensor([sess], device=device))[0].cpu().numpy()


def sentence_errors(lp: np.ndarray, ref: np.ndarray) -> tuple[int, int, str]:
    hyp = greedy(lp)
    return levenshtein(ref, hyp), int(len(ref)), decode(hyp)


def pooled_cer(edits: Sequence[int], refs: Sequence[int]) -> float:
    return float(sum(edits)) / max(1, int(sum(refs)))


def bootstrap_delta(e_a: np.ndarray, e_b: np.ndarray, ref: np.ndarray, n: int = 10_000, seed: int = 0) -> dict:
    """Paired bootstrap over sentences of CER(a) - CER(b) (ratio of sums). e_* = per-sentence edits
    (already averaged over seeds). Returns the point value and the 95 % percentile interval."""
    rng = np.random.default_rng(seed)
    k = len(ref)
    d0 = (e_a.sum() - e_b.sum()) / ref.sum()
    ii = rng.integers(0, k, size=(n, k))
    d = (e_a[ii].sum(1) - e_b[ii].sum(1)) / ref[ii].sum(1)
    return {"delta": float(d0), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)), "n": n}


def cfg_json(c) -> dict:
    return asdict(c)


def save_json(obj, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    tmp.replace(path)
