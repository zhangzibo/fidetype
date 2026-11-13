"""fidetype: a trust layer for neural text entry.

The package reads decoder output in one standard format, the
NeuralTextStream. It then calibrates the output, abstains when unsure,
offers n-best choices and guards against hallucination.

Stable public API (SDK v0.1, M7-01). Everything below imports lazily, so
``import fidetype`` is fast and loads no optional dependency.

Produce a stream
    :class:`NeuralTextStream`, :func:`make_stream`, :func:`write_stream`,
    :class:`StreamWriter`, :func:`stream_meta`, :func:`open_stream`,
    :data:`VOCAB`, :data:`SPEC_VERSION`
Check a stream
    :func:`validate` (same as :func:`fidetype.conformance.check`),
    :func:`read_stream`
Run the trust layer
    :class:`StreamingTrustLayer` (alias :data:`TrustLayer`),
    :class:`StreamingConfig`, :class:`StreamDecision`, :class:`Action`,
    :class:`FrozenTrustConfig` (``FrozenTrustConfig.load``),
    :func:`calibrate`, :func:`replay`, :func:`greedy_decoder`,
    :class:`NBest`, :class:`Candidate`

Quick start::

    import fidetype

    layer = fidetype.TrustLayer(fidetype.FrozenTrustConfig.load("trust.json"),
                                decode_fn=fidetype.greedy_decoder())  # the decode_fn of the fit
    for event in fidetype.open_stream("stream.jsonl"):
        for d in layer.push(event):
            if d.final:
                print(d.action.value, d.shown)

Command line: ``fidetype --help``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__version__ = "0.0.1"

#: public name -> (module, attribute)
_LAZY: dict[str, tuple[str, str]] = {
    # streams
    "NeuralTextStream": ("fidetype.streams.spec", "NeuralTextStream"),
    "SPEC_VERSION": ("fidetype.streams.spec", "SPEC_VERSION"),
    "VOCAB": ("fidetype.streams.vocab", "VOCAB"),
    "BLANK_ID": ("fidetype.streams.vocab", "BLANK_ID"),
    "make_stream": ("fidetype.writer", "make_stream"),
    "write_stream": ("fidetype.writer", "write_stream"),
    "StreamWriter": ("fidetype.writer", "StreamWriter"),
    "stream_meta": ("fidetype.writer", "stream_meta"),
    "open_stream": ("fidetype.api", "open_stream"),
    "read_stream": ("fidetype.api", "read_stream"),
    "validate": ("fidetype.api", "validate"),
    "StreamRejected": ("fidetype.conformance.io", "StreamRejected"),
    # trust layer
    "StreamingTrustLayer": ("fidetype.trust.streaming", "StreamingTrustLayer"),
    "TrustLayer": ("fidetype.trust.streaming", "StreamingTrustLayer"),
    "StreamingConfig": ("fidetype.trust.streaming", "StreamingConfig"),
    "StreamDecision": ("fidetype.trust.streaming", "StreamDecision"),
    "StreamEventError": ("fidetype.trust.streaming", "StreamEventError"),
    "replay": ("fidetype.trust.streaming", "replay"),
    "FrozenTrustConfig": ("fidetype.trust.frozen", "FrozenTrustConfig"),
    "Action": ("fidetype.trust.policy", "Action"),
    "NBest": ("fidetype.trust.types", "NBest"),
    "Candidate": ("fidetype.trust.types", "Candidate"),
    "calibrate": ("fidetype.api", "calibrate"),
    "greedy_decoder": ("fidetype.api", "greedy_decoder"),
}

__all__ = ["__version__", *sorted(_LAZY)]


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'fidetype' has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(target[0]), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


if TYPE_CHECKING:  # pragma: no cover - static names for type checkers and IDEs
    from fidetype.api import calibrate, greedy_decoder, open_stream, read_stream, validate
    from fidetype.conformance.io import StreamRejected
    from fidetype.streams.spec import SPEC_VERSION, NeuralTextStream
    from fidetype.streams.vocab import BLANK_ID, VOCAB
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.policy import Action
    from fidetype.trust.streaming import (
        StreamDecision,
        StreamEventError,
        StreamingConfig,
        StreamingTrustLayer,
        replay,
    )
    from fidetype.trust.streaming import StreamingTrustLayer as TrustLayer
    from fidetype.trust.types import Candidate, NBest
    from fidetype.writer import StreamWriter, make_stream, stream_meta, write_stream
