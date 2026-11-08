"""Noisy-decoder simulator.

The simulator makes fake decoder output in the NeuralTextStream format.
With it, we can build and test the trust layer before a real brain
decoder exists. It also returns the ground truth, so we can score
calibration exactly.

Facts that the model uses
-------------------------
Brain2Qwerty v1 (Levy et al. 2025) and v2 give these facts:

- The vocabulary has 28 classes: CTC blank, ``a``-``z`` and space.
- The decoder runs at about 25 frames/s (40 ms per frame).
- Participants type at about 152 characters/min (about 395 ms per
  character, v1).
- The greedy CTC character error rate (CER) of the MEG encoder is about
  0.17 for the best subject and 0.41 for the worst. The v2 mean is about
  0.25-0.28.
- Errors go mostly to physically near QWERTY keys. The confusion rate
  rises with keyboard distance (r = 0.73, v1).
- Rare letters (for example ``z``, ``k``, ``w``) decode worse. Frequent
  letters decode better.
- The space decodes robustly. It is about 19 % of the characters.

Deep networks are often over-confident (Guo et al. 2017). The
``confidence_temperature`` setting copies this effect, so calibration
methods can be tested against a known truth.

How the simulator works
-----------------------
1. It normalises the text and makes a keystroke timeline. The intervals
   between keys have log-normal jitter.
2. Each typed character can be deleted (no output peak). After each
   character, the decoder can insert a spurious peak.
3. Each remaining character gives a short peak of 1-3 frames. Blank
   frames fill the gaps. There is always at least one blank frame
   between two peaks, so repeated letters stay separate.
4. For each peak, the simulator draws a calibrated confidence ``c`` from
   a Beta distribution with mean ``p_correct(char)``. The peak is
   correct with probability ``c``. If it is not correct, the label is a
   different key, chosen with probability ``softmax(-distance / tau)``.
5. The reported distribution of the peak gives probability ``c`` to the
   label. Thus the reported confidence is exactly calibrated before
   step 6.
6. The simulator divides all log-probabilities by
   ``confidence_temperature`` and normalises them again. A value below 1
   makes the stream over-confident. A value above 1 makes it
   under-confident. The argmax does not change, so the greedy CER does
   not change.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import (
    BLANK_ID,
    LETTERS,
    SPACE_ID,
    VOCAB,
    VOCAB_SIZE,
    key_distance,
    normalize_text,
)

# English letter frequency in percent (Lewand 2000, common table).
LETTER_FREQ: dict[str, float] = {
    "a": 8.17, "b": 1.49, "c": 2.78, "d": 4.25, "e": 12.70, "f": 2.23,
    "g": 2.02, "h": 6.09, "i": 6.97, "j": 0.15, "k": 0.77, "l": 4.03,
    "m": 2.41, "n": 6.75, "o": 7.51, "p": 1.93, "q": 0.10, "r": 5.99,
    "s": 6.33, "t": 9.06, "u": 2.76, "v": 0.98, "w": 2.36, "x": 0.15,
    "y": 1.97, "z": 0.07,
}
#: Share of spaces in typed text (Brain2Qwerty v1: about 19 %).
SPACE_SHARE = 0.19

# Limits for the calibrated confidence of one peak.
_C_MIN = 0.05
_C_MAX = 0.999
# Part of the residual mass (1 - c) of a peak frame that goes to blank.
_PEAK_BLANK_SHARE = 0.1

PRESET_CER = {"best": 0.17, "median": 0.28, "worst": 0.41, "perfect": 0.0}


@dataclass(frozen=True)
class SimConfig:
    """Settings of :class:`NoisyDecoderSimulator`.

    Use :meth:`preset` for the standard levels. ``target_cer`` is the
    expected greedy CER. It includes substitutions, deletions and
    insertions.
    """

    #: Expected greedy CER (Brain2Qwerty v1/v2: 0.17 best .. 0.41 worst).
    target_cer: float = 0.28
    #: Typing speed (Brain2Qwerty v1: about 152 characters/min).
    chars_per_min: float = 152.0
    #: Sigma of the log-normal jitter of the key intervals.
    timing_jitter: float = 0.3
    #: Decoder frame rate (Brain2Qwerty: about 25 frames/s).
    frame_rate_hz: float = 25.0
    #: Minimum and maximum peak length, in frames.
    peak_frames: tuple[int, int] = (1, 3)
    #: Probability of a spurious peak after each character.
    insertion_rate: float = 0.01
    #: Probability that a character gives no peak.
    deletion_rate: float = 0.01
    #: Strength of the letter-frequency effect. 0 = no effect.
    frequency_gamma: float = 0.25
    #: Error rate of space relative to the base letter error rate.
    space_error_factor: float = 0.2
    #: Distance scale (key units) of the neighbour-key confusion.
    neighbour_tau: float = 1.0
    #: Beta concentration of the per-peak confidence. Higher = less spread.
    confidence_concentration: float = 6.0
    #: Distortion of reported probabilities. <1 over-confident, >1 under-confident.
    confidence_temperature: float = 1.0
    #: Upper limit of the error rate of one character.
    max_char_error: float = 0.9
    #: Silence before the first key and after the last key, in seconds.
    lead_in_s: float = 0.4
    tail_s: float = 0.4

    def __post_init__(self) -> None:
        if not 0.0 <= self.target_cer < 1.0:
            raise ValueError("target_cer must be in [0, 1)")
        if self.chars_per_min <= 0 or self.frame_rate_hz <= 0:
            raise ValueError("chars_per_min and frame_rate_hz must be positive")
        lo, hi = self.peak_frames
        if not 1 <= lo <= hi:
            raise ValueError("peak_frames must be (lo, hi) with 1 <= lo <= hi")
        if self.confidence_temperature <= 0:
            raise ValueError("confidence_temperature must be positive")
        if self.insertion_rate < 0 or self.deletion_rate < 0:
            raise ValueError("insertion_rate and deletion_rate must not be negative")
        if self.insertion_rate + self.deletion_rate > self.target_cer:
            raise ValueError("insertion_rate + deletion_rate must not exceed target_cer")

    @classmethod
    def preset(cls, name: str, **overrides: Any) -> "SimConfig":
        """Return a preset: ``best``, ``median``, ``worst`` or ``perfect``.

        ``best``, ``median`` and ``worst`` aim at a greedy CER of 0.17,
        0.28 and 0.41 (Brain2Qwerty v1/v2). ``perfect`` makes no errors.
        Keyword arguments replace preset fields.
        """
        if name not in PRESET_CER:
            raise ValueError(f"unknown preset {name!r}; use one of {sorted(PRESET_CER)}")
        fields: dict[str, Any] = {"target_cer": PRESET_CER[name]}
        if name == "perfect":
            fields.update(insertion_rate=0.0, deletion_rate=0.0)
        fields.update(overrides)
        return cls(**fields)


@dataclass
class SimResult:
    """Output of one simulation: the stream and its ground truth.

    The peak arrays have one entry per output peak, in time order.
    """

    stream: NeuralTextStream
    #: The normalised intended text.
    text: str
    #: The labels that the simulator drew. The greedy decode of ``stream``
    #: gives exactly this text.
    sampled_text: str
    #: Centre frame of each peak.
    peak_frames: np.ndarray
    #: Token id that each peak shows (the argmax label).
    peak_labels: np.ndarray
    #: Intended token id of each peak; -1 for an inserted peak.
    peak_targets: np.ndarray
    #: True if the peak label equals the intended token.
    peak_correct: np.ndarray
    #: Reported probability of the label at the centre frame
    #: (after ``confidence_temperature``).
    peak_confidence: np.ndarray
    #: The calibrated probability that the simulator used to draw
    #: ``peak_correct``.
    peak_true_prob: np.ndarray
    #: One entry per intended character: "correct", "substitution" or
    #: "deletion".
    char_outcomes: list[str] = field(default_factory=list)


def _letter_adjustments(gamma: float) -> dict[str, float]:
    """Return error multipliers per letter. Rare letters get more error.

    The frequency-weighted mean of the multipliers is 1.
    """
    freqs = np.array([LETTER_FREQ[c] for c in LETTERS])
    raw = (freqs / freqs.mean()) ** (-gamma)
    raw /= np.sum(freqs * raw) / np.sum(freqs)
    return dict(zip(LETTERS, raw))


def _char_error_rates(cfg: SimConfig) -> np.ndarray:
    """Return the substitution rate per token id (blank gets 0).

    The function solves for a base rate by bisection, so that the
    expected CER on English text equals ``cfg.target_cer``.
    """
    adj = _letter_adjustments(cfg.frequency_gamma)
    freqs = np.array([LETTER_FREQ[c] for c in LETTERS])
    freqs = freqs / freqs.sum()
    adj_arr = np.array([adj[c] for c in LETTERS])
    p_del, p_ins = cfg.deletion_rate, cfg.insertion_rate
    # The CER is about p_sub * (1 - p_del) + p_del + p_ins.
    sub_target = (cfg.target_cer - p_ins - p_del) / (1.0 - p_del)

    def rates(base: float) -> tuple[np.ndarray, float]:
        letters = np.minimum(cfg.max_char_error, base * adj_arr)
        space = min(cfg.max_char_error, base * cfg.space_error_factor)
        return letters, space

    def expected(base: float) -> float:
        letters, space = rates(base)
        return (1 - SPACE_SHARE) * float(freqs @ letters) + SPACE_SHARE * space

    out = np.zeros(VOCAB_SIZE)
    if sub_target <= 0.0:
        return out  # No substitutions.
    lo, hi = 0.0, 10.0
    if expected(hi) < sub_target:
        raise ValueError(f"target_cer {cfg.target_cer} is too high for max_char_error")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if expected(mid) < sub_target else (lo, mid)
    letters, space = rates(0.5 * (lo + hi))
    out[1:27] = letters
    out[SPACE_ID] = space
    return out


def _neighbour_probs(tau: float) -> np.ndarray:
    """Return a (V, V) matrix. Row i is the substitution distribution of
    token i: ``softmax(-distance / tau)`` over the letters, without i.

    Substitutions never give blank or space. Space decodes robustly, so
    the model does not turn a letter into a space.
    """
    keys = VOCAB
    m = np.zeros((VOCAB_SIZE, VOCAB_SIZE))
    for i in range(1, VOCAB_SIZE):
        for j in range(1, 27):
            if i != j:
                m[i, j] = math.exp(-key_distance(keys[i], keys[j]) / tau)
        m[i] /= m[i].sum()
    return m


def _residual_weights(tau: float) -> np.ndarray:
    """Return a (V, V) matrix. Row k is the spread of the residual mass
    (1 - c) of a peak with label k over the other tokens.

    Near keys get more mass, so the intended key of a wrong peak is often
    the second choice. A blank share is included.
    """
    m = np.zeros((VOCAB_SIZE, VOCAB_SIZE))
    for k in range(1, VOCAB_SIZE):
        for j in range(1, VOCAB_SIZE):
            if j != k:
                m[k, j] = math.exp(-key_distance(VOCAB[k], VOCAB[j]) / tau)
        m[k] *= (1.0 - _PEAK_BLANK_SHARE) / m[k].sum()
        m[k, BLANK_ID] = _PEAK_BLANK_SHARE
    return m


class NoisyDecoderSimulator:
    """Make fake CTC decoder streams with known ground truth.

    The simulator is deterministic. With the same ``seed`` and the same
    sequence of calls, it gives the same output. Give ``seed`` to
    :meth:`simulate` to make one call independent of earlier calls.
    """

    def __init__(self, config: SimConfig | None = None, seed: int = 0) -> None:
        self.config = config or SimConfig()
        self.seed = seed
        self._rng = np.random.default_rng(seed)
        cfg = self.config
        self.error_rates = _char_error_rates(cfg)
        self._sub = _neighbour_probs(cfg.neighbour_tau)
        self._resid = _residual_weights(cfg.neighbour_tau)
        self._dt = 1.0 / cfg.frame_rate_hz

    def p_correct(self, char: str) -> float:
        """Return the probability that a peak of ``char`` is correct."""
        return 1.0 - float(self.error_rates[VOCAB.index(char)])

    # --- helpers ----------------------------------------------------------

    def _draw_confidence(self, rng: np.random.Generator, p: float) -> float:
        k = self.config.confidence_concentration
        if p >= 1.0:
            return _C_MAX
        c = rng.beta(k * p, k * (1.0 - p))
        return float(np.clip(c, _C_MIN, _C_MAX))

    def _peak_dist(self, label: int, c: float) -> np.ndarray:
        """Return the centre-frame distribution of a peak. The label gets
        ``c``. No other token gets more than 0.95 * c."""
        r = (1.0 - c) * self._resid[label]
        u = np.full(VOCAB_SIZE, (1.0 - c) / (VOCAB_SIZE - 1))
        u[label] = 0.0
        lam = 1.0
        mixed = r
        # Flatten the residual until the label is the clear argmax.
        while mixed.max() > 0.95 * c and lam > 0:
            lam = max(0.0, lam - 0.1)
            mixed = lam * r + (1 - lam) * u
        p = mixed.copy()
        p[label] = c
        return p

    # --- main entry -------------------------------------------------------

    def simulate(self, text: str, seed: int | None = None) -> SimResult:
        """Simulate the decoder output for ``text``.

        ``text`` is normalised first (see
        :func:`fidetype.streams.vocab.normalize_text`).
        """
        cfg = self.config
        rng = np.random.default_rng(seed) if seed is not None else self._rng
        norm = normalize_text(text)
        ids = [VOCAB.index(c) for c in norm]
        n = len(ids)

        # 1. Keystroke timeline with log-normal jitter (mean interval kept).
        mean_iki = 60.0 / cfg.chars_per_min
        s = cfg.timing_jitter
        iki = mean_iki * np.exp(s * rng.standard_normal(n) - 0.5 * s * s)
        onsets = cfg.lead_in_s + np.concatenate([[0.0], np.cumsum(iki)])[:n]

        # 2-4. Events: (time, label, target, true_prob, correct).
        events: list[tuple[float, int, int, float, bool]] = []
        outcomes: list[str] = []
        for i, tid in enumerate(ids):
            err = self.error_rates[tid]
            # Space is robust: it is also deleted less often.
            p_del = cfg.deletion_rate * (cfg.space_error_factor if tid == SPACE_ID else 1.0)
            if rng.random() < p_del:
                outcomes.append("deletion")
            else:
                c = self._draw_confidence(rng, 1.0 - err)
                correct = bool(err == 0.0 or rng.random() < c)
                label = tid if correct else int(rng.choice(VOCAB_SIZE, p=self._sub[tid]))
                outcomes.append("correct" if correct else "substitution")
                events.append((onsets[i], label, tid, c, correct))
            if rng.random() < cfg.insertion_rate:
                # A spurious peak, often a near key (like a key bounce).
                label = int(rng.choice(VOCAB_SIZE, p=self._sub[tid]))
                c = self._draw_confidence(rng, 0.4)
                events.append((onsets[i] + 0.5 * iki[i], label, -1, c, False))

        # 5. Place the peaks on the frame grid. Keep one blank between peaks.
        lo, hi = cfg.peak_frames
        starts, lengths = [], []
        prev_end = -2
        for t, *_ in events:
            length = int(rng.integers(lo, hi + 1))
            start = max(int(round(t / self._dt)), prev_end + 2)
            starts.append(start)
            lengths.append(length)
            prev_end = start + length - 1
        last_t = (onsets[-1] if n else 0.0) + cfg.tail_s
        T = max(int(math.ceil(max(last_t, cfg.lead_in_s) / self._dt)), prev_end + 3)

        # Background: blank frames with a small spread of mass.
        probs = np.empty((T, VOCAB_SIZE))
        eps = rng.uniform(0.005, 0.08, size=T)
        probs[:] = (eps / (VOCAB_SIZE - 1))[:, None]
        probs[:, BLANK_ID] = 1.0 - eps

        centres = []
        for (t, label, target, c, correct), start, length in zip(events, starts, lengths):
            p = self._peak_dist(label, c)
            centre = start + length // 2
            centres.append(centre)
            for f in range(start, start + length):
                if f == centre:
                    probs[f] = p
                else:
                    # Shoulder frame: mix in blank, but keep the label on top.
                    b_max = max(0.0, (0.9 * c - p[BLANK_ID]) / (1.0 + 0.9 * c - p[BLANK_ID]))
                    b = rng.uniform(0.0, b_max)
                    probs[f] = (1.0 - b) * p
                    probs[f, BLANK_ID] += b
            # Frames next to the peak: some label mass, blank stays on top.
            for f in (start - 1, start + length):
                # These frames are always blank frames (peaks keep a gap).
                if 0 <= f < T and probs[f].argmax() == BLANK_ID:
                    share = rng.uniform(0.05, 0.3)
                    probs[f] *= 1.0 - share
                    probs[f, label] += share

        # 6. Distort the confidence with the temperature, then normalise.
        logp = np.log(probs) / cfg.confidence_temperature
        top = logp.max(axis=1, keepdims=True)
        logp -= top + np.log(np.sum(np.exp(logp - top), axis=1, keepdims=True))

        stream = NeuralTextStream(
            log_probs=logp.astype(np.float32),
            frame_times=np.arange(T) * self._dt,
            vocab=list(VOCAB),
            blank_id=BLANK_ID,
            source="simulator",
            meta={
                "simulator": "NoisyDecoderSimulator",
                "config": asdict(cfg),
                "seed": self.seed if seed is None else seed,
            },
        )
        centres_arr = np.array(centres, dtype=np.int64)
        labels = np.array([e[1] for e in events], dtype=np.int64)
        conf = np.exp(stream.log_probs[centres_arr, labels].astype(np.float64)) if events else np.zeros(0)
        return SimResult(
            stream=stream,
            text=norm,
            sampled_text="".join(VOCAB[l] for l in labels),
            peak_frames=centres_arr,
            peak_labels=labels,
            peak_targets=np.array([e[2] for e in events], dtype=np.int64),
            peak_correct=np.array([e[4] for e in events], dtype=bool),
            peak_confidence=conf,
            peak_true_prob=np.array([e[3] for e in events], dtype=np.float64),
            char_outcomes=outcomes,
        )
