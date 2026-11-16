"""P11-01 unit tests and CPU smoke train (synthetic data only; no real data, no GPU).

Run (repo root): set HIP_VISIBLE_DEVICES=-1 and CUDA_VISIBLE_DEVICES=-1, then
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -m pytest -q experiments/2026-11-16-p11-01-emg-decoder/test_p11_01.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")
torch = pytest.importorskip("torch")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emgdec as E  # noqa: E402
import prep as P  # noqa: E402
import train as TR  # noqa: E402

from fidetype.adapters import emg2qwerty as e2q  # noqa: E402
from fidetype.eval.metrics import edit_distance  # noqa: E402

T0 = 1_600_000_000.0
FS = 2000.0
WORDS = ("abc", "fed", "bad", "cafe", "Bead")


def write_session(path: Path, name: str, user: str, seed: int, n_prompts: int = 6) -> None:
    """A small session in the emg2qwerty layout; each key drives its own channel group."""
    rng = np.random.default_rng(seed)
    keys, prompts, t = [], [], 1.0
    for p in range(n_prompts):
        text = " ".join(WORDS[(p + j + seed) % len(WORDS)] for j in range(2))
        start = t - 0.2
        for ch in text:
            keys.append({"ascii": ord(ch), "key": "Key.space" if ch == " " else ch, "start": T0 + t, "end": T0 + t + 0.1})
            t += 0.2
        keys.append({"ascii": 0, "key": "Key.shift", "start": T0 + t - 0.05, "end": T0 + t})  # dropped (modifier)
        keys.append({"ascii": 8, "key": "Key.backspace", "start": T0 + t, "end": T0 + t + 0.1})
        t += 0.2
        keys.append({"ascii": 9166, "key": "Key.enter", "start": T0 + t, "end": T0 + t + 0.1})
        t += 0.2
        prompts.append({"name": "text_prompt", "start": T0 + start, "end": T0 + t - 0.1,
                        "payload": {"prompt_num": p, "text": text + "\u23ce"}, "payload_type": "text_prompt"})
        t += 0.8
    keys.sort(key=lambda k: k["start"])
    n = int((t + 1.0) * FS)
    times = T0 + np.arange(n) / FS
    emg = rng.normal(0, 1.0, (n, 32)).astype(np.float32)
    for k in keys:
        tok = P.key_token(k["key"])
        if tok is None:
            continue
        a = int((k["start"] - T0 - 0.08) * FS)
        g = tok % 8
        emg[a:a + 200, 4 * g:4 * g + 4] *= 6.0
    dt = np.dtype([("emg_right", "<f4", (16,)), ("time", "<f8"), ("emg_left", "<f4", (16,))])
    rec = np.zeros(n, dtype=dt)
    rec["emg_left"], rec["emg_right"], rec["time"] = emg[:, :16], emg[:, 16:], times
    with h5py.File(path, "w") as f:
        g = f.create_group("emg2qwerty")
        g.create_dataset("timeseries", data=rec)
        for k, v in {"condition": "on_keyboard", "daq_channels": "16", "daq_sample_rate": "2000.0",
                     "session_name": name, "user": user, "schedule": "x", "keystrokes": json.dumps(keys),
                     "prompts": json.dumps(prompts)}.items():
            g.attrs[k] = v
        g.attrs["duration_mins"] = n / FS / 60
        g.attrs["quality_check_tags"] = np.zeros(0)


# --- prep ----------------------------------------------------------------------------------------


def test_vocab_and_tokens():
    assert len(P.VOCAB) == 98 and P.VOCAB[0] == "<blank>" and len(set(P.VOCAB)) == 98
    assert P.key_token("a") == P.TOK["a"] and P.key_token("Key.space") == P.TOK[" "]
    assert P.VOCAB[P.key_token("Key.backspace")] == P.BACKSPACE and P.VOCAB[P.key_token("Key.enter")] == P.ENTER
    for k in ("Key.shift", "Key.left", "Key.tab", "\u00e9", "<blank>"):
        assert P.key_token(k) is None


def test_frames_and_mapping():
    assert P.n_frames(63) == 0 and P.n_frames(64) == 1 and P.n_frames(84) == 2
    assert np.allclose(P.band_matrix().sum(axis=0), 1.0) and P.band_matrix()[0].sum() == 0
    x = np.random.default_rng(0).normal(size=(2000, 32)).astype(np.float32)
    f = P.frames_from_block(x)
    assert f.shape == (P.n_frames(2000), 32, 12) and np.isfinite(f).all()
    # frame k ends at k*HOP + WIN; a key at sample s maps to the first frame that ends at or after s
    for s in (0, 63, 64, 65, 84, 85, 1000):
        k = int(P.sample_to_frame(np.array([s]))[0])
        assert k * P.HOP + P.WIN >= s and (k == 0 or (k - 1) * P.HOP + P.WIN < s)


def test_process_one_blocks_equal_one_pass(tmp_path, monkeypatch):
    src = tmp_path / "data"; src.mkdir()
    write_session(src / "s1.hdf5", "s1", "00000001", 0)
    monkeypatch.setattr(P, "BLOCK_ROWS", 5000)  # many blocks
    out = tmp_path / "cache"; (out / "sessions").mkdir(parents=True)
    rec = P.process_one(str(src / "s1.hdf5"), str(out))
    feat = np.load(out / "sessions" / "s1.feat.npy")
    with e2q.Session(src / "s1.hdf5") as s:
        ref = P.frames_from_block(s.read_emg(0, s.n_samples)).astype(np.float16)
    assert feat.shape == ref.shape == (rec["n_frames"], 32, 12)
    assert np.array_equal(feat, ref)
    lab = np.load(out / "sessions" / "s1.lab.npz")
    assert rec["dropped_keys"] == 6 and rec["n_keys"] == len(lab["key_tok"]) > 0
    assert np.all(np.diff(lab["key_frame"]) > 0) and len(lab["prompt_lo"]) == 6
    assert (P.process_one(str(src / "s1.hdf5"), str(out))) == rec  # marker -> skipped


def test_splits_rule():
    rows = [e2q.MetadataRow(f"{u:08d}", f"2020-01-{d:02d}-x-{u}", 10.0, 100, 10, "[]")
            for u in range(20) for d in range(1, (12 if u % 2 else 5))]
    sp = P.make_splits(rows)
    assert len(sp["test_users"]) == 8
    assert all(int(u) % 2 == 1 for u in sp["test_users"])  # only users with >= 8 sessions
    gt = set(sp["generic_train"])
    for u in sp["test_users"]:
        p = sp["personal"][u]
        assert len(p["val"]) == 2 and len(p["test"]) == 2 and max(p["train"]) < min(p["val"]) < min(p["test"])
        assert not (set(p["train"]) | set(p["val"]) | set(p["test"])) & gt
    assert P.make_splits(list(reversed(rows))) == sp  # order-independent


# --- metric and decoding ----------------------------------------------------------------------------


def test_levenshtein_matches_reference():
    rng = np.random.default_rng(1)
    for _ in range(200):
        a = rng.integers(0, 5, rng.integers(0, 30)); b = rng.integers(0, 5, rng.integers(0, 30))
        assert E.levenshtein(a, b) == edit_distance(list(a), list(b))


def test_greedy():
    lp = np.log(np.eye(4)[[0, 1, 1, 0, 1, 2, 2, 3, 0]] * 0.97 + 0.01)
    assert E.greedy(lp).tolist() == [1, 1, 2, 3]


# --- model ----------------------------------------------------------------------------------------


def _model(d=32):
    cfg = E.ModelCfg(d=d, ring_c=4, dilations=(1, 2, 4), dropout=0.0)
    return E.CRT(cfg, np.zeros((32, 12), np.float32), np.ones((32, 12), np.float32)).eval()


def test_model_is_causal_and_chunking_exact():
    torch.manual_seed(0)
    m = _model()
    x = np.random.default_rng(2).normal(size=(300, 32, 12)).astype(np.float32)
    full = E.session_log_probs(m, x, "cpu", chunk=10_000)
    chunked = E.session_log_probs(m, x, "cpu", chunk=37)
    assert np.allclose(full, chunked, atol=1e-5)
    y = x.copy(); y[200:] += 5.0
    out2 = E.session_log_probs(m, y, "cpu")
    assert np.allclose(full[:200], out2[:200], atol=1e-5) and not np.allclose(full[200:], out2[200:])
    assert np.allclose(np.exp(full).sum(1), 1.0, atol=1e-4)
    assert m.cfg.receptive_field() == 1 + 4 * 7


def test_augment_deterministic_and_rotation():
    x = torch.randn(3, 50, 32, 12)
    a = E.AugCfg(gain_sd=0.0, time_masks=0, band_masks=0)
    r1 = E.augment(x, a, torch.Generator().manual_seed(5)); r2 = E.augment(x, a, torch.Generator().manual_seed(5))
    assert torch.equal(r1, r2)
    for b in range(3):  # each band is a ring rotation of the input by -1, 0 or +1
        for lo in (0, 16):
            assert any(torch.equal(r1[b, :, lo:lo + 16], torch.roll(x[b, :, lo:lo + 16], s, dims=1)) for s in (-1, 0, 1))
    full = E.augment(x, E.AugCfg(), torch.Generator().manual_seed(5))
    assert full.shape == x.shape and torch.isfinite(full).all()


# --- end-to-end smoke (cache -> train -> eval -> NTS) ----------------------------------------------------


@pytest.fixture(scope="module")
def cache(tmp_path_factory):
    root = tmp_path_factory.mktemp("p11")
    src = root / "data"; src.mkdir()
    out = root / "cache"; (out / "sessions").mkdir(parents=True)
    rows = []
    for u in range(10):
        for d in range(8 if u < 8 else 3):
            name = f"2020-01-{d + 1:02d}-{u}"
            write_session(src / f"{name}.hdf5", name, f"{u:08d}", seed=u * 10 + d, n_prompts=4)
            r = P.process_one(str(src / f"{name}.hdf5"), str(out))
            rows.append(e2q.MetadataRow(f"{u:08d}", name, r["n_samples"] / FS / 60, r["n_keys"], 4, "[]"))
    (out / "splits.json").write_text(json.dumps(P.make_splits(rows)), encoding="utf-8")
    P.cmd_index(type("A", (), {"out": str(out)})())
    return out


def _tiny_config(path: Path, steps=6) -> Path:
    raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    for k in ("generic", "personal"):
        raw[k].update(steps=steps, warmup=2, batch=4, window=120, val_every=3, ckpt_minutes=100.0)
        raw[k]["model"].update(d=32, ring_c=4, dilations=[1, 2])
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_sampler_deterministic(cache):
    st = E.SessionStore(cache)
    sp = json.loads((cache / "splits.json").read_text())
    s = E.WindowSampler(st, sp["generic_train"], 120, 4, 6, 0)
    a, b = s.batch_at(7), s.batch_at(7)
    assert np.array_equal(a["x"], b["x"]) and np.array_equal(a["targets"], b["targets"])
    assert a["x"].shape == (4, 120, 32, 12) and a["target_lengths"].sum() == len(a["targets"])
    assert not np.array_equal(s.batch_at(8)["x"], a["x"])


def test_resume_is_exact(cache, tmp_path):
    cfgp = _tiny_config(tmp_path / "cfg.json")
    o1, o2 = tmp_path / "o1", tmp_path / "o2"
    TR.main(["generic", "--cache", str(cache), "--out", str(o1), "--config", str(cfgp), "--device", "cpu", "--no-budget"])
    assert TR.main(["generic", "--cache", str(cache), "--out", str(o2), "--config", str(cfgp), "--device", "cpu",
                    "--no-budget", "--max-steps", "4"]) == 0
    assert not (o2 / "generic" / "DONE.json").exists()
    TR.main(["generic", "--cache", str(cache), "--out", str(o2), "--config", str(cfgp), "--device", "cpu", "--no-budget"])
    a = torch.load(o1 / "generic" / "latest.pt", weights_only=True)["model"]
    b = torch.load(o2 / "generic" / "latest.pt", weights_only=True)["model"]
    assert a.keys() == b.keys() and all(torch.equal(a[k], b[k]) for k in a)


def test_pause_file(cache, tmp_path):
    cfgp = _tiny_config(tmp_path / "cfg.json")
    o = tmp_path / "o"; o.mkdir(); (o / "pause").write_text("")
    rc = TR.main(["generic", "--cache", str(cache), "--out", str(o), "--config", str(cfgp), "--device", "cpu", "--no-budget"])
    assert rc == TR.PAUSED and torch.load(o / "generic" / "latest.pt", weights_only=True)["step"] == 1


def test_smoke_all_stages(cache, tmp_path):
    cfgp = _tiny_config(tmp_path / "cfg.json")
    o = tmp_path / "run"
    assert TR.main(["all", "--cache", str(cache), "--out", str(o), "--config", str(cfgp), "--device", "cpu", "--no-budget"]) == 0
    assert (o / "DONE").exists()
    res = json.loads((o / "results.json").read_text())
    for k in ("generic_val", "generic_test", "personal_test", "control_time_shuffled", "emission_delay_ms"):
        assert k in res
    assert 0 <= res["personal_test"]["cer_pooled"] and res["personal_test"]["ref"] > 0
    nts = json.loads((o / "nts" / "DONE.json").read_text())
    assert nts["streams"] > 0 and nts["pass"] == nts["streams"]
    text = (o / "results.json").read_text()
    assert not any(f"\"{u:08d}\"" in text for u in range(10))  # no user ids in the aggregate file


def test_shift_impl_equals_torch_convs():
    torch.manual_seed(3)
    cfg = E.ModelCfg(d=32, ring_c=4, dilations=(1, 2, 4), dropout=0.0)
    m1 = E.CRT(cfg, np.zeros((32, 12), np.float32), np.ones((32, 12), np.float32)).eval()
    cfg2 = E.ModelCfg(d=32, ring_c=4, dilations=(1, 2, 4), dropout=0.0, conv_impl="shift")
    m2 = E.CRT(cfg2, np.zeros((32, 12), np.float32), np.ones((32, 12), np.float32)).eval()
    m2.load_state_dict(m1.state_dict())
    x = torch.randn(2, 90, 32, 12)
    with torch.no_grad():
        assert torch.allclose(m1(x), m2(x), atol=1e-5)
    # gradients agree too
    m1.train(); m2.train()
    m1(x).sum().backward(); m2(x).sum().backward()
    for (n, a), (_, b) in zip(m1.named_parameters(), m2.named_parameters()):
        assert torch.allclose(a.grad, b.grad, atol=1e-4, rtol=1e-4), n


def test_budget_stage(cache, tmp_path):
    cfgp = _tiny_config(tmp_path / "cfg.json")
    raw, g, p = TR.load_cfgs(cfgp)
    g.steps = 200_000
    raw["budget_hours_generic"] = 0.5
    st = E.SessionStore(cache)
    sp = json.loads((cache / "splits.json").read_text())
    rec = TR.stage_budget(tmp_path / "o", st, raw, g, sp, "cpu", pilot_steps=2, warm_steps=1)
    assert rec["conv_impl"] in ("torch", "shift") and 1000 <= rec["generic_steps"] <= 200_000
    assert rec["generic_steps"] % 1000 == 0 and not (tmp_path / "o" / "pilot").exists()
    assert TR.stage_budget(tmp_path / "o", st, raw, g, sp, "cpu") == rec  # fixed once
