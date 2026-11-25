"""Streaming word-by-word prefix commits within one utterance (P5-27).

A prefix guard (P5-24, ``calibrate(confidence="learned", commit_unit="prefix")``)
decides once, at the end of an utterance. A *streaming* prefix guard decides
at checkpoints while the utterance goes on. At each checkpoint it decodes the
decoder output received so far (a causal decoder emits the same frames for
a truncated input) and may commit more words of the top-1 text:

* **Append-only.** Committed words are never retracted. A new commit adds
  words after the committed ones. If the top-1 text at a checkpoint does
  not start with the committed words, the guard commits nothing at that
  checkpoint (a *conflict*; it is counted).
* **Score.** One learned score per word prefix and checkpoint
  (:data:`~fidetype.trust.commit_score.STREAM_FEATURES`: the P5-24 prefix
  features of the decode so far, plus ``stable_log``, ``at_end`` and
  ``open_last_word``). Prefix scores are made monotone in k (running
  minimum), as in P5-24. At a checkpoint the guard commits up to the
  longest prefix whose score passes the threshold.
* **Complete commits.** Only at the end of the utterance can a commit claim
  the whole sentence (all top-1 words). Every earlier commit is a prefix
  commit.
* **Risk unit: the utterance.** An utterance is wrong if *any* of its
  commits is wrong. For append-only commits this is the same as "its final
  committed text is wrong" (a wrong prefix stays wrong when it grows). The
  threshold is certified by Learn then Test (fixed sequence, exact binomial
  p-values) on this loss, on calibration items that the score fit did not
  use. The guarantee: P(rate of wrong utterances <= alpha) >= 1 - delta over
  the calibration draw, for exchangeable utterances.
* **Null controls.** Near-uniform and time-shuffled inputs are streamed
  through the guard; an input with one or more commits counts.

Each commit gives one decision event. The events of an utterance form a
hash chain (``prev_id`` -> ``id``), so a log reader can check that no commit
was removed or changed.

Metric: ``safe_wpm(..., metric_version="0.2", n_commits=...)`` (rule (7),
"several commits per trial", of safe-wpm/0.2; adopted 2026-11-24). Licence:
our own code, Apache-2.0.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from fidetype.trust.commit_score import (PREFIX_FEATURES, STREAM_FEATURES, LearnedCommitScore, longest_prefix,
                                         monotone_prefix_scores)

__all__ = [
    "STREAM_GUARD_SCHEMA",
    "STREAM_EVENT_SCHEMA",
    "RISK_STREAM",
    "CheckpointView",
    "StreamResult",
    "StreamingPrefixGuard",
    "checkpoint_frames",
    "checkpoint_time_s",
    "base_view",
    "stream_views",
    "stream_rows",
    "stream_labels",
    "run_stream",
    "stream_wrong",
    "ltt_stream_threshold",
    "null_control_inputs",
    "calibrate_streaming",
]

STREAM_GUARD_SCHEMA = "fidetype.stream-prefix-guard/0.1"
STREAM_EVENT_SCHEMA = "fidetype.stream-commit-event/0.1"
#: The loss of a streaming prefix guard, in words (``safe-wpm/0.2`` with ``n_commits`` reads the name before ":").
RISK_STREAM = ("wrong-stream-commit: an utterance is wrong if any of its append-only commits is wrong (a prefix "
               "commit is wrong if its words are not the first words of the true text; a complete commit is "
               "wrong unless it equals the true text); rate over all utterances")


def checkpoint_frames(n_frames: int, step: int) -> list[int]:
    """The frame counts at which the guard decides: ``step, 2 step, ...`` below ``n_frames``, then ``n_frames``.

    The last checkpoint is the end of the utterance. ``n_frames = 0`` gives no checkpoint.
    """
    if int(step) < 1:
        raise ValueError("step must be >= 1 frame")
    n = int(n_frames)
    if n <= 0:
        return []
    return list(range(int(step), n, int(step))) + [n]


def checkpoint_time_s(n_frames: int, *, patch: int, stride: int, bin_s: float) -> float:
    """When the first ``n_frames`` output frames exist (s after the first input bin), for a causal patch decoder.

    Output frame j reads input bins ``[stride j, stride j + patch)``; it is ready at the end of bin
    ``stride j + patch - 1``. So ``n`` frames are ready at ``(stride (n - 1) + patch) * bin_s``.
    """
    if n_frames < 1:
        raise ValueError("need at least one frame")
    return float((int(stride) * (int(n_frames) - 1) + int(patch)) * float(bin_s))


@dataclass(frozen=True)
class CheckpointView:
    """What the guard sees at one checkpoint: the decode of the first ``n_frames`` frames."""

    n_frames: int
    #: True at the last checkpoint (all input of the utterance seen).
    at_end: bool
    #: Words of the top-1 text of the decode so far.
    words: tuple[str, ...]
    #: :data:`~fidetype.trust.commit_score.PREFIX_FEATURES` rows, one per word prefix (shape (m, 16)).
    rows: np.ndarray
    #: The commit gate allows a commit of this top-1 text (non-empty, guard risk below the gate).
    gate_ok: bool
    #: Wall-clock seconds to decode and score this checkpoint (nan if not measured).
    seconds: float = math.nan

    def to_dict(self) -> dict[str, Any]:
        return {"n_frames": self.n_frames, "at_end": self.at_end, "words": list(self.words),
                "rows": np.asarray(self.rows, float).tolist(), "gate_ok": self.gate_ok, "seconds": self.seconds}


def base_view(base: Any, x: Any, n_frames: int, at_end: bool, input_scale: str | None = None) -> CheckpointView:
    """Decode the first ``n_frames`` frames of ``x`` with the base prefix guard and return its view.

    ``base`` is a calibrated :class:`~fidetype.trust.dropin.TrustGuard` with logits input (normally the P5-24
    prefix guard of the same calibration). Only its decoder, calibrator, hallucination guard and commit gate
    are used, not its commit score.
    """
    import time

    t0 = time.perf_counter()
    xa = np.asarray(x)
    events, _ = base._codec.events(xa[: int(n_frames)], input_scale)
    sd = base._run_layer(base._layer, events)
    rows, words = base._prefix_rows(sd, events)
    gate = base.config.gate
    ok = bool(sd.inputs.texts) and len(rows) > 0 and (gate is None or gate.violation(
        sd.inputs.texts[0], float(sd.inputs.guard_risk) if base.config.use_guard else None) is None)
    rows = np.asarray(rows, dtype=np.float64).reshape(-1, len(PREFIX_FEATURES))
    return CheckpointView(int(n_frames), bool(at_end), tuple(words), rows, bool(ok), time.perf_counter() - t0)


def stream_views(base: Any, x: Any, step_frames: int, input_scale: str | None = None) -> list[CheckpointView]:
    """The views of every checkpoint of one utterance (:func:`checkpoint_frames`, :func:`base_view`)."""
    n = int(np.asarray(x).shape[0])
    fr = checkpoint_frames(n, step_frames)
    return [base_view(base, x, f, j == len(fr) - 1, input_scale) for j, f in enumerate(fr)]


def stream_rows(views: Sequence[CheckpointView]) -> list[np.ndarray]:
    """The :data:`~fidetype.trust.commit_score.STREAM_FEATURES` rows of each checkpoint (shape (m_c, 19))."""
    out: list[np.ndarray] = []
    for c, v in enumerate(views):
        m = len(v.words)
        r = np.full((m, len(STREAM_FEATURES)), math.nan)
        if m:
            r[:, : len(PREFIX_FEATURES)] = v.rows[:m]
        for k in range(1, m + 1):
            run = 0
            for b in range(c - 1, -1, -1):
                w = views[b].words
                if len(w) >= k and w[:k] == v.words[:k]:
                    run += 1
                else:
                    break
            r[k - 1, -3] = math.log1p(run)
            r[k - 1, -2] = 1.0 if v.at_end else 0.0
            r[k - 1, -1] = 1.0 if (k == m and not v.at_end) else 0.0
        out.append(r)
    return out


def _right(words: Sequence[str], complete: bool, truth_words: Sequence[str]) -> bool:
    c, t = list(words), list(truth_words)
    if complete:
        return c == t
    return len(c) >= 1 and len(t) >= len(c) and t[: len(c)] == c


def stream_labels(view: CheckpointView, truth_words: Sequence[str]) -> np.ndarray:
    """Per prefix k of the checkpoint's top-1 words: True if a commit of the first k words would be right.

    Before the end, every commit is a prefix commit (right if its words are the first words of the truth).
    At the end, the commit of all top-1 words is complete (right only if the words equal the truth).
    """
    m = len(view.words)
    return np.array([_right(view.words[:k], view.at_end and k == m, truth_words) for k in range(1, m + 1)],
                    dtype=bool)


def run_stream(views: Sequence[CheckpointView], scores: Sequence[np.ndarray], threshold: float) -> dict[str, Any]:
    """Apply the append-only commit rule to the checkpoints of one utterance.

    ``scores[c]``: the monotone prefix scores of checkpoint c (empty: no commit possible). Returns
    ``commits`` (a list of dicts: ``checkpoint``, ``n_frames``, ``k_from``, ``k_to``, ``complete``,
    ``score``), the final ``words`` committed, ``complete`` (the last commit claims the whole sentence) and
    ``n_conflicts`` (checkpoints whose top-1 text did not start with the committed words).
    """
    committed: tuple[str, ...] = ()
    commits: list[dict[str, Any]] = []
    conflicts = 0
    complete = False
    for c, (v, s) in enumerate(zip(views, scores)):
        if complete:
            break
        K = len(committed)
        if K and tuple(v.words[:K]) != committed:
            conflicts += 1
            continue
        if not v.gate_ok or not len(s):
            continue
        k = longest_prefix(s, threshold)
        if k <= K:
            continue
        comp = bool(v.at_end and k == len(v.words))
        commits.append({"checkpoint": c, "n_frames": v.n_frames, "k_from": K, "k_to": int(k), "complete": comp,
                        "score": float(s[k - 1])})
        committed = tuple(v.words[:k])
        complete = comp
    return {"commits": commits, "words": committed, "complete": complete, "n_conflicts": conflicts}


def stream_wrong(run: Mapping[str, Any], views: Sequence[CheckpointView], truth_words: Sequence[str]) -> bool:
    """The trial loss: True if any commit of the utterance is wrong."""
    for cm in run["commits"]:
        w = views[cm["checkpoint"]].words[: cm["k_to"]]
        if not _right(w, cm["complete"], truth_words):
            return True
    return False


def ltt_stream_threshold(views: Sequence[Sequence[CheckpointView]], scores: Sequence[Sequence[np.ndarray]],
                         truths: Sequence[Sequence[str]], alpha: float, delta: float,
                         grid: Sequence[float]) -> dict[str, Any]:
    """Learn then Test for the streaming threshold (fixed sequence from the largest grid value down, exact
    binomial p-values, stop at the first p-value above ``delta``). Loss of an item: :func:`stream_wrong`.

    The loss need not be monotone in the threshold (an early commit can block a later one); fixed-sequence
    testing does not need it. Returns ``threshold`` (``inf`` if none passes), ``feasible``,
    ``empirical_risk``, ``p_value``, ``commit_rate`` and ``n``.
    """
    from fidetype.trust.risk_control import binomial_pvalue

    n = len(views)
    best = None
    for lam in sorted((float(x) for x in grid), reverse=True):
        loss = com = 0
        for v, s, t in zip(views, scores, truths):
            r = run_stream(v, s, lam)
            if r["commits"]:
                com += 1
                loss += int(stream_wrong(r, v, t))
        risk = loss / n if n else math.nan
        p = binomial_pvalue(risk, n, alpha) if n else 1.0
        if p > delta:
            break
        best = (lam, risk, p, com / n)
    if best is None:
        return {"threshold": math.inf, "feasible": False, "empirical_risk": math.nan, "p_value": math.nan,
                "commit_rate": 0.0, "n": n}
    lam, risk, p, cr = best
    return {"threshold": lam, "feasible": True, "empirical_risk": risk, "p_value": p, "commit_rate": cr, "n": n}


@dataclass
class StreamResult:
    """The commits of one utterance."""

    #: One dict per commit, in order: the decision events (hash-chained, see :class:`StreamingPrefixGuard`).
    events: list[dict[str, Any]]
    #: All committed words (None if nothing was committed).
    text: str | None
    n_words_committed: int
    #: True if the last commit claims the whole sentence.
    complete: bool | None
    n_commits: int
    #: Checkpoints whose top-1 text did not start with the committed words (no commit there).
    n_conflicts: int
    #: The text added by each commit (same order as ``events``).
    added: list[str] = field(default_factory=list)


class StreamingPrefixGuard:
    """A streaming prefix guard: a base prefix guard (decoder, calibrator, commit gate) + a streaming score.

    ``step_frames``: decide every ``step_frames`` decoder frames and at the end of the utterance.
    ``frame_timing``: optional ``{"patch", "stride", "bin_s"}`` of a causal patch decoder; events then carry
    ``t_s`` (when the frames of the checkpoint exist; :func:`checkpoint_time_s`).
    """

    def __init__(self, base: Any, score: LearnedCommitScore, step_frames: int, *,
                 frame_timing: Mapping[str, Any] | None = None, sheet: Mapping[str, Any] | None = None) -> None:
        if score.unit != "stream-prefix":
            raise ValueError("a streaming guard needs a score with unit 'stream-prefix'")
        if getattr(base, "input_kind", None) != "logits":
            raise ValueError("a streaming guard needs a base guard with logits input (frames)")
        if int(step_frames) < 1:
            raise ValueError("step_frames must be >= 1")
        self.base = base
        self.score = score
        self.step_frames = int(step_frames)
        self.frame_timing = dict(frame_timing) if frame_timing else None
        self.sheet = dict(sheet or {})

    @property
    def threshold(self) -> float:
        return float(self.score.threshold)

    def _config(self) -> dict[str, Any]:
        return {"base_config_id": self.base.config_id, "score": self.score.to_dict(), "step_frames": self.step_frames,
                "frame_timing": self.frame_timing}

    @property
    def config_id(self) -> str:
        """Content id of the streaming configuration (``scfg-...``): base guard, score, threshold, step, timing."""
        b = json.dumps(self._config(), sort_keys=True, allow_nan=False, default=str).encode()
        return "scfg-" + hashlib.sha256(b).hexdigest()[:16]

    def views(self, x: Any, input_scale: str | None = None) -> list[CheckpointView]:
        """Decode every checkpoint of one utterance (``x``: the decoder output of the whole utterance)."""
        return stream_views(self.base, x, self.step_frames, input_scale)

    def scores_of(self, views: Sequence[CheckpointView]) -> list[np.ndarray]:
        """The monotone streaming prefix scores of each checkpoint (empty where the commit gate blocks)."""
        rows = stream_rows(views)
        return [monotone_prefix_scores(self.score.scores(r)) if (v.gate_ok and len(r)) else np.zeros(0)
                for v, r in zip(views, rows)]

    def decide_views(self, views: Sequence[CheckpointView], *, utterance_id: str | None = None,
                     audit_text: bool = False) -> StreamResult:
        """The commits of one utterance from its checkpoint views (see :meth:`views`)."""
        run = run_stream(views, self.scores_of(views), self.threshold)
        events: list[dict[str, Any]] = []
        added: list[str] = []
        prev = None
        cid = self.config_id
        for j, cm in enumerate(run["commits"]):
            v = views[cm["checkpoint"]]
            new = " ".join(v.words[cm["k_from"]: cm["k_to"]])
            added.append(new)
            ev = {"schema": STREAM_EVENT_SCHEMA, "config_id": cid, "utterance_id": utterance_id, "seq": j,
                  "checkpoint": cm["checkpoint"], "n_frames": cm["n_frames"], "at_end": v.at_end,
                  "words_added": cm["k_to"] - cm["k_from"], "n_words_committed": cm["k_to"],
                  "complete": cm["complete"], "score": round(cm["score"], 6), "threshold": self.threshold,
                  "prev_id": prev}
            if self.frame_timing:
                ev["t_s"] = checkpoint_time_s(cm["n_frames"], **{k: self.frame_timing[k]
                                                                 for k in ("patch", "stride", "bin_s")})
            if audit_text:
                ev["text_added"] = new
            ev["id"] = hashlib.sha256(json.dumps(ev, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
            prev = ev["id"]
            events.append(ev)
        words = run["words"]
        return StreamResult(events=events, text=" ".join(words) if words else None, n_words_committed=len(words),
                            complete=run["complete"] if words else None, n_commits=len(events),
                            n_conflicts=run["n_conflicts"], added=added)

    def decide(self, x: Any, *, utterance_id: str | None = None, input_scale: str | None = None,
               audit_text: bool = False) -> StreamResult:
        """Stream one utterance through the guard (offline replay of a causal decoder's output)."""
        return self.decide_views(self.views(x, input_scale), utterance_id=utterance_id, audit_text=audit_text)

    @staticmethod
    def check_chain(events: Sequence[Mapping[str, Any]]) -> bool:
        """True if the events form an unbroken hash chain (ids match their content; each points to the last)."""
        prev = None
        for ev in events:
            d = {k: v for k, v in ev.items() if k != "id"}
            if d.get("prev_id") != prev:
                return False
            if hashlib.sha256(json.dumps(d, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16] != ev["id"]:
                return False
            prev = ev["id"]
        return True

    def to_dict(self) -> dict[str, Any]:
        return {"schema": STREAM_GUARD_SCHEMA, "config_id": self.config_id, **self._config(),
                "risk": RISK_STREAM, "sheet": self.sheet}

    def save(self, path: str | PathLike[str]) -> Path:
        """Save the streaming configuration and sheet as JSON (no signal, no text). The base guard is saved
        separately (:meth:`TrustGuard.save`)."""
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                default=str) + "\n", encoding="utf-8", newline="\n")
        return p

    def guarantee(self) -> dict[str, Any]:
        """The guarantee in the form that :func:`fidetype.benchmark.safe_wpm.safe_wpm` reads."""
        s = self.sheet
        return {"method": "ltt", "alpha": s.get("alpha"), "delta": s.get("delta"), "n_cal": s.get("n_certify"),
                "calibration_split": s.get("split"), "feasible": s.get("feasible", True),
                "config_id": self.config_id, "commit_threshold": self.threshold, "risk": "wrong-stream-commit"}


