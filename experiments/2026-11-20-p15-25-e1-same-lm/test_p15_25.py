"""Small CPU tests for P15-25 (no data, no torch)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def _lev_ref(a, b) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[-1]


def test_levenshtein_matches_reference():
    rng = np.random.default_rng(0)
    for _ in range(200):
        a = list(rng.integers(0, 5, rng.integers(0, 12)))
        b = list(rng.integers(0, 5, rng.integers(0, 12)))
        assert C.levenshtein(a, b) == _lev_ref(a, b)


def test_run_lists():
    assert len(C.all_runs()) == 41 and C.all_runs()[-1] == "E-b30-s0-labelshuf"
    assert len(C.tune_runs(C.config())) == 16
    assert sorted(C.c1_runs()) == sorted(f"{a}-b{b}-s{s}" for a in C.ARMS for b in ("30", "all") for s in (0, 1))
    assert C.parse_run("E-b30-s0-labelshuf") == {"arm": "E", "budget": "30", "seed": 0, "label_shuffle": True}


def test_encode_roundtrip_and_greedy():
    assert "".join(C.VOCAB[t] for t in C.encode("hi, you.")) == "hi, you."
    lp = np.full((6, 98), -10.0)
    for t, k in enumerate([5, 5, 0, 5, 0, 0]):
        lp[t, k] = 0.0
    assert C.greedy_tokens(lp) == [5, 5]


def test_bootstrap_same_draws_as_e1a():
    rng = np.random.default_rng(1)
    ref = rng.integers(20, 60, 80).astype(float)
    ea, eb = rng.integers(0, 40, 80).astype(float), rng.integers(0, 40, 80).astype(float)
    bs = C.bootstrap(ea, eb, ref, 2000, 0, 13)
    r2 = np.random.default_rng(0)
    ii = r2.integers(0, 80, size=(2000, 80))
    d = (ea[ii].sum(1) - eb[ii].sum(1)) / ref[ii].sum(1)
    assert abs(bs["lo"] - np.percentile(d, 2.5)) < 1e-12
    assert bs["lo_bonf"] <= bs["lo"] <= bs["hi"] <= bs["hi_bonf"]


def test_verdict_detects_a_clear_winner():
    e1a = C.e1a_config()
    rng = np.random.default_rng(2)
    ref = rng.integers(20, 60, 80)
    res, minutes = {}, {}
    for name in C.all_runs():
        p = C.parse_run(name)
        rate = 0.3 if p["arm"] == "E" else 0.8
        ed = np.round(ref * rate + rng.normal(0, 1, 80)).clip(0)
        res[name] = {"cer": float(ed.sum() / ref.sum()), "edits": ed.tolist(), "ref": ref.tolist()}
        minutes[name] = 1.0 if p["budget"] == "all" else float(p["budget"])
    minutes = {n: (506.0 if C.parse_run(n)["budget"] == "all" else m) for n, m in minutes.items()}
    v = C.verdict(res, minutes, e1a, 13, shuf={n: 0.95 for n in C.c1_runs()})
    assert v["V1"]["pass"] and v["H1"]["status"] == "pass" and v["H4"]["status"] == "pass"
    assert v["H3"]["status"] in ("fail", "partial") and v["H5"]["status"] == "pass"
    assert v["C1"]["pass"] and "C2" in v
