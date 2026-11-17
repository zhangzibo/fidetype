"""The live decode loop of ``fidetype live`` (P14-04): signal -> windows -> model -> trust guard -> NTS.

:class:`LiveDecoder` gets chunks from a source (:mod:`fidetype.live.sources`)
and does four things:

1. **Windows.** It keeps a ring buffer of the signal. ``timing="markers"``:
   one window per ``keypress`` marker (the key onset; a key detector or the
   recording's key log gives it). ``timing="fixed"``: one window every
   ``hop_s`` seconds (a board with no onset markers). ``timing="detect"``
   (P4-10): one window per onset that a causal detector finds in the signal
   (:mod:`fidetype.live.onset`; ``keypress`` markers are ignored). A window
   is decoded when the signal has reached ``t + post_s``.
2. **Model.** :class:`~fidetype.live.model.KeyWindowModel` gives one key
   posterior (a ``frame`` over 32 key codes) per window.
3. **Trust.** At each ``segment_end`` marker (or every ``segment_s``
   seconds), the frames of the segment go through the key beam search
   (:func:`fidetype.demo.live.keys.key_nbest`) to an n-best list. The
   drop-in guard (:class:`fidetype.trust.dropin.TrustGuard`, input kind
   ``nbest``) decides: commit, offer or withhold.
4. **Output.** One line per decision (text or JSON), and optionally an NTS
   JSON Lines file (header, ``frame``, final ``hypothesis``,
   ``segment_end``, ``end``) written with
   :class:`fidetype.writer.StreamWriter`, plus a separate decision log
   of the ``trust_decision`` events (TD-4: never in the input stream;
   P14-17; :func:`make_writer`).

Stream loss and gaps (P4-11, spec LSL-G1 abort mode, LSL-G2, LSL-G3). A
chunk with ``lost`` or ``gap`` set (:class:`~fidetype.live.sources.LSLSource`
sets them) is a discontinuity. The decoder drops the open segment (no
decision on a cut input), the pending key onsets and segment ends, and
the signal buffer (no window spans the gap). With ``segment_end``
markers it also drops the first segment after the gap, up to the next
``segment_end`` (its start may be inside the gap; compare WS-Q5). The NTS
output gets one ``lsl_status`` record with ``status = "gap_abort"`` and
the LSL-G3 fields (``t_start``, ``t_end``, ``missing_frames``,
``stream``) plus ``lsl_cause`` (``lost`` or ``timestamp``). A consumer
drops its open utterance there. A run that ends while the stream is
lost writes ``lsl_status`` with ``status = "lost"``. The file keeps its
one header (JSONL rule 6.2.1); the source checks that a reconnected
stream has the same channel count and rate.

Latency. ``frame_ms``: compute time of one window (features + scaler +
LDA). ``decision_ms``: compute time of one decision (beam search + guard).
``added_ms``: wall time from the end of the ``poll`` that delivered the
last sample a frame or decision needed, to the moment its output is
written. This is the latency that Fidetype adds on top of the source.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass, field
from typing import IO, Any, Callable

import numpy as np

from fidetype.adapters.kt_semg import KEY_VOCAB, keypress_stream
from fidetype.demo.live.keys import key_nbest
from fidetype.live.model import KeyWindowModel
from fidetype.live.synthetic import KEYPRESS, SEGMENT_END

__all__ = ["LiveDecision", "LiveStats", "LiveDecoder", "nbest_of_frames"]

ADAPTER_NAME = "fidetype.live"


def nbest_of_frames(log_probs: np.ndarray, times: np.ndarray) -> list[dict[str, Any]]:
    """The n-best list (dicts: text, score, char_confidences) of a segment's key frames."""
    st = keypress_stream(np.asarray(log_probs), list(times))
    nb = key_nbest(st)
    out = []
    for c in nb.candidates:
        d: dict[str, Any] = {"text": c.text, "score": float(c.score)}
        if c.char_confidences and len(c.char_confidences) == len(c.text):
            d["char_confidences"] = [min(1.0, max(0.0, float(v))) for v in c.char_confidences]
        out.append(d)
    return out or [{"text": "", "score": 0.0}]


