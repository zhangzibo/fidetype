"""CPU unit tests for the P15-49 wrapper (no T15 data, no GPU): config vs plan, stream order, session filter, labels
per arm, fits touch only the allowed parameters, guard outputs, the aci bound, rules and outcomes, and the amendment-2
parts (secondary controller, IPW exposure test, Card rule, check-block report, both outcome readings)."""

from __future__ import annotations

import json
import math
import os
import string
import sys
from pathlib import Path

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import torch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e2  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
PLAN_ARMS = {"F", "FB", "OR", "ST", "SH"}


# --- config vs plan.md ---------------------------------------------------------------------------------------------


def test_config_matches_plan():
    s = CFG["sessions"]
    assert s["base"] == list(range(8)) and s["tuning"] == 8 and s["replay"] == list(range(9, 45))
    assert s["last_third"] == list(range(33, 45))
    L = CFG["loop"]
    assert (L["alpha"], L["delta"], L["gamma"], L["eta"]) == (0.05, 0.1, 0.1, 0.05)
    assert (L["n_phase_a"], L["n_check"], L["null_trials"], L["offer_k"]) == (24, 45, 100, 5)
    assert L["challenger_test"] == "noninferiority" and L["recalibration_rule"] == "absolute"
    assert (L["challenger_level"], L["challenger_margin"], L["challenger_margin_abs"]) == (0.05, 0.1, 0.1)
    assert CFG["base"]["steps"] == 30000 and CFG["base"]["stop_if_val_per_above"] == 0.30
    assert CFG["fit"]["update1_steps"] == 100 and CFG["fit"]["nightly_steps_default"] == 300
    g = CFG["grid"]
    assert g["update1_lr"] == [1e-4, 3e-4] and g["nightly_steps"] == [150, 300]
    assert (g["arm"], g["user"], g["seed"], g["session"]) == ("FB", "U1", 0, 8)
    assert CFG["users"]["U1"] == {"p_retype": 0.3, "p_notice": 0.9, "p_sloppy": 0.0}
    assert CFG["users"]["U2"] == {"p_retype": 0.1, "p_notice": 0.5, "p_sloppy": 0.0}
    assert set(CFG["arms"]) == PLAN_ARMS | {"CR", "FBX"} and set(e2.ARM_LABELS) == set(CFG["arms"])
    assert list(e2.ARM_LABELS)[:5] == ["F", "FB", "OR", "ST", "SH"]  # plan arms keep their seed index
    R = CFG["rules"]
    assert (R["p1_max_delta"], R["p1_seeds_needed"], R["p2b_max_rate"], R["p4_min_delta"]) == (-0.02, 2, 0.05, -0.005)
    assert (R["bootstrap_n"], R["bootstrap_seed"]) == (2000, 0)
    assert CFG["gpu_cap_hours"] == 90.0
    assert Path(CFG["out"]).name == "p15-49"


def test_n_check_is_min_ltt_items():
    from fidetype.trust.session_risk import min_ltt_items

    assert min_ltt_items(0.05, 0.1) == CFG["loop"]["n_check"] == 45


def test_run_order_is_plan_order():
    sp = e2.run_specs(CFG)
    assert len(sp) == 20 and len({s["name"] for s in sp}) == 20
    assert [s["name"] for s in sp[:4]] == ["F-U1-s0", "FB-U1-s0", "F-U1-s1", "FB-U1-s1"]
    assert [s["name"] for s in sp[4:10]] == ["SH-U1-s0", "SH-U1-s1", "ST-U1-s0", "ST-U1-s1", "OR-U1-s0", "OR-U1-s1"]
    assert all(s["user"] == "U2" for s in sp[10:]) and {s["arm"] for s in sp} == PLAN_ARMS
    assert sum(e2.ARM_LABELS[s["arm"]] is not None for s in sp) == 16  # 16 runs with fits


def test_grid_cells_and_selection_ties():
    cells = e2.grid_cells(CFG)
    assert [(c["lr"], c["nightly_steps"]) for c in cells] == [(1e-4, 150), (1e-4, 300), (3e-4, 150), (3e-4, 300)]
    w = {1e-4: 0.30, 3e-4: 0.30}
    got = e2.select_grid([{**c, "wer": w[c["lr"]]} for c in cells])
    assert (got["lr"], got["nightly_steps"]) == (1e-4, 150)  # ties: smaller LR, then fewer steps
    w = {1e-4: 0.31, 3e-4: 0.29}
    assert e2.select_grid([{**c, "wer": w[c["lr"]]} for c in cells])["lr"] == 3e-4


