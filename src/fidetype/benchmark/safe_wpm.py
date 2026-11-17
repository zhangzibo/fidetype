"""Safe WPM: words per minute of committed, correct text at a certified wrong-commit rate (P14-05).

Definition (``safe-wpm/0.1``; full text: ``docs/safe-wpm.md``)
--------------------------------------------------------------
A session has N trials (intended sentences) y_1 .. y_N. Per trial i:

- ``neural_s_i``: the time of the neural input, in seconds. Use the
  measured trial duration where the dataset has it. Otherwise use the
  track model ``len(y_i) * 60 / chars_per_min`` and say so (``timing``).
- ``committed_i``: the trust policy COMMITs a text (no user action).
- ``correct_i``: the committed text equals y_i exactly, after the text
  normalisation of the track.

Credit and time::

    credit_i = words(y_i)   if committed_i and correct_i
             = 0            otherwise (wrong commit, offer, withhold, abstain)
    time_i   = neural_s_i + [committed_i and not correct_i] * penalty_i
    penalty_i = correction_overhead_s + correction_s_per_char * len(y_i)

    safe WPM = 60 * sum_i credit_i / sum_i time_i

Rules:

1. Only text that the system commits counts. Offered text counts 0, also
   if the user would accept it: the eWPM column already credits offers
   with the simulated user.
2. A withheld or offered trial costs its neural time and gives 0 words.
3. A wrong commit gives 0 words and costs a correction: the user deletes
   the text and writes the sentence again with the correction rate of the
   ``aac-gaze-v1`` user model (2.0 s + 2 * 60 / 152 s per character). The
   rewritten words do not count (the BCI did not produce them).
4. The value is a **safe** WPM only when the policy carries a certified
   bound: method ``ltt`` (P(wrong-commit rate <= alpha) >= 1 - delta) or
   ``crc`` (expected wrong-commit rate <= alpha). Without a bound the
   status is ``not-certified`` and ``value`` is None (``unguarded_wpm``
   still gives the number, for reference only).
5. If the measured wrong-commit rate on the scored trials is above alpha,
   the status is ``above-alpha`` and the leaderboard marks the entry.
6. If the policy commits nothing, the status is ``vacuous`` and the value
   is 0.0 (safe, but no value).

The report always carries alpha, delta, the method, the calibration size,
the measured wrong-commit rate with its Clopper-Pearson 95 % interval, the
controls and the no-BCI reference.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from fidetype.utils.binomial import clopper_pearson

DEFINITION = "safe-wpm/0.1"
CERTIFIED_METHODS = ("ltt", "crc")
#: aac-gaze-v1 correction constants (``fidetype.interact.simulated_user.UserConfig`` defaults).
DEFAULT_OVERHEAD_S = 2.0
DEFAULT_S_PER_CHAR = 2.0 * 60.0 / 152.0
GAZE_CHARS_PER_MIN = 20.0


@dataclass(frozen=True)
class CorrectionRule:
    """Time cost of one wrong commit: ``overhead_s + s_per_char * len(truth)``.

    ``name="none"`` gives no penalty (an optimistic variant; not the headline).
    """

    name: str = "rewrite"
    overhead_s: float = DEFAULT_OVERHEAD_S
    s_per_char: float = DEFAULT_S_PER_CHAR

    def penalty(self, n_chars: np.ndarray) -> np.ndarray:
        if self.name == "none":
            return np.zeros_like(n_chars, dtype=float)
        if self.name != "rewrite":
            raise ValueError(f"unknown correction rule {self.name!r} (use 'rewrite' or 'none')")
        return self.overhead_s + self.s_per_char * np.asarray(n_chars, float)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["formula"] = ("0" if self.name == "none" else
                        f"{self.overhead_s:g} s + {self.s_per_char:.4f} s/char * len(truth) per wrong commit")
        return d


def model_neural_s(n_chars: Sequence[float], chars_per_min: float) -> np.ndarray:
    """Neural time from a track rate model: ``len(truth) * 60 / chars_per_min``."""
    return np.asarray(n_chars, float) * 60.0 / float(chars_per_min)


def certification(guarantee: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the guarantee fields that safe WPM reports, and whether a bound exists."""
    g = dict(guarantee or {})
    m = str(g.get("method", "none")).lower()
    out = {"method": m, "alpha": g.get("alpha"), "delta": g.get("delta") if m == "ltt" else None,
           "n_cal": g.get("n_cal"), "calibration": g.get("calibration_split") or g.get("calibration"),
           "certified": False}
    if m in CERTIFIED_METHODS and isinstance(g.get("alpha"), (int, float)):
        if g.get("feasible", True) is False:
            out["note"] = "the calibration found no certified threshold (policy never commits)"
        out["certified"] = True
    if m == "crc":
        out["confidence"] = "in expectation (CRC has no delta)"
    elif m == "ltt" and isinstance(out["delta"], (int, float)):
        out["confidence"] = f"probability >= {1 - out['delta']:g} over calibration draws"
    return out


