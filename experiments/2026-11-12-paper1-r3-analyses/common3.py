"""Shared code for the Paper 1 round-3 analyses (CPU only).

Re-uses the round-1 module ``common.py`` (conditions, item tables, metrics,
bootstraps) and adds:

- frame-temperature snapping (``install_snap``): the frame temperature
  fitted on a fit-A set is rounded to 0.01 so that decodes can be shared
  between repeated splits. The largest change is 0.005 (0.13 % of T = 3.8
  on B2T; 0.4 % of T = 1.25 on sEMG). The fitted and the used value are
  both recorded.
- a decoder router: one disk decode cache per (snapped) frame temperature.
- selective-risk controllers: SGR (Geifman & El-Yaniv 2017, Algorithm 1)
  and LTT on the error among commits (Bonferroni over a fixed grid).
- Clopper-Pearson bounds, Holm correction, exact sign / sign-flip tests.
"""

from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R1 = HERE.parent / "2026-11-12-paper1-r1-analyses"
sys.path.insert(0, str(R1))
import common as C  # noqa: E402

from fidetype.eval import harness as H  # noqa: E402
from fidetype.trust.risk_control import _log_binom_cdf  # noqa: E402

REPO = C.REPO
CACHE3 = Path("C:/Users/zhang/bci-data/cache/paper1-r3")
CACHE3.mkdir(parents=True, exist_ok=True)
ALPHA, DELTA = C.ALPHA, C.DELTA
UNIFIED_SEED = 20261112
UNIFIED_B = 2000


# ---------------------------------------------------------------------------
# Frame temperature snapping + per-temperature decode caches
# ---------------------------------------------------------------------------

class TState:
    fitted: float | None = None
    used: float | None = None
    step: float = 0.01


_orig_fit_frame = H.fit_frame_temperature


def snap(t: float, step: float | None = None) -> float:
    step = step or TState.step
    return round(round(t / step) * step, 6)


def snapped_fit_frame_temperature(streams, truths):
    sc = _orig_fit_frame(streams, truths)
    TState.fitted = float(sc.temperature)
    sc.temperature = snap(sc.temperature)
    TState.used = float(sc.temperature)
    return sc


def install_snap(step: float = 0.01) -> None:
    TState.step = step
    H.fit_frame_temperature = snapped_fit_frame_temperature


def fit_T(streams, truths) -> tuple[float, float]:
    sc = _orig_fit_frame(streams, truths)
    t = float(sc.temperature)
    return t, snap(t)


class TRouter:
    """``fn(stream)`` dispatch to one DiskCachedDecoder per snapped frame temperature (TState.used)."""

    def __init__(self, fn, tag: str, save: bool = True):
        self.fn, self.tag, self.save_ok = fn, tag, save
        self.d: dict = {}
        self.__name__ = f"router_{tag}"

    def get(self, T: float):
        k = f"{T:.2f}"
        if k not in self.d:
            dc = object.__new__(C.DiskCachedDecoder)
            dc.fn, dc.tag, dc.new = self.fn, f"{self.tag}-T{k}", 0
            dc.path = CACHE3 / f"decode-{self.tag}-T{k}.pkl"
            dc.__name__ = dc.tag
            dc.d = {}
            if dc.path.exists():
                try:
                    dc.d = pickle.loads(dc.path.read_bytes())
                except Exception:  # noqa: BLE001
                    dc.d = {}
            self.d[k] = dc
        return self.d[k]

    def __call__(self, stream):
        T = TState.used if TState.used is not None else 1.0
        return self.get(T)(stream)

    def new_count(self) -> int:
        return sum(c.new for c in self.d.values())

    def save(self) -> None:
        if self.save_ok:
            for c in self.d.values():
                c.save()


# ---------------------------------------------------------------------------
# Item-table helpers
# ---------------------------------------------------------------------------

KEYS = ("loss_c", "loss_f", "wc_c", "wc_f", "time_c", "time_f", "words_c", "words_f")


def arr(tab: dict) -> dict:
    out = {k: np.asarray(tab[k], float) for k in KEYS}
    out["s"] = np.array([C.fnum(x) for x in tab["score"]])
    out["c"], out["f"] = out["loss_c"], out["loss_f"]
    out["lam_old"] = float(C.fnum(tab["lam_old"]))
    return out


def take(a: dict, idx) -> dict:
    idx = np.asarray(idx)
    out = {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in a.items()}
    out["c"], out["f"] = out["loss_c"], out["loss_f"]
    return out


def outcome(a: dict, lam: float, rows=None) -> dict:
    b = a if rows is None else take(a, rows)
    on = b["s"] >= lam
    wc = np.where(on, b["wc_c"], b["wc_f"])
    t = np.where(on, b["time_c"], b["time_f"])
    w = np.where(on, b["words_c"], b["words_f"])
    ncom = int(on.sum())
    nerr = float((wc * on).sum())
    return {"n": int(on.size), "wrong_commit": float(wc.mean()), "commit_rate": float(on.mean()), "n_commit": ncom,
            "n_commit_wrong": nerr, "error_among_commits": (nerr / ncom) if ncom else float("nan"),
            "ewpm": float(60.0 * w.sum() / t.sum())}


def crc(a: dict, alpha: float = ALPHA):
    return C.crc_threshold(a["s"], a["c"], alpha, a["f"])


def ltt(a: dict, alpha: float = ALPHA, delta: float = DELTA):
    return C.ltt_threshold(a["s"], a["c"], alpha, delta, a["f"])


def cal_bound(a: dict, lam: float, B: float = 1.0) -> float:
    """CRC bound (n R_hat(lam) + B) / (n + 1) on calibration data at threshold lam."""
    on = a["s"] >= lam
    r = float(np.where(on, a["c"], a["f"]).mean())
    n = on.size
    return (n * r + B) / (n + 1)


