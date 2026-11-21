"""Train / test overlap check of benchmark entries (P6-10, gap 33). Synthetic data and committed hash files only."""

from __future__ import annotations

import json

import pytest

from fidetype.benchmark import leaderboard as LB
from fidetype.benchmark import overlap as OV
from fidetype.benchmark import scorecard as SC
from fidetype.benchmark import tracks as TR
from fidetype.benchmark.__main__ import main as cli
from fidetype.benchmark.submission import SubmissionError


def _kt_fixture(root, n_runs=10):
    """10 synthetic KT-sEMG runs, 3 bursts each (train 1 run, cal 3 runs, test 6 runs). Same text in every run."""
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
    root = _kt_fixture(tmp_path / "kt")
    split = TR.make_split("kt-semg", TR.local_units("kt-semg", root))
    monkeypatch.setattr(TR, "load_split", lambda track: split)
    rows = SC.build_truth("kt-semg", root)
    return root, split, rows


def _submission(tmp_path, rows, training_data=None, name="sub"):
    m = SC.manifest_dict("kt-semg", {"name": "unit-test", "weights_licence": "MIT"}, policy={"name": "always"},
                         regime="cross-session", controls={"shuffled": "permuted", "zeros": "zero EMG"},
                         training_data=training_data)
    real = [SC.unit_row(r["unit"], [r["text"]], [-0.1]) for r in rows]
    null = [SC.unit_row(r["unit"], ["KeyQ KeyQ"], [-9.0], action="abstain") for r in rows]
    return SC.write_submission(tmp_path / name, m, real, {"shuffled": null, "zeros": null})


def _card(kt, tmp_path, training_data, name="sub"):
    _, split, rows = kt
    sub = _submission(tmp_path, rows, training_data, name)
    return SC.score("kt-semg", sub, {r["unit"]: r for r in rows}, B=50, split=split)


def test_no_overlap_passes(kt, tmp_path):
    td = {"sources": [{"dataset": "kt-semg", "partitions": ["train"], "use": "train"},
                      {"dataset": "kt-semg", "partitions": ["cal"], "use": "calibration"}]}
    res = _card(kt, tmp_path, td)
    ov = res["overlap_check"]
    assert ov["status"] == "pass" and ov["passed"] is True and ov["n_overlapping_units"] == 0
    assert ov["text_checked"] and ov["declared"] == "listed"
    assert {(f["use"], f["partition"]) for f in ov["findings"]} == {("train", "train"), ("calibration", "cal")}
    assert res["status"] == "scored"  # the check warns only; numbers and status stay
    assert "overlap: pass" in SC.score_card_text(res)


def test_id_overlap_fails(kt, tmp_path):
    _, split, rows = kt
    test_units = [r["unit"] for r in rows]
    td = {"sources": [{"dataset": "kt-semg", "partitions": ["train"], "use": "train"}],
          "unit_ids": {"tune": test_units[:4]}}
    res = _card(kt, tmp_path, td)
    ov = res["overlap_check"]
    assert ov["status"] == "overlap" and ov["passed"] is False
    assert ov["n_overlapping_units"] == 4 and ov["by_kind"]["id"] == 4 and ov["by_use"]["tune"] == 4
    f = [f for f in ov["findings"] if f["n_units"]]
    assert f == [{"use": "tune", "source": "unit_ids", "partition": None, "kind": "id", "n_units": 4}]
    assert any(n.startswith("WARNING (train / test overlap") for n in res["notes"])
    assert "overlap: FAIL, 4/18 units" in SC.score_card_text(res)
    # A whole partition: training on the test split overlaps every scored unit.
    res2 = _card(kt, tmp_path, {"sources": [{"dataset": "kt-semg", "partitions": ["test"], "use": "train"}]}, "s2")
    assert res2["overlap_check"]["n_overlapping_units"] == len(rows)
    # The check without truth (`check`) sees the id overlap too.
    rep = SC.check_submission("kt-semg", tmp_path / "sub", split)
    assert rep["overlap_check"]["status"] == "overlap" and not rep["overlap_check"]["text_checked"]


def test_text_only_overlap_fails(kt, tmp_path):
    _, _, rows = kt
    # The training corpus holds the same sentences under other ids (synthetic: every run types the same text).
    hashes = sorted({OV.text_hash("kt-semg", r["text"]) for r in rows})
    td = {"sources": [{"dataset": "kt-semg", "partitions": ["train"], "use": "train"}],
          "text_hashes": {"train": hashes[:1]}}
    res = _card(kt, tmp_path, td)
    ov = res["overlap_check"]
    assert ov["status"] == "overlap" and ov["passed"] is False
    assert ov["by_kind"].get("id", 0) == 0 and ov["by_kind"]["text"] == ov["n_overlapping_units"] > 0
    # Equal text after normalisation gives the same hash.
    assert OV.text_hash("kt-semg", "KeyA  KeyB") == OV.text_hash("kt-semg", "KeyA KeyB")


