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

Signal-check tracks (opt-in; P15-56, pre-registered in
``experiments/2026-11-25-p15-56-signal-check-tracks/plan.md``)
--------------------------------------------------------------------------
Three stricter checks of the signal, with their own outcomes and card
(:func:`make_signal_checks`, :func:`run_signal_checks`, :func:`to_signal_outcomes`,
:func:`score_signal_outcomes`). They never change the tracks above, protocol 0.2 or its cards.

``truncated_<pct>`` (25, 50, 75)
    Only the first ``max(1, ceil(f * T))`` frames. Unsupported: any commit that is not a
    proper word prefix of the truth (the full sentence included). 75 has no pass rule.
``noise_mix_<pct>`` (25, 50, 75)
    ``log((1 - lam) softmax(x) + lam exp(q))`` with one null-type noise matrix ``q`` per item
    (``default_rng([seed, 13])``), shared by the levels. Unsupported: text != truth.
``near_miss``
    The signal of trial ``j`` with a language side whose text differs from the truth in 1 or 2
    words (``default_rng([seed, 17])``, words from the held-out vocabulary). Unsupported: text != truth.

Each scored level uses :func:`paired_swap_test` against the real track (same constants).

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


# ---------------------------------------------------------------------------
# signal-check tracks (opt-in; P15-56)
# ---------------------------------------------------------------------------

SIGNAL_PROTOCOL = "fidetype.halluc-signal/0.1"
SIGNAL_OUTCOMES_SCHEMA = "fidetype.halluc.signal-outcomes/0.1"
SIGNAL_CARD_SCHEMA = "fidetype.halluc.signal-card/0.1"
SIGNAL_DECISIONS_SCHEMA = "fidetype.halluc.signal-decisions/0.1"
TRUNC_LEVELS = (0.25, 0.50, 0.75)
#: Truncation levels with a pass rule (at 75 % the speech can be complete).
TRUNC_SCORED = (0.25, 0.50)
NOISE_LEVELS = (0.25, 0.50, 0.75)
NOISE_MIX_TAG = 13
NEAR_MISS_TAG = 17
SIGNAL_FAMILIES = ("truncated", "noise_mix", "near_miss")


def _pct(f: float) -> int:
    return int(round(float(f) * 100))


def truncated_key(f: float) -> str:
    return f"truncated_{_pct(f)}"


def noise_mix_key(lam: float) -> str:
    return f"noise_mix_{_pct(lam)}"


def signal_track_keys(trunc_levels: Sequence[float] = TRUNC_LEVELS,
                      noise_levels: Sequence[float] = NOISE_LEVELS) -> list[str]:
    """Track keys in card order: truncated levels, noise levels, ``near_miss``."""
    return [truncated_key(f) for f in trunc_levels] + [noise_mix_key(v) for v in noise_levels] + ["near_miss"]


def signal_family(track: str) -> str | None:
    """``truncated`` / ``noise_mix`` / ``near_miss`` for a signal-check track key, else None."""
    if track == "near_miss":
        return "near_miss"
    for fam in ("truncated", "noise_mix"):
        if track.startswith(fam + "_"):
            return fam
    return None


def truncate_input(x: np.ndarray, f: float) -> np.ndarray:
    """The first ``max(1, ceil(f * T))`` frames of ``x``."""
    x = np.asarray(x)
    k = max(1, int(math.ceil(float(f) * x.shape[0] - 1e-9)))
    return np.ascontiguousarray(x[:k])


def _log_softmax(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=np.float64)
    m = z.max(axis=1, keepdims=True)
    return z - (m + np.log(np.exp(z - m).sum(axis=1, keepdims=True)))


def noise_matrix(rng: np.random.Generator, T: int, V: int, noise: float = DEFAULT_NOISE) -> np.ndarray:
    """One null-type noise matrix: ``-log V + noise * N(0, 1)``, log-softmax per frame (float64)."""
    return _log_softmax(np.full((T, V), -math.log(V)) + noise * rng.standard_normal((T, V)))


