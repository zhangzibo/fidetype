"""The live decode loop of ``fidetype live`` (P14-04): signal -> windows -> model -> trust guard -> NTS.

:class:`LiveDecoder` gets chunks from a source (:mod:`fidetype.live.sources`)
and does four things:

1. **Windows.** It keeps a ring buffer of the signal. ``timing="markers"``:
   one window per ``keypress`` marker (the key onset; a key detector or the
   recording's key log gives it). ``timing="fixed"``: one window every
   ``hop_s`` seconds (a board with no onset markers). A window is decoded
   when the signal has reached ``t + post_s``.
2. **Model.** :class:`~fidetype.live.model.KeyWindowModel` gives one key
   posterior (a ``frame`` over 32 key codes) per window.
3. **Trust.** At each ``segment_end`` marker (or every ``segment_s``
   seconds), the frames of the segment go through the key beam search
   (:func:`fidetype.demo.live.keys.key_nbest`) to an n-best list. The
   drop-in guard (:class:`fidetype.trust.dropin.TrustGuard`, input kind
   ``nbest``) decides: commit, offer or withhold.
4. **Output.** One line per decision (text or JSON), and optionally an NTS
   JSON Lines file (header, ``frame``, final ``hypothesis``,
   ``trust_decision``, ``segment_end``, ``end``) written with
   :class:`fidetype.writer.StreamWriter`.

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
                 clock: Callable[[], float] = time.perf_counter) -> None:
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
        if self.timing not in ("markers", "fixed"):
            raise ValueError(f"unknown timing {self.timing!r}")
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
        if self.timing == "markers":
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
            if not final and self.timing == "markers" and self.keys and self.keys[0] < te:
                break
            if not final and self.timing == "fixed" and self.next_fixed is not None and self.next_fixed < te:
                break
            self.seg_ends.pop(0)
            self._decide(te)
        if final and self.seg_frames:
            self._decide(max(now, self.seg_times[-1]))

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
        self._append(chunk.samples, chunk.times)
        for t, m in chunk.markers:
            m = m.strip()
            if m == KEYPRESS and self.timing == "markers":
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
        if reason == "end of source":
            # decode the windows the last samples allow, then the open segment
            self._due_frames()
            self._due_segments(final=True)
        self.stats.wall_s = self.clock() - t0
        self.stats.stop_reason = reason
        return self.stats


def make_writer(target: str | IO[str], model: KeyWindowModel, source_info: dict[str, Any], guard: Any,
                source_kind: str) -> Any:
    """A :class:`~fidetype.writer.StreamWriter` with the header and ``meta`` of a live stream."""
    from fidetype import __version__
    from fidetype.writer import StreamWriter, stream_meta

    extra: dict[str, Any] = {
        "device.channel_count": int(source_info["channels"]),
        "fidetype.vocab_id": "key.w3c-code.az-space-punct-edit-32",
        "fidetype.live": {"source": source_kind, "timing": model.timing, "model": model.name,
                          "trust_config_id": guard.config_id},
    }
    for k, v in (source_info.get("meta") or {}).items():
        if k.startswith(("brainflow.", "device.model", "fidetype.synthetic", "fidetype.replay")):
            extra[k] = v
    meta = stream_meta(modality=str(source_info.get("modality") or model.modality),
                       decoder_name=model.name, decoder_version=model.version, causal=True,
                       lookahead_s=model.post_s, weights_sha256=model.weights_sha256 or None, stream_id="auto",
                       adapter_name=ADAPTER_NAME, adapter_version=__version__, extra=extra)
    return StreamWriter(target, vocab=list(KEY_VOCAB), source=f"fidetype.live/{source_kind}", vocab_type="key",
                        blank_id=None, latency=model.post_s, meta=meta)


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
