"""The benchmark submission format: NeuralTextStream files plus a manifest.

Layout of a submission folder::

    submission.json                 the manifest (below)
    streams/<trial id>.jsonl        one NTS stream per scored trial (.jsonl or .npz)
    controls/shuffled/<id>.jsonl    the same decoder on time-shuffled input
    controls/zeros/<id>.jsonl       the same decoder on all-zero input

Each stream is plain NeuralTextStream v0.1 (spec section 6). The scorer
reads the **last final hypothesis event** (spec 3.6) of each file:

- ``nbest[0].text`` is the decoder's output text (used for CER and WER);
- ``nbest[:k]`` are the candidates that an OFFER shows;
- the benchmark key ``fidetype.action`` on the hypothesis event is the
  decision of the trust layer: ``"commit"``, ``"offer"`` or ``"abstain"``
  (default ``"commit"``). ``fidetype.offer_k`` (default 3) caps the shown
  candidates. Unknown keys are allowed by spec 6.2 rule 5, so the files
  stay valid NTS.

A stream without a hypothesis event (an NPZ file, or frames only) is
scored as "always commit the CTC greedy text" (char vocabularies only).

The leakage rule (spec 5.3) applies: no truth text in any stream. The
truth travels separately (``prepare``), and the scorer checks the headers.

Manifest ``submission.json`` (schema ``fidetype.benchmark.submission/0.1``)::

    {
      "schema": "fidetype.benchmark.submission/0.1",
      "track": "b2t25-t15-copytask",
      "benchmark_version": "0.1",
      "decoder": {"name": "...", "version": "...", "url": "...",
                  "weights_licence": "...", "training_data": ["..."],
                  "training_regime": "..."},
      "policy": {"name": "trust | always-commit | ...", "description": "..."},
      "guarantee": {"method": "crc | ltt | aci | none", "alpha": 0.05,
                    "delta": 0.1, "n_cal": 812, "scope": "...",
                    "calibration_split": "cal"},
      "submitter": {"name": "...", "contact": "..."},
      "notes": "..."
    }
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Sequence

from fidetype.streams.spec import NeuralTextStream

SUBMISSION_SCHEMA = "fidetype.benchmark.submission/0.1"
ACTIONS = ("commit", "offer", "abstain")
ACTION_KEY = "fidetype.action"
OFFER_K_KEY = "fidetype.offer_k"
DEFAULT_OFFER_K = 3
GUARANTEE_METHODS = ("none", "crc", "ltt", "aci", "other")
STREAM_SUFFIXES = (".jsonl", ".npz")
CONTROL_KINDS = ("shuffled", "zeros")


class SubmissionError(ValueError):
    """The submission folder or a stream breaks the format."""


@dataclass
class TrialOutput:
    """What the scorer takes from one stream file."""

    trial_id: str
    texts: list[str]
    action: str
    offer_k: int
    score: float | None = None
    score_semantics: str | None = None
    from_hypothesis: bool = True

    @property
    def top1(self) -> str:
        return self.texts[0] if self.texts else ""


@dataclass
class Manifest:
    track: str
    decoder: dict[str, Any]
    policy: dict[str, Any] = field(default_factory=dict)
    guarantee: dict[str, Any] = field(default_factory=lambda: {"method": "none"})
    submitter: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    benchmark_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SUBMISSION_SCHEMA, "track": self.track, "benchmark_version": self.benchmark_version,
                "decoder": self.decoder, "policy": self.policy, "guarantee": self.guarantee,
                "submitter": self.submitter, "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Manifest":
        if d.get("schema") != SUBMISSION_SCHEMA:
            raise SubmissionError(f"submission.json: schema must be {SUBMISSION_SCHEMA!r}")
        for k in ("track", "decoder"):
            if k not in d:
                raise SubmissionError(f"submission.json: missing {k!r}")
        dec = d["decoder"]
        if not isinstance(dec, dict) or not dec.get("name"):
            raise SubmissionError("submission.json: decoder.name is required")
        if not dec.get("weights_licence"):
            raise SubmissionError("submission.json: decoder.weights_licence is required (use 'not released' if so)")
        g = d.get("guarantee") or {"method": "none"}
        validate_guarantee(g)
        return cls(track=d["track"], decoder=dec, policy=d.get("policy") or {}, guarantee=g,
                   submitter=d.get("submitter") or {}, notes=d.get("notes", ""),
                   benchmark_version=d.get("benchmark_version", "0.1"))


def validate_guarantee(g: dict[str, Any]) -> None:
    """A guarantee block must say what was promised and on which data."""
    m = g.get("method", "none")
    if m not in GUARANTEE_METHODS:
        raise SubmissionError(f"guarantee.method must be one of {GUARANTEE_METHODS}, not {m!r}")
    if m == "none":
        return
    a = g.get("alpha")
    if not isinstance(a, (int, float)) or not 0 < a < 1:
        raise SubmissionError("guarantee.alpha must be in (0, 1)")
    if m == "ltt":
        dl = g.get("delta")
        if not isinstance(dl, (int, float)) or not 0 < dl < 1:
            raise SubmissionError("guarantee.delta must be in (0, 1) for LTT")
    if m in ("crc", "ltt"):
        n = g.get("n_cal")
        if not isinstance(n, int) or n < 1:
            raise SubmissionError("guarantee.n_cal (number of calibration items) is required for CRC/LTT")
    if not g.get("scope"):
        raise SubmissionError("guarantee.scope is required (for example 'marginal over test trials, exchangeable')")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def stream_files(folder: str | PathLike[str]) -> dict[str, Path]:
    """{trial id: path} of the stream files in a folder."""
    p = Path(folder)
    if not p.is_dir():
        return {}
    out: dict[str, Path] = {}
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in STREAM_SUFFIXES:
            if f.stem in out:
                raise SubmissionError(f"two stream files for trial {f.stem!r} in {p}")
            out[f.stem] = f
    return out


def trial_output(path: str | PathLike[str], events: Sequence[dict[str, Any]] | None = None,
                 stream: NeuralTextStream | None = None) -> TrialOutput:
    """Read the scored output of one stream file (see the module docstring)."""
    p = Path(path)
    if events is None or stream is None:
        from fidetype.conformance.io import load_stream

        c = load_stream(p)
        events, stream = c.events, c.stream
    hyps = [e for e in events if e.get("type") == "hypothesis"]
    final = [e for e in hyps if e.get("is_final") is True]
    h = (final or hyps or [None])[-1]
    if h is None:
        if stream.vocab_type not in ("char", "key") or stream.blank_id is None:
            raise SubmissionError(f"{p.name}: no hypothesis event and no char/key CTC frames to decode")
        from fidetype.eval.metrics import ctc_greedy_decode

        return TrialOutput(p.stem, [" ".join(ctc_greedy_decode(stream).split())], "commit", 1, from_hypothesis=False)
    texts = [str(x.get("text", "")) for x in h.get("nbest", [])]
    action = h.get(ACTION_KEY, "commit")
    if action not in ACTIONS:
        raise SubmissionError(f"{p.name}: {ACTION_KEY} must be one of {ACTIONS}, not {action!r}")
    k = h.get(OFFER_K_KEY, DEFAULT_OFFER_K)
    if not isinstance(k, int) or k < 1:
        raise SubmissionError(f"{p.name}: {OFFER_K_KEY} must be an integer >= 1")
    sc = h["nbest"][0].get("score") if h.get("nbest") else None
    return TrialOutput(p.stem, texts, action, k, score=sc, score_semantics=h.get("score_semantics"))


def load_manifest(folder: str | PathLike[str]) -> Manifest:
    p = Path(folder) / "submission.json"
    if not p.exists():
        raise SubmissionError(f"no submission.json in {folder}")
    return Manifest.from_dict(json.loads(p.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Writing (helpers for producers)
# ---------------------------------------------------------------------------


def hypothesis_event(texts: Sequence[str], scores: Sequence[float] | None = None, *, action: str = "commit",
                     offer_k: int | None = None, score_semantics: str = "none", hyp_id: str = "final",
                     t_start: float | None = None, t_end: float | None = None) -> dict[str, Any]:
    """Build the final hypothesis event that the scorer reads."""
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    if scores is None:
        scores = [0.0] * len(texts)
    if score_semantics in ("calibrated_prob", "uncalibrated_prob"):
        if any(not (0.0 <= float(s) <= 1.0) for s in scores):
            raise ValueError("probability scores must be in [0, 1]")
    nbest = [{"text": str(t), "score": (None if s is None or (isinstance(s, float) and not math.isfinite(s))
                                          else round(float(s), 6))}
             for t, s in zip(texts, scores)]
    for x in nbest:
        if x["score"] is None:
            x["score"] = -1e9  # spec 3.6: score is a number
    e: dict[str, Any] = {"type": "hypothesis", "id": hyp_id, "is_final": True, "score_semantics": score_semantics,
                         "nbest": nbest, ACTION_KEY: action}
    if offer_k is not None:
        e[OFFER_K_KEY] = int(offer_k)
    if t_start is not None:
        e["t_start"] = float(t_start)
    if t_end is not None:
        e["t_end"] = float(t_end)
    return e


def write_trial(path: str | PathLike[str], stream: NeuralTextStream, texts: Sequence[str],
                scores: Sequence[float] | None = None, *, action: str = "commit", offer_k: int | None = None,
                score_semantics: str = "none") -> None:
    """Write one trial: the stream frames plus the final hypothesis event (JSON Lines)."""
    from fidetype.conformance.io import write_jsonl

    t_end = float(stream.frame_times[-1]) if stream.n_frames else None
    ev = hypothesis_event(texts, scores, action=action, offer_k=offer_k, score_semantics=score_semantics,
                          t_start=float(stream.frame_times[0]) if stream.n_frames else None, t_end=t_end)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(stream, path, events=[ev])


def write_manifest(folder: str | PathLike[str], manifest: Manifest) -> Path:
    Manifest.from_dict(manifest.to_dict())  # validate
    p = Path(folder) / "submission.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest.to_dict(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
