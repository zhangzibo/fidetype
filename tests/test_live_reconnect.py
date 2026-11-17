"""P4-11: ``fidetype live --source lsl`` survives a stream loss.

The fake-inlet tests always run (no pylsl): :class:`fidetype.adapters.lsl.ScriptedInlet`
plays the synthetic typist, is lost in the middle of an utterance, and a
new inlet comes back. The last test uses a real pylsl loopback outlet that
is closed and opened again; it skips without pylsl.
"""

from __future__ import annotations

import json
import threading
import time
import uuid

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.adapters import lsl as L
from fidetype.adapters.lsl import LSLStreamInfo, ScriptedInlet
from fidetype.conformance import check_file
from fidetype.live import sources as S
from fidetype.live.__main__ import main as live_main
from fidetype.live.model import load_model, resolve_asset
from fidetype.live.runner import LiveDecoder, make_writer

lsl_only = pytest.mark.skipif(not L.pylsl_available(), reason="pylsl / liblsl not available")

T0 = 1000.0  # LSL clock of sample 0


@pytest.fixture(scope="module")
def model():
    return load_model("builtin:synthetic-keys")


@pytest.fixture(scope="module")
def guard():
    return ft.load(resolve_asset("builtin:synthetic-keys", ".guard.json"))


def _sig_info(srate: float = 250.0, ch: int = 16) -> LSLStreamInfo:
    return LSLStreamInfo("fake-sig", "EMG", ch, srate, "float32", "sid", "u1", "hostA",
                         fidetype={"device.modality": "other"})


def _mk_info() -> LSLStreamInfo:
    return LSLStreamInfo("fake-sig.markers", "Markers", 1, 0.0, "string", "sid.markers", "u2", "hostA")


def _scripts(src: S.SyntheticSource, i0: int, i1: int, step: int = 50) -> tuple[list, list]:
    """Signal and marker scripts for samples [i0, i1) (one marker chunk per signal chunk)."""
    sig, mk = [], []
    marks = sorted(src.markers)
    for a in range(i0, i1, step):
        b = min(i1, a + step)
        ts = (T0 + np.arange(a, b) / src.fs).tolist()
        sig.append((src.x[a:b].tolist(), ts))
        lo, hi = a / src.fs, b / src.fs
        m = [(t, s) for t, s in marks if lo <= t < hi]
        mk.append(([[s] for _, s in m], [T0 + t for t, _ in m]))
    return sig, mk


def _run_with_loss(model, guard, out, cut_s: float, back_s: float, max_reconnects: int = 3, reopen_fail: int = 1):
    """Utterances 0..4; the stream is lost at ``cut_s`` and comes back at ``back_s`` (seconds from sample 0)."""
    src = S.SyntheticSource(5, seed=7, speed=0)
    n = src.x.shape[0]
    i_cut, i_back = int(cut_s * src.fs), int(back_s * src.fs)
    s1, m1 = _scripts(src, 0, i_cut)
    s2, m2 = _scripts(src, i_back, n)
    sig1 = ScriptedInlet(_sig_info(), s1 + ["lost"])
    mk1 = ScriptedInlet(_mk_info(), m1)
    sig2, mk2 = ScriptedInlet(_sig_info(), s2), ScriptedInlet(_mk_info(), m2)
    tries = {"n": 0}

    def reopen():
        tries["n"] += 1
        if tries["n"] <= reopen_fail:
            raise L.LSLResolveError("not visible yet")
        return sig2

    lsrc = S.LSLSource(inlet=sig1, marker_inlet=mk1, reopen=reopen, reopen_markers=lambda: mk2,
                       max_reconnects=max_reconnects, reconnect_timeout=5.0, retry_s=0.01, max_retry_s=0.05)
    w = make_writer(str(out), model, lsrc.info, guard, "lsl")
    dec = LiveDecoder(model, guard, lsrc, writer=w)
    st = dec.run(duration_s=20.0)
    w.close()
    return src, lsrc, dec, st, tries


