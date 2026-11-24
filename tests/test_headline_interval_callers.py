"""Check: every caller of ``calibration_draw_interval`` that can make a headline uses the adopted rule.

The adopted safe-WPM v0.2 reporting rule needs K >= 80 calibration draws and partition-only draws
(docs/safe-wpm.md section 6b). The function warns when a call breaks it, but it does not refuse. This test
reads the code of the library, the tools, the benchmark, the experiment scripts and the docs examples. Each
call must either pass ``draw_scheme="partition"`` (a headline candidate; K is checked at run time), or be pinned
to ``metric_version="0.1"`` (an old number: the function labels its result ``adopted_headline: false`` with
the reason in ``not_headline_because``). The tests in ``tests/`` are not callers of a headline.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
NAME = "calibration_draw_interval"
SCAN = [("src", "*.py"), ("tools", "*.py"), ("benchmark", "*.py"), ("experiments", "*.py"), ("docs", "*.md"),
        ("benchmark", "*.md")]
_CALL = re.compile(r"\b" + NAME + r"\(")  # a call; prose such as "name (..." is not one


def _call_text(text: str, start: int) -> str:
    """The argument text of one call, from its ``(`` to the matching ``)``."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def _calls() -> list[tuple[str, int, str]]:
    out = []
    for top, pat in SCAN:
        base = ROOT / top
        if not base.is_dir():
            continue
        for p in sorted(base.rglob(pat)):
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            for m in _CALL.finditer(text):
                line_start = text.rfind("\n", 0, m.start()) + 1
                if text[line_start:m.start()].lstrip().startswith("def "):
                    continue  # the definition itself
                rel = p.relative_to(ROOT).as_posix()
                if rel.startswith("experiments/") and "/test_" in rel:
                    continue  # experiment unit tests (toy numbers)
                args = _call_text(text, m.end() - 1)
                out.append((rel, text.count("\n", 0, m.start()) + 1, args))
    return out


def _kind(args: str) -> str:
    flat = re.sub(r"\s+", "", args)
    if 'draw_scheme="partition"' in flat or "draw_scheme='partition'" in flat:
        return "headline"
    if 'metric_version="0.1"' in flat or "metric_version='0.1'" in flat:
        return "pinned-v0.1"
    return "breaks-rule"


def test_no_headline_caller_breaks_the_rule():
    calls = _calls()
    assert calls, "the scan found no caller; the check would test nothing"
    bad = [f"{f}:{n}" for f, n, a in calls if _kind(a) == "breaks-rule"]
    assert not bad, ("calls of calibration_draw_interval that are neither partition-only headline calls nor "
                     "pinned to metric_version='0.1': " + ", ".join(bad))
    # the docs example (the public headline recipe) passes draw_scheme="partition"
    docs = [(f, n) for f, n, a in calls if f.startswith("docs/") and _kind(a) == "headline"]
    assert docs, "the docs example of the headline interval must pass draw_scheme='partition'"


def test_kinds():
    assert _kind('(d, nw, B=2, draw_scheme="partition")') == "headline"
    assert _kind('(d, nw, metric_version="0.1")') == "pinned-v0.1"
    assert _kind("(d, nw, B=2)") == "breaks-rule"
    assert _kind('(d, nw, draw_scheme="resample")') == "breaks-rule"


def _toy(n: int = 40, k: int = 80, seed: int = 0):
    rng = np.random.default_rng(seed)
    nw = rng.integers(3, 9, n).astype(float)
    nc = nw * 5.0
    ns = rng.uniform(5.0, 15.0, n)
    g = {"method": "ltt", "alpha": 0.5, "delta": 0.1, "n_cal": 100}
    draws = []
    for _ in range(k):
        com = rng.random(n) < 0.5
        draws.append({"committed": com.tolist(), "correct": (com & (rng.random(n) < 0.97)).tolist(),
                      "guarantee": dict(g)})
    return draws, nw, nc, ns


def test_headline_path_gives_no_warning():
    from fidetype.benchmark.safe_wpm import MIN_CALIBRATION_DRAWS, calibration_draw_interval

    draws, nw, nc, ns = _toy(k=MIN_CALIBRATION_DRAWS)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the headline path
        r = calibration_draw_interval(draws, nw, nc, ns, B=50, seed=0, draw_scheme="partition")
    assert r["adopted_headline"] is True and r["n_draws"] >= 80 and r["draw_scheme"] == "partition"


def test_pinned_v01_callers_are_labelled_not_a_headline():
    from fidetype.benchmark.safe_wpm import CalibrationIntervalWarning, calibration_draw_interval

    draws, nw, nc, ns = _toy(k=40)
    with pytest.warns(CalibrationIntervalWarning):
        r = calibration_draw_interval(draws, nw, nc, ns, B=50, seed=0, metric_version="0.1")
    assert r["adopted_headline"] is False
    assert any("safe-wpm/0.1" in w for w in r["not_headline_because"])
