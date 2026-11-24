"""A1 trust gate, null inputs, metrics and pass rules (plan.md). CPU only; NumPy / SciPy.

Our own code, Apache-2.0. The gate reuses the Fidetype trust layer unchanged:

* temperature: :class:`fidetype.trust.calibration.TemperatureScaler`
* COMMIT threshold: :func:`fidetype.trust.precision_bound.precision_ltt` (precision LTT, order / certify split)
* OFFER sets: :func:`fidetype.trust.conformal.conformal_quantile` with the LAC score ``1 - p``
* bounds: :func:`fidetype.utils.binomial.cp_upper`
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

from fidetype.trust.calibration import TemperatureScaler, softmax
from fidetype.trust.conformal import conformal_quantile
from fidetype.trust.precision_bound import DEFAULT_COMMIT_P_GRID, PrecisionItem, precision_ltt
from fidetype.utils.binomial import cp_upper

ALPHA = 0.10
DELTA = 0.10
MAX_OFFER = 10
MIN_COMMIT_RATE = 0.05
V1_MIN_TOP1 = 0.10
BOOT = 10_000

COMMIT, OFFER, ABSTAIN = "commit", "offer", "abstain"


# --- scores --------------------------------------------------------------------------------------------------------

def _unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def cosine_shared(emb: np.ndarray, gallery_feats: np.ndarray) -> np.ndarray:
    """[N, D] x [G, D] -> [N, G] cosine similarities (one gallery for all units, as on test)."""
    return _unit(emb) @ _unit(gallery_feats).T


def cosine_per_unit(emb: np.ndarray, img_feats: np.ndarray, galleries: np.ndarray) -> np.ndarray:
    """Per-unit galleries ([N, G] image indices) -> [N, G] cosines. Column 0 is the true image (a1data)."""
    e = _unit(emb)
    f = _unit(img_feats)
    return np.einsum("nd,ngd->ng", e, f[galleries])


def topk_acc(sim: np.ndarray, true_col: np.ndarray, k: int) -> float:
    rank = (sim > sim[np.arange(len(sim)), true_col][:, None]).sum(axis=1)
    return float(np.mean(rank < k))


def margin(sim: np.ndarray) -> np.ndarray:
    s = np.sort(sim, axis=1)
    return s[:, -1] - s[:, -2]


# --- gate ----------------------------------------------------------------------------------------------------------

@dataclass
class Gate:
    temperature: float
    commit_p: float | None  # None: never commit
    conf_q: float  # LAC threshold: candidate j is in the set if 1 - p_j <= conf_q
    alpha: float = ALPHA
    delta: float = DELTA
    max_offer: int = MAX_OFFER
    ltt: dict | None = None
    n_cal: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["conf_q"] = float(self.conf_q) if math.isfinite(self.conf_q) else "inf"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Gate":
        d = dict(d)
        d["conf_q"] = math.inf if d["conf_q"] == "inf" else float(d["conf_q"])
        return cls(**d)

    def posteriors(self, sim: np.ndarray) -> np.ndarray:
        return softmax(np.asarray(sim, dtype=np.float64) / self.temperature, axis=1)

    def decide(self, sim: np.ndarray) -> dict[str, np.ndarray]:
        """Per unit: action, top-1 column, p_top1, set size and set membership mask [N, G]."""
        p = self.posteriors(sim)
        top = p.argmax(axis=1)
        p1 = p[np.arange(len(p)), top]
        in_set = (1.0 - p) <= self.conf_q + 1e-12
        size = in_set.sum(axis=1)
        commit = np.zeros(len(p), dtype=bool) if self.commit_p is None else p1 >= self.commit_p
        offer = ~commit & (size <= self.max_offer) & (size >= 1)
        action = np.where(commit, COMMIT, np.where(offer, OFFER, ABSTAIN))
        return {"action": action, "top": top, "p_top1": p1, "set_size": size, "in_set": in_set}


def fit_temperature(sim_val: np.ndarray, true_col: np.ndarray) -> float:
    return float(TemperatureScaler().fit(sim_val, true_col).temperature)


def fit_gate(sim_order: np.ndarray, true_order: np.ndarray, sim_cert: np.ndarray, true_cert: np.ndarray,
             temperature: float, alpha: float = ALPHA, delta: float = DELTA, max_offer: int = MAX_OFFER,
             grid: Sequence[float] = DEFAULT_COMMIT_P_GRID) -> Gate:
    """COMMIT threshold by precision LTT (order -> certify); conformal threshold on order + certify units."""
    g = Gate(temperature, None, math.inf, alpha, delta, max_offer)

    def items(sim: np.ndarray, true: np.ndarray) -> list[PrecisionItem]:
        p = g.posteriors(sim)
        top = p.argmax(axis=1)
        return [PrecisionItem(True, float(p[i, top[i]]), bool(top[i] != true[i])) for i in range(len(p))]

    res = precision_ltt(items(sim_order, true_order), items(sim_cert, true_cert), grid,
                        target_precision=1.0 - alpha, delta=delta)
    sim_all = np.concatenate([sim_order, sim_cert])
    true_all = np.concatenate([true_order, true_cert])
    p_all = g.posteriors(sim_all)
    scores = 1.0 - p_all[np.arange(len(p_all)), true_all]
    g.commit_p = None if res.selected is None else float(res.selected)
    g.conf_q = float(conformal_quantile(scores, alpha))
    g.ltt = res.to_dict()
    g.n_cal = int(len(sim_all))
    return g


# --- null inputs ---------------------------------------------------------------------------------------------------

def null_trial_shuffled(units: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """N1: channel c of null unit i is channel c of a random unit (independent per channel)."""
    n, c = units.shape[:2]
    src = rng.integers(0, n, size=(n, c))
    return units[src, np.arange(c)[None, :]]


def null_time_reversed(units: np.ndarray) -> np.ndarray:
    """N2: the time axis reversed."""
    return np.ascontiguousarray(units[..., ::-1])


def null_phase_randomised(units: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """N3: FFT phase randomisation, the same random phases for all channels of a unit (keeps spectra, covariance)."""
    x = np.asarray(units, dtype=np.float64)
    t = x.shape[-1]
    f = np.fft.rfft(x, axis=-1)
    ph = rng.uniform(0, 2 * np.pi, size=(x.shape[0], 1, f.shape[-1]))
    ph[..., 0] = 0.0
    if t % 2 == 0:
        ph[..., -1] = 0.0
    return np.fft.irfft(f * np.exp(1j * ph), n=t, axis=-1).astype(np.float32)


def make_nulls(units: np.ndarray, subject: int) -> dict[str, np.ndarray]:
    return {
        "N1": null_trial_shuffled(units, np.random.default_rng([subject, 7, 1])),
        "N2": null_time_reversed(units),
        "N3": null_phase_randomised(units, np.random.default_rng([subject, 7, 3])),
    }


# --- metrics -------------------------------------------------------------------------------------------------------

def cluster_boot_upper(num: np.ndarray, den: np.ndarray, cluster: np.ndarray, n_boot: int = BOOT, seed: int = 0,
                       q: float = 0.95) -> float:
    """Image-cluster bootstrap upper quantile of sum(num) / sum(den). Resamples clusters with replacement."""
    ids, inv = np.unique(cluster, return_inverse=True)
    sn = np.bincount(inv, weights=num, minlength=len(ids))
    sd = np.bincount(inv, weights=den, minlength=len(ids))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(n_boot, len(ids)))
    tn, td = sn[idx].sum(axis=1), sd[idx].sum(axis=1)
    ratio = np.where(td > 0, tn / np.maximum(td, 1e-12), 0.0)
    return float(np.quantile(ratio, q))


def gate_metrics(dec: dict[str, np.ndarray], true_col: np.ndarray | None, cluster: np.ndarray,
                 n_boot: int = BOOT) -> dict[str, Any]:
    """Counts, rates and bounds. ``true_col`` None (a null input): every commit counts as wrong."""
    n = len(dec["action"])
    commit = dec["action"] == COMMIT
    wrong = commit if true_col is None else commit & (dec["top"] != true_col)
    k, c = int(wrong.sum()), int(commit.sum())
    out: dict[str, Any] = {
        "units": n, "commits": c, "wrong_commits": k,
        "commit_rate": c / n if n else 0.0,
        "commit_rate_cp95_upper": cp_upper(c, n, 0.05),
        "commit_rate_boot95_upper": cluster_boot_upper(commit.astype(float), np.ones(n), cluster, n_boot),
        "wrong_rate_precision": k / c if c else 0.0,
        "wrong_rate_precision_cp95_upper": cp_upper(k, c, 0.05),
        "wrong_rate_precision_boot95_upper": cluster_boot_upper(wrong.astype(float), commit.astype(float),
                                                                cluster, n_boot) if c else 1.0,
        "wrong_rate_marginal": k / n if n else 0.0,
        "offer_rate": float(np.mean(dec["action"] == OFFER)),
        "abstain_rate": float(np.mean(dec["action"] == ABSTAIN)),
        "mean_set_size": float(np.mean(dec["set_size"])),
    }
    if true_col is not None:
        cov = dec["in_set"][np.arange(n), true_col]
        out["coverage"] = float(np.mean(cov))
        out["offer_coverage"] = float(np.mean(cov[dec["action"] == OFFER])) if np.any(dec["action"] == OFFER) else None
    return out


def per_cluster_mean(x: np.ndarray, cluster: np.ndarray) -> np.ndarray:
    ids, inv = np.unique(cluster, return_inverse=True)
    return np.bincount(inv, weights=x, minlength=len(ids)) / np.bincount(inv, minlength=len(ids))


def set_size_test(size_real: np.ndarray, size_null: np.ndarray, cluster: np.ndarray) -> dict[str, Any]:
    """(iii): per image mean set size, real < null, one-sided Wilcoxon signed-rank."""
    from scipy.stats import wilcoxon

    a = per_cluster_mean(size_real.astype(float), cluster)
    b = per_cluster_mean(size_null.astype(float), cluster)
    if np.allclose(a, b):
        p = 1.0
    else:
        p = float(wilcoxon(a, b, alternative="less").pvalue)
    return {"n_pairs": int(len(a)), "mean_real": float(a.mean()), "mean_null": float(b.mean()), "p_one_sided": p}


# --- rules ---------------------------------------------------------------------------------------------------------

def rule_null(m: dict, alpha: float = ALPHA) -> bool:
    return (m["commit_rate"] <= alpha and m["commit_rate_cp95_upper"] <= 2 * alpha
            and m["commit_rate_boot95_upper"] <= 2 * alpha)


def rule_error(m: dict, alpha: float = ALPHA) -> bool:
    """Error part of (ii). With no commits there is no wrong commit: it passes (the commit part then fails: B)."""
    if m["commits"] == 0:
        return True
    return (m["wrong_rate_precision"] <= alpha and m["wrong_rate_precision_cp95_upper"] <= 2 * alpha
            and m["wrong_rate_precision_boot95_upper"] <= 2 * alpha)


def rule_commits(m: dict) -> bool:
    return m["commit_rate"] >= MIN_COMMIT_RATE


def subject_verdict(v1_top1: float, real: dict, nulls: dict[str, dict], sets: dict, alpha: float = ALPHA) -> dict:
    v1 = v1_top1 >= V1_MIN_TOP1
    r_i = all(rule_null(m, alpha) for m in nulls.values())
    r_ii_err = rule_error(real, alpha)
    r_ii_com = rule_commits(real)
    r_iii = sets["p_one_sided"] < 0.01
    v2 = real.get("coverage", 0.0) >= 1 - 2 * alpha
    if not v1:
        oc = "N"
    elif not r_i or not r_ii_err:
        oc = "C"
    elif not r_ii_com:
        oc = "B"
    elif not r_iii:
        oc = "D"
    else:
        oc = "A"
    return {"V1": v1, "i": r_i, "ii_error": r_ii_err, "ii_commits": r_ii_com, "ii": r_ii_err and r_ii_com,
            "iii": r_iii, "V2": v2, "outcome": oc}


def overall_outcome(per_subject: dict[str, dict]) -> str:
    """A only if A on both subjects; A-one if A on one; else the worst of N > C > B > D (plan.md)."""
    ocs = [v["outcome"] for v in per_subject.values()]
    n_a = sum(o == "A" for o in ocs)
    if n_a == len(ocs) and ocs:
        return "A"
    for o in ("C", "N"):
        if o in ocs:
            return o if n_a == 0 else f"A-one ({o} on the other)"
    if n_a:
        return "A-one"
    return "B" if "B" in ocs else "D"


def rule_drift(early: dict, late: dict, alpha: float = ALPHA) -> bool:
    return all(m["commits"] == 0 or (m["wrong_rate_precision"] <= alpha
                                     and m["wrong_rate_precision_cp95_upper"] <= 2 * alpha) for m in (early, late))


# --- R2: k-means on concept text embeddings ------------------------------------------------------------------------

def kmeans(x: np.ndarray, k: int = 8, seed: int = 0, iters: int = 100) -> np.ndarray:
    """Spherical k-means (cosine), k-means++ init. Returns labels."""
    x = _unit(x)
    rng = np.random.default_rng(seed)
    c = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = 1.0 - np.max(x @ np.array(c).T, axis=1)
        pr = np.maximum(d, 0) ** 2
        c.append(x[rng.choice(len(x), p=pr / pr.sum())])
    cent = np.array(c)
    lab = np.zeros(len(x), dtype=np.int64)
    for it in range(iters):
        new = np.argmax(x @ cent.T, axis=1)
        if it and np.array_equal(new, lab):
            break
        lab = new
        for j in range(k):
            if np.any(lab == j):
                cent[j] = _unit(x[lab == j].mean(axis=0))
    return lab


def pooled_counts(ms: Sequence[dict]) -> dict:
    c = sum(m["commits"] for m in ms)
    k = sum(m["wrong_commits"] for m in ms)
    n = sum(m["units"] for m in ms)
    return {"units": n, "commits": c, "wrong_commits": k, "commit_rate": c / n if n else 0.0,
            "wrong_rate_precision": k / c if c else 0.0, "wrong_rate_precision_cp95_upper": cp_upper(k, c, 0.05)}


def rule_cluster(pooled: dict, alpha: float = ALPHA) -> bool:
    if pooled["commits"] == 0:
        return True
    return pooled["wrong_rate_precision"] <= alpha and pooled["wrong_rate_precision_cp95_upper"] <= 2 * alpha