def mix_noise(x: np.ndarray, q: np.ndarray, lam: float) -> np.ndarray:
    """``log((1 - lam) softmax(x) + lam exp(q))`` per frame, float32 (``lam`` = 1: the null input)."""
    p = (1.0 - float(lam)) * np.exp(_log_softmax(x)) + float(lam) * np.exp(np.asarray(q, dtype=np.float64))
    return np.log(np.maximum(p, 1e-300)).astype(np.float32)


def near_miss_text(truth: str, rng: np.random.Generator, pool: Sequence[str]) -> tuple[str, int]:
    """One near-miss of ``truth``: 1 or 2 words replaced by other pool words. Returns ``(text, edits)``."""
    words = _norm(truth).split()
    w = len(words)
    if w == 0:
        raise ValueError("near-miss: empty truth")
    if len(set(pool)) < 2:
        raise ValueError("near-miss: the word pool needs at least 2 different words")
    e = 1 if w == 1 else 1 + int(rng.integers(0, 2))
    pos = sorted(int(p) for p in rng.choice(w, e, replace=False))
    out = list(words)
    for p in pos:
        while True:
            c = pool[int(rng.integers(0, len(pool)))]
            if c != words[p]:
                break
        out[p] = c
    return " ".join(out), e


def word_pool(texts: Sequence[str]) -> list[str]:
    """Sorted set of the words of ``texts`` (the near-miss replacement words)."""
    return sorted({w for t in texts for w in _norm(t).split()})


def near_miss_texts(texts: Sequence[str], seed: int = DEFAULT_SEED) -> tuple[list[str], list[int]]:
    """The near-miss text and its number of edits for every held-out truth (``default_rng([seed, 17])``)."""
    rng = np.random.default_rng([seed, NEAR_MISS_TAG])
    pool = word_pool(texts)
    out, edits = [], []
    for t in texts:
        v, e = near_miss_text(t, rng, pool)
        out.append(v)
        edits.append(e)
    return out, edits


@dataclass
class SignalChecks:
    """The inputs of the signal-check tracks of one held-out set (see the module docstring)."""

    seed: int
    noise: float
    trunc_levels: tuple
    noise_levels: tuple
    truncated: dict  # track key -> list of inputs
    noise_mix: dict  # track key -> list of inputs
    near_miss: list  # near-miss text per item
    near_miss_edits: list

    def inputs(self, track: str) -> list[np.ndarray]:
        return self.truncated[track] if track in self.truncated else self.noise_mix[track]

    def tracks(self) -> list[str]:
        return signal_track_keys(self.trunc_levels, self.noise_levels)

    def digest(self) -> str:
        """SHA-256 over the float32 bytes of all inputs (track order) and the near-miss texts (a check, not a key)."""
        h = hashlib.sha256()
        for k in [*self.truncated, *self.noise_mix]:
            for a in self.inputs(k):
                h.update(np.ascontiguousarray(a, dtype=np.float32).tobytes())
        for v in self.near_miss:
            h.update(v.encode("utf-8") + b"\n")
        return h.hexdigest()


def make_signal_checks(xs: Sequence[np.ndarray], texts: Sequence[str], *, seed: int = DEFAULT_SEED,
                       noise: float = DEFAULT_NOISE, trunc_levels: Sequence[float] = TRUNC_LEVELS,
                       noise_levels: Sequence[float] = NOISE_LEVELS,
                       vocab_size: int | None = None) -> SignalChecks:
    """Build the truncated, noise-mix and near-miss inputs of held-out inputs ``xs`` (each ``(T, V)``).

    Noise: one matrix per item in held-out order from ``default_rng([seed, 13])``, shared by the levels.
    Near-miss texts: :func:`near_miss_texts`. ``vocab_size`` must equal ``V`` if given (mixing needs one width).
    """
    n = len(xs)
    if n == 0:
        raise ValueError("no held-out inputs")
    if len(texts) != n:
        raise ValueError("xs and texts differ in length")
    tr = {truncated_key(f): [truncate_input(x, f) for x in xs] for f in trunc_levels}
    rng = np.random.default_rng([seed, NOISE_MIX_TAG])
    nm: dict = {noise_mix_key(v): [] for v in noise_levels}
    for x in xs:
        x = np.asarray(x)
        V = x.shape[1]
        if vocab_size is not None and int(vocab_size) != V:
            raise ValueError(f"noise mix: input width {V} != vocab_size {vocab_size}")
        q = noise_matrix(rng, x.shape[0], V, noise)
        for v in noise_levels:
            nm[noise_mix_key(v)].append(mix_noise(x, q, v))
    nmt, ed = near_miss_texts(list(texts), seed)
    return SignalChecks(seed=seed, noise=noise, trunc_levels=tuple(trunc_levels), noise_levels=tuple(noise_levels),
                        truncated=tr, noise_mix=nm, near_miss=nmt, near_miss_edits=ed)


