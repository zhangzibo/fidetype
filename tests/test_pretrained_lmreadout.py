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
    assert f.sha256 == "7c4f133c1eb5b46d67d185eb61b6ec282b009b652112591274c3c865757a06b8"
    assert "CC-BY-2.0-FR" in m.licence["text_files"][cfg["lm_file"]]
    assert "13 of the 80 test sentences" in cfg["test_overlap"]


WILLETT_DIR = Path(r"C:\Users\zhang\bci-data\pretrained")


@pytest.mark.skipif(not (WILLETT_DIR / "willett-hw" / "willett-hw.weights.npz").is_file()
                    or not (WILLETT_DIR / "text" / "eng_tatoeba_6gram_mkn_noE2Q.npz").is_file(),
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
