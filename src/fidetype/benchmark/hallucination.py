"""Hallucination benchmark (P15-07, F2): does a brain-to-text decoder invent text?

The benchmark gives a decoder + trust policy inputs that carry no matching
neural evidence and counts how often the system still **commits** text. It
also measures how many wrong commits on real input read well ("fluent-wrong").
It is a set of tracks next to the open benchmark (:mod:`fidetype.benchmark`),
not a new leaderboard. Docs: ``docs/hallucination-benchmark.md``.

Tracks (protocols ``fidetype.halluc/0.1`` and ``/0.2``; the tracks are the same)
------------------------------------------------------------------------------
``real``
    The held-out trials as recorded. Metrics: commit rate, wrong-commit
    rate (marginal: wrong commits / trials), error among commits, and the
    fluent-wrong rate (wrong **and** fluent commits / trials).
``null``
    ``n_null`` trials drawn with replacement (``rng = default_rng([seed, 7])``,
    ``idx = rng.integers(0, n, n_null)``). Each input is replaced by a
    uniform log-probability matrix of the same shape plus Gaussian noise
    (standard deviation ``noise``), renormalised per frame. Every commit is
    a hallucination.
``scrambled``
    The same ``idx``; the frames of each input are permuted at random
    (the same generator, after the null draws). Every commit is a
    hallucination: the frame order carries the text.
``swapped``
    A derangement ``perm`` of the held-out trials
    (``default_rng([seed, 11])``; no fixed point, and the two trials of a
    pair never share a text). Trial ``j`` gives the **signal** (the
    evidence the trust layer checks); trial ``perm[j]`` gives the
    **language side** (the n-best list or the language-model context).
    A commit of any text other than the truth of trial ``j`` is unsupported
    by the signal. ``leak`` counts commits equal to the truth of the
    language trial.

The recipe is the one of the P15-05 / P15-06 experiments, so the same seed
gives the same control inputs. The generators are numpy ``PCG64``.

Fluency
-------
A wrong commit is *fluent* if a language model finds it plausible:
``log p_LLM(text) / words >= threshold`` (:func:`fidetype.trust.halluc_bound.is_fluent`).
The LLM is optional (``fidetype[llm]``, llama-cpp-python, a local GGUF model).
The deterministic fallback (``conservative``) counts **every** wrong commit as
fluent, so the fluent-wrong rate is then an upper bound (it equals the
wrong-commit rate). A score card always states the fluency mode.

Data flow
---------
1. :func:`make_controls` builds the control inputs from your held-out inputs.
2. :func:`run_tracks` (Python) runs your decoder + trust policy on every
   track and returns :class:`Record` rows, or you run them yourself and write
   a decisions file (:func:`read_decisions`).
3. :func:`to_outcomes` applies the fluency test and drops every text: the
   result has flags only (committed / wrong / fluent / leak per item).
4. :func:`score_outcomes` makes the score card (schema
   ``fidetype.halluc.scorecard/0.2``; with ``protocol="0.1"`` the old
   ``/0.1`` card) with Clopper-Pearson 95 % intervals.

Pass rules
----------
Protocol 0.1 (P15-07): a control track passes if its unsupported commit rate
is at most 0.05. A system that rarely commits passes the swapped track
without a signal check.

Protocol 0.2 (P15-15, pre-registered in
``experiments/2026-11-17-p15-15-halluc-0.2/plan.md``): null and scrambled keep
the 0.05 rule. The swapped track uses a paired test on the same items.
Pair ``j`` = real item ``j`` and swapped item ``j`` (same signal trial).
``R_j`` = real commit, ``S_j`` = unsupported swapped commit. With
``m`` = pairs with any commit and ``Y = n01 + n11`` = pairs with ``S = 1``:

* ``pass``: ``cp_upper(Y, m, alpha) < r / (1 + r)``. Then
  ``P(S) / P(R) <= r`` (error <= alpha; the bound is conservative because
  ``(p01 + p11) / p10 >= (p01 + p11) / (p10 + p11)``).
* ``fail``: not pass and (``m >= m_min`` or ``cp_lower(n01, m, alpha) > r / (1 + r)``).
* ``insufficient evidence``: otherwise. It is never a pass.

Defaults: ``r`` 0.5, ``alpha`` 0.05, ``m_min`` 25 (power >= 0.9 at ratio 0.1).

The benchmark ships no data: the split file (:func:`split_definition`) has
salted SHA-256 trial ids, the control indices and the recipe only.
Command line: ``python -m fidetype.benchmark.hallucination --help``.
Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from fidetype.utils.binomial import clopper_pearson, cp_lower, cp_upper

PROTOCOL_V01 = "fidetype.halluc/0.1"
PROTOCOL_V02 = "fidetype.halluc/0.2"
#: The current protocol (new outcomes, split files and score cards). 0.1 scoring stays available.
PROTOCOL = PROTOCOL_V02
PROTOCOLS = (PROTOCOL_V01, PROTOCOL_V02)
SPLIT_SCHEMA = "fidetype.halluc.split/0.1"
DECISIONS_SCHEMA = "fidetype.halluc.decisions/0.1"
OUTCOMES_SCHEMA = "fidetype.halluc.outcomes/0.1"
SCORECARD_SCHEMA_V01 = "fidetype.halluc.scorecard/0.1"
SCORECARD_SCHEMA = "fidetype.halluc.scorecard/0.2"
TRACKS = ("real", "null", "scrambled", "swapped")
CONTROL_TRACKS = ("null", "scrambled", "swapped")
DEFAULT_SEED = 0
DEFAULT_N_NULL = 300
DEFAULT_NOISE = 0.05
#: A control track passes if its commit rate is at most this value (as ``scoring.NULL_COMMIT_MAX``).
CONTROL_COMMIT_MAX = 0.05
#: Protocol 0.2 swapped-track rule (P15-15 pre-registration): P(swapped commit) / P(real commit) <= SWAP_RATIO_MAX.
SWAP_RATIO_MAX = 0.5
SWAP_ALPHA = 0.05
#: Pairs with any commit needed before a non-pass counts as "fail" (power >= 0.9 at ratio 0.1, n11 = 0).
SWAP_M_MIN = 25
PASS, FAIL, INSUFFICIENT = "pass", "fail", "insufficient evidence"
#: Fluency threshold (LLM log-probability per word) of the P15-05 T15 run (Qwen2.5-1.5B-Instruct Q4_K_M).
DEFAULT_FLUENT_THRESHOLD = -7.88165954200173


# ---------------------------------------------------------------------------
# control inputs
# ---------------------------------------------------------------------------


def swap_permutation(texts: Sequence[str], seed: int = DEFAULT_SEED) -> list[int]:
    """Derangement of ``range(n)`` with ``texts[perm[j]] != texts[j]`` for every ``j`` (needs n >= 2).

    Same algorithm and generator as P15-05 / P15-06 (``default_rng([seed, 11])``).
    """
    n = len(texts)
    if n < 2:
        raise ValueError("the swapped track needs at least 2 trials")
    if len(set(texts)) < 2:
        raise ValueError("the swapped track needs at least 2 different texts")
    rng = np.random.default_rng([seed, 11])
    while True:
        p = rng.permutation(n)
        bad = [j for j in range(n) if p[j] == j or texts[p[j]] == texts[j]]
        if not bad:
            return [int(v) for v in p]
        for j in bad:
            k = int(rng.integers(0, n))
            p[j], p[k] = p[k], p[j]
        if all(p[j] != j and texts[p[j]] != texts[j] for j in range(n)):
            return [int(v) for v in p]


@dataclass
class ControlSet:
    """The control inputs of one held-out set (see the module docstring)."""

    seed: int
    noise: float
    null_idx: list[int]
    null_inputs: list[np.ndarray]
    scrambled_inputs: list[np.ndarray]
    frame_perms: list[list[int]]
    swap_perm: list[int]

    @property
    def scrambled_idx(self) -> list[int]:
        return self.null_idx

    def digest(self) -> str:
        """SHA-256 over the float32 bytes of all null and scrambled inputs, in order (a check, not a key)."""
        h = hashlib.sha256()
        for a in [*self.null_inputs, *self.scrambled_inputs]:
            h.update(np.ascontiguousarray(a, dtype=np.float32).tobytes())
        return h.hexdigest()


def make_controls(xs: Sequence[np.ndarray], texts: Sequence[str], *, seed: int = DEFAULT_SEED,
                  n_null: int = DEFAULT_N_NULL, noise: float = DEFAULT_NOISE,
                  vocab_size: int | None = None) -> ControlSet:
    """Build the null, scrambled and swapped controls of held-out inputs ``xs`` (each ``(T, V)``).

    ``vocab_size`` is the width of the null log-probabilities (default: ``V`` of each input).
    The draw order is fixed: ``idx``, then one noise matrix per null item, then one frame
    permutation per scrambled item (as P15-06 ``run_arm``).
    """
    n = len(xs)
    if n == 0:
        raise ValueError("no held-out inputs")
    if len(texts) != n:
        raise ValueError("xs and texts differ in length")
    rng = np.random.default_rng([seed, 7])
    idx = [int(i) for i in rng.integers(0, n, n_null)]
    nulls = []
    for i in idx:
        x = np.asarray(xs[i])
        V = int(vocab_size or x.shape[1])
        z = np.full((x.shape[0], V), -math.log(V)) + noise * rng.standard_normal((x.shape[0], V))
        z = (z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32)
        nulls.append(z)
    scr, perms = [], []
    for i in idx:
        x = np.asarray(xs[i])
        p = rng.permutation(x.shape[0])
        perms.append([int(v) for v in p])
        scr.append(x[p])
    return ControlSet(seed=seed, noise=noise, null_idx=idx, null_inputs=nulls, scrambled_inputs=scr,
                      frame_perms=perms, swap_perm=swap_permutation(list(texts), seed))


def trial_hash(dataset: str, trial_id: str) -> str:
    """Salted trial id for public files: ``sha256("<dataset>|<trial_id>")``, first 16 hex digits."""
    return hashlib.sha256(f"{dataset}|{trial_id}".encode("utf-8")).hexdigest()[:16]


def ids_from_rule(split: Mapping) -> list[tuple[str, int]]:
    """Held-out trial ids of a split file that states ``id_sessions`` (P15-20), in held-out order.

    Returns ``(trial_id, hdf5_val_index)`` pairs. For ``b2t25-t15-val-eval`` the id is
    ``<session>|val|<i>`` with ``i`` = position inside the session's ``val_eval`` list (odd keys of
    ``data_val.hdf5`` in sorted order), so the HDF5 ``val`` index is ``2i + 1``. Excluded trials keep their ``i``.
    """
    out = []
    for s in split["id_sessions"]:
        skip = set(s.get("excluded", []))
        out += [(f"{s['session']}|val|{i}", 2 * i + 1) for i in range(s["n_val_eval"]) if i not in skip]
    return out


def split_definition(dataset: str, trial_ids: Sequence[str], texts: Sequence[str], controls: ControlSet, *,
                     licence: str, rule: str, n_null: int | None = None) -> dict:
    """The public split file of one held-out set: hashes, control indices and the recipe; no text, no signal.

    ``text_sha256`` lets a user check that a rebuilt truth matches without the file holding the text.
    """
    if len(trial_ids) != len(texts):
        raise ValueError("trial_ids and texts differ in length")
    return {
        "schema": SPLIT_SCHEMA, "protocol": PROTOCOL, "dataset": dataset, "licence": licence, "rule": rule,
        "seed": controls.seed, "noise": controls.noise, "n_null": n_null if n_null is not None else len(controls.null_idx),
        "n_real": len(trial_ids),
        "trials": [{"h": trial_hash(dataset, t), "text_sha256": hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]}
                   for t, s in zip(trial_ids, texts)],
        "null_idx": list(controls.null_idx),
        "swap_perm": list(controls.swap_perm),
        "controls_sha256": controls.digest(),
    }


def verify_split(split: Mapping, trial_ids: Sequence[str], texts: Sequence[str], controls: ControlSet) -> list[str]:
    """Compare a rebuilt held-out set with a split file. Returns a list of problems (empty: same).

    ``controls_sha256`` is compared last and reported as a warning only: the float bytes can differ
    in the last bit between numpy builds, while the indices and permutations cannot.
    """
    probs = []
    ref = split_definition(split["dataset"], trial_ids, texts, controls, licence=split.get("licence", ""),
                           rule=split.get("rule", ""), n_null=split.get("n_null"))
    for k in ("trials", "null_idx", "swap_perm", "seed"):
        if ref[k] != split[k]:
            probs.append(f"{k} differs")
    if not probs and ref["controls_sha256"] != split.get("controls_sha256"):
        probs.append("warning: controls_sha256 differs (float bytes; indices agree)")
    return probs


# ---------------------------------------------------------------------------
# running a decoder + trust policy
# ---------------------------------------------------------------------------


@dataclass
class Record:
    """One decision on one track item. ``text`` is the committed text (None if no commit)."""

    track: str
    item: int
    signal_trial: int
    language_trial: int
    action: str
    text: str | None
    truth: str
    language_truth: str | None = None

    @property
    def committed(self) -> bool:
        return self.action == "commit"

    @property
    def wrong(self) -> bool:
        """A commit whose text is not the truth of the signal trial (controls: every commit on null / scrambled)."""
        if not self.committed:
            return False
        if self.track in ("null", "scrambled"):
            return True
        return _norm(self.text) != _norm(self.truth)

    @property
    def leak(self) -> bool:
        return (self.track == "swapped" and self.committed and self.language_truth is not None
                and _norm(self.text) == _norm(self.language_truth))


def _norm(s: str | None) -> str:
    return " ".join((s or "").split())


DecideFn = Callable[[np.ndarray], Any]
SwappedDecideFn = Callable[[np.ndarray, int], Any]


def _action_text(r: Any) -> tuple[str, str | None]:
    if isinstance(r, Mapping):
        a, t = r.get("action"), r.get("text")
    else:
        a, t = getattr(r, "action"), getattr(r, "text", None)
    a = str(a).lower()
    if a not in ("commit", "offer", "withhold"):
        raise ValueError(f"unknown action {a!r} (expected commit / offer / withhold)")
    return a, (t if a == "commit" else None)


def run_tracks(decide: DecideFn, xs: Sequence[np.ndarray], texts: Sequence[str], *,
               controls: ControlSet | None = None, decide_swapped: SwappedDecideFn | None = None,
               tracks: Sequence[str] = TRACKS, seed: int = DEFAULT_SEED, n_null: int = DEFAULT_N_NULL,
               progress: Callable[[str, int], None] | None = None) -> list[Record]:
    """Run a decoder + trust policy on every track. Returns one :class:`Record` per decision.

    ``decide(x)`` returns an object or dict with ``action`` (``"commit"``, ``"offer"`` or
    ``"withhold"``) and ``text`` (for example :meth:`fidetype.trust.TrustGuard.decide`).
    ``decide_swapped(x_signal, language_trial)`` decides the signal ``x_signal`` with the
    language side of held-out trial ``language_trial``; without it, the swapped track is skipped.
    """
    texts = [_norm(t) for t in texts]
    ctl = controls or make_controls(xs, texts, seed=seed, n_null=n_null)
    out: list[Record] = []
    if "real" in tracks:
        for i, x in enumerate(xs):
            a, t = _action_text(decide(x))
            out.append(Record("real", i, i, i, a, t, texts[i]))
            if progress:
                progress("real", i)
    for kind, inputs in (("null", ctl.null_inputs), ("scrambled", ctl.scrambled_inputs)):
        if kind not in tracks:
            continue
        for k, (i, z) in enumerate(zip(ctl.null_idx, inputs)):
            a, t = _action_text(decide(z))
            out.append(Record(kind, k, i, i, a, t, texts[i]))
            if progress:
                progress(kind, k)
    if "swapped" in tracks and decide_swapped is not None:
        for j, i in enumerate(ctl.swap_perm):
            a, t = _action_text(decide_swapped(xs[j], i))
            out.append(Record("swapped", j, j, i, a, t, texts[j], texts[i]))
            if progress:
                progress("swapped", j)
    return out


# ---------------------------------------------------------------------------
# fluency
# ---------------------------------------------------------------------------


class Fluency:
    """Fluency test of a wrong commit. Subclasses set ``mode`` and implement :meth:`is_fluent`."""

    mode = "abstract"

    def is_fluent(self, text: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def describe(self) -> dict:
        return {"mode": self.mode}


class ConservativeFluency(Fluency):
    """Deterministic fallback: every wrong commit counts as fluent (fluent-wrong = wrong-commit; an upper bound)."""

    mode = "conservative"

    def is_fluent(self, text: str) -> bool:
        return True


class LLMFluency(Fluency):
    """Fluent if ``scorer.score([text])[0] / words >= threshold`` (``scorer``: any :class:`fidetype.lm.llm.SentenceScorer`).

    An unknown or non-finite score counts as fluent (as :func:`fidetype.trust.halluc_bound.is_fluent`).
    """

    mode = "llm"

    def __init__(self, scorer: Any, threshold: float = DEFAULT_FLUENT_THRESHOLD, name: str = "") -> None:
        self.scorer = scorer
        self.threshold = float(threshold)
        self.name = name

    def is_fluent(self, text: str) -> bool:
        from fidetype.trust.halluc_bound import is_fluent

        return bool(is_fluent(text, self.scorer, self.threshold))

    def describe(self) -> dict:
        return {"mode": self.mode, "threshold_logp_per_word": self.threshold, "scorer": self.name}

    @classmethod
    def from_gguf(cls, model_path: str, threshold: float = DEFAULT_FLUENT_THRESHOLD, *, n_threads: int = 4,
                  n_ctx: int = 1024, seed: int = 0) -> "LLMFluency":
        """Local GGUF model on the CPU (needs ``fidetype[llm]``). Greedy scoring; deterministic per build."""
        from fidetype.lm.llm import CachedScorer, LlamaCppLLM

        llm = LlamaCppLLM(model_path, n_threads=n_threads, n_ctx=n_ctx, seed=seed)
        return cls(CachedScorer(llm), threshold, name=f"llama-cpp:{Path(model_path).name}")


class TableFluency(Fluency):
    """Fluency from a precomputed table ``text -> log-prob`` (for example an LLM cache); a missing text counts as fluent."""

    mode = "llm-table"

    def __init__(self, table: Mapping[str, float], threshold: float = DEFAULT_FLUENT_THRESHOLD, name: str = "") -> None:
        self.table = table
        self.threshold = float(threshold)
        self.name = name
        self.missing = 0

    def is_fluent(self, text: str) -> bool:
        n = len(text.split())
        if n == 0:
            return False
        v = self.table.get(text)
        if v is None or not math.isfinite(float(v)):
            self.missing += v is None
            return True
        return float(v) / n >= self.threshold

    def describe(self) -> dict:
        return {"mode": self.mode, "threshold_logp_per_word": self.threshold, "scorer": self.name,
                "missing_scores_counted_fluent": self.missing}


# ---------------------------------------------------------------------------
# outcomes (flags only) and the score card
# ---------------------------------------------------------------------------


def to_outcomes(records: Iterable[Record], fluency: Fluency | None = None, *, dataset: str = "",
                system: str = "", meta: Mapping | None = None) -> dict:
    """Flags per track item, in item order; no text. ``fluent`` is ``-`` where the item is not a wrong commit."""
    fl = fluency or ConservativeFluency()
    by: dict[str, list[Record]] = {}
    for r in records:
        by.setdefault(r.track, []).append(r)
    tracks = {}
    for k in TRACKS:
        rs = sorted(by.get(k, []), key=lambda r: r.item)
        if not rs:
            continue
        flu = "".join(("1" if fl.is_fluent(_norm(r.text)) else "0") if r.wrong else "-" for r in rs)
        t = {"n": len(rs), "committed": "".join("1" if r.committed else "0" for r in rs),
             "wrong": "".join("1" if r.wrong else "0" for r in rs), "fluent": flu}
        if k == "swapped":
            t["leak"] = "".join("1" if r.leak else "0" for r in rs)
        tracks[k] = t
    return {"schema": OUTCOMES_SCHEMA, "protocol": PROTOCOL, "dataset": dataset, "system": system,
            "fluency": fl.describe(), "meta": dict(meta or {}), "tracks": tracks}


def _rate(k: int, n: int) -> dict:
    return {"k": int(k), "n": int(n), "value": (k / n) if n else None, "cp95": clopper_pearson(k, n)}


def protocol_name(protocol: str) -> str:
    """``"0.1"`` / ``"0.2"`` or the full name -> the full protocol name (ValueError if unknown)."""
    p = str(protocol)
    full = p if p.startswith("fidetype.halluc/") else f"fidetype.halluc/{p}"
    if full not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r} (known: {', '.join(PROTOCOLS)})")
    return full


def paired_swap_test(real_committed: str, swapped_wrong: str, *, ratio_max: float = SWAP_RATIO_MAX,
                     alpha: float = SWAP_ALPHA, m_min: int = SWAP_M_MIN) -> dict:
    """Protocol 0.2 swapped-track test on paired flags (see the module docstring).

    ``real_committed[j]`` / ``swapped_wrong[j]`` are the ``"0"`` / ``"1"`` flags of pair ``j`` (same signal trial).
    Returns the cell counts, the bounds and ``verdict`` (``pass`` / ``fail`` / ``insufficient evidence``).
    """
    if len(real_committed) != len(swapped_wrong):
        raise ValueError(f"paired test: {len(real_committed)} real flags, {len(swapped_wrong)} swapped flags")
    n10 = n01 = n11 = 0
    for a, b in zip(real_committed, swapped_wrong):
        if a == "1" and b == "1":
            n11 += 1
        elif a == "1":
            n10 += 1
        elif b == "1":
            n01 += 1
    m, y = n10 + n01 + n11, n01 + n11
    theta_r = ratio_max / (1.0 + ratio_max)
    upper = cp_upper(y, m, alpha)
    lower01 = cp_lower(n01, m, alpha)
    if m > 0 and upper < theta_r:
        verdict = PASS
    elif m >= m_min or lower01 > theta_r:
        verdict = FAIL
    else:
        verdict = INSUFFICIENT
    rc, sc = n10 + n11, n01 + n11
    return {"test": "paired: Y = n01 + n11 ~ Binomial(m, theta); pass iff cp_upper(Y, m, alpha) < r / (1 + r)",
            "n": len(real_committed), "n10": n10, "n01": n01, "n11": n11, "m": m, "Y": y,
            "real_commits": rc, "swapped_unsupported_commits": sc,
            "ratio_estimate": (sc / rc) if rc else None,
            "theta_hat": (y / m) if m else None, "theta_upper": upper, "theta_r": theta_r,
            "n01_share_lower": lower01, "ratio_max": ratio_max, "alpha": alpha, "m_min": m_min,
            "verdict": verdict}


def score_outcomes(outcomes: Mapping, *, protocol: str = PROTOCOL, control_commit_max: float = CONTROL_COMMIT_MAX,
                   alpha_wrong: float | None = None, alpha_fluent: float | None = None,
                   swap_ratio_max: float = SWAP_RATIO_MAX, swap_alpha: float = SWAP_ALPHA,
                   swap_m_min: int = SWAP_M_MIN) -> dict:
    """The score card of one outcomes dict under ``protocol`` (default: the current one, 0.2).

    ``protocol="0.1"`` gives the old card, unchanged (P15-07). Protocol 0.2 keeps every 0.1 metric and
    changes the swapped-track pass rule to :func:`paired_swap_test`; each control track gets a ``verdict``
    and the card a ``controls_verdict`` (``pass`` needs all three control tracks).
    """
    proto = protocol_name(protocol)
    card = _score_outcomes_v01(outcomes, control_commit_max=control_commit_max, alpha_wrong=alpha_wrong,
                               alpha_fluent=alpha_fluent)
    if proto == PROTOCOL_V01:
        return card
    card["schema"], card["protocol"] = SCORECARD_SCHEMA, PROTOCOL_V02
    tr = outcomes["tracks"]
    for k in ("null", "scrambled"):
        row = card["tracks"][k]
        if row["status"] == "run":
            row["verdict"] = PASS if row["pass"] else FAIL
    sw = card["tracks"]["swapped"]
    if sw["status"] == "run":
        if tr.get("real") is None:
            raise ValueError("protocol 0.2: the swapped track needs the real track (paired test)")
        sw["pass_v01_rule"] = sw["pass"]
        sw["paired"] = paired_swap_test(tr["real"]["committed"], tr["swapped"]["wrong"], ratio_max=swap_ratio_max,
                                        alpha=swap_alpha, m_min=swap_m_min)
        sw["verdict"] = sw["paired"]["verdict"]
        sw["pass"] = sw["verdict"] == PASS
    run_ctl = card["controls_run"]
    verdicts = [card["tracks"][k]["verdict"] for k in run_ctl]
    if FAIL in verdicts:
        cv = FAIL
    elif card["controls_complete"] and all(v == PASS for v in verdicts):
        cv = PASS
    else:
        cv = INSUFFICIENT
    card["controls_verdict"] = cv
    card["controls_passed"] = cv == PASS
    card["rules"].update({"swap_ratio_max": swap_ratio_max, "swap_alpha": swap_alpha, "swap_m_min": swap_m_min,
                          "swapped_rule": "paired swapped / real commit-ratio test (protocol 0.2)",
                          "null_scrambled_rule": "commit rate <= control_commit_max"})
    if "headline" in card:
        card["headline"]["controls_verdict"] = cv
        if sw["status"] == "run":
            card["headline"]["swapped_verdict"] = sw["verdict"]
    return card


def _score_outcomes_v01(outcomes: Mapping, *, control_commit_max: float = CONTROL_COMMIT_MAX,
                        alpha_wrong: float | None = None, alpha_fluent: float | None = None) -> dict:
    """Protocol 0.1 score card (P15-07; kept unchanged so 0.1 results stay reproducible).

    Pass rules: a control track passes if its commit rate is at most ``control_commit_max``.
    ``controls_passed`` needs every control track that was run. ``alpha_wrong`` / ``alpha_fluent``
    (optional) add point checks of the real-track wrong-commit and fluent-wrong rates.
    """
    if outcomes.get("schema") != OUTCOMES_SCHEMA:
        raise ValueError(f"not an outcomes file (schema {outcomes.get('schema')!r})")
    tr = outcomes["tracks"]
    card: dict[str, Any] = {"schema": SCORECARD_SCHEMA_V01, "protocol": PROTOCOL_V01, "dataset": outcomes.get("dataset", ""),
                            "system": outcomes.get("system", ""), "fluency": dict(outcomes.get("fluency", {})),
                            "meta": dict(outcomes.get("meta", {})), "tracks": {}}
    for k in TRACKS:
        t = tr.get(k)
        if t is None:
            card["tracks"][k] = {"status": "not run"}
            continue
        n = int(t["n"])
        for f in ("committed", "wrong", "fluent"):
            if len(t[f]) != n:
                raise ValueError(f"track {k}: {f} has {len(t[f])} flags, n = {n}")
        c = t["committed"].count("1")
        w = t["wrong"].count("1")
        fw = t["fluent"].count("1")
        row: dict[str, Any] = {"status": "run", "n": n, "commit_rate": _rate(c, n),
                               "wrong_commit_rate": _rate(w, n), "fluent_wrong_rate": _rate(fw, n),
                               "error_among_commits": _rate(w, c), "fluent_among_wrong_commits": _rate(fw, w)}
        if k in CONTROL_TRACKS:
            row["unsupported_commit_rate"] = row["wrong_commit_rate"]
            row["pass"] = (w / n) <= control_commit_max if n else False
        if k == "swapped" and "leak" in t:
            row["leak_commits"] = t["leak"].count("1")
        card["tracks"][k] = row
    run_ctl = [k for k in CONTROL_TRACKS if card["tracks"][k]["status"] == "run"]
    card["controls_run"] = run_ctl
    card["controls_passed"] = bool(run_ctl) and all(card["tracks"][k]["pass"] for k in run_ctl)
    card["controls_complete"] = len(run_ctl) == len(CONTROL_TRACKS)
    card["rules"] = {"control_commit_max": control_commit_max, "alpha_wrong": alpha_wrong, "alpha_fluent": alpha_fluent}
    real = card["tracks"]["real"]
    if real["status"] == "run":
        card["headline"] = {
            "fluent_wrong_rate": real["fluent_wrong_rate"]["value"],
            "fluent_wrong_cp95": real["fluent_wrong_rate"]["cp95"],
            "wrong_commit_rate": real["wrong_commit_rate"]["value"],
            "commit_rate": real["commit_rate"]["value"],
            "control_commits": {k: card["tracks"][k]["commit_rate"]["k"] for k in run_ctl},
        }
        sw = card["tracks"]["swapped"]
        if sw["status"] == "run":
            # About 1: commits follow the language side and ignore the signal; about 0: the signal vetoes them.
            rc = real["commit_rate"]["k"]
            card["headline"]["swapped_to_real_commit_ratio"] = (sw["commit_rate"]["k"] / rc) if rc else None
        if alpha_wrong is not None:
            card["wrong_commit_le_alpha"] = real["wrong_commit_rate"]["value"] <= alpha_wrong
        if alpha_fluent is not None:
            card["fluent_wrong_le_alpha"] = real["fluent_wrong_rate"]["value"] <= alpha_fluent
    return card


def summary_line(card: Mapping) -> str:
    """One line for logs and tables."""
    t = card["tracks"]
    parts = [f"{card.get('dataset', '')}/{card.get('system', '')}"]
    if t["real"]["status"] == "run":
        r = t["real"]
        parts.append(f"real commit {r['commit_rate']['k']}/{r['n']} wrong {r['wrong_commit_rate']['k']} "
                     f"fluent-wrong {r['fluent_wrong_rate']['k']} ({card['fluency'].get('mode')})")
    for k in CONTROL_TRACKS:
        if t[k]["status"] != "run":
            continue
        v = t[k].get("verdict")
        flag = ("" if t[k]["pass"] else " FAIL") if v is None else ("" if v == PASS else f" {v.upper()}")
        extra = ""
        if k == "swapped" and "paired" in t[k]:
            pr = t[k]["paired"]
            extra = f" (paired n10 {pr['n10']} n01 {pr['n01']} n11 {pr['n11']})"
        parts.append(f"{k} {t[k]['commit_rate']['k']}/{t[k]['n']}{flag}{extra}")
    if card.get("protocol") != PROTOCOL_V01:
        parts.append(card.get("protocol", ""))
    return "  ".join(parts)


# ---------------------------------------------------------------------------
# decisions files (for decoders run outside Python)
# ---------------------------------------------------------------------------


def read_truth(path: str | Path) -> dict[str, str]:
    """``{"id": ..., "text": ...}`` per line (the benchmark truth format)."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[str(d["id"])] = _norm(d["text"])
    return out


