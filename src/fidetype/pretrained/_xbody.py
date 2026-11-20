"""NumPy inference of the P15-08 "XBody" Willett handwriting decoder. Our own code (Apache-2.0).

Same maths as ``experiments/2026-11-19-p15-08-e1-cross-body/e1.py`` (``XBody`` with the ``willett``
stem) in eval mode:

    threshold crossings (T, 192), 10 ms bins
    -> per-session z-score with fixed statistics (``mean[s]``, ``std[s]``)
    -> Linear(192 -> d)                                   (the stem)
    -> the P11-01 causal trunk + head (:func:`fidetype.pretrained._crt.trunk_log_probs`)
    -> log-softmax over the 98 P11-01 key tokens (CTC blank 0)

Every layer is causal: the output at frame t uses frames <= t only. A sentence starts from zero
left padding (as in training and evaluation).
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from fidetype.pretrained._crt import VOCAB, receptive_field, trunk_keys, trunk_log_probs

__all__ = ["N_W", "BIN_S", "VOCAB", "required_keys", "xbody_log_probs", "willett_text"]

N_W = 192  # electrodes (two 96-channel arrays)
BIN_S = 0.01  # 10 ms bins = 100 frames/s


def required_keys(n_blocks: int) -> list[str]:
    return ["mean", "std", "stem.weight", "stem.bias", *trunk_keys(n_blocks)]


def willett_text(s: str) -> str:
    """Willett ``intendedText`` -> plain text: '>' = space, '~' = period, '#' (pause cue) dropped."""
    return s.replace(">", " ").replace("~", ".").replace("#", "")


def _forward(p: Mapping[str, np.ndarray], x: np.ndarray, s: int, *, kernel: int,
             dilations: Sequence[int]) -> np.ndarray:
    z = (np.asarray(x, np.float32) - p["mean"][s]) / p["std"][s]
    h = z @ p["stem.weight"].T + p["stem.bias"]
    return trunk_log_probs(p, h, kernel=kernel, dilations=dilations)


def xbody_log_probs(p: Mapping[str, np.ndarray], x: np.ndarray, session: int, *, kernel: int,
                    dilations: Sequence[int], chunk: int = 4000) -> np.ndarray:
    """Causal log-probs (T, V) of one sentence ``x`` (T, 192) of session index ``session``.

    Computed in chunks with left context = receptive field; equal to one pass over the whole input.
    """
    x = np.asarray(x, np.float32)
    if x.ndim != 2 or x.shape[1] != p["mean"].shape[1]:
        raise ValueError(f"input must be (T, {p['mean'].shape[1]}), got {x.shape}")
    if not 0 <= int(session) < p["mean"].shape[0]:
        raise ValueError(f"session index {session} out of range 0..{p['mean'].shape[0] - 1}")
    rf = receptive_field(kernel, dilations)
    n = len(x)
    out = np.empty((n, p["head.weight"].shape[0]), np.float32)
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        c = max(0, a - rf)
        out[a:b] = _forward(p, x[c:b], int(session), kernel=kernel, dilations=dilations)[a - c:]
    return out