def test_check_out():
    d = Path(r"C:\Users\zhang\bci-data\derived")
    assert e2.check_out(d / "p15-49", d) and e2.check_out(d / "p15-49" / "runs", d)
    assert not e2.check_out(d, d) and not e2.check_out(d / "p15-50", d) and not e2.check_out(d / "m4-13", d)
    assert e2.check_out(Path(r"C:\tmp\scratch"), d)


# --- data ----------------------------------------------------------------------------------------------------------


def test_stream_order_interleaves_val_in_file_order():
    o = e2.stream_order(3, 3, 2)
    assert o == [("train", 0), ("train", 1), ("train", 2), ("val_select", 0), ("val_eval", 0), ("val_select", 1),
                 ("val_eval", 1), ("val_select", 2)]


def _fake_derived(root: Path, n_sess: int = 3) -> list[str]:
    ss = [f"t15.2023.01.{k + 10:02d}" for k in range(n_sess)]
    rng = np.random.default_rng(0)
    texts = {}
    for k, s in enumerate(ss):
        arrs, tx = {}, {}
        for part, n in (("train", 4), ("val_select", 2), ("val_eval", 1)):
            arrs[f"{part}_n"] = np.array(n)
            arrs[f"{part}_known"] = np.array([i != 1 for i in range(n)], bool)
            for i in range(n):
                arrs[f"{part}_X{i}"] = rng.standard_normal((60 + 10 * i + k, 512)).astype(np.float16)
                arrs[f"{part}_ph{i}"] = np.array([3, 1, 4 + i], np.int16)
            tx[part] = [f"w{k} {part} {i}" for i in range(n)]
        np.savez(root / f"{s}.npz", **arrs)
        texts[s] = tx
    (root / "sessions.json").write_text(json.dumps(ss), encoding="utf-8")
    (root / "texts.json").write_text(json.dumps(texts), encoding="utf-8")
    return ss


def test_load_part_sessions_equals_filtered_load_part(tmp_path, monkeypatch):
    _fake_derived(tmp_path)
    monkeypatch.setattr(e2.T, "DERIVED", tmp_path)
    for part in ("train", "val_select"):
        full = [x for x in e2.T.load_part(part) if x[0] in (0, 2)]
        mine = e2.load_part_sessions(part, [0, 2])
        assert [x[3] for x in mine] == [x[3] for x in full] and len(mine) > 0
        assert all(np.array_equal(a[1], b[1]) and np.array_equal(a[2], b[2]) for a, b in zip(mine, full))


def test_store_items_plan_order_and_known_only(tmp_path):
    ss = _fake_derived(tmp_path)
    st = e2.Store(tmp_path)
    it = st.items(1)
    assert [x["id"] for x in it] == [f"{ss[1]}|train|0", f"{ss[1]}|train|2", f"{ss[1]}|train|3",
                                     f"{ss[1]}|val_select|0", f"{ss[1]}|val_eval|0"]  # val_select 1 not known
    assert it[0]["text"] == "w1 train 0" and it[0]["n_bins"] == 61 and st.X(it[1]).shape == (81, 512)


# --- labels per arm ------------------------------------------------------------------------------------------------

CMU = {"yes": ["Y", "EH", "S"], "no": ["N", "OW"], "go": ["G", "OW"]}


def _rec(i, truth, top1, label, n_bins=400):
    ph = e2.phoneme_label(truth, CMU)
    return {"id": f"s|train|{i}", "si": 9, "part": "train", "i": i, "n_bins": n_bins, "truth": truth,
            "truth_ph": ph, "top1": top1, "label": label}


def test_phoneme_label_uses_t15_phonemize():
    ids = e2.phoneme_label("yes no", CMU)
    assert list(ids) == [e2.T.PH_ID[p] for p in ["Y", "EH", "S", "SIL", "N", "OW"]]
    assert e2.phoneme_label("yes maybe", CMU) is None and e2.phoneme_label(None, CMU) is None