@dataclass
class LiveDecision:
    seq: int
    t_start: float
    t_end: float
    n_frames: int
    action: str
    text: str | None
    choices: tuple[str, ...]
    p_top1: float
    reason: str
    decision_ms: float
    added_ms: float
    nbest: list[dict[str, Any]] = field(repr=False, default_factory=list)
    event: dict[str, Any] = field(repr=False, default_factory=dict)
    #: ``t_end`` in seconds from the first sample of the run (the source clock can be large, for example LSL).
    t_rel: float = 0.0

    def as_dict(self, include_text: bool = True) -> dict[str, Any]:
        d = {"seq": self.seq, "t_start": round(self.t_start, 4), "t_end": round(self.t_end, 4),
             "t_rel": round(self.t_rel, 4),
             "n_frames": self.n_frames, "action": self.action, "p_top1": round(self.p_top1, 4),
             "reason": self.reason, "decision_ms": round(self.decision_ms, 3), "added_ms": round(self.added_ms, 3)}
        if include_text:
            d["text"] = self.text
            d["choices"] = list(self.choices)
        return d


def _pct(a: list[float]) -> dict[str, float]:
    if not a:
        return {"n": 0}
    x = np.asarray(a, dtype=np.float64)
    return {"n": int(x.size), "p50": round(float(np.percentile(x, 50)), 3),
            "p95": round(float(np.percentile(x, 95)), 3), "max": round(float(x.max()), 3)}


@dataclass
class LiveStats:
    samples: int = 0
    frames: int = 0
    decisions: int = 0
    commits: int = 0
    offers: int = 0
    withholds: int = 0
    empty_segments: int = 0
    late_keys: int = 0
    #: P4-10: onsets found by the detector (``detect`` timing).
    onsets: int = 0
    #: P4-11: stream losses, gap records written, segments and frames dropped at a discontinuity.
    losses: int = 0
    gaps: int = 0
    dropped_segments: int = 0
    dropped_frames: int = 0
    frame_ms: list[float] = field(default_factory=list)
    frame_added_ms: list[float] = field(default_factory=list)
    decision_ms: list[float] = field(default_factory=list)
    decision_added_ms: list[float] = field(default_factory=list)
    wall_s: float = 0.0
    stop_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if not isinstance(v, list)}
        d.update(frame_ms=_pct(self.frame_ms), frame_added_ms=_pct(self.frame_added_ms),
                 decision_ms=_pct(self.decision_ms), decision_added_ms=_pct(self.decision_added_ms))
        return d


