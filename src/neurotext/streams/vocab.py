"""Character vocabulary and QWERTY key positions.

The vocabulary follows Brain2Qwerty (Levy et al. 2025, v1; v2). It has
28 classes:

- id 0: the CTC blank (``"<blank>"``),
- ids 1-26: the letters ``a`` to ``z``,
- id 27: the space (``" "``).

Text is lower case only. The helpers fold accents (``"é"`` becomes
``"e"``, ``"ñ"`` becomes ``"n"``). They map other characters to a space
or drop them.

The QWERTY table gives each key a position in key units. We use the
standard row stagger of an ANSI keyboard: the home row is 0.25 keys to
the right of the top row, and the bottom row is 0.75 keys to the right.
Brain2Qwerty v1 reports that decoding errors rise with keyboard distance
(r = 0.73). The simulator uses this table to model that effect.
"""

from __future__ import annotations

import math
import unicodedata
from typing import Iterable, Literal

BLANK_TOKEN = "<blank>"
BLANK_ID = 0
SPACE_ID = 27
LETTERS = "abcdefghijklmnopqrstuvwxyz"

#: The 28 tokens, in id order.
VOCAB: tuple[str, ...] = (BLANK_TOKEN, *LETTERS, " ")
VOCAB_SIZE = len(VOCAB)

_CHAR_TO_ID = {c: i for i, c in enumerate(VOCAB) if i != BLANK_ID}

Unknown = Literal["space", "drop"]


def normalize_text(text: str, unknown: Unknown = "space") -> str:
    """Return ``text`` in the vocabulary character set.

    The function does these steps:

    1. It changes the text to lower case and removes accents.
    2. It keeps ``a``-``z`` and the space.
    3. It changes all other characters to a space (``unknown="space"``)
       or removes them (``unknown="drop"``). Whitespace always becomes a
       space.
    4. It joins runs of spaces into one space and removes spaces at the
       start and the end.
    """
    if unknown not in ("space", "drop"):
        raise ValueError(f"unknown must be 'space' or 'drop', not {unknown!r}")
    decomposed = unicodedata.normalize("NFKD", text.lower())
    out: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch):
            continue  # Remove the accent mark. Keep the base letter.
        if "a" <= ch <= "z" or ch == " ":
            out.append(ch)
        elif ch.isspace() or unknown == "space":
            out.append(" ")
        # Otherwise, drop the character.
    return " ".join("".join(out).split())


def encode(text: str, unknown: Unknown = "space") -> list[int]:
    """Normalise ``text`` and return its token ids (no blanks)."""
    return [_CHAR_TO_ID[c] for c in normalize_text(text, unknown)]


def decode(ids: Iterable[int]) -> str:
    """Return the text for token ids. Blank ids are skipped.

    This function does not collapse repeats. For CTC decoding, use
    :func:`neurotext.eval.metrics.ctc_greedy_decode`.
    """
    out = []
    for i in ids:
        i = int(i)
        if not 0 <= i < VOCAB_SIZE:
            raise ValueError(f"token id {i} is out of range 0..{VOCAB_SIZE - 1}")
        if i != BLANK_ID:
            out.append(VOCAB[i])
    return "".join(out)


# --- QWERTY geometry ------------------------------------------------------

_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_ROW_OFFSETS = (0.0, 0.25, 0.75)

#: Key centre (x, y) in key units. y grows downwards. ``x`` of ``q`` is 0.
KEY_POS: dict[str, tuple[float, float]] = {
    ch: (offset + col, float(row))
    for row, (keys, offset) in enumerate(zip(_ROWS, _ROW_OFFSETS))
    for col, ch in enumerate(keys)
}
# The space bar is one row below the bottom row. Its centre is near "b".
KEY_POS[" "] = (4.75, 3.0)


def key_distance(a: str, b: str) -> float:
    """Return the Euclidean distance between two keys, in key units."""
    (xa, ya), (xb, yb) = KEY_POS[a], KEY_POS[b]
    return math.hypot(xa - xb, ya - yb)
