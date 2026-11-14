"""Conformance profile ``fep-0003``: output profiles and discrete intent events (P12-01 / P12-02).

Tests the rules of ``spec/feps/0003-intent-events.md`` on JSON Lines files
of two kinds:

``input``
    A NeuralTextStream (line 1 is the ``header``) that may carry an
    ``intent_declaration``, ``intent`` and ``intent_feedback`` events,
    next to text events. It must also pass the v0.1 core level.
``decisions``
    A decision log (only ``trust_decision`` lines). Intent decisions have
    ``profile = "intent"``; text decisions (no ``profile``, or ``"text"``)
    follow FEP-0001 and may share the log.

The reference consumer (:func:`consume`) returns a summary. For a
decision log it holds ``acted_intents`` (the intents a bridge may
actuate: final intent COMMITs only) and ``acted_texts`` (FEP-0001).

All vector content is synthetic. No data from people.
"""

from __future__ import annotations

import math
from os import PathLike
from pathlib import Path
from typing import Any, Callable

from fidetype.conformance.checks import FAIL, PASS, SKIP, CheckResult
from fidetype.conformance.io import StreamRejected
from fidetype.conformance.profiles.fep0001 import read_events, stream_kind, td_format_errors
from fidetype.conformance.report import TargetReport
from fidetype.conformance.vectors import Vector, _frames, _header, _w_lines
from fidetype.streams.vocab import VOCAB
from fidetype.trust.intent import (
    DECLARATION_KEY,
    PROFILE,
    RISK_CLASSES,
    ROLES,
    IntentVocabulary,
    validate_feedback_event,
    validate_intent_declaration,
    validate_intent_event,
)

SUFFIXES = (".jsonl", ".ndjson")
FEP = "FEP-0003"
INTENT_ACTIONS = ("COMMIT", "OFFER", "ABSTAIN")
PROFILES = ("text", "intent")

#: (id, keyword, FEP clause, title)
CHECKS = [
    ("FEP3-PARSE", "MUST", "1 (6.2 v0.1)", "Every line is a JSON object with a string type (no NaN tokens)"),
    ("FEP3-KIND", "MUST", "1", "The file is an input stream (header first) or a decision log (only trust_decision)"),
    ("FEP3-V01-CORE", "MUST", "Compatibility", "An input stream passes the v0.1 core level"),
    ("FEP3-DECL", "MUST", "2 table, r1-r4", "intent_declaration has the defined form"),
    ("FEP3-VOCAB", "MUST", "2 r5", "On a command-vocabulary stream with a declaration, vocab (without blank) equals the declared intents"),
    ("FEP3-INTENT", "MUST", "3 table, r1-r5", "intent events: declared, unique candidates; scores fit their semantics; ranked"),
    ("FEP3-FEEDBACK", "MUST", "4 table", "intent_feedback events have the defined form"),
    ("FEP3-TD-FORMAT", "MUST", "5 table, r1-r3", "Intent trust_decision fields (profile, unit, intent, offered, risk_class, no shown)"),
    ("FEP3-TD-FINAL", "MUST", "5 r4, 7 r2", "Per session: seq increases over both profiles; one final decision per intent unit; none after it"),
    ("FEP3-SAFETY", "MUST", "6 r1-r6", "No null COMMIT; COMMIT p >= threshold; irreversible COMMIT confirmed; valid undo"),
]
_META = {c[0]: c for c in CHECKS}

HOW_TO_USE = ("FEP-0003 profile. For each vector, load the file with your consumer. Input streams (line 1 = header) "
              "must follow v0.1 and FEP-0003 sections 2-4. Decision logs (only trust_decision lines) must follow "
              "sections 5-7; text decisions in the same log follow FEP-0001. A conforming consumer accepts exactly the "
              "vectors with expect = accept. For a decision log, 'acted_intents' lists the intents a bridge may "
              "actuate (final intent COMMITs only) and 'acted_texts' the FEP-0001 texts.")


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_intent(e: dict[str, Any]) -> bool:
    return e.get("type") == "trust_decision" and e.get("profile") == PROFILE


# --- input rules ---------------------------------------------------------------------------


def _declarations(events: list[dict[str, Any]]):
    """Yield (header event, IntentVocabulary or None, errors) per header."""
    for e in events:
        if e["type"] == "header":
            if DECLARATION_KEY not in e:
                yield e, None, []
                continue
            errs = validate_intent_declaration(e[DECLARATION_KEY])
            yield e, (None if errs else IntentVocabulary.from_declaration(e[DECLARATION_KEY])), errs