def _arrays(committed, correct, n_words, n_chars, neural_s) -> dict[str, np.ndarray]:
    cm = np.asarray(committed, bool)
    ok = np.asarray(correct, bool) & cm
    a = {"cm": cm, "ok": ok, "wrong": cm & ~ok, "nw": np.asarray(n_words, float),
         "nc": np.asarray(n_chars, float), "ns": np.asarray(neural_s, float)}
    n = len(cm)
    for k, v in a.items():
        if len(v) != n:
            raise ValueError(f"array {k!r} has length {len(v)}, expected {n}")
    if n and (not np.all(np.isfinite(a["ns"])) or np.any(a["ns"] < 0)):
        raise ValueError("neural_s must be finite and >= 0")
    return a


def _point(a: dict[str, np.ndarray], pen: np.ndarray, w: np.ndarray | None = None) -> dict[str, float]:
    w = np.ones(len(a["cm"])) if w is None else w
    credit = float((np.where(a["ok"], a["nw"], 0.0) * w).sum())
    t_neural = float((a["ns"] * w).sum())
    t_pen = float((np.where(a["wrong"], pen, 0.0) * w).sum())
    t = t_neural + t_pen
    return {"wpm": 60.0 * credit / t if t > 0 else math.nan,
            "wpm_no_penalty": 60.0 * credit / t_neural if t_neural > 0 else math.nan,
            "wrong_commit_rate": float((a["wrong"] * w).sum() / w.sum()) if w.sum() > 0 else math.nan}


