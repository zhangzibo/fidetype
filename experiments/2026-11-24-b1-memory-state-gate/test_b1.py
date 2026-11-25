"""CPU tests of the B1 code on tiny synthetic data (no iEEG). Run: python -m pytest <this folder>."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import b1data as D  # noqa: E402
import b1feat as FT  # noqa: E402
import b1gate as G  # noqa: E402
import b1run as R  # noqa: E402

# ------------------------------------------------------------------------------------- EDF writer


def write_edf(path: Path, data: np.ndarray, fs: int, labels: list[str], pmin=-1000.0, pmax=1000.0,
              annotations: bool = True) -> None:
    """Minimal EDF+C writer: 1 s records, int16, optional 'EDF Annotations' signal (spr 8)."""
    nc, n = data.shape
    nrec = n // fs
    data = data[:, :nrec * fs]
    labs = list(labels) + (["EDF Annotations"] if annotations else [])
    ns = len(labs)
    spr = [fs] * nc + ([8] if annotations else [])

    def f(x, w):
        s = str(x)[:w]
        return s.ljust(w).encode("ascii")

    h = b"".join([f("0", 8), f("X X X SECRET-NAME", 80), f("Startdate X SECRET-REC", 80), f("01.01.01", 8),
                  f("00.00.00", 8), f(256 * (ns + 1), 8), f("EDF+C", 44), f(nrec, 8), f(1, 8), f(ns, 4)])
    pm = [pmin] * nc + ([-1] if annotations else [])
    px = [pmax] * nc + ([1] if annotations else [])
    cols = [[f(l, 16) for l in labs], [f("", 80)] * ns, [f("uV", 8)] * ns, [f(v, 8) for v in pm],
            [f(v, 8) for v in px], [f(-32768, 8)] * ns, [f(32767, 8)] * ns, [f("", 80)] * ns,
            [f(s, 8) for s in spr], [f("", 32)] * ns]
    h += b"".join(b"".join(c) for c in cols)
    gain = (pmax - pmin) / 65535.0
    dig = np.clip(np.round((data - pmin) / gain - 32768), -32768, 32767).astype("<i2")
    with path.open("wb") as fh:
        fh.write(h)
        for r in range(nrec):
            for c in range(nc):
                fh.write(dig[c, r * fs:(r + 1) * fs].tobytes())
            if annotations:
                fh.write(np.zeros(8, dtype="<i2").tobytes())


def test_edf_reader_roundtrip(tmp_path):
    fs = 100
    rng = np.random.default_rng(0)
    x = rng.uniform(-500, 500, size=(3, 5 * fs))
    p = tmp_path / "a.edf"
    write_edf(p, x, fs, ["A1-A2", "A2-A3", "B1-B2"])
    h = D.read_edf_header(p)
    assert h.data_labels == ["A1-A2", "A2-A3", "B1-B2"] and h.fs == 100 and h.n_samples == 500
    assert not hasattr(h, "patient") and "SECRET" not in repr(h)
    rd = D.EdfReader(p)
    seg = rd.segment(150, 333)
    assert seg.shape == (3, 183)
    assert np.allclose(seg, x[:, 150:333], atol=0.02)
    cm = rd.to_channel_major(tmp_path / "cm.i16")
    full = R.CMReader(cm, rd.gain, rd.offset)
    assert np.allclose(full.channel(1), x[1], atol=0.02)
    assert np.allclose(full.segment(150, 333), seg)
    del cm, full
    rd.close()
    with pytest.raises(IndexError):
        D.EdfReader(p).segment(-1, 10)


def test_edf_bad_size(tmp_path):
    p = tmp_path / "a.edf"
    write_edf(p, np.zeros((2, 300)), 100, ["a", "b"])
    with p.open("ab") as fh:
        fh.write(b"\0\0")
    with pytest.raises(ValueError):
        D.read_edf_header(p)


# ------------------------------------------------------------------------------------------ labels


def _ev(tt, item="n/a", lst=-999, sp=-999, sample=-1, onset=0.0):
    return {"trial_type": tt, "item_name": item, "list": str(lst), "serialpos": str(sp), "sample": str(sample),
            "onset": str(onset)}


def test_labels_rule():
    rows = [_ev("PRACTICE_WORD", "cat", 0, 1), _ev("WORD", "Dog ", 1, 1, 10), _ev("WORD", "SUN", 1, 2, 20),
            _ev("WORD", "tree", 1, 3, 30), _ev("REC_START", lst=1), _ev("REC_WORD", "dog", 1),
            _ev("REC_WORD", "DOG", 1), _ev("REC_WORD", "car", 1), _ev("REC_WORD_VV", "tree", 1),
            _ev("WORD", "sun", 2, 1, 40), _ev("REC_WORD", "SUN", 2),     # list 2 has no REC_START -> dropped
            _ev("WORD", "moon", 3, 1, 50), _ev("REC_START", lst=3), _ev("REC_WORD", "sun", 3)]
    w, cnt = D.words_from_events(rows)
    assert w.items == ["DOG", "SUN", "TREE", "MOON"]
    assert w.recalled.tolist() == [1, 0, 0, 0]                    # other-list recall and VV do not count
    assert w.sample.tolist() == [10, 20, 30, 50]
    assert cnt["n_dropped_no_rec_start"] == 1 and cnt["n_word_events"] == 5


def test_cal_split_deterministic():
    o1, c1 = D.cal_list_split("sub-X", 2, list(range(1, 26)))
    o2, c2 = D.cal_list_split("sub-X", 2, list(range(25, 0, -1)))
    assert o1 == o2 and c1 == c2 and len(o1) == 8 and len(c1) == 17 and not set(o1) & set(c1)
    o3, _ = D.cal_list_split("sub-Y", 2, list(range(1, 26)))
    assert o3 != o1
    assert D.cal_list_split("sub-X", 2, [1, 2]) == ([], [1, 2])


def test_a0_detects_erp():
    fs = 200
    rng = np.random.default_rng(1)
    x = rng.standard_normal((4, 200 * fs))
    idx = np.arange(5 * fs, 190 * fs, 3 * fs)
    for i in idx:
        x[:, i + 20:i + 80] += 1.5
    rd = R.CMReader(np.round(x * 1000).astype(np.int16), np.full(4, 1e-3), np.zeros(4))
    sw = D.a0_statistic(rd, idx, fs)
    sr = D.a0_statistic(rd, D.a0_random_times(idx, fs, 300, [1, 0, 0]), fs)
    assert sw > 3 * sr
    assert math.isnan(D.a0_statistic(rd, np.array([-5]), fs))


# ---------------------------------------------------------------------------------------- features


def test_morlet_peak_and_buffer_equivalence():
    fs = 500.0
    t = np.arange(int(8 * fs)) / fs
    f0 = FT.FREQS[5]
    x = np.sin(2 * np.pi * f0 * t)
    bank = FT.morlet_bank(fs)
    pre, post = int(FT.SEG_PRE_S * fs), int(FT.SEG_POST_S * fs)
    win, b = int(round(FT.WIN_S * fs)), int(FT.BUF_S * fs)
    i = int(3 * fs)
    seg = x[None, i - pre:i + post]
    main, _ = FT.window_logpower(seg, fs, [(pre, win), (pre - b, b)], bank)
    assert int(np.argmax(main[0])) == 5
    # broadband signal: the window values on the long segment equal those on the 3.366 s epoch
    xn = np.random.default_rng(9).standard_normal(t.size)
    seg = xn[None, i - pre:i + post]
    m2, _ = FT.window_logpower(seg, fs, [(pre, win), (pre - b, b)], bank)
    ep = xn[None, i - b:i + win + b]
    alt = FT.window_logpower(ep, fs, [(b, win)], bank)[0]
    assert np.allclose(m2, alt, atol=1e-3)


def test_line_filter_removes_60hz():
    fs = 1000.0
    t = np.arange(int(10 * fs)) / fs
    x = np.sin(2 * np.pi * 60 * t) + np.sin(2 * np.pi * 10 * t)
    y = FT.line_filter(x, fs)
    mid = slice(2000, 8000)
    assert np.std(y[mid] - np.sin(2 * np.pi * 10 * t[mid])) < 0.05


def test_nulls_keep_power_spectrum():
    rng = np.random.default_rng(2)
    ep = rng.standard_normal((5, 400)) * np.linspace(1, 3, 400)
    ph = FT.common_phases(5, 400, [1, 7, 3])
    r = FT.phase_randomise(ep, ph)
    assert np.allclose(np.abs(np.fft.rfft(r)), np.abs(np.fft.rfft(ep)), atol=1e-8)
    assert not np.allclose(r, ep)
    Z = FT.common_gaussian(5, 400, [1, 7, 4])
    nz = FT.mean_spectrum_noise(ep, Z)
    assert nz.shape == ep.shape and np.isrealobj(nz)
    rev = FT.time_reverse(ep)
    assert np.allclose(rev[:, ::-1], ep)


def test_channel_features_shapes():
    fs = 500.0
    rng = np.random.default_rng(3)
    x = rng.standard_normal(int(60 * fs))
    idx = np.array([int(5 * fs), int(20 * fs), int(40 * fs)])
    L = FT.epoch_len(fs)
    nulls = {"phases": FT.common_phases(3, L, [1, 7, 3]), "Z": FT.common_gaussian(3, L, [1, 7, 4])}
    out = FT.channel_features(x, fs, idx, nulls)
    assert set(out) == {"main", "p0", "n2", "n3a", "n3b"}
    assert all(v.shape == (3, 8) and np.all(np.isfinite(v)) for v in out.values())
    # time-averaged power is nearly invariant under time reversal (an invariance check, not a null)
    assert np.max(np.abs(out["n2"] - out["main"])) < 0.5
    assert FT.valid_word_mask(np.array([10, int(30 * fs), int(59 * fs)]), fs, len(x)).tolist() == [False, True, False]


def test_zscore_flat_channel_nan():
    F = np.column_stack([np.arange(5.0), np.ones(5)])
    z = FT.zscore_session(F)
    assert np.allclose(z[:, 0].mean(), 0) and np.all(np.isnan(z[:, 1]))


# ------------------------------------------------------------------------------------ decoder, gate


def test_logreg_gradient_and_fit():
    rng = np.random.default_rng(4)
    X = rng.standard_normal((300, 5))
    y = (X[:, 0] + 0.5 * rng.standard_normal(300) > 0.8).astype(int)
    m = G.fit_logreg(X, y, C=1.0)
    assert G.auc(m.logit(X), y) > 0.9
    m2 = G.fit_logreg(X, y)                      # C = 2.4e-4: tiny weights, ranking kept
    assert np.max(np.abs(m2.w)) < 0.05 and G.auc(m2.logit(X), y) > 0.9
    # optimality: gradient of the objective ~ 0
    cw = G.class_weights(y)
    s = 2 * y - 1
    z = X @ m.w + m.b
    g = -s * (1 / (1 + np.exp(s * z))) * cw
    assert np.max(np.abs(m.w + 1.0 * X.T @ g)) < 1e-4 and abs(g.sum()) < 1e-4
    with pytest.raises(ValueError):
        G.class_weights(np.zeros(4))


def test_platt_recovers():
    rng = np.random.default_rng(5)
    s = rng.standard_normal(20000) * 0.01
    p = 1 / (1 + np.exp(-(150 * s - 1)))
    y = (rng.uniform(size=s.size) < p).astype(int)
    pl = G.fit_platt(s, y)
    assert abs(pl.a - 150) < 10 and abs(pl.b + 1) < 0.1


def test_auc_basic():
    assert G.auc(np.array([1, 2, 3, 4.0]), np.array([0, 0, 1, 1])) == 1.0
    assert G.auc(np.array([1, 1, 1, 1.0]), np.array([0, 1, 0, 1])) == 0.5
    assert math.isnan(G.auc(np.array([1.0, 2]), np.array([1, 1])))


def test_gate_certifies_signal_not_noise():
    rng = np.random.default_rng(6)
    n = 3000
    p = rng.uniform(0, 1, n)
    y = (rng.uniform(size=n) < p).astype(int)           # calibrated: P(recall | p) = p
    g = G.fit_gate(p[:1000], y[:1000] == 0, p[1000:], y[1000:] == 0, target=0.6)
    assert g["lambda"] is not None
    pf = rng.uniform(0, 1, 20000)
    yf = (rng.uniform(size=pf.size) < pf).astype(int)
    fl = G.flags(pf, g["lambda"])
    assert yf[fl].mean() >= 0.58                         # precision on fresh data near the target
    cnt = 0
    for k in range(20):
        r = np.random.default_rng([k, 2026])
        pn = r.uniform(0.2, 0.4, n)
        yn = (r.uniform(size=n) < 0.3).astype(int)       # no signal; base 0.3, target 0.4
        cnt += G.fit_gate(pn[:1000], yn[:1000] == 0, pn[1000:], yn[1000:] == 0, target=0.4)["certified_any"]
    assert cnt <= 4
    assert G.flags(np.array([0.1, 0.9]), None).tolist() == [False, False]


def test_offer_conformal():
    p = np.array([0.9, 0.8, 0.2, 0.1, 0.5])
    y = np.array([1, 1, 0, 0, 1])
    q = G.fit_offer(p, y, alpha=0.5)
    inr, inf = G.offer_sets(p, q)
    assert inr.dtype == bool and inf.dtype == bool and np.all(inr | inf | (q < 0.5))


def test_gate_metrics_counts_and_bootstrap():
    f = [np.array([1, 1, 0, 0], bool), np.array([0, 0, 0, 1], bool)]
    y = [np.array([1, 0, 1, 0]), np.array([0, 0, 1, 1])]
    m = G.gate_metrics(f, y, wrong_when=0, n_boot=500)
    assert m["flags"] == 3 and m["wrong"] == 1 and m["words"] == 8
    assert m["base_rate"] == 0.5 and abs(m["precision"] - 2 / 3) < 1e-12
    assert m["boot"]["flag_rate"][0] <= m["flag_rate"] <= m["boot"]["flag_rate"][1]
    assert m["flag_rate_cp_upper95"] > m["flag_rate"] > m["flag_rate_cp_lower95"]
    z = G.gate_metrics([np.zeros(4, bool)], [np.array([1, 0, 1, 0])], 0, 100)
    assert z["flags"] == 0 and z["wrong_rate"] is None and z["boot"]["wrong_rate"] == [None, None]


def _fake_summary(flags=100, wrong=40, words=1000, rate_n3=0.05, n1=2, auc=0.6, p=1e-4, lo=0.02):
    gp = {"flags": flags, "wrong_rate": wrong / flags if flags else None, "flag_rate": flags / words,
          "boot": {"wrong_rate": [0.3, 0.5], "precision_minus_base": [lo, 0.2]}}
    n3 = {"flag_rate": rate_n3, "flag_rate_cp_upper95": rate_n3 + 0.02, "boot": {"flag_rate": [0, rate_n3 + 0.03]}}
    n4 = {"flags": 10, "precision": 0.3, "base_rate": 0.3}
    return {"neural": {"g_plus": gp, "auc": {"mean": auc, "p_two_sided": p}}, "n3b": {"g_plus": n3},
            "n4": {"g_plus": n4}, "n1": {"n_g_plus_certified": n1},
            "b0": {"g_plus": {"flags": 5}, "gate": {"lambda_plus": None}}}


def test_rules_outcomes():
    gate = {"alpha": 0.1, "a0": {"pass": True}, "gates": {"neural": {"tau_plus": 0.4}}}
    assert R.evaluate_rules(_fake_summary(), gate)[1] == "A"
    assert R.evaluate_rules(_fake_summary(lo=-0.01), gate)[1] == "B"
    assert R.evaluate_rules(_fake_summary(flags=0, wrong=0), gate)[1] == "B"
    assert R.evaluate_rules(_fake_summary(n1=5), gate)[1] == "C"
    assert R.evaluate_rules(_fake_summary(wrong=70), gate)[1] == "C"
    assert R.evaluate_rules(_fake_summary(rate_n3=0.15), gate)[1] == "C"
    assert R.evaluate_rules(_fake_summary(auc=0.54), gate)[1] == "N"
    assert R.evaluate_rules(_fake_summary(), {**gate, "a0": {"pass": False}})[1] == "N"


# ------------------------------------------------------------------------------------- end to end


def _make_dataset(root: Path, n_sub=3, n_ses=3, fs=500, n_lists=6, seed=0) -> None:
    rng = np.random.default_rng(seed)
    files = root / "files"
    order = []
    for si in range(n_sub):
        subj = f"sub-T{si:03d}"
        order.append({"subject": subj, "sessions": list(range(n_ses))})
        for ses in range(n_ses):
            d = files / subj / f"ses-{ses}" / "ieeg"
            d.mkdir(parents=True)
            n_words = n_lists * 12
            dur = int((10 + n_words * 3 + n_lists * 10 + 10) * fs)
            x = rng.standard_normal((4, dur)) * 20
            rows = []
            t = 10 * fs
            for li in range(1, n_lists + 1):
                rec = []
                for sp in range(1, 13):
                    item = f"W{li}_{sp}"
                    good = rng.uniform() < 0.35
                    if good:     # a 70 Hz burst on channels 0-1 during encoding -> later recalled
                        tt = np.arange(int(1.2 * fs)) / fs
                        x[:2, t:t + tt.size] += 40 * np.sin(2 * np.pi * 70 * tt)
                        rec.append(item)
                    rows.append({"onset": t / fs + 1000, "sample": t, "trial_type": "WORD", "item_name": item,
                                 "serialpos": sp, "list": li})
                    t += 3 * fs
                rows.append({"onset": t / fs + 1000, "sample": t, "trial_type": "REC_START", "item_name": "n/a",
                             "serialpos": -999, "list": li})
                for item in rec:
                    rows.append({"onset": t / fs + 1000, "sample": t, "trial_type": "REC_WORD", "item_name": item.lower(),
                                 "serialpos": -999, "list": li})
                t += 10 * fs
            base = f"{subj}_ses-{ses}_task-FR1"
            write_edf(d / f"{base}_acq-bipolar_ieeg.edf", x, fs, ["A1-A2", "A2-A3", "B1-B2", "B2-B3"])
            (d / f"{base}_acq-bipolar_ieeg.edf.ok").write_text("ok")
            cols = ["onset", "duration", "sample", "trial_type", "item_name", "serialpos", "list"]
            lines = ["\t".join(cols)] + ["\t".join(str(r.get(c, "n/a")) for c in cols) for r in rows]
            (d / f"{base}_events.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "selection.json").write_text(json.dumps({"order": order}), encoding="utf-8")


def test_end_to_end_synthetic(tmp_path, monkeypatch, capsys):
    raw, out = tmp_path / "raw", tmp_path / "out"
    _make_dataset(raw)
    ctx = R.Ctx(raw, out, tmp_path / "res", 3, 1, 200)
    subj = R.stage_parse(ctx)
    assert [c["rank"] for c in subj["subjects"]] == [1, 2, 3]
    assert R.stage_feat(ctx, subj)
    assert len(list((out / "feat").glob("r*.npz"))) == 9
    assert not list((out / "tmp").iterdir())
    gate = R.stage_fit(ctx, subj)
    assert gate["a0"]["pass"] in (True, False) and gate["index_mode"] in ("sample", "onset")
    g = gate["gates"]["neural"]
    assert 0 < g["b_order"] < 1 and abs(g["tau_plus"] - g["b_order"] - 0.10) < 1e-12
    s = R.stage_test(ctx, subj, gate)
    assert s["outcome"] in "ABCN"
    assert s["neural"]["auc"]["mean"] > 0.6           # the injected burst is decodable
    assert len(s["n1"]["runs"]) == 20
    assert set(s["rules"]) >= {"A0", "V1", "i", "ii", "iii", "iv"}
    text = json.dumps(s)
    assert "sub-T" not in text and "sub-T" not in json.dumps(gate)
    for name in ("gate.json", "summary.json"):
        assert "sub-T" not in (tmp_path / "res" / name).read_text(encoding="utf-8")
    import b1report
    monkeypatch.setattr(sys, "argv", ["b1report.py", str(tmp_path / "res")])
    assert b1report.main() == 0 and "Outcome" in capsys.readouterr().out


def test_split_cal_few_lists():
    sd = {"subject": "sub-X", "sessions": [{}, {"session": 1, "lst": np.array([1, 1, 2, 2])}, {}]}
    o, c = R.split_cal(sd)
    assert o.all() and not c.any()
    sd["sessions"][1]["lst"] = np.repeat(np.arange(1, 7), 2)
    o, c = R.split_cal(sd)
    assert o.sum() == 4 and c.sum() == 8 and not (o & c).any()


def test_parse_replaces_subject(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "out"
    _make_dataset(raw, n_sub=3, n_lists=2)
    ev = raw / "files" / "sub-T000" / "ses-1" / "ieeg" / "sub-T000_ses-1_task-FR1_events.tsv"
    ev.write_text("onset\tsample\ttrial_type\n1\t1\tSESS_START\n", encoding="utf-8")   # no WORD events
    subj = R.stage_parse(R.Ctx(raw, out, None, 2, 1, 100))
    assert [c["subject"] for c in subj["subjects"]] == ["sub-T001", "sub-T002"]
    assert any("no WORD" in d.get("reason", "") for d in subj["drops"])