def null_control_inputs(base: Any, inputs: Sequence[Any], n_trials: int, seed: Any) -> list[tuple[str, np.ndarray, str]]:
    """The null-control inputs of a streaming guard: ``(name, x, input_scale)``, ``n_trials`` per control.

    ``uniform``: near-uniform logits (log 1/V + 0.05 N(0, 1)) of the length of a random calibration item;
    ``shuffled``: the frames of a random calibration item in a random time order. As in
    :func:`fidetype.trust.calibrate`, with the generator ``numpy.random.default_rng(seed)``.
    """
    from fidetype.adapters.ctc_logits import to_log_probs

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(inputs), size=int(n_trials))
    V = len(base._codec.vocab)
    scale = base._codec.input_scale
    out: list[tuple[str, np.ndarray, str]] = []
    for i in idx:
        T = to_log_probs(inputs[i], scale).shape[0]
        out.append(("uniform", np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V)), "logits"))
    for i in idx:
        lp = to_log_probs(inputs[i], scale)
        out.append(("shuffled", lp[rng.permutation(lp.shape[0])], "log_probs"))
    return out


def calibrate_streaming(base: Any, inputs: Sequence[Any], texts: Sequence[str], *, step_frames: int,
                        alpha: float = 0.05, delta: float = 0.1, seed: int = 0, l2: float = 1.0,
                        frame_timing: Mapping[str, Any] | None = None,
                        views: Sequence[Sequence[CheckpointView]] | None = None,
                        control_views: Sequence[tuple[str, Sequence[CheckpointView]]] | None = None,
                        null_trials: int = 300, control_seed: Any = (0, 527),
                        grid: Sequence[float] | None = None,
                        progress: Callable[[str], None] | None = None) -> StreamingPrefixGuard:
    """Fit and certify a streaming prefix guard on calibration data.

    The split is the split of :func:`fidetype.trust.calibrate` with the same ``seed``: the items are permuted
    with ``numpy.random.default_rng(seed)``; the fit + policy-grid parts (62.5 %) fit the streaming score
    (one row per word prefix and checkpoint; label :func:`stream_labels`); the LTT part (37.5 %) certifies the
    threshold on the trial loss :func:`stream_wrong` (:func:`ltt_stream_threshold`, grid 1.00 -> 0.00 step
    0.01). ``base``: the calibrated base prefix guard of the same calibration items and seed (its temperatures
    and conformal parts use only the fit part).

    ``views`` / ``control_views``: precomputed checkpoint views (``StreamingPrefixGuard.views``) of every
    input / of :func:`null_control_inputs`, to reuse decodes; computed here if None. Raises
    :class:`~fidetype.trust.dropin.NullControlError` if a null control has more than ``floor(alpha *
    null_trials)`` inputs with a commit.
    """
    from fidetype.trust.dropin import ControlResult, NullControlError, _split
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    say = progress or (lambda s: None)
    n = len(inputs)
    if len(texts) != n:
        raise ValueError("inputs and texts must have the same length")
    if views is None:
        views = [stream_views(base, x, step_frames) for x in inputs]
    if len(views) != n:
        raise ValueError("views must have one entry per input")
    order = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, n_ltt = _split(n)
    k = n_fit + n_pol
    truth = [str(t).split() for t in texts]
    Xs, ys = [], []
    for i in order[:k]:
        for v, r in zip(views[i], stream_rows(views[i])):
            if len(r):
                Xs.append(r)
                ys.append(stream_labels(v, truth[i]))
    X = np.vstack(Xs) if Xs else np.zeros((0, len(STREAM_FEATURES)))
    y = np.concatenate(ys) if ys else np.zeros(0, bool)
    model = LearnedCommitScore.fit(X, y, l2=l2, unit="stream-prefix")
    say(f"stream score fitted on {k} items, {len(y)} rows ({int(y.sum())} right); dropped {list(model.dropped)}")
    tmp = StreamingPrefixGuard(base, model, step_frames, frame_timing=frame_timing)
    cert_idx = order[k:]
    s_c = [tmp.scores_of(views[i]) for i in cert_idx]
    res = ltt_stream_threshold([views[i] for i in cert_idx], s_c, [truth[i] for i in cert_idx], alpha, delta,
                               DEFAULT_LTT_GRID if grid is None else grid)
    say(f"LTT: threshold {res['threshold']}, empirical risk {res['empirical_risk']}, p {res['p_value']}")
    cert = {"method": "ltt-binomial (stream loss)", "alpha": float(alpha), "delta": float(delta), "n": int(res["n"]),
            "feasible": bool(res["feasible"]),
            "empirical_risk": None if math.isnan(res["empirical_risk"]) else float(res["empirical_risk"]),
            "p_value": None if math.isnan(res["p_value"]) else float(res["p_value"]),
            "ltt_commit_rate": float(res["commit_rate"]), "grid": "1.00 -> 0.00 step 0.01" if grid is None else
            "user grid", "risk": RISK_STREAM}
    model = model.with_threshold(res["threshold"], cert)
    sheet: dict[str, Any] = {
        "alpha": float(alpha), "delta": float(delta), "risk": RISK_STREAM, "n_items": n, "n_fit": int(k),
        "n_fit_rows": int(len(y)), "n_fit_positive_rows": int(y.sum()), "n_certify": int(n_ltt),
        "split": (f"{n} items, numpy default_rng({seed}) permutation: {k} fit (fit + policy grid of calibrate) + "
                  f"{n_ltt} certify (LTT part)"),
        "feasible": bool(res["feasible"]), "threshold": res["threshold"] if math.isfinite(res["threshold"]) else "inf",
        "ltt_empirical_risk": cert["empirical_risk"], "ltt_p_value": cert["p_value"],
        "ltt_commit_rate": cert["ltt_commit_rate"], "step_frames": int(step_frames),
        "base_config_id": base.config_id, "dropped": list(model.dropped),
        "coef": {f: float(c) for f, c in zip(STREAM_FEATURES, model.coef)}, "intercept": float(model.intercept),
        "confidence": {"kind": "learned", "unit": "stream-prefix"},
        "guarantee": (f"P(rate of utterances with a wrong commit <= {alpha:g}) >= {1 - delta:g} over the "
                      "calibration draw, if calibration and use utterances are exchangeable"),
    }
    guard = StreamingPrefixGuard(base, model, step_frames, frame_timing=frame_timing, sheet=sheet)
    if control_views is None:
        control_views = [(nm, guard.views(x, sc)) for nm, x, sc in null_control_inputs(base, inputs, null_trials,
                                                                                         control_seed)]
    allowed = int(math.floor(alpha * null_trials + 1e-9))
    counts: dict[str, int] = {}
    totals: dict[str, int] = {}
    for nm, vs in control_views:
        totals[nm] = totals.get(nm, 0) + 1
        counts[nm] = counts.get(nm, 0) + int(guard.decide_views(vs).n_commits > 0)
    desc = {"uniform": "near-uniform frames (log 1/V + 0.05 N(0,1)), same lengths, streamed",
            "shuffled": "calibration frames in a random time order, streamed"}
    report = [ControlResult(nm, desc.get(nm, nm), totals[nm], counts[nm], int(math.floor(alpha * totals[nm] + 1e-9)))
              for nm in sorted(totals)]
    sheet["controls"] = [c.to_dict() for c in report]
    sheet["controls_rule"] = f"an input with one or more commits counts; pass iff count <= floor({alpha:g} * n)"
    sheet["controls_allowed"] = allowed
    say(f"controls: {[(c.name, c.n_commit, c.allowed) for c in report]}")
    failed = [c for c in report if not c.passed]
    if failed:
        raise NullControlError(f"streaming guard commits on null input: {[c.to_dict() for c in failed]}", report)
    guard.sheet = sheet
    return guard
