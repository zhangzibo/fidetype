"""Key-press streams as text: rendering and a small n-best decoder (P14-06).

A key-press stream (``vocab_type="key"``, ``blank_id=None``) has one
frame per key press. The CTC greedy rule merges runs of equal argmax
frames, so it would turn "ll" into "l". A key stream needs its own
decode: every frame is one key press.

:func:`render_keys` turns key codes into the text that appears on the
screen (``Backspace`` deletes the last character; ``Enter`` and keys
outside the vocabulary type nothing). :func:`key_nbest` is a
``decode_fn`` for :class:`~fidetype.trust.streaming.StreamingTrustLayer`:
a beam search over the per-frame key posteriors, with no language model.
It is a baseline decoder for the demo, not a result.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.types import Candidate, NBest

#: W3C ``KeyboardEvent.code`` -> the character it types. Backspace is handled by :func:`render_keys`.
KEY_CHAR: dict[str, str] = {
    **{f"Key{c}": c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    "Space": " ", "Period": ".", "Comma": ",", "Quote": "'",
}
BACKSPACE = "Backspace"


def render_keys(codes: Sequence[str | None], conf: Sequence[float] | None = None) -> tuple[str, tuple[float, ...]]:
    """The screen text of a key sequence, and one confidence per character that stays on the screen."""
    out: list[str] = []
    oc: list[float] = []
    for i, c in enumerate(codes):
        if c == BACKSPACE:
            if out:
                out.pop()
                oc.pop()
            continue
        ch = KEY_CHAR.get(c or "")
        if ch:
            out.append(ch)
            oc.append(float(conf[i]) if conf is not None else 1.0)
    return "".join(out), tuple(oc)


def normalize(text: str) -> str:
    """Lower case, single spaces, no edge spaces (for exact-match checks)."""
    return " ".join(text.lower().split())


def greedy_keys(stream: NeuralTextStream) -> str:
    """The screen text of the per-frame argmax keys."""
    if stream.n_frames == 0:
        return ""
    idx = np.argmax(stream.log_probs, axis=1)
    return render_keys([stream.vocab[i] for i in idx])[0]


def key_nbest(stream: NeuralTextStream, top_per_frame: int = 3, beam: int = 16, n_best: int = 8) -> NBest:
    """A beam search over the key posteriors (no LM). Candidates with the same screen text are merged."""
    lp = np.asarray(stream.log_probs, dtype=np.float64)
    vocab = list(stream.vocab)
    beams: list[tuple[float, tuple[int, ...]]] = [(0.0, ())]
    for row in lp:
        top = np.argsort(-row)[:top_per_frame]
        nxt = [(s + float(row[j]), seq + (int(j),)) for s, seq in beams for j in top]
        nxt.sort(key=lambda x: -x[0])
        beams = nxt[:beam]
    merged: dict[str, tuple[float, tuple[float, ...]]] = {}
    for s, seq in beams:
        conf = [math.exp(float(lp[t, j])) for t, j in enumerate(seq)]
        text, cc = render_keys([vocab[j] for j in seq], conf)
        text = normalize(text) if text.strip() else ""
        if len(cc) != len(text):  # normalisation removed spaces: keep a flat confidence list
            cc = tuple([float(np.mean(cc)) if cc else 1.0] * len(text))
        if text in merged:
            old, occ = merged[text]
            merged[text] = (float(np.logaddexp(old, s)), occ)
        else:
            merged[text] = (s, cc)
    cands = [Candidate(t, s, s, 0.0, cc) for t, (s, cc) in merged.items()]
    cands.sort(key=lambda c: -c.score)
    return NBest(cands[:n_best], {"decoder": "fidetype.demo.live.keys.key_nbest"})
