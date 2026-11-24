"""Safe WPM: words per minute of committed, correct text at a certified wrong-commit rate (P14-05).

Versions
--------
- ``safe-wpm/0.2`` (ADOPTED 2026-11-22; the default since P14-61):
  ``safe_wpm(...)`` with no ``metric_version``. It adds prefix credit and
  the ``aac-gaze-v1`` reading cost (0.5 s + 0.3 s per committed word, per
  commit) to v0.1. For a sentence-level policy it gives the v0.1 credit
  and penalty plus the reading time. See "safe-wpm/0.2" below.
- ``safe-wpm/0.1`` (the headline until 2026-11-22): ``metric_version="0.1"``.
  It stays selectable, so every old number can be reproduced. A v0.1
  number keeps its value and its v0.1 label.

Every report carries ``definition`` (the version label). A v0.2 report
also carries ``definition_status`` and ``adopted_headline`` (False for a
sensitivity variant, for example without the reading cost). The v0.1
report is unchanged, so an old v0.1 block is reproduced byte for byte.

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

``safe-wpm/0.2`` (P14-26; ADOPTED 2026-11-22, the default)
---------------------------------------------------------
``safe_wpm(..., metric_version="0.2")`` (the default) scores word-prefix
commits; ``metric_version="0.1"`` gives the v0.1 value. Full text:
``docs/safe-wpm.md`` section 6a and ``docs/safe-wpm-v0.2-proposal.md``. Per trial, a commit has k_i words and
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
time); the headline time stays ``neural_s``.

Reading cost (P14-28; part of the adopted v0.2): ``read_s_per_commit`` +
``read_s_per_word`` add a reading / checking time to every commit, right
or wrong (``read_s_per_commit + read_s_per_word * k_i``, k_i = words of
the committed text). The defaults are the adopted ``aac-gaze-v1`` values
:data:`READ_S_PER_COMMIT` = 0.5 s and :data:`READ_S_PER_WORD` = 0.3 s.
``min_prefix_words`` m (adopted: 1) turns a prefix commit (not complete)
with fewer than m words into no commit (0 words, no time). Other values
(for example ``read_s_per_commit=0, read_s_per_word=0``, the proposal as
first committed) give a sensitivity variant: ``adopted_headline`` is then
False. For a policy with only complete commits and no reading cost, v0.2
gives the same value as v0.1.

Proposed extension "several commits per trial" (P5-27; an extension of
v0.2, NOT adopted): ``n_commits`` gives the number of append-only
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
#: The prefix-credit version (P14-26), adopted 2026-11-22 with the reading cost; the default since P14-61.
DEFINITION_V02 = "safe-wpm/0.2"
METRIC_VERSIONS = ("0.1", "0.2")
#: The ``metric_version`` of :func:`safe_wpm` when the caller gives none (P14-61).
DEFAULT_METRIC_VERSION = "0.2"
#: The date the maintainer adopted ``safe-wpm/0.2`` (docs/safe-wpm.md section 6a).
V02_ADOPTED = "2026-11-22"
V02_STATUS = ("adopted 2026-11-22: the headline metric (prefix credit + the aac-gaze-v1 reading cost); "
              "safe-wpm/0.1 stays selectable with metric_version='0.1' for old numbers")
V02_VARIANT_STATUS = ("safe-wpm/0.2 sensitivity variant (v0.2 adopted 2026-11-22): this value is not an "
                      "adopted-v0.2 headline")
#: The adopted v0.2 reading cost (aac-gaze-v1, P14-28): seconds per commit and per committed word.
READ_S_PER_COMMIT = 0.5
READ_S_PER_WORD = 0.3
#: The adopted minimum prefix length in words (v0.2).
MIN_PREFIX_WORDS = 1
#: Loss names of a guarantee (``guarantee["risk"]``). Absent = ``RISK_SENTENCE``.
RISK_SENTENCE = "wrong-commit"
RISK_PREFIX = "wrong-prefix-commit"
#: P5-27 (proposed extension of v0.2, not adopted): the trial is wrong if any of its append-only commits is wrong.
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
             B: int = 2000, seed: int = 0, metric_version: str = DEFAULT_METRIC_VERSION,
             committed_words: Sequence[float] | None = None, complete: Sequence[bool] | None = None,
             penalty_chars: Sequence[float] | None = None, speech_s: Sequence[float] | None = None,
             speech_timing: str = "unspecified", read_s_per_commit: float | None = None,
             read_s_per_word: float | None = None, min_prefix_words: int = MIN_PREFIX_WORDS,
             n_commits: Sequence[int] | None = None) -> dict[str, Any]:
    """Compute safe WPM for one entry (see the module docstring for the definition).

    Per-trial inputs: ``committed`` (the policy committed), ``correct`` (the
    committed text is exactly the truth; ignored where not committed),
    ``n_words`` / ``n_chars`` (truth lengths), ``neural_s`` (neural time).
    ``guarantee``: the declared bound (``method``, ``alpha``, ``delta``,
    ``n_cal``, ...). ``clusters`` + ``ci_unit``: a percentile cluster
    bootstrap CI (as the benchmark scorer); omit for no CI.

    ``metric_version`` (P14-61): ``"0.2"`` (the default, adopted 2026-11-22)
    or ``"0.1"`` (the earlier headline; use it to reproduce old numbers).

    ``metric_version="0.2"`` (P14-26) scores prefix
    commits: ``correct`` is then right_i (:func:`prefix_outcome`),
    ``complete`` marks commits that claim the whole sentence (default: all),
    ``committed_words`` (k_i) and ``penalty_chars`` are needed for the
    commits that are not complete, and ``speech_s`` (optional) adds a
    ``speech_time`` block. The v0.2 arguments are refused with v0.1.

    v0.2 reading cost (P14-28; adopted): ``read_s_per_commit`` and
    ``read_s_per_word`` (seconds, >= 0; ``None`` = the adopted 0.5 s and
    0.3 s) add ``read_s_per_commit + read_s_per_word * k_i`` to the time
    of every commit (k_i from ``committed_words``; for a complete commit
    without it, the truth length). ``min_prefix_words`` (>= 1; adopted 1)
    drops prefix commits with fewer words (they become no commit). The
    ``reading_cost`` block of every v0.2 report gives them. v0.1 has no
    reading cost: there these arguments must stay ``None`` (or 0 / 1).

    ``n_commits`` (P5-27, proposed extension of v0.2, not adopted): the number of
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
                                ("min_prefix_words", min_prefix_words, 1)) if v is not None and v != d]
    if extra:
        raise ValueError(f"{extra} are safe-wpm/0.2 fields; pass metric_version='0.2' (the default)")
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
                  speech_timing, read_s_per_commit=None, read_s_per_word=None,
                  min_prefix_words=MIN_PREFIX_WORDS, n_commits=None) -> dict[str, Any]:
    """``safe-wpm/0.2`` (adopted 2026-11-22): prefix credit, prefix penalty, reading cost, optional speech time."""
    rsc = READ_S_PER_COMMIT if read_s_per_commit is None else float(read_s_per_commit)
    rsw = READ_S_PER_WORD if read_s_per_word is None else float(read_s_per_word)
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
    variant = [f"{k} = {v:g} (adopted: {d:g})" for k, v, d in
               (("read_s_per_commit", rsc, READ_S_PER_COMMIT), ("read_s_per_word", rsw, READ_S_PER_WORD),
                ("min_prefix_words", min_prefix_words, MIN_PREFIX_WORDS)) if v != d]
    if rule.to_dict() != CorrectionRule().to_dict():
        variant.append(f"correction rule {rule.name!r} is not the aac-gaze-v1 rewrite rule")
    if multi.any():
        variant.append("several commits per trial (a proposed extension, not adopted)")
    out: dict[str, Any] = {
        "definition": DEFINITION_V02,
        "definition_status": V02_VARIANT_STATUS if variant else V02_STATUS,
        "adopted_headline": not variant,
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
    if variant:
        out["not_headline_because"] = variant
    # Every v0.2 report has the reading cost block (part of the adopted definition, 2026-11-22).
    t_read = float(np.where(a["cm"], a["rd"], 0.0).sum()) if read_on else 0.0
    b = {k: v for k, v in a.items() if k != "rd"}
    out["reading_cost"] = {
        "read_s_per_commit": rsc, "read_s_per_word": rsw, "min_prefix_words": min_prefix_words,
        "formula": (f"{rsc:g} s + {rsw:g} s/word * k per commit (right or wrong); prefix commits with fewer "
                    f"than {min_prefix_words} word(s) count as no commit"),
        "minutes_reading": t_read / 60.0, "n_prefix_commits_dropped": int(dropped.sum()),
        "wpm_without_reading": _point(b, pen)["wpm"],
        "model": "aac-gaze-v1",
        "adopted": {"read_s_per_commit": READ_S_PER_COMMIT, "read_s_per_word": READ_S_PER_WORD,
                    "min_prefix_words": MIN_PREFIX_WORDS},
        "note": ("the adopted safe-wpm/0.2 reading cost (2026-11-22) is 0.5 s + 0.3 s/word per commit, "
                 "minimum prefix 1 word; other values give a sensitivity variant"),
    }
    if n_commits is not None:
        out["multi_commit"] = {
            "n_commit_events": int(nci.sum()), "n_trials_with_several_commits": int(multi.sum()),
            "max_commits_per_trial": int(nci.max()) if n else 0,
            "rule": ("P5-27 proposed extension: append-only commits; the trial is right only if every commit is "
                     "right (= its final committed text is right); credit and penalty of that text; every commit "
                     "pays read_s_per_commit, every committed word read_s_per_word once"),
            "status": "proposed extension of safe-wpm/0.2 (not adopted)"}
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


#: The default ``scope`` of a guarantee from a drop-in guard sheet (a submission guarantee needs one).
SHEET_SCOPE = "marginal over decisions exchangeable with the calibration items"


def _sheet_dict(sheet: Any) -> Mapping[str, Any]:
    """A sheet dict from a TrustGuard, a GuaranteeSheet, a saved guard dict or a sheet dict."""
    sh = getattr(sheet, "sheet", sheet)  # a TrustGuard has .sheet
    if hasattr(sh, "to_dict"):
        sh = sh.to_dict()
    if not isinstance(sh, Mapping):
        raise TypeError(f"expected a TrustGuard, a GuaranteeSheet or a sheet dict, got {type(sheet).__name__}")
    return sh.get("sheet", sh) if "alpha" not in sh and isinstance(sh.get("sheet"), Mapping) else sh


def guarantee_from_sheet(sheet: Any, *, scope: str = SHEET_SCOPE,
                         calibration_split: str | None = None) -> dict[str, Any]:
    """The guarantee of a drop-in ``TrustGuard`` (``guard.sheet.to_dict()`` or the ``sheet`` of a saved guard).

    The result is a valid submission guarantee (P14-46): it has ``scope`` (default
    :data:`SHEET_SCOPE`). ``calibration_split``: the benchmark split that calibrated the guard
    (for example ``"cal"``); default: a text with the item counts of the sheet. ``sheet`` may
    also be a TrustGuard or a GuaranteeSheet.
    """
    sheet = _sheet_dict(sheet)
    n_ltt = sheet.get("n_ltt")
    cal = calibration_split or (f"{sheet.get('n_items')} items: {sheet.get('n_fit')} fit + {sheet.get('n_policy')} "
                                f"grid + {n_ltt} LTT (fidetype.trust.calibrate)")
    return {"method": "ltt", "alpha": sheet.get("alpha"), "delta": sheet.get("delta"), "n_cal": n_ltt,
            "scope": scope, "calibration_split": cal,
            "feasible": sheet.get("feasible", True), "config_id": sheet.get("config_id"),
            "commit_threshold": sheet.get("commit_threshold"),
            **({"risk": RISK_PREFIX} if (sheet.get("confidence") or {}).get("unit") == "prefix" else
               {"risk": RISK_STREAM} if (sheet.get("confidence") or {}).get("unit") == "stream-prefix" else {})}


def controls_from_sheet(sheet: Any) -> dict[str, Any]:
    """Map the drop-in null controls (uniform, shuffled: commit rate <= allowed) to the benchmark control keys.

    The drop-in controls test commit refusal, not a CER gap: ``shuffled`` = time-shuffled calibration frames,
    ``zeros`` and ``null_commit`` = near-uniform frames (no signal). ``sheet``: as :func:`guarantee_from_sheet`.
    """
    sheet = _sheet_dict(sheet)
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
                      B: int = 2000, seed: int = 0, metric_version: str = DEFAULT_METRIC_VERSION) -> dict[str, Any]:
    """Safe WPM from benchmark :class:`~fidetype.benchmark.scoring.TrialScore` objects (needs ``neural_s``).

    Sentence-level commits. ``metric_version``: ``"0.2"`` (default, with the adopted reading cost) or ``"0.1"``.
    """
    return safe_wpm([s.committed for s in scores], [s.committed and not s.wrong_commit for s in scores],
                    [s.n_w for s in scores], [s.n_c for s in scores], [s.neural_s for s in scores],
                    guarantee=guarantee, rule=rule, timing=timing,
                    clusters=[s.clusters for s in scores] if ci_unit else None, ci_unit=ci_unit,
                    controls=controls, gaze_chars_per_min=gaze_chars_per_min, B=B, seed=seed,
                    metric_version=metric_version)


