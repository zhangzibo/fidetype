"""Multi-user safety check and per-user bound of the drop-in calibration (P5-42).

A guard calibrated on a **pool** of users (or sessions) gets a bound on the wrong-commit rate of the pool. Two
things can go wrong when the users differ (B1, the pooled-guard check of 2026-11-25):

1. The commit score can carry **who the user is** (for example each user's base rate of right top-1 texts). Then
   the LTT step can certify commits of the "good" users with no evidence from the utterance itself.
2. One user can be above the bound while the pool meets it.

This module gives the two statistics that :func:`fidetype.trust.calibrate` uses with ``users=``. Both work on the
LTT items only, at the score level: item ``i`` has a fixed commit score ``s_i`` (``-inf``: the guard cannot commit
it at any threshold), a 0/1 label ``w_i`` ("the top-1 text is wrong") and an optional 0/1 flag ``o_i`` (the item
is an OFFER_WORDS decision at ``commit_p = inf``; its fallback loss is ``w_i`` then). The LTT step is
:func:`~fidetype.trust.risk_control.ltt_threshold` with exact binomial p-values on the grid 1.00 -> 0.00.

- :func:`user_label_null`: labels permuted **inside** each user (NW, keeps each user's base rate) and **over the
  pool** (NP). ``p_user`` tests "the real certificate is not larger than what each user's base rate alone gives";
  ``p_leak`` tests "NW certifies more commits than NP" (one-sided Mann-Whitney U).
- :func:`per_user_thresholds`: the same LTT step on the items of each user (Mondrian LTT,
  :func:`~fidetype.trust.session_risk.mondrian_ltt`), each at level ``delta`` (``"each"``) or ``delta / K``
  (``"all"``, Bonferroni over the K users). The max of the user thresholds and the pooled threshold bounds the
  wrong-commit rate of every calibration user (a higher threshold only removes commits).

Our own implementation (numpy only).
"""

from __future__ import annotations

import math
from typing import Any, Hashable, Sequence

import numpy as np

from fidetype.trust.risk_control import DEFAULT_LTT_GRID, ltt_threshold

USER_CHECKS = ("off", "warn", "refuse")
USER_BOUNDS = ("pooled", "each", "all")
#: Permutation runs per null (NW and NP).
N_RUNS = 200
#: ``fail`` if the real certificate is not above the within-user null: ``p_user > P_USER_MAX``.
P_USER_MAX = 0.05
#: ``partial`` if NW certifies more commits than NP: one-sided Mann-Whitney ``p_leak < P_LEAK_MAX``.
P_LEAK_MAX = 0.01
#: Tag of the permutation generator (with the calibration seed): the split and the controls do not change.
_RNG_TAG = 5042