NearMissDecideFn = Callable[[np.ndarray, str, int], Any]


def run_signal_checks(decide: DecideFn, xs: Sequence[np.ndarray], texts: Sequence[str], checks: SignalChecks, *,
                      decide_near_miss: NearMissDecideFn | None = None, tracks: Sequence[str] | None = None,
                      with_real: bool = True, progress: Callable[[str, int], None] | None = None) -> list[Record]:
    """Run a decoder + trust policy on the signal-check tracks (and, by default, the real track for the pairs).

    ``decide_near_miss(x_signal, near_miss_text, item)`` decides the signal ``x_signal`` with ``near_miss_text``
    as the language side; without it, ``near_miss`` is skipped. ``language_truth`` of a near-miss record is the
    near-miss text.
    """
    texts = [_norm(t) for t in texts]
    want = list(tracks) if tracks is not None else checks.tracks()
    out: list[Record] = []
    if with_real:
        for i, x in enumerate(xs):
            a, t = _action_text(decide(x))
            out.append(Record("real", i, i, i, a, t, texts[i]))
            if progress:
                progress("real", i)
    for k in want:
        if k == "near_miss":
            if decide_near_miss is None:
                continue
            for j, x in enumerate(xs):
                a, t = _action_text(decide_near_miss(x, checks.near_miss[j], j))
                out.append(Record(k, j, j, j, a, t, texts[j], checks.near_miss[j]))
                if progress:
                    progress(k, j)
            continue
        for j, z in enumerate(checks.inputs(k)):
            a, t = _action_text(decide(z))
            out.append(Record(k, j, j, j, a, t, texts[j]))
            if progress:
                progress(k, j)
    return out


def is_proper_prefix(text: str | None, truth: str) -> bool:
    """True if ``text`` is 1 to (words - 1) leading words of ``truth``."""
    a, b = _norm(text).split(), _norm(truth).split()
    return 0 < len(a) < len(b) and a == b[: len(a)]


def signal_unsupported(r: Record) -> bool:
    """Unsupported commit on a signal-check track (truncated: not a proper word prefix; others: text != truth)."""
    if not r.committed:
        return False
    if signal_family(r.track) == "truncated":
        return not is_proper_prefix(r.text, r.truth)
    return _norm(r.text) != _norm(r.truth)


