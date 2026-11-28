"""CPU unit tests for the P15-54 wrapper (no data, no GPU): session roles, symbol map, selection, pass rules,
outcomes, run order, model, checkpoint resume."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import f3s  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
RULES = CFG["rules"]
#: H2 held-in calibration trial counts (amendment 1, point 1).
COUNTS = {"20220518": 30, "20220523": 48, "20220525": 36, "20220601": 48, "20220603": 48, "20220606": 47,
          "20220608": 25, "20220613": 48, "20220615": 36, "20220622": 48, "20220901": 30, "20220929": 24,
          "20221006": 24, "20221018": 24, "20221025": 23, "20221027": 24, "20221101": 24, "20221103": 24,
          "20221208": 24, "20221215": 12, "20230228": 24}


def test_config_matches_plan():
    t, s1, pc, r = CFG["target"], CFG["stage1"], CFG["pretrain"], CFG["roles"]
    assert t["steps"] == {"3": 500, "6": 650, "12": 800, "24": 1100, "40": 1500}
    assert (t["warmup"], t["lr_min"], t["weight_decay"], t["clip"], t["max_frames"]) == (100, 1e-6, 0.01, 1.0, 24000)
    assert (t["noise_sd"], t["offset_sd"], t["time_masks"], t["time_mask_max"]) == (0.3, 0.2, 2, 20)
    assert s1["lrs"] == [3e-4, 1e-3] and s1["budget"] == 12 and s1["seed"] == 10 and s1["arms"] == ["R", "E", "I"]
    assert s1["exclude_if_val_cer_above"] == 0.95 and s1["tie"] == 0.005 and s1["fallback_lr"] == 3e-4
    assert s1["lr_of"]["E0"] == "E" and s1["lr_of"]["T"] == "E" and s1["lr_of"]["P"] == "R"
    assert s1["lr_of"]["X-R"] == "R" and s1["lr_of"]["X-E"] == "E"
    assert (pc["steps"], pc["lr"], pc["warmup"], pc["lr_min"], pc["weight_decay"], pc["clip"]) == (
        10000, 1e-3, 1000, 1e-6, 0.01, 1.0)
    assert pc["I"]["vocab"] == 41 and pc["I"]["n_in"] == 512 and pc["P"]["perm_seed"] == 12345
    assert CFG["stage2"]["seeds"] == [0, 1, 2]
    assert (RULES["bootstrap_n"], RULES["bootstrap_seed"], RULES["seed_ci_min"]) == (10000, 0, 2)
    assert (RULES["c2_min_cer"], RULES["c2_min_gap"], RULES["c2_rng"], RULES["c2_band"]) == (0.75, 0.10, 77, 0.03)
    assert (RULES["c1_min_cer"], RULES["c1_applies_if_cer_below"]) == (0.85, 0.70)
    assert CFG["caps"] == {"core_hours": 9.0, "total_hours": 20.0}
    assert r["min_trials"] == 50 and r["fallback_min_trials"] == 34 and r["test_last"] == 10
    assert CFG["trunk"]["dilations"] == [1, 2, 4, 8, 1, 2, 4, 8] and CFG["trunk"]["d"] == 512
    assert f3s.e1.TrunkCfg(**{**CFG["trunk"], "dilations": tuple(CFG["trunk"]["dilations"])}).receptive_field() == 121


def test_session_roles_real_counts_use_fallback():
    r = f3s.session_roles(COUNTS, CFG["roles"])
    assert r["fallback"] and r["threshold"] == 34 and r["core_budgets"] == [3, 12, 24] and r["extended_budgets"] == [6]
    assert r["test"] == ["20220603", "20220606", "20220613", "20220615", "20220622"]
    assert r["val"] == ["20220523", "20220525", "20220601"]
    assert len(r["source"]) == 13 and not set(r["source"]) & set(r["test"] + r["val"]) and r["top_budget"] == 24


def test_session_roles_no_fallback_and_stops():
    many = {f"2022{m:02d}01": 60 for m in range(1, 11)}
    r = f3s.session_roles(many, CFG["roles"])
    assert not r["fallback"] and r["core_budgets"] == [3, 12, 40] and r["extended_budgets"] == [6, 24]
    assert r["test"] == ["20220601", "20220701", "20220801", "20220901", "20221001"] and len(r["val"]) == 3
    seven = {f"2022{m:02d}01": 40 for m in range(1, 8)}
    r7 = f3s.session_roles(seven, CFG["roles"])
    assert len(r7["test"]) == 3 and len(r7["val"]) == 3 and len(r7["source"]) == 1
    with pytest.raises(f3s.DataStop):
        f3s.session_roles({f"2022{m:02d}01": 40 for m in range(1, 6)}, CFG["roles"])


def test_symbol_map():
    assert f3s.map_text("hello>world~", CFG["roles"]["symbol_map"]) == "hello world."
    assert f3s.check_symbols(["ab c.", "x,y?'"]) == []
    assert f3s.check_symbols(["ok", "é"]) == ["é"]


def test_select_lr():
    c = CFG["stage1"]
    assert f3s.select_lr({3e-4: 0.5, 1e-3: 0.4}, c)["lr"] == 1e-3
    assert f3s.select_lr({3e-4: 0.404, 1e-3: 0.400}, c)["lr"] == 3e-4  # tie: smaller LR
    assert f3s.select_lr({3e-4: 0.406, 1e-3: 0.400}, c)["lr"] == 1e-3
    assert f3s.select_lr({3e-4: 0.97, 1e-3: 0.6}, c)["lr"] == 1e-3  # diverged run excluded
    assert f3s.select_lr({3e-4: 0.97, 1e-3: 0.99}, c)["lr"] == 3e-4  # both excluded -> 3e-4


def _res(edits, ref, extra=None):
    return {"test_edits_final": list(map(int, edits)), "test_ref": list(map(int, ref)),
            "test_cer_final": float(np.sum(edits) / np.sum(ref)), **(extra or {})}


def test_win_rule():
    rng = np.random.default_rng(0)
    ref = rng.integers(20, 40, 50)
    runs = {}
    for s in range(3):
        runs[("E", 12, s)] = _res(ref * 0.3, ref)
        runs[("R", 12, s)] = _res(ref * 0.6, ref)
    w = f3s.win("E", "R", 12, runs, RULES, [0, 1, 2])
    assert w["pass"] and w["n_ci_above_0"] == 3
    assert f3s.win("R", "E", 12, runs, RULES, [0, 1, 2])["pass"] is False
    runs[("E", 12, 2)] = _res(ref * 0.61, ref)  # one seed with d < 0 -> part (a) fails
    assert f3s.win("E", "R", 12, runs, RULES, [0, 1, 2])["pass"] is False
    del runs[("E", 12, 2)]
    assert f3s.win("E", "R", 12, runs, RULES, [0, 1, 2])["status"] == "not_run"


def test_win_needs_ci_on_two_seeds():
    rng = np.random.default_rng(1)
    ref = rng.integers(20, 40, 50)
    runs = {("R", 3, s): _res(ref * 0.6, ref) for s in range(3)}
    runs[("E", 3, 0)] = _res(ref * 0.3, ref)
    e = (ref * 0.6).astype(int); e[0] -= 1  # tiny gain: d > 0 but CI includes 0
    runs[("E", 3, 1)] = _res(e, ref)
    runs[("E", 3, 2)] = _res(e, ref)
    w = f3s.win("E", "R", 3, runs, RULES, [0, 1, 2])
    assert w["all_d_positive"] and w["n_ci_above_0"] == 1 and w["pass"] is False


def test_c2_rules():
    assert f3s.c2_need(0.30, RULES) == 0.75 and abs(f3s.c2_need(0.70, RULES) - 0.80) < 1e-12
    assert f3s.c2_seed(0.30, [0.90, None, None], RULES)["pass"] is True  # margin 0.15: one run decides
    assert f3s.c2_seed(0.30, [0.70, None, None], RULES)["pass"] is False  # margin -0.05
    assert f3s.c2_triggers_extra(0.30, 0.77, RULES) and f3s.c2_triggers_extra(0.30, 0.72, RULES)
    assert not f3s.c2_triggers_extra(0.30, 0.79, RULES)
    assert f3s.c2_seed(0.30, [0.77, None, None], RULES)["status"] == "missing"  # pair needed but not run
    three = f3s.c2_seed(0.30, [0.77, 0.80, 0.70], RULES)  # mean 0.757 >= 0.75 and 2 of 3 >= 0.75
    assert three["pass"] is True and three["n_runs"] == 3
    assert f3s.c2_seed(0.30, [0.77, 0.74, 0.74], RULES)["pass"] is False  # mean 0.75 but 1 of 3


def test_c1_rule():
    normal = {("E", 3, 0): {"test_cer_final": 0.5, "c1_shuffled_cer": 0.9},
              ("E", 3, 1): {"test_cer_final": 0.8, "c1_shuffled_cer": 0.5},
              ("E", 3, 2): {"test_cer_final": 0.7, "c1_shuffled_cer": 0.86}}
    c = f3s.c1_rule("E", 3, normal, RULES, [0, 1, 2])
    assert c["pass"] is True and [r["seed"] for r in c["runs"]] == [0, 2]
    normal[("E", 3, 2)]["c1_shuffled_cer"] = 0.84
    assert f3s.c1_rule("E", 3, normal, RULES, [0, 1, 2])["pass"] is False


def _roles():
    return f3s.session_roles(COUNTS, CFG["roles"])


def _world(gain_e=0.0, gain_i=0.0, gain_e0=0.0, der=0.95, base=0.6):
    """All core runs + C2 runs. Arm CERs = base - gain on every sentence and seed."""
    rng = np.random.default_rng(3)
    ref = rng.integers(20, 40, 50)
    normal, d = {}, {}
    for b in (3, 12, 24):
        for s in range(3):
            for a, g in (("R", 0.0), ("E", gain_e), ("E0", gain_e0), ("I", gain_i)):
                normal[(a, b, s)] = _res(ref * (base - g), ref, {"c1_shuffled_cer": 0.99})
            for a in ("E", "I"):
                d[(a, b, s, 0)] = der
        d[("R", 24, 0, 0)] = d[("R", 24, 1, 0)] = d[("R", 24, 2, 0)] = der
    return normal, d


def test_verdict_outcomes():
    roles, seeds = _roles(), [0, 1, 2]
    n, d = _world(gain_e=0.3, gain_e0=0.3)
    v = f3s.verdict(n, d, roles, RULES, seeds)
    assert v["H"]["H1"]["pass"] and v["H"]["H3"]["pass"] and v["outcome"]["label"] == "A-trunk"
    assert v["H"]["H5"]["pass"] is None and v["reads"]["R_top"] is True
    n, d = _world(gain_e=0.3, gain_e0=0.0)
    assert f3s.verdict(n, d, roles, RULES, seeds)["outcome"]["label"] == "A-head"
    n, d = _world(gain_i=0.3)
    assert f3s.verdict(n, d, roles, RULES, seeds)["outcome"]["label"] == "I-only"
    n, d = _world()
    assert f3s.verdict(n, d, roles, RULES, seeds)["outcome"]["label"] == "D"
    n, d = _world(gain_e=-0.2)  # E worse than R: negative transfer
    assert "C" in f3s.verdict(n, d, roles, RULES, seeds)["outcome"]["labels"]
    n, d = _world(gain_e=0.3, gain_e0=0.3, der=0.5)  # deranged runs read well: no valid test
    v = f3s.verdict(n, d, roles, RULES, seeds)
    assert v["outcome"]["label"] == "N" and not v["H"]["H1"]["pass"]


def test_stage2_order_and_counts():
    plan = f3s.stage2_plan(_roles(), CFG)
    core = [r for r in plan if r["part"] == "core"]
    ext = [r for r in plan if r["part"] == "ext"]
    assert sum(r["j"] is None for r in core) == 36 and sum(r["j"] == 0 for r in core) == 21
    assert sum(r["j"] is None for r in ext) == 12 + 27 + 18 and sum(r["j"] == 0 for r in ext) == 9 + 3
    assert [(r["arm"], r["budget"]) for r in core[:4]] == [("R", 24), ("E", 24), ("E0", 24), ("I", 24)]
    assert core[11]["seed"] == 0 and core[12]["seed"] == 1  # by seed
    assert all(r["j"] is None for r in core[:36]) and all(r["j"] == 0 for r in core[36:])
    assert [r for r in core if r["j"] == 0 and r["arm"] == "R"][0]["budget"] == 24
    assert {r["budget"] for r in ext if r["arm"] == "R" and r["j"] == 0} == {12}
    assert len({r["dir"] for r in plan}) == len(plan)


def test_check_out(tmp_path):
    d = tmp_path / "derived"
    assert f3s.check_out(d / "p15-54", d) and f3s.check_out(d / "p15-54" / "s2", d)
    assert not f3s.check_out(d / "p15-50", d) and not f3s.check_out(d, d) and f3s.check_out(tmp_path / "x", d)


TINY = f3s.e1.TrunkCfg(d=16, dilations=(1, 2), ff_mult=2, vocab=98)


def test_session_layer_identity_and_causality():
    torch.manual_seed(0)
    m = f3s.Net(TINY, {"h2": (8, 3)}, vocab=98).eval()
    a = m.adapters["h2"]
    assert torch.equal(a.W[1], torch.eye(8)) and torch.equal(a.b, torch.zeros(3, 8))
    x = torch.randn(2, 30, 8)
    s = torch.tensor([0, 2])
    y = a(x, s)
    assert torch.allclose(y, x / (1 + x.abs()))  # softsign(I x + 0)
    lp1 = m(x, "h2", s)
    x2 = x.clone(); x2[:, 20:] = 5.0
    lp2 = m(x2, "h2", s)
    assert torch.allclose(lp1[:, :20], lp2[:, :20], atol=1e-6) and not torch.allclose(lp1[:, 20:], lp2[:, 20:])
    assert sum(p.numel() for p in a.parameters()) == 3 * (8 * 8 + 8)


def test_x_arm_has_no_session_layer():
    m = f3s.Net(TINY, {"h2": (8, 3)}, per_session=False)
    assert not hasattr(m, "adapters") and all(not k.startswith("adapters") for k in m.state_dict())


def test_same_seed_same_new_layers_and_copy_parts():
    torch.manual_seed(4)
    r = f3s.Net(TINY, {"h2": (8, 3)})
    torch.manual_seed(4)
    e0 = f3s.Net(TINY, {"h2": (8, 3)})
    src = f3s.Net(TINY, {"text": (64, 1)})  # another stem, as the E / T checkpoints
    n = f3s.copy_parts(e0, src.state_dict(), f3s.TRUNK)
    assert n > 0 and torch.equal(e0.head.weight, r.head.weight) and torch.equal(e0.p_in["h2"].weight, r.p_in["h2"].weight)
    assert torch.equal(e0.out_norm.weight, src.out_norm.weight)
    assert not torch.equal(e0.blocks[0].ff[0].weight, r.blocks[0].ff[0].weight)
    f3s.copy_parts(e0, src.state_dict(), f3s.TRUNK_HEAD)
    assert torch.equal(e0.head.weight, src.head.weight)
    with pytest.raises(ValueError):
        f3s.copy_parts(f3s.Net(TINY, {"h2": (8, 3)}, vocab=41), src.state_dict(), f3s.TRUNK_HEAD)


def test_norm_stats_hold_invariant():
    rng = np.random.default_rng(0)
    x = rng.integers(0, 5, (40, 6)).astype(np.uint8)
    m1, s1 = f3s.norm_stats([(0, x)], 1, 6, 0.1)
    m2, s2 = f3s.norm_stats([(0, np.repeat(x, 2, axis=0))], 1, 6, 0.1)
    assert np.allclose(m1, m2) and np.allclose(s1, s2) and np.allclose(m1[0], x.mean(0))
    _, s3 = f3s.norm_stats([(0, np.zeros((5, 6)))], 1, 6, 0.1)
    assert np.all(s3 == np.float32(0.1))


def test_binning_helpers():
    v = np.array([[1.0], [3.0], [np.nan], [5.0]])
    ts = np.array([0.000, 0.004, 0.012, 0.025])
    y, m = f3s.frame_mean(ts, v, 0.0, 3, 0.01)
    assert m.tolist() == [True, False, True] and y[0, 0] == 2.0 and y[2, 0] == 5.0
    yh, ok = f3s.hold_series(np.array([0.0, 0.02, 0.04]), np.array([[1.0], [2.0], [3.0]]), 0.0, 6, 0.01)
    assert yh[:, 0].tolist() == [1, 1, 2, 2, 3, 3] and ok.all()


def _fake_store(n_sess=2, n_trials=14, C=8):
    rng = np.random.default_rng(0)
    meta, arrays = [], {}
    for s in range(n_sess):
        d = f"2022010{s + 1}"
        xs, off = [], [0]
        for t in range(n_trials):
            nb = int(rng.integers(10, 20))
            xs.append(rng.integers(0, 4, (nb, C)).astype(np.uint8)); off.append(off[-1] + nb)
            meta.append({"date": d, "trial": t, "block": 0, "n_bins": nb, "row": t, "text": f"ab {t}"})
        arrays[d] = (np.concatenate(xs), np.asarray(off))
    return f3s.H2Store(meta, arrays)


def test_h2_store_split_and_hold():
    st = _fake_store()
    pool, ev = st.split(["20220101", "20220102"], 3, 10)
    assert len(pool) == 6 and len(ev) == 20 and not set(pool) & set(ev)
    assert [st.meta[i]["trial"] for i in pool[:3]] == [0, 1, 2] and [st.meta[i]["trial"] for i in ev[:2]] == [4, 5]
    i = pool[0]
    assert st.length[i] == 2 * st.meta[i]["n_bins"] and np.array_equal(st.frames(i)[::2], st.x20[i])
    with pytest.raises(f3s.DataStop):
        st.split(["20220101"], 5, 10)


def _tiny_env(tmp_path, st):
    cfg = json.loads(json.dumps(CFG))
    cfg["model"]["n_h2"] = 8
    cfg["target"]["steps"] = {k: 4 for k in cfg["target"]["steps"]}
    cfg["target"]["warmup"] = 1
    roles = {"test_last": 10, "test": ["20220101", "20220102"]}
    env = f3s.Env(cfg=cfg, out=tmp_path, device="cpu", trunk=TINY, roles=roles, h2=st, max_frames_override=200)
    return env


def test_target_run_pause_resume_exact(tmp_path):
    st = _fake_store()
    spec = {"stage": "s2", "arm": "R", "budget": 3, "seed": 0, "j": None, "lr": 1e-3,
            "sessions": ["20220101", "20220102"], "dir": "s2/a"}
    full = f3s.target_run(_tiny_env(tmp_path / "full", st), spec)
    env = _tiny_env(tmp_path / "pz", st)
    env.out.mkdir()
    (env.out / "pause").write_text("")
    with pytest.raises(f3s.R8.Paused):
        f3s.target_run(env, spec)
    assert (env.out / "s2/a/latest.pt").exists()
    ck = torch.load(env.out / "s2/a/latest.pt", weights_only=True)
    assert ck["step"] == 1
    (env.out / "pause").unlink()
    res = f3s.target_run(env, spec)
    assert res["test_cer_final"] == full["test_cer_final"] and res["test_edits_final"] == full["test_edits_final"]
    a = torch.load(tmp_path / "full/s2/a/final.pt", weights_only=True)["model"]
    b = torch.load(env.out / "s2/a/final.pt", weights_only=True)["model"]
    assert all(torch.equal(a[k], b[k]) for k in a)
    assert "c1_shuffled_cer" in res and not (env.out / "s2/a/latest.pt").exists()
    assert res["final_train_loss"] == full["final_train_loss"] and res["loss_curve"] == full["loss_curve"]
    assert res["attempt"] == 0 and res["init_seed"] == 0 and res["blank_bias"] == CFG["stability"]["blank_bias"]
    assert isinstance(res["trained"], bool)
    lic = json.loads((env.out / "s2/a/licence.json").read_text(encoding="utf-8"))
    assert lic["research_only"] is False


def test_deranged_and_stage1_results(tmp_path):
    st = _fake_store()
    env = _tiny_env(tmp_path, st)
    d = f3s.target_run(env, {"stage": "s2", "arm": "R", "budget": 3, "seed": 0, "j": 1, "lr": 1e-3,
                             "sessions": ["20220101", "20220102"], "dir": "s2/d"})
    assert d["label_deranged"] and "c1_shuffled_cer" not in d
    spec1 = {"stage": "s1", "arm": "X-R", "budget": 3, "seed": 10, "j": None, "lr": 1e-3,
             "sessions": ["20220101", "20220102"], "dir": "s1/x"}
    with pytest.raises(RuntimeError):  # amendment 2: stage 1 / pilot refuse a test session
        f3s.target_run(env, spec1)
    env.roles["test"] = ["20220109"]
    s1 = f3s.target_run(env, {**spec1, "dir": "s1/y"})
    assert "val_cer_final" in s1 and "test_cer_final" not in s1 and "test_edits_final" not in s1


def test_overlap_and_p_trials():
    st = _fake_store(n_sess=3, n_trials=14)
    roles = {"core_budgets": [3], "extended_budgets": [], "test": ["20220102"], "val": ["20220103"],
             "source": ["20220101"], "test_last": 10}
    assert f3s.overlap_counts(st, roles) == {"3": 0}  # texts "ab 0" .. "ab 2" vs "ab 4" .. "ab 13"
    keep, removed = f3s.p_trials(st, roles)
    assert removed == 10 and len(keep) == 4  # trials 4..13 of the source share texts with test / val


def test_derangement_rng_rule():
    p0 = f3s.e1.derangement(30, np.random.default_rng([2, 77]))
    p1 = f3s.e1.derangement(30, np.random.default_rng([2, 78]))
    assert not np.any(p0 == np.arange(30)) and not np.array_equal(p0, p1)


def test_committed_gate_fails_without_files(tmp_path):
    ok, why = f3s.committed(tmp_path / "a.json", tmp_path / "b.json")
    assert ok is False and why


# --- amendment 2: stability measure S1, trained rule S2, re-seed S3, verdict S4, pilot ---------------------------------


ST = CFG["stability"]


def test_config_stability():
    assert ST["blank_bias"] == round(np.log(97 * (159.2 - 1)), 1) == 9.6  # ln((V - 1)(F - 1)), stage-1 train pool
    assert ST["blank_bias_pretrain_I"] == round(np.log(40 * (68.52 - 1)), 1) == 7.9  # T15 phoneme head
    assert ST["trained_window"] == 100 and ST["max_reseeds"] == 2
    assert ST["reseed_offset"] == 1000 and ST["trained_margin"] == 1.0
    p = ST["pilot"]
    assert p["arms"] == ["R"] and p["budget"] == 12 and p["seeds"] == [20, 21, 22, 23, 24] and p["stop_at"] == 400
    assert not set(p["seeds"]) & set(CFG["stage2"]["seeds"] + [CFG["stage1"]["seed"]])
    assert p["stop_at"] < CFG["target"]["steps"][str(p["budget"])]
    assert CFG["target"]["warmup"] == 100 and CFG["target"]["clip"] == 1.0  # recipe unchanged by amendment 2


def test_blank_bias_init_changes_only_the_blank_bias():
    torch.manual_seed(7)
    a = f3s.Net(TINY, {"h2": (8, 3)}, vocab=98)
    torch.manual_seed(7)
    b = f3s.Net(TINY, {"h2": (8, 3)}, vocab=98, blank_bias=6.0, blank=0)
    sa, sb = a.state_dict(), b.state_dict()
    assert all(torch.equal(sa[k], sb[k]) for k in sa if k != "head.bias")
    assert float(b.head.bias.detach()[0]) == 6.0 and torch.equal(a.head.bias[1:], b.head.bias[1:])
    src = f3s.Net(TINY, {"text": (64, 1)})
    f3s.copy_parts(b, src.state_dict(), f3s.TRUNK_HEAD)  # a copied head (arm E, T, P) replaces the bias
    assert torch.equal(b.head.bias, src.head.bias)
    x = torch.randn(1, 40, 8)
    torch.manual_seed(7)
    c = f3s.Net(TINY, {"h2": (8, 3)}, vocab=98, blank_bias=6.0).eval()
    p_blank = c(x, "h2", torch.tensor([0]))[..., 0].exp().mean().detach()
    assert float(p_blank) > 0.7  # blank dominates at the start, as with a pretrained head
    assert f3s.blank_bias(CFG) == ST["blank_bias"] and f3s.blank_bias(CFG, float("nan")) is None
    assert f3s.blank_bias({}) is None


def test_init_target_e0_head_equals_r_head(tmp_path):
    env = _tiny_env(tmp_path, _fake_store())
    r = f3s.init_target(env, "R", 3, 2)
    assert abs(float(r.head.bias.detach()[0]) - ST["blank_bias"]) < 1e-6
    torch.manual_seed(3)
    ref = f3s.Net(TINY, {"h2": (8, 2)}, vocab=98)
    assert torch.equal(r.head.weight, ref.head.weight)


def test_trained_rule_and_accept():
    assert f3s.trained_rule(1.0, 3.0, ST) and f3s.trained_rule(4.0, 3.0, ST)  # at the label prior + 1: trained
    assert f3s.trained_rule(3.6, 3.0, ST)  # at the label prior (no signal read) still counts as trained
    assert not f3s.trained_rule(4.01, 3.0, ST) and not f3s.trained_rule(20.0, 3.0, ST)
    assert not f3s.trained_rule(None, 3.0, ST) and not f3s.trained_rule(float("nan"), 3.0, ST)
    assert not f3s.trained_rule(float("inf"), 3.0, ST) and not f3s.trained_rule(1.0, None, ST)
    good, bad = {"final_train_loss": 0.5, "prior_loss": 3.0}, {"final_train_loss": 20.0, "prior_loss": 3.0}
    assert f3s.accept([], ST)["status"] == "missing" and f3s.accept([None, None, None], ST)["status"] == "missing"
    a = f3s.accept([good, None, None], ST)
    assert a["status"] == "done" and a["attempt"] == 0 and a["trained"]
    assert f3s.accept([bad, None, None], ST) == {"status": "need", "next": 1, "result": None}
    a = f3s.accept([bad, good, None], ST)
    assert a["attempt"] == 1 and a["trained"] and a["result"] is good
    a = f3s.accept([bad, bad, bad], ST)
    assert a["attempt"] == 0 and a["trained"] is False and a["result"] is bad and a["n_untrained_before"] == 3
    assert f3s.attempt_seed(2, 0, ST) == 2 and f3s.attempt_seed(2, 2, ST) == 2002
    assert f3s.attempt_dir("s2/R-b3-s0", 0) == "s2/R-b3-s0" and f3s.attempt_dir("s2/R-b3-s0", 1) == "s2/R-b3-s0-a1"


def test_select_lr_excludes_untrained():
    c = CFG["stage1"]
    assert f3s.select_lr({3e-4: 0.5, 1e-3: 0.4}, c, [1e-3])["lr"] == 3e-4
    assert f3s.select_lr({3e-4: 0.5, 1e-3: 0.4}, c, [3e-4, 1e-3])["why"].startswith("all excluded")


def test_verdict_untrained_baseline_does_not_count():
    roles, seeds = _roles(), [0, 1, 2]
    n, d = _world(gain_e=0.3, gain_e0=0.3)
    for b in (3, 12, 24):
        for s in seeds:
            for a in ("R", "E", "E0", "I"):
                n[(a, b, s)]["trained"] = True
    v = f3s.verdict(n, d, roles, RULES, seeds)
    assert v["H"]["H1"]["pass"] and v["untrained_confounded_wins"] == []
    for b in (3, 12, 24):
        n[("R", b, 1)]["trained"] = False  # R did not train on seed 1: E "wins" there for the wrong reason
    v = f3s.verdict(n, d, roles, RULES, seeds)
    assert v["H"]["H1"]["pass"] is False and not any(v["H"]["H1"]["valid_win"].values())
    assert "E|R|3" in v["untrained_confounded_wins"] and v["win"]["E|R|3"]["untrained_seeds"] == [1]
    v0 = f3s.verdict(n, d, roles, RULES, seeds, require_trained=False)  # as-is secondary: plan rules only
    assert v0["H"]["H1"]["pass"] and v0["outcome"]["label"] == "A-trunk"


def test_c2_untrained_deranged_run_fails_the_seed():
    assert f3s.c2_seed(0.30, [0.90, None, None], RULES, [True, False, False])["status"] == "untrained"
    assert f3s.c2_seed(0.30, [0.90, None, None], RULES, [True, False, False])["pass"] is False
    assert f3s.c2_seed(0.30, [0.90, None, None], RULES, [False, True, True])["pass"] is True  # j = 1, 2 not needed
    roles, seeds = _roles(), [0, 1, 2]
    n, d = _world(gain_e=0.3, gain_e0=0.3)
    v = f3s.verdict(n, d, roles, RULES, seeds, der_untrained={("E", 24, 0, 0)})
    assert v["C2"]["E|24"]["pass"] is False and v["C2"]["E|12"]["pass"] is True


def _env_rule(tmp_path, margin):
    env = _tiny_env(tmp_path, _fake_store())
    env.cfg["stability"]["trained_margin"] = margin
    return env


def test_prior_loss():
    rng = np.random.default_rng(0)
    tg = [rng.integers(1, 30, int(rng.integers(5, 12))) for _ in range(8)]
    ln = [int(len(t) * rng.integers(20, 60)) for t in tg]
    p = f3s.prior_loss(tg, ln)
    assert 0 < p < np.log(97)
    T, L = sum(ln), sum(len(t) for t in tg)  # the prior beats a constant output with a wrong blank rate
    worse = []
    for t, n in zip(tg, ln):
        x = torch.full((n, 1, 98), float(np.log(0.5 * L / T / 29)))
        x[..., 0] = float(np.log(1 - 0.5 * L / T))
        x[..., 30:] = -1e4
        worse.append(float(torch.nn.functional.ctc_loss(x, torch.from_numpy(t)[None], torch.tensor([n]),
                                                        torch.tensor([len(t)]), blank=0, reduction="mean")))
    assert p < float(np.mean(worse))
    perm = f3s.e1.derangement(8, np.random.default_rng([0, 77]))
    pd = f3s.prior_loss([tg[int(k)] for k in perm], ln)
    assert np.isfinite(pd) and pd > 0


def test_slot_run_reseeds_until_trained_or_limit(tmp_path):
    spec = {"stage": "s2", "arm": "R", "budget": 3, "seed": 1, "j": 0, "lr": 1e-3,
            "sessions": ["20220101", "20220102"], "dir": "s2/R-b3-s1-d0"}
    env = _env_rule(tmp_path / "never", -1e9)  # no run can train
    res = f3s.slot_run(env, spec)
    assert res["accept"] == {"attempt": 0, "trained": False, "n_untrained_before": 3} and res["attempt"] == 0
    atts = f3s.read_attempts(env, spec["dir"])
    assert [a["init_seed"] for a in atts] == [1, 1001, 2001] and len({a["final_train_loss"] for a in atts}) == 3
    assert f3s.accepted_result(env, spec["dir"])["trained"] is False
    env2 = _env_rule(tmp_path / "always", 1e9)
    res2 = f3s.slot_run(env2, spec)
    assert res2["accept"]["attempt"] == 0 and res2["trained"] and not (env2.out / "s2/R-b3-s1-d0-a1").exists()
    assert res2["test_cer_final"] == atts[0]["test_cer_final"]  # attempt 0 is the plan run, unchanged


def test_accepted_result_incomplete_reseed_counts_as_untrained(tmp_path):
    env = _env_rule(tmp_path, -1e9)
    spec = {"stage": "s2", "arm": "R", "budget": 3, "seed": 0, "j": None, "lr": 1e-3,
            "sessions": ["20220101", "20220102"], "dir": "s2/R-b3-s0"}
    f3s.target_run(env, spec)  # attempt 0 only (e.g. the cap stopped the re-seeds)
    assert f3s.accepted_result(env, spec["dir"], final=False) is None
    r = f3s.accepted_result(env, spec["dir"])
    assert r["trained"] is False and r["accept"]["reseeds_incomplete"]


def test_pilot_plan_and_decision(tmp_path):
    roles = _roles()
    plan = f3s.pilot_plan(CFG, roles)
    p = ST["pilot"]
    assert len(plan) == len(p["seeds"]) * len(p["lrs"]) * 2 and len({x["dir"] for x in plan}) == len(plan)
    assert all(x["sessions"] == roles["val"] and not set(x["sessions"]) & set(roles["test"]) for x in plan)
    assert [x["bias_on"] for x in plan[:2]] == [True, False] and all(x["stop_at"] == 400 for x in plan)
    rows = [{"bias_on": x["bias_on"], "trained": True} for x in plan]
    assert f3s.pilot_decision(rows, p)["decision"] == "go"
    on = [r for r in rows if r["bias_on"]]
    for r in on[:p["stop_if_untrained"]]:
        r["trained"] = False
    d = f3s.pilot_decision(rows, p)
    assert d["decision"] == "stop" and d["on_untrained"] == p["stop_if_untrained"]
    assert f3s.pilot_decision(rows[:3], p)["decision"] is None


def test_pilot_run_stops_early_and_reads_val_only(tmp_path):
    env = _tiny_env(tmp_path, _fake_store())
    env.cfg["target"]["steps"]["12"] = 6
    env.roles = {"test_last": 10, "test": ["20220109"], "val": ["20220101", "20220102"]}
    spec = {"stage": "pilot", "arm": "R", "budget": 3, "seed": 20, "j": None, "lr": 1e-3,
            "sessions": ["20220101", "20220102"], "dir": "pilot/x", "stop_at": 2, "bias": float("nan")}
    env.cfg["target"]["steps"]["3"] = 6
    r = f3s.target_run(env, spec)
    assert r["steps"] == 2 and r["blank_bias"] is None and "val_cer_final" in r and "test_cer_final" not in r