def _arrays(s: Sequence[float], w: Sequence[bool], o: Sequence[bool] | None,
            users: Sequence[Hashable]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sv = np.asarray(s, dtype=np.float64)
    wv = np.asarray(w, dtype=bool)
    ov = np.zeros(sv.shape, bool) if o is None else np.asarray(o, dtype=bool)
    first: dict[Hashable, int] = {}
    uv = np.array([first.setdefault(u, len(first)) for u in users], dtype=np.int64)  # ids by first appearance
    if not (sv.shape == wv.shape == ov.shape == uv.shape) or sv.ndim != 1:
        raise ValueError("scores, labels, offer flags and users need one entry per item")
    return sv, wv, ov, uv


def certified(s: np.ndarray, w: np.ndarray, o: np.ndarray, alpha: float, delta: float) -> tuple[float, int]:
    """(threshold, certified commits) of the LTT step for labels ``w``. No certified threshold: (inf, 0)."""
    c = w.astype(np.float64)
    f = (w & o).astype(np.float64)
    r = ltt_threshold(s, c, alpha, delta, f, DEFAULT_LTT_GRID, pvalue="binomial")
    lam = float(r.threshold)
    return lam, (int(np.sum(s >= lam)) if math.isfinite(lam) else 0)


def mwu_greater_p(a: Sequence[float], b: Sequence[float]) -> float:
    """One-sided Mann-Whitney U p-value of "a is larger than b" (normal approximation, tie and continuity
    corrections). 1.0 if all values are equal."""
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    n1, n2 = x.size, y.size
    if n1 == 0 or n2 == 0:
        return 1.0
    allv = np.concatenate([x, y])
    vals, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    upper = np.cumsum(cnt)
    avg_rank = upper - (cnt - 1) / 2.0
    r1 = float(avg_rank[inv[:n1]].sum())
    u = r1 - n1 * (n1 + 1) / 2.0
    n = n1 + n2
    tie = float(np.sum(cnt.astype(np.float64) ** 3 - cnt))
    var = n1 * n2 / 12.0 * ((n + 1) - tie / (n * (n - 1)))
    if var <= 0.0:
        return 1.0
    z = (u - n1 * n2 / 2.0 - 0.5) / math.sqrt(var)
    return float(0.5 * math.erfc(z / math.sqrt(2.0)))


def _permute_within(rng: np.random.Generator, w: np.ndarray, uv: np.ndarray) -> np.ndarray:
    out = w.copy()
    for u in np.unique(uv):
        idx = np.nonzero(uv == u)[0]
        out[idx] = w[rng.permutation(idx)]
    return out


def user_label_null(s: Sequence[float], w: Sequence[bool], o: Sequence[bool] | None, users: Sequence[Hashable],
                    alpha: float, delta: float, *, seed: int = 0, n_runs: int = N_RUNS) -> dict[str, Any]:
    """The NW-vs-NP label null on the LTT items (module docstring). Returns a JSON-ready dict with the verdict
    ``"no commits"``, ``"fail"``, ``"partial"`` or ``"pass"``."""
    sv, wv, ov, uv = _arrays(s, w, o, users)
    if n_runs < 1:
        raise ValueError("n_runs must be >= 1")
    lam_real, k_real = certified(sv, wv, ov, alpha, delta)
    rng = np.random.default_rng([int(seed), _RNG_TAG])
    k_nw, k_np = [], []
    for _ in range(int(n_runs)):
        k_nw.append(certified(sv, _permute_within(rng, wv, uv), ov, alpha, delta)[1])
        k_np.append(certified(sv, wv[rng.permutation(wv.size)], ov, alpha, delta)[1])
    a_nw, a_np = np.array(k_nw), np.array(k_np)
    p_user = float((1 + np.sum(a_nw >= k_real)) / (n_runs + 1))
    p_leak = mwu_greater_p(a_nw, a_np)
    if k_real == 0:
        verdict = "no commits"
    elif p_user > P_USER_MAX:
        verdict = "fail"
    elif p_leak < P_LEAK_MAX:
        verdict = "partial"
    else:
        verdict = "pass"
    sizes = np.bincount(uv)
    return {
        "method": ("label null on the LTT items at the score level: labels permuted inside each user (NW) and over "
                   f"all LTT items (NP), {n_runs} runs each; the same LTT step as the guard"),
        "rule": (f"fail if the guard certifies commits and p_user > {P_USER_MAX:g} (the certificate is not above "
                 f"the within-user null); partial if p_leak < {P_LEAK_MAX:g} (NW certifies more than NP, "
                 "one-sided Mann-Whitney U); else pass"),
        "n_runs": int(n_runs), "n_items": int(sv.size), "n_users": int(sizes.size),
        "items_per_user": [int(sizes.min()), int(sizes.max())],
        "real_threshold": _jf(lam_real), "real_commits": int(k_real),
        "nw_commits_median": float(np.median(a_nw)), "np_commits_median": float(np.median(a_np)),
        "nw_commits_max": int(a_nw.max()), "np_commits_max": int(a_np.max()),
        "nw_certified_runs": int(np.sum(a_nw > 0)), "np_certified_runs": int(np.sum(a_np > 0)),
        "p_user": p_user, "p_leak": p_leak, "verdict": verdict,
    }


def per_user_thresholds(s: Sequence[float], w: Sequence[bool], o: Sequence[bool] | None,
                        users: Sequence[Hashable], alpha: float, delta: float, mode: str) -> dict[str, Any]:
    """Per-user LTT thresholds (module docstring). ``mode`` is ``"each"`` or ``"all"``. Raises ``ValueError`` if a
    user has fewer LTT items than :func:`~fidetype.trust.session_risk.min_ltt_items` needs at its level."""
    from fidetype.trust.session_risk import min_ltt_items

    if mode not in ("each", "all"):
        raise ValueError(f"mode must be 'each' or 'all', not {mode!r}")
    sv, wv, ov, uv = _arrays(s, w, o, users)
    k = int(np.unique(uv).size)
    d_u = float(delta) if mode == "each" else float(delta) / k
    n_min = min_ltt_items(alpha, d_u)
    sizes = np.bincount(uv)
    short = int(np.sum(sizes < n_min))
    if short:
        raise ValueError(
            f"user_bound={mode!r} needs at least {n_min} LTT items per user (alpha {alpha:g}, level {d_u:.4g}); "
            f"{short} of {k} users have fewer (smallest: {int(sizes.min())}). The LTT part is "
            "37.5 % of the items of each user on average: give more labelled utterances per user, or use "
            "user_bound='each' (level delta per user) instead of 'all'.")
    lams = []
    for u in range(k):
        m = uv == u
        lams.append(certified(sv[m], wv[m], ov[m], alpha, d_u)[0])
    lam = np.array(lams)
    return {"mode": mode, "n_users": k, "level_per_user": d_u, "n_min_per_user": int(n_min),
            "ltt_items_per_user": [int(sizes.min()), int(sizes.max())],
            "threshold_max": _jf(float(lam.max())), "users_never": int(np.sum(~np.isfinite(lam))),
            "_thresholds": lams}


def _jf(x: float) -> float | str:
    return float(x) if math.isfinite(x) else "inf"
