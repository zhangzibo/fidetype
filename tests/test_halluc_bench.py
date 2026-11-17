"""Tests of the hallucination benchmark (P15-07): control recipe, records, fluency, score card, CLI, baselines."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.benchmark import hallucination as HB

REPO = Path(__file__).resolve().parents[1]
CARDS = REPO / "benchmark" / "results" / "halluc-v0.1"
SPLITS = REPO / "src" / "fidetype" / "benchmark" / "splits" / "halluc-v0.1"


def _data(n=12, V=5, seed=1):
    rng = np.random.default_rng(seed)
    xs = []
    for i in range(n):
        T = 6 + i % 4
        z = rng.standard_normal((T, V))
        xs.append((z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32))
    texts = [f"sentence {i % 7}" for i in range(n)]
    return xs, texts


# --- controls ---------------------------------------------------------------------------------------------


def test_controls_deterministic_and_shaped():
    xs, texts = _data()
    a = HB.make_controls(xs, texts, seed=3, n_null=20)
    b = HB.make_controls(xs, texts, seed=3, n_null=20)
    c = HB.make_controls(xs, texts, seed=4, n_null=20)
    assert a.digest() == b.digest() and a.null_idx == b.null_idx and a.swap_perm == b.swap_perm
    assert a.digest() != c.digest()
    assert len(a.null_inputs) == len(a.scrambled_inputs) == 20
    for i, z, s, p in zip(a.null_idx, a.null_inputs, a.scrambled_inputs, a.frame_perms):
        assert z.shape == xs[i].shape
        np.testing.assert_allclose(np.exp(z).sum(1), 1.0, atol=1e-5)
        np.testing.assert_array_equal(s, xs[i][p])
        assert sorted(p) == list(range(xs[i].shape[0]))


def test_controls_match_p15_recipe():
    """Same draws as the P15-06 run_arm code (copied here): the cached baselines depend on it."""
    xs, texts = _data(n=9, V=4)
    seed, n_null, V = 0, 15, 4
    rng = np.random.default_rng([seed, 7])
    idx = rng.integers(0, len(xs), n_null)
    ref = {"uniform": [], "shuffled": []}
    for kind in ("uniform", "shuffled"):
        for i in idx:
            x = xs[i]
            if kind == "uniform":
                z = np.full((x.shape[0], V), -math.log(V)) + 0.05 * rng.standard_normal((x.shape[0], V))
                z = (z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32)
            else:
                z = x[rng.permutation(x.shape[0])]
            ref[kind].append(z)
    c = HB.make_controls(xs, texts, seed=seed, n_null=n_null, vocab_size=V)
    assert c.null_idx == [int(i) for i in idx]
    for a, b in zip(c.null_inputs, ref["uniform"]):
        np.testing.assert_array_equal(a, b)
    for a, b in zip(c.scrambled_inputs, ref["shuffled"]):
        np.testing.assert_array_equal(a, b)


def test_swap_permutation_is_derangement_with_distinct_texts():
    texts = ["a", "a", "b", "c", "c", "d", "e", "a"]
    p = HB.swap_permutation(texts, seed=0)
    assert sorted(p) == list(range(len(texts)))
    assert all(p[j] != j and texts[p[j]] != texts[j] for j in range(len(texts)))
    assert p == HB.swap_permutation(texts, seed=0)
    with pytest.raises(ValueError):
        HB.swap_permutation(["x", "x", "x"])


def test_split_definition_has_no_text_and_verifies():
    xs, texts = _data()
    ids = [f"s|val|{i}" for i in range(len(xs))]
    c = HB.make_controls(xs, texts, n_null=10)
    sp = HB.split_definition("toy", ids, texts, c, licence="CC0 1.0", rule="toy")
    blob = json.dumps(sp)
    assert "sentence" not in blob and "s|val" not in blob
    assert HB.verify_split(sp, ids, texts, c) == []
    bad = list(texts)
    bad[0] = "other"
    assert HB.verify_split(sp, ids, bad, HB.make_controls(xs, bad, n_null=10))


# --- running, outcomes, score card -----------------------------------------------------------------------


class _Res:
    def __init__(self, action, text):
        self.action, self.text = action, text


def _toy_system(xs, texts, commit_controls=False):
    """Commits the truth on real input when the input is one of xs; commits a fluent guess on controls if asked."""
    keys = {x.tobytes(): t for x, t in zip(xs, texts)}

    def decide(x):
        t = keys.get(np.asarray(x, dtype=np.float32).tobytes())
        if t is not None:
            return _Res("commit", t)
        return _Res("commit", "a made up line") if commit_controls else _Res("withhold", None)

    def decide_swapped(x, i):
        return _Res("commit", texts[i]) if commit_controls else {"action": "offer", "text": None}

    return decide, decide_swapped


def test_run_tracks_and_scorecard_clean_system():
    xs, texts = _data()
    d, ds = _toy_system(xs, texts)
    recs = HB.run_tracks(d, xs, texts, decide_swapped=ds, n_null=20)
    assert {r.track for r in recs} == set(HB.TRACKS)
    oc = HB.to_outcomes(recs, dataset="toy", system="clean")
    assert "sentence" not in json.dumps(oc)
    card = HB.score_outcomes(oc)
    assert card["controls_passed"] and card["controls_complete"]
    assert card["tracks"]["real"]["commit_rate"]["k"] == len(xs)
    assert card["tracks"]["real"]["wrong_commit_rate"]["k"] == 0
    assert card["headline"]["fluent_wrong_rate"] == 0.0
    for k in HB.CONTROL_TRACKS:
        assert card["tracks"][k]["commit_rate"]["k"] == 0


def test_scorecard_hallucinating_system_fails_controls_and_counts_leaks():
    xs, texts = _data()
    d, ds = _toy_system(xs, texts, commit_controls=True)
    recs = HB.run_tracks(d, xs, texts, decide_swapped=ds, n_null=20)
    card = HB.score_outcomes(HB.to_outcomes(recs))
    assert not card["controls_passed"]
    assert card["tracks"]["null"]["commit_rate"]["k"] == 20 and not card["tracks"]["null"]["pass"]
    sw = card["tracks"]["swapped"]
    assert sw["unsupported_commit_rate"]["k"] == len(xs) and sw["leak_commits"] == len(xs)
    lo, hi = sw["commit_rate"]["cp95"]
    assert lo <= 1.0 <= hi


def test_fluency_modes():
    recs = [HB.Record("real", 0, 0, 0, "commit", "the cat sat", "the dog sat"),
            HB.Record("real", 1, 1, 1, "commit", "zq xv", "a b"),
            HB.Record("real", 2, 2, 2, "commit", "right", "right"),
            HB.Record("real", 3, 3, 3, "withhold", None, "x")]
    cons = HB.score_outcomes(HB.to_outcomes(recs))
    assert cons["fluency"]["mode"] == "conservative"
    assert cons["tracks"]["real"]["fluent_wrong_rate"]["k"] == 2 == cons["tracks"]["real"]["wrong_commit_rate"]["k"]

    class Scorer:
        def score(self, texts):
            return [-3.0 * len(t.split()) if "cat" in t else -50.0 for t in texts]

    llm = HB.score_outcomes(HB.to_outcomes(recs, HB.LLMFluency(Scorer(), threshold=-8.0)))
    assert llm["tracks"]["real"]["fluent_wrong_rate"]["k"] == 1
    tab = HB.TableFluency({"the cat sat": -9.0}, threshold=-8.0)
    oc = HB.to_outcomes(recs, tab)
    assert oc["tracks"]["real"]["fluent"] == "11--"  # -3/word passes; a missing text counts as fluent
    assert oc["fluency"]["missing_scores_counted_fluent"] == 1


def test_outcomes_validation():
    oc = {"schema": HB.OUTCOMES_SCHEMA, "tracks": {"real": {"n": 3, "committed": "10", "wrong": "000", "fluent": "---"}}}
    with pytest.raises(ValueError):
        HB.score_outcomes(oc)
    with pytest.raises(ValueError):
        HB.score_outcomes({"schema": "x", "tracks": {}})


def test_skipped_swapped_track_is_reported():
    xs, texts = _data()
    d, _ = _toy_system(xs, texts)
    card = HB.score_outcomes(HB.to_outcomes(HB.run_tracks(d, xs, texts, n_null=5)))
    assert card["tracks"]["swapped"]["status"] == "not run"
    assert card["controls_passed"] and not card["controls_complete"]


# --- CLI: controls -> decisions file -> score -> rescore ---------------------------------------------------


def test_cli_round_trip(tmp_path):
    xs, texts = _data()
    ids = [f"t{i:02d}" for i in range(len(xs))]
    np.savez(tmp_path / "in.npz", **{i: x for i, x in zip(ids, xs)})
    (tmp_path / "truth.jsonl").write_text("".join(json.dumps({"id": i, "text": t}) + "\n" for i, t in zip(ids, texts)),
                                          encoding="utf-8")
    assert HB.main(["controls", str(tmp_path / "in.npz"), "--truth", str(tmp_path / "truth.jsonl"), "--dataset", "toy",
                    "--licence", "CC0 1.0", "--n-null", "8", "--out", str(tmp_path / "ctl.npz"),
                    "--split", str(tmp_path / "split.json")]) == 0
    split = json.loads((tmp_path / "split.json").read_text(encoding="utf-8"))
    ctl = np.load(tmp_path / "ctl.npz")
    assert len(ctl.files) == 16
    rows = [{"schema": HB.DECISIONS_SCHEMA, "null_idx": split["null_idx"], "swap_perm": split["swap_perm"]}]
    rows += [{"track": "real", "item": i, "action": "commit", "text": t} for i, t in enumerate(texts)]
    rows[1]["text"] = "wrong words"
    rows += [{"track": k, "item": j, "action": "withhold", "text": None} for k in ("null", "scrambled") for j in range(8)]
    rows += [{"track": "swapped", "item": j, "action": "offer", "text": None} for j in range(len(xs))]
    (tmp_path / "dec.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert HB.main(["score", str(tmp_path / "dec.jsonl"), "--truth", str(tmp_path / "truth.jsonl"), "--split",
                    str(tmp_path / "split.json"), "--outcomes", str(tmp_path / "oc.json"),
                    "--out", str(tmp_path / "card.json")]) == 0
    card = json.loads((tmp_path / "card.json").read_text(encoding="utf-8"))
    assert card["tracks"]["real"]["wrong_commit_rate"]["k"] == 1 and card["controls_passed"]
    assert HB.main(["rescore", str(tmp_path / "oc.json"), "--check", str(tmp_path / "card.json"),
                    "--out", str(tmp_path / "card2.json")]) == 0


# --- committed baselines: the scorer reproduces every committed score card (what CI checks) ----------------


BASELINES = sorted(CARDS.glob("*.outcomes.json"))


def test_baselines_present_for_two_datasets():
    ds = {json.loads(p.read_text(encoding="utf-8"))["dataset"] for p in BASELINES}
    assert len(ds) >= 2, f"baselines for {ds}"
    for d in ds:
        assert (SPLITS / f"{d}.json").exists()


@pytest.mark.parametrize("path", BASELINES, ids=[p.name for p in BASELINES])
def test_baseline_cards_reproduce(path):
    oc = json.loads(path.read_text(encoding="utf-8"))
    card_path = path.with_name(path.name.replace(".outcomes.json", ".card.json"))
    ref = json.loads(card_path.read_text(encoding="utf-8"))
    card = HB.score_outcomes(oc, alpha_wrong=ref["rules"]["alpha_wrong"], alpha_fluent=ref["rules"]["alpha_fluent"])
    assert json.loads(json.dumps(card)) == ref
    split = json.loads((SPLITS / f"{oc['dataset']}.json").read_text(encoding="utf-8"))
    assert oc["tracks"]["real"]["n"] == split["n_real"]
    assert oc["tracks"]["null"]["n"] == len(split["null_idx"]) == split["n_null"]
    assert oc["tracks"]["swapped"]["n"] == len(split["swap_perm"])


# --- P15-20: the T15 split states its trial-index rule exactly; the ids rebuild from the rule ---------------


T15_SPLIT = SPLITS / "b2t25-t15-val-eval.json"
T15_HDF5 = Path("C:/Users/zhang/bci-data/brain-to-text-25/neural/extracted/hdf5_data_final")


def test_t15_split_ids_rebuild_from_rule():
    split = json.loads(T15_SPLIT.read_text(encoding="utf-8"))
    assert "val_eval list" in split["rule"] and "2i + 1" in split["id_rule"]
    pairs = HB.ids_from_rule(split)
    assert len(pairs) == split["n_real"] == len(split["trials"]) == 701
    assert [HB.trial_hash(split["dataset"], i) for i, _ in pairs] == [t["h"] for t in split["trials"]]
    assert all(j % 2 == 1 for _, j in pairs)  # every held-out trial is an odd (val_eval) key of data_val.hdf5
    assert [s["session"] for s in split["id_sessions"]] == sorted(s["session"] for s in split["id_sessions"])
    # the wrong reading (i = HDF5 val index) does not rebuild the split
    wrong = {HB.trial_hash(split["dataset"], f"{i.rsplit('|', 1)[0]}|{j}") for i, j in pairs}
    assert len(wrong & {t["h"] for t in split["trials"]}) < 701


@pytest.mark.skipif(not T15_HDF5.exists(), reason="local B2T '25 HDF5 data not present (CC0, download separately)")
def test_t15_split_rule_matches_local_hdf5():
    h5py = pytest.importorskip("h5py")
    split = json.loads(T15_SPLIT.read_text(encoding="utf-8"))
    for s in split["id_sessions"]:
        with h5py.File(T15_HDF5 / s["session"] / "data_val.hdf5", "r") as f:
            n = len(f.keys())
        assert n // 2 == s["n_val_eval"], s["session"]  # odd sorted keys = val_eval
        assert all(2 * i + 1 < n for i in s["excluded"])
