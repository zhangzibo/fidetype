"""Conformance profile ``fep-0001``: streaming trust events (M4-07).

Tests the rules of ``spec/feps/0001-streaming-trust-events.md`` on JSON
Lines files of two kinds:

``input``
    A NeuralTextStream (line 1 is the ``header``). It may carry
    ``segment_end`` events, evidence fields on ``hypothesis`` items and a
    ``decode_declaration``. It must also pass the v0.1 core level.
``decisions``
    A decision log: every line is a ``trust_decision`` event (the output
    of a trust layer).

The reference consumer (:func:`consume`) returns a summary. For a decision
log the summary holds ``acted``: the texts that a bridge may act on. Only a
final ``COMMIT`` is in it (FEP-0001 section 3, rule 1: a consumer MUST NOT
act on ``is_final = false``). The golden vectors test this.

All vector content is synthetic (fixed seeds). No data from people.
"""

from __future__ import annotations

import json
import math
from os import PathLike
from pathlib import Path
from typing import Any, Callable

from fidetype.conformance.checks import FAIL, PASS, SCORE_SEMANTICS, SKIP, CheckResult
from fidetype.conformance.io import StreamRejected
from fidetype.conformance.report import TargetReport
from fidetype.conformance.vectors import Vector, _frames, _header, _w_lines
from fidetype.streams.vocab import VOCAB
from fidetype.trust.declaration import DECLARATION_KEY, validate_declaration

SUFFIXES = (".jsonl", ".ndjson")
FEP = "FEP-0001"
ACTIONS = ("COMMIT", "OFFER", "ASK", "ABSTAIN", "OFFER_WORDS")
SEGMENT_UNITS = ("utterance", "word", "trial")
#: log-probabilities may exceed 0 by this much (float rounding).
LOGP_TOL = 1e-9

#: (id, keyword, FEP clause, title)
CHECKS = [
    ("FEP1-PARSE", "MUST", "6.2 (v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"),
    ("FEP1-KIND", "MUST", "3 r4 / 6.2.1", "The file is an input stream (header first) or a decision log (only trust_decision)"),
    ("FEP1-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"),
    ("FEP1-SEGMENT", "MUST", "1 table, r5", "segment_end: t a finite number not before the last frame; unit in the enum"),
    ("FEP1-EVIDENCE", "MUST", "2 table, r1, r4", "char_confidences: one number in [0, 1] per code point; logp_* finite and <= 0"),
    ("FEP1-SCORE", "MUST", "2 r3", "Every n-best item has a finite numeric score"),
    ("FEP1-DECL", "MUST", "4 table", "decode_declaration (header or hypothesis) has the defined form"),
    ("FEP1-TD-INPUT", "MUST", "3 r4", "No trust_decision event in an input stream"),
    ("FEP1-TD-FORMAT", "MUST", "3 table, r2, r8", "trust_decision fields have the defined types and ranges"),
    ("FEP1-TD-FINAL", "MUST", "3 r5-r7", "Per session: seq increases; at most one final decision per utterance; none after it"),
]
_META = {c[0]: c for c in CHECKS}

HOW_TO_USE = ("FEP-0001 profile. For each vector, load the file with your consumer. Input streams (line 1 = header) "
              "must follow v0.1 and FEP-0001 sections 1, 2 and 4. Decision logs (only trust_decision lines) must "
              "follow section 3. A conforming consumer accepts exactly the vectors with expect = accept. For a "
              "decision log, 'acted' lists the texts a bridge may act on: only final COMMIT decisions "
              "(section 3 rule 1).")


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not a JSON value")


