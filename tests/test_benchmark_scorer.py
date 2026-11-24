"""Submission format v0.2 + one-command scorer (P6-02), on synthetic fixtures only (no raw data)."""

from __future__ import annotations

import json

import pytest

from fidetype.benchmark import scorecard as SC
from fidetype.benchmark import tracks as TR
from fidetype.benchmark.registry import keycodes_to_chars, normalize
from fidetype.benchmark.submission import SubmissionError


def _kt_fixture(root, n_runs=10):
    """Same layout as tests/test_benchmark_tracks.py: 10 runs, 3 bursts each (cal 3 runs, test 6 runs)."""
    root.mkdir()
    for r in range(1, n_runs + 1):
        t0 = 1_600_000_000.0 + r * 10_000
        (root / f"run{r}_ts.txt").write_text(f"2020-09-{r:02d} 10:00:00.000", encoding="ascii")
        lines, t = [], t0 + 5
        for burst in range(3):
            for ch in "hello world"[: 6 + burst]:
                lines.append(f"{ch} {t:.6f}")
                t += 0.3
            t += 5.0
        (root / f"run{r}_keys.txt").write_bytes(("\n".join(lines) + "\n").encode("latin-1"))
        (root / f"run{r}.csv").write_text("Time\tc1\n0\t1\n", encoding="ascii")
    return root


@pytest.fixture()
def kt(tmp_path, monkeypatch):
    """A synthetic KT-sEMG copy, its split (monkeypatched in), and the truth rows from `build_truth`."""
    root = _kt_fixture(tmp_path / "kt")
    split = TR.make_split("kt-semg", TR.local_units("kt-semg", root))
    monkeypatch.setattr(TR, "load_split", lambda track: split)
    rows = SC.build_truth("kt-semg", root)
    return root, split, rows


def _manifest(**kw):
    d = dict(decoder={"name": "unit-test", "weights_licence": "MIT"}, policy={"name": "half"}, regime="cross-session",
             controls={"shuffled": "frames permuted", "zeros": "all-zero EMG"})
    d.update(kw)
    return SC.manifest_dict("kt-semg", **d)


def _rows(truth, wrong_every=2, action_wrong="offer"):
    out = []
    for k, r in enumerate(truth):
        ok = k % wrong_every == 0
        hyp = r["text"] if ok else " ".join(["KeyX"] * len(r["text"].split()))
        out.append(SC.unit_row(r["unit"], [hyp, r["text"]], [-0.1, -2.0], action="commit" if ok else action_wrong,
                               latency_s=0.2))
    return out


def _null_rows(truth, action="abstain"):
    return [SC.unit_row(r["unit"], ["KeyQ KeyQ"], [-9.0], action=action) for r in truth]


# ---------------------------------------------------------------------------


def test_keycodes_normalizer():
    assert keycodes_to_chars("KeyH KeyI Space Period Backspace") == "hi .⌫"
    assert normalize("KeyA  KeyB", "keycodes") == "ab"
    assert normalize("Foo ?", "keycodes") == "��"
    assert set(SC.SCORE_SPECS) == set(TR.TRACKS)
    for slug in TR.TRACKS:
        t = SC.scoring_track(slug)
        assert t.user_model.config["chars_per_min"] > 0
    assert SC.scoring_track("spanishbcbl-meg").ci_unit == "two_way:sentence,group"


def test_truth_rows_match_split(kt, tmp_path):
    root, split, rows = kt
    assert len(rows) == 6 * 3 and all(r["neural_s"] > 0 for r in rows)
    p = tmp_path / "truth.jsonl"
    SC.write_truth(p, "kt-semg", rows)
    truth = SC.read_truth(p, "kt-semg", split)
    assert set(truth) == {r["unit"] for r in rows}
    # A changed truth text breaks the fingerprint check.
    bad = [dict(r) for r in rows]
    bad[0]["payload"] = "KeyZ " + bad[0]["payload"]
    SC.write_truth(p, "kt-semg", bad)
    with pytest.raises(SubmissionError):
        SC.read_truth(p, "kt-semg", split)