def to_signal_outcomes(records: Iterable[Record], fluency: Fluency | None = None, *, dataset: str = "",
                       system: str = "", meta: Mapping | None = None) -> dict:
    """Flags per item of the real track and every signal-check track found; no text.

    Per track: ``committed``, ``unsupported`` and ``fluent`` (``-`` where the item is not an unsupported commit;
    real track: ``wrong`` and ``fluent`` as :func:`to_outcomes`). Truncated tracks add ``prefix`` (supported prefix
    commits) and ``full`` (commits of the full truth); ``near_miss`` adds ``near_miss_commit``.
    """
    fl = fluency or ConservativeFluency()
    by: dict[str, list[Record]] = {}
    for r in records:
        by.setdefault(r.track, []).append(r)
    order = ["real"] + sorted((k for k in by if signal_family(k)),
                              key=lambda k: (SIGNAL_FAMILIES.index(signal_family(k)), k))
    tracks = {}
    for k in order:
        rs = sorted(by.get(k, []), key=lambda r: r.item)
        if not rs:
            continue
        if [r.item for r in rs] != list(range(len(rs))):
            raise ValueError(f"track {k}: items are not 0..n-1 once each")
        if k == "real":
            bad = [r.wrong for r in rs]
        else:
            bad = [signal_unsupported(r) for r in rs]
        t = {"n": len(rs), "committed": "".join("1" if r.committed else "0" for r in rs),
             ("wrong" if k == "real" else "unsupported"): "".join("1" if b else "0" for b in bad),
             "fluent": "".join(("1" if fl.is_fluent(_norm(r.text)) else "0") if b else "-" for r, b in zip(rs, bad))}
        fam = signal_family(k)
        if fam == "truncated":
            t["prefix"] = "".join("1" if r.committed and is_proper_prefix(r.text, r.truth) else "0" for r in rs)
            t["full"] = "".join("1" if r.committed and _norm(r.text) == _norm(r.truth) else "0" for r in rs)
        elif fam == "near_miss":
            t["near_miss_commit"] = "".join(
                "1" if r.committed and r.language_truth is not None and _norm(r.text) == _norm(r.language_truth)
                else "0" for r in rs)
        tracks[k] = t
    return {"schema": SIGNAL_OUTCOMES_SCHEMA, "protocol": SIGNAL_PROTOCOL, "dataset": dataset, "system": system,
            "fluency": fl.describe(), "meta": dict(meta or {}), "tracks": tracks}


def _combine(verdicts: Sequence[str]) -> str:
    if not verdicts:
        return INSUFFICIENT
    if FAIL in verdicts:
        return FAIL
    return PASS if all(v == PASS for v in verdicts) else INSUFFICIENT


def score_signal_outcomes(outcomes: Mapping, *, ratio_max: float = SWAP_RATIO_MAX, alpha: float = SWAP_ALPHA,
                          m_min: int = SWAP_M_MIN, trunc_scored: Sequence[float] = TRUNC_SCORED) -> dict:
    """The signal-check card (schema ``fidetype.halluc.signal-card/0.1``) of one signal outcomes dict.

    Every track is paired with the real track (:func:`paired_swap_test`). Truncated levels outside
    ``trunc_scored`` get ``verdict = "no rule"``. ``families`` combines the scored levels of each family,
    ``signal_checks_verdict`` the three families (``pass`` needs all three).
    """
    if outcomes.get("schema") != SIGNAL_OUTCOMES_SCHEMA:
        raise ValueError(f"not a signal outcomes file (schema {outcomes.get('schema')!r})")
    tr = outcomes["tracks"]
    real = tr.get("real")
    if real is None:
        raise ValueError("signal checks need the real track (paired test)")
    scored_tr = {truncated_key(f) for f in trunc_scored}
    card: dict[str, Any] = {"schema": SIGNAL_CARD_SCHEMA, "protocol": SIGNAL_PROTOCOL,
                            "dataset": outcomes.get("dataset", ""), "system": outcomes.get("system", ""),
                            "fluency": dict(outcomes.get("fluency", {})), "meta": dict(outcomes.get("meta", {})),
                            "real": {"n": int(real["n"]), "commits": real["committed"].count("1"),
                                     "wrong_commits": real["wrong"].count("1")},
                            "tracks": {}}
    fam_verdicts: dict[str, list[str]] = {f: [] for f in SIGNAL_FAMILIES}
    for k, t in tr.items():
        fam = signal_family(k)
        if fam is None:
            continue
        n = int(t["n"])
        if n != int(real["n"]):
            raise ValueError(f"track {k}: {n} items, real track {real['n']}")
        for f in ("committed", "unsupported", "fluent"):
            if len(t[f]) != n:
                raise ValueError(f"track {k}: {f} has {len(t[f])} flags, n = {n}")
        c, u, fu = t["committed"].count("1"), t["unsupported"].count("1"), t["fluent"].count("1")
        row: dict[str, Any] = {"family": fam, "n": n, "commit_rate": _rate(c, n), "unsupported_commit_rate": _rate(u, n),
                               "fluent_unsupported_rate": _rate(fu, n), "unsupported_among_commits": _rate(u, c)}
        for extra in ("prefix", "full", "near_miss_commit"):
            if extra in t:
                row[f"{extra}_commits"] = t[extra].count("1")
        row["paired"] = paired_swap_test(real["committed"], t["unsupported"], ratio_max=ratio_max, alpha=alpha,
                                         m_min=m_min)
        if fam == "truncated" and k not in scored_tr:
            row["verdict"] = "no rule"
        else:
            row["verdict"] = row["paired"]["verdict"]
            fam_verdicts[fam].append(row["verdict"])
        card["tracks"][k] = row
    card["families"] = {f: {"verdict": _combine(v) if v else "not run", "levels_scored": len(v)}
                        for f, v in fam_verdicts.items()}
    run = [f for f in SIGNAL_FAMILIES if fam_verdicts[f]]
    vs = [card["families"][f]["verdict"] for f in run]
    if FAIL in vs:
        sv = FAIL
    elif len(run) == len(SIGNAL_FAMILIES) and all(v == PASS for v in vs):
        sv = PASS
    else:
        sv = INSUFFICIENT
    card["signal_checks_verdict"] = sv
    card["signal_checks_complete"] = len(run) == len(SIGNAL_FAMILIES)
    card["rules"] = {"ratio_max": ratio_max, "alpha": alpha, "m_min": m_min,
                     "truncated_scored_levels": [truncated_key(f) for f in trunc_scored],
                     "rule": "paired: pass iff cp_upper(n01 + n11, m, alpha) < r / (1 + r), per scored level"}
    return card


