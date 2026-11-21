"""Newcomer API additions found by the tutorials (P14-43): gaps 129 (P14-44), 130 (P14-45), 131 (P14-46).

- P14-44: toy model, item count + clear IndexError, decode() deprecation path, one guard entry point, [hdf5] extra.
- P14-45: safe WPM from TrustGuard decisions in one call (same report as the manual route).
- P14-46: build_truth(split=), key-log-only KT truth, track-space n-best, valid submission guarantee from a sheet,
  packaged leaderboard cards.

Synthetic data only. Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import shutil
import string
import tomllib
import warnings
from pathlib import Path

import numpy as np
import pytest

import fidetype.pretrained as ftp
from fidetype.pretrained import readers as R

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------------------------------
# P14-44: pretrained API
# --------------------------------------------------------------------------------------------------


def test_toy_model_loads_decodes_and_checks_files(tmp_path):
    import fidetype.conformance as C

    path = ftp.make_toy_manifest(tmp_path, n_in=8, hidden=8, sessions=["a.2026.01.01"])
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["task"] == "tutorial" and doc["trust"] is None and doc["files"][0]["url"] is None
    m = ftp.load(str(path), weights=tmp_path)  # load() checks size + SHA-256
    assert m.sessions == ("a.2026.01.01",)
    st = m.decode(np.zeros((40, 8), np.float32), session=m.sessions[0])
    assert st.log_probs.shape[1] == 41 and C.check(st).passes("provenance")
    with pytest.raises(ftp.NoTrustConfig):
        m.decide(st)
    # a changed weights file is refused
    w = tmp_path / doc["files"][0]["name"]
    b = bytearray(w.read_bytes())
    b[len(b) // 2] ^= 0xFF
    w.write_bytes(bytes(b))
    with pytest.raises(ftp.WeightsMismatch):
        ftp.load(str(path), weights=tmp_path)
    t = ftp.toy_model(folder=tmp_path / "t2")
    assert t.name == "toy-gru" and t.sessions == ("toy.2026.01.01", "toy.2026.01.02")
    with pytest.raises(ValueError, match="toy runtimes"):
        ftp.make_toy_manifest(tmp_path, runtime="no-such-runtime")


def _hdf5(folder: Path, n: int, n_in: int = 16) -> Path:
    h5py = pytest.importorskip("h5py")
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    p = folder / "data_val.hdf5"
    with h5py.File(p, "w") as f:
        for i in range(n):
            g = f.create_group(f"trial_{i:04d}")
            g.create_dataset("input_features", data=rng.standard_normal((30, n_in)).astype(np.float32))
            g.attrs["sentence_label"] = f"text {i}"
    return p


def test_n_items_and_clear_index_error(tmp_path):
    m = ftp.toy_model(folder=tmp_path / "m", sessions=["toy.2026.01.01"])
    p = _hdf5(tmp_path / "toy.2026.01.01", 3)
    assert m.n_items(p) == 3 == R.count_items("b2t25-hdf5", p)
    assert len(m.decode_file(p, indices=[0, 2, -1])) == 3  # -n .. n-1 stays valid
    with pytest.raises(IndexError, match=r"index 3 is out of range: the file has 3 items \(indices 0\.\.2\)"):
        m.decode_file(p, indices=[1, 3])
    with pytest.raises(IndexError, match="index -4"):
        R.read_b2t25_hdf5(p, indices=[-4])
    with pytest.raises(ValueError, match="unknown input file format"):
        R.count_items("nope", p)


def test_decode_path_is_deprecated_but_unchanged(tmp_path):
    m = ftp.toy_model(folder=tmp_path / "m", sessions=["toy.2026.01.01"])
    p = _hdf5(tmp_path / "toy.2026.01.01", 2)
    with pytest.warns(DeprecationWarning, match="decode_file"):
        old = m.decode(str(p))
    new = m.decode_file(p)
    assert isinstance(old, list) and len(old) == len(new) == 2
    for a, b in zip(old, new):
        np.testing.assert_array_equal(a.log_probs, b.log_probs)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # an array gives one stream, no warning
        st = m.decode(np.zeros((30, 16), np.float32), session=0)
    assert st.log_probs.ndim == 2


def _key_model(tmp: Path):
    from fidetype.live.model import builtin_dir
    from fidetype.pretrained.manifest import MANIFEST_SCHEMA

    import hashlib

    src = builtin_dir()
    files = []
    for role, suf in (("card", ".model.json"), ("weights", ".weights.json"), ("guard", ".guard.json")):
        p = tmp / f"synthetic-keys{suf}"
        shutil.copy(src / f"synthetic-keys{suf}", p)
        files.append({"role": role, "name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                      "size": p.stat().st_size, "url": None})
    doc = {"schema": MANIFEST_SCHEMA, "name": "fake-keys", "version": "1", "title": "synthetic keys",
           "status": "available", "task": "test", "modality": "emg", "runtime": "key-lda",
           "input": {"file_format": "kt-semg-run"}, "output": {"vocab_type": "key", "latency_s": 0.05},
           "files": files, "licence": {"data.licence": "LicenseRef-fidetype-own", "data.research_only": False},
           "trust": {"config": "file:synthetic-keys.guard.json", "decode": "nbest-keys"}}
    mp = tmp / "fake-keys.json"
    mp.write_text(json.dumps(doc), encoding="utf-8")
    m = ftp.load(str(mp), weights=tmp)
    rng = np.random.default_rng(0)
    sig = rng.standard_normal((int(m.model.sample_rate * 3), m.model.channels)).astype(np.float32)
    return m, m.decode(sig, times=[0.5, 1.0, 1.5, 2.0])


def test_one_guard_entry_point_per_model(tmp_path):
    m, st = _key_model(tmp_path)
    assert m.guard_input(st) == m.nbest(st)  # key model: the n-best list
    g = m.guard()
    a = m.decide(st, guard=g, utterance_id="u0")
    b = m.guard().decide(m.nbest(st))
    assert (a.action, a.text, a.choices) == (b.action, b.text, b.choices)
    assert g.audit_log[-1]["utterance_id"] == "u0"
    c = m.decide(st)  # default guard: built once, then kept
    assert m.decide(st).action == c.action and m._default_guard is not None
    toy = ftp.toy_model(folder=tmp_path / "toy")
    s2 = toy.decode(np.zeros((30, 16), np.float32), session=0)
    assert toy.guard_input(s2) is s2.log_probs  # score-matrix models


def test_neutral_hdf5_extra():
    d = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ex = d["project"]["optional-dependencies"]
    assert ex["hdf5"] == ["h5py>=3.10"] and ex["emg2qwerty"] == ex["hdf5"]  # old name kept


# --------------------------------------------------------------------------------------------------
# P14-45: decisions -> safe WPM
# --------------------------------------------------------------------------------------------------

VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]
PHRASES = ["yes", "no thanks", "thank you", "i am thirsty", "good morning", "i need help", "see you later"]


def _toy_logits(text: str, rng: np.random.Generator) -> np.ndarray:
    noise = rng.uniform(0.0, 1.0)
    rows = []
    for ch in text:
        target = VOCAB.index(ch)
        if rng.random() < 0.25 * noise:
            target = int(rng.integers(1, len(VOCAB)))
        for k in range(4):
            row = rng.normal(0.0, 1.0, len(VOCAB))
            row[target if k == 0 else 0] += (9.0 - 6.0 * noise) if k == 0 else 7.0
            rows.append(row)
    return np.array(rows)


@pytest.fixture(scope="module")
def guard_and_decisions():
    import fidetype.trust as ft

    rng = np.random.default_rng(3)
    cal = [str(rng.choice(PHRASES)) for _ in range(160)]
    lex = sorted({w for p in PHRASES for w in p.split()})
    g = ft.calibrate([_toy_logits(t, rng) for t in cal], cal, vocab=VOCAB, blank="_", lexicon=lex, alpha=0.1,
                     delta=0.1, decoder_name="test-toy", modality="other", null_trials=20)
    test = [str(rng.choice(PHRASES)) for _ in range(60)]
    xs = [_toy_logits(t, rng) for t in test]
    res = [g.decide(x) for x in xs]
    return g, res, test, [x.shape[0] * 0.1 for x in xs]


def _js(d: dict) -> str:
    return json.dumps(d, sort_keys=True, default=str)


def test_from_decisions_equals_manual_route(guard_and_decisions):
    from fidetype.benchmark import safe_wpm as sw

    g, res, truths, ns = guard_and_decisions
    committed = [r.action == "commit" for r in res]
    correct = [c and r.text == t for c, r, t in zip(committed, res, truths)]
    sheet = g.sheet.to_dict()
    manual = sw.safe_wpm(committed, correct, n_words=[len(t.split()) for t in truths],
                         n_chars=[len(t) for t in truths], neural_s=ns, guarantee=sw.guarantee_from_sheet(sheet),
                         controls=sw.controls_from_sheet(sheet), timing="toy")
    assert manual["n_commits"] > 0  # the check covers commits
    for src in (g, g.sheet, sheet, {"sheet": sheet}):  # guard, GuaranteeSheet, sheet dict, saved-guard dict
        assert _js(sw.from_decisions(res, truths, ns, src, timing="toy")) == _js(manual)
    # a named track normaliser or a callable; "words" lower-cases and drops punctuation
    w = sw.from_decisions(res, [t.upper() + "." for t in truths], ns, g, normalizer="words", timing="toy")
    keys = ("n_commits", "n_correct_commits", "value")
    assert [w[k] for k in keys] == [manual[k] for k in keys]
    c = sw.from_decisions(res, truths, ns, g, normalizer=lambda t: " ".join(t.split()), timing="toy")
    assert _js(c) == _js(manual)
    with pytest.raises(ValueError, match="same length"):
        sw.from_decisions(res, truths[:-1], ns, g)
    with pytest.raises(ValueError, match="unknown normalizer"):
        sw.from_decisions(res, truths, ns, g, normalizer="nope")


# --------------------------------------------------------------------------------------------------
# P14-46: benchmark glue
# --------------------------------------------------------------------------------------------------

KT_PHRASES = ["hello world", "thank you", "good morning", "see you soon", "i am fine"]


def _fake_kt(root: Path, n_runs: int = 12, with_csv: bool = False) -> Path:
    rng = np.random.default_rng(0)
    root.mkdir(parents=True, exist_ok=True)
    for r in range(1, n_runs + 1):
        (root / f"run{r}_ts.txt").write_text(f"2020-09-{r:02d} 10:00:00.000", encoding="ascii")
        t = 1_600_000_000.0 + r * 100_000 + 5
        lines = []
        for _ in range(4):
            for ch in str(rng.choice(KT_PHRASES)):
                lines.append(f"{ch} {t:.6f}")
                t += 0.3
            t += 5.0
        (root / f"run{r}_keys.txt").write_bytes(("\n".join(lines) + "\n").encode("latin-1"))
        if with_csv:
            (root / f"run{r}.csv").write_text("Time\tc1\n0\t1\n", encoding="ascii")
    return root


def test_build_truth_with_split_and_key_logs_only(tmp_path):
    from fidetype.benchmark import scorecard as SC
    from fidetype.benchmark import tracks as TR

    keys_only = _fake_kt(tmp_path / "keys")
    full = _fake_kt(tmp_path / "full", with_csv=True)
    with pytest.raises(FileNotFoundError):
        TR.local_units("kt-semg", keys_only)  # the default loader still needs the CSVs (verify)
    split = TR.make_split("kt-semg", TR.local_units("kt-semg", keys_only, keys_only=True))
    rows = SC.build_truth("kt-semg", keys_only, split=split)
    assert len(rows) == split["counts"]["segment"]["test"] == 24
    assert all(r["neural_s"] > 0 and r["text"].startswith("Key") for r in rows)
    # same segment truth with or without the CSVs (only run payloads differ)
    split_full = TR.make_split("kt-semg", TR.local_units("kt-semg", full))
    rows_full = SC.build_truth("kt-semg", full, split=split_full)
    strip = [{k: v for k, v in r.items()} for r in rows_full]
    assert [(r["unit"], r["text"], r["neural_s"]) for r in rows] == [(r["unit"], r["text"], r["neural_s"])
                                                                     for r in strip]
    # a split of another track is refused
    with pytest.raises(ValueError, match="track"):
        SC.build_truth("kt-semg", keys_only, split=dict(split, track="willett-hw"))


def test_guarantee_from_sheet_is_a_valid_submission_guarantee():
    from fidetype.benchmark import scorecard as SC
    from fidetype.benchmark.safe_wpm import SHEET_SCOPE, guarantee_from_sheet
    from fidetype.benchmark.submission import validate_guarantee

    sheet = {"alpha": 0.05, "delta": 0.1, "n_ltt": 120, "n_items": 300, "n_fit": 60, "n_policy": 120,
             "feasible": True, "config_id": "tcfg-x", "controls": []}
    g = guarantee_from_sheet(sheet)
    assert g["scope"] == SHEET_SCOPE and "300 items" in g["calibration_split"]
    validate_guarantee(g)
    g2 = guarantee_from_sheet(sheet, calibration_split="cal", scope="marginal over test units, exchangeable")
    assert g2["calibration_split"] == "cal" and g2["scope"].startswith("marginal over test units")
    SC.manifest_dict("kt-semg", {"name": "x", "version": "0", "weights_licence": "none"}, guarantee=g2,
                     regime="cross-session")


def test_track_space_nbest_and_converter(tmp_path):
    from fidetype.adapters import kt_semg as K
    from fidetype.benchmark.registry import normalize

    m, st = _key_model(tmp_path)
    nb = m.track_nbest(st, n_best=4)
    assert nb[0]["text"] == " ".join(K.greedy_codes(st))
    assert len(nb) == 4 and all(len(c["text"].split()) == st.log_probs.shape[0] for c in nb)
    assert all(a["score"] >= b["score"] for a, b in zip(nb, nb[1:]))
    assert all(set(c["text"].split()) <= set(K.KEY_VOCAB) for c in nb)
    # a stream that types "ab<Backspace>": the codes keep the Backspace, the screen text does not
    lp = np.full((3, len(K.KEY_VOCAB)), -10.0)
    for i, code in enumerate(["KeyA", "KeyB", "Backspace"]):
        lp[i, K.KEY_VOCAB.index(code)] = -0.01
    s3 = K.keypress_stream(lp, [0.1, 0.2, 0.3])
    assert K.code_nbest(s3)[0]["text"] == "KeyA KeyB Backspace"
    assert K.codes_from_text("Hi you!") == ["KeyH", "KeyI", "Space", "KeyY", "KeyO", "KeyU", "?"]
    assert normalize(" ".join(K.codes_from_text("hello world")), "keycodes") == "hello world"


def test_committed_cards_ship_in_the_package():
    from fidetype.benchmark import leaderboard as LB

    d = LB.results_dir("v0.2")
    assert d.is_dir() and any(d.glob("kt-semg__*.json"))
    assert len(LB.committed_results("v0.2")) >= 1 and LB.results_dir("v0.1").is_dir()
    with pytest.raises(ValueError, match="unknown card version"):
        LB.results_dir("v9")
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]
    fi = cfg["wheel"]["force-include"]
    assert fi["benchmark/results/v0.2"] == "fidetype/_benchmark/results/v0.2"
    assert fi["benchmark/results/v0.1"] == "fidetype/_benchmark/results/v0.1"
    assert "/benchmark/results/v0.2/*.json" in cfg["sdist"]["include"]  # the wheel from the sdist needs them