def test_full_score_card_with_controls(kt, tmp_path):
    _, split, rows = kt
    truth = {r["unit"]: r for r in rows}
    sub = SC.write_submission(tmp_path / "sub", _manifest(), _rows(rows),
                              {"shuffled": _null_rows(rows), "zeros": _null_rows(rows)})
    rep = SC.check_submission("kt-semg", sub, split)
    assert rep["ok"] and rep["controls_complete"] and not rep["coverage"]["partial"]
    res = SC.score("kt-semg", sub, truth, B=200, split=split)
    m = res["metrics"]
    assert res["status"] == "scored" and res["controls"]["passed"]
    assert m["commit_rate"]["value"] == pytest.approx(0.5) and m["wrong_commit_rate"]["value"] == 0
    assert m["key_error_rate"]["value"] == m["cer"]["value"] > 0
    assert m["ewpm"]["ci"] is not None and m["gaze_ewpm"]["value"] > 0
    assert res["safe_wpm"]["status"] == "not-certified" and res["certification"] == "not-certified"
    assert res["coverage"] == {"n_scored_units": 18, "n_covered": 18, "partial": False}
    assert res["latency"]["median_s"] == pytest.approx(0.2) and res["timing"].startswith("measured")
    assert res["schema"] == SC.RESULT_SCHEMA_V02 and res["ci"]["unit_name"] == "run"
    assert "kt-semg" in SC.score_card_text(res)
    # No truth text in the card.
    blob = json.dumps(res)
    assert not any(r["payload"] in blob for r in rows)


def test_certified_guarantee_and_failed_null_control(kt, tmp_path):
    _, split, rows = kt
    truth = {r["unit"]: r for r in rows}
    g = {"method": "ltt", "alpha": 0.05, "delta": 0.1, "n_cal": 9, "scope": "marginal over test units",
         "calibration_split": "cal"}
    sub = SC.write_submission(tmp_path / "sub", _manifest(guarantee=g), _rows(rows),
                              {"shuffled": _null_rows(rows), "zeros": _null_rows(rows, action="commit")})
    res = SC.score("kt-semg", sub, truth, B=100, split=split)
    assert res["safe_wpm"]["status"] == "certified" and res["safe_wpm"]["value"] > 0
    # The headline block is the adopted safe-wpm/0.2 (with the reading cost); v0.1 keeps its key and label.
    v1, v2 = res["safe_wpm"], res["safe_wpm_v02"]
    assert v1["definition"] == "safe-wpm/0.1" and v2["definition"] == "safe-wpm/0.2"
    assert v2["adopted_headline"] is True and res["safe_wpm_headline"] == "safe_wpm_v02"
    assert v2["status"] == v1["status"] == res["certification"] and 0 < v2["value"] < v1["value"]
    assert v2["reading_cost"]["minutes_reading"] > 0
    assert res["rerun"]["scorer"]["metrics"] == {"safe_wpm": "safe-wpm/0.1", "safe_wpm_v02": "safe-wpm/0.2"}
    assert "safe WPM v0.2" in SC.score_card_text(res)
    assert res["controls"]["null_commit"]["status"] == "fail"
    assert res["status"] == "scored: controls failed"


def test_missing_controls_and_partial_coverage(kt, tmp_path):
    _, split, rows = kt
    truth = {r["unit"]: r for r in rows}
    sub = SC.write_submission(tmp_path / "sub", _manifest(), _rows(rows))
    res = SC.score("kt-semg", sub, truth, B=50, split=split)
    assert res["status"] == "scored: controls missing" and res["controls"]["shuffled"]["status"] == "missing"
    # Missing units are refused unless the manifest declares a subset.
    part = SC.write_submission(tmp_path / "part", _manifest(), _rows(rows)[:10])
    with pytest.raises(SubmissionError, match="no output"):
        SC.check_submission("kt-semg", part, split)
    part2 = SC.write_submission(tmp_path / "part2", _manifest(coverage={"subset": "decoder output exists for 10"}),
                                _rows(rows)[:10])
    res = SC.score("kt-semg", part2, truth, B=50, split=split)
    assert res["coverage"]["partial"] and res["coverage"]["n_covered"] == 10 and res["n_trials"] == 10