def read_decisions(path: str | Path, truth: Mapping[str, str], held_out: Sequence[str]) -> list[Record]:
    """Read a decisions JSONL file (schema ``fidetype.halluc.decisions/0.1``) into records.

    One line per decision: ``{"track", "item", "action", "text"}``. ``item`` is the item index of
    the track (real / swapped: the held-out position; null / scrambled: the control index). The
    signal and language trials follow from the split (``held_out`` ids in order, ``null_idx``,
    ``swap_perm``), given in a first header line ``{"schema", "null_idx", "swap_perm"}``.
    """
    lines = [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]
    if not lines or lines[0].get("schema") != DECISIONS_SCHEMA:
        raise ValueError(f"first line must be a header with schema {DECISIONS_SCHEMA!r}")
    head, rows = lines[0], lines[1:]
    texts = [truth[i] for i in held_out]
    nidx, perm = head.get("null_idx", []), head.get("swap_perm", [])
    out, seen = [], set()
    for d in rows:
        k, it = str(d["track"]), int(d["item"])
        if k not in TRACKS:
            raise ValueError(f"unknown track {k!r}")
        if (k, it) in seen:
            raise ValueError(f"duplicate decision {k} {it}")
        seen.add((k, it))
        a, t = _action_text(d)
        if k == "real":
            out.append(Record(k, it, it, it, a, t, texts[it]))
        elif k in ("null", "scrambled"):
            i = int(nidx[it])
            out.append(Record(k, it, i, i, a, t, texts[i]))
        else:
            i = int(perm[it])
            out.append(Record(k, it, it, i, a, t, texts[it], texts[i]))
    for k, n in (("real", len(texts)), ("null", len(nidx)), ("scrambled", len(nidx)), ("swapped", len(perm))):
        got = sum(1 for kk, _ in seen if kk == k)
        if got and got != n:
            raise ValueError(f"track {k}: {got} decisions, expected {n}")
    return out


