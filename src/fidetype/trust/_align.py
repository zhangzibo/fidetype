"""Levenshtein alignment with a backtrace (internal helper)."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence


def align(ref: Sequence, hyp: Sequence) -> list[tuple[int | None, int | None]]:
    """Return a minimum-cost alignment of ``ref`` and ``hyp``.

    Each pair is ``(i, j)``: a match or substitution of ``ref[i]`` and
    ``hyp[j]``, a deletion ``(i, None)`` or an insertion ``(None, j)``.
    Ties prefer a match/substitution, then a deletion.
    """
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        ri = ref[i - 1]
        row, prev = d[i], d[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prev[j - 1] + (ri != hyp[j - 1]), prev[j] + 1, row[j - 1] + 1)
    out: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            out.append((i - 1, None))
            i -= 1
        else:
            out.append((None, j - 1))
            j -= 1
    out.reverse()
    return out


def hyp_correct_mask(ref: str, hyp: str) -> list[bool]:
    """Return one flag per character of ``hyp``: True if the alignment
    matches it to an equal character of ``ref``."""
    mask = [False] * len(hyp)
    for i, j in align(ref, hyp):
        if i is not None and j is not None and ref[i] == hyp[j]:
            mask[j] = True
    return mask


def map_positions(ref: Sequence, hyp: Sequence) -> list:
    """For each element of ``ref``, return the aligned element of ``hyp``
    (or ``None`` if it is deleted). Insertions in ``hyp`` are dropped."""
    out: list = [None] * len(ref)
    for i, j in align(ref, hyp):
        if i is not None and j is not None:
            out[i] = hyp[j]
    return out


@lru_cache(maxsize=200_000)
def cached_edit_distance(a: str | tuple, b: str | tuple) -> int:
    """Levenshtein distance with a cache (strings or tuples of words)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]
