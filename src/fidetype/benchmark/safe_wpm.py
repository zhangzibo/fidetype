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
7. A guarantee with ``feasible: false`` (the calibration found no
   certified threshold) certifies only a policy that never commits. If the
   policy commits on at least one trial, the status is ``not-certified``
   (P5-30).

The report always carries alpha, delta, the method, the calibration size,
the measured wrong-commit rate with its Clopper-Pearson 95 % interval, the
controls and the no-BCI reference.

Proposed ``safe-wpm/0.2`` (P14-26; PROPOSED, NOT ADOPTED)
--------------------------------------------------------
``safe_wpm(..., metric_version="0.2")`` scores word-prefix commits. The
default stays ``"0.1"``; v0.1 numbers do not change. Full text:
``docs/safe-wpm-v0.2-proposal.md``. Per trial, a commit has k_i words and
a flag ``complete_i`` (the commit claims the whole sentence; every
sentence-level commit is complete)::

    right_i   = (c_i == y_i)                                   if complete_i
              = (k_i >= 1 and c_i == first k_i words of y_i)   otherwise
    credit_i  = words(y_i) if right_i and complete_i; k_i if right_i and not complete_i; else 0
    penalty_i = overhead + s_per_char * len(y_i)                       if complete_i
              = overhead + s_per_char * len(first k_i words of y_i)    otherwise

Words of y_i after a prefix commit give 0 words and no time (as a withheld
trial). The risk unit is the trial: a wrong commit is a commit that is not
right_i. A policy with prefix commits is certified only by a bound on that
loss (guarantee ``risk = "wrong-prefix-commit"``). An optional per-trial
``speech_s`` adds a ``speech_time`` block (the same credit over speech
time); the headline time stays ``neural_s``. For a policy with only
complete commits, v0.2 gives the same value as v0.1.

Optional v0.2 sensitivity options (P14-28; the defaults keep every
published value): ``read_s_per_commit`` + ``read_s_per_word`` add a
reading / checking time to every commit, right or wrong
(``read_s_per_commit + read_s_per_word * k_i``, k_i = words of the
committed text), and ``min_prefix_words`` m turns a prefix commit
(not complete) with fewer than m words into no commit (0 words, no time).

Proposed extension "several commits per trial" (P5-27; part of the v0.2
proposal, not adopted): ``n_commits`` gives the number of append-only
commit events of each trial (a streaming guard commits more words of the
same sentence as evidence arrives; committed words are never retracted).
The per-trial commit arrays then describe the union of the trial's
commits (its final committed text): the trial is right only if every
commit is right, which for append-only commits is the same as "the final
committed text is right" by rule (1). Credit and penalty use that text.
The reading time is ``read_s_per_commit * n_commits_i + read_s_per_word *
k_i`` (every commit pays the fixed cost; every committed word is read
once). A trial with more than one commit is certified only by a bound on
the trial loss "any commit of the trial is wrong" (guarantee ``risk =
"wrong-stream-commit"``). With one commit per trial the extension gives
the v0.2 value.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from fidetype.utils.binomial import clopper_pearson

DEFINITION = "safe-wpm/0.1"
#: The proposed prefix-credit version (P14-26). Not adopted: the default stays v0.1.
DEFINITION_V02 = "safe-wpm/0.2"
METRIC_VERSIONS = ("0.1", "0.2")
V02_STATUS = "proposed, not adopted (P14-26): v0.1 stays the headline metric until the user accepts v0.2"
#: Loss names of a guarantee (``guarantee["risk"]``). Absent = ``RISK_SENTENCE``.
RISK_SENTENCE = "wrong-commit"
RISK_PREFIX = "wrong-prefix-commit"
#: P5-27 (proposed extension of v0.2): the trial is wrong if any of its append-only commits is wrong.
RISK_STREAM = "wrong-stream-commit"
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