def _dump(obj: Any, out: str | None) -> None:
    text = json.dumps(obj, indent=1, ensure_ascii=False)
    if out in (None, "-"):
        sys.stdout.write(text + "\n")
    else:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n", encoding="utf-8")


def _load_npz_inputs(path: str) -> tuple[list[str], list[np.ndarray]]:
    z = np.load(path)
    ids = list(z.files)
    return ids, [np.asarray(z[i], dtype=np.float32) for i in ids]


def _fluency_from_args(a) -> Fluency:
    if a.fluency == "conservative":
        return ConservativeFluency()
    if a.fluency == "llm":
        if not a.llm_model:
            raise SystemExit("--fluency llm needs --llm-model PATH (a GGUF file)")
        return LLMFluency.from_gguf(a.llm_model, a.fluent_threshold)
    table = json.loads(Path(a.fluency_table).read_text(encoding="utf-8"))
    return TableFluency(table, a.fluent_threshold, name=Path(a.fluency_table).name)


def cmd_controls(a) -> int:
    ids, xs = _load_npz_inputs(a.inputs)
    truth = read_truth(a.truth)
    texts = [truth[i] for i in ids]
    ctl = make_controls(xs, texts, seed=a.seed, n_null=a.n_null)
    arrays = {f"null/{k:05d}": z for k, z in enumerate(ctl.null_inputs)}
    arrays.update({f"scrambled/{k:05d}": z for k, z in enumerate(ctl.scrambled_inputs)})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, **arrays)
    split = split_definition(a.dataset, ids, texts, ctl, licence=a.licence, rule=a.rule, n_null=a.n_null)
    _dump(split, a.split)
    head = {"schema": DECISIONS_SCHEMA, "null_idx": ctl.null_idx, "swap_perm": ctl.swap_perm,
            "held_out": ids}
    print(f"wrote {len(arrays)} control inputs to {a.out} (local file: it is derived from your data). "
          f"Decisions header: {json.dumps({k: head[k] for k in ('schema',)})} + null_idx + swap_perm (see the split file)",
          file=sys.stderr)
    return 0


