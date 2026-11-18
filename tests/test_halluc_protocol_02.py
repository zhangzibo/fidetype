"""Tests of hallucination benchmark protocol 0.2 (P15-15): the paired swapped / real commit-ratio rule.

No raw data: unit tests on flag strings and a re-score of the committed outcome files (flags only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.benchmark import hallucination as HB
from fidetype.utils.binomial import clopper_pearson, cp_lower, cp_upper

REPO = Path(__file__).resolve().parents[1]
V01 = REPO / "benchmark" / "results" / "halluc-v0.1"
V02 = REPO / "benchmark" / "results" / "halluc-v0.2"


def _flags(n10: int, n01: int, n11: int, n00: int) -> tuple[str, str]:
    real = "1" * n10 + "0" * n01 + "1" * n11 + "0" * n00
    swap = "0" * n10 + "1" * n01 + "1" * n11 + "0" * n00
    return real, swap


def _outcomes(n10: int, n01: int, n11: int, n00: int, null_commits: int = 0) -> dict:
    real, swap = _flags(n10, n01, n11, n00)
    n = len(real)
    nul = "1" * null_commits + "0" * (20 - null_commits)
    return {"schema": HB.OUTCOMES_SCHEMA, "protocol": HB.PROTOCOL, "dataset": "toy", "system": "toy",
            "fluency": {"mode": "conservative"}, "meta": {},
            "tracks": {"real": {"n": n, "committed": real, "wrong": "0" * n, "fluent": "-" * n},
                       "null": {"n": 20, "committed": nul, "wrong": nul, "fluent": nul.replace("0", "-")},
                       "scrambled": {"n": 20, "committed": "0" * 20, "wrong": "0" * 20, "fluent": "-" * 20},
                       "swapped": {"n": n, "committed": swap, "wrong": swap, "fluent": swap.replace("0", "-"),
                                   "leak": "0" * n}}}


def test_cp_lower_matches_two_sided_interval():
    assert cp_lower(0, 10, 0.05) == 0.0 and cp_lower(3, 0, 0.05) == 0.0
    assert abs(cp_lower(10, 10, 0.05) - 0.05 ** (1 / 10)) < 1e-9
    lo, hi = clopper_pearson(7, 30, level=0.9, ndigits=None)
    assert abs(cp_lower(7, 30, 0.05) - lo) < 1e-12 and abs(cp_upper(7, 30, 0.05) - hi) < 1e-12


def test_pre_registered_constants():
    assert (HB.SWAP_RATIO_MAX, HB.SWAP_ALPHA, HB.SWAP_M_MIN) == (0.5, 0.05, 25)
    assert HB.PROTOCOL == HB.PROTOCOL_V02 == "fidetype.halluc/0.2"
    # M_MIN: at m = 25 the rule passes with Y <= 4 and not with Y = 5; no pass is possible below m = 8
    th = HB.SWAP_RATIO_MAX / (1 + HB.SWAP_RATIO_MAX)
    assert cp_upper(4, 25, 0.05) < th <= cp_upper(5, 25, 0.05)
    assert cp_upper(0, 7, 0.05) >= th > cp_upper(0, 8, 0.05)


def test_signal_checking_system_passes():
    pr = HB.paired_swap_test(*_flags(n10=40, n01=1, n11=0, n00=60))
    assert pr["verdict"] == HB.PASS and pr["m"] == 41 and pr["Y"] == 1
    assert pr["ratio_estimate"] == pytest.approx(1 / 40)


def test_rarely_committing_system_without_signal_check_does_not_pass():
    # the P15-07 T15 P14-03 pattern: 2 real commits, the same number of swapped commits
    pr = HB.paired_swap_test(*_flags(n10=2, n01=2, n11=0, n00=697))
    assert pr["verdict"] == HB.INSUFFICIENT
    card = HB.score_outcomes(_outcomes(2, 2, 0, 697))
    assert not card["controls_passed"] and card["controls_verdict"] == HB.INSUFFICIENT
    assert card["tracks"]["swapped"]["pass_v01_rule"]  # the old rule passed it
    assert HB.score_outcomes(_outcomes(2, 2, 0, 697), protocol="0.1")["controls_passed"]


def test_never_committing_system_is_insufficient_not_pass():
    pr = HB.paired_swap_test("0" * 400, "0" * 400)
    assert pr["verdict"] == HB.INSUFFICIENT and pr["m"] == 0 and pr["ratio_estimate"] is None


def test_frequent_system_without_signal_check_fails():
    pr = HB.paired_swap_test(*_flags(n10=24, n01=24, n11=1, n00=351))
    assert pr["verdict"] == HB.FAIL and pr["m"] >= HB.SWAP_M_MIN


def test_small_m_with_clear_evidence_fails():
    # only swapped commits: n01 / m lower bound > 1/3 already at m = 6
    pr = HB.paired_swap_test(*_flags(n10=0, n01=6, n11=0, n00=50))
    assert pr["m"] < HB.SWAP_M_MIN and pr["verdict"] == HB.FAIL


def test_rule_is_conservative_for_concordant_commits():
    # n11 counts in Y: a system that commits both ways on the same signal cannot pass on n11 alone
    pr = HB.paired_swap_test(*_flags(n10=10, n01=0, n11=30, n00=0))
    assert pr["ratio_estimate"] == pytest.approx(30 / 40) and pr["verdict"] == HB.FAIL


def test_controls_verdict_combines_tracks():
    good = HB.score_outcomes(_outcomes(40, 0, 0, 60))
    assert good["controls_verdict"] == HB.PASS and good["controls_passed"]
    assert good["schema"] == HB.SCORECARD_SCHEMA and good["protocol"] == HB.PROTOCOL_V02
    assert good["headline"]["swapped_verdict"] == HB.PASS
    bad_null = HB.score_outcomes(_outcomes(40, 0, 0, 60, null_commits=5))
    assert bad_null["tracks"]["null"]["verdict"] == HB.FAIL and bad_null["controls_verdict"] == HB.FAIL
    # fail wins over insufficient evidence
    mixed = HB.score_outcomes(_outcomes(0, 0, 0, 100, null_commits=5))
    assert mixed["tracks"]["swapped"]["verdict"] == HB.INSUFFICIENT and mixed["controls_verdict"] == HB.FAIL


def test_protocol_names_and_errors():
    assert HB.protocol_name("0.1") == HB.PROTOCOL_V01 and HB.protocol_name(HB.PROTOCOL_V02) == HB.PROTOCOL_V02
    with pytest.raises(ValueError):
        HB.protocol_name("0.3")
    with pytest.raises(ValueError):
        HB.paired_swap_test("10", "1")
    oc = _outcomes(1, 1, 0, 3)
    del oc["tracks"]["real"]
    with pytest.raises(ValueError):
        HB.score_outcomes(oc)


def test_cli_protocol_flag(tmp_path):
    p = tmp_path / "oc.json"
    p.write_text(json.dumps(_outcomes(2, 2, 0, 50)), encoding="utf-8")
    assert HB.main(["rescore", str(p), "--out", str(tmp_path / "c2.json")]) == 0
    assert HB.main(["rescore", str(p), "--protocol", "0.1", "--out", str(tmp_path / "c1.json")]) == 0
    c2 = json.loads((tmp_path / "c2.json").read_text(encoding="utf-8"))
    c1 = json.loads((tmp_path / "c1.json").read_text(encoding="utf-8"))
    assert c2["protocol"] == HB.PROTOCOL_V02 and c2["controls_verdict"] == HB.INSUFFICIENT
    assert c1["protocol"] == HB.PROTOCOL_V01 and c1["controls_passed"] and "controls_verdict" not in c1


# --- committed protocol 0.2 cards: the scorer reproduces each one from its committed outcomes (CI) ---------


CARDS_V02 = sorted(V02.glob("*.card.json"))


def _assert_same(a, b, path="card"):
    """Equal, except that floats may differ in the last bits (the CP bisection runs on other platforms in CI)."""
    if isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-12), path
    elif isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a:
            _assert_same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_same(x, y, f"{path}[{i}]")
    else:
        assert a == b, path


def _outcomes_for(card: dict, card_path: Path) -> dict:
    rel = card["meta"]["outcomes_file"]
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def test_v02_cards_cover_all_v01_entries():
    stems01 = {p.name[: -len(".outcomes.json")] for p in V01.glob("*.outcomes.json")}
    stems02 = {p.name[: -len(".card.json")] for p in CARDS_V02}
    assert len(stems01) == 12 and stems01 <= stems02


@pytest.mark.parametrize("path", CARDS_V02, ids=[p.name for p in CARDS_V02])
def test_v02_cards_reproduce(path):
    ref = json.loads(path.read_text(encoding="utf-8"))
    assert ref["protocol"] == HB.PROTOCOL_V02 and ref["schema"] == HB.SCORECARD_SCHEMA
    oc = _outcomes_for(ref, path)
    r = ref["rules"]
    card = HB.score_outcomes(oc, alpha_wrong=r["alpha_wrong"], alpha_fluent=r["alpha_fluent"],
                             swap_ratio_max=r["swap_ratio_max"], swap_alpha=r["swap_alpha"], swap_m_min=r["swap_m_min"])
    card["meta"] = {**card["meta"], "outcomes_file": ref["meta"]["outcomes_file"]}
    _assert_same(json.loads(json.dumps(card)), ref)


def test_v02_verdicts_of_p15_07_baselines():
    """The pre-registered expectation (plan.md): no P15-07 baseline passes the swapped track under 0.2."""
    for p in CARDS_V02:
        c = json.loads(p.read_text(encoding="utf-8"))
        if "halluc-v0.1/" in c["meta"]["outcomes_file"]:
            assert c["tracks"]["swapped"]["verdict"] in (HB.FAIL, HB.INSUFFICIENT), p.name
