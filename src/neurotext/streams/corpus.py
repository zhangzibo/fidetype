"""Simple English sentences for tests and demos.

The list is small and written for this project. It has no licence
restrictions. :func:`sentences` adds sentences from templates when a
caller needs more than the fixed list.
"""

from __future__ import annotations

import numpy as np

BASE_SENTENCES: tuple[str, ...] = (
    "the quick brown fox jumps over the lazy dog",
    "please close the window before you leave",
    "my sister works at the city hospital",
    "we will meet at the station at noon",
    "the coffee is too hot to drink",
    "he forgot his keys in the car again",
    "can you send me the report by friday",
    "the children played in the park all day",
    "it is raining so take an umbrella",
    "i would like a glass of water please",
    "the train was late this morning",
    "she reads a book every week",
    "turn left at the next corner",
    "the meeting starts in ten minutes",
    "our dog likes to sleep by the fire",
    "they bought fresh bread at the market",
    "the light in the kitchen is broken",
    "do you know where the museum is",
    "my phone battery is almost empty",
    "the jazz band played until midnight",
    "a lazy zebra walked to the zoo",
    "the quiz was quick and fun",
    "we keep the knives in the top drawer",
    "she wrote a long letter to her friend",
    "the weather will be warm tomorrow",
    "please call me when you get home",
    "the old man walked slowly up the hill",
    "i need to buy milk and eggs",
    "the cat jumped onto the kitchen table",
    "he plays the violin very well",
    "the river is wide and deep here",
    "we watched a movie last night",
    "this soup needs more salt",
    "the doctor will see you now",
    "my brother lives near the sea",
    "the bus stops in front of the bank",
    "she likes to walk in the morning",
    "the garden is full of yellow flowers",
    "what time does the shop open",
    "i am happy to help you today",
)

_SUBJECTS = (
    "the boy", "my mother", "the teacher", "a small dog", "our neighbour",
    "the driver", "my friend", "the old woman", "the student", "his father",
    "the nurse", "a young girl", "the farmer", "her uncle", "the cook",
)
_VERBS = (
    "found", "wanted", "carried", "painted", "cleaned", "watched", "opened",
    "fixed", "liked", "packed", "moved", "checked", "sold", "kept", "took",
)
_OBJECTS = (
    "a red box", "the black bag", "an old map", "the new chair", "a warm coat",
    "the blue cup", "a heavy book", "the wooden door", "a big jar of honey",
    "the broken clock", "a quiet room", "the white jacket", "a sharp knife",
    "the empty bottle", "a fresh pizza",
)
_PLACES = (
    "in the house", "at the office", "near the lake", "after lunch",
    "before dinner", "in the village", "on the boat", "at school",
    "in the evening", "by the window", "at the market", "in the morning",
    "on monday", "after the storm", "next to the bridge",
)


def sentences(n: int, seed: int = 0) -> list[str]:
    """Return ``n`` different simple sentences.

    The function returns the fixed list first. Then it adds sentences
    from templates (subject, verb, object, place), in a random order that
    ``seed`` sets.
    """
    out = list(BASE_SENTENCES[:n])
    if len(out) == n:
        return out
    rng = np.random.default_rng(seed)
    seen = set(out)
    limit = len(_SUBJECTS) * len(_VERBS) * len(_OBJECTS) * len(_PLACES)
    if n - len(out) > limit:
        raise ValueError(f"cannot make more than {limit + len(BASE_SENTENCES)} sentences")
    while len(out) < n:
        s = " ".join(
            (
                _SUBJECTS[rng.integers(len(_SUBJECTS))],
                _VERBS[rng.integers(len(_VERBS))],
                _OBJECTS[rng.integers(len(_OBJECTS))],
                _PLACES[rng.integers(len(_PLACES))],
            )
        )
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out