def _normalizer(normalizer: Any) -> Any:
    if normalizer is None:
        return lambda t: " ".join(str(t).split())
    if isinstance(normalizer, str):
        from fidetype.benchmark.registry import normalize

        normalize("", normalizer)  # raises ValueError on an unknown name
        return lambda t: normalize(str(t), normalizer)
    if callable(normalizer):
        return normalizer
    raise TypeError("normalizer must be None, a track normaliser name (for example 'words') or a callable")


def from_decisions(results: Sequence[Any], truths: Sequence[str], neural_s: Sequence[float], sheet: Any, *,
                   normalizer: Any = None, timing: str = "unspecified", controls: Mapping[str, Any] | None = None,
                   **kwargs: Any) -> dict[str, Any]:
    """Safe WPM from the decisions of a drop-in ``TrustGuard`` in one call (P14-45).

    - ``results``: the ``TrustResult`` of each utterance (``guard.decide(...)``), in order;
    - ``truths``: the true text of each utterance;
    - ``neural_s``: the seconds of neural signal of each utterance (say how in ``timing``);
    - ``sheet``: the guard itself, its ``GuaranteeSheet``, or the sheet dict. It gives the
      guarantee (:func:`guarantee_from_sheet`) and, unless ``controls`` is given, the controls
      (:func:`controls_from_sheet`);
    - ``normalizer``: how a commit and its truth are compared, and how words and characters are
      counted. ``None``: whitespace only (the guard's own rule); a track normaliser name of
      :func:`fidetype.benchmark.registry.normalize` (for example ``"words"``); or a callable.

    A commit is right when ``normalizer(result.text) == normalizer(truth)``. Other keyword
    arguments go to :func:`safe_wpm` (for example ``B``, ``seed``, ``rule``, ``metric_version``).
    The result is the same report as :func:`safe_wpm` with the five lists built by hand: by
    default ``safe-wpm/0.2`` with the adopted reading cost; ``metric_version="0.1"`` for v0.1.
    """
    results, truths, neural_s = list(results), list(truths), list(neural_s)
    if not len(results) == len(truths) == len(neural_s):
        raise ValueError(f"results, truths and neural_s must have the same length "
                         f"({len(results)}, {len(truths)}, {len(neural_s)})")
    norm = _normalizer(normalizer)
    sh = _sheet_dict(sheet)
    committed = [r.action == "commit" for r in results]
    nt = [norm(t) for t in truths]
    correct = [c and norm(r.text or "") == t for c, r, t in zip(committed, results, nt)]
    return safe_wpm(committed, correct, n_words=[len(t.split()) for t in nt], n_chars=[len(t) for t in nt],
                    neural_s=neural_s, guarantee=guarantee_from_sheet(sh),
                    controls=controls_from_sheet(sh) if controls is None else controls, timing=timing, **kwargs)


