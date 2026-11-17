"""Replay tracks of the live demo (P14-06): one class per ``kind`` (see :mod:`fidetype.demo.live.config`).

A track gives, for each utterance, a list of timed messages
``(t, message)``: ``t`` is seconds from the start of the utterance at
real time. The server waits until each message is due and publishes it.
Message types:

``demo_utterance``  the utterance starts (signal duration, intended text if known)
``demo_preview``    raw decoder output so far (phonemes, keys or text); never an action
``demo_decision``   the final trust decision (a FEP-0001 ``trust_decision`` event) and its outcome

:meth:`Track.summary` computes the numbers over the whole replay set
(the honest wrong-commit rate), independent of how far the replay is.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np

from fidetype.demo.live.config import DemoConfigError, expand
from fidetype.utils.binomial import _bisect, binom_cdf, clopper_pearson  # noqa: F401 (re-exported)

Timed = tuple[float, dict[str, Any]]

CATEGORY = {"COMMIT": "commit", "OFFER": "offer", "OFFER_WORDS": "offer", "ASK": "withhold", "ABSTAIN": "withhold"}


def category(action: str) -> str:
    return CATEGORY.get(action, "withhold")


def outcome(action: str, shown: list[str], truth: str | None, norm: Callable[[str], str], known: bool = True) -> str:
    """``commit-correct``, ``commit-wrong``, ``offer-hit``, ``offer-miss``, ``withhold`` or ``unknown``.

    ``truth`` None with ``known`` True means "the user meant no text"
    (a null input): every COMMIT is then wrong.
    """
    c = category(action)
    if c == "withhold":
        return "withhold"
    if not known:
        return "unknown"
    t = norm(truth) if truth is not None else None
    if c == "commit":
        return "commit-correct" if t is not None and shown and norm(shown[0]) == t else "commit-wrong"
    return "offer-hit" if t is not None and t in [norm(s) for s in shown] else "offer-miss"


# The exact binomial helpers moved to fidetype.utils.binomial (P5-02 reuses them); the old names stay here.
_binom_cdf = binom_cdf


def tally(outcomes: list[str], top1_wrong: list[bool] | None) -> dict[str, Any]:
    """Aggregate numbers of a list of outcomes (no ids, no text)."""
    n = len(outcomes)
    commit = sum(o.startswith("commit") for o in outcomes)
    wrong = sum(o == "commit-wrong" for o in outcomes)
    offer = sum(o.startswith("offer") for o in outcomes)
    out: dict[str, Any] = {
        "n": n, "commit": commit, "offer": offer, "withhold": sum(o == "withhold" for o in outcomes),
        "unknown": sum(o == "unknown" for o in outcomes),
        "wrong_commit": wrong, "wrong_commit_rate": round(wrong / n, 4) if n else None,
        "wrong_commit_cp95": clopper_pearson(wrong, n),
        "error_among_commits": round(wrong / commit, 4) if commit else None,
        "offer_hit": sum(o == "offer-hit" for o in outcomes),
    }
    if top1_wrong is not None:
        aw = sum(top1_wrong)
        out["always_commit_wrong"] = aw
        out["always_commit_wrong_rate"] = round(aw / n, 4) if n else None
    return out


def _num(x: Any, nd: int = 4) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


class Track:
    """Base class. ``spec`` is the track object of the demo configuration."""

    kind = ""
    preview_mode = "text"

    def __init__(self, spec: dict[str, Any], base: Path | None) -> None:
        self.spec = spec
        self.base = base
        self.id: str = spec["id"]
        self.title: str = spec["title"]
        self.gap_s = float(spec.get("gap_s", 1.5))
        self._loaded = False

    # --- paths -------------------------------------------------------------------
    def path(self, key: str, required: bool = True) -> Path | None:
        v = self.spec.get(key)
        if isinstance(v, dict):
            v = v.get("path")
        if v is None:
            if required:
                raise DemoConfigError(f"track {self.id}: {key!r} is required")
            return None
        return expand(str(v), self.base)

    def required_paths(self) -> list[tuple[str, Path]]:
        return []

    def status(self) -> tuple[str, str]:
        """("ok" | "missing" | "not-prepared" | "disabled", message)."""
        if self.spec.get("enabled", True) is False:
            return "disabled", "disabled in the demo configuration"
        try:
            req = self.required_paths()
        except DemoConfigError as e:
            return "missing", str(e)
        missing = [(w, p) for w, p in req if not p.exists()]
        if missing:
            w, p = missing[0]
            prep = self.spec.get("prepare")
            if prep and w in prep.get("makes", []):
                return "not-prepared", (f"{w} not found: {p}. Run: fidetype demo live --prepare {self.id}")
            return "missing", f"{w} not found: {p}"
        return "ok", "ready"

    def info(self) -> dict[str, Any]:
        st, msg = self.status()
        return {
            "id": self.id, "title": self.title, "kind": self.kind, "status": st, "message": msg,
            "subtitle": self.spec.get("subtitle", ""), "dataset": self.spec.get("dataset", {}),
            "decoder": self.spec.get("decoder_label", ""), "trust": self.spec.get("trust_label", ""),
            "notes": list(self.spec.get("notes", [])), "replay": self.kind != "synthetic",
            "preview_mode": self.preview_mode, "n": len(self) if self._loaded else None,
        }

    # --- replay ---------------------------------------------------------------------
    def load(self) -> None:
        self._loaded = True

    def __len__(self) -> int:
        return 0

    def utterance(self, k: int) -> Iterator[Timed]:
        raise NotImplementedError

    def summary(self) -> dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------
# trust-log: recorded trust decisions (T15 / M2-19)
# ---------------------------------------------------------------------------------------


class TrustLogTrack(Track):
    """Recorded ``trust_decision`` events, replayed with their original timing.

    ``decisions``: a JSON file ``{"keys": [...], "decisions": [...]}`` (the
    M2-19 per-trial log) or JSON Lines of ``trust_decision`` events (key =
    ``session|utterance``). ``truth``: ``{"format": "b2t25-texts", "path": ...}``
    (texts.json of the M4-01/02 derived files: ``texts[session][part][i]``)
    or ``{"format": "json-map", "path": ...}`` (key -> text). ``preview``
    (optional): ``{"format": "ctc-logprobs-npz", "path": ..., "suffix": "|L0",
    "vocab": "b2t25"}``: the recorded decoder log-probabilities; the page
    shows their greedy CTC output while the utterance plays.
    """

    kind = "trust-log"
    preview_mode = "phonemes"

    def required_paths(self) -> list[tuple[str, Path]]:
        out = [("decisions", self.path("decisions")), ("truth", self.path("truth"))]
        if self.spec.get("preview"):
            out.append(("preview", self.path("preview")))
        return out

    def load(self) -> None:
        dp = self.path("decisions")
        if dp.suffix == ".jsonl":
            decs = [json.loads(line) for line in dp.read_text(encoding="utf-8").splitlines() if line.strip()]
            keys = [f"{d.get('session')}|{d.get('utterance')}" for d in decs]
        else:
            raw = json.loads(dp.read_text(encoding="utf-8"))
            keys, decs = list(raw["keys"]), list(raw["decisions"])
        pairs = [(k, d) for k, d in zip(keys, decs) if d.get("type") == "trust_decision" and d.get("is_final", True)]
        tspec = self.spec["truth"]
        tp = self.path("truth")
        tj = json.loads(tp.read_text(encoding="utf-8"))
        if tspec.get("format") == "b2t25-texts":
            def truth_of(key: str) -> str:
                s, part, i = key.split("|")
                return tj[s][part][int(i)]
        elif tspec.get("format") == "json-map":
            def truth_of(key: str) -> str:
                v = tj[key]
                return v["text"] if isinstance(v, dict) else v
        else:
            raise DemoConfigError(f"track {self.id}: unknown truth format {tspec.get('format')!r}")
        self.keys = [k for k, _ in pairs]
        self.decisions = [d for _, d in pairs]
        self.truths = [truth_of(k) for k in self.keys]
        from fidetype.adapters.b2t25 import normalize_words

        self.norm = normalize_words
        self._npz = None
        pv = self.spec.get("preview")
        if pv:
            self._npz = np.load(self.path("preview"))
            self._suffix = pv.get("suffix", "")
            if pv.get("vocab", "b2t25") != "b2t25":
                raise DemoConfigError(f"track {self.id}: preview vocab must be 'b2t25'")
            from fidetype.adapters.b2t25 import BLANK_ID, SIL_TOKEN, VOCAB

            self._vocab, self._blank, self._sil = VOCAB, BLANK_ID, SIL_TOKEN
        self._loaded = True

    def __len__(self) -> int:
        return len(self.decisions)

    def _phoneme_previews(self, k: int, t_range: list[float]) -> list[Timed]:
        if self._npz is None:
            return []
        name = self.keys[k] + self._suffix
        if name not in self._npz.files:
            return []
        am = np.argmax(self._npz[name], axis=1)
        n = len(am)
        t0, t1 = float(t_range[0]), float(t_range[1])
        step = (t1 - t0) / (n - 1) if n > 1 else 0.0
        out: list[Timed] = []
        toks: list[str] = []
        prev = -1
        for i, a in enumerate(am):
            a = int(a)
            if a != prev and a != self._blank:
                tok = self._vocab[a]
                tok = "·" if tok == self._sil else tok
                if not (tok == "·" and (not toks or toks[-1] == "·")):
                    toks.append(tok)
                    out.append((t0 + i * step, {"type": "demo_preview", "text": " ".join(toks), "mode": "phonemes"}))
            prev = a
        return out

    def utterance(self, k: int) -> Iterator[Timed]:
        d = self.decisions[k]
        truth = self.truths[k]
        inp = d.get("input") or {}
        t_end = float(d.get("t_signal_end") or (inp.get("t_range") or [0, 0])[1])
        lat = float(d.get("latency_s") or 0.0)
        yield 0.0, {"type": "demo_utterance", "duration": round(t_end, 3), "truth": truth}
        yield from self._phoneme_previews(k, inp.get("t_range") or [0.0, t_end])
        shown = list(d.get("shown") or [])
        yield t_end + lat, {"type": "demo_decision", "decision": d, "truth": truth,
                            "outcome": outcome(d["action"], shown, truth, self.norm),
                            "latency_ms": _num(1e3 * lat, 1), "latency_source": "recorded"}

    def summary(self) -> dict[str, Any]:
        outs, top1_wrong = [], []
        for d, t in zip(self.decisions, self.truths):
            shown = list(d.get("shown") or [])
            outs.append(outcome(d["action"], shown, t, self.norm))
            top1_wrong.append(not shown or self.norm(shown[0]) != self.norm(t))
        s = tally(outs, top1_wrong if self.spec.get("top1_is_shown0", True) else None)
        cids = sorted({d.get("config_id") for d in self.decisions if d.get("config_id")})
        lat = [float(d["latency_s"]) for d in self.decisions if isinstance(d.get("latency_s"), (int, float))]
        s.update(scope=f"all {len(outs)} recorded utterances", config_ids=cids, alpha=self.spec.get("alpha"),
                 latency_ms_median=_num(1e3 * float(np.median(lat)), 1) if lat else None)
        return s


# ---------------------------------------------------------------------------------------
# nts-streams: decoder output files through the streaming trust layer
# ---------------------------------------------------------------------------------------


def decoder_by_name(name: str) -> Callable[[Any], Any] | None:
    """``keys`` (key-press streams), ``greedy`` (CTC greedy), ``demo`` (synthetic demo decoder)."""
    if name == "keys":
        from fidetype.demo.live.keys import key_nbest

        return key_nbest
    from fidetype.trust.streaming import frame_decoder

    return frame_decoder(name)


class NTSStreamsTrack(Track):
    """NTS stream files replayed at real time through :class:`~fidetype.trust.streaming.StreamingTrustLayer`.

    Keys: ``streams_dir``; ``files`` (optional): ``{"path": split.json,
    "key": "replay"}`` (a JSON list of file names) or a glob (default
    ``*.jsonl``); ``trust_config`` (a frozen configuration file);
    ``decoder`` (``keys``, ``greedy`` or ``demo``); ``truth`` (optional):
    ``{"format": "json-map", "path": ..., "field": "text"}`` (file name
    -> text); ``preview_every_frames`` (default 1).

    TODO(P14-03): the drop-in API (``fidetype.trust.wrap`` / ``TrustGuard``, commit f70707e) landed during
    P14-06; this track still uses StreamingTrustLayer directly (needed for real-time frame pushes).
    """

    kind = "nts-streams"

    def required_paths(self) -> list[tuple[str, Path]]:
        out = [("streams_dir", self.path("streams_dir")), ("trust_config", self.path("trust_config"))]
        f = self.spec.get("files")
        if isinstance(f, dict):
            out.append(("files", self.path("files")))
        if self.spec.get("truth"):
            out.append(("truth", self.path("truth")))
        return out

    def load(self) -> None:
        from fidetype.trust.frozen import FrozenTrustConfig

        sd = self.path("streams_dir")
        f = self.spec.get("files", "*.jsonl")
        if isinstance(f, dict):
            names = json.loads(self.path("files").read_text(encoding="utf-8"))
            if f.get("key"):
                names = names[f["key"]]
            files = [sd / str(n) for n in names]
        else:
            files = sorted(sd.glob(str(f)))
        if not files:
            raise DemoConfigError(f"track {self.id}: no stream files in {sd}")
        bad = [p for p in files if p.resolve().parent != sd.resolve()]
        if bad:
            raise DemoConfigError(f"track {self.id}: stream file outside streams_dir: {bad[0].name}")
        self.files = files
        self.cfg = FrozenTrustConfig.load(self.path("trust_config"))
        self.decode_fn = decoder_by_name(str(self.spec.get("decoder", "greedy")))
        self.truth: dict[str, str] | None = None
        if self.spec.get("truth"):
            field = self.spec["truth"].get("field", "text")
            raw = json.loads(self.path("truth").read_text(encoding="utf-8"))
            self.truth = {k: (v[field] if isinstance(v, dict) else v) for k, v in raw.items()}
        from fidetype.demo.live.keys import normalize

        self.norm = normalize
        self.every = max(1, int(self.spec.get("preview_every_frames", 1)))
        self._layer = self._new_layer()
        self._loaded = True

    def _new_layer(self) -> Any:
        from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

        return StreamingTrustLayer(self.cfg, decode_fn=self.decode_fn,
                                   streaming=StreamingConfig(max_attempts=1, fingerprint_streams=False))

    def __len__(self) -> int:
        return len(self.files)

    def _truth(self, p: Path) -> tuple[str | None, bool]:
        if self.truth is None:
            return None, False
        return self.truth.get(p.name), p.name in self.truth

    def _preview(self, header: dict[str, Any], rows: list[np.ndarray], times: list[float]) -> str:
        from fidetype.streams.spec import NeuralTextStream

        st = NeuralTextStream(log_probs=np.stack(rows).astype(np.float32), frame_times=np.asarray(times),
                              vocab=list(header["vocab"]), blank_id=header.get("blank_id"),
                              vocab_type=header.get("vocab_type", "char"))
        if st.vocab_type == "key":
            from fidetype.demo.live.keys import greedy_keys

            return greedy_keys(st)
        from fidetype.trust.testing import greedy_nbest

        return greedy_nbest(st).candidates[0].text

    def utterance(self, k: int) -> Iterator[Timed]:
        from fidetype.trust.streaming import frame_row, iter_events

        p = self.files[k]
        truth, known = self._truth(p)
        evs = list(iter_events(p))
        header = next(e for e in evs if e.get("type") == "header")
        frames = [e for e in evs if e.get("type") == "frame"]
        if not frames:
            return
        t0 = float(frames[0]["t"])
        dur = float(frames[-1]["t"]) - t0
        dec_lat = float(header.get("latency") or 0.0)
        yield 0.0, {"type": "demo_utterance", "duration": round(dur + dec_lat, 3), "truth": truth if known else None}
        mode = "keys" if header.get("vocab_type") == "key" else "text"
        sid = f"{self.id}-{k}-{time.monotonic_ns()}"
        layer = self._layer
        V = len(header["vocab"])
        rows: list[np.ndarray] = []
        times: list[float] = []
        final = None
        for e in evs:
            if e.get("type") == "frame":
                rel = float(e["t"]) - t0
                yield rel, None  # wait until the frame is due, then push it (real-time replay)
                layer.push(e, sid)
                rows.append(frame_row(e, V))
                times.append(float(e["t"]))
                if len(rows) % self.every == 0:
                    yield rel, {"type": "demo_preview", "text": self._preview(header, rows, times), "mode": mode}
            elif e.get("type") == "end":
                yield dur + dec_lat, None
                r = layer.push(e, sid)
                final = next((d for d in reversed(r) if d.final), None)
            elif e.get("type") == "header":
                layer.push(e, sid)
        if final is None:
            r = layer.end_of_utterance(sid)
            final = next((d for d in reversed(r) if d.final), None)
        layer.close(sid)
        if final is None:
            return
        ev = final.to_event()
        lat = final.provenance.get("latency_s")
        shown = list(final.shown)
        yield dur + dec_lat, {"type": "demo_decision", "decision": ev, "truth": truth if known else None,
                              "outcome": outcome(ev["action"], shown, truth, self.norm, known=known),
                              "latency_ms": _num(1e3 * float(lat), 1) if lat is not None else None,
                              "latency_source": "measured now"}

    def summary(self) -> dict[str, Any]:
        from fidetype.trust.streaming import iter_events

        layer = self._new_layer()
        outs, top1_wrong, lat = [], [], []
        for i, p in enumerate(self.files):
            sid = f"sum-{i}"
            final = None
            for e in iter_events(p):
                for d in layer.push(e, sid):
                    if d.final:
                        final = d
            layer.close(sid)
            if final is None:
                continue
            truth, known = self._truth(p)
            outs.append(outcome(final.action.value, list(final.shown), truth, self.norm, known=known))
            if known:
                top = final.inputs.texts[0] if final.inputs.texts else ""
                top1_wrong.append(self.norm(top) != self.norm(truth or ""))
            if final.provenance.get("latency_s") is not None:
                lat.append(float(final.provenance["latency_s"]))
        s = tally(outs, top1_wrong if self.truth is not None else None)
        s.update(scope=f"all {len(outs)} replay streams", config_ids=[self.cfg.config_id],
                 latency_ms_median=_num(1e3 * float(np.median(lat)), 1) if lat else None,
                 alpha=self.cfg.risk_control.get("alpha"))
        if self.truth is None:
            s["note"] = "no ground truth configured: the wrong-commit rate is unknown"
        return s


# ---------------------------------------------------------------------------------------
# synthetic: the M7-01 session (no data)
# ---------------------------------------------------------------------------------------


class SyntheticTrack(Track):
    """The synthetic M7-01 session (:mod:`fidetype.demo`): simulated decoder streams, demo trust config."""

    kind = "synthetic"

    def load(self) -> None:
        from fidetype import demo

        self.demo = demo
        self.cfg = demo.load_config()
        self.layer = demo.new_layer(self.cfg, partial_every_frames=int(self.spec.get("partial_every_frames", 10)))
        self.texts = demo.demo_phrases()
        self._loaded = True

    def __len__(self) -> int:
        return len(self.demo.SESSION)

    def utterance(self, k: int) -> Iterator[Timed]:
        cond = self.demo.SESSION[k]
        u = self.demo.run_utterance(self.layer, k, cond, self.texts[k], seed=5000 + k)
        yield 0.0, {"type": "demo_utterance", "duration": u["duration"], "truth": u["truth"],
                    "label": u["label"]}
        for pv in u["previews"]:
            yield float(pv["t"]), {"type": "demo_preview", "text": pv["top1"], "mode": "text"}
        f = u["final"]
        ev = {"type": "trust_decision", "session": f"synthetic-{k}", "utterance": 0, "is_final": True,
              "action": f["action"], "reason": f["reason"], "p_top1": f["p_top1"], "score_semantics": "calibrated_prob",
              "set_size": f["set_size"], "guard_risk": f["guard_risk"], "config_id": self.cfg.config_id,
              "shown": f["shown"]}
        norm = self.demo_norm
        yield float(u["duration"]), {"type": "demo_decision", "decision": ev, "truth": u["truth"],
                                     "outcome": outcome(f["action"], f["shown"], u["truth"], norm),
                                     "latency_ms": f["latency_ms"], "latency_source": "measured now"}

    @staticmethod
    def demo_norm(s: str) -> str:
        return s

    def summary(self) -> dict[str, Any]:
        n = int(self.spec.get("summary_per_condition", 20))
        layer = self.demo.new_layer(self.cfg, None)
        texts = self.demo.demo_phrases()[len(self.demo.SESSION):]
        outs, top1_wrong, lat = [], [], []
        for ci, cond in enumerate(self.demo.CONDITIONS):
            for j in range(n):
                u = self.demo.run_utterance(layer, 10_000 + ci * 1000 + j, cond, texts[j], seed=7000 + 97 * ci + j)
                f = u["final"]
                outs.append(outcome(f["action"], f["shown"], u["truth"], self.demo_norm))
                top1_wrong.append(u["baseline"]["outcome"] == "commit-wrong")
                if f.get("latency_ms") is not None:
                    lat.append(float(f["latency_ms"]))
        s = tally(outs, top1_wrong)
        s["latency_ms_median"] = _num(float(np.median(lat)), 1) if lat else None
        s.update(scope=f"{len(outs)} other synthetic phrases ({n} per signal condition)",
                 config_ids=[self.cfg.config_id], alpha=self.cfg.risk_control.get("alpha"))
        return s


KIND_CLASSES: dict[str, type[Track]] = {"trust-log": TrustLogTrack, "nts-streams": NTSStreamsTrack,
                                        "synthetic": SyntheticTrack}


def make_track(spec: dict[str, Any], base: Path | None) -> Track:
    return KIND_CLASSES[spec["kind"]](spec, base)