def decl_errors(events: list[dict[str, Any]]) -> list[str]:
    return [f"line {h['_line']}: {x}" for h, _v, errs in _declarations(events) for x in errs]


def vocab_errors(events: list[dict[str, Any]]) -> list[str]:
    out = []
    for h, v, _ in _declarations(events):
        if v is None or h.get("vocab_type") != "command":
            continue
        vocab, b = h.get("vocab") or [], h.get("blank_id")
        toks = {t for j, t in enumerate(vocab) if j != b}
        if toks != set(v.ids):
            out.append(f"line {h['_line']}: command vocab without blank {sorted(toks)} != declared intents {sorted(v.ids)} (rule 5)")
    return out


def intent_errors(events: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    vocab: IntentVocabulary | None = None
    has_decl = False
    ids: set[str] = set()
    for e in events:
        if e["type"] == "header":
            has_decl = DECLARATION_KEY in e
            vocab = None
            if has_decl and not validate_intent_declaration(e[DECLARATION_KEY]):
                vocab = IntentVocabulary.from_declaration(e[DECLARATION_KEY])
            ids = set()
        elif e["type"] == "intent":
            n = e["_line"]
            if not has_decl:
                out.append(f"line {n}: intent event without an intent_declaration in the header (rule 1)")
                continue
            if vocab is None:
                continue  # FEP3-DECL reports it
            out += [f"line {n}: {x}" for x in validate_intent_event(e, vocab)]
            if isinstance(e.get("id"), str):
                if e["id"] in ids:
                    out.append(f"line {n}: intent id {e['id']!r} is not unique in the stream")
                ids.add(e["id"])
    return out


def feedback_errors(events: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    vocab: IntentVocabulary | None = None
    for e in events:
        if e["type"] == "header":
            d = e.get(DECLARATION_KEY)
            vocab = IntentVocabulary.from_declaration(d) if d is not None and not validate_intent_declaration(d) else None
        elif e["type"] == "intent_feedback":
            out += [f"line {e['_line']}: {x}" for x in validate_feedback_event(e, vocab)]
    return out


# --- decision-log rules ----------------------------------------------------------------------


def td_intent_format_errors(e: dict[str, Any]) -> list[str]:
    """Format errors of one ``trust_decision`` (FEP-0001 table for all; section 5 for intent decisions)."""
    errs = list(td_format_errors(e))
    n = e.get("_line", "?")
    prof = e.get("profile", "text")
    if prof not in PROFILES:
        return errs + [f"line {n}: profile {prof!r} is not one of {list(PROFILES)}"]
    if prof != PROFILE:
        return errs
    x: list[str] = []
    if "shown" in e:
        x.append("an intent decision MUST NOT carry shown (rule 2)")
    if "utterance" in e:
        x.append("an intent decision uses unit, not utterance (rule 1)")
    if not (_int(e.get("unit")) and e["unit"] >= 0):
        x.append("unit must be an integer >= 0")
    if e.get("action") not in INTENT_ACTIONS:
        x.append(f"intent action {e.get('action')!r} is not one of {list(INTENT_ACTIONS)}")
    if e.get("action") == "COMMIT" and not isinstance(e.get("intent"), str):
        x.append("a COMMIT needs the committed intent (rule 3)")
    if "intent" in e and not isinstance(e["intent"], str):
        x.append("intent must be a string")
    if "offered" in e and not (isinstance(e["offered"], list) and all(isinstance(i, str) for i in e["offered"])):
        x.append("offered must be a list of strings")
    if e.get("action") == "OFFER" and not (isinstance(e.get("offered"), list) and e["offered"]):
        x.append("an OFFER needs a non-empty offered list (rule 3)")
    if "risk_class" in e and e["risk_class"] is not None and e["risk_class"] not in RISK_CLASSES:
        x.append(f"risk_class {e['risk_class']!r} is not one of {list(RISK_CLASSES)}")
    if e.get("action") == "COMMIT" and e.get("risk_class") not in RISK_CLASSES:
        x.append("a COMMIT needs risk_class (rule 3)")
    if "role" in e and e["role"] is not None and e["role"] not in ROLES:
        x.append(f"role {e['role']!r} is not one of {list(ROLES)}")
    if "threshold" in e and e["threshold"] is not None and not (_num(e["threshold"]) and 0.0 <= e["threshold"] <= 1.0):
        x.append("threshold must be a number in [0, 1] or null")
    if "confirm_required" in e and not isinstance(e["confirm_required"], bool):
        x.append("confirm_required must be a boolean")
    if e.get("confirm_required") is True and e.get("action") != "OFFER":
        x.append("confirm_required is only allowed on an OFFER")
    for k in ("confirmation_of", "undo_of"):
        if k in e and not (_int(e[k]) and e[k] >= 0):
            x.append(f"{k} must be an integer >= 0")
    if "confirmed_via" in e and e["confirmed_via"] not in ("intent", "feedback"):
        x.append("confirmed_via must be 'intent' or 'feedback'")
    return errs + [f"line {n}: {m}" for m in x]


def td_final_errors(events: list[dict[str, Any]]) -> list[str]:
    """seq per session over both profiles; FEP-0001 rules 6-7 per text utterance and per intent unit."""
    errs = []
    last_seq: dict[str, int] = {}
    last: dict[tuple[str, str], int] = {}
    finals: set[tuple[str, str, int]] = set()
    for e in events:
        if e.get("type") != "trust_decision":
            continue
        n, sid = e.get("_line", "?"), e.get("session", "")
        if not isinstance(sid, str):
            continue
        seq = e.get("seq")
        if _int(seq):
            if sid in last_seq and seq <= last_seq[sid]:
                errs.append(f"line {n}: seq {seq} does not increase in session {sid!r} (section 7 rule 2)")
            last_seq[sid] = max(seq, last_seq.get(sid, seq))
        intent = _is_intent(e)
        key, val = ("unit", e.get("unit")) if intent else ("utterance", e.get("utterance"))
        if not _int(val):
            continue
        pk = (sid, key)
        if pk in last and val < last[pk]:
            errs.append(f"line {n}: {key} {val} goes back in session {sid!r}")
        last[pk] = max(val, last.get(pk, val))
        if (sid, key, val) in finals:
            kind = "a second final decision" if e.get("is_final") is True else "a decision"
            errs.append(f"line {n}: {kind} for {key} {val} of session {sid!r} after its final one (rule 4)")
        if e.get("is_final") is True:
            finals.add((sid, key, val))
    return errs


def safety_errors(events: list[dict[str, Any]]) -> list[str]:
    """Section 6: null, threshold, confirmation and undo rules on final intent decisions."""
    errs = []
    offers: dict[tuple[str, int], list[str]] = {}
    used: set[tuple[str, int]] = set()
    commits: dict[tuple[str, int], str] = {}
    for e in events:
        if not _is_intent(e) or e.get("is_final") is not True:
            continue
        n, sid, unit = e.get("_line", "?"), e.get("session", ""), e.get("unit")
        act = e.get("action")
        if act == "OFFER" and isinstance(e.get("offered"), list):
            offers[(sid, unit)] = list(e["offered"])
        if act != "COMMIT":
            continue
        if e.get("role") == "null":
            errs.append(f"line {n}: COMMIT of a null intent (rule 1)")
        p, thr = e.get("p_top1"), e.get("threshold")
        if e.get("confirmed_via") != "feedback" and _num(p) and _num(thr) and p < thr - 1e-12:
            errs.append(f"line {n}: COMMIT with p_top1 {p} below its threshold {thr} (rule 3)")
        sem = (e.get("input") or {}).get("score_semantics") if isinstance(e.get("input"), dict) else None
        if sem in ("none", "power", "strength") and e.get("confirmed_via") != "feedback":
            errs.append(f"line {n}: COMMIT on input with score_semantics {sem!r} (rule 2)")
        if e.get("risk_class") == "irreversible":
            ref = e.get("confirmation_of")
            if not _int(ref):
                errs.append(f"line {n}: irreversible COMMIT without confirmation_of (rule 4)")
            elif (sid, ref) not in offers or e.get("intent") not in offers[(sid, ref)]:
                errs.append(f"line {n}: confirmation_of {ref} is not an earlier final OFFER of {e.get('intent')!r} (rule 4)")
            elif (sid, ref) in used:
                errs.append(f"line {n}: OFFER unit {ref} is confirmed twice (rule 4)")
            else:
                used.add((sid, ref))
        if "undo_of" in e:
            tgt = commits.get((sid, e["undo_of"]))
            if tgt is None:
                errs.append(f"line {n}: undo_of {e['undo_of']} is not an earlier final COMMIT (rule 5)")
            elif tgt == "irreversible":
                errs.append(f"line {n}: undo_of {e['undo_of']} targets an irreversible COMMIT (rule 5)")
        if _int(unit):
            commits[(sid, unit)] = e.get("risk_class")
    return errs


def acted(decisions: list[dict[str, Any]]) -> tuple[list[str | None], list[str | None]]:
    ai, at = [], []
    for e in decisions:
        if e.get("type") != "trust_decision" or e.get("is_final") is not True or e.get("action") != "COMMIT":
            continue
        if _is_intent(e):
            ai.append(e.get("intent"))
        else:
            sh = e.get("shown")
            at.append(sh[0] if isinstance(sh, list) and sh else None)
    return ai, at


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
    out = [_res("FEP3-PARSE", parse_errors or [])]
    kind = stream_kind(events)
    out.append(_res("FEP3-KIND", [] if kind != "unknown" else
                    ["line 1 is neither a header nor a trust_decision, or a decision log has other events"], kind))
    inp, dec = kind == "input", kind == "decisions"
    na_in, na_dec = (None if inp else "not an input stream"), (None if dec else "not a decision log")
    out.append(_res("FEP3-DECL", decl_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP3-VOCAB", vocab_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP3-INTENT", intent_errors(events) if inp else None, skipped=na_in))
    out.append(_res("FEP3-FEEDBACK", feedback_errors(events) if inp else None, skipped=na_in))
    fmt = [x for e in events for x in td_intent_format_errors(e)] if dec else None
    out.append(_res("FEP3-TD-FORMAT", fmt, f"{len(events)} decision(s)", skipped=na_dec))
    out.append(_res("FEP3-TD-FINAL", td_final_errors(events) if dec else None, skipped=na_dec))
    out.append(_res("FEP3-SAFETY", safety_errors(events) if dec else None, skipped=na_dec))
    return out


def check_file(path: str | PathLike[str]) -> TargetReport:
    events, perr = read_events(path)
    results = check_events(events, perr)
    kind = stream_kind(events)
    if kind == "input" and not perr:
        from fidetype.conformance import check_file as v01_check

        fails = v01_check(path).failures("core")
        results.insert(2, _res("FEP3-V01-CORE", [f"{r.check_id}: {r.message}" for r in fails], "v0.1 core passed"))
    else:
        results.insert(2, _res("FEP3-V01-CORE", None, skipped="not an input stream"))
    return TargetReport(str(path), "file", results, {"format": "jsonl", "kind": kind, "events": len(events)})


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    kind = stream_kind(events)
    if kind == "decisions":
        ai, at = acted(events)
        return {"kind": kind, "decisions": len(events), "intent_decisions": sum(_is_intent(e) for e in events),
                "final": sum(e.get("is_final") is True for e in events), "acted_intents": ai, "acted_texts": at}
    return {
        "kind": kind,
        "declarations": sum(1 for e in events if e["type"] == "header" and DECLARATION_KEY in e),
        "intents": sum(e["type"] == "intent" for e in events),
        "final_intents": sum(e["type"] == "intent" and e.get("is_final") is True for e in events),
        "feedback": sum(e["type"] == "intent_feedback" for e in events),
        "hypotheses": sum(e["type"] == "hypothesis" for e in events),
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

DECL = {"vocab_id": "intent.conformance-home", "vocab_version": "1", "intents": [
    {"id": "intent.rest", "risk": "safe", "role": "null"},
    {"id": "intent.select", "risk": "undoable"},
    {"id": "intent.next", "risk": "safe"},
    {"id": "intent.stop", "risk": "safe"},
    {"id": "intent.undo", "risk": "undoable", "role": "undo"},
    {"id": "intent.cancel", "risk": "safe", "role": "cancel"},
    {"id": "intent.confirm", "risk": "irreversible", "role": "confirm"},
    {"id": "intent.call-caregiver", "risk": "irreversible", "label": "call the caregiver"},
]}
CMD_VOCAB = [it["id"] for it in DECL["intents"]]


def _decl(**over: Any) -> dict[str, Any]:
    d = {**DECL, "intents": [dict(i) for i in DECL["intents"]]}
    for k, v in over.items():
        if v is _DROP:
            d.pop(k, None)
        else:
            d[k] = v
    return d


def _ih(**over: Any) -> dict[str, Any]:
    """A command-vocabulary header with the declaration."""
    kw: dict[str, Any] = {"vocab_type": "command", "blank_id": None, DECLARATION_KEY: _decl()}
    kw.update(over)
    vocab = kw.pop("vocab", CMD_VOCAB)
    return _header(vocab, **kw)


def _intent(iid: str = "u1", t: float = 1.0, cands: list | None = None, **kw: Any) -> dict[str, Any]:
    ev: dict[str, Any] = {"type": "intent", "id": iid, "t": t, "is_final": True, "score_semantics": "uncalibrated_prob",
                          "candidates": cands if cands is not None else
                          [{"intent": "intent.select", "score": 0.81}, {"intent": "intent.next", "score": 0.12}]}
    for k, v in kw.items():
        if v is _DROP:
            ev.pop(k, None)
        else:
            ev[k] = v
    return ev


def _input(*body: dict[str, Any], header: dict[str, Any] | None = None, end: bool = True) -> Callable[[Path], None]:
    return _w_lines([header or _ih(), *body, *([{"type": "end"}] if end else [])])


def _td(**kw: Any) -> dict[str, Any]:
    ev = {"type": "trust_decision", "profile": "intent", "session": "u1", "seq": 0, "unit": 0, "is_final": True,
          "action": "COMMIT", "reason": "p 0.97 >= 0.90 (undoable)", "p_top1": 0.97, "score_semantics": "calibrated_prob",
          "risk_class": "undoable", "threshold": 0.9, "intent": "intent.select", "role": "action",
          "config_id": "icfg-0123456789abcdef", "vocab_id": "intent.conformance-home"}
    for k, v in kw.items():
        if v is _DROP:
            ev.pop(k, None)
        else:
            ev[k] = v
    return ev


def _armed(seq: int = 0, unit: int = 0, **kw: Any) -> dict[str, Any]:
    return _td(seq=seq, unit=unit, action="OFFER", intent="intent.call-caregiver", offered=["intent.call-caregiver"],
               confirm_required=True, risk_class="irreversible", threshold=0.99, p_top1=0.995,
               reason="armed: needs confirmation", **kw)


def _confirmed(seq: int = 1, unit: int = 1, ref: int | None = 0, **kw: Any) -> dict[str, Any]:
    base = dict(seq=seq, unit=unit, intent="intent.call-caregiver", risk_class="irreversible", threshold=0.99,
                p_top1=0.996, confirmation_of=ref, confirmed_via="intent", reason="confirmed")
    if ref is None:
        base["confirmation_of"] = _DROP
    base.update(kw)
    return _td(**base)


def _text_td(**kw: Any) -> dict[str, Any]:
    ev = {"type": "trust_decision", "session": "u1", "seq": 0, "utterance": 0, "is_final": True, "action": "COMMIT",
          "shown": ["ab"], "p_top1": 0.93, "score_semantics": "calibrated_prob", "config_id": "tcfg-0123456789abcdef"}
    ev.update(kw)
    return ev


def build_vectors() -> list[Vector]:
    vs: list[Vector] = []

    def add(vid: str, file: str, expect: str, clause: str, desc: str, expected: dict | None = None,
            failing: str | None = None, writer: Callable[[Path], None] | None = None) -> None:
        vs.append(Vector(vid, file, expect, f"{FEP} {clause}", desc, None, expected or {}, failing, writer))

    V = len(VOCAB)
    # --- input streams: accept
    add("I01", "i01-intents.jsonl", "accept", "2, 3",
        "Command stream with a declaration; a provisional intent, its final revision, and a top-k intent",
        {"kind": "input", "declarations": 1, "intents": 3, "final_intents": 2},
        writer=_input(_intent("u1a", 1.0, is_final=False), _intent("u1", 1.2, revision_of="u1a"),
                      _intent("u2", 2.0, [{"intent": "intent.call-caregiver", "score": 0.6}, {"intent": "intent.stop", "score": 0.1}])))
    add("I02", "i02-text-and-intent.jsonl", "accept", "7 r1",
        "A character (text) stream that also carries intent events: frames, segment_end and intents interleave",
        {"kind": "input", "intents": 2, "n_frames": 2},
        writer=_input(*_frames(2, V, 3), _intent("u1", 0.05), {"type": "segment_end", "t": 0.1},
                      _intent("u2", 0.2, [{"intent": "intent.stop", "score": 0.9}]),
                      header=_header(**{DECLARATION_KEY: _decl()})))
    add("I03", "i03-feedback.jsonl", "accept", "4",
        "intent_feedback events: confirmed, selected (with intent), undone, cancelled",
        {"kind": "input", "feedback": 4},
        writer=_input(_intent("u1"), {"type": "intent_feedback", "ref_unit": 0, "outcome": "confirmed", "source": "switch"},
                      {"type": "intent_feedback", "ref_unit": 1, "outcome": "selected", "intent": "intent.next", "t": 3.0},
                      {"type": "intent_feedback", "ref_unit": 2, "outcome": "undone"},
                      {"type": "intent_feedback", "ref_unit": 3, "outcome": "cancelled"}))
    add("I04", "i04-no-score.jsonl", "accept", "3 r3",
        "score_semantics none: candidates without scores (rank only; a layer may OFFER, never COMMIT)",
        {"kind": "input", "intents": 1},
        writer=_input(_intent(score_semantics="none", cands=[{"intent": "intent.select"}, {"intent": "intent.next", "score": None}])))
    add("I05", "i05-command-frames.jsonl", "accept", "2 r5",
        "Command-vocabulary frames (vocab equals the declared intents) closed by segment_end",
        {"kind": "input", "n_frames": 2},
        writer=_input(*_frames(2, len(CMD_VOCAB), 4), {"type": "segment_end", "t": 0.1}))
    add("I06", "i06-v01-decision.jsonl", "accept", "1",
        "A v0.1 decision event (3.5) on a command stream: maps to a one-candidate intent",
        {"kind": "input", "intents": 0},
        writer=_input({"type": "decision", "t": 0.5, "label": "intent.stop", "score": 0.7, "score_semantics": "uncalibrated_prob"}))
    # --- input streams: reject
    add("I07", "i07-decl-not-object.jsonl", "reject", "2 table", "intent_declaration is a list",
        failing="FEP3-DECL", writer=_input(header=_ih(**{DECLARATION_KEY: ["intent.select"]})))
    add("I08", "i08-decl-duplicate.jsonl", "reject", "2 r1", "Two intents with the same id",
        failing="FEP3-DECL", writer=_input(header=_header(**{DECLARATION_KEY: _decl(intents=[
            {"id": "intent.select", "risk": "undoable"}, {"id": "intent.select", "risk": "safe"}])})))
    add("I09", "i09-decl-bad-risk.jsonl", "reject", "2 r2", 'risk "dangerous" is not a risk class',
        failing="FEP3-DECL", writer=_input(header=_header(**{DECLARATION_KEY: _decl(intents=[
            {"id": "intent.select", "risk": "dangerous"}])})))
    add("I10", "i10-decl-two-confirm.jsonl", "reject", "2 r3", "Two intents with role confirm",
        failing="FEP3-DECL", writer=_input(header=_header(**{DECLARATION_KEY: _decl(intents=[
            {"id": "intent.yes", "risk": "irreversible", "role": "confirm"},
            {"id": "intent.ok", "risk": "irreversible", "role": "confirm"}, {"id": "intent.go", "risk": "undoable"}])})))
    add("I11", "i11-decl-weak-confirm.jsonl", "reject", "2 r4",
        "The confirm intent is undoable although the vocabulary has an irreversible intent",
        failing="FEP3-DECL", writer=_input(header=_header(**{DECLARATION_KEY: _decl(intents=[
            {"id": "intent.confirm", "risk": "undoable", "role": "confirm"},
            {"id": "intent.call-caregiver", "risk": "irreversible"}])})))
    add("I12", "i12-command-vocab-mismatch.jsonl", "reject", "2 r5",
        "Command stream whose vocab has a token that is not declared",
        failing="FEP3-VOCAB", writer=_input(header=_ih(vocab=[*CMD_VOCAB[:-1], "intent.open-door"])))
    add("I13", "i13-intent-no-declaration.jsonl", "reject", "3 r1", "An intent event in a stream without a declaration",
        failing="FEP3-INTENT", writer=_input(_intent(), header=_header()))
    add("I14", "i14-intent-unknown.jsonl", "reject", "3 r2", "A candidate intent that is not declared",
        failing="FEP3-INTENT", writer=_input(_intent(cands=[{"intent": "intent.open-door", "score": 0.5}])))
    add("I15", "i15-intent-duplicate-candidate.jsonl", "reject", "3 r2", "The same intent twice in candidates",
        failing="FEP3-INTENT", writer=_input(_intent(cands=[{"intent": "intent.stop", "score": 0.5}, {"intent": "intent.stop", "score": 0.4}])))
    add("I16", "i16-intent-score-range.jsonl", "reject", "3 r3", "A probability score of 1.2",
        failing="FEP3-INTENT", writer=_input(_intent(cands=[{"intent": "intent.stop", "score": 1.2}])))
    add("I17", "i17-intent-sum.jsonl", "reject", "3 r3", "Probability scores that sum to 1.3",
        failing="FEP3-INTENT", writer=_input(_intent(cands=[{"intent": "intent.stop", "score": 0.7}, {"intent": "intent.next", "score": 0.6}])))
    add("I18", "i18-intent-unranked.jsonl", "reject", "3 r4", "Candidates not ranked best first",
        failing="FEP3-INTENT", writer=_input(_intent(cands=[{"intent": "intent.stop", "score": 0.1}, {"intent": "intent.next", "score": 0.6}])))
    add("I19", "i19-intent-none-with-score.jsonl", "reject", "3 r3", "score_semantics none but a candidate has a score",
        failing="FEP3-INTENT", writer=_input(_intent(score_semantics="none", cands=[{"intent": "intent.stop", "score": 0.4}])))
    add("I20", "i20-intent-no-is-final.jsonl", "reject", "3 table", "intent event without is_final",
        failing="FEP3-INTENT", writer=_input(_intent(is_final=_DROP)))
    add("I21", "i21-intent-duplicate-id.jsonl", "reject", "3 r5", "Two intent events with the same id",
        failing="FEP3-INTENT", writer=_input(_intent("u1", 1.0), _intent("u1", 2.0)))
    add("I22", "i22-feedback-bad-outcome.jsonl", "reject", "4 table", 'feedback outcome "maybe"',
        failing="FEP3-FEEDBACK", writer=_input({"type": "intent_feedback", "ref_unit": 0, "outcome": "maybe"}))
    add("I23", "i23-v01-core-broken.jsonl", "reject", "Compatibility",
        "Valid FEP-0003 parts, but a frame breaks v0.1 (row does not sum to 1)", failing="FEP3-V01-CORE",
        writer=_input({**_frames(1, len(CMD_VOCAB), 4)[0], "log_probs": [0.0] * len(CMD_VOCAB)}, _intent()))
    # --- decision logs: accept
    add("D01", "d01-log-commit-offer-abstain.jsonl", "accept", "5",
        "Intent COMMIT (undoable), OFFER (two intents), ABSTAIN (null top intent)",
        {"kind": "decisions", "intent_decisions": 3, "final": 3, "acted_intents": ["intent.select"]},
        writer=_w_lines([_td(), _td(seq=1, unit=1, action="OFFER", intent=_DROP, offered=["intent.next", "intent.stop"],
                                    p_top1=0.55, reason="offer 2"),
                         _td(seq=2, unit=2, action="ABSTAIN", intent=_DROP, role="null", p_top1=0.8, risk_class="safe",
                             reason="top intent is null")]))
    add("D02", "d02-log-confirm.jsonl", "accept", "6 r4",
        "Irreversible intent armed (OFFER, confirm_required), then executed by a confirm unit (confirmation_of)",
        {"kind": "decisions", "acted_intents": ["intent.call-caregiver"]},
        writer=_w_lines([_armed(), _confirmed()]))
    add("D03", "d03-log-feedback-confirm.jsonl", "accept", "6 r4",
        "Irreversible intent armed, then confirmed by a switch (confirmed_via feedback, p_top1 null)",
        {"kind": "decisions", "acted_intents": ["intent.call-caregiver"]},
        writer=_w_lines([_armed(), _confirmed(confirmed_via="feedback", p_top1=None, threshold=None)]))
    add("D04", "d04-log-mixed-profiles.jsonl", "accept", "7 r2",
        "Text (FEP-0001) and intent decisions in one session share seq; each keeps its own utterance / unit",
        {"kind": "decisions", "decisions": 4, "intent_decisions": 2, "acted_intents": ["intent.stop"], "acted_texts": ["ab"]},
        writer=_w_lines([_text_td(seq=0, is_final=False, action="OFFER"),
                         _td(seq=1, unit=0, intent="intent.stop", risk_class="safe", threshold=0.5, p_top1=0.7),
                         _text_td(seq=2),
                         _td(seq=3, unit=1, action="ABSTAIN", intent=_DROP, p_top1=0.3)]))
    add("D05", "d05-log-undo.jsonl", "accept", "6 r5",
        "An undoable COMMIT, then an undo COMMIT that names it (undo_of)",
        {"kind": "decisions", "acted_intents": ["intent.select", "intent.undo"]},
        writer=_w_lines([_td(), _td(seq=1, unit=1, intent="intent.undo", role="undo", undo_of=0)]))
    add("D06", "d06-log-provisional-commit.jsonl", "accept", "5 r4",
        "A provisional intent COMMIT, then a final ABSTAIN: a bridge MUST NOT act",
        {"kind": "decisions", "final": 1, "acted_intents": []},
        writer=_w_lines([_td(is_final=False), _td(seq=1, action="ABSTAIN", intent=_DROP, p_top1=0.4)]))
    # --- decision logs: reject
    add("D07", "d07-td-commit-no-intent.jsonl", "reject", "5 r3", "An intent COMMIT without intent",
        failing="FEP3-TD-FORMAT", writer=_w_lines([_td(intent=_DROP)]))
    add("D08", "d08-td-shown.jsonl", "reject", "5 r2", "An intent decision with shown (a text consumer could type it)",
        failing="FEP3-TD-FORMAT", writer=_w_lines([_td(shown=["intent.select"])]))
    add("D09", "d09-td-utterance.jsonl", "reject", "5 r1", "An intent decision with utterance in place of unit",
        failing="FEP3-TD-FORMAT", writer=_w_lines([_td(unit=_DROP, utterance=0)]))
    add("D10", "d10-td-ask.jsonl", "reject", "5 table", "Intent action ASK (intents use COMMIT, OFFER, ABSTAIN)",
        failing="FEP3-TD-FORMAT", writer=_w_lines([_td(action="ASK", intent=_DROP, offered=["intent.select"])]))
    add("D11", "d11-td-bad-risk.jsonl", "reject", "5 table", 'risk_class "low"',
        failing="FEP3-TD-FORMAT", writer=_w_lines([_td(risk_class="low")]))
    add("D12", "d12-td-bad-profile.jsonl", "reject", "5 table", 'profile "pointer" is not defined',
        failing="FEP3-TD-FORMAT", writer=_w_lines([_td(profile="pointer")]))
    add("D13", "d13-td-two-finals.jsonl", "reject", "5 r4", "Two final decisions for the same intent unit",
        failing="FEP3-TD-FINAL", writer=_w_lines([_td(), _td(seq=1, action="ABSTAIN", intent=_DROP)]))
    add("D14", "d14-td-seq-across-profiles.jsonl", "reject", "7 r2",
        "A text and an intent decision of one session reuse the same seq",
        failing="FEP3-TD-FINAL", writer=_w_lines([_text_td(seq=0), _td(seq=0)]))
    add("D15", "d15-safety-null.jsonl", "reject", "6 r1", "A final COMMIT of a null (rest) intent",
        failing="FEP3-SAFETY", writer=_w_lines([_td(intent="intent.rest", role="null", risk_class="safe")]))
    add("D16", "d16-safety-below-threshold.jsonl", "reject", "6 r3", "A COMMIT with p_top1 0.6 below its threshold 0.9",
        failing="FEP3-SAFETY", writer=_w_lines([_td(p_top1=0.6)]))
    add("D17", "d17-safety-irreversible-direct.jsonl", "reject", "6 r4",
        "An irreversible intent committed directly (no confirmation_of)",
        failing="FEP3-SAFETY", writer=_w_lines([_confirmed(seq=0, unit=0, ref=None)]))
    add("D18", "d18-safety-confirm-wrong-offer.jsonl", "reject", "6 r4",
        "confirmation_of names an OFFER of another intent",
        failing="FEP3-SAFETY", writer=_w_lines([_td(action="OFFER", intent=_DROP, offered=["intent.next"], p_top1=0.5),
                                               _confirmed()]))
    add("D19", "d19-safety-confirm-twice.jsonl", "reject", "6 r4", "One armed OFFER confirmed twice",
        failing="FEP3-SAFETY", writer=_w_lines([_armed(), _confirmed(), _confirmed(seq=2, unit=2)]))
    add("D20", "d20-safety-undo-irreversible.jsonl", "reject", "6 r5", "undo_of names an irreversible COMMIT",
        failing="FEP3-SAFETY", writer=_w_lines([_armed(), _confirmed(),
                                               _td(seq=2, unit=2, intent="intent.undo", role="undo", undo_of=1)]))
    add("D21", "d21-safety-no-score-commit.jsonl", "reject", "6 r2",
        "A COMMIT on an input whose score_semantics is none",
        failing="FEP3-SAFETY", writer=_w_lines([_td(input={"kind": "intent", "intent_id": "u1", "score_semantics": "none"})]))
    vs.sort(key=lambda v: v.vid)
    return vs


__all__ = ["CHECKS", "acted", "build_vectors", "check_events", "check_file", "consume", "safety_errors",
           "summarize", "td_final_errors", "td_intent_format_errors"]