class LiveDecoder:
    """The live loop (module docstring).

    ``guard``: a drop-in :class:`~fidetype.trust.dropin.TrustGuard` with input kind ``nbest``; or None
    (collect mode: the n-best list of each segment goes to :attr:`collected`, for calibration).
    ``writer``: an optional :class:`~fidetype.writer.StreamWriter` (frames over :data:`KEY_VOCAB`).
    ``on_decision``: called with each :class:`LiveDecision`.
    """

    def __init__(self, model: KeyWindowModel, guard: Any, source: Any, *, timing: str | None = None,
                 hop_s: float | None = None, segment_s: float | None = None, writer: Any = None,
                 on_decision: Callable[[LiveDecision], None] | None = None, buffer_s: float = 10.0,
                 clock: Callable[[], float] = time.perf_counter, detector: Any = None) -> None:
        if guard is not None and getattr(guard, "input_kind", None) != "nbest":
            raise ValueError("fidetype live needs a guard calibrated on n-best input (input_kind 'nbest')")
        info = source.info
        if int(info["channels"]) != model.channels:
            raise ValueError(f"the model needs {model.channels} channels; the source has {info['channels']}")
        if abs(float(info["sample_rate"]) - model.sample_rate) > 1e-6 * model.sample_rate:
            raise ValueError(f"the model needs {model.sample_rate:g} Hz; the source has {info['sample_rate']:g} Hz")
        self.model = model
        self.guard = guard
        self.source = source
        self.timing = timing or model.timing
        if self.timing not in ("markers", "fixed", "detect"):
            raise ValueError(f"unknown timing {self.timing!r}")
        if self.timing == "detect" and detector is None:
            raise ValueError("timing 'detect' needs an onset detector (fidetype.live.onset)")
        #: P4-10: the onset detector of ``detect`` timing.
        self.detector = detector
        #: ``detect`` timing: a segment end waits this long for late onsets (the detector's delay).
        self.detect_wait_s = 0.15
        self.hop_s = float(hop_s or model.hop_s)
        self.segment_s = segment_s
        self.writer = writer
        self.on_decision = on_decision
        self.clock = clock
        self.fs = model.sample_rate
        self.cap = int(buffer_s * self.fs)
        C = model.channels
        self.buf = np.zeros((0, C), np.float32)
        self.buf_t = np.zeros(0)
        self.keys: list[float] = []  # pending key onsets
        self.seg_ends: list[float] = []  # pending segment ends
        self.next_fixed: float | None = None
        self.next_seg: float | None = None
        self.scaler = model.new_scaler()
        self.seg_frames: list[np.ndarray] = []
        self.seg_times: list[float] = []
        self.seg_t0: float | None = None
        self.last_frame_t = -math.inf
        self.stats = LiveStats()
        self.decisions: list[LiveDecision] = []
        #: Collect mode (``guard=None``): (n-best list, t_start, t_end) per segment.
        self.collected: list[tuple[list[dict[str, Any]], float, float]] = []
        self._poll_end = clock()
        self.t_first: float | None = None
        #: P4-11: markers before this time are ignored (they belong to a cut segment).
        self._floor = -math.inf
        #: P4-11: True from a discontinuity to the next ``segment_end`` marker (that segment is dropped).
        self._skip = False
        self._lost_open = False

    # --- buffer -------------------------------------------------------------

    def _append(self, x: np.ndarray, t: np.ndarray) -> None:
        if len(t) == 0:
            return
        if self.t_first is None:
            self.t_first = float(t[0])
        self.buf = np.concatenate([self.buf, x]) if len(self.buf) else np.asarray(x, np.float32)
        self.buf_t = np.concatenate([self.buf_t, t]) if len(self.buf_t) else np.asarray(t, np.float64)
        if len(self.buf_t) > self.cap:
            k = len(self.buf_t) - self.cap
            self.buf, self.buf_t = self.buf[k:], self.buf_t[k:]
        self.stats.samples += len(t)

    @property
    def t_now(self) -> float:
        return float(self.buf_t[-1]) if len(self.buf_t) else -math.inf

    # --- frames -------------------------------------------------------------

    def _frame(self, tk: float) -> None:
        if self._skip:  # inside the segment cut by a gap: no frame, no output
            return
        if len(self.buf_t) == 0 or tk - self.model.pre_s < self.buf_t[0]:
            self.stats.late_keys += 1
            return
        c0 = time.perf_counter()
        i = int(np.searchsorted(self.buf_t, tk))
        f = self.model.features(self.buf, [i / self.fs])
        z = self.scaler.update_transform(f)
        lp = self.model.log_proba(z)[0]
        ms = (time.perf_counter() - c0) * 1e3
        t = max(float(tk), self.last_frame_t + 1e-6)
        self.last_frame_t = t
        if self.writer is not None:
            self.writer.frame(t, lp)
        if self.seg_t0 is None:
            self.seg_t0 = t
        self.seg_frames.append(lp)
        self.seg_times.append(t)
        self.stats.frames += 1
        self.stats.frame_ms.append(ms)
        self.stats.frame_added_ms.append((self.clock() - self._poll_end) * 1e3)

    def _due_frames(self) -> None:
        now = self.t_now
        post = self.model.post_s
        if self.timing in ("markers", "detect"):
            while self.keys and self.keys[0] + post <= now:
                self._frame(self.keys.pop(0))
        else:
            if self.next_fixed is None and len(self.buf_t):
                self.next_fixed = float(self.buf_t[0]) + self.model.pre_s
            while self.next_fixed is not None and self.next_fixed + post <= now:
                self._frame(self.next_fixed)
                self.next_fixed += self.hop_s

    # --- segments -----------------------------------------------------------

    def _due_segments(self, final: bool = False) -> None:
        now = self.t_now
        post = self.model.post_s
        if self.segment_s and len(self.buf_t):
            if self.next_seg is None:
                self.next_seg = float(self.buf_t[0]) + self.segment_s
            while self.next_seg + post <= now:
                self.seg_ends.append(self.next_seg)
                self.next_seg += self.segment_s
        while self.seg_ends:
            te = self.seg_ends[0]
            # all frames before te must be done: no pending key/fixed window before te
            if not final and self.timing in ("markers", "detect") and self.keys and self.keys[0] < te:
                break
            if not final and self.timing == "detect" and te + self.detect_wait_s > now:
                break
            if not final and self.timing == "fixed" and self.next_fixed is not None and self.next_fixed < te:
                break
            self.seg_ends.pop(0)
            self._decide(te)
        if final and self.seg_frames:
            self._decide(max(now, self.seg_times[-1]))

    # --- discontinuities (P4-11) ---------------------------------------------------

    def _discontinuity(self, gap: dict[str, Any] | None) -> None:
        """Drop all state that a gap cuts (module docstring). ``gap`` None: the stream is lost now."""
        if self.seg_frames:
            self.stats.dropped_segments += 1
            self.stats.dropped_frames += len(self.seg_frames)
        self.seg_frames, self.seg_times, self.seg_t0 = [], [], None
        self.keys, self.seg_ends = [], []
        self.buf = np.zeros((0, self.model.channels), np.float32)
        self.buf_t = np.zeros(0)
        self.next_fixed = None
        self.next_seg = None
        self._skip = not self.segment_s
        if self.detector is not None:
            self.detector.reset()
        if gap is None:
            self.stats.losses += 1
            self._lost_open = True
            return
        self._lost_open = False
        self.stats.gaps += 1
        self._floor = float(gap["t_end"])
        if self.writer is not None:
            rec = {"type": "lsl_status", "status": "gap_abort", "t_start": float(gap["t_start"]),
                   "t_end": float(gap["t_end"]), "missing_frames": gap.get("missing_frames"),
                   "stream": str(gap.get("stream") or ""), "lsl_cause": str(gap.get("cause") or "lost")}
            self.writer.event(rec)

    def _decide(self, t_end: float) -> None:
        if not self.seg_frames:
            self.stats.empty_segments += 1
            if self.writer is not None:
                self.writer.segment_end(t_end)
            return
        lp = np.stack(self.seg_frames)
        times = np.asarray(self.seg_times)
        c0 = time.perf_counter()
        nb = nbest_of_frames(lp, times)
        k = self.stats.decisions
        if self.guard is None:  # collect mode (calibration): keep the n-best list, decide nothing
            self.collected.append((nb, float(times[0]), float(t_end)))
            self.stats.decisions += 1
            self.seg_frames, self.seg_times, self.seg_t0 = [], [], None
            return
        r = self.guard.decide(nb, utterance_id=f"live-{k}")
        dms = (time.perf_counter() - c0) * 1e3
        hid = f"u{k}"
        if self.writer is not None:
            self.writer.hypothesis(nb, is_final=True, id=hid, t_start=float(times[0]), t_end=float(times[-1]))
            ev = dict(r.event)
            if "hypothesis_id" in ev:
                ev["hypothesis_id"] = hid
            self.writer.event(ev)
            self.writer.segment_end(max(t_end, float(times[-1])))
        d = LiveDecision(k, float(times[0]), float(t_end), len(times), r.action, r.text, tuple(r.choices),
                         float(r.p_top1), r.reason, dms, (self.clock() - self._poll_end) * 1e3, nb, dict(r.event),
                         float(t_end) - (self.t_first if self.t_first is not None else float(t_end)))
        self.stats.decisions += 1
        self.stats.decision_ms.append(dms)
        self.stats.decision_added_ms.append(d.added_ms)
        if r.action == "commit":
            self.stats.commits += 1
        elif r.action == "offer":
            self.stats.offers += 1
        else:
            self.stats.withholds += 1
        self.decisions.append(d)
        self.seg_frames, self.seg_times, self.seg_t0 = [], [], None
        if self.on_decision is not None:
            self.on_decision(d)

    # --- loop -----------------------------------------------------------------

    def feed(self, chunk: Any) -> None:
        """Process one chunk (samples, times, markers)."""
        self._poll_end = self.clock()
        if getattr(chunk, "lost", False):
            self._discontinuity(None)
        gap = getattr(chunk, "gap", None)
        if gap is not None:
            self._discontinuity(gap)
        self._append(chunk.samples, chunk.times)
        if self.timing == "detect" and len(chunk.times):
            for t in self.detector.process(chunk.samples, chunk.times):
                if t >= self._floor and not self._skip:
                    self.keys.append(float(t))
                    self.stats.onsets += 1
        for t, m in chunk.markers:
            m = m.strip()
            if float(t) < self._floor:
                continue
            if m == SEGMENT_END and not self.segment_s and self._skip:
                # the end of the segment that the gap cut: drop it, start clean after it
                self._skip = False
                self.stats.dropped_segments += 1
                self._floor = float(t)
                self.keys = [k for k in self.keys if k >= t]
                if self.timing == "fixed":
                    self.next_fixed = float(t)
                continue
            if m == KEYPRESS and self.timing == "markers" and not self._skip:
                self.keys.append(float(t))
            elif m == SEGMENT_END and not self.segment_s:
                self.seg_ends.append(float(t))
        self.keys.sort()
        self.seg_ends.sort()
        self._due_frames()
        self._due_segments()

    def run(self, duration_s: float | None = None, max_decisions: int | None = None,
            poll_timeout: float = 0.05) -> LiveStats:
        """Run until the source ends, ``duration_s`` passes, ``max_decisions`` is reached, or Ctrl+C."""
        t0 = self.clock()
        self.source.start()
        reason = "end of source"
        try:
            while True:
                if duration_s is not None and self.clock() - t0 >= duration_s:
                    reason = "duration"
                    break
                if max_decisions is not None and self.stats.decisions >= max_decisions:
                    reason = "max decisions"
                    break
                ch = self.source.poll(poll_timeout)
                if ch is None:
                    break
                self.feed(ch)
        except KeyboardInterrupt:
            reason = "interrupted"
        finally:
            self.source.close()
        why = getattr(self.source, "stop_reason", "")
        if reason == "end of source" and why:
            reason = why
        if self._lost_open and self.writer is not None:
            self.writer.event({"type": "lsl_status", "status": "lost",
                               "stream": str(getattr(self.source, "stream_name", "")), "detail": why or "lost"})
        if reason == "end of source" or why:
            # decode the windows the last samples allow, then the open segment
            self._due_frames()
            self._due_segments(final=True)
        self.stats.wall_s = self.clock() - t0
        self.stats.stop_reason = reason
        return self.stats


