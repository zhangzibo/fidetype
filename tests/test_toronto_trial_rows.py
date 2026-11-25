"""The Toronto per-trial files: ``n_words`` holds the word count, not the correct flag.

Before 2026-11-25 the writer in ``experiments/2026-11-16-p6-01-tracks/run.py`` unpacked its ``zip`` in the
wrong order, so ``n_words`` held the correct flag (0 or 1). These tests check the fixed writer and the reader
check in ``tools/benchmark/add_safe_wpm_v02_tracks01.py``. No data are needed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def run():
    return _load("p6_01_tracks_run", "experiments/2026-11-16-p6-01-tracks/run.py")


@pytest.fixture(scope="module")
def tool():
    return _load("add_safe_wpm_v02_tracks01", "tools/benchmark/add_safe_wpm_v02_tracks01.py")


def test_trial_rows_hold_word_counts(run):
    texts = ["the cat sat", "a dog", "one two three four five", "hello"]
    committed = np.array([True, True, False, True])
    correct = np.array([True, False, True, False])  # a "correct" flag on an uncommitted trial does not count
    nw = np.array([len(t.split()) for t in texts], float)
    nc = np.array([len(t) for t in texts], float)
    rows = run.trial_rows([f"id{i}" for i in range(4)], committed, correct, nw, nc, cpm=60.0)
    assert [r["n_words"] for r in rows] == [3, 2, 5, 1]
    assert [r["n_chars"] for r in rows] == [11, 5, 23, 5]
    assert [r["committed"] for r in rows] == [True, True, False, True]
    assert [r["correct"] for r in rows] == [True, False, False, False]
    assert [r["neural_s"] for r in rows] == [11.0, 5.0, 23.0, 5.0]  # 60 chars/min = 1 s per char
    # the old bug: n_words equal to the correct flag
    assert [r["n_words"] for r in rows] != [int(r["correct"]) for r in rows]


def test_trial_rows_need_equal_lengths(run):
    with pytest.raises(ValueError):
        run.trial_rows(["a", "b"], [True], [True], [1.0], [1.0], cpm=60.0)


def test_reader_checks_word_counts(tool):
    rows = [{"n_chars": 11, "n_words": 3}, {"n_chars": 5, "n_words": 2}]
    tool.check_counts("card.json", rows, np.array([11.0, 5.0]), np.array([3.0, 2.0]))  # no error
    old = [{"n_chars": 11, "n_words": 1}, {"n_chars": 5, "n_words": 0}]  # the correct flag in n_words
    with pytest.raises(SystemExit, match="word counts differ"):
        tool.check_counts("card.json", old, np.array([11.0, 5.0]), np.array([3.0, 2.0]))
    with pytest.raises(SystemExit, match="character counts differ"):
        tool.check_counts("card.json", rows, np.array([12.0, 5.0]), np.array([3.0, 2.0]))
