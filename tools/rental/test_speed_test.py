"""CPU tests for tools/rental/speed_test.py (no GPU, no data).

Run: C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tools/rental/test_speed_test.py
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HIP_VISIBLE_DEVICES", "-1")  # never touch a GPU in these tests
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import speed_test as S  # noqa: E402


def test_project_hours_matches_hand_computation():
    plan = {"train_steps": 1000, "fit_steps": 500, "overhead": 1.1}
    assert abs(S.project_hours(2.0, 0.5, plan) - (2000 + 250) * 1.1 / 3600) < 1e-12


def test_local_reference_reproduces_m4_13_hours():
    # 115,000 steps x 1.27 s = 40.6 h, the measured M4-13 training time (40.56 h)
    h = S.project_hours(S.LOCAL_REF_S_PER_STEP, 0.0, {**S.PLANS["calibration_holdout"], "overhead": 1.0})
    assert abs(h - 40.57) < 0.05


def test_plan_step_counts_are_the_registered_ones():
    assert S.PLANS["calibration_holdout"]["train_steps"] == 115_000
    e2 = S.PLANS["e2_self_teaching_t15"]
    assert e2["train_steps"] == 30_000
    assert e2["fit_steps"] == 16 * 36 * 400 + 1600 == 232_000


def test_negative_seconds_refused():
    try:
        S.project_hours(-1.0, 0.0, S.PLANS["calibration_holdout"])
    except ValueError:
        return
    raise AssertionError("negative seconds accepted")


def test_speedup():
    assert S.speedup_vs_local(S.LOCAL_REF_S_PER_STEP / 4) == 4.0


def test_synthetic_items_are_ctc_feasible():
    items = S.synthetic_items(50, 45, seed=3, min_bins=40, max_bins=200)
    assert len(items) == 50
    for si, X, ph, key in items:
        assert 0 <= si < 45 and X.shape[1] == 512 and X.dtype.name == "float16"
        assert (X.shape[0] - 3 - 14) // 4 + 1 >= len(ph) >= 1
        assert ph.min() >= 1 and ph.max() <= 40 and key.startswith("synthetic|")


def test_fit_trainable_names_on_tiny_model():
    sys.path.insert(0, str(S.REPO / "src"))
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, build_torch_model

    m = build_torch_model(LookaheadGRUConfig(n_sessions=3, hidden=8, layers=3, la_proj=4))
    names = S.fit_trainable_names(m)
    assert "day_W" in names and "day_b" in names
    assert any(n.startswith("grus.2.") for n in names)
    assert not any(n.startswith("grus.0.") or n.startswith("grus.1.") for n in names)
    assert any(n.startswith("out.") for n in names)
    assert not any(n.startswith("la_") for n in names)
    for n, p in m.named_parameters():
        assert p.requires_grad == (n in names)


def test_end_to_end_tiny_cpu(tmp_path):
    out = tmp_path / "r.json"
    rc = S.main(["--synthetic", "--synthetic-items", "16", "--synthetic-min-bins", "60",
                 "--synthetic-max-bins", "120", "--tiny", "--device", "cpu", "--steps", "2",
                 "--fit-steps", "2", "--warmup", "1", "--batch", "4", "--fit-batch", "2", "--out", str(out)])
    assert rc == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["device"] == "cpu" and r["tiny_model"] is True
    assert r["train_steps_timed"] == 2 and r["fit_steps_timed"] == 2
    assert set(r["projected_gpu_hours"]) == set(S.PLANS)
    assert r["s_per_step_train_median"] > 0