def safe_wpm(committed: Sequence[bool], correct: Sequence[bool], n_words: Sequence[float],
             n_chars: Sequence[float], neural_s: Sequence[float], *, guarantee: Mapping[str, Any] | None,
             rule: CorrectionRule = CorrectionRule(), timing: str = "unspecified",
             clusters: Sequence[Mapping[str, str]] | None = None, ci_unit: str | None = None,
             controls: Mapping[str, Any] | None = None, gaze_chars_per_min: float | None = GAZE_CHARS_PER_MIN,
             B: int = 2000, seed: int = 0) -> dict[str, Any]:
    """Compute safe WPM for one entry (see the module docstring for the definition).

    Per-trial inputs: ``committed`` (the policy committed), ``correct`` (the
    committed text is exactly the truth; ignored where not committed),
    ``n_words`` / ``n_chars`` (truth lengths), ``neural_s`` (neural time).
    ``guarantee``: the declared bound (``method``, ``alpha``, ``delta``,
    ``n_cal``, ...). ``clusters`` + ``ci_unit``: a percentile cluster
    bootstrap CI (as the benchmark scorer); omit for no CI.
    """
    a = _arrays(committed, correct, n_words, n_chars, neural_s)
    n = len(a["cm"])
    pen = rule.penalty(a["nc"])
    pt = _point(a, pen)
    cert = certification(guarantee)
    k_wrong, k_commit = int(a["wrong"].sum()), int(a["cm"].sum())
    measured = k_wrong / n if n else math.nan
    ci = None
    if clusters is not None and ci_unit and n:
        from fidetype.benchmark.scoring import bootstrap_ci

        ci = bootstrap_ci(lambda w: {"wpm": _point(a, pen, w)["wpm"]}, ci_unit, list(clusters), B=B, seed=seed)["wpm"]
    if not cert["certified"]:
        status, value = "not-certified", None
    elif k_commit == 0:
        status, value = "vacuous", 0.0
    elif isinstance(cert["alpha"], (int, float)) and measured > cert["alpha"]:
        status, value = "above-alpha", pt["wpm"]
    else:
        status, value = "certified", pt["wpm"]
    t_neural = float(a["ns"].sum())
    t_pen = float(np.where(a["wrong"], pen, 0.0).sum())
    out: dict[str, Any] = {
        "definition": DEFINITION,
        "value": value,
        "ci": (ci if value is not None and status != "vacuous" else None),
        "status": status,
        "unguarded_wpm": pt["wpm"],
        "wpm_no_penalty": pt["wpm_no_penalty"],
        **{k: cert[k] for k in ("method", "alpha", "delta", "n_cal", "calibration")},
        "confidence": cert.get("confidence"),
        "measured_wrong_commit": measured,
        "measured_wrong_commit_cp95": clopper_pearson(k_wrong, n) if n else [None, None],
        "n_trials": n, "n_commits": k_commit, "n_wrong_commits": k_wrong, "n_correct_commits": k_commit - k_wrong,
        "error_among_commits": (k_wrong / k_commit) if k_commit else None,
        "committed_correct_words": int(np.where(a["ok"], a["nw"], 0.0).sum()),
        "total_words": int(a["nw"].sum()),
        "minutes_neural": t_neural / 60.0, "minutes_correction": t_pen / 60.0,
        "timing": timing,
        "correction_rule": rule.to_dict(),
    }
    if ci is not None:
        out["ci_unit"] = ci_unit
    if gaze_chars_per_min:
        out["no_bci_wpm"] = 60.0 * a["nw"].sum() / (a["nc"].sum() * 60.0 / gaze_chars_per_min) if a["nc"].sum() else None
        out["no_bci_note"] = f"gaze typing of every sentence at {gaze_chars_per_min:g} chars/min (the eWPM reference)"
    if cert.get("note"):
        out["note"] = cert["note"]
    if controls is not None:
        out["controls"] = summarize_controls(controls)
    return out


