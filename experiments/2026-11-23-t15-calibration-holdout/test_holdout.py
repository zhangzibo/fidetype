"""CPU tests of the pre-registered hold-out rule (holdout.py). No data needed.

Run: C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-23-t15-calibration-holdout/test_holdout.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import holdout as H  # noqa: E402


def _w(i):
    """A letters-only word for an integer (normalize_text drops digits)."""
    return "".join("abcdefghij"[int(c)] for c in str(i))


def _items():
    texts = [f"sentence number {_w(i % 300)}" for i in range(1000)]  # every sentence repeats
    return [(f"s{i % 7}|train|{i}", f"s{i % 7}", t) for i, t in enumerate(texts)]


def test_normalize():
    assert H.normalize_text("  Hello,  World!  It's ") == "hello world it's"
    assert H.normalize_text("a1 b") == "a b"  # digits are dropped (T15 cue texts have none)


def test_whole_sentence_groups_stay_together():
    items = _items()
    ho = H.assign(items, q=0.3)
    side = {}
    for k, _s, t in items:
        side.setdefault(H.normalize_text(t), set()).add(k in ho)
    assert all(len(v) == 1 for v in side.values())


def test_rule_is_deterministic_and_salted():
    items = _items()
    assert H.assign(items) == H.assign(items)
    assert H.assign(items, salt="other") != H.assign(items)


def test_share_close_to_q():
    items = [(f"s|train|{i}", "s", f"unique {_w(i)}") for i in range(20000)]
    share = len(H.assign(items, q=0.2727)) / len(items)
    assert abs(share - 0.2727) < 0.015


def test_tune_split_disjoint_and_complete():
    items = _items()
    ho = H.assign(items, q=0.5)
    tune, cal = H.split_tune(ho, n_tune=50)
    assert len(tune) == 50 and not set(tune) & set(cal) and set(tune) | set(cal) == ho


def test_audit_reports_no_sentence_overlap():
    r = H.audit(_items(), q=0.3, n_tune=10)
    assert r["holdout_sentences_also_in_kept_train"] == 0
    assert r["holdout"] + r["train_kept"] == r["train_labelled"]


def test_bad_q_and_forbidden_out(tmp_path):
    try:
        H.assign(_items(), q=1.0)
        raise AssertionError("q = 1 accepted")
    except ValueError:
        pass
    assert "m4-13" in H.FORBIDDEN_OUT and "m4-01-02-lookahead" in H.FORBIDDEN_OUT
