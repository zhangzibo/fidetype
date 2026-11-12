"""The benchmark scorer.

Input: per-trial outputs (from NeuralTextStream files, see
:mod:`fidetype.benchmark.submission`), the local truth, and the committed
split file. Output: one result dict (schema
``fidetype.benchmark.result/0.1``) that the leaderboard reads.

Metrics (all on the scored split, pooled over trials)
-----------------------------------------------------
``cer`` / ``wer``
    Edit distance of the top-1 text over the truth length (characters /
    words), pooled: sum of edits / sum of lengths.
``ewpm``
    Effective words per minute (``fidetype.eval.ewpm``): the documented
    simulated user (track :class:`~fidetype.benchmark.registry.UserModel`)
    answers each decision once; time = neural input time + the user's
    reading, selection and correction time. A sentence counts only if it
    ends exactly right.
``gaze_ewpm`` and ``ewpm_minus_gaze``
    The no-BCI reference: the user types every sentence with the fallback
    method. Every eWPM is reported next to it.
``wrong_commit_rate`` (marginal)
    Wrong commits / all trials. This is the quantity that CRC and LTT
    control.
``error_among_commits``
    Wrong commits / commits: how often a committed text is wrong. It can be
    high while the marginal rate is low, if the system rarely commits.
``commit_rate``
    Commits / all trials.
``silent_error_rate``
    Trials that end with a wrong text that the user did not correct.

Confidence intervals
--------------------
Percentile bootstrap (default B = 2000, seed 0) at the cluster unit of
the track: sentences x participants (two-way, crossed) for SpanishBCBL,
recording days for Brain-to-Text '25, participants for Toronto sEMG.
Repeated sentences and repeated people are not independent, so a trial
bootstrap gives CIs that are too narrow.

Controls
--------
``shuffled`` and ``zeros``: the same decoder on time-shuffled and on
all-zero input. A control passes if the top-1 CER on the control input is
higher than on the real input, with the lower CI bound of the paired gap
above 0. ``null_commit`` passes if the commit rate on zeros input is at
most :data:`NULL_COMMIT_MAX`. ``controls.passed`` is true only if all
three pass.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

import numpy as np

from fidetype.benchmark.registry import BENCHMARK_VERSION, Track, get_track, normalize
from fidetype.benchmark.submission import TrialOutput

RESULT_SCHEMA = "fidetype.benchmark.result/0.1"
NULL_COMMIT_MAX = 0.05
DEFAULT_B = 2000
CONFORMANCE_GATE = "trust-ready"


@dataclass
class TrialScore:
    id: str
    truth: str
    top1: str
    action: str
    edits_c: int
    n_c: int
    edits_w: int
    n_w: int
    committed: bool
    wrong_commit: bool
    silent_error: bool
    time_s: float
    words: int
    clusters: dict[str, str] = field(default_factory=dict)


def _seed(trial_id: str) -> int:
    return int(hashlib.sha256(trial_id.encode("utf-8")).hexdigest()[:8], 16)


def score_trials(track: Track | str, outputs: dict[str, TrialOutput], truth: dict[str, str],
                 clusters: dict[str, dict[str, str]], ids: Sequence[str]) -> list[TrialScore]:
    """Score every trial in ``ids`` (the scored split, in split order)."""
    from fidetype.eval.ewpm import correct_words_strict, SentenceRecord
    from fidetype.eval.metrics import edit_distance
    from fidetype.interact.simulated_user import SimulatedUser
    from fidetype.trust.policy import Action, Decision

    t = get_track(track) if isinstance(track, str) else track
    user = SimulatedUser(t.user_model.user_config())
    out = []
    for tid in ids:
        if tid not in outputs:
            raise KeyError(f"no output for trial {tid!r}")
        if tid not in truth:
            raise KeyError(f"no truth for trial {tid!r}")
        o = outputs[tid]
        ref = normalize(truth[tid], t.normalizer)
        texts = [normalize(x, t.normalizer) for x in o.texts]
        top1 = texts[0] if texts else ""
        if o.action == "commit":
            d = Decision(Action.COMMIT, (top1,))
        elif o.action == "offer":
            d = Decision(Action.OFFER, tuple(dict.fromkeys(texts[: o.offer_k])))
        else:
            d = Decision(Action.ABSTAIN)
        oc = user.respond(d, ref, can_repeat=False, rng=np.random.default_rng(_seed(tid)))
        time_s = user.typing_time(ref) + oc.time_s
        rec = SentenceRecord(ref, oc.final_text, oc.communicated, time_s)
        out.append(TrialScore(
            id=tid, truth=ref, top1=top1, action=o.action,
            edits_c=edit_distance(ref, top1), n_c=len(ref),
            edits_w=edit_distance(ref.split(), top1.split()), n_w=len(ref.split()),
            committed=o.action == "commit", wrong_commit=bool(oc.wrong_commit), silent_error=bool(oc.silent_error),
            time_s=float(time_s), words=correct_words_strict(rec), clusters=dict(clusters.get(tid, {})),
        ))
    return out


# ---------------------------------------------------------------------------
# Arrays, weighted metrics and the cluster bootstrap
# ---------------------------------------------------------------------------


def arrays(scores: Sequence[TrialScore], gaze_cpm: float) -> dict[str, np.ndarray]:
    nchar = np.array([s.n_c for s in scores], float)
    return {
        "ec": np.array([s.edits_c for s in scores], float), "nc": nchar,
        "ew": np.array([s.edits_w for s in scores], float), "nw": np.array([s.n_w for s in scores], float),
        "w": np.array([s.words for s in scores], float), "t": np.array([s.time_s for s in scores], float),
        "wc": np.array([s.wrong_commit for s in scores], float),
        "cm": np.array([s.committed for s in scores], float),
        "se": np.array([s.silent_error for s in scores], float),
        "gt": nchar * 60.0 / gaze_cpm,
    }


def _ratio(num: float, den: float) -> float:
    return float(num / den) if den > 0 else math.nan


def weighted_metrics(a: dict[str, np.ndarray], wt: np.ndarray | None = None) -> dict[str, float]:
    """All pooled metrics under trial weights ``wt`` (None = all 1)."""
    wt = np.ones(len(next(iter(a.values()))), float) if wt is None else wt
    s = lambda k: float((a[k] * wt).sum())  # noqa: E731
    n = float(wt.sum())
    m: dict[str, float] = {}
    if "ec" in a:
        m["cer"] = _ratio(s("ec"), s("nc"))
        m["wer"] = _ratio(s("ew"), s("nw"))
    if "w" in a:
        m["ewpm"] = 60.0 * _ratio(s("w"), s("t"))
        m["gaze_ewpm"] = 60.0 * _ratio(s("nw"), s("gt")) if "nw" in a and "gt" in a else math.nan
        m["ewpm_minus_gaze"] = m["ewpm"] - m["gaze_ewpm"]
    if "wc" in a:
        m["wrong_commit_rate"] = _ratio(s("wc"), n)
        m["commit_rate"] = _ratio(s("cm"), n)
        m["error_among_commits"] = _ratio(s("wc"), s("cm"))
    if "se" in a:
        m["silent_error_rate"] = _ratio(s("se"), n)
    return m


def cluster_codes(clusters: Sequence[dict[str, str]], key: str) -> np.ndarray:
    labels = [c.get(key, "") for c in clusters]
    if any(x == "" for x in labels):
        raise ValueError(f"some trials lack the cluster label {key!r}")
    return np.unique(np.array(labels), return_inverse=True)[1]


def bootstrap_weights(rng: np.random.Generator, unit: str, clusters: Sequence[dict[str, str]]) -> Callable[[], np.ndarray]:
    """Return a function that draws one vector of bootstrap trial weights."""
    n = len(clusters)
    if unit == "trial":
        return lambda: np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
    if unit.startswith("two_way:"):
        ka, kb = unit.split(":", 1)[1].split(",")
        ca, cb = cluster_codes(clusters, ka), cluster_codes(clusters, kb)
        na, nb = int(ca.max()) + 1, int(cb.max()) + 1

        def draw2() -> np.ndarray:
            wa = np.bincount(rng.integers(0, na, na), minlength=na)
            wb = np.bincount(rng.integers(0, nb, nb), minlength=nb)
            return (wa[ca] * wb[cb]).astype(float)

        return draw2
    c = cluster_codes(clusters, unit)
    k = int(c.max()) + 1

    def draw() -> np.ndarray:
        return np.bincount(rng.integers(0, k, k), minlength=k)[c].astype(float)

    return draw


def bootstrap_ci(fn: Callable[[np.ndarray], dict[str, float]], unit: str, clusters: Sequence[dict[str, str]],
                 B: int = DEFAULT_B, seed: int = 0, level: float = 0.95) -> dict[str, list[float]]:
    """Percentile CIs of every metric that ``fn(weights)`` returns."""
    rng = np.random.default_rng(seed)
    draw = bootstrap_weights(rng, unit, clusters)
    reps: dict[str, list[float]] = {}
    for _ in range(B):
        w = draw()
        if w.sum() == 0:
            continue
        for k, v in fn(w).items():
            reps.setdefault(k, []).append(v)
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    out = {}
    for k, v in reps.items():
        x = np.array(v, float)
        x = x[np.isfinite(x)]
        out[k] = [float(np.percentile(x, lo)), float(np.percentile(x, hi))] if x.size else [math.nan, math.nan]
    return out


def metric_block(point: dict[str, float], ci: dict[str, list[float]]) -> dict[str, dict[str, Any]]:
    return {k: {"value": v, "ci": ci.get(k)} for k, v in point.items()}


# ---------------------------------------------------------------------------
# Controls and guarantee
# ---------------------------------------------------------------------------


def control_block(real: Sequence[TrialScore], controls: dict[str, Sequence[TrialScore] | None], unit: str,
                  B: int = DEFAULT_B, seed: int = 0) -> dict[str, Any]:
    """Paired CER gaps (control - real) and the null-input commit rate."""
    out: dict[str, Any] = {}
    clusters = [s.clusters for s in real]
    ec = np.array([s.edits_c for s in real], float)
    nc = np.array([s.n_c for s in real], float)
    for kind in ("shuffled", "zeros"):
        ctl = controls.get(kind)
        if not ctl:
            out[kind] = {"status": "missing"}
            continue
        by = {s.id: s for s in ctl}
        if any(s.id not in by for s in real):
            out[kind] = {"status": "incomplete", "n": len(ctl)}
            continue
        cc = np.array([by[s.id].edits_c for s in real], float)

        def gap(w: np.ndarray) -> dict[str, float]:
            den = float((nc * w).sum())
            return {"cer_control": float((cc * w).sum()) / den, "cer_gap": float(((cc - ec) * w).sum()) / den}

        pt = gap(np.ones_like(nc))
        ci = bootstrap_ci(gap, unit, clusters, B=B, seed=seed + 11)
        ok = bool(ci["cer_gap"][0] > 0)
        out[kind] = {"status": "pass" if ok else "fail", "cer_control": pt["cer_control"],
                     "cer_gap": pt["cer_gap"], "cer_gap_ci": ci["cer_gap"]}
    z = controls.get("zeros")
    if z:
        rate = float(np.mean([s.committed for s in z]))
        out["null_commit"] = {"status": "pass" if rate <= NULL_COMMIT_MAX else "fail", "commit_rate_zeros": rate,
                              "max": NULL_COMMIT_MAX}
    else:
        out["null_commit"] = {"status": "missing"}
    st = [out[k]["status"] for k in ("shuffled", "zeros", "null_commit")]
    out["passed"] = all(s == "pass" for s in st)
    return out


def guarantee_block(g: dict[str, Any], metrics: dict[str, dict[str, Any]], n_cal_split: int | None) -> dict[str, Any]:
    """Echo the declared guarantee and compare it with the measured test rate."""
    m = g.get("method", "none")
    if m == "none":
        return {"method": "none"}
    wc = metrics.get("wrong_commit_rate", {})
    out = {k: g.get(k) for k in ("method", "alpha", "delta", "n_cal", "scope", "calibration_split")}
    out["measured_wrong_commit"] = wc.get("value")
    out["measured_wrong_commit_ci"] = wc.get("ci")
    a = g.get("alpha")
    if isinstance(a, (int, float)) and wc.get("value") is not None:
        out["met_on_test"] = bool(wc["value"] <= a)
    if n_cal_split is not None and isinstance(g.get("n_cal"), int) and g["n_cal"] > n_cal_split:
        out["warning"] = f"n_cal {g['n_cal']} is larger than the calibration split ({n_cal_split})"
    return out


# ---------------------------------------------------------------------------
# One call: score a set of outputs
# ---------------------------------------------------------------------------


def build_result(track: Track | str, real: Sequence[TrialScore], *, decoder: dict[str, Any], policy: dict[str, Any],
                 guarantee: dict[str, Any] | None = None, controls: dict[str, Sequence[TrialScore] | None] | None = None,
                 conformance: dict[str, Any] | None = None, scored_from: str = "stream-submission",
                 sources: Sequence[str] = (), notes: Sequence[str] = (), B: int = DEFAULT_B, seed: int = 0,
                 n_cal_split: int | None = None, entry_id: str | None = None) -> dict[str, Any]:
    """Score trials and return the result dict of one leaderboard entry."""
    t = get_track(track) if isinstance(track, str) else track
    a = arrays(real, t.user_model.gaze_chars_per_min)
    clusters = [s.clusters for s in real]
    point = weighted_metrics(a)
    ci = bootstrap_ci(lambda w: weighted_metrics(a, w), t.ci_unit, clusters, B=B, seed=seed)
    metrics = metric_block(point, ci)
    res = {
        "schema": RESULT_SCHEMA,
        "benchmark_version": BENCHMARK_VERSION,
        "entry_id": entry_id or f"{t.slug}/{decoder.get('name', 'decoder')}/{policy.get('name', 'policy')}",
        "track": t.slug,
        "decoder": decoder,
        "policy": policy,
        "scored_from": scored_from,
        "sources": list(sources),
        "n_trials": len(real),
        "ci": {"unit": t.ci_unit, "method": "percentile cluster bootstrap", "B": B, "seed": seed, "level": 0.95},
        "metrics": metrics,
        "controls": control_block(real, controls or {}, t.ci_unit, B=B, seed=seed),
        "guarantee": guarantee_block(guarantee or {"method": "none"}, metrics, n_cal_split),
        "conformance": conformance or {"level": "unknown"},
        "user_model": {"name": t.user_model.name, "config": t.user_model.config,
                       "gaze_chars_per_min": t.user_model.gaze_chars_per_min},
        "notes": list(notes),
    }
    return res


def to_jsonable(o: Any) -> Any:
    """Replace NaN / inf with None (JSON has no NaN)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return to_jsonable(float(o))
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


__all__ = ["RESULT_SCHEMA", "NULL_COMMIT_MAX", "TrialScore", "score_trials", "arrays", "weighted_metrics",
           "bootstrap_ci", "control_block", "guarantee_block", "build_result", "to_jsonable", "asdict"]
