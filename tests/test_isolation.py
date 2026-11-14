"""Tests for fidetype.utils.isolation (CPU classes for latency measurements)."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from fidetype.utils import isolation as iso

SMT8 = [[2 * i, 2 * i + 1] for i in range(8)]  # 8 cores, 16 logical CPUs (Ryzen-style numbering)


def test_plan_reserves_top_cores_and_idles_siblings():
    p = iso.plan_classes(SMT8, 4)
    assert p.timing == (8, 10, 12, 14)
    assert p.idle == (9, 11, 13, 15)
    assert p.background == tuple(range(8))
    assert p.smt
    assert not set(p.timing) & set(p.background)


def test_plan_without_smt_and_caps():
    p = iso.plan_classes([[i] for i in range(4)], 2)
    assert p.timing == (2, 3) and p.background == (0, 1) and p.idle == () and not p.smt
    assert iso.plan_classes([[i] for i in range(4)], 99).background == (0,)  # background keeps one core
    with pytest.raises(ValueError):
        iso.plan_classes([[0, 1]], 1)


def test_plan_env_override(monkeypatch):
    monkeypatch.setenv("FIDETYPE_TIMING_CORES", "2")
    assert iso.plan_classes(SMT8).timing == (12, 14)


def test_masks_and_cpu_list():
    assert iso.mask_of([0, 2, 3]) == 0b1101
    assert iso.cpus_of(0b1101) == [0, 2, 3]
    assert iso._parse_cpu_list("0-2,5") == [0, 1, 2, 5]


def test_thread_env():
    env = iso.thread_env(3)
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
              iso.TORCH_THREADS_ENV):
        assert env[k] == "3"


def test_load_pct():
    before = [(0.0, 0.0), (0.0, 0.0)]
    after = [(1.0, 2.0), (0.0, 2.0)]
    assert iso.load_pct(before, after, [0]) == 50.0
    assert iso.load_pct(before, after, [0, 1]) == 25.0
    assert iso.load_pct(None, after, [0]) is None


def test_topology_is_consistent():
    cores = iso.physical_cores()
    flat = sorted(c for core in cores for c in core)
    assert len(flat) == len(set(flat))
    assert len(flat) <= (os.cpu_count() or 1)


def test_timing_lock_excludes_second_holder(tmp_path, monkeypatch):
    monkeypatch.setenv("FIDETYPE_ISOLATION_DIR", str(tmp_path))
    a, b = iso.TimingLock(), iso.TimingLock()
    a.acquire(label="first")
    try:
        assert a.owner()["label"] == "first"
        with pytest.raises(iso.TimingBusy, match="busy"):
            b.acquire(wait_s=0)
    finally:
        a.release()
    b.acquire(wait_s=0)  # free again
    b.release()
    assert a.owner() is None


def test_record_flags_dirty_runs():
    p = iso.plan_classes(SMT8, 4)
    n = 16
    s0 = [(0.0, 0.0)] * n
    s1 = [(0.0, 10.0)] * n
    clean = iso.build_record("timing", p, True, True, 10.0, 0.0, s0, s1, lock_held=True)
    assert clean["clean"] and clean["foreign_load_pct"] == 0.0
    busy = [(5.0, 10.0)] * n
    dirty = iso.build_record("timing", p, True, True, 10.0, 0.0, s0, busy, lock_held=False)
    assert not dirty["clean"]
    assert any("lock" in r for r in dirty["clean_reasons"])
    assert any("other load" in r for r in dirty["clean_reasons"])
    assert dirty["schema"] == "fidetype.isolation/0.1"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows affinity API")
def test_isolated_pins_and_restores(tmp_path, monkeypatch):
    monkeypatch.setenv("FIDETYPE_ISOLATION_DIR", str(tmp_path))
    before_aff, before_prio = iso.get_affinity(), iso.get_priority()
    with iso.isolated("background") as h:
        assert iso.get_affinity() == list(h.plan.background)
        assert iso.get_priority() == "below_normal"
        assert os.environ["OMP_NUM_THREADS"] == str(len(h.plan.background))
        t_end = time.perf_counter() + 0.1
        while time.perf_counter() < t_end:  # let the load counters move
            pass
    assert iso.get_affinity() == before_aff
    assert iso.get_priority() == before_prio
    rec = h.record
    assert rec["class"] == "background" and rec["affinity_set"] and rec["cpu_model"]
    assert rec["class_cpu_load_pct"] is not None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job object")
def test_cli_child_inherits_class(tmp_path):
    env = dict(os.environ, FIDETYPE_ISOLATION_DIR=str(tmp_path))
    out = tmp_path / "env.json"
    code = ("import os; from fidetype.utils.isolation import get_affinity, get_priority; "
            "print(get_affinity(), get_priority(), os.environ['OMP_NUM_THREADS'])")
    r = subprocess.run([sys.executable, "-m", "fidetype.utils.isolation", "run", "--class", "background",
                        "--env-json", str(out), "--", sys.executable, "-c", code],
                       env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    plan = iso.plan_classes(iso.physical_cores())
    assert str(list(plan.background)) in r.stdout
    assert "below_normal" in r.stdout
    assert out.exists()
