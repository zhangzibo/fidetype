"""Pool scope and safety findings on the score cards and the leaderboard (2026-11-25).

The bound of a CRC / LTT entry covers its whole pooled test set, not each user, session or day
(docs/trust-guarantee.md section 4). Every committed card with a bound says so in its scope line. Two
safety findings of the pooled-guard check are recorded on the cards (key ``safety_findings``) and shown
on the leaderboard. No number changes.
"""

from __future__ import annotations

import json
from pathlib import Path

from fidetype.benchmark import leaderboard as LB

ROOT = Path(__file__).resolve().parents[1]
RESULTS = [ROOT / "benchmark/results/v0.1", ROOT / "benchmark/results/v0.2"]


def _cards() -> dict[str, dict]:
    return {f"{p.parent.name}/{p.name}": json.loads(p.read_text(encoding="utf-8"))
            for d in RESULTS for p in sorted(d.glob("*.json"))}


def test_every_bounded_card_states_the_pool_scope():
    n = 0
    for name, c in _cards().items():
        g = c.get("guarantee") or {}
        if g.get("method", "none") == "none":
            continue
        n += 1
        assert "the bound covers the pool" in g["scope"], name
        assert "trust-guarantee.md#4-what-is-not-guaranteed" in g["scope"], name
    assert n >= 28


def test_safety_findings_on_the_flagged_cards():
    cards = _cards()
    for v, stem in (("v0.1", "spanishbcbl-meg-async"), ("v0.2", "spanishbcbl-meg")):
        for m in ("crc", "ltt"):
            f = cards[f"{v}/{stem}__convctc-m-async__{m}.json"]["safety_findings"]
            assert [x["kind"] for x in f] == ["label-blind-commit-step"]
            assert f[0]["mark"] == "LABEL-BLIND COMMIT STEP: no evidence of signal" and not f[0]["numbers_changed"]
    for v, stem in (("v0.1", "b2t25-t15-copytask"), ("v0.2", "b2t25-t15")):
        for m in ("crc", "ltt"):
            c = cards[f"{v}/{stem}__published__{m}.json"]
            f = c["safety_findings"]
            assert [x["kind"] for x in f] == ["per-day-exceedance"]
            rows = f[0]["per_group"]["rows"]
            assert sum(r["n"] for r in rows) == c["n_trials"] == 816
            assert sum(r["wrong"] for r in rows) == c["safe_wpm"]["n_wrong_commits"]
            above = [r for r in rows if r["cp_lower"] > f[0]["per_group"]["alpha"]]
            assert [(r["group"], r["wrong"], r["n"]) for r in above] == [("day034", 9, 50)]
    flagged = {k for k, c in cards.items() if c.get("safety_findings")}
    assert len(flagged) == 8


def test_leaderboard_shows_pool_scope_and_findings():
    by = LB.build_rows(LB.load_results(RESULTS))
    row = next(r for r in by["b2t25-t15"] if r["file"] == "b2t25-t15__published__crc.json")
    assert row["guarantee"].endswith("[SAFETY FINDING: one day above alpha]")
    meg = next(r for r in by["spanishbcbl-meg"] if r["file"] == "spanishbcbl-meg__convctc-m-async__crc.json")
    assert "[LABEL-BLIND COMMIT STEP: no evidence of signal]" in meg["guarantee"]
    plain = next(r for r in by["toronto-semg"] if r["file"] == "toronto-semg__cnn-calib__crc.json")
    assert "[" not in plain["guarantee"] and plain["safety_findings"] == []
    md = LB.markdown(by)
    assert LB.POOL_SCOPE_NOTE in md and "| day034 | 50 | 24 | 9 | 0.180 |" in md
    h = LB.findings_html(row)
    assert 'class="finding"' in h and '<td class="bad">day034</td>' in h
    assert LB.findings_html(plain) == ""
