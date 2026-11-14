"""Conformance profile ``fep-0004``: NeuralTextStream over WebSocket (M6-11).

Tests the binding of ``spec/feps/0004-nts-over-websocket.md`` without a
network and without ``websockets``. Each golden vector is a JSON
**scenario** (schema ``fidetype.conformance.ws-scenario/1``).

``kind = "ingest"``
    The server side of the ``/nts`` path. ``steps`` script connections:
    ``open`` (with the offered subprotocols and an optional
    ``Authorization`` value), ``msg`` (a message as a JSON value), ``raw``
    (a text message as a string), ``binary``, ``drop`` (the connection ends
    without an ``end`` event), ``close`` and ``tick``. Each step has a time
    ``at`` (seconds, not decreasing); the time-outs run before each step.
    The reference consumer plays the steps through
    :class:`~fidetype.adapters.ws.IngestCore` and
    :class:`~fidetype.adapters.ws.WSTrustRunner` into a
    :class:`~fidetype.trust.streaming.StreamingTrustLayer` (a fixed loose
    synthetic config; CTC greedy decoder on the frames route). At the end
    it drops the utterances of streams that wait for a resume and closes
    the open utterance of every connected stream. A **refusal** (a close
    code 1002, 1003, 1007, 1008, 1009 or 4000) rejects the vector.
``kind = "subscribe"``
    The client side of the ``/decisions`` path: the ``messages`` that a
    subscriber receives, after a ``ws_subscribe`` with ``from_seq`` (default
    1; ``null`` = new decisions only). The reference subscriber
    (:class:`~fidetype.adapters.ws.SubscriberCore`) checks the welcome, the
    ``ws_seq`` order (a gap means "resubscribe") and the FEP-0001 rules.

All content is synthetic.
"""

from __future__ import annotations

import json
from os import PathLike
from pathlib import Path
from typing import Any, Callable

from fidetype.conformance.checks import FAIL, PASS, SKIP, CheckResult
from fidetype.conformance.io import StreamRejected
from fidetype.conformance.report import TargetReport
from fidetype.conformance.vectors import BASE_META, Vector, _lp

SUFFIXES = (".json",)
FEP = "FEP-0004"
SCENARIO_SCHEMA = "fidetype.conformance.ws-scenario/1"
KINDS = ("ingest", "subscribe")
STEP_KINDS = ("open", "msg", "raw", "binary", "drop", "close", "tick")
SETTING_KEYS = ("reorder_window", "reorder_timeout_s", "resume_timeout_s", "max_batch", "ack_every", "window",
                "ack_interval_s", "token")

#: (id, keyword, FEP clause, title)
CHECKS = [
    ("FEP4-HANDSHAKE", "MUST", "4-5", "Subprotocol nts-ws.0.1; the first message is the NTS header with a known binding"),
    ("FEP4-FRAMING", "MUST", "3, 6", "Text messages with one JSON object each; ws_seq on every event; batches consecutive"),
    ("FEP4-ORDER", "MUST", "6", "Duplicates dropped, reorder window, gaps drop the open utterance"),
    ("FEP4-RESUME", "MUST", "8", "Resume after a broken connection; no decision on a cut utterance"),
    ("FEP4-AUTH", "MUST", "9", "Token hook: a refused token closes with 1008"),
    ("FEP4-DECISIONS", "MUST", "7", "Decisions channel: welcome, ws_seq without gaps (or resubscribe), FEP-0001 rules"),
    ("FEP4-CONSUME", "MUST", "3-8", "The reference consumer accepts the scenario"),
]
_META = {c[0]: c for c in CHECKS}

HOW_TO_USE = ("FEP-0004 profile. Each vector is a JSON scenario (schema fidetype.conformance.ws-scenario/1). "
              "kind 'ingest': play the steps into your /nts server as if they came from WebSocket connections "
              "(open, msg, raw, binary, drop, close, tick; 'at' is the time in seconds). A refusal close code "
              "(1002, 1003, 1007, 1008, 1009, 4000) rejects the vector. kind 'subscribe': feed the messages to your "
              "/decisions client. A conforming implementation accepts exactly the vectors with expect = accept and, "
              "for those, gives the values in 'expected' (FEP-0004 section 11).")