def crc_active(a: dict, lam: float) -> bool:
    """CRC constraint active: the CRC threshold excludes at least one eligible calibration item."""
    fin = a["s"][np.isfinite(a["s"])]
    if not fin.size:
        return False
    if not math.isfinite(lam):
        return True
    return bool(np.any(fin < lam))


def same_decisions(a: dict, l1: float, l2: float) -> bool:
    return bool(np.array_equal(a["s"] >= l1, a["s"] >= l2))


# ---------------------------------------------------------------------------
# Selective-risk controllers
# ---------------------------------------------------------------------------

def binom_upper(k: int, n: int, delta: float) -> float:
    """Exact one-sided upper bound b with P(Bin(n, b) <= k) = delta (Clopper-Pearson)."""
    from scipy.stats import beta
    if n <= 0 or k >= n:
        return 1.0
    return float(beta.ppf(1 - delta, k + 1, n - k))


def sgr(scores, errors, r_star: float, delta: float = DELTA) -> dict:
    """Selection with guaranteed risk (Geifman & El-Yaniv 2017, Alg. 1).

    ``scores``: confidence per calibration item (-inf = never committed by
    the other policy rules); ``errors``: 1 if a commit of the item is wrong.
    Binary search over the sorted finite scores, k = ceil(log2 m) steps,
    Bonferroni delta / k, exact binomial bound. Returns the threshold
    (commit if s >= theta; +inf = never commit) and its bound.
    """
    s = np.asarray(scores, float)
    e = np.asarray(errors, float)
    fin = np.isfinite(s)
    sv, ev = s[fin], e[fin]
    m = sv.size
    if m == 0:
        return {"threshold": math.inf, "feasible": False, "bound": None, "n_selected": 0, "k": 0}
    o = np.argsort(sv, kind="stable")
    sv, ev = sv[o], ev[o]
    k = max(1, int(math.ceil(math.log2(m)))) if m > 1 else 1
    lo, hi = 0, m - 1
    best = None
    for _ in range(k):
        z = int(math.ceil((lo + hi) / 2))
        theta = sv[z]
        acc = sv >= theta
        n_acc, n_err = int(acc.sum()), int(ev[acc].sum())
        b = binom_upper(n_err, n_acc, delta / k)
        if b < r_star:
            best = (float(theta), b, n_acc, n_err)
            hi = z
        else:
            lo = z
        if hi - lo <= 0:
            break
    if best is None:
        return {"threshold": math.inf, "feasible": False, "bound": None, "n_selected": 0, "k": k}
    return {"threshold": best[0], "feasible": True, "bound": best[1], "n_selected": best[2], "n_err": best[3], "k": k}


LTT_SEL_GRID = tuple(float(x) for x in np.round(np.arange(0.05, 1.0001, 0.05), 2))


def ltt_selective(scores, errors, beta_: float, delta: float = DELTA, grid=LTT_SEL_GRID) -> dict:
    """LTT on the error among commits. H0(lam): P(wrong | s >= lam) > beta. Exact binomial p-value
    conditional on the number of commits; Bonferroni over the fixed grid; the smallest rejected lam."""
    s = np.asarray(scores, float)
    e = np.asarray(errors, float)
    rej = []
    for lam in grid:
        on = s >= lam
        n = int(on.sum())
        if n == 0:
            continue
        p = math.exp(_log_binom_cdf(int(e[on].sum()), n, beta_))
        if p <= delta / len(grid):
            rej.append(float(lam))
    if not rej:
        return {"threshold": math.inf, "feasible": False}
    return {"threshold": min(rej), "feasible": True}


# ---------------------------------------------------------------------------
# Small-sample inference
# ---------------------------------------------------------------------------

def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    from scipy.stats import beta
    a = 1 - conf
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def upper_one_sided(k: int, n: int, conf: float = 0.95) -> float:
    from scipy.stats import beta
    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, run = {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def sign_test(d) -> dict:
    """Exact two-sided sign test on per-cluster differences (zeros dropped)."""
    from scipy.stats import binomtest
    d = np.asarray(d, float)
    pos, neg = int((d > 1e-12).sum()), int((d < -1e-12).sum())
    n = pos + neg
    p = float(binomtest(pos, n, 0.5).pvalue) if n else 1.0
    return {"positive": pos, "negative": neg, "zero": int(d.size - n), "p_two_sided": p}


def perm_test_clusters(d, reps: int = 20000, seed: int = UNIFIED_SEED) -> dict:
    """Sign-flip permutation test of the mean per-cluster difference (exact if 2^k <= reps)."""
    import itertools
    d = np.asarray(d, float)
    k = d.size
    obs = float(d.mean())
    if 2 ** k <= reps:
        signs = np.array(list(itertools.product([-1.0, 1.0], repeat=k)))
    else:
        signs = np.random.default_rng(seed).choice([-1.0, 1.0], size=(reps, k))
    null = (signs * d).mean(1)
    p = float(np.mean(np.abs(null) >= abs(obs) - 1e-12))
    return {"mean_diff": obs, "p_two_sided": p, "n_clusters": k, "exact": bool(2 ** k <= reps)}


def summ(v) -> dict:
    v = np.asarray(v, float)
    f = v[np.isfinite(v)]
    if not f.size:
        return {"mean": None, "sd": None, "p05": None, "p95": None, "n_finite": 0}
    return {"mean": float(f.mean()), "sd": float(f.std(ddof=1)) if f.size > 1 else 0.0,
            "p05": float(np.quantile(f, 0.05)), "p95": float(np.quantile(f, 0.95)),
            "min": float(f.min()), "max": float(f.max()), "n_finite": int(f.size)}
