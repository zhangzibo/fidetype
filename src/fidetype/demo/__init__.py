"""The Fidetype offline demo (M7-01): synthetic decoders, the streaming trust layer, live decisions.

Everything is synthetic and runs on a CPU in seconds. No participant
data, no network, no weights:

- **Texts**: short phrases from :mod:`fidetype.streams.corpus` (written
  for this project).
- **Decoder output**: :class:`~fidetype.streams.simulator.NoisyDecoderSimulator`
  frames at four signal levels (target greedy CER 0.05, 0.17, 0.28,
  0.41), plus two null inputs from :mod:`fidetype.trust.guard`: a *flat*
  stream (near-uniform frames: no signal, for example a sensor that is
  off) and a *frame-shuffled* stream (real frame statistics, no text).
- **Decoder**: :class:`~fidetype.trust.testing.ReferenceDecoder`, a small
  beam search with a character 5-gram LM fitted on other phrases. The LM
  writes fluent text even from no signal, as large LMs do.
- **Trust layer**: :class:`~fidetype.trust.streaming.StreamingTrustLayer`
  (frame route) with a frozen configuration
  (``trust-config-demo.json`` in this package). :func:`build_config`
  fitted it on 600 other synthetic phrases with the Paper 1 recipe
  (guard on, policy grid, Learn then Test at alpha 0.05).

The baseline is "always commit": it types the top-1 text every time.

:func:`run_session` returns a decision log (a JSON-ready dict). The
terminal demo (``fidetype demo``) prints it live; ``fidetype demo --html
FILE`` writes the static page (:mod:`fidetype.demo.page`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Callable, Iterator

import numpy as np

from fidetype.streams import corpus
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.streaming import StreamDecision, StreamingConfig, StreamingTrustLayer

__all__ = [
    "CONDITIONS", "SESSION", "Condition", "build_config", "build_decoder", "load_config", "make_stream",
    "phrases", "run_session", "run_totals",
]

LOG_SCHEMA = "fidetype.demo-log/0.1"
CONFIG_FILE = "trust-config-demo.json"
FRAME_RATE_HZ = 25.0
#: Confidence temperature of the simulated decoder (< 1: over-confident, as real decoders).
SIM_CONFIDENCE_TEMPERATURE = 0.5
N_LM, N_CALIB = 500, 600


@dataclass(frozen=True)
class Condition:
    key: str
    label: str
    #: Target greedy CER of the simulator; None for a null input.
    target_cer: float | None = None
    #: "uniform" (flat stream) or "shuffled"; None for a real signal.
    null: str | None = None


CONDITIONS: dict[str, Condition] = {c.key: c for c in (
    Condition("strong", "strong signal", 0.05),
    Condition("good", "good signal", 0.17),
    Condition("medium", "medium signal", 0.28),
    Condition("weak", "weak signal", 0.41),
    Condition("no-signal", "no signal (flat stream)", null="uniform"),
    Condition("shuffled", "scrambled signal (frames shuffled)", null="shuffled"),
)}

#: The order of the demo session (fixed; not selected by outcome).
SESSION: tuple[str, ...] = (
    "strong", "good", "strong", "medium", "no-signal", "good", "strong", "weak", "shuffled", "strong", "medium",
    "no-signal",
)


def _short(s: str) -> str:
    for p in corpus._PLACES:
        if s.endswith(" " + p):
            return s[: -len(p) - 1]
    return s


@lru_cache(maxsize=1)
def phrases() -> tuple[str, ...]:
    """Unique short phrases ("the boy found a red box"), in a fixed order.

    The first ``N_CALIB`` fit the configuration, the next ``N_LM`` fit
    the LM, the rest are the demo phrases (never seen by the LM or the fit).
    """
    out: list[str] = []
    seen: set[str] = set()
    for s in corpus.sentences(2400, seed=5)[len(corpus.BASE_SENTENCES):]:
        p = _short(s)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return tuple(out)


def calib_phrases() -> tuple[str, ...]:
    return phrases()[:N_CALIB]


def lm_phrases() -> tuple[str, ...]:
    return phrases()[N_CALIB:N_CALIB + N_LM]


def demo_phrases() -> tuple[str, ...]:
    return phrases()[N_CALIB + N_LM:]


@lru_cache(maxsize=1)
def build_decoder() -> Callable[[NeuralTextStream], Any]:
    """The demo decoder: a beam search (width 8) with a character 5-gram LM."""
    from fidetype.trust.testing import RefCharLM, ReferenceDecoder

    return ReferenceDecoder(RefCharLM(5).fit(lm_phrases()), beam=8)


def make_stream(text: str, condition: str, seed: int) -> NeuralTextStream:
    """The simulated decoder output for ``text`` under ``condition``.

    A null condition first simulates a strong signal, then replaces it
    (flat frames, or the same frames in a random order).
    """
    from fidetype.trust.guard import shuffle_stream, uniform_stream

    c = CONDITIONS[condition]
    cer = c.target_cer if c.target_cer is not None else 0.05
    sim = NoisyDecoderSimulator(SimConfig(target_cer=cer, confidence_temperature=SIM_CONFIDENCE_TEMPERATURE,
                                          frame_rate_hz=FRAME_RATE_HZ), seed=seed)
    st = sim.simulate(text).stream
    meta = {"device.modality": "other", "decoder.name": "fidetype-demo-simulator", "decoder.version": "1",
            "decoder.causal": True, "decoder.calibration_method": "none", "calibration.applied": False,
            "lm.name": "none", "language": "en", "data.derived": True, "fidetype.synthetic": True}
    if c.null == "uniform":
        st = uniform_stream(st, np.random.default_rng(seed))
    elif c.null == "shuffled":
        st = shuffle_stream(st, np.random.default_rng(seed))
    return NeuralTextStream(log_probs=st.log_probs, frame_times=st.frame_times, vocab=st.vocab,
                            blank_id=st.blank_id, source="fidetype-demo", meta=meta,
                            frame_period=1.0 / FRAME_RATE_HZ)


def build_config() -> FrozenTrustConfig:
    """Fit the demo configuration again (about 5 s). The package ships the result."""
    from fidetype.api import calibrate

    levels = [c.key for c in CONDITIONS.values() if c.null is None]
    texts = list(calib_phrases())
    streams = [make_stream(t, levels[i % len(levels)], seed=1000 + i) for i, t in enumerate(texts)]
    cfg = calibrate(streams, texts, build_decoder(), name="fidetype-demo (synthetic)")
    cfg.recipe["fitted_by"] = "fidetype.demo.build_config"
    cfg.recipe["data"] = "synthetic: NoisyDecoderSimulator, 600 phrases, CER 0.05/0.17/0.28/0.41, temperature 0.5"
    return cfg


def load_config() -> FrozenTrustConfig:
    """The frozen demo configuration that ships with the package."""
    text = resources.files("fidetype.demo").joinpath(CONFIG_FILE).read_text(encoding="utf-8")
    import json

    return FrozenTrustConfig.from_dict(json.loads(text))


def stream_events(stream: NeuralTextStream) -> Iterator[dict[str, Any]]:
    """The JSON Lines events of a stream (header, frames), without ``end``."""
    head: dict[str, Any] = {"type": "header", "spec_version": stream.version, "vocab": list(stream.vocab),
                            "vocab_type": stream.vocab_type, "blank_id": stream.blank_id, "source": stream.source,
                            "meta": dict(stream.meta)}
    if stream.frame_period is not None:
        head["frame_period"] = stream.frame_period
    yield head
    for t, row in zip(stream.frame_times, stream.log_probs):
        yield {"type": "frame", "t": float(t), "log_probs": [None if v == -math.inf else float(v) for v in row]}


def _num(x: float, nd: int = 3) -> float | None:
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def outcome(action: str, shown: tuple[str, ...], truth: str | None) -> str:
    """``commit-correct``, ``commit-wrong``, ``offer-hit``, ``offer-miss`` or ``abstain``."""
    if action == "COMMIT":
        return "commit-correct" if truth is not None and shown and shown[0] == truth else "commit-wrong"
    if action in ("OFFER", "OFFER_WORDS"):
        return "offer-hit" if truth is not None and truth in shown else "offer-miss"
    return "abstain"


def _decision_dict(d: StreamDecision) -> dict[str, Any]:
    return {"action": d.action.value, "shown": list(d.shown), "reason": d.decision.reason,
            "p_top1": _num(d.inputs.p_top1), "guard_risk": _num(d.inputs.guard_risk), "set_size": d.inputs.set_size,
            "top1": d.inputs.texts[0] if d.inputs.texts else ""}


def new_layer(config: FrozenTrustConfig | None = None, partial_every_frames: int | None = 25) -> StreamingTrustLayer:
    """A streaming layer with the demo decoder (one attempt per phrase: no ASK)."""
    return StreamingTrustLayer(config or load_config(), decode_fn=build_decoder(),
                               streaming=StreamingConfig(max_attempts=1, partial_every_frames=partial_every_frames))


def run_utterance(layer: StreamingTrustLayer, k: int, condition: str, text: str, seed: int,
                  t0: float = 0.0) -> dict[str, Any]:
    """Push one simulated utterance through ``layer``. Return its log entry."""
    c = CONDITIONS[condition]
    st = make_stream(text, condition, seed)
    truth = None if c.null else text
    sid = f"demo-{k}"
    previews: list[dict[str, Any]] = []
    last_t = 0.0
    for ev in stream_events(st):
        if ev["type"] == "frame":
            last_t = ev["t"]
        for d in layer.push(ev, sid):
            if not d.final:
                previews.append({"t": round(last_t, 3), **_decision_dict(d)})
    final = layer.push({"type": "end"}, sid)[-1]
    layer.close(sid)
    fd = _decision_dict(final)
    fd["latency_ms"] = _num(1e3 * final.provenance.get("latency_s", math.nan), 1)
    fd["outcome"] = outcome(fd["action"], tuple(fd["shown"]), truth)
    base_text = fd["top1"]
    blank = st.blank_id if st.blank_id is not None else 0
    evidence = (1.0 - np.exp(st.log_probs[:, blank].astype(np.float64))).round(2).tolist()
    return {
        "k": k, "condition": condition, "label": c.label, "truth": truth,
        "t0": round(t0, 3), "duration": round(float(st.frame_times[-1] + st.frame_period), 3),
        "n_frames": st.n_frames, "evidence": evidence, "previews": previews, "final": fd,
        "baseline": {"action": "COMMIT", "text": base_text,
                     "outcome": outcome("COMMIT", (base_text,), truth)},
    }


def iter_session(config: FrozenTrustConfig | None = None, partial_every_frames: int | None = 25,
                 gap_s: float = 1.0) -> Iterator[dict[str, Any]]:
    """Yield the log entry of each session utterance as soon as it is decided."""
    layer = new_layer(config, partial_every_frames)
    texts = demo_phrases()
    t0 = 0.0
    for k, cond in enumerate(SESSION):
        u = run_utterance(layer, k, cond, texts[k], seed=5000 + k, t0=t0)
        t0 += u["duration"] + gap_s
        yield u


def run_totals(n_per_condition: int = 40, config: FrozenTrustConfig | None = None) -> dict[str, dict[str, Any]]:
    """Run ``n_per_condition`` other phrases per condition (final decisions only).

    Returns per condition: counts of each outcome for the trust layer and
    the wrong-commit rate (wrong commits / phrases) of trust and of
    always commit.
    """
    layer = new_layer(config, None)
    texts = demo_phrases()[len(SESSION):]
    if n_per_condition > len(texts):
        raise ValueError(f"at most {len(texts)} phrases per condition")
    out: dict[str, dict[str, Any]] = {}
    for ci, cond in enumerate(CONDITIONS):
        counts = {k: 0 for k in ("commit-correct", "commit-wrong", "offer-hit", "offer-miss", "abstain")}
        base_wrong = 0
        for j in range(n_per_condition):
            u = run_utterance(layer, 10_000 + ci * 1000 + j, cond, texts[j], seed=7000 + 97 * ci + j)
            counts[u["final"]["outcome"]] += 1
            base_wrong += u["baseline"]["outcome"] == "commit-wrong"
        n = n_per_condition
        out[cond] = {"label": CONDITIONS[cond].label, "n": n, "trust": counts,
                     "trust_commit_rate": round((counts["commit-correct"] + counts["commit-wrong"]) / n, 3),
                     "trust_wrong_commit_rate": round(counts["commit-wrong"] / n, 3),
                     "always_commit_wrong_commit_rate": round(base_wrong / n, 3)}
    return out


def run_session(config: FrozenTrustConfig | None = None, n_per_condition: int = 40,
                partial_every_frames: int | None = 25) -> dict[str, Any]:
    """The full decision log: the session plus the totals."""
    from fidetype import __version__

    cfg = config or load_config()
    utts = list(iter_session(cfg, partial_every_frames))
    totals = run_totals(n_per_condition, cfg) if n_per_condition else {}
    return log_header(cfg, partial_every_frames) | {"utterances": utts, "totals": totals,
                                                     "fidetype_version": __version__}


def log_header(cfg: FrozenTrustConfig, partial_every_frames: int | None) -> dict[str, Any]:
    pol = cfg.policy
    return {
        "schema": LOG_SCHEMA,
        "config_id": cfg.config_id,
        "config_name": cfg.name,
        "policy": {k: pol.get(k) for k in ("commit_p", "commit_max_risk", "offer_max_k", "abstain_risk",
                                           "final_fallback")},
        "risk_control": {k: cfg.risk_control.get(k) for k in ("method", "alpha", "delta", "threshold", "n")},
        "decoder": "ReferenceDecoder (beam 8) + character 5-gram LM",
        "frame_period": 1.0 / FRAME_RATE_HZ,
        "partial_every_frames": partial_every_frames,
        "conditions": {k: {"label": c.label, "target_cer": c.target_cer, "null": c.null}
                       for k, c in CONDITIONS.items()},
    }
