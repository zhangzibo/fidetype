"""B1 features (Ezzyat et al. 2018, Methods; our own code) and the epoch-level null transforms.

Per bipolar channel and word: 58-62 Hz Butterworth band-stop (order 4, zero phase) on the
continuous channel; Morlet wavelet power at 8 log-spaced frequencies 3-180 Hz, wave number 5;
log10 power, mean over the window. The wavelet is truncated at +-1 s (and +-5 sigma), so every
window value uses only signal inside the window +- 1000 ms buffer: computing on a longer segment
gives the same numbers as computing on the 3.366 s epoch (window + buffers).
"""

from __future__ import annotations

import math

import numpy as np
from scipy import fft as sfft
from scipy import signal

FREQS = np.logspace(math.log10(3.0), math.log10(180.0), 8)
N_CYCLES = 5.0
BUF_S = 1.0
WIN_S = 1.366          # encoding window 0 .. 1366 ms
P0_S = 1.0             # pre-stimulus window -1000 .. 0 ms
SEG_PRE_S = 2.0        # long segment: -2000 ms .. +2366 ms (covers both windows + buffers)
SEG_POST_S = WIN_S + BUF_S


def line_filter(x: np.ndarray, fs: float) -> np.ndarray:
    sos = signal.butter(4, [58.0, 62.0], btype="bandstop", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x, axis=-1)


def morlet_bank(fs: float, freqs: np.ndarray = FREQS, n_cycles: float = N_CYCLES) -> list[np.ndarray]:
    bank = []
    for f in freqs:
        sd = n_cycles / (2.0 * math.pi * f)
        half = min(BUF_S, 5.0 * sd)
        t = np.arange(-int(math.floor(half * fs)), int(math.floor(half * fs)) + 1) / fs
        w = np.exp(2j * math.pi * f * t) * np.exp(-(t ** 2) / (2.0 * sd ** 2))
        bank.append((w / np.sqrt(np.sum(np.abs(w) ** 2))).astype(np.complex64))
    return bank


def window_logpower(seg: np.ndarray, fs: float, windows: list[tuple[int, int]],
                    bank: list[np.ndarray] | None = None) -> list[np.ndarray]:
    """Mean log10 wavelet power in each window.

    ``seg``: (n_epochs, L) float. ``windows``: (start, length) in samples inside the segment.
    Returns one (n_epochs, n_freqs) array per window. Linear (not circular) convolution.
    """
    seg = np.asarray(seg, dtype=np.float32)
    if bank is None:
        bank = morlet_bank(fs)
    n, L = seg.shape
    m = max(len(w) for w in bank)
    nfft = sfft.next_fast_len(L + m - 1)
    X = sfft.fft(seg, n=nfft, axis=-1)
    outs = [np.empty((n, len(bank)), dtype=np.float64) for _ in windows]
    for j, w in enumerate(bank):
        h = (len(w) - 1) // 2
        Y = sfft.ifft(X * sfft.fft(w, n=nfft)[None, :], axis=-1)
        for o, (a, ln) in zip(outs, windows):
            p = np.abs(Y[:, a + h: a + h + ln]) ** 2
            o[:, j] = np.log10(np.maximum(p, 1e-30)).mean(axis=-1)
    return outs


def zscore_session(F: np.ndarray) -> np.ndarray:
    """z-score each feature over the words of the session (axis 0). SD = 0 -> nan (channel dropped later)."""
    mu = F.mean(axis=0, keepdims=True)
    sd = F.std(axis=0, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sd > 0, (F - mu) / sd, np.nan)


# ------------------------------------------------------------------------------------ null transforms


def time_reverse(ep: np.ndarray) -> np.ndarray:
    return ep[..., ::-1].copy()


def common_phases(n_epochs: int, L: int, seed: list[int]) -> np.ndarray:
    """Random phase offsets per epoch (shared by all channels); DC and Nyquist stay 0."""
    rng = np.random.default_rng(seed)
    nb = L // 2 + 1
    ph = rng.uniform(0.0, 2.0 * math.pi, size=(n_epochs, nb))
    ph[:, 0] = 0.0
    if L % 2 == 0:
        ph[:, -1] = 0.0
    return ph


def phase_randomise(ep: np.ndarray, phases: np.ndarray) -> np.ndarray:
    """N3a: add the per-epoch phase offsets to every frequency (keeps power spectrum and cross-spectra)."""
    L = ep.shape[-1]
    X = np.fft.rfft(ep, axis=-1)
    return np.fft.irfft(X * np.exp(1j * phases), n=L, axis=-1)


def common_gaussian(n_epochs: int, L: int, seed: list[int]) -> np.ndarray:
    """Complex Gaussian spectra with E|Z|^2 = 1, one per epoch, shared by all channels (N3b)."""
    rng = np.random.default_rng(seed)
    nb = L // 2 + 1
    Z = (rng.standard_normal((n_epochs, nb)) + 1j * rng.standard_normal((n_epochs, nb))) / math.sqrt(2.0)
    Z[:, 0] = Z[:, 0].real * math.sqrt(2.0)
    if L % 2 == 0:
        Z[:, -1] = Z[:, -1].real * math.sqrt(2.0)
    return Z


def mean_spectrum_noise(ep: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """N3b: Gaussian noise shaped to the channel's mean power spectrum over the session's epochs."""
    L = ep.shape[-1]
    S = np.mean(np.abs(np.fft.rfft(ep, axis=-1)) ** 2, axis=0)
    return np.fft.irfft(np.sqrt(S)[None, :] * Z, n=L, axis=-1)


# ------------------------------------------------------------------------------------ one channel


def channel_features(x: np.ndarray, fs: float, idx: np.ndarray, nulls: dict | None = None,
                     bank: list[np.ndarray] | None = None) -> dict[str, np.ndarray]:
    """Features of one continuous channel ``x`` (already in physical units) at word indices ``idx``.

    Returns ``main`` and ``p0`` (n_words, 8) raw log power (not yet z-scored). With ``nulls``
    (dict with ``phases`` and ``Z`` for this session), also ``n2``, ``n3a``, ``n3b`` computed on
    the 3.366 s epoch (-1000 .. +2366 ms) after the transform.
    """
    if bank is None:
        bank = morlet_bank(fs)
    xf = line_filter(np.asarray(x, dtype=np.float64), fs)
    pre, post = int(round(SEG_PRE_S * fs)), int(round(SEG_POST_S * fs))
    seg = np.stack([xf[i - pre:i + post] for i in idx])
    win = int(round(WIN_S * fs))
    b = int(round(BUF_S * fs))
    p0 = int(round(P0_S * fs))
    main, pre_w = window_logpower(seg, fs, [(pre, win), (pre - p0, p0)], bank)
    out = {"main": main, "p0": pre_w}
    if nulls is not None:
        ep = seg[:, pre - b: pre + win + b]
        wins = [(b, win)]
        out["n2"] = window_logpower(time_reverse(ep), fs, wins, bank)[0]
        out["n3a"] = window_logpower(phase_randomise(ep, nulls["phases"]), fs, wins, bank)[0]
        out["n3b"] = window_logpower(mean_spectrum_noise(ep, nulls["Z"]), fs, wins, bank)[0]
    return out


def valid_word_mask(idx: np.ndarray, fs: float, n_samples: int) -> np.ndarray:
    pre, post = int(round(SEG_PRE_S * fs)), int(round(SEG_POST_S * fs))
    idx = np.asarray(idx)
    return (idx - pre >= 0) & (idx + post <= n_samples)


def epoch_len(fs: float) -> int:
    return int(round(WIN_S * fs)) + 2 * int(round(BUF_S * fs))
