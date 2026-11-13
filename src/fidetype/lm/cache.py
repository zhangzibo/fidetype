"""A small LRU memo for the decoders (M4-10).

The word decoder and the character LM keep memos of pure functions (the
lexicon candidates of a phoneme segment, the LM score of a sentence, the
LM row of a context). In a long live session these memos grow without
limit. :class:`LRUCache` bounds them: when it is full, it removes the
entry that was used least recently.

A memo only stores values that the decoder computes anyway. So a bound
changes the cost of a call, never its result. ``maxsize=None`` keeps
the old unbounded behaviour.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class LRUCache(OrderedDict):
    """A dict with an optional size bound and least-recently-used eviction.

    ``get`` and ``[]`` mark a hit as recently used. ``in`` does not.
    ``self[k] = v`` inserts or replaces ``k`` and then removes the oldest
    entries until ``len(self) <= maxsize``. ``maxsize=None``: no bound.
    Equality is plain dict equality (the order does not matter).
    Only ``get``, ``[]``, ``self[k] = v``, ``in``, ``len``, iteration and
    ``clear`` are part of the contract (``update`` / ``setdefault`` do not
    evict).
    """

    def __init__(self, maxsize: int | None = None) -> None:
        super().__init__()
        self.maxsize = _check(maxsize)
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    __eq__ = dict.__eq__
    __ne__ = dict.__ne__
    __hash__ = None  # type: ignore[assignment]

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self:
            self.move_to_end(key)
            self.hits += 1
            return dict.__getitem__(self, key)
        self.misses += 1
        return default

    def __getitem__(self, key: Any) -> Any:
        v = dict.__getitem__(self, key)
        self.move_to_end(key)
        return v

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self.move_to_end(key)
        if self.maxsize is not None:
            while len(self) > self.maxsize:
                self.popitem(last=False)
                self.evictions += 1

    def resize(self, maxsize: int | None) -> None:
        """Set a new bound. The oldest entries go if the cache is now too large."""
        self.maxsize = _check(maxsize)
        if self.maxsize is not None:
            while len(self) > self.maxsize:
                self.popitem(last=False)
                self.evictions += 1

    def info(self) -> dict[str, Any]:
        """Size, bound and counters (hits/misses count ``get`` calls only)."""
        return {"size": len(self), "maxsize": self.maxsize, "hits": self.hits, "misses": self.misses,
                "evictions": self.evictions}

    def copy(self) -> "LRUCache":
        return _rebuild(self.maxsize, list(OrderedDict.items(self)))

    def __repr__(self) -> str:
        return f"LRUCache(size={len(self)}, maxsize={self.maxsize})"

    def __reduce__(self):  # pickle: the bound and the entries (oldest first)
        return (_rebuild, (self.maxsize, list(OrderedDict.items(self))))


def _rebuild(maxsize: int | None, items: list) -> LRUCache:
    c = LRUCache(maxsize)
    for k, v in items:
        c[k] = v
    return c


def _check(maxsize: int | None) -> int | None:
    if maxsize is None:
        return None
    if isinstance(maxsize, bool) or int(maxsize) != maxsize or maxsize < 1:
        raise ValueError("maxsize must be a positive int or None")
    return int(maxsize)