def cmd_score(a) -> int:
    truth = read_truth(a.truth)
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    by_h = {trial_hash(split["dataset"], i): i for i in truth}
    try:
        held = [by_h[t["h"]] for t in split["trials"]]
    except KeyError as e:
        raise SystemExit(f"a split trial is missing from the truth file: {e}") from None
    recs = read_decisions(a.decisions, truth, held)
    oc = to_outcomes(recs, _fluency_from_args(a), dataset=split["dataset"], system=a.system)
    if a.outcomes:
        _dump(oc, a.outcomes)
    card = score_outcomes(oc, protocol=a.protocol, alpha_wrong=a.alpha_wrong, alpha_fluent=a.alpha_fluent)
    _dump(card, a.out)
    print(summary_line(card), file=sys.stderr)
    return 0


def _card_diff(a: Any, b: Any, path: str = "card") -> str | None:
    """The first path where two cards differ, or None. Floats may differ in the last bits (the Clopper-Pearson
    bisection gives other last bits on other platforms), so they compare with a relative tolerance of 1e-9."""
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12):
            return None
        return path
    if isinstance(a, dict):
        if not isinstance(b, dict) or a.keys() != b.keys():
            return path
        return next((d for k in a if (d := _card_diff(a[k], b[k], f"{path}.{k}"))), None)
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            return path
        return next((d for i, (x, y) in enumerate(zip(a, b)) if (d := _card_diff(x, y, f"{path}[{i}]"))), None)
    return None if a == b else path


