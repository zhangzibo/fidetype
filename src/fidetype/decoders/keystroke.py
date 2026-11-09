"""Synchronous keystroke decoder for MEG typing data (oracle key timing).

**Setting.** This is the *v1 synchronous* setting of Brain2Qwerty v1
(Levy et al. 2025): the times of the key presses come from the keyboard
log of the dataset ("oracle timing"). The decoder classifies one MEG
window per key press. It is **not** a real-time device setting: a real
device must find the key times from the brain signal itself, and here
each window also uses 0.3 s of signal after the key press.

Pipeline
--------
1. :func:`window_features`: for each key press, take the window
   -0.2 .. +0.3 s (all channels), and average it in ``n_bins`` time
   bins (default 10 bins of 50 ms at 100 Hz). One row per key press,
   ``n_channels * n_bins`` values.
2. :class:`LogRegDecoder`: per-subject multinomial logistic regression
   over 27 classes (``a``-``z`` and space), with an L2 penalty. The
   features are z-scored and rotated to their principal axes (an
   orthonormal rotation, so the L2 penalty is unchanged). The fit uses
   L-BFGS in numpy. :func:`fit_logreg_cv` picks the penalty by grouped
   cross-validation on the training trials.
3. :class:`SharedMLPDecoder` (optional, needs torch): one small MLP for
   all subjects, with a learned subject embedding.
4. :func:`keystroke_stream`: one NeuralTextStream per trial, in CTC
   form, so the CTC beam and the trust core work unchanged:

   - one *key frame* per key press. It holds the classifier
     log-probabilities, with a small blank mass ``key_blank``;
   - one *blank frame* between two key frames (blank probability
     ``1 - gap_nonblank``). It keeps repeated letters apart ("cc").

   ``frame_times`` are the key times in seconds; blank frames sit at
   the midpoints. The stream holds no ground-truth text. The number of
   frames does tell the number of key presses: that is a property of
   the oracle-timing setting.

Classes and vocabulary
----------------------
Class ``k`` (0..26) is ``KEY_CLASSES[k]``. In the stream vocabulary
:data:`fidetype.streams.vocab.VOCAB` it has id ``k + 1``; id 0 is the
blank. Keys that are not a letter or a space (return, backspace,
unknown keys) give no class and no frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID, LETTERS, VOCAB

KEY_CLASSES: str = LETTERS + " "
N_CLASSES = len(KEY_CLASSES)  # 27
_CLASS_OF = {c: i for i, c in enumerate(KEY_CLASSES)}

DECODER_NAME = "fidetype-keystroke-sync"
WINDOW_S = (-0.2, 0.3)
N_BINS = 10


def key_class(ch: str) -> int | None:
    """Return the class index of a key label, or None (return, backspace, ...)."""
    return _CLASS_OF.get(ch) if isinstance(ch, str) and len(ch) == 1 else None


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------


def window_features(
    data: np.ndarray,
    centres: Sequence[int],
    sfreq: float,
    window: tuple[float, float] = WINDOW_S,
    n_bins: int = N_BINS,
) -> np.ndarray:
    """Return time-binned windows around ``centres``, shape (n, C * n_bins), float32.

    ``data`` is (C, T). The window is ``window[0] .. window[1]`` seconds
    around each centre sample. Samples outside the data repeat the edge
    sample, so every key press gets a row.
    """
    c = np.asarray(centres, dtype=np.int64)
    i0 = int(round(window[0] * sfreq))
    n_samp = int(round((window[1] - window[0]) * sfreq))
    if n_samp < n_bins or n_samp % n_bins:
        raise ValueError(f"window of {n_samp} samples does not split into {n_bins} bins")
    C, T = data.shape
    if c.size == 0:
        return np.zeros((0, C * n_bins), dtype=np.float32)
    idx = np.clip(c[:, None] + i0 + np.arange(n_samp)[None, :], 0, T - 1)  # (n, S)
    w = data[:, idx].astype(np.float32)  # (C, n, S)
    w = w.reshape(C, len(c), n_bins, n_samp // n_bins).mean(axis=3)  # (C, n, B)
    return np.ascontiguousarray(w.transpose(1, 0, 2).reshape(len(c), C * n_bins))


@dataclass
class KeyTrial:
    """The key presses of one trial (one sentence) and their features.

    ``key_times`` are seconds from the segment start. ``labels`` are
    class indices of ``key_chars`` (what the subject typed). Only keys
    with a class are kept.
    """

    subject: str
    session: str
    block: str
    trial_idx: int
    split: str
    is_training: bool
    target_text: str
    typed_text: str
    key_chars: list[str]
    key_times: np.ndarray
    labels: np.ndarray
    features: np.ndarray

    @property
    def trial_id(self) -> str:
        return f"{self.subject}-{self.session}-{self.block}-t{self.trial_idx:03d}"

    @property
    def typed_keys(self) -> str:
        """The class keys in typed order (before any backspace correction)."""
        return "".join(self.key_chars)

    @property
    def n_keys(self) -> int:
        return int(len(self.labels))


def trials_from_segments(
    data: np.ndarray,
    sfreq: float,
    sidecar: dict[str, Any],
    window: tuple[float, float] = WINDOW_S,
    n_bins: int = N_BINS,
) -> list[KeyTrial]:
    """Cut the key-press features of every segment of one cached block."""
    from fidetype.streams.vocab import normalize_text

    out = []
    for seg in sidecar["segments"]:
        keep = [(s, ch) for s, ch in zip(seg["key_samples"], seg["key_chars"]) if key_class(ch) is not None]
        rel = np.array([s for s, _ in keep], dtype=np.int64)
        chars = [ch for _, ch in keep]
        feats = window_features(data, seg["start_sample"] + rel, sfreq, window, n_bins)
        out.append(
            KeyTrial(
                subject=str(sidecar["subject"]),
                session=str(sidecar["session"]),
                block=str(sidecar["block"]),
                trial_idx=int(seg["trial_idx"]),
                split=str(seg["split"]),
                is_training=bool(seg["is_training"]),
                target_text=normalize_text(seg["target_text"]),
                typed_text=normalize_text(seg.get("typed_text", "")),
                key_chars=chars,
                key_times=rel / float(sfreq),
                labels=np.array([key_class(ch) for ch in chars], dtype=np.int64),
                features=feats,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Multinomial logistic regression (numpy, L-BFGS)
# ---------------------------------------------------------------------------


def _log_softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    return z - np.log(np.exp(z).sum(axis=1, keepdims=True))


def _lbfgs(fg, x0: np.ndarray, max_iter: int = 300, m: int = 10, tol: float = 1e-6) -> np.ndarray:
    """Minimise a smooth convex function. ``fg(x) -> (f, grad)``."""
    x = x0.astype(np.float64).copy()
    f, g = fg(x)
    S: list[np.ndarray] = []
    Y: list[np.ndarray] = []
    for it in range(max_iter):
        gn = float(np.linalg.norm(g))
        if gn < tol:
            break
        q = g.copy()
        alphas = []
        for s, y in zip(reversed(S), reversed(Y)):
            a = float(s @ q) / float(y @ s)
            alphas.append(a)
            q -= a * y
        if S:
            q *= float(S[-1] @ Y[-1]) / float(Y[-1] @ Y[-1])
        else:
            q /= max(gn, 1e-12)
        for (s, y), a in zip(zip(S, Y), reversed(alphas)):
            b = float(y @ q) / float(y @ s)
            q += (a - b) * s
        d = -q
        gd = float(g @ d)
        if gd >= 0:  # not a descent direction: reset the memory
            S.clear()
            Y.clear()
            d = -g / max(gn, 1e-12)
            gd = float(g @ d)
        step = 1.0
        for _ in range(30):
            x_new = x + step * d
            f_new, g_new = fg(x_new)
            if f_new <= f + 1e-4 * step * gd:
                break
            step *= 0.5
        else:
            break
        s, y = x_new - x, g_new - g
        if float(s @ y) > 1e-12:
            S.append(s)
            Y.append(y)
            if len(S) > m:
                S.pop(0)
                Y.pop(0)
        rel = abs(f - f_new) / max(1.0, abs(f))
        x, f, g = x_new, f_new, g_new
        if rel < 1e-9:
            break
    return x


@dataclass
class LogRegDecoder:
    """Multinomial logistic regression with an L2 penalty.

    Loss: ``mean cross-entropy + lam / 2 * ||W||^2`` on z-scored,
    PCA-rotated features. The rotation keeps every component with a
    variance share above ``var_floor`` (MEG after tSSS has a low rank,
    so this removes only null directions).
    """

    lam: float = 1e-2
    n_classes: int = N_CLASSES
    max_iter: int = 300
    var_floor: float = 1e-6
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None
    rot: np.ndarray | None = None
    W: np.ndarray | None = None
    b: np.ndarray | None = None
    info: dict[str, Any] = field(default_factory=dict)

    def _prep_fit(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-6
        Z = (X - self.mu) / self.sd
        # Principal axes from the feature covariance.
        cov = (Z.T.astype(np.float64) @ Z.astype(np.float64)) / max(1, len(Z))
        ev, V = np.linalg.eigh(cov)
        keep = ev > self.var_floor * ev.sum()
        self.rot = np.ascontiguousarray(V[:, keep][:, ::-1]).astype(np.float32)
        self.info["n_components"] = int(keep.sum())
        return Z @ self.rot

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.rot is None:
            raise RuntimeError("decoder is not fitted")
        return ((np.asarray(X, dtype=np.float32) - self.mu) / self.sd) @ self.rot

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogRegDecoder":
        y = np.asarray(y, dtype=np.int64)
        Z = self._prep_fit(X)
        self._fit_rotated(Z, y)
        return self

    def _fit_rotated(self, Z: np.ndarray, y: np.ndarray, x0: np.ndarray | None = None) -> None:
        n, p = Z.shape
        K = self.n_classes
        lam = float(self.lam)
        Zf = np.ascontiguousarray(Z, dtype=np.float32)

        def fg(x):
            W = x[: p * K].reshape(p, K)
            b = x[p * K :]
            lp = _log_softmax((Zf @ W.astype(np.float32)).astype(np.float64) + b)
            f = -lp[np.arange(n), y].mean() + 0.5 * lam * float((W * W).sum())
            P = np.exp(lp)
            P[np.arange(n), y] -= 1.0
            P /= n
            gW = (Zf.T @ P.astype(np.float32)).astype(np.float64) + lam * W
            return f, np.concatenate([gW.ravel(), P.sum(axis=0)])

        x0 = np.zeros(p * K + K) if x0 is None else x0
        x = _lbfgs(fg, x0, max_iter=self.max_iter)
        self.W = x[: p * K].reshape(p, K).astype(np.float32)
        self.b = x[p * K :].astype(np.float32)

    def predict_log_proba(self, X: np.ndarray) -> np.ndarray:
        """Return natural-log class probabilities, shape (n, 27), float64."""
        Z = self.transform(X)
        return _log_softmax((Z @ self.W).astype(np.float64) + self.b)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_log_proba(X).argmax(axis=1)


def group_folds(groups: np.ndarray, n_folds: int, seed: int = 0) -> np.ndarray:
    """Assign each sample to a fold so that a group stays in one fold."""
    ug = np.random.default_rng(seed).permutation(np.unique(groups))
    fold_of = {g: i % n_folds for i, g in enumerate(ug)}
    return np.array([fold_of[g] for g in groups], dtype=np.int64)


def fit_logreg_cv(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    lams: Sequence[float] = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0),
    n_folds: int = 3,
    seed: int = 0,
    max_iter: int = 300,
) -> tuple[LogRegDecoder, dict[str, Any]]:
    """Pick ``lam`` by grouped cross-validated log-loss, then refit on all data.

    The z-score and the rotation are fitted inside each fold.
    """
    y = np.asarray(y, dtype=np.int64)
    folds = group_folds(np.asarray(groups), n_folds, seed)
    scores = {lam: [0.0, 0] for lam in lams}
    acc = {lam: 0 for lam in lams}
    for k in range(n_folds):
        tr, te = folds != k, folds == k
        if not te.any() or not tr.any():
            continue
        base = LogRegDecoder(lam=lams[0], max_iter=max_iter)
        Ztr = base._prep_fit(X[tr])
        Zte = base.transform(X[te])
        x0 = None
        for lam in sorted(lams, reverse=True):  # strong to weak, warm start
            d = LogRegDecoder(lam=lam, max_iter=max_iter)
            d._fit_rotated(Ztr, y[tr], x0)
            x0 = np.concatenate([d.W.astype(np.float64).ravel(), d.b.astype(np.float64)])
            lp = _log_softmax((Zte @ d.W).astype(np.float64) + d.b)
            scores[lam][0] += float(-lp[np.arange(te.sum()), y[te]].sum())
            scores[lam][1] += int(te.sum())
            acc[lam] += int((lp.argmax(1) == y[te]).sum())
    cv = {
        str(lam): {"logloss": s / max(n, 1), "acc": acc[lam] / max(n, 1)} for lam, (s, n) in scores.items()
    }
    best = min(lams, key=lambda lam: scores[lam][0] / max(scores[lam][1], 1))
    dec = LogRegDecoder(lam=best, max_iter=max_iter).fit(X, y)
    dec.info["cv"] = cv
    return dec, {"lam": best, "cv": cv}


# ---------------------------------------------------------------------------
# Optional shared MLP (torch)
# ---------------------------------------------------------------------------


class SharedMLPDecoder:
    """One MLP for all subjects, with a learned subject embedding.

    Input: the per-subject z-scored window features. Layer 1 is shared;
    the subject embedding is added to its output (a per-subject bias).
    Needs torch. Early stopping uses a held-out part of the *training*
    trials, not the validation split.
    """

    def __init__(
        self,
        n_features: int,
        subjects: Sequence[str],
        hidden: int = 256,
        dropout: float = 0.4,
        lr: float = 1e-3,
        weight_decay: float = 1e-2,
        epochs: int = 40,
        batch_size: int = 256,
        seed: int = 0,
        device: str | None = None,
    ) -> None:
        import torch

        self.torch = torch
        self.subjects = list(subjects)
        self.sid = {s: i for i, s in enumerate(self.subjects)}
        self.hp = dict(hidden=hidden, dropout=dropout, lr=lr, weight_decay=weight_decay, epochs=epochs,
                       batch_size=batch_size, seed=seed)
        self.device = device or "cpu"
        torch.manual_seed(seed)
        nn = torch.nn

        class Net(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.drop_in = nn.Dropout(0.2)
                self.l1 = nn.Linear(n_features, hidden)
                self.emb = nn.Embedding(len(subjects), hidden)
                nn.init.zeros_(self.emb.weight)
                self.body = nn.Sequential(nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, hidden), nn.GELU(),
                                          nn.Dropout(dropout), nn.Linear(hidden, N_CLASSES))

            def forward(self, x, s):
                return self.body(self.l1(self.drop_in(x)) + self.emb(s))

        self.net = Net().to(self.device)
        self.norm: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.history: list[dict[str, float]] = []

    def set_norm(self, subject: str, X: np.ndarray) -> None:
        X = np.asarray(X, dtype=np.float32)
        self.norm[subject] = (X.mean(0), X.std(0) + 1e-6)

    def _z(self, subject: str, X: np.ndarray) -> np.ndarray:
        mu, sd = self.norm[subject]
        return ((np.asarray(X, dtype=np.float32) - mu) / sd).astype(np.float32)

    def fit(self, data: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], holdout: float = 0.1) -> "SharedMLPDecoder":
        """``data[subject] = (X, y, groups)`` (training trials only)."""
        torch = self.torch
        rng = np.random.default_rng(self.hp["seed"])
        Xtr, ytr, str_, Xho, yho, sho = [], [], [], [], [], []
        for s, (X, y, g) in data.items():
            self.set_norm(s, X)
            Z = self._z(s, X)
            ug = rng.permutation(np.unique(g))
            ho = np.isin(g, ug[: max(1, int(round(len(ug) * holdout)))])
            for (dst_x, dst_y, dst_s), m in (((Xtr, ytr, str_), ~ho), ((Xho, yho, sho), ho)):
                dst_x.append(Z[m])
                dst_y.append(y[m])
                dst_s.append(np.full(int(m.sum()), self.sid[s]))
        T = lambda a, dt: torch.as_tensor(np.concatenate(a), dtype=dt, device=self.device)  # noqa: E731
        Xt, yt, st = T(Xtr, torch.float32), T(ytr, torch.long), T(str_, torch.long)
        Xh, yh, sh = T(Xho, torch.float32), T(yho, torch.long), T(sho, torch.long)
        opt = torch.optim.AdamW(self.net.parameters(), lr=self.hp["lr"], weight_decay=self.hp["weight_decay"])
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=self.hp["epochs"])
        best = (math.inf, None, -1)
        g = torch.Generator(device="cpu").manual_seed(self.hp["seed"])
        for ep in range(self.hp["epochs"]):
            self.net.train()
            perm = torch.randperm(len(yt), generator=g).to(self.device)
            tot = 0.0
            for i in range(0, len(perm), self.hp["batch_size"]):
                b = perm[i : i + self.hp["batch_size"]]
                loss = torch.nn.functional.cross_entropy(self.net(Xt[b], st[b]), yt[b], label_smoothing=0.05)
                opt.zero_grad()
                loss.backward()
                opt.step()
                tot += float(loss.detach()) * len(b)
            sched.step()
            self.net.eval()
            with torch.no_grad():
                lo = self.net(Xh, sh)
                hl = float(torch.nn.functional.cross_entropy(lo, yh))
                ha = float((lo.argmax(1) == yh).float().mean())
            self.history.append({"epoch": ep, "train_loss": tot / len(yt), "holdout_loss": hl, "holdout_acc": ha})
            if hl < best[0]:
                best = (hl, {k: v.detach().clone() for k, v in self.net.state_dict().items()}, ep)
        if best[1] is not None:
            self.net.load_state_dict(best[1])
        self.best_epoch = best[2]
        return self

    def predict_log_proba(self, subject: str, X: np.ndarray) -> np.ndarray:
        torch = self.torch
        if len(X) == 0:
            return np.zeros((0, N_CLASSES))
        self.net.eval()
        with torch.no_grad():
            x = torch.as_tensor(self._z(subject, X), device=self.device)
            s = torch.full((len(x),), self.sid[subject], dtype=torch.long, device=self.device)
            lp = torch.log_softmax(self.net(x, s).double(), dim=1)
        return lp.cpu().numpy()


# ---------------------------------------------------------------------------
# Stream construction
# ---------------------------------------------------------------------------


def strictly_increasing(times: np.ndarray, min_gap: float = 1e-3) -> np.ndarray:
    """Return a copy where each time is at least ``min_gap`` after the previous one."""
    t = np.asarray(times, dtype=np.float64).copy()
    for i in range(1, len(t)):
        if t[i] < t[i - 1] + min_gap:
            t[i] = t[i - 1] + min_gap
    return t


def stream_meta(subject: str, session: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the namespaced ``meta`` of a keystroke stream (no labels)."""
    meta = {
        "device.modality": "meg",
        "device.channel_count": 306,
        "decoder.name": DECODER_NAME,
        "decoder.causal": False,
        "decoder.timing": "oracle-keystroke",
        "decoder.window_s": list(WINDOW_S),
        "subject.id": str(subject),
        "session.id": f"{subject}-{session}",
        "language": "es",
        "lm.name": "none",
        "calibration.applied": False,
        "data.derived": True,
    }
    meta.update(extra or {})
    return meta