def signal_summary_line(card: Mapping) -> str:
    """One line for logs and tables."""
    parts = [f"{card.get('dataset', '')}/{card.get('system', '')}",
             f"real commit {card['real']['commits']}/{card['real']['n']}"]
    for k, r in card["tracks"].items():
        p = r["paired"]
        parts.append(f"{k} {r['unsupported_commit_rate']['k']}/{r['commit_rate']['k']}"
                     f" m{p['m']} {r['verdict']}")
    parts.append(f"=> {card['signal_checks_verdict']}")
    return "  ".join(parts)


def read_signal_decisions(path: str | Path, truth: Mapping[str, str], held_out: Sequence[str]) -> list[Record]:
    """Read a signal decisions JSONL file (schema ``fidetype.halluc.signal-decisions/0.1``) into records.

    First line: a header ``{"schema", "seed"}``. Then one line per decision ``{"track", "item", "action", "text"}``
    for the real track and the signal-check tracks; ``item`` = held-out position. The near-miss texts are rebuilt
    from the truth and the seed (:func:`near_miss_texts`). A track must be complete or absent.
    """
    lines = [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]
    if not lines or lines[0].get("schema") != SIGNAL_DECISIONS_SCHEMA:
        raise ValueError(f"first line must be a header with schema {SIGNAL_DECISIONS_SCHEMA!r}")
    texts = [truth[i] for i in held_out]
    nm, _ = near_miss_texts(texts, int(lines[0].get("seed", DEFAULT_SEED)))
    out, seen = [], set()
    for d in lines[1:]:
        k, it = str(d["track"]), int(d["item"])
        if k != "real" and signal_family(k) is None:
            raise ValueError(f"unknown signal track {k!r}")
        if (k, it) in seen:
            raise ValueError(f"duplicate decision {k} {it}")
        if not 0 <= it < len(texts):
            raise ValueError(f"track {k}: item {it} out of range")
        seen.add((k, it))
        a, t = _action_text(d)
        out.append(Record(k, it, it, it, a, t, texts[it], nm[it] if k == "near_miss" else None))
    for k in {kk for kk, _ in seen}:
        got = sum(1 for kk, _ in seen if kk == k)
        if got != len(texts):
            raise ValueError(f"track {k}: {got} decisions, expected {len(texts)}")
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