def test_labels_per_arm():
    recs = [_rec(0, "yes", "no", "yes"), _rec(1, "no", "go", "go"), _rec(2, "go", "go", None)]  # 1: silent error
    assert e2.label_set("F", recs, CMU, None) == []
    fb = e2.label_set("FB", recs, CMU, None)
    assert [r["id"] for r in fb] == ["s|train|0", "s|train|1"] and [r["correct"] for r in fb] == [True, False]
    orc = e2.label_set("OR", recs, CMU, None)
    assert len(orc) == 3 and all(r["correct"] for r in orc)
    st = e2.label_set("ST", recs, CMU, None)
    assert list(st[0]["ph"]) == list(e2.phoneme_label("no", CMU)) and [r["correct"] for r in st] == [False, False, True]
    many = [_rec(i, "yes", "no", ["yes", "no", "go"][i % 3]) for i in range(30)]
    sh = e2.label_set("SH", many, CMU, np.random.default_rng(0))
    fb2 = e2.label_set("FB", many, CMU, None)
    assert sorted(tuple(r["ph"]) for r in sh) == sorted(tuple(r["ph"]) for r in fb2)  # same labels, permuted
    assert any(not np.array_equal(a["ph"], b["ph"]) for a, b in zip(sh, fb2))


def test_length_filter_drops_labels_longer_than_frames():
    recs = [_rec(0, "yes", "no", "yes no yes no yes no", n_bins=30)]
    assert e2.label_set("FB", recs, CMU, None) == []
    assert e2.ctc_ok(400, 20) and not e2.ctc_ok(30, 10)


def test_shuffle_pool_keeps_the_label_multiset():
    pool = [{"id": str(i), "si": 9, "part": "train", "i": i, "n_bins": 400, "ph": np.array([i % 4 + 2]),
             "correct": True} for i in range(20)]
    sh = e2.shuffle_pool(pool, np.random.default_rng(1))
    assert sorted(int(r["ph"][0]) for r in sh) == sorted(int(r["ph"][0]) for r in pool)
    assert [r["id"] for r in sh] == [r["id"] for r in pool]


# --- model and fits ------------------------------------------------------------------------------------------------

MC = {"n_sessions": 3, "n_in": 512, "n_out": 41, "hidden": 8, "layers": 2, "patch": 14, "stride": 4,
      "smooth_sd": 2.0, "la_max": 25, "la_proj": 4, "dropout": 0.4}


def _tiny():
    torch.manual_seed(0)
    m = e2.build_model(MC, None, "cpu")
    with torch.no_grad():
        m.day_W.add_(0.01 * torch.randn_like(m.day_W))
    sd = {k: v.detach().clone() for k, v in m.state_dict().items()}
    keys = e2.delta_keys(sd, MC["layers"])
    return m, sd, e2.Version("base", {k: sd[k].clone() for k in keys}, frozenset(), 0)


def _data(n=3):
    rng = np.random.default_rng(0)
    return [(1, rng.standard_normal((140, 512)).astype(np.float16), np.array([3, 1, 5], np.int64)) for _ in range(n)]


def test_delta_keys():
    _, sd, v = _tiny()
    assert set(v.delta) == {"day_W", "day_b", "out.weight", "out.bias"} | {
        f"grus.1.{n}" for n in ("weight_ih_l0", "weight_hh_l0", "bias_ih_l0", "bias_hh_l0")}


def test_with_day_copies_only_the_target_day():
    _, _, v = _tiny()
    w = e2.with_day(v, 0, 2)
    assert torch.equal(w.delta["day_W"][2], v.delta["day_W"][0]) and w.last_sess == 2
    assert torch.equal(w.delta["day_W"][1], v.delta["day_W"][1]) and not torch.equal(v.delta["day_W"][2], v.delta["day_W"][0])


@pytest.mark.parametrize("mode", ["day", "nightly"])
def test_fit_changes_only_allowed_parameters(mode):
    m, sd, v = _tiny()
    v1 = e2.with_day(v, 0, 1)
    new, broken, loss = e2.fit(m, v1, _data(), 1, mode, 3, 1e-2, 2, (0, 1, 2), "cpu", MC["layers"])
    assert not broken and math.isfinite(loss)
    assert torch.equal(new["day_W"][0], v1.delta["day_W"][0]) and torch.equal(new["day_W"][2], v1.delta["day_W"][2])
    assert not torch.equal(new["day_W"][1], v1.delta["day_W"][1])
    changed_out = not torch.equal(new["out.weight"], v1.delta["out.weight"])
    assert changed_out == (mode == "nightly")
    after = dict(m.named_parameters())
    for k in sd:  # parameters outside the delta never change
        if k not in v.delta and k in after:
            assert torch.equal(after[k].detach(), sd[k]), k
    assert all(p.requires_grad for p in m.parameters())