_POLICY = dict(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)


class Refused(StreamRejected):
    """A refusal of the reference server, with the profile check it fails."""

    def __init__(self, message: str, clause: str, check_id: str) -> None:
        super().__init__(message, clause)
        self.check_id = check_id


def refusal_check(code: int, reason: str, detail: str) -> str:
    """The profile check that a refusal (close code, ws_error code, detail) fails."""
    if code == 1008:
        return "FEP4-AUTH"
    if code in (1002, 4000) or (reason == "bad_header" and "resume" not in detail):
        return "FEP4-HANDSHAKE"
    if reason == "bad_header":
        return "FEP4-RESUME"
    return "FEP4-FRAMING"


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x: Any) -> bool:
    import math

    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


# --- scenario players ----------------------------------------------------------------------------


def run_ingest_scenario(sc: dict[str, Any]) -> dict[str, Any]:
    """Play an ``ingest`` scenario through the reference server core. Raise on rejection."""
    from fidetype.adapters.ws import (REFUSAL_CODES, WS_ACK, WS_STATUS, WS_WELCOME, IngestCore, IngestSettings,
                                      WSTrustRunner, token_checker)
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer
    from fidetype.trust.testing import greedy_nbest

    settings = sc.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    bad = [k for k in settings if k not in SETTING_KEYS]
    if bad:
        raise ValueError(f"unknown settings {bad}")
    token = settings.get("token")
    if token is not None and not (isinstance(token, str) and token):
        raise ValueError("settings.token must be a non-empty string")
    ingest = IngestSettings(**{k: v for k, v in settings.items() if k != "token"})
    route = sc.get("route", "frames")
    if route not in ("frames", "hypothesis"):
        raise ValueError(f"unknown route {route!r}")
    steps = sc.get("steps")
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    core = IngestCore(ingest, auth=token_checker(token) if token else None)
    cfg = FrozenTrustConfig(name="fep-0004-conformance").with_policy(**_POLICY)
    layer = StreamingTrustLayer(cfg, decode_fn=greedy_nbest if route == "frames" else None,
                                streaming=StreamingConfig(route=route, max_attempts=1))
    decisions: list[dict[str, Any]] = []
    runner = WSTrustRunner(layer, sink=decisions.append, on_bad_event="raise", clock=lambda: 0.0)
    seen: list[dict[str, Any]] = []
    sends: list[dict[str, Any]] = []
    closes: list[list[int]] = []

    def apply(eff: Any) -> None:
        sends.extend(m for _, m in eff.sends)
        for cid, code, reason in eff.closes:
            closes.append([cid, code])
            if code in REFUSAL_CODES:
                detail = next((m.get("detail", "") for c, m in eff.sends if c == cid and m.get("type") == "ws_error"), reason)
                raise Refused(f"connection {cid} refused with close code {code} ({reason}: {detail})", f"{FEP} 9",
                              refusal_check(code, reason, str(detail)))
        seen.extend(ev for _, ev in eff.items if ev.get("type") != WS_STATUS)
        runner.handle(eff.items)

    at = 0.0
    for n, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError(f"step {n} must be an object")
        kinds = [k for k in STEP_KINDS if k in step]
        if len(kinds) != 1:
            raise ValueError(f"step {n} needs exactly one of {list(STEP_KINDS)}")
        kind = kinds[0]
        t = step.get("at", at)
        if not (_is_num(t) and t >= at):
            raise ValueError(f"step {n}: at must be a number >= the previous at")
        at = float(t)
        apply(core.tick(at))
        if kind == "tick":
            continue
        cid = step.get("conn")
        if not (_is_int(cid) and cid >= 1):
            raise ValueError(f"step {n}: conn must be an integer >= 1")
        if kind == "open":
            o = step["open"]
            if not isinstance(o, dict):
                raise ValueError(f"step {n}: open must be an object")
            subs = o.get("subprotocols", ["nts-ws.0.1"])
            if not (isinstance(subs, list) and all(isinstance(s, str) for s in subs)):
                raise ValueError(f"step {n}: subprotocols must be a list of strings")
            auth = o.get("authorization")
            if auth is not None and not isinstance(auth, str):
                raise ValueError(f"step {n}: authorization must be a string")
            apply(core.open(cid, subs, auth, at))
        elif kind == "msg":
            apply(core.message(cid, step["msg"], at))
        elif kind == "raw":
            if not isinstance(step["raw"], str):
                raise ValueError(f"step {n}: raw must be a string")
            apply(core.message(cid, step["raw"], at))
        elif kind == "binary":
            if step["binary"] is not True:
                raise ValueError(f"step {n}: binary must be true")
            apply(core.message(cid, b"\x00", at))
        else:  # drop, close
            if step[kind] is not True:
                raise ValueError(f"step {n}: {kind} must be true")
            apply(core.disconnect(cid, at))
    apply(core.finish(at))
    for sid in core.live_streams():
        runner.flush(sid)
    types: dict[str, int] = {}
    for e in seen:
        types[e["type"]] = types.get(e["type"], 0) + 1
    st = core.stats
    return {
        "streams": st.streams,
        "event_types": dict(sorted(types.items())),
        "frames": types.get("frame", 0),
        "decisions": len(decisions),
        "final_decisions": sum(d["is_final"] for d in decisions),
        "sessions": sorted({d["session"] for d in decisions}),
        "aborted_utterances": runner.summary.aborted_utterances,
        "skipped_after_gap": runner.summary.skipped_after_gap,
        "duplicates": st.duplicates, "reordered": st.reordered, "gaps": st.gaps,
        "missing_events": st.missing_events, "resumes": st.resumes, "takeovers": st.takeovers,
        "lost_streams": st.lost_streams, "ignored_controls": st.ignored_controls,
        "welcomes": [[m["stream_id"], m["seq"], m["resumed"]] for m in sends if m.get("type") == WS_WELCOME],
        "acks": [m["seq"] for m in sends if m.get("type") == WS_ACK],
        "closes": closes,
    }


