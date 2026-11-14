"""Processors of the collector (FEP-0006 section 4): ``process(items) -> items``.

Each processor keeps its own state per stream. Order in a pipeline:
``validate`` -> ``trust`` -> ``thin`` / ``redact`` (the configuration
loader enforces that ``redact`` comes after ``trust``).

Loss rule (spec GEN-8, LSL-G2, WS-Q5): an input event that a processor
cannot accept is replaced by a ``gap`` status. The trust processor then
drops the open utterance **without** a final decision and drops the
frames up to the next boundary. No processor drops an input event and
lets the utterance go on as if nothing happened.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import math
from typing import Any, Callable

import numpy as np

from fidetype.adapters import ws as W
from fidetype.collector.receivers import STATUS, Item, status
from fidetype.trust.content import REASON_PREFIX as GATE_REASON

SEGMENT_UNITS = ("utterance", "word", "trial")
SCORE_SEMANTICS = ("calibrated_prob", "uncalibrated_prob", "power", "strength", "none")
SQ_UNITS = ("index", "snr_db", "impedance_ohm", "other")


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


class Processor:
    type = "processor"

    def __init__(self, name: str, log: Callable[[str], None]) -> None:
        self.name = name
        self.log = log
        self.counts: dict[str, int] = {"items_in": 0, "items_out": 0}

    def start(self) -> None:
        pass

    def process(self, items: list[Item]) -> list[Item]:
        self.counts["items_in"] += len(items)
        out = self._process(items)
        self.counts["items_out"] += len(out)
        return out

    def _process(self, items: list[Item]) -> list[Item]:
        return items

    def finish(self) -> list[Item]:
        return []

    def stats(self) -> dict[str, Any]:
        return {"type": self.type, **self.counts}


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def header_errors(ev: dict[str, Any], level: str = "core") -> list[str]:
    """The MUST-level header errors from the conformance suite (``fidetype.conformance``).

    The header is checked as a stream with zero frames, so only the header checks can fail.
    """
    from fidetype.conformance.checks import run_checks
    from fidetype.conformance.io import RawStream

    hdr = {k: v for k, v in ev.items() if k != "type"}
    vocab = hdr.get("vocab")
    V = len(vocab) if isinstance(vocab, list) else 0
    raw = RawStream(format="jsonl", header=hdr, log_probs=np.zeros((0, V)), frame_times=np.zeros(0))
    return [f"[{r.check_id}, spec {r.clause}] {r.message}" for r in run_checks(raw)
            if r.outcome == "fail" and r.blocks(level)]


def decision_errors(ev: dict[str, Any]) -> list[str]:
    """The format errors of one ``trust_decision`` (the FEP-0001 conformance profile, TD-F1 ... TD-F3, TD-8, TD-9)."""
    from fidetype.conformance.profiles.fep0001 import td_format_errors

    return [e.removeprefix("line ?: ") for e in td_format_errors(ev)]


class _VState:
    def __init__(self) -> None:
        self.header_ok = False
        self.V = 0
        self.last_t = -math.inf
        self.ended = False


class ValidateProcessor(Processor):
    """Check each item against the spec; cut the utterance on an invalid input event.

    Input events (per stream): the header with the conformance suite's core checks; frames with the
    reference frame reader (FRM-1 ... FRM-4, strictly increasing ``t``); ``segment_end`` (SEG-4,
    SEG-5); ``hypothesis`` (HYP-1); ``signal_quality`` (SQ-1). Decisions: the FEP-0001 format
    checks and, per session, TD-5 (``seq`` increases), TD-6 / TD-7 (one final per utterance, nothing
    after it).

    ``on_invalid = "cut"`` (default): an invalid input event becomes a ``gap`` status; an invalid
    header drops the stream until the next valid header (status ``lost``); an invalid decision is
    dropped. ``"log"``: count and log, pass the item on unchanged (for debugging only).
    """

    type = "validate"

    def __init__(self, name: str, log: Callable[[str], None], on_invalid: str = "cut", level: str = "core") -> None:
        super().__init__(name, log)
        self.on_invalid = on_invalid
        self.level = level
        self.streams: dict[str, _VState] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.counts.update(invalid_headers=0, invalid_events=0, invalid_decisions=0, dropped_no_header=0)
        self._logged: set[tuple[str, str]] = set()

    def _note(self, sid: str, what: str, errs: list[str]) -> None:
        key = (sid, what)
        if key not in self._logged:  # one log line per stream and kind (no flood)
            self._logged.add(key)
            self.log(f"processors.{self.name}: stream {sid}: invalid {what}: {errs[0]}"
                     + (f" (+{len(errs) - 1} more)" if len(errs) > 1 else ""))

    def event_errors(self, st: _VState, ev: dict[str, Any]) -> list[str]:
        from fidetype.trust.streaming import StreamEventError, frame_row

        typ = ev["type"]
        if typ == "frame":
            t = ev.get("t")
            if not _num(t):
                return ["frame needs a finite numeric t (4.2)"]
            if not t > st.last_t:
                return [f"frame t {t} does not increase (last {st.last_t}; WS-K2 / 5.1)"]
            try:
                frame_row(ev, st.V)
            except StreamEventError as e:
                return [f"{e} (FRM-1 ... FRM-4)"]
            return []
        if typ == "segment_end":
            errs = []
            if "t" in ev and not (_num(ev["t"]) and ev["t"] >= (st.last_t if math.isfinite(st.last_t) else -math.inf)):
                errs.append("segment_end t must be finite and not before the last frame (SEG-4)")
            if "unit" in ev and ev["unit"] not in SEGMENT_UNITS:
                errs.append(f"segment_end unit {ev['unit']!r} is not one of {list(SEGMENT_UNITS)} (SEG-5)")
            return errs
        if typ == "hypothesis":
            errs = []
            if not isinstance(ev.get("id"), str):
                errs.append("hypothesis id must be a string (HYP-1)")
            if not isinstance(ev.get("is_final"), bool):
                errs.append("hypothesis is_final must be a boolean (HYP-1)")
            if ev.get("score_semantics") not in SCORE_SEMANTICS:
                errs.append("hypothesis score_semantics is missing or unknown (HYP-1)")
            nb = ev.get("nbest")
            if not isinstance(nb, list) or not all(isinstance(i, dict) and isinstance(i.get("text"), str) for i in nb):
                errs.append("hypothesis nbest must be a list of items with a string text (HYP-1)")
            return errs
        if typ == "signal_quality":
            v, u = ev.get("value"), ev.get("unit")
            if not _num(ev.get("t")) or not _num(v) or u not in SQ_UNITS or (u == "index" and not 0 <= v <= 1):
                return ["signal_quality needs a numeric t and value, a known unit, and an index in [0, 1] (SQ-1)"]
        return []

    def _decision(self, sid: str, ev: dict[str, Any]) -> list[str]:
        errs = decision_errors(ev)
        sess = ev.get("session", sid)
        st = self.sessions.setdefault(str(sess), {"seq": -1, "final_utts": set()})
        seq, utt = ev.get("seq"), ev.get("utterance")
        if _int(seq):
            if seq <= st["seq"]:
                errs.append(f"seq {seq} does not increase in session (TD-5)")
            else:
                st["seq"] = seq
        if _int(utt):
            if utt in st["final_utts"]:
                errs.append(f"a decision for utterance {utt} after its final decision (TD-6 / TD-7)")
            elif ev.get("is_final") is True:
                st["final_utts"].add(utt)
                if len(st["final_utts"]) > 4096:  # bounded memory: keep the newest utterance ids
                    st["final_utts"] = set(sorted(st["final_utts"])[-2048:])
        return errs

    def _process(self, items: list[Item]) -> list[Item]:
        out: list[Item] = []
        for sid, ev in items:
            typ = ev.get("type")
            if typ == STATUS:
                if ev.get("status") in ("lost", "closed", "replaced"):
                    self.streams.pop(sid, None)
                out.append((sid, ev))
                continue
            if typ == "trust_decision":
                errs = self._decision(sid, ev)
                if errs:
                    self.counts["invalid_decisions"] += 1
                    self._note(sid, "trust_decision", errs)
                    if self.on_invalid == "cut":
                        continue
                out.append((sid, ev))
                continue
            st = self.streams.setdefault(sid, _VState())
            if typ == "header":
                errs = header_errors(ev, self.level)
                if errs:
                    self.counts["invalid_headers"] += 1
                    self._note(sid, "header", errs)
                    if self.on_invalid == "cut":
                        had_stream = st.header_ok
                        self.streams[sid] = _VState()
                        if had_stream:
                            out.append(status(sid, "lost", "invalid header"))
                        continue
                ns = _VState()
                ns.header_ok, ns.V = True, len(ev.get("vocab") or [])
                self.streams[sid] = ns
                out.append((sid, ev))
                continue
            if not st.header_ok and self.on_invalid == "cut":
                self.counts["dropped_no_header"] += 1
                continue
            errs = self.event_errors(st, ev) if not st.ended else []
            if errs:
                self.counts["invalid_events"] += 1
                self._note(sid, typ, errs)
                if self.on_invalid == "cut":
                    out.append(status(sid, "gap", f"invalid {typ} event"))
                    continue
            elif typ == "frame":
                st.last_t = float(ev["t"])
            elif typ == "end":
                st.ended = True
            out.append((sid, ev))
        return out


# ---------------------------------------------------------------------------
# trust
# ---------------------------------------------------------------------------


class _CollectorTrustRunner(W.WSTrustRunner):
    """:class:`fidetype.adapters.ws.WSTrustRunner` (the loss rules) for any receiver.

    Streams that come from a WebSocket receiver keep the ``ws`` record of the reference server.
    Streams from other receivers get a plain ``trust_decision`` (no ``ws`` record).
    """

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self.ws_streams: set[str] = set()

    def handle(self, items: Any) -> list[Any]:
        items = list(items)
        for sid, ev in items:
            if "ws_seq" in ev or "ws_t_recv" in ev:
                self.ws_streams.add(sid)
        return super().handle(items)

    def _emit(self, sid: str, d: Any, trigger: dict[str, Any] | None) -> Any:
        if sid in self.ws_streams:
            return super()._emit(sid, d, trigger)
        ev = d.to_event(include_text=self.include_text)
        if self.sink is not None:
            self.sink(ev)
        self.summary.decisions += 1
        if d.final:
            self.summary.final_decisions += 1
            self.utt[sid] = {"frames": 0, "gaps": 0}
        return d


#: The rules version that the collector stamps on every ``trust_decision`` (spec 6.1, VER-1, TD-F3).
DECISION_SPEC_VERSION = "1.0"


def blank_safe_config(cfg: Any, name: str = "trust", log: Callable[[str], None] | None = None) -> Any:
    """Return a trust configuration that can never COMMIT a blank text (TD-9, a MUST NOT for 1.x decisions).

    - A ``trust`` policy without a commit gate, or with a gate that allows an empty text
      (``min_chars = 0`` and ``min_words = 0``), gets the commit gate with ``min_chars = 1``
      (M2-18; the other gate fields stay). The copy has a new ``config_id``; the decisions carry it.
    - An ``always_commit`` policy can COMMIT an empty text and has no gate: refused (ValueError).
    """
    from dataclasses import replace

    from fidetype.trust.content import CommitGate

    if cfg.policy_class != "trust":
        raise ValueError(f"policy_class {cfg.policy_class!r} can commit a blank text; the collector stamps "
                         f"spec_version {DECISION_SPEC_VERSION!r} on its decisions and TD-9 forbids that. "
                         "Use a 'trust' policy")
    gate = cfg.gate
    if gate is not None and (gate.min_chars >= 1 or gate.min_words >= 1):
        return cfg
    new_gate = CommitGate(1, 0, None) if gate is None else replace(gate, min_chars=1)
    out = replace(cfg, commit_gate=new_gate.to_dict())
    if log is not None:
        log(f"processors.{name}: commit gate min_chars = 1 added (no blank COMMIT, TD-9 for spec_version "
            f"{DECISION_SPEC_VERSION}); config_id {cfg.config_id} -> {out.config_id}")
    return out


#: Actions whose ``shown`` lists candidates for the user (TD-12).
OFFER_ACTIONS = ("OFFER", "ASK", "OFFER_WORDS")
#: Text added to ``reason`` when the collector drops blank candidates (TD-12).
BLANK_REASON = "TD-12: blank candidates dropped"


def drop_blank_candidates(ev: dict[str, Any]) -> tuple[dict[str, Any], int, bool]:
    """Remove blank texts (spec 1.4) from ``shown`` of a text OFFER, ASK or OFFER_WORDS (TD-12, NTS 1.0 RC2).

    Returns ``(event, dropped, abstained)``. The event is a new dict only when something changed.
    When no candidate is left, an OFFER or OFFER_WORDS becomes ``ABSTAIN`` with ``shown = []``: TD-9
    says that a decision that shows no text is an ABSTAIN, and an OFFER without ``shown`` would look
    like a privacy log (TD-10), where the text exists but is hidden. An ASK stays an ASK (it asks the
    user to try again; it needs no candidate). ``reason`` gets :data:`BLANK_REASON`.
    """
    sh = ev.get("shown")
    if ev.get("action") not in OFFER_ACTIONS or ev.get("profile") in ("intent", "control") or not isinstance(sh, list):
        return ev, 0, False
    keep = [x for x in sh if not (isinstance(x, str) and not x.strip())]
    dropped = len(sh) - len(keep)
    if not dropped:
        return ev, 0, False
    out = dict(ev)
    out["shown"] = keep
    abstained = not keep and ev.get("action") in ("OFFER", "OFFER_WORDS")
    if abstained:
        out["action"] = "ABSTAIN"
    why = BLANK_REASON + ("; no candidate left: ABSTAIN" if abstained else "")
    out["reason"] = f"{ev['reason']}; {why}" if isinstance(ev.get("reason"), str) and ev["reason"] else why
    return out, dropped, abstained


class TrustProcessor(Processor):
    """The streaming trust layer (:class:`fidetype.trust.streaming.StreamingTrustLayer`), one session per stream.

    Input: NTS events and status items. Output: ``trust_decision`` events only (TD-4: decisions are
    output, they never go back into an input stream). Loss rules from the reference runner: a
    ``gap``, ``lost`` or ``replaced`` status drops the open utterance without a decision; after a gap
    the frames up to the next boundary are dropped too. At shutdown an open utterance is dropped.

    Every decision gets ``spec_version: "1.0"``. The trust configuration then must never COMMIT a
    blank text (TD-9 is a MUST NOT for 1.x): :func:`blank_safe_config` adds the commit gate when
    the configuration has none. A gated COMMIT becomes an OFFER whose candidates can be blank:
    :func:`drop_blank_candidates` removes them (TD-12) and turns an OFFER with no candidate left
    into an ABSTAIN. The provenance ledger (option ``ledger``) keeps the trust layer's own decision;
    ``reason`` of the emitted decision names the TD-12 step.
    """

    type = "trust"

    def __init__(self, name: str, log: Callable[[str], None], config_path: Any, decoder: str = "none",
                 max_attempts: int = 2, route: str = "auto", min_signal_quality: float | None = None,
                 declaration_check: str = "warn", ledger: Any = None) -> None:
        super().__init__(name, log)
        from fidetype.trust.frozen import FrozenTrustConfig
        from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, frame_decoder

        self.cfg = blank_safe_config(FrozenTrustConfig.load(config_path), name, log)
        self.layer = StreamingTrustLayer(
            self.cfg, decode_fn=frame_decoder(decoder), ledger=ledger,
            streaming=StreamingConfig(max_attempts=max_attempts, route=route, min_signal_quality=min_signal_quality,
                                      declaration_check=declaration_check))
        self._out: list[Item] = []
        self.counts.update(gated_commits=0, blank_candidates_dropped=0, blank_offers_abstained=0)
        self.runner = _CollectorTrustRunner(self.layer, sink=self._sink, include_text=True,
                                            log=lambda m: log(f"processors.{name}: {m}"))

    @property
    def config_id(self) -> str:
        return self.cfg.config_id

    def _sink(self, ev: dict[str, Any]) -> None:
        ev = {"type": ev["type"], "spec_version": DECISION_SPEC_VERSION, **ev}  # spec 6.1, VER-1, TD-F3
        if str(ev.get("reason", "")).startswith(GATE_REASON):
            self.counts["gated_commits"] += 1
        ev, dropped, abstained = drop_blank_candidates(ev)  # TD-12
        self.counts["blank_candidates_dropped"] += dropped
        self.counts["blank_offers_abstained"] += abstained
        self._out.append((str(ev.get("session", "")), ev))

    def _process(self, items: list[Item]) -> list[Item]:
        self._out = []
        self.runner.handle(items)
        out, self._out = self._out, []
        return out

    def finish(self) -> list[Item]:
        for sid in list(self.layer.sessions):
            if self.runner._pending(sid):
                self.runner.abort(sid, "collector stopped inside an utterance")
        return []

    def stats(self) -> dict[str, Any]:
        s = self.runner.summary
        return {**super().stats(), "config_id": self.cfg.config_id, "decisions": s.decisions,
                "final_decisions": s.final_decisions, "events": s.events, "rejected_events": s.rejected_events,
                "aborted_utterances": s.aborted_utterances, "skipped_after_gap": s.skipped_after_gap,
                "sessions": len(self.layer.sessions)}


# ---------------------------------------------------------------------------
# redact
# ---------------------------------------------------------------------------


class RedactProcessor(Processor):
    """Remove decoded text from the output (SEC-7, TD-10, PRV-2).

    ``trust_decision.shown`` is removed. ``mode = "hmac"`` replaces it with ``shown_hmac`` (HMAC-SHA256
    hex per text, with the key from the environment variable ``key_env``), so an auditor who has the
    key can check a text without the log holding it. Each changed decision gets ``redaction``.
    With ``hypothesis_text = true`` (default) the ``text`` of each n-best item of a ``hypothesis``
    event is treated the same way (when input events pass through to an exporter).
    The key never appears in an output; ``key_id`` (optional) names it.
    """

    type = "redact"

    def __init__(self, name: str, log: Callable[[str], None], mode: str = "drop", key: bytes | None = None,
                 key_id: str | None = None, hypothesis_text: bool = True) -> None:
        super().__init__(name, log)
        if mode == "hmac" and not key:
            raise ValueError(f"processors.{name}: mode 'hmac' needs a non-empty key")
        self.mode = mode
        self._key = key
        self.key_id = key_id
        self.hypothesis_text = hypothesis_text
        self.counts.update(redacted_decisions=0, redacted_hypotheses=0)

    def _mac(self, text: str) -> str:
        return hmac.new(self._key or b"", text.encode("utf-8"), hashlib.sha256).hexdigest()

    def _record(self) -> dict[str, Any]:
        rec: dict[str, Any] = {"mode": "drop" if self.mode == "drop" else "hmac-sha256"}
        if self.key_id and self.mode == "hmac":
            rec["key_id"] = self.key_id
        return rec

    def _process(self, items: list[Item]) -> list[Item]:
        out: list[Item] = []
        for sid, ev in items:
            typ = ev.get("type")
            if typ == "trust_decision" and "shown" in ev:
                ev = dict(ev)
                shown = ev.pop("shown")
                if self.mode == "hmac" and isinstance(shown, list):
                    ev["shown_hmac"] = [self._mac(s) for s in shown if isinstance(s, str)]
                ev["redaction"] = self._record()
                self.counts["redacted_decisions"] += 1
            elif typ == "hypothesis" and self.hypothesis_text and isinstance(ev.get("nbest"), list):
                ev = copy.deepcopy(ev)
                for it in ev["nbest"]:
                    if isinstance(it, dict) and "text" in it:
                        t = it.pop("text")
                        if self.mode == "hmac" and isinstance(t, str):
                            it["text_hmac"] = self._mac(t)
                ev["redaction"] = self._record()
                self.counts["redacted_hypotheses"] += 1
            out.append((sid, ev))
        return out


# ---------------------------------------------------------------------------
# thin
# ---------------------------------------------------------------------------


class ThinProcessor(Processor):
    """Drop provisional decisions that carry no news; never drop a final decision or an input event.

    ``keep_provisional = "changes"`` (default): keep a provisional decision only when its action or
    its shown texts differ from the last kept provisional decision of the same utterance. ``"none"``:
    drop every provisional decision (consumers MUST NOT act on them, TD-1). ``"all"``: keep all.
    """

    type = "thin"

    def __init__(self, name: str, log: Callable[[str], None], keep_provisional: str = "changes") -> None:
        super().__init__(name, log)
        self.keep = keep_provisional
        self.last: dict[tuple[str, Any], tuple[Any, Any]] = {}
        self.counts.update(dropped_provisional=0)

    def _process(self, items: list[Item]) -> list[Item]:
        out: list[Item] = []
        for sid, ev in items:
            if ev.get("type") != "trust_decision" or self.keep == "all":
                out.append((sid, ev))
                continue
            key = (str(ev.get("session", sid)), ev.get("utterance"))
            if ev.get("is_final") is True:
                self.last.pop(key, None)
                out.append((sid, ev))
                continue
            sig = (ev.get("action"), tuple(ev.get("shown") or ()), tuple(ev.get("shown_hmac") or ()))
            if self.keep == "none" or self.last.get(key) == sig:
                self.counts["dropped_provisional"] += 1
                continue
            self.last[key] = sig
            if len(self.last) > 4096:
                self.last.pop(next(iter(self.last)))
            out.append((sid, ev))
        return out