def test_fit_is_deterministic_on_cpu():
    m, _, v = _tiny()
    a, _, la = e2.fit(m, v, _data(), 1, "nightly", 2, 1e-2, 2, (0, 1, 2), "cpu", MC["layers"])
    b, _, lb = e2.fit(m, v, _data(), 1, "nightly", 2, 1e-2, 2, (0, 1, 2), "cpu", MC["layers"])
    assert la == lb and all(torch.equal(a[k], b[k]) for k in a)


def test_log_probs_shapes_and_order():
    m, _, v = _tiny()
    e2.load_version(m, v)
    items = [{"si": 1, "n_bins": n, "ph": np.array([3], np.int64), "X": np.zeros((n, 512), np.float16)}
             for n in (200, 60, 120)]
    lps = e2.log_probs(m, items, lambda it: it["X"], "cpu", chunk=2)
    assert [lp.shape for lp in lps] == [((n - 14) // 4 + 1, 41) for n in (200, 60, 120)]
    assert np.allclose(np.exp(lps[0]).sum(1), 1.0, atol=1e-4)


# --- trust layer ---------------------------------------------------------------------------------------------------

VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]
PHRASES = ["yes please", "thank you", "i am thirsty", "call my wife", "turn on the light", "i need help"]
LEX = sorted({w for p in PHRASES for w in p.split()})


def _fake_logits(text, rng):
    rows = []
    for ch in text:
        for k in range(3):
            row = rng.normal(0.0, 1.0, len(VOCAB))
            row[VOCAB.index(ch) if k == 0 else 0] += 8.0
            rows.append(row)
    return np.array(rows)


def _phrase_decoder(log_probs):
    from fidetype.lm.beam import ctc_prefix_beam_search

    hyps = ctc_prefix_beam_search(log_probs, beam=32, n_best=32, prune_topk=None, blank_id=0)
    return [{"text": h.text, "score": float(h.score)} for h in hyps
            if h.text and all(w in LEX for w in h.text.split())][:8]


@pytest.fixture(scope="module")
def guard_and_tap():
    import fidetype.trust as ft

    rng = np.random.default_rng(6)
    ts = [str(rng.choice(PHRASES)) for _ in range(160)]
    xs = [_fake_logits(t, rng) for t in ts]
    tap = e2.NBestTap(_phrase_decoder)
    g = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=tap, null_trials=30)
    return g, tap, xs, ts


def test_guard_out_matches_the_updater_item(guard_and_tap):
    from fidetype.trust.update_hooks import TrustGuardUpdater

    g, tap, xs, _ = guard_and_tap
    up = TrustGuardUpdater(e2.copy_guard(g))
    for x in xs[:15]:
        o = e2.guard_out(g, tap, x, 5)
        s, t, risk, action = up._item(g, x)
        assert (o["score"], o["top1"], o["risk"], o["action"]) == (s, t, risk, action)
        assert len(o["offered"]) <= 5 and len(set(o["offered"])) == len(o["offered"])
        if o["top1"]:
            assert o["offered"][0] == o["top1"]


def test_copy_guard_is_the_same_decoder(guard_and_tap):
    from fidetype.trust.update_hooks import same_decoder

    g = guard_and_tap[0]
    c = e2.copy_guard(g)
    assert same_decoder(c, g) and c.config_id == g.config_id and c is not g


def test_loop_settings_and_bound_identity():
    loop = e2.make_loop(CFG, None, "t", 0.5)
    assert loop.n_check == 45 and loop.challenger_test == "noninferiority" and loop.recalibration_rule == "absolute"
    assert loop.evidence_gate and loop.eta == 0.05 and loop.gamma == 0.1
    b = e2.bound_now(loop)
    assert b["n_observed"] == 0 and b["holds"]
    loop.aci.lam_init = 0.5
    rng = np.random.default_rng(0)
    for _ in range(400):  # feed the ACI controller directly: the identity holds for any loss sequence
        tk = loop.aci.decide(float(rng.uniform()))
        loop.aci.observe(tk, float(rng.uniform() < 0.3) if tk.commit else None)
    b = e2.bound_now(loop)
    assert b["n_observed"] == 400 and b["holds"] and b["observed_rate"] <= b["certificate"] + 1e-12