def run_subscribe_scenario(sc: dict[str, Any]) -> dict[str, Any]:
    """Feed a ``subscribe`` scenario to the reference subscriber. Raise on rejection."""
    from fidetype.adapters.ws import SubscriberCore, SubscriberError

    msgs = sc.get("messages")
    if not isinstance(msgs, list):
        raise ValueError("messages must be a list")
    from_seq = sc.get("from_seq", 1)
    if from_seq is not None and not (_is_int(from_seq) and from_seq >= 1):
        raise ValueError("from_seq must be an integer >= 1 or null")
    core = SubscriberCore(from_seq)
    try:
        for m in msgs:
            core.receive(m)
        return core.finish()
    except SubscriberError as e:
        raise StreamRejected(str(e), f"{FEP} 7") from None


def load_scenario(path: str | PathLike[str]) -> dict[str, Any]:
    sc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(sc, dict) or sc.get("schema") != SCENARIO_SCHEMA or sc.get("kind") not in KINDS:
        raise StreamRejected(f"not a {SCENARIO_SCHEMA} scenario", FEP)
    return sc


def consume(path: str | PathLike[str]) -> dict[str, Any]:
    """Reference consumer of the profile: return a summary, or raise."""
    sc = load_scenario(path)
    return run_ingest_scenario(sc) if sc["kind"] == "ingest" else run_subscribe_scenario(sc)


def _res(cid: str, errs: list[str] | None, msg_ok: str = "", skipped: str | None = None) -> CheckResult:
    _, kw, clause, title = _META[cid]
    if skipped is not None:
        status, msg = SKIP, skipped
    elif errs:
        status, msg = FAIL, "; ".join(errs[:6])
    else:
        status, msg = PASS, msg_ok
    return CheckResult(cid, "core", kw, f"{FEP} {clause}", title, status, msg)