def load_trials_jsonl(path: str, language: str | None = None) -> dict[str, list]:
    """Read a per-trial JSON Lines file for the CLI.

    One object per trial: ``committed`` (bool), ``correct`` (bool), and
    either ``truth`` (text; lengths taken from it) or ``n_words`` +
    ``n_chars``; ``neural_s`` (seconds; optional if ``--chars-per-min``
    is given); optional ``cluster`` (string) for the bootstrap.
    ``safe-wpm/0.2`` fields (ignored by v0.1): ``complete``
    (default true), ``committed_text`` (with ``truth``: sets ``correct``,
    ``committed_words`` and ``penalty_chars`` by :func:`prefix_outcome`, in
    ``correct_v02``; ``correct`` then means the exact sentence, as in v0.1)
    or ``committed_words`` + ``penalty_chars``; ``speech_s``; ``n_commits`` (P5-27: the number of
    append-only commits of the trial; default 1 if committed).

    ``language`` (P14-34, optional BCP 47 tag): count the words of ``truth``
    with :mod:`fidetype.lang`. A language without word boundaries (``zh``)
    raises :class:`fidetype.lang.WordsNotDefinedError`: safe WPM is not
    defined for it. ``None`` (default) keeps the v0.1 rule (``str.split``).
    """
    import json

    count_words: Any = lambda t: len(t.split())  # noqa: E731 (the v0.1 rule)
    if language is not None:
        from fidetype.lang import get as get_language

        count_words = get_language(language).count_words

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
                nw, nc = count_words(t), len(t)
            else:
                nw, nc = d["n_words"], d["n_chars"]
            cols["committed"].append(bool(d["committed"]))
            cols["correct"].append(bool(d.get("correct", False)))
            cols["n_words"].append(float(nw))
            cols["n_chars"].append(float(nc))
            cols["neural_s"].append(float(d["neural_s"]) if d.get("neural_s") is not None else math.nan)
            cols["cluster"].append(str(d["cluster"]) if d.get("cluster") is not None else "")
            # safe-wpm/0.2 fields; v0.1 ignores them
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
        kind = "adopted" if r.get("adopted_headline", True) else "sensitivity variant"
        vs += f" [{DEFINITION_V02}, {kind}; {r.get('n_prefix_commits', 0)} prefix commits]"
    else:
        vs += f" [{r.get('definition', DEFINITION)}]"
    return (f"safe WPM {vs} ({r['status']}; {g}; test wrong-commit {r['n_wrong_commits']}/{r['n_trials']} = "
            f"{r['measured_wrong_commit']:.4f}; commits {r['n_commits']}; unguarded {r['unguarded_wpm']:.2f}; "
            f"no-BCI {r.get('no_bci_wpm') or float('nan'):.2f})")