def test_rejections(kt, tmp_path):
    _, split, rows = kt
    good = _rows(rows)
    # Unknown unit hash.
    bad = [dict(good[0], unit="0" * 16)] + good[1:]
    sub = SC.write_submission(tmp_path / "a", _manifest(), bad)
    with pytest.raises(SubmissionError, match="not scored units"):
        SC.check_submission("kt-semg", sub, split)
    # A truth-like field in a row.
    sub = SC.write_submission(tmp_path / "b", _manifest(), [dict(good[0], truth="x")] + good[1:])
    with pytest.raises(SubmissionError, match="not allowed"):
        SC.check_submission("kt-semg", sub, split)
    # Duplicate unit.
    sub = SC.write_submission(tmp_path / "c", _manifest(), good + [good[0]])
    with pytest.raises(SubmissionError, match="duplicate"):
        SC.check_submission("kt-semg", sub, split)
    # Sub-unit keys on a track without sub-units.
    sub = SC.write_submission(tmp_path / "d", _manifest(), [dict(r, unit=r["unit"] + "#0") for r in good])
    with pytest.raises(SubmissionError, match="unit keys"):
        SC.check_submission("kt-semg", sub, split)
    # Manifest errors.
    with pytest.raises(SubmissionError, match="regime"):
        _manifest(regime="magic")
    with pytest.raises(SubmissionError, match="weights_licence"):
        _manifest(decoder={"name": "x"})
    with pytest.raises(SubmissionError, match="track"):
        SC.parse_manifest({**_manifest(), "track": "b2t25-t15-copytask"})