def check_file(path: str | PathLike[str]) -> TargetReport:
    """Producer check: a scenario ``.json`` file (for example a recorded session)."""
    p = Path(path)
    try:
        sc = load_scenario(p)
    except Exception as e:  # noqa: BLE001
        return TargetReport(str(p), "file", [_res("FEP4-CONSUME", [f"{type(e).__name__}: {e}"])], {"format": "ws-scenario"})
    cid = "FEP4-DECISIONS" if sc["kind"] == "subscribe" else "FEP4-CONSUME"
    try:
        run_ingest_scenario(sc) if sc["kind"] == "ingest" else run_subscribe_scenario(sc)
        res = _res(cid, [], "accepted")
    except Refused as e:
        res = _res(e.check_id, [str(e)])
    except Exception as e:  # noqa: BLE001 - any exception is a rejection
        res = _res(cid, [f"{type(e).__name__}: {e}"])
    return TargetReport(str(p), "file", [res], {"format": "ws-scenario", "kind": sc["kind"]})


# --- golden vectors ----------------------------------------------------------------------------

VOCAB5 = ["<blank>", "a", "b", "c", " "]
FP = 0.04
HEADER = {"type": "header", "spec_version": "0.1", "vocab": VOCAB5, "vocab_type": "char", "blank_id": 0,
          "source": "conformance-vector", "frame_period": FP, "latency": 0.0, "clock_domain": "trial",
          "meta": dict(BASE_META)}
SUB = "nts-ws.0.1"


def _hdr(sid: str | None = "acme-1", resume: bool | None = None, **over: Any) -> dict[str, Any]:
    h = dict(HEADER)
    ws: dict[str, Any] = {"binding": "nts-ws/0.1"}
    if sid is not None:
        ws["stream_id"] = sid
    if resume is not None:
        ws["resume"] = resume
    h["ws"] = ws
    h.update(over)
    return h


def _frames(T: int, seed: int, t0: float = 0.0) -> list[dict[str, Any]]:
    lp = _lp(T, len(VOCAB5), seed)
    return [{"type": "frame", "t": round(t0 + i * FP, 6), "log_probs": [round(float(x), 4) for x in row]}
            for i, row in enumerate(lp)]


def _numbered(evs: list[dict[str, Any]], start: int = 1) -> list[dict[str, Any]]:
    return [{**e, "ws_seq": start + i} for i, e in enumerate(evs)]


def _two_utts() -> list[dict[str, Any]]:
    """Two utterances (4 + 4 frames) with segment_end, then end: 11 events, ws_seq 1-11."""
    return _numbered(_frames(4, 1) + [{"type": "segment_end"}] + _frames(4, 2, 1.0) + [{"type": "segment_end"},
                                                                                        {"type": "end"}])


def _open(conn: int = 1, at: float = 0.0, **o: Any) -> dict[str, Any]:
    return {"at": at, "conn": conn, "open": {"subprotocols": [SUB], **o}}


def _msgs(evs: list[Any], conn: int = 1, at: float = 0.0) -> list[dict[str, Any]]:
    return [{"at": at, "conn": conn, "msg": e} for e in evs]


def _scenario(kind: str, description: str, **body: Any) -> dict[str, Any]:
    return {"schema": SCENARIO_SCHEMA, "kind": kind, "fep": FEP, "description": description, **body}


def _ingest(desc: str, steps: list[dict[str, Any]], route: str = "frames",
            settings: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"route": route, "steps": steps}
    if settings:
        body["settings"] = settings
    return _scenario("ingest", desc, **body)


def _w_json(obj: dict[str, Any]) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
                        newline="\n")

    return w


def _td(ws_seq: int, seq: int, utt: int, final: bool = True, action: str = "COMMIT", text: str = "ab") -> dict[str, Any]:
    return {"type": "trust_decision", "session": "acme-1", "seq": seq, "utterance": utt, "is_final": final,
            "action": action, "shown": [text], "p_top1": 0.9 if final else 0.6, "score_semantics": "calibrated_prob",
            "set_size": 1, "guard_risk": 0.1, "config_id": "tcfg-0123456789abcdef", "ws_seq": ws_seq,
            "ws": {"stream_id": "acme-1", "binding": "nts-ws/0.1"}}


WELCOME = {"type": "ws_welcome", "binding": "nts-ws/0.1", "role": "decisions", "spec": "FEP-0001",
           "config_id": "tcfg-0123456789abcdef", "seq": 0, "first_available": 1}


