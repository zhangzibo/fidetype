"""P11-11 run.py helpers (CPU, no data): Backspace resolution, rescoring, merge, tuning split, cache key.

    .venv\\Scripts\\python.exe -m pytest -q experiments/2026-11-19-p11-11-emg-nonvacuous/test_p11_11.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_11_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_11_run"] = m
    spec.loader.exec_module(m)
    return m


def test_resolve_applies_backspace_and_drops_enter(run):
    from fidetype.adapters import emg2qwerty as A

    kt = A.codes_to_key_text("KeyE KeyN Backspace KeyM KeyI Space Space KeyA Comma Enter")
    assert run.resolve(kt) == "emi a,"
    assert run.resolve(A.codes_to_key_text("Backspace Backspace KeyH KeyI")) == "hi"
    # a Backspace after a space removes the space
    assert run.resolve(A.codes_to_key_text("KeyA Space Backspace KeyB")) == "ab"
    assert run.resolve(A.codes_to_key_text("Space KeyA Space Enter")) == "a"
    assert run.intended_truth({"codes": "KeyF KeyI KeyX Space Backspace Backspace Backspace Backspace KeyO Enter"}) == "o"


class _LM:
    def score_sentence(self, text):
        return -1.0 * len(text) - (5.0 if "zz" in text else 0.0)


def test_rescoring_merges_and_ranks(run):
    from fidetype.adapters import emg2qwerty as A

    d = run.Decoder()
    d.lm = _LM()
    d.lex = frozenset({"hi", "ho"})
    bs = A.key_chars()[A.KEY_VOCAB.index("Backspace")]
    hyps = [("hi", -1.0), (f"hx{bs}i", -1.5), ("zz", -0.5), ("ho", -2.0)]
    out = d.intended(hyps, w=1.0, c=1.0)
    texts = [t for t, _ in out]
    assert texts[0] == "hi"  # merged: logaddexp(-1, -1.5) - 2 > -0.5 - 2 - 5 - 1
    assert len(texts) == len(set(texts)) == 3
    merged = float(np.logaddexp(-1.0, -1.5)) - 2.0
    assert out[0][1] == pytest.approx(merged)
    k = d.keys(hyps, w=1.0, c=1.0)
    assert {t for t, _ in k} == {t for t, _ in hyps}
    assert k[0][0] == "hi"


def test_tune_items_are_calibrates_fit_and_grid_parts(run):
    pos = run.tune_items(1224)
    assert len(pos) == 765 == len(set(pos))
    order = np.random.default_rng(0).permutation(1224)
    assert set(pos) == {int(i) for i in order[:765]}
    assert not set(pos) & {int(i) for i in order[765:]}


def test_window_key_ignores_row_offset_and_tiny_noise(run):
    rng = np.random.default_rng(1)
    x = rng.normal(size=(50, 33))
    x = x - np.logaddexp.reduce(x, axis=1, keepdims=True)
    assert run.window_key(x) == run.window_key(x + 0.0)
    assert run.window_key(x) != run.window_key(x[:-1])


def test_arm_settings(run):
    assert run.arm_kw("S") == {} and run.arm_kw("K") == {}
    assert run.arm_kw("X") == {"confidence": "learned", "commit_unit": "prefix"}
    assert run.arm_fn("K") is run.decode_keys and run.arm_fn("S") is run.decode_intended


def test_contains_block_matches_the_slow_rule(run):
    longt = ["a large number of", "the quick brown fox jumps"]
    sents = ["there is a large number of cats", "a large number", "quick brown fox jumps", "the quick brown fox",
             "brown fox jumps", "nothing here at all today", "a large number of"]
    L = run.LM_BLOCK_MIN_LEN
    slow = [any(t in s for t in longt) or (len(s) >= L and any(s in t for t in longt)) for s in sents]
    assert [run.contains_block(s, longt) for s in sents] == slow
    assert slow == [True, False, True, True, True, False, True]