def test_lam_init_of_inf_is_none(guard_and_tap):
    g = guard_and_tap[0]
    cp = float(g.config.policy["commit_p"])
    assert e2.lam_init_of(g) == (cp if math.isfinite(cp) else None)


# --- rules and outcomes --------------------------------------------------------------------------------------------


def _res(arm, user, seed, wer_by_session, wrong=0, items=100, holds=True, p3=True, p5=True):
    ps = [{"session": f"S{s:02d}", "si": s, "items": items, "commits": 10, "wrong": wrong, "silent": 0,
           "w_ed": int(round(w * 100)), "w_n": 100, "ph_ed": 0, "ph_n": 1, "accepted": [], "learning_view": None}
          for s, w in wer_by_session.items()]
    n = items * len(ps)
    return {"arm": arm, "user": user, "seed": seed, "per_session": ps, "p2a": {"holds": holds},
            "p2b": {"wrong": wrong * len(ps), "items": n, "rate": wrong * len(ps) / n, "cp95": [0, 1]},
            "p3": {"pass": p3}, "p5": {"ledger_verify_ok": p5, "every_proposal_decided": True,
                                       "config_changes_on_accept_only": True}}


def _all(fb_gain=0.05, sh_gain=0.0, only=None, **kw):
    rng = np.random.default_rng(0)
    base = {s: 0.4 + 0.05 * rng.standard_normal() for s in range(9, 45)}
    gain = {"F": 0.0, "FB": fb_gain, "OR": fb_gain + 0.02, "ST": 0.0, "SH": sh_gain}
    res = {}
    for name in CFG["run_order"]:
        a, u, s = name.split("-")
        res[name] = _res(a, u, int(s[1:]), {k: v - (gain[a] if k >= 33 else 0.0) for k, v in base.items()},
                         **(kw if only is None or a in only else {}))
    return res


def test_wer_delta_paired_and_bootstrap():
    res = _all()
    d = e2.wer_delta(res["FB-U1-s0"], res["F-U1-s0"], CFG["sessions"]["last_third"], 2000, 0)
    assert d["status"] == "done" and d["delta"] == pytest.approx(-0.05, abs=1e-9) and d["ci95"][1] < 0
    same = e2.wer_delta(res["F-U1-s0"], res["F-U1-s0"], CFG["sessions"]["last_third"], 200, 0)
    assert same["delta"] == 0.0 and same["ci95"] == [0.0, 0.0]
    short = {**res["F-U1-s0"], "per_session": res["F-U1-s0"]["per_session"][:30]}
    assert e2.wer_delta(short, res["F-U1-s0"], CFG["sessions"]["last_third"], 10, 0)["status"] == "incomplete"


def test_verdict_outcomes():
    assert e2.verdict(CFG, _all(), None)["outcome"]["label"] == "A"
    assert e2.verdict(CFG, _all(fb_gain=0.0), None)["outcome"]["label"] == "B"
    assert e2.verdict(CFG, _all(sh_gain=0.05), None)["outcome"]["label"] == "D"
    assert e2.verdict(CFG, _all(wrong=8, only=("FB",)), None)["outcome"]["label"] == "C"  # FB rate 0.08 > 0.05
    assert e2.verdict(CFG, _all(wrong=8), None)["outcome"]["label"] == "D"  # P4 also needs P2b of SH and ST
    assert e2.verdict(CFG, _all(holds=False), None)["outcome"]["label"] == "X"
    assert e2.verdict(CFG, _all(p5=False), None)["outcome"]["label"] == "X"
    assert e2.verdict(CFG, _all(p3=False, only=("OR",)), None)["outcome"]["label"] == "C"
    res = _all()
    del res["FB-U1-s1"]
    assert e2.verdict(CFG, res, None)["outcome"]["label"] == "N"
    assert e2.verdict(CFG, {}, {"base_stop": True})["outcome"]["label"] == "N"
    res = _all()
    del res["SH-U1-s1"]
    assert e2.verdict(CFG, res, None)["outcome"]["label"] == "not_determined"


