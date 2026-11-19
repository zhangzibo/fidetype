"""Hub command line and rerun recipes (P13-06), on synthetic fixtures and the committed cards only (no raw data)."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from fidetype.benchmark import hub
from fidetype.benchmark import scorecard as SC
from fidetype.benchmark import tracks as TR
from fidetype.benchmark.hub import cli as H
from fidetype.benchmark.hub import recipe as R

ROOT = Path(__file__).resolve().parents[1]


def run(capsys, *argv):
    code = H.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


# --- list / show / instructions / check ------------------------------------------------------------


def test_list_and_show(capsys):
    code, out, _ = run(capsys, "list")
    assert code == 0
    for d in ("brain-to-text-25", "spanishbcbl", "toronto-semg"):
        assert d in out
    assert "RESEARCH ONLY" in out  # spanishbcbl is CC BY-NC
    code, out, _ = run(capsys, "list", "--json")
    rows = json.loads(out)
    assert {r["id"] for r in rows} >= {"brain-to-text-25", "spanishbcbl", "toronto-semg"}
    code, out, _ = run(capsys, "show", "toronto-semg")
    assert code == 0 and "73c4f925b81c" in out and "fidetype.adapters.toronto_semg" in out
    code, out, _ = run(capsys, "show", "toronto-semg", "--json")
    assert json.loads(out)["id"] == "toronto-semg"
    with pytest.raises(SystemExit, match="known: brain-to-text-25"):
        H.main(["show", "no-such-dataset"])


def test_instructions_print_the_official_source_only(capsys):
    code, out, _ = run(capsys, "instructions", "brain-to-text-25")
    d = hub.get_dataset("brain-to-text-25")
    assert code == 0 and d["url"] in out and d["download"]["instructions"] in out
    assert "never downloads" in out and "login:       required" in out
    code, out, _ = run(capsys, "instructions", "spanishbcbl")
    assert "RESEARCH ONLY" in out and "Build the local cache" in out
    # The hub command line has no network code: it cannot download or re-host data.
    src = inspect.getsource(H) + inspect.getsource(R)
    for mod in ("urllib", "requests", "http.client", "socket", "huggingface_hub"):
        assert f"import {mod}" not in src and f"from {mod}" not in src


def test_check_registry_and_entry(capsys, tmp_path):
    assert run(capsys, "check")[0] == 0
    assert H.main([]) == 0  # no command = check (P13-01 behaviour)
    capsys.readouterr()
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps(hub.load_registry()), encoding="utf-8")
    assert run(capsys, "check", "--registry", str(reg))[0] == 0
    bad = copy.deepcopy(hub.get_dataset("toronto-semg"))
    bad["personal_data"]["rehost"] = True
    entry = tmp_path / "entry.json"
    entry.write_text(json.dumps(bad), encoding="utf-8")
    code, _, err = run(capsys, "check", "--entry", str(entry))
    assert code == 1 and "rehost" in err
    entry.write_text(json.dumps(hub.get_dataset("toronto-semg")), encoding="utf-8")
    assert run(capsys, "check", "--entry", str(entry))[0] == 0


def test_fidetype_hub_subcommand(capsys):
    from fidetype.cli import main as fidetype_cli

    assert fidetype_cli(["hub", "list"]) == 0
    assert "toronto-semg" in capsys.readouterr().out


# --- verify ------------------------------------------------------------------------------------------


@pytest.fixture()
def fake(monkeypatch, tmp_path):
    """A registry entry whose files are small local files."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.bin").write_bytes(b"abc" * 1000)
    (data / "b.zip").write_bytes(b"zip")
    sha_a = hashlib.sha256(b"abc" * 1000).hexdigest()
    entry = copy.deepcopy(hub.get_dataset("toronto-semg"))
    entry["forms"] = [
        {"form": "one", "description": "x", "files": [{"name": "a.bin", "bytes": 3000, "sha256": sha_a}]},
        {"form": "two", "description": "y", "files": [{"name": "b.zip", "bytes": None, "sha256": None, "note": "n"},
                                                      {"name": "S*/*.fif", "bytes": None, "sha256": None,
                                                       "note": "no manifest"}]},
    ]
    monkeypatch.setattr(hub, "get_dataset", lambda i, v=None: entry)
    return entry, data, sha_a


