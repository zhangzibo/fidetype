"""CPU tests of the A1 code on tiny synthetic data (no EEG, no GPU). Run: python -m pytest <this folder>."""

from __future__ import annotations

import json
import math
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import a1data as D  # noqa: E402
import a1gate as G  # noqa: E402


# --- safe loading --------------------------------------------------------------------------------------------------

class _Evil:
    def __reduce__(self):
        return (os.system, ("echo pwned",))


def test_safe_unpickler_blocks_globals(tmp_path):
    p = tmp_path / "evil.npy"
    p.write_bytes(pickle.dumps({"x": _Evil()}, protocol=4))
    with pytest.raises(pickle.UnpicklingError):
        D.safe_load(p)
    with pytest.raises(pickle.UnpicklingError):
        D.lazy_load(p)


@pytest.mark.parametrize("big", [1000, 1 << 24])
def test_lazy_convert_streams_big_payload(tmp_path, big):
    rng = np.random.default_rng(10)
    x = rng.normal(size=(40, 4, 3, 50))  # 192 kB float64: above big=1000 -> skipped and memory-mapped
    t = np.linspace(0, 1, 50)
    src = tmp_path / "raw.npy"
    with open(src, "wb") as f:
        pickle.dump({"preprocessed_eeg_data": x, "ch_names": ["a", "b", "c"], "times": t}, f, protocol=4)
    d = D.lazy_load(src, big)
    assert (d["preprocessed_eeg_data"].offset is not None) == (big == 1000)
    assert np.array_equal(np.asarray(d["preprocessed_eeg_data"].array(src)), x)
    meta = D.convert_eeg(src, tmp_path / "o", "test", (40, 4, 3, 50), big=big)
    y = np.load(tmp_path / "o" / "test.npy", allow_pickle=False)
    assert y.dtype == np.float32 and np.allclose(y, x, atol=1e-6)
    assert np.allclose(meta["times"], t) and meta["src_dtype"] == "float64"
    xf = np.asfortranarray(x)
    with open(src, "wb") as f:
        pickle.dump({"preprocessed_eeg_data": xf, "ch_names": ["a"], "times": t}, f, protocol=4)
    D.convert_eeg(src, tmp_path / "f", "test", None, big=big)
    assert np.allclose(np.load(tmp_path / "f" / "test.npy"), x, atol=1e-6)


def test_safe_load_and_convert(tmp_path):
    x = np.random.default_rng(0).normal(size=(5, 4, 3, 7))
    src = tmp_path / "raw.npy"
    with open(src, "wb") as f:
        pickle.dump({"preprocessed_eeg_data": x, "ch_names": ["a", "b", "c"], "times": np.arange(7) / 250}, f,
                    protocol=4)
    obj = np.empty((), dtype=object)
    obj[()] = {"k": [1, 2]}
    np.save(tmp_path / "meta.npy", obj, allow_pickle=True)
    assert D.safe_load(tmp_path / "meta.npy") == {"k": [1, 2]}
    meta = D.convert_eeg(src, tmp_path / "out", "train", (5, 4, 3, 7))
    y = np.load(tmp_path / "out" / "train.npy", allow_pickle=False)
    assert y.dtype == np.float32 and np.allclose(y, x, atol=1e-6)
    assert meta["ch_names"] == ["a", "b", "c"] and len(meta["times"]) == 7
    with pytest.raises(ValueError):
        D.convert_eeg(src, tmp_path / "out2", "train", (5, 4, 3, 8))


# --- splits, units, sessions, galleries ----------------------------------------------------------------------------

def _concepts(n_concepts=600, per=10):
    return [f"{i:05d}_c{i}" for i in range(n_concepts) for _ in range(per)]


def test_split_sizes_disjoint_deterministic():
    tr = _concepts()
    s1 = D.make_split(tr, ["t1", "t2"])
    s2 = D.make_split(list(reversed(tr)))
    assert s1 == s2
    assert len(s1.val) == D.N_VAL and len(s1.cal) == D.N_CAL and len(s1.fit) == 600 - D.N_VAL - D.N_CAL
    assert not (set(s1.val) & set(s1.cal)) and not (set(s1.cal) & set(s1.fit))
    assert len(s1.order) == D.N_ORDER and len(s1.certify) == D.N_CAL - D.N_ORDER
    with pytest.raises(ValueError):
        D.make_split(tr, [tr[0]])


