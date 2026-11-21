"""P2-14 (gap 154): the CI shard split in tests/conftest.py covers every test file exactly once."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DEFAULT_SECONDS_PER_TEST, assign_shards, load_weights, parse_shard

TESTS = Path(__file__).parent


def test_parse_shard() -> None:
    assert parse_shard("1/2") == (1, 2)
    assert parse_shard("3/3") == (3, 3)
    for bad in ("0/2", "3/2", "1/0", "x", "1/2/3", ""):
        with pytest.raises(pytest.UsageError):
            parse_shard(bad)


def test_assign_is_a_partition_and_deterministic() -> None:
    weights = {f"tests/test_{i}.py": float((i * 37) % 11 + 1) for i in range(40)}
    for n in (1, 2, 3, 5):
        a = assign_shards(weights, n)
        assert set(a) == set(weights)
        assert set(a.values()) <= set(range(1, n + 1))
        assert a == assign_shards(dict(reversed(list(weights.items()))), n)


def test_assign_balances_lpt() -> None:
    a = assign_shards({"a": 10.0, "b": 6.0, "c": 5.0, "d": 1.0}, 2)
    totals = {1: 0.0, 2: 0.0}
    for f, s in a.items():
        totals[s] += {"a": 10.0, "b": 6.0, "c": 5.0, "d": 1.0}[f]
    assert sorted(totals.values()) == [11.0, 11.0]


def test_real_suite_split_covers_every_file() -> None:
    files = sorted(f"tests/{p.name}" for p in TESTS.glob("test_*.py"))
    known = load_weights()
    weights = {f: known.get(f, DEFAULT_SECONDS_PER_TEST) for f in files}
    a = assign_shards(weights, 2)
    assert sorted(a) == files
    assert {1, 2} == set(a.values())


def test_weights_table_is_usable() -> None:
    # Entries for removed files are harmless (only collected files are split), so they are not an error.
    known = load_weights()
    assert known, "tests/shard_weights.json is missing or empty"
    assert all(v >= 0 for v in known.values())
