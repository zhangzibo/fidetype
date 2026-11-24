"""CPU unit tests for the P15-45 pure rules (no data, no GPU)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p45  # noqa: E402

RULES = {"c2_min_cer": 0.75, "c2_min_gap": 0.10}


def test_c2_need_floor_and_gap():
    assert p45.c2_need(RULES, 0.36) == 0.75
    assert abs(p45.c2_need(RULES, 0.70) - 0.80) < 1e-12


def test_c2_row_pass_fail_missing():
    r = p45.c2_row(0.36, 0.90, RULES)
    assert r["pass"] is True and abs(r["margin"] - 0.15) < 1e-12
    r = p45.c2_row(0.36, 0.74, RULES)
    assert r["pass"] is False
    r = p45.c2_row(0.70, 0.79, RULES)  # gap rule decides: needs 0.80
    assert r["pass"] is False
    r = p45.c2_row(0.36, 0.75, RULES)  # equality passes
    assert r["pass"] is True
    assert p45.c2_row(None, 0.9, RULES)["status"] == "missing"


def _rows(vals):
    return {str(i): (p45.c2_row(0.4, v, RULES) if v is not None else p45.c2_row(0.4, None, RULES))
            for i, v in enumerate(vals)}


def test_outcomes():
    assert p45.outcome(_rows([0.9] * 5), 5) == "A"
    assert p45.outcome(_rows([0.9, 0.9, 0.9, None, None]), 5) == "A3"
    assert p45.outcome(_rows([0.9, 0.9, None, None, None]), 5) == "N"
    assert p45.outcome(_rows([0.9, 0.7, 0.9, 0.9, 0.9]), 5) == "B"
    assert p45.outcome(_rows([0.7] * 5), 5) == "C"
    assert p45.outcome(_rows([0.7, 0.7, 0.7, None, None]), 5) == "C"
    assert p45.outcome(_rows([0.7, None, None, None, None]), 5) == "C_partial"


def test_parse_run():
    assert p45.parse_run("E-ball-s2-labelshuf") == ("E", "all", 2, True)
    assert p45.parse_run("E-ball-s0") == ("E", "all", 0, False)


def test_check_out(tmp_path):
    d = tmp_path / "derived"
    assert p45.check_out(d / "p15-45", d)
    assert p45.check_out(d / "p15-45" / "x", d)
    assert not p45.check_out(d / "p15-08", d)
    assert not p45.check_out(d / "p15-43" / "runs", d)
    assert not p45.check_out(d, d)
    assert p45.check_out(tmp_path / "scratch", d)


def test_config_matches_plan():
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    assert cfg["seeds"] == [0, 1, 2, 3, 4] and cfg["budget"] == "all" and cfg["arm"] == "E"
    assert cfg["rules"] == RULES
    names = cfg["new_runs_in_order"]
    assert sorted(names) == sorted([f"E-ball-s{s}-labelshuf" for s in range(5)] + [f"E-ball-s{s}" for s in (2, 3, 4)])
    assert set(cfg["sources"]["normal_test_reused"]) == {"E-ball-s0", "E-ball-s1"}
    rec = json.loads((HERE.parent / "2026-11-19-p15-08-e1-cross-body" / "config.json").read_text(encoding="utf-8"))
    assert rec["finetune"]["steps"]["all"] == cfg["steps"]