def read_events(path: str | PathLike[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Read the JSON Lines file. Return (events with ``_line``, parse errors)."""
    events, errs = [], []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [], [f"cannot read: {e}"]
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line, parse_constant=_reject_constant)
        except ValueError as e:
            errs.append(f"line {n}: not JSON: {e}")
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
            errs.append(f"line {n}: not an object with a string type")
            continue
        events.append({**obj, "_line": n})
    return events, errs


def stream_kind(events: list[dict[str, Any]]) -> str:
    """``input``, ``decisions`` or ``unknown``."""
    if not events:
        return "unknown"
    if events[0]["type"] == "header":
        return "input"
    if all(e["type"] == "trust_decision" for e in events):
        return "decisions"
    return "unknown"


# --- rule functions: each returns a list of error strings ------------------------------


def segment_errors(events: list[dict[str, Any]]) -> list[str]:
    errs = []
    last_frame_t = -math.inf
    for e in events:
        if e["type"] == "header":
            last_frame_t = -math.inf
        elif e["type"] == "frame" and _num(e.get("t")):
            last_frame_t = float(e["t"])
        elif e["type"] == "segment_end":
            n = e["_line"]
            if "t" in e:
                if not _num(e["t"]):
                    errs.append(f"line {n}: segment_end t must be a finite number")
                elif e["t"] < last_frame_t:
                    errs.append(f"line {n}: segment_end t {e['t']} is before the last frame t {last_frame_t} (rule 5)")
            if "unit" in e and e["unit"] not in SEGMENT_UNITS:
                errs.append(f"line {n}: segment_end unit {e['unit']!r} is not one of {list(SEGMENT_UNITS)}")
    return errs


def _items(events: list[dict[str, Any]]):
    for e in events:
        if e["type"] == "hypothesis" and isinstance(e.get("nbest"), list):
            for k, it in enumerate(e["nbest"]):
                if isinstance(it, dict):
                    yield e["_line"], k, it


def evidence_errors(events: list[dict[str, Any]]) -> list[str]:
    errs = []
    for n, k, it in _items(events):
        where = f"line {n} nbest[{k}]"
        if "char_confidences" in it:
            cc, text = it["char_confidences"], it.get("text")
            if not isinstance(cc, list):
                errs.append(f"{where}: char_confidences must be a list")
            else:
                if isinstance(text, str) and len(cc) != len(text):
                    errs.append(f"{where}: char_confidences has {len(cc)} values, text has {len(text)} code points (rule 1)")
                if any(not _num(c) or not 0.0 <= c <= 1.0 for c in cc):
                    errs.append(f"{where}: char_confidences values must be numbers in [0, 1]")
        for key in ("logp_acoustic", "logp_lm"):
            if key in it:
                v = it[key]
                if not _num(v):
                    errs.append(f"{where}: {key} must be a finite number")
                elif v > LOGP_TOL:
                    errs.append(f"{where}: {key} {v} is a log-probability and must be <= 0 (rule 4)")
    return errs


def score_errors(events: list[dict[str, Any]]) -> list[str]:
    return [f"line {n} nbest[{k}]: score must be a finite number (rule 3)"
            for n, k, it in _items(events) if not _num(it.get("score"))]


def declaration_errors(events: list[dict[str, Any]]) -> list[str]:
    errs = []
    for e in events:
        if e["type"] in ("header", "hypothesis") and DECLARATION_KEY in e:
            errs += [f"line {e['_line']}: {x}" for x in validate_declaration(e[DECLARATION_KEY])]
    return errs


def td_input_errors(events: list[dict[str, Any]]) -> list[str]:
    return [f"line {e['_line']}: trust_decision in an input stream" for e in events if e["type"] == "trust_decision"]


def td_format_errors(e: dict[str, Any]) -> list[str]:
    """The format errors of one ``trust_decision`` event."""
    n = e.get("_line", "?")
    errs = []
    if not isinstance(e.get("is_final"), bool):
        errs.append("is_final must be a boolean")
    if e.get("action") not in ACTIONS:
        errs.append(f"action {e.get('action')!r} is not one of {list(ACTIONS)}")
    if "p_top1" not in e:
        errs.append("p_top1 is required (number or null)")
    elif e["p_top1"] is not None and not (_num(e["p_top1"]) and 0.0 <= e["p_top1"] <= 1.0):
        errs.append(f"p_top1 {e['p_top1']!r} must be a number in [0, 1] or null")
    sem = e.get("score_semantics")
    if sem is None:
        errs.append("score_semantics is required")
    elif sem not in SCORE_SEMANTICS:
        errs.append(f"score_semantics {sem!r} is not one of {list(SCORE_SEMANTICS)}")
    if "shown" in e:
        sh = e["shown"]
        if not isinstance(sh, list) or not all(isinstance(x, str) for x in sh):
            errs.append("shown must be a list of strings")
        elif e.get("action") == "COMMIT" and not sh:
            errs.append("a COMMIT with shown needs at least one text (rule 8)")
    if "set_size" in e and not (_int(e["set_size"]) and e["set_size"] >= 0):
        errs.append("set_size must be an integer >= 0")
    if "guard_risk" in e and e["guard_risk"] is not None and not (_num(e["guard_risk"]) and 0.0 <= e["guard_risk"] <= 1.0):
        errs.append("guard_risk must be a number in [0, 1] or null")
    if "session" in e and not isinstance(e["session"], str):
        errs.append("session must be a string")
    for k in ("seq", "utterance"):
        if k in e and not (_int(e[k]) and e[k] >= 0):
            errs.append(f"{k} must be an integer >= 0")
    if "config_id" in e and e["config_id"] is not None and not isinstance(e["config_id"], str):
        errs.append("config_id must be a string")
    if "input" in e and not isinstance(e["input"], dict):
        errs.append("input must be an object")
    if "latency_s" in e and not (_num(e["latency_s"]) and e["latency_s"] >= 0):
        errs.append("latency_s must be a number >= 0")
    return [f"line {n}: {x}" for x in errs]


def td_final_errors(events: list[dict[str, Any]]) -> list[str]:
    """is_final semantics per session (rules 5-7)."""
    errs = []
    last_seq: dict[str, int] = {}
    last_utt: dict[str, int] = {}
    finals: set[tuple[str, int]] = set()
    for e in events:
        if e.get("type") != "trust_decision":
            continue
        n, sid = e.get("_line", "?"), e.get("session", "")
        if not isinstance(sid, str):
            continue
        seq, utt = e.get("seq"), e.get("utterance")
        if _int(seq):
            if sid in last_seq and seq <= last_seq[sid]:
                errs.append(f"line {n}: seq {seq} does not increase in session {sid!r} (rule 5)")
            last_seq[sid] = max(seq, last_seq.get(sid, seq))
        if _int(utt):
            if sid in last_utt and utt < last_utt[sid]:
                errs.append(f"line {n}: utterance {utt} goes back in session {sid!r} (rule 5)")
            last_utt[sid] = max(utt, last_utt.get(sid, utt))
            if (sid, utt) in finals:
                kind = "a second final decision" if e.get("is_final") is True else "a decision"
                errs.append(f"line {n}: {kind} for utterance {utt} of session {sid!r} after its final one (rules 6-7)")
            if e.get("is_final") is True:
                finals.add((sid, utt))
    return errs


def acted_texts(decisions: list[dict[str, Any]]) -> list[str | None]:
    """The texts a bridge may act on: ``shown[0]`` of each final COMMIT (None if text is omitted)."""
    out: list[str | None] = []
    for e in decisions:
        if e.get("type") == "trust_decision" and e.get("is_final") is True and e.get("action") == "COMMIT":
            sh = e.get("shown")
            out.append(sh[0] if isinstance(sh, list) and sh else None)
    return out


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
    """Run the profile checks on parsed events (without the v0.1 check)."""
    out = [_res("FEP1-PARSE", parse_errors or [])]
    kind = stream_kind(events)
    out.append(_res("FEP1-KIND", [] if kind != "unknown" else
                    ["line 1 is neither a header nor a trust_decision, or a decision log has other events"], kind))
    inp, dec = kind == "input", kind == "decisions"
    na_in, na_dec = (None if inp else "not an input stream"), (None if dec else "not a decision log")
    out.append(_res("FEP1-SEGMENT", segment_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP1-EVIDENCE", evidence_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP1-SCORE", score_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP1-DECL", declaration_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP1-TD-INPUT", td_input_errors(events) if inp else None, skipped=na_in))
    fmt = [x for e in events for x in td_format_errors(e)] if dec else None
    out.append(_res("FEP1-TD-FORMAT", fmt, f"{len(events)} decision(s)", skipped=na_dec))
    out.append(_res("FEP1-TD-FINAL", td_final_errors(events) if dec else None, skipped=na_dec))
    return out


def check_file(path: str | PathLike[str]) -> TargetReport:
    """Producer check of one JSON Lines file under the profile."""
    events, perr = read_events(path)
    results = check_events(events, perr)
    kind = stream_kind(events)
    if kind == "input" and not perr:
        from fidetype.conformance import check_file as v01_check

        rep = v01_check(path)
        fails = rep.failures("core")
        results.insert(2, _res("FEP1-V01-CORE", [f"{r.check_id}: {r.message}" for r in fails], "v0.1 core passed"))
    else:
        results.insert(2, _res("FEP1-V01-CORE", None, skipped="not an input stream"))
    return TargetReport(str(path), "file", results, {"format": "jsonl", "kind": kind, "events": len(events)})


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    kind = stream_kind(events)
    if kind == "decisions":
        return {"kind": kind, "decisions": len(events), "final": sum(e.get("is_final") is True for e in events),
                "acted": acted_texts(events)}
    segs, has_input, ends = 0, False, 0
    for e in events:
        t = e["type"]
        if t in ("frame", "hypothesis"):
            has_input = True
        elif t in ("segment_end", "end", "header"):
            if has_input:
                segs += 1
            has_input = False
            ends += t == "segment_end"
    segs += has_input
    return {
        "kind": kind,
        "n_frames": sum(e["type"] == "frame" for e in events),
        "segments": segs,
        "segment_ends": ends,
        "hypotheses": sum(e["type"] == "hypothesis" for e in events),
        "evidence_items": sum(1 for _, _, it in _items(events)
                              if any(k in it for k in ("char_confidences", "logp_acoustic", "logp_lm"))),
        "declarations": sum(1 for e in events if e["type"] in ("header", "hypothesis") and DECLARATION_KEY in e),
    }


def consume(path: str | PathLike[str]) -> dict[str, Any]:
    """Reference consumer of the profile: return a summary, or raise :class:`StreamRejected`."""
    rep = check_file(path)
    fails = rep.failures("core")
    if fails:
        f = fails[0]
        raise StreamRejected(f"[{f.check_id}, {f.clause}] {f.message}", f.clause)
    events, _ = read_events(path)
    return summarize(events)


# --- golden vectors ---------------------------------------------------------------------------


def _td(**kw: Any) -> dict[str, Any]:
    ev = {"type": "trust_decision", "session": "u1", "seq": 0, "utterance": 0, "is_final": True, "action": "COMMIT",
          "shown": ["ab"], "p_top1": 0.93, "score_semantics": "calibrated_prob", "set_size": 1, "guard_risk": 0.12,
          "config_id": "tcfg-0123456789abcdef"}
    for k, v in kw.items():
        if v is _DROP:
            ev.pop(k, None)
        else:
            ev[k] = v
    return ev


_DROP = object()
DECL = {"decoder": "conformance-beam", "decoder_version": "1.0", "frame_temperature": 1.25,
        "params": {"beam": 8, "lm_weight": 0.5}, "config_id": "tcfg-0123456789abcdef"}


def _hyp(hid: str = "h1", final: bool = True, items: list[dict[str, Any]] | None = None, **kw: Any) -> dict[str, Any]:
    ev = {"type": "hypothesis", "id": hid, "is_final": final, "score_semantics": "none",
          "nbest": items if items is not None else [{"text": "ab", "score": -1.0}]}
    ev.update(kw)
    return ev


def _item(**kw: Any) -> dict[str, Any]:
    it: dict[str, Any] = {"text": "ab", "score": -1.0}
    it.update(kw)
    return it


def _input(*body: dict[str, Any], header: dict[str, Any] | None = None, end: bool = True) -> Callable[[Path], None]:
    return _w_lines([header or _header(), *body, *([{"type": "end"}] if end else [])])


def _shift(frames: list[dict[str, Any]], dt: float) -> list[dict[str, Any]]:
    return [{**f, "t": round(f["t"] + dt, 6)} for f in frames]


def build_vectors() -> list[Vector]:
    V = len(VOCAB)
    vs: list[Vector] = []

    def add(vid: str, file: str, expect: str, clause: str, desc: str, expected: dict | None = None,
            failing: str | None = None, writer: Callable[[Path], None] | None = None) -> None:
        vs.append(Vector(vid, file, expect, f"{FEP} {clause}", desc, None, expected or {}, failing, writer))

    f2a, f2b = _frames(2, V, 1), _shift(_frames(2, V, 2), 1.0)
    # --- section 1: segment_end
    add("F01", "f01-segments.jsonl", "accept", "1", "Two utterances of frames, each closed by segment_end (t, unit)",
        {"kind": "input", "n_frames": 4, "segments": 2, "segment_ends": 2},
        writer=_input(*f2a, {"type": "segment_end", "t": 0.1, "unit": "utterance"}, *f2b,
                      {"type": "segment_end", "t": 1.1, "unit": "utterance"}))
    add("F02", "f02-segment-minimal.jsonl", "accept", "1", "segment_end with no t and no unit; end closes the last segment",
        {"kind": "input", "segments": 2, "segment_ends": 1},
        writer=_input(*f2a, {"type": "segment_end"}, *f2b))
    add("F03", "f03-empty-segment.jsonl", "accept", "1 r4", "A segment_end right after the header: an empty segment, no input",
        {"kind": "input", "segments": 1, "segment_ends": 2},
        writer=_input({"type": "segment_end"}, *f2a, {"type": "segment_end", "unit": "trial"}))
    add("F04", "f04-segment-bad-unit.jsonl", "reject", "1 table", 'segment_end unit "sentence" is not in the enum',
        failing="FEP1-SEGMENT", writer=_input(*f2a, {"type": "segment_end", "unit": "sentence"}))
    add("F05", "f05-segment-t-string.jsonl", "reject", "1 table", "segment_end t is a string",
        failing="FEP1-SEGMENT", writer=_input(*f2a, {"type": "segment_end", "t": "0.1"}))
    add("F06", "f06-segment-before-frame.jsonl", "reject", "1 r5", "segment_end t is before the last frame of its segment",
        failing="FEP1-SEGMENT", writer=_input(*f2a, {"type": "segment_end", "t": 0.01}))
    # --- section 2: evidence fields, score
    ex1 = _hyp("h1", False, [_item(score=-1.2, char_confidences=[0.91, 0.40])])
    ex2 = _hyp("h2", True, [_item(char_confidences=[0.93, 0.88], logp_acoustic=-2.1, logp_lm=-3.0),
                            {"text": "a", "score": -2.4}], revision_of="h1")
    add("F07", "f07-evidence-valid.jsonl", "accept", "2", "The FEP example: partial and final hypotheses with evidence fields",
        {"kind": "input", "hypotheses": 2, "evidence_items": 2, "segments": 1},
        writer=_input(ex1, ex2, {"type": "segment_end", "t": 1.2}))
    add("F08", "f08-evidence-code-points.jsonl", "accept", "2 r1",
        "char_confidences counts Unicode code points: 'a\U0001F600' has 2 (UTF-16 would give 3)",
        {"kind": "input", "evidence_items": 1},
        writer=_input(_hyp(items=[_item(text="a\U0001F600", char_confidences=[0.9, 0.5])])))
    add("F09", "f09-evidence-length.jsonl", "reject", "2 r1", "char_confidences has 3 values for a 2-character text",
        failing="FEP1-EVIDENCE", writer=_input(_hyp(items=[_item(char_confidences=[0.9, 0.8, 0.7])])))
    add("F10", "f10-evidence-range.jsonl", "reject", "2 table", "A char_confidences value is 1.2",
        failing="FEP1-EVIDENCE", writer=_input(_hyp(items=[_item(char_confidences=[0.9, 1.2])])))
    add("F11", "f11-evidence-bool.jsonl", "reject", "2 table", "A char_confidences value is a boolean",
        failing="FEP1-EVIDENCE", writer=_input(_hyp(items=[_item(char_confidences=[True, 0.5])])))
    add("F12", "f12-logp-positive.jsonl", "reject", "2 r4", "logp_acoustic is +0.5 (a log-probability is <= 0)",
        failing="FEP1-EVIDENCE", writer=_input(_hyp(items=[_item(logp_acoustic=0.5)])))
    add("F13", "f13-logp-string.jsonl", "reject", "2 table", "logp_lm is a string",
        failing="FEP1-EVIDENCE", writer=_input(_hyp(items=[_item(logp_lm="-3.0")])))
    add("F14", "f14-score-null.jsonl", "reject", "2 r3", "An n-best item for a trust layer has score null",
        failing="FEP1-SCORE", writer=_input(_hyp(items=[_item(), {"text": "a", "score": None}])))
    # --- section 4: decode declaration
    add("F15", "f15-declaration-header.jsonl", "accept", "4", "decode_declaration in the header, all fields",
        {"kind": "input", "declarations": 1, "hypotheses": 1},
        writer=_input(_hyp(), header=_header(**{DECLARATION_KEY: DECL})))
    add("F16", "f16-declaration-override.jsonl", "accept", "4 r2",
        "A hypothesis declaration (decoder only) replaces the header declaration for that event",
        {"kind": "input", "declarations": 2, "hypotheses": 2},
        writer=_input(_hyp("h1", True), {"type": "segment_end"},
                      _hyp("h2", True, **{DECLARATION_KEY: {"decoder": "other-decoder"}}),
                      header=_header(**{DECLARATION_KEY: DECL})))
    add("F17", "f17-declaration-temperature-zero.jsonl", "reject", "4 table", "frame_temperature is 0",
        failing="FEP1-DECL", writer=_input(_hyp(), header=_header(**{DECLARATION_KEY: {**DECL, "frame_temperature": 0}})))
    add("F18", "f18-declaration-no-decoder.jsonl", "reject", "4 table", "decode_declaration without decoder",
        failing="FEP1-DECL",
        writer=_input(_hyp(**{DECLARATION_KEY: {"frame_temperature": 1.0, "config_id": "tcfg-0123456789abcdef"}})))
    add("F19", "f19-declaration-not-object.jsonl", "reject", "4 table", "decode_declaration is a string",
        failing="FEP1-DECL", writer=_input(_hyp(), header=_header(**{DECLARATION_KEY: "conformance-beam"})))
    add("F20", "f20-declaration-params-list.jsonl", "reject", "4 table", "decode_declaration params is a list",
        failing="FEP1-DECL", writer=_input(_hyp(**{DECLARATION_KEY: {"decoder": "x", "params": [8, 0.5]}})))
    # --- section 3: trust_decision
    add("F21", "f21-decision-in-input.jsonl", "reject", "3 r4", "A trust_decision event inside a decoder input stream",
        failing="FEP1-TD-INPUT", writer=_input(*f2a, _td()))
    add("F22", "f22-log-preview-then-commit.jsonl", "accept", "3 r1",
        "Provisional OFFER, then final COMMIT: act on the final COMMIT only",
        {"kind": "decisions", "decisions": 2, "final": 1, "acted": ["ab"]},
        writer=_w_lines([_td(seq=0, is_final=False, action="OFFER", p_top1=0.71, guard_risk=0.5),
                         _td(seq=1, input={"kind": "hypothesis", "hypothesis_id": "h2", "revision_of": "h1"})]))
    add("F23", "f23-log-provisional-commit.jsonl", "accept", "3 r1",
        "A provisional COMMIT, then a final ABSTAIN: a consumer MUST NOT act (acted is empty)",
        {"kind": "decisions", "decisions": 2, "final": 1, "acted": []},
        writer=_w_lines([_td(seq=0, is_final=False, shown=["ab"]),
                         _td(seq=1, action="ABSTAIN", shown=[], p_top1=0.2, guard_risk=0.9)]))
    add("F24", "f24-log-privacy.jsonl", "accept", "3 table",
        "Final OFFER and final COMMIT without shown (privacy log), p_top1 null on the OFFER",
        {"kind": "decisions", "final": 2, "acted": [None]},
        writer=_w_lines([_td(seq=0, action="OFFER", shown=_DROP, p_top1=None),
                         _td(seq=1, utterance=1, shown=_DROP)]))
    add("F25", "f25-log-two-sessions.jsonl", "accept", "3 r5",
        "Two interleaved sessions, each with its own seq and utterance counts, plus extension keys",
        {"kind": "decisions", "decisions": 4, "final": 2, "acted": ["cd", "ab"]},
        writer=_w_lines([_td(session="u1", seq=0, is_final=False, action="OFFER"),
                         _td(session="u2", seq=0, is_final=False, action="OFFER", shown=["cd"]),
                         _td(session="u2", seq=1, shown=["cd"], reason="p_top1 0.93 >= 0.90", attempt=0,
                             final_attempt=True, latency_s=0.0004, acme_extra={"x": 1}),
                         _td(session="u1", seq=1)]))
    add("F26", "f26-log-ask-then-retry.jsonl", "accept", "3 r6",
        "Final ASK on utterance 0, then a final COMMIT on utterance 1 of the same session",
        {"kind": "decisions", "final": 2, "acted": ["ab"]},
        writer=_w_lines([_td(seq=0, action="ASK", shown=["ab", "abc"], set_size=2),
                         _td(seq=1, utterance=1)]))
    add("F27", "f27-td-no-is-final.jsonl", "reject", "3 table", "trust_decision without is_final",
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(is_final=_DROP)]))
    add("F28", "f28-td-is-final-string.jsonl", "reject", "3 table", 'is_final is the string "false"',
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(is_final="false")]))
    add("F29", "f29-td-bad-action.jsonl", "reject", "3 table", 'action "MAYBE" is not in the enum',
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(action="MAYBE")]))
    add("F30", "f30-td-p-top1-range.jsonl", "reject", "3 r2", "p_top1 1.3 with calibrated_prob",
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(p_top1=1.3)]))
    add("F31", "f31-td-no-semantics.jsonl", "reject", "3 table", "trust_decision without score_semantics",
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(score_semantics=_DROP)]))
    add("F32", "f32-td-bad-semantics.jsonl", "reject", "3 table", 'score_semantics "probability" is not in the 3.5 enum',
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(score_semantics="probability")]))
    add("F33", "f33-td-guard-risk.jsonl", "reject", "3 table", "guard_risk 1.5",
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(guard_risk=1.5)]))
    add("F34", "f34-td-set-size.jsonl", "reject", "3 table", "set_size 1.5",
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(set_size=1.5)]))
    add("F35", "f35-td-commit-empty-shown.jsonl", "reject", "3 r8", "A final COMMIT with an empty shown list",
        failing="FEP1-TD-FORMAT", writer=_w_lines([_td(shown=[])]))
    add("F36", "f36-td-two-finals.jsonl", "reject", "3 r6", "Two final decisions for the same utterance",
        failing="FEP1-TD-FINAL", writer=_w_lines([_td(seq=0), _td(seq=1, action="OFFER")]))
    add("F37", "f37-td-after-final.jsonl", "reject", "3 r7", "A provisional decision after the final one of its utterance",
        failing="FEP1-TD-FINAL", writer=_w_lines([_td(seq=0), _td(seq=1, is_final=False, action="OFFER")]))
    add("F38", "f38-td-seq-back.jsonl", "reject", "3 r5", "seq does not increase within a session",
        failing="FEP1-TD-FINAL", writer=_w_lines([_td(seq=3, is_final=False, action="OFFER"), _td(seq=2)]))
    add("F39", "f39-log-mixed.jsonl", "reject", "3 r4 / 6.2.1", "A file without a header that mixes trust_decision and frame lines",
        failing="FEP1-KIND", writer=_w_lines([_td(), *f2a]))
    add("F40", "f40-v01-core-broken.jsonl", "reject", "Compatibility",
        "Valid FEP-0001 parts, but a frame breaks v0.1 (row does not sum to 1)", failing="FEP1-V01-CORE",
        writer=_input({**f2a[0], "log_probs": [0.0] * V}, {"type": "segment_end"}))
    vs.sort(key=lambda v: v.vid)
    return vs


__all__ = ["ACTIONS", "CHECKS", "acted_texts", "build_vectors", "check_events", "check_file", "consume",
           "read_events", "stream_kind", "summarize", "td_final_errors", "td_format_errors"]
