"""Test-suite plugin: split the suite into CI shards (P2-14, gap 154).

`pytest --shard K/N` runs only shard K of N (1-based). Each test file goes to exactly one shard, so module-scoped
fixtures still run once. The split is deterministic: files are sorted by weight (heaviest first, then by name) and
each file goes to the shard with the smallest total weight so far (LPT greedy). The weight of a file is its time in
seconds from `tests/shard_weights.json` (measured on CI). A file that is not in the table gets
`DEFAULT_SECONDS_PER_TEST` per test.

`pytest --file-durations` prints the time of each test file at the end (setup + call + teardown). Use it to refresh
`tests/shard_weights.json` when the split gets unbalanced.

Without `--shard`, nothing is deselected: a plain `pytest` still runs the full suite.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

WEIGHTS_PATH = Path(__file__).with_name("shard_weights.json")
DEFAULT_SECONDS_PER_TEST = 0.5


def parse_shard(text: str) -> tuple[int, int]:
    """Parse "K/N" into (K, N) with 1 <= K <= N."""
    try:
        k_text, n_text = text.split("/")
        k, n = int(k_text), int(n_text)
    except ValueError:
        raise pytest.UsageError(f"--shard must be K/N (for example 1/2), got {text!r}") from None
    if n < 1 or not 1 <= k <= n:
        raise pytest.UsageError(f"--shard K/N needs 1 <= K <= N, got {text!r}")
    return k, n


def assign_shards(file_weights: dict[str, float], n: int) -> dict[str, int]:
    """Map each file to a shard in 1..n (LPT greedy; deterministic for the same input)."""
    totals = [0.0] * n
    out: dict[str, int] = {}
    for name in sorted(file_weights, key=lambda f: (-file_weights[f], f)):
        best = min(range(n), key=lambda i: (totals[i], i))
        out[name] = best + 1
        totals[best] += file_weights[name]
    return out


def load_weights(path: Path = WEIGHTS_PATH) -> dict[str, float]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): float(v) for k, v in data.get("seconds", {}).items()}


def _file_key(item: pytest.Item) -> str:
    return item.nodeid.split("::", 1)[0].replace("\\", "/")


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("fidetype-shard")
    group.addoption("--shard", default=None, metavar="K/N", help="run only shard K of N (whole test files)")
    group.addoption("--file-durations", action="store_true", default=False,
                    help="print the total time of each test file at the end")


def pytest_configure(config: pytest.Config) -> None:
    text = config.getoption("--shard")
    config._fidetype_shard = parse_shard(text) if text else None  # type: ignore[attr-defined]
    config._fidetype_file_seconds = defaultdict(float)  # type: ignore[attr-defined]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    shard = config._fidetype_shard  # type: ignore[attr-defined]
    if shard is None:
        return
    k, n = shard
    known = load_weights()
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[_file_key(item)] += 1
    weights = {f: known.get(f, DEFAULT_SECONDS_PER_TEST * c) for f, c in counts.items()}
    mapping = assign_shards(weights, n)
    keep = [it for it in items if mapping[_file_key(it)] == k]
    drop = [it for it in items if mapping[_file_key(it)] != k]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep
    mine = sorted(f for f, s in mapping.items() if s == k)
    est = sum(weights[f] for f in mine)
    config._fidetype_shard_summary = (  # type: ignore[attr-defined]
        f"shard {k}/{n}: {len(mine)} of {len(mapping)} files, {len(keep)} tests, about {est:.0f} s by weight")


def pytest_report_collectionfinish(config: pytest.Config) -> str | None:
    return getattr(config, "_fidetype_shard_summary", None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):  # type: ignore[no-untyped-def]
    yield
    if item.config.getoption("--file-durations"):
        item.config._fidetype_file_seconds[_file_key(item)] += call.duration  # type: ignore[attr-defined]


def pytest_terminal_summary(terminalreporter, exitstatus, config: pytest.Config) -> None:  # type: ignore[no-untyped-def]
    if not config.getoption("--file-durations"):
        return
    seconds = config._fidetype_file_seconds  # type: ignore[attr-defined]
    terminalreporter.section("file durations (s)")
    for name, s in sorted(seconds.items(), key=lambda kv: -kv[1]):
        terminalreporter.write_line(f"{s:9.2f} {name}")
    terminalreporter.write_line("json: " + json.dumps({k: round(v, 1) for k, v in sorted(seconds.items())}))
