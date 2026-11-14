"""Conformance profile ``fep-0005``: continuous-control events (P12-03).

Tests the rules of ``spec/feps/0005-control-events.md`` on JSON Lines files
of two kinds:

``input``
    A NeuralTextStream (line 1 is the ``header``) with a
    ``control_declaration``, ``control``, ``control_enable`` and v0.1
    ``pointer`` events. It may also carry FEP-0003 intent events (a click):
    the FEP-0003 input rules then apply too. It must pass the v0.1 core level.
``decisions``
    A decision log (only ``trust_decision`` lines). Control decisions have
    ``profile = "control"``; text and intent decisions may share the log
    (FEP-0001 / FEP-0003 rules).

The reference consumer (:func:`consume`) returns a summary. For a decision
log it holds ``moving_ticks`` (control COMMITs: ticks a bridge may move on),
``acted_intents`` and ``acted_texts``.

All vector content is synthetic. No data from people or animals.
"""

from __future__ import annotations

import math
from os import PathLike
from pathlib import Path
from typing import Any, Callable

from fidetype.conformance.checks import FAIL, PASS, SKIP, CheckResult
from fidetype.conformance.io import StreamRejected
from fidetype.conformance.profiles import fep0003 as f3
from fidetype.conformance.profiles.fep0001 import read_events, stream_kind
from fidetype.conformance.report import TargetReport
from fidetype.conformance.vectors import _frames, _header, _w_lines
from fidetype.trust.control import (CONTROL, CONTROL_ENABLE, DECLARATION_KEY, PROFILE, STATES, ControlDeclaration,
                                    validate_control_declaration, validate_control_event, validate_enable_event)
from fidetype.trust.intent import DECLARATION_KEY as INTENT_DECL
from fidetype.trust.intent import validate_intent_declaration

SUFFIXES = (".jsonl", ".ndjson")
FEP = "FEP-0005"
CONTROL_ACTIONS = ("COMMIT", "ABSTAIN")
MOVING = ("act", "attenuate")
#: Reasons that mean "no signal / no engagement": a decision with one of them MUST NOT move.
NO_MOTION_REASONS = ("no_signal", "no_signal_reference", "stale_input", "disengaged", "not_engaged", "absent")
SPEED_TOL = 1e-6

#: (id, keyword, FEP clause, title)
CHECKS = [
    ("FEP5-PARSE", "MUST", "1 (6.2 v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"),
    ("FEP5-KIND", "MUST", "1", "The file is an input stream (header first) or a decision log (only trust_decision)"),
    ("FEP5-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"),
    ("FEP5-DECL", "MUST", "2 table, r1-r4", "control_declaration has the defined form (dims, quantity, units, frame, rate, click intent)"),
    ("FEP5-CONTROL", "MUST", "3 table, r1-r4", "control and pointer events: declared, dims values, std per declaration, tick and t increase"),
    ("FEP5-ENABLE", "MUST", "4 table", "control_enable events have the defined form"),
    ("FEP5-INTENT", "MUST", "5 r6 (FEP-0003 2-4)", "Intent parts of the stream follow FEP-0003"),
    ("FEP5-TD-FORMAT", "MUST", "5 table, r1-r4", "Control trust_decision fields (profile, tick, state, velocity, gain, v_max, ttl_s, engagement; no shown)"),
    ("FEP5-TD-ORDER", "MUST", "5 r5", "Per session: seq increases over all profiles; control decisions are final; a moving tick is never reused"),
    ("FEP5-SAFETY", "MUST", "6 r1-r7", "No motion on hold/stop or no-signal reasons; speed <= v_max; re-engage after stop; no intent COMMIT while stopped"),
]
_META = {c[0]: c for c in CHECKS}

HOW_TO_USE = ("FEP-0005 profile. For each vector, load the file with your consumer. Input streams (line 1 = header) "
              "must follow v0.1 and FEP-0005 sections 2-4 (and FEP-0003 for intent events). Decision logs (only "
              "trust_decision lines) must follow sections 5-6; text and intent decisions in the same log follow "
              "FEP-0001 / FEP-0003. A conforming consumer accepts exactly the vectors with expect = accept. For a "
              "decision log, 'moving_ticks' lists the ticks a bridge may move on (control COMMITs), "
              "'acted_intents' the FEP-0003 intents and 'acted_texts' the FEP-0001 texts.")


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_control(e: dict[str, Any]) -> bool:
    return e.get("type") == "trust_decision" and e.get("profile") == PROFILE


# --- input rules ---------------------------------------------------------------------------


