"""Toy raw-signal decoders for pipeline tests (M6-08). They do NOT decode text.

A :class:`~fidetype.adapters.lsl.SignalDecoder` turns raw signal samples
(EEG, EMG) into NTS frames. Fidetype ships no real EEG text decoder. These
toy decoders exist only to exercise the live path

    signal source -> LSL -> SignalDecoder -> streaming trust layer -> decisions

with a stream that carries **no text information**. The correct trust
layer output on such a stream is: never COMMIT.

Two modes:

``flat``
    Each frame is a near-uniform posterior over the 28-token character
    vocab (``log_softmax(log(1/V) + jitter * N(0, 1))``, seeded RNG). The
    frame does not depend on the signal at all. This is the same null
    input as :func:`fidetype.trust.guard.uniform_stream` and the demo
    condition ``no-signal``.
``features``
    Each frame depends on the signal: the per-channel log variance of the
    frame window, z-scored with running statistics, times a fixed random
    matrix (seeded), gives the logits. The posterior changes with the
    signal, so the frames are not flat. The matrix is random and the
    signal (for example the BrainFlow Synthetic board: sine waves plus
    noise) has no link to any text. So the frames carry no text
    information. This is a harder null input than ``flat``: the frames
    look like a decoder output, with peaks.

The header marks the output as a toy (``decoder.toy = true``,
``decoder.text_information = "none"``, ``fidetype.synthetic = true``).
numpy only. Our own code (Apache-2.0).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from fidetype.streams.vocab import BLANK_ID, VOCAB

__all__ = ["TOY_MODES", "ToySignalDecoder", "toy_signal_decoder"]

TOY_MODES = ("flat", "features")
#: Default frame rate of the toy decoders (the demo decoder and config use 25 Hz).
FRAME_RATE_HZ = 25.0
DECODER_NAME = "fidetype-toy-signal"
DECODER_VERSION = "0.1"


def _log_softmax(z: np.ndarray) -> np.ndarray:
    m = z.max(axis=-1, keepdims=True)
    return z - (m + np.log(np.exp(z - m).sum(axis=-1, keepdims=True)))


class ToySignalDecoder:
    """A toy :class:`~fidetype.adapters.lsl.SignalDecoder` (module docstring).

    ``srate``: the sample rate of the input (Hz). ``n_channels``: the
    number of input channels. One frame per ``window`` samples
    (``round(srate / frame_rate_hz)``); the frame time is the time of the
    last sample of its window.
    """

    def __init__(self, srate: float, n_channels: int, mode: str = "flat", frame_rate_hz: float = FRAME_RATE_HZ,
                 seed: int = 0, jitter: float = 0.05, gain: float = 1.0, ema: float = 0.02,
                 modality: str = "eeg") -> None:
        if mode not in TOY_MODES:
            raise ValueError(f"unknown toy mode {mode!r} (one of {TOY_MODES})")
        if srate <= 0:
            raise ValueError("the toy decoder needs a regular stream (nominal_srate > 0)")
        if n_channels < 1:
            raise ValueError("n_channels must be >= 1")
        self.mode = mode
        self.srate = float(srate)
        self.n_channels = int(n_channels)
        self.window = max(1, int(round(self.srate / frame_rate_hz)))
        self.jitter = float(jitter)
        self.gain = float(gain)
        self.ema = float(ema)
        self.rng = np.random.default_rng(seed)
        V = len(VOCAB)
        self.W = np.random.default_rng(seed + 1).standard_normal((self.n_channels, V)) / math.sqrt(self.n_channels)
        self._buf = np.zeros((0, self.n_channels))
        self._buf_t = np.zeros(0)
        self._mu: np.ndarray | None = None
        self._var: np.ndarray | None = None
        self._last_t = -math.inf
        self.frames = 0
        self.header: dict[str, Any] = {
            "vocab": list(VOCAB),
            "vocab_type": "char",
            "blank_id": BLANK_ID,
            "source": f"{DECODER_NAME}:{mode}",
            "frame_period": self.window / self.srate,
            "meta": {
                "device.modality": modality,
                "decoder.name": DECODER_NAME,
                "decoder.version": DECODER_VERSION,
                "decoder.mode": mode,
                "decoder.toy": True,
                "decoder.text_information": "none",
                "decoder.causal": True,
                "decoder.calibration_method": "none",
                "calibration.applied": False,
                "fidetype.synthetic": True,
                "data.derived": True,
            },
        }

    def reset(self) -> None:
        """Drop the buffered samples (the running statistics stay)."""
        self._buf = np.zeros((0, self.n_channels))
        self._buf_t = np.zeros(0)

    def _frame(self, win: np.ndarray) -> np.ndarray:
        V = len(VOCAB)
        if self.mode == "flat":
            z = np.full(V, -math.log(V)) + self.jitter * self.rng.standard_normal(V)
            return _log_softmax(z)
        f = np.log(np.var(win, axis=0) + 1e-12)
        if self._mu is None:
            self._mu, self._var = f.copy(), np.ones_like(f)
        else:
            a = self.ema
            d = f - self._mu
            self._mu = self._mu + a * d
            self._var = (1 - a) * self._var + a * d * d
        zf = (f - self._mu) / np.sqrt(self._var + 1e-6)
        return _log_softmax(self.gain * (zf @ self.W))

    def process(self, samples: np.ndarray, times: np.ndarray) -> list[tuple[float, np.ndarray]]:
        x = np.asarray(samples, dtype=np.float64)
        t = np.asarray(times, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != self.n_channels or len(t) != len(x):
            raise ValueError(f"expected samples [n, {self.n_channels}] and n times")
        self._buf = np.concatenate([self._buf, x])
        self._buf_t = np.concatenate([self._buf_t, t])
        out: list[tuple[float, np.ndarray]] = []
        w = self.window
        while len(self._buf) >= w:
            win, wt = self._buf[:w], self._buf_t[w - 1]
            self._buf, self._buf_t = self._buf[w:], self._buf_t[w:]
            if wt <= self._last_t:  # times must increase strictly over calls
                continue
            self._last_t = float(wt)
            out.append((float(wt), self._frame(win)))
            self.frames += 1
        return out


def toy_signal_decoder(mode: str, srate: float, n_channels: int, **kw: Any) -> ToySignalDecoder:
    """Build a toy decoder (``mode``: ``flat`` or ``features``)."""
    return ToySignalDecoder(srate, n_channels, mode=mode, **kw)
