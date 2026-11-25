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


# --- amendment 1: sentence-group-aware calibration parts -------------------------------------------------------------


def _ho_items():
    return [(k, s, t) for k, s, t in _items() if k in H.assign(_items(), q=0.5)]


def test_tune_groups_take_whole_groups_and_skip_excluded():
    ho = _ho_items()
    excl = frozenset(H.normalize_text(t) for _k, _s, t in ho[:30])
    tune, cal = H.split_tune_groups(ho, n_tune=60, exclude=excl)
    assert len(tune) >= 60 and not set(tune) & set(cal) and set(tune) | set(cal) == {k for k, _s, _t in ho}
    text = {k: H.normalize_text(t) for k, _s, t in ho}
    tune_g, cal_g = {text[k] for k in tune}, {text[k] for k in cal}
    assert not tune_g & cal_g and not tune_g & excl
    assert H.split_tune_groups(ho, n_tune=60, exclude=excl) == (tune, cal)  # deterministic
    try:
        H.split_tune_groups(ho, n_tune=10 ** 6)
        raise AssertionError("too large n_tune accepted")
    except ValueError:
        pass


def test_pool_groups_and_draw_seed():
    pool = [("a|val_select|0", "a", "Hello, World"), ("b|train|3", "b", "hello world")]
    assert H.pool_groups(pool) == ["hello world", "hello world"]
    assert H.draw_seed("A", 1) == H.draw_seed("A", 1) != H.draw_seed("A", 2) != H.draw_seed("B", 1)
    assert 0 <= H.draw_seed("A", 1) < 16 ** 8


def test_part_crossing_plain_vs_group_aware():
    groups = [H.normalize_text(t) for _k, _s, t in _items()]  # 300 sentences, each repeats
    plain = H.part_crossing(groups, H.draw_seed("A", 1))
    aware = H.part_crossing(groups, H.draw_seed("A", 1), group_aware=True)
    assert plain["crossing_groups"] > 0 and plain["ltt_items_sharing_a_group_with_fit_or_policy"] > 0
    assert aware["crossing_groups"] == 0 and aware["crossing_items"] == 0
    assert aware["ltt_items_sharing_a_group_with_fit_or_policy"] == 0 and sum(aware["sizes"]) == len(groups)


def test_crossing_audit_on_synthetic_parts():
    items = _items()
    parts = {"train": items,
             "val_select": [(f"v|val_select|{i}", "v", f"sentence number {_w(i % 40)}") for i in range(60)],
             "val_eval": [(f"v|val_eval|{i}", "v", f"sentence number {_w(i)}") for i in range(20)]}
    r = H.crossing_audit(parts, n_draws=3, n_tune=40)
    new = r["amendment 1 (rule 5 tune set)"]
    assert new["tune_groups_also_in_pool_A"] == 0 and new["pool_A_items_sharing_a_group_with_tune"] == 0
    for arm in ("A", "B", "R"):
        assert new[f"arm_{arm}_group_aware_split"]["crossing_groups"]["max"] == 0
    assert r["old (rule 4, plain split)"]["arm_A_plain_split"]["crossing_groups"]["max"] > 0
