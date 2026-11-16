"""Shared code of the P15-01 (F1 / E2) CPU pilot. Our own code (no third-party code copied).

CPU only: the environment variables below hide the GPU before torch is imported,
and no tensor is moved to a device. Data (read only): the M3-28 v2 per-session
feature files (B2T '24 / T12, CC0). Outputs with per-trial content go to
``C:/Users/zhang/bci-data/derived/f1-e2-pilot/`` only.
"""

from __future__ import annotations

import os

for _v in ("HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES"):
    os.environ[_v] = "-1"
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
V2 = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
V2CFG = json.loads((V2 / "config.json").read_text(encoding="utf-8"))
FEAT = Path(V2CFG["derived_dir"])  # read only
OWN = Path(CONFIG["derived_dir"])
assert OWN.name == "f1-e2-pilot"
OWN.mkdir(parents=True, exist_ok=True)
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
N_OUT = 41
C_IN = 512


def log(path: Path, *a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


def sessions() -> list[str]:
    return sorted(p.stem for p in FEAT.glob("t12.*.npz"))


_TEXTS: dict | None = None


def texts() -> dict:
    global _TEXTS
    if _TEXTS is None:
        _TEXTS = json.loads((FEAT / "texts.json").read_text(encoding="utf-8"))
    return _TEXTS


def load_day(si: int, parts=("train", "val", "pool")) -> list[dict]:
    """Items of session si in recording order: id, X (T, 512) float16, ph (int64 or None), text."""
    s = sessions()[si]
    z = np.load(FEAT / f"{s}.npz")
    tx = texts()[s]
    out = []
    for p in parts:
        known = z[f"{p}_known"]
        for i in range(int(z[f"{p}_n"])):
            ph = z[f"{p}_ph{i}"].astype(np.int64) if known[i] else None
            X = z[f"{p}_X{i}"]
            if ph is not None and (len(ph) == 0 or n_frames_np(X.shape[0]) < len(ph)):
                ph = None
            out.append({"id": f"{si}|{p}|{i}", "X": X, "ph": ph, "text": " ".join(tx[p][i].split())})
    return out


def n_frames_np(T: int) -> int:
    k, s = CONFIG["model"]["patch"], CONFIG["model"]["stride"]
    return max(0, (T - k) // s + 1)


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


def causal_kernel(sd: float) -> torch.Tensor:
    w = int(math.ceil(3 * sd))
    t = torch.arange(w + 1, dtype=torch.float32)
    k = torch.exp(-0.5 * (t / sd) ** 2)
    return (k / k.sum()).flip(0)


class Trunk(nn.Module):
    """Smoother -> [day layer given from outside] -> patch conv -> causal dilated conv blocks -> 41 logits."""

    def __init__(self, ch: int, patch: int, stride: int, dilations, dropout: float, smooth_sd: float) -> None:
        super().__init__()
        self.patch, self.stride = patch, stride
        self.register_buffer("kern", causal_kernel(smooth_sd))
        self.inp = nn.Conv1d(C_IN, ch, patch, stride=stride)
        self.dil = list(dilations)
        self.blocks = nn.ModuleList([nn.Conv1d(ch, ch, 3, dilation=d) for d in self.dil])
        self.mix = nn.ModuleList([nn.Conv1d(ch, ch, 1) for _ in self.dil])
        self.drop = nn.Dropout(dropout)
        self.out = nn.Conv1d(ch, N_OUT, 1)

    def n_frames(self, T: torch.Tensor) -> torch.Tensor:
        return torch.clamp((T - self.patch) // self.stride + 1, min=0)

    def forward(self, x: torch.Tensor, W: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """x (B, T, 512); W (512, 512), b (512,): one day layer for the whole batch. Returns logits (B, T', 41)."""
        x = x.transpose(1, 2)  # B, C, T
        k = self.kern.numel()
        x = F.conv1d(F.pad(x, (k - 1, 0)), self.kern.view(1, 1, -1).repeat(C_IN, 1, 1), groups=C_IN)
        x = F.softsign(F.conv1d(x, W.t().contiguous().unsqueeze(-1), b))  # y = W^T x + b per bin
        y = F.gelu(self.inp(x))
        for conv, mix, d in zip(self.blocks, self.mix, self.dil):
            h = F.gelu(conv(F.pad(y, (2 * d, 0))))
            y = y + self.drop(mix(h))
        return self.out(y).transpose(1, 2)


def make_trunk() -> Trunk:
    m = CONFIG["model"]
    return Trunk(m["channels"], m["patch"], m["stride"], m["dilations"], m["dropout"], m["smooth_sd_bins"])


def identity_layer() -> tuple[torch.Tensor, torch.Tensor]:
    return torch.eye(C_IN), torch.zeros(C_IN)


def collate(items, train: bool, noise: dict | None = None):
    T = max(it["X"].shape[0] for it in items)
    X = np.zeros((len(items), T, C_IN), np.float32)
    for i, it in enumerate(items):
        X[i, : it["X"].shape[0]] = it["X"]
    X = torch.from_numpy(X)
    if train and noise:
        X = X + noise["white_noise_sd"] * torch.randn_like(X) + noise["offset_sd"] * torch.randn(len(items), 1, C_IN)
    lens = torch.tensor([it["X"].shape[0] for it in items])
    return X, lens


def ctc_loss(trunk: Trunk, W, b, items, noise=None, train=True, label_key="ph") -> torch.Tensor:
    X, lens = collate(items, train, noise)
    lg = trunk(X, W, b)
    lp = lg.log_softmax(-1)
    fl = trunk.n_frames(lens)
    tg = torch.cat([torch.as_tensor(it[label_key]) for it in items])
    tl = torch.tensor([len(it[label_key]) for it in items])
    return F.ctc_loss(lp.transpose(0, 1), tg, fl, tl, blank=0, reduction="mean", zero_infinity=True)


@torch.no_grad()
def log_probs(trunk: Trunk, W, b, items, bs: int = 32) -> list[np.ndarray]:
    """(T', 41) float32 log-probs per item (input order)."""
    trunk.eval()
    order = sorted(range(len(items)), key=lambda j: items[j]["X"].shape[0])
    out: list = [None] * len(items)
    for i in range(0, len(order), bs):
        idx = order[i : i + bs]
        X, lens = collate([items[j] for j in idx], False)
        lp = trunk(X, W, b).log_softmax(-1).numpy()
        fl = trunk.n_frames(lens).numpy()
        for r, j in enumerate(idx):
            out[j] = np.ascontiguousarray(lp[r, : max(1, int(fl[r]))], dtype=np.float32)
    return out


def greedy(lp: np.ndarray) -> list[int]:
    a = lp.argmax(-1)
    out, prev = [], -1
    for t in a:
        if t != prev and t != 0:
            out.append(int(t))
        prev = t
    return out


def edit(a, b) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[-1]


def per_counts(lps, items) -> tuple[int, int]:
    ed = n = 0
    for lp, it in zip(lps, items):
        if it["ph"] is None:
            continue
        ed += edit(list(it["ph"]), greedy(lp))
        n += len(it["ph"])
    return ed, n


def fit_day_layer(trunk: Trunk, W0, b0, items, *, lr: float, l2: float, steps: int | None = None,
                  epochs: int | None = None, batch: int = 48, seed: int = 0, label_key: str = "lab"):
    """Adam on the day layer only (trunk frozen): CTC + l2 * ||(W, b) - (W0, b0)||^2. Returns (W, b)."""
    items = [it for it in items if it.get(label_key) is not None and len(it[label_key]) > 0
             and n_frames_np(it["X"].shape[0]) >= len(it[label_key])]
    W = W0.clone().requires_grad_(True)
    b = b0.clone().requires_grad_(True)
    if not items:
        return W0.clone(), b0.clone()
    trunk.eval()  # no dropout in the frozen trunk
    for p in trunk.parameters():
        p.requires_grad_(False)
    opt = torch.optim.Adam([W, b], lr=lr)
    rng = np.random.default_rng(seed)
    noise = CONFIG["train"]["noise"]
    if steps is None:
        steps = max(1, int(math.ceil(len(items) / batch)) * int(epochs or 1))
    order = []
    for _ in range(steps):
        if len(order) < min(batch, len(items)):
            order.extend(rng.permutation(len(items)).tolist())
        idx, order = order[: min(batch, len(items))], order[min(batch, len(items)):]
        loss = ctc_loss(trunk, W, b, [items[j] for j in idx], noise, True, label_key)
        reg = l2 * (((W - W0) ** 2).sum() + ((b - b0) ** 2).sum())
        opt.zero_grad()
        (loss + reg).backward()
        opt.step()
    return W.detach().clone(), b.detach().clone()


def load_base():
    ck = torch.load(OWN / "base" / "best.pt", map_location="cpu", weights_only=False)
    trunk = make_trunk()
    trunk.load_state_dict(ck["trunk"])
    trunk.eval()
    for p in trunk.parameters():
        p.requires_grad_(False)
    return trunk, ck


# ---------------------------------------------------------------------------
# word route (M3-28 v2, unchanged) and labels
# ---------------------------------------------------------------------------


class WordRoute:
    """(T', 41) log-probs -> word n-best [(text, score)] with the M3-28 v2 route. Text -> phoneme ids."""

    def __init__(self) -> None:
        from fidetype.adapters import b2t25 as B
        from fidetype.streams.spec import NeuralTextStream

        self.B, self.NTS = B, NeuralTextStream
        bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
        self.dec = bt.Decoders([], V2CFG["word_decoder_tuned"])
        sys.path.insert(0, str(V2))
        import wordlm  # noqa: E402

        beta = V2CFG["word_lm"]["beta"]
        cache = Path(V2CFG["word_lm"]["cache"])
        assert cache.exists(), "word LM cache missing (would be rebuilt)"
        wm = wordlm.load_or_build(bt.CONFIG["tatoeba_eng"], cache, B.normalize_words)
        char = self.dec.lm.score_sentence
        self.dec.wdec.sentence_lm = lambda t: char(t) + beta * wm.score_sentence(t)
        self.dec.wdec.clear_caches()
        self.dec._wcache.clear()
        t12 = load_module("t12v2", V2 / "t12.py")
        self.t12 = t12
        self.cmu = t12.load_cmudict(V2CFG["cmudict"])
        self._ph_cache: dict = {}

    def nbest(self, lp: np.ndarray) -> list[tuple[str, float]]:
        st = self.NTS(log_probs=np.ascontiguousarray(lp, dtype=np.float32), frame_times=np.arange(lp.shape[0]) * 0.08,
                      vocab=list(self.B.SYMBOL_VOCAB), blank_id=0, vocab_type="phoneme")
        self.dec._wcache = {}
        nb = self.dec.words_fn(st)
        out, seen = [], set()
        for c in nb.candidates:
            t = " ".join(c.text.split())
            if t in seen:
                continue
            seen.add(t)
            out.append((t, float(c.score)))
        return out

    def phonemes(self, text: str | None):
        """Phoneme ids (int64) of a word text, or None if a word is not in CMUdict."""
        if not text:
            return None
        hit = self._ph_cache.get(text)
        if hit is None:
            ph, ok = self.t12.phonemize(text, self.cmu)
            hit = np.array([self.t12.PH_ID[q] for q in ph], np.int64) if ok and ph else np.zeros(0, np.int64)
            self._ph_cache[text] = hit
        return hit if hit.size else None


def p_top1(scores: list[float], T: float) -> float:
    if not scores:
        return -math.inf
    s = np.asarray(scores, np.float64) / T
    s = s - s.max()
    p = np.exp(s)
    return float(p[0] / p.sum())


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def cp(k: int, n: int, level: float = 0.95) -> list:
    """Clopper-Pearson interval (scipy)."""
    from scipy.stats import beta

    if n == 0:
        return [0.0, 1.0]
    a = 1 - level
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]
