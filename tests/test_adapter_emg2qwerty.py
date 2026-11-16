"""Tests for the emg2qwerty adapter (synthetic HDF5 fixtures built here; no real data)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from fidetype.adapters import emg2qwerty as E
from fidetype.adapters import kt_semg as K
from fidetype.conformance import check_stream

h5py = pytest.importorskip("h5py")

T0 = 1_600_000_000.0
FS = 2000.0
ALPHABET = "abcdef"  # six key classes; each one drives its own channel group in the synthetic EMG


def _write_session(path, *, name="2020-01-01-1600000000-keystrokes-00000001", user="00000001", seed=0,
                   n_prompts=6, words=("abc", "fed", "bad", "cafe"), rate="2000.0", extra_keys=(),
                   tamper=None):
    """A small session in the emg2qwerty layout: prompts of words, one key press every 0.25 s."""
    rng = np.random.default_rng(seed)
    keys, prompts, t = [], [], 1.0
    for p in range(n_prompts):
        text = " ".join(words[(p + j) % len(words)] for j in range(2))
        start = t - 0.2
        for ch in text:
            keys.append({"ascii": ord(ch), "key": "Key.space" if ch == " " else ch, "start": T0 + t, "end": T0 + t + 0.1})
            t += 0.25
        keys.append({"ascii": 9166, "key": "Key.enter", "start": T0 + t, "end": T0 + t + 0.1})
        t += 0.25
        prompts.append({"name": "text_prompt", "start": T0 + start, "end": T0 + t - 0.1,
                        "payload": {"prompt_num": p, "text": text + E.PROMPT_END_MARK}, "payload_type": "text_prompt"})
        t += 1.0
    for k in extra_keys:
        keys.append(k)
    keys.sort(key=lambda k: k["start"])
    prompts.insert(0, {"name": "Intro", "start": T0, "end": T0 + 0.5, "payload": None, "payload_type": None})
    n = int((t + 1.0) * FS)
    times = T0 + np.arange(n) / FS + rng.uniform(-2e-5, 2e-5, n)
    emg = rng.normal(0, 1.0, (n, 32)).astype(np.float32)
    for k in keys:
        cls = ALPHABET.find(k["key"]) if len(k["key"]) == 1 else (6 if k["key"] == "Key.space" else 7)
        if cls < 0:
            continue
        a = int((k["start"] - T0 - 0.1) * FS)
        emg[a:a + 200, 4 * cls:4 * cls + 4] *= 6.0  # channel groups 0-3, 4-7, ...: left band then right band
    dt = np.dtype([("emg_right", "<f4", (16,)), ("time", "<f8"), ("emg_left", "<f4", (16,))])
    rec = np.zeros(n, dtype=dt)
    rec["emg_left"], rec["emg_right"], rec["time"] = emg[:, :16], emg[:, 16:], times
    with h5py.File(path, "w") as f:
        g = f.create_group("emg2qwerty")
        g.create_dataset("timeseries", data=rec)
        attrs = {"condition": "on_keyboard", "daq_channels": "16", "daq_sample_rate": rate, "session_name": name,
                 "user": user, "schedule": "6.3", "keystrokes": json.dumps(keys), "prompts": json.dumps(prompts)}
        if tamper:
            attrs.update(tamper)
        for k, v in attrs.items():
            g.attrs[k] = v
        g.attrs["duration_mins"] = n / FS / 60
        g.attrs["quality_check_tags"] = np.zeros(0)
    return emg, keys


def test_key_codes_and_vocab():
    assert E.KEY_VOCAB == K.KEY_VOCAB and E.KEY_VOCAB_ID == K.KEY_VOCAB_ID
    assert E.key_class("a") == 0 and E.key_class("Key.space") == 26
    assert E.KEY_VOCAB[E.key_class("Key.backspace")] == "Backspace" and E.KEY_VOCAB[E.key_class("Key.enter")] == "Enter"
    assert E.key_code("Key.left") == "ArrowLeft" and E.key_class("Key.left") is None
    assert E.key_code("Key.media_volume_up") is None and E.key_class("3") is None
    assert E.typed_char("Key.backspace") == "\x08" and E.typed_char("Key.shift") == "" and E.typed_char("x") == "x"


def test_parse_attributes_and_rejects_bad_json():
    ks = E.parse_keystrokes(json.dumps([{"ascii": 98, "key": "b", "start": 2.0, "end": 2.1},
                                        {"ascii": 97, "key": "a", "start": 1.0, "end": 1.1}]))
    assert [k.key for k in ks] == ["a", "b"] and ks[0].code == "KeyA"
    with pytest.raises(ValueError):
        E.parse_keystrokes('[{"key": "a", "start": NaN, "end": 1}]')
    with pytest.raises(ValueError):
        E.parse_keystrokes('[{"key": "a", "start": "1", "end": 1}]')
    with pytest.raises(ValueError):
        E.parse_keystrokes('{"key": "a"}')
    pr = E.parse_prompts(json.dumps([
        {"name": "Intro", "start": 0, "end": 1, "payload": None},
        {"name": "text_prompt", "start": 5, "end": 6, "payload": {"prompt_num": 1, "text": "b⏎"}},
        {"name": "text_prompt", "start": 2, "end": 3, "payload": {"prompt_num": 0, "text": "a b⏎"}}]))
    assert [(p.index, p.prompt_num, p.text) for p in pr] == [(0, 0, "a b"), (1, 1, "b")]
    with pytest.raises(ValueError):
        E.parse_prompts('[{"name": "text_prompt", "start": 3, "end": 2, "payload": {"text": "x"}}]')


def test_session_reader_events_and_prompts(tmp_path):
    p = tmp_path / "s.hdf5"
    emg, keys = _write_session(p, extra_keys=[{"ascii": None, "key": "Key.left", "start": T0 + 0.6, "end": T0 + 0.7},
                                              {"ascii": 97, "key": "a", "start": T0 - 5.0, "end": T0 - 4.9}])
    with E.Session(p) as s:
        assert s.n_samples == len(emg) and s.condition == "on_keyboard" and len(s.prompts) == 6
        np.testing.assert_array_equal(s.read_emg(10, 20), emg[10:20])
        assert s.read_emg(-5, 3).shape == (3, 32) and s.read_emg(5, 5).shape == (0, 32)
        ev = E.key_events(s)
        assert len(ev) == len(keys) - 1  # the press before the recording is dropped
        assert all(b.t > a.t for a, b in zip(ev, ev[1:]))
        for e in ev[:5]:
            assert abs(s.times[e.sample] - (s.t0 + e.t)) <= 0.5 / FS + 1e-4
        pe = E.prompt_events(s, s.prompts[0], ev)
        assert E.typed_text(pe) == s.prompts[0].text + "\r"
        assert "Key.left" not in [e.key for e in pe]  # before the first prompt


def test_session_rejects_bad_files(tmp_path):
    _write_session(tmp_path / "r.hdf5", rate="1000.0")
    with pytest.raises(ValueError, match="sample rate"):
        E.Session(tmp_path / "r.hdf5")
    _write_session(tmp_path / "k.hdf5", tamper={"keystrokes": "not json"})
    with pytest.raises(ValueError):
        E.Session(tmp_path / "k.hdf5")
    with h5py.File(tmp_path / "x.hdf5", "w") as f:
        f.create_group("other")
    with pytest.raises(ValueError, match="no group"):
        E.Session(tmp_path / "x.hdf5")
    (tmp_path / "y.pkl").write_bytes(b"")
    with pytest.raises(ValueError, match="not an HDF5"):
        E.Session(tmp_path / "y.pkl")


def test_streamed_features_equal_in_memory_features(tmp_path):
    p = tmp_path / "s.hdf5"
    emg, _ = _write_session(p)
    with E.Session(p) as s:
        ev = E.key_events(s, margin_s=E.WINDOW_PRE_S)
        samples = [e.sample for e in ev][::-1]  # any order
        X = E.session_features(s, samples, block_rows=777)  # many blocks, windows cut at block edges
    ref = K.window_features(emg, np.array(samples) / FS)
    np.testing.assert_allclose(X, ref, rtol=1e-6, atol=1e-6)


def test_session_baseline_streams_reach_provenance(tmp_path):
    p = tmp_path / "s.hdf5"
    _write_session(p, n_prompts=16)
    out = tmp_path / "out"
    with E.Session(p) as s:
        res = E.run_session_baseline(s, 3, out, min_frames=3)
        texts = [pr.text for pr in s.prompts]
    assert res.n_test > 0 and res.correct / res.n_test > 0.9  # separable toy problem
    assert res.n_streams > 0 and res.streams_at_level == res.n_streams
    files = sorted(out.glob("s003-p*.jsonl"))
    assert len(files) == res.n_streams and (out / "s003-lda.npz").is_file()
    blob = "".join(f.read_text(encoding="utf-8") for f in files)
    assert "00000001" not in blob and "2020-01-01" not in blob and "1600000000" not in blob
    for t in texts:
        assert t not in blob


def test_prompt_stream_meta_and_conformance():
    text = "abc fed"
    codes = [E.key_class("Key.space" if c == " " else c) for c in text]
    lg = np.random.default_rng(1).normal(0, 1, (len(text), 32))
    lg[np.arange(len(text)), codes] += 10
    times = 1.0 + 0.25 * np.arange(len(text))
    sid = E.session_stream_id("2020-01-01-1600000000-keystrokes", 4, "w")
    meta = E.stream_meta(session_index=2, prompt_index=4, weights_sha256="0" * 64, stream_id=sid)
    s = E.prompt_stream(lg, times, meta, latency=E.WINDOW_POST_S)
    assert s.source == "emg2qwerty" and s.vocab_type == "key" and s.blank_id is None
    assert s.meta["decoder.causal"] is True and s.meta["decoder.lookahead_s"] == E.WINDOW_POST_S
    assert E.greedy_codes(s)[:4] == ["KeyA", "KeyB", "KeyC", "Space"]
    rp = s.meta["fidetype.replay"]
    assert rp["licence"] == "CC-BY-NC-SA-4.0" and rp["research_only"] is True and rp["session_index"] == 2
    blob = json.dumps(s.meta)
    assert "2020-01-01" not in blob and "abc fed" not in blob and len(sid) == 32
    rep = check_stream(s, "e2q", [text])
    assert rep.level == "provenance", [f.to_dict() for f in rep.failures()]
    off = E.prompt_stream(lg, times, meta)
    assert off.meta["decoder.causal"] is False and check_stream(off, "e2q-off", [text]).level == "provenance"


def test_metadata_subset_and_run_baseline(tmp_path):
    rows = ["user,session,condition,duration_mins,num_keystrokes,num_prompts,quality_check_tags"]
    for u, n in (("00000002", 2), ("00000001", 2), ("00000003", 1)):
        for j in range(n):
            name = f"2020-01-0{j + 1}-160000000{j}-keystrokes-{u}"
            _write_session(tmp_path / f"{name}.hdf5", name=name, user=u, seed=int(u) * 10 + j, n_prompts=12)
            rows.append(f"{u},{name},on_keyboard,1.5,100,12,[]")
    (tmp_path / "metadata.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    meta = E.read_metadata(tmp_path / "metadata.csv")
    summ = E.metadata_summary(meta)
    assert summ["sessions"] == 5 and summ["users"] == 3 and summ["keystrokes"] == 500
    assert summ["sessions_per_user_min_median_max"] == [1, 2.0, 2]
    sub = E.select_subset(meta, 5, 2)
    assert [s[0][-8:] for s in sub] == ["00000001", "00000002"]  # user 3 has one session only
    rep = E.run_baseline(tmp_path, 2, 2, tmp_path / "out", progress=False)
    sc = rep["session_calibrated"]
    assert rep["subset"]["sessions"] == 4 and sc["streams"] == sc["streams_at_provenance"] > 0
    assert sc["accuracy"] > 0.9 and rep["cross_session_same_user"]["pairs"] == 2
    saved = (tmp_path / "out" / "report.json").read_text(encoding="utf-8")
    assert "00000001" not in saved and json.loads(saved)["licence"] == "CC-BY-NC-SA-4.0"
    assert E.main(["summary", str(tmp_path)]) == 0
    assert E.main(["baseline", str(tmp_path), "--users", "1", "--no-streams", "--no-cross-session"]) == 0