def test_p1_needs_both_seeds_and_ci():
    res = _all(fb_gain=0.015)  # gain smaller than 0.02: fails P1
    v = e2.verdict(CFG, res, None)
    assert v["rules"]["P1"] is False and all(not x["pass"] for x in v["P1"].values())


def test_outcome_table_direct():
    ok = {"P1": True, "P2a": True, "P2b": True, "P3": True, "P4": True, "P5": True, "primary_done": True}
    assert e2.outcome(ok)["label"] == "A"
    assert e2.outcome({**ok, "P3": False})["label"] == "C"
    assert e2.outcome({**ok, "P1": False, "P2b": False})["label"] == "no pre-registered label"


def test_no_gpu_used():
    assert not torch.cuda.is_initialized()


# --- amendment 2 ---------------------------------------------------------------------------------------------------


def test_amendment2_config():
    a2 = CFG["amendment_2"]
    assert a2["secondary_aci"]["q_lower"] == {"U1": 0.82, "U2": 0.38}
    assert CFG["secondary_runs"] == ["CR-U1-s0", "CR-U1-s1", "FBX-U1-s0", "FBX-U1-s1"]
    assert CFG["arms"]["CR"]["gate"] == "card" and CFG["arms"]["CR"]["holdout_share"] == 0.33
    assert CFG["arms"]["FBX"]["gate"] == "ipw" and CFG["arms"]["FBX"]["exposure_p"] == 0.5
    assert all(CFG["arms"][a].get("gate", "plan") == "plan" and "exposure_p" not in CFG["arms"][a] for a in PLAN_ARMS)
    assert "naive self-training" in CFG["arms"]["ST"]["role"]


def test_q_lower_is_the_pre_stated_binomial_percentile():
    from scipy.stats import binom

    for u, q in CFG["amendment_2"]["secondary_aci"]["q_lower"].items():
        p = CFG["users"][u]["p_notice"]
        assert q == pytest.approx(binom.ppf(0.01, 100, p) / 100)
        assert binom.cdf(round(q * 100) - 1, 100, p) <= 0.01  # P(realised share < q_lower) <= 1 % at N = 100


def test_execution_order_holds_plan_and_secondary_runs():
    ex = [s["name"] for s in e2.exec_specs(CFG)]
    assert len(ex) == 24 and ex[:10] == CFG["run_order"][:10] and ex[10:12] == ["CR-U1-s0", "CR-U1-s1"]
    assert ex[12:22] == CFG["run_order"][10:] and ex[22:] == ["FBX-U1-s0", "FBX-U1-s1"]
    bad = {**CFG, "execution_order": CFG["execution_order"][:-1]}
    with pytest.raises(ValueError):
        e2.exec_specs(bad)


def test_card_arm_uses_the_fb_labels_and_keeps_the_holdout_flag():
    recs = [_rec(0, "yes", "no", "yes"), _rec(1, "no", "go", "go"), {**_rec(2, "go", "go", "go"), "holdout": True}]
    cr, fb = e2.label_set("CR", recs, CMU, None), e2.label_set("FB", recs, CMU, None)
    assert [r["id"] for r in cr] == [r["id"] for r in fb] and [r["correct"] for r in cr] == [True, False, True]
    assert [r.get("holdout") for r in cr] == [None, None, True]


def _aci_stream(q_notice, alpha, n=30000, seed=0):
    """Synthetic stream where ACI binds: score s ~ U(0, 1), P(wrong | s) = 0.5 (1 - s)."""
    rng = np.random.default_rng(seed)
    rc = OnlineCommitRiskControl(alpha=alpha, method="aci", eta=0.05, lam_init=0.5)
    true = obs = 0
    for _ in range(n):
        s = float(rng.uniform())
        wrong = rng.uniform() < 0.5 * (1.0 - s)
        noticed = rng.uniform() < q_notice
        tk = rc.decide(s)
        if tk.commit:
            true += int(wrong)
            obs += int(wrong and noticed)
        rc.observe(tk, float(wrong and noticed) if tk.commit else None)
    return true / n, obs / n


from fidetype.trust.online_risk import OnlineCommitRiskControl  # noqa: E402


