"""Small CPU tests for P15-38 (no data, no LM file, no torch)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402


def test_decoders_are_the_p1525_settings():
    mine = C.config()["decoders"]
    p25 = json.loads((C.REPO / C.config()["p1525_dir"] / "config.json").read_text(encoding="utf-8"))["decoders"]
    assert mine["F"] == p25["F"] and mine["FL"] == p25["FL"]
    assert mine["Fv"] == {"w": 0.5, "beta": 2.0, "lam": 0.0, "B": 8}  # the P15-25 val-tuned value, not retuned
    assert C.config()["old_lm_sha256"] == json.loads(
        (C.REPO / C.config()["p1525_dir"] / "config.json").read_text(encoding="utf-8"))["lm_sha256"]


def test_p1525_verdict_code_imports_unchanged():
    P = C.p1525()
    assert len(P.all_runs()) == 41 and len(P.VOCAB) == 98
    assert callable(P.verdict) and callable(P.beats) and callable(P.bootstrap)


def test_own_paths_stay_in_p15_38():
    assert C.own("tests", "y.json").is_relative_to(C.OWN.resolve())
    with pytest.raises(AssertionError):
        C.own("..", "p15-25", "z.json")
    with pytest.raises(AssertionError):
        C.save_json({}, C.P1525 / "never.json")


def test_contains_block_rule():
    sys.path.insert(0, str(C.REPO / "src"))
    M = C.load_module("p1111run", C.REPO / C.config()["p1111_dir"] / "run.py")
    longt = ["the quick brown fox jumps"]
    assert M.contains_block("i saw the quick brown fox jumps over", longt)  # sentence contains a blocked text
    assert M.contains_block("quick brown fox", longt)  # sentence (>= 15 chars) inside a blocked text
    assert not M.contains_block("brown fox", longt)  # too short to count as contained
    assert not M.contains_block("a slow red dog sleeps all day", longt)