def test_cli_check_truth_score(kt, tmp_path, capsys, monkeypatch):
    from fidetype.benchmark.__main__ import main

    root, split, rows = kt
    sub = SC.write_submission(tmp_path / "sub", _manifest(), _rows(rows),
                              {"shuffled": _null_rows(rows), "zeros": _null_rows(rows)})
    assert main(["check", "kt-semg", str(sub)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    truth = tmp_path / "truth.jsonl"
    assert main(["truth", "kt-semg", "--data", str(root), "--out", str(truth)]) == 0
    card = tmp_path / "card.json"
    assert main(["score", "kt-semg", str(sub), "--truth", str(truth), "--out", str(card), "--B", "50"]) == 0
    assert json.loads(card.read_text(encoding="utf-8"))["status"] == "scored"
    assert main(["score", "kt-semg", str(sub), "--data", str(root), "--B", "50"]) == 0
    capsys.readouterr()
    # Controls missing -> exit code 1; a rejected submission -> exit code 2.
    sub2 = SC.write_submission(tmp_path / "sub2", _manifest(), _rows(rows))
    assert main(["score", "kt-semg", str(sub2), "--truth", str(truth), "--B", "20"]) == 1
    sub3 = SC.write_submission(tmp_path / "sub3", _manifest(), _rows(rows)[:3])
    assert main(["score", "kt-semg", str(sub3), "--truth", str(truth), "--B", "20"]) == 2
    assert main(["check", "kt-semg", str(sub3)]) == 2


def test_stream_submission_and_board(kt, tmp_path):
    """NTS stream files (v0.1 hypothesis-event rules) are a valid v0.2 submission too; the board shows the entry."""
    import numpy as np

    from fidetype.adapters import kt_semg as K
    from fidetype.benchmark.leaderboard import build
    from fidetype.benchmark.submission import write_trial

    _, split, rows = kt
    truth = {r["unit"]: r for r in rows}
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "submission.json").write_text(json.dumps(_manifest(regime="session-calibrated")), encoding="utf-8")
    for r in rows:
        codes = r["text"].split()
        lp = np.full((len(codes), len(K.KEY_VOCAB)), -5.0)
        for i, c in enumerate(codes):
            lp[i, K.KEY_VOCAB.index(c)] = 0.0
        st = K.keypress_stream(lp, np.arange(len(codes)) * 0.3)
        write_trial(sub / "streams" / f"{r['unit']}.jsonl", st, [r["text"]], [0.0], action="commit")
    res = SC.score("kt-semg", sub, truth, B=50, split=split)
    assert res["check"]["format"] == "nts-streams" and res["metrics"]["cer"]["value"] == 0
    assert res["conformance"]["n_files"] == len(rows)
    out = tmp_path / "res"
    out.mkdir()
    (out / "e.json").write_text(json.dumps(SC_jsonable(res)), encoding="utf-8")
    info = build([out], tmp_path / "site")
    page = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert info["tracks"]["kt-semg"] == 1 and "unit-test" in page and "key error rate" in page


def SC_jsonable(res):
    from fidetype.benchmark.scoring import to_jsonable

    return to_jsonable(res)


def test_committed_v02_results_are_clean():
    """Committed v0.2 score cards: schema, licence flags, no unit hashes of text, research-only marked."""
    from pathlib import Path

    d = Path(__file__).resolve().parents[1] / "benchmark" / "results" / "v0.2"
    if not d.exists():
        pytest.skip("no committed v0.2 results")
    files = sorted(d.glob("*.json"))
    assert files
    for p in files:
        r = json.loads(p.read_text(encoding="utf-8"))
        assert r["schema"] == SC.RESULT_SCHEMA_V02 and r["track"] in TR.TRACKS
        assert r["track_info"]["research_only"] == TR.get_track(r["track"]).research_only
        assert r["decoder"].get("weights_licence")
        for k in ("cer", "ewpm", "gaze_ewpm", "wrong_commit_rate", "error_among_commits", "commit_rate"):
            assert k in r["metrics"]
        assert {"shuffled", "zeros", "null_commit", "passed"} <= set(r["controls"])
        if r["track_info"]["research_only"]:
            assert any("RESEARCH ONLY" in n for n in r["notes"])


def test_sub_unit_keys(kt, tmp_path, monkeypatch):
    """emg2qwerty-style keys '<parent h>#<k>': coverage per parent, scoring per sub-unit, truth checked per parent."""
    from dataclasses import replace

    _, split, rows = kt
    monkeypatch.setitem(SC.SCORE_SPECS, "kt-semg", replace(SC.SCORE_SPECS["kt-semg"], sub_units=True))
    sub_rows = [dict(r, unit=f"{r['unit']}#{k}") for r in rows for k in (0, 3)]
    p = tmp_path / "truth.jsonl"
    SC.write_truth(p, "kt-semg", sub_rows)
    truth = SC.read_truth(p, "kt-semg", split)
    assert len(truth) == 36
    sub = SC.write_submission(tmp_path / "sub", _manifest(), _rows(sub_rows),
                              {"shuffled": _null_rows(sub_rows), "zeros": _null_rows(sub_rows)})
    res = SC.score("kt-semg", sub, truth, B=50, split=split)
    assert res["n_trials"] == 36 and res["status"] == "scored"
    # Plain hashes are refused on a sub-unit track; a missing prompt is refused without a declared subset.
    with pytest.raises(SubmissionError, match="unit keys"):
        SC.check_submission("kt-semg", SC.write_submission(tmp_path / "b", _manifest(), _rows(rows)), split)
    short = SC.write_submission(tmp_path / "c", _manifest(), _rows(sub_rows)[:-1])
    with pytest.raises(SubmissionError, match="no output"):
        SC.score("kt-semg", short, truth, B=20, split=split)


# ---------------------------------------------------------------------------
# Scoring targets (P11-13): raw_keys (default) and intended_text (Backspace applied)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("codes, want", [
    ("KeyH KeyI", "hi"),
    ("Backspace KeyH KeyI", "hi"),                        # leading Backspace: nothing to remove
    ("Backspace Backspace Backspace", ""),                # only Backspaces
    ("KeyH KeyX KeyX Backspace Backspace KeyI", "hi"),     # several Backspaces in a row
    ("KeyH KeyI Backspace Backspace Backspace KeyO", "o"),  # more Backspaces than characters
    ("KeyH KeyI Space Backspace KeyO", "hio"),            # Backspace removes the word-boundary space
    ("KeyH KeyI Space KeyX Backspace KeyO", "hi o"),      # Backspace just after a word boundary
    ("KeyH KeyI Space Space Enter KeyO Space", "hi o"),   # Enter ignored, spaces joined, ends stripped
    ("Space Space KeyA", "a"),
    ("KeyA Foo Backspace KeyB", "ab"),                    # an unknown code is a character; Backspace removes it
    ("", ""),
])
def test_intended_text_rule(codes, want):
    from fidetype.benchmark.registry import INTENDED_TEXT_RULE, keycodes_to_intended_text

    assert INTENDED_TEXT_RULE == "intended-text/1"
    assert keycodes_to_intended_text(codes) == want
    assert normalize(codes, "keycodes_intended") == want