def prefix_outcome(committed_text: str, truth: str, complete: bool) -> dict[str, Any]:
    """The ``safe-wpm/0.2`` outcome of one commit (words split on spaces, after the track normalisation).

    ``complete``: the commit claims the whole sentence (a sentence-level
    commit); otherwise it claims only its first k words. Returns
    ``correct`` (right_i), ``committed_words`` (k_i), ``complete``,
    ``credit_words`` and ``penalty_chars`` (the characters of the truth
    that the user types again after a wrong commit).
    """
    c, t = str(committed_text).split(), str(truth).split()
    k = len(c)
    if k == 0:
        raise ValueError("a commit needs at least one word")
    if complete:
        right, chars = c == t, len(" ".join(t))
    else:
        right, chars = (len(t) >= k and t[:k] == c), len(" ".join(t[:k]))
    return {"correct": bool(right), "committed_words": k, "complete": bool(complete),
            "credit_words": (len(t) if complete else k) if right else 0, "penalty_chars": chars}


def certification(guarantee: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the guarantee fields that safe WPM reports, and whether a bound exists."""
    g = dict(guarantee or {})
    m = str(g.get("method", "none")).lower()
    out = {"method": m, "alpha": g.get("alpha"), "delta": g.get("delta") if m == "ltt" else None,
           "n_cal": g.get("n_cal"), "calibration": g.get("calibration_split") or g.get("calibration"),
           "certified": False}
    if m in CERTIFIED_METHODS and isinstance(g.get("alpha"), (int, float)):
        if g.get("feasible", True) is False:
            out["infeasible"] = True
            out["note"] = "the calibration found no certified threshold (policy never commits)"
        out["certified"] = True
    if m == "crc":
        out["confidence"] = "in expectation (CRC has no delta)"
    elif m == "ltt" and isinstance(out["delta"], (int, float)):
        out["confidence"] = f"probability >= {1 - out['delta']:g} over calibration draws"
    return out


def _refuse_infeasible(cert: dict[str, Any], k_commit: int, note: str | None) -> str | None:
    """P5-30: an infeasible guarantee certifies only a policy that never commits.

    ``feasible: false`` means the calibration found no certified threshold.
    The bound then holds only because the policy commits nothing. If the
    scored policy commits at least once, it has no bound: the function
    sets ``certified`` to False and returns the new note (else ``note``).
    """
    if cert.get("certified") and cert.get("infeasible") and k_commit > 0:
        cert["certified"] = False
        return (f"the calibration found no certified threshold (feasible: false), but the policy commits on "
                f"{k_commit} trial(s): no bound covers these commits (P5-30)")
    return note


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
    if "rd" in a:  # safe-wpm/0.2 reading time per commit (P14-28); absent = 0
        t += float((np.where(a["cm"], a["rd"], 0.0) * w).sum())
    return {"wpm": 60.0 * credit / t if t > 0 else math.nan,
            "wpm_no_penalty": 60.0 * credit / t_neural if t_neural > 0 else math.nan,
            "wrong_commit_rate": float((a["wrong"] * w).sum() / w.sum()) if w.sum() > 0 else math.nan}


def safe_wpm(committed: Sequence[bool], correct: Sequence[bool], n_words: Sequence[float],
             n_chars: Sequence[float], neural_s: Sequence[float], *, guarantee: Mapping[str, Any] | None,
             rule: CorrectionRule = CorrectionRule(), timing: str = "unspecified",
             clusters: Sequence[Mapping[str, str]] | None = None, ci_unit: str | None = None,
             controls: Mapping[str, Any] | None = None, gaze_chars_per_min: float | None = GAZE_CHARS_PER_MIN,
             B: int = 2000, seed: int = 0, metric_version: str = "0.1",
             committed_words: Sequence[float] | None = None, complete: Sequence[bool] | None = None,
             penalty_chars: Sequence[float] | None = None, speech_s: Sequence[float] | None = None,
             speech_timing: str = "unspecified", read_s_per_commit: float = 0.0, read_s_per_word: float = 0.0,
             min_prefix_words: int = 1, n_commits: Sequence[int] | None = None) -> dict[str, Any]:
    """Compute safe WPM for one entry (see the module docstring for the definition).

    Per-trial inputs: ``committed`` (the policy committed), ``correct`` (the
    committed text is exactly the truth; ignored where not committed),
    ``n_words`` / ``n_chars`` (truth lengths), ``neural_s`` (neural time).
    ``guarantee``: the declared bound (``method``, ``alpha``, ``delta``,
    ``n_cal``, ...). ``clusters`` + ``ci_unit``: a percentile cluster
    bootstrap CI (as the benchmark scorer); omit for no CI.

    ``metric_version="0.2"`` (P14-26, proposed, not adopted) scores prefix
    commits: ``correct`` is then right_i (:func:`prefix_outcome`),
    ``complete`` marks commits that claim the whole sentence (default: all),
    ``committed_words`` (k_i) and ``penalty_chars`` are needed for the
    commits that are not complete, and ``speech_s`` (optional) adds a
    ``speech_time`` block. The v0.2 arguments are refused with v0.1.

    v0.2 sensitivity options (P14-28, all off by default):
    ``read_s_per_commit`` and ``read_s_per_word`` (seconds, >= 0) add
    ``read_s_per_commit + read_s_per_word * k_i`` to the time of every
    commit (k_i from ``committed_words``; for a complete commit without
    it, the truth length). ``min_prefix_words`` (>= 1) drops prefix
    commits with fewer words (they become no commit). A ``reading_cost``
    block reports them when one is not at its default.

    ``n_commits`` (P5-27, proposed extension of v0.2): the number of
    append-only commits of each trial (default: 1 per committed trial).
    The other per-trial commit arrays then describe the union of the
    trial's commits. Each commit pays ``read_s_per_commit``. A trial with
    several commits needs a guarantee with ``risk="wrong-stream-commit"``.
    """
    if metric_version not in METRIC_VERSIONS:
        raise ValueError(f"metric_version must be one of {METRIC_VERSIONS}, not {metric_version!r}")
    if metric_version == "0.2":
        return _safe_wpm_v02(committed, correct, n_words, n_chars, neural_s, guarantee=guarantee, rule=rule,
                             timing=timing, clusters=clusters, ci_unit=ci_unit, controls=controls,
                             gaze_chars_per_min=gaze_chars_per_min, B=B, seed=seed, committed_words=committed_words,
                             complete=complete, penalty_chars=penalty_chars, speech_s=speech_s,
                             speech_timing=speech_timing, read_s_per_commit=read_s_per_commit,
                             read_s_per_word=read_s_per_word, min_prefix_words=min_prefix_words,
                             n_commits=n_commits)
    extra = [k for k, v in (("committed_words", committed_words), ("complete", complete),
                            ("penalty_chars", penalty_chars), ("speech_s", speech_s),
                            ("n_commits", n_commits)) if v is not None]
    extra += [k for k, v, d in (("read_s_per_commit", read_s_per_commit, 0.0),
                                ("read_s_per_word", read_s_per_word, 0.0),
                                ("min_prefix_words", min_prefix_words, 1)) if v != d]
    if extra:
        raise ValueError(f"{extra} are safe-wpm/0.2 fields; pass metric_version='0.2' (proposed, not adopted)")
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
    note = _refuse_infeasible(cert, k_commit, cert.get("note"))
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
    if note:
        out["note"] = note
    if controls is not None:
        out["controls"] = summarize_controls(controls)
    return out


def _safe_wpm_v02(committed, correct, n_words, n_chars, neural_s, *, guarantee, rule, timing, clusters, ci_unit,
                  controls, gaze_chars_per_min, B, seed, committed_words, complete, penalty_chars, speech_s,
                  speech_timing, read_s_per_commit=0.0, read_s_per_word=0.0,
                  min_prefix_words=1, n_commits=None) -> dict[str, Any]:
    """``safe-wpm/0.2`` (proposed): prefix credit, prefix penalty, optional speech time (module docstring)."""
    rsc, rsw = float(read_s_per_commit), float(read_s_per_word)
    if not (math.isfinite(rsc) and rsc >= 0 and math.isfinite(rsw) and rsw >= 0):
        raise ValueError("read_s_per_commit and read_s_per_word must be finite and >= 0")
    if isinstance(min_prefix_words, bool) or int(min_prefix_words) != min_prefix_words or min_prefix_words < 1:
        raise ValueError("min_prefix_words must be an integer >= 1")
    min_prefix_words = int(min_prefix_words)
    a = _arrays(committed, correct, n_words, n_chars, neural_s)
    n = len(a["cm"])
    full = np.ones(n, bool) if complete is None else np.asarray(complete, bool)
    if len(full) != n:
        raise ValueError(f"array 'complete' has length {len(full)}, expected {n}")
    partial = a["cm"] & ~full
    kw = np.full(n, np.nan) if committed_words is None else np.asarray(committed_words, float)
    pc = np.full(n, np.nan) if penalty_chars is None else np.asarray(penalty_chars, float)
    for name, v in (("committed_words", kw), ("penalty_chars", pc)):
        if len(v) != n:
            raise ValueError(f"array {name!r} has length {len(v)}, expected {n}")
        if partial.any() and not np.all(np.isfinite(v[partial]) & (v[partial] >= 0)):
            raise ValueError(f"{name} is needed (finite, >= 0) for every commit that is not complete")
    if partial.any() and np.any(kw[partial] < 1):
        raise ValueError("a prefix commit needs at least one word")
    if n_commits is None:
        nci = a["cm"].astype(float)
    else:
        nci = np.asarray(n_commits, float)
        if len(nci) != n:
            raise ValueError(f"array 'n_commits' has length {len(nci)}, expected {n}")
        if not np.all(np.isfinite(nci)) or np.any(nci != np.round(nci)) or np.any(nci < 0):
            raise ValueError("n_commits must be integers >= 0")
        if np.any(a["cm"] & (nci < 1)):
            raise ValueError("a committed trial needs n_commits >= 1")
        nci = np.where(a["cm"], nci, 0.0)
    multi = a["cm"] & (nci > 1)
    if multi.any() and min_prefix_words != 1:
        raise ValueError("min_prefix_words is not defined for trials with several commits (P5-27)")
    dropped = partial & (np.nan_to_num(kw) < min_prefix_words)
    if dropped.any():  # P14-28: a prefix commit shorter than min_prefix_words becomes no commit
        a["cm"] = a["cm"] & ~dropped
        a["ok"] = a["ok"] & a["cm"]
        a["wrong"] = a["cm"] & ~a["ok"]
        partial = partial & ~dropped
    read_on = rsc > 0 or rsw > 0
    if read_on:
        a["rd"] = rsc * np.maximum(nci, 1.0) + rsw * np.where(np.isfinite(kw), kw, a["nw"])
    total_words = a["nw"].copy()
    credit_words = np.where(partial, np.nan_to_num(kw), a["nw"])
    if np.any(a["ok"] & partial & (credit_words > total_words)):
        raise ValueError("a right prefix cannot have more words than the truth")
    a["nw"] = credit_words  # _point credits a["nw"] where a["ok"]
    pen = rule.penalty(np.where(partial, np.nan_to_num(pc), a["nc"]))
    pt = _point(a, pen)
    cert = certification(guarantee)
    risk = str((guarantee or {}).get("risk", RISK_SENTENCE))
    note = cert.get("note")
    if multi.any() and risk != RISK_STREAM:
        cert["certified"] = False
        note = (f"the policy commits several times in a trial, but its bound is on '{risk}', not on "
                f"'{RISK_STREAM}' (the P5-27 extension needs a bound on the trial loss 'any commit is wrong')")
    elif partial.any() and risk not in (RISK_PREFIX, RISK_STREAM):
        cert["certified"] = False
        note = (f"the policy commits prefixes, but its bound is on '{risk}', not on '{RISK_PREFIX}' "
                "(safe-wpm/0.2 needs a bound on wrong-prefix commits)")
    k_wrong, k_commit = int(a["wrong"].sum()), int(a["cm"].sum())
    measured = k_wrong / n if n else math.nan
    ci = None
    if clusters is not None and ci_unit and n:
        from fidetype.benchmark.scoring import bootstrap_ci

        ci = bootstrap_ci(lambda w: {"wpm": _point(a, pen, w)["wpm"]}, ci_unit, list(clusters), B=B, seed=seed)["wpm"]
    note = _refuse_infeasible(cert, k_commit, note)
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
        "definition": DEFINITION_V02,
        "definition_status": V02_STATUS,
        "value": value,
        "ci": (ci if value is not None and status != "vacuous" else None),
        "status": status,
        "unguarded_wpm": pt["wpm"],
        "wpm_no_penalty": pt["wpm_no_penalty"],
        **{k: cert[k] for k in ("method", "alpha", "delta", "n_cal", "calibration")},
        "confidence": cert.get("confidence"),
        "risk": risk,
        "measured_wrong_commit": measured,
        "measured_wrong_commit_cp95": clopper_pearson(k_wrong, n) if n else [None, None],
        "n_trials": n, "n_commits": k_commit, "n_wrong_commits": k_wrong, "n_correct_commits": k_commit - k_wrong,
        "n_prefix_commits": int(partial.sum()), "n_complete_commits": int((a["cm"] & full).sum()),
        "n_right_complete_commits": int((a["ok"] & full).sum()),
        "error_among_commits": (k_wrong / k_commit) if k_commit else None,
        "committed_correct_words": int(np.where(a["ok"], credit_words, 0.0).sum()),
        "total_words": int(total_words.sum()),
        "minutes_neural": t_neural / 60.0, "minutes_correction": t_pen / 60.0,
        "timing": timing,
        "correction_rule": dict(rule.to_dict(), prefix=("a wrong prefix of k words costs the penalty of the first k "
                                                        "words of the truth")),
    }
    if read_on or min_prefix_words != 1:
        t_read = float(np.where(a["cm"], a["rd"], 0.0).sum()) if read_on else 0.0
        b = {k: v for k, v in a.items() if k != "rd"}
        out["reading_cost"] = {
            "read_s_per_commit": rsc, "read_s_per_word": rsw, "min_prefix_words": min_prefix_words,
            "formula": (f"{rsc:g} s + {rsw:g} s/word * k per commit (right or wrong); prefix commits with fewer "
                        f"than {min_prefix_words} word(s) count as no commit"),
            "minutes_reading": t_read / 60.0, "n_prefix_commits_dropped": int(dropped.sum()),
            "wpm_without_reading": _point(b, pen)["wpm"],
            "note": ("P14-28 sensitivity option of the proposed safe-wpm/0.2; the default (0 s, 1 word) is the "
                     "proposal as committed"),
        }
    if n_commits is not None:
        out["multi_commit"] = {
            "n_commit_events": int(nci.sum()), "n_trials_with_several_commits": int(multi.sum()),
            "max_commits_per_trial": int(nci.max()) if n else 0,
            "rule": ("P5-27 proposed extension: append-only commits; the trial is right only if every commit is "
                     "right (= its final committed text is right); credit and penalty of that text; every commit "
                     "pays read_s_per_commit, every committed word read_s_per_word once"),
            "status": "proposed extension of the proposed safe-wpm/0.2 (not adopted)"}
    if ci is not None:
        out["ci_unit"] = ci_unit
    if speech_s is not None:
        sp = np.asarray(speech_s, float)
        if len(sp) != n or (n and (not np.all(np.isfinite(sp)) or np.any(sp < 0))):
            raise ValueError("speech_s must have one finite value >= 0 per trial")
        b = dict(a, ns=sp)
        ps = _point(b, pen)
        out["speech_time"] = {"value": (0.0 if status == "vacuous" else ps["wpm"]) if value is not None else None,
                              "wpm_no_penalty": ps["wpm_no_penalty"], "minutes_speech": float(sp.sum()) / 60.0,
                              "timing": speech_timing,
                              "note": "same credit and penalty over speech time; the headline value uses neural_s"}
    if gaze_chars_per_min:
        out["no_bci_wpm"] = (60.0 * total_words.sum() / (a["nc"].sum() * 60.0 / gaze_chars_per_min)
                             if a["nc"].sum() else None)
        out["no_bci_note"] = f"gaze typing of every sentence at {gaze_chars_per_min:g} chars/min (the eWPM reference)"
    if note:
        out["note"] = note
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
            "commit_threshold": sheet.get("commit_threshold"),
            **({"risk": RISK_PREFIX} if (sheet.get("confidence") or {}).get("unit") == "prefix" else
               {"risk": RISK_STREAM} if (sheet.get("confidence") or {}).get("unit") == "stream-prefix" else {})}


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
    ``safe-wpm/0.2`` (proposed) fields, ignored by v0.1: ``complete``
    (default true), ``committed_text`` (with ``truth``: sets ``correct``,
    ``committed_words`` and ``penalty_chars`` by :func:`prefix_outcome`, in
    ``correct_v02``; ``correct`` then means the exact sentence, as in v0.1)
    or ``committed_words`` + ``penalty_chars``; ``speech_s``; ``n_commits`` (P5-27: the number of
    append-only commits of the trial; default 1 if committed).
    """
    import json

    cols: dict[str, list] = {k: [] for k in ("committed", "correct", "n_words", "n_chars", "neural_s", "cluster",
                                             "correct_v02", "committed_words", "complete", "penalty_chars",
                                             "speech_s", "n_commits")}
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
            # safe-wpm/0.2 (proposed) fields; v0.1 ignores them
            comp = bool(d.get("complete", True))
            kw, pch = d.get("committed_words"), d.get("penalty_chars")
            ok2 = cols["correct"][-1]
            if d.get("committed_text") is not None and bool(d["committed"]):
                if "truth" not in d:
                    raise ValueError(f"line {ln}: committed_text needs truth")
                po = prefix_outcome(d["committed_text"], d["truth"], comp)
                ok2, kw, pch = po["correct"], po["committed_words"], po["penalty_chars"]
                # v0.1: only the exact sentence is right
                cols["correct"][-1] = " ".join(str(d["committed_text"]).split()) == " ".join(str(d["truth"]).split())
            cols["correct_v02"].append(bool(ok2))
            cols["complete"].append(comp)
            cols["committed_words"].append(float(kw) if kw is not None else math.nan)
            cols["penalty_chars"].append(float(pch) if pch is not None else math.nan)
            cols["speech_s"].append(float(d["speech_s"]) if d.get("speech_s") is not None else math.nan)
            cols["n_commits"].append(int(d["n_commits"]) if d.get("n_commits") is not None else
                                     int(bool(d["committed"])))
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
    if r.get("definition") == DEFINITION_V02:
        vs += f" [{DEFINITION_V02}, proposed; {r.get('n_prefix_commits', 0)} prefix commits]"
    return (f"safe WPM {vs} ({r['status']}; {g}; test wrong-commit {r['n_wrong_commits']}/{r['n_trials']} = "
            f"{r['measured_wrong_commit']:.4f}; commits {r['n_commits']}; unguarded {r['unguarded_wpm']:.2f}; "
            f"no-BCI {r.get('no_bci_wpm') or float('nan'):.2f})")


__all__ = ["DEFINITION", "DEFINITION_V02", "METRIC_VERSIONS", "RISK_SENTENCE", "RISK_PREFIX", "prefix_outcome",
           "CorrectionRule", "certification", "model_neural_s", "safe_wpm", "from_trial_scores",
           "summarize_controls", "guarantee_from_sheet", "controls_from_sheet", "load_trials_jsonl", "format_line"]
