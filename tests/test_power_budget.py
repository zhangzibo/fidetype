"""Tests for the M1-15 r2 fixes (CPU only, synthetic data).

- sleep prevention (``fidetype.utils.power``),
- the active-time budget (a large gap is not counted; a resume keeps the budget),
- the opt-in "plateau" schedule (LR decay and stop on the val trend),
- ``infer_sentence --head conv``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.utils import power
from fidetype.utils.power import ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ActiveTimer, keep_awake, set_keep_awake


class FakeKernel32:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def SetThreadExecutionState(self, flags: int) -> int:  # noqa: N802 (Windows API name)
        self.calls.append(flags)
        return 0x80000000  # the previous state; non-zero = success


# --- power helper ---------------------------------------------------------------------------


def test_set_keep_awake_flags():
    k = FakeKernel32()
    assert set_keep_awake(True, k) is True
    assert set_keep_awake(False, k) is True
    assert k.calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]
    assert k.calls[0] == 0x80000001


def test_keep_awake_clears_on_exception():
    k = FakeKernel32()
    msgs: list[str] = []
    with pytest.raises(RuntimeError):
        with keep_awake(msgs.append, kernel32=k) as on:
            assert on is True
            raise RuntimeError("boom")
    assert k.calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]
    assert any("cleared" in m for m in msgs)


def test_keep_awake_noop_off_windows(monkeypatch):
    monkeypatch.setattr(power.sys, "platform", "linux")
    assert power._kernel32() is None
    assert set_keep_awake(True) is False
    with keep_awake() as on:
        assert on is False


# --- active timer ---------------------------------------------------------------------------


class StepClock:
    """+1 s per call; a one-off extra jump of ``jump`` s on call number ``at``."""

    def __init__(self, jump: float = 0.0, at: int = -1) -> None:
        self.n, self.t, self.jump, self.at = 0, 0.0, jump, at

    def __call__(self) -> float:
        self.n += 1
        self.t += 1.0 + (self.jump if self.n == self.at else 0.0)
        return self.t


def test_active_timer_ignores_large_gap():
    gaps: list[float] = []
    tm = ActiveTimer(0.0, max_gap_s=300, clock=StepClock(jump=3600, at=3), on_gap=gaps.append)
    for _ in range(5):
        tm.tick()
    assert tm.active_s == pytest.approx(4.0)  # 5 ticks; one of them is the 3601 s gap
    assert gaps == [pytest.approx(3601.0)]
    assert not tm.exceeded(0.1) and tm.exceeded(3.5 / 60) and not tm.exceeded(None)


def test_active_timer_starts_from_saved_value():
    tm = ActiveTimer(100.0, clock=StepClock())
    tm.tick()
    assert tm.active_s == pytest.approx(101.0)


# --- plateau schedule (pure logic) -----------------------------------------------------------


def test_plateau_lr_decay_and_trend_stop():
    torch = pytest.importorskip("torch")  # noqa: F841 (train_sentence imports torch)
    from fidetype.decoders.train_sentence import plateau_init_state, plateau_lr_lambda, plateau_update

    ocfg = {"lr": 1e-3, "plateau_patience": 2, "plateau_factor": 0.5, "min_lr": 1e-5, "max_lr_reductions": 3}
    tcfg = {"patience_evals": 6, "smooth_alpha": 0.5, "min_delta": 0.002}
    st = plateau_init_state()
    f = plateau_lr_lambda(4, st)
    assert f(0) == pytest.approx(0.25) and f(10) == pytest.approx(1.0)
    # Improving trend: no reduction, no stop.
    for v in (0.9, 0.8, 0.7, 0.6):
        tr = plateau_update(st, v, ocfg, tcfg)
        assert not tr["stop"] and not tr["lr_reduced"]
    assert st["since_improve"] == 0 and st["lr_scale"] == 1.0
    # A noisy single drop on a flat trend counts less than the raw value (smoothing).
    flat = [0.6] * 20
    stopped_at = None
    for i, v in enumerate(flat):
        tr = plateau_update(st, v, ocfg, tcfg)
        if tr["stop"]:
            stopped_at = i
            break
    assert st["lr_reductions"] == 3 and st["lr_scale"] == pytest.approx(0.125)
    assert f(10) == pytest.approx(0.125)  # the LR lambda reads the reduced scale
    assert stopped_at is not None and st["since_improve"] >= 6
    # No stop while improvements continue, even after many evals.
    st2 = plateau_init_state()
    for i in range(200):
        assert not plateau_update(st2, 1.0 - 0.004 * i, ocfg, tcfg)["stop"]


def test_plateau_floor_allows_stop_before_max_reductions():
    pytest.importorskip("torch")
    from fidetype.decoders.train_sentence import plateau_init_state, plateau_update

    ocfg = {"lr": 4e-5, "plateau_patience": 1, "plateau_factor": 0.5, "min_lr": 1e-5, "max_lr_reductions": 10}
    tcfg = {"patience_evals": 3, "smooth_alpha": 1.0, "min_delta": 0.002}
    st = plateau_init_state()
    stops = [plateau_update(st, 0.5, ocfg, tcfg)["stop"] for _ in range(5)]
    assert st["lr_scale"] == pytest.approx(0.25)  # 4e-5 -> 2e-5 -> 1e-5 (floor)
    assert stops.index(True) == 3  # since_improve 3 (first eval sets the best) and LR at the floor


def test_plateau_max_lr_reductions_is_a_cap():
    pytest.importorskip("torch")
    from fidetype.decoders.train_sentence import plateau_init_state, plateau_update

    # Patience for the stop is long, so without a cap the LR would keep halving down to the floor.
    ocfg = {"lr": 1e-3, "plateau_patience": 1, "plateau_factor": 0.5, "min_lr": 1e-6, "max_lr_reductions": 2}
    tcfg = {"patience_evals": 12, "smooth_alpha": 1.0, "min_delta": 0.002}
    st = plateau_init_state()
    trs = [plateau_update(st, 0.5, ocfg, tcfg) for _ in range(14)]
    assert st["lr_reductions"] == 2 and st["lr_scale"] == pytest.approx(0.25)
    assert sum(t["lr_reduced"] for t in trs) == 2
    assert [t["stop"] for t in trs].index(True) == 12  # since_improve reaches 12 (the first eval sets the best)


# --- training (synthetic cache, CPU) ---------------------------------------------------------

torch = pytest.importorskip("torch")
torch.set_num_threads(2)

from fidetype.decoders.synthetic import write_synthetic_cache  # noqa: E402

CACHE_MODEL = dict(spatial_dim=8, conv_dim=16, conv_blocks=1, conv_kernel=3, key_dim=16, trans_layers=1,
                   trans_heads=2, trans_ffn=32, dropout=0.0, input_dropout=0.0, lookahead_keys=0)


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("cache") / "v1"
    write_synthetic_cache(root, n_subjects=2, blocks_per_subject=1, trials_per_block=8, amplitude=3.0, seed=1)
    return root


def _cfg(cache: Path, tmp: Path, max_minutes=None, epochs: int = 50, **optim) -> dict:
    return {
        "run_name": "t",
        "runs_dir": str(tmp),
        "data": {"root": str(cache), "train_splits": ["train", "val", "test"], "val_splits": ["val"],
                 "batch_size": 2, "eval_batch_size": 8, "augment": {}, "mmap_dir": str(tmp / "mm")},
        "model": CACHE_MODEL,
        "optim": {"lr": 3e-3, "warmup_steps": 2, "epochs": epochs, "weight_decay": 0.0, **optim},
        "train": {"seed": 0, "device": "cpu", "bf16": False, "log_every_steps": 1000, "torch_threads": 2,
                  "patience_evals": 1000, "max_minutes": max_minutes},
    }


def _fake_timer(monkeypatch, jump: float = 0.0, at: int = -1) -> None:
    import fidetype.decoders.train_sentence as ts

    class FakeTimer(ActiveTimer):
        def __init__(self, active_s=0.0, max_gap_s=300.0, clock=None, on_gap=None):
            super().__init__(active_s, max_gap_s, StepClock(jump, at), on_gap)

    monkeypatch.setattr(ts, "ActiveTimer", FakeTimer)


def test_budget_ignores_simulated_suspend(cache, tmp_path, monkeypatch):
    from fidetype.decoders.train_sentence import train

    _fake_timer(monkeypatch, jump=3600, at=3)  # a 1 h "sleep" after the 2nd step
    res = train(_cfg(cache, tmp_path, max_minutes=10 / 60), tmp_path / "r", echo=False)  # 10 s budget
    assert res["stop_reason"] == "max_minutes"
    assert 10.0 < res["active_s"] < 13.0  # the 3601 s gap did not count
    assert res["global_step"] >= 8  # wall-clock logic would have stopped after step 2
    log = (tmp_path / "r" / "train.log").read_text(encoding="utf-8")
    assert "suspend gap detected" in log
    st = json.loads((tmp_path / "r" / "status.json").read_text())
    assert st["status"] == "stopped" and st["active_min"] > 0


def test_resume_keeps_budget(cache, tmp_path, monkeypatch):
    from fidetype.decoders.train_sentence import train

    _fake_timer(monkeypatch)
    budget = 10 / 60
    fresh = train(_cfg(cache, tmp_path, max_minutes=budget), tmp_path / "fresh", echo=False)
    part = train(_cfg(cache, tmp_path, max_minutes=budget), tmp_path / "b", max_steps=5, echo=False)
    ck = torch.load(tmp_path / "b" / "latest.pt", weights_only=False)
    assert ck["state"]["active_s"] == pytest.approx(part["active_s"]) and part["active_s"] > 3.0
    res = train(_cfg(cache, tmp_path, max_minutes=budget), tmp_path / "b", resume=True, echo=False)
    assert res["stop_reason"] == "max_minutes"
    added = res["global_step"] - part["global_step"]
    assert added < fresh["global_step"] - 3  # the resumed run spent only the rest of the budget
    assert res["active_s"] == pytest.approx(fresh["active_s"], abs=3.0)
    assert "active time so far" in (tmp_path / "b" / "train.log").read_text(encoding="utf-8")


def test_plateau_training_stops_on_trend_and_logs(cache, tmp_path):
    from fidetype.decoders.train_sentence import train

    cfg = _cfg(cache, tmp_path, epochs=2000, schedule="plateau", plateau_patience=1, min_lr=1e-4,
               max_lr_reductions=2)
    cfg["train"].update(patience_evals=3, min_delta=0.5)  # nothing counts as improvement -> fast stop
    res = train(cfg, tmp_path / "p", echo=False)
    assert res["stop_reason"] == "early_stop" and res["epoch"] < 20
    assert res["lr_reductions"] >= 2 and res["lr_scale"] < 1.0
    assert (tmp_path / "p" / "best.pt").exists()
    log = (tmp_path / "p" / "train.log").read_text(encoding="utf-8")
    assert "trend: smoothed" in log and "evals_since_improve" in log and "plateau: LR scale reduced" in log
    st = json.loads((tmp_path / "p" / "status.json").read_text())
    assert st["schedule"] == "plateau" and {"smooth", "since_improve", "lr", "last_val"} <= set(st)
    # Resume restores the reduced LR scale.
    r2 = train({**cfg, "train": {**cfg["train"], "patience_evals": 1000}}, tmp_path / "p", resume=True,
               max_steps=res["global_step"] + 1, echo=False)
    assert r2["lr_scale"] == pytest.approx(res["lr_scale"])


def test_cosine_default_unchanged(cache, tmp_path):
    from fidetype.decoders.train_sentence import DEFAULT_CONFIG, train

    assert DEFAULT_CONFIG["optim"]["schedule"] == "cosine"
    res = train(_cfg(cache, tmp_path, epochs=1), tmp_path / "c", echo=False)
    assert res["stop_reason"] == "epochs_done" and res["lr_scale"] == 1.0
    with pytest.raises(ValueError):
        train(_cfg(cache, tmp_path, epochs=1, schedule="bogus"), tmp_path / "x", echo=False)


# --- infer_sentence --head conv ---------------------------------------------------------------


def test_infer_head_conv(cache, tmp_path):
    from fidetype.decoders.infer_sentence import run_inference
    from fidetype.decoders.train_sentence import train

    train(_cfg(cache, tmp_path, epochs=1), tmp_path / "full", echo=False)
    fin = run_inference(tmp_path / "full", splits=("val",), out_root=tmp_path / "streams", device="cpu",
                        control=True, echo=False)
    conv = run_inference(tmp_path / "full", splits=("val",), out_root=tmp_path / "streams", device="cpu",
                         control=True, echo=False, head="conv")
    assert fin["head"] == "final" and conv["head"] == "conv"
    m_fin = json.loads((tmp_path / "streams" / "full" / "metrics.json").read_text())
    m_conv = json.loads((tmp_path / "streams" / "full_head-conv" / "metrics.json").read_text())
    assert m_fin["head"] == "final" and m_conv["head"] == "conv"  # separate files, no overwrite
    assert {"greedy_real", "greedy_shuffled", "greedy_zeros"} <= set(m_conv["splits"]["val"])
    assert list((tmp_path / "streams" / "full_head-conv" / "val").glob("*.npz"))
    with pytest.raises(ValueError):
        run_inference(tmp_path / "full", splits=("val",), out_root=tmp_path / "streams", device="cpu",
                      echo=False, head="bogus")


def test_infer_cli_accepts_head(monkeypatch):
    import fidetype.decoders.infer_sentence as inf

    seen = {}

    def fake_run(*a, **kw):
        seen.update(kw)
        return {"splits": {}}

    monkeypatch.setattr(inf, "run_inference", fake_run)
    monkeypatch.setattr("fidetype.decoders.train.hard_exit", lambda code: None)
    inf.main(["--run-dir", "x", "--head", "conv"])
    assert seen["head"] == "conv"
    with pytest.raises(SystemExit):
        inf.main(["--run-dir", "x", "--head", "trans"])
