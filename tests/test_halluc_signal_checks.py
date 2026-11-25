"""Tests of the opt-in signal-check tracks of the hallucination benchmark (P15-56): truncated, noise mix, near miss.

Pins: the recipe (seeds, shapes, nesting), the unsupported definitions, the paired verdicts, the CLI round trip,
and that the existing tracks, outcomes and committed score cards do not change.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fidetype.benchmark import hallucination as HB

REPO = Path(__file__).resolve().parents[1]
V01 = REPO / "benchmark" / "results" / "halluc-v0.1"
V02 = REPO / "benchmark" / "results" / "halluc-v0.2"
P1556 = REPO / "experiments" / "2026-11-25-p15-56-signal-check-tracks" / "results"


def _data(n=12, V=5, seed=1):
    rng = np.random.default_rng(seed)
    xs = []
    for i in range(n):
        T = 6 + i % 4
        z = rng.standard_normal((T, V))
        xs.append((z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32))
    texts = [f"the sentence number {i % 7} here" if i % 3 else f"word{i}" for i in range(n)]
    return xs, texts


# --- recipe ------------------------------------------------------------------------------------------------


def test_keys_and_families():
    assert HB.signal_track_keys() == ["truncated_25", "truncated_50", "truncated_75", "noise_mix_25",
                                      "noise_mix_50", "noise_mix_75", "near_miss"]
    assert HB.signal_family("truncated_50") == "truncated"
    assert HB.signal_family("noise_mix_75") == "noise_mix"
    assert HB.signal_family("near_miss") == "near_miss"
    for k in HB.TRACKS:
        assert HB.signal_family(k) is None


def test_truncate_lengths():
    x = np.zeros((10, 3), dtype=np.float32)
    assert [HB.truncate_input(x, f).shape[0] for f in (0.25, 0.5, 0.75)] == [3, 5, 8]
    assert HB.truncate_input(np.zeros((1, 3)), 0.25).shape[0] == 1
    assert HB.truncate_input(np.zeros((4, 3)), 0.25).shape[0] == 1


def test_signal_checks_deterministic_and_shaped():
    xs, texts = _data()
    a = HB.make_signal_checks(xs, texts, seed=3)
    b = HB.make_signal_checks(xs, texts, seed=3)
    c = HB.make_signal_checks(xs, texts, seed=4)
    assert a.digest() == b.digest() and a.near_miss == b.near_miss
    assert a.digest() != c.digest()
    assert a.tracks() == HB.signal_track_keys()
    for k in a.truncated:
        for x, z in zip(xs, a.inputs(k)):
            np.testing.assert_array_equal(z, x[: z.shape[0]])
    for k in a.noise_mix:
        for x, z in zip(xs, a.inputs(k)):
            assert z.shape == x.shape and z.dtype == np.float32
            np.testing.assert_allclose(np.exp(z.astype(np.float64)).sum(1), 1.0, atol=1e-5)


def test_noise_mix_recipe_and_nesting():
    """One noise matrix per item from default_rng([seed, 13]), shared by the levels (copied recipe)."""
    xs, texts = _data(n=5, V=4)
    sc = HB.make_signal_checks(xs, texts, seed=0)
    rng = np.random.default_rng([0, 13])
    for j, x in enumerate(xs):
        q = np.full(x.shape, -math.log(4)) + 0.05 * rng.standard_normal(x.shape)
        q = q - np.log(np.exp(q).sum(1, keepdims=True))
        px = np.exp(x.astype(np.float64))
        px = px / px.sum(1, keepdims=True)
        for lam in HB.NOISE_LEVELS:
            ref = np.log((1 - lam) * px + lam * np.exp(q))
            np.testing.assert_allclose(sc.inputs(HB.noise_mix_key(lam))[j], ref, rtol=1e-5, atol=1e-5)
    # more noise: each frame is closer to the noise matrix (max prob shrinks toward 1/V on average)
    m = [np.mean([np.exp(z).max(1).mean() for z in sc.inputs(HB.noise_mix_key(v))]) for v in HB.NOISE_LEVELS]
    assert m[0] > m[1] > m[2]
    # lam = 1 gives a null-type input; lam = 0 the signal
    q = HB.noise_matrix(np.random.default_rng(0), 6, 4)
    np.testing.assert_allclose(HB.mix_noise(xs[0][:6], q, 1.0), q, atol=1e-5)
    q0 = HB.noise_matrix(np.random.default_rng(0), xs[0].shape[0], 4)
    np.testing.assert_allclose(HB.mix_noise(xs[0], q0, 0.0), xs[0], atol=1e-5)


def test_noise_mix_width_check():
    xs, texts = _data(n=3, V=4)
    with pytest.raises(ValueError):
        HB.make_signal_checks(xs, texts, vocab_size=5)


def test_near_miss_texts_edit_count():
    xs, texts = _data(n=40)
    nm, ed = HB.near_miss_texts(texts, seed=0)
    pool = set(HB.word_pool(texts))
    for t, v, e in zip(texts, nm, ed):
        a, b = t.split(), v.split()
        assert len(a) == len(b)
        diff = sum(x != y for x, y in zip(a, b))
        assert diff == e and e in (1, 2)
        if len(a) == 1:
            assert e == 1
        assert set(b) <= pool
    assert 1 in ed and 2 in ed
    assert HB.near_miss_texts(texts, seed=0) == (nm, ed)
    assert HB.near_miss_texts(texts, seed=1)[0] != nm


def test_near_miss_recipe_copy():
    """The documented draw order (copied here)."""
    texts = ["a b c", "d e", "f", "a d f"]
    rng = np.random.default_rng([0, 17])
    pool = sorted({w for t in texts for w in t.split()})
    ref = []
    for t in texts:
        w = t.split()
        e = 1 if len(w) == 1 else 1 + int(rng.integers(0, 2))
        pos = sorted(int(p) for p in rng.choice(len(w), e, replace=False))
        out = list(w)
        for p in pos:
            while True:
                c = pool[int(rng.integers(0, len(pool)))]
                if c != w[p]:
                    break
            out[p] = c
        ref.append(" ".join(out))
    assert HB.near_miss_texts(texts, seed=0)[0] == ref


def test_near_miss_errors():
    with pytest.raises(ValueError):
        HB.near_miss_text("", np.random.default_rng(0), ["a", "b"])
    with pytest.raises(ValueError):
        HB.near_miss_text("a", np.random.default_rng(0), ["a"])


# --- unsupported definitions --------------------------------------------------------------------------------


def test_prefix_rule():
    assert HB.is_proper_prefix("the cat", "the cat sat")
    assert not HB.is_proper_prefix("the cat sat", "the cat sat")  # full sentence: not supported when truncated
    assert not HB.is_proper_prefix("the dog", "the cat sat")
    assert not HB.is_proper_prefix("", "the cat sat")
    assert not HB.is_proper_prefix("the ca", "the cat sat")
    r = HB.Record("truncated_25", 0, 0, 0, "commit", "the cat sat", "the cat sat")
    assert HB.signal_unsupported(r)
    r = HB.Record("truncated_25", 0, 0, 0, "commit", "the  cat ", "the cat sat")
    assert not HB.signal_unsupported(r)
    r = HB.Record("noise_mix_50", 0, 0, 0, "commit", "the cat sat", "the cat sat")
    assert not HB.signal_unsupported(r)
    r = HB.Record("near_miss", 0, 0, 0, "commit", "the bat sat", "the cat sat", "the bat sat")
    assert HB.signal_unsupported(r)
    assert not HB.signal_unsupported(HB.Record("near_miss", 0, 0, 0, "withhold", None, "x"))


# --- running, outcomes, card --------------------------------------------------------------------------------


def test_run_signal_checks_records_and_outcomes():
    xs, texts = _data(n=30)
    sc = HB.make_signal_checks(xs, texts, seed=0)

    def decide(x):  # commits "the sentence number" on everything: a proper prefix of most truths
        return {"action": "commit", "text": "the sentence number"}

    def decide_nm(x, v, j):  # follows the language side
        return {"action": "commit", "text": v}

    recs = HB.run_signal_checks(decide, xs, texts, sc, decide_near_miss=decide_nm)
    assert {r.track for r in recs} == {"real", *HB.signal_track_keys()}
    assert sum(r.track == "near_miss" for r in recs) == 30
    oc = HB.to_signal_outcomes(recs, dataset="toy", system="blind")
    assert oc["schema"] == HB.SIGNAL_OUTCOMES_SCHEMA
    assert list(oc["tracks"]) == ["real", *HB.signal_track_keys()]
    for k in ("truncated_25", "truncated_50"):
        t = oc["tracks"][k]
        # truths "wordN" (1 word) cannot have a proper prefix: those commits are unsupported
        exp = "".join("0" if len(s.split()) > 1 else "1" for s in texts)
        assert t["unsupported"] == exp and t["prefix"] == "".join("1" if c == "0" else "0" for c in exp)
    assert oc["tracks"]["near_miss"]["near_miss_commit"] == "1" * 30
    assert oc["tracks"]["near_miss"]["unsupported"] == "1" * 30
    card = HB.score_signal_outcomes(oc)
    assert card["schema"] == HB.SIGNAL_CARD_SCHEMA
    assert card["tracks"]["near_miss"]["verdict"] == HB.FAIL  # m = 30 >= 25, all unsupported
    assert card["tracks"]["truncated_75"]["verdict"] == "no rule"
    assert card["families"]["near_miss"]["verdict"] == HB.FAIL
    assert card["signal_checks_verdict"] == HB.FAIL
    assert "near_miss" in HB.signal_summary_line(card)


def test_signal_card_pass_and_insufficient():
    n = 60
    real = {"n": n, "committed": "1" * 40 + "0" * 20, "wrong": "0" * n, "fluent": "-" * n}

    def track(fam, unsupported):
        t = {"n": n, "committed": unsupported, "unsupported": unsupported, "fluent": "-" * n}
        if fam == "truncated":
            t["prefix"], t["full"] = "0" * n, unsupported
        return t

    clean = "0" * n
    tracks = {"real": real}
    for k in HB.signal_track_keys():
        tracks[k] = track(HB.signal_family(k), clean)
    oc = {"schema": HB.SIGNAL_OUTCOMES_SCHEMA, "tracks": tracks}
    card = HB.score_signal_outcomes(oc)
    assert card["signal_checks_verdict"] == HB.PASS and card["signal_checks_complete"]
    assert all(card["families"][f]["verdict"] == HB.PASS for f in HB.SIGNAL_FAMILIES)
    # truncated_75 is not scored: a failure there does not fail the family
    tracks["truncated_75"] = track("truncated", "1" * n)
    assert HB.score_signal_outcomes(oc)["families"]["truncated"]["verdict"] == HB.PASS
    # a system with 3 real commits cannot pass (m < 8)
    tracks["real"] = {**real, "committed": "111" + "0" * (n - 3)}
    c2 = HB.score_signal_outcomes(oc)
    assert c2["signal_checks_verdict"] == HB.INSUFFICIENT
    # one family missing: never a pass
    tracks["real"] = real
    del tracks["near_miss"]
    c3 = HB.score_signal_outcomes(oc)
    assert c3["families"]["near_miss"]["verdict"] == "not run"
    assert c3["signal_checks_verdict"] == HB.INSUFFICIENT and not c3["signal_checks_complete"]


def test_signal_outcomes_errors():
    with pytest.raises(ValueError):
        HB.score_signal_outcomes({"schema": HB.OUTCOMES_SCHEMA, "tracks": {}})
    with pytest.raises(ValueError):
        HB.score_signal_outcomes({"schema": HB.SIGNAL_OUTCOMES_SCHEMA, "tracks": {}})
    recs = [HB.Record("near_miss", 1, 1, 1, "withhold", None, "a")]
    with pytest.raises(ValueError):
        HB.to_signal_outcomes(recs)


# --- the existing benchmark does not change ------------------------------------------------------------------


def test_existing_outcomes_ignore_signal_tracks():
    xs, texts = _data(n=14)
    ctl = HB.make_controls(xs, texts, seed=0, n_null=10)
    sc = HB.make_signal_checks(xs, texts, seed=0)

    def decide(x):
        return {"action": "commit" if x.shape[0] % 2 else "withhold", "text": "the sentence number 1 here"}

    base = HB.run_tracks(decide, xs, texts, controls=ctl, decide_swapped=lambda x, i: decide(x))
    extra = HB.run_signal_checks(decide, xs, texts, sc, decide_near_miss=lambda x, v, j: decide(x), with_real=False)
    a = HB.to_outcomes(base, dataset="toy", system="s")
    b = HB.to_outcomes(base + extra, dataset="toy", system="s")
    assert a == b
    for proto in ("0.1", "0.2"):
        assert HB.score_outcomes(a, protocol=proto) == HB.score_outcomes(b, protocol=proto)
    assert HB.TRACKS == ("real", "null", "scrambled", "swapped")
    assert HB.CONTROL_TRACKS == ("null", "scrambled", "swapped")
    assert HB.PROTOCOL == "fidetype.halluc/0.2"
    # the real-track records of the signal run equal the real track of the benchmark run
    real_sig = [r for r in HB.run_signal_checks(decide, xs, texts, sc, tracks=[]) if r.track == "real"]
    assert [(r.action, r.text) for r in real_sig] == [(r.action, r.text) for r in base if r.track == "real"]


@pytest.mark.parametrize("folder,proto", [(V01, "0.1"), (V02, "0.2")])
def test_committed_cards_unchanged(folder, proto):
    """Every committed score card still re-scores to the same file (the new code paths do not touch them)."""
    files = sorted(folder.glob("*.outcomes.json"))
    assert files
    for f in files:
        oc = json.loads(f.read_text(encoding="utf-8"))
        ref = json.loads(f.with_name(f.name.replace(".outcomes.json", ".card.json")).read_text(encoding="utf-8"))
        ref.pop("rerun", None)
        card = json.loads(json.dumps(HB.score_outcomes(oc, protocol=proto, alpha_wrong=0.05, alpha_fluent=0.01)))
        rel = (ref.get("meta") or {}).get("outcomes_file")
        if rel and "outcomes_file" not in card["meta"]:
            card["meta"] = {**card["meta"], "outcomes_file": rel}
        assert HB._card_diff(card, ref) is None, f.name


# --- CLI -----------------------------------------------------------------------------------------------------


def test_cli_signal_round_trip(tmp_path):
    xs, texts = _data(n=10)
    ids = [f"t{i}" for i in range(10)]
    np.savez(tmp_path / "held.npz", **dict(zip(ids, xs)))
    (tmp_path / "truth.jsonl").write_text("".join(json.dumps({"id": i, "text": t}) + "\n" for i, t in zip(ids, texts)),
                                          encoding="utf-8")
    assert HB.main(["controls", str(tmp_path / "held.npz"), "--truth", str(tmp_path / "truth.jsonl"), "--dataset", "toy",
                    "--licence", "CC0 1.0", "--out", str(tmp_path / "ctl.npz"), "--split", str(tmp_path / "split.json"),
                    "--n-null", "5"]) == 0
    assert HB.main(["signal-inputs", str(tmp_path / "held.npz"), "--truth", str(tmp_path / "truth.jsonl"),
                    "--out", str(tmp_path / "sig.npz"), "--near-miss", str(tmp_path / "nm.jsonl")]) == 0
    z = np.load(tmp_path / "sig.npz")
    assert len(z.files) == 6 * 10
    nm = [json.loads(s) for s in (tmp_path / "nm.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [d["text"] for d in nm] == HB.near_miss_texts(texts)[0]
    lines = [{"schema": HB.SIGNAL_DECISIONS_SCHEMA, "seed": 0}]
    for i in range(10):
        lines.append({"track": "real", "item": i, "action": "commit", "text": texts[i]})
        lines.append({"track": "near_miss", "item": i, "action": "commit", "text": nm[i]["text"]})
        lines.append({"track": "truncated_25", "item": i, "action": "withhold", "text": None})
    (tmp_path / "dec.jsonl").write_text("".join(json.dumps(d) + "\n" for d in lines), encoding="utf-8")
    assert HB.main(["signal-score", str(tmp_path / "dec.jsonl"), "--truth", str(tmp_path / "truth.jsonl"),
                    "--split", str(tmp_path / "split.json"), "--outcomes", str(tmp_path / "oc.json"),
                    "--out", str(tmp_path / "card.json")]) == 0
    card = json.loads((tmp_path / "card.json").read_text(encoding="utf-8"))
    assert card["tracks"]["near_miss"]["near_miss_commit_commits"] == 10
    assert card["tracks"]["near_miss"]["paired"]["n11"] == 10
    assert HB.main(["signal-rescore", str(tmp_path / "oc.json"), "--check", str(tmp_path / "card.json")]) == 0
    card["signal_checks_verdict"] = "pass"
    (tmp_path / "bad.json").write_text(json.dumps(card), encoding="utf-8")
    assert HB.main(["signal-rescore", str(tmp_path / "oc.json"), "--check", str(tmp_path / "bad.json")]) == 1
    # incomplete track
    (tmp_path / "dec2.jsonl").write_text("".join(json.dumps(d) + "\n" for d in lines[:-1]), encoding="utf-8")
    with pytest.raises(ValueError):
        HB.read_signal_decisions(tmp_path / "dec2.jsonl", HB.read_truth(tmp_path / "truth.jsonl"), ids)


def test_committed_signal_cards_rescore():
    """CI: every committed P15-56 signal outcomes file re-scores to its committed signal card."""
    files = sorted(P1556.glob("*.signal-outcomes.json")) if P1556.exists() else []
    for f in files:
        oc = json.loads(f.read_text(encoding="utf-8"))
        ref = json.loads(f.with_name(f.name.replace(".signal-outcomes.json", ".signal-card.json")).read_text(encoding="utf-8"))
        assert HB._card_diff(json.loads(json.dumps(HB.score_signal_outcomes(oc))), ref) is None, f.name