def test_missing_declaration_is_not_checked(kt, tmp_path):
    res = _card(kt, tmp_path, None)
    ov = res["overlap_check"]
    assert ov["status"] == "not checked" and ov["passed"] is None and ov["declared"] == "missing"
    assert ov["status"] != "pass" and "not checked" in SC.score_card_text(res)
    assert any("not checked" in n for n in res["notes"])
    assert "[overlap not checked]" in LB.row({**res, "_file": "x.json"})["decoder"]
    # An unresolved partition of the track's own dataset is "not checked" too, never "pass".
    res2 = _card(kt, tmp_path, {"sources": [{"dataset": "kt-semg", "partitions": ["runs-1-5"], "use": "train"}]},
                 "s2")
    assert res2["overlap_check"]["status"] == "not checked" and res2["overlap_check"]["passed"] is None
    # "none" is a declaration: pass.
    assert _card(kt, tmp_path, "none", "s3")["overlap_check"]["status"] == "pass"
    # External data with no text hashes: listed as unchecked, does not block a pass.
    ext = _card(kt, tmp_path, {"sources": [{"dataset": "tatoeba-en", "use": "train"}]}, "s4")["overlap_check"]
    assert ext["status"] == "pass" and ext["unchecked"][0].startswith("external: tatoeba-en")


def test_bad_declarations_are_rejected():
    for bad in ("all", {"sources": [{"dataset": "kt-semg", "use": "fit"}]},
                {"sources": [{"use": "train"}]}, {"unit_ids": {"train": ["xyz"]}}, {"foo": 1}, {}):
        with pytest.raises(SubmissionError):
            OV.parse_declaration(bad)


def test_board_marks_overlap(kt, tmp_path):
    _, _, rows = kt
    res = _card(kt, tmp_path, {"unit_ids": {"calibration": [rows[0]["unit"]]}})
    name = LB.row({**res, "_file": "x.json"})["decoder"]
    assert "[TRAIN/TEST OVERLAP: 1/18 units]" in name
    clean = _card(kt, tmp_path, "none", "s2")
    assert "OVERLAP" not in LB.row({**clean, "_file": "y.json"})["decoder"]
    old = {k: v for k, v in clean.items() if k != "overlap_check"}  # a card from before P6-10
    assert "overlap" not in LB.row({**old, "_file": "z.json"})["decoder"]


def test_cli_warns_and_can_fail(kt, tmp_path, capsys):
    _, _, rows = kt
    sub = _submission(tmp_path, rows, {"unit_ids": {"train": [rows[0]["unit"]]}})
    truth = tmp_path / "truth.jsonl"
    SC.write_truth(truth, "kt-semg", rows)
    args = ["score", "kt-semg", str(sub), "--truth", str(truth), "--B", "50", "--out", str(tmp_path / "card.json")]
    assert cli(args) == 0
    err = capsys.readouterr().err
    assert "WARNING: train / test overlap" in err
    assert cli(args + ["--fail-on-overlap"]) == 1
    card = json.loads((tmp_path / "card.json").read_text(encoding="utf-8"))
    assert card["overlap_check"]["status"] == "overlap"
    # overlap-hashes makes the declaration lists.
    texts = tmp_path / "texts.txt"
    texts.write_text(rows[0]["text"] + "\n", encoding="utf-8")
    assert cli(["overlap-hashes", "kt-semg", "--texts", str(texts), "--use", "train", "--out",
                str(tmp_path / "h.json")]) == 0
    h = json.loads((tmp_path / "h.json").read_text(encoding="utf-8"))
    assert h["text_hashes"]["train"] == [OV.text_hash("kt-semg", rows[0]["text"])]


def test_sidecar_file(kt, tmp_path):
    _, split, rows = kt
    sub = _submission(tmp_path, rows, {"file": "training_data.json"})
    (sub / "training_data.json").write_text(json.dumps({"unit_ids": {"train": [rows[1]["unit"]]}}), encoding="utf-8")
    res = SC.score("kt-semg", sub, {r["unit"]: r for r in rows}, B=50, split=split)
    assert res["overlap_check"]["n_overlapping_units"] == 1


def test_b2t25_hdf5_map_matches_the_audit():
    """The committed hash-only map reproduces the T15 split audit counts (no raw data needed)."""
    m = OV.load_map("b2t25-t15", "b2t25-hdf5")
    assert m is not None and m["schema"] == OV.MAP_SCHEMA
    split = TR.load_split("b2t25-t15")
    assert m["split_digest"] == split["digest"]
    test = [e["h"] for e in split["entries"] if e["s"] == "test"]
    assert len(test) == 816 and {r["u"] for r in m["trials"]} <= set(test)
    c = m["counts"]
    assert c["units_strict_by_partition"]["train"] == 366 and c["units_any_by_partition"]["train"] == 368
    assert c["units_sentence_in_partition"]["train"] == 428
    # No text and no plain ids: only hashes, partition names and counts.
    blob = json.dumps(m["trials"]) + json.dumps(m["text"])
    assert "t15." not in blob
    # Training on HDF5 train: 366 id + 2 possible-id units; leaving the matches out removes them,
    # but the same sentences stay (text overlap).
    decl = OV.parse_declaration({"sources": [{"dataset": "b2t25-hdf5", "partitions": ["train"], "use": "train"}]})
    ov = OV.check_overlap("b2t25-t15", decl, test, None, split=split)
    assert ov["status"] == "overlap" and ov["by_kind"]["id"] == 366 and ov["by_kind"]["possible id"] == 2
    decl = OV.parse_declaration({"sources": [{"dataset": "b2t25-hdf5", "partitions": ["train"], "use": "train",
                                              "exclude": OV.EXCLUDE_ALL}]})
    ov = OV.check_overlap("b2t25-t15", decl, test, None, split=split)
    assert ov["by_kind"]["id"] == 0 and ov["by_kind"]["possible id"] == 0 and ov["by_kind"]["text"] == 428
    assert len(OV.leave_out()) == 810 and len(OV.leave_out(possible=False)) < 810