def test_loss_drops_cut_segment_and_reconnects(tmp_path, model, guard):
    src0 = S.SyntheticSource(5, seed=7, speed=0)
    u = src0.utterances
    # cut inside utterance 1, come back inside utterance 2
    cut = (u[1].key_times[0] + u[1].t_end) / 2
    back = (u[2].key_times[0] + u[2].t_end) / 2
    out = tmp_path / "loss.nts.jsonl"
    src, lsrc, dec, st, tries = _run_with_loss(model, guard, out, cut, back)
    assert lsrc.losses == 1 and lsrc.reconnects == 1 and tries["n"] == 2  # one failed try, then back
    assert st.losses == 1 and st.gaps == 1 and st.dropped_segments == 2  # utterance 1 (cut) and 2 (started in gap)
    # decisions on utterances 0, 3, 4 only; none spans the gap
    t_cut, t_back = T0 + cut, T0 + back
    assert st.decisions == 3
    for d in dec.decisions:
        assert d.t_end < t_cut or d.t_start > t_back, (d.t_start, d.t_end)
    for d, k in zip(dec.decisions, (0, 3, 4)):
        if d.action == "commit":
            assert d.text == src.utterances[k].text
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    gaps = [e for e in evs if e["type"] == "lsl_status"]
    assert len(gaps) == 1 and gaps[0]["status"] == "gap_abort" and gaps[0]["lsl_cause"] == "lost"
    g = gaps[0]
    assert g["t_start"] < t_cut <= g["t_end"] and abs(g["t_end"] - t_back) <= 1 / 250
    assert g["missing_frames"] == int(round((g["t_end"] - g["t_start"]) * 250)) - 1
    assert g["stream"] == "fake-sig"
    # no frame between the gap record and the end of the cut segment; every decision after it is clean
    i = evs.index(g)
    assert all(e["t"] < g["t_end"] for e in evs[:i] if e["type"] == "frame")
    assert not check_file(out).failures("trust-ready")


def test_max_reconnects_zero_ends_the_run(tmp_path, model, guard):
    u = S.SyntheticSource(5, seed=7, speed=0).utterances
    cut = (u[1].key_times[0] + u[1].t_end) / 2
    out = tmp_path / "stop.nts.jsonl"
    _, lsrc, dec, st, tries = _run_with_loss(model, guard, out, cut, cut + 1.0, max_reconnects=0)
    assert tries["n"] == 0 and lsrc.reconnects == 0
    assert "reconnect is off" in st.stop_reason
    assert st.decisions == 1 and st.dropped_segments == 1  # utterance 0 only; no decision on the cut one
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    last = [e for e in evs if e["type"] == "lsl_status"]
    assert last and last[-1]["status"] == "lost"
    assert not check_file(out).failures("trust-ready")


def test_reconnect_timeout_ends_the_run(model, guard):
    src = S.SyntheticSource(2, seed=7, speed=0)
    s1, m1 = _scripts(src, 0, 400)

    def never():
        raise L.LSLResolveError("gone")

    lsrc = S.LSLSource(inlet=ScriptedInlet(_sig_info(), s1 + ["lost"]), marker_inlet=ScriptedInlet(_mk_info(), m1),
                       reopen=never, reconnect_timeout=0.3, retry_s=0.01, max_retry_s=0.05)
    t0 = time.monotonic()
    st = LiveDecoder(model, guard, lsrc).run(duration_s=10.0)
    assert time.monotonic() - t0 < 3.0
    assert "not back within" in st.stop_reason and st.losses == 1


def test_timestamp_jump_is_a_gap(model, guard):
    """A jump of more than 2.5 sample periods inside one chunk is a gap (LSL-G1), with no reconnect."""
    src = S.SyntheticSource(4, seed=7, speed=0)
    u = src.utterances
    i_cut = int((u[1].key_times[0] + u[1].t_end) / 2 * src.fs)
    i_back = int((u[2].key_times[0] + u[2].t_end) / 2 * src.fs)
    s1, m1 = _scripts(src, 0, i_cut)
    s2, m2 = _scripts(src, i_back, src.x.shape[0])
    # glue the last chunk before the cut and the first after it into one chunk
    (xa, ta), (xb, tb) = s1.pop(), s2.pop(0)
    (ma, mta), (mb, mtb) = m1.pop(), m2.pop(0)
    sig = ScriptedInlet(_sig_info(), s1 + [(xa + xb, ta + tb)] + s2)
    mk = ScriptedInlet(_mk_info(), m1 + [(ma + mb, mta + mtb)] + m2)
    lsrc = S.LSLSource(inlet=sig, marker_inlet=mk, max_reconnects=0)
    dec = LiveDecoder(model, guard, lsrc)
    st = dec.run(duration_s=10.0)
    assert lsrc.gaps == 1 and st.gaps == 1 and st.losses == 0
    assert st.decisions == 2  # utterances 0 and 3
    for d in dec.decisions:
        assert d.t_end <= ta[-1] or d.t_start >= tb[0]


