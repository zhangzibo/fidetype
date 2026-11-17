"""A synthetic "typist" signal for ``fidetype live`` tests and demos (P14-04). No real data.

:class:`SyntheticTypist` makes a raw multi-channel signal (default 16
channels at 250 Hz, the shape of the BrainFlow Synthetic board) in which
each key press leaves a burst with a key-specific gain pattern over the
channels. A model trained on this signal (``builtin:synthetic-keys``) can
decode it. The signal is our own: it has no participant data and no
licence limit. It is a plumbing and trust test, not a result about EMG.

Each utterance: 1-3 words from :data:`WORDS`, typed at 0.17-0.30 s per key
(space between words), then a pause. Markers (strings, as on an LSL marker
stream): ``keypress`` at each key time (the onset only; never the key) and
``segment_end`` after the last key.

``noise`` (background level against the key bursts) sets how hard
decoding is. With the default (11), about 97 of 100 keys are right, so
some utterances decode exactly and some do not: the trust guard then has
real work.

Our own code (Apache-2.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Sequence

import numpy as np

from fidetype.adapters.kt_semg import KEY_VOCAB, key_class

__all__ = ["WORDS", "Utterance", "SyntheticTypist", "KEYPRESS", "SEGMENT_END"]

KEYPRESS = "keypress"
SEGMENT_END = "segment_end"

#: A small public-domain word list (common English words).
WORDS: tuple[str, ...] = tuple("""
the of and to in is you that it he was for on are as with his they at be this have from or one had by word but
not what all were we when your can said there use an each which she do how their if will up other about out many
then them these so some her would make like him into time has look two more write go see number no way could people
my than first water been call who oil its now find long down day did get come made may part over new sound take only
little work know place year live me back give most very after thing our just name good sentence man think say great
where help through much before line right too mean old any same tell boy follow came want show also around form three
small set put end does another well large must big even such because turn here why ask went men read need land
different home us move try kind hand picture again change off play spell air away animal house point page letter
mother answer found study still learn should world high every near add food between own below country plant last
school father keep tree never start city earth eye light thought head under story saw left few while along might
close something seem next hard open example begin life always those both paper together got group often run
""".split())


@dataclass
class Utterance:
    """One synthetic utterance: its text and key times (seconds, signal clock)."""

    text: str
    key_times: list[float]
    key_classes: list[int]
    t_end: float  # time of the segment_end marker


@dataclass
class SyntheticTypist:
    """Signal generator (module docstring). Deterministic for a given ``seed``."""

    sample_rate: float = 250.0
    channels: int = 16
    seed: int = 0
    noise: float = 11.0
    pattern_seed: int = 1234
    burst_pre_s: float = 0.12
    burst_post_s: float = 0.04
    words: Sequence[str] = WORDS
    max_words: int = 3
    pause_s: tuple[float, float] = (0.8, 1.4)
    _rng: np.random.Generator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        self._renders = 0
        pr = np.random.default_rng(self.pattern_seed)
        V = len(KEY_VOCAB)
        # key-specific log-gain per channel, two halves of the burst (so both sub-windows carry information)
        self.patterns = pr.normal(0.0, 0.9, size=(V, 2, self.channels))

    def utterances(self, n: int | None = None, t0: float = 0.5) -> Iterator[Utterance]:
        """Random utterances, back to back, starting at ``t0`` seconds."""
        rng = self._rng
        t = t0
        k = 0
        while n is None or k < n:
            nw = int(rng.integers(1, self.max_words + 1))
            text = " ".join(str(rng.choice(self.words)) for _ in range(nw))
            times, classes = [], []
            for ch in text:
                c = key_class(ch)
                if c is None:
                    continue
                t += float(rng.uniform(0.17, 0.30))
                times.append(t)
                classes.append(c)
            t_end = t + 0.5
            yield Utterance(text, times, classes, t_end)
            t = t_end + float(rng.uniform(*self.pause_s))
            k += 1

    def render(self, utts: Sequence[Utterance], t_stop: float | None = None, null: bool = False) -> np.ndarray:
        """The signal (N, C) float32 from time 0 to ``t_stop`` (default: last segment end + 0.5 s).

        ``null=True`` leaves out the key bursts (background only): a no-signal control with the same timing.
        """
        fs = self.sample_rate
        t_stop = t_stop if t_stop is not None else (utts[-1].t_end + 0.5 if utts else 1.0)
        n = int(round(t_stop * fs))
        # own generators for the signal: the noise of utterance k does not depend on how many utterances follow
        self._renders += 1
        rng = np.random.default_rng([self.seed, 1, self._renders])
        x = rng.normal(0.0, self.noise, size=(n, self.channels)).astype(np.float64)
        if not null:
            a, b = int(round(self.burst_pre_s * fs)), int(round(self.burst_post_s * fs))
            half = (a + b) // 2
            for ui, u in enumerate(utts):
                brng = np.random.default_rng([self.seed, 2, self._renders, ui])
                for tk, c in zip(u.key_times, u.key_classes):
                    i0 = int(round(tk * fs)) - a
                    for j, (lo, hi) in enumerate(((i0, i0 + half), (i0 + half, i0 + a + b))):
                        lo, hi = max(lo, 0), min(hi, n)
                        if hi <= lo:
                            continue
                        gain = np.exp(self.patterns[c, j]) * 3.0
                        x[lo:hi] += brng.normal(0.0, 1.0, size=(hi - lo, self.channels)) * gain
        x *= 10.0  # microvolt-like scale
        return x.astype(np.float32)
