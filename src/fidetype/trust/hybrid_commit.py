"""Hybrid streaming + end-of-trial prefix commits within one utterance (P5-28).

P5-27 (:mod:`fidetype.trust.stream_commit`) showed that a streaming prefix guard with one threshold for every
checkpoint commits early and then stops: it never extends a commit at the end of the utterance, where the
one-commit P5-24 prefix guard gets most of its words. A *hybrid* guard uses two scores and two thresholds:

* **Mid-trial checkpoints** (every ``step_frames`` decoder frames before the end): the streaming score
  (unit ``"stream-prefix"``, 19 features) with threshold ``lam_mid``. Mid-trial commits are prefix commits.
* **End checkpoint** (all input seen): the P5-24 prefix score of the base guard (unit ``"prefix"``, 16
  features) with threshold ``lam_end``. The end decision can **extend** the mid-trial commits, and it can
  make a complete commit (all top-1 words).

The commit rule is append-only, as in P5-27: committed words are never retracted; if the top-1 text at a
checkpoint does not start with the committed words, the guard commits nothing there (a *conflict*).

**Joint certification.** The risk unit is the utterance: an utterance is wrong if *any* of its commits is
wrong (:func:`fidetype.trust.stream_commit.stream_wrong`). ``lam_mid`` is fixed before the certification;
``lam_end`` is certified by Learn then Test (fixed sequence from 1.00 down, exact binomial p-values) on this
loss, with the mid-trial commits switched on. So one bound covers all commits of an utterance. If no ``lam_end``
passes, the guard never commits (``lam_mid`` is set to inf as well).

Each commit gives one decision event; the events of an utterance form a hash chain (``prev_id`` -> ``id``).
Metric: ``safe_wpm(..., metric_version="0.2", n_commits=...)`` with ``risk = "wrong-stream-commit"`` (rule (7),
"several commits per trial", of safe-wpm/0.2; adopted 2026-11-24). Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import hashlib
import json
import math
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from fidetype.trust.commit_score import LearnedCommitScore, longest_prefix, monotone_prefix_scores
from fidetype.trust.stream_commit import (RISK_STREAM, CheckpointView, StreamingPrefixGuard, StreamResult,
                                          checkpoint_time_s, stream_rows, stream_views, stream_wrong)

__all__ = [
    "HYBRID_GUARD_SCHEMA",
    "HYBRID_EVENT_SCHEMA",
    "hybrid_scores",
    "run_hybrid",
    "ltt_hybrid_end",
    "HybridPrefixGuard",
    "calibrate_hybrid",
]

HYBRID_GUARD_SCHEMA = "fidetype.hybrid-prefix-guard/0.1"
HYBRID_EVENT_SCHEMA = "fidetype.hybrid-commit-event/0.1"


def hybrid_scores(views: Sequence[CheckpointView], mid_score: LearnedCommitScore,
                  end_score: LearnedCommitScore) -> list[np.ndarray]:
    """The monotone prefix scores of each checkpoint: the streaming score before the end, the prefix score at
    the end. Empty where the commit gate blocks or the top-1 text is empty."""
    if mid_score.unit != "stream-prefix":
        raise ValueError("mid_score must have unit 'stream-prefix'")
    if end_score.unit != "prefix":
        raise ValueError("end_score must have unit 'prefix'")
    rows = stream_rows(views)
    out: list[np.ndarray] = []
    for v, r in zip(views, rows):
        if not v.gate_ok or not len(v.words):
            out.append(np.zeros(0))
        elif v.at_end:
            out.append(monotone_prefix_scores(end_score.scores(np.asarray(v.rows)[: len(v.words)])))
        else:
            out.append(monotone_prefix_scores(mid_score.scores(r)))
    return out


def run_hybrid(views: Sequence[CheckpointView], scores: Sequence[np.ndarray], lam_mid: float,
               lam_end: float) -> dict[str, Any]:
    """Apply the append-only commit rule with threshold ``lam_mid`` before the end and ``lam_end`` at the end.

    Same output as :func:`fidetype.trust.stream_commit.run_stream`; each commit also has ``at_end``.
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
        k = longest_prefix(s, lam_end if v.at_end else lam_mid)
        if k <= K:
            continue
        comp = bool(v.at_end and k == len(v.words))
        commits.append({"checkpoint": c, "n_frames": v.n_frames, "k_from": K, "k_to": int(k), "complete": comp,
                        "score": float(s[k - 1]), "at_end": bool(v.at_end)})
        committed = tuple(v.words[:k])
        complete = comp
    return {"commits": commits, "words": committed, "complete": complete, "n_conflicts": conflicts}


