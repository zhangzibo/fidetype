"""P11-12 run.py helpers (CPU, no data): greedy key count, key rate, gate fit rule, gate decision.

    .venv\Scripts\python.exe -m pytest -q experiments/2026-11-20-p11-12-emg-nosignal-gate/test_p11_12.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_12_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_12_run"] = m
    spec.loader.exec_module(m)
    return m


def frames(seq, V=33):
    x = np.full((len(seq), V), -10.0)
    x[np.arange(len(seq)), seq] = 0.0
    return x


def test_n_keys_joins_runs_and_drops_blank(run):
    assert run.n_keys(frames([0, 3, 3, 0, 3, 5, 5, 0, 0])) == 3
    assert run.n_keys(frames([0, 0, 0])) == 0
    assert run.n_keys(np.zeros((0, 33))) == 0
    assert run.kps(frames([3] + [0] * 99)) == pytest.approx(1.0)


def test_fit_gate_rule(run):
    k = list(range(10, 110))  # 100 windows: m = 1
    r = [i / 10 for i in range(1, 101)]
    g = run.fit_gate(k, r)
    assert g["m"] == 1
    assert g["k_min"] == 11  # one window (10) below 11; two below 12
    assert g["r_min"] == pytest.approx(0.2)  # 2nd smallest
    assert g["r_max"] == pytest.approx(20.0)


def test_gate_pass(run):
    g = {"k_min": 2, "r_min": 1.0, "r_max": 50.0}
    assert run.gate_pass(frames([3, 0, 4] + [0] * 97), g)  # 2 keys in 1 s
    assert not run.gate_pass(frames([3] + [0] * 99), g)  # 1 key
    assert not run.gate_pass(frames([3, 0, 4] + [0] * 297), g)  # 0.67 keys / s
    noisy = np.random.default_rng(0).normal(size=(100, 33))  # near-uniform frames: about 97 keys / s
    assert not run.gate_pass(noisy, g)