def build_vectors() -> list[Vector]:
    vs: list[Vector] = []

    def add(vid: str, file: str, expect: str, clause: str, desc: str, sc: dict[str, Any],
            expected: dict | None = None, failing: str = "FEP4-CONSUME") -> None:
        vs.append(Vector(vid, file, expect, f"{FEP} {clause}", desc, None, expected or {},
                         None if expect == "accept" else failing, _w_json(sc)))

    ev = _two_utts()
    base = [_open(), {"at": 0.0, "conn": 1, "msg": _hdr()}]
    full = base + _msgs(ev) + [{"at": 0.5, "conn": 1, "close": True}]
    # --- accept: framing
    add("W01", "w01-one-message-per-event.json", "accept", "3, 5, 6",
        "One stream, one message per event: two utterances, then end and a clean close",
        _ingest("one message per event", full),
        {"streams": 1, "frames": 8, "final_decisions": 2, "aborted_utterances": 0, "sessions": ["acme-1"],
         "event_types": {"end": 1, "frame": 8, "header": 1, "segment_end": 2},
         "welcomes": [["acme-1", 0, False]], "acks": [11], "closes": []})
    add("W02", "w02-batches.json", "accept", "6 r4",
        "The same events in ws_batch messages (4 + 4 + 3 events): the same decisions as W01",
        _ingest("batches", base + [{"at": 0.0, "conn": 1, "msg": {"type": "ws_batch", "events": ev[i:i + 4]}}
                                   for i in range(0, 11, 4)] + [{"at": 0.5, "conn": 1, "close": True}]),
        {"streams": 1, "frames": 8, "final_decisions": 2, "acks": [11]})
    hyp = _numbered([{"type": "hypothesis", "id": "h1", "is_final": False, "score_semantics": "none",
                      "nbest": [{"text": "ab", "score": -1.5}]},
                     {"type": "hypothesis", "id": "h2", "revision_of": "h1", "is_final": True, "score_semantics": "none",
                      "nbest": [{"text": "ab", "score": -1.0}, {"text": "a", "score": -2.5}]},
                     {"type": "end"}])
    add("W03", "w03-hypothesis-route.json", "accept", "5, 6",
        "A hypothesis-only producer (empty vocab): one provisional and one final decision",
        _ingest("hypothesis route", [_open(), {"at": 0.0, "conn": 1, "msg": _hdr(vocab=[], blank_id=None)}] + _msgs(hyp),
                route="hypothesis"),
        {"decisions": 2, "final_decisions": 1, "event_types": {"end": 1, "header": 1, "hypothesis": 2}})
    add("W04", "w04-unknown-control-and-event.json", "accept", "4 r3",
        "An unknown ws_ control message is ignored; an unknown NTS event type passes to the layer (which ignores it)",
        _ingest("unknown types", base + _msgs([{"type": "ws_future", "x": 1}]) + _msgs(
            _numbered(_frames(3, 3) + [{"type": "vendor_note", "text": "hi"}, {"type": "end"}]))),
        {"ignored_controls": 1, "final_decisions": 1, "event_types": {"end": 1, "frame": 3, "header": 1, "vendor_note": 1}})
    add("W05", "w05-no-ws-record.json", "accept", "5 r3, 10 r2",
        "A header without the ws record (a 6.3-sketch producer with ws_seq): binding nts-ws/0.1 assumed, a server stream id",
        _ingest("no ws record", [_open(), {"at": 0.0, "conn": 1, "msg": {k: v for k, v in HEADER.items()}}] +
                _msgs(_numbered(_frames(3, 4) + [{"type": "end"}]))),
        {"welcomes": [["anon-1", 0, False]], "sessions": ["anon-1"], "final_decisions": 1})
    # --- accept: order
    add("W06", "w06-duplicates.json", "accept", "6 r2",
        "Every event is sent twice (a resend): the copies are dropped",
        _ingest("duplicates", base + _msgs([e for e in ev for _ in (0, 1)])),
        {"duplicates": 11, "frames": 8, "final_decisions": 2, "aborted_utterances": 0})
    swapped = ev[:2] + [ev[3], ev[2]] + ev[4:]
    add("W07", "w07-reorder-in-window.json", "accept", "6 r3",
        "ws_seq 4 arrives before 3 (inside the reorder window): released in order; same decisions as W01",
        _ingest("reorder", base + _msgs(swapped)),
        {"reordered": 1, "gaps": 0, "frames": 8, "final_decisions": 2})
    gap_steps = base + _msgs(ev[:2]) + _msgs(ev[3:5], at=0.1) + [{"at": 0.5, "tick": True}] + _msgs(ev[5:], at=0.6)
    add("W08", "w08-gap-timeout.json", "accept", "6 r3, 8 r1",
        "ws_seq 3 never arrives: after the reorder time-out (0.25 s) it is a gap; the first utterance is dropped",
        _ingest("gap after time-out", gap_steps),
        {"gaps": 1, "missing_events": 1, "aborted_utterances": 1, "skipped_after_gap": 1, "final_decisions": 1,
         "frames": 7})
    add("W09", "w09-gap-window-zero.json", "accept", "6 r3",
        "reorder_window 0: a missing ws_seq is a gap at once",
        _ingest("gap, window 0", base + _msgs(ev[:2] + ev[3:]), settings={"reorder_window": 0}),
        {"gaps": 1, "missing_events": 1, "aborted_utterances": 1, "skipped_after_gap": 1, "final_decisions": 1})
    # --- accept: resume
    add("W10", "w10-resume-lossless.json", "accept", "8 r2-r4",
        "The connection breaks inside the first utterance; the producer resumes (ack seq 3) and resends from 4: "
        "no abort, the same decisions as W01",
        _ingest("lossless resume", base + _msgs(ev[:3]) + [{"at": 0.2, "conn": 1, "drop": True},
                                                          _open(2, 1.0), {"at": 1.0, "conn": 2, "msg": _hdr(resume=True)}] +
                _msgs(ev[2:], conn=2, at=1.0) + [{"at": 1.5, "conn": 2, "close": True}]),
        {"resumes": 1, "aborted_utterances": 0, "final_decisions": 2, "duplicates": 1,
         "welcomes": [["acme-1", 0, False], ["acme-1", 3, True]], "frames": 8})
    add("W11", "w11-resume-timeout.json", "accept", "8 r5",
        "The connection breaks and no resume comes within resume_timeout_s (2 s): the stream is lost, no decision on the cut utterance",
        _ingest("resume time-out", base + _msgs(ev[:3]) + [{"at": 0.2, "conn": 1, "drop": True}, {"at": 5.0, "tick": True}],
                settings={"resume_timeout_s": 2.0}),
        {"lost_streams": 1, "aborted_utterances": 1, "final_decisions": 0})
    add("W12", "w12-resume-unknown.json", "accept", "8 r6",
        "A resume header for a stream the server does not know: a new stream (resumed false, seq 0)",
        _ingest("resume unknown", [_open(), {"at": 0.0, "conn": 1, "msg": _hdr("other-7", resume=True)}] +
                _msgs(_numbered(_frames(3, 5) + [{"type": "end"}]))),
        {"welcomes": [["other-7", 0, False]], "resumes": 0, "final_decisions": 1})
    add("W13", "w13-takeover.json", "accept", "8 r7",
        "A second connection resumes the stream while the first is still open: the first is closed with 4001",
        _ingest("take-over", base + _msgs(ev[:3]) + [_open(2, 0.3), {"at": 0.3, "conn": 2, "msg": _hdr(resume=True)}] +
                _msgs(ev[3:], conn=2, at=0.3) + _msgs(ev[3:5], conn=1, at=0.4)),
        {"takeovers": 1, "closes": [[1, 4001]], "final_decisions": 2, "aborted_utterances": 0})
    other = _numbered(_frames(3, 6) + [{"type": "end"}])
    add("W14", "w14-two-producers.json", "accept", "5 r4",
        "Two producers at the same time (two stream ids): one trust session each",
        _ingest("two producers", base + [_open(2), {"at": 0.0, "conn": 2, "msg": _hdr("acme-2")}] +
                [s for pair in zip(_msgs(ev[:4]), _msgs(other, conn=2)) for s in pair] + _msgs(ev[4:])),
        {"streams": 2, "sessions": ["acme-1", "acme-2"], "final_decisions": 3})
    add("W15", "w15-token-message.json", "accept", "9 r2",
        "Token required; the client sends ws_auth before the header (a browser cannot set headers)",
        _ingest("token in ws_auth", [_open(), {"at": 0.0, "conn": 1, "msg": {"type": "ws_auth", "token": "s3cret"}},
                                     {"at": 0.0, "conn": 1, "msg": _hdr()}] + _msgs(ev), settings={"token": "s3cret"}),
        {"final_decisions": 2})
    add("W16", "w16-token-header.json", "accept", "9 r1",
        "Token required; the client sends Authorization: Bearer in the opening handshake",
        _ingest("token in header", [_open(authorization="Bearer s3cret"), {"at": 0.0, "conn": 1, "msg": _hdr()}] + _msgs(ev),
                settings={"token": "s3cret"}),
        {"final_decisions": 2})
    add("W17", "w17-ack-every.json", "accept", "7 r1",
        "ack_every 4: a ws_ack after every 4 released events and at end",
        _ingest("acks", full, settings={"ack_every": 4}), {"acks": [4, 8, 11]})
    # --- reject: ingest
    add("W18", "w18-first-not-header.json", "reject", "5 r1", "The first message is a frame, not the header",
        _ingest("first not header", [_open()] + _msgs(ev)), failing="FEP4-HANDSHAKE")
    add("W19", "w19-no-subprotocol.json", "reject", "4 r1", "The client offers no subprotocol",
        _ingest("no subprotocol", [{"at": 0.0, "conn": 1, "open": {"subprotocols": []}}, {"at": 0.0, "conn": 1, "msg": _hdr()}]),
        failing="FEP4-HANDSHAKE")
    add("W20", "w20-unknown-binding.json", "reject", "10 r3", 'ws.binding "nts-ws/9.0" is not known (close 4000)',
        _ingest("unknown binding", [_open(), {"at": 0.0, "conn": 1, "msg": {**_hdr(), "ws": {"binding": "nts-ws/9.0"}}}]),
        failing="FEP4-HANDSHAKE")
    add("W21", "w21-header-version.json", "reject", "5 r2", 'Header spec_version "9.9"',
        _ingest("spec version", [_open(), {"at": 0.0, "conn": 1, "msg": _hdr(spec_version="9.9")}]), failing="FEP4-HANDSHAKE")
    add("W22", "w22-binary.json", "reject", "3 r1", "A binary message (close 1003)",
        _ingest("binary", base + [{"at": 0.0, "conn": 1, "binary": True}]), failing="FEP4-FRAMING")
    add("W23", "w23-not-json.json", "reject", "3 r2", "A text message that is not JSON (close 1007)",
        _ingest("not JSON", base + [{"at": 0.0, "conn": 1, "raw": "{\"type\": \"frame\", "}]), failing="FEP4-FRAMING")
    add("W24", "w24-no-ws-seq.json", "reject", "6 r1", "An event without ws_seq",
        _ingest("no ws_seq", base + _msgs([{k: v for k, v in ev[0].items() if k != "ws_seq"}])), failing="FEP4-FRAMING")
    add("W25", "w25-float-ws-seq.json", "reject", "6 r1", "ws_seq 1.5 is not an integer",
        _ingest("float ws_seq", base + _msgs([{**ev[0], "ws_seq": 1.5}])), failing="FEP4-FRAMING")
    add("W26", "w26-batch-not-consecutive.json", "reject", "6 r4", "A batch with ws_seq 1, 2, 4",
        _ingest("batch order", base + _msgs([{"type": "ws_batch", "events": [ev[0], ev[1], ev[3]]}])), failing="FEP4-FRAMING")
    add("W27", "w27-batch-too-big.json", "reject", "6 r4", "A batch of 5 events with max_batch 4 (close 1009)",
        _ingest("batch size", base + _msgs([{"type": "ws_batch", "events": ev[:5]}]), settings={"max_batch": 4}),
        failing="FEP4-FRAMING")
    add("W28", "w28-resume-header-differs.json", "reject", "8 r3", "The resume header has another vocab",
        _ingest("resume header", base + _msgs(ev[:3]) + [{"at": 0.2, "conn": 1, "drop": True}, _open(2, 1.0),
                                                         {"at": 1.0, "conn": 2, "msg": _hdr(resume=True, vocab=["<blank>", "x", "y", "z", " "])}]),
        failing="FEP4-RESUME")
    add("W29", "w29-bad-token.json", "reject", "9 r3", "Token required; ws_auth has the wrong token (close 1008)",
        _ingest("bad token", [_open(), {"at": 0.0, "conn": 1, "msg": {"type": "ws_auth", "token": "guess"}},
                              {"at": 0.0, "conn": 1, "msg": _hdr()}], settings={"token": "s3cret"}), failing="FEP4-AUTH")
    add("W30", "w30-bad-frame.json", "reject", "5 r2", "A frame with 4 log-probabilities for a 5-token vocab (the layer refuses it)",
        _ingest("bad frame", base + _msgs([{**ev[0], "log_probs": ev[0]["log_probs"][:4]}])), failing="FEP4-CONSUME")
    # --- subscribe
    dec = [_td(1, 0, 0, final=False, action="OFFER"), _td(2, 1, 0), _td(3, 2, 1, text="ba")]
    add("W31", "w31-decisions.json", "accept", "7",
        "Welcome, then a provisional OFFER and two final COMMITs with ws_seq 1-3",
        _scenario("subscribe", "decisions", messages=[WELCOME] + dec),
        {"decisions": 3, "final": 2, "acted": ["ab", "ba"], "gaps": [], "duplicates": 0})
    add("W32", "w32-decisions-gap-resubscribe.json", "accept", "7 r3-r4",
        "ws_seq 2 is missing: the subscriber resubscribes from 2; the replay repeats 3 (a duplicate)",
        _scenario("subscribe", "gap and resubscribe", messages=[WELCOME, dec[0], dec[2], {**WELCOME, "seq": 3, "replayed": 2},
                                                                dec[1], dec[2], dec[2]]),
        {"decisions": 3, "final": 2, "acted": ["ab", "ba"], "gaps": [2], "duplicates": 1})
    add("W33", "w33-decisions-missed.json", "accept", "7 r5",
        "The resubscribe asks for history the server no longer has: the welcome reports missed 2",
        _scenario("subscribe", "missed history", messages=[{**WELCOME, "seq": 5, "first_available": 3, "missed": 2},
                                                          _td(3, 2, 1, text="ba")]),
        {"decisions": 1, "missed": 2})
    add("W34", "w34-decisions-no-welcome.json", "reject", "7 r2", "The first message is a decision, not ws_welcome",
        _scenario("subscribe", "no welcome", messages=dec), failing="FEP4-DECISIONS")
    add("W35", "w35-decisions-bad-binding.json", "reject", "10 r3", 'Welcome binding "nts-ws/2.0"',
        _scenario("subscribe", "bad binding", messages=[{**WELCOME, "binding": "nts-ws/2.0"}] + dec), failing="FEP4-DECISIONS")
    add("W36", "w36-decisions-no-ws-seq.json", "reject", "7 r3", "A decision without ws_seq",
        _scenario("subscribe", "no ws_seq", messages=[WELCOME, {k: v for k, v in dec[0].items() if k != "ws_seq"}]),
        failing="FEP4-DECISIONS")
    add("W37", "w37-decisions-two-finals.json", "reject", "7 r6", "Two final decisions for one utterance (FEP-0001 rules 6-7)",
        _scenario("subscribe", "two finals", messages=[WELCOME, _td(1, 0, 0), _td(2, 1, 0, action="OFFER")]),
        failing="FEP4-DECISIONS")
    vs.sort(key=lambda v: v.vid)
    return vs


__all__ = ["CHECKS", "build_vectors", "check_file", "consume", "run_ingest_scenario", "run_subscribe_scenario"]