def test_aci_on_observed_loss_overshoots_by_one_over_p_notice_and_the_secondary_target_holds():
    true, obs = _aci_stream(0.9, 0.05)
    assert obs == pytest.approx(0.05, abs=0.003) and true == pytest.approx(0.05 / 0.9, abs=0.004) and true > 0.052
    sh = e2.make_shadow(CFG, 0.5, CFG["amendment_2"]["secondary_aci"]["q_lower"]["U1"])
    assert sh.alpha == pytest.approx(0.05 * 0.82)
    true_q, _ = _aci_stream(0.9, sh.alpha)
    assert true_q < 0.05
    true2, _ = _aci_stream(0.5, 0.05)
    assert true2 == pytest.approx(0.10, abs=0.008)
    true2q, _ = _aci_stream(0.5, 0.05 * 0.38)
    assert true2q < 0.05
    with pytest.raises(ValueError):
        e2.make_shadow(CFG, 0.5, 0.0)


def _ipw_items(W, B, n_items, pi, rng, n_same=0):
    """Check items with W worse pairs, B better pairs, n_same identical pairs, the rest both wrong (different texts);
    the shown arm follows a coin with P(challenger) = pi; truth known iff the shown top-1 is right."""
    kinds = ["W"] * W + ["B"] * B + ["S"] * n_same
    kinds += ["T"] * (n_items - len(kinds))
    out = []
    for j, k in enumerate(kinds):
        truth = f"t{j}"
        ch = {"W": "x", "B": truth, "S": truth, "T": "x"}[k]
        cp = {"W": truth, "B": "y", "S": truth, "T": "y"}[k]
        shown = "ch" if rng.uniform() < pi else "cp"
        right = (ch if shown == "ch" else cp) == truth
        out.append({"shown": shown, "ch": ch, "cp": cp, "truth": truth if right else None})
    return out


def test_ipw_estimates_are_unbiased_over_the_coin():
    rng = np.random.default_rng(1)
    ws, bs = [], []
    for _ in range(3000):
        t = e2.ipw_challenger_test(_ipw_items(4, 9, 45, 0.5, rng), 0.5)
        ws.append(t["W_hat"])
        bs.append(t["B_hat"])
    assert np.mean(ws) == pytest.approx(4, abs=0.15) and np.mean(bs) == pytest.approx(9, abs=0.2)


def test_ipw_test_identical_strong_and_worse():
    rng = np.random.default_rng(2)
    same = e2.ipw_challenger_test(_ipw_items(0, 0, 45, 0.5, rng, n_same=45), 0.5)
    assert same["passed"] and same["passed_by"] == "identical top-1" and same["n_diff"] == 0
    strong = [e2.ipw_challenger_test(_ipw_items(0, 45, 45, 0.5, rng), 0.5)["passed"] for _ in range(200)]
    assert np.mean(strong) > 0.9
    worse = [e2.ipw_challenger_test(_ipw_items(15, 2, 45, 0.5, rng), 0.5)["passed"] for _ in range(200)]
    assert not any(worse)
    # the absolute branch cannot pass with 45 items: log(12 / 0.025) = 6.17 > 0.1 x 45
    one = e2.ipw_challenger_test(_ipw_items(0, 0, 45, 0.5, rng, n_same=44), 0.5)
    assert not one["pass_abs"] and one["upper_worse"] > one["abs_limit"]
    with pytest.raises(ValueError):
        e2.ipw_challenger_test([], 0.2)


def test_ipw_test_level_under_the_null():
    rng = np.random.default_rng(3)
    # boundary of the non-inferiority null: W / (W + B) = 0.6 with W + B = 40
    acc = [e2.ipw_challenger_test(_ipw_items(24, 16, 45, 0.5, rng), 0.5)["passed"] for _ in range(2000)]
    assert np.mean(acc) <= 0.05


def test_card_rule():
    assert e2.card_rule(10, 100, 12, 100)["passed"]
    assert not e2.card_rule(12, 100, 12, 100)["passed"]  # strict improvement only
    assert not e2.card_rule(0, 0, 0, 0)["passed"]