def test_verify_files(fake, capsys):
    entry, data, sha_a = fake
    rows = {r["name"]: r for r in H.verify_files(entry, data)}
    assert rows["a.bin"]["status"] == "ok" and rows["a.bin"]["sha256"] == sha_a
    assert rows["b.zip"]["status"] == "no-checksum"
    assert rows["S*/*.fif"]["status"] == "not-checkable"
    code, out, _ = run(capsys, "verify", "toronto-semg", "--data", str(data))
    assert code == 0 and "ok" in out and "next: check the split units" in out
    # One file given: only its own row is checked.
    assert [r["name"] for r in H.verify_files(entry, data / "a.bin")] == ["a.bin", "S*/*.fif"]
    assert run(capsys, "verify", "toronto-semg", "--data", str(data / "a.bin"), "--form", "one")[0] == 0
    # Same size, other bytes: SHA-256 mismatch, exit 1.
    (data / "a.bin").write_bytes(b"abd" * 1000)
    code, out, _ = run(capsys, "verify", "toronto-semg", "--data", str(data), "--json")
    js = json.loads(out)
    assert code == 1 and js["exit"] == 1 and js["files"][0]["status"] == "sha256-mismatch"
    # Other size: size mismatch (no hash needed).
    (data / "a.bin").write_bytes(b"short")
    assert H.verify_files(entry, data, "one")[0]["status"] == "size-mismatch"
    # Nothing registered at this path: exit 2.
    empty = data / "empty"
    empty.mkdir()
    assert run(capsys, "verify", "toronto-semg", "--data", str(empty), "--form", "one")[0] == 2


# --- recipes -----------------------------------------------------------------------------------------


def _cards():
    return sorted((ROOT / "benchmark" / "results").glob("v0.*/*.json"))


def test_every_committed_card_has_a_valid_recipe():
    files = _cards()
    if not files:
        pytest.skip("no committed cards")
    for p in files:
        card = json.loads(p.read_text(encoding="utf-8"))
        r = card.get("rerun")
        assert r is not None, f"{p.name}: no rerun recipe"
        assert R.check_recipe(r) == [], (p.name, R.check_recipe(r))
        assert R.rerun_level(card) == "rescore"
        assert r["track"]["track"] == card["track"]
        assert r["scorer"]["scorer_version"] == card.get("scorer_version", "benchmark-0.1")
        assert len(r["track"]["digest"]) == 64 and r["code_ref"].startswith("git ")
        if r["track"]["split_version"] == "tracks-v0.2":
            assert r["track"]["digest"] == TR.load_split(card["track"])["digest"]
            assert "python -m fidetype.benchmark score" in r["command"]
        hub_ds = R.dataset_for_track(card["track"])
        if hub_ds:
            assert r["dataset"] == {"id": hub_ds["id"], "version": hub_ds["version"], "revision": hub_ds["revision"]}
        else:
            assert r["dataset"] is None and r["dataset_note"]


def test_recipe_checker_and_adapter_hash(tmp_path):
    a = R.adapter_id("fidetype.adapters.b2t25")
    assert a["module"] == "fidetype.adapters.b2t25" and len(a["sha256"]) == 64
    # CRLF and LF checkouts give the same hash.
    lf, crlf = tmp_path / "lf.py", tmp_path / "crlf.py"
    lf.write_bytes(b"x = 1\ny = 2\n")
    crlf.write_bytes(b"x = 1\r\ny = 2\r\n")
    assert R.source_sha256(lf) == R.source_sha256(crlf)
    assert R.adapter_module_for("b2t24-t12") == "fidetype.benchmark.tracks"  # "<module>.<function>" in tracks.py
    card = json.loads((ROOT / "benchmark/results/v0.2/b2t25-t15__published__ltt.json").read_text(encoding="utf-8"))
    r = copy.deepcopy(card["rerun"])
    bad = dict(r, level="maybe", command="python run.py C:/Users/me/data")
    del bad["versions"]
    errs = " | ".join(R.check_recipe(bad))
    for part in ("rerun.level", "local path", "rerun.versions"):
        assert part in errs
    assert "dataset_note" in " ".join(R.check_recipe(dict(r, dataset=None)))
    assert R.check_recipe(dict(r, command="python x.py https://example.org/a")) == []  # a URL is not a local path
    assert R.rerun_level({"track": "x"}) == "no"
    assert "rerun: no" in R.recipe_text(None)
    with pytest.raises(ValueError):
        R.make_recipe(card, command="x", level="unknown")


def test_recipe_command_prints(capsys):
    p = ROOT / "benchmark/results/v0.2/b2t25-t15__published__ltt.json"
    code, out, _ = run(capsys, "recipe", str(p))
    assert code == 0 and "rerun level: rescore" in out and "brain-to-text-25 dryad-2025-07-03 r1" in out
    code, out, _ = run(capsys, "recipe", str(p), "--json")
    assert json.loads(out)["schema"] == R.RECIPE_SCHEMA


