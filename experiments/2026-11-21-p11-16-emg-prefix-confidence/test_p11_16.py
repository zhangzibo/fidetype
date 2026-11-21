r"""P11-16 run.py helpers (CPU, synthetic data only).

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-21-p11-16-emg-prefix-confidence/test_p11_16.py
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_16_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_16_run"] = m
    spec.loader.exec_module(m)
    return m


def test_prefix_mass(run):
    pairs = [("the cat sat", math.log(0.5)), ("the cat", math.log(0.2)), ("the dog sat", math.log(0.2)),
             ("a cat sat", math.log(0.1))]
    w = "the cat sat".split()
    assert run.prefix_mass(pairs, w, 1) == pytest.approx(0.9)
    assert run.prefix_mass(pairs, w, 2) == pytest.approx(0.7)
    assert run.prefix_mass(pairs, w, 3) == pytest.approx(0.5)  # complete: exact text only
    # a longer text with the same first words counts for k < m, not for the complete claim
    pairs2 = [("the cat", 0.0), ("the cat sat", 0.0)]
    assert run.prefix_mass(pairs2, ["the", "cat"], 1) == pytest.approx(1.0)
    assert run.prefix_mass(pairs2, ["the", "cat"], 2) == pytest.approx(0.5)
    assert run.prefix_mass([], ["a"], 1) == 0.0


def test_prefix_lm_text(run):
    assert run.prefix_lm_text("Hello, World") == "hello world "
    assert run.prefix_lm_text("it's") == "it s "


def test_prefix_rows(run):
    sig = {"p_fU": 0.4, "lm_pc": -1.5, "dist_g": 0.1, "kps": 5.0}
    native = [("the cat sat", 0.0), ("the cat", -1.0)]
    fU = [("the cat sat", 0.0), ("the cat", -1.0), ("a cat sat", -0.5)]
    X = run.prefix_rows("the cat sat", native, fU, sig, lambda p: -float(len(p)))
    F = run.FEATS16
    assert X.shape == (3, len(F))
    assert list(X[:, F.index("complete")]) == [0.0, 0.0, 1.0]
    assert X[2, F.index("lm_pc_k")] == -1.5 and X[0, F.index("lm_pc_k")] == -3.0
    pm3 = run.prefix_mass(fU, "the cat sat".split(), 3)
    assert X[2, F.index("lg_pm_fU")] == pytest.approx(run.logit_clip(pm3))
    assert X[0, F.index("lg_pm_fU")] >= X[1, F.index("lg_pm_fU")] >= X[2, F.index("lg_pm_fU")]
    assert np.allclose(X[:, F.index("share")], [1 / 3, 2 / 3, 1.0])


def test_plearned_signs_and_roundtrip(run):
    rng = np.random.default_rng(0)
    n = 400
    X = rng.standard_normal((n, len(run.FEATS16)))
    y = (X[:, 0] + 0.5 * X[:, 2] - 0.8 * X[:, 3] + 0.3 * rng.standard_normal(n)) > 0  # feature 3 has the wrong sign
    m = run.PLearned.fit(X, y)
    assert "lg_p_fU" in m.dropped and m.coef[3] == 0.0
    sg = np.asarray(run.SIGNS16)
    assert np.all(sg * m.coef >= 0)
    m2 = run.PLearned.from_dict(m.to_dict())
    assert np.allclose(m.prob(X), m2.prob(X)) and m.digest() == m2.digest()


def test_decide_k(run):
    assert run.decide_k(None, 0.5) == 0
    assert run.decide_k(np.array([0.9, 0.7, 0.4]), 0.6) == 2
    assert run.decide_k(np.array([0.9, 0.7, 0.4]), 0.95) == 0
    assert run.decide_k(np.array([0.9, 0.7, 0.4]), 0.4) == 3


def _syn(rng, n):
    truths, decs = [], []
    for i in range(n):
        t = " ".join(rng.choice(["a", "bb", "ccc", "dd"], size=int(rng.integers(2, 6))))
        truths.append(t)
        u = rng.random()
        w = t.split()
        if u < 0.3:
            decs.append({"action": "withhold", "text": None, "complete": None, "n_words_committed": 0})
        elif u < 0.6:
            k = int(rng.integers(1, len(w)))
            txt = " ".join(w[:k]) if rng.random() < 0.8 else " ".join(["zz"] + w[1:k])
            decs.append({"action": "commit", "text": txt, "complete": False, "n_words_committed": k})
        else:
            txt = t if rng.random() < 0.8 else t + " zz"
            decs.append({"action": "commit", "text": txt, "complete": True, "n_words_committed": len(txt.split())})
    return truths, decs


def test_v02_values_equal_safe_wpm(run):
    from fidetype.benchmark import safe_wpm as SW

    rng = np.random.default_rng(1)
    truths, decs = _syn(rng, 200)
    oc = run.outcomes(decs, truths)
    nw = [len(t.split()) for t in truths]
    nch = [len(t) for t in truths]
    ns = list(rng.uniform(2, 8, size=200))
    g = {"method": "ltt", "alpha": 0.5, "delta": 0.1, "n_cal": 100, "risk": SW.RISK_PREFIX}
    sw = SW.safe_wpm(oc["committed"], oc["correct"], nw, nch, ns, guarantee=g, metric_version="0.2",
                     committed_words=oc["committed_words"], complete=oc["complete"], penalty_chars=oc["penalty_chars"])
    v = run.v02_values(oc["committed"], oc["correct"], oc["credit_words"], oc["penalty_chars"], ns, np.ones((1, 200)))
    assert sw["unguarded_wpm"] == pytest.approx(float(v[0]), abs=1e-9)
    # with weights: two rows, the second doubles the first half
    W = np.vstack([np.ones(200), np.r_[np.full(100, 2.0), np.ones(100)]])
    v2 = run.v02_values(oc["committed"], oc["correct"], oc["credit_words"], oc["penalty_chars"], ns, W)
    assert v2.shape == (2,) and np.all(np.isfinite(v2))


def test_ext_sheet_reads_as_prefix_guarantee(run):
    from fidetype.benchmark import safe_wpm as SW
    from fidetype.trust.dropin import ControlResult

    ctl = [ControlResult("uniform", "u", 300, 0, 15), ControlResult("shuffled", "s", 300, 2, 15),
           ControlResult("user", "n", 300, 0, 15)]
    ltt = {"threshold": 0.7, "feasible": True, "empirical_risk": 0.03, "p_value": 0.01, "commit_rate": 0.3, "n": 459}
    sh = run.ext_sheet("LX-FL", {"a": 1}, ltt, ctl)
    g = SW.guarantee_from_sheet(sh)
    assert g["risk"] == SW.RISK_PREFIX and g["n_cal"] == 459 and g["alpha"] == 0.05 and g["commit_threshold"] == 0.7
    c = SW.controls_from_sheet(sh)
    assert c["passed"] is True
    sh2 = run.ext_sheet("LX-FL", {"a": 1}, {**ltt, "threshold": math.inf, "feasible": False}, [])
    assert sh2["commit_threshold"] is None and sh2["feasible"] is False


def test_ext_guard_and_controls(run):
    """ExtGuard via dropin._run_controls: no committable window -> 0 commits; always committable -> all commit."""

    class FakeAn:
        KV = ["_"] + [chr(97 + i) for i in range(4)]

        def __init__(self, ok: bool) -> None:
            self.ok = ok

        def analyse(self, x, dec):
            assert x.ndim == 2 and np.allclose(np.exp(x).sum(1), 1.0)
            return {"status": "ok", "top": "a b"} if self.ok else None

    class FakeScorer:
        def mono(self, a):
            return None if a is None else np.array([0.9, 0.8])

    rng = np.random.default_rng(0)
    inputs = [np.log(rng.dirichlet(np.ones(5), size=20)) for _ in range(10)]
    nulls = [np.log(rng.dirichlet(np.ones(5), size=20)) for _ in range(4)]
    for ok, expect in ((False, 0), (True, 6)):
        old = run.NULL_TRIALS
        run.NULL_TRIALS = 6
        try:
            ctl = run.run_controls(FakeAn(ok), FakeScorer(), 0.85, inputs, 0, nulls)
        finally:
            run.NULL_TRIALS = old
        assert [c.name for c in ctl] == ["uniform", "shuffled", "user"]
        assert ctl[0].n_commit == expect and ctl[1].n_commit == expect and ctl[2].n_commit == (4 if ok else 0)
    d = run.decision(FakeScorer(), 0.85, {"status": "ok", "top": "a b"})
    assert d["action"] == "commit" and d["text"] == "a" and d["complete"] is False
    d = run.decision(FakeScorer(), 0.5, {"status": "ok", "top": "a b"})
    assert d["text"] == "a b" and d["complete"] is True
    assert run.decision(FakeScorer(), 0.95, {"status": "ok", "top": "a b"})["action"] == "offer"
    assert run.decision(FakeScorer(), 0.5, None)["action"] == "withhold"


def test_combined_interval_k1(run):
    rng = np.random.default_rng(2)
    truths, decs = _syn(rng, 120)
    oc = run.outcomes(decs, truths)
    ns = list(rng.uniform(2, 8, size=120))
    W = np.vstack([np.ones(120)] + [rng.multinomial(120, np.ones(120) / 120).astype(float) for _ in range(50)])
    full = float(run.v02_values(oc["committed"], oc["correct"], oc["credit_words"], oc["penalty_chars"], ns,
                                np.ones((1, 120)))[0])
    d = {**oc, "value": full, "credited": True}
    out = run.combined_interval([d], ns, W, reference=None)
    assert out["value"] == pytest.approx(full) and out["interval"][0] <= full <= out["interval"][1]
    out2 = run.combined_interval([d, {"credited": False}], ns, W, reference=1.0)
    assert out2["value"] == pytest.approx(full / 2) and out2["interval"][0] == 0.0
    assert run.verdict(5.0, 3.5, 3.09).startswith("clearly") and run.verdict(1.0, 0.0, 3.09) == "not above"
