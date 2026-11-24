r"""P15-41 unit tests (toy numbers and temp folders only; no real data, no GPU).

Run (repo root):
  C:\venvs\fidetype-rocm\Scripts\python.exe -m pytest -q -p no:cacheprovider experiments/2026-11-22-p15-41-more-seeds/test_p41.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import pytest

torch = pytest.importorskip("torch")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p41 as P  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CFG36 = json.loads((P.P36_DIR / "config.json").read_text(encoding="utf-8"))


def ctx_in(tmp: Path) -> P.L.Ctx35:
    return P.make_ctx(HERE / "config.json", tmp, "cpu")


def test_recipe_unchanged_from_p15_36():
    for k in ("p15_33_config", "base_recipe", "frr20", "frr20_budgets", "text_pool", "synth"):
        assert CFG[k] == CFG36[k], k
    for k in ("c2_min_cer", "c2_min_gap", "val_margin", "length_guard", "shuffle_seed"):
        assert CFG["rules"][k] == CFG36["rules"][k], k
    assert CFG["seeds"] == [2, 3, 4] and CFG["old_seeds"] == CFG36["seeds"]
    assert CFG["gpu_cap_hours"] == 8.0 and CFG["block_start_max_hours"] == 5.4


def test_bcfg_and_recipe(tmp_path):
    ctx = ctx_in(tmp_path)
    for b, n in (("3", 1200), ("10", 2000), ("30", 4000)):
        c = P.P36.bcfg(CFG, b)
        spec = c["candidates"][P.FR]
        assert spec["steps"] == n and spec["code"] == 3524 and spec["synth_frac"] == 0.2
        for name, path in c["aligner_sources"].items():
            assert "p15-41" in path.replace("\\", "/") and name.split("-s")[1] in ("2", "3", "4")
        rec = P.B.run_recipe(P.P36.bctx(ctx, b), P.FR)
        assert rec.steps[b] == n and rec.warmup == 100 and rec.weight_decay == 0.05 and rec.dropout == 0.3
    assert ctx.rec.steps["3"] == 600 and ctx.rec.steps["10"] == 1000 and ctx.rec.steps["30"] == 2000


def test_block_runs_order():
    r = P.block_runs(CFG, 3)
    assert len(r) == 7
    assert r[:6] == [("T", "3", 3, False), ("E", "3", 3, False), ("T", "10", 3, False), ("E", "10", 3, False),
                     ("T", "30", 3, False), ("E", "30", 3, False)]
    assert r[6] == ("E", "10", 3, True)


def test_check_out():
    for p in ("p15-36", "p15-35b", "p15-33", "p15-08", "p15-35"):
        assert not P.check_out(Path(rf"C:\Users\zhang\bci-data\derived\{p}").resolve())
    assert not P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-36\x").resolve())
    assert P.check_out(Path(r"C:\Users\zhang\bci-data\derived\p15-41").resolve())


def test_paired_t_and_win():
    d = [0.08, 0.02, 0.03, 0.05, 0.04]
    r = P.paired_t(d)
    m = sum(d) / 5
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / 4)
    half = 2.7764451051977987 * sd / math.sqrt(5)
    assert abs(r["mean"] - m) < 1e-12 and abs(r["ci"][0] - (m - half)) < 1e-9 and r["win"]
    r2 = P.paired_t([0.026, -0.013, 0.01, 0.0, 0.005])
    assert r2["ci"][0] < 0 and not r2["win"]
    assert not P.paired_t([0.1])["win"]
    assert not P.paired_t([-0.05, -0.04, -0.06])["win"]


def test_sign_test():
    assert P.sign_test([0.1] * 5)["p_one_sided"] == 1 / 32
    s = P.sign_test([0.1, 0.1, 0.1, 0.1, -0.1])
    assert s["k_positive"] == 4 and abs(s["p_one_sided"] - 6 / 32) < 1e-12
    assert P.sign_test([0.0, 0.1])["k_positive"] == 1


def test_h1_status():
    pb = ["10", "30"]
    assert P.h1_status({"3": False, "10": True, "30": True}, pb) == "pass"
    assert P.h1_status({"3": True, "10": True, "30": False}, pb) == "partial"
    assert P.h1_status({"3": True, "10": False, "30": False}, pb) == "fail"


def fake_res(seeds, d_by_budget, ref_bad=None):
    res = {}
    for b in CFG["budgets_min"]:
        for k, s in enumerate(seeds):
            for a in ("E", "T"):
                cer = 0.75 + (d_by_budget[b][k] if a == "T" else 0.0)
                ref = [10] * 80
                if ref_bad == (a, b, s):
                    ref = [11] * 80
                res[(a, b, s)] = {"test_cer_final": cer, "test_edits_final": [cer * 10] * 80, "test_ref": ref}
    return res


RULES33 = {"bootstrap_n": 200, "bootstrap_seed": 0, "win_min_abs": 0.0}


def test_h1_verdict():
    seeds = [0, 1, 2, 3, 4]
    d = {"3": [0.08, 0.07, 0.09, 0.06, 0.08], "10": [0.03, 0.02, 0.04, 0.01, 0.03], "30": [0.02, -0.03, 0.01, 0.0, 0.01]}
    v = P.h1_verdict(fake_res(seeds, d), seeds, CFG, RULES33, [2, 3, 4])
    assert v["wins"] == {"3": True, "10": True, "30": False}
    assert v["H1"]["status"] == "partial" and v["H1_3min_secondary"]["win"]
    assert v["per_budget"]["10"]["paired_t_new_seeds_only"]["n"] == 3
    assert abs(v["per_budget"]["10"]["mean_T"] - v["per_budget"]["10"]["mean_E"] - 0.026) < 1e-9
    with pytest.raises(RuntimeError):
        P.h1_verdict(fake_res(seeds, d, ref_bad=("T", "30", 3)), seeds, CFG, RULES33, [2, 3, 4])


def test_c2_row():
    r = P.c2_row({"test_cer_final": 0.77}, {"test_cer_final": 0.88}, CFG["rules"])
    assert r["pass"] and abs(r["needed"] - 0.87) < 1e-12
    assert not P.c2_row({"test_cer_final": 0.77}, {"test_cer_final": 0.86}, CFG["rules"])["pass"]
    assert P.c2_row({"test_cer_final": 0.6}, None, CFG["rules"]) == {"status": "missing", "pass": False}
    assert not P.c2_row({"test_cer_final": 0.6}, {"test_cer_final": 0.74}, CFG["rules"])["pass"]


def test_block_skip_rule(tmp_path, monkeypatch):
    ctx = ctx_in(tmp_path)
    called = []
    monkeypatch.setattr(P.L, "clock_hours", lambda c: 6.0)
    monkeypatch.setattr(P.P36, "train_one", lambda *a, **k: called.append(a) or {"partial": True})
    assert P.stage_blocks(ctx, None, None) == "done"
    b = json.loads((tmp_path / "blocks.json").read_text(encoding="utf-8"))
    assert all(b[str(s)]["status"] == "skipped" for s in (2, 3, 4)) and not called


def test_block_started_continues_after_clock(tmp_path, monkeypatch):
    ctx = ctx_in(tmp_path)
    (tmp_path / "aligners" / "T-b3-s2").mkdir(parents=True)
    assert P.block_started(ctx, 2) and not P.block_started(ctx, 3)
    called = []
    monkeypatch.setattr(P.L, "clock_hours", lambda c: 6.0)
    monkeypatch.setattr(P.P36, "train_one", lambda *a, **k: called.append(a[3:6]) or {"partial": True})
    assert P.stage_blocks(ctx, None, None) == "partial"
    assert called == [("T", "3", 2)]
    b = json.loads((tmp_path / "blocks.json").read_text(encoding="utf-8"))
    assert b["2"]["status"] == "started" and "3" not in b


def test_block_runs_and_tests_in_order(tmp_path, monkeypatch):
    ctx = ctx_in(tmp_path)
    seq = []
    monkeypatch.setattr(P.L, "clock_hours", lambda c: 1.0)
    monkeypatch.setattr(P.P36, "train_one", lambda c, st, pl, a, b, s, ls, m=None: seq.append(("train", a, b, s, ls)) or {})
    monkeypatch.setattr(P, "test_one", lambda c, st, a, b, s, ls: seq.append(("test", a, b, s, ls)) or {})
    assert P.stage_blocks(ctx, None, None) == "done"
    assert len(seq) == 3 * 7 * 2
    assert seq[0] == ("train", "T", "3", 2, False) and seq[1] == ("test", "T", "3", 2, False)
    assert seq[13] == ("test", "E", "10", 2, True) and seq[-1] == ("test", "E", "10", 4, True)
    b = json.loads((tmp_path / "blocks.json").read_text(encoding="utf-8"))
    assert all(b[str(s)]["status"] == "done" for s in (2, 3, 4))


def test_test_one_needs_finished_run(tmp_path):
    ctx = ctx_in(tmp_path)
    with pytest.raises(RuntimeError):
        P.test_one(ctx, None, "E", "10", 2, False)


def test_old_result_paths(tmp_path):
    cfg = json.loads(json.dumps(CFG))
    a, b = tmp_path / "a", tmp_path / "b"
    cfg["sources"]["old_test"] = {"p15_36": str(a), "p15_35b": str(b), "p15_35b_runs": ["E-b30-s0"]}
    for root, name in ((a, "T-b30-s0"), (b, "E-b30-s0")):
        (root / name).mkdir(parents=True)
        (root / name / "result.json").write_text(json.dumps({"budget": 30, "src": root.name}), encoding="utf-8")
    assert P.old_result(cfg, "E", "30", 0)["src"] == "b" and P.old_result(cfg, "T", "30", 0)["budget"] == "30"


def test_control_flags_show_pass_or_fail():
    c2 = {"2": {"status": "done", "pass": False}, "3": {"status": "done", "pass": True}}
    c1 = {"runs": [{"run": "E-10-s2", "pass": True}, {"run": "E-30-s3", "pass": False}]}
    flags = P.control_flags(c2, c1, [2, 3, 4])
    assert flags == ["C2 fail on seed 2", "C2 pass on seed 3", "C2 fail on seed 4 (missing)",
                     "C1 pass on E-10-s2", "C1 fail on E-30-s3"]
    assert not any("done" in f for f in flags)
    assert P.controls_ok(flags) is False
    assert P.controls_ok(P.control_flags({"2": {"status": "done", "pass": True}}, {"runs": []}, [2])) is True


def test_committed_summary_flags_match_stored_rows():
    s = json.loads((HERE / "results" / "summary.json").read_text(encoding="utf-8"))
    assert s["control_flags"] == P.control_flags(s["C2"], s["C1"], s["new_complete_seeds"])
    assert P.controls_ok(s["control_flags"]) == s["H1_valid"]


def test_relabel_summary_keeps_numbers(tmp_path):
    src = json.loads((HERE / "results" / "summary.json").read_text(encoding="utf-8"))
    old = dict(src, control_flags=["C2 done on seed 2"])
    old.pop("control_flags_note", None)
    p = tmp_path / "summary.json"
    p.write_text(json.dumps(old), encoding="utf-8")
    new = P.relabel_summary(p)
    assert new["control_flags"] == P.control_flags(src["C2"], src["C1"], src["new_complete_seeds"])
    for k in ("C2", "C1", "verdict", "runs", "H1_valid", "gpu_hours", "time"):
        assert new[k] == old[k], k
    bad = dict(old, H1_valid=True)
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        P.relabel_summary(p)