def test_units():
    eeg = np.random.default_rng(1).normal(size=(3, 80, 2, 5)).astype(np.float32)
    u, img = D.test_units(eeg)
    assert u.shape == (60, 2, 5) and list(img[:21]) == [0] * 20 + [1]
    assert np.allclose(u[1], eeg[0, 4:8].mean(axis=0), atol=1e-6)
    tr = np.random.default_rng(2).normal(size=(6, 4, 2, 5)).astype(np.float32)
    t = D.train_units(tr, np.array([5, 1]))
    assert np.allclose(t[0], tr[5].mean(axis=0), atol=1e-6)


def test_session_reconstruction():
    ses = D.session_of_file_rep()
    assert np.bincount(ses).tolist() == [20, 20, 20, 20]
    # same as sklearn.utils.shuffle(arange(80), random_state=seed) (RandomState.shuffle of arange)
    a = np.arange(80)
    np.random.RandomState(D.PREP_SEED).shuffle(a)
    assert np.array_equal(ses, a // 20)
    eeg = np.random.default_rng(3).normal(size=(12, 80, 3, 20)).astype(np.float32)
    early, im = D.session_units(eeg, (0, 1), ses_of_rep=ses)
    assert early.shape == (12 * 10, 3, 20) and np.all(np.bincount(im) == 10)
    reps = np.nonzero(np.isin(ses, [0, 1]))[0][:4]
    assert np.allclose(early[0], eeg[0, reps].mean(axis=0), atol=1e-5)


def test_s0_detects_session_structure():
    rng = np.random.default_rng(4)
    ses = D.session_of_file_rep()
    n_img = 15
    off = rng.normal(size=(4, 3, 20)) * 1.0
    eeg = rng.normal(size=(n_img, 80, 3, 20)) + off[ses][None]
    assert D.s0_session_check(eeg, ses)["pass"]
    assert not D.s0_session_check(rng.normal(size=(n_img, 80, 3, 20)), ses)["pass"]


def test_galleries():
    concepts = _concepts(300, 10)
    cid = D.concept_ids(concepts)
    pool = np.arange(len(concepts))
    units = np.array([0, 15, 2999])
    g = D.make_galleries(units, cid, pool, subject=1)
    assert g.shape == (3, 200) and list(g[:, 0]) == list(units)
    for r in g:
        cs = cid[r]
        assert len(set(cs.tolist())) == 200
    assert np.array_equal(g, D.make_galleries(units, cid, pool, subject=1))
    with pytest.raises(ValueError):
        D.make_galleries(units, cid, pool[:1000], subject=1)  # only 100 concepts


# --- nulls ---------------------------------------------------------------------------------------------------------

def test_nulls():
    rng = np.random.default_rng(5)
    u = rng.normal(size=(30, 4, 64)).astype(np.float32)
    n = G.make_nulls(u, subject=1)
    assert np.array_equal(n["N2"][0, 0], u[0, 0, ::-1])
    a0 = np.abs(np.fft.rfft(u, axis=-1))
    a3 = np.abs(np.fft.rfft(n["N3"], axis=-1))
    assert np.allclose(a0, a3, rtol=1e-3, atol=1e-3)
    assert not np.allclose(u, n["N3"], atol=1e-2)
    # cross-channel covariance kept by N3 (same phases on all channels)
    c0 = np.einsum("nct,ndt->ncd", u - u.mean(-1, keepdims=True), u - u.mean(-1, keepdims=True))
    x3 = n["N3"] - n["N3"].mean(-1, keepdims=True)
    c3 = np.einsum("nct,ndt->ncd", x3, x3)
    assert np.allclose(c0, c3, rtol=1e-2, atol=1e-2)
    # N1: every channel comes from some unit, channel index kept
    for c in range(4):
        assert all(any(np.array_equal(n["N1"][i, c], u[j, c]) for j in range(30)) for i in range(5))


# --- gate ----------------------------------------------------------------------------------------------------------

def _synthetic_sims(n, rng, strength):
    """[n, 200] cosines; column 0 true; per-unit signal strength from an 'easiness' draw."""
    s = rng.normal(0, 0.05, size=(n, 200))
    easy = rng.uniform(0, 1, size=n) ** 3
    s[:, 0] += strength * easy
    return s


def test_gate_precision_holds_on_new_data():
    rng = np.random.default_rng(6)
    T = G.fit_temperature(_synthetic_sims(2000, rng, 0.4), np.zeros(2000, dtype=int))
    gate = G.fit_gate(_synthetic_sims(1000, rng, 0.4), np.zeros(1000, dtype=int),
                      _synthetic_sims(2000, rng, 0.4), np.zeros(2000, dtype=int), T)
    assert gate.commit_p is not None and gate.ltt["feasible"]
    test = _synthetic_sims(4000, rng, 0.4)
    perm = np.argsort(rng.uniform(size=(4000, 200)), axis=1)  # move the true column around
    sim = np.take_along_axis(test, perm, axis=1)
    true = np.argmax(perm == 0, axis=1)
    dec = gate.decide(sim)
    m = G.gate_metrics(dec, true, np.arange(4000) // 20, n_boot=300)
    assert m["commits"] > 100
    assert m["wrong_rate_precision"] <= G.ALPHA + 0.03
    assert abs(m["coverage"] - (1 - G.ALPHA)) < 0.04
    # flat (null) similarities: no commits, big sets
    null = gate.decide(rng.normal(0, 0.05, size=(4000, 200)))
    mn = G.gate_metrics(null, None, np.arange(4000) // 20, n_boot=300)
    # precision LTT allows some null commits (as no-signal real units commit); rule (i) still holds
    assert mn["commit_rate"] < G.ALPHA and G.rule_null(mn)
    st = G.set_size_test(dec["set_size"], null["set_size"], np.arange(4000) // 20)
    assert st["p_one_sided"] < 0.01


def test_gate_never_commits_without_signal():
    rng = np.random.default_rng(7)
    z = lambda n: np.zeros(n, dtype=int)  # noqa: E731
    gate = G.fit_gate(_synthetic_sims(1000, rng, 0.0), z(1000), _synthetic_sims(2000, rng, 0.0), z(2000), 0.05)
    assert gate.commit_p is None
    dec = gate.decide(_synthetic_sims(100, rng, 0.0))
    assert not np.any(dec["action"] == G.COMMIT)
    m = G.gate_metrics(dec, z(100), np.arange(100), n_boot=50)
    assert G.rule_error(m) and not G.rule_commits(m)


def test_gate_roundtrip():
    g = G.Gate(0.03, None, math.inf, ltt={"a": 1}, n_cal=5)
    g2 = G.Gate.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g2 == g


def test_cluster_boot_upper():
    rng = np.random.default_rng(8)
    cl = np.repeat(np.arange(200), 20)
    num = (rng.uniform(size=4000) < 0.1).astype(float)
    up = G.cluster_boot_upper(num, np.ones(4000), cl, n_boot=500)
    assert 0.1 < up < 0.12
    # strong cluster effect widens the bound
    num2 = np.repeat((rng.uniform(size=200) < 0.1).astype(float), 20)
    assert G.cluster_boot_upper(num2, np.ones(4000), cl, n_boot=500) > up


def _m(commits, wrong, units=4000, ub=None):
    from fidetype.utils.binomial import cp_upper

    return {"units": units, "commits": commits, "wrong_commits": wrong, "commit_rate": commits / units,
            "commit_rate_cp95_upper": cp_upper(commits, units, 0.05), "commit_rate_boot95_upper": commits / units,
            "wrong_rate_precision": wrong / commits if commits else 0.0,
            "wrong_rate_precision_cp95_upper": cp_upper(wrong, commits, 0.05),
            "wrong_rate_precision_boot95_upper": ub if ub is not None else (wrong / commits if commits else 1.0),
            "coverage": 0.9}


def test_verdicts_and_outcomes():
    null_ok = {k: _m(10, 10) for k in ("N1", "N2", "N3")}
    sets_ok = {"p_one_sided": 0.001}
    assert G.subject_verdict(0.2, _m(400, 20), null_ok, sets_ok)["outcome"] == "A"
    assert G.subject_verdict(0.05, _m(400, 20), null_ok, sets_ok)["outcome"] == "N"
    assert G.subject_verdict(0.2, _m(400, 80), null_ok, sets_ok)["outcome"] == "C"
    assert G.subject_verdict(0.2, _m(100, 2), null_ok, sets_ok)["outcome"] == "B"
    assert G.subject_verdict(0.2, _m(0, 0), null_ok, sets_ok)["outcome"] == "B"
    bad_null = dict(null_ok, N2=_m(600, 600))
    assert G.subject_verdict(0.2, _m(400, 20), bad_null, sets_ok)["outcome"] == "C"
    assert G.subject_verdict(0.2, _m(400, 20), null_ok, {"p_one_sided": 0.2})["outcome"] == "D"
    # cluster bound too wide -> C
    assert G.subject_verdict(0.2, _m(400, 20, ub=0.25), null_ok, sets_ok)["outcome"] == "C"
    o = lambda *xs: G.overall_outcome({str(i): {"outcome": x} for i, x in enumerate(xs)})  # noqa: E731
    assert o("A", "A") == "A" and o("A", "B") == "A-one" and o("A", "C").startswith("A-one")
    assert o("B", "C") == "C" and o("B", "D") == "B" and o("D", "D") == "D" and o("N", "B") == "N"


def test_drift_and_cluster_rules():
    assert G.rule_drift(_m(200, 10), _m(0, 0))
    assert not G.rule_drift(_m(200, 10), _m(100, 30))
    p = G.pooled_counts([_m(100, 5), _m(50, 3)])
    assert p["commits"] == 150 and G.rule_cluster(p)


def test_kmeans_recovers_clusters():
    rng = np.random.default_rng(9)
    cent = np.eye(8, 16) * 5
    x = np.concatenate([cent[k] + rng.normal(size=(30, 16)) * 0.3 for k in range(8)])
    lab = G.kmeans(x, k=8, seed=0)
    for k in range(8):
        assert len(set(lab[30 * k:30 * (k + 1)].tolist())) == 1
    assert len(set(lab.tolist())) == 8


def test_topk_and_margin():
    s = np.array([[0.9, 0.1, 0.5], [0.1, 0.9, 0.5]])
    assert G.topk_acc(s, np.array([0, 0]), 1) == 0.5 and G.topk_acc(s, np.array([0, 0]), 3) == 1.0
    assert np.allclose(G.margin(s), [0.4, 0.4])


# --- model ---------------------------------------------------------------------------------------------------------

def test_model_shapes_and_one_step():
    torch = pytest.importorskip("torch")
    import a1model as M

    torch.manual_seed(0)
    net = M.ATMS(n_ch=63, n_t=250)
    assert 2_500_000 < M.n_params(net) < 3_500_000
    x = torch.randn(8, 63, 250)
    sub = torch.ones(8, dtype=torch.long)
    img, txt = torch.randn(8, 1024), torch.randn(8, 1024)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3)
    l0 = M.atm_loss(net, net(x, sub), img, txt)
    for _ in range(5):
        opt.zero_grad()
        loss = M.atm_loss(net, net(x, sub), img, txt)
        loss.backward()
        opt.step()
    assert net(x, sub).shape == (8, 1024)
    assert float(M.atm_loss(net, net(x, sub), img, txt).detach()) < float(l0.detach())


# --- runner stages on synthetic score files -----------------------------------------------------------------------

def test_gate_and_evaluate_stages_end_to_end(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import a1run as R

    rng = np.random.default_rng(11)
    d = tmp_path / "sub-01"
    d.mkdir()
    n_tr_img = 3000
    cl_tr = rng.integers(0, 8, size=n_tr_img)
    cl_te = rng.integers(0, 8, size=200)
    monkeypatch.setattr(R, "concept_clusters", lambda c: (cl_tr, cl_te))
    np.savez(d / "scores_cal.npz", val_sim=_synthetic_sims(2000, rng, 0.4),
             order_sim=_synthetic_sims(1000, rng, 0.4), order_img=np.arange(1000),
             certify_sim=_synthetic_sims(2000, rng, 0.4), certify_img=np.arange(1000, 3000))
    (d / "train_done.json").write_text(json.dumps({"best_epoch": 7}), encoding="utf-8")
    (d / "s0.json").write_text(json.dumps({"pass": True}), encoding="utf-8")
    c = SimpleNamespace(dir=d, s=1, out=tmp_path, dry=True)
    g = R.st_gate(c)
    assert g["gate"]["commit_p"] is not None and len(g["r2_gates"]) == 8

    def shuffled(n):
        s = _synthetic_sims(n, rng, 0.4)
        img = np.repeat(np.arange(200), n // 200)
        out = np.empty_like(s)
        for i in range(n):  # true column = the unit's image
            row = np.delete(s[i], 0)
            out[i] = np.insert(row, img[i], s[i, 0])
        return out, img

    t, timg = shuffled(4000)
    e, eimg = shuffled(2000)
    lt, limg = shuffled(2000)
    a80, _ = shuffled(200)
    flat = lambda: rng.normal(0, 0.05, size=(4000, 200))  # noqa: E731
    np.savez(d / "scores_test.npz", test_img=timg, test_sim=t, avg80_sim=a80, N1_sim=flat(), N2_sim=flat(),
             N3_sim=flat(), early_sim=e, early_img=eimg, late_sim=lt, late_img=limg)
    res = R.st_evaluate(c)
    assert res["verdict"]["outcome"] == "A", res["verdict"]
    assert res["R1"]["pass"] and res["R2"]["pass"]
    assert res["alpha_0.05_descriptive"]["real"]["units"] == 4000
    monkeypatch.setattr(R, "RESULTS", tmp_path / "results")
    s = R.st_summary(tmp_path, [1])
    assert s["outcome"] == "A-one" or s["outcome"] == "A"
