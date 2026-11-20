r"""P11-14 run.py helpers (CPU, synthetic data only): exact CTC likelihood, learned score, two-item n-best, AUROC.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p11-14-emg-lm-confidence/test_p11_14.py
"""

from __future__ import annotations

import importlib.util
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_14_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_14_run"] = m
    spec.loader.exec_module(m)
    return m


def brute_ctc(x: np.ndarray, seq: tuple[int, ...], blank: int = 0) -> float:
    """Sum over every frame path that collapses to ``seq`` (tiny T, V only)."""
    T, V = x.shape
    tot = -math.inf
    for path in itertools.product(range(V), repeat=T):
        out, prev = [], None
        for p in path:
            if p != prev and p != blank:
                out.append(p)
            prev = p
        if tuple(out) == tuple(seq):
            tot = float(np.logaddexp(tot, sum(x[t, p] for t, p in enumerate(path))))
    return tot


def test_ctc_logliks_equals_brute_force(run):
    rng = np.random.default_rng(1)
    z = rng.normal(size=(5, 3))
    x = z - np.log(np.exp(z).sum(1, keepdims=True))
    seqs = [(), (1,), (2,), (1, 2), (1, 1), (2, 1, 2), (1, 2, 1, 2, 1)]
    got = run.ctc_logliks(x, seqs)
    for s, g in zip(seqs, got):
        assert g == pytest.approx(brute_ctc(x, s), abs=1e-9) if math.isfinite(brute_ctc(x, s)) else g == -math.inf
    # sequences that need more frames than T are impossible
    assert run.ctc_logliks(x, [(1, 1, 1, 1)])[0] == -math.inf  # needs 7 frames (repeats need a blank)


def test_ctc_logliks_batch_independent(run):
    rng = np.random.default_rng(2)
    z = rng.normal(size=(30, 6))
    x = z - np.log(np.exp(z).sum(1, keepdims=True))
    seqs = [(1, 2, 3), (4,), (5, 5, 1, 2), ()]
    all_ = run.ctc_logliks(x, seqs)
    for s, v in zip(seqs, all_):
        assert run.ctc_logliks(x, [s])[0] == pytest.approx(v, abs=1e-9)


def test_two_item_and_logit(run):
    it = run.two_item("abc", 0.8)
    assert it[0][0] == "abc" and it[1][0] == ""
    assert math.exp(it[0][1]) == pytest.approx(0.8) and math.exp(it[1][1]) == pytest.approx(0.2)
    assert math.isfinite(run.two_item("a", 1.0)[1][1])
    assert run.two_item("a", 0.5) == [] and run.two_item("a", 0.2) == [] and run.two_item("a", 0.0) == []  # amendment 1
    assert run.logit_clip(1.0) == run.LG_CLIP and run.logit_clip(0.0) == -run.LG_CLIP
    assert run.logit_clip(0.5) == pytest.approx(0.0)


def test_learned_signs_and_roundtrip(run):
    rng = np.random.default_rng(3)
    n = 400
    X = rng.normal(size=(n, len(run.FEATS)))
    # truth depends positively on lg_p_aU (index 2); dist_g (index 5, sign -) is made positively related -> dropped
    z = 2.0 * X[:, 2] + 1.5 * X[:, 5]
    y = rng.random(n) < 1 / (1 + np.exp(-z))
    m = run.Learned.fit(X, y)
    assert "dist_g" in m.dropped
    assert m.coef[2] > 0
    for j, s in enumerate(run.SIGNS):
        if s != 0:
            assert m.coef[j] * s >= 0
    m2 = run.Learned.from_dict(m.to_dict())
    assert np.allclose(m.prob(X[:5]), m2.prob(X[:5]))
    assert m.digest() == m2.digest()
    # clipping to the fit range: an extreme row scores as the range edge
    big = X[:1].copy()
    big[0, 2] = 1e6
    edge = X[:1].copy()
    edge[0, 2] = X[:, 2].max()
    assert m.prob(big)[0] == pytest.approx(m.prob(edge)[0])


def test_auroc(run):
    assert run.auroc(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1])) == 1.0
    assert run.auroc(np.array([0.5, 0.5]), np.array([0, 1])) == 0.5
    assert run.auroc(np.array([0.9, 0.1]), np.array([0, 1])) == 0.0
    assert run.auroc(np.array([0.1]), np.array([1])) is None


def test_two_item_nbest_in_calibrate(run):
    """The reject-item encoding through fidetype.trust.calibrate: p_top1 is monotone in c; no commit at c < 0.5."""
    import fidetype.trust as ft

    rng = np.random.default_rng(0)
    V, T, n = 5, 20, 400
    vocab = ["<b>", "a", "b", "c", " "]
    cs = rng.uniform(0.0, 1.0, size=n)
    right = rng.random(n) < cs  # c is a calibrated probability of "right"
    xs, texts = [], []
    for i in range(n):
        x = np.full((T, V), -8.0)
        x[:, 0] = 0.0
        x[0, 0] = -8.0
        x[0, 1] = 0.0  # a signal marker: frame 0 emits "a"
        x[1, :] = -30.0
        x[1, 0] = float(np.log(cs[i]))  # encodes c in the window (decoded below)
        x[1, 2] = float(np.log1p(-cs[i]))
        xs.append(x)
        texts.append("ab" if right[i] else "ba")

    def dec(lp):
        lp = np.asarray(lp)
        if lp[0].argmax() != 1:  # no marker (uniform / shuffled controls): no output
            return []
        c = float(np.exp(lp[1, 0] - np.logaddexp.reduce(lp[1])))
        return run.two_item("ab", c)

    nulls = [np.zeros((T, V)) for _ in range(50)]
    g = ft.calibrate(xs, texts, alpha=0.2, delta=0.1, input_kind="logits", vocab=vocab, blank=0,
                     input_scale="logits", frame_period=0.01, decode_fn=dec, null_inputs=nulls,
                     decoder_name="synthetic", decoder_version="1", modality="emg", name="t", seed=0,
                     audit_text=False)
    ps, acts = [], []
    for c in (0.05, 0.3, 0.45, 0.55, 0.7, 0.9, 0.99):
        x = xs[0].copy()
        x[1, 0] = float(np.log(c))
        x[1, 2] = float(np.log1p(-c))
        r = g.decide(x)
        ps.append((c, r.p_top1, r.text if r.action == "commit" else None))
        acts.append(r.action)
    commits = [(c, t) for c, _, t in ps if t is not None]
    assert commits and all(c > 0.5 and t == "ab" for c, t in commits)
    assert acts[0] != "commit" and acts[-1] == "commit"
    above = [p for c, p, _ in ps if c > 0.5]
    assert all(b >= a - 1e-12 for a, b in zip(above, above[1:]))
    # c is calibrated here, so the fitted temperature keeps p_top1 close to c (no compression of the range)
    assert above[0] < 0.65 and above[-1] > 0.95
