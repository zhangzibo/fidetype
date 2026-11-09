"""Tests for the SpanishBCBL loader and the preprocessing helpers.

The tests use synthetic inputs only. They need neither MNE nor the data. The
integration test at the end runs only if the local cache exists.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from fidetype.data import preprocess as pp
from fidetype.data import spanishbcbl as sb
from fidetype.streams.vocab import normalize_text

# --------------------------------------------------------------------------
# File names
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, kind, block, retry",
    [
        ("block1.fif", "block", 1, 0),
        ("Block2.fif", "block", 2, 0),
        ("bolck2.fif", "block", 2, 0),
        ("block22.fif", "block", 2, 2),
        ("block2_1.fif", "block", 2, 1),
        ("block1_1.fif", "block", 1, 1),
        ("d2_block1.fif", "block", 1, 0),
        ("s2_block2.fif", "block", 2, 0),
        ("03_11123_block2.fif", "block", 2, 0),
        ("block1-1.fif", "split", None, 0),
        ("tapping.fif", "localizer", None, 0),
        ("Typing.fif", "localizer", None, 0),
        ("typing_s2.fif", "localizer", None, 0),
        ("block2fail.fif", "excluded", None, 0),
        ("testdavid.fif", "excluded", None, 0),
        ("Emptyroom.fif", "excluded", None, 0),
        ("random.fif", "unknown", None, 0),
    ],
)
def test_parse_fif_name(name, kind, block, retry):
    fn = sb.parse_fif_name(name)
    assert fn.kind == kind
    if kind == "block":
        assert (fn.block, fn.retry) == (block, retry)


def test_split_part_base():
    fn = sb.parse_fif_name("bolck2-1.fif")
    assert fn.kind == "split" and fn.base_stem == "bolck2" and fn.part == 1


def test_parse_log_name_and_swap():
    assert sb.parse_log_name("S25-session1_block2_list2.mat") == (25, 1, 2)
    assert sb.parse_log_name("S1-session1-1.mat") == (1, 1, 1)
    # S1/S2 session 2: block numbers in the log names are swapped.
    assert sb.parse_log_name("S1-session2-1.mat") == (1, 2, 2)
    assert sb.parse_log_name("S2-session2-2.mat") == (2, 2, 1)
    assert sb.parse_log_name("notes.mat") is None


def test_participant_ids():
    assert sb.participant_id(1) == sb.participant_id(18) == "P01"
    assert sb.participant_id(4) == sb.participant_id(14) == "P04"
    assert sb.participant_id(5) == sb.participant_id(10) == sb.participant_id(21) == "P05"
    assert sb.participant_id(25) == "P25"


def test_participant_groups_match_dataset_card():
    """The HF dataset card ("Repeated participants (MEG)") lists S1=S18,
    S4=S14, S5=S10=S21, and S23 excluded. The Brain2Qwerty code uses the
    same merge (SUBJECT_MERGE). 25 IDs - 4 merged - S23 = 20 people; the
    release has no logs for S13, so discovery finds 19 (the card's count)."""
    assert set(sb.PARTICIPANT_GROUPS) == {(1, 18), (4, 14), (5, 10, 21)}
    ids = {sb.participant_id(n) for n in range(1, 26) if n not in sb.EXCLUDED_SUBJECTS}
    assert len(ids) == 20
    assert len(ids - {sb.participant_id(13)}) == 19
    # The recording-folder codes agree: S1 and S18 share code 9228.
    disc = sb.discover_blocks(
        ["MEG/FIF/01_9228/220411/d2_block1.fif", "MEG/FIF/18_9228/231121/block1.fif"],
        ["S1-session1-1.mat", "S18-session1_block1_list1.mat"],
    )
    assert {b.participant for b in disc.blocks} == {"P01"}
    assert {b.subject for b in disc.blocks} == {"S1", "S18"}


def test_discover_blocks_synthetic():
    fifs = [
        "MEG/FIF/14_9875/231108/block1.fif",
        "MEG/FIF/14_9875/231108/block1-1.fif",
        "MEG/FIF/14_9875/231108/bolck2.fif",
        "MEG/FIF/14_9875/231108/bolck2-1.fif",
        "MEG/FIF/14_9875/231108/typing.fif",
        "MEG/FIF/14_9875/231115/block1.fif",
        "MEG/FIF/14_9876/231115/block1.fif",  # duplicate folder
        "MEG/FIF/20_11966/231122/block2.fif",
        "MEG/FIF/20_11966/231122/block2_1.fif",  # later retry wins
        "MEG/FIF/23_9948/240514/block2fail.fif",  # excluded subject
        "MEG/FIF/07_10038/230503/testdavid.fif",
        "MEG/FIF/08_11374/230508/block1.fif",
        "MEG/FIF/8_11374/231023/block1.fif",  # S8 session 2 lives in another folder
    ]
    logs = [
        "S14-session1_block1_list1.mat",
        "S14-session1_block2_list2.mat",
        "S14-session2_block1_list2.mat",
        "S20-session1_block2_list2.mat",
        "S8-session1_block1_list1.mat",
        "S8-session2_block1_list2.mat",
    ]
    d = sb.discover_blocks(fifs, logs)
    keys = {b.key: b for b in d.blocks}
    assert set(keys) == {"S14/ses1_block1", "S14/ses1_block2", "S14/ses2_block1", "S20/ses1_block2", "S8/ses1_block1", "S8/ses2_block1"}
    assert keys["S14/ses1_block2"].fif.endswith("bolck2.fif")
    assert keys["S14/ses1_block2"].split_parts == ["MEG/FIF/14_9875/231108/bolck2-1.fif"]
    assert keys["S14/ses2_block1"].fif.startswith("MEG/FIF/14_9875/")
    assert keys["S14/ses1_block1"].participant == "P04"
    assert keys["S20/ses1_block2"].fif.endswith("block2_1.fif")
    assert keys["S8/ses2_block1"].log == "MEG/logs/S8-session2_block1_list2.mat"
    reasons = {e["path"]: e["reason"] for e in d.excluded}
    assert "duplicate" in reasons["MEG/FIF/14_9876/231115/block1.fif"]
    assert "superseded" in reasons["MEG/FIF/20_11966/231122/block2.fif"]
    assert "localizer" in reasons["MEG/FIF/14_9875/231108/typing.fif"]
    assert "S23" in reasons["MEG/FIF/23_9948/240514/block2fail.fif"]
    assert "excluded" in reasons["MEG/FIF/07_10038/230503/testdavid.fif"]


def test_discover_no_log_is_excluded():
    d = sb.discover_blocks(["MEG/FIF/13_8233/231026/block1.fif"], [])
    assert d.blocks == []
    assert "no log" in d.excluded[0]["reason"]


# --------------------------------------------------------------------------
# Clock alignment
# --------------------------------------------------------------------------


def _synthetic_events(seed=0, slope=1.0005, offset=-3700.0):
    rng = np.random.default_rng(seed)
    n = 800
    log_t = 3800.0 + np.cumsum(rng.uniform(0.05, 0.6, n))
    log_code = rng.choice([10, 32, 65, 69, 76, 79, 83], n)
    meg_t = slope * log_t + offset + rng.normal(0, 0.0003, n)
    meg_code = log_code.copy()
    # Remove 5 MEG events (missed triggers) and add 7 extra MEG events (pauses).
    drop = rng.choice(n, 5, replace=False)
    keep = np.setdiff1d(np.arange(n), drop)
    extra_t = rng.uniform(meg_t[0], meg_t[-1], 7)
    meg_t = np.concatenate([meg_t[keep], extra_t])
    meg_code = np.concatenate([meg_code[keep], np.full(7, 30)])
    order = np.argsort(meg_t)
    return log_t, log_code, meg_t[order], meg_code[order], drop


def test_fit_clock_recovers_offset_and_slope():
    slope, offset = 1.0005, -3700.0
    log_t, log_code, meg_t, meg_code, drop = _synthetic_events(slope=slope, offset=offset)
    fit = sb.fit_clock(meg_t, meg_code, log_t, log_code, tol=0.02)
    assert fit.slope == pytest.approx(slope, abs=2e-6)
    assert fit.predict(4000.0) == pytest.approx(slope * 4000.0 + offset, abs=1e-3)
    assert (fit.match >= 0).sum() == len(log_t) - len(drop)
    assert np.all(fit.match[drop] == -1)
    ok = fit.match >= 0
    assert np.all(meg_code[fit.match[ok]] == log_code[ok])
    assert fit.resid_ms_p95 < 1.0


def test_constant_offset_is_not_enough():
    # With the drift, a slope-1 fit is off by more than the 20 ms tolerance.
    log_t, _, _, _, _ = _synthetic_events()
    err = (1.0005 - 1) * (log_t[-1] - log_t[0])
    assert err > 0.02


def test_drop_start_ramp():
    ramp_t = 50 + np.arange(40) * 0.02
    t = np.concatenate([ramp_t, [60, 61, 62]])
    c = np.concatenate([np.arange(1, 41), [10, 65, 32]])
    assert sb.drop_start_ramp(t, c) == 40
    assert sb.drop_start_ramp(t[40:], c[40:]) == 0


def _toy_log():
    keys = [sb.KeyPress(ord(ch.upper()) if ch != " " else 32, ord(ch), ch, 0.0, 0.0) for ch in "la casa"]
    keys.append(sb.KeyPress(13, 13, sb.RETURN, 0.0, 0.0))
    t = 1000.0
    for k in keys:
        t += 0.2
        k.t_trig = t
    words = [sb.Word("la", 995.0), sb.Word("casa", 996.0)]
    return sb.BlockLog([sb.LogTrial(0, "LA CASA  ", True, keys, words)], [990.0], {"word": 10, "block": 20, "pause": 30})


def test_align_block_sample_indices():
    log = _toy_log()
    lt, lc, _ = log.events()
    sfreq, first_samp, slope, off = 1000.0, 12345, 1.0005, -900.0
    meg_s = np.round((slope * lt + off) * sfreq).astype(int) + first_samp
    ramp = np.stack([first_samp + 1000 + np.arange(20) * 20, np.zeros(20, int), np.arange(1, 21)], 1)
    events = np.concatenate([ramp, np.stack([meg_s, np.zeros_like(meg_s), lc], 1)])
    al = sb.align_block(events, first_samp, sfreq, log)
    assert al.qc["n_ramp_dropped"] == 20
    assert al.qc["key_matched_fraction"] == 1.0
    expect = np.round((slope * np.array([k.t_trig for k in log.trials[0].keys]) + off) * sfreq).astype(int)
    np.testing.assert_array_equal(al.key_samples[0], expect)
    assert len(al.word_samples[0]) == 2


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------


def test_key_char():
    assert sb.key_char(108, 76) == "l"
    assert sb.key_char(65, 65) == "a"  # caps lock
    assert sb.key_char(241, 192) == "n"  # ñ
    assert sb.key_char(209, 192) == "n"  # Ñ
    assert sb.key_char(32, 32) == " "
    assert sb.key_char(8, 8) == sb.BACKSPACE
    assert sb.key_char(13, 13) == sb.RETURN
    assert sb.key_char(39, 222) == sb.OTHER  # dead accent key
    assert sb.key_char(59, 186) == sb.OTHER


def test_typed_text_backspace_and_spaces():
    chars = list(" ab") + [sb.BACKSPACE, "c", " ", " ", "d", sb.OTHER, " ", sb.RETURN]
    typed, pos = sb.typed_text_from_keys(chars)
    assert typed == "ac d"
    assert typed == normalize_text(typed)
    assert pos[0] is None  # leading space
    assert pos[1] == 0 and pos[2] is None  # "b" was erased
    assert pos[3] is None  # the backspace itself
    assert pos[4] == 1 and pos[5] == 2 and pos[6] is None  # repeated space
    assert pos[7] == 3 and pos[9] is None and pos[10] is None  # trailing space, return


def test_align_chars_substitution_insertion():
    target = "el procesador ejecuta"
    typed = "el procesadorr ejectua"
    m = sb.align_chars(typed, target)
    assert len(m) == len(typed)
    # Exact prefix maps one to one.
    assert m[:13] == list(range(13))
    # One extra "r" is an insertion.
    assert m.count(None) >= 1
    mapped = [j for j in m if j is not None]
    assert mapped == sorted(mapped)  # monotonic
    assert sb.align_chars("abc", "abc") == [0, 1, 2]
    assert sb.align_chars("axc", "abc") == [0, 1, 2]  # substitution keeps its target


def test_trial_text():
    chars = list("La flexión") + [sb.RETURN]
    chars = [sb.key_char(ord(c), 0) if c not in (sb.RETURN,) else c for c in chars]
    tt = sb.trial_text("LA FLEXION   ", chars)
    assert tt.target_text == "la flexion"
    assert tt.typed_text == "la flexion"
    assert tt.key_target_chars[:10] == list("la flexion")
    assert tt.key_target_chars[-1] is None


# --------------------------------------------------------------------------
# Split rule
# --------------------------------------------------------------------------


def test_assign_split_stable_and_balanced():
    rng = np.random.default_rng(0)
    letters = np.array(list("abcdefghijklmnopqrstuvwxyz "))
    texts = sorted({"".join(rng.choice(letters, 30)) for _ in range(5000)})
    texts = list(dict.fromkeys(normalize_text(t) for t in texts))
    n = len(texts)
    assert n > 4900
    splits = [pp.assign_split(t) for t in texts]
    c = Counter(splits)
    assert abs(c["train"] / n - 0.8) < 0.03
    assert abs(c["val"] / n - 0.1) < 0.02
    assert abs(c["test"] / n - 0.1) < 0.02
    assert [pp.assign_split(t) for t in texts] == splits  # deterministic


def test_assign_split_normalises_text():
    s = "La flexión de la rodilla es mínima"
    assert pp.assign_split(s) == pp.assign_split("LA FLEXION DE LA RODILLA ES MINIMA   ")
    # Fixed values guard against a silent change of the rule (sha1 based).
    import hashlib

    for t in ("hola", "la casa", "el procesador ejecuta la instruccion"):
        b = int(hashlib.sha1(t.encode()).hexdigest()[:8], 16) % 100
        assert pp.assign_split(t) == ("train" if b < 80 else "val" if b < 90 else "test")


# --------------------------------------------------------------------------
# Sidecar schema
# --------------------------------------------------------------------------


def _toy_sidecar():
    log = _toy_log()
    key_s = {0: np.array([1000 + 200 * i for i in range(len(log.trials[0].keys))])}
    segs = pp.build_segments(log, key_s, 1000.0, 100.0, n_times=10_000)
    return {
        "schema": pp.SIDECAR_SCHEMA,
        "subject": "S25",
        "participant": "P25",
        "session": "ses1",
        "block": "block1",
        "source": {},
        "preprocessing": {"version": pp.get_config().version, "config": pp.get_config().to_dict()},
        "qc": {},
        "sfreq": 100.0,
        "n_times": 10_000,
        "segments": segs,
    }


def test_build_segments_and_schema():
    side = _toy_sidecar()
    assert pp.validate_sidecar(side) == []
    seg = side["segments"][0]
    assert seg["start_sample"] == 100 - 40  # first key at 1.0 s, minus 0.4 s
    assert seg["end_sample"] == 100 + 20 * 7 + 50 + 1
    assert seg["key_samples"][0] == 40
    assert seg["target_text"] == "la casa" and seg["typed_text"] == "la casa"
    assert seg["key_target_chars"][-1] is None  # return key
    assert seg["is_training"] is True
    assert seg["split"] == pp.assign_split("la casa")
    json.dumps(side)  # serialisable


def test_validate_sidecar_finds_errors():
    side = _toy_sidecar()
    del side["segments"][0]["split"]
    side.pop("qc")
    errs = pp.validate_sidecar(side)
    assert any("qc" in e for e in errs) and any("split" in e for e in errs)


def test_config_version_changes():
    assert pp.get_config().version == pp.get_config().version
    assert pp.get_config().version != pp.get_config("v1").version
    assert pp.PRESETS["v1"].sfreq_out == 50.0 and pp.PRESETS["v1"].h_freq == 20.0


def test_robust_scale():
    rng = np.random.default_rng(1)
    x = rng.normal(3.0, 2.0, (4, 10_000))
    x[0, :10] = 1e6
    y, med, iqr = pp.robust_scale(x, 5.0)
    assert np.abs(y).max() <= 5.0
    assert np.allclose(np.median(y, axis=1), 0, atol=0.02)


# --------------------------------------------------------------------------
# Optional integration test (needs the local cache)
# --------------------------------------------------------------------------

CACHE = Path(os.environ.get("FIDETYPE_SPANISHBCBL_CACHE", r"C:\Users\zhang\bci-data\cache\spanishbcbl\v1"))


@pytest.mark.skipif(not (CACHE / "S25").is_dir(), reason="SpanishBCBL cache not present")
def test_cached_s25():
    files = sorted((CACHE / "S25").glob("*.npz"))
    files = [f for f in files if f.with_suffix(".json").is_file()]
    if not files:
        pytest.skip("no finished S25 block in the cache")
    blk = pp.load_cached_block(files[0])
    assert blk.data.dtype == np.float16
    assert blk.data.shape[0] == 306 and blk.data.shape[1] == blk.sidecar["n_times"]
    assert blk.ch_pos.shape == (306, 3)
    assert set(blk.ch_types) == {"mag", "grad"}
    assert blk.sfreq == blk.sidecar["sfreq"]
    assert np.isfinite(blk.data).all() and np.abs(blk.data).max() <= 5.0
    assert pp.validate_sidecar(blk.sidecar) == []
    segs = blk.sidecar["segments"]
    assert len(segs) >= 60
    assert sum(s["is_training"] for s in segs) == 2
    assert all(s["target_text"] for s in segs)
    good = [s for s in segs if s["typed_text"] == s["target_text"]]
    assert len(good) > len(segs) / 2
    assert blk.segment(0).shape[1] == segs[0]["end_sample"] - segs[0]["start_sample"]
