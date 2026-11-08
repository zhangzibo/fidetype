"""CTC peak helpers (internal)."""

from __future__ import annotations

import numpy as np

from fidetype.streams.spec import NeuralTextStream


def find_segments(stream: NeuralTextStream) -> list[tuple[int, int, int]]:
    """Return (start, end, centre) for each run of equal non-blank argmax frames.

    ``end`` is exclusive. ``centre`` is the frame with the highest
    non-blank probability in the run. The greedy CTC text is the argmax
    token of each centre, in order.
    """
    lp = stream.log_probs
    if lp.shape[0] == 0:
        return []
    am = np.argmax(lp, axis=1)
    nb = am != stream.blank_id
    nonblank = np.delete(lp, stream.blank_id, axis=1).max(axis=1)
    segs = []
    t, T = 0, len(am)
    while t < T:
        if nb[t]:
            s = t
            while t < T and nb[t] and am[t] == am[s]:
                t += 1
            segs.append((s, t, s + int(np.argmax(nonblank[s:t]))))
        else:
            t += 1
    return segs