def make_writer(target: str | IO[str], model: KeyWindowModel, source_info: dict[str, Any], guard: Any,
                source_kind: str, timing: str | None = None, decisions: str | None = None) -> Any:
    """A :class:`~fidetype.writer.StreamWriter` with the header and ``meta`` of a live stream.

    ``target`` a path: the file gets the NTS input stream only. The ``trust_decision`` events go to
    the decision log ``decisions`` (a path; FEP-0001, no header), or are not written when it is None
    (TD-4: no ``trust_decision`` in an input stream; P14-17). ``target`` a text stream (for example
    an :class:`~fidetype.live.publish.EventTee`): it gets every line, decisions included, and does
    the split itself.
    """
    from fidetype import __version__
    from fidetype.live.publish import EventTee
    from fidetype.writer import StreamWriter, stream_meta

    extra: dict[str, Any] = {
        "device.channel_count": int(source_info["channels"]),
        "fidetype.vocab_id": "key.w3c-code.az-space-punct-edit-32",
        "fidetype.live": {"source": source_kind, "timing": timing or model.timing, "model": model.name,
                          "trust_config_id": guard.config_id},
    }
    for k, v in (source_info.get("meta") or {}).items():
        if k.startswith(("brainflow.", "device.model", "fidetype.synthetic", "fidetype.replay")):
            extra[k] = v
    meta = stream_meta(modality=str(source_info.get("modality") or model.modality),
                       decoder_name=model.name, decoder_version=model.version, causal=True,
                       lookahead_s=model.post_s, weights_sha256=model.weights_sha256 or None, stream_id="auto",
                       adapter_name=ADAPTER_NAME, adapter_version=__version__, extra=extra)
    kw = dict(vocab=list(KEY_VOCAB), source=f"fidetype.live/{source_kind}", vocab_type="key", blank_id=None,
              latency=model.post_s, meta=meta)
    if hasattr(target, "write"):
        return StreamWriter(target, **kw)
    tee = EventTee([], open(target, "w", encoding="utf-8", newline="\n"),
                   decisions_file=open(decisions, "w", encoding="utf-8", newline="\n") if decisions else None)

    class _SplitWriter(StreamWriter):
        """Closes the stream file and the decision log on close()."""

        def close(self) -> None:
            try:
                super().close()
            finally:
                tee.finish()

    return _SplitWriter(tee, **kw)


def print_decision(d: LiveDecision, fh: IO[str] | None = None, as_json: bool = False,
                   include_text: bool = True) -> None:
    """Print one decision: a text line, or one JSON object (``as_json``)."""
    fh = fh or sys.stdout
    if as_json:
        fh.write(json.dumps(d.as_dict(include_text), ensure_ascii=False) + "\n")
    else:
        what = ""
        if include_text:
            if d.action == "commit":
                what = f' "{d.text}"'
            elif d.action == "offer":
                what = " [" + " | ".join(d.choices[:3]) + "]"
        fh.write(f"[{d.t_rel:8.2f}s] {d.action.upper():8s}{what}  p={d.p_top1:.2f} keys={d.n_frames} "
                 f"decide={d.decision_ms:.1f} ms added={d.added_ms:.1f} ms\n")
    fh.flush()
