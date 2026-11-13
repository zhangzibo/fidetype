"""Top-level SDK functions (M7-01). Import them from :mod:`fidetype`.

- :func:`open_stream`: read the events of a stream file, or open a
  :class:`~fidetype.writer.StreamWriter`.
- :func:`read_stream`: load a stream file with the reference consumer.
- :func:`validate`: run the conformance suite on one stream.
- :func:`calibrate`: fit the trust layer on labelled calibration streams
  and return a :class:`~fidetype.trust.frozen.FrozenTrustConfig`.
- :func:`greedy_decoder`: the CTC greedy decode as a ``decode_fn``.
"""

from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING, Any, Callable, Iterator, Literal, Sequence, overload

if TYPE_CHECKING:  # pragma: no cover
    from fidetype.conformance.report import TargetReport
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.types import NBest
    from fidetype.writer import StreamWriter

DecodeFn = Callable[["NeuralTextStream"], "NBest"]

__all__ = ["calibrate", "greedy_decoder", "open_stream", "read_stream", "validate"]


@overload
def open_stream(path: str | PathLike[str], mode: Literal["r"] = "r") -> Iterator[dict[str, Any]]: ...
@overload
def open_stream(path: str | PathLike[str], mode: Literal["w"], **header: Any) -> "StreamWriter": ...


def open_stream(path: str | PathLike[str], mode: str = "r", **header: Any) -> Any:
    """Open a NeuralTextStream file, like :func:`open`.

    - ``mode="r"`` (default): return an iterator over the events of a
      ``.jsonl`` file (one dict per line) or an ``.npz`` file (a header,
      one ``frame`` per row, then ``end``). Feed the events to
      :meth:`StreamingTrustLayer.push`.
    - ``mode="w"``: return a :class:`~fidetype.writer.StreamWriter`. The
      keyword arguments go to its constructor (``vocab``, ``source``,
      ``meta``, ``frame_period``, ...). Use it in a ``with`` block.
    """
    if mode == "r":
        from fidetype.trust.streaming import iter_events

        return iter_events(path)
    if mode == "w":
        from fidetype.writer import StreamWriter

        return StreamWriter(path, **header)
    raise ValueError(f"mode must be 'r' or 'w', not {mode!r}")


def read_stream(path: str | PathLike[str]) -> "NeuralTextStream":
    """Load a stream file (``.jsonl`` or ``.npz``) into a :class:`NeuralTextStream`.

    This is the reference consumer: it raises
    :class:`~fidetype.conformance.io.StreamRejected` (a ``ValueError``)
    if the file breaks a Core-level MUST rule.
    """
    from fidetype.conformance.io import load_stream

    return load_stream(path).stream


def validate(
    target: "str | PathLike[str] | NeuralTextStream",
    level: str | None = None,
) -> "TargetReport":
    """Run the conformance suite on one stream file or in-memory stream.

    Same as :func:`fidetype.conformance.check`. ``report.level`` is the
    highest level reached (``none``, ``core``, ``trust-ready``,
    ``provenance``). With ``level`` given, raise ``StreamRejected`` if the
    stream does not reach it.
    """
    from fidetype.conformance import check

    return check(target, level=level)


def greedy_decoder() -> DecodeFn:
    """Return the CTC greedy decode (a one-candidate n-best) as a ``decode_fn``.

    Use it with ``StreamingTrustLayer(config, decode_fn=...)`` when your
    decoder sends frames and you have no beam search. Prefer your own
    beam search with a language model for real use.
    """
    from fidetype.trust.testing import greedy_nbest

    return greedy_nbest


def calibrate(
    streams: Sequence["NeuralTextStream"],
    texts: Sequence[str],
    decode_fn: DecodeFn | None = None,
    *,
    name: str = "",
    max_wrong_commit: float = 0.05,
    policy_fraction: float = 0.5,
    **harness_overrides: Any,
) -> "FrozenTrustConfig":
    """Fit the trust layer on labelled calibration data. Return a frozen configuration.

    ``streams[i]`` is the decoder output when the user meant ``texts[i]``.
    Use data of the same user and session type as the live use
    (exchangeable data: the guarantee holds only then). The function
    follows the Paper 1 frozen recipe (guard on, policy grid fit, then
    the commit threshold from Learn then Test, alpha = ``max_wrong_commit``,
    delta 0.1, combined by ``max``):

    1. The first ``1 - policy_fraction`` of the items fit the
       temperatures and the conformal threshold.
    2. The rest fit the policy grid and the Learn-then-Test threshold.

    ``decode_fn`` turns a stream into an :class:`~fidetype.trust.types.NBest`
    (default: :func:`greedy_decoder`). Save the result with
    ``config.save("trust.json")``; load it with ``FrozenTrustConfig.load``.
    About 100 items or more give a usable threshold; with too few items
    Learn then Test cannot certify a threshold and the layer commits less.
    """
    from fidetype.eval.harness import Item, TrustPipeline
    from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config

    if len(streams) != len(texts):
        raise ValueError("streams and texts must have the same length")
    if len(streams) < 8:
        raise ValueError("calibrate needs at least 8 labelled streams")
    if not 0.0 < policy_fraction < 1.0:
        raise ValueError("policy_fraction must be in (0, 1)")
    items = [Item(s, t) for s, t in zip(streams, texts)]
    n_cal = len(items) - int(round(len(items) * policy_fraction))
    dec = decode_fn or greedy_decoder()
    pipe = TrustPipeline(dec, paper1_v4_harness_config(max_wrong_commit=max_wrong_commit, **harness_overrides), {})
    pipe.fit(items[:n_cal], items[n_cal:])
    recipe = dict(PAPER1_V4_RECIPE)
    recipe["risk_control"] = dict(recipe["risk_control"], alpha=max_wrong_commit)
    recipe["fitted_by"] = "fidetype.calibrate"
    return FrozenTrustConfig.from_pipeline(pipe, name, recipe)
