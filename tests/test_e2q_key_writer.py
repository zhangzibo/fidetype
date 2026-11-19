"""P11-09: the character-key CTC token -> KeyboardEvent.code writer of the emg2qwerty adapter."""

from __future__ import annotations

import string

import numpy as np
import pytest

from fidetype.adapters import emg2qwerty as A
from fidetype.benchmark.registry import keycodes_to_chars

#: The P11-01 vocabulary: blank, the 95 printable ASCII characters, Backspace, Enter (98 entries).
P1101_VOCAB = ["<blank>", *[chr(c) for c in range(32, 127)], A.TOKEN_BACKSPACE, A.TOKEN_ENTER]


def test_token_key_code_follows_the_track_truth_rule():
    for ch in string.printable:
        want = A.key_code(ch) if A.key_class(ch) is not None else None
        assert A.token_key_code(ch) == want, ch
    assert A.token_key_code("a") == A.token_key_code("A") == "KeyA"
    assert A.token_key_code(" ") == "Space"
    assert A.token_key_code(A.TOKEN_BACKSPACE) == "Backspace"
    assert A.token_key_code(A.TOKEN_ENTER) == "Enter"
    assert A.token_key_code("'") == "Quote"
    for ch in "!1?\"#:":  # digits and shifted symbols are not track classes
        assert A.token_key_code(ch) is None
    assert A.token_key_code("<blank>") is None


def test_tokens_to_codes():
    assert A.tokens_to_codes("Hi !" + A.TOKEN_BACKSPACE + A.TOKEN_ENTER) == "KeyH KeyI Space Backspace Enter"
    assert A.tokens_to_codes(["a", "<blank>", "1", "b"]) == "KeyA KeyB"
    assert A.tokens_to_codes("") == ""


def test_key_text_round_trip():
    codes = "KeyT KeyH KeyE Space KeyF KeyO KeyX Backspace Period Enter"
    text = A.codes_to_key_text(codes)
    assert " " not in text and text.startswith("the_fo")
    assert A.key_text_to_codes(text) == codes
    assert keycodes_to_chars(A.key_text_to_codes(text)) == keycodes_to_chars(codes)
    assert A.key_text_to_codes("a#") == "KeyA ?"


def test_key_ctc_vocab():
    v = A.key_ctc_vocab()
    assert v[0] == "<blank>" and len(v) == 1 + len(A.KEY_VOCAB) == 33
    assert len(set(v)) == len(v) and all(len(c) == 1 for c in v[1:])


def test_merge_to_key_ctc():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(7, len(P1101_VOCAB)))
    lp = x - np.logaddexp.reduce(x, axis=1, keepdims=True)
    m = A.merge_to_key_ctc(lp, P1101_VOCAB)
    assert m.shape == (7, 33) and m.dtype == np.float32
    np.testing.assert_allclose(np.logaddexp.reduce(m.astype(np.float64), axis=1), 0.0, atol=1e-5)
    # one-hot rows: "A" -> KeyA, "!" (no key) -> blank, Backspace -> Backspace
    v = A.key_ctc_vocab()
    for tok, col in (("A", v.index("a")), ("!", 0), (A.TOKEN_BACKSPACE, v.index("⌫")), (" ", v.index("_"))):
        row = np.full(len(P1101_VOCAB), -30.0)
        row[P1101_VOCAB.index(tok)] = 0.0
        out = A.merge_to_key_ctc(row[None, :], P1101_VOCAB)
        assert int(out[0].argmax()) == col, tok
    # "a" and "A" add up
    row = np.full(len(P1101_VOCAB), -np.inf)
    row[P1101_VOCAB.index("a")] = np.log(0.5)
    row[P1101_VOCAB.index("A")] = np.log(0.5)
    assert A.merge_to_key_ctc(row[None, :], P1101_VOCAB)[0, v.index("a")] == pytest.approx(0.0, abs=1e-6)


def test_merge_greedy_matches_writer():
    """Greedy CTC on the merged matrix equals the writer applied to greedy CTC on the token matrix (no a/A pair)."""
    seq = ["<blank>", "H", "H", "<blank>", "i", "!", "<blank>", " ", A.TOKEN_BACKSPACE, "<blank>", A.TOKEN_ENTER]
    lp = np.full((len(seq), len(P1101_VOCAB)), -20.0)
    for t, tok in enumerate(seq):
        lp[t, P1101_VOCAB.index(tok)] = 0.0
    m = A.merge_to_key_ctc(lp, P1101_VOCAB)
    v = A.key_ctc_vocab()
    a = m.argmax(axis=1)
    keep = np.r_[True, a[1:] != a[:-1]] & (a != 0)
    merged_text = "".join(v[i] for i in a[keep])
    b = lp.argmax(axis=1)
    keep_b = np.r_[True, b[1:] != b[:-1]] & (b != 0)
    tokens = [P1101_VOCAB[i] for i in b[keep_b]]
    assert A.key_text_to_codes(merged_text) == A.tokens_to_codes(tokens) == "KeyH KeyI Space Backspace Enter"


def test_merge_rejects_bad_shape():
    with pytest.raises(ValueError):
        A.merge_to_key_ctc(np.zeros((3, 5)), P1101_VOCAB)