CALIBRATION_INTERVAL = ("safe-wpm-calibration-interval/0.1 (adopted 2026-11-22 with safe-wpm/0.2: a headline needs "
                        "K >= 80 partition-only calibration draws)")
#: The adopted minimum number of calibration draws for a headline interval (docs/safe-wpm.md section 6b).
MIN_CALIBRATION_DRAWS = 80
#: ``draw_scheme`` values of :func:`calibration_draw_interval`. Only ``"partition"`` is adopted.
DRAW_SCHEMES = ("partition", "resample")


class CalibrationIntervalWarning(UserWarning):
    """A calibration-draw interval that is not an adopted headline (K < 80 or draws not partition-only)."""


def calibration_draw_interval(draws: Sequence[Mapping[str, Any]], n_words: Sequence[float],
                              n_chars: Sequence[float], neural_s: Sequence[float], *,
                              rule: CorrectionRule = CorrectionRule(), B: int = 2000, seed: int = 0,
                              level: float = 0.95, reference: float | None = None,
                              credit_statuses: Sequence[str] = ("certified",),
                              metric_version: str = DEFAULT_METRIC_VERSION,
                              read_s_per_commit: float | None = None, read_s_per_word: float | None = None,
                              draw_scheme: str | None = None) -> dict[str, Any]:
    """Safe-WPM interval over calibration draws and evaluation trials (reporting addition, adopted 2026-11-22).

    The usual ``safe_wpm`` CI is a trial bootstrap with the decisions fixed,
    so it is conditional on one calibration. This function takes K
    calibration draws (each draw = one full re-calibration of the guard,
    then its decisions on the SAME evaluation trials) and returns a
    two-level bootstrap interval (P15-29):

    * inner level: the same ``B`` multinomial trial resamples for every
      draw (``numpy.random.default_rng(seed).integers(0, n, n)`` per
      resample, so K = 1 gives the usual trial-bootstrap CI);
    * credit rule: a draw adds its values only if its ``safe_wpm`` status is
      in ``credit_statuses`` (default: ``certified``); any other draw
      (refused, not-certified, above-alpha, vacuous) adds 0.0 to every
      resample;
    * interval: percentiles of the pooled K x B values at ``level``;
      point: the mean of the K draw values.

    ``metric_version`` (P14-61): ``"0.2"`` (default; the adopted reading
    cost, see :func:`safe_wpm`) or ``"0.1"`` (to reproduce old intervals).

    ``draws``: one mapping per draw with ``committed`` and ``correct`` (one
    bool per evaluation trial) and ``guarantee`` (as for :func:`safe_wpm`),
    or ``{"refused": True}`` for a calibration that produced no guard. With
    v0.2 a draw may also give ``complete``, ``committed_words`` and
    ``penalty_chars`` (prefix commits, as for :func:`safe_wpm`).
    ``reference`` (optional, e.g. the no-BCI WPM) adds
    ``lower_above_reference``. Also returned: the law-of-total-variance
    decomposition (within-draw and between-draw SD) and its normal interval
    as a cross-check, the count of non-credited draws and the between-draw
    SD of the credited draws only.

    Adopted rules for a headline interval (docs/safe-wpm.md section 6b):
    K >= :data:`MIN_CALIBRATION_DRAWS` (80) draws, and partition-only draws
    (``draw_scheme="partition"``: a new split of the calibration set per
    draw, no resample with replacement inside a part). The function cannot
    see how the draws were made, so the caller states it in
    ``draw_scheme`` (``"partition"`` or ``"resample"``; ``None`` = not
    stated). If K < 80 or the draws are not stated as partition-only, it
    gives a :class:`CalibrationIntervalWarning` and sets
    ``adopted_headline`` to False with the reasons in
    ``not_headline_because``. The numbers do not change.
    """
    if not 0.0 < float(level) < 1.0:
        raise ValueError("level must be a confidence level in (0, 1), e.g. 0.95")
    if int(B) < 2:
        raise ValueError("B must be >= 2")
    if not draws:
        raise ValueError("draws is empty: give at least one calibration draw")
    if metric_version not in METRIC_VERSIONS:
        raise ValueError(f"metric_version must be one of {METRIC_VERSIONS}, not {metric_version!r}")
    if draw_scheme is not None and draw_scheme not in DRAW_SCHEMES:
        raise ValueError(f"draw_scheme must be one of {DRAW_SCHEMES} or None, not {draw_scheme!r}")
    v02 = metric_version == "0.2"
    if not v02 and any(x not in (None, 0, 0.0) for x in (read_s_per_commit, read_s_per_word)):
        raise ValueError("read_s_per_commit / read_s_per_word are safe-wpm/0.2 fields; pass metric_version='0.2'")
    rsc = (READ_S_PER_COMMIT if read_s_per_commit is None else float(read_s_per_commit)) if v02 else 0.0
    rsw = (READ_S_PER_WORD if read_s_per_word is None else float(read_s_per_word)) if v02 else 0.0
    ns = np.asarray(neural_s, float)
    nw = np.asarray(n_words, float)
    nc = np.asarray(n_chars, float)
    n = len(ns)
    if n == 0 or len(nw) != n or len(nc) != n:
        raise ValueError("n_words, n_chars and neural_s must be non-empty and of the same length")
    rng = np.random.default_rng(seed)
    W = np.empty((int(B), n))
    for b in range(int(B)):
        W[b] = np.bincount(rng.integers(0, n, n), minlength=n)
    t_neural = W @ ns
    q = [(1.0 - level) / 2.0 * 100.0, (1.0 + level) / 2.0 * 100.0]
    values, statuses, cond, per_draw = [], [], [], []
    v02_keys = ("complete", "committed_words", "penalty_chars")
    for k, d in enumerate(draws):
        if d.get("refused"):
            st, v, vals, info = "refused", 0.0, np.zeros(int(B)), {}
        else:
            for key in ("committed", "correct"):
                if len(d.get(key, ())) != n:
                    raise ValueError(f"draw {k}: {key!r} must have one value per evaluation trial ({n})")
            extra = {key: d[key] for key in v02_keys if d.get(key) is not None}
            if extra and not v02:
                raise ValueError(f"draw {k}: {sorted(extra)} are safe-wpm/0.2 fields; pass metric_version='0.2'")
            kw02 = dict(read_s_per_commit=rsc, read_s_per_word=rsw, **extra) if v02 else {}
            r = safe_wpm(d["committed"], d["correct"], nw, nc, ns, guarantee=d.get("guarantee"), rule=rule,
                         gaze_chars_per_min=None, metric_version=metric_version, **kw02)
            st = r["status"]
            info = {"n_commits": r["n_commits"], "n_wrong_commits": r["n_wrong_commits"]}
            if st in credit_statuses and r["value"] is not None:
                cm = np.asarray(d["committed"], bool)
                ok = cm & np.asarray(d["correct"], bool)
                full = np.ones(n, bool) if extra.get("complete") is None else np.asarray(extra["complete"], bool)
                part = cm & ~full
                kwd = (np.full(n, np.nan) if extra.get("committed_words") is None
                       else np.asarray(extra["committed_words"], float))
                pch = (np.full(n, np.nan) if extra.get("penalty_chars") is None
                       else np.asarray(extra["penalty_chars"], float))
                credit_w = np.where(part, np.nan_to_num(kwd), nw)
                pen = rule.penalty(np.where(part, np.nan_to_num(pch), nc))
                read = rsc + rsw * np.where(np.isfinite(kwd), kwd, nw)
                credit = W @ np.where(ok, credit_w, 0.0)
                den = t_neural + W @ np.where(cm & ~ok, pen, 0.0) + W @ np.where(cm, read, 0.0)
                vals = np.where(den > 0, 60.0 * credit / np.where(den > 0, den, 1.0), 0.0)
                v = float(r["value"])
            else:
                v, vals = 0.0, np.zeros(int(B))
        values.append(v)
        statuses.append(st)
        cond.append(vals)
        per_draw.append({"value": v, "status": st, "conditional_interval": [float(x) for x in np.percentile(vals, q)],
                         **info})
    pooled = np.concatenate(cond)
    lo, hi = (float(x) for x in np.percentile(pooled, q))
    vals_arr = np.asarray(values)
    K = len(values)
    mean = float(vals_arr.mean())
    sd_between = float(vals_arr.std(ddof=1)) if K > 1 else 0.0
    credited = np.asarray([x for x, s in zip(values, statuses) if s in credit_statuses])
    var_within = float(np.mean([c.var(ddof=1) for c in cond]))
    sd_total = math.sqrt(var_within + sd_between ** 2)
    from statistics import NormalDist

    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    why = []
    if K < MIN_CALIBRATION_DRAWS:
        why.append(f"K = {K} calibration draws (a headline needs K >= {MIN_CALIBRATION_DRAWS})")
    if draw_scheme != "partition":
        why.append("the draws are not stated as partition-only" if draw_scheme is None else
                   f"draw_scheme {draw_scheme!r} (a headline needs partition-only draws)")
    if v02 and (rsc, rsw) != (READ_S_PER_COMMIT, READ_S_PER_WORD):
        why.append(f"reading cost {rsc:g} s + {rsw:g} s/word (adopted: {READ_S_PER_COMMIT:g} s + "
                   f"{READ_S_PER_WORD:g} s/word)")
    if not v02:
        why.append("safe-wpm/0.1 (the headline metric is safe-wpm/0.2 since 2026-11-22)")
    if rule.to_dict() != CorrectionRule().to_dict():
        why.append(f"correction rule {rule.name!r} is not the aac-gaze-v1 rewrite rule")
    rule_warn = [w for w in why if w.startswith("K =") or "partition" in w]
    if rule_warn:
        import warnings

        warnings.warn("calibration_draw_interval: not an adopted headline interval: " + "; ".join(rule_warn),
                      CalibrationIntervalWarning, stacklevel=2)
    out: dict[str, Any] = {
        "method": CALIBRATION_INTERVAL,
        "description": ("two-level bootstrap: K calibration draws (outer) x B trial resamples of the fixed "
                        "evaluation set (inner, the same resamples in every draw); percentile interval of the "
                        "pooled values; non-credited draws add 0.0"),
        "definition": DEFINITION_V02 if v02 else DEFINITION,
        "adopted_headline": not why,
        "draw_scheme": draw_scheme or "not stated",
        "min_draws": MIN_CALIBRATION_DRAWS,
        "level": float(level), "B": int(B), "seed": int(seed), "n_trials": n,
        "n_draws": K, "credit_statuses": list(credit_statuses),
        "n_credited": int(sum(s in credit_statuses for s in statuses)),
        "n_not_credited": int(sum(s not in credit_statuses for s in statuses)),
        "statuses": {s: statuses.count(s) for s in sorted(set(statuses))},
        "value": mean, "median_draw_value": float(np.median(vals_arr)),
        "draw_value_range": [float(vals_arr.min()), float(vals_arr.max())],
        "interval": [lo, hi],
        "sd_between_draws": sd_between, "sd_within_draw": math.sqrt(var_within), "sd_total": sd_total,
        "sd_between_credited_draws": float(credited.std(ddof=1)) if len(credited) > 1 else None,
        "between_to_within_sd": (sd_between / math.sqrt(var_within)) if var_within > 0 else None,
        "analytic_interval": [mean - z * sd_total, mean + z * sd_total],
        "draws": per_draw,
    }
    if v02:
        out["reading_cost"] = {"read_s_per_commit": rsc, "read_s_per_word": rsw, "model": "aac-gaze-v1"}
    if why:
        out["not_headline_because"] = why
    if reference is not None:
        out["reference"] = float(reference)
        out["lower_above_reference"] = bool(lo > float(reference))
        out["fraction_of_draws_above_reference"] = float(np.mean(vals_arr > float(reference)))
    return out


__all__ = ["DEFINITION", "DEFINITION_V02", "METRIC_VERSIONS", "DEFAULT_METRIC_VERSION", "V02_ADOPTED", "V02_STATUS",
           "READ_S_PER_COMMIT", "READ_S_PER_WORD", "MIN_PREFIX_WORDS", "RISK_SENTENCE", "RISK_PREFIX",
           "prefix_outcome",
           "CorrectionRule", "certification", "model_neural_s", "safe_wpm", "from_trial_scores",
           "summarize_controls", "SHEET_SCOPE", "guarantee_from_sheet", "controls_from_sheet", "from_decisions",
           "load_trials_jsonl", "format_line",
           "CALIBRATION_INTERVAL", "MIN_CALIBRATION_DRAWS", "DRAW_SCHEMES", "CalibrationIntervalWarning",
           "calibration_draw_interval"]