def ltt_hybrid_end(views: Sequence[Sequence[CheckpointView]], scores: Sequence[Sequence[np.ndarray]],
                   truths: Sequence[Sequence[str]], lam_mid: float, alpha: float, delta: float,
                   grid: Sequence[float]) -> dict[str, Any]:
    """Learn then Test for ``lam_end`` with ``lam_mid`` fixed (fixed sequence from the largest grid value down,
    exact binomial p-values, stop at the first p-value above ``delta``). Loss of an item: any commit wrong.

    Returns ``threshold`` (``inf`` if none passes), ``feasible``, ``empirical_risk``, ``p_value``,
    ``commit_rate`` and ``n``.
    """
    from fidetype.trust.risk_control import binomial_pvalue

    n = len(views)
    best = None
    for lam in sorted((float(x) for x in grid), reverse=True):
        loss = com = 0
        for v, s, t in zip(views, scores, truths):
            r = run_hybrid(v, s, lam_mid, lam)
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


def _num(x: float) -> float | str:
    return float(x) if math.isfinite(x) else "inf"


class HybridPrefixGuard:
    """A base prefix guard (decoder, calibrator, gate, P5-24 end score) + a streaming mid-trial score.

    ``lam_mid``: threshold of the streaming score before the end. ``lam_end``: threshold of the base guard's
    prefix score at the end (certified jointly; see :func:`calibrate_hybrid`).
    """

    def __init__(self, base: Any, mid_score: LearnedCommitScore, step_frames: int, lam_mid: float, lam_end: float,
                 *, frame_timing: Mapping[str, Any] | None = None, sheet: Mapping[str, Any] | None = None) -> None:
        if mid_score.unit != "stream-prefix":
            raise ValueError("a hybrid guard needs a mid-trial score with unit 'stream-prefix'")
        if getattr(base, "input_kind", None) != "logits":
            raise ValueError("a hybrid guard needs a base guard with logits input (frames)")
        cs = getattr(base, "commit_score", None)
        if cs is None or cs.unit != "prefix":
            raise ValueError("a hybrid guard needs a base prefix guard (commit_unit='prefix')")
        if not isinstance(cs, LearnedCommitScore):
            raise ValueError("a hybrid guard needs a learned base prefix score; an external prefix score (P5-35) "
                             "is not supported here")
        if int(step_frames) < 1:
            raise ValueError("step_frames must be >= 1")
        self.base = base
        self.mid_score = mid_score
        self.end_score = cs
        self.step_frames = int(step_frames)
        self.lam_mid = float(lam_mid)
        self.lam_end = float(lam_end)
        self.frame_timing = dict(frame_timing) if frame_timing else None
        self.sheet = dict(sheet or {})

    def _config(self) -> dict[str, Any]:
        return {"base_config_id": self.base.config_id, "mid_score": self.mid_score.to_dict(),
                "step_frames": self.step_frames, "lam_mid": _num(self.lam_mid), "lam_end": _num(self.lam_end), "frame_timing": self.frame_timing}

    @property
    def config_id(self) -> str:
        """Content id of the hybrid configuration (``hcfg-...``)."""
        b = json.dumps(self._config(), sort_keys=True, allow_nan=False, default=str).encode()
        return "hcfg-" + hashlib.sha256(b).hexdigest()[:16]

    def views(self, x: Any, input_scale: str | None = None) -> list[CheckpointView]:
        return stream_views(self.base, x, self.step_frames, input_scale)

    def scores_of(self, views: Sequence[CheckpointView]) -> list[np.ndarray]:
        return hybrid_scores(views, self.mid_score, self.end_score)

    def decide_views(self, views: Sequence[CheckpointView], *, utterance_id: str | None = None,
                     audit_text: bool = False) -> StreamResult:
        """The commits of one utterance from its checkpoint views."""
        run = run_hybrid(views, self.scores_of(views), self.lam_mid, self.lam_end)
        events: list[dict[str, Any]] = []
        added: list[str] = []
        prev = None
        cid = self.config_id
        for j, cm in enumerate(run["commits"]):
            v = views[cm["checkpoint"]]
            new = " ".join(v.words[cm["k_from"]: cm["k_to"]])
            added.append(new)
            ev = {"schema": HYBRID_EVENT_SCHEMA, "config_id": cid, "utterance_id": utterance_id, "seq": j,
                  "checkpoint": cm["checkpoint"], "n_frames": cm["n_frames"], "at_end": v.at_end,
                  "words_added": cm["k_to"] - cm["k_from"], "n_words_committed": cm["k_to"],
                  "complete": cm["complete"], "score": round(cm["score"], 6),
                  "threshold": _num(self.lam_end if v.at_end else self.lam_mid), "prev_id": prev}
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

    check_chain = staticmethod(StreamingPrefixGuard.check_chain)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": HYBRID_GUARD_SCHEMA, "config_id": self.config_id, **self._config(), "risk": RISK_STREAM,
                "sheet": self.sheet}

    def save(self, path: str | PathLike[str]) -> Path:
        """Save the hybrid configuration and sheet as JSON (no signal, no text). The base guard is saved
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
                "config_id": self.config_id, "commit_threshold": self.lam_end, "risk": "wrong-stream-commit"}


def calibrate_hybrid(base: Any, mid_score: LearnedCommitScore, views: Sequence[Sequence[CheckpointView]],
                     texts: Sequence[str], *, step_frames: int, lam_mid: float, alpha: float = 0.05,
                     delta: float = 0.1, seed: int = 0, frame_timing: Mapping[str, Any] | None = None,
                     control_views: Sequence[tuple[str, Sequence[CheckpointView]]] | None = None,
                     grid: Sequence[float] | None = None,
                     progress: Callable[[str], None] | None = None) -> HybridPrefixGuard:
    """Certify ``lam_end`` of a hybrid guard on the LTT part of the calibration split, with ``lam_mid`` fixed.

    The split is the split of :func:`fidetype.trust.calibrate` with the same ``seed`` (permutation with
    ``numpy.random.default_rng(seed)``; the last 37.5 % certify). ``base`` and ``mid_score`` must not have
    used the certify items (the base guard's conformal parts use the fit part; the streaming score of
    :func:`~fidetype.trust.stream_commit.calibrate_streaming` uses fit + policy parts). ``control_views``:
    ``(name, views)`` of null-control inputs; an input with one or more commits counts; raises
    :class:`~fidetype.trust.dropin.NullControlError` if a control has more than ``floor(alpha * n)``.
    """
    from fidetype.trust.dropin import ControlResult, NullControlError, _split
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    say = progress or (lambda s: None)
    n = len(views)
    if len(texts) != n:
        raise ValueError("views and texts must have the same length")
    order = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, n_ltt = _split(n)
    cert = order[n_fit + n_pol:]
    truth = [str(t).split() for t in texts]
    tmp = HybridPrefixGuard(base, mid_score, step_frames, lam_mid, math.inf, frame_timing=frame_timing)
    s_c = [tmp.scores_of(views[i]) for i in cert]
    res = ltt_hybrid_end([views[i] for i in cert], s_c, [truth[i] for i in cert], lam_mid, alpha, delta,
                         DEFAULT_LTT_GRID if grid is None else grid)
    say(f"hybrid LTT (lam_mid {lam_mid}): lam_end {res['threshold']}, empirical risk {res['empirical_risk']}, "
        f"p {res['p_value']}, commit rate {res['commit_rate']}")
    fin = lambda x: None if (isinstance(x, float) and math.isnan(x)) else x  # noqa: E731
    sheet: dict[str, Any] = {
        "alpha": float(alpha), "delta": float(delta), "risk": RISK_STREAM, "n_items": n, "n_certify": int(n_ltt),
        "split": (f"{n} items, numpy default_rng({seed}) permutation: last {n_ltt} certify (LTT part of calibrate)"),
        "feasible": bool(res["feasible"]), "lam_mid": float(lam_mid),
        "lam_end": res["threshold"] if math.isfinite(res["threshold"]) else "inf",
        "ltt_empirical_risk": fin(res["empirical_risk"]), "ltt_p_value": fin(res["p_value"]),
        "ltt_commit_rate": float(res["commit_rate"]), "step_frames": int(step_frames),
        "base_config_id": base.config_id,
        "grid": "1.00 -> 0.00 step 0.01 (lam_end), fixed sequence" if grid is None else "user grid",
        "guarantee": (f"P(rate of utterances with a wrong commit <= {alpha:g}) >= {1 - delta:g} over the "
                      "calibration draw, if calibration and use utterances are exchangeable"),
    }
    # No certified lam_end: the pair is not certified, so the guard must not commit mid-trial either (P5-28 fix:
    # the first version kept lam_mid and so made uncertified mid-trial commits).
    lam_mid_used = float(lam_mid) if res["feasible"] else math.inf
    sheet["lam_mid_used"] = _num(lam_mid_used)
    guard = HybridPrefixGuard(base, mid_score, step_frames, lam_mid_used, res["threshold"], frame_timing=frame_timing,
                              sheet=sheet)
    if control_views is not None:
        counts: dict[str, int] = {}
        totals: dict[str, int] = {}
        for nm, vs in control_views:
            totals[nm] = totals.get(nm, 0) + 1
            counts[nm] = counts.get(nm, 0) + int(guard.decide_views(vs).n_commits > 0)
        desc = {"uniform": "near-uniform frames (log 1/V + 0.05 N(0,1)), same lengths, streamed",
                "shuffled": "calibration frames in a random time order, streamed"}
        report = [ControlResult(nm, desc.get(nm, nm), totals[nm], counts[nm],
                                int(math.floor(alpha * totals[nm] + 1e-9))) for nm in sorted(totals)]
        sheet["controls"] = [c.to_dict() for c in report]
        sheet["controls_rule"] = f"an input with one or more commits counts; pass iff count <= floor({alpha:g} * n)"
        say(f"hybrid controls: {[(c.name, c.n_commit, c.allowed) for c in report]}")
        failed = [c for c in report if not c.passed]
        if failed:
            raise NullControlError(f"hybrid guard commits on null input: {[c.to_dict() for c in failed]}", report)
    guard.sheet = sheet
    return guard