def test_backoff_wait_grows_and_caps():
    rc = L._Reconnector(lambda: (_ for _ in ()).throw(RuntimeError("x")), retry_s=0.05, prewarm_tc_s=0.0,
                        give_up_s=0.0, name="t", backoff=2.0, max_retry_s=0.3)
    assert [round(rc.retry_wait(k), 3) for k in (1, 2, 3, 4, 5)] == [0.05, 0.1, 0.2, 0.3, 0.3]
    rc.cancel()
    rc2 = L._Reconnector(lambda: (_ for _ in ()).throw(RuntimeError("x")), retry_s=0.001, prewarm_tc_s=0.0,
                         give_up_s=5.0, name="t", max_tries=3)
    rc2.thread.join(2.0)
    assert rc2.done() and rc2.attempts == 3


# --- real pylsl loopback: the outlet is closed and opened again ---------------------------------


@lsl_only
def test_real_lsl_outlet_restart(tmp_path, capsys):
    """Close a real loopback outlet mid-utterance and open a new one (same source_id): the run goes on."""
    from fidetype.live.replay import make_outlets

    pl = L.require_pylsl()
    src = S.SyntheticSource(6, seed=7)
    u = src.utterances
    name = f"fidetype-test-live-rc-{uuid.uuid4().hex[:8]}"
    sid = f"fidetype-replay-{name}"
    cut = (u[2].key_times[0] + u[2].t_end) / 2
    pause_s = 1.5
    stop = threading.Event()
    sent = {"cut_lsl": None, "back_lsl": None}

    def publish():
        sig, mk = make_outlets(name, src.x.shape[1], src.fs, "other", sid)
        t_wait = time.monotonic() + 20
        while not (sig.have_consumers() and mk.have_consumers()) and time.monotonic() < t_wait:
            time.sleep(0.02)
        marks = sorted(src.markers)
        step, n, i, mi = 5, src.x.shape[0], 0, 0
        base = pl.local_clock()
        w0 = time.monotonic()
        restarted = False
        while i < n and not stop.is_set():
            j = min(n, i + step)
            d = w0 + (j / src.fs) / 2.0 - time.monotonic()  # 2x real time
            if d > 0:
                time.sleep(d)
            if not restarted and j / src.fs >= cut:
                sent["cut_lsl"] = base + i / src.fs
                del sig, mk  # the producer goes away mid-utterance
                time.sleep(pause_s)
                restarted = True
                skip = int(pause_s * 2.0 * src.fs)  # the samples of the pause are never sent
                i = min(n, i + skip)
                while mi < len(marks) and marks[mi][0] < i / src.fs:
                    mi += 1
                sig, mk = make_outlets(name, src.x.shape[1], src.fs, "other", sid)
                t_wait = time.monotonic() + 15
                while not (sig.have_consumers() and mk.have_consumers()) and time.monotonic() < t_wait:
                    time.sleep(0.02)
                w0 = time.monotonic() - (i / src.fs) / 2.0
                sent["back_lsl"] = base + i / src.fs
                continue
            sig.push_chunk(src.x[i:j], (base + np.arange(i, j) / src.fs).tolist())
            while mi < len(marks) and marks[mi][0] < j / src.fs:
                mk.push_sample([marks[mi][1]], base + marks[mi][0])
                mi += 1
            i = j
        time.sleep(0.5)
        del sig, mk

    th = threading.Thread(target=publish, daemon=True)
    th.start()
    out, summ = tmp_path / "rc.nts.jsonl", tmp_path / "rc.json"
    try:
        rc = live_main(["--source", "lsl", "--stream-name", name, "--duration", "60", "--json", "--out", str(out),
                        "--summary", str(summ), "--reconnect-timeout", "6", "--max-reconnects", "2"])
    finally:
        stop.set()
        th.join(30)
    assert rc == 0
    s = json.loads(summ.read_text())
    # loss 1: the restart (reconnected); loss 2: the producer ends for good (the run stops after 6 s)
    assert s["losses"] == 2 and s["gaps"] == 1, s
    assert "not back within" in s["stop_reason"]
    assert s["dropped_segments"] >= 1
    assert 2 <= s["decisions"] <= 5, s  # some utterances before the loss and some after it
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    g = [e for e in evs if e["type"] == "lsl_status"]
    assert [e["status"] for e in g] == ["gap_abort", "lost"]
    hyps = [e for e in evs if e["type"] == "hypothesis"]
    for h in hyps:  # no decision spans the gap
        assert h["t_end"] < g[0]["t_start"] + 1e-6 or h["t_start"] > g[0]["t_end"] - 1e-6, (h, g[0])
    assert not check_file(out).failures("trust-ready")
