from neurotext.streams.vocab import (
    BLANK_ID,
    KEY_POS,
    SPACE_ID,
    VOCAB,
    decode,
    encode,
    key_distance,
    normalize_text,
)


def test_vocab_layout():
    assert len(VOCAB) == 28
    assert VOCAB[BLANK_ID] == "<blank>" and BLANK_ID == 0
    assert VOCAB[1] == "a" and VOCAB[26] == "z"
    assert VOCAB[SPACE_ID] == " " and SPACE_ID == 27


def test_round_trip():
    text = "the quick brown fox jumps over the lazy dog"
    ids = encode(text)
    assert all(1 <= i <= 27 for i in ids)
    assert decode(ids) == text


def test_normalize_maps_and_drops():
    assert normalize_text("Hello,  World!") == "hello world"
    assert normalize_text("Hello,World", unknown="drop") == "helloworld"
    assert normalize_text("  café\tniño 42 ") == "cafe nino"
    assert encode("A-b", unknown="space") == encode("a b")


def test_decode_skips_blank():
    assert decode([BLANK_ID, 1, BLANK_ID, 2]) == "ab"


def test_key_distance():
    assert key_distance("a", "a") == 0.0
    assert key_distance("q", "w") == 1.0
    # Row stagger: "a" is 0.25 keys right of "q".
    assert KEY_POS["a"] == (0.25, 1.0)
    assert key_distance("f", "g") < key_distance("f", "p")
    assert key_distance("q", "p") == 9.0
    assert set(KEY_POS) == set(VOCAB[1:])
