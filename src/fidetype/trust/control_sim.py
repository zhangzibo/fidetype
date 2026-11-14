"""Synthetic cursor-control data for tests (SYNTHETIC DATA, no people, no animals).

A clearly artificial generator. It is not a model of any device or brain
area. It exists so that the control trust layer
(:mod:`fidetype.trust.control`) can be tested with known truth.

Model, per 20 ms bin::

    v(t)      = 2D velocity, a smoothed random walk (mm/s), speed capped
    rate_u(t) = exp(b_u + g_u . v(t) / 100)        (cosine-like tuning, Hz)
    counts    ~ Poisson(rate_u(t) * dt)

``no_signal`` spans set every count to zero (a disconnected amplifier).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SimControl:
    counts: np.ndarray       # T x U spike counts
    vel: np.ndarray          # T x 2 true velocity (mm/s)
    no_signal: np.ndarray    # T bool
    dt: float = 0.02


def simulate_control(T: int = 6000, U: int = 60, seed: int = 0, dt: float = 0.02, base_hz: float = 8.0,
                     gain: float = 1.0, max_speed: float = 250.0, no_signal_frac: float = 0.0) -> SimControl:
    rng = np.random.default_rng(seed)
    v = np.zeros((T, 2))
    for t in range(1, T):
        v[t] = 0.95 * v[t - 1] + rng.normal(0.0, 25.0, 2)
        sp = np.linalg.norm(v[t])
        if sp > max_speed:
            v[t] *= max_speed / sp
    b = np.log(base_hz) + rng.normal(0.0, 0.3, U)
    ang = rng.uniform(0, 2 * np.pi, U)
    G = gain * np.column_stack([np.cos(ang), np.sin(ang)])
    rate = np.exp(b[None, :] + (v / 100.0) @ G.T)
    counts = rng.poisson(rate * dt)
    ns = np.zeros(T, bool)
    if no_signal_frac > 0:
        n = int(T * no_signal_frac)
        s = int(rng.integers(0, T - n))
        ns[s:s + n] = True
        counts[ns] = 0
    return SimControl(counts.astype(np.int64), v, ns, dt)


__all__ = ["SimControl", "simulate_control"]
