"""Conformance profile ``fep-0002``: NeuralTextStream over LSL (M6-09).

Tests the binding of ``spec/feps/0002-nts-over-lsl.md`` without a network
and without ``pylsl``. Each golden vector is a JSON **scenario**: LSL
stream infos (as the XML that liblsl gives), scripted sample chunks with
their LSL timestamps, the clock correction, and the consumer settings.

``kind = "inlet"``
    One primary inlet (frames, or markers for a hypothesis-only producer),
    an optional events inlet, and an optional inlet for after a reconnect.
    The reference consumer plays the scripts through
    :class:`~fidetype.adapters.lsl.LSLEventSource` and
    :class:`~fidetype.adapters.lsl.LSLTrustRunner` into a
    :class:`~fidetype.trust.streaming.StreamingTrustLayer` (a fixed loose
    synthetic config; CTC greedy decoder on the frames route). At the end
    of the scripts it closes the open utterance.
``kind = "decisions"``
    A ``fidetype.decisions`` stream: its info and its string samples.

Numbers in numeric samples: JSON ``null`` is ``-inf`` and the string
``"NaN"`` is NaN (JSON has no tokens for them). All content is synthetic.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from os import PathLike
from pathlib import Path
from typing import Any, Callable

import numpy as np

from fidetype.conformance.checks import FAIL, PASS, SKIP, CheckResult
from fidetype.conformance.io import StreamRejected
from fidetype.conformance.report import TargetReport
from fidetype.conformance.vectors import BASE_META, Vector, _lp, _lsm
from fidetype.streams.vocab import VOCAB

SUFFIXES = (".json", ".xml")
FEP = "FEP-0002"
SCENARIO_SCHEMA = "fidetype.conformance.lsl-scenario/1"

#: (id, keyword, FEP clause, title)
CHECKS = [
    ("FEP2-BINDING", "MUST", "9", "desc/fidetype/binding is a known version; event_clock is lsl or source"),
    ("FEP2-FRAMES", "MUST", "3", "Frames stream: type NTS, float32 or double64, V channels, labels in vocab order, srate = 1 / frame_period"),
    ("FEP2-DESC", "MUST", "4", "desc/fidetype/nts_header is a JSON object with spec_version 0.1; values is a known kind"),
    ("FEP2-MARKERS", "MUST", "5", "Events stream: type Markers, 1 string channel, irregular rate"),
    ("FEP2-DECISIONS", "MUST", "8", "Decisions stream: Markers, 1 string channel, role and event_type keys; samples are valid trust_decision events"),
    ("FEP2-CONSUME", "MUST", "3-7", "The reference consumer accepts the scenario"),
]
_META = {c[0]: c for c in CHECKS}

HOW_TO_USE = ("FEP-0002 profile. Each vector is a JSON scenario (schema fidetype.conformance.lsl-scenario/1): LSL stream "
              "infos as XML, scripted chunks (samples + LSL timestamps, or \"lost\"), the clock correction and the "
              "consumer settings. Feed the scripts to your LSL consumer as if they came from liblsl inlets. In "
              "numeric samples null = -inf and \"NaN\" = NaN. A conforming consumer accepts exactly the vectors with "
              "expect = accept and, for those, gives the values in 'expected' (see FEP-0002 section 10 for their "
              "meaning).")

# The loose synthetic trust config of the reference consumer (COMMIT, OFFER and ABSTAIN all occur).
_POLICY = dict(commit_p=0.3, commit_max_risk=1.0, abstain_risk=1.01)


# --- scenario decoding -----------------------------------------------------------------------


def _num_in(x: Any) -> float:
    if x is None:
        return -math.inf
    if isinstance(x, str):
        special = {"NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf}
        return special[x] if x in special else x  # type: ignore[return-value]  # the source refuses it
    return float(x)


def _inlet(spec: dict[str, Any]) -> Any:
    from fidetype.adapters.lsl import LSLStreamInfo, ScriptedInlet

    info = LSLStreamInfo.from_xml(spec["info_xml"])
    script: list[Any] = []
    for ch in spec.get("chunks", []):
        if ch == "lost":
            script.append("lost")
            continue
        samples = ch["samples"]
        if not info.is_string:
            samples = [[_num_in(v) for v in row] for row in samples]
        script.append((samples, [float(t) for t in ch["timestamps"]]))
    return ScriptedInlet(info, script, float(spec.get("time_correction", 0.0)))


def _rows_sha(rows: list[list[float]]) -> str:
    a = np.asarray(rows, dtype="<f8") if rows else np.zeros((0,), dtype="<f8")
    return hashlib.sha256(a.tobytes()).hexdigest()


def run_inlet_scenario(sc: dict[str, Any]) -> dict[str, Any]:
    """Play an ``inlet`` scenario through the reference LSL consumer. Raise on rejection."""
    from fidetype.adapters.lsl import LSLEventSource, LSLMapping, LSLTrustRunner
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer
    from fidetype.trust.testing import greedy_nbest

    inl = sc["inlets"]
    primary = _inlet(inl["primary"])
    events = _inlet(inl["events"]) if inl.get("events") else None
    after = inl.get("primary_after_reconnect")
    pending = [after]

    def reopen() -> Any:
        if pending and pending[0] is not None:
            return _inlet(pending.pop(0))
        raise RuntimeError("no stream")

    settings = dict(sc.get("consumer_settings") or {})
    for k in ("boundary_markers",):
        if k in settings:
            settings[k] = tuple(settings[k])
    mapping = LSLMapping(merge_window_s=1e9, reconnect_timeout_s=1.0, **settings)
    ticks = itertools.count()
    clock = lambda: 1000.0 + next(ticks) * 1e-3  # noqa: E731 - deterministic receiver clock
    src = LSLEventSource(primary, events, mapping, reopen_primary=reopen if after else None, clock=clock)
    route = sc.get("route", "frames")
    cfg = FrozenTrustConfig(name="fep-0002-conformance").with_policy(**_POLICY)
    layer = StreamingTrustLayer(cfg, decode_fn=greedy_nbest if route == "frames" else None,
                                streaming=StreamingConfig(route=route, max_attempts=1))
    seen: list[dict[str, Any]] = []
    orig_poll, orig_drain = src.poll, src.drain

    def poll(timeout: float = 0.0) -> list[dict[str, Any]]:
        out = orig_poll(timeout)
        seen.extend(out)
        return out

    def drain() -> list[dict[str, Any]]:
        out = orig_drain()
        seen.extend(out)
        return out

    src.poll, src.drain = poll, drain  # type: ignore[method-assign]
    decisions: list[dict[str, Any]] = []
    runner = LSLTrustRunner(layer, src, session_id="lsl", sink=decisions.append, on_bad_event="raise")
    idle = 0
    for _ in range(10000):
        n0 = len(seen)
        runner.step(0.0)
        if runner.summary.ended:
            break
        busy = any(r.lost_since is not None or getattr(r.inlet, "script", None) for r in src.readers)
        idle = 0 if (busy or len(seen) != n0) else idle + 1
        if idle >= 3:
            break
    runner.finish()
    if not runner.summary.ended:
        runner.flush()
    frames = [e for e in seen if e.get("type") == "frame"]
    rows = [[float(v) for v in e["log_probs"]] for e in frames]
    types: dict[str, int] = {}
    for e in seen:
        if e.get("type") != "lsl_status":
            types[e["type"]] = types.get(e["type"], 0) + 1
    head = next(e for e in seen if e.get("type") == "header")
    st = src.stats
    return {
        "clock_domain": head.get("clock_domain"),
        "binding": head["lsl"]["binding"],
        "event_clock": head["lsl"]["event_clock"],
        "vocab_size": len(head["vocab"]),
        "frames": len(frames),
        "first_frame_t": frames[0]["t"] if frames else None,
        "rows_sha256": _rows_sha(rows),
        "neg_inf_cells": int(sum(1 for r in rows for v in r if v == -math.inf)),
        "event_types": dict(sorted(types.items())),
        "hypothesis_times": [[e.get("t_start"), e.get("t_end")] for e in seen if e.get("type") == "hypothesis"],
        "marker_lsl_t": [e["lsl_t"] for e in seen if "lsl_t" in e],
        "decisions": len(decisions),
        "final_decisions": sum(d["is_final"] for d in decisions),
        "aborted_utterances": runner.summary.aborted_utterances,
        "gaps": st.gaps, "clamped": st.clamped, "dropped_out_of_order": st.dropped_out_of_order,
        "reconnects": st.reconnects, "bad_markers": st.bad_markers, "ignored_markers": st.ignored_markers,
    }


def decisions_info_errors(info: Any) -> list[str]:
    from fidetype.adapters.lsl import MARKERS_TYPE, check_binding

    errs = []
    if info.type != MARKERS_TYPE:
        errs.append(f"type {info.type!r} is not {MARKERS_TYPE!r}")
    if info.channel_count != 1 or info.channel_format != "string":
        errs.append("a decisions stream has 1 channel of format string")
    if info.nominal_srate != 0:
        errs.append("a decisions stream has an irregular rate (nominal_srate 0)")
    if info.fidetype.get("role") != "trust_decisions":
        errs.append("desc/fidetype/role must be trust_decisions")
    if info.fidetype.get("event_type") != "trust_decision":
        errs.append("desc/fidetype/event_type must be trust_decision")
    try:
        check_binding(info)
    except ValueError as e:
        errs.append(str(e))
    return errs


def run_decisions_scenario(sc: dict[str, Any]) -> dict[str, Any]:
    """Read a ``decisions`` scenario. Raise on rejection."""
    from fidetype.adapters.lsl import LSLStreamInfo
    from fidetype.conformance.profiles.fep0001 import acted_texts, td_final_errors, td_format_errors

    info = LSLStreamInfo.from_xml(sc["info_xml"])
    errs = decisions_info_errors(info)
    events = []
    for n, s in enumerate(sc.get("samples", []), 1):
        try:
            ev = json.loads(s, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        except ValueError as e:
            errs.append(f"sample {n}: not JSON: {e}")
            continue
        if not isinstance(ev, dict) or ev.get("type") != "trust_decision":
            errs.append(f"sample {n}: not a trust_decision event")
            continue
        ev["_line"] = n
        errs += td_format_errors(ev)
        events.append(ev)
    errs += td_final_errors(events)
    if errs:
        raise StreamRejected("; ".join(errs[:5]), f"{FEP} 8")
    return {"decisions": len(events), "final": sum(e.get("is_final") is True for e in events),
            "acted": acted_texts(events)}


def load_scenario(path: str | PathLike[str]) -> dict[str, Any]:
    sc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(sc, dict) or sc.get("schema") != SCENARIO_SCHEMA or sc.get("kind") not in ("inlet", "decisions"):
        raise StreamRejected(f"not a {SCENARIO_SCHEMA} scenario", FEP)
    return sc


def consume(path: str | PathLike[str]) -> dict[str, Any]:
    """Reference consumer of the profile: return a summary, or raise."""
    sc = load_scenario(path)
    return run_inlet_scenario(sc) if sc["kind"] == "inlet" else run_decisions_scenario(sc)


# --- producer checks of stream infos ------------------------------------------------------------


def _res(cid: str, errs: list[str] | None, msg_ok: str = "", skipped: str | None = None) -> CheckResult:
    _, kw, clause, title = _META[cid]
    if skipped is not None:
        status, msg = SKIP, skipped
    elif errs:
        status, msg = FAIL, "; ".join(errs[:6])
    else:
        status, msg = PASS, msg_ok
    return CheckResult(cid, "core", kw, f"{FEP} {clause}", title, status, msg)


def info_role(info: Any) -> str:
    if info.fidetype.get("role") == "trust_decisions":
        return "decisions"
    return "events" if info.is_string else "frames"


def check_info(info: Any) -> list[CheckResult]:
    """Producer checks of one LSL stream info."""
    from fidetype.adapters.lsl import MARKERS_TYPE, NTS_STREAM_TYPE, check_binding, check_native_frames

    role = info_role(info)
    try:
        check_binding(info)
        b_err: list[str] = []
    except ValueError as e:
        b_err = [str(e)]
    out = [_res("FEP2-BINDING", b_err, info.fidetype.get("binding", "absent (0.1 assumed)"))]
    d_err: list[str] = []
    header = None
    if role != "decisions":
        try:
            header = info.nts_header
        except ValueError as e:
            d_err.append(str(e))
        if header is None and not d_err:
            d_err.append("no desc/fidetype/nts_header")
        elif header is not None and header.get("spec_version") != "0.1":
            d_err.append(f"nts_header spec_version {header.get('spec_version')!r} is not '0.1'")
        if info.fidetype.get("values", "log_probs") not in ("log_probs", "probs", "logits"):
            d_err.append(f"values {info.fidetype.get('values')!r} is not log_probs, probs or logits")
        out.append(_res("FEP2-DESC", d_err))
    else:
        out.append(_res("FEP2-DESC", None, skipped="decisions stream"))
    if role == "frames":
        f_err = [] if info.type == NTS_STREAM_TYPE else [f"type {info.type!r} is not {NTS_STREAM_TYPE!r}"]
        if header is not None:
            if len(header.get("vocab") or []) != info.channel_count:
                f_err.append(f"{info.channel_count} channels but the vocab has {len(header.get('vocab') or [])} tokens")
            try:
                check_native_frames(info, header)
            except ValueError as e:
                f_err.append(str(e))
        out.append(_res("FEP2-FRAMES", f_err))
    else:
        out.append(_res("FEP2-FRAMES", None, skipped="not a frames stream"))
    if role == "events":
        m_err = [] if info.type == MARKERS_TYPE else [f"type {info.type!r} is not {MARKERS_TYPE!r}"]
        if info.channel_count != 1:
            m_err.append("an events stream has 1 channel")
        if info.nominal_srate != 0:
            m_err.append("an events stream has an irregular rate (nominal_srate 0)")
        out.append(_res("FEP2-MARKERS", m_err))
    else:
        out.append(_res("FEP2-MARKERS", None, skipped="not an events stream"))
    out.append(_res("FEP2-DECISIONS", decisions_info_errors(info) if role == "decisions" else None,
                    skipped=None if role == "decisions" else "not a decisions stream"))
    return out


def check_file(path: str | PathLike[str]) -> TargetReport:
    """Producer check: a stream info ``.xml`` file, or a scenario ``.json`` file."""
    from fidetype.adapters.lsl import LSLStreamInfo

    p = Path(path)
    if p.suffix.lower() == ".xml":
        info = LSLStreamInfo.from_xml(p.read_text(encoding="utf-8"))
        return TargetReport(str(p), "file", check_info(info), {"format": "lsl-info-xml", "role": info_role(info)})
    try:
        sc = load_scenario(p)
    except Exception as e:  # noqa: BLE001
        return TargetReport(str(p), "file", [_res("FEP2-CONSUME", [f"{type(e).__name__}: {e}"])], {"format": "lsl-scenario"})
    cid = "FEP2-DECISIONS" if sc["kind"] == "decisions" else "FEP2-CONSUME"
    try:
        run_inlet_scenario(sc) if sc["kind"] == "inlet" else run_decisions_scenario(sc)
        res = _res(cid, [], "accepted")
    except Exception as e:  # noqa: BLE001 - any exception is a rejection
        res = _res(cid, [f"{type(e).__name__}: {e}"])
    return TargetReport(str(p), "file", [res], {"format": "lsl-scenario", "kind": sc["kind"]})


# --- golden vectors ----------------------------------------------------------------------------

T0 = 100.0
FP = 0.125
TC = 0.25
HEADER = {"type": "header", "spec_version": "0.1", "vocab": list(VOCAB), "vocab_type": "char", "blank_id": 0,
          "source": "conformance-vector", "frame_period": FP, "latency": 0.0, "clock_domain": "trial",
          "meta": dict(BASE_META)}
_DROP = object()


def _hdr(**over: Any) -> dict[str, Any]:
    h = {k: v for k, v in HEADER.items() if k != "type"}
    for k, v in over.items():
        if v is _DROP:
            h.pop(k, None)
        else:
            h[k] = v
    return h


def _info_xml(name: str, type_: str, n: int, srate: float, fmt: str, sid: str, labels: list[str] | None = None,
              desc: dict[str, str] | None = None) -> str:
    from fidetype.adapters.lsl import LSLStreamInfo, info_to_xml

    info = LSLStreamInfo(name, type_, n, srate, fmt, sid, f"uid-{sid}", "", 0.0,
                         channel_labels=list(labels or []), channel_units=["log_prob"] * len(labels or []),
                         fidetype=dict(desc or {}))
    return info_to_xml(info)


def _frames_xml(header: dict[str, Any] | None = None, fmt: str = "float32", srate: float = 1 / FP,
                labels: list[str] | None | object = _DROP, n: int | None = None, type_: str = "NTS",
                extra: dict[str, str] | None = None, raw_header: str | None = None, events: bool = True) -> str:
    h = header or _hdr()
    desc = {"nts_header": raw_header if raw_header is not None else json.dumps(h), "values": "log_probs",
            "role": "nts_frames", "binding": "nts-lsl/0.1"}
    if events:
        desc["events_source_id"] = "acme-1.events"
    desc.update(extra or {})
    lab = list(h.get("vocab", [])) if labels is _DROP else labels
    return _info_xml("acme.nts", type_, len(h.get("vocab", [])) if n is None else n, srate, fmt, "acme-1",
                     lab, {k: v for k, v in desc.items() if v is not None})


def _events_xml(header: dict[str, Any] | None = None, fmt: str = "string", event_clock: str | None = "lsl",
                extra: dict[str, str] | None = None, name: str = "acme.nts.events", sid: str = "acme-1.events") -> str:
    desc = {"nts_header": json.dumps(header or _hdr()), "role": "nts_events", "binding": "nts-lsl/0.1",
            "frames_source_id": "acme-1"}
    if event_clock is not None:
        desc["event_clock"] = event_clock
    desc.update(extra or {})
    return _info_xml(name, "Markers", 1, 0.0, fmt, sid, None, desc)


def _num_out(v: float) -> Any:
    if math.isnan(v):
        return "NaN"
    if v == -math.inf:
        return None
    return float(v)


def _rows(T: int, seed: int, fmt: str = "float32", V: int | None = None) -> list[list[Any]]:
    lp = _lp(T, V or len(VOCAB), seed)
    if fmt == "float32":
        lp = lp.astype(np.float32).astype(np.float64)
    return [[_num_out(float(x)) for x in row] for row in lp]


def _chunks(rows: list[list[Any]], stamps: list[float], size: int = 3) -> list[dict[str, Any]]:
    return [{"samples": rows[i:i + size], "timestamps": stamps[i:i + size]} for i in range(0, len(rows), size)]


def _stamps(T: int, t0: float = T0, dt: float = FP) -> list[float]:
    return [t0 + i * dt for i in range(T)]


def _markers(evs: list[Any], stamps: list[float], lead_empty: int = 0) -> list[Any]:
    """One marker per chunk (after ``lead_empty`` empty chunks). Dict events become JSON strings."""
    out: list[Any] = [{"samples": [], "timestamps": []}] * lead_empty
    for e, t in zip(evs, stamps):
        out.append({"samples": [[e if isinstance(e, str) else json.dumps(e)]], "timestamps": [t]})
    return out


def _scenario(kind: str, description: str, **body: Any) -> dict[str, Any]:
    return {"schema": SCENARIO_SCHEMA, "kind": kind, "fep": FEP, "description": description, **body}


def _w_json(obj: dict[str, Any]) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
                        newline="\n")

    return w


def _inlet_spec(info_xml: str, chunks: list[Any], tc: float = TC) -> dict[str, Any]:
    return {"info_xml": info_xml, "time_correction": tc, "chunks": chunks}


def _std(desc: str, T: int = 6, seed: int = 0, fmt: str = "float32", frames_xml: str | None = None,
         tc: float = TC, settings: dict[str, Any] | None = None, rows: list[list[Any]] | None = None,
         stamps: list[float] | None = None) -> dict[str, Any]:
    """Frames + events (segment_end, end) from one producer host."""
    rows = rows if rows is not None else _rows(T, seed, fmt)
    stamps = stamps if stamps is not None else _stamps(len(rows))
    last = stamps[-1]
    ev = [{"type": "segment_end", "t": last + 0.01}, {"type": "end"}]
    body: dict[str, Any] = {"route": "frames", "inlets": {
        "primary": _inlet_spec(frames_xml or _frames_xml(fmt=fmt), _chunks(rows, stamps), tc),
        "events": _inlet_spec(_events_xml(), _markers(ev, [last + 0.01, last + 0.02]), tc)}}
    if settings:
        body["consumer_settings"] = settings
    return _scenario("inlet", desc, **body)


def _td(**kw: Any) -> dict[str, Any]:
    ev = {"type": "trust_decision", "session": "lsl", "seq": 0, "utterance": 0, "is_final": True, "action": "COMMIT",
          "shown": ["ab"], "p_top1": 0.93, "score_semantics": "calibrated_prob", "set_size": 1, "guard_risk": 0.12,
          "config_id": "tcfg-0123456789abcdef",
          "lsl": {"streams": [{"name": "acme.nts", "type": "NTS", "source_id": "acme-1"}], "clock": "receiver",
                  "time_correction_s": TC, "updates": 1, "e2e_latency_s": 0.0123}}
    for k, v in kw.items():
        if v is _DROP:
            ev.pop(k, None)
        else:
            ev[k] = v
    return ev


def _dec_xml(fmt: str = "string", desc: dict[str, str] | None = None, type_: str = "Markers") -> str:
    from fidetype.adapters.lsl import decisions_desc

    d = decisions_desc("tcfg-0123456789abcdef")
    d.update(desc or {})
    return _info_xml("fidetype.decisions", type_, 1, 0.0, fmt, "fidetype.decisions.tcfg-0123456789abcdef", None,
                     {k: v for k, v in d.items() if v is not None})


def _decisions(desc: str, samples: list[Any], info_xml: str | None = None) -> dict[str, Any]:
    ss = [s if isinstance(s, str) else json.dumps(s) for s in samples]
    return _scenario("decisions", desc, info_xml=info_xml or _dec_xml(), samples=ss,
                     timestamps=[2000.0 + i for i in range(len(ss))])


def _hyp_events(t_start: float, t_end: float) -> list[dict[str, Any]]:
    return [{"type": "hypothesis", "id": "h1", "is_final": False, "score_semantics": "none",
             "nbest": [{"text": "ab", "score": -1.5}], "t_start": t_start, "t_end": t_end - 0.25},
            {"type": "hypothesis", "id": "h2", "revision_of": "h1", "is_final": True, "score_semantics": "none",
             "nbest": [{"text": "ab", "score": -1.0, "char_confidences": [0.9, 0.8]}, {"text": "a", "score": -2.5}],
             "t_start": t_start, "t_end": t_end},
            {"type": "end"}]


def build_vectors() -> list[Vector]:
    vs: list[Vector] = []

    def add(vid: str, file: str, expect: str, clause: str, desc: str, sc: dict[str, Any],
            expected: dict | None = None, failing: str = "FEP2-CONSUME") -> None:
        vs.append(Vector(vid, file, expect, f"{FEP} {clause}", desc, None, expected or {},
                         None if expect == "accept" else failing, _w_json(sc)))

    # --- accept: frames + events
    add("L01", "l01-native-float32.json", "accept", "3-6",
        "NTS-native float32 frames + events stream; receiver clock adds time_correction 0.25 s",
        _std("NTS-native float32 frames + events"),
        {"clock_domain": "lsl", "binding": "nts-lsl/0.1", "vocab_size": 28, "frames": 6, "first_frame_t": T0 + TC,
         "event_types": {"end": 1, "frame": 6, "header": 1, "segment_end": 1}, "final_decisions": 1,
         "marker_lsl_t": [T0 + 5 * FP + 0.01 + TC, T0 + 5 * FP + 0.02 + TC]})
    rows64 = _rows(6, 1, "double64")
    add("L02", "l02-native-double64-exact.json", "accept", "3 r4",
        "double64 frames: the received rows are bit-equal to the sent rows (rows_sha256 over float64 little-endian)",
        _std("double64 frames, exact", fmt="double64", rows=rows64),
        {"frames": 6, "rows_sha256": _rows_sha([[_num_in(v) for v in r] for r in rows64]), "final_decisions": 1})
    add("L03", "l03-no-binding-key.json", "accept", "9 r2", "No binding key: the consumer assumes nts-lsl/0.1",
        _std("no binding key", frames_xml=_frames_xml(extra={"binding": None})),
        {"binding": "nts-lsl/0.1", "final_decisions": 1})
    lp_inf = _lp(4, len(VOCAB), 2)
    lp_inf[:, 5] = -np.inf  # -inf cells (probability 0), then renormalise
    lp_inf = _lsm(lp_inf).astype(np.float32).astype(np.float64)
    rows_inf = [[_num_out(float(x)) for x in row] for row in lp_inf]
    add("L04", "l04-minus-inf-cells.json", "accept", "3 r5", "float32 frames with -inf cells (JSON null in the vector)",
        _std("-inf cells", rows=rows_inf), {"frames": 4, "neg_inf_cells": 4})
    add("L05", "l05-sender-clock.json", "accept", "6 r3", "Consumer setting clock = sender: raw LSL timestamps",
        _std("sender clock", settings={"clock": "sender"}), {"first_frame_t": T0, "clock_domain": "lsl"})
    # --- gaps, order
    st_gap = _stamps(3) + _stamps(3, T0 + 1.0)
    for mode, vid, exp in (("mark", "L06", {"gaps": 1, "final_decisions": 1, "event_types": {"end": 1, "frame": 6, "gap": 1, "header": 1, "segment_end": 1}}),
                           ("segment", "L07", {"gaps": 1, "final_decisions": 2}),
                           ("abort", "L08", {"gaps": 1, "final_decisions": 1, "aborted_utterances": 1})):
        add(vid, f"{vid.lower()}-gap-{mode}.json", "accept", "7",
            f"A frame step of 0.75 s (> 2.5 periods of 0.125 s); on_gap = {mode}",
            _std(f"gap, {mode}", stamps=st_gap, settings={"on_gap": mode}), exp)
    st_ooo = [T0, T0 + FP, T0 + FP - 0.001, T0 + 2 * FP, T0 + 2 * FP - 0.05, T0 + 3 * FP]
    add("L09", "l09-out-of-order.json", "accept", "6 r4",
        "One timestamp 1 ms back (clamped) and one 50 ms back (dropped); tolerance 5 ms",
        _std("out of order", stamps=st_ooo), {"frames": 5, "clamped": 1, "dropped_out_of_order": 1})
    # --- loss and reconnect
    rows_a, rows_b = _rows(3, 3), _rows(4, 4)
    st_b = _stamps(4, T0 + 2.0)
    ev_l = [{"type": "segment_end", "t": st_b[-1] + 0.01}, {"type": "end"}]
    add("L10", "l10-loss-reconnect.json", "accept", "7 r3",
        "The frames stream is lost inside an utterance and comes back: no decision on the cut utterance",
        _scenario("inlet", "loss and reconnect", route="frames", inlets={
            "primary": _inlet_spec(_frames_xml(), [_chunks(rows_a, _stamps(3))[0], "lost"]),
            "primary_after_reconnect": _inlet_spec(_frames_xml(), _chunks(rows_b, st_b, 4)),
            "events": _inlet_spec(_events_xml(), _markers(ev_l, [st_b[-1] + 0.01, st_b[-1] + 0.02], lead_empty=3))}),
        {"aborted_utterances": 1, "reconnects": 1, "final_decisions": 1, "frames": 7,
         "event_types": {"end": 1, "frame": 7, "header": 2, "segment_end": 1}})
    # --- markers: hypothesis-only producer, event clock
    hyp_st = [T0 + 0.6, T0 + 0.7, T0 + 0.8]
    add("L11", "l11-hypothesis-lsl-clock.json", "accept", "6 r5",
        "Hypothesis-only producer (primary = Markers); event_clock lsl: t_start / t_end get the clock correction",
        _scenario("inlet", "hypothesis route, event_clock lsl", route="hypothesis", inlets={
            "primary": _inlet_spec(_events_xml(name="acme.nts", sid="acme-1"), _markers(_hyp_events(T0, T0 + 0.5), hyp_st))}),
        {"hypothesis_times": [[T0 + TC, T0 + 0.25 + TC], [T0 + TC, T0 + 0.5 + TC]], "decisions": 2,
         "final_decisions": 1, "event_clock": "lsl", "marker_lsl_t": [t + TC for t in hyp_st]})
    add("L12", "l12-hypothesis-source-clock.json", "accept", "6 r5",
        "Same, event_clock absent (source): the time fields inside the JSON stay as sent",
        _scenario("inlet", "hypothesis route, event_clock source", route="hypothesis", inlets={
            "primary": _inlet_spec(_events_xml(name="acme.nts", sid="acme-1", event_clock=None),
                                   _markers(_hyp_events(5.0, 5.5), hyp_st))}),
        {"hypothesis_times": [[5.0, 5.25], [5.0, 5.5]], "final_decisions": 1, "event_clock": "source"})
    rows_p = _rows(4, 5)
    last = _stamps(4)[-1]
    add("L13", "l13-plain-markers.json", "accept", "5 r3-r4",
        "Plain string markers: a boundary marker becomes segment_end; other plain strings and bad JSON are ignored",
        _scenario("inlet", "plain markers", route="frames", consumer_settings={"boundary_markers": ["trial_end"]}, inlets={
            "primary": _inlet_spec(_frames_xml(), _chunks(rows_p, _stamps(4))),
            "events": _inlet_spec(_events_xml(), _markers(["hello", "{not json", "trial_end", {"type": "end"}],
                                                          [last + 0.01, last + 0.02, last + 0.03, last + 0.04]))}),
        {"bad_markers": 1, "ignored_markers": 1, "final_decisions": 1,
         "event_types": {"end": 1, "frame": 4, "header": 1, "segment_end": 1}})
    probs = [[0.7, 0.1, 0.1, 0.1], [0.25, 0.25, 0.25, 0.25], [0.0, 0.5, 0.25, 0.25]]
    add("L14", "l14-foreign-probs.json", "accept", "3 r7 (informative)",
        "A foreign class-probability stream (no nts_header): vocab from labels, values = probs, vocab_type from the settings",
        _scenario("inlet", "foreign probabilities", route="hypothesis",
                  consumer_settings={"values": "probs", "vocab_type": "command"}, inlets={
                      "primary": _inlet_spec(_info_xml("acme.probs", "Probabilities", 4, 4.0, "float32", "acme-p",
                                                       ["rest", "left", "right", "select"]),
                                             _chunks(probs, _stamps(3, T0, 0.25)))}),
        {"vocab_size": 4, "frames": 3, "neg_inf_cells": 1, "first_frame_t": T0 + TC, "final_decisions": 0})
    # --- reject: stream infos and samples
    add("L15", "l15-header-not-json.json", "reject", "4 r1", "desc/fidetype/nts_header is not JSON",
        _std("bad nts_header", frames_xml=_frames_xml(raw_header="{vocab: [")))
    add("L16", "l16-channel-count.json", "reject", "3 r2", "27 channels for a 28-token vocab",
        _std("channel count", frames_xml=_frames_xml(n=27, labels=list(VOCAB)[:27])))
    add("L17", "l17-int16-frames.json", "reject", "3 r1", "An NTS-native frames stream in int16",
        _std("int16", frames_xml=_frames_xml(fmt="int16")))
    swapped = list(VOCAB)
    swapped[1], swapped[2] = swapped[2], swapped[1]
    add("L18", "l18-labels-order.json", "reject", "3 r3", "Channel labels are not in vocab order (two swapped)",
        _std("labels order", frames_xml=_frames_xml(labels=swapped)))
    add("L19", "l19-unknown-binding.json", "reject", "9 r3", 'binding "nts-lsl/9.0" is not known',
        _std("unknown binding", frames_xml=_frames_xml(extra={"binding": "nts-lsl/9.0"})))
    add("L20", "l20-srate-mismatch.json", "reject", "3 r6", "nominal_srate 10 Hz, frame_period 0.125 s",
        _std("srate mismatch", frames_xml=_frames_xml(srate=10.0)))
    sc21 = _std("events not string")
    sc21["inlets"]["events"]["info_xml"] = _events_xml(fmt="float32")
    add("L21", "l21-events-not-string.json", "reject", "5 r1", "The events stream has channel format float32", sc21)
    rows_nan = _rows(3, 6)
    rows_nan[1][3] = "NaN"
    add("L22", "l22-nan-sample.json", "reject", "3 r5", "A frame sample holds NaN", _std("NaN", rows=rows_nan))
    add("L23", "l23-header-version.json", "reject", "4 r2", 'nts_header spec_version "9.9"',
        _std("spec version", frames_xml=_frames_xml(header=_hdr(spec_version="9.9"))))
    add("L24", "l24-bad-values.json", "reject", "4 r3", 'desc/fidetype/values "dB" is not a known kind',
        _std("values", frames_xml=_frames_xml(extra={"values": "dB"})))
    sc25 = _std("event clock")
    sc25["inlets"]["events"]["info_xml"] = _events_xml(event_clock="gps")
    add("L25", "l25-bad-event-clock.json", "reject", "6 r5", 'event_clock "gps" is not lsl or source', sc25)
    # --- decisions stream
    add("L26", "l26-decisions-valid.json", "accept", "8",
        "fidetype.decisions stream: a provisional OFFER then a final COMMIT, with the lsl extension record",
        _decisions("valid decisions", [_td(seq=0, is_final=False, action="OFFER", p_top1=0.71), _td(seq=1)]),
        {"decisions": 2, "final": 1, "acted": ["ab"]})
    add("L27", "l27-decisions-not-json.json", "reject", "8 r2", "A decisions sample is not JSON",
        _decisions("not JSON", [_td(), "COMMIT ab"]), failing="FEP2-DECISIONS")
    add("L28", "l28-decisions-bad-event.json", "reject", "8 r2", "A decisions sample has no is_final",
        _decisions("bad event", [_td(is_final=_DROP)]), failing="FEP2-DECISIONS")
    add("L29", "l29-decisions-float.json", "reject", "8 r1", "The decisions stream has channel format float32",
        _decisions("float32", [_td()], _dec_xml(fmt="float32")), failing="FEP2-DECISIONS")
    add("L30", "l30-decisions-no-event-type.json", "reject", "8 r1", "desc/fidetype/event_type is missing",
        _decisions("no event_type", [_td()], _dec_xml(desc={"event_type": None})), failing="FEP2-DECISIONS")
    add("L31", "l31-decisions-two-finals.json", "reject", "8 r2", "Two final decisions for one utterance",
        _decisions("two finals", [_td(seq=0), _td(seq=1, action="OFFER")]), failing="FEP2-DECISIONS")
    vs.sort(key=lambda v: v.vid)
    return vs


__all__ = ["CHECKS", "build_vectors", "check_file", "check_info", "consume", "decisions_info_errors",
           "run_decisions_scenario", "run_inlet_scenario"]
