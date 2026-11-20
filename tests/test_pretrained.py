"""P14-01: pretrained decoders (registry, manifests, licence gate, NumPy runtimes, NTS output).

All tests use tiny fake weights written to a temporary folder. No real weights, no data files.
The real-weight reruns are in ``experiments/2026-11-19-p14-01-pretrained`` (local only).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

import fidetype.conformance as C
import fidetype.decoders
import fidetype.pretrained as ftp
from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, NumpyLookaheadGRU, forward_numpy
from fidetype.pretrained import _crt, _gru
from fidetype.pretrained import readers as R
from fidetype.pretrained.__main__ import main as cli_main
from fidetype.pretrained.manifest import MANIFEST_SCHEMA, ManifestError, all_manifests, parse_manifest


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def entry(role: str, p: Path) -> dict:
    return {"role": role, "name": p.name, "sha256": sha(p), "size": p.stat().st_size, "url": None}


LIC_CC0 = {"data.licence": "CC0-1.0", "data.research_only": False, "weights": "CC0-1.0", "weights_status": "test"}
LIC_NC = {"data.licence": "CC-BY-NC-SA-4.0", "data.research_only": True, "weights": "CC-BY-NC-SA-4.0",
          "weights_status": "test"}


def write_manifest(tmp: Path, doc: dict) -> Path:
    p = tmp / f"{doc['name']}.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


# --- tiny GRU-CTC model (T15 / T12 runtime) ----------------------------------------------------------

GCFG = LookaheadGRUConfig(n_in=8, n_out=41, n_sessions=2, hidden=6, layers=2, patch=3, stride=2, smooth_sd=1.0,
                          la_max=3, la_proj=2)


def gru_model(tmp: Path, lookahead: bool = True, licence: dict | None = None, name: str = "fake-gru") -> Path:
    m = NumpyLookaheadGRU.random(GCFG, seed=1)
    params = dict(m.params)
    if not lookahead:
        params = {k: v for k, v in params.items() if not k.startswith("la_")}
    w = tmp / f"{name}.weights.npz"
    np.savez(w, **params)
    doc = {
        "schema": MANIFEST_SCHEMA, "name": name, "version": "1", "title": "tiny GRU", "status": "available",
        "task": "test", "modality": "intracortical", "runtime": "gru-ctc",
        "input": {"bin_s": 0.02, "file_format": "b2t25-hdf5"},
        "output": {"vocab_type": "phoneme", "vocab_id": "phoneme.arpabet-39-sil", "frame_period_s": 0.04,
                   "latency_s": 0.0},
        "architecture": {"patch": 3, "stride": 2, "layers": 2, "hidden": 6, "smooth_sd": 1.0,
                         "lookahead": {"bins": 0, "max": 3} if lookahead else None, "input_round": "float16",
                         "sessions": ["t15.2023.08.11", "t15.2023.08.13"]},
        "files": [entry("weights", w)], "licence": licence or LIC_CC0, "trust": None,
        "trust_note": "no config in this test",
    }
    return write_manifest(tmp, doc)


def test_packaged_manifests_parse_and_flags():
    ms = {m.name: m for m in all_manifests()}
    assert {"t15-m4-13", "t12-v2", "kt-semg-lda", "emg2qwerty-p11-01", "willett-hw", "toronto-semg-cnn"} <= set(ms)
    assert ms["emg2qwerty-p11-01"].research_only is True
    assert ms["emg2qwerty-p11-01"].licence["weights"] == "CC-BY-NC-SA-4.0"
    for n in ("t15-m4-13", "t12-v2", "kt-semg-lda"):
        assert ms[n].research_only is False and ms[n].status == "available"
        assert ms[n].weights_sha256 and all(f.url is None for f in ms[n].files)  # nothing hosted yet (P14-02)
    assert ms["willett-hw"].status == "available" and ms["willett-hw"].research_only is False
    assert ms["willett-hw"].language == "en" and ms["willett-hw"].runtime == "xbody-ctc"
    assert ms["willett-hw"].licence["weights"] == "CC0-1.0" and "D11" in ms["willett-hw"].licence["weights_status"]
    assert all(f.url is None for f in ms["willett-hw"].files)
    card = ms["willett-hw"].card()
    for must in ("0.305", "0.92", "seed 1", "No language model", "Descriptive only"):
        assert must in card, must
    assert ms["toronto-semg-cnn"].status == "planned"
    assert "t15-m4-13" in ms["t15-m4-13"].card()
    # the packaged T15 guard exists and is the P14-05 config
    g = json.loads((Path(ftp.__file__).parent / "guards/t15-m4-13.guard.json").read_text(encoding="utf-8"))
    assert g["sheet"]["config_id"] == ms["t15-m4-13"].trust["config_id"]


def test_manifest_rejects_bad_documents(tmp_path):
    good = json.loads(gru_model(tmp_path).read_text(encoding="utf-8"))
    parse_manifest(good)
    for mutate, msg in [
        (lambda d: d.update(schema="x"), "schema"),
        (lambda d: d.update(name="Bad Name"), "name"),
        (lambda d: d["files"][0].update(sha256="abc"), "sha256"),
        (lambda d: d["files"][0].update(name="../x.npz"), "file name"),
        (lambda d: d["files"][0].update(url="http://insecure"), "https"),
        (lambda d: d["licence"].update({"data.licence": "CC-BY-NC-4.0"}), "research_only"),  # looser than the licence
        (lambda d: d["licence"].update({"data.licence": "CC BY 4.0"}), "SPDX"),
        (lambda d: d.update(files=[]), "weights file"),
    ]:
        d = copy.deepcopy(good)
        mutate(d)
        with pytest.raises(ManifestError, match=msg):
            parse_manifest(d)


def test_gru_runtime_equals_reference_forward():
    m = NumpyLookaheadGRU.random(GCFG, seed=3)
    x = np.random.default_rng(0).standard_normal((40, 8)).astype(np.float32)
    for la in (0, 2):
        ref = forward_numpy(m, x, 1, la)
        got = _gru.gru_ctc_logits(m.params, x, 1, patch=3, stride=2, layers=2, hidden=6, smooth_sd=1.0,
                                  la_bins=la, la_max=3)
        np.testing.assert_allclose(got, ref, atol=1e-5)
    # without the lookahead head: head = out(h_k)
    p = {k: v for k, v in m.params.items() if not k.startswith("la_")}
    got = _gru.gru_ctc_logits(p, x, 0, patch=3, stride=2, layers=2, hidden=6, smooth_sd=1.0)
    z = m.day_features(x, 0)
    hs = [np.zeros(6, np.float32)] * 2
    rows = []
    for k in range(_gru.n_steps(40, 3, 2)):
        a = z[2 * k:2 * k + 3].reshape(-1)
        for i in range(2):
            hs[i] = m.gru_step(i, a, hs[i])
            a = hs[i]
        rows.append(a @ p["out.weight"].T + p["out.bias"])
    np.testing.assert_allclose(got, np.stack(rows), atol=1e-5)
    assert _gru.gru_ctc_logits(p, x[:2], 0, patch=3, stride=2, layers=2, hidden=6, smooth_sd=1.0).shape == (0, 41)


def test_load_decode_nts_provenance(tmp_path):
    mp = gru_model(tmp_path)
    m = ftp.load(str(mp), weights=tmp_path)
    x = np.random.default_rng(1).standard_normal((50, 8)).astype(np.float32)
    st = m.decode(x, session="t15.2023.08.13")
    assert st.vocab_type == "phoneme" and st.blank_id == 0 and st.log_probs.shape == (24, 41)
    meta = st.meta
    assert meta["decoder.weights_sha256"] == m.weights_sha256
    assert meta["data.licence"] == "CC0-1.0" and meta["data.research_only"] is False
    assert meta["decoder.name"] == "fidetype-fake-gru" and meta["fidetype.pretrained"] == "fake-gru@1"
    rep = C.check(st)
    assert rep.passes("provenance"), [f.check_id for f in rep.failures()]
    np.testing.assert_allclose(np.exp(st.log_probs).sum(1), 1.0, atol=1e-4)
    assert isinstance(m.text(st), str)
    with pytest.raises(ValueError, match="session"):
        m.decode(x)
    with pytest.raises(ValueError, match="unknown session"):
        m.decode(x, session="t15.2099.01.01")
    paths = m.save([st], tmp_path / "out")
    assert C.check(paths[0]).passes("provenance")
    with pytest.raises(ftp.NoTrustConfig):
        m.guard()


def test_weights_missing_mismatch_and_cache(tmp_path, monkeypatch):
    mp = gru_model(tmp_path)
    doc = json.loads(mp.read_text(encoding="utf-8"))
    cache = tmp_path / "cache"
    monkeypatch.setenv(ftp.ENV_DIR, str(cache))
    assert ftp.default_cache_dir() == cache
    with pytest.raises(ftp.WeightsNotFound, match="P14-02"):
        ftp.load(str(mp))
    (cache / "fake-gru").mkdir(parents=True)
    shutil.copy(tmp_path / "fake-gru.weights.npz", cache / "fake-gru" / "fake-gru.weights.npz")
    assert ftp.load(str(mp)).name == "fake-gru"  # found in <cache>/<name>/
    with open(cache / "fake-gru" / "fake-gru.weights.npz", "r+b") as f:  # same size, one byte changed
        f.seek(100)
        b = f.read(1)
        f.seek(100)
        f.write(bytes([b[0] ^ 1]))
    with pytest.raises(ftp.WeightsMismatch, match="SHA-256"):
        ftp.load(str(mp))
    doc["files"][0]["size"] += 1
    with pytest.raises(ftp.WeightsMismatch, match="size"):
        ftp.load(str(write_manifest(tmp_path, doc)), weights=tmp_path)
    with pytest.raises(ftp.WeightsNotFound):
        ftp.download(str(write_manifest(tmp_path, doc)), cache_dir=tmp_path / "empty")


def test_research_only_gate(tmp_path):
    mp = gru_model(tmp_path, licence=LIC_NC, name="fake-nc")
    with pytest.raises(ftp.ResearchOnlyRefused, match="accept_research_only"):
        ftp.load(str(mp), weights=tmp_path)
    with pytest.raises(ftp.ResearchOnlyRefused):
        ftp.resolve_files(str(mp), weights=tmp_path)
    with pytest.raises(ftp.ResearchOnlyRefused):
        ftp.download(str(mp), cache_dir=tmp_path)
    m = ftp.load(str(mp), weights=tmp_path, accept_research_only=True)
    st = m.decode(np.zeros((20, 8), np.float32), session=0)
    assert st.meta["data.research_only"] is True and st.meta["data.licence"] == "CC-BY-NC-SA-4.0"
    # the packaged emg2qwerty model refuses before it looks for files
    with pytest.raises(ftp.ResearchOnlyRefused):
        ftp.load("emg2qwerty-p11-01", cache_dir=tmp_path)
    assert cli_main(["verify", "emg2qwerty-p11-01", "--cache-dir", str(tmp_path)]) == 2


def test_planned_model_and_unknown_name(tmp_path):
    with pytest.raises(ftp.ModelNotAvailable, match="runtime"):
        ftp.load("toronto-semg-cnn", cache_dir=tmp_path)
    with pytest.raises(KeyError, match="known"):
        ftp.load("no-such-model")


def test_decoders_alias(tmp_path):
    mp = gru_model(tmp_path)
    m = fidetype.decoders.load(str(mp), weights=tmp_path)
    assert isinstance(m, ftp.GruCtcDecoder)
    assert [x.name for x in fidetype.decoders.list_models()] == [x.name for x in ftp.list_models()]


def test_b2t25_hdf5_reader_and_decode_file(tmp_path):
    h5py = pytest.importorskip("h5py")
    mp = gru_model(tmp_path)
    d = tmp_path / "t15.2023.08.11"
    d.mkdir()
    rng = np.random.default_rng(2)
    with h5py.File(d / "data_val.hdf5", "w") as f:
        for i in range(3):
            g = f.create_group(f"trial_{i:04d}")
            g.create_dataset("input_features", data=rng.standard_normal((30 + i, 8)).astype(np.float32))
            g.attrs["sentence_label"] = f"secret sentence {i}"
    m = ftp.load(str(mp), weights=tmp_path)
    pairs = m.decode(str(d / "data_val.hdf5"), with_items=True)
    assert len(pairs) == 3 and pairs[0][0].session == "t15.2023.08.11"
    for it, st in pairs:
        assert "secret" not in json.dumps(st.meta)  # truth never in a stream
        assert C.check(st).passes("provenance")
    one = m.decode_file(d / "data_val.hdf5", indices=[2])
    np.testing.assert_allclose(one[0].log_probs, pairs[2][1].log_probs)
    # same numbers as decode_array on the same input
    st = m.decode(R.read_b2t25_hdf5(d / "data_val.hdf5", indices=[1])[0].x, session="t15.2023.08.11")
    np.testing.assert_allclose(st.log_probs, pairs[1][1].log_probs)


def test_b2t24_rolling_normalisation():
    rng = np.random.default_rng(4)
    seq = [rng.standard_normal((5 + i, 3)) * (1 + i) for i in range(6)]
    out = R.b2t24_normalise(seq, window=2, clip=10.0)
    allp = np.concatenate(seq[2:4])
    mu, sd = allp.mean(0), allp.std(0)
    np.testing.assert_allclose(out[4], np.clip((seq[4] - mu) / sd, -10, 10).astype(np.float16), atol=1e-6)
    first = np.concatenate(seq[:2])
    np.testing.assert_allclose(out[1], ((seq[1] - first.mean(0)) / first.std(0)).astype(np.float16), atol=1e-6)


# --- tiny CRT model (emg2qwerty runtime) ---------------------------------------------------------------


def crt_params(seed: int = 0, d: int = 8, c: int = 2, dil=(1, 2)) -> dict[str, np.ndarray]:
    r = np.random.default_rng(seed)
    p = {"mean": r.standard_normal((1, 1, 32, 12)).astype(np.float32),
         "std": (1 + r.random((1, 1, 32, 12))).astype(np.float32),
         "out_norm.weight": (1 + 0.1 * r.standard_normal(d)).astype(np.float32),
         "out_norm.bias": (0.1 * r.standard_normal(d)).astype(np.float32),
         "head.weight": r.standard_normal((98, d)).astype(np.float32), "head.bias": r.standard_normal(98).astype(np.float32)}
    for s in ("left", "right"):
        p[f"{s}.conv.weight"] = (0.3 * r.standard_normal((c, 12, 5))).astype(np.float32)
        p[f"{s}.conv.bias"] = (0.1 * r.standard_normal(c)).astype(np.float32)
        p[f"{s}.proj.weight"] = (0.3 * r.standard_normal((d // 2, 16 * c))).astype(np.float32)
        p[f"{s}.proj.bias"] = (0.1 * r.standard_normal(d // 2)).astype(np.float32)
    for i in range(len(dil)):
        q = f"blocks.{i}."
        p[q + "norm.weight"] = np.ones(d, np.float32)
        p[q + "norm.bias"] = np.zeros(d, np.float32)
        p[q + "dw.weight"] = (0.3 * r.standard_normal((d, 1, 5))).astype(np.float32)
        p[q + "dw.bias"] = (0.1 * r.standard_normal(d)).astype(np.float32)
        p[q + "ff.0.weight"] = (0.3 * r.standard_normal((2 * d, d))).astype(np.float32)
        p[q + "ff.0.bias"] = np.zeros(2 * d, np.float32)
        p[q + "ff.3.weight"] = (0.3 * r.standard_normal((d, 2 * d))).astype(np.float32)
        p[q + "ff.3.bias"] = np.zeros(d, np.float32)
    return p


def test_crt_chunks_equal_one_pass_and_causal():
    p = crt_params()
    feat = np.random.default_rng(5).standard_normal((300, 32, 12)).astype(np.float32)
    full = _crt.crt_log_probs(p, feat, ring_k=5, kernel=5, dilations=[1, 2], chunk=10_000)
    for ch in (7, 50):
        np.testing.assert_allclose(_crt.crt_log_probs(p, feat, ring_k=5, kernel=5, dilations=[1, 2], chunk=ch), full,
                                   atol=1e-5)
    feat2 = feat.copy()
    feat2[200:] += 5.0  # a change in the future does not change the past (causal)
    np.testing.assert_allclose(_crt.crt_log_probs(p, feat2, ring_k=5, kernel=5, dilations=[1, 2])[:200], full[:200],
                               atol=1e-6)
    np.testing.assert_allclose(np.exp(full).sum(1), 1.0, atol=1e-4)


def test_erf_gelu_accuracy():
    xs = np.linspace(-6, 6, 2001).astype(np.float64)
    ref = np.array([math.erf(v) for v in xs])
    assert np.abs(_crt.erf(xs) - ref).max() < 2e-7
    x = np.float32(1.3)
    assert abs(float(_crt.gelu(np.array([x]))[0]) - 1.3 * 0.5 * (1 + math.erf(1.3 / math.sqrt(2)))) < 1e-6


def test_features_shape_and_timing():
    x = np.random.default_rng(6).standard_normal((2000, 32)).astype(np.float32)
    f = _crt.frames_from_block(x)
    assert f.shape == (_crt.n_frames(2000), 32, 12) == (97, 32, 12)
    np.testing.assert_allclose(_crt.frames_from_block(x[20:84])[0], f[1], atol=1e-5)  # frame 1 = samples 20..83


def test_crt_model_end_to_end(tmp_path):
    p = crt_params()
    w = tmp_path / "fake-crt.weights.npz"
    np.savez(w, **p)
    doc = {"schema": MANIFEST_SCHEMA, "name": "fake-crt", "version": "1", "title": "tiny CRT", "status": "available",
           "task": "test", "modality": "emg", "runtime": "crt-ctc",
           "input": {"sample_rate_hz": 2000.0, "file_format": "emg2qwerty-hdf5"},
           "output": {"vocab_type": "char", "vocab_id": "fidetype-p11-01-keys-v1", "frame_period_s": 0.01,
                      "latency_s": 0.0},
           "architecture": {"ring_k": 5, "kernel": 5, "dilations": [1, 2]}, "files": [entry("weights", w)],
           "licence": LIC_NC, "trust": None}
    mp = write_manifest(tmp_path, doc)
    with pytest.raises(ftp.ResearchOnlyRefused):
        ftp.load(str(mp), weights=tmp_path)
    m = ftp.load(str(mp), weights=tmp_path, accept_research_only=True)
    st = m.decode(np.random.default_rng(7).standard_normal((4000, 32)).astype(np.float32))
    assert st.vocab_type == "char" and st.vocab[0] == "<blank>" and len(st.vocab) == 98
    assert st.frame_times[0] == pytest.approx(0.032) and st.frame_period == pytest.approx(0.01)
    assert st.meta["data.research_only"] is True
    assert C.check(st).passes("provenance")
    with pytest.raises(ValueError, match="32"):
        m.decode(np.zeros((100, 8), np.float32))


# --- Willett handwriting model (xbody-ctc runtime, P14-33) -------------------------------------------------


def xbody_params(seed: int = 0, d: int = 8, dil: tuple[int, ...] = (1, 2), n_sess: int = 2) -> dict:
    r = np.random.default_rng(seed)
    p = {k: v for k, v in crt_params(seed, d=d, dil=dil).items() if k.startswith(("blocks.", "out_norm.", "head."))}
    p.update({"mean": r.random((n_sess, 192)).astype(np.float32), "std": (1 + r.random((n_sess, 192))).astype(np.float32),
              "stem.weight": (0.2 * r.standard_normal((d, 192))).astype(np.float32),
              "stem.bias": (0.1 * r.standard_normal(d)).astype(np.float32)})
    return p


def xbody_reference(p: dict, x: np.ndarray, s: int, dil: tuple[int, ...]) -> np.ndarray:
    """A plain loop of the same maths (no chunking, explicit causal sums), float64."""
    p = {k: v.astype(np.float64) for k, v in p.items()}
    gelu = np.vectorize(lambda v: 0.5 * v * (1 + math.erf(v / math.sqrt(2))))

    def ln(h, w, b):
        return (h - h.mean(1, keepdims=True)) / np.sqrt(h.var(1, keepdims=True) + 1e-5) * w + b

    h = ((x.astype(np.float64) - p["mean"][s]) / p["std"][s]) @ p["stem.weight"].T + p["stem.bias"]
    for i, dl in enumerate(dil):
        q = f"blocks.{i}."
        n = ln(h, p[q + "norm.weight"], p[q + "norm.bias"])
        c = np.zeros_like(n)
        for t in range(len(n)):
            acc = p[q + "dw.bias"].copy()
            for j in range(5):
                k = t - (4 - j) * dl
                if k >= 0:
                    acc = acc + p[q + "dw.weight"][:, 0, j] * n[k]
            c[t] = acc
        f = gelu(c) @ p[q + "ff.0.weight"].T + p[q + "ff.0.bias"]
        h = h + gelu(f) @ p[q + "ff.3.weight"].T + p[q + "ff.3.bias"]
    o = ln(h, p["out_norm.weight"], p["out_norm.bias"]) @ p["head.weight"].T + p["head.bias"]
    mx = o.max(1, keepdims=True)
    return o - mx - np.log(np.exp(o - mx).sum(1, keepdims=True))


def test_xbody_runtime_equals_reference_chunks_and_causal():
    from fidetype.pretrained import _xbody

    p = xbody_params()
    x = np.random.default_rng(1).integers(0, 6, (120, 192)).astype(np.uint8)
    full = _xbody.xbody_log_probs(p, x, 1, kernel=5, dilations=[1, 2])
    np.testing.assert_allclose(full, xbody_reference(p, x, 1, (1, 2)), atol=1e-4)
    np.testing.assert_allclose(_xbody.xbody_log_probs(p, x, 1, kernel=5, dilations=[1, 2], chunk=17), full, atol=1e-5)
    x2 = x.copy()
    x2[80:] = 9  # the future does not change the past
    np.testing.assert_allclose(_xbody.xbody_log_probs(p, x2, 1, kernel=5, dilations=[1, 2])[:80], full[:80], atol=1e-6)
    assert not np.allclose(_xbody.xbody_log_probs(p, x, 0, kernel=5, dilations=[1, 2]), full)  # per-session z-score
    with pytest.raises(ValueError, match="192"):
        _xbody.xbody_log_probs(p, x[:, :10], 0, kernel=5, dilations=[1, 2])
    with pytest.raises(ValueError, match="session"):
        _xbody.xbody_log_probs(p, x, 2, kernel=5, dilations=[1, 2])
    assert _xbody.willett_text("hi>there~#") == "hi there."


def xbody_manifest(tmp: Path, sessions: list[str] | None = None) -> Path:
    w = tmp / "fake-hw.weights.npz"
    np.savez(w, **xbody_params())
    doc = {"schema": MANIFEST_SCHEMA, "name": "fake-hw", "version": "1", "title": "tiny XBody", "status": "available",
           "task": "test", "modality": "intracortical", "runtime": "xbody-ctc", "language": "en",
           "input": {"bin_s": 0.01, "file_format": "willett-hw-mat"},
           "output": {"vocab_type": "char", "vocab_id": "fidetype-p11-01-keys-v1", "frame_period_s": 0.01,
                      "latency_s": 0.0},
           "architecture": {"kernel": 5, "dilations": [1, 2],
                            "sessions": sessions or ["t5.2019.05.08", "t5.2019.11.25"]},
           "files": [entry("weights", w)], "licence": LIC_CC0, "trust": None}
    return write_manifest(tmp, doc)


def fake_sentences_mat(folder: Path) -> None:
    """A tiny Willett-like sentences.mat: 4 sentences in blocks 1, 1, 2, 2; sentence 1 is excluded."""
    sio = pytest.importorskip("scipy.io")
    folder.mkdir(parents=True)
    rng = np.random.default_rng(3)
    ts = rng.integers(0, 4, (400, 192)).astype(np.uint8)
    bts = np.r_[np.ones(200), 2 * np.ones(200)].astype(np.int64)[:, None]
    texts = np.empty((4, 1), dtype=object)
    for i, t in enumerate(["ab>c~", "zz", "hello#", "x>y"]):
        texts[i, 0] = np.array([t])
    cond = np.empty((4, 1), dtype=object)
    for i in range(4):
        cond[i, 0] = np.array(["OL"])
    sio.savemat(folder / "sentences.mat", {
        "neuralActivityTimeSeries": ts, "blockNumsTimeSeries": bts,
        "goCueOnsetTimeBin": np.array([[1], [101], [201], [301]]),  # MATLAB 1-based
        "numTimeBinsPerSentence": np.array([[50], [40], [60], [80]]),
        "sentenceBlockNums": np.array([[1], [1], [2], [2]]), "excludedSentences": np.array([[0], [1], [0], [0]]),
        "intendedText": texts, "sentenceCondition": cond})


def test_willett_reader_and_xbody_model_end_to_end(tmp_path):
    sess = tmp_path / "Datasets" / "t5.2019.11.25"
    fake_sentences_mat(sess)
    items = R.read_willett_session(sess)
    assert [it.extra["trial"] for it in items] == [0, 2, 3]  # the excluded sentence is skipped
    assert [it.truth for it in items] == ["ab c.", "hello", "x y"]
    assert items[0].x.shape == (150, 192) and items[0].x.dtype == np.uint8  # 50 bins + 100 tail in the same block
    assert items[1].x.shape == (160, 192)  # 60 + 100
    assert items[2].x.shape == (100, 192)  # 80 bins + 20 tail: the recording ends
    assert R.willett_test_block(items) == 2
    assert len(R.read_willett_session(sess / "sentences.mat", include_excluded=True)) == 4
    assert [it.extra["block"] for it in R.read_willett_session(sess, blocks=[2])] == [2, 2]
    with pytest.raises(ValueError, match="t5"):
        R.read_willett_session(tmp_path / "Datasets")
    with pytest.raises(ValueError, match="too large"):
        R.read_willett_session(sess, max_bytes=10)
    m = ftp.load(str(xbody_manifest(tmp_path)), weights=tmp_path)
    assert isinstance(m, ftp.XBodyCtcDecoder)
    pairs = m.decode(str(sess), with_items=True)
    assert len(pairs) == 3
    for it, st in pairs:
        assert st.vocab_type == "char" and len(st.vocab) == 98 and st.blank_id == 0
        assert st.frame_times[0] == pytest.approx(0.01) and st.frame_period == pytest.approx(0.01)
        assert st.meta["data.licence"] == "CC0-1.0" and st.meta["data.research_only"] is False
        assert st.meta["decoder.weights_sha256"] == m.weights_sha256
        assert not any(t in json.dumps(st.meta) for t in ("hello", "ab c"))  # truth never in a stream
        assert C.check(st).passes("provenance"), [f.check_id for f in C.check(st).failures()]
        assert isinstance(m.text(st), str)
    st = m.decode(pairs[1][0].x, session="t5.2019.11.25")
    np.testing.assert_allclose(st.log_probs, pairs[1][1].log_probs)
    np.testing.assert_allclose(m.decode(pairs[1][0].x, session=1).log_probs, st.log_probs)
    assert len(m.decode_file(sess, blocks=[1])) == 1
    with pytest.raises(ValueError, match="unknown session"):
        m.decode(pairs[1][0].x, session="t5.2099.01.01")
    with pytest.raises(ftp.NoTrustConfig):
        m.guard()
    with pytest.raises(ftp.WeightsMismatch, match="sessions"):
        ftp.load(str(xbody_manifest(tmp_path, sessions=["t5.2019.05.08"])), weights=tmp_path)


WILLETT_WEIGHTS = Path(r"C:\Users\zhang\bci-data\pretrained\willett-hw\willett-hw.weights.npz")
WILLETT_RAW = Path(r"C:\Users\zhang\bci-data\raw\willett-handwriting\extracted\handwritingBCIData\Datasets")


@pytest.mark.skipif(not WILLETT_WEIGHTS.is_file(), reason="willett-hw weights are local only (not hosted, P14-02)")
def test_willett_hw_real_weights():
    m = ftp.load("willett-hw", weights=WILLETT_WEIGHTS.parent)
    st = m.decode(np.zeros((50, 192), np.uint8), session="t5.2020.01.15")
    assert st.log_probs.shape == (50, 98) and C.check(st).passes("provenance")
    if (WILLETT_RAW / "t5.2020.01.15" / "sentences.mat").is_file():
        from fidetype.eval.metrics import edit_distance

        items = R.read_willett_session(WILLETT_RAW / "t5.2020.01.15")
        tb = R.willett_test_block(items)
        test = [it for it in items if it.extra["block"] == tb][:3]
        ed = sum(edit_distance(it.truth, m.text(m.decode(it.x, session=it.session))) for it in test)
        assert ed / sum(len(it.truth) for it in test) < 0.6  # weak, but far from chance


# --- key-window model (KT-sEMG runtime), with the packaged synthetic-keys files ------------------------------


def test_key_lda_model_with_guard(tmp_path):
    from fidetype.live.model import builtin_dir

    src = builtin_dir()
    files = []
    for role, suf in (("card", ".model.json"), ("weights", ".weights.json"), ("guard", ".guard.json")):
        shutil.copy(src / f"synthetic-keys{suf}", tmp_path / f"synthetic-keys{suf}")
        files.append(entry(role, tmp_path / f"synthetic-keys{suf}"))
    doc = {"schema": MANIFEST_SCHEMA, "name": "fake-keys", "version": "1", "title": "synthetic keys",
           "status": "available", "task": "test", "modality": "emg", "runtime": "key-lda",
           "input": {"file_format": "kt-semg-run"}, "output": {"vocab_type": "key", "latency_s": 0.05},
           "files": files, "licence": {"data.licence": "LicenseRef-fidetype-own", "data.research_only": False},
           "trust": {"config": "file:synthetic-keys.guard.json", "decode": "nbest-keys"}}
    m = ftp.load(str(write_manifest(tmp_path, doc)), weights=tmp_path)
    rng = np.random.default_rng(0)
    sig = rng.standard_normal((int(m.model.sample_rate * 3), m.model.channels)).astype(np.float32)
    keys = [0.5, 1.0, 1.5, 2.0]
    st = m.decode(sig, times=keys)
    assert st.vocab_type == "key" and st.log_probs.shape[0] == len(keys)
    assert st.meta["decoder.weights_sha256"] == m.weights_sha256
    assert C.check(st).passes("provenance"), [f.check_id for f in C.check(st).failures()]
    g = m.guard()
    r = g.decide(m.nbest(st))
    assert r.action in ("commit", "offer", "withhold")
    with pytest.raises(ValueError, match="times"):
        m.decode(sig)


def test_cli_list_info_path(capsys, tmp_path):
    assert cli_main(["list"]) == 0
    out = capsys.readouterr().out
    assert "t15-m4-13" in out and "emg2qwerty-p11-01" in out and "true" in out
    assert cli_main(["info", "kt-semg-lda"]) == 0
    assert "CC-BY-4.0" in capsys.readouterr().out
    assert cli_main(["path", "t15-m4-13", "--cache-dir", str(tmp_path)]) == 0
    assert "MISSING" in capsys.readouterr().out
    assert cli_main(["verify", "t15-m4-13", "--cache-dir", str(tmp_path)]) == 2
    from fidetype.cli import main as ft_main

    assert ft_main(["decoders", "list", "--json"]) == 0