def keystroke_stream(
    key_log_probs: np.ndarray,
    key_times: np.ndarray,
    meta: dict[str, Any] | None = None,
    key_blank: float = 1e-3,
    gap_nonblank: float = 1e-4,
    source: str = DECODER_NAME,
) -> NeuralTextStream:
    """Build a CTC-form NeuralTextStream from per-key class log-probabilities.

    ``key_log_probs`` is (n, 27) over :data:`KEY_CLASSES`. The stream has
    ``2n - 1`` frames: key, blank, key, ..., key. A key frame gives the
    blank the mass ``key_blank`` and scales the classifier distribution
    by ``1 - key_blank``. A blank frame gives the 27 classes the total
    mass ``gap_nonblank`` (uniform) and the blank the rest.
    """
    lp = np.asarray(key_log_probs, dtype=np.float64)
    n = lp.shape[0] if lp.ndim == 2 else 0
    if lp.ndim != 2 or lp.shape[1] != N_CLASSES:
        raise ValueError(f"key_log_probs must have shape (n, {N_CLASSES}), got {lp.shape}")
    t = strictly_increasing(np.asarray(key_times, dtype=np.float64))
    if t.shape != (n,):
        raise ValueError("key_times must have one value per key")
    V = len(VOCAB)
    lp = lp - np.logaddexp.reduce(lp, axis=1, keepdims=True) if n else lp  # renormalise exactly
    key_rows = np.empty((n, V))
    key_rows[:, BLANK_ID] = math.log(key_blank)
    key_rows[:, 1:] = lp + math.log1p(-key_blank)
    gap = np.full(V, math.log(gap_nonblank / N_CLASSES))
    gap[BLANK_ID] = math.log1p(-gap_nonblank)
    T = max(0, 2 * n - 1)
    rows = np.empty((T, V))
    times = np.empty(T)
    rows[0::2] = key_rows
    times[0::2] = t
    if n > 1:
        rows[1::2] = gap
        times[1::2] = 0.5 * (t[:-1] + t[1:])
    return NeuralTextStream(
        log_probs=rows.astype(np.float32),
        frame_times=times,
        vocab=list(VOCAB),
        blank_id=BLANK_ID,
        source=source,
        meta=dict(meta or {}),
        vocab_type="char",
    )


def key_frame_indices(stream: NeuralTextStream) -> np.ndarray:
    """Return the frame indices of the key frames (even frames)."""
    return np.arange(0, stream.n_frames, 2)


def greedy_keys(stream: NeuralTextStream) -> str:
    """Return the argmax character of every key frame (no CTC collapse needed)."""
    idx = key_frame_indices(stream)
    if idx.size == 0:
        return ""
    best = stream.log_probs[idx][:, 1:].argmax(axis=1)
    return "".join(KEY_CLASSES[i] for i in best)