def test_unknown_truth_items_have_a_wrong_champion_without_exposure():
    """With the champion's offer shown and p_sloppy 0, a right champion top-1 is always accepted, so every check
    item with unknown truth has a wrong champion (amendment 2, item 2)."""
    from fidetype.trust.adaptive import FeedbackUser

    user = FeedbackUser(p_notice=0.9, p_retype=0.3, p_sloppy=0.0)
    rng = np.random.default_rng(4)
    rows = []
    for j in range(400):
        truth = f"t{j}"
        cp = truth if rng.uniform() < 0.6 else f"c{j}"
        ch = truth if rng.uniform() < 0.6 else f"h{j}"
        offered = [cp] + ([truth] if rng.uniform() < 0.2 and cp != truth else [])
        fb = user.respond_offer(offered, truth, np.random.default_rng([j]))
        rows.append({"known": fb.truth_known, "cp_right": cp == truth, "ch_right": ch == truth, "shown": "cp"})
    u = e2.unknown_split(rows)
    assert u["n_unknown"] > 50 and u["champion_right"] == 0 and u["champion_wrong"] == u["n_unknown"]
    assert u["lost_better"] > 0 and u["hidden_worse"] == 0 and u["unknown_challenger_shown"] == 0


def test_plan_test_shadow_scores_unknown_with_wrong_champion_as_tie():
    """The plan test (library code) on a block where the champion is wrong and the truth is unknown on 20 items, and
    the challenger is right there: the pairs are ties, not 'better' and not 'worse'."""
    ch_out, cp_out, truths, rej = [], [], [], []
    for j in range(45):
        t = f"t {j}"
        if j < 20:  # champion wrong (rejected offer), truth unknown, challenger right
            cp_out.append({"top1": f"c {j}", "score": 0.9, "risk": 0.0})
            ch_out.append({"top1": t, "score": 0.9, "risk": 0.0})
            truths.append(None)
            rej.append([f"c {j}"])
        else:  # both right
            cp_out.append({"top1": t, "score": 0.9, "risk": 0.0})
            ch_out.append({"top1": t, "score": 0.9, "risk": 0.0})
            truths.append(t)
            rej.append(None)
    r = e2.plan_test_shadow(CFG, ch_out, cp_out, truths, rej)
    assert r["better"] == 0 and r["worse"] == 0 and r["n_unknown"] == 0


def _res2(arm, user, seed, wer_by_session, q_rate=0.04, **kw):
    r = _res(arm, user, seed, wer_by_session, **kw)
    n = r["p2b"]["items"]
    r["p2b_q"] = {"wrong": int(q_rate * n), "items": n, "rate": int(q_rate * n) / n}
    r["binding"] = {"commit_mode_items": n, "aci_binds_items": 0}
    return r


def test_verdict_amendment2_reports_both_readings():
    res = _all(wrong=6, only=("FB",))  # plan reading: FB true rate 0.06 > 0.05 (the predicted P2b fail)
    for n, r in list(res.items()):
        r["p2b_q"] = {"wrong": 4 * 36, "items": r["p2b"]["items"], "rate": 4 * 36 / r["p2b"]["items"]}
    v = e2.verdict(CFG, res, None)
    assert v["rules"]["P2b"] is False and v["outcome"]["label"] == "C"  # plan reading (P1 passes, P2b fails)
    a2 = v["amendment_2"]
    assert a2["rules_amendment_2"]["P2b"] is True and a2["outcome_amendment_2"]["label"] == "A"
    assert all(s["status"] == "not_run" for s in a2["secondary"].values()) and not a2["secondary_code_fault"]
    rng = np.random.default_rng(0)
    base = {s: 0.4 + 0.05 * rng.standard_normal() for s in range(9, 45)}
    res["CR-U1-s0"] = _res2("CR", "U1", 0, {k: v - (0.01 if k >= 33 else 0.0) for k, v in base.items()})
    res["CR-U1-s0"]["external_rule"] = {"rule": "card", "n_tested": 36, "n_passed": 20}
    v = e2.verdict(CFG, res, None)
    sec = v["amendment_2"]["secondary"]["CR-U1-s0"]
    assert sec["status"] == "done" and sec["minus_F"]["status"] == "done" and sec["p2a"] is True
    assert v["outcome"]["label"] == "C" and len(v["P2a"]) == 20  # secondary runs never enter the plan rules


def test_verdict_without_p2b_q_is_not_determined():
    v = e2.verdict(CFG, _all(), None)
    assert v["outcome"]["label"] == "A" and v["amendment_2"]["outcome_amendment_2"]["label"] == "not_determined"
