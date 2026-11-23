"""P14-48: the packaged LM readout and the no-signal gate (fidetype.pretrained.lmreadout). CPU, seconds."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

import fidetype.pretrained as ftp
from fidetype.lm.ngram import CharNgramLM
from fidetype.pretrained import lmreadout as LR
from fidetype.pretrained._xbody import VOCAB

REPO = Path(__file__).resolve().parents[1]
P1107 = REPO / "experiments" / "2026-11-20-p11-07-emg-beam-lm" / "lmbeam.py"


def _p1107():
    spec = importlib.util.spec_from_file_location("lmbeam_p1107_test", P1107)
    m = importlib.util.module_from_spec(spec)
    sys.modules["lmbeam_p1107_test"] = m
    spec.loader.exec_module(m)
    return m


def _lm() -> CharNgramLM:
    return CharNgramLM(order=4).train(["the cat sat on the mat", "a dog ran", "hello there", "we will see"] * 5)


def _lp(rng: np.random.Generator, T: int, peak: float = 4.0) -> np.ndarray:
    z = rng.standard_normal((T, len(VOCAB))) * 3.0
    z[:, 0] += peak
    return z - np.log(np.exp(z).sum(1, keepdims=True))


@pytest.mark.skipif(not P1107.is_file(), reason="the P11-07 experiment file is missing")
def test_packaged_lmbeam_equals_p11_07():
    old = _p1107()
    lm = _lm()
    rng = np.random.default_rng(0)
    for k in range(6):
        lp = _lp(rng, 120 + 40 * k, peak=2.0 + k)
        for w, beta, B in ((0.5, 1.0, 8), (0.0, 0.0, 4), (1.0, 2.0, 16)):
            a, b = old.LMBeam(list(VOCAB), 0, lm=lm, lm_weight=w, bonus=beta, beam=B, prune_logp=-8.0), \
                LR.LMBeam(list(VOCAB), 0, lm=lm, lm_weight=w, bonus=beta, beam=B, prune_logp=-8.0)
            half = lp.shape[0] // 2
            a.push(lp[:half]); a.push(lp[half:])  # noqa: E702 (chunked push, the streaming path)
            b.push(lp)
            ha, hb = a.nbest(8), b.nbest(8)
            assert [h.tokens for h in ha] == [h.tokens for h in hb]
            assert np.allclose([h.score for h in ha], [h.score for h in hb], rtol=0, atol=1e-9)


def test_gate_fit_rule_and_decision():
    fs = 0.01
    xs = []
    for n in (10, 12, 14, 20):  # n emissions in 400 frames (4 s)
        lp = np.full((400, 5), -20.0)
        lp[:, 0] = 0.0
        for j in range(n):
            lp[10 + 15 * j, 0], lp[10 + 15 * j, 1 + j % 4] = -20.0, 0.0
        xs.append(lp)
    assert [LR.gate_features(x, fs)[0] for x in xs] == [10, 12, 14, 20]
    g = LR.NoSignalGate.fit(xs, fs)  # floor(0.01 * 4) = 0: the smallest values, 2 x the fastest rate
    assert (g.k_min, g.r_min, g.r_max) == (10, 2.5, 10.0)
    assert all(g.passes(x) for x in xs)
    blank = np.full((400, 5), -20.0)
    blank[:, 0] = 0.0
    assert not g.passes(blank)
    noisy = np.random.default_rng(0).standard_normal((400, 5))  # argmax changes on most frames: too fast
    assert not g.passes(noisy)
    assert LR.NoSignalGate.from_dict(json.loads(json.dumps(g.to_dict()))) == g
    g2 = LR.NoSignalGate.fit(xs * 50, fs)  # 200 inputs: floor(2) = 2 -> the 3rd smallest
    assert g2.k_min == 10 and g2.r_min == 2.5


def test_readout_gate_gives_empty_text_and_nbest():
    lm = _lm()
    rng = np.random.default_rng(3)
    lp = _lp(rng, 200)
    flat = np.full((200, len(VOCAB)), -np.log(len(VOCAB)))
    s = {"lm_weight": 0.5, "bonus": 1.0, "beam": 8, "prune_logp": -8.0, "n_best": 8}
    raw = LR.LmReadout(VOCAB, lm, s, None)
    assert len(raw.text(flat)) == 200  # the P15-25 finding: one token per flat frame without a gate
    g = LR.NoSignalGate.fit([lp], 0.01)
    r = LR.LmReadout(VOCAB, lm, s, g)
    assert r.gated(flat) and r.text(flat) == "" and r.nbest(flat) == []
    nb = r.nbest(lp)
    assert nb and nb[0]["text"] == r.text(lp) and len({d["text"] for d in nb}) == len(nb)
    assert all(d.get("logp_acoustic", 0.0) <= 0 and d.get("logp_lm", 0.0) <= 0 for d in nb)
    assert r.decode_fn()(lp) == nb


def test_manifest_lm_readout_block():
    m = ftp.info("willett-hw")
    cfg = m.raw["readouts"]["lm"]
    assert cfg["decode"] == LR.READOUT_ID
    assert cfg["settings"] == {"lm_weight": 0.5, "bonus": 1.0, "beam": 8, "prune_logp": -8.0, "n_best": 8}
    f = next(f for f in m.files if f.name == cfg["lm_file"])
    assert f.role == "text" and f.url is None
    assert f.sha256 == "d7f6e829b827d1f7d09f5927eb51ec33fd79df29201d7e722a0878a503059261"  # P14-50: Willett-blocked LM
    assert cfg["lm_file"] == "eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz"
    assert [x.name for x in m.files if x.role == "text"] == [cfg["lm_file"]]  # one LM: the default
    assert "CC-BY-2.0-FR" in m.licence["text_files"][cfg["lm_file"]]
    assert cfg["test_overlap"].startswith("none")
    assert "research-only emg2qwerty" in m.licence["text_files"][cfg["lm_file"]]


WILLETT_DIR = Path(r"C:\Users\zhang\bci-data\pretrained")


@pytest.mark.skipif(not (WILLETT_DIR / "willett-hw" / "willett-hw.weights.npz").is_file()
                    or not (WILLETT_DIR / "text" / "eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz").is_file(),
                    reason="willett-hw weights and the LM file are local only (not hosted, P14-02)")
def test_willett_hw_lm_readout_local():
    m = ftp.load("willett-hw", cache_dir=WILLETT_DIR)
    r = m.lm_readout(gate=False)
    assert r.settings["beam"] == 8 and r.gate is None
    flat = np.full((150, 98), -np.log(98.0))
    assert len(r.text(flat)) == 150
    if m.manifest.raw["readouts"]["lm"].get("gate"):
        g = m.lm_readout()
        assert g.text(flat) == ""
        st = m._stream(flat.astype(np.float32), "flat")
        assert m.text(st, readout="lm") == "" and isinstance(m.text(st), str)
    t = m.manifest.raw["readouts"]["lm"].get("trust")
    if t:
        guard = m.guard(readout="lm")
        assert guard.config_id == t["config_id"] != m.guard().config_id
        assert guard.decide(np.full((150, 98), -np.log(98.0))).action == "withhold"  # gated: empty n-best
    with pytest.raises(ValueError):
        m.text(m._stream(flat.astype(np.float32), "flat"), readout="other")


# --- P14-49: score gates ----------------------------------------------------------------------------------

def _emit(T: int, n: int, peak: float, V: int = 5) -> np.ndarray:
    lp = np.full((T, V), -8.0)
    lp[:, 0] = 0.0
    for j in range(n):
        t = 10 + 15 * j
        lp[t, 0], lp[t, 1 + j % (V - 1)] = np.log(1 - peak), np.log(peak)
    return lp - np.log(np.exp(lp).sum(1, keepdims=True))


def test_posterior_features():
    x = _emit(400, 10, 0.9)
    f = LR.posterior_features(x, 0.01)
    assert f["n_keys"] == 10 and abs(f["kps"] - 2.5) < 1e-12 and abs(f["nb_share"] - 10 / 400) < 1e-12
    assert abs(f["peak"] - 0.9) < 1e-3 and f["neg_entropy"] < 0 and abs(f["log_n_keys"] - np.log(11)) < 1e-12
    blank = np.zeros((50, 5)) - 20.0
    blank[:, 0] = 0.0
    fb = LR.posterior_features(blank, 0.01)
    assert fb["n_keys"] == 0 and fb["peak"] == 0.0 and fb["neg_entropy"] == -np.log(5)


@pytest.mark.parametrize("feature", ["nb_share", "peak", "neg_entropy", "logit"])
def test_score_gate_fit_rule_round_trip(feature):
    real = [_emit(400, n, 0.9) for n in (10, 12, 14, 20)]
    null = [_emit(400, n, 0.55) for n in (10, 12, 14, 20)]
    g = LR.ScoreGate.fit(feature, real, 0.01, null=null)
    assert g.k_min == 1 and g.r_max == 2 * 20 / 4.0 and g.hi == np.inf
    assert g.lo == min(g.score(x) for x in real)  # floor(0.01 x 4) = 0: the smallest real score
    assert all(g.passes(x) for x in real)
    if feature != "nb_share":  # the same counts: only the confidence features see the weak peaks
        assert not any(g.passes(x) for x in null)
    blank = np.full((400, 5), -20.0)
    blank[:, 0] = 0.0
    assert not g.passes(blank)  # no emission
    assert not g.passes(np.random.default_rng(0).standard_normal((400, 5)))  # too fast
    d = json.loads(json.dumps(g.to_dict()))
    assert d["kind"] == "score" and LR.gate_from_dict(d) == g


def test_lm_ratio_gate_in_the_readout():
    lm = _lm()
    s = {"lm_weight": 0.5, "bonus": 1.0, "beam": 8, "prune_logp": -8.0, "n_best": 8}
    lp = _lp(np.random.default_rng(3), 200)
    raw = LR.LmReadout(VOCAB, lm, s, None)
    nt = len(raw.hyps(lp, 1)[0].tokens)
    n = LR.gate_features(lp, 0.01)[0]
    g = LR.ScoreGate.fit("lm_ratio", [lp], 0.01, real_lm_tokens=[nt])
    assert g.needs_lm and g.lo == g.hi == nt / max(1, n)
    r = LR.LmReadout(VOCAB, lm, s, g)
    assert not r.gated(lp) and r.text(lp) == raw.text(lp)
    narrow = LR.ScoreGate(**{**g.__dict__, "lo": g.lo + 1.0, "hi": g.lo + 2.0})
    r2 = LR.LmReadout(VOCAB, lm, s, narrow)
    assert r2.gated(lp) and r2.text(lp) == "" and r2.nbest(lp) == []
    with pytest.raises(ValueError):
        g.passes(lp)  # lm_ratio needs the LM token count


def test_gate_from_dict_kinds():
    c = {"k_min": 7, "r_min": 0.4, "r_max": 2.8, "frame_s": 0.01, "blank": 0}
    assert isinstance(LR.gate_from_dict(c), LR.NoSignalGate)
    assert isinstance(LR.gate_from_dict({**c, "kind": "count"}), LR.NoSignalGate)
    with pytest.raises(ValueError):
        LR.gate_from_dict({**c, "kind": "other"})
    with pytest.raises(ValueError):
        LR.ScoreGate.from_dict({"feature": "nope", "lo": 0, "hi": None, "k_min": 1, "r_max": 1, "frame_s": 0.01})


def test_manifest_default_gate_is_the_p14_49_score_gate():
    cfg = ftp.info("willett-hw").raw["readouts"]["lm"]
    g = LR.gate_from_dict(cfg["gate"])
    assert isinstance(g, LR.ScoreGate) and g.feature == "logit" and not g.needs_lm
    assert g.k_min == 1 and len(g.coef) == len(LR.LOGIT_INPUTS) == len(g.mean) == len(g.scale)
    assert cfg["trust"]["config"] == "file:willett-hw.lm3.guard.json"
    assert g.lo == pytest.approx(0.5659314232741417)  # P14-58 quantile_lo, shipped by P14-59
    blank = np.full((300, len(VOCAB)), -20.0)
    blank[:, 0] = 0.0
    assert not g.passes(blank) and not g.passes(np.full((300, len(VOCAB)), -np.log(len(VOCAB))))


def test_beta_cdf_without_scipy():
    """The numpy-only Beta CDF of hd_quantile matches closed forms (the core package has no scipy)."""
    for x in (0.0, 0.03, 0.2, 0.5, 0.77, 0.999, 1.0):
        assert LR._beta_cdf(x, 1.0, 1.0) == pytest.approx(x, abs=1e-13)
        assert LR._beta_cdf(x, 3.5, 1.0) == pytest.approx(x ** 3.5, abs=1e-13)
        assert LR._beta_cdf(x, 1.0, 2.5) == pytest.approx(1.0 - (1.0 - x) ** 2.5, abs=1e-13)
        # Beta(2, 3): I_x = 6x^2 - 8x^3 + 3x^4
        assert LR._beta_cdf(x, 2.0, 3.0) == pytest.approx(6 * x**2 - 8 * x**3 + 3 * x**4, abs=1e-13)
    # symmetry I_x(a, b) = 1 - I_{1-x}(b, a), with HD weights of a large sample (n = 781, q = 0.03)
    a, b = 782 * 0.03, 782 * 0.97
    for x in (0.01, 0.02, 0.03, 0.05):
        assert LR._beta_cdf(x, a, b) == pytest.approx(1.0 - LR._beta_cdf(1.0 - x, b, a), abs=1e-12)


def test_beta_cdf_matches_scipy_when_present():
    """Where scipy is installed (the ``data`` extra), the numpy-only CDF agrees with it."""
    stats = pytest.importorskip("scipy.stats")
    for n in (2, 10, 80, 106, 781):
        for q in (0.01, 0.03, 0.5, 0.97):
            xs = np.arange(n + 1) / n
            a, b = (n + 1) * q, (n + 1) * (1 - q)
            mine = np.array([LR._beta_cdf(v, a, b) for v in xs])
            assert np.abs(mine - stats.beta.cdf(xs, a, b)).max() < 1e-10


def test_hd_quantile_and_quantile_lo():
    """P14-58: the Harrell-Davis quantile moves little when the smallest value moves; quantile_lo."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    assert LR.hd_quantile(x, 0.5) == pytest.approx(float(np.median(x)), abs=0.05)
    assert LR.hd_quantile([3.0], 0.03) == 3.0
    assert LR.hd_quantile([1.0, 2.0, 3.0], 0.5) == pytest.approx(2.0)
    y = x.copy()
    y[np.argmin(y)] -= 10.0  # one much weaker value
    assert abs(LR.hd_quantile(y, 0.03) - LR.hd_quantile(x, 0.03)) < 0.5 < abs(y.min() - x.min())
    with pytest.raises(ValueError):
        LR.hd_quantile([], 0.5)
    with pytest.raises(ValueError):
        LR.hd_quantile([1.0], 0.0)
    lo, parts = LR.quantile_lo(x, q=0.03)
    assert lo == parts["lo_real_hd"] and "lo_null" not in parts
    lo2, parts2 = LR.quantile_lo(x, null_scores=np.full(100, 5.0), q=0.03)
    assert lo2 == pytest.approx(5.0) and parts2["lo_real_hd"] == pytest.approx(lo)
    g = LR.ScoreGate("peak", -1.0, np.inf, 1, 10.0, 0.01)
    assert g.with_lo(0.5).lo == 0.5 and g.with_lo(0.5).to_dict()["lo"] == 0.5 and g.lo == -1.0
    with pytest.raises(ValueError):
        g.with_lo(float("nan"))
