"""Benchmark tracks v0.2 (P6-01): committed split files + loaders on small synthetic fixtures.

No raw data: the committed split files are checked on their own, and each
loader runs on a tiny synthetic copy of its dataset layout.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from fidetype.benchmark import tracks as TR


# ---------------------------------------------------------------------------
# Committed split files (no data needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", sorted(TR.TRACKS))
def test_committed_split_is_valid(slug):
    d = TR.load_split(slug)
    assert TR.check_split(d) == []
    t = TR.get_track(slug)
    assert d["counts"][t.scored_set][t.scored_split] > 0
    assert set(d["counts"]) == set(t.units)


@pytest.mark.parametrize("slug", sorted(TR.TRACKS))
def test_split_file_holds_only_hashes(slug):
    raw = TR.split_path(slug).read_text(encoding="utf-8")
    body = raw[raw.index('"entries"'):]
    # Only the five short keys, split names and hex digests after "entries".
    words = set(re.findall(r'"([^"]*)"', body))
    allowed = {"entries", "u", "h", "s", "g", "fp"} | set(TR.get_track(slug).units) | {
        "train", "val", "cal", "test", "holdout"}
    assert all(w in allowed or re.fullmatch(r"[0-9a-f]{12}|[0-9a-f]{16}", w) for w in words)


def test_licences_and_research_flags():
    nc = {s for s, t in TR.TRACKS.items() if t.research_only}
    assert nc == {"spanishbcbl-meg", "emg2qwerty"}
    for s, t in TR.TRACKS.items():
        assert ("NC" in t.licence) == t.research_only, s
        assert t.attribution and t.citation and t.url
        assert set(TR.REQUIRED_CONTROLS) <= set(t.controls)
        assert TR.load_split(s)["research_only"] == t.research_only
    assert {t.modality for t in TR.TRACKS.values()} == {"intracortical", "emg", "meg"}


@pytest.mark.parametrize("slug", ["b2t25-t15", "toronto-semg", "spanishbcbl-meg"])
def test_v02_keeps_the_v01_trials(slug):
    r = TR.check_v01_equivalence(slug)
    assert r["mismatch"] == [] and r["n_v01"] == r["n_v02"] > 0


def test_salts_differ_per_track():
    assert TR.id_hash("kt-semg", "run1") != TR.id_hash("emg2qwerty", "run1")
    assert len(TR.id_hash("a", "b")) == 16 and len(TR.group_hash("a", "b")) == 12


def test_check_split_catches_tampering():
    d = TR.load_split("kt-semg")
    bad = json.loads(json.dumps(d))
    bad["entries"][0]["s"] = "train" if bad["entries"][0]["s"] != "train" else "test"
    probs = TR.check_split(bad)
    assert any("digest" in p for p in probs) and any("counts" in p for p in probs)
    bad = json.loads(json.dumps(d))
    bad["entries"][0]["text"] = "hello"
    assert any("fields" in p for p in TR.check_split(bad))


def test_cli_list_and_info(capsys):
    assert TR.main(["list"]) == 0
    out = capsys.readouterr().out
    assert sum("RESEARCH ONLY" in line for line in out.splitlines()) == 2
    assert TR.main(["info", "willett-hw"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["licence"] == "CC0 1.0" and info["split_counts"]["trial"]["test"] > 0


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------


def _kt_fixture(root, n_runs=10):
    root.mkdir()
    for r in range(1, n_runs + 1):
        t0 = 1_600_000_000.0 + r * 10_000
        (root / f"run{r}_ts.txt").write_text(f"2020-09-{r:02d} 10:00:00.000", encoding="ascii")
        lines = []
        t = t0 + 5
        for burst in range(3):
            for ch in "hello world"[: 6 + burst]:
                lines.append(f"{ch} {t:.6f}")
                t += 0.3
            t += 5.0  # pause > 2 s: a new segment
        lines.append(f"a {t:.6f}")  # one-key burst: dropped (< 5 keys)
        (root / f"run{r}_keys.txt").write_bytes(("\n".join(lines) + "\n").encode("latin-1"))
        (root / f"run{r}.csv").write_text("Time\tc1\n0\t1\n", encoding="ascii")
    return root


def _e2q_fixture(root):
    root.mkdir()
    rows = ["user,session,condition,duration_mins,num_keystrokes,num_prompts,quality_check_tags"]
    for u, n in (("11111111", 5), ("22222222", 2)):
        for k in range(n):
            s = f"2020-08-{10 + k:02d}-{1597000000 + k}-keystrokes-{u}"
            rows.append(f"{u},{s},on_keyboard,15.0,{100 + k},{10 + k},[]")
            (root / f"{s}.hdf5").write_bytes(b"x" * (50 + k))
    (root / "metadata.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return root


def _toronto_fixture(root):
    for p in ("P1", "P2"):
        for s in ("T1", "T2"):
            d = root / "CleanData" / p / s / "Data"
            d.mkdir(parents=True)
            for letter in "ab":
                for k, hh in enumerate(("10", "11")):
                    (d / f"{letter.upper()}_22090{1 if s == 'T1' else 2}_{hh}{k}000.rhd").write_bytes(b"r" * (10 + k))
    return root


def _round_trip(slug, data, **kw):
    units = TR.local_units(slug, data, **kw)
    d = TR.make_split(slug, units)
    assert TR.check_split(d) == [] or all("no scored entries" in p for p in TR.check_split(d))
    rep = TR.verify_units(d, units)
    assert rep.ok, rep.summary()
    return units, d


def test_kt_semg_rule_and_verify(tmp_path):
    root = _kt_fixture(tmp_path / "kt")
    units, d = _round_trip("kt-semg", root)
    runs = [u for u in units if u.set == "run"]
    assert [u.split for u in runs] == ["train"] + ["cal"] * 3 + ["test"] * 6
    segs = [u for u in units if u.set == "segment"]
    assert len(segs) == 9 * 3 and all(len(u.payload.split()) >= 5 for u in segs)
    assert {u.split for u in segs} == {"cal", "test"}
    # A changed key file breaks the fingerprint of its run and its segments.
    p = root / "run10_keys.txt"
    p.write_bytes(p.read_bytes().replace(b"h ", b"j ", 1))
    rep = TR.verify_units(d, TR.local_units("kt-semg", root))
    assert not rep.ok and len(rep.fp_mismatch) == 2
    # A missing run is reported as missing.
    for f in root.glob("run1.*"):
        f.unlink()
    (root / "run1_keys.txt").unlink()
    rep = TR.verify_units(d, TR.local_units("kt-semg", root))
    assert any(m.startswith("run/") for m in rep.missing)


def test_emg2qwerty_rule_select_and_missing_file(tmp_path):
    root = _e2q_fixture(tmp_path / "e2q")
    units, d = _round_trip("emg2qwerty", root)
    sp = {u.id: u.split for u in units}
    u1 = sorted(i for i in sp if i.endswith("11111111"))
    assert [sp[i] for i in u1] == ["train", "train", "train", "val", "test"]
    assert all(sp[i] == "train" for i in sp if i.endswith("22222222"))
    sel = TR.select_units(d, units, "test")
    assert [u.id for u in sel] == [u1[-1]] and sel[0].ref["present"]
    (root / f"{u1[-1]}.hdf5").unlink()
    rep = TR.verify_units(d, TR.local_units("emg2qwerty", root))
    assert len(rep.fp_mismatch) == 1


def test_toronto_recording_rule(tmp_path):
    root = _toronto_fixture(tmp_path / "tor")
    units, d = _round_trip("toronto-semg", root)
    by = {u.id: u.split for u in units}
    assert all(v == "train" for k, v in by.items() if "/T1/" in k)
    t2 = sorted((k, v) for k, v in by.items() if "/T2/" in k)
    assert [v for _, v in t2] == ["cal", "test"] * 4
    assert d["counts"] == {"recording": {"cal": 4, "test": 4, "train": 8}}
    # The sentence set is skipped (no cache given), not failed.
    rep = TR.verify_units(TR.load_split("toronto-semg"), units)
    assert "sentence" in rep.skipped_sets and rep.missing  # the fixture is not the real dataset


def test_split_mismatch_and_group_mismatch(tmp_path):
    root = _e2q_fixture(tmp_path / "e2q")
    units = TR.local_units("emg2qwerty", root)
    d = TR.make_split("emg2qwerty", units)
    units[0].split = "test" if units[0].split != "test" else "train"
    units[1].group = "someone-else"
    rep = TR.verify_units(d, units)
    assert len(rep.split_mismatch) == 1 and len(rep.group_mismatch) == 1 and not rep.ok


def test_select_raises_on_missing_units(tmp_path):
    root = _e2q_fixture(tmp_path / "e2q")
    units = TR.local_units("emg2qwerty", root)
    d = TR.make_split("emg2qwerty", units)
    with pytest.raises(LookupError):
        TR.select_units(d, [u for u in units if u.split != "test"], "test")


def test_cli_verify_against_committed_split_fails_on_fixture(tmp_path, capsys):
    root = _kt_fixture(tmp_path / "kt")
    assert TR.main(["verify", "kt-semg", "--data", str(root), "--json", str(tmp_path / "r.json")]) == 1
    assert "MISMATCH" in capsys.readouterr().out
    assert json.loads((tmp_path / "r.json").read_text())["ok"] is False


def test_cli_make_and_select(tmp_path, capsys):
    root = _e2q_fixture(tmp_path / "e2q")
    out = tmp_path / "split.json"
    assert TR.main(["make", "emg2qwerty", "--data", str(root), "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert TR.check_split(d) == []
    capsys.readouterr()


def _cells(n):
    c = np.empty((1, n), dtype=object)
    for i in range(n):
        c[0, i] = np.zeros((3, 2), np.float32)
    return c


def test_t12_rule(tmp_path):
    sio = pytest.importorskip("scipy.io")
    root = tmp_path / "competitionData"
    for folder, n in (("train", 6), ("test", 2), ("competitionHoldOut", 2)):
        (root / folder).mkdir(parents=True)
        texts = ["HELD OUT"] * n if folder == "competitionHoldOut" else [f"Sentence number {'abcdef'[i]}." for i in range(n)]
        blocks = np.array([[1], [1], [1], [2], [2], [2]][:n], dtype=np.uint8) if folder == "train" else np.ones((n, 1), np.uint8)
        width = max(len(t) for t in texts)
        sio.savemat(root / folder / "t12.2022.04.28.mat",
                    {"sentenceText": np.array([t.ljust(width) for t in texts]), "blockIdx": blocks,
                     "tx1": _cells(n)})
    units, d = _round_trip("b2t24-t12", tmp_path)
    sp = [u.split for u in units]
    assert sp == ["train"] * 3 + ["cal"] * 3 + ["test"] * 2 + ["holdout"] * 2
    assert all(u.payload == "" for u in units if u.split == "holdout")
    assert units[0].payload == "sentence number a"


def test_willett_rule(monkeypatch):
    from fidetype.adapters import willett_handwriting as W
    from fidetype.conformance.producers import synthetic_willett_session

    files = [__import__("pathlib").Path(f"/x/Datasets/t5.2020.01.{d:02d}/sentences.mat") for d in range(1, 6)]
    sess = synthetic_willett_session(n_trials=12)
    monkeypatch.setattr(W, "list_session_files", lambda root: files)
    monkeypatch.setattr(W, "load_sentences", lambda f: sess)
    units = TR.local_units("willett-hw", "/x")
    by_sess: dict = {}
    for u in units:
        by_sess.setdefault(u.group, []).append(u.split)
    n = sum(1 for i in range(sess.n_trials) if not sess.excluded[i])
    early = by_sess["t5.2020.01.01"]
    assert early.count("val") == max(1, -(-n // 10)) and early[-1] == "val"
    late = by_sess["t5.2020.01.05"]
    assert late.count("cal") == n // 3 and late[0] == "cal" and late[-1] == "test"
    assert set(by_sess["t5.2020.01.02"]) == {"train", "val"}
    assert set(by_sess["t5.2020.01.03"]) == {"cal", "test"}
    d = TR.make_split("willett-hw", units)
    assert TR.verify_units(d, units).ok


def test_benchmark_cli_verify_passthrough(tmp_path, capsys):
    from fidetype.benchmark.__main__ import main

    root = _kt_fixture(tmp_path / "kt")
    assert main(["verify", "kt-semg", "--data", str(root)]) == 1
    assert "kt-semg: MISMATCH" in capsys.readouterr().out
