"""Micro-benchmark for fidetype.utils.isolation (task M0-22).

Runs one fixed single-thread CPU workload (numpy 96x96 matmuls + a Python
loop, about 1 ms per iteration) and records the per-iteration latency in
three conditions:

  A  timing class, no extra load
  B  timing class, synthetic load in the background class (8 processes)
  C  no isolation (normal priority, all CPUs), same synthetic load unpinned

Usage (repo root):  .venv/Scripts/python experiments/2026-11-13-cpu-isolation/bench.py [--seconds 20]
Writes results.json next to this file. Keep it short: the M6-13 soak may be running.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")  # single-thread workload and load
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

from fidetype.utils.isolation import cpu_model, cpu_times, isolated, load_pct  # noqa: E402

HERE = Path(__file__).resolve().parent
N_LOAD = 8


def spin_main(seconds: float) -> None:
    """Load process: memory-heavy numpy work + Python loops until the deadline."""
    a = np.random.default_rng(0).standard_normal(2_000_000)  # 16 MB, larger than one core's share of L3
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        a = a * 1.0000001
        s = 0
        for i in range(20000):
            s += i


def start_load(seconds: float, isolated_bg: bool) -> list[subprocess.Popen]:
    py = sys.executable
    procs = []
    for _ in range(N_LOAD):
        cmd = [py, str(Path(__file__)), "--spin", str(seconds)]
        if isolated_bg:
            cmd = [py, "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "1",
                   "--label", "M0-22 bench load", "--", *cmd]
        procs.append(subprocess.Popen(cmd, stderr=subprocess.DEVNULL))
    time.sleep(1.5)  # let the load start
    return procs


def workload(n_iter_s: float) -> list[float]:
    rng = np.random.default_rng(1)
    m = rng.standard_normal((96, 96))
    lat = []
    end = time.perf_counter() + n_iter_s
    while time.perf_counter() < end:
        t0 = time.perf_counter_ns()
        x = m
        for _ in range(3):
            x = x @ m
            x /= np.abs(x).max()
        s = 0
        for i in range(15000):
            s += i
        lat.append((time.perf_counter_ns() - t0) / 1e6)
    return lat


def summary(lat: list[float]) -> dict:
    a = np.asarray(lat[50:])  # drop warm-up
    return {"n": int(a.size), "p50_ms": round(float(np.percentile(a, 50)), 4),
            "p95_ms": round(float(np.percentile(a, 95)), 4), "p99_ms": round(float(np.percentile(a, 99)), 4),
            "max_ms": round(float(a.max()), 3), "mean_ms": round(float(a.mean()), 4)}


def run_condition(name: str, seconds: float) -> dict:
    load = []
    if name in ("B", "C"):
        load = start_load(seconds + 4, isolated_bg=(name == "B"))
    try:
        if name in ("A", "B"):
            with isolated("timing", wait_s=0, label=f"M0-22 bench {name}") as iso:
                lat = workload(seconds)
            env = iso.record
        else:
            s0, t0 = cpu_times(), time.perf_counter()
            lat = workload(seconds)
            s1 = cpu_times()
            env = {"class": None, "affinity": "all", "priority": "normal", "cpu_model": cpu_model(),
                   "machine_load_pct": load_pct(s0, s1, range(len(s1))), "wall_s": time.perf_counter() - t0}
    finally:
        for p in load:
            p.wait()
    return {"condition": name, **summary(lat), "measurement_env": env}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--spin", type=float, default=None)
    a = ap.parse_args()
    if a.spin is not None:
        spin_main(a.spin)
        return
    out = {"task": "M0-22", "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seconds_per_condition": a.seconds,
           "n_load_processes": N_LOAD, "results": []}
    for name in ("A", "B", "C"):
        r = run_condition(name, a.seconds)
        print(json.dumps({k: v for k, v in r.items() if k != "measurement_env"}), flush=True)
        out["results"].append(r)
        time.sleep(2)
    (HERE / "results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
