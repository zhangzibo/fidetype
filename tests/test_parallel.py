"""Tests for fidetype.utils.parallel (deterministic process-pool map). Synthetic data only."""

from __future__ import annotations

import os
import random
import subprocess
import sys
import time

import numpy as np
import pytest

from fidetype.utils import parallel as par
from fidetype.utils.parallel import item_seed, pmap

_SHARED: dict = {}


# Module-level functions: spawn pickles them by name.
def square_jitter(x):
    time.sleep(random.random() * 0.02)  # scramble the finish order
    return x * x


def draws(x, seed):
    return (x, seed, np.random.default_rng(seed).random(3).tolist())


def env_probe(_x):
    return {"pid": os.getpid(), "omp": os.environ.get("OMP_NUM_THREADS"), "worker": par.in_worker(),
            "shared": _SHARED.get("value")}


def init_shared(value):
    _SHARED["value"] = value


def logged(item):
    x, log_dir, fail_at = item
    (log_dir / f"call-{x:03d}-{os.getpid()}-{time.perf_counter_ns()}").touch()
    if x == fail_at:
        raise RuntimeError(f"planned failure at {x}")
    return -x


@pytest.fixture(autouse=True)
def private_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("FIDETYPE_ISOLATION_DIR", str(tmp_path / "iso"))
    monkeypatch.delenv(par.WORKERS_ENV, raising=False)


def test_item_seed_is_deterministic_and_distinct():
    a = [item_seed(7, i) for i in range(1000)]
    assert a == [item_seed(7, i) for i in range(1000)]
    assert len(set(a)) == 1000
    assert a != [item_seed(8, i) for i in range(1000)]
    assert all(0 <= s < 2**32 for s in a)


def test_serial_fallback_runs_in_process_with_initializer():
    out = pmap(env_probe, range(3), workers=1, initializer=init_shared, initargs=(42,), log=None)
    assert [o["pid"] for o in out] == [os.getpid()] * 3
    assert all(o["shared"] == 42 and not o["worker"] for o in out)


def test_parallel_equals_serial_order_and_seeds():
    items = list(range(23))
    ref = [x * x for x in items]
    assert pmap(square_jitter, items, workers=1, log=None) == ref
    par_out = pmap(square_jitter, items, workers=3, exact=True, chunksize=2, log=None)
    assert par_out == ref  # input order, not finish order
    s1 = pmap(draws, items, seed=11, workers=1, log=None)
    s3 = pmap(draws, items, seed=11, workers=3, exact=True, chunksize=4, log=None)
    assert s1 == s3  # seed per item, independent of worker count and chunk size
    assert [s for _, s, _ in s1] == [item_seed(11, i) for i in items]
    assert s1 != pmap(draws, items, seed=12, workers=1, log=None)


def test_workers_get_one_thread_background_class_and_shared_data():
    info: dict = {}
    out = pmap(env_probe, range(4), workers=2, exact=True, initializer=init_shared, initargs=("big",), log=None,
               info=info)
    assert info["workers"] == 2
    assert all(o["omp"] == "1" and o["worker"] and o["shared"] == "big" for o in out)
    assert all(o["pid"] != os.getpid() for o in out)
    assert os.environ.get(par.WORKER_ENV) is None  # the parent environment is restored


