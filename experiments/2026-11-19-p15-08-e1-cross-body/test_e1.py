"""P15-08 E1a unit tests and CPU smoke runs (synthetic data only; no real data, no GPU).

Run (repo root):
  C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -m pytest -q experiments/2026-11-19-p15-08-e1-cross-body/test_e1.py
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

torch = pytest.importorskip("torch")
sio = pytest.importorskip("scipy.io")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e1  # noqa: E402
import run as R  # noqa: E402

SMALL = e1.TrunkCfg(d=32, dilations=(1, 2), dropout=0.1)
SALT = "test-salt"


# --- text and splits ------------------------------------------------------------------------------------


def test_text_mapping():
    assert e1.willett_text("thanks>so>much,>honey~") == "thanks so much, honey."
    assert e1.willett_text("that>opin#ion") == "that opinion"
    t = "it's ok? yes."
    assert e1.decode(e1.encode(t)) == t
    assert e1.VOCAB[e1.TOK["a"]] == "a" and e1.TOK[" "] == 1
    with pytest.raises(KeyError):
        e1.encode("\u00e9")


def fake_meta(n_sess=3, blocks=(1, 2, 3, 4), per_block=5):
    meta = []
    for s in range(n_sess):
        for b in blocks:
            for k in range(per_block):
                meta.append({"session": s, "block": b, "trial": len(meta), "n_write": 600 + 37 * k, "ok": k != 4 or b != 2})
    return meta


def test_splits_last_block_is_test_and_disjoint():
    meta = fake_meta()
    sp = e1.make_splits(meta, SALT)
    sets = [set(sp[k]) for k in ("test", "val", "pool")]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    assert all(meta[i]["block"] == 4 for i in sp["test"])
    assert all(meta[i]["ok"] for k in ("test", "val", "pool") for i in sp[k])
    for s in range(3):
        vb = {meta[i]["block"] for i in sp["val"] if meta[i]["session"] == s}
        assert len(vb) == 1 and 4 not in vb
    assert sp == e1.make_splits(meta, SALT)
    assert len(sets[0]) + len(sets[1]) + len(sets[2]) == sum(r["ok"] for r in meta)


def test_budgets_nested_and_seeded():
    meta = fake_meta(n_sess=4, blocks=tuple(range(1, 9)))
    pool = e1.make_splits(meta, SALT)["pool"]
    for seed in (0, 1):
        prev: list[int] = []
        for b in (0.5, 1, 2, 4):
            sub = e1.budget_subset(meta, pool, b, SALT, seed)
            assert sub[:len(prev)] == prev
            assert e1.minutes_of(meta, sub) >= b
            assert e1.minutes_of(meta, sub[:-1]) < b
            prev = sub
    assert e1.budget_subset(meta, pool, 2, SALT, 0) != e1.budget_subset(meta, pool, 2, SALT, 1)
    assert sorted(e1.budget_subset(meta, pool, None, SALT, 0)) == sorted(pool)


def test_derangement():
    rng = np.random.default_rng(0)
    for n in (2, 3, 10, 47):
        p = e1.derangement(n, rng)
        assert sorted(p) == list(range(n)) and not np.any(p == np.arange(n))


# --- model ---------------------------------------------------------------------------------------------


def test_load_trunk_from_p11_crt():
    ED = e1.ED
    crt = ED.CRT(ED.ModelCfg(d=32, dilations=(1, 2), vocab=98), np.zeros((32, 12), np.float32),
                 np.ones((32, 12), np.float32))
    m = e1.XBody(SMALL, "willett", 2)
    stem0 = m.stem.weight.detach().clone()
    n = e1.load_trunk(m, crt.state_dict())
    assert n == len(e1.trunk_state(crt.state_dict())) > 0
    for k, v in e1.trunk_state(crt.state_dict()).items():
        assert torch.equal(m.state_dict()[k], v)
    assert torch.equal(m.stem.weight, stem0)
    big = e1.XBody(e1.TrunkCfg(d=48, dilations=(1, 2)), "text")
    with pytest.raises(ValueError):
        e1.load_trunk(m, big.state_dict())


def test_shuffle_within_tensors_keeps_values():
    sd = e1.XBody(SMALL, "willett").state_dict()
    sh = e1.shuffle_within_tensors(sd, 7)
    changed = 0
    for k, v in sd.items():
        if k.startswith(e1.TRUNK_PREFIXES) and v.numel() > 1:
            assert torch.equal(torch.sort(v.reshape(-1)).values, torch.sort(sh[k].reshape(-1)).values)
            changed += not torch.equal(v, sh[k])
        else:
            assert torch.equal(v, sh[k])
    assert changed > 5
    assert all(torch.equal(a, b) for a, b in zip(sh.values(), e1.shuffle_within_tensors(sd, 7).values()))


def test_model_is_causal_and_padding_invariant():
    torch.manual_seed(0)
    m = e1.XBody(SMALL, "willett", 2).eval()
    x = torch.randn(1, 50, 192)
    y = m(x, torch.tensor([1]), normalised=True)
    x2 = x.clone(); x2[:, 30:] = torch.randn(1, 20, 192)
    y2 = m(x2, torch.tensor([1]), normalised=True)
    assert torch.allclose(y[:, :30], y2[:, :30], atol=1e-5)
    assert not torch.allclose(y[:, 30:], y2[:, 30:])
    pad = torch.cat([x, torch.zeros(1, 17, 192)], 1)
    assert torch.allclose(m(pad, torch.tensor([1]), normalised=True)[:, :50], y, atol=1e-5)


def test_render_text_puts_bumps_at_keys():
    c = e1.TextCfg(p_drop=0.0, p_sub=0.0, noise_sd=0.0, delay_max=0, bump_min=9, bump_max=9)
    emb = e1.text_embeddings(0)
    x = e1.render_text(np.array([50, 200]), np.array([e1.TOK["a"], e1.TOK["b"]]), 400, emb, c, np.random.default_rng(0))
    assert x.shape == (400, e1.TEXT_DIM)
    e = np.linalg.norm(x, axis=1)
    assert e[:40].max() == 0 and e[60:190].max() == 0 and e[50] > 0 and e[200] > 0
    assert np.dot(x[50], emb[e1.TOK["a"]]) > 0
    c2 = e1.TextCfg(p_drop=1.0, noise_sd=0.0)
    assert np.abs(e1.render_text(np.array([50]), np.array([5]), 400, emb, c2, np.random.default_rng(0))).max() == 0


def test_bootstrap_and_minutes_to():
    ref = np.full(40, 30.0)
    e = np.random.default_rng(0).integers(0, 10, 40).astype(float)
    b = e1.bootstrap_delta(e, e, ref, n=500)
    assert b["delta"] == 0 and b["lo"] <= 0 <= b["hi"]
    b2 = e1.bootstrap_delta(e + 5, e, ref, n=500)
    assert b2["lo"] > 0
    assert R.minutes_to([(3, 0.9), (10, 0.7), (30, 0.5)], 0.6) == pytest.approx(np.exp((np.log(10) + np.log(30)) / 2))
    assert R.minutes_to([(3, 0.9), (10, 0.8)], 0.6) is None
    assert R.minutes_to([(3, 0.5), (10, 0.4)], 0.6) == 3


def fake_results(cers: dict, n=20, seeds=(0, 1), budgets=("3", "10", "30", "all")):
    """cers[(arm, budget)] -> mean CER; seed s gets +-0.005; per-sentence edits match the CER."""
    out = []
    for (a, b), c in cers.items():
        for s in seeds:
            cs = c + (0.005 if s else -0.005)
            rng = np.random.default_rng([ord(a), int(b) if b != "all" else 999, s])
            ed = np.clip(np.round(cs * 50 + rng.normal(0, 1, n)), 0, None)
            out.append({"run": f"{a}-b{b}-s{s}", "arm": a, "budget": b, "seed": s, "label_shuffle": False,
                        "minutes": {"3": 3.2, "10": 10.4, "30": 30.3, "all": 506.0}[b],
                        "test_cer_final": float(ed.sum() / (50 * n)), "test_edits_final": ed.tolist(),
                        "test_ref": [50] * n})
    return out


def test_verdict_rules():
    raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raw = {**raw, "h_budgets": ["3", "10", "30"], "roadmap_rule_budgets": ["3", "10", "30"]}
    base = {("R", b): c for b, c in zip(("3", "10", "30", "all"), (0.95, 0.85, 0.6, 0.3))}
    base |= {("T", b): c for b, c in zip(("3", "10", "30", "all"), (0.90, 0.80, 0.55, 0.3))}
    base |= {("S", b): c for b, c in zip(("3", "10", "30", "all"), (0.95, 0.85, 0.6, 0.3))}
    pos = base | {("E", b): c for b, c in zip(("3", "10", "30", "all"), (0.60, 0.50, 0.40, 0.25))}
    v = R.verdict(fake_results(pos), raw, [0, 1], ["3", "10", "30", "all"])
    assert v["V1"]["pass"] and v["H1"]["status"] == "pass" and v["H2"]["status"] == "pass" and v["H4"]["status"] == "pass"
    null = base | {("E", b): c for b, c in zip(("3", "10", "30", "all"), (0.90, 0.80, 0.55, 0.3))}
    v = R.verdict(fake_results(null), raw, [0, 1], ["3", "10", "30", "all"])
    assert v["H1"]["status"] == "fail" and not v["roadmap_rule"]["pass"]
    weak = {k: (0.9 if k[1] == "all" else c) for k, c in pos.items()}
    v = R.verdict(fake_results(weak), raw, [0, 1], ["3", "10", "30", "all"])
    assert not v["V1"]["pass"] and v["H1"]["status"] == "inconclusive"


# --- CPU smoke: prep from fake .mat files, text pretraining, adaptation, exact resume, summary ------------


def write_fake_session(path: Path, seed: int, n_blocks=3, per_block=4):
    rng = np.random.default_rng(seed)
    words = ["ab", "ba", "cab", "bad", "dab"]
    T = 0
    ts, bts, go, nb, blk, txt = [], [], [], [], [], []
    for b in range(1, n_blocks + 1):
        for k in range(per_block):
            s = ">".join(rng.choice(words, 2)) + ("~" if k % 2 else "")
            L = 60 + 10 * len(s)
            delay = 20
            x = rng.poisson(0.3, (delay + L + 30, 192))
            for j, ch in enumerate(s):  # each character drives its own channel group
                c = (ord(ch) * 7) % 180
                x[delay + 10 * j: delay + 10 * j + 8, c:c + 12] += 3
            go.append(T + delay + 1); nb.append(L); blk.append(b); txt.append(s)
            ts.append(x); bts.append(np.full(len(x), b)); T += len(x)
    obj = np.empty((len(txt), 1), object)
    for i, s in enumerate(txt):
        obj[i, 0] = s
    cond = np.empty((len(txt), 1), object)
    for i in range(len(txt)):
        cond[i, 0] = "OL Copy"
    path.parent.mkdir(parents=True, exist_ok=True)
    sio.savemat(str(path), {"sentencePrompt": obj, "intendedText": obj, "numTimeBinsPerSentence": np.array(nb)[:, None],
                            "sentenceCondition": cond, "sentenceBlockNums": np.array(blk)[:, None],
                            "excludedSentences": np.zeros((len(txt), 1)), "neuralActivityTimeSeries": np.concatenate(ts).astype(np.uint8),
                            "blockNumsTimeSeries": np.concatenate(bts)[:, None], "goCueOnsetTimeBin": np.array(go)[:, None],
                            "sentenceEndTimeBin": (np.array(go) + np.array(nb))[:, None]})


def small_ctx(tmp: Path) -> R.Ctx:
    raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raw = {**raw, "c1_budgets": ["all"], "c2": {"arm": "E", "budget": "0.2", "seed": 0},
           "h_budgets": ["0.2"], "roadmap_rule_budgets": ["0.2"]}
    ft = e1.FTCfg(steps={"0.2": 6, "all": 6}, val_every=3, warmup=2, max_frames=2000)
    tx = e1.TextCfg(steps=6, window=80, batch=4, warmup=2)
    ctx = R.Ctx(out=tmp / "out", cache=tmp / "out" / "willett", raw=raw, device="cpu", trunk=SMALL, ft=ft, tx=tx,
                e_ckpt=tmp / "e.pt", p11_cache=tmp, seeds=[0, 1], budgets=["0.2", "all"], arms=list(e1.ARMS),
                repo_results=tmp / "repo_results")
    ctx.out.mkdir(parents=True, exist_ok=True)
    return ctx


def fake_text_sampler(c: e1.TextCfg) -> R.TextSampler:
    rng = np.random.default_rng(3)
    labs, n = [], []
    for _ in range(3):
        kf = np.sort(rng.choice(np.arange(5, 990), 120, replace=False))
        labs.append({"key_frame": kf, "key_tok": rng.integers(66, 70, len(kf))})
        n.append(1000)
    return R.TextSampler(labs, n, c)


def test_prep_reads_fake_mat(tmp_path):
    for i in range(2):
        write_fake_session(tmp_path / "raw" / f"t5.2020.01.0{i}" / "sentences.mat", i)
    ctx = small_ctx(tmp_path)
    rec = R.stage_prep(ctx, tmp_path / "raw")
    assert rec["sessions"] == 2 and rec["ok"] == 24 and rec["n_test"] == 8
    st = R.WillettStore(ctx.cache)
    i = st.splits["test"][0]
    assert e1.decode(st.tgt[i]) == st.meta[i]["text"] and "." in "".join(st.meta[j]["text"] for j in st.x)
    assert st.length[i] >= st.meta[i]["n_write"] and st.x[i].dtype == np.uint8


def test_cpu_smoke_full_pipeline_and_exact_resume(tmp_path):
    for i in range(2):
        write_fake_session(tmp_path / "raw" / f"t5.2020.01.0{i}" / "sentences.mat", i)
    ctx = small_ctx(tmp_path)
    R.stage_prep(ctx, tmp_path / "raw")
    store = R.WillettStore(ctx.cache)
    torch.manual_seed(5)
    torch.save({"model": e1.XBody(SMALL, "text").state_dict()}, ctx.e_ckpt)
    # Text pretraining with a pause after 3 steps, then resume to the end.
    sampler = fake_text_sampler(ctx.tx)
    (ctx.out / "pause").write_text("x")
    with pytest.raises(R.Paused):
        R.stage_text(ctx, sampler)
    (ctx.out / "pause").unlink()
    assert R.stage_text(ctx, sampler)["steps"] == 6
    # Exact resume of one adaptation run: 6 steps straight == 3 steps + pause + 3 steps.
    other = small_ctx(tmp_path / "b")
    other.cache = ctx.cache; other.e_ckpt = ctx.e_ckpt
    (other.out / "text").mkdir(parents=True)
    import shutil
    shutil.copy(ctx.out / "text" / "final.pt", other.out / "text" / "final.pt")
    R.train_run(other, store, "T", "0.2", 0)
    r1 = R.train_run(ctx, store, "T", "0.2", 0, max_steps=3)
    assert r1 == {"partial": True, "step": 3}
    r2 = R.train_run(ctx, store, "T", "0.2", 0)
    a = torch.load(ctx.out / "runs" / "T-b0.2-s0" / "final.pt", weights_only=True)["model"]
    b = torch.load(other.out / "runs" / "T-b0.2-s0" / "final.pt", weights_only=True)["model"]
    assert all(torch.allclose(a[k], b[k], atol=1e-6) for k in a)
    assert r2["n_train"] >= 1 and 0 <= r2["test_cer_final"] and len(r2["test_edits_final"]) == len(store.splits["test"])
    assert json.loads((ctx.out / "runs" / "T-b0.2-s0" / "licence.json").read_text())["research_only"] is True
    # The whole grid + summary.
    assert R.stage_grid(ctx, store)
    agg = R.stage_summary(ctx)
    assert {"V1", "H1", "H2", "H3", "H4", "C1", "C2", "curve", "roadmap_rule"} <= set(agg)
    assert (ctx.repo_results / "summary.json").exists()
    s = json.loads((ctx.repo_results / "summary.json").read_text(encoding="utf-8"))
    assert "test_edits_final" not in json.dumps(s["runs"])  # aggregate only
    assert len(s["runs"]) == 2 * 2 * 4 + 1
    lic_r = json.loads((ctx.out / "runs" / "R-ball-s1" / "licence.json").read_text())
    assert lic_r["research_only"] is False
    c2 = json.loads((ctx.out / "runs" / "E-b0.2-s0-labelshuf" / "result.json").read_text())
    assert c2["label_shuffle"] is True and "c1_shuffled_cer" not in c2