def _intent_ids(h: dict[str, Any]) -> tuple[list[str] | None, list[str]]:
    d = h.get(INTENT_DECL)
    if isinstance(d, dict) and not validate_intent_declaration(d):
        return [it["id"] for it in d["intents"]], [it["id"] for it in d["intents"] if it.get("role") == "null"]
    return None, []


def decl_errors(events: list[dict[str, Any]]) -> list[str]:
    out = []
    for h in events:
        if h["type"] == "header" and DECLARATION_KEY in h:
            ids, nulls = _intent_ids(h)
            out += [f"line {h['_line']}: {x}" for x in validate_control_declaration(h[DECLARATION_KEY], ids, nulls)]
    return out


def control_errors(events: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    decl: ControlDeclaration | None = None
    has = False
    last_tick: int | None = None
    last_t: float | None = None
    for e in events:
        n = e.get("_line")
        if e["type"] == "header":
            has = DECLARATION_KEY in e
            decl, last_tick, last_t = None, None, None
            if has:
                ids, nulls = _intent_ids(e)
                if not validate_control_declaration(e[DECLARATION_KEY], ids, nulls):
                    decl = ControlDeclaration.from_declaration(e[DECLARATION_KEY])
        elif e["type"] == CONTROL:
            if not has:
                out.append(f"line {n}: control event without a control_declaration in the header (rule 1)")
                continue
            if decl is None:
                continue  # FEP5-DECL reports it
            errs = validate_control_event(e, decl)
            out += [f"line {n}: {x}" for x in errs]
            if errs or e.get("source", "decoder") != "decoder":
                continue
            if last_tick is not None and e["tick"] <= last_tick:
                out.append(f"line {n}: tick {e['tick']} does not increase (rule 2)")
            if last_t is not None and e["t"] <= last_t:
                out.append(f"line {n}: t {e['t']} does not increase (rule 2)")
            last_tick, last_t = e["tick"], e["t"]
        elif e["type"] == "pointer" and has and decl is not None:
            if e.get("dims") != decl.dims:
                out.append(f"line {n}: pointer dims {e.get('dims')!r} != declared dims {decl.dims} (rule 4)")
    return out


def enable_errors(events: list[dict[str, Any]]) -> list[str]:
    return [f"line {e['_line']}: {x}" for e in events if e["type"] == CONTROL_ENABLE for x in validate_enable_event(e)]


def intent_compat_errors(events: list[dict[str, Any]]) -> list[str]:
    return f3.decl_errors(events) + f3.vocab_errors(events) + f3.intent_errors(events) + f3.feedback_errors(events)


# --- decision-log rules ----------------------------------------------------------------------


def td_control_format_errors(e: dict[str, Any]) -> list[str]:
    """Format errors of one ``trust_decision``: section 5 for control decisions, FEP-0003 / FEP-0001 for the others."""
    if not _is_control(e):
        return f3.td_intent_format_errors(e)
    from fidetype.conformance.profiles.fep0001 import td_format_errors

    errs = list(td_format_errors(e))
    n = e.get("_line", "?")
    x: list[str] = []
    for k in ("shown", "utterance", "unit"):
        if k in e:
            x.append(f"a control decision MUST NOT carry {k} (rule 1)")
    if not (_int(e.get("tick")) and e["tick"] >= 0):
        x.append("tick must be an integer >= 0")
    if e.get("is_final") is not True:
        x.append("a control decision MUST be final (is_final = true) (rule 2)")
    act, st = e.get("action"), e.get("state")
    if act not in CONTROL_ACTIONS:
        x.append(f"control action {act!r} is not one of {list(CONTROL_ACTIONS)}")
    if st not in STATES:
        x.append(f"state {st!r} is not one of {list(STATES)}")
    elif act in CONTROL_ACTIONS and (st in MOVING) != (act == "COMMIT"):
        x.append(f"state {st!r} does not fit action {act!r} (act/attenuate = COMMIT, hold/stop = ABSTAIN) (rule 3)")
    vel = e.get("velocity")
    if not (isinstance(vel, list) and 1 <= len(vel) <= 3 and all(_num(v) for v in vel)):
        x.append("velocity must be a list of 1-3 finite numbers")
    if "raw" in e and not (isinstance(e["raw"], list) and all(_num(v) for v in e["raw"])
                           and (not isinstance(vel, list) or len(e["raw"]) == len(vel))):
        x.append("raw must be a list of finite numbers, one per axis")
    if not (_num(e.get("gain")) and 0.0 <= e["gain"] <= 1.0):
        x.append("gain must be a number in [0, 1]")
    if not isinstance(e.get("units"), str):
        x.append("units is required (string)")
    if not (_num(e.get("v_max")) and e["v_max"] > 0):
        x.append("v_max is required: a number > 0 (rule 4)")
    if not (_num(e.get("ttl_s")) and e["ttl_s"] > 0):
        x.append("ttl_s is required: a number > 0 (rule 4)")
    if not (_int(e.get("engagement")) and e["engagement"] >= 0):
        x.append("engagement is required: an integer >= 0")
    if "authority" in e and not (_num(e["authority"]) and 0.0 <= e["authority"] <= 1.0):
        x.append("authority must be a number in [0, 1]")
    if "radius" in e:
        if not (_num(e["radius"]) and e["radius"] >= 0):
            x.append("radius must be a number >= 0")
        if not (_num(e.get("level")) and 0.0 < e["level"] < 1.0):
            x.append("a decision with radius needs level in (0, 1)")
    if "reasons" in e and not (isinstance(e["reasons"], list) and all(isinstance(r, str) for r in e["reasons"])):
        x.append("reasons must be a list of strings")
    if "t" in e and not _num(e["t"]):
        x.append("t must be a finite number")
    return errs + [f"line {n}: {m}" for m in x]


def td_order_errors(events: list[dict[str, Any]]) -> list[str]:
    """seq over all profiles; text / intent finals as FEP-0003; control: a moving tick is never reused."""
    errs = f3.td_final_errors([e for e in events if not _is_control(e)])
    last_seq: dict[str, int] = {}
    last_move: dict[str, int] = {}
    last_tick: dict[str, int] = {}
    for e in events:
        if e.get("type") != "trust_decision" or not isinstance(e.get("session", ""), str):
            continue
        sid, n, seq = e.get("session", ""), e.get("_line", "?"), e.get("seq")
        if _int(seq):
            if sid in last_seq and seq <= last_seq[sid]:
                errs.append(f"line {n}: seq {seq} does not increase in session {sid!r} (rule 5)")
            last_seq[sid] = max(seq, last_seq.get(sid, seq))
        if not _is_control(e) or not _int(e.get("tick")):
            continue
        tick = e["tick"]
        if sid in last_tick and tick < last_tick[sid]:
            errs.append(f"line {n}: tick {tick} goes back in session {sid!r} (rule 5)")
        last_tick[sid] = max(tick, last_tick.get(sid, tick))
        if e.get("action") == "COMMIT":
            if sid in last_move and tick <= last_move[sid]:
                errs.append(f"line {n}: a second moving decision for tick {tick} (rule 5: one input moves once)")
            last_move[sid] = tick
    return sorted(set(errs), key=errs.index)


def safety_errors(events: list[dict[str, Any]]) -> list[str]:
    errs = f3.safety_errors([e for e in events if not _is_control(e)])
    stopped: dict[str, int | None] = {}
    for e in events:
        if e.get("type") != "trust_decision":
            continue
        sid, n = e.get("session", ""), e.get("_line", "?")
        if not _is_control(e):
            if (f3._is_intent(e) and e.get("is_final") is True and e.get("action") == "COMMIT"
                    and stopped.get(sid) is not None):
                errs.append(f"line {n}: intent COMMIT while the control is stopped (rule 7)")
            continue
        vel = e.get("velocity")
        if not (isinstance(vel, list) and all(_num(v) for v in vel)):
            continue
        sp = math.sqrt(sum(float(v) ** 2 for v in vel))
        act, st, eng = e.get("action"), e.get("state"), e.get("engagement")
        reasons = e.get("reasons") if isinstance(e.get("reasons"), list) else []
        if act == "ABSTAIN" and sp != 0.0:
            errs.append(f"line {n}: a {st} decision with non-zero velocity (rule 1)")
        if act == "ABSTAIN" and _num(e.get("gain")) and e["gain"] != 0.0:
            errs.append(f"line {n}: a {st} decision with gain {e['gain']} (rule 1)")
        if act == "COMMIT":
            bad = [r for r in reasons if r in NO_MOTION_REASONS]
            if bad:
                errs.append(f"line {n}: a moving decision with the no-motion reason(s) {bad} (rule 2)")
            if _num(e.get("v_max")) and sp > e["v_max"] * (1 + SPEED_TOL) + SPEED_TOL:
                errs.append(f"line {n}: speed {sp:.6g} above v_max {e['v_max']} (rule 3)")
            if sp == 0.0:
                errs.append(f"line {n}: a COMMIT with zero velocity (use hold) (rule 1)")
            if stopped.get(sid) is not None and eng == stopped[sid]:
                errs.append(f"line {n}: motion after a stop without a new engagement (rule 5)")
            if "raw" in e and isinstance(e["raw"], list) and all(_num(v) for v in e["raw"]) and _num(e.get("gain")):
                rs = math.sqrt(sum(float(v) ** 2 for v in e["raw"]))
                if rs > 0 and e.get("authority", 1.0) == 1.0 and sp > rs * (1 + SPEED_TOL) + SPEED_TOL:
                    errs.append(f"line {n}: output faster than the decoder output at full authority (rule 6)")
        if st == "stop":
            stopped[sid] = eng if _int(eng) else -1
        elif act == "COMMIT" and _int(eng) and stopped.get(sid) is not None and eng != stopped[sid]:
            stopped[sid] = None
    return errs


def moving_ticks(decisions: list[dict[str, Any]]) -> list[int]:
    return [e["tick"] for e in decisions if _is_control(e) and e.get("is_final") is True and e.get("action") == "COMMIT"
            and _int(e.get("tick"))]


# --- checks, report, reference consumer -----------------------------------------------------


def _res(cid: str, errs: list[str] | None, msg_ok: str = "", skipped: str | None = None) -> CheckResult:
    _, kw, clause, title = _META[cid]
    if skipped is not None:
        status, msg = SKIP, skipped
    elif errs:
        status, msg = FAIL, "; ".join(errs[:6]) + (f" (+{len(errs) - 6} more)" if len(errs) > 6 else "")
    else:
        status, msg = PASS, msg_ok
    return CheckResult(cid, "core", kw, f"{FEP} {clause}", title, status, msg)


def check_events(events: list[dict[str, Any]], parse_errors: list[str] | None = None) -> list[CheckResult]:
    out = [_res("FEP5-PARSE", parse_errors or [])]
    kind = stream_kind(events)
    out.append(_res("FEP5-KIND", [] if kind != "unknown" else
                    ["line 1 is neither a header nor a trust_decision, or a decision log has other events"], kind))
    inp, dec = kind == "input", kind == "decisions"
    na_in, na_dec = (None if inp else "not an input stream"), (None if dec else "not a decision log")
    out.append(_res("FEP5-DECL", decl_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP5-CONTROL", control_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP5-ENABLE", enable_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP5-INTENT", intent_compat_errors(events) if inp else None, skipped=na_in))
    fmt = [x for e in events for x in td_control_format_errors(e)] if dec else None
    out.append(_res("FEP5-TD-FORMAT", fmt, f"{len(events)} decision(s)", skipped=na_dec))
    out.append(_res("FEP5-TD-ORDER", td_order_errors(events) if dec else None, skipped=na_dec))
    out.append(_res("FEP5-SAFETY", safety_errors(events) if dec else None, skipped=na_dec))
    return out


def check_file(path: str | PathLike[str]) -> TargetReport:
    events, perr = read_events(path)
    results = check_events(events, perr)
    kind = stream_kind(events)
    if kind == "input" and not perr:
        from fidetype.conformance import check_file as v01_check

        fails = v01_check(path).failures("core")
        results.insert(2, _res("FEP5-V01-CORE", [f"{r.check_id}: {r.message}" for r in fails], "v0.1 core passed"))
    else:
        results.insert(2, _res("FEP5-V01-CORE", None, skipped="not an input stream"))
    return TargetReport(str(path), "file", results, {"format": "jsonl", "kind": kind, "events": len(events)})


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    kind = stream_kind(events)
    if kind == "decisions":
        ai, at = f3.acted([e for e in events if not _is_control(e)])
        return {"kind": kind, "decisions": len(events), "control_decisions": sum(_is_control(e) for e in events),
                "moving_ticks": moving_ticks(events), "acted_intents": ai, "acted_texts": at}
    return {
        "kind": kind,
        "declarations": sum(1 for e in events if e["type"] == "header" and DECLARATION_KEY in e),
        "controls": sum(e["type"] == CONTROL for e in events),
        "pointers": sum(e["type"] == "pointer" for e in events),
        "enables": sum(e["type"] == CONTROL_ENABLE for e in events),
        "intents": sum(e["type"] == "intent" for e in events),
        "n_frames": sum(e["type"] == "frame" for e in events),
    }


def consume(path: str | PathLike[str]) -> dict[str, Any]:
    rep = check_file(path)
    fails = rep.failures("core")
    if fails:
        f = fails[0]
        raise StreamRejected(f"[{f.check_id}, {f.clause}] {f.message}", f.clause)
    events, _ = read_events(path)
    return summarize(events)


# --- golden vectors ---------------------------------------------------------------------------

_DROP = object()

CDECL = {"dims": 2, "quantity": "velocity", "units": "mm/s", "frame": "workspace", "rate_hz": 50.0,
         "uncertainty": "std", "axes": ["x", "y"], "max_speed": 400.0, "latency_s": 0.1, "window_s": 0.2}
IDECL = {"vocab_id": "intent.cursor-v1", "intents": [
    {"id": "intent.rest", "risk": "safe", "role": "null"},
    {"id": "intent.click", "risk": "undoable"},
    {"id": "intent.stop", "risk": "safe"},
    {"id": "intent.undo", "risk": "undoable", "role": "undo"},
]}
CTRL_VOCAB = ["control"]


def _over(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    d = dict(base)
    for k, v in over.items():
        if v is _DROP:
            d.pop(k, None)
        else:
            d[k] = v
    return d


def _ch(decl: dict[str, Any] | None = None, **over: Any) -> dict[str, Any]:
    """A control-only header (placeholder command vocab, no frames)."""
    kw: dict[str, Any] = {"vocab_type": "command", "blank_id": None, DECLARATION_KEY: CDECL if decl is None else decl}
    kw.update(over)
    vocab = kw.pop("vocab", CTRL_VOCAB)
    return _header(vocab, **kw)


def _ctl(tick: int, t: float | None = None, values: list | None = None, **kw: Any) -> dict[str, Any]:
    ev: dict[str, Any] = {"type": CONTROL, "t": round(0.02 * (tick + 1), 4) if t is None else t, "tick": tick,
                          "values": [40.0, -12.5] if values is None else values, "std": [15.0, 15.0]}
    return _over(ev, kw)


def _en(enabled: bool = True, t: float = 0.0, **kw: Any) -> dict[str, Any]:
    return _over({"type": CONTROL_ENABLE, "t": t, "enabled": enabled, "source": "switch"}, kw)


def _input(*body: dict[str, Any], header: dict[str, Any] | None = None, end: bool = True) -> Callable[[Path], None]:
    return _w_lines([header or _ch(), *body, *([{"type": "end"}] if end else [])])


def _cd(**kw: Any) -> dict[str, Any]:
    ev = {"type": "trust_decision", "profile": "control", "session": "c1", "seq": 0, "tick": 0, "t": 0.02,
          "is_final": True, "action": "COMMIT", "state": "attenuate", "velocity": [30.0, -9.0], "raw": [40.0, -12.0],
          "gain": 0.75, "units": "mm/s", "reasons": ["shrunk"], "reason": "shrunk", "p_top1": None,
          "score_semantics": "calibrated_prob", "radius": 10.0, "level": 0.9, "authority": 1.0, "engagement": 1,
          "v_max": 400.0, "ttl_s": 0.06, "config_id": "ccfg-0123456789abcdef"}
    return _over(ev, kw)


def _hold(seq: int, tick: int, reason: str = "uncertain", **kw: Any) -> dict[str, Any]:
    base = dict(seq=seq, tick=tick, action="ABSTAIN", state="hold", velocity=[0.0, 0.0], gain=0.0, reasons=[reason],
                reason=reason)
    return _cd(**{**base, **kw})


def _stop(seq: int, tick: int, **kw: Any) -> dict[str, Any]:
    base = dict(seq=seq, tick=tick, action="ABSTAIN", state="stop", velocity=[0.0, 0.0], gain=0.0, reasons=["disengaged"],
                reason="disengaged", raw=_DROP, radius=_DROP, level=_DROP)
    return _cd(**{**base, **kw})


def build_vectors() -> list[Any]:
    from fidetype.conformance.vectors import Vector

    vs: list[Vector] = []

    def add(vid: str, file: str, expect: str, clause: str, desc: str, expected: dict | None = None,
            failing: str | None = None, writer: Callable[[Path], None] | None = None) -> None:
        vs.append(Vector(vid, file, expect, f"{FEP} {clause}", desc, None, expected or {}, failing, writer))

    sq = lambda t, v: {"type": "signal_quality", "t": t, "value": v, "unit": "index"}  # noqa: E731
    # --- input streams: accept
    add("C01", "c01-velocity-stream.jsonl", "accept", "2, 3, 4",
        "2D velocity stream with std, an engage, signal quality, three ticks and a disengage",
        {"kind": "input", "declarations": 1, "controls": 3, "enables": 2},
        writer=_input(_en(True, 0.0), sq(0.01, 0.9), _ctl(0), _ctl(1, values=[55.0, -20.0]), _ctl(2, values=[0.5, 0.2]),
                      _en(False, 0.07, reason="user switch")))
    add("C02", "c02-click-intent.jsonl", "accept", "2 r4, 5 r6",
        "Velocity stream plus a click as a FEP-0003 intent (click_intent declared in intent_declaration)",
        {"kind": "input", "controls": 2, "intents": 1},
        writer=_input(_en(), _ctl(0), _ctl(1),
                      {"type": "intent", "id": "k1", "t": 0.05, "is_final": True, "score_semantics": "uncalibrated_prob",
                       "candidates": [{"intent": "intent.click", "score": 0.93}, {"intent": "intent.rest", "score": 0.05}]},
                      header=_ch({**CDECL, "click_intent": "intent.click"}, vocab=[i["id"] for i in IDECL["intents"]],
                                 intent_declaration=IDECL)))
    add("C03", "c03-human-absent-timing.jsonl", "accept", "3 r3, 3.8 v0.1",
        "A human assist event (no std), an absent axis, and v0.1 timing fields in order",
        {"kind": "input", "controls": 3},
        writer=_input(_en(), {"type": CONTROL, "t": 0.015, "tick": 0, "values": [10.0, 0.0], "source": "human"},
                      _ctl(0, absent=[False, True], values=[12.0, None]),
                      _ctl(1, t_signal_start=-0.16, t_signal_end=0.04, t_decoded=0.045, t_emitted=0.046)))
    add("C04", "c04-v01-pointer.jsonl", "accept", "3 r4",
        "v0.1 pointer events (relative, no score) on a control stream with uncertainty none",
        {"kind": "input", "pointers": 2},
        writer=_input(_en(), {"type": "pointer", "t": 0.02, "dims": 2, "mode": "relative", "values": [0.4, -0.1]},
                      {"type": "pointer", "t": 0.04, "dims": 2, "mode": "relative", "values": [0.5, -0.1]},
                      header=_ch({**CDECL, "uncertainty": "none"})))
    add("C05", "c05-screen-position.jsonl", "accept", "2 table",
        "Normalised screen position (quantity position, units norm, frame screen, no uncertainty)",
        {"kind": "input", "controls": 2},
        writer=_input(_ctl(0, values=[0.5, 0.5], std=_DROP), _ctl(1, values=[0.52, 0.49], std=_DROP),
                      header=_ch({"dims": 2, "quantity": "position", "units": "norm", "frame": "screen", "rate_hz": 60.0})))
    # --- input streams: reject
    add("C06", "c06-decl-dims.jsonl", "reject", "2 table", "dims 4", failing="FEP5-DECL",
        writer=_input(header=_ch(_over(CDECL, {"dims": 4, "axes": _DROP}))))
    add("C07", "c07-decl-units.jsonl", "reject", "2 r1", 'Velocity with position units "mm"', failing="FEP5-DECL",
        writer=_input(header=_ch({**CDECL, "units": "mm"})))
    add("C08", "c08-decl-frame.jsonl", "reject", "2 table", 'frame "world" is not defined', failing="FEP5-DECL",
        writer=_input(header=_ch({**CDECL, "frame": "world"})))
    add("C09", "c09-decl-rate.jsonl", "reject", "2 table", "rate_hz 0", failing="FEP5-DECL",
        writer=_input(header=_ch({**CDECL, "rate_hz": 0})))
    add("C10", "c10-decl-click-undeclared.jsonl", "reject", "2 r4", "click_intent without an intent_declaration",
        failing="FEP5-DECL", writer=_input(header=_ch({**CDECL, "click_intent": "intent.click"})))
    add("C11", "c11-decl-click-null.jsonl", "reject", "2 r4", "click_intent names the null (rest) intent",
        failing="FEP5-DECL", writer=_input(header=_ch({**CDECL, "click_intent": "intent.rest"},
                                                      vocab=[i["id"] for i in IDECL["intents"]], intent_declaration=IDECL)))
    add("C12", "c12-control-no-declaration.jsonl", "reject", "3 r1", "A control event in a stream without a declaration",
        failing="FEP5-CONTROL", writer=_input(_ctl(0), header=_header()))
    add("C13", "c13-control-dims.jsonl", "reject", "3 table", "values has 3 numbers on a 2-axis stream",
        failing="FEP5-CONTROL", writer=_input(_ctl(0, values=[1.0, 2.0, 3.0])))
    add("C14", "c14-control-tick-order.jsonl", "reject", "3 r2", "tick goes from 5 to 5", failing="FEP5-CONTROL",
        writer=_input(_ctl(5), _ctl(5, t=0.2)))
    add("C15", "c15-control-t-order.jsonl", "reject", "3 r2", "t goes back between two ticks", failing="FEP5-CONTROL",
        writer=_input(_ctl(0, t=0.10), _ctl(1, t=0.08)))
    add("C16", "c16-control-std-missing.jsonl", "reject", "3 r3", "uncertainty std, but a decoder event has no std",
        failing="FEP5-CONTROL", writer=_input(_ctl(0, std=_DROP)))
    add("C17", "c17-control-std-negative.jsonl", "reject", "3 table", "std -1", failing="FEP5-CONTROL",
        writer=_input(_ctl(0, std=[-1.0, 2.0])))
    add("C18", "c18-control-nan-value.jsonl", "reject", "3 table", "A value is null without absent",
        failing="FEP5-CONTROL", writer=_input(_ctl(0, values=[None, 1.0])))
    add("C19", "c19-control-timing.jsonl", "reject", "3.8 v0.1", "t_decoded before t_signal_end", failing="FEP5-CONTROL",
        writer=_input(_ctl(0, t_signal_end=0.04, t_decoded=0.03)))
    add("C20", "c20-enable-form.jsonl", "reject", "4 table", 'control_enable with enabled = "yes"', failing="FEP5-ENABLE",
        writer=_input(_en(enabled="yes")))  # type: ignore[arg-type]
    add("C21", "c21-pointer-dims.jsonl", "reject", "3 r4", "A pointer with 3 dims on a 2-axis stream",
        failing="FEP5-CONTROL", writer=_input({"type": "pointer", "t": 0.02, "dims": 3, "mode": "relative",
                                               "values": [0.1, 0.1, 0.1]}, header=_ch({**CDECL, "uncertainty": "none"})))
    add("C22", "c22-intent-unknown.jsonl", "reject", "5 r6", "A click intent event names an undeclared intent",
        failing="FEP5-INTENT", writer=_input(
            {"type": "intent", "id": "k1", "t": 0.05, "is_final": True, "score_semantics": "uncalibrated_prob",
             "candidates": [{"intent": "intent.double-click", "score": 0.9}]},
            header=_ch({**CDECL, "click_intent": "intent.click"}, vocab=[i["id"] for i in IDECL["intents"]],
                       intent_declaration=IDECL)))
    add("C23", "c23-v01-core-broken.jsonl", "reject", "Compatibility",
        "Valid FEP-0005 parts, but a frame breaks v0.1 (row does not sum to 1)", failing="FEP5-V01-CORE",
        writer=_input({**_frames(1, 1, 4)[0], "log_probs": [-1.0]}, _ctl(0)))
    # --- decision logs: accept
    add("E01", "e01-log-states.jsonl", "accept", "5, 6",
        "Control decisions: hold (not engaged), attenuate, act, hold (uncertain), stop",
        {"kind": "decisions", "control_decisions": 5, "moving_ticks": [1, 2]},
        writer=_w_lines([_hold(0, 0, "not_engaged", engagement=0, radius=_DROP, level=_DROP, score_semantics="none"),
                         _cd(seq=1, tick=1),
                         _cd(seq=2, tick=2, state="act", gain=1.0, velocity=[40.0, -12.0], reasons=["ok"], reason="ok"),
                         _hold(3, 3),
                         _stop(4, 3)]))
    add("E02", "e02-log-control-and-click.jsonl", "accept", "5 r5, 6 r7",
        "Control and intent (click) decisions in one session share seq; the click is committed while engaged",
        {"kind": "decisions", "decisions": 3, "control_decisions": 2, "moving_ticks": [0, 1], "acted_intents": ["intent.click"]},
        writer=_w_lines([_cd(seq=0, tick=0),
                         f3._td(session="c1", seq=1, unit=0, intent="intent.click", vocab_id="intent.cursor-v1"),
                         _cd(seq=2, tick=1)]))
    add("E03", "e03-log-reengage.jsonl", "accept", "6 r5",
        "Stop (engagement 1), then motion again only with engagement 2 and a hand-off ramp (authority < 1)",
        {"kind": "decisions", "moving_ticks": [0, 2]},
        writer=_w_lines([_cd(seq=0, tick=0), _stop(1, 0),
                         _hold(2, 1, "not_engaged", engagement=1, radius=_DROP, level=_DROP, score_semantics="none"),
                         _cd(seq=3, tick=2, engagement=2, authority=0.2, velocity=[6.0, -1.8], gain=0.15,
                             reasons=["shrunk", "handoff"], reason="shrunk,handoff")]))
    add("E04", "e04-log-stale-hold.jsonl", "accept", "6 r4",
        "A dead-man HOLD (stale_input) repeats the last tick with zero velocity",
        {"kind": "decisions", "moving_ticks": [7]},
        writer=_w_lines([_cd(seq=0, tick=7), _hold(1, 7, "stale_input", raw=_DROP, radius=_DROP, level=_DROP)]))
    # --- decision logs: reject
    add("E05", "e05-hold-moves.jsonl", "reject", "6 r1", "A hold decision with non-zero velocity", failing="FEP5-SAFETY",
        writer=_w_lines([_hold(0, 0, velocity=[3.0, 0.0])]))
    add("E06", "e06-over-vmax.jsonl", "reject", "6 r3", "Speed 500 above v_max 400", failing="FEP5-SAFETY",
        writer=_w_lines([_cd(velocity=[400.0, 300.0], raw=[400.0, 300.0], gain=1.0, state="act")]))
    add("E07", "e07-motion-after-stop.jsonl", "reject", "6 r5", "Motion after a stop with the same engagement",
        failing="FEP5-SAFETY", writer=_w_lines([_stop(0, 0), _cd(seq=1, tick=1)]))
    add("E08", "e08-move-on-no-signal.jsonl", "reject", "6 r2", "A COMMIT with reason no_signal", failing="FEP5-SAFETY",
        writer=_w_lines([_cd(reasons=["no_signal"], reason="no_signal")]))
    add("E09", "e09-provisional.jsonl", "reject", "5 r2", "A control decision with is_final = false",
        failing="FEP5-TD-FORMAT", writer=_w_lines([_cd(is_final=False)]))
    add("E10", "e10-state-action.jsonl", "reject", "5 r3", "state hold with action COMMIT", failing="FEP5-TD-FORMAT",
        writer=_w_lines([_cd(state="hold")]))
    add("E11", "e11-no-vmax.jsonl", "reject", "5 r4", "A control decision without v_max", failing="FEP5-TD-FORMAT",
        writer=_w_lines([_cd(v_max=_DROP)]))
    add("E12", "e12-no-ttl.jsonl", "reject", "5 r4", "A control decision without ttl_s", failing="FEP5-TD-FORMAT",
        writer=_w_lines([_cd(ttl_s=_DROP)]))
    add("E13", "e13-gain-range.jsonl", "reject", "5 table", "gain 1.5", failing="FEP5-TD-FORMAT",
        writer=_w_lines([_cd(gain=1.5)]))
    add("E14", "e14-shown.jsonl", "reject", "5 r1", "A control decision with shown (a text bridge could type it)",
        failing="FEP5-TD-FORMAT", writer=_w_lines([_cd(shown=["40,-12"])]))
    add("E15", "e15-tick-moves-twice.jsonl", "reject", "5 r5", "Two moving decisions for the same tick",
        failing="FEP5-TD-ORDER", writer=_w_lines([_cd(seq=0, tick=4), _cd(seq=1, tick=4)]))
    add("E16", "e16-seq-across-profiles.jsonl", "reject", "5 r5", "A control and an intent decision reuse seq 0",
        failing="FEP5-TD-ORDER", writer=_w_lines([_cd(seq=0), f3._td(session="c1", seq=0, unit=0, intent="intent.click")]))
    add("E17", "e17-click-while-stopped.jsonl", "reject", "6 r7", "An intent COMMIT after a control stop",
        failing="FEP5-SAFETY", writer=_w_lines([_stop(0, 0), f3._td(session="c1", seq=1, unit=0, intent="intent.click")]))
    add("E18", "e18-faster-than-raw.jsonl", "reject", "6 r6",
        "At full authority the output (60, 0) is faster than the decoder output (40, 0)", failing="FEP5-SAFETY",
        writer=_w_lines([_cd(velocity=[60.0, 0.0], raw=[40.0, 0.0], gain=1.0, state="act")]))
    add("E19", "e19-commit-zero.jsonl", "reject", "6 r1", "A COMMIT with zero velocity (a hold must say hold)",
        failing="FEP5-SAFETY", writer=_w_lines([_cd(velocity=[0.0, 0.0], gain=0.0)]))
    vs.sort(key=lambda v: v.vid)
    return vs


__all__ = ["CHECKS", "build_vectors", "check_events", "check_file", "consume", "moving_ticks", "safety_errors",
           "summarize", "td_control_format_errors", "td_order_errors"]