def test_intended_text_rule_equals_the_p11_11_resolve():
    """The library rule is the same as the experiment rule that P11-11 / P11-12 used (no second variant).

    Only ``resolve`` and its two constants are taken from the runner (via ``ast``): importing the whole runner
    would change process-wide settings (thread counts, visible GPUs)."""
    import ast
    import random
    from pathlib import Path

    from fidetype.adapters import emg2qwerty as A
    from fidetype.benchmark.registry import keycodes_to_intended_text

    f = Path(__file__).resolve().parents[1] / "experiments" / "2026-11-19-p11-11-emg-nonvacuous" / "run.py"
    if not f.is_file():
        pytest.skip("P11-11 runner not present")
    tree = ast.parse(f.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == "resolve") or (
        isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("BS_CHAR", "EN_CHAR") for t in n.targets))]
    assert len(keep) == 3
    ns: dict = {"A": A}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(f), "exec"), ns)
    resolve = ns["resolve"]
    rng = random.Random(0)
    heavy = list(A.KEY_VOCAB) + ["Backspace"] * 8 + ["Space"] * 6 + ["Enter"] * 2
    for _ in range(2000):
        codes = " ".join(rng.choice(heavy) for _ in range(rng.randint(0, 25)))
        assert keycodes_to_intended_text(codes) == resolve(A.codes_to_key_text(codes)), codes


def _bs_truth(rows):
    """Truth rows with a leading Backspace and a typo + Backspace after the first key (the raw text changes)."""
    out = {}
    for r in rows:
        c = r["text"].split()
        out[r["unit"]] = dict(r, text=" ".join(["Backspace", c[0], "KeyQ", "Backspace", *c[1:]]))
    return out


def _target_spec(monkeypatch):
    from dataclasses import replace

    monkeypatch.setitem(SC.SCORE_SPECS, "kt-semg",
                        replace(SC.SCORE_SPECS["kt-semg"], targets=("raw_keys", "intended_text")))


def test_default_target_scores_exactly_as_before(kt, tmp_path, monkeypatch):
    """Regression: a manifest without a target scores exactly as before the target option existed; declaring
    raw_keys gives the same numbers plus the target block."""
    _, split, rows = kt
    truth = _bs_truth(rows)
    rws = _rows(list(truth.values()))
    ctl = {"shuffled": _null_rows(rows), "zeros": _null_rows(rows)}
    before = SC.score("kt-semg", SC.write_submission(tmp_path / "a", _manifest(), rws, ctl), truth, B=100, split=split)
    _target_spec(monkeypatch)
    after = SC.score("kt-semg", SC.write_submission(tmp_path / "a", _manifest(), rws, ctl), truth, B=100, split=split)
    assert json.dumps(SC_jsonable(before), sort_keys=True) == json.dumps(SC_jsonable(after), sort_keys=True)
    assert "target" not in after
    raw = SC.score("kt-semg", SC.write_submission(tmp_path / "b", _manifest(target="raw_keys"), rws, ctl), truth,
                   B=100, split=split)
    assert raw["target"]["name"] == "raw_keys" and raw["target"]["version"] == "raw-keys/1"
    for k in ("metrics", "controls", "safe_wpm", "guarantee", "n_trials", "status"):
        assert SC_jsonable(raw[k]) == SC_jsonable(after[k]), k
    assert raw["rerun"]["scorer"]["target"] == "raw-keys/1"