# --- the scorer writes the recipe; rerun reproduces the card -------------------------------------------


def _kt_fixture(root, n_runs=10):
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
def scored(tmp_path, monkeypatch):
    root = _kt_fixture(tmp_path / "kt")
    split = TR.make_split("kt-semg", TR.local_units("kt-semg", root))
    monkeypatch.setattr(TR, "load_split", lambda track: split)
    rows = SC.build_truth("kt-semg", root)
    truth_path = tmp_path / "truth.jsonl"
    SC.write_truth(truth_path, "kt-semg", rows)
    man = SC.manifest_dict("kt-semg", decoder={"name": "unit-test", "weights_licence": "MIT"},
                           policy={"name": "half"}, regime="cross-session",
                           controls={"shuffled": "frames permuted", "zeros": "all-zero EMG"})
    out = []
    for k, r in enumerate(rows):
        ok = k % 2 == 0
        hyp = r["text"] if ok else " ".join(["KeyX"] * len(r["text"].split()))
        out.append(SC.unit_row(r["unit"], [hyp], [-0.1], action="commit" if ok else "offer"))
    null = [SC.unit_row(r["unit"], ["KeyQ KeyQ"], [-9.0], action="abstain") for r in rows]
    sub = SC.write_submission(tmp_path / "sub", man, out, {"shuffled": null, "zeros": null})
    res = SC.score("kt-semg", sub, {r["unit"]: r for r in rows}, B=50, seed=3)
    card = tmp_path / "card.json"
    card.write_text(R.card_json(res), encoding="utf-8")
    return card, sub, truth_path


def test_scorer_writes_the_recipe_and_rerun_reproduces_the_card(scored, capsys, tmp_path):
    card_path, sub, truth = scored
    card = json.loads(card_path.read_text(encoding="utf-8"))
    r = card["rerun"]
    assert R.check_recipe(r) == []
    assert r["level"] == "rescore" and r["scorer"]["B"] == 50 and r["scorer"]["seed"] == 3
    assert r["command"] == "python -m fidetype.benchmark score kt-semg <submission> --truth <truth.jsonl> --B 50 --seed 3"
    assert r["adapter"]["module"] == "fidetype.adapters.kt_semg"
    assert r["dataset"] is None and "P13-07" in r["dataset_note"]  # kt-semg is not yet in the hub registry
    assert R.rescore(card, sub, truth)["same"]
    code, out, _ = run(capsys, "rerun", str(card_path), "--submission", str(sub), "--truth", str(truth),
                       "--out", str(tmp_path / "new.json"))
    assert code == 0 and "same card" in out and (tmp_path / "new.json").exists()
    # A changed number in the card: the rerun says DIFFERENT.
    card["metrics"]["cer"]["value"] += 0.01
    card_path.write_text(R.card_json(card), encoding="utf-8")
    code, out, _ = run(capsys, "rerun", str(card_path), "--submission", str(sub), "--truth", str(truth))
    assert code == 1 and "metrics" in out
    with pytest.raises(ValueError, match="only rescore"):
        R.rescore(dict(card, rerun=dict(r, level="full")), sub, truth)


def test_leaderboard_shows_the_rerun_level_and_recipe(scored, tmp_path):
    from fidetype.benchmark.leaderboard import build

    card_path, _, _ = scored
    res = tmp_path / "res"
    res.mkdir()
    card = json.loads(card_path.read_text(encoding="utf-8"))
    (res / "with.json").write_text(json.dumps(card), encoding="utf-8")
    (res / "without.json").write_text(json.dumps({k: v for k, v in card.items() if k != "rerun"}
                                                 | {"entry_id": "no-recipe"}), encoding="utf-8")
    build([res], tmp_path / "site")
    page = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    md = (tmp_path / "site" / "leaderboard.md").read_text(encoding="utf-8")
    lb = json.loads((tmp_path / "site" / "leaderboard.json").read_text(encoding="utf-8"))
    assert "<th>Rerun</th>" in page and "Rerun recipes (1 of 2 entries)" in page
    assert "python -m fidetype.benchmark score kt-semg &lt;submission&gt;" in page
    assert "| Rerun |" in md and "[score] python -m fidetype.benchmark score kt-semg" in md
    levels = sorted(r["rerun_level"] for r in lb["tracks"]["kt-semg"])
    assert levels == ["no", "rescore"]
