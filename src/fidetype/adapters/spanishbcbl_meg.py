"""SpanishBCBL MEG adapter: ConvCTC output for one typing segment -> NeuralTextStream.

Source data: the SpanishBCBL typing MEG dataset (Brain2Qwerty v1/v2
data; 306-channel Elekta/MEGIN MEG, Spanish sentences). Our own ConvCTC
decoder (:mod:`fidetype.decoders.conv_ctc`) gives per-frame CTC logits
over the 28-token Brain2Qwerty vocabulary (:data:`fidetype.streams.vocab.VOCAB`,
``char.b2q-28``). :mod:`fidetype.decoders.infer` calls
:func:`segment_stream` for each segment.

This module only builds the stream. It does not need torch, so the
conformance suite can run it on synthetic logits.

Timing
------
Frames are ``frame_period_s`` apart (40 ms for ``downsample = 4`` at
100 Hz), relative to the segment start. In causal mode
(``lookahead_frames`` set) output frame j of the strided convolution sees
input samples up to ``4 j`` only, and each of the N Conformer layers adds
``lookahead_frames`` frames of attention lookahead. So the algorithmic
lookahead is ``N * lookahead_frames * frame_period_s`` and the stream sets
``latency`` to it. The offline (bidirectional) model omits ``latency``
and sets ``decoder.causal = false`` (spec 3.2).

Meta
----
Spec section 4.2 keys, plus dataset keys under the ``spanishbcbl.``
namespace. Before 2026-11-11 the producer wrote flat keys (``subject``,
``split``, ...). The conformance suite (M5-10) flagged them, so they now
live under ``spanishbcbl.``. No key holds the target or typed text.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID, VOCAB

SOURCE = "spanishbcbl-convctc"
ADAPTER_NAME = "fidetype.adapters.spanishbcbl_meg"
VOCAB_ID = "char.b2q-28"
N_MEG_CHANNELS = 306


def opaque_stream_id(*parts: Any) -> str:
    """An opaque, deterministic ``stream.id``: SHA-256 of the parts, 32 hex characters."""
    return hashlib.sha256("/".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:32]


def stream_latency(frame_period_s: float, lookahead_frames: int | None, conformer_layers: int) -> float | None:
    """The algorithmic lookahead in seconds, or None for the offline model."""
    if lookahead_frames is None:
        return None
    return float(lookahead_frames * conformer_layers * frame_period_s)


def stream_meta(
    *,
    subject: str,
    session: str,
    participant: str | None = None,
    block: str | None = None,
    trial_idx: int | None = None,
    split: str | None = None,
    run_name: str = "unknown",
    checkpoint: str = "best.pt",
    segment_start_s: float | None = None,
    lookahead_frames: int | None = None,
    latency: float | None = None,
    model: str = "conv_ctc",
    weights_sha256: str | None = None,
    stream_id: str | None = None,
) -> dict[str, Any]:
    """The ``meta`` of a segment stream. No target text, no typed text."""
    m: dict[str, Any] = {
        "device.modality": "meg",
        "device.vendor": "MEGIN (Elekta)",
        "device.channel_count": N_MEG_CHANNELS,
        "device.invasive": False,
        "device.regulatory_status": "research",
        "decoder.name": f"fidetype-{model}",
        "decoder.version": f"{run_name}/{checkpoint}",
        "decoder.causal": lookahead_frames is not None,
        "decoder.calibration_method": "none",
        "adapter.name": ADAPTER_NAME,
        "adapter.version": _FIDETYPE_VERSION,
        "lm.name": "none",
        "user.personalized": False,
        "subject.id": str(subject),
        "session.id": f"{subject}-{session}",
        "language": "es",
        "calibration.applied": False,
        "data.derived": True,
        "fidetype.vocab_id": VOCAB_ID,
        "spanishbcbl.subject": str(subject),
        "spanishbcbl.session": str(session),
        "spanishbcbl.run_name": run_name,
        "spanishbcbl.checkpoint": checkpoint,
        "spanishbcbl.lookahead_frames": lookahead_frames,
        "spanishbcbl.model": model,
    }
    if latency is not None:
        m["decoder.lookahead_s"] = float(latency)
    if weights_sha256 is not None:
        m["decoder.weights_sha256"] = weights_sha256
    if stream_id is not None:
        m["stream.id"] = stream_id
    for k, v in (("participant", participant), ("block", block), ("trial_idx", trial_idx), ("split", split),
                 ("segment_start_s", segment_start_s)):
        if v is not None:
            m[f"spanishbcbl.{k}"] = v
    return m


def segment_stream(
    log_probs: np.ndarray,
    frame_period_s: float,
    *,
    subject: str,
    session: str,
    conformer_layers: int = 4,
    lookahead_frames: int | None = None,
    source: str = SOURCE,
    **meta_kw: Any,
) -> NeuralTextStream:
    """Build the stream of one segment from per-frame log-probabilities (T, 28).

    ``log_probs`` must already be log-softmax output. ``meta_kw`` goes to
    :func:`stream_meta`.
    """
    lp = np.asarray(log_probs)
    latency = stream_latency(frame_period_s, lookahead_frames, conformer_layers)
    return NeuralTextStream(
        log_probs=lp,
        frame_times=np.arange(lp.shape[0]) * frame_period_s,
        vocab=list(VOCAB),
        blank_id=BLANK_ID,
        source=source,
        meta=stream_meta(subject=subject, session=session, lookahead_frames=lookahead_frames, latency=latency,
                         **meta_kw),
        vocab_type="char",
        frame_period=float(frame_period_s),
        latency=latency,
    )
