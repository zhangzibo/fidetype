"""M6-13: the guard's edit-distance memo has a small bound (it grew for hours in the live soak test)."""

from __future__ import annotations

import random

import numpy as np

from fidetype.trust import guard
from fidetype.trust._align import (
    GUARD_EDIT_CACHE_SIZE,
    cached_edit_distance,
    edit_distance,
    guard_edit_distance,
)

WORDS = ["the", "a", "boy", "girl", "took", "packed", "nurse", "driver", "carried", "broken", "cleaned", "my"]


def _sentence(rng: random.Random) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(rng.randint(0, 9)))


def test_three_edit_distances_agree() -> None:
    rng = random.Random(0)
    for _ in range(500):
        a, b = tuple(_sentence(rng).split()), tuple(_sentence(rng).split())
        d = edit_distance(a, b)
        assert guard_edit_distance(a, b) == d == cached_edit_distance(a, b) == edit_distance(b, a)
        sa, sb = " ".join(a), " ".join(b)
        assert guard_edit_distance(sa, sb) == edit_distance(sa, sb)
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance((), ("a", "b")) == 2


def _ref_similarity(a: str, b: str) -> float:
    wa, wb = tuple(a.split()), tuple(b.split())
    n = max(len(wa), len(wb))
    return 1.0 if n == 0 else 1.0 - edit_distance(wa, wb) / n


def _ref_entropy(texts, post, k):
    reps, mass = [], []
    for t, p in zip(texts, post):
        w = tuple(t.split())
        for i, r in enumerate(reps):
            if edit_distance(w, r) <= k:
                mass[i] += float(p)
                break
        else:
            reps.append(w)
            mass.append(float(p))
    m = np.asarray(mass)
    m = m / m.sum()
    m = m[m > 0]
    return float(-(m * np.log(m)).sum())


def test_guard_memo_stays_bounded_and_results_do_not_change() -> None:
    guard_edit_distance.cache_clear()
    rng = random.Random(1)
    # Many distinct n-best lists, as in a long live session: the memo must stop at its bound.
    for _ in range(3000):
        texts = [_sentence(rng) for _ in range(10)]
        post = np.asarray([rng.random() + 1e-3 for _ in texts])
        post = post / post.sum()
        c = guard.nbest_consistency(texts, post, 5)
        ref_sims = np.array([_ref_similarity(texts[0], t) for t in texts[:5]])
        assert c == float(np.sum(post[:5] * ref_sims) / np.sum(post[:5]))
        for k in (0, 1):
            assert np.isclose(guard.semantic_entropy(texts, post, k), _ref_entropy(texts, post, k))
        assert guard_edit_distance.cache_info().currsize <= GUARD_EDIT_CACHE_SIZE
    info = guard_edit_distance.cache_info()
    assert info.maxsize == GUARD_EDIT_CACHE_SIZE
    assert info.currsize == GUARD_EDIT_CACHE_SIZE  # it filled, and the bound held


def test_offline_memo_is_separate() -> None:
    guard_edit_distance.cache_clear()
    before = cached_edit_distance.cache_info().currsize
    guard.word_similarity("a boy took", "a girl took")
    assert cached_edit_distance.cache_info().currsize == before  # the guard no longer fills the eval memo
    assert guard_edit_distance.cache_info().currsize == 1