def cmd_rescore(a) -> int:
    oc = json.loads(Path(a.outcomes).read_text(encoding="utf-8"))
    card = score_outcomes(oc, protocol=a.protocol, alpha_wrong=a.alpha_wrong, alpha_fluent=a.alpha_fluent)
    if a.check:
        ref = json.loads(Path(a.check).read_text(encoding="utf-8"))
        ref.pop("rerun", None)  # the rerun recipe (P13-11) is not a scorer output
        rel = (ref.get("meta") or {}).get("outcomes_file")
        if rel and Path(rel).name == Path(a.outcomes).name and "outcomes_file" not in card["meta"]:
            card["meta"] = {**card["meta"], "outcomes_file": rel}  # a pointer the publisher adds to protocol 0.2 cards
        diff = _card_diff(json.loads(json.dumps(card)), ref)
        if diff:
            print(f"score card differs from {a.check} at {diff}", file=sys.stderr)
            return 1
    _dump(card, a.out)
    print(summary_line(card), file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.benchmark.hallucination",
                                 description="Hallucination benchmark (null / scrambled / swapped tracks, fluent-wrong).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("controls", help="build the control inputs and the split file from your held-out inputs")
    p.add_argument("inputs", help="NPZ: one (T, V) log-prob array per held-out trial id, in held-out order")
    p.add_argument("--truth", required=True, help="truth JSONL ({id, text} per line)")
    p.add_argument("--dataset", required=True)
    p.add_argument("--licence", required=True, help="licence of the dataset (for example 'CC0 1.0')")
    p.add_argument("--rule", default="", help="how the held-out set was chosen (one sentence)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--n-null", type=int, default=DEFAULT_N_NULL)
    p.add_argument("--out", required=True, help="control inputs NPZ (local file; do not commit)")
    p.add_argument("--split", required=True, help="split file JSON (hashes only; safe to publish)")
    p.set_defaults(fn=cmd_controls)
    for name in ("score", "rescore"):
        p = sub.add_parser(name, help="score a decisions file" if name == "score"
                           else "score an outcomes file (flags only; what CI runs)")
        if name == "score":
            p.add_argument("decisions", help="decisions JSONL (header line + one line per decision)")
            p.add_argument("--truth", required=True)
            p.add_argument("--split", required=True)
            p.add_argument("--system", default="")
            p.add_argument("--fluency", choices=("conservative", "llm", "table"), default="conservative")
            p.add_argument("--llm-model", default=None, help="GGUF model for --fluency llm (needs fidetype[llm])")
            p.add_argument("--fluency-table", default=None, help="JSON {text: log-prob} for --fluency table")
            p.add_argument("--fluent-threshold", type=float, default=DEFAULT_FLUENT_THRESHOLD)
            p.add_argument("--outcomes", default=None, help="also write the outcomes file (flags only)")
        else:
            p.add_argument("outcomes")
            p.add_argument("--check", default=None, help="exit 1 if the result differs from this score card")
        p.add_argument("--protocol", default=PROTOCOL,
                       help="scoring protocol: 0.2 (default; paired swapped rule) or 0.1 (old fixed 0.05 rule)")
        p.add_argument("--alpha-wrong", type=float, default=None)
        p.add_argument("--alpha-fluent", type=float, default=None)
        p.add_argument("--out", default=None)
        p.set_defaults(fn=cmd_score if name == "score" else cmd_rescore)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