def summarize_controls(c: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the status of the required controls (shuffled, zeros, null_commit) and the overall flag."""
    out: dict[str, Any] = {k: (c.get(k) or {}).get("status", "missing") for k in ("shuffled", "zeros", "null_commit")}
    if "passed" in c:
        out["passed"] = bool(c["passed"])
    else:
        out["passed"] = all(out[k] == "pass" for k in ("shuffled", "zeros", "null_commit"))
    r = c.get("null_commit") or {}
    if "commit_rate_zeros" in r:
        out["commit_rate_zeros"] = r["commit_rate_zeros"]
    basis = {k: (c.get(k) or {}).get("basis") for k in ("shuffled", "zeros", "null_commit") if (c.get(k) or {}).get("basis")}
    if basis:
        out["basis"] = basis
    return out


def guarantee_from_sheet(sheet: Mapping[str, Any]) -> dict[str, Any]:
    """The guarantee of a drop-in ``TrustGuard`` (``guard.sheet.to_dict()`` or the ``sheet`` of a saved guard)."""
    n_ltt = sheet.get("n_ltt")
    return {"method": "ltt", "alpha": sheet.get("alpha"), "delta": sheet.get("delta"), "n_cal": n_ltt,
            "calibration_split": (f"{sheet.get('n_items')} items: {sheet.get('n_fit')} fit + {sheet.get('n_policy')} "
                                  f"grid + {n_ltt} LTT (fidetype.trust.calibrate)"),
            "feasible": sheet.get("feasible", True), "config_id": sheet.get("config_id"),
            "commit_threshold": sheet.get("commit_threshold")}


def controls_from_sheet(sheet: Mapping[str, Any]) -> dict[str, Any]:
    """Map the drop-in null controls (uniform, shuffled: commit rate <= allowed) to the benchmark control keys.

    The drop-in controls test commit refusal, not a CER gap: ``shuffled`` = time-shuffled calibration frames,
    ``zeros`` and ``null_commit`` = near-uniform frames (no signal).
    """
    by = {c.get("name"): c for c in sheet.get("controls", [])}
    out: dict[str, Any] = {}
    for key, name in (("shuffled", "shuffled"), ("zeros", "uniform"), ("null_commit", "uniform")):
        c = by.get(name)
        if not c:
            out[key] = {"status": "missing"}
            continue
        out[key] = {"status": "pass" if c.get("passed") else "fail",
                    "basis": f"drop-in null control '{name}': {c.get('n_commit')}/{c.get('n')} commits "
                             f"(allowed {c.get('allowed')})"}
        if key == "null_commit" and c.get("n"):
            out[key]["commit_rate_zeros"] = c.get("n_commit", 0) / c["n"]
    out["passed"] = all(out[k]["status"] == "pass" for k in ("shuffled", "zeros", "null_commit"))
    return out


def from_trial_scores(scores: Sequence[Any], *, guarantee: Mapping[str, Any] | None, timing: str,
                      ci_unit: str | None = None, controls: Mapping[str, Any] | None = None,
                      gaze_chars_per_min: float | None = GAZE_CHARS_PER_MIN, rule: CorrectionRule = CorrectionRule(),
                      B: int = 2000, seed: int = 0) -> dict[str, Any]:
    """Safe WPM from benchmark :class:`~fidetype.benchmark.scoring.TrialScore` objects (needs ``neural_s``)."""
    return safe_wpm([s.committed for s in scores], [s.committed and not s.wrong_commit for s in scores],
                    [s.n_w for s in scores], [s.n_c for s in scores], [s.neural_s for s in scores],
                    guarantee=guarantee, rule=rule, timing=timing,
                    clusters=[s.clusters for s in scores] if ci_unit else None, ci_unit=ci_unit,
                    controls=controls, gaze_chars_per_min=gaze_chars_per_min, B=B, seed=seed)


def load_trials_jsonl(path: str) -> dict[str, list]:
    """Read a per-trial JSON Lines file for the CLI.

    One object per trial: ``committed`` (bool), ``correct`` (bool), and
    either ``truth`` (text; lengths taken from it) or ``n_words`` +
    ``n_chars``; ``neural_s`` (seconds; optional if ``--chars-per-min``
    is given); optional ``cluster`` (string) for the bootstrap.
    """
    import json

    cols: dict[str, list] = {k: [] for k in ("committed", "correct", "n_words", "n_chars", "neural_s", "cluster")}
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            d = json.loads(line)
            if "truth" in d:
                t = " ".join(str(d["truth"]).split())
                nw, nc = len(t.split()), len(t)
            else:
                nw, nc = d["n_words"], d["n_chars"]
            cols["committed"].append(bool(d["committed"]))
            cols["correct"].append(bool(d.get("correct", False)))
            cols["n_words"].append(float(nw))
            cols["n_chars"].append(float(nc))
            cols["neural_s"].append(float(d["neural_s"]) if d.get("neural_s") is not None else math.nan)
            cols["cluster"].append(str(d["cluster"]) if d.get("cluster") is not None else "")
    return cols


def format_line(r: Mapping[str, Any]) -> str:
    """One-line human summary of a safe-WPM block."""
    v = r.get("value")
    vs = "n/a" if v is None else f"{v:.2f}"
    if r.get("ci") and v is not None:
        vs += f" [{r['ci'][0]:.2f}, {r['ci'][1]:.2f}]"
    g = r.get("method", "none").upper()
    if r.get("alpha") is not None:
        g += f" a={r['alpha']}"
    if r.get("delta") is not None:
        g += f" d={r['delta']}"
    if r.get("n_cal") is not None:
        g += f" n_cal={r['n_cal']}"
    return (f"safe WPM {vs} ({r['status']}; {g}; test wrong-commit {r['n_wrong_commits']}/{r['n_trials']} = "
            f"{r['measured_wrong_commit']:.4f}; commits {r['n_commits']}; unguarded {r['unguarded_wpm']:.2f}; "
            f"no-BCI {r.get('no_bci_wpm') or float('nan'):.2f})")


__all__ = ["DEFINITION", "CorrectionRule", "certification", "model_neural_s", "safe_wpm", "from_trial_scores",
           "summarize_controls", "guarantee_from_sheet", "controls_from_sheet", "load_trials_jsonl", "format_line"]