def test_intended_text_target(kt, tmp_path, monkeypatch):
    from fidetype.benchmark.registry import keycodes_to_intended_text

    _, split, rows = kt
    truth = _bs_truth(rows)
    _target_spec(monkeypatch)
    g = {"method": "ltt", "alpha": 0.05, "delta": 0.1, "n_cal": 9, "scope": "marginal", "calibration_split": "cal"}
    ctl = {"shuffled": _null_rows(rows), "zeros": _null_rows(rows)}
    # Commit the intended text (no Backspace) for every unit.
    rws = [SC.unit_row(r["unit"], [r["text"]], action="commit") for r in rows]
    raw = SC.score("kt-semg", SC.write_submission(tmp_path / "r", _manifest(guarantee=g), rws, ctl), truth, B=50,
                   split=split)
    it = SC.score("kt-semg", SC.write_submission(tmp_path / "i", _manifest(guarantee=g, target="intended_text"), rws,
                                                 ctl), truth, B=50, split=split)
    # Raw-key scoring calls every intended-text commit wrong; intended-text scoring calls every one right.
    assert raw["metrics"]["wrong_commit_rate"]["value"] == 1.0
    assert it["metrics"]["wrong_commit_rate"]["value"] == 0.0 and it["metrics"]["cer"]["value"] == 0.0
    assert it["target"] == SC.target_block("intended_text") and "key_error_rate" not in it["metrics"]
    assert it["safe_wpm"]["status"] == "certified" and it["safe_wpm"]["value"] > 0
    # The no-BCI reference is gaze typing of the INTENDED text (fewer characters than the raw keys).
    nw = sum(len(keycodes_to_intended_text(r["text"]).split()) for r in truth.values())
    nc = sum(len(keycodes_to_intended_text(r["text"])) for r in truth.values())
    assert it["metrics"]["gaze_ewpm"]["value"] == pytest.approx(nw / (nc / 20.0))
    assert it["safe_wpm"]["total_words"] == nw
    assert it["metrics"]["gaze_ewpm"]["value"] != raw["metrics"]["gaze_ewpm"]["value"]
    # A raw-key output (leading Backspace, typo + Backspace kept) is also right under the intended-text target.
    rk = [SC.unit_row(u, [r["text"]], action="commit") for u, r in truth.items()]
    it2 = SC.score("kt-semg", SC.write_submission(tmp_path / "k", _manifest(guarantee=g, target="intended_text"), rk,
                                                  ctl), truth, B=50, split=split)
    assert it2["metrics"]["wrong_commit_rate"]["value"] == 0.0
    assert "target intended_text" in SC.score_card_text(it)


def test_target_validation(monkeypatch):
    with pytest.raises(SubmissionError, match="one target"):
        _manifest(target="intended_text")  # kt-semg has a single target
    assert SC.SCORE_SPECS["emg2qwerty"].targets == ("raw_keys", "intended_text")
    assert SC.resolve_target("emg2qwerty", None) == "raw_keys"
    assert SC.resolve_target("b2t25-t15", None) is None
    _target_spec(monkeypatch)
    with pytest.raises(SubmissionError, match="not valid"):
        _manifest(target="intended")
    assert SC.parse_manifest(_manifest(target="intended_text")).target == "intended_text"


def test_leaderboard_separates_targets():
    from fidetype.benchmark import leaderboard as LB

    def card(name, target=None, ewpm=1.0):
        d = {"track": "emg2qwerty", "decoder": {"name": name}, "policy": {"name": "p"}, "_file": f"{name}.json",
             "metrics": {"ewpm": {"value": ewpm}, "gaze_ewpm": {"value": 3.0 if target else 2.9}}}
        if target:
            d["target"] = SC.target_block(target)
        return d

    old = [LB.row(card("a")), LB.row(card("b", "raw_keys"))]
    assert LB.target_groups("emg2qwerty", old) == [(None, old)]  # only the default: one table, as before
    rows = old + [LB.row(card("c", "intended_text", ewpm=9.0))]
    groups = LB.target_groups("emg2qwerty", rows)
    assert [g for g, _ in groups] == ["raw_keys", "intended_text"]
    assert [r["decoder"] for r in groups[1][1]] == ["c [target: intended_text]"]
    assert all("target" not in r["decoder"] for r in groups[0][1])
    md = "\n".join(LB._md_track("emg2qwerty", rows))
    assert "Target intended_text (intended-text/1)" in md and md.count("No-BCI reference") == 2
    assert LB._board_tables("emg2qwerty", rows, "").count("<table>") == 2