def cmd_signal_inputs(a) -> int:
    ids, xs = _load_npz_inputs(a.inputs)
    truth = read_truth(a.truth)
    texts = [truth[i] for i in ids]
    sc = make_signal_checks(xs, texts, seed=a.seed)
    arrays = {f"{k}/{j:05d}": z for k in [*sc.truncated, *sc.noise_mix] for j, z in enumerate(sc.inputs(k))}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, **arrays)
    with open(a.near_miss, "w", encoding="utf-8") as f:
        for i, v, e in zip(ids, sc.near_miss, sc.near_miss_edits):
            f.write(json.dumps({"id": i, "text": v, "edits": e}, ensure_ascii=False) + "\n")
    print(f"wrote {len(arrays)} signal-check inputs to {a.out} and {len(ids)} near-miss texts to {a.near_miss} "
          f"(local files: they are derived from your data). digest {sc.digest()[:16]}", file=sys.stderr)
    return 0


def cmd_signal_score(a) -> int:
    truth = read_truth(a.truth)
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    by_h = {trial_hash(split["dataset"], i): i for i in truth}
    try:
        held = [by_h[t["h"]] for t in split["trials"]]
    except KeyError as e:
        raise SystemExit(f"a split trial is missing from the truth file: {e}") from None
    recs = read_signal_decisions(a.decisions, truth, held)
    oc = to_signal_outcomes(recs, _fluency_from_args(a), dataset=split["dataset"], system=a.system)
    if a.outcomes:
        _dump(oc, a.outcomes)
    card = score_signal_outcomes(oc)
    _dump(card, a.out)
    print(signal_summary_line(card), file=sys.stderr)
    return 0


def cmd_signal_rescore(a) -> int:
    oc = json.loads(Path(a.outcomes).read_text(encoding="utf-8"))
    card = score_signal_outcomes(oc)
    if a.check:
        ref = json.loads(Path(a.check).read_text(encoding="utf-8"))
        diff = _card_diff(json.loads(json.dumps(card)), ref)
        if diff:
            print(f"signal card differs from {a.check} at {diff}", file=sys.stderr)
            return 1
    _dump(card, a.out)
    print(signal_summary_line(card), file=sys.stderr)
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
    p = sub.add_parser("signal-inputs", help="opt-in signal checks: build the truncated / noise-mix inputs and the "
                                             "near-miss texts from your held-out inputs")
    p.add_argument("inputs", help="NPZ: one (T, V) log-prob array per held-out trial id, in held-out order")
    p.add_argument("--truth", required=True, help="truth JSONL ({id, text} per line)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--out", required=True, help="signal-check inputs NPZ (local file; do not commit)")
    p.add_argument("--near-miss", required=True, help="near-miss texts JSONL (local file; do not commit)")
    p.set_defaults(fn=cmd_signal_inputs)
    p = sub.add_parser("signal-score", help="opt-in signal checks: score a signal decisions file")
    p.add_argument("decisions", help="signal decisions JSONL (header line + one line per decision)")
    p.add_argument("--truth", required=True)
    p.add_argument("--split", required=True)
    p.add_argument("--system", default="")
    p.add_argument("--fluency", choices=("conservative", "llm", "table"), default="conservative")
    p.add_argument("--llm-model", default=None)
    p.add_argument("--fluency-table", default=None)
    p.add_argument("--fluent-threshold", type=float, default=DEFAULT_FLUENT_THRESHOLD)
    p.add_argument("--outcomes", default=None, help="also write the signal outcomes file (flags only)")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_signal_score)
    p = sub.add_parser("signal-rescore", help="opt-in signal checks: score a signal outcomes file (flags only)")
    p.add_argument("outcomes")
    p.add_argument("--check", default=None, help="exit 1 if the result differs from this signal card")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_signal_rescore)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
