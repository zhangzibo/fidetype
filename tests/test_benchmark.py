"""Tests of the open benchmark v0.1 (fidetype.benchmark). CPU only, no data."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.benchmark import DATASETS, TRACKS, get_track
from fidetype.benchmark import harness as H
from fidetype.benchmark.leaderboard import build as build_board
from fidetype.benchmark.prepare import TruthTrial, text_hash
from fidetype.benchmark.registry import normalize
from fidetype.benchmark.scoring import (
    bootstrap_ci,
    bootstrap_weights,
    build_result,
    control_block,
    score_trials,
    weighted_metrics,
    arrays,
)
from fidetype.benchmark.splits import SplitFile, load_split, make_split, verify
from fidetype.benchmark.submission import (
    Manifest,
    SubmissionError,
    TrialOutput,
    trial_output,
    write_manifest,
    write_trial,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {
    "spanishbcbl-meg-async": {"train": 4026, "val": 437, "test": 637},
    "b2t25-t15-copytask": {"cal": 812, "test": 816},
    "toronto-semg-composed": {"cal": 570, "test": 551},
}


# --- registry and split files ------------------------------------------------------


def test_registry_entries_are_complete():
    for slug, t in TRACKS.items():
        assert t.dataset in DATASETS
        ds = DATASETS[t.dataset]
        assert ds.licence and ds.url.startswith("https://") and ds.download and ds.version
        assert t.user_model.config["chars_per_min"] > 0
    assert DATASETS["spanishbcbl"].non_commercial and TRACKS["spanishbcbl-meg-async"].research_only
    assert not DATASETS["brain-to-text-25"].non_commercial
    assert DATASETS["brain-to-text-25"].files[0]["sha256"].startswith("7313b9a1")


@pytest.mark.parametrize("track", sorted(TRACKS))
def test_split_files_hold_no_text_and_match_counts(track):
    sp = load_split(track)
    assert sp.counts == EXPECTED_COUNTS[track]
    t = get_track(track)
    ids = [r["id"] for r in sp.scored]
    assert len(ids) == len(set(ids))
    keys = t.ci_unit.split(":", 1)[1].split(",") if t.ci_unit.startswith("two_way:") else [t.ci_unit]
    for r in sp.scored:
        assert set(r) <= {"id", "split", "text_sha256", "clusters", "detail_sha256"}  # never the text
        assert len(r["text_sha256"]) == 64
        assert all(k in r["clusters"] for k in keys)
    raw = sp.to_dict()
    assert "text" not in json.dumps(raw["scored"][:5]).replace("text_sha256", "")


def test_meg_split_has_17_test_sentences_and_19_participants():
    sp = load_split("spanishbcbl-meg-async")
    test = sp.trials("test")
    assert len({r["clusters"]["sentence"] for r in test}) == 17
    assert len({r["clusters"]["participant"] for r in test}) == 19
    # Split by sentence: no test sentence group in val.
    assert not ({r["clusters"]["sentence"] for r in test} & {r["clusters"]["sentence"] for r in sp.trials("val")})


def _trials(n=6, split="test"):
    return [TruthTrial(f"P{i % 3 + 1}-{split}-{i:02d}", split, f"hello world number {i}", {"participant": f"P{i % 3 + 1}"})
            for i in range(n)]


def test_make_split_and_verify_roundtrip(tmp_path):
    tr = _trials(6) + _trials(4, "cal")
    sp = make_split("toronto-semg-composed", tr, ("cal", "test"), rule="synthetic")
    p = tmp_path / "s.json"
    sp.save(p)
    sp2 = SplitFile.from_dict(json.loads(p.read_text(encoding="utf-8")))
    assert sp2.counts == {"cal": 4, "test": 6}
    assert verify(sp2, tr).ok
    bad = [TruthTrial(t.id, t.split, t.text + "x", t.clusters) for t in tr]
    rep = verify(sp2, bad)
    assert not rep.ok and len(rep.text_mismatch) == 10
    assert not verify(sp2, tr[1:]).ok


def test_normalizers():
    assert normalize("¡Él  está aquí!", "char28") == "el esta aqui"
    assert normalize("That's   Fine.", "words") == "that's fine"
    assert normalize(" a  b ", "none") == "a b"


# --- submission format -----------------------------------------------------------------


def _stream(text="hello world", seed=0):
    from fidetype.adapters import toronto_semg as T

    rng = np.random.default_rng(seed)
    lg = rng.standard_normal((len(text), len(T.KEY_VOCAB)))
    for i, c in enumerate(text):
        lg[i, T.KEY_CHARS.index(c)] += 5.0
    meta = T.stream_meta("P1", "T2", decoder_name="test-decoder", personalized=True, composed=True)
    return T.to_ctc_char_stream(T.keypress_stream(lg, T.compose_times(len(text), 0.79), meta))


def test_write_and_read_trial(tmp_path):
    p = tmp_path / "x.jsonl"
    write_trial(p, _stream(), ["hello world", "hello word"], [0.7, 0.2], action="offer", offer_k=2,
                score_semantics="calibrated_prob")
    o = trial_output(p)
    assert o.texts == ["hello world", "hello word"] and o.action == "offer" and o.offer_k == 2
    assert o.score == 0.7 and o.score_semantics == "calibrated_prob"
    from fidetype.conformance import check_file

    rep = check_file(p, truth=["hello world"])
    assert "trust-ready" in rep.levels  # hypothesis text may equal the truth; the header must not


def test_stream_without_hypothesis_is_greedy_commit(tmp_path):
    p = tmp_path / "y.npz"
    _stream("abc def").to_npz(p)
    o = trial_output(p)
    assert o.action == "commit" and not o.from_hypothesis and o.top1 == "abc def"


def test_manifest_validation():
    ok = {"schema": "fidetype.benchmark.submission/0.1", "track": "b2t25-t15-copytask",
          "decoder": {"name": "d", "weights_licence": "MIT"}}
    Manifest.from_dict(ok)
    with pytest.raises(SubmissionError):
        Manifest.from_dict({**ok, "decoder": {"name": "d"}})
    with pytest.raises(SubmissionError):
        Manifest.from_dict({**ok, "guarantee": {"method": "crc", "alpha": 0.05}})  # no n_cal, no scope
    with pytest.raises(SubmissionError):
        Manifest.from_dict({**ok, "guarantee": {"method": "ltt", "alpha": 0.05, "n_cal": 10, "scope": "x"}})  # no delta
    Manifest.from_dict({**ok, "guarantee": {"method": "crc", "alpha": 0.05, "n_cal": 10, "scope": "marginal"}})


# --- scoring ------------------------------------------------------------------------------


def _score(action, texts_fn, n=12, track="toronto-semg-composed"):
    ids = [f"P{i % 4 + 1}-test-{i:02d}" for i in range(n)]
    truth = {i: f"the quick brown fox {k}" .replace(str(k), "jumps" if k % 2 else "runs") for k, i in enumerate(ids)}
    clusters = {i: {"participant": i.split("-")[0]} for i in ids}
    outs = {i: TrialOutput(i, texts_fn(truth[i]), action, 3) for i in ids}
    return score_trials(track, outs, truth, clusters, ids)


def test_perfect_commit_beats_gaze_and_has_no_errors():
    s = _score("commit", lambda t: [t])
    m = weighted_metrics(arrays(s, 20.0))
    assert m["cer"] == 0 and m["wer"] == 0 and m["wrong_commit_rate"] == 0 and m["commit_rate"] == 1
    assert m["error_among_commits"] == 0 and m["ewpm"] > m["gaze_ewpm"]


def test_wrong_commits_and_error_among_commits():
    s = _score("commit", lambda t: [t + " extra"])
    m = weighted_metrics(arrays(s, 20.0))
    assert m["wrong_commit_rate"] == 1 and m["error_among_commits"] == 1 and m["cer"] > 0


def test_offer_and_abstain_never_count_as_commits():
    for action in ("offer", "abstain"):
        s = _score(action, lambda t: [t + " x", t])
        m = weighted_metrics(arrays(s, 20.0))
        assert m["commit_rate"] == 0 and m["wrong_commit_rate"] == 0 and math.isnan(m["error_among_commits"])
    off = weighted_metrics(arrays(_score("offer", lambda t: ["zzz", t]), 20.0))
    assert off["ewpm"] > 0  # the user selects the second candidate


def test_bootstrap_units():
    rng = np.random.default_rng(0)
    cl = [{"sentence": f"s{i % 3}", "participant": f"p{i % 4}"} for i in range(24)]
    for unit in ("trial", "sentence", "participant", "two_way:sentence,participant"):
        w = bootstrap_weights(rng, unit, cl)()
        assert w.shape == (24,) and (w >= 0).all()
    s = bootstrap_weights(rng, "sentence", cl)()
    assert all(s[i] == s[i % 3] for i in range(24))  # whole clusters are resampled
    x = np.arange(24, dtype=float)
    ci = bootstrap_ci(lambda w: {"m": float((x * w).sum() / w.sum())}, "participant", cl, B=200)
    assert ci["m"][0] < x.mean() < ci["m"][1]
    with pytest.raises(ValueError):
        bootstrap_weights(rng, "day", cl)


def test_control_block():
    real = _score("commit", lambda t: [t])
    worse = _score("abstain", lambda t: ["qqqq qqqq"])
    c = control_block(real, {"shuffled": worse, "zeros": worse}, "participant", B=200)
    assert c["shuffled"]["status"] == "pass" and c["zeros"]["status"] == "pass"
    assert c["null_commit"]["status"] == "pass" and c["passed"]
    same = control_block(real, {"shuffled": real, "zeros": real}, "participant", B=200)
    assert same["shuffled"]["status"] == "fail" and same["null_commit"]["status"] == "fail" and not same["passed"]
    miss = control_block(real, {}, "participant", B=50)
    assert miss["shuffled"]["status"] == "missing" and not miss["passed"]


def test_guarantee_reporting():
    s = _score("commit", lambda t: [t])
    r = build_result("toronto-semg-composed", s, decoder={"name": "d", "weights_licence": "x"}, policy={"name": "p"},
                     guarantee={"method": "crc", "alpha": 0.05, "n_cal": 999, "scope": "marginal",
                                "calibration_split": "cal"}, B=100, n_cal_split=570)
    g = r["guarantee"]
    assert g["method"] == "crc" and g["met_on_test"] is True and "warning" in g
    assert r["metrics"]["ewpm"]["ci"] is not None


# --- end to end: one submission folder ----------------------------------------------------------


def test_score_submission_end_to_end(tmp_path, monkeypatch):
    texts = ["hello world", "good morning", "see you soon", "thank you", "how are you", "i am fine"]
    trials = [TruthTrial(f"P{k % 3 + 1}-test-{k:02d}", "test", t, {"participant": f"P{k % 3 + 1}"})
              for k, t in enumerate(texts)]
    sp = make_split("toronto-semg-composed", trials, ("test",), rule="synthetic")
    monkeypatch.setattr(H, "load_split", lambda track: sp)
    truth = tmp_path / "truth.jsonl"
    truth.write_text("".join(json.dumps(t.to_dict()) + "\n" for t in trials), encoding="utf-8")
    sub = tmp_path / "sub"
    for k, tr in enumerate(trials):
        hyp = tr.text if k % 2 == 0 else tr.text[:-1] + "x"
        action = "commit" if k % 2 == 0 else "offer"
        write_trial(sub / "streams" / f"{tr.id}.jsonl", _stream(tr.text, k), [hyp, tr.text], [0.9, 0.1],
                    action=action, score_semantics="calibrated_prob")
        for kind in ("shuffled", "zeros"):
            write_trial(sub / "controls" / kind / f"{tr.id}.jsonl", _stream(tr.text, k), ["zzz zzz"], [0.01],
                        action="abstain", score_semantics="calibrated_prob")
    write_manifest(sub, Manifest(track="toronto-semg-composed", decoder={"name": "unit-test", "weights_licence": "MIT"},
                                 policy={"name": "half commit"}))
    res = H.score_submission(sub, truth, B=200)
    assert res["status"] == "scored" and res["conformance"]["passed"]
    assert res["conformance"]["level"] in ("trust-ready", "provenance")
    m = res["metrics"]
    assert m["commit_rate"]["value"] == 0.5 and m["wrong_commit_rate"]["value"] == 0
    assert m["error_among_commits"]["value"] == 0 and m["cer"]["value"] > 0
    assert res["controls"]["passed"]
    out = tmp_path / "results"
    out.mkdir()
    (out / "r.json").write_text(json.dumps(res), encoding="utf-8")
    info = build_board(out, tmp_path / "site")
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert info["n_results"] == 1 and "unit-test" in html and "No-BCI reference" in html
    # A truth file that does not match the split hashes is refused.
    bad = tmp_path / "bad.jsonl"
    bad.write_text("".join(json.dumps({**t.to_dict(), "text": t.text + "!"}) + "\n" for t in trials), encoding="utf-8")
    with pytest.raises(SubmissionError):
        H.score_submission(sub, bad, B=50)
    # A missing stream file is refused.
    next((sub / "streams").iterdir()).unlink()
    with pytest.raises(SubmissionError):
        H.score_submission(sub, truth, B=50)


def test_cli_tracks_and_info(capsys):
    from fidetype.benchmark.__main__ import main

    assert main(["tracks"]) == 0
    assert "b2t25-t15-copytask" in capsys.readouterr().out
    assert main(["info", "spanishbcbl-meg-async"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["dataset"]["licence"] == "CC BY-NC 4.0" and info["split_counts"]["test"] == 637


# --- committed results and licence hygiene (M5-03) ------------------------------------------------


def test_committed_results_build_a_board(tmp_path):
    res_dir = ROOT / "benchmark" / "results" / "v0.1"
    if not res_dir.exists():
        pytest.skip("no committed results")
    info = build_board(res_dir, tmp_path)
    assert all(info["tracks"][t] >= 1 for t in TRACKS)  # baselines on all three tracks
    for p in res_dir.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["scored_from"] in ("stream-submission", "committed-per-trial", "committed-aggregate")
        assert d["decoder"].get("weights_licence")


def test_spanishbcbl_is_marked_non_commercial():
    from fidetype.adapters.spanishbcbl_meg import stream_meta
    from fidetype.data import spanishbcbl as S

    assert S.LICENCE == "CC-BY-NC-4.0" and S.NON_COMMERCIAL and "huggingface.co" in S.SOURCE_URL
    assert "research" in S.licence_notice()
    import inspect

    assert "spanishbcbl.licence" in inspect.getsource(stream_meta)


def test_no_data_or_weights_in_package_or_benchmark():
    bad_suffixes = {".npz", ".npy", ".pt", ".ckpt", ".pkl", ".fif", ".mat", ".h5", ".safetensors", ".onnx", ".rhd"}
    for folder in (ROOT / "src", ROOT / "benchmark"):
        if folder.exists():
            hits = [p for p in folder.rglob("*") if p.suffix.lower() in bad_suffixes]
            assert not hits, hits[:5]
