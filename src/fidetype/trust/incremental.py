"""Incremental frame decoders for the streaming trust layer (M4-08).

The frame route of :class:`~fidetype.trust.streaming.StreamingTrustLayer`
decodes the whole utterance when it ends. For a large beam with a lexicon
this end-of-utterance decode can take seconds (M4-06: p95 992 ms). An
*incremental* decoder does the search while the frames arrive and keeps
its state between chunks. At the end of the utterance only a small,
bounded part of the work is left.

Interface
---------
::

    dec = factory(header)          # one decoder per utterance; header = the stream header dict
    dec.push_frames(chunk)         # (n, V) float32 log-probs, frame temperature already applied
    preview = dec.partial()        # NBest, provisional: NEVER act on it
    nbest = dec.finalize(stream)   # NBest; equals the batch decode_fn(stream)

``finalize`` gets the full (temperature-scaled) stream of the utterance,
as the batch ``decode_fn`` does, so that a decoder can copy its ``meta``
or run work that needs all frames (for example a forced alignment).

Implementations
---------------
- :class:`IncrementalGreedy`: CTC greedy. ``finalize`` equals
  :func:`~fidetype.trust.testing.greedy_nbest` exactly.
- :class:`IncrementalReferenceDecoder`: the segment beam of
  :class:`~fidetype.trust.testing.ReferenceDecoder` (the demo decoder),
  one closed peak at a time. Equals it exactly.
- :class:`IncrementalCTCBeam`: the CTC prefix beam search of
  :func:`fidetype.lm.ctc_prefix_beam_search` (with or without the
  character LM), through :class:`fidetype.lm.IncrementalPrefixBeam`.
  A ``post`` function can turn the character or phoneme hypotheses into
  the final n-best (for example a lexicon word decoder). Equals the
  batch search exactly: the batch function is the same code with one
  chunk.
- :class:`BufferedDecoder`: any batch ``decode_fn`` behind this
  interface (it buffers the frames; no time saved).

:class:`CTCBeamSpec` builds both the batch ``decode_fn`` and the
incremental factory from one setting, so the two cannot drift apart.

:func:`stability_metrics` measures how stable the provisional top-1 is
(for UI design). Provisional output stays a preview only.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Protocol, Sequence, runtime_checkable

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.types import NBest

DecodeFn = Callable[[NeuralTextStream], NBest]


@runtime_checkable
class IncrementalDecoder(Protocol):
    """A frame decoder that keeps its search state between chunks."""

    def push_frames(self, chunk: np.ndarray) -> None:
        """Consume a (n, V) chunk of log-probs (float32, frame temperature applied)."""

    def partial(self) -> NBest:
        """The provisional n-best of the frames so far. Never act on it."""

    def finalize(self, stream: NeuralTextStream) -> NBest:
        """The final n-best of the utterance (``stream``: all its frames)."""


#: ``factory(header) -> IncrementalDecoder``. ``header`` is the stream header
#: dict (``vocab``, ``blank_id``, ``meta``, ...). One decoder per utterance.
IncrementalFactory = Callable[[dict], IncrementalDecoder]


# ---------------------------------------------------------------------------
# CTC peaks, one chunk at a time
# ---------------------------------------------------------------------------


class SegmentTracker:
    """The runs of :func:`fidetype.trust._ctc.find_segments`, one chunk at a time.

    A run is a maximal block of frames with the same non-blank argmax. Its
    centre is the first frame with the highest non-blank log-probability.
    :meth:`push` returns the runs that a chunk closes; :meth:`close`
    returns the open run at the end. Each run is ``(start, end, centre,
    centre_row)`` with ``end`` exclusive and ``centre_row`` the log-probs
    of the centre frame (the input dtype is kept).
    """

    def __init__(self, blank_id: int) -> None:
        self.blank = int(blank_id)
        self.t = 0
        self._open: list[Any] | None = None  # [start, label, best_value, centre, centre_row]

    def push(self, lp: np.ndarray) -> list[tuple[int, int, int, np.ndarray]]:
        out: list[tuple[int, int, int, np.ndarray]] = []
        if lp.shape[0] == 0:
            return out
        am = np.argmax(lp, axis=1)
        nonblank = np.delete(lp, self.blank, axis=1).max(axis=1)
        for k in range(lp.shape[0]):
            t = self.t + k
            a = int(am[k])
            op = self._open
            if a == self.blank:
                if op is not None:
                    out.append((op[0], t, op[3], op[4]))
                    self._open = None
                continue
            if op is not None and op[1] == a:
                if nonblank[k] > op[2]:
                    op[2], op[3], op[4] = nonblank[k], t, lp[k]
                continue
            if op is not None:
                out.append((op[0], t, op[3], op[4]))
            self._open = [t, a, nonblank[k], t, lp[k]]
        self.t += lp.shape[0]
        return out

    def close(self) -> list[tuple[int, int, int, np.ndarray]]:
        op, self._open = self._open, None
        return [] if op is None else [(op[0], self.t, op[3], op[4])]

    @property
    def open_run(self) -> tuple[int, int, int, np.ndarray] | None:
        op = self._open
        return None if op is None else (op[0], self.t, op[3], op[4])


def _as_chunk(chunk: Any) -> np.ndarray:
    a = np.asarray(chunk, dtype=np.float32)
    if a.ndim != 2:
        raise ValueError(f"a chunk must be 2-D (n, V), got shape {a.shape}")
    return a


# ---------------------------------------------------------------------------
# Greedy
# ---------------------------------------------------------------------------


class IncrementalGreedy:
    """CTC greedy decode, one chunk at a time. ``finalize`` == ``greedy_nbest``."""

    name = "greedy"

    def __init__(self, vocab: Sequence[str], blank_id: int) -> None:
        self.vocab = list(vocab)
        self.seg = SegmentTracker(blank_id)
        self.chars: list[str] = []
        self.conf: list[float] = []

    @classmethod
    def factory(cls, header: dict) -> "IncrementalGreedy":
        return cls(header["vocab"], header["blank_id"])

    def _take(self, runs) -> None:
        for _, _, _, row in runs:
            i = int(np.argmax(row))
            self.chars.append(self.vocab[i])
            self.conf.append(float(np.exp(row[i])))

    def push_frames(self, chunk: np.ndarray) -> None:
        self._take(self.seg.push(_as_chunk(chunk)))

    def partial(self) -> NBest:
        from fidetype.trust.testing import greedy_candidate

        chars, conf = list(self.chars), list(self.conf)
        op = self.seg.open_run
        if op is not None:
            i = int(np.argmax(op[3]))
            chars.append(self.vocab[i])
            conf.append(float(np.exp(op[3][i])))
        return greedy_candidate(chars, conf)

    def finalize(self, stream: NeuralTextStream) -> NBest:
        from fidetype.trust.testing import greedy_candidate

        self._take(self.seg.close())
        return greedy_candidate(self.chars, self.conf)


# ---------------------------------------------------------------------------
# Segment beam (the demo decoder)
# ---------------------------------------------------------------------------


class IncrementalReferenceDecoder:
    """:class:`~fidetype.trust.testing.ReferenceDecoder`, one closed peak at a time."""

    name = "reference-segment-beam"

    def __init__(self, ref: Any, vocab: Sequence[str], blank_id: int) -> None:
        self.ref = ref
        self.vocab = list(vocab)
        self.blank = int(blank_id)
        self.seg = SegmentTracker(blank_id)
        self.beams = ref.start()

    @staticmethod
    def factory_for(ref: Any) -> IncrementalFactory:
        return lambda header: IncrementalReferenceDecoder(ref, header["vocab"], header["blank_id"])

    def _take(self, runs) -> None:
        for _, _, _, row in runs:
            self.beams = self.ref.extend(self.beams, row, self.vocab, self.blank)

    def push_frames(self, chunk: np.ndarray) -> None:
        self._take(self.seg.push(_as_chunk(chunk)))

    def partial(self) -> NBest:
        return self.ref.finish(self.beams, {})  # closed peaks only

    def finalize(self, stream: NeuralTextStream) -> NBest:
        self._take(self.seg.close())
        return self.ref.finish(self.beams, stream.meta)


# ---------------------------------------------------------------------------
# CTC prefix beam search
# ---------------------------------------------------------------------------

#: ``post(hypotheses, stream) -> NBest``: final n-best from the beam output.
PostFn = Callable[[list, NeuralTextStream], NBest]
#: ``preview(hypotheses) -> NBest``: provisional n-best from :meth:`IncrementalPrefixBeam.partial`.
PreviewFn = Callable[[list], NBest]


def _default_post(confidence_variant: str | None) -> PostFn:
    def post(hyps: list, stream: NeuralTextStream) -> NBest:
        from fidetype.trust.types import from_lm_hypotheses

        return from_lm_hypotheses(hyps, stream.meta, confidence_variant=confidence_variant)

    return post


@dataclass
class CTCBeamSpec:
    """One CTC prefix-beam setting -> a batch ``decode_fn`` and an incremental factory.

    ``beam_kwargs`` are the keyword arguments of
    :func:`fidetype.lm.ctc_prefix_beam_search` (for example
    ``dict(RETUNED)``). ``post`` turns the hypotheses into the final
    n-best (default: :func:`~fidetype.trust.types.from_lm_hypotheses`
    with ``confidence_variant``). ``preview`` turns the provisional
    hypotheses into a preview n-best (default: the same conversion with no
    character confidences). ``prewarm_every``: every N frames the
    decoder runs speculative end-of-utterance work
    (:meth:`IncrementalPrefixBeam.prewarm` and ``on_prewarm``); None: off.
    ``on_prewarm(texts)`` gets the current candidate texts, for example to
    fill the caches of a word decoder. It may return an iterator: each
    step is then one small unit of work (for example
    :meth:`fidetype.lm.phoneme_words.PhonemeWordDecoder.warm`).
    ``prewarm_max_new`` caps the new alignments per prewarm.
    ``prewarm_budget_s``: None runs each prewarm to its end inside the push
    that starts it (push spikes are possible). A number bounds the prewarm
    work per ``push_frames`` call to about this many seconds (measured from
    the start of the call): the work runs in steps, continues in the next
    pushes, and a new prewarm replaces an unfinished one. A push can exceed
    the budget by at most one step. The alignments run first, then the
    ``on_prewarm`` steps. Prewarming never changes a result: the budget
    decides only how much cache work runs, never a decode decision.
    ``clock``: the time source of the budget (default
    :func:`time.perf_counter`). Tests pass a fake clock to make the budget
    run out at chosen points (M4-11).
    For hard push bounds in a live process, also call ``gc.collect()`` and
    ``gc.freeze()`` once after loading the models: with a large heap
    (lexicon, LMs) one full cyclic-GC pass can take 0.3 s inside a push
    (M4-09).
    Memory: the beam memos (LM rows, alignments) live in one
    :class:`IncrementalPrefixBeam` per utterance and go with it. The memos
    that live across utterances (``PhonemeWordDecoder``, ``CharNgramLM``)
    have an LRU entry bound (``cache_size``; M4-10).
    """

    beam_kwargs: dict = field(default_factory=dict)
    lm: Any = None
    post: PostFn | None = None
    preview: PreviewFn | None = None
    confidence_variant: str | None = "frame"
    prewarm_every: int | None = None
    on_prewarm: Callable[[list[str]], None] | None = None
    prewarm_max_new: int | None = None
    preview_n: int = 10
    prewarm_budget_s: float | None = None
    clock: Callable[[], float] = field(default=time.perf_counter, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.prewarm_every is not None and self.prewarm_every < 1:
            raise ValueError("prewarm_every must be >= 1 or None")
        if self.prewarm_budget_s is not None and not self.prewarm_budget_s > 0:
            raise ValueError("prewarm_budget_s must be > 0 or None")
        if self.post is None:
            self.post = _default_post(self.confidence_variant)

    def decode_fn(self, stream: NeuralTextStream) -> NBest:
        """The batch decode (the reference of :meth:`factory`)."""
        from fidetype.lm import ctc_prefix_beam_search

        return self.post(ctc_prefix_beam_search(stream, self.lm, **self.beam_kwargs), stream)  # type: ignore[misc]

    def factory(self, header: dict) -> "IncrementalCTCBeam":
        return IncrementalCTCBeam(self, header["vocab"], header["blank_id"])


class IncrementalCTCBeam:
    """The CTC prefix beam search behind :class:`IncrementalDecoder` (see :class:`CTCBeamSpec`)."""

    name = "ctc-prefix-beam"

    def __init__(self, spec: CTCBeamSpec, vocab: Sequence[str], blank_id: int) -> None:
        from fidetype.lm import IncrementalPrefixBeam

        kw = dict(spec.beam_kwargs)
        kw.pop("blank_id", None)
        self.spec = spec
        self.beam = IncrementalPrefixBeam(list(vocab), blank_id, spec.lm, **kw)
        self._since_prewarm = 0
        self._pending: Iterator[None] | None = None
        self._deadline: float | None = None
        self.prewarm_s = 0.0
        self.n_prewarm = 0  # prewarms run to their end
        self.n_prewarm_dropped = 0  # budgeted prewarms replaced or cut by the end of the utterance

    def push_frames(self, chunk: np.ndarray) -> None:
        t0 = self.spec.clock()
        self.beam.push(_as_chunk(chunk))
        pe = self.spec.prewarm_every
        if pe is not None:
            self._since_prewarm += int(np.shape(chunk)[0])
            if self._since_prewarm >= pe:
                self._since_prewarm = 0
                if self.spec.prewarm_budget_s is None:
                    self.prewarm()
                else:
                    if self._pending is not None:
                        self.n_prewarm_dropped += 1
                    self._pending = self._prewarm_steps()
        if self._pending is not None:
            self._run_pending(t0 + self.spec.prewarm_budget_s)  # type: ignore[operator]

    def prewarm(self) -> None:
        """One full prewarm now (no time budget)."""
        t0 = time.perf_counter()
        self._deadline = None
        for _ in self._prewarm_steps():
            pass
        self.prewarm_s += time.perf_counter() - t0
        self.n_prewarm += 1

    def _prewarm_steps(self) -> Iterator[None]:
        yield from self._align_steps()
        yield  # the on_prewarm work starts in its own step
        yield from self._post_steps()

    def _align_steps(self) -> Iterator[None]:
        # The alignments stop at the deadline and continue in the next step.
        while True:
            self.beam.prewarm(self.spec.prewarm_max_new, deadline=self._deadline, clock=self.spec.clock)
            if self._deadline is None or self.spec.clock() < self._deadline:
                return
            yield

    def _post_steps(self) -> Iterator[None]:
        if self.spec.on_prewarm is None:
            return
        r = self.spec.on_prewarm(self.beam.end_candidates()[0])
        if r is not None and hasattr(r, "__next__"):
            for _ in r:
                yield

    def _run_pending(self, deadline: float) -> None:
        clock = self.spec.clock
        t0 = clock()
        self._deadline = deadline
        try:
            while self._pending is not None and clock() < deadline:
                try:
                    next(self._pending)
                except StopIteration:
                    self._pending = None
                    self.n_prewarm += 1
        finally:
            self._deadline = None
            self.prewarm_s += clock() - t0

    def partial(self) -> NBest:
        hyps = self.beam.partial(self.spec.preview_n)
        if self.spec.preview is not None:
            return self.spec.preview(hyps)
        from fidetype.trust.types import from_lm_hypotheses

        return from_lm_hypotheses(hyps, None, confidence_variant=None)

    def finalize(self, stream: NeuralTextStream) -> NBest:
        if self._pending is not None:  # unfinished speculative work: not needed now
            self._pending = None
            self.n_prewarm_dropped += 1
        return self.spec.post(self.beam.finalize(), stream)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Any batch decoder
# ---------------------------------------------------------------------------


class BufferedDecoder:
    """A batch ``decode_fn`` behind the incremental interface (no time saved).

    It keeps the chunks; :meth:`partial` decodes the frames so far and
    :meth:`finalize` decodes the full stream (as the default frame route).
    """

    name = "buffered"

    def __init__(self, decode_fn: DecodeFn, header: dict) -> None:
        self.decode_fn = decode_fn
        self.header = header
        self.chunks: list[np.ndarray] = []

    @staticmethod
    def factory_for(decode_fn: DecodeFn) -> IncrementalFactory:
        return lambda header: BufferedDecoder(decode_fn, header)

    def push_frames(self, chunk: np.ndarray) -> None:
        self.chunks.append(_as_chunk(chunk))

    def partial(self) -> NBest:
        h = self.header
        lp = np.concatenate(self.chunks) if self.chunks else np.zeros((0, len(h["vocab"])), dtype=np.float32)
        st = NeuralTextStream(log_probs=lp, frame_times=np.arange(lp.shape[0], dtype=np.float64), vocab=list(h["vocab"]),
                              blank_id=h.get("blank_id"), source=h.get("source", "unknown"), meta=dict(h.get("meta") or {}),
                              vocab_type=h.get("vocab_type", "char"))
        return self.decode_fn(st)

    def finalize(self, stream: NeuralTextStream) -> NBest:
        return self.decode_fn(stream)


# ---------------------------------------------------------------------------
# Stability of the provisional top-1
# ---------------------------------------------------------------------------


def stability_metrics(previews: Sequence[tuple[float, str]], final_text: str, t_end: float) -> dict[str, Any]:
    """How stable the provisional top-1 of one utterance is (for UI design).

    ``previews`` are ``(time, top-1 text)`` of the provisional decisions in
    order, ``final_text`` the top-1 of the final decision, ``t_end`` the
    time of the last frame. Returns:

    - ``n_previews``, ``n_changes`` (top-1 differs from the previous
      preview), ``change_rate`` (changes per preview after the first);
    - ``n_rewrites``: changes that are not a pure append (the new text
      does not start with the previous one: the user sees shown text
      change);
    - ``stable_at``: the time of the first preview from which every later
      preview equals ``final_text`` (None: the last preview differs);
      ``time_to_stable_before_end`` = ``t_end - stable_at``;
    - ``last_preview_equals_final``;
    - ``prefix_ok_fraction``: share of previews whose text is a prefix of
      ``final_text`` (a "grow only" preview).
    """
    n = len(previews)
    texts = [t for _, t in previews]
    changes = sum(1 for a, b in zip(texts, texts[1:]) if a != b)
    rewrites = sum(1 for a, b in zip(texts, texts[1:]) if a != b and not b.startswith(a))
    stable_at = None
    for i in range(n - 1, -1, -1):
        if texts[i] != final_text:
            break
        stable_at = previews[i][0]
    return {
        "n_previews": n,
        "n_changes": changes,
        "change_rate": changes / (n - 1) if n > 1 else math.nan,
        "n_rewrites": rewrites,
        "stable_at": stable_at,
        "time_to_stable_before_end": None if stable_at is None else float(t_end - stable_at),
        "last_preview_equals_final": bool(n and texts[-1] == final_text),
        "prefix_ok_fraction": sum(final_text.startswith(t) for t in texts) / n if n else math.nan,
    }