@pytest.mark.parametrize("workers", [1, 2])
def test_checkpoint_resume_skips_finished_chunks(tmp_path, workers):
    logs = tmp_path / "calls"
    logs.mkdir()
    ck = tmp_path / "ckpt"
    items = [(x, logs, 7) for x in range(10)]
    with pytest.raises(RuntimeError, match="planned failure"):
        pmap(logged, items, workers=workers, exact=True, chunksize=2, checkpoint=ck, checkpoint_key="k1", log=None)
    finished = sorted(p.name for p in ck.glob("chunk-*.pkl"))
    assert "chunk-000003.pkl" not in finished  # the chunk with item 7 failed
    if workers == 1:
        assert finished == [f"chunk-{k:06d}.pkl" for k in range(3)]  # serial stops at the failure
    n_first = len(list(logs.iterdir()))
    items2 = [(x, logs, -1) for x in range(10)]
    out = pmap(logged, items2, workers=workers, exact=True, chunksize=2, checkpoint=ck, checkpoint_key="k1", log=None)
    assert out == [-x for x in range(10)]
    second = len(list(logs.iterdir())) - n_first
    assert second == 2 * (5 - len(finished))  # only unfinished chunks ran again
    # a third run does no work at all
    out3 = pmap(logged, items2, workers=workers, exact=True, chunksize=2, checkpoint=ck, checkpoint_key="k1", log=None)
    assert out3 == out and len(list(logs.iterdir())) - n_first == second


def test_checkpoint_from_another_run_is_refused(tmp_path):
    ck = tmp_path / "ckpt"
    pmap(square_jitter, range(4), workers=1, checkpoint=ck, log=None)
    with pytest.raises(ValueError, match="another run"):
        pmap(square_jitter, range(5), workers=1, checkpoint=ck, log=None)
    with pytest.raises(ValueError, match="another run"):
        pmap(square_jitter, range(4), workers=1, chunksize=2, checkpoint=ck, log=None)


def test_resolve_workers_caps_and_job_slots(monkeypatch):
    from fidetype.utils import isolation as iso

    nbg = len(par.background_cpus())
    n, why = par.resolve_workers(None)
    assert n == nbg and why["slots_held_by_other_jobs"] == 0
    assert par.resolve_workers(3)[0] == min(3, nbg)
    assert par.resolve_workers(None, n_tasks=2)[0] == min(2, nbg)
    monkeypatch.setenv(par.WORKERS_ENV, "2")
    assert par.resolve_workers(None)[0] == min(2, nbg)
    assert par.resolve_workers(64, exact=True)[0] == 2  # the env variable caps even exact
    monkeypatch.delenv(par.WORKERS_ENV)
    assert par.resolve_workers(64, exact=True)[0] == 64
    # another live background job holding 3 slots, and a timing job (ignored)
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        iso.register_job("background", "other", pid=p.pid, slots=3)
        n, why = par.resolve_workers(None)
        assert why["slots_held_by_other_jobs"] == 3 and n == max(1, nbg - 3)
        iso.register_job("timing", "latency", pid=p.pid)  # same pid file overwritten -> class timing
        assert par.resolve_workers(None)[1]["slots_held_by_other_jobs"] == 0
    finally:
        p.kill()
        p.wait()
    with pytest.raises(ValueError):
        par.resolve_workers(0)


def test_resolve_workers_memory_limit(monkeypatch):
    monkeypatch.setattr(par, "available_memory_gb", lambda: 5.0)
    n, why = par.resolve_workers(None, mem_per_worker_gb=2.0)
    assert n == min(2, len(par.background_cpus())) and why["free_ram_gb"] == 5.0
    monkeypatch.setattr(par, "available_memory_gb", lambda: 0.5)
    assert par.resolve_workers(None, mem_per_worker_gb=2.0)[0] == 1  # never below one worker


def test_shared_arrays_are_memory_mapped(tmp_path):
    a = np.arange(12, dtype=np.float32).reshape(3, 4)
    par.save_shared({"lm": a, "ids": np.array([3, 1, 2])}, tmp_path / "sh")
    got = par.load_shared(tmp_path / "sh")
    assert set(got) == {"lm", "ids"}
    assert isinstance(got["lm"], np.memmap) and np.array_equal(got["lm"], a)
    with pytest.raises(ValueError):
        got["lm"][0, 0] = 1.0  # read-only
    with pytest.raises(ValueError):
        par.save_shared({"not a name": a}, tmp_path / "sh")


def test_empty_input_and_bad_chunksize():
    assert pmap(square_jitter, [], log=None) == []
    with pytest.raises(ValueError):
        pmap(square_jitter, [1], chunksize=0, log=None)
